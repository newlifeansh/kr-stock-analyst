"""Closed-session Korean returns from one split-adjusted price series per listing."""
from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import re
from threading import local
from xml.etree import ElementTree

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StockMaster
from app.services.complete_snapshots import get, request_refresh
from app.services.market_calendar import (
    is_scheduled_korea_market_session_date,
    krx_session_hours,
    preceding_korea_session,
)
from app.services.stock_dashboard import _rate

PERIOD_RANKING_KEY = "kr-adjusted-period-returns:v1"
KST = timezone(timedelta(hours=9))
CHART_URL = "https://fchart.stock.naver.com/sise.nhn"
_connections = local()


def market_close(day: date) -> datetime:
    return datetime.combine(day, krx_session_hours(day).at(15, 30), tzinfo=KST)


def completed_session(now: datetime) -> date:
    local_now = now.astimezone(KST)
    day = local_now.date()
    if local_now <= market_close(day):
        day -= timedelta(days=1)
    for _ in range(31):
        if is_scheduled_korea_market_session_date(day):
            return day
        day -= timedelta(days=1)
    raise ValueError("KRX calendar has no recent session")


def _fetch_chart(code: str) -> bytes:
    if not hasattr(_connections, "session"):
        session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=(429, 502, 503, 504))
        session.mount("https://", HTTPAdapter(max_retries=retry))
        _connections.session = session
    response = _connections.session.get(
        CHART_URL,
        params={"symbol": code, "timeframe": "day", "count": 40, "requestType": "0"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    response.raise_for_status()
    return response.content


def chart_closes(raw: bytes, code: str, dates: set[str]) -> dict[str, int]:
    root = ElementTree.fromstring(raw.strip().decode("euc-kr").split("?>", 1)[-1])
    if root.tag != "protocol":
        raise ValueError("Unexpected adjusted chart response")
    chart = root.find("chartdata")
    if chart is None:
        return {}
    if chart.get("symbol") != code or chart.get("timeframe") != "day":
        raise ValueError("Unexpected adjusted chart identity")
    closes = {}
    for item in chart.findall("item"):
        fields = (item.get("data") or "").split("|")
        if fields[0] not in dates:
            continue
        if len(fields) < 5 or not fields[4].isdigit() or fields[0] in closes:
            raise ValueError("Invalid dated adjusted close")
        if int(fields[4]) > 0:
            closes[fields[0]] = int(fields[4])
    return closes


def collect_period_closes(stocks: Sequence[tuple[str, str, str]], session_day: date) -> dict:
    dates = [session_day, *(preceding_korea_session(session_day, n) for n in (1, 5, 21))]
    if any(day is None for day in dates):
        raise ValueError("Missing KRX period baseline")
    latest, previous, week, month = [day.strftime("%Y%m%d") for day in dates]
    required_dates = {latest, previous, week, month}

    def collect(stock):
        code, name, market = stock
        closes = chart_closes(_fetch_chart(code), code, required_dates)
        if latest not in closes:
            return None
        return [code, name, market, closes[latest], closes.get(previous), closes.get(week), closes.get(month)]

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = [row for row in pool.map(collect, stocks) if row is not None]
    if not rows or len(rows) < len(stocks) * 0.9:
        raise ValueError(f"Incomplete adjusted market close coverage: {len(rows)}/{len(stocks)}")
    return {"trade_date": session_day.isoformat(), "universe_count": len(stocks), "rows": rows}


def build_period_snapshot(db: Session, session_day: date) -> dict:
    stocks = db.execute(
        select(StockMaster.code, StockMaster.name, StockMaster.market)
        .where(StockMaster.is_active.is_(True), StockMaster.market.in_(("KOSPI", "KOSDAQ")))
        .order_by(StockMaster.code)
    ).all()
    listings = [(code, name, market) for code, name, market in stocks if re.fullmatch(r"[0-9A-Z]{6}", code)]
    return collect_period_closes(listings, session_day)


def period_rankings(snapshot: dict, market: str | None, mode: str, limit: int) -> dict:
    trade_date = date.fromisoformat(snapshot["trade_date"])
    eligible = 0
    items = []
    for code, name, exchange, close, prior, week, month in snapshot["rows"]:
        if market and exchange != market.upper():
            continue
        baseline = week if mode == "week" else month
        if not baseline:
            continue
        eligible += 1
        change = _rate(close, baseline)
        if change is None or change <= Decimal(0):
            continue
        items.append({
            "code": code, "name": name, "market": exchange, "price": close,
            "trade_date": trade_date, "change_rate": _rate(close, prior),
            "one_week_return": _rate(close, week), "one_month_return": _rate(close, month),
            "category": "surge", "metric_value": change,
        })
    items.sort(key=lambda item: (-item["metric_value"], item["code"]))
    ranked = items[:limit]
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return {
        "category": "surge", "mode": mode, "market": market,
        "as_of": market_close(trade_date), "source": "naver_adjusted_close",
        "matching_count": len(items), "universe_count": eligible, "items": ranked,
    }


def read_period_rankings(db: Session | None, market: str | None, mode: str, limit: int) -> dict:
    snapshot = get(db, PERIOD_RANKING_KEY) if db is not None else None
    if db is not None and (snapshot is None or not snapshot.is_fresh):
        request_refresh(db, PERIOD_RANKING_KEY)
    if snapshot is not None:
        return period_rankings(snapshot.payload, market, mode, limit)
    return {
        "category": "surge", "mode": mode, "market": market, "source": "unavailable",
        "as_of": datetime.now(KST), "items": [], "universe_count": 0, "matching_count": 0,
    }
