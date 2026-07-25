from __future__ import annotations

from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import MacroObservation


INDEX_DEFINITIONS = (
    ("KOSPI", "코스피", "^KS11"),
    ("KOSDAQ", "코스닥", "^KQ11"),
)


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
