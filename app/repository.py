from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import (
    BrokerAccount,
    BrokerHolding,
    BrokerOrder,
    BriefingEvent,
    BriefingMetric,
    BriefingMover,
    BriefingQuote,
    BriefingSnapshot,
    DailyPrice,
    DisclosureItem,
    FinancialStatementLine,
    IngestionRun,
    InvestorFlow,
    MacroObservation,
    NewsItem,
    ResearchReport,
    StockMaster,
)


def upsert_many(db: Session, model: type, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0

    bind_name = db.get_bind().dialect.name
    if bind_name == "sqlite":
        max_rows_per_statement = max(1, 900 // max(1, len(model.__table__.columns)))
        for start in range(0, len(rows), max_rows_per_statement):
            chunk = rows[start : start + max_rows_per_statement]
            statement = sqlite_insert(model).values(chunk)
            update_cols = {
                column.name: getattr(statement.excluded, column.name)
                for column in model.__table__.columns
                if not column.primary_key
            }
            db.execute(statement.on_conflict_do_update(index_elements=_conflict_columns(model), set_=update_cols))
    else:
        for row in rows:
            db.merge(model(**row))
    return len(rows)


def _conflict_columns(model: type) -> list[str]:
    if model is StockMaster:
        return ["code"]
    if model is DailyPrice:
        return ["code", "trade_date"]
    if model is InvestorFlow:
        return ["code", "trade_date", "investor_type"]
    if model is FinancialStatementLine:
        return [
            "corp_code",
            "stock_code",
            "bsns_year",
            "reprt_code",
            "fs_div",
            "sj_div",
            "account_id",
            "account_name",
            "ord",
        ]
    if model is MacroObservation:
        return ["source", "series_code", "item_code", "period"]
    if model is BriefingMetric:
        return ["snapshot_id", "metric_key"]
    if model is BriefingQuote:
        return ["snapshot_id", "code"]
    if model is BriefingMover:
        return ["snapshot_id", "list_type", "rank"]
    if model is ResearchReport:
        return ["source", "source_category", "external_id"]
    if model is DisclosureItem:
        return ["source", "external_id"]
    if model is NewsItem:
        return ["source", "source_category", "external_id"]
    if model is BrokerAccount:
        return ["broker_name", "account_seq"]
    if model is BrokerHolding:
        return ["broker_name", "account_seq", "symbol"]
    if model is BrokerOrder:
        return ["broker_name", "account_seq", "order_id"]
    raise ValueError(f"No conflict key configured for {model}")


def start_ingestion(db: Session, source: str, dataset: str) -> IngestionRun:
    run = IngestionRun(source=source, dataset=dataset, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finish_ingestion(
    db: Session, run: IngestionRun, status: str, rows_loaded: int = 0, message: Optional[str] = None
) -> None:
    run.status = status
    run.rows_loaded = rows_loaded
    run.message = message
    run.finished_at = datetime.utcnow()
    db.add(run)
    db.commit()


def list_stocks(db: Session, market: Optional[str] = None, limit: int = 5000) -> list[StockMaster]:
    statement = select(StockMaster).order_by(StockMaster.market, StockMaster.code).limit(limit)
    if market:
        statement = statement.where(StockMaster.market == market.upper())
    return list(db.scalars(statement))


def latest_briefing_snapshot(db: Session, kind: str = "home") -> Optional[BriefingSnapshot]:
    statement = (
        select(BriefingSnapshot)
        .where(BriefingSnapshot.briefing_kind == kind)
        .order_by(BriefingSnapshot.as_of.desc(), BriefingSnapshot.id.desc())
        .limit(1)
    )
    return db.scalar(statement)


def list_briefing_snapshots(db: Session, kind: str = "home", limit: int = 20) -> list[BriefingSnapshot]:
    statement = (
        select(BriefingSnapshot)
        .where(BriefingSnapshot.briefing_kind == kind)
        .order_by(BriefingSnapshot.as_of.desc(), BriefingSnapshot.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def briefing_metrics(db: Session, snapshot_id: int) -> list[BriefingMetric]:
    statement = (
        select(BriefingMetric)
        .where(BriefingMetric.snapshot_id == snapshot_id)
        .order_by(BriefingMetric.sort_order, BriefingMetric.metric_key)
    )
    return list(db.scalars(statement))


def briefing_quotes(db: Session, snapshot_id: int) -> list[BriefingQuote]:
    statement = (
        select(BriefingQuote)
        .where(BriefingQuote.snapshot_id == snapshot_id)
        .order_by(BriefingQuote.role, BriefingQuote.code)
    )
    return list(db.scalars(statement))


def briefing_movers(db: Session, snapshot_id: int) -> list[BriefingMover]:
    statement = (
        select(BriefingMover)
        .where(BriefingMover.snapshot_id == snapshot_id)
        .order_by(BriefingMover.list_type, BriefingMover.rank)
    )
    return list(db.scalars(statement))


def briefing_events(db: Session, snapshot_id: int) -> list[BriefingEvent]:
    statement = (
        select(BriefingEvent)
        .where(BriefingEvent.snapshot_id == snapshot_id)
        .order_by(BriefingEvent.published_at.desc(), BriefingEvent.id.desc())
    )
    return list(db.scalars(statement))


def latest_research_reports(
    db: Session,
    limit: int = 20,
    stock_code: Optional[str] = None,
    source_category: Optional[str] = None,
    company_name: Optional[str] = None,
    broker_name: Optional[str] = None,
    opinion: Optional[str] = None,
    query: Optional[str] = None,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
) -> list[ResearchReport]:
    statement = select(ResearchReport).order_by(ResearchReport.published_at.desc(), ResearchReport.id.desc()).limit(limit)
    if stock_code:
        statement = statement.where(ResearchReport.stock_code == stock_code)
    if source_category:
        statement = statement.where(ResearchReport.source_category == source_category)
    if company_name:
        statement = statement.where(ResearchReport.company_name.contains(company_name))
    if broker_name:
        statement = statement.where(ResearchReport.broker_name == broker_name)
    if opinion:
        statement = statement.where(ResearchReport.opinion == opinion)
    if query:
        statement = statement.where(ResearchReport.title.contains(query))
    if from_at:
        statement = statement.where(ResearchReport.published_at >= from_at)
    if to_at:
        statement = statement.where(ResearchReport.published_at <= to_at)
    return list(db.scalars(statement))


def latest_disclosures(
    db: Session,
    limit: int = 50,
    stock_code: Optional[str] = None,
    category: Optional[str] = None,
    company_name: Optional[str] = None,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
) -> list[DisclosureItem]:
    statement = (
        select(DisclosureItem)
        .order_by(DisclosureItem.published_at.desc(), DisclosureItem.external_id.desc(), DisclosureItem.id.desc())
        .limit(limit)
    )
    if stock_code:
        statement = statement.where(DisclosureItem.stock_code == stock_code)
    if category:
        statement = statement.where(DisclosureItem.disclosure_category == category)
    if company_name:
        statement = statement.where(DisclosureItem.company_name.contains(company_name))
    if from_at:
        statement = statement.where(DisclosureItem.published_at >= from_at)
    if to_at:
        statement = statement.where(DisclosureItem.published_at <= to_at)
    return list(db.scalars(statement))


def latest_news_items(
    db: Session,
    limit: int = 50,
    category: Optional[str] = None,
    press_name: Optional[str] = None,
    query: Optional[str] = None,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
) -> list[NewsItem]:
    statement = select(NewsItem).order_by(NewsItem.published_at.desc(), NewsItem.id.desc()).limit(limit)
    if category:
        statement = statement.where(NewsItem.source_category == category)
    if press_name:
        statement = statement.where(NewsItem.press_name == press_name)
    if query:
        statement = statement.where(NewsItem.title.contains(query))
    if from_at:
        statement = statement.where(NewsItem.published_at >= from_at)
    if to_at:
        statement = statement.where(NewsItem.published_at <= to_at)
    return list(db.scalars(statement))


def latest_prices_by_codes(db: Session, codes: list[str]) -> dict[str, DailyPrice]:
    codes = [code for code in codes if code]
    if not codes:
        return {}

    latest_dates = (
        select(DailyPrice.code, func.max(DailyPrice.trade_date).label("latest_trade_date"))
        .where(DailyPrice.code.in_(codes))
        .group_by(DailyPrice.code)
        .subquery()
    )
    statement = select(DailyPrice).join(
        latest_dates,
        and_(
            DailyPrice.code == latest_dates.c.code,
            DailyPrice.trade_date == latest_dates.c.latest_trade_date,
        ),
    )
    return {row.code: row for row in db.scalars(statement)}


def list_broker_accounts(db: Session, broker_name: str, limit: int = 50) -> list[BrokerAccount]:
    statement = (
        select(BrokerAccount)
        .where(BrokerAccount.broker_name == broker_name)
        .order_by(BrokerAccount.account_seq)
        .limit(limit)
    )
    return list(db.scalars(statement))


def list_broker_holdings(
    db: Session,
    broker_name: str,
    *,
    account_seq: Optional[int] = None,
    symbol: Optional[str] = None,
    limit: int = 500,
) -> list[BrokerHolding]:
    statement = (
        select(BrokerHolding)
        .where(BrokerHolding.broker_name == broker_name)
        .order_by(BrokerHolding.market_value.is_(None), BrokerHolding.market_value.desc(), BrokerHolding.symbol)
        .limit(limit)
    )
    if account_seq is not None:
        statement = statement.where(BrokerHolding.account_seq == account_seq)
    if symbol:
        statement = statement.where(BrokerHolding.symbol == symbol)
    return list(db.scalars(statement))


def list_broker_orders(
    db: Session,
    broker_name: str,
    *,
    account_seq: Optional[int] = None,
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 200,
) -> list[BrokerOrder]:
    statement = (
        select(BrokerOrder)
        .where(BrokerOrder.broker_name == broker_name)
        .order_by(BrokerOrder.ordered_at.is_(None), BrokerOrder.ordered_at.desc(), BrokerOrder.id.desc())
        .limit(limit)
    )
    if account_seq is not None:
        statement = statement.where(BrokerOrder.account_seq == account_seq)
    if status:
        statement = statement.where(BrokerOrder.status == status)
    if symbol:
        statement = statement.where(BrokerOrder.symbol == symbol)
    return list(db.scalars(statement))
