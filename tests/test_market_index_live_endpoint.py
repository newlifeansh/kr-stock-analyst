from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.db import Base, get_db


class _FakeMarketIndexProvider:
    def __init__(self):
        self.calls = 0

    def is_configured(self):
        return True

    def fetch_market_indices(self):
        self.calls += 1
        return [
            {
                "code": "KOSPI",
                "source": "kis",
                "current": 6700 + self.calls,
                "previous_close": 6690,
                "change": 10 + self.calls,
                "change_rate": 0.2,
            },
            {
                "code": "KOSDAQ",
                "source": "kis",
                "current": 760 + self.calls,
                "previous_close": 750,
                "change": 10 + self.calls,
                "change_rate": 1.3,
            },
        ]


def test_market_index_endpoint_reuses_complete_snapshot_and_disables_http_cache(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        with testing_session() as db:
            yield db

    provider = _FakeMarketIndexProvider()
    monkeypatch.setattr(main_module, "kis_rest_provider", provider)
    main_module.app.dependency_overrides[get_db] = override_db
    client = TestClient(main_module.app)
    try:
        first = client.get("/market/indices?limit=30")
        second = client.get("/market/indices?limit=30")

        assert first.status_code == 200
        assert second.status_code == 200
        assert provider.calls == 1
        assert first.json()["items"][0]["current"] == 6701
        assert second.json()["items"][0]["current"] == 6701
        assert second.json()["items"][0]["source"] == "kis"
        assert second.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
        assert second.headers["pragma"] == "no-cache"
        assert second.headers["expires"] == "0"
    finally:
        main_module.app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_dashboard_polls_live_market_indices_without_frontend_cache():
    source = TestClient(main_module.app).get("/assets/dashboard/app.js").text

    assert "marketIndexRefreshTimer" in source
    assert 'liveUrl(domesticEndpoint), { force: true, ttlMs: 0 }' in source
    assert 'liveUrl("/market/global-assets?limit=30"), { force: true, ttlMs: 0 }' in source
    assert 'koreaMarketPhase() === "regular" ? 5_000 : 30_000' in source


def test_dashboard_market_index_loader_supports_legacy_mobile_webviews():
    source = TestClient(main_module.app).get("/assets/dashboard/app.js").text
    loader = source[
        source.index("async function loadHomeMarketIndices"):
        source.index("function stopHomeMarketIndexRefresh")
    ]

    assert "await Promise.allSettled([" not in loader
    assert ".at(" not in loader
    assert ".catch(() => null)" in loader
    assert "incomingByCode.get(code) || previousByCode.get(code)" in loader
    assert "mergedItems.length !== expectedCodes.size" in loader
    assert "updatedAtCandidates[updatedAtCandidates.length - 1] || null" in loader


def test_cross_market_endpoint_composes_and_caches_korea_and_us_snapshots(monkeypatch):
    calls = {"korea": 0, "us": 0}

    def fake_korea(*, response, limit, refresh, db):
        calls["korea"] += 1
        return {
            "items": [
                {
                    "code": "KOSPI",
                    "label": "코스피",
                    "current": 2700,
                    "change_rate": 0.42,
                    "as_of": "2026-09-05T09:00:00+09:00",
                }
            ]
        }

    def fake_us(*, response, limit, db):
        calls["us"] += 1
        return {
            "items": [
                {
                    "code": "SP500",
                    "label": "S&P 500",
                    "current": 6500,
                    "change_rate": -0.18,
                    "as_of": "2026-09-05T06:00:00-04:00",
                }
            ]
        }

    monkeypatch.setattr(main_module, "market_indices", fake_korea)
    monkeypatch.setattr(main_module, "global_market_assets", fake_us)
    main_module.api_cache.clear()
    main_module.app.dependency_overrides[get_db] = lambda: iter([object()])
    client = TestClient(main_module.app)
    try:
        first = client.get("/market/cross-market?limit=31")
        second = client.get("/market/cross-market?limit=31")
    finally:
        main_module.app.dependency_overrides.pop(get_db, None)
        main_module.api_cache.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["source"] == "snapshot-composite"
    assert first.json()["korea"]["items"][0]["code"] == "KOSPI"
    assert first.json()["us"]["items"][0]["code"] == "SP500"
    assert first.json()["refresh_interval_seconds"] == 30
    assert calls == {"korea": 1, "us": 1}
    assert second.headers["cache-control"] == "public, max-age=15, stale-while-revalidate=30"


def test_us_entry_uses_current_dashboard_top50_contract_and_keeps_legacy_assets_available():
    client = TestClient(main_module.app)

    shell = client.get("/us")
    script = client.get("/dashboard-app-v170.js")
    legacy_script = client.get("/assets/nasdaq/app.js")
    manifest = client.get("/us.webmanifest")

    assert shell.status_code == 200
    assert 'id="home-view"' in shell.text
    assert 'id="home-surge"' in shell.text
    assert 'data-home-ranking-market="NASDAQ"' in shell.text
    assert 'data-home-ranking-market="SP500"' in shell.text
    assert script.status_code == 200
    assert 'const US_MARKET_RANKING_MARKETS = new Set(["NASDAQ", "SP500"]);' in script.text
    assert '"/us/market/rankings"' in script.text
    assert legacy_script.status_code == 200
    assert "/market/cross-market?limit=30" in legacy_script.text
    assert manifest.status_code == 200
    assert manifest.json()["start_url"] == "/us?view=overview"
    assert manifest.json()["scope"] == "/us"
    assert 'US_APP_BASE_PATH = "/us"' in legacy_script.text
