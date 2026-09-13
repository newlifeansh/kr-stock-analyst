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


US_SIGNAL_UNIVERSE_VERSION = "us-market-cap-top100-v1"
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


def _fetch_exchange_screen(exchange: str, *, refresh: bool = False) -> list[dict[str, Any]]:
    def load() -> list[dict[str, Any]]:
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
                raise ValueError(f"Nasdaq {exchange} screener as-of date is unavailable")
            if expected_as_of is None:
                expected_as_of = page_as_of
            elif page_as_of != expected_as_of:
                raise ValueError(f"Nasdaq {exchange} screener as-of changed during pagination")
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
                raise ValueError(f"Nasdaq {exchange} screener total changed during pagination")
            if not page:
                raise ValueError(f"Nasdaq {exchange} screener page is incomplete")
            rows.extend({**item, "_screen_as_of": page_as_of} for item in page)
            offset += len(page)
            if len(page) > page_limit or len(rows) > expected_total:
                raise ValueError(f"Nasdaq {exchange} screener pagination is inconsistent")
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
        detail_by_code = {_ticker(item.get("symbol")): item for item in detail_rows}
        eligible_detail_codes = {
            code
            for code, item in detail_by_code.items()
            if _screen_row_allowed(item)
        }
        missing_detail_codes = set(eligible_ranked_by_code) - set(detail_by_code)
        unexpected_detail_codes = eligible_detail_codes - set(ranked_by_code)
        if missing_detail_codes or unexpected_detail_codes:
            raise ValueError(
                f"Nasdaq {exchange} eligible ranking and classification sets differ"
            )
        return [
            {
                **detail_by_code[code],
                **eligible_ranked_by_code[code],
            }
            for code in eligible_ranked_by_code
        ]

    if refresh:
        loaded = load()
        US_SIGNAL_UNIVERSE_SOURCE_CACHE.set(
            ("exchange_screen", exchange),
            loaded,
            US_SIGNAL_UNIVERSE_SOURCE_TTL_SECONDS,
        )
        return loaded
    return US_SIGNAL_UNIVERSE_SOURCE_CACHE.get_or_set(
        ("exchange_screen", exchange),
        US_SIGNAL_UNIVERSE_SOURCE_TTL_SECONDS,
        load,
    )


def _screen_row_allowed(row: dict[str, Any]) -> bool:
    symbol = _ticker(row.get("symbol"))
    name = str(row.get("name") or "").strip()
    market_cap = _decimal(row.get("marketCap"))
    if not symbol or not name or market_cap is None or market_cap <= 0:
        return False
    if any(pattern.search(name) for pattern in EXCLUDED_NAME_PATTERNS):
        return False
    return not bool(re.search(r"(?:\+|=|\^)", symbol))


def _screen_candidates(*, refresh: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for exchange in SIGNAL_EXCHANGES:
        for raw in _fetch_exchange_screen(exchange, refresh=refresh):
            if not _screen_row_allowed(raw):
                continue
            rows.append(
                {
                    "code": _ticker(raw.get("symbol")),
                    "name": str(raw.get("name") or raw.get("symbol") or "").strip(),
                    "screen_exchange": exchange.upper(),
                    "screen_market_cap": _decimal(raw.get("marketCap")),
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
    return list(unique.values())[:600]


def _quote_date(value: object) -> Optional[date]:
    try:
        from app.services.us_market import NEW_YORK_TZ

        return datetime.fromtimestamp(int(value), timezone.utc).astimezone(NEW_YORK_TZ).date()
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
) -> list[dict[str, Any]]:
    """Freeze the top 100 issuers using Nasdaq screen market cap only.

    Yahoo validates security type, price, market cap presence, and quote date;
    it does not reorder the Nasdaq ranking.  SEC CIK must be complete through
    the 100/101 boundary, including every market-cap tie at that boundary.
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

    eligible = sorted(
        issuers.values(),
        key=lambda item: (
            -Decimal(str(item["screen_market_cap"])),
            str(item["issuer_key"]),
        ),
    )[:US_SIGNAL_UNIVERSE_LIMIT]
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
    return eligible


def _validated_members(
    candidates: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
    cik_by_code: dict[str, str],
) -> tuple[list[dict[str, Any]], Optional[date]]:
    # Freeze the authoritative issuer boundary before consulting Yahoo. A
    # missing quote for issuer #1 must not silently promote issuer #101.
    eligible_issuers = _screen_issuer_boundary(candidates, cik_by_code)

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
                quote.get("longName")
                or quote.get("shortName")
                or candidate["name"]
            )
            if any(pattern.search(name) for pattern in EXCLUDED_NAME_PATTERNS):
                continue
            average_volume = _decimal(quote.get("averageDailyVolume3Month")) or Decimal("0")
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
    return representatives, target_date


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
        if (
            not isinstance(rank, int)
            or isinstance(rank, bool)
            or rank != expected_rank
        ):
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
            or (
                previous_market_cap is not None
                and market_cap > previous_market_cap
            )
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
        default=lambda value: value.isoformat()
        if isinstance(value, (date, datetime))
        else str(value),
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
            default=lambda value: value.isoformat()
            if isinstance(value, (date, datetime))
            else str(value),
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
            if existing["checksum"] != payload["checksum"]:
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
            raise ValueError("US completed session is still inside provider publication grace")
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
        candidates = _screen_candidates(refresh=True)
        quotes = us_market.fetch_us_quote_batch(
            [str(item["code"]) for item in candidates],
            refresh=True,
        )
        cik_by_code = us_market._sec_ticker_map()
        if not cik_by_code:
            raise ValueError("SEC CIK issuer map is empty")
        members, target_date = _validated_members(candidates, quotes, cik_by_code)
        screen_dates = {
            value
            for value in (
                _parse_snapshot_date(item.get("screen_as_of")) for item in candidates
            )
            if value is not None
        }
        screen_date = next(iter(screen_dates)) if len(screen_dates) == 1 else None
        if (
            len(members) != US_SIGNAL_UNIVERSE_LIMIT
            or target_date is None
            or screen_date is None
            or screen_date != target_date
            or target_date != completed_date
        ):
            raise ValueError(
                "US top-100 source is incomplete or not aligned to the latest completed session"
            )
        ranked = [
            {**item, "market_cap_rank": rank}
            for rank, item in enumerate(members, start=1)
        ]
        payload = {
            "status": "ready",
            "data_state": "ready",
            "universe_version": US_SIGNAL_UNIVERSE_VERSION,
            "universe_as_of": target_date,
            "universe_count": len(ranked),
            "source_candidate_count": len(candidates),
            "validated_quote_count": len(quotes),
            "checksum": _snapshot_checksum(ranked),
            "generated_at": generated_at,
            "source": "Nasdaq NYSE/Nasdaq market-cap ranking + Yahoo Finance quote validation + SEC CIK",
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
        previous = load_latest_us_signal_universe_snapshot(db) if db is not None else None
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
