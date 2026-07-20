from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.models import MacroObservation
from app.repository import finish_ingestion, start_ingestion, upsert_many

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}
DEFAULT_MACRO_SERIES = [
    {"symbol": "USDKRW=X", "name": "USD/KRW", "unit": "KRW"},
    {"symbol": "^TNX", "name": "US 10Y Treasury Yield", "unit": "%"},
    {"symbol": "CL=F", "name": "WTI Crude Oil Futures", "unit": "USD"},
    {"symbol": "GC=F", "name": "Gold Futures", "unit": "USD"},
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


def _period(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


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
                "period": _period(int(timestamp)),
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
