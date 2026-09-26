from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

if sys.version_info < (3, 10):
    pytest.skip("MCP SDK tests require Python 3.10+", allow_module_level=True)

mcp = pytest.importorskip("mcp")

from app.config import get_settings  # noqa: E402
from app.mcp_server import _format_reports, build_insight_mcp_server, mcp_sdk_available  # noqa: E402


def test_mcp_research_links_use_the_same_mobile_safe_normalization():
    payload = _format_reports(
        [
            SimpleNamespace(
                title="SK하이닉스 목표가 상향",
                company_name="SK하이닉스",
                stock_code="000660",
                broker_name="DB증권",
                opinion="매수",
                target_price=2_300_000,
                published_at=None,
                source="stockhub",
                external_id="stockhub-16331",
                detail_url="https://www.db-fi.com/bbs/board.php?bo_table=research",
                pdf_url=None,
                source_category="company",
            )
        ]
    )

    assert payload[0]["detail_url"] == "https://www.stockhub.kr/stock/000660"


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
