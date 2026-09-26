from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import DisclosureItem
from app.services.stock_dashboard import GUIDANCE_WORDS, _disclosure_events


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_disclosure_events_can_fall_back_to_recent_general_filings():
    with _session() as db:
        db.add_all(
            [
                DisclosureItem(
                    source="dart",
                    external_id="20260925000001",
                    disclosure_category="filings",
                    company_name="삼성전자",
                    stock_code="005930",
                    report_name="풍문또는보도에대한해명(미확정)",
                    detail_url="https://broken.example/first",
                    published_at=datetime.utcnow() - timedelta(days=1),
                ),
                DisclosureItem(
                    source="dart",
                    external_id="20260924000002",
                    disclosure_category="insider_trade",
                    company_name="삼성전자",
                    stock_code="005930",
                    report_name="임원ㆍ주요주주특정증권등소유상황보고서",
                    detail_url="https://broken.example/second",
                    published_at=datetime.utcnow() - timedelta(days=2),
                ),
            ]
        )
        db.commit()

        strict = _disclosure_events(db, "005930", GUIDANCE_WORDS, fallback_to_recent=False)
        fallback = _disclosure_events(db, "005930", GUIDANCE_WORDS, fallback_to_recent=True)

        assert strict["recent_count"] == 0
        assert strict["all_count"] == 2
        assert fallback["recent_count"] == 2
        assert fallback["all_count"] == 2
        assert [item["title"] for item in fallback["latest_events"]] == [
            "풍문또는보도에대한해명(미확정)",
            "임원ㆍ주요주주특정증권등소유상황보고서",
        ]
        assert [item["url"] for item in fallback["latest_events"]] == [
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260925000001",
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260924000002",
        ]
