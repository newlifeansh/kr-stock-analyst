from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.briefing import (
    BriefingBundle,
    BriefingEventPayload,
    BriefingMetricPayload,
    BriefingMoverPayload,
    BriefingQuotePayload,
    persist_briefing_bundle,
)
from app.db import Base
from app.models import BriefingEvent, BriefingMover, BriefingQuote, BriefingSnapshot


def test_persist_briefing_bundle_in_memory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    bundle = BriefingBundle(
        briefing_kind="home",
        source="test",
        transport="polling",
        market_status="open",
        is_live=True,
        as_of=datetime(2026, 6, 17, 9, 1, 0),
        summary="watchlist=1 movers=1 disclosures=1",
        metrics=[
            BriefingMetricPayload(
                metric_key="market_status",
                label="장 상태",
                value_text="open",
                sort_order=0,
            )
        ],
        quotes=[
            BriefingQuotePayload(
                code="005930",
                name="삼성전자",
                market="KOSPI",
                role="watchlist",
                price=Decimal("81200"),
                change_rate=Decimal("1.23"),
            )
        ],
        movers=[
            BriefingMoverPayload(
                list_type="gainers",
                rank=1,
                code="000660",
                name="SK하이닉스",
                market="KOSPI",
                price=Decimal("250000"),
                change_rate=Decimal("3.45"),
            )
        ],
        events=[
            BriefingEventPayload(
                event_type="disclosure",
                source="dart",
                title="주요사항보고서",
                company_name="삼성전자",
            )
        ],
    )

    with SessionLocal() as db:
        snapshot = persist_briefing_bundle(db, bundle)

        assert snapshot.id == 1
        assert db.scalar(select(func.count()).select_from(BriefingSnapshot)) == 1
        assert db.scalar(select(func.count()).select_from(BriefingQuote)) == 1
        assert db.scalar(select(func.count()).select_from(BriefingMover)) == 1
        assert db.scalar(select(func.count()).select_from(BriefingEvent)) == 1
