from __future__ import annotations

import asyncio
import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip("MCP SDK tests require Python 3.10+", allow_module_level=True)

mcp = pytest.importorskip("mcp")

from app.config import get_settings
from app.mcp_server import build_insight_mcp_server, mcp_sdk_available


def test_mcp_server_lists_expected_tools():
    assert mcp_sdk_available()
    server = build_insight_mcp_server(get_settings())
    assert server is not None

    from mcp.shared.memory import create_connected_server_and_client_session

    async def run() -> set[str]:
        async with create_connected_server_and_client_session(server) as client:
            response = await client.list_tools()
            return {tool.name for tool in response.tools}

    tool_names = asyncio.run(run())
    assert "get_market_briefing" in tool_names
    assert "search_korea_stocks" in tool_names
    assert "get_korea_stock_dashboard" in tool_names
    assert "get_market_impact" in tool_names


def test_mcp_server_pipeline_status_tool_returns_payload():
    server = build_insight_mcp_server(get_settings())
    assert server is not None

    from mcp.shared.memory import create_connected_server_and_client_session

    async def run():
        async with create_connected_server_and_client_session(server) as client:
            return await client.call_tool("get_data_pipeline_status", {})

    result = asyncio.run(run())
    assert result.structuredContent is not None
    assert "configured_sources" in result.structuredContent
