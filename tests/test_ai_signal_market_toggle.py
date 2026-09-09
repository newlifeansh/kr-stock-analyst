from fastapi.testclient import TestClient

from app.main import app


def test_us_ai_signal_uses_compact_community_market_toggle_contract():
    client = TestClient(app, base_url="https://secretnote.cloud")
    shell = client.get("/us?view=ai-signals")
    dashboard_js = client.get("/dashboard-app-v170.js").text
    staging_js = client.get("/assets/staging/toss-ia.js").text
    staging_css = client.get("/assets/staging/toss-fidelity.css").text

    assert shell.status_code == 200
    assert 'src="/dashboard-app-v170.js?v=20260910v505"' in shell.text
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
        '["ai-signals", "news"].includes(requestedView)',
        'requestedMarketScopeValue === "all"',
        'const compactSignalToggle = Boolean(button.closest("[data-ai-signal-market-toggle]"));',
        'button.setAttribute("aria-pressed", String(active));',
        '["home", "ai-signals", "stock", "portfolio"',
        'state.marketScope = ["ai-signals", "news"].includes(routeView) && routeMarketScope === "all"',
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


def test_us_feed_replaces_the_wide_country_tabs_with_a_compact_flag_toggle():
    client = TestClient(app, base_url="https://secretnote.cloud")
    shell = client.get("/us?view=news")
    dashboard_js = client.get("/dashboard-app-v170.js").text
    dashboard_css = client.get("/assets/dashboard/styles.css").text

    assert shell.status_code == 200
    scope_markup = shell.text.split('id="unified-market-scope"', 1)[1].split("</nav>", 1)[0]
    for contract in (
        'data-unified-market-scope="all"',
        'data-unified-market-scope="us"><span aria-hidden="true">🇺🇸</span>',
        'data-unified-market-scope="kr"><span aria-hidden="true">🇰🇷</span>',
        'class="unified-market-scope-button-label"',
    ):
        assert contract in scope_markup

    for contract in (
        '["ai-signals", "news"].includes(requestedView)',
        'const compactFeedToggle = isUsHubContext && view === "news";',
        'compactFeedToggle ? "오늘의 피드" : "시장"',
        'tabs.setAttribute("role", compactFeedToggle ? "group" : "tablist");',
        'tabs.toggleAttribute("data-market-toggle-style", compactFeedToggle);',
        'const orderedScopes = compactFeedToggle ? ["us", "kr"] : ["all", "kr", "us"];',
        'button.hidden = compactFeedToggle && scope === "all";',
        'scope === "us" ? "미국 피드 보기" : "한국 피드 보기"',
        '["ai-signals", "news"].includes(routeView) && routeMarketScope === "all"',
    ):
        assert contract in dashboard_js

    feed_toggle_rules = dashboard_css.split(
        "/* Feed market scope: compact country switch aligned with the feed heading. */",
        1,
    )[1]
    for contract in (
        '.unified-market-scope[data-presentation="feed-toggle"]',
        "top: var(--tc-header-height, 78px);",
        "grid-template-columns: repeat(2, minmax(0, 1fr));",
        "flex: 0 0 100px;",
        "min-height: 44px;",
        'button[data-unified-market-scope="us"]',
        '[aria-pressed="true"]',
        ".unified-market-scope-button-label",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert contract in feed_toggle_rules


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
