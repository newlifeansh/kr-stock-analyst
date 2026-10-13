"""Read US collector configuration and snapshot state without rebuilding it."""
import json
from datetime import datetime, timezone
from sqlalchemy import text, select, func
from app.models import PushSubscription, PushDelivery
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
    hybrid_state = None
    try:
        from app.services.us_hybrid_signals import read_us_hybrid_state
        hybrid_state = read_us_hybrid_state(db)
    except ImportError:
        pass
    hybrid_summary = None
    if hybrid_state:
        observations = hybrid_state.get("observations", {})
        quality_counts = {}
        for observation in observations.values():
            quality = str(observation.get("state"))
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
        hybrid_summary = {
            "version": hybrid_state.get("version"),
            "initialized_at": hybrid_state.get("initialized_at"),
            "updated_at": hybrid_state.get("updated_at"),
            "revision": hybrid_state.get("revision"),
            "setup_date": hybrid_state.get("setup_date"),
            "eligible_count": sum(bool(item.get("eligible")) for item in hybrid_state.get("setups", {}).values()),
            "events_count": len(hybrid_state.get("events", [])),
            "open_positions": sum(item.get("remaining", 0) > 0 for item in hybrid_state.get("positions", {}).values()),
            "observation_states": quality_counts,
            "observations": [{"code": code, "state": item.get("state"), "observed_at": item.get("observed_at"), "checked_at": item.get("checked_at"), "price": item.get("price")} for code, item in observations.items()],
        }
    delivery_counts = dict(db.execute(select(PushDelivery.status, func.count()).where(
        PushDelivery.event_key.like("us-hybrid-v1:%")
    ).group_by(PushDelivery.status)).all())
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
        "hybrid_setup_count": len((payload or {}).get("hybrid_setups") or []),
        "hybrid": hybrid_summary,
        "push_configured": bool(settings.web_push_enabled and settings.web_push_vapid_private_key and settings.web_push_vapid_public_key),
        "push_poll_seconds": settings.web_push_poll_seconds,
        "enabled_subscription_count": db.scalar(select(func.count()).select_from(PushSubscription).where(PushSubscription.enabled.is_(True))),
        "hybrid_delivery_counts": delivery_counts,
        "writes": 0,
        "notifications_sent": 0,
    }, default=str))
    db.rollback()
