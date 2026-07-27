from fastapi.testclient import TestClient

import app.main as main_module


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


def test_market_index_endpoint_fetches_kis_every_time_and_disables_http_cache(monkeypatch):
    provider = _FakeMarketIndexProvider()
    monkeypatch.setattr(main_module, "kis_rest_provider", provider)
    client = TestClient(main_module.app)

    first = client.get("/market/indices?limit=30")
    second = client.get("/market/indices?limit=30")

    assert first.status_code == 200
    assert second.status_code == 200
    assert provider.calls == 2
    assert first.json()["items"][0]["current"] == 6701
    assert second.json()["items"][0]["current"] == 6702
    assert second.json()["items"][0]["source"] == "kis"
    assert second.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert second.headers["pragma"] == "no-cache"
    assert second.headers["expires"] == "0"


def test_dashboard_polls_live_market_indices_without_frontend_cache():
    source = TestClient(main_module.app).get("/assets/dashboard/app.js").text

    assert "marketIndexRefreshTimer" in source
    assert 'liveUrl(endpoint), { force: true, ttlMs: 0 }' in source
    assert 'koreaMarketPhase() === "regular" ? 5_000 : 60_000' in source
