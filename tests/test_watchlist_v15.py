from fastapi.testclient import TestClient

from app.main import app


def test_watchlist_v15_shell_and_asset_version():
    client = TestClient(app)
    shell = client.get("/dashboard?view=watchlist")

    assert shell.status_code == 200
    assert 'id="watchlist-view" class="watchlist-v15 watchlist-v2 watchlist-v3" data-ui-version="3.0"' in shell.text
    assert 'name="application-version" content="3.4"' in shell.text
    assert "20260725v42" in shell.text
    assert 'class="watch-v2-filter watch-v3-tabs"' in shell.text
    assert 'class="watch-v3-stock-section"' in shell.text
    assert shell.text.index('id="watchlist-strategy"') < shell.text.index('class="watch-v2-filter watch-v3-tabs"')

    for view_id in ("home-view", "search-view", "portfolio-view", "chart-view"):
        view_markup = shell.text.split(f'id="{view_id}"', 1)[1].split("</section>", 1)[0]
        assert 'class="app-page-intro' not in view_markup
    assert shell.text.index('class="watch-v2-filter watch-v3-tabs"') < shell.text.index('class="watch-v3-stock-section"')


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
        "/* Dashboard stock-detail fidelity 3.3 */",
        "#recommend-history-view .recommend-history.archive-page",
        "#trend-view .trend-tabs",
        "width: calc(100% + 40px) !important;",
        ".market-impact-hero",
        ".market-impact-node",
        ".market-impact-metric",
        ".market-impact-stock-tags a",
        ".push-notification-condition",
        "box-shadow: none !important;",
        "border-radius: 8px;",
        "border-radius: 6px;",
        "border-radius: 0;",
    ):
        assert expected in styles

    for expected in (
        "/* Watchlist 3.1:",
        "#watchlist-view.watchlist-v3",
        "grid-template-columns: minmax(0, 1fr);",
        "grid-template-columns: repeat(2, minmax(0, 1fr));",
        "@media (max-width: 720px)",
        "grid-template-columns: repeat(3, minmax(0, 1fr));",
        '"Apple SD Gothic Neo"',
        "overflow: clip;",
        "flex-direction: row;",
        "align-items: flex-start;",
        ".watch-v3-tabs button.active::after",
        "font-size: 16px !important;",
    ):
        assert expected in styles

    assert "#watchlist-view.watchlist-v3 .watch-v2-list-surface" in styles
    assert "#watchlist-view.watchlist-v3 .watchlist-empty-card" in styles


def test_dashboard_v32_uses_stock_detail_typography_on_every_page():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "/* Dashboard typography system 3.2:",
        "--app-type-page: 24px;",
        "--app-type-section: 20px;",
        "--app-type-body: 14px;",
        "--app-type-label: 11px;",
        "--app-type-metric: 15px;",
        "--app-type-page: 20px;",
        "--app-type-tab: 16px;",
        "--app-type-section: 19px;",
        "--app-type-body: 15px;",
        "--app-type-label: 12px;",
        ".market-leaderboard-name strong",
        ".recommend-name strong",
        ".watch-chart-row-main strong",
        ".loading-modal-card h2",
        ".push-notification-sheet-head h2",
        ".login-card h1",
    ):
        assert expected in styles
