from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import MacroObservation


INDEX_DEFINITIONS = (
    ("KOSPI", "코스피", "^KS11"),
    ("KOSDAQ", "코스닥", "^KQ11"),
)

KST = ZoneInfo("Asia/Seoul")


def empty_market_indices() -> dict[str, object]:
    return {
        "items": [
            {
                "code": code,
                "label": label,
                "series_code": series_code,
                "source": "unavailable",
                "as_of": None,
                "current": None,
                "previous_close": None,
                "change": None,
                "change_rate": None,
                "points": [],
            }
            for code, label, series_code in INDEX_DEFINITIONS
        ]
    }


def _number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _index_payload(
    db: Session,
    *,
    code: str,
    label: str,
    series_code: str,
    limit: int,
) -> dict[str, object]:
    rows = list(
        db.scalars(
            select(MacroObservation)
            .where(MacroObservation.source == "yahoo")
            .where(MacroObservation.series_code == series_code)
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
    latest = rows[-1] if rows else None
    previous = rows[-2] if len(rows) > 1 else None
    latest_value = latest.value if latest else None
    previous_value = previous.value if previous else None
    change = latest_value - previous_value if latest_value is not None and previous_value is not None else None
    change_rate = (
        change / previous_value * Decimal("100")
        if change is not None and previous_value not in (None, Decimal("0"))
        else None
    )
    return {
        "code": code,
        "label": label,
        "series_code": series_code,
        "source": latest.source if latest else "yahoo",
        "as_of": latest.period if latest else None,
        "current": _number(latest_value),
        "previous_close": _number(previous_value),
        "change": _number(change),
        "change_rate": _number(change_rate),
        "points": points,
    }


def build_market_indices(db: Session, *, limit: int = 30) -> dict[str, object]:
    safe_limit = max(2, min(int(limit), 120))
    return {
        "items": [
            _index_payload(
                db,
                code=code,
                label=label,
                series_code=series_code,
                limit=safe_limit,
            )
            for code, label, series_code in INDEX_DEFINITIONS
        ]
    }


def latest_korean_market_date(now: datetime | None = None) -> str:
    local = now or datetime.now(KST)
    if local.tzinfo is None:
        local = local.replace(tzinfo=KST)
    local = local.astimezone(KST)
    candidate = local.date()
    if local.time() < time(9, 0):
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.isoformat()


def korean_market_session(now: datetime | None = None) -> str:
    local = now or datetime.now(KST)
    if local.tzinfo is None:
        local = local.replace(tzinfo=KST)
    local = local.astimezone(KST)
    if local.weekday() >= 5:
        return "closed"
    if time(7, 0) <= local.time() < time(9, 0):
        return "preopen"
    return "open" if time(9, 0) <= local.time() < time(15, 30) else "closed"


def merge_live_market_indices(
    stored_payload: dict[str, object],
    live_snapshots: list[dict[str, object]],
    *,
    as_of: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    live_by_code = {str(item.get("code")): item for item in live_snapshots}
    local_now = now or datetime.now(KST)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=KST)
    local_now = local_now.astimezone(KST)
    basis_date = as_of or latest_korean_market_date(local_now)
    updated_at = local_now.isoformat(timespec="seconds")
    market_session = korean_market_session(local_now)
    merged_items: list[dict[str, object]] = []

    for stored_item in stored_payload.get("items", []):
        item = dict(stored_item)
        live = live_by_code.get(str(item.get("code")))
        if not live or live.get("current") is None:
            merged_items.append(item)
            continue

        current = _number(live.get("current"))
        previous_close = _number(live.get("previous_close"))
        change = _number(live.get("change"))
        change_rate = _number(live.get("change_rate"))
        points = [
            dict(point)
            for point in item.get("points", [])
            if point.get("date") != basis_date
        ]
        points.append({"date": basis_date, "value": current})

        item.update(
            {
                "source": live.get("source") or "kis",
                "as_of": basis_date,
                "current": current,
                "previous_close": previous_close,
                "change": change,
                "change_rate": change_rate,
                "points": points,
                "is_live": True,
                "is_realtime": market_session == "open",
                "market_session": market_session,
                "updated_at": updated_at,
            }
        )
        merged_items.append(item)

    return {
        "items": merged_items,
        "source": "kis",
        "market_session": market_session,
        "updated_at": updated_at,
    }
