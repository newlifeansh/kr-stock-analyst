from fastapi.testclient import TestClient

from app.main import app


def test_watchlist_v15_shell_and_asset_version():
    client = TestClient(app)
    shell = client.get("/dashboard?view=watchlist")

    assert shell.status_code == 200
    assert 'id="watchlist-view" class="watchlist-v15 watchlist-v2 watchlist-v3" data-ui-version="3.0"' in shell.text
    assert 'name="application-version" content="5.1"' in shell.text
    assert "20260726v77" in shell.text
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
        'el("button", "recommend-ai-button", "AI 상세 보기")',
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


def test_recommendation_score_explains_scale_and_interpretation():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'el("span", "", "/ 100")',
        'help.setAttribute("aria-label", "추천 점수 설명")',
        '"기준은 70점 이상 우수, 55~69점 관찰, 55점 미만 신중입니다."',
        '"수익률 확률이나 매수 확정 신호는 아닙니다."',
        'return { label: "우수", guide: "70점 이상", className: "high" };',
        'return { label: "관찰", guide: "55~69점", className: "watch" };',
        'return { label: "신중", guide: "55점 미만", className: "cautious" };',
    ):
        assert expected in source

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


def test_event_calendar_uses_compact_stock_detail_hierarchy():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'schedule.append(el("span", "event-stage", "발표 예정"), date)',
        'el("h3", "", item.title)',
        'el("dl", "event-facts")',
        'el("dt", "", "영향 분야")',
        'el("dt", "", "예상 영향")',
        'el("button", "flow-button", "영향 흐름")',
        'detailsSummary.textContent = "근거와 출처"',
        'button.textContent = "영향 흐름"',
    ):
        assert expected in source

    for expected in (
        "/* Event calendar 6.0: compact stock-detail table hierarchy. */",
        "#trend-events-panel .event-facts",
        "#trend-events-panel .event-schedule time",
        "#trend-events-panel .event-importance-critical",
        "#trend-events-panel .event-axis-badges",
        "#trend-events-panel .flow-button",
    ):
        assert expected in styles

    assert 'schedule.append(el("span", "", "발표")' not in source


def test_market_impact_uses_five_element_relationship_and_sector_correlations():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "const MARKET_FIVE_ELEMENTS",
        "const MARKET_FIVE_RELATIONS",
        "function createMarketFiveRelationSvg",
        "function buildMarketSectorCorrelations",
        'el("section", "market-five-map-section")',
        'el("section", "market-sector-section")',
        'el("h2", "", "시장 오행 관계도")',
        'el("h2", "", "섹터 상관 영향도")',
        'detailsSummary.textContent = "공식 지표와 종목 근거 보기"',
        'el("div", "market-impact-source-list")',
        'el("div", "market-impact-keyword-rail")',
    ):
        assert expected in source

    for expected in (
        "/* Market impact 5.0: five-element relationship and sector correlation map. */",
        "#trend-impact-content .market-five-canvas",
        ".market-five-generate-line",
        ".market-five-control-line",
        ".market-five-node.wood",
        ".market-five-node.fire",
        ".market-five-node.earth",
        ".market-five-node.metal",
        ".market-five-node.water",
        ".market-sector-matrix",
        "/* Market impact evidence 5.4: compact analyst notes and keyword rails. */",
        ".market-impact-source-list",
        ".market-impact-keyword-groups",
        ".market-impact-keyword-rail",
    ):
        assert expected in styles

    assert 'label: "금리", percent:' not in source
    assert "외부 변수 → 국내증시 → 영향 종목" not in source
    assert 'el("span", `market-impact-icon ${factor.key || factor.className || ""}`, factor.label)' not in source
    assert source.count("appendMarketImpactDetail(detailGrid, factor)") == 1

    for expected in (
        "/* Market impact flow 5.3: restrained research-table treatment for legacy views. */",
        "#trend-impact-content .market-impact-flow-title span",
        "display: none !important;",
        "grid-template-columns: minmax(112px, 0.32fr) minmax(0, 1.4fr) minmax(180px, 0.7fr);",
    ):
        assert expected in styles


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
