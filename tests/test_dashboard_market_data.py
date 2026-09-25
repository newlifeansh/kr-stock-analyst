from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

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


def test_us_market_calendar_uses_official_bls_dates_and_korean_time(monkeypatch):
    from app.services.dashboard_market_data import build_us_market_calendar

    def releases(start, end):
        assert start == datetime(2026, 9, 24, 9, 0)
        assert end == datetime(2026, 10, 12, 9, 0)
        return [
            ("us-employment", datetime(2026, 10, 2, 21, 30)),
            ("us-cpi", datetime(2026, 9, 25, 21, 30)),
        ]

    monkeypatch.setattr("app.services.dashboard_market_data.bls_market_releases_between", releases)
    payload = asyncio.run(build_us_market_calendar(
        days=16, now=datetime(2026, 9, 26, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    ))

    assert [item["title"] for item in payload["events"]] == ["미국 고용보고서"]
    assert payload["events"][0]["starts_at"] == "2026-10-02T21:30:00+09:00"
    assert payload["events"][0]["source_url"].endswith("/bls.ics")
    assert [item["title"] for item in payload["past_events"]] == ["미국 CPI 소비자물가지수"]


def test_public_us_market_calendar_contract_and_upstream_failure(monkeypatch):
    async def fake_calendar(*, days):
        assert days == 16
        return {"events": [{"id": "us-employment"}], "past_events": []}

    monkeypatch.setattr(main_module, "build_us_market_calendar", fake_calendar)
    client = TestClient(app)
    response = client.get("/us/market/calendar?days=16")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    assert response.json()["events"][0]["id"] == "us-employment"
    assert client.get("/us/market/calendar?days=32").status_code == 422

    async def failed_calendar(*, days):
        raise DashboardMarketDataError("BLS unavailable")

    monkeypatch.setattr(main_module, "build_us_market_calendar", failed_calendar)
    failure = client.get("/us/market/calendar?days=16")
    assert failure.status_code == 502
    assert failure.json()["detail"] == "미국 주요 일정을 불러오지 못했습니다."


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
    assert STRATEGY_VERSION == "position-lifecycle-v7.4.2"
    assert ENTRY_EVIDENCE_STRATEGY_VERSION == "position-lifecycle-v7.0"
    assert STRATEGY_VERSION != ENTRY_EVIDENCE_STRATEGY_VERSION
