from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic import Field


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    market: str
    isin: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    listed_date: Optional[date] = None
    last_seen_date: Optional[date] = None


class WatchlistItemIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=12)
    name: str = Field(..., min_length=1, max_length=120)
    market: Optional[str] = Field(default=None, max_length=20)


class WatchlistUpdateIn(BaseModel):
    items: list[WatchlistItemIn] = Field(default_factory=list, max_length=100)


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    market: Optional[str] = None


class WatchlistOut(BaseModel):
    share_id: str
    items: list[WatchlistItemOut]
    updated_at: datetime


class PushSubscriptionKeysIn(BaseModel):
    p256dh: str = Field(..., min_length=20, max_length=500)
    auth: str = Field(..., min_length=8, max_length=255)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(..., min_length=20, max_length=2048)
    keys: PushSubscriptionKeysIn
    conditions: list[str] = Field(default_factory=list, max_length=10)


class PushSubscriptionDeleteIn(BaseModel):
    endpoint: str = Field(..., min_length=20, max_length=2048)


class DailyPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    trade_date: date
    open: Optional[int] = None
    high: Optional[int] = None
    low: Optional[int] = None
    close: Optional[int] = None
    volume: Optional[int] = None
    trading_value: Optional[int] = None
    market_cap: Optional[int] = None
    listed_shares: Optional[int] = None


class InvestorFlowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    trade_date: date
    investor_type: str
    buy_volume: Optional[int] = None
    sell_volume: Optional[int] = None
    net_buy_volume: Optional[int] = None
    buy_value: Optional[int] = None
    sell_value: Optional[int] = None
    net_buy_value: Optional[int] = None


class FinancialStatementLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    corp_code: str
    stock_code: Optional[str] = None
    bsns_year: str
    reprt_code: str
    fs_div: Optional[str] = None
    sj_div: Optional[str] = None
    account_id: Optional[str] = None
    account_name: str
    ord: Optional[int] = None
    current_amount: Optional[Decimal] = None
    previous_amount: Optional[Decimal] = None


class MacroObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str
    series_code: str
    item_code: Optional[str] = None
    period: str
    value: Optional[Decimal] = None
    unit: Optional[str] = None
    name: Optional[str] = None


class IngestionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    dataset: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    rows_loaded: int
    message: Optional[str] = None


class BriefingMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_key: str
    label: str
    value_numeric: Optional[Decimal] = None
    value_text: Optional[str] = None
    change_value: Optional[Decimal] = None
    change_rate: Optional[Decimal] = None
    unit: Optional[str] = None
    sort_order: int


class BriefingQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    market: Optional[str] = None
    role: str
    price: Optional[Decimal] = None
    change_value: Optional[Decimal] = None
    change_rate: Optional[Decimal] = None
    volume: Optional[int] = None
    trading_value: Optional[int] = None


class BriefingMoverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    list_type: str
    rank: int
    code: str
    name: str
    market: Optional[str] = None
    price: Optional[Decimal] = None
    change_value: Optional[Decimal] = None
    change_rate: Optional[Decimal] = None
    volume: Optional[int] = None
    trading_value: Optional[int] = None


class BriefingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_type: str
    source: str
    title: str
    company_name: Optional[str] = None
    stock_code: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class BriefingSnapshotSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    briefing_kind: str
    source: str
    transport: str
    market_status: str
    is_live: bool
    as_of: datetime
    summary: Optional[str] = None
    created_at: datetime


class BriefingSnapshotOut(BriefingSnapshotSummaryOut):
    metrics: list[BriefingMetricOut]
    quotes: list[BriefingQuoteOut]
    movers: list[BriefingMoverOut]
    events: list[BriefingEventOut]


class BriefingRuntimeStatusOut(BaseModel):
    enabled: bool
    research_enabled: bool
    disclosure_enabled: bool
    news_enabled: bool
    price_enabled: bool
    toss_enabled: bool
    toss_sync_holdings_enabled: bool
    running: bool
    poll_seconds: int
    research_poll_seconds: int
    research_backfill_poll_seconds: int
    disclosure_poll_seconds: int
    news_poll_seconds: int
    price_poll_seconds: int
    investor_flow_enabled: bool
    investor_flow_poll_seconds: int
    financials_enabled: bool
    financials_poll_seconds: int
    macro_enabled: bool
    macro_poll_seconds: int
    toss_poll_seconds: int
    toss_order_poll_seconds: int
    configured_sources: list[str]
    last_success_at: Optional[datetime] = None
    last_research_at: Optional[datetime] = None
    last_research_backfill_at: Optional[datetime] = None
    last_disclosure_at: Optional[datetime] = None
    last_disclosure_source: Optional[str] = None
    last_disclosure_message: Optional[str] = None
    last_news_at: Optional[datetime] = None
    last_price_at: Optional[datetime] = None
    last_price_source: Optional[str] = None
    last_price_message: Optional[str] = None
    last_investor_flow_at: Optional[datetime] = None
    last_investor_flow_source: Optional[str] = None
    last_investor_flow_message: Optional[str] = None
    last_financials_at: Optional[datetime] = None
    last_financials_source: Optional[str] = None
    last_financials_message: Optional[str] = None
    last_macro_at: Optional[datetime] = None
    last_macro_source: Optional[str] = None
    last_macro_message: Optional[str] = None
    last_toss_at: Optional[datetime] = None
    last_toss_order_at: Optional[datetime] = None
    next_toss_retry_at: Optional[datetime] = None
    next_toss_order_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    source_errors: dict[str, str] = Field(default_factory=dict)


class ResearchReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_category: str
    external_id: str
    title: str
    subject_name: Optional[str] = None
    company_name: Optional[str] = None
    stock_code: Optional[str] = None
    broker_name: Optional[str] = None
    opinion: Optional[str] = None
    target_price: Optional[Decimal] = None
    detail_url: Optional[str] = None
    pdf_url: Optional[str] = None
    published_at: Optional[datetime] = None
    views: Optional[int] = None


class DisclosureItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str
    disclosure_category: str
    company_name: str
    stock_code: Optional[str] = None
    corp_code: Optional[str] = None
    corp_class: Optional[str] = None
    report_name: str
    filer_name: Optional[str] = None
    remark: Optional[str] = None
    detail_url: Optional[str] = None
    published_at: Optional[datetime] = None


class NewsItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_category: str
    external_id: str
    title: str
    summary: Optional[str] = None
    press_name: Optional[str] = None
    image_url: Optional[str] = None
    detail_url: Optional[str] = None
    published_at: Optional[datetime] = None


class CompanyBriefOut(BaseModel):
    company_name: str
    stock_code: Optional[str] = None
    market: Optional[str] = None
    latest_close: Optional[int] = None
    latest_trade_date: Optional[date] = None
    report_count: int
    disclosure_count: int
    news_count: int
    total_count: int
    latest_published_at: Optional[datetime] = None
    latest_report_title: Optional[str] = None
    latest_report_url: Optional[str] = None
    latest_report_at: Optional[datetime] = None
    latest_report_broker: Optional[str] = None
    latest_disclosure_title: Optional[str] = None
    latest_disclosure_url: Optional[str] = None
    latest_disclosure_at: Optional[datetime] = None
    latest_disclosure_category: Optional[str] = None
    latest_news_title: Optional[str] = None
    latest_news_url: Optional[str] = None
    latest_news_at: Optional[datetime] = None
    latest_news_press: Optional[str] = None


class DashboardQuoteOut(BaseModel):
    trade_date: Optional[date] = None
    price: Optional[int] = None
    change_value: Optional[int] = None
    change_rate: Optional[Decimal] = None
    volume: Optional[int] = None
    trading_value: Optional[int] = None
    market_cap: Optional[int] = None
    pre_market_price: Optional[int] = None
    pre_market_change_value: Optional[int] = None
    pre_market_change_rate: Optional[Decimal] = None
    pre_market_volume: Optional[int] = None
    pre_market_status: Optional[str] = None
    pre_market_as_of: Optional[str] = None


class DashboardMomentumOut(BaseModel):
    one_month_return: Optional[Decimal] = None
    three_month_return: Optional[Decimal] = None
    trading_value_change: Optional[Decimal] = None
    latest_trading_value: Optional[int] = None
    baseline_trading_value: Optional[Decimal] = None


class DashboardChartAnalysisOut(BaseModel):
    score: Decimal
    stance: str
    trend: str
    setup: str
    risk_level: str
    moving_averages: dict[str, Optional[Decimal]]
    volume_ratio: Optional[Decimal] = None
    atr_percent: Optional[Decimal] = None
    support: Optional[int] = None
    resistance: Optional[int] = None
    distance_to_support: Optional[Decimal] = None
    distance_to_resistance: Optional[Decimal] = None
    signals: list[str]
    risks: list[str]


class DashboardResearchReportOut(BaseModel):
    title: str
    broker_name: Optional[str] = None
    opinion: Optional[str] = None
    target_price: Optional[Decimal] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class DashboardRevisionOut(BaseModel):
    report_count_90d: int
    target_up_count: int
    target_down_count: int
    target_up_ratio: Optional[Decimal] = None
    latest_target_price: Optional[Decimal] = None
    latest_opinion: Optional[str] = None
    latest_report_at: Optional[datetime] = None
    estimated_revenue: Optional[Decimal] = None
    estimated_operating_profit: Optional[Decimal] = None
    estimated_eps: Optional[Decimal] = None
    estimated_per: Optional[Decimal] = None
    recent_reports: list[DashboardResearchReportOut] = Field(default_factory=list)


class DashboardEventOut(BaseModel):
    title: str
    source: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class DashboardSurpriseOut(BaseModel):
    recent_count: int
    positive_count: int
    negative_count: int
    latest_events: list[DashboardEventOut]
    latest_revenue: Optional[Decimal] = None
    latest_operating_profit: Optional[Decimal] = None
    latest_eps: Optional[Decimal] = None
    revenue_growth: Optional[Decimal] = None
    operating_profit_growth: Optional[Decimal] = None


class DashboardFlowOut(BaseModel):
    foreign_net_buy_20d: Optional[int] = None
    institution_net_buy_20d: Optional[int] = None
    foreign_intensity: Optional[Decimal] = None
    institution_intensity: Optional[Decimal] = None


class DashboardValuationOut(BaseModel):
    per: Optional[Decimal] = None
    pbr: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    bps: Optional[Decimal] = None
    estimated_per: Optional[Decimal] = None
    estimated_eps: Optional[Decimal] = None
    industry_per: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    per_zscore: Optional[Decimal] = None
    pbr_zscore: Optional[Decimal] = None
    ev_ebitda_zscore: Optional[Decimal] = None


class DashboardSentimentOut(BaseModel):
    score: Optional[Decimal] = None
    positive_count: int
    negative_count: int
    neutral_count: int
    latest_items: list[DashboardEventOut]


class DashboardCoverageOut(BaseModel):
    price: bool
    investor_flow: bool
    research_proxy: bool
    disclosure: bool
    news: bool
    valuation: bool
    macro_sensitivity: bool


class DashboardCompanyProfileOut(BaseModel):
    corp_name: Optional[str] = None
    corp_name_eng: Optional[str] = None
    summary: str
    summary_source: str
    industry: Optional[str] = None
    sector: Optional[str] = None
    ceo_name: Optional[str] = None
    address: Optional[str] = None
    homepage_url: Optional[str] = None
    ir_url: Optional[str] = None
    established_date: Optional[date] = None
    fiscal_month: Optional[str] = None
    business_report_title: Optional[str] = None
    business_report_url: Optional[str] = None
    business_report_published_at: Optional[datetime] = None
    source_label: str
    source_url: Optional[str] = None
    updated_at: Optional[datetime] = None


class StockDashboardOut(BaseModel):
    code: str
    name: str
    market: str
    as_of: datetime
    source: Optional[str] = None
    company_profile: DashboardCompanyProfileOut
    quote: DashboardQuoteOut
    revisions: DashboardRevisionOut
    surprise: DashboardSurpriseOut
    guidance: DashboardSurpriseOut
    momentum: DashboardMomentumOut
    chart_analysis: DashboardChartAnalysisOut
    flows: DashboardFlowOut
    valuation: DashboardValuationOut
    macro_sensitivity: dict[str, Optional[Decimal]]
    sentiment: DashboardSentimentOut
    coverage: DashboardCoverageOut


class StockAIAnalysisSectionOut(BaseModel):
    title: str
    items: list[str]


class StockAITradeLevelsOut(BaseModel):
    buy_low: Optional[int] = None
    buy_high: Optional[int] = None
    breakout: Optional[int] = None
    stop: Optional[int] = None
    first_sell: Optional[int] = None
    support_reference: Optional[int] = None
    resistance_reference: Optional[int] = None
    actionable: bool = False
    entry_label: Optional[str] = None
    entry_note: Optional[str] = None


class StockAIAnalysisOut(BaseModel):
    code: str
    name: str
    market: str
    as_of: datetime
    generated_at: datetime
    stance: str
    confidence: Decimal
    data_covered: int = 0
    data_total: int = 0
    summary: str
    key_points: list[str]
    strategy: list[str]
    risks: list[str]
    sections: list[StockAIAnalysisSectionOut]
    trade_levels: Optional[StockAITradeLevelsOut] = None
    generation_mode: str = "rules"
    model_name: Optional[str] = None
    generation_note: Optional[str] = None


class MarketRankingItemOut(BaseModel):
    rank: int
    category: str
    code: str
    name: str
    market: str
    trade_date: Optional[date] = None
    price: Optional[int] = None
    change_rate: Optional[Decimal] = None
    one_month_return: Optional[Decimal] = None
    three_month_return: Optional[Decimal] = None
    trading_value: Optional[int] = None
    trading_value_change: Optional[Decimal] = None
    per: Optional[Decimal] = None
    pbr: Optional[Decimal] = None
    sentiment_score: Optional[Decimal] = None
    news_count: Optional[int] = None
    metric_value: Optional[Decimal] = None


class MarketRankingOut(BaseModel):
    category: str
    market: Optional[str] = None
    as_of: datetime
    source: str = "database"
    universe_count: int = 0
    matching_count: int = 0
    items: list[MarketRankingItemOut]


class RecommendationItemOut(BaseModel):
    rank: int
    code: str
    name: str
    market: str
    score: Decimal
    action: str
    price: Optional[int] = None
    change_rate: Optional[Decimal] = None
    one_month_return: Optional[Decimal] = None
    three_month_return: Optional[Decimal] = None
    trading_value: Optional[int] = None
    component_scores: dict[str, Decimal]
    chart_analysis: DashboardChartAnalysisOut
    reasons: list[str]
    risks: list[str]


class MarketRecommendationOut(BaseModel):
    as_of: datetime
    universe_count: int
    candidate_count: int
    methodology: list[str]
    items: list[RecommendationItemOut]


class TrendTimelineItemOut(BaseModel):
    id: str
    published_at: Optional[datetime] = None
    title: str
    source: str
    url: Optional[str] = None
    category: str
    impact: str
    leader_stocks: list[str] = Field(default_factory=list)
    related_event: Optional[str] = None


class TrendEventOut(BaseModel):
    id: str
    starts_at: datetime
    event_axes: list[str] = Field(default_factory=list)
    category: str
    title: str
    importance: str
    expected_impact: str
    affected_variables: list[str]
    affected_sectors: list[str]
    watch_points: list[str]
    source_name: str
    source_url: str
    timeline: list[TrendTimelineItemOut]


class TrendAnalysisOut(BaseModel):
    as_of: datetime
    window_start: datetime
    window_end: datetime
    headline: str
    events: list[TrendEventOut]
    past_events: list[TrendEventOut]
    timeline: list[TrendTimelineItemOut]


class MarketImpactEvidenceOut(BaseModel):
    source: str
    metric: str
    value: Optional[Decimal] = None
    value_text: Optional[str] = None
    change_1d: Optional[Decimal] = None
    change_1d_text: Optional[str] = None
    change_5d: Optional[Decimal] = None
    change_5d_text: Optional[str] = None
    as_of: Optional[str] = None
    url: str


class MarketImpactFactorOut(BaseModel):
    key: str
    label: str
    percent: Decimal
    direction: str
    confidence: Decimal
    interpretation: str
    evidence: list[MarketImpactEvidenceOut] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)
    leader_stocks: list[str] = Field(default_factory=list)


class MarketImpactOut(BaseModel):
    as_of: datetime
    market_status: str
    summary: str
    good_weight: Decimal
    bad_weight: Decimal
    factors: list[MarketImpactFactorOut]


class TrendGraphNodeOut(BaseModel):
    id: str
    label: str
    kind: str
    detail: Optional[str] = None
    polarity: str = "neutral"


class TrendGraphLayerOut(BaseModel):
    title: str
    nodes: list[TrendGraphNodeOut]


class TrendGraphStockOut(BaseModel):
    code: str
    name: str
    market: str
    market_cap: Optional[int] = None
    impact_score: Decimal
    impact_direction: str
    reasons: list[str]


class TrendEventGraphOut(BaseModel):
    event_id: str
    title: str
    as_of: datetime
    summary: str
    scenario: str
    negative_label: str
    positive_label: str
    layers: list[TrendGraphLayerOut]
    negative_stocks: list[TrendGraphStockOut]
    positive_stocks: list[TrendGraphStockOut]


class InsightHorizonOut(BaseModel):
    key: str
    label: str
    window: str
    focus: str
    primary_inputs: list[str]


class InsightLoopOut(BaseModel):
    key: str
    label: str
    interval: str
    purpose: str
    sources: list[str]
    action_rule: str


class InsightCadenceOut(BaseModel):
    thread_id: str
    principles: list[str]
    horizons: list[InsightHorizonOut]
    intraday_loops: list[InsightLoopOut]
    review_cycles: list[InsightLoopOut]
    default_watch_rules: list[str]


class ResearchSourceOut(BaseModel):
    key: str
    display_name: str
    source_type: str
    access_model: str
    listing_url: str
    is_active_collector: bool
    supports_pdf: bool
    supports_target_price: bool
    notes: Optional[str] = None


class IntegrationMetaOut(BaseModel):
    key: str
    display_name: str
    integration_type: str
    status: str
    configured: bool
    enabled: bool
    default_poll_seconds: Optional[int] = None
    base_url: Optional[str] = None
    purpose: str
    capabilities: list[str]
    not_for: list[str]
    required_settings: list[str]
    note: Optional[str] = None


class BrokerAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    broker_name: str
    account_seq: int
    account_no: Optional[str] = None
    account_type: Optional[str] = None
    total_purchase_amount_krw: Optional[Decimal] = None
    total_purchase_amount_usd: Optional[Decimal] = None
    market_value_krw: Optional[Decimal] = None
    market_value_usd: Optional[Decimal] = None
    market_value_after_cost_krw: Optional[Decimal] = None
    market_value_after_cost_usd: Optional[Decimal] = None
    profit_loss_krw: Optional[Decimal] = None
    profit_loss_usd: Optional[Decimal] = None
    profit_loss_after_cost_krw: Optional[Decimal] = None
    profit_loss_after_cost_usd: Optional[Decimal] = None
    profit_loss_rate: Optional[Decimal] = None
    profit_loss_rate_after_cost: Optional[Decimal] = None
    daily_profit_loss_krw: Optional[Decimal] = None
    daily_profit_loss_usd: Optional[Decimal] = None
    daily_profit_loss_rate: Optional[Decimal] = None
    synced_at: Optional[datetime] = None
    updated_at: datetime


class BrokerHoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    broker_name: str
    account_seq: int
    symbol: str
    name: str
    market_country: Optional[str] = None
    currency: Optional[str] = None
    quantity: Optional[Decimal] = None
    last_price: Optional[Decimal] = None
    average_purchase_price: Optional[Decimal] = None
    purchase_amount: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    market_value_after_cost: Optional[Decimal] = None
    profit_loss: Optional[Decimal] = None
    profit_loss_after_cost: Optional[Decimal] = None
    profit_loss_rate: Optional[Decimal] = None
    profit_loss_rate_after_cost: Optional[Decimal] = None
    daily_profit_loss: Optional[Decimal] = None
    daily_profit_loss_rate: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    synced_at: Optional[datetime] = None
    updated_at: datetime


class BrokerOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    broker_name: str
    account_seq: int
    order_id: str
    symbol: str
    side: Optional[str] = None
    order_type: Optional[str] = None
    time_in_force: Optional[str] = None
    status: Optional[str] = None
    price: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    order_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    ordered_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    filled_quantity: Optional[Decimal] = None
    average_filled_price: Optional[Decimal] = None
    filled_amount: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    filled_at: Optional[datetime] = None
    settlement_date: Optional[date] = None
    synced_at: Optional[datetime] = None
    updated_at: datetime


class BrokerSyncResultOut(BaseModel):
    broker_name: str
    dataset: str
    rows_loaded: int
    account_seq: Optional[int] = None
    message: Optional[str] = None


class TossStatusOut(BaseModel):
    enabled: bool
    configured: bool
    sync_holdings_enabled: bool
    base_url: str
    account_no: Optional[str] = None
    account_seq: Optional[int] = None
    poll_seconds: int
    order_poll_seconds: int


class TossBuyingPowerOut(BaseModel):
    currency: str
    cash_buying_power: Decimal


class TossSellableQuantityOut(BaseModel):
    sellable_quantity: Decimal


class TossStockInfoOut(BaseModel):
    symbol: str
    name: str
    english_name: str
    isin_code: str
    market: str
    security_type: str
    is_common_share: bool
    status: str
    currency: str
    list_date: Optional[date] = None
    delist_date: Optional[date] = None
    shares_outstanding: Decimal
    leverage_factor: Optional[Decimal] = None


class TossOrderOperationOut(BaseModel):
    order_id: str
    client_order_id: Optional[str] = None


class TossOrderCreateIn(BaseModel):
    account_seq: Optional[int] = None
    client_order_id: Optional[str] = None
    symbol: str
    side: str
    order_type: str
    time_in_force: Optional[str] = "DAY"
    quantity: Optional[str] = None
    price: Optional[str] = None
    order_amount: Optional[str] = None
    confirm_high_value_order: bool = False


class TossOrderModifyIn(BaseModel):
    account_seq: Optional[int] = None
    order_type: str
    quantity: Optional[str] = None
    price: Optional[str] = None
    confirm_high_value_order: bool = False
