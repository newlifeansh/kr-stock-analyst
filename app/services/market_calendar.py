from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from app.services.ttl_cache import TTLCache


KST = ZoneInfo("Asia/Seoul")
NAVER_INDEX_CHART_URL = "https://fchart.stock.naver.com/sise.nhn"
MARKET_SESSION_CACHE = TTLCache(maxsize=2)
MARKET_SESSION_TTL_SECONDS = 60
INVESTOR_FLOW_READY_TIME = time(18, 0)


def _kst_datetime(value: Optional[datetime] = None) -> datetime:
    current = value or datetime.now(KST)
    if current.tzinfo is None:
        return current.replace(tzinfo=KST)
    return current.astimezone(KST)


def _parse_latest_market_session_date(payload: bytes, through: date) -> Optional[date]:
    dates: list[date] = []
    for raw in re.findall(rb'data="(\d{8})\|', payload):
        try:
            parsed = datetime.strptime(raw.decode("ascii"), "%Y%m%d").date()
        except (UnicodeDecodeError, ValueError):
            continue
        if parsed <= through:
            dates.append(parsed)
    return max(dates) if dates else None


def _fetch_latest_market_session_date(through: date) -> Optional[date]:
    response = requests.get(
        NAVER_INDEX_CHART_URL,
        params={"symbol": "KOSPI", "timeframe": "day", "count": "10", "requestType": "0"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8,
    )
    response.raise_for_status()
    return _parse_latest_market_session_date(response.content, through)


def latest_korea_market_session_date(now: Optional[datetime] = None) -> Optional[date]:
    current = _kst_datetime(now)
    try:
        return MARKET_SESSION_CACHE.get_or_set(
            ("latest_korea_market_session_date", current.date()),
            MARKET_SESSION_TTL_SECONDS,
            lambda: _fetch_latest_market_session_date(current.date()),
        )
    except Exception:
        return None


def latest_completed_korea_market_session_date(now: Optional[datetime] = None) -> Optional[date]:
    """Return the latest session whose end-of-day investor flow should exist.

    Naver's investor table does not expose the current session while trading is
    in progress.  Before its evening publication window, compare flow coverage
    with the latest session through yesterday instead of a potentially stale
    ``daily_price`` table or today's still-forming session.
    """
    current = _kst_datetime(now)
    through = current.date()
    if current.time() < INVESTOR_FLOW_READY_TIME:
        through -= timedelta(days=1)
    lookup_time = datetime.combine(through, time(23, 59, 59), tzinfo=KST)
    return latest_korea_market_session_date(lookup_time)


def is_korea_market_session_date(target: date, now: Optional[datetime] = None) -> bool:
    current = _kst_datetime(now)
    if target.weekday() >= 5 or target > current.date():
        return False
    return latest_korea_market_session_date(current) == target


def is_korea_regular_market_session(now: Optional[datetime] = None) -> bool:
    current = _kst_datetime(now)
    return (
        time(9, 0) <= current.time() <= time(15, 30)
        and is_korea_market_session_date(current.date(), current)
    )


def is_korea_daily_signal_window(now: Optional[datetime] = None) -> bool:
    current = _kst_datetime(now)
    return (
        time(15, 40) <= current.time() <= time(18, 0)
        and is_korea_market_session_date(current.date(), current)
    )
