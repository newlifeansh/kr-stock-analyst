from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.collectors.krx import collect_stocks
from app.config import Settings, get_settings
from app.db import SessionLocal, init_db
from app.models import BriefingSnapshot, DisclosureItem, NewsItem, ResearchReport, StockMaster
from app.services.briefing import briefing_runtime

KST = ZoneInfo("Asia/Seoul")


def _bootstrap_target_date() -> str:
    return datetime.now(KST).strftime("%Y%m%d")


def _bootstrap_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "stocks": int(db.scalar(select(func.count()).select_from(StockMaster)) or 0),
            "briefings": int(db.scalar(select(func.count()).select_from(BriefingSnapshot)) or 0),
            "reports": int(db.scalar(select(func.count()).select_from(ResearchReport)) or 0),
            "disclosures": int(db.scalar(select(func.count()).select_from(DisclosureItem)) or 0),
            "news": int(db.scalar(select(func.count()).select_from(NewsItem)) or 0),
        }


def _needs_runtime_refresh(counts: dict[str, int], settings: Settings) -> bool:
    if counts["briefings"] == 0:
        return True
    if settings.research_enabled and counts["reports"] == 0:
        return True
    if settings.disclosure_enabled and counts["disclosures"] == 0:
        return True
    if settings.news_enabled and counts["news"] == 0:
        return True
    return False


def bootstrap_runtime_data(settings: Optional[Settings] = None, *, force_refresh: bool = False) -> dict[str, object]:
    settings = settings or get_settings()
    init_db()

    seeded_stocks = 0
    target_date = _bootstrap_target_date()
    counts_before = _bootstrap_counts()

    if counts_before["stocks"] == 0:
        with SessionLocal() as db:
            seeded_stocks = collect_stocks(db, target_date, "KOSPI,KOSDAQ")

    should_refresh = force_refresh or _needs_runtime_refresh(_bootstrap_counts(), settings)
    refreshed_runtime = False
    if should_refresh:
        briefing_runtime.run_once()
        refreshed_runtime = True

    counts_after = _bootstrap_counts()
    return {
        "target_date": target_date,
        "seeded_stocks": seeded_stocks,
        "refreshed_runtime": refreshed_runtime,
        "counts_before": counts_before,
        "counts_after": counts_after,
    }
