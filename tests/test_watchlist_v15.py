from fastapi.testclient import TestClient

from app.main import app


def test_watchlist_v15_shell_and_asset_version():
    client = TestClient(app)
    shell = client.get("/dashboard?view=watchlist")

    assert shell.status_code == 200
    assert 'id="watchlist-view" class="watchlist-v15" data-ui-version="1.5"' in shell.text
    assert 'name="application-version" content="1.5"' in shell.text
    assert "20260725v16" in shell.text


def test_watchlist_v15_uses_progressive_real_time_cards():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    for expected in (
        'className = "watch-stock-card watch-v15-stock-card"',
        'className = "watch-v15-metrics"',
        'className = "watch-v15-context"',
        'className = "watch-v15-card-footer"',
        'el("h2", "", headline)',
        'el("h3", "", "우선 확인 종목")',
        "scheduleWatchlistStrategyRender();",
        "state.watchlistResults = [",
        'elements.watchlistMeta.textContent = `${items.length}개 종목 · ${completedCount}/${items.length}개 확인 중`;',
        'const keepExpanded = itemCode ? state.watchPreopenExpanded.has(itemCode) : false;',
        'action.textContent = "종목 검색 열기";',
    ):
        assert expected in source

    assert "watchDetailsExpanded" not in source
    assert 'className = "watch-stock-details"' not in source


def test_watchlist_v15_is_responsive_and_matches_stock_detail_tokens():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "/* Watchlist 1.5:",
        "#watchlist-view.watchlist-v15",
        "grid-template-columns: repeat(auto-fit, minmax(min(100%, 390px), 1fr));",
        "grid-template-columns: repeat(4, minmax(0, 1fr));",
        "@media (max-width: 720px)",
        "grid-template-columns: minmax(0, 1fr);",
        '"Apple SD Gothic Neo"',
        "overflow: clip;",
        "flex-direction: row;",
        "align-items: flex-start;",
    ):
        assert expected in styles

    assert "#watchlist-view.watchlist-v15 .watchlist-empty-card button" in styles
