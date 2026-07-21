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
  stockSectionTabs: Array.from(document.querySelectorAll("[data-stock-tab]")),
  stockTabPanels: Array.from(document.querySelectorAll("[data-stock-panel]")),
  watchlistView: $("watchlist-view"),
  watchlistIdForm: $("watchlist-id-form"),
  watchlistIdInput: $("watchlist-id-input"),
  watchlistIdDisplay: $("watchlist-id-display"),
  watchlistIdStatus: $("watchlist-id-status"),
  logoutButton: $("logout-button"),
  sidebarPresenceCount: $("sidebar-presence-count"),
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
  stockAISayProbability: $("stock-ai-say-probability"),
  stockAISayConfidence: $("stock-ai-say-confidence"),
  stockAISayText: $("stock-ai-say-text"),
  stockInlineAIRefresh: $("stock-inline-ai-refresh"),
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
  watchlistStrategy: $("watchlist-strategy"),
  watchlistBody: $("watchlist-body"),
  recommendMeta: $("recommend-meta"),
  recommendButton: $("recommend-button"),
  recommendArchiveButton: $("recommend-archive-button"),
  recommendHistoryNewButton: $("recommend-history-new-button"),
  recommendStatus: $("recommend-status"),
  recommendList: $("recommend-list"),
  recommendHistoryMeta: $("recommend-history-meta"),
  recommendHistoryList: $("recommend-history-list"),
  trendTitle: $("trend-title"),
  trendSummary: document.querySelector("#trend-view .trend-summary"),
  trendHeadline: $("trend-headline"),
  trendEventsTitle: $("trend-events-title"),
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
  sideNav: $("side-nav"),
  sideItems: Array.from(document.querySelectorAll(".side-menu-item")),
  rankTabs: Array.from(document.querySelectorAll(".rank-tab")),
  rankCategorySelect: $("rank-category-select"),
  marketTabs: Array.from(document.querySelectorAll("[data-market-filter]")),
  rankingBody: $("ranking-body"),
  name: $("stock-name"),
  meta: $("stock-meta"),
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
};

const WATCHLIST_KEY = "analyst.watchlist";
const WATCHLIST_ID_KEY = "analyst.watchlistId";
const WATCHLIST_ACTIVITY_KEY = "analyst.watchlistActivity";
const RECOMMENDATION_HISTORY_KEY = "analyst.recommendationSnapshots";
const RECOMMENDATION_TRACK_KEY = "analyst.recommendationTracks";
const RECOMMENDATION_COOLDOWN_KEY = "analyst.recommendationCooldown";
const CHART_SNAPSHOT_KEY = "analyst.chartSnapshots";
const UI_CACHE_TTL_MS = 60_000;
const PAGE_ENTRY_MINUTE_MS = 60_000;
const LOGIN_SPLASH_DURATION_MS = 5_000;
const APP_SPLASH_DURATION_MS = 5_000;
const SESSION_IDLE_TIMEOUT_MS = 10 * 60_000;
const SESSION_ACTIVITY_SYNC_MS = 10_000;
const RECOMMENDATION_LIMIT = 10;
const RECOMMENDATION_REGULAR_COOLDOWN_MS = 10 * 60_000;
const RECOMMENDATION_OFFHOURS_COOLDOWN_MS = 30 * 60_000;
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

const state = {
  view: ["market", "watchlist", "recommend", "recommend-history", "trend", "trend-past", "trend-impact", "chart", "chart-history"].includes(new URLSearchParams(window.location.search).get("view"))
    ? new URLSearchParams(window.location.search).get("view")
    : "stock",
  rankingCategory: "surge",
  currentStock: null,
  currentDashboard: null,
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
  marketLeaderboardItems: [],
  marketLeaderboardAsOf: "",
  marketLeaderboardTradeDate: "",
  marketQuoteSockets: new Map(),
  marketQuoteReconnectTimers: new Map(),
  marketPrefetchKey: "",
  usSectorMoves: null,
  usSectorRefreshTimer: null,
  usSectorRefreshing: false,
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
  watchlistResults: [],
  watchlistMarketContext: null,
  stockActiveTab: "summary",
  stockPriceRows: [],
  stockAIAnalysis: null,
  stockAIRequestedCode: "",
  stockAILoading: false,
  watchPreopenExpanded: new Set(),
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
  presenceSocket: null,
  presenceReconnectTimer: null,
  presencePageKey: "",
  presenceCount: null,
  presenceHundredsDigit: null,
  presenceHundredsHourKey: "",
  presenceHourTimer: null,
  recommendTrackRequestId: 0,
  recommendationLoading: false,
  recommendationCooldownTimer: null,
  loginGateTimer: null,
  loginSplashSeen: false,
  sessionIdleTimer: null,
  sessionLastActiveAt: 0,
  sessionLastSyncedAt: 0,
  sessionScrollTicking: false,
  mobileMenuScrollY: 0,
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
  if (payload.source === "kis_realtime") {
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
  const parts = [data.code, data.market, formatDate(data.as_of)];
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
  return ["summary", "strategy"].includes(tabName) && Boolean(state.currentStock?.code);
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
}

function scrollToStockSection(hash, options = {}) {
  const map = {
    "#stock-summary-section": "summary",
    "#stock-ai-section": "strategy",
    "#stock-strategy-section": "strategy",
    "#stock-chart-section": "evidence",
    "#stock-flow-section": "evidence",
    "#stock-research-section": "evidence",
    "#stock-consensus-section": "evidence",
    "#stock-momentum-section": "summary",
    "#stock-finance-section": "evidence",
    "#stock-news-section": "evidence",
    "#stock-macro-section": "evidence",
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
  const entryLabel = levels.entry_label || (actionable ? "1차 매수권" : "관찰 가격대");
  const entry = buyLow !== null && buyHigh !== null
    ? `${entryLabel} ${formatNumber(Math.min(buyLow, buyHigh))}~${formatNumber(Math.max(buyLow, buyHigh))}`
    : "-";
  const conditionParts = [];
  if (breakout !== null) {
    conditionParts.push(`돌파 ${formatNumber(breakout)}`);
  }
  if (stop !== null) {
    conditionParts.push(`축소 ${formatNumber(stop)}`);
  }
  const condition = conditionParts.length
    ? `${actionable ? "분할 접근" : "관찰 우선"} · ${conditionParts.join(" · ")}`
    : (payload?.stance || "-");
  setText(elements.aiDecisionStance, payload?.stance || "-");
  setText(elements.aiDecisionConfidence, coverage);
  setText(elements.aiDecisionEntry, entry);
  setText(elements.aiDecisionCondition, condition);
  if (elements.aiDecisionStance) {
    const stance = String(payload?.stance || "");
    setTone(elements.aiDecisionStance, stance.includes("관망") ? -1 : stance.includes("중립") ? 0 : 1);
  }
}

function renderStockMiniChart(prices) {
  if (!elements.stockMiniChart) {
    return;
  }
  const rows = (prices || [])
    .slice()
    .reverse()
    .map((row) => ({ date: row.trade_date || row.date, close: toNumber(row.close) }))
    .filter((row) => row.close !== null)
    .slice(-80);
  if (rows.length < 2) {
    elements.stockMiniChart.innerHTML = "<p>가격 데이터 부족</p>";
    return;
  }
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
  const startDate = formatDateLabel(rows[0]?.date);
  const endDate = formatDateLabel(rows[rows.length - 1]?.date);
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
    <div><span>${formatNumber(start)}</span><strong>${formatNumber(end)}</strong></div>
    <p class="mini-chart-date-range">기준 ${startDate} ~ ${endDate} · 최근 ${formatNumber(rows.length)}거래일</p>
  `;
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
    elements.stockMiniChart.innerHTML = "<p>가격 데이터 준비 중</p>";
  }
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
    const prices = await fetchJsonCached(liveUrl(`/stocks/${encodeURIComponent(code)}/prices?limit=260`), { force: true, ttlMs: 0 });
    if (state.currentStock?.code !== code) {
      return;
    }
    state.stockPriceRows = prices || [];
    renderStockPriceSummaryFromPrices(prices, quote);
    renderStockMiniChart(prices);
  } catch {
    renderStockPriceSummaryFromPrices([], quote);
    renderStockMiniChart([]);
  }
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

function currentPresencePageKey() {
  const path = window.location.pathname || "/dashboard";
  const search = window.location.search || "";
  return `${path}${search}` || "/dashboard";
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
      if (payload?.type !== "presence") {
        return;
      }
      if (payload.page !== currentPresencePageKey()) {
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
    state.currentDashboard.quote = { ...state.currentDashboard.quote, ...quote };
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
    const sourceLabel = quoteSourceLabel(payload) || (payload.source === "kis_realtime" ? "KIS 실시간" : "보조 갱신");
    elements.meta.textContent = stockDetailMetaText({ code: payload.code, market: payload.market });
    renderStockLiveSummary({ code: payload.code, market: payload.market, as_of: payload.as_of, quote }, sourceLabel);
  }
  if (state.stockAIAnalysis) {
    renderStockStrategyVisual(state.stockAIAnalysis);
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
    card.watchDashboard = {
      ...card.watchDashboard,
      quote: {
        ...(card.watchDashboard.quote || {}),
        ...quote,
      },
    };
    const point = renderWatchPreOpenPoint(card, card.watchDashboard, card.watchDashboard.quote, card.watchItem, card.usSectorMoves || state.usSectorMoves);
    const priceRow = card.querySelector(".watch-stock-price-row");
    if (priceRow && point.nextSibling !== priceRow) {
      card.insertBefore(point, priceRow);
    }
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
    if (state.view !== "watchlist" || !elements.watchlistBody.querySelector(`[data-watch-card][data-code="${selectorEscape(code)}"]`)) {
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
    item.price = quote.price;
    const priceNode = card.querySelector('[data-field="recommend_price"]');
    if (priceNode) {
      animateQuoteNumber(priceNode, quote.price, (value) => formatNumber(Math.round(Number(value))));
    }
  }
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
    if (!["recommend", "recommend-history"].includes(state.view) || !hasTarget) {
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
    if (state.view !== "market" || state.rankingCategory !== "surge") {
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
  const timeoutMs = Number(options.timeoutMs) > 0 ? Number(options.timeoutMs) : 0;
  const now = Date.now();
  const cached = state.responseCache.get(url);
  if (!force && cached && now - cached.savedAt <= ttlMs) {
    return clonePayload(cached.payload);
  }
  if (!force && state.pendingRequests.has(url)) {
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
      state.responseCache.set(url, { savedAt: Date.now(), payload: clonePayload(payload) });
      return payload;
    })
    .finally(() => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
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
      const query = state.currentStock?.name || pathQuery();
      const shouldRefreshAI = state.stockAIAnalysis !== null || elements.aiAnalysisPanel?.hidden === false;
      await load(query);
      if (shouldRefreshAI && state.currentStock?.code) {
        await loadAIAnalysis({ auto: false });
      }
      return;
    }
    case "watchlist":
      await loadWatchlist();
      return;
    case "recommend":
      await loadRecommendations();
      return;
    case "recommend-history":
      await loadRecommendationHistory();
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
      await loadWatchCharts();
      return;
    case "chart-history":
      renderChartSnapshots();
      return;
    case "market":
      state.marketRankingCache.delete(marketRankingKey("surge", currentMarketFilter()));
      await loadMarketRankings({ market: currentMarketFilter() });
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
  elements.loginStatus.className = `login-status${tone ? ` ${tone}` : ""}`;
}

function readWatchlistActivity() {
  try {
    const parsed = JSON.parse(localStorage.getItem(WATCHLIST_ACTIVITY_KEY) || "null");
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    const id = normalizeWatchlistId(parsed.id || "");
    const at = Number(parsed.at);
    if (!id || !Number.isFinite(at) || at <= 0) {
      return null;
    }
    return { id, at };
  } catch {
    return null;
  }
}

function getWatchlistLastActive(shareId = state.watchlistId) {
  const normalizedId = normalizeWatchlistId(shareId || "");
  if (!normalizedId) {
    return null;
  }
  const activity = readWatchlistActivity();
  if (!activity || activity.id !== normalizedId) {
    return null;
  }
  return activity.at;
}

function clearWatchlistActivity() {
  window.clearTimeout(state.sessionIdleTimer);
  state.sessionIdleTimer = null;
  state.sessionLastActiveAt = 0;
  state.sessionLastSyncedAt = 0;
  state.sessionScrollTicking = false;
  localStorage.removeItem(WATCHLIST_ACTIVITY_KEY);
}

function writeWatchlistActivity(at = Date.now()) {
  if (!state.watchlistId) {
    return;
  }
  const activity = {
    id: state.watchlistId,
    at,
  };
  state.sessionLastActiveAt = at;
  state.sessionLastSyncedAt = at;
  localStorage.setItem(WATCHLIST_ACTIVITY_KEY, JSON.stringify(activity));
}

function scheduleSessionTimeout() {
  window.clearTimeout(state.sessionIdleTimer);
  state.sessionIdleTimer = null;
  if (!state.watchlistId) {
    return;
  }
  const lastActive = getWatchlistLastActive(state.watchlistId) || state.sessionLastActiveAt || Date.now();
  state.sessionLastActiveAt = lastActive;
  const remaining = SESSION_IDLE_TIMEOUT_MS - (Date.now() - lastActive);
  if (remaining <= 0) {
    logoutWatchlistIdentity({ reason: "timeout" });
    return;
  }
  state.sessionIdleTimer = window.setTimeout(() => {
    logoutWatchlistIdentity({ reason: "timeout" });
  }, remaining + 250);
}

function markWatchlistSessionActive(options = {}) {
  if (!state.watchlistId || !elements.loginGate?.hidden) {
    return;
  }
  const now = Date.now();
  state.sessionLastActiveAt = now;
  if (options.force || now - state.sessionLastSyncedAt >= SESSION_ACTIVITY_SYNC_MS) {
    writeWatchlistActivity(now);
  }
  scheduleSessionTimeout();
}

function validateWatchlistSession(shareId = state.watchlistId) {
  const normalizedId = normalizeWatchlistId(shareId || "");
  if (!normalizedId) {
    return true;
  }
  const lastActive = getWatchlistLastActive(normalizedId) || state.sessionLastActiveAt;
  if (!lastActive) {
    return true;
  }
  state.sessionLastActiveAt = lastActive;
  if (Date.now() - lastActive >= SESSION_IDLE_TIMEOUT_MS) {
    logoutWatchlistIdentity({ reason: "timeout" });
    return false;
  }
  scheduleSessionTimeout();
  return true;
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
    clearWatchlistActivity();
    if (elements.watchlistIdInput) {
      elements.watchlistIdInput.value = "";
    }
    updateWatchlistIdentityDisplay();
    if (state.view === "recommend") {
      updateRecommendationButtonState();
    }
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
  if (state.view === "recommend") {
    updateRecommendationButtonState();
  }
  setWatchlistIdStatus("서버 목록 불러오는 중");
  try {
    const localItems = readWatchlist();
    const remotePayload = await fetchRemoteWatchlist(normalizedId);
    const merged = options.merge === false ? normalizeWatchlistItems(remotePayload.items) : normalizeWatchlistItems([...localItems, ...(remotePayload.items || [])]);
    writeWatchlist(merged, { sync: false });
    await saveRemoteWatchlist(merged);
    setWatchlistIdStatus(`${normalizedId} · ${formatNumber(merged.length)}개 동기화`, "success");
    writeWatchlistActivity(Date.now());
    scheduleSessionTimeout();
    updateWatchButton();
    if (state.view === "watchlist") {
      loadWatchlist();
    } else if (state.view === "chart") {
      loadWatchCharts();
    }
    return true;
  } catch {
    setWatchlistIdStatus("동기화 실패 · ID를 확인해주세요", "error");
    return false;
  }
}

function logoutWatchlistIdentity(options = {}) {
  window.clearTimeout(state.watchlistSyncTimer);
  state.watchlistSyncTimer = null;
  state.watchlistSyncing = false;
  state.watchlistId = "";
  state.writeToken = "";
  state.writeTokenShareId = "";
  localStorage.removeItem(WATCHLIST_ID_KEY);
  localStorage.removeItem(WATCHLIST_KEY);
  clearWatchlistActivity();
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
  if (state.view === "recommend") {
    updateRecommendationButtonState();
  }
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
  const message = options.reason === "timeout"
    ? "10분 동안 동작이 없어 로그아웃되었습니다. 다시 아이디를 입력해주세요."
    : "로그아웃되었습니다. 다시 아이디를 입력해주세요.";
  showLoginGate(message, { skipSplash: true });
}

async function initializeWatchlistIdentity() {
  const savedId = normalizeWatchlistId(localStorage.getItem(WATCHLIST_ID_KEY));
  if (elements.watchlistIdInput) {
    elements.watchlistIdInput.value = savedId;
  }
  updateWatchlistIdentityDisplay();
  if (savedId) {
    const savedLastActive = getWatchlistLastActive(savedId);
    if (savedLastActive && Date.now() - savedLastActive >= SESSION_IDLE_TIMEOUT_MS) {
      state.watchlistId = savedId;
      logoutWatchlistIdentity({ reason: "timeout" });
      return;
    }
    if (elements.loginInput) {
      elements.loginInput.value = savedId;
    }
    setLoginStatus("저장된 ID로 불러오는 중");
    const [ok] = await Promise.all([
      applyWatchlistId(savedId, { merge: true }),
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
  const isOpen = document.body.classList.contains("mobile-menu-open");
  if (open === isOpen) {
    return;
  }
  if (open) {
    state.mobileMenuScrollY = window.scrollY || document.documentElement.scrollTop || 0;
    document.body.style.top = `-${state.mobileMenuScrollY}px`;
  }
  document.body.classList.toggle("mobile-menu-open", open);
  elements.mobileMenuToggle.setAttribute("aria-expanded", open ? "true" : "false");
  elements.mobileMenuToggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
  elements.mobileMenuScrim.hidden = !open;
  if (!open) {
    const scrollY = state.mobileMenuScrollY || 0;
    document.body.style.top = "";
    state.mobileMenuScrollY = 0;
    window.scrollTo(0, scrollY);
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
  navigator.serviceWorker.register("/dashboard-sw.js", { scope: "/" }).catch(() => undefined);
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

function setView(view) {
  state.view = view;
  setFlowLoading(false);
  hideSuggestions();
  if (view !== "stock") {
    closeQuoteStream();
  }
  if (view !== "watchlist") {
    closeWatchlistQuoteStreams();
  }
  if (view !== "market") {
    closeMarketQuoteStreams();
  }
  if (!["recommend", "recommend-history"].includes(view)) {
    closeRecommendationQuoteStreams();
  }
  if (view !== "recommend") {
    window.clearTimeout(state.recommendationCooldownTimer);
    state.recommendationCooldownTimer = null;
  }
  if (!["watchlist", "recommend"].includes(view)) {
    closeUsSectorStream();
  }
  elements.stockView.hidden = view !== "stock";
  elements.watchlistView.hidden = view !== "watchlist";
  elements.recommendView.hidden = view !== "recommend";
  elements.recommendHistoryView.hidden = view !== "recommend-history";
  elements.trendView.hidden = !["trend", "trend-past", "trend-impact"].includes(view);
  elements.chartView.hidden = view !== "chart";
  elements.chartHistoryView.hidden = view !== "chart-history";
  elements.marketView.hidden = view !== "market";
  const activeView = view === "chart-history" ? "chart" : view;
  for (const item of elements.sideItems) {
    item.classList.toggle("active", item.dataset.view === activeView);
  }
  for (const group of document.querySelectorAll(".side-menu-group")) {
    group.classList.toggle("has-active", Boolean(group.querySelector(".side-menu-item.active")));
  }
  if (view === "market") {
    history.replaceState(null, "", "/dashboard?view=market");
    loadMarketRankings(pageEntryRefreshOptions("market", currentMarketFilter()));
  } else if (view === "watchlist") {
    history.replaceState(null, "", "/dashboard?view=watchlist");
    loadWatchlist(pageEntryRefreshOptions("watchlist"));
  } else if (view === "recommend") {
    history.replaceState(null, "", "/dashboard?view=recommend");
    updateRecommendationButtonState();
    const entryOptions = pageEntryRefreshOptions("recommend");
    refreshUsSectorMoves(entryOptions);
    refreshVisibleRecommendationCards(entryOptions);
    const shouldAutoLoadRecommendations = entryOptions.force || !elements.recommendList.querySelector(".recommend-card");
    if (shouldAutoLoadRecommendations && !state.recommendationLoading) {
      loadRecommendations({ auto: true, force: entryOptions.force });
    }
    connectUsSectorStream();
  } else if (view === "recommend-history") {
    history.replaceState(null, "", "/dashboard?view=recommend-history");
    loadRecommendationHistory(pageEntryRefreshOptions("recommend-history"));
  } else if (view === "trend") {
    history.replaceState(null, "", "/dashboard?view=trend");
    loadTrends("events", pageEntryRefreshOptions("trend", "events"));
  } else if (view === "trend-past") {
    history.replaceState(null, "", "/dashboard?view=trend-past");
    loadTrends("past", pageEntryRefreshOptions("trend-past", "past"));
  } else if (view === "trend-impact") {
    history.replaceState(null, "", "/dashboard?view=trend-impact");
    loadMarketImpactAnalysis(pageEntryRefreshOptions("trend-impact"));
  } else if (view === "chart") {
    history.replaceState(null, "", "/dashboard?view=chart");
    loadWatchCharts(pageEntryRefreshOptions("chart"));
  } else if (view === "chart-history") {
    history.replaceState(null, "", "/dashboard?view=chart-history");
    renderChartSnapshots();
  }
  sendPresencePage();
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
  card.dataset.code = item.code;

  const main = document.createElement("section");
  main.className = "market-leaderboard-main";

  const rank = document.createElement("span");
  rank.className = "market-rank-badge";
  rank.textContent = String(item.rank || "-");

  const quoteBlock = document.createElement("div");
  quoteBlock.className = "market-leaderboard-quote-block";

  const name = document.createElement("a");
  name.className = "market-leaderboard-name";
  name.href = viewStockUrl(item.name);

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

  quoteBlock.append(rank, price);

  const summary = document.createElement("div");
  summary.className = "market-leaderboard-summary";
  summary.append(name, change);

  main.append(quoteBlock, summary);

  const strip = document.createElement("section");
  strip.className = "quote-strip market-leaderboard-strip";
  strip.append(
    createWatchMetric("거래대금", formatMoney(item.trading_value)),
    createWatchMetric("1개월", formatPercent(item.one_month_return), "", item.one_month_return),
    createWatchMetric("3개월", formatPercent(item.three_month_return), "", item.three_month_return)
  );

  card.append(main, strip);
  return card;
}

function renderMarketSurgeLeaderboard(options = {}) {
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
  state.marketLeaderboardAsOf = payload.as_of || "";
  state.marketLeaderboardTradeDate = state.marketLeaderboardItems.find((item) => item.trade_date)?.trade_date || "";
  sortMarketLeaderboardItems();
  renderMarketSurgeLeaderboard();
  for (const item of state.marketLeaderboardItems) {
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

function currentMarketFilter() {
  return elements.marketTabs.find((tab) => tab.classList.contains("active"))?.dataset.marketFilter || "KOSPI";
}

function setMarketFilter(market) {
  const normalized = market === "KOSDAQ" ? "KOSDAQ" : "KOSPI";
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
  return category === "surge" ? "급상승" : elements.rankTabs.find((tab) => tab.dataset.category === category)?.textContent?.trim() || category;
}

function requestMarketRanking(category, market, options = {}) {
  const normalizedCategory = "surge";
  const key = marketRankingKey(normalizedCategory, market);
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
    limit: "20",
  });
  params.set("market", market);
  const url = `/market/rankings?${params.toString()}`;
  const promise = fetchJsonCached(url, {
    force,
    ttlMs: force ? 0 : ttlMs,
    timeoutMs: 12_000,
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
  const force = options.force === true;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("market");
  setMarketLeaderboardMode(category === "surge");
  const key = marketRankingKey(category, market);
  const cached = state.marketRankingCache.get(key);
  if (!force && cached?.payload && Date.now() - (cached.savedAt || 0) <= ttlMs) {
    renderRankings(cached.payload);
    return;
  }
  closeMarketQuoteStreams();
  renderRankingMessage("불러오는 중");
  try {
    const payload = await requestMarketRanking(category, market, { force, ttlMs });
    if (state.view === "market" && state.rankingCategory === category && currentMarketFilter() === market) {
      renderRankings(payload);
    }
  } catch {
    if (state.view === "market" && state.rankingCategory === category && currentMarketFilter() === market) {
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

function createWatchInsight(label, value, tone = "muted") {
  const item = document.createElement("article");
  item.className = `watch-insight-card ${tone}`;
  const labelNode = document.createElement("span");
  labelNode.textContent = label;
  const valueNode = document.createElement("strong");
  valueNode.textContent = value;
  item.append(labelNode, valueNode);
  return item;
}

async function loadUsSectorMoves(options = {}) {
  if (!options.force && state.usSectorMoves) {
    return state.usSectorMoves;
  }
  try {
    const url = "/market/us-sector-moves?refresh=1";
    const payload = await fetchJsonCached(url, { force: options.force === true, ttlMs: 5 * 60 * 1000 });
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
  if (!("WebSocket" in window) || !["watchlist", "recommend"].includes(state.view)) {
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
    if (!["watchlist", "recommend"].includes(state.view)) {
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
  if (!["watchlist", "recommend"].includes(state.view)) {
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
    const priceRow = card.querySelector(".watch-stock-price-row");
    if (priceRow && point.nextSibling !== priceRow) {
      card.insertBefore(point, priceRow);
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

  const header = el("div", "watchlist-report-head");
  const titleBlock = el("div", "watchlist-report-title");
  titleBlock.append(el("p", "", "AI 시황 리포트"), el("h2", "", headline));
  const phaseBadge = el("span", `watchlist-report-phase ${usTone}`, `${phase.label} / ${phase.usLabel}`);
  header.append(titleBlock, phaseBadge);

  const actionBlock = el("section", "watchlist-report-action");
  actionBlock.append(el("span", "", "지금 확인"), el("strong", "", action));

  const signals = el("div", "watchlist-report-signals");
  for (const factor of majorFactors) {
    signals.append(el("span", factor.direction === "호재" ? "positive" : factor.direction === "악재" ? "negative" : "muted", `${factor.label} ${factor.direction}`));
  }
  if (importantEvent) {
    signals.append(el("span", "event", `주요 이벤트 · ${importantEvent.title.replace("미국 ", "")}`));
  }
  const news = marketNews ? el("p", "watchlist-report-news", marketNews.title) : null;

  const monitorBlock = el("section", "watchlist-monitoring");
  const monitorHead = el("div", "watchlist-monitoring-head");
  monitorHead.append(el("h3", "", "모니터링 우선"), el("span", "", `관심 ${valid.length}개 · 하락 ${negativeCount}개`));
  const monitorList = el("div", "watchlist-monitoring-list");
  for (const [index, item] of monitoring.entries()) {
    const row = document.createElement("a");
    row.className = "watchlist-monitor-row";
    row.href = viewStockUrl(item.item.name);
    const rank = el("span", "watchlist-monitor-rank", String(index + 1));
    const name = el("strong", "", item.item.name);
    const reason = el("span", toNumber(item.relatedAverage) < 0 ? "negative" : "muted", item.reason);
    row.append(rank, name, reason);
    monitorList.appendChild(row);
  }
  monitorBlock.append(monitorHead, monitorList);
  const footnote = el("p", "watchlist-report-note", "이벤트·뉴스·거시·수급·미국 섹터를 종합해 우선순위를 계산합니다.");
  const reportNodes = [header, actionBlock, signals];
  if (news) {
    reportNodes.push(news);
  }
  reportNodes.push(monitorBlock, footnote);
  section.replaceChildren(...reportNodes);
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
      title = "강세 진행";
      tone = "positive";
    } else if (changeRate <= -1) {
      title = "약세 경계";
      tone = "negative";
    } else {
      title = "보합권 탐색";
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
      title = "강세 마감";
      tone = "positive";
    } else if (changeRate <= -1) {
      title = "약세 마감";
      tone = "negative";
    } else {
      title = "보합권 마감";
    }
    addPoint(flowPoint || "수급 방향 확인 중");
    addPoint(trendPoint);
    addPoint(newsPoint);
    addPoint(`거시 ${macroView.label}`);
    return { label, title, tone, points: points.slice(0, 4), collapsed, mode: phase, hint: "" };
  }

  if (preRate !== null) {
    if (preRate >= 1) {
      title = "상승 출발 체크";
      tone = "positive";
    } else if (preRate <= -1) {
      title = "하락 출발 주의";
      tone = "negative";
    } else {
      title = quote.pre_market_status === "장전 호가 대기" ? "장전 호가 대기" : "보합 출발 관찰";
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
    section.className = "watch-preopen-point";
    section.dataset.field = "preopen_point";
    section.addEventListener("toggle", () => {
      const code = section.dataset.code || "";
      if (!code || section.dataset.mode !== "regular") {
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
  if (point.mode !== "regular" && itemCode) {
    state.watchPreopenExpanded.delete(itemCode);
  }
  const keepExpanded = point.mode === "regular" && itemCode ? state.watchPreopenExpanded.has(itemCode) : false;
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
  section.replaceChildren(summary, list, createWatchUsSectorStrip(item, dashboard, usSectorMoves));
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
  message.textContent = text;
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
  card.className = "watch-stock-card";
  card.dataset.code = item.code;
  card.dataset.watchCard = "true";
  card.watchDashboard = dashboard;
  card.watchItem = item;
  card.usSectorMoves = usSectorMoves;

  const header = document.createElement("div");
  header.className = "watch-stock-head";
  const link = document.createElement("a");
  link.className = "watch-stock-name";
  link.href = viewStockUrl(item.name);
  const strong = document.createElement("strong");
  strong.textContent = item.name;
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
  link.append(strong, meta);

  const removeButton = document.createElement("button");
  removeButton.className = "remove-watch";
  removeButton.type = "button";
  removeButton.textContent = "관심 해제";
  removeButton.dataset.code = item.code;
  header.append(link, removeButton);

  const metrics = document.createElement("section");
  metrics.className = "quote-strip watch-quote-strip";
  metrics.append(
    createWatchMetric("거래대금", formatMoney(dashboard.quote.trading_value), "trading_value"),
    createWatchMetric("1개월", formatPercent(dashboard.momentum.one_month_return), "one_month", dashboard.momentum.one_month_return),
    createWatchMetric("3개월", formatPercent(dashboard.momentum.three_month_return), "three_month", dashboard.momentum.three_month_return),
    createWatchMetric("뉴스", formatPercent(dashboard.sentiment.score), "sentiment", dashboard.sentiment.score)
  );

  const valuationView = interpretValuation(dashboard);
  const macroView = interpretMacro(dashboard);
  const preOpenPoint = renderWatchPreOpenPoint(card, dashboard, null, item, usSectorMoves);
  const insights = document.createElement("section");
  insights.className = "watch-insight-grid";
  insights.append(
    createWatchInsight("밸류 판단", valuationView.label, valuationView.tone),
    createWatchInsight("거시 판단", macroView.label, macroView.tone)
  );

  card.append(header, preOpenPoint, metrics, insights);
  elements.watchlistBody.appendChild(card);
}

async function loadWatchlist(options = {}) {
  const force = options.force !== false;
  const ttlMs = options.ttlMs ?? pageEntryTtlMs("watchlist");
  closeWatchlistQuoteStreams();
  const items = readWatchlist();
  elements.watchlistMeta.textContent = `${items.length}개 종목`;
  elements.watchlistBody.innerHTML = "";
  showWatchlistLoadingOverlay();
  if (!items.length) {
    clearWatchlistLoadingOverlay();
    state.watchlistResults = [];
    renderWatchlistStrategy();
    renderWatchlistMessage("관심 종목 없음");
    return;
  }
  const sectorMovesPromise = refreshUsSectorMoves({ force });
  const marketContextPromise = refreshWatchlistMarketContext({ force });
  const results = await Promise.all(
    items.map(async (item) => {
      try {
        const url = `/stocks/${encodeURIComponent(item.code)}/dashboard?refresh=1`;
        return { item, dashboard: await fetchJsonCached(url, { force, ttlMs: force ? 0 : ttlMs }) };
      } catch {
        return { item, dashboard: null };
      }
    })
  );
  clearWatchlistLoadingOverlay();
  state.watchlistResults = results.filter((result) => result.dashboard);
  renderWatchlistStrategy(state.watchlistResults, state.usSectorMoves, state.watchlistMarketContext);
  for (const result of results) {
    if (result.dashboard) {
      appendWatchRow(result.item, result.dashboard, state.usSectorMoves);
      connectWatchlistQuoteStream(result.item.code);
    }
  }
  connectUsSectorStream();
  sectorMovesPromise.catch(() => {});
  marketContextPromise.catch(() => {});
  if (!elements.watchlistBody.children.length) {
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
      el("span", "", `${formatDate(snapshot.saved_at)} · 점수 ${formatNumber(snapshot.score)} · 현재가 ${formatNumber(snapshot.price)}`)
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
  card.append(head, chartWrap, legend, metrics, indicators, checklist, notes);
  return card;
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

function renderWatchChartList(results) {
  clearWatchChartLoadingOverlay();
  state.selectedWatchChartCode = "";
  elements.watchChartList.innerHTML = "";
  const available = results.filter((result) => result.dashboard && result.prices?.length && result.analysis);
  if (!available.length) {
    renderWatchChartMessage("차트 데이터를 불러오지 못했습니다.", "잠시 후 다시 들어오거나 종목 카드의 새로고침을 눌러주세요.");
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
    const price = el("span", "watch-chart-row-price", formatNumber(analysis.latest?.close));
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
    clearCachedUrl(`/stocks/${encodeURIComponent(code)}/prices?limit=180`);
    clearCachedUrl(`/stocks/${encodeURIComponent(code)}/dashboard?refresh=1`);
    const [prices, dashboard] = await Promise.all([
      fetchJsonCached(liveUrl(`/stocks/${encodeURIComponent(code)}/prices?limit=180`), { force: true, ttlMs: 0 }),
      fetchJsonCached(liveUrl(`/stocks/${encodeURIComponent(code)}/dashboard?refresh=1`), { force: true, ttlMs: 0 }),
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
    renderWatchChartMessage("관심 종목이 없습니다.", "종목 검색에서 관심 종목을 추가하면 이곳에 AI 차트 분석 리스트가 표시됩니다.");
    return;
  }
  showWatchChartLoadingOverlay();
  setWatchChartMetaLoading(items.length, 0);
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
          const [prices, dashboard] = await Promise.race([
            Promise.all([
              fetchJsonCached(`/stocks/${encodeURIComponent(item.code)}/prices?limit=180`, { force, ttlMs: force ? 0 : ttlMs }),
              fetchJsonCached(`/stocks/${encodeURIComponent(item.code)}/dashboard?refresh=1`, { force, ttlMs: force ? 0 : ttlMs }),
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
      }
    );
    state.watchChartResults = results;
    setWatchChartMetaText(`관심종목 ${formatNumber(items.length)}개`);
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
  setText(elements.stockStrategyStatus, "AI 분석을 불러오면 현재가 근처의 가격 기준을 표시합니다.");
  setText(elements.stockStrategyStance, "-");
  if (elements.stockPriceLadder) {
    elements.stockPriceLadder.innerHTML = '<p class="muted">전략 가격대 대기 중</p>';
  }
}

function renderAIAnalysis(payload) {
  state.stockAIAnalysis = payload;
  state.stockAIRequestedCode = payload.code;
  elements.aiAnalysisPanel.hidden = false;
  const coverage = aiDataCoverage(payload);
  elements.aiAnalysisMeta.textContent = `${payload.name} · 분석 데이터 ${coverage} · ${formatDate(payload.generated_at)}`;
  elements.aiAnalysisStance.textContent = payload.stance || "-";
  elements.aiAnalysisSummary.textContent = payload.summary || "";
  setText(elements.stockSummaryStance, payload.stance || "-");
  setText(elements.stockSummaryLine, payload.summary || elements.stockSummaryLine?.textContent || "");
  setText(elements.stockSummaryConfidence, coverage);
  setText(elements.stockAISayConfidence, `분석 데이터 ${coverage}`);
  setText(elements.stockAISayText, payload.summary || "AI 분석 요약을 생성하지 못했습니다.");
  const stance = payload.stance || "";
  setTone(elements.aiAnalysisStance, stance.includes("관망") ? -1 : stance.includes("중립") ? 0 : 1);
  renderAIDecisionSummary(payload);
  appendListItems(elements.aiKeyPoints, payload.key_points, "핵심 판단을 만들 데이터가 부족합니다.");
  appendListItems(elements.aiStrategy, payload.strategy, "매매 시나리오를 만들 데이터가 부족합니다.");
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
  const normalizedOptions = options && options.auto === true ? options : {};
  const forceRefresh = !normalizedOptions.auto;
  const originalMainText = elements.aiAnalysisButton?.textContent || "AI 분석하기";
  const originalInlineText = elements.stockInlineAIRefresh?.textContent || "AI 분석 갱신하기";
  state.stockAILoading = true;
  setAIAnalysisButtonsLoading(true);
  elements.aiAnalysisPanel.hidden = false;
  elements.aiAnalysisMeta.textContent = `${state.currentStock.name} · 분석 중`;
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
  elements.recommendHistoryMeta.textContent = tracks.length ? `종목 ${formatNumber(tracks.length)}개 추적 중` : "추적 종목 없음";
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
    el("span", "", `${track.code || "-"} · ${track.market || "-"}`)
  );
  const actions = el("div", "recommend-track-actions");
  const open = document.createElement("a");
  open.className = "snapshot-button";
  open.href = viewStockUrl(track.name || track.code || "");
  open.textContent = "종목 상세";
  const remove = el("button", "snapshot-delete track-delete", "추적 해제");
  remove.type = "button";
  remove.dataset.trackId = track.id || "";
  actions.append(open, remove);
  head.append(title, actions);

  const metrics = el("div", "recommend-track-metrics");
  const metricRows = [
    ["추적 단가", trackedPrice !== null ? formatNumber(trackedPrice) : "-", "", trackedPrice],
    ["현재 단가", currentPrice !== null ? formatNumber(currentPrice) : "불러오는 중", "tracked_current_price", currentPrice],
    ["주당 손익", profit.value !== null ? formatChangeValue(profit.value) : "-", "tracked_pnl_value", profit.value],
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
    el("p", "", track.ai?.summary || `${track.name || "종목"} 추적 시점 요약이 아직 없습니다.`)
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
    animateQuoteNumber(currentPriceNode, quote.price, (value) => formatNumber(Math.round(Number(value))));
  }
  const profit = recommendationTrackProfit(trackedPrice, quote.price);
  if (pnlValueNode && profit.value !== null) {
    animateQuoteNumber(pnlValueNode, profit.value, formatChangeValue);
    setLiveCellTone(pnlValueNode, profit.value);
  }
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
    elements.recommendHistoryList.appendChild(el("p", "muted", "추천 카드에서 종목별 추적하기를 누르면, 누른 시점의 주당 단가와 현재 손익률을 여기서 바로 비교할 수 있습니다."));
    return;
  }
  for (const track of tracks) {
    elements.recommendHistoryList.appendChild(createRecommendationTrackCard(track));
    connectRecommendationQuoteStream(track.code);
  }
  await Promise.all(
    tracks.map(async (track) => {
      try {
        const dashboard = await fetchJsonCached(`/stocks/${encodeURIComponent(track.code)}/dashboard?refresh=1`, { force, ttlMs: force ? 0 : ttlMs });
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
    })
  );
}

function setRecommendStatus(message = "") {
  elements.recommendStatus.textContent = message;
  elements.recommendStatus.parentElement.hidden = !message;
}

function koreaDateKey(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function recommendationCooldownStorageKey() {
  return `${RECOMMENDATION_COOLDOWN_KEY}:${state.watchlistId || "guest"}`;
}

function recommendationCooldownMs(date = new Date()) {
  return koreaMarketPhase(date) === "regular"
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
    if (!record || record.dayKey !== koreaDateKey()) {
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
    dayKey: koreaDateKey(now),
    generatedAt,
    cooldownUntil: generatedAt + durationMs,
    durationMs,
    phase: koreaMarketPhase(now),
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
  const url = `/stocks/${encodeURIComponent(item.code)}/dashboard?refresh=1`;
  clearCachedUrl(url);
  clearCachedUrl(`/stocks/${encodeURIComponent(item.code)}/dashboard`);
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
      const dashboard = await fetchJsonCached(`/stocks/${encodeURIComponent(item.code)}/dashboard?refresh=1`, { force: true, ttlMs: 0 });
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

  const nearbySupport = price && support && support < price && support >= price * 0.9 ? support : null;
  const nearbyResistance = price && resistance && resistance > price ? resistance : null;
  const entryLow = price ? Math.max(nearbySupport || 0, Math.round(price * 0.985 / 100) * 100) : null;
  const entryHigh = price ? Math.round(price * 1.005 / 100) * 100 : null;
  const breakout = price ? Math.round(Math.max(nearbyResistance || 0, price * 1.025) / 100) * 100 : null;
  const reduce = price ? Math.round(Math.max((nearbySupport || 0) * 0.985, price * 0.965) / 100) * 100 : null;
  const target = price ? Math.round(Math.max(nearbyResistance || 0, price * 1.04) / 100) * 100 : null;

  const summary =
    decision === "매수"
      ? `${item.name}은 지금 바로 크게 따라가기보다 ${formatNumber(entryLow)}~${formatNumber(entryHigh)} 구간에서 나눠 담는 쪽이 현실적입니다.`
      : decision === "매도"
        ? `${item.name}은 추천 점수나 차트 흐름이 약해져서 새 매수보다 보유 비중을 줄이는 판단이 우선입니다.`
        : `${item.name}은 관심 종목으로 볼 수 있지만, 현재 판단은 매수 실행보다 관찰이 우선입니다. 가격이 안정되거나 돌파 전환가를 넘을 때만 접근합니다.`;

  const plain = [
    `현재가는 ${formatNumber(price)}이고 오늘 등락률은 ${formatPercent(change)}입니다.`,
    `최근 1개월 수익률은 ${formatPercent(oneMonth)}, 3개월 수익률은 ${formatPercent(threeMonth)}입니다. 이미 많이 오른 종목은 좋은 종목이어도 한 번에 사면 손실 구간을 크게 맞을 수 있습니다.`,
    `추천 점수는 ${formatNumber(score)}점이고 AI 차트 점수는 ${formatNumber(chartScore)}점입니다. 점수는 “좋은 기업인가”보다 “지금 가격에서 행동하기 쉬운가”에 가깝게 봅니다.`,
  ];
  if (valuationScore !== null) {
    plain.push(`밸류에이션 점수는 ${formatNumber(valuationScore)}점입니다. 낮으면 가격 부담이 크다는 뜻이고, 높으면 현재 가격이 과거와 비교해 덜 부담스럽다는 뜻입니다.`);
  }
  if (flowsScore !== null) {
    plain.push(`수급 점수는 ${formatNumber(flowsScore)}점입니다. 외국인과 기관의 매수세가 함께 들어오면 가격이 버티는 힘이 좋아질 수 있습니다.`);
  }
  if (sentimentScore !== null) {
    plain.push(`뉴스 분위기 점수는 ${formatNumber(sentimentScore)}점입니다. 좋은 뉴스가 많아도 가격에 이미 반영된 경우가 있으니 가격 위치와 함께 봐야 합니다.`);
  }

  const timing = [
    price
      ? decision === "매수"
        ? `현실적인 1차 매수 구간: ${formatNumber(entryLow)}~${formatNumber(entryHigh)}. 이 구간에서 가격이 밀리지 않을 때만 나눠 담습니다.`
        : `관찰 가격대: ${formatNumber(entryLow)}~${formatNumber(entryHigh)}. 현재 판단에서는 실행 구간이 아니라 가격이 버티는지 보는 기준입니다.`
      : "현재가 데이터가 부족해서 가격대를 숫자로 잡기 어렵습니다.",
    breakout ? `매수 전환가: ${formatNumber(breakout)} 이상. 이 가격 위에서 거래대금이 늘 때만 소액 접근합니다.` : "돌파 가격은 저항선 데이터가 부족해 계산하지 않았습니다.",
    reduce ? `손실을 줄일 가격: ${formatNumber(reduce)} 아래. 이 가격 아래에서는 생각이 틀렸다고 보고 비중을 줄이는 기준으로 삼습니다.` : "손실 제한 가격은 지지선 데이터가 부족해 계산하지 않았습니다.",
    target ? `1차 이익실현 참고 가격: ${formatNumber(target)} 부근. 욕심내기보다 일부 수익을 잠그는 구간으로 봅니다.` : "이익실현 가격은 저항선 데이터가 부족해 계산하지 않았습니다.",
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
  name.href = viewStockUrl(item.name);
  const nameStrong = el("strong", "", item.name);
  const nameMeta = el("span", "", `${item.code} · ${item.market}`);
  name.append(nameStrong, nameMeta);

  const score = el("div", "recommend-score");
  score.append(el("strong", "", String(item.score)), el("span", "", "점"));

  const metrics = el("div", "recommend-metrics");
  const metricRows = [
    ["현재가", formatNumber(item.price), "recommend_price", item.price],
    ["등락률", formatPercent(item.change_rate), "recommend_change_rate", item.change_rate],
    ["1개월", formatPercent(item.one_month_return), "", item.one_month_return],
    ["3개월", formatPercent(item.three_month_return), "", item.three_month_return],
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
    ["지지", chart.support ? `${formatNumber(chart.support)} (${formatPercent(chart.distance_to_support)})` : "-"],
    ["저항", chart.resistance ? `${formatNumber(chart.resistance)} (${formatPercent(chart.distance_to_resistance)})` : "-"],
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
  const recommendMetaText = payload.as_of ? `기준 시간 : ${formatDate(payload.as_of)}` : "";
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
  const summary = el("p", "", factor.interpretation || factor.summary || "현재 공식 지표 기준으로 영향 방향을 계산했습니다.");
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
    evidenceGrid.appendChild(el("p", "muted", "공식 지표 수집 대기 중"));
  }
  const sectorWrap = el("div", "market-impact-tag-block");
  sectorWrap.appendChild(el("span", "", "영향 업종"));
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
    tag.href = viewStockUrl(stock);
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

function setTrendImpactChrome({ loading = false } = {}) {
  if (elements.trendTitle) {
    elements.trendTitle.textContent = "시장 영향도 분석";
  }
  if (elements.trendTabsWrap) {
    elements.trendTabsWrap.hidden = true;
  }
  if (elements.trendSummary) {
    elements.trendSummary.hidden = true;
  }
  if (elements.trendEventsTitle) {
    elements.trendEventsTitle.hidden = true;
    elements.trendEventsTitle.textContent = loading ? "시장 영향도 계산 중" : "";
  }
  elements.trendEventsPanel.hidden = false;
  elements.trendLivePanel.hidden = true;
  elements.trendPastPanel.hidden = true;
}

function restoreTrendChrome(activeTab = "events", headline = "") {
  if (elements.trendTitle) {
    elements.trendTitle.textContent = activeTab === "past" ? "지난 이벤트" : "트렌드 분석";
  }
  if (elements.trendTabsWrap) {
    elements.trendTabsWrap.hidden = false;
  }
  if (elements.trendSummary) {
    elements.trendSummary.hidden = false;
  }
  if (elements.trendEventsTitle) {
    elements.trendEventsTitle.hidden = false;
    elements.trendEventsTitle.textContent = activeTab === "past" ? "지난 이벤트" : "이벤트 캘린더";
  }
  elements.trendHeadline.textContent = headline;
}

function renderMarketImpactAnalysis(payload) {
  const model = normalizeMarketImpactModel(payload);
  const fallback = isFallbackMarketImpact(model);
  setTrendImpactChrome();
  elements.trendHeadline.textContent = "";
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
  centerContent.append(el("span", "", "국내증시"), el("strong", "", model.marketStatus), el("small", "", `기준 ${formatDate(model.asOf)}`));
  center.append(centerContent);
  orbit.append(center);
  const slotOrder = ["rate", "dollar", "bond", "commodity", "risk"];
  const orderedFactors = [...model.factors].sort((a, b) => slotOrder.indexOf(a.key) - slotOrder.indexOf(b.key));
  orderedFactors.forEach((factor, index) => appendMarketImpactNode(orbit, factor, index + 1));
  const heroCopy = el("div", "market-impact-copy");
  const heroSummary = fallback ? "공식 지표 수집이 지연되어 기본 리스크 분포를 표시 중입니다." : model.summary;
  const heroMeta = fallback ? "일부 지표 연결 후 자동으로 다시 계산됩니다." : `호재 축 ${model.goodWeight.toFixed(1)}% · 악재 축 ${model.badWeight.toFixed(1)}%`;
  heroCopy.append(el("span", "section-eyebrow", fallback ? "임시 상태" : "마켓 밸런스"), el("h2", "", heroSummary), el("p", "", heroMeta));
  hero.append(orbit, heroCopy);

  const flow = el("section", "market-impact-flow");
  const flowTitle = el("div", "market-impact-flow-title");
  flowTitle.append(el("strong", "", "현재 흐름"), el("span", "", "외부 변수 → 국내증시 → 영향 종목"));
  const flowGrid = el("div", "market-impact-flow-grid");
  const leadingFactors = model.factors.slice(0, 3);
  for (const factor of leadingFactors) {
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
      button.textContent = "흐름 보기";
    }
  }
}

function renderTrends(payload, activeTab = "events") {
  restoreTrendChrome(activeTab, payload.headline || "다가오는 주요 이벤트를 확인해보세요.");
  elements.trendEvents.innerHTML = "";
  elements.trendPastEvents.innerHTML = "";
  elements.trendThread.innerHTML = "";
  setTrendTab(activeTab);
  const events = focusedTrendEvents(payload.events);
  const pastEvents = focusedTrendEvents(payload.past_events);
  const timeline = (payload.timeline || []).filter(isFocusedTrendTimelineItem);

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

async function loadTrends(activeTab = state.view === "trend-past" ? "past" : "events", options = {}) {
  restoreTrendChrome(activeTab, "다가오는 이벤트와 최신 타임라인을 정리하는 중입니다.");
  try {
    const force = options.force === true;
    const ttlMs = options.ttlMs ?? pageEntryTtlMs(activeTab === "past" ? "trend-past" : "trend");
    const url = "/market/trends?days=7";
    renderTrends(await fetchJsonCached(url, { force, ttlMs: force ? 0 : ttlMs }), activeTab);
  } catch {
    elements.trendHeadline.textContent = "트렌드 데이터를 불러오지 못했습니다.";
  }
}

async function loadMarketImpactAnalysis(options = {}) {
  setTrendImpactChrome({ loading: true });
  elements.trendHeadline.textContent = "";
  elements.trendEvents.innerHTML = "";
  elements.trendEvents.appendChild(el("p", "muted", "외부 지표를 수집하고 영향도를 계산하는 중입니다."));
  try {
    const force = options.force === true;
    const ttlMs = options.ttlMs ?? pageEntryTtlMs("trend-impact");
    const url = force ? liveUrl("/market/impact?refresh=true") : "/market/impact";
    const payload = await fetchJsonCached(url, { force, ttlMs: force ? 0 : ttlMs });
    renderMarketImpactAnalysis(payload);
  } catch {
    try {
      const fallbackPayload = await fetchJsonCached("/market/trends?days=7", { force: true, ttlMs: 0 });
      renderMarketImpactAnalysis(fallbackPayload);
    } catch {
      setTrendImpactChrome();
      elements.trendHeadline.textContent = "";
      elements.trendEvents.innerHTML = "";
      elements.trendEvents.appendChild(el("p", "muted", "시장 영향도 데이터 없음"));
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
      : "가격, 거래대금, 추정치, 밸류, 수급, 뉴스 데이터를 새로 점수화하는 중입니다.",
  );
  elements.recommendList.innerHTML = "";
  const sectorMovesPromise = refreshUsSectorMoves(options);
  const fetchRecommendations = () => {
    const baseUrl = `/market/recommendations?limit=${RECOMMENDATION_LIMIT}&candidate_limit=45${recompute ? "&refresh=1" : ""}`;
    const requestUrl = forceFetch ? liveUrl(baseUrl) : baseUrl;
    return fetchJsonCached(requestUrl, forceFetch ? { force: true, ttlMs: 0 } : {});
  };
  try {
    const payload = await fetchRecommendations();
    renderRecommendations(payload, { save: saveSnapshot, usSectorMoves: state.usSectorMoves });
    if (!auto && (payload.items || []).length > 0) {
      saveRecommendationCooldown();
    }
  } catch {
    setRecommendStatus(auto ? "추천 데이터를 다시 불러오는 중입니다." : "추천 데이터를 다시 시도하는 중입니다.");
    try {
      await delay(auto ? 500 : 1200);
      const payload = await fetchRecommendations();
      renderRecommendations(payload, { save: saveSnapshot, usSectorMoves: state.usSectorMoves });
      if (!auto && (payload.items || []).length > 0) {
        saveRecommendationCooldown();
      }
    } catch {
      setRecommendStatus(
        auto
          ? "추천 데이터를 불러오지 못했습니다. 잠시 후 다시 들어와주세요."
          : "추천 데이터를 계산하지 못했습니다. 잠시 후 다시 눌러주세요.",
      );
    }
  } finally {
    sectorMovesPromise.catch(() => {});
    connectUsSectorStream();
    state.recommendationLoading = false;
    updateRecommendationButtonState();
  }
}

function setLoading(code) {
  state.currentStock = null;
  state.currentDashboard = null;
  state.stockAIAnalysis = null;
  state.stockAIRequestedCode = "";
  state.stockPriceRows = [];
  elements.name.textContent = "종목 분석";
  elements.meta.textContent = `${code} · 불러오는 중`;
  setText(elements.stockPreMarket, "장전 -");
  resetAIAnalysis();
  resetStockPriceSummary();
  setActiveStockTab("summary", { preserveScroll: true });
}

function render(data) {
  const previousCode = state.currentStock?.code;
  state.currentStock = { code: data.code, name: data.name, market: data.market };
  state.currentDashboard = data;
  state.stockAIAnalysis = null;
  state.stockAIRequestedCode = "";
  resetAIAnalysis();
  setActiveStockTab("summary", { preserveScroll: true });
  elements.name.textContent = data.name;
  elements.meta.textContent = stockDetailMetaText(data);
  elements.input.value = data.name;
  if (previousCode !== data.code) {
    for (const node of [elements.quotePrice, elements.stockChangeValue, elements.quoteChange, elements.quoteValue, elements.quoteCap]) {
      delete node.dataset.rawValue;
    }
  }

  renderStockLiveSummary(data);
  updateQuoteStrip(data.quote);
  renderStockResearchSummary(data);
  renderStockDerivedIndicators(data);
  renderStockSummaryFallback(data);
  renderEvidenceSummary(data);
  loadStockPriceSummary(data.code, data.quote);
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

async function load(query) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    return;
  }
  hideSuggestions();
  setLoading(normalized);
  const stock = await resolveStock(normalized);
  if (!stock) {
    elements.name.textContent = "종목 분석";
    elements.meta.textContent = `${normalized} · 데이터 없음`;
    closeQuoteStream();
    resetAIAnalysis();
    return;
  }
  try {
    render(await fetchJsonCached(liveUrl(`/stocks/${encodeURIComponent(stock.code)}/dashboard?refresh=1`), { force: true, ttlMs: 0 }));
  } catch {
    elements.name.textContent = stock.name;
    elements.meta.textContent = `${stock.code} · 데이터 없음`;
    closeQuoteStream();
    resetAIAnalysis();
    return;
  }
  history.replaceState(null, "", `/dashboard/${encodeURIComponent(stock.name)}`);
  setView("stock");
}

for (const item of elements.sideItems) {
  item.addEventListener("click", () => {
    if (item.dataset.view === "stock") {
      const query = state.currentStock?.name || pathQuery();
      const entryOptions = pageEntryRefreshOptions("stock", state.currentStock?.code || query);
      if (state.currentStock?.name && !entryOptions.force) {
        setView("stock");
      } else {
        load(query);
      }
    } else {
      setView(item.dataset.view);
    }
    setMobileMenu(false);
  });
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
    const market = setMarketFilter(tab.dataset.marketFilter);
    loadMarketRankings({ market });
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
elements.aiAnalysisButton.addEventListener("click", (event) => {
  event.preventDefault();
  loadAIAnalysis({ auto: false });
});
elements.stockInlineAIRefresh?.addEventListener("click", (event) => {
  event.preventDefault();
  loadAIAnalysis({ auto: false });
});
for (const tab of elements.stockSectionTabs) {
  tab.addEventListener("click", (event) => {
    event.preventDefault();
    setActiveStockTab(tab.dataset.stockTab || "summary");
  });
}
elements.recommendButton.addEventListener("click", loadRecommendations);
elements.recommendArchiveButton?.addEventListener("click", () => setView("recommend-history"));
elements.recommendHistoryNewButton?.addEventListener("click", () => setView("recommend"));
elements.watchChartRefresh?.addEventListener("click", () => {
  for (const item of readWatchlist()) {
    clearCachedUrl(`/stocks/${encodeURIComponent(item.code)}/prices?limit=180`);
    clearCachedUrl(`/stocks/${encodeURIComponent(item.code)}/dashboard`);
  }
  loadWatchCharts();
});
elements.chartArchiveButton?.addEventListener("click", () => setView("chart-history"));
elements.chartHistoryBackButton.addEventListener("click", () => setView("chart"));
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
  state.watchPreopenExpanded.delete(code);
  writeWatchlist(readWatchlist().filter((item) => item.code !== code));
  updateWatchButton();
  loadWatchlist();
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

document.addEventListener("pointerdown", () => {
  markWatchlistSessionActive();
}, { passive: true });

document.addEventListener("keydown", () => {
  markWatchlistSessionActive();
});

window.addEventListener("scroll", () => {
  if (state.sessionScrollTicking) {
    return;
  }
  state.sessionScrollTicking = true;
  window.requestAnimationFrame(() => {
    state.sessionScrollTicking = false;
    markWatchlistSessionActive();
  });
}, { passive: true });

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    validateWatchlistSession();
  }
});

window.addEventListener("storage", (event) => {
  if (event.key === WATCHLIST_ACTIVITY_KEY && state.watchlistId) {
    validateWatchlistSession();
  }
});

registerDashboardServiceWorker();
updateHomeInstallButton();
initializeWatchlistIdentity();
applyStockTermTooltips();

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
