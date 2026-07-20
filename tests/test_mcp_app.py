from __future__ import annotations

from app.mcp_app import mcp_health_payload, mcp_ready_payload


def test_mcp_health_payload_exposes_submit_ready_fields():
    payload = mcp_health_payload()

    assert payload["status"] == "ok"
    assert "app" in payload
    assert "mcp_server_name" in payload
    assert "bootstrap_on_start" in payload


def test_mcp_ready_payload_exposes_runtime_checks():
    payload = mcp_ready_payload()

    assert payload["status"] == "ok"
    assert payload["database_ok"] is True
    assert "mcp_sdk_available" in payload
    assert "mcp_server_available" in payload
    assert "briefing_runtime_running" in payload
