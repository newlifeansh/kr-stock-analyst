from decimal import Decimal

from fastapi.testclient import TestClient

import app.main as main_module


class _FakeKisProvider:
    def __init__(self):
        self.calls = 0

    def is_configured(self):
        return True

    def _request_current_price(self, code):
        self.calls += 1
        return {
            "stck_prpr": str(100_000 + self.calls),
            "prdy_vrss": "1200",
            "prdy_ctrt": "1.21",
            "prdy_vrss_sign": "2",
            "acml_vol": "345678",
            "acml_tr_pbmn": "9876543210",
        }


def test_kis_current_quote_is_requested_again_instead_of_cached(monkeypatch):
    provider = _FakeKisProvider()
    monkeypatch.setattr(main_module, "kis_rest_provider", provider)

    first = main_module._fetch_kis_current_quote("005930")
    second = main_module._fetch_kis_current_quote("005930")

    assert provider.calls == 2
    assert first["price"] == 100_001
    assert second["price"] == 100_002
    assert second["change_rate"] == Decimal("1.21")


def test_live_quote_endpoint_disables_http_caching(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_stock_quote_stream_payload",
        lambda code: {
            "type": "quote",
            "code": code,
            "name": "삼성전자",
            "market": "KOSPI",
            "source": "kis_rest",
            "as_of": "2026-07-23T10:00:00+09:00",
            "quote": {"price": 100_000, "change_rate": 1.2},
        },
    )
    response = TestClient(main_module.app).get("/stocks/005930/quote")

    assert response.status_code == 200
    assert response.json()["source"] == "kis_rest"
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.headers["pragma"] == "no-cache"


def test_dashboard_frontend_bypasses_quote_cache_and_shows_provider_badge():
    source = TestClient(main_module.app).get("/assets/dashboard/app.js").text

    assert "isUncachedKoreaMarketDataUrl" in source
    assert "/^\\/stocks\\/[^/]+\\/(?:dashboard|quote)$/" in source
    assert "if (!bypassCache)" in source
    assert 'badge.textContent = generationLabel;' in source
    assert 'badge.classList.toggle("is-ollama", isOllamaAnalysis);' in source

