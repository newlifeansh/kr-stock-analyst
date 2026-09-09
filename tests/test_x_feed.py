from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.config import Settings
from app.db import Base, get_db
from app.main import app
from app.models import NewsItem, StockMaster
from app.repository import latest_news_items
from app.services import community_feed, x_feed


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
    recent_time = (datetime.utcnow() - timedelta(days=1)).replace(microsecond=0)

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
                        "created_at": f"{recent_time.isoformat()}.000Z",
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
        assert payload["items"][0]["created_at"] == recent_time
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


def test_stock_community_feed_endpoint_uses_naver_board_and_threads(monkeypatch):
    db = _session()
    db.add(StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True))
    db.commit()

    class Response:
        text = """
        <table class="type2">
          <tr><th>날짜</th><th>제목</th><th>글쓴이</th><th>조회</th><th>추천</th><th>비추천</th></tr>
          <tr align="center">
            <td><span>2026.07.25 12:13</span></td>
            <td class="title"><a href="/item/board_read.naver?code=215600&nid=426298204&page=1" title="신라젠 다시 상승 준비">신라젠 다시 상승 준비</a></td>
            <td class="p11 align_right">개미투자자</td>
            <td><span>27</span></td>
            <td><strong>3</strong></td>
            <td><strong>0</strong></td>
          </tr>
        </table>
        """

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(url, **kwargs):
        assert url == community_feed.NAVER_BOARD_URL
        assert kwargs["params"]["code"] == "215600"
        return Response()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module.settings, "threads_access_token", None)
    monkeypatch.setattr(community_feed.requests, "get", fake_get)
    try:
        response = TestClient(app).get("/stocks/215600/community-feed")
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == "215600"
        assert payload["providers"][0]["key"] == "naver_board"
        assert payload["providers"][0]["label"] == "네이버"
        assert (
            payload["providers"][0]["search_url"]
            == "https://m.stock.naver.com/domestic/stock/215600/discussion"
        )
        assert payload["providers"][0]["items"][0]["title"] == "신라젠 다시 상승 준비"
        assert (
            payload["providers"][0]["items"][0]["url"]
            == "https://m.stock.naver.com/domestic/stock/215600/discussion/426298204"
        )
        assert payload["providers"][0]["items"][0]["view_count"] == 27
        assert payload["providers"][1]["key"] == "threads"
        assert payload["providers"][1]["label"] == "쓰레드"
        assert payload["providers"][1]["search_url"].startswith("https://www.threads.com/search?q=")
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_stock_community_popular_mode_scans_today_and_orders_recommendations_then_views(monkeypatch):
    db = _session()
    db.add(StockMaster(code="215601", name="인기테스트", market="KOSDAQ", is_active=True))
    db.commit()
    calls = []

    class Response:
        def __init__(self, payload):
            self._payload = payload

        @staticmethod
        def raise_for_status():
            return None

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        assert url == community_feed.NAVER_WORLD_DISCUSSION_URL
        params = kwargs["params"]
        assert params["itemCode"] == "215601"
        assert params["discussionType"] == "domesticStock"
        assert params["pageSize"] == 100
        if "offset" not in params:
            return Response({
                "result": {
                    "lastOffset": "-next",
                    "posts": [
                        {
                            "id": "popular-1",
                            "writtenAt": "2026-09-09T10:00:00",
                            "title": "조회가 높은 글",
                            "writer": {"nickname": "작성자1"},
                            "recommendCount": 5,
                            "notRecommendCount": 1,
                            "commentCount": 2,
                            "viewCount": 1000,
                        },
                        {
                            "id": "popular-2",
                            "writtenAt": "2026-09-09T11:00:00",
                            "title": "공감이 높은 글",
                            "writer": {"nickname": "작성자2"},
                            "recommendCount": 20,
                            "notRecommendCount": 0,
                            "commentCount": 1,
                            "viewCount": 100,
                        },
                    ],
                }
            })
        assert params["offset"] == "-next"
        return Response({
            "result": {
                "lastOffset": "-done",
                "posts": [
                    {
                        "id": "popular-3",
                        "writtenAt": "2026-09-09T09:00:00",
                        "title": "공감과 조회가 모두 높은 글",
                        "writer": {"nickname": "작성자3"},
                        "recommendCount": 20,
                        "notRecommendCount": 2,
                        "commentCount": 3,
                        "viewCount": 800,
                    },
                    {
                        "id": "yesterday",
                        "writtenAt": "2026-09-08T23:59:59",
                        "title": "어제 글",
                        "writer": {"nickname": "작성자4"},
                        "recommendCount": 999,
                        "viewCount": 99999,
                    },
                ],
            }
        })

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module.settings, "threads_access_token", None)
    monkeypatch.setattr(community_feed, "_today_kst", lambda: date(2026, 9, 9))
    monkeypatch.setattr(community_feed.requests, "get", fake_get)
    try:
        response = TestClient(app).get(
            "/stocks/215601/community-feed?limit=12&mode=popular"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "popular"
        assert len(payload["providers"]) == 1
        assert [item["post_id"] for item in payload["providers"][0]["items"]] == [
            "popular-3",
            "popular-2",
            "popular-1",
        ]
        assert payload["providers"][0]["message"] == "오늘 인기글 3건"
        assert len(calls) == 2
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_us_stock_community_feed_uses_naver_world_board(monkeypatch):
    calls = []

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "result": {
                    "posts": [{
                        "id": "428998231",
                        "writtenAt": "2026-09-06T15:05:56",
                        "title": "AI 투자 과열 논란",
                        "writer": {"nickname": "미국주식러", "imageUrl": "https://example.test/avatar.png"},
                        "recommendCount": 12,
                        "notRecommendCount": 1,
                        "commentCount": 3,
                        "viewCount": 99,
                    }],
                },
            }

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(community_feed.requests, "get", fake_get)
    stock = {"code": "NVDA", "name": "NVIDIA", "market": "NASDAQ", "markets": ["NASDAQ"]}

    payload = community_feed.build_us_stock_community_feed(stock, limit=12)

    provider = payload["providers"][0]
    item = provider["items"][0]
    assert calls[0][0] == community_feed.NAVER_WORLD_DISCUSSION_URL
    assert calls[0][1]["params"] == {"itemCode": "NVDA.O", "discussionType": "foreignStock"}
    assert provider["label"] == "네이버 미국증시"
    assert provider["source"] == "naver_world_stock_board"
    assert item["url"] == "https://m.stock.naver.com/worldstock/stock/NVDA.O/discussion/428998231"
    assert item["like_count"] == 12
    assert item["reply_count"] == 3


def test_us_stock_community_popular_mode_uses_today_only(monkeypatch):
    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "result": {
                    "lastOffset": "-done",
                    "posts": [
                        {
                            "id": "us-popular-1",
                            "writtenAt": "2026-09-09T08:30:00",
                            "title": "오늘 미국 인기글",
                            "writer": {"nickname": "미국주식러"},
                            "recommendCount": 14,
                            "notRecommendCount": 1,
                            "commentCount": 4,
                            "viewCount": 500,
                        },
                        {
                            "id": "us-old",
                            "writtenAt": "2026-09-08T23:30:00",
                            "title": "어제 미국 글",
                            "writer": {"nickname": "어제작성자"},
                            "recommendCount": 100,
                            "viewCount": 5000,
                        },
                    ],
                }
            }

    def fake_get(url, **kwargs):
        assert url == community_feed.NAVER_WORLD_DISCUSSION_URL
        assert kwargs["params"] == {
            "itemCode": "NVDA.O",
            "discussionType": "foreignStock",
            "pageSize": 100,
        }
        return Response()

    monkeypatch.setattr(community_feed, "_today_kst", lambda: date(2026, 9, 9))
    monkeypatch.setattr(community_feed.requests, "get", fake_get)
    payload = community_feed.build_us_stock_community_feed(
        {"code": "NVDA", "name": "NVIDIA", "market": "NASDAQ", "markets": ["NASDAQ"]},
        limit=12,
        mode="popular",
    )

    assert payload["mode"] == "popular"
    assert [item["post_id"] for item in payload["providers"][0]["items"]] == [
        "us-popular-1"
    ]
    assert payload["providers"][0]["message"] == "오늘 인기글 1건"


def test_us_stock_community_feed_endpoint_is_market_scoped(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "resolve_us_stock",
        lambda symbol: {"code": "ZZZ", "name": "Test US", "market": "NYSE", "markets": ["NYSE"]},
    )
    monkeypatch.setattr(
        main_module,
        "build_us_stock_community_feed",
        lambda stock, **kwargs: {
            "code": stock["code"],
            "name": stock["name"],
            "as_of": datetime.utcnow(),
            "message": "네이버 미국증시 종목토론방",
            "providers": [],
        },
    )

    response = TestClient(app).get("/us/stocks/ZZZ/community-feed")

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("no-store")
    assert response.json()["message"] == "네이버 미국증시 종목토론방"


def test_threads_keyword_search_is_mapped_with_meta_api(monkeypatch):
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
                        "id": "threads-post-1",
                        "text": "신라젠 임상 기대감으로 상승 가능성을 살펴봅니다.",
                        "permalink": "https://www.threads.net/@market/post/example",
                        "username": "market_note",
                        "timestamp": "2026-07-25T01:20:00+0000",
                        "profile_picture_url": "https://example.test/threads-profile.jpg",
                    }
                ]
            }

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(community_feed.requests, "get", fake_get)
    settings = Settings(
        threads_access_token="threads-secret",
        threads_feed_timeout_seconds=7,
        threads_feed_max_results=12,
    )
    stock = StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True)

    payload = community_feed.build_stock_community_feed(stock, settings, limit=12)
    provider = payload["providers"][1]

    assert provider["configured"] is True
    assert provider["source"] == "threads_api"
    assert provider["message"] == "최근 글 1건"
    assert provider["items"][0]["username"] == "market_note"


def test_threads_keyword_search_tries_multiple_queries_until_it_finds_posts(monkeypatch):
    calls = []

    class EmptyResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"data": []}

    class HitResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "data": [
                    {
                        "id": "threads-post-2",
                        "text": "215600 실적 기대감과 상승 모멘텀으로 관심이 다시 늘고 있습니다.",
                        "permalink": "https://www.threads.net/@market/post/example2",
                        "username": "market_note",
                        "timestamp": "2026-07-25T03:10:00+0000",
                    }
                ]
            }

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"]["q"])
        if len(calls) == 1:
            return EmptyResponse()
        return HitResponse()

    monkeypatch.setattr(community_feed.requests, "get", fake_get)
    settings = Settings(
        threads_access_token="threads-secret",
        threads_feed_timeout_seconds=7,
        threads_feed_max_results=12,
    )
    stock = StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True)

    payload = community_feed.build_stock_community_feed(stock, settings, limit=12)
    provider = payload["providers"][1]

    assert calls[0] == "신라젠"
    assert "215600" in calls
    assert provider["configured"] is True
    assert provider["items"][0]["post_id"] == "threads-post-2"
    assert provider["message"] == "최근 글 1건"
    assert provider["items"][0]["impact"] == "호재"
    assert provider["items"][0]["created_at"] == datetime(2026, 7, 25, 3, 10)
    assert calls[:2] == ["신라젠", "215600"]


def test_stock_detail_contains_community_ui():
    client = TestClient(app)
    shell = client.get("/dashboard/215600").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'id="stock-community-section"' in shell
    assert 'id="stock-community-providers"' in shell
    assert "function loadStockCommunity" in source
    assert "/home-context?flow_limit=1500" in source
    assert "/community-feed?limit=12" in source
    assert ".stock-community-tabs" in styles
    assert '"stock-community-tabs stock-v3-segment"' in source
    assert ".stock-community-entry" in styles
    assert ".stock-community-text" in styles
    assert "state.stockCommunityProviderKey" in source
    assert "stock-community-expand" in source
    assert "function stockCommunityShortcutUrl" in source
    assert 'row.external_landing ? "원문에서 보기" : "바로가기"' in source
    assert "stock-community-shortcut" in styles
    assert "min-height: 44px" in styles
    assert "stock-community-original" not in source
    assert "stock-community-original" not in styles
    assert '"원문 ↗"' not in source


def test_stock_detail_community_has_latest_and_popular_badge_filters():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert '[["latest", "최신글"], ["popular", "인기글"]]' in source
    assert 'group.setAttribute("role", "group")' in source
    assert 'group.setAttribute("aria-label", "커뮤니티 글 정렬")' in source
    assert 'button.setAttribute("aria-pressed", active ? "true" : "false")' in source
    assert "function setStockCommunityMode(mode)" in source
    assert "state.stockCommunityPopularLoading" in source
    assert "/community-feed?limit=12&mode=popular" in source
    assert "오늘 인기글을 불러오는 중입니다." in source
    assert ".stock-community-mode-filter button" in styles
    mode_filter_styles = styles.split(
        "#stock-view.stock-detail-v3 .stock-community-mode-filter button {", 1
    )[1].split("}", 1)[0]
    assert "min-height: 44px" in mode_filter_styles
    assert "border-radius: 999px" in mode_filter_styles
    assert ".stock-community-mode-filter button:focus-visible" in styles
