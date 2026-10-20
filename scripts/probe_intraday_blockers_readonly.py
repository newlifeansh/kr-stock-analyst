"""Diagnose domestic evidence blockers in a PostgreSQL read-only transaction."""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app.db import SessionLocal
from app.models import DailyPrice, MarketQuantSignalSnapshot, QuantSignalIntradayPathSnapshot, StockMaster
from app.services import quant_signals as qs
from app.services.regular_signal_transition import (
    REGULAR_FORWARD_START, REGULAR_FORWARD_VERSION, _load, forward_price_envelope,
)
from app.services.regular_price_replay import regular_ordered_paths
from app.services.regular_session_prices import load_regular_session_evidence, _session_dates
from app.services.signal_entry_evidence import load_entry_evidence_timeline


def prefix_comparison(previous, current):
    differences = []
    fields = ("trade_date", "trade_time", "open", "high", "low", "price")
    for index, (old, new) in enumerate(zip(previous, current)):
        changed = {key: [old.get(key), new.get(key)] for key in fields
                   if (str(old.get(key)) != str(new.get(key)) if key in fields[:2]
                       else qs._safe_number(old.get(key)) != qs._safe_number(new.get(key)))}
        if changed:
            differences.append({"index": index, "differences": changed})
    return {
        "prior_count": len(previous), "current_count": len(current),
        "preserved": qs._intraday_path_preserves_prior_touches(previous, current),
        "changed_count": len(differences), "first_differences": differences[:4],
    }


now = datetime.now(ZoneInfo("Asia/Seoul"))
with SessionLocal() as db:
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL read-only transaction required")
    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    db.execute(text("SET LOCAL statement_timeout = '30s'"))
    snapshot = db.get(MarketQuantSignalSnapshot, qs.market_quant_signal_snapshot_key(150, 0, 30))
    feed = json.loads(snapshot.payload) if snapshot else {}
    blocked = feed.get("execution_replay_unverified_codes") or []
    codes = list(dict.fromkeys(["068270", "032640", "000100"] + blocked))
    results = []
    completed = qs.latest_completed_korea_market_session_date(now)
    for code in codes:
        stock = db.get(StockMaster, code)
        item = {"code": code, "name": stock.name if stock else None}
        rows = list(reversed(list(db.scalars(select(DailyPrice).where(
            DailyPrice.code == code, DailyPrice.trade_date <= completed,
        ).order_by(DailyPrice.trade_date.desc()).limit(qs.SIGNAL_HISTORY_ROWS)))))
        baseline = _load(db, f"{REGULAR_FORWARD_VERSION}:prices:{code}")
        item["baseline_rows"] = len(baseline) if baseline is not None else 0
        item["sessions"] = []
        for day in _session_dates(REGULAR_FORWARD_START, completed):
            session = {"date": day.isoformat()}
            try:
                evidence = load_regular_session_evidence(db, code, day, allow_bounded=True)
                session.update(state=evidence["state"], points=len(evidence["regular_rows"]))
                path = db.get(QuantSignalIntradayPathSnapshot, (code, day))
                if path:
                    prior = json.loads(path.payload)
                    current = [r for r in evidence["regular_rows"] if not qs._non_trade_closing_auction_row(r)]
                    session["stored_path"] = {
                        "is_final": path.is_final, "strategy": path.strategy_version,
                        "observed_at": path.observed_at,
                        **prefix_comparison(prior, current),
                    }
            except Exception as exc:
                session.update(state="error", error_type=type(exc).__name__, reason=str(exc))
            item["sessions"].append(session)
        if baseline is None:
            item["forward_error"] = "frozen_baseline_missing; no write attempted"
            results.append(item)
            continue
        try:
            envelope = forward_price_envelope(db, code, rows, completed_through=completed)
            paths = regular_ordered_paths(envelope)
            item["forward_envelope"] = "ready"
            if code in {"068270", "032640", "000100"}:
                timeline = load_entry_evidence_timeline(db, code, strategy_version=qs.STRATEGY_VERSION)
                timeline = {day: value for day, value in timeline.items()
                            if day >= REGULAR_FORWARD_START}
                for cutoff in _session_dates(REGULAR_FORWARD_START, completed)[-2:]:
                    selected = [r for r in envelope.lower if r.trade_date <= cutoff]
                    payload = qs.build_quant_signal_payload(
                        stock, selected, now=now, entry_evidence_by_date=timeline,
                        historical_intraday_minutes_by_date={d: v for d, v in paths.items() if d <= cutoff},
                        lifecycle_start_date=REGULAR_FORWARD_START,
                    )
                    item.setdefault("replay", []).append({
                        "through": cutoff, "current": payload.get("current"),
                        "events": payload.get("events"), "performance": payload.get("performance"),
                        "notice": "diagnostic only; bypasses stored-prefix comparison; cannot authorize publication",
                    })
        except Exception as exc:
            item.update(forward_error=str(exc), error_type=type(exc).__name__)
        results.append(item)
    report = {
        "observed_at": datetime.now(timezone.utc),
        "transaction_read_only": db.scalar(text("SHOW transaction_read_only")),
        "snapshot_generated_at": snapshot.generated_at if snapshot else None,
        "blocked_codes": blocked, "items": results,
        "writes": 0, "notifications_sent": 0,
    }
    db.rollback()
print(json.dumps(report, ensure_ascii=False, default=str))
