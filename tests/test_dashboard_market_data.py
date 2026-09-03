from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.services.dashboard_market_data import DashboardMarketDataError
from app.services.quant_signals import STRATEGY_VERSION
from app.services.signal_entry_evidence import ENTRY_EVIDENCE_STRATEGY_VERSION


def test_public_market_calendar_contract(monkeypatch):
    async def fake_calendar(*, days):
        assert days == 14
        return {
            "as_of": "2026-08-29T09:00:00",
            "window_start": "2026-08-15T09:00:00",
            "window_end": "2026-09-12T09:00:00",
            "events": [{"id": "kr-event", "starts_at": "2026-09-02T23:30:00"}],
            "past_events": [],
        }

    monkeypatch.setattr(main_module, "build_korea_market_calendar", fake_calendar)
    response = TestClient(app).get("/market/calendar?days=14")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.json()["events"][0]["id"] == "kr-event"


def test_public_market_calendar_rejects_out_of_range_days():
    client = TestClient(app)

    assert client.get("/market/calendar?days=0").status_code == 422
    assert client.get("/market/calendar?days=32").status_code == 422


def test_public_market_calendar_returns_explicit_upstream_error(monkeypatch):
    async def fail_calendar(*, days):
        raise DashboardMarketDataError(f"calendar failed for {days}")

    monkeypatch.setattr(main_module, "build_korea_market_calendar", fail_calendar)
    response = TestClient(app).get("/market/calendar")

    assert response.status_code == 502
    assert response.json()["detail"] == "한국 주요 일정을 불러오지 못했습니다."


def test_public_stock_week_chart_contract(monkeypatch):
    async def fake_week_chart(code):
        assert code == "005930"
        return {"periodType": "week", "priceInfos": {"20260829": []}}

    monkeypatch.setattr(main_module, "fetch_stock_week_chart", fake_week_chart)
    response = TestClient(app).get("/stocks/005930/week-chart")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.json()["priceInfos"] == {"20260829": []}


def test_public_stock_week_chart_rejects_invalid_code():
    response = TestClient(app).get("/stocks/not-a-code/week-chart")

    assert response.status_code == 422
    assert response.json()["detail"] == "종목 코드는 6자리 숫자여야 합니다."


def test_public_stock_week_chart_returns_explicit_upstream_error(monkeypatch):
    async def fail_week_chart(_code):
        raise DashboardMarketDataError("week chart failed")

    monkeypatch.setattr(main_module, "fetch_stock_week_chart", fail_week_chart)
    response = TestClient(app).get("/stocks/005930/week-chart")

    assert response.status_code == 502
    assert response.json()["detail"] == "일주일 실시간 차트를 불러오지 못했습니다."


def test_quality_strategy_version_does_not_retag_evidence_history():
    assert STRATEGY_VERSION == "position-lifecycle-v7.4"
    assert ENTRY_EVIDENCE_STRATEGY_VERSION == "position-lifecycle-v7.0"
    assert STRATEGY_VERSION != ENTRY_EVIDENCE_STRATEGY_VERSION
