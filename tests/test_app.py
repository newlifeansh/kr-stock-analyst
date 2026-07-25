from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    healthz = client.get("/healthz")
    assert healthz.status_code == 200
    assert healthz.json()["status"] == "ok"

    readyz = client.get("/readyz")
    assert readyz.status_code == 200
    assert readyz.json()["database_ok"] is True


def test_root_redirects_to_korea_dashboard():
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard?view=home"


def test_watchlist_share_id_roundtrip():
    client = TestClient(app)
    share_id = "codex-test-watchlist"
    payload = {"items": [{"code": "005930", "name": "삼성전자", "market": "KOSPI"}]}
    token_response = client.get(f"/session/write-token?share_id={share_id}")
    assert token_response.status_code == 200
    write_token = token_response.json()["write_token"]

    saved = client.put(f"/watchlists/{share_id}", json=payload, headers={"X-Write-Token": write_token})
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["share_id"] == share_id
    assert saved_body["items"] == payload["items"]

    loaded = client.get(f"/watchlists/{share_id}")
    assert loaded.status_code == 200
    assert loaded.json()["items"] == payload["items"]


def test_briefing_status():
    client = TestClient(app)
    response = client.get("/briefings/status")
    assert response.status_code == 200
    body = response.json()
    assert "enabled" in body
    assert "poll_seconds" in body
    assert "research_enabled" in body
    assert "research_poll_seconds" in body
    assert "disclosure_enabled" in body
    assert "news_enabled" in body
    assert "price_enabled" in body
    assert "toss_enabled" in body
    assert "toss_sync_holdings_enabled" in body
    assert "disclosure_poll_seconds" in body
    assert "news_poll_seconds" in body
    assert "price_poll_seconds" in body
    assert "investor_flow_enabled" in body
    assert "investor_flow_poll_seconds" in body
    assert "financials_enabled" in body
    assert "financials_poll_seconds" in body
    assert "fundamental_snapshot_enabled" in body
    assert "fundamental_snapshot_poll_seconds" in body
    assert "macro_enabled" in body
    assert "macro_poll_seconds" in body
    assert "toss_poll_seconds" in body
    assert "toss_order_poll_seconds" in body
    assert "last_price_at" in body
    assert "last_investor_flow_at" in body
    assert "last_financials_at" in body
    assert "last_fundamental_snapshot_at" in body
    assert "last_macro_at" in body
    assert "source_errors" in body


def test_insight_shell_and_feed():
    client = TestClient(app)

    shell = client.get("/insight")
    assert shell.status_code == 200
    assert "text/html" in shell.headers["content-type"]
    assert "<title>인사이트</title>" in shell.text

    dashboard_shell = client.get("/dashboard")
    assert dashboard_shell.status_code == 200
    assert "text/html" in dashboard_shell.headers["content-type"]
    assert "비밀노트" in dashboard_shell.text

    nasdaq_shell = client.get("/nasdaq")
    assert nasdaq_shell.status_code == 200
    assert "text/html" in nasdaq_shell.headers["content-type"]
    assert "미국증시" in nasdaq_shell.text

    portfolio_shell = client.get("/portfolio")
    assert portfolio_shell.status_code == 200
    assert "AI 주식 정보 서비스 제품 사례" in portfolio_shell.text
    assert "6가지" in portfolio_shell.text
    assert "핵심 기능" in portfolio_shell.text

    concepts_shell = client.get("/concepts")
    assert concepts_shell.status_code == 200
    assert "주식 정보 서비스 디자인 탐색" in concepts_shell.text
    assert "Market Pulse" in concepts_shell.text
    assert "Equity Lens" in concepts_shell.text
    assert "My Signals" in concepts_shell.text

    feed = client.get("/insight/feed")
    assert feed.status_code == 200
    body = feed.json()
    assert "research_reports" in body
    assert "disclosures" in body
    assert "news_items" in body
    assert "company_briefs" in body
    assert "briefing_quotes" in body
    assert "watch_codes" in body
    assert "latest_prices" in body
    assert "toss_status" in body
    assert "toss_accounts" in body
    assert "toss_holdings" in body
    assert "toss_orders" in body


def test_watch_point_expansion_survives_market_data_refresh():
    client = TestClient(app)

    for asset_path in ("/assets/dashboard/app.js", "/assets/nasdaq/app.js"):
        response = client.get(asset_path)
        assert response.status_code == 200
        source = response.text
        assert 'const keepExpanded = itemCode ? state.watchPreopenExpanded.has(itemCode) : false;' in source
        assert 'section.dataset.mode !== "regular"' not in source
        assert "state.watchPreopenExpanded.delete(itemCode)" not in source

    dashboard_source = client.get("/assets/dashboard/app.js").text
    assert "이벤트·뉴스·거시·수급·미국 섹터를 종합해 우선순위를 계산합니다." not in dashboard_source


def test_stock_research_links_open_in_current_view_and_tab_survives_refresh():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    assert 'title.target = "_blank"' not in source
    assert 'title.setAttribute("aria-label", `${report.title || "리포트"} 원문 보기`);' in source
    assert 'previousStock?.code && previousStock.code !== stock.code' in source
    assert 'setActiveStockTab(state.stockActiveTab || "summary", { preserveScroll: true });' in source


def test_dashboard_shows_shared_loading_state_for_navigation_and_stock_lookup():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="page-loading"' in shell
    assert 'id="page-loading-label"' in shell
    assert "function runPageLoading" in source
    assert "function launchPageLoading" in source
    assert "function clearPageLoading" in source
    assert "return runPageLoading(PAGE_LOADING_LABELS.stock" in source
    assert "function launchBriefPageLoading" in source
    for view in ("market", "watchlist", "recommend", "trend", "chart"):
        assert f"PAGE_LOADING_LABELS.{view.replace('-', '_')}" in source or f'PAGE_LOADING_LABELS["{view}"]' in source


def test_dashboard_v3_uses_four_primary_views_and_nested_market_tabs():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    live_index = shell.index('data-trend-tab="live"')
    events_index = shell.index('data-trend-tab="events"')
    impact_index = shell.index('data-trend-tab="impact"')
    assert live_index < events_index < impact_index
    assert '>실시간</button>' in shell
    assert '>주요 이벤트</button>' in shell
    assert '>시장 영향</button>' in shell
    assert 'class="trend-summary"' not in shell
    assert 'id="trend-headline"' not in shell
    assert 'id="home-view"' in shell
    assert 'id="search-view"' in shell
    assert 'id="portfolio-view"' in shell
    assert 'id="chart-view"' in shell
    assert 'id="discovery-search-form"' in shell
    assert 'id="portfolio-watchlist-panel"' in shell
    assert 'id="chart-stock-search-form"' in shell
    assert 'id="trend-watch-stock-rail"' in shell
    assert 'id="trend-watch-news-board"' in shell
    assert 'id="trend-topbar" hidden' in shell
    assert 'class="side-nav"' not in shell
    nav_order = [
        shell.index('data-app-view="home"'),
        shell.index('data-app-view="search"'),
        shell.index('data-app-view="portfolio"'),
        shell.index('data-app-view="chart"'),
    ]
    assert nav_order == sorted(nav_order)
    assert 'trend: "home"' in source
    assert 'market: "search"' in source
    assert 'watchlist: "portfolio"' in source
    assert 'const initialView = hasStockDetailPath ? "stock" : (LEGACY_VIEW_MAP[requestedView] || "home");' in source


def test_dashboard_restores_the_visible_view_on_browser_history_navigation():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    assert 'window.addEventListener("popstate"' in source
    assert "syncViewFromLocation" in source


def test_watchlist_news_deduplicates_matching_headlines():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    assert "const seenTitles = new Set();" in source
    assert "seenTitles.has(normalizedTitle)" in source


def test_trend_watchlist_mobile_layout_stays_inside_viewport():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    assert "width: calc(100vw - 28px);" in styles
    assert "width: calc(100vw - 24px);" in styles
    assert "contain: inline-size;" in styles
    assert ".trend-watch-news-item > span" in styles
    assert "overflow-wrap: anywhere !important;" in styles


def test_mobile_stock_evidence_sections_share_one_alignment():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    assert "#stock-view #stock-evidence-section > .evidence-core-grid" in styles
    assert "padding-inline: 0 !important;" in styles


def test_push_settings_include_device_test_action():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="push-notification-sheet-test-button"' in shell
    assert "/push/subscriptions/${encodeURIComponent(state.watchlistId)}/test" in source
    assert "iPhone은 홈 화면에 설치한 비밀노트 앱에서만 알림을 받을 수 있습니다." in source


def test_meta_endpoints():
    client = TestClient(app)

    cadence = client.get("/meta/insight-cadence")
    assert cadence.status_code == 200
    cadence_body = cadence.json()
    assert cadence_body["thread_id"] == "019ed577-3961-7f30-b9da-05112758804a"
    assert cadence_body["intraday_loops"]
    assert cadence_body["review_cycles"]

    sources = client.get("/meta/research-sources")
    assert sources.status_code == 200
    source_body = sources.json()
    assert any(item["key"] == "naver_finance" for item in source_body)
    assert any(item["is_active_collector"] for item in source_body)

    integrations = client.get("/meta/integrations")
    assert integrations.status_code == 200
    integration_body = integrations.json()
    toss = next(item for item in integration_body if item["key"] == "toss_securities")
    assert toss["integration_type"] == "broker_api"
    assert toss["required_settings"]


def test_toss_status_endpoint():
    client = TestClient(app)
    response = client.get("/toss/status")
    assert response.status_code == 200
    body = response.json()
    assert "configured" in body
    assert "base_url" in body
    assert "order_poll_seconds" in body


def test_company_briefs_endpoint():
    client = TestClient(app)
    response = client.get("/company-briefs?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
