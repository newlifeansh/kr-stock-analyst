from __future__ import annotations

from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import (
    CompanyProfile,
    DailyPrice,
    DisclosureItem,
    FinancialStatementLine,
    InvestorFlow,
    ResearchReport,
    StockFundamentalSnapshot,
    StockCompanySnapshot,
    StockNewsSnapshot,
    StockMaster,
)


def _distinct_coverage(db: Session, column, active_codes: list[str]) -> int:
    if not active_codes:
        return 0
    return int(db.scalar(select(func.count(distinct(column))).where(column.in_(active_codes))) or 0)


def stock_data_coverage(db: Session) -> dict[str, object]:
    active_codes = list(
        db.scalars(
            select(StockMaster.code)
            .where(StockMaster.is_active.is_(True))
            .where(StockMaster.market.in_(["KOSPI", "KOSDAQ"]))
            .order_by(StockMaster.market, StockMaster.code)
        )
    )
    total = len(active_codes)
    price_rows = (
        select(DailyPrice.code, func.count(DailyPrice.id).label("row_count"))
        .where(DailyPrice.code.in_(active_codes))
        .group_by(DailyPrice.code)
        .subquery()
    )
    flow_rows = (
        select(
            InvestorFlow.code,
            func.count(distinct(InvestorFlow.trade_date)).label("day_count"),
        )
        .where(InvestorFlow.code.in_(active_codes))
        .group_by(InvestorFlow.code)
        .subquery()
    )

    def threshold_count(subquery, column_name: str, threshold: int) -> int:
        return int(
            db.scalar(
                select(func.count())
                .select_from(subquery)
                .where(getattr(subquery.c, column_name) >= threshold)
            )
            or 0
        )

    datasets = {
        "latest_price": _distinct_coverage(db, DailyPrice.code, active_codes),
        "investor_flow": _distinct_coverage(db, InvestorFlow.code, active_codes),
        "fundamental_snapshot": _distinct_coverage(db, StockFundamentalSnapshot.stock_code, active_codes),
        "stock_news_snapshot": _distinct_coverage(db, StockNewsSnapshot.stock_code, active_codes),
        "company_snapshot": _distinct_coverage(db, StockCompanySnapshot.stock_code, active_codes),
        "dart_financials": _distinct_coverage(db, FinancialStatementLine.stock_code, active_codes),
        "company_profile": _distinct_coverage(db, CompanyProfile.stock_code, active_codes),
        "research_report_published": _distinct_coverage(db, ResearchReport.stock_code, active_codes),
        "disclosure_published": _distinct_coverage(db, DisclosureItem.stock_code, active_codes),
    }
    return {
        "as_of": datetime.utcnow(),
        "active_stocks": total,
        "datasets": {
            key: {
                "stocks": value,
                "coverage_rate": round(value / total, 4) if total else 0,
            }
            for key, value in datasets.items()
        },
        "price_history": {
            str(threshold): threshold_count(price_rows, "row_count", threshold)
            for threshold in (1, 22, 64, 125, 250)
        },
        "quant_signal_ready": {
            "minimum_rows": 125,
            "stocks": threshold_count(price_rows, "row_count", 125),
            "coverage_rate": round(threshold_count(price_rows, "row_count", 125) / total, 4) if total else 0,
        },
        "investor_flow_history": {
            str(threshold): threshold_count(flow_rows, "day_count", threshold)
            for threshold in (1, 20, 60, 120, 240)
        },
        "notes": {
            "live_quote": "KIS 요청 시 실시간 조회하며 DB 캐시 대상이 아닙니다.",
            "quant_signal_ready": "125거래일 이상 일봉이 있는 종목은 동일한 퀀트 규칙을 즉시 계산합니다.",
            "research_report_published": "리포트가 실제 발행된 종목만 집계합니다.",
            "disclosure_published": "수집 기간에 공시가 실제 제출된 종목만 집계합니다.",
        },
    }
