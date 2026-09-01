from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StockMaster(Base):
    __tablename__ = "stock_master"

    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    isin: Mapped[Optional[str]] = mapped_column(String(20))
    sector: Mapped[Optional[str]] = mapped_column(String(120))
    industry: Mapped[Optional[str]] = mapped_column(String(120))
    listed_date: Mapped[Optional[date]] = mapped_column(Date)
    last_seen_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @property
    def logo_url(self) -> str:
        return f"/stock-logos/{self.code}.png"

    @property
    def investment_sector(self) -> str:
        from app.services.sector_taxonomy import classify_investment_sector

        return classify_investment_sector(self.sector, self.industry).key

    @property
    def investment_sector_label(self) -> str:
        from app.services.sector_taxonomy import classify_investment_sector

        return classify_investment_sector(self.sector, self.industry).label


class StockLogo(Base):
    __tablename__ = "stock_logo"

    stock_code: Mapped[str] = mapped_column(
        ForeignKey("stock_master.code"), primary_key=True
    )
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    image_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(20), default="missing", nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class CompanyProfile(Base):
    __tablename__ = "company_profile"

    stock_code: Mapped[str] = mapped_column(
        ForeignKey("stock_master.code"), primary_key=True
    )
    corp_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    corp_name: Mapped[str] = mapped_column(String(200), nullable=False)
    corp_name_eng: Mapped[Optional[str]] = mapped_column(String(300))
    ceo_name: Mapped[Optional[str]] = mapped_column(String(200))
    corp_class: Mapped[Optional[str]] = mapped_column(String(20))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    homepage_url: Mapped[Optional[str]] = mapped_column(String(500))
    ir_url: Mapped[Optional[str]] = mapped_column(String(500))
    phone: Mapped[Optional[str]] = mapped_column(String(100))
    industry_code: Mapped[Optional[str]] = mapped_column(String(40))
    established_date: Mapped[Optional[date]] = mapped_column(Date)
    fiscal_month: Mapped[Optional[str]] = mapped_column(String(10))
    business_summary: Mapped[Optional[str]] = mapped_column(Text)
    summary_source: Mapped[Optional[str]] = mapped_column(String(40))
    business_report_title: Mapped[Optional[str]] = mapped_column(String(500))
    business_report_url: Mapped[Optional[str]] = mapped_column(String(1000))
    business_report_published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    source_modified_date: Mapped[Optional[date]] = mapped_column(Date)
    raw: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True
    )


class StockFundamentalSnapshot(Base):
    __tablename__ = "stock_fundamental_snapshot"

    stock_code: Mapped[str] = mapped_column(
        ForeignKey("stock_master.code"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(40), default="naver_finance", nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class StockNewsSnapshot(Base):
    __tablename__ = "stock_news_snapshot"

    stock_code: Mapped[str] = mapped_column(
        ForeignKey("stock_master.code"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(40), default="naver_finance", nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class StockIntradaySnapshot(Base):
    __tablename__ = "stock_intraday_snapshot"

    stock_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), default="kis_rest", nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    max_points: Mapped[int] = mapped_column(Integer, default=390, nullable=False)
    point_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validated_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class StockCompanySnapshot(Base):
    __tablename__ = "stock_company_snapshot"

    stock_code: Mapped[str] = mapped_column(
        ForeignKey("stock_master.code"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(40), default="naver_wisereport", nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    sector: Mapped[Optional[str]] = mapped_column(String(120))
    industry: Mapped[Optional[str]] = mapped_column(String(120))
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class MarketQuantSignalSnapshot(Base):
    __tablename__ = "market_quant_signal_snapshot"

    cache_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class QuantSignalEvidenceSnapshot(Base):
    """Point-in-time evidence used to approve a daily quant entry.

    Fundamental, research, flow, and disclosure tables keep receiving newer
    rows.  Rebuilding an old signal directly from those mutable tables would
    let future information change a past buy decision.  This snapshot freezes
    the normalized evidence available for one stock and one signal date.
    """

    __tablename__ = "quant_signal_evidence_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "stock_code",
            "signal_date",
            "strategy_version",
            name="uq_quant_signal_evidence_stock_date_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    signal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class MarketRankingSnapshot(Base):
    __tablename__ = "market_ranking_snapshot"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class CompletePayloadSnapshot(Base):
    """Last complete API payload plus a cross-process refresh lease.

    ``payload`` stays nullable so a request can enqueue the first refresh without
    inventing an incomplete response. Publishers replace it only after the new
    payload has been validated and serialized successfully.
    """

    __tablename__ = "complete_payload_snapshot"
    __table_args__ = (
        Index(
            "ix_complete_payload_snapshot_refresh_lease",
            "refresh_requested_at",
            "lease_until",
        ),
    )

    snapshot_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload: Mapped[Optional[str]] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    fresh_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    refresh_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(160))
    lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_item"
    __table_args__ = (UniqueConstraint("share_id", "code", name="uq_watchlist_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    market: Mapped[Optional[str]] = mapped_column(String(20))
    investor_state: Mapped[str] = mapped_column(
        String(20), default="not_holding", server_default="not_holding", nullable=False
    )
    average_buy_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 2))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class DashboardAccessIdentity(Base):
    __tablename__ = "dashboard_access_identity"

    share_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    admitted_host: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DashboardAccessQuota(Base):
    __tablename__ = "dashboard_access_quota"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admitted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class DesktopUserPreference(Base):
    __tablename__ = "desktop_user_preferences"

    share_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_title: Mapped[str] = mapped_column(String(80), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class RecommendationTrackState(Base):
    __tablename__ = "recommendation_track_state"

    share_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PushSubscription(Base):
    __tablename__ = "push_subscription"
    __table_args__ = (UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    content_encoding: Mapped[str] = mapped_column(String(40), default="aes128gcm", nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    notification_preferences: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PushDelivery(Base):
    __tablename__ = "push_delivery"
    __table_args__ = (
        UniqueConstraint("subscription_id", "event_key", name="uq_push_delivery_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("push_subscription.id"), nullable=False, index=True
    )
    event_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    notification_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PushNotificationHistory(Base):
    __tablename__ = "push_notification_history"
    __table_args__ = (
        UniqueConstraint("share_id", "event_key", name="uq_push_notification_history_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    share_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    notification_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class DailyPrice(Base):
    __tablename__ = "daily_price"
    __table_args__ = (UniqueConstraint("code", "trade_date", name="uq_daily_price"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[Optional[int]] = mapped_column(Integer)
    high: Mapped[Optional[int]] = mapped_column(Integer)
    low: Mapped[Optional[int]] = mapped_column(Integer)
    close: Mapped[Optional[int]] = mapped_column(Integer)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    trading_value: Mapped[Optional[int]] = mapped_column(BigInteger)
    market_cap: Mapped[Optional[int]] = mapped_column(BigInteger)
    listed_shares: Mapped[Optional[int]] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class InvestorFlow(Base):
    __tablename__ = "investor_flow"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", "investor_type", name="uq_investor_flow"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    investor_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    buy_volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    sell_volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    net_buy_volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    buy_value: Mapped[Optional[int]] = mapped_column(BigInteger)
    sell_value: Mapped[Optional[int]] = mapped_column(BigInteger)
    net_buy_value: Mapped[Optional[int]] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class FinancialStatementLine(Base):
    __tablename__ = "financial_statement_line"
    __table_args__ = (
        UniqueConstraint(
            "corp_code",
            "stock_code",
            "bsns_year",
            "reprt_code",
            "fs_div",
            "sj_div",
            "account_id",
            "account_name",
            "ord",
            name="uq_financial_line",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corp_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stock_code: Mapped[Optional[str]] = mapped_column(String(12), index=True)
    bsns_year: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    reprt_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    fs_div: Mapped[Optional[str]] = mapped_column(String(10))
    sj_div: Mapped[Optional[str]] = mapped_column(String(10))
    account_id: Mapped[Optional[str]] = mapped_column(String(255))
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    ord: Mapped[Optional[int]] = mapped_column(Integer)
    current_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 2))
    previous_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 2))
    raw: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class MacroObservation(Base):
    __tablename__ = "macro_observation"
    __table_args__ = (
        UniqueConstraint("source", "series_code", "item_code", "period", name="uq_macro"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    series_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    item_code: Mapped[Optional[str]] = mapped_column(String(80))
    period: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    unit: Mapped[Optional[str]] = mapped_column(String(40))
    name: Mapped[Optional[str]] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    dataset: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)


class BriefingSnapshot(Base):
    __tablename__ = "briefing_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    briefing_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    transport: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    market_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class BriefingMetric(Base):
    __tablename__ = "briefing_metric"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "metric_key", name="uq_briefing_metric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("briefing_snapshot.id"), nullable=False, index=True)
    metric_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    value_numeric: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    value_text: Mapped[Optional[str]] = mapped_column(String(120))
    change_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    change_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    unit: Mapped[Optional[str]] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class BriefingQuote(Base):
    __tablename__ = "briefing_quote"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "code", name="uq_briefing_quote"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("briefing_snapshot.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    market: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    change_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    change_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    trading_value: Mapped[Optional[int]] = mapped_column(BigInteger)


class BriefingMover(Base):
    __tablename__ = "briefing_mover"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "list_type", "rank", name="uq_briefing_mover"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("briefing_snapshot.id"), nullable=False, index=True)
    list_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    market: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    change_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    change_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    trading_value: Mapped[Optional[int]] = mapped_column(BigInteger)


class BriefingEvent(Base):
    __tablename__ = "briefing_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("briefing_snapshot.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    stock_code: Mapped[Optional[str]] = mapped_column(String(12), index=True)
    url: Mapped[Optional[str]] = mapped_column(String(400))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    raw: Mapped[Optional[str]] = mapped_column(Text)


class ResearchReport(Base):
    __tablename__ = "research_report"
    __table_args__ = (
        UniqueConstraint("source", "source_category", "external_id", name="uq_research_report"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    subject_name: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    stock_code: Mapped[Optional[str]] = mapped_column(String(12), index=True)
    broker_name: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    opinion: Mapped[Optional[str]] = mapped_column(String(40))
    target_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 2))
    detail_url: Mapped[Optional[str]] = mapped_column(String(400))
    pdf_url: Mapped[Optional[str]] = mapped_column(String(400))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    views: Mapped[Optional[int]] = mapped_column(Integer)
    raw: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class DisclosureItem(Base):
    __tablename__ = "disclosure_item"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_disclosure_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    disclosure_category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    stock_code: Mapped[Optional[str]] = mapped_column(String(12), index=True)
    corp_code: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    corp_class: Mapped[Optional[str]] = mapped_column(String(8), index=True)
    report_name: Mapped[str] = mapped_column(String(240), nullable=False)
    filer_name: Mapped[Optional[str]] = mapped_column(String(120))
    remark: Mapped[Optional[str]] = mapped_column(String(120))
    detail_url: Mapped[Optional[str]] = mapped_column(String(400))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    raw: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class NewsItem(Base):
    __tablename__ = "news_item"
    __table_args__ = (
        UniqueConstraint("source", "source_category", "external_id", name="uq_news_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    press_name: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(400))
    detail_url: Mapped[Optional[str]] = mapped_column(String(400))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    raw: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


# Query-order indexes are declared separately so their direction is explicit on
# both SQLite and PostgreSQL. Existing single-column and uniqueness indexes
# remain intact and continue to enforce the current data contract.
Index(
    "ix_investor_flow_code_trade_date_desc_type",
    InvestorFlow.code,
    InvestorFlow.trade_date.desc(),
    InvestorFlow.investor_type,
)
Index(
    "ix_research_report_stock_published_id_desc",
    ResearchReport.stock_code,
    ResearchReport.published_at.desc(),
    ResearchReport.id.desc(),
)
Index(
    "ix_disclosure_item_stock_published_external_id_desc",
    DisclosureItem.stock_code,
    DisclosureItem.published_at.desc(),
    DisclosureItem.external_id.desc(),
    DisclosureItem.id.desc(),
)
Index(
    "ix_market_ranking_snapshot_category_captured_desc",
    MarketRankingSnapshot.category,
    MarketRankingSnapshot.captured_at.desc(),
)
