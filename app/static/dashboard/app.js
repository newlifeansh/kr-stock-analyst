const $ = (id) => document.getElementById(id);

if ("scrollRestoration" in history) {
  history.scrollRestoration = "manual";
}

const elements = {
  appFrame: document.querySelector(".app-frame"),
  loginGate: $("login-gate"),
  loginSplash: $("login-splash"),
  loginForm: $("login-form"),
  loginInput: $("login-id-input"),
  loginStatus: $("login-status"),
  pullRefreshIndicator: $("pull-refresh-indicator"),
  pullRefreshLabel: $("pull-refresh-label"),
  pageLoading: $("page-loading"),
  pageLoadingLabel: $("page-loading-label"),
  form: $("stock-form"),
  input: $("stock-code"),
  suggestions: $("stock-suggestions"),
  stockView: $("stock-view"),
  homeView: $("home-view"),
  searchView: $("search-view"),
  recommendDetailPage: $("recommend-detail-page"),
  recommendDetailBack: $("recommend-detail-back"),
  recommendDetailName: $("recommend-detail-name"),
  recommendDetailCode: $("recommend-detail-code"),
  recommendDetailContent: $("recommend-detail-content"),
  portfolioView: $("portfolio-view"),
  marketView: $("market-view"),
  aiSignalsView: $("ai-signals-view"),
  appNavItems: Array.from(document.querySelectorAll("[data-app-view]")),
  stockSectionTabs: Array.from(document.querySelectorAll("[data-stock-tab]")),
  stockTabPanels: Array.from(document.querySelectorAll("[data-stock-panel]")),
  watchlistView: $("watchlist-view"),
  watchlistIdForm: $("watchlist-id-form"),
  watchlistIdInput: $("watchlist-id-input"),
  watchlistIdDisplay: $("watchlist-id-display"),
  watchlistIdStatus: $("watchlist-id-status"),
  logoutButton: $("logout-button"),
  pushNotificationButton: $("push-notification-button"),
  pushNotificationButtonText: $("push-notification-button-text"),
  pushNotificationButtonLabel: $("push-notification-button-label"),
  pushNotificationUnreadDot: $("push-notification-unread-dot"),
  pushNotificationDisableButton: $("push-notification-disable-button"),
  pushNotificationStatus: $("push-notification-status"),
  notificationsView: $("notifications-view"),
  pushHistoryBack: $("push-history-back"),
  pushHistorySettings: $("push-history-settings"),
  pushHistoryTabs: Array.from(document.querySelectorAll("[data-notification-tab]")),
  pushHistoryMeta: $("push-history-meta"),
  pushHistoryList: $("push-history-list"),
  pushNotificationSheet: $("push-notification-sheet"),
  pushNotificationSheetBackdrop: $("push-notification-sheet-backdrop"),
  pushNotificationSheetClose: $("push-notification-sheet-close"),
  pushNotificationSheetStatus: $("push-notification-sheet-status"),
  pushNotificationConditionList: $("push-notification-condition-list"),
  pushNotificationSheetTestButton: $("push-notification-sheet-test-button"),
  pushNotificationSheetDisableButton: $("push-notification-sheet-disable-button"),
  pushNotificationSheetSaveButton: $("push-notification-sheet-save-button"),
  recommendView: $("recommend-view"),
  recommendHistoryView: $("recommend-history-view"),
  trendView: $("trend-view"),
  chartView: $("chart-view"),
  chartHistoryView: $("chart-history-view"),
  watchToggle: $("watch-toggle"),
  aiAnalysisButton: $("ai-analysis-button"),
  aiAnalysisPanel: $("ai-analysis-panel"),
  aiAnalysisMeta: $("ai-analysis-meta"),
  aiAnalysisProviderBadge: $("ai-analysis-provider-badge"),
  aiAnalysisStance: $("ai-analysis-stance"),
  aiAnalysisSummary: $("ai-analysis-summary"),
  aiDecisionStance: $("ai-decision-stance"),
  aiDecisionConfidence: $("ai-decision-confidence"),
  aiDecisionEntryLabel: $("ai-decision-entry-label"),
  aiDecisionEntry: $("ai-decision-entry"),
  aiDecisionCondition: $("ai-decision-condition"),
  aiPrimaryAction: $("ai-primary-action"),
  aiPrimaryReason: $("ai-primary-reason"),
  aiKeyPoints: $("ai-key-points"),
  aiStrategy: $("ai-strategy"),
  aiRisks: $("ai-risks"),
  aiSectionList: $("ai-section-list"),
  quantSignalStatus: $("quant-signal-status"),
  quantSignalContent: $("quant-signal-content"),
  quantSignalRefresh: $("quant-signal-refresh"),
  quantCurrentLabel: $("quant-current-label"),
  quantLifecycle: $("quant-lifecycle"),
  quantCurrentReasons: $("quant-current-reasons"),
  quantCurrentPosition: $("quant-current-position"),
  quantNextConfirmation: $("quant-next-confirmation"),
  quantContextLabel: $("quant-context-label"),
  quantContextCoverage: $("quant-context-coverage"),
  quantContextNote: $("quant-context-note"),
  quantContextList: $("quant-context-list"),
  quantPerformancePeriod: $("quant-performance-period"),
  quantPerformanceGrid: $("quant-performance-grid"),
  quantSampleNote: $("quant-sample-note"),
  quantSignalChart: $("quant-signal-chart"),
  quantChartSource: $("quant-chart-source"),
  quantTradeList: $("quant-trade-list"),
  quantMethodologyList: $("quant-methodology-list"),
  quantDisclaimer: $("quant-disclaimer"),
  stockSummaryScoreRing: $("stock-summary-score-ring"),
  stockSummaryScore: $("stock-summary-score"),
  stockSummaryConfidence: $("stock-summary-confidence"),
  stockSummaryAIBadge: $("stock-summary-ai-badge"),
  stockSummaryStance: $("stock-summary-stance"),
  stockSummaryLine: $("stock-summary-line"),
  stockAISayProbability: $("stock-ai-say-probability"),
  stockAISayConfidence: $("stock-ai-say-confidence"),
  stockAISayText: $("stock-ai-say-text"),
  stockInlineAIRefresh: $("stock-inline-ai-refresh"),
  stockMiniChart: $("stock-mini-chart"),
  stockDetailBack: $("stock-detail-back"),
  stockV2PricePeriods: Array.from(document.querySelectorAll("[data-price-period]")),
  stockV2MarketCode: $("stock-v2-market-code"),
  stockV2AsOf: $("stock-v2-as-of"),
  stockV2RangePercent: $("stock-v2-range-percent"),
  stockV2RangeChart: $("stock-v2-range-chart"),
  stockV2ConsensusUpside: $("stock-v2-consensus-upside"),
  stockV2ConsensusChart: $("stock-v2-consensus-chart"),
  stockV2FlowState: $("stock-v2-flow-state"),
  stockV2FlowChart: $("stock-v2-flow-chart"),
  stockV2SentimentState: $("stock-v2-sentiment-state"),
  stockV2SentimentChart: $("stock-v2-sentiment-chart"),
  stockHomeTodayDate: $("stock-home-today-date"),
  stockHomeSummaryList: $("stock-home-summary-list"),
  stockHomeUpdates: $("stock-home-updates"),
  stockHomeCheckpoints: $("stock-home-checkpoints"),
  stockHomeKeywords: $("stock-home-keywords"),
  stockHomeIssueTabs: $("stock-home-issue-tabs"),
  stockHomeIssueCard: $("stock-home-issue-card"),
  stockFinancialMetricTabs: Array.from(document.querySelectorAll("[data-financial-metric]")),
  stockFinancialScopeTabs: Array.from(document.querySelectorAll("[data-financial-scope]")),
  stockFinancialChart: $("stock-financial-chart"),
  stockFinancialSummary: $("stock-financial-summary"),
  stockFinancialSource: $("stock-financial-source"),
  stockFlowModeTabs: Array.from(document.querySelectorAll("[data-flow-mode]")),
  stockFlowPeriodTabs: Array.from(document.querySelectorAll("[data-flow-period]")),
  stockFlowSummary: $("stock-flow-summary"),
  stockFlowHistoryChart: $("stock-flow-history-chart"),
  stockReportModeTabs: Array.from(document.querySelectorAll("[data-report-mode]")),
  stockReportHistoryChart: $("stock-report-history-chart"),
  stockReportSummary: $("stock-report-summary"),
  stockNewsModeTabs: Array.from(document.querySelectorAll("[data-news-mode]")),
  stockNewsTemperature: $("stock-news-temperature"),
  stockNewsTemperatureChart: $("stock-news-temperature-chart"),
  stockCommunityStatus: $("stock-community-status"),
  stockCommunityProviders: $("stock-community-providers"),
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
  watchlistStrategy: $("watchlist-strategy"),
  watchlistFilterButtons: Array.from(document.querySelectorAll("[data-watch-filter]")),
  watchlistBody: $("watchlist-body"),
  recommendMeta: $("recommend-meta"),
  recommendArchiveButton: $("recommend-archive-button"),
  recommendHistoryNewButton: $("recommend-history-new-button"),
  recommendStatus: $("recommend-status"),
  recommendList: $("recommend-list"),
  recommendHistoryMeta: $("recommend-history-meta"),
  recommendHistoryList: $("recommend-history-list"),
  trendTitle: $("trend-title"),
  trendTopbar: $("trend-topbar"),
  trendEventsTitle: $("trend-events-title"),
  trendTabsWrap: $("trend-tabs"),
  trendTabs: Array.from(document.querySelectorAll(".trend-tab")),
  trendEventsPanel: $("trend-events-panel"),
  trendLivePanel: $("trend-live-panel"),
  trendImpactPanel: $("trend-impact-panel"),
  trendImpactContent: $("trend-impact-content"),
  trendWatchlistPanel: $("trend-watchlist-panel"),
  trendPastPanel: $("trend-past-panel"),
  trendEvents: $("trend-events"),
  trendPastEvents: $("trend-past-events"),
  trendThread: $("trend-thread"),
  trendWatchlistMeta: $("trend-watchlist-meta"),
  trendWatchStockRail: $("trend-watch-stock-rail"),
  trendWatchlistStatus: $("trend-watchlist-status"),
  trendWatchNewsBoard: $("trend-watch-news-board"),
  homeMarketSignalTicker: $("home-market-signal-ticker"),
  homeMarketSignalWindow: $("home-market-signal-window"),
  homeMarketIndices: $("home-market-indices"),
  homeMarketCarousel: $("home-market-carousel"),
  homeIndexSharedAsOf: $("home-index-shared-asof"),
  homeAiSignals: $("home-ai-signals"),
  homeAiSignalsMeta: $("home-ai-signals-meta"),
  homeAiSignalsList: $("home-ai-signals-list"),
  homeAiSignalsMore: $("home-ai-signals-more"),
  homeAiResponseTitle: $("home-ai-response-title"),
  homeAiResponseSummary: $("home-ai-response-summary"),
  homeAiResponseAsOf: $("home-ai-response-asof"),
  homeAiResponseWatch: $("home-ai-response-watch"),
  aiSignalsBack: $("ai-signals-back"),
  aiSignalsMeta: $("ai-signals-meta"),
  aiSignalStageTabs: Array.from(document.querySelectorAll("[data-ai-signal-stage]")),
  aiSignalsPageList: $("ai-signals-page-list"),
  homeSurge: $("home-surge"),
  homeSurgeMeta: $("home-surge-meta"),
  homeSurgeList: $("home-surge-list"),
  homeSurgeMore: $("home-surge-more"),
  homePastToggle: $("home-past-toggle"),
  discoverySearchForm: $("discovery-search-form"),
  discoverySearchInput: $("discovery-search-input"),
  discoverySearchSuggestions: $("discovery-search-suggestions"),
  portfolioTabs: Array.from(document.querySelectorAll("[data-portfolio-tab]")),
  portfolioWatchlistPanel: $("portfolio-watchlist-panel"),
  portfolioTrackingPanel: $("portfolio-tracking-panel"),
  watchlistContentTabs: Array.from(document.querySelectorAll("[data-watch-content-tab]")),
  watchlistStrategyPanel: $("watchlist-strategy-panel"),
  watchlistNewsPanel: $("watchlist-news-panel"),
  watchChartMeta: $("watch-chart-meta"),
  watchChartRefresh: $("watch-chart-refresh"),
  chartHistoryBackButton: $("chart-history-back-button"),
  watchChartList: $("watch-chart-list"),
  watchChartSnapshotMeta: $("watch-chart-snapshot-meta"),
  watchChartSnapshots: $("watch-chart-snapshots"),
  chartStockSearchForm: $("chart-stock-search-form"),
  chartStockSearchInput: $("chart-stock-search-input"),
  chartStockSearchSuggestions: $("chart-stock-search-suggestions"),
  chartStartGuide: $("chart-start-guide"),
  chartWatchlistPicker: $("chart-watchlist-picker"),
  homeInstallButton: $("home-install-button"),
  installSheet: $("install-sheet"),
  installSheetBackdrop: $("install-sheet-backdrop"),
  installSheetClose: $("install-sheet-close"),
  installSteps: $("install-steps"),
  installSheetSubtitle: $("install-sheet-subtitle"),
  flowLoadingModal: $("flow-loading-modal"),
  rankTabs: Array.from(document.querySelectorAll(".rank-tab")),
  rankCategorySelect: $("rank-category-select"),
  marketTabs: Array.from(document.querySelectorAll("[data-market-filter]")),
  marketRankingBack: $("market-ranking-back"),
  marketMeta: $("market-meta"),
  rankingBody: $("ranking-body"),
  name: $("stock-name"),
  meta: $("stock-meta"),
  stockLiveBadge: $("stock-live-badge"),
  stockPreMarket: $("stock-pre-market"),
  stockChangeValue: $("stock-change-value"),
  stockVolume: $("stock-volume"),
  stockPrevCloseSummary: $("stock-prev-close-summary"),
  stockPrevClose: $("stock-prev-close"),
  stockCompanyProfile: $("stock-company-profile"),
  stockCompanySummary: $("stock-company-summary"),
  stockCompanyIndustry: $("stock-company-industry"),
  stockCompanyCeo: $("stock-company-ceo"),
  stockCompanyCeoRow: $("stock-company-ceo-row"),
  stockCompanyEstablished: $("stock-company-established"),
  stockCompanyEstablishedRow: $("stock-company-established-row"),
  stockCompanyFiscal: $("stock-company-fiscal"),
  stockCompanyFiscalRow: $("stock-company-fiscal-row"),
  stockCompanyAddress: $("stock-company-address"),
  stockCompanyAddressRow: $("stock-company-address-row"),
  stockCompanyHomepage: $("stock-company-homepage"),
  stockCompanyIr: $("stock-company-ir"),
  stockCompanySourceLabel: $("stock-company-source-label"),
  stockCompanySourceLink: $("stock-company-source-link"),
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
  stockResearchList: $("stock-research-list"),
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
};

const WATCHLIST_KEY = "analyst.watchlist";
const WATCHLIST_ID_KEY = "analyst.watchlistId";
const HOME_AI_SIGNALS_CACHE_PREFIX = "analyst.homeAiSignals.v2";
const AI_SIGNAL_LOOKBACK_DAYS = 14;
const PUSH_HISTORY_CACHE_PREFIX = "analyst.pushHistory";
const PUSH_LAST_SEEN_PREFIX = "analyst.pushLastSeen";
const PUSH_ENABLED_PREFIX = "analyst.pushEnabled";
const RECOMMENDATION_HISTORY_KEY = "analyst.recommendationSnapshots";
const RECOMMENDATION_TRACK_KEY = "analyst.recommendationTracks";
const CHART_SNAPSHOT_KEY = "analyst.chartSnapshots";
const UI_CACHE_TTL_MS = 60_000;
const PAGE_ENTRY_MINUTE_MS = 60_000;
const LOGIN_SPLASH_DURATION_MS = 700;
const PUSH_NOTIFICATION_FALLBACK_OPTIONS = [
  {
    id: "ai_signal",
    label: "AI 매매신호",
    description: "관심종목의 매수·매도 신호 변화는 항상 알려드립니다.",
    required: true,
  },
  {
    id: "market_ai_signal",
    label: "시장 AI 매매신호",
    description: "관심종목 밖에서 새 매수·매도 신호가 발생하면 알려드립니다.",
  },
  {
    id: "price_move",
    label: "급등락",
    description: "관심종목 변동이 기준 이상 커지면 알려드립니다.",
  },
  {
    id: "disclosure_report",
    label: "중요 공시·리포트",
    description: "새 공시와 애널리스트 리포트 중 중요한 것만 알려드립니다.",
  },
  {
    id: "major_event",
    label: "주요 이벤트",
    description: "관심종목에 영향이 큰 일정이 가까워지면 알려드립니다.",
  },
];
const RECOMMENDATION_LIMIT = 10;
const STOCK_PRICE_PERIOD_COUNTS = { "1M": 22, "3M": 66, "6M": 132, "1Y": 260 };
const PULL_REFRESH_TRIGGER_DISTANCE = 72;
const PULL_REFRESH_MAX_DISTANCE = 104;
const PULL_REFRESH_DRAG_OFFSET = 10;
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
  "미국 EIA 주간 원유재고": ["원유"],
  "미국 PCE 물가·개인소득/지출": ["환율"],
  "미국 주간 신규실업수당청구건수": ["금리(고용)"],
};

const TREND_AXIS_CLASS = {
  원유: "axis-oil",
  환율: "axis-fx",
  "금리(고용)": "axis-rate",
};

const MARKET_IMPACT_FACTORS = [
  {
    key: "rate",
    label: "금리",
    symbol: "금리",
    className: "rate",
    keywords: ["금리", "FOMC", "연준", "Fed", "PCE", "물가", "고용", "실업", "신규실업수당", "국채금리", "10년물"],
    goodWords: ["인하", "하락", "둔화", "완화", "실업 증가", "예상 하회", "비둘기"],
    badWords: ["인상", "상승", "고금리", "예상 상회", "물가 압력", "긴축", "매파"],
    goodText: "금리 부담이 낮아지면 성장주와 코스닥 심리에 우호적입니다.",
    badText: "금리 부담이 커지면 성장주 밸류와 시장 PER에 압박이 생깁니다.",
    defaultStocks: ["NAVER", "카카오", "삼성전자", "KB금융"],
  },
  {
    key: "dollar",
    label: "달러",
    symbol: "달러",
    className: "dollar",
    keywords: ["달러", "환율", "원달러", "원/달러", "DXY", "원화", "외국인", "고환율"],
    goodWords: ["약세", "하락", "원화 강세", "외국인 매수", "수급 개선"],
    badWords: ["강세", "상승", "고환율", "원화 약세", "외국인 매도", "수급 부담"],
    goodText: "달러 부담이 낮아지면 외국인 수급과 대형주 심리가 좋아질 수 있습니다.",
    badText: "달러가 강하면 외국인 수급과 원화 약세 부담이 커질 수 있습니다.",
    defaultStocks: ["삼성전자", "SK하이닉스", "현대차", "기아"],
  },
  {
    key: "bond",
    label: "채권",
    symbol: "채권",
    className: "bond",
    keywords: ["채권", "국채", "10년물", "장기금리", "금리 경로", "수익률", "안전자산"],
    goodWords: ["금리 하락", "수익률 하락", "채권가격 상승", "완화", "안정"],
    badWords: ["금리 상승", "수익률 상승", "채권가격 하락", "급등", "불안"],
    goodText: "채권금리 안정은 주식의 상대 매력을 회복시키는 신호입니다.",
    badText: "채권금리 상승은 주식보다 채권 매력을 키워 성장주에 부담입니다.",
    defaultStocks: ["삼성생명", "KB금융", "신한지주", "NAVER"],
  },
  {
    key: "commodity",
    label: "원자재",
    symbol: "원자재",
    className: "commodity",
    keywords: ["원유", "유가", "WTI", "브렌트", "EIA", "재고", "금", "구리", "원자재", "정제마진"],
    goodWords: ["유가 하락", "재고 증가", "물가 완화", "비용 완화", "원자재 하락"],
    badWords: ["유가 상승", "재고 감소", "물가 부담", "원자재 상승", "비용 부담", "금 급등"],
    goodText: "원자재 부담이 낮아지면 항공·화학·운송 비용 압력이 줄어듭니다.",
    badText: "원자재가 강하면 물가와 비용 부담이 커져 마진이 흔들릴 수 있습니다.",
    defaultStocks: ["S-Oil", "대한항공", "LG화학", "POSCO홀딩스"],
  },
  {
    key: "risk",
    label: "위험자산",
    symbol: "위험",
    className: "risk",
    keywords: ["나스닥", "기술주", "반도체", "비트코인", "코인", "위험자산", "성장주", "AI", "레버리지"],
    goodWords: ["상승", "강세", "반등", "위험선호", "랠리", "호황", "기대"],
    badWords: ["하락", "급락", "약세", "위험회피", "조정", "폭락", "부담"],
    goodText: "위험자산 선호가 강하면 반도체·인터넷·성장주에 수급이 붙기 쉽습니다.",
    badText: "위험자산 심리가 식으면 나스닥과 국내 성장주가 같이 눌릴 수 있습니다.",
    defaultStocks: ["SK하이닉스", "삼성전자", "NAVER", "한미반도체"],
  },
];

const MARKET_IMPACT_LEARNING_GUIDES = {
  rate: {
    lesson: "금리 상승은 미래 이익의 할인율을 높여 성장주 밸류에이션에 부담을 줍니다.",
    metrics: "미국 10년물 국채금리 · 미국 10년 실질금리",
  },
  dollar: {
    lesson: "달러 강세는 원화와 외국인 수급에 부담이지만, 수출주는 환산 이익과 원가 구조를 함께 봐야 합니다.",
    metrics: "원/달러 환율 · 광의 달러지수",
  },
  bond: {
    lesson: "국채금리 상승은 채권의 상대 매력을 높여 주식 위험 프리미엄과 성장주 부담을 키울 수 있습니다.",
    metrics: "미국 10년-2년 금리차 · 미국 10년물 · VIX",
  },
  commodity: {
    lesson: "원자재 상승은 정유·소재에는 기회가 될 수 있지만 항공·화학·운송에는 비용 부담으로 전달됩니다.",
    metrics: "WTI 원유 · 구리 가격 · EIA 원유재고",
  },
  risk: {
    lesson: "위험자산 선호가 약해지면 미국 기술주와 국내 반도체·인터넷의 수급이 함께 위축될 수 있습니다.",
    metrics: "나스닥 · VIX · 비트코인",
  },
};

const MARKET_FIVE_ELEMENTS = [
  { key: "risk", element: "목", className: "wood", role: "성장·위험선호" },
  { key: "commodity", element: "화", className: "fire", role: "원자재·물가" },
  { key: "rate", element: "토", className: "earth", role: "금리·자금비용" },
  { key: "bond", element: "금", className: "metal", role: "채권·할인율" },
  { key: "dollar", element: "수", className: "water", role: "달러·유동성" },
];

const MARKET_FIVE_RELATIONS = {
  generate: { risk: "commodity", commodity: "rate", rate: "bond", bond: "dollar", dollar: "risk" },
  control: { risk: "rate", rate: "dollar", dollar: "commodity", commodity: "bond", bond: "risk" },
};

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
  거래량: "주식이 실제로 몇 주 거래됐는지 보는 값입니다. 가격 상승과 함께 늘면 매수세가 붙은 것으로 봅니다.",
  "52주 최고/최저": "최근 1년 동안 가장 높았던 가격과 가장 낮았던 가격입니다. 현재가가 어느 위치인지 볼 때 씁니다.",
  차트점수: "이동평균선, 지지·저항, 거래량, 변동성을 합쳐 지금 차트가 행동하기 좋은지 점수화한 값입니다.",
  판단: "차트 점수와 추세를 바탕으로 지금 매수 관찰인지, 대기인지 요약한 문장입니다.",
  추세: "가격과 이동평균선 배열로 상승 흐름인지, 박스권인지, 약세인지 판단한 값입니다.",
  셋업: "지금 차트가 돌파 구간인지, 눌림목인지, 지지 이탈인지 같은 매매 상황입니다.",
  리스크: "ATR, 지지선 이탈, 평균선 하회 등 차트상 조심해야 할 정도입니다.",
  지지: "가격이 내려올 때 버텨주길 기대하는 구간입니다. 이탈하면 비중 축소 기준으로 봅니다.",
  저항: "가격이 올라갈 때 막힐 수 있는 구간입니다. 거래대금과 함께 넘으면 추가 상승 가능성을 봅니다.",
  추정치: "애널리스트 목표가, EPS, 매출 추정 등 이익 기대가 좋아지는지 보는 점수입니다.",
  상향비율: "목표가나 추정치를 올린 애널리스트 비율입니다. 높을수록 시장 기대가 좋아진 쪽입니다.",
  실적: "최근 실적 발표나 공시가 기대보다 좋았는지 나빴는지 반영한 점수입니다.",
  가이던스: "회사나 시장이 앞으로 실적 전망을 좋게 보는지 나쁘게 보는지 반영합니다.",
  모멘텀: "1개월·3개월 가격 흐름과 차트 힘을 함께 본 점수입니다.",
  밸류: "PER/PBR 등 가격 부담이 과거 또는 업종 대비 과한지 낮은지 보는 점수입니다.",
  거시: "금리, 환율, 원자재, 수출 같은 외부 변수가 종목에 우호적인지 보는 점수입니다.",
  수급: "외국인과 기관이 최근 사고 있는지 팔고 있는지 반영한 점수입니다.",
  뉴스: "최근 뉴스 제목과 요약의 분위기가 호재 쪽인지 악재 쪽인지 본 점수입니다.",
};

const RECOMMEND_SCORE_HELP = [
  "100점 만점의 추천 우선순위 점수입니다.",
  "1차 후보는 가격 흐름·거래대금·차트를 중심으로 계산하고, 정밀 분석에서는 리포트·실적·밸류·수급·뉴스·거시 데이터를 추가로 반영합니다.",
  "기준은 70점 이상 우수, 55~69점 관찰, 55점 미만 신중입니다.",
  "1차 후보는 55점 이상이면서 차트 50점 이상이어야 합니다.",
  "수익률 확률이나 매수 확정 신호는 아닙니다.",
].join(" ");

const STOCK_TERM_HELP = {
  ...RECOMMEND_TERM_HELP,
  "차트 점수": "이동평균선, 지지·저항, 거래량, 변동성을 합쳐 지금 차트가 행동하기 좋은지 점수화한 값입니다.",
  전일: "직전 거래일 종가입니다. 오늘 등락률을 계산하는 기준 가격입니다.",
  시가: "오늘 장이 시작될 때 처음 형성된 가격입니다.",
  고가: "오늘 장중 가장 높게 거래된 가격입니다.",
  저가: "오늘 장중 가장 낮게 거래된 가격입니다.",
  대금: "가격에 거래량을 곱한 금액입니다. 실제 돈이 얼마나 들어왔는지 볼 때 씁니다.",
  시총: "주가에 발행주식 수를 곱한 회사 규모입니다. 대형주는 비교적 안정적이고 중소형주는 변동성이 큰 편입니다.",
  외인소진율: "외국인이 보유 가능한 한도 대비 얼마나 보유 중인지 보는 지표입니다. 현재 앱에 원천 데이터가 없으면 비워둡니다.",
  EPS: "순이익을 주식 수로 나눈 주당순이익입니다. 이 값이 높아지면 이익 체력이 좋아진 것으로 봅니다.",
  BPS: "순자산을 주식 수로 나눈 주당순자산입니다. PBR을 해석할 때 같이 봅니다.",
  배당수익률: "현재 주가 대비 1년 배당금 비율입니다. 배당주를 볼 때 중요합니다.",
  주당배당금: "주식 1주당 받을 수 있는 배당금입니다.",
  목표가: "최근 애널리스트가 제시한 목표 주가입니다. 실제 주가와 괴리가 클수록 기대와 리스크를 같이 봐야 합니다.",
  투자의견: "증권사가 제시한 매수·보유·중립 같은 의견입니다. 보고서 날짜와 함께 봐야 합니다.",
  상향: "목표가나 실적 추정치를 올린 횟수입니다. 많을수록 시장 기대가 좋아지는 쪽입니다.",
  하향: "목표가나 실적 추정치를 내린 횟수입니다. 많을수록 기대가 낮아지는 쪽입니다.",
  셋업: "지금 차트가 돌파 구간인지, 눌림목인지, 지지 이탈인지 같은 매매 상황입니다.",
  거래량: "최근 거래량이 평소보다 늘었는지 보는 값입니다. 가격 상승과 함께 늘면 매수세가 붙은 것으로 봅니다.",
  시가총액: "주가에 발행주식 수를 곱한 회사 규모입니다. 대형주는 비교적 안정적이고 중소형주는 변동성이 큰 편입니다.",
  "추정 매출": "애널리스트가 예상하는 앞으로의 매출입니다. 올라가면 성장 기대가 커진 것으로 봅니다.",
  "추정 영업이익": "애널리스트가 예상하는 앞으로의 본업 이익입니다. 주가에는 매출보다 더 직접적으로 반영되는 경우가 많습니다.",
  "추정 EPS": "예상 순이익을 주식 수로 나눈 값입니다. EPS가 오르면 이익 체력이 좋아진 것으로 해석합니다.",
  리포트: "최근 애널리스트 보고서 수입니다. 많을수록 시장에서 관심 있게 보고 있다는 뜻입니다.",
  "거래대금 변화": "최근 거래대금이 과거보다 늘었는지 줄었는지 보는 값입니다. 상승과 함께 늘면 힘이 붙은 흐름입니다.",
  "외국인 20일": "최근 20거래일 동안 외국인이 순매수했는지 순매도했는지 보여줍니다.",
  "기관 20일": "최근 20거래일 동안 기관이 순매수했는지 순매도했는지 보여줍니다.",
  "외국인 강도": "외국인 순매수 규모를 거래대금과 비교한 값입니다. 높으면 외국인 수급 영향이 강합니다.",
  "기관 강도": "기관 순매수 규모를 거래대금과 비교한 값입니다. 높으면 기관 수급 영향이 강합니다.",
  PER: "주가가 1년 이익의 몇 배로 거래되는지 보는 지표입니다. 낮다고 무조건 싸지는 않고 성장성과 함께 봅니다.",
  PBR: "주가가 회사 순자산의 몇 배인지 보는 지표입니다. 금융·지주·자산주에서 특히 자주 봅니다.",
  추정PER: "예상 이익 기준 PER입니다. 현재 이익보다 앞으로의 이익 기대가 반영됩니다.",
  업종PER: "같은 업종 평균 PER입니다. 내 종목이 업종 대비 비싼지 싼지 비교할 때 씁니다.",
  "PER z": "현재 PER이 과거 평균보다 얼마나 높거나 낮은지 표준화한 값입니다. 높으면 과거 대비 부담이 큽니다.",
  "PBR z": "현재 PBR이 과거 평균보다 얼마나 높거나 낮은지 표준화한 값입니다. 높으면 자산가치 대비 부담이 큽니다.",
  "최근 매출": "가장 최근 발표된 매출입니다. 전년 대비 성장 여부와 함께 봅니다.",
  "최근 영업이익": "가장 최근 발표된 본업 이익입니다. 실적 서프라이즈 판단의 핵심입니다.",
  "최근 EPS": "최근 순이익을 주식 수로 나눈 값입니다. 주당 이익 체력을 보여줍니다.",
  "영업이익 변화": "최근 영업이익이 전년 또는 직전 기준으로 얼마나 변했는지 보여줍니다.",
  "금리 프록시": "금리 변화에 얼마나 민감한지 보는 대리 지표입니다. 금리 부담이 큰 종목은 상승기에 조심합니다.",
  "환율 프록시": "환율 변화에 얼마나 민감한지 보는 대리 지표입니다. 수출주와 원가 민감 업종에서 중요합니다.",
  "원자재 프록시": "원유·금속 같은 원자재 가격 변화에 얼마나 영향을 받는지 보는 대리 지표입니다.",
  "수출 프록시": "수출 경기와 글로벌 수요 변화에 얼마나 민감한지 보는 대리 지표입니다.",
};

const requestedView = new URLSearchParams(window.location.search).get("view");
const hasStockDetailPath = window.location.pathname.split("/").filter(Boolean).length > 1;
const LEGACY_VIEW_MAP = {
  trend: "home",
  "trend-past": "home",
  "trend-impact": "home",
  market: "movers",
  movers: "movers",
  recommend: "search",
  watchlist: "portfolio",
  "recommend-history": "portfolio",
  stock: "search",
  home: "home",
  search: "search",
  "recommend-detail": "recommend-detail",
  notifications: "notifications",
  "ai-signals": "ai-signals",
  movers: "movers",
  portfolio: "portfolio",
  chart: "chart",
  "chart-history": "chart-history",
};
const initialView = hasStockDetailPath ? "stock" : (LEGACY_VIEW_MAP[requestedView] || "home");
const US_SECTOR_STREAM_VIEWS = new Set(["home", "search", "portfolio"]);

const state = {
  view: initialView,
  rankingCategory: "surge",
  currentStock: null,
  currentDashboard: null,
  suggestions: [],
  suggestionIndex: -1,
  suggestionTimer: null,
  suggestionController: null,
  activeTrendGraph: null,
  activeTrendTab: requestedView === "trend-impact" ? "impact" : requestedView === "trend-past" ? "events" : "live",
  showPastEvents: requestedView === "trend-past",
  portfolioTab: requestedView === "recommend-history" ? "tracking" : "watchlist",
  watchlistContentTab: "strategy",
  aiSignalStage: "recent-buy",
  aiSignalItems: [],
  homeAiSignalsAsOf: "",
  homeMarketIndexItems: [],
  homeTrendContext: null,
  homeMarketImpact: null,
  marketSignalTickerItems: [],
  marketSignalTickerIndex: 0,
  marketSignalTickerTimer: null,
  marketIndexRefreshTimer: null,
  discoverySuggestions: [],
  discoverySuggestionController: null,
  discoverySuggestionTimer: null,
  chartSuggestions: [],
  chartSuggestionController: null,
  chartSuggestionTimer: null,
  selectedTrendWatchCode: "",
  trendWatchRequestId: 0,
  watchlistId: "",
  watchlistSyncTimer: null,
  watchlistSyncing: false,
  writeToken: "",
  writeTokenShareId: "",
  watchChartResults: [],
  watchChartLoadSequence: 0,
  selectedWatchChartCode: "",
  marketRankingCache: new Map(),
  marketLeaderboardItems: [],
  marketLeaderboardVisibleCount: 30,
  marketLeaderboardAsOf: "",
  marketLeaderboardTradeDate: "",
  marketQuoteSockets: new Map(),
  marketQuoteReconnectTimers: new Map(),
  marketPrefetchKey: "",
  usSectorMoves: null,
  usSectorRefreshTimer: null,
  usSectorRefreshing: false,
  usSectorRefreshPromise: null,
  usSectorSocket: null,
  usSectorReconnectTimer: null,
  recommendationQuoteSockets: new Map(),
  recommendationQuoteReconnectTimers: new Map(),
  responseCache: new Map(),
  pendingRequests: new Map(),
  pageEntryRefreshAt: new Map(),
  quoteSocket: null,
  quoteSocketCode: "",
  quoteReconnectTimer: null,
  watchlistQuoteSockets: new Map(),
  watchlistQuoteReconnectTimers: new Map(),
  watchlistLoadSequence: 0,
  watchlistResults: [],
  watchlistMarketContext: null,
  watchlistStrategyRenderTimer: null,
  watchlistFilter: "all",
  stockActiveTab: "summary",
  stockPriceRows: [],
  stockPricePeriod: "1D",
  stockIntradayRows: [],
  stockIntradayMeta: null,
  stockFlowRows: [],
  stockResearchRows: [],
  stockDisclosureRows: [],
  stockNewsRows: [],
  stockCommunity: null,
  stockCommunityProviderKey: "naver_board",
  stockFinancialMetric: "revenue",
  stockFinancialScope: "quarterly",
  stockFlowMode: "cumulative",
  stockFlowPeriod: "3M",
  stockReportMode: "target",
  stockNewsMode: "company",
  stockHomeDetailsRequestId: 0,
  stockIssueKeyword: "",
  stockAIAnalysis: null,
  stockAIRequestedCode: "",
  stockAILoading: false,
  stockQuantSignals: null,
  stockQuantRequestedCode: "",
  stockQuantLoading: false,
  stockQuantLoadingCode: "",
  stockQuantRequestSequence: 0,
  stockQuantLastLiveRefreshAt: 0,
  watchPreopenExpanded: new Set(),
  pullRefreshTracking: false,
  pullRefreshReady: false,
  pullRefreshRefreshing: false,
  pullRefreshDistance: 0,
  pullRefreshStartX: 0,
  pullRefreshStartY: 0,
  pullRefreshHideTimer: null,
  recommendTrackRequestId: 0,
  recommendationLoading: false,
  currentRecommendationDetailItem: null,
  loginGateTimer: null,
  loginSplashSeen: false,
  pushConfig: null,
  pushNotificationBusy: false,
  pushNotificationEnabled: false,
  pushNotificationConditions: PUSH_NOTIFICATION_FALLBACK_OPTIONS.map((item) => item.id),
  pushNotificationHistory: [],
  pushNotificationHistoryBusy: false,
  pushNotificationHistoryTab: "all",
  pushNotificationHistoryScrollTop: new Map(),
  pushNotificationUnread: false,
  pushNotificationUnreadTimer: null,
  notificationReturnView: "home",
  pageLoadingSequence: 0,
  pageLoadingTokens: new Map(),
};

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function scopedStorageKey(prefix, shareId = state.watchlistId) {
  const normalizedId = normalizeWatchlistId(shareId);
  return normalizedId ? `${prefix}.${normalizedId}` : "";
}

function readStoredJson(key, fallback = null) {
  if (!key) {
    return fallback;
  }
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}

function writeStoredJson(key, value) {
  if (!key) {
    return;
  }
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage can be unavailable in private browsing; live requests still work.
  }
}

function readCachedHomeAiSignals() {
  const cached = readStoredJson(scopedStorageKey(HOME_AI_SIGNALS_CACHE_PREFIX), null);
  return cached && Array.isArray(cached.items) ? cached : null;
}

function writeCachedHomeAiSignals(payload = {}) {
  writeStoredJson(scopedStorageKey(HOME_AI_SIGNALS_CACHE_PREFIX), {
    savedAt: Date.now(),
    items: Array.isArray(payload.items) ? payload.items : [],
  });
}

function pushEnabledStorageKey() {
  return scopedStorageKey(PUSH_ENABLED_PREFIX);
}

function readCachedPushEnabled() {
  return localStorage.getItem(pushEnabledStorageKey()) === "true";
}

function writeCachedPushEnabled(enabled) {
  const key = pushEnabledStorageKey();
  if (key) {
    localStorage.setItem(key, String(enabled === true));
  }
}

function rejectAfter(ms, message) {
  return new Promise((_, reject) => {
    setTimeout(() => reject(new Error(message)), ms);
  });
}

function pathQuery() {
  if (state.view !== "stock") {
    return "SK하이닉스";
  }
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts[0] === "dashboard" && parts[1]) {
    return decodeURIComponent(parts[1]);
  }
  return new URLSearchParams(window.location.search).get("query") || "SK하이닉스";
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return Number(value).toLocaleString("ko-KR");
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
  return `${formatNumber(Math.min(roundedLow, roundedHigh))}~${formatNumber(Math.max(roundedLow, roundedHigh))}`;
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  if (Math.abs(number) >= 1_0000_0000_0000) {
    return `${(number / 1_0000_0000_0000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조`;
  }
  if (Math.abs(number) >= 1_0000_0000) {
    return `${(number / 1_0000_0000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`;
  }
  return number.toLocaleString("ko-KR");
}

function formatCompactCount(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  const abs = Math.abs(number);
  if (abs >= 100_000_000) {
    return `${(number / 100_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`;
  }
  if (abs >= 10_000) {
    return `${(number / 10_000).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}만`;
  }
  return number.toLocaleString("ko-KR");
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

function formatRatioPercent(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return `${number.toFixed(1)}%`;
}

function formatPreMarketChange(quote, includePrice = true) {
  if (!quote || quote.pre_market_change_rate === null || quote.pre_market_change_rate === undefined || quote.pre_market_change_rate === "") {
    return "-";
  }
  const rate = formatPercent(quote.pre_market_change_rate);
  if (!includePrice || quote.pre_market_price === null || quote.pre_market_price === undefined || quote.pre_market_price === "") {
    return rate;
  }
  return `${rate} · ${formatNumber(quote.pre_market_price)}`;
}

function formatQuoteTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function quoteSourceLabel(payload = null) {
  if (!payload) {
    return "";
  }
  if (["kis_realtime", "kis_rest"].includes(payload.source)) {
    return "KIS 실시간";
  }
  return "보조 갱신";
}

function koreaMarketPhaseLabel(now = new Date()) {
  const phase = koreaMarketPhase(now);
  if (phase === "preopen") {
    return "장 시작전";
  }
  if (phase === "regular") {
    return "장 중";
  }
  return "장 마감";
}

function formatPreMarketDisplay(quote, payload = null) {
  const status = quote?.pre_market_status || "장전";
  const change = formatPreMarketChange(quote);
  const source = quoteSourceLabel(payload);
  if (change === "-") {
    return source ? `${status} · ${source}` : status;
  }
  return source ? `${status} ${change} · ${source}` : `${status} ${change}`;
}

function stockMetaText(data, sourceLabel = "") {
  const parts = [data.code, data.market, formatDataBasis(data.as_of)];
  const preMarket = formatPreMarketChange(data.quote, false);
  if (preMarket !== "-") {
    parts.push(`장전 ${preMarket}`);
  }
  if (sourceLabel) {
    parts.push(sourceLabel);
  }
  return parts.filter(Boolean).join(" · ");
}

function stockDetailMetaText(data) {
  return [data?.code, data?.market].filter(Boolean).join(" · ");
}

function previousCloseFromQuote(quote) {
  if (!quote) {
    return null;
  }
  const price = toNumber(quote.price);
  const changeValue = toNumber(quote.change_value);
  if (price !== null && changeValue !== null) {
    return price - changeValue;
  }
  const changeRate = toNumber(quote.change_rate);
  if (price !== null && changeRate !== null && changeRate !== -100) {
    return price / (1 + changeRate / 100);
  }
  return null;
}

function rebasePeriodReturn(periodReturn, previousPrice, livePrice) {
  const rate = toNumber(periodReturn);
  const previous = toNumber(previousPrice);
  const next = toNumber(livePrice);
  if (rate === null || previous === null || next === null || previous <= 0 || next <= 0) {
    return periodReturn;
  }
  return ((1 + rate / 100) * (next / previous) - 1) * 100;
}

function applyLiveQuoteToDashboard(dashboard, quote, payload = null) {
  if (!dashboard || !quote) {
    return dashboard;
  }
  const previousPrice = toNumber(dashboard.quote?.price);
  const livePrice = toNumber(quote.price);
  if (dashboard.momentum && previousPrice !== null && livePrice !== null && previousPrice !== livePrice) {
    dashboard.momentum.one_month_return = rebasePeriodReturn(
      dashboard.momentum.one_month_return,
      previousPrice,
      livePrice,
    );
    dashboard.momentum.three_month_return = rebasePeriodReturn(
      dashboard.momentum.three_month_return,
      previousPrice,
      livePrice,
    );
  }
  dashboard.quote = { ...(dashboard.quote || {}), ...quote };
  if (payload?.as_of) {
    dashboard.as_of = payload.as_of;
  }
  if (payload?.source) {
    dashboard.source = payload.source;
  }
  return dashboard;
}

function formatChangeValue(value) {
  const number = toNumber(value);
  if (number === null) {
    return "-";
  }
  return `${number > 0 ? "+" : ""}${formatNumber(Math.round(number))}`;
}

function setText(node, text) {
  if (node) {
    node.textContent = text;
  }
}

function stockSectionOffset() {
  const appBar = window.innerWidth <= 980 ? document.querySelector(".mobile-app-bar")?.offsetHeight || 0 : 0;
  const tabs = document.querySelector(".stock-section-tabs")?.offsetHeight || 0;
  return appBar + tabs + 14;
}

function stockTabsStickyTop() {
  const tabs = document.querySelector(".stock-detail-tabs") || document.querySelector(".stock-section-tabs");
  if (!tabs) {
    return 0;
  }
  const top = Number.parseFloat(window.getComputedStyle(tabs).top);
  return Number.isFinite(top) ? top : 0;
}

function stockTabsDocumentTop(tabs) {
  const previousPosition = tabs.style.position;
  tabs.style.position = "static";
  const top = window.scrollY + tabs.getBoundingClientRect().top;
  tabs.style.position = previousPosition;
  return top;
}

function scrollStockTabsToTop(options = {}) {
  const tabs = document.querySelector(".stock-detail-tabs") || document.querySelector(".stock-section-tabs");
  if (!tabs) {
    return;
  }
  const stickyTop = stockTabsStickyTop();
  const target = stockTabsDocumentTop(tabs) - stickyTop;
  const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
  window.scrollTo({
    top: clampNumber(target, 0, maxScroll),
    behavior: options.instant ? "auto" : "smooth",
  });
}

function shouldAutoLoadStockAI(tabName = state.stockActiveTab) {
  return tabName === "summary" && Boolean(state.currentStock?.code);
}

function shouldAutoLoadStockQuantSignals(tabName = state.stockActiveTab) {
  return Boolean(state.currentStock?.code);
}

function ensureStockAIAnalysis() {
  if (!shouldAutoLoadStockAI() || state.stockAILoading) {
    return;
  }
  if (state.stockAIAnalysis && state.stockAIRequestedCode === state.currentStock?.code) {
    return;
  }
  loadAIAnalysis({ auto: true });
}

function ensureStockQuantSignals() {
  if (!shouldAutoLoadStockQuantSignals() || state.stockQuantLoading) {
    return;
  }
  if (state.stockQuantSignals && state.stockQuantRequestedCode === state.currentStock?.code) {
    return;
  }
  loadQuantSignals({ auto: true });
}

function setActiveStockTab(tabName, options = {}) {
  state.stockActiveTab = tabName || "summary";
  for (const tab of elements.stockSectionTabs) {
    const active = tab.dataset.stockTab === state.stockActiveTab;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  }
  for (const panel of elements.stockTabPanels) {
    panel.hidden = panel.dataset.stockPanel !== state.stockActiveTab;
  }
  if (!options.preserveScroll) {
    window.requestAnimationFrame(() => scrollStockTabsToTop({ instant: options.instant }));
  }
  ensureStockAIAnalysis();
  ensureStockQuantSignals();
}

function scrollToStockSection(hash, options = {}) {
  const map = {
    "#stock-summary-section": "summary",
    "#stock-ai-section": "strategy",
    "#stock-strategy-section": "strategy",
    "#stock-chart-section": "summary",
    "#stock-flow-section": "summary",
    "#stock-research-section": "summary",
    "#stock-consensus-section": "summary",
    "#stock-momentum-section": "summary",
    "#stock-finance-section": "summary",
    "#stock-news-section": "summary",
    "#stock-macro-section": "summary",
  };
  setActiveStockTab(map[hash] || "summary", { preserveScroll: options.instant });
}

function renderStockLiveSummary(data, sourceLabel = "") {
  if (!data) {
    return;
  }
  setText(elements.stockLiveBadge, koreaMarketPhaseLabel());
  const preMarketText = formatPreMarketDisplay(data.quote);
  setText(elements.stockPreMarket, sourceLabel ? `${preMarketText} · ${sourceLabel}` : preMarketText);
  setText(elements.stockChangeValue, formatChangeValue(data.quote?.change_value));
  setTone(elements.stockChangeValue, data.quote?.change_value);
  setText(elements.stockVolume, formatCompactCount(data.quote?.volume));
  setText(elements.stockVolumeDetail, formatNumber(data.quote?.volume));
  setText(elements.stockTradingValueDetail, formatMoney(data.quote?.trading_value));
  setText(elements.stockMarketCapDetail, formatMoney(data.quote?.market_cap));
  const previousClose = previousCloseFromQuote(data.quote);
  setText(elements.stockPrevCloseSummary, previousClose === null ? "-" : formatNumber(Math.round(previousClose)));
  setText(elements.stockPrevClose, previousClose === null ? "-" : formatNumber(Math.round(previousClose)));
}

function signalLabel(value, positive = "우호", neutral = "보통", negative = "부담") {
  const number = toNumber(value);
  if (number === null) {
    return "데이터 없음";
  }
  if (number >= 15) {
    return positive;
  }
  if (number <= -15) {
    return negative;
  }
  return neutral;
}

function setSignalCard(textNode, barNode, label, score) {
  setText(textNode, label);
  if (textNode) {
    setTone(textNode, toNumber(score) === null ? 0 : Number(score) - 50);
  }
  if (barNode) {
    barNode.style.width = `${clampNumber(score, 0, 100)}%`;
  }
}

function valuationLabel(valuation = {}) {
  const perZ = toNumber(valuation.per_zscore);
  const pbrZ = toNumber(valuation.pbr_zscore);
  const maxZ = Math.max(perZ ?? 0, pbrZ ?? 0);
  const minZ = Math.min(perZ ?? 0, pbrZ ?? 0);
  if (maxZ >= 1.5) {
    return "과거 대비 부담";
  }
  if (minZ <= -1) {
    return "과거 대비 낮음";
  }
  return "부담 중립";
}

function valuationScore(valuation = {}) {
  const perZ = toNumber(valuation.per_zscore);
  const pbrZ = toNumber(valuation.pbr_zscore);
  const maxZ = Math.max(perZ ?? 0, pbrZ ?? 0);
  return clampNumber(65 - maxZ * 18, 10, 90);
}

function flowLabel(flows = {}) {
  const foreign = toNumber(flows.foreign_intensity) || 0;
  const institution = toNumber(flows.institution_intensity) || 0;
  if (foreign > 0.8 && institution > 0.2) {
    return "외국인·기관 동반 매수";
  }
  if (foreign > Math.abs(institution) && foreign > 0.4) {
    return "외국인 우위";
  }
  if (institution > Math.abs(foreign) && institution > 0.4) {
    return "기관 우위";
  }
  if (foreign < -0.8 || institution < -0.8) {
    return "매도 압력";
  }
  return "수급 혼재";
}

function flowActionLabel(value, intensity = null) {
  const number = toNumber(value);
  const power = Math.abs(toNumber(intensity) || 0);
  if (number === null || !Number.isFinite(number) || number === 0) {
    return "중립";
  }
  if (power > 0 && power < 0.1) {
    return "중립";
  }
  return number > 0 ? "매수" : "매도";
}

function watchFlowPoint(flows = {}) {
  const foreign = toNumber(flows.foreign_net_buy_20d);
  const institution = toNumber(flows.institution_net_buy_20d);
  const foreignIntensity = toNumber(flows.foreign_intensity);
  const institutionIntensity = toNumber(flows.institution_intensity);
  if (foreign === null && institution === null) {
    return null;
  }
  const parts = [];
  if (foreign !== null) {
    parts.push(`외국인 ${flowActionLabel(foreign, foreignIntensity)}`);
  }
  if (institution !== null) {
    parts.push(`기관 ${flowActionLabel(institution, institutionIntensity)}`);
  }
  if (foreign !== null && institution !== null) {
    parts.push(`개인 추정 ${flowActionLabel(-(foreign + institution))}`);
  }
  return parts.length ? `수급 ${parts.join(" · ")}` : null;
}

function flowScore(flows = {}) {
  const foreign = toNumber(flows.foreign_intensity) || 0;
  const institution = toNumber(flows.institution_intensity) || 0;
  return clampNumber(50 + foreign * 12 + institution * 10, 5, 95);
}

function newsLabel(sentiment = {}) {
  const score = toNumber(sentiment.score);
  if (score === null) {
    return "뉴스 부족";
  }
  if (score >= 25) {
    return "호재 우위";
  }
  if (score <= -25) {
    return "악재 우위";
  }
  return "혼재";
}

function watchTrendPoint(oneMonth, threeMonth) {
  const shortTerm = toNumber(oneMonth);
  const midTerm = toNumber(threeMonth);
  if (shortTerm === null && midTerm === null) {
    return null;
  }
  if ((shortTerm ?? 0) >= 5 && (midTerm ?? 0) >= 5) {
    return "추세 우상향";
  }
  if ((shortTerm ?? 0) <= -5 && (midTerm ?? 0) <= -5) {
    return "추세 약세";
  }
  if ((shortTerm ?? 0) > 0 && (midTerm ?? 0) <= 0) {
    return "단기 반등 시도";
  }
  if ((shortTerm ?? 0) < 0 && (midTerm ?? 0) > 0) {
    return "단기 조정 구간";
  }
  return "추세 혼재";
}

function watchNewsPoint(sentiment = {}) {
  const score = toNumber(sentiment.score);
  if (score === null) {
    return "뉴스 부족";
  }
  const label = newsLabel(sentiment);
  return label === "혼재" ? "뉴스 혼재" : `뉴스 ${label}`;
}

function stockTrendScore(data) {
  const chartScore = toNumber(data?.chart_analysis?.score);
  const flow = flowScore(data?.flows || {});
  const valuation = valuationScore(data?.valuation || {});
  const news = clampNumber(50 + (toNumber(data?.sentiment?.score) || 0), 0, 100);
  const momentum = clampNumber(50 + (toNumber(data?.momentum?.one_month_return) || 0) * 1.4, 0, 100);
  const intraday = clampNumber(50 + (toNumber(data?.quote?.change_rate) || 0) * 6, 0, 100);
  const base = chartScore === null ? 50 : chartScore;
  return clampNumber(base * 0.32 + flow * 0.14 + valuation * 0.1 + news * 0.1 + momentum * 0.14 + intraday * 0.2, 0, 100);
}

function stockDataCoverage(data) {
  const coverage = data?.coverage || {};
  const values = Object.values(coverage);
  return values.length ? `${values.filter(Boolean).length}/${values.length}` : "-";
}

function aiDataCoverage(payload) {
  const covered = toNumber(payload?.data_covered);
  const total = toNumber(payload?.data_total);
  if (covered !== null && total !== null && total > 0) {
    return `${covered}/${total}`;
  }
  const confidence = toNumber(payload?.confidence);
  return confidence === null ? "-" : formatProbability(confidence);
}

function formatProbability(value) {
  const number = toNumber(value);
  return number === null ? "-" : `${number.toFixed(1)}%`;
}

function formatTrendScore(value) {
  const number = toNumber(value);
  return number === null ? "-" : `${number.toFixed(1)}점`;
}

function stockTrendContext(data) {
  const dayChange = toNumber(data?.quote?.change_rate);
  const oneMonth = toNumber(data?.momentum?.one_month_return);
  if (dayChange !== null && dayChange >= 2 && oneMonth !== null && oneMonth <= -5) {
    return `오늘 ${formatPercent(dayChange)} 강세지만 1개월 ${formatPercent(oneMonth)}여서, 급락 뒤 반등인지 추세 전환인지 확인이 필요합니다.`;
  }
  if (dayChange !== null && dayChange >= 2) {
    return `오늘 ${formatPercent(dayChange)} 강세로 단기 매수세가 유입되고 있습니다.`;
  }
  if (dayChange !== null && dayChange <= -2) {
    return `오늘 ${formatPercent(dayChange)} 약세로 단기 매도 압력이 커졌습니다.`;
  }
  return `${data.name}은 차트 ${data?.chart_analysis?.trend || "데이터 확인 중"}, 뉴스 ${newsLabel(data.sentiment)}, 밸류 ${valuationLabel(data.valuation)} 흐름입니다.`;
}

function renderStockTrendScore(data) {
  const score = stockTrendScore(data);
  if (elements.stockSummaryScoreRing) {
    elements.stockSummaryScoreRing.style.setProperty("--score", score);
  }
  setText(elements.stockSummaryScore, formatTrendScore(score));
  setText(elements.stockAISayProbability, formatTrendScore(score));
}

function renderStockSummaryFallback(data) {
  const chart = data?.chart_analysis || {};
  const score = stockTrendScore(data);
  const coverage = stockDataCoverage(data);
  renderStockTrendScore(data);
  setText(elements.stockSummaryConfidence, coverage);
  setText(elements.stockSummaryStance, chart.stance || "판단 대기");
  setText(elements.stockSummaryLine, stockTrendContext(data));
  setText(elements.stockAISayConfidence, `분석 데이터 ${coverage}`);
  setText(
    elements.stockAISayText,
    `${chart.trend || "추세 데이터"}와 ${flowLabel(data.flows)} 수급, ${valuationLabel(data.valuation)} 밸류를 함께 보면 현재 판단은 ${chart.stance || "추가 데이터 대기"}입니다.`
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
  setText(elements.evidenceSummaryFlow, `외국인 ${formatMoney(flows.foreign_net_buy_20d)} · 기관 ${formatMoney(flows.institution_net_buy_20d)}`);
  setText(elements.evidenceSummaryValue, `영업이익 ${formatPercent(surprise.operating_profit_growth)} · PER ${formatMultiple(valuation.per)}`);
  setText(elements.evidenceSummaryNews, `${newsLabel(sentiment)} · ${formatPercent(sentiment.score)}`);
}

function renderAIDecisionSummary(payload) {
  const levels = payload?.trade_levels || {};
  const buyLow = toNumber(levels.buy_low);
  const buyHigh = toNumber(levels.buy_high);
  const breakout = toNumber(levels.breakout);
  const stop = toNumber(levels.stop);
  const coverage = aiDataCoverage(payload);
  const actionable = isTradeLevelActionable(levels, payload);
  const entry = buyLow !== null && buyHigh !== null
    ? `${formatNumber(Math.min(buyLow, buyHigh))}~${formatNumber(Math.max(buyLow, buyHigh))}`
    : "-";
  const conditionParts = [];
  if (breakout !== null) {
    conditionParts.push(`돌파 ${formatNumber(breakout)}`);
  }
  if (stop !== null) {
    conditionParts.push(`축소 ${formatNumber(stop)}`);
  }
  const condition = conditionParts.length ? conditionParts.join(" · ") : (payload?.stance || "-");
  setText(elements.aiDecisionStance, payload?.stance || "-");
  setText(elements.aiDecisionConfidence, coverage);
  setText(elements.aiDecisionEntryLabel, actionable ? "1차 진입" : "관찰 가격");
  setText(elements.aiDecisionEntry, entry);
  setText(elements.aiDecisionCondition, condition);
  if (elements.aiDecisionStance) {
    const stance = String(payload?.stance || "");
    setTone(elements.aiDecisionStance, stance.includes("관망") ? -1 : stance.includes("중립") ? 0 : 1);
  }
}

function stockPriceRowsWithLiveQuote(prices, quote = null) {
  const rows = (prices || [])
    .slice()
    .reverse()
    .map((row) => ({
      date: String(row.trade_date || row.date || ""),
      open: toNumber(row.open),
      high: toNumber(row.high),
      low: toNumber(row.low),
      close: toNumber(row.close),
      volume: toNumber(row.volume),
    }))
    .filter((row) => row.date && row.close !== null);
  const livePrice = toNumber(quote?.price);
  const liveDate = String(quote?.trade_date || "");
  if (livePrice !== null && liveDate) {
    const matchingRow = rows.find((row) => row.date === liveDate);
    if (matchingRow) {
      matchingRow.close = livePrice;
      matchingRow.volume = toNumber(quote?.volume) ?? matchingRow.volume;
      matchingRow.high = Math.max(matchingRow.high ?? livePrice, livePrice);
      matchingRow.low = Math.min(matchingRow.low ?? livePrice, livePrice);
    } else {
      rows.push({
        date: liveDate,
        open: null,
        high: livePrice,
        low: livePrice,
        close: livePrice,
        volume: toNumber(quote?.volume),
      });
    }
  }
  return rows.sort((a, b) => a.date.localeCompare(b.date));
}

function formatChartAxisPrice(value) {
  const number = toNumber(value);
  if (number === null) {
    return "-";
  }
  if (Math.abs(number) >= 10000) {
    return `${Math.round(number / 10000).toLocaleString("ko-KR")}만`;
  }
  return formatNumber(Math.round(number));
}

function formatChartDate(value) {
  const text = String(value || "");
  if (text.length < 10) {
    return text || "-";
  }
  return `${text.slice(5, 7)}.${text.slice(8, 10)}`;
}

function renderStockV2Range(prices, quote = null) {
  if (!elements.stockV2RangeChart) {
    return;
  }
  const rows = stockPriceRowsWithLiveQuote(prices, quote);
  if (rows.length < 2) {
    setText(elements.stockV2RangePercent, "-");
    elements.stockV2RangeChart.innerHTML = '<p class="stock-v2-empty">52주 가격 데이터가 부족합니다.</p>';
    return;
  }
  const low = Math.min(...rows.map((row) => row.low ?? row.close));
  const high = Math.max(...rows.map((row) => row.high ?? row.close));
  const current = toNumber(quote?.price) ?? rows[rows.length - 1].close;
  const span = high === low ? 1 : high - low;
  const position = clampNumber(((current - low) / span) * 100, 0, 100);
  const upperDistance = Math.max(0, 100 - position);
  setText(elements.stockV2RangePercent, `상단 ${upperDistance.toFixed(0)}%`);
  elements.stockV2RangeChart.innerHTML = `
    <div class="stock-v2-range-value"><strong>${formatNumber(current)}</strong><span>현재가</span></div>
    <div class="stock-v2-range-track" style="--position:${position.toFixed(2)}%">
      <i class="stock-v2-range-fill"></i>
      <b class="stock-v2-range-marker"><span>${formatNumber(current)}</span></b>
    </div>
    <div class="stock-v2-range-labels"><span>최저 ${formatNumber(low)}</span><span>최고 ${formatNumber(high)}</span></div>
  `;
}

function renderStockV2Consensus(data) {
  if (!elements.stockV2ConsensusChart) {
    return;
  }
  const current = toNumber(data?.quote?.price);
  const target = toNumber(data?.revisions?.latest_target_price);
  const reportCount = toNumber(data?.revisions?.report_count_90d) || 0;
  if (current === null || target === null || target <= 0) {
    setText(elements.stockV2ConsensusUpside, "자료 부족");
    elements.stockV2ConsensusChart.innerHTML = '<p class="stock-v2-empty">최근 목표가가 확인되지 않았습니다.</p>';
    return;
  }
  const upside = ((target / current) - 1) * 100;
  const scaleMax = Math.max(current, target) * 1.08;
  const currentWidth = clampNumber((current / scaleMax) * 100, 2, 100);
  const targetWidth = clampNumber((target / scaleMax) * 100, 2, 100);
  setText(elements.stockV2ConsensusUpside, `여력 ${formatPercent(upside)}`);
  setTone(elements.stockV2ConsensusUpside, upside);
  elements.stockV2ConsensusChart.innerHTML = `
    <div class="stock-v2-comparison-row current"><span>현재가</span><div><i style="width:${currentWidth.toFixed(2)}%"></i></div><strong>${formatNumber(current)}</strong></div>
    <div class="stock-v2-comparison-row target"><span>목표가</span><div><i style="width:${targetWidth.toFixed(2)}%"></i></div><strong>${formatNumber(target)}</strong></div>
    <p>최근 90일 리포트 ${formatNumber(reportCount)}건 · ${data?.revisions?.latest_opinion || "의견 없음"}</p>
  `;
}

function stockFlowState(foreign, institution) {
  if (foreign === null || institution === null) {
    return "자료 부족";
  }
  if (foreign > 0 && institution > 0) {
    return "동반 순매수";
  }
  if (foreign < 0 && institution < 0) {
    return "동반 순매도";
  }
  return foreign > institution ? "외국인 우위" : "기관 우위";
}

function renderStockV2Flow(data) {
  if (!elements.stockV2FlowChart) {
    return;
  }
  const foreign = toNumber(data?.flows?.foreign_net_buy_20d);
  const institution = toNumber(data?.flows?.institution_net_buy_20d);
  const stateLabel = stockFlowState(foreign, institution);
  setText(elements.stockV2FlowState, stateLabel);
  const tone = foreign !== null && institution !== null ? foreign + institution : 0;
  setTone(elements.stockV2FlowState, tone);
  if (foreign === null && institution === null) {
    elements.stockV2FlowChart.innerHTML = '<p class="stock-v2-empty">20일 수급 데이터가 없습니다.</p>';
    return;
  }
  const maxAbs = Math.max(Math.abs(foreign || 0), Math.abs(institution || 0), 1);
  const rows = [
    { label: "외국인", value: foreign },
    { label: "기관", value: institution },
  ];
  elements.stockV2FlowChart.innerHTML = rows.map((row) => {
    const value = row.value || 0;
    const magnitude = Math.max(2, Math.abs(value) / maxAbs * 50);
    const direction = value >= 0 ? "positive" : "negative";
    return `
      <div class="stock-v2-flow-row ${direction}">
        <span>${row.label}</span>
        <div class="stock-v2-flow-track"><i style="width:${magnitude.toFixed(2)}%"></i></div>
        <strong>${formatMoney(row.value)}</strong>
      </div>
    `;
  }).join("");
}

function renderStockV2Sentiment(data) {
  if (!elements.stockV2SentimentChart) {
    return;
  }
  const positive = Math.max(0, toNumber(data?.sentiment?.positive_count) || 0);
  const negative = Math.max(0, toNumber(data?.sentiment?.negative_count) || 0);
  const neutral = Math.max(0, toNumber(data?.sentiment?.neutral_count) || 0);
  const total = positive + negative + neutral;
  if (!total) {
    setText(elements.stockV2SentimentState, "자료 부족");
    elements.stockV2SentimentChart.innerHTML = '<p class="stock-v2-empty">분류된 뉴스가 없습니다.</p>';
    return;
  }
  const positivePct = positive / total * 100;
  const neutralPct = neutral / total * 100;
  const negativePct = negative / total * 100;
  const stateLabel = positive > negative * 1.25 ? "긍정 우세" : negative > positive * 1.25 ? "부정 우세" : "혼조";
  const score = toNumber(data?.sentiment?.score);
  setText(elements.stockV2SentimentState, stateLabel);
  setTone(elements.stockV2SentimentState, positive - negative);
  elements.stockV2SentimentChart.innerHTML = `
    <div class="stock-v2-donut" style="--positive:${positivePct.toFixed(2)}%;--neutral:${(positivePct + neutralPct).toFixed(2)}%">
      <div><strong>${score === null ? "-" : formatPercent(score)}</strong><span>뉴스 점수</span></div>
    </div>
    <dl class="stock-v2-sentiment-legend">
      <div class="positive"><dt>긍정</dt><dd>${positive}건 · ${positivePct.toFixed(0)}%</dd></div>
      <div class="neutral"><dt>중립</dt><dd>${neutral}건 · ${neutralPct.toFixed(0)}%</dd></div>
      <div class="negative"><dt>부정</dt><dd>${negative}건 · ${negativePct.toFixed(0)}%</dd></div>
    </dl>
  `;
}

function renderStockV2Dashboard(data) {
  setText(elements.stockV2MarketCode, data?.code || "");
  setText(elements.stockV2AsOf, formatDataBasis(data?.as_of));
  renderStockV2Consensus(data);
  renderStockV2Flow(data);
  renderStockV2Sentiment(data);
  renderStockV2Range(state.stockPriceRows, data?.quote);
}

function quantSignalMarkers(rows, points, options = {}) {
  const payload = state.stockQuantSignals;
  if (!payload || state.stockQuantRequestedCode !== state.currentStock?.code || !Array.isArray(payload.events)) {
    return "";
  }
  const compact = options.compact === true;
  const pointByDate = new Map(rows.map((row, index) => [row.date, points[index]]));
  const visibleEvents = payload.events
    .filter((event) => pointByDate.has(String(event.execution_date || "")))
    .slice(compact ? -8 : -16);
  return visibleEvents.map((event) => {
    const point = pointByDate.get(String(event.execution_date));
    const side = event.side === "partial_sell" ? "partial" : event.side === "sell" ? "sell" : "buy";
    const direction = side === "buy" ? 1 : -1;
    const stemEnd = point.y + (direction * (compact ? 17 : 22));
    const labelY = point.y + (direction * (compact ? 30 : 36));
    const triangle = side === "buy"
      ? `${point.x - 5},${stemEnd + 5} ${point.x + 5},${stemEnd + 5} ${point.x},${stemEnd - 3}`
      : `${point.x - 5},${stemEnd - 5} ${point.x + 5},${stemEnd - 5} ${point.x},${stemEnd + 3}`;
    const compactLabel = side === "buy" ? "진입" : side === "partial" ? "분할" : "청산";
    const label = compact ? compactLabel : (event.label || compactLabel);
    return `
      <g class="quant-chart-marker ${side}">
        <title>${label} · ${formatDateLabel(event.execution_date)} · ${formatNumber(event.price)}</title>
        <line x1="${point.x.toFixed(2)}" y1="${point.y.toFixed(2)}" x2="${point.x.toFixed(2)}" y2="${stemEnd.toFixed(2)}"></line>
        <polygon points="${triangle}"></polygon>
        <text x="${point.x.toFixed(2)}" y="${labelY.toFixed(2)}" text-anchor="middle">${label}</text>
      </g>
    `;
  }).join("");
}

function renderStockMiniChart(prices, quote = null) {
  if (!elements.stockMiniChart) {
    return;
  }
  const period = state.stockPricePeriod || "1D";
  for (const button of elements.stockV2PricePeriods) {
    const active = button.dataset.pricePeriod === period;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  if (period === "1D") {
    renderStockIntradayChart(state.stockIntradayRows, quote, state.stockIntradayMeta);
    return;
  }
  const allRows = stockPriceRowsWithLiveQuote(prices, quote);
  const periodCount = STOCK_PRICE_PERIOD_COUNTS[period] || STOCK_PRICE_PERIOD_COUNTS["3M"];
  const rows = allRows.slice(-periodCount);
  if (rows.length < 2) {
    elements.stockMiniChart.innerHTML = '<p class="stock-v2-empty">가격 데이터가 충분하지 않습니다.</p>';
    return;
  }

  const width = 760;
  const height = 320;
  const left = 58;
  const right = 18;
  const top = 18;
  const priceBottom = 226;
  const volumeTop = 248;
  const volumeBottom = 296;
  const plotWidth = width - left - right;
  const plotHeight = priceBottom - top;
  const closes = rows.map((row) => row.close);
  const rawMin = Math.min(...closes);
  const rawMax = Math.max(...closes);
  const rawSpan = rawMax === rawMin ? Math.max(rawMax * 0.02, 1) : rawMax - rawMin;
  const min = Math.max(0, rawMin - rawSpan * 0.08);
  const max = rawMax + rawSpan * 0.08;
  const span = max - min || 1;
  const volumes = rows.map((row) => row.volume || 0);
  const maxVolume = Math.max(...volumes, 1);
  const pointFor = (row, index) => ({
    x: left + (index / Math.max(1, rows.length - 1)) * plotWidth,
    y: top + ((max - row.close) / span) * plotHeight,
  });
  const points = rows.map(pointFor);
  const linePath = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x.toFixed(2)} ${priceBottom} L${points[0].x.toFixed(2)} ${priceBottom} Z`;
  const start = closes[0];
  const end = closes[closes.length - 1];
  const change = start ? ((end / start) - 1) * 100 : 0;
  const toneClass = end >= start ? "up" : "down";
  const yTicks = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3;
    const y = top + ratio * plotHeight;
    const value = max - ratio * span;
    return `<g class="stock-v2-chart-grid"><line x1="${left}" y1="${y.toFixed(2)}" x2="${width - right}" y2="${y.toFixed(2)}"></line><text x="${left - 8}" y="${(y + 4).toFixed(2)}">${formatChartAxisPrice(value)}</text></g>`;
  }).join("");
  const volumeWidth = Math.max(1.5, (plotWidth / rows.length) * 0.56);
  const volumeBars = rows.map((row, index) => {
    const barHeight = ((row.volume || 0) / maxVolume) * (volumeBottom - volumeTop);
    const x = points[index].x - volumeWidth / 2;
    const y = volumeBottom - barHeight;
    return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${volumeWidth.toFixed(2)}" height="${Math.max(1, barHeight).toFixed(2)}"></rect>`;
  }).join("");
  const labelIndexes = [0, Math.floor((rows.length - 1) / 2), rows.length - 1];
  const dateLabels = labelIndexes.map((index) => `<text class="stock-v2-chart-date" x="${points[index].x.toFixed(2)}" y="316" text-anchor="${index === 0 ? "start" : index === rows.length - 1 ? "end" : "middle"}">${formatChartDate(rows[index].date)}</text>`).join("");
  const signalMarkers = quantSignalMarkers(rows, points, { compact: true });

  elements.stockMiniChart.innerHTML = `
    <div class="stock-v2-chart-summary ${toneClass}">
      <strong>${formatPercent(change)}</strong><span>${formatChartDate(rows[0].date)} 대비</span>
    </div>
    <svg class="stock-v2-price-svg ${toneClass}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${formatDateLabel(rows[0].date)}부터 ${formatDateLabel(rows[rows.length - 1].date)}까지 가격과 거래량">
      ${yTicks}
      <path class="stock-v2-chart-area" d="${areaPath}"></path>
      <g class="stock-v2-volume-bars">${volumeBars}</g>
      <path class="stock-v2-chart-line" d="${linePath}"></path>
      <circle class="stock-v2-chart-end" cx="${points[points.length - 1].x.toFixed(2)}" cy="${points[points.length - 1].y.toFixed(2)}" r="4"></circle>
      ${signalMarkers}
      ${dateLabels}
      <line class="stock-v2-hover-line" x1="0" y1="${top}" x2="0" y2="${priceBottom}" hidden></line>
      <circle class="stock-v2-hover-point" cx="0" cy="0" r="5" hidden></circle>
      <rect class="stock-v2-chart-hit" x="${left}" y="${top}" width="${plotWidth}" height="${priceBottom - top}"></rect>
    </svg>
    <div class="stock-v2-chart-tooltip" hidden></div>
  `;
  const svg = elements.stockMiniChart.querySelector(".stock-v2-price-svg");
  const hit = elements.stockMiniChart.querySelector(".stock-v2-chart-hit");
  const hoverLine = elements.stockMiniChart.querySelector(".stock-v2-hover-line");
  const hoverPoint = elements.stockMiniChart.querySelector(".stock-v2-hover-point");
  const tooltip = elements.stockMiniChart.querySelector(".stock-v2-chart-tooltip");
  const hideTooltip = () => {
    hoverLine.hidden = true;
    hoverPoint.hidden = true;
    tooltip.hidden = true;
  };
  hit?.addEventListener("pointermove", (event) => {
    const bounds = svg.getBoundingClientRect();
    const viewX = (event.clientX - bounds.left) / bounds.width * width;
    const index = clampNumber(Math.round((viewX - left) / plotWidth * (rows.length - 1)), 0, rows.length - 1);
    const row = rows[index];
    const point = points[index];
    hoverLine.hidden = false;
    hoverPoint.hidden = false;
    tooltip.hidden = false;
    hoverLine.setAttribute("x1", point.x.toFixed(2));
    hoverLine.setAttribute("x2", point.x.toFixed(2));
    hoverPoint.setAttribute("cx", point.x.toFixed(2));
    hoverPoint.setAttribute("cy", point.y.toFixed(2));
    tooltip.style.left = `${clampNumber(point.x / width * 100, 12, 88)}%`;
    tooltip.innerHTML = `<span>${formatDateLabel(row.date)}</span><strong>${formatNumber(row.close)}</strong><em>거래량 ${formatCompactCount(row.volume)}</em>`;
  });
  hit?.addEventListener("pointerleave", hideTooltip);
}

function formatIntradayTime(value) {
  const text = String(value || "").padStart(6, "0");
  return `${text.slice(0, 2)}:${text.slice(2, 4)}`;
}

function renderStockIntradayChart(intradayRows, quote = null, meta = null) {
  if (!elements.stockMiniChart) {
    return;
  }
  const rows = (intradayRows || [])
    .map((row) => ({
      date: String(row.trade_date || ""),
      time: String(row.trade_time || "").padStart(6, "0"),
      price: toNumber(row.price),
      volume: toNumber(row.volume) || 0,
    }))
    .filter((row) => row.date && row.time && row.price !== null)
    .sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`));
  if (rows.length < 2) {
    elements.stockMiniChart.innerHTML = '<p class="stock-v3-chart-empty">당일 분봉을 불러오는 중입니다.</p>';
    return;
  }

  const width = 760;
  const height = 300;
  const left = 18;
  const right = 70;
  const top = 24;
  const bottom = 254;
  const plotWidth = width - left - right;
  const plotHeight = bottom - top;
  const previousClose = previousCloseFromQuote(quote);
  const priceValues = rows.map((row) => row.price);
  if (previousClose !== null) {
    priceValues.push(previousClose);
  }
  const rawMin = Math.min(...priceValues);
  const rawMax = Math.max(...priceValues);
  const rawSpan = rawMax === rawMin ? Math.max(rawMax * 0.02, 1) : rawMax - rawMin;
  const min = Math.max(0, rawMin - rawSpan * 0.08);
  const max = rawMax + rawSpan * 0.08;
  const span = max - min || 1;
  const pointFor = (row, index) => ({
    x: left + (index / Math.max(1, rows.length - 1)) * plotWidth,
    y: top + ((max - row.price) / span) * plotHeight,
  });
  const points = rows.map(pointFor);
  const linePath = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x.toFixed(2)} ${bottom} L${points[0].x.toFixed(2)} ${bottom} Z`;
  const lastPrice = rows[rows.length - 1].price;
  const change = previousClose ? ((lastPrice / previousClose) - 1) * 100 : 0;
  const toneClass = change >= 0 ? "up" : "down";
  const highPrice = Math.max(...rows.map((row) => row.price));
  const lowPrice = Math.min(...rows.map((row) => row.price));
  const highIndex = rows.findIndex((row) => row.price === highPrice);
  const lowIndex = rows.findIndex((row) => row.price === lowPrice);
  const grid = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    const y = top + ratio * plotHeight;
    const value = max - ratio * span;
    return `<g class="stock-v3-chart-grid"><line x1="${left}" y1="${y.toFixed(2)}" x2="${width - right}" y2="${y.toFixed(2)}"></line><text x="${width - right + 10}" y="${(y + 4).toFixed(2)}">${formatNumber(Math.round(value))}</text></g>`;
  }).join("");
  const previousLine = previousClose === null ? "" : (() => {
    const y = top + ((max - previousClose) / span) * plotHeight;
    return `<g class="stock-v3-previous-line"><line x1="${left}" y1="${y.toFixed(2)}" x2="${width - right}" y2="${y.toFixed(2)}"></line><text x="${width - right - 4}" y="${(y - 6).toFixed(2)}" text-anchor="end">전일 ${formatNumber(Math.round(previousClose))}</text></g>`;
  })();
  const labelIndexes = [0, Math.floor((rows.length - 1) / 4), Math.floor((rows.length - 1) / 2), Math.floor((rows.length - 1) * 0.75), rows.length - 1];
  const timeLabels = [...new Set(labelIndexes)].map((index) => `<text class="stock-v3-chart-date" x="${points[index].x.toFixed(2)}" y="285" text-anchor="${index === 0 ? "start" : index === rows.length - 1 ? "end" : "middle"}">${formatIntradayTime(rows[index].time)}</text>`).join("");
  const extrema = [
    { label: "고가", value: highPrice, point: points[highIndex], className: "high" },
    { label: "저가", value: lowPrice, point: points[lowIndex], className: "low" },
  ].map((item) => `<g class="stock-v3-extrema ${item.className}"><circle cx="${item.point.x.toFixed(2)}" cy="${item.point.y.toFixed(2)}" r="3"></circle><text x="${item.point.x.toFixed(2)}" y="${(item.point.y + (item.className === "high" ? -10 : 20)).toFixed(2)}" text-anchor="middle">${item.label} ${formatNumber(item.value)}</text></g>`).join("");

  elements.stockMiniChart.innerHTML = `
    <div class="stock-v3-chart-badge ${toneClass}"><strong>${formatPercent(change)}</strong><span>${formatNumber(rows.length)}분</span></div>
    <svg class="stock-v3-price-svg ${toneClass}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${formatDateLabel(rows[0].date)} 당일 분봉 차트">
      ${grid}${previousLine}
      <path class="stock-v3-chart-area" d="${areaPath}"></path>
      <path class="stock-v3-chart-line" d="${linePath}"></path>
      ${extrema}${timeLabels}
      <line class="stock-v3-hover-line" x1="0" y1="${top}" x2="0" y2="${bottom}" hidden></line>
      <circle class="stock-v3-hover-point" cx="0" cy="0" r="5" hidden></circle>
      <rect class="stock-v3-chart-hit" x="${left}" y="${top}" width="${plotWidth}" height="${plotHeight}"></rect>
    </svg>
    <div class="stock-v3-chart-tooltip" hidden></div>
  `;
  const svg = elements.stockMiniChart.querySelector(".stock-v3-price-svg");
  const hit = elements.stockMiniChart.querySelector(".stock-v3-chart-hit");
  const hoverLine = elements.stockMiniChart.querySelector(".stock-v3-hover-line");
  const hoverPoint = elements.stockMiniChart.querySelector(".stock-v3-hover-point");
  const tooltip = elements.stockMiniChart.querySelector(".stock-v3-chart-tooltip");
  hit?.addEventListener("pointermove", (event) => {
    const bounds = svg.getBoundingClientRect();
    const viewX = (event.clientX - bounds.left) / bounds.width * width;
    const index = clampNumber(Math.round((viewX - left) / plotWidth * (rows.length - 1)), 0, rows.length - 1);
    const row = rows[index];
    const point = points[index];
    hoverLine.hidden = false;
    hoverPoint.hidden = false;
    tooltip.hidden = false;
    hoverLine.setAttribute("x1", point.x.toFixed(2));
    hoverLine.setAttribute("x2", point.x.toFixed(2));
    hoverPoint.setAttribute("cx", point.x.toFixed(2));
    hoverPoint.setAttribute("cy", point.y.toFixed(2));
    tooltip.style.left = `${clampNumber(point.x / width * 100, 13, 87)}%`;
    tooltip.innerHTML = `<span>${formatIntradayTime(row.time)}</span><strong>${formatNumber(row.price)}</strong><em>체결 ${formatCompactCount(row.volume)}</em>`;
  });
  hit?.addEventListener("pointerleave", () => {
    hoverLine.hidden = true;
    hoverPoint.hidden = true;
    tooltip.hidden = true;
  });
}

function formatFinancialAmount(value) {
  const number = toNumber(value);
  if (number === null) {
    return "-";
  }
  const absolute = Math.abs(number);
  if (absolute >= 10000) {
    return `${number < 0 ? "-" : ""}${(absolute / 10000).toFixed(1)}조`;
  }
  return `${formatNumber(Math.round(number))}억`;
}

function periodEndDate(period) {
  const match = String(period || "").match(/(\d{4})\.(\d{2})/);
  return match ? `${match[1]}-${match[2]}-31` : "";
}

function closestStockPrice(targetDate) {
  if (!targetDate) {
    return null;
  }
  const rows = stockPriceRowsWithLiveQuote(state.stockPriceRows, state.currentDashboard?.quote);
  let candidate = null;
  for (const row of rows) {
    if (row.date <= targetDate) {
      candidate = row.close;
    } else {
      break;
    }
  }
  return candidate;
}

function renderStockFinancialChart() {
  if (!elements.stockFinancialChart || !state.currentDashboard) {
    return;
  }
  const metric = state.stockFinancialMetric || "revenue";
  const scope = state.stockFinancialScope || "quarterly";
  for (const button of elements.stockFinancialMetricTabs) {
    button.classList.toggle("active", button.dataset.financialMetric === metric);
  }
  for (const button of elements.stockFinancialScopeTabs) {
    button.classList.toggle("active", button.dataset.financialScope === scope);
  }
  const series = (state.currentDashboard.financial_series?.[scope] || [])
    .map((row) => ({ ...row, value: toNumber(row?.[metric]) }))
    .filter((row) => row.value !== null);
  const metricLabels = { revenue: "매출액", operating_profit: "영업이익", net_income: "순이익" };
  if (!series.length) {
    elements.stockFinancialChart.innerHTML = '<p class="stock-v3-chart-empty">표시할 실적 시계열이 없습니다.</p>';
    elements.stockFinancialSummary.innerHTML = "";
    return;
  }

  const width = 760;
  const height = 330;
  const left = 54;
  const right = 54;
  const top = 28;
  const bottom = 276;
  const plotWidth = width - left - right;
  const plotHeight = bottom - top;
  const values = series.map((row) => row.value);
  const minValue = Math.min(0, ...values);
  const maxValue = Math.max(0, ...values);
  const span = maxValue - minValue || 1;
  const y = (value) => top + ((maxValue - value) / span) * plotHeight;
  const baseline = y(0);
  const slot = plotWidth / series.length;
  const barWidth = Math.min(68, slot * 0.58);
  const bars = series.map((row, index) => {
    const x = left + slot * index + (slot - barWidth) / 2;
    const valueY = y(row.value);
    const barY = row.value >= 0 ? valueY : baseline;
    const barHeight = Math.max(2, Math.abs(valueY - baseline));
    return `<g class="stock-v3-financial-bar ${row.estimated ? "estimated" : "actual"}"><rect x="${x.toFixed(2)}" y="${barY.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight.toFixed(2)}" rx="3"></rect><text x="${(x + barWidth / 2).toFixed(2)}" y="${(barY - 8).toFixed(2)}" text-anchor="middle">${formatFinancialAmount(row.value)}</text><text class="period" x="${(x + barWidth / 2).toFixed(2)}" y="305" text-anchor="middle">${String(row.period).replace("20", "").replace(" (E)", "E")}</text></g>`;
  }).join("");
  const prices = series.map((row) => closestStockPrice(periodEndDate(row.period)));
  const validPrices = prices.filter((value) => value !== null);
  let pricePath = "";
  let priceDots = "";
  if (validPrices.length >= 2) {
    const priceMin = Math.min(...validPrices);
    const priceMax = Math.max(...validPrices);
    const priceSpan = priceMax - priceMin || 1;
    const priceY = (value) => top + ((priceMax - value) / priceSpan) * plotHeight;
    const points = prices.map((value, index) => value === null ? null : ({
      x: left + slot * index + slot / 2,
      y: priceY(value),
      value,
    })).filter(Boolean);
    pricePath = `<path class="stock-v3-secondary-line" d="${points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ")}"></path>`;
    priceDots = points.map((point) => `<circle class="stock-v3-secondary-dot" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3"></circle>`).join("");
  }
  const grid = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3;
    const gridY = top + ratio * plotHeight;
    const value = maxValue - ratio * span;
    return `<g class="stock-v3-chart-grid"><line x1="${left}" y1="${gridY.toFixed(2)}" x2="${width - right}" y2="${gridY.toFixed(2)}"></line><text x="${left - 8}" y="${(gridY + 4).toFixed(2)}" text-anchor="end">${formatFinancialAmount(value)}</text></g>`;
  }).join("");
  elements.stockFinancialChart.innerHTML = `
    <svg class="stock-v3-data-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${metricLabels[metric]} ${scope === "annual" ? "연간" : "분기"} 추이">
      ${grid}<line class="stock-v3-baseline" x1="${left}" y1="${baseline.toFixed(2)}" x2="${width - right}" y2="${baseline.toFixed(2)}"></line>
      ${bars}${pricePath}${priceDots}
    </svg>
    <div class="stock-v3-legend"><span class="bar">${metricLabels[metric]}</span><span class="line">주가</span><span class="estimate">E 추정치</span></div>
  `;
  const latest = series[series.length - 1];
  const comparisonIndex = scope === "quarterly" && series.length > 4 ? series.length - 5 : series.length - 2;
  const previous = comparisonIndex >= 0 ? series[comparisonIndex] : null;
  const growth = previous?.value ? ((latest.value / previous.value) - 1) * 100 : null;
  elements.stockFinancialSummary.innerHTML = `
    <div><span>${latest.period}</span><strong>${formatFinancialAmount(latest.value)}</strong></div>
    <div><span>${scope === "quarterly" ? "전년 동기 대비" : "전년 대비"}</span><strong class="${growth !== null && growth >= 0 ? "positive" : "negative"}">${growth === null ? "-" : formatPercent(growth)}</strong></div>
    <div><span>영업이익률</span><strong>${latest.operating_margin === null || latest.operating_margin === undefined ? "-" : formatPercent(latest.operating_margin)}</strong></div>
  `;
  setText(elements.stockFinancialSource, `${state.currentDashboard.financial_series?.source || "네이버 금융"} · 단위 ${state.currentDashboard.financial_series?.unit || "억원"}`);
}

function stockFlowSeries() {
  const grouped = new Map();
  for (const row of state.stockFlowRows || []) {
    const date = String(row.trade_date || "");
    if (!date) {
      continue;
    }
    const item = grouped.get(date) || { date, foreign: 0, institution: 0 };
    const value = toNumber(row.net_buy_volume) || 0;
    if (String(row.investor_type || "").includes("외국")) {
      item.foreign += value;
    }
    if (String(row.investor_type || "").includes("기관")) {
      item.institution += value;
    }
    grouped.set(date, item);
  }
  const periodCounts = { "3M": 66, "6M": 132, "1Y": 264 };
  const count = periodCounts[state.stockFlowPeriod] || periodCounts["3M"];
  const rows = [...grouped.values()].sort((a, b) => a.date.localeCompare(b.date)).slice(-count);
  if (state.stockFlowMode === "cumulative") {
    let foreign = 0;
    let institution = 0;
    return rows.map((row) => {
      foreign += row.foreign;
      institution += row.institution;
      return { ...row, foreign, institution };
    });
  }
  return rows;
}

function formatSignedShares(value) {
  const number = toNumber(value);
  if (number === null) {
    return "-";
  }
  return `${number > 0 ? "+" : ""}${formatCompactCount(number)}`;
}

function renderStockFlowHistoryChart() {
  if (!elements.stockFlowHistoryChart) {
    return;
  }
  for (const button of elements.stockFlowModeTabs) {
    button.classList.toggle("active", button.dataset.flowMode === state.stockFlowMode);
  }
  for (const button of elements.stockFlowPeriodTabs) {
    button.classList.toggle("active", button.dataset.flowPeriod === state.stockFlowPeriod);
  }
  const rows = stockFlowSeries();
  if (rows.length < 2) {
    elements.stockFlowHistoryChart.innerHTML = '<p class="stock-v3-chart-empty">투자자 수급 이력을 불러오는 중입니다.</p>';
    setText(elements.stockFlowSummary, "수급 이력 준비 중");
    return;
  }
  const priceByDate = new Map(stockPriceRowsWithLiveQuote(state.stockPriceRows, state.currentDashboard?.quote).map((row) => [row.date, row.close]));
  const chartRows = rows.map((row) => ({ ...row, price: priceByDate.get(row.date) ?? null }));
  const width = 760;
  const height = 330;
  const left = 58;
  const right = 58;
  const top = 22;
  const bottom = 274;
  const plotWidth = width - left - right;
  const plotHeight = bottom - top;
  const flowValues = chartRows.flatMap((row) => [row.foreign, row.institution]);
  const maxAbs = Math.max(...flowValues.map((value) => Math.abs(value)), 1);
  const flowY = (value) => top + ((maxAbs - value) / (maxAbs * 2)) * plotHeight;
  const pointX = (index) => left + (index / Math.max(1, chartRows.length - 1)) * plotWidth;
  const pathFor = (key, yScale) => chartRows.map((row, index) => `${index ? "L" : "M"}${pointX(index).toFixed(2)} ${yScale(row[key]).toFixed(2)}`).join(" ");
  const validPrices = chartRows.map((row) => row.price).filter((value) => value !== null);
  let pricePath = "";
  if (validPrices.length >= 2) {
    const minPrice = Math.min(...validPrices);
    const maxPrice = Math.max(...validPrices);
    const priceSpan = maxPrice - minPrice || 1;
    const priceY = (value) => top + ((maxPrice - value) / priceSpan) * plotHeight;
    const points = chartRows.map((row, index) => row.price === null ? null : `${pointX(index).toFixed(2)} ${priceY(row.price).toFixed(2)}`).filter(Boolean);
    pricePath = `<path class="stock-v3-flow-line price" d="${points.map((point, index) => `${index ? "L" : "M"}${point}`).join(" ")}"></path>`;
  }
  const grid = [-1, -0.5, 0, 0.5, 1].map((ratio) => {
    const value = maxAbs * ratio;
    const gridY = flowY(value);
    return `<g class="stock-v3-chart-grid"><line x1="${left}" y1="${gridY.toFixed(2)}" x2="${width - right}" y2="${gridY.toFixed(2)}"></line><text x="${left - 8}" y="${(gridY + 4).toFixed(2)}" text-anchor="end">${formatCompactCount(value)}</text></g>`;
  }).join("");
  const labelIndexes = [0, Math.floor((chartRows.length - 1) / 2), chartRows.length - 1];
  const labels = labelIndexes.map((index) => `<text class="stock-v3-chart-date" x="${pointX(index).toFixed(2)}" y="306" text-anchor="${index === 0 ? "start" : index === chartRows.length - 1 ? "end" : "middle"}">${formatChartDate(chartRows[index].date)}</text>`).join("");
  elements.stockFlowHistoryChart.innerHTML = `
    <svg class="stock-v3-data-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="외국인과 기관 수급 및 주가 추이">
      ${grid}<path class="stock-v3-flow-line foreign" d="${pathFor("foreign", flowY)}"></path><path class="stock-v3-flow-line institution" d="${pathFor("institution", flowY)}"></path>${pricePath}${labels}
    </svg>
    <div class="stock-v3-legend"><span class="foreign">외국인</span><span class="institution">기관</span><span class="line">주가</span></div>
  `;
  const latest = chartRows[chartRows.length - 1];
  elements.stockFlowSummary.innerHTML = `
    <span>외국인 <strong class="${latest.foreign >= 0 ? "positive" : "negative"}">${formatSignedShares(latest.foreign)}</strong></span>
    <span>기관 <strong class="${latest.institution >= 0 ? "positive" : "negative"}">${formatSignedShares(latest.institution)}</strong></span>
  `;
}

function stockResearchReports() {
  const source = state.stockResearchRows.length
    ? state.stockResearchRows
    : state.currentDashboard?.revisions?.recent_reports || [];
  return source
    .map((row) => ({
      ...row,
      date: String(row.published_at || row.date || "").slice(0, 10),
      target: toNumber(row.target_price),
      title: row.title || "리포트",
      broker: row.broker_name || "증권사",
    }))
    .filter((row) => row.date)
    .sort((a, b) => a.date.localeCompare(b.date));
}

function setStockReportModeTabs() {
  const mode = state.stockReportMode || "target";
  for (const button of elements.stockReportModeTabs) {
    const active = button.dataset.reportMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  }
}

function setStockReportSummary(items) {
  if (!elements.stockReportSummary) {
    return;
  }
  elements.stockReportSummary.replaceChildren(...items.map(([label, value]) => {
    const item = el("div");
    item.append(el("span", "", label), el("strong", "", value));
    return item;
  }));
}

function renderStockReportIssuance(reports) {
  const monthly = new Map();
  for (const report of reports) {
    const month = report.date.slice(0, 7);
    monthly.set(month, (monthly.get(month) || 0) + 1);
  }
  const rows = Array.from(monthly, ([month, count]) => ({ month, count })).slice(-6);
  if (!rows.length) {
    elements.stockReportHistoryChart.innerHTML = '<p class="stock-v3-chart-empty">최근 발행된 증권사 리포트가 없습니다.</p>';
    elements.stockReportSummary.innerHTML = "";
    return;
  }
  const width = 760;
  const height = 220;
  const left = 54;
  const right = 30;
  const top = 48;
  const bottom = 182;
  const maxCount = Math.max(...rows.map((row) => row.count), 1);
  const slot = (width - left - right) / rows.length;
  const barWidth = Math.min(66, slot * 0.55);
  const bars = rows.map((row, index) => {
    const barHeight = row.count / maxCount * (bottom - top);
    const x = left + slot * index + (slot - barWidth) / 2;
    const y = bottom - barHeight;
    return `<g class="stock-v3-report-issuance"><rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${barHeight.toFixed(2)}" rx="4"></rect><text x="${(x + barWidth / 2).toFixed(2)}" y="${Math.max(36, y - 8).toFixed(2)}" text-anchor="middle">${row.count}건</text><text class="stock-v3-chart-date" x="${(x + barWidth / 2).toFixed(2)}" y="214" text-anchor="middle">${row.month.replace("-", ".")}</text></g>`;
  }).join("");
  elements.stockReportHistoryChart.innerHTML = `<svg class="stock-v3-data-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 월별 리포트 발행 건수"><line class="stock-v3-report-baseline" x1="${left}" y1="${bottom}" x2="${width - right}" y2="${bottom}"></line>${bars}</svg>`;
  const recentCutoff = new Date();
  recentCutoff.setDate(recentCutoff.getDate() - 30);
  const recentCount = reports.filter((row) => new Date(`${row.date}T00:00:00`) >= recentCutoff).length;
  setStockReportSummary([
    ["최근 30일", `${formatNumber(recentCount)}건`],
    ["최근 6개월", `${formatNumber(rows.reduce((sum, row) => sum + row.count, 0))}건`],
    ["최근 발행일", reports.at(-1)?.date || "-"],
  ]);
}

function renderStockReportBrokers(reports) {
  const brokerCounts = new Map();
  for (const report of reports) {
    brokerCounts.set(report.broker, (brokerCounts.get(report.broker) || 0) + 1);
  }
  const rows = Array.from(brokerCounts, ([broker, count]) => ({ broker, count }))
    .sort((a, b) => b.count - a.count || a.broker.localeCompare(b.broker));
  if (!rows.length) {
    elements.stockReportHistoryChart.innerHTML = '<p class="stock-v3-chart-empty">발행 증권사 정보가 없습니다.</p>';
    elements.stockReportSummary.innerHTML = "";
    return;
  }
  const maxCount = Math.max(...rows.map((row) => row.count), 1);
  const list = el("div", "stock-v3-report-brokers");
  rows.slice(0, 8).forEach((row, index) => {
    const meter = el("span", "stock-v3-report-broker-meter");
    const fill = el("i");
    fill.style.width = `${(row.count / maxCount * 100).toFixed(2)}%`;
    meter.appendChild(fill);
    const item = el("div", "stock-v3-report-broker-row");
    item.append(
      el("span", "stock-v3-report-broker-rank", String(index + 1)),
      el("strong", "", row.broker),
      meter,
      el("b", "", `${formatNumber(row.count)}건`)
    );
    list.appendChild(item);
  });
  elements.stockReportHistoryChart.replaceChildren(list);
  setStockReportSummary([
    ["발행 증권사", `${formatNumber(rows.length)}곳`],
    ["최다 발행", rows[0].broker],
    ["전체 리포트", `${formatNumber(reports.length)}건`],
  ]);
}

function renderStockReportHistoryChart() {
  if (!elements.stockReportHistoryChart || !state.currentDashboard) {
    return;
  }
  setStockReportModeTabs();
  elements.stockReportHistoryChart.dataset.mode = state.stockReportMode || "target";
  const reports = stockResearchReports();
  if (state.stockReportMode === "issuance") {
    renderStockReportIssuance(reports);
    return;
  }
  if (state.stockReportMode === "broker") {
    renderStockReportBrokers(reports);
    return;
  }
  const priceRows = stockPriceRowsWithLiveQuote(state.stockPriceRows, state.currentDashboard.quote).slice(-132);
  const targets = reports.filter((row) => row.target !== null && row.target > 0);
  if (priceRows.length < 2) {
    elements.stockReportHistoryChart.innerHTML = '<p class="stock-v3-chart-empty">주가 이력을 불러오는 중입니다.</p>';
    elements.stockReportSummary.innerHTML = "";
    return;
  }
  const width = 760;
  const height = 330;
  const left = 58;
  const right = 58;
  const top = 22;
  const bottom = 274;
  const plotWidth = width - left - right;
  const plotHeight = bottom - top;
  const values = [...priceRows.map((row) => row.close), ...targets.map((row) => row.target)].filter((value) => value !== null);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const rawSpan = rawMax - rawMin || Math.max(rawMax * 0.1, 1);
  const min = Math.max(0, rawMin - rawSpan * 0.08);
  const max = rawMax + rawSpan * 0.08;
  const y = (value) => top + ((max - value) / (max - min || 1)) * plotHeight;
  const x = (index) => left + (index / Math.max(1, priceRows.length - 1)) * plotWidth;
  const pricePath = priceRows.map((row, index) => `${index ? "L" : "M"}${x(index).toFixed(2)} ${y(row.close).toFixed(2)}`).join(" ");
  let currentTarget = null;
  const targetPoints = [];
  for (let index = 0; index < priceRows.length; index += 1) {
    const row = priceRows[index];
    for (const report of targets) {
      if (report.date <= row.date) {
        currentTarget = report.target;
      }
    }
    if (currentTarget !== null) {
      targetPoints.push({ x: x(index), y: y(currentTarget), value: currentTarget });
    }
  }
  const targetPath = targetPoints.length ? targetPoints.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ") : "";
  const grid = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    const gridY = top + ratio * plotHeight;
    const value = max - ratio * (max - min);
    return `<g class="stock-v3-chart-grid"><line x1="${left}" y1="${gridY.toFixed(2)}" x2="${width - right}" y2="${gridY.toFixed(2)}"></line><text x="${width - right + 8}" y="${(gridY + 4).toFixed(2)}">${formatChartAxisPrice(value)}</text></g>`;
  }).join("");
  const labels = [0, Math.floor((priceRows.length - 1) / 2), priceRows.length - 1].map((index) => `<text class="stock-v3-chart-date" x="${x(index).toFixed(2)}" y="306" text-anchor="${index === 0 ? "start" : index === priceRows.length - 1 ? "end" : "middle"}">${formatChartDate(priceRows[index].date)}</text>`).join("");
  elements.stockReportHistoryChart.innerHTML = `
    <svg class="stock-v3-data-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 6개월 목표가와 주가 비교">
      ${grid}<path class="stock-v3-report-price" d="${pricePath}"></path>${targetPath ? `<path class="stock-v3-report-target" d="${targetPath}"></path>` : ""}${labels}
    </svg>
    <div class="stock-v3-legend"><span class="target">목표가</span><span class="line">주가</span></div>
  `;
  const current = toNumber(state.currentDashboard.quote?.price);
  const latestTarget = targets.length ? targets[targets.length - 1].target : null;
  const upside = current && latestTarget ? (latestTarget / current - 1) * 100 : null;
  elements.stockReportSummary.innerHTML = `
    <div><span>목표가 대비 현재가</span><strong>${upside === null ? "-" : formatPercent(upside)}</strong></div>
    <div><span>최근 목표가</span><strong>${latestTarget === null ? "-" : formatNumber(latestTarget)}</strong></div>
    <div><span>최근 180일 리포트</span><strong>${formatNumber(reports.length)}건</strong></div>
  `;
}

function stockHomeContentItems(data = state.currentDashboard) {
  const reports = state.stockResearchRows.length ? state.stockResearchRows : data?.revisions?.recent_reports || [];
  const disclosures = state.stockDisclosureRows.length ? state.stockDisclosureRows : [
    ...(data?.surprise?.latest_events || []),
    ...(data?.guidance?.latest_events || []),
  ];
  const news = state.stockNewsRows.length ? state.stockNewsRows : data?.sentiment?.latest_items || [];
  return { reports, disclosures, news };
}

function updateItemLink(row) {
  return row?.detail_url || row?.pdf_url || row?.url || null;
}

function updateItemDate(row) {
  return row?.published_at || row?.date || null;
}

function renderStockHomeUpdates(data) {
  if (!elements.stockHomeUpdates) {
    return;
  }
  const { reports, disclosures, news } = stockHomeContentItems(data);
  const rows = [
    { label: "리포트", icon: "R", row: reports[0], title: reports[0]?.title },
    { label: "공시", icon: "D", row: disclosures[0], title: disclosures[0]?.report_name || disclosures[0]?.title },
    { label: "뉴스", icon: "N", row: news[0], title: news[0]?.title },
  ];
  elements.stockHomeUpdates.innerHTML = "";
  for (const item of rows) {
    const title = String(item.title || "최근 자료가 없습니다.").trim();
    const href = updateItemLink(item.row);
    const node = href ? el("a", "stock-v3-update-row") : el("div", "stock-v3-update-row is-empty");
    if (href) {
      node.href = href;
      node.setAttribute("aria-label", `${title} 원문 보기`);
    }
    node.append(
      el("i", "", item.icon),
      el("span", "stock-v3-update-kind", item.label),
      el("strong", "", title),
      el("time", "", item.row ? formatDateLabel(updateItemDate(item.row)) : "-")
    );
    elements.stockHomeUpdates.appendChild(node);
  }
}

function renderStockTodaySummary(data) {
  if (!elements.stockHomeSummaryList) {
    return;
  }
  const quote = data?.quote || {};
  const price = toNumber(quote.price);
  const changeRate = toNumber(quote.change_rate);
  const flows = data?.flows || {};
  const prices = stockPriceRowsWithLiveQuote(state.stockPriceRows, quote);
  const latestVolume = toNumber(quote.volume) ?? prices.at(-1)?.volume ?? null;
  const previousVolumes = prices.slice(-21, -1).map((row) => row.volume).filter((value) => value > 0);
  const averageVolume = previousVolumes.length ? previousVolumes.reduce((sum, value) => sum + value, 0) / previousVolumes.length : null;
  const volumeRatio = latestVolume !== null && averageVolume ? latestVolume / averageVolume * 100 : null;
  const range = prices.slice(-260);
  const high = range.length ? Math.max(...range.map((row) => row.high ?? row.close)) : null;
  const distanceFromHigh = price && high ? (price / high - 1) * 100 : null;
  const phase = koreaMarketPhaseLabel();
  const bullets = [
    `${phase} ${price === null ? "시세 대기" : `${formatNumber(price)}원 (${formatPercent(changeRate)})`}${distanceFromHigh === null ? "" : ` · 52주 고점 대비 ${formatPercent(distanceFromHigh)}`}`,
    `외국인 ${formatMoney(flows.foreign_net_buy_20d)} · 기관 ${formatMoney(flows.institution_net_buy_20d)} (최근 20거래일)`,
    volumeRatio === null ? `거래량 ${formatCompactCount(latestVolume)}` : `거래량 ${formatCompactCount(latestVolume)} · 최근 20일 평균의 ${volumeRatio.toFixed(0)}%`,
    `${data?.market || "시장"} · ${data?.company_profile?.industry || data?.company_profile?.sector || "업종 정보 확인 중"}`,
  ];
  elements.stockHomeSummaryList.innerHTML = "";
  for (const text of bullets) {
    elements.stockHomeSummaryList.appendChild(el("li", "", text));
  }
  const summaryDate = quote.trade_date || data?.as_of;
  setText(elements.stockHomeTodayDate, formatDataBasis(summaryDate));
}

function renderStockHomeCheckpoints(data) {
  if (!elements.stockHomeCheckpoints) {
    return;
  }
  const flows = data?.flows || {};
  const items = [
    { label: "외국인 20일", value: toNumber(flows.foreign_net_buy_20d) },
    { label: "기관 20일", value: toNumber(flows.institution_net_buy_20d) },
  ];
  elements.stockHomeCheckpoints.innerHTML = "";
  for (const item of items) {
    const card = el("article", `stock-v3-checkpoint ${item.value === null ? "neutral" : item.value >= 0 ? "positive" : "negative"}`);
    card.append(
      el("span", "", item.label),
      el("strong", "", item.value === null ? "자료 없음" : item.value >= 0 ? "순매수" : "순매도"),
      el("small", "", formatMoney(item.value))
    );
    elements.stockHomeCheckpoints.appendChild(card);
  }
}

const STOCK_KEYWORD_STOPWORDS = new Set([
  "관련", "대한", "위한", "통해", "최근", "전망", "주가", "증권", "투자", "리포트", "뉴스", "공시", "분석", "기업", "시장", "종목", "이번", "올해", "내년", "상승", "하락", "강세", "약세", "확대", "감소", "증가", "발표", "기준", "가능", "예상", "코스피", "코스닥", "the", "and", "with", "for", "from",
]);

function stockKeywords(data) {
  const { reports, disclosures, news } = stockHomeContentItems(data);
  const texts = [
    data?.company_profile?.industry,
    data?.company_profile?.sector,
    ...reports.map((row) => row.title),
    ...disclosures.map((row) => row.report_name || row.title),
    ...news.map((row) => row.title),
  ].filter(Boolean);
  const stockName = String(data?.name || "").toLowerCase();
  const counts = new Map();
  for (const text of texts) {
    const tokens = String(text).match(/[가-힣A-Za-z0-9]{2,}/g) || [];
    for (const rawToken of tokens) {
      const token = rawToken.replace(/^20\d{2}$/, "").trim();
      const normalized = token.toLowerCase();
      if (!token || normalized === stockName || STOCK_KEYWORD_STOPWORDS.has(normalized) || /^\d+$/.test(token)) {
        continue;
      }
      counts.set(token, (counts.get(token) || 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length)
    .slice(0, 10)
    .map(([label, count]) => ({ label, count }));
}

function renderStockIssueCard(data, keyword) {
  if (!elements.stockHomeIssueCard) {
    return;
  }
  const { reports, disclosures, news } = stockHomeContentItems(data);
  const candidates = [
    ...news.map((row) => ({ ...row, kind: "뉴스", title: row.title })),
    ...reports.map((row) => ({ ...row, kind: "리포트", title: row.title })),
    ...disclosures.map((row) => ({ ...row, kind: "공시", title: row.report_name || row.title })),
  ].filter((row) => row.title);
  const matched = candidates.filter((row) => String(row.title).toLowerCase().includes(String(keyword || "").toLowerCase()));
  const row = (matched.length ? matched : candidates)[0];
  elements.stockHomeIssueCard.innerHTML = "";
  if (!row) {
    elements.stockHomeIssueCard.appendChild(el("p", "stock-v3-chart-empty", "연결된 이슈가 없습니다."));
    return;
  }
  const title = el("strong", "", row.title);
  const href = updateItemLink(row);
  if (href) {
    const link = el("a", "", row.title);
    link.href = href;
    link.setAttribute("aria-label", `${row.title} 원문 보기`);
    title.replaceWith(link);
    elements.stockHomeIssueCard.append(link);
  } else {
    elements.stockHomeIssueCard.append(title);
  }
  elements.stockHomeIssueCard.append(
    el("p", "", `${row.kind} · ${formatDateLabel(updateItemDate(row))}`),
    el("span", "", keyword || "최근 이슈")
  );
}

function renderStockHomeKeywords(data) {
  const keywords = stockKeywords(data);
  if (elements.stockHomeKeywords) {
    elements.stockHomeKeywords.innerHTML = "";
    for (const keyword of keywords) {
      elements.stockHomeKeywords.appendChild(el("span", "", keyword.label));
    }
    if (!keywords.length) {
      elements.stockHomeKeywords.appendChild(el("p", "stock-v3-chart-empty", "키워드 집계에 필요한 자료가 부족합니다."));
    }
  }
  if (elements.stockHomeIssueTabs) {
    elements.stockHomeIssueTabs.innerHTML = "";
    const issueKeywords = keywords.slice(0, 5);
    if (!issueKeywords.length) {
      renderStockIssueCard(data, "");
      return;
    }
    if (!issueKeywords.some((item) => item.label === state.stockIssueKeyword)) {
      state.stockIssueKeyword = issueKeywords[0].label;
    }
    for (const keyword of issueKeywords) {
      const button = el("button", keyword.label === state.stockIssueKeyword ? "active" : "", keyword.label);
      button.type = "button";
      button.addEventListener("click", () => {
        state.stockIssueKeyword = keyword.label;
        renderStockHomeKeywords(data);
      });
      elements.stockHomeIssueTabs.appendChild(button);
    }
    renderStockIssueCard(data, state.stockIssueKeyword);
  }
}

function renderStockNewsTemperature(data) {
  if (!elements.stockNewsTemperature || !elements.stockNewsTemperatureChart) {
    return;
  }
  const sentiment = data?.sentiment || {};
  const positive = Math.max(0, toNumber(sentiment.positive_count) || 0);
  const negative = Math.max(0, toNumber(sentiment.negative_count) || 0);
  const neutral = Math.max(0, toNumber(sentiment.neutral_count) || 0);
  const total = positive + negative + neutral;
  const positivePct = total ? positive / total * 100 : 0;
  const negativePct = total ? negative / total * 100 : 0;
  elements.stockNewsTemperature.innerHTML = `
    <div class="stock-v3-temperature-gauge" style="--positive:${positivePct.toFixed(2)}%;--negative:${negativePct.toFixed(2)}%"><strong>${newsLabel(sentiment)}</strong><span>기사 ${formatNumber(total)}건</span></div>
    <dl><div><dt>긍정</dt><dd>${positive}건</dd></div><div><dt>중립</dt><dd>${neutral}건</dd></div><div><dt>부정</dt><dd>${negative}건</dd></div></dl>
  `;
  const priceRows = stockPriceRowsWithLiveQuote(state.stockPriceRows, data?.quote).slice(-30);
  if (priceRows.length < 2) {
    elements.stockNewsTemperatureChart.innerHTML = '<p class="stock-v3-chart-empty">가격 이력을 불러오는 중입니다.</p>';
    return;
  }
  const width = 760;
  const height = 178;
  const left = 28;
  const right = 28;
  const top = 12;
  const bottom = 142;
  const min = Math.min(...priceRows.map((row) => row.close));
  const max = Math.max(...priceRows.map((row) => row.close));
  const span = max - min || 1;
  const x = (index) => left + (index / Math.max(1, priceRows.length - 1)) * (width - left - right);
  const y = (value) => top + ((max - value) / span) * (bottom - top);
  const path = priceRows.map((row, index) => `${index ? "L" : "M"}${x(index).toFixed(2)} ${y(row.close).toFixed(2)}`).join(" ");
  const events = (sentiment.latest_items || []).map((row) => ({ ...row, date: String(row.published_at || "").slice(0, 10) }));
  const markers = events.map((event) => {
    const index = priceRows.findIndex((row) => row.date >= event.date);
    if (index < 0) {
      return "";
    }
    const tone = event.impact === "호재" ? "positive" : event.impact === "악재" ? "negative" : "neutral";
    return `<circle class="stock-v3-news-marker ${tone}" cx="${x(index).toFixed(2)}" cy="${y(priceRows[index].close).toFixed(2)}" r="5"></circle>`;
  }).join("");
  elements.stockNewsTemperatureChart.innerHTML = `
    <svg class="stock-v3-data-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 뉴스 분류와 실제 주가 흐름">
      <path class="stock-v3-news-price" d="${path}"></path>${markers}
      <text class="stock-v3-chart-date" x="${left}" y="170">${formatChartDate(priceRows[0].date)}</text>
      <text class="stock-v3-chart-date" x="${width - right}" y="170" text-anchor="end">${formatChartDate(priceRows.at(-1).date)}</text>
    </svg>
    <div class="stock-v3-legend"><span class="positive">호재</span><span class="negative">악재</span><span class="line">주가</span></div>
  `;
}

function renderStockNewsRows(rows) {
  if (!elements.newsList) {
    return;
  }
  const mode = state.stockNewsMode || "company";
  for (const button of elements.stockNewsModeTabs) {
    const active = button.dataset.newsMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  }
  const sourceRows = Array.isArray(rows) ? rows : [];
  let filteredRows = sourceRows.filter((row) => mode === "breaking"
    ? row.source_category === "breaking"
    : row.source_category !== "breaking");
  if (mode === "company" && !filteredRows.length) {
    filteredRows = sourceRows;
  }
  const seen = new Set();
  filteredRows = filteredRows.filter((row) => {
    const key = row.external_id || updateItemLink(row) || row.title;
    if (!key || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
  elements.newsList.innerHTML = "";
  if (!filteredRows.length) {
    elements.newsList.appendChild(el("li", "stock-v3-news-empty", mode === "breaking" ? "최근 AI 속보가 없습니다." : "최근 종목뉴스가 없습니다."));
    return;
  }
  for (const row of filteredRows.slice(0, 8)) {
    const item = el("li", "stock-v3-news-row");
    const href = updateItemLink(row);
    const article = href ? el("a", "stock-v3-news-link") : el("article", "stock-v3-news-link");
    const copy = el("div", "stock-v3-news-copy");
    const title = el("strong", "stock-v3-news-title", row.title || "뉴스");
    const meta = el(
      "span",
      "stock-v3-news-meta",
      [row.press_name || row.source, formatDate(updateItemDate(row))].filter(Boolean).join(" · "),
    );
    if (href) {
      article.href = href;
      article.setAttribute("aria-label", `${row.title || "뉴스"} 원문 보기`);
    }
    copy.append(title, meta);
    article.appendChild(copy);
    if (row.image_url) {
      const thumbnail = el("img", "stock-v3-news-thumb");
      thumbnail.src = row.image_url;
      thumbnail.alt = "";
      thumbnail.loading = "lazy";
      thumbnail.decoding = "async";
      thumbnail.referrerPolicy = "no-referrer";
      thumbnail.addEventListener("error", () => {
        thumbnail.remove();
        article.classList.add("is-text-only");
      }, { once: true });
      article.appendChild(thumbnail);
    } else {
      article.classList.add("is-text-only");
    }
    item.appendChild(article);
    elements.newsList.appendChild(item);
  }
}

function stockCommunityDate(value) {
  if (!value) {
    return "시각 정보 없음";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return formatDate(value);
  }
  return new Intl.DateTimeFormat("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function stockCommunityAvatarLabel(providerKey) {
  if (providerKey === "naver_board") {
    return "N";
  }
  return "T";
}

function stockCommunityMeta(providerKey, row) {
  if (providerKey === "naver_board") {
    return `${stockCommunityDate(row.created_at)} · 조회 ${formatCompactCount(row.view_count || 0)} · 공감 ${formatCompactCount(row.like_count || 0)} · 비공감 ${formatCompactCount(row.dislike_count || 0)}`;
  }
  return `${stockCommunityDate(row.created_at)} · 좋아요 ${formatCompactCount(row.like_count || 0)} · 답글 ${formatCompactCount(row.reply_count || 0)}`;
}

function renderStockCommunity(payload) {
  if (!elements.stockCommunityProviders || !elements.stockCommunityStatus) {
    return;
  }
  const providers = Array.isArray(payload?.providers) ? payload.providers : [];
  const totalItems = providers.reduce((sum, provider) => sum + (Array.isArray(provider?.items) ? provider.items.length : 0), 0);
  elements.stockCommunityProviders.innerHTML = "";
  elements.stockCommunityStatus.hidden = totalItems > 0;
  elements.stockCommunityStatus.textContent = totalItems
    ? ""
    : (payload?.message || "관련 커뮤니티 글을 찾지 못했습니다.");

  if (!providers.length) {
    return;
  }

  const selected = providers.find((provider) => provider.key === state.stockCommunityProviderKey) || providers[0];
  state.stockCommunityProviderKey = selected.key;

  const board = el("section", "stock-community-board");
  const tabs = el("div", "stock-community-tabs stock-v3-segment");
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "커뮤니티 출처");
  for (const provider of providers) {
    const button = el("button", provider.key === selected.key ? "active" : "", provider.label || "커뮤니티");
    button.type = "button";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", provider.key === selected.key ? "true" : "false");
    button.addEventListener("click", () => {
      if (state.stockCommunityProviderKey === provider.key) return;
      state.stockCommunityProviderKey = provider.key;
      renderStockCommunity(payload);
    });
    tabs.appendChild(button);
  }
  board.appendChild(tabs);

  const items = Array.isArray(selected.items) ? selected.items : [];
  const summary = el("div", "stock-community-board-summary");
  if (items.length) {
    summary.appendChild(el("strong", "", `최근 글 ${formatNumber(items.length)}건`));
    board.appendChild(summary);
  }

  const list = el("ul", "stock-community-list");
  for (const row of items.slice(0, 8)) {
    const item = el("li", "stock-community-item");
    const article = el("article", "stock-community-entry");
    const avatar = el("span", `stock-community-avatar is-${selected.key}`, stockCommunityAvatarLabel(selected.key));
    if (row.author_profile_image_url) {
      const image = document.createElement("img");
      image.src = row.author_profile_image_url;
      image.alt = "";
      image.loading = "lazy";
      image.referrerPolicy = "no-referrer";
      image.addEventListener("error", () => image.remove(), { once: true });
      avatar.appendChild(image);
    }

    const body = el("div", "stock-community-body");
    const line = el("div", "stock-community-line");
    const identity = el("span", "stock-community-identity");
    identity.append(
      el("strong", "", row.author_name || selected.label || "커뮤니티"),
      el("span", "", row.username ? `@${row.username}` : (selected.key === "naver_board" ? "종토방" : "Threads"))
    );
    const impact = el("span", `stock-community-impact is-${row.impact === "호재" ? "positive" : row.impact === "악재" ? "negative" : "neutral"}`, row.impact || "중립");
    line.append(identity, impact);

    const text = el("p", "stock-community-text", row.text || row.title || "게시물 내용 없음");
    const footer = el("div", "stock-community-footer");
    footer.appendChild(el("span", "stock-community-meta", stockCommunityMeta(selected.key, row)));
    const actions = el("span", "stock-community-actions");
    if (String(row.text || row.title || "").length > 120) {
      const expand = el("button", "stock-community-expand", "펼치기");
      expand.type = "button";
      expand.setAttribute("aria-expanded", "false");
      expand.addEventListener("click", () => {
        const expanded = text.classList.toggle("expanded");
        expand.textContent = expanded ? "접기" : "펼치기";
        expand.setAttribute("aria-expanded", expanded ? "true" : "false");
      });
      actions.appendChild(expand);
    }
    if (row.url) {
      const original = el("a", "stock-community-original", "원문 ↗");
      original.href = row.url;
      original.target = "_blank";
      original.rel = "noopener noreferrer";
      original.setAttribute("aria-label", `${selected.label || "커뮤니티"} 게시물 원문 보기`);
      actions.appendChild(original);
    }
    footer.appendChild(actions);
    body.append(line, text, footer);
    article.append(avatar, body);
    item.appendChild(article);
    list.appendChild(item);
  }

  if (!items.length) {
    const empty = el("li", "stock-community-empty");
    empty.appendChild(el("span", "", selected.message || "표시할 게시물이 없습니다."));
    list.appendChild(empty);
  }
  board.appendChild(list);
  elements.stockCommunityProviders.appendChild(board);
}

function renderStockHome(data = state.currentDashboard) {
  if (!data) {
    return;
  }
  renderStockTodaySummary(data);
  renderStockHomeUpdates(data);
  renderStockHomeCheckpoints(data);
  renderStockHomeKeywords(data);
  renderStockFinancialChart();
  renderStockFlowHistoryChart();
  renderStockReportHistoryChart();
  renderStockNewsTemperature(data);
  renderStockNewsRows(state.stockNewsRows.length ? state.stockNewsRows : data?.sentiment?.latest_items || []);
}

function isTradeLevelActionable(levels, payload) {
  if (typeof levels?.actionable === "boolean") {
    return levels.actionable;
  }
  const stance = String(payload?.stance || "");
  return !stance.includes("관망") && !stance.includes("중립");
}

function renderStockStrategyVisual(payload) {
  if (!elements.stockPriceLadder) {
    return;
  }
  const levels = payload?.trade_levels || null;
  const price = toNumber(state.currentDashboard?.quote?.price);
  if (!levels || price === null) {
    setText(elements.stockStrategyStatus, "AI 분석을 불러오면 현재가 근처의 가격 기준을 표시합니다.");
    setText(elements.stockStrategyStance, payload?.stance || "-");
    elements.stockPriceLadder.innerHTML = '<p class="muted">전략 가격대 대기 중</p>';
    return;
  }
  const actionable = isTradeLevelActionable(levels, payload);
  const entryLabel = levels.entry_label || (actionable ? "1차 매수권" : "관찰 가격대");
  const entryNote = levels.entry_note || (actionable ? "분할 접근 구간" : "신규 매수 보류 기준");
  const entryTone = actionable ? "buy" : "watch";
  const markers = [
    { key: "stop", label: "축소", value: toNumber(levels.stop), tone: "risk" },
    { key: "buy_low", label: `${entryLabel} 하단`, value: toNumber(levels.buy_low), tone: entryTone },
    { key: "buy_high", label: `${entryLabel} 상단`, value: toNumber(levels.buy_high), tone: entryTone },
    { key: "current", label: "현재가", value: price, tone: "current" },
    { key: "breakout", label: "돌파", value: toNumber(levels.breakout), tone: "breakout" },
    { key: "first_sell", label: "1차 매도", value: toNumber(levels.first_sell), tone: "sell" },
  ].filter((item) => item.value !== null);
  if (markers.length < 3) {
    elements.stockPriceLadder.innerHTML = '<p class="muted">전략 가격대가 충분하지 않습니다.</p>';
    return;
  }
  const buyLow = toNumber(levels.buy_low);
  const buyHigh = toNumber(levels.buy_high);
  const breakout = toNumber(levels.breakout);
  const stop = toNumber(levels.stop);
  const firstSell = toNumber(levels.first_sell);
  const rawMin = Math.min(...markers.map((item) => item.value));
  const rawMax = Math.max(...markers.map((item) => item.value));
  const rawSpan = rawMax === rawMin ? Math.max(rawMax * 0.04, 1) : rawMax - rawMin;
  const min = Math.max(0, rawMin - rawSpan * 0.08);
  const max = rawMax + rawSpan * 0.08;
  const span = max === min ? 1 : max - min;
  const pos = (value) => clampNumber(((value - min) / span) * 100, 0, 100);
  const buyStart = buyLow === null || buyHigh === null ? null : Math.min(buyLow, buyHigh);
  const buyEnd = buyLow === null || buyHigh === null ? null : Math.max(buyLow, buyHigh);
  const zoneStyle = (from, to, minimum = 2) => {
    if (from === null || to === null) {
      return "display:none;";
    }
    const left = pos(Math.min(from, to));
    const width = Math.max(minimum, pos(Math.max(from, to)) - left);
    return `left:${left}%;width:${width}%;`;
  };
  const currentPos = pos(price);
  const currentEdgeClass = currentPos < 12 ? "near-left" : currentPos > 88 ? "near-right" : "";
  const levelCards = [
    { label: "현재가", value: formatNumber(price), note: "지금 거래 기준", tone: "current" },
    { label: "1차 매도", value: formatNumber(firstSell), note: "일부 이익 실현", tone: "sell" },
    { label: "돌파", value: formatNumber(breakout), note: "거래대금 동반 필요", tone: "breakout" },
    { label: "축소", value: formatNumber(stop), note: "이탈 시 비중 축소", tone: "risk" },
    { label: entryLabel, value: `${formatNumber(buyLow)}~${formatNumber(buyHigh)}`, note: entryNote, tone: entryTone, featured: true },
  ];
  const stockName = payload?.name || state.currentDashboard?.profile?.name || "현재 종목";
  setText(
    elements.stockStrategyStatus,
    actionable
      ? `${stockName} 기준 1차 매수권은 ${formatNumber(buyLow)}~${formatNumber(buyHigh)}, 돌파 기준은 ${formatNumber(breakout)}입니다.`
      : `${stockName}은 현재 ${payload?.stance || "관찰"} 판단이라 ${formatNumber(buyLow)}~${formatNumber(buyHigh)}는 실행 구간이 아닌 관찰 가격대입니다. 돌파 기준 ${formatNumber(breakout)} 위에서 다시 봅니다.`
  );
  setText(elements.stockStrategyStance, payload.stance || "-");
  elements.stockPriceLadder.innerHTML = `
    <div class="strategy-range-chart" aria-label="매매 가격 기준 가로 막대그래프">
      <div class="strategy-range-scale">
        <span>${formatNumber(Math.round(min))}</span>
        <strong>가격 기준선</strong>
        <span>${formatNumber(Math.round(max))}</span>
      </div>
      <div class="strategy-range-track">
        <span class="strategy-zone risk" style="${zoneStyle(min, stop, 1)}"></span>
        <span class="strategy-zone ${entryTone}" style="${zoneStyle(buyStart, buyEnd, 3)}"></span>
        <span class="strategy-zone breakout" style="${zoneStyle(breakout, max, 1)}"></span>
        ${markers.filter((item) => item.key !== "current").map((item) => `
          <span class="strategy-tick ${item.tone}" style="left:${pos(item.value)}%;" aria-label="${item.label} ${formatNumber(item.value)}"></span>
        `).join("")}
        <span class="strategy-current ${currentEdgeClass}" style="left:${currentPos}%;">
          <i></i>
          <b>현재가</b>
          <em>${formatNumber(price)}</em>
        </span>
      </div>
      <div class="strategy-range-legend">
        <span><i class="risk"></i>축소 구간</span>
        <span><i class="${entryTone}"></i>${entryLabel}</span>
        <span><i class="breakout"></i>돌파 이후</span>
      </div>
    </div>
    <div class="strategy-level-grid">
      ${levelCards.map((item) => `
        <div class="strategy-level-card ${item.tone}${item.featured ? " featured" : ""}">
          <span>${item.label}</span>
          <strong>${item.value}</strong>
          <em>${item.note}</em>
        </div>
      `).join("")}
    </div>
  `;
}

function renderStockResearchSummary(data) {
  const revisions = data?.revisions || {};
  const latestTargetPrice = revisions.latest_target_price;
  setText(elements.stockTargetPrice, latestTargetPrice ? formatNumber(latestTargetPrice) : "-");
  setText(elements.stockLatestOpinion, revisions.latest_opinion || "-");
  if (elements.stockLatestReportAt) {
    elements.stockLatestReportAt.textContent = "";
    elements.stockLatestReportAt.hidden = true;
  }
  setText(elements.revisionRatio, formatPercent(revisions.target_up_ratio));
  setText(elements.revisionUp, formatNumber(revisions.target_up_count));
  setText(elements.revisionDown, formatNumber(revisions.target_down_count));
  if (elements.stockResearchList) {
    elements.stockResearchList.innerHTML = "";
    const reports = state.stockResearchRows.length ? state.stockResearchRows : revisions.recent_reports || [];
    if (!reports.length) {
      elements.stockResearchList.appendChild(el("li", "research-report-empty", "최근 180일 종목 리포트가 없습니다."));
    } else {
      for (const report of reports.slice(0, 8)) {
        const item = el("li", "research-report-item");
        const reportUrl = updateItemLink(report);
        const title = reportUrl ? el("a", "research-report-title", report.title || "리포트 원문") : el("strong", "research-report-title", report.title || "리포트");
        if (reportUrl) {
          title.href = reportUrl;
          title.setAttribute("aria-label", `${report.title || "리포트"} 원문 보기`);
        }
        const details = [
          report.broker_name,
          formatDateLabel(report.published_at),
          report.target_price ? `목표가 ${formatNumber(report.target_price)}` : "",
          report.opinion,
        ].filter(Boolean).join(" · ");
        item.append(title, el("span", "research-report-meta", details || "발행 정보 확인 중"));
        elements.stockResearchList.appendChild(item);
      }
    }
  }
}

function setCompanyProfileRow(row, valueNode, value) {
  if (!row || !valueNode) {
    return;
  }
  const text = String(value || "").trim();
  row.hidden = !text;
  valueNode.textContent = text || "-";
}

function setCompanyProfileLink(link, href) {
  if (!link) {
    return;
  }
  const url = String(href || "").trim();
  link.hidden = !url;
  if (url) {
    link.href = url;
  } else {
    link.removeAttribute("href");
  }
}

function renderStockCompanyProfile(data) {
  const profile = data?.company_profile || {};
  setText(elements.stockCompanySummary, profile.short_summary || profile.summary || "기업 설명을 확인할 수 없습니다.");
  const industry = [profile.industry, profile.sector]
    .map((item) => String(item || "").trim())
    .filter((item, index, items) => item && items.indexOf(item) === index)
    .join(" · ");
  if (elements.stockCompanyIndustry) {
    elements.stockCompanyIndustry.textContent = industry ? `업종 ${industry}` : "";
    elements.stockCompanyIndustry.hidden = !industry;
  }
  setCompanyProfileRow(elements.stockCompanyCeoRow, elements.stockCompanyCeo, profile.ceo_name);
  setCompanyProfileRow(
    elements.stockCompanyEstablishedRow,
    elements.stockCompanyEstablished,
    profile.established_date ? formatDateLabel(profile.established_date) : ""
  );
  setCompanyProfileRow(
    elements.stockCompanyFiscalRow,
    elements.stockCompanyFiscal,
    profile.fiscal_month ? `${Number(profile.fiscal_month)}월` : ""
  );
  setCompanyProfileRow(elements.stockCompanyAddressRow, elements.stockCompanyAddress, profile.address);
  setCompanyProfileLink(elements.stockCompanyHomepage, profile.homepage_url);
  setCompanyProfileLink(elements.stockCompanyIr, profile.ir_url);
  const sourceDate = profile.business_report_published_at ? formatDateLabel(profile.business_report_published_at) : "";
  setText(
    elements.stockCompanySourceLabel,
    [profile.source_label || "기업 정보", sourceDate].filter(Boolean).join(" · ")
  );
  setCompanyProfileLink(elements.stockCompanySourceLink, profile.source_url);
}

function renderStockDerivedIndicators(data) {
  const quotePrice = toNumber(data?.quote?.price);
  const pbr = toNumber(data?.valuation?.pbr);
  const latestEps = data?.surprise?.latest_eps ?? data?.revisions?.estimated_eps;
  const bps = quotePrice !== null && pbr !== null && pbr !== 0 ? quotePrice / pbr : null;
  setText(elements.stockEps, formatNumber(latestEps));
  setText(elements.stockBps, bps === null ? "-" : formatNumber(Math.round(bps)));
  setText(elements.stockDividendYield, "-");
  setText(elements.stockDividendPerShare, "-");
  setText(elements.stockForeignRatio, "-");
}

function resetStockPriceSummary() {
  for (const node of [
    elements.stockOpen,
    elements.stockHigh,
    elements.stockLow,
    elements.stockPrevCloseSummary,
    elements.stockVolumeDetail,
    elements.stockTradingValueDetail,
    elements.stockMarketCapDetail,
  ]) {
    setText(node, "-");
  }
  if (elements.stockMiniChart) {
    elements.stockMiniChart.innerHTML = '<p class="stock-v3-chart-empty">가격 데이터 준비 중</p>';
  }
  setText(elements.stockV2RangePercent, "-");
  setText(elements.stockV2ConsensusUpside, "-");
  setText(elements.stockV2FlowState, "-");
  setText(elements.stockV2SentimentState, "-");
  if (elements.stockV2RangeChart) elements.stockV2RangeChart.innerHTML = '<p class="stock-v2-empty">가격 범위를 계산하는 중입니다.</p>';
  if (elements.stockV2ConsensusChart) elements.stockV2ConsensusChart.innerHTML = '<p class="stock-v2-empty">리포트 목표가를 확인하는 중입니다.</p>';
  if (elements.stockV2FlowChart) elements.stockV2FlowChart.innerHTML = '<p class="stock-v2-empty">수급 데이터를 확인하는 중입니다.</p>';
  if (elements.stockV2SentimentChart) elements.stockV2SentimentChart.innerHTML = '<p class="stock-v2-empty">뉴스 분류를 확인하는 중입니다.</p>';
}

function resetStockHomeDetails() {
  state.stockIntradayRows = [];
  state.stockIntradayMeta = null;
  state.stockFlowRows = [];
  state.stockResearchRows = [];
  state.stockDisclosureRows = [];
  state.stockNewsRows = [];
  state.stockCommunity = null;
  state.stockIssueKeyword = "";
  if (elements.stockHomeUpdates) elements.stockHomeUpdates.innerHTML = '<p>리포트·공시·뉴스를 확인하는 중입니다.</p>';
  if (elements.stockHomeCheckpoints) elements.stockHomeCheckpoints.innerHTML = '<p class="stock-v3-chart-empty">수급을 확인하는 중입니다.</p>';
  if (elements.stockHomeKeywords) elements.stockHomeKeywords.innerHTML = '<p class="stock-v3-chart-empty">키워드를 정리하는 중입니다.</p>';
  if (elements.stockHomeIssueTabs) elements.stockHomeIssueTabs.innerHTML = "";
  if (elements.stockHomeIssueCard) elements.stockHomeIssueCard.innerHTML = '<p class="stock-v3-chart-empty">이슈를 연결하는 중입니다.</p>';
  if (elements.stockFinancialChart) elements.stockFinancialChart.innerHTML = '<p class="stock-v3-chart-empty">실적을 불러오는 중입니다.</p>';
  if (elements.stockFlowHistoryChart) elements.stockFlowHistoryChart.innerHTML = '<p class="stock-v3-chart-empty">수급 이력을 불러오는 중입니다.</p>';
  if (elements.stockReportHistoryChart) elements.stockReportHistoryChart.innerHTML = '<p class="stock-v3-chart-empty">목표가 이력을 불러오는 중입니다.</p>';
  if (elements.stockNewsTemperatureChart) elements.stockNewsTemperatureChart.innerHTML = '<p class="stock-v3-chart-empty">뉴스 온도를 계산하는 중입니다.</p>';
  if (elements.stockCommunityStatus) {
    elements.stockCommunityStatus.hidden = false;
    elements.stockCommunityStatus.textContent = "커뮤니티 글을 불러오는 중입니다.";
  }
  if (elements.stockCommunityProviders) elements.stockCommunityProviders.innerHTML = "";
}

function renderStockPriceSummaryFromPrices(prices, quote = null) {
  if (!Array.isArray(prices) || !prices.length) {
    return;
  }
  const latest = prices[0] || {};
  const previous = prices[1] || {};
  const previousClose = previous.close ?? previousCloseFromQuote(quote);

  setText(elements.stockPrevClose, formatNumber(previousClose));
  setText(elements.stockPrevCloseSummary, formatNumber(previousClose));
  setText(elements.stockOpen, formatNumber(latest.open));
  setText(elements.stockHigh, formatNumber(latest.high));
  setText(elements.stockLow, formatNumber(latest.low));
  setText(elements.stockVolumeDetail, formatNumber(quote?.volume ?? latest.volume));
  setText(elements.stockTradingValueDetail, formatMoney(quote?.trading_value ?? latest.trading_value));
  setText(elements.stockMarketCapDetail, formatMoney(quote?.market_cap ?? latest.market_cap));
}

async function loadStockPriceSummary(code, quote) {
  if (!code) {
    return;
  }
  resetStockPriceSummary();
  state.stockPriceRows = [];
  try {
    const marketOpen = koreaMarketPhase() === "regular";
    const prices = await fetchJsonCached(`/stocks/${encodeURIComponent(code)}/prices?limit=1000`, {
      ttlMs: marketOpen ? 30_000 : 30 * PAGE_ENTRY_MINUTE_MS,
    });
    if (state.currentStock?.code !== code) {
      return;
    }
    state.stockPriceRows = prices || [];
    renderStockPriceSummaryFromPrices(prices, quote);
    renderStockMiniChart(prices, quote);
    renderQuantSignalChart();
    renderStockV2Range(prices, quote);
    renderStockHome(state.currentDashboard);
  } catch {
    renderStockPriceSummaryFromPrices([], quote);
    renderStockMiniChart([], quote);
    renderStockV2Range([], quote);
  }
}

async function loadStockIntraday(code, requestId) {
  try {
    const marketOpen = koreaMarketPhase() === "regular";
    const endpoint = `/stocks/${encodeURIComponent(code)}/intraday?limit=390`;
    const requestUrl = marketOpen ? liveUrl(endpoint) : endpoint;
    const payload = await fetchJsonCached(requestUrl, {
      force: marketOpen,
      ttlMs: marketOpen ? 0 : 30 * PAGE_ENTRY_MINUTE_MS,
    });
    if (requestId !== state.stockHomeDetailsRequestId || state.currentStock?.code !== code) {
      return;
    }
    state.stockIntradayRows = Array.isArray(payload?.points) ? payload.points : [];
    state.stockIntradayMeta = payload || null;
    if (!state.stockIntradayRows.length) {
      state.responseCache.delete(requestUrl);
    }
  } catch {
    if (requestId === state.stockHomeDetailsRequestId) {
      state.stockIntradayRows = [];
      state.stockIntradayMeta = null;
    }
  }
  if (state.stockPricePeriod === "1D") {
    renderStockMiniChart(state.stockPriceRows, state.currentDashboard?.quote);
  }
}

async function loadStockCommunity(data, requestId) {
  const code = data?.code;
  if (!code) {
    return;
  }
  try {
    const payload = await fetchJsonCached(
      `/stocks/${encodeURIComponent(code)}/community-feed?limit=12`,
      { ttlMs: 5 * UI_CACHE_TTL_MS }
    );
    if (requestId !== state.stockHomeDetailsRequestId || state.currentStock?.code !== code) {
      return;
    }
    state.stockCommunity = payload;
    renderStockCommunity(payload);
  } catch {
    if (requestId !== state.stockHomeDetailsRequestId || state.currentStock?.code !== code) {
      return;
    }
    renderStockCommunity({
      message: "커뮤니티 글을 불러오지 못했습니다.",
      providers: [],
    });
  }
}

async function loadStockHomeDetails(data) {
  const code = data?.code;
  if (!code) {
    return;
  }
  const requestId = ++state.stockHomeDetailsRequestId;
  resetStockHomeDetails();
  renderStockHome(data);
  const intradayPromise = loadStockIntraday(code, requestId);
  void loadStockCommunity(data, requestId);
  const [flowsResult, researchResult, disclosuresResult, newsResult] = await Promise.allSettled([
    fetchJsonCached(`/stocks/${encodeURIComponent(code)}/flows?limit=5000&pages=7`, { ttlMs: 5 * PAGE_ENTRY_MINUTE_MS }),
    fetchJsonCached(`/research-reports?stock_code=${encodeURIComponent(code)}&limit=100`, { ttlMs: 5 * UI_CACHE_TTL_MS }),
    fetchJsonCached(`/disclosures?stock_code=${encodeURIComponent(code)}&limit=30`, { ttlMs: 5 * UI_CACHE_TTL_MS }),
    fetchJsonCached(`/news-items?query=${encodeURIComponent(data.name || code)}&limit=60`, { ttlMs: 2 * UI_CACHE_TTL_MS }),
  ]);
  if (requestId !== state.stockHomeDetailsRequestId || state.currentStock?.code !== code) {
    return;
  }
  state.stockFlowRows = flowsResult.status === "fulfilled" && Array.isArray(flowsResult.value) ? flowsResult.value : [];
  state.stockResearchRows = researchResult.status === "fulfilled" && Array.isArray(researchResult.value) ? researchResult.value : [];
  state.stockDisclosureRows = disclosuresResult.status === "fulfilled" && Array.isArray(disclosuresResult.value) ? disclosuresResult.value : [];
  state.stockNewsRows = newsResult.status === "fulfilled" && Array.isArray(newsResult.value) ? newsResult.value : [];
  renderStockResearchSummary(data);
  renderStockHome(data);
  await intradayPromise;
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

function socketUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

function selectorEscape(value) {
  if (window.CSS?.escape) {
    return window.CSS.escape(String(value));
  }
  return String(value).replace(/["\\]/g, "\\$&");
}

function animateQuoteNumber(node, nextValue, formatter) {
  if (nextValue === null || nextValue === undefined || nextValue === "") {
    return;
  }
  const next = Number(nextValue);
  if (!Number.isFinite(next)) {
    node.textContent = formatter(nextValue);
    return;
  }
  const previousRaw = node.dataset.rawValue;
  const previous = previousRaw === undefined || previousRaw === "" ? null : Number(previousRaw);
  node.dataset.rawValue = String(next);
  node.classList.remove("quote-updated", "quote-count-up", "quote-count-down");
  void node.offsetWidth;
  if (previous === null || !Number.isFinite(previous) || previous === next) {
    node.textContent = formatter(next);
    node.classList.add("quote-updated");
    return;
  }
  node.classList.add(next > previous ? "quote-count-up" : "quote-count-down");
  const startedAt = performance.now();
  const duration = 620;
  const tick = (now) => {
    const progress = Math.min(1, (now - startedAt) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    node.textContent = formatter(previous + (next - previous) * eased);
    if (progress < 1) {
      requestAnimationFrame(tick);
    } else {
      node.textContent = formatter(next);
      node.classList.add("quote-updated");
    }
  };
  requestAnimationFrame(tick);
}

function updateQuoteStrip(quote, payload = null) {
  if (!quote) {
    return;
  }
  if (state.currentDashboard?.quote) {
    applyLiveQuoteToDashboard(state.currentDashboard, quote, payload);
    elements.momentum1m.textContent = formatPercent(state.currentDashboard.momentum?.one_month_return);
    elements.momentum3m.textContent = formatPercent(state.currentDashboard.momentum?.three_month_return);
    setTone(elements.momentum1m, state.currentDashboard.momentum?.one_month_return);
    setTone(elements.momentum3m, state.currentDashboard.momentum?.three_month_return);
    renderStockTrendScore(state.currentDashboard);
  }
  animateQuoteNumber(elements.quotePrice, quote.price, (value) => formatNumber(Math.round(Number(value))));
  animateQuoteNumber(elements.stockChangeValue, quote.change_value, formatChangeValue);
  animateQuoteNumber(elements.quoteChange, quote.change_rate, formatPercent);
  setTone(elements.stockChangeValue, quote.change_value);
  setTone(elements.quoteChange, quote.change_rate);
  setText(elements.stockPreMarket, formatPreMarketDisplay(quote, payload));
  setText(elements.stockVolume, formatCompactCount(quote.volume));
  setText(elements.stockVolumeDetail, formatNumber(quote.volume));
  flashTextUpdate(elements.quoteValue, formatMoney(quote.trading_value), quote.trading_value);
  setText(elements.stockTradingValueDetail, formatMoney(quote.trading_value));
  if (quote.market_cap !== null && quote.market_cap !== undefined && quote.market_cap !== "") {
    animateQuoteNumber(elements.quoteCap, quote.market_cap, (value) => formatMoney(Math.round(Number(value))));
    setText(elements.stockMarketCapDetail, formatMoney(quote.market_cap));
  }
  const previousClose = previousCloseFromQuote(quote);
  setText(elements.stockPrevCloseSummary, previousClose === null ? "-" : formatNumber(Math.round(previousClose)));
  setText(elements.stockPrevClose, previousClose === null ? "-" : formatNumber(Math.round(previousClose)));
  if (payload?.as_of && state.currentStock?.code === payload.code && payload.market) {
    const sourceLabel = quoteSourceLabel(payload);
    elements.meta.textContent = stockDetailMetaText({ code: payload.code, market: payload.market });
    renderStockLiveSummary({ code: payload.code, market: payload.market, as_of: payload.as_of, quote }, sourceLabel);
  }
  if (state.stockAIAnalysis) {
    renderStockStrategyVisual(state.stockAIAnalysis);
  }
  if (state.currentDashboard) {
    renderStockV2Dashboard(state.currentDashboard);
    renderStockMiniChart(state.stockPriceRows, state.currentDashboard.quote);
    renderStockTodaySummary(state.currentDashboard);
  }
  if (
    state.stockActiveTab === "strategy"
    && state.stockQuantSignals
    && !state.stockQuantLoading
    && Date.now() - state.stockQuantLastLiveRefreshAt >= 30_000
  ) {
    state.stockQuantLastLiveRefreshAt = Date.now();
    void loadQuantSignals({ auto: true });
  }
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
  const socket = new WebSocket(socketUrl(`/ws/stocks/${encodeURIComponent(code)}/quote`));
  state.quoteSocket = socket;
  state.quoteSocketCode = code;
  socket.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload?.type === "status" && payload.code === state.currentStock?.code) {
      elements.meta.textContent = stockDetailMetaText(state.currentStock);
      setText(elements.stockLiveBadge, koreaMarketPhaseLabel());
      return;
    }
    if (payload?.type !== "quote" || payload.code !== state.currentStock?.code) {
      return;
    }
    payload.market = payload.market || state.currentStock.market;
    payload.name = payload.name || state.currentStock.name;
    updateQuoteStrip(payload.quote, payload);
  };
  socket.onclose = () => {
    if (state.view !== "stock" || state.currentStock?.code !== code) {
      return;
    }
    state.quoteReconnectTimer = window.setTimeout(() => connectQuoteStream(state.currentStock), 5000);
  };
  socket.onerror = () => {
    socket.close();
  };
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

function setLiveCellTone(cell, value) {
  if (!cell) {
    return;
  }
  cell.classList.remove("positive", "negative", "muted");
  setTone(cell, value);
}

function flashTextUpdate(node, nextText, value = null) {
  if (!node || !nextText || node.textContent === nextText) {
    return;
  }
  const previousRaw = node.dataset.rawValue;
  const previous = previousRaw === undefined || previousRaw === "" ? null : Number(previousRaw);
  const next = value === null || value === undefined || value === "" ? null : Number(value);
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

function updateWatchlistStreamStatus(code, payload) {
  const card = elements.watchlistBody.querySelector(`[data-watch-card][data-code="${selectorEscape(code)}"]`);
  if (!card || !payload) {
    return;
  }
}

function updateWatchlistRowQuote(code, quote, payload = null) {
  if (!code || !quote) {
    return;
  }
  const card = elements.watchlistBody.querySelector(`[data-watch-card][data-code="${selectorEscape(code)}"]`);
  if (!card) {
    return;
  }
  const priceCell = card.querySelector('[data-field="price"]');
  const changeCell = card.querySelector('[data-field="change_rate"]');
  const preMarketCell = card.querySelector('[data-field="pre_market"]');
  const tradingValueCell = card.querySelector('[data-field="trading_value"]');
  const oneMonthCell = card.querySelector('[data-field="one_month"]');
  const threeMonthCell = card.querySelector('[data-field="three_month"]');

  if (card.watchDashboard) {
    applyLiveQuoteToDashboard(card.watchDashboard, quote, payload);
    quote = card.watchDashboard.quote;
    if (oneMonthCell) {
      flashTextUpdate(oneMonthCell, formatPercent(card.watchDashboard.momentum?.one_month_return), card.watchDashboard.momentum?.one_month_return);
      setLiveCellTone(oneMonthCell, card.watchDashboard.momentum?.one_month_return);
    }
    if (threeMonthCell) {
      flashTextUpdate(threeMonthCell, formatPercent(card.watchDashboard.momentum?.three_month_return), card.watchDashboard.momentum?.three_month_return);
      setLiveCellTone(threeMonthCell, card.watchDashboard.momentum?.three_month_return);
    }
  }

  if (priceCell && quote.price !== null && quote.price !== undefined && quote.price !== "") {
    animateQuoteNumber(priceCell, quote.price, (value) => formatNumber(Math.round(Number(value))));
  }
  if (changeCell && quote.change_rate !== null && quote.change_rate !== undefined && quote.change_rate !== "") {
    animateQuoteNumber(changeCell, quote.change_rate, formatPercent);
    setLiveCellTone(changeCell, quote.change_rate);
  }
  if (preMarketCell) {
    const preMarketText = formatPreMarketDisplay(quote);
    flashTextUpdate(preMarketCell, preMarketText, quote.pre_market_change_rate);
    setLiveCellTone(preMarketCell, quote.pre_market_change_rate);
  }
  if (tradingValueCell && quote.trading_value !== null && quote.trading_value !== undefined && quote.trading_value !== "") {
    flashTextUpdate(tradingValueCell, formatMoney(quote.trading_value), quote.trading_value);
  }
  if (card.watchDashboard) {
    const point = renderWatchPreOpenPoint(card, card.watchDashboard, card.watchDashboard.quote, card.watchItem, card.usSectorMoves || state.usSectorMoves);
    const metrics = card.querySelector(".watch-v15-metrics");
    if (metrics && point.nextSibling !== metrics) {
      card.insertBefore(point, metrics);
    }
    const statusView = watchStatusView(card.watchDashboard);
    card.dataset.watchStatus = statusView.id;
    const status = card.querySelector('[data-field="watch_status"]');
    if (status) {
      status.className = `watch-v2-status ${statusView.tone}`;
      status.replaceChildren(el("i", ""), document.createTextNode(statusView.label));
    }
    applyWatchlistFilter();
    scheduleWatchlistStrategyRender();
  }
}

function connectWatchlistQuoteStream(code) {
  if (!code || !("WebSocket" in window)) {
    return;
  }
  const existing = state.watchlistQuoteSockets.get(code);
  if (existing && existing.readyState <= WebSocket.OPEN) {
    return;
  }
  const timer = state.watchlistQuoteReconnectTimers.get(code);
  if (timer) {
    window.clearTimeout(timer);
    state.watchlistQuoteReconnectTimers.delete(code);
  }
  const socket = new WebSocket(socketUrl(`/ws/stocks/${encodeURIComponent(code)}/quote`));
  state.watchlistQuoteSockets.set(code, socket);
  socket.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload?.type === "status" && payload.code === code) {
      updateWatchlistStreamStatus(code, payload);
      return;
    }
    if (payload?.type !== "quote" || payload.code !== code) {
      return;
    }
    updateWatchlistRowQuote(code, payload.quote, payload);
  };
  socket.onclose = () => {
    if (state.watchlistQuoteSockets.get(code) === socket) {
      state.watchlistQuoteSockets.delete(code);
    }
    if (state.view !== "portfolio" || state.portfolioTab !== "watchlist" || !elements.watchlistBody.querySelector(`[data-watch-card][data-code="${selectorEscape(code)}"]`)) {
      return;
    }
    const reconnectTimer = window.setTimeout(() => connectWatchlistQuoteStream(code), 5000);
    state.watchlistQuoteReconnectTimers.set(code, reconnectTimer);
  };
  socket.onerror = () => {
    socket.close();
  };
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

function closeRecommendationQuoteStreams() {
  for (const timer of state.recommendationQuoteReconnectTimers.values()) {
    window.clearTimeout(timer);
  }
  state.recommendationQuoteReconnectTimers.clear();
  for (const socket of state.recommendationQuoteSockets.values()) {
    socket.onclose = null;
    socket.close();
  }
  state.recommendationQuoteSockets.clear();
}

function updateRecommendationCardQuote(code, quote) {
  if (!code || !quote) {
    return;
  }
  const card = elements.recommendList.querySelector(`.recommend-card[data-code="${selectorEscape(code)}"]`);
  if (!card) {
    return;
  }
  const item = card.recommendationItem || {};
  if (quote.price !== null && quote.price !== undefined && quote.price !== "") {
    item.one_month_return = rebasePeriodReturn(item.one_month_return, item.price, quote.price);
    item.three_month_return = rebasePeriodReturn(item.three_month_return, item.price, quote.price);
    item.price = quote.price;
    const priceNode = card.querySelector('[data-field="recommend_price"]');
    if (priceNode) {
      animateQuoteNumber(priceNode, quote.price, (value) => formatNumber(Math.round(Number(value))));
    }
  }
  const oneMonthNode = card.querySelector('[data-field="recommend_one_month"]');
  const threeMonthNode = card.querySelector('[data-field="recommend_three_month"]');
  flashTextUpdate(oneMonthNode, formatPercent(item.one_month_return), item.one_month_return);
  flashTextUpdate(threeMonthNode, formatPercent(item.three_month_return), item.three_month_return);
  setLiveCellTone(oneMonthNode, item.one_month_return);
  setLiveCellTone(threeMonthNode, item.three_month_return);
  if (quote.change_rate !== null && quote.change_rate !== undefined && quote.change_rate !== "") {
    item.change_rate = quote.change_rate;
    const changeNode = card.querySelector('[data-field="recommend_change_rate"]');
    if (changeNode) {
      animateQuoteNumber(changeNode, quote.change_rate, formatPercent);
      setLiveCellTone(changeNode, quote.change_rate);
    }
  }
  if (quote.trading_value !== null && quote.trading_value !== undefined && quote.trading_value !== "") {
    item.trading_value = quote.trading_value;
    flashTextUpdate(card.querySelector('[data-field="recommend_trading_value"]'), formatMoney(quote.trading_value), quote.trading_value);
  }
  card.recommendationItem = item;
}

function connectRecommendationQuoteStream(code) {
  if (!code || !("WebSocket" in window)) {
    return;
  }
  const existing = state.recommendationQuoteSockets.get(code);
  if (existing && existing.readyState <= WebSocket.OPEN) {
    return;
  }
  const timer = state.recommendationQuoteReconnectTimers.get(code);
  if (timer) {
    window.clearTimeout(timer);
    state.recommendationQuoteReconnectTimers.delete(code);
  }
  const socket = new WebSocket(socketUrl(`/ws/stocks/${encodeURIComponent(code)}/quote`));
  state.recommendationQuoteSockets.set(code, socket);
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
    updateRecommendationCardQuote(code, payload.quote);
    updateTrackedRecommendationQuote(code, payload.quote);
  };
  socket.onclose = () => {
    if (state.recommendationQuoteSockets.get(code) === socket) {
      state.recommendationQuoteSockets.delete(code);
    }
    const hasTarget =
      Boolean(elements.recommendList.querySelector(`.recommend-card[data-code="${selectorEscape(code)}"]`))
      || Boolean(elements.recommendHistoryList.querySelector(`.recommend-track-card[data-code="${selectorEscape(code)}"]`));
    if (!["search", "portfolio"].includes(state.view) || !hasTarget) {
      return;
    }
    const reconnectTimer = window.setTimeout(() => connectRecommendationQuoteStream(code), 5000);
    state.recommendationQuoteReconnectTimers.set(code, reconnectTimer);
  };
  socket.onerror = () => {
    socket.close();
  };
}

function sortMarketLeaderboardItems() {
  state.marketLeaderboardItems.sort((a, b) => {
    const changeDiff = (toNumber(b.change_rate) ?? -Infinity) - (toNumber(a.change_rate) ?? -Infinity);
    if (changeDiff !== 0) {
      return changeDiff;
    }
    return (toNumber(b.trading_value) ?? 0) - (toNumber(a.trading_value) ?? 0);
  });
  state.marketLeaderboardItems = state.marketLeaderboardItems.map((item, index) => ({
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
    item.one_month_return = rebasePeriodReturn(item.one_month_return, item.price, quote.price);
    item.three_month_return = rebasePeriodReturn(item.three_month_return, item.price, quote.price);
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
  renderMarketSurgeLeaderboard({ live: true });
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
  const socket = new WebSocket(socketUrl(`/ws/stocks/${encodeURIComponent(code)}/quote`));
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
    if (state.view !== "search" || state.rankingCategory !== "surge") {
      return;
    }
    const reconnectTimer = window.setTimeout(() => connectMarketQuoteStream(code), 5000);
    state.marketQuoteReconnectTimers.set(code, reconnectTimer);
  };
  socket.onerror = () => {
    socket.close();
  };
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

function formatDateLabel(value) {
  if (!value) {
    return "-";
  }
  return String(value).replace("T", " ").slice(0, 10);
}

function formatDataBasis(value, fallback = "기준 정보 확인 중") {
  if (!value) {
    return fallback;
  }
  const source = String(value).trim();
  const dateMatch = source.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}:\d{2}))?/);
  if (!dateMatch) {
    return fallback;
  }
  return `${dateMatch[1]}${dateMatch[2] ? ` ${dateMatch[2]}` : ""} 기준`;
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

function createStockListLogo(code) {
  const normalizedCode = String(code || "").trim().toUpperCase();
  const frame = el("span", "stock-list-logo");
  frame.setAttribute("aria-hidden", "true");
  if (!normalizedCode) {
    frame.classList.add("is-empty");
    return frame;
  }
  const image = document.createElement("img");
  image.src = `/stock-logos/${encodeURIComponent(normalizedCode)}.png`;
  image.alt = "";
  image.loading = "lazy";
  image.decoding = "async";
  frame.appendChild(image);
  return frame;
}

function createStockListCopy(name, code, market) {
  const copy = el("span", "stock-list-copy");
  copy.append(
    el("strong", "", name || code || "-"),
    el("small", "", `${code || "-"} · ${market || "-"}`)
  );
  return copy;
}

function clonePayload(payload) {
  return JSON.parse(JSON.stringify(payload));
}

function liveUrl(url) {
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}_=${Date.now()}`;
}

function isUncachedKoreaMarketDataUrl(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return /^\/stocks\/(?:search|resolve)$/.test(parsed.pathname)
      || /^\/stocks\/[^/]+\/quote$/.test(parsed.pathname)
      || (/^\/stocks\/[^/]+\/dashboard$/.test(parsed.pathname) && parsed.searchParams.get("include_live") !== "0");
  } catch {
    return false;
  }
}

async function fetchJsonCached(url, options = {}) {
  const bypassCache = isUncachedKoreaMarketDataUrl(url);
  const ttlMs = bypassCache ? 0 : options.ttlMs ?? UI_CACHE_TTL_MS;
  const force = bypassCache || Boolean(options.force);
  const timeoutMs = Number(options.timeoutMs) > 0 ? Number(options.timeoutMs) : 0;
  const now = Date.now();
  const cached = state.responseCache.get(url);
  if (!bypassCache && !force && cached && now - cached.savedAt <= ttlMs) {
    return clonePayload(cached.payload);
  }
  if (!bypassCache && !force && state.pendingRequests.has(url)) {
    return clonePayload(await state.pendingRequests.get(url));
  }
  const controller = timeoutMs ? new AbortController() : null;
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(), timeoutMs)
    : null;
  const request = fetch(url, {
    cache: force || ttlMs === 0 ? "no-store" : "default",
    signal: controller?.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`request failed: ${url}`);
      }
      const payload = await response.json();
      if (!bypassCache) {
        state.responseCache.set(url, { savedAt: Date.now(), payload: clonePayload(payload) });
      }
      return payload;
    })
    .finally(() => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    });
  if (!bypassCache) {
    state.pendingRequests.set(url, request);
  }
  try {
    return clonePayload(await request);
  } finally {
    if (!bypassCache) {
      state.pendingRequests.delete(url);
    }
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
  if (currentScrollTop() > 0) {
    return false;
  }
  if (!(target instanceof Element)) {
    return true;
  }
  return !target.closest(
    "a, button, [role='button'], [role='link'], input, textarea, select, .suggestions, .loading-modal-card, .install-sheet-card",
  );
}

async function refreshCurrentView() {
  switch (state.view) {
    case "stock": {
      const query = state.currentStock?.name || pathQuery();
      const shouldRefreshAI = state.stockAIAnalysis !== null || elements.aiAnalysisPanel?.hidden === false;
      const shouldRefreshQuant = state.stockQuantSignals !== null || state.stockActiveTab === "strategy";
      await load(query);
      if (shouldRefreshAI && state.currentStock?.code) {
        await loadAIAnalysis({ auto: false, force: true });
      }
      if (shouldRefreshQuant && state.currentStock?.code) {
        await loadQuantSignals({ auto: false, force: true });
      }
      return;
    }
    case "home":
      await Promise.all([
        loadTrends(state.activeTrendTab === "impact" ? "live" : state.activeTrendTab || "live", { force: true }),
        loadMarketImpactAnalysis({ force: true, embedded: true }),
        loadHomeMarketIndices({ force: true }),
        loadHomeAiSignals({ force: true, ttlMs: 0 }),
        loadHomeSurgeRankings({ force: true, ttlMs: 0 }),
      ]);
      return;
    case "search":
      await loadRecommendations({ auto: true, force: true, recompute: true });
      return;
    case "movers":
      state.marketRankingCache.delete(marketRankingKey("surge", currentMarketFilter(), 30));
      await loadMarketRankings({ market: currentMarketFilter(), limit: 30, force: true });
      return;
    case "portfolio":
      if (state.portfolioTab === "tracking") {
        await loadRecommendationHistory({ force: true });
      } else {
        await Promise.all([loadWatchlist({ force: true }), loadTrendWatchlistNews({ force: true })]);
      }
      return;
    case "chart":
      if (state.watchChartResults[0]?.item) {
        await loadWatchCharts({ items: [state.watchChartResults[0].item], force: true, single: true });
      }
      return;
    case "chart-history":
      renderChartSnapshots();
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
  try {
    await refreshCurrentView().catch(() => null);
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
  elements.input.value = item.name;
  hideSuggestions();
  load(item.name);
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
    const response = await fetch(`/stocks/search?query=${encodeURIComponent(normalized)}&limit=30`, {
      signal: state.suggestionController.signal,
      cache: "no-store",
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

function hideStandaloneSuggestions(input, container) {
  if (!input || !container) {
    return;
  }
  container.hidden = true;
  container.innerHTML = "";
  input.setAttribute("aria-expanded", "false");
}

function renderStandaloneSuggestions(input, container, items, onChoose) {
  if (!input || !container) {
    return;
  }
  container.innerHTML = "";
  if (!Array.isArray(items) || !items.length) {
    hideStandaloneSuggestions(input, container);
    return;
  }
  for (const item of items.slice(0, 12)) {
    const button = document.createElement("button");
    button.className = "discovery-suggestion-item";
    button.type = "button";
    button.setAttribute("role", "option");
    button.append(
      el("strong", "", item.name || item.code),
      el("span", "", `${item.code || ""}${item.market ? ` · ${item.market}` : ""}`),
    );
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => {
      input.value = item.name || item.code || "";
      hideStandaloneSuggestions(input, container);
      onChoose(item);
    });
    container.appendChild(button);
  }
  container.hidden = false;
  input.setAttribute("aria-expanded", "true");
}

async function fetchStandaloneSuggestions(kind, query) {
  const normalized = String(query || "").trim();
  const isChart = kind === "chart";
  const input = isChart ? elements.chartStockSearchInput : elements.discoverySearchInput;
  const container = isChart ? elements.chartStockSearchSuggestions : elements.discoverySearchSuggestions;
  const controllerKey = isChart ? "chartSuggestionController" : "discoverySuggestionController";
  if (!normalized) {
    hideStandaloneSuggestions(input, container);
    return;
  }
  state[controllerKey]?.abort();
  const controller = new AbortController();
  state[controllerKey] = controller;
  try {
    const response = await fetch(`/stocks/search?query=${encodeURIComponent(normalized)}&limit=12`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      hideStandaloneSuggestions(input, container);
      return;
    }
    const items = await response.json();
    if (document.activeElement !== input) {
      hideStandaloneSuggestions(input, container);
      return;
    }
    if (isChart) {
      state.chartSuggestions = items;
      renderStandaloneSuggestions(input, container, items, (item) => void loadChartStock(item));
    } else {
      state.discoverySuggestions = items;
      renderStandaloneSuggestions(input, container, items, (item) => void load(item.name || item.code));
    }
  } catch (error) {
    if (error.name !== "AbortError") {
      hideStandaloneSuggestions(input, container);
    }
  }
}

function scheduleStandaloneSuggestions(kind) {
  const isChart = kind === "chart";
  const timerKey = isChart ? "chartSuggestionTimer" : "discoverySuggestionTimer";
  const input = isChart ? elements.chartStockSearchInput : elements.discoverySearchInput;
  window.clearTimeout(state[timerKey]);
  state[timerKey] = window.setTimeout(() => fetchStandaloneSuggestions(kind, input?.value), 160);
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

function sentimentBreakdown(sentiment = {}) {
  const positiveCount = Math.max(0, Number(sentiment?.positive_count) || 0);
  const negativeCount = Math.max(0, Number(sentiment?.negative_count) || 0);
  const neutralCount = Math.max(0, Number(sentiment?.neutral_count) || 0);
  const directionalCount = positiveCount + negativeCount;
  if (!directionalCount) {
    return {
      positiveText: `긍정 ${formatRatioPercent(0)} · 0건`,
      negativeText: neutralCount ? `부정 ${formatRatioPercent(0)} · 0건` : "부정 -",
      hasDirectionalSignal: false,
    };
  }
  const positiveRate = (positiveCount / directionalCount) * 100;
  const negativeRate = (negativeCount / directionalCount) * 100;
  return {
    positiveText: `긍정 ${formatRatioPercent(positiveRate)} · ${formatNumber(positiveCount)}건`,
    negativeText: `부정 ${formatRatioPercent(negativeRate)} · ${formatNumber(negativeCount)}건`,
    hasDirectionalSignal: true,
  };
}

function viewStockUrl(name) {
  return `/dashboard/${encodeURIComponent(name)}`;
}

function stockRouteQuery(href) {
  try {
    const url = new URL(href, window.location.origin);
    if (url.origin !== window.location.origin) {
      return "";
    }
    const parts = url.pathname.split("/").filter(Boolean);
    return parts[0] === "dashboard" && parts[1] ? decodeURIComponent(parts[1]) : "";
  } catch {
    return "";
  }
}

function navigateToStock(query, href = viewStockUrl(query)) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    return Promise.resolve();
  }
  const url = new URL(href, window.location.origin);
  const nextPath = `${url.pathname}${url.search}${url.hash}`;
  if (`${window.location.pathname}${window.location.search}${window.location.hash}` !== nextPath) {
    history.pushState({ view: "stock" }, "", nextPath);
  }
  setView("stock");
  window.scrollTo({ top: 0, behavior: "auto" });
  return load(normalized, { historyMode: "none" });
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
  elements.watchlistIdStatus.className = ["sr-only", tone].filter(Boolean).join(" ");
  updateWatchlistIdentityDisplay();
}

function setLoginStatus(text, tone = "") {
  if (!elements.loginStatus) {
    return;
  }
  elements.loginStatus.textContent = text;
  elements.loginStatus.className = `login-status${tone ? ` ${tone}` : ""}`;
}

function setLoginGatePhase(phase) {
  if (!elements.loginGate) {
    return;
  }
  elements.loginGate.dataset.phase = phase;
}

function showLoginGate(message = "", options = {}) {
  if (!elements.loginGate) {
    return;
  }
  document.documentElement.classList.remove("has-saved-watchlist-id");
  const skipSplash = options.skipSplash ?? state.loginSplashSeen;
  window.clearTimeout(state.loginGateTimer);
  elements.loginGate.hidden = false;
  setLoginStatus(message);
  if (skipSplash) {
    setLoginGatePhase("form");
    window.setTimeout(() => {
      elements.loginInput?.focus();
    }, 50);
    return;
  }
  setLoginGatePhase("splash");
  state.loginSplashSeen = true;
  state.loginGateTimer = window.setTimeout(() => {
    setLoginGatePhase("form");
    window.setTimeout(() => {
      elements.loginInput?.focus();
    }, 40);
  }, LOGIN_SPLASH_DURATION_MS);
}

function hideLoginGate() {
  if (!elements.loginGate) {
    return;
  }
  window.clearTimeout(state.loginGateTimer);
  state.loginGateTimer = null;
  elements.loginGate.hidden = true;
  document.documentElement.classList.add("has-saved-watchlist-id");
}

async function fetchRemoteWatchlist(shareId) {
  const response = await fetch(`/watchlists/${encodeURIComponent(shareId)}`);
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
  const response = await fetch(`/session/write-token?share_id=${encodeURIComponent(normalizedId)}`, {
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
    fetch(`/watchlists/${encodeURIComponent(state.watchlistId)}`, {
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
  state.pushNotificationEnabled = readCachedPushEnabled();
  hydratePushNotificationHistory();
  updatePushNotificationButton({
    label: state.pushNotificationEnabled ? "알림 내역" : "알림 설정",
    buttonText: "알림",
    active: state.pushNotificationEnabled,
  });
  if (elements.watchlistIdInput) {
    elements.watchlistIdInput.value = normalizedId;
  }
  updateWatchlistIdentityDisplay();
  setWatchlistIdStatus("서버 목록 불러오는 중");
  const syncIdentity = async () => {
    const localItems = readWatchlist();
    const remotePayload = await fetchRemoteWatchlist(normalizedId);
    const remoteItems = normalizeWatchlistItems(remotePayload.items || []);
    const merged = options.merge === false ? remoteItems : normalizeWatchlistItems([...localItems, ...remoteItems]);
    writeWatchlist(merged, { sync: false });
    setWatchlistIdStatus(`${normalizedId} · ${formatNumber(merged.length)}개 동기화`, "success");
    if (JSON.stringify(merged) !== JSON.stringify(remoteItems)) {
      queueRemoteWatchlistSync();
    }
    if (options.backgroundSync !== true) {
      void refreshPushNotificationState({ syncServer: false });
    }
    updateWatchButton();
    if (options.refreshView !== false) {
      if (state.view === "portfolio" && state.portfolioTab === "watchlist") {
        void loadWatchlist();
      }
    }
  };
  if (options.backgroundSync === true) {
    void refreshPushNotificationState({ syncServer: false });
    void syncIdentity().catch(() => {
      setWatchlistIdStatus(`${normalizedId} · 저장된 목록 사용 중`, "error");
    });
    return true;
  }
  try {
    await syncIdentity();
    return true;
  } catch {
    setWatchlistIdStatus("동기화 실패 · ID를 확인해주세요", "error");
    return false;
  }
}

async function logoutWatchlistIdentity() {
  const currentId = state.watchlistId;
  if (currentId) {
    await disablePushNotifications(currentId).catch(() => undefined);
  }
  window.clearTimeout(state.watchlistSyncTimer);
  stopPushNotificationUnreadRefresh();
  state.watchlistSyncTimer = null;
  state.watchlistSyncing = false;
  state.watchlistId = "";
  state.writeToken = "";
  state.writeTokenShareId = "";
  state.pushNotificationHistory = [];
  state.pushNotificationUnread = false;
  localStorage.removeItem(WATCHLIST_ID_KEY);
  localStorage.removeItem(WATCHLIST_KEY);
  localStorage.removeItem("analyst.watchlistActivity");
  closeQuoteStream();
  closeWatchlistQuoteStreams();
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
    elements.watchlistBody.innerHTML = '<p class="muted">로그인 후 관심 종목을 불러옵니다.</p>';
  }
  if (elements.watchlistMeta) {
    elements.watchlistMeta.textContent = "로그인 필요";
  }
  if (elements.watchChartList) {
    elements.watchChartList.innerHTML = '<p class="muted">로그인 후 AI 차트 분석을 불러옵니다.</p>';
  }
  setWatchlistIdStatus("로그아웃됨");
  updatePushNotificationButton({ hidden: true });
  showLoginGate("로그아웃되었습니다. 다시 아이디를 입력해주세요.", { skipSplash: true });
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
    const [ok] = await Promise.all([
      applyWatchlistId(savedId, { merge: true, refreshView: false, backgroundSync: true }),
      delay(LOGIN_SPLASH_DURATION_MS),
    ]);
    if (ok) {
      hideLoginGate();
    } else {
      showLoginGate("저장된 아이디를 불러오지 못했습니다. 다시 입력해주세요.", { skipSplash: true });
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
    elements.watchToggle.textContent = "☆";
    elements.watchToggle.setAttribute("aria-label", "관심종목 추가");
    elements.watchToggle.title = "관심종목 추가";
    return;
  }
  const active = isWatched(state.currentStock.code);
  elements.watchToggle.disabled = false;
  elements.watchToggle.classList.toggle("active", active);
  elements.watchToggle.textContent = active ? "★" : "☆";
  elements.watchToggle.setAttribute("aria-label", active ? "관심종목 해제" : "관심종목 추가");
  elements.watchToggle.title = active ? "관심종목 해제" : "관심종목 추가";
}

function toggleWatchCurrent() {
  if (!state.currentStock) {
    return;
  }
  toggleWatchlistItem(state.currentStock);
  updateWatchButton();
  if (state.view === "portfolio" && state.portfolioTab === "watchlist") {
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
    button.textContent = active ? "관심 해제" : "관심 추가";
  }
}

function updateRecommendationTrackButtons() {
  for (const button of document.querySelectorAll(".recommend-track-button")) {
    const code = button.dataset.code || "";
    const active = isTrackedRecommendation(code);
    button.classList.toggle("active", active);
    button.textContent = active ? "핀 종목 보기" : "핀 설정하기";
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

function pushNotificationOptions() {
  return state.pushConfig?.condition_options || PUSH_NOTIFICATION_FALLBACK_OPTIONS;
}

function normalizePushNotificationConditions(values) {
  const options = pushNotificationOptions();
  const allowed = new Set(options.map((item) => item.id));
  const required = options.filter((item) => item.required).map((item) => item.id);
  const normalized = Array.isArray(values)
    ? [...new Set(values.map((item) => String(item || "").trim()).filter((item) => allowed.has(item)))]
    : [];
  const selected = normalized.length ? normalized : options.map((item) => item.id);
  return [...new Set([...required, ...selected])];
}

function selectedPushNotificationConditions() {
  if (!elements.pushNotificationConditionList) {
    return [];
  }
  return Array.from(elements.pushNotificationConditionList.querySelectorAll("input[data-push-condition]:checked")).map((input) => input.value);
}

function renderPushNotificationConditionOptions() {
  const list = elements.pushNotificationConditionList;
  if (!list) {
    return;
  }
  const selected = new Set(state.pushNotificationConditions);
  const disabled = state.pushNotificationBusy;
  list.innerHTML = "";
  for (const option of pushNotificationOptions()) {
    const row = el("label", "push-notification-condition");
    const copy = el("span", "push-notification-condition-copy");
    copy.append(el("strong", "", option.label));
    copy.append(el("span", "", option.description));
    const control = el("span", "push-notification-condition-control");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = option.id;
    input.dataset.pushCondition = option.id;
    input.checked = option.required || selected.has(option.id);
    input.disabled = disabled || option.required;
    input.addEventListener("change", () => {
      state.pushNotificationConditions = selectedPushNotificationConditions();
      updatePushNotificationSheet();
    });
    const switchTrack = el("span", "push-notification-condition-switch");
    if (option.required) {
      copy.append(el("em", "push-notification-required", "항상 받기"));
      row.classList.add("is-required");
    }
    control.append(input, switchTrack);
    row.append(copy, control);
    list.append(row);
  }
}

function showPushNotificationSheet() {
  renderPushNotificationConditionOptions();
  updatePushNotificationSheet();
  if (elements.pushNotificationSheet) {
    elements.pushNotificationSheet.hidden = false;
  }
  document.body.classList.add("modal-open");
}

function closePushNotificationSheet() {
  if (elements.pushNotificationSheet) {
    elements.pushNotificationSheet.hidden = true;
  }
  document.body.classList.remove("modal-open");
}

const PUSH_HISTORY_KIND_LABELS = {
  ai_signal: "AI 매매신호",
  market_ai_signal: "시장 AI 매매신호",
  price_move: "시세",
  price_move_digest: "시세",
  report: "리포트",
  disclosure: "공시",
  major_event: "주요 이벤트",
  test: "테스트",
};

const PUSH_HISTORY_WATCHLIST_KINDS = new Set(["price_move", "price_move_digest", "report", "disclosure"]);

function pushHistoryCacheKey() {
  return scopedStorageKey(PUSH_HISTORY_CACHE_PREFIX);
}

function pushLastSeenStorageKey() {
  return scopedStorageKey(PUSH_LAST_SEEN_PREFIX);
}

function recentPushHistoryItems(items = []) {
  const cutoff = Date.now() - 3 * 24 * 60 * 60 * 1000;
  return items.filter((item) => {
    const timestamp = Date.parse(item?.created_at || "");
    return Number.isFinite(timestamp) && timestamp >= cutoff;
  });
}

function readCachedPushHistory() {
  const cached = readStoredJson(pushHistoryCacheKey(), null);
  return recentPushHistoryItems(Array.isArray(cached?.items) ? cached.items : []);
}

function writeCachedPushHistory(items = []) {
  writeStoredJson(pushHistoryCacheKey(), { savedAt: Date.now(), items: recentPushHistoryItems(items) });
}

function updatePushUnreadFromHistory(items = state.pushNotificationHistory) {
  const newest = items.reduce((latest, item) => Math.max(latest, Date.parse(item?.created_at || "") || 0), 0);
  const seenAt = Number(localStorage.getItem(pushLastSeenStorageKey()) || 0);
  setPushNotificationUnread(newest > seenAt);
}

function markPushNotificationsSeen() {
  const newest = state.pushNotificationHistory.reduce(
    (latest, item) => Math.max(latest, Date.parse(item?.created_at || "") || 0),
    Date.now(),
  );
  const key = pushLastSeenStorageKey();
  if (key) {
    localStorage.setItem(key, String(newest));
  }
  setPushNotificationUnread(false);
}

function hydratePushNotificationHistory() {
  state.pushNotificationHistory = readCachedPushHistory();
  updatePushUnreadFromHistory();
}

function formatPushHistoryTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function pushHistoryItemsForActiveTab() {
  const tab = state.pushNotificationHistoryTab;
  if (tab === "all") {
    return state.pushNotificationHistory;
  }
  if (tab === "watchlist") {
    return state.pushNotificationHistory.filter((item) => PUSH_HISTORY_WATCHLIST_KINDS.has(item.kind));
  }
  if (tab === "ai_signal") {
    return state.pushNotificationHistory.filter((item) => ["ai_signal", "market_ai_signal"].includes(item.kind));
  }
  return state.pushNotificationHistory.filter((item) => item.kind === tab);
}

function updatePushHistoryTabs() {
  for (const tab of elements.pushHistoryTabs) {
    const selected = tab.dataset.notificationTab === state.pushNotificationHistoryTab;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  }
}

function renderPushNotificationHistory(options = {}) {
  const list = elements.pushHistoryList;
  if (!list) {
    return;
  }
  list.replaceChildren();
  if (options.loading) {
    if (elements.pushHistoryMeta) {
      elements.pushHistoryMeta.textContent = "알림을 불러오는 중";
    }
    const loading = el("div", "push-history-state");
    loading.textContent = "알림을 불러오는 중입니다.";
    list.append(loading);
    return;
  }
  if (options.error) {
    if (elements.pushHistoryMeta) {
      elements.pushHistoryMeta.textContent = "불러오기 실패";
    }
    const error = el("div", "push-history-state is-error");
    error.textContent = "알림 내역을 불러오지 못했습니다. 잠시 후 다시 열어주세요.";
    list.append(error);
    return;
  }
  updatePushHistoryTabs();
  const items = pushHistoryItemsForActiveTab();
  if (elements.pushHistoryMeta) {
    elements.pushHistoryMeta.textContent = `${items.length}건 · 최근 3일`;
  }
  if (!items.length) {
    const empty = el("div", "push-history-state");
    const title = el("strong");
    title.textContent = state.pushNotificationHistory.length ? "이 유형의 알림이 없습니다." : "새 알림이 없습니다.";
    const copy = el("span");
    copy.textContent = "최근 3일 동안 받은 알림이 여기에 표시됩니다.";
    empty.append(title, copy);
    list.append(empty);
    return;
  }
  let previousDate = "";
  for (const item of items) {
    const formattedTime = formatPushHistoryTime(item.created_at);
    const itemDate = formattedTime.slice(0, 10);
    if (itemDate && itemDate !== previousDate) {
      const dateHeading = el("h2", "notifications-date", itemDate);
      list.append(dateHeading);
      previousDate = itemDate;
    }
    const row = el("button", `push-history-item kind-${item.kind || "default"}`);
    row.type = "button";
    row.setAttribute("role", "listitem");
    const meta = el("span", "push-history-item-meta");
    const kind = el("span");
    kind.textContent = PUSH_HISTORY_KIND_LABELS[item.kind] || "알림";
    const time = el("time");
    time.dateTime = item.created_at || "";
    time.textContent = formattedTime.slice(11) || formattedTime;
    meta.append(kind, time);
    const title = el("strong", "push-history-item-title");
    title.textContent = item.title || "알림";
    const body = el("span", "push-history-item-body");
    body.textContent = item.body || "";
    row.append(meta, title, body);
    if (item.url) {
      row.addEventListener("click", () => {
        window.location.assign(item.url);
      });
    } else {
      row.disabled = true;
    }
    list.append(row);
  }
  if (options.restoreScroll) {
    const savedScrollTop = state.pushNotificationHistoryScrollTop.get(state.pushNotificationHistoryTab) || 0;
    window.requestAnimationFrame(() => {
      list.scrollTop = savedScrollTop;
    });
  }
}

async function loadPushNotificationHistory(options = {}) {
  if (!state.watchlistId || state.pushNotificationHistoryBusy) {
    return;
  }
  if (!state.pushNotificationHistory.length) {
    hydratePushNotificationHistory();
  }
  state.pushNotificationHistoryBusy = true;
  if (options.render !== false) {
    if (state.pushNotificationHistory.length) {
      renderPushNotificationHistory();
    } else if (!options.silent) {
      renderPushNotificationHistory({ loading: true });
    }
  }
  try {
    const writeToken = await ensureWriteToken(state.watchlistId);
    const response = await fetch(`/push/notifications/${encodeURIComponent(state.watchlistId)}`, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Write-Token": writeToken },
    });
    if (!response.ok) {
      throw new Error("push history failed");
    }
    const payload = await response.json();
    state.pushNotificationHistory = Array.isArray(payload.items) ? payload.items : [];
    writeCachedPushHistory(state.pushNotificationHistory);
    if (state.view === "notifications") {
      markPushNotificationsSeen();
    } else {
      updatePushUnreadFromHistory();
    }
    if (options.render !== false || state.view === "notifications") {
      renderPushNotificationHistory();
    }
  } catch {
    if (options.render !== false && !state.pushNotificationHistory.length) {
      renderPushNotificationHistory({ error: true });
    }
  } finally {
    state.pushNotificationHistoryBusy = false;
  }
}

function setPushNotificationSheetStatus(text = "", tone = "") {
  if (!elements.pushNotificationSheetStatus) {
    return;
  }
  elements.pushNotificationSheetStatus.textContent = text;
  elements.pushNotificationSheetStatus.dataset.tone = tone;
}

function updatePushNotificationDisableButton(options = {}) {
  if (!elements.pushNotificationDisableButton) {
    return;
  }
  const hidden = options.hidden ?? !state.pushNotificationEnabled;
  elements.pushNotificationDisableButton.hidden = hidden;
  elements.pushNotificationDisableButton.disabled = options.disabled ?? false;
}

function updatePushNotificationSheet() {
  renderPushNotificationConditionOptions();
  const saveButton = elements.pushNotificationSheetSaveButton;
  const testButton = elements.pushNotificationSheetTestButton;
  const disableButton = elements.pushNotificationSheetDisableButton;
  const selected = state.pushNotificationConditions;
  const configReady = Boolean(state.pushConfig?.enabled && state.pushConfig?.public_key);
  const supported = webPushSupported();
  const permissionDenied = supported && Notification.permission === "denied";
  const busy = state.pushNotificationBusy;
  if (saveButton) {
    saveButton.textContent = busy ? "저장 중" : state.pushNotificationEnabled ? "설정 저장" : "알림 켜기";
  }
  if (disableButton) {
    disableButton.hidden = !state.pushNotificationEnabled;
    disableButton.disabled = busy;
  }
  if (testButton) {
    testButton.hidden = !state.pushNotificationEnabled;
    testButton.disabled = busy;
  }
  if (isIOSDevice() && !isStandaloneApp()) {
    saveButton && (saveButton.disabled = true);
    testButton && (testButton.disabled = true);
    setPushNotificationSheetStatus("iPhone은 홈 화면에 설치한 비밀노트 앱에서만 알림을 받을 수 있습니다.", "error");
    return;
  }
  if (!supported) {
    saveButton && (saveButton.disabled = true);
    setPushNotificationSheetStatus("이 브라우저에서는 웹 알림을 지원하지 않습니다.", "error");
    return;
  }
  if (!configReady) {
    saveButton && (saveButton.disabled = true);
    setPushNotificationSheetStatus("알림 기능을 준비하고 있습니다. 잠시 후 다시 시도해주세요.");
    return;
  }
  if (permissionDenied) {
    saveButton && (saveButton.disabled = true);
    setPushNotificationSheetStatus("브라우저 설정에서 알림 권한을 허용한 뒤 다시 열어주세요.", "error");
    return;
  }
  if (!selected.length) {
    saveButton && (saveButton.disabled = true);
    setPushNotificationSheetStatus("최소 한 가지 알림은 선택해주세요.", "error");
    return;
  }
  saveButton && (saveButton.disabled = busy);
  setPushNotificationSheetStatus(
    state.pushNotificationEnabled ? "받고 싶은 알림만 남기고 저장할 수 있어요." : "받고 싶은 알림을 고른 뒤 알림을 켜주세요.",
    state.pushNotificationEnabled ? "success" : ""
  );
}

async function openPushNotificationSheet() {
  if (!state.watchlistId || state.pushNotificationBusy) {
    return;
  }
  await refreshPushNotificationState();
  showPushNotificationSheet();
}

async function openPushNotificationCenter() {
  if (!state.watchlistId || state.pushNotificationBusy) {
    return;
  }
  const likelyEnabled = state.pushNotificationEnabled
    || readCachedPushEnabled()
    || (webPushSupported() && Notification.permission === "granted");
  if (!likelyEnabled) {
    showPushNotificationSheet();
    void refreshPushNotificationState().then(updatePushNotificationSheet);
    return;
  }
  state.pushNotificationEnabled = true;
  writeCachedPushEnabled(true);
  hydratePushNotificationHistory();
  state.notificationReturnView = state.view === "notifications" ? state.notificationReturnView : state.view;
  setView("notifications");
  markPushNotificationsSeen();
  window.scrollTo({ top: 0, behavior: "auto" });
  void refreshPushNotificationState();
}

async function openPushSettingsFromHistory() {
  await openPushNotificationSheet();
}

function setFlowLoading(open) {
  if (!elements.flowLoadingModal) {
    return;
  }
  elements.flowLoadingModal.hidden = !open;
  document.body.classList.toggle("modal-open", open);
}

const PAGE_LOADING_MINIMUM_MS = 320;
const PAGE_LOADING_LABELS = {
  stock: "종목 정보를 불러오는 중",
  watchlist: "관심 종목을 점검하는 중",
  recommend: "추천 종목을 분석하는 중",
  "recommend-history": "핀 종목을 불러오는 중",
  trend: "주요 이벤트를 불러오는 중",
  "trend-past": "지난 이벤트를 불러오는 중",
  "trend-impact": "시장 영향도를 계산하는 중",
  chart: "차트 분석을 불러오는 중",
  market: "급상승 종목을 불러오는 중",
  ai: "AI 매매신호를 계산하는 중",
};

function refreshPageLoading() {
  if (!elements.pageLoading) {
    return;
  }
  const entries = Array.from(state.pageLoadingTokens.values());
  if (entries.length) {
    elements.pageLoadingLabel.textContent = entries[entries.length - 1].label;
    elements.pageLoading.hidden = false;
    document.body.setAttribute("aria-busy", "true");
    window.requestAnimationFrame(() => elements.pageLoading?.classList.add("visible"));
    return;
  }
  elements.pageLoading.classList.remove("visible");
  document.body.removeAttribute("aria-busy");
  window.setTimeout(() => {
    if (state.pageLoadingTokens.size === 0 && elements.pageLoading) {
      elements.pageLoading.hidden = true;
    }
  }, 150);
}

function clearPageLoading() {
  state.pageLoadingTokens.clear();
  if (!elements.pageLoading) {
    return;
  }
  elements.pageLoading.classList.remove("visible");
  elements.pageLoading.hidden = true;
  document.body.removeAttribute("aria-busy");
}

function beginPageLoading(label = "데이터를 불러오는 중") {
  state.pageLoadingSequence += 1;
  const token = state.pageLoadingSequence;
  state.pageLoadingTokens.set(token, { label, startedAt: Date.now() });
  refreshPageLoading();
  return token;
}

function endPageLoading(token) {
  const entry = state.pageLoadingTokens.get(token);
  if (!entry) {
    return;
  }
  const remaining = Math.max(0, PAGE_LOADING_MINIMUM_MS - (Date.now() - entry.startedAt));
  window.setTimeout(() => {
    state.pageLoadingTokens.delete(token);
    refreshPageLoading();
  }, remaining);
}

async function runPageLoading(label, operation) {
  const token = beginPageLoading(label);
  try {
    return await operation();
  } finally {
    endPageLoading(token);
  }
}

function launchPageLoading(label, operation) {
  return runPageLoading(label, operation).catch(() => undefined);
}

function launchBriefPageLoading(label, operation, maxWaitMs = 1800) {
  const task = Promise.resolve().then(operation);
  task.catch(() => undefined);
  return runPageLoading(label, () => Promise.race([task, delay(maxWaitMs)])).catch(() => undefined);
}

async function handleHomeInstall() {
  showInstallSheet();
}

function registerDashboardServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  navigator.serviceWorker.register("/dashboard-sw.js", { scope: "/" }).catch(() => undefined);
}

function webPushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function pushApplicationServerKey(value) {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = `${value}${padding}`.replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map((character) => character.charCodeAt(0)));
}

function setPushNotificationStatus(text = "", tone = "") {
  if (!elements.pushNotificationStatus) {
    return;
  }
  elements.pushNotificationStatus.textContent = text;
  elements.pushNotificationStatus.dataset.tone = tone;
}

function setPushNotificationUnread(unread) {
  state.pushNotificationUnread = unread === true;
  if (elements.pushNotificationUnreadDot) {
    elements.pushNotificationUnreadDot.hidden = !state.pushNotificationUnread;
  }
  const button = elements.pushNotificationButton;
  if (button && !button.hidden) {
    const baseLabel = state.pushNotificationEnabled ? "알림 내역" : "알림 설정";
    const label = state.pushNotificationUnread ? `${baseLabel}, 새 알림 있음` : baseLabel;
    button.setAttribute("aria-label", label);
    button.title = label;
    if (elements.pushNotificationButtonLabel) {
      elements.pushNotificationButtonLabel.textContent = label;
    }
  }
}

function stopPushNotificationUnreadRefresh() {
  window.clearInterval(state.pushNotificationUnreadTimer);
  state.pushNotificationUnreadTimer = null;
}

function startPushNotificationUnreadRefresh() {
  stopPushNotificationUnreadRefresh();
  if (!state.watchlistId || !state.pushNotificationEnabled) {
    return;
  }
  state.pushNotificationUnreadTimer = window.setInterval(() => {
    void loadPushNotificationHistory({ silent: true, render: false });
  }, 60_000);
}

function updatePushNotificationButton(options = {}) {
  const button = elements.pushNotificationButton;
  if (!button) {
    return;
  }
  const hidden = options.hidden ?? !state.watchlistId;
  button.hidden = hidden;
  if (hidden) {
    setPushNotificationUnread(false);
    setPushNotificationStatus();
    updatePushNotificationDisableButton({ hidden: true });
    return;
  }
  const label = options.label || "알림 설정";
  const buttonText = options.buttonText || "알림 설정";
  button.disabled = options.disabled ?? false;
  button.dataset.active = String(options.active === true);
  button.setAttribute("aria-pressed", String(options.active === true));
  button.setAttribute("aria-label", label);
  button.title = options.title || label;
  if (elements.pushNotificationButtonText) {
    elements.pushNotificationButtonText.textContent = buttonText;
  }
  if (elements.pushNotificationButtonLabel) {
    elements.pushNotificationButtonLabel.textContent = label;
  }
  setPushNotificationUnread(state.pushNotificationUnread);
}

async function loadPushConfig() {
  if (state.pushConfig) {
    return state.pushConfig;
  }
  const response = await fetch("/push/config", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("push config failed");
  }
  state.pushConfig = await response.json();
  return state.pushConfig;
}

async function currentPushSubscription() {
  if (!webPushSupported()) {
    return null;
  }
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

async function savePushSubscription(shareId, subscription) {
  const writeToken = await ensureWriteToken(shareId);
  const conditions = normalizePushNotificationConditions(state.pushNotificationConditions);
  const response = await fetch(`/push/subscriptions/${encodeURIComponent(shareId)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Write-Token": writeToken,
    },
    body: JSON.stringify({ ...subscription.toJSON(), conditions }),
  });
  if (!response.ok) {
    throw new Error("push subscription save failed");
  }
  return response.json();
}

async function fetchPushSubscriptionStatus(shareId, endpoint) {
  const url = `/push/subscriptions/${encodeURIComponent(shareId)}/status?endpoint=${encodeURIComponent(endpoint)}`;
  const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) {
    throw new Error("push subscription status failed");
  }
  return response.json();
}

async function disablePushNotifications(shareId = state.watchlistId) {
  if (!shareId || !webPushSupported()) {
    return;
  }
  const subscription = await currentPushSubscription();
  if (!subscription) {
    return;
  }
  const writeToken = await ensureWriteToken(shareId);
  const response = await fetch(`/push/subscriptions/${encodeURIComponent(shareId)}`, {
    method: "DELETE",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-Write-Token": writeToken,
    },
    body: JSON.stringify({ endpoint: subscription.endpoint }),
  });
  if (!response.ok) {
    throw new Error("push subscription delete failed");
  }
  await subscription.unsubscribe();
}

async function refreshPushNotificationState(options = {}) {
  if (!elements.pushNotificationButton || !state.watchlistId) {
    updatePushNotificationButton({ hidden: true });
    return;
  }
  if (!webPushSupported()) {
    state.pushNotificationEnabled = false;
    writeCachedPushEnabled(false);
    stopPushNotificationUnreadRefresh();
    updatePushNotificationButton({ label: "알림 미지원", buttonText: "미지원", disabled: true });
    updatePushNotificationDisableButton({ hidden: true });
    setPushNotificationStatus("이 브라우저에서는 알림을 지원하지 않습니다.");
    return;
  }
  try {
    const config = await loadPushConfig();
    state.pushNotificationConditions = normalizePushNotificationConditions(state.pushNotificationConditions);
    if (!config.enabled || !config.public_key) {
      state.pushNotificationEnabled = false;
      writeCachedPushEnabled(false);
      stopPushNotificationUnreadRefresh();
      updatePushNotificationButton({ label: "알림 준비 중", buttonText: "준비중", disabled: false });
      updatePushNotificationDisableButton({ hidden: true });
      setPushNotificationStatus("알림 기능을 준비하고 있습니다.");
      return;
    }
    if (Notification.permission === "denied") {
      state.pushNotificationEnabled = false;
      writeCachedPushEnabled(false);
      stopPushNotificationUnreadRefresh();
      updatePushNotificationButton({ label: "알림 차단됨", buttonText: "권한 차단", disabled: false });
      updatePushNotificationDisableButton({ hidden: true });
      setPushNotificationStatus("브라우저 설정에서 알림 권한을 허용해주세요.", "error");
      return;
    }
    const subscription = await currentPushSubscription();
    if (subscription) {
      const status = await fetchPushSubscriptionStatus(state.watchlistId, subscription.endpoint).catch(() => null);
      state.pushNotificationEnabled = Boolean(status?.enabled ?? true);
      writeCachedPushEnabled(state.pushNotificationEnabled);
      state.pushNotificationConditions = normalizePushNotificationConditions(status?.conditions || state.pushNotificationConditions);
      updatePushNotificationButton({ label: "알림 내역", buttonText: "알림", active: true });
      updatePushNotificationDisableButton({ hidden: false });
      setPushNotificationStatus("급등락, 공시, 리포트만 바로 알려드려요.", "success");
      startPushNotificationUnreadRefresh();
      void loadPushNotificationHistory({ silent: true, render: false });
      if (options.syncServer) {
        await savePushSubscription(state.watchlistId, subscription);
      }
      return;
    }
    state.pushNotificationEnabled = false;
    writeCachedPushEnabled(false);
    stopPushNotificationUnreadRefresh();
    updatePushNotificationButton({ label: "알림 켜기", buttonText: "알림 켜기" });
    updatePushNotificationDisableButton({ hidden: true });
    setPushNotificationStatus("관심종목의 급등락, 공시, 리포트를 알려드려요.");
  } catch {
    state.pushNotificationEnabled = readCachedPushEnabled();
    if (state.pushNotificationEnabled) {
      updatePushNotificationButton({ label: "알림 내역", buttonText: "알림", active: true });
      startPushNotificationUnreadRefresh();
      return;
    }
    stopPushNotificationUnreadRefresh();
    updatePushNotificationButton({ label: "알림 다시 시도", buttonText: "재시도" });
    updatePushNotificationDisableButton({ hidden: true });
    setPushNotificationStatus("알림 상태를 확인하지 못했습니다.", "error");
  }
}

async function savePushNotificationSettings() {
  if (state.pushNotificationBusy || !state.watchlistId) {
    return;
  }
  const conditions = selectedPushNotificationConditions();
  if (!conditions.length) {
    state.pushNotificationConditions = [];
    updatePushNotificationSheet();
    return;
  }
  state.pushNotificationConditions = conditions;
  state.pushNotificationBusy = true;
  updatePushNotificationSheet();
  try {
    const config = await loadPushConfig();
    if (!config.enabled || !config.public_key) {
      throw new Error("push is not configured");
    }
    let subscription = await currentPushSubscription();
    if (!subscription) {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        await refreshPushNotificationState();
        updatePushNotificationSheet();
        return;
      }
      const registration = await navigator.serviceWorker.ready;
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: pushApplicationServerKey(config.public_key),
      });
    }
    const result = await savePushSubscription(state.watchlistId, subscription);
    state.pushNotificationEnabled = true;
    state.pushNotificationConditions = normalizePushNotificationConditions(result.conditions || conditions);
    closePushNotificationSheet();
    updatePushNotificationButton({ label: "알림 내역", buttonText: "알림", active: true });
    updatePushNotificationDisableButton({ hidden: false });
    setPushNotificationStatus(
      result.test_sent ? "알림 설정 완료. 테스트 알림을 보냈어요." : "알림 설정 완료. 중요한 변화만 알려드릴게요.",
      "success"
    );
  } catch {
    updatePushNotificationButton({ label: "알림 다시 시도", buttonText: "재시도" });
    setPushNotificationStatus("알림을 설정하지 못했습니다. 잠시 후 다시 시도해주세요.", "error");
    setPushNotificationSheetStatus("알림을 저장하지 못했습니다. 잠시 후 다시 시도해주세요.", "error");
  } finally {
    state.pushNotificationBusy = false;
    updatePushNotificationSheet();
  }
}

async function sendPushTestNotification() {
  if (state.pushNotificationBusy || !state.watchlistId) {
    return;
  }
  state.pushNotificationBusy = true;
  updatePushNotificationSheet();
  let statusText = "";
  let statusTone = "";
  try {
    const subscription = await currentPushSubscription();
    if (!subscription) {
      throw new Error("push subscription missing");
    }
    const writeToken = await ensureWriteToken(state.watchlistId);
    const response = await fetch(`/push/subscriptions/${encodeURIComponent(state.watchlistId)}/test`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Write-Token": writeToken,
      },
      body: JSON.stringify({ endpoint: subscription.endpoint }),
    });
    if (!response.ok) {
      throw new Error("push test failed");
    }
    statusText = "테스트 알림을 보냈습니다. 보이지 않으면 iPhone 설정의 비밀노트 알림 허용을 확인해주세요.";
    statusTone = "success";
  } catch {
    statusText = "테스트 알림을 보내지 못했습니다. 알림을 껐다가 다시 켜주세요.";
    statusTone = "error";
  } finally {
    state.pushNotificationBusy = false;
    updatePushNotificationSheet();
    setPushNotificationSheetStatus(statusText, statusTone);
  }
}

async function disablePushNotificationsFromUi() {
  if (state.pushNotificationBusy || !state.watchlistId) {
    return;
  }
  state.pushNotificationBusy = true;
  updatePushNotificationSheet();
  try {
    await disablePushNotifications(state.watchlistId);
    state.pushNotificationEnabled = false;
    closePushNotificationSheet();
    updatePushNotificationButton({ label: "알림 켜기", buttonText: "알림 켜기" });
    updatePushNotificationDisableButton({ hidden: true });
    setPushNotificationStatus("이 기기에서는 알림을 껐습니다.");
  } catch {
    setPushNotificationStatus("알림을 끄지 못했습니다. 잠시 후 다시 시도해주세요.", "error");
    setPushNotificationSheetStatus("알림을 끄지 못했습니다. 잠시 후 다시 시도해주세요.", "error");
  } finally {
    state.pushNotificationBusy = false;
    updatePushNotificationSheet();
  }
}

function pageEntryTtlMs(view) {
  const phase = koreaMarketPhase();
  const marketIsMoving = phase === "regular" || phase === "preopen";
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
    case "market-indices":
      return 0;
    case "chart":
      return 2 * PAGE_ENTRY_MINUTE_MS;
    case "chart-history":
      return 5 * PAGE_ENTRY_MINUTE_MS;
    case "notifications":
      return 15_000;
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

function canonicalAppView(requested) {
  if (requested === "trend-impact") {
    state.activeTrendTab = "impact";
  } else if (requested === "trend-past") {
    state.activeTrendTab = "events";
    state.showPastEvents = true;
  } else if (requested === "trend") {
    state.activeTrendTab = state.activeTrendTab || "live";
  } else if (requested === "recommend-history") {
    state.portfolioTab = "tracking";
  } else if (requested === "watchlist") {
    state.portfolioTab = "watchlist";
  }
  return requested === "stock" ? "stock" : (LEGACY_VIEW_MAP[requested] || "home");
}

function setWatchlistContentTab(tabName, options = {}) {
  const active = tabName === "news" ? "news" : "strategy";
  state.watchlistContentTab = active;
  for (const tab of elements.watchlistContentTabs) {
    const selected = tab.dataset.watchContentTab === active;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  }
  elements.watchlistStrategyPanel.hidden = active !== "strategy";
  elements.watchlistNewsPanel.hidden = active !== "news";
  if (options.load === false || state.view !== "portfolio" || state.portfolioTab !== "watchlist") {
    return active;
  }
  if (active === "news") {
    closeWatchlistQuoteStreams();
    launchBriefPageLoading("관심종목 뉴스를 불러오는 중", () => loadTrendWatchlistNews(pageEntryRefreshOptions("watchlist", "news")));
  } else {
    launchBriefPageLoading(PAGE_LOADING_LABELS.watchlist, () => loadWatchlist(pageEntryRefreshOptions("watchlist", "strategy")));
  }
  return active;
}

function setPortfolioTab(tabName, options = {}) {
  const active = tabName === "tracking" ? "tracking" : "watchlist";
  state.portfolioTab = active;
  for (const tab of elements.portfolioTabs) {
    const selected = tab.dataset.portfolioTab === active;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  }
  elements.portfolioWatchlistPanel.hidden = active !== "watchlist";
  elements.portfolioTrackingPanel.hidden = active !== "tracking";
  if (options.load === false || state.view !== "portfolio") {
    return active;
  }
  if (active === "tracking") {
    launchBriefPageLoading(PAGE_LOADING_LABELS["recommend-history"], () => loadRecommendationHistory(pageEntryRefreshOptions("recommend-history")));
  } else {
    setWatchlistContentTab(state.watchlistContentTab, { load: true });
  }
  return active;
}

function setView(requestedViewName) {
  const view = canonicalAppView(requestedViewName);
  if (state.view !== view) {
    clearPageLoading();
  }
  state.view = view;
  document.body.dataset.view = view;
  setFlowLoading(false);
  hideSuggestions();
  if (view !== "stock") {
    closeQuoteStream();
  }
  if (!(view === "portfolio" && state.portfolioTab === "watchlist")) {
    closeWatchlistQuoteStreams();
  }
  if (view !== "movers") {
    closeMarketQuoteStreams();
  }
  if (!["search", "portfolio"].includes(view)) {
    closeRecommendationQuoteStreams();
  }
  if (view !== "home") {
    stopHomeMarketSignalTicker();
    stopHomeMarketIndexRefresh();
  }
  if (!US_SECTOR_STREAM_VIEWS.has(view)) {
    closeUsSectorStream();
  }
  elements.stockView.hidden = view !== "stock";
  elements.notificationsView.hidden = view !== "notifications";
  elements.homeView.hidden = view !== "home";
  elements.searchView.hidden = view !== "search";
  elements.recommendDetailPage.hidden = view !== "recommend-detail";
  elements.portfolioView.hidden = view !== "portfolio";
  elements.marketView.hidden = view !== "movers";
  elements.aiSignalsView.hidden = view !== "ai-signals";
  elements.trendView.hidden = false;
  elements.watchlistView.hidden = false;
  elements.recommendView.hidden = false;
  elements.recommendHistoryView.hidden = false;
  elements.chartView.hidden = view !== "chart";
  elements.chartHistoryView.hidden = view !== "chart-history";
  const activeView = view === "chart-history" ? "chart" : ["movers", "ai-signals"].includes(view) ? "home" : view === "recommend-detail" ? "search" : view;
  for (const item of elements.appNavItems) {
    const active = item.dataset.appView === activeView;
    item.classList.toggle("active", active);
    if (active) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  }
  if (view === "notifications") {
    history.replaceState(null, "", "/dashboard?view=notifications");
    hydratePushNotificationHistory();
    renderPushNotificationHistory(state.pushNotificationHistory.length ? {} : { loading: true });
    void loadPushNotificationHistory();
  } else if (view === "home") {
    history.replaceState(null, "", "/dashboard?view=home");
    const activeTab = state.activeTrendTab || "live";
    void loadHomeAiSignals(pageEntryRefreshOptions("watchlist", "home-ai-signals"));
    void loadHomeSurgeRankings(pageEntryRefreshOptions("market", "home"));
    void loadHomeMarketImpact({ force: false, ttlMs: PAGE_ENTRY_MINUTE_MS });
    void refreshUsSectorMoves({ force: false, ttlMs: PAGE_ENTRY_MINUTE_MS });
    connectUsSectorStream();
    launchBriefPageLoading(
      PAGE_LOADING_LABELS.trend,
      () => loadHomeMarketIndices(pageEntryRefreshOptions("market-indices")),
      900,
    );
    window.setTimeout(() => {
      if (state.view !== "home") return;
      void loadTrends(activeTab === "impact" ? "live" : activeTab, pageEntryRefreshOptions("trend", activeTab));
      if (activeTab === "impact") {
        void loadMarketImpactAnalysis(pageEntryRefreshOptions("trend-impact"));
      }
    }, 80);
  } else if (view === "search") {
    history.replaceState(null, "", "/dashboard?view=search");
    const entryOptions = pageEntryRefreshOptions("recommend");
    if (!state.recommendationLoading) {
      launchBriefPageLoading(
        PAGE_LOADING_LABELS.recommend,
        () => loadRecommendations({ auto: true, ...entryOptions, recompute: false }),
      );
    }
    connectUsSectorStream();
  } else if (view === "recommend-detail") {
    const code = state.currentRecommendationDetailItem?.code || new URLSearchParams(window.location.search).get("code") || "";
    history.replaceState(null, "", `/dashboard?view=recommend-detail${code ? `&code=${encodeURIComponent(code)}` : ""}`);
    window.scrollTo(0, 0);
    launchBriefPageLoading("AI 추천 설명을 불러오는 중", () => loadRecommendationDetail(code));
  } else if (view === "movers") {
    history.replaceState(null, "", "/dashboard?view=movers");
    const market = currentMarketFilter();
    launchBriefPageLoading(PAGE_LOADING_LABELS.market, () => loadMarketRankings({
      force: false,
      ttlMs: pageEntryTtlMs("market"),
      market,
      limit: 30,
    }));
  } else if (view === "ai-signals") {
    history.replaceState(null, "", "/dashboard?view=ai-signals");
    launchBriefPageLoading("AI 매매신호를 불러오는 중", () => loadAiSignalsPage(pageEntryRefreshOptions("watchlist", "ai-signals")));
  } else if (view === "portfolio") {
    history.replaceState(null, "", "/dashboard?view=portfolio");
    setPortfolioTab(state.portfolioTab, { load: true });
  } else if (view === "chart") {
    history.replaceState(null, "", "/dashboard?view=chart");
    clearWatchChartLoadingOverlay();
    if (!state.watchChartResults.length) {
      elements.chartStartGuide?.removeAttribute("hidden");
      elements.watchChartList.innerHTML = "";
    }
  } else if (view === "chart-history") {
    history.replaceState(null, "", "/dashboard?view=chart-history");
    renderChartSnapshots();
  }
}

function renderEvents(listNode, items) {
  if (!listNode) {
    return;
  }
  listNode.innerHTML = "";
  if (!items || items.length === 0) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "-";
    listNode.appendChild(empty);
    return;
  }
  const seenTitles = new Set();
  let appended = 0;
  for (const item of items) {
    const title = String(item.title || "").trim();
    if (!title || seenTitles.has(title)) {
      continue;
    }
    seenTitles.add(title);
    const li = document.createElement("li");
    const anchor = document.createElement(item.url ? "a" : "span");
    anchor.textContent = title;
    if (item.url) {
      anchor.href = item.url;
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
    }
    const time = document.createElement("time");
    time.textContent = formatDate(item.published_at);
    li.append(anchor, time);
    listNode.appendChild(li);
    appended += 1;
  }
  if (appended === 0) {
    const empty = document.createElement("li");
    empty.className = "muted";
    empty.textContent = "-";
    listNode.appendChild(empty);
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

function setMarketLeaderboardMode(enabled) {
  elements.rankingBody?.classList.toggle("market-leaderboard-list", enabled);
}

function renderRankingMessage(text) {
  elements.rankingBody.innerHTML = "";
  const message = document.createElement("p");
  message.className = "muted ranking-message-cell";
  message.textContent = text;
  elements.rankingBody.appendChild(message);
}

function createMarketLeaderboardCard(item) {
  const card = document.createElement("article");
  card.className = "market-leaderboard-card";
  card.dataset.code = item.code;

  const main = document.createElement("a");
  main.className = "market-leaderboard-main";
  main.href = viewStockUrl(item.name);

  const rank = document.createElement("span");
  rank.className = "market-rank-badge";
  rank.textContent = String(item.rank || "-");

  const name = document.createElement("span");
  name.className = "market-leaderboard-name";

  const strong = document.createElement("strong");
  strong.textContent = item.name;

  const meta = document.createElement("span");
  meta.textContent = `${item.code} · ${item.market}`;
  name.append(strong, meta);

  const price = document.createElement("strong");
  price.className = "market-leaderboard-price";
  price.textContent = formatNumber(item.price);

  const change = document.createElement("strong");
  change.className = "market-leaderboard-change";
  change.textContent = formatPercent(item.change_rate);
  setTone(change, item.change_rate);

  const quoteBlock = document.createElement("span");
  quoteBlock.className = "market-leaderboard-quote-block";
  quoteBlock.append(price, change);

  main.append(rank, createStockListLogo(item.code), name, quoteBlock);

  const strip = document.createElement("dl");
  strip.className = "market-leaderboard-strip";
  strip.append(
    createMarketLeaderboardMetric("거래대금", formatMoney(item.trading_value)),
    createMarketLeaderboardMetric("1개월", formatPercent(item.one_month_return), item.one_month_return),
    createMarketLeaderboardMetric("3개월", formatPercent(item.three_month_return), item.three_month_return)
  );

  card.append(main, strip);
  return card;
}

function createMarketLeaderboardMetric(label, value, toneValue = null) {
  const item = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value;
  if (toneValue !== null && toneValue !== undefined) {
    setTone(description, toneValue);
  }
  item.append(term, description);
  return item;
}

function renderMarketSurgeLeaderboard(options = {}) {
  elements.rankingBody.innerHTML = "";
  const shell = document.createElement("section");
  shell.className = "market-leaderboard-shell";

  const board = document.createElement("div");
  board.className = "market-leaderboard";
  const visibleItems = state.marketLeaderboardItems.slice(0, state.marketLeaderboardVisibleCount);
  for (const item of visibleItems) {
    board.appendChild(createMarketLeaderboardCard(item));
  }
  shell.appendChild(board);
  elements.rankingBody.appendChild(shell);
}

async function hydrateMarketPeriodReturns(items) {
  const codes = items
    .filter((item) => item.one_month_return == null || item.three_month_return == null)
    .map((item) => item.code)
    .filter(Boolean);
  if (!codes.length) {
    return;
  }
  const payload = await fetchJsonCached(
    `/market/rankings/returns?codes=${encodeURIComponent(codes.join(","))}`,
    { force: true, ttlMs: 0, timeoutMs: 20_000 }
  );
  const returnsByCode = new Map((payload.items || []).map((item) => [item.code, item]));
  state.marketLeaderboardItems = state.marketLeaderboardItems.map((item) => {
    const periodReturns = returnsByCode.get(item.code);
    return periodReturns ? { ...item, ...periodReturns } : item;
  });
}

function startMarketSurgeLeaderboard(payload) {
  closeMarketQuoteStreams();
  state.marketLeaderboardVisibleCount = 30;
  state.marketLeaderboardItems = (payload.items || []).map((item, index) => ({
    ...item,
    rank: index + 1,
    metric_value: item.metric_value ?? item.change_rate,
  }));
  state.marketLeaderboardAsOf = payload.as_of || "";
  state.marketLeaderboardTradeDate = state.marketLeaderboardItems.find((item) => item.trade_date)?.trade_date || "";
  sortMarketLeaderboardItems();
  renderMarketSurgeLeaderboard();
  for (const item of state.marketLeaderboardItems.slice(0, 20)) {
    connectMarketQuoteStream(item.code);
  }
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
    return { label: "업종 대비 고PER", tone: "negative" };
  }
  if (per !== null && industryPer !== null && industryPer > 0 && per <= industryPer * 0.8) {
    return { label: "업종 대비 저PER", tone: "positive" };
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
  const fx = toNumber(macro.fx_usdkrw);
  const commodity = toNumber(macro.commodity);
  const exports = toNumber(macro.exports);
  const positives = [];
  const risks = [];

  if (rate !== null) {
    if (rate <= -20) risks.push("금리 부담");
    if (rate >= 20) positives.push("금리 우호");
  }
  if (fx !== null) {
    if (fx >= 20) positives.push("환율 우호");
    if (fx <= -20) risks.push("환율 부담");
  }
  if (commodity !== null) {
    if (commodity >= 20) positives.push("원자재 우호");
    if (commodity <= -20) risks.push("원자재 부담");
  }
  if (exports !== null) {
    if (exports >= 20) positives.push("수출 우호");
    if (exports <= -20) risks.push("수출 둔화 민감");
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

function renderRankings(payload) {
  const category = payload.category;
  elements.rankingBody.innerHTML = "";
  setMarketLeaderboardMode(category === "surge");
  if (category === "surge") {
    if (elements.marketMeta) {
      elements.marketMeta.textContent = `${marketRankingBasisLabel(payload, { includeMarket: false })} · 상승 ${formatNumber(payload.matching_count ?? payload.items?.length ?? 0)}개`;
    }
    if (!payload.items || payload.items.length === 0) {
      closeMarketQuoteStreams();
      renderRankingMessage("데이터 없음");
      return;
    }
    startMarketSurgeLeaderboard(payload);
    return;
  }
  closeMarketQuoteStreams();
  if (!payload.items || payload.items.length === 0) {
    renderRankingMessage("데이터 없음");
    return;
  }
  for (const item of payload.items) {
    const row = document.createElement("tr");
    const metric = rankingMetricLabel(category, item);
    row.innerHTML = `
      <td data-label="순위">${item.rank}</td>
      <td data-label="종목">
        <a class="rank-name" href="${viewStockUrl(item.name)}">
          <strong>${item.name}</strong>
          <span>${item.code} · ${item.market}</span>
        </a>
      </td>
      <td data-label="현재가">${formatNumber(item.price)}</td>
      <td data-label="핵심값">${metric}</td>
      <td data-label="1개월" class="${Number(item.one_month_return) > 0 ? "positive" : "negative"}">${formatPercent(item.one_month_return)}</td>
      <td data-label="3개월" class="${Number(item.three_month_return) > 0 ? "positive" : "negative"}">${formatPercent(item.three_month_return)}</td>
      <td data-label="거래대금">${formatMoney(item.trading_value)}</td>
    `;
    elements.rankingBody.appendChild(row);
  }
}

function marketRankingBasisLabel(payload = {}, options = {}) {
  const firstTradeDate = (payload.items || []).find((item) => item.trade_date)?.trade_date;
  const marketLabel = payload.market === "KOSDAQ" ? "KOSDAQ" : payload.market === "KOSPI" ? "KOSPI" : "전체 시장";
  const basisValue = payload.source === "naver_market_rise"
    ? payload.as_of || firstTradeDate
    : firstTradeDate || payload.as_of;
  const formattedBasis = formatDataBasis(basisValue, "기준 정보 확인 중");
  const basis = payload.source === "naver_market_rise"
    ? formattedBasis
    : formattedBasis.replace(/ 기준$/, " 장 마감 기준");
  return options.includeMarket === false ? basis : `${basis} · ${marketLabel}`;
}

function aiSignalDateValue(item = {}) {
  const current = item.current || {};
  const transition = current.lifecycle?.latest_transition || {};
  if (item.signal_date) {
    return item.signal_date;
  }
  if (current.action === "exited") {
    return transition.transition_date || current.partial_exit_date || "";
  }
  return current.entry_date || "";
}

function isRecentAiSignal(item = {}) {
  const matchedDate = String(aiSignalDateValue(item) || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!matchedDate) {
    return false;
  }
  const signalDate = new Date(`${matchedDate[1]}-${matchedDate[2]}-${matchedDate[3]}T00:00:00`);
  if (Number.isNaN(signalDate.getTime())) {
    return false;
  }
  const cutoff = new Date();
  cutoff.setHours(0, 0, 0, 0);
  cutoff.setDate(cutoff.getDate() - AI_SIGNAL_LOOKBACK_DAYS);
  return signalDate >= cutoff;
}

function homeAiSignalView(item = {}) {
  if (!isRecentAiSignal(item)) {
    return null;
  }
  const current = item.current || {};
  const action = current.action || "unavailable";
  const signalDate = aiSignalDateValue(item);
  if (action === "entered") {
    return { key: "recent-buy", label: "최근 매수", tone: "buy", signalDate };
  }
  if (current.position_open) {
    return { key: "holding", label: "보유 중", tone: "hold", signalDate };
  }
  if (action === "exited") {
    return { key: "recent-sell", label: "최근 매도", tone: "sell", signalDate };
  }
  return null;
}

function aiSignalSortValue(item) {
  const view = homeAiSignalView(item);
  const stageOrder = { "recent-buy": 0, holding: 1, "recent-sell": 2 };
  const timestamp = Date.parse(view?.signalDate || "") || 0;
  return [(stageOrder[view?.key] ?? 9), -timestamp];
}

function normalizedAiSignalItems(items = []) {
  return items
    .filter((item) => homeAiSignalView(item))
    .sort((left, right) => {
      const leftSort = aiSignalSortValue(left);
      const rightSort = aiSignalSortValue(right);
      return leftSort[0] - rightSort[0] || leftSort[1] - rightSort[1];
    });
}

function homeMarketVolatilitySentence(items = state.homeMarketIndexItems) {
  const domestic = (Array.isArray(items) ? items : [])
    .filter((item) => ["KOSPI", "KOSDAQ"].includes(String(item?.code || "").toUpperCase()))
    .map((item) => ({
      label: item.label || item.code,
      rate: toNumber(item.change_rate),
    }))
    .filter((item) => item.rate !== null);
  if (!domestic.length) {
    return "시장 변동성 데이터를 확인하고 있습니다.";
  }
  const strongest = [...domestic].sort((left, right) => Math.abs(right.rate) - Math.abs(left.rate))[0];
  const rates = domestic.map((item) => item.rate);
  const maximumMove = Math.max(...rates.map((rate) => Math.abs(rate)));
  const hasMixedDirection = rates.some((rate) => rate > 0) && rates.some((rate) => rate < 0);
  const allPositive = rates.every((rate) => rate > 0);
  const allNegative = rates.every((rate) => rate < 0);
  if (maximumMove >= 2) {
    return `${strongest.label} ${formatPercent(strongest.rate)}로 변동성이 큰 구간이어서 장중 급등락에 유의해야 합니다.`;
  }
  if (hasMixedDirection) {
    return "코스피와 코스닥 흐름이 엇갈려 종목별 변동성 차이를 확인해야 합니다.";
  }
  if (allPositive && maximumMove >= 0.7) {
    return "코스피와 코스닥이 함께 강세지만 단기 추격보다 종목별 수급 확인이 필요합니다.";
  }
  if (allNegative && maximumMove >= 0.7) {
    return "코스피와 코스닥이 함께 약세여서 추가 하락과 수급 이탈에 유의해야 합니다.";
  }
  return "국내 지수 변동은 제한적이지만 종목별 움직임 차이를 확인할 구간입니다.";
}

function homeAttentionSignal(items = []) {
  const normalized = normalizedAiSignalItems(items);
  const score = (item) => toNumber(item?.current?.score) ?? -Infinity;
  const pickHighest = (candidates) => [...candidates].sort((left, right) => score(right) - score(left))[0] || null;
  const holding = normalized.filter((item) => homeAiSignalView(item)?.key === "holding");
  const recentBuy = normalized.filter((item) => homeAiSignalView(item)?.key === "recent-buy");
  const recentSell = normalized.filter((item) => homeAiSignalView(item)?.key === "recent-sell");
  return pickHighest(holding) || pickHighest(recentBuy) || recentSell[0] || null;
}

function homeAttentionSentence(items = []) {
  const item = homeAttentionSignal(items);
  if (!item) {
    return readWatchlist().length
      ? "관심종목 분석을 불러오는 중이므로 현재가와 수급 변화를 먼저 확인하세요."
      : "관심종목을 추가하면 우선 확인할 종목과 이유를 알려드립니다.";
  }
  const name = item.name || item.code || "관심종목";
  const view = homeAiSignalView(item);
  if (view?.key === "holding") {
    return `${name} 유의: 보유 신호가 유지 중이므로 변동성 확대 시 매도 기준 도달 여부를 확인하세요.`;
  }
  if (view?.key === "recent-buy") {
    return `${name} 유의: 최근 매수 신호 이후 변동성이 커질 수 있어 손실 제한 기준을 확인하세요.`;
  }
  return `${name} 유의: 최근 매도 신호가 있어 가격이 안정되기 전 재진입을 서두르지 마세요.`;
}

function compactMarketHeadline(value, maxLength = 42) {
  const text = String(value || "")
    .replace(/^\[[^\]]+\]\s*/, "")
    .replace(/\s+/g, " ")
    .trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(1, maxLength - 1)).trim()}…`;
}

function homeTrendTimeline(payload = state.homeTrendContext || {}) {
  const entries = [
    ...(Array.isArray(payload.timeline) ? payload.timeline : []),
    ...(Array.isArray(payload.events) ? payload.events.flatMap((event) => event.timeline || []) : []),
  ];
  const seen = new Set();
  return entries.filter((item) => {
    const key = item.id || `${item.published_at || ""}:${item.title || ""}`;
    if (!item?.title || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function majorMarketIssueContext(payload = state.homeTrendContext || {}, now = Date.now()) {
  const majorIssuePattern = /전쟁|공습|미사일|침공|무력\s*충돌|군사\s*충돌|교전|휴전\s*파기|테러|핵실험|비상계엄|대규모\s*제재|지진|쓰나미|태풍|허리케인|홍수|산불|대형\s*재난|비상사태|무역전쟁|수출\s*규제|금수/;
  const candidates = homeTrendTimeline(payload)
    .map((item) => ({ ...item, timestamp: Date.parse(item.published_at || "") }))
    .filter((item) => Number.isFinite(item.timestamp)
      && item.timestamp <= now + 10 * 60 * 1000
      && item.timestamp >= now - 36 * 60 * 60 * 1000
      && majorIssuePattern.test(item.title));
  if (!candidates.length) {
    return null;
  }
  const item = candidates.sort((left, right) => right.timestamp - left.timestamp)[0];
  const title = compactMarketHeadline(item.title);
  const isWar = /전쟁|공습|미사일|침공|충돌|교전|테러|핵실험|제재/.test(item.title);
  const isDisaster = /지진|쓰나미|태풍|허리케인|홍수|산불|재난|비상사태/.test(item.title);
  const themes = isWar
    ? ["방산", "정유", "항공", "해운"]
    : isDisaster
      ? ["보험", "운송", "건설"]
      : ["자동차", "반도체", "수출"];
  return {
    kind: "major-issue",
    title,
    asOf: item.published_at,
    themes,
    leaderStocks: item.leader_stocks || [],
    sentence: `${title} 소식이 최우선 변수입니다. 관련 자산과 업종의 급격한 방향 전환에 유의하세요.`,
    watchReason: "대형 이슈 영향권이므로 관련 속보와 장중 수급 변화를 함께 확인하세요.",
  };
}

function upcomingMarketEventContext(payload = state.homeTrendContext || {}, now = Date.now()) {
  const importanceScore = { "매우 중요": 3, 중요: 2, 보통: 1 };
  const candidates = (Array.isArray(payload.events) ? payload.events : [])
    .map((event) => ({ ...event, timestamp: Date.parse(event.starts_at || "") }))
    .filter((event) => Number.isFinite(event.timestamp)
      && event.timestamp >= now - 15 * 60 * 1000
      && event.timestamp <= now + 36 * 60 * 60 * 1000)
    .sort((left, right) => {
      const importanceGap = (importanceScore[right.importance] || 0) - (importanceScore[left.importance] || 0);
      return importanceGap || left.timestamp - right.timestamp;
    });
  if (!candidates.length) {
    return null;
  }
  const event = candidates[0];
  const eventDate = new Date(event.timestamp);
  const today = new Date(now);
  const sameDay = eventDate.getFullYear() === today.getFullYear()
    && eventDate.getMonth() === today.getMonth()
    && eventDate.getDate() === today.getDate();
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  const isTomorrow = eventDate.getFullYear() === tomorrow.getFullYear()
    && eventDate.getMonth() === tomorrow.getMonth()
    && eventDate.getDate() === tomorrow.getDate();
  const timeLabel = eventDate.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });
  const dayLabel = sameDay ? "오늘" : isTomorrow ? "내일" : `${eventDate.getMonth() + 1}월 ${eventDate.getDate()}일`;
  const focus = [...(event.affected_variables || []), ...(event.affected_sectors || [])].slice(0, 3).join("·");
  return {
    kind: "event",
    title: event.title,
    asOf: event.starts_at,
    timestamp: event.timestamp,
    importance: event.importance,
    themes: event.affected_sectors || [],
    leaderStocks: (event.timeline || []).flatMap((item) => item.leader_stocks || []),
    sentence: `${dayLabel} ${timeLabel} ${event.title} 발표가 예정돼 ${focus || "국내증시"} 변동성이 커질 수 있습니다.`,
    watchReason: `${event.title} 민감 종목입니다. 발표 전후 가격보다 거래대금과 외국인 수급 변화를 먼저 확인하세요.`,
  };
}

function usSectorMarketContext(payload = state.usSectorMoves || {}) {
  if (!["premarket", "regular", "afterhours"].includes(payload.market_session)) {
    return null;
  }
  const broadSymbols = new Set(["QQQ", "SPY", "IWM"]);
  const candidates = (payload.items || [])
    .filter((item) => !broadSymbols.has(item.symbol))
    .map((item) => ({ ...item, rate: toNumber(item.change_rate) }))
    .filter((item) => item.rate !== null)
    .sort((left, right) => Math.abs(right.rate) - Math.abs(left.rate));
  if (!candidates.length) {
    return null;
  }
  const item = candidates[0];
  const direction = item.rate >= 2.5 ? "급등" : item.rate > 0 ? "강세" : item.rate <= -2.5 ? "급락" : "약세";
  return {
    kind: "us-sector",
    title: `${item.label} ${direction}`,
    asOf: payload.as_of,
    rate: item.rate,
    sector: item.sector || item.label,
    themes: [item.sector, item.label].filter(Boolean),
    leaderStocks: [],
    sentence: `${usSectorSessionLabel(payload)} ${item.label} 섹터가 ${formatPercent(item.rate)}로 ${direction}입니다. 국내 연관 종목의 장중 수급 변화를 확인하세요.`,
    watchReason: `${item.label} 흐름과 직접 연결됩니다. 현재가보다 거래대금과 외국인 수급 변화를 먼저 확인하세요.`,
  };
}

function marketImpactHomeContext(payload = state.homeMarketImpact || {}) {
  const factors = Array.isArray(payload.factors) ? payload.factors : [];
  if (!factors.length) {
    return null;
  }
  const factor = [...factors]
    .map((item) => ({
      ...item,
      weight: toNumber(item.percent) ?? 0,
      confidence: toNumber(item.confidence) ?? 0,
    }))
    .sort((left, right) => (right.weight * Math.max(right.confidence, 1)) - (left.weight * Math.max(left.confidence, 1)))[0];
  const label = String(factor?.label || factor?.name || "시장 변수").trim();
  const direction = String(factor?.direction || "변동").trim();
  const interpretation = String(factor?.interpretation || "").trim();
  const themes = Array.isArray(factor?.affected_sectors) ? factor.affected_sectors.filter(Boolean) : [];
  const leaderStocks = Array.isArray(factor?.leader_stocks) ? factor.leader_stocks.filter(Boolean) : [];
  return {
    kind: "market-impact",
    title: `${label} ${direction}`,
    asOf: payload.as_of,
    themes,
    leaderStocks,
    sentence: interpretation ? `${label} ${direction}: ${interpretation}` : `현재 핵심 변수는 ${label} ${direction}입니다.`,
    watchReason: themes.length
      ? `${themes.slice(0, 3).join("·")} 업종과 연결됩니다. 거래대금과 외국인 수급을 우선 확인하세요.`
      : "변동성 확대 가능성을 확인하세요. 거래대금과 외국인 수급을 우선 확인하세요.",
  };
}

function selectHomeMarketContext() {
  const majorIssue = majorMarketIssueContext();
  if (majorIssue) {
    return majorIssue;
  }
  const sector = usSectorMarketContext();
  const event = upcomingMarketEventContext();
  const marketImpact = marketImpactHomeContext();
  const eventDistance = event?.timestamp ? event.timestamp - Date.now() : Infinity;
  if (event && event.importance === "매우 중요" && eventDistance <= 4 * 60 * 60 * 1000) {
    return event;
  }
  if (sector && Math.abs(sector.rate) >= 1.5) {
    return sector;
  }
  if (marketImpact) {
    return marketImpact;
  }
  if (event) {
    return event;
  }
  return sector;
}

function normalizedHomeThemes(context = {}) {
  const aliases = {
    기술주: ["인터넷", "반도체"],
    성장주: ["인터넷", "반도체", "2차전지"],
    "자동차/소비": ["자동차"],
    에너지: ["정유"],
    "소재/화학": ["화학"],
    산업재: ["산업재", "방산"],
    "운송/해운": ["해운", "항공"],
  };
  const values = [];
  for (const theme of context.themes || []) {
    const normalized = String(theme || "").trim();
    if (!normalized) continue;
    values.push(normalized, ...(aliases[normalized] || []));
  }
  return [...new Set(values)];
}

function homeContextWatchItems(context = {}, signalItems = []) {
  const watchlist = readWatchlist();
  const pool = watchlist.length
    ? watchlist
    : normalizedAiSignalItems(signalItems).map((item) => ({ code: item.code, name: item.name, market: item.market }));
  const leaders = new Set(context.leaderStocks || []);
  const themes = normalizedHomeThemes(context);
  return pool.filter((item) => {
    if (leaders.has(item.name)) {
      return true;
    }
    const stockTheme = watchlistTheme(item);
    return stockTheme !== "기타" && themes.some((theme) => theme.includes(stockTheme) || stockTheme.includes(theme));
  }).slice(0, 2);
}

function homeContextAttentionSentence(context, signalItems = []) {
  if (!context) {
    return homeAttentionSentence(signalItems);
  }
  const matched = homeContextWatchItems(context, signalItems);
  if (!matched.length) {
    return homeAttentionSentence(signalItems);
  }
  return `${matched.map((item) => item.name).join("·")} 유의: ${context.watchReason}`;
}

function latestHomeAiResponseAsOf(asOf = "") {
  const candidates = [
    asOf,
    state.homeAiSignalsAsOf,
    state.homeTrendContext?.as_of,
    state.homeMarketImpact?.as_of,
    state.usSectorMoves?.as_of,
    ...homeTrendTimeline().map((item) => item.published_at),
    ...state.homeMarketIndexItems.flatMap((item) => [item?.updated_at, item?.as_of]),
  ].map((value) => String(value || "")).filter(Boolean);
  return candidates.sort((left, right) => (Date.parse(left) || 0) - (Date.parse(right) || 0)).at(-1) || "";
}

function renderHomeAiResponse(items = state.aiSignalItems, asOf = "") {
  if (!elements.homeAiResponseTitle || !elements.homeAiResponseSummary) {
    return;
  }
  const context = selectHomeMarketContext();
  elements.homeAiResponseTitle.textContent = context?.sentence || homeMarketVolatilitySentence();
  elements.homeAiResponseSummary.textContent = homeContextAttentionSentence(context, items);
  if (elements.homeAiResponseAsOf) {
    elements.homeAiResponseAsOf.textContent = formatDataBasis(context?.asOf || latestHomeAiResponseAsOf(asOf), "기준 정보 확인 중");
  }
}

function createHomeAiSignalRow(item, options = {}) {
  const view = homeAiSignalView(item);
  if (!view) {
    return null;
  }
  const row = document.createElement("a");
  row.className = `home-ai-signal-row is-${view.tone}`;
  row.href = viewStockUrl(item.name || item.code || "");
  row.dataset.code = item.code || "";

  const identity = el("span", "home-ai-signal-identity");
  identity.append(el("strong", "", item.name || item.code || "-"));
  if (options.detail) {
    identity.append(el("small", "", `${item.code || "-"} · ${item.market || "-"}`));
  }
  const status = el("span", "home-ai-signal-status");
  status.append(el("strong", "", view.label));
  if (options.detail && view.signalDate) {
    status.append(el("small", "", formatDataBasis(view.signalDate, "")));
  }
  row.append(identity, status);
  return row;
}

function renderHomeAiSignals(payload = {}) {
  if (!elements.homeAiSignalsList) {
    return;
  }
  const items = normalizedAiSignalItems(Array.isArray(payload.items) ? payload.items : []);
  state.aiSignalItems = items;
  state.homeAiSignalsAsOf = payload.updated_at || payload.as_of || "";
  renderHomeMarketSignalTicker({ items });
  renderHomeAiResponse(items, state.homeAiSignalsAsOf);
  elements.homeAiSignalsMeta.textContent = items.length ? `${formatNumber(items.length)}개 신호` : "새 신호 없음";
  elements.homeAiSignalsList.innerHTML = "";
  if (!items.length) {
    elements.homeAiSignalsList.append(el("p", "muted", "최근 매수·보유·매도 신호가 없습니다."));
    return;
  }
  items.slice(0, 5).forEach((item) => elements.homeAiSignalsList.appendChild(createHomeAiSignalRow(item)));
}

function renderPendingHomeAiSignals() {
  if (!elements.homeAiSignalsList) {
    return;
  }
  const watched = readWatchlist().slice(0, 5);
  showHomeMarketSignalLoading();
  if (elements.homeAiResponseTitle && elements.homeAiResponseSummary) {
    elements.homeAiResponseTitle.textContent = "시장 변동성 데이터를 확인하고 있습니다.";
    elements.homeAiResponseSummary.textContent = watched.length ? "우선 확인할 관심종목을 찾고 있습니다." : "관심종목을 추가하면 우선 확인할 종목과 이유를 알려드립니다.";
  }
  elements.homeAiSignalsMeta.textContent = watched.length ? `${formatNumber(watched.length)}개 종목 확인 중` : "관심종목 없음";
  elements.homeAiSignalsList.replaceChildren();
  if (!watched.length) {
    elements.homeAiSignalsList.append(el("p", "muted", "관심종목을 추가하면 매매신호를 확인할 수 있습니다."));
    return;
  }
  for (const item of watched) {
    const row = document.createElement("a");
    row.className = "home-ai-signal-row is-pending";
    row.href = viewStockUrl(item.name || item.code || "");
    const identity = el("span", "home-ai-signal-identity");
    identity.append(el("strong", "", item.name || item.code || "-"));
    const status = el("span", "home-ai-signal-status");
    status.append(el("strong", "", "확인 중"));
    row.append(identity, status);
    elements.homeAiSignalsList.append(row);
  }
}

function aiSignalStageCounts(items = state.aiSignalItems) {
  return items.reduce((counts, item) => {
    const view = homeAiSignalView(item);
    if (view) {
      counts[view.key] = (counts[view.key] || 0) + 1;
    }
    return counts;
  }, { "recent-buy": 0, holding: 0, "recent-sell": 0 });
}

function setAiSignalStage(stageName, options = {}) {
  const allowed = new Set(["recent-buy", "holding", "recent-sell"]);
  state.aiSignalStage = allowed.has(stageName) ? stageName : "recent-buy";
  for (const tab of elements.aiSignalStageTabs) {
    const selected = tab.dataset.aiSignalStage === state.aiSignalStage;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  }
  if (options.render !== false) {
    renderAiSignalsPage();
  }
}

function renderAiSignalsPage() {
  if (!elements.aiSignalsPageList) {
    return;
  }
  const items = normalizedAiSignalItems(state.aiSignalItems);
  const counts = aiSignalStageCounts(items);
  elements.aiSignalsMeta.textContent = items.length ? `${formatNumber(items.length)}개 신호` : "새 신호 없음";
  for (const tab of elements.aiSignalStageTabs) {
    const count = counts[tab.dataset.aiSignalStage] || 0;
    const countNode = tab.querySelector("span");
    if (countNode) {
      countNode.textContent = formatNumber(count);
    }
  }
  const visible = items.filter((item) => homeAiSignalView(item)?.key === state.aiSignalStage);
  elements.aiSignalsPageList.innerHTML = "";
  if (!visible.length) {
    const labels = { "recent-buy": "최근 매수", holding: "보유 중", "recent-sell": "최근 매도" };
    elements.aiSignalsPageList.append(el("p", "muted", `${labels[state.aiSignalStage]} 종목이 없습니다.`));
    return;
  }
  visible.forEach((item) => elements.aiSignalsPageList.appendChild(createHomeAiSignalRow(item, { detail: true })));
}

async function loadAiSignalsPage(options = {}) {
  if (!state.watchlistId) {
    state.aiSignalItems = [];
    renderAiSignalsPage();
    return;
  }
  elements.aiSignalsPageList.innerHTML = '<p class="muted">관심종목의 AI 매매신호를 불러오는 중입니다.</p>';
  try {
    const payload = await fetchJsonCached(
      `/watchlists/${encodeURIComponent(state.watchlistId)}/quant-signals`,
      { force: options.force === true, ttlMs: options.force ? 0 : (options.ttlMs ?? PAGE_ENTRY_MINUTE_MS) },
    );
    state.aiSignalItems = normalizedAiSignalItems(payload.items || []);
    const counts = aiSignalStageCounts(state.aiSignalItems);
    if (!counts[state.aiSignalStage]) {
      state.aiSignalStage = ["recent-buy", "holding", "recent-sell"].find((stage) => counts[stage]) || "recent-buy";
    }
    setAiSignalStage(state.aiSignalStage);
  } catch {
    elements.aiSignalsPageList.innerHTML = '<p class="muted">AI 매매신호를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.</p>';
  }
}

async function loadHomeAiSignals(options = {}) {
  if (!elements.homeAiSignalsList) {
    return;
  }
  if (!state.watchlistId) {
    renderHomeAiSignals({ items: [] });
    return;
  }
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? PAGE_ENTRY_MINUTE_MS;
  if (!elements.homeAiSignalsList.querySelector(".home-ai-signal-row")) {
    const cached = readCachedHomeAiSignals();
    if (cached) {
      renderHomeAiSignals(cached);
    } else {
      renderPendingHomeAiSignals();
    }
  }
  try {
    const payload = await fetchJsonCached(
      `/watchlists/${encodeURIComponent(state.watchlistId)}/quant-signals`,
      { force, ttlMs: force ? 0 : ttlMs },
    );
    writeCachedHomeAiSignals(payload);
    if (state.view === "home") {
      renderHomeAiSignals(payload);
    }
  } catch {
    if (state.view === "home" && !elements.homeAiSignalsList.querySelector(".home-ai-signal-row")) {
      elements.homeAiSignalsList.innerHTML = '<p class="muted">AI 매매신호를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.</p>';
    }
  }
}

function stopHomeMarketSignalTicker() {
  window.clearInterval(state.marketSignalTickerTimer);
  state.marketSignalTickerTimer = null;
}

function showHomeMarketSignalLoading() {
  if (!elements.homeMarketSignalWindow) {
    return;
  }
  elements.homeMarketSignalWindow.classList.add("is-loading");
  elements.homeMarketSignalWindow.setAttribute("aria-label", "보유종목 대응을 불러오는 중");
  elements.homeMarketSignalWindow.innerHTML = '<span class="home-market-signal-skeleton" aria-hidden="true"></span>';
}

function compactHoldingSignalSummary(item = {}) {
  const current = item.current || {};
  const action = String(current.action || "");
  if (action === "entered") {
    return "최근 매수 · 초기 위험선 확인";
  }
  if (["partial_exit_pending", "partially_exited"].includes(action)) {
    return "분할 매도 구간 · 남은 비중 위험선 확인";
  }
  if (action === "full_exit_pending") {
    return "매도 기준 접근 · 위험선 우선 확인";
  }
  const reason = String((current.reasons || []).find((value) => value && !String(value).startsWith("종합 신호")) || "").trim();
  if (reason.includes("추세가 유지") && reason.includes("기준은 미도달")) {
    return "추세 유지 · 분할매도·청산 기준 미도달";
  }
  if (reason) {
    return reason.replace(/ 판단으로 모델 포지션.*$/, "").replace(/함$/, "");
  }
  return String(current.next_confirmation || "보유 기준 유지 · 위험선 확인").trim();
}

function compactSignalDate(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[1]}-${match[2]}-${match[3]}` : "날짜 확인 중";
}

function homeMarketSignalItems(items = []) {
  return normalizedAiSignalItems(items)
    .map((item) => ({
      ...item,
      tickerSignal: (() => {
        const current = item.current || {};
        const transition = current.lifecycle?.latest_transition || {};
        const isSell = ["partial_exit_pending", "partially_exited", "full_exit_pending", "exited"].includes(current.action)
          || /매도|청산/.test(String(transition.label || ""));
        const signalDate = isSell
          ? current.partial_exit_date || transition.transition_date || current.as_of || item.as_of
          : current.entry_date || transition.transition_date || current.as_of || item.as_of;
        return {
          label: isSell ? "매도" : "매수",
          side: isSell ? "sell" : "buy",
          date: compactSignalDate(signalDate),
        };
      })(),
    }));
}

function homeHoldingSignalItems(items = []) {
  return homeMarketSignalItems(items);
}

function createHomeMarketSignalTickerRow(item) {
  const row = document.createElement("a");
  row.className = "home-market-signal-row";
  row.href = viewStockUrl(item.name || item.code || "");
  const signal = item.tickerSignal || { label: "매수", side: "buy", date: "날짜 확인 중" };
  row.dataset.side = signal.side;
  const name = el("strong", "home-market-signal-name", item.name || item.code || "-");
  const summary = el("span", "home-market-signal-action", `${signal.label} (${signal.date})`);
  row.append(name, summary);
  return row;
}

function showHomeMarketSignalTickerItem() {
  if (!elements.homeMarketSignalWindow) {
    return;
  }
  const items = state.marketSignalTickerItems;
  if (!items.length) {
    elements.homeMarketSignalWindow.classList.remove("is-loading");
    elements.homeMarketSignalWindow.setAttribute("aria-label", "현재 보유 신호 종목 없음");
    elements.homeMarketSignalWindow.innerHTML = '<p class="muted">현재 보유 신호 종목이 없습니다.</p>';
    return;
  }
  const itemIndex = state.marketSignalTickerIndex % items.length;
  elements.homeMarketSignalWindow.classList.remove("is-loading");
  elements.homeMarketSignalWindow.removeAttribute("aria-label");
  elements.homeMarketSignalWindow.replaceChildren(createHomeMarketSignalTickerRow(items[itemIndex]));
}

function startHomeMarketSignalTicker() {
  window.clearInterval(state.marketSignalTickerTimer);
  if (state.marketSignalTickerItems.length > 1) {
    state.marketSignalTickerTimer = window.setInterval(() => {
      if (state.view !== "home") {
        return;
      }
      state.marketSignalTickerIndex = (state.marketSignalTickerIndex + 1) % state.marketSignalTickerItems.length;
      showHomeMarketSignalTickerItem();
    }, 3000);
  }
}

function renderHomeMarketSignalTicker(payload = {}) {
  state.marketSignalTickerItems = homeMarketSignalItems(Array.isArray(payload.items) ? payload.items : []);
  state.marketSignalTickerIndex = 0;
  showHomeMarketSignalTickerItem();
  startHomeMarketSignalTicker();
}

function createHomeSurgeRow(item, index) {
  const row = document.createElement("a");
  row.className = "home-surge-row";
  row.href = viewStockUrl(item.name);
  row.dataset.code = item.code || "";

  const rank = el("span", "home-surge-rank", String(index + 1));
  const identity = el("span", "home-surge-identity");
  identity.append(
    createStockListLogo(item.code),
    createStockListCopy(item.name, item.code, item.market)
  );
  const quote = el("span", "home-surge-quote");
  quote.append(el("strong", "", formatNumber(item.price)), el("small", "", formatPercent(item.change_rate)));
  setTone(quote, item.change_rate);
  row.append(rank, identity, quote);
  return row;
}

function renderHomeSurgeRankings(payload = {}) {
  if (!elements.homeSurgeList) {
    return;
  }
  const items = (payload.items || []).slice(0, 5);
  elements.homeSurgeMeta.textContent = marketRankingBasisLabel(payload, { includeMarket: false });
  elements.homeSurgeList.innerHTML = "";
  if (!items.length) {
    elements.homeSurgeList.append(el("p", "muted", "상승 종목이 없습니다."));
    return;
  }
  items.forEach((item, index) => elements.homeSurgeList.appendChild(createHomeSurgeRow(item, index)));
}

async function loadHomeSurgeRankings(options = {}) {
  if (!elements.homeSurgeList) {
    return;
  }
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("market");
  if (!elements.homeSurgeList.querySelector(".home-surge-row")) {
    elements.homeSurgeList.innerHTML = '<p class="muted">급등 종목을 불러오는 중입니다.</p>';
  }
  try {
    const payload = await requestMarketRanking("surge", "ALL", { force, ttlMs, limit: 5 });
    if (state.view === "home") {
      renderHomeSurgeRankings(payload);
    }
  } catch {
    if (state.view === "home") {
      elements.homeSurgeList.innerHTML = '<p class="muted">급등 종목을 불러오지 못했습니다.</p>';
    }
  }
}

function currentMarketFilter() {
  return elements.marketTabs.find((tab) => tab.classList.contains("active"))?.dataset.marketFilter || "KOSPI";
}

function setMarketFilter(market) {
  const normalized = ["KOSPI", "KOSDAQ"].includes(market) ? market : "KOSPI";
  for (const tab of elements.marketTabs) {
    const active = tab.dataset.marketFilter === normalized;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  }
  return normalized;
}

function marketRankingKey(category, market, limit = 30) {
  return `${market}:surge:${limit}`;
}

function marketCategoryLabel(category) {
  return category === "surge" ? "급상승" : elements.rankTabs.find((tab) => tab.dataset.category === category)?.textContent?.trim() || category;
}

function requestMarketRanking(category, market, options = {}) {
  const normalizedCategory = "surge";
  const limit = Math.max(1, Math.min(3000, Number(options.limit) || 30));
  const key = marketRankingKey(normalizedCategory, market, limit);
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("market");
  const now = Date.now();
  const cached = state.marketRankingCache.get(key);
  if (!force && cached?.payload && now - (cached.savedAt || 0) <= ttlMs) {
    return Promise.resolve(cached.payload);
  }
  if (!force && cached?.promise) {
    return cached.promise;
  }
  const params = new URLSearchParams({
    category: normalizedCategory,
    limit: String(limit),
  });
  if (force) {
    params.set("refresh", "1");
  }
  if (market !== "ALL") {
    params.set("market", market);
  }
  const url = `/market/rankings?${params.toString()}`;
  const promise = fetchJsonCached(url, {
    force,
    ttlMs: force ? 0 : ttlMs,
    timeoutMs: 25_000,
  })
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
  const limit = Math.max(1, Math.min(30, Number(options.limit) || 30));
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("market");
  setMarketLeaderboardMode(category === "surge");
  const key = marketRankingKey(category, market, limit);
  const cached = state.marketRankingCache.get(key);
  if (!force && cached?.payload && Date.now() - (cached.savedAt || 0) <= ttlMs) {
    renderRankings(cached.payload);
    return;
  }
  closeMarketQuoteStreams();
  renderRankingMessage("불러오는 중");
  try {
    const payload = await requestMarketRanking(category, market, { force, ttlMs, limit });
    if (state.view === "movers" && state.rankingCategory === category && currentMarketFilter() === market) {
      renderRankings(payload);
    }
  } catch {
    if (state.view === "movers" && state.rankingCategory === category && currentMarketFilter() === market) {
      renderRankingMessage("데이터를 불러오지 못했습니다. 시장 탭을 다시 눌러주세요.");
    }
  }
}

function createWatchMetric(label, value, field = "", toneValue = null) {
  const item = document.createElement("div");
  const labelNode = document.createElement("span");
  labelNode.textContent = label;
  const valueNode = document.createElement("strong");
  valueNode.textContent = value;
  if (field) {
    valueNode.dataset.field = field;
  }
  if (toneValue !== null && toneValue !== undefined) {
    setTone(valueNode, toneValue);
  }
  item.append(labelNode, valueNode);
  return item;
}

function createWatchReportMetric(label, value, tone = "", field = "", toneValue = null) {
  const item = document.createElement("div");
  if (tone) {
    item.className = tone;
  }
  const valueNode = el("dd", "", value);
  if (field) {
    valueNode.dataset.field = field;
  }
  if (toneValue !== null && toneValue !== undefined) {
    setTone(valueNode, toneValue);
  }
  item.append(el("dt", "", label), valueNode);
  return item;
}

function createWatchContextItem(label, value, tone = "muted") {
  const item = document.createElement("div");
  item.className = tone;
  item.append(el("dt", "", label), el("dd", "", value));
  return item;
}

function watchFlowView(dashboard = {}) {
  const foreign = toNumber(dashboard.flows?.foreign_net_buy_20d);
  const institution = toNumber(dashboard.flows?.institution_net_buy_20d);
  if (foreign === null && institution === null) {
    return { label: "수급 확인 중", tone: "muted" };
  }
  if ((foreign ?? 0) < 0 && (institution ?? 0) < 0) {
    return { label: "외국인·기관 매도", tone: "negative" };
  }
  if ((foreign ?? 0) > 0 && (institution ?? 0) > 0) {
    return { label: "외국인·기관 매수", tone: "positive" };
  }
  if ((foreign ?? 0) > 0) {
    return { label: "외국인 매수 우위", tone: "positive" };
  }
  if ((institution ?? 0) > 0) {
    return { label: "기관 매수 우위", tone: "positive" };
  }
  return { label: "수급 엇갈림", tone: "muted" };
}

function watchNewsView(dashboard = {}) {
  const score = toNumber(dashboard.sentiment?.score);
  if (score === null) {
    return { label: "뉴스 확인 중", tone: "muted" };
  }
  return {
    label: newsLabel(dashboard.sentiment),
    tone: score >= 25 ? "positive" : score <= -25 ? "negative" : "muted",
  };
}

function watchStatusView(dashboard = {}) {
  const change = toNumber(dashboard.quote?.change_rate);
  const sentiment = toNumber(dashboard.sentiment?.score);
  const flow = watchFlowView(dashboard);
  const needsAttention = (change !== null && change <= -1)
    || (sentiment !== null && sentiment <= -25)
    || (flow.tone === "negative" && (change === null || change < 0));
  if (needsAttention) {
    return { id: "attention", label: "확인 필요", tone: "negative" };
  }
  const looksPositive = change !== null
    && change >= 1
    && sentiment !== null
    && sentiment >= -10
    && flow.tone !== "negative";
  if (looksPositive) {
    return { id: "positive", label: "흐름 양호", tone: "positive" };
  }
  return { id: "neutral", label: "변화 관찰", tone: "muted" };
}

function applyWatchlistFilter() {
  if (!elements.watchlistBody) {
    return;
  }
  const rows = Array.from(elements.watchlistBody.querySelectorAll("[data-watch-card]"));
  const filter = state.watchlistFilter || "all";
  let visibleCount = 0;
  for (const row of rows) {
    const visible = filter === "all" || row.dataset.watchStatus === filter;
    row.hidden = !visible;
    if (visible) {
      visibleCount += 1;
    }
  }
  for (const button of elements.watchlistFilterButtons || []) {
    const active = button.dataset.watchFilter === filter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  }
  elements.watchlistBody.classList.toggle("is-filter-empty", rows.length > 0 && visibleCount === 0);
}

function scheduleWatchlistStrategyRender() {
  window.clearTimeout(state.watchlistStrategyRenderTimer);
  state.watchlistStrategyRenderTimer = window.setTimeout(() => {
    state.watchlistStrategyRenderTimer = null;
    if (state.view === "portfolio" && state.portfolioTab === "watchlist") {
      renderWatchlistStrategy(state.watchlistResults, state.usSectorMoves, state.watchlistMarketContext);
    }
  }, 350);
}

async function loadUsSectorMoves(options = {}) {
  if (!options.force && state.usSectorMoves) {
    return state.usSectorMoves;
  }
  try {
    const force = options.force === true;
    const ttlMs = options.ttlMs ?? 5 * 60 * 1000;
    const url = force ? liveUrl("/market/us-sector-moves?refresh=1") : "/market/us-sector-moves";
    const payload = await fetchJsonCached(url, { force, ttlMs: force ? 0 : ttlMs });
    state.usSectorMoves = payload;
    return payload;
  } catch {
    return state.usSectorMoves || { items: [] };
  }
}

function clearUsSectorRefreshTimer() {
  if (state.usSectorRefreshTimer) {
    window.clearTimeout(state.usSectorRefreshTimer);
    state.usSectorRefreshTimer = null;
  }
}

function applyUsSectorMoves(payload) {
  if (!payload) {
    return;
  }
  state.usSectorMoves = payload;
  updateWatchPreOpenPoints(payload);
  renderWatchlistStrategy(state.watchlistResults, payload, state.watchlistMarketContext);
  updateRecommendationUsSectorCards(payload);
  if (state.view === "home") {
    renderHomeAiResponse();
  }
}

function closeUsSectorStream() {
  window.clearTimeout(state.usSectorReconnectTimer);
  state.usSectorReconnectTimer = null;
  if (state.usSectorSocket) {
    state.usSectorSocket.onclose = null;
    state.usSectorSocket.close();
    state.usSectorSocket = null;
  }
}

function connectUsSectorStream() {
  if (!("WebSocket" in window) || !US_SECTOR_STREAM_VIEWS.has(state.view)) {
    scheduleUsSectorRefresh(state.usSectorMoves);
    return;
  }
  if (state.usSectorSocket && state.usSectorSocket.readyState <= WebSocket.OPEN) {
    return;
  }
  clearUsSectorRefreshTimer();
  window.clearTimeout(state.usSectorReconnectTimer);
  const socket = new WebSocket(socketUrl("/ws/market/us-sector-moves"));
  state.usSectorSocket = socket;
  socket.onmessage = (event) => {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    if (payload?.type === "us_sector_moves") {
      applyUsSectorMoves(payload);
    }
  };
  socket.onclose = () => {
    if (state.usSectorSocket === socket) {
      state.usSectorSocket = null;
    }
    if (!US_SECTOR_STREAM_VIEWS.has(state.view)) {
      return;
    }
    state.usSectorReconnectTimer = window.setTimeout(connectUsSectorStream, 5000);
    scheduleUsSectorRefresh(state.usSectorMoves);
  };
  socket.onerror = () => {
    socket.close();
  };
}

function scheduleUsSectorRefresh(payload = state.usSectorMoves) {
  clearUsSectorRefreshTimer();
  if (!US_SECTOR_STREAM_VIEWS.has(state.view)) {
    return;
  }
  if (state.usSectorSocket && state.usSectorSocket.readyState <= WebSocket.OPEN) {
    return;
  }
  const intervalSeconds = Math.max(30, toNumber(payload?.refresh_interval_seconds) || (payload?.market_session === "regular" ? 60 : 300));
  state.usSectorRefreshTimer = window.setTimeout(() => {
    refreshUsSectorMoves({ force: true });
  }, intervalSeconds * 1000);
}

async function refreshUsSectorMoves(options = {}) {
  if (state.usSectorRefreshPromise) {
    return state.usSectorRefreshPromise;
  }
  state.usSectorRefreshing = true;
  state.usSectorRefreshPromise = (async () => {
    try {
      const payload = await loadUsSectorMoves({
        force: options.force === true,
        ttlMs: options.ttlMs,
      });
      applyUsSectorMoves(payload);
      scheduleUsSectorRefresh(payload);
      return payload;
    } finally {
      state.usSectorRefreshing = false;
      state.usSectorRefreshPromise = null;
    }
  })();
  return state.usSectorRefreshPromise;
}

function usSectorMoveMap(usSectorMoves = state.usSectorMoves) {
  return new Map((usSectorMoves?.items || []).map((item) => [item.symbol, item]));
}

function relatedUsSectorSymbols(item = {}, dashboard = {}) {
  const text = `${item.name || ""} ${dashboard.name || ""} ${item.code || dashboard.code || ""}`;
  const symbols = [];
  const add = (...values) => {
    for (const value of values) {
      if (value && !symbols.includes(value)) {
        symbols.push(value);
      }
    }
  };

  if (/삼성전자|SK하이닉스|하이닉스|반도체|DB하이텍|한미반도체|리노공업|HPSP|ISC|이오테크닉스/.test(text)) {
    add("SOXX", "XLK");
  }
  if (/NAVER|카카오|크래프톤|엔씨|게임|인터넷|플랫폼|소프트웨어/.test(text)) {
    add("QQQ", "XLK");
  }
  if (/LG에너지|삼성SDI|에코프로|엘앤에프|포스코퓨처|2차전지|배터리/.test(text)) {
    add("LIT", "XLY");
  }
  if (/현대차|기아|모비스|만도|자동차/.test(text)) {
    add("XLY", "QQQ");
  }
  if (/KB금융|신한|하나금융|우리금융|은행|증권|보험|미래에셋|삼성생명|메리츠|키움|금융/.test(text)) {
    add("XLF", "QQQ");
  }
  if (/SK이노|S-Oil|에쓰오일|GS|HD현대|한국가스|정유|에너지/.test(text)) {
    add("XLE", "XLB");
  }
  if (/LG화학|롯데케미칼|금호석유|한화솔루션|화학|소재|철강|POSCO|포스코|고려아연/.test(text)) {
    add("XLB", "XLE");
  }
  if (/대한항공|아시아나|항공/.test(text)) {
    add("JETS", "XLE");
  }
  if (/HMM|팬오션|해운|운송|물류|CJ대한통운/.test(text)) {
    add("IYT", "XLE");
  }
  if (/현대건설|건설|HD현대중공업|한화오션|조선|두산|방산|LIG넥스원|한화에어로|산업/.test(text)) {
    add("XLI", "XLB");
  }
  add("QQQ", "EWY");
  return symbols.slice(0, 2);
}

function relatedUsSectorMoves(item = {}, dashboard = {}, usSectorMoves = state.usSectorMoves) {
  const moves = usSectorMoveMap(usSectorMoves);
  return relatedUsSectorSymbols(item, dashboard)
    .map((symbol) => moves.get(symbol))
    .filter(Boolean);
}

function formatRelatedUsSectorMoves(item = {}, dashboard = {}, usSectorMoves = state.usSectorMoves) {
  const moves = relatedUsSectorMoves(item, dashboard, usSectorMoves).filter((move) => move.change_rate !== null && move.change_rate !== undefined);
  if (!moves.length) {
    return "미국 섹터 데이터 대기";
  }
  return moves.map((move) => `${move.label} ${formatPercent(move.change_rate)}`).join(" · ");
}

function koreaMarketPhase(now = new Date()) {
  const day = now.getDay();
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (day === 0 || day === 6) {
    return "closed";
  }
  if (8 * 60 <= minutes && minutes < 9 * 60) {
    return "preopen";
  }
  if (9 * 60 <= minutes && minutes < 15 * 60 + 30) {
    return "regular";
  }
  return "closed";
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

function updateWatchPreOpenPoints(usSectorMoves = state.usSectorMoves) {
  for (const card of elements.watchlistBody.querySelectorAll("[data-watch-card]")) {
    if (!card.watchDashboard) {
      continue;
    }
    card.usSectorMoves = usSectorMoves;
    const point = renderWatchPreOpenPoint(card, card.watchDashboard, card.watchDashboard.quote, card.watchItem, usSectorMoves);
    const metrics = card.querySelector(".watch-v15-metrics");
    if (metrics && point.nextSibling !== metrics) {
      card.insertBefore(point, metrics);
    }
  }
}

function watchlistStrategyPhase(usSectorMoves = state.usSectorMoves) {
  const koreaPhase = koreaMarketPhase();
  const usLabel = usSectorSessionLabel(usSectorMoves);
  if (koreaPhase === "preopen") {
    return { label: "국내 장전", usLabel, action: "시초가보다 미국 섹터 방향을 먼저 확인" };
  }
  if (koreaPhase === "regular") {
    return { label: "국내 장중", usLabel, action: "거래대금과 수급이 함께 유지되는 종목만 확인" };
  }
  return { label: "국내 장마감", usLabel, action: "다음 국내장 전, 미국 섹터 흐름을 확인" };
}

function watchlistTheme(item = {}) {
  const text = `${item.name || ""} ${item.code || ""}`;
  if (/삼성전자|SK하이닉스|DB하이텍|한미반도체|리노공업|HPSP|ISC|이오테크닉스/.test(text)) return "반도체";
  if (/LG에너지|삼성SDI|에코프로|엘앤에프|포스코퓨처|2차전지|배터리/.test(text)) return "2차전지";
  if (/현대차|기아|모비스|만도/.test(text)) return "자동차";
  if (/KB금융|신한|하나금융|우리금융|은행|증권|보험|미래에셋|삼성생명|메리츠|키움/.test(text)) return "금융";
  if (/SK이노|S-Oil|에쓰오일|GS|HD현대|한국가스|정유|에너지/.test(text)) return "정유";
  if (/LG화학|롯데케미칼|금호석유|한화솔루션|효성첨단소재|화학|소재|철강|POSCO|포스코|고려아연/.test(text)) return "화학";
  if (/한화에어로|LIG넥스원|현대로템|한국항공우주|풍산|한화시스템|방산/.test(text)) return "방산";
  if (/HD한국조선|HD현대중공업|한화오션|삼성중공업|조선/.test(text)) return "산업재";
  if (/셀트리온|삼성바이오|유한양행|한미약품|신풍제약|바이오|제약|헬스케어/.test(text)) return "헬스케어";
  if (/NAVER|카카오|크래프톤|엔씨|게임|인터넷|플랫폼|소프트웨어/.test(text)) return "인터넷";
  if (/대한항공|아시아나|항공/.test(text)) return "항공";
  if (/HMM|팬오션|해운|운송|물류|CJ대한통운/.test(text)) return "해운";
  return "기타";
}

function eventMatchesWatchItem(event = {}, item = {}) {
  const leaders = (event.timeline || []).flatMap((entry) => entry.leader_stocks || []);
  if (leaders.includes(item.name)) {
    return true;
  }
  const theme = watchlistTheme(item);
  return theme !== "기타" && (event.affected_sectors || []).some((sector) => String(sector).includes(theme) || theme.includes(String(sector)));
}

async function refreshWatchlistMarketContext(options = {}) {
  const force = options.force === true;
  const requests = await Promise.all([
    fetchJsonCached(force ? liveUrl("/market/impact?refresh=true") : "/market/impact", { force, ttlMs: force ? 0 : 5 * 60 * 1000 }).catch(() => null),
    fetchJsonCached("/market/trends?days=7", { force, ttlMs: force ? 0 : 5 * 60 * 1000 }).catch(() => null),
  ]);
  state.watchlistMarketContext = { impact: requests[0], trends: requests[1] };
  renderWatchlistStrategy(state.watchlistResults, state.usSectorMoves, state.watchlistMarketContext);
  return state.watchlistMarketContext;
}

function renderWatchlistStrategy(results = state.watchlistResults, usSectorMoves = state.usSectorMoves, marketContext = state.watchlistMarketContext) {
  const section = elements.watchlistStrategy;
  if (!section) {
    return;
  }
  const valid = (results || []).filter((result) => result?.dashboard);
  if (!valid.length) {
    section.hidden = true;
    section.replaceChildren();
    return;
  }

  const phase = watchlistStrategyPhase(usSectorMoves);
  const changes = valid.map((result) => toNumber(result.dashboard.quote?.change_rate)).filter((value) => value !== null);
  const positiveCount = changes.filter((value) => value > 0).length;
  const negativeCount = changes.filter((value) => value < 0).length;
  const relatedMoves = valid.flatMap((result) => relatedUsSectorMoves(result.item, result.dashboard, usSectorMoves));
  const uniqueMoves = Array.from(new Map(relatedMoves.map((move) => [move.symbol, move])).values());
  const usRates = uniqueMoves.map((move) => toNumber(move.change_rate)).filter((value) => value !== null);
  const usAverage = usRates.length ? usRates.reduce((sum, value) => sum + value, 0) / usRates.length : null;
  const usTone = usAverage === null ? "muted" : usAverage > 0 ? "positive" : usAverage < 0 ? "negative" : "muted";
  const factors = Array.isArray(marketContext?.impact?.factors) ? marketContext.impact.factors : [];
  const watchNames = new Set(valid.map((result) => result.item.name));
  const watchThemes = new Set(valid.map((result) => watchlistTheme(result.item)).filter((theme) => theme !== "기타"));
  const relevantFactors = factors.filter((factor) => {
    const leaders = Array.isArray(factor.leader_stocks) ? factor.leader_stocks : [];
    const sectors = Array.isArray(factor.affected_sectors) ? factor.affected_sectors : [];
    return leaders.some((name) => watchNames.has(name))
      || sectors.some((sector) => Array.from(watchThemes).some((theme) => String(sector).includes(theme) || theme.includes(String(sector))));
  });
  const majorFactors = relevantFactors.slice(0, 2);
  const events = Array.isArray(marketContext?.trends?.events) ? marketContext.trends.events : [];
  const relevantEvents = events.filter((event) => valid.some((result) => eventMatchesWatchItem(event, result.item)));
  const importantEvent = relevantEvents.find((event) => event.importance === "중요") || relevantEvents[0] || null;
  const marketNews = relevantEvents.flatMap((event) => event.timeline || []).find((item) => item?.title) || null;
  const mainFactor = majorFactors[0] || null;
  const monitoring = valid
    .map((result) => {
      const change = toNumber(result.dashboard.quote?.change_rate) || 0;
      const sentiment = toNumber(result.dashboard.sentiment?.score) || 0;
      const moves = relatedUsSectorMoves(result.item, result.dashboard, usSectorMoves);
      const relatedRates = moves.map((move) => toNumber(move.change_rate)).filter((value) => value !== null);
      const relatedAverage = relatedRates.length ? relatedRates.reduce((sum, value) => sum + value, 0) / relatedRates.length : null;
      const relatedMove = moves.find((move) => toNumber(move.change_rate) !== null);
      const factor = factors.find((entry) => (entry.leader_stocks || []).includes(result.item.name));
      const event = events.find((entry) => eventMatchesWatchItem(entry, result.item));
      const factorWeight = factor?.direction === "악재" ? Number(factor.percent || 0) * 0.45 : factor?.direction === "호재" ? Number(factor.percent || 0) * 0.2 : 0;
      const eventWeight = event?.importance === "중요" ? 14 : event ? 7 : 0;
      const score = Math.max(0, -change) * 4 + Math.max(0, -sentiment) * 0.2 + Math.max(0, -(relatedAverage || 0)) * 18 + factorWeight + eventWeight;
      let reason = change <= -1 ? `오늘 ${formatPercent(change)}` : "변동성 확인";
      if (factor) {
        reason = `${factor.label} ${factor.direction}`;
      } else if (event) {
        reason = `이벤트: ${event.title.replace("미국 ", "")}`;
      } else if (relatedMove && toNumber(relatedMove.change_rate) <= -0.2) {
        reason = `${relatedMove.label} ${formatPercent(relatedMove.change_rate)}`;
      }
      return { ...result, score, reason, relatedAverage, factor, event };
    })
    .sort((left, right) => right.score - left.score)
    .slice(0, Math.min(3, valid.length));

  const headline = mainFactor && positiveCount > negativeCount && mainFactor.direction === "악재"
    ? `관심 종목은 상승 중, ${mainFactor.label} 악재와의 괴리 확인`
    : mainFactor
      ? `${mainFactor.label} ${mainFactor.direction} 신호가 관심 종목의 핵심 변수`
    : usAverage !== null && usAverage <= -0.3
      ? "미국 연관 섹터 약세, 관심 종목 변동성 확인"
      : "주요 이벤트와 뉴스 흐름을 반영해 관심 종목을 점검 중";
  const leaderNames = mainFactor ? (mainFactor.leader_stocks || []).filter((name) => valid.some((result) => result.item.name === name)) : [];
  const action = mainFactor?.direction === "악재" && positiveCount > negativeCount
    ? `${leaderNames.length ? `${leaderNames.slice(0, 2).join(" · ")} 상승 지속 여부: ` : ""}거래대금과 외국인·기관 수급이 악재를 이기는지 확인`
    : mainFactor?.direction === "악재"
      ? `${leaderNames.length ? `${leaderNames.slice(0, 2).join(" · ")} 점검: ` : ""}${mainFactor.interpretation || "수급·뉴스 반응을 우선 확인"}`
    : negativeCount > positiveCount
      ? "오늘 약세였던 종목의 뉴스·수급·미국 연관 섹터를 함께 확인"
      : phase.action;

  const header = el("header", "watch-v2-briefing-head");
  const titleBlock = el("div", "watch-v2-briefing-title");
  titleBlock.append(el("span", "", "AI 시황 브리핑"), el("h2", "", headline));
  const phaseText = el("p", `watch-v2-session ${usTone}`, `${phase.label} / ${phase.usLabel}`);
  header.append(titleBlock, phaseText);

  const actionBlock = el("section", "watch-v2-action");
  actionBlock.append(el("span", "", "오늘의 대응"), el("strong", "", action));

  const stats = el("dl", "watch-v2-portfolio-line");
  const statItems = [
    ["관심", `${valid.length}개`, ""],
    ["상승", `${positiveCount}개`, positiveCount ? "positive" : ""],
    ["하락", `${negativeCount}개`, negativeCount ? "negative" : ""],
    ["미국 연관", usAverage === null ? "확인 중" : formatPercent(usAverage), usTone],
  ];
  for (const [label, value, tone] of statItems) {
    stats.appendChild(createWatchReportMetric(label, value, tone));
  }

  const context = el("dl", "watch-v2-briefing-context");
  const factorText = majorFactors.length
    ? majorFactors.map((factor) => `${factor.label} ${factor.direction}`).join(" · ")
    : "직접 연결된 특이 신호 없음";
  const factorTone = majorFactors.some((factor) => factor.direction === "악재")
    ? "negative"
    : majorFactors.some((factor) => factor.direction === "호재")
      ? "positive"
      : "muted";
  context.append(
    createWatchContextItem("시장 변수", factorText, factorTone),
    createWatchContextItem("주요 일정", importantEvent ? importantEvent.title.replace("미국 ", "") : "가까운 주요 일정 없음", importantEvent ? "event" : "muted"),
    createWatchContextItem("시장 뉴스", marketNews?.title || "연결된 주요 뉴스 확인 중", "muted"),
  );
  const monitorBlock = el("section", "watch-v2-monitoring");
  const monitorHead = el("div", "watch-v2-monitoring-head");
  monitorHead.append(el("h3", "", "먼저 볼 종목"), el("span", "", `${monitoring.length}개`));
  const monitorList = el("div", "watch-v2-monitoring-list");
  for (const [index, item] of monitoring.entries()) {
    const row = document.createElement("a");
    row.className = "watch-v2-monitor-row";
    row.href = viewStockUrl(item.item.name);
    const rank = el("span", "watch-v2-monitor-rank", String(index + 1));
    const copy = el("span", "watch-v2-monitor-copy");
    copy.append(el("strong", "", item.item.name), el("small", "", item.reason));
    const change = toNumber(item.dashboard.quote?.change_rate);
    const rate = el("span", change > 0 ? "positive" : change < 0 ? "negative" : "muted", formatPercent(change));
    row.append(rank, copy, rate);
    monitorList.appendChild(row);
  }
  monitorBlock.append(monitorHead, monitorList);

  const body = el("div", "watch-v2-briefing-body");
  const overview = el("div", "watch-v2-briefing-overview");
  overview.append(actionBlock, stats, context);
  body.append(overview, monitorBlock);
  section.className = "watchlist-strategy watch-v2-briefing";
  section.replaceChildren(header, body);
  section.hidden = false;
}

function watchPreOpenSummary(dashboard, quoteOverride = null, item = {}, usSectorMoves = state.usSectorMoves) {
  const quote = quoteOverride || dashboard.quote || {};
  const phase = koreaMarketPhase();
  const preRate = toNumber(quote.pre_market_change_rate);
  const changeRate = toNumber(quote.change_rate);
  const oneMonth = toNumber(dashboard.momentum?.one_month_return);
  const threeMonth = toNumber(dashboard.momentum?.three_month_return);
  const macroView = interpretMacro(dashboard);
  const flowPoint = watchFlowPoint(dashboard.flows || {});
  const trendPoint = watchTrendPoint(oneMonth, threeMonth);
  const newsPoint = watchNewsPoint(dashboard.sentiment || {});
  const points = [];
  let title = "출발 포인트 대기";
  let tone = "muted";
  let label = "국내증시 개장 전 포인트";
  let collapsed = true;
  const addPoint = (text) => {
    if (!text || points.includes(text)) {
      return;
    }
    points.push(text);
  };

  if (phase === "regular") {
    label = "국내증시 장중 포인트";
    if (changeRate >= 1) {
      title = "강세 진행 · 거래대금 유지 확인";
      tone = "positive";
    } else if (changeRate <= -1) {
      title = "약세 진행 · 추가 매도 압력 확인";
      tone = "negative";
    } else {
      title = "보합권 · 수급 방향 확인";
      tone = "muted";
    }
    addPoint(flowPoint || "수급 방향 확인 중");
    addPoint(trendPoint);
    addPoint(newsPoint);
    addPoint(`거시 ${macroView.label}`);
    return { label, title, tone, points: points.slice(0, 4), collapsed, mode: phase, hint: "" };
  }

  if (phase === "closed") {
    label = "국내증시 장마감 포인트";
    if (changeRate >= 1) {
      title = "강세 마감 · 다음 장 수급 지속 확인";
      tone = "positive";
    } else if (changeRate <= -1) {
      title = "약세 마감 · 다음 장 수급 회복 확인";
      tone = "negative";
    } else {
      title = "보합 마감 · 다음 장 방향 확인";
    }
    addPoint(flowPoint || "수급 방향 확인 중");
    addPoint(trendPoint);
    addPoint(newsPoint);
    addPoint(`거시 ${macroView.label}`);
    return { label, title, tone, points: points.slice(0, 4), collapsed, mode: phase, hint: "" };
  }

  if (preRate !== null) {
    if (preRate >= 1) {
      title = "상승 출발 · 시초가 지지 확인";
      tone = "positive";
    } else if (preRate <= -1) {
      title = "하락 출발 · 낙폭 확대 여부 확인";
      tone = "negative";
    } else {
      title = quote.pre_market_status === "장전 호가 대기" ? "장전 호가 대기" : "보합 출발 · 수급 확인";
    }
    addPoint(preRate === 0 ? "장전 호가 대기" : `장전 흐름 ${formatPercent(preRate)}`);
  } else if (changeRate !== null) {
    title = quote.pre_market_status || (changeRate > 0 ? "전일 강세 연장 여부" : changeRate < 0 ? "전일 약세 회복 여부" : "보합 출발 관찰");
    tone = changeRate > 0 ? "positive" : changeRate < 0 ? "negative" : "muted";
    addPoint(changeRate > 0 ? "전일 강세 흐름 이어지는지 확인" : changeRate < 0 ? "전일 약세 회복 여부 확인" : "보합 출발 가능성 확인");
  } else {
    addPoint(quote.pre_market_status || "장전 호가 데이터 없음");
  }

  addPoint(flowPoint || "수급 방향 확인 중");
  addPoint(trendPoint);
  addPoint(newsPoint);
  addPoint(`거시 ${macroView.label}`);
  return { label, title, tone, points: points.slice(0, 5), collapsed, mode: phase, hint: "" };
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
    section.className = "watch-preopen-point watch-v15-response watch-v2-response";
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
  section.className = `watch-preopen-point watch-v15-response watch-v2-response ${point.tone} ${point.collapsed ? "collapsed" : ""}`;
  const keepExpanded = itemCode ? state.watchPreopenExpanded.has(itemCode) : false;
  section.open = point.collapsed ? keepExpanded : true;
  section.dataset.mode = point.mode || "";
  const summary = document.createElement("summary");
  const summaryMain = document.createElement("div");
  const label = document.createElement("span");
  label.textContent = point.label || "개장 전 포인트";
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
  for (const item of point.points) {
    const row = document.createElement("li");
    row.textContent = item;
    list.appendChild(row);
  }
  const evidence = document.createElement("dl");
  evidence.className = "watch-v2-evidence";
  const flowView = watchFlowView(dashboard);
  const valuationView = interpretValuation(dashboard);
  const newsView = watchNewsView(dashboard);
  const macroView = interpretMacro(dashboard);
  evidence.append(
    createWatchContextItem("수급", flowView.label, flowView.tone),
    createWatchContextItem("밸류", valuationView.label, valuationView.tone),
    createWatchContextItem("뉴스", newsView.label, newsView.tone),
    createWatchContextItem("거시", macroView.label, macroView.tone),
  );
  const detailBody = document.createElement("div");
  detailBody.className = "watch-v2-response-body";
  detailBody.append(list, evidence, createWatchUsSectorStrip(item, dashboard, usSectorMoves));
  section.replaceChildren(summary, detailBody);
  return section;
}

function isLoadingMessageText(text = "") {
  return /불러오는 중|로딩|계산/.test(String(text));
}

function appendInlineLoadingState(card, title, message = "") {
  const spinner = document.createElement("span");
  spinner.className = "inline-loading-spinner";
  spinner.setAttribute("aria-hidden", "true");
  const titleEl = document.createElement("strong");
  titleEl.textContent = title;
  card.append(spinner, titleEl);
  if (message) {
    const messageEl = document.createElement("p");
    messageEl.textContent = message;
    card.appendChild(messageEl);
  }
}

function renderWatchlistMessage(text) {
  clearWatchlistLoadingOverlay();
  elements.watchlistBody.innerHTML = "";
  const message = document.createElement("article");
  message.className = "watchlist-empty-card";
  const isEmpty = text === "관심 종목 없음";
  const title = document.createElement("strong");
  title.textContent = isEmpty ? "관심 종목이 아직 없습니다." : "종목 정보를 불러오지 못했습니다.";
  const description = document.createElement("p");
  description.textContent = isEmpty
    ? "종목 검색에서 별표를 누르면 이곳에서 시황과 대응 정보를 한 번에 볼 수 있습니다."
    : "잠시 후 다시 열거나 새로고침해 주세요.";
  message.append(title, description);
  if (isEmpty) {
    const action = document.createElement("button");
    action.type = "button";
    action.textContent = "종목 검색 열기";
    action.addEventListener("click", () => setView("stock"));
    message.appendChild(action);
  }
  elements.watchlistBody.appendChild(message);
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

function appendWatchRow(item, dashboard, usSectorMoves = state.usSectorMoves) {
  const card = document.createElement("article");
  card.className = "watch-stock-card watch-v2-stock-row";
  card.dataset.code = item.code;
  card.dataset.watchCard = "true";
  card.watchDashboard = dashboard;
  card.watchItem = item;
  card.usSectorMoves = usSectorMoves;
  const statusView = watchStatusView(dashboard);
  card.dataset.watchStatus = statusView.id;

  const header = document.createElement("div");
  header.className = "watch-stock-head watch-v2-stock-head";
  const link = document.createElement("a");
  link.className = "watch-stock-name";
  link.href = viewStockUrl(item.name);
  const nameRow = document.createElement("span");
  nameRow.className = "watch-v2-stock-name-row";
  const strong = document.createElement("strong");
  strong.textContent = item.name;
  const status = document.createElement("span");
  status.className = `watch-v2-status ${statusView.tone}`;
  status.dataset.field = "watch_status";
  status.append(el("i", ""), document.createTextNode(statusView.label));
  nameRow.append(strong, status);
  const meta = document.createElement("span");
  meta.className = "watch-stock-quote";
  const inlinePrice = document.createElement("strong");
  inlinePrice.className = "watch-stock-inline-price";
  inlinePrice.dataset.field = "price";
  inlinePrice.textContent = formatNumber(dashboard.quote.price);
  const inlineChange = document.createElement("strong");
  inlineChange.className = "watch-stock-inline-change";
  inlineChange.dataset.field = "change_rate";
  inlineChange.textContent = formatPercent(dashboard.quote.change_rate);
  setTone(inlineChange, dashboard.quote.change_rate);
  meta.append(inlinePrice, inlineChange);
  link.append(nameRow, meta);

  const removeButton = document.createElement("button");
  removeButton.className = "remove-watch";
  removeButton.type = "button";
  removeButton.textContent = "★";
  removeButton.dataset.code = item.code;
  removeButton.setAttribute("aria-label", `${item.name} 관심 해제`);
  removeButton.setAttribute("aria-pressed", "true");
  removeButton.title = "관심 해제";
  header.append(link, removeButton);

  const metrics = document.createElement("dl");
  metrics.className = "watch-v15-metrics watch-v2-metrics";
  metrics.append(
    createWatchReportMetric("거래대금", formatMoney(dashboard.quote.trading_value), "", "trading_value"),
    createWatchReportMetric("1개월", formatPercent(dashboard.momentum.one_month_return), "", "one_month", dashboard.momentum.one_month_return),
    createWatchReportMetric("3개월", formatPercent(dashboard.momentum.three_month_return), "", "three_month", dashboard.momentum.three_month_return),
    createWatchReportMetric("뉴스", formatPercent(dashboard.sentiment.score), "", "sentiment", dashboard.sentiment.score)
  );

  const preOpenPoint = renderWatchPreOpenPoint(card, dashboard, null, item, usSectorMoves);

  const footer = document.createElement("footer");
  footer.className = "watch-v2-row-footer";
  const detailLink = document.createElement("a");
  detailLink.href = viewStockUrl(item.name);
  detailLink.append(el("span", "", "종목 상세"), el("span", "", "›"));
  footer.appendChild(detailLink);

  card.append(header, preOpenPoint, metrics, footer);
  elements.watchlistBody.appendChild(card);
  return card;
}

function appendWatchLoadingRow(item) {
  const card = document.createElement("article");
  card.className = "watch-stock-card watch-v2-stock-row watch-stock-loading";
  card.dataset.code = item.code || "";
  card.setAttribute("aria-label", `${item.name || item.code || "종목"} · ${PAGE_LOADING_LABELS.watchlist}`);
  const name = document.createElement("strong");
  name.textContent = item.name || item.code || "종목";
  const status = document.createElement("div");
  status.className = "watch-stock-loading-status";
  const spinner = document.createElement("span");
  spinner.className = "inline-loading-spinner";
  spinner.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.textContent = "핵심 지표 확인 중";
  status.append(spinner, label);
  card.append(name, status);
  elements.watchlistBody.appendChild(card);
  return card;
}

async function loadWatchlist(options = {}) {
  const loadSequence = ++state.watchlistLoadSequence;
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("watchlist");
  closeWatchlistQuoteStreams();
  const items = readWatchlist();
  const itemOrder = new Map(items.map((item, index) => [item.code, index]));
  let completedCount = 0;
  elements.watchlistMeta.textContent = `${items.length}개 종목 · 핵심 지표 확인 중`;
  elements.watchlistBody.innerHTML = "";
  state.watchlistResults = [];
  applyWatchlistFilter();
  renderWatchlistStrategy();
  if (!items.length) {
    elements.watchlistMeta.textContent = "0개 종목";
    clearWatchlistLoadingOverlay();
    renderWatchlistMessage("관심 종목 없음");
    return;
  }
  clearWatchlistLoadingOverlay();
  const pendingRows = new Map(items.map((item) => [item.code, appendWatchLoadingRow(item)]));
  const sectorMovesPromise = refreshUsSectorMoves({ force });
  const marketContextPromise = refreshWatchlistMarketContext({ force });
  const results = await mapWithConcurrency(
    items,
    6,
    async (item) => {
      try {
        const url = `/stocks/${encodeURIComponent(item.code)}/dashboard?include_profile=0&include_live=0`;
        const dashboard = await Promise.race([
          fetchJsonCached(url, { force, ttlMs: force ? 0 : ttlMs }),
          rejectAfter(15_000, "watchlist dashboard timeout"),
        ]);
        if (loadSequence !== state.watchlistLoadSequence) {
          return { item, dashboard: null, cancelled: true };
        }
        const card = appendWatchRow(item, dashboard, state.usSectorMoves);
        const pendingRow = pendingRows.get(item.code);
        if (pendingRow?.isConnected) {
          pendingRow.replaceWith(card);
        } else {
          elements.watchlistBody.appendChild(card);
        }
        state.watchlistResults = [
          ...state.watchlistResults.filter((result) => result.item.code !== item.code),
          { item, dashboard },
        ].sort((left, right) => (itemOrder.get(left.item.code) || 0) - (itemOrder.get(right.item.code) || 0));
        applyWatchlistFilter();
        renderWatchlistStrategy(state.watchlistResults, state.usSectorMoves, state.watchlistMarketContext);
        connectWatchlistQuoteStream(item.code);
        return { item, dashboard };
      } catch {
        if (loadSequence !== state.watchlistLoadSequence) {
          return { item, dashboard: null, cancelled: true };
        }
        const pendingRow = pendingRows.get(item.code);
        if (pendingRow?.isConnected) {
          pendingRow.classList.add("is-error");
          const label = pendingRow.querySelector(".watch-stock-loading-status span:last-child");
          if (label) {
            label.textContent = "데이터 확인이 지연되고 있습니다";
          }
          pendingRow.querySelector(".inline-loading-spinner")?.remove();
        }
        return { item, dashboard: null };
      } finally {
        completedCount += 1;
        if (loadSequence === state.watchlistLoadSequence && completedCount < items.length) {
          elements.watchlistMeta.textContent = `${items.length}개 종목 · ${completedCount}/${items.length}개 확인 중`;
        }
      }
    }
  );
  if (loadSequence !== state.watchlistLoadSequence) {
    return;
  }
  clearWatchlistLoadingOverlay();
  state.watchlistResults = results.filter((result) => result.dashboard);
  elements.watchlistMeta.textContent = `${items.length}개 종목 · 실시간 시세`;
  applyWatchlistFilter();
  renderWatchlistStrategy(state.watchlistResults, state.usSectorMoves, state.watchlistMarketContext);
  connectUsSectorStream();
  sectorMovesPromise.catch(() => {});
  marketContextPromise.catch(() => {});
  if (!state.watchlistResults.length && !elements.watchlistBody.children.length) {
    renderWatchlistMessage("데이터 없음");
  }
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
    .reverse();
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
    patterns: [],
  };
}

function attachChartPatterns(analysis, dashboard) {
  if (!analysis) {
    return analysis;
  }
  analysis.patterns = Array.isArray(dashboard?.chart_analysis?.patterns)
    ? dashboard.chart_analysis.patterns
    : [];
  return analysis;
}

function primaryChartPattern(analysis) {
  const patterns = Array.isArray(analysis?.patterns) ? analysis.patterns : [];
  return patterns.find((item) => item.status === "확인") || patterns[0] || null;
}

function chartPatternTone(pattern) {
  if (pattern?.direction === "bullish") return "positive";
  if (pattern?.direction === "bearish") return "negative";
  return "neutral";
}

function computeChartForecast(analysis, horizon = 5, liveCurrentPrice = null) {
  const days = horizon === 10 ? 10 : 5;
  const rows = (analysis?.prices || []).filter((row) => toNumber(row.close) !== null);
  const closes = rows.map((row) => toNumber(row.close));
  const lastDailyClose = closes.at(-1) ?? null;
  const current = toNumber(liveCurrentPrice) ?? lastDailyClose;
  if (current === null || closes.length < 30) {
    return { days, available: false, reason: "예상 범위를 계산하려면 최소 30거래일의 가격이 필요합니다." };
  }

  const returns = [];
  for (let index = 1; index < closes.length; index += 1) {
    if (closes[index - 1] > 0 && closes[index] > 0) {
      returns.push(Math.log(closes[index] / closes[index - 1]));
    }
  }
  const recentReturns = returns.slice(-20);
  const shortReturns = returns.slice(-5);
  const shortDrift = average(shortReturns) ?? 0;
  const mediumDrift = average(recentReturns) ?? 0;
  const trendGap = analysis.ma5 && analysis.ma20 ? (analysis.ma5 - analysis.ma20) / analysis.ma20 : 0;
  const momentumBoost = analysis.macd?.histogram && current ? clampNumber(analysis.macd.histogram / current, -0.01, 0.01) : 0;
  const primaryPattern = primaryChartPattern(analysis);
  const patternWeight = primaryPattern
    ? (primaryPattern.status === "확인" ? 0.0015 : 0.00045) * ((toNumber(primaryPattern.confidence) ?? 50) / 100)
    : 0;
  const patternDrift = primaryPattern?.direction === "bullish"
    ? patternWeight
    : primaryPattern?.direction === "bearish" ? -patternWeight : 0;
  const dailyDrift = clampNumber(shortDrift * 0.42 + mediumDrift * 0.38 + trendGap * 0.014 + momentumBoost * 0.2 + patternDrift, -0.025, 0.025);
  const returnVolatility = standardDeviation(recentReturns) ?? 0;
  const atrVolatility = (analysis.atr ?? 0) / 100;
  const dailyVolatility = clampNumber(returnVolatility * 0.68 + atrVolatility * 0.32, 0.005, 0.06);
  const points = [];
  for (let day = 1; day <= days; day += 1) {
    const center = current * Math.exp(dailyDrift * day);
    const band = Math.min(0.35, 1.28 * dailyVolatility * Math.sqrt(day));
    points.push({ day, center, lower: center * (1 - band), upper: center * (1 + band) });
  }
  const expected = points.at(-1)?.center ?? current;
  const expectedRate = ((expected - current) / current) * 100;
  const trendAligned = (dailyDrift >= 0 && analysis.ma20 && current >= analysis.ma20)
    || (dailyDrift < 0 && analysis.ma20 && current < analysis.ma20);
  const confidenceScore = clampNumber(
    48 + Math.min(18, rows.length / 10) + (trendAligned ? 10 : 0) + (primaryPattern?.status === "확인" ? 5 : 0) - Math.max(0, dailyVolatility * 240),
    35,
    82,
  );
  const confidence = confidenceScore >= 68 ? "높음" : confidenceScore >= 52 ? "보통" : "낮음";
  const direction = expectedRate > 1 ? "상승 우위" : expectedRate < -1 ? "하락 우위" : "횡보 가능성";
  return {
    days,
    available: true,
    current,
    dailyClose: lastDailyClose,
    expected,
    expectedRate,
    dailyDrift,
    dailyVolatility,
    confidence,
    confidenceScore,
    direction,
    points,
    primaryPattern,
  };
}

function chartForecastTone(value) {
  const number = toNumber(value) ?? 0;
  return number > 0.1 ? "positive" : number < -0.1 ? "negative" : "neutral";
}

function createChartForecastSvg(analysis, forecast) {
  const actual = analysis.prices.slice(-90).map((row) => ({
    date: String(row.trade_date || row.date || "").slice(0, 10),
    close: toNumber(row.close),
    volume: toNumber(row.volume) ?? 0,
  })).filter((row) => row.close !== null);
  if (actual.length < 2 || !forecast?.available) {
    return "";
  }
  // The final point is the current KIS quote; prior points remain completed candles.
  actual[actual.length - 1] = { ...actual.at(-1), close: forecast.current };
  const width = 720;
  const height = 330;
  const left = 24;
  const right = 54;
  const top = 24;
  const bottom = 54;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const future = forecast.points;
  const values = [
    ...actual.map((row) => row.close),
    ...future.flatMap((point) => [point.lower, point.center, point.upper]),
  ];
  let min = Math.min(...values);
  let max = Math.max(...values);
  const padding = Math.max(1, (max - min) * 0.12);
  min -= padding;
  max += padding;
  const span = max - min || 1;
  const totalSteps = actual.length - 1 + future.length;
  const x = (step) => left + (step / totalSteps) * plotWidth;
  const y = (value) => top + ((max - value) / span) * plotHeight;
  const path = (points) => points.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ");
  const actualPoints = actual.map((row, index) => [x(index), y(row.close)]);
  const currentIndex = actual.length - 1;
  const centerPoints = [[x(currentIndex), y(actual.at(-1).close)], ...future.map((point) => [x(currentIndex + point.day), y(point.center)])];
  const upperPoints = [[x(currentIndex), y(actual.at(-1).close)], ...future.map((point) => [x(currentIndex + point.day), y(point.upper)])];
  const lowerPoints = [[x(currentIndex), y(actual.at(-1).close)], ...future.map((point) => [x(currentIndex + point.day), y(point.lower)])];
  const bandPoints = [...upperPoints, ...lowerPoints.slice().reverse()];
  const maxVolume = Math.max(1, ...actual.map((row) => row.volume));
  const volumeBars = actual.map((row, index) => {
    const barHeight = Math.max(2, (row.volume / maxVolume) * 34);
    return `<rect x="${(x(index) - 1.7).toFixed(1)}" y="${(top + plotHeight - barHeight).toFixed(1)}" width="3.4" height="${barHeight.toFixed(1)}" rx="1.5" />`;
  }).join("");
  const grids = [0, 0.5, 1].map((ratio) => {
    const value = max - span * ratio;
    const gridY = top + plotHeight * ratio;
    return `<line x1="${left}" y1="${gridY.toFixed(1)}" x2="${width - right}" y2="${gridY.toFixed(1)}"/><text x="${width - right + 8}" y="${(gridY + 4).toFixed(1)}">${formatChartAxisPrice(value)}</text>`;
  }).join("");
  const currentX = x(currentIndex);
  const end = future.at(-1);
  const endX = x(totalSteps);
  const endY = y(end.center);
  const pattern = forecast.primaryPattern;
  const dateIndex = new Map(actual.map((row, index) => [row.date, index]));
  const patternPoints = (pattern?.points || [])
    .map((point) => {
      const index = dateIndex.get(String(point.date || "").slice(0, 10));
      const price = toNumber(point.price);
      return index === undefined || price === null ? null : [x(index), y(price)];
    })
    .filter(Boolean);
  const patternLine = patternPoints.length >= 2
    ? `<polyline class="chart-pattern-shape ${chartPatternTone(pattern)}" points="${patternPoints.map((point) => `${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ")}" />`
    : "";
  const trigger = toNumber(pattern?.trigger);
  const triggerLine = trigger !== null && trigger >= min && trigger <= max && patternPoints.length
    ? `<line class="chart-pattern-trigger" x1="${patternPoints[0][0].toFixed(1)}" y1="${y(trigger).toFixed(1)}" x2="${currentX.toFixed(1)}" y2="${y(trigger).toFixed(1)}" />`
    : "";
  const patternLabel = patternLine
    ? `<text class="chart-pattern-label ${chartPatternTone(pattern)}" x="${patternPoints[0][0].toFixed(1)}" y="${Math.max(top + 14, patternPoints[0][1] - 12).toFixed(1)}">${pattern.name} · ${pattern.status}</text>`
    : "";
  return `
    <svg class="chart-forecast-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="실제 가격과 ${forecast.days}거래일 예상 범위">
      <g class="chart-forecast-grid">${grids}</g>
      <rect class="chart-forecast-future-zone" x="${currentX.toFixed(1)}" y="${top}" width="${(width - right - currentX).toFixed(1)}" height="${plotHeight}" />
      <g class="chart-forecast-volume">${volumeBars}</g>
      <path class="chart-forecast-band" d="${path(bandPoints)} Z" />
      <path class="chart-forecast-actual" d="${path(actualPoints)}" />
      ${patternLine}${triggerLine}${patternLabel}
      <path class="chart-forecast-bound" d="${path(upperPoints)}" />
      <path class="chart-forecast-bound" d="${path(lowerPoints)}" />
      <path class="chart-forecast-center ${chartForecastTone(forecast.expectedRate)}" d="${path(centerPoints)}" />
      <line class="chart-forecast-now" x1="${currentX.toFixed(1)}" y1="${top}" x2="${currentX.toFixed(1)}" y2="${top + plotHeight}" />
      <circle class="chart-forecast-current-dot" cx="${currentX.toFixed(1)}" cy="${y(actual.at(-1).close).toFixed(1)}" r="5" />
      <circle class="chart-forecast-end-dot ${chartForecastTone(forecast.expectedRate)}" cx="${endX.toFixed(1)}" cy="${endY.toFixed(1)}" r="6" />
      <text class="chart-forecast-axis-label" x="${left}" y="${height - 14}">최근 흐름</text>
      <text class="chart-forecast-axis-label current" x="${currentX.toFixed(1)}" y="${height - 14}" text-anchor="middle">현재</text>
      <text class="chart-forecast-axis-label" x="${width - right}" y="${height - 14}" text-anchor="end">${forecast.days}거래일 후</text>
    </svg>`;
}

function renderChartPatternAnalysis(analysis) {
  const section = el("section", "chart-pattern-analysis");
  const heading = el("div", "chart-pattern-heading");
  heading.append(el("span", "", "가격 구조"), el("h2", "", "패턴 분석"));
  section.appendChild(heading);
  const patterns = Array.isArray(analysis?.patterns) ? analysis.patterns : [];
  if (!patterns.length) {
    section.append(el("p", "chart-pattern-empty", "현재 구간에서 기준을 충족한 고전 패턴은 없습니다."));
    return section;
  }
  const primary = primaryChartPattern(analysis);
  const top = el("div", "chart-pattern-primary");
  const title = el("div", "chart-pattern-title");
  title.append(
    el("strong", "", primary.name),
    el("span", `${chartPatternTone(primary)} status`, primary.status),
    el("span", "confidence", `신뢰도 ${Math.round(toNumber(primary.confidence) ?? 0)}점`),
  );
  top.append(title, el("p", "", primary.summary));
  const levels = el("div", "chart-pattern-levels");
  for (const [label, value, tone] of [
    ["전환 기준", primary.trigger, ""],
    ["목표", primary.target, chartPatternTone(primary)],
    ["무효화", primary.invalidation, primary.direction === "bullish" ? "negative" : "positive"],
  ]) {
    const cell = el("div", "");
    cell.append(el("span", "", label), el("strong", tone, value ? `${formatNumber(value)}원` : "확인 중"));
    levels.appendChild(cell);
  }
  top.appendChild(levels);
  section.appendChild(top);
  if (patterns.length > 1) {
    const details = el("details", "chart-pattern-more");
    const summary = el("summary", "", `함께 감지된 패턴 ${patterns.length - 1}개`);
    const list = el("div", "chart-pattern-list");
    for (const pattern of patterns.slice(1)) {
      const row = el("div", "chart-pattern-row");
      row.append(
        el("strong", "", pattern.name),
        el("span", chartPatternTone(pattern), `${pattern.status} · ${Math.round(toNumber(pattern.confidence) ?? 0)}점`),
      );
      list.appendChild(row);
    }
    details.append(summary, list);
    section.appendChild(details);
  }
  return section;
}

function createChartForecastReason(label, value, tone = "") {
  const row = el("div", "chart-forecast-reason");
  row.append(el("span", "", label), el("strong", tone, value));
  return row;
}

function renderChartForecastResult(result, horizon = 5) {
  if (!result?.analysis || !result?.dashboard) {
    renderWatchChartMessage("차트 데이터를 불러오지 못했습니다.", "잠시 후 다시 조회해주세요.");
    return;
  }
  const { item, analysis, dashboard } = result;
  attachChartPatterns(analysis, dashboard);
  const forecast = computeChartForecast(analysis, horizon, dashboard?.quote?.price);
  elements.chartStartGuide?.setAttribute("hidden", "");
  elements.watchChartList.innerHTML = "";
  const section = el("section", "chart-forecast-page");
  section.dataset.code = item.code;

  const header = el("header", "chart-forecast-header");
  const heading = el("div", "chart-forecast-heading");
  heading.append(
    el("span", "chart-forecast-eyebrow", "기술적 흐름 분석"),
    el("h1", "", item.name || dashboard.name || item.code),
    el("p", "", [item.code, item.market || dashboard.market].filter(Boolean).join(" · ")),
  );
  const basis = formatDateLabel(dashboard?.quote?.as_of || analysis.latest?.date || dashboard?.as_of);
  header.append(heading, el("time", "chart-forecast-basis", `${basis} 기준`));

  const controls = el("div", "chart-forecast-controls");
  controls.setAttribute("role", "tablist");
  controls.setAttribute("aria-label", "예상 기간");
  for (const days of [5, 10]) {
    const button = el("button", days === forecast.days ? "active" : "", `${days}일`);
    button.type = "button";
    button.dataset.chartHorizon = String(days);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(days === forecast.days));
    controls.appendChild(button);
  }

  if (!forecast.available) {
    const empty = el("section", "chart-forecast-insufficient");
    empty.append(el("strong", "", "분석 데이터가 부족합니다."), el("p", "", forecast.reason));
    section.append(header, controls, empty);
    elements.watchChartList.appendChild(section);
    return;
  }

  const visual = el("figure", "chart-forecast-visual");
  visual.innerHTML = createChartForecastSvg(analysis, forecast);
  const legend = el("figcaption", "chart-forecast-legend");
  legend.innerHTML = '<span class="actual">실제 가격</span><span class="center">예상 중심</span><span class="range">예상 범위</span>';
  visual.appendChild(legend);

  const summary = el("section", "chart-forecast-summary");
  const summaryHead = el("div", "chart-forecast-summary-head");
  summaryHead.append(
    el("span", "", `${forecast.days}거래일 시나리오`),
    el("strong", chartForecastTone(forecast.expectedRate), forecast.direction),
  );
  const metrics = el("div", "chart-forecast-metrics");
  const metricData = [
    ["현재가", `${formatNumber(roundTradePrice(forecast.current))}원`, ""],
    ["예상 중심", `${formatNumber(roundTradePrice(forecast.expected))}원`, chartForecastTone(forecast.expectedRate)],
    ["예상 범위", `${formatPriceRange(forecast.points.at(-1).lower, forecast.points.at(-1).upper)}원`, ""],
    ["흐름 신뢰도", `${forecast.confidence} · ${Math.round(forecast.confidenceScore)}점`, ""],
  ];
  for (const [label, value, tone] of metricData) {
    const cell = el("div", "chart-forecast-metric");
    cell.append(el("span", "", label), el("strong", tone, value));
    metrics.appendChild(cell);
  }
  summary.append(summaryHead, metrics);

  const reasons = el("section", "chart-forecast-reasons");
  reasons.append(el("h2", "", "분석 포인트"));
  const trendText = analysis.ma20 && forecast.current >= analysis.ma20 ? "20일 평균선 위" : "20일 평균선 아래";
  const momentumText = analysis.rsi === null ? "모멘텀 확인 중" : `RSI ${Math.round(analysis.rsi)} · ${analysis.rsi >= 70 ? "과열 주의" : analysis.rsi <= 35 ? "약세 구간" : "중립 구간"}`;
  const volatilityText = analysis.atr === null ? "변동성 확인 중" : `일 변동폭 약 ${analysis.atr.toFixed(1)}%`;
  reasons.append(
    createChartForecastReason("추세", trendText, analysis.ma20 && forecast.current >= analysis.ma20 ? "positive" : "negative"),
    createChartForecastReason("모멘텀", momentumText),
    createChartForecastReason("변동성", volatilityText),
  );

  const note = el("p", "chart-forecast-note", "최근 가격·거래량·이동평균·RSI·MACD·ATR을 결합한 기술적 시나리오입니다. 실제 가격은 뉴스와 수급에 따라 예상 범위를 벗어날 수 있습니다.");
  section.append(header, controls, visual, renderChartPatternAnalysis(analysis), summary, reasons, note);
  elements.watchChartList.appendChild(section);
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
  label.textContent = `MA5 ${formatNumber(analysis.ma5)} · MA20 ${formatNumber(analysis.ma20)} · MA60 ${formatNumber(analysis.ma60)} · MA120 ${formatNumber(analysis.ma120)} · BB 상/하 ${formatNumber(analysis.bands.upper)}/${formatNumber(analysis.bands.lower)}`;
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
  const snapshots = readChartSnapshots();
  elements.watchChartSnapshotMeta.textContent = snapshots.length ? `${formatNumber(snapshots.length)}개 저장` : "저장 없음";
  elements.watchChartSnapshots.innerHTML = "";
  if (!snapshots.length) {
    elements.watchChartSnapshots.appendChild(el("p", "muted", "차트 카드의 스냅샷 저장을 누르면 이곳에 기록됩니다."));
    return;
  }
  for (const snapshot of snapshots.slice(0, 12)) {
    const item = el("article", "chart-snapshot-item");
    item.dataset.snapshotId = snapshot.id;
    item.append(
      el("strong", "", `${snapshot.name} · ${snapshot.stance}`),
      el("span", "", `${formatDataBasis(snapshot.saved_at)} · 점수 ${formatNumber(snapshot.score)} · 현재가 ${formatNumber(snapshot.price)}`)
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
        ["현재가", formatNumber(price)],
        ["매수 기준", "보류"],
        ["손절/축소 기준", "산정 보류"],
        ["돌파 매수가", "산정 보류"],
      ],
      explanation: [
        `현재가 ${formatNumber(price)} 기준으로는 매수 가격대와 손실 제한선을 계산할 데이터가 부족합니다.`,
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
  const atrBasis = clampNumber(analysis.atr || 2.5, 1, 8);
  const buyLowPct = clampNumber(atrBasis * 0.45, 1, 2.2);
  const buyHighDiscountPct = clampNumber(atrBasis * 0.1, 0.2, 0.6);
  const stopPct = clampNumber(atrBasis * 0.55, 2, 3.5);
  const breakoutPct = clampNumber(atrBasis * 0.35, 1.2, 2.5);
  const targetPct = clampNumber(atrBasis * 0.8, 3, 5.5);
  const nearbyResistance = analysis.resistance && price && analysis.resistance > price && analysis.resistance <= price * 1.03
    ? analysis.resistance
    : null;
  const nearbySupport = analysis.support && price && analysis.support < price && analysis.support >= price * 0.97
    ? analysis.support
    : null;
  const buyHigh = price ? price * (1 - buyHighDiscountPct / 100) : null;
  const fallbackBuyLow = price ? price * (1 - buyLowPct / 100) : null;
  const supportedBuyLow = nearbySupport && fallbackBuyLow && buyHigh && nearbySupport >= fallbackBuyLow && nearbySupport <= buyHigh
    ? nearbySupport
    : fallbackBuyLow;
  const buyLow = supportedBuyLow && buyHigh
    ? Math.max(fallbackBuyLow, Math.min(supportedBuyLow, buyHigh * 0.992))
    : supportedBuyLow;
  const stopRaw = price && buyLow
    ? Math.min(price * (1 - stopPct / 100), buyLow * 0.992)
    : null;
  const breakoutRaw = price
    ? nearbyResistance
      ? clampNumber(nearbyResistance, price * 1.012, price * 1.025)
      : price * (1 + breakoutPct / 100)
    : null;
  const targetRaw = price ? Math.max(breakoutRaw || 0, price * (1 + targetPct / 100)) : null;
  const buyZone = formatPriceRange(buyLow, buyHigh);
  const stopLine = formatNumber(roundTradePrice(stopRaw));
  const breakoutLine = formatNumber(roundTradePrice(breakoutRaw));
  const firstTarget = formatNumber(roundTradePrice(targetRaw));
  const actionableChartBuy = decision === "분할매수";
  const entryLabel = actionableChartBuy ? "1차 매수가" : "관찰 가격대";
  const summary =
    actionableChartBuy
      ? `${item.name}: ${buyZone}에서 1차 분할매수, ${breakoutLine} 위에서는 추가매수, ${stopLine} 아래는 비중축소입니다.`
      : decision === "매도/축소"
        ? `${item.name}: 현재 차트는 약합니다. 보유 중이면 ${stopLine} 아래에서 비중축소, 신규 매수는 보류입니다.`
        : `${item.name}: 지금은 보류입니다. ${buyZone}은 실행 구간이 아닌 관찰 가격대이고, ${breakoutLine} 위로 강하게 올라설 때만 접근합니다.`;

  const pricePlan = [
    ["현재가", formatNumber(price)],
    [entryLabel, buyZone],
    [actionableChartBuy ? "추가 매수가" : "매수 전환가", breakoutLine],
    ["1차 매도 구간", firstTarget],
    ["손절/축소 기준", stopLine],
    ["판단 신뢰도", confidence],
  ];

  const explanation = [
    `현재 위치: 현재가 ${formatNumber(price)}, 20일선 ${aboveMa20 ? "위" : "아래"}, 60일선 ${aboveMa60 ? "위" : "아래"}, 120일선 ${aboveMa120 ? "위" : "아래"}.`,
    actionableChartBuy
      ? `매수 타이밍: ${buyZone}에서 밀리지 않으면 1차 분할매수, ${breakoutLine} 위에서 거래량이 붙으면 추가매수.`
      : `관찰 기준: ${buyZone}은 바로 사는 구간이 아니라 가격이 무너지지 않는지 보는 구간이고, ${breakoutLine} 위에서 거래량이 붙어야 매수 전환입니다.`,
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

  const scenarios = actionableChartBuy
    ? [
        `1차 매수: ${buyZone}에서 가격이 버티면 소액 분할매수.`,
        `추가 매수: ${breakoutLine} 위에서 거래량이 늘면 비중 추가.`,
        `보류: ${buyZone}과 ${breakoutLine} 사이에서 방향 없이 움직이면 매수하지 않음.`,
        `매도/축소: ${stopLine} 아래로 내려가면 비중 축소.`,
      ]
    : [
        `신규 매수: 보류.`,
        `관찰 가격대: ${buyZone}에서 가격이 버티더라도 거래량이 약하면 매수하지 않음.`,
        `매수 전환: ${breakoutLine} 위에서 거래량이 늘 때만 소액 접근.`,
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
  const keepDetailsOpen = Boolean(panel.querySelector(".chart-ai-detail-disclosure")?.open);
  panel.innerHTML = "";
  const head = el("div", "chart-ai-head");
  const title = el("div");
  title.append(el("h3", "", "AI 차트 분석"), el("span", "", formatDataBasis(new Date().toISOString())));
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
  const details = el("details", "chart-ai-detail-disclosure");
  details.open = keepDetailsOpen;
  const detailsSummary = document.createElement("summary");
  detailsSummary.textContent = "AI 판단 근거 보기";
  details.append(detailsSummary, explanation, grid);
  panel.append(head, summary, pricePlan, details);
  panel.hidden = false;
}

function createWatchChartCard(item, prices, dashboard, chartAnalysis = null) {
  const analysis = chartAnalysis || computeWatchChart(prices);
  const card = el("article", "watch-chart-card");
  const head = el("div", "watch-chart-head");
  const title = el("div");
  const link = el("a", "watch-chart-name", item.name);
  link.href = viewStockUrl(item.name);
  title.append(link, el("span", "", `${item.market || dashboard.market || "국내증시"} · 선택 종목 AI 차트`));
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
    ["현재가", formatNumber(analysis.latest.close)],
    ["5일선", formatNumber(analysis.ma5)],
    ["20일선", formatNumber(analysis.ma20)],
    ["60일선", formatNumber(analysis.ma60)],
    ["120일선", formatNumber(analysis.ma120)],
    ["이격", formatPercent(analysis.distance20)],
    ["지지", formatNumber(analysis.support)],
    ["저항", formatNumber(analysis.resistance)],
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
  const details = el("details", "chart-detail-disclosure");
  const detailsSummary = document.createElement("summary");
  detailsSummary.textContent = "지표와 판단 근거 보기";
  details.append(detailsSummary, metrics, indicators, checklist, notes);
  card.append(head, chartWrap, legend, details);
  return card;
}

function renderWatchChartMessage(title, message = "") {
  elements.watchChartList.innerHTML = "";
  if (isLoadingMessageText(title)) {
    clearWatchChartLoadingOverlay();
    const card = el("article", "watch-chart-empty-card is-loading");
    appendInlineLoadingState(card, PAGE_LOADING_LABELS.chart, message || "완료된 종목부터 순서대로 보여드립니다.");
    elements.watchChartList.appendChild(card);
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
  const spinner = document.createElement("span");
  spinner.className = "inline-loading-spinner";
  spinner.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.textContent = total ? `${formatNumber(done)}/${formatNumber(total)} 확인 중` : "확인 중";
  elements.watchChartMeta.append(spinner, label);
}

function renderWatchChartList(results) {
  clearWatchChartLoadingOverlay();
  state.selectedWatchChartCode = "";
  const available = results.filter((result) => result.dashboard && result.prices?.length && result.analysis);
  if (!available.length) {
    renderWatchChartMessage("차트 데이터를 불러오지 못했습니다.", "잠시 후 다시 들어오거나 종목 카드의 새로고침을 눌러주세요.");
    return;
  }
  renderChartForecastResult(available[0], 5);
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

function renderChartWatchlistPicker(activeCode = "") {
  if (!elements.chartWatchlistPicker) {
    return;
  }
  elements.chartWatchlistPicker.innerHTML = "";
  const items = readWatchlist();
  if (!items.length) {
    elements.chartWatchlistPicker.appendChild(el("p", "muted", "관심종목을 추가하면 여기에서 바로 선택할 수 있습니다."));
    return;
  }
  for (const item of items) {
    const button = el("button", `chart-stock-chip${item.code === activeCode ? " active" : ""}`, item.name);
    button.type = "button";
    button.dataset.code = item.code;
    button.setAttribute("aria-pressed", String(item.code === activeCode));
    button.addEventListener("click", () => void loadChartStock(item));
    elements.chartWatchlistPicker.appendChild(button);
  }
}

async function loadChartStock(stockOrQuery) {
  const query = typeof stockOrQuery === "string" ? stockOrQuery : stockOrQuery?.code || stockOrQuery?.name;
  const stock = typeof stockOrQuery === "object" && stockOrQuery?.code
    ? stockOrQuery
    : await resolveStock(query);
  if (!stock?.code) {
    setWatchChartMetaText("종목을 찾지 못했습니다.");
    renderWatchChartMessage("검색 결과가 없습니다.", "종목명이나 종목코드를 다시 확인해주세요.");
    return;
  }
  if (elements.chartStockSearchInput) {
    elements.chartStockSearchInput.value = stock.name || stock.code;
    elements.chartStockSearchInput.blur();
  }
  window.clearTimeout(state.chartSuggestionTimer);
  state.chartSuggestionController?.abort();
  hideStandaloneSuggestions(elements.chartStockSearchInput, elements.chartStockSearchSuggestions);
  await loadWatchCharts({
    items: [{ code: stock.code, name: stock.name || stock.code, market: stock.market || "" }],
    force: false,
    single: true,
  });
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
    clearCachedUrl(`/stocks/${encodeURIComponent(code)}/prices?limit=260`);
    clearCachedUrl(`/stocks/${encodeURIComponent(code)}/dashboard?include_profile=0&include_live=1`);
    const [prices, dashboard] = await Promise.all([
      fetchJsonCached(liveUrl(`/stocks/${encodeURIComponent(code)}/prices?limit=260`), { force: true, ttlMs: 0 }),
      fetchJsonCached(liveUrl(`/stocks/${encodeURIComponent(code)}/dashboard?include_profile=0&include_live=1`), { force: true, ttlMs: 0 }),
    ]);
    const analysis = prices.length ? attachChartPatterns(computeWatchChart(prices), dashboard) : null;
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
  const loadSequence = ++state.watchChartLoadSequence;
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("chart");
  const items = Array.isArray(options.items) ? normalizeWatchlistItems(options.items) : [];
  renderChartSnapshots();
  elements.watchChartList.innerHTML = "";
  state.watchChartResults = [];
  state.selectedWatchChartCode = "";
  if (!items.length) {
    clearWatchChartLoadingOverlay();
    elements.chartStartGuide?.removeAttribute("hidden");
    return;
  }
  elements.chartStartGuide?.setAttribute("hidden", "");
  renderWatchChartMessage("차트 데이터를 불러오는 중", "실제 가격과 기술 지표를 계산하고 있습니다.");
  showWatchChartLoadingOverlay();
  if (elements.watchChartRefresh) {
    elements.watchChartRefresh.disabled = true;
    elements.watchChartRefresh.textContent = "불러오는 중";
  }
  try {
    const results = await mapWithConcurrency(
      items,
      1,
      async (item) => {
        try {
          const [prices, dashboard] = await Promise.race([
            Promise.all([
              fetchJsonCached(`/stocks/${encodeURIComponent(item.code)}/prices?limit=260`, { force, ttlMs: force ? 0 : ttlMs }),
              fetchJsonCached(liveUrl(`/stocks/${encodeURIComponent(item.code)}/dashboard?include_profile=0&include_live=1`), { force: true, ttlMs: 0 }),
            ]),
            rejectAfter(15_000, "watch chart timeout"),
          ]);
          const result = { item, prices, dashboard, analysis: prices.length ? attachChartPatterns(computeWatchChart(prices), dashboard) : null };
          return result;
        } catch {
          return { item, prices: [], dashboard: null, analysis: null };
        }
      },
      (done, total) => {
        if (loadSequence !== state.watchChartLoadSequence) {
          return;
        }
        if (elements.watchChartRefresh) {
          elements.watchChartRefresh.textContent = `${formatNumber(done)}/${formatNumber(total)}`;
        }
      }
    );
    if (loadSequence !== state.watchChartLoadSequence) {
      return;
    }
    state.watchChartResults = results;
    renderWatchChartList(results);
  } finally {
    if (loadSequence !== state.watchChartLoadSequence) {
      return;
    }
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

function recommendationScoreLevel(value) {
  const score = toNumber(value);
  if (score >= 70) {
    return { label: "우수", guide: "70점 이상", className: "high" };
  }
  if (score >= 55) {
    return { label: "관찰", guide: "55~69점", className: "watch" };
  }
  return { label: "신중", guide: "55점 미만", className: "cautious" };
}

function recommendationScoreDisplay(value) {
  const level = recommendationScoreLevel(value);
  const wrapper = el("div", "recommend-score");
  const valueRow = el("div", "recommend-score-value");
  const help = el("button", "term-help recommend-score-help", "?");
  help.type = "button";
  help.setAttribute("aria-label", "추천 점수 설명");
  help.setAttribute("data-tooltip", RECOMMEND_SCORE_HELP);
  valueRow.append(el("strong", "", formatNumber(value)), el("span", "", "/ 100"), help);
  const levelRow = el("div", `recommend-score-level ${level.className}`);
  levelRow.append(el("b", "", level.label), el("span", "", `· ${level.guide}`));
  wrapper.append(valueRow, levelRow);
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
  elements.aiAnalysisProviderBadge.hidden = true;
  elements.stockSummaryAIBadge.hidden = true;
  elements.aiAnalysisMeta.textContent = "";
  elements.aiAnalysisStance.textContent = "-";
  elements.aiAnalysisSummary.textContent = "";
  setText(elements.aiDecisionStance, "-");
  setText(elements.aiDecisionConfidence, "-");
  setText(elements.aiDecisionEntry, "-");
  setText(elements.aiDecisionCondition, "-");
  setText(elements.aiPrimaryAction, "분석 결과를 불러오는 중입니다.");
  setText(elements.aiPrimaryReason, "현재 흐름과 가격 기준을 확인하고 있습니다.");
  elements.aiKeyPoints.innerHTML = "";
  elements.aiStrategy.innerHTML = "";
  elements.aiRisks.innerHTML = "";
  elements.aiSectionList.innerHTML = "";
  setText(elements.stockStrategyStatus, "AI 분석을 불러오면 현재가 근처의 가격 기준을 표시합니다.");
  setText(elements.stockStrategyStance, "-");
  if (elements.stockPriceLadder) {
    elements.stockPriceLadder.innerHTML = '<p class="muted">전략 가격대 대기 중</p>';
  }
}

function resetQuantSignals(message = "AI 매매신호를 계산하는 중입니다.") {
  state.stockQuantSignals = null;
  state.stockQuantRequestedCode = "";
  if (elements.quantSignalStatus) {
    elements.quantSignalStatus.hidden = false;
    elements.quantSignalStatus.textContent = message;
  }
  if (elements.quantSignalContent) {
    elements.quantSignalContent.hidden = true;
  }
  if (elements.quantSignalChart) {
    elements.quantSignalChart.innerHTML = "";
  }
  if (elements.quantLifecycle) {
    elements.quantLifecycle.innerHTML = "";
  }
  if (elements.quantContextList) {
    elements.quantContextList.innerHTML = "";
  }
}

function quantToneClass(value) {
  const number = toNumber(value);
  if (number === null || number === 0) {
    return "neutral";
  }
  return number > 0 ? "positive" : "negative";
}

function formatQuantActionDate(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) {
    return formatDateLabel(value);
  }
  return `${Number(match[2])}월 ${Number(match[3])}일`;
}

function quantCurrentStatusView(payload) {
  const current = payload.current || {};
  const events = Array.isArray(payload.events) ? payload.events : [];
  const trades = Array.isArray(payload.trades) ? payload.trades : [];
  const latestEvent = events.length ? events[events.length - 1] : null;
  const latestTrade = trades[0] || null;
  const currentPrice = current.price ? `${formatNumber(current.price)}원` : "-";
  const exposure = `${formatNumber(current.model_exposure_percent || 0)}%`;
  const base = {
    tone: "waiting",
    headline: "관망 중",
    next: "현재는 새 매수 신호를 기다리고 있어요.",
    rows: [
      ["현재가", currentPrice, "neutral"],
      ["보유 비중", exposure, "neutral"],
      ["최근 신호", "없음", "neutral"],
    ],
  };

  if (current.action === "entry_pending") {
    return {
      ...base,
      tone: "entry_pending",
      headline: "매수 대기",
      next: "다음 거래일 시가에 AI 전략의 매수로 반영할 예정이에요.",
    };
  }
  if (current.action === "partial_exit_pending") {
    return {
      ...base,
      tone: "partial_exit_pending",
      headline: "일부 매도 대기",
      next: "다음 거래일 시가에 일부 매도로 반영할 예정이에요.",
      rows: [
        ["현재가", currentPrice, "neutral"],
        ["현재 보유", exposure, "neutral"],
        ["보유 수익률", formatPercent(current.unrealized_return), quantToneClass(current.unrealized_return)],
      ],
    };
  }
  if (current.action === "full_exit_pending") {
    return {
      ...base,
      tone: "full_exit_pending",
      headline: "매도 대기",
      next: "다음 거래일 시가에 모두 매도로 반영할 예정이에요.",
      rows: [
        ["현재가", currentPrice, "neutral"],
        ["현재 보유", exposure, "neutral"],
        ["보유 수익률", formatPercent(current.unrealized_return), quantToneClass(current.unrealized_return)],
      ],
    };
  }
  if (current.position_open) {
    const partial = current.action === "partially_exited" || latestEvent?.side === "partial_sell";
    const actionDate = current.partial_exit_date || current.entry_date || latestEvent?.execution_date;
    const actionPrice = current.partial_exit_price || current.entry_price || latestEvent?.price;
    return {
      ...base,
      tone: partial ? "partially_exited" : "holding",
      headline: partial ? "일부 매도" : "보유 중",
      next: current.next_confirmation || "다음 매도 신호를 확인하고 있어요.",
      rows: [
        [partial ? "일부 매도일" : "매수일", formatDateLabel(actionDate), "neutral"],
        [partial ? "일부 매도가" : "매수가", actionPrice ? `${formatNumber(actionPrice)}원` : "-", "neutral"],
        ["현재 수익률", formatPercent(current.unrealized_return), quantToneClass(current.unrealized_return)],
      ],
    };
  }
  if (latestEvent?.side === "sell") {
    const tradeReturn = latestEvent.return_rate ?? latestTrade?.net_return;
    return {
      ...base,
      tone: "exited",
      headline: "매도 완료",
      next: "현재 보유 비중은 0%이며, 다음 매수 신호를 기다리고 있어요.",
      rows: [
        ["매도일", formatDateLabel(latestEvent.execution_date), "neutral"],
        ["매도 가격", `${formatNumber(latestEvent.price)}원`, "neutral"],
        ["해당 매매", formatPercent(tradeReturn), quantToneClass(tradeReturn)],
      ],
    };
  }
  return base;
}

function renderQuantSignalChart() {
  if (!elements.quantSignalChart) {
    return;
  }
  const payload = state.stockQuantSignals;
  const rows = stockPriceRowsWithLiveQuote(state.stockPriceRows, state.currentDashboard?.quote).slice(-260);
  if (!payload || payload.data_state !== "ready" || rows.length < 2) {
    elements.quantSignalChart.innerHTML = '<p class="stock-v3-chart-empty">매매신호 차트를 만들 가격 데이터가 부족합니다.</p>';
    return;
  }

  const width = 760;
  const height = 320;
  const left = 58;
  const right = 18;
  const top = 34;
  const bottom = 268;
  const plotWidth = width - left - right;
  const plotHeight = bottom - top;
  const closes = rows.map((row) => row.close);
  const rawMin = Math.min(...closes);
  const rawMax = Math.max(...closes);
  const rawSpan = rawMax === rawMin ? Math.max(rawMax * 0.02, 1) : rawMax - rawMin;
  const min = Math.max(0, rawMin - rawSpan * 0.14);
  const max = rawMax + rawSpan * 0.14;
  const span = max - min || 1;
  const points = rows.map((row, index) => ({
    x: left + (index / Math.max(1, rows.length - 1)) * plotWidth,
    y: top + ((max - row.close) / span) * plotHeight,
  }));
  const linePath = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x.toFixed(2)} ${bottom} L${points[0].x.toFixed(2)} ${bottom} Z`;
  const yTicks = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3;
    const y = top + ratio * plotHeight;
    const value = max - ratio * span;
    return `<g class="stock-v2-chart-grid"><line x1="${left}" y1="${y.toFixed(2)}" x2="${width - right}" y2="${y.toFixed(2)}"></line><text x="${left - 8}" y="${(y + 4).toFixed(2)}">${formatChartAxisPrice(value)}</text></g>`;
  }).join("");
  const labelIndexes = [0, Math.floor((rows.length - 1) / 2), rows.length - 1];
  const dateLabels = labelIndexes.map((index) => `<text class="stock-v2-chart-date" x="${points[index].x.toFixed(2)}" y="310" text-anchor="${index === 0 ? "start" : index === rows.length - 1 ? "end" : "middle"}">${formatChartDate(rows[index].date)}</text>`).join("");
  const markers = quantSignalMarkers(rows, points);
  const current = payload.current || {};
  const lastPoint = points[points.length - 1];
  const watchMarker = ["entry_pending", "partial_exit_pending", "full_exit_pending"].includes(current.action)
    ? `<g class="quant-chart-marker watch"><circle cx="${lastPoint.x.toFixed(2)}" cy="${lastPoint.y.toFixed(2)}" r="9"></circle><text x="${(lastPoint.x - 5).toFixed(2)}" y="${Math.max(16, lastPoint.y - 16).toFixed(2)}" text-anchor="end">${current.label}</text></g>`
    : "";
  const start = closes[0];
  const end = closes[closes.length - 1];
  const toneClass = end >= start ? "up" : "down";
  elements.quantSignalChart.innerHTML = `
    <svg class="stock-v2-price-svg quant-price-svg ${toneClass}" viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 1년 가격과 전략 포지션 상태 전환">
      ${yTicks}
      <path class="stock-v2-chart-area" d="${areaPath}"></path>
      <path class="stock-v2-chart-line" d="${linePath}"></path>
      ${markers}
      ${watchMarker}
      ${dateLabels}
    </svg>
  `;
  setText(elements.quantChartSource, `최근 1년 · ${formatNumber(rows.length)}거래일`);
}

function renderQuantSignals(payload) {
  state.stockQuantSignals = payload;
  state.stockQuantRequestedCode = payload.code;
  if (elements.quantSignalStatus) {
    elements.quantSignalStatus.hidden = payload.data_state === "ready";
    elements.quantSignalStatus.textContent = payload.data_message || "신호 데이터가 부족합니다.";
  }
  if (!elements.quantSignalContent) {
    return;
  }
  const revealingSignalContent = elements.quantSignalContent.hidden;
  elements.quantSignalContent.hidden = payload.data_state !== "ready";
  if (payload.data_state !== "ready") {
    renderStockMiniChart(state.stockPriceRows, state.currentDashboard?.quote);
    return;
  }

  const performance = payload.performance || {};
  const statusView = quantCurrentStatusView(payload);
  setText(elements.quantCurrentLabel, statusView.headline);
  elements.quantCurrentLabel.className = `quant-current-message quant-action-${statusView.tone}`;
  elements.quantCurrentPosition.innerHTML = statusView.rows
    .map(([label, value, tone]) => `<div><dt>${label}</dt><dd class="${tone || "neutral"}">${value}</dd></div>`)
    .join("");
  setText(elements.quantNextConfirmation, statusView.next);

  setText(
    elements.quantPerformancePeriod,
    performance.period_start && performance.period_end
      ? formatDataBasis(performance.period_end)
      : "최근 1년 기준",
  );
  const performanceRows = [
    ["모의 누적수익률", formatPercent(performance.strategy_return), quantToneClass(performance.strategy_return)],
    ["매매 적중률", performance.win_rate === null || performance.win_rate === undefined ? "-" : `${Number(performance.win_rate).toFixed(1)}%`, "neutral"],
    ["완료 매매", `${formatNumber(performance.completed_trades)}회`, "neutral"],
  ];
  elements.quantPerformanceGrid.innerHTML = performanceRows.map(([label, value, tone]) => `<div><dt>${label}</dt><dd class="${tone}">${value}</dd></div>`).join("");
  setText(elements.quantSampleNote, performance.sample_note || "같은 규칙을 최근 1년 가격에 적용한 결과입니다.");
  elements.quantSampleNote.classList.toggle("limited", performance.sample_state === "limited");
  elements.quantTradeList.innerHTML = "";
  const events = Array.isArray(payload.events) ? payload.events.slice().reverse() : [];
  if (!events.length) {
    elements.quantTradeList.appendChild(el("p", "stock-v3-chart-empty", "최근 1년 매매내역이 없습니다."));
  } else {
    for (const event of events) {
      const row = el("article", "quant-trade-row");
      const actionLabel = event.side === "buy" ? "매수" : event.side === "partial_sell" ? "일부 매도" : "모두 매도";
      const result = event.return_rate === null || event.return_rate === undefined ? "" : formatPercent(event.return_rate);
      const remaining = event.side === "partial_sell" ? "절반 보유" : event.side === "sell" ? "보유 종료" : "보유 시작";
      row.innerHTML = `
        <div><strong>${formatQuantActionDate(event.execution_date)} ${actionLabel}</strong><span>${formatNumber(event.price)}원</span></div>
        <div>${result ? `<strong class="${quantToneClass(event.return_rate)}">${result}</strong>` : ""}<span>${remaining}</span></div>
      `;
      elements.quantTradeList.appendChild(row);
    }
  }
  setText(elements.quantDisclaimer, "AI 전략의 모의 매매 결과이며 실제 계좌 주문이 아닙니다.");
  renderQuantSignalChart();
  renderStockMiniChart(state.stockPriceRows, state.currentDashboard?.quote);
  if (revealingSignalContent && state.stockActiveTab === "strategy") {
    window.requestAnimationFrame(() => scrollStockTabsToTop());
  }
}

async function loadQuantSignals(options = {}) {
  if (!state.currentStock?.code) {
    return;
  }
  const code = state.currentStock.code;
  if (state.stockQuantLoading && state.stockQuantLoadingCode === code) {
    return;
  }
  const forceRefresh = options.force === true;
  const requestSequence = ++state.stockQuantRequestSequence;
  state.stockQuantLoading = true;
  state.stockQuantLoadingCode = code;
  state.stockQuantRequestedCode = code;
  if (elements.quantSignalRefresh) {
    elements.quantSignalRefresh.disabled = true;
    elements.quantSignalRefresh.textContent = "계산 중";
  }
  if (elements.quantSignalStatus) {
    elements.quantSignalStatus.hidden = false;
    elements.quantSignalStatus.textContent = forceRefresh ? "최신 가격으로 AI 매매신호를 다시 계산하는 중입니다." : "AI 매매신호를 계산하는 중입니다.";
  }
  if (elements.quantSignalContent && state.stockQuantRequestedCode !== code) {
    elements.quantSignalContent.hidden = true;
  }
  try {
    const suffix = forceRefresh ? "?refresh=1" : "";
    const payload = await fetchJsonCached(
      liveUrl(`/stocks/${encodeURIComponent(code)}/quant-signals${suffix}`),
      { force: true, ttlMs: 0 },
    );
    if (state.currentStock?.code === code) {
      renderQuantSignals(payload);
      state.stockQuantLastLiveRefreshAt = Date.now();
    }
  } catch {
    if (state.currentStock?.code === code && elements.quantSignalStatus) {
      elements.quantSignalStatus.hidden = false;
      elements.quantSignalStatus.textContent = "AI 매매신호를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
    }
  } finally {
    if (state.stockQuantLoadingCode === code && state.stockQuantRequestSequence === requestSequence) {
      state.stockQuantLoading = false;
      state.stockQuantLoadingCode = "";
      if (elements.quantSignalRefresh) {
        elements.quantSignalRefresh.disabled = false;
        elements.quantSignalRefresh.textContent = "새로고침";
      }
    }
  }
}

function renderAIAnalysis(payload) {
  state.stockAIAnalysis = payload;
  state.stockAIRequestedCode = payload.code;
  elements.aiAnalysisPanel.hidden = false;
  const coverage = aiDataCoverage(payload);
  const isOllamaAnalysis = payload.generation_mode === "local_llm";
  const generationLabel = isOllamaAnalysis ? "Ollama AI" : "데이터 분석";
  const providerTitle = isOllamaAnalysis
    ? `Ollama ${payload.model_name || "로컬 모델"}로 생성된 요약입니다.`
    : "실시간 시세와 정형 데이터 계산 엔진으로 생성된 분석입니다.";
  for (const badge of [elements.aiAnalysisProviderBadge, elements.stockSummaryAIBadge]) {
    badge.hidden = false;
    badge.textContent = generationLabel;
    badge.title = providerTitle;
    badge.classList.toggle("is-ollama", isOllamaAnalysis);
    badge.classList.remove("is-loading");
  }
  elements.stockSummaryAIBadge.textContent = `${generationLabel} 분석 완료`;
  elements.aiAnalysisMeta.textContent = "";
  elements.aiAnalysisMeta.title = payload.generation_note || "";
  elements.aiAnalysisStance.textContent = payload.stance || "-";
  elements.aiAnalysisSummary.textContent = payload.summary || "";
  setText(elements.stockSummaryStance, payload.stance || "-");
  setText(elements.stockSummaryLine, payload.summary || elements.stockSummaryLine?.textContent || "");
  setText(elements.stockSummaryConfidence, coverage);
  setText(elements.stockAISayConfidence, `${generationLabel} · 분석 데이터 ${coverage}`);
  setText(elements.stockAISayText, payload.summary || "AI 분석 요약을 생성하지 못했습니다.");
  const stance = payload.stance || "";
  setTone(elements.aiAnalysisStance, stance.includes("관망") ? -1 : stance.includes("중립") ? 0 : 1);
  renderAIDecisionSummary(payload);
  const primaryAction = String(payload?.strategy?.[0] || payload?.stance || "관찰 우선")
    .replace(/^신규 매수\s*:\s*/, "")
    .trim();
  setText(elements.aiPrimaryAction, primaryAction);
  setText(elements.aiPrimaryReason, payload?.key_points?.[0] || payload?.summary || "현재가와 주요 가격 기준을 함께 확인합니다.");
  appendListItems(elements.aiKeyPoints, payload.key_points, "핵심 판단을 만들 데이터가 부족합니다.");
  const followUpSteps = (payload.strategy || []).slice(1, 4);
  appendListItems(elements.aiStrategy, followUpSteps, "현재는 신규 행동보다 관찰이 우선입니다.");
  appendListItems(elements.aiRisks, payload.risks, "확인할 리스크가 제한적입니다.");
  renderStockStrategyVisual(payload);

  elements.aiSectionList.innerHTML = "";
  for (const section of payload.sections || []) {
    const box = el("section", "ai-section");
    box.appendChild(el("h3", "", section.title));
    const list = el("ul", "ai-list");
    appendListItems(list, section.items, "표시할 내용이 부족합니다.");
    box.appendChild(list);
    elements.aiSectionList.appendChild(box);
  }
}

function setAIAnalysisButtonsLoading(isLoading, labels = {}) {
  if (elements.aiAnalysisButton) {
    elements.aiAnalysisButton.disabled = isLoading;
    elements.aiAnalysisButton.textContent = isLoading ? "분석 중" : labels.main || "AI 분석하기";
  }
  if (elements.stockInlineAIRefresh) {
    elements.stockInlineAIRefresh.disabled = isLoading;
    elements.stockInlineAIRefresh.textContent = isLoading ? "분석 중입니다" : labels.inline || "AI 분석 갱신하기";
  }
}

async function loadAIAnalysis(options = {}) {
  if (!state.currentStock || !state.currentStock.code) {
    return;
  }
  if (state.stockAILoading) {
    return;
  }
  const code = state.currentStock.code;
  const forceRefresh = options.force === true;
  const originalMainText = elements.aiAnalysisButton?.textContent || "AI 분석하기";
  const originalInlineText = elements.stockInlineAIRefresh?.textContent || "AI 분석 갱신하기";
  state.stockAILoading = true;
  for (const badge of [elements.aiAnalysisProviderBadge, elements.stockSummaryAIBadge]) {
    badge.hidden = false;
    badge.textContent = "Ollama AI 분석 중";
    badge.title = "Railway의 Ollama 모델로 핵심 근거를 분석하고 있습니다.";
    badge.classList.add("is-ollama", "is-loading");
  }
  setAIAnalysisButtonsLoading(true);
  elements.aiAnalysisPanel.hidden = false;
  elements.aiAnalysisMeta.textContent = "";
  elements.aiAnalysisStance.textContent = "-";
  elements.aiAnalysisSummary.textContent = "차트, 수급, 밸류에이션, 뉴스, 거시 민감도를 현재 기준으로 다시 정리하는 중입니다.";
  setText(elements.stockAISayText, "현재 시세와 최신 지표를 기준으로 다시 분석하는 중입니다.");
  setText(elements.stockAISayConfidence, "분석 데이터 확인 중");
  elements.aiKeyPoints.innerHTML = "";
  elements.aiStrategy.innerHTML = "";
  elements.aiRisks.innerHTML = "";
  elements.aiSectionList.innerHTML = "";
  const url = `/stocks/${encodeURIComponent(code)}/ai-analysis${forceRefresh ? "?refresh=1" : ""}`;
  if (forceRefresh) {
    clearCachedUrl(url);
  }
  try {
    renderAIAnalysis(await fetchJsonCached(url, { force: forceRefresh, ttlMs: forceRefresh ? 0 : UI_CACHE_TTL_MS }));
  } catch {
    elements.aiAnalysisSummary.textContent = "AI 분석을 생성하지 못했습니다.";
    for (const badge of [elements.aiAnalysisProviderBadge, elements.stockSummaryAIBadge]) {
      badge.hidden = false;
      badge.textContent = "AI 분석 확인 실패";
      badge.title = "분석 서버의 응답을 확인하지 못했습니다.";
      badge.classList.remove("is-loading", "is-ollama");
    }
  } finally {
    state.stockAILoading = false;
    setAIAnalysisButtonsLoading(false, { main: originalMainText, inline: originalInlineText });
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
  elements.recommendHistoryMeta.textContent = tracks.length ? `${formatNumber(tracks.length)}개 종목에 핀 설정됨` : "핀 종목 없음";
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

function recommendationTrackDecisionLabel(value) {
  const text = String(value || "").trim();
  if (!text || /^(?:none|null|nan|undefined|-)$/i.test(text)) {
    return "판단 정보 없음";
  }
  if (text === "보류") {
    return "관찰 우선";
  }
  if (text === "1차 후보") {
    return "관찰 후보";
  }
  return text;
}

function recommendationTrackScoreLabel(value, includeLevel = false) {
  const score = toNumber(value);
  if (score === null) {
    return "점수 정보 없음";
  }
  if (!includeLevel) {
    return `${formatNumber(score)}점 / 100점`;
  }
  const level = recommendationScoreLevel(score);
  return `${formatNumber(score)}점 · ${level.label}`;
}

function sanitizeRecommendationTrackPoint(value) {
  const text = String(value || "").trim();
  if (!text || /^(?:none|null|nan|undefined|-)$/i.test(text)) {
    return "";
  }
  if (/가격 모멘텀 기준 선별/i.test(text) && /(?:none|null|nan|undefined)/i.test(text)) {
    return "1개월·3개월 수익률 데이터가 부족해 최근 가격과 거래대금을 우선 확인합니다.";
  }

  const chartMatch = text.match(/^차트 점수\s*([+-]?[\d,.]+)점,\s*(.+)$/i);
  if (chartMatch) {
    const score = toNumber(chartMatch[1].replaceAll(",", ""));
    const trend = chartMatch[2].replaceAll("/", "·").trim();
    return `차트 흐름은 ${recommendationTrackScoreLabel(score)}이며 ${trend} 상태입니다.`;
  }

  const tradingMatch = text.match(/^거래대금 변화\s*([+-]?[\d,.]+)%\s*반영$/i);
  if (tradingMatch) {
    const change = toNumber(tradingMatch[1].replaceAll(",", ""));
    if (change !== null) {
      return `거래대금은 비교 기준보다 ${formatNumber(Math.abs(change))}% ${change >= 0 ? "늘었습니다" : "줄었습니다"}.`;
    }
  }

  const levelMatch = text.match(/^차트 지지\s*([\d,.]+),\s*저항\s*([\d,.]+)$/i);
  if (levelMatch) {
    const support = toNumber(levelMatch[1].replaceAll(",", ""));
    const resistance = toNumber(levelMatch[2].replaceAll(",", ""));
    if (support !== null && resistance !== null) {
      return `가격 기준선은 지지 ${formatNumber(support)}원 · 저항 ${formatNumber(resistance)}원이었습니다.`;
    }
  }

  return text.replace(/\b(?:None|null|NaN|undefined)\b%?/gi, "데이터 없음");
}

function recommendationPinSummary(track, dashboard, profit) {
  const decision = recommendationTrackDecisionLabel(track.ai?.decision || track.tracked_action);
  if (profit.rate === null) {
    return `현재 가격을 확인 중이며, 핀 시작 당시 판단은 ${decision}이었습니다.`;
  }
  return `핀 설정 후 현재 수익률은 ${formatPercent(profit.rate)}이며, 시작 판단은 ${decision}입니다.`;
}

function recommendationPinHighlights(track, dashboard, profit) {
  const saved = track.item || {};
  const chart = saved.chart_analysis || {};
  const trackedPrice = toNumber(track.tracked_price);
  const currentPrice = toNumber(dashboard?.quote?.price);
  const points = [];

  if (trackedPrice !== null && currentPrice !== null) {
    const direction = profit.rate > 0 ? "상승" : profit.rate < 0 ? "하락" : "변동 없음";
    points.push(`가격은 핀 시작 ${formatNumber(trackedPrice)}원에서 현재 ${formatNumber(currentPrice)}원으로 ${direction}했습니다.`);
  }

  const score = toNumber(track.tracked_score);
  if (score !== null) {
    points.push(`시작 당시 추천 점수는 ${formatNumber(score)}점으로 ${recommendationScoreLevel(score).label} 구간이었습니다.`);
  }

  const support = toNumber(chart.support);
  const resistance = toNumber(chart.resistance);
  if (support !== null || resistance !== null) {
    const levels = [
      support !== null ? `지지 ${formatNumber(support)}원` : "",
      resistance !== null ? `저항 ${formatNumber(resistance)}원` : "",
    ].filter(Boolean).join(" · ");
    points.push(`다음 가격 확인 기준은 ${levels}입니다.`);
  }

  if (points.length < 3) {
    const readableReason = (saved.reasons || []).map(sanitizeRecommendationTrackPoint).find(Boolean);
    if (readableReason) {
      points.push(readableReason);
    }
  }
  return points.slice(0, 3);
}

function setRecommendationTrackExpanded(card, expanded) {
  const detail = card?.querySelector(".recommend-track-detail");
  const toggle = card?.querySelector(".recommend-track-detail-toggle");
  if (!detail || !toggle) {
    return;
  }
  detail.hidden = !expanded;
  const label = toggle.querySelector(".recommend-track-detail-toggle-label");
  const icon = toggle.querySelector(".recommend-track-detail-toggle-icon");
  if (label) {
    label.textContent = expanded ? "핵심 정보 접기" : "핵심 정보 보기";
  }
  if (icon) {
    icon.textContent = expanded ? "−" : "+";
  }
  toggle.setAttribute("aria-expanded", String(expanded));
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

  const head = el("header", "recommend-track-head");
  const open = document.createElement("a");
  open.className = "recommend-track-stock-link";
  open.href = viewStockUrl(track.name || track.code || "");
  open.setAttribute("aria-label", `${track.name || "종목"} 종목 상세 보기`);
  const title = el("span", "recommend-track-title");
  title.append(
    el("strong", "", track.name || "-"),
    el("span", "", `${track.code || "-"} · ${track.market || "-"}`)
  );
  open.append(title);
  const pinState = el("span", "recommend-track-pin-state", "핀 설정됨");
  pinState.setAttribute("aria-label", `${track.name || "종목"} 핀 설정됨`);
  head.append(open, pinState);

  const actions = el("div", "recommend-track-actions");
  const stockDetail = document.createElement("a");
  stockDetail.className = "recommend-track-stock-action";
  stockDetail.href = viewStockUrl(track.name || track.code || "");
  stockDetail.textContent = "종목 상세";
  const remove = el("button", "recommend-track-remove track-delete", "핀 해제하기");
  remove.type = "button";
  remove.dataset.trackId = track.id || "";
  remove.setAttribute("aria-label", `${track.name || "종목"} 핀 해제하기`);
  remove.title = "핀 해제하기";
  actions.append(stockDetail, remove);

  const metrics = document.createElement("dl");
  metrics.className = "recommend-track-metrics";
  const metricRows = [
    ["핀 시작일", track.tracked_at ? formatDateLabel(track.tracked_at).replaceAll("-", ".") : "날짜 정보 없음", "", ""],
    ["핀 시작가", trackedPrice !== null ? `${formatNumber(trackedPrice)}원` : "정보 없음", "", trackedPrice],
    ["현재가", currentPrice !== null ? `${formatNumber(currentPrice)}원` : "확인 중", "tracked_current_price", currentPrice],
    ["수익률", profit.rate !== null ? formatPercent(profit.rate) : "계산 전", "tracked_pnl_rate", profit.rate],
  ];
  for (const [label, value, field, rawValue] of metricRows) {
    const row = el("div");
    const valueNode = el("dd", "", value);
    if (field) {
      valueNode.dataset.field = field;
    }
    if (rawValue !== null && rawValue !== undefined && rawValue !== "") {
      valueNode.dataset.rawValue = String(rawValue);
    }
    if (field === "tracked_pnl_rate") {
      setTone(valueNode, rawValue);
    }
    row.append(el("dt", "", label), valueNode);
    metrics.appendChild(row);
  }

  const signalGrid = document.createElement("dl");
  signalGrid.className = "recommend-track-signals";
  const signalRows = [
    ["시작 판단", recommendationTrackDecisionLabel(track.ai?.decision || track.tracked_action)],
    ["추천 점수", recommendationTrackScoreLabel(track.tracked_score, true)],
    ["차트 점수", recommendationTrackScoreLabel(chart.score)],
  ];
  for (const [label, value] of signalRows) {
    const row = el("div");
    row.append(el("dt", "", label), el("dd", "", value || "정보 없음"));
    signalGrid.appendChild(row);
  }

  const detailToggle = el("button", "recommend-track-detail-toggle");
  detailToggle.type = "button";
  detailToggle.setAttribute("aria-expanded", "false");
  detailToggle.append(
    el("span", "recommend-track-detail-toggle-label", "핵심 정보 보기"),
    el("span", "recommend-track-detail-toggle-icon", "+")
  );

  const detail = el("section", "recommend-track-detail");
  detail.hidden = true;

  const savedInfo = el("section", "recommend-track-saved-info");
  savedInfo.append(el("h3", "", "핀 시작 정보"), signalGrid);

  const summary = el("section", "recommend-track-summary");
  summary.append(
    el("h3", "", "핵심 요약"),
    el("p", "", recommendationPinSummary(track, dashboard, profit))
  );

  const reasons = el("section", "recommend-track-summary");
  reasons.appendChild(el("h3", "", "확인할 것"));
  const reasonList = document.createElement("ul");
  reasonList.className = "recommend-track-points";
  appendListItems(reasonList, recommendationPinHighlights(track, dashboard, profit), "현재 가격과 시작 당시 판단을 다시 확인하세요.");
  reasons.appendChild(reasonList);

  detail.append(savedInfo, summary, reasons);
  card.append(head, metrics, actions, detailToggle, detail);
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
  const pnlRateNode = card.querySelector('[data-field="tracked_pnl_rate"]');
  if (currentPriceNode && quote.price !== null && quote.price !== undefined && quote.price !== "") {
    animateQuoteNumber(currentPriceNode, quote.price, (value) => `${formatNumber(Math.round(Number(value)))}원`);
  }
  const profit = recommendationTrackProfit(trackedPrice, quote.price);
  if (pnlRateNode && profit.rate !== null) {
    animateQuoteNumber(pnlRateNode, profit.rate, formatPercent);
    setLiveCellTone(pnlRateNode, profit.rate);
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
  closeRecommendationQuoteStreams();
  if (!tracks.length) {
    elements.recommendHistoryList.appendChild(el("p", "muted", "추천 종목에서 ‘핀 설정하기’를 누르면 시작일과 이후 수익률을 한곳에서 확인할 수 있습니다."));
    return;
  }
  for (const track of tracks) {
    elements.recommendHistoryList.appendChild(createRecommendationTrackCard(track));
    connectRecommendationQuoteStream(track.code);
  }
  await Promise.all(
    tracks.map(async (track) => {
      try {
        const dashboard = await fetchJsonCached(`/stocks/${encodeURIComponent(track.code)}/dashboard?include_profile=0&include_live=0`, { force, ttlMs: force ? 0 : ttlMs });
        if (state.recommendTrackRequestId !== requestId || state.view !== "portfolio" || state.portfolioTab !== "tracking") {
          return;
        }
        const currentCard = elements.recommendHistoryList.querySelector(`.recommend-track-card[data-code="${selectorEscape(track.code)}"]`);
        if (currentCard) {
          const keepExpanded = !currentCard.querySelector(".recommend-track-detail")?.hidden;
          const nextCard = createRecommendationTrackCard(track, dashboard);
          setRecommendationTrackExpanded(nextCard, keepExpanded);
          currentCard.replaceWith(nextCard);
        }
      } catch {
        return;
      }
    })
  );
}

function setRecommendStatus(message = "") {
  elements.recommendStatus.textContent = message;
  elements.recommendStatus.parentElement.hidden = !message;
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
  const url = `/stocks/${encodeURIComponent(item.code)}/dashboard?refresh=1&include_profile=0`;
  clearCachedUrl(url);
  clearCachedUrl(`/stocks/${encodeURIComponent(item.code)}/dashboard?include_profile=0`);
  try {
    const dashboard = await fetchJsonCached(url, { force: true, ttlMs: 0 });
    const updatedItem = updateRecommendationItemFromDashboard(item, dashboard);
    card.replaceWith(createRecommendationCard(updatedItem));
  } catch {
    button.textContent = "실패";
    window.setTimeout(() => {
      button.disabled = false;
      button.textContent = originalText;
    }, 1200);
  }
}

async function refreshVisibleRecommendationCards(options = {}) {
  const force = options.force === true;
  if (!force || !elements.recommendList) {
    return;
  }
  const cards = Array.from(elements.recommendList.querySelectorAll(".recommend-card"));
  if (!cards.length) {
    return;
  }
  await mapWithConcurrency(cards, 3, async (card) => {
    const item = card.recommendationItem;
    if (!item?.code || !card.isConnected) {
      return;
    }
    try {
      const dashboard = await fetchJsonCached(`/stocks/${encodeURIComponent(item.code)}/dashboard?include_profile=0&include_live=0`, { force: true, ttlMs: 0 });
      const updatedItem = updateRecommendationItemFromDashboard(item, dashboard);
      if (card.isConnected) {
        card.replaceWith(createRecommendationCard(updatedItem));
      }
    } catch {
      return;
    }
  });
}

function buildRecommendationAIExplanation(item) {
  const chart = item.chart_analysis || {};
  const score = toNumber(item.score) ?? 0;
  const price = toNumber(item.price);
  const oneMonth = toNumber(item.one_month_return);
  const threeMonth = toNumber(item.three_month_return);
  const support = toNumber(chart.support);
  const resistance = toNumber(chart.resistance);
  const chartScore = toNumber(chart.score);
  const action = item.action || (score >= 75 && (chartScore === null || chartScore >= 60) ? "분할 접근" : score >= 68 ? "매수 우선검토" : score < 45 ? "신중" : "관찰");
  const entryLow = price ? roundTradePrice(Math.max(support && support < price ? support : 0, price * 0.985)) : null;
  const entryHigh = price ? roundTradePrice(price * 1.005) : null;
  const breakout = price ? roundTradePrice(Math.max(resistance && resistance > price ? resistance : 0, price * 1.025)) : null;
  const reduce = price ? roundTradePrice(Math.max(support ? support * 0.985 : 0, price * 0.965)) : null;
  const reason = item.decision_reason || (
    action === "분할 접근"
      ? "후보 점수와 차트가 모두 우수해 추격하지 않고 가격을 나눠 확인합니다."
      : action === "매수 우선검토"
        ? "점수와 차트가 기준을 통과해 진입 가격 확인이 우선입니다."
        : action === "신중"
          ? "점수 또는 차트가 기준에 못 미쳐 신규 진입보다 위험 확인이 우선입니다."
          : "후보 점수는 확인됐지만 추가 전환 신호를 기다립니다."
  );
  return {
    decision: action,
    summary: reason,
    entryLow,
    entryHigh,
    breakout,
    reduce,
    score,
    chartScore,
    oneMonth,
    threeMonth,
  };
}

function saveRecommendationDetailItem(item) {
  state.currentRecommendationDetailItem = item;
  try {
    sessionStorage.setItem("recommendation-detail-v1", JSON.stringify(item));
  } catch {
    return;
  }
}

function readRecommendationDetailItem(code = "") {
  if (state.currentRecommendationDetailItem && (!code || state.currentRecommendationDetailItem.code === code)) {
    return state.currentRecommendationDetailItem;
  }
  try {
    const item = JSON.parse(sessionStorage.getItem("recommendation-detail-v1") || "null");
    return item && (!code || item.code === code) ? item : null;
  } catch {
    return null;
  }
}

function recommendationDetailMetric(label, value, rawValue = null) {
  const row = el("div", "recommend-detail-metric");
  const strong = el("strong", "", value);
  if (rawValue !== null) {
    setTone(strong, rawValue);
  }
  row.append(el("span", "", label), strong);
  return row;
}

function renderRecommendationDetail(item, aiAnalysis = null, loading = false) {
  if (!elements.recommendDetailContent || !item) {
    return;
  }
  const explanation = buildRecommendationAIExplanation(item);
  const level = recommendationScoreLevel(item.score);
  const generationMode = aiAnalysis?.generation_mode || "";
  const providerText = loading
    ? "Ollama AI 분석 중"
    : generationMode === "local_llm"
      ? "Ollama AI 분석 완료"
      : aiAnalysis
        ? "데이터 분석 완료"
        : "Ollama AI 대기";
  const providerClass = generationMode === "local_llm" ? "local" : generationMode === "rules" ? "rules" : "loading";
  const aiSummary = aiAnalysis?.summary || explanation.summary;

  elements.recommendDetailName.textContent = item.name || "추천 종목";
  elements.recommendDetailCode.textContent = [item.code, item.market].filter(Boolean).join(" · ");
  elements.recommendDetailContent.innerHTML = "";

  const hero = el("section", "recommend-detail-hero");
  const heroHead = el("div", "recommend-detail-hero-head");
  const titleWrap = el("div");
  titleWrap.append(el("span", "recommend-detail-eyebrow", "추천 결과"), el("h1", "", explanation.decision));
  const scoreWrap = el("div", `recommend-detail-score ${level.className}`);
  scoreWrap.append(el("strong", "", formatNumber(item.score)), el("span", "", "/ 100"), el("em", "", level.label));
  heroHead.append(titleWrap, scoreWrap);
  hero.append(heroHead, el("p", "recommend-detail-lead", explanation.summary));

  const action = el("section", "recommend-detail-section recommend-detail-action");
  const actionHead = el("div", "recommend-detail-section-head");
  actionHead.append(el("div", "", "지금 할 일"), el("span", `recommend-detail-ai-badge ${providerClass}`, providerText));
  action.append(actionHead);
  const actionText =
    explanation.decision === "분할 접근"
      ? `${formatPriceRange(explanation.entryLow, explanation.entryHigh)}에서 2~3회로 나눠 접근합니다.`
      : explanation.decision === "매수 우선검토"
        ? `${formatPriceRange(explanation.entryLow, explanation.entryHigh)}에서 가격이 버티는지 먼저 확인합니다.`
        : explanation.decision === "신중"
          ? "신규 진입은 미루고 차트와 수급이 회복되는지 확인합니다."
          : "현재 가격을 따라가지 말고 전환 신호를 기다립니다.";
  action.append(el("h2", "", actionText), el("p", "", aiSummary));

  const levels = el("section", "recommend-detail-section");
  levels.appendChild(el("h2", "", "가격 기준"));
  const levelGrid = el("div", "recommend-detail-table");
  levelGrid.append(
    recommendationDetailMetric("현재가", formatNumber(item.price)),
    recommendationDetailMetric("접근 구간", formatPriceRange(explanation.entryLow, explanation.entryHigh)),
    recommendationDetailMetric("매수 전환", explanation.breakout ? `${formatNumber(explanation.breakout)} 이상` : "확인 중"),
    recommendationDetailMetric("위험 관리", explanation.reduce ? `${formatNumber(explanation.reduce)} 아래` : "확인 중"),
  );
  levels.appendChild(levelGrid);

  const snapshot = el("section", "recommend-detail-section");
  snapshot.appendChild(el("h2", "", "판단에 쓴 핵심 수치"));
  const snapshotGrid = el("div", "recommend-detail-table");
  snapshotGrid.append(
    recommendationDetailMetric("추천 점수", `${formatNumber(item.score)}점`, item.score),
    recommendationDetailMetric("차트 점수", explanation.chartScore === null ? "-" : `${formatNumber(explanation.chartScore)}점`, explanation.chartScore),
    recommendationDetailMetric("1개월", formatPercent(item.one_month_return), item.one_month_return),
    recommendationDetailMetric("3개월", formatPercent(item.three_month_return), item.three_month_return),
  );
  snapshot.appendChild(snapshotGrid);

  const evidence = el("section", "recommend-detail-section");
  evidence.appendChild(el("h2", "", "세부 근거"));
  const columns = el("div", "recommend-detail-evidence");
  for (const [title, values, fallback] of [
    ["긍정 근거", item.reasons, "확인된 긍정 근거가 부족합니다."],
    ["주의할 점", item.risks, "두드러진 위험 신호는 없습니다."],
  ]) {
    const column = el("section");
    column.appendChild(el("h3", "", title));
    const list = document.createElement("ul");
    appendListItems(list, (values || []).slice(0, 5), fallback);
    column.appendChild(list);
    columns.appendChild(column);
  }
  evidence.appendChild(columns);

  const source = el("p", "recommend-detail-source", generationMode === "local_llm"
    ? `${aiAnalysis.model_name || "Ollama"}가 핵심 근거를 선택했고, 점수와 가격 기준은 데이터 규칙으로 계산했습니다.`
    : aiAnalysis?.generation_note || "점수와 가격 기준은 수집된 시장 데이터 규칙으로 계산합니다.");

  elements.recommendDetailContent.append(hero, action, levels, snapshot, evidence, source);
}

async function loadRecommendationDetail(code = "") {
  window.scrollTo(0, 0);
  let item = readRecommendationDetailItem(code);
  if (!item && code) {
    try {
      const payload = await fetchJsonCached("/market/recommendations?limit=20&candidate_limit=100", { force: true, ttlMs: 0 });
      item = (payload.items || []).find((candidate) => candidate.code === code) || null;
    } catch {
      item = null;
    }
  }
  if (!item) {
    elements.recommendDetailContent.replaceChildren(el("p", "muted", "추천 정보를 찾지 못했습니다. 추천 목록에서 다시 선택해주세요."));
    return;
  }
  saveRecommendationDetailItem(item);
  renderRecommendationDetail(item, null, true);
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => window.scrollTo(0, 0)));
  try {
    const aiAnalysis = await fetchJsonCached(`/stocks/${encodeURIComponent(item.code)}/ai-analysis`, { force: true, ttlMs: 0 });
    renderRecommendationDetail(item, aiAnalysis, false);
  } catch {
    renderRecommendationDetail(item, { generation_mode: "rules", generation_note: "Ollama 연결을 확인하지 못해 데이터 분석으로 표시합니다." }, false);
  }
}

function openRecommendationDetail(item) {
  if (!item?.code) {
    return;
  }
  saveRecommendationDetailItem(item);
  window.scrollTo(0, 0);
  setView("recommend-detail");
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
  const card = el("article", "recommend-card");
  card.dataset.code = item.code || "";
  card.recommendationItem = item;
  const head = el("div", "recommend-head");
  const actionText = item.action || "관찰";
  const rank = el("div", "recommend-rank", `#${item.rank} · ${actionText}`);
  rank.classList.add(actionText.includes("매수") || actionText.includes("분할") ? "buy" : "watch");
  const rankLine = el("div", "recommend-rank-line");
  const trackButton = el("button", "recommend-track-button", isTrackedRecommendation(item.code) ? "핀 종목 보기" : "핀 설정하기");
  trackButton.type = "button";
  trackButton.dataset.code = item.code || "";
  trackButton.classList.toggle("active", isTrackedRecommendation(item.code));
  const watchButton = el("button", "recommend-watch-button", isWatched(item.code) ? "관심 해제" : "관심 추가");
  watchButton.type = "button";
  watchButton.dataset.code = item.code || "";
  watchButton.classList.toggle("active", isWatched(item.code));
  const explainButton = el("button", "recommend-ai-button", "AI 상세 보기");
  explainButton.type = "button";
  rankLine.appendChild(rank);
  const name = el("a", "recommend-name");
  name.href = viewStockUrl(item.name);
  name.append(
    createStockListLogo(item.code),
    createStockListCopy(item.name, item.code, item.market)
  );

  const score = recommendationScoreDisplay(item.score);

  const metrics = el("div", "recommend-metrics");
  const metricRows = [
    ["현재가", formatNumber(item.price), "recommend_price", item.price],
    ["등락률", formatPercent(item.change_rate), "recommend_change_rate", item.change_rate],
    ["1개월", formatPercent(item.one_month_return), "recommend_one_month", item.one_month_return],
    ["3개월", formatPercent(item.three_month_return), "recommend_three_month", item.three_month_return],
    ["거래대금", formatMoney(item.trading_value), "recommend_trading_value", item.trading_value],
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
    if (label === "등락률") {
      setTone(valueNode, rawValue);
    }
    row.append(recommendTermLabel(label), valueNode);
    metrics.appendChild(row);
  }
  const actions = el("div", "recommend-card-actions");
  actions.append(watchButton, trackButton, explainButton);
  head.append(rankLine, name, score, metrics, createRecommendationUsSectorSummary(item), actions);
  card.append(head);
  return card;
}

function appendRecommendationCard(item) {
  elements.recommendList.appendChild(createRecommendationCard(item));
}

function renderRecommendations(payload, options = {}) {
  closeRecommendationQuoteStreams();
  if (options.usSectorMoves) {
    state.usSectorMoves = options.usSectorMoves;
  }
  const rankedItems = rerankRecommendationItems(payload.items || []);
  const normalizedPayload = {
    ...payload,
    items: rankedItems,
  };
  if (options.save) {
    saveRecommendationSnapshot(normalizedPayload);
  }
  updateRecommendationTrackMeta();
  const recommendMetaText = payload.as_of ? formatDataBasis(payload.as_of) : "";
  elements.recommendMeta.textContent = recommendMetaText;
  elements.recommendMeta.hidden = !recommendMetaText;
  setRecommendStatus("");
  elements.recommendList.innerHTML = "";
  const items = rankedItems.slice(0, RECOMMENDATION_LIMIT);
  if (items.length === 0) {
    setRecommendStatus("추천 후보를 찾지 못했습니다.");
    return;
  }
  for (const item of items) {
    appendRecommendationCard(item);
    connectRecommendationQuoteStream(item.code);
  }
  scheduleUsSectorRefresh(state.usSectorMoves);
}

function appendTags(parent, items) {
  for (const item of items || []) {
    parent.appendChild(el("span", "tag", item));
  }
}

function setTrendTab(tabName) {
  const active = ["live", "events", "impact"].includes(tabName) ? tabName : "live";
  state.activeTrendTab = active;
  if (elements.trendTabsWrap) {
    elements.trendTabsWrap.hidden = false;
  }
  for (const tab of elements.trendTabs) {
    const selected = tab.dataset.trendTab === active;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  }
  elements.trendEventsPanel.hidden = active !== "events";
  elements.trendLivePanel.hidden = active !== "live";
  elements.trendImpactPanel.hidden = active !== "impact";
  elements.trendPastPanel.hidden = active !== "events" || !state.showPastEvents;
  if (elements.homePastToggle) {
    elements.homePastToggle.setAttribute("aria-expanded", String(active === "events" && state.showPastEvents));
    elements.homePastToggle.textContent = state.showPastEvents ? "지난 이벤트 닫기" : "지난 이벤트";
  }
  return active;
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
  const leaderStocks = (item.leader_stocks || []).slice(0, 4);
  const leaders = el("div", "thread-leader-stocks");
  for (const stock of leaderStocks) {
    leaders.appendChild(el("span", "thread-tag leader-stock-tag", stock));
  }
  node.append(meta, title, tags);
  if (leaderStocks.length) {
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

function trendWatchNewsImpact(item = {}) {
  if (["호재", "악재", "중립"].includes(item.impact)) {
    return item.impact;
  }
  const title = String(item.title || "");
  if (/(상향|호조|개선|증가|최대|수주|흑자|서프라이즈|강세|성장|돌파)/i.test(title)) {
    return "호재";
  }
  if (/(하향|부진|감소|적자|쇼크|약세|하락|악화|손실|둔화)/i.test(title)) {
    return "악재";
  }
  return "중립";
}

function renderTrendWatchStockRail(items, activeCode) {
  elements.trendWatchStockRail.innerHTML = "";
  for (const item of items) {
    const selected = item.code === activeCode;
    const button = el("button", `trend-watch-stock-chip${selected ? " active" : ""}`, item.name);
    button.type = "button";
    button.dataset.code = item.code;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(selected));
    elements.trendWatchStockRail.appendChild(button);
  }
}

function appendTrendWatchNewsGroup(parent, label, items, tone) {
  const group = el("section", `trend-watch-news-group ${tone}`);
  const heading = el("div", "trend-watch-news-group-head");
  heading.append(el("h3", "", label), el("span", "", `${formatNumber(items.length)}건`));
  group.appendChild(heading);
  if (!items.length) {
    group.appendChild(el("p", "trend-watch-news-empty", `${label} 뉴스 없음`));
  } else {
    for (const item of items) {
      const node = document.createElement(item.url ? "a" : "article");
      node.className = "trend-watch-news-item";
      if (item.url) {
        node.href = item.url;
        node.target = "_blank";
        node.rel = "noreferrer";
      }
      node.append(
        el("strong", "", item.title || "제목 없음"),
        el("span", "", `${item.source || "출처 확인 중"} · ${formatDate(item.published_at)}`),
      );
      group.appendChild(node);
    }
  }
  parent.appendChild(group);
}

function renderTrendWatchNews(item, dashboard) {
  const sentiment = dashboard?.sentiment || {};
  const seenNews = new Set();
  const seenTitles = new Set();
  const latestItems = (sentiment.latest_items || []).filter((news) => {
    if (!news?.title || news.title === "최근 종목 뉴스 없음") {
      return false;
    }
    const normalizedTitle = String(news.title).replace(/\s+/g, " ").trim().toLocaleLowerCase("ko-KR");
    const key = news.url || `${news.title}|${news.source || ""}|${news.published_at || ""}`;
    if (seenNews.has(key) || seenTitles.has(normalizedTitle)) {
      return false;
    }
    seenNews.add(key);
    seenTitles.add(normalizedTitle);
    return true;
  });
  const positiveItems = latestItems.filter((news) => trendWatchNewsImpact(news) === "호재");
  const negativeItems = latestItems.filter((news) => trendWatchNewsImpact(news) === "악재");
  const neutralItems = latestItems.filter((news) => trendWatchNewsImpact(news) === "중립");
  elements.trendWatchlistMeta.textContent = `${item.name} · 호재 ${formatNumber(sentiment.positive_count || 0)} · 악재 ${formatNumber(sentiment.negative_count || 0)}`;
  elements.trendWatchlistStatus.textContent = "";
  elements.trendWatchNewsBoard.innerHTML = "";
  appendTrendWatchNewsGroup(elements.trendWatchNewsBoard, "호재", positiveItems.slice(0, 2), "positive");
  appendTrendWatchNewsGroup(elements.trendWatchNewsBoard, "악재", negativeItems.slice(0, 2), "negative");
  if (neutralItems.length) {
    appendTrendWatchNewsGroup(elements.trendWatchNewsBoard, "판단 보류", neutralItems.slice(0, 1), "neutral");
  }
}

async function loadTrendWatchlistNews(options = {}) {
  const items = readWatchlist();
  elements.trendWatchNewsBoard.innerHTML = "";
  if (!items.length) {
    state.selectedTrendWatchCode = "";
    elements.trendWatchStockRail.innerHTML = "";
    elements.trendWatchlistMeta.textContent = "관심종목 0개";
    elements.trendWatchlistStatus.textContent = "관심종목을 추가하면 종목별 최신 뉴스가 표시됩니다.";
    return;
  }
  const requestedCode = String(options.code || state.selectedTrendWatchCode || "");
  const selected = items.find((item) => item.code === requestedCode) || items[0];
  state.selectedTrendWatchCode = selected.code;
  renderTrendWatchStockRail(items, selected.code);
  elements.trendWatchlistMeta.textContent = `${formatNumber(items.length)}개 종목`;
  elements.trendWatchlistStatus.textContent = `${selected.name} 뉴스를 불러오는 중입니다.`;
  const requestId = ++state.trendWatchRequestId;
  try {
    const force = options.force === true;
    const url = `/stocks/${encodeURIComponent(selected.code)}/dashboard?include_profile=0&include_live=0`;
    const dashboard = await fetchJsonCached(url, { force, ttlMs: force ? 0 : PAGE_ENTRY_MINUTE_MS });
    if (requestId !== state.trendWatchRequestId) {
      return;
    }
    renderTrendWatchNews(selected, dashboard);
  } catch {
    if (requestId !== state.trendWatchRequestId) {
      return;
    }
    elements.trendWatchlistMeta.textContent = selected.name;
    elements.trendWatchlistStatus.textContent = "종목 뉴스를 불러오지 못했습니다.";
  }
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

function isFocusedTrendTimelineItem(item) {
  const text = `${item.title || ""} ${item.category || ""} ${item.related_event || ""}`;
  return /(원유|유가|WTI|브렌트|정제마진|환율|원달러|원\/달러|고환율|원화|달러\s*(강세|약세)|금리|고용|실업|신규실업수당|PCE|FOMC|연준)/i.test(text);
}

function hasAnyKeyword(text, keywords = []) {
  const lowerText = String(text || "").toLowerCase();
  return keywords.some((keyword) => lowerText.includes(String(keyword).toLowerCase()));
}

function uniqueLimited(items = [], limit = 6) {
  return Array.from(new Set((items || []).filter(Boolean))).slice(0, limit);
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
  if (/(호재|수혜|개선|완화|안정|강세 기대|부담 완화|비용 완화|수급 개선)/i.test(text)) {
    score += 1;
  }
  if (/(악재|부담|압박|약화|불안|위험|급등|급락|이탈|매도|비용 부담|물가 부담)/i.test(text)) {
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
        reasons: uniqueLimited(factor.reasons, 3),
        stocks: uniqueLimited(factor.stocks, 6),
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

function appendMarketImpactFactorRow(parent, factor, index) {
  const direction = factor.direction || factor.status || "악재";
  const percent = Math.max(0, Math.min(100, Number(factor.percent || 0)));
  const row = el(
    "article",
    `market-impact-factor-row ${direction === "호재" ? "good" : "bad"}${index === 0 ? " is-leading" : ""}`,
  );
  row.setAttribute("aria-label", `${factor.label} 영향도 ${percent.toFixed(1)}%, ${direction}`);

  const head = el("div", "market-impact-factor-head");
  const name = el("div", "market-impact-factor-name");
  name.append(el("span", "market-impact-factor-rank", String(index + 1).padStart(2, "0")), el("strong", "", factor.label));
  const value = el("div", "market-impact-factor-value");
  value.append(el("strong", "", `${percent.toFixed(1)}%`), el("span", direction === "호재" ? "good" : "bad", direction));
  head.append(name, value);

  const track = el("div", "market-impact-factor-track");
  track.setAttribute("aria-hidden", "true");
  const fill = el("span", "market-impact-factor-fill");
  fill.style.setProperty("--factor-width", `${percent}%`);
  track.appendChild(fill);
  row.append(head, track);
  parent.appendChild(row);
}

function isMarketImpactFactorFallback(factor) {
  const evidence = Array.isArray(factor?.evidence) ? factor.evidence : [];
  return evidence.some((item) => item?.source === "시스템") || Number(factor?.confidence || 0) <= 20;
}

function marketImpactLearningGuide(factor) {
  return MARKET_IMPACT_LEARNING_GUIDES[factor?.key] || {
    lesson: factor?.interpretation || factor?.summary || "외부 변수가 국내증시에 전달되는 경로를 확인합니다.",
    metrics: "공식 지표 연결 대기 중",
  };
}

function appendMarketImpactDetail(parent, factor) {
  const direction = factor.direction || factor.status || "악재";
  const fallback = isMarketImpactFactorFallback(factor);
  const guide = marketImpactLearningGuide(factor);
  const card = el("article", `market-impact-detail ${direction === "호재" ? "good" : "bad"}`);
  const head = el("div", "market-impact-detail-head");
  head.append(
    el("strong", "", factor.label),
    el("em", direction === "호재" ? "good" : "bad", `${direction} ${factor.percent.toFixed(1)}%`),
  );
  const summary = el("p", "", fallback ? guide.lesson : (factor.interpretation || factor.summary || "현재 공식 지표 기준으로 영향 방향을 계산했습니다."));
  const evidenceList = el("div", "market-impact-source-list");
  if (fallback) {
    const learning = el("div", "market-impact-source market-impact-learning-note");
    learning.append(
      el("span", "", "확인할 공식 지표"),
      el("strong", "", guide.metrics),
    );
    evidenceList.appendChild(learning);
  } else {
    for (const item of (factor.evidence || []).slice(0, 2)) {
      const metric = el("a", "market-impact-source");
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
      evidenceList.appendChild(metric);
    }
  }
  if (!evidenceList.childElementCount) {
    evidenceList.appendChild(el("p", "muted", "공식 지표 수집 대기 중"));
  }
  const keywordGroups = el("div", "market-impact-keyword-groups");
  const sectorWrap = el("div", "market-impact-keyword-group");
  sectorWrap.appendChild(el("span", "", "영향 업종"));
  const sectors = el("div", "market-impact-keyword-rail");
  for (const sector of factor.affected_sectors || []) {
    sectors.appendChild(el("span", "", sector));
  }
  sectorWrap.appendChild(sectors);
  const stockWrap = el("div", "market-impact-keyword-group");
  stockWrap.appendChild(el("span", "", "대표 종목"));
  const stocks = el("div", "market-impact-keyword-rail");
  for (const stock of factor.leader_stocks || factor.stocks || []) {
    const tag = el("a", "", stock);
    tag.href = viewStockUrl(stock);
    stocks.appendChild(tag);
  }
  stockWrap.appendChild(stocks);
  if (sectors.childElementCount) {
    keywordGroups.appendChild(sectorWrap);
  }
  if (stocks.childElementCount) {
    keywordGroups.appendChild(stockWrap);
  }
  card.append(head, summary, evidenceList, keywordGroups);
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
      summary: payload.summary || "외부 요인의 국내증시 영향도를 계산했습니다.",
    };
  }
  return buildMarketImpactModel(payload);
}

function isFallbackMarketImpact(model) {
  return Array.isArray(model?.factors) && model.factors.length > 0 && model.factors.every((factor) => {
    const source = Array.isArray(factor.evidence) && factor.evidence[0] ? factor.evidence[0].source : "";
    return source === "시스템" || Number(factor.confidence || 0) <= 20;
  });
}

function restoreTrendChrome(activeTab = "live") {
  if (elements.trendTopbar) {
    elements.trendTopbar.hidden = true;
  }
  if (elements.trendTitle) {
    elements.trendTitle.textContent = "시장 홈";
  }
  if (elements.trendTabsWrap) {
    elements.trendTabsWrap.hidden = false;
  }
  if (elements.trendEventsTitle) {
    elements.trendEventsTitle.hidden = false;
    elements.trendEventsTitle.textContent = "이벤트 캘린더";
  }
}

const HOME_MARKET_ASSET_ORDER = ["KOSDAQ", "KOSPI", "NASDAQ", "SP500", "GOLD", "OIL"];

function formatMarketIndexValue(value) {
  const number = toNumber(value);
  return number === null
    ? "-"
    : number.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function marketIndexChartMarkup(item) {
  const points = Array.isArray(item?.points)
    ? item.points.map((point) => toNumber(point?.value)).filter((value) => value !== null)
    : [];
  if (points.length < 2) {
    return "";
  }
  const width = 320;
  const height = 96;
  const top = 7;
  const bottom = 7;
  const minimum = Math.min(...points);
  const maximum = Math.max(...points);
  const range = Math.max(maximum - minimum, Math.abs(maximum || 1) * 0.002);
  const coordinates = points.map((value, index) => {
    const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
    const y = top + ((maximum - value) / range) * (height - top - bottom);
    return [x, y];
  });
  const line = coordinates.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
  const area = `${line} L${width} ${height} L0 ${height} Z`;
  const key = String(item.code || "index").toLowerCase();
  const previous = toNumber(item?.previous_close) ?? points[0];
  const current = toNumber(item?.current) ?? points.at(-1);
  const change = toNumber(item?.change) ?? (current - previous);
  const chartTone = change < 0 ? "negative" : change > 0 ? "positive" : "neutral";
  const chartColor = chartTone === "negative" ? "#2388e8" : chartTone === "positive" ? "#ef3e43" : "#8d97a4";
  const gradientId = `home-index-gradient-${chartTone}-${key}`;
  const baselineY = Math.max(top, Math.min(height - bottom, top + ((maximum - previous) / range) * (height - top - bottom)));
  return `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="${gradientId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${chartColor}" stop-opacity="0.18"></stop>
          <stop offset="100%" stop-color="${chartColor}" stop-opacity="0.02"></stop>
        </linearGradient>
      </defs>
      <line class="home-index-baseline" x1="0" y1="${baselineY.toFixed(2)}" x2="${width}" y2="${baselineY.toFixed(2)}"></line>
      <path class="home-index-area home-index-area-${chartTone}" d="${area}" fill="url(#${gradientId})"></path>
      <path class="home-index-line home-index-line-${chartTone}" d="${line}"></path>
    </svg>`;
}

function createHomeMarketAssetCard(item = {}) {
  const card = document.createElement("article");
  const code = String(item.code || "MARKET");
  const current = toNumber(item?.current);
  const change = toNumber(item?.change);
  const changeRate = toNumber(item?.change_rate);
  const tone = change === null || change === 0 ? "neutral" : change > 0 ? "positive" : "negative";
  card.className = `home-index-card ${tone}${current === null ? " is-empty" : ""}`;
  card.dataset.code = code;

  const header = document.createElement("header");
  header.append(el("h2", "", item.label || code));

  const value = el("strong", "home-index-current", formatMarketIndexValue(current));
  const changeNode = el("span", "home-index-change");
  if (change === null) {
    changeNode.append(el("span", "home-index-change-value", "전일 대비 -"));
  } else {
    changeNode.append(
      el(
        "span",
        "home-index-change-value",
        `${change > 0 ? "▲" : change < 0 ? "▼" : "-"} ${formatMarketIndexValue(Math.abs(change))}`,
      ),
      el("span", "home-index-change-rate", formatPercent(changeRate)),
    );
  }

  const chartNode = el("div", "home-index-chart");
  const chart = marketIndexChartMarkup(item);
  if (chart) {
    chartNode.innerHTML = chart;
  } else {
    chartNode.append(el("span", "", "시세 확인 중"));
  }
  const label = item?.label || code;
  chartNode.setAttribute("role", "img");
  chartNode.setAttribute(
    "aria-label",
    current === null
      ? `${label} 시세 데이터 없음`
      : `${label} ${formatMarketIndexValue(current)}, 전일 대비 ${change === null ? "확인 불가" : `${formatMarketIndexValue(Math.abs(change))} ${change >= 0 ? "상승" : "하락"}`}`,
  );

  const basisNode = el("p", "home-index-basis");
  const basis = formatDataBasis(item.updated_at || item.as_of, "").replace(/ 기준$/, "");
  const session = el("span", "home-index-session", item.is_realtime ? "실시간" : "장마감");
  session.classList.toggle("is-realtime", Boolean(item.is_realtime));
  basisNode.append(el("time", "", basis || "기준 정보 확인 중"), session);
  card.append(header, value, changeNode, chartNode, basisNode);
  return card;
}

function renderHomeMarketIndices(payload = {}) {
  if (!elements.homeMarketCarousel) {
    return;
  }
  const items = Array.isArray(payload.items) ? payload.items : [];
  state.homeMarketIndexItems = items;
  const byCode = new Map(items.map((item) => [item.code, item]));
  elements.homeMarketCarousel.replaceChildren();
  HOME_MARKET_ASSET_ORDER.forEach((code) => {
    const fallbackLabels = { KOSDAQ: "코스닥", KOSPI: "코스피", NASDAQ: "나스닥", SP500: "S&P 500", GOLD: "금", OIL: "원유" };
    elements.homeMarketCarousel.appendChild(createHomeMarketAssetCard(byCode.get(code) || { code, label: fallbackLabels[code] }));
  });
  const timestamps = [
    payload.updated_at,
    ...items.map((item) => item?.updated_at),
  ].map((value) => String(value || "")).filter(Boolean).sort();
  const dates = [...new Set(items.map((item) => String(item?.as_of || "")).filter(Boolean))].sort();
  if (elements.homeIndexSharedAsOf) {
    elements.homeIndexSharedAsOf.textContent = timestamps.length
      ? formatDataBasis(timestamps[timestamps.length - 1])
      : dates.length === 0
      ? "기준 정보 확인 중"
      : formatDataBasis(dates[dates.length - 1]);
  }
  renderHomeAiResponse(state.aiSignalItems, payload.updated_at || "");
}

function setHomeMarketIndicesLoading() {
  if (!elements.homeMarketCarousel) {
    return;
  }
  elements.homeMarketCarousel.replaceChildren();
  HOME_MARKET_ASSET_ORDER.forEach((code) => {
    const card = createHomeMarketAssetCard({ code, label: "시장 확인 중" });
    card.classList.add("is-loading");
    elements.homeMarketCarousel.appendChild(card);
  });
}

async function loadHomeMarketIndices(options = {}) {
  if (!elements.homeMarketIndices) {
    return;
  }
  if (!options.silent) {
    setHomeMarketIndicesLoading();
  }
  try {
    const refreshHistory = options.refreshHistory === true;
    const domesticEndpoint = `/market/indices?limit=30${refreshHistory ? "&refresh=true" : ""}`;
    const [domesticResult, globalResult] = await Promise.allSettled([
      fetchJsonCached(liveUrl(domesticEndpoint), { force: true, ttlMs: 0 }),
      fetchJsonCached(liveUrl("/market/global-assets?limit=30"), { force: true, ttlMs: 0 }),
    ]);
    const domesticPayload = domesticResult.status === "fulfilled" ? domesticResult.value : {};
    const globalPayload = globalResult.status === "fulfilled" ? globalResult.value : {};
    const mergedItems = [
      ...(Array.isArray(domesticPayload.items) ? domesticPayload.items : []),
      ...(Array.isArray(globalPayload.items) ? globalPayload.items : []),
    ];
    renderHomeMarketIndices({
      items: mergedItems,
      updated_at: [domesticPayload.updated_at, globalPayload.updated_at].filter(Boolean).sort().at(-1) || null,
    });
    if (state.view === "home") {
      startHomeMarketIndexRefresh();
    }
  } catch {
    if (!options.silent) {
      renderHomeMarketIndices({ items: [] });
    }
  }
}

function stopHomeMarketIndexRefresh() {
  window.clearTimeout(state.marketIndexRefreshTimer);
  state.marketIndexRefreshTimer = null;
}

function startHomeMarketIndexRefresh() {
  stopHomeMarketIndexRefresh();
  if (state.view !== "home") {
    return;
  }
  const intervalMs = koreaMarketPhase() === "regular" ? 5_000 : 30_000;
  state.marketIndexRefreshTimer = window.setTimeout(async () => {
    if (state.view === "home" && !document.hidden) {
      await loadHomeMarketIndices({ force: true, silent: true });
    } else if (state.view === "home") {
      startHomeMarketIndexRefresh();
    }
  }, intervalMs);
}

function marketFiveMeta(key) {
  return MARKET_FIVE_ELEMENTS.find((item) => item.key === key) || MARKET_FIVE_ELEMENTS[0];
}

function marketImpactDirection(factor = {}) {
  return factor.direction || factor.status || "악재";
}

function marketFiveFactorMap(model = {}) {
  return new Map((model.factors || []).map((factor) => [factor.key, factor]));
}

function createMarketFiveRelationSvg() {
  const namespace = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(namespace, "svg");
  svg.setAttribute("class", "market-five-lines");
  svg.setAttribute("viewBox", "0 0 1000 900");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");

  const defs = document.createElementNS(namespace, "defs");
  for (const [id, className] of [["market-five-generate-arrow", "generate"], ["market-five-control-arrow", "control"]]) {
    const marker = document.createElementNS(namespace, "marker");
    marker.setAttribute("id", id);
    marker.setAttribute("viewBox", "0 0 10 10");
    marker.setAttribute("refX", "8");
    marker.setAttribute("refY", "5");
    marker.setAttribute("markerWidth", "6");
    marker.setAttribute("markerHeight", "6");
    marker.setAttribute("orient", "auto-start-reverse");
    const arrow = document.createElementNS(namespace, "path");
    arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
    arrow.setAttribute("class", className);
    marker.appendChild(arrow);
    defs.appendChild(marker);
  }
  svg.appendChild(defs);

  const generatePaths = [
    "M540 105 C690 115 805 220 835 340",
    "M855 420 C850 575 795 700 710 755",
    "M655 810 C520 850 390 850 285 790",
    "M230 745 C135 645 110 505 145 405",
    "M170 330 C225 205 330 125 460 105",
  ];
  for (const data of generatePaths) {
    const path = document.createElementNS(namespace, "path");
    path.setAttribute("d", data);
    path.setAttribute("class", "market-five-generate-line");
    path.setAttribute("marker-end", "url(#market-five-generate-arrow)");
    svg.appendChild(path);
  }

  const controlLines = [
    [500, 190, 685, 690],
    [675, 720, 215, 405],
    [210, 375, 790, 375],
    [790, 405, 325, 720],
    [315, 690, 490, 190],
  ];
  for (const [x1, y1, x2, y2] of controlLines) {
    const line = document.createElementNS(namespace, "line");
    line.setAttribute("x1", String(x1));
    line.setAttribute("y1", String(y1));
    line.setAttribute("x2", String(x2));
    line.setAttribute("y2", String(y2));
    line.setAttribute("class", "market-five-control-line");
    line.setAttribute("marker-end", "url(#market-five-control-arrow)");
    svg.appendChild(line);
  }
  return svg;
}

function buildMarketSectorCorrelations(model = {}) {
  const sectors = new Map();
  for (const factor of model.factors || []) {
    const direction = marketImpactDirection(factor);
    const signedImpact = Number(factor.percent || 0) * (direction === "호재" ? 1 : -1);
    for (const sector of factor.affected_sectors || []) {
      if (!sectors.has(sector)) {
        sectors.set(sector, { name: sector, score: 0, factors: [] });
      }
      const item = sectors.get(sector);
      item.score += signedImpact;
      item.factors.push({
        key: factor.key,
        label: factor.label,
        element: marketFiveMeta(factor.key).element,
        direction,
        impact: Number(factor.percent || 0),
      });
    }
  }
  return [...sectors.values()]
    .map((sector) => ({ ...sector, score: Math.max(-100, Math.min(100, sector.score)) }))
    .sort((a, b) => Math.abs(b.score) - Math.abs(a.score) || a.name.localeCompare(b.name, "ko"))
    .slice(0, 8);
}

function marketRelationText(source, target, kind) {
  const sameDirection = marketImpactDirection(source) === marketImpactDirection(target);
  const strength = ((Number(source.percent || 0) + Number(target.percent || 0)) / 2).toFixed(1);
  if (kind === "generate") {
    return `${sameDirection ? "같은 방향 강화" : "반대 방향 상쇄"} · 관계 강도 ${strength}`;
  }
  return `${sameDirection ? "동시 압력" : "서로 견제"} · 관계 강도 ${strength}`;
}

function renderMarketFiveRelation(panel, selectedKey, factorMap, sectorRows) {
  const factor = factorMap.get(selectedKey);
  if (!factor) {
    return;
  }
  const meta = marketFiveMeta(selectedKey);
  const generateFactor = factorMap.get(MARKET_FIVE_RELATIONS.generate[selectedKey]);
  const controlFactor = factorMap.get(MARKET_FIVE_RELATIONS.control[selectedKey]);
  panel.replaceChildren();

  const head = el("div", "market-five-relation-head");
  const title = el("div", "");
  title.append(el("span", `market-five-element-mark ${meta.className}`, meta.element), el("strong", "", `${factor.label} 영향 경로`));
  head.append(title, el("em", marketImpactDirection(factor) === "호재" ? "good" : "bad", `${marketImpactDirection(factor)} ${Number(factor.percent || 0).toFixed(1)}%`));

  const relations = el("div", "market-five-relation-grid");
  for (const [kind, label, targetFactor] of [
    ["generate", "상생 · 이어지는 변수", generateFactor],
    ["control", "상극 · 견제하는 변수", controlFactor],
  ]) {
    if (!targetFactor) {
      continue;
    }
    const item = el("div", `market-five-relation-item ${kind}`);
    item.append(
      el("span", "", label),
      el("strong", "", `${factor.label} → ${targetFactor.label}`),
      el("small", "", marketRelationText(factor, targetFactor, kind)),
    );
    relations.appendChild(item);
  }
  const interpretation = el("p", "market-five-interpretation", factor.interpretation || factor.summary || marketImpactLearningGuide(factor).lesson);
  const sectors = el("p", "market-five-linked-sectors", `주요 영향 업종 · ${(factor.affected_sectors || []).join(" · ") || "확인 중"}`);
  panel.append(head, relations, interpretation, sectors);

  for (const row of sectorRows) {
    const linked = String(row.dataset.factorKeys || "").split(" ").includes(selectedKey);
    row.classList.toggle("is-linked", linked);
    row.classList.toggle("is-muted", !linked);
  }
}

function appendMarketSectorCorrelation(parent, sector) {
  const tone = sector.score > 0.5 ? "good" : sector.score < -0.5 ? "bad" : "neutral";
  const row = el("article", `market-sector-row ${tone}`);
  row.dataset.factorKeys = sector.factors.map((factor) => factor.key).join(" ");
  const head = el("div", "market-sector-row-head");
  const identity = el("div", "");
  identity.append(
    el("strong", "", sector.name),
    el("span", "", sector.factors.map((factor) => `${factor.element} · ${factor.label}`).join(" / ")),
  );
  const result = el("div", "market-sector-result");
  result.append(
    el("span", "", tone === "good" ? "우호" : tone === "bad" ? "부담" : "중립"),
    el("strong", "", `${sector.score > 0 ? "+" : ""}${sector.score.toFixed(1)}`),
  );
  head.append(identity, result);

  const scale = el("div", "market-sector-scale");
  scale.setAttribute("aria-label", `${sector.name} 순영향 ${sector.score.toFixed(1)}점`);
  const axis = el("span", "market-sector-axis");
  const bar = el("span", "market-sector-bar");
  bar.style.setProperty("--sector-impact", `${Math.min(50, Math.abs(sector.score) / 2)}%`);
  scale.append(axis, bar);

  const matrix = el("div", "market-sector-matrix");
  for (const meta of MARKET_FIVE_ELEMENTS) {
    const factor = sector.factors.find((item) => item.key === meta.key);
    const cell = el("span", factor ? (factor.direction === "호재" ? "good" : "bad") : "neutral");
    cell.title = factor ? `${factor.label} ${factor.direction} ${factor.impact.toFixed(1)}%` : `${meta.role} 직접 영향 없음`;
    cell.setAttribute("aria-label", cell.title);
    cell.append(el("b", "", meta.element), document.createTextNode(factor ? (factor.direction === "호재" ? "+" : "−") : "·"));
    matrix.appendChild(cell);
  }
  row.append(head, scale, matrix);
  parent.appendChild(row);
  return row;
}

function renderMarketImpactAnalysis(payload, target = elements.trendImpactContent) {
  const model = normalizeMarketImpactModel(payload);
  const fallback = isFallbackMarketImpact(model);
  if (!target) {
    return;
  }
  target.innerHTML = "";

  const factorMap = marketFiveFactorMap(model);
  const orderedFactors = MARKET_FIVE_ELEMENTS.map((meta) => factorMap.get(meta.key)).filter(Boolean);
  const leadFactor = [...orderedFactors].sort((a, b) => Number(b.percent || 0) - Number(a.percent || 0))[0];
  const initialKey = leadFactor?.key || MARKET_FIVE_ELEMENTS[0].key;
  const shell = el("section", "market-impact-dashboard market-five-dashboard");

  const summary = el("section", "market-five-summary");
  const summaryHead = el("div", "market-five-summary-head");
  const status = el("div", "");
  status.append(el("span", "section-eyebrow", "국내증시"), el("strong", model.marketStatus === "호재 우위" ? "good" : "bad", model.marketStatus));
  summaryHead.append(status, el("time", "", formatDataBasis(model.asOf)));
  const goodWeight = Math.max(0, Number(model.goodWeight || 0));
  const badWeight = Math.max(0, Number(model.badWeight || 0));
  const weightTotal = goodWeight + badWeight || 1;
  const balance = el("div", "market-five-balance");
  const balanceTrack = el("div", "market-five-balance-track");
  const goodBar = el("span", "good");
  const badBar = el("span", "bad");
  goodBar.style.setProperty("--balance-width", `${(goodWeight / weightTotal) * 100}%`);
  badBar.style.setProperty("--balance-width", `${(badWeight / weightTotal) * 100}%`);
  balanceTrack.append(goodBar, badBar);
  balance.append(balanceTrack, el("p", "", `호재 ${goodWeight.toFixed(1)} · 악재 ${badWeight.toFixed(1)}`));
  summary.append(summaryHead, el("p", "market-five-summary-copy", fallback ? "외부 변수가 국내 업종으로 전달되는 구조를 확인합니다." : model.summary), balance);

  const mapSection = el("section", "market-five-map-section");
  const mapHeader = el("header", "market-five-map-head");
  const mapTitle = el("div", "");
  mapTitle.append(el("span", "section-eyebrow", "상생·상극 시장 구조"), el("h2", "", "시장 오행 관계도"));
  const legend = el("div", "market-five-legend");
  legend.append(el("span", "generate", "상생 · 전달"), el("span", "control", "상극 · 견제"));
  mapHeader.append(mapTitle, legend);

  const canvas = el("div", "market-five-canvas");
  canvas.appendChild(createMarketFiveRelationSvg());
  const nodeButtons = [];
  for (const meta of MARKET_FIVE_ELEMENTS) {
    const factor = factorMap.get(meta.key);
    if (!factor) {
      continue;
    }
    const direction = marketImpactDirection(factor);
    const button = el("button", `market-five-node ${meta.className} ${direction === "호재" ? "good" : "bad"}`);
    button.type = "button";
    button.dataset.factorKey = meta.key;
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", `${meta.element} ${factor.label}, 영향도 ${Number(factor.percent || 0).toFixed(1)}%, ${direction}`);
    button.append(
      el("span", "market-five-node-role", meta.role),
      el("strong", "", `${Number(factor.percent || 0).toFixed(1)}%`),
      el("span", "market-five-node-factor", factor.label),
      el("b", "market-five-node-element", meta.element),
    );
    canvas.appendChild(button);
    nodeButtons.push(button);
  }
  const center = el("div", "market-five-center");
  center.append(el("span", "", "국내증시"), el("strong", model.marketStatus === "호재 우위" ? "good" : "bad", model.marketStatus), el("small", "", "변수 간 순환"));
  canvas.appendChild(center);

  const relationPanel = el("section", "market-five-relation-panel");
  relationPanel.setAttribute("aria-live", "polite");
  mapSection.append(mapHeader, canvas, relationPanel);

  const sectorSection = el("section", "market-sector-section");
  const sectorHeader = el("header", "market-sector-head");
  const sectorTitle = el("div", "");
  sectorTitle.append(el("span", "section-eyebrow", "주요 업종 연결"), el("h2", "", "섹터 상관 영향도"));
  sectorHeader.append(sectorTitle, el("p", "", "오행별 + 호재 · − 악재"));
  const sectorList = el("div", "market-sector-list");
  const sectorRows = buildMarketSectorCorrelations(model).map((sector) => appendMarketSectorCorrelation(sectorList, sector));
  sectorSection.append(sectorHeader, sectorList);

  const selectFactor = (key) => {
    for (const button of nodeButtons) {
      const active = button.dataset.factorKey === key;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    }
    renderMarketFiveRelation(relationPanel, key, factorMap, sectorRows);
  };
  for (const button of nodeButtons) {
    button.addEventListener("click", () => selectFactor(button.dataset.factorKey));
  }
  selectFactor(initialKey);

  const detailGrid = el("section", "market-impact-details");
  for (const factor of orderedFactors) {
    appendMarketImpactDetail(detailGrid, factor);
  }
  const details = el("details", "market-impact-disclosure");
  const detailsSummary = document.createElement("summary");
  detailsSummary.textContent = "공식 지표와 종목 근거 보기";
  details.append(detailsSummary, detailGrid);

  shell.append(summary, mapSection, sectorSection, details);
  target.appendChild(shell);
}

function appendTrendEvent(item, parent = elements.trendEvents) {
  const importance = String(item.importance || "일반").trim();
  const importanceClass = importance.includes("매우") ? "critical" : importance.includes("중요") ? "important" : "standard";
  const card = el("article", `trend-event event-importance-${importanceClass}`);
  card.dataset.eventId = item.id;
  const head = el("div", "trend-event-head");
  const title = el("div", "trend-event-title");
  const schedule = el("div", "event-schedule");
  const dateLabel = formatDate(item.starts_at);
  const date = el("time", "", dateLabel);
  date.dateTime = item.starts_at || "";
  schedule.append(el("span", "event-stage", "발표 예정"), date);
  const importanceLabel = el("span", `event-importance event-importance-${importanceClass}`, importance);
  head.append(schedule, importanceLabel);
  title.append(el("h3", "", item.title));

  const facts = el("dl", "event-facts");
  const axisFact = el("div", "event-fact event-axis-fact");
  axisFact.appendChild(el("dt", "", "영향 분야"));
  const axisBadges = el("dd", "event-axis-badges");
  for (const axis of trendEventAxes(item)) {
    axisBadges.appendChild(el("span", `event-axis-badge ${TREND_AXIS_CLASS[axis] || ""}`, axis));
  }
  if (axisBadges.children.length > 0) {
    axisFact.appendChild(axisBadges);
  } else {
    axisFact.appendChild(el("dd", "event-axis-badges", item.category));
  }

  const impactFact = el("div", "event-fact event-impact-fact");
  impactFact.append(el("dt", "", "예상 영향"), el("dd", "trend-impact", item.expected_impact));
  facts.append(axisFact, impactFact);

  const actionRow = el("div", "event-actions");
  const flowButton = el("button", "flow-button", "영향 흐름");
  flowButton.type = "button";
  flowButton.setAttribute("aria-label", `${item.title} 영향 흐름 보기`);
  actionRow.appendChild(flowButton);

  const tags = el("div", "tag-row event-detail-tags");
  appendTags(tags, [...(item.affected_variables || []), ...(item.affected_sectors || [])]);

  const points = el("ul", "watch-points");
  appendListItems(points, item.watch_points, "추가 확인 포인트 없음");

  const source = el("a", "event-source", item.source_name);
  source.href = item.source_url;
  source.target = "_blank";
  source.rel = "noreferrer";

  const details = el("details", "trend-event-disclosure");
  const detailsSummary = document.createElement("summary");
  detailsSummary.textContent = "근거와 출처";
  details.append(detailsSummary, tags, points, source);
  card.append(head, title, facts, actionRow, details);
  parent.appendChild(card);
}

function appendGraphNode(parent, node, stockMap = {}) {
  const stockCode = node.kind === "stock" ? node.id.replace("stock-", "") : "";
  const stock = stockMap[stockCode];
  const item = stock ? el("a", `flow-node ${node.kind} ${node.polarity || "neutral"}`) : el("div", `flow-node ${node.kind} ${node.polarity || "neutral"}`);
  if (stock) {
    item.href = viewStockUrl(stock.name);
  }
  item.append(el("strong", "", node.label));
  if (node.detail) {
    item.appendChild(el("span", "", node.detail));
  }
  parent.appendChild(item);
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

function appendStockImpact(parent, stock) {
  const node = el("article", "impact-stock");
  node.dataset.code = stock.code || "";
  node.dataset.name = stock.name || "";
  node.dataset.market = stock.market || "";
  const head = el("div", "impact-stock-head");
  const identity = el("div", "impact-stock-identity");
  const title = el("a", "impact-stock-title", stock.name);
  title.href = viewStockUrl(stock.name);
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
    const graphUrl = `/market/trends/${encodeURIComponent(eventId)}/graph`;
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
      button.textContent = "영향 흐름";
    }
  }
}

function renderTrends(payload, activeTab = "live") {
  restoreTrendChrome(activeTab);
  elements.trendEvents.innerHTML = "";
  elements.trendPastEvents.innerHTML = "";
  elements.trendThread.innerHTML = "";
  const selectedTab = ["live", "events", "impact"].includes(state.activeTrendTab) ? state.activeTrendTab : activeTab;
  setTrendTab(selectedTab);
  const events = focusedTrendEvents(payload.events);
  const pastEvents = focusedTrendEvents(payload.past_events);
  // The live feed is a chronological market-news stream. Macro-only filtering
  // belongs to the event/impact views and can otherwise hide every fresh item.
  const timeline = payload.timeline || [];

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
}

async function loadTrends(activeTab = state.activeTrendTab || "live", options = {}) {
  restoreTrendChrome(activeTab);
  try {
    const force = options.force === true;
    const ttlMs = options.ttlMs ?? pageEntryTtlMs(activeTab === "past" ? "trend-past" : "trend");
    const url = "/market/trends?days=7";
    const payload = await fetchJsonCached(url, { force, ttlMs: force ? 0 : ttlMs });
    state.homeTrendContext = payload;
    if (state.view === "home") {
      renderHomeAiResponse();
    }
    renderTrends(payload, activeTab);
  } catch {
    const target = activeTab === "events" ? elements.trendEvents : elements.trendThread;
    if (target) {
      target.replaceChildren(el("p", "muted", "트렌드 데이터를 불러오지 못했습니다."));
    }
  }
}

async function loadMarketImpactAnalysis(options = {}) {
  const target = elements.trendImpactContent;
  if (target) {
    target.innerHTML = "";
    target.appendChild(el("p", "muted", "외부 지표를 수집하고 영향도를 계산하는 중입니다."));
  }
  try {
    const force = options.force === true;
    const ttlMs = options.ttlMs ?? pageEntryTtlMs("trend-impact");
    const url = force ? liveUrl("/market/impact?refresh=true") : "/market/impact";
    const payload = await fetchJsonCached(url, { force, ttlMs: force ? 0 : ttlMs });
    state.homeMarketImpact = payload;
    if (state.view === "home") {
      renderHomeAiResponse();
    }
    renderMarketImpactAnalysis(payload, target);
  } catch {
    try {
      const fallbackPayload = await fetchJsonCached("/market/trends?days=7", { force: true, ttlMs: 0 });
      renderMarketImpactAnalysis(fallbackPayload, target);
    } catch {
      if (target) {
        target.innerHTML = "";
        target.appendChild(el("p", "muted", "시장 영향도 데이터 없음"));
      }
    }
  }
}

async function loadHomeMarketImpact(options = {}) {
  try {
    const force = options.force === true;
    const ttlMs = options.ttlMs ?? PAGE_ENTRY_MINUTE_MS;
    const payload = await fetchJsonCached("/market/impact", { force, ttlMs: force ? 0 : ttlMs });
    state.homeMarketImpact = payload;
    if (state.view === "home") {
      renderHomeAiResponse();
    }
  } catch {
    // The rest of the live market context remains available when impact data is delayed.
  }
}

async function loadRecommendations(options = {}) {
  if (state.recommendationLoading) {
    return;
  }
  const force = options.force === true;
  const recompute = options.recompute === true;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("recommend");
  const saveSnapshot = options.save === true;

  state.recommendationLoading = true;
  const hadRecommendations = elements.recommendList.children.length > 0;
  if (!hadRecommendations) {
    setRecommendStatus("추천 종목을 불러오는 중입니다.");
  }
  const sectorMovesPromise = refreshUsSectorMoves(options);
  const baseUrl = `/market/recommendations?limit=${RECOMMENDATION_LIMIT}&candidate_limit=45`;
  const fetchLatestRecommendations = () => fetchJsonCached(baseUrl, { force, ttlMs: force ? 0 : ttlMs });
  const liveRefreshPromise = recompute
    ? fetchJsonCached(liveUrl(`${baseUrl}&refresh=1`), { force: true, ttlMs: 0 })
    : null;
  let rendered = hadRecommendations;
  try {
    const initialPayload = await fetchLatestRecommendations();
    renderRecommendations(initialPayload, { save: saveSnapshot, usSectorMoves: state.usSectorMoves });
    rendered = true;
  } catch {
    if (!liveRefreshPromise && !rendered) {
      setRecommendStatus("추천 종목을 불러오지 못했습니다. 잠시 후 검색 화면을 다시 열어주세요.");
    }
  }
  if (liveRefreshPromise) {
    try {
      const livePayload = await liveRefreshPromise;
      renderRecommendations(livePayload, { save: saveSnapshot, usSectorMoves: state.usSectorMoves });
      rendered = true;
    } catch {
      if (!rendered) {
        setRecommendStatus("추천 종목을 불러오지 못했습니다. 잠시 후 검색 화면을 다시 열어주세요.");
      }
    }
  }
  sectorMovesPromise.catch(() => {});
  connectUsSectorStream();
  state.recommendationLoading = false;
}

function setLoading(code) {
  state.currentStock = null;
  state.currentDashboard = null;
  state.stockAIAnalysis = null;
  state.stockAIRequestedCode = "";
  state.stockQuantSignals = null;
  state.stockQuantRequestedCode = "";
  state.stockQuantLastLiveRefreshAt = 0;
  state.stockPriceRows = [];
  elements.name.textContent = "종목 분석";
  elements.meta.textContent = `${code} · 불러오는 중`;
  setText(elements.stockV2MarketCode, code);
  setText(elements.stockV2AsOf, "기준 정보 확인 중");
  setText(elements.stockPreMarket, "장전 -");
  resetAIAnalysis();
  resetQuantSignals();
  resetStockPriceSummary();
  resetStockHomeDetails();
}

function render(data, options = {}) {
  const previousCode = options.previousCode || state.currentStock?.code;
  const preserveQuantRequest = options.preserveQuantRequest === true
    && state.stockQuantRequestedCode === data.code;
  state.currentStock = { code: data.code, name: data.name, market: data.market };
  state.currentDashboard = data;
  state.stockAIAnalysis = null;
  state.stockAIRequestedCode = "";
  resetAIAnalysis();
  if (!preserveQuantRequest) {
    state.stockQuantSignals = null;
    state.stockQuantRequestedCode = "";
    state.stockQuantLastLiveRefreshAt = 0;
    resetQuantSignals();
  }
  setActiveStockTab(state.stockActiveTab || "summary", { preserveScroll: true });
  elements.name.textContent = data.name;
  elements.meta.textContent = stockDetailMetaText(data);
  elements.input.value = data.name;
  if (previousCode !== data.code) {
    for (const node of [elements.quotePrice, elements.stockChangeValue, elements.quoteChange, elements.quoteValue, elements.quoteCap]) {
      delete node.dataset.rawValue;
    }
  }

  renderStockLiveSummary(data, quoteSourceLabel(data));
  updateQuoteStrip(data.quote, data);
  renderStockCompanyProfile(data);
  renderStockResearchSummary(data);
  renderStockDerivedIndicators(data);
  renderStockSummaryFallback(data);
  renderEvidenceSummary(data);
  renderStockV2Dashboard(data);
  loadStockPriceSummary(data.code, data.quote);
  void loadStockHomeDetails(data);
  connectQuoteStream(state.currentStock);

  const chart = data.chart_analysis || {};
  elements.chartScore.textContent = formatNumber(chart.score);
  elements.chartStance.textContent = chart.stance || "-";
  elements.chartTrend.textContent = chart.trend || "-";
  elements.chartSetup.textContent = chart.setup || "-";
  elements.chartRisk.textContent = chart.risk_level || "-";
  elements.chartVolume.textContent = formatRatio(chart.volume_ratio);
  elements.chartSupport.textContent = chart.support
    ? `${formatNumber(chart.support)} (${formatPercent(chart.distance_to_support)})`
    : "-";
  elements.chartResistance.textContent = chart.resistance
    ? `${formatNumber(chart.resistance)} (${formatPercent(chart.distance_to_resistance)})`
    : "-";
  setTone(elements.chartScore, chart.score - 50);
  appendListItems(elements.chartSignals, chart.signals, "뚜렷한 차트 신호가 아직 약합니다.");
  appendListItems(elements.chartRisks, chart.risks, "주요 차트 리스크 신호는 제한적입니다.");

  elements.estimateRevenue.textContent = formatMoney(data.revisions.estimated_revenue ? Number(data.revisions.estimated_revenue) * 100000000 : null);
  elements.estimateProfit.textContent = formatMoney(data.revisions.estimated_operating_profit ? Number(data.revisions.estimated_operating_profit) * 100000000 : null);
  elements.estimateEps.textContent = formatNumber(data.revisions.estimated_eps);
  elements.revisionCount.textContent = formatNumber(data.revisions.report_count_90d);
  elements.revisionUp.textContent = formatNumber(data.revisions.target_up_count);
  elements.revisionDown.textContent = formatNumber(data.revisions.target_down_count);
  elements.revisionRatio.textContent = formatPercent(data.revisions.target_up_ratio);

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

  elements.per.textContent = formatMultiple(data.valuation.per);
  elements.pbr.textContent = formatMultiple(data.valuation.pbr);
  elements.estimatedPer.textContent = formatMultiple(data.valuation.estimated_per);
  elements.industryPer.textContent = formatMultiple(data.valuation.industry_per);
  elements.perZ.textContent = data.valuation.per_zscore ?? "계산중";
  elements.pbrZ.textContent = data.valuation.pbr_zscore ?? "계산중";

  elements.latestRevenue.textContent = formatMoney(data.surprise.latest_revenue ? Number(data.surprise.latest_revenue) * 100000000 : null);
  elements.latestProfit.textContent = formatMoney(data.surprise.latest_operating_profit ? Number(data.surprise.latest_operating_profit) * 100000000 : null);
  elements.latestEps.textContent = formatNumber(data.surprise.latest_eps);
  elements.profitGrowth.textContent = formatPercent(data.surprise.operating_profit_growth);
  setTone(elements.profitGrowth, data.surprise.operating_profit_growth);

  const sentimentView = sentimentBreakdown(data.sentiment);
  elements.sentimentScore.textContent = sentimentView.positiveText;
  elements.sentimentCounts.textContent = sentimentView.negativeText;
  elements.sentimentScore.classList.remove("positive", "negative", "muted");
  elements.sentimentCounts.classList.remove("positive", "negative", "muted");
  if (sentimentView.hasDirectionalSignal) {
    elements.sentimentScore.classList.add("positive");
    elements.sentimentCounts.classList.add("negative");
  } else {
    elements.sentimentScore.classList.add("muted");
    elements.sentimentCounts.classList.add("muted");
  }
  renderEvents(elements.newsEvidenceList, (data.sentiment.latest_items || []).slice(0, 3));

  renderEvents(elements.surpriseList, data.surprise.latest_events);
  renderEvents(elements.guidanceList, data.guidance.latest_events);
  renderEvents(elements.newsList, data.sentiment.latest_items);

  elements.macroRate.textContent = formatPercent(data.macro_sensitivity.interest_rate);
  elements.macroFx.textContent = formatPercent(data.macro_sensitivity.fx_usdkrw);
  elements.macroCommodity.textContent = formatPercent(data.macro_sensitivity.commodity);
  elements.macroExport.textContent = formatPercent(data.macro_sensitivity.exports);
  setTone(elements.macroRate, data.macro_sensitivity.interest_rate);
  setTone(elements.macroFx, data.macro_sensitivity.fx_usdkrw);
  setTone(elements.macroCommodity, data.macro_sensitivity.commodity);
  setTone(elements.macroExport, data.macro_sensitivity.exports);
  renderStockHome(data);
  updateWatchButton();
}

async function resolveStock(query) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    return null;
  }
  try {
    return await fetchJsonCached(`/stocks/resolve?query=${encodeURIComponent(normalized)}`, { ttlMs: 5 * UI_CACHE_TTL_MS });
  } catch {
    return null;
  }
}

async function loadStockRequest(query, options = {}) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    return;
  }
  const previousStock = state.currentStock;
  hideSuggestions();
  elements.form?.classList.remove("expanded");
  setLoading(normalized);
  const stock = await resolveStock(normalized);
  if (!stock) {
    elements.name.textContent = "종목 분석";
    elements.meta.textContent = `${normalized} · 데이터 없음`;
    closeQuoteStream();
    resetAIAnalysis();
    return;
  }
  if (previousStock?.code && previousStock.code !== stock.code) {
    setActiveStockTab("summary", { preserveScroll: true });
  }
  state.currentStock = { code: stock.code, name: stock.name, market: stock.market };
  const quantSignalPrefetch = loadQuantSignals({ auto: true });
  try {
    render(
      await fetchJsonCached(`/stocks/${encodeURIComponent(stock.code)}/dashboard?include_profile=0&include_live=0`, {
        force: options.force === true,
        ttlMs: pageEntryTtlMs("stock"),
      }),
      { previousCode: previousStock?.code, preserveQuantRequest: true },
    );
  } catch {
    elements.name.textContent = stock.name;
    elements.meta.textContent = `${stock.code} · 데이터 없음`;
    closeQuoteStream();
    resetAIAnalysis();
    return;
  }
  void quantSignalPrefetch;
  const stockUrl = `/dashboard/${encodeURIComponent(stock.name)}`;
  if (options.historyMode !== "none") {
    if (state.view === "stock") {
      history.replaceState(null, "", stockUrl);
    } else {
      history.pushState(null, "", stockUrl);
    }
  }
  setView("stock");
}

function load(query, options = {}) {
  return runPageLoading(PAGE_LOADING_LABELS.stock, () => loadStockRequest(query, options));
}

async function syncViewFromLocation() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  if (parts[0] === "dashboard" && parts[1]) {
    setView("stock");
    await load(decodeURIComponent(parts[1]));
    return;
  }
  const routeView = new URLSearchParams(window.location.search).get("view") || "home";
  setView(routeView);
}

window.addEventListener("popstate", () => {
  void syncViewFromLocation();
});

for (const item of elements.appNavItems) {
  item.addEventListener("click", () => {
    setView(item.dataset.appView);
    window.scrollTo({ top: 0, behavior: "auto" });
  });
}
elements.homeInstallButton?.addEventListener("click", handleHomeInstall);
elements.homeAiSignalsMore?.addEventListener("click", () => {
  setView("ai-signals");
  window.scrollTo({ top: 0, behavior: "auto" });
});
elements.homeAiResponseWatch?.addEventListener("click", () => {
  state.portfolioTab = "watchlist";
  state.watchlistContentTab = "strategy";
  setView("portfolio");
  window.scrollTo({ top: 0, behavior: "auto" });
});
elements.aiSignalsBack?.addEventListener("click", () => {
  setView("home");
  window.scrollTo({ top: 0, behavior: "auto" });
});
for (const tab of elements.aiSignalStageTabs) {
  tab.addEventListener("click", () => setAiSignalStage(tab.dataset.aiSignalStage));
}
elements.homeSurgeMore?.addEventListener("click", () => {
  setMarketFilter("KOSPI");
  setView("movers");
  window.scrollTo({ top: 0, behavior: "auto" });
});
elements.marketRankingBack?.addEventListener("click", () => {
  if (window.history.length > 1 && document.referrer.startsWith(window.location.origin)) {
    window.history.back();
    return;
  }
  setView("home");
  window.scrollTo({ top: 0, behavior: "auto" });
});
elements.installSheetBackdrop?.addEventListener("click", closeInstallSheet);
elements.installSheetClose?.addEventListener("click", closeInstallSheet);

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeInstallSheet();
    document.querySelectorAll(".term-help.open").forEach((item) => item.classList.remove("open"));
  }
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 980) {
    resetPullRefreshIndicator({ immediate: true });
  }
  updateHomeInstallButton();
});

window.addEventListener("touchstart", handlePullRefreshStart, { passive: true });
window.addEventListener("touchmove", handlePullRefreshMove, { passive: false });
window.addEventListener("touchend", handlePullRefreshEnd, { passive: true });
window.addEventListener("touchcancel", () => resetPullRefreshIndicator({ immediate: true }), { passive: true });

window.addEventListener("appinstalled", () => {
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
    launchPageLoading(PAGE_LOADING_LABELS.market, () => loadMarketRankings());
  });
}

elements.rankCategorySelect?.addEventListener("change", () => {
  state.rankingCategory = elements.rankCategorySelect.value;
  for (const item of elements.rankTabs) {
    item.classList.toggle("active", item.dataset.category === state.rankingCategory);
  }
  launchPageLoading(PAGE_LOADING_LABELS.market, () => loadMarketRankings());
});

for (const tab of elements.marketTabs) {
  tab.addEventListener("click", () => {
    const market = setMarketFilter(tab.dataset.marketFilter);
    launchPageLoading(PAGE_LOADING_LABELS.market, () => loadMarketRankings({ market, limit: 30 }));
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
  setLoginStatus("접속 ID로 들어가는 중");
  const ok = await applyWatchlistId(elements.loginInput.value, { merge: true });
  if (ok) {
    setLoginStatus("입장 완료", "success");
    hideLoginGate();
  } else {
    showLoginGate("아이디를 확인해주세요. 2~40자 한글/영문/숫자/._-만 가능합니다.", { skipSplash: true });
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
elements.pushNotificationButton?.addEventListener("click", openPushNotificationCenter);
elements.pushHistoryBack?.addEventListener("click", () => {
  const returnView = state.notificationReturnView || "home";
  if (returnView === "stock" && state.currentStock?.name) {
    window.location.assign(viewStockUrl(state.currentStock.name));
    return;
  }
  setView(["home", "search", "portfolio", "chart", "movers"].includes(returnView) ? returnView : "home");
  window.scrollTo({ top: 0, behavior: "auto" });
});
elements.pushHistorySettings?.addEventListener("click", openPushSettingsFromHistory);
for (const tab of elements.pushHistoryTabs) {
  tab.addEventListener("click", () => {
    const nextTab = tab.dataset.notificationTab || "all";
    if (nextTab === state.pushNotificationHistoryTab) {
      return;
    }
    if (elements.pushHistoryList) {
      state.pushNotificationHistoryScrollTop.set(
        state.pushNotificationHistoryTab,
        elements.pushHistoryList.scrollTop,
      );
    }
    state.pushNotificationHistoryTab = nextTab;
    renderPushNotificationHistory({ restoreScroll: true });
  });
}
elements.pushNotificationDisableButton?.addEventListener("click", disablePushNotificationsFromUi);
elements.pushNotificationSheetBackdrop?.addEventListener("click", closePushNotificationSheet);
elements.pushNotificationSheetClose?.addEventListener("click", closePushNotificationSheet);
elements.pushNotificationSheetSaveButton?.addEventListener("click", savePushNotificationSettings);
elements.pushNotificationSheetTestButton?.addEventListener("click", sendPushTestNotification);
elements.pushNotificationSheetDisableButton?.addEventListener("click", disablePushNotificationsFromUi);
for (const button of elements.stockV2PricePeriods) {
  button.addEventListener("click", () => {
    state.stockPricePeriod = button.dataset.pricePeriod || "1D";
    renderStockMiniChart(state.stockPriceRows, state.currentDashboard?.quote);
  });
}
const stockSearchSubmitButton = elements.form?.querySelector(":scope > button");
stockSearchSubmitButton?.addEventListener("click", (event) => {
  if (!window.matchMedia("(max-width: 980px)").matches || elements.form.classList.contains("expanded")) {
    return;
  }
  event.preventDefault();
  elements.form.classList.add("expanded");
  elements.input.focus();
  elements.input.select();
});
elements.input?.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    elements.form.classList.remove("expanded");
    elements.input.blur();
  }
});
elements.stockDetailBack?.addEventListener("click", () => {
  if (window.history.length > 1 && document.referrer.startsWith(window.location.origin)) {
    window.history.back();
    return;
  }
  setView("trend");
});
for (const button of elements.stockFinancialMetricTabs) {
  button.addEventListener("click", () => {
    state.stockFinancialMetric = button.dataset.financialMetric || "revenue";
    renderStockFinancialChart();
  });
}
for (const button of elements.stockFinancialScopeTabs) {
  button.addEventListener("click", () => {
    state.stockFinancialScope = button.dataset.financialScope || "quarterly";
    renderStockFinancialChart();
  });
}
for (const button of elements.stockFlowModeTabs) {
  button.addEventListener("click", () => {
    state.stockFlowMode = button.dataset.flowMode || "cumulative";
    renderStockFlowHistoryChart();
  });
}
for (const button of elements.stockFlowPeriodTabs) {
  button.addEventListener("click", () => {
    state.stockFlowPeriod = button.dataset.flowPeriod || "3M";
    renderStockFlowHistoryChart();
  });
}
for (const button of elements.stockReportModeTabs) {
  button.addEventListener("click", () => {
    state.stockReportMode = button.dataset.reportMode || "target";
    renderStockReportHistoryChart();
  });
}
for (const button of elements.stockNewsModeTabs) {
  button.addEventListener("click", () => {
    state.stockNewsMode = button.dataset.newsMode || "company";
    renderStockNewsRows(state.stockNewsRows.length
      ? state.stockNewsRows
      : state.currentDashboard?.sentiment?.latest_items || []);
  });
}
elements.quantSignalRefresh?.addEventListener("click", (event) => {
  event.preventDefault();
  launchPageLoading(PAGE_LOADING_LABELS.ai, () => loadQuantSignals({ auto: false, force: true }));
});
elements.aiAnalysisButton?.addEventListener("click", (event) => {
  event.preventDefault();
  launchPageLoading(PAGE_LOADING_LABELS.ai, () => Promise.all([
    loadQuantSignals({ auto: false, force: true }),
    loadAIAnalysis({ auto: false, force: true }),
  ]));
});
elements.stockInlineAIRefresh?.addEventListener("click", (event) => {
  event.preventDefault();
  launchPageLoading(PAGE_LOADING_LABELS.ai, () => loadAIAnalysis({ auto: false, force: true }));
});
for (const tab of elements.stockSectionTabs) {
  tab.addEventListener("click", (event) => {
    event.preventDefault();
    setActiveStockTab(tab.dataset.stockTab || "summary");
  });
}
elements.recommendArchiveButton?.addEventListener("click", () => setView("recommend-history"));
elements.recommendHistoryNewButton?.addEventListener("click", () => setView("recommend"));
elements.watchChartRefresh?.addEventListener("click", () => {
  const item = state.watchChartResults[0]?.item;
  if (item) {
    clearCachedUrl(`/stocks/${encodeURIComponent(item.code)}/prices?limit=180`);
    clearCachedUrl(`/stocks/${encodeURIComponent(item.code)}/dashboard?include_profile=0`);
    void loadWatchCharts({ items: [item], force: true, single: true });
  }
});
elements.chartHistoryBackButton.addEventListener("click", () => setView("chart"));
elements.recommendHistoryList.addEventListener("click", (event) => {
  const detailButton = event.target.closest(".recommend-track-detail-toggle");
  if (detailButton) {
    const card = detailButton.closest(".recommend-track-card");
    const detail = card?.querySelector(".recommend-track-detail");
    if (detail) {
      setRecommendationTrackExpanded(card, detail.hidden);
    }
    return;
  }

  const deleteButton = event.target.closest(".track-delete");
  if (deleteButton) {
    deleteRecommendationTrack(deleteButton.dataset.trackId);
    updateRecommendationTrackButtons();
    launchPageLoading(PAGE_LOADING_LABELS["recommend-history"], () => loadRecommendationHistory());
    return;
  }
});
for (const tab of elements.trendTabs) {
  tab.addEventListener("click", () => {
    const active = setTrendTab(tab.dataset.trendTab);
    if (active === "impact" && !elements.trendImpactContent.querySelector(".market-impact-dashboard")) {
      void loadMarketImpactAnalysis(pageEntryRefreshOptions("trend-impact"));
    }
  });
}
elements.homePastToggle?.addEventListener("click", () => {
  state.showPastEvents = !state.showPastEvents;
  setTrendTab("events");
});
for (const tab of elements.portfolioTabs) {
  tab.addEventListener("click", () => setPortfolioTab(tab.dataset.portfolioTab, { load: true }));
}
for (const tab of elements.watchlistContentTabs) {
  tab.addEventListener("click", () => setWatchlistContentTab(tab.dataset.watchContentTab, { load: true }));
}
elements.trendWatchStockRail?.addEventListener("click", (event) => {
  const button = event.target.closest(".trend-watch-stock-chip");
  if (button) {
    void loadTrendWatchlistNews({ code: button.dataset.code });
  }
});
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
  if (event.target.closest(".trend-event-disclosure")) {
    return;
  }
  const card = event.target.closest(".trend-event");
  if (card) {
    loadTrendGraph(card);
  }
}

elements.trendEvents.addEventListener("click", handleTrendEventClick);
elements.trendPastEvents.addEventListener("click", handleTrendEventClick);
elements.trendImpactContent?.addEventListener("click", handleTrendEventClick);

elements.discoverySearchForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = elements.discoverySearchInput.value.trim();
  if (query) {
    hideStandaloneSuggestions(elements.discoverySearchInput, elements.discoverySearchSuggestions);
    void load(query);
  }
});
elements.discoverySearchInput?.addEventListener("input", () => scheduleStandaloneSuggestions("discovery"));
elements.discoverySearchInput?.addEventListener("focus", () => {
  if (elements.discoverySearchInput.value.trim()) {
    scheduleStandaloneSuggestions("discovery");
  }
});
elements.chartStockSearchForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = elements.chartStockSearchInput.value.trim();
  if (query) {
    window.clearTimeout(state.chartSuggestionTimer);
    state.chartSuggestionController?.abort();
    hideStandaloneSuggestions(elements.chartStockSearchInput, elements.chartStockSearchSuggestions);
    elements.chartStockSearchInput.blur();
    void loadChartStock(query);
  }
});
elements.chartStockSearchInput?.addEventListener("input", () => scheduleStandaloneSuggestions("chart"));
elements.chartStockSearchInput?.addEventListener("focus", () => {
  if (elements.chartStockSearchInput.value.trim()) {
    scheduleStandaloneSuggestions("chart");
  }
});

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
  state.watchPreopenExpanded.delete(code);
  writeWatchlist(readWatchlist().filter((item) => item.code !== code));
  updateWatchButton();
  void loadWatchlist();
});

for (const button of elements.watchlistFilterButtons) {
  button.addEventListener("click", () => {
    state.watchlistFilter = button.dataset.watchFilter || "all";
    applyWatchlistFilter();
  });
}

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
    if (card?.recommendationItem) {
      openRecommendationDetail(card.recommendationItem);
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

elements.recommendDetailBack?.addEventListener("click", () => setView("search"));

elements.watchChartList.addEventListener("click", (event) => {
  const horizonButton = event.target.closest("[data-chart-horizon]");
  if (horizonButton) {
    const result = state.watchChartResults[0];
    if (result) {
      renderChartForecastResult(result, Number(horizonButton.dataset.chartHorizon));
    }
    return;
  }

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
  const stockLink = event.target.closest('a[href^="/dashboard/"]');
  if (
    stockLink
    && !event.defaultPrevented
    && event.button === 0
    && !event.metaKey
    && !event.ctrlKey
    && !event.shiftKey
    && !event.altKey
    && !stockLink.hasAttribute("download")
    && (!stockLink.target || stockLink.target === "_self")
  ) {
    const query = stockRouteQuery(stockLink.href);
    if (query) {
      event.preventDefault();
      void navigateToStock(query, stockLink.href);
      return;
    }
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
    elements.form.classList.remove("expanded");
  }
  if (elements.discoverySearchForm && !elements.discoverySearchForm.contains(event.target)) {
    hideStandaloneSuggestions(elements.discoverySearchInput, elements.discoverySearchSuggestions);
  }
  if (elements.chartStockSearchForm && !elements.chartStockSearchForm.contains(event.target)) {
    hideStandaloneSuggestions(elements.chartStockSearchInput, elements.chartStockSearchSuggestions);
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopHomeMarketIndexRefresh();
    closeQuoteStream();
    closeWatchlistQuoteStreams();
    closeMarketQuoteStreams();
    closeRecommendationQuoteStreams();
    closeUsSectorStream();
    return;
  }
  if (state.view === "home") {
    void loadHomeMarketIndices({ force: true, silent: true });
    void loadTrends(state.activeTrendTab === "impact" ? "live" : state.activeTrendTab || "live", { force: true, ttlMs: 0 });
    void refreshUsSectorMoves({ force: true, ttlMs: 0 });
    connectUsSectorStream();
  } else if (state.view === "stock" && state.currentStock) {
    connectQuoteStream(state.currentStock);
  } else if (state.view === "portfolio" && state.portfolioTab === "watchlist") {
    elements.watchlistBody.querySelectorAll("[data-watch-card][data-code]").forEach((card) => {
      connectWatchlistQuoteStream(card.dataset.code);
    });
    connectUsSectorStream();
  } else if (state.view === "search") {
    if (state.rankingCategory === "surge") {
      state.marketLeaderboardItems.slice(0, 30).forEach((item) => connectMarketQuoteStream(item.code));
    }
    elements.recommendList.querySelectorAll(".recommend-card[data-code]").forEach((card) => {
      connectRecommendationQuoteStream(card.dataset.code);
    });
    connectUsSectorStream();
  }
});

registerDashboardServiceWorker();
updateHomeInstallButton();
applyStockTermTooltips();

async function initializeDashboard() {
  await initializeWatchlistIdentity();
  if (state.view === "stock") {
    setView("stock");
    await load(pathQuery());
  } else {
    setView(state.view);
  }
}

void initializeDashboard();
