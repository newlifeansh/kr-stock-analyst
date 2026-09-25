from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import re
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx

from app.services.economic_calendar import (
    BLS_MARKET_RELEASE_TITLES,
    BLS_RELEASE_CALENDAR_URL,
    bls_market_releases_between,
)
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


async def build_us_market_calendar(
    *,
    days: int = 16,
    now: Optional[datetime] = None,
) -> dict[str, object]:
    if not 1 <= int(days) <= 31:
        raise ValueError("days must be between 1 and 31")
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    current = current.astimezone(KST)
    window_start = current - timedelta(days=2)
    window_end = current + timedelta(days=int(days))
    try:
        releases = await asyncio.to_thread(
            bls_market_releases_between,
            window_start.replace(tzinfo=None),
            window_end.replace(tzinfo=None),
        )
    except Exception as exc:
        raise DashboardMarketDataError("US market calendar source failed") from exc
    titles = {key: title for key, title in BLS_MARKET_RELEASE_TITLES.values()}
    rows = [
        {
            "id": f"{key}-{starts_at:%Y%m%d%H%M}",
            "starts_at": starts_at.replace(tzinfo=KST).isoformat(),
            "title": titles[key],
            "category": "미국",
            "source_name": "U.S. Bureau of Labor Statistics",
            "source_url": BLS_RELEASE_CALENDAR_URL,
            "expected_impact": "미국 금리와 주식시장에 영향을 줄 수 있는 주요 경제지표 발표",
            "timeline": [],
        }
        for key, starts_at in releases
    ]
    return {
        "as_of": current.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "events": [row for row in rows if datetime.fromisoformat(row["starts_at"]) >= current],
        "past_events": [row for row in reversed(rows) if datetime.fromisoformat(row["starts_at"]) < current],
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
