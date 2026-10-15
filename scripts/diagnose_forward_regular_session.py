"""Read-only production diagnostic for the forward regular-session cohort.

This script intentionally mirrors ``collect_forward_session`` while disabling
persistence.  Its JSON output contains only stock codes, session dates, and
sanitized failure categories already permitted by the collector report.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
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
        provider = KisRestBriefingProvider(get_settings())
        report = collect_regular_session_prices(
            db,
            provider,
            codes=selected,
            start=REGULAR_FORWARD_START,
            end=completed,
            observed_at=now,
            persist=False,
            max_pairs=250,
        )

        source_shapes = []
        for failure in report["unverified"]:
            code = failure["code"]
            trade_date = date.fromisoformat(failure["trade_date"])
            source = provider.fetch_regular_session_data(code, trade_date)
            regular = {
                str(row.get("trade_time") or "").zfill(6): row
                for row in source["rows"]
                if "090000" <= str(row.get("trade_time") or "").zfill(6) <= "153000"
            }
            expected_prefix = []
            instant = datetime.combine(trade_date, datetime.min.time()).replace(
                hour=9
            )
            while instant.strftime("%H%M%S") <= "151900":
                expected_prefix.append(instant.strftime("%H%M%S"))
                instant += timedelta(minutes=1)
            positive_prefix = [
                stamp
                for stamp in expected_prefix
                if stamp in regular and int(regular[stamp].get("volume") or 0) > 0
            ]
            zero_prefix = [
                stamp
                for stamp in expected_prefix
                if stamp in regular and int(regular[stamp].get("volume") or 0) == 0
            ]
            closing = regular.get("153000")
            naver = source.get("closing_auction_evidence") or {}
            buckets = (naver.get("priceInfos") or {}).get(
                trade_date.strftime("%Y%m%d")
            ) or []
            source_shapes.append(
                {
                    "code": code,
                    "trade_date": trade_date.isoformat(),
                    "source_row_count": len(source["rows"]),
                    "missing_prefix_times": [
                        stamp for stamp in expected_prefix if stamp not in regular
                    ],
                    "zero_volume_prefix_times": zero_prefix,
                    "first_positive_prefix_time": (
                        positive_prefix[0] if positive_prefix else None
                    ),
                    "last_positive_prefix_time": (
                        positive_prefix[-1] if positive_prefix else None
                    ),
                    "closing_row_present": closing is not None,
                    "closing_row_positive": bool(
                        closing and int(closing.get("volume") or 0) > 0
                    ),
                    "naver_bucket_times": [
                        str(bucket.get("localDateTime") or "")[-6:]
                        for bucket in buckets
                    ],
                    "preopen_baseline_kind": (
                        source.get("preopen_baseline") or {}
                    ).get("kind"),
                }
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
                "source_shapes": source_shapes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
