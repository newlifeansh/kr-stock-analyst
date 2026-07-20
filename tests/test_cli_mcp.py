from __future__ import annotations

from app.cli import verify_mcp_endpoint_payload


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status={self.status_code}")

    def json(self) -> dict[str, object]:
        return self._payload


def test_verify_mcp_endpoint_payload_collects_summary(monkeypatch):
    responses = iter(
        [
            _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "serverInfo": {"name": "한국증시 비밀노트"},
                    },
                }
            ),
            _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {"name": "get_market_briefing"},
                            {"name": "search_korea_stocks"},
                        ]
                    },
                }
            ),
            _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "result": {
                        "structuredContent": {
                            "count": 1,
                            "stocks": [{"code": "005930", "name": "삼성전자"}],
                        }
                    },
                }
            ),
            _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "result": {
                        "structuredContent": {
                            "configured_sources": {"reports": True, "disclosures": True},
                        }
                    },
                }
            ),
        ]
    )

    def fake_post(url, headers, json, timeout):  # noqa: A002
        assert url == "https://example.com/mcp/"
        assert headers["Accept"] == "application/json, text/event-stream"
        assert timeout == 15
        return next(responses)

    monkeypatch.setattr("app.cli.requests.post", fake_post)

    payload = verify_mcp_endpoint_payload(
        "https://example.com/mcp/",
        query="삼성전자",
        timeout=15,
        limit=2,
    )

    assert payload["ok"] is True
    assert payload["server_name"] == "한국증시 비밀노트"
    assert payload["tool_count"] == 2
    assert payload["search_count"] == 1
    assert payload["search_preview"] == [{"code": "005930", "name": "삼성전자"}]
    assert payload["pipeline_status"] == {"configured_sources": {"reports": True, "disclosures": True}}


def test_verify_mcp_endpoint_payload_raises_on_rpc_error(monkeypatch):
    responses = iter(
        [
            _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "serverInfo": {"name": "한국증시 비밀노트"},
                    },
                }
            ),
            _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "error": {"code": -32601, "message": "method not found"},
                }
            ),
        ]
    )

    def fake_post(url, headers, json, timeout):  # noqa: A002
        return next(responses)

    monkeypatch.setattr("app.cli.requests.post", fake_post)

    try:
        verify_mcp_endpoint_payload("https://example.com/mcp/")
    except RuntimeError as exc:
        assert "tools/list failed" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected RuntimeError")
