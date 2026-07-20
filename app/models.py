from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StockMaster(Base):
    __tablename__ = "stock_master"

    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    isin: Mapped[Optional[str]] = mapped_column(String(20))
    sector: Mapped[Optional[str]] = mapped_column(String(120))
    industry: Mapped[Optional[str]] = mapped_column(String(120))
    listed_date: Mapped[Optional[date]] = mapped_column(Date)
    last_seen_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
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
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


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
    volume: Mapped[Optional[int]] = mapped_column(Integer)
    trading_value: Mapped[Optional[int]] = mapped_column(Integer)
    market_cap: Mapped[Optional[int]] = mapped_column(Integer)
    listed_shares: Mapped[Optional[int]] = mapped_column(Integer)
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
    buy_volume: Mapped[Optional[int]] = mapped_column(Integer)
    sell_volume: Mapped[Optional[int]] = mapped_column(Integer)
    net_buy_volume: Mapped[Optional[int]] = mapped_column(Integer)
    buy_value: Mapped[Optional[int]] = mapped_column(Integer)
    sell_value: Mapped[Optional[int]] = mapped_column(Integer)
    net_buy_value: Mapped[Optional[int]] = mapped_column(Integer)
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
    account_id: Mapped[Optional[str]] = mapped_column(String(80))
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
    volume: Mapped[Optional[int]] = mapped_column(Integer)
    trading_value: Mapped[Optional[int]] = mapped_column(Integer)


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
    volume: Mapped[Optional[int]] = mapped_column(Integer)
    trading_value: Mapped[Optional[int]] = mapped_column(Integer)


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


class BrokerAccount(Base):
    __tablename__ = "broker_account"
    __table_args__ = (
        UniqueConstraint("broker_name", "account_seq", name="uq_broker_account"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broker_name: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    account_seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_no: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    total_purchase_amount_krw: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    total_purchase_amount_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    market_value_krw: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    market_value_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    market_value_after_cost_krw: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    market_value_after_cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_krw: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_after_cost_krw: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_after_cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_rate_after_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    daily_profit_loss_krw: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    daily_profit_loss_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    daily_profit_loss_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    raw: Mapped[Optional[str]] = mapped_column(Text)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BrokerHolding(Base):
    __tablename__ = "broker_holding"
    __table_args__ = (
        UniqueConstraint("broker_name", "account_seq", "symbol", name="uq_broker_holding"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broker_name: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    account_seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    market_country: Mapped[Optional[str]] = mapped_column(String(8), index=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), index=True)
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    last_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    average_purchase_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    purchase_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    market_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    market_value_after_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_after_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    profit_loss_rate_after_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    daily_profit_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    daily_profit_loss_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    commission: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    raw: Mapped[Optional[str]] = mapped_column(Text)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BrokerOrder(Base):
    __tablename__ = "broker_order"
    __table_args__ = (
        UniqueConstraint("broker_name", "account_seq", "order_id", name="uq_broker_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broker_name: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    account_seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    side: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    order_type: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    time_in_force: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    status: Mapped[Optional[str]] = mapped_column(String(24), index=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    order_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    currency: Mapped[Optional[str]] = mapped_column(String(8), index=True)
    ordered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    filled_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    average_filled_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    filled_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    commission: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8))
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    settlement_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    raw: Mapped[Optional[str]] = mapped_column(Text)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
