from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from math import ceil
from typing import Any, Callable, Optional

import requests
from bs4 import BeautifulSoup

from app.services.ttl_cache import TTLCache


FNGUIDE_ETF_URL = "https://navercomp.wisereport.co.kr/v2/ETF/index.aspx"
NAVER_ETF_SOURCE_URL = "https://finance.naver.com/item/main.naver?code={code}"
NAVER_STOCK_INTEGRATION_URL = "https://m.stock.naver.com/api/stock/{code}/integration"
NAVER_ETF_DIVIDEND_SUMMARY_URL = (
    "https://stock.naver.com/api/domestic/detail/{code}/ETFDividend"
)
NAVER_ETF_DIVIDEND_HISTORY_URL = (
    "https://stock.naver.com/api/domestic/detail/{code}/ETFDividendHist"
)
NAVER_ETF_DIVIDEND_SOURCE_URL = (
    "https://m.stock.naver.com/domestic/stock/{code}/total"
)
NAVER_ETF_COMPONENT_URL = (
    "https://stock.naver.com/api/domestic/detail/{code}/ETFComponent"
)
NAVER_ETF_UNIVERSE_URL = (
    "https://stock.naver.com/api/stockSecurity/etfs/v2/domestic"
)
ETF_HOLDINGS_SNAPSHOT_KEY = "etf_holdings_universe:v1"
ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION = 1
TIGER_DISTRIBUTION_URL = "https://investments.miraeasset.com/tigeretf/ko/product/search/detail/refDivAjax.ajax"
TIGER_PRODUCT_URL = "https://investments.miraeasset.com/tigeretf/ko/product/search/detail/index.do?ksdFund={isin}"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
}

# Domestic ETF names are conventionally prefixed by the manager's brand.  This
# lets normal companies avoid an unnecessary ETF lookup while still supporting
# current and legacy fund brands in the local universe.
ETF_NAME_PREFIXES = (
    "1Q",
    "ACE",
    "ARIRANG",
    "BNK",
    "DAISHIN",
    "DS",
    "FOCUS",
    "HANARO",
    "HEROES",
    "HK",
    "IBK",
    "KCGI",
    "KBSTAR",
    "KINDEX",
    "KIWOOM",
    "KOACT",
    "KODEX",
    "KOSEF",
    "MIGHTY",
    "MIDAS",
    "PLUS",
    "RISE",
    "SOL",
    "TIGER",
    "TIME",
    "TIMEFOLIO",
    "TREX",
    "TRUSTON",
    "UNICORN",
    "WON",
    "WOORI",
    "더제이",
    "마이다스",
    "마이티",
    "아이엠에셋",
    "에셋플러스",
    "파워",
    "히어로즈",
)

_PROFILE_CACHE = TTLCache(maxsize=1024)


def is_likely_etf_name(name: Optional[str]) -> bool:
    normalized = re.sub(r"\s+", " ", str(name or "")).strip().upper()
    if not normalized:
        return False
    return "ETF" in normalized.replace(" ", "") or any(
        normalized == prefix or normalized.startswith(f"{prefix} ")
        for prefix in ETF_NAME_PREFIXES
    )


def korean_security_isin(code: str) -> str:
    """Build the standard Korean security ISIN and ISO-6166 check digit."""

    normalized = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise ValueError("A six-digit Korean security code is required")
    base = f"KR7{normalized}00"
    expanded = "".join(str(ord(char) - 55) if char.isalpha() else char for char in base)
    checksum_total = 0
    for index, char in enumerate(reversed(f"{expanded}0")):
        value = int(char) * (2 if index % 2 else 1)
        checksum_total += (value // 10) + (value % 10)
    return f"{base}{(10 - checksum_total % 10) % 10}"


def _extract_javascript_object(html: str, variable_name: str) -> dict[str, Any]:
    match = re.search(
        rf"\bvar\s+{re.escape(variable_name)}\s*=\s*(\{{.*?\}})\s*;",
        html,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    try:
        payload = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def parse_fnguide_etf_profile(html: str) -> dict[str, Any]:
    summary = _extract_javascript_object(html, "summary_data")
    product = _extract_javascript_object(html, "product_summary_data")
    composition = _extract_javascript_object(html, "CU_data")
    raw_holdings = composition.get("grid_data") if isinstance(composition, dict) else []
    holdings: list[dict[str, Any]] = []
    if isinstance(raw_holdings, list):
        for row in raw_holdings:
            if not isinstance(row, dict):
                continue
            name = str(row.get("STK_NM_KOR") or "").strip()
            weight = _decimal(row.get("ETF_WEIGHT"))
            if not name or weight is None or weight < 0:
                continue
            holdings.append(
                {
                    "name": name,
                    "code": None,
                    "weight": weight,
                    "shares": _decimal(row.get("AGMT_STK_CNT")),
                }
            )
    holdings.sort(key=lambda item: item["weight"], reverse=True)
    holding_date = next(
        (
            _date(row.get("TRD_DT"))
            for row in raw_holdings or []
            if isinstance(row, dict) and _date(row.get("TRD_DT")) is not None
        ),
        None,
    )
    code = str(summary.get("CMP_CD") or "").strip()
    name = str(summary.get("CMP_KOR") or "").strip()
    is_etf = bool(code and name and (holdings or summary.get("CMP_TYP") == "5"))
    return {
        "is_etf": is_etf,
        "code": code,
        "name": name,
        "as_of": holding_date,
        "benchmark": str(
            product.get("BASE_IDX_NM_KOR") or summary.get("BASE_IDX_NM_KOR") or ""
        ).strip()
        or None,
        "issuer": str(
            product.get("ISSUE_NM_KOR") or summary.get("ISSUE_NM_KOR") or ""
        ).strip()
        or None,
        "category": str(summary.get("ETF_TYP_SVC_NM") or "").strip() or None,
        "total_fee": _decimal(product.get("TOT_PAY") or summary.get("TOT_PAY")),
        "distribution_schedule": str(product.get("DIV_BASE_DT") or "").strip() or None,
        "holdings": holdings[:10],
    }


def parse_tiger_distribution_history(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict[str, Any]] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(cells) < 3:
            continue
        record_date = _date(cells[0])
        payment_date = _date(cells[1])
        amount = _decimal(cells[2])
        if record_date is None or amount is None:
            continue
        items.append(
            {
                "record_date": record_date,
                "payment_date": payment_date,
                "amount_per_share": amount,
                "date_type": "record_date",
            }
        )
    items.sort(key=lambda item: item["record_date"], reverse=True)
    return items


def parse_naver_etf_dividend_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    code = str(payload.get("itemCode") or "").strip()
    if not code:
        return {}
    return {
        "reference_date": _date(payload.get("referenceDate")),
        "trailing_distribution_yield": _decimal(payload.get("dividendYieldTtm")),
        "trailing_distribution_amount": _decimal(payload.get("dividendPerShareTtm")),
    }


def parse_naver_etf_holdings(payload: Any) -> dict[str, Any]:
    raw_items = payload if isinstance(payload, list) else []
    holdings: list[dict[str, Any]] = []
    holding_dates: list[date] = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        name = str(row.get("componentName") or "").strip()
        weight = _decimal(row.get("weight"))
        if not name or weight is None or weight <= 0:
            continue
        holding_date = _date(row.get("referenceDate"))
        if holding_date is not None:
            holding_dates.append(holding_date)
        code = str(
            row.get("componentItemCode")
            or row.get("componentReutersCode")
            or row.get("componentIsinCode")
            or ""
        ).strip()
        holdings.append(
            {
                "name": name,
                "code": code or None,
                "weight": weight,
                "shares": _decimal(row.get("cuUnitQuantity")),
            }
        )
    holdings.sort(key=lambda item: item["weight"], reverse=True)
    return {
        "as_of": max(holding_dates) if holding_dates else None,
        "holdings": holdings[:10],
    }


def parse_naver_etf_distribution_history(payload: Any) -> list[dict[str, Any]]:
    raw_items = payload if isinstance(payload, list) else []
    items: list[dict[str, Any]] = []
    seen: set[tuple[date, Decimal]] = set()
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        row_id = row.get("id") if isinstance(row.get("id"), dict) else {}
        ex_dividend_date = _date(row_id.get("exDividendAt"))
        amount = _decimal(row.get("dividendAmount"))
        if ex_dividend_date is None or amount is None or amount < 0:
            continue
        key = (ex_dividend_date, amount)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                # The shared Naver endpoint publishes the ex-dividend date, not
                # the manager's record/payment date.  Keep the normalized date
                # field for sorting and expose its meaning separately so the UI
                # can label it accurately.
                "record_date": ex_dividend_date,
                "payment_date": None,
                "amount_per_share": amount,
                "date_type": "ex_dividend_date",
            }
        )
    items.sort(key=lambda item: item["record_date"], reverse=True)
    return items


def _fetch_fnguide_profile(
    code: str,
    *,
    get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    response = get(
        FNGUIDE_ETF_URL,
        params={"cmp_cd": code},
        headers=REQUEST_HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    return parse_fnguide_etf_profile(response.text)


def _fetch_naver_trailing_distribution_yield(
    code: str,
    *,
    get: Callable[..., Any] = requests.get,
) -> Optional[Decimal]:
    response = get(
        NAVER_STOCK_INTEGRATION_URL.format(code=code),
        headers=REQUEST_HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    indicator = payload.get("etfKeyIndicator") if isinstance(payload, dict) else None
    if not isinstance(indicator, dict):
        return None
    return _decimal(indicator.get("dividendYieldTtm"))


def _fetch_naver_etf_dividend_summary(
    code: str,
    *,
    get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    response = get(
        NAVER_ETF_DIVIDEND_SUMMARY_URL.format(code=code),
        headers={**REQUEST_HEADERS, "Referer": NAVER_ETF_DIVIDEND_SOURCE_URL.format(code=code)},
        timeout=8,
    )
    response.raise_for_status()
    return parse_naver_etf_dividend_summary(response.json())


def _fetch_naver_etf_holdings(
    code: str,
    *,
    get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    response = get(
        NAVER_ETF_COMPONENT_URL.format(code=code),
        params={"startIdx": 0, "pageSize": 20},
        headers={
            **REQUEST_HEADERS,
            "Referer": NAVER_ETF_DIVIDEND_SOURCE_URL.format(code=code),
        },
        timeout=8,
    )
    response.raise_for_status()
    return parse_naver_etf_holdings(response.json())


def fetch_naver_etf_universe(
    *,
    get: Callable[..., Any] = requests.get,
    page_size: int = 100,
) -> list[dict[str, str]]:
    size = max(1, min(int(page_size), 100))
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for index in range(20):
        response = get(
            NAVER_ETF_UNIVERSE_URL,
            params={
                "listingType": "tradingValueDesc",
                "size": size,
                "index": index,
            },
            headers=REQUEST_HEADERS,
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("ETF universe response must be an object")
        rows = payload.get("items") if isinstance(payload.get("items"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("itemCode") or "").strip().upper()
            name = str(row.get("itemName") or "").strip()
            if not re.fullmatch(r"[0-9A-Z]{6}", code) or not name or code in seen:
                continue
            seen.add(code)
            items.append({"code": code, "name": name})
        if not payload.get("hasNext"):
            break
    if not items:
        raise ValueError("ETF universe is empty")
    return items


def _holding_names_signature(item: Any) -> tuple[str, ...]:
    holdings = item.get("holdings") if isinstance(item, dict) else []
    return tuple(
        str(holding.get("code") or holding.get("name") or "").strip()
        for holding in holdings or []
        if isinstance(holding, dict)
        and str(holding.get("code") or holding.get("name") or "").strip()
    )


def build_naver_etf_holdings_snapshot(
    previous: Optional[dict[str, Any]] = None,
    *,
    get: Callable[..., Any] = requests.get,
    max_workers: int = 8,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    universe = fetch_naver_etf_universe(get=get)
    previous_items = (
        previous.get("items")
        if isinstance(previous, dict) and isinstance(previous.get("items"), dict)
        else {}
    )
    items: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    fresh_count = 0

    def fetch_one(row: dict[str, str]) -> tuple[str, dict[str, Any]]:
        code = row["code"]
        last_error: Optional[Exception] = None
        for _attempt in range(2):
            try:
                parsed = _fetch_naver_etf_holdings(code, get=get)
                if not parsed.get("holdings"):
                    raise ValueError(f"ETF holdings are empty: {code}")
                return code, {
                    "code": code,
                    "name": row["name"],
                    "as_of": parsed.get("as_of"),
                    "holdings": parsed.get("holdings") or [],
                    "source_label": "네이버페이 증권 ETF",
                    "source_url": NAVER_ETF_DIVIDEND_SOURCE_URL.format(code=code),
                    "stale": False,
                }
            except (requests.RequestException, ValueError, TypeError) as exc:
                last_error = exc
        raise last_error or RuntimeError(f"ETF holdings unavailable: {code}")

    worker_count = max(1, min(int(max_workers), 24, len(universe)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(fetch_one, row): row for row in universe}
        for future in as_completed(futures):
            row = futures[future]
            code = row["code"]
            try:
                resolved_code, item = future.result()
                items[resolved_code] = item
                fresh_count += 1
            except Exception as exc:
                failures[code] = str(exc)[:300]
                old_item = previous_items.get(code)
                if isinstance(old_item, dict):
                    items[code] = {**old_item, "name": row["name"], "stale": True}

    current_codes = {row["code"] for row in universe}
    previous_codes = set(previous_items)
    changed_codes = sorted(
        code
        for code in current_codes & previous_codes
        if code in items
        and _holding_names_signature(items[code])
        != _holding_names_signature(previous_items[code])
    )
    added_codes = sorted(current_codes - previous_codes)
    removed_codes = sorted(previous_codes - current_codes)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    as_of_values = [
        str(item.get("as_of") or "")
        for item in items.values()
        if str(item.get("as_of") or "")
    ]
    total_count = len(universe)
    return {
        "generated_at": current.isoformat(),
        "source_label": "네이버페이 증권 ETF",
        "reference_date": max(as_of_values) if as_of_values else None,
        "total_count": total_count,
        "loaded_count": len(items),
        "fresh_count": fresh_count,
        "fresh_coverage": fresh_count / total_count if total_count else 0,
        "changed_count": len(changed_codes),
        "changed_codes": changed_codes,
        "added_codes": added_codes,
        "removed_codes": removed_codes,
        "failed_codes": sorted(failures),
        "failures": failures,
        "items": items,
    }


def validate_etf_holdings_snapshot(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("ETF holdings snapshot must be an object")
    items = payload.get("items")
    total_count = int(payload.get("total_count") or 0)
    fresh_count = int(payload.get("fresh_count") or 0)
    if total_count <= 0 or not isinstance(items, dict):
        raise ValueError("ETF holdings snapshot has no universe")
    minimum = max(1, ceil(total_count * 0.95))
    if fresh_count < minimum or len(items) < minimum:
        raise ValueError(
            f"ETF holdings snapshot coverage is incomplete: {fresh_count}/{total_count}"
        )
    return payload


def _fetch_naver_etf_distribution_history(
    code: str,
    *,
    get: Callable[..., Any] = requests.get,
) -> list[dict[str, Any]]:
    response = get(
        NAVER_ETF_DIVIDEND_HISTORY_URL.format(code=code),
        params={"startIdx": 0, "pageSize": 100},
        headers={**REQUEST_HEADERS, "Referer": NAVER_ETF_DIVIDEND_SOURCE_URL.format(code=code)},
        timeout=8,
    )
    response.raise_for_status()
    return parse_naver_etf_distribution_history(response.json())


def _fetch_tiger_distributions(
    code: str,
    name: str,
    isin: Optional[str],
    *,
    post: Callable[..., Any] = requests.post,
) -> tuple[list[dict[str, Any]], str]:
    resolved_isin = str(isin or "").strip() or korean_security_isin(code)
    response = post(
        TIGER_DISTRIBUTION_URL,
        data={
            "pageIndex": 1,
            "firstIndex": 0,
            "listCnt": 100,
            "ksdFund": resolved_isin,
            "jongName": name,
        },
        headers={
            **REQUEST_HEADERS,
            "Referer": TIGER_PRODUCT_URL.format(isin=resolved_isin),
        },
        timeout=8,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    return parse_tiger_distribution_history(response.text), resolved_isin


def _empty_profile(
    code: str, name: str, *, is_etf: bool, message: Optional[str] = None
) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "is_etf": is_etf,
        "as_of": None,
        "benchmark": None,
        "issuer": None,
        "category": None,
        "total_fee": None,
        "trailing_distribution_yield": None,
        "trailing_distribution_amount": None,
        "distribution_schedule": None,
        "holdings": [],
        "distributions": [],
        "source_label": "FnGuide ETF",
        "source_url": NAVER_ETF_SOURCE_URL.format(code=code),
        "distribution_source_label": None,
        "distribution_source_url": None,
        "message": message,
    }


def _build_etf_profile_uncached(
    code: str,
    name: str,
    isin: Optional[str],
    *,
    holdings_snapshot: Optional[dict[str, Any]] = None,
    get: Callable[..., Any] = requests.get,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    likely_etf = is_likely_etf_name(name)
    if not likely_etf:
        return _empty_profile(code, name, is_etf=False)

    payload = _empty_profile(code, name, is_etf=True)
    try:
        parsed = _fetch_fnguide_profile(code, get=get)
    except (requests.RequestException, ValueError, TypeError):
        payload["message"] = "ETF 구성자산을 일시적으로 불러오지 못했습니다."
        parsed = {}
    if parsed.get("is_etf"):
        payload.update(parsed)
        payload["code"] = code
        payload["name"] = str(parsed.get("name") or name)
        payload["source_label"] = "FnGuide ETF"
        payload["source_url"] = NAVER_ETF_SOURCE_URL.format(code=code)
        payload["message"] = None

    scheduled_holdings = (
        holdings_snapshot.get("holdings")
        if isinstance(holdings_snapshot, dict)
        and isinstance(holdings_snapshot.get("holdings"), list)
        else []
    )
    if scheduled_holdings:
        naver_holdings = {
            "as_of": _date(holdings_snapshot.get("as_of")),
            "holdings": scheduled_holdings,
        }
    else:
        try:
            naver_holdings = _fetch_naver_etf_holdings(code, get=get)
        except (requests.RequestException, ValueError, TypeError):
            naver_holdings = {}
    if naver_holdings.get("holdings"):
        payload["holdings"] = naver_holdings["holdings"][:10]
        payload["as_of"] = naver_holdings.get("as_of") or payload.get("as_of")
        payload["source_label"] = "네이버페이 증권 ETF"
        payload["source_url"] = NAVER_ETF_DIVIDEND_SOURCE_URL.format(code=code)
        payload["message"] = None

    try:
        dividend_summary = _fetch_naver_etf_dividend_summary(code, get=get)
    except (requests.RequestException, ValueError, TypeError):
        dividend_summary = {}
    if dividend_summary:
        payload["trailing_distribution_yield"] = dividend_summary.get(
            "trailing_distribution_yield"
        )
        payload["trailing_distribution_amount"] = dividend_summary.get(
            "trailing_distribution_amount"
        )
    else:
        try:
            payload["trailing_distribution_yield"] = (
                _fetch_naver_trailing_distribution_yield(
                    code,
                    get=get,
                )
            )
        except (requests.RequestException, ValueError, TypeError):
            pass

    try:
        payload["distributions"] = _fetch_naver_etf_distribution_history(
            code,
            get=get,
        )
        payload["distribution_source_label"] = "네이버페이 증권 ETF"
        payload["distribution_source_url"] = NAVER_ETF_DIVIDEND_SOURCE_URL.format(
            code=code
        )
    except (requests.RequestException, ValueError, TypeError):
        pass

    if str(payload.get("name") or name).replace(" ", "").upper().startswith("TIGER"):
        try:
            distributions, resolved_isin = _fetch_tiger_distributions(
                code,
                str(payload.get("name") or name),
                isin,
                post=post,
            )
        except (requests.RequestException, ValueError, TypeError):
            distributions = []
            resolved_isin = str(isin or "").strip()
        if distributions:
            payload["distributions"] = distributions
        if resolved_isin and distributions:
            payload["distribution_source_label"] = "TIGER ETF 공식"
            payload["distribution_source_url"] = TIGER_PRODUCT_URL.format(
                isin=resolved_isin
            )

    return payload


def build_etf_profile(
    code: str,
    name: str,
    isin: Optional[str] = None,
    *,
    holdings_snapshot: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    normalized_code = str(code or "").strip()
    normalized_name = str(name or normalized_code).strip()
    holdings_marker = tuple(
        (
            str(item.get("code") or ""),
            str(item.get("name") or ""),
            str(item.get("weight") or ""),
            str(item.get("shares") or ""),
        )
        for item in (
            holdings_snapshot.get("holdings", [])
            if isinstance(holdings_snapshot, dict)
            else []
        )
        if isinstance(item, dict)
    )
    cache_key = (
        normalized_code,
        normalized_name,
        str(isin or "").strip(),
        str(holdings_snapshot.get("as_of") or "")
        if isinstance(holdings_snapshot, dict)
        else "",
        holdings_marker,
    )
    return _PROFILE_CACHE.get_or_set(
        cache_key,
        30 * 60,
        lambda: _build_etf_profile_uncached(
            normalized_code,
            normalized_name,
            isin,
            holdings_snapshot=holdings_snapshot,
        ),
    )
