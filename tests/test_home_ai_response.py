from pathlib import Path


APP_JS = Path(__file__).parents[1] / "app" / "static" / "dashboard" / "app.js"
DASHBOARD_CSS = Path(__file__).parents[1] / "app" / "static" / "dashboard" / "styles.css"


def app_source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def dashboard_styles() -> str:
    return DASHBOARD_CSS.read_text(encoding="utf-8")


def test_home_market_volatility_copy_is_not_visually_clipped() -> None:
    styles = dashboard_styles()
    card_start = styles.rindex('body:not([data-view="stock"]) .home-ai-response {')
    card_rule = styles[card_start:styles.index("}\n", card_start) + 1]
    title_start = styles.rindex('body:not([data-view="stock"]) .home-ai-response h3 {')
    title_rule = styles[title_start:styles.index("}\n", title_start) + 1]

    assert "min-height" not in card_rule
    assert "display: block;" in title_rule
    assert "overflow: visible;" in title_rule
    assert "text-overflow: clip;" in title_rule
    assert "-webkit-line-clamp: unset;" in title_rule
    assert "-webkit-line-clamp: 1;" not in title_rule


def test_home_ai_response_uses_realtime_market_context() -> None:
    source = app_source()

    assert 'const US_SECTOR_STREAM_VIEWS = new Set(["home", "search", "portfolio"]);' in source
    assert "function majorMarketIssueContext" in source
    assert "function upcomingMarketEventContext" in source
    assert "function usSectorMarketContext" in source
    assert "const context = selectHomeMarketContext();" in source
    assert "homeContextAttentionSentence(context, items)" in source
    assert "function homeAiResponseSentences" in source
    assert "homeAiResponseSentences(context?.sentence || homeMarketVolatilitySentence())" in source


def test_home_trend_payload_refreshes_ai_response() -> None:
    source = app_source()

    assert "state.homeTrendContext = payload;" in source
    assert 'if (state.view === "home") {\n      renderHomeAiResponse();' in source
    assert 'void refreshUsSectorMoves({ force: true, ttlMs: 0 });' in source
    assert "connectUsSectorStream();" in source


def test_market_context_priority_is_explicit() -> None:
    source = app_source()
    start = source.index("function selectHomeMarketContext()")
    end = source.index("function normalizedHomeThemes", start)
    selector = source[start:end]

    assert selector.index("majorMarketIssueContext") < selector.index("usSectorMarketContext")
    assert selector.index("usSectorMarketContext") < selector.index("upcomingMarketEventContext")
    assert "Math.abs(sector.rate) >= 1.5" in selector
