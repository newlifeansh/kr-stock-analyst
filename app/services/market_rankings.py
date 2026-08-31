from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import re
from statistics import mean
from typing import Optional
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, aliased

from app.models import DailyPrice, NewsItem, StockMaster
from app.services.market_calendar import latest_korea_market_session_date
from app.services.sector_taxonomy import investment_sector_fields
from app.services.stock_dashboard import NAVER_CACHE, _keyword_score, _naver_snapshot, _rate, _round_decimal
from app.services.ttl_cache import TTLCache

KST = timezone(timedelta(hours=9))
NAVER_MARKET_RISE_URL = "https://finance.naver.com/sise/sise_rise.naver"
NAVER_CHART_URL = "https://fchart.stock.naver.com/sise.nhn"
NAVER_DOMESTIC_LIST_URL = "https://m.stock.naver.com/front-api/domestic/stock/list"
NAVER_REALTIME_QUOTES_URL = "https://polling.finance.naver.com/api/realtime/domestic/stock"
NAVER_ETF_LIST_URL = "https://finance.naver.com/api/sise/etfItemList.nhn"
NAVER_MARKET_SUM_URL = "https://finance.naver.com/sise/sise_market_sum.naver"
MARKET_RISE_CACHE = TTLCache(maxsize=4)
MARKET_PERIOD_CACHE = TTLCache(maxsize=4096)
MARKET_TOP_CACHE = TTLCache(maxsize=96)
MARKET_RISE_TTL_SECONDS = 60
MARKET_PERIOD_TTL_SECONDS = 60 * 30
MARKET_TOP_TTL_SECONDS = 45
MARKET_FUNDAMENTAL_TTL_SECONDS = 60 * 5


def _now_kst() -> datetime:
    return datetime.now(KST)


def _integer(value: object, *, multiplier: int = 1) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        normalized = str(value).replace(",", "").replace("원", "").strip()
        return int(Decimal(normalized) * multiplier)
    except (ValueError, ArithmeticError):
        return None


def _decimal(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        normalized = (
            str(value)
            .replace(",", "")
            .replace("%", "")
            .replace("배", "")
            .replace("+", "")
            .strip()
        )
        return _round_decimal(Decimal(normalized))
    except (ValueError, ArithmeticError):
        return None


def _market_name(value: object, fallback: str = "KOSPI") -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("code")
    normalized = str(value or fallback).upper()
    return "KOSDAQ" if "KOSDAQ" in normalized else "KOSPI"


def _previous_weekday(target: date) -> date:
    candidate = target
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _latest_ranking_trade_date(db: Optional[Session], now: Optional[datetime] = None) -> date:
    current = now or _now_kst()
    calendar_date = latest_korea_market_session_date(current)
    if calendar_date is not None:
        return calendar_date

    if db is not None:
        stored_dates = db.scalars(
            select(DailyPrice.trade_date)
            .where(DailyPrice.trade_date <= current.date())
            .distinct()
            .order_by(desc(DailyPrice.trade_date))
            .limit(10)
        )
        for stored_date in stored_dates:
            if stored_date.weekday() < 5:
                return stored_date

    return _previous_weekday(current.date())


def _is_regular_session(now: Optional[datetime] = None) -> bool:
    current = now or _now_kst()
    if current.weekday() >= 5:
        return False
    return (current.hour, current.minute) >= (9, 0) and (current.hour, current.minute) <= (15, 30)


def _row_value(row: DailyPrice) -> Optional[int]:
    if row.trading_value is not None:
        return row.trading_value
    if row.close is not None and row.volume is not None:
        return row.close * row.volume
    return None


def _mapping_row_value(row: dict[str, object]) -> Optional[int]:
    if row.get("trading_value") is not None:
        return int(row["trading_value"])
    if row.get("close") is not None and row.get("volume") is not None:
        return int(row["close"]) * int(row["volume"])
    return None


def _parse_naver_market_rise(html: bytes, market: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html.decode("euc-kr", "replace"), "html.parser")
    rows: list[dict[str, object]] = []
    for link in soup.select("table.type_2 a.tltle"):
        match = re.search(r"[?&]code=([0-9A-Z]+)", str(link.get("href") or ""))
        row = link.find_parent("tr")
        cells = row.find_all("td") if row else []
        if not match or len(cells) < 6:
            continue
        try:
            price = int(cells[2].get_text(" ", strip=True).replace(",", ""))
            change_rate = Decimal(
                cells[4].get_text(" ", strip=True).replace(",", "").replace("%", "").replace("+", "")
            )
            volume = int(cells[5].get_text(" ", strip=True).replace(",", ""))
        except (ValueError, ArithmeticError):
            continue
        if price <= 0 or change_rate <= 0:
            continue
        rows.append(
            {
                "code": match.group(1),
                "name": link.get_text(" ", strip=True),
                "market": market,
                "price": price,
                "change_rate": _round_decimal(change_rate),
                "volume": volume,
                "trading_value": price * volume,
            }
        )
    return rows


def _fetch_naver_market_rise(market: str) -> list[dict[str, object]]:
    response = requests.get(
        NAVER_MARKET_RISE_URL,
        params={"sosok": "1" if market == "KOSDAQ" else "0"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=12,
    )
    response.raise_for_status()
    return _parse_naver_market_rise(response.content, market)


def _parse_naver_chart_baselines(payload: bytes) -> dict[str, Optional[int]]:
    xml_text = payload.decode("euc-kr", "replace")
    xml_text = re.sub(r"<\?xml[^>]+\?>", "", xml_text, count=1)
    try:
        root = ElementTree.fromstring(xml_text)
    except (ElementTree.ParseError, ValueError):
        return {"latest": None, "one_week": None, "one_month": None, "three_month": None}
    closes: list[int] = []
    for item in root.findall(".//item"):
        parts = str(item.attrib.get("data") or "").split("|")
        if len(parts) < 5:
            continue
        try:
            close = int(parts[4])
        except ValueError:
            continue
        if close > 0:
            closes.append(close)
    return {
        "latest": closes[-1] if closes else None,
        "one_week": closes[-6] if len(closes) >= 6 else None,
        "one_month": closes[-22] if len(closes) >= 22 else None,
        "three_month": closes[-64] if len(closes) >= 64 else None,
    }


def _fetch_naver_chart_baselines(code: str) -> dict[str, Optional[int]]:
    response = requests.get(
        NAVER_CHART_URL,
        params={"symbol": code, "timeframe": "day", "count": "100", "requestType": "0"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8,
    )
    response.raise_for_status()
    return _parse_naver_chart_baselines(response.content)


def _naver_chart_baselines(code: str) -> dict[str, Optional[int]]:
    return MARKET_PERIOD_CACHE.get_or_set(
        ("naver_chart_baselines", code),
        MARKET_PERIOD_TTL_SECONDS,
        lambda: _fetch_naver_chart_baselines(code),
    )


def build_market_period_returns(codes: list[str]) -> list[dict[str, object]]:
    unique_codes = list(dict.fromkeys(code.strip() for code in codes if re.fullmatch(r"[0-9A-Z]{6}", code.strip())))[:100]
    if not unique_codes:
        return []

    output: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=min(20, len(unique_codes))) as executor:
        futures = {executor.submit(_naver_chart_baselines, code): code for code in unique_codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                baselines = future.result()
            except Exception:
                continue
            latest = baselines.get("latest")
            output.append(
                {
                    "code": code,
                    "one_week_return": _rate(latest, baselines.get("one_week")),
                    "one_month_return": _rate(latest, baselines.get("one_month")),
                    "three_month_return": _rate(latest, baselines.get("three_month")),
                }
            )
    return output


def _enrich_market_period_returns(items: list[dict[str, object]], max_items: int = 100) -> list[dict[str, object]]:
    candidates = items[:max_items]
    if not candidates:
        return items
    baselines_by_code: dict[str, dict[str, Optional[int]]] = {}
    with ThreadPoolExecutor(max_workers=min(20, len(candidates))) as executor:
        futures = {executor.submit(_naver_chart_baselines, str(item["code"])): str(item["code"]) for item in candidates}
        for future in as_completed(futures):
            try:
                baselines_by_code[futures[future]] = future.result()
            except Exception:
                continue
    for item in candidates:
        baselines = baselines_by_code.get(str(item["code"]))
        if not baselines:
            continue
        current_price = item.get("price") or baselines.get("latest")
        item["one_week_return"] = _rate(current_price, baselines.get("one_week"))
        item["one_month_return"] = _rate(current_price, baselines.get("one_month"))
        item["three_month_return"] = _rate(current_price, baselines.get("three_month"))
    return items


def _naver_market_rise_items(db: Optional[Session], market: Optional[str]) -> list[dict[str, object]]:
    markets = [market.upper()] if market and market.upper() in {"KOSPI", "KOSDAQ"} else ["KOSPI", "KOSDAQ"]
    fetched: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=len(markets)) as executor:
        futures = {
            executor.submit(
                MARKET_RISE_CACHE.get_or_set,
                ("naver_market_rise", target_market),
                MARKET_RISE_TTL_SECONDS,
                lambda selected_market=target_market: _fetch_naver_market_rise(selected_market),
            ): target_market
            for target_market in markets
        }
        for future in as_completed(futures):
            try:
                fetched.extend(future.result())
            except Exception:
                continue
    if not fetched:
        return []

    trade_date = _latest_ranking_trade_date(db)
    if db is None:
        return [
            {
                **live,
                "trade_date": trade_date,
                "market_cap": None,
                "metric_value": live.get("change_rate"),
                "one_week_return": None,
                "one_month_return": None,
                "three_month_return": None,
                "trading_value_change": None,
                "per": None,
                "pbr": None,
                "sentiment_score": None,
            }
            for live in fetched
        ]

    master_statement = select(StockMaster)
    if market:
        master_statement = master_statement.where(StockMaster.market == market.upper())
    masters = {stock.code: stock for stock in db.scalars(master_statement)}
    history = {str(item["code"]): item for item in _fast_price_items(db, market, lookback=64)}
    items: list[dict[str, object]] = []
    for live in fetched:
        code = str(live["code"])
        stock = masters.get(code)
        if not stock:
            continue
        base = history.get(code, {})
        item = dict(base)
        item.update(live)
        item.update(
            {
                "name": stock.name,
                "market": stock.market,
                "trade_date": trade_date,
                "market_cap": base.get("market_cap"),
                "metric_value": live.get("change_rate"),
                "one_week_return": _rate(live.get("price"), base.get("_one_week_price")),
                "one_month_return": _rate(live.get("price"), base.get("_one_month_price")),
                "three_month_return": _rate(live.get("price"), base.get("_three_month_price")),
                "trading_value_change": base.get("trading_value_change"),
                "per": None,
                "pbr": None,
                "sentiment_score": None,
            }
        )
        items.append(item)
    return items


def _parse_naver_domestic_list_payload(
    payload: dict[str, object],
    category: str,
    trade_date: date,
) -> list[dict[str, object]]:
    result = payload.get("result") if isinstance(payload, dict) else None
    rows = result.get("stocks") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return []

    items: list[dict[str, object]] = []
    for source_rank, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("id") or raw.get("itemCode") or "").strip().upper()
        name = str(raw.get("name") or raw.get("stockName") or "").strip()
        if not code or not name:
            continue
        raw_market = raw.get("stockExchangeType")
        if isinstance(raw_market, dict):
            raw_market = raw_market.get("name") or raw_market.get("code")
        market = str(raw_market or "").strip().upper()
        if market not in {"KOSPI", "KOSDAQ"}:
            continue
        price = _integer(raw.get("currentPrice"))
        # The low-52-week feed can lead with scheduled, expired, or otherwise
        # non-quoting instruments at 0 won. They do not make a useful ranking.
        if category == "low52" and (price is None or price <= 0):
            continue
        volume = _integer(raw.get("accumulatedTradingVolume"))
        market_cap = _integer(raw.get("marketValue"))
        change_rate = _decimal(raw.get("fluctuationsRatio"))
        metric_value: object = change_rate
        if category == "volume":
            metric_value = volume
        elif category == "market_cap":
            metric_value = market_cap
        items.append(
            {
                "code": code,
                "name": name,
                "market": market,
                "trade_date": trade_date,
                "price": price,
                "change_rate": change_rate,
                "volume": volume,
                "trading_value": _integer(raw.get("accumulatedTradingValue")),
                "market_cap": market_cap,
                "one_week_return": None,
                "one_month_return": None,
                "three_month_return": None,
                "trading_value_change": None,
                "per": None,
                "pbr": None,
                "dividend_yield": None,
                "dividend_per_share": None,
                "instrument_type": str(raw.get("stockEndType") or "stock").lower(),
                "sentiment_score": None,
                "metric_value": metric_value,
                "_source_rank": source_rank,
            }
        )
    return items


def _fetch_naver_domestic_list(
    sort_type: str,
    market_category: str,
    page_size: int,
    ranking_category: str,
    trade_date: date,
    *,
    fetch_all_pages: bool = False,
) -> list[dict[str, object]]:
    def fetch_page(page: int) -> tuple[list[dict[str, object]], int]:
        response = requests.get(
            NAVER_DOMESTIC_LIST_URL,
            params={
                "sortType": sort_type,
                "category": market_category,
                "domesticStockExchangeType": "KRX",
                "page": page,
                "pageSize": page_size,
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("isSuccess") is False:
            return [], 0
        result = payload.get("result")
        total_count = _integer(result.get("totalCount")) if isinstance(result, dict) else None
        return (
            _parse_naver_domestic_list_payload(payload, ranking_category, trade_date),
            max(0, total_count or 0),
        )

    first_page, total_count = fetch_page(1)
    if not fetch_all_pages or total_count <= page_size:
        return first_page

    page_count = min(10, (total_count + page_size - 1) // page_size)
    pages: dict[int, list[dict[str, object]]] = {1: first_page}
    with ThreadPoolExecutor(max_workers=min(4, page_count - 1)) as executor:
        futures = {executor.submit(fetch_page, page): page for page in range(2, page_count + 1)}
        for future in as_completed(futures):
            try:
                pages[futures[future]] = future.result()[0]
            except Exception:
                continue
    return [item for page in sorted(pages) for item in pages[page]]


def _naver_domestic_top_items(
    db: Optional[Session],
    category: str,
    market: Optional[str],
    limit: int,
    refresh: bool = False,
) -> list[dict[str, object]]:
    sort_type = {
        "volume": "quantTop",
        "market_cap": "marketValue",
        "low52": "low52week",
        "high52": "high52week",
    }[category]
    market_category = market.upper() if market and market.upper() in {"KOSPI", "KOSDAQ"} else "all"
    page_size = 50
    trade_date = _latest_ranking_trade_date(db)
    key = ("naver_domestic_top", category, market_category, page_size, trade_date.isoformat())
    factory = lambda: _fetch_naver_domestic_list(
        sort_type,
        market_category,
        page_size,
        category,
        trade_date,
        fetch_all_pages=category == "low52",
    )
    items = factory() if refresh else MARKET_TOP_CACHE.get_or_set(key, MARKET_TOP_TTL_SECONDS, factory)
    filtered = [
        item
        for item in items
        if not market or str(item.get("market") or "").upper() == market.upper()
    ][:limit]
    for rank, item in enumerate(filtered, start=1):
        item["rank"] = rank
        item["category"] = category
        item.pop("_source_rank", None)
    return filtered


def _parse_naver_realtime_quote_payload(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = payload.get("datas") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        result = payload.get("result") if isinstance(payload, dict) else None
        rows = result.get("datas") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return {}
    quotes: dict[str, dict[str, object]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("itemCode") or raw.get("code") or "").strip().upper()
        if not code:
            continue
        quotes[code] = {
            "code": code,
            "name": str(raw.get("stockName") or raw.get("name") or "").strip(),
            "market": _market_name(raw.get("stockExchangeType")),
            "price": _integer(raw.get("closePriceRaw")),
            "change_rate": _decimal(raw.get("fluctuationsRatioRaw")),
            "volume": _integer(raw.get("accumulatedTradingVolumeRaw")),
            "trading_value": _integer(raw.get("accumulatedTradingValueRaw")),
            "market_cap": _integer(raw.get("marketValueFullRaw")),
            "updated_at": raw.get("localTradedAt"),
        }
    return quotes


def _fetch_naver_realtime_quotes(codes: list[str]) -> dict[str, dict[str, object]]:
    normalized = list(dict.fromkeys(code for code in codes if re.fullmatch(r"[0-9A-Z]{6}", code)))
    output: dict[str, dict[str, object]] = {}
    for start in range(0, len(normalized), 50):
        chunk = normalized[start : start + 50]
        if not chunk:
            continue
        response = requests.get(
            f"{NAVER_REALTIME_QUOTES_URL}/{','.join(chunk)}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"},
            timeout=12,
        )
        response.raise_for_status()
        output.update(_parse_naver_realtime_quote_payload(response.json()))
    return output


def _parse_naver_etf_payload(
    payload: dict[str, object],
    mode: str,
    trade_date: date,
) -> list[dict[str, object]]:
    result = payload.get("result") if isinstance(payload, dict) else None
    rows = result.get("etfItemList") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return []
    items: list[dict[str, object]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("itemcode") or "").strip().upper()
        name = str(raw.get("itemname") or "").strip()
        if not code or not name:
            continue
        market_cap_eok = _integer(raw.get("marketSum"))
        market_cap = market_cap_eok * 100_000_000 if market_cap_eok is not None else None
        volume = _integer(raw.get("quant"))
        metric_value = volume if mode == "volume" else market_cap
        items.append(
            {
                "code": code,
                "name": name,
                "market": "KOSPI",
                "trade_date": trade_date,
                "price": _integer(raw.get("nowVal")),
                "change_rate": _decimal(raw.get("changeRate")),
                "volume": volume,
                "trading_value": _integer(raw.get("amonut"), multiplier=1_000_000),
                "market_cap": market_cap,
                "one_week_return": None,
                "one_month_return": None,
                "three_month_return": _decimal(raw.get("threeMonthEarnRate")),
                "trading_value_change": None,
                "per": None,
                "pbr": None,
                "dividend_yield": None,
                "dividend_per_share": None,
                "instrument_type": "etf",
                "sentiment_score": None,
                "metric_value": metric_value,
            }
        )
    return items


def _fetch_naver_etf_items(mode: str, trade_date: date) -> list[dict[str, object]]:
    response = requests.get(
        NAVER_ETF_LIST_URL,
        params={
            "etfType": 0,
            "targetColumn": "acc_quant" if mode == "volume" else "market_sum",
            "sortOrder": "desc",
        },
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/sise/etf.naver"},
        timeout=12,
    )
    response.raise_for_status()
    return _parse_naver_etf_payload(response.json(), mode, trade_date)


def _naver_etf_top_items(
    db: Optional[Session],
    limit: int,
    mode: str,
    refresh: bool = False,
) -> list[dict[str, object]]:
    normalized_mode = "volume" if mode == "volume" else "market_cap"
    trade_date = _latest_ranking_trade_date(db)
    key = ("naver_etf_top", normalized_mode, trade_date.isoformat())
    factory = lambda: _fetch_naver_etf_items(normalized_mode, trade_date)
    items = factory() if refresh else MARKET_TOP_CACHE.get_or_set(key, MARKET_TOP_TTL_SECONDS, factory)
    metric_key = "volume" if normalized_mode == "volume" else "market_cap"
    ranked = _ranked(items, "etf", metric_key, True, limit)
    return ranked


def _parse_naver_dividend_payload(
    payload: dict[str, object],
    mode: str,
    trade_date: date,
) -> list[dict[str, object]]:
    result = payload.get("result") if isinstance(payload, dict) else None
    rows = result.get("dividends") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return []
    items: list[dict[str, object]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("id") or "").strip().upper()
        name = str(raw.get("name") or "").strip()
        if not code or not name:
            continue
        dividend_yield = _decimal(raw.get("dividendRate"))
        dividend_per_share = _integer(raw.get("dividend"))
        metric_value: object = dividend_per_share if mode == "amount" else dividend_yield
        items.append(
            {
                "code": code,
                "name": name,
                "market": _market_name(raw.get("stockExchangeType")),
                "trade_date": trade_date,
                "price": None,
                "change_rate": None,
                "volume": None,
                "trading_value": None,
                "market_cap": None,
                "one_week_return": None,
                "one_month_return": None,
                "three_month_return": None,
                "trading_value_change": None,
                "per": None,
                "pbr": None,
                "dividend_yield": dividend_yield,
                "dividend_per_share": dividend_per_share,
                "dividend_date": raw.get("dividendDate"),
                "instrument_type": str(raw.get("stockEndType") or "stock").lower(),
                "sentiment_score": None,
                "metric_value": metric_value,
            }
        )
    return items


def _fetch_naver_dividend_items(mode: str, trade_date: date, page_count: int = 1) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []

    def fetch_page(page: int) -> list[dict[str, object]]:
        response = requests.get(
            NAVER_DOMESTIC_LIST_URL,
            params={
                "sortType": "dividend",
                "category": "value" if mode == "amount" else "rate",
                "domesticStockExchangeType": "KRX",
                "page": page,
                "pageSize": 50,
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        response.raise_for_status()
        return _parse_naver_dividend_payload(response.json(), mode, trade_date)

    with ThreadPoolExecutor(max_workers=min(6, page_count)) as executor:
        futures = [executor.submit(fetch_page, page) for page in range(1, page_count + 1)]
        for future in as_completed(futures):
            items.extend(future.result())
    metric_key = "dividend_per_share" if mode == "amount" else "dividend_yield"
    items.sort(key=lambda item: Decimal(str(item.get(metric_key) or 0)), reverse=True)
    return items


def _naver_dividend_top_items(
    db: Optional[Session],
    market: Optional[str],
    limit: int,
    mode: str,
    refresh: bool = False,
) -> list[dict[str, object]]:
    normalized_mode = "amount" if mode == "amount" else "yield"
    trade_date = _latest_ranking_trade_date(db)
    page_count = 6 if market and market.upper() in {"KOSPI", "KOSDAQ"} else 1
    key = ("naver_dividend_top", normalized_mode, page_count, trade_date.isoformat())
    factory = lambda: _fetch_naver_dividend_items(normalized_mode, trade_date, page_count)
    items = factory() if refresh else MARKET_TOP_CACHE.get_or_set(key, MARKET_TOP_TTL_SECONDS, factory)
    if market and market.upper() in {"KOSPI", "KOSDAQ"}:
        items = [item for item in items if item.get("market") == market.upper()]
    items = items[:limit]
    try:
        quotes = _fetch_naver_realtime_quotes([str(item["code"]) for item in items])
    except Exception:
        quotes = {}
    for item in items:
        quote = quotes.get(str(item["code"])) or {}
        for field in ("price", "change_rate", "volume", "trading_value", "market_cap"):
            if quote.get(field) is not None:
                item[field] = quote[field]
    metric_key = "dividend_per_share" if normalized_mode == "amount" else "dividend_yield"
    return _ranked(items, "dividend", metric_key, True, limit)


def _parse_naver_market_sum(html: bytes, market: str, trade_date: date) -> list[dict[str, object]]:
    soup = BeautifulSoup(html.decode("euc-kr", "replace"), "html.parser")
    items: list[dict[str, object]] = []
    for link in soup.select("table.type_2 a.tltle"):
        match = re.search(r"[?&]code=([0-9A-Z]+)", str(link.get("href") or ""))
        row = link.find_parent("tr")
        cells = row.find_all("td") if row else []
        if not match or len(cells) < 11:
            continue
        market_cap_eok = _integer(cells[6].get_text(" ", strip=True))
        per = _decimal(cells[10].get_text(" ", strip=True))
        if per is None or per <= 0:
            continue
        price = _integer(cells[2].get_text(" ", strip=True))
        change_rate = _decimal(cells[4].get_text(" ", strip=True))
        volume = _integer(cells[9].get_text(" ", strip=True))
        market_cap = market_cap_eok * 100_000_000 if market_cap_eok is not None else None
        items.append(
            {
                "code": match.group(1),
                "name": link.get_text(" ", strip=True),
                "market": market,
                "trade_date": trade_date,
                "price": price,
                "change_rate": change_rate,
                "volume": volume,
                "trading_value": price * volume if price is not None and volume is not None else None,
                "market_cap": market_cap,
                "one_week_return": None,
                "one_month_return": None,
                "three_month_return": None,
                "trading_value_change": None,
                "per": per,
                "pbr": None,
                "dividend_yield": None,
                "dividend_per_share": None,
                "instrument_type": "stock",
                "sentiment_score": None,
                "metric_value": per,
            }
        )
    return items


def _fetch_naver_market_sum_page(market: str, page: int, trade_date: date) -> list[dict[str, object]]:
    response = requests.get(
        NAVER_MARKET_SUM_URL,
        params={"sosok": "1" if market == "KOSDAQ" else "0", "page": page},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=12,
    )
    response.raise_for_status()
    return _parse_naver_market_sum(response.content, market, trade_date)


def _naver_per_top_items(
    db: Optional[Session],
    market: Optional[str],
    limit: int,
    refresh: bool = False,
) -> list[dict[str, object]]:
    markets = [market.upper()] if market and market.upper() in {"KOSPI", "KOSDAQ"} else ["KOSPI", "KOSDAQ"]
    trade_date = _latest_ranking_trade_date(db)
    page_count = max(2, min(6, (max(limit * 4, 100) + 49) // 50))
    key = ("naver_per_top", tuple(markets), page_count, trade_date.isoformat())

    def fetch_all() -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        with ThreadPoolExecutor(max_workers=min(8, len(markets) * page_count)) as executor:
            futures = [
                executor.submit(_fetch_naver_market_sum_page, target_market, page, trade_date)
                for target_market in markets
                for page in range(1, page_count + 1)
            ]
            for future in as_completed(futures):
                try:
                    items.extend(future.result())
                except Exception:
                    continue
        return items

    items = fetch_all() if refresh else MARKET_TOP_CACHE.get_or_set(key, MARKET_FUNDAMENTAL_TTL_SECONDS, fetch_all)
    return _ranked(items, "per", "per", False, limit)


def _live_top_payload(
    db: Optional[Session],
    category: str,
    market: Optional[str],
    items: list[dict[str, object]],
    source: str,
) -> dict[str, object]:
    rankings = enrich_market_ranking_sector_fields(db, items)
    return {
        "category": category,
        "market": market,
        "as_of": _now_kst(),
        "source": source,
        "universe_count": len(rankings),
        "matching_count": len(rankings),
        "items": rankings,
    }


def _price_groups(db: Session, market: Optional[str]) -> dict[str, tuple[StockMaster, list[DailyPrice]]]:
    latest_date = db.scalar(select(func.max(DailyPrice.trade_date)))
    if not latest_date:
        return {}

    from_date = latest_date - timedelta(days=150)
    statement = (
        select(StockMaster, DailyPrice)
        .join(DailyPrice, DailyPrice.code == StockMaster.code)
        .where(DailyPrice.trade_date >= from_date)
        .order_by(StockMaster.code, DailyPrice.trade_date)
    )
    if market:
        statement = statement.where(StockMaster.market == market.upper())

    groups: dict[str, tuple[StockMaster, list[DailyPrice]]] = {}
    for stock, price in db.execute(statement):
        if stock.code not in groups:
            groups[stock.code] = (stock, [])
        groups[stock.code][1].append(price)
    return groups


def _stock_universe_count(db: Session, market: Optional[str]) -> int:
    statement = select(func.count()).select_from(StockMaster)
    if market:
        statement = statement.where(StockMaster.market == market.upper())
    return int(db.scalar(statement) or 0)


def _base_item_from_rows(stock: dict[str, object], prices: list[dict[str, object]]) -> Optional[dict[str, object]]:
    if not prices:
        return None
    latest = prices[-1]
    previous = prices[-2] if len(prices) >= 2 else None
    one_week = prices[-6] if len(prices) >= 6 else None
    one_month = prices[-22] if len(prices) >= 22 else None
    three_month = prices[-64] if len(prices) >= 64 else None
    recent_values = [value for row in prices[-5:] if (value := _mapping_row_value(row)) is not None]
    baseline_values = [value for row in prices[-25:-5] if (value := _mapping_row_value(row)) is not None]
    recent_average = Decimal(str(mean(recent_values))) if recent_values else None
    baseline_average = Decimal(str(mean(baseline_values))) if baseline_values else None

    return {
        "code": stock["code"],
        "name": stock["name"],
        "market": stock["market"],
        "trade_date": latest.get("trade_date"),
        "price": latest.get("close"),
        "volume": latest.get("volume"),
        "market_cap": latest.get("market_cap"),
        "change_rate": _rate(latest.get("close"), previous.get("close") if previous else None),
        "_previous_price": previous.get("close") if previous else None,
        "_one_week_price": one_week.get("close") if one_week else None,
        "_one_month_price": one_month.get("close") if one_month else None,
        "_three_month_price": three_month.get("close") if three_month else None,
        "one_week_return": _rate(latest.get("close"), one_week.get("close") if one_week else None),
        "one_month_return": _rate(latest.get("close"), one_month.get("close") if one_month else None),
        "three_month_return": _rate(latest.get("close"), three_month.get("close") if three_month else None),
        "trading_value": _mapping_row_value(latest),
        "trading_value_change": _rate(recent_average, baseline_average),
        "per": None,
        "pbr": None,
        "sentiment_score": None,
    }


def _fast_price_items(db: Session, market: Optional[str], lookback: int = 64) -> list[dict[str, object]]:
    recent_dates = list(
        db.scalars(
            select(DailyPrice.trade_date)
            .distinct()
            .order_by(desc(DailyPrice.trade_date))
            .limit(lookback)
        )
    )
    if not recent_dates:
        return []
    from_date = min(recent_dates)
    statement = (
        select(
            StockMaster.code.label("code"),
            StockMaster.name.label("name"),
            StockMaster.market.label("market"),
            DailyPrice.trade_date.label("trade_date"),
            DailyPrice.close.label("close"),
            DailyPrice.volume.label("volume"),
            DailyPrice.trading_value.label("trading_value"),
            DailyPrice.market_cap.label("market_cap"),
        )
        .join(DailyPrice, DailyPrice.code == StockMaster.code)
        .where(
            DailyPrice.close.is_not(None),
            DailyPrice.trade_date >= from_date,
        )
    )
    if market:
        statement = statement.where(StockMaster.market == market.upper())
    rows = db.execute(statement.order_by(StockMaster.code, DailyPrice.trade_date)).mappings()

    groups: dict[str, tuple[dict[str, object], list[dict[str, object]]]] = {}
    for row in rows:
        code = str(row["code"])
        if code not in groups:
            groups[code] = (
                {"code": code, "name": row["name"], "market": row["market"]},
                [],
            )
        groups[code][1].append(dict(row))
    return [item for stock, prices in groups.values() if (item := _base_item_from_rows(stock, prices))]


def _period_return_items(db: Session, market: Optional[str], mode: str) -> list[dict[str, object]]:
    required_sessions = 6 if mode == "week" else 22
    coverage_statement = (
        select(DailyPrice.trade_date, func.count(DailyPrice.code).label("stock_count"))
        .join(StockMaster, StockMaster.code == DailyPrice.code)
        .where(DailyPrice.close.is_not(None))
        .group_by(DailyPrice.trade_date)
        .order_by(desc(DailyPrice.trade_date))
        .limit(40)
    )
    if market:
        coverage_statement = coverage_statement.where(StockMaster.market == market.upper())
    coverage_rows = list(db.execute(coverage_statement))
    if not coverage_rows:
        return []
    max_coverage = max(int(row.stock_count or 0) for row in coverage_rows)
    minimum_coverage = max(1, int(max_coverage * 0.75))
    latest_complete_date = next(
        (row.trade_date for row in coverage_rows if int(row.stock_count or 0) >= minimum_coverage),
        coverage_rows[0].trade_date,
    )
    date_statement = (
        select(DailyPrice.trade_date)
        .where(DailyPrice.trade_date <= latest_complete_date)
        .distinct()
        .order_by(desc(DailyPrice.trade_date))
        .limit(required_sessions)
    )
    recent_dates = list(db.scalars(date_statement))
    if len(recent_dates) < required_sessions:
        return []
    latest_date = recent_dates[0]
    previous_date = recent_dates[1]
    baseline_date = recent_dates[5] if mode == "week" else recent_dates[21]

    LatestPrice = aliased(DailyPrice)
    PreviousPrice = aliased(DailyPrice)
    BaselinePrice = aliased(DailyPrice)
    statement = (
        select(
            StockMaster,
            LatestPrice,
            PreviousPrice.close.label("previous_close"),
            BaselinePrice.close.label("baseline_close"),
        )
        .join(LatestPrice, and_(LatestPrice.code == StockMaster.code, LatestPrice.trade_date == latest_date))
        .outerjoin(PreviousPrice, and_(PreviousPrice.code == StockMaster.code, PreviousPrice.trade_date == previous_date))
        .outerjoin(BaselinePrice, and_(BaselinePrice.code == StockMaster.code, BaselinePrice.trade_date == baseline_date))
        .where(LatestPrice.close.is_not(None), BaselinePrice.close.is_not(None))
    )
    if market:
        statement = statement.where(StockMaster.market == market.upper())

    items: list[dict[str, object]] = []
    for stock, latest, previous_close, baseline_close in db.execute(statement):
        period_return = _rate(latest.close, baseline_close)
        items.append(
            {
                "code": stock.code,
                "name": stock.name,
                "market": stock.market,
                "trade_date": latest.trade_date,
                "price": latest.close,
                "volume": latest.volume,
                "market_cap": latest.market_cap,
                "change_rate": _rate(latest.close, previous_close),
                "_previous_price": previous_close,
                "_one_week_price": baseline_close if mode == "week" else None,
                "_one_month_price": baseline_close if mode == "month" else None,
                "_three_month_price": None,
                "one_week_return": period_return if mode == "week" else None,
                "one_month_return": period_return if mode == "month" else None,
                "three_month_return": None,
                "trading_value": _row_value(latest),
                "trading_value_change": None,
                "per": None,
                "pbr": None,
                "sentiment_score": None,
            }
        )
    return items


def _latest_session_surge_items(db: Session, market: Optional[str]) -> list[dict[str, object]]:
    date_statement = (
        select(DailyPrice.trade_date)
        .join(StockMaster, StockMaster.code == DailyPrice.code)
        .distinct()
        .order_by(desc(DailyPrice.trade_date))
    )
    if market:
        date_statement = date_statement.where(StockMaster.market == market.upper())
    date_statement = date_statement.limit(16)
    now = _now_kst()
    completed_dates = [
        trade_date
        for trade_date in db.scalars(date_statement)
        if trade_date.weekday() < 5
        and not (trade_date >= now.date() and (now.hour, now.minute) <= (15, 30))
    ]
    if len(completed_dates) < 2:
        return []
    latest_date, previous_date = completed_dates[:2]

    LatestPrice = aliased(DailyPrice)
    PreviousPrice = aliased(DailyPrice)
    statement = (
        select(StockMaster, LatestPrice, PreviousPrice.close.label("previous_close"))
        .join(LatestPrice, and_(LatestPrice.code == StockMaster.code, LatestPrice.trade_date == latest_date))
        .outerjoin(PreviousPrice, and_(PreviousPrice.code == StockMaster.code, PreviousPrice.trade_date == previous_date))
        .where(LatestPrice.close.is_not(None))
    )
    if market:
        statement = statement.where(StockMaster.market == market.upper())

    items: list[dict[str, object]] = []
    for stock, latest, previous_close in db.execute(statement):
        items.append(
            {
                "code": stock.code,
                "name": stock.name,
                "market": stock.market,
                "trade_date": latest.trade_date,
                "price": latest.close,
                "volume": latest.volume,
                "market_cap": latest.market_cap,
                "change_rate": _rate(latest.close, previous_close),
                "_previous_price": previous_close,
                "_one_week_price": None,
                "_one_month_price": None,
                "_three_month_price": None,
                "one_week_return": None,
                "one_month_return": None,
                "three_month_return": None,
                "trading_value": _row_value(latest),
                "trading_value_change": None,
                "per": None,
                "pbr": None,
                "sentiment_score": None,
            }
        )
    return items


def _enrich_database_period_returns(
    db: Session,
    items: list[dict[str, object]],
) -> list[dict[str, object]]:
    codes = [str(item["code"]) for item in items if item.get("code")]
    trade_dates = [item["trade_date"] for item in items if item.get("trade_date")]
    if not codes or not trade_dates:
        return items

    row_number = func.row_number().over(
        partition_by=DailyPrice.code,
        order_by=DailyPrice.trade_date.desc(),
    ).label("row_number")
    ranked = (
        select(
            DailyPrice.code.label("code"),
            DailyPrice.trade_date.label("trade_date"),
            DailyPrice.close.label("close"),
            row_number,
        )
        .where(
            DailyPrice.code.in_(codes),
            DailyPrice.trade_date <= max(trade_dates),
            DailyPrice.close.is_not(None),
        )
        .subquery()
    )
    history: dict[str, list[int]] = {code: [] for code in codes}
    rows = db.execute(
        select(ranked)
        .where(ranked.c.row_number <= 64)
        .order_by(ranked.c.code, ranked.c.trade_date)
    ).mappings()
    for row in rows:
        if row["close"] is not None:
            history[str(row["code"])].append(int(row["close"]))

    for item in items:
        closes = history.get(str(item.get("code"))) or []
        current_price = item.get("price")
        item["one_month_return"] = _rate(current_price, closes[-22] if len(closes) >= 22 else None)
        item["one_week_return"] = _rate(current_price, closes[-6] if len(closes) >= 6 else None)
        item["three_month_return"] = _rate(current_price, closes[-64] if len(closes) >= 64 else None)
    return items


def _base_item(stock: StockMaster, prices: list[DailyPrice]) -> Optional[dict[str, object]]:
    if not prices:
        return None
    latest = prices[-1]
    previous = prices[-2] if len(prices) >= 2 else None
    one_week = prices[-6] if len(prices) >= 6 else None
    one_month = prices[-22] if len(prices) >= 22 else None
    three_month = prices[-64] if len(prices) >= 64 else None
    recent_values = [value for row in prices[-5:] if (value := _row_value(row)) is not None]
    baseline_values = [value for row in prices[-25:-5] if (value := _row_value(row)) is not None]
    recent_average = Decimal(str(mean(recent_values))) if recent_values else None
    baseline_average = Decimal(str(mean(baseline_values))) if baseline_values else None

    return {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        "trade_date": latest.trade_date,
        "price": latest.close,
        "volume": latest.volume,
        "market_cap": latest.market_cap,
        "change_rate": _rate(latest.close, previous.close if previous else None),
        "_previous_price": previous.close if previous else None,
        "_one_week_price": one_week.close if one_week else None,
        "_one_month_price": one_month.close if one_month else None,
        "_three_month_price": three_month.close if three_month else None,
        "one_week_return": _rate(latest.close, one_week.close if one_week else None),
        "one_month_return": _rate(latest.close, one_month.close if one_month else None),
        "three_month_return": _rate(latest.close, three_month.close if three_month else None),
        "trading_value": _row_value(latest),
        "trading_value_change": _rate(recent_average, baseline_average),
        "per": None,
        "pbr": None,
        "sentiment_score": None,
    }


def _ranked(items: list[dict[str, object]], category: str, metric_key: str, reverse: bool = True, limit: int = 50) -> list[dict[str, object]]:
    filtered = [item for item in items if item.get(metric_key) is not None]
    filtered.sort(key=lambda item: Decimal(str(item[metric_key])), reverse=reverse)
    output = filtered[:limit]
    for idx, item in enumerate(output, start=1):
        item["rank"] = idx
        item["category"] = category
        item["metric_value"] = item.get(metric_key)
    return output


def _valuation_rank(
    items: list[dict[str, object]],
    limit: int,
    candidate_count: int = 160,
    refresh_live: bool = False,
) -> list[dict[str, object]]:
    candidates = sorted(
        [item for item in items if item.get("trading_value")],
        key=lambda item: int(item["trading_value"]),
        reverse=True,
    )[:candidate_count]

    def enrich(item: dict[str, object]) -> Optional[dict[str, object]]:
        if refresh_live:
            snapshot = _naver_snapshot(str(item["code"]), refresh=True)
        else:
            snapshot = NAVER_CACHE.get(("naver_snapshot", str(item["code"]))) or {}
        per = snapshot.get("per")
        pbr = snapshot.get("pbr")
        if per is None or pbr is None or Decimal(str(per)) <= 0 or Decimal(str(pbr)) <= 0:
            return None
        enriched = dict(item)
        enriched["per"] = per
        enriched["pbr"] = pbr
        industry_per = snapshot.get("industry_per")
        if industry_per and Decimal(str(industry_per)) > 0:
            enriched["metric_value"] = _round_decimal(Decimal(str(per)) / Decimal(str(industry_per)) * Decimal("100"))
        else:
            enriched["metric_value"] = per
        return enriched

    enriched_items: list[dict[str, object]] = []
    if refresh_live:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(enrich, item): item for item in candidates}
            for future in as_completed(futures):
                item = future.result()
                if item:
                    enriched_items.append(item)
    else:
        for candidate in candidates:
            item = enrich(candidate)
            if item:
                enriched_items.append(item)

    if len(enriched_items) < limit:
        fallback_items: list[dict[str, object]] = []
        for item in candidates:
            if any(existing["code"] == item["code"] for existing in enriched_items):
                continue
            market_cap = item.get("market_cap")
            trading_value = item.get("trading_value")
            if not market_cap or not trading_value:
                continue
            fallback = dict(item)
            fallback["metric_value"] = _round_decimal(Decimal(str(trading_value)) / Decimal(str(market_cap)) * Decimal("100"))
            fallback_items.append(fallback)
        fallback_items.sort(key=lambda item: Decimal(str(item["metric_value"])), reverse=True)
        enriched_items.extend(fallback_items[: max(0, limit - len(enriched_items))])

    def valuation_sort_key(item: dict[str, object]) -> tuple[int, Decimal, Decimal]:
        if item.get("per") is not None and item.get("pbr") is not None:
            return (0, Decimal(str(item["metric_value"])), Decimal(str(item["pbr"])))
        return (1, -Decimal(str(item["metric_value"] or 0)), Decimal("0"))

    enriched_items.sort(key=valuation_sort_key)
    output = enriched_items[:limit]
    for idx, item in enumerate(output, start=1):
        item["rank"] = idx
        item["category"] = "valuation"
    return output


def _enrich_live_rankings(items: list[dict[str, object]], category: str, limit: int) -> list[dict[str, object]]:
    def enrich(item: dict[str, object]) -> dict[str, object]:
        snapshot = _naver_snapshot(str(item["code"]), refresh=True)
        enriched = dict(item)
        price = snapshot.get("price")
        if price is not None:
            enriched["price"] = price
            enriched["one_month_return"] = _rate(price, item.get("_one_month_price"))
            enriched["three_month_return"] = _rate(price, item.get("_three_month_price"))
        change_rate = snapshot.get("change_rate_abs")
        if change_rate is not None:
            enriched["change_rate"] = change_rate
        if snapshot.get("trading_value") is not None:
            enriched["trading_value"] = snapshot.get("trading_value")
        if snapshot.get("market_cap") is not None:
            enriched["market_cap"] = snapshot.get("market_cap")
        if category == "surge":
            enriched["metric_value"] = enriched.get("change_rate")
        elif category == "trading_value":
            enriched["metric_value"] = enriched.get("trading_value")
        elif category == "momentum":
            one_month = enriched.get("one_month_return")
            three_month = enriched.get("three_month_return")
            if one_month is not None and three_month is not None:
                enriched["momentum_score"] = _round_decimal(
                    Decimal(str(one_month)) * Decimal("0.55") + Decimal(str(three_month)) * Decimal("0.45")
                )
                enriched["metric_value"] = enriched["momentum_score"]
        return enriched

    enriched_items: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(enrich, item) for item in items]
        for future in as_completed(futures):
            enriched_items.append(future.result())

    metric_key = {
        "surge": "change_rate",
        "trading_value": "trading_value",
        "momentum": "momentum_score",
        "sentiment": "sentiment_score",
        "valuation": "metric_value",
    }.get(category, "metric_value")
    reverse = category != "valuation"
    enriched_items = [item for item in enriched_items if item.get(metric_key) is not None]
    enriched_items.sort(key=lambda item: Decimal(str(item[metric_key])), reverse=reverse)
    output = enriched_items[:limit]
    for idx, item in enumerate(output, start=1):
        item["rank"] = idx
        item["category"] = category
        item["metric_value"] = item.get(metric_key)
    return output


def _news_sentiment_rank(db: Session, items: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    since = datetime.utcnow() - timedelta(days=14)
    news = list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.published_at >= since)
            .order_by(NewsItem.published_at.desc())
            .limit(2000)
        )
    )
    if not news:
        return []

    scored: list[dict[str, object]] = []
    stock_items = sorted(items, key=lambda item: int(item.get("trading_value") or 0), reverse=True)[:600]
    for item in stock_items:
        name = str(item["name"])
        matches = [row for row in news if name in row.title or (row.summary and name in row.summary)]
        if not matches:
            continue
        score = sum(_keyword_score(f"{row.title} {row.summary or ''}") for row in matches)
        normalized = _round_decimal(Decimal(score) / Decimal(len(matches)) * Decimal("100"))
        ranked = dict(item)
        ranked["sentiment_score"] = normalized
        ranked["metric_value"] = normalized
        ranked["news_count"] = len(matches)
        scored.append(ranked)

    scored.sort(key=lambda item: Decimal(str(item["sentiment_score"])), reverse=True)
    output = scored[:limit]
    for idx, item in enumerate(output, start=1):
        item["rank"] = idx
        item["category"] = "sentiment"
    return output


def build_market_rankings(
    db: Optional[Session],
    category: str,
    market: Optional[str] = None,
    limit: int = 50,
    refresh_live: bool = False,
    mode: str = "",
) -> dict[str, object]:
    category = str(category or "surge").strip().lower()
    normalized_mode = str(mode or "").strip().lower()

    try:
        if category in {"volume", "market_cap", "low52", "high52"}:
            rankings = _naver_domestic_top_items(
                db,
                category,
                market,
                limit,
                refresh=refresh_live,
            )
            if rankings:
                payload = _live_top_payload(db, category, market, rankings, "naver_domestic_list")
                payload["mode"] = normalized_mode
                return payload
        elif category == "etf":
            rankings = _naver_etf_top_items(
                db,
                limit,
                normalized_mode or "market_cap",
                refresh=refresh_live,
            )
            payload = _live_top_payload(db, category, market, rankings, "naver_etf")
            payload["mode"] = "volume" if normalized_mode == "volume" else "market_cap"
            return payload
        elif category == "dividend":
            rankings = _naver_dividend_top_items(
                db,
                market,
                limit,
                normalized_mode or "yield",
                refresh=refresh_live,
            )
            payload = _live_top_payload(db, category, market, rankings, "naver_dividend")
            payload["mode"] = "amount" if normalized_mode == "amount" else "yield"
            return payload
        elif category == "per":
            rankings = _naver_per_top_items(db, market, limit, refresh=refresh_live)
            if rankings:
                payload = _live_top_payload(db, category, market, rankings, "naver_market_sum")
                payload["mode"] = "low"
                return payload
    except Exception:
        # The database fallback below keeps the screen usable during a source outage.
        pass

    if category == "surge" and normalized_mode in {"week", "weekly", "month", "monthly"}:
        period_mode = "week" if normalized_mode in {"week", "weekly"} else "month"
        items = _period_return_items(db, market, period_mode) if db is not None else []
        metric_key = "one_week_return" if period_mode == "week" else "one_month_return"
        maximum_return = Decimal("300") if period_mode == "week" else Decimal("1000")
        candidates = [
            item
            for item in items
            if Decimal("0") < Decimal(str(item.get(metric_key) or 0)) <= maximum_return
        ]
        rankings = _ranked(candidates, "surge", metric_key, True, limit)
        payload = _live_top_payload(db, category, market, rankings, "database")
        payload["mode"] = "week" if metric_key == "one_week_return" else "month"
        return payload

    if category in {"etf", "dividend"}:
        payload = _live_top_payload(db, category, market, [], "unavailable")
        payload["mode"] = normalized_mode
        return payload

    should_refresh_live = category == "surge" and _is_regular_session()
    source = "database"
    # The market-wide feed remains authoritative after the close as well. The
    # local DailyPrice table can lag or contain an unadjusted corporate-action
    # price, which must never be presented as the current surge rate.
    live_market_items = _naver_market_rise_items(None, market) if category == "surge" else []
    if live_market_items:
        items = live_market_items
        source = "naver_market_rise"
    elif category == "surge":
        items = _latest_session_surge_items(db, market)
        if not items:
            items = _fast_price_items(db, market, lookback=64)
    else:
        groups = _price_groups(db, market)
        items = [item for stock, prices in groups.values() if (item := _base_item(stock, prices))]
    rank_limit = (
        limit
        if source == "naver_market_rise"
        else min(max(limit * 5, limit), 200)
        if should_refresh_live and category in {"surge", "trading_value", "momentum"}
        else limit
    )

    universe_count = len(items)
    matching_count = 0
    if category == "surge":
        rising_items = [
            item
            for item in items
            if Decimal("0") < Decimal(str(item.get("change_rate") or 0)) <= Decimal("30.5")
        ]
        matching_count = len(rising_items)
        rankings = _ranked(rising_items, "surge", "change_rate", True, rank_limit)
    elif category == "trading_value":
        rankings = _ranked(items, "trading_value", "trading_value", True, rank_limit)
    elif category == "volume":
        rankings = _ranked(items, "volume", "volume", True, rank_limit)
    elif category == "market_cap":
        rankings = _ranked(items, "market_cap", "market_cap", True, rank_limit)
    elif category == "low52":
        rankings = _ranked(items, "low52", "change_rate", False, rank_limit)
    elif category == "high52":
        rankings = _ranked(items, "high52", "change_rate", True, rank_limit)
    elif category == "per":
        rankings = _ranked(items, "per", "per", False, rank_limit)
    elif category == "momentum":
        for item in items:
            one_month = item.get("one_month_return")
            three_month = item.get("three_month_return")
            if one_month is not None and three_month is not None:
                item["momentum_score"] = _round_decimal(Decimal(str(one_month)) * Decimal("0.55") + Decimal(str(three_month)) * Decimal("0.45"))
        rankings = _ranked(items, "momentum", "momentum_score", True, rank_limit)
    elif category == "valuation":
        rankings = _valuation_rank(items, limit, refresh_live=refresh_live)
    elif category == "sentiment":
        rankings = _news_sentiment_rank(db, items, limit)
    else:
        rankings = _ranked(items, "surge", "change_rate", True, rank_limit)
    if category != "surge":
        matching_count = len(rankings)

    if should_refresh_live and source != "naver_market_rise" and rankings:
        fallback_rankings = rankings[:limit]
        try:
            live_rankings = _enrich_live_rankings(rankings, category, limit)
        except Exception:
            live_rankings = []
        if live_rankings:
            existing_codes = {str(item["code"]) for item in live_rankings}
            for item in fallback_rankings:
                if str(item["code"]) not in existing_codes:
                    live_rankings.append(item)
                if len(live_rankings) >= limit:
                    break
            rankings = live_rankings[:limit]
        else:
            rankings = fallback_rankings

    if category == "surge" and source == "naver_market_rise" and rankings:
        rankings = _enrich_market_period_returns(rankings, max_items=min(100, limit))
    elif category == "surge" and source == "database" and rankings:
        rankings = _enrich_database_period_returns(db, rankings)

    rankings = enrich_market_ranking_sector_fields(db, rankings)

    return {
        "category": category,
        "market": market,
        "mode": normalized_mode or ("daily" if category == "surge" else ""),
        "as_of": _now_kst(),
        "source": source,
        "universe_count": universe_count,
        "matching_count": matching_count,
        "items": rankings,
    }


def enrich_market_ranking_sector_fields(
    db: Optional[Session],
    items: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Attach the shared investment-sector layer without changing source fields."""

    result = [dict(item) for item in items]
    if db is None or not result:
        for item in result:
            item.update(
                investment_sector_fields(
                    item.get("sector"),
                    item.get("industry"),
                )
            )
        return result

    codes = {
        str(item.get("code") or "").strip()
        for item in result
        if str(item.get("code") or "").strip()
    }
    stocks_by_code = {
        stock.code: stock
        for stock in db.scalars(select(StockMaster).where(StockMaster.code.in_(tuple(codes))))
    } if codes else {}
    for item in result:
        stock = stocks_by_code.get(str(item.get("code") or "").strip())
        sector = stock.sector if stock else item.get("sector")
        industry = stock.industry if stock else item.get("industry")
        item.update(investment_sector_fields(sector, industry))
    return result
