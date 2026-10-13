"""Inspect only currently blocked forward-cohort inputs; never mutate baselines."""
import json
from datetime import datetime, timezone
from sqlalchemy import select, text
from app.db import SessionLocal
from app.models import DailyPrice, MarketQuantSignalSnapshot, SignalSessionPrice
from app.services.regular_signal_transition import REGULAR_FORWARD_START, REGULAR_FORWARD_VERSION, _load
from app.services.quant_signals import _normalize_prices, SIGNAL_HISTORY_ROWS

with SessionLocal() as db:
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL read-only transaction required")
    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    snapshot = db.get(MarketQuantSignalSnapshot, "v37:150:0:30")
    payload = json.loads(snapshot.payload) if snapshot else {}
    result = []
    for code in (payload.get("execution_replay_unverified_codes") or [])[:30]:
        rows = list(reversed(list(db.scalars(select(DailyPrice).where(
            DailyPrice.code == code, DailyPrice.trade_date < REGULAR_FORWARD_START,
        ).order_by(DailyPrice.trade_date.desc()).limit(SIGNAL_HISTORY_ROWS)))))
        bars = _normalize_prices(rows)
        last_bad = max((i for i, bar in enumerate(bars) if not bar.ohlc_complete), default=-1)
        frozen = _load(db, f"{REGULAR_FORWARD_VERSION}:prices:{code}")
        result.append({
            "code": code,
            "legacy_rows": len(rows),
            "last_date": rows[-1].trade_date if rows else None,
            "last_incomplete_date": bars[last_bad].trade_date if last_bad >= 0 else None,
            "complete_tail_rows": len(bars[last_bad + 1:]),
            "frozen_baseline_exists": frozen is not None,
            "frozen_rows": len(frozen) if isinstance(frozen, list) else None,
            "regular_evidence": [{"date": str(record.trade_date), "state": record.state,
                "payload": json.loads(record.payload)} for record in db.scalars(select(SignalSessionPrice).where(
                    SignalSessionPrice.code == code, SignalSessionPrice.trade_date >= REGULAR_FORWARD_START,
                ).order_by(SignalSessionPrice.id.desc()).limit(1))],
        })
    print(json.dumps({
        "observed_at": datetime.now(timezone.utc),
        "transaction_read_only": db.scalar(text("SHOW transaction_read_only")),
        "snapshot_generated_at": payload.get("snapshot_generated_at"),
        "blocked_count": payload.get("execution_replay_unverified_count"),
        "items": result, "writes": 0, "notifications_sent": 0,
    }, default=str))
    db.rollback()
