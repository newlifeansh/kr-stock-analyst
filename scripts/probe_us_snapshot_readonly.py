"""Read US collector configuration and snapshot state without rebuilding it."""
import json
from datetime import datetime, timezone
from sqlalchemy import text
from app.config import get_settings
from app.db import SessionLocal
from app.services.us_market_calendar import us_signal_session_state
from app.services.us_position_lifecycle import (
    load_us_position_lifecycle_snapshot,
    us_position_lifecycle_refresh_due,
    us_position_lifecycle_schema_upgrade_due,
)

current = datetime.now(timezone.utc)
settings = get_settings()
with SessionLocal() as db:
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL read-only transaction required")
    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    payload = load_us_position_lifecycle_snapshot(db, now=current)
    state = us_signal_session_state(current)
    print(json.dumps({
        "observed_at": current.isoformat(),
        "transaction_read_only": db.scalar(text("SHOW transaction_read_only")),
        "process_role": settings.process_role,
        "runs_collectors": settings.runs_collectors(),
        "us_market_enabled": settings.us_market_enabled,
        "refresh_allowed": state["refresh_allowed"],
        "refresh_due": us_position_lifecycle_refresh_due(payload, now=current),
        "schema_upgrade_due": us_position_lifecycle_schema_upgrade_due(payload),
        "status": (payload or {}).get("status"),
        "data_state": (payload or {}).get("data_state"),
        "snapshot_generated_at": (payload or {}).get("snapshot_generated_at"),
        "has_performance_summary": isinstance((payload or {}).get("performance_summary"), dict),
        "writes": 0,
        "notifications_sent": 0,
    }, default=str))
    db.rollback()
