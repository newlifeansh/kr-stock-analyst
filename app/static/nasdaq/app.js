const $ = (id) => document.getElementById(id);

const elements = {
  appFrame: document.querySelector(".app-frame"),
  appSplash: $("app-splash"),
  loginGate: $("login-gate"),
  loginSplash: $("login-splash"),
  loginForm: $("login-form"),
  loginInput: $("login-id-input"),
  loginStatus: $("login-status"),
  pullRefreshIndicator: $("pull-refresh-indicator"),
  pullRefreshLabel: $("pull-refresh-label"),
  form: $("stock-form"),
  input: $("stock-code"),
  suggestions: $("stock-suggestions"),
  stockView: $("stock-view"),
  stockOverviewView: $("stock-overview-view"),
  stockDetailLayout: $("stock-detail-layout"),
  stockSectionTabs: Array.from(document.querySelectorAll("[data-stock-tab]")),
  stockTabPanels: Array.from(document.querySelectorAll("[data-stock-panel]")),
  watchlistView: $("watchlist-view"),
  watchlistIdForm: $("watchlist-id-form"),
  watchlistIdInput: $("watchlist-id-input"),
  watchlistIdDisplay: $("watchlist-id-display"),
  watchlistIdStatus: $("watchlist-id-status"),
  logoutButton: $("logout-button"),
  recommendView: $("recommend-view"),
  recommendHistoryView: $("recommend-history-view"),
  trendView: $("trend-view"),
  chartView: $("chart-view"),
  chartHistoryView: $("chart-history-view"),
  marketView: $("market-view"),
  watchToggle: $("watch-toggle"),
  aiAnalysisButton: $("ai-analysis-button"),
  aiAnalysisPanel: $("ai-analysis-panel"),
  aiAnalysisMeta: $("ai-analysis-meta"),
  aiAnalysisStance: $("ai-analysis-stance"),
  aiAnalysisSummary: $("ai-analysis-summary"),
  aiDecisionStance: $("ai-decision-stance"),
  aiDecisionConfidence: $("ai-decision-confidence"),
  aiDecisionEntry: $("ai-decision-entry"),
  aiDecisionCondition: $("ai-decision-condition"),
  aiKeyPoints: $("ai-key-points"),
  aiStrategy: $("ai-strategy"),
  aiRisks: $("ai-risks"),
  aiSectionList: $("ai-section-list"),
  stockSummaryScoreRing: $("stock-summary-score-ring"),
  stockSummaryScore: $("stock-summary-score"),
  stockSummaryConfidence: $("stock-summary-confidence"),
  stockSummaryStance: $("stock-summary-stance"),
  stockSummaryLine: $("stock-summary-line"),
  stockMiniChart: $("stock-mini-chart"),
  stockSignalChart: $("stock-signal-chart"),
  stockSignalChartBar: $("stock-signal-chart-bar"),
  stockSignalFlow: $("stock-signal-flow"),
  stockSignalFlowBar: $("stock-signal-flow-bar"),
  stockSignalValuation: $("stock-signal-valuation"),
  stockSignalValuationBar: $("stock-signal-valuation-bar"),
  stockSignalNews: $("stock-signal-news"),
  stockSignalNewsBar: $("stock-signal-news-bar"),
  stockStrategyStatus: $("stock-strategy-status"),
  stockStrategyStance: $("stock-strategy-stance"),
  stockPriceLadder: $("stock-price-ladder"),
  watchlistMeta: $("watchlist-meta"),
  watchlistBody: $("watchlist-body"),
  recommendMeta: $("recommend-meta"),
  recommendButton: $("recommend-button"),
  recommendArchiveButton: $("recommend-archive-button"),
  recommendHistoryNewButton: $("recommend-history-new-button"),
  recommendStatus: $("recommend-status"),
  recommendList: $("recommend-list"),
  recommendHistoryMeta: $("recommend-history-meta"),
  recommendHistoryList: $("recommend-history-list"),
  trendMeta: $("trend-meta"),
  trendTitle: $("trend-title"),
  trendEventsTitle: $("trend-events-title"),
  trendRefresh: $("trend-refresh"),
  trendHeadline: $("trend-headline"),
  trendTabsWrap: $("trend-tabs"),
  trendTabs: Array.from(document.querySelectorAll(".trend-tab")),
  trendEventsPanel: $("trend-events-panel"),
  trendLivePanel: $("trend-live-panel"),
  trendPastPanel: $("trend-past-panel"),
  trendEvents: $("trend-events"),
  trendPastEvents: $("trend-past-events"),
  trendThread: $("trend-thread"),
  watchChartMeta: $("watch-chart-meta"),
  watchChartRefresh: $("watch-chart-refresh"),
  chartArchiveButton: $("chart-archive-button"),
  chartHistoryBackButton: $("chart-history-back-button"),
  watchChartList: $("watch-chart-list"),
  watchChartSnapshotMeta: $("watch-chart-snapshot-meta"),
  watchChartSnapshots: $("watch-chart-snapshots"),
  homeInstallButton: $("home-install-button"),
  installSheet: $("install-sheet"),
  installSheetBackdrop: $("install-sheet-backdrop"),
  installSheetClose: $("install-sheet-close"),
  installSteps: $("install-steps"),
  installSheetSubtitle: $("install-sheet-subtitle"),
  flowLoadingModal: $("flow-loading-modal"),
  mobileMenuToggle: $("mobile-menu-toggle"),
  mobileMenuScrim: $("mobile-menu-scrim"),
  mobilePageTitle: $("mobile-page-title"),
  sideNav: $("side-nav"),
  sidebarPresenceCount: $("sidebar-presence-count"),
  sideItems: Array.from(document.querySelectorAll(".side-menu-item")),
  sectionShellTopbar: $("section-shell-topbar"),
  sectionShellTitle: $("section-shell-title"),
  sectionShellMeta: $("section-shell-meta"),
  sectionShellViewMode: $("section-shell-view-mode"),
  sectionShellRefresh: $("section-shell-refresh"),
  sectionShellFilters: $("section-shell-filters"),
  sectionShellPrimaryTabs: $("section-shell-primary-tabs"),
  sectionShellSecondaryTabs: $("section-shell-secondary-tabs"),
  sectionShellKeyword: $("section-shell-keyword"),
  sectionShellStartDate: $("section-shell-start-date"),
  sectionShellEndDate: $("section-shell-end-date"),
  sectionShellDateDivider: $("section-shell-date-divider"),
  sectionShellCategory: $("section-shell-category"),
  sectionShellAuxOne: $("section-shell-aux-one"),
  sectionShellAuxTwo: $("section-shell-aux-two"),
  sectionShellReset: $("section-shell-reset"),
  sectionShellPrimaryAction: $("section-shell-primary-action"),
  sectionShellSecondaryAction: $("section-shell-secondary-action"),
  rankTabs: Array.from(document.querySelectorAll(".rank-tab")),
  rankCategorySelect: $("rank-category-select"),
  marketFilter: $("market-filter"),
  marketTabs: Array.from(document.querySelectorAll("[data-market-filter]")),
  marketMeta: $("market-meta"),
  rankingBody: $("ranking-body"),
  name: $("stock-name"),
  meta: $("stock-meta"),
  stockCardName: $("stock-card-name"),
  stockDetailTitle: $("stock-detail-title"),
  stockDetailSource: $("stock-detail-source"),
  stockLiveBadge: $("stock-live-badge"),
  stockPreMarket: $("stock-pre-market"),
  stockChangeValue: $("stock-change-value"),
  stockVolume: $("stock-volume"),
  stockPrevCloseSummary: $("stock-prev-close-summary"),
  stockPrevClose: $("stock-prev-close"),
  stockOpen: $("stock-open"),
  stockHigh: $("stock-high"),
  stockLow: $("stock-low"),
  stockVolumeDetail: $("stock-volume-detail"),
  stockTradingValueDetail: $("stock-trading-value-detail"),
  stockMarketCapDetail: $("stock-market-cap-detail"),
  stockForeignRatio: $("stock-foreign-ratio"),
  stockEps: $("stock-eps"),
  stockBps: $("stock-bps"),
  stockDividendYield: $("stock-dividend-yield"),
  stockDividendPerShare: $("stock-dividend-per-share"),
  stockTargetPrice: $("stock-target-price"),
  stockLatestOpinion: $("stock-latest-opinion"),
  stockLatestReportAt: $("stock-latest-report-at"),
  quotePrice: $("quote-price"),
  quoteChange: $("quote-change"),
  quoteValue: $("quote-value"),
  quoteCap: $("quote-cap"),
  chartScore: $("chart-score"),
  chartStance: $("chart-stance"),
  chartTrend: $("chart-trend"),
  chartSetup: $("chart-setup"),
  chartRisk: $("chart-risk"),
  chartVolume: $("chart-volume"),
  chartSupport: $("chart-support"),
  chartResistance: $("chart-resistance"),
  chartSignals: $("chart-signals"),
  chartRisks: $("chart-risks"),
  evidenceSummaryChart: $("evidence-summary-chart"),
  evidenceSummaryFlow: $("evidence-summary-flow"),
  evidenceSummaryValue: $("evidence-summary-value"),
  evidenceSummaryNews: $("evidence-summary-news"),
  estimateRevenue: $("estimate-revenue"),
  estimateProfit: $("estimate-profit"),
  estimateEps: $("estimate-eps"),
  revisionCount: $("revision-count"),
  revisionUp: $("revision-up"),
  revisionDown: $("revision-down"),
  revisionRatio: $("revision-ratio"),
  momentum1m: $("momentum-1m"),
  momentum3m: $("momentum-3m"),
  valueChange: $("value-change"),
  foreignFlow: $("foreign-flow"),
  institutionFlow: $("institution-flow"),
  foreignIntensity: $("foreign-intensity"),
  institutionIntensity: $("institution-intensity"),
  per: $("per"),
  pbr: $("pbr"),
  estimatedPer: $("estimated-per"),
  industryPer: $("industry-per"),
  perZ: $("per-z"),
  pbrZ: $("pbr-z"),
  evEbitdaZ: $("ev-ebitda-z"),
  latestRevenue: $("latest-revenue"),
  latestProfit: $("latest-profit"),
  latestEps: $("latest-eps"),
  profitGrowth: $("profit-growth"),
  surpriseList: $("surprise-list"),
  guidanceList: $("guidance-list"),
  sentimentScore: $("sentiment-score"),
  sentimentCounts: $("sentiment-counts"),
  newsList: $("news-list"),
  newsEvidenceList: $("news-evidence-list"),
  macroRate: $("macro-rate"),
  macroFx: $("macro-fx"),
  macroCommodity: $("macro-commodity"),
  macroExport: $("macro-export"),
  displayCurrencyToggle: $("display-currency-toggle"),
  displayCurrencyLabel: $("display-currency-label"),
};

const WATCHLIST_KEY = "analyst.us.watchlist";
const WATCHLIST_ID_KEY = "analyst.us.watchlistId";
const RECOMMENDATION_HISTORY_KEY = "analyst.us.recommendationSnapshots";
const RECOMMENDATION_TRACK_KEY = "analyst.us.recommendationTracks";
const RECOMMENDATION_COOLDOWN_KEY = "analyst.us.recommendationCooldown";
const CHART_SNAPSHOT_KEY = "analyst.us.chartSnapshots";
const CURRENCY_MODE_KEY = "analyst.us.currencyMode";
const LOGIN_SPLASH_DURATION_MS = 5_000;
const APP_SPLASH_DURATION_MS = 5_000;
const DEFAULT_USDKRW_RATE = 1400;
const UI_CACHE_TTL_MS = 60_000;
const PAGE_ENTRY_MINUTE_MS = 60_000;
const RECOMMENDATION_LIMIT = 10;
const RECOMMENDATION_REGULAR_COOLDOWN_MS = 10 * 60 * 1000;
const RECOMMENDATION_OFFHOURS_COOLDOWN_MS = 30 * 60 * 1000;
const PULL_REFRESH_TRIGGER_DISTANCE = 72;
const PULL_REFRESH_MAX_DISTANCE = 104;
const PULL_REFRESH_DRAG_OFFSET = 10;
const STOCK_OVERVIEW_SYMBOL_LIMIT = 10;
const STOCK_OVERVIEW_SECTION_LIMIT = 5;
const COMPONENT_LABELS = {
  estimate_revision: "추정치",
  analyst_revision_ratio: "상향비율",
  surprise: "실적",
  guidance: "가이던스",
  price_momentum: "모멘텀",
  trading_value: "거래대금",
  valuation: "밸류",
  macro: "거시",
  flows: "수급",
  sentiment: "뉴스",
};

const TREND_FOCUS_EVENT_AXES = {
  "미국 금리·달러 방향 점검": ["금리", "달러"],
  "AI 설비투자와 반도체 수요": ["AI"],
};

const TREND_AXIS_CLASS = {
  금리: "axis-rate",
  달러: "axis-dollar",
  AI: "axis-ai",
};

const MARKET_IMPACT_FACTORS = [
  {
    key: "rate",
    label: "금리",
    className: "rate",
    keywords: ["금리", "yield", "10y", "10년물", "연준", "fomc", "fed", "pce", "고용", "실업"],
    goodWords: ["인하", "하락", "둔화", "완화", "비둘기", "soft landing"],
    badWords: ["인상", "상승", "긴축", "매파", "higher for longer"],
    goodText: "금리 부담이 낮아지면 미국 성장주 멀티플과 기술주 심리에 우호적입니다.",
    badText: "금리 부담이 커지면 고PER 성장주와 장기 스토리 종목 밸류에이션에 압박이 생깁니다.",
    defaultStocks: ["MSFT", "AAPL", "AMZN", "META"],
  },
  {
    key: "dollar",
    label: "달러",
    className: "dollar",
    keywords: ["달러", "usd", "dxy", "환율", "fx", "외환"],
    goodWords: ["약세", "하락", "안정", "완화"],
    badWords: ["강세", "상승", "급등", "압박"],
    goodText: "달러 부담이 완화되면 글로벌 리스크 선호와 대형 성장주 심리에 우호적일 수 있습니다.",
    badText: "달러가 강하면 글로벌 유동성 부담이 커지고 위험자산 선호가 약해질 수 있습니다.",
    defaultStocks: ["AAPL", "NVDA", "TSLA", "AMZN"],
  },
  {
    key: "bond",
    label: "채권",
    className: "bond",
    keywords: ["채권", "국채", "yield", "장기금리", "2y", "10y", "bond"],
    goodWords: ["하락", "안정", "완화", "수익률 둔화"],
    badWords: ["상승", "급등", "불안", "변동성 확대"],
    goodText: "채권금리 안정은 주식의 상대 매력을 회복시키는 신호가 됩니다.",
    badText: "채권수익률 상승은 주식보다 채권 매력을 키워 성장주에 부담을 줍니다.",
    defaultStocks: ["MSFT", "GOOGL", "CRM", "NVDA"],
  },
  {
    key: "commodity",
    label: "원자재",
    className: "commodity",
    keywords: ["원유", "유가", "wti", "브렌트", "commodity", "구리", "전력", "천연가스"],
    goodWords: ["하락", "완화", "안정", "공급 개선"],
    badWords: ["상승", "급등", "부족", "비용 압박"],
    goodText: "원자재 부담이 낮아지면 소비주와 일부 제조업 마진 기대에 우호적입니다.",
    badText: "원자재가 강하면 전력·물류·원가 부담이 커져 마진이 흔들릴 수 있습니다.",
    defaultStocks: ["TSLA", "AMZN", "CEG", "XOM"],
  },
  {
    key: "risk",
    label: "위험자산",
    className: "risk",
    keywords: ["ai", "나스닥", "growth", "기술주", "반도체", "risk-on", "risk-off", "capex", "gpu", "hbm"],
    goodWords: ["상승", "강세", "확대", "랠리", "투자 확대", "수요 호조"],
    badWords: ["하락", "약세", "둔화", "감소", "투자 축소", "조정"],
    goodText: "AI와 위험자산 선호가 강하면 나스닥과 반도체 주도주의 유동성이 강화되기 쉽습니다.",
    badText: "위험자산 심리가 식으면 나스닥 주도 성장주가 같이 눌릴 가능성이 큽니다.",
    defaultStocks: ["NVDA", "AVGO", "AMD", "PLTR"],
  },
];

const MARKET_IMPACT_IMPORTANCE_WEIGHT = {
  "매우 중요": 22,
  중요: 16,
  보통: 10,
};

const RECOMMEND_TERM_HELP = {
  현재가: "현재 앱이 가진 최신 보조 시세입니다. 실시간 거래소 체결가와는 차이가 날 수 있습니다.",
  등락률: "전일 종가 대비 현재 가격이 얼마나 올랐거나 내렸는지 보는 값입니다.",
  "1개월": "약 한 달 전 가격과 비교한 수익률입니다. 단기 추세가 살아있는지 볼 때 씁니다.",
  "3개월": "약 세 달 전 가격과 비교한 수익률입니다. 중기 추세와 과열 여부를 같이 봅니다.",
  거래대금: "가격에 거래량을 곱한 값입니다. 돈이 실제로 많이 들어오는 종목인지 볼 때 중요합니다.",
  차트점수: "이동평균선, 지지·저항, 거래량, 변동성을 합쳐 지금 차트가 행동하기 좋은지 점수화한 값입니다.",
  판단: "차트 점수와 추세를 바탕으로 지금 매수 관찰인지, 대기인지 요약한 문장입니다.",
  추세: "가격과 이동평균선 배열로 상승 흐름인지, 박스권인지, 약세인지 판단한 값입니다.",
  셋업: "지금 차트가 돌파 구간인지, 눌림목인지, 지지 이탈인지 같은 매매 상황입니다.",
  리스크: "ATR, 지지선 이탈, 평균선 하회 등 차트상 조심해야 할 정도입니다.",
  지지: "가격이 내려올 때 버텨주길 기대하는 구간입니다. 이탈하면 비중 축소 기준으로 봅니다.",
  저항: "가격이 올라갈 때 막힐 수 있는 구간입니다. 거래대금과 함께 넘으면 추가 상승 가능성을 봅니다.",
  추정치: "애널리스트 목표가, EPS, 매출 추정 등 이익 기대가 좋아지는지 보는 점수입니다.",
  상향비율: "목표가나 추정치를 올린 애널리스트 비율입니다. 높을수록 시장 기대가 좋아진 쪽입니다.",
  실적: "최근 실적 발표나 SEC filing이 기대보다 좋았는지 나빴는지 반영한 점수입니다.",
  가이던스: "회사나 시장이 앞으로 실적 전망을 좋게 보는지 나쁘게 보는지 반영합니다.",
  모멘텀: "1개월·3개월 가격 흐름과 차트 힘을 함께 본 점수입니다.",
  밸류: "PER/PBR 등 가격 부담이 과거 또는 섹터 평균 대비 과한지 낮은지 보는 점수입니다.",
  거시: "미국 금리, 달러, 원자재, 글로벌 수요가 종목에 우호적인지 보는 점수입니다.",
  수급: "거래대금과 ETF/대형주 흐름으로 미장 유동성을 대체 판단한 점수입니다.",
  유동성: "거래대금과 ETF/대형주 흐름으로 미장 유동성을 대체 판단한 점수입니다.",
  뉴스: "최근 뉴스 제목과 요약의 분위기가 호재 쪽인지 악재 쪽인지 본 점수입니다.",
};

const STOCK_TERM_HELP = {
  ...RECOMMEND_TERM_HELP,
  "차트 점수": "이동평균선, 지지·저항, 거래량, 변동성을 합쳐 지금 차트가 행동하기 좋은지 점수화한 값입니다.",
  셋업: "지금 차트가 돌파 구간인지, 눌림목인지, 지지 이탈인지 같은 매매 상황입니다.",
  거래량: "최근 거래량이 평소보다 늘었는지 보는 값입니다. 가격 상승과 함께 늘면 매수세가 붙은 것으로 봅니다.",
  시가총액: "주가에 발행주식 수를 곱한 회사 규모입니다. 대형주는 비교적 안정적이고 중소형주는 변동성이 큰 편입니다.",
  "추정 매출": "애널리스트가 예상하는 앞으로의 매출입니다. 올라가면 성장 기대가 커진 것으로 봅니다.",
  "추정 영업이익": "애널리스트가 예상하는 앞으로의 본업 이익입니다. 주가에는 매출보다 더 직접적으로 반영되는 경우가 많습니다.",
  "추정 EPS": "예상 순이익을 주식 수로 나눈 값입니다. EPS가 오르면 이익 체력이 좋아진 것으로 해석합니다.",
  리포트: "최근 애널리스트 보고서 수입니다. 많을수록 시장에서 관심 있게 보고 있다는 뜻입니다.",
  "거래대금 변화": "최근 거래대금이 과거보다 늘었는지 줄었는지 보는 값입니다. 상승과 함께 늘면 힘이 붙은 흐름입니다.",
  "대형주 자금": "미장 대형주로 자금이 들어오는지 보는 대체 지표입니다. 무료 데이터에서는 비어 있을 수 있습니다.",
  "ETF/펀드": "ETF와 거래대금 흐름으로 미장 자금 흐름을 보완해서 보는 자리입니다.",
  "유동성 강도": "현재 거래대금이 평소보다 강한지 보는 값입니다.",
  "ETF 흐름": "QQQ, SPY 같은 미국 ETF 흐름을 함께 확인할 때 쓰는 자리입니다.",
  "개별 거래대금 변화": "최근 개별 종목 거래대금이 평소보다 얼마나 강해졌는지 보는 값입니다. 가격과 함께 늘면 관심이 다시 붙는 흐름으로 봅니다.",
  "섹터 ETF 흐름": "해당 종목과 가장 가까운 미국 섹터 ETF의 거래대금 변화입니다. 개별 종목 흐름이 혼자 가는지, 섹터 전체가 같이 움직이는지 볼 때 씁니다.",
  "개별 유동성 점수": "개별 종목 거래대금이 평소보다 얼마나 강한지 점수처럼 읽는 자리입니다.",
  "ETF 유동성 점수": "섹터 ETF 쪽 거래가 평소보다 강한지 보는 자리입니다. 미장에서는 개별 종목보다 ETF 쪽 자금이 먼저 움직일 때가 많습니다.",
  PER: "주가가 1년 이익의 몇 배로 거래되는지 보는 지표입니다. 낮다고 무조건 싸지는 않고 성장성과 함께 봅니다.",
  PBR: "주가가 회사 순자산의 몇 배인지 보는 지표입니다. 은행·보험·자산주처럼 자산가치가 중요한 업종에서 특히 자주 봅니다.",
  추정PER: "예상 이익 기준 PER입니다. 현재 이익보다 앞으로의 이익 기대가 반영됩니다.",
  업종PER: "같은 섹터 평균 PER입니다. 내 종목이 섹터 평균 대비 비싼지 싼지 비교할 때 씁니다.",
  섹터PER: "같은 섹터 평균 PER입니다. 내 종목이 섹터 평균 대비 비싼지 싼지 비교할 때 씁니다.",
  "PER z": "현재 PER이 과거 평균보다 얼마나 높거나 낮은지 표준화한 값입니다. 높으면 과거 대비 부담이 큽니다.",
  "PBR z": "현재 PBR이 과거 평균보다 얼마나 높거나 낮은지 표준화한 값입니다. 높으면 자산가치 대비 부담이 큽니다.",
  "최근 매출": "가장 최근 발표된 매출입니다. 전년 대비 성장 여부와 함께 봅니다.",
  "최근 영업이익": "가장 최근 발표된 본업 이익입니다. 실적 서프라이즈 판단의 핵심입니다.",
  "최근 EPS": "최근 순이익을 주식 수로 나눈 값입니다. 주당 이익 체력을 보여줍니다.",
  "영업이익 변화": "최근 영업이익이 전년 또는 직전 기준으로 얼마나 변했는지 보여줍니다.",
  "금리 민감도": "미국 10년물과 연준 기대 변화에 얼마나 민감한지 보는 대리 지표입니다.",
  "달러 민감도": "달러 강세·약세가 매출, 원가, 멀티플에 주는 영향을 보는 자리입니다.",
  "원자재 민감도": "원유·금속 같은 원자재 가격 변화에 얼마나 영향을 받는지 보는 대리 지표입니다.",
  "리스크 선호": "미국 대형 성장주와 위험자산 선호가 살아날 때 같이 탄력을 받을지 보는 자리입니다.",
};

const state = {
  view: ["market", "watchlist", "recommend", "recommend-history", "trend", "trend-past", "trend-impact", "chart", "chart-history"].includes(new URLSearchParams(window.location.search).get("view"))
    ? new URLSearchParams(window.location.search).get("view")
    : "stock",
  rankingCategory: "surge",
  stockActiveTab: "summary",
  currentStock: null,
  pendingStockLabel: "",
  stockLoadRequestId: 0,
  suggestions: [],
  suggestionIndex: -1,
  suggestionTimer: null,
  suggestionController: null,
  activeTrendGraph: null,
  watchlistId: "",
  watchlistSyncTimer: null,
  watchlistSyncing: false,
  writeToken: "",
  writeTokenShareId: "",
  watchChartResults: [],
  selectedWatchChartCode: "",
  deferredInstallPrompt: null,
  marketRankingCache: new Map(),
  marketPrefetchKey: "",
  responseCache: new Map(),
  pendingRequests: new Map(),
  pageEntryRefreshAt: new Map(),
  viewFilters: {},
  currencyMode: localStorage.getItem(CURRENCY_MODE_KEY) === "KRW" ? "KRW" : "USD",
  usdKrwRate: DEFAULT_USDKRW_RATE,
  currencyLoading: false,
  currentDashboard: null,
  currentStockOverview: null,
  currentOverviewRows: null,
  currentOverviewDetail: null,
  watchlistRows: [],
  currentRecommendations: null,
  recommendationLoading: false,
  recommendationCooldownTimer: null,
  currentTrendPayload: null,
  currentTrendImpactPayload: null,
  currentMarketPayload: null,
  usSectorMoves: null,
  usSectorRefreshing: false,
  usSectorSocket: null,
  usSectorRefreshTimer: null,
  watchPreopenExpanded: new Set(),
  marketLeaderboardItems: [],
  marketQuoteSockets: new Map(),
  marketQuoteReconnectTimers: new Map(),
  recommendTrackRequestId: 0,
  quoteSocket: null,
  quoteSocketCode: "",
  quoteReconnectTimer: null,
  watchlistQuoteSockets: new Map(),
  watchlistQuoteReconnectTimers: new Map(),
  listQuoteSockets: new Map(),
  listQuoteReconnectTimers: new Map(),
  presenceSocket: null,
  presenceReconnectTimer: null,
  presencePageKey: "",
  presenceCount: null,
  presenceHundredsDigit: null,
  presenceHundredsHourKey: "",
  presenceHourTimer: null,
  loginGateTimer: null,
  loginSplashSeen: false,
  pullRefreshTracking: false,
  pullRefreshReady: false,
  pullRefreshRefreshing: false,
  pullRefreshDistance: 0,
  pullRefreshStartX: 0,
  pullRefreshStartY: 0,
  pullRefreshHideTimer: null,
  appSplashTimer: null,
  appSplashHideTimer: null,
  appSplashResolve: null,
};

const VIEW_NAV_SECTION = {
  stock: "stock",
  watchlist: "stock",
  recommend: "research",
  "recommend-history": "research",
  trend: "disclosure",
  "trend-past": "disclosure",
  "trend-impact": "disclosure",
  market: "news",
  chart: "stock",
  "chart-history": "stock",
};

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function showAppSplash(duration = APP_SPLASH_DURATION_MS) {
  if (!elements.appSplash) {
    return delay(duration);
  }
  if (state.appSplashResolve) {
    state.appSplashResolve();
    state.appSplashResolve = null;
  }
  window.clearTimeout(state.appSplashTimer);
  window.clearTimeout(state.appSplashHideTimer);
  elements.appSplash.hidden = false;
  window.requestAnimationFrame(() => {
    elements.appSplash?.classList.add("visible");
  });
  return new Promise((resolve) => {
    state.appSplashResolve = resolve;
    state.appSplashTimer = window.setTimeout(() => {
      elements.appSplash?.classList.remove("visible");
      state.appSplashHideTimer = window.setTimeout(() => {
        if (elements.appSplash) {
          elements.appSplash.hidden = true;
        }
        state.appSplashResolve = null;
        resolve();
      }, 340);
    }, duration);
  });
}

function rejectAfter(ms, message) {
  return new Promise((_, reject) => {
    setTimeout(() => reject(new Error(message)), ms);
  });
}

function pathQuery() {
  if (state.view !== "stock") {
    return "AAPL";
  }
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts[0] === "nasdaq" && parts[1]) {
    return decodeURIComponent(parts[1]);
  }
  return new URLSearchParams(window.location.search).get("query") || state.currentStock?.code || "AAPL";
}

function isStockOverviewQuery() {
  return false;
}

function hasExplicitStockPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts[0] === "nasdaq" && Boolean(parts[1]);
}

function isStockOverviewMode(view = state.view) {
  return false;
}

const DEFAULT_VIEW_FILTER = Object.freeze({
  keyword: "",
  startDate: "",
  endDate: "",
  category: "all",
  auxOne: "all",
  auxTwo: "all",
});

const SECTION_SHELL_TABS = {
  stock: [
    { view: "stock", label: "종목 검색" },
    { view: "watchlist", label: "관심 종목" },
    { view: "chart", label: "AI 차트 분석" },
    { view: "chart-history", label: "지난 AI 차트 스냅샷" },
  ],
  research: [
    { view: "recommend", label: "지금 추천 종목" },
    { view: "recommend-history", label: "추적 종목" },
  ],
  disclosure: [
    { view: "trend", label: "트랜드 분석" },
    { view: "trend-past", label: "지난 이벤트" },
    { view: "trend-impact", label: "시장 영향도 분석" },
  ],
  chart: [
    { view: "chart", label: "AI 차트 분석" },
    { view: "chart-history", label: "지난 AI 차트 스냅샷" },
  ],
};

function cloneDefaultViewFilter() {
  return { ...DEFAULT_VIEW_FILTER };
}

function getViewFilters(view = state.view) {
  if (!state.viewFilters[view]) {
    state.viewFilters[view] = cloneDefaultViewFilter();
  }
  return state.viewFilters[view];
}

function uniqueValues(values) {
  return Array.from(new Set((values || []).filter(Boolean))).sort((left, right) => String(left).localeCompare(String(right), "ko"));
}

function normalizeSearchText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/\s+/g, "")
    .trim();
}

function matchesKeyword(keyword, ...parts) {
  const needle = normalizeSearchText(keyword);
  if (!needle) {
    return true;
  }
  return parts.some((part) => normalizeSearchText(part).includes(needle));
}

function comparableDate(value) {
  if (!value) {
    return "";
  }
  if (typeof value === "string") {
    return value.slice(0, 10);
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toISOString().slice(0, 10);
}

function matchesDateRange(value, startDate, endDate) {
  const current = comparableDate(value);
  if (!current) {
    return !startDate && !endDate;
  }
  if (startDate && current < startDate) {
    return false;
  }
  if (endDate && current > endDate) {
    return false;
  }
  return true;
}

function populateSelect(select, options, selectedValue = "all") {
  if (!select) {
    return;
  }
  select.innerHTML = "";
  for (const [value, label] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (value === selectedValue) {
      option.selected = true;
    }
    select.appendChild(option);
  }
  if (![...select.options].some((option) => option.value === selectedValue) && select.options.length) {
    select.value = select.options[0].value;
  }
}

function toggleShellField(node, visible) {
  if (!node) {
    return;
  }
  node.hidden = !visible;
  node.disabled = !visible;
}

function shellMetaTextForView(view) {
  if (view === "stock" && isStockOverviewMode(view)) return stockOverviewMetaText();
  if (view === "watchlist") return elements.watchlistMeta.textContent || "저장된 종목";
  if (view === "recommend") return elements.recommendMeta.textContent || "추천 계산 전";
  if (view === "recommend-history") return elements.recommendHistoryMeta.textContent || "추적 종목 없음";
  if (view === "trend" || view === "trend-past" || view === "trend-impact") return elements.trendMeta.textContent || "최근 이벤트 기준";
  if (view === "chart") return elements.watchChartMeta.textContent || "관심종목 기준";
  if (view === "chart-history") return elements.watchChartSnapshotMeta.textContent || "저장 없음";
  if (view === "market") return elements.marketMeta.textContent || "미국 시장 랭킹";
  return "";
}

function shellTitleForView(view) {
  if (view === "stock") return "종목 검색";
  if (view === "watchlist") return "관심 종목";
  if (view === "recommend") return "지금 추천 종목";
  if (view === "recommend-history") return "추적 종목";
  if (view === "trend") return "트랜드 분석";
  if (view === "trend-past") return "지난 이벤트";
  if (view === "trend-impact") return "시장 영향도 분석";
  if (view === "chart") return "AI 차트 분석";
  if (view === "chart-history") return "지난 AI 차트 스냅샷";
  if (view === "market") return "급상승 종목";
  return "종목 검색";
}

function mobilePageTitleForView(view = state.view) {
  if (view === "stock" && state.currentStock?.name) {
    return state.currentStock.name;
  }
  if (view === "stock" && state.pendingStockLabel) {
    return state.pendingStockLabel;
  }
  return "";
}

function updateMobilePageTitle(view = state.view) {
  const title = mobilePageTitleForView(view);
  setText(elements.mobilePageTitle, title);
  if (elements.mobilePageTitle) {
    elements.mobilePageTitle.hidden = !title;
  }
}

function shellTabsForView(view) {
  const section = navSectionForView(view);
  return SECTION_SHELL_TABS[section] || [];
}

function sectionShellConfig(view = state.view) {
  const filters = getViewFilters(view);
  const trendEvents = [
    ...(state.currentTrendPayload?.events || []),
    ...(state.currentTrendPayload?.past_events || []),
  ];
  const trendCategoryOptions = [["all", "이벤트 구분"], ...uniqueValues(trendEvents.map((item) => item.category)).map((value) => [value, value])];
  const trendImportanceOptions = [["all", "중요도"], ...uniqueValues(trendEvents.map((item) => item.importance)).map((value) => [value, value])];

  const config = {
    title: shellTitleForView(view),
    meta: shellMetaTextForView(view),
    tabs: shellTabsForView(view),
    keywordPlaceholder: "종목명 또는 제목",
    showKeyword: true,
    showDates: false,
    categoryOptions: [["all", "전체"]],
    auxOneOptions: [],
    auxTwoOptions: [],
    primaryAction: null,
    secondaryAction: null,
  };

  if (view === "stock" && isStockOverviewMode(view)) {
    config.keywordPlaceholder = "기업명 또는 제목";
    config.categoryOptions = [["all", "전체"], ["reports", "리포트 포함"], ["disclosures", "공시 포함"], ["news", "뉴스 포함"]];
    config.auxOneOptions = [["all", "시장"], ["NASDAQ", "NASDAQ"], ["SP500", "S&P 500"]];
  } else if (view === "watchlist") {
    config.keywordPlaceholder = "종목명 또는 코드";
    config.categoryOptions = [["all", "전체"], ["positive", "상승"], ["negative", "하락"]];
    config.auxOneOptions = [["all", "시장"], ["NASDAQ", "NASDAQ"], ["SP500", "S&P 500"]];
  } else if (view === "recommend") {
    config.keywordPlaceholder = "종목명 또는 코드";
    config.categoryOptions = [["all", "추천결론"], ["buy", "매수"], ["hold", "관심"], ["review", "보류"]];
    config.auxOneOptions = [["all", "시장"], ["NASDAQ", "NASDAQ"], ["SP500", "S&P 500"]];
    config.primaryAction = { action: "recommend", label: "추천받기" };
    config.secondaryAction = { action: "recommend-history", label: "추적종목" };
  } else if (view === "recommend-history") {
    config.keywordPlaceholder = "추천 종목 또는 생성일";
    config.showDates = true;
    config.categoryOptions = [["all", "전체"]];
    config.primaryAction = { action: "recommend", label: "추천받기" };
  } else if (view === "trend" || view === "trend-past" || view === "trend-impact") {
    config.keywordPlaceholder = "이벤트명 또는 섹터";
    config.showDates = true;
    config.categoryOptions = trendImportanceOptions.length > 1 ? trendImportanceOptions : [["all", "중요도"]];
    config.auxOneOptions = trendCategoryOptions.length > 1 ? trendCategoryOptions : [["all", "이벤트 구분"]];
  } else if (view === "chart") {
    config.keywordPlaceholder = "종목명 또는 코드";
    config.categoryOptions = [["all", "판단"], ["strong", "강세"], ["neutral", "중립"], ["weak", "약세"]];
    config.auxOneOptions = [["all", "시장"], ["NASDAQ", "NASDAQ"], ["SP500", "S&P 500"]];
    config.secondaryAction = { action: "chart-history", label: "스냅샷" };
  } else if (view === "chart-history") {
    config.keywordPlaceholder = "종목명 또는 저장일";
    config.showDates = true;
    config.categoryOptions = [["all", "전체"]];
    config.primaryAction = { action: "chart", label: "AI 차트" };
  } else if (view === "market") {
    config.keywordPlaceholder = "종목명 또는 코드";
    config.categoryOptions = [
      ["surge", "급상승"],
      ["trading_value", "거래대금"],
      ["valuation", "밸류에이션"],
      ["momentum", "모멘텀"],
      ["sentiment", "뉴스 분위기"],
    ];
    config.auxOneOptions = [["ALL", "전체 미장"], ["NASDAQ", "NASDAQ"], ["SP500", "S&P 500"]];
  }

  if (!filters.category && config.categoryOptions.length) {
    filters.category = config.categoryOptions[0][0];
  }
  if (!filters.auxOne && config.auxOneOptions.length) {
    filters.auxOne = config.auxOneOptions[0][0];
  }
  if (!filters.auxTwo && config.auxTwoOptions.length) {
    filters.auxTwo = config.auxTwoOptions[0][0];
  }
  return config;
}

function setShellButton(button, actionConfig) {
  if (!button) {
    return;
  }
  if (!actionConfig) {
    button.hidden = true;
    button.dataset.action = "";
    button.textContent = "";
    return;
  }
  button.hidden = false;
  button.dataset.action = actionConfig.action;
  button.textContent = actionConfig.label;
}

function updateResponsiveModeBadges() {
  const label = window.innerWidth <= 980 ? "자동 감지 · 모바일" : "자동 감지 · PC";
  const sidebarBadge = document.querySelector(".side-footer-panel .count-badge");
  if (sidebarBadge) {
    sidebarBadge.textContent = label;
  }
  if (elements.sectionShellViewMode) {
    elements.sectionShellViewMode.textContent = label;
  }
}

function renderSectionShell() {
  if (!elements.sectionShellTopbar || !elements.sectionShellFilters) {
    return;
  }
  const visible = state.view !== "stock" || isStockOverviewMode();
  elements.sectionShellTopbar.hidden = !visible;
  elements.sectionShellFilters.hidden = !visible;
  for (const header of document.querySelectorAll(".section-view-topbar")) {
    header.hidden = true;
  }
  if (!visible) {
    return;
  }

  const config = sectionShellConfig(state.view);
  const filters = getViewFilters(state.view);
  elements.sectionShellTitle.textContent = config.title;
  elements.sectionShellMeta.textContent = config.meta || "최근 적재 기준";
  elements.sectionShellPrimaryTabs.hidden = true;
  elements.sectionShellPrimaryTabs.innerHTML = "";

  elements.sectionShellSecondaryTabs.innerHTML = "";
  const tabs = config.tabs || [];
  elements.sectionShellSecondaryTabs.hidden = tabs.length <= 1;
  for (const tab of tabs) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `secondary-section-tab${tab.view === state.view ? " active" : ""}`;
    button.dataset.shellView = tab.view;
    button.textContent = tab.label;
    elements.sectionShellSecondaryTabs.appendChild(button);
  }

  if (elements.sectionShellKeyword) {
    elements.sectionShellKeyword.placeholder = config.keywordPlaceholder || "종목명 또는 제목";
    elements.sectionShellKeyword.value = filters.keyword || "";
  }
  if (elements.sectionShellStartDate) {
    elements.sectionShellStartDate.value = filters.startDate || "";
  }
  if (elements.sectionShellEndDate) {
    elements.sectionShellEndDate.value = filters.endDate || "";
  }

  toggleShellField(elements.sectionShellStartDate, config.showDates);
  toggleShellField(elements.sectionShellEndDate, config.showDates);
  if (elements.sectionShellDateDivider) {
    elements.sectionShellDateDivider.hidden = !config.showDates;
  }

  populateSelect(elements.sectionShellCategory, config.categoryOptions, filters.category || config.categoryOptions?.[0]?.[0] || "all");
  populateSelect(elements.sectionShellAuxOne, config.auxOneOptions, filters.auxOne || config.auxOneOptions?.[0]?.[0] || "all");
  populateSelect(elements.sectionShellAuxTwo, config.auxTwoOptions, filters.auxTwo || config.auxTwoOptions?.[0]?.[0] || "all");

  toggleShellField(elements.sectionShellCategory, (config.categoryOptions || []).length > 0);
  toggleShellField(elements.sectionShellAuxOne, (config.auxOneOptions || []).length > 0);
  toggleShellField(elements.sectionShellAuxTwo, (config.auxTwoOptions || []).length > 0);

  setShellButton(elements.sectionShellPrimaryAction, config.primaryAction);
  setShellButton(elements.sectionShellSecondaryAction, config.secondaryAction);
  updateResponsiveModeBadges();
}

function syncSectionShellMeta() {
  if (state.view === "stock" || !elements.sectionShellTopbar || elements.sectionShellTopbar.hidden) {
    return;
  }
  elements.sectionShellTitle.textContent = shellTitleForView(state.view);
  elements.sectionShellMeta.textContent = shellMetaTextForView(state.view) || "최근 적재 기준";
}

function stockOverviewMetaText(payload = state.currentStockOverview) {
  if (!payload) {
    return "미국 대표 종목 검색 준비 중";
  }
  return payload.meta || "미국 대표 종목 검색";
}

function overviewTargetView(target) {
  if (target === "research") return "recommend";
  if (target === "disclosure") return "trend";
  if (target === "news") return "market";
  if (target === "watchlist" || target === "holdings") return "watchlist";
  if (target === "indices" || target === "all-companies") return "market";
  return "stock";
}

function stockOverviewSymbols(recommendations, rankings) {
  const symbols = [];
  const seen = new Set();
  const append = (code) => {
    const normalized = String(code || "").trim().toUpperCase();
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    symbols.push(normalized);
  };
  for (const item of readWatchlist()) append(item.code);
  for (const item of recommendations?.items || []) append(item.code);
  for (const item of rankings?.items || []) append(item.code);
  for (const code of ["AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META"]) append(code);
  return symbols.slice(0, STOCK_OVERVIEW_SYMBOL_LIMIT);
}

function stockOverviewRowMatches(row, filters) {
  if (!row) {
    return false;
  }
  const keywordMatch = matchesKeyword(filters.keyword, row.name, row.code, row.market, row.title, row.summary, row.source, row.meta);
  const marketMatch = filters.auxOne === "all" || row.market === filters.auxOne;
  return keywordMatch && marketMatch;
}

function stockOverviewRows(payload, section, filters) {
  const rows = (payload?.sections?.[section] || []).filter((row) => stockOverviewRowMatches(row, filters));
  if (filters.category === "reports" && section !== "reports") return [];
  if (filters.category === "disclosures" && section !== "disclosures") return [];
  if (filters.category === "news" && section !== "news") return [];
  return rows;
}

function createOverviewWatchButton(code, name, market = "") {
  const button = el("button", `overview-star${isWatched(code) ? " active" : ""}`, "★");
  button.type = "button";
  button.dataset.overviewWatch = code || "";
  button.dataset.name = name || "";
  button.dataset.market = market || "";
  button.title = isWatched(code) ? "관심 해제" : "관심 추가";
  return button;
}

function createOverviewRow(row, section, index) {
  const article = el("article", "overview-feed-row");
  article.appendChild(createOverviewWatchButton(row.code, row.name, row.market));
  const button = el("button", "overview-row-button");
  button.type = "button";
  button.dataset.overviewDetailSection = section;
  button.dataset.overviewDetailIndex = String(index);

  const company = el("div", "overview-row-company");
  company.append(
    el("strong", "", row.name || row.code || "-"),
    el("span", "", `${row.code || "-"} · ${row.market || "-"}`),
  );

  const price = el("div", "overview-row-price");
  price.append(
    el("strong", "", row.price !== null && row.price !== undefined ? formatPrice(row.price) : "-"),
    el("span", "", row.change_rate !== null && row.change_rate !== undefined ? formatPercent(row.change_rate) : (row.published_at ? formatDate(row.published_at) : "-")),
  );

  const copy = el("div", "overview-row-copy");
  copy.append(
    el("span", "", row.meta || row.source || "-"),
    el("strong", "", row.title || "-"),
  );

  button.append(company, price, copy);
  if (section === "news" && row.sentiment_label) {
    button.append(el("span", row.sentiment === "positive" ? "positive" : row.sentiment === "negative" ? "negative" : "muted", row.sentiment_label));
  }
  article.appendChild(button);
  return article;
}

function createOverviewSection(title, rows, target, emptyText, sectionKey = target) {
  const section = el("section", "overview-section");
  const head = el("button", "overview-section-head");
  head.type = "button";
  head.dataset.overviewTarget = target;
  head.append(
    el("strong", "", title),
    el("span", "", `전체 ${formatNumber(rows.length)}건`),
    el("span", "", "›"),
  );
  const list = el("div", "overview-feed-list");
  if (!rows.length) {
    list.appendChild(el("div", "overview-empty", emptyText));
  } else {
    rows.slice(0, STOCK_OVERVIEW_SECTION_LIMIT).forEach((row, index) => list.appendChild(createOverviewRow(row, sectionKey, index)));
  }
  section.append(head, list);
  return section;
}

function createOverviewPortfolioBlock(rows) {
  const section = el("section", "overview-section overview-portfolio-block");
  const head = el("button", "overview-section-head");
  head.type = "button";
  head.dataset.overviewTarget = "watchlist";
  head.append(
    el("strong", "", "포트폴리오"),
    el("span", "", rows.length ? "브로커 연결 보류" : "아카이빙"),
    el("span", "", "›"),
  );
  const list = el("div", "overview-feed-list");
  if (!rows.length) {
    list.appendChild(el("div", "overview-empty", "브로커 연동은 아카이빙되어 있습니다."));
  } else {
    rows.slice(0, STOCK_OVERVIEW_SECTION_LIMIT).forEach((row, index) => list.appendChild(createOverviewRow(row, "portfolio", index)));
  }
  section.append(head, list);
  return section;
}

function createOverviewUpdateCards(payload, rowsBySection) {
  const wrap = el("div", "overview-update-grid");
  const cards = [
    ["research", "증권사리포트", rowsBySection.reports.length],
    ["disclosure", "공시·IR", rowsBySection.disclosures.length],
    ["news", "뉴스", rowsBySection.news.length],
  ];
  for (const [target, label, count] of cards) {
    const button = el("button", "overview-update-card");
    button.type = "button";
    button.dataset.overviewTarget = target;
    const strong = document.createElement("strong");
    strong.innerHTML = `${formatNumber(count)}<small>건</small>`;
    button.append(el("span", "", label), strong);
    wrap.appendChild(button);
  }
  return wrap;
}

function createOverviewGuideList() {
  const items = [
    ["리포트 읽기", "목표가와 의견 변화로 기대를 확인합니다."],
    ["SEC filing 보기", "10-K, 8-K, Form 4 같은 서류 흐름을 봅니다."],
    ["뉴스 묶어보기", "종목별 최근 기사와 긍부정 흐름을 확인합니다."],
    ["관심기업 설정", "별표로 관심 종목을 저장하고 추적합니다."],
  ];
  const section = el("section", "overview-section");
  const head = el("button", "overview-section-head");
  head.type = "button";
  head.dataset.overviewTarget = "help";
  head.append(el("strong", "", "사용법"), el("span", "", "핵심 흐름"), el("span", "", "›"));
  const list = el("div", "overview-guide-list");
  for (const [title, copy] of items) {
    const button = el("button", "overview-guide-row");
    button.type = "button";
    button.dataset.overviewTarget = "help";
    button.append(el("strong", "", title), el("span", "", copy));
    list.appendChild(button);
  }
  section.append(head, list);
  return section;
}

function createOverviewIndexBlock(items) {
  const section = el("section", "overview-section");
  const head = el("button", "overview-section-head");
  head.type = "button";
  head.dataset.overviewTarget = "indices";
  head.append(el("strong", "", "주요 지수"), el("span", "", "시세 60초"), el("span", "", "›"));
  const list = el("div", "overview-feed-list");
  if (!items.length) {
    list.appendChild(el("div", "overview-empty", "지수 데이터를 불러오는 중입니다."));
  } else {
    for (const item of items.slice(0, 5)) {
      const button = el("button", "overview-index-row");
      button.type = "button";
      button.dataset.overviewTarget = "indices";
      const price = el("span", "", formatPrice(item.price));
      const change = el("em", "", formatPercent(item.change_rate));
      setTone(change, item.change_rate);
      button.append(el("strong", "", item.label || item.symbol || "-"), price, change);
      list.appendChild(button);
    }
  }
  section.append(head, list);
  return section;
}

function createOverviewRightRail(payload) {
  const aside = el("aside", "overview-side-panel");
  const account = el("div", "overview-account-card");
  const cta = el("button", "overview-cta", "관심기업 보기");
  cta.type = "button";
  cta.dataset.overviewTarget = "watchlist";
  account.append(
    el("strong", "", "자산 관리"),
    el("span", "", "브로커 연동은 아카이빙되어 있습니다."),
    cta,
  );

  const tabs = el("div", "overview-side-tabs");
  const counters = [
    ["holdings", payload.holdingCount || 0, "보유기업"],
    ["watchlist", payload.watchCount || 0, "관심기업"],
    ["all-companies", payload.universeCount || 0, "전체기업"],
    ["indices", (payload.indices || []).length, "주요지수"],
  ];
  for (const [target, count, label] of counters) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.overviewTarget = target;
    button.append(el("strong", "", formatNumber(count)), el("span", "", label));
    tabs.appendChild(button);
  }
  aside.append(account, tabs);
  return aside;
}

function buildStockOverviewPayload(recommendations, rankings, indices, dashboards) {
  const dashboardRows = dashboards.filter((item) => item?.dashboard).map((item) => item.dashboard);
  const reports = dashboardRows
    .filter((dashboard) => dashboard.revisions?.latest_report_at)
    .map((dashboard) => ({
      code: dashboard.code,
      name: dashboard.name,
      market: dashboard.market,
      price: dashboard.quote?.price,
      change_value: dashboard.quote?.change_value,
      change_rate: dashboard.quote?.change_rate,
      published_at: dashboard.revisions?.latest_report_at,
      title: `${dashboard.revisions?.latest_opinion || "-"} · 목표 ${formatPrice(dashboard.revisions?.latest_target_price)}`,
      summary: dashboard.revisions?.source || "",
      source: dashboard.revisions?.source || "Yahoo Finance",
      url: null,
      meta: `${dashboard.revisions?.report_count_90d || 0}건 · ${formatDate(dashboard.revisions?.latest_report_at)}`,
    }))
    .sort((left, right) => String(right.published_at || "").localeCompare(String(left.published_at || "")));

  const disclosures = dashboardRows
    .flatMap((dashboard) =>
      (dashboard.guidance?.latest_events || []).map((item) => ({
        code: dashboard.code,
        name: dashboard.name,
        market: dashboard.market,
        price: dashboard.quote?.price,
        change_value: dashboard.quote?.change_value,
        change_rate: dashboard.quote?.change_rate,
        published_at: item.published_at,
        title: item.title,
        summary: item.form || "SEC filing",
        source: item.source || "SEC EDGAR",
        url: item.url || null,
        meta: `${item.form || "SEC"} · ${formatDate(item.published_at)}`,
      }))
    )
    .sort((left, right) => String(right.published_at || "").localeCompare(String(left.published_at || "")));

  const news = dashboardRows
    .flatMap((dashboard) =>
      (dashboard.sentiment?.latest_items || []).map((item) => ({
        code: dashboard.code,
        name: dashboard.name,
        market: dashboard.market,
        price: dashboard.quote?.price,
        change_value: dashboard.quote?.change_value,
        change_rate: dashboard.quote?.change_rate,
        published_at: item.published_at,
        title: item.title,
        summary: item.sentiment_reason || "",
        source: item.source || "News",
        url: item.url || null,
        meta: `${item.source || "News"} · ${formatDate(item.published_at)}`,
        sentiment: item.sentiment,
        sentiment_label: item.sentiment_label,
      }))
    )
    .sort((left, right) => String(right.published_at || "").localeCompare(String(left.published_at || "")));

  const watchCodes = new Set(readWatchlist().map((item) => item.code));
  const portfolio = dashboardRows
    .filter((dashboard) => watchCodes.has(dashboard.code))
    .map((dashboard) => {
      const latestReportAt = dashboard.revisions?.latest_report_at || "";
      const latestDisclosureAt = dashboard.guidance?.latest_events?.[0]?.published_at || "";
      const latestNewsAt = dashboard.sentiment?.latest_items?.[0]?.published_at || "";
      const latestTimestamp = [latestReportAt, latestDisclosureAt, latestNewsAt].filter(Boolean).sort().reverse()[0] || null;
      const latestNews = dashboard.sentiment?.latest_items?.[0] || null;
      return {
        code: dashboard.code,
        name: dashboard.name,
        market: dashboard.market,
        price: dashboard.quote?.price,
        change_value: dashboard.quote?.change_value,
        change_rate: dashboard.quote?.change_rate,
        published_at: latestTimestamp,
        title: latestNews?.title || `${dashboard.revisions?.latest_opinion || "브리핑"} · 목표 ${formatPrice(dashboard.revisions?.latest_target_price)}`,
        summary: latestNews?.sentiment_reason || "",
        source: "관심 종목",
        url: latestNews?.url || null,
        meta: latestTimestamp ? `최근 갱신 · ${formatDate(latestTimestamp)}` : "최근 연결 신호 없음",
      };
    })
    .sort((left, right) => String(right.published_at || "").localeCompare(String(left.published_at || "")));
  const watchRows = news.filter((item) => watchCodes.has(item.code));
  return {
    as_of: new Date().toISOString(),
    meta: `${formatNumber(recommendations?.universe_count || 0)}종목 · ${formatDate(recommendations?.as_of || rankings?.as_of || new Date().toISOString())} · 자동갱신`,
    universeCount: recommendations?.universe_count || rankings?.items?.length || 0,
    watchCount: watchCodes.size,
    holdingCount: 0,
    indices: indices?.items || [],
    dashboardsByCode: Object.fromEntries(dashboardRows.map((dashboard) => [dashboard.code, dashboard])),
    sections: {
      portfolio,
      reports,
      disclosures,
      news,
      watchlistNews: watchRows,
    },
  };
}

function overviewSectionRows(section) {
  return state.currentOverviewRows?.[section] || [];
}

function overviewDetailPayload() {
  const detail = state.currentOverviewDetail;
  if (!detail) {
    return null;
  }
  const rows = overviewSectionRows(detail.section);
  const row = rows[detail.index];
  if (!row) {
    return null;
  }
  const dashboard = state.currentStockOverview?.dashboardsByCode?.[row.code] || null;
  const quote = dashboard?.quote || {};
  const targetPrice = toNumber(dashboard?.revisions?.latest_target_price);
  const currentPrice = toNumber(quote.price ?? row.price);
  const returnRate =
    targetPrice !== null && currentPrice !== null && currentPrice !== 0
      ? ((targetPrice - currentPrice) / currentPrice) * 100
      : null;
  return {
    ...detail,
    row,
    rows,
    dashboard,
    targetPrice,
    currentPrice,
    returnRate,
  };
}

function overviewDetailMetric(label, value) {
  return `
    <div class="detail-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function overviewDetailSignalCount(dashboard) {
  return {
    reports: dashboard?.revisions?.report_count_90d || 0,
    disclosures: dashboard?.guidance?.latest_events?.length || 0,
    news: dashboard?.sentiment?.latest_items?.length || 0,
  };
}

function overviewDetailBullets(payload) {
  const { section, row, dashboard, returnRate, targetPrice } = payload;
  const signalCount = overviewDetailSignalCount(dashboard);
  if (section === "reports") {
    return [
      ["투자 의견 및 목표주가", `${dashboard?.revisions?.latest_opinion || "의견 없음"} · 목표주가 ${targetPrice !== null ? formatPrice(targetPrice) : "미제시"}${returnRate !== null ? ` · 기대수익률 ${formatPercent(returnRate)}` : ""}`],
      ["최근 연결 신호", `리포트 ${formatNumber(signalCount.reports)}건 · 공시 ${formatNumber(signalCount.disclosures)}건 · 뉴스 ${formatNumber(signalCount.news)}건`],
      ["리포트 핵심", row.title || "제목 없음"],
    ];
  }
  if (section === "disclosures") {
    return [
      ["공시/이벤트", `${row.summary || row.source || "이벤트"} · ${formatDate(row.published_at)}`],
      ["최근 연결 신호", `리포트 ${formatNumber(signalCount.reports)}건 · 공시 ${formatNumber(signalCount.disclosures)}건 · 뉴스 ${formatNumber(signalCount.news)}건`],
      ["이벤트 핵심", row.title || "이벤트 없음"],
    ];
  }
  if (section === "news" || section === "watchlistNews") {
    return [
      ["뉴스 판단", `${row.sentiment_label || "중립"} · ${row.source || "뉴스"} · ${formatDate(row.published_at)}`],
      ["최근 연결 신호", `리포트 ${formatNumber(signalCount.reports)}건 · 공시 ${formatNumber(signalCount.disclosures)}건 · 뉴스 ${formatNumber(signalCount.news)}건`],
      ["뉴스 핵심", row.title || "기사 없음"],
    ];
  }
  return [
    ["관심기업 브리핑", `${row.source || "관심 종목"} · ${formatDate(row.published_at)}`],
    ["최근 연결 신호", `리포트 ${formatNumber(signalCount.reports)}건 · 공시 ${formatNumber(signalCount.disclosures)}건 · 뉴스 ${formatNumber(signalCount.news)}건`],
    ["핵심 내용", row.title || "연결된 최신 내용이 없습니다."],
  ];
}

function overviewDetailChart(payload) {
  const status = payload.priceHistoryStatus || "loading";
  const prices = (payload.priceHistory || [])
    .map((item) => ({
      date: item.trade_date || item.date,
      time: new Date(item.trade_date || item.date || "").getTime(),
      close: toNumber(item.close),
    }))
    .filter((item) => item.date && Number.isFinite(item.time) && item.close !== null)
    .sort((left, right) => left.time - right.time)
    .slice(-90);

  if (status === "loading") {
    return `
      <div class="detail-chart detail-chart-empty">
        <strong>실제 차트 데이터 불러오는 중</strong>
        <span>최근 종가와 현재 목표주가 기준선을 연결하고 있습니다.</span>
      </div>
    `;
  }

  if (prices.length < 2) {
    return `
      <div class="detail-chart detail-chart-empty">
        <strong>차트 데이터 부족</strong>
        <span>최근 종가 이력이 충분하지 않아 상세 차트를 그리지 못했습니다.</span>
      </div>
    `;
  }

  const values = prices.map((item) => item.close);
  const targetPrice = payload.targetPrice;
  if (targetPrice !== null) {
    values.push(targetPrice);
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const minTime = prices[0].time;
  const maxTime = prices[prices.length - 1].time;
  const width = 520;
  const height = 300;
  const pad = { top: 42, right: 28, bottom: 48, left: 52 };
  const timeSpan = maxTime === minTime ? 1 : maxTime - minTime;
  const valueSpan = maxValue === minValue ? 1 : maxValue - minValue;
  const xFor = (time) => pad.left + ((time - minTime) / timeSpan) * (width - pad.left - pad.right);
  const yFor = (value) => height - pad.bottom - ((value - minValue) / valueSpan) * (height - pad.top - pad.bottom);
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = minValue + valueSpan * ratio;
    const y = yFor(value);
    return { value, y };
  });
  const closePoints = prices.map((item) => `${xFor(item.time).toFixed(1)},${yFor(item.close).toFixed(1)}`).join(" ");
  const targetY = targetPrice !== null ? yFor(targetPrice).toFixed(1) : null;
  const latest = prices[prices.length - 1];
  return `
    <div class="detail-chart detail-chart-real">
      <div class="detail-chart-title">목표주가 / 종가 추이</div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="현재 목표주가와 종가 추이">
        ${yTicks
          .map(
            (tick) => `
              <line class="chart-grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${tick.y.toFixed(1)}" y2="${tick.y.toFixed(1)}"></line>
              <text class="chart-axis-label" x="${pad.left - 8}" y="${(tick.y + 4).toFixed(1)}">${escapeHtml(formatNumber(Math.round(tick.value)))}</text>
            `
          )
          .join("")}
        <polyline class="chart-close-line" points="${escapeHtml(closePoints)}"></polyline>
        ${
          targetY
            ? `
              <line class="chart-target-line" x1="${pad.left}" x2="${width - pad.right}" y1="${targetY}" y2="${targetY}"></line>
              <circle class="chart-target-dot" cx="${xFor(latest.time).toFixed(1)}" cy="${targetY}" r="4"></circle>
            `
            : ""
        }
      </svg>
      <div class="detail-chart-legend">
        <span><i class="legend-accent"></i>${escapeHtml(targetPrice !== null ? "현재 목표주가" : "목표주가 없음")}</span>
        <span><i class="legend-muted"></i>종가 ${escapeHtml(formatNumber(prices.length))}개</span>
      </div>
    </div>
  `;
}

function overviewDetailModal(payload) {
  const { row, dashboard, returnRate, targetPrice, currentPrice, rows, section, index } = payload;
  const signalCount = overviewDetailSignalCount(dashboard);
  const companyName = row.name || row.code || "종목";
  const changeValue = toNumber(dashboard?.quote?.change_value ?? row.change_value);
  const changeRate = toNumber(dashboard?.quote?.change_rate ?? row.change_rate);
  const toneClass = !Number.isFinite(changeValue) || changeValue === 0 ? "muted" : changeValue > 0 ? "positive" : "negative";
  const changeText =
    Number.isFinite(changeValue) && Number.isFinite(changeRate)
      ? `${formatPriceChange(changeValue)} · ${formatPercent(changeRate)}`
      : "시세 대기";
  const bullets = overviewDetailBullets(payload)
    .map(
      ([title, body]) => `
        <div class="detail-bullet">
          <strong>${escapeHtml(title)}</strong>
          <p>${escapeHtml(body)}</p>
        </div>
      `
    )
    .join("");
  const title = row.title || companyName;
  const sourceLabel = row.source || dashboard?.revisions?.source || "비밀노트 미국증시";
  const sourceUrl = row.url || viewStockUrl({ code: row.code || "AAPL" });
  const sourceCta = row.url ? "원문 보기" : "종목 보기";
  return `
    <div class="detail-backdrop" data-overview-detail-close="true">
      <section class="detail-modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(companyName)} 상세">
        <header class="detail-head">
          <div>
            <strong>${escapeHtml(companyName)}</strong>
            <span class="${escapeHtml(toneClass)}">${escapeHtml(formatPrice(currentPrice ?? row.price))} · ${escapeHtml(changeText)}</span>
          </div>
          <div class="detail-actions">
            <button
              class="overview-star ${isWatched(row.code) ? "active" : ""}"
              data-overview-watch="${escapeHtml(row.code || "")}"
              data-name="${escapeHtml(companyName)}"
              data-market="${escapeHtml(row.market || "")}"
              type="button"
              aria-pressed="${isWatched(row.code) ? "true" : "false"}"
              title="${isWatched(row.code) ? "관심 해제" : "관심 추가"}"
            >★</button>
            <button class="detail-close" data-overview-detail-close="true" type="button" aria-label="닫기">×</button>
          </div>
        </header>
        <div class="detail-metric-strip">
          ${overviewDetailMetric("종목코드", row.code || "-")}
          ${overviewDetailMetric("시장", row.market || "-")}
          ${overviewDetailMetric("투자의견", dashboard?.revisions?.latest_opinion || row.sentiment_label || "-")}
          ${overviewDetailMetric("기대수익률", returnRate !== null ? formatPercent(returnRate) : "-")}
          ${overviewDetailMetric("작성일", formatDateOnly(row.published_at))}
        </div>
        <div class="detail-title-row">
          <h2>${escapeHtml(title)}</h2>
          <span>${escapeHtml(sourceLabel)}</span>
        </div>
        <div class="detail-body-grid">
          ${overviewDetailChart(payload)}
          <aside class="detail-side">
            ${overviewDetailMetric("목표주가", targetPrice !== null ? formatPrice(targetPrice) : "-")}
            ${overviewDetailMetric("현재가", formatPrice(currentPrice ?? row.price))}
            ${overviewDetailMetric("브리핑 갱신", row.published_at ? formatDate(row.published_at) : "-")}
            <a class="detail-source-link" href="${escapeHtml(sourceUrl)}" ${row.url ? 'target="_blank" rel="noreferrer"' : ""}>${escapeHtml(sourceCta)}</a>
          </aside>
        </div>
        <div class="detail-summary">${bullets}</div>
        <footer class="detail-nav">
          <button data-overview-detail-nav="${escapeHtml(section)}:${index - 1}" ${index > 0 ? "" : "disabled"} type="button">‹ 이전</button>
          <button data-overview-detail-nav="${escapeHtml(section)}:${index + 1}" ${index < rows.length - 1 ? "" : "disabled"} type="button">다음 ›</button>
        </footer>
      </section>
    </div>
  `;
}

function renderOverviewDetailModal() {
  let root = document.getElementById("detail-modal-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "detail-modal-root";
    document.body.appendChild(root);
  }
  const payload = overviewDetailPayload();
  if (!payload) {
    root.innerHTML = "";
    return;
  }
  root.innerHTML = overviewDetailModal(payload);
}

async function openOverviewDetail(section, index) {
  const rows = overviewSectionRows(section);
  const targetRow = rows[index];
  if (!targetRow) {
    return;
  }
  state.currentOverviewDetail = {
    section,
    index,
    priceHistoryStatus: "loading",
    priceHistory: [],
  };
  renderOverviewDetailModal();
  if (!targetRow.code) {
    state.currentOverviewDetail.priceHistoryStatus = "error";
    renderOverviewDetailModal();
    return;
  }
  try {
    const prices = await fetchJsonCached(`/us/stocks/${encodeURIComponent(targetRow.code)}/prices?limit=180`, { ttlMs: UI_CACHE_TTL_MS });
    if (state.currentOverviewDetail && state.currentOverviewDetail.section === section && state.currentOverviewDetail.index === index) {
      state.currentOverviewDetail = {
        ...state.currentOverviewDetail,
        priceHistoryStatus: "ready",
        priceHistory: prices,
      };
      renderOverviewDetailModal();
    }
  } catch {
    if (state.currentOverviewDetail && state.currentOverviewDetail.section === section && state.currentOverviewDetail.index === index) {
      state.currentOverviewDetail = {
        ...state.currentOverviewDetail,
        priceHistoryStatus: "error",
        priceHistory: [],
      };
      renderOverviewDetailModal();
    }
  }
}

function closeOverviewDetail() {
  state.currentOverviewDetail = null;
  renderOverviewDetailModal();
}

function renderStockOverview(payload) {
  state.currentStockOverview = payload;
  if (!elements.stockOverviewView) {
    return;
  }
  const filters = getViewFilters("stock");
  const portfolioRows = stockOverviewRows(payload, "portfolio", filters);
  const reportRows = stockOverviewRows(payload, "reports", filters);
  const disclosureRows = stockOverviewRows(payload, "disclosures", filters);
  const newsRows = stockOverviewRows(payload, "news", filters);
  const watchRows = (payload.sections.watchlistNews || []).filter((row) => stockOverviewRowMatches(row, filters));
  state.currentOverviewRows = {
    portfolio: portfolioRows,
    reports: reportRows,
    disclosures: disclosureRows,
    news: newsRows,
    watchlistNews: watchRows,
  };
  const shell = el("div", "butler-overview-shell");
  const main = el("main", "overview-main-card");

  const update = el("section", "overview-update-section");
  update.append(el("h2", "", "오늘의 업데이트"), createOverviewUpdateCards(payload, { reports: reportRows, disclosures: disclosureRows, news: newsRows }));
  main.appendChild(update);

  main.appendChild(createOverviewSection("지금 많이 보는 리포트", reportRows, "research", "표시할 리포트가 없습니다.", "reports"));
  main.appendChild(createOverviewSection("주요 공시", disclosureRows, "disclosure", "표시할 공시가 없습니다.", "disclosures"));
  main.appendChild(createOverviewSection("최신 뉴스", newsRows, "news", "표시할 뉴스가 없습니다.", "news"));
  main.appendChild(createOverviewPortfolioBlock(portfolioRows));
  main.appendChild(createOverviewSection("관심기업 주요소식", watchRows, "watchlist", "관심기업 데이터가 없습니다.", "watchlistNews"));
  main.appendChild(createOverviewGuideList());
  main.appendChild(createOverviewIndexBlock(payload.indices || []));

  shell.append(main, createOverviewRightRail(payload));
  elements.stockOverviewView.innerHTML = "";
  elements.stockOverviewView.appendChild(shell);
  if (elements.sectionShellMeta) {
    elements.sectionShellMeta.textContent = stockOverviewMetaText(payload);
  }
  renderSectionShell();
  renderOverviewDetailModal();
}

async function loadStockOverview(options = {}) {
  if (!elements.stockOverviewView) {
    return;
  }
  const force = options.force === true;
  elements.stockOverviewView.innerHTML = '<div class="overview-empty">미국 대표 종목 검색 화면을 준비하는 중입니다.</div>';
  try {
    const [recommendations, rankings, indices] = await Promise.all([
      fetchJsonCached(
        force ? liveUrl(`/us/market/recommendations?limit=${RECOMMENDATION_LIMIT}&candidate_limit=80&refresh=1`) : `/us/market/recommendations?limit=${RECOMMENDATION_LIMIT}&candidate_limit=80`,
        { force, ttlMs: force ? 0 : UI_CACHE_TTL_MS },
      ),
      fetchJsonCached(
        force ? liveUrl("/us/market/rankings?category=surge&market=ALL&limit=10") : "/us/market/rankings?category=surge&market=ALL&limit=10",
        { force, ttlMs: force ? 0 : UI_CACHE_TTL_MS },
      ),
      fetchJsonCached(
        force ? liveUrl("/market/us-sector-moves?refresh=1") : "/market/us-sector-moves",
        { force, ttlMs: force ? 0 : UI_CACHE_TTL_MS },
      ),
    ]);
    const symbols = stockOverviewSymbols(recommendations, rankings);
    const dashboards = await mapWithConcurrency(
      symbols,
      5,
      async (code) => {
        try {
          const url = `/us/stocks/${encodeURIComponent(code)}/dashboard?refresh=1`;
          const dashboard = await fetchJsonCached(force ? liveUrl(url) : url, { force, ttlMs: force ? 0 : UI_CACHE_TTL_MS });
          return { code, dashboard };
        } catch {
          return { code, dashboard: null };
        }
      },
    );
    renderStockOverview(buildStockOverviewPayload(recommendations, rankings, indices, dashboards));
  } catch {
    elements.stockOverviewView.innerHTML = '<div class="overview-empty">종목 검색 데이터를 불러오지 못했습니다.</div>';
  }
}

function applySectionShellFilters() {
  if (state.view === "stock") {
    return;
  }
  const filters = getViewFilters(state.view);
  filters.keyword = elements.sectionShellKeyword?.value?.trim() || "";
  filters.startDate = elements.sectionShellStartDate?.value || "";
  filters.endDate = elements.sectionShellEndDate?.value || "";
  filters.category = elements.sectionShellCategory?.hidden ? "all" : (elements.sectionShellCategory?.value || "all");
  filters.auxOne = elements.sectionShellAuxOne?.hidden ? "all" : (elements.sectionShellAuxOne?.value || "all");
  filters.auxTwo = elements.sectionShellAuxTwo?.hidden ? "all" : (elements.sectionShellAuxTwo?.value || "all");

  if (state.view === "market") {
    state.rankingCategory = filters.category || "surge";
    elements.rankCategorySelect.value = state.rankingCategory;
    elements.marketFilter.value = filters.auxOne || "ALL";
    loadMarketRankings({ category: state.rankingCategory, market: currentMarketFilter() });
    return;
  }

  rerenderCurrentView();
}

function resetSectionShellFilters() {
  state.viewFilters[state.view] = cloneDefaultViewFilter();
  if (state.view === "market") {
    state.viewFilters[state.view].category = state.rankingCategory || "surge";
    state.viewFilters[state.view].auxOne = currentMarketFilter();
  }
  renderSectionShell();
  applySectionShellFilters();
}

function runSectionShellAction(action) {
  if (action === "recommend") {
    if (state.view !== "recommend") {
      setView("recommend");
    }
    loadRecommendations();
    return;
  }
  if (action === "recommend-history") {
    setView("recommend-history");
    return;
  }
  if (action === "chart") {
    setView("chart");
    return;
  }
  if (action === "chart-history") {
    setView("chart-history");
  }
}

function refreshCurrentShellView() {
  if (state.view === "stock") {
    if (isStockOverviewMode()) {
      loadStockOverview({ force: true });
    } else {
      load(state.currentStock?.code || pathQuery());
    }
    return;
  }
  if (state.view === "watchlist") {
    loadWatchlist();
    return;
  }
  if (state.view === "recommend") {
    loadRecommendations();
    return;
  }
  if (state.view === "recommend-history") {
    renderRecommendationHistory();
    return;
  }
  if (state.view === "trend") {
    loadTrends("events");
    return;
  }
  if (state.view === "trend-past") {
    loadTrends("past");
    return;
  }
  if (state.view === "trend-impact") {
    loadMarketImpactAnalysis({ force: true });
    return;
  }
  if (state.view === "chart") {
    loadWatchCharts();
    return;
  }
  if (state.view === "chart-history") {
    renderChartSnapshots();
    return;
  }
  if (state.view === "market") {
    loadMarketRankings({ category: state.rankingCategory, market: currentMarketFilter() });
  }
}

function rerenderCurrentView() {
  if (state.view === "stock" && isStockOverviewMode() && state.currentStockOverview) {
    renderStockOverview(state.currentStockOverview);
    return;
  }
  if (state.view === "watchlist") {
    renderWatchlistTable(state.watchlistRows);
    return;
  }
  if (state.view === "recommend" && state.currentRecommendations) {
    renderRecommendations(state.currentRecommendations, { save: false });
    return;
  }
  if (state.view === "recommend-history") {
    renderRecommendationHistory();
    return;
  }
  if ((state.view === "trend" || state.view === "trend-past") && state.currentTrendPayload) {
    renderTrends(state.currentTrendPayload, state.view === "trend-past" ? "past" : "events");
    return;
  }
  if (state.view === "trend-impact" && state.currentTrendImpactPayload) {
    renderMarketImpactAnalysis(state.currentTrendImpactPayload);
    return;
  }
  if (state.view === "chart") {
    renderWatchChartList(state.watchChartResults);
    return;
  }
  if (state.view === "chart-history") {
    renderChartSnapshots();
    return;
  }
  if (state.view === "market" && state.currentMarketPayload) {
    renderRankings(state.currentMarketPayload);
  }
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return Number(value).toLocaleString("ko-KR");
}

function setText(node, text) {
  if (node) {
    node.textContent = text;
  }
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function clampNumber(value, min, max) {
  const number = toNumber(value);
  if (number === null) {
    return min;
  }
  return Math.min(max, Math.max(min, number));
}

function roundTradePrice(value) {
  const price = toNumber(value);
  if (price === null) {
    return null;
  }
  const abs = Math.abs(price);
  const tick =
    abs >= 500000 ? 1000 :
    abs >= 200000 ? 500 :
    abs >= 50000 ? 100 :
    abs >= 20000 ? 50 :
    abs >= 5000 ? 10 :
    abs >= 2000 ? 5 :
    1;
  return Math.round(price / tick) * tick;
}

function formatPriceRange(low, high) {
  const roundedLow = roundTradePrice(low);
  const roundedHigh = roundTradePrice(high);
  if (roundedLow === null || roundedHigh === null) {
    return "-";
  }
  return `${formatPrice(Math.min(roundedLow, roundedHigh))}~${formatPrice(Math.max(roundedLow, roundedHigh))}`;
}

function toDisplayCurrency(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return null;
  }
  return state.currencyMode === "KRW" ? number * state.usdKrwRate : number;
}

function formatUsdCompact(number) {
  const abs = Math.abs(number);
  if (abs >= 1_000_000_000_000) {
    return `$${(number / 1_000_000_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}T`;
  }
  if (abs >= 1_000_000_000) {
    return `$${(number / 1_000_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}B`;
  }
  if (abs >= 1_000_000) {
    return `$${(number / 1_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}M`;
  }
  return `$${number.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`;
}

function formatKrwCompact(number) {
  const rounded = Math.round(number);
  const abs = Math.abs(rounded);
  if (abs >= 1_0000_0000_0000) {
    return `${(rounded / 1_0000_0000_0000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조원`;
  }
  if (abs >= 1_0000_0000) {
    return `${(rounded / 1_0000_0000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억원`;
  }
  if (abs >= 1_0000) {
    return `${(rounded / 1_0000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만원`;
  }
  return `${rounded.toLocaleString("ko-KR")}원`;
}

function formatPrice(value) {
  const number = toDisplayCurrency(value);
  if (number === null) {
    return "-";
  }
  if (state.currencyMode === "KRW") {
    return `${Math.round(number).toLocaleString("ko-KR")}원`;
  }
  return `$${number.toLocaleString("ko-KR", { minimumFractionDigits: number < 100 ? 2 : 0, maximumFractionDigits: 2 })}`;
}

function formatPriceChange(value) {
  const number = toDisplayCurrency(value);
  if (number === null) {
    return "-";
  }
  const sign = number > 0 ? "+" : number < 0 ? "-" : "";
  const abs = Math.abs(number);
  if (state.currencyMode === "KRW") {
    return `${sign}${Math.round(abs).toLocaleString("ko-KR")}원`;
  }
  return `${sign}$${abs.toLocaleString("ko-KR", { minimumFractionDigits: abs < 100 ? 2 : 0, maximumFractionDigits: 2 })}`;
}

function formatMoney(value) {
  const number = toDisplayCurrency(value);
  if (number === null) {
    return "-";
  }
  if (state.currencyMode === "KRW") {
    return formatKrwCompact(number);
  }
  return formatUsdCompact(number);
}

function updateCurrencyButtons() {
  const isKrw = state.currencyMode === "KRW";
  if (elements.displayCurrencyLabel) {
    elements.displayCurrencyLabel.textContent = isKrw ? "원" : "달러";
  }
  if (elements.displayCurrencyToggle) {
    elements.displayCurrencyToggle.classList.toggle("loading", state.currencyLoading);
    elements.displayCurrencyToggle.setAttribute("aria-label", `표시 단가를 ${isKrw ? "달러" : "원"}로 변경`);
    elements.displayCurrencyToggle.title = isKrw
      ? `현재 원화 표시 · 클릭하면 달러로 변경`
      : `현재 달러 표시 · 클릭하면 원으로 변경`;
  }
}

async function loadUsdKrwRate(options = {}) {
  state.currencyLoading = true;
  updateCurrencyButtons();
  try {
    const payload = await fetchJsonCached(`/us/fx/usdkrw${options.refresh ? "?refresh=1" : ""}`, {
      force: Boolean(options.refresh),
      ttlMs: 5 * 60 * 1000,
    });
    const rate = Number(payload.rate);
    if (Number.isFinite(rate) && rate > 0) {
      state.usdKrwRate = rate;
    }
  } catch {
    state.usdKrwRate = state.usdKrwRate || DEFAULT_USDKRW_RATE;
  } finally {
    state.currencyLoading = false;
    updateCurrencyButtons();
  }
}

async function toggleCurrencyMode() {
  state.currencyMode = state.currencyMode === "KRW" ? "USD" : "KRW";
  localStorage.setItem(CURRENCY_MODE_KEY, state.currencyMode);
  updateCurrencyButtons();
  if (state.currencyMode === "KRW") {
    await loadUsdKrwRate();
  }
  refreshCurrentViewForCurrency();
}

function refreshCurrentViewForCurrency() {
  updateCurrencyButtons();
  if (state.view === "stock" && isStockOverviewMode() && state.currentStockOverview) {
    renderStockOverview(state.currentStockOverview);
    return;
  }
  if (state.view === "stock" && state.currentDashboard) {
    render(state.currentDashboard);
    return;
  }
  if (state.view === "watchlist") {
    loadWatchlist();
    return;
  }
  if (state.view === "market") {
    const cached = state.marketRankingCache.get(marketRankingKey(state.rankingCategory, currentMarketFilter()));
    if (cached?.payload) {
      renderRankings(cached.payload);
    } else {
      loadMarketRankings();
    }
    return;
  }
  if (state.view === "recommend") {
    updateRecommendationTrackMeta();
    updateRecommendationTrackButtons();
    for (const card of Array.from(elements.recommendList.querySelectorAll(".recommend-card"))) {
      const item = card.recommendationItem;
      if (!item) continue;
      card.replaceWith(createRecommendationCard(item));
    }
    return;
  }
  if (state.view === "recommend-history") {
    void loadRecommendationHistory({ force: false });
    return;
  }
  if (state.view === "chart") {
    loadWatchCharts();
    return;
  }
  if (state.view === "chart-history") {
    renderChartSnapshots();
  }
}

function formatPercent(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function formatDateOnly(value) {
  const formatted = formatDate(value);
  return formatted === "-" ? "-" : formatted.split(" ")[0];
}

function formatMultiple(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return `${number.toFixed(2)}x`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatRatio(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return `${number.toFixed(2)}배`;
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  return String(value).replace("T", " ").slice(0, 16);
}

function socketUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

function currentPresencePageKey() {
  const path = window.location.pathname || "/nasdaq";
  const search = window.location.search || "";
  return `${path}${search}` || "/nasdaq";
}

function presenceHourKey(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}-${values.hour}`;
}

function hashPresenceHourDigit(hourKey) {
  let hash = 0;
  for (let index = 0; index < hourKey.length; index += 1) {
    hash = (hash * 31 + hourKey.charCodeAt(index)) % 9973;
  }
  return (hash % 9) + 1;
}

function presenceHundredsDigit() {
  const hourKey = presenceHourKey();
  if (state.presenceHundredsHourKey === hourKey && Number.isFinite(state.presenceHundredsDigit)) {
    return state.presenceHundredsDigit;
  }
  const digit = hashPresenceHourDigit(hourKey);
  state.presenceHundredsHourKey = hourKey;
  state.presenceHundredsDigit = digit;
  return digit;
}

function schedulePresenceHourRefresh() {
  if (state.presenceHourTimer) {
    window.clearTimeout(state.presenceHourTimer);
    state.presenceHourTimer = null;
  }
  const now = new Date();
  const nextHour = new Date(now);
  nextHour.setMinutes(60, 1, 0);
  state.presenceHourTimer = window.setTimeout(() => {
    state.presenceHundredsHourKey = "";
    renderPresenceStatus({ count: state.presenceCount, connected: state.presenceSocket?.readyState === WebSocket.OPEN });
    schedulePresenceHourRefresh();
  }, Math.max(1000, nextHour.getTime() - now.getTime()));
}

function formatPresenceDisplayCount(count) {
  if (!Number.isFinite(count)) {
    return "-";
  }
  const actual = Math.max(0, Math.trunc(Number(count)));
  const lastTwoDigits = String(actual % 100).padStart(2, "0");
  return `${presenceHundredsDigit()}${lastTwoDigits}`;
}

function renderPresenceStatus({ count = null, connected = false } = {}) {
  if (elements.sidebarPresenceCount) {
    elements.sidebarPresenceCount.textContent = Number.isFinite(count) ? `${formatPresenceDisplayCount(count)}명` : "-명";
  }
  if (connected || Number.isFinite(count)) {
    schedulePresenceHourRefresh();
  }
}

function sendPresencePage() {
  const page = currentPresencePageKey();
  state.presencePageKey = page;
  if (state.presenceSocket?.readyState === WebSocket.OPEN) {
    state.presenceSocket.send(JSON.stringify({ page }));
    return;
  }
  connectPresenceStream();
}

function connectPresenceStream() {
  if (!("WebSocket" in window)) {
    renderPresenceStatus({ count: null, connected: false });
    return;
  }
  if (state.presenceSocket && state.presenceSocket.readyState <= WebSocket.OPEN) {
    return;
  }
  if (state.presenceReconnectTimer) {
    window.clearTimeout(state.presenceReconnectTimer);
    state.presenceReconnectTimer = null;
  }
  const socket = new WebSocket(socketUrl("/ws/presence"));
  state.presenceSocket = socket;
  socket.onopen = () => {
    renderPresenceStatus({ count: state.presenceCount, connected: true });
    sendPresencePage();
  };
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload?.type !== "presence" || payload.page !== currentPresencePageKey()) {
        return;
      }
      state.presencePageKey = payload.page;
      state.presenceCount = Number.isFinite(Number(payload.count)) ? Number(payload.count) : null;
      renderPresenceStatus({ count: state.presenceCount, connected: true });
    } catch {
      return;
    }
  };
  socket.onclose = () => {
    if (state.presenceSocket === socket) {
      state.presenceSocket = null;
    }
    renderPresenceStatus({ count: state.presenceCount, connected: false });
    state.presenceReconnectTimer = window.setTimeout(connectPresenceStream, 1500);
  };
  socket.onerror = () => {
    socket.close();
  };
}

function selectorEscape(value) {
  if (window.CSS?.escape) {
    return window.CSS.escape(String(value));
  }
  return String(value).replace(/["\\]/g, "\\$&");
}

function looksLikeUsSymbol(value) {
  return /^[A-Za-z][A-Za-z0-9.-]{0,9}$/.test(String(value || "").trim());
}

function animateTextUpdate(node, nextText, nextValue = null) {
  if (!node || nextText === "-" || node.textContent === nextText) {
    return;
  }
  const previousRaw = node.dataset.rawValue;
  const previous = previousRaw === undefined || previousRaw === "" ? null : Number(previousRaw);
  const next = nextValue === null || nextValue === undefined || nextValue === "" ? null : Number(nextValue);
  node.textContent = nextText;
  if (Number.isFinite(next)) {
    node.dataset.rawValue = String(next);
  }
  node.classList.remove("quote-updated", "quote-count-up", "quote-count-down");
  void node.offsetWidth;
  if (Number.isFinite(previous) && Number.isFinite(next) && previous !== next) {
    node.classList.add(next > previous ? "quote-count-up" : "quote-count-down");
  } else {
    node.classList.add("quote-updated");
  }
}

function updateQuoteStrip(quote, payload = null) {
  if (!quote) return;
  animateTextUpdate(elements.quotePrice, formatPrice(quote.price), quote.price);
  animateTextUpdate(elements.stockChangeValue, formatPriceChange(quote.change_value), quote.change_value);
  animateTextUpdate(elements.quoteChange, formatPercent(quote.change_rate), quote.change_rate);
  setTone(elements.stockChangeValue, quote.change_value);
  setTone(elements.quoteChange, quote.change_rate);
  animateTextUpdate(elements.stockVolume, formatNumber(quote.volume), quote.volume);
  animateTextUpdate(elements.quoteValue, formatMoney(quote.trading_value), quote.trading_value);
  animateTextUpdate(elements.quoteCap, formatMoney(quote.market_cap), quote.market_cap);
  if (payload?.as_of && state.currentStock?.code === payload.code) {
    elements.meta.textContent = `${payload.code} · ${payload.market || state.currentStock.market} · ${formatDate(payload.as_of)} · 실시간 갱신`;
    elements.meta.hidden = true;
  }
}

function formatProbability(value) {
  const number = toNumber(value);
  return number === null ? "-" : `${number.toFixed(1)}%`;
}

function setActiveStockTab(tabName, options = {}) {
  state.stockActiveTab = tabName || "summary";
  const tabsVisible = elements.stockSectionTabs.some((tab) => !tab.closest("[hidden]"));
  if (!tabsVisible) {
    for (const panel of elements.stockTabPanels) {
      panel.hidden = false;
    }
    return;
  }
  for (const tab of elements.stockSectionTabs) {
    const active = tab.dataset.stockTab === state.stockActiveTab;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  }
  for (const panel of elements.stockTabPanels) {
    panel.hidden = panel.dataset.stockPanel !== state.stockActiveTab;
  }
  if (!options.preserveScroll) {
    window.requestAnimationFrame(() => {
      const tabs = document.querySelector(".stock-detail-tabs");
      if (tabs) {
        tabs.scrollIntoView({ block: "start", behavior: options.instant ? "auto" : "smooth" });
      }
    });
  }
}

function flowScore(flows = {}) {
  const stockFlow = toNumber(flows.foreign_intensity);
  const etfFlow = toNumber(flows.institution_intensity);
  const values = [stockFlow, etfFlow].filter((value) => value !== null);
  if (!values.length) {
    return 50;
  }
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  return clampNumber(50 + average, 0, 100);
}

function valuationScore(valuation = {}) {
  const perZ = toNumber(valuation.per_zscore);
  const pbrZ = toNumber(valuation.pbr_zscore);
  const zScores = [perZ, pbrZ].filter((value) => value !== null);
  if (!zScores.length) {
    return 50;
  }
  const averageZ = zScores.reduce((sum, value) => sum + value, 0) / zScores.length;
  return clampNumber(55 - averageZ * 10, 0, 100);
}

function flowLabel(flows = {}) {
  const score = flowScore(flows);
  if (score >= 62) return "유입 우위";
  if (score <= 42) return "둔화 구간";
  return "중립";
}

function valuationLabel(valuation = {}) {
  const score = valuationScore(valuation);
  if (score >= 64) return "과거 대비 낮음";
  if (score <= 42) return "과거 대비 부담";
  return "중립";
}

function newsLabel(sentiment = {}) {
  const score = toNumber(sentiment.score) || 0;
  if (score >= 15) return "호재 우위";
  if (score <= -15) return "악재 우위";
  return "중립";
}

function setSignalCard(labelNode, barNode, label, score) {
  setText(labelNode, label || "-");
  if (barNode) {
    barNode.style.width = `${clampNumber(score, 0, 100)}%`;
  }
}

function stockSignalProbability(data) {
  const chartScore = toNumber(data?.chart_analysis?.score);
  const base = chartScore === null ? 50 : chartScore;
  const flow = flowScore(data?.flows || {});
  const valuation = valuationScore(data?.valuation || {});
  const news = clampNumber(50 + (toNumber(data?.sentiment?.score) || 0), 0, 100);
  const momentum = clampNumber(50 + (toNumber(data?.momentum?.one_month_return) || 0) * 1.4, 0, 100);
  return clampNumber(base * 0.44 + flow * 0.18 + valuation * 0.14 + news * 0.12 + momentum * 0.12, 0, 100);
}

function stockSignalConfidence(data) {
  const checks = [
    data?.quote?.price,
    data?.chart_analysis?.score,
    data?.revisions?.report_count_90d,
    data?.momentum?.one_month_return,
    data?.flows?.foreign_intensity,
    data?.valuation?.per,
    data?.sentiment?.latest_items?.length,
    data?.macro_sensitivity?.interest_rate,
  ];
  const covered = checks.filter((value) => value !== null && value !== undefined && value !== "").length;
  return clampNumber(50 + covered * 5, 50, 90);
}

function renderStockLiveSummary(data) {
  const quote = data?.quote || {};
  setText(elements.stockLiveBadge, quote.trade_date ? `정규장 ${quote.trade_date}` : "실시간");
  setText(elements.stockPreMarket, `미국 정규장 기준 · ${formatDate(data?.as_of)}`);
  setText(elements.stockVolume, formatNumber(quote.volume));
  setText(elements.stockVolumeDetail, formatNumber(quote.volume));
  setText(elements.stockTradingValueDetail, formatMoney(quote.trading_value));
  setText(elements.stockMarketCapDetail, formatMoney(quote.market_cap));
}

function renderStockSummaryFallback(data) {
  const chart = data?.chart_analysis || {};
  const score = stockSignalProbability(data);
  const confidence = stockSignalConfidence(data);
  if (elements.stockSummaryScoreRing) {
    elements.stockSummaryScoreRing.style.setProperty("--score", score);
  }
  setText(elements.stockSummaryScore, formatProbability(score));
  setText(elements.stockSummaryConfidence, formatProbability(confidence));
  setText(elements.stockSummaryStance, chart.stance || "판단 대기");
  setText(
    elements.stockSummaryLine,
    `${data.name}은 차트 ${chart.trend || "데이터 확인 중"}, 수급 ${flowLabel(data.flows)}, 뉴스 ${newsLabel(data.sentiment)}, 밸류 ${valuationLabel(data.valuation)} 흐름입니다.`
  );
  setSignalCard(elements.stockSignalChart, elements.stockSignalChartBar, chart.trend || chart.stance || "차트 데이터 부족", score);
  setSignalCard(elements.stockSignalFlow, elements.stockSignalFlowBar, flowLabel(data.flows), flowScore(data.flows));
  setSignalCard(elements.stockSignalValuation, elements.stockSignalValuationBar, valuationLabel(data.valuation), valuationScore(data.valuation));
  setSignalCard(elements.stockSignalNews, elements.stockSignalNewsBar, newsLabel(data.sentiment), clampNumber(50 + (toNumber(data.sentiment?.score) || 0), 0, 100));
  renderStockStrategyVisual(null);
}

function renderEvidenceSummary(data) {
  const chart = data?.chart_analysis || {};
  const sentiment = data?.sentiment || {};
  const flows = data?.flows || {};
  const valuation = data?.valuation || {};
  const surprise = data?.surprise || {};
  setText(elements.evidenceSummaryChart, `${chart.trend || "추세 확인"} · ${chart.stance || "판단 대기"}`);
  setText(
    elements.evidenceSummaryFlow,
    `개별 ${formatPercent(flows.foreign_intensity)} · ETF ${formatPercent(flows.institution_intensity)}`
  );
  setText(
    elements.evidenceSummaryValue,
    `영업이익 ${formatPercent(surprise.operating_profit_growth)} · PER ${formatMultiple(valuation.per)}`
  );
  setText(elements.evidenceSummaryNews, `${newsLabel(sentiment)} · ${formatPercent(sentiment.score)}`);
}

function renderAIDecisionSummary(payload) {
  const levels = payload?.trade_levels || {};
  const buyLow = toNumber(levels.buy_low);
  const buyHigh = toNumber(levels.buy_high);
  const breakout = toNumber(levels.breakout);
  const stop = toNumber(levels.stop);
  const confidence = toNumber(payload?.confidence);
  const actionable = isTradeLevelActionable(levels, payload);
  const entryLabel = levels.entry_label || (actionable ? "1차 매수권" : "관찰 가격대");
  const entry = buyLow !== null && buyHigh !== null
    ? `${entryLabel} ${formatPrice(Math.min(buyLow, buyHigh))}~${formatPrice(Math.max(buyLow, buyHigh))}`
    : "-";
  const conditionParts = [];
  if (breakout !== null) {
    conditionParts.push(`돌파 ${formatPrice(breakout)}`);
  }
  if (stop !== null) {
    conditionParts.push(`축소 ${formatPrice(stop)}`);
  }
  const condition = conditionParts.length
    ? `${actionable ? "분할 접근" : "관찰 우선"} · ${conditionParts.join(" · ")}`
    : (payload?.stance || "-");
  setText(elements.aiDecisionStance, payload?.stance || "-");
  setText(elements.aiDecisionConfidence, confidence === null ? "-" : formatProbability(confidence));
  setText(elements.aiDecisionEntry, entry);
  setText(elements.aiDecisionCondition, condition);
  if (elements.aiDecisionStance) {
    const stance = String(payload?.stance || "");
    setTone(elements.aiDecisionStance, stance.includes("관망") ? -1 : stance.includes("중립") ? 0 : 1);
  }
}

function resetStockMiniChart() {
  if (elements.stockMiniChart) {
    elements.stockMiniChart.innerHTML = "<p>가격 데이터 준비 중</p>";
  }
  setText(elements.stockPrevCloseSummary, "-");
}

function renderStockMiniChart(prices, quote = null) {
  if (!elements.stockMiniChart) {
    return;
  }
  const rows = (prices || [])
    .map((row) => ({
      date: row.trade_date || row.date,
      close: toNumber(row.close),
      open: toNumber(row.open),
      high: toNumber(row.high),
      low: toNumber(row.low),
      volume: toNumber(row.volume),
    }))
    .filter((row) => row.date && row.close !== null)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
    .slice(-80);
  if (rows.length < 2) {
    elements.stockMiniChart.innerHTML = "<p>가격 데이터 부족</p>";
    return;
  }
  const latest = rows[rows.length - 1];
  const previous = rows[rows.length - 2];
  setText(elements.stockOpen, formatPrice(latest.open));
  setText(elements.stockHigh, formatPrice(latest.high));
  setText(elements.stockLow, formatPrice(latest.low));
  setText(elements.stockPrevClose, formatPrice(previous.close));
  const width = 360;
  const height = 150;
  const padding = 14;
  const values = rows.map((row) => row.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max === min ? 1 : max - min;
  const points = rows.map((row, index) => {
    const x = padding + (index / (rows.length - 1)) * (width - padding * 2);
    const y = height - padding - ((row.close - min) / span) * (height - padding * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const start = values[0];
  const end = values[values.length - 1];
  const toneClass = end >= start ? "up" : "down";
  elements.stockMiniChart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 가격 흐름">
      <defs>
        <linearGradient id="stockMiniGradient" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="currentColor" stop-opacity="0.20" />
          <stop offset="100%" stop-color="currentColor" stop-opacity="0.02" />
        </linearGradient>
      </defs>
      <polyline class="mini-chart-fill ${toneClass}" points="${points[0]} ${points.join(" ")} ${points[points.length - 1].split(",")[0]},${height - padding} ${padding},${height - padding}" />
      <polyline class="mini-chart-line ${toneClass}" points="${points.join(" ")}" />
    </svg>
    <div><span>${formatPrice(start)}</span><strong>${formatPrice(end)}</strong></div>
    <p class="mini-chart-date-range">기준 ${rows[0].date} ~ ${latest.date} · 최근 ${formatNumber(rows.length)}거래일</p>
  `;
}

async function loadStockMiniPrices(code, quote = null) {
  resetStockMiniChart();
  try {
    const prices = await fetchJsonCached(liveUrl(`/us/stocks/${encodeURIComponent(code)}/prices?limit=260`), { force: true, ttlMs: 0 });
    if (state.currentStock?.code === code) {
      renderStockMiniChart(prices, quote);
    }
  } catch {
    if (state.currentStock?.code === code && elements.stockMiniChart) {
      elements.stockMiniChart.innerHTML = "<p>가격 데이터 부족</p>";
    }
  }
}

function renderStockStrategyVisual(payload) {
  if (!elements.stockPriceLadder) {
    return;
  }
  const price = toNumber(state.currentDashboard?.quote?.price);
  const chart = state.currentDashboard?.chart_analysis || {};
  const levels = payload?.trade_levels || {};
  const support = toNumber(levels.stop) || toNumber(chart.support);
  const resistance = toNumber(levels.breakout) || toNumber(chart.resistance);
  const buyLow = toNumber(levels.buy_low) || (price ? price * 0.985 : null);
  const buyHigh = toNumber(levels.buy_high) || (price ? price * 1.005 : null);
  const stop = support || (price ? price * 0.965 : null);
  const breakout = resistance || (price ? price * 1.025 : null);
  const firstSell = toNumber(levels.first_sell) || (price ? Math.max(breakout || price, price * 1.04) : null);
  setText(elements.stockStrategyStance, payload?.stance || chart.stance || "-");
  if (!price) {
    setText(elements.stockStrategyStatus, "현재가 데이터가 부족해 가격 기준을 계산하지 못했습니다.");
    elements.stockPriceLadder.innerHTML = '<p class="muted">전략 가격대 대기 중</p>';
    return;
  }
  setText(
    elements.stockStrategyStatus,
    `${state.currentStock?.name || "현재 종목"} 기준 1차 관찰 구간은 ${formatPrice(buyLow)}~${formatPrice(buyHigh)}, 돌파 기준은 ${formatPrice(breakout)}입니다.`
  );
  const cards = [
    { label: "현재가", value: formatPrice(price), note: "지금 거래 기준", tone: "current" },
    { label: "1차 매도", value: formatPrice(firstSell), note: "일부 이익 실현", tone: "sell" },
    { label: "돌파", value: formatPrice(breakout), note: "거래대금 동반 필요", tone: "breakout" },
    { label: "축소", value: formatPrice(stop), note: "이탈 시 비중 축소", tone: "risk" },
    { label: "1차 관찰 구간", value: `${formatPrice(buyLow)}~${formatPrice(buyHigh)}`, note: "분할 접근 후보", tone: "buy", featured: true },
  ];
  const rawValues = [price, buyLow, buyHigh, stop, breakout, firstSell].filter((value) => value !== null);
  const rawMin = Math.min(...rawValues);
  const rawMax = Math.max(...rawValues);
  const rawSpan = rawMax === rawMin ? Math.max(rawMax * 0.04, 1) : rawMax - rawMin;
  const min = Math.max(0, rawMin - rawSpan * 0.08);
  const max = rawMax + rawSpan * 0.08;
  const span = max === min ? 1 : max - min;
  const pos = (value) => clampNumber(((value - min) / span) * 100, 0, 100);
  const zoneStyle = (from, to, minimum = 2) => {
    if (from === null || to === null) return "display:none;";
    const left = pos(Math.min(from, to));
    return `left:${left}%;width:${Math.max(minimum, pos(Math.max(from, to)) - left)}%;`;
  };
  elements.stockPriceLadder.innerHTML = `
    <div class="strategy-range-chart" aria-label="매매 가격 기준 가로 막대그래프">
      <div class="strategy-range-scale">
        <span>${formatPrice(min)}</span>
        <strong>가격 기준선</strong>
        <span>${formatPrice(max)}</span>
      </div>
      <div class="strategy-range-track">
        <span class="strategy-zone risk" style="${zoneStyle(min, stop, 1)}"></span>
        <span class="strategy-zone buy" style="${zoneStyle(buyLow, buyHigh, 3)}"></span>
        <span class="strategy-zone breakout" style="${zoneStyle(breakout, max, 1)}"></span>
        <span class="strategy-tick risk" style="left:${pos(stop)}%;"></span>
        <span class="strategy-tick buy" style="left:${pos(buyLow)}%;"></span>
        <span class="strategy-tick buy" style="left:${pos(buyHigh)}%;"></span>
        <span class="strategy-tick breakout" style="left:${pos(breakout)}%;"></span>
        <span class="strategy-current" style="left:${pos(price)}%;">
          <i></i>
          <b>현재가</b>
          <em>${formatPrice(price)}</em>
        </span>
      </div>
      <div class="strategy-range-legend">
        <span><i class="risk"></i>축소 구간</span>
        <span><i class="buy"></i>관찰 구간</span>
        <span><i class="breakout"></i>돌파 이후</span>
      </div>
    </div>
    <div class="strategy-level-grid">
      ${cards.map((item) => `
        <div class="strategy-level-card ${item.tone}${item.featured ? " featured" : ""}">
          <span>${item.label}</span>
          <strong>${item.value}</strong>
          <em>${item.note}</em>
        </div>
      `).join("")}
    </div>
  `;
}

function closeQuoteStream() {
  window.clearTimeout(state.quoteReconnectTimer);
  state.quoteReconnectTimer = null;
  state.quoteSocketCode = "";
  if (state.quoteSocket) {
    state.quoteSocket.onclose = null;
    state.quoteSocket.close();
    state.quoteSocket = null;
  }
}

function connectQuoteStream(stock) {
  if (!stock?.code || !("WebSocket" in window)) {
    return;
  }
  if (state.quoteSocket && state.quoteSocketCode === stock.code && state.quoteSocket.readyState <= WebSocket.OPEN) {
    return;
  }
  closeQuoteStream();
  const code = stock.code;
  const socket = new WebSocket(socketUrl(`/ws/us/stocks/${encodeURIComponent(code)}/quote`));
  state.quoteSocket = socket;
  state.quoteSocketCode = code;
  socket.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload?.type !== "quote" || payload.code !== state.currentStock?.code) {
      return;
    }
    updateQuoteStrip(payload.quote, payload);
  };
  socket.onclose = () => {
    if (state.view !== "stock" || state.currentStock?.code !== code) {
      return;
    }
    state.quoteReconnectTimer = window.setTimeout(() => connectQuoteStream(state.currentStock), 5000);
  };
  socket.onerror = () => socket.close();
}

function closeWatchlistQuoteStreams() {
  for (const timer of state.watchlistQuoteReconnectTimers.values()) {
    window.clearTimeout(timer);
  }
  state.watchlistQuoteReconnectTimers.clear();
  for (const socket of state.watchlistQuoteSockets.values()) {
    socket.onclose = null;
    socket.close();
  }
  state.watchlistQuoteSockets.clear();
}

function clearUsSectorRefreshTimer() {
  if (state.usSectorRefreshTimer) {
    window.clearTimeout(state.usSectorRefreshTimer);
    state.usSectorRefreshTimer = null;
  }
}

function closeUsSectorStream() {
  clearUsSectorRefreshTimer();
  if (state.usSectorSocket) {
    state.usSectorSocket.onclose = null;
    state.usSectorSocket.close();
    state.usSectorSocket = null;
  }
}

function applyUsSectorMoves(payload = null) {
  state.usSectorMoves = payload || null;
  updateWatchPreOpenPoints(state.usSectorMoves);
  updateRecommendationUsSectorCards(state.usSectorMoves);
}

function loadUsSectorMoves(options = {}) {
  const force = options.force === true;
  return fetchJsonCached(
    force ? liveUrl("/market/us-sector-moves?refresh=1") : "/market/us-sector-moves",
    { force, ttlMs: force ? 0 : 5 * 60 * 1000 },
  );
}

function scheduleUsSectorRefresh(payload = state.usSectorMoves) {
  clearUsSectorRefreshTimer();
  if (!["watchlist", "recommend"].includes(state.view)) {
    return;
  }
  if (state.usSectorSocket && state.usSectorSocket.readyState <= WebSocket.OPEN) {
    return;
  }
  const intervalSeconds = Math.max(
    30,
    toNumber(payload?.refresh_interval_seconds) || (payload?.market_session === "regular" ? 60 : 300),
  );
  state.usSectorRefreshTimer = window.setTimeout(() => {
    refreshUsSectorMoves({ force: true }).catch(() => undefined);
  }, intervalSeconds * 1000);
}

async function refreshUsSectorMoves(options = {}) {
  if (state.usSectorRefreshing && !options.force) {
    return state.usSectorMoves;
  }
  state.usSectorRefreshing = true;
  try {
    const payload = await loadUsSectorMoves({ force: options.force === true });
    applyUsSectorMoves(payload);
    scheduleUsSectorRefresh(payload);
    return payload;
  } finally {
    state.usSectorRefreshing = false;
  }
}

function connectUsSectorStream() {
  if (!["watchlist", "recommend"].includes(state.view) || !("WebSocket" in window)) {
    return;
  }
  if (state.usSectorSocket && state.usSectorSocket.readyState <= WebSocket.OPEN) {
    return;
  }
  closeUsSectorStream();
  const socket = new WebSocket(socketUrl("/ws/market/us-sector-moves"));
  state.usSectorSocket = socket;
  socket.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload?.type !== "us_sector_moves" && !Array.isArray(payload?.items)) {
      return;
    }
    applyUsSectorMoves(payload);
    scheduleUsSectorRefresh(payload);
  };
  socket.onclose = () => {
    if (!["watchlist", "recommend"].includes(state.view)) {
      return;
    }
    scheduleUsSectorRefresh();
  };
  socket.onerror = () => socket.close();
}

function renderWatchlistMessage(text) {
  clearWatchlistLoadingOverlay();
  elements.watchlistBody.innerHTML = "";
  const card = document.createElement("article");
  card.className = "watchlist-empty-card";
  card.textContent = text;
  elements.watchlistBody.appendChild(card);
}

function watchFlowPoint(flows = {}) {
  const liquidityScore = toNumber(flows.liquidity_score ?? flows.score ?? flows.etf_flow_score);
  const intensity = toNumber(flows.liquidity_intensity ?? flows.etf_intensity ?? flows.trading_intensity);
  if (liquidityScore !== null && liquidityScore >= 60) {
    return "수급 유입 우위";
  }
  if (liquidityScore !== null && liquidityScore <= 40) {
    return "수급 둔화 구간";
  }
  if (intensity !== null && intensity >= 20) {
    return "거래 강도 확대";
  }
  if (intensity !== null && intensity <= -20) {
    return "거래 강도 약화";
  }
  return "수급 중립";
}

function watchTrendPoint(oneMonth, threeMonth) {
  if (oneMonth === null && threeMonth === null) {
    return "모멘텀 데이터 대기";
  }
  if ((oneMonth ?? 0) >= 10 || (threeMonth ?? 0) >= 20) {
    return "상승 모멘텀 우위";
  }
  if ((oneMonth ?? 0) <= -10 || (threeMonth ?? 0) <= -20) {
    return "약세 모멘텀 주의";
  }
  return `1개월 ${formatPercent(oneMonth)} · 3개월 ${formatPercent(threeMonth)}`;
}

function watchNewsPoint(sentiment = {}) {
  const score = toNumber(sentiment.score);
  if (score === null) {
    return "뉴스 판단 대기";
  }
  if (score >= 15) {
    return "뉴스 톤 긍정 우위";
  }
  if (score <= -15) {
    return "뉴스 톤 부정 우위";
  }
  return "뉴스 톤 중립";
}

function usSectorMoveMap(usSectorMoves = state.usSectorMoves) {
  return new Map((usSectorMoves?.items || []).map((item) => [item.symbol, item]));
}

function relatedUsSectorSymbols(item = {}, dashboard = {}) {
  const text = `${item.name || ""} ${dashboard.name || ""} ${item.code || dashboard.code || ""} ${dashboard.sector || ""}`.toUpperCase();
  const symbols = [];
  const add = (...values) => {
    for (const value of values) {
      if (value && !symbols.includes(value)) {
        symbols.push(value);
      }
    }
  };

  if (/NVDA|AMD|AVGO|QCOM|TXN|MU|AMAT|LRCX|KLAC|ASML|ARM|MRVL|INTC|SOXX|SEMICONDUCT|반도체|메모리|EDA/.test(text)) {
    add("SOXX", "XLK");
  }
  if (/AAPL|MSFT|GOOGL|GOOG|META|ORCL|ADBE|CRM|INTU|CSCO|TMUS|PLTR|QQQ|TECH|SOFTWARE|클라우드|AI|소프트웨어|광고/.test(text)) {
    add("XLK", "QQQ");
  }
  if (/TSLA|AMZN|BKNG|ABNB|SBUX|MCD|SHOP|MELI|XLY|CONSUMER|여행|이커머스|소비|콘텐츠|자동차/.test(text)) {
    add("XLY", "SPY");
  }
  if (/JPM|BAC|BRK|V|MA|PYPL|XLF|금융|결제/.test(text)) {
    add("XLF", "SPY");
  }
  if (/XOM|CVX|CEG|XLE|XLU|ENERGY|에너지|전력|원전|유틸리티/.test(text)) {
    add("XLE", "XLU");
  }
  if (/LLY|UNH|JNJ|MRK|ABBV|TMO|AMGN|GILD|REGN|VRTX|ISRG|XLV|HEALTH|헬스|바이오|의료/.test(text)) {
    add("XLV", "SPY");
  }
  if (/COST|WMT|PG|KO|PEP|MDLZ|XLP|필수소비재/.test(text)) {
    add("XLP", "SPY");
  }
  if (/GE|CAT|HON|LIN|IYT|XLI|INDUSTR|산업재|운송|항공/.test(text)) {
    add("XLI", "IYT");
  }
  add("QQQ", "SPY");
  return symbols.slice(0, 2);
}

function relatedUsSectorMoves(item = {}, dashboard = {}, usSectorMoves = state.usSectorMoves) {
  const moves = usSectorMoveMap(usSectorMoves);
  return relatedUsSectorSymbols(item, dashboard)
    .map((symbol) => moves.get(symbol))
    .filter(Boolean);
}

function usSectorSessionLabel(usSectorMoves = state.usSectorMoves) {
  if (usSectorMoves?.market_session_label) {
    return usSectorMoves.market_session_label;
  }
  if (usSectorMoves?.market_session === "premarket") {
    return "미국 프리장";
  }
  if (usSectorMoves?.market_session === "regular") {
    return "미국 정규장";
  }
  if (usSectorMoves?.market_session === "afterhours") {
    return "미국 애프터장";
  }
  return "미국 정규장 마감";
}

function createWatchUsSectorStrip(item = {}, dashboard = {}, usSectorMoves = state.usSectorMoves) {
  const section = document.createElement("section");
  section.className = "watch-us-sector-strip";
  const title = document.createElement("span");
  title.textContent = "미국시장 참고";
  const session = document.createElement("strong");
  session.textContent = usSectorSessionLabel(usSectorMoves);
  const chips = document.createElement("div");
  const moves = relatedUsSectorMoves(item, dashboard, usSectorMoves);
  if (!moves.length) {
    const chip = document.createElement("em");
    chip.textContent = "섹터 데이터 대기";
    chips.appendChild(chip);
  } else {
    for (const move of moves) {
      const chip = document.createElement("em");
      const rate = toNumber(move.change_rate);
      chip.className = rate > 0 ? "positive" : rate < 0 ? "negative" : "muted";
      chip.textContent = `${move.label} ${formatPercent(move.change_rate)}`;
      chips.appendChild(chip);
    }
  }
  section.append(title, session, chips);
  return section;
}

function watchPreOpenSummary(dashboard, quoteOverride = null, item = {}, usSectorMoves = state.usSectorMoves) {
  const quote = quoteOverride || dashboard.quote || {};
  const session = usSectorMoves?.market_session || "closed";
  const preRate = toNumber(quote.pre_market_change_rate);
  const changeRate = toNumber(quote.change_rate);
  const oneMonth = toNumber(dashboard.momentum?.one_month_return);
  const threeMonth = toNumber(dashboard.momentum?.three_month_return);
  const macroView = interpretMacro(dashboard);
  const points = [];
  let title = "체크 포인트 대기";
  let tone = "muted";
  let label = "미국증시 체크 포인트";
  let collapsed = false;
  const addPoint = (text) => {
    if (!text || points.includes(text)) {
      return;
    }
    points.push(text);
  };

  if (session === "regular") {
    label = "미국 정규장 포인트";
    if (changeRate >= 1) {
      title = "강세 진행";
      tone = "positive";
    } else if (changeRate <= -1) {
      title = "약세 경계";
      tone = "negative";
    } else {
      title = "보합권 탐색";
    }
    collapsed = true;
  } else if (session === "afterhours") {
    label = "미국 애프터장 포인트";
    if (changeRate >= 1) {
      title = "강세 마감 후 연장";
      tone = "positive";
    } else if (changeRate <= -1) {
      title = "약세 마감 후 연장";
      tone = "negative";
    } else {
      title = "장마감 후 보합권";
    }
  } else if (session === "premarket") {
    label = "미국 프리장 포인트";
    if (preRate !== null) {
      if (preRate >= 1) {
        title = "상승 출발 체크";
        tone = "positive";
      } else if (preRate <= -1) {
        title = "하락 출발 주의";
        tone = "negative";
      } else {
        title = "보합 출발 관찰";
      }
      addPoint(preRate === 0 ? "장전 호가 대기" : `프리장 흐름 ${formatPercent(preRate)}`);
    } else {
      title = quote.pre_market_status || "프리장 데이터 대기";
      addPoint(quote.pre_market_status || "프리장 데이터 대기");
    }
  } else {
    label = "미국 장마감 포인트";
    if (changeRate >= 1) {
      title = "강세 마감";
      tone = "positive";
    } else if (changeRate <= -1) {
      title = "약세 마감";
      tone = "negative";
    } else {
      title = "보합권 마감";
    }
  }

  addPoint(watchFlowPoint(dashboard.flows || {}));
  addPoint(watchTrendPoint(oneMonth, threeMonth));
  addPoint(watchNewsPoint(dashboard.sentiment || {}));
  addPoint(macroView.label === "거시 중립" ? macroView.label : `거시 ${macroView.label}`);
  return {
    label,
    title,
    tone,
    points: points.slice(0, 5),
    collapsed,
    mode: session,
    hint: usSectorSessionLabel(usSectorMoves),
  };
}

function renderWatchPreOpenPoint(card, dashboard, quoteOverride = null, item = {}, usSectorMoves = state.usSectorMoves) {
  const point = watchPreOpenSummary(dashboard, quoteOverride, item, usSectorMoves);
  const itemCode = item?.code || card?.dataset?.code || "";
  let section = card.querySelector("[data-field='preopen_point']");
  if (!section || section.tagName !== "DETAILS") {
    const nextSection = document.createElement("details");
    if (section) {
      section.replaceWith(nextSection);
    }
    section = nextSection;
    section.className = "watch-preopen-point";
    section.dataset.field = "preopen_point";
    section.addEventListener("toggle", () => {
      const code = section.dataset.code || "";
      if (!code) {
        return;
      }
      if (section.open) {
        state.watchPreopenExpanded.add(code);
      } else {
        state.watchPreopenExpanded.delete(code);
      }
    });
  }
  section.dataset.code = itemCode;
  section.className = `watch-preopen-point ${point.tone} ${point.collapsed ? "collapsed" : ""}`;
  const keepExpanded = itemCode ? state.watchPreopenExpanded.has(itemCode) : false;
  section.open = point.collapsed ? keepExpanded : true;
  section.dataset.mode = point.mode || "";
  const summary = document.createElement("summary");
  const summaryMain = document.createElement("div");
  const label = document.createElement("span");
  label.textContent = point.label || "미국증시 체크 포인트";
  const title = document.createElement("strong");
  title.textContent = point.title;
  summaryMain.append(label, title);
  if (point.hint) {
    const hint = document.createElement("em");
    hint.textContent = point.hint;
    summaryMain.appendChild(hint);
  }
  summary.append(summaryMain);
  const list = document.createElement("ul");
  for (const bullet of point.points) {
    const row = document.createElement("li");
    row.textContent = bullet;
    list.appendChild(row);
  }
  section.replaceChildren(summary, list, createWatchUsSectorStrip(item, dashboard, usSectorMoves));
  return section;
}

function updateWatchPreOpenPoints(usSectorMoves = state.usSectorMoves) {
  for (const card of elements.watchlistBody.querySelectorAll("[data-watch-card]")) {
    if (!card.watchDashboard) {
      continue;
    }
    card.usSectorMoves = usSectorMoves;
    const point = renderWatchPreOpenPoint(
      card,
      card.watchDashboard,
      card.watchDashboard.quote,
      card.watchItem,
      usSectorMoves,
    );
    const priceRow = card.querySelector(".watch-stock-price-row");
    if (priceRow && point.nextSibling !== priceRow) {
      card.insertBefore(point, priceRow);
    }
  }
}

function clearWatchlistLoadingOverlay() {
  if (!elements.watchlistView) {
    return;
  }
  elements.watchlistView.classList.remove("is-loading");
  const overlay = document.querySelector(".watchlist-loader-overlay");
  if (overlay) {
    overlay.remove();
  }
}

function showWatchlistLoadingOverlay() {
  if (!elements.watchlistView) {
    return;
  }
  clearWatchlistLoadingOverlay();
  const overlay = document.createElement("div");
  overlay.className = "watchlist-loader-overlay";
  overlay.setAttribute("role", "status");
  overlay.setAttribute("aria-label", "관심종목을 불러오는 중");
  overlay.setAttribute("aria-busy", "true");
  const spinner = document.createElement("span");
  spinner.className = "inline-loading-spinner";
  spinner.setAttribute("aria-hidden", "true");
  overlay.appendChild(spinner);
  document.body.appendChild(overlay);
  elements.watchlistView.classList.add("is-loading");
}

function updateWatchlistRowQuote(code, quote) {
  if (!code || !quote) return;
  const card = elements.watchlistBody.querySelector(`.watch-stock-card[data-code="${selectorEscape(code)}"]`);
  if (!card) return;
  const priceCell = card.querySelector('[data-field="price"]');
  const changeCell = card.querySelector('[data-field="change_rate"]');
  const tradingValueCell = card.querySelector('[data-field="trading_value"]');
  animateTextUpdate(priceCell, formatPrice(quote.price), quote.price);
  animateTextUpdate(changeCell, formatPercent(quote.change_rate), quote.change_rate);
  if (changeCell) setTone(changeCell, quote.change_rate);
  animateTextUpdate(tradingValueCell, formatMoney(quote.trading_value), quote.trading_value);
  if (card.watchDashboard) {
    card.watchDashboard = {
      ...card.watchDashboard,
      quote: {
        ...(card.watchDashboard.quote || {}),
        ...quote,
      },
    };
    const point = renderWatchPreOpenPoint(
      card,
      card.watchDashboard,
      card.watchDashboard.quote,
      card.watchItem,
      card.usSectorMoves || state.usSectorMoves,
    );
    const priceRow = card.querySelector(".watch-stock-price-row");
    if (priceRow && point.nextSibling !== priceRow) {
      card.insertBefore(point, priceRow);
    }
  }
}

function connectWatchlistQuoteStream(code) {
  if (!code || !("WebSocket" in window)) return;
  const existing = state.watchlistQuoteSockets.get(code);
  if (existing && existing.readyState <= WebSocket.OPEN) return;
  const socket = new WebSocket(socketUrl(`/ws/us/stocks/${encodeURIComponent(code)}/quote`));
  state.watchlistQuoteSockets.set(code, socket);
  socket.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload?.type === "quote" && payload.code === code) {
      updateWatchlistRowQuote(code, payload.quote);
    }
  };
  socket.onclose = () => {
    if (state.watchlistQuoteSockets.get(code) === socket) {
      state.watchlistQuoteSockets.delete(code);
    }
    if (state.view !== "watchlist" || !elements.watchlistBody.querySelector(`.watch-stock-card[data-code="${selectorEscape(code)}"]`)) {
      return;
    }
    const timer = window.setTimeout(() => connectWatchlistQuoteStream(code), 5000);
    state.watchlistQuoteReconnectTimers.set(code, timer);
  };
  socket.onerror = () => socket.close();
}

function closeListQuoteStreams() {
  for (const timer of state.listQuoteReconnectTimers.values()) {
    window.clearTimeout(timer);
  }
  state.listQuoteReconnectTimers.clear();
  for (const socket of state.listQuoteSockets.values()) {
    socket.onclose = null;
    socket.close();
  }
  state.listQuoteSockets.clear();
}

function closeMarketQuoteStreams() {
  for (const timer of state.marketQuoteReconnectTimers.values()) {
    window.clearTimeout(timer);
  }
  state.marketQuoteReconnectTimers.clear();
  for (const socket of state.marketQuoteSockets.values()) {
    socket.onclose = null;
    socket.close();
  }
  state.marketQuoteSockets.clear();
}

function updateLiveQuoteElements(code, quote) {
  if (!code || !quote) return;
  for (const root of document.querySelectorAll(`[data-live-code="${selectorEscape(code)}"]`)) {
    const priceNode = root.querySelector('[data-live-field="price"]');
    const changeNode = root.querySelector('[data-live-field="change_rate"]');
    const tradingValueNode = root.querySelector('[data-live-field="trading_value"]');
    animateTextUpdate(priceNode, formatPrice(quote.price), quote.price);
    animateTextUpdate(changeNode, formatPercent(quote.change_rate), quote.change_rate);
    if (changeNode) setTone(changeNode, quote.change_rate);
    animateTextUpdate(tradingValueNode, formatMoney(quote.trading_value), quote.trading_value);
  }
}

function connectListQuoteStream(code) {
  if (!code || !("WebSocket" in window)) return;
  const existing = state.listQuoteSockets.get(code);
  if (existing && existing.readyState <= WebSocket.OPEN) return;
  const socket = new WebSocket(socketUrl(`/ws/us/stocks/${encodeURIComponent(code)}/quote`));
  state.listQuoteSockets.set(code, socket);
  socket.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload?.type === "quote" && payload.code === code) {
      updateLiveQuoteElements(code, payload.quote);
      updateTrackedRecommendationQuote(code, payload.quote);
    }
  };
  socket.onclose = () => {
    if (state.listQuoteSockets.get(code) === socket) {
      state.listQuoteSockets.delete(code);
    }
    const hasTarget =
      Boolean(document.querySelector(`[data-live-code="${selectorEscape(code)}"]`))
      || Boolean(elements.recommendHistoryList.querySelector(`.recommend-track-card[data-code="${selectorEscape(code)}"]`));
    if (!["market", "recommend", "recommend-history"].includes(state.view) || !hasTarget) {
      return;
    }
    const timer = window.setTimeout(() => connectListQuoteStream(code), 5000);
    state.listQuoteReconnectTimers.set(code, timer);
  };
  socket.onerror = () => socket.close();
}

function sortMarketLeaderboardItems() {
  state.marketLeaderboardItems.sort((a, b) => {
    const changeDiff = (toNumber(b.change_rate) ?? -Infinity) - (toNumber(a.change_rate) ?? -Infinity);
    if (changeDiff !== 0) {
      return changeDiff;
    }
    return (toNumber(b.trading_value) ?? 0) - (toNumber(a.trading_value) ?? 0);
  });
  state.marketLeaderboardItems = state.marketLeaderboardItems.slice(0, 20).map((item, index) => ({
    ...item,
    rank: index + 1,
  }));
}

function updateMarketLeaderboardQuote(code, quote) {
  if (!code || !quote) {
    return;
  }
  const item = state.marketLeaderboardItems.find((entry) => entry.code === code);
  if (!item) {
    return;
  }
  if (quote.price !== null && quote.price !== undefined && quote.price !== "") {
    item.price = quote.price;
  }
  if (quote.change_rate !== null && quote.change_rate !== undefined && quote.change_rate !== "") {
    item.change_rate = quote.change_rate;
    item.metric_value = quote.change_rate;
  }
  if (quote.trading_value !== null && quote.trading_value !== undefined && quote.trading_value !== "") {
    item.trading_value = quote.trading_value;
  }
  sortMarketLeaderboardItems();
  renderMarketSurgeLeaderboard();
}

function connectMarketQuoteStream(code) {
  if (!code || !("WebSocket" in window)) {
    return;
  }
  const existing = state.marketQuoteSockets.get(code);
  if (existing && existing.readyState <= WebSocket.OPEN) {
    return;
  }
  const timer = state.marketQuoteReconnectTimers.get(code);
  if (timer) {
    window.clearTimeout(timer);
    state.marketQuoteReconnectTimers.delete(code);
  }
  const socket = new WebSocket(socketUrl(`/ws/us/stocks/${encodeURIComponent(code)}/quote`));
  state.marketQuoteSockets.set(code, socket);
  socket.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload?.type !== "quote" || payload.code !== code) {
      return;
    }
    updateMarketLeaderboardQuote(code, payload.quote);
  };
  socket.onclose = () => {
    if (state.marketQuoteSockets.get(code) === socket) {
      state.marketQuoteSockets.delete(code);
    }
    if (state.view !== "market" || state.rankingCategory !== "surge") {
      return;
    }
    const reconnectTimer = window.setTimeout(() => connectMarketQuoteStream(code), 5000);
    state.marketQuoteReconnectTimers.set(code, reconnectTimer);
  };
  socket.onerror = () => socket.close();
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== "") {
    node.textContent = text;
  }
  return node;
}

function clonePayload(payload) {
  return JSON.parse(JSON.stringify(payload));
}

function liveUrl(url) {
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}_=${Date.now()}`;
}

async function fetchJsonCached(url, options = {}) {
  const ttlMs = options.ttlMs ?? UI_CACHE_TTL_MS;
  const force = Boolean(options.force);
  const now = Date.now();
  const cached = state.responseCache.get(url);
  if (!force && cached && now - cached.savedAt <= ttlMs) {
    return clonePayload(cached.payload);
  }
  if (!force && state.pendingRequests.has(url)) {
    return clonePayload(await state.pendingRequests.get(url));
  }
  const request = fetch(url, { cache: force || ttlMs === 0 ? "no-store" : "default" }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`request failed: ${url}`);
    }
    const payload = await response.json();
    state.responseCache.set(url, { savedAt: Date.now(), payload: clonePayload(payload) });
    return payload;
  });
  state.pendingRequests.set(url, request);
  try {
    return clonePayload(await request);
  } finally {
    state.pendingRequests.delete(url);
  }
}

async function mapWithConcurrency(items, limit, mapper, onProgress = null) {
  const results = new Array(items.length);
  let nextIndex = 0;
  let done = 0;
  const workerCount = Math.min(limit, items.length);
  const workers = Array.from({ length: workerCount }, async () => {
    while (nextIndex < items.length) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      results[currentIndex] = await mapper(items[currentIndex], currentIndex);
      done += 1;
      if (onProgress) {
        onProgress(done, items.length);
      }
    }
  });
  await Promise.all(workers);
  return results;
}

function clearCachedUrl(url) {
  state.responseCache.delete(url);
  state.pendingRequests.delete(url);
}

function isMobileViewport() {
  return window.matchMedia("(max-width: 980px)").matches;
}

function currentScrollTop() {
  return Math.max(window.scrollY || 0, document.documentElement.scrollTop || 0, document.body.scrollTop || 0);
}

function setPullRefreshIndicator(distance = 0, options = {}) {
  if (!elements.pullRefreshIndicator || !elements.pullRefreshLabel) {
    return;
  }
  window.clearTimeout(state.pullRefreshHideTimer);
  state.pullRefreshHideTimer = null;
  const nextDistance = Math.max(0, Math.min(PULL_REFRESH_MAX_DISTANCE, distance));
  const refreshing = options.refreshing === true;
  const ready = options.ready === true;
  state.pullRefreshDistance = nextDistance;
  elements.pullRefreshIndicator.hidden = false;
  elements.pullRefreshIndicator.classList.toggle("visible", nextDistance > 0 || refreshing);
  elements.pullRefreshIndicator.classList.toggle("ready", ready);
  elements.pullRefreshIndicator.classList.toggle("refreshing", refreshing);
  elements.pullRefreshLabel.textContent = refreshing
    ? "새로고침 중..."
    : ready
      ? "손을 떼면 새로고침"
      : "아래로 당겨서 새로고침";
  document.documentElement.style.setProperty("--pull-refresh-distance", `${refreshing ? PULL_REFRESH_TRIGGER_DISTANCE : nextDistance}px`);
  elements.appFrame?.classList.toggle("pull-refresh-active", nextDistance > 0 || refreshing);
}

function resetPullRefreshIndicator(options = {}) {
  state.pullRefreshTracking = false;
  state.pullRefreshReady = false;
  state.pullRefreshDistance = 0;
  document.documentElement.style.setProperty("--pull-refresh-distance", "0px");
  elements.appFrame?.classList.remove("pull-refresh-active");
  if (!elements.pullRefreshIndicator) {
    return;
  }
  elements.pullRefreshIndicator.classList.remove("ready", "refreshing", "visible");
  const immediate = options.immediate === true;
  window.clearTimeout(state.pullRefreshHideTimer);
  state.pullRefreshHideTimer = window.setTimeout(() => {
    if (!state.pullRefreshRefreshing) {
      elements.pullRefreshIndicator.hidden = true;
    }
  }, immediate ? 0 : 160);
}

function canStartPullRefresh(target) {
  if (!isMobileViewport() || state.pullRefreshRefreshing) {
    return false;
  }
  if (elements.loginGate && !elements.loginGate.hidden) {
    return false;
  }
  if (document.body.classList.contains("mobile-menu-open")) {
    return false;
  }
  if (currentScrollTop() > 0) {
    return false;
  }
  if (!(target instanceof Element)) {
    return true;
  }
  return !target.closest("input, textarea, select, .suggestions, .loading-modal-card, .install-sheet-card");
}

async function refreshCurrentView() {
  switch (state.view) {
    case "stock": {
      const query = stockNavigationQuery();
      const shouldRefreshAI = elements.aiAnalysisPanel?.hidden === false;
      await load(query);
      if (shouldRefreshAI && state.currentStock?.code) {
        await loadAIAnalysis();
      }
      return;
    }
    case "watchlist":
      await loadWatchlist({ force: true });
      return;
    case "recommend":
      await loadRecommendations({ auto: false });
      return;
    case "recommend-history":
      await loadRecommendationHistory({ force: true });
      return;
    case "trend":
      await loadTrends("events", { force: true });
      return;
    case "trend-past":
      await loadTrends("past", { force: true });
      return;
    case "trend-impact":
      await loadMarketImpactAnalysis({ force: true });
      return;
    case "chart":
      await loadWatchCharts({ force: true });
      return;
    case "chart-history":
      renderChartSnapshots();
      return;
    case "market":
      state.marketRankingCache.delete(marketRankingKey("surge", currentMarketFilter()));
      await loadMarketRankings({ market: currentMarketFilter(), force: true });
      return;
    default:
      return;
  }
}

async function triggerPullRefresh() {
  if (state.pullRefreshRefreshing) {
    return;
  }
  state.pullRefreshRefreshing = true;
  setPullRefreshIndicator(PULL_REFRESH_TRIGGER_DISTANCE, { ready: true, refreshing: true });
  const refreshPromise = refreshCurrentView().catch(() => null);
  const splashPromise = showAppSplash(APP_SPLASH_DURATION_MS);
  try {
    await Promise.all([refreshPromise, splashPromise]);
  } finally {
    state.pullRefreshRefreshing = false;
    resetPullRefreshIndicator();
  }
}

function handlePullRefreshStart(event) {
  if (event.touches.length !== 1 || !canStartPullRefresh(event.target)) {
    return;
  }
  const touch = event.touches[0];
  state.pullRefreshTracking = true;
  state.pullRefreshReady = false;
  state.pullRefreshDistance = 0;
  state.pullRefreshStartX = touch.clientX;
  state.pullRefreshStartY = touch.clientY;
}

function handlePullRefreshMove(event) {
  if (!state.pullRefreshTracking || state.pullRefreshRefreshing || event.touches.length !== 1) {
    return;
  }
  if (currentScrollTop() > 0) {
    resetPullRefreshIndicator({ immediate: true });
    return;
  }
  const touch = event.touches[0];
  const deltaX = touch.clientX - state.pullRefreshStartX;
  const deltaY = touch.clientY - state.pullRefreshStartY;
  if (deltaY <= 0) {
    resetPullRefreshIndicator({ immediate: true });
    return;
  }
  if (Math.abs(deltaX) > deltaY) {
    return;
  }
  const distance = Math.min(PULL_REFRESH_MAX_DISTANCE, Math.max(0, (deltaY - PULL_REFRESH_DRAG_OFFSET) * 0.55));
  if (distance <= 0) {
    return;
  }
  state.pullRefreshReady = distance >= PULL_REFRESH_TRIGGER_DISTANCE;
  setPullRefreshIndicator(distance, { ready: state.pullRefreshReady });
  if (event.cancelable) {
    event.preventDefault();
  }
}

function handlePullRefreshEnd() {
  if (!state.pullRefreshTracking) {
    return;
  }
  if (state.pullRefreshReady) {
    void triggerPullRefresh();
    return;
  }
  resetPullRefreshIndicator();
}

function hideSuggestions() {
  state.suggestions = [];
  state.suggestionIndex = -1;
  elements.suggestions.hidden = true;
  elements.suggestions.innerHTML = "";
  elements.input.setAttribute("aria-expanded", "false");
}

function setActiveSuggestion(index) {
  const buttons = Array.from(elements.suggestions.querySelectorAll(".suggestion-item"));
  if (!buttons.length) {
    state.suggestionIndex = -1;
    return;
  }
  state.suggestionIndex = (index + buttons.length) % buttons.length;
  buttons.forEach((button, buttonIndex) => {
    const active = buttonIndex === state.suggestionIndex;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
}

function chooseSuggestion(item) {
  elements.input.value = item.code;
  hideSuggestions();
  load(item.code);
}

function renderSuggestions(items) {
  state.suggestions = items || [];
  state.suggestionIndex = -1;
  elements.suggestions.innerHTML = "";
  if (!state.suggestions.length) {
    hideSuggestions();
    return;
  }
  for (const item of state.suggestions) {
    const button = document.createElement("button");
    button.className = "suggestion-item";
    button.type = "button";
    button.role = "option";
    button.dataset.code = item.code;
    const name = document.createElement("span");
    name.className = "suggestion-name";
    name.textContent = item.name;
    const meta = document.createElement("span");
    meta.className = "suggestion-meta";
    meta.textContent = `${item.code} · ${item.market}`;
    button.append(name, meta);
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => chooseSuggestion(item));
    elements.suggestions.appendChild(button);
  }
  elements.suggestions.hidden = false;
  elements.input.setAttribute("aria-expanded", "true");
}

async function fetchSuggestions(query) {
  const normalized = String(query || "").trim();
  if (normalized.length < 1) {
    hideSuggestions();
    return;
  }
  if (state.suggestionController) {
    state.suggestionController.abort();
  }
  state.suggestionController = new AbortController();
  try {
    const response = await fetch(`/us/stocks/search?query=${encodeURIComponent(normalized)}&limit=30`, {
      signal: state.suggestionController.signal,
    });
    if (!response.ok) {
      hideSuggestions();
      return;
    }
    renderSuggestions(await response.json());
  } catch (error) {
    if (error.name !== "AbortError") {
      hideSuggestions();
    }
  }
}

function scheduleSuggestions() {
  clearTimeout(state.suggestionTimer);
  state.suggestionTimer = setTimeout(() => fetchSuggestions(elements.input.value), 160);
}

function setTone(node, value) {
  node.classList.remove("positive", "negative", "muted");
  const number = Number(value);
  if (!Number.isFinite(number) || number === 0) {
    node.classList.add("muted");
  } else if (number > 0) {
    node.classList.add("positive");
  } else {
    node.classList.add("negative");
  }
}

function viewStockUrl(stockOrName) {
  const value = typeof stockOrName === "object" && stockOrName
    ? stockOrName.code || stockOrName.name
    : stockOrName;
  return `/nasdaq/${encodeURIComponent(value || "AAPL")}`;
}

function stockNavigationQuery() {
  return state.currentStock?.code || pathQuery();
}

function focusStockView(query = stockNavigationQuery()) {
  const normalized = String(query || "").trim() || "AAPL";
  history.replaceState(null, "", viewStockUrl(state.currentStock?.code ? state.currentStock : normalized));
  setView("stock");
  return normalized;
}

function readWatchlist() {
  try {
    const parsed = JSON.parse(localStorage.getItem(WATCHLIST_KEY) || "[]");
    return Array.isArray(parsed) ? normalizeWatchlistItems(parsed) : [];
  } catch {
    return [];
  }
}

function normalizeWatchlistId(value) {
  return String(value || "").trim();
}

function normalizeWatchlistItems(items) {
  const seen = new Set();
  const normalized = [];
  for (const item of items || []) {
    const code = String(item?.code || "").trim();
    const name = String(item?.name || "").trim();
    if (!code || !name || seen.has(code)) {
      continue;
    }
    seen.add(code);
    normalized.push({ code, name, market: item.market || "" });
  }
  return normalized.slice(0, 100);
}

function writeWatchlist(items, options = {}) {
  const normalized = normalizeWatchlistItems(items);
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(normalized));
  if (options.sync !== false) {
    queueRemoteWatchlistSync();
  }
}

function updateWatchlistIdentityDisplay() {
  if (!elements.watchlistIdDisplay) {
    return;
  }
  const currentId = state.watchlistId || normalizeWatchlistId(localStorage.getItem(WATCHLIST_ID_KEY));
  elements.watchlistIdDisplay.textContent = currentId || "로그인 필요";
  elements.watchlistIdDisplay.title = currentId || "";
}

function setWatchlistIdStatus(text, tone = "") {
  if (!elements.watchlistIdStatus) {
    return;
  }
  elements.watchlistIdStatus.textContent = text;
  elements.watchlistIdStatus.className = tone;
  updateWatchlistIdentityDisplay();
}

function setLoginStatus(text, tone = "") {
  if (!elements.loginStatus) {
    return;
  }
  elements.loginStatus.textContent = text;
  elements.loginStatus.className = tone;
}

function setLoginGatePhase(phase) {
  if (!elements.loginGate) {
    return;
  }
  elements.loginGate.dataset.phase = phase;
}

function showLoginGate(message = "2~40자 한글, 영문, 숫자, ., _, - 사용 가능", options = {}) {
  if (!elements.loginGate) {
    return;
  }
  const skipSplash = options.skipSplash ?? state.loginSplashSeen;
  window.clearTimeout(state.loginGateTimer);
  elements.loginGate.hidden = false;
  setLoginStatus(message);
  if (skipSplash) {
    setLoginGatePhase("form");
    window.setTimeout(() => elements.loginInput?.focus(), 50);
    return;
  }
  setLoginGatePhase("splash");
  state.loginSplashSeen = true;
  state.loginGateTimer = window.setTimeout(() => {
    setLoginGatePhase("form");
    window.setTimeout(() => elements.loginInput?.focus(), 40);
  }, LOGIN_SPLASH_DURATION_MS);
}

function hideLoginGate() {
  if (!elements.loginGate) {
    return;
  }
  window.clearTimeout(state.loginGateTimer);
  state.loginGateTimer = null;
  elements.loginGate.hidden = true;
}

async function fetchRemoteWatchlist(shareId) {
  const response = await fetch(`/us/watchlists/${encodeURIComponent(shareId)}`);
  if (!response.ok) {
    throw new Error("watchlist load failed");
  }
  return response.json();
}

async function ensureWriteToken(shareId = state.watchlistId, options = {}) {
  const normalizedId = normalizeWatchlistId(shareId);
  if (!normalizedId) {
    return "";
  }
  if (!options.force && state.writeToken && state.writeTokenShareId === normalizedId) {
    return state.writeToken;
  }
  const response = await fetch(`/session/write-token?share_id=${encodeURIComponent(normalizedId)}&market=us`, {
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw new Error("write token failed");
  }
  const payload = await response.json();
  state.writeToken = String(payload.write_token || "");
  state.writeTokenShareId = normalizedId;
  return state.writeToken;
}

async function saveRemoteWatchlist(items) {
  if (!state.watchlistId) {
    return null;
  }
  const requestPayload = JSON.stringify({ items: normalizeWatchlistItems(items) });
  const requestOnce = async (writeToken) =>
    fetch(`/us/watchlists/${encodeURIComponent(state.watchlistId)}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Write-Token": writeToken,
      },
      body: requestPayload,
    });
  let response = await requestOnce(await ensureWriteToken(state.watchlistId));
  if (response.status === 403) {
    response = await requestOnce(await ensureWriteToken(state.watchlistId, { force: true }));
  }
  if (!response.ok) {
    throw new Error("watchlist save failed");
  }
  return response.json();
}

function queueRemoteWatchlistSync() {
  if (!state.watchlistId) {
    setWatchlistIdStatus("로컬 저장 중");
    return;
  }
  window.clearTimeout(state.watchlistSyncTimer);
  state.watchlistSyncTimer = window.setTimeout(syncLocalWatchlistToRemote, 450);
}

async function syncLocalWatchlistToRemote() {
  if (!state.watchlistId || state.watchlistSyncing) {
    return;
  }
  state.watchlistSyncing = true;
  setWatchlistIdStatus("서버 저장 중");
  try {
    const payload = await saveRemoteWatchlist(readWatchlist());
    setWatchlistIdStatus(`${state.watchlistId} · ${formatNumber(payload.items.length)}개 동기화`, "success");
  } catch {
    setWatchlistIdStatus("동기화 실패 · ID를 확인해주세요", "error");
  } finally {
    state.watchlistSyncing = false;
  }
}

async function applyWatchlistId(shareId, options = {}) {
  const normalizedId = normalizeWatchlistId(shareId);
  if (!normalizedId) {
    state.watchlistId = "";
    state.writeToken = "";
    state.writeTokenShareId = "";
    localStorage.removeItem(WATCHLIST_ID_KEY);
    if (elements.watchlistIdInput) {
      elements.watchlistIdInput.value = "";
    }
    updateWatchlistIdentityDisplay();
    setWatchlistIdStatus("로컬 저장 중");
    return false;
  }
  if (!/^[0-9A-Za-z가-힣_.-]{2,40}$/.test(normalizedId)) {
    setWatchlistIdStatus("2~40자 한글/영문/숫자/._-만 가능", "error");
    return false;
  }
  state.watchlistId = normalizedId;
  state.writeToken = "";
  state.writeTokenShareId = "";
  localStorage.setItem(WATCHLIST_ID_KEY, normalizedId);
  if (elements.watchlistIdInput) {
    elements.watchlistIdInput.value = normalizedId;
  }
  updateWatchlistIdentityDisplay();
  setWatchlistIdStatus("서버 목록 불러오는 중");
  try {
    const localItems = readWatchlist();
    const remotePayload = await fetchRemoteWatchlist(normalizedId);
    const merged = options.merge === false ? normalizeWatchlistItems(remotePayload.items) : normalizeWatchlistItems([...localItems, ...(remotePayload.items || [])]);
    writeWatchlist(merged, { sync: false });
    await saveRemoteWatchlist(merged);
    setWatchlistIdStatus(`${normalizedId} · ${formatNumber(merged.length)}개 동기화`, "success");
    updateWatchButton();
    if (options.reloadCurrentView !== false) {
      if (state.view === "watchlist") {
        loadWatchlist();
      } else if (state.view === "chart") {
        loadWatchCharts();
      }
    }
    return true;
  } catch {
    setWatchlistIdStatus("동기화 실패 · ID를 확인해주세요", "error");
    return false;
  }
}

function logoutWatchlistIdentity() {
  window.clearTimeout(state.watchlistSyncTimer);
  state.watchlistSyncTimer = null;
  state.watchlistSyncing = false;
  state.watchlistId = "";
  state.writeToken = "";
  state.writeTokenShareId = "";
  localStorage.removeItem(WATCHLIST_ID_KEY);
  localStorage.removeItem(WATCHLIST_KEY);
  closeQuoteStream();
  closeWatchlistQuoteStreams();
  closeUsSectorStream();
  closeListQuoteStreams();
  if (elements.watchlistIdInput) {
    elements.watchlistIdInput.value = "";
  }
  if (elements.loginInput) {
    elements.loginInput.value = "";
  }
  updateWatchlistIdentityDisplay();
  updateWatchButton();
  updateRecommendationWatchButtons();
  if (elements.watchlistBody) {
    elements.watchlistBody.innerHTML = '<tr><td colspan="10" class="muted">로그인 후 관심 종목을 불러옵니다.</td></tr>';
  }
  if (elements.watchlistMeta) {
    elements.watchlistMeta.textContent = "로그인 필요";
  }
  if (elements.watchChartList) {
    elements.watchChartList.innerHTML = '<p class="muted">로그인 후 AI 차트 분석을 불러옵니다.</p>';
  }
  setWatchlistIdStatus("로그아웃됨");
  showLoginGate("로그아웃되었습니다. 다시 ID로 시작해주세요.", { skipSplash: true });
}

async function initializeWatchlistIdentity() {
  const savedId = normalizeWatchlistId(localStorage.getItem(WATCHLIST_ID_KEY));
  if (elements.watchlistIdInput) {
    elements.watchlistIdInput.value = savedId;
  }
  updateWatchlistIdentityDisplay();
  if (savedId) {
    if (elements.loginInput) {
      elements.loginInput.value = savedId;
    }
    setLoginStatus("저장된 ID로 불러오는 중");
    const ok = await applyWatchlistId(savedId, { merge: true, reloadCurrentView: false });
    if (ok) {
      hideLoginGate();
    } else {
      showLoginGate("저장된 ID를 불러오지 못했습니다. 다시 입력해주세요.", { skipSplash: true });
    }
  } else {
    setWatchlistIdStatus("로컬 저장 중");
    showLoginGate();
  }
}

function isWatched(code) {
  return readWatchlist().some((item) => item.code === code);
}

function updateWatchButton() {
  if (!state.currentStock) {
    elements.watchToggle.disabled = true;
    elements.watchToggle.classList.remove("active");
    elements.watchToggle.textContent = "관심 추가";
    return;
  }
  const active = isWatched(state.currentStock.code);
  elements.watchToggle.disabled = false;
  elements.watchToggle.classList.toggle("active", active);
  elements.watchToggle.textContent = active ? "관심 해제" : "관심 추가";
}

function toggleWatchCurrent() {
  if (!state.currentStock) {
    return;
  }
  toggleWatchlistItem(state.currentStock);
  updateWatchButton();
  if (state.view === "watchlist") {
    loadWatchlist();
  }
}

function toggleWatchlistItem(stock) {
  if (!stock || !stock.code || !stock.name) {
    return false;
  }
  const items = readWatchlist();
  const exists = items.some((item) => item.code === stock.code);
  const nextItems = exists
    ? items.filter((item) => item.code !== stock.code)
    : [...items, { code: stock.code, name: stock.name, market: stock.market || "" }];
  writeWatchlist(nextItems);
  return !exists;
}

function updateRecommendationWatchButtons() {
  for (const button of document.querySelectorAll(".recommend-watch-button")) {
    const code = button.dataset.code || "";
    const active = isWatched(code);
    button.classList.toggle("active", active);
    button.textContent = active ? "관심 해제" : "관심 추가하기";
  }
}

function updateRecommendationTrackButtons() {
  for (const button of document.querySelectorAll(".recommend-track-button")) {
    const code = button.dataset.code || "";
    const active = isTrackedRecommendation(code);
    button.classList.toggle("active", active);
    button.textContent = active ? "추적 보기" : "추적하기";
  }
}

function updateImpactWatchButtons() {
  for (const button of document.querySelectorAll(".impact-watch-button")) {
    const code = button.dataset.code || "";
    const active = isWatched(code);
    button.classList.toggle("active", active);
    button.textContent = "+";
    button.setAttribute("aria-label", active ? "관심 해제" : "관심 추가");
    button.title = active ? "관심 해제" : "관심 추가";
  }
}

function setMobileMenu(open) {
  if (!elements.mobileMenuToggle || !elements.mobileMenuScrim) {
    return;
  }
  document.body.classList.toggle("mobile-menu-open", open);
  elements.mobileMenuToggle.setAttribute("aria-expanded", open ? "true" : "false");
  elements.mobileMenuToggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
  elements.mobileMenuScrim.hidden = !open;
}

function isMobileDevice() {
  return window.matchMedia("(max-width: 980px)").matches || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
}

function isStandaloneApp() {
  return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

function isIOSDevice() {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function updateHomeInstallButton() {
  if (!elements.homeInstallButton) {
    return;
  }
  elements.homeInstallButton.hidden = !isMobileDevice() || isStandaloneApp();
}

function renderInstallSteps() {
  if (!elements.installSteps) {
    return;
  }
  const steps = isIOSDevice()
    ? ["Safari 하단 또는 상단의 공유 버튼을 누릅니다.", "목록에서 홈 화면에 추가를 선택합니다.", "추가를 누르면 비밀노트 아이콘이 홈 화면에 생깁니다."]
    : ["Chrome에서 이 페이지를 연 상태로 우측 상단 메뉴를 누릅니다.", "앱 설치 또는 홈 화면에 추가를 선택합니다.", "추가를 누르면 비밀노트 아이콘이 홈 화면에 생깁니다."];
  elements.installSteps.innerHTML = "";
  for (const step of steps) {
    elements.installSteps.appendChild(el("li", "", step));
  }
  if (elements.installSheetSubtitle) {
    elements.installSheetSubtitle.textContent = isIOSDevice()
      ? "iPhone은 브라우저 보안 정책상 안내에 따라 직접 추가해야 합니다."
      : "설치 버튼이 바로 뜨지 않으면 아래 순서로 홈 화면에 추가할 수 있습니다.";
  }
}

function showInstallSheet() {
  renderInstallSteps();
  if (elements.installSheet) {
    elements.installSheet.hidden = false;
  }
}

function closeInstallSheet() {
  if (elements.installSheet) {
    elements.installSheet.hidden = true;
  }
}

function setFlowLoading(open) {
  if (!elements.flowLoadingModal) {
    return;
  }
  elements.flowLoadingModal.hidden = !open;
  document.body.classList.toggle("modal-open", open);
}

async function handleHomeInstall() {
  if (state.deferredInstallPrompt) {
    const promptEvent = state.deferredInstallPrompt;
    state.deferredInstallPrompt = null;
    promptEvent.prompt();
    await promptEvent.userChoice.catch(() => null);
    updateHomeInstallButton();
    return;
  }
  showInstallSheet();
}

function registerDashboardServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  navigator.serviceWorker.register("/nasdaq-sw.js", { scope: "/nasdaq" }).catch(() => undefined);
}

function pageEntryTtlMs(view) {
  const phase = usRecommendationMarketPhase();
  const marketIsMoving = phase === "regular" || phase === "premarket" || phase === "afterhours";
  switch (view) {
    case "stock":
      return marketIsMoving ? 15_000 : PAGE_ENTRY_MINUTE_MS;
    case "watchlist":
      return marketIsMoving ? 15_000 : PAGE_ENTRY_MINUTE_MS;
    case "market":
      return marketIsMoving ? 15_000 : 2 * PAGE_ENTRY_MINUTE_MS;
    case "recommend":
      return marketIsMoving ? 2 * PAGE_ENTRY_MINUTE_MS : 10 * PAGE_ENTRY_MINUTE_MS;
    case "recommend-history":
      return marketIsMoving ? 30_000 : 2 * PAGE_ENTRY_MINUTE_MS;
    case "trend":
      return PAGE_ENTRY_MINUTE_MS;
    case "trend-past":
      return 10 * PAGE_ENTRY_MINUTE_MS;
    case "trend-impact":
      return 5 * PAGE_ENTRY_MINUTE_MS;
    case "chart":
      return 2 * PAGE_ENTRY_MINUTE_MS;
    case "chart-history":
      return 5 * PAGE_ENTRY_MINUTE_MS;
    default:
      return PAGE_ENTRY_MINUTE_MS;
  }
}

function pageEntryRefreshOptions(view, key = "") {
  const ttlMs = pageEntryTtlMs(view);
  const cacheKey = `${view}:${state.watchlistId || "local"}:${key}`;
  const now = Date.now();
  const lastRefreshAt = state.pageEntryRefreshAt.get(cacheKey) || 0;
  const force = now - lastRefreshAt >= ttlMs;
  if (force) {
    state.pageEntryRefreshAt.set(cacheKey, now);
  }
  return { force, ttlMs };
}

function navSectionForView(view) {
  return VIEW_NAV_SECTION[view] || "stock";
}

function updateSideNavState() {
  const activeView = state.view === "chart-history" ? "chart" : state.view;
  for (const item of elements.sideItems) {
    const active = item.dataset.view === activeView;
    item.classList.toggle("active", active);
  }
  for (const group of document.querySelectorAll(".side-menu-group")) {
    group.classList.toggle("has-active", Boolean(group.querySelector(".side-menu-item.active")));
  }
}

function setView(view) {
  state.view = view;
  setFlowLoading(false);
  hideSuggestions();
  updateMobilePageTitle(view);
  if (view !== "stock" && state.currentOverviewDetail) {
    closeOverviewDetail();
  }
  if (view !== "stock") {
    closeQuoteStream();
  }
  if (view !== "watchlist") {
    closeWatchlistQuoteStreams();
  }
  if (view !== "market") {
    closeMarketQuoteStreams();
  }
  if (!["watchlist", "recommend"].includes(view)) {
    closeUsSectorStream();
  }
  if (!["market", "recommend"].includes(view)) {
    closeListQuoteStreams();
  }
  if (view !== "recommend") {
    window.clearTimeout(state.recommendationCooldownTimer);
    state.recommendationCooldownTimer = null;
  }
  elements.stockView.hidden = view !== "stock";
  elements.watchlistView.hidden = view !== "watchlist";
  elements.recommendView.hidden = view !== "recommend";
  elements.recommendHistoryView.hidden = view !== "recommend-history";
  elements.trendView.hidden = !["trend", "trend-past", "trend-impact"].includes(view);
  elements.chartView.hidden = view !== "chart";
  elements.chartHistoryView.hidden = view !== "chart-history";
  elements.marketView.hidden = view !== "market";
  updateSideNavState();
  renderSectionShell();
  if (view === "stock") {
  } else if (view === "market") {
    history.replaceState(null, "", "/nasdaq?view=market");
    loadMarketRankings(pageEntryRefreshOptions("market", currentMarketFilter()));
  } else if (view === "watchlist") {
    history.replaceState(null, "", "/nasdaq?view=watchlist");
    loadWatchlist(pageEntryRefreshOptions("watchlist"));
  } else if (view === "recommend") {
    history.replaceState(null, "", "/nasdaq?view=recommend");
    updateRecommendationButtonState();
    const entryOptions = pageEntryRefreshOptions("recommend");
    refreshUsSectorMoves(entryOptions);
    if (state.currentRecommendations && !entryOptions.force) {
      renderRecommendations(state.currentRecommendations, { save: false });
    } else {
      loadRecommendations({ auto: true, force: entryOptions.force });
    }
    connectUsSectorStream();
  } else if (view === "recommend-history") {
    history.replaceState(null, "", "/nasdaq?view=recommend-history");
    loadRecommendationHistory(pageEntryRefreshOptions("recommend-history"));
  } else if (view === "trend") {
    history.replaceState(null, "", "/nasdaq?view=trend");
    loadTrends("events", pageEntryRefreshOptions("trend", "events"));
  } else if (view === "trend-past") {
    history.replaceState(null, "", "/nasdaq?view=trend-past");
    loadTrends("past", pageEntryRefreshOptions("trend-past", "past"));
  } else if (view === "trend-impact") {
    history.replaceState(null, "", "/nasdaq?view=trend-impact");
    loadMarketImpactAnalysis(pageEntryRefreshOptions("trend-impact"));
  } else if (view === "chart") {
    history.replaceState(null, "", "/nasdaq?view=chart");
    loadWatchCharts(pageEntryRefreshOptions("chart"));
  } else if (view === "chart-history") {
    history.replaceState(null, "", "/nasdaq?view=chart-history");
    renderChartSnapshots();
  }
  updateResponsiveModeBadges();
  sendPresencePage();
}

function renderEvents(listNode, items) {
  listNode.innerHTML = "";
  if (!items || items.length === 0) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "-";
    listNode.appendChild(empty);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    const head = document.createElement("div");
    head.className = "event-item-head";
    const anchor = document.createElement(item.url ? "a" : "span");
    anchor.textContent = item.title;
    if (item.url) {
      anchor.href = item.url;
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
    }
    head.appendChild(anchor);
    if (item.sentiment_label) {
      const badge = document.createElement("span");
      badge.className = `news-sentiment-badge ${item.sentiment || "neutral"}`;
      badge.textContent = item.sentiment_label;
      badge.title = item.sentiment_reason || "";
      head.appendChild(badge);
    }
    const time = document.createElement("time");
    const reason = item.sentiment_reason && item.sentiment_reason !== "명확한 방향성 단어 없음"
      ? ` · ${item.sentiment_reason}`
      : "";
    time.textContent = `${formatDate(item.published_at)}${reason}`;
    li.append(head, time);
    listNode.appendChild(li);
  }
}

function rankingMetricLabel(category, item) {
  if (category === "surge") return formatPercent(item.change_rate);
  if (category === "trading_value") return formatMoney(item.trading_value);
  if (category === "momentum") return formatPercent(item.metric_value);
  if (category === "valuation") return item.per ? `PER ${formatMultiple(item.per)}` : `시총대비 거래 ${formatPercent(item.metric_value)}`;
  if (category === "sentiment") return formatPercent(item.sentiment_score);
  return item.metric_value ?? "-";
}

function interpretValuation(dashboard) {
  const valuation = dashboard.valuation || {};
  const per = toNumber(valuation.per);
  const pbr = toNumber(valuation.pbr);
  const estimatedPer = toNumber(valuation.estimated_per);
  const industryPer = toNumber(valuation.industry_per);
  const perZ = toNumber(valuation.per_zscore);
  const pbrZ = toNumber(valuation.pbr_zscore);
  const zScores = [perZ, pbrZ].filter((value) => value !== null);
  const avgZ = zScores.length ? zScores.reduce((sum, value) => sum + value, 0) / zScores.length : null;

  if (avgZ !== null && avgZ >= 1.5) {
    return { label: "과거 대비 부담", tone: "negative" };
  }
  if (avgZ !== null && avgZ <= -1) {
    return { label: "과거 대비 저평가", tone: "positive" };
  }
  if (per !== null && industryPer !== null && industryPer > 0 && per >= industryPer * 1.25) {
    return { label: "섹터 대비 고PER", tone: "negative" };
  }
  if (per !== null && industryPer !== null && industryPer > 0 && per <= industryPer * 0.8) {
    return { label: "섹터 대비 저PER", tone: "positive" };
  }
  if (estimatedPer !== null && per !== null && estimatedPer > 0 && estimatedPer <= per * 0.85) {
    return { label: "이익개선 반영", tone: "positive" };
  }
  if ((per !== null && per <= 0) || (pbr !== null && pbr <= 0)) {
    return { label: "이익/자본 확인", tone: "muted" };
  }
  return { label: "밸류 중립", tone: "muted" };
}

function interpretMacro(dashboard) {
  const macro = dashboard.macro_sensitivity || {};
  const rate = toNumber(macro.interest_rate);
  const fx = toNumber(macro.fx ?? macro.fx_usdkrw);
  const commodity = toNumber(macro.commodity);
  const exports = toNumber(macro.export ?? macro.exports);
  const positives = [];
  const risks = [];

  if (rate !== null) {
    if (rate <= -20) risks.push("금리 부담");
    if (rate >= 20) positives.push("금리 우호");
  }
  if (fx !== null) {
    if (fx >= 20) positives.push("달러 우호");
    if (fx <= -20) risks.push("달러 부담");
  }
  if (commodity !== null) {
    if (commodity >= 20) positives.push("원자재 우호");
    if (commodity <= -20) risks.push("원자재 부담");
  }
  if (exports !== null) {
    if (exports >= 20) positives.push("글로벌 수요 우호");
    if (exports <= -20) risks.push("글로벌 수요 둔화");
  }

  if (risks.length && positives.length) {
    return { label: `${positives[0]} / ${risks[0]}`, tone: "muted" };
  }
  if (positives.length) {
    return { label: positives[0], tone: "positive" };
  }
  if (risks.length) {
    return { label: risks[0], tone: "negative" };
  }
  return { label: "거시 중립", tone: "muted" };
}

function createCell(value, className = "") {
  const cell = value instanceof HTMLElement ? value : document.createElement("td");
  if (!(value instanceof HTMLElement)) {
    cell.textContent = value;
  }
  if (className) {
    cell.className = className;
  }
  return cell;
}

function createWatchMetric(label, value, field = "", toneValue = null) {
  const item = document.createElement("div");
  const title = document.createElement("span");
  title.textContent = label;
  const strong = document.createElement("strong");
  strong.textContent = value;
  if (field) {
    strong.dataset.field = field;
  }
  if (toneValue !== null && toneValue !== undefined) {
    setTone(strong, toneValue);
  }
  item.append(title, strong);
  return item;
}

function createWatchInsight(label, value, tone = "muted") {
  const item = document.createElement("article");
  item.className = `watch-insight-card ${tone}`;
  item.append(el("span", "", label), el("strong", "", value));
  return item;
}

function marketFilterLabel(value) {
  if (value === "ALL") return "전체 미장";
  if (value === "SP500") return "S&P 500";
  if (value) return value;
  return "전체 미장";
}

function setMarketLeaderboardMode(enabled) {
  elements.rankingBody.closest(".ranking-table")?.classList.toggle("market-leaderboard-table", enabled);
}

function renderRankingMessage(text) {
  elements.rankingBody.innerHTML = "";
  const row = document.createElement("tr");
  row.className = "ranking-message-row";
  row.innerHTML = `<td colspan="7" class="muted ranking-message-cell">${text}</td>`;
  elements.rankingBody.appendChild(row);
}

function createMarketLeaderboardCard(item) {
  const card = document.createElement("article");
  card.className = "market-leaderboard-card";
  card.dataset.liveCode = item.code;

  const main = document.createElement("section");
  main.className = "market-leaderboard-main";

  const quoteBlock = document.createElement("div");
  quoteBlock.className = "market-leaderboard-quote-block";
  const rank = document.createElement("span");
  rank.className = "market-rank-badge";
  rank.textContent = String(item.rank || "-");
  const price = document.createElement("strong");
  price.className = "market-leaderboard-price";
  price.dataset.liveField = "price";
  price.textContent = formatPrice(item.price);
  quoteBlock.append(rank, price);

  const summary = document.createElement("div");
  summary.className = "market-leaderboard-summary";
  const name = document.createElement("a");
  name.className = "market-leaderboard-name";
  name.href = viewStockUrl(item);
  name.append(el("strong", "", item.name), el("span", "", `${item.code} · ${item.market}`));
  const change = document.createElement("strong");
  change.className = "market-leaderboard-change";
  change.dataset.liveField = "change_rate";
  change.textContent = formatPercent(item.change_rate);
  setTone(change, item.change_rate);
  summary.append(name, change);
  main.append(quoteBlock, summary);

  const strip = document.createElement("section");
  strip.className = "quote-strip market-leaderboard-strip";
  strip.append(
    createWatchMetric("거래대금", formatMoney(item.trading_value), "trading_value"),
    createWatchMetric("1개월", formatPercent(item.one_month_return), "", item.one_month_return),
    createWatchMetric("3개월", formatPercent(item.three_month_return), "", item.three_month_return)
  );

  card.append(main, strip);
  return card;
}

function renderMarketSurgeLeaderboard(items) {
  elements.rankingBody.innerHTML = "";
  const row = document.createElement("tr");
  row.className = "market-leaderboard-row";
  const cell = document.createElement("td");
  cell.colSpan = 7;
  const shell = document.createElement("section");
  shell.className = "market-leaderboard-shell";
  const board = document.createElement("div");
  board.className = "market-leaderboard";
  for (const item of state.marketLeaderboardItems) {
    board.appendChild(createMarketLeaderboardCard(item));
  }
  shell.appendChild(board);
  cell.appendChild(shell);
  row.appendChild(cell);
  elements.rankingBody.appendChild(row);
}

function startMarketSurgeLeaderboard(payload) {
  closeMarketQuoteStreams();
  state.marketLeaderboardItems = (payload.items || []).slice(0, 20).map((item, index) => ({
    ...item,
    rank: index + 1,
    metric_value: item.metric_value ?? item.change_rate,
  }));
  sortMarketLeaderboardItems();
  renderMarketSurgeLeaderboard();
  for (const item of state.marketLeaderboardItems) {
    connectMarketQuoteStream(item.code);
  }
}

function renderRankings(payload) {
  state.currentMarketPayload = payload;
  const category = payload.category;
  const filters = getViewFilters("market");
  const items = (payload.items || []).filter((item) => matchesKeyword(filters.keyword, item.name, item.code));
  closeListQuoteStreams();
  elements.marketMeta.textContent = `${marketFilterLabel(payload.market)} · ${formatDate(payload.as_of)} · ${formatNumber(items.length)}개`;
  elements.marketMeta.hidden = true;
  syncSectionShellMeta();
  setMarketLeaderboardMode(category === "surge");
  if (!items.length) {
    closeMarketQuoteStreams();
    renderRankingMessage("데이터 없음");
    return;
  }
  if (category === "surge") {
    startMarketSurgeLeaderboard({ ...payload, items });
    return;
  }
  closeMarketQuoteStreams();
  elements.rankingBody.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("tr");
    row.dataset.liveCode = item.code;
    const metric = rankingMetricLabel(category, item);
    row.innerHTML = `
      <td data-label="순위">${item.rank}</td>
      <td data-label="종목">
        <a class="rank-name" href="${viewStockUrl(item)}">
          <strong>${item.name}</strong>
          <span>${item.code} · ${item.market}</span>
        </a>
      </td>
      <td data-label="현재가" data-live-field="price">${formatPrice(item.price)}</td>
      <td data-label="핵심값">${metric}</td>
      <td data-label="1개월" class="${Number(item.one_month_return) > 0 ? "positive" : "negative"}">${formatPercent(item.one_month_return)}</td>
      <td data-label="3개월" class="${Number(item.three_month_return) > 0 ? "positive" : "negative"}">${formatPercent(item.three_month_return)}</td>
      <td data-label="거래대금" data-live-field="trading_value">${formatMoney(item.trading_value)}</td>
    `;
    elements.rankingBody.appendChild(row);
    connectListQuoteStream(item.code);
  }
}

function currentMarketFilter() {
  return elements.marketTabs.find((tab) => tab.classList.contains("active"))?.dataset.marketFilter || "ALL";
}

function setMarketFilter(market) {
  const normalized = ["NASDAQ", "SP500"].includes(market) ? market : "ALL";
  for (const tab of elements.marketTabs) {
    const active = tab.dataset.marketFilter === normalized;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  }
  return normalized;
}

function marketRankingKey(category, market) {
  return `${market}:surge`;
}

function marketCategoryLabel(category) {
  return elements.rankTabs.find((tab) => tab.dataset.category === category)?.textContent?.trim() || category;
}

function requestMarketRanking(category, market, options = {}) {
  const normalizedCategory = "surge";
  const key = marketRankingKey(normalizedCategory, market);
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? UI_CACHE_TTL_MS;
  const cached = state.marketRankingCache.get(key);
  if (!force && cached?.payload && Date.now() - (cached.savedAt || 0) <= ttlMs) {
    return Promise.resolve(cached.payload);
  }
  if (!force && cached?.promise) {
    return cached.promise;
  }
  const params = new URLSearchParams({
    category: normalizedCategory,
    limit: "20",
    market,
    refresh: "1",
  });
  const fallbackParams = new URLSearchParams(params);
  fallbackParams.delete("refresh");
  const primaryUrl = `/us/market/rankings?${params.toString()}`;
  const fallbackUrl = `/us/market/rankings?${fallbackParams.toString()}`;
  const fallbackRequest = () => fetchJsonCached(fallbackUrl, { force: true, ttlMs: 0 });
  const promise = fetchJsonCached(primaryUrl, { force, ttlMs: force ? 0 : ttlMs })
    .then((payload) => {
      if (!payload.items || payload.items.length === 0) {
        return fallbackRequest();
      }
      return payload;
    })
    .catch(() => fallbackRequest())
    .then((payload) => {
      state.marketRankingCache.set(key, { payload, savedAt: Date.now() });
      return payload;
    })
    .catch((error) => {
      state.marketRankingCache.delete(key);
      throw error;
    });
  state.marketRankingCache.set(key, { promise });
  return promise;
}

async function prefetchMarketRankings(market = currentMarketFilter()) {
  state.marketPrefetchKey = `${market}:surge:${Date.now()}`;
}

async function loadMarketRankings(options = {}) {
  const category = "surge";
  state.rankingCategory = category;
  if (elements.rankCategorySelect) {
    elements.rankCategorySelect.value = category;
  }
  const market = options.market || currentMarketFilter();
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("market");
  setMarketLeaderboardMode(true);
  const key = marketRankingKey(category, market);
  const cached = state.marketRankingCache.get(key);
  if (!force && cached?.payload && Date.now() - (cached.savedAt || 0) <= ttlMs) {
    renderRankings(cached.payload);
    return;
  }
  closeMarketQuoteStreams();
  elements.marketMeta.textContent = `${marketFilterLabel(market)} · ${marketCategoryLabel(category)} 준비 중`;
  elements.marketMeta.hidden = true;
  renderRankingMessage("불러오는 중");
  renderSectionShell();
  try {
    const payload = await requestMarketRanking(category, market, { force, ttlMs });
    if (state.view === "market" && state.rankingCategory === category && currentMarketFilter() === market) {
      renderRankings(payload);
    }
  } catch {
    if (state.view === "market" && state.rankingCategory === category && currentMarketFilter() === market) {
      elements.marketMeta.textContent = "데이터 없음";
      elements.marketMeta.hidden = true;
      renderRankingMessage("데이터 없음");
      renderSectionShell();
    }
  }
}

function appendWatchRow(item, dashboard) {
  const card = document.createElement("article");
  card.className = "watch-stock-card";
  card.dataset.code = item.code;
  card.dataset.watchCard = "true";
  card.watchDashboard = dashboard;
  card.watchItem = item;
  card.usSectorMoves = state.usSectorMoves;

  const header = document.createElement("div");
  header.className = "watch-stock-head";
  const link = document.createElement("a");
  link.className = "watch-stock-name";
  link.href = viewStockUrl(item);
  link.append(el("strong", "", item.name), el("span", "", `${item.code} · ${item.market || dashboard.market}`));
  const removeButton = document.createElement("button");
  removeButton.className = "remove-watch";
  removeButton.type = "button";
  removeButton.textContent = "관심 해제";
  removeButton.dataset.code = item.code;
  header.append(link, removeButton);

  const valuationView = interpretValuation(dashboard);
  const macroView = interpretMacro(dashboard);

  const priceRow = document.createElement("div");
  priceRow.className = "watch-stock-price-row";
  const priceBlock = document.createElement("div");
  const price = document.createElement("strong");
  price.className = "watch-stock-price";
  price.dataset.field = "price";
  price.textContent = formatPrice(dashboard.quote.price);
  priceBlock.appendChild(price);
  const change = document.createElement("strong");
  change.className = "watch-stock-change";
  change.dataset.field = "change_rate";
  change.textContent = formatPercent(dashboard.quote.change_rate);
  setTone(change, dashboard.quote.change_rate);
  priceRow.append(priceBlock, change);

  const metrics = document.createElement("section");
  metrics.className = "quote-strip watch-quote-strip";
  metrics.append(
    createWatchMetric("거래대금", formatMoney(dashboard.quote.trading_value), "trading_value"),
    createWatchMetric("1개월", formatPercent(dashboard.momentum.one_month_return), "one_month", dashboard.momentum.one_month_return),
    createWatchMetric("3개월", formatPercent(dashboard.momentum.three_month_return), "three_month", dashboard.momentum.three_month_return),
    createWatchMetric("뉴스", formatPercent(dashboard.sentiment.score), "sentiment", dashboard.sentiment.score)
  );

  const preOpenPoint = renderWatchPreOpenPoint(card, dashboard, null, item, state.usSectorMoves);
  const insights = document.createElement("section");
  insights.className = "watch-insight-grid";
  insights.append(
    createWatchInsight("밸류 판단", valuationView.label, valuationView.tone),
    createWatchInsight("거시 판단", macroView.label, macroView.tone)
  );

  card.append(header, preOpenPoint, priceRow, metrics, insights);
  elements.watchlistBody.appendChild(card);
}

function renderWatchlistTable(results = state.watchlistRows) {
  closeWatchlistQuoteStreams();
  const filtered = (results || []).filter((result) => result.dashboard);
  elements.watchlistMeta.textContent = `${filtered.length}개 종목`;
  syncSectionShellMeta();
  elements.watchlistBody.innerHTML = "";
  if (!filtered.length) {
    renderWatchlistMessage("관심 종목 없음");
    return;
  }
  for (const result of filtered) {
    appendWatchRow(result.item, result.dashboard);
    connectWatchlistQuoteStream(result.item.code);
  }
}

async function loadWatchlist(options = {}) {
  const force = options.force !== false;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("watchlist");
  closeWatchlistQuoteStreams();
  closeUsSectorStream();
  const items = readWatchlist();
  state.watchlistRows = [];
  elements.watchlistMeta.textContent = `${items.length}개 종목`;
  syncSectionShellMeta();
  elements.watchlistBody.innerHTML = "";
  showWatchlistLoadingOverlay();
  if (!items.length) {
    clearWatchlistLoadingOverlay();
    renderWatchlistMessage("관심 종목 없음");
    renderSectionShell();
    return;
  }
  const sectorMovesPromise = refreshUsSectorMoves({ force: true }).catch(() => null);
  const results = await Promise.all(
    items.map(async (item) => {
      try {
        const url = `/us/stocks/${encodeURIComponent(item.code)}/dashboard?refresh=1`;
        return { item, dashboard: await fetchJsonCached(url, { force, ttlMs: force ? 0 : ttlMs }) };
      } catch {
        return { item, dashboard: null };
      }
    })
  );
  await sectorMovesPromise;
  clearWatchlistLoadingOverlay();
  state.watchlistRows = results.filter((result) => result.dashboard);
  renderWatchlistTable(state.watchlistRows);
  connectUsSectorStream();
}

function average(values) {
  const numbers = values.map(toNumber).filter((value) => value !== null);
  if (!numbers.length) {
    return null;
  }
  return numbers.reduce((sum, value) => sum + value, 0) / numbers.length;
}

function maxValue(values) {
  const numbers = values.map(toNumber).filter((value) => value !== null);
  return numbers.length ? Math.max(...numbers) : null;
}

function minValue(values) {
  const numbers = values.map(toNumber).filter((value) => value !== null);
  return numbers.length ? Math.min(...numbers) : null;
}

function movingAverageSeries(prices, window) {
  return prices.map((_, index) => {
    if (index + 1 < window) {
      return null;
    }
    return average(prices.slice(index + 1 - window, index + 1).map((row) => row.close));
  });
}

function standardDeviation(values) {
  const numbers = values.map(toNumber).filter((value) => value !== null);
  if (!numbers.length) {
    return null;
  }
  const mean = average(numbers);
  const variance = average(numbers.map((value) => (value - mean) ** 2));
  return Math.sqrt(variance);
}

function rsiValue(closes, window = 14) {
  const numbers = closes.map(toNumber).filter((value) => value !== null);
  if (numbers.length <= window) {
    return null;
  }
  let gains = 0;
  let losses = 0;
  for (let index = numbers.length - window; index < numbers.length; index += 1) {
    const change = numbers[index] - numbers[index - 1];
    if (change >= 0) {
      gains += change;
    } else {
      losses += Math.abs(change);
    }
  }
  if (losses === 0) {
    return 100;
  }
  const rs = gains / losses;
  return 100 - 100 / (1 + rs);
}

function emaSeries(values, window) {
  const result = [];
  const multiplier = 2 / (window + 1);
  let ema = null;
  for (const rawValue of values) {
    const value = toNumber(rawValue);
    if (value === null) {
      result.push(null);
      continue;
    }
    ema = ema === null ? value : value * multiplier + ema * (1 - multiplier);
    result.push(ema);
  }
  return result;
}

function macdValue(closes) {
  const ema12 = emaSeries(closes, 12);
  const ema26 = emaSeries(closes, 26);
  const macd = closes.map((_, index) => {
    if (ema12[index] === null || ema26[index] === null) {
      return null;
    }
    return ema12[index] - ema26[index];
  });
  const signal = emaSeries(macd, 9);
  const latestMacd = macd.at(-1);
  const latestSignal = signal.at(-1);
  return {
    macd: latestMacd,
    signal: latestSignal,
    histogram: latestMacd !== null && latestSignal !== null ? latestMacd - latestSignal : null,
  };
}

function atrPercent(rows, window = 14) {
  if (rows.length <= window) {
    return null;
  }
  const ranges = [];
  for (let index = rows.length - window; index < rows.length; index += 1) {
    const current = rows[index];
    const previous = rows[index - 1];
    const high = toNumber(current.high);
    const low = toNumber(current.low);
    const previousClose = toNumber(previous.close);
    if (high === null || low === null || previousClose === null) {
      continue;
    }
    ranges.push(Math.max(high - low, Math.abs(high - previousClose), Math.abs(low - previousClose)));
  }
  const atr = average(ranges);
  const latestClose = toNumber(rows.at(-1)?.close);
  return atr && latestClose ? (atr / latestClose) * 100 : null;
}

function bollingerBands(closes, window = 20) {
  const slice = closes.slice(-window);
  const middle = average(slice);
  const deviation = standardDeviation(slice);
  if (middle === null || deviation === null) {
    return { upper: null, middle: null, lower: null };
  }
  return {
    upper: middle + deviation * 2,
    middle,
    lower: middle - deviation * 2,
  };
}

function computeWatchChart(prices) {
  const ordered = (prices || [])
    .filter((row) => row.close)
    .slice()
    .sort((a, b) => String(a.trade_date || "").localeCompare(String(b.trade_date || "")));
  const latest = ordered.at(-1) || {};
  const closes = ordered.map((row) => row.close);
  const volumes = ordered.map((row) => row.volume);
  const ma5 = average(closes.slice(-5));
  const ma20 = average(closes.slice(-20));
  const ma60 = average(closes.slice(-60));
  const ma120 = average(closes.slice(-120));
  const ma5Prev = average(closes.slice(-10, -5));
  const ma20Prev = average(closes.slice(-30, -10));
  const ma60Prev = average(closes.slice(-90, -30));
  const recentHigh = maxValue(ordered.slice(-20).map((row) => row.high || row.close));
  const priorHigh = maxValue(ordered.slice(-40, -20).map((row) => row.high || row.close));
  const recentLow = minValue(ordered.slice(-20).map((row) => row.low || row.close));
  const priorLow = minValue(ordered.slice(-40, -20).map((row) => row.low || row.close));
  const volume20 = average(volumes.slice(-20));
  const volume60 = average(volumes.slice(-60));
  const volumeRatio = volume20 && volume60 ? volume20 / volume60 : null;
  const price = toNumber(latest.close);
  const distance20 = price && ma20 ? ((price - ma20) / ma20) * 100 : null;
  const distance120 = price && ma120 ? ((price - ma120) / ma120) * 100 : null;
  const aboveMa20 = price && ma20 ? price >= ma20 : false;
  const aboveMa60 = price && ma60 ? price >= ma60 : false;
  const aboveMa120 = price && ma120 ? price >= ma120 : false;
  const ma5Up = ma5 && ma5Prev ? ma5 > ma5Prev : false;
  const ma20Up = ma20 && ma20Prev ? ma20 > ma20Prev : false;
  const ma60Up = ma60 && ma60Prev ? ma60 > ma60Prev : false;
  const rsi = rsiValue(closes, 14);
  const macd = macdValue(closes);
  const atr = atrPercent(ordered);
  const bands = bollingerBands(closes);
  const bandPosition = price && bands.upper && bands.lower ? ((price - bands.lower) / (bands.upper - bands.lower)) * 100 : null;
  const higherHighLow = recentHigh && priorHigh && recentLow && priorLow ? recentHigh > priorHigh && recentLow > priorLow : false;
  const overheat = (distance20 !== null && distance20 > 22) || (rsi !== null && rsi >= 75) || (bandPosition !== null && bandPosition >= 105);
  const bullishCandle = latest.open && latest.close ? latest.close >= latest.open : false;
  let score = 50;
  if (ma5Up) score += 4;
  if (aboveMa20) score += 10;
  if (aboveMa60) score += 10;
  if (aboveMa120) score += 6;
  if (ma20Up) score += 10;
  if (ma60Up) score += 8;
  if (higherHighLow) score += 10;
  if (volumeRatio && volumeRatio > 1.25 && bullishCandle) score += 8;
  if (macd.histogram !== null && macd.histogram > 0) score += 5;
  if (rsi !== null && rsi >= 45 && rsi <= 68) score += 5;
  if (overheat) score -= 12;
  if (!aboveMa20) score -= 10;
  if (!aboveMa60) score -= 8;
  score = Math.max(0, Math.min(100, Math.round(score)));
  const stance = score >= 78 ? "추세 유지 관심" : score >= 64 ? "분할 관찰" : score >= 48 ? "기준 확인" : "관망";
  const checklist = [
    { label: "큰 추세가 우상향", ok: ma60Up || ma20Up, note: `20일선 ${ma20Up ? "상승" : "둔화"} · 60일선 ${ma60Up ? "상승" : "둔화"}` },
    { label: "주가가 주요 이평선 위", ok: aboveMa20 && aboveMa60, note: `20일 ${aboveMa20 ? "위" : "아래"} · 60일 ${aboveMa60 ? "위" : "아래"} · 120일 ${aboveMa120 ? "위" : "아래"}` },
    { label: "고점과 저점이 높아짐", ok: higherHighLow, note: higherHighLow ? "상승 추세 구조" : "추세 구조 확인 필요" },
    { label: "거래량 증가 구간", ok: volumeRatio !== null && volumeRatio >= 1.15, note: `20일/60일 ${formatRatio(volumeRatio)}` },
    { label: "과열 추격매수 아님", ok: !overheat, note: `20일 이격 ${formatPercent(distance20)} · RSI ${formatNumber(rsi)}` },
    { label: "손절 기준 숫자화 가능", ok: Boolean(recentLow), note: `최근 지지 ${formatNumber(recentLow)}` },
  ];
  const notes = [
    aboveMa20 && aboveMa60 ? "가격이 단기/중기 평균선 위에 있어 흐름은 살아 있습니다." : "주요 평균선 회복 여부를 먼저 확인해야 합니다.",
    higherHighLow ? "최근 고점과 저점이 함께 올라가는 구조입니다." : "고점 또는 저점 구조가 아직 명확하지 않습니다.",
    overheat ? "20일선 이격이 커서 추격매수 부담이 있습니다." : "이격 부담은 과도하지 않은 편입니다.",
    macd.histogram !== null && macd.histogram > 0 ? "MACD가 양의 모멘텀을 가리킵니다." : "MACD 모멘텀은 아직 강한 확인 신호가 아닙니다.",
  ];
  return {
    prices: ordered,
    latest,
    ma5,
    ma20,
    ma60,
    ma120,
    rsi,
    macd,
    atr,
    bands,
    bandPosition,
    score,
    stance,
    support: recentLow,
    resistance: recentHigh,
    distance20,
    distance120,
    volumeRatio,
    checklist,
    notes,
  };
}

function yScale(value, min, max, top, height) {
  if (max === min) {
    return top + height / 2;
  }
  return top + ((max - value) / (max - min)) * height;
}

function pointsForSeries(rows, series, min, max, top, height, left, width) {
  const step = rows.length > 1 ? width / (rows.length - 1) : width;
  return series
    .map((value, index) => {
      if (!value) {
        return "";
      }
      return `${left + index * step},${yScale(value, min, max, top, height)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function createWatchChartSvg(analysis) {
  const rows = analysis.prices.slice(-90);
  if (!rows.length) {
    return el("div", "empty-chart", "차트 데이터 없음");
  }
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 760 360");
  svg.setAttribute("role", "img");
  svg.classList.add("watch-chart-svg");
  const left = 46;
  const top = 18;
  const width = 680;
  const priceHeight = 230;
  const volumeTop = 272;
  const volumeHeight = 56;
  const highs = rows.map((row) => row.high || row.close);
  const lows = rows.map((row) => row.low || row.close);
  const baseMin = minValue(lows);
  const baseMax = maxValue(highs);
  const min = Math.min(baseMin * 0.97, analysis.bands.lower || baseMin);
  const max = Math.max(baseMax * 1.03, analysis.bands.upper || baseMax);
  const maxVolume = maxValue(rows.map((row) => row.volume)) || 1;
  const ma5 = movingAverageSeries(analysis.prices, 5).slice(-90);
  const ma20 = movingAverageSeries(analysis.prices, 20).slice(-90);
  const ma60 = movingAverageSeries(analysis.prices, 60).slice(-90);
  const ma120 = movingAverageSeries(analysis.prices, 120).slice(-90);
  const bandUpper = analysis.prices.map((_, index) => {
    if (index + 1 < 20) return null;
    const slice = analysis.prices.slice(index + 1 - 20, index + 1).map((row) => row.close);
    const middle = average(slice);
    const deviation = standardDeviation(slice);
    return middle !== null && deviation !== null ? middle + deviation * 2 : null;
  }).slice(-90);
  const bandLower = analysis.prices.map((_, index) => {
    if (index + 1 < 20) return null;
    const slice = analysis.prices.slice(index + 1 - 20, index + 1).map((row) => row.close);
    const middle = average(slice);
    const deviation = standardDeviation(slice);
    return middle !== null && deviation !== null ? middle - deviation * 2 : null;
  }).slice(-90);
  const step = rows.length > 1 ? width / (rows.length - 1) : width;
  const candleWidth = Math.max(3, Math.min(8, step * 0.55));

  for (let i = 0; i < 4; i += 1) {
    const y = top + (priceHeight / 3) * i;
    const line = document.createElementNS(svg.namespaceURI, "line");
    line.setAttribute("x1", left);
    line.setAttribute("x2", left + width);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("class", "chart-grid-line");
    svg.appendChild(line);
  }

  rows.forEach((row, index) => {
    const x = left + index * step;
    const open = toNumber(row.open) ?? toNumber(row.close);
    const close = toNumber(row.close);
    const high = toNumber(row.high) ?? close;
    const low = toNumber(row.low) ?? close;
    const up = close >= open;
    const wick = document.createElementNS(svg.namespaceURI, "line");
    wick.setAttribute("x1", x);
    wick.setAttribute("x2", x);
    wick.setAttribute("y1", yScale(high, min, max, top, priceHeight));
    wick.setAttribute("y2", yScale(low, min, max, top, priceHeight));
    wick.setAttribute("class", up ? "candle-up" : "candle-down");
    svg.appendChild(wick);

    const body = document.createElementNS(svg.namespaceURI, "rect");
    const y1 = yScale(open, min, max, top, priceHeight);
    const y2 = yScale(close, min, max, top, priceHeight);
    body.setAttribute("x", x - candleWidth / 2);
    body.setAttribute("y", Math.min(y1, y2));
    body.setAttribute("width", candleWidth);
    body.setAttribute("height", Math.max(1.5, Math.abs(y1 - y2)));
    body.setAttribute("class", up ? "candle-up fill" : "candle-down fill");
    svg.appendChild(body);

    if (row.volume) {
      const volume = document.createElementNS(svg.namespaceURI, "rect");
      const volumeHeightValue = (row.volume / maxVolume) * volumeHeight;
      volume.setAttribute("x", x - candleWidth / 2);
      volume.setAttribute("y", volumeTop + volumeHeight - volumeHeightValue);
      volume.setAttribute("width", candleWidth);
      volume.setAttribute("height", Math.max(1, volumeHeightValue));
      volume.setAttribute("class", up ? "volume-up" : "volume-down");
      svg.appendChild(volume);
    }
  });

  for (const [series, className] of [
    [bandUpper, "band-line band-upper"],
    [bandLower, "band-line band-lower"],
    [ma5, "ma-line ma5"],
    [ma20, "ma-line ma20"],
    [ma60, "ma-line ma60"],
    [ma120, "ma-line ma120"],
  ]) {
    const line = document.createElementNS(svg.namespaceURI, "polyline");
    line.setAttribute("points", pointsForSeries(rows, series, min, max, top, priceHeight, left, width));
    line.setAttribute("class", className);
    svg.appendChild(line);
  }

  const supportY = yScale(analysis.support, min, max, top, priceHeight);
  const resistanceY = yScale(analysis.resistance, min, max, top, priceHeight);
  for (const [value, y, className] of [
    [analysis.support, supportY, "support-line"],
    [analysis.resistance, resistanceY, "resistance-line"],
  ]) {
    if (!value) continue;
    const line = document.createElementNS(svg.namespaceURI, "line");
    line.setAttribute("x1", left);
    line.setAttribute("x2", left + width);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("class", className);
    svg.appendChild(line);
  }

  const label = document.createElementNS(svg.namespaceURI, "text");
  label.setAttribute("x", left);
  label.setAttribute("y", 350);
  label.setAttribute("class", "chart-legend");
  label.textContent = `MA5 ${formatPrice(analysis.ma5)} · MA20 ${formatPrice(analysis.ma20)} · MA60 ${formatPrice(analysis.ma60)} · MA120 ${formatPrice(analysis.ma120)} · BB 상/하 ${formatPrice(analysis.bands.upper)}/${formatPrice(analysis.bands.lower)}`;
  svg.appendChild(label);
  return svg;
}

function readChartSnapshots() {
  try {
    return JSON.parse(localStorage.getItem(CHART_SNAPSHOT_KEY) || "[]");
  } catch {
    return [];
  }
}

function writeChartSnapshots(items) {
  localStorage.setItem(CHART_SNAPSHOT_KEY, JSON.stringify(items.slice(0, 50)));
}

function saveChartSnapshot(card) {
  const snapshot = card.chartSnapshot;
  if (!snapshot) {
    return;
  }
  const svg = card.querySelector(".watch-chart-svg");
  const next = [
    { ...snapshot, chart_svg: svg ? svg.outerHTML : "", id: `${snapshot.code}-${Date.now()}`, saved_at: new Date().toISOString() },
    ...readChartSnapshots(),
  ];
  writeChartSnapshots(next);
  renderChartSnapshots();
}

function renderChartSnapshots() {
  const filters = getViewFilters("chart-history");
  const snapshots = readChartSnapshots();
  const filtered = snapshots.filter((snapshot) =>
    matchesKeyword(filters.keyword, snapshot.name, snapshot.code, snapshot.saved_at) &&
    matchesDateRange(snapshot.saved_at, filters.startDate, filters.endDate)
  );
  elements.watchChartSnapshotMeta.textContent = filtered.length === snapshots.length ? (snapshots.length ? `${formatNumber(snapshots.length)}개 저장` : "저장 없음") : `${formatNumber(filtered.length)} / ${formatNumber(snapshots.length)}개 저장`;
  elements.watchChartSnapshots.innerHTML = "";
  if (!filtered.length) {
    elements.watchChartSnapshots.appendChild(el("p", "muted", "차트 카드의 스냅샷 저장을 누르면 이곳에 기록됩니다."));
    renderSectionShell();
    return;
  }
  for (const snapshot of filtered.slice(0, 12)) {
    const item = el("article", "chart-snapshot-item");
    item.dataset.snapshotId = snapshot.id;
    item.append(
      el("strong", "", `${snapshot.name} · ${snapshot.stance}`),
      el("span", "", `${formatDate(snapshot.saved_at)} · 점수 ${formatNumber(snapshot.score)} · 현재가 ${formatPrice(snapshot.price)}`)
    );
    if (snapshot.chart_svg) {
      const preview = el("div", "chart-snapshot-preview");
      preview.innerHTML = snapshot.chart_svg;
      item.appendChild(preview);
    }
    const remove = el("button", "chart-snapshot-remove", "삭제");
    remove.type = "button";
    remove.dataset.snapshotId = snapshot.id;
    item.appendChild(remove);
    elements.watchChartSnapshots.appendChild(item);
  }
  renderSectionShell();
}

function renderWatchChartMessage(title, message = "") {
  elements.watchChartList.innerHTML = "";
  if (isLoadingMessageText(title)) {
    showWatchChartLoadingOverlay();
    return;
  }
  clearWatchChartLoadingOverlay();
  const card = el("article", "watch-chart-empty-card");
  card.appendChild(el("strong", "", title));
  if (message) {
    card.appendChild(el("p", "", message));
  }
  elements.watchChartList.appendChild(card);
}

function clearWatchChartLoadingOverlay() {
  if (!elements.chartView) {
    return;
  }
  elements.chartView.classList.remove("is-loading");
  const overlay = document.querySelector(".watch-chart-loader-overlay");
  if (overlay) {
    overlay.remove();
  }
}

function showWatchChartLoadingOverlay() {
  if (!elements.chartView) {
    return;
  }
  clearWatchChartLoadingOverlay();
  const overlay = document.createElement("div");
  overlay.className = "watch-chart-loader-overlay";
  overlay.setAttribute("role", "status");
  overlay.setAttribute("aria-label", "차트 데이터를 불러오는 중");
  overlay.setAttribute("aria-busy", "true");
  const spinner = document.createElement("span");
  spinner.className = "inline-loading-spinner";
  spinner.setAttribute("aria-hidden", "true");
  overlay.appendChild(spinner);
  document.body.appendChild(overlay);
  elements.chartView.classList.add("is-loading");
}

function setWatchChartMetaText(text) {
  if (!elements.watchChartMeta) {
    return;
  }
  elements.watchChartMeta.classList.remove("is-loading");
  elements.watchChartMeta.removeAttribute("role");
  elements.watchChartMeta.removeAttribute("aria-busy");
  elements.watchChartMeta.removeAttribute("aria-live");
  elements.watchChartMeta.textContent = text;
}

function setWatchChartMetaLoading(total = 0, done = 0) {
  if (!elements.watchChartMeta) {
    return;
  }
  elements.watchChartMeta.classList.add("is-loading");
  elements.watchChartMeta.setAttribute("role", "status");
  elements.watchChartMeta.setAttribute("aria-live", "polite");
  elements.watchChartMeta.setAttribute("aria-busy", "true");
  elements.watchChartMeta.setAttribute("aria-label", total ? `관심종목 ${formatNumber(total)}개 중 ${formatNumber(done)}개 로딩` : "차트 데이터 로딩");
  elements.watchChartMeta.textContent = "";
}

function buildWatchChartAIAnalysis(item, analysis, dashboard) {
  const price = toNumber(analysis.latest.close);
  const enoughData = (analysis.prices || []).length >= 60;
  if (!enoughData) {
    return {
      decision: "보류",
      decisionTone: "hold",
      confidence: "낮음",
      summary: `${item.name}은 차트 데이터가 충분하지 않아 최종 판단은 보류가 적절합니다.`,
      pricePlan: [
        ["현재가", formatPrice(price)],
        ["매수 기준", "보류"],
        ["손절/축소 기준", "산정 보류"],
        ["돌파 매수가", "산정 보류"],
      ],
      explanation: [
        `현재가 ${formatPrice(price)} 기준으로는 매수 가격대와 손실 제한선을 계산할 데이터가 부족합니다.`,
        "20일선, 60일선, 최근 지지/저항이 쌓이기 전까지 신규 매수는 보류합니다.",
      ],
      keyPoints: ["60일 이상 가격 데이터가 부족해 추세 판단 신뢰도가 낮습니다.", "지지/저항과 거래량 기준이 아직 약합니다."],
      scenarios: ["신규 매수: 보류", "보유 중: 현재가 기준 손실 제한선을 따로 정하지 않고 비중을 작게 유지"],
      risks: ["데이터 부족 상태에서 산출된 점수는 참고용으로만 봐야 합니다."],
    };
  }

  const aboveMa20 = price !== null && analysis.ma20 !== null && price >= analysis.ma20;
  const aboveMa60 = price !== null && analysis.ma60 !== null && price >= analysis.ma60;
  const aboveMa120 = price !== null && analysis.ma120 !== null && price >= analysis.ma120;
  const overheat = (analysis.distance20 !== null && analysis.distance20 > 22) || (analysis.rsi !== null && analysis.rsi >= 75) || (analysis.bandPosition !== null && analysis.bandPosition >= 105);
  const macdPositive = analysis.macd.histogram !== null && analysis.macd.histogram > 0;
  const volumeStrong = analysis.volumeRatio !== null && analysis.volumeRatio >= 1.2;
  const valueChange = dashboard?.momentum?.trading_value_change;
  const buyCandidate = analysis.score >= 72 && aboveMa20 && aboveMa60 && !overheat && (macdPositive || volumeStrong);
  const sellCandidate = analysis.score < 45 || (!aboveMa20 && !aboveMa60) || (price !== null && analysis.support !== null && price < analysis.support);
  const decision = buyCandidate ? "분할매수" : sellCandidate ? "매도/축소" : "보류";
  const decisionTone = buyCandidate ? "buy" : sellCandidate ? "sell" : "hold";
  const confidence = analysis.score >= 78 || analysis.score <= 40 ? "보통 이상" : "보통";
  const trendLabel = analysis.score >= 78 ? "강한 상승 흐름" : analysis.score >= 64 ? "상승 흐름 유지" : analysis.score >= 48 ? "방향성 약함" : "약세 구간";
  const volatilityPct = clampNumber((analysis.atr || 2.5) * 0.75, 1.4, 4.2);
  const buyLowPct = clampNumber(volatilityPct * 0.85, 1.2, 3.5);
  const buyHighPct = buyCandidate ? 0.7 : 0.2;
  const stopPct = clampNumber((analysis.atr || 2.5) * 1.15, 2.8, 5.8);
  const breakoutPct = clampNumber((analysis.atr || 2.5) * 0.55, 1.0, 3.2);
  const targetPct = clampNumber((analysis.atr || 2.5) * 1.2, 3.0, 6.5);
  const nearbyResistance = analysis.resistance && price && analysis.resistance > price && analysis.resistance <= price * 1.045
    ? analysis.resistance
    : null;
  const nearbySupport = analysis.support && price && analysis.support < price && analysis.support >= price * 0.94
    ? analysis.support
    : null;
  const buyLow = nearbySupport || (price ? price * (1 - buyLowPct / 100) : null);
  const buyHigh = price ? price * (1 + buyHighPct / 100) : null;
  const stopRaw = nearbySupport ? Math.min(nearbySupport * 0.985, price * (1 - 2.2 / 100)) : (price ? price * (1 - stopPct / 100) : null);
  const breakoutRaw = nearbyResistance || (price ? price * (1 + breakoutPct / 100) : null);
  const targetRaw = price ? Math.max(breakoutRaw || 0, price * (1 + targetPct / 100)) : null;
  const buyZone = formatPriceRange(buyLow, buyHigh);
  const stopLine = formatPrice(roundTradePrice(stopRaw));
  const breakoutLine = formatPrice(roundTradePrice(breakoutRaw));
  const firstTarget = formatPrice(roundTradePrice(targetRaw));
  const summary =
    decision === "분할매수"
      ? `${item.name}: ${buyZone}에서 1차 분할매수, ${breakoutLine} 위에서는 추가매수, ${stopLine} 아래는 비중축소입니다.`
      : decision === "매도/축소"
        ? `${item.name}: 현재 차트는 약합니다. 보유 중이면 ${stopLine} 아래에서 비중축소, 신규 매수는 보류입니다.`
        : `${item.name}: 지금은 보류입니다. ${buyZone}까지 내려오거나 ${breakoutLine} 위로 강하게 올라설 때만 접근합니다.`;

  const pricePlan = [
    ["현재가", formatPrice(price)],
    ["1차 매수가", buyZone],
    ["추가 매수가", breakoutLine],
    ["1차 매도 구간", firstTarget],
    ["손절/축소 기준", stopLine],
    ["판단 신뢰도", confidence],
  ];

  const explanation = [
    `현재 위치: 현재가 ${formatPrice(price)}, 20일선 ${aboveMa20 ? "위" : "아래"}, 60일선 ${aboveMa60 ? "위" : "아래"}, 120일선 ${aboveMa120 ? "위" : "아래"}.`,
    `매수 타이밍: ${buyZone}에서 밀리지 않으면 1차 분할매수, ${breakoutLine} 위에서 거래량이 붙으면 추가매수.`,
    `매도 타이밍: ${firstTarget} 부근은 일부 이익실현, ${stopLine} 아래는 손절 또는 비중축소.`,
    `지표 판단: RSI ${formatNumber(analysis.rsi)}, 20일선 이격 ${formatPercent(analysis.distance20)}, MACD ${macdPositive ? "상승" : "둔화"}, 거래량 ${formatRatio(analysis.volumeRatio)}.`,
  ];

  const keyPoints = [
    `${trendLabel}: 차트 점수 ${analysis.score}점, 최종 판단은 ${decision}입니다.`,
    `가격 위치: 20일선 ${aboveMa20 ? "위" : "아래"}, 60일선 ${aboveMa60 ? "위" : "아래"}입니다.`,
    `너무 비싼 자리인지: 20일선과 ${formatPercent(analysis.distance20)} 벌어져 있어 ${overheat ? "따라 사기 부담이 있습니다" : "과열 부담은 크지 않습니다"}.`,
    `매수 힘: RSI ${formatNumber(analysis.rsi)}, MACD ${macdPositive ? "양호" : "약함"}입니다.`,
    `거래량: 평소 대비 ${formatRatio(analysis.volumeRatio)}, 거래대금 변화 ${formatPercent(valueChange)}입니다.`,
  ];

  const scenarios = [
    `1차 매수: ${buyZone}에서 가격이 버티면 소액 분할매수.`,
    `추가 매수: ${breakoutLine} 위에서 거래량이 늘면 비중 추가.`,
    `보류: ${buyZone}과 ${breakoutLine} 사이에서 방향 없이 움직이면 매수하지 않음.`,
    `매도/축소: ${stopLine} 아래로 내려가면 비중 축소.`,
  ];

  const risks = [];
  if (!aboveMa20) risks.push("현재가가 20일선 아래라 단기 추세가 약합니다.");
  if (!aboveMa60) risks.push("60일선 아래에서는 중기 추세 신뢰도가 낮아집니다.");
  if (overheat) risks.push("RSI/이격/볼린저 위치상 추격매수 부담이 있습니다.");
  if (!volumeStrong) risks.push("거래량 확장이 약하면 돌파 신뢰도가 낮습니다.");
  if (!macdPositive) risks.push("MACD 모멘텀이 둔화되어 상승 힘이 약합니다.");
  risks.push(`${stopLine} 아래로 내려가면 손절 또는 비중축소 기준에 들어옵니다.`);

  return { decision, decisionTone, confidence, summary, pricePlan, explanation, keyPoints, scenarios, risks };
}

function renderWatchChartAI(card) {
  if (!card.chartAIContext) {
    return;
  }
  const { item, analysis, dashboard } = card.chartAIContext;
  const payload = buildWatchChartAIAnalysis(item, analysis, dashboard);
  let panel = card.querySelector(".chart-ai-panel");
  if (!panel) {
    panel = el("section", "chart-ai-panel");
    const chart = card.querySelector(".watch-chart-visual");
    card.insertBefore(panel, chart || null);
  }
  panel.innerHTML = "";
  const head = el("div", "chart-ai-head");
  const title = el("div");
  title.append(el("h3", "", "AI 차트 분석"), el("span", "", formatDate(new Date().toISOString())));
  const decision = el("strong", `chart-ai-decision ${payload.decisionTone}`, payload.decision);
  head.append(title, decision);
  const summary = el("p", "chart-ai-summary", payload.summary);
  const pricePlan = el("div", "chart-ai-price-plan");
  for (const [label, value] of payload.pricePlan || []) {
    const row = el("div");
    row.append(el("span", "", label), el("strong", "", value));
    pricePlan.appendChild(row);
  }
  const explanation = el("div", "chart-ai-explanation");
  for (const text of payload.explanation || []) {
    explanation.appendChild(el("p", "", text));
  }
  const grid = el("div", "chart-ai-grid");
  for (const [title, items] of [
    ["핵심 판단", payload.keyPoints],
    ["매매 시나리오", payload.scenarios],
    ["위험 구간", payload.risks],
  ]) {
    const section = el("section");
    section.appendChild(el("h4", "", title));
    const list = el("ul", "chart-ai-list");
    appendListItems(list, items, "표시할 분석이 부족합니다.");
    section.appendChild(list);
    grid.appendChild(section);
  }
  panel.append(head, summary, pricePlan, explanation, grid);
  panel.hidden = false;
}

function createWatchChartCard(item, prices, dashboard, chartAnalysis = null) {
  const analysis = chartAnalysis || computeWatchChart(prices);
  const card = el("article", "watch-chart-card");
  const head = el("div", "watch-chart-head");
  const title = el("div");
  const link = el("a", "watch-chart-name", item.name);
  link.href = viewStockUrl(item);
  title.append(link, el("span", "", `${item.market || dashboard.market || "미국증시"} · 선택 종목 AI 차트`));
  const score = el("div", "watch-chart-score");
  score.append(el("strong", "", String(analysis.score)), el("span", "", analysis.stance));
  setTone(score, analysis.score - 55);
  const actions = el("div", "watch-chart-actions");
  const refreshButton = el("button", "chart-refresh-button", "새로고침");
  refreshButton.type = "button";
  const aiButton = el("button", "chart-ai-button", "AI 분석하기");
  aiButton.type = "button";
  const saveButton = el("button", "chart-save-button", "스냅샷 저장");
  saveButton.type = "button";
  actions.append(refreshButton, aiButton, saveButton);
  const headAside = el("div", "watch-chart-head-aside");
  headAside.append(score, actions);
  head.append(title, headAside);

  const chartWrap = el("div", "watch-chart-visual");
  chartWrap.appendChild(createWatchChartSvg(analysis));

  const legend = el("div", "chart-line-legend");
  for (const [className, label] of [
    ["legend-ma5", "MA5"],
    ["legend-ma20", "MA20"],
    ["legend-ma60", "MA60"],
    ["legend-ma120", "MA120"],
    ["legend-band", "볼린저밴드"],
    ["legend-support", "지지"],
    ["legend-resistance", "저항"],
  ]) {
    const itemNode = el("span");
    itemNode.append(el("i", className), document.createTextNode(label));
    legend.appendChild(itemNode);
  }

  const metrics = el("div", "watch-chart-metrics");
  for (const [label, value] of [
    ["현재가", formatPrice(analysis.latest.close)],
    ["5일선", formatPrice(analysis.ma5)],
    ["20일선", formatPrice(analysis.ma20)],
    ["60일선", formatPrice(analysis.ma60)],
    ["120일선", formatPrice(analysis.ma120)],
    ["이격", formatPercent(analysis.distance20)],
    ["지지", formatPrice(analysis.support)],
    ["저항", formatPrice(analysis.resistance)],
  ]) {
    const row = el("div");
    row.append(chartTermLabel(label), el("strong", "", value));
    metrics.appendChild(row);
  }

  const indicators = el("div", "chart-indicators");
  const rsiState = analysis.rsi === null ? "-" : analysis.rsi >= 70 ? "과열권" : analysis.rsi <= 30 ? "침체권" : "중립권";
  const macdState = analysis.macd.histogram === null ? "-" : analysis.macd.histogram > 0 ? "상승 모멘텀" : "둔화 모멘텀";
  const bandState =
    analysis.bandPosition === null ? "-" : analysis.bandPosition >= 100 ? "상단 돌파" : analysis.bandPosition <= 0 ? "하단 이탈" : "밴드 내부";
  const atrState = analysis.atr === null ? "-" : analysis.atr >= 6 ? "변동성 큼" : analysis.atr >= 3 ? "보통" : "변동성 낮음";
  for (const [label, value, note] of [
    ["RSI(14)", formatNumber(analysis.rsi), rsiState],
    ["MACD", formatNumber(analysis.macd.histogram), macdState],
    ["볼린저", `${formatNumber(analysis.bandPosition)}% 위치`, bandState],
    ["ATR", formatPercent(analysis.atr), atrState],
    ["거래량", formatRatio(analysis.volumeRatio), "20일/60일"],
  ]) {
    const itemNode = el("div");
    itemNode.append(chartTermLabel(label), el("strong", "", value), el("em", "", note));
    indicators.appendChild(itemNode);
  }

  const checklist = el("div", "chart-checklist");
  for (const row of analysis.checklist) {
    const itemNode = el("div", row.ok ? "check-row positive-check" : "check-row caution-check");
    itemNode.append(el("strong", "", row.ok ? "충족" : "확인"), el("span", "", row.label), el("em", "", row.note));
    checklist.appendChild(itemNode);
  }

  const notes = document.createElement("ul");
  notes.className = "chart-note-list";
  appendListItems(notes, analysis.notes, "차트 판단 근거가 부족합니다.");

  card.chartAIContext = { item, analysis, dashboard };
  card.dataset.code = item.code;
  card.chartSnapshot = {
    code: item.code,
    name: item.name,
    market: item.market || dashboard.market,
    stance: analysis.stance,
    score: analysis.score,
    price: analysis.latest.close,
    support: analysis.support,
    resistance: analysis.resistance,
    notes: analysis.notes,
  };
  card.append(head, chartWrap, legend, metrics, indicators, checklist, notes);
  return card;
}

function renderWatchChartList(results) {
  clearWatchChartLoadingOverlay();
  state.selectedWatchChartCode = "";
  elements.watchChartList.innerHTML = "";
  const filters = getViewFilters("chart");
  const categoryMatch = (analysis) => {
    if (filters.category === "all") return true;
    if (filters.category === "strong") return (analysis?.score || 0) >= 70;
    if (filters.category === "weak") return (analysis?.score || 0) < 50;
    if (filters.category === "neutral") return (analysis?.score || 0) >= 50 && (analysis?.score || 0) < 70;
    return true;
  };
  const marketMatch = (result) => filters.auxOne === "all" || (result.item?.market || result.dashboard?.market) === filters.auxOne;
  const keywordMatch = (result) => matchesKeyword(filters.keyword, result.item?.name, result.item?.code, result.item?.market || result.dashboard?.market);
  const allAvailable = results.filter((result) => result.dashboard && result.prices?.length && result.analysis);
  const available = allAvailable.filter((result) => categoryMatch(result.analysis) && marketMatch(result) && keywordMatch(result));
  const filterActive = Boolean(filters.keyword || filters.category !== "all" || filters.auxOne !== "all");
  const metaText = available.length || allAvailable.length
    ? `관심종목 ${formatNumber(available.length)}개${allAvailable.length !== available.length ? ` / 전체 ${formatNumber(allAvailable.length)}개` : ""}`
    : "관심종목 없음";
  setWatchChartMetaText(metaText);
  syncSectionShellMeta();
  if (!available.length) {
    if (filterActive && allAvailable.length) {
      renderWatchChartMessage("조건에 맞는 관심 종목이 없습니다.", "검색어나 필터 조건을 조정하면 다시 확인할 수 있습니다.");
    } else {
      renderWatchChartMessage("차트 데이터를 불러오지 못했습니다.", "잠시 후 다시 들어오거나 종목 카드의 새로고침을 눌러주세요.");
    }
    renderSectionShell();
    return;
  }
  const list = el("section", "watch-chart-selector-list");
  for (const result of available) {
    const { item, dashboard, analysis } = result;
    const row = el("button", "watch-chart-row");
    row.type = "button";
    row.dataset.code = item.code;
    const main = el("div", "watch-chart-row-main");
    const head = el("div", "watch-chart-row-head");
    const name = el("strong", "", item.name);
    const price = el("span", "watch-chart-row-price", formatPrice(analysis.latest?.close));
    setTone(price, dashboard?.quote?.change_rate);
    head.append(name);
    main.append(head, price);

    const metrics = el("div", "watch-chart-row-metrics");
    const scoreWrap = el("div", "watch-chart-score-badge");
    const scoreLabel = el("span", "", "AI 점수");
    const score = el("strong", "", String(analysis.score));
    const stance = el("em", "watch-chart-stance-badge", analysis.stance);
    setTone(score, analysis.score - 55);
    setTone(stance, analysis.score >= 78 ? 1 : analysis.score >= 48 ? 0 : -1);
    scoreWrap.append(scoreLabel, score);
    metrics.append(scoreWrap, stance);
    row.append(main, metrics);
    list.appendChild(row);
  }
  elements.watchChartList.appendChild(list);
  renderSectionShell();
}

async function resolveWatchChartItems() {
  let items = readWatchlist();
  if (!items.length && state.watchlistId) {
    try {
      const remotePayload = await fetchRemoteWatchlist(state.watchlistId);
      items = normalizeWatchlistItems(remotePayload.items || []);
      if (items.length) {
        writeWatchlist(items, { sync: false });
        setWatchlistIdStatus(`${state.watchlistId} · ${formatNumber(items.length)}개 동기화`, "success");
      }
    } catch {
      setWatchlistIdStatus("관심종목 동기화 실패", "error");
    }
  }
  return items;
}

function renderWatchChartDetail(code) {
  const result = state.watchChartResults.find((item) => item.item?.code === code);
  if (!result || !result.dashboard || !result.prices?.length) {
    renderWatchChartList(state.watchChartResults);
    return;
  }
  state.selectedWatchChartCode = code;
  elements.watchChartList.innerHTML = "";
  const detail = el("section", "watch-chart-detail-view");
  const toolbar = el("div", "watch-chart-detail-toolbar");
  const back = el("button", "secondary-action chart-detail-back", "<");
  back.type = "button";
  back.setAttribute("aria-label", "목록으로 돌아가기");
  back.title = "목록으로 돌아가기";
  toolbar.append(back);
  detail.append(toolbar, createWatchChartCard(result.item, result.prices, result.dashboard, result.analysis));
  elements.watchChartList.appendChild(detail);
}

async function refreshWatchChartCard(card, button) {
  const code = card?.dataset?.code;
  const current = state.watchChartResults.find((result) => result.item?.code === code);
  if (!code || !current?.item) {
    return;
  }
  const hadAI = Boolean(card.querySelector(".chart-ai-panel"));
  const previousText = button.textContent;
  button.disabled = true;
  button.textContent = "갱신 중";
  try {
    clearCachedUrl(`/us/stocks/${encodeURIComponent(code)}/prices?limit=180`);
    clearCachedUrl(`/us/stocks/${encodeURIComponent(code)}/dashboard?refresh=1`);
    const [prices, dashboard] = await Promise.all([
      fetchJsonCached(liveUrl(`/us/stocks/${encodeURIComponent(code)}/prices?limit=180`), { force: true, ttlMs: 0 }),
      fetchJsonCached(liveUrl(`/us/stocks/${encodeURIComponent(code)}/dashboard?refresh=1`), { force: true, ttlMs: 0 }),
    ]);
    const analysis = prices.length ? computeWatchChart(prices) : null;
    const next = { item: current.item, prices, dashboard, analysis };
    state.watchChartResults = state.watchChartResults.map((result) => (result.item?.code === code ? next : result));
    renderWatchChartDetail(code);
    const nextCard = elements.watchChartList.querySelector(`.watch-chart-card[data-code="${selectorEscape(code)}"]`);
    if (hadAI && nextCard) {
      renderWatchChartAI(nextCard);
      const nextAIButton = nextCard.querySelector(".chart-ai-button");
      if (nextAIButton) {
        nextAIButton.textContent = "AI 분석 갱신";
      }
    }
  } catch {
    button.textContent = "실패";
    window.setTimeout(() => {
      button.disabled = false;
      button.textContent = previousText || "새로고침";
    }, 1200);
    return;
  }
}

async function loadWatchCharts(options = {}) {
  const force = options.force !== false;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("chart");
  const items = await resolveWatchChartItems();
  renderChartSnapshots();
  elements.watchChartList.innerHTML = "";
  state.watchChartResults = [];
  state.selectedWatchChartCode = "";
  if (!items.length) {
    setWatchChartMetaText("관심종목 없음");
    syncSectionShellMeta();
    renderWatchChartMessage("관심 종목이 없습니다.", "종목 검색에서 관심 종목을 추가하면 이곳에 AI 차트 분석 리스트가 표시됩니다.");
    return;
  }
  showWatchChartLoadingOverlay();
  setWatchChartMetaLoading(items.length, 0);
  syncSectionShellMeta();
  if (elements.watchChartRefresh) {
    elements.watchChartRefresh.disabled = true;
    elements.watchChartRefresh.textContent = "불러오는 중";
  }
  try {
    const results = await mapWithConcurrency(
      items,
      2,
      async (item) => {
        try {
          const pricesUrl = `/us/stocks/${encodeURIComponent(item.code)}/prices?limit=180`;
          const dashboardUrl = `/us/stocks/${encodeURIComponent(item.code)}/dashboard?refresh=1`;
          const [prices, dashboard] = await Promise.race([
            Promise.all([
              fetchJsonCached(pricesUrl, { force, ttlMs: force ? 0 : ttlMs }),
              fetchJsonCached(dashboardUrl, { force, ttlMs: force ? 0 : ttlMs }),
            ]),
            rejectAfter(15_000, "watch chart timeout"),
          ]);
          return { item, prices, dashboard, analysis: prices.length ? computeWatchChart(prices) : null };
        } catch {
          return { item, prices: [], dashboard: null, analysis: null };
        }
      },
      (done, total) => {
        if (elements.watchChartRefresh) {
          elements.watchChartRefresh.textContent = `${formatNumber(done)}/${formatNumber(total)}`;
        }
        setWatchChartMetaLoading(total, done);
        syncSectionShellMeta();
      }
    );
    state.watchChartResults = results;
    const availableCount = results.filter((result) => result.dashboard && result.prices?.length && result.analysis).length;
    setWatchChartMetaText(availableCount ? `관심종목 ${formatNumber(availableCount)}개` : `관심종목 ${formatNumber(items.length)}개`);
    syncSectionShellMeta();
    renderWatchChartList(results);
  } finally {
    clearWatchChartLoadingOverlay();
    if (elements.watchChartRefresh) {
      elements.watchChartRefresh.disabled = false;
      elements.watchChartRefresh.textContent = "새로고침";
    }
  }
}

function appendListItems(parent, items, fallback) {
  parent.innerHTML = "";
  const list = items && items.length ? items : [fallback];
  for (const item of list) {
    const li = document.createElement("li");
    li.textContent = item;
    parent.appendChild(li);
  }
}

const CHART_TERM_HELP = {
  현재가: "지금 시장에서 거래되는 가격입니다. 매수·매도 판단의 출발점으로 봅니다.",
  "5일선": "최근 5거래일 평균 가격입니다. 아주 짧은 단기 흐름을 볼 때 씁니다.",
  "20일선": "최근 20거래일 평균 가격입니다. 한 달 정도의 단기 추세 기준으로 많이 봅니다.",
  "60일선": "최근 60거래일 평균 가격입니다. 중기 흐름이 살아 있는지 볼 때 씁니다.",
  "120일선": "최근 120거래일 평균 가격입니다. 긴 흐름의 방향을 보는 기준입니다.",
  이격: "현재가가 20일선에서 얼마나 떨어져 있는지입니다. 너무 크면 추격매수 부담이 커집니다.",
  지지: "가격이 내려올 때 버텨주길 기대하는 구간입니다. 이탈하면 손실 관리가 필요합니다.",
  저항: "가격이 올라갈 때 막힐 수 있는 구간입니다. 넘으면 추가 상승 기대가 커질 수 있습니다.",
  "RSI(14)": "최근 14일 기준 매수세가 과한지 보는 지표입니다. 70 이상은 과열, 30 이하는 침체로 봅니다.",
  MACD: "짧은 평균과 긴 평균의 차이를 보는 추세 지표입니다. 양수면 상승 힘, 음수면 둔화 힘으로 해석합니다.",
  볼린저: "평균 가격 주변의 위아래 범위입니다. 상단에 가까우면 단기 과열, 하단에 가까우면 약세를 의심합니다.",
  ATR: "최근 가격 변동 폭입니다. 값이 높으면 하루하루 흔들림이 큰 종목입니다.",
  거래량: "최근 20일 거래량이 60일 평균보다 많은지 보는 값입니다. 1배 이상이면 평소보다 관심이 늘어난 편입니다.",
};

function chartTermLabel(label) {
  const text = el("span", "chart-term-text", label);
  const help = CHART_TERM_HELP[label];
  if (!help) {
    return text;
  }
  const wrapper = el("span", "chart-term-label");
  const button = el("button", "term-help", "?");
  button.type = "button";
  button.setAttribute("aria-label", `${label} 설명`);
  button.setAttribute("data-tooltip", help);
  wrapper.append(text, button);
  return wrapper;
}

function recommendTermLabel(label) {
  const text = el("span", "chart-term-text", label);
  const help = RECOMMEND_TERM_HELP[label];
  if (!help) {
    return text;
  }
  const wrapper = el("span", "chart-term-label recommend-term-label");
  const button = el("button", "term-help", "?");
  button.type = "button";
  button.setAttribute("aria-label", `${label} 설명`);
  button.setAttribute("data-tooltip", help);
  wrapper.append(text, button);
  return wrapper;
}

function componentTermLabel(key, label) {
  return recommendTermLabel(label || COMPONENT_LABELS[key] || key);
}

function applyStockTermTooltips() {
  const targets = [
    "#stock-view .quote-strip > div > span",
    "#stock-view .chart-score-block > span",
    "#stock-view .chart-summary-grid div > span",
    "#stock-view .metrics dt",
  ];
  document.querySelectorAll(targets.join(",")).forEach((node) => {
    if (node.querySelector(".term-help")) {
      return;
    }
    const label = node.textContent.trim();
    const help = STOCK_TERM_HELP[label] || CHART_TERM_HELP[label];
    if (!help) {
      return;
    }
    const button = el("button", "term-help", "?");
    button.type = "button";
    button.setAttribute("aria-label", `${label} 설명`);
    button.setAttribute("data-tooltip", help);
    node.classList.add("chart-term-label", "stock-term-label");
    node.replaceChildren(el("span", "chart-term-text", label), button);
  });
}

function resetAIAnalysis() {
  elements.aiAnalysisPanel.hidden = true;
  elements.aiAnalysisMeta.textContent = "-";
  elements.aiAnalysisStance.textContent = "-";
  elements.aiAnalysisSummary.textContent = "";
  setText(elements.aiDecisionStance, "-");
  setText(elements.aiDecisionConfidence, "-");
  setText(elements.aiDecisionEntry, "-");
  setText(elements.aiDecisionCondition, "-");
  elements.aiKeyPoints.innerHTML = "";
  elements.aiStrategy.innerHTML = "";
  elements.aiRisks.innerHTML = "";
  elements.aiSectionList.innerHTML = "";
  renderStockStrategyVisual(null);
}

function renderAIAnalysis(payload) {
  elements.aiAnalysisPanel.hidden = false;
  elements.aiAnalysisMeta.textContent = `${payload.name} · 판단 신뢰도 ${formatProbability(payload.confidence)} · ${formatDate(payload.generated_at)}`;
  elements.aiAnalysisStance.textContent = payload.stance || "-";
  elements.aiAnalysisSummary.textContent = payload.summary || "";
  setText(elements.stockSummaryStance, payload.stance || "-");
  setText(elements.stockSummaryLine, payload.summary || elements.stockSummaryLine?.textContent || "");
  setText(elements.stockSummaryConfidence, formatProbability(payload.confidence));
  const stance = payload.stance || "";
  setTone(elements.aiAnalysisStance, stance.includes("관망") ? -1 : stance.includes("중립") ? 0 : 1);
  renderAIDecisionSummary(payload);
  appendListItems(elements.aiKeyPoints, payload.key_points, "핵심 판단을 만들 데이터가 부족합니다.");
  appendListItems(elements.aiStrategy, payload.strategy, "매매 시나리오를 만들 데이터가 부족합니다.");
  appendListItems(elements.aiRisks, payload.risks, "확인할 리스크가 제한적입니다.");

  elements.aiSectionList.innerHTML = "";
  for (const section of payload.sections || []) {
    const box = el("section", "ai-section");
    box.appendChild(el("h3", "", section.title));
    const list = el("ul", "ai-list");
    appendListItems(list, section.items, "표시할 내용이 부족합니다.");
    box.appendChild(list);
    elements.aiSectionList.appendChild(box);
  }
  renderStockStrategyVisual(payload);
}

async function loadAIAnalysis() {
  if (!state.currentStock || !state.currentStock.code) {
    return;
  }
  const code = state.currentStock.code;
  const originalText = elements.aiAnalysisButton.textContent;
  elements.aiAnalysisButton.disabled = true;
  elements.aiAnalysisButton.textContent = "분석 중";
  elements.aiAnalysisPanel.hidden = false;
  elements.aiAnalysisMeta.textContent = `${state.currentStock.name} · 분석 중`;
  elements.aiAnalysisStance.textContent = "-";
  elements.aiAnalysisSummary.textContent = "차트, 수급, 밸류에이션, 뉴스, 거시 민감도를 함께 해석하는 중입니다.";
  elements.aiKeyPoints.innerHTML = "";
  elements.aiStrategy.innerHTML = "";
  elements.aiRisks.innerHTML = "";
  elements.aiSectionList.innerHTML = "";
  const url = `/us/stocks/${encodeURIComponent(code)}/ai-analysis?refresh=1`;
  clearCachedUrl(url);
  try {
    renderAIAnalysis(await fetchJsonCached(url, { force: true, ttlMs: 0 }));
  } catch {
    elements.aiAnalysisSummary.textContent = "AI 분석을 생성하지 못했습니다.";
  } finally {
    elements.aiAnalysisButton.disabled = false;
    elements.aiAnalysisButton.textContent = originalText;
  }
}

function readRecommendationHistory() {
  try {
    return JSON.parse(localStorage.getItem(RECOMMENDATION_HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function writeRecommendationHistory(items) {
  localStorage.setItem(RECOMMENDATION_HISTORY_KEY, JSON.stringify(items.slice(0, 20)));
}

function saveRecommendationSnapshot(payload) {
  if (!payload || !payload.items || payload.items.length === 0) {
    return;
  }
  const snapshot = {
    id: `${payload.as_of || new Date().toISOString()}-${Date.now()}`,
    saved_at: payload.as_of || new Date().toISOString(),
    as_of: payload.as_of || new Date().toISOString(),
    universe_count: payload.universe_count,
    candidate_count: payload.candidate_count,
    methodology: payload.methodology || [],
    items: payload.items,
  };
  const history = readRecommendationHistory().filter((item) => item.as_of !== snapshot.as_of);
  writeRecommendationHistory([snapshot, ...history]);
}

function newYorkClockParts(date = new Date()) {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = Object.fromEntries(formatter.formatToParts(date).map((part) => [part.type, part.value]));
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    weekday: parts.weekday || "",
    hour: Number(parts.hour),
    minute: Number(parts.minute),
  };
}

function newYorkDateKey(date = new Date()) {
  const parts = newYorkClockParts(date);
  return `${parts.year}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
}

function usRecommendationMarketPhase(date = new Date()) {
  if (state.usSectorMoves?.market_session) {
    return state.usSectorMoves.market_session;
  }
  const parts = newYorkClockParts(date);
  if (["Sat", "Sun"].includes(parts.weekday)) {
    return "closed";
  }
  const minutes = parts.hour * 60 + parts.minute;
  if (minutes >= 4 * 60 && minutes < 9 * 60 + 30) {
    return "premarket";
  }
  if (minutes >= 9 * 60 + 30 && minutes < 16 * 60) {
    return "regular";
  }
  if (minutes >= 16 * 60 && minutes < 20 * 60) {
    return "afterhours";
  }
  return "closed";
}

function recommendationCooldownStorageKey() {
  return `${RECOMMENDATION_COOLDOWN_KEY}:${state.watchlistId || "guest"}`;
}

function recommendationCooldownMs(date = new Date()) {
  return usRecommendationMarketPhase(date) === "regular"
    ? RECOMMENDATION_REGULAR_COOLDOWN_MS
    : RECOMMENDATION_OFFHOURS_COOLDOWN_MS;
}

function readRecommendationCooldown() {
  try {
    const raw = localStorage.getItem(recommendationCooldownStorageKey());
    if (!raw) {
      return null;
    }
    const record = JSON.parse(raw);
    if (!record || record.dayKey !== newYorkDateKey()) {
      localStorage.removeItem(recommendationCooldownStorageKey());
      return null;
    }
    const generatedAt = Number(record.generatedAt);
    const cooldownUntil = Number(record.cooldownUntil);
    if (!Number.isFinite(generatedAt) || !Number.isFinite(cooldownUntil)) {
      localStorage.removeItem(recommendationCooldownStorageKey());
      return null;
    }
    return {
      dayKey: record.dayKey,
      generatedAt,
      cooldownUntil,
      phase: record.phase || "closed",
    };
  } catch {
    return null;
  }
}

function saveRecommendationCooldown() {
  const now = new Date();
  const generatedAt = now.getTime();
  const durationMs = recommendationCooldownMs(now);
  const record = {
    dayKey: newYorkDateKey(now),
    generatedAt,
    cooldownUntil: generatedAt + durationMs,
    durationMs,
    phase: usRecommendationMarketPhase(now),
  };
  try {
    localStorage.setItem(recommendationCooldownStorageKey(), JSON.stringify(record));
  } catch {
    return record;
  }
  return record;
}

function recommendationCooldownRemainingMs(record = readRecommendationCooldown()) {
  if (!record) {
    return 0;
  }
  return Math.max(0, record.cooldownUntil - Date.now());
}

function formatRecommendationCooldown(ms) {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function updateRecommendationButtonState() {
  if (!elements.recommendButton) {
    return;
  }
  window.clearTimeout(state.recommendationCooldownTimer);
  state.recommendationCooldownTimer = null;

  if (state.recommendationLoading) {
    elements.recommendButton.disabled = true;
    elements.recommendButton.textContent = "계산 중";
    elements.recommendButton.title = "";
    return;
  }

  const record = readRecommendationCooldown();
  const remaining = recommendationCooldownRemainingMs(record);
  if (remaining > 0) {
    elements.recommendButton.disabled = true;
    elements.recommendButton.textContent = `다시 추천받기 ${formatRecommendationCooldown(remaining)}`;
    elements.recommendButton.title = "남은 시간이 끝나면 새 추천을 다시 계산할 수 있습니다.";
    state.recommendationCooldownTimer = window.setTimeout(updateRecommendationButtonState, 1000);
    return;
  }

  elements.recommendButton.disabled = false;
  elements.recommendButton.textContent = record ? "다시 추천받기" : "추천받기";
  elements.recommendButton.title = record ? "현재 시점 기준으로 추천 10개를 다시 계산합니다." : "현재 시점 기준으로 추천 10개를 계산합니다.";
}

const RECOMMENDATION_REPEAT_WINDOW_MS = 1000 * 60 * 60 * 48;

function buildRecommendationPenaltyMap(history) {
  const penaltyMap = new Map();
  const now = Date.now();
  const recentHistory = (history || [])
    .filter((snapshot) => {
      const asOf = new Date(snapshot?.as_of || snapshot?.saved_at || 0).getTime();
      return Number.isFinite(asOf) && now - asOf <= RECOMMENDATION_REPEAT_WINDOW_MS;
    })
    .slice(0, 6);
  for (const snapshot of recentHistory) {
    const asOf = new Date(snapshot?.as_of || snapshot?.saved_at || 0).getTime();
    const ageMs = Math.max(0, now - asOf);
    const decay = Math.max(0.2, 1 - ageMs / RECOMMENDATION_REPEAT_WINDOW_MS);
    for (const [index, entry] of (snapshot.items || []).entries()) {
      const code = String(entry?.code || "").trim();
      if (!code) {
        continue;
      }
      const basePenalty =
        index < 3 ? 10 :
        index < 5 ? 7 :
        index < RECOMMENDATION_LIMIT ? 4 :
        2;
      const nextPenalty = (penaltyMap.get(code) || 0) + basePenalty * decay;
      penaltyMap.set(code, Math.min(nextPenalty, 14));
    }
  }
  return penaltyMap;
}

function rerankRecommendationItems(items) {
  const penaltyMap = buildRecommendationPenaltyMap(readRecommendationHistory());
  return (items || [])
    .map((item, index) => {
      const code = String(item?.code || "").trim();
      return {
        item,
        index,
        rawScore: toNumber(item?.score) ?? 0,
        penalty: penaltyMap.get(code) || 0,
      };
    })
    .sort((left, right) => {
      const leftScore = left.rawScore - left.penalty;
      const rightScore = right.rawScore - right.penalty;
      return rightScore - leftScore || right.rawScore - left.rawScore || left.index - right.index;
    })
    .map(({ item }, index) => ({
      ...item,
      rank: index + 1,
    }));
}

function readRecommendationTracks() {
  try {
    const parsed = JSON.parse(localStorage.getItem(RECOMMENDATION_TRACK_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((item) => item && item.code && item.name) : [];
  } catch {
    return [];
  }
}

function writeRecommendationTracks(items) {
  const seen = new Set();
  const normalized = [];
  for (const item of items || []) {
    const code = String(item?.code || "").trim();
    if (!code || seen.has(code)) {
      continue;
    }
    seen.add(code);
    normalized.push(item);
  }
  localStorage.setItem(RECOMMENDATION_TRACK_KEY, JSON.stringify(normalized.slice(0, 50)));
  updateRecommendationTrackMeta();
}

function isTrackedRecommendation(code) {
  return readRecommendationTracks().some((item) => item.code === code);
}

function buildRecommendationTrackEntry(item) {
  const ai = buildRecommendationAIExplanation(item);
  return {
    id: `${item.code}-${Date.now()}`,
    code: item.code,
    name: item.name,
    market: item.market,
    tracked_at: new Date().toISOString(),
    tracked_price: toNumber(item.price),
    tracked_score: toNumber(item.score),
    tracked_action: item.action || "",
    ai: {
      decision: ai.decision,
      summary: ai.summary,
    },
    item: {
      score: item.score,
      action: item.action,
      reasons: Array.isArray(item.reasons) ? item.reasons.slice(0, 5) : [],
      risks: Array.isArray(item.risks) ? item.risks.slice(0, 4) : [],
      component_scores: item.component_scores || {},
      chart_analysis: item.chart_analysis || {},
      one_month_return: item.one_month_return,
      three_month_return: item.three_month_return,
      trading_value: item.trading_value,
      change_rate: item.change_rate,
    },
  };
}

function trackRecommendationItem(item) {
  if (!item?.code || !item?.name) {
    return null;
  }
  const tracks = readRecommendationTracks();
  const existing = tracks.find((entry) => entry.code === item.code);
  if (existing) {
    return existing;
  }
  const next = buildRecommendationTrackEntry(item);
  writeRecommendationTracks([next, ...tracks]);
  return next;
}

function deleteRecommendationTrack(trackId) {
  writeRecommendationTracks(readRecommendationTracks().filter((item) => item.id !== trackId));
}

function updateRecommendationTrackMeta() {
  const tracks = readRecommendationTracks();
  elements.recommendHistoryMeta.textContent = tracks.length ? `종목 ${formatNumber(tracks.length)}개 추적 중` : "추적 종목 없음";
  syncSectionShellMeta();
}

function recommendationTrackProfit(trackedPrice, currentPrice) {
  const base = toNumber(trackedPrice);
  const current = toNumber(currentPrice);
  if (base === null || current === null || base === 0) {
    return { value: null, rate: null };
  }
  const value = current - base;
  const rate = (value / base) * 100;
  return { value, rate };
}

function createRecommendationTrackCard(track, dashboard = null) {
  const saved = track.item || {};
  const chart = saved.chart_analysis || {};
  const trackedPrice = toNumber(track.tracked_price);
  const currentPrice = toNumber(dashboard?.quote?.price);
  const profit = recommendationTrackProfit(trackedPrice, currentPrice);
  const card = el("article", "recommend-track-card");
  card.dataset.trackId = track.id || "";
  card.dataset.code = track.code || "";
  card.dataset.trackedPrice = trackedPrice !== null ? String(trackedPrice) : "";
  card.recommendationTrack = track;
  card.trackDashboard = dashboard;

  const head = el("div", "recommend-track-head");
  const title = el("div", "recommend-track-title");
  title.append(
    el("strong", "", track.name || "-"),
    el("span", "", `${track.code || "-"} · ${track.market || "-"}`),
  );
  const actions = el("div", "recommend-track-actions");
  const open = document.createElement("a");
  open.className = "snapshot-button";
  open.href = viewStockUrl({ code: track.code || "AAPL" });
  open.textContent = "종목 상세";
  const remove = el("button", "snapshot-delete track-delete", "추적 해제");
  remove.type = "button";
  remove.dataset.trackId = track.id || "";
  actions.append(open, remove);
  head.append(title, actions);

  const metrics = el("div", "recommend-track-metrics");
  const metricRows = [
    ["추적 단가", trackedPrice !== null ? formatPrice(trackedPrice) : "-", "", trackedPrice],
    ["현재 단가", currentPrice !== null ? formatPrice(currentPrice) : "불러오는 중", "tracked_current_price", currentPrice],
    ["주당 손익", profit.value !== null ? formatPriceChange(profit.value) : "-", "tracked_pnl_value", profit.value],
    ["손익률", profit.rate !== null ? formatPercent(profit.rate) : "-", "tracked_pnl_rate", profit.rate],
  ];
  for (const [label, value, field, rawValue] of metricRows) {
    const row = el("div");
    const valueNode = el("strong", "", value);
    if (field) {
      valueNode.dataset.field = field;
    }
    if (rawValue !== null && rawValue !== undefined && rawValue !== "") {
      valueNode.dataset.rawValue = String(rawValue);
    }
    if (field === "tracked_pnl_value" || field === "tracked_pnl_rate") {
      setTone(valueNode, rawValue);
    }
    row.append(el("span", "", label), valueNode);
    metrics.appendChild(row);
  }

  const signalGrid = el("div", "recommend-track-signals");
  const signalRows = [
    ["추적 시작", formatDate(track.tracked_at)],
    ["당시 AI 판단", track.ai?.decision || track.tracked_action || "-"],
    ["당시 추천 점수", formatNumber(track.tracked_score)],
    ["당시 차트 점수", formatNumber(chart.score)],
    ["현재 기준", dashboard?.as_of ? formatDate(dashboard.as_of) : "현재 시세 확인 중"],
  ];
  for (const [label, value] of signalRows) {
    const row = el("div");
    row.append(el("span", "", label), el("strong", "", value || "-"));
    signalGrid.appendChild(row);
  }

  const detailToggle = el("button", "recommend-track-detail-toggle", "자세히 보기");
  detailToggle.type = "button";
  detailToggle.setAttribute("aria-expanded", "false");

  const detail = el("section", "recommend-track-detail");
  detail.hidden = true;

  const summary = el("section", "recommend-track-summary");
  summary.append(
    el("h3", "", "추적 시점 AI 요약"),
    el("p", "", track.ai?.summary || `${track.name || "종목"} 추적 시점 요약이 아직 없습니다.`),
  );

  const reasons = el("section", "recommend-track-summary");
  reasons.appendChild(el("h3", "", "당시 핵심 포인트"));
  const reasonList = document.createElement("ul");
  reasonList.className = "recommend-track-points";
  appendListItems(reasonList, saved.reasons || [], "저장된 요약 포인트가 없습니다.");
  reasons.appendChild(reasonList);

  detail.append(signalGrid, summary, reasons);
  card.append(head, metrics, detailToggle, detail);
  return card;
}

function updateTrackedRecommendationQuote(code, quote) {
  if (!code || !quote) {
    return;
  }
  const card = elements.recommendHistoryList.querySelector(`.recommend-track-card[data-code="${selectorEscape(code)}"]`);
  if (!card) {
    return;
  }
  const trackedPrice = toNumber(card.dataset.trackedPrice);
  const currentPriceNode = card.querySelector('[data-field="tracked_current_price"]');
  const pnlValueNode = card.querySelector('[data-field="tracked_pnl_value"]');
  const pnlRateNode = card.querySelector('[data-field="tracked_pnl_rate"]');
  if (currentPriceNode && quote.price !== null && quote.price !== undefined && quote.price !== "") {
    animateTextUpdate(currentPriceNode, formatPrice(quote.price), quote.price);
  }
  const profit = recommendationTrackProfit(trackedPrice, quote.price);
  if (pnlValueNode && profit.value !== null) {
    animateTextUpdate(pnlValueNode, formatPriceChange(profit.value), profit.value);
    setTone(pnlValueNode, profit.value);
  }
  if (pnlRateNode && profit.rate !== null) {
    animateTextUpdate(pnlRateNode, formatPercent(profit.rate), profit.rate);
    setTone(pnlRateNode, profit.rate);
  }
}

async function loadRecommendationHistory(options = {}) {
  const force = options.force !== false;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("recommend-history");
  const tracks = readRecommendationTracks();
  state.recommendTrackRequestId += 1;
  const requestId = state.recommendTrackRequestId;
  updateRecommendationTrackMeta();
  elements.recommendHistoryList.innerHTML = "";
  closeListQuoteStreams();
  if (!tracks.length) {
    elements.recommendHistoryList.appendChild(el("p", "muted", "추천 카드에서 종목별 추적하기를 누르면, 누른 시점의 주당 단가와 현재 손익률을 여기서 바로 비교할 수 있습니다."));
    renderSectionShell();
    return;
  }
  for (const track of tracks) {
    elements.recommendHistoryList.appendChild(createRecommendationTrackCard(track));
    connectListQuoteStream(track.code);
  }
  await Promise.all(
    tracks.map(async (track) => {
      try {
        const url = `/us/stocks/${encodeURIComponent(track.code)}/dashboard?refresh=1`;
        const dashboard = await fetchJsonCached(
          force ? liveUrl(url) : url,
          { force, ttlMs: force ? 0 : ttlMs },
        );
        if (state.recommendTrackRequestId !== requestId || state.view !== "recommend-history") {
          return;
        }
        const currentCard = elements.recommendHistoryList.querySelector(`.recommend-track-card[data-code="${selectorEscape(track.code)}"]`);
        if (currentCard) {
          currentCard.replaceWith(createRecommendationTrackCard(track, dashboard));
        }
      } catch {
        return;
      }
    }),
  );
  syncSectionShellMeta();
}

function renderRecommendationHistory() {
  void loadRecommendationHistory();
}

function loadRecommendationSnapshot(snapshotId) {
  const snapshot = readRecommendationHistory().find((item) => item.id === snapshotId);
  if (!snapshot) {
    return;
  }
  renderRecommendations(snapshot, { save: false, fromHistory: true });
  setView("recommend");
}

function deleteRecommendationSnapshot(snapshotId) {
  writeRecommendationHistory(readRecommendationHistory().filter((item) => item.id !== snapshotId));
  renderRecommendationHistory();
}

function setRecommendStatus(message = "") {
  elements.recommendStatus.textContent = message;
  elements.recommendStatus.parentElement.hidden = !message;
  syncSectionShellMeta();
}

function updateRecommendationItemFromDashboard(item, dashboard) {
  return {
    ...item,
    price: dashboard.quote?.price,
    change_rate: dashboard.quote?.change_rate,
    one_month_return: dashboard.momentum?.one_month_return,
    three_month_return: dashboard.momentum?.three_month_return,
    trading_value: dashboard.quote?.trading_value ?? dashboard.momentum?.latest_trading_value,
    chart_analysis: dashboard.chart_analysis || item.chart_analysis,
  };
}

async function refreshRecommendationCard(card, button) {
  const item = card.recommendationItem;
  if (!item || !item.code) {
    return;
  }
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "갱신 중";
  const url = `/us/stocks/${encodeURIComponent(item.code)}/dashboard?refresh=1`;
  clearCachedUrl(url);
  clearCachedUrl(`/us/stocks/${encodeURIComponent(item.code)}/dashboard`);
  try {
    const dashboard = await fetchJsonCached(url, { force: true, ttlMs: 0 });
    const updatedItem = updateRecommendationItemFromDashboard(item, dashboard);
    const nextCard = createRecommendationCard(updatedItem);
    card.replaceWith(nextCard);
    connectListQuoteStream(updatedItem.code);
  } catch {
    button.textContent = "실패";
    window.setTimeout(() => {
      button.disabled = false;
      button.textContent = originalText;
    }, 1200);
  }
}

function buildRecommendationAIExplanation(item) {
  const chart = item.chart_analysis || {};
  const score = toNumber(item.score) ?? 0;
  const price = toNumber(item.price);
  const oneMonth = toNumber(item.one_month_return);
  const threeMonth = toNumber(item.three_month_return);
  const change = toNumber(item.change_rate);
  const support = toNumber(chart.support);
  const resistance = toNumber(chart.resistance);
  const chartScore = toNumber(chart.score);
  const volumeRatio = toNumber(chart.volume_ratio);
  const distanceToResistance = toNumber(chart.distance_to_resistance);
  const distanceToSupport = toNumber(chart.distance_to_support);
  const componentScores = item.component_scores || {};
  const valuationScore = toNumber(componentScores.valuation);
  const sentimentScore = toNumber(componentScores.sentiment);
  const flowsScore = toNumber(componentScores.flows);

  let decision = "보류";
  if (score >= 68 && chartScore >= 65 && price && support && distanceToResistance !== null && distanceToResistance >= 3) {
    decision = "매수";
  } else if (score < 48 || (price && support && price < support) || chartScore < 45) {
    decision = "매도";
  }

  const entryLow = price && support ? Math.max(support, Math.round(price * 0.985 / 100) * 100) : price ? Math.round(price * 0.985 / 100) * 100 : null;
  const entryHigh = price ? Math.round(price * 1.005 / 100) * 100 : null;
  const breakout = price && resistance ? Math.round(Math.min(resistance * 1.01, price * 1.035) / 100) * 100 : price ? Math.round(price * 1.025 / 100) * 100 : null;
  const reduce = price && support ? Math.round(Math.max(support * 0.985, price * 0.965) / 100) * 100 : price ? Math.round(price * 0.965 / 100) * 100 : null;
  const target = price && resistance ? Math.round(Math.max(resistance, price * 1.04) / 100) * 100 : price ? Math.round(price * 1.04 / 100) * 100 : null;

  const summary =
    decision === "매수"
      ? `${item.name}은 지금 바로 크게 따라가기보다 ${formatPrice(entryLow)}~${formatPrice(entryHigh)} 구간에서 나눠 담는 쪽이 현실적입니다.`
      : decision === "매도"
        ? `${item.name}은 추천 점수나 차트 흐름이 약해져서 새 매수보다 보유 비중을 줄이는 판단이 우선입니다.`
        : `${item.name}은 관심 종목으로 볼 수 있지만, 현재 가격에서는 바로 매수보다 가격이 조금 내려오거나 위 가격을 뚫는 흐름을 기다리는 편이 낫습니다.`;

  const plain = [
    `현재가는 ${formatPrice(price)}이고 오늘 등락률은 ${formatPercent(change)}입니다.`,
    `최근 1개월 수익률은 ${formatPercent(oneMonth)}, 3개월 수익률은 ${formatPercent(threeMonth)}입니다. 이미 많이 오른 종목은 좋은 종목이어도 한 번에 사면 손실 구간을 크게 맞을 수 있습니다.`,
    `추천 점수는 ${formatNumber(score)}점이고 AI 차트 점수는 ${formatNumber(chartScore)}점입니다. 점수는 “좋은 기업인가”보다 “지금 가격에서 행동하기 쉬운가”에 가깝게 봅니다.`,
  ];
  if (valuationScore !== null) {
    plain.push(`밸류에이션 점수는 ${formatNumber(valuationScore)}점입니다. 낮으면 가격 부담이 크다는 뜻이고, 높으면 현재 가격이 과거와 비교해 덜 부담스럽다는 뜻입니다.`);
  }
  if (flowsScore !== null) {
    plain.push(`유동성 점수는 ${formatNumber(flowsScore)}점입니다. 미장에서는 거래대금, ETF 흐름, 대형주 선호가 함께 좋아질 때 가격이 버티는 힘이 커질 수 있습니다.`);
  }
  if (sentimentScore !== null) {
    plain.push(`뉴스 분위기 점수는 ${formatNumber(sentimentScore)}점입니다. 좋은 뉴스가 많아도 가격에 이미 반영된 경우가 있으니 가격 위치와 함께 봐야 합니다.`);
  }

  const timing = [
    price ? `현실적인 1차 매수 구간: ${formatPrice(entryLow)}~${formatPrice(entryHigh)}. 이 구간은 현재가에서 너무 멀지 않게 잡은 가격대입니다.` : "현재가 데이터가 부족해서 매수 구간을 숫자로 잡기 어렵습니다.",
    breakout ? `강하게 따라붙을 수 있는 가격: ${formatPrice(breakout)} 이상. 이 가격 위에서는 위로 가려는 힘이 생겼다고 보고 소액만 접근하는 편이 낫습니다.` : "돌파 가격은 저항선 데이터가 부족해 계산하지 않았습니다.",
    reduce ? `손실을 줄일 가격: ${formatPrice(reduce)} 아래. 이 가격 아래에서는 생각이 틀렸다고 보고 비중을 줄이는 기준으로 삼습니다.` : "손실 제한 가격은 지지선 데이터가 부족해 계산하지 않았습니다.",
    target ? `1차 이익실현 참고 가격: ${formatPrice(target)} 부근. 욕심내기보다 일부 수익을 잠그는 구간으로 봅니다.` : "이익실현 가격은 저항선 데이터가 부족해 계산하지 않았습니다.",
  ];

  const risks = [];
  if (oneMonth !== null && oneMonth > 25) {
    risks.push("최근 1개월 상승률이 커서 추격매수 부담이 있습니다.");
  }
  if (threeMonth !== null && threeMonth > 60) {
    risks.push("3개월 기준으로 많이 오른 상태라 작은 악재에도 조정이 깊어질 수 있습니다.");
  }
  if (distanceToSupport !== null && distanceToSupport > 12) {
    risks.push("현재가가 손실 제한 가격과 멀어 손절 폭이 커질 수 있습니다.");
  }
  if (volumeRatio !== null && volumeRatio < 0.9) {
    risks.push("거래량이 충분히 붙지 않아 상승 힘이 약할 수 있습니다.");
  }
  if (!risks.length) {
    risks.push("큰 위험 신호는 많지 않지만, 추천 종목도 가격이 빠르게 변하면 판단을 다시 해야 합니다.");
  }

  return { decision, summary, plain, timing, risks };
}

function renderRecommendationAIExplanation(card) {
  const item = card.recommendationItem;
  if (!item) {
    return;
  }
  const payload = buildRecommendationAIExplanation(item);
  let panel = card.querySelector(".recommend-ai-panel");
  if (!panel) {
    panel = el("section", "recommend-ai-panel");
    const body = card.querySelector(".recommend-body");
    card.insertBefore(panel, body || null);
  }
  panel.innerHTML = "";
  const head = el("div", "recommend-ai-head");
  head.append(el("h3", "", "AI 설명"), el("strong", `recommend-ai-decision ${payload.decision}`, payload.decision));
  const summary = el("p", "recommend-ai-summary", payload.summary);
  const grid = el("div", "recommend-ai-grid");
  for (const [title, items] of [
    ["쉽게 풀어보기", payload.plain],
    ["매매 타이밍", payload.timing],
    ["조심할 점", payload.risks],
  ]) {
    const box = el("section");
    box.appendChild(el("h4", "", title));
    const list = el("ul");
    appendListItems(list, items, "표시할 설명이 부족합니다.");
    box.appendChild(list);
    grid.appendChild(box);
  }
  panel.append(head, summary, grid);
}

function createRecommendationUsSectorSummary(item, usSectorMoves = state.usSectorMoves) {
  const section = el("section", "recommend-us-sector");
  section.dataset.field = "us_sector";
  section.appendChild(el("h3", "", `${usSectorSessionLabel(usSectorMoves)} 섹터`));
  const moves = relatedUsSectorMoves(item, item, usSectorMoves);
  if (!moves.length || moves.every((move) => move.change_rate === null || move.change_rate === undefined)) {
    section.appendChild(el("p", "muted", "관련 섹터 등락률 불러오는 중"));
    return section;
  }
  const chips = el("div", "recommend-us-sector-chips");
  for (const move of moves) {
    const chip = el("span", toNumber(move.change_rate) >= 0 ? "positive" : "negative");
    chip.append(el("em", "", move.label), document.createTextNode(formatPercent(move.change_rate)));
    chips.appendChild(chip);
  }
  section.appendChild(chips);
  return section;
}

function updateRecommendationUsSectorCards(usSectorMoves = state.usSectorMoves) {
  for (const card of elements.recommendList.querySelectorAll(".recommend-card")) {
    const item = card.recommendationItem;
    if (!item) {
      continue;
    }
    const next = createRecommendationUsSectorSummary(item, usSectorMoves);
    const current = card.querySelector("[data-field='us_sector']");
    if (current) {
      current.replaceWith(next);
    } else {
      const actions = card.querySelector(".recommend-card-actions");
      if (actions) {
        actions.parentElement.insertBefore(next, actions);
      }
    }
  }
}

function createRecommendationCard(item) {
  const componentScores = item.component_scores || {};
  const card = el("article", "recommend-card");
  card.dataset.code = item.code || "";
  card.dataset.liveCode = item.code || "";
  card.recommendationItem = item;
  const head = el("div", "recommend-head");
  const actionText = item.action || "관찰";
  const rank = el("div", "recommend-rank", `#${item.rank} · ${actionText}`);
  rank.classList.add(actionText.includes("매수") ? "buy" : "watch");
  const rankLine = el("div", "recommend-rank-line");
  const topActions = el("div", "recommend-top-actions");
  const refreshButton = el("button", "recommend-refresh", "새로고침");
  refreshButton.type = "button";
  refreshButton.dataset.code = item.code || "";
  const trackButton = el("button", "recommend-track-button", isTrackedRecommendation(item.code) ? "추적 보기" : "추적하기");
  trackButton.type = "button";
  trackButton.dataset.code = item.code || "";
  trackButton.classList.toggle("active", isTrackedRecommendation(item.code));
  const watchButton = el("button", "recommend-watch-button", isWatched(item.code) ? "관심 해제" : "관심 추가하기");
  watchButton.type = "button";
  watchButton.dataset.code = item.code || "";
  watchButton.classList.toggle("active", isWatched(item.code));
  const explainButton = el("button", "recommend-ai-button", "AI 설명 받기");
  explainButton.type = "button";
  topActions.append(trackButton, refreshButton);
  rankLine.append(rank, topActions);
  const name = el("a", "recommend-name");
  name.href = viewStockUrl(item);
  const nameStrong = el("strong", "", item.name);
  const nameMeta = el("span", "", `${item.code} · ${item.market}`);
  name.append(nameStrong, nameMeta);

  const score = el("div", "recommend-score");
  score.append(el("strong", "", String(item.score)), el("span", "", "점"));

  const metrics = el("div", "recommend-metrics");
  const metricRows = [
    ["현재가", formatPrice(item.price), "price", item.price],
    ["등락률", formatPercent(item.change_rate), "change_rate", item.change_rate],
    ["1개월", formatPercent(item.one_month_return), "", item.one_month_return],
    ["3개월", formatPercent(item.three_month_return), "", item.three_month_return],
    ["거래대금", formatMoney(item.trading_value), "trading_value", item.trading_value],
  ];
  for (const [label, value, liveField, rawValue] of metricRows) {
    const row = el("div");
    const strong = el("strong", "", value);
    if (liveField) {
      strong.dataset.liveField = liveField;
    }
    if (rawValue !== null && rawValue !== undefined && rawValue !== "") {
      strong.dataset.rawValue = String(rawValue);
    }
    if (label === "등락률") {
      setTone(strong, rawValue);
    }
    row.append(recommendTermLabel(label), strong);
    metrics.appendChild(row);
  }
  const actions = el("div", "recommend-card-actions");
  actions.append(watchButton, explainButton);
  head.append(rankLine, name, score, metrics, createRecommendationUsSectorSummary(item), actions);

  const body = el("div", "recommend-body");
  const chart = item.chart_analysis || {};
  const chartBox = el("section", "recommend-chart");
  chartBox.appendChild(el("h3", "", "AI 차트 분석"));
  const chartSummary = el("div", "recommend-chart-summary");
  const chartRows = [
    ["차트점수", formatNumber(chart.score)],
    ["판단", chart.stance || "-"],
    ["추세", chart.trend || "-"],
    ["셋업", chart.setup || "-"],
    ["리스크", chart.risk_level || "-"],
    ["거래량", formatRatio(chart.volume_ratio)],
    ["지지", chart.support ? `${formatPrice(chart.support)} (${formatPercent(chart.distance_to_support)})` : "-"],
    ["저항", chart.resistance ? `${formatPrice(chart.resistance)} (${formatPercent(chart.distance_to_resistance)})` : "-"],
  ];
  for (const [label, value] of chartRows) {
    const row = el("div");
    row.append(recommendTermLabel(label), el("strong", "", value));
    chartSummary.appendChild(row);
  }
  const chartSignals = document.createElement("ul");
  appendListItems(chartSignals, chart.signals, "뚜렷한 차트 신호가 아직 약합니다.");
  chartBox.append(chartSummary, chartSignals);

  const components = el("section");
  components.appendChild(el("h3", "", "항목별 점수"));
  const componentGrid = el("div", "component-grid");
  for (const [key, label] of Object.entries(COMPONENT_LABELS)) {
    const row = el("div");
    row.append(componentTermLabel(key, label), el("strong", "", formatNumber(componentScores[key])));
    componentGrid.appendChild(row);
  }
  components.appendChild(componentGrid);

  const reasonWrap = el("section", "recommend-reasons");
  const reasons = el("div");
  reasons.appendChild(el("h3", "", "추천 이유"));
  const reasonList = document.createElement("ul");
  appendListItems(reasonList, item.reasons, "뚜렷한 긍정 이유가 부족합니다.");
  reasons.appendChild(reasonList);

  const risks = el("div");
  risks.appendChild(el("h3", "", "확인 리스크"));
  const riskList = document.createElement("ul");
  appendListItems(riskList, item.risks, "주요 리스크 신호는 제한적입니다.");
  risks.appendChild(riskList);
  reasonWrap.append(reasons, risks);

  body.append(chartBox, components, reasonWrap);
  card.append(head, body);
  return card;
}

function appendRecommendationCard(item) {
  const card = createRecommendationCard(item);
  elements.recommendList.appendChild(card);
  connectListQuoteStream(item.code);
}

function renderRecommendations(payload, options = {}) {
  if (options.usSectorMoves) {
    state.usSectorMoves = options.usSectorMoves;
  }
  const rankedItems = rerankRecommendationItems(payload.items || []);
  const normalizedPayload = {
    ...payload,
    items: rankedItems,
  };
  state.currentRecommendations = normalizedPayload;
  if (options.save) {
    saveRecommendationSnapshot(normalizedPayload);
  }
  updateRecommendationTrackMeta();
  const filters = getViewFilters("recommend");
  const filteredItems = rankedItems.filter((item) => {
    const action = String(item.action || "").toLowerCase();
    const categoryMatch =
      filters.category === "all" ||
      (filters.category === "buy" && (action.includes("매수") || action.includes("buy"))) ||
      (filters.category === "hold" && (action.includes("관심") || action.includes("watch"))) ||
      (filters.category === "review" && (action.includes("보류") || action.includes("hold")));
    const marketMatch = filters.auxOne === "all" || item.market === filters.auxOne;
    return categoryMatch && marketMatch && matchesKeyword(filters.keyword, item.name, item.code, item.market, item.action);
  });
  const recommendMetaText = payload.as_of ? `기준 시간 : ${formatDate(payload.as_of)}` : "";
  elements.recommendMeta.textContent = recommendMetaText;
  elements.recommendMeta.hidden = !recommendMetaText;
  setRecommendStatus("");
  closeListQuoteStreams();
  elements.recommendList.innerHTML = "";
  const items = filteredItems.slice(0, RECOMMENDATION_LIMIT);
  if (!items.length) {
    setRecommendStatus("추천 후보를 찾지 못했습니다.");
    renderSectionShell();
    return;
  }
  for (const item of items) {
    appendRecommendationCard(item);
  }
  updateRecommendationTrackButtons();
  scheduleUsSectorRefresh(state.usSectorMoves);
  renderSectionShell();
}

function appendTags(parent, items) {
  for (const item of items || []) {
    parent.appendChild(el("span", "tag", item));
  }
}

function setTrendTab(tabName) {
  const active = ["events", "past", "live"].includes(tabName) ? tabName : "events";
  if (elements.trendTabsWrap) {
    elements.trendTabsWrap.hidden = active === "past";
  }
  for (const tab of elements.trendTabs) {
    tab.classList.toggle("active", tab.dataset.trendTab === active);
  }
  elements.trendEventsPanel.hidden = active !== "events";
  elements.trendPastPanel.hidden = active !== "past";
  elements.trendLivePanel.hidden = active !== "live";
}

function appendThreadItem(parent, item) {
  const node = el("a", "thread-item");
  node.href = item.url || "#";
  if (item.url) {
    node.target = "_blank";
    node.rel = "noreferrer";
  }
  const meta = el("div", "thread-meta", `${formatDate(item.published_at)} · ${item.source}`);
  const title = el("strong", "", item.title);
  const tags = el("div", "thread-tags");
  tags.append(el("span", "thread-tag", item.category), el("span", `thread-tag impact-${item.impact}`, item.impact));
  const leaders = el("div", "thread-leader-stocks");
  for (const stock of (item.leader_stocks || []).slice(0, 4)) {
    leaders.appendChild(el("span", "thread-tag leader-stock-tag", stock));
  }
  node.append(meta, title, tags);
  if (leaders.children.length > 0) {
    node.appendChild(leaders);
  }
  parent.appendChild(node);
}

function appendThreadGroup(parent, label, items, tone) {
  const group = el("section", `thread-group ${tone}`);
  group.appendChild(el("h3", "thread-group-title", label));
  if (!items || items.length === 0) {
    group.appendChild(el("p", "muted", `${label} 기사 없음`));
  } else {
    for (const item of items) {
      appendThreadItem(group, item);
    }
  }
  parent.appendChild(group);
}

function trendEventAxes(item) {
  const axes = Array.isArray(item.event_axes) ? item.event_axes.filter(Boolean) : [];
  return axes.length > 0 ? axes : (TREND_FOCUS_EVENT_AXES[item.title] || []);
}

function isFocusedTrendEvent(item) {
  return trendEventAxes(item).length > 0;
}

function focusedTrendEvents(items) {
  return (items || []).filter(isFocusedTrendEvent);
}

function hasAnyKeyword(text, keywords = []) {
  const lowerText = String(text || "").toLowerCase();
  return keywords.some((keyword) => lowerText.includes(String(keyword).toLowerCase()));
}

function uniqueLimited(items = [], limit = 6) {
  return Array.from(new Set((items || []).filter(Boolean))).slice(0, limit);
}

function isFocusedTrendTimelineItem(item) {
  const text = `${item.title || ""} ${item.category || ""} ${item.related_event || ""}`;
  return /(금리|달러|yield|10y|fomc|fed|ai|capex|gpu|hbm|반도체|risk-on|risk-off)/i.test(text);
}

function trendEventWeight(item = {}) {
  const base = MARKET_IMPACT_IMPORTANCE_WEIGHT[item.importance] || 10;
  const startsAt = item.starts_at ? new Date(item.starts_at).getTime() : null;
  if (!Number.isFinite(startsAt)) {
    return base;
  }
  const daysAway = Math.abs(startsAt - Date.now()) / 86_400_000;
  if (daysAway <= 1) {
    return base + 8;
  }
  if (daysAway <= 3) {
    return base + 4;
  }
  return base;
}

function marketImpactDirectionScore(text, factor, fallbackImpact = "") {
  let score = 0;
  for (const word of factor.goodWords || []) {
    if (hasAnyKeyword(text, [word])) {
      score += 1;
    }
  }
  for (const word of factor.badWords || []) {
    if (hasAnyKeyword(text, [word])) {
      score -= 1;
    }
  }
  if (/(호재|수혜|개선|완화|안정|강세|투자 확대|수요 호조|랠리)/i.test(text)) {
    score += 1;
  }
  if (/(악재|부담|압박|약화|위험|투자 둔화|조정|risk-off|긴축)/i.test(text)) {
    score -= 1;
  }
  if (fallbackImpact === "호재") {
    score += 1;
  } else if (fallbackImpact === "악재") {
    score -= 1;
  }
  return score;
}

function buildMarketImpactModel(payload = {}) {
  const sourceEvents = [...(payload.events || []), ...(payload.past_events || [])];
  const sourceTimeline = payload.timeline || [];
  const factors = MARKET_IMPACT_FACTORS.map((factor) => ({
    ...factor,
    raw: 4,
    directionScore: 0,
    reasons: [],
    stocks: [...factor.defaultStocks],
  }));

  for (const event of sourceEvents) {
    const text = [
      event.title,
      event.category,
      event.expected_impact,
      ...(event.event_axes || []),
      ...(event.affected_variables || []),
      ...(event.affected_sectors || []),
      ...(event.watch_points || []),
    ].join(" ");
    for (const factor of factors) {
      if (!hasAnyKeyword(text, factor.keywords)) {
        continue;
      }
      const weight = trendEventWeight(event);
      factor.raw += weight;
      factor.directionScore += marketImpactDirectionScore(text, factor) * weight;
      factor.reasons.push(`${event.title}: ${event.expected_impact}`);
    }
  }

  for (const item of sourceTimeline) {
    const text = [item.title, item.category, item.related_event, item.impact].join(" ");
    for (const factor of factors) {
      if (!hasAnyKeyword(text, factor.keywords)) {
        continue;
      }
      const weight = item.impact === "호재" ? 11 : 10;
      factor.raw += weight;
      factor.directionScore += marketImpactDirectionScore(text, factor, item.impact) * weight;
      factor.reasons.push(`${item.source || "뉴스"}: ${item.title}`);
      factor.stocks.push(...(item.leader_stocks || []));
    }
  }

  const rawTotal = factors.reduce((sum, factor) => sum + factor.raw, 0) || 1;
  const enrichedFactors = factors
    .map((factor) => {
      const percent = Math.max(4, Math.round((factor.raw / rawTotal) * 1000) / 10);
      const status = factor.directionScore >= 0 ? "호재" : "악재";
      return {
        ...factor,
        percent,
        status,
        summary: status === "호재" ? factor.goodText : factor.badText,
        interpretation: status === "호재" ? factor.goodText : factor.badText,
        reasons: uniqueLimited(factor.reasons, 3),
        leader_stocks: uniqueLimited(factor.stocks, 6),
        affected_sectors: uniqueLimited([factor.label, ...(factor.affected_sectors || [])], 4),
      };
    })
    .sort((a, b) => b.percent - a.percent);

  const goodWeight = enrichedFactors
    .filter((factor) => factor.status === "호재")
    .reduce((sum, factor) => sum + factor.percent, 0);
  const badWeight = enrichedFactors
    .filter((factor) => factor.status === "악재")
    .reduce((sum, factor) => sum + factor.percent, 0);
  const marketStatus = goodWeight >= badWeight ? "호재 우위" : "리스크 우위";
  const leadFactor = enrichedFactors[0];
  const summary = marketStatus === "호재 우위"
    ? `${leadFactor.label} 영향이 가장 크고, 현재는 호재 축이 더 우세합니다.`
    : `${leadFactor.label} 영향이 가장 크고, 현재는 리스크 관리가 더 우선입니다.`;

  return {
    asOf: payload.as_of,
    factors: enrichedFactors,
    goodWeight,
    badWeight,
    marketStatus,
    summary,
  };
}

function appendTrendEvent(item, parent = elements.trendEvents) {
  const card = el("article", "trend-event");
  card.dataset.eventId = item.id;
  const head = el("div", "trend-event-head");
  const title = el("div", "trend-event-title");
  const schedule = el("div", "event-schedule");
  const dateLabel = formatDate(item.starts_at);
  schedule.append(el("span", "", "발표"), el("strong", "", dateLabel));
  title.append(schedule, el("strong", "", item.title));
  const axisBadges = el("div", "event-axis-badges");
  for (const axis of trendEventAxes(item)) {
    axisBadges.appendChild(el("span", `event-axis-badge ${TREND_AXIS_CLASS[axis] || ""}`, axis));
  }
  if (axisBadges.children.length > 0) {
    title.appendChild(axisBadges);
  } else {
    title.appendChild(el("span", "", item.category));
  }
  const badgeWrap = el("div", "event-actions");
  badgeWrap.append(el("span", "event-badge", item.importance), el("button", "flow-button", "흐름 보기"));
  head.append(title, badgeWrap);

  const impact = el("p", "trend-impact", item.expected_impact);
  const tags = el("div", "tag-row");
  appendTags(tags, [...(item.affected_variables || []), ...(item.affected_sectors || [])]);

  const points = el("ul", "watch-points");
  appendListItems(points, item.watch_points, "추가 확인 포인트 없음");

  const source = el("a", "event-source", item.source_name);
  source.href = item.source_url;
  source.target = "_blank";
  source.rel = "noreferrer";

  card.append(head, impact, tags, points, source);
  parent.appendChild(card);
}

function appendGraphNode(parent, node, stockMap = {}) {
  const stockCode = node.kind === "stock" ? node.id.replace("stock-", "") : "";
  const stock = stockMap[stockCode];
  const item = stock ? el("a", `flow-node ${node.kind} ${node.polarity || "neutral"}`) : el("div", `flow-node ${node.kind} ${node.polarity || "neutral"}`);
  if (stock) {
    item.href = viewStockUrl(stock);
  }
  item.append(el("strong", "", node.label));
  if (node.detail) {
    item.appendChild(el("span", "", node.detail));
  }
  parent.appendChild(item);
}

function appendStockImpact(parent, stock) {
  const node = el("article", "impact-stock");
  node.dataset.code = stock.code || "";
  node.dataset.name = stock.name || "";
  node.dataset.market = stock.market || "";
  const head = el("div", "impact-stock-head");
  const identity = el("div", "impact-stock-identity");
  const title = el("a", "impact-stock-title", stock.name);
  title.href = viewStockUrl(stock);
  const score = el("span", "impact-stock-score", `${stock.impact_score}점 · ${stock.impact_direction}`);
  const watchButton = el("button", "impact-watch-button", "+");
  watchButton.type = "button";
  watchButton.dataset.code = stock.code || "";
  watchButton.dataset.name = stock.name || "";
  watchButton.dataset.market = stock.market || "";
  watchButton.classList.toggle("active", isWatched(stock.code));
  watchButton.setAttribute("aria-label", isWatched(stock.code) ? "관심 해제" : "관심 추가");
  watchButton.title = isWatched(stock.code) ? "관심 해제" : "관심 추가";
  const summary = el("p", "impact-stock-summary", summarizeImpactReason(stock));
  summary.title = Array.isArray(stock.reasons) ? stock.reasons.join(" / ") : "";
  identity.append(title, score);
  head.append(identity, watchButton);
  node.append(head, summary);
  parent.appendChild(node);
}

function summarizeImpactReason(stock) {
  const reasons = Array.isArray(stock.reasons) ? stock.reasons.filter(Boolean) : [];
  const first = reasons[0] || "";
  if (!first) {
    return stock.impact_direction || "";
  }
  if (first.includes("대표주 기준 이벤트 민감도 우선 매칭")) {
    return first.replace(" 기준 이벤트 민감도 우선 매칭", " 매칭");
  }
  if (first.includes("시가총액 상위 100위 내 ")) {
    return first.replace("시가총액 상위 100위 내 ", "").replace(" 노출", " 상위주");
  }
  return first;
}

function renderTrendGraph(card, graph) {
  const existing = card.querySelector(".event-flow");
  if (existing) {
    existing.remove();
  }
  const flow = el("section", "event-flow");
  flow.append(el("h3", "", "이벤트 영향 흐름도"));
  flow.append(el("p", "trend-impact", graph.scenario));
  const layers = el("div", "flow-layers");
  const mobileLayers = el("div", "flow-mobile");
  const stockMap = {};
  for (const stock of [...(graph.negative_stocks || []), ...(graph.positive_stocks || [])]) {
    stockMap[stock.code] = stock;
  }
  for (const layer of graph.layers) {
    const column = el("div", "flow-layer");
    column.appendChild(el("h4", "", layer.title));
    for (const node of layer.nodes) {
      appendGraphNode(column, node, stockMap);
    }
    layers.appendChild(column);
    const mobileGroup = el("section", "flow-mobile-group");
    mobileGroup.appendChild(el("h4", "", layer.title));
    for (const node of layer.nodes) {
      appendGraphNode(mobileGroup, node, stockMap);
    }
    mobileLayers.appendChild(mobileGroup);
  }
  const columns = el("div", "impact-columns");
  const negativeColumn = el("section", "impact-column negative-case");
  negativeColumn.appendChild(el("h3", "", graph.negative_label || "부정 시나리오 수혜"));
  const negativeStocks = el("div", "impact-stocks");
  for (const stock of graph.negative_stocks || []) {
    appendStockImpact(negativeStocks, stock);
  }
  if (!graph.negative_stocks || graph.negative_stocks.length === 0) {
    negativeStocks.appendChild(el("p", "muted", "매칭 종목 없음"));
  }
  negativeColumn.appendChild(negativeStocks);

  const positiveColumn = el("section", "impact-column positive-case");
  positiveColumn.appendChild(el("h3", "", graph.positive_label || "긍정 시나리오 수혜"));
  const positiveStocks = el("div", "impact-stocks");
  for (const stock of graph.positive_stocks || []) {
    appendStockImpact(positiveStocks, stock);
  }
  if (!graph.positive_stocks || graph.positive_stocks.length === 0) {
    positiveStocks.appendChild(el("p", "muted", "매칭 종목 없음"));
  }
  positiveColumn.appendChild(positiveStocks);
  columns.append(negativeColumn, positiveColumn);

  const scroll = el("div", "flow-scroll");
  scroll.appendChild(layers);
  flow.append(el("p", "scroll-hint", "좌우로 밀어서 흐름도를 볼 수 있습니다."), scroll, mobileLayers, el("h3", "", "결과 종목 영향도"), columns);
  card.appendChild(flow);
}

async function loadTrendGraph(card) {
  const eventId = card.dataset.eventId;
  if (!eventId) {
    return;
  }
  const existing = card.querySelector(".event-flow");
  if (existing && state.activeTrendGraph === eventId) {
    existing.remove();
    state.activeTrendGraph = null;
    return;
  }
  state.activeTrendGraph = eventId;
  const placeholder = el("section", "event-flow");
  placeholder.appendChild(el("p", "muted", "영향 흐름을 계산하는 중입니다."));
  const old = card.querySelector(".event-flow");
  if (old) {
    old.remove();
  }
  card.appendChild(placeholder);
  const button = card.querySelector(".flow-button");
  if (button) {
    button.disabled = true;
    button.textContent = "계산 중";
  }
  setFlowLoading(true);
  try {
    const graphUrl = `/us/market/trends/${encodeURIComponent(eventId)}/graph`;
    placeholder.remove();
    const graph = await Promise.race([
      fetchJsonCached(graphUrl, { ttlMs: 5 * 60 * 1000 }),
      rejectAfter(120_000, "trend graph timeout"),
    ]);
    renderTrendGraph(card, graph);
  } catch {
    placeholder.textContent = "영향 흐름을 불러오지 못했습니다.";
  } finally {
    setFlowLoading(false);
    if (button) {
      button.disabled = false;
      button.textContent = "흐름 보기";
    }
  }
}

function appendMarketImpactNode(parent, factor, index) {
  const direction = factor.direction || factor.status || "악재";
  const node = el("article", `market-impact-node ${factor.key || factor.className || ""} ${direction === "호재" ? "good" : "bad"} slot-${index}`);
  node.style.setProperty("--fill-level", `${Math.max(0, Math.min(100, factor.percent))}%`);
  const content = el("div", "market-impact-node-content");
  content.append(
    el("span", "market-impact-node-label", factor.label),
    el("strong", "", `${factor.percent.toFixed(1)}%`),
    el("em", direction === "호재" ? "good" : "bad", direction),
  );
  node.append(el("span", "market-impact-water"), content);
  parent.appendChild(node);
}

function appendMarketImpactDetail(parent, factor) {
  const direction = factor.direction || factor.status || "악재";
  const card = el("article", `market-impact-detail ${direction === "호재" ? "good" : "bad"}`);
  const head = el("div", "market-impact-detail-head");
  head.append(
    el("span", `market-impact-icon ${factor.key || factor.className || ""}`, factor.label),
    el("strong", "", factor.label),
    el("em", direction === "호재" ? "good" : "bad", `${direction} ${factor.percent.toFixed(1)}%`),
  );
  const summary = el("p", "", factor.interpretation || factor.summary || "현재 주요 이벤트 기준으로 영향 방향을 계산했습니다.");
  const evidenceGrid = el("div", "market-impact-metric-grid");
  for (const item of factor.evidence || []) {
    const metric = el("a", "market-impact-metric");
    metric.href = item.url || "#";
    if (item.url) {
      metric.target = "_blank";
      metric.rel = "noreferrer";
    }
    metric.append(
      el("span", "", `${item.source || "출처"} · ${item.metric || "지표"}`),
      el("strong", "", item.value_text || formatNumber(item.value)),
      el("small", "", `1일 ${item.change_1d_text || formatNumber(item.change_1d)} · 5일 ${item.change_5d_text || formatNumber(item.change_5d)}`),
    );
    evidenceGrid.appendChild(metric);
  }
  if (!evidenceGrid.childElementCount) {
    evidenceGrid.appendChild(el("p", "muted", "보조 지표 수집 대기 중"));
  }
  const sectorWrap = el("div", "market-impact-tag-block");
  sectorWrap.appendChild(el("span", "", "영향 축"));
  const sectors = el("div", "market-impact-stock-tags");
  for (const sector of factor.affected_sectors || []) {
    sectors.appendChild(el("span", "", sector));
  }
  sectorWrap.appendChild(sectors);
  const stockWrap = el("div", "market-impact-tag-block");
  stockWrap.appendChild(el("span", "", "대표 종목"));
  const stocks = el("div", "market-impact-stock-tags");
  for (const stock of factor.leader_stocks || factor.stocks || []) {
    const tag = el("a", "", stock);
    tag.href = viewStockUrl({ code: stock });
    stocks.appendChild(tag);
  }
  stockWrap.appendChild(stocks);
  card.append(head, summary, evidenceGrid, sectorWrap, stockWrap);
  parent.appendChild(card);
}

function normalizeMarketImpactModel(payload = {}) {
  if (Array.isArray(payload.factors) && payload.factors.length) {
    const factors = payload.factors.map((factor) => ({
      ...factor,
      percent: Number(factor.percent || 0),
      confidence: Number(factor.confidence || 0),
    }));
    return {
      asOf: payload.as_of,
      factors,
      goodWeight: Number(payload.good_weight || 0),
      badWeight: Number(payload.bad_weight || 0),
      marketStatus: payload.market_status || "리스크 우위",
      summary: payload.summary || "외부 요인의 미국증시 영향도를 계산했습니다.",
    };
  }
  return buildMarketImpactModel(payload);
}

function renderMarketImpactAnalysis(payload) {
  state.currentTrendImpactPayload = payload;
  const model = normalizeMarketImpactModel(payload);
  if (elements.trendTitle) {
    elements.trendTitle.textContent = "시장 영향도 분석";
  }
  if (elements.trendEventsTitle) {
    elements.trendEventsTitle.textContent = "외부요인 영향도 맵";
  }
  if (elements.trendTabsWrap) {
    elements.trendTabsWrap.hidden = true;
  }
  if (elements.trendMeta) {
    elements.trendMeta.textContent = model.asOf ? `기준 ${formatDate(model.asOf)}` : "";
    elements.trendMeta.hidden = true;
  }
  syncSectionShellMeta();
  elements.trendEventsPanel.hidden = false;
  elements.trendLivePanel.hidden = true;
  elements.trendPastPanel.hidden = true;
  elements.trendHeadline.textContent = "현재 시간 기준으로 금리, 달러, 채권, 원자재, AI 위험선호가 미국증시에 주는 영향을 계산했습니다.";
  elements.trendEvents.innerHTML = "";
  elements.trendPastEvents.innerHTML = "";
  elements.trendThread.innerHTML = "";

  const shell = el("section", "market-impact-dashboard");
  const hero = el("article", "market-impact-hero");
  const orbit = el("div", "market-impact-orbit");
  const center = el("div", `market-impact-center ${model.marketStatus === "호재 우위" ? "good" : "bad"}`);
  const centerLevel = model.marketStatus === "호재 우위" ? model.goodWeight : model.badWeight;
  center.style.setProperty("--fill-level", `${Math.max(0, Math.min(100, centerLevel))}%`);
  const centerContent = el("div", "market-impact-center-content");
  centerContent.append(
    el("span", "", "미국증시"),
    el("strong", "", model.marketStatus),
    el("small", "", `기준 ${formatDate(model.asOf)}`),
  );
  center.append(centerContent);
  orbit.append(center);
  const slotOrder = ["rate", "dollar", "bond", "commodity", "risk"];
  const orderedFactors = [...model.factors].sort((a, b) => slotOrder.indexOf(a.key) - slotOrder.indexOf(b.key));
  orderedFactors.forEach((factor, index) => appendMarketImpactNode(orbit, factor, index + 1));
  const heroCopy = el("div", "market-impact-copy");
  heroCopy.append(
    el("span", "section-eyebrow", "마켓 밸런스"),
    el("h2", "", model.summary),
    el("p", "", `호재 축 ${model.goodWeight.toFixed(1)}% · 악재 축 ${model.badWeight.toFixed(1)}%`),
  );
  hero.append(orbit, heroCopy);

  const flow = el("section", "market-impact-flow");
  const flowTitle = el("div", "market-impact-flow-title");
  flowTitle.append(el("strong", "", "현재 흐름"), el("span", "", "외부 변수 → 미국증시 → 대표 종목"));
  const flowGrid = el("div", "market-impact-flow-grid");
  for (const factor of model.factors.slice(0, 3)) {
    const direction = factor.direction || factor.status || "악재";
    const item = el("article", direction === "호재" ? "good" : "bad");
    item.append(
      el("span", "", `${factor.label} ${direction}`),
      el("strong", "", factor.interpretation || factor.summary),
      el("small", "", (factor.leader_stocks || factor.stocks || []).slice(0, 3).join(" · ")),
    );
    flowGrid.appendChild(item);
  }
  flow.append(flowTitle, flowGrid);

  const detailGrid = el("section", "market-impact-details");
  for (const factor of model.factors) {
    appendMarketImpactDetail(detailGrid, factor);
  }

  shell.append(hero, flow, detailGrid);
  elements.trendEvents.appendChild(shell);
  renderSectionShell();
}

function matchesTrendEventFilters(item, filters) {
  const keywordMatch = matchesKeyword(
    filters.keyword,
    item.title,
    item.category,
    item.expected_impact,
    ...(item.affected_variables || []),
    ...(item.affected_sectors || []),
  );
  const dateMatch = matchesDateRange(item.starts_at, filters.startDate, filters.endDate);
  const importanceMatch = filters.category === "all" || item.importance === filters.category;
  const categoryMatch = filters.auxOne === "all" || item.category === filters.auxOne;
  return keywordMatch && dateMatch && importanceMatch && categoryMatch;
}

function matchesTrendTimelineFilters(item, filters) {
  const keywordMatch = matchesKeyword(
    filters.keyword,
    item.title,
    item.category,
    item.related_event,
    ...(item.affected_variables || []),
    ...(item.affected_sectors || []),
    ...(item.leader_stocks || []),
  );
  const dateMatch = matchesDateRange(item.published_at || item.starts_at, filters.startDate, filters.endDate);
  const importanceMatch = filters.category === "all" || item.importance === filters.category;
  const categoryMatch = filters.auxOne === "all" || item.category === filters.auxOne;
  return keywordMatch && dateMatch && importanceMatch && categoryMatch;
}

function renderTrends(payload, activeTab = "events") {
  state.currentTrendPayload = payload;
  if (elements.trendMeta) {
    const rangeText = payload.window_start && payload.window_end
      ? `${formatDate(payload.window_start)} ~ ${formatDate(payload.window_end)}`
      : "";
    elements.trendMeta.textContent = rangeText;
    elements.trendMeta.hidden = true;
  }
  syncSectionShellMeta();
  if (elements.trendTitle) {
    elements.trendTitle.textContent = activeTab === "past" ? "지난 이벤트" : "트렌드 분석";
  }
  if (elements.trendEventsTitle) {
    elements.trendEventsTitle.textContent = activeTab === "past" ? "지난 이벤트" : "이벤트 캘린더";
  }
  elements.trendHeadline.textContent = payload.headline || "금리, 달러, 원자재, AI에 대한 주요 이벤트를 확인해보세요.";
  elements.trendEvents.innerHTML = "";
  elements.trendPastEvents.innerHTML = "";
  elements.trendThread.innerHTML = "";
  setTrendTab(activeTab);
  const filters = getViewFilters(activeTab === "past" ? "trend-past" : "trend");
  const events = focusedTrendEvents(payload.events).filter((item) => matchesTrendEventFilters(item, filters));
  const pastEvents = focusedTrendEvents(payload.past_events).filter((item) => matchesTrendEventFilters(item, filters));
  const timeline = (payload.timeline || [])
    .filter(isFocusedTrendTimelineItem)
    .filter((item) => matchesTrendTimelineFilters(item, filters));

  if (events.length === 0) {
    elements.trendEvents.appendChild(el("p", "muted", "다가오는 이벤트 없음"));
  } else {
    for (const item of events) {
      appendTrendEvent(item);
    }
  }

  if (pastEvents.length === 0) {
    elements.trendPastEvents.appendChild(el("p", "muted", "지난 이벤트 없음"));
  } else {
    for (const item of pastEvents) {
      appendTrendEvent(item, elements.trendPastEvents);
    }
  }

  if (timeline.length === 0) {
    elements.trendThread.appendChild(el("p", "muted", "타임라인 데이터 없음"));
  } else {
    const positiveItems = timeline.filter((item) => item.impact === "호재");
    const negativeItems = timeline.filter((item) => item.impact !== "호재");
    appendThreadGroup(elements.trendThread, "호재", positiveItems, "positive");
    appendThreadGroup(elements.trendThread, "악재", negativeItems, "negative");
  }
  renderSectionShell();
}

async function loadTrends(activeTab = state.view === "trend-past" ? "past" : "events", options = {}) {
  if (elements.trendRefresh) {
    elements.trendRefresh.disabled = true;
    elements.trendRefresh.textContent = "불러오는 중";
  }
  elements.trendHeadline.textContent = "다가오는 이벤트와 최신 타임라인을 정리하는 중입니다.";
  try {
    const force = options.force === true;
    const payload = await fetchJsonCached(
      force ? liveUrl("/us/market/trends?days=7") : "/us/market/trends?days=7",
      { force, ttlMs: force ? 0 : 60 * 1000 },
    );
    renderTrends(payload, activeTab);
  } catch {
    elements.trendHeadline.textContent = "트렌드 데이터를 불러오지 못했습니다.";
    renderSectionShell();
  } finally {
    if (elements.trendRefresh) {
      elements.trendRefresh.disabled = false;
      elements.trendRefresh.textContent = "새로고침";
    }
  }
}

async function loadMarketImpactAnalysis(options = {}) {
  if (elements.trendRefresh) {
    elements.trendRefresh.disabled = true;
    elements.trendRefresh.textContent = "불러오는 중";
  }
  if (elements.trendTitle) {
    elements.trendTitle.textContent = "시장 영향도 분석";
  }
  if (elements.trendEventsTitle) {
    elements.trendEventsTitle.textContent = "외부요인 영향도 맵";
  }
  if (elements.trendTabsWrap) {
    elements.trendTabsWrap.hidden = true;
  }
  if (elements.trendMeta) {
    elements.trendMeta.textContent = "";
    elements.trendMeta.hidden = true;
  }
  syncSectionShellMeta();
  elements.trendEventsPanel.hidden = false;
  elements.trendLivePanel.hidden = true;
  elements.trendPastPanel.hidden = true;
  elements.trendHeadline.textContent = "현재 시간 기준으로 외부 요인의 영향도를 계산하는 중입니다.";
  elements.trendEvents.innerHTML = "";
  elements.trendEvents.appendChild(el("p", "muted", "시장 영향도 계산 중"));
  try {
    const force = options.force === true;
    const ttlMs = options.ttlMs ?? pageEntryTtlMs("trend-impact");
    const payload = await fetchJsonCached(
      force ? liveUrl("/us/market/impact?refresh=true") : "/us/market/impact",
      { force, ttlMs: force ? 0 : ttlMs },
    );
    renderMarketImpactAnalysis(payload);
  } catch {
    try {
      const fallbackPayload = await fetchJsonCached(liveUrl("/us/market/trends?days=7"), { force: true, ttlMs: 0 });
      renderMarketImpactAnalysis(fallbackPayload);
      elements.trendHeadline.textContent = "보조 이벤트 기준으로 시장 영향도를 임시 표시합니다.";
    } catch {
      elements.trendHeadline.textContent = "시장 영향도 데이터를 불러오지 못했습니다.";
      elements.trendEvents.innerHTML = "";
      elements.trendEvents.appendChild(el("p", "muted", "시장 영향도 데이터 없음"));
      renderSectionShell();
    }
  } finally {
    if (elements.trendRefresh) {
      elements.trendRefresh.disabled = false;
      elements.trendRefresh.textContent = "새로고침";
    }
  }
}

async function loadRecommendations(options = {}) {
  const auto = options.auto === true;
  const recompute = options.recompute === true || (!auto && options.recompute !== false);
  const forceFetch = options.force === true || recompute;
  const saveSnapshot = options.save ?? !auto;
  const remaining = recommendationCooldownRemainingMs();
  if (!auto && remaining > 0) {
    updateRecommendationButtonState();
    setRecommendStatus(`다시 추천은 ${formatRecommendationCooldown(remaining)} 후 가능합니다.`);
    return;
  }

  state.recommendationLoading = true;
  updateRecommendationButtonState();
  setRecommendStatus(
    auto
      ? "추천 데이터를 불러오는 중입니다."
      : "NASDAQ·S&P 500 대표 종목에서 가격, 모멘텀, 거래대금, 뉴스 데이터를 새로 점수화하는 중입니다.",
  );
  elements.recommendList.innerHTML = "";
  renderSectionShell();
  const sectorMovesPromise = refreshUsSectorMoves({ force: forceFetch }).catch(() => null);
  const fetchRecommendations = () => fetchJsonCached(
    forceFetch
      ? liveUrl(`/us/market/recommendations?limit=${RECOMMENDATION_LIMIT}&candidate_limit=100&refresh=1`)
      : `/us/market/recommendations?limit=${RECOMMENDATION_LIMIT}&candidate_limit=100`,
    forceFetch ? { force: true, ttlMs: 0 } : {},
  );
  try {
    const payload = await fetchRecommendations();
    renderRecommendations(payload, { save: saveSnapshot, usSectorMoves: state.usSectorMoves });
    if (!auto && (payload.items || []).length > 0) {
      saveRecommendationCooldown();
    }
  } catch (error) {
    console.error("loadRecommendations failed", error);
    setRecommendStatus(
      auto
        ? "추천 데이터를 불러오지 못했습니다. 잠시 후 다시 들어와주세요."
        : "추천 데이터를 계산하지 못했습니다. 잠시 후 다시 눌러주세요.",
    );
    renderSectionShell();
  } finally {
    sectorMovesPromise.catch(() => {});
    connectUsSectorStream();
    state.recommendationLoading = false;
    updateRecommendationButtonState();
  }
}

function setLoading(code) {
  const pendingLabel = String(code || "").trim();
  state.pendingStockLabel = pendingLabel;
  state.currentStock = null;
  state.currentDashboard = null;
  elements.name.textContent = pendingLabel || "종목 분석";
  updateMobilePageTitle("stock");
  setText(elements.stockCardName, pendingLabel || "종목 분석");
  setText(elements.stockDetailTitle, pendingLabel ? `${pendingLabel} 상세 브리핑` : "종목 상세 브리핑");
  setText(elements.stockDetailSource, "실시간 시세 · 리서치 · 뉴스");
  if (elements.input) {
    elements.input.value = pendingLabel;
  }
  elements.meta.textContent = `${code} · 불러오는 중`;
  elements.meta.hidden = true;
  setActiveStockTab("summary", { preserveScroll: true });
  resetStockMiniChart();
  resetAIAnalysis();
}

function render(data) {
  const previousCode = state.currentStock?.code;
  state.pendingStockLabel = data.name || data.code || "";
  state.currentStock = { code: data.code, name: data.name, market: data.market };
  state.currentDashboard = data;
  resetAIAnalysis();
  setActiveStockTab("summary", { preserveScroll: true });
  elements.name.textContent = data.name;
  updateMobilePageTitle("stock");
  setText(elements.stockCardName, data.name);
  elements.meta.textContent = `${data.code} · ${data.market} · ${formatDate(data.as_of)}`;
  elements.meta.hidden = true;
  setText(elements.stockDetailTitle, `${data.name} 상세 브리핑`);
  setText(elements.stockDetailSource, `${data.market} · ${formatDate(data.as_of)} · 자동갱신`);
  elements.input.value = data.name;
  if (previousCode !== data.code) {
    for (const node of [elements.quotePrice, elements.stockChangeValue, elements.quoteChange, elements.stockVolume, elements.quoteValue, elements.quoteCap]) {
      if (node) {
        delete node.dataset.rawValue;
      }
    }
  }

  renderStockLiveSummary(data);
  updateQuoteStrip(data.quote);
  renderStockSummaryFallback(data);
  renderEvidenceSummary(data);
  loadStockMiniPrices(data.code, data.quote);
  connectQuoteStream(state.currentStock);

  const chart = data.chart_analysis || {};
  elements.chartScore.textContent = formatNumber(chart.score);
  elements.chartStance.textContent = chart.stance || "-";
  elements.chartTrend.textContent = chart.trend || "-";
  elements.chartSetup.textContent = chart.setup || "-";
  elements.chartRisk.textContent = chart.risk_level || "-";
  elements.chartVolume.textContent = formatRatio(chart.volume_ratio);
  elements.chartSupport.textContent = chart.support
    ? `${formatPrice(chart.support)} (${formatPercent(chart.distance_to_support)})`
    : "-";
  elements.chartResistance.textContent = chart.resistance
    ? `${formatPrice(chart.resistance)} (${formatPercent(chart.distance_to_resistance)})`
    : "-";
  setTone(elements.chartScore, chart.score - 50);
  appendListItems(elements.chartSignals, chart.signals, "뚜렷한 차트 신호가 아직 약합니다.");
  appendListItems(elements.chartRisks, chart.risks, "주요 차트 리스크 신호는 제한적입니다.");

  elements.estimateRevenue.textContent = formatMoney(data.revisions.estimated_revenue);
  elements.estimateProfit.textContent = formatMoney(data.revisions.estimated_operating_profit);
  elements.estimateEps.textContent = formatNumber(data.revisions.estimated_eps);
  elements.revisionCount.textContent = formatNumber(data.revisions.report_count_90d);
  setText(elements.stockLatestOpinion, data.revisions.latest_opinion || "-");
  setText(elements.stockTargetPrice, formatPrice(data.revisions.latest_target_price));
  elements.revisionRatio.textContent = formatPercent(data.revisions.target_up_ratio);
  elements.revisionUp.textContent = formatNumber(data.revisions.target_up_count);
  elements.revisionDown.textContent = formatNumber(data.revisions.target_down_count);
  setText(elements.stockLatestReportAt, `최근 리포트 ${formatDate(data.revisions.latest_report_at)}`);
  const revisionRatioValue = toNumber(data.revisions.target_up_ratio);
  setTone(elements.revisionRatio, revisionRatioValue === null ? 0 : revisionRatioValue - 50);

  elements.momentum1m.textContent = formatPercent(data.momentum.one_month_return);
  elements.momentum3m.textContent = formatPercent(data.momentum.three_month_return);
  elements.valueChange.textContent = formatPercent(data.momentum.trading_value_change);
  setTone(elements.momentum1m, data.momentum.one_month_return);
  setTone(elements.momentum3m, data.momentum.three_month_return);
  setTone(elements.valueChange, data.momentum.trading_value_change);

  elements.foreignFlow.textContent = formatMoney(data.flows.foreign_net_buy_20d);
  elements.institutionFlow.textContent = formatMoney(data.flows.institution_net_buy_20d);
  elements.foreignIntensity.textContent = formatPercent(data.flows.foreign_intensity);
  elements.institutionIntensity.textContent = formatPercent(data.flows.institution_intensity);
  setTone(elements.foreignFlow, data.flows.foreign_net_buy_20d);
  setTone(elements.institutionFlow, data.flows.institution_net_buy_20d);
  setTone(elements.foreignIntensity, data.flows.foreign_intensity);
  setTone(elements.institutionIntensity, data.flows.institution_intensity);

  elements.per.textContent = formatMultiple(data.valuation.per);
  elements.pbr.textContent = formatMultiple(data.valuation.pbr);
  elements.estimatedPer.textContent = formatMultiple(data.valuation.estimated_per);
  elements.industryPer.textContent = formatMultiple(data.valuation.industry_per);
  setText(elements.stockEps, formatNumber(data.valuation.eps ?? data.revisions.estimated_eps));
  const pbrValue = toNumber(data.valuation.pbr);
  const priceValue = toNumber(data.quote?.price);
  setText(elements.stockBps, pbrValue && priceValue ? formatPrice(priceValue / pbrValue) : "-");
  setText(elements.stockDividendYield, data.valuation.dividend_yield ? formatPercent(Number(data.valuation.dividend_yield) * 100) : "-");
  const dividendPerShare =
    priceValue !== null && data.valuation.dividend_yield !== null && data.valuation.dividend_yield !== undefined
      ? priceValue * (Number(data.valuation.dividend_yield) / 100)
      : null;
  setText(elements.stockDividendPerShare, dividendPerShare === null ? "-" : formatPrice(dividendPerShare));
  setText(elements.stockForeignRatio, "-");
  elements.perZ.textContent = data.valuation.per_zscore === null || data.valuation.per_zscore === undefined ? "자료 없음" : formatNumber(data.valuation.per_zscore);
  elements.pbrZ.textContent = data.valuation.pbr_zscore === null || data.valuation.pbr_zscore === undefined ? "자료 없음" : formatNumber(data.valuation.pbr_zscore);

  elements.latestRevenue.textContent = formatMoney(data.surprise.latest_revenue);
  elements.latestProfit.textContent = formatMoney(data.surprise.latest_operating_profit);
  elements.latestEps.textContent = formatNumber(data.surprise.latest_eps);
  elements.profitGrowth.textContent = formatPercent(data.surprise.operating_profit_growth);
  setTone(elements.profitGrowth, data.surprise.operating_profit_growth);

  const positiveCount = Number(data.sentiment.positive_count || 0);
  const negativeCount = Number(data.sentiment.negative_count || 0);
  const neutralCount = Number(data.sentiment.neutral_count || 0);
  const sentimentBias = positiveCount > negativeCount
    ? "긍정 우세"
    : negativeCount > positiveCount
      ? "부정 우세"
      : "혼조";
  elements.sentimentScore.textContent = formatPercent(data.sentiment.score);
  elements.sentimentCounts.textContent = `${sentimentBias} · 긍정 ${positiveCount} · 부정 ${negativeCount} · 중립 ${neutralCount}`;
  setTone(elements.sentimentScore, data.sentiment.score);
  renderEvents(elements.newsEvidenceList, (data.sentiment.latest_items || []).slice(0, 3));

  renderEvents(elements.surpriseList, data.surprise.latest_events);
  renderEvents(elements.guidanceList, data.guidance.latest_events);
  renderEvents(elements.newsList, data.sentiment.latest_items);

  elements.macroRate.textContent = formatPercent(data.macro_sensitivity.interest_rate);
  elements.macroFx.textContent = formatPercent(data.macro_sensitivity.fx ?? data.macro_sensitivity.fx_usdkrw);
  elements.macroCommodity.textContent = formatPercent(data.macro_sensitivity.commodity);
  elements.macroExport.textContent = formatPercent(data.macro_sensitivity.export ?? data.macro_sensitivity.exports);
  setTone(elements.macroRate, data.macro_sensitivity.interest_rate);
  setTone(elements.macroFx, data.macro_sensitivity.fx ?? data.macro_sensitivity.fx_usdkrw);
  setTone(elements.macroCommodity, data.macro_sensitivity.commodity);
  setTone(elements.macroExport, data.macro_sensitivity.export ?? data.macro_sensitivity.exports);
  updateWatchButton();
}

function commitStockRender(dashboard, options = {}) {
  const requestId = Number(options.requestId || 0);
  if (requestId && requestId !== state.stockLoadRequestId) {
    return false;
  }
  render(dashboard);
  if (options.activateView !== false && state.view === "stock") {
    history.replaceState(null, "", viewStockUrl({
      code: dashboard.code,
      name: dashboard.name,
      market: dashboard.market,
    }));
    setView("stock");
  }
  return true;
}

async function fetchAndRenderStockDashboard(code, options = {}) {
  const normalizedCode = String(code || "").trim().toUpperCase();
  if (!normalizedCode) {
    throw new Error("stock code required");
  }
  let renderedFast = false;
  try {
    const cachedDashboard = await fetchJsonCached(`/us/stocks/${encodeURIComponent(normalizedCode)}/dashboard`, { ttlMs: UI_CACHE_TTL_MS });
    renderedFast = commitStockRender(cachedDashboard, options);
  } catch {
    renderedFast = false;
  }
  try {
    const liveDashboard = await fetchJsonCached(liveUrl(`/us/stocks/${encodeURIComponent(normalizedCode)}/dashboard?refresh=1`), { force: true, ttlMs: 0 });
    if (commitStockRender(liveDashboard, options)) {
      return liveDashboard;
    }
    return null;
  } catch (error) {
    if (renderedFast) {
      return null;
    }
    throw error;
  }
}

async function resolveStock(query) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    return null;
  }
  try {
    return await fetchJsonCached(`/us/stocks/resolve?query=${encodeURIComponent(normalized)}`, { ttlMs: 5 * UI_CACHE_TTL_MS });
  } catch {
    return null;
  }
}

async function load(query, options = {}) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    return;
  }
  const requestId = ++state.stockLoadRequestId;
  const requestOptions = {
    activateView: options.activateView !== false,
    requestId,
  };
  const isStale = () => requestId !== state.stockLoadRequestId;
  hideSuggestions();
  setLoading(normalized);
  const directSymbol = looksLikeUsSymbol(normalized) ? normalized.toUpperCase() : "";
  if (directSymbol) {
    try {
      await fetchAndRenderStockDashboard(directSymbol, requestOptions);
      return;
    } catch {
      // Fall back to resolver for names, aliases, and symbols that need normalization.
    }
  }
  const stock = await resolveStock(normalized);
  if (isStale()) {
    return;
  }
  if (!stock) {
    state.pendingStockLabel = normalized;
    elements.name.textContent = normalized;
    updateMobilePageTitle("stock");
    elements.meta.textContent = `${normalized} · 데이터 없음`;
    elements.meta.hidden = true;
    setText(elements.stockCardName, normalized);
    setText(elements.stockDetailTitle, `${normalized} 상세 브리핑`);
    resetAIAnalysis();
    return;
  }
  try {
    await fetchAndRenderStockDashboard(stock.code, requestOptions);
  } catch {
    if (isStale()) {
      return;
    }
    state.pendingStockLabel = stock.name || stock.code || normalized;
    elements.name.textContent = stock.name;
    updateMobilePageTitle("stock");
    elements.meta.textContent = `${stock.code} · 데이터 없음`;
    elements.meta.hidden = true;
    setText(elements.stockCardName, stock.name);
    setText(elements.stockDetailTitle, `${stock.name} 상세 브리핑`);
    resetAIAnalysis();
    return;
  }
}

for (const item of elements.sideItems) {
  item.addEventListener("click", () => {
    if (item.dataset.view === "stock") {
      const query = focusStockView();
      const entryOptions = pageEntryRefreshOptions("stock", state.currentStock?.code || query);
      if (!state.currentStock?.code || entryOptions.force) {
        load(query);
      }
    } else {
      setView(item.dataset.view);
    }
    setMobileMenu(false);
  });
}

elements.sectionShellSecondaryTabs?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-shell-view]");
  if (!button) {
    return;
  }
  if (button.dataset.shellView === "stock") {
    const query = focusStockView();
    if (!state.currentStock?.code) {
      load(query);
    }
    setMobileMenu(false);
    return;
  }
  setView(button.dataset.shellView);
  setMobileMenu(false);
});

elements.sectionShellRefresh?.addEventListener("click", refreshCurrentShellView);
elements.sectionShellPrimaryAction?.addEventListener("click", () => runSectionShellAction(elements.sectionShellPrimaryAction.dataset.action));
elements.sectionShellSecondaryAction?.addEventListener("click", () => runSectionShellAction(elements.sectionShellSecondaryAction.dataset.action));
elements.sectionShellReset?.addEventListener("click", resetSectionShellFilters);

for (const input of [
  elements.sectionShellKeyword,
  elements.sectionShellStartDate,
  elements.sectionShellEndDate,
  elements.sectionShellCategory,
  elements.sectionShellAuxOne,
  elements.sectionShellAuxTwo,
]) {
  if (!input) {
    continue;
  }
  const eventName = input.tagName === "INPUT" && input.type === "text" ? "input" : "change";
  input.addEventListener(eventName, applySectionShellFilters);
  if (eventName !== "input") {
    input.addEventListener("input", applySectionShellFilters);
  }
}

elements.mobileMenuToggle?.addEventListener("click", () => {
  setMobileMenu(!document.body.classList.contains("mobile-menu-open"));
});

elements.mobileMenuScrim?.addEventListener("click", () => setMobileMenu(false));
elements.homeInstallButton?.addEventListener("click", handleHomeInstall);
elements.installSheetBackdrop?.addEventListener("click", closeInstallSheet);
elements.installSheetClose?.addEventListener("click", closeInstallSheet);

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (state.currentOverviewDetail) {
      closeOverviewDetail();
    }
    setMobileMenu(false);
    closeInstallSheet();
    document.querySelectorAll(".term-help.open").forEach((item) => item.classList.remove("open"));
  }
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 980) {
    setMobileMenu(false);
    resetPullRefreshIndicator({ immediate: true });
  }
  updateHomeInstallButton();
  updateResponsiveModeBadges();
});

window.addEventListener("touchstart", handlePullRefreshStart, { passive: true });
window.addEventListener("touchmove", handlePullRefreshMove, { passive: false });
window.addEventListener("touchend", handlePullRefreshEnd, { passive: true });
window.addEventListener("touchcancel", () => resetPullRefreshIndicator({ immediate: true }), { passive: true });

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  state.deferredInstallPrompt = event;
  updateHomeInstallButton();
});

window.addEventListener("appinstalled", () => {
  state.deferredInstallPrompt = null;
  closeInstallSheet();
  updateHomeInstallButton();
});

for (const tab of elements.rankTabs) {
  tab.addEventListener("click", () => {
    state.rankingCategory = tab.dataset.category;
    if (elements.rankCategorySelect) {
      elements.rankCategorySelect.value = state.rankingCategory;
    }
    for (const item of elements.rankTabs) {
      item.classList.toggle("active", item === tab);
    }
    loadMarketRankings();
  });
}

elements.rankCategorySelect?.addEventListener("change", () => {
  state.rankingCategory = elements.rankCategorySelect.value;
  for (const item of elements.rankTabs) {
    item.classList.toggle("active", item.dataset.category === state.rankingCategory);
  }
  loadMarketRankings();
});

for (const tab of elements.marketTabs) {
  tab.addEventListener("click", () => {
    setMarketFilter(tab.dataset.marketFilter);
    loadMarketRankings({ market: currentMarketFilter() });
  });
}
elements.watchToggle.addEventListener("click", toggleWatchCurrent);
elements.loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = elements.loginForm.querySelector("button");
  const originalText = button?.textContent || "시작하기";
  if (button) {
    button.disabled = true;
    button.textContent = "불러오는 중";
  }
  setLoginStatus("내 관심 ID로 들어가는 중");
  const ok = await applyWatchlistId(elements.loginInput.value, { merge: true });
  if (ok) {
    setLoginStatus("입장 완료", "success");
    hideLoginGate();
  } else {
    showLoginGate("ID를 확인해주세요. 2~40자 한글/영문/숫자/._-만 가능합니다.", { skipSplash: true });
  }
  if (button) {
    button.disabled = false;
    button.textContent = originalText;
  }
});
elements.watchlistIdForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  applyWatchlistId(elements.watchlistIdInput.value, { merge: true });
});
elements.logoutButton?.addEventListener("click", logoutWatchlistIdentity);
for (const tab of elements.stockSectionTabs) {
  tab.addEventListener("click", () => {
    setActiveStockTab(tab.dataset.stockTab || "summary");
  });
}
elements.aiAnalysisButton.addEventListener("click", () => {
  setActiveStockTab("strategy");
  loadAIAnalysis();
});
elements.recommendButton?.addEventListener("click", loadRecommendations);
elements.recommendArchiveButton?.addEventListener("click", () => setView("recommend-history"));
elements.recommendHistoryNewButton?.addEventListener("click", () => setView("recommend"));
elements.watchChartRefresh?.addEventListener("click", () => {
  for (const item of readWatchlist()) {
    clearCachedUrl(`/us/stocks/${encodeURIComponent(item.code)}/prices?limit=180`);
    clearCachedUrl(`/us/stocks/${encodeURIComponent(item.code)}/dashboard`);
  }
  loadWatchCharts();
});
elements.chartArchiveButton?.addEventListener("click", () => setView("chart-history"));
elements.chartHistoryBackButton?.addEventListener("click", () => setView("chart"));
elements.displayCurrencyToggle?.addEventListener("click", toggleCurrencyMode);
elements.recommendHistoryList.addEventListener("click", (event) => {
  const detailButton = event.target.closest(".recommend-track-detail-toggle");
  if (detailButton) {
    const card = detailButton.closest(".recommend-track-card");
    const detail = card?.querySelector(".recommend-track-detail");
    if (detail) {
      const nextOpen = detail.hidden;
      detail.hidden = !nextOpen;
      detailButton.textContent = nextOpen ? "접기" : "자세히 보기";
      detailButton.setAttribute("aria-expanded", String(nextOpen));
    }
    return;
  }

  const deleteButton = event.target.closest(".track-delete");
  if (deleteButton) {
    deleteRecommendationTrack(deleteButton.dataset.trackId);
    updateRecommendationTrackButtons();
    loadRecommendationHistory();
    return;
  }
});
elements.trendRefresh?.addEventListener("click", () => {
  if (state.view === "trend-impact") {
    loadMarketImpactAnalysis({ force: true });
    return;
  }
  loadTrends(state.view === "trend-past" ? "past" : "events", { force: true });
});
for (const tab of elements.trendTabs) {
  tab.addEventListener("click", () => setTrendTab(tab.dataset.trendTab));
}
function handleTrendEventClick(event) {
  const impactWatchButton = event.target.closest(".impact-watch-button");
  if (impactWatchButton) {
    event.preventDefault();
    event.stopPropagation();
    const added = toggleWatchlistItem({
      code: impactWatchButton.dataset.code,
      name: impactWatchButton.dataset.name,
      market: impactWatchButton.dataset.market,
    });
    impactWatchButton.classList.toggle("active", added);
    impactWatchButton.textContent = added ? "관심 해제" : "관심 추가";
    updateWatchButton();
    updateRecommendationWatchButtons();
    updateImpactWatchButtons();
    return;
  }
  if (event.target.closest("a")) {
    return;
  }
  if (event.target.closest(".event-flow")) {
    return;
  }
  const card = event.target.closest(".trend-event");
  if (card) {
    loadTrendGraph(card);
  }
}

elements.trendEvents.addEventListener("click", handleTrendEventClick);
elements.trendPastEvents.addEventListener("click", handleTrendEventClick);

elements.input.addEventListener("input", scheduleSuggestions);
elements.input.addEventListener("focus", () => {
  if (elements.input.value.trim()) {
    scheduleSuggestions();
  }
});
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" && !elements.suggestions.hidden) {
    event.preventDefault();
    setActiveSuggestion(state.suggestionIndex + 1);
  } else if (event.key === "ArrowUp" && !elements.suggestions.hidden) {
    event.preventDefault();
    setActiveSuggestion(state.suggestionIndex - 1);
  } else if (event.key === "Enter" && !elements.suggestions.hidden && state.suggestionIndex >= 0) {
    event.preventDefault();
    chooseSuggestion(state.suggestions[state.suggestionIndex]);
  } else if (event.key === "Escape") {
    hideSuggestions();
  }
});

elements.watchlistBody.addEventListener("click", (event) => {
  const button = event.target.closest(".remove-watch");
  if (!button) {
    return;
  }
  const code = button.dataset.code;
  writeWatchlist(readWatchlist().filter((item) => item.code !== code));
  updateWatchButton();
  loadWatchlist();
});

elements.stockOverviewView?.addEventListener("click", (event) => {
  const watchButton = event.target.closest("[data-overview-watch]");
  if (watchButton) {
    event.preventDefault();
    event.stopPropagation();
    const added = toggleWatchlistItem({
      code: watchButton.dataset.overviewWatch,
      name: watchButton.dataset.name,
      market: watchButton.dataset.market,
    });
    watchButton.classList.toggle("active", added);
    watchButton.title = added ? "관심 해제" : "관심 추가";
    updateWatchButton();
    loadStockOverview();
    return;
  }

  const stockButton = event.target.closest("[data-overview-detail-section][data-overview-detail-index]");
  if (stockButton) {
    const section = stockButton.dataset.overviewDetailSection;
    const index = Number(stockButton.dataset.overviewDetailIndex);
    if (section && Number.isInteger(index) && index >= 0) {
      openOverviewDetail(section, index);
    }
    return;
  }

  const targetButton = event.target.closest("[data-overview-target]");
  if (!targetButton) {
    return;
  }
  const nextView = overviewTargetView(targetButton.dataset.overviewTarget);
  if (nextView === "stock") {
    const query = focusStockView();
    if (!state.currentStock?.code) {
      load(query);
    }
    return;
  }
  setView(nextView);
});

elements.recommendList.addEventListener("click", (event) => {
  const watchButton = event.target.closest(".recommend-watch-button");
  if (watchButton) {
    const card = watchButton.closest(".recommend-card");
    const item = card?.recommendationItem;
    if (item) {
      const added = toggleWatchlistItem({ code: item.code, name: item.name, market: item.market });
      watchButton.classList.toggle("active", added);
      watchButton.textContent = added ? "관심 해제" : "관심 추가하기";
      updateWatchButton();
      updateRecommendationWatchButtons();
    }
    return;
  }

  const trackButton = event.target.closest(".recommend-track-button");
  if (trackButton) {
    const card = trackButton.closest(".recommend-card");
    const item = card?.recommendationItem;
    if (item) {
      trackRecommendationItem(item);
      updateRecommendationTrackButtons();
      updateRecommendationTrackMeta();
      setView("recommend-history");
    }
    return;
  }

  const explainButton = event.target.closest(".recommend-ai-button");
  if (explainButton) {
    const card = explainButton.closest(".recommend-card");
    if (card) {
      renderRecommendationAIExplanation(card);
      explainButton.textContent = "AI 설명 갱신";
    }
    return;
  }

  const button = event.target.closest(".recommend-refresh");
  if (!button) {
    return;
  }
  const card = button.closest(".recommend-card");
  if (card) {
    refreshRecommendationCard(card, button);
  }
});

elements.watchChartList.addEventListener("click", (event) => {
  const backButton = event.target.closest(".chart-detail-back");
  if (backButton) {
    renderWatchChartList(state.watchChartResults);
    return;
  }

  const row = event.target.closest(".watch-chart-row");
  if (row) {
    renderWatchChartDetail(row.dataset.code);
    return;
  }

  const refreshButton = event.target.closest(".chart-refresh-button");
  if (refreshButton) {
    const card = refreshButton.closest(".watch-chart-card");
    if (card) {
      refreshWatchChartCard(card, refreshButton);
    }
    return;
  }

  const aiButton = event.target.closest(".chart-ai-button");
  if (aiButton) {
    const card = aiButton.closest(".watch-chart-card");
    if (card) {
      renderWatchChartAI(card);
      aiButton.textContent = "AI 분석 갱신";
    }
    return;
  }

  const button = event.target.closest(".chart-save-button");
  if (!button) {
    return;
  }
  const card = button.closest(".watch-chart-card");
  if (card) {
    saveChartSnapshot(card);
    button.textContent = "저장됨";
    window.setTimeout(() => {
      button.textContent = "스냅샷 저장";
    }, 1000);
  }
});

elements.watchChartSnapshots.addEventListener("click", (event) => {
  const button = event.target.closest(".chart-snapshot-remove");
  if (!button) {
    return;
  }
  writeChartSnapshots(readChartSnapshots().filter((item) => item.id !== button.dataset.snapshotId));
  renderChartSnapshots();
});

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!elements.suggestions.hidden && state.suggestionIndex >= 0) {
    chooseSuggestion(state.suggestions[state.suggestionIndex]);
    return;
  }
  const query = elements.input.value.trim();
  if (!query) {
    return;
  }
  load(query);
});

document.addEventListener("click", (event) => {
  const detailWatch = event.target.closest(".detail-modal [data-overview-watch]");
  if (detailWatch) {
    event.preventDefault();
    const added = toggleWatchlistItem({
      code: detailWatch.dataset.overviewWatch,
      name: detailWatch.dataset.name,
      market: detailWatch.dataset.market,
    });
    detailWatch.classList.toggle("active", added);
    detailWatch.setAttribute("aria-pressed", added ? "true" : "false");
    detailWatch.title = added ? "관심 해제" : "관심 추가";
    updateWatchButton();
    renderOverviewDetailModal();
    if (state.currentStockOverview) {
      renderStockOverview(state.currentStockOverview);
    }
    return;
  }

  const detailClose = event.target.closest("[data-overview-detail-close]");
  if (detailClose) {
    closeOverviewDetail();
    return;
  }

  const detailNav = event.target.closest("[data-overview-detail-nav]");
  if (detailNav) {
    const [section, indexText] = String(detailNav.dataset.overviewDetailNav || "").split(":");
    const index = Number(indexText);
    if (section && Number.isInteger(index) && index >= 0) {
      openOverviewDetail(section, index);
    }
    return;
  }

  const termButton = event.target.closest(".term-help");
  if (termButton) {
    const wasOpen = termButton.classList.contains("open");
    document.querySelectorAll(".term-help.open").forEach((item) => item.classList.remove("open"));
    termButton.classList.toggle("open", !wasOpen);
    return;
  }
  document.querySelectorAll(".term-help.open").forEach((item) => item.classList.remove("open"));
  if (!elements.form.contains(event.target)) {
    hideSuggestions();
  }
});

function bootInitialView() {
  if (state.view === "market") {
    setView("market");
  } else if (state.view === "watchlist") {
    setView("watchlist");
  } else if (state.view === "recommend") {
    setView("recommend");
  } else if (state.view === "recommend-history") {
    setView("recommend-history");
  } else if (state.view === "trend") {
    setView("trend");
  } else if (state.view === "trend-past") {
    setView("trend-past");
  } else if (state.view === "trend-impact") {
    setView("trend-impact");
  } else if (state.view === "chart") {
    setView("chart");
  } else if (state.view === "chart-history") {
    setView("chart-history");
  } else {
    setView("stock");
    load(pathQuery());
  }
}

registerDashboardServiceWorker();
updateHomeInstallButton();
updateCurrencyButtons();
updateResponsiveModeBadges();
connectPresenceStream();
if (state.currencyMode === "KRW") {
  loadUsdKrwRate().then(refreshCurrentViewForCurrency);
}
applyStockTermTooltips();
initializeWatchlistIdentity().finally(bootInitialView);
