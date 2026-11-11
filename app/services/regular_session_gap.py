"""Expose independently verified prices while a dated signal path is quarantined."""
from __future__ import annotations

from datetime import date

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models import SignalSessionPrice
from app.services.regular_session_prices import (
    REGULAR_PRICE_BASIS,
    UnverifiedRegularSessionPrice,
    load_regular_session_evidence,
)


def verified_sessions_around_gap(
    db: Session, code: str, gap_date: date, *, limit: int = 5,
) -> list[dict[str, int | str]]:
    """Return only revalidated KRX candles; never infer a trade or position."""
    if not inspect(db.connection()).has_table(SignalSessionPrice.__tablename__):
        return []
    candidate_dates = db.scalars(
        select(SignalSessionPrice.trade_date)
        .where(
            SignalSessionPrice.code == code,
            SignalSessionPrice.trade_date != gap_date,
            SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS,
            SignalSessionPrice.state.in_(("ready", "bounded")),
        )
        .distinct()
        .order_by(SignalSessionPrice.trade_date.desc())
        .limit(max(1, min(limit * 3, 30)))
    )
    result: list[dict[str, int | str]] = []
    for day in candidate_dates:
        try:
            evidence = load_regular_session_evidence(db, code, day, allow_bounded=True)
        except UnverifiedRegularSessionPrice:
            continue
        prices = evidence["prices"]
        result.append({
            "trade_date": day.isoformat(),
            "open": int(prices["open"]),
            "high": int(prices["high"]),
            "low": int(prices["low"]),
            "close": int(prices["close"]),
            "volume": int(prices["volume"]),
        })
        if len(result) >= limit:
            break
    return result
