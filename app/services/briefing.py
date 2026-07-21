from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select

from app.collectors.briefing import (
    DartDisclosureProvider,
    KisRestBriefingProvider,
    collect_home_briefing,
)
from app.collectors.disclosures import collect_disclosures
from app.collectors.dart import (
    REPORT_CODES,
    collect_financial_statements_for_disclosure_companies,
    latest_financial_report_target,
)
from app.collectors.krx import collect_market_prices, collect_prices_for_codes, is_supported_price_code
from app.collectors.macro import DEFAULT_MACRO_SERIES, collect_yahoo_macro_observations
from app.collectors.naver_flows import collect_naver_investor_flows
from app.collectors.naver_quotes import collect_naver_quotes
from app.collectors.news import collect_news_items
from app.collectors.research import collect_research_reports
from app.config import Settings, get_settings
from app.db import SessionLocal
from app.integrations.toss import TossInvestError
from app.integrations.toss import sync_toss_accounts, sync_toss_holdings, sync_toss_orders
from app.models import DailyPrice, DisclosureItem, FinancialStatementLine, InvestorFlow, MacroObservation, StockMaster
from app.repository import latest_disclosures, latest_news_items, latest_research_reports
from app.services.company_briefs import build_company_briefs


class BriefingRuntime:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.market_provider = KisRestBriefingProvider(self.settings)
        self.disclosure_provider = DartDisclosureProvider(self.settings)
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.last_research_at: Optional[datetime] = None
        self.last_research_backfill_at: Optional[datetime] = None
        self.last_disclosure_at: Optional[datetime] = None
        self.last_disclosure_source: Optional[str] = None
        self.last_disclosure_message: Optional[str] = None
        self.last_news_at: Optional[datetime] = None
        self.last_price_at: Optional[datetime] = None
        self.last_price_source: Optional[str] = None
        self.last_price_message: Optional[str] = None
        self.last_investor_flow_at: Optional[datetime] = None
        self.last_investor_flow_source: Optional[str] = None
        self.last_investor_flow_message: Optional[str] = None
        self.last_financials_at: Optional[datetime] = None
        self.last_financials_source: Optional[str] = None
        self.last_financials_message: Optional[str] = None
        self.last_macro_at: Optional[datetime] = None
        self.last_macro_source: Optional[str] = None
        self.last_macro_message: Optional[str] = None
        self.last_toss_at: Optional[datetime] = None
        self.last_toss_order_at: Optional[datetime] = None
        self.next_toss_retry_at: Optional[datetime] = None
        self.next_toss_order_retry_at: Optional[datetime] = None
        self.source_errors: dict[str, str] = {}

    def configured_sources(self) -> list[str]:
        sources: list[str] = []
        if self.settings.kis_app_key and self.settings.kis_app_secret:
            sources.append("kis")
        if self.settings.research_enabled:
            sources.append("naver_research")
        if self.settings.disclosure_enabled:
            sources.append("dart_api" if self.settings.dart_api_key else "dart_web")
        if self.settings.news_enabled:
            sources.append("naver_news")
        if self.settings.price_enabled:
            sources.append("krx_prices")
        if self.settings.investor_flow_enabled:
            sources.append("naver_investor_flow")
        if self.settings.financials_enabled and self.settings.dart_api_key:
            sources.append("dart_financials")
        if self.settings.macro_enabled:
            sources.append("yahoo_macro")
        if self.settings.toss_enabled and self.settings.toss_client_id and self.settings.toss_client_secret:
            sources.append("toss")
        return sources

    async def start(self) -> None:
        if self.running:
            return
        if not any(
            [
                self.settings.briefing_realtime_enabled,
                self.settings.research_enabled,
                self.settings.disclosure_enabled,
                self.settings.news_enabled,
                self.settings.price_enabled,
                self.settings.investor_flow_enabled,
                self.settings.financials_enabled,
                self.settings.macro_enabled,
                self.settings.toss_enabled and self.settings.toss_sync_holdings_enabled,
            ]
        ):
            return
        if not self.configured_sources():
            return
        self.running = True
        self.task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _loop(self) -> None:
        while self.running:
            try:
                await asyncio.to_thread(self.run_once)
                self.last_success_at = datetime.utcnow()
                self.last_error = "; ".join(f"{source}: {message}" for source, message in self.source_errors.items()) or None
            except Exception as exc:
                self.last_error = str(exc)
            await asyncio.sleep(self.settings.briefing_poll_seconds)

    def run_once(self) -> None:
        self.source_errors = {}
        with SessionLocal() as db:
            refreshed_any = False
            if self.settings.research_enabled and self._research_backfill_due():
                try:
                    collect_research_reports(
                        db,
                        settings=self.settings,
                        categories=["company"],
                        max_pages=self.settings.research_backfill_max_pages,
                        days_back=self.settings.research_backfill_days_back,
                        include_detail=False,
                    )
                    self.last_research_backfill_at = datetime.utcnow()
                    refreshed_any = True
                except Exception as exc:
                    self.source_errors["research_backfill"] = str(exc)
            if self.settings.research_enabled and self._research_due():
                try:
                    collect_research_reports(db, settings=self.settings)
                    self.last_research_at = datetime.utcnow()
                    refreshed_any = True
                except Exception as exc:
                    self.source_errors["research"] = str(exc)
            if self.settings.disclosure_enabled and self._disclosure_due():
                try:
                    result = collect_disclosures(db, settings=self.settings)
                    self.last_disclosure_at = datetime.utcnow()
                    self.last_disclosure_source = result.resolved_source
                    self.last_disclosure_message = result.message
                    refreshed_any = True
                except Exception as exc:
                    self.source_errors["disclosure"] = str(exc)
            if self.settings.news_enabled and self._news_due():
                try:
                    collect_news_items(db, settings=self.settings)
                    self.last_news_at = datetime.utcnow()
                    refreshed_any = True
                except Exception as exc:
                    self.source_errors["news"] = str(exc)
            if self.settings.price_enabled and self._price_due():
                try:
                    price_result = self._collect_prices(db)
                    if price_result["rows_loaded"]:
                        refreshed_any = True
                    self.last_price_source = str(price_result["source"])
                    self.last_price_message = str(price_result["message"])
                    self.last_price_at = datetime.utcnow()
                except Exception as exc:
                    self.source_errors["prices"] = str(exc)
            if self.settings.investor_flow_enabled and self._investor_flow_due():
                try:
                    flow_result = self._collect_investor_flows(db)
                    if flow_result["rows_loaded"]:
                        refreshed_any = True
                    self.last_investor_flow_source = str(flow_result["source"])
                    self.last_investor_flow_message = str(flow_result["message"])
                    self.last_investor_flow_at = datetime.utcnow()
                except Exception as exc:
                    self.source_errors["investor_flow"] = str(exc)
            if self.settings.financials_enabled and self._financials_due():
                try:
                    financials_result = self._collect_financials(db)
                    if financials_result["rows_loaded"]:
                        refreshed_any = True
                    self.last_financials_source = str(financials_result["source"])
                    self.last_financials_message = str(financials_result["message"])
                    self.last_financials_at = datetime.utcnow()
                except Exception as exc:
                    self.source_errors["financials"] = str(exc)
            if self.settings.macro_enabled and self._macro_due():
                try:
                    macro_result = self._collect_macro(db)
                    if macro_result["rows_loaded"]:
                        refreshed_any = True
                    self.last_macro_source = str(macro_result["source"])
                    self.last_macro_message = str(macro_result["message"])
                    self.last_macro_at = datetime.utcnow()
                except Exception as exc:
                    self.source_errors["macro"] = str(exc)
            if self.settings.toss_enabled and self.settings.toss_sync_holdings_enabled and self._toss_due():
                refreshed_any = self._run_toss_sync(db) or refreshed_any
            if self.settings.briefing_realtime_enabled or refreshed_any:
                collect_home_briefing(
                    db,
                    settings=self.settings,
                    market_provider=self.market_provider,
                    disclosure_provider=self.disclosure_provider,
                )

    def _run_toss_sync(self, db) -> bool:
        attempted_at = datetime.utcnow()
        refreshed = False
        try:
            sync_toss_accounts(db, settings=self.settings)
            sync_toss_holdings(db, settings=self.settings)
            self.next_toss_retry_at = None
            refreshed = True
        except Exception as exc:
            self.source_errors["toss"] = str(exc)
            if self._is_toss_rate_limited(exc):
                self.next_toss_retry_at = datetime.utcnow() + timedelta(
                    seconds=max(self.settings.toss_poll_seconds * 5, 300)
                )
        finally:
            self.last_toss_at = attempted_at

        if not self._toss_order_due():
            return refreshed

        order_attempted_at = datetime.utcnow()
        try:
            sync_toss_orders(db, settings=self.settings, status="OPEN")
            self.next_toss_order_retry_at = None
            refreshed = True
        except TossInvestError as exc:
            self.source_errors["toss_orders"] = str(exc)
            if self._is_toss_rate_limited(exc):
                self.next_toss_order_retry_at = datetime.utcnow() + timedelta(
                    seconds=max(self.settings.toss_order_poll_seconds * 2, 600)
                )
        except Exception as exc:
            self.source_errors["toss_orders"] = str(exc)
            if self._is_toss_rate_limited(exc):
                self.next_toss_order_retry_at = datetime.utcnow() + timedelta(
                    seconds=max(self.settings.toss_order_poll_seconds * 2, 600)
                )
        finally:
            self.last_toss_order_at = order_attempted_at
        return refreshed

    def _research_due(self) -> bool:
        if self.last_research_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_research_at).total_seconds()
        return elapsed >= self.settings.research_poll_seconds

    def _research_backfill_due(self) -> bool:
        if self.last_research_backfill_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_research_backfill_at).total_seconds()
        return elapsed >= self.settings.research_backfill_poll_seconds

    def _disclosure_due(self) -> bool:
        if self.last_disclosure_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_disclosure_at).total_seconds()
        return elapsed >= self.settings.disclosure_poll_seconds

    def _news_due(self) -> bool:
        if self.last_news_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_news_at).total_seconds()
        return elapsed >= self.settings.news_poll_seconds

    def _price_due(self) -> bool:
        if self.last_price_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_price_at).total_seconds()
        return elapsed >= self.settings.price_poll_seconds

    def _investor_flow_due(self) -> bool:
        if self.last_investor_flow_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_investor_flow_at).total_seconds()
        return elapsed >= self.settings.investor_flow_poll_seconds

    def _financials_due(self) -> bool:
        if self.last_financials_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_financials_at).total_seconds()
        return elapsed >= self.settings.financials_poll_seconds

    def _macro_due(self) -> bool:
        if self.last_macro_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_macro_at).total_seconds()
        return elapsed >= self.settings.macro_poll_seconds

    def _toss_due(self) -> bool:
        if self.next_toss_retry_at and datetime.utcnow() < self.next_toss_retry_at:
            return False
        if self.last_toss_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_toss_at).total_seconds()
        return elapsed >= self.settings.toss_poll_seconds

    def _toss_order_due(self) -> bool:
        if self.next_toss_order_retry_at and datetime.utcnow() < self.next_toss_order_retry_at:
            return False
        if self.last_toss_order_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_toss_order_at).total_seconds()
        return elapsed >= self.settings.toss_order_poll_seconds

    def _is_toss_rate_limited(self, exc: Exception) -> bool:
        if isinstance(exc, TossInvestError) and exc.status_code == 429:
            return True
        return "요청 한도를 초과" in str(exc)

    def _collect_prices(self, db) -> dict[str, object]:
        target_yyyymmdd = datetime.utcnow().strftime("%Y%m%d")
        coverage = self._latest_price_coverage(db, target_yyyymmdd)
        if coverage["total"] and coverage["coverage_ratio"] >= 0.95:
            return {
                "source": "existing_prices",
                "rows_loaded": 0,
                "message": (
                    f"date={target_yyyymmdd} fresh={coverage['fresh']}/{coverage['total']} "
                    f"coverage={coverage['coverage_ratio']:.2%}"
                ),
            }
        market_errors: dict[str, str] = {}
        total_rows = 0
        for market in ("KOSPI", "KOSDAQ"):
            try:
                total_rows += collect_market_prices(db, target_yyyymmdd, market)
            except Exception as exc:
                market_errors[market] = str(exc)
        if total_rows:
            return {
                "source": "krx_market",
                "rows_loaded": total_rows,
                "message": f"date={target_yyyymmdd} markets=KOSPI,KOSDAQ errors={len(market_errors)}",
            }

        try:
            naver_rows = collect_naver_quotes(
                db,
                target_yyyymmdd,
                markets="KOSPI,KOSDAQ",
                limit=None,
                max_workers=self.settings.price_max_workers,
            )
            if naver_rows:
                return {
                    "source": "naver_full_quotes",
                    "rows_loaded": naver_rows,
                    "message": f"date={target_yyyymmdd} markets=KOSPI,KOSDAQ krx_errors={len(market_errors)}",
                }
        except Exception as exc:
            market_errors["naver_full_quotes"] = str(exc)

        codes = self._recent_price_codes(db)
        if not codes:
            return {
                "source": "none",
                "rows_loaded": 0,
                "message": f"date={target_yyyymmdd} no_supported_codes errors={market_errors}",
            }
        rows = collect_prices_for_codes(
            db,
            codes,
            from_yyyymmdd=(datetime.utcnow() - timedelta(days=self.settings.price_days_back)).strftime("%Y%m%d"),
            to_yyyymmdd=target_yyyymmdd,
            max_workers=self.settings.price_max_workers,
        )
        return {
            "source": "event_code_history",
            "rows_loaded": rows,
            "message": f"date={target_yyyymmdd} codes={len(codes)} krx_errors={len(market_errors)}",
        }

    def _latest_price_coverage(self, db, target_yyyymmdd: str) -> dict[str, object]:
        target_date = datetime.strptime(target_yyyymmdd, "%Y%m%d").date()
        code_rows = db.execute(
            select(StockMaster.code).where(StockMaster.market.in_(["KOSPI", "KOSDAQ"]))
        ).all()
        codes = [row[0] for row in code_rows if row[0]]
        if not codes:
            return {"total": 0, "fresh": 0, "coverage_ratio": 0.0}
        latest_rows = db.execute(
            select(DailyPrice.code, func.max(DailyPrice.trade_date))
            .where(DailyPrice.code.in_(codes))
            .group_by(DailyPrice.code)
        ).all()
        latest_by_code = {code: latest_date for code, latest_date in latest_rows}
        fresh = sum(1 for code in codes if latest_by_code.get(code) and latest_by_code[code] >= target_date)
        return {
            "total": len(codes),
            "fresh": fresh,
            "coverage_ratio": fresh / len(codes),
        }

    def _collect_investor_flows(self, db) -> dict[str, object]:
        coverage = self._latest_investor_flow_coverage(db)
        if coverage["total"] and coverage["coverage_ratio"] >= 0.95:
            return {
                "source": "existing_investor_flows",
                "rows_loaded": 0,
                "message": (
                    f"target={coverage['target_date']} fresh={coverage['fresh']}/{coverage['total']} "
                    f"coverage={coverage['coverage_ratio']:.2%}"
                ),
            }
        rows = collect_naver_investor_flows(
            db,
            markets="KOSPI,KOSDAQ",
            pages=self.settings.investor_flow_pages,
            limit=self.settings.investor_flow_code_limit,
            max_workers=self.settings.investor_flow_max_workers,
        )
        return {
            "source": "naver_investor_flow",
            "rows_loaded": rows,
            "message": f"pages={self.settings.investor_flow_pages} target={coverage['target_date']}",
        }

    def _latest_investor_flow_coverage(self, db) -> dict[str, object]:
        target_date = db.scalar(select(func.max(DailyPrice.trade_date))) or datetime.utcnow().date()
        code_rows = db.execute(
            select(StockMaster.code).where(StockMaster.market.in_(["KOSPI", "KOSDAQ"]))
        ).all()
        codes = [row[0] for row in code_rows if row[0]]
        if not codes:
            return {"target_date": target_date, "total": 0, "fresh": 0, "coverage_ratio": 0.0}
        latest_rows = db.execute(
            select(InvestorFlow.code, func.max(InvestorFlow.trade_date))
            .where(InvestorFlow.code.in_(codes))
            .group_by(InvestorFlow.code)
        ).all()
        latest_by_code = {code: latest_date for code, latest_date in latest_rows}
        fresh = sum(1 for code in codes if latest_by_code.get(code) and latest_by_code[code] >= target_date)
        return {
            "target_date": target_date,
            "total": len(codes),
            "fresh": fresh,
            "coverage_ratio": fresh / len(codes),
        }

    def _collect_financials(self, db) -> dict[str, object]:
        coverage = self._latest_financials_coverage(db)
        if coverage["total"] and coverage["coverage_ratio"] >= 0.95:
            return {
                "source": "existing_financials",
                "rows_loaded": 0,
                "message": (
                    f"target={coverage['target']} fresh={coverage['fresh']}/{coverage['total']} "
                    f"coverage={coverage['coverage_ratio']:.2%}"
                ),
            }
        result = collect_financial_statements_for_disclosure_companies(
            db,
            bsns_year=self.settings.financials_year,
            report=self.settings.financials_report,
            fs_div=self.settings.financials_fs_div,
            limit=self.settings.financials_company_limit,
        )
        return {
            "source": "dart_financials",
            "rows_loaded": result["rows_loaded"],
            "message": result["message"],
        }

    def _latest_financials_coverage(self, db) -> dict[str, object]:
        target_year, target_report = (
            (self.settings.financials_year, self.settings.financials_report)
            if self.settings.financials_year and self.settings.financials_report
            else latest_financial_report_target()
        )
        target_year = str(target_year)
        target_report = str(target_report)
        target_code = REPORT_CODES.get(target_report, target_report)
        fallback_year = str(int(target_year) - 1) if target_report != "annual" else None
        fallback_code = REPORT_CODES["annual"]

        corp_codes = {
            str(corp_code)
            for (corp_code,) in db.execute(
                select(DisclosureItem.corp_code)
                .where(DisclosureItem.stock_code.is_not(None))
                .where(DisclosureItem.corp_code.is_not(None))
            ).all()
            if corp_code
        }
        if not corp_codes:
            return {"target": f"{target_year}:{target_code}", "total": 0, "fresh": 0, "coverage_ratio": 0.0}

        statement = (
            select(FinancialStatementLine.corp_code)
            .where(FinancialStatementLine.corp_code.in_(corp_codes))
        )
        target_rows = db.execute(
            statement.where(FinancialStatementLine.bsns_year == target_year).where(
                FinancialStatementLine.reprt_code == target_code
            )
        ).all()
        covered = {str(corp_code) for (corp_code,) in target_rows if corp_code}
        if fallback_year:
            fallback_rows = db.execute(
                statement.where(FinancialStatementLine.bsns_year == fallback_year).where(
                    FinancialStatementLine.reprt_code == fallback_code
                )
            ).all()
            covered.update(str(corp_code) for (corp_code,) in fallback_rows if corp_code)

        return {
            "target": f"{target_year}:{target_code}",
            "total": len(corp_codes),
            "fresh": len(corp_codes & covered),
            "coverage_ratio": len(corp_codes & covered) / len(corp_codes),
        }

    def _collect_macro(self, db) -> dict[str, object]:
        coverage = self._latest_macro_coverage(db)
        if coverage["total"] and coverage["coverage_ratio"] >= 1:
            return {
                "source": "existing_macro",
                "rows_loaded": 0,
                "message": (
                    f"fresh={coverage['fresh']}/{coverage['total']} "
                    f"since={coverage['fresh_since']}"
                ),
            }
        rows = collect_yahoo_macro_observations(db, range_=self.settings.macro_range)
        return {
            "source": "yahoo_macro",
            "rows_loaded": rows,
            "message": f"range={self.settings.macro_range} fresh_before={coverage['fresh']}/{coverage['total']}",
        }

    def _latest_macro_coverage(self, db) -> dict[str, object]:
        series_codes = [item["symbol"] for item in DEFAULT_MACRO_SERIES]
        fresh_since = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
        rows = db.execute(
            select(MacroObservation.series_code, func.max(MacroObservation.period))
            .where(MacroObservation.source == "yahoo")
            .where(MacroObservation.series_code.in_(series_codes))
            .group_by(MacroObservation.series_code)
        ).all()
        latest_by_series = {code: period for code, period in rows}
        fresh = sum(1 for code in series_codes if latest_by_series.get(code) and latest_by_series[code] >= fresh_since)
        return {
            "total": len(series_codes),
            "fresh": fresh,
            "fresh_since": fresh_since,
            "coverage_ratio": fresh / len(series_codes) if series_codes else 0.0,
        }

    def _recent_price_codes(self, db) -> list[str]:
        lookup_limit = max(self.settings.price_code_limit * 3, 120)
        research_items = latest_research_reports(db, limit=lookup_limit)
        disclosure_items = latest_disclosures(db, limit=lookup_limit)
        news_items = latest_news_items(db, limit=lookup_limit)
        company_briefs = build_company_briefs(
            db,
            research_items=research_items,
            disclosure_items=disclosure_items,
            news_items=news_items,
            limit=self.settings.price_code_limit,
        )

        codes: list[str] = []
        seen: set[str] = set()

        def push(code: Optional[str]) -> None:
            normalized = (code or "").strip()
            if not is_supported_price_code(normalized) or normalized in seen:
                return
            codes.append(normalized)
            seen.add(normalized)

        for item in research_items:
            push(item.stock_code)
            if len(codes) >= self.settings.price_code_limit:
                return codes

        for item in company_briefs:
            push(item.get("stock_code"))
            if len(codes) >= self.settings.price_code_limit:
                return codes

        for item in disclosure_items:
            push(item.stock_code)
            if len(codes) >= self.settings.price_code_limit:
                return codes

        return codes

    def status(self) -> dict[str, object]:
        return {
            "enabled": self.settings.briefing_realtime_enabled,
            "research_enabled": self.settings.research_enabled,
            "disclosure_enabled": self.settings.disclosure_enabled,
            "news_enabled": self.settings.news_enabled,
            "price_enabled": self.settings.price_enabled,
            "toss_enabled": self.settings.toss_enabled,
            "toss_sync_holdings_enabled": self.settings.toss_sync_holdings_enabled,
            "running": self.running,
            "poll_seconds": self.settings.briefing_poll_seconds,
            "research_poll_seconds": self.settings.research_poll_seconds,
            "research_backfill_poll_seconds": self.settings.research_backfill_poll_seconds,
            "disclosure_poll_seconds": self.settings.disclosure_poll_seconds,
            "news_poll_seconds": self.settings.news_poll_seconds,
            "price_poll_seconds": self.settings.price_poll_seconds,
            "investor_flow_enabled": self.settings.investor_flow_enabled,
            "investor_flow_poll_seconds": self.settings.investor_flow_poll_seconds,
            "financials_enabled": self.settings.financials_enabled,
            "financials_poll_seconds": self.settings.financials_poll_seconds,
            "macro_enabled": self.settings.macro_enabled,
            "macro_poll_seconds": self.settings.macro_poll_seconds,
            "toss_poll_seconds": self.settings.toss_poll_seconds,
            "toss_order_poll_seconds": self.settings.toss_order_poll_seconds,
            "configured_sources": self.configured_sources(),
            "last_success_at": self.last_success_at,
            "last_research_at": self.last_research_at,
            "last_research_backfill_at": self.last_research_backfill_at,
            "last_disclosure_at": self.last_disclosure_at,
            "last_disclosure_source": self.last_disclosure_source,
            "last_disclosure_message": self.last_disclosure_message,
            "last_news_at": self.last_news_at,
            "last_price_at": self.last_price_at,
            "last_price_source": self.last_price_source,
            "last_price_message": self.last_price_message,
            "last_investor_flow_at": self.last_investor_flow_at,
            "last_investor_flow_source": self.last_investor_flow_source,
            "last_investor_flow_message": self.last_investor_flow_message,
            "last_financials_at": self.last_financials_at,
            "last_financials_source": self.last_financials_source,
            "last_financials_message": self.last_financials_message,
            "last_macro_at": self.last_macro_at,
            "last_macro_source": self.last_macro_source,
            "last_macro_message": self.last_macro_message,
            "last_toss_at": self.last_toss_at,
            "last_toss_order_at": self.last_toss_order_at,
            "next_toss_retry_at": self.next_toss_retry_at,
            "next_toss_order_retry_at": self.next_toss_order_retry_at,
            "last_error": self.last_error,
            "source_errors": self.source_errors,
        }


briefing_runtime = BriefingRuntime()
