from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import MacroObservation


YAHOO_CHART_URLS = (
    "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
)
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}

GLOBAL_MARKET_DEFINITIONS = (
    ("SP500", "S&P 500", "^GSPC", "index"),
    ("NASDAQ", "나스닥 종합", "^IXIC", "index"),
    ("SOX", "필라델피아 반도체", "^SOX", "index"),
    ("DOW", "다우존스", "^DJI", "index"),
    ("GOLD", "금", "GC=F", "USD"),
    ("OIL", "원유", "CL=F", "USD"),
)
NEW_YORK_TZ = ZoneInfo("America/New_York")


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _stored_asset(
    db: Session,
    *,
    code: str,
    label: str,
    symbol: str,
    unit: str,
    limit: int,
) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(MacroObservation)
            .where(MacroObservation.source == "yahoo")
            .where(MacroObservation.series_code == symbol)
            .where(MacroObservation.item_code == "close")
            .order_by(desc(MacroObservation.period))
            .limit(limit)
        )
    )
    rows.reverse()
    points = [
        {"date": row.period, "value": _number(row.value)}
        for row in rows
        if row.value is not None
    ]
    current = _number(rows[-1].value) if rows else None
    previous = _number(rows[-2].value) if len(rows) > 1 else None
    change = current - previous if current is not None and previous is not None else None
    change_rate = change / previous * 100 if change is not None and previous not in (None, 0) else None
    return {
        "code": code,
        "label": label,
        "series_code": symbol,
        "unit": unit,
        "source": "yahoo_stored" if rows else "unavailable",
        "as_of": rows[-1].period if rows else None,
        "updated_at": None,
        "current": current,
        "previous_close": previous,
        "change": change,
        "change_rate": change_rate,
        "points": points,
        "market_session": "closed",
        "is_realtime": False,
    }


def build_stored_global_market_assets(db: Session, *, limit: int = 30) -> dict[str, object]:
    safe_limit = max(2, min(int(limit), 120))
    return {
        "items": [
            _stored_asset(
                db,
                code=code,
                label=label,
                symbol=symbol,
                unit=unit,
                limit=safe_limit,
            )
            for code, label, symbol, unit in GLOBAL_MARKET_DEFINITIONS
        ]
    }


def _fetch_yahoo_chart(symbol: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for template in YAHOO_CHART_URLS:
        try:
            response = requests.get(
                template.format(symbol=symbol),
                params={"range": "5d", "interval": "15m", "includePrePost": "true"},
                headers=YAHOO_HEADERS,
                timeout=8,
            )
            response.raise_for_status()
            result = (((response.json().get("chart") or {}).get("result") or [None])[0])
            if result:
                return result
        except Exception as exc:  # pragma: no cover - provider fallback is environment dependent
            last_error = exc
    if last_error:
        raise last_error
    return {}


def _live_asset(definition: tuple[str, str, str, str], now: datetime) -> dict[str, object]:
    code, label, symbol, unit = definition
    result = _fetch_yahoo_chart(symbol)
    meta = result.get("meta") or {}
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0]) or {}
    closes = quote.get("close") or []
    values = [
        (int(timestamp), _number(close))
        for timestamp, close in zip(timestamps, closes)
        if _number(close) is not None
    ]
    current = _number(meta.get("regularMarketPrice"))
    if current is None and values:
        current = values[-1][1]
    previous = _number(meta.get("previousClose"))
    if previous is None:
        previous = _number(meta.get("chartPreviousClose"))
    change = current - previous if current is not None and previous is not None else None
    change_rate = change / previous * 100 if change is not None and previous not in (None, 0) else None
    period = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    now_epoch = int(now.timestamp())
    regular_start = int(period["start"]) if period.get("start") else None
    regular_end = int(period["end"]) if period.get("end") else None
    is_realtime = bool(
        regular_start is not None
        and regular_end is not None
        and regular_start <= now_epoch <= regular_end
    )
    is_preopen = bool(
        unit == "index"
        and regular_start is not None
        and regular_start - 2 * 60 * 60 <= now_epoch < regular_start
    )
    market_session = "open" if is_realtime else "preopen" if is_preopen else "closed"
    updated_epoch = int(meta.get("regularMarketTime") or (values[-1][0] if values else now_epoch))
    updated_at = datetime.fromtimestamp(updated_epoch, tz=timezone.utc).isoformat(timespec="minutes")
    points = [
        {"date": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="minutes"), "value": value}
        for timestamp, value in values[-36:]
    ]
    return {
        "code": code,
        "label": label,
        "series_code": symbol,
        "unit": unit,
        "source": "yahoo",
        "as_of": updated_at,
        "updated_at": updated_at,
        "current": current,
        "previous_close": previous,
        "change": change,
        "change_rate": change_rate,
        "points": points,
        "market_session": market_session,
        "is_realtime": is_realtime,
    }


def fetch_live_global_market_assets(*, now: datetime | None = None) -> list[dict[str, object]]:
    observed_at = now or datetime.now(timezone.utc)
    items: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=len(GLOBAL_MARKET_DEFINITIONS)) as executor:
        futures = {
            executor.submit(_live_asset, definition, observed_at): definition[0]
            for definition in GLOBAL_MARKET_DEFINITIONS
        }
        for future in as_completed(futures):
            try:
                items[futures[future]] = future.result()
            except Exception:
                continue
    return [items[definition[0]] for definition in GLOBAL_MARKET_DEFINITIONS if definition[0] in items]


def merge_global_market_assets(
    stored_payload: dict[str, object],
    live_items: list[dict[str, object]],
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    new_york_now = observed_at.astimezone(NEW_YORK_TZ)
    fallback_preopen = (
        new_york_now.weekday() < 5
        and time(7, 30) <= new_york_now.time() < time(9, 30)
    )
    live_by_code = {str(item.get("code")): item for item in live_items}
    merged: list[dict[str, object]] = []
    for stored_item in stored_payload.get("items", []):
        live_item = live_by_code.get(str(stored_item.get("code")))
        if live_item:
            merged.append(live_item)
            continue
        item = dict(stored_item)
        if fallback_preopen and item.get("unit") == "index":
            item["market_session"] = "preopen"
            item["is_realtime"] = False
        merged.append(item)
    timestamps = [str(item.get("updated_at")) for item in merged if item.get("updated_at")]
    return {"items": merged, "updated_at": max(timestamps) if timestamps else None}
