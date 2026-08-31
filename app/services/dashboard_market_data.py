from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import re
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx

from app.services.trends import scheduled_calendar_events_between


KST = ZoneInfo("Asia/Seoul")
WEEK_CHART_TIMEOUT_SECONDS = 25.0
STOCK_CODE_PATTERN = re.compile(r"^[0-9]{6}$")


class DashboardMarketDataError(RuntimeError):
    """Raised when a public dashboard data source cannot return a valid payload."""


def _serialize_calendar_event(item: dict[str, object]) -> dict[str, object]:
    starts_at = item.get("starts_at")
    if not isinstance(starts_at, datetime):
        raise DashboardMarketDataError("calendar event is missing starts_at")
    return {
        **{key: value for key, value in item.items() if not key.startswith("_")},
        "starts_at": starts_at.isoformat(),
        "timeline": [],
    }


async def build_korea_market_calendar(
    *,
    days: int = 14,
    now: Optional[datetime] = None,
) -> dict[str, object]:
    if not 1 <= int(days) <= 31:
        raise ValueError("days must be between 1 and 31")

    current = now or datetime.now(KST).replace(tzinfo=None)
    if current.tzinfo is not None:
        current = current.astimezone(KST).replace(tzinfo=None)
    window_start = current - timedelta(days=14)
    window_end = current + timedelta(days=int(days))
    try:
        rows = await asyncio.to_thread(
            scheduled_calendar_events_between,
            window_start,
            window_end,
            categories={"한국"},
        )
        upcoming = [
            _serialize_calendar_event(item)
            for item in rows
            if item.get("starts_at") >= current
        ]
        past = [
            _serialize_calendar_event(item)
            for item in reversed(rows)
            if item.get("starts_at") < current
        ]
    except DashboardMarketDataError:
        raise
    except Exception as exc:
        raise DashboardMarketDataError("korea market calendar source failed") from exc

    return {
        "as_of": current.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "events": upcoming,
        "past_events": past,
    }


async def fetch_stock_week_chart(code: str) -> dict[str, Any]:
    normalized_code = str(code or "").strip()
    if STOCK_CODE_PATTERN.fullmatch(normalized_code) is None:
        raise ValueError("stock code must contain exactly six digits")

    url = (
        "https://api.stock.naver.com/chart/domestic/item/"
        f"{normalized_code}?periodType=week"
    )
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=WEEK_CHART_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "SecretNote-Dashboard-Week-Chart/1.0",
                },
            )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise DashboardMarketDataError("stock week chart source failed") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("priceInfos"), dict):
        raise DashboardMarketDataError("week chart payload is missing priceInfos")
    return payload
