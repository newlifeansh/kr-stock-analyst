from pathlib import Path


APP_JS = Path(__file__).parents[1] / "app" / "static" / "dashboard" / "app.js"


def app_source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_home_ai_response_uses_realtime_market_context() -> None:
    source = app_source()

    assert 'const US_SECTOR_STREAM_VIEWS = new Set(["home", "search", "portfolio"]);' in source
    assert "function majorMarketIssueContext" in source
    assert "function upcomingMarketEventContext" in source
    assert "function usSectorMarketContext" in source
    assert "const context = selectHomeMarketContext();" in source
    assert "homeContextAttentionSentence(context, items)" in source


def test_home_trend_payload_refreshes_ai_response() -> None:
    source = app_source()

    assert "state.homeTrendContext = payload;" in source
    assert 'if (state.view === "home") {\n      renderHomeAiResponse();' in source
    assert "async function refreshHomeAiResponseContext" in source
    assert "loadTrends(trendTab, { force: false, ttlMs: 0 })" in source
    assert "refreshUsSectorMoves({ force: false, ttlMs: 0 })" in source
    assert "scheduleHomeAiResponseRefresh();" in source
    assert "connectUsSectorStream();" in source


def test_market_context_priority_is_explicit() -> None:
    source = app_source()
    start = source.index("function selectHomeMarketContext()")
    end = source.index("function normalizedHomeThemes", start)
    selector = source[start:end]

    assert selector.index("majorMarketIssueContext") < selector.index("usSectorMarketContext")
    assert selector.index("usSectorMarketContext") < selector.index("upcomingMarketEventContext")
    assert "Math.abs(sector.rate) >= 1.5" in selector
