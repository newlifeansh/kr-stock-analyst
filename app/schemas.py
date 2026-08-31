from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict
from pydantic import Field


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    market: str
    is_active: bool = True
    isin: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    investment_sector: str = "other"
    investment_sector_label: str = "기타"
    listed_date: Optional[date] = None
    last_seen_date: Optional[date] = None
    logo_url: Optional[str] = None


class WatchlistItemIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=12)
    name: str = Field(..., min_length=1, max_length=120)
    market: Optional[str] = Field(default=None, max_length=20)


class WatchlistUpdateIn(BaseModel):
    items: list[WatchlistItemIn] = Field(default_factory=list, max_length=100)


class InviteAccessIn(BaseModel):
    invite_code: str = Field(..., min_length=4, max_length=64)


class DashboardAccessIn(BaseModel):
    share_id: str = Field(..., min_length=2, max_length=40)


class DesktopPreferenceIn(BaseModel):
    document_title: str = Field(..., min_length=1, max_length=80)


class WatchlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    market: Optional[str] = None


class WatchlistOut(BaseModel):
    share_id: str
    items: list[WatchlistItemOut]
    updated_at: datetime


class RecommendationTrackUpdateIn(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list, max_length=50)


class RecommendationTrackStateOut(BaseModel):
    share_id: str
    initialized: bool
    items: list[dict[str, Any]]
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


class MorningMoneyBriefingItemOut(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    detail_url: Optional[str] = None
    published_at: Optional[datetime] = None
    status: str
    why_it_matters: str
    schedule_kind: Optional[str] = None
    category_key: Optional[str] = None
    category_label: Optional[str] = None


class MorningMoneyBriefingCategoryOut(BaseModel):
    key: str
    label: str
    icon: str
    description: str
    count: int
    items: list[MorningMoneyBriefingItemOut] = Field(default_factory=list)


class MorningMoneyBriefingOut(BaseModel):
    title: str
    edition: Literal["morning", "midday", "afternoon"]
    edition_key: str
    edition_label: str
    publication_date: date
    timezone: str
    window_start: datetime
    window_end: datetime
    published_at: datetime
    next_publication_at: datetime
    popup_start: datetime
    popup_end: datetime
    generated_at: datetime
    total_news_count: int
    selected_news_count: int
    opportunity_count: int
    caution_count: int
    highlights: list[MorningMoneyBriefingItemOut] = Field(default_factory=list)
    categories: list[MorningMoneyBriefingCategoryOut] = Field(default_factory=list)
    empty_message: Optional[str] = None


class BriefingRuntimeStatusOut(BaseModel):
    enabled: bool
    research_enabled: bool
    disclosure_enabled: bool
    news_enabled: bool
    price_enabled: bool
    stock_universe_enabled: bool
    running: bool
    poll_seconds: int
    snapshot_seconds: int
    retention_snapshots: int
    research_poll_seconds: int
    research_backfill_poll_seconds: int
    disclosure_poll_seconds: int
    news_poll_seconds: int
    price_poll_seconds: int
    stock_universe_poll_seconds: int
    investor_flow_enabled: bool
    investor_flow_poll_seconds: int
    financials_enabled: bool
    financials_poll_seconds: int
    fundamental_snapshot_enabled: bool
    fundamental_snapshot_poll_seconds: int
    fundamental_snapshot_effective_poll_seconds: int
    fundamental_snapshot_refresh_days: int
    fundamental_snapshot_collection_refresh_days: int
    stock_news_snapshot_enabled: bool
    stock_news_snapshot_poll_seconds: int
    stock_company_snapshot_enabled: bool
    stock_company_snapshot_poll_seconds: int
    macro_enabled: bool
    macro_poll_seconds: int
    configured_sources: list[str]
    last_success_at: Optional[datetime] = None
    last_briefing_at: Optional[datetime] = None
    last_research_at: Optional[datetime] = None
    last_research_backfill_at: Optional[datetime] = None
    last_disclosure_at: Optional[datetime] = None
    last_disclosure_source: Optional[str] = None
    last_disclosure_message: Optional[str] = None
    last_news_at: Optional[datetime] = None
    last_price_at: Optional[datetime] = None
    last_price_source: Optional[str] = None
    last_price_message: Optional[str] = None
    last_stock_universe_at: Optional[datetime] = None
    last_stock_universe_message: Optional[str] = None
    last_investor_flow_at: Optional[datetime] = None
    last_investor_flow_source: Optional[str] = None
    last_investor_flow_message: Optional[str] = None
    last_financials_at: Optional[datetime] = None
    last_financials_source: Optional[str] = None
    last_financials_message: Optional[str] = None
    last_fundamental_snapshot_at: Optional[datetime] = None
    last_fundamental_snapshot_message: Optional[str] = None
    last_fundamental_snapshot_state: str = "idle"
    last_fundamental_snapshot_priority_failed: int = 0
    last_fundamental_snapshot_full_failed: int = 0
    next_fundamental_snapshot_retry_at: Optional[datetime] = None
    last_stock_news_snapshot_at: Optional[datetime] = None
    last_stock_news_snapshot_message: Optional[str] = None
    last_stock_company_snapshot_at: Optional[datetime] = None
    last_stock_company_snapshot_message: Optional[str] = None
    last_macro_at: Optional[datetime] = None
    last_macro_source: Optional[str] = None
    last_macro_message: Optional[str] = None
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
    market_session: Optional[str] = None
    market_session_label: Optional[str] = None
    market_venue: Optional[str] = None
    market_division: Optional[str] = None
    is_live: Optional[bool] = None
    trade_time: Optional[str] = None
    trade_volume: Optional[int] = None


class DashboardMomentumOut(BaseModel):
    one_month_return: Optional[Decimal] = None
    three_month_return: Optional[Decimal] = None
    trading_value_change: Optional[Decimal] = None
    latest_trading_value: Optional[int] = None
    baseline_trading_value: Optional[Decimal] = None


class DashboardChartPatternPointOut(BaseModel):
    index: int
    date: str
    price: int
    kind: str


class DashboardChartPatternBoundaryLineOut(BaseModel):
    start_index: int
    end_index: int
    start_date: str
    end_date: str
    start_price: int
    end_price: int
    slope_per_day: Decimal


class DashboardChartPatternBoundariesOut(BaseModel):
    window_days: int
    touch_count: int
    upper_touch_count: int
    lower_touch_count: int
    containment_rate: Decimal
    upper: DashboardChartPatternBoundaryLineOut
    lower: DashboardChartPatternBoundaryLineOut


class DashboardChartPatternConfirmationOut(BaseModel):
    price_crossed: bool
    volume_confirmed: bool
    volume_ratio: Optional[Decimal] = None
    required_volume_ratio: Decimal
    crossing_date: Optional[str] = None
    crossing_index: Optional[int] = None


class DashboardChartPatternOut(BaseModel):
    key: str
    name: str
    family: str
    direction: str
    confidence: Decimal
    score_kind: str = "pattern_fit"
    status: str
    points: list[DashboardChartPatternPointOut] = Field(default_factory=list)
    trigger: Optional[int] = None
    target: Optional[int] = None
    invalidation: Optional[int] = None
    signal_date: Optional[str] = None
    age_days: int = 0
    window_days: int = 0
    is_recent: bool = False
    boundaries: Optional[DashboardChartPatternBoundariesOut] = None
    confirmation: Optional[DashboardChartPatternConfirmationOut] = None
    summary: str
    evidence: list[str] = Field(default_factory=list)


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
    patterns: list[DashboardChartPatternOut] = Field(default_factory=list)
    pattern_schema_version: int = 1


class DashboardResearchReportOut(BaseModel):
    title: str
    source: Optional[str] = None
    source_category: Optional[str] = None
    stock_code: Optional[str] = None
    external_id: Optional[str] = None
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
    impact: Optional[str] = None


class StockXFeedItemOut(BaseModel):
    post_id: str
    text: str
    author_name: str
    username: Optional[str] = None
    author_profile_image_url: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    impact: str = "중립"


class StockXFeedOut(BaseModel):
    code: str
    name: str
    configured: bool
    source: str
    query: str
    search_url: str
    as_of: datetime
    message: Optional[str] = None
    items: list[StockXFeedItemOut] = Field(default_factory=list)


class StockCommunityFeedItemOut(BaseModel):
    provider_key: str
    post_id: str
    title: str
    text: str
    author_name: str
    username: Optional[str] = None
    author_profile_image_url: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    like_count: int = 0
    dislike_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    view_count: int = 0
    impact: str = "중립"


class StockCommunityProviderOut(BaseModel):
    key: str
    label: str
    source: str
    configured: bool
    search_url: str
    more_label: str
    message: Optional[str] = None
    items: list[StockCommunityFeedItemOut] = Field(default_factory=list)


class StockCommunityFeedOut(BaseModel):
    code: str
    name: str
    as_of: datetime
    message: Optional[str] = None
    providers: list[StockCommunityProviderOut] = Field(default_factory=list)


class StockHomeContextOut(BaseModel):
    code: str
    name: str
    as_of: datetime
    flows: list[InvestorFlowOut] = Field(default_factory=list)
    research_reports: list[ResearchReportOut] = Field(default_factory=list)
    disclosures: list[DisclosureItemOut] = Field(default_factory=list)
    news_items: list[NewsItemOut] = Field(default_factory=list)
    community: StockCommunityFeedOut


class StockEtfHoldingOut(BaseModel):
    name: str
    code: Optional[str] = None
    weight: Decimal
    shares: Optional[Decimal] = None


class StockEtfDistributionOut(BaseModel):
    record_date: date
    payment_date: Optional[date] = None
    amount_per_share: Decimal
    date_type: Literal["record_date", "ex_dividend_date"] = "record_date"


class StockEtfProfileOut(BaseModel):
    code: str
    name: str
    is_etf: bool
    as_of: Optional[date] = None
    benchmark: Optional[str] = None
    issuer: Optional[str] = None
    category: Optional[str] = None
    total_fee: Optional[Decimal] = None
    trailing_distribution_yield: Optional[Decimal] = None
    trailing_distribution_amount: Optional[Decimal] = None
    distribution_schedule: Optional[str] = None
    holdings: list[StockEtfHoldingOut] = Field(default_factory=list)
    distributions: list[StockEtfDistributionOut] = Field(default_factory=list)
    source_label: str
    source_url: Optional[str] = None
    distribution_source_label: Optional[str] = None
    distribution_source_url: Optional[str] = None
    message: Optional[str] = None


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


class DashboardFinancialPointOut(BaseModel):
    period: str
    estimated: bool = False
    revenue: Optional[Decimal] = None
    operating_profit: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    operating_margin: Optional[Decimal] = None
    net_margin: Optional[Decimal] = None
    eps: Optional[Decimal] = None


class DashboardFinancialSeriesOut(BaseModel):
    annual: list[DashboardFinancialPointOut] = Field(default_factory=list)
    quarterly: list[DashboardFinancialPointOut] = Field(default_factory=list)
    unit: str = "억원"
    source: str = "네이버 금융"


class SectorOperatingMarginPointOut(BaseModel):
    period: str
    year: int
    operating_margin: Decimal


class SectorOperatingMarginCompanyOut(BaseModel):
    code: str
    name: str
    is_target: bool = False
    revenue_rank: int
    latest_revenue: Decimal
    latest_operating_margin: Decimal
    points: list[SectorOperatingMarginPointOut] = Field(default_factory=list)


class ValuationComparisonCompanyOut(BaseModel):
    code: str
    name: str
    is_target: bool = False
    latest_revenue: Optional[Decimal] = None
    current_per: Optional[Decimal] = None
    forward_per: Optional[Decimal] = None


class StockValuationComparisonOut(BaseModel):
    classification: Optional[str] = None
    classification_level: str = "industry"
    basis: str
    selection_reason: str
    target: ValuationComparisonCompanyOut
    peer: ValuationComparisonCompanyOut
    source: str = "네이버 금융"
    as_of: Optional[datetime] = None


class StockSectorOperatingMarginComparisonOut(BaseModel):
    code: str
    name: str
    industry: Optional[str] = None
    sector: Optional[str] = None
    classification: Optional[str] = None
    classification_level: str = "industry"
    basis: str
    latest_period: Optional[str] = None
    periods: list[str] = Field(default_factory=list)
    companies: list[SectorOperatingMarginCompanyOut] = Field(default_factory=list)
    target_margin_rank: Optional[int] = None
    peer_median_margin: Optional[Decimal] = None
    target_margin_gap: Optional[Decimal] = None
    valuation_comparison: Optional[StockValuationComparisonOut] = None
    source: str = "네이버 금융"
    as_of: Optional[datetime] = None


class StockSgaDetailOut(BaseModel):
    name: str
    amount: Decimal
    sales_ratio: Optional[Decimal] = None


class StockSgaCategoryOut(BaseModel):
    key: str
    label: str
    amount: Decimal
    sales_ratio: Optional[Decimal] = None
    share_of_sga: Optional[Decimal] = None
    details: list[StockSgaDetailOut] = Field(default_factory=list)


class StockSgaAnalysisOut(BaseModel):
    code: str
    name: str
    available: bool = False
    detail_available: bool = False
    period: Optional[str] = None
    consolidated: Optional[bool] = None
    unit: str = "억원"
    revenue: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    sales_ratio: Optional[Decimal] = None
    coverage_ratio: Optional[Decimal] = None
    categories: list[StockSgaCategoryOut] = Field(default_factory=list)
    source: str = "DART 사업보고서 주석"
    source_url: Optional[str] = None
    message: Optional[str] = None


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
    short_summary: Optional[str] = None
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
    financial_series: DashboardFinancialSeriesOut
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


class QuantFactorOut(BaseModel):
    key: str
    label: str
    score: Optional[Decimal] = None
    state: str
    detail: str


class QuantSignalReconciliationOut(BaseModel):
    id: str
    code: str
    signal_origin: str
    source_strategy_version: str
    target_strategy_version: str
    signal_at: datetime
    execution_date: date
    price: Optional[int] = None
    entry_price: Optional[int] = None
    reason: str


class QuantSignalEventOut(BaseModel):
    signal_date: date
    signal_at: Optional[datetime] = None
    execution_date: date
    side: str
    label: str
    price: Optional[int] = None
    entry_price: Optional[int] = None
    target_sell_price: Optional[int] = None
    target_sell_status: Optional[str] = None
    target_sell_delta: Optional[int] = None
    score: Optional[Decimal] = None
    reason: str
    entry_setup: Optional[str] = None
    entry_confirmation: Optional[dict[str, object]] = None
    profit_stage: Optional[int] = None
    sold_percent: Optional[Decimal] = None
    return_rate: Optional[Decimal] = None
    holding_days: Optional[int] = None
    position_percent: Optional[Decimal] = None
    state_after: Optional[str] = None
    signal_origin: Optional[str] = None
    source_strategy_version: Optional[str] = None
    reconciliation_id: Optional[str] = None


class QuantPartialExitOut(BaseModel):
    stage: int
    execution_date: date
    price: Optional[int] = None
    sold_percent: Decimal
    remaining_percent: Decimal
    target_price: Optional[int] = None


class QuantTradeOut(BaseModel):
    entry_date: date
    entry_price: Optional[int] = None
    target_sell_price: Optional[int] = None
    partial_exit_date: Optional[date] = None
    partial_exit_price: Optional[int] = None
    partial_exits: list[QuantPartialExitOut] = Field(default_factory=list)
    profit_stage: int = 0
    exit_date: Optional[date] = None
    exit_price: Optional[int] = None
    gross_return: Optional[Decimal] = None
    net_return: Optional[Decimal] = None
    holding_days: int
    status: str
    exit_reason: Optional[str] = None
    remaining_percent: Optional[Decimal] = None


class QuantPerformanceOut(BaseModel):
    period_start: date
    period_end: date
    trading_days: int
    history_complete: bool = False
    completed_trades: int
    win_rate: Optional[Decimal] = None
    average_return: Optional[Decimal] = None
    strategy_return: Optional[Decimal] = None
    annualized_return: Optional[Decimal] = None
    annualized_volatility: Optional[Decimal] = None
    risk_adjusted_return: Optional[Decimal] = None
    calmar_ratio: Optional[Decimal] = None
    benchmark_return: Optional[Decimal] = None
    max_return: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    average_drawdown: Optional[Decimal] = None
    positive_month_ratio: Optional[Decimal] = None
    worst_month_return: Optional[Decimal] = None
    average_model_exposure_percent: Optional[Decimal] = None
    turnover_percent: Optional[Decimal] = None
    execution_count: int = 0
    rejected_gap_entries: int = 0
    rejected_evidence_entries: int = 0
    rejected_missing_open_executions: int = 0
    average_holding_days: Optional[Decimal] = None
    transaction_cost_per_side: Decimal
    sample_state: str
    minimum_required_trades: int = 20
    sample_note: str


class QuantLifecycleTransitionOut(BaseModel):
    label: Optional[str] = None
    side: Optional[str] = None
    signal_at: Optional[datetime] = None
    signal_date: Optional[date] = None
    transition_date: Optional[date] = None
    price: Optional[int] = None
    entry_price: Optional[int] = None
    target_sell_price: Optional[int] = None
    target_sell_status: Optional[str] = None
    target_sell_delta: Optional[int] = None
    profit_stage: Optional[int] = None
    sold_percent: Optional[Decimal] = None
    signal_origin: Optional[str] = None
    reconciliation_id: Optional[str] = None


class QuantLifecycleOut(BaseModel):
    state: str
    label: str
    stage_index: int
    stages: list[str]
    latest_transition: Optional[QuantLifecycleTransitionOut] = None


class QuantDecisionLevelOut(BaseModel):
    key: str
    label: str
    price: Optional[int] = None
    condition: str


class QuantContextEvidenceOut(BaseModel):
    key: str
    label: str
    state: str
    summary: str
    source: str
    as_of: Optional[datetime] = None
    score: Optional[Decimal] = None
    available: bool
    used_for_entry: bool = False


class QuantConfirmationOut(BaseModel):
    state: str
    label: str
    score: Optional[Decimal] = None
    available_count: int
    total_count: int
    note: str
    entry_allowed: bool = False
    required_supports: int = 0
    supportive_count: int = 0
    caution_count: int = 0
    vetoes: list[str] = Field(default_factory=list)
    quality_state: str = "limited"
    source_checks: list[dict[str, object]] = Field(default_factory=list)
    evidence: list[QuantContextEvidenceOut] = Field(default_factory=list)


class QuantReturnBasisOut(BaseModel):
    price: int
    return_rate: Decimal
    return_rate_per_price: Decimal


class QuantCurrentSignalOut(BaseModel):
    action: str
    label: str
    score: Decimal
    price: Optional[int] = None
    as_of: datetime
    live_observation: bool
    position_open: bool
    model_exposure_percent: Decimal
    lifecycle: QuantLifecycleOut
    entry_date: Optional[date] = None
    entry_price: Optional[int] = None
    target_sell_price: Optional[int] = None
    target_sell_status: Optional[str] = None
    target_sell_delta: Optional[int] = None
    partial_exit_date: Optional[date] = None
    partial_exit_price: Optional[int] = None
    partial_exits: list[QuantPartialExitOut] = Field(default_factory=list)
    profit_stage: int = 0
    pending_profit_stage: Optional[int] = None
    pending_sell_percent: Optional[Decimal] = None
    expected_remaining_percent: Optional[Decimal] = None
    profit_steps_total: int = 3
    entry_setup: Optional[str] = None
    entry_confirmation: Optional[dict[str, object]] = None
    holding_days: Optional[int] = None
    unrealized_return: Optional[Decimal] = None
    return_basis: Optional[QuantReturnBasisOut] = None
    stop_reference: Optional[int] = None
    locked_profit_reference: Optional[int] = None
    partial_exit_reference: Optional[int] = None
    levels: list[QuantDecisionLevelOut] = Field(default_factory=list)
    reasons: list[str]
    next_confirmation: str
    signal_origin: Optional[str] = None
    reconciliation_id: Optional[str] = None


class StockQuantSignalsOut(BaseModel):
    code: str
    name: str
    market: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    investment_sector: str = "other"
    investment_sector_label: str = "기타"
    as_of: datetime
    strategy_name: str
    strategy_version: str
    profit_preservation_effective_date: Optional[date] = None
    tactical_exit_effective_date: Optional[date] = None
    entry_score_threshold: Decimal
    source: str
    signal_source: Optional[str] = None
    data_rows: int
    price_through: Optional[date] = None
    data_state: str
    data_message: str
    trading_state: str = "active"
    trading_state_label: str = "정상 거래"
    display_return_rate: Optional[Decimal] = None
    display_return_kind: Optional[str] = None
    display_return_event_date: Optional[date] = None
    display_return_event_side: Optional[str] = None
    confirmation: QuantConfirmationOut
    current: Optional[QuantCurrentSignalOut] = None
    performance: Optional[QuantPerformanceOut] = None
    factors: list[QuantFactorOut] = Field(default_factory=list)
    events: list[QuantSignalEventOut] = Field(default_factory=list)
    signal_reconciliations: list[QuantSignalReconciliationOut] = Field(default_factory=list)
    trades: list[QuantTradeOut] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)
    applied_principles: list[str] = Field(default_factory=list)
    excluded_principles: list[str] = Field(default_factory=list)
    disclaimer: str


class MarketRankingItemOut(BaseModel):
    rank: int
    category: str
    code: str
    name: str
    market: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    investment_sector: str = "other"
    investment_sector_label: str = "기타"
    trade_date: Optional[date] = None
    price: Optional[int] = None
    change_rate: Optional[Decimal] = None
    volume: Optional[int] = None
    market_cap: Optional[int] = None
    one_week_return: Optional[Decimal] = None
    one_month_return: Optional[Decimal] = None
    three_month_return: Optional[Decimal] = None
    trading_value: Optional[int] = None
    trading_value_change: Optional[Decimal] = None
    per: Optional[Decimal] = None
    pbr: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    dividend_per_share: Optional[int] = None
    dividend_date: Optional[str] = None
    instrument_type: str = "stock"
    sentiment_score: Optional[Decimal] = None
    news_count: Optional[int] = None
    metric_value: Optional[Decimal] = None


class MarketRankingOut(BaseModel):
    category: str
    market: Optional[str] = None
    mode: str = ""
    as_of: datetime
    source: str = "database"
    universe_count: int = 0
    matching_count: int = 0
    items: list[MarketRankingItemOut]
    snapshot_id: Optional[str] = None
    snapshot_captured_at: Optional[datetime] = None


class RecommendationItemOut(BaseModel):
    rank: int
    code: str
    name: str
    market: str
    recommended_at: datetime
    sector: Optional[str] = None
    industry: Optional[str] = None
    investment_sector: str = "other"
    investment_sector_label: str = "기타"
    score: Decimal
    action: str
    decision_reason: Optional[str] = None
    price: Optional[int] = None
    change_rate: Optional[Decimal] = None
    one_month_return: Optional[Decimal] = None
    three_month_return: Optional[Decimal] = None
    trading_value: Optional[int] = None
    component_scores: dict[str, Decimal]
    chart_analysis: DashboardChartAnalysisOut
    reasons: list[str]
    risks: list[str]
    ai_trade_signal: Optional["RecommendationAiTradeSignalOut"] = None


class RecommendationAiTradeSignalCurrentOut(BaseModel):
    action: str
    label: str
    score: Decimal
    price: Optional[int] = None
    as_of: datetime
    live_observation: bool
    position_open: bool
    model_exposure_percent: Decimal
    lifecycle: Optional[QuantLifecycleOut] = None
    entry_date: Optional[date] = None
    entry_price: Optional[int] = None
    target_sell_price: Optional[int] = None
    partial_exit_date: Optional[date] = None
    partial_exit_price: Optional[int] = None
    profit_stage: int = 0
    pending_profit_stage: Optional[int] = None
    pending_sell_percent: Optional[Decimal] = None
    expected_remaining_percent: Optional[Decimal] = None
    profit_steps_total: int = 3
    partial_exit_reference: Optional[int] = None
    locked_profit_reference: Optional[int] = None
    stop_reference: Optional[int] = None
    unrealized_return: Optional[Decimal] = None
    reasons: list[str] = Field(default_factory=list)
    next_confirmation: str


class RecommendationAiTradeSignalPreliminaryOut(BaseModel):
    side: str
    signal_date: Optional[date] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    active: bool = False
    price: Optional[int] = None
    score: Optional[Decimal] = None
    reason: Optional[str] = None


class RecommendationAiTradeSignalOut(BaseModel):
    data_state: str
    data_message: str
    as_of: datetime
    price_through: Optional[date] = None
    strategy_version: str
    signal_source: Optional[str] = None
    entry_score_threshold: Decimal
    display_return_rate: Optional[Decimal] = None
    display_return_kind: Optional[str] = None
    latest_preliminary: Optional[RecommendationAiTradeSignalPreliminaryOut] = None
    current: Optional[RecommendationAiTradeSignalCurrentOut] = None


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
    data_quality: Optional[str] = None
    quality_note: Optional[str] = None
    observation_count: Optional[int] = None


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
    data_quality: str = "확인"
    quality_note: str = ""


class MarketImpactOut(BaseModel):
    as_of: datetime
    data_as_of: Optional[str] = None
    data_quality: str = "확인"
    data_quality_note: str = ""
    market_status: str
    summary: str
    good_weight: Decimal
    bad_weight: Decimal
    neutral_weight: Decimal = Decimal("0")
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
