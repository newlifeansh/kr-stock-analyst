from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.db import Base, get_db
from app.main import app
from app.models import StockMaster


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_stock_home_context_combines_detail_sections(monkeypatch):
    db = _session()
    db.add(StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True))
    db.commit()

    def override_db():
        yield db

    research_calls = []
    disclosure_calls = []
    news_calls = []
    community_calls = []
    disclosure_refresh_calls = []
    flow_refresh_calls = []

    def fake_research_reports(db, **kwargs):
        research_calls.append(kwargs)
        return [
            {
                "id": 1,
                "source": "broker",
                "source_category": "company",
                "external_id": "r-1",
                "title": "신라젠 목표가 상향",
                "stock_code": "215600",
                "published_at": datetime(2026, 7, 29, 9, 30),
            }
        ]

    def fake_disclosures(db, **kwargs):
        disclosure_calls.append(kwargs)
        return [
            {
                "id": 2,
                "source": "dart",
                "external_id": "d-1",
                "disclosure_category": "report",
                "company_name": "신라젠",
                "stock_code": "215600",
                "report_name": "사업보고서",
                "published_at": datetime(2026, 7, 29, 10, 15),
            }
        ]

    def fake_news_items(db, code, **kwargs):
        news_calls.append({"code": code, **kwargs})
        return [
            {
                "id": 3,
                "source": "naver",
                "source_category": "company",
                "external_id": "n-1",
                "title": "신라젠 임상 기대감",
                "published_at": datetime(2026, 7, 29, 11, 0),
            }
        ]

    def fake_community_feed(stock, settings, **kwargs):
        community_calls.append(
            {
                "limit": kwargs["limit"],
                "timeout_seconds": kwargs["timeout_seconds"],
                "stock_code": stock.code,
            }
        )
        return {
            "code": stock.code,
            "name": stock.name,
            "as_of": datetime(2026, 7, 29, 12, 0),
            "message": "커뮤니티",
            "providers": [
                {
                    "key": "naver_board",
                    "label": "네이버",
                    "source": "naver_finance_board",
                    "configured": True,
                    "search_url": "https://finance.naver.com/item/board.naver?code=215600",
                    "more_label": "종토방 더 보기 ↗",
                    "message": "최근 글 1건",
                    "items": [
                        {
                            "provider_key": "naver_board",
                            "post_id": "post-1",
                            "title": "신라젠 다시 상승 준비",
                            "text": "신라젠 다시 상승 준비",
                            "author_name": "개미투자자",
                            "url": "https://finance.naver.com/item/board_read.naver?code=215600&nid=1",
                            "created_at": datetime(2026, 7, 29, 11, 30),
                            "like_count": 3,
                            "dislike_count": 0,
                            "reply_count": 1,
                            "repost_count": 0,
                            "view_count": 27,
                            "impact": "호재",
                        }
                    ],
                }
            ],
        }

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "latest_research_reports", fake_research_reports)
    monkeypatch.setattr(main_module, "latest_disclosures", fake_disclosures)
    monkeypatch.setattr(main_module, "stock_news_item_payloads", fake_news_items)
    monkeypatch.setattr(main_module, "build_stock_community_feed", fake_community_feed)
    monkeypatch.setattr(
        main_module,
        "_refresh_stock_disclosure_window",
        lambda _db, stock_code: disclosure_refresh_calls.append(stock_code),
    )
    monkeypatch.setattr(
        main_module,
        "_refresh_stock_investor_flow_if_stale",
        lambda _db, stock_code: flow_refresh_calls.append(stock_code) or {
            "refreshed": False,
            "latest_date": None,
        },
    )
    main_module.api_cache.clear()
    try:
        response = TestClient(app).get("/stocks/215600/home-context")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, max-age=120"
        payload = response.json()
        assert payload["code"] == "215600"
        assert payload["name"] == "신라젠"
        assert payload["flows"] == []
        assert payload["research_reports"][0]["title"] == "신라젠 목표가 상향"
        assert payload["disclosures"][0]["report_name"] == "사업보고서"
        assert payload["news_items"][0]["title"] == "신라젠 임상 기대감"
        assert payload["community"]["providers"][0]["items"][0]["title"] == "신라젠 다시 상승 준비"
        assert research_calls[0]["stock_code"] == "215600"
        assert disclosure_calls[0]["stock_code"] == "215600"
        assert disclosure_refresh_calls == ["215600"]
        assert flow_refresh_calls == ["215600"]
        assert news_calls[0] == {"code": "215600", "limit": 60}
        assert community_calls[0]["limit"] == 12
        assert community_calls[0]["timeout_seconds"] == main_module.settings.threads_feed_timeout_seconds

        second = TestClient(app).get("/stocks/215600/home-context")
        assert second.status_code == 200
        assert second.json() == payload
        assert len(research_calls) == 1
        assert len(disclosure_calls) == 1
        assert len(news_calls) == 1
        assert len(community_calls) == 1
        assert disclosure_refresh_calls == ["215600"]
        assert flow_refresh_calls == ["215600"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_stock_news_endpoint_uses_the_stock_code_feed(monkeypatch):
    db = _session()
    db.add(StockMaster(code="373220", name="LG에너지솔루션", market="KOSPI", is_active=True))
    db.commit()

    def override_db():
        yield db

    calls = []
    monkeypatch.setattr(
        main_module,
        "stock_news_item_payloads",
        lambda _db, code, limit: calls.append((code, limit)) or [
            {
                "id": -1,
                "source": "naver_finance",
                "source_category": "company",
                "external_id": "011:3",
                "title": "LG엔솔 오늘 최신 기사",
                "summary": None,
                "press_name": "서울경제",
                "image_url": None,
                "detail_url": "https://n.news.naver.com/mnews/article/011/3",
                "published_at": datetime(2026, 8, 28, 15, 0),
            }
        ],
    )
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/stocks/373220/news-items?limit=30")
        assert response.status_code == 200
        assert response.headers["x-stock-news-source"] == "naver-stock-code"
        assert response.json()[0]["title"] == "LG엔솔 오늘 최신 기사"
        assert calls == [("373220", 30)]
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
