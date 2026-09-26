from __future__ import annotations

"""Point-in-time US market-cap universe for the signal candidate.

Search/logo coverage keeps using the checked-in Nasdaq-100/S&P 500 union.  The
signal engine uses this independent NYSE/Nasdaq equity screen and never falls
back to a hand-picked ticker list when a source is incomplete.
"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re
from typing import Any, Optional

import requests
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import MarketRankingSnapshot
from app.services.ttl_cache import TTLCache


US_SIGNAL_UNIVERSE_VERSION = "us-market-cap-top100-v4"
US_SIGNAL_UNIVERSE_AUDIT_VERSION = "us-market-cap-source-audit-v2"
US_SIGNAL_UNIVERSE_LIMIT = 100
US_SIGNAL_UNIVERSE_CATEGORY = "us_signal_universe"
NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"
NASDAQ_SCREENER_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "SecretNoteUSSignalUniverse/1.0",
}
SIGNAL_EXCHANGES = ("nasdaq", "nyse")
VALID_YAHOO_EXCHANGES = {"NMS", "NGM", "NCM", "NYQ", "NASDAQ", "NYSE"}
US_SIGNAL_UNIVERSE_SOURCE_CACHE = TTLCache(maxsize=4)
US_SIGNAL_UNIVERSE_SOURCE_TTL_SECONDS = 300
EXCLUDED_NAME_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bpreferred\b",
        r"\bpreference\b",
        r"depositary shares?.*preferred",
        r"\bwarrants?\b",
        r"\bunits?\b",
        r"\brights?\b",
        r"\bnotes? due\b",
        r"\bsubordinated notes?\b",
        r"\bdebentures?\b",
        r"\bbonds?\b",
        r"\bzones\b",
        r"\betf\b",
        r"\betn\b",
        r"\bclosed.end fund\b",
        r"\bacquisition corp",
        r"\bblank check\b",
    )
)


def _screen_as_of_date(value: object) -> Optional[date]:
    text = str(value or "").strip()
    match = re.search(r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})", text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%b %d, %Y").date()
    except ValueError:
        return None


def _decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    if cleaned in {"", "--", "N/A", "None"}:
        return None
    multiplier = Decimal("1")
    if cleaned[-1:].upper() in {"K", "M", "B", "T"}:
        multiplier = {
            "K": Decimal("1000"),
            "M": Decimal("1000000"),
            "B": Decimal("1000000000"),
            "T": Decimal("1000000000000"),
        }[cleaned[-1].upper()]
        cleaned = cleaned[:-1]
    try:
        result = Decimal(cleaned) * multiplier
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _ticker(value: object) -> str:
    return str(value or "").strip().upper().replace("/", ".")


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _decimal_text(value: object) -> Optional[str]:
    parsed = _decimal(value)
    if parsed is None:
        return None
    normalized = parsed.normalize()
    return "0" if normalized == 0 else format(normalized, "f")


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda item: (
                item.isoformat() if isinstance(item, (date, datetime)) else str(item)
            ),
        ).encode("utf-8")
    ).hexdigest()


def _normalized_screen_row(
    row: dict[str, Any],
    *,
    exchange: str,
    include_classification: bool,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "code": _ticker(row.get("symbol")),
        "exchange": exchange.upper(),
        "name": _normalized_text(row.get("name")),
        "market_cap": _decimal_text(row.get("marketCap")),
        "screen_as_of": (
            row.get("_screen_as_of").isoformat()
            if isinstance(row.get("_screen_as_of"), date)
            else None
        ),
    }
    if include_classification:
        normalized.update(
            {
                "sector": _normalized_text(row.get("sector")),
                "industry": _normalized_text(row.get("industry")) or None,
                "country": _normalized_text(row.get("country")) or None,
            }
        )
    return normalized


def _normalized_classification_row(
    row: dict[str, Any],
    *,
    exchange: str,
) -> dict[str, Any]:
    return {
        "code": _ticker(row.get("symbol")),
        "exchange": exchange.upper(),
        "sector": _normalized_text(row.get("sector")) or None,
        "industry": _normalized_text(row.get("industry")) or None,
        "country": _normalized_text(row.get("country")) or None,
    }


def _exchange_screen_audit(
    exchange: str,
    ranked_rows: list[dict[str, Any]],
    eligible_rows: list[dict[str, Any]],
    *,
    classification_rows: Optional[list[dict[str, Any]]] = None,
    classification_as_of: Optional[date] = None,
) -> dict[str, Any]:
    normalized_ranked = sorted(
        (
            _normalized_screen_row(
                row,
                exchange=exchange,
                include_classification=False,
            )
            for row in ranked_rows
        ),
        key=lambda row: str(row["code"]),
    )
    normalized_eligible = sorted(
        (
            _normalized_screen_row(
                row,
                exchange=exchange,
                include_classification=True,
            )
            for row in eligible_rows
        ),
        key=lambda row: str(row["code"]),
    )
    normalized_classifications = sorted(
        (
            _normalized_classification_row(row, exchange=exchange)
            for row in (classification_rows or eligible_rows)
        ),
        key=lambda row: str(row["code"]),
    )
    return {
        "exchange": exchange.upper(),
        "raw_count": len(ranked_rows),
        "eligible_count": len(eligible_rows),
        "ranking_dataset_digest": _canonical_digest(normalized_ranked),
        "eligible_dataset_digest": _canonical_digest(normalized_eligible),
        "classification_dataset_digest": _canonical_digest(
            normalized_classifications
        ),
        "classification_as_of": (
            classification_as_of.isoformat()
            if classification_as_of is not None
            else None
        ),
        "classification_date_state": (
            "reported_match"
            if classification_as_of is not None
            else "provider_unreported"
        ),
        "classification_missing_count": sum(
            row["sector"] is None or row["industry"] is None
            for row in normalized_classifications
        ),
    }


def _fetch_exchange_screen(
    exchange: str,
    *,
    refresh: bool = False,
    audit_out: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    def load() -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        offset = 0
        expected_total: Optional[int] = None
        expected_as_of: Optional[date] = None
        page_limit = 5000
        while expected_total is None or offset < expected_total:
            response = requests.get(
                NASDAQ_SCREENER_URL,
                params={
                    "tableonly": "true",
                    "limit": page_limit,
                    "offset": offset,
                    "exchange": exchange,
                },
                headers=NASDAQ_SCREENER_HEADERS,
                timeout=25,
            )
            response.raise_for_status()
            data = (response.json() or {}).get("data") or {}
            table = data.get("table") or {}
            page = list(table.get("rows") or data.get("rows") or [])
            page_as_of = _screen_as_of_date(data.get("asof") or data.get("asOf"))
            if page_as_of is None:
                raise ValueError(
                    f"Nasdaq {exchange} screener as-of date is unavailable"
                )
            if expected_as_of is None:
                expected_as_of = page_as_of
            elif page_as_of != expected_as_of:
                raise ValueError(
                    f"Nasdaq {exchange} screener as-of changed during pagination"
                )
            total_value = _decimal(
                data.get("totalrecords")
                or data.get("totalRecords")
                or table.get("totalrecords")
                or table.get("totalRecords")
            )
            if total_value is None or total_value < 1:
                raise ValueError(f"Nasdaq {exchange} screener total is unavailable")
            page_total = int(total_value)
            if expected_total is None:
                expected_total = page_total
            elif page_total != expected_total:
                raise ValueError(
                    f"Nasdaq {exchange} screener total changed during pagination"
                )
            if not page:
                raise ValueError(f"Nasdaq {exchange} screener page is incomplete")
            rows.extend({**item, "_screen_as_of": page_as_of} for item in page)
            offset += len(page)
            if len(page) > page_limit or len(rows) > expected_total:
                raise ValueError(
                    f"Nasdaq {exchange} screener pagination is inconsistent"
                )
        if expected_total is None or len(rows) != expected_total:
            raise ValueError(f"Nasdaq {exchange} screener response is incomplete")
        detail_response = requests.get(
            NASDAQ_SCREENER_URL,
            params={
                "tableonly": "true",
                "limit": page_limit,
                "offset": 0,
                "download": "true",
                "exchange": exchange,
            },
            headers=NASDAQ_SCREENER_HEADERS,
            timeout=25,
        )
        detail_response.raise_for_status()
        detail_data = (detail_response.json() or {}).get("data") or {}
        detail_table = detail_data.get("table") or {}
        detail_rows = list(detail_data.get("rows") or detail_table.get("rows") or [])
        detail_as_of_value = detail_data.get("asof") or detail_data.get("asOf")
        detail_as_of = _screen_as_of_date(detail_as_of_value)
        if detail_as_of_value not in (None, "") and detail_as_of is None:
            raise ValueError(
                f"Nasdaq {exchange} classification as-of date is invalid"
            )
        if detail_as_of is not None and detail_as_of != expected_as_of:
            raise ValueError(
                f"Nasdaq {exchange} ranking and classification dates differ"
            )
        ranked_by_code = {_ticker(item.get("symbol")): item for item in rows}
        if len(ranked_by_code) != expected_total:
            raise ValueError(
                f"Nasdaq {exchange} screener ranking contains duplicate tickers"
            )
        eligible_ranked_by_code = {
            code: item
            for code, item in ranked_by_code.items()
            if _screen_row_allowed(item)
        }
        detail_codes = [_ticker(item.get("symbol")) for item in detail_rows]
        if any(not code for code in detail_codes) or len(set(detail_codes)) != len(
            detail_codes
        ):
            raise ValueError(
                f"Nasdaq {exchange} classification contains invalid or duplicate tickers"
            )
        detail_by_code = dict(zip(detail_codes, detail_rows))
        eligible_detail_codes = {
            code for code, item in detail_by_code.items() if _screen_row_allowed(item)
        }
        missing_detail_codes = set(eligible_ranked_by_code) - set(detail_by_code)
        unexpected_detail_codes = eligible_detail_codes - set(ranked_by_code)
        if missing_detail_codes or unexpected_detail_codes:
            raise ValueError(
                f"Nasdaq {exchange} eligible ranking and classification sets differ"
            )
        classification_rows = [
            detail_by_code[code] for code in eligible_ranked_by_code
        ]
        if any(
            not {"sector", "industry", "country"}.issubset(row)
            for row in classification_rows
        ):
            raise ValueError(
                f"Nasdaq {exchange} classification fields are incomplete"
            )
        eligible_rows = [
            {
                **eligible_ranked_by_code[code],
                "sector": detail_by_code[code].get("sector"),
                "industry": detail_by_code[code].get("industry"),
                "country": detail_by_code[code].get("country"),
            }
            for code in eligible_ranked_by_code
        ]
        return {
            "rows": eligible_rows,
            "audit": _exchange_screen_audit(
                exchange,
                rows,
                eligible_rows,
                classification_rows=classification_rows,
                classification_as_of=detail_as_of,
            ),
        }

    if refresh:
        dataset = load()
        US_SIGNAL_UNIVERSE_SOURCE_CACHE.set(
            ("exchange_screen", exchange),
            dataset,
            US_SIGNAL_UNIVERSE_SOURCE_TTL_SECONDS,
        )
    else:
        dataset = US_SIGNAL_UNIVERSE_SOURCE_CACHE.get_or_set(
            ("exchange_screen", exchange),
            US_SIGNAL_UNIVERSE_SOURCE_TTL_SECONDS,
            load,
        )
    if audit_out is not None:
        audit_out.update(dict(dataset["audit"]))
    return list(dataset["rows"])


def _screen_row_allowed(row: dict[str, Any]) -> bool:
    symbol = _ticker(row.get("symbol"))
    name = str(row.get("name") or "").strip()
    market_cap = _decimal(row.get("marketCap"))
    if not symbol or not name or market_cap is None or market_cap <= 0:
        return False
    if any(pattern.search(name) for pattern in EXCLUDED_NAME_PATTERNS):
        return False
    return not bool(re.search(r"(?:\+|=|\^)", symbol))


def _normalized_candidate_row(item: dict[str, Any]) -> dict[str, Any]:
    screen_as_of = item.get("screen_as_of")
    return {
        "code": _ticker(item.get("code")),
        "name": _normalized_text(item.get("name")),
        "screen_exchange": str(item.get("screen_exchange") or "").upper(),
        "screen_market_cap": _decimal_text(item.get("screen_market_cap")),
        "screen_last_price": _decimal_text(item.get("screen_last_price")),
        "screen_as_of": (
            screen_as_of.isoformat()
            if isinstance(screen_as_of, date)
            else str(screen_as_of or "") or None
        ),
        "sector": _normalized_text(item.get("sector")),
        "industry": _normalized_text(item.get("industry")) or None,
        "country": _normalized_text(item.get("country")) or None,
    }


def _screen_source_audit(
    candidates: list[dict[str, Any]],
    exchange_audits: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    audits_by_exchange = {
        str(item.get("exchange") or "").upper(): dict(item)
        for item in list(exchange_audits or [])
        if isinstance(item, dict)
    }
    ordered_exchange_audits: list[dict[str, Any]] = []
    for exchange in SIGNAL_EXCHANGES:
        exchange_name = exchange.upper()
        audit = audits_by_exchange.get(exchange_name)
        if audit is None:
            exchange_rows = [
                item
                for item in candidates
                if str(item.get("screen_exchange") or "").upper() == exchange_name
            ]
            normalized_rows = [
                {
                    "symbol": item.get("code"),
                    "name": item.get("name"),
                    "marketCap": item.get("screen_market_cap"),
                    "sector": item.get("sector"),
                    "industry": item.get("industry"),
                    "country": item.get("country"),
                    "_screen_as_of": item.get("screen_as_of"),
                }
                for item in exchange_rows
            ]
            audit = _exchange_screen_audit(
                exchange,
                normalized_rows,
                normalized_rows,
            )
        ordered_exchange_audits.append(audit)
    normalized_candidates = sorted(
        (_normalized_candidate_row(item) for item in candidates),
        key=lambda item: (
            -Decimal(str(item["screen_market_cap"])),
            str(item["code"]),
        ),
    )
    return {
        "exchanges": ordered_exchange_audits,
        "prefilter_candidate_count": len(candidates),
        "prefilter_candidate_digest": _canonical_digest(normalized_candidates),
    }


def _align_candidates_to_completed_session(
    candidates: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    completed_date: date,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Return a completed-session ranking input and its audit evidence.

    Nasdaq is authoritative when its screen is current. If it is exactly one
    XNYS session behind, Yahoo may bridge only when every prefiltered candidate
    has a fully validated latest-session equity quote and market cap. A wider
    lag, a partial quote set, or an invalid identity fails closed.
    """

    from app.services.us_market_calendar import recent_us_market_session_dates

    screen_dates = {
        value
        for value in (
            _parse_snapshot_date(item.get("screen_as_of")) for item in candidates
        )
        if value is not None
    }
    if len(screen_dates) != 1 or len(candidates) < US_SIGNAL_UNIVERSE_LIMIT + 1:
        raise ValueError("US screener dates are missing or misaligned")
    screen_date = next(iter(screen_dates))
    if screen_date == completed_date:
        alignment = {
            "mode": "same_session_nasdaq",
            "screen_as_of": screen_date.isoformat(),
            "quote_as_of": completed_date.isoformat(),
            "completed_session": completed_date.isoformat(),
            "adjusted_candidate_count": 0,
            "evidence_digest": _canonical_digest(
                {
                    "mode": "same_session_nasdaq",
                    "screen_as_of": screen_date,
                    "completed_session": completed_date,
                    "candidate_count": len(candidates),
                }
            ),
        }
        return list(candidates), alignment, "nasdaq_screener_market_cap"

    recent_sessions = recent_us_market_session_dates(completed_date, 2)
    if len(recent_sessions) != 2 or screen_date != recent_sessions[0]:
        raise ValueError(
            "US screener is more than one completed XNYS session behind"
        )
    if len(quotes) != len(candidates):
        raise ValueError(
            "US latest-session market-cap bridge requires every candidate quote"
        )

    aligned: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for candidate in candidates:
        code = str(candidate["code"])
        quote = dict(quotes.get(code) or {})
        market_cap = _decimal(quote.get("marketCap"))
        price = _decimal(quote.get("regularMarketPrice"))
        quote_date = _quote_date(quote.get("regularMarketTime"))
        quote_type = str(quote.get("quoteType") or "").upper()
        exchange = str(quote.get("exchange") or "").upper()
        currency = str(quote.get("currency") or "").upper()
        quote_symbol = _ticker(quote.get("symbol"))
        if (
            market_cap is None
            or market_cap <= 0
            or price is None
            or price <= 0
            or quote_date != completed_date
            or quote_type != "EQUITY"
            or exchange not in VALID_YAHOO_EXCHANGES
            or currency != "USD"
            or quote_symbol.replace("-", ".") != code.replace("-", ".")
        ):
            raise ValueError(
                f"US latest-session market-cap bridge quote is invalid for {code}"
            )
        aligned.append(
            {
                **candidate,
                "source_screen_as_of": screen_date,
                "source_screen_market_cap": candidate.get("screen_market_cap"),
                "screen_market_cap": market_cap,
                "screen_as_of": completed_date,
            }
        )
        evidence.append(
            {
                "code": code,
                "screen_as_of": screen_date,
                "source_screen_market_cap": _decimal_text(
                    candidate.get("screen_market_cap")
                ),
                "quote_as_of": quote_date,
                "quote_market_cap": _decimal_text(market_cap),
            }
        )

    alignment = {
        "mode": "prior_session_yahoo_market_cap_bridge",
        "screen_as_of": screen_date.isoformat(),
        "quote_as_of": completed_date.isoformat(),
        "completed_session": completed_date.isoformat(),
        "adjusted_candidate_count": len(aligned),
        "evidence_digest": _canonical_digest(
            sorted(evidence, key=lambda item: str(item["code"]))
        ),
    }
    return (
        aligned,
        alignment,
        "yahoo_market_cap_validated_against_prior_nasdaq_candidate_pool",
    )


def _screen_candidates(
    *,
    refresh: bool = False,
    audit_out: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    exchange_audits: list[dict[str, Any]] = []
    for exchange in SIGNAL_EXCHANGES:
        exchange_audit: dict[str, Any] = {}
        exchange_rows = _fetch_exchange_screen(
            exchange,
            refresh=refresh,
            audit_out=exchange_audit,
        )
        if not exchange_audit:
            exchange_audit = _exchange_screen_audit(
                exchange,
                list(exchange_rows),
                [row for row in exchange_rows if _screen_row_allowed(row)],
            )
        exchange_audits.append(exchange_audit)
        for raw in exchange_rows:
            if not _screen_row_allowed(raw):
                continue
            rows.append(
                {
                    "code": _ticker(raw.get("symbol")),
                    "name": str(raw.get("name") or raw.get("symbol") or "").strip(),
                    "screen_exchange": exchange.upper(),
                    "screen_market_cap": _decimal(raw.get("marketCap")),
                    "screen_last_price": _decimal(raw.get("lastsale")),
                    "screen_as_of": raw.get("_screen_as_of"),
                    "sector": str(raw.get("sector") or "").strip() or "기타",
                    "industry": str(raw.get("industry") or "").strip() or None,
                    "country": str(raw.get("country") or "").strip() or None,
                }
            )
    # A wide prefilter bounds Yahoo calls while safely covering the global top
    # 100 even when one exchange dominates the upper tail.
    rows.sort(key=lambda item: (-int(item["screen_market_cap"]), item["code"]))
    screen_dates = {
        item.get("screen_as_of")
        for item in rows
        if isinstance(item.get("screen_as_of"), date)
    }
    if len(screen_dates) != 1 or any(
        not isinstance(item.get("screen_as_of"), date) for item in rows
    ):
        raise ValueError("NYSE and Nasdaq screener dates are missing or misaligned")
    duplicate_codes = {
        code
        for code, count in Counter(str(item["code"]) for item in rows).items()
        if count > 1
    }
    if duplicate_codes:
        raise ValueError(
            "NYSE and Nasdaq screeners contain duplicate ticker identities"
        )
    unique: dict[str, dict[str, Any]] = {}
    for item in rows:
        unique.setdefault(str(item["code"]), item)
    candidates = list(unique.values())[:600]
    if audit_out is not None:
        audit_out.update(_screen_source_audit(candidates, exchange_audits))
    return candidates


def _quote_date(value: object) -> Optional[date]:
    try:
        from app.services.us_market import NEW_YORK_TZ

        return (
            datetime.fromtimestamp(int(value), timezone.utc)
            .astimezone(NEW_YORK_TZ)
            .date()
        )
    except (TypeError, ValueError, OSError):
        return None


def _cik_for_code(code: str, cik_by_code: dict[str, str]) -> Optional[str]:
    return cik_by_code.get(code) or cik_by_code.get(code.replace(".", "-"))


def _issuer_key(code: str, name: str, cik_by_code: dict[str, str]) -> str:
    del name  # Names are display data, never an authoritative issuer identity.
    cik = _cik_for_code(code, cik_by_code)
    if not cik:
        raise ValueError(f"SEC CIK is missing for US signal boundary member {code}")
    return f"cik:{cik}"


def _screen_issuer_boundary(
    candidates: list[dict[str, Any]],
    cik_by_code: dict[str, str],
    *,
    ranking_authority: str = "nasdaq_screener_market_cap",
    evidence_out: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Freeze the top 100 issuers using the audited candidate market cap.

    The normal path uses the same-session Nasdaq market cap. When Nasdaq is
    exactly one completed XNYS session behind, the caller may supply an
    all-candidate Yahoo market-cap bridge for the latest completed session.
    SEC CIK must be complete through the 100/101 boundary, including every
    market-cap tie at that boundary.
    """

    ordered = sorted(
        candidates,
        key=lambda item: (
            -Decimal(str(item["screen_market_cap"])),
            str(item["code"]),
        ),
    )
    issuers: dict[str, dict[str, Any]] = {}
    cutoff_market_cap: Optional[Decimal] = None
    for candidate in ordered:
        screen_market_cap = _decimal(candidate.get("screen_market_cap"))
        if screen_market_cap is None or screen_market_cap <= 0:
            continue
        if cutoff_market_cap is not None and screen_market_cap < cutoff_market_cap:
            break
        code = str(candidate["code"])
        issuer_key = _issuer_key(
            code,
            str(candidate.get("name") or code),
            cik_by_code,
        )
        issuer = issuers.setdefault(
            issuer_key,
            {
                "issuer_key": issuer_key,
                "screen_market_cap": screen_market_cap,
                "candidates": [],
            },
        )
        issuer["screen_market_cap"] = max(
            Decimal(str(issuer["screen_market_cap"])),
            screen_market_cap,
        )
        issuer["candidates"].append(candidate)
        if len(issuers) >= US_SIGNAL_UNIVERSE_LIMIT + 1 and cutoff_market_cap is None:
            cutoff_market_cap = screen_market_cap

    if len(issuers) < US_SIGNAL_UNIVERSE_LIMIT + 1:
        raise ValueError("US screener did not prove the top-100 issuer boundary")

    ranked_issuers = sorted(
        issuers.values(),
        key=lambda item: (
            -Decimal(str(item["screen_market_cap"])),
            str(item["issuer_key"]),
        ),
    )
    eligible = ranked_issuers[:US_SIGNAL_UNIVERSE_LIMIT]
    eligible_by_key = {str(item["issuer_key"]): item for item in eligible}

    # Include lower-ranked alternate classes of a selected issuer so one
    # missing class quote can be replaced without promoting issuer #101.
    included_codes = {
        str(candidate["code"])
        for issuer in eligible
        for candidate in issuer["candidates"]
    }
    for candidate in ordered:
        code = str(candidate["code"])
        if code in included_codes:
            continue
        cik = _cik_for_code(code, cik_by_code)
        issuer_key = f"cik:{cik}" if cik else ""
        if issuer_key in eligible_by_key:
            eligible_by_key[issuer_key]["candidates"].append(candidate)
            included_codes.add(code)
    if evidence_out is not None:
        rank_100 = ranked_issuers[US_SIGNAL_UNIVERSE_LIMIT - 1]
        rank_101 = ranked_issuers[US_SIGNAL_UNIVERSE_LIMIT]
        rank_100_cap = Decimal(str(rank_100["screen_market_cap"]))
        rank_101_cap = Decimal(str(rank_101["screen_market_cap"]))
        tie_applied = rank_100_cap == rank_101_cap
        tie_issuers = (
            [
                item
                for item in ranked_issuers
                if Decimal(str(item["screen_market_cap"])) == rank_100_cap
            ]
            if tie_applied
            else []
        )
        selected_keys = {str(item["issuer_key"]) for item in eligible}

        def boundary_record(item: dict[str, Any], rank: int) -> dict[str, Any]:
            return {
                "rank": rank,
                "issuer_key": str(item["issuer_key"]),
                "market_cap": _decimal_text(item["screen_market_cap"]),
                "candidate_codes": sorted(
                    {str(candidate["code"]) for candidate in item["candidates"]}
                ),
            }

        tie_keys = sorted(str(item["issuer_key"]) for item in tie_issuers)
        evidence_out.update(
            {
                "ranking_authority": ranking_authority,
                "issuer_identity": "sec_cik",
                "proven_issuer_count": len(ranked_issuers),
                "rank_100": boundary_record(rank_100, US_SIGNAL_UNIVERSE_LIMIT),
                "rank_101": boundary_record(
                    rank_101,
                    US_SIGNAL_UNIVERSE_LIMIT + 1,
                ),
                "tie": {
                    "applied": tie_applied,
                    "market_cap": _decimal_text(rank_100_cap) if tie_applied else None,
                    "tie_breaker": "sec_cik_ascending",
                    "issuer_keys": tie_keys,
                    "selected_issuer_keys": sorted(
                        key for key in tie_keys if key in selected_keys
                    ),
                    "excluded_issuer_keys": sorted(
                        key for key in tie_keys if key not in selected_keys
                    ),
                },
            }
        )
    return eligible


def _validated_members(
    candidates: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    cik_by_code: dict[str, str],
    *,
    ranking_authority: str = "nasdaq_screener_market_cap",
    boundary_evidence_out: Optional[dict[str, Any]] = None,
) -> tuple[list[dict[str, Any]], Optional[date]]:
    # Freeze the authoritative issuer boundary before consulting Yahoo. A
    # missing quote for issuer #1 must not silently promote issuer #101.
    eligible_issuers = _screen_issuer_boundary(
        candidates,
        cik_by_code,
        ranking_authority=ranking_authority,
        evidence_out=boundary_evidence_out,
    )

    quote_rows: dict[str, list[dict[str, Any]]] = {}
    quote_dates: list[date] = []
    for issuer in eligible_issuers:
        issuer_key = str(issuer["issuer_key"])
        for candidate in issuer["candidates"]:
            code = str(candidate["code"])
            quote = quotes.get(code) or {}
            market_cap = _decimal(quote.get("marketCap"))
            price = _decimal(quote.get("regularMarketPrice"))
            quote_type = str(quote.get("quoteType") or "").upper()
            exchange = str(quote.get("exchange") or "").upper()
            currency = str(quote.get("currency") or "").upper()
            quote_symbol = _ticker(quote.get("symbol"))
            observed_date = _quote_date(quote.get("regularMarketTime"))
            if (
                market_cap is None
                or market_cap <= 0
                or price is None
                or price <= 0
                or quote_type != "EQUITY"
                or exchange not in VALID_YAHOO_EXCHANGES
                or currency != "USD"
                or quote_symbol.replace("-", ".") != code.replace("-", ".")
                or observed_date is None
            ):
                continue
            name = str(
                quote.get("longName") or quote.get("shortName") or candidate["name"]
            )
            if any(pattern.search(name) for pattern in EXCLUDED_NAME_PATTERNS):
                continue
            average_volume = _decimal(quote.get("averageDailyVolume3Month")) or Decimal(
                "0"
            )
            liquidity = price * average_volume
            quote_dates.append(observed_date)
            quote_rows.setdefault(issuer_key, []).append(
                {
                    **candidate,
                    "name": name,
                    "market": "NASDAQ"
                    if exchange in {"NMS", "NGM", "NCM", "NASDAQ"}
                    else "NYSE",
                    "exchange": exchange,
                    "currency": "USD",
                    "market_cap": Decimal(str(issuer["screen_market_cap"])),
                    "validation_market_cap": market_cap,
                    "price": price,
                    "quote_date": observed_date,
                    "issuer_key": issuer_key,
                    "cik": _cik_for_code(code, cik_by_code),
                    "average_daily_dollar_volume_3m": liquidity,
                    "legacy_regular_market_change_percent": _decimal(
                        quote.get("regularMarketChangePercent")
                    ),
                    "legacy_regular_market_volume": (
                        int(quote.get("regularMarketVolume") or 0) or None
                    ),
                    "legacy_fifty_day_average_change_percent": _decimal(
                        quote.get("fiftyDayAverageChangePercent")
                    ),
                    "legacy_two_hundred_day_average_change_percent": _decimal(
                        quote.get("twoHundredDayAverageChangePercent")
                    ),
                    "legacy_trailing_pe": _decimal(quote.get("trailingPE")),
                    "legacy_price_to_book": _decimal(quote.get("priceToBook")),
                    "is_adr": bool(
                        re.search(
                            r"\bADR\b|American Depositary",
                            name,
                            re.IGNORECASE,
                        )
                    ),
                }
            )

    target_date = Counter(quote_dates).most_common(1)[0][0] if quote_dates else None
    issuer_rows = {
        issuer_key: [row for row in rows if row["quote_date"] == target_date]
        for issuer_key, rows in quote_rows.items()
    }
    issuer_rows = {key: rows for key, rows in issuer_rows.items() if rows}

    representatives: list[dict[str, Any]] = []
    for issuer in eligible_issuers:
        issuer_key = str(issuer["issuer_key"])
        rows = issuer_rows.get(issuer_key) or []
        if not rows:
            continue
        chosen = sorted(
            rows,
            key=lambda item: (
                -Decimal(str(item["average_daily_dollar_volume_3m"])),
                str(item["code"]),
            ),
        )[0]
        representatives.append(
            {
                **chosen,
                "market_cap": Decimal(str(issuer["screen_market_cap"])),
            }
        )
    if (
        boundary_evidence_out is not None
        and len(representatives) == US_SIGNAL_UNIVERSE_LIMIT
    ):
        rank_100 = boundary_evidence_out.get("rank_100")
        if isinstance(rank_100, dict):
            rank_100["selected_code"] = str(representatives[-1]["code"])
    return representatives, target_date


def _normalized_quote_observation(
    code: str,
    quote: dict[str, Any],
) -> dict[str, Any]:
    regular_market_time = quote.get("regularMarketTime")
    try:
        normalized_market_time: Optional[int] = int(regular_market_time)
    except (TypeError, ValueError):
        normalized_market_time = None
    normalized_quote_date = _quote_date(normalized_market_time)
    return {
        "requested_code": _ticker(code),
        "present": bool(quote),
        "observed_symbol": _ticker(quote.get("symbol")) or None,
        "quote_type": str(quote.get("quoteType") or "").strip().upper() or None,
        "exchange": str(quote.get("exchange") or "").strip().upper() or None,
        "currency": str(quote.get("currency") or "").strip().upper() or None,
        "market_cap": _decimal_text(quote.get("marketCap")),
        "regular_market_price": _decimal_text(quote.get("regularMarketPrice")),
        "regular_market_time": normalized_market_time,
        "quote_date": (
            normalized_quote_date.isoformat()
            if normalized_quote_date is not None
            else None
        ),
        "long_name": _normalized_text(quote.get("longName")) or None,
        "short_name": _normalized_text(quote.get("shortName")) or None,
        "average_daily_volume_3m": _decimal_text(quote.get("averageDailyVolume3Month")),
        "regular_market_volume": _decimal_text(quote.get("regularMarketVolume")),
        "regular_market_change_percent": _decimal_text(
            quote.get("regularMarketChangePercent")
        ),
        "fifty_day_average_change_percent": _decimal_text(
            quote.get("fiftyDayAverageChangePercent")
        ),
        "two_hundred_day_average_change_percent": _decimal_text(
            quote.get("twoHundredDayAverageChangePercent")
        ),
        "trailing_pe": _decimal_text(quote.get("trailingPE")),
        "price_to_book": _decimal_text(quote.get("priceToBook")),
    }


def _quote_source_audit(
    candidates: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    observations = [
        _normalized_quote_observation(
            str(candidate["code"]),
            dict(quotes.get(str(candidate["code"])) or {}),
        )
        for candidate in sorted(candidates, key=lambda item: str(item["code"]))
    ]
    return {
        "requested_count": len(candidates),
        "returned_count": len(quotes),
        "observation_digest": _canonical_digest(observations),
    }


def _sec_identity_source_audit(
    candidates: list[dict[str, Any]],
    cik_by_code: dict[str, str],
) -> dict[str, Any]:
    observations = [
        {
            "code": str(candidate["code"]),
            "cik": str(_cik_for_code(str(candidate["code"]), cik_by_code) or "")
            or None,
        }
        for candidate in sorted(candidates, key=lambda item: str(item["code"]))
    ]
    return {
        "requested_count": len(candidates),
        "mapped_count": sum(item["cik"] is not None for item in observations),
        "identity_digest": _canonical_digest(observations),
    }


def _snapshot_audit_checksum(
    source_audit: dict[str, Any],
    boundary_evidence: dict[str, Any],
    *,
    member_checksum: str,
    universe_version: str,
    universe_as_of: object,
) -> str:
    return _canonical_digest(
        {
            "integrity_scope": "trusted_database_snapshot_v1",
            "universe_version": universe_version,
            "universe_as_of": str(universe_as_of),
            "member_checksum": member_checksum,
            "source_audit": source_audit,
            "boundary_evidence": boundary_evidence,
        }
    )


def _parse_snapshot_date(value: object) -> Optional[date]:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    text = str(value or "")
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == text else None


def _parse_snapshot_datetime(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _sha256_digest_is_valid(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _strict_int_at_least(value: object, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _valid_audit_issuer_key(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"cik:\d{10}", value))


def _boundary_record_values(
    value: object,
    *,
    expected_rank: int,
    require_selected_code: bool,
) -> Optional[tuple[str, Decimal, list[str], Optional[str]]]:
    if not isinstance(value, dict):
        return None
    expected_keys = {"rank", "issuer_key", "market_cap", "candidate_codes"}
    if require_selected_code:
        expected_keys.add("selected_code")
    if set(value) != expected_keys or value.get("rank") != expected_rank:
        return None
    issuer_key = value.get("issuer_key")
    market_cap_value = value.get("market_cap")
    market_cap = _decimal(market_cap_value)
    codes = value.get("candidate_codes")
    selected_code = value.get("selected_code") if require_selected_code else None
    if (
        not _valid_audit_issuer_key(issuer_key)
        or not isinstance(market_cap_value, str)
        or market_cap is None
        or market_cap <= 0
        or market_cap_value != _decimal_text(market_cap_value)
        or not isinstance(codes, list)
        or not codes
        or any(
            not isinstance(code, str) or not code or code != _ticker(code)
            for code in codes
        )
        or codes != sorted(set(codes))
        or (
            require_selected_code
            and (
                not isinstance(selected_code, str)
                or selected_code not in codes
                or selected_code != _ticker(selected_code)
            )
        )
    ):
        return None
    return str(issuer_key), market_cap, list(codes), selected_code


def _source_audit_is_valid(
    payload: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    source_candidate_count: int,
    validated_quote_count: int,
) -> bool:
    source_audit = payload.get("source_audit")
    boundary = payload.get("boundary_evidence")
    audit_checksum = payload.get("audit_checksum")
    if (
        not isinstance(source_audit, dict)
        or set(source_audit)
        != {
            "version",
            "trust_model",
            "screen",
            "alignment",
            "quotes",
            "sec_identities",
        }
        or source_audit.get("version") != US_SIGNAL_UNIVERSE_AUDIT_VERSION
        or source_audit.get("trust_model")
        != "trusted_database_integrity_checksum_not_external_signature"
        or not isinstance(boundary, dict)
        or set(boundary)
        != {
            "ranking_authority",
            "issuer_identity",
            "proven_issuer_count",
            "rank_100",
            "rank_101",
            "tie",
        }
        or boundary.get("issuer_identity") != "sec_cik"
        or not _sha256_digest_is_valid(audit_checksum)
        or not hmac.compare_digest(
            str(audit_checksum),
            _snapshot_audit_checksum(
                source_audit,
                boundary,
                member_checksum=str(payload.get("checksum") or ""),
                universe_version=str(payload.get("universe_version") or ""),
                universe_as_of=payload.get("universe_as_of"),
            ),
        )
    ):
        return False

    alignment = source_audit.get("alignment")
    universe_date = _parse_snapshot_date(payload.get("universe_as_of"))
    if (
        not isinstance(alignment, dict)
        or set(alignment)
        != {
            "mode",
            "screen_as_of",
            "quote_as_of",
            "completed_session",
            "adjusted_candidate_count",
            "evidence_digest",
        }
        or universe_date is None
        or _parse_snapshot_date(alignment.get("quote_as_of")) != universe_date
        or _parse_snapshot_date(alignment.get("completed_session")) != universe_date
        or not _sha256_digest_is_valid(alignment.get("evidence_digest"))
    ):
        return False
    alignment_mode = alignment.get("mode")
    screen_as_of = _parse_snapshot_date(alignment.get("screen_as_of"))
    ranking_authority = boundary.get("ranking_authority")
    if alignment_mode == "same_session_nasdaq":
        if (
            screen_as_of != universe_date
            or alignment.get("adjusted_candidate_count") != 0
            or ranking_authority != "nasdaq_screener_market_cap"
        ):
            return False
    elif alignment_mode == "prior_session_yahoo_market_cap_bridge":
        try:
            from app.services.us_market_calendar import recent_us_market_session_dates

            sessions = recent_us_market_session_dates(universe_date, 2)
        except Exception:
            return False
        if (
            len(sessions) != 2
            or screen_as_of != sessions[0]
            or alignment.get("adjusted_candidate_count") != source_candidate_count
            or ranking_authority
            != "yahoo_market_cap_validated_against_prior_nasdaq_candidate_pool"
            or validated_quote_count != source_candidate_count
        ):
            return False
    else:
        return False

    screen = source_audit.get("screen")
    if (
        not isinstance(screen, dict)
        or set(screen)
        != {"exchanges", "prefilter_candidate_count", "prefilter_candidate_digest"}
        or screen.get("prefilter_candidate_count") != source_candidate_count
        or not _sha256_digest_is_valid(screen.get("prefilter_candidate_digest"))
    ):
        return False
    exchanges = screen.get("exchanges")
    expected_exchanges = [exchange.upper() for exchange in SIGNAL_EXCHANGES]
    if not isinstance(exchanges, list) or len(exchanges) != len(expected_exchanges):
        return False
    eligible_total = 0
    for expected_exchange, exchange_audit in zip(expected_exchanges, exchanges):
        if (
            not isinstance(exchange_audit, dict)
            or set(exchange_audit)
            != {
                "exchange",
                "raw_count",
                "eligible_count",
                "ranking_dataset_digest",
                "eligible_dataset_digest",
                "classification_dataset_digest",
                "classification_as_of",
                "classification_date_state",
                "classification_missing_count",
            }
            or exchange_audit.get("exchange") != expected_exchange
            or not _strict_int_at_least(exchange_audit.get("raw_count"), 1)
            or not _strict_int_at_least(exchange_audit.get("eligible_count"), 0)
            or int(exchange_audit["eligible_count"]) > int(exchange_audit["raw_count"])
            or not _sha256_digest_is_valid(exchange_audit.get("ranking_dataset_digest"))
            or not _sha256_digest_is_valid(
                exchange_audit.get("eligible_dataset_digest")
            )
            or not _sha256_digest_is_valid(
                exchange_audit.get("classification_dataset_digest")
            )
            or exchange_audit.get("classification_date_state")
            not in {"reported_match", "provider_unreported"}
            or not _strict_int_at_least(
                exchange_audit.get("classification_missing_count"), 0
            )
            or int(exchange_audit["classification_missing_count"])
            > int(exchange_audit["eligible_count"])
        ):
            return False
        classification_as_of = exchange_audit.get("classification_as_of")
        classification_date_state = exchange_audit["classification_date_state"]
        if classification_date_state == "reported_match":
            if _parse_snapshot_date(classification_as_of) != _parse_snapshot_date(
                alignment.get("screen_as_of")
            ):
                return False
        elif classification_as_of is not None:
            return False
        eligible_total += int(exchange_audit["eligible_count"])
    if eligible_total < source_candidate_count:
        return False

    quote_audit = source_audit.get("quotes")
    if (
        not isinstance(quote_audit, dict)
        or set(quote_audit)
        != {"requested_count", "returned_count", "observation_digest"}
        or quote_audit.get("requested_count") != source_candidate_count
        or quote_audit.get("returned_count") != validated_quote_count
        or not _strict_int_at_least(
            quote_audit.get("returned_count"), US_SIGNAL_UNIVERSE_LIMIT
        )
        or int(quote_audit["returned_count"]) > source_candidate_count
        or not _sha256_digest_is_valid(quote_audit.get("observation_digest"))
    ):
        return False

    sec_audit = source_audit.get("sec_identities")
    proven_issuer_count = boundary.get("proven_issuer_count")
    if (
        not isinstance(sec_audit, dict)
        or set(sec_audit) != {"requested_count", "mapped_count", "identity_digest"}
        or sec_audit.get("requested_count") != source_candidate_count
        or not _strict_int_at_least(
            sec_audit.get("mapped_count"),
            US_SIGNAL_UNIVERSE_LIMIT + 1,
        )
        or int(sec_audit["mapped_count"]) > source_candidate_count
        or not _sha256_digest_is_valid(sec_audit.get("identity_digest"))
        or not _strict_int_at_least(
            proven_issuer_count,
            US_SIGNAL_UNIVERSE_LIMIT + 1,
        )
        or int(proven_issuer_count) > int(sec_audit["mapped_count"])
    ):
        return False

    rank_100 = _boundary_record_values(
        boundary.get("rank_100"),
        expected_rank=US_SIGNAL_UNIVERSE_LIMIT,
        require_selected_code=True,
    )
    rank_101 = _boundary_record_values(
        boundary.get("rank_101"),
        expected_rank=US_SIGNAL_UNIVERSE_LIMIT + 1,
        require_selected_code=False,
    )
    if rank_100 is None or rank_101 is None:
        return False
    rank_100_key, rank_100_cap, _, rank_100_selected_code = rank_100
    rank_101_key, rank_101_cap, _, _ = rank_101
    member_issuer_keys = {str(item.get("issuer_key") or "") for item in items}
    if (
        rank_100_key != str(items[-1].get("issuer_key") or "")
        or rank_100_cap != _decimal(items[-1].get("market_cap"))
        or rank_100_selected_code != str(items[-1].get("code") or "")
        or rank_101_key in member_issuer_keys
        or rank_100_key == rank_101_key
        or rank_100_cap < rank_101_cap
    ):
        return False

    tie = boundary.get("tie")
    if (
        not isinstance(tie, dict)
        or set(tie)
        != {
            "applied",
            "market_cap",
            "tie_breaker",
            "issuer_keys",
            "selected_issuer_keys",
            "excluded_issuer_keys",
        }
        or not isinstance(tie.get("applied"), bool)
        or tie.get("tie_breaker") != "sec_cik_ascending"
    ):
        return False
    tie_keys = tie.get("issuer_keys")
    selected_tie_keys = tie.get("selected_issuer_keys")
    excluded_tie_keys = tie.get("excluded_issuer_keys")
    for keys in (tie_keys, selected_tie_keys, excluded_tie_keys):
        if (
            not isinstance(keys, list)
            or any(not _valid_audit_issuer_key(key) for key in keys)
            or keys != sorted(set(keys))
        ):
            return False
    tie_applied = bool(tie["applied"])
    if tie_applied != (rank_100_cap == rank_101_cap):
        return False
    if tie_applied:
        tie_cap_value = tie.get("market_cap")
        expected_selected = sorted(set(tie_keys) & member_issuer_keys)
        expected_excluded = sorted(set(tie_keys) - member_issuer_keys)
        selected_count = len(selected_tie_keys)
        member_caps_by_issuer = {
            str(item.get("issuer_key") or ""): _decimal(item.get("market_cap"))
            for item in items
        }
        if (
            not isinstance(tie_cap_value, str)
            or _decimal(tie_cap_value) != rank_100_cap
            or tie_cap_value != _decimal_text(tie_cap_value)
            or rank_100_key not in tie_keys
            or rank_101_key not in tie_keys
            or selected_tie_keys != expected_selected
            or excluded_tie_keys != expected_excluded
            or not selected_tie_keys
            or not excluded_tie_keys
            or selected_tie_keys != tie_keys[:selected_count]
            or excluded_tie_keys != tie_keys[selected_count:]
            or rank_100_key != selected_tie_keys[-1]
            or rank_101_key != excluded_tie_keys[0]
            or any(
                member_caps_by_issuer.get(issuer_key) != rank_100_cap
                for issuer_key in selected_tie_keys
            )
        ):
            return False
    elif (
        tie.get("market_cap") is not None
        or tie_keys != []
        or selected_tie_keys != []
        or excluded_tie_keys != []
    ):
        return False
    return True


def _snapshot_payload_is_valid(
    payload: object,
    *,
    snapshot_id: Optional[str] = None,
    require_source_evidence: bool = True,
) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("status") != "ready" or payload.get("data_state") != "ready":
        return False
    if payload.get("universe_version") != US_SIGNAL_UNIVERSE_VERSION:
        return False
    universe_date = _parse_snapshot_date(payload.get("universe_as_of"))
    if universe_date is None:
        return False
    if snapshot_id is not None and snapshot_id != (
        f"{US_SIGNAL_UNIVERSE_VERSION}:{universe_date.isoformat()}"
    ):
        return False

    items = payload.get("items")
    universe_count = payload.get("universe_count")
    source_candidate_count = payload.get("source_candidate_count")
    validated_quote_count = payload.get("validated_quote_count")
    if require_source_evidence and (
        payload.get("new_entries_allowed") is not True
        or not isinstance(source_candidate_count, int)
        or isinstance(source_candidate_count, bool)
        or source_candidate_count < US_SIGNAL_UNIVERSE_LIMIT + 1
        or not isinstance(validated_quote_count, int)
        or isinstance(validated_quote_count, bool)
        or validated_quote_count < US_SIGNAL_UNIVERSE_LIMIT
    ):
        return False
    if require_source_evidence:
        try:
            from app.services.us_market_calendar import (
                US_SIGNAL_PUBLICATION_GRACE,
                us_market_session,
            )

            generated_at = _parse_snapshot_datetime(payload.get("generated_at"))
            session = us_market_session(universe_date)
            if (
                generated_at is None
                or session is None
                or generated_at
                < session.close_at.astimezone(timezone.utc)
                + US_SIGNAL_PUBLICATION_GRACE
            ):
                return False
        except Exception:
            return False
    if (
        not isinstance(universe_count, int)
        or isinstance(universe_count, bool)
        or universe_count != US_SIGNAL_UNIVERSE_LIMIT
        or not isinstance(items, list)
        or len(items) != US_SIGNAL_UNIVERSE_LIMIT
    ):
        return False

    codes: set[str] = set()
    issuers: set[str] = set()
    previous_market_cap: Optional[Decimal] = None
    for expected_rank, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            return False
        rank = item.get("market_cap_rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank != expected_rank:
            return False
        raw_code = item.get("code")
        raw_issuer_key = item.get("issuer_key")
        raw_cik = item.get("cik")
        if not isinstance(raw_code, str) or not isinstance(raw_issuer_key, str):
            return False
        code = raw_code.strip()
        issuer_key = raw_issuer_key.strip()
        cik = str(raw_cik or "").strip()
        market_cap = _decimal(item.get("market_cap"))
        if (
            not code
            or code != raw_code
            or code != _ticker(code)
            or code in codes
            or not issuer_key
            or issuer_key != raw_issuer_key
            or issuer_key in issuers
            or not issuer_key.startswith("cik:")
            or not cik
            or len(cik) != 10
            or not cik.isdigit()
            or issuer_key != f"cik:{cik}"
            or market_cap is None
            or market_cap <= 0
            or (previous_market_cap is not None and market_cap > previous_market_cap)
            or item.get("market") not in {"NASDAQ", "NYSE"}
            or str(item.get("exchange") or "").upper() not in VALID_YAHOO_EXCHANGES
            or item.get("currency") != "USD"
            or not str(item.get("sector") or "").strip()
            or _parse_snapshot_date(item.get("screen_as_of")) != universe_date
            or _parse_snapshot_date(item.get("quote_date")) != universe_date
        ):
            return False
        codes.add(code)
        issuers.add(issuer_key)
        previous_market_cap = market_cap

    if require_source_evidence and not _source_audit_is_valid(
        payload,
        items,
        source_candidate_count=source_candidate_count,
        validated_quote_count=validated_quote_count,
    ):
        return False

    try:
        expected_checksum = _snapshot_checksum(items)
    except (KeyError, TypeError, ValueError):
        return False
    checksum = str(payload.get("checksum") or "")
    return len(checksum) == 64 and hmac.compare_digest(checksum, expected_checksum)


def _serialize_payload(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: (
            value.isoformat() if isinstance(value, (date, datetime)) else str(value)
        ),
    )


def _snapshot_checksum(items: list[dict[str, Any]]) -> str:
    # Hash every stored member field because sector, exchange, quote date, and
    # identifiers are all decision or validation inputs downstream.
    return hashlib.sha256(
        json.dumps(
            items,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda value: (
                value.isoformat() if isinstance(value, (date, datetime)) else str(value)
            ),
        ).encode("utf-8")
    ).hexdigest()


def _decode_valid_snapshot(snapshot: MarketRankingSnapshot) -> Optional[dict[str, Any]]:
    if snapshot.category != US_SIGNAL_UNIVERSE_CATEGORY:
        return None
    try:
        payload = json.loads(snapshot.payload)
    except (TypeError, ValueError):
        return None
    if not _snapshot_payload_is_valid(payload, snapshot_id=snapshot.snapshot_id):
        return None
    return payload


def _persist_snapshot(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    trade_date_value = _parse_snapshot_date(payload.get("universe_as_of"))
    if trade_date_value is None:
        raise ValueError("US universe snapshot date is invalid")
    trade_date = trade_date_value.isoformat()
    snapshot_id = f"{US_SIGNAL_UNIVERSE_VERSION}:{trade_date}"
    if not _snapshot_payload_is_valid(payload, snapshot_id=snapshot_id):
        raise ValueError("US universe snapshot is incomplete")
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None)
    snapshot = db.get(MarketRankingSnapshot, snapshot_id)
    serialized = _serialize_payload(payload)
    if snapshot is None:
        snapshot = MarketRankingSnapshot(
            snapshot_id=snapshot_id,
            category=US_SIGNAL_UNIVERSE_CATEGORY,
            payload=serialized,
            captured_at=captured_at,
            expires_at=captured_at + timedelta(days=400),
        )
        db.add(snapshot)
    else:
        existing = _decode_valid_snapshot(snapshot)
        if existing is not None:
            if (
                existing["checksum"] != payload["checksum"]
                or existing["audit_checksum"] != payload["audit_checksum"]
            ):
                raise ValueError("US universe daily snapshot is immutable")
            return existing
        # A current-version daily identity is immutable even when its stored
        # payload is malformed. Repairing it in place would erase evidence of
        # corruption and make an already published boundary unauditable. A
        # migration must use a new versioned snapshot identity instead.
        raise ValueError("Existing US universe daily snapshot is invalid and immutable")
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return payload


def load_latest_us_signal_universe_snapshot(db: Session) -> Optional[dict[str, Any]]:
    snapshots = db.scalars(
        select(MarketRankingSnapshot)
        .where(MarketRankingSnapshot.category == US_SIGNAL_UNIVERSE_CATEGORY)
        .order_by(
            desc(MarketRankingSnapshot.captured_at),
            desc(MarketRankingSnapshot.snapshot_id),
        )
    )
    for snapshot in snapshots:
        payload = _decode_valid_snapshot(snapshot)
        if payload is not None:
            return payload
    return None


def load_us_signal_universe_snapshot_for_date(
    db: Session,
    universe_date: date,
) -> Optional[dict[str, Any]]:
    """Load the immutable complete universe for one official session date."""

    snapshot_id = f"{US_SIGNAL_UNIVERSE_VERSION}:{universe_date.isoformat()}"
    snapshot = db.get(MarketRankingSnapshot, snapshot_id)
    if snapshot is None:
        return None
    return _decode_valid_snapshot(snapshot)


def build_us_signal_universe(
    *,
    db: Optional[Session] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    from app.services import us_market

    generated_at = now or datetime.now(timezone.utc)
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    else:
        generated_at = generated_at.astimezone(timezone.utc)
    try:
        from app.services.us_market_calendar import us_signal_session_state

        session_state = us_signal_session_state(generated_at)
        completed_date = session_state["latest_completed_date"]
        if generated_at < session_state["refresh_after"]:
            raise ValueError(
                "US completed session is still inside provider publication grace"
            )
        if db is not None:
            exact_snapshot = load_us_signal_universe_snapshot_for_date(
                db,
                completed_date,
            )
            if exact_snapshot is not None:
                # The completed-session ranking is deliberately immutable.
                # Reusing it prevents a later provider-field revision from
                # turning a valid same-day retry into a permanent mismatch.
                return exact_snapshot
        screen_audit: dict[str, Any] = {}
        candidates = _screen_candidates(refresh=True, audit_out=screen_audit)
        if not screen_audit:
            # Deterministic injected loaders used by offline jobs/tests may not
            # expose transport metadata. Their normalized candidate dataset is
            # still recorded without persisting any raw provider payload.
            screen_audit = _screen_source_audit(candidates)
        quotes = us_market.fetch_us_quote_batch(
            [str(item["code"]) for item in candidates],
            refresh=True,
        )
        candidates, source_alignment, ranking_authority = (
            _align_candidates_to_completed_session(
                candidates,
                quotes,
                completed_date,
            )
        )
        cik_by_code = us_market._sec_ticker_map()
        if not cik_by_code:
            raise ValueError("SEC CIK issuer map is empty")
        boundary_evidence: dict[str, Any] = {}
        members, target_date = _validated_members(
            candidates,
            quotes,
            cik_by_code,
            ranking_authority=ranking_authority,
            boundary_evidence_out=boundary_evidence,
        )
        if (
            len(members) != US_SIGNAL_UNIVERSE_LIMIT
            or target_date is None
            or target_date != completed_date
        ):
            raise ValueError(
                "US top-100 source is incomplete or not aligned to the latest completed session"
            )
        ranked = [
            {**item, "market_cap_rank": rank}
            for rank, item in enumerate(members, start=1)
        ]
        source_audit = {
            "version": US_SIGNAL_UNIVERSE_AUDIT_VERSION,
            "trust_model": "trusted_database_integrity_checksum_not_external_signature",
            "screen": screen_audit,
            "alignment": source_alignment,
            "quotes": _quote_source_audit(candidates, quotes),
            "sec_identities": _sec_identity_source_audit(candidates, cik_by_code),
        }
        member_checksum = _snapshot_checksum(ranked)
        payload = {
            "status": "ready",
            "data_state": "ready",
            "universe_version": US_SIGNAL_UNIVERSE_VERSION,
            "universe_as_of": target_date,
            "universe_count": len(ranked),
            "source_candidate_count": len(candidates),
            "validated_quote_count": len(quotes),
            "checksum": member_checksum,
            "source_audit": source_audit,
            "boundary_evidence": boundary_evidence,
            "audit_checksum": _snapshot_audit_checksum(
                source_audit,
                boundary_evidence,
                member_checksum=member_checksum,
                universe_version=US_SIGNAL_UNIVERSE_VERSION,
                universe_as_of=target_date,
            ),
            "generated_at": generated_at,
            "source": "Nasdaq NYSE/Nasdaq market-cap ranking with audited latest-session Yahoo bridge + SEC CIK",
            "new_entries_allowed": True,
            "items": ranked,
        }
        if db is not None:
            payload = _persist_snapshot(db, payload)
        return payload
    except Exception as exc:
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
        previous = (
            load_latest_us_signal_universe_snapshot(db) if db is not None else None
        )
        if previous:
            return {
                **previous,
                "status": "degraded",
                "data_state": "stale",
                "generated_at": generated_at,
                "source_error": str(exc),
                "new_entries_allowed": False,
            }
        return {
            "status": "unavailable",
            "data_state": "unavailable",
            "universe_version": US_SIGNAL_UNIVERSE_VERSION,
            "universe_as_of": None,
            "universe_count": 0,
            "generated_at": generated_at,
            "source_error": str(exc),
            "new_entries_allowed": False,
            "items": [],
        }
