from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.db import Base
from app.services.trends import (
    _category_for_text,
    build_event_graph,
    build_trend_analysis,
    _impact_for_text,
    _leader_stocks_for_text,
    _mentioned_stocks_for_text,
)


def _session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def test_trend_impact_prefers_positive_company_signal():
    text = '교보증권 "LG전자, 하반기 AI 모멘텀 기대…목표주가 ↑"'
    assert _impact_for_text(text) == "호재"


def test_trend_impact_marks_exchange_rate_risk_as_negative():
    text = "사상 최대 경상흑자에도 환율은 1500원대 악세…이유는"
    assert _impact_for_text(text) == "악재"


def test_trend_category_uses_company_hint_before_broad_ai_keyword():
    text = "LG전자, 하반기 AI 모멘텀 기대"
    assert _category_for_text(text, hinted_names=["LG전자"]) == "대형주"


def test_trend_stock_matching_prefers_direct_company_name():
    candidates = ["LG전자", "삼성전자", "SK하이닉스"]
    text = '교보증권 "LG전자, 하반기 AI 모멘텀 기대…목표주가 ↑"'
    assert _mentioned_stocks_for_text(text, candidates) == ["LG전자"]
    assert _leader_stocks_for_text(text, "시장", stock_candidates=candidates)[0] == "LG전자"


def test_trend_stock_matching_uses_axis_fallback_for_oil_news():
    text = "미국 EIA 주간 원유재고 발표 앞두고 유가 변동성 확대"
    leaders = _leader_stocks_for_text(text, "원자재", stock_candidates=["삼성전자", "NAVER"])
    assert leaders == ["S-Oil", "SK이노베이션", "대한항공"]


def test_trend_stock_matching_skips_shorter_overlap_name():
    text = "SK하이닉스, 프리마켓서 300만원 돌파"
    leaders = _mentioned_stocks_for_text(text, ["SK하이닉스", "이닉스", "삼성전자"])
    assert leaders == ["SK하이닉스"]


def test_build_trend_analysis_uses_current_date_for_upcoming_events(monkeypatch):
    monkeypatch.setattr("app.services.trends._now_kst", lambda: datetime(2026, 7, 19, 9, 0))
    SessionLocal = _session_factory()

    with SessionLocal() as db:
        payload = build_trend_analysis(db, days=7)

    assert payload["events"]
    assert any(
        item["title"] == "미국 EIA 주간 원유재고" and item["starts_at"] == datetime(2026, 7, 22, 23, 30)
        for item in payload["events"]
    )
    assert any(
        item["title"] == "미국 주간 신규실업수당청구건수" and item["starts_at"] == datetime(2026, 7, 23, 21, 30)
        for item in payload["events"]
    )
    assert "원유" in payload["headline"]
    assert "금리(고용)" in payload["headline"]


def test_build_event_graph_supports_dynamic_event_id(monkeypatch):
    monkeypatch.setattr("app.services.trends._now_kst", lambda: datetime(2026, 7, 19, 9, 0))
    SessionLocal = _session_factory()

    with SessionLocal() as db:
        graph = build_event_graph(db, "us-jobless-claims-202607232130")

    assert graph is not None
    assert graph["title"] == "미국 주간 신규실업수당청구건수"
    assert graph["starts_at"] == datetime(2026, 7, 23, 21, 30)


def test_build_event_graph_falls_back_to_sector_leaders_without_price_data(monkeypatch):
    monkeypatch.setattr("app.services.trends._now_kst", lambda: datetime(2026, 7, 19, 9, 0))
    SessionLocal = _session_factory()

    with SessionLocal() as db:
        db.add_all(
            [
                models.StockMaster(code="096770", name="SK이노베이션", market="KOSPI"),
                models.StockMaster(code="010950", name="S-Oil", market="KOSPI"),
                models.StockMaster(code="003490", name="대한항공", market="KOSPI"),
            ]
        )
        db.commit()

        graph = build_event_graph(db, "us-eia-oil-202607222330")

    assert graph is not None
    assert [item["name"] for item in graph["positive_stocks"][:3]] == ["SK이노베이션", "S-Oil", "대한항공"]
    assert [item["name"] for item in graph["negative_stocks"][:3]] == ["대한항공", "SK이노베이션", "S-Oil"]
    assert all(item["impact_score"] > 0 for item in graph["positive_stocks"])
