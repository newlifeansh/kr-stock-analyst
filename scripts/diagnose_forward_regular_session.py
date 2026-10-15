"""Read-only production diagnostic for the forward regular-session cohort.

This script intentionally mirrors ``collect_forward_session`` while disabling
persistence.  Its JSON output contains only stock codes, session dates, and
sanitized failure categories already permitted by the collector report.
"""
from __future__ import annotations

from datetime import datetime
import json
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.collectors.briefing import KisRestBriefingProvider
from app.config import get_settings
from app.db import SessionLocal
from app.models import DailyPrice
from app.services import quant_signals as qs
from app.services.regular_session_prices import collect_regular_session_prices
from app.services.regular_signal_transition import (
    REGULAR_FORWARD_START,
    REGULAR_FORWARD_VERSION,
    _load,
)


def main() -> None:
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    completed = qs.latest_completed_korea_market_session_date(now)
    if (
        now.hour * 60 + now.minute >= 15 * 60 + 40
        and qs.is_korea_market_session_date(now.date(), now)
    ):
        completed = now.date()
    if completed is None or completed < REGULAR_FORWARD_START:
        raise RuntimeError("no completed forward regular session")

    with SessionLocal() as db:
        latest_rank_date = db.scalar(
            select(func.max(DailyPrice.trade_date)).where(DailyPrice.market_cap > 0)
        )
        codes = list(
            db.scalars(
                select(DailyPrice.code)
                .where(
                    DailyPrice.trade_date == latest_rank_date,
                    DailyPrice.market_cap > 0,
                )
                .order_by(DailyPrice.market_cap.desc())
                .limit(150)
            )
        )
        for days in (30, 90):
            codes.extend(
                qs._market_signal_retention_state(
                    db,
                    universe_limit=150,
                    limit=0,
                    recent_days=days,
                )
            )
        cohort = _load(db, f"{REGULAR_FORWARD_VERSION}:shadow-cohort:100")
        if cohort:
            codes.extend(cohort["codes"])
        selected = sorted(set(codes))
        report = collect_regular_session_prices(
            db,
            KisRestBriefingProvider(get_settings()),
            codes=selected,
            start=REGULAR_FORWARD_START,
            end=completed,
            observed_at=now,
            persist=False,
            max_pairs=250,
        )

    print(
        json.dumps(
            {
                "observed_at": now.isoformat(),
                "latest_rank_date": (
                    latest_rank_date.isoformat() if latest_rank_date else None
                ),
                "cohort_size": len(selected),
                "report": report,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
