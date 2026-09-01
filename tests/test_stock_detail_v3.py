import json
import subprocess
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.services.company_profiles import _short_company_summary
from app.services import stock_dashboard


def test_chart_daily_series_appends_a_newer_live_quote():
    source = TestClient(app).get("/assets/dashboard/app.js").text
    start = source.index("function stockPriceRowsWithLiveQuote(")
    end = source.index("function formatChartAxisPrice(", start)
    function_source = source[start:end]
    script = f"""
function toNumber(value) {{
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}}
{function_source}
const rows = stockPriceRowsWithLiveQuote(
  [
    {{ trade_date: "2026-08-21", close: 36000, high: 36500, low: 35500, volume: 100 }},
    {{ trade_date: "2026-08-20", close: 37000, high: 37500, low: 36500, volume: 90 }},
  ],
  {{ trade_date: "2026-08-25", price: 35800, volume: 120 }},
);
console.log(JSON.stringify(rows));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = json.loads(completed.stdout)

    assert [row["date"] for row in rows] == ["2026-08-20", "2026-08-21", "2026-08-25"]
    assert rows[-1] == {
        "date": "2026-08-25",
        "open": None,
        "high": 35800,
        "low": 35800,
        "close": 35800,
        "volume": 120,
        "is_live_quote": True,
    }


def test_chart_pattern_age_moves_with_the_latest_daily_point():
    source = TestClient(app).get("/assets/dashboard/app.js").text
    start = source.index("function chartPatternAgeDays(")
    end = source.index("function recentChartPatterns(", start)
    function_source = source[start:end]
    script = f"""
function toNumber(value) {{
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}}
{function_source}
const analysis = {{
  prices: ["18", "19", "20", "21", "25"].map((day) => ({{ date: `2026-08-${{day}}` }})),
}};
console.log(chartPatternAgeDays({{ signal_date: "2026-08-18", age_days: 3 }}, analysis));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "4"


def test_chart_analysis_uses_the_same_one_month_daily_window_as_the_home_chart():
    source = TestClient(app).get("/assets/dashboard/app.js").text
    assert 'const STOCK_PRICE_PERIOD_COUNTS = { "1M": 22' in source
    assert 'const CHART_FORECAST_VISIBLE_DAYS = STOCK_PRICE_PERIOD_COUNTS["1M"];' in source

    start = source.index("function createChartForecastSvg(")
    end = source.index("function renderChartPatternAnalysis(", start)
    function_source = source[start:end]
    script = """
const CHART_FORECAST_VISIBLE_DAYS = 22;
const CHART_FORECAST_TREND_DAYS = 20;
function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function formatChartAxisPrice(value) { return String(Math.round(value)); }
function chartForecastResultTone() { return "neutral"; }
function chartPatternTone() { return "neutral"; }
function chartPatternRecencyLabel() { return "최신 거래일"; }
function escapeChartSvgText(value) { return String(value ?? ""); }
function chartPatternHasBoundaries() { return false; }
function chartPatternBoundaryMarkup() { return ""; }
""" + function_source + """
const prices = Array.from({ length: 45 }, (_, index) => ({
  date: `2026-07-${String(index + 1).padStart(2, "0")}`,
  close: 100 + index,
  volume: 1000 + index,
}));
const forecast = {
  available: true,
  days: 5,
  primaryPattern: null,
  points: Array.from({ length: 5 }, (_, index) => ({
    day: index + 1,
    lower: 140 - index,
    center: 145 + index,
    upper: 150 + index,
  })),
};
const svg = createChartForecastSvg({ prices }, forecast);
const actualPath = svg.match(/class="chart-forecast-actual" d="([^"]+)"/)[1];
console.log(JSON.stringify({
  actualPointCount: (actualPath.match(/[ML]/g) || []).length,
  hasOneMonthLabel: svg.includes("1개월 일봉 · 22거래일"),
}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result == {"actualPointCount": 22, "hasOneMonthLabel": True}


def test_stock_detail_pending_buy_omits_previous_trade_metrics():
    source = TestClient(app).get("/assets/dashboard/app.js").text
    sanitizer_start = source.index("function sanitizePendingEntryAiSignal(")
    sanitizer_end = source.index("function combineAiSignalPayloads(", sanitizer_start)
    status_start = source.index("function quantSignalCurrentState(")
    status_end = source.index("function renderQuantCurrentStatus(", status_start)
    function_source = source[sanitizer_start:sanitizer_end] + source[status_start:status_end]
    script = f"""
function formatNumber(value) {{ return String(Number(value)); }}
function formatPercent(value) {{ return `${{Number(value) >= 0 ? "+" : ""}}${{Number(value).toFixed(2)}}%`; }}
function quantToneClass(value) {{ return Number(value) >= 0 ? "positive" : "negative"; }}
function formatDateLabel(value) {{ return String(value || "-"); }}
{function_source}
const raw = {{
  display_return_rate: 10.21,
  display_return_kind: "closed_trade",
  events: [{{
    side: "sell",
    execution_date: "2026-05-29",
    price: 4990,
    entry_price: 4830,
    target_sell_price: 5593,
    return_rate: 10.21,
  }}],
  trades: [{{ net_return: 10.21 }}],
  current: {{
    action: "entry_pending",
    live_observation: true,
    position_open: false,
    price: 5460,
    score: 84.63,
    model_exposure_percent: 0,
    entry_price: null,
    target_sell_price: 5593,
    target_sell_status: "missed",
    target_sell_delta: -603,
    lifecycle: {{ latest_transition: {{ side: "sell", entry_price: 4830, target_sell_price: 5593 }} }},
  }},
}};
const sanitized = sanitizePendingEntryAiSignal(raw);
const status = quantCurrentStatusView(sanitized);
console.log(JSON.stringify({{
  headline: status.headline,
  tone: status.tone,
  next: status.next,
  rows: status.rows,
  currentTarget: sanitized.current.target_sell_price,
  displayReturn: sanitized.display_return_rate,
  historicalEntry: sanitized.current.lifecycle.latest_transition.entry_price,
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "headline": "매수 대기중",
        "tone": "entry_pending",
        "next": "다음 거래일 시가의 갭을 확인한 뒤 매수 신호로 반영할 예정이에요.",
        "rows": [
            ["현재가", "5460원", "neutral"],
            ["종합 신호", "84.63점", "neutral"],
            ["전략 잔여비중", "0%", "neutral"],
        ],
        "currentTarget": None,
        "displayReturn": None,
        "historicalEntry": 4830,
    }
    render_source = source[source.index("function renderQuantSignals("):source.index("async function loadQuantSignals(")]
    assert "payload = sanitizePendingEntryAiSignal(payload);" in render_source


def test_stock_detail_title_logo_tracks_the_selected_stock_with_a_fallback():
    client = TestClient(app)
    shell = client.get("/dashboard/005930").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text
    staging_source = client.get("/assets/staging/toss-ia.js").text

    assert 'class="stock-v3-name-row"' in shell
    assert 'class="stock-title-logo" id="stock-title-logo" aria-hidden="true" hidden' in shell
    assert '<div class="stock-v3-chart-pane">\n              <div class="stock-mini-chart"' in shell
    assert 'stockTitleLogo: $("stock-title-logo")' in source
    logo_source = source[
        source.index("function createStockListLogo(")
        : source.index("function createStockListCopy(")
    ]
    assert 'function createStockListLogo(code, className = "")' in logo_source
    assert '["stock-list-logo", className].filter(Boolean).join(" ")' in logo_source
    assert 'function renderStockTitleLogo(stock = state.currentStock)' in logo_source
    assert 'elements.stockTitleLogo.dataset.stockCode === code' in logo_source
    assert 'createStockListLogo(code, "stock-title-logo-frame")' in logo_source
    assert 'image.src = `/stock-logos/${encodeURIComponent(normalizedCode)}.png' in logo_source
    assert 'image.addEventListener("error", () => {' in logo_source
    assert "image.remove();" in logo_source
    assert "renderStockTitleLogo(null);" in source
    assert "renderStockTitleLogo(state.currentStock);" in source

    daily_chart_source = source[
        source.index("function renderStockMiniChart(")
        : source.index("function formatIntradayTime(")
    ]
    intraday_chart_source = source[
        source.index("function renderStockIntradayChart(")
        : source.index("function setCompanyProfileRow(")
    ]
    assert "const top = 18;" in daily_chart_source
    assert "const top = 24;" in intraday_chart_source
    assert ".stock-v3-name-row {" in styles
    assert ".stock-title-logo {" in styles
    assert "pointer-events: none;" in styles
    assert ".stock-title-logo[hidden]" in styles
    assert ".stock-title-logo-frame" in styles
    staging_logo_styles = styles[styles.index(
        'body[data-staging-ia="tds-video"] #stock-view '
        ".staging-stock-hero-name-row > .stock-title-logo"
    ) :]
    assert "width: 36px !important;" in staging_logo_styles
    assert 'const stockTitleLogo = document.getElementById("stock-title-logo");' in staging_source
    assert "stockHeroNameRow.prepend(stockTitleLogo)" in staging_source
    staging_chart_source = staging_source[
        staging_source.index("const width = 360;") : staging_source.index(
            "const priceValues = isCandle"
        )
    ]
    assert "const top = 34;" in staging_chart_source


def test_stock_detail_v3_shell_and_controls():
    client = TestClient(app)

    shell = client.get("/dashboard/SK하이닉스")
    assert shell.status_code == 200
    for expected in (
        'class="stock-detail-v3"',
        'id="stock-detail-tabs-sentinel"',
        'id="stock-command-quote"',
        'id="stock-command-price"',
        'id="stock-command-change"',
        ">종목홈</button>",
        ">기업분석</button>",
        ">AI 시그널</button>",
        'id="stock-company-section"',
        'data-stock-panel="company"',
        'id="stock-investment-snapshot"',
        'id="stock-company-metric-groups"',
        'id="stock-revenue-breakdown"',
        'id="stock-revenue-breakdown-lead"',
        'id="stock-revenue-breakdown-summary"',
        'id="stock-sector-margin-comparison"',
        'id="stock-sector-margin-summary"',
        'id="stock-sga-analysis"',
        'id="stock-sga-source"',
        'id="stock-financial-health"',
        'id="stock-financial-health-source"',
        'id="stock-cashflow-waterfall"',
        'id="stock-cashflow-waterfall-source"',
        'id="stock-company-valuation"',
        "기업 체력 한눈에 보기",
        "현금·안정성·효율",
        "매출 심층 분석",
        "동종 업계 영업이익률 추이",
        "판관비 심층분석",
        "현금 흐름 심층 분석",
        "밸류에이션 비교",
        "현재 · 예상 PER",
        "현금 사용 추적",
        "플러스는 현금 유입, 마이너스는 현금 유출",
        "순차입금비율은 (차입금·사채 - 현금성자산) ÷ 자본",
        "투자 체크포인트",
        'id="stock-financial-chart"',
        'id="stock-flow-history-chart"',
        'id="stock-home-checkpoints"',
        'id="stock-home-chart-analysis"',
        "최근 7일 수급",
        'id="stock-home-disclosures"',
        'id="stock-home-disclosures-summary"',
        'id="stock-home-disclosures-all"',
        'id="stock-home-disclosures-toggle"',
        "최근 1개월 공시",
        "전체 보기",
        'id="stock-report-history-chart"',
        'id="stock-news-temperature-chart"',
        'class="stock-v3-section stock-v3-chart-section stock-v3-news-temperature-section"',
        'id="quant-signal-chart"',
        'id="quant-current-label"',
        'id="quant-signal-refresh"',
        "AI 지금 이렇게 판단해요",
        "최근 1년 AI 시그널",
        "모든 매매내역 보기",
        'id="stock-share"',
        'id="stock-share-status"',
        'src="/dashboard-app-v170.js?v=',
    ):
        assert expected in shell.text
    assert "1,000만원 모의 운용" not in shell.text
    assert "네이버 종토방과 Threads에서 종목 반응을 함께 확인합니다." not in shell.text
    home_tab_index = shell.text.index('data-stock-tab="summary"')
    company_tab_index = shell.text.index('data-stock-tab="company"')
    strategy_tab_index = shell.text.index('data-stock-tab="strategy"')
    assert home_tab_index < company_tab_index < strategy_tab_index
    home_panel_index = shell.text.index('id="stock-summary-section"')
    company_panel_index = shell.text.index('id="stock-company-section"')
    finance_section_index = shell.text.index('id="stock-finance-section"')
    strategy_panel_index = shell.text.index('id="stock-strategy-section"')
    assert home_panel_index < company_panel_index < finance_section_index < strategy_panel_index

    source = client.get("/assets/dashboard/app.js").text
    assert 'state.stockPricePeriod = button.dataset.pricePeriod || "1D"' in source
    assert "function syncStockDetailTabsFixedState()" in source
    assert "function syncStockDetailCommandbarState()" in source
    assert "const shouldShowCompactQuote = stockTop <= -24" in source
    assert 'commandbar.classList.toggle("is-scrolled", shouldShowCompactQuote)' in source
    assert "const stockBottom = elements.stockView?.getBoundingClientRect().bottom ?? Number.POSITIVE_INFINITY;" in source
    assert "const withinStockBoundary = stockBottom > fixedTop + tabsHeight;" in source
    assert 'tabs.classList.toggle("is-fixed", sentinelTop <= fixedTop && withinStockBoundary)' in source
    assert 'window.addEventListener("resize", scheduleStockDetailTabsFixedState' in source
    assert 'state.stockFinancialMetric = button.dataset.financialMetric || "revenue"' in source
    assert '"#stock-finance-section": "company"' in source
    assert "function latestCompanyPerformance(data)" in source
    assert "function companyStatementMetrics(data, lines = state.stockFinancialLines)" in source
    assert "function renderStockCompanyAnalysis(data = state.currentDashboard)" in source
    assert "function companyRevenueBreakdownRows(data)" in source
    assert "function renderCompanyRevenueBreakdown(data)" in source
    assert "function renderCompanySectorMargins()" in source
    assert "function installCompanySectorMarginScrubber({" in source
    assert 'hitArea.setAttribute("role", "slider")' in source
    assert 'hitArea.addEventListener("pointermove", (event) => {' in source
    assert '["ArrowLeft", "ArrowRight", "Home", "End"]' in source
    assert 'const currentCode = String(state.currentStock?.code || "")' in source
    assert "stock-sector-margin-focus-card" in source
    assert "stock-sector-margin-scrub-hint" in source
    assert "/sector-operating-margins?limit=5" in source
    assert "/sector-operating-margins?limit=5&per_pair=1" in source
    assert "업계 중앙값" in source
    assert "function renderCompanySgaAnalysis()" in source
    sga_render_source = source[source.index("function renderCompanySgaAnalysis()") : source.index("const COMPANY_REPORT_LABELS")]
    assert "setStockBarTooltipTarget(" not in sga_render_source
    assert "installStockBarTooltips(" not in sga_render_source
    assert "/sga-analysis" in source
    assert "function renderCompanyFinancialHealth(data, metrics, statementLabel)" in source
    assert "function renderCompanyCashflowWaterfall(metrics, statementLabel)" in source
    assert "function renderCompanyPerComparison(data, valuation)" in source
    assert "기업별 PER 한눈에" in source
    assert "동종 경쟁사" in source
    assert "comparison.selection_reason" in source
    assert "companyPerComparisonSentence" in source
    assert "ifrs-full_CashFlowsFromUsedInInvestingActivities" in source
    assert "ifrs-full_CashFlowsFromUsedInFinancingActivities" in source
    assert "ifrs-full_IncreaseDecreaseInCashAndCashEquivalents" in source
    assert "cashFlowResidual: cashChange === null || coreCashFlow === null" in source
    assert "영업현금으로 투자활동 유출의" in source
    assert "환율·연결범위 등 기타 효과" in source
    assert "ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings" in source
    assert "ifrs-full_LongtermBorrowings" in source
    assert "ifrs-full_CostOfSales" in source
    assert "inventoryDays: companyRatio(averageInventory, annualizedCostOfSales, 365)" in source
    assert "netDebtRatio: companyRatio(netDebt, balance.equity)" in source
    assert "자산은 누구 돈으로 만들어졌나" in source
    assert "부채비율" in source
    assert "operatingCostRate: 100 - operatingMargin" in source
    assert "const isLoss = row.operatingMargin < 0" in source
    assert 'row.estimated ? "추정" : "실제"' in source
    assert "표시할 연간 매출·영업이익 자료가 없습니다." in source
    assert "/financials?limit=500" in source
    assert "현금이익비율" in source
    current_state_source = source[
        source.index("function quantSignalCurrentState") : source.index("function quantCurrentStatusView")
    ]
    assert 'headline: "매수 대기중"' in current_state_source
    assert 'headline: `${pendingStage}차 수익확정 대기중`' in current_state_source
    assert "current.pending_profit_stage || (profitStage + 1)" in current_state_source
    assert 'headline: "전량 매도 대기중"' in current_state_source
    assert '`${profitStage || latestEvent?.profit_stage || 1}차 수익확정 후 보유중` : "매수 후 보유중"' in current_state_source
    assert 'headline: "전량 매도 후 대기중"' in current_state_source
    assert current_state_source.index('latestEvent?.side === "sell"') < current_state_source.index("current.position_open")
    assert current_state_source.index('action === "entry_pending"') < current_state_source.index('latestEvent?.side === "sell"')
    assert '["buy", "partial_sell"].includes(latestEvent?.side)' in current_state_source
    assert "잉여현금흐름 FCF" in source
    assert "수익성 구조" in source
    assert "매출총이익률" in source
    assert "FCF 수익률" in source
    assert "매출 100% 중 영업비용" in source
    assert "영업비용이 매출의" in source
    assert "stock-revenue-chart-columns" in source
    styles = client.get("/assets/dashboard/styles.css").text
    assert ".stock-revenue-chart-bar {\n  position: absolute;\n  bottom: 0;" in styles
    assert "display: flex;\n  flex-direction: column-reverse;\n  overflow: hidden;\n  border-radius: 0;" in styles
    assert ".stock-revenue-chart-bar .cost {\n  border-radius: 0;" in styles
    assert ".stock-revenue-chart-bar .profit {\n  border-radius: 0;" in styles
    assert ".stock-revenue-chart-bar .loss {\n  border-radius: 0;" in styles
    assert "top: calc(62px + env(safe-area-inset-top, 0px));" in styles
    assert 'body[data-view="stock"] .shell {\n    will-change: auto;' in styles
    assert ".stock-detail-tabs.is-fixed {" in styles
    assert ".stock-v3-commandbar.is-scrolled {" in styles
    assert ".stock-v3-commandbar.is-scrolled .stock-v3-command-title h1 {\n    order: 0;" in styles
    assert ".stock-v3-commandbar.is-scrolled .stock-v3-command-quote {\n    order: 1;" in styles
    assert ".stock-detail-tabs.is-fixed ~ .stock-tab-panel:not([hidden])" in styles
    assert "transform: translateX(-50%);" in styles
    assert 'const stockName = String(data?.name || state.currentStock?.name || "선택 종목").trim()' in source
    assert 'setText(elements.stockRevenueBreakdownTitle, `${stockName} 매출 심층 분석`)' in source
    assert 'id="stock-revenue-breakdown-source"' not in shell.text
    assert "각 비율은 매출을 100%로 환산했습니다." not in shell.text
    assert '`${stockIdentity} · ${data?.financial_series?.source || "금융 데이터"} · 연간 실적`' not in source
    assert 'dashboardCode !== selectedCode' in source
    assert 'breakdownSection.dataset.stockCode = dashboardCode' in source
    assert "const labelLevelRate = Math.max(100, stackRate)" in source
    assert "marginLabel.style.bottom = `calc(${clampNumber((labelLevelRate / scaleMax) * 100, 8, 100)}% + 9px)`" in source
    assert "const stackRate = Math.max(0.01, costSegmentRate + resultSegmentRate)" in source
    assert "bar.style.height = `${(stackRate / scaleMax) * 100}%`" in source
    assert "cost.style.flexBasis = `${(costSegmentRate / stackRate) * 100}%`" in source
    assert "result.style.flexBasis = `${(resultSegmentRate / stackRate) * 100}%`" in source
    assert '`${yearLabel} 영업비용 ${formatRevenueShare(costRate)} · ${isLoss ? "영업손실률" : "영업이익률"}' in source
    assert "setStockBarTooltipTarget(cost" not in source
    assert "setStockBarTooltipTarget(result" not in source
    for expected in (
        "function dismissStockBarTooltip(container = null)",
        "function positionStockBarTooltip(container, target, tooltip)",
        "function showStockBarTooltip(container, target)",
        "function setStockBarTooltipTarget(target, text, options = {})",
        "function installStockBarTooltips(container)",
        'tooltip.setAttribute("role", "tooltip")',
        'container.addEventListener("keydown", (event) => {',
        'setStockBarTooltipTarget(bar, `${row.label} ${formatCompanySignedStatementAmount(row.value)}`)',
            'setStockBarTooltipTarget(barItem, `${company.name} ${item.label} ${formatCompanyMultiple(value)}`',
        'setStockBarTooltipTarget(target, `${row.month.replace("-", ".")} 리포트',
    ):
        assert expected in source
    assert 'plot.setAttribute("aria-hidden", "true")' not in source
    for expected in (
        ".stock-bar-value-tooltip {",
        "background: #111827;",
        ".stock-bar-tooltip-target:focus-visible {",
        ".stock-cashflow-waterfall-bar.stock-bar-tooltip-target::after {",
    ):
        assert expected in styles
    assert "직전 실제 연도보다 영업이익률이" in source
    assert 'el("span", tick.value === 100 ? "is-reference"' in source
    assert "단순 연환산 ROE" in source
    assert "매출채권 증가율" in source
    assert "재고 증가율" in source
    assert "function stockHomeSevenDayFlowRows()" in source
    assert "function renderStockHomeChartAnalysis" in source
    assert "renderStockHomeChartAnalysis();" in source
    assert "stockHomeChartHorizon: 10" in source
    assert "state.stockHomeChartHorizon = 10" in source
    assert "section.append(header, controls, visual, summary, clarification, renderChartPatternAnalysis(analysis, forecast, item), reasons);" in source
    assert "data-chart-horizon" in source
    assert "for (const days of [5, 10])" in source
    assert "#stock-home-chart-analysis.chart-forecast-host" in styles
    assert ".slice(-7)" in source
    assert "personal: -(row.foreign + row.institution)" in source
    assert "최근 7거래일 · 일별 순매수 금액" in source
    assert "최근 7거래일 개인 추정, 외국인, 기관 일별 순매수 금액 비교" in source
    assert "function installStockHomeFlowScrubber" in source
    assert 'stock-home-flow-chart stock-v3-flow-plot' in source
    assert "같은 날짜의 개인·외국인·기관 수급" in source
    assert "function applyStockFlowRowsToDashboard" in source
    assert "const recentDates = [...rowsByDate.keys()].sort().slice(-20);" in source
    assert 'rows.find((row) => row.investorType === "기관합계")' in source
    assert "applyStockFlowRowsToDashboard(data);" in source
    assert 'event.pointerType !== "mouse"' in source
    assert 'aria-label="최근 7거래일 투자자 수급 탐색"' in source
    assert ".stock-home-flow-line.personal" in styles
    assert ".stock-home-flow-chart .stock-v3-flow-focus-point.personal" in styles
    assert "touch-action: pan-y;" in styles
    mobile_two_column = styles.split("#stock-view.stock-detail-v3 .stock-v3-two-column {", 2)[2].split("}", 1)[0]
    assert "padding-inline: 0;" in mobile_two_column
    assert ".stock-home-disclosure-all {" in styles
    assert ".stock-home-disclosure-list {" in styles
    assert ".stock-home-disclosure-toggle {" in styles
    assert ".stock-home-disclosure-row {" in styles
    assert "min-height: 44px;" in styles
    assert 'state.stockFlowMode = button.dataset.flowMode || "cumulative"' in source
    assert '"1Y": { count: 264, months: 12, label: "1년" }' in source
    assert "async function ensureStockFlowHistory" in source
    assert "refresh=true&pages=${pages}" in source
    assert 'button.setAttribute("aria-pressed", active ? "true" : "false")' in source
    assert "과거 이력 확장 중" in source
    assert "void ensureStockFlowHistory(state.currentStock?.code" in source
    assert 'data-flow-mode="cumulative" aria-pressed="true"' in shell.text
    assert 'data-flow-period="3M" aria-pressed="true"' in shell.text
    assert 'id="stock-flow-summary" aria-live="polite"' in shell.text
    assert 'stock-v3-flow-context' not in shell.text
    assert 'stock-v3-flow-scrub-hit' in source
    assert "renderStockIntradayChart" in source
    assert 'marketOpen ? liveUrl(endpoint) : endpoint' in source
    assert 'meta?.source === "unavailable"' in source
    assert "당일 분봉을 불러오지 못했습니다. 잠시 후 다시 확인해 주세요." in source
    assert "표시할 당일 분봉 데이터가 없습니다." in source
    assert "한국투자증권 장마감 확정 분봉" not in source
    assert "네이버 금융 실제 수급" not in source
    assert 'id="stock-v2-chart-source"' not in shell.text
    assert 'id="stock-flow-source"' not in shell.text
    assert "renderStockReportHistoryChart" in source
    assert 'class="stock-v3-report-target"' in source
    assert 'class="stock-v3-report-target-point"' in source
    assert '.filter((provider) => provider?.key !== "threads")' in source
    assert 'provider.key === "threads" && providerWithItems(provider)' not in source
    assert "/home-context?flow_limit=1500" in source
    assert "disclosure_limit=100" in source
    assert "function stockOneMonthDisclosureRows(data)" in source
    assert "function renderStockHomeDisclosures(data)" in source
    assert "stockHomeDisclosuresExpanded" in source
    assert "const disclosureLimit = 5;" in source
    assert "function installStockFlowScrubber({" in source
    assert 'hitArea.addEventListener("pointermove", (event) => {' in source
    assert "같은 날짜의 외국인·기관·주가" in source
    assert "rows.slice(0, disclosureLimit)" in source
    assert 'aria-expanded", state.stockHomeDisclosuresExpanded ? "true" : "false"' in source
    assert 'state.stockHomeDisclosuresExpanded = !state.stockHomeDisclosuresExpanded' in source
    assert "cutoff.setDate(cutoff.getDate() - 30)" in source
    assert 'date && date >= cutoffDate && date <= referenceDate' in source
    assert 'https://dart.fss.or.kr/dsab001/main.do?' in source
    assert 'params.set("textCrpCik", corpCode)' in source
    assert 'node.target = "_blank"' in source
    assert 'renderStockHomeDisclosures(data);' in source
    assert 'data-report-mode="issuance"' in shell.text
    assert 'data-report-mode="broker"' in shell.text
    assert ">발행 추이</button>" in shell.text
    assert "stockReportModeTabs" in source
    news_section = shell.text.split('id="stock-news-section"', 1)[1].split("</article>", 1)[0]
    assert "<h2>종목뉴스</h2>" in news_section
    assert 'id="news-list" aria-live="polite"' in news_section
    assert "data-news-mode" not in news_section
    assert "AI 속보" not in news_section
    assert "stockNewsModeTabs" not in source
    assert "stockNewsMode" not in source
    assert "function naverNewsArticleUrl(row)" in source
    assert 'return naverResearchDetailUrl(row) || naverNewsArticleUrl(row)' in source
    assert "https://n.news.naver.com/mnews/article/" in source
    assert 'sourceRows.filter((row) => row.source_category !== "breaking")' in source
    assert "filteredRows = sourceRows;" not in source
    assert "최근 AI 속보가 없습니다." not in source
    assert '"최근 종목뉴스가 없습니다."' in source
    assert "stock-v3-news-list" in shell.text
    assert '"stock-v3-news-thumb"' in source
    assert "row.image_url" in source
    assert 'formatDate(updateItemDate(row))' in source
    assert "const height = 178;" in source
    assert 'y="170"' in source
    assert "renderQuantSignalChart" in source
    assert "/quant-signals" in source
    assert "quantSignalMarkers" in source
    assert "ensureStockAIAnalysis();" in source
    assert "function navigateToStock(query, href = viewStockUrl(query))" in source
    assert "async function shareCurrentStock()" in source
    assert 'typeof navigator.share === "function"' in source
    assert 'showStockShareStatus("종목 상세 링크를 복사했습니다.")' in source
    assert 'return load(normalized, { historyMode: "none" });' in source
    assert "const quantSignalPrefetch = loadQuantSignals({ auto: true });" not in source
    assert 'return tabName === "strategy" && Boolean(state.currentStock?.code);' in source
    assert "ensureStockCompanyAnalysis();" in source
    assert 'a[href^="/dashboard/"]' in source
    assert 'classList.remove("has-saved-watchlist-id")' in source
    assert 'classList.add("has-saved-watchlist-id")' in source
    assert 'id="stock-summary-ai-badge"' not in shell.text
    assert "stockSummaryAIBadge" not in source
    assert 'badge.textContent = "Ollama AI 분석 중";' in source
    assert 'badge.textContent = "AI 분석 확인 실패";' in source
    assert 'headline: "전량 매도 후 대기중"' in source
    assert "AI 전략 기준 현재 상태" not in shell.text
    assert "AI 모의 전략 ·" not in source
    assert 'id="quant-current-score"' not in shell.text
    assert "원에 모두 팔았어요" not in source
    assert "AI가 과거 데이터로 계산한 교육·연구용 참고 신호이며" in source
    assert "실제 계좌 주문" not in source
    assert "오늘의 대응" not in shell.text
    assert "판단 근거와 위험 보기" not in shell.text

    styles = client.get("/assets/dashboard/styles.css").text
    assert "aspect-ratio: 19 / 8" in styles
    assert "/* iPhone 16 Pro (402 CSS px)" in styles
    assert "@media (max-width: 430px)" in styles
    assert '"Apple SD Gothic Neo"' in styles
    assert "--stock-v3-type-display: 38px" in styles
    assert "--stock-v3-type-tab: 16px" in styles
    assert "#stock-view.stock-detail-v3 .stock-v3-report-target-point" in styles
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in styles
    assert ".stock-investment-snapshot-row" in styles
    assert ".stock-company-metric-list" in styles
    assert ".stock-company-valuation-bars" in styles
    assert ".stock-per-comparison" in styles
    assert ".stock-per-groups" in styles
    assert ".stock-per-bar-item.is-forward" in styles
    assert ".stock-per-company-captions" in styles
    assert "--company-type-kicker: 11px;" in styles
    assert "--company-type-title: 21px;" in styles
    assert "--company-type-meta: 11px;" in styles
    assert "--company-type-tab: 15px;" in styles
    assert "--company-type-lead: 14px;" in styles
    assert "--company-type-body: 13px;" in styles
    assert "--company-type-note: 11px;" in styles
    assert "--company-type-chart-axis: 10px;" in styles
    assert "--company-type-chart-value: 12px;" in styles
    assert "Company analysis typography system." in styles
    assert styles.rindex("Company analysis typography system.") > styles.rindex(
        "#stock-view.stock-detail-v3 .stock-company-valuation-bar"
    )
    assert ".stock-v3-company .stock-v3-section-head h2" in styles
    assert ".stock-financial-health-kpis" in styles
    assert ".stock-sector-margin-series.is-target" in styles
    assert ".stock-sector-margin-scrub-hit" in styles
    assert "touch-action: pan-y;" in styles
    assert ".stock-sector-margin-focus-card" in styles
    assert ".stock-v3-flow-focus-card" in styles
    assert ".stock-v3-flow-scrub-hint" in styles
    assert ".stock-sector-margin-value.is-active" in styles
    assert ".stock-sector-margin-legend" in styles
    assert ".stock-sga-category-details" in styles
    assert ".stock-sga-category.is-largest" in styles
    assert ".stock-sga-category > summary.stock-bar-tooltip-target" not in styles
    assert ".stock-balance-composition" in styles
    assert ".stock-balance-funding .liability" in styles
    funding_label_css = styles.split("#stock-view.stock-detail-v3 .stock-balance-funding span {", 1)[1].split("}", 1)[0]
    assert "line-height: 1.25;" in funding_label_css
    assert "text-overflow: clip;" in funding_label_css
    assert "white-space: normal;" in funding_label_css
    assert "@media (max-width: 360px)" in styles
    assert "min-height: 52px;" in styles
    assert ".stock-cashflow-waterfall-columns" in styles
    assert ".stock-cashflow-waterfall-bar.is-outflow" in styles
    assert ".stock-cashflow-waterfall-summary" in styles
    assert "@media (max-width: 390px)" in styles
    assert "vector-effect: non-scaling-stroke" in styles
    assert ".stock-v3-news-temperature-section .stock-v3-main-chart" in styles
    assert ".stock-v3-news-temperature-section .stock-v3-temperature-gauge" in styles
    assert ".stock-v3-news-link" in styles
    assert ".stock-v3-news-title" in styles
    assert ".stock-v3-news-thumb" in styles
    assert "min-height: 74px;" in styles
    assert "html.has-saved-watchlist-id .login-gate" not in styles
    assert 'id="login-gate" data-phase="splash"' in shell.text


def test_stock_detail_commandbar_reveals_quote_after_mobile_scroll_without_interrupting_search():
    source = TestClient(app).get("/assets/dashboard/app.js").text
    start = source.index("function syncStockDetailCommandbarState()")
    function_source = source[start : source.index("function syncStockDetailTabsFixedState()", start)]
    script = f"""
let stockTop = 0;
let searchExpanded = false;
const classes = new Set();
const commandbar = {{
  classList: {{
    remove: (name) => classes.delete(name),
    toggle: (name, active) => active ? classes.add(name) : classes.delete(name),
  }},
}};
const state = {{ stockEtfDividendPageOpen: false }};
const elements = {{
  stockCommandbar: commandbar,
  stockView: {{ hidden: false, getBoundingClientRect: () => ({{ top: stockTop }}) }},
  form: {{ classList: {{ contains: () => searchExpanded }} }},
}};
const document = {{ body: {{ dataset: {{ view: "stock" }} }} }};
const window = {{ innerWidth: 402 }};
{function_source}
const snapshots = [];
for (const scenario of [
  {{ top: 0, expanded: false }},
  {{ top: -23, expanded: false }},
  {{ top: -24, expanded: false }},
  {{ top: -80, expanded: true }},
]) {{
  stockTop = scenario.top;
  searchExpanded = scenario.expanded;
  syncStockDetailCommandbarState();
  snapshots.push(classes.has("is-scrolled"));
}}
state.stockEtfDividendPageOpen = true;
searchExpanded = false;
syncStockDetailCommandbarState();
snapshots.push(classes.has("is-scrolled"));
console.log(JSON.stringify(snapshots));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == [False, False, True, False, False]


def test_short_company_summary_corrects_korean_topic_particle():
    assert _short_company_summary(
        "신라젠는 항암 신약개발을 목적으로 설립된 기업입니다.",
        "신라젠",
    ) == "신라젠은 항암 신약개발을 목적으로 설립된 기업입니다."
    assert _short_company_summary(
        "기아은 자동차를 제조하는 기업입니다.",
        "기아",
    ) == "기아는 자동차를 제조하는 기업입니다."


def test_naver_snapshot_preserves_annual_and_quarterly_series(monkeypatch):
    html = """
    <html><body>
      <table class="tb_type1 tb_num tb_type1_ifrs">
        <thead>
          <tr><th>주요재무정보</th><th colspan="2">최근 연간 실적</th><th colspan="1">최근 분기 실적</th></tr>
        </thead>
        <tbody>
          <tr><th>2024.12</th><th>2025.12 (E)</th><th>2026.03</th></tr>
          <tr><th>매출액</th><td>100,000</td><td>120,000</td><td>35,000</td></tr>
          <tr><th>영업이익</th><td>20,000</td><td>28,000</td><td>9,000</td></tr>
          <tr><th>당기순이익</th><td>15,000</td><td>22,000</td><td>7,000</td></tr>
          <tr><th>영업이익률</th><td>20.0</td><td>23.3</td><td>25.7</td></tr>
          <tr><th>순이익률</th><td>15.0</td><td>18.3</td><td>20.0</td></tr>
          <tr><th>EPS(원)</th><td>1,500</td><td>2,200</td><td>700</td></tr>
        </tbody>
      </table>
    </body></html>
    """

    class Response:
        text = html
        encoding = "utf-8"

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(stock_dashboard.requests, "get", lambda *args, **kwargs: Response())
    snapshot = stock_dashboard._fetch_naver_snapshot("000660")

    series = snapshot["financial_series"]
    assert len(series["annual"]) == 2
    assert len(series["quarterly"]) == 1
    assert series["annual"][1]["estimated"] is True
    assert series["annual"][0]["revenue"] == Decimal("100000")
    assert series["quarterly"][0]["operating_profit"] == Decimal("9000")
