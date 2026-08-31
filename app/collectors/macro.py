from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from sqlalchemy.orm import Session

from app.models import MacroObservation
from app.repository import finish_ingestion, start_ingestion, upsert_many

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}
NAVER_INDEX_CHART_URL = "https://fchart.stock.naver.com/sise.nhn"
NAVER_INDEX_SYMBOLS = {"^KS11": "KOSPI", "^KQ11": "KOSDAQ"}
DEFAULT_MACRO_SERIES = [
    {"symbol": "USDKRW=X", "name": "USD/KRW", "unit": "KRW"},
    {"symbol": "^TNX", "name": "US 10Y Treasury Yield", "unit": "%"},
    {"symbol": "CL=F", "name": "WTI Crude Oil Futures", "unit": "USD"},
    {"symbol": "GC=F", "name": "Gold Futures", "unit": "USD"},
    {"symbol": "^IXIC", "name": "NASDAQ Composite", "unit": "index"},
    {"symbol": "^GSPC", "name": "S&P 500 Index", "unit": "index"},
    {"symbol": "^KS11", "name": "KOSPI Index", "unit": "index"},
    {"symbol": "^KQ11", "name": "KOSDAQ Index", "unit": "index"},
]


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _period(timestamp: int, timezone_name: str | None = None) -> str:
    target_timezone = timezone.utc
    if timezone_name:
        try:
            target_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            target_timezone = timezone.utc
    return datetime.fromtimestamp(timestamp, tz=target_timezone).date().isoformat()


def fetch_yahoo_macro_rows(symbol: str, name: str, unit: str, range_: str = "1y") -> list[dict[str, object]]:
    response = requests.get(
        YAHOO_CHART_URL.format(symbol=symbol),
        params={"range": range_, "interval": "1d"},
        headers=YAHOO_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return []
    exchange_timezone = str((result.get("meta") or {}).get("exchangeTimezoneName") or "UTC")
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
    closes = quote.get("close") or []
    rows: list[dict[str, object]] = []
    for timestamp, close in zip(timestamps, closes):
        value = _to_decimal(close)
        if value is None:
            continue
        rows.append(
            {
                "source": "yahoo",
                "series_code": symbol,
                "item_code": "close",
                "period": _period(int(timestamp), exchange_timezone),
                "value": value,
                "unit": unit,
                "name": name,
            }
        )
    return rows


def _naver_index_count(range_: str) -> int:
    return {
        "5d": 10,
        "1mo": 30,
        "3mo": 90,
        "6mo": 150,
        "1y": 280,
        "2y": 560,
        "5y": 1400,
    }.get(str(range_ or "").lower(), 280)


def fetch_naver_index_close_rows(
    series_code: str,
    name: str,
    unit: str,
    range_: str = "1y",
) -> list[dict[str, object]]:
    naver_symbol = NAVER_INDEX_SYMBOLS.get(series_code)
    if not naver_symbol:
        return []
    response = requests.get(
        NAVER_INDEX_CHART_URL,
        params={
            "symbol": naver_symbol,
            "timeframe": "day",
            "count": str(_naver_index_count(range_)),
            "requestType": "0",
        },
        headers=YAHOO_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    rows: list[dict[str, object]] = []
    for raw in re.findall(rb'data="([^"]+)"', response.content):
        fields = raw.decode("ascii", errors="ignore").split("|")
        if len(fields) < 5 or not re.fullmatch(r"\d{8}", fields[0]):
            continue
        value = _to_decimal(fields[4])
        if value is None:
            continue
        rows.append(
            {
                "source": "naver_finance",
                "series_code": series_code,
                "item_code": "close",
                "period": datetime.strptime(fields[0], "%Y%m%d").date().isoformat(),
                "value": value,
                "unit": unit,
                "name": name,
            }
        )
    return rows


def collect_yahoo_macro_observations(
    db: Session,
    *,
    range_: str = "1y",
    series: list[dict[str, str]] | None = None,
) -> int:
    run = start_ingestion(db, "yahoo", "macro_observations")
    rows: list[dict[str, object]] = []
    errors: dict[str, str] = {}
    try:
        for item in series or DEFAULT_MACRO_SERIES:
            symbol = item["symbol"]
            try:
                rows.extend(
                    fetch_yahoo_macro_rows(
                        symbol,
                        item.get("name") or symbol,
                        item.get("unit") or "",
                        range_=range_,
                    )
                )
                if symbol in NAVER_INDEX_SYMBOLS:
                    rows.extend(
                        fetch_naver_index_close_rows(
                            symbol,
                            item.get("name") or symbol,
                            item.get("unit") or "",
                            range_=range_,
                        )
                    )
            except Exception as exc:
                errors[symbol] = str(exc)
        count = upsert_many(db, MacroObservation, rows)
        db.commit()
        message = f"series={len(series or DEFAULT_MACRO_SERIES)}"
        if errors:
            message += f" failed={len(errors)}"
        finish_ingestion(db, run, "success", count, message)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise
