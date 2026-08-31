from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select

from app.collectors.briefing import (
    DartDisclosureProvider,
    KisRestBriefingProvider,
    collect_home_briefing,
)
from app.collectors.dart import (
    REPORT_CODES,
    collect_financial_statements_for_disclosure_companies,
    latest_financial_report_target,
)
from app.collectors.disclosures import collect_disclosures
from app.collectors.krx import (
    collect_market_prices,
    collect_prices_for_codes,
    collect_stocks,
    is_supported_price_code,
)
from app.collectors.macro import DEFAULT_MACRO_SERIES, collect_yahoo_macro_observations
from app.collectors.naver_flows import collect_naver_investor_flows
from app.collectors.naver_quotes import (
    collect_naver_krx_price_rows_for_codes,
    collect_naver_price_history_for_codes,
    collect_naver_quotes,
)
from app.collectors.news import collect_news_items
from app.collectors.research import collect_research_reports
from app.collectors.stock_snapshots import (
    collect_stock_company_snapshots,
    collect_stock_fundamental_snapshots,
    collect_stock_news_snapshots,
)
from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import (
    DailyPrice,
    DisclosureItem,
    FinancialStatementLine,
    InvestorFlow,
    MacroObservation,
    StockMaster,
)
from app.repository import (
    latest_disclosures,
    latest_news_items,
    latest_research_reports,
    upsert_many,
)
from app.services.company_briefs import build_company_briefs
from app.services.market_calendar import (
    is_korea_market_session_date,
    latest_completed_korea_market_session_date,
    latest_korea_market_session_date,
)

KST = ZoneInfo("Asia/Seoul")
SECONDS_PER_DAY = 86_400
FUNDAMENTAL_SIGNAL_UNIVERSE_LIMIT = 100
FUNDAMENTAL_SNAPSHOT_RETRY_SECONDS = 3_600


def _has_complete_price_ohlc(row: DailyPrice) -> bool:
    values = (row.open, row.high, row.low, row.close)
    if any(value is None or value <= 0 for value in values):
        return False
    return bool(
        row.high >= max(row.open, row.close)
        and row.low <= min(row.open, row.close)
        and row.high >= row.low
    )


class BriefingRuntime:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.market_provider = KisRestBriefingProvider(self.settings)
        self.disclosure_provider = DartDisclosureProvider(self.settings)
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.last_briefing_at: Optional[datetime] = None
        self.last_research_at: Optional[datetime] = None
        self.last_research_backfill_at: Optional[datetime] = None
        self.last_disclosure_at: Optional[datetime] = None
        self.last_disclosure_source: Optional[str] = None
        self.last_disclosure_message: Optional[str] = None
        self.last_news_at: Optional[datetime] = None
        self.last_price_at: Optional[datetime] = None
        self.last_post_close_price_repair_date: Optional[date] = None
        self.last_price_source: Optional[str] = None
        self.last_price_message: Optional[str] = None
        self.last_stock_universe_at: Optional[datetime] = None
        self.last_stock_universe_message: Optional[str] = None
        self.last_investor_flow_at: Optional[datetime] = None
        self.last_investor_flow_source: Optional[str] = None
        self.last_investor_flow_message: Optional[str] = None
        self.last_financials_at: Optional[datetime] = None
        self.last_financials_source: Optional[str] = None
        self.last_financials_message: Optional[str] = None
        self.last_fundamental_snapshot_at: Optional[datetime] = None
        self.last_fundamental_snapshot_message: Optional[str] = None
        self.last_fundamental_snapshot_state = "idle"
        self.last_fundamental_snapshot_priority_failed = 0
        self.last_fundamental_snapshot_full_failed = 0
        self.next_fundamental_snapshot_retry_at: Optional[datetime] = None
        self.last_stock_news_snapshot_at: Optional[datetime] = None
        self.last_stock_news_snapshot_message: Optional[str] = None
        self.last_stock_company_snapshot_at: Optional[datetime] = None
        self.last_stock_company_snapshot_message: Optional[str] = None
        self.last_macro_at: Optional[datetime] = None
        self.last_macro_source: Optional[str] = None
        self.last_macro_message: Optional[str] = None
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
        if self.settings.stock_universe_enabled:
            sources.append("krx_stock_master")
        if self.settings.investor_flow_enabled:
            sources.append("naver_investor_flow")
        if self.settings.financials_enabled and self.settings.dart_api_key:
            sources.append("dart_financials")
        if self.settings.fundamental_snapshot_enabled:
            sources.append("naver_fundamentals")
        if self.settings.stock_news_snapshot_enabled:
            sources.append("naver_stock_news")
        if self.settings.stock_company_snapshot_enabled:
            sources.append("naver_company_info")
        if self.settings.macro_enabled:
            sources.append("yahoo_macro")
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
                self.settings.stock_universe_enabled,
                self.settings.investor_flow_enabled,
                self.settings.financials_enabled,
                self.settings.fundamental_snapshot_enabled,
                self.settings.stock_news_snapshot_enabled,
                self.settings.stock_company_snapshot_enabled,
                self.settings.macro_enabled,
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
            if self.settings.stock_universe_enabled and self._stock_universe_due():
                try:
                    loaded = collect_stocks(
                        db,
                        datetime.now(KST).strftime("%Y%m%d"),
                        self.settings.stock_universe_markets,
                    )
                    self.last_stock_universe_at = datetime.utcnow()
                    self.last_stock_universe_message = f"active_rows={loaded}"
                    refreshed_any = refreshed_any or loaded > 0
                except Exception as exc:
                    self.source_errors["stock_universe"] = str(exc)
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
            if self.settings.fundamental_snapshot_enabled and self._fundamental_snapshot_due():
                try:
                    priority_snapshot_result = {
                        "rows_loaded": 0,
                        "failed": 0,
                        "message": "not_needed",
                    }
                    if self.settings.fundamental_snapshot_refresh_days > 0:
                        priority_snapshot_result = collect_stock_fundamental_snapshots(
                            db,
                            limit=FUNDAMENTAL_SIGNAL_UNIVERSE_LIMIT,
                            max_workers=self.settings.fundamental_snapshot_max_workers,
                            refresh_days=self._fundamental_snapshot_collection_refresh_days(),
                        )
                    snapshot_result = collect_stock_fundamental_snapshots(
                        db,
                        max_workers=self.settings.fundamental_snapshot_max_workers,
                        refresh_days=self.settings.fundamental_snapshot_refresh_days,
                    )
                    if priority_snapshot_result["rows_loaded"] or snapshot_result["rows_loaded"]:
                        refreshed_any = True
                    self.last_fundamental_snapshot_message = (
                        f"signal_top_{FUNDAMENTAL_SIGNAL_UNIVERSE_LIMIT}="
                        f"{priority_snapshot_result['message']}; "
                        f"full_universe={snapshot_result['message']}"
                    )
                    completed_at = datetime.utcnow()
                    priority_failed = int(priority_snapshot_result.get("failed") or 0)
                    full_failed = int(snapshot_result.get("failed") or 0)
                    self.last_fundamental_snapshot_at = completed_at
                    self.last_fundamental_snapshot_priority_failed = priority_failed
                    self.last_fundamental_snapshot_full_failed = full_failed
                    if priority_failed or full_failed:
                        self.last_fundamental_snapshot_state = "degraded"
                        self.next_fundamental_snapshot_retry_at = (
                            completed_at + timedelta(seconds=self._fundamental_snapshot_retry_seconds())
                        )
                        self.source_errors["fundamental_snapshot"] = (
                            f"priority_failed={priority_failed} full_failed={full_failed}; "
                            f"retry_at={self.next_fundamental_snapshot_retry_at.isoformat()}"
                        )
                    else:
                        self.last_fundamental_snapshot_state = "ready"
                        self.next_fundamental_snapshot_retry_at = None
                except Exception as exc:
                    failed_at = datetime.utcnow()
                    self.last_fundamental_snapshot_at = failed_at
                    self.last_fundamental_snapshot_state = "error"
                    self.next_fundamental_snapshot_retry_at = (
                        failed_at + timedelta(seconds=self._fundamental_snapshot_retry_seconds())
                    )
                    self.source_errors["fundamental_snapshot"] = str(exc)
            if self.settings.stock_news_snapshot_enabled and self._stock_news_snapshot_due():
                try:
                    stock_news_result = collect_stock_news_snapshots(
                        db,
                        max_workers=self.settings.stock_news_snapshot_max_workers,
                        refresh_hours=self.settings.stock_news_snapshot_refresh_hours,
                    )
                    if stock_news_result["rows_loaded"]:
                        refreshed_any = True
                    self.last_stock_news_snapshot_message = str(stock_news_result["message"])
                    self.last_stock_news_snapshot_at = datetime.utcnow()
                except Exception as exc:
                    self.source_errors["stock_news_snapshot"] = str(exc)
            if self.settings.stock_company_snapshot_enabled and self._stock_company_snapshot_due():
                try:
                    company_snapshot_result = collect_stock_company_snapshots(
                        db,
                        max_workers=self.settings.stock_company_snapshot_max_workers,
                        refresh_days=self.settings.stock_company_snapshot_refresh_days,
                    )
                    if company_snapshot_result["rows_loaded"]:
                        refreshed_any = True
                    self.last_stock_company_snapshot_message = str(company_snapshot_result["message"])
                    self.last_stock_company_snapshot_at = datetime.utcnow()
                except Exception as exc:
                    self.source_errors["stock_company_snapshot"] = str(exc)
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
            if refreshed_any or (
                self.settings.briefing_realtime_enabled and self._briefing_snapshot_due()
            ):
                collect_home_briefing(
                    db,
                    settings=self.settings,
                    market_provider=self.market_provider,
                    disclosure_provider=self.disclosure_provider,
                )
                self.last_briefing_at = datetime.utcnow()

    def _research_due(self) -> bool:
        if self.last_research_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_research_at).total_seconds()
        return elapsed >= self.settings.research_poll_seconds

    def _briefing_snapshot_due(self) -> bool:
        if self.last_briefing_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_briefing_at).total_seconds()
        return elapsed >= max(self.settings.briefing_snapshot_seconds, self.settings.briefing_poll_seconds)

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

    def _stock_universe_due(self) -> bool:
        if self.last_stock_universe_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_stock_universe_at).total_seconds()
        return elapsed >= self.settings.stock_universe_poll_seconds

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

    def _fundamental_snapshot_due(self) -> bool:
        now = datetime.utcnow()
        if self.next_fundamental_snapshot_retry_at is not None:
            return now >= self.next_fundamental_snapshot_retry_at
        if self.last_fundamental_snapshot_at is None:
            return True
        elapsed = (now - self.last_fundamental_snapshot_at).total_seconds()
        return elapsed >= self._fundamental_snapshot_effective_poll_seconds()

    def _fundamental_snapshot_effective_poll_seconds(self) -> int:
        configured = max(1, int(self.settings.fundamental_snapshot_poll_seconds))
        freshness_days = max(0, int(self.settings.fundamental_snapshot_refresh_days))
        if freshness_days == 0:
            return configured
        # A configured poll at or beyond the freshness SLA cannot keep data
        # continuously ready. Cap it at half the SLA so a retry window remains.
        freshness_seconds = freshness_days * SECONDS_PER_DAY
        return min(configured, max(1, freshness_seconds // 2))

    def _fundamental_snapshot_retry_seconds(self) -> int:
        return min(
            FUNDAMENTAL_SNAPSHOT_RETRY_SECONDS,
            self._fundamental_snapshot_effective_poll_seconds(),
        )

    def _fundamental_snapshot_collection_refresh_days(self) -> int:
        """Refresh before the quality SLA expires between collector polls."""
        freshness_days = max(0, int(self.settings.fundamental_snapshot_refresh_days))
        if freshness_days == 0:
            return 0
        poll_seconds = self._fundamental_snapshot_effective_poll_seconds()
        poll_days = max(1, (poll_seconds + SECONDS_PER_DAY - 1) // SECONDS_PER_DAY)
        return max(0, freshness_days - poll_days)

    def _stock_news_snapshot_due(self) -> bool:
        if self.last_stock_news_snapshot_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_stock_news_snapshot_at).total_seconds()
        return elapsed >= self.settings.stock_news_snapshot_poll_seconds

    def _stock_company_snapshot_due(self) -> bool:
        if self.last_stock_company_snapshot_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_stock_company_snapshot_at).total_seconds()
        return elapsed >= self.settings.stock_company_snapshot_poll_seconds

    def _macro_due(self) -> bool:
        if self.last_macro_at is None:
            return True
        elapsed = (datetime.utcnow() - self.last_macro_at).total_seconds()
        return elapsed >= self.settings.macro_poll_seconds

    def _collect_prices(self, db, now: Optional[datetime] = None) -> dict[str, object]:
        current = now or datetime.now(KST)
        if current.tzinfo is None:
            current = current.replace(tzinfo=KST)
        else:
            current = current.astimezone(KST)
        target_yyyymmdd = current.strftime("%Y%m%d")
        if not is_korea_market_session_date(current.date(), current):
            completed_target = latest_completed_korea_market_session_date(current)
            if (
                completed_target
                and self.last_post_close_price_repair_date != completed_target
            ):
                repaired = self._repair_signal_price_ohlc(db, completed_target)
                self.last_post_close_price_repair_date = completed_target
                if repaired:
                    return {
                        "source": "previous_session_price_ohlc_repair",
                        "rows_loaded": repaired,
                        "message": f"date={completed_target.isoformat()} repaired_after_close",
                    }
            return {
                "source": "market_closed",
                "rows_loaded": 0,
                "message": f"date={target_yyyymmdd} skipped_non_trading_day",
            }
        coverage = self._latest_price_coverage(db, target_yyyymmdd)
        if coverage["total"] and coverage["coverage_ratio"] >= 0.95:
            if self._post_close_price_repair_due(current):
                repaired = self._repair_signal_price_ohlc(
                    db,
                    current.date(),
                    force=True,
                )
                if repaired:
                    self.last_post_close_price_repair_date = current.date()
                return {
                    "source": "post_close_price_ohlc_finalize",
                    "rows_loaded": repaired,
                    "message": (
                        f"date={target_yyyymmdd} fresh={coverage['fresh']}/{coverage['total']} "
                        f"coverage={coverage['coverage_ratio']:.2%} finalized={repaired}"
                    ),
                }
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
            repaired = self._repair_signal_price_ohlc(db, current.date())
            return {
                "source": "krx_market+naver_ohlc_repair" if repaired else "krx_market",
                "rows_loaded": total_rows + repaired,
                "message": (
                    f"date={target_yyyymmdd} markets=KOSPI,KOSDAQ "
                    f"errors={len(market_errors)} repaired={repaired}"
                ),
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
                must_finalize_close = self._post_close_price_repair_due(current)
                repaired = self._repair_signal_price_ohlc(
                    db,
                    current.date(),
                    force=must_finalize_close,
                )
                if must_finalize_close and repaired:
                    self.last_post_close_price_repair_date = current.date()
                return {
                    "source": "naver_quotes+naver_ohlc_repair" if repaired else "naver_full_quotes",
                    "rows_loaded": naver_rows + repaired,
                    "message": (
                        f"date={target_yyyymmdd} markets=KOSPI,KOSDAQ "
                        f"krx_errors={len(market_errors)} repaired={repaired}"
                    ),
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
            from_yyyymmdd=(current - timedelta(days=self.settings.price_days_back)).strftime("%Y%m%d"),
            to_yyyymmdd=target_yyyymmdd,
            max_workers=self.settings.price_max_workers,
        )
        return {
            "source": "event_code_history",
            "rows_loaded": rows,
            "message": f"date={target_yyyymmdd} codes={len(codes)} krx_errors={len(market_errors)}",
        }

    def _repair_signal_price_ohlc(
        self,
        db,
        target_date,
        *,
        force: bool = False,
    ) -> int:
        market_rows = list(
            db.execute(
                select(StockMaster.code, DailyPrice)
                .outerjoin(
                    DailyPrice,
                    (DailyPrice.code == StockMaster.code)
                    & (DailyPrice.trade_date == target_date),
                )
                .where(
                    StockMaster.is_active.is_(True),
                    StockMaster.market.in_(("KOSPI", "KOSDAQ")),
                )
                .order_by(
                    desc(DailyPrice.market_cap).nullslast(),
                    StockMaster.code,
                )
            )
        )
        repair_codes = [
            code
            for rank, (code, row) in enumerate(market_rows, start=1)
            if ((force and rank <= 100) or row is None or not _has_complete_price_ohlc(row))
            and not (
                row is not None
                and (row.volume or 0) == 0
                and (row.trading_value or 0) == 0
            )
        ]
        if not repair_codes:
            return 0
        history_rows = collect_naver_price_history_for_codes(
            db,
            repair_codes,
            pages=1,
            max_workers=min(12, max(1, self.settings.price_max_workers)),
        )
        krx_rows = collect_naver_krx_price_rows_for_codes(
            db,
            repair_codes,
            target_date,
            max_workers=min(12, max(1, self.settings.price_max_workers)),
        )
        finalized_rows = self._finalize_signal_price_ohlc_from_kis(
            db,
            repair_codes,
            target_date,
        )
        return history_rows + krx_rows + finalized_rows

    def _finalize_signal_price_ohlc_from_kis(
        self,
        db,
        codes: list[str],
        target_date: date,
    ) -> int:
        if not self.market_provider.is_configured():
            return 0
        try:
            rows = self.market_provider.fetch_daily_price_rows(codes, target_date)
        except Exception:
            return 0
        if not rows:
            return 0
        count = upsert_many(db, DailyPrice, rows)
        db.commit()
        return count

    def _post_close_price_repair_due(self, current: datetime) -> bool:
        return bool(
            # Naver publishes the official KRX daily candle after its 16:30
            # close-price send window. Running at 15:40 can persist a partial
            # candle even though the trading signal itself is already closed.
            current.time() >= time(16, 35)
            and self.last_post_close_price_repair_date != current.date()
        )

    def _latest_price_coverage(self, db, target_yyyymmdd: str) -> dict[str, object]:
        target_date = datetime.strptime(target_yyyymmdd, "%Y%m%d").date()
        code_rows = db.execute(
            select(StockMaster.code).where(
                StockMaster.is_active.is_(True),
                StockMaster.market.in_(["KOSPI", "KOSDAQ"]),
            )
        ).all()
        codes = [row[0] for row in code_rows if row[0]]
        if not codes:
            return {"total": 0, "fresh": 0, "coverage_ratio": 0.0}
        target_rows = list(
            db.scalars(
                select(DailyPrice).where(
                    DailyPrice.code.in_(codes),
                    DailyPrice.trade_date == target_date,
                )
            )
        )
        fresh_codes = {
            row.code
            for row in target_rows
            if _has_complete_price_ohlc(row)
        }
        fresh = len(fresh_codes)
        return {
            "total": len(codes),
            "fresh": fresh,
            "coverage_ratio": fresh / len(codes),
        }

    def _collect_investor_flows(self, db) -> dict[str, object]:
        coverage = self._latest_investor_flow_coverage(db)
        stale_codes = coverage.get("stale_codes")
        has_exact_stale_codes = isinstance(stale_codes, list)
        if not coverage["total"] or coverage["coverage_ratio"] >= 0.95:
            return {
                "source": "existing_investor_flows",
                "rows_loaded": 0,
                "message": (
                    f"target={coverage['target_date']} fresh={coverage['fresh']}/{coverage['total']} "
                    f"coverage={coverage['coverage_ratio']:.2%}"
                ),
            }
        collector_kwargs: dict[str, object] = {
            "pages": self.settings.investor_flow_pages,
            "max_workers": self.settings.investor_flow_max_workers,
        }
        if has_exact_stale_codes:
            target_codes = stale_codes
            if self.settings.investor_flow_code_limit:
                target_codes = target_codes[: self.settings.investor_flow_code_limit]
            collector_kwargs["codes"] = target_codes
        else:
            collector_kwargs.update(
                {
                    "markets": "KOSPI,KOSDAQ",
                    "limit": self.settings.investor_flow_code_limit,
                }
            )
        rows = collect_naver_investor_flows(db, **collector_kwargs)
        return {
            "source": "naver_investor_flow",
            "rows_loaded": rows,
            "message": (
                f"pages={self.settings.investor_flow_pages} target={coverage['target_date']} "
                f"stale={len(stale_codes) if has_exact_stale_codes else 'unknown'}"
            ),
        }

    def _latest_investor_flow_coverage(
        self,
        db,
        now: Optional[datetime] = None,
    ) -> dict[str, object]:
        current = now or datetime.now(KST)
        calendar_target = latest_completed_korea_market_session_date(current)
        stored_price_target = db.scalar(select(func.max(DailyPrice.trade_date)))
        target_date = calendar_target or stored_price_target or current.date()
        code_statement = select(StockMaster.code).where(
            StockMaster.is_active.is_(True),
            StockMaster.market.in_(["KOSPI", "KOSDAQ"]),
        )
        if stored_price_target is not None:
            code_statement = code_statement.outerjoin(
                DailyPrice,
                (DailyPrice.code == StockMaster.code)
                & (DailyPrice.trade_date == stored_price_target),
            ).order_by(
                desc(func.coalesce(DailyPrice.market_cap, 0)),
                StockMaster.market,
                StockMaster.code,
            )
        else:
            code_statement = code_statement.order_by(StockMaster.market, StockMaster.code)
        if self.settings.investor_flow_code_limit:
            # Investor flow is used by the same ranked signal universe.  Keep the
            # freshness denominator bounded to that configured universe as well;
            # otherwise each poll walks the next block of all listed stocks and
            # the signal-critical top names never reach the 95% ready threshold.
            code_statement = code_statement.limit(self.settings.investor_flow_code_limit)
        code_rows = db.execute(code_statement).all()
        codes = [row[0] for row in code_rows if row[0]]
        if not codes:
            return {
                "target_date": target_date,
                "total": 0,
                "fresh": 0,
                "coverage_ratio": 0.0,
                "stale_codes": [],
            }
        latest_rows = db.execute(
            select(InvestorFlow.code, func.max(InvestorFlow.trade_date))
            .where(InvestorFlow.code.in_(codes))
            .group_by(InvestorFlow.code)
        ).all()
        latest_by_code = {code: latest_date for code, latest_date in latest_rows}
        stale_codes = [
            code
            for code in codes
            if not latest_by_code.get(code) or latest_by_code[code] < target_date
        ]
        fresh = len(codes) - len(stale_codes)
        return {
            "target_date": target_date,
            "total": len(codes),
            "fresh": fresh,
            "coverage_ratio": fresh / len(codes),
            "stale_codes": stale_codes,
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

    def _latest_macro_coverage(
        self,
        db,
        now: Optional[datetime] = None,
    ) -> dict[str, object]:
        series_codes = [item["symbol"] for item in DEFAULT_MACRO_SERIES]
        current = now or datetime.now(KST)
        if current.tzinfo is None:
            current = current.replace(tzinfo=KST)
        else:
            current = current.astimezone(KST)
        fresh_since = (current.astimezone(timezone.utc).replace(tzinfo=None) - timedelta(days=7)).date().isoformat()
        market_target = latest_korea_market_session_date(current)
        if market_target is None:
            market_target = db.scalar(select(func.max(DailyPrice.trade_date)))
        rows = db.execute(
            select(MacroObservation.series_code, func.max(MacroObservation.period))
            .where(MacroObservation.source.in_(("yahoo", "naver_finance")))
            .where(MacroObservation.series_code.in_(series_codes))
            .group_by(MacroObservation.series_code)
        ).all()
        latest_by_series = {code: period for code, period in rows}
        market_series = {"^KS11", "^KQ11"}
        fresh_by_series = {
            code: bool(
                latest_by_series.get(code)
                and (
                    latest_by_series[code] >= market_target.isoformat()
                    if code in market_series and market_target is not None
                    else latest_by_series[code] >= fresh_since
                )
            )
            for code in series_codes
        }
        fresh = sum(1 for value in fresh_by_series.values() if value)
        return {
            "total": len(series_codes),
            "fresh": fresh,
            "fresh_since": fresh_since,
            "market_target": market_target,
            "latest_by_series": latest_by_series,
            "stale_series": [code for code, is_fresh in fresh_by_series.items() if not is_fresh],
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
            "stock_universe_enabled": self.settings.stock_universe_enabled,
            "running": self.running,
            "poll_seconds": self.settings.briefing_poll_seconds,
            "snapshot_seconds": self.settings.briefing_snapshot_seconds,
            "retention_snapshots": self.settings.briefing_retention_snapshots,
            "research_poll_seconds": self.settings.research_poll_seconds,
            "research_backfill_poll_seconds": self.settings.research_backfill_poll_seconds,
            "disclosure_poll_seconds": self.settings.disclosure_poll_seconds,
            "news_poll_seconds": self.settings.news_poll_seconds,
            "price_poll_seconds": self.settings.price_poll_seconds,
            "stock_universe_poll_seconds": self.settings.stock_universe_poll_seconds,
            "investor_flow_enabled": self.settings.investor_flow_enabled,
            "investor_flow_poll_seconds": self.settings.investor_flow_poll_seconds,
            "financials_enabled": self.settings.financials_enabled,
            "financials_poll_seconds": self.settings.financials_poll_seconds,
            "fundamental_snapshot_enabled": self.settings.fundamental_snapshot_enabled,
            "fundamental_snapshot_poll_seconds": self.settings.fundamental_snapshot_poll_seconds,
            "fundamental_snapshot_effective_poll_seconds": self._fundamental_snapshot_effective_poll_seconds(),
            "fundamental_snapshot_refresh_days": self.settings.fundamental_snapshot_refresh_days,
            "fundamental_snapshot_collection_refresh_days": self._fundamental_snapshot_collection_refresh_days(),
            "stock_news_snapshot_enabled": self.settings.stock_news_snapshot_enabled,
            "stock_news_snapshot_poll_seconds": self.settings.stock_news_snapshot_poll_seconds,
            "stock_company_snapshot_enabled": self.settings.stock_company_snapshot_enabled,
            "stock_company_snapshot_poll_seconds": self.settings.stock_company_snapshot_poll_seconds,
            "macro_enabled": self.settings.macro_enabled,
            "macro_poll_seconds": self.settings.macro_poll_seconds,
            "configured_sources": self.configured_sources(),
            "last_success_at": self.last_success_at,
            "last_briefing_at": self.last_briefing_at,
            "last_research_at": self.last_research_at,
            "last_research_backfill_at": self.last_research_backfill_at,
            "last_disclosure_at": self.last_disclosure_at,
            "last_disclosure_source": self.last_disclosure_source,
            "last_disclosure_message": self.last_disclosure_message,
            "last_news_at": self.last_news_at,
            "last_price_at": self.last_price_at,
            "last_price_source": self.last_price_source,
            "last_price_message": self.last_price_message,
            "last_stock_universe_at": self.last_stock_universe_at,
            "last_stock_universe_message": self.last_stock_universe_message,
            "last_investor_flow_at": self.last_investor_flow_at,
            "last_investor_flow_source": self.last_investor_flow_source,
            "last_investor_flow_message": self.last_investor_flow_message,
            "last_financials_at": self.last_financials_at,
            "last_financials_source": self.last_financials_source,
            "last_financials_message": self.last_financials_message,
            "last_fundamental_snapshot_at": self.last_fundamental_snapshot_at,
            "last_fundamental_snapshot_message": self.last_fundamental_snapshot_message,
            "last_fundamental_snapshot_state": self.last_fundamental_snapshot_state,
            "last_fundamental_snapshot_priority_failed": self.last_fundamental_snapshot_priority_failed,
            "last_fundamental_snapshot_full_failed": self.last_fundamental_snapshot_full_failed,
            "next_fundamental_snapshot_retry_at": self.next_fundamental_snapshot_retry_at,
            "last_stock_news_snapshot_at": self.last_stock_news_snapshot_at,
            "last_stock_news_snapshot_message": self.last_stock_news_snapshot_message,
            "last_stock_company_snapshot_at": self.last_stock_company_snapshot_at,
            "last_stock_company_snapshot_message": self.last_stock_company_snapshot_message,
            "last_macro_at": self.last_macro_at,
            "last_macro_source": self.last_macro_source,
            "last_macro_message": self.last_macro_message,
            "last_error": self.last_error,
            "source_errors": self.source_errors,
        }


briefing_runtime = BriefingRuntime()
