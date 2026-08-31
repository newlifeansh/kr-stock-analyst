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
