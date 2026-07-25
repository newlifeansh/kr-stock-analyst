from fastapi.testclient import TestClient

from app.main import app


def test_watchlist_v15_shell_and_asset_version():
    client = TestClient(app)
    shell = client.get("/dashboard?view=watchlist")

    assert shell.status_code == 200
    assert 'id="watchlist-view" class="watchlist-v15 watchlist-v2" data-ui-version="1.5"' in shell.text
    assert 'name="application-version" content="1.5"' in shell.text
    assert "20260725v17" in shell.text


def test_watchlist_v15_uses_progressive_real_time_cards():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    for expected in (
        'className = "watch-stock-card watch-v2-stock-row"',
        'className = "watch-v15-metrics watch-v2-metrics"',
        'evidence.className = "watch-v2-evidence"',
        'footer.className = "watch-v2-row-footer"',
        'el("h2", "", headline)',
        'el("h3", "", "먼저 볼 종목")',
        "scheduleWatchlistStrategyRender();",
        "applyWatchlistFilter();",
        'state.watchlistFilter = button.dataset.watchFilter || "all";',
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
        "/* Watchlist 2.0:",
        "#watchlist-view.watchlist-v2",
        "grid-template-columns: minmax(0, 1fr);",
        "grid-template-columns: repeat(4, minmax(0, 1fr));",
        "@media (max-width: 720px)",
        "grid-template-columns: repeat(3, minmax(0, 1fr));",
        '"Apple SD Gothic Neo"',
        "overflow: clip;",
        "flex-direction: row;",
        "align-items: flex-start;",
    ):
        assert expected in styles

    assert "#watchlist-view.watchlist-v2 .watch-v2-list-surface" in styles
    assert "#watchlist-view.watchlist-v2 .watchlist-empty-card" in styles
