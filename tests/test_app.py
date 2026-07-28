from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal, init_db
from app.main import app
from app.models import PushNotificationHistory, WatchlistItem


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


def test_push_notification_history_keeps_only_recent_three_days():
    init_db()
    client = TestClient(app)
    share_id = "codex-push-history"
    token_response = client.get(f"/session/write-token?share_id={share_id}")
    assert token_response.status_code == 200
    write_token = token_response.json()["write_token"]
    now = datetime.utcnow()
    with SessionLocal() as db:
        db.execute(delete(PushNotificationHistory).where(PushNotificationHistory.share_id == share_id))
        db.add_all(
            [
                PushNotificationHistory(
                    share_id=share_id,
                    event_key="recent:event",
                    notification_kind="price_move",
                    title="최근 알림",
                    body="최근 3일 안에 받은 알림입니다.",
                    url="/dashboard/삼성전자",
                    created_at=now - timedelta(hours=2),
                ),
                PushNotificationHistory(
                    share_id=share_id,
                    event_key="expired:event",
                    notification_kind="report",
                    title="지난 알림",
                    body="보관 기간을 지났습니다.",
                    url="/dashboard/삼성전자",
                    created_at=now - timedelta(days=4),
                ),
            ]
        )
        db.commit()
    try:
        denied = client.get(f"/push/notifications/{share_id}")
        assert denied.status_code == 403

        response = client.get(
            f"/push/notifications/{share_id}",
            headers={"X-Write-Token": write_token},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["retention_days"] == 3
        assert [item["title"] for item in payload["items"]] == ["최근 알림"]
        assert payload["items"][0]["created_at"].endswith("Z")
        with SessionLocal() as db:
            remaining = list(
                db.scalars(
                    PushNotificationHistory.__table__.select().where(
                        PushNotificationHistory.share_id == share_id
                    )
                )
            )
            assert len(remaining) == 1
    finally:
        with SessionLocal() as db:
            db.execute(delete(PushNotificationHistory).where(PushNotificationHistory.share_id == share_id))
            db.commit()


def test_dashboard_notification_button_opens_notification_page_before_settings():
    client = TestClient(app)
    shell = client.get("/dashboard?view=home").text
    source = client.get("/assets/dashboard/app.js").text

    for expected in (
        'id="notifications-view"',
        'id="push-history-tabs"',
        'data-notification-tab="all"',
        'data-notification-tab="ai_signal"',
        'data-notification-tab="watchlist"',
        'data-notification-tab="major_event"',
        'id="push-history-settings"',
        'id="push-history-list"',
        'id="push-notification-unread-dot"',
        'class="secondary-commandbar notifications-commandbar"',
    ):
        assert expected in shell
    for expected in (
        "async function openPushNotificationCenter()",
        "const likelyEnabled = state.pushNotificationEnabled",
        "function setPushNotificationUnread(unread)",
        "function hydratePushNotificationHistory()",
        'setView("notifications");',
        'if (view === "notifications")',
        'history.replaceState(null, "", "/dashboard?view=notifications");',
        'const nextTab = tab.dataset.notificationTab || "all";',
        "pushNotificationHistoryScrollTop: new Map()",
        "renderPushNotificationHistory({ restoreScroll: true });",
        'fetch(`/push/notifications/${encodeURIComponent(state.watchlistId)}`',
        'elements.pushHistorySettings?.addEventListener("click", openPushSettingsFromHistory)',
    ):
        assert expected in source


def test_secondary_pages_use_stock_detail_navigation_contract():
    client = TestClient(app)
    shell = client.get("/dashboard?view=home").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'class="secondary-commandbar notifications-commandbar"',
        'class="secondary-commandbar ai-signals-commandbar"',
        'class="secondary-commandbar market-ranking-commandbar"',
        'class="secondary-commandbar recommend-detail-topbar"',
        'class="secondary-commandbar chart-history-commandbar"',
        'class="secondary-commandbar-back notifications-back"',
        'id="ai-signals-back"',
        'class="secondary-commandbar-back market-ranking-back"',
        'id="chart-history-back-button"',
    ):
        assert expected in shell

    assert '<header class="app-page-intro"><span>저장 기록</span>' not in shell
    assert "Secondary navigation 6.0" in styles
    for view in ("notifications", "ai-signals", "movers", "recommend-detail", "chart-history"):
        assert f'[data-view="{view}"]' in styles
    assert ":is(.app-topbar, .bottom-nav)" in styles
    assert "grid-template-columns: 42px minmax(0, 1fr) 42px" in styles


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


def test_watchlist_update_preserves_existing_item_added_at():
    init_db()
    client = TestClient(app)
    share_id = "codex-watchlist-added-at"
    token_response = client.get(f"/session/write-token?share_id={share_id}")
    write_token = token_response.json()["write_token"]
    headers = {"X-Write-Token": write_token}
    first_payload = {
        "items": [{"code": "005930", "name": "삼성전자", "market": "KOSPI"}]
    }
    second_payload = {
        "items": [
            {"code": "005930", "name": "삼성전자", "market": "KOSPI"},
            {"code": "000660", "name": "SK하이닉스", "market": "KOSPI"},
        ]
    }
    try:
        assert client.put(f"/watchlists/{share_id}", json=first_payload, headers=headers).status_code == 200
        with SessionLocal() as db:
            first_added_at = db.scalar(
                WatchlistItem.__table__.select()
                .with_only_columns(WatchlistItem.created_at)
                .where(
                    WatchlistItem.share_id == share_id,
                    WatchlistItem.code == "005930",
                )
            )

        assert client.put(f"/watchlists/{share_id}", json=second_payload, headers=headers).status_code == 200
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    WatchlistItem.__table__.select()
                    .with_only_columns(WatchlistItem.created_at)
                    .where(
                        WatchlistItem.share_id == share_id,
                        WatchlistItem.code == "005930",
                    )
                )
            )
        assert rows == [first_added_at]
    finally:
        with SessionLocal() as db:
            db.execute(delete(WatchlistItem).where(WatchlistItem.share_id == share_id))
            db.commit()


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
    styles = client.get("/assets/dashboard/styles.css").text

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
    assert 'id="recommend-button"' not in shell
    assert '>추천받기<' not in shell
    assert 'loadRecommendations({ auto: true, force: true, recompute: true })' in source
    assert '추천 종목을 불러오는 중입니다.' in source
    assert 'const liveRefreshPromise = recompute' in source
    assert 'const initialPayload = await fetchLatestRecommendations();' in source
    assert 'id="portfolio-watchlist-panel"' in shell
    assert 'id="chart-stock-search-form"' in shell
    assert 'id="trend-watch-stock-rail"' in shell
    assert 'id="trend-watch-news-board"' in shell
    assert 'id="trend-topbar" hidden' in shell
    assert 'id="home-market-indices"' in shell
    assert 'id="home-market-signal-ticker"' in shell
    assert 'id="home-market-snapshot"' not in shell
    assert '>시장 상태<' not in shell
    assert 'id="home-ai-signals"' in shell
    assert 'id="home-ai-signals-more"' in shell
    assert 'id="ai-signals-view" class="app-page app-ai-signals"' in shell
    assert 'id="home-market-carousel"' in shell
    assert 'const HOME_MARKET_ASSET_ORDER = ["KOSDAQ", "KOSPI", "NASDAQ", "SP500", "GOLD", "OIL"]' in source
    assert 'liveUrl("/market/global-assets?limit=30")' in source
    assert 'id="home-index-shared-asof"' in shell
    assert 'id="home-kospi-asof"' not in shell
    assert 'id="home-kosdaq-asof"' not in shell
    assert "/market/indices?limit=30" in source
    assert "/market/quant-signals?universe_limit=100&limit=30&recent_days=30" not in source
    assert "function homeHoldingSignalItems" in source
    assert "function homeMarketSignalItems" in source
    assert 'label: isSell ? "매도" : "매수"' in source
    assert '`${signal.label} (${signal.date})`' in source
    assert 'formatPercent(returnRate)' not in source[source.index("function createHomeMarketSignalTickerRow"):source.index("function showHomeMarketSignalTickerItem")]
    assert "추세 유지 · 분할매도·청산 기준 미도달" in source
    assert "function startHomeMarketSignalTicker" in source
    assert '시총 상위 100' not in shell
    assert '시총 상위 종목의 최근 신호' not in shell
    assert 'class="home-flat-section-head"' in shell
    assert 'Home market briefing 7.2: reference-matched market strip and briefing rows.' in styles
    assert 'styles.css?v=20260728v132' in shell
    assert 'class="service-footer"' in shell
    assert '>안석환<' in shell
    assert 'href="https://www.linkedin.com/in/connor-sh"' in shell
    assert '>시장 변동성<' in shell
    assert '>관심종목 유의<' in shell
    assert 'function homeMarketVolatilitySentence' in source
    assert 'function homeAttentionSentence' in source
    assert 'app.js?v=20260728v132' in shell
    render_trends_source = source[source.index("function renderTrends"):source.index("async function loadTrends")]
    assert "const timeline = payload.timeline || [];" in render_trends_source
    assert ".filter(isFocusedTrendTimelineItem)" not in render_trends_source
    assert 'maximum-scale=1, user-scalable=no, viewport-fit=cover' in shell
    assert '/assets/zoom-lock.js?v=20260728z1' in shell
    assert 'env(safe-area-inset-top, 0px)' in styles
    assert 'min-height: calc(62px + env(safe-area-inset-top, 0px));' in styles
    assert 'border-radius: 50%;' in styles
    assert '0 0 12px rgba(32, 205, 105, 0.72)' in styles
    assert 'DASHBOARD_SW_VERSION = "20260728v132"' in client.get("/dashboard-sw.js").text
    assert '#trend-events-panel .trend-event' in styles
    assert 'padding-right: 0;' in styles
    assert 'padding-left: 0;' in styles
    assert 'id="logout-button"' not in shell
    assert ".app-notification-button svg" in styles
    assert "width: 25px;" in styles
    assert "height: 25px;" in styles
    assert "renderHomeMarketIndices" in source
    assert 'class="side-nav"' not in shell
    nav_order = [
        shell.index('data-app-view="home"'),
        shell.index('data-app-view="search"'),
        shell.index('data-app-view="portfolio"'),
        shell.index('data-app-view="chart"'),
    ]
    assert nav_order == sorted(nav_order)
    assert 'trend: "home"' in source


def test_chart_view_is_search_first_and_renders_five_or_ten_day_scenarios():
    client = TestClient(app)
    shell = client.get("/dashboard?view=chart").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="chart-view" class="app-page app-chart" data-ui-version="4.0"' in shell
    assert 'placeholder="궁금한 종목의 흐름 분석하기"' in shell
    assert "검색하면 이렇게 비교해드려요" in shell
    assert 'class="chart-example-svg"' in shell
    assert "최근 가격 흐름과 5일·10일 예상 범위를 한 차트에서 확인합니다." in shell
    assert 'id="chart-example-search-button"' not in shell
    assert 'id="chart-archive-button"' not in shell
    assert "차트 시나리오" not in shell
    assert 'id="chart-watchlist-picker"' not in shell
    assert "function computeChartForecast" in source
    assert "function renderChartForecastResult" in source
    assert "for (const days of [5, 10])" in source
    assert "실제 가격은 뉴스와 수급에 따라 예상 범위를 벗어날 수 있습니다." in source


def test_home_shows_top_five_movers_and_links_to_market_top_thirty_page():
    client = TestClient(app)
    shell = client.get("/dashboard?view=home").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="home-surge"' in shell
    assert 'id="home-surge-more"' in shell
    assert 'id="market-view" class="app-page app-market-rankings"' in shell
    assert (
        shell.index('id="home-market-indices"')
        < shell.index('id="home-ai-signals"')
        < shell.index('id="home-market-signal-ticker"')
        < shell.index('id="home-surge"')
        < shell.index('id="trend-view"')
    )
    assert shell.index('id="search-view"') > shell.index('id="market-view"')
    assert 'data-market-filter="KOSPI"' in shell
    assert 'data-market-filter="KOSDAQ"' in shell
    assert 'data-market-filter="ALL"' not in shell
    assert 'id="market-ranking-back"' in shell
    assert 'class="market-segment market-ranking-tabs"' in shell
    assert 'data-ui-version="5.0"' in shell
    assert '<h1>급등주</h1>' in shell
    assert 'function createMarketLeaderboardMetric' in source
    assert 'setView("home")' in source
    assert "function renderHomeSurgeRankings" in source
    assert 'formattedBasis.replace(/ 기준$/, " 장 마감 기준")' in source
    assert "function renderHomeAiSignals" in source
    assert 'return { key: "recent-buy", label: "최근 매수", tone: "buy", signalDate };' in source
    assert 'return { key: "holding", label: "보유 중", tone: "hold", signalDate };' in source
    assert 'return { key: "recent-sell", label: "최근 매도", tone: "sell", signalDate };' in source
    assert 'items.slice(0, 5).forEach' in source
    assert 'data-ai-signal-stage="recent-buy"' in shell
    assert 'data-ai-signal-stage="holding"' in shell
    assert 'data-ai-signal-stage="recent-sell"' in shell
    assert 'history.replaceState(null, "", "/dashboard?view=ai-signals")' in source
    assert 'setView("ai-signals")' in source
    assert "/quant-signals`" in source
    assert ".slice(0, 5)" in source
    assert 'limit: 30' in source
    assert 'ttlMs: pageEntryTtlMs("market")' in source
    assert 'force: false' in source
    assert 'history.replaceState(null, "", "/dashboard?view=movers")' in source
    assert 'market: "movers"' in source
    assert 'watchlist: "portfolio"' in source
    assert 'const initialView = hasStockDetailPath ? "stock" : (LEGACY_VIEW_MAP[requestedView] || "home");' in source


def test_dashboard_restores_the_visible_view_on_browser_history_navigation():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    assert 'window.addEventListener("popstate"' in source
    assert "syncViewFromLocation" in source


def test_dashboard_internal_navigation_does_not_render_the_logo_splash():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="app-splash"' not in shell
    assert "showAppSplash" not in source
    assert "APP_SPLASH_DURATION_MS" not in source
    assert "a, button, [role='button'], [role='link']" in source


def test_dashboard_uses_one_data_basis_date_format_across_views():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'function formatDataBasis(value, fallback = "기준 정보 확인 중")' in source
    assert 'return `${dateMatch[1]}${dateMatch[2] ? ` ${dateMatch[2]}` : ""} 기준`;' in source
    assert "setText(elements.stockHomeTodayDate, formatDataBasis(summaryDate));" in source
    assert "formatDataBasis(payload.as_of)" in source
    assert "formatDataBasis(model.asOf)" in source
    assert "기준 시간 :" not in source
    assert "기준 시각 확인 중" not in shell
    assert "최근 장 마감 기준" not in shell


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


def test_all_web_entrypoints_disable_pinch_zoom():
    client = TestClient(app)

    for path in ("/dashboard", "/insight", "/nasdaq", "/portfolio", "/concepts"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'maximum-scale=1, user-scalable=no, viewport-fit=cover' in response.text
        assert '/assets/zoom-lock.js?v=20260728z1' in response.text

    zoom_lock = client.get("/assets/zoom-lock.js")
    assert zoom_lock.status_code == 200
    assert "event.touches.length > 1" in zoom_lock.text
    assert '"gesturestart", "gesturechange", "gestureend"' in zoom_lock.text
