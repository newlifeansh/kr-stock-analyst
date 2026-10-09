from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

if sys.version_info < (3, 10):
    pytest.skip("MCP SDK tests require Python 3.10+", allow_module_level=True)

pytest.importorskip("mcp")

from app.config import Settings  # noqa: E402
from app.us_mcp_app import PersonalMCPAccessMiddleware, us_mcp_health_payload  # noqa: E402
from app.us_mcp_server import (  # noqa: E402
    US_MCP_ANALYSIS_CACHE,
    build_us_mcp_server,
    get_us_stock_analysis_payload,
    list_us_stock_signals_payload,
)


def _public_reasons() -> list[dict[str, object]]:
    return [
        {
            "key": "trend_20d",
            "label": "20일 가격",
            "state": "positive",
            "summary": "최근 20일 가격 흐름이 우호적입니다.",
            "as_of": "2026-09-25",
            "available": True,
        },
        {
            "key": "trend_60d",
            "label": "60일 가격",
            "state": "positive",
            "summary": "최근 60일 가격 흐름이 우호적입니다.",
            "as_of": "2026-09-25",
            "available": True,
        },
        {
            "key": "flow",
            "label": "거래대금 참여도",
            "state": "neutral",
            "summary": "거래대금 참여도가 중립입니다.",
            "as_of": "2026-09-25",
            "available": True,
        },
    ]


def _ready_feed() -> dict[str, object]:
    signal = {
        "code": "NVDA",
        "name": "NVIDIA",
        "market": "NASDAQ",
        "currency": "USD",
        "data_state": "ready",
        "is_preliminary": True,
        "signal_date": "2026-09-25",
        "signal_at": "2026-09-25T16:00:00-04:00",
        "public_reasons": _public_reasons(),
        "current": {
            "action": "entry_watch",
            "label": "예비 포착",
            "position_open": False,
            "model_exposure_percent": 0,
            "as_of": "2026-09-25",
        },
    }
    return {
        "status": "ready",
        "data_state": "ready",
        "strategy_version": "position-lifecycle-us-v2-rc1",
        "rollout_mode": "model_replay",
        "execution_enabled": False,
        "snapshot_id": "position-lifecycle-us-v2-rc1:2026-09-25:0123456789abcdef",
        "snapshot_checksum": "0" * 64,
        "snapshot_generated_at": "2026-09-26T01:00:00+00:00",
        "universe_as_of": "2026-09-25",
        "universe_count": 100,
        "evaluated_count": 100,
        "data_coverage_count": 100,
        "signal_eligible_count": 100,
        "insufficient_history_count": 0,
        "new_entries_allowed": True,
        "coverage": {"complete": True},
        "methodology": ["fixture"],
        "universe_members": [
            {"code": "NVDA", "name": "NVIDIA", "market": "NASDAQ"}
        ],
        "public_member_signals": [signal],
        "items": [signal],
        "preliminary_history": [],
    }


def _dashboard() -> dict[str, object]:
    return {
        "code": "NVDA",
        "name": "NVIDIA",
        "market": "NASDAQ",
        "as_of": datetime(2026, 9, 25, 20, 0, tzinfo=timezone.utc),
        "quote": {"price": 180, "change_rate": 1.2, "trading_value": 1_000_000},
        "momentum": {
            "one_month_return": 8,
            "three_month_return": 14,
            "trading_value_change": 3,
        },
        "chart_analysis": {"score": 72, "stance": "상승", "signals": [], "risks": []},
        "revisions": {},
        "surprise": {},
        "flows": {
            "stock_dollar_volume_change": 0.2,
            "sector_etf_dollar_volume_change": 0.1,
            "etf_symbol": "SOXX",
        },
        "valuation": {},
        "sentiment": {"score": 2, "latest_items": []},
        "macro_sensitivity": {},
        "coverage": {"price": True, "flow": True, "news": True},
    }


def test_us_mcp_server_exposes_only_personal_signal_and_analysis_tools():
    server = build_us_mcp_server(Settings())
    assert server is not None

    from mcp.shared.memory import create_connected_server_and_client_session

    async def run() -> set[str]:
        async with create_connected_server_and_client_session(server) as client:
            response = await client.list_tools()
            return {tool.name for tool in response.tools}

    assert asyncio.run(run()) == {
        "list_us_stock_signals",
        "get_us_stock_analysis",
    }


def test_us_mcp_signal_list_reads_stored_snapshot_without_refresh(monkeypatch):
    monkeypatch.setattr("app.us_mcp_server._load_us_feed", lambda: _ready_feed())

    payload = list_us_stock_signals_payload(limit=5, recent_days=14)

    assert payload["snapshot_id"].endswith("0123456789abcdef")
    assert payload["items"][0]["code"] == "NVDA"
    assert payload["items"][0]["current"]["action"] == "entry_watch"
    assert payload["delivery"] == {
        "market": "US",
        "source_mode": "stored_snapshot",
        "upstream_refresh_allowed": False,
        "execution_enabled": False,
    }
    assert "universe_members" not in payload
    assert "public_member_signals" not in payload


def test_us_mcp_stock_analysis_uses_cached_non_refresh_dashboard(monkeypatch):
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr("app.us_mcp_server._load_us_feed", lambda: _ready_feed())
    monkeypatch.setattr(
        "app.us_mcp_server.resolve_us_stock",
        lambda symbol: {"code": "NVDA", "name": "NVIDIA", "market": "NASDAQ"},
    )

    def fake_dashboard(symbol: str, refresh: bool = False):
        calls.append((symbol, refresh))
        return _dashboard()

    monkeypatch.setattr("app.us_mcp_server.build_us_dashboard", fake_dashboard)
    US_MCP_ANALYSIS_CACHE.clear()

    first = get_us_stock_analysis_payload("NVDA")
    second = get_us_stock_analysis_payload("nvda")

    assert calls == [("NVDA", False)]
    assert first["snapshot"] == second["snapshot"]
    assert first["signal"] == second["signal"]
    assert first["analysis"]["snapshot_id"] == second["analysis"]["snapshot_id"]
    assert first["ok"] is True
    assert first["signal"]["current"]["action"] == "entry_watch"
    assert first["analysis"]["current"]["action"] == "entry_watch"
    assert first["analysis"]["snapshot_id"].endswith("0123456789abcdef")
    assert first["delivery"]["upstream_refresh_allowed"] is False
    assert first["delivery"]["execution_enabled"] is False
    assert "trade_levels" not in first["analysis"]


def test_personal_us_mcp_requires_bearer_token_and_limits_bursts():
    async def ok(_):
        return JSONResponse({"ok": True})

    app = Starlette(
        routes=[
            Route("/healthz", ok),
            Route("/rpc", ok, methods=["POST"]),
        ]
    )
    app.add_middleware(
        PersonalMCPAccessMiddleware,
        bearer_token="personal-secret",
        rate_limit_per_minute=2,
        require_configured_token=True,
    )

    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.post("/rpc").status_code == 401
        assert client.post(
            "/rpc", headers={"Authorization": "Bearer wrong"}
        ).status_code == 401
        headers = {"Authorization": "Bearer personal-secret"}
        assert client.post("/rpc", headers=headers).status_code == 200
        assert client.post("/rpc", headers=headers).status_code == 200
        limited = client.post("/rpc", headers=headers)
        assert limited.status_code == 429
        assert limited.headers["Retry-After"]


def test_personal_us_mcp_remote_health_fails_closed_without_token():
    settings = Settings(
        mcp_public_base_url="https://us-mcp.example.com",
        us_mcp_bearer_token=None,
    )

    payload = us_mcp_health_payload(settings, server_available=True)

    assert payload["auth_configured"] is False
    assert payload["remote_access_ready"] is False
    assert "bearer_token" not in payload
