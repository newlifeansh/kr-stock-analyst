from fastapi.testclient import TestClient

from app.main import app


def test_us_ai_signal_uses_compact_community_market_toggle_contract():
    client = TestClient(app, base_url="https://secretnote.cloud")
    shell = client.get("/us?view=ai-signals")
    dashboard_js = client.get("/dashboard-app-v170.js").text
    staging_js = client.get("/assets/staging/toss-ia.js").text
    staging_css = client.get("/assets/staging/toss-fidelity.css").text

    assert shell.status_code == 200
    assert 'src="/dashboard-app-v170.js?v=20260910v512"' in shell.text
    assert 'src="/assets/staging/toss-ia.js?v=20260909-unified-market-v108"' in shell.text

    intro_contract = staging_js.split(
        'intro.className = "staging-ai-signals-intro";',
        1,
    )[1].split('modeTabs.insertAdjacentElement("beforebegin", intro)', 1)[0]
    for contract in (
        'intro.classList.add("has-market-toggle")',
        'data-ai-signal-market-toggle role="group" aria-label="AI 시그널 시장 선택"',
        'aria-label="미국 시그널 보기" aria-pressed="false" data-unified-market-scope="us"',
        '<span aria-hidden="true">🇺🇸</span>',
        'aria-label="한국 시그널 보기" aria-pressed="false" data-unified-market-scope="kr"',
        '<span aria-hidden="true">🇰🇷</span>',
    ):
        assert contract in intro_contract
    assert 'data-unified-market-scope="all"' not in intro_contract

    for contract in (
        'BINARY_MARKET_SCOPE_ROUTES.has(requestedView)',
        'requestedMarketScopeValue === "all"',
        'const compactSignalToggle = Boolean(button.closest("[data-ai-signal-market-toggle]"));',
        'button.setAttribute("aria-pressed", String(active));',
        '["news", "search", "portfolio", "chart"].includes(state.view)',
        'state.marketScope = BINARY_MARKET_SCOPE_ROUTES.has(routeView) && routeMarketScope === "all"',
        'if (isUsHubContext && state.marketScope === "all")',
        'state.marketScope = "kr";',
    ):
        assert contract in dashboard_js

    signal_rules = staging_css.split(
        "/* v158 — match the /us AI signal market switch to the compact community toggle. */",
        1,
    )[1]
    for contract in (
        ".staging-ai-signals-intro.has-market-toggle",
        "grid-template-columns: minmax(0, 1fr) auto !important",
        ".staging-ai-signal-market-toggle",
        "grid-row: 1 / span 2 !important",
    ):
        assert contract in signal_rules

    shared_toggle_rules = staging_css.split(
        "/* v157 — country-flag market switch for the home community feed. */",
        1,
    )[1]
    for contract in (
        ".staging-hot-community-market-toggle",
        "grid-template-columns: repeat(2, minmax(0, 1fr)) !important",
        "min-height: 44px !important",
        '[aria-pressed="true"]',
        "> button:focus-visible",
    ):
        assert contract in shared_toggle_rules


def test_us_shared_country_selector_is_a_binary_toggle_on_every_scoped_page():
    client = TestClient(app, base_url="https://secretnote.cloud")
    shell = client.get("/us?view=news")
    dashboard_js = client.get("/dashboard-app-v170.js").text
    dashboard_css = client.get("/assets/dashboard/styles.css").text

    assert shell.status_code == 200
    scope_markup = shell.text.split('id="unified-market-scope"', 1)[1].split("</nav>", 1)[0]
    for contract in (
        'class="unified-market-scope-toggle" role="group"',
        'data-market-toggle-style="compact"',
        'aria-label="미국 종목 보기" aria-pressed="false" data-unified-market-scope="us"',
        'aria-label="한국 종목 보기" aria-pressed="true" data-unified-market-scope="kr"',
    ):
        assert contract in scope_markup
    assert 'data-unified-market-scope="all"' not in scope_markup
    assert 'role="tablist"' not in scope_markup
    assert scope_markup.index('data-unified-market-scope="us"') < scope_markup.index('data-unified-market-scope="kr"')

    for contract in (
        'const BINARY_MARKET_SCOPE_ROUTES = new Set([',
        'elements.unifiedMarketScope.hidden = !["news", "search", "portfolio", "chart"].includes(state.view);',
        'elements.unifiedMarketScope.hidden = !isUsHubContext || !["news", "search", "portfolio", "chart"].includes(view);',
        'news: { heading: "오늘의 피드", item: "피드" }',
        'search: { heading: "종목 찾기", item: "종목" }',
        'portfolio: { heading: "관심 종목", item: "관심 종목" }',
        'chart: { heading: "차트 분석", item: "차트 분석" }',
        'const selectedMarketLabel = state.marketScope === "us"',
        'setCopy("recommend-stage-title", `${selectedMarketLabel} 추천 종목`);',
        'elements.discoverySearchInput.setAttribute("aria-label", `${selectedMarketLabel} 종목 검색`);',
        'elements.unifiedMarketScope.dataset.presentation = "country-toggle";',
        'toggle.setAttribute("role", "group");',
        'const orderedScopes = ["us", "kr"];',
        'button.hidden = scope === "all";',
        'button.setAttribute("aria-pressed", String(active));',
        'if (!isUsHubContext || !["kr", "us"].includes(marketScope)) return;',
        'BINARY_MARKET_SCOPE_ROUTES.has(routeView) && routeMarketScope === "all"',
        'canonicalUrl.searchParams.set("market_scope", state.marketScope);',
        'if (normalizedBinaryMarketScope) {',
        'applyUsMarketSurface();',
    ):
        assert contract in dashboard_js

    shared_toggle_rules = dashboard_css.split(
        "/* /us country scope: the same compact US/KR toggle on every scoped page. */",
        1,
    )[1]
    for contract in (
        '.unified-market-scope[data-presentation="country-toggle"]',
        ".unified-market-scope-toggle",
        "grid-template-columns: repeat(2, minmax(0, 1fr));",
        "flex: 0 0 100px;",
        "min-height: 44px;",
        'button[data-unified-market-scope="us"]',
        '[aria-pressed="true"]',
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert contract in shared_toggle_rules


def test_us_top50_uses_title_flag_toggle_and_country_scoped_rankings():
    client = TestClient(app, base_url="https://secretnote.cloud")
    shell = client.get("/us?view=movers&category=surge&mode=daily")
    dashboard_js = client.get("/dashboard-app-v170.js").text
    dashboard_css = client.get("/assets/dashboard/styles.css").text

    assert shell.status_code == 200
    hero = shell.text.split('<header class="market-ranking-hero">', 1)[1].split("</header>", 1)[0]
    toggle = hero.split('id="market-ranking-country-toggle"', 1)[1].split("</div>", 1)[0]
    assert hero.index('id="market-ranking-title"') < hero.index('id="market-ranking-country-toggle"')
    assert hero.index('id="market-ranking-country-toggle"') < hero.index('id="market-ranking-description"')
    for contract in (
        'role="group" aria-label="TOP 50 국가 선택" hidden',
        'aria-label="미국 TOP 50 보기" aria-pressed="false" data-top50-market-scope="us"',
        '<span aria-hidden="true">🇺🇸</span>',
        'aria-label="한국 TOP 50 보기" aria-pressed="false" data-top50-market-scope="kr"',
        '<span aria-hidden="true">🇰🇷</span>',
    ):
        assert contract in toggle

    for contract in (
        'BINARY_MARKET_SCOPE_ROUTES.has(requestedView)',
        'BINARY_MARKET_SCOPE_ROUTES.has(routeView)',
        '["news", "search", "portfolio", "chart"].includes(state.view)',
        'const visible = isUsRootPath && view === "movers";',
        'button.setAttribute("aria-pressed", String(active));',
        'button.hidden = state.marketScope === "us"',
        '? ["MIXED", "ALL", "KOSPI", "KOSDAQ"].includes(market)',
        ': ["MIXED", "NASDAQ", "SP500"].includes(market);',
        'function marketRankingMarketForScope(market, marketScope = state.marketScope)',
        'return US_MARKET_RANKING_MARKETS.has(normalized) ? normalized : "NASDAQ";',
        'return ["ALL", "KOSPI", "KOSDAQ"].includes(normalized) ? normalized : "ALL";',
        'button.addEventListener("click", () => setUnifiedMarketScope(button.dataset.top50MarketScope || "kr"));',
        'const url = `${usMarket ? "/us/market/rankings" : "/market/rankings"}?${params.toString()}`;',
    ):
        assert contract in dashboard_js

    domestic_more = dashboard_js.split('elements.homeSurgeMore?.addEventListener("click", () => {', 1)[1]
    domestic_more = domestic_more.split('elements.homeRankingMarketTrigger?.addEventListener', 1)[0]
    assert 'state.marketScope = "kr";' in domestic_more
    us_more = dashboard_js.split('usSection.querySelector("#home-surge-more-us")?.addEventListener("click", () => {', 1)[1]
    us_more = us_more.split('domestic.insertAdjacentElement', 1)[0]
    assert 'state.marketScope = "us";' in us_more
    assert 'setMarketFilter("NASDAQ");' in us_more

    toggle_rules = dashboard_css.split(
        "/* TOP 50 country scope: compact flag switch beside the ranking title. */",
        1,
    )[1]
    for contract in (
        ".market-ranking-heading-row",
        ".market-ranking-country-toggle[hidden]",
        "grid-template-columns: repeat(2, minmax(0, 1fr));",
        "min-height: 44px;",
        '[aria-pressed="true"]',
        "> button:focus-visible",
        "@media (max-width: 359px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert contract in toggle_rules


def test_us_ai_signal_waits_for_both_markets_then_toggles_cached_snapshot_without_skeleton():
    client = TestClient(app, base_url="https://secretnote.cloud")
    dashboard_js = client.get("/dashboard-app-v170.js").text
    staging_css = client.get("/assets/staging/toss-fidelity.css").text

    snapshot_source = dashboard_js.split(
        "function aiSignalRequiredMarketScopes()",
        1,
    )[1].split("function createMarketBadge", 1)[0]
    for contract in (
        'return isUsHubContext ? ["kr", "us"] : ["kr"];',
        "function aiSignalHasCompleteMarketSnapshot()",
        "state.aiSignalLoadedMarketScopes.has(scope)",
        "market_revision_by_scope",
    ):
        assert contract in snapshot_source

    scope_source = dashboard_js.split(
        "function setUnifiedMarketScope(marketScope)",
        1,
    )[1].split("function syncUnifiedMarketScopeVisibility", 1)[0]
    cached_signal_branch = scope_source.split(
        'if (state.view === "ai-signals" && ["kr", "us"].includes(marketScope))',
        1,
    )[1].split("window.location.assign", 1)[0]
    for contract in (
        "window.history.replaceState",
        "applyUsMarketSurface();",
        "if (aiSignalHasCompleteMarketSnapshot()) renderAiSignalsPage();",
        "return;",
    ):
        assert contract in cached_signal_branch
    assert "renderAiSignalsSkeleton" not in cached_signal_branch
    assert "fetch" not in cached_signal_branch

    load_source = dashboard_js.split(
        "async function loadAiSignalsPage(options = {})",
        1,
    )[1].split("async function fetchMarketAiSignals", 1)[0]
    for contract in (
        "const hadCompleteSnapshot = aiSignalHasCompleteMarketSnapshot();",
        "if (!hadCompleteSnapshot && options.silent !== true)",
        "requireCompleteMarkets: isUsHubContext",
        "const settledScopes = new Set(",
        "aiSignalRequiredMarketScopes()",
        ".every((scope) => settledScopes.has(scope))",
        "if (!scheduleRetry() && !hadCompleteSnapshot) renderAiSignalsSkeleton({ delayed: true });",
        "if (!hadCompleteSnapshot || snapshotChanged)",
        "if (isAiSignalMarketUpdating()) scheduleRetry();",
    ):
        assert contract in load_source

    fetch_source = dashboard_js.split(
        "async function fetchMarketAiSignals(options = {})",
        1,
    )[1].split("async function fetchCombinedAiSignals", 1)[0]
    for contract in (
        '["home", "ai-signals"].includes(state.view)',
        'const requestedScopes = ["kr", "us"];',
        'const retryDelays = options.requireCompleteMarkets === true ? [0] : [0, 1200, 2500];',
        "payloads = await Promise.all(requestedScopes.map((scope) => fetchScope(scope)));",
        'status: complete ? "ready" : "refreshing"',
        "market_scopes_ready: readyScopes",
        "market_revision_by_scope: Object.fromEntries",
    ):
        assert contract in fetch_source

    render_source = dashboard_js.split(
        "function renderAiSignalsPage()",
        1,
    )[1].split("async function loadAiSignalsPage", 1)[0]
    assert ".filter((item) => !isUsHubContext || itemMatchesMarketScope(item, state.marketScope))" in render_source
    assert "elements.aiSignalsPageList.replaceChildren(...nextRows);" in render_source
    assert 'elements.aiSignalsPageList.innerHTML = ""' not in render_source

    set_view_source = dashboard_js.split(
        "function setView(requestedViewName, options = {})",
        1,
    )[1].split("function renderEvents", 1)[0]
    signal_entry_source = set_view_source.split(
        '} else if (view === "ai-signals") {',
        1,
    )[1].split("} else if", 1)[0]
    assert "void loadAiSignalsPage" in signal_entry_source
    assert "launchBriefPageLoading" not in signal_entry_source

    skeleton_rules = staging_css.split(
        "/* v161 — keep AI signal loading stable while both markets prepare off-screen. */",
        1,
    )[1]
    for contract in (
        ".ai-signals-page-list[data-loading]",
        "min-height: 528px !important",
        ".ai-signal-skeleton-row",
        "min-height: 88px !important",
        "@keyframes ai-signal-skeleton-shift",
        "@media (prefers-reduced-motion: reduce)",
        "animation: none !important",
    ):
        assert contract in skeleton_rules
