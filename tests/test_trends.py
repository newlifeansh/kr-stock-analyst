from datetime import date, datetime, timedelta

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
    _latest_timeline,
    _mentioned_stocks_for_text,
    _timeline_item,
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


def test_financial_fraud_news_is_negative_and_keeps_only_the_named_stock():
    title = "기업은행 중국 법인, 현지서 800억원대 사기 당해"
    item = _timeline_item(
        "news",
        1,
        title,
        "조선일보",
        "https://example.com/news",
        datetime(2026, 8, 25, 0, 33),
        analysis_text=f"{title} 833억원 규모 금융사고와 허술한 내부통제 지적",
        stock_candidates=["기업은행", "SK이노베이션", "S-Oil"],
    )

    assert item["category"] == "금융"
    assert item["impact"] == "악재"
    assert item["leader_stocks"] == ["기업은행"]


def test_news_without_a_named_stock_does_not_add_category_representatives():
    title = '트럼프, 전문직 비자에 1.4억 수수료 추진…유학생도 대상'
    item = _timeline_item(
        "news",
        1,
        title,
        "아시아경제",
        "https://example.com/news",
        datetime(2026, 8, 25, 2, 49),
        analysis_text=f"{title} 미국 이민 정책 변화와 시장 영향",
        stock_candidates=["삼성전자", "현대차", "NAVER"],
        allow_inferred_stocks=False,
    )

    assert item["leader_stocks"] == []


def test_news_uses_only_a_stock_explicitly_named_in_the_visible_title():
    title = "LG전자, AI 스마트폰 부품 수요 회복 기대"
    item = _timeline_item(
        "news",
        1,
        title,
        "테스트뉴스",
        "https://example.com/news",
        datetime(2026, 8, 25, 3, 0),
        analysis_text=f"{title} 공급망 개선이 확인됐다",
        stock_candidates=["삼성전자", "LG전자", "NAVER"],
        allow_inferred_stocks=False,
    )

    assert item["leader_stocks"] == ["LG전자"]


def test_news_does_not_show_a_stock_found_only_in_the_hidden_summary():
    title = "증시 자사주 소각액 2년새 4.5배로 늘어"
    item = _timeline_item(
        "news",
        1,
        title,
        "테스트뉴스",
        "https://example.com/news",
        datetime(2026, 8, 25, 3, 0),
        analysis_text=f"{title} 삼성전자와 SK하이닉스 사례를 포함한다",
        stock_candidates=["삼성전자", "SK하이닉스", "NAVER"],
        allow_inferred_stocks=False,
    )

    assert item["leader_stocks"] == []


def test_latest_timeline_deduplicates_article_url_and_keeps_complete_title():
    SessionLocal = _session_factory()
    short_title = "[속보]美 재무 "
    full_title = '[속보]美 재무 "이란 위해 자금세탁하면 달러 시스템서 제외될 것"'

    with SessionLocal() as db:
        db.add_all(
            [
                models.NewsItem(
                    source="naver_finance",
                    source_category="breaking",
                    external_id="277:0005806717",
                    title=short_title,
                    press_name="아시아경제",
                    published_at=datetime(2026, 8, 25, 2, 32),
                ),
                models.NewsItem(
                    source="naver_finance",
                    source_category="global",
                    external_id="277:0005806717",
                    title=full_title,
                    press_name="아시아경제",
                    published_at=datetime(2026, 8, 25, 2, 32),
                ),
            ]
        )
        db.commit()
        timeline = _latest_timeline(db)

    matching = [item for item in timeline if item["url"] and item["url"].endswith("/277/0005806717")]
    assert len(matching) == 1
    assert matching[0]["title"] == full_title


def test_build_trend_analysis_uses_current_date_for_upcoming_events(monkeypatch):
    monkeypatch.setattr("app.services.trends._now_kst", lambda: datetime(2026, 7, 19, 9, 0))
    monkeypatch.setattr("app.services.trends.cpi_release_occurrences_between", lambda _start, _end: [])
    monkeypatch.setattr(
        "app.services.trends.bok_release_occurrences_between",
        lambda _key, _start, _end: [],
    )
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


def test_build_trend_analysis_includes_official_cpi_release(monkeypatch):
    monkeypatch.setattr("app.services.trends._now_kst", lambda: datetime(2026, 8, 10, 9, 0))
    monkeypatch.setattr(
        "app.services.trends.bok_release_occurrences_between",
        lambda _key, _start, _end: [],
    )
    monkeypatch.setattr(
        "app.services.trends.cpi_release_occurrences_between",
        lambda _start, _end: [datetime(2026, 8, 12, 21, 30)],
    )
    SessionLocal = _session_factory()

    with SessionLocal() as db:
        payload = build_trend_analysis(db, days=7)

    cpi_event = next(item for item in payload["events"] if item["id"] == "us-cpi-202608122130")
    assert cpi_event["title"] == "미국 CPI 소비자물가지수"
    assert cpi_event["starts_at"] == datetime(2026, 8, 12, 21, 30)
    assert cpi_event["importance"] == "매우 중요"
    assert cpi_event["event_axes"] == ["물가", "금리(고용)", "환율"]
    assert cpi_event["source_name"] == "U.S. Bureau of Labor Statistics"


def test_build_trend_analysis_limits_past_events_to_two_weeks(monkeypatch):
    now = datetime(2026, 8, 12, 22, 0)
    monkeypatch.setattr("app.services.trends._now_kst", lambda: now)
    monkeypatch.setattr(
        "app.services.trends.bok_release_occurrences_between",
        lambda _key, _start, _end: [],
    )
    monkeypatch.setattr(
        "app.services.trends.cpi_release_occurrences_between",
        lambda start, _end: [
            start - timedelta(minutes=1),
            datetime(2026, 8, 12, 21, 30),
        ],
    )
    SessionLocal = _session_factory()

    with SessionLocal() as db:
        payload = build_trend_analysis(db, days=7)

    assert any(item["id"] == "us-cpi-202608122130" for item in payload["past_events"])
    assert all(now - timedelta(days=14) <= item["starts_at"] < now for item in payload["past_events"])


def test_build_trend_analysis_includes_official_korean_releases(monkeypatch):
    monkeypatch.setattr("app.services.trends._now_kst", lambda: datetime(2026, 8, 24, 9, 0))
    monkeypatch.setattr("app.services.trends.cpi_release_occurrences_between", lambda _start, _end: [])

    def bok_occurrences(event_key, _start, _end):
        return {
            "kr-bsi-esi": [datetime(2026, 8, 26, 6, 0)],
            "kr-bank-rate": [datetime(2026, 8, 26, 12, 0)],
        }[event_key]

    monkeypatch.setattr(
        "app.services.trends.bok_release_occurrences_between",
        bok_occurrences,
    )
    SessionLocal = _session_factory()

    with SessionLocal() as db:
        payload = build_trend_analysis(db, days=7)

    korean_events = [item for item in payload["events"] if item["category"] == "한국"]
    assert [item["id"] for item in korean_events] == [
        "kr-bsi-esi-202608260600",
        "kr-bank-rate-202608261200",
    ]
    assert [item["title"] for item in korean_events] == [
        "한국 BSI·ESI",
        "한국 금융기관 가중평균금리",
    ]


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


def test_build_cpi_event_graph_scores_growth_and_financial_stocks_by_scenario(monkeypatch):
    monkeypatch.setattr("app.services.trends._now_kst", lambda: datetime(2026, 8, 10, 9, 0))
    SessionLocal = _session_factory()

    stocks = [
        models.StockMaster(code="005930", name="삼성전자", market="KOSPI"),
        models.StockMaster(code="035420", name="NAVER", market="KOSPI"),
        models.StockMaster(code="373220", name="LG에너지솔루션", market="KOSPI"),
        models.StockMaster(code="105560", name="KB금융", market="KOSPI"),
    ]
    prices = [
        models.DailyPrice(code=stock.code, trade_date=date(2026, 8, 7), close=100, market_cap=4_000_000 - idx * 100_000)
        for idx, stock in enumerate(stocks)
    ]
    with SessionLocal() as db:
        db.add_all([*stocks, *prices])
        db.commit()
        graph = build_event_graph(db, "us-cpi-202608122130")

    assert graph is not None
    assert graph["negative_label"] == "CPI 예상 상회/재가속"
    assert graph["positive_label"] == "CPI 예상 하회/둔화"

    hot_cpi = {item["name"]: item for item in graph["negative_stocks"]}
    cool_cpi = {item["name"]: item for item in graph["positive_stocks"]}
    assert hot_cpi["삼성전자"]["impact_direction"] == "시나리오 부담"
    assert hot_cpi["KB금융"]["impact_direction"] == "시나리오 수혜"
    assert cool_cpi["삼성전자"]["impact_direction"] == "시나리오 수혜"
    assert cool_cpi["KB금융"]["impact_direction"] == "시나리오 부담"
    assert hot_cpi["KB금융"]["impact_score"] > cool_cpi["KB금융"]["impact_score"]
