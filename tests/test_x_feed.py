from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_db
from app.main import app
from app.models import NewsItem, StockMaster
from app.repository import latest_news_items
from app.services import x_feed


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_x_recent_search_is_mapped_and_persisted(monkeypatch):
    calls = []

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "data": [
                    {
                        "id": "1900000000000000000",
                        "text": "신라젠 임상 기대감으로 주가 상승 가능성을 살펴봅니다.",
                        "author_id": "42",
                        "created_at": "2026-07-25T01:20:00.000Z",
                        "public_metrics": {
                            "like_count": 12,
                            "retweet_count": 3,
                            "reply_count": 2,
                            "quote_count": 1,
                        },
                    }
                ],
                "includes": {
                    "users": [
                        {
                            "id": "42",
                            "name": "시장 관찰자",
                            "username": "market_watcher",
                            "profile_image_url": "https://example.test/profile.jpg",
                        }
                    ]
                },
            }

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(x_feed.requests, "get", fake_get)
    settings = Settings(
        x_bearer_token="secret-token",
        x_feed_cache_seconds=300,
        x_feed_retention_days=14,
    )
    with _session() as db:
        stock = StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True)
        db.add(stock)
        db.commit()

        payload = x_feed.build_stock_x_feed(db, stock, settings, refresh=True)

        assert payload["configured"] is True
        assert payload["items"][0]["username"] == "market_watcher"
        assert payload["items"][0]["like_count"] == 12
        assert payload["items"][0]["impact"] == "호재"
        assert payload["items"][0]["created_at"] == datetime(2026, 7, 25, 1, 20)
        assert calls[0][0] == x_feed.X_RECENT_SEARCH_URL
        assert calls[0][1]["headers"] == {"Authorization": "Bearer secret-token"}
        assert '"신라젠"' in calls[0][1]["params"]["query"]

        stored = db.scalar(select(NewsItem).where(NewsItem.source == "x_api"))
        assert stored is not None
        assert stored.external_id == "1900000000000000000"
        assert stored.detail_url == "https://x.com/market_watcher/status/1900000000000000000"
        assert latest_news_items(db) == []
        assert latest_news_items(db, include_social=True)[0].external_id == stored.external_id

        cached = x_feed.build_stock_x_feed(db, stock, settings)
        assert cached["items"][0]["text"].startswith("신라젠 임상")
        assert len(calls) == 1


def test_x_feed_endpoint_has_search_fallback_without_token(monkeypatch):
    db = _session()
    db.add(StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True))
    db.commit()

    def override_db():
        yield db

    from app import main as main_module

    monkeypatch.setattr(main_module.settings, "x_feed_enabled", True)
    monkeypatch.setattr(main_module.settings, "x_bearer_token", None)
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/stocks/215600/x-feed", params={"refresh": "true"})
        assert response.status_code == 200
        assert response.headers["cache-control"].startswith("no-store")
        payload = response.json()
        assert payload["configured"] is False
        assert payload["items"] == []
        assert payload["search_url"].startswith("https://x.com/search?")
        assert "신라젠" in payload["query"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_stock_detail_contains_x_feed_ui():
    client = TestClient(app)
    shell = client.get("/dashboard/215600").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'id="stock-x-feed-section"' in shell
    assert 'id="stock-x-feed-list"' in shell
    assert 'id="stock-x-feed-more"' in shell
    assert "function loadStockXFeed" in source
    assert "/x-feed?limit=20" in source
    assert ".stock-x-feed-link" in styles
    assert ".stock-x-feed-text" in styles
