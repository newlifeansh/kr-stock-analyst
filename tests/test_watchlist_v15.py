from fastapi.testclient import TestClient

from app.main import app


def test_watchlist_v15_shell_and_asset_version():
    client = TestClient(app)
    shell = client.get("/dashboard?view=watchlist")

    assert shell.status_code == 200
    assert 'id="watchlist-view" class="watchlist-v15 watchlist-v2 watchlist-v3" data-ui-version="3.0"' in shell.text
    assert 'name="application-version" content="5.6"' in shell.text
    assert 'src="/dashboard-app-v170.js?v=20260831v453"' in shell.text
    assert 'id="push-notification-disable-button"' not in shell.text
    assert 'class="watch-v2-filter watch-v3-tabs"' in shell.text
    assert 'class="watch-v3-stock-section"' in shell.text
    assert 'id="watchlist-content-tabs"' in shell.text
    assert 'data-watch-content-tab="strategy">AI 전략</button>' in shell.text
    assert 'data-watch-content-tab="news">종목 뉴스</button>' in shell.text
    assert 'id="watchlist-strategy-panel"' in shell.text
    assert 'id="watchlist-news-panel"' in shell.text
    assert shell.text.index('data-watch-content-tab="strategy"') < shell.text.index('data-watch-content-tab="news"')
    assert shell.text.index('id="watchlist-strategy-panel"') < shell.text.index('id="watchlist-news-panel"')

    styles = client.get("/assets/dashboard/styles.css").text
    assert "Recommendation metrics use the same continuous table language as stock detail" in styles
    assert "#recommend-view .recommend-metrics > div:last-child" in styles
    assert 'class="watch-v2-list-head"' not in shell.text
    assert 'id="watchlist-filter-summary"' not in shell.text
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
        "function setWatchlistContentTab",
        'const active = tabName === "news" ? "news" : "strategy";',
        'tab.addEventListener("click", () => setWatchlistContentTab(tab.dataset.watchContentTab, { load: true }));',
    ):
        assert expected in source

    assert "watchDetailsExpanded" not in source
    assert 'className = "watch-stock-details"' not in source

    styles = client.get("/assets/dashboard/styles.css").text
    for expected in (
        "/* Portfolio 4.9: separate AI strategy from stock news without stacking both feeds. */",
        "grid-template-columns: repeat(2, minmax(0, 1fr));",
        ".watchlist-content-tabs button.active",
        ".watchlist-content-panel[hidden]",
    ):
        assert expected in styles


def test_recommendation_cards_use_one_compact_action_row():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'actions.append(watchButton, trackButton, explainButton);',
        'isWatched(item.code) ? "관심 해제" : "관심 추가"',
        'isTrackedRecommendation(item.code) ? "핀 종목 보기" : "핀 설정하기"',
        'el("button", "recommend-ai-button", "AI 시그널 보기")',
        "grid-template-columns: repeat(3, minmax(0, 1fr));",
    ):
        assert expected in source or expected in styles

    assert 'el("button", "recommend-refresh", "새로고침")' not in source


def test_recommendation_ai_explanation_opens_on_a_dedicated_page():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'id="recommend-detail-page"',
        'function openRecommendationDetail(item)',
        'setView("recommend-detail");',
        'openRecommendationDetail(card.recommendationItem);',
        'Ollama AI 분석 완료',
    ):
        assert expected in source or expected in client.get("/dashboard?view=recommend-detail").text

    assert 'renderRecommendationAIExplanation(card)' not in source
    assert 'detailsSummary.textContent = "세부 점수와 근거 보기"' not in source
    assert ".recommend-detail-page" in styles


def test_recommendation_detail_is_single_column_and_action_first_on_mobile():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    detail_render = source.split("function renderRecommendationDetail", 1)[1].split("async function loadRecommendationDetail", 1)[0]
    signal_flow = detail_render.index("createRecommendationDecisionFlow(item, {")
    assert detail_render.index("hero,") < signal_flow
    assert signal_flow < detail_render.index("action,")
    assert 'options.detail ? "AI 시그널 여정" : "현재 단계"' in source
    assert '"AI 대응 · 지금 할 일"' in source

    assert ".recommend-detail-content {\n  display: grid;\n  grid-template-columns: minmax(0, 1fr);" in styles
    assert ".recommend-detail-content > .recommend-decision-flow.is-detail {\n  grid-area: auto;" in styles
    assert "overflow-wrap: break-word;\n  word-break: keep-all;" in styles


def test_recommendation_cards_show_linked_signal_status_and_load_full_history_on_demand():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "function recommendationSignalStageView",
        "function recommendationShouldCollectSignal",
        'headline: "시그널 수집 중"',
        'if (action === "entry_watch")',
        'headline: "예비 포착"',
        '`${profitStage || 1}차 수익확정 후 보유`',
        'headline: "전량 매도"',
        'headline: "조건 해제"',
        'stage.changedLabel || "마지막 변경"',
        'el("dt", "", "다음 조건")',
        'function recommendationSignalTimelineItems',
        '"추천 전 이력"',
        'const [aiResult, signalResult] = await Promise.all([',
        'liveUrl(`/stocks/${encodeURIComponent(item.code)}/quant-signals`)',
        '"시그널 다시 불러오기"',
    ):
        assert expected in source

    card_render = source.split("function createRecommendationCard", 1)[1].split("function appendRecommendationCard", 1)[0]
    assert "createRecommendationDecisionFlow(item)" in card_render
    assert 'el("section", "recommend-card-reason")' in card_render
    assert 'recommendationReasonSummary(item)' in card_render
    assert card_render.index('const reason = el("section", "recommend-card-reason")') < card_render.index("createRecommendationDecisionFlow(item)")
    assert "createRecommendationUsSectorSummary(item)" not in card_render
    assert 'const metrics = el("div", "recommend-metrics")' not in card_render

    for expected in (
        "/* Recommendation lifecycle 5.4",
        ".recommend-signal-stage",
        ".recommend-signal-facts",
        ".recommend-signal-timeline",
        ".recommend-signal-retry:focus-visible",
        "/* Recommendation context 5.5",
        ".recommend-card-reason",
        ".recommend-signal-stage.is-collecting",
        "font-size: var(--app-type-button) !important;",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert expected in styles

    detail_render = source.split("function renderRecommendationDetail", 1)[1].split("async function loadRecommendationDetail", 1)[0]
    assert 'el("h1", "", "추천한 핵심 이유")' in detail_render
    assert 'recommendationReasonSummary(item)' in detail_render
    assert '"추천 이후 신규 매수 시그널을 수집하고 있습니다."' in detail_render


def test_recommendation_score_explains_scale_and_interpretation():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'el("span", "", "/ 100")',
        'help.setAttribute("aria-label", "추천 점수 설명")',
        '"70점 이상은 우수, 55~69점은 관찰, 55점 미만은 신중 구간입니다."',
        '"매수 확정이나 수익률 보장을 뜻하지 않습니다."',
        'return { label: "우수", guide: "70점 이상", className: "high" };',
        'return { label: "관찰", guide: "55~69점", className: "watch" };',
        'return { label: "신중", guide: "55점 미만", className: "cautious" };',
    ):
        assert expected in source

    assert '"recommend-as-of"' not in source
    assert '`추천 기준 ${recommendationMoment(recommendedAt)}`' not in source

    for expected in (
        "#recommend-view .recommend-score-value",
        "#recommend-view .recommend-score-help::after",
        "#recommend-view .recommend-score-level.high",
    ):
        assert expected in styles


def test_tracked_recommendation_uses_readable_values_and_stock_detail_table():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "function sanitizeRecommendationTrackPoint",
        "function recommendationPinSummary",
        "function recommendationPinHighlights",
        'return "1개월·3개월 수익률 데이터가 부족해 최근 가격과 거래대금을 우선 확인합니다.";',
        'return "판단 정보 없음";',
        'return `${formatNumber(score)}점 / 100점`;',
        '["핀 시작일", track.tracked_at ? formatDateLabel',
        '["핀 시작가", trackedPrice !== null',
        '["현재가", currentPrice !== null',
        '["수익률", profit.rate !== null',
        '["시작 판단", recommendationTrackDecisionLabel',
        'el("h3", "", "핀 시작 정보")',
        'el("h3", "", "핵심 요약")',
        'el("h3", "", "확인할 것")',
        "setRecommendationTrackExpanded(nextCard, keepExpanded);",
        'open.className = "recommend-track-stock-link";',
        'el("button", "recommend-track-remove track-delete", "핀 해제하기")',
        'stockDetail.textContent = "종목 상세";',
        'metrics.className = "recommend-track-metrics";',
        'el("span", "recommend-track-detail-toggle-label", "핵심 정보 보기")',
        'el("span", "recommend-track-detail-toggle-icon", "+")',
    ):
        assert expected in source

    assert 'open.className = "snapshot-button";' not in source
    assert 'el("button", "snapshot-delete track-delete", "추적 해제")' not in source
    assert '["주당 손익"' not in source
    for old_label in ('"추적 보기"', '"추적 종목"', '"추적 해제"', '["추적가"'):
        assert old_label not in source

    for expected in (
        "/* Tracked recommendation tables match the continuous stock-detail table. */",
        "/* Tracked recommendations use the same flat section language as stock detail. */",
        "/* Final tracking layout overrides legacy dashboard card rules. */",
        "/* Pin portfolio 5.0 final precedence: mirror the stock-detail visual system. */",
        "#recommend-history-view :is(",
        ".recommend-track-signals > div:last-child",
        ".recommend-track-saved-info",
        ".recommend-track-stock-link",
        ".recommend-track-remove",
        ".recommend-track-detail-toggle-icon",
        "grid-template-columns: repeat(2, minmax(0, 1fr));",
    ):
        assert expected in styles

    shell = client.get("/dashboard?view=recommend-history").text
    assert '>핀 종목</button>' in shell
    assert "핀 종목 없음" in shell
    assert "추적종목" not in shell


def test_watchlist_v15_is_responsive_and_matches_stock_detail_tokens():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "/* Dashboard stock-detail fidelity 3.3 */",
        "#recommend-history-view .recommend-history.archive-page",
        "#recommend-history-view > .app-section-heading",
        "padding: 16px 20px 14px;",
        "#portfolio-tracking-panel",
        "#trend-view .trend-tabs",
        "width: calc(100% + 40px) !important;",
        ".market-impact-hero",
        ".market-impact-factor-row",
        ".market-impact-factor-track",
        ".market-impact-balance-track",
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


def test_event_calendar_uses_week_strip_and_dedicated_impact_detail():
    client = TestClient(app)
    shell = client.get("/dashboard?view=trend").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "function renderTrendCalendar(payload = state.homeTrendContext || {})",
        "function appendTrendEvent(item, parent = elements.trendEvents)",
        'button.dataset.trendEventOpen = item.id || "";',
        "function renderTrendEventDetail(item)",
        'el("span", "event-detail-eyebrow", "한눈에 보기")',
        'el("h3", "", "이번 발표에서 볼 것")',
        'el("h3", "", "3단계로 확인하세요")',
        "function appendTrendScenario(parent, label, stocks = [], tone = \"neutral\")",
        'el("summary", "", "영향 경로 자세히 보기")',
        "function renderTrendGraph(card, graph)",
        'el("h3", "", "시장은 이렇게 반응할 수 있어요")',
        'setView("event-detail");',
        'elements.homePastToggleLabel.textContent = pastEventsExpanded ? "지난 이벤트 접기" : "지난 이벤트 펼치기"',
    ):
        assert expected in source

    for expected in (
        "/* News preview, trading calendar, and event analysis 7.0. */",
        ".trend-calendar-days",
        ".trend-calendar-day.active",
        ".trend-calendar-event",
        ".event-detail-hero",
        ".event-detail-watch-list",
        ".event-detail-graph > .event-flow",
        ".event-detail-graph .impact-columns",
        "#trend-events-panel .trend-past-toggle",
    ):
        assert expected in styles

    assert 'id="trend-calendar-days" role="tablist"' in shell
    assert 'id="trend-calendar-selected-date"' not in shell
    assert 'id="trend-calendar-event-count" aria-live="polite">0개 일정</span>' in shell
    assert "trendCalendarSelectedDate" not in source
    assert 'id="event-detail-view" class="app-page event-detail-page"' in shell
    assert 'id="event-detail-back"' in shell
    assert 'id="home-past-toggle"' in shell
    assert 'aria-controls="trend-past-panel"' in shell
    assert 'id="home-past-toggle-label">지난 이벤트 펼치기</strong>' in shell
    assert '<small>최근 2주</small>' in shell
    assert 'aria-label="최근 2주 지난 이벤트"' in shell
    assert 'data-trend-tab="impact" data-archived="true"' in shell
    assert '#trend-view [data-archived="true"]' in styles
    assert 'class="trend-panel home-market-card home-news-card"' in shell
    assert 'class="trend-panel home-market-card home-events-card"' in shell
    assert '#trend-view.home-market-sections' in styles
    assert '#trend-view .home-market-card' in styles


def test_market_impact_uses_beginner_signal_summary_without_five_element_metaphor():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "const MARKET_BEGINNER_FACTOR_ORDER",
        "const MARKET_BEGINNER_COPY",
        "function marketImpactBeginnerStatus",
        "function marketImpactBeginnerShortStatus",
        "function marketImpactBeginnerSummary",
        "function marketImpactEvidenceItems",
        "function appendMarketBeginnerThreadItem",
        "function createMarketBeginnerImpactChart",
        'el("section", "market-beginner-signals")',
        'el("h2", "", "5개 변수를 한 줄씩 읽어보세요")',
        'detailsSummary.textContent = "숫자와 공식 출처 확인"',
        'el("div", "market-impact-source-list")',
        'el("div", "market-thread-list")',
        'el("article", `market-thread-item',
        'el("div", "market-beginner-impact-chart")',
        'period: "5일", value: item.change_5d_text',
        'period: "현재", value: item.value_text || "자료 없음"',
    ):
        assert expected in source

    for expected in (
        "/* Market impact beginner mode: answer",
        ".market-beginner-dashboard",
        ".market-beginner-summary",
        ".market-beginner-signal-row",
        ".market-beginner-status",
        ".market-beginner-impact-chart",
        ".market-beginner-impact-bar-fill",
        ".market-beginner-signal-evidence",
        ".market-beginner-disclosure",
        "/* Market impact thread 3.0:",
        ".market-thread-list",
        ".market-thread-item",
        ".market-thread-avatar",
        ".market-thread-metric",
        ".market-thread-sector",
    ):
        assert expected in styles

    assert 'label: "금리", percent:' not in source
    assert "외부 변수 → 국내증시 → 영향 종목" not in source
    assert "채권 가격이 오르면 채권금리는 내려갑니다." in source
    assert "나스닥은 오르고 비트코인은 내리는 엇갈린 신호" in source
    assert "좋은 신호" in source
    assert "주의 신호" in source
    assert "function appendMarketBeginnerSignalRow" not in source
    assert "시장 변수 연결도" not in source
    assert "오행별" not in source
    assert 'el("span", `market-impact-icon ${factor.key || factor.className || ""}`, factor.label)' not in source
    assert source.count("appendMarketImpactDetail(detailGrid, factor)") == 1


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


def test_market_lists_share_stock_logo_identity():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "function createStockListLogo(code)",
        "`/stock-logos/${encodeURIComponent(normalizedCode)}.png?v=${encodeURIComponent(DASHBOARD_CLIENT_VERSION)}`",
        "fallbackIcon.src = STOCK_LOGO_FALLBACK_DATA_URL;",
        'image.loading = "eager";',
        'image.addEventListener("error", () => {',
        "identity.append(\n    createStockListLogo(item.code),\n    createStockListCopy(item.name, item.code)",
        "createStockListCopy(item.name, item.code)",
    ):
        assert expected in source

    for expected in (
        ".stock-list-logo {",
        ".stock-list-logo-image {",
        "object-fit: contain;",
        ".home-surge-identity {",
        ".recommend-name .stock-list-copy",
    ):
        assert expected in styles


def test_market_ranking_tabs_reserve_their_full_mobile_grid_row():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    assert "/* Market movers 5.1: reserve the tabs' full mobile height before the stock list. */" in styles
    assert "grid-template-rows: auto auto minmax(0, 1fr);" in styles
    assert "#market-view.app-market-rankings .market-ranking-commandbar,\n#market-view.app-market-rankings .market-ranking-tabs {\n  box-sizing: border-box;" in styles
    assert "#market-view.app-market-rankings .market-ranking-tabs {\n  align-self: start;" in styles
