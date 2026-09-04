from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import hmac
import html
import json
import logging
import secrets
import time as time_module
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from threading import RLock
from typing import Any, Optional
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

import requests
import websockets
from bs4 import BeautifulSoup
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, desc, func, or_, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, get_db, init_db, recover_interrupted_ingestions
from app.meta import integration_payload, insight_cadence_payload, research_source_payload
from app.collectors.research import ensure_stock_research_reports
from app.models import (
    CompanyProfile,
    DailyPrice,
    DashboardAccessIdentity,
    DashboardAccessQuota,
    DesktopUserPreference,
    FinancialStatementLine,
    IngestionRun,
    InvestorFlow,
    MacroObservation,
    MarketRankingSnapshot,
    PushNotificationHistory,
    PushSubscription,
    RecommendationTrackState,
    StockLogo,
    StockMaster,
    StockIntradaySnapshot,
    WatchlistItem,
)
from app.repository import (
    briefing_events,
    briefing_metrics,
    briefing_movers,
    briefing_quotes,
    latest_briefing_snapshot,
    latest_prices_by_codes,
    latest_research_reports,
    list_briefing_snapshots,
    list_stocks,
)
from app.schemas import (
    BriefingQuoteOut,
    BriefingRuntimeStatusOut,
    BriefingSnapshotOut,
    BriefingSnapshotSummaryOut,
    CompanyBriefOut,
    DailyPriceOut,
    DashboardAccessIn,
    DesktopPreferenceIn,
    DisclosureItemOut,
    FinancialStatementLineOut,
    InsightCadenceOut,
    IntegrationMetaOut,
    InviteAccessIn,
    IngestionRunOut,
    InvestorFlowOut,
    MacroObservationOut,
    MarketImpactOut,
    MarketRankingOut,
    MarketRecommendationOut,
    MorningMoneyBriefingOut,
    NewsItemOut,
    PushSubscriptionDeleteIn,
    PushSubscriptionIn,
    RecommendationTrackStateOut,
    RecommendationTrackUpdateIn,
    ResearchSourceOut,
    ResearchReportOut,
    StockAIAnalysisOut,
    StockCommunityFeedOut,
    StockEtfProfileOut,
    StockHomeContextOut,
    StockQuantSignalsOut,
    StockSgaAnalysisOut,
    StockSectorOperatingMarginComparisonOut,
    StockOut,
    StockDashboardOut,
    StockXFeedOut,
    TrendAnalysisOut,
    TrendEventGraphOut,
    WatchlistOut,
    WatchlistUpdateIn,
)
from app.services.briefing import briefing_runtime
from app.collectors.briefing import KisRestBriefingProvider
from app.collectors.disclosures import collect_disclosures
from app.collectors.naver_flows import collect_naver_investor_flows
from app.collectors.news import preferred_news_url
from app.bootstrap import bootstrap_runtime_data
from app.mcp_server import build_insight_mcp_server
from app.services.company_briefs import build_company_briefs
from app.services.chart_patterns import CHART_PATTERN_SCHEMA_VERSION, detect_chart_patterns
from app.services.company_profiles import ensure_company_profile
from app.services.community_feed import build_stock_community_feed
from app.services.dashboard_market_data import (
    DashboardMarketDataError,
    build_korea_market_calendar,
    fetch_stock_week_chart,
)
from app.services.etf_profiles import (
    ETF_HOLDINGS_SNAPSHOT_KEY,
    ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION,
    build_etf_profile,
    build_naver_etf_holdings_snapshot,
    is_likely_etf_name,
    validate_etf_holdings_snapshot,
)
from app.services.market_indices import build_market_indices, merge_live_market_indices
from app.services.staging_page_summary import (
    PageSummaryResponse,
    summarize_staging_page,
)
from app.services.market_calendar import (
    is_korea_market_session_date,
    is_korea_regular_market_session,
    latest_completed_korea_market_session_date,
)
from app.services.global_market_assets import (
    GLOBAL_MARKET_DEFINITIONS,
    build_stored_global_market_assets,
    fetch_live_global_market_assets,
    merge_global_market_assets,
)
from app.services.market_rankings import (
    build_market_period_returns,
    build_market_rankings,
    enrich_market_ranking_sector_fields,
)
from app.services.market_impact import build_market_impact
from app.services.morning_money_briefing import (
    build_morning_money_briefing,
    build_morning_money_briefing_history,
    money_briefing_edition,
)
from app.services.recommendations import build_recommendations
from app.services.stock_ai_analysis import build_stock_ai_analysis
from app.services.local_stock_ai import enrich_stock_ai_analysis
from app.services.quant_signals import (
    MARKET_SIGNAL_UNIVERSE_LIMIT,
    MIN_BACKTEST_HISTORY_ROWS,
    STRATEGY_VERSION,
    enrich_market_quant_signal_sectors,
    enrich_quant_signal_payload_sector,
    load_external_market_quant_signal_feed,
    load_external_stock_quant_signal_payload,
    load_market_quant_signal_feed,
    load_market_quant_signal_snapshot,
    market_payload_has_trade_metadata,
    load_reference_quant_signal_payload,
    quant_signal_current_summary_fields,
    quant_payload_has_trade_metadata,
    sanitize_pending_entry_signal_payload,
    sanitize_pending_entry_signal_items,
    save_market_quant_signal_snapshot,
    synchronize_quant_payload_live_quote,
)
from app.services.entry_filter_backtest import refresh_entry_filter_shadow_snapshot
from app.services.signal_reconciliations import (
    apply_market_signal_reconciliations,
    apply_stock_signal_reconciliations,
)
from app.services.signal_data_quality import (
    probe_signal_source_apis,
    signal_data_quality_status,
)
from app.services.stock_dashboard import (
    _daily_price_has_complete_ohlc,
    _naver_snapshot,
    build_stock_dashboard,
    ensure_stock_price_history,
    stock_news_item_payloads,
)
from app.services.complete_snapshots import (
    SnapshotPublishConflictError,
    get as get_complete_snapshot,
    publish as publish_complete_snapshot,
    request_refresh as request_complete_snapshot_refresh,
)
from app.services.snapshot_runtime import SnapshotBuild, SnapshotHandler, SnapshotRuntime
from app.services.sector_margin_comparison import build_sector_margin_comparison
from app.services.sga_analysis import build_sga_analysis
from app.services.stock_data_coverage import stock_data_coverage
from app.services.stock_logos import ensure_stock_logo, sync_stock_logos
from app.services.x_feed import build_stock_x_feed
from app.services.kis_realtime import (
    KIS_REALTIME_STOCK_TR_ID,
    KisRealtimeError,
    KisRealtimeQuoteProvider,
    parse_kis_stock_tick,
)
from app.services.ttl_cache import TTLCache
from app.services.trends import build_event_graph, build_trend_analysis
from app.services.web_push import (
    notification_history_event_date,
    notification_history_is_valid,
    notification_history_signal_name,
    notification_history_signal_context,
    web_push_runtime,
)
from app.services.us_market import (
    US_SECTOR_ETFS,
    build_us_dashboard,
    build_us_event_graph,
    build_us_market_impact,
    build_us_rankings,
    build_us_recommendations,
    build_us_trends,
    resolve_us_stock,
    search_us_stocks,
    usdkrw_rate,
    us_prices,
    us_sector_moves,
)
from app.repository import latest_disclosures, latest_news_items

settings = get_settings()
logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
INSIGHT_INDEX = STATIC_DIR / "insight" / "index.html"
DESKTOP_INDEX = STATIC_DIR / "desktop" / "index.html"
DESKTOP_SERVICE_WORKER = STATIC_DIR / "desktop" / "desktop-sw.js"
STOCK_DASHBOARD_INDEX = STATIC_DIR / "dashboard" / "index.html"
STOCK_DASHBOARD_APP = STATIC_DIR / "dashboard" / "app.js"
STOCK_DASHBOARD_STYLES = STATIC_DIR / "dashboard" / "styles.css"
MANUAL_STOCK_LOGO_DIR = STATIC_DIR / "stock-logos"
PORTFOLIO_INDEX = STATIC_DIR / "portfolio" / "index.html"
CONCEPTS_INDEX = STATIC_DIR / "concepts" / "index.html"
DASHBOARD_MANIFEST = STATIC_DIR / "dashboard" / "manifest.webmanifest"
DASHBOARD_SERVICE_WORKER = STATIC_DIR / "dashboard" / "dashboard-sw.js"
DASHBOARD_CLIENT_VERSION = "20260904v465"
DASHBOARD_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
DASHBOARD_MUTABLE_ASSET_CACHE_CONTROL = "no-store, no-cache, must-revalidate, max-age=0"
NASDAQ_DASHBOARD_INDEX = STATIC_DIR / "nasdaq" / "index.html"
NASDAQ_MANIFEST = STATIC_DIR / "nasdaq" / "manifest.webmanifest"
NASDAQ_SERVICE_WORKER = STATIC_DIR / "nasdaq" / "dashboard-sw.js"
api_cache = TTLCache(maxsize=1024)
stock_research_refresh_cache = TTLCache(maxsize=2048)
stock_investor_flow_refresh_cache = TTLCache(maxsize=2048)
intraday_chart_cache = TTLCache(maxsize=4096)
market_quant_signal_cache = TTLCache(maxsize=16)
watchlist_quant_signal_cache = TTLCache(maxsize=256)
live_quote_cache = TTLCache(maxsize=1024)
morning_money_briefing_cache = TTLCache(maxsize=32)
MORNING_MONEY_BRIEFING_CACHE_SECONDS = 30
MORNING_MONEY_HISTORY_CACHE_SECONDS = 120
complete_snapshot_runtime: Optional[SnapshotRuntime] = None
market_quant_signal_refresh_lock = RLock()
entry_filter_shadow_refresh_lock = RLock()
MARKET_QUANT_SIGNAL_ACTIVE_MAX_AGE_SECONDS = 10 * 60
MARKET_QUANT_SIGNAL_CLOSED_MAX_AGE_SECONDS = 6 * 60 * 60
kis_realtime_provider = KisRealtimeQuoteProvider(settings)
kis_rest_provider = KisRestBriefingProvider(settings)
mcp_server = (
    build_insight_mcp_server(settings)
    if settings.mcp_enabled and settings.runs_web_services()
    else None
)
kis_quote_subscribers: dict[str, set[asyncio.Queue]] = {}
kis_realtime_active_codes: set[str] = set()
kis_quote_lock = asyncio.Lock()
kis_realtime_hub_task: Optional[asyncio.Task] = None
kis_realtime_idle_disconnect_task: Optional[asyncio.Task] = None
kis_realtime_control_queue: asyncio.Queue = asyncio.Queue(
    maxsize=max(1, int(settings.quote_stream_control_queue_size))
)
kis_quote_last_broadcast_at: dict[str, float] = {}
kis_quote_last_received_at: dict[str, float] = {}
kis_quote_pending_payloads: dict[str, dict[str, object]] = {}
kis_quote_flush_tasks: dict[str, asyncio.Task] = {}
quote_fallback_poll_task: Optional[asyncio.Task] = None
quote_fallback_last_polled_at: dict[str, float] = {}
live_quote_async_lock = asyncio.Lock()
live_quote_async_tasks: dict[str, asyncio.Task] = {}
live_quote_fetch_semaphore = asyncio.Semaphore(max(1, settings.quote_stream_fetch_concurrency))
quote_stream_connection_lock = asyncio.Lock()
quote_stream_connections = 0
quote_stream_legacy_connections = 0
quote_stream_peak_connections = 0
quote_stream_metadata_lock = RLock()
quote_stream_sequences: dict[str, int] = {}
quote_stream_last_observed_at: dict[str, float] = {}
quote_stream_last_published_at: dict[str, float] = {}
quote_stream_metrics_lock = RLock()
quote_stream_metrics: dict[str, int] = {
    "quotes_published": 0,
    "quotes_coalesced": 0,
    "stale_quotes_suppressed": 0,
    "fallback_cycles": 0,
    "fallback_codes_polled": 0,
    "subscription_commands": 0,
    "subscription_commands_throttled": 0,
    "subscription_codes_rejected": 0,
    "client_queue_overflows": 0,
    "control_sync_coalesced": 0,
    "signal_revisions_published": 0,
}
ai_signal_revision_lock = RLock()
ai_signal_revision_state: dict[str, object] = {
    "revision": 0,
    "as_of": None,
    "code_signatures": {},
}
ai_signal_revision_clients: dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}
presence_page_clients: dict[str, set[WebSocket]] = {}
presence_client_pages: dict[WebSocket, str] = {}
presence_lock = asyncio.Lock()
write_session_cache = TTLCache(maxsize=8192)
rate_limit_lock = RLock()
rate_limit_windows: dict[tuple[str, str], list[float]] = {}
intraday_lock_guard = RLock()
intraday_code_locks: dict[str, RLock] = {}

STOCK_DASHBOARD_TTL_SECONDS = 120
SECTOR_MARGIN_COMPARISON_TTL_SECONDS = 60 * 60 * 6
SGA_ANALYSIS_TTL_SECONDS = 60 * 60 * 12
STOCK_HOME_CONTEXT_TTL_SECONDS = 120
STOCK_DISCLOSURE_WINDOW_TTL_SECONDS = 60 * 60
STOCK_DISCLOSURE_WINDOW_DAYS = 30
STOCK_INVESTOR_FLOW_REFRESH_TTL_SECONDS = 300
MARKET_RANKING_TTL_SECONDS = 120
MARKET_INDICES_TTL_SECONDS = 300
GLOBAL_MARKET_ASSETS_TTL_SECONDS = 30
MARKET_IMPACT_TTL_SECONDS = 60
RECOMMENDATION_TTL_SECONDS = 600
RECOMMENDATION_EMPTY_CACHE_TTL_SECONDS = 5
INTRADAY_CLOSED_TTL_SECONDS = 60 * 60 * 72
INTRADAY_WARMUP_MAX_STOCKS = 60
INTRADAY_WARMUP_START = time(15, 35)
QUANT_SIGNAL_QUOTE_REFRESH_END = time(18, 0)
TREND_ANALYSIS_TTL_SECONDS = 60
TREND_GRAPH_TTL_SECONDS = 300
WRITE_SESSION_COOKIE = "sn_write_session"
WRITE_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
DESKTOP_SESSION_COOKIE = "sn_desktop_session"
DESKTOP_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
DEFAULT_DESKTOP_DOCUMENT_TITLE = "한국증시 비밀노트"
INVITE_ACCESS_COOKIE = "sn_invite_access"
INVITE_ACCESS_TTL_SECONDS = 60 * 60 * 24 * 365
DASHBOARD_ACCESS_QUOTA_ID = 1
LOCAL_ONLY_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}
KST = ZoneInfo("Asia/Seoul")
SURGE_RANKING_SNAPSHOT_REUSE_SECONDS = MARKET_RANKING_TTL_SECONDS
SURGE_RANKING_SNAPSHOT_RETENTION = timedelta(days=1)
SURGE_RANKING_SNAPSHOT_PER_MARKET_LIMIT = 100
SURGE_RANKING_MARKETS = ("KOSPI", "KOSDAQ")
COMPLETE_SNAPSHOT_SCHEMA_VERSION = 1
STOCK_DASHBOARD_SNAPSHOT_PREFIX = "stock-dashboard:v1:"
STOCK_HOME_CONTEXT_SNAPSHOT_PREFIX = "stock-home-context:v1:"
MARKET_RANKING_SNAPSHOT_PREFIX = "market-ranking:v1:"
MARKET_INDICES_SNAPSHOT_PREFIX = "market-indices:v1:"
GLOBAL_MARKET_ASSETS_SNAPSHOT_PREFIX = "global-market-assets:v1:"
US_SECTOR_MOVES_SNAPSHOT_KEY = "us-sector-moves:v1"
SURGE_COMPLETE_SNAPSHOT_KEY = f"{MARKET_RANKING_SNAPSHOT_PREFIX}surge"


def _news_item_payload(item) -> dict[str, object]:
    payload = NewsItemOut.model_validate(item).model_dump(mode="json")
    payload["detail_url"] = preferred_news_url(
        payload.get("source"),
        payload.get("external_id"),
        payload.get("detail_url"),
    )
    return payload


def _refresh_stock_disclosure_window(db: Session, stock_code: str) -> None:
    if not settings.dart_api_key:
        return
    existing = latest_disclosures(db, limit=1, stock_code=stock_code)
    first = existing[0] if existing else None
    corp_code = str(
        first.get("corp_code") if isinstance(first, dict) else getattr(first, "corp_code", "") or ""
    ).strip()
    if not corp_code:
        profile = db.get(CompanyProfile, stock_code)
        corp_code = str(getattr(profile, "corp_code", "") or "").strip()
    if not corp_code:
        return
    key = (
        "stock_disclosure_window",
        stock_code,
        corp_code,
        datetime.now(KST).date().isoformat(),
    )

    def refresh() -> int:
        result = collect_disclosures(
            db,
            settings=settings,
            days_back=STOCK_DISCLOSURE_WINDOW_DAYS,
            page_count=100,
            corp_code=corp_code,
            stock_code=stock_code,
        )
        return result.rows_loaded

    try:
        api_cache.get_or_set(key, STOCK_DISCLOSURE_WINDOW_TTL_SECONDS, refresh)
    except Exception as exc:
        logger.warning("stock disclosure window refresh failed for %s: %s", stock_code, exc)


def _latest_stock_investor_flow_date(db: Session, stock_code: str) -> Optional[date]:
    return db.scalar(
        select(func.max(InvestorFlow.trade_date)).where(InvestorFlow.code == stock_code)
    )


def _refresh_stock_investor_flow_if_stale(
    db: Session,
    stock_code: str,
    *,
    now: Optional[datetime] = None,
    pages: int = 1,
    force: bool = False,
) -> dict[str, object]:
    """Refresh one detail page from the flow source when its latest day is stale."""
    current = now or datetime.now(KST)
    target_date = latest_completed_korea_market_session_date(current)
    stored_date = _latest_stock_investor_flow_date(db, stock_code)
    if not force and target_date is not None and stored_date is not None and stored_date >= target_date:
        return {
            "refreshed": False,
            "target_date": target_date,
            "latest_date": stored_date,
        }

    refresh_key = (
        "stock_investor_flow_refresh",
        stock_code,
        target_date.isoformat() if target_date else current.date().isoformat(),
    )

    def refresh_once() -> dict[str, object]:
        try:
            rows_loaded = collect_naver_investor_flows(
                db,
                codes=[stock_code],
                pages=max(1, min(int(pages), 20)),
                max_workers=1,
                batch_size=500,
            )
            return {"ok": True, "rows_loaded": rows_loaded}
        except Exception as exc:
            db.rollback()
            logger.warning("Investor flow refresh failed for %s: %s", stock_code, exc)
            return {"ok": False, "rows_loaded": 0}

    result = (
        refresh_once()
        if force
        else stock_investor_flow_refresh_cache.get_or_set(
            refresh_key,
            STOCK_INVESTOR_FLOW_REFRESH_TTL_SECONDS,
            refresh_once,
        )
    )
    latest_date = _latest_stock_investor_flow_date(db, stock_code)
    return {
        "refreshed": bool(result.get("ok") and result.get("rows_loaded")),
        "target_date": target_date,
        "latest_date": latest_date,
    }


PUSH_CONDITION_OPTIONS = [
    {
        "id": "morning_briefing",
        "label": "돈이 되는 소식",
        "description": "매일 오전 8시·낮 12시·오후 4시에 새 소식을 알려드립니다.",
        "required": True,
    },
    {
        "id": "market_session",
        "label": "국내장 시작·마감",
        "description": "국내 정규장 시작과 마감 5분 전에 알려드립니다.",
    },
    {
        "id": "ai_signal",
        "label": "AI 시그널",
        "description": "관심종목의 장중 예비·장 마감 확정 신호를 알려드립니다.",
        "required": True,
    },
    {
        "id": "market_ai_signal",
        "label": "시장 AI 시그널",
        "description": "시장 종목의 장중 예비·장 마감 확정 신호를 알려드립니다.",
    },
    {
        "id": "recommendation_update",
        "label": "추천 업데이트",
        "description": "상위 10 신규 진입과 추천 종목의 매수·매도 단계 변경을 알려드립니다.",
    },
    {
        "id": "price_move",
        "label": "급등락",
        "description": f"관심종목 변동이 {settings.web_push_price_threshold:.0f}% 이상이면 알려드립니다.",
    },
    {
        "id": "disclosure_report",
        "label": "중요 공시·리포트",
        "description": "새 공시와 애널리스트 리포트 중 중요한 것만 알려드립니다.",
    },
    {
        "id": "major_event",
        "label": "주요 이벤트",
        "description": "관심종목에 영향이 큰 일정이 가까워지면 알려드립니다.",
    },
]
DEFAULT_PUSH_CONDITIONS = tuple(item["id"] for item in PUSH_CONDITION_OPTIONS)
REQUIRED_PUSH_CONDITIONS = tuple(
    item["id"] for item in PUSH_CONDITION_OPTIONS if item.get("required")
)


async def _run_bootstrap_task() -> None:
    try:
        await asyncio.to_thread(
            bootstrap_runtime_data,
            settings,
            force_refresh=settings.bootstrap_force_refresh,
        )
    except Exception:  # pragma: no cover - operational safeguard
        logger.exception("Background bootstrap failed")


async def _run_intraday_warmup_loop() -> None:
    last_attempted_date: Optional[date] = None
    while True:
        now = datetime.now(KST)
        should_warm = (
            now.weekday() < 5
            and now.time() >= INTRADAY_WARMUP_START
            and last_attempted_date != now.date()
        )
        if should_warm:
            last_attempted_date = now.date()
            try:
                warmed = await asyncio.to_thread(_warm_closed_intraday_snapshots, now)
                logger.info("Closed intraday warmup completed: %s stocks", warmed)
            except Exception:  # pragma: no cover - operational safeguard
                logger.exception("Closed intraday warmup failed")
        await asyncio.sleep(60)


def _market_quant_signal_ohlc_repair_codes(
    db: Session,
    *,
    universe_limit: int = MARKET_SIGNAL_UNIVERSE_LIMIT,
    recent_days: int = 30,
) -> list[str]:
    """Return recent top-universe stocks with an incomplete confirmed candle."""
    market_cap_date = db.scalar(
        select(func.max(DailyPrice.trade_date)).where(DailyPrice.market_cap.is_not(None))
    )
    if market_cap_date is None:
        return []

    capped_universe_limit = max(
        1,
        min(int(universe_limit), MARKET_SIGNAL_UNIVERSE_LIMIT),
    )
    cutoff = market_cap_date - timedelta(days=max(1, min(int(recent_days), 90)))
    daily_ranked = (
        select(
            DailyPrice.code.label("code"),
            func.row_number()
            .over(
                partition_by=DailyPrice.trade_date,
                order_by=(DailyPrice.market_cap.desc(), DailyPrice.code),
            )
            .label("market_cap_rank"),
        )
        .join(StockMaster, StockMaster.code == DailyPrice.code)
        .where(
            StockMaster.is_active.is_(True),
            StockMaster.market.in_(("KOSPI", "KOSDAQ")),
            DailyPrice.trade_date >= cutoff,
            DailyPrice.trade_date <= market_cap_date,
            DailyPrice.market_cap.is_not(None),
            DailyPrice.market_cap > 0,
            DailyPrice.close.is_not(None),
        )
        .subquery()
    )
    universe_codes = set(
        str(code)
        for code in db.scalars(
            select(daily_ranked.c.code).where(
                daily_ranked.c.market_cap_rank <= capped_universe_limit
            )
        )
    )
    if not universe_codes:
        return []

    recent_price_cutoff = market_cap_date - timedelta(days=45)
    incomplete_codes = {
        row.code
        for row in db.scalars(
            select(DailyPrice).where(
                DailyPrice.code.in_(tuple(universe_codes)),
                DailyPrice.trade_date >= recent_price_cutoff,
                DailyPrice.trade_date <= market_cap_date,
            )
        )
        if (
            row.trade_date.weekday() < 5
            and not _daily_price_has_complete_ohlc(row)
            and not ((row.volume or 0) == 0 and (row.trading_value or 0) == 0)
        )
    }
    return sorted(incomplete_codes)


def _repair_market_quant_signal_ohlc(
    db: Session,
    *,
    universe_limit: int = MARKET_SIGNAL_UNIVERSE_LIMIT,
    recent_days: int = 30,
) -> int:
    codes = _market_quant_signal_ohlc_repair_codes(
        db,
        universe_limit=universe_limit,
        recent_days=recent_days,
    )
    if not codes:
        return 0
    from app.collectors.naver_quotes import collect_naver_price_history_for_codes

    return collect_naver_price_history_for_codes(
        db,
        codes,
        pages=3,
        max_workers=12,
    )


def _increment_quote_stream_metric(name: str, amount: int = 1) -> None:
    with quote_stream_metrics_lock:
        quote_stream_metrics[name] = int(quote_stream_metrics.get(name, 0)) + int(amount)


def _is_canonical_market_signal_scope(
    universe_limit: int,
    limit: int,
    recent_days: int,
) -> bool:
    return (
        int(universe_limit) == MARKET_SIGNAL_UNIVERSE_LIMIT
        and int(limit) == 0
        and int(recent_days) == 30
    )


def _signal_revision_token(value: Any) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _signal_revision_token(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_signal_revision_token(item) for item in value]
    return value


def _ai_signal_code_signatures(payload: dict[str, Any]) -> dict[str, str]:
    records: dict[str, list[dict[str, object]]] = {}
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        current = item.get("current") if isinstance(item.get("current"), dict) else {}
        holding_context = (
            item.get("holding_context")
            if isinstance(item.get("holding_context"), dict)
            else {}
        )
        transition = (
            current.get("lifecycle", {}).get("latest_transition", {})
            if isinstance(current.get("lifecycle"), dict)
            else {}
        )
        if not isinstance(transition, dict):
            transition = {}
        records.setdefault(code, []).append(
            {
                "kind": "item",
                "side": item.get("side"),
                "event_side": item.get("event_side"),
                "status": item.get("status"),
                "is_preliminary": bool(item.get("is_preliminary")),
                "signal_date": _signal_revision_token(item.get("signal_date")),
                "execution_date": _signal_revision_token(item.get("execution_date")),
                "action": current.get("action") or item.get("action"),
                "position_open": bool(current.get("position_open")),
                "is_current_holding": bool(item.get("is_current_holding")),
                "current_price": _signal_revision_token(current.get("price")),
                "unrealized_return": _signal_revision_token(
                    current.get("unrealized_return")
                ),
                "entry_date": _signal_revision_token(current.get("entry_date")),
                "entry_price": current.get("entry_price") or item.get("entry_price"),
                "target_sell_price": (
                    current.get("target_sell_price") or item.get("target_sell_price")
                ),
                "target_sell_status": (
                    current.get("target_sell_status") or item.get("target_sell_status")
                ),
                "target_sell_delta": _signal_revision_token(
                    current.get("target_sell_delta")
                    if current.get("target_sell_delta") is not None
                    else item.get("target_sell_delta")
                ),
                "profit_stage": current.get("profit_stage") or item.get("profit_stage"),
                "pending_profit_stage": current.get("pending_profit_stage"),
                "pending_sell_percent": _signal_revision_token(
                    current.get("pending_sell_percent")
                ),
                "expected_remaining_percent": _signal_revision_token(
                    current.get("expected_remaining_percent")
                ),
                "model_exposure_percent": _signal_revision_token(
                    current.get("model_exposure_percent")
                ),
                "stop_reference": current.get("stop_reference"),
                "locked_profit_reference": current.get("locked_profit_reference"),
                "partial_exit_reference": current.get("partial_exit_reference"),
                "return_basis": _signal_revision_token(current.get("return_basis")),
                "holding_context": _signal_revision_token(holding_context),
                "display_return_rate": _signal_revision_token(
                    item.get("display_return_rate")
                ),
                "event_return_rate": _signal_revision_token(item.get("return_rate")),
                "display_return_kind": item.get("display_return_kind"),
                "display_return_event_date": _signal_revision_token(
                    item.get("display_return_event_date")
                ),
                "display_return_event_side": item.get("display_return_event_side"),
                "transition_side": transition.get("side"),
                "transition_date": _signal_revision_token(
                    transition.get("transition_date")
                ),
                "transition_price": transition.get("price"),
                "transition_return_rate": _signal_revision_token(
                    transition.get("return_rate")
                ),
                "reconciliation_id": (
                    current.get("reconciliation_id") or item.get("reconciliation_id")
                ),
            }
        )
    for item in payload.get("preliminary_history") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        records.setdefault(code, []).append(
            {
                "kind": "preliminary_history",
                "side": item.get("side"),
                "signal_date": _signal_revision_token(item.get("signal_date")),
                "active": bool(item.get("active")),
                "first_seen_at": _signal_revision_token(item.get("first_seen_at")),
            }
        )
    signatures: dict[str, str] = {}
    for code, values in records.items():
        encoded = json.dumps(
            sorted(values, key=lambda value: json.dumps(value, sort_keys=True, default=str)),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        signatures[code] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]
    return signatures


def _ai_signal_revision_frame(
    *,
    initial: bool,
    changed_codes: Optional[list[str]] = None,
) -> dict[str, object]:
    with ai_signal_revision_lock:
        revision = int(ai_signal_revision_state.get("revision") or 0)
        as_of = ai_signal_revision_state.get("as_of")
    return {
        "type": "signal_revision",
        "revision": revision,
        "as_of": str(as_of) if as_of else None,
        "changed_codes": sorted(set(changed_codes or [])),
        "initial": bool(initial),
    }


def _publish_ai_signal_revision(changed_codes: list[str]) -> None:
    frame = _ai_signal_revision_frame(initial=False, changed_codes=changed_codes)
    with ai_signal_revision_lock:
        clients = list(ai_signal_revision_clients.items())
    for queue, loop in clients:
        try:
            loop.call_soon_threadsafe(_enqueue_quote_message, queue, dict(frame))
        except RuntimeError:
            with ai_signal_revision_lock:
                ai_signal_revision_clients.pop(queue, None)
    _increment_quote_stream_metric("signal_revisions_published")


def _record_ai_signal_revision(
    payload: Optional[dict[str, Any]],
    *,
    publish: bool,
) -> dict[str, object]:
    """Record a canonical content token; revision equality, not ordering, is the contract."""
    if not isinstance(payload, dict):
        return _ai_signal_revision_frame(initial=not publish)
    signatures = _ai_signal_code_signatures(payload)
    strategy_version = str(payload.get("strategy_version") or "")
    revision_source = json.dumps(
        {"strategy_version": strategy_version, "codes": signatures},
        sort_keys=True,
        separators=(",", ":"),
    )
    revision = int(
        hashlib.sha256(revision_source.encode("utf-8")).hexdigest()[:13],
        16,
    )
    as_of = payload.get("snapshot_generated_at") or payload.get("as_of")
    as_of_token = _signal_revision_token(as_of)
    with ai_signal_revision_lock:
        previous_revision = int(ai_signal_revision_state.get("revision") or 0)
        previous_signatures = dict(ai_signal_revision_state.get("code_signatures") or {})
        previous_strategy = str(ai_signal_revision_state.get("strategy_version") or "")
        ai_signal_revision_state.update(
            {
                "revision": revision,
                "as_of": as_of_token,
                "code_signatures": signatures,
                "strategy_version": strategy_version,
            }
        )
    changed_codes = sorted(
        code
        for code in set(previous_signatures) | set(signatures)
        if previous_signatures.get(code) != signatures.get(code)
    )
    if previous_strategy and previous_strategy != strategy_version:
        changed_codes = sorted(set(previous_signatures) | set(signatures))
    if publish and revision != previous_revision:
        _publish_ai_signal_revision(changed_codes)
    return _ai_signal_revision_frame(initial=not publish, changed_codes=[])


def _current_ai_signal_revision_frame() -> dict[str, object]:
    with ai_signal_revision_lock:
        initialized = int(ai_signal_revision_state.get("revision") or 0) > 0
    if not initialized:
        with SessionLocal() as db:
            payload = load_market_quant_signal_snapshot(db)
            if payload is not None:
                payload = _canonical_ai_signal_revision_payload(
                    db,
                    payload,
                    now=datetime.now(KST),
                )
        if payload is not None:
            _record_ai_signal_revision(payload, publish=False)
    return _ai_signal_revision_frame(initial=True, changed_codes=[])


def _register_ai_signal_revision_client(
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    *,
    enqueue_initial: bool = False,
) -> dict[str, object]:
    with ai_signal_revision_lock:
        ai_signal_revision_clients[queue] = loop
        frame = {
            "type": "signal_revision",
            "revision": int(ai_signal_revision_state.get("revision") or 0),
            "as_of": (
                str(ai_signal_revision_state.get("as_of"))
                if ai_signal_revision_state.get("as_of")
                else None
            ),
            "changed_codes": [],
            "initial": True,
        }
        if enqueue_initial:
            _enqueue_quote_message(queue, frame)
        return frame


def _unregister_ai_signal_revision_client(queue: asyncio.Queue) -> None:
    with ai_signal_revision_lock:
        ai_signal_revision_clients.pop(queue, None)


def _canonical_ai_signal_revision_payload(
    db: Session,
    payload: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Apply the same user-visible transforms used by the canonical HTTP feed."""
    result = deepcopy(payload)
    freshness = _market_quant_signal_snapshot_freshness(result, now)
    result.update(freshness)
    if freshness["snapshot_state"] == "stale":
        result["status"] = "refreshing"
        result = _suppress_stale_preliminary_market_signals(result)
    result = apply_market_signal_reconciliations(result, now=now) or result
    result = enrich_market_quant_signal_sectors(db, result)
    result = _merge_market_preliminary_notification_history(db, result)
    return sanitize_pending_entry_signal_items(result)


def _refresh_market_quant_signal_snapshot(
    universe_limit: int = MARKET_SIGNAL_UNIVERSE_LIMIT,
    limit: int = 0,
    recent_days: int = 30,
) -> Optional[dict[str, Any]]:
    if not market_quant_signal_refresh_lock.acquire(blocking=False):
        return None
    try:
        with SessionLocal() as db:
            current_time = datetime.now(KST)
            repaired_rows = _repair_market_quant_signal_ohlc(
                db,
                universe_limit=universe_limit,
                recent_days=recent_days,
            )
            if repaired_rows:
                logger.info("Market quant signal OHLC repair completed: %s rows", repaired_rows)
            payload = _build_market_quant_signal_payload(
                db,
                universe_limit=universe_limit,
                limit=limit,
                recent_days=recent_days,
                now=current_time,
            )
            stored = save_market_quant_signal_snapshot(
                db,
                payload,
                universe_limit=universe_limit,
                limit=limit,
                recent_days=recent_days,
            )
            market_quant_signal_cache.set(
                ("market_quant_signals", universe_limit, limit, recent_days),
                stored,
                300,
            )
            if _is_canonical_market_signal_scope(universe_limit, limit, recent_days):
                revision_payload = _canonical_ai_signal_revision_payload(
                    db,
                    stored,
                    now=current_time,
                )
                _record_ai_signal_revision(revision_payload, publish=True)
            return stored
    except Exception:  # pragma: no cover - operational safeguard
        logger.exception("Market quant signal snapshot refresh failed")
        return None
    finally:
        market_quant_signal_refresh_lock.release()


def _refresh_entry_filter_shadow_snapshot() -> Optional[dict[str, Any]]:
    if not entry_filter_shadow_refresh_lock.acquire(blocking=False):
        return None
    try:
        with SessionLocal() as db:
            return refresh_entry_filter_shadow_snapshot(db)
    except Exception:  # pragma: no cover - operational safeguard
        logger.exception("Entry filter shadow backtest refresh failed")
        return None
    finally:
        entry_filter_shadow_refresh_lock.release()


async def _run_entry_filter_shadow_backtest_loop() -> None:
    """Keep H1/H2/H3 replayed together whenever a new daily dataset exists."""

    while True:
        try:
            result = await asyncio.to_thread(_refresh_entry_filter_shadow_snapshot)
            if result and result.get("status") == "refreshed":
                report = result.get("report") or {}
                logger.info(
                    "Entry filter shadow backtest refreshed: candidate=%s latest_price_date=%s symbols=%s",
                    report.get("candidate_strategy_version"),
                    report.get("latest_price_date"),
                    report.get("symbols_evaluated"),
                )
        except Exception:  # pragma: no cover - operational safeguard
            logger.exception("Entry filter shadow backtest loop failed")
        await asyncio.sleep(300)


def _build_market_quant_signal_payload(
    db: Session,
    *,
    universe_limit: int,
    limit: int,
    recent_days: int,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(KST)
    external = load_external_market_quant_signal_feed(
        settings.market_quant_signal_source_url,
        universe_limit=universe_limit,
        limit=limit,
        recent_days=recent_days,
        timeout_seconds=settings.market_quant_signal_source_timeout_seconds,
    )
    if external is not None and market_payload_has_trade_metadata(external):
        payload = external
    else:
        payload = load_market_quant_signal_feed(
            db,
            universe_limit=universe_limit,
            limit=limit,
            recent_days=recent_days,
            now=current_time,
            live_quotes=_market_quant_signal_live_quotes(db, universe_limit, current_time),
        )
    payload = apply_market_signal_reconciliations(payload, now=current_time) or payload
    return enrich_market_quant_signal_sectors(db, payload)


def _market_quant_signal_live_quotes(
    db: Session,
    universe_limit: int,
    now: Optional[datetime] = None,
) -> dict[str, dict[str, Any]]:
    market_cap_date = db.scalar(
        select(func.max(DailyPrice.trade_date)).where(DailyPrice.market_cap.is_not(None))
    )
    if market_cap_date is None:
        return {}
    capped_limit = max(1, min(int(universe_limit), MARKET_SIGNAL_UNIVERSE_LIMIT))
    codes = list(
        db.scalars(
            select(StockMaster.code)
            .join(
                DailyPrice,
                (DailyPrice.code == StockMaster.code)
                & (DailyPrice.trade_date == market_cap_date),
            )
            .where(
                StockMaster.is_active.is_(True),
                StockMaster.market.in_(("KOSPI", "KOSDAQ")),
                DailyPrice.market_cap.is_not(None),
                DailyPrice.market_cap > 0,
            )
            .order_by(DailyPrice.market_cap.desc(), StockMaster.code)
            .limit(capped_limit)
        )
    )
    quotes: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(codes) or 1)) as executor:
        futures = {executor.submit(_fetch_uncached_current_quote, code): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                quote, _source = future.result()
            except Exception:
                continue
            if quote:
                quotes[code] = quote
    return quotes


def _watchlist_quant_signal_live_quotes(
    codes: list[str],
    now: Optional[datetime] = None,
) -> dict[str, dict[str, Any]]:
    """Fetch one fresh mark per signal; the route cache limits closed-session work."""
    normalized_codes = list(dict.fromkeys(str(code).strip() for code in codes if str(code).strip()))[:100]
    quotes: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(normalized_codes) or 1)) as executor:
        futures = {executor.submit(_fetch_uncached_current_quote, code): code for code in normalized_codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                quote, _source = future.result()
            except Exception:
                continue
            if quote:
                quotes[code] = quote
    return quotes


def _quant_signal_quote_refresh_active(now: Optional[datetime] = None) -> bool:
    """Keep list marks live through the post-close signal publication window."""
    current = now or datetime.now(KST)
    if is_korea_regular_market_session(current):
        return True
    return (
        time(15, 30) < current.time() <= QUANT_SIGNAL_QUOTE_REFRESH_END
        and is_korea_market_session_date(current.date(), current)
    )


def _market_quant_signal_snapshot_freshness(
    payload: Optional[dict[str, Any]],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    current = now or datetime.now(KST)
    max_age_seconds = (
        MARKET_QUANT_SIGNAL_ACTIVE_MAX_AGE_SECONDS
        if _quant_signal_quote_refresh_active(current)
        else MARKET_QUANT_SIGNAL_CLOSED_MAX_AGE_SECONDS
    )
    raw_generated_at = str((payload or {}).get("snapshot_generated_at") or "").strip()
    generated_at: Optional[datetime] = None
    if raw_generated_at:
        try:
            generated_at = datetime.fromisoformat(raw_generated_at.replace("Z", "+00:00"))
        except ValueError:
            generated_at = None
    if generated_at is not None:
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        generated_at = generated_at.astimezone(KST)
    age_seconds = (
        max(0, int((current - generated_at).total_seconds()))
        if generated_at is not None
        else None
    )
    stale = age_seconds is None or age_seconds > max_age_seconds
    return {
        "snapshot_state": "stale" if stale else "fresh",
        "snapshot_age_seconds": age_seconds,
        "snapshot_max_age_seconds": max_age_seconds,
        "snapshot_generated_at": generated_at.isoformat() if generated_at else None,
    }


def _is_preliminary_market_quant_signal(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    current = item.get("current") if isinstance(item.get("current"), dict) else {}
    action = str(current.get("action") or item.get("action") or "")
    return bool(
        item.get("is_preliminary") is True
        or item.get("status") == "preliminary"
        or action
        in {
            "entry_watch",
            "entry_pending",
            "partial_exit_pending",
            "full_exit_pending",
        }
    )


def _suppress_stale_preliminary_market_signals(payload: dict[str, Any]) -> dict[str, Any]:
    """Never expose an actionable preliminary state from an expired snapshot."""

    result = deepcopy(payload)
    items = [item for item in result.get("items") or [] if isinstance(item, dict)]
    stale_preliminary_count = sum(
        1 for item in items if _is_preliminary_market_quant_signal(item)
    )
    result["items"] = [
        item for item in items if not _is_preliminary_market_quant_signal(item)
    ]
    result["stale_preliminary_count"] = max(
        int(result.get("stale_preliminary_count") or 0),
        stale_preliminary_count,
    )
    result["preliminary_count"] = 0
    result["confirmed_count"] = len(result["items"])
    return result


async def _run_market_quant_signal_refresh_loop() -> None:
    last_premarket_refresh_date: Optional[date] = None
    while True:
        now = datetime.now(KST)
        premarket_refresh = (
            now.weekday() < 5
            and time(6, 0) <= now.time() <= time(9, 0)
            and is_korea_market_session_date(now.date(), now)
            and last_premarket_refresh_date != now.date()
        )
        if _quant_signal_quote_refresh_active(now) or premarket_refresh:
            refreshed = await asyncio.to_thread(_refresh_market_quant_signal_snapshot)
            if premarket_refresh and refreshed is not None:
                last_premarket_refresh_date = now.date()
        await asyncio.sleep(300)


async def _run_stock_logo_sync_loop() -> None:
    await asyncio.sleep(max(0, settings.stock_logo_initial_delay_seconds))
    while True:
        try:
            def sync_once() -> dict[str, int]:
                with SessionLocal() as db:
                    return sync_stock_logos(
                        db,
                        markets=settings.stock_universe_markets,
                        timeout_seconds=settings.stock_logo_timeout_seconds,
                        max_workers=settings.stock_logo_max_workers,
                        missing_retry_days=settings.stock_logo_missing_retry_days,
                    )

            result = await asyncio.to_thread(sync_once)
            logger.info("Stock logo sync completed: %s", result)
        except Exception:  # pragma: no cover - operational safeguard
            logger.exception("Stock logo sync failed")
        await asyncio.sleep(max(300, settings.stock_logo_poll_seconds))


def _build_etf_holdings_universe_snapshot(
    db: Session,
    snapshot_key: str,
) -> SnapshotBuild:
    previous = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION,
    )
    payload = build_naver_etf_holdings_snapshot(
        previous.payload if previous is not None else None,
        max_workers=settings.etf_holdings_snapshot_max_workers,
    )
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None)
    current_date = datetime.now(KST).date()
    for item in payload.get("items", {}).values():
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        if not re.fullmatch(r"[0-9A-Z]{6}", code) or not name:
            continue
        stock = db.get(StockMaster, code)
        if stock is None:
            stock = StockMaster(code=code, name=name, market="KOSPI")
        stock.name = name
        stock.market = "KOSPI"
        stock.is_active = True
        stock.last_seen_date = current_date
        db.add(stock)
    logger.info(
        "ETF holdings refresh completed total=%s fresh=%s changed=%s added=%s removed=%s failed=%s",
        payload.get("total_count"),
        payload.get("fresh_count"),
        payload.get("changed_count"),
        len(payload.get("added_codes") or []),
        len(payload.get("removed_codes") or []),
        len(payload.get("failed_codes") or []),
    )
    return SnapshotBuild(
        payload=payload,
        fresh_for_seconds=13 * 60 * 60,
        schema_version=ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION,
        captured_at=captured_at,
        validator=validate_etf_holdings_snapshot,
    )


def _complete_snapshot_handlers() -> tuple[SnapshotHandler, ...]:
    return (
        SnapshotHandler(
            key_prefix=STOCK_DASHBOARD_SNAPSHOT_PREFIX,
            builder=_build_stock_dashboard_snapshot,
            fresh_for_seconds=STOCK_DASHBOARD_TTL_SECONDS,
            validator=_validate_stock_dashboard_snapshot,
        ),
        SnapshotHandler(
            key_prefix=STOCK_HOME_CONTEXT_SNAPSHOT_PREFIX,
            builder=_build_stock_home_context_snapshot,
            fresh_for_seconds=STOCK_HOME_CONTEXT_TTL_SECONDS,
            validator=_validate_stock_home_context_snapshot,
        ),
        SnapshotHandler(
            key_prefix=MARKET_INDICES_SNAPSHOT_PREFIX,
            builder=_build_market_indices_snapshot,
            fresh_for_seconds=30,
            validator=_validate_market_indices_snapshot,
            lane="indices",
        ),
        SnapshotHandler(
            key_prefix=GLOBAL_MARKET_ASSETS_SNAPSHOT_PREFIX,
            builder=_build_global_market_assets_snapshot,
            fresh_for_seconds=GLOBAL_MARKET_ASSETS_TTL_SECONDS,
            validator=_validate_global_market_assets_snapshot,
            lane="market",
        ),
        SnapshotHandler(
            key_prefix=US_SECTOR_MOVES_SNAPSHOT_KEY,
            builder=_build_us_sector_moves_snapshot,
            fresh_for_seconds=300,
            validator=_validate_us_sector_moves_snapshot,
            lane="market",
        ),
        SnapshotHandler(
            key_prefix=SURGE_COMPLETE_SNAPSHOT_KEY,
            builder=_build_surge_complete_snapshot,
            fresh_for_seconds=MARKET_RANKING_TTL_SECONDS,
            validator=_validate_surge_complete_snapshot,
            lane="market",
        ),
        SnapshotHandler(
            key_prefix=ETF_HOLDINGS_SNAPSHOT_KEY,
            builder=_build_etf_holdings_universe_snapshot,
            fresh_for_seconds=13 * 60 * 60,
            schema_version=ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION,
            validator=validate_etf_holdings_snapshot,
            lane="etf",
        ),
    )


def _get_complete_snapshot_runtime() -> SnapshotRuntime:
    global complete_snapshot_runtime
    if complete_snapshot_runtime is None:
        complete_snapshot_runtime = SnapshotRuntime(
            SessionLocal,
            _complete_snapshot_handlers(),
            lease_seconds=1800,
            poll_seconds=0.5,
            failure_retry_seconds=30,
        )
    return complete_snapshot_runtime


def _periodic_complete_snapshot_keys() -> tuple[str, ...]:
    return (
        f"{MARKET_INDICES_SNAPSHOT_PREFIX}30",
        f"{GLOBAL_MARKET_ASSETS_SNAPSHOT_PREFIX}30",
        US_SECTOR_MOVES_SNAPSHOT_KEY,
        SURGE_COMPLETE_SNAPSHOT_KEY,
    )


def _latest_etf_holdings_refresh_slot(now: Optional[datetime] = None) -> datetime:
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    else:
        current = current.astimezone(KST)
    slot_hour = 12 if current.hour >= 12 else 0
    return current.replace(hour=slot_hour, minute=0, second=0, microsecond=0)


def _etf_holdings_snapshot_due(
    complete: Any,
    now: Optional[datetime] = None,
) -> bool:
    if complete is None or getattr(complete, "captured_at", None) is None:
        return True
    captured_at = complete.captured_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    captured_kst = captured_at.astimezone(KST)
    return captured_kst < _latest_etf_holdings_refresh_slot(now)


def _queue_due_periodic_complete_snapshots() -> None:
    with SessionLocal() as db:
        for snapshot_key in _periodic_complete_snapshot_keys():
            complete = get_complete_snapshot(
                db,
                snapshot_key,
                schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
            )
            if complete is None or not complete.is_fresh:
                request_complete_snapshot_refresh(
                    db,
                    snapshot_key,
                    schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
                )
        if settings.etf_holdings_snapshot_enabled:
            etf_complete = get_complete_snapshot(
                db,
                ETF_HOLDINGS_SNAPSHOT_KEY,
                schema_version=ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION,
            )
            if _etf_holdings_snapshot_due(etf_complete):
                request_complete_snapshot_refresh(
                    db,
                    ETF_HOLDINGS_SNAPSHOT_KEY,
                    schema_version=ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION,
                )


async def _run_complete_snapshot_schedule_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(_queue_due_periodic_complete_snapshots)
            _get_complete_snapshot_runtime().wake()
        except Exception:  # pragma: no cover - operational safeguard
            logger.exception("Complete snapshot scheduling failed")
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.runs_collectors():
        recover_interrupted_ingestions()
    bootstrap_task: asyncio.Task | None = None
    intraday_warmup_task: asyncio.Task | None = None
    market_quant_signal_task: asyncio.Task | None = None
    entry_filter_shadow_task: asyncio.Task | None = None
    stock_logo_task: asyncio.Task | None = None
    complete_snapshot_schedule_task: asyncio.Task | None = None
    collectors_started = False
    async with AsyncExitStack() as stack:
        if settings.runs_web_services() and mcp_server is not None:
            await stack.enter_async_context(mcp_server.session_manager.run())
        if settings.runs_collectors():
            await briefing_runtime.start()
            await web_push_runtime.start()
            collectors_started = True
            await _get_complete_snapshot_runtime().start()
            complete_snapshot_schedule_task = asyncio.create_task(
                _run_complete_snapshot_schedule_loop()
            )
            intraday_warmup_task = asyncio.create_task(_run_intraday_warmup_loop())
            market_quant_signal_task = asyncio.create_task(_run_market_quant_signal_refresh_loop())
            entry_filter_shadow_task = asyncio.create_task(
                _run_entry_filter_shadow_backtest_loop()
            )
            if settings.stock_logo_enabled:
                stock_logo_task = asyncio.create_task(_run_stock_logo_sync_loop())
            if settings.bootstrap_on_start:
                bootstrap_task = asyncio.create_task(_run_bootstrap_task())
        try:
            yield
        finally:
            if bootstrap_task is not None:
                bootstrap_task.cancel()
                with suppress(asyncio.CancelledError):
                    await bootstrap_task
            if intraday_warmup_task is not None:
                intraday_warmup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await intraday_warmup_task
            if market_quant_signal_task is not None:
                market_quant_signal_task.cancel()
                with suppress(asyncio.CancelledError):
                    await market_quant_signal_task
            if entry_filter_shadow_task is not None:
                entry_filter_shadow_task.cancel()
                with suppress(asyncio.CancelledError):
                    await entry_filter_shadow_task
            if stock_logo_task is not None:
                stock_logo_task.cancel()
                with suppress(asyncio.CancelledError):
                    await stock_logo_task
            if complete_snapshot_schedule_task is not None:
                complete_snapshot_schedule_task.cancel()
                with suppress(asyncio.CancelledError):
                    await complete_snapshot_schedule_task
            if collectors_started:
                await _get_complete_snapshot_runtime().stop()
                await web_push_runtime.stop()
                await briefing_runtime.stop()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item for item in settings.mcp_allowed_origins.split(",") if item.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id", "mcp-session-id", "MCP-Protocol-Version"],
)


def _dashboard_asset_cache_headers(request: Request) -> dict[str, str]:
    if request.query_params.get("v") == DASHBOARD_CLIENT_VERSION:
        return {"Cache-Control": DASHBOARD_IMMUTABLE_CACHE_CONTROL}
    return {
        "Cache-Control": DASHBOARD_MUTABLE_ASSET_CACHE_CONTROL,
        "Pragma": "no-cache",
    }


@app.api_route("/assets/dashboard/styles.css", methods=["GET", "HEAD"])
def stock_dashboard_styles(request: Request):
    if not STOCK_DASHBOARD_STYLES.exists():
        raise HTTPException(status_code=404, detail="Dashboard stylesheet not found")
    return FileResponse(
        STOCK_DASHBOARD_STYLES,
        media_type="text/css",
        headers=_dashboard_asset_cache_headers(request),
    )


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
if mcp_server is not None:
    app.mount("/mcp", mcp_server.streamable_http_app())


PAGE_SUMMARY_PATH = "/ai/page-summary"
PAGE_SUMMARY_MAX_BODY_BYTES = 64 * 1024
PAGE_SUMMARY_RATE_WINDOW_SECONDS = 60.0
PAGE_SUMMARY_RATE_PER_CLIENT = 15
PAGE_SUMMARY_RATE_GLOBAL = 120
_page_summary_rate_lock = RLock()
_page_summary_client_requests: dict[str, list[float]] = {}
_page_summary_global_requests: list[float] = []


def _allow_page_summary_request(request: Request) -> bool:
    now = time_module.monotonic()
    cutoff = now - PAGE_SUMMARY_RATE_WINDOW_SECONDS
    client_key = request.client.host if request.client else "unknown"
    with _page_summary_rate_lock:
        _page_summary_global_requests[:] = [
            timestamp
            for timestamp in _page_summary_global_requests
            if timestamp > cutoff
        ]
        for key, timestamps in list(_page_summary_client_requests.items()):
            current = [timestamp for timestamp in timestamps if timestamp > cutoff]
            if current:
                _page_summary_client_requests[key] = current
            else:
                _page_summary_client_requests.pop(key, None)
        client_requests = _page_summary_client_requests.setdefault(client_key, [])
        if (
            len(client_requests) >= PAGE_SUMMARY_RATE_PER_CLIENT
            or len(_page_summary_global_requests) >= PAGE_SUMMARY_RATE_GLOBAL
        ):
            return False
        client_requests.append(now)
        _page_summary_global_requests.append(now)
        return True


@app.post(PAGE_SUMMARY_PATH, response_model=PageSummaryResponse)
async def page_summary(request: Request, response: Response):
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise HTTPException(status_code=403, detail="교차 사이트 요청은 허용하지 않습니다.")
    if not _allow_page_summary_request(request):
        raise HTTPException(
            status_code=429,
            detail="요약 요청이 잠시 많습니다. 기존 데이터 문구를 유지합니다.",
            headers={"Retry-After": "60"},
        )
    raw_body = await request.body()
    if len(raw_body) > PAGE_SUMMARY_MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="요약 요청 크기가 제한을 초과했습니다.")
    try:
        payload = json.loads(raw_body or b"{}")
        if not isinstance(payload, dict):
            raise TypeError("request payload must be an object")
        result = await summarize_staging_page(payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="요약 요청 형식을 확인해 주세요.")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return result


@app.get("/")
def root_shell():
    return RedirectResponse(url="/dashboard?view=home", status_code=307)


def _end_of_day(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.combine(value, time(23, 59, 59))


def _host_only(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = raw.split(",", 1)[0].strip()
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.netloc or parsed.path
    if raw.startswith("[") and "]" in raw:
        return raw[1 : raw.index("]")]
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw


def _normalize_push_conditions(values: object) -> list[str]:
    allowed = set(DEFAULT_PUSH_CONDITIONS)
    if not isinstance(values, list):
        return list(DEFAULT_PUSH_CONDITIONS)
    normalized: list[str] = []
    for item in values:
        condition = str(item or "").strip()
        if condition in allowed and condition not in normalized:
            normalized.append(condition)
    legacy_defaults = {"ai_signal", "price_move", "disclosure_report", "major_event"}
    if legacy_defaults.issubset({str(item or "").strip() for item in values}):
        for condition in ("market_ai_signal", "market_session"):
            if condition not in normalized:
                normalized.append(condition)
    selected = normalized or list(DEFAULT_PUSH_CONDITIONS)
    return list(dict.fromkeys((*REQUIRED_PUSH_CONDITIONS, *selected)))


def _subscription_conditions(subscription: Optional[PushSubscription]) -> list[str]:
    if subscription is None:
        return list(DEFAULT_PUSH_CONDITIONS)
    raw = subscription.notification_preferences
    if not raw:
        return list(DEFAULT_PUSH_CONDITIONS)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return list(DEFAULT_PUSH_CONDITIONS)
    return _normalize_push_conditions(parsed)


def _request_is_local_console(request: Request) -> bool:
    host = _host_only(request.headers.get("x-forwarded-host") or request.headers.get("host"))
    if host in LOCAL_ONLY_HOSTS:
        return True
    origin_host = _host_only(request.headers.get("origin"))
    if origin_host in LOCAL_ONLY_HOSTS:
        return True
    referer_host = _host_only(request.headers.get("referer"))
    return referer_host in LOCAL_ONLY_HOSTS


def _request_scheme(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    if forwarded:
        return forwarded
    return request.url.scheme


def _request_trace_id(request: Request) -> str:
    existing = str(getattr(request.state, "request_id", "") or "").strip()
    if existing:
        return existing
    forwarded = str(
        request.headers.get("x-request-id")
        or request.headers.get("x-railway-request-id")
        or ""
    ).strip()
    request_id = re.sub(r"[^0-9A-Za-z._:-]", "", forwarded)[:128] or secrets.token_hex(8)
    request.state.request_id = request_id
    return request_id


def _client_identifier(request: Request) -> str:
    forwarded = str(
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-real-ip")
        or request.headers.get("x-forwarded-for")
        or ""
    ).strip()
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _enforce_rate_limit(request: Request, scope: str, limit: int, window_seconds: int) -> None:
    now = time_module.monotonic()
    key = (scope, _client_identifier(request))
    with rate_limit_lock:
        hits = [stamp for stamp in rate_limit_windows.get(key, []) if now - stamp < window_seconds]
        if len(hits) >= limit:
            retry_after = max(1, int(window_seconds - (now - hits[0]) + 0.999))
            raise HTTPException(
                status_code=429,
                detail="요청이 많습니다. 잠시 후 다시 시도해주세요.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-Request-ID": _request_trace_id(request),
                },
            )
        hits.append(now)
        rate_limit_windows[key] = hits


def _write_session_key(session_id: str) -> tuple[str, str]:
    return ("write_session", session_id)


def _load_write_session(session_id: str) -> Optional[dict[str, object]]:
    if not session_id:
        return None
    payload = write_session_cache.get(_write_session_key(session_id))
    return payload if isinstance(payload, dict) else None


def _store_write_session(session_id: str, token: str, share_ids: list[str]) -> None:
    write_session_cache.set(
        _write_session_key(session_id),
        {"token": token, "share_ids": sorted({item for item in share_ids if item})},
        WRITE_SESSION_TTL_SECONDS,
    )


def _invite_access_fingerprint() -> str:
    configured_code = str(settings.dashboard_invite_code or "").strip().upper()
    return hashlib.sha256(f"secret-note-invite-v1:{configured_code}".encode("utf-8")).hexdigest()


def _invite_access_required(request: Request) -> bool:
    request_host = _host_only(request.headers.get("x-forwarded-host") or request.headers.get("host"))
    invite_hosts = {
        host
        for item in str(settings.dashboard_invite_hosts or "").split(",")
        if (host := _host_only(item))
    }
    return request_host in invite_hosts


def _has_invite_access(request: Request) -> bool:
    submitted = str(request.cookies.get(INVITE_ACCESS_COOKIE) or "").strip()
    return bool(submitted) and secrets.compare_digest(submitted, _invite_access_fingerprint())


def _set_invite_access_cookie(request: Request, response: Response) -> None:
    response.set_cookie(
        INVITE_ACCESS_COOKIE,
        _invite_access_fingerprint(),
        max_age=INVITE_ACCESS_TTL_SECONDS,
        httponly=True,
        secure=_request_scheme(request) == "https",
        samesite="lax",
        path="/",
    )


def _normalize_write_scope(share_id: str, market: Optional[str] = None) -> str:
    normalized_id = _normalize_watchlist_id(share_id)
    if str(market or "").strip().lower() == "us":
        return f"us.{normalized_id}"
    return normalized_id


def _desktop_session_secret() -> bytes:
    configured = str(settings.dashboard_invite_code or "").strip()
    return f"secret-note-desktop-v1:{configured or settings.app_name}".encode("utf-8")


def _desktop_session_value(share_id: str, issued_at: Optional[int] = None) -> str:
    encoded_id = base64.urlsafe_b64encode(share_id.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"{encoded_id}.{issued_at or int(time_module.time())}"
    signature = hmac.new(_desktop_session_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _desktop_share_id_from_request(request: Request) -> str:
    try:
        encoded_id, timestamp, signature = str(request.cookies.get(DESKTOP_SESSION_COOKIE) or "").split(".", 2)
        payload = f"{encoded_id}.{timestamp}"
        expected = hmac.new(_desktop_session_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        age = int(time_module.time()) - int(timestamp)
        if age < -300 or age > DESKTOP_SESSION_TTL_SECONDS:
            raise ValueError("expired session")
        padding = "=" * (-len(encoded_id) % 4)
        decoded = base64.urlsafe_b64decode(encoded_id + padding).decode("utf-8")
        return _normalize_watchlist_id(decoded)
    except (ValueError, UnicodeError, TypeError):
        raise HTTPException(status_code=401, detail="PC 세션이 만료되었습니다.") from None


def _require_write_access(request: Request, share_id: str) -> None:
    session_id = str(request.cookies.get(WRITE_SESSION_COOKIE) or "").strip()
    write_token = str(request.headers.get("x-write-token") or "").strip()
    session = _load_write_session(session_id)
    if not session or not write_token or write_token != str(session.get("token") or ""):
        raise HTTPException(status_code=403, detail="쓰기 세션이 필요합니다.")
    issued_ids = [str(item).strip() for item in (session.get("share_ids") or []) if str(item).strip()]
    if share_id not in issued_ids:
        raise HTTPException(status_code=403, detail="이 관심 ID에 대한 쓰기 권한이 없습니다.")
    _store_write_session(session_id, write_token, issued_ids)


LEGACY_RAILWAY_PUBLIC_INVITE_CODE = "KORNOTE2026"


def _legacy_railway_destination(request: Request, canonical_base: str) -> str:
    path = request.url.path or "/"
    if path != "/":
        destination = f"{canonical_base}{path}"
        if request.url.query:
            destination = f"{destination}?{request.url.query}"
        return destination

    query_items = list(request.query_params.multi_items())
    if not any(key == "view" for key, _value in query_items):
        query_items.insert(0, ("view", "home"))
    query = urlencode(query_items)
    return f"{canonical_base}/dashboard{f'?{query}' if query else ''}"


def _legacy_railway_browser_destination(request: Request, canonical_base: str) -> str:
    """Map a legacy browser visit to an HTML route on the canonical service.

    API clients still use ``_legacy_railway_destination`` so their path and query
    remain intact. A person can, however, arrive at the Railway host on an API
    URL (for example from an old stock-signal link). Carrying that URL to the
    canonical host would render raw JSON instead of the dashboard.
    """
    path = request.url.path or "/"
    if path == "/":
        return _legacy_railway_destination(request, canonical_base)

    stock_match = re.fullmatch(r"/stocks/(\d{6})(?:/.*)?", path)
    if stock_match:
        return f"{canonical_base}/dashboard/{stock_match.group(1)}"

    if path == "/market/quant-signals" or re.fullmatch(
        r"/watchlists/[^/]+/quant-signals", path
    ):
        return f"{canonical_base}/dashboard?view=ai-signals"

    is_dashboard_ui = (
        path == "/dashboard"
        or path.startswith("/dashboard/")
        or path == "/dashboard-refresh"
    )
    is_other_ui = (
        path in {
            "/desktop",
            "/insight",
            "/insight/desktop",
            "/insight/mobile",
            "/portfolio",
            "/concepts",
            "/nasdaq",
        }
        or path.startswith("/nasdaq/")
    )
    if is_dashboard_ui or is_other_ui:
        return _legacy_railway_destination(request, canonical_base)

    return f"{canonical_base}/dashboard?view=home"


def _legacy_railway_notice_html(destination: str) -> str:
    safe_destination = html.escape(destination, quote=True)
    destination_json = json.dumps(destination, ensure_ascii=False).replace("</", "<\\/")
    invite_code = LEGACY_RAILWAY_PUBLIC_INVITE_CODE
    invite_code_json = json.dumps(invite_code)
    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="theme-color" content="#111111" />
    <meta name="robots" content="noindex, nofollow" />
    <title>비밀노트 새 주소 안내</title>
    <style>
      :root {{
        color-scheme: light;
        font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        --migration-bg: #111111;
        --migration-surface: #ffffff;
        --migration-text: #17181b;
        --migration-muted: #686d76;
        --migration-line: #e6e8eb;
        --migration-soft: #f4f5f6;
        --migration-success: #16794f;
      }}
      * {{ box-sizing: border-box; }}
      html, body {{ min-height: 100%; margin: 0; }}
      body {{
        min-height: 100dvh;
        overflow: hidden;
        color: var(--migration-text);
        background:
          radial-gradient(circle at 50% 16%, rgba(255, 255, 255, 0.12), transparent 36%),
          var(--migration-bg);
      }}
      button, a {{ font: inherit; }}
      .migration-stage {{
        min-height: 100dvh;
        display: grid;
        align-content: start;
        justify-items: center;
        padding: max(34px, env(safe-area-inset-top, 0px)) 24px 240px;
      }}
      .migration-brand {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
        color: rgba(255, 255, 255, 0.82);
        font-size: 14px;
        font-weight: 800;
        letter-spacing: -0.01em;
      }}
      .migration-brand-mark {{
        width: 34px;
        height: 34px;
        display: grid;
        place-items: center;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 11px;
        color: #111111;
        background: #ffffff;
        font-size: 17px;
        font-weight: 950;
      }}
      .migration-stage-copy {{
        width: min(520px, 100%);
        margin-top: clamp(54px, 12vh, 110px);
        color: #ffffff;
        text-align: center;
      }}
      .migration-stage-copy p {{
        margin: 0;
        color: rgba(255, 255, 255, 0.5);
        font-size: 13px;
        font-weight: 750;
        letter-spacing: 0.03em;
      }}
      .migration-stage-copy strong {{
        display: block;
        margin-top: 10px;
        font-size: clamp(24px, 7vw, 36px);
        line-height: 1.2;
        letter-spacing: -0.04em;
      }}
      .migration-backdrop {{
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.18);
        backdrop-filter: blur(2px);
        -webkit-backdrop-filter: blur(2px);
      }}
      .migration-sheet {{
        position: fixed;
        z-index: 1;
        right: 0;
        bottom: 0;
        left: 0;
        width: min(100%, 640px);
        max-height: calc(100dvh - max(28px, env(safe-area-inset-top, 0px)));
        margin-inline: auto;
        overflow: auto;
        overscroll-behavior: contain;
        border-radius: 28px 28px 0 0;
        padding: 10px 22px calc(22px + env(safe-area-inset-bottom, 0px));
        background: var(--migration-surface);
        box-shadow: 0 -24px 80px rgba(0, 0, 0, 0.34);
        animation: migration-sheet-in 240ms cubic-bezier(0.22, 1, 0.36, 1) both;
      }}
      .migration-handle {{
        width: 42px;
        height: 5px;
        margin: 0 auto 20px;
        border-radius: 999px;
        background: #d7dade;
      }}
      .migration-eyebrow {{
        margin: 0 0 8px;
        color: var(--migration-success);
        font-size: 12px;
        font-weight: 900;
        letter-spacing: 0.04em;
      }}
      .migration-sheet h1 {{
        margin: 0;
        font-size: clamp(25px, 7vw, 32px);
        line-height: 1.22;
        letter-spacing: -0.045em;
        word-break: keep-all;
      }}
      .migration-description {{
        margin: 12px 0 0;
        color: var(--migration-muted);
        font-size: 15px;
        font-weight: 650;
        line-height: 1.6;
        word-break: keep-all;
      }}
      .migration-domain {{
        display: flex;
        align-items: center;
        gap: 10px;
        min-height: 52px;
        margin-top: 20px;
        padding: 0 16px;
        border: 1px solid var(--migration-line);
        border-radius: 14px;
        background: var(--migration-soft);
        font-size: 14px;
        font-weight: 850;
        overflow-wrap: anywhere;
      }}
      .migration-domain::before {{
        width: 9px;
        height: 9px;
        flex: 0 0 auto;
        border-radius: 999px;
        background: var(--migration-success);
        box-shadow: 0 0 0 4px rgba(22, 121, 79, 0.12);
        content: "";
      }}
      .migration-code-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 12px;
        margin-top: 12px;
        padding: 14px 14px 14px 16px;
        border: 1px solid var(--migration-line);
        border-radius: 14px;
      }}
      .migration-code-copy {{ display: grid; gap: 4px; min-width: 0; }}
      .migration-code-copy span {{
        color: var(--migration-muted);
        font-size: 12px;
        font-weight: 750;
      }}
      .migration-code-copy code {{
        color: var(--migration-text);
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: clamp(17px, 5vw, 20px);
        font-weight: 900;
        letter-spacing: 0.025em;
      }}
      .migration-copy-button {{
        min-width: 64px;
        min-height: 44px;
        border: 1px solid #d7dade;
        border-radius: 11px;
        padding: 0 14px;
        color: var(--migration-text);
        background: #ffffff;
        cursor: pointer;
        font-size: 13px;
        font-weight: 850;
      }}
      .migration-actions {{ display: grid; gap: 10px; margin-top: 18px; }}
      .migration-primary {{
        min-height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 15px;
        padding: 0 20px;
        color: #ffffff;
        background: #111111;
        cursor: pointer;
        font-size: 16px;
        font-weight: 900;
        text-decoration: none;
      }}
      .migration-pause {{
        min-height: 44px;
        border: 0;
        padding: 0 12px;
        color: var(--migration-muted);
        background: transparent;
        cursor: pointer;
        font-size: 13px;
        font-weight: 750;
      }}
      .migration-status {{
        min-height: 20px;
        margin: 12px 0 0;
        color: var(--migration-muted);
        font-size: 12px;
        font-weight: 650;
        line-height: 1.5;
        text-align: center;
      }}
      :is(.migration-copy-button, .migration-primary, .migration-pause):focus-visible {{
        outline: 3px solid rgba(17, 17, 17, 0.22);
        outline-offset: 3px;
      }}
      .migration-copy-button:hover {{ background: var(--migration-soft); }}
      .migration-primary:hover {{ background: #292929; }}
      @keyframes migration-sheet-in {{
        from {{ opacity: 0.5; transform: translateY(42px); }}
        to {{ opacity: 1; transform: translateY(0); }}
      }}
      @media (min-width: 720px) {{
        .migration-stage {{ padding-bottom: 300px; }}
        .migration-sheet {{
          bottom: 24px;
          border-radius: 28px;
          padding: 12px 28px 26px;
        }}
      }}
      @media (prefers-reduced-motion: reduce) {{
        .migration-sheet {{ animation: none; }}
      }}
    </style>
  </head>
  <body>
    <main class="migration-stage" aria-hidden="true">
      <div class="migration-brand"><span class="migration-brand-mark">B</span><span>비밀노트 · 국내증시</span></div>
      <div class="migration-stage-copy"><p>OFFICIAL DOMAIN</p><strong>secretnote.cloud</strong></div>
    </main>
    <div class="migration-backdrop" aria-hidden="true"></div>
    <section
      class="migration-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="migration-title"
      aria-describedby="migration-description migration-status"
    >
      <div class="migration-handle" aria-hidden="true"></div>
      <p class="migration-eyebrow">공식 주소 안내</p>
      <h1 id="migration-title">secretnote.cloud로<br />접속해 주세요!</h1>
      <p class="migration-description" id="migration-description">기존 Railway 주소는 종료 예정입니다. 앞으로 아래 공식 주소를 이용해 주세요.</p>
      <div class="migration-domain">https://secretnote.cloud</div>
      <div class="migration-code-row">
        <div class="migration-code-copy">
          <span>첫 접속 코드</span>
          <code id="migration-code">{invite_code}</code>
        </div>
        <button class="migration-copy-button" id="migration-copy" type="button">복사</button>
      </div>
      <div class="migration-actions">
        <a class="migration-primary" id="migration-move" href="{safe_destination}">코드 복사하고 새 주소로 이동</a>
        <button class="migration-pause" id="migration-pause" type="button">자동 이동 멈추기</button>
      </div>
      <p class="migration-status" id="migration-status" role="status" aria-live="polite">15초 후 새 공식 주소로 자동 이동합니다.</p>
    </section>
    <script>
      (() => {{
        const destination = {destination_json};
        const inviteCode = {invite_code_json};
        const copyButton = document.getElementById("migration-copy");
        const moveButton = document.getElementById("migration-move");
        const pauseButton = document.getElementById("migration-pause");
        const status = document.getElementById("migration-status");
        let seconds = 15;
        let timer = null;
        let paused = false;

        const copyInviteCode = async () => {{
          try {{
            await navigator.clipboard.writeText(inviteCode);
            return true;
          }} catch (_error) {{
            const field = document.createElement("textarea");
            field.value = inviteCode;
            field.setAttribute("readonly", "");
            field.style.position = "fixed";
            field.style.opacity = "0";
            document.body.append(field);
            field.select();
            const copied = document.execCommand("copy");
            field.remove();
            return copied;
          }}
        }};

        const updateCountdown = () => {{
          if (paused || document.hidden) return;
          seconds -= 1;
          if (seconds <= 0) {{
            window.location.replace(destination);
            return;
          }}
          status.textContent = `${{seconds}}초 후 새 공식 주소로 자동 이동합니다.`;
        }};

        copyButton.addEventListener("click", async () => {{
          const copied = await copyInviteCode();
          seconds = Math.max(seconds, 6);
          status.textContent = copied
            ? `접속 코드를 복사했습니다. ${{seconds}}초 후 이동합니다.`
            : `접속 코드 ${{inviteCode}}를 확인해 주세요. ${{seconds}}초 후 이동합니다.`;
        }});

        moveButton.addEventListener("click", async (event) => {{
          event.preventDefault();
          window.clearInterval(timer);
          status.textContent = "접속 코드를 복사한 뒤 새 주소로 이동합니다.";
          await copyInviteCode();
          window.location.replace(destination);
        }});

        pauseButton.addEventListener("click", () => {{
          paused = true;
          window.clearInterval(timer);
          pauseButton.hidden = true;
          status.textContent = "자동 이동을 멈췄습니다. 위 버튼을 눌러 이동해 주세요.";
          moveButton.focus();
        }});

        window.addEventListener("keydown", (event) => {{
          if (event.key === "Tab") {{
            const focusable = [copyButton, moveButton, pauseButton].filter((item) => !item.hidden);
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {{
              event.preventDefault();
              last.focus();
            }} else if (!event.shiftKey && document.activeElement === last) {{
              event.preventDefault();
              first.focus();
            }}
            return;
          }}
          if (event.key !== "Escape" || paused) return;
          event.preventDefault();
          pauseButton.click();
        }});

        timer = window.setInterval(updateCountdown, 1000);
        window.requestAnimationFrame(() => moveButton.focus());
      }})();
    </script>
  </body>
</html>"""


@app.middleware("http")
async def _protect_internal_routes(request: Request, call_next):
    request_id = _request_trace_id(request)
    request_host = str(request.url.hostname or "").strip().lower()
    redirect_hosts = {
        item.strip().lower()
        for item in settings.canonical_redirect_hosts.split(",")
        if item.strip()
    }
    canonical_base = settings.canonical_public_base_url.strip().rstrip("/")
    if (
        canonical_base
        and request_host in redirect_hosts
        and request.url.path not in {"/health", "/healthz", "/readyz"}
    ):
        accepts_html = "text/html" in str(request.headers.get("accept") or "").lower()
        if request.method in {"GET", "HEAD"} and accepts_html:
            destination = _legacy_railway_browser_destination(request, canonical_base)
            return HTMLResponse(
                _legacy_railway_notice_html(destination),
                status_code=200,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Content-Security-Policy": (
                        "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
                    ),
                    "Link": f'<{canonical_base}>; rel="canonical"',
                    "Referrer-Policy": "no-referrer",
                    "X-Request-ID": request_id,
                    "X-Robots-Tag": "noindex, nofollow",
                },
            )
        destination = _legacy_railway_destination(request, canonical_base)
        return RedirectResponse(
            destination,
            status_code=308,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "X-Request-ID": request_id,
            },
        )
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request error method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )
        raise
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    if _request_scheme(request) == "https":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    if "text/html" in str(response.headers.get("content-type") or "").lower():
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; base-uri 'self'; object-src 'none'; "
                "frame-ancestors 'none'; form-action 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "font-src 'self' data: https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https: wss: ws:; "
                "worker-src 'self'; manifest-src 'self'"
            ),
        )
    return response


def _normalize_presence_page(value: object) -> str:
    page = str(value or "").strip()
    if not page.startswith("/"):
        return "/dashboard"
    page = page.split("#", 1)[0].strip()
    if not page:
        return "/dashboard"
    return page[:240]


def _presence_payload(page: str, count: int) -> dict[str, object]:
    return _json_ready({"type": "presence", "page": page, "count": count, "as_of": datetime.now(KST)})


async def _presence_broadcast(page: str) -> None:
    async with presence_lock:
        sockets = list(presence_page_clients.get(page, set()))
        count = len(sockets)
    if not sockets:
        return
    payload = _presence_payload(page, count)
    stale: list[WebSocket] = []
    for socket in sockets:
        try:
            await socket.send_json(payload)
        except Exception:
            stale.append(socket)
    if not stale:
        return
    async with presence_lock:
        for socket in stale:
            active_page = presence_client_pages.pop(socket, None)
            if not active_page:
                continue
            subscribers = presence_page_clients.get(active_page)
            if not subscribers:
                continue
            subscribers.discard(socket)
            if not subscribers:
                presence_page_clients.pop(active_page, None)
        remaining = list(presence_page_clients.get(page, set()))
        remaining_count = len(remaining)
    if not remaining:
        return
    refreshed = _presence_payload(page, remaining_count)
    for socket in remaining:
        try:
            await socket.send_json(refreshed)
        except Exception:
            pass


async def _presence_set_page(socket: WebSocket, page: str) -> None:
    normalized = _normalize_presence_page(page)
    async with presence_lock:
        previous = presence_client_pages.get(socket)
        if previous == normalized:
            current_count = len(presence_page_clients.get(normalized, set()))
            send_self = True
        else:
            if previous:
                previous_clients = presence_page_clients.get(previous)
                if previous_clients:
                    previous_clients.discard(socket)
                    if not previous_clients:
                        presence_page_clients.pop(previous, None)
            presence_client_pages[socket] = normalized
            presence_page_clients.setdefault(normalized, set()).add(socket)
            current_count = len(presence_page_clients.get(normalized, set()))
            send_self = False
    if send_self:
        try:
            await socket.send_json(_presence_payload(normalized, current_count))
        except Exception:
            await _presence_remove(socket)
        return
    targets = {normalized}
    if previous and previous != normalized:
        targets.add(previous)
    for target in targets:
        await _presence_broadcast(target)


async def _presence_remove(socket: WebSocket) -> None:
    async with presence_lock:
        page = presence_client_pages.pop(socket, None)
        if not page:
            return
        subscribers = presence_page_clients.get(page)
        if subscribers:
            subscribers.discard(socket)
            if not subscribers:
                presence_page_clients.pop(page, None)
    await _presence_broadcast(page)


@app.get("/insight")
@app.get("/insight/desktop")
@app.get("/insight/mobile")
def insight_shell():
    if not INSIGHT_INDEX.exists():
        raise HTTPException(status_code=404, detail="Insight UI not found")
    return HTMLResponse(INSIGHT_INDEX.read_text(encoding="utf-8"))


@app.get("/desktop")
def desktop_shell():
    if not DESKTOP_INDEX.exists():
        raise HTTPException(status_code=404, detail="Desktop UI not found")
    return HTMLResponse(
        DESKTOP_INDEX.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/desktop-sw.js")
def desktop_service_worker():
    if not DESKTOP_SERVICE_WORKER.exists():
        raise HTTPException(status_code=404, detail="Desktop service worker not found")
    return FileResponse(
        DESKTOP_SERVICE_WORKER,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Service-Worker-Allowed": "/desktop",
        },
    )


@app.get("/dashboard")
@app.get("/dashboard/{code}")
def stock_dashboard_shell():
    if not STOCK_DASHBOARD_INDEX.exists():
        raise HTTPException(status_code=404, detail="Stock dashboard UI not found")
    # The dashboard shell points at versioned assets and must not be served from
    # an old browser document cache after a production release.
    document = STOCK_DASHBOARD_INDEX.read_text(encoding="utf-8").replace(
        "__DASHBOARD_ASSET_VERSION__", DASHBOARD_CLIENT_VERSION
    )
    return HTMLResponse(
        document,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/dashboard-version")
def stock_dashboard_version():
    return JSONResponse(
        {"version": DASHBOARD_CLIENT_VERSION},
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/market/calendar")
async def korea_market_calendar(days: int = Query(14, ge=1, le=31)):
    try:
        payload = await build_korea_market_calendar(days=days)
    except DashboardMarketDataError as exc:
        raise HTTPException(
            status_code=502,
            detail="한국 주요 일정을 불러오지 못했습니다.",
        ) from exc
    return JSONResponse(
        payload,
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/stocks/{code}/week-chart")
async def stock_week_chart(code: str):
    if re.fullmatch(r"[0-9]{6}", str(code or "")) is None:
        raise HTTPException(
            status_code=422,
            detail="종목 코드는 6자리 숫자여야 합니다.",
        )
    try:
        payload = await fetch_stock_week_chart(code)
    except DashboardMarketDataError as exc:
        raise HTTPException(
            status_code=502,
            detail="일주일 실시간 차트를 불러오지 못했습니다.",
        ) from exc
    return JSONResponse(
        payload,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/dashboard-refresh")
def stock_dashboard_refresh():
    # Recovery page for installed iOS/PWA clients that are still executing an
    # old cached dashboard bundle. It removes only this dashboard's worker and
    # static caches; local/session storage (including the login identity) stays.
    return HTMLResponse(
        f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <title>비밀노트 업데이트</title>
  </head>
  <body>
    <p>비밀노트 최신 화면을 준비하고 있습니다.</p>
    <script>
      (async () => {{
        try {{
          const registrations = await navigator.serviceWorker?.getRegistrations?.() || [];
          await Promise.all(registrations
            .filter((registration) => {{
              const scriptUrl = registration.active?.scriptURL || registration.waiting?.scriptURL || registration.installing?.scriptURL || "";
              return new URL(scriptUrl, location.origin).pathname === "/dashboard-sw.js";
            }})
            .map((registration) => registration.unregister()));
        }} catch {{}}
        try {{
          const cacheKeys = await caches?.keys?.() || [];
          await Promise.all(cacheKeys
            .filter((key) => key.startsWith("secret-note-static-"))
            .map((key) => caches.delete(key)));
        }} catch {{}}
        const params = new URLSearchParams(location.search);
        const view = ["home", "search", "portfolio", "chart", "recommend-detail", "morning-briefing"].includes(params.get("view"))
          ? params.get("view")
          : "search";
        const code = /^\\d{{6}}$/.test(params.get("code") || "") ? params.get("code") : "";
        const destination = code
          ? `/dashboard/${{code}}?app_build={DASHBOARD_CLIENT_VERSION}`
          : `/dashboard?view=${{encodeURIComponent(view)}}&app_build={DASHBOARD_CLIENT_VERSION}`;
        location.replace(destination);
      }})();
    </script>
  </body>
</html>""",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/portfolio")
def portfolio_shell():
    if not PORTFOLIO_INDEX.exists():
        raise HTTPException(status_code=404, detail="Portfolio UI not found")
    return HTMLResponse(PORTFOLIO_INDEX.read_text(encoding="utf-8"))


@app.get("/concepts")
def concepts_shell():
    if not CONCEPTS_INDEX.exists():
        raise HTTPException(status_code=404, detail="Concept UI not found")
    return HTMLResponse(CONCEPTS_INDEX.read_text(encoding="utf-8"))


@app.get("/nasdaq")
@app.get("/nasdaq/{code}")
def nasdaq_dashboard_shell():
    if not NASDAQ_DASHBOARD_INDEX.exists():
        raise HTTPException(status_code=404, detail="NASDAQ dashboard UI not found")
    return HTMLResponse(NASDAQ_DASHBOARD_INDEX.read_text(encoding="utf-8"))


@app.get("/dashboard.webmanifest")
def stock_dashboard_manifest():
    if not DASHBOARD_MANIFEST.exists():
        raise HTTPException(status_code=404, detail="Dashboard manifest not found")
    return FileResponse(DASHBOARD_MANIFEST, media_type="application/manifest+json")


@app.api_route("/dashboard-app-v170.js", methods=["GET", "HEAD"])
def stock_dashboard_app(request: Request):
    if not STOCK_DASHBOARD_APP.exists():
        raise HTTPException(status_code=404, detail="Dashboard application not found")
    # The shell supplies a build-version query, so released bundles can stay in
    # the browser cache while unversioned recovery requests remain revalidated.
    return FileResponse(
        STOCK_DASHBOARD_APP,
        media_type="application/javascript",
        headers=_dashboard_asset_cache_headers(request),
    )


@app.get("/dashboard-sw.js")
def stock_dashboard_service_worker():
    if not DASHBOARD_SERVICE_WORKER.exists():
        raise HTTPException(status_code=404, detail="Dashboard service worker not found")
    return FileResponse(
        DASHBOARD_SERVICE_WORKER,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/nasdaq.webmanifest")
def nasdaq_manifest():
    if not NASDAQ_MANIFEST.exists():
        raise HTTPException(status_code=404, detail="NASDAQ manifest not found")
    return FileResponse(NASDAQ_MANIFEST, media_type="application/manifest+json")


@app.get("/nasdaq-sw.js")
def nasdaq_service_worker():
    if not NASDAQ_SERVICE_WORKER.exists():
        raise HTTPException(status_code=404, detail="NASDAQ service worker not found")
    return FileResponse(NASDAQ_SERVICE_WORKER, media_type="application/javascript")


@app.get("/health")
@app.get("/healthz")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "strategy_version": STRATEGY_VERSION,
        "dashboard_version": DASHBOARD_CLIENT_VERSION,
        "canonical_base_url": settings.canonical_public_base_url,
    }


@app.get("/readyz")
def readyz() -> dict[str, object]:
    with SessionLocal() as db:
        db.execute(select(1))
    return {
        "status": "ok",
        "app": settings.app_name,
        "database_ok": True,
        "strategy_version": STRATEGY_VERSION,
        "dashboard_version": DASHBOARD_CLIENT_VERSION,
        "canonical_base_url": settings.canonical_public_base_url,
    }


WATCHLIST_ID_RE = re.compile(r"^[0-9A-Za-z가-힣_.-]{2,40}$")


def _normalize_watchlist_id(share_id: str) -> str:
    cleaned = share_id.strip()
    if not WATCHLIST_ID_RE.match(cleaned):
        raise HTTPException(status_code=422, detail="Watchlist ID must be 2-40 characters: Korean, letters, numbers, _, -, .")
    return cleaned


def _normalize_watchlist_investor_state(value: Optional[str]) -> str:
    return "holding" if str(value or "").strip() == "holding" else "not_holding"


def _watchlist_response(db: Session, share_id: str) -> dict[str, object]:
    items = list(
        db.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.share_id == share_id)
            .order_by(WatchlistItem.sort_order, WatchlistItem.created_at, WatchlistItem.code)
        )
    )
    updated_at = max((item.updated_at for item in items), default=datetime.utcnow())
    return {"share_id": share_id, "items": items, "updated_at": updated_at}


@app.get("/session/invite-status")
def session_invite_status(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    required = _invite_access_required(request)
    return {
        "required": required,
        "authorized": not required or _has_invite_access(request),
    }


@app.post("/session/invite-access")
def session_invite_access(payload: InviteAccessIn, request: Request, response: Response):
    if not _invite_access_required(request):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return {"required": False, "authorized": True}
    _enforce_rate_limit(request, "dashboard-invite", limit=10, window_seconds=15 * 60)
    expected = str(settings.dashboard_invite_code or "").strip().upper()
    submitted = str(payload.invite_code or "").strip().upper()
    if not expected or not secrets.compare_digest(submitted, expected):
        raise HTTPException(status_code=401, detail="초대 코드를 확인해주세요.")
    _set_invite_access_cookie(request, response)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return {"required": True, "authorized": True, "expires_in_seconds": INVITE_ACCESS_TTL_SECONDS}


@app.post("/session/dashboard-access")
def session_dashboard_access(
    payload: DashboardAccessIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    request_id = _request_trace_id(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["X-Request-ID"] = request_id
    share_id = _normalize_watchlist_id(payload.share_id)
    required = _invite_access_required(request)
    if not required:
        return {
            "required": False,
            "authorized": True,
            "newly_registered": False,
            "registered_count": None,
            "limit": None,
        }
    if not _has_invite_access(request):
        raise HTTPException(status_code=403, detail="초대 코드 확인이 필요합니다.")

    _enforce_rate_limit(request, "dashboard-access", limit=30, window_seconds=15 * 60)
    identity_limit = max(1, int(settings.dashboard_identity_limit or 100))
    now = datetime.utcnow()
    try:
        existing = db.get(DashboardAccessIdentity, share_id)
        if existing is not None:
            existing.last_seen_at = now
            db.commit()
            quota = db.get(DashboardAccessQuota, DASHBOARD_ACCESS_QUOTA_ID)
            return {
                "required": True,
                "authorized": True,
                "newly_registered": False,
                "registered_count": int(quota.admitted_count if quota else 0),
                "limit": identity_limit,
            }

        claimed_count = db.scalar(
            update(DashboardAccessQuota)
            .where(
                DashboardAccessQuota.id == DASHBOARD_ACCESS_QUOTA_ID,
                DashboardAccessQuota.admitted_count < identity_limit,
            )
            .values(
                admitted_count=DashboardAccessQuota.admitted_count + 1,
                updated_at=now,
            )
            .returning(DashboardAccessQuota.admitted_count)
        )
        if claimed_count is None:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "capacity_full",
                    "message": f"초기 이용 인원 {identity_limit}명이 모두 찼습니다.",
                    "limit": identity_limit,
                },
            )

        db.add(
            DashboardAccessIdentity(
                share_id=share_id,
                admitted_host=_host_only(request.headers.get("x-forwarded-host") or request.headers.get("host")),
                created_at=now,
                last_seen_at=now,
            )
        )
        newly_registered = True
        try:
            db.commit()
        except IntegrityError:
            # A simultaneous request using the same ID may have registered first.
            db.rollback()
            existing = db.get(DashboardAccessIdentity, share_id)
            if existing is None:
                raise
            existing.last_seen_at = now
            db.commit()
            quota = db.get(DashboardAccessQuota, DASHBOARD_ACCESS_QUOTA_ID)
            claimed_count = int(quota.admitted_count if quota else 0)
            newly_registered = False

        return {
            "required": True,
            "authorized": True,
            "newly_registered": newly_registered,
            "registered_count": int(claimed_count),
            "limit": identity_limit,
        }
    except HTTPException:
        raise
    except Exception:
        with suppress(Exception):
            db.rollback()
        share_id_fingerprint = hashlib.sha256(share_id.encode("utf-8")).hexdigest()[:12]
        logger.exception(
            "Dashboard access failed request_id=%s share_id_fingerprint=%s",
            request_id,
            share_id_fingerprint,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "access_unavailable",
                "message": "로그인 확인 서버가 잠시 불안정합니다.",
            },
            headers={"Retry-After": "1", "X-Request-ID": request_id},
        ) from None


@app.get("/internal/operations/invite-access-report")
def invite_access_report(
    request: Request,
    db: Session = Depends(get_db),
):
    expected = str(settings.dashboard_invite_code or "").strip()
    submitted = str(request.headers.get("x-operations-token") or "").strip()
    if not expected or not submitted or not secrets.compare_digest(submitted, expected):
        raise HTTPException(status_code=401, detail="운영 리포트 인증이 필요합니다.")

    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    start_of_day_utc = (
        now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(ZoneInfo("UTC"))
        .replace(tzinfo=None)
    )
    registered_count = int(
        db.scalar(select(func.count()).select_from(DashboardAccessIdentity)) or 0
    )
    today_new_count = int(
        db.scalar(
            select(func.count())
            .select_from(DashboardAccessIdentity)
            .where(DashboardAccessIdentity.created_at >= start_of_day_utc)
        )
        or 0
    )
    today_active_count = int(
        db.scalar(
            select(func.count())
            .select_from(DashboardAccessIdentity)
            .where(DashboardAccessIdentity.last_seen_at >= start_of_day_utc)
        )
        or 0
    )
    identity_limit = max(1, int(settings.dashboard_identity_limit or 100))
    return {
        "as_of": now_kst.isoformat(),
        "timezone": "Asia/Seoul",
        "registered_count": registered_count,
        "limit": identity_limit,
        "remaining_count": max(0, identity_limit - registered_count),
        "today_new_count": today_new_count,
        "today_active_count": today_active_count,
    }


@app.post("/desktop/session")
def desktop_session(
    payload: DashboardAccessIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    share_id = _normalize_watchlist_id(payload.share_id)
    access = session_dashboard_access(payload, request, response, db)
    response.set_cookie(
        DESKTOP_SESSION_COOKIE,
        _desktop_session_value(share_id),
        max_age=DESKTOP_SESSION_TTL_SECONDS,
        httponly=True,
        secure=_request_scheme(request) == "https",
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return {
        "authorized": True,
        "share_id": share_id,
        "expires_in_seconds": DESKTOP_SESSION_TTL_SECONDS,
        "access": access,
    }


@app.get("/desktop/preferences")
def desktop_preferences(request: Request, response: Response, db: Session = Depends(get_db)):
    share_id = _desktop_share_id_from_request(request)
    preference = db.get(DesktopUserPreference, share_id)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return {
        "share_id": share_id,
        "document_title": preference.document_title if preference else DEFAULT_DESKTOP_DOCUMENT_TITLE,
        "updated_at": preference.updated_at.isoformat() if preference else None,
    }


@app.put("/desktop/preferences")
def update_desktop_preferences(
    payload: DesktopPreferenceIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    share_id = _desktop_share_id_from_request(request)
    document_title = payload.document_title.strip()
    if not document_title:
        raise HTTPException(status_code=422, detail="문서 제목을 입력해주세요.")
    preference = db.get(DesktopUserPreference, share_id)
    if preference is None:
        preference = DesktopUserPreference(share_id=share_id, document_title=document_title)
        db.add(preference)
    else:
        preference.document_title = document_title
        preference.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(preference)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return {
        "share_id": share_id,
        "document_title": preference.document_title,
        "updated_at": preference.updated_at.isoformat(),
    }


@app.get("/session/write-token")
def session_write_token(
    request: Request,
    response: Response,
    share_id: str = Query(..., min_length=2, max_length=40),
    market: Optional[str] = Query(default=None),
):
    normalized_id = _normalize_write_scope(share_id, market=market)
    session_id = str(request.cookies.get(WRITE_SESSION_COOKIE) or "").strip()
    session = _load_write_session(session_id) if session_id else None
    if not session:
        session_id = secrets.token_urlsafe(18)
        token = secrets.token_urlsafe(24)
        share_ids = [normalized_id]
    else:
        token = str(session.get("token") or secrets.token_urlsafe(24))
        share_ids = [str(item).strip() for item in (session.get("share_ids") or []) if str(item).strip()]
        share_ids.append(normalized_id)
    _store_write_session(session_id, token, share_ids)
    response.set_cookie(
        WRITE_SESSION_COOKIE,
        session_id,
        max_age=WRITE_SESSION_TTL_SECONDS,
        httponly=True,
        secure=_request_scheme(request) == "https",
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "share_id": normalized_id,
        "write_token": token,
        "expires_in_seconds": WRITE_SESSION_TTL_SECONDS,
    }


@app.get("/watchlists/{share_id}", response_model=WatchlistOut)
def get_watchlist(share_id: str, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return _watchlist_response(db, _normalize_watchlist_id(share_id))


def _normalize_recommendation_track_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        code = _normalize_stock_code(str(raw_item.get("code") or ""))
        name = str(raw_item.get("name") or "").strip()[:120]
        if not code or not name or code in seen:
            continue
        seen.add(code)
        item = deepcopy(raw_item)
        item["code"] = code
        item["name"] = name
        if item.get("market") is not None:
            item["market"] = str(item.get("market") or "").strip()[:20]
        normalized.append(item)
    return normalized[:50]


def _recommendation_track_state_response(
    db: Session, share_id: str
) -> dict[str, object]:
    row = db.get(RecommendationTrackState, share_id)
    if row is None:
        return {
            "share_id": share_id,
            "initialized": False,
            "items": [],
            "updated_at": datetime.utcnow(),
        }
    try:
        decoded = json.loads(row.payload or "[]")
    except (TypeError, ValueError):
        decoded = []
    items = _normalize_recommendation_track_items(decoded if isinstance(decoded, list) else [])
    return {
        "share_id": share_id,
        "initialized": True,
        "items": items,
        "updated_at": row.updated_at,
    }


@app.get(
    "/watchlists/{share_id}/recommendation-tracks",
    response_model=RecommendationTrackStateOut,
)
def get_recommendation_tracks(
    share_id: str,
    response: Response,
    db: Session = Depends(get_db),
):
    normalized_id = _normalize_watchlist_id(share_id)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return _recommendation_track_state_response(db, normalized_id)


@app.put(
    "/watchlists/{share_id}/recommendation-tracks",
    response_model=RecommendationTrackStateOut,
)
def put_recommendation_tracks(
    share_id: str,
    payload: RecommendationTrackUpdateIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    normalized_id = _normalize_watchlist_id(share_id)
    _require_write_access(request, normalized_id)
    items = _normalize_recommendation_track_items(payload.items)
    encoded = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > 500_000:
        raise HTTPException(status_code=413, detail="핀 종목 데이터가 너무 큽니다.")
    row = db.get(RecommendationTrackState, normalized_id)
    if row is None:
        row = RecommendationTrackState(share_id=normalized_id, payload=encoded)
    else:
        row.payload = encoded
        row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return _recommendation_track_state_response(db, normalized_id)


@app.get("/watchlists/{share_id}/quant-signals")
def get_watchlist_quant_signals(
    share_id: str,
    request: Request,
    response: Response,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "watchlist_quant_signals", limit=30, window_seconds=60)
    normalized_id = _normalize_watchlist_id(share_id)
    cache_key = ("watchlist_quant_signals", normalized_id)
    current_time = datetime.now(KST)
    quote_refresh_active = _quant_signal_quote_refresh_active(current_time)
    cached_payload = None if refresh else watchlist_quant_signal_cache.get(cache_key)
    if cached_payload is not None and not quote_refresh_active:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return deepcopy(cached_payload)
    watch_items = list(
        db.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.share_id == normalized_id)
            .order_by(WatchlistItem.sort_order, WatchlistItem.created_at, WatchlistItem.code)
        )
    )
    live_quotes = _watchlist_quant_signal_live_quotes(
        [watch_item.code for watch_item in watch_items],
        current_time,
    )
    items: list[dict[str, object]] = []
    for watch_item in watch_items:
        if not settings.market_quant_signal_source_url:
            ensure_stock_price_history(
                db,
                watch_item.code,
                min_rows=MIN_BACKTEST_HISTORY_ROWS,
                lookback_days=600,
                require_recent_complete_ohlc=True,
            )
        live_quote = live_quotes.get(watch_item.code)
        payload = load_reference_quant_signal_payload(
            db,
            watch_item.code,
            source_url=settings.market_quant_signal_source_url,
            source_timeout_seconds=settings.market_quant_signal_source_timeout_seconds,
            live_quote=live_quote,
            now=current_time,
            include_context=False,
            include_stored_intraday=live_quote is None,
        )
        sector_payload = enrich_quant_signal_payload_sector(
            db,
            payload or {"code": watch_item.code},
            watch_item.code,
        )
        if payload:
            payload = sanitize_pending_entry_signal_payload(sector_payload)
        summary = quant_signal_current_summary_fields(payload) if payload else {
            "strategy_version": STRATEGY_VERSION,
            "data_state": "unavailable",
            "data_message": "가격 이력을 확인하는 중입니다.",
            "current": None,
        }
        items.append(
            {
                "code": watch_item.code,
                "name": watch_item.name,
                "market": watch_item.market,
                "sector": sector_payload.get("sector"),
                "industry": sector_payload.get("industry"),
                "investment_sector": sector_payload.get("investment_sector"),
                "investment_sector_label": sector_payload.get("investment_sector_label"),
                **summary,
            }
        )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    result = {
        "share_id": normalized_id,
        "strategy_version": STRATEGY_VERSION,
        "as_of": current_time,
        "live_quotes": bool(live_quotes),
        "items": items,
    }
    # During trading and the post-close publication window, rebuild from the
    # same uncached quote source used by stock detail. Stable closes can reuse
    # the result only briefly. Stable closes may reuse it for one minute, while
    # an explicit refresh always bypasses the server cache above.
    watchlist_quant_signal_cache.set(cache_key, result, 5 if quote_refresh_active else 60)
    return deepcopy(result)


def _notification_history_kst_iso(value: datetime) -> str:
    candidate = value
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)
    return candidate.astimezone(KST).isoformat(timespec="seconds")


def _signal_history_time(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        candidate = value
    else:
        raw = str(value or "").strip().replace("Z", "+00:00")
        if not raw:
            return None
        try:
            candidate = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=KST)
    return candidate.astimezone(KST)


def _signal_history_time_boundary(
    *values: Any,
    latest: bool = False,
) -> Optional[str]:
    candidates = [candidate for value in values if (candidate := _signal_history_time(value))]
    if not candidates:
        return None
    selected = max(candidates) if latest else min(candidates)
    return selected.isoformat(timespec="seconds")


def _merge_market_preliminary_notification_history(
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Supplement the shared snapshot with today's actually delivered signals."""

    result = deepcopy(payload)
    event_date = datetime.now(KST).date().isoformat()
    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    active_keys: set[tuple[str, str, str]] = set()
    for item in result.get("items") or []:
        if not isinstance(item, dict):
            continue
        preliminary = bool(item.get("is_preliminary")) or item.get("status") == "preliminary"
        code = str(item.get("code") or "").strip()
        side = str(item.get("side") or "").strip().lower()
        signal_date = str(item.get("signal_date") or "")[:10]
        if preliminary and code and side in {"buy", "sell"} and signal_date == event_date:
            active_keys.add((code, side, signal_date))
    for item in result.get("preliminary_history") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        side = str(item.get("side") or "").strip().lower()
        signal_date = str(item.get("signal_date") or "")[:10]
        if code and side in {"buy", "sell"} and signal_date == event_date:
            records[(code, side, signal_date)] = deepcopy(item)

    rows = list(
        db.scalars(
            select(PushNotificationHistory)
            .where(
                # This is a shared market feed. Account/watchlist notifications
                # (``ai_signal``) must never leak an account-only stock into it.
                PushNotificationHistory.notification_kind == "market_ai_signal",
                PushNotificationHistory.created_at >= datetime.combine(
                    date.fromisoformat(event_date) - timedelta(days=1),
                    time.min,
                ),
            )
            .order_by(PushNotificationHistory.created_at.asc(), PushNotificationHistory.id.asc())
        )
    )
    for row in rows:
        context = notification_history_signal_context(row.notification_kind, row.event_key)
        if not context or context.get("phase") != "preliminary":
            continue
        signal_date = context["event_date"]
        if signal_date != event_date:
            continue
        code = context["code"]
        side = context["side"]
        key = (code, side, signal_date)
        stored = records.get(key, {})
        created_at = _notification_history_kst_iso(row.created_at)
        name = notification_history_signal_name(row.title)
        stored.update(
            {
                "code": code,
                "name": stored.get("name") or name or code,
                "side": side,
                "signal": "예비 매수" if side == "buy" else "예비 매도",
                "signal_date": signal_date,
                "action": context["action"],
                "first_seen_at": _signal_history_time_boundary(
                    stored.get("first_seen_at"),
                    created_at,
                ),
                "last_seen_at": _signal_history_time_boundary(
                    stored.get("last_seen_at"),
                    created_at,
                    latest=True,
                ),
                "active": key in active_keys,
            }
        )
        records[key] = stored
    result["preliminary_history"] = sorted(
        records.values(),
        key=lambda item: str(item.get("first_seen_at") or ""),
        reverse=True,
    )
    return result


@app.get("/market/quant-signals")
def get_market_quant_signals(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    universe_limit: int = Query(
        default=MARKET_SIGNAL_UNIVERSE_LIMIT,
        ge=20,
        le=MARKET_SIGNAL_UNIVERSE_LIMIT,
    ),
    limit: int = Query(default=0, ge=0, le=1000),
    recent_days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "market_quant_signals", limit=30, window_seconds=60)
    cache_key = ("market_quant_signals", universe_limit, limit, recent_days)
    payload = market_quant_signal_cache.get(cache_key)
    if payload is None:
        payload = load_market_quant_signal_snapshot(
            db,
            universe_limit=universe_limit,
            limit=limit,
            recent_days=recent_days,
        )
    if payload is None:
        if market_quant_signal_refresh_lock.acquire(blocking=False):
            try:
                generated = _build_market_quant_signal_payload(
                    db,
                    universe_limit=universe_limit,
                    limit=limit,
                    recent_days=recent_days,
                    now=datetime.now(KST),
                )
                payload = save_market_quant_signal_snapshot(
                    db,
                    generated,
                    universe_limit=universe_limit,
                    limit=limit,
                    recent_days=recent_days,
                )
            finally:
                market_quant_signal_refresh_lock.release()
    if payload is None:
        background_tasks.add_task(
            _refresh_market_quant_signal_snapshot,
            universe_limit,
            limit,
            recent_days,
        )
        payload = {
            "status": "preparing",
            "strategy_version": STRATEGY_VERSION,
            "as_of": datetime.now(KST),
            "universe_as_of": None,
            "universe_count": 0,
            "recent_days": recent_days,
            "preliminary_count": 0,
            "confirmed_count": 0,
            "items": [],
        }
        payload = apply_market_signal_reconciliations(payload, now=datetime.now(KST)) or payload
    else:
        current_time = datetime.now(KST)
        payload = deepcopy(payload)
        freshness = _market_quant_signal_snapshot_freshness(payload, current_time)
        payload.update(freshness)
        if freshness["snapshot_state"] == "stale":
            payload["status"] = "refreshing"
            payload = _suppress_stale_preliminary_market_signals(payload)
            background_tasks.add_task(
                _refresh_market_quant_signal_snapshot,
                universe_limit,
                limit,
                recent_days,
            )
        payload = apply_market_signal_reconciliations(payload, now=current_time) or payload
        payload = enrich_market_quant_signal_sectors(db, payload)
        market_quant_signal_cache.set(cache_key, payload, 300)
        payload = _merge_market_preliminary_notification_history(db, payload)
    payload = sanitize_pending_entry_signal_items(payload)
    payload.setdefault("snapshot_generated_at", None)
    payload.setdefault("as_of", datetime.now(KST))
    if _is_canonical_market_signal_scope(universe_limit, limit, recent_days):
        revision_frame = _record_ai_signal_revision(payload, publish=True)
    else:
        revision_frame = _current_ai_signal_revision_frame()
    payload["signal_revision"] = revision_frame["revision"]
    payload["signal_revision_as_of"] = revision_frame["as_of"]
    payload["signal_revision_scope"] = "canonical_market_feed"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return payload


@app.put("/watchlists/{share_id}", response_model=WatchlistOut)
def put_watchlist(share_id: str, payload: WatchlistUpdateIn, request: Request, db: Session = Depends(get_db)):
    normalized_id = _normalize_watchlist_id(share_id)
    _require_write_access(request, normalized_id)
    existing = {
        item.code: item
        for item in db.scalars(
            select(WatchlistItem).where(WatchlistItem.share_id == normalized_id)
        )
    }
    seen: set[str] = set()
    rows: list[WatchlistItem] = []
    for item in payload.items:
        code = _normalize_stock_code(item.code)
        if not code or code in seen:
            continue
        seen.add(code)
        master = db.get(StockMaster, code)
        row = existing.get(code)
        requested_state = (
            _normalize_watchlist_investor_state(item.investor_state)
            if item.investor_state is not None
            else None
        )
        if row is None:
            row = WatchlistItem(
                share_id=normalized_id,
                code=code,
                investor_state=requested_state or "not_holding",
            )
        elif requested_state is not None:
            row.investor_state = requested_state
        if requested_state == "not_holding":
            row.average_buy_price = None
        elif row.investor_state == "holding" and "average_buy_price" in item.model_fields_set:
            row.average_buy_price = item.average_buy_price
        row.name = (item.name or (master.name if master else code)).strip()
        row.market = item.market or (master.market if master else None)
        row.sort_order = len(rows)
        rows.append(row)
    for code, row in existing.items():
        if code not in seen:
            db.delete(row)
    db.add_all(row for row in rows if row.id is None)
    db.commit()
    return _watchlist_response(db, normalized_id)


@app.get("/push/config")
def push_config():
    return {
        "enabled": web_push_runtime.configured,
        "public_key": settings.web_push_vapid_public_key if web_push_runtime.configured else None,
        "conditions": list(DEFAULT_PUSH_CONDITIONS),
        "condition_options": deepcopy(PUSH_CONDITION_OPTIONS),
        "price_threshold": settings.web_push_price_threshold,
    }


@app.get("/push/subscriptions/{share_id}/status")
def push_subscription_status(
    share_id: str,
    endpoint: str = Query(..., min_length=20, max_length=2048),
    db: Session = Depends(get_db),
):
    normalized_id = _normalize_watchlist_id(share_id)
    subscription = db.scalar(
        select(PushSubscription).where(
            PushSubscription.share_id == normalized_id,
            PushSubscription.endpoint == endpoint,
            PushSubscription.enabled.is_(True),
        )
    )
    return {
        "enabled": subscription is not None,
        "conditions": _subscription_conditions(subscription),
    }


def _push_notification_event_date(row: PushNotificationHistory) -> Optional[str]:
    event_date = notification_history_event_date(row.notification_kind, row.event_key)
    return event_date.isoformat() if event_date else None


@app.get("/push/notifications/{share_id}")
def push_notification_history(
    share_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    normalized_id = _normalize_watchlist_id(share_id)
    _require_write_access(request, normalized_id)
    cutoff = datetime.utcnow() - timedelta(days=3)
    db.execute(delete(PushNotificationHistory).where(PushNotificationHistory.created_at < cutoff))
    db.commit()
    recent_rows = list(
        db.scalars(
            select(PushNotificationHistory)
            .where(
                PushNotificationHistory.share_id == normalized_id,
                PushNotificationHistory.created_at >= cutoff,
            )
            .order_by(desc(PushNotificationHistory.created_at), desc(PushNotificationHistory.id))
        )
    )
    invalid_signal_ids = [
        row.id
        for row in recent_rows
        if not notification_history_is_valid(
            row.notification_kind,
            row.event_key,
            row.created_at,
        )
    ]
    invalid_signal_id_set = set(invalid_signal_ids)
    rows = [row for row in recent_rows if row.id not in invalid_signal_id_set][:limit]
    if invalid_signal_ids:
        db.execute(
            delete(PushNotificationHistory).where(
                PushNotificationHistory.id.in_(invalid_signal_ids)
            )
        )
        db.commit()
    return {
        "retention_days": 3,
        "items": [
            {
                "id": row.id,
                "kind": row.notification_kind,
                "title": row.title,
                "body": row.body,
                "url": row.url,
                "event_date": _push_notification_event_date(row),
                "created_at": f"{row.created_at.isoformat(timespec='seconds')}Z",
            }
            for row in rows
        ],
    }


@app.post("/push/subscriptions/{share_id}")
def save_push_subscription(
    share_id: str,
    payload: PushSubscriptionIn,
    request: Request,
    db: Session = Depends(get_db),
):
    normalized_id = _normalize_watchlist_id(share_id)
    _require_write_access(request, normalized_id)
    if not web_push_runtime.configured:
        raise HTTPException(status_code=503, detail="웹푸시 발송 키가 설정되지 않았습니다.")
    if not payload.endpoint.startswith("https://"):
        raise HTTPException(status_code=422, detail="유효한 HTTPS 푸시 주소가 필요합니다.")
    conditions = _normalize_push_conditions(payload.conditions)
    subscription = db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    )
    should_test = subscription is None or not subscription.enabled or subscription.share_id != normalized_id
    if subscription is None:
        subscription = PushSubscription(
            share_id=normalized_id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            notification_preferences=json.dumps(conditions, ensure_ascii=False),
            user_agent=str(request.headers.get("user-agent") or "")[:500] or None,
        )
        db.add(subscription)
    else:
        if subscription.share_id != normalized_id or not subscription.enabled:
            subscription.created_at = datetime.utcnow()
        subscription.share_id = normalized_id
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth
        subscription.notification_preferences = json.dumps(conditions, ensure_ascii=False)
        subscription.user_agent = str(request.headers.get("user-agent") or "")[:500] or None
        subscription.enabled = True
    db.commit()
    db.refresh(subscription)
    test_sent = web_push_runtime.send_test(db, subscription) if should_test else None
    db.refresh(subscription)
    if should_test and not test_sent:
        raise HTTPException(
            status_code=502,
            detail="구독은 저장했지만 시험 알림 전송에 실패했습니다. 이 기기의 알림을 다시 켜주세요.",
        )
    return {
        "enabled": subscription.enabled,
        "test_required": should_test,
        "test_sent": test_sent,
        "conditions": conditions,
    }


@app.post("/push/subscriptions/{share_id}/test")
def test_push_subscription(
    share_id: str,
    payload: PushSubscriptionDeleteIn,
    request: Request,
    db: Session = Depends(get_db),
):
    normalized_id = _normalize_watchlist_id(share_id)
    _require_write_access(request, normalized_id)
    if not web_push_runtime.configured:
        raise HTTPException(status_code=503, detail="웹푸시 발송 키가 설정되지 않았습니다.")
    subscription = db.scalar(
        select(PushSubscription).where(
            PushSubscription.share_id == normalized_id,
            PushSubscription.endpoint == payload.endpoint,
            PushSubscription.enabled.is_(True),
        )
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="현재 기기의 알림 구독을 찾지 못했습니다.")
    if not web_push_runtime.send_test(db, subscription):
        raise HTTPException(status_code=502, detail="푸시 서버가 시험 알림을 수락하지 않았습니다.")
    return {"sent": True}


@app.delete("/push/subscriptions/{share_id}")
def delete_push_subscription(
    share_id: str,
    payload: PushSubscriptionDeleteIn,
    request: Request,
    db: Session = Depends(get_db),
):
    normalized_id = _normalize_watchlist_id(share_id)
    _require_write_access(request, normalized_id)
    subscription = db.scalar(
        select(PushSubscription).where(
            PushSubscription.share_id == normalized_id,
            PushSubscription.endpoint == payload.endpoint,
        )
    )
    if subscription:
        subscription.enabled = False
        db.commit()
    return {"enabled": False}


def _normalize_us_symbol(value: str) -> str:
    return "".join(ch for ch in value.strip().upper() if ch.isalnum() or ch in ".-")[:12]


def _us_watchlist_id(share_id: str) -> str:
    return f"us.{_normalize_watchlist_id(share_id)}"


@app.get("/us/watchlists/{share_id}")
def get_us_watchlist(share_id: str, db: Session = Depends(get_db)):
    return _watchlist_response(db, _us_watchlist_id(share_id))


@app.put("/us/watchlists/{share_id}")
def put_us_watchlist(share_id: str, payload: WatchlistUpdateIn, request: Request, db: Session = Depends(get_db)):
    normalized_id = _us_watchlist_id(share_id)
    _require_write_access(request, normalized_id)
    seen: set[str] = set()
    rows: list[WatchlistItem] = []
    for item in payload.items:
        code = _normalize_us_symbol(item.code)
        if not code or code in seen:
            continue
        seen.add(code)
        rows.append(
            WatchlistItem(
                share_id=normalized_id,
                code=code,
                name=(item.name or code).strip(),
                market=item.market or "NASDAQ",
                sort_order=len(rows),
            )
        )
    db.execute(delete(WatchlistItem).where(WatchlistItem.share_id == normalized_id))
    db.add_all(rows)
    db.commit()
    return _watchlist_response(db, normalized_id)


@app.get("/us/stocks/search")
def us_stock_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    return search_us_stocks(query, limit=limit)


@app.get("/us/stocks/resolve")
def us_stock_resolve(query: str = Query(..., min_length=1)):
    try:
        return resolve_us_stock(query)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="US stock not found") from exc


@app.get("/us/stocks/{symbol}")
def us_stock_detail(symbol: str):
    try:
        return resolve_us_stock(symbol)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="US stock not found") from exc


@app.get("/us/stocks/{symbol}/dashboard")
def us_stock_dashboard(symbol: str, refresh: bool = Query(default=False)):
    key = ("us_stock_dashboard", _normalize_us_symbol(symbol))
    try:
        if refresh:
            payload = build_us_dashboard(symbol, refresh=True)
            api_cache.set(key, payload, STOCK_DASHBOARD_TTL_SECONDS)
        else:
            payload = api_cache.get_or_set(key, STOCK_DASHBOARD_TTL_SECONDS, lambda: build_us_dashboard(symbol))
        return payload
    except Exception as exc:
        raise HTTPException(status_code=404, detail="US stock not found") from exc


@app.websocket("/ws/us/stocks/{symbol}/quote")
async def us_stock_quote_stream(websocket: WebSocket, symbol: str):
    await websocket.accept()
    normalized = _normalize_us_symbol(symbol)
    try:
        while True:
            payload = await asyncio.to_thread(_us_stock_quote_stream_payload, normalized)
            if payload is None:
                await websocket.send_json({"type": "error", "message": "US stock quote not found"})
                return
            await websocket.send_json(payload)
            await asyncio.sleep(8)
    except (WebSocketDisconnect, RuntimeError):
        return


@app.websocket("/ws/presence")
async def page_presence_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            await _presence_set_page(websocket, (payload or {}).get("page") or "/dashboard")
    except WebSocketDisconnect:
        return
    finally:
        await _presence_remove(websocket)


def _us_stock_quote_stream_payload(symbol: str) -> Optional[dict[str, object]]:
    try:
        dashboard = build_us_dashboard(symbol, refresh=True)
    except Exception:
        return None
    return _json_ready(
        {
            "type": "quote",
            "code": dashboard["code"],
            "name": dashboard["name"],
            "market": dashboard["market"],
            "as_of": dashboard["as_of"],
            "source": "yahoo_stream",
            "interval_seconds": 8,
            "quote": dashboard["quote"],
        }
    )


@app.get("/us/fx/usdkrw")
def us_fx_usdkrw(refresh: bool = Query(default=False)):
    try:
        return usdkrw_rate(refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="USD/KRW rate not available") from exc


@app.get("/market/us-sector-moves")
def market_us_sector_moves(
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    try:
        complete = get_complete_snapshot(
            db,
            US_SECTOR_MOVES_SNAPSHOT_KEY,
            schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
        )
        if complete is None:
            if not settings.runs_collectors():
                _queue_cold_snapshot_or_503(
                    db,
                    US_SECTOR_MOVES_SNAPSHOT_KEY,
                    detail="Complete US sector snapshot is being prepared",
                )
            payload = us_sector_moves(refresh=refresh)
            try:
                published = _publish_cold_snapshot_or_read_winner(
                    db,
                    US_SECTOR_MOVES_SNAPSHOT_KEY,
                    payload,
                    fresh_for_seconds=int(payload.get("refresh_interval_seconds") or 300),
                    schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
                    captured_at=payload.get("as_of"),
                    validator=_validate_us_sector_moves_snapshot,
                )
                return published.payload
            except ValueError:
                logger.warning("US sector cold-start payload was incomplete; refusing partial response")
                _queue_cold_snapshot_or_503(
                    db,
                    US_SECTOR_MOVES_SNAPSHOT_KEY,
                    detail="Complete US sector snapshot is being prepared",
                )
        if refresh or not complete.is_fresh:
            _queue_complete_snapshot_refresh(db, US_SECTOR_MOVES_SNAPSHOT_KEY)
        return complete.payload
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="US sector moves not available") from exc


def _validate_us_sector_moves_snapshot(payload: Any) -> dict[str, Any]:
    candidate = _json_ready(payload)
    items = candidate.get("items") if isinstance(candidate, dict) else None
    expected = [item["symbol"] for item in US_SECTOR_ETFS]
    actual = [str(item.get("symbol") or "") for item in items or []]
    if actual != expected:
        raise ValueError("US sector snapshot must contain every configured ETF in order")
    for item in items:
        if not str(item.get("label") or "").strip() or not str(item.get("sector") or "").strip():
            raise ValueError("US sector snapshot item metadata is incomplete")
        if item.get("price") is None or item.get("previous_close") is None:
            raise ValueError("US sector snapshot item is missing price data")
        if item.get("change_rate") is None or not item.get("trade_date"):
            raise ValueError("US sector snapshot item is missing change or date data")
    return candidate


def _build_us_sector_moves_snapshot(_db: Session, _snapshot_key: str) -> SnapshotBuild:
    payload = us_sector_moves(refresh=True)
    return SnapshotBuild(
        payload=payload,
        fresh_for_seconds=int(payload.get("refresh_interval_seconds") or 300),
        captured_at=payload.get("as_of"),
        validator=_validate_us_sector_moves_snapshot,
    )


def _load_us_sector_moves_snapshot_for_stream() -> dict[str, Any]:
    with SessionLocal() as db:
        return market_us_sector_moves(refresh=False, db=db)


@app.websocket("/ws/market/us-sector-moves")
async def market_us_sector_moves_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = await asyncio.to_thread(_load_us_sector_moves_snapshot_for_stream)
            await websocket.send_json(_json_ready({"type": "us_sector_moves", **payload}))
            interval_seconds = max(30, int(payload.get("refresh_interval_seconds") or 300))
            await asyncio.sleep(interval_seconds)
    except (WebSocketDisconnect, RuntimeError):
        return


@app.get("/us/stocks/{symbol}/prices")
def us_stock_prices(
    symbol: str,
    limit: int = Query(default=250, ge=1, le=2000),
    refresh: bool = Query(default=False),
):
    try:
        return us_prices(symbol, limit=limit, refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="US stock prices not found") from exc


@app.get("/us/stocks/{symbol}/ai-analysis", response_model=StockAIAnalysisOut)
def us_stock_ai_analysis(
    symbol: str,
    request: Request,
    refresh: bool = Query(default=False),
):
    _enforce_rate_limit(request, "us_stock_ai_analysis", limit=20, window_seconds=60)
    dashboard = us_stock_dashboard(symbol, refresh=refresh)
    return build_stock_ai_analysis(dashboard)


@app.get("/us/market/rankings")
def us_market_rankings(
    category: str = Query(default="surge"),
    market: str = Query(default="ALL"),
    limit: int = Query(default=20, ge=1, le=100),
):
    key = ("us_market_rankings", category, market, limit)
    return api_cache.get_or_set(
        key,
        MARKET_RANKING_TTL_SECONDS,
        lambda: build_us_rankings(category, limit=limit, market=market),
    )


@app.get("/us/market/recommendations")
def us_market_recommendations(
    request: Request,
    limit: int = Query(default=8, ge=1, le=20),
    candidate_limit: int = Query(default=30, ge=5, le=100),
):
    _enforce_rate_limit(request, "us_market_recommendations", limit=10, window_seconds=60)
    key = ("us_market_recommendations", limit, candidate_limit)
    return api_cache.get_or_set(
        key,
        RECOMMENDATION_TTL_SECONDS,
        lambda: build_us_recommendations(limit=limit, candidate_limit=candidate_limit),
    )


@app.get("/us/market/trends")
def us_market_trends(
    request: Request,
    days: int = Query(default=7, ge=1, le=30),
):
    _enforce_rate_limit(request, "us_market_trends", limit=12, window_seconds=60)
    key = ("us_market_trends", days)
    return api_cache.get_or_set(key, TREND_ANALYSIS_TTL_SECONDS, lambda: build_us_trends(days=days))


@app.get("/us/market/trends/{event_id}/graph")
def us_market_trend_graph(event_id: str, request: Request):
    _enforce_rate_limit(request, "us_market_trend_graph", limit=20, window_seconds=60)
    key = ("us_market_trend_graph", event_id)
    return api_cache.get_or_set(key, TREND_GRAPH_TTL_SECONDS, lambda: build_us_event_graph(event_id))


@app.get("/us/market/impact", response_model=MarketImpactOut)
def us_market_impact(
    request: Request,
    refresh: bool = Query(default=False),
):
    _enforce_rate_limit(request, "us_market_impact", limit=20, window_seconds=60)
    key = ("us_market_impact",)
    if refresh:
        payload = build_us_market_impact()
        api_cache.set(key, payload, MARKET_IMPACT_TTL_SECONDS)
        return payload
    return api_cache.get_or_set(key, MARKET_IMPACT_TTL_SECONDS, build_us_market_impact)


def _normalize_stock_query(value: str) -> str:
    return re.sub(r"[^0-9A-Z가-힣]", "", value.strip().upper())


def _stock_query_terms(value: str) -> set[str]:
    normalized = _normalize_stock_query(value)
    terms = {normalized} if normalized else set()
    replacements = {
        "TND": "티엔디",
        "TD": "티엔디",
        "티엔디": "TND",
    }
    for source, target in replacements.items():
        if source in normalized:
            terms.add(normalized.replace(source, target))
    return {term for term in terms if term}


def _normalize_stock_code(value: str) -> str:
    cleaned = _normalize_stock_query(value)
    if len(cleaned) == 7 and cleaned.startswith("A") and cleaned[1:].isdigit():
        return cleaned[1:]
    return cleaned


REPRESENTATIVE_STOCK_NAMES = {
    "삼성": "삼성전자",
    "현대": "현대차",
    "하이닉스": "SK하이닉스",
    "엘지": "LG",
    "네이버": "NAVER",
}


def _fetch_naver_stock_identity(code: str) -> Optional[dict[str, str]]:
    if not re.fullmatch(r"[0-9A-Z]{6}", code):
        return None
    if code.isdigit():
        try:
            response = requests.get(
                "https://finance.naver.com/item/main.naver",
                params={"code": code},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            response.raise_for_status()
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            name_node = soup.select_one("div.wrap_company h2 a")
            name = name_node.get_text(strip=True) if name_node else ""
            if name:
                market = (
                    "KOSDAQ"
                    if soup.select_one("img.kosdaq")
                    else "KOSPI"
                    if soup.select_one("img.kospi")
                    else ""
                )
                if not market:
                    market_text = soup.get_text(" ", strip=True)
                    market = (
                        "KOSDAQ"
                        if "코스닥" in market_text
                        else "KOSPI"
                        if "코스피" in market_text
                        else "UNKNOWN"
                    )
                return {"code": code, "name": name, "market": market}
        except Exception:
            pass

    # New Korean short codes may contain letters.  The legacy finance page
    # cannot resolve them, while Naver's ETF detail API is keyed by the exact
    # six-character exchange code and remains authoritative for the ETF name.
    try:
        response = requests.get(
            f"https://stock.naver.com/api/domestic/detail/{code}/ETFBase",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://stock.naver.com/"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    name = str(payload.get("itemName") or "").strip() if isinstance(payload, dict) else ""
    if not name:
        return None
    return {"code": code, "name": name, "market": "KOSPI"}


def _fetch_naver_stock_code_by_query(query: str) -> Optional[str]:
    cleaned = str(query or "").strip()
    if not cleaned:
        return None
    try:
        response = requests.get(
            "https://ac.stock.naver.com/ac",
            params={"q": cleaned, "target": "stock,index,marketindicator"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    items = payload.get("items") if isinstance(payload, dict) else []
    candidates = [
        item
        for item in items or []
        if isinstance(item, dict)
        and item.get("nationCode") == "KOR"
        and re.fullmatch(r"[0-9A-Z]{6}", str(item.get("code") or ""))
        and str(item.get("name") or "").strip()
    ]
    if not candidates:
        return None
    normalized_query = _normalize_stock_query(cleaned)
    exact = next(
        (
            item
            for item in candidates
            if _normalize_stock_query(str(item.get("name") or "")) == normalized_query
        ),
        None,
    )
    return str((exact or candidates[0]).get("code") or "") or None


def _ensure_stock_master_from_naver(db: Session, code: str) -> Optional[StockMaster]:
    code = _normalize_stock_code(code)
    item = db.get(StockMaster, code)
    if item and item.is_active:
        return item
    identity = _fetch_naver_stock_identity(code)
    if not identity:
        return None
    if item is None:
        item = StockMaster(code=identity["code"])
    item.name = identity["name"]
    item.market = identity["market"]
    item.is_active = True
    item.last_seen_date = datetime.now(KST).date()
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.get(StockMaster, code)
    db.refresh(item)
    return item


@app.get("/meta/insight-cadence", response_model=InsightCadenceOut)
def insight_cadence():
    return insight_cadence_payload()


@app.get("/meta/stock-data-coverage")
def stock_data_coverage_status(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return stock_data_coverage(db)


@app.get("/meta/signal-data-quality")
def signal_data_quality(
    request: Request,
    response: Response,
    probe: bool = Query(
        default=False,
        description="외부 원천 API에 읽기 전용 형식 검사를 함께 수행합니다.",
    ),
    sample_code: str = Query(default="005930", min_length=6, max_length=7),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    if probe:
        _enforce_rate_limit(request, "signal_data_quality_probe", limit=5, window_seconds=60)
    try:
        normalized_code = _normalize_stock_code(sample_code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = signal_data_quality_status(db, settings)
    if probe:
        payload["api_probe"] = api_cache.get_or_set(
            ("signal_source_probe", normalized_code),
            300,
            lambda: probe_signal_source_apis(
                settings,
                sample_code=normalized_code,
            ),
        )
    return payload


@app.get("/meta/research-sources", response_model=list[ResearchSourceOut])
def research_sources(
    active_only: bool = Query(default=False),
):
    return research_source_payload(active_only=active_only)


@app.get("/meta/integrations", response_model=list[IntegrationMetaOut])
def integrations(
    configured_only: bool = Query(default=False),
):
    items = integration_payload(settings)
    if configured_only:
        items = [item for item in items if item["configured"]]
    return items


@app.get("/stock-logos/{code}.png")
def stock_logo(code: str, db: Session = Depends(get_db)):
    try:
        normalized = _normalize_stock_code(code)
    except ValueError:
        raise HTTPException(status_code=404, detail="Stock logo not found")
    manual_logo_path = MANUAL_STOCK_LOGO_DIR / f"{normalized}.png"
    if manual_logo_path.is_file():
        return FileResponse(
            manual_logo_path,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=2592000, stale-while-revalidate=86400",
                "X-Content-Type-Options": "nosniff",
                "X-Stock-Logo-Fallback": "false",
                "X-Stock-Logo-Source": "official-manual",
            },
        )
    if db.get(StockMaster, normalized) is None:
        raise HTTPException(status_code=404, detail="Stock logo not found")
    try:
        item = db.get(StockLogo, normalized)
        if not item or item.status != "ready" or not item.image_data:
            if settings.stock_logo_enabled:
                item = ensure_stock_logo(
                    db,
                    normalized,
                    timeout_seconds=settings.stock_logo_timeout_seconds,
                    missing_retry_days=settings.stock_logo_missing_retry_days,
                )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Stock logo not found") from exc
    if not item or item.status != "ready" or not item.image_data:
        raise HTTPException(status_code=404, detail="Stock logo not found")
    return Response(
        content=item.image_data,
        media_type=item.content_type or "image/png",
        headers={
            "Cache-Control": "public, max-age=2592000, stale-while-revalidate=86400",
            "X-Content-Type-Options": "nosniff",
            "X-Stock-Logo-Fallback": "false",
        },
    )


@app.get("/stocks", response_model=list[StockOut])
def stocks(
    market: Optional[str] = None,
    limit: int = Query(default=5000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    return list_stocks(db, market=market, limit=limit)


@app.get("/stocks/resolve", response_model=StockOut)
def resolve_stock(
    response: Response,
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    cleaned = query.strip()
    terms = _stock_query_terms(cleaned)
    code = _normalize_stock_code(cleaned)
    item = db.get(StockMaster, code)
    if item and not item.is_active:
        item = None
    if not item:
        item = _ensure_stock_master_from_naver(db, code)
    if not item:
        item = db.scalar(select(StockMaster).where(StockMaster.name == cleaned).limit(1))
        if item and not item.is_active:
            item = _ensure_stock_master_from_naver(db, item.code)
    if not item:
        external_code = api_cache.get_or_set(
            ("naver_stock_code_by_query", _normalize_stock_query(cleaned)),
            60 * 60,
            lambda: _fetch_naver_stock_code_by_query(cleaned),
        )
        if external_code:
            item = _ensure_stock_master_from_naver(db, str(external_code))
    if not item:
        candidates = list(
            db.scalars(
                select(StockMaster)
                .where(
                    StockMaster.is_active.is_(True),
                    or_(StockMaster.name.contains(cleaned), StockMaster.code.startswith(code)),
                )
                .order_by(StockMaster.market, StockMaster.code)
                .limit(5000)
            )
        )
        if not candidates:
            candidates = list(
                db.scalars(
                    select(StockMaster)
                    .where(StockMaster.is_active.is_(True))
                    .order_by(StockMaster.market, StockMaster.code)
                    .limit(5000)
                )
            )
        matches = [
            candidate
            for candidate in candidates
            if any(term in _normalize_stock_query(candidate.name) for term in terms)
            or code in _normalize_stock_code(candidate.code)
        ]
        market_caps = {
            code: price.market_cap or 0
            for code, price in latest_prices_by_codes(db, [candidate.code for candidate in matches]).items()
        }
        item = (
            sorted(matches, key=lambda candidate: _stock_search_sort_key(candidate, cleaned, market_caps))[0]
            if matches
            else None
        )
    if not item:
        raise HTTPException(status_code=404, detail="Stock not found")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return item


def _stock_search_sort_key(
    item: StockMaster,
    query: str,
    market_caps: Optional[dict[str, int]] = None,
) -> tuple[int, int, int, int, int, int, int, str]:
    cleaned = query.strip()
    normalized = _normalize_stock_query(cleaned)
    terms = _stock_query_terms(cleaned)
    code = _normalize_stock_code(cleaned)
    item_name = _normalize_stock_query(item.name)
    item_code = _normalize_stock_code(item.code)
    if item_code == code or item.name == cleaned or item_name == normalized:
        match_rank = 0
    elif any(item_name.startswith(term) for term in terms) or item.name.startswith(cleaned):
        match_rank = 1
    elif item_code.startswith(code):
        match_rank = 2
    elif any(term in item_name for term in terms):
        match_rank = 3
    else:
        match_rank = 4
    representative_rank = 0 if REPRESENTATIVE_STOCK_NAMES.get(normalized) == item.name else 1
    preferred_rank = 1 if item.name.endswith("우") or item.name.endswith("우B") or item.name.endswith("우C") else 0
    market_rank = 0 if item.market == "KOSPI" else 1 if item.market == "KOSDAQ" else 2
    special_rank = 1 if "스팩" in item.name.upper() or "SPAC" in item.name.upper() else 0
    market_cap = (market_caps or {}).get(item.code) or 0
    return (match_rank, representative_rank, preferred_rank, special_rank, market_rank, -market_cap, len(item.name), item.code)


@app.get("/stocks/search", response_model=list[StockOut])
def search_stocks(
    response: Response,
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cleaned = query.strip()
    if not cleaned:
        return []
    terms = _stock_query_terms(cleaned)
    code = _normalize_stock_code(cleaned)

    candidates = list(
        db.scalars(
            select(StockMaster)
            .where(
                StockMaster.is_active.is_(True),
                or_(StockMaster.name.contains(cleaned), StockMaster.code.startswith(code)),
            )
            .order_by(StockMaster.market, StockMaster.code)
            .limit(5000)
        )
    )
    if not candidates:
        candidates = [
            item
            for item in db.scalars(
                select(StockMaster)
                .where(StockMaster.is_active.is_(True))
                .order_by(StockMaster.market, StockMaster.code)
                .limit(5000)
            )
            if any(term in _normalize_stock_query(item.name) for term in terms) or code in _normalize_stock_code(item.code)
        ]

    exact_code = db.get(StockMaster, code)
    if exact_code and not exact_code.is_active:
        exact_code = _ensure_stock_master_from_naver(db, exact_code.code)
    exact_name = db.scalar(
        select(StockMaster)
        .where(StockMaster.name == cleaned)
        .limit(1)
    )
    if exact_name and not exact_name.is_active:
        exact_name = _ensure_stock_master_from_naver(db, exact_name.code)
    if exact_code:
        candidates.append(exact_code)
    if exact_name:
        candidates.append(exact_name)

    unique = {}
    for item in candidates:
        unique[item.code] = item

    market_caps = {
        code: price.market_cap or 0
        for code, price in latest_prices_by_codes(db, list(unique)).items()
    }
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return sorted(unique.values(), key=lambda item: _stock_search_sort_key(item, cleaned, market_caps))[:limit]


@app.get("/stocks/quotes")
async def stock_live_quotes(codes: str, response: Response):
    """Return public quotes in one response for WebSocket recovery."""
    try:
        normalized = _normalize_quote_code_list(codes.split(","))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not normalized:
        raise HTTPException(status_code=422, detail="At least one valid stock code is required")
    active_codes = await asyncio.to_thread(_active_stock_quote_codes, normalized)
    accepted = [code for code in normalized if code in active_codes]
    rejected = [code for code in normalized if code not in active_codes]
    payloads = [
        _stamp_quote_payload(payload)
        for payload in await _quote_payloads_for_codes(accepted)
    ]
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return {
        "type": "quotes",
        "as_of": datetime.now(KST).isoformat(),
        "items": payloads,
        "rejected_codes": rejected,
    }


@app.get("/stocks/{code}", response_model=StockOut)
def stock_detail(code: str, db: Session = Depends(get_db)):
    code = _normalize_stock_code(code)
    item = db.get(StockMaster, code)
    if not item or not item.is_active:
        item = _ensure_stock_master_from_naver(db, code)
    if not item:
        raise HTTPException(status_code=404, detail="Stock not found")
    return item


def _parse_decimal_value(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _parse_int_value(value: Any) -> Optional[int]:
    decimal_value = _parse_decimal_value(value)
    if decimal_value is None:
        return None
    return int(decimal_value)


def _parse_kis_business_date(value: Any) -> Optional[date]:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def _pick_quote_field(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _first_quote_row(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        value = value[0] if value else {}
    return value if isinstance(value, dict) else {}


def _apply_kis_sign(value: Optional[int | Decimal], sign: Any) -> Optional[int | Decimal]:
    if value is None:
        return None
    sign_value = str(sign or "").strip()
    if sign_value in {"4", "5"}:
        return -abs(value)
    if sign_value in {"1", "2"}:
        return abs(value)
    return value


def _change_rate_from_prices(price: Optional[int], base: Optional[int]) -> Optional[Decimal]:
    if price is None or base in (None, 0):
        return None
    return ((Decimal(price) - Decimal(base)) * Decimal("100") / Decimal(base)).quantize(Decimal("0.01"))


def _pre_market_accept_time(row: dict[str, Any]) -> Optional[str]:
    raw = str(_pick_quote_field(row, "aspr_acpt_hour", "stck_cntg_hour", "cntg_hour") or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 6:
        return None
    return f"{digits[0:2]}:{digits[2:4]}:{digits[4:6]}"


def _korea_quote_session(now: Optional[datetime] = None) -> dict[str, Any]:
    """Return the venue that owns the public display quote at this moment."""
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    else:
        current = current.astimezone(KST)
    # Daily index candles do not include today's session before the KRX opens,
    # so they cannot be used to decide whether the 08:00 NXT feed should be
    # queried. The venue feed itself remains the authority for an actual tick.
    session_open = current.weekday() < 5
    if not session_open:
        return {
            "market_session": "closed",
            "market_session_label": "장 마감",
            "market_venue": "KRX",
            "market_division": "J",
            "is_live": False,
        }

    current_time = current.time()
    if time(8, 0) <= current_time < time(8, 50):
        return {
            "market_session": "nxt_pre_market",
            "market_session_label": "NXT 프리마켓",
            "market_venue": "NXT",
            "market_division": "NX",
            "is_live": True,
        }
    if time(8, 50) <= current_time < time(9, 0):
        return {
            "market_session": "krx_opening_auction",
            "market_session_label": "KRX 시가 단일가",
            "market_venue": "KRX",
            "market_division": "J",
            "is_live": False,
        }
    if time(9, 0) <= current_time < time(9, 0, 30):
        return {
            "market_session": "krx_regular",
            "market_session_label": "KRX 정규장",
            "market_venue": "KRX",
            "market_division": "J",
            "is_live": True,
        }
    if time(9, 0, 30) <= current_time < time(15, 20):
        return {
            "market_session": "integrated_regular",
            "market_session_label": "통합 정규장",
            "market_venue": "INTEGRATED",
            "market_division": "UN",
            "is_live": True,
        }
    if time(15, 20) <= current_time <= time(15, 30):
        return {
            "market_session": "krx_regular",
            "market_session_label": "KRX 정규장",
            "market_venue": "KRX",
            "market_division": "J",
            "is_live": True,
        }
    if time(15, 30) < current_time < time(15, 40):
        return {
            "market_session": "nxt_after_market_wait",
            "market_session_label": "NXT 애프터마켓 준비",
            "market_venue": "NXT",
            "market_division": "NX",
            "is_live": False,
        }
    if time(15, 40) <= current_time < time(20, 0):
        return {
            "market_session": "nxt_after_market",
            "market_session_label": "NXT 애프터마켓",
            "market_venue": "NXT",
            "market_division": "NX",
            "is_live": True,
        }
    return {
        "market_session": "closed",
        "market_session_label": "장 마감",
        "market_venue": "KRX",
        "market_division": "J",
        "is_live": False,
    }


def _quote_session_fields(
    session: dict[str, Any],
    *,
    actual_market_division: str,
    trade_time: Optional[str] = None,
) -> dict[str, Any]:
    fields = dict(session)
    requested = str(session.get("market_division") or "J")
    actual = str(actual_market_division or "J")
    fields["market_division"] = actual
    if trade_time:
        fields["trade_time"] = re.sub(r"\D", "", str(trade_time)).zfill(6)[-6:]
    if actual == requested:
        return fields
    if session.get("market_session") == "nxt_pre_market":
        fields.update(
            {
                "market_session": "pre_market_reference",
                "market_session_label": "NXT 미지원 · KRX 기준가",
                "market_venue": "KRX",
                "is_live": False,
            }
        )
    elif session.get("market_session") in {"nxt_after_market", "nxt_after_market_wait"}:
        fields.update(
            {
                "market_session": "after_market_reference",
                "market_session_label": "NXT 미지원 · KRX 종가",
                "market_venue": "KRX",
                "is_live": False,
            }
        )
    elif requested == "UN":
        fields.update(
            {
                "market_session": "krx_regular",
                "market_session_label": "KRX 정규장",
                "market_venue": "KRX",
            }
        )
    return fields


def _decorate_extended_quote(
    quote: dict[str, Any],
    session: dict[str, Any],
    *,
    actual_market_division: str,
    trade_time: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> dict[str, Any]:
    quote.update(
        _quote_session_fields(
            session,
            actual_market_division=actual_market_division,
            trade_time=trade_time,
        )
    )
    if quote.get("market_session") == "nxt_pre_market":
        active_trade = bool((quote.get("volume") or 0) > 0 or quote.get("trade_time"))
        quote.update(
            {
                "pre_market_price": quote.get("price"),
                "pre_market_change_value": quote.get("change_value"),
                "pre_market_change_rate": quote.get("change_rate"),
                "pre_market_volume": quote.get("volume"),
                "pre_market_status": (
                    "NXT 프리마켓 실시간" if active_trade else "NXT 프리마켓 체결 대기"
                ),
                "pre_market_as_of": (
                    _pre_market_accept_time({"stck_cntg_hour": quote.get("trade_time")})
                    or (observed_at or datetime.now(KST)).astimezone(KST).strftime("%H:%M:%S")
                ),
            }
        )
    return quote


def _quote_poll_interval_seconds(current_time: Optional[time] = None) -> int:
    now = current_time or datetime.now(KST).time()
    if time(8, 0) <= now < time(20, 0):
        return 2
    return 8


def _fetch_pre_market_quote(code: str) -> dict[str, Any]:
    if not kis_rest_provider.is_configured():
        return {}
    try:
        payload = kis_rest_provider._get(
            "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
            "FHKST01010200",
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
            },
        )
    except Exception:
        return {}
    row = {
        **_first_quote_row(payload.get("output")),
        **_first_quote_row(payload.get("output1")),
        **_first_quote_row(payload.get("output2")),
    }
    if not row:
        return {}

    sign = _pick_quote_field(row, "antc_cntg_vrss_sign", "antc_vrss_sign", "prdy_vrss_sign")
    expected_price = _parse_int_value(_pick_quote_field(row, "antc_cnpr", "antc_cntg_prpr"))
    display_price = _parse_int_value(_pick_quote_field(row, "stck_prpr"))
    base_price = _parse_int_value(_pick_quote_field(row, "stck_sdpr", "prdy_clpr"))
    price = expected_price if expected_price not in (None, 0) else display_price
    change_value = _parse_int_value(_pick_quote_field(row, "antc_cntg_vrss", "antc_vrss", "prdy_vrss"))
    change_rate = _parse_decimal_value(_pick_quote_field(row, "antc_cntg_prdy_ctrt", "antc_prdy_ctrt", "prdy_ctrt"))
    volume = _parse_int_value(_pick_quote_field(row, "antc_vol", "antc_cnqn", "cntg_vol"))

    if price in (None, 0) and volume in (None, 0):
        return {}

    if expected_price in (None, 0) and display_price not in (None, 0) and base_price not in (None, 0):
        change_value = display_price - base_price
        change_rate = _change_rate_from_prices(display_price, base_price)
        sign = "2" if change_value > 0 else "5" if change_value < 0 else "3"

    signed_change_value = _apply_kis_sign(change_value, sign)
    signed_change_rate = _apply_kis_sign(change_rate, sign)
    status = "장전 예상체결" if expected_price not in (None, 0) else "장전 호가 대기"
    return {
        "pre_market_price": price,
        "pre_market_change_value": signed_change_value,
        "pre_market_change_rate": signed_change_rate,
        "pre_market_volume": volume,
        "pre_market_status": status,
        "pre_market_as_of": _pre_market_accept_time(row),
    }


def _pre_market_quote(code: str, now: Optional[datetime] = None) -> dict[str, Any]:
    current = now or datetime.now(KST)
    current_time = current.astimezone(KST).time() if current.tzinfo else current.time()
    if not (
        time(8, 50) <= current_time <= time(9, 5)
        or time(15, 20) <= current_time <= time(15, 45)
    ):
        return {}
    return _fetch_pre_market_quote(code)


def _enrich_pre_market_quote(
    payload: Optional[dict[str, Any]],
    code: str,
    now: Optional[datetime] = None,
) -> None:
    if not payload or not isinstance(payload.get("quote"), dict):
        return
    quote = payload["quote"]
    if quote.get("market_session") == "nxt_pre_market":
        _decorate_extended_quote(
            quote,
            _korea_quote_session(now),
            actual_market_division="NX",
            trade_time=quote.get("trade_time"),
            observed_at=now,
        )
        return
    quote.update(_pre_market_quote(code, now))


def _fetch_kis_current_quote(
    code: str,
    *,
    extended_hours: bool = False,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    if not kis_rest_provider.is_configured():
        return {}
    current = now or datetime.now(KST)
    session = (
        _korea_quote_session(current)
        if extended_hours
        else {
            "market_session": "krx_reference",
            "market_session_label": "KRX 기준",
            "market_venue": "KRX",
            "market_division": "J",
            "is_live": False,
        }
    )
    requested_market_division = (
        str(session.get("market_division") or "J") if extended_hours else "J"
    )
    actual_market_division = requested_market_division
    try:
        row = kis_rest_provider._request_current_price(
            code,
            market_division=requested_market_division,
        )
    except Exception:
        row = {}
    if not isinstance(row, dict):
        row = {}
    price = _parse_int_value(_pick_quote_field(row, "stck_prpr"))
    if price in (None, 0) and requested_market_division != "J":
        actual_market_division = "J"
        try:
            row = kis_rest_provider._request_current_price(code, market_division="J")
        except Exception:
            row = {}
        if not isinstance(row, dict):
            row = {}
    sign = _pick_quote_field(row, "prdy_vrss_sign")
    price = _parse_int_value(_pick_quote_field(row, "stck_prpr"))
    if price in (None, 0):
        return {}
    change_value = _apply_kis_sign(_parse_int_value(_pick_quote_field(row, "prdy_vrss")), sign)
    change_rate = _apply_kis_sign(_parse_decimal_value(_pick_quote_field(row, "prdy_ctrt")), sign)
    observed_trade_date = _parse_kis_business_date(
        _pick_quote_field(row, "stck_bsop_date", "bsop_date")
    )
    quote = {
        "trade_date": observed_trade_date
        or (current.astimezone(KST).date() if current.tzinfo else current.date()),
        "trade_date_verified": observed_trade_date is not None,
        "quote_source": "kis_rest",
        "observed_at": current,
        "price": price,
        "open": _parse_int_value(_pick_quote_field(row, "stck_oprc")),
        "high": _parse_int_value(_pick_quote_field(row, "stck_hgpr")),
        "low": _parse_int_value(_pick_quote_field(row, "stck_lwpr")),
        "change_value": change_value,
        "change_rate": change_rate,
        "volume": _parse_int_value(_pick_quote_field(row, "acml_vol")),
        "trading_value": _parse_int_value(_pick_quote_field(row, "acml_tr_pbmn")),
    }
    if extended_hours:
        return _decorate_extended_quote(
            quote,
            session,
            actual_market_division=actual_market_division,
            trade_time=_pick_quote_field(row, "stck_cntg_hour", "cntg_hour"),
            observed_at=current,
        )
    quote.update(
        {
            "market_session": str(session.get("market_session") or "krx_reference"),
            "market_session_label": str(session.get("market_session_label") or "KRX 기준"),
            "market_venue": "KRX",
            "market_division": "J",
            "is_live": bool(session.get("is_live")),
        }
    )
    return quote


def _fetch_naver_current_quote(code: str) -> dict[str, Any]:
    snapshot = _naver_snapshot(code, refresh=True)
    price = _parse_int_value(snapshot.get("price"))
    if price in (None, 0):
        return {}
    return {
        "trade_date": datetime.now(KST).date(),
        "price": price,
        "change_value": _parse_int_value(snapshot.get("change_value")),
        "change_rate": _parse_decimal_value(snapshot.get("change_rate_abs")),
        "volume": _parse_int_value(snapshot.get("volume")),
        "trading_value": _parse_int_value(snapshot.get("trading_value")),
    }


def _fetch_uncached_current_quote(
    code: str,
    *,
    extended_hours: bool = False,
    now: Optional[datetime] = None,
) -> tuple[dict[str, Any], str]:
    if extended_hours or now is not None:
        kis_quote = _fetch_kis_current_quote(
            code,
            extended_hours=extended_hours,
            now=now,
        )
    else:
        # Keep the long-standing KRX-only call shape for internal analytics and
        # existing integrations that replace the provider with a one-argument
        # callable. Extended-hours display paths opt in explicitly above.
        kis_quote = _fetch_kis_current_quote(code)
    if kis_quote:
        return kis_quote, "kis_rest"
    naver_quote = _fetch_naver_current_quote(code)
    if naver_quote:
        if extended_hours:
            session = _korea_quote_session(now)
            naver_quote.update(
                _quote_session_fields(
                    session,
                    actual_market_division="J",
                )
            )
            naver_quote["is_live"] = False
        return naver_quote, "naver_finance"
    return {}, "stored_daily_price"


def _quote_trade_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _live_quote_can_override_stored_close(
    live_quote: Optional[dict[str, Any]],
    stored_trade_date: Optional[date],
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Fail closed when a provider quote cannot be tied to a real session.

    KIS occasionally omits ``stck_bsop_date`` from the current-price response.
    The adapter then labels the observation with the request date so live
    sessions can still work.  That synthetic date must not replace Friday's
    completed candle after midnight or during a weekend.  Live NXT/KRX quotes,
    explicitly dated observations, and same-session references remain valid.
    """
    if not live_quote or _parse_int_value(live_quote.get("price")) in (None, 0):
        return False
    current = now or datetime.now(KST)
    current = (
        current.replace(tzinfo=KST)
        if current.tzinfo is None
        else current.astimezone(KST)
    )
    observed_trade_date = _quote_trade_date(live_quote.get("trade_date"))
    if observed_trade_date is None:
        return False
    if live_quote.get("is_live") is True:
        return current.weekday() < 5 and observed_trade_date == current.date()
    if live_quote.get("trade_date_verified") is True:
        return stored_trade_date is None or observed_trade_date >= stored_trade_date
    return stored_trade_date is not None and observed_trade_date == stored_trade_date


def _live_period_return(price: Optional[int], reference: Optional[int]) -> Optional[Decimal]:
    if price in (None, 0) or reference in (None, 0):
        return None
    return ((Decimal(price) - Decimal(reference)) * Decimal("100") / Decimal(reference)).quantize(Decimal("0.01"))


def _apply_live_quote_to_dashboard(
    payload: Optional[dict[str, Any]],
    code: str,
    db: Session,
    live_quote: dict[str, Any],
    source: str,
    *,
    as_of: Optional[datetime] = None,
) -> bool:
    if not payload or not isinstance(payload.get("quote"), dict):
        return False
    if not live_quote:
        return False

    rows = list(
        reversed(
            list(
                db.scalars(
                    select(DailyPrice)
                    .where(DailyPrice.code == code)
                    .order_by(DailyPrice.trade_date.desc())
                    .limit(64)
                )
            )
        )
    )
    latest_trade_date = rows[-1].trade_date if rows else _quote_trade_date(
        payload["quote"].get("trade_date")
    )
    current_time = as_of or datetime.now(KST)
    if not _live_quote_can_override_stored_close(
        live_quote,
        latest_trade_date,
        now=current_time,
    ):
        return False
    payload["quote"].update({key: value for key, value in live_quote.items() if value is not None})
    payload["source"] = source
    payload["as_of"] = current_time

    momentum = payload.get("momentum")
    if isinstance(momentum, dict):
        one_month_reference = rows[-22].close if len(rows) > 21 else None
        three_month_reference = rows[-64].close if len(rows) > 63 else None
        momentum["one_month_return"] = _live_period_return(live_quote["price"], one_month_reference)
        momentum["three_month_return"] = _live_period_return(live_quote["price"], three_month_reference)
        if live_quote.get("trading_value") is not None:
            momentum["latest_trading_value"] = live_quote["trading_value"]
    return True


def _enrich_uncached_kis_quote(payload: Optional[dict[str, Any]], code: str, db: Session) -> bool:
    live_quote, source = _fetch_uncached_current_quote(code, extended_hours=True)
    return _apply_live_quote_to_dashboard(payload, code, db, live_quote, source)


def _enrich_cached_live_quote(payload: Optional[dict[str, Any]], code: str, db: Session) -> bool:
    cached = live_quote_cache.get(("live_quote", code))
    if not isinstance(cached, dict) or not isinstance(cached.get("quote"), dict):
        return False
    raw_as_of = cached.get("as_of")
    try:
        as_of = datetime.fromisoformat(str(raw_as_of)) if raw_as_of else None
    except (TypeError, ValueError):
        as_of = None
    return _apply_live_quote_to_dashboard(
        payload,
        code,
        db,
        dict(cached["quote"]),
        str(cached.get("source") or "live_quote_cache"),
        as_of=as_of,
    )


def _validate_stock_dashboard_snapshot(payload: Any) -> dict[str, Any]:
    return StockDashboardOut.model_validate(payload).model_dump(mode="json")


def _upgrade_cached_chart_patterns(
    payload: dict[str, Any],
    code: str,
    db: Session,
) -> bool:
    """Replace only stale chart-pattern output while preserving the complete snapshot."""
    analysis = payload.get("chart_analysis")
    if not isinstance(analysis, dict):
        return False
    try:
        current_version = int(analysis.get("pattern_schema_version") or 0)
    except (TypeError, ValueError):
        current_version = 0
    if current_version >= CHART_PATTERN_SCHEMA_VERSION:
        return False
    price_rows = list(
        db.scalars(
            select(DailyPrice)
            .where(DailyPrice.code == code, DailyPrice.close.is_not(None))
            .order_by(desc(DailyPrice.trade_date))
            .limit(250)
        )
    )
    price_rows.reverse()
    analysis["patterns"] = detect_chart_patterns(price_rows)
    analysis["pattern_schema_version"] = CHART_PATTERN_SCHEMA_VERSION
    return True


def _stock_dashboard_snapshot_key(code: str) -> str:
    return f"{STOCK_DASHBOARD_SNAPSHOT_PREFIX}{code}"


def _queue_complete_snapshot_refresh(db: Session, snapshot_key: str) -> None:
    request_complete_snapshot_refresh(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    if complete_snapshot_runtime is not None:
        complete_snapshot_runtime.wake()


def _queue_cold_snapshot_or_503(
    db: Session,
    snapshot_key: str,
    *,
    detail: str,
) -> None:
    """Hand a cold shared payload to the collector without fabricating data.

    A web-only process must never fall back to a synchronous provider call. The
    retryable error keeps an incomplete/empty payload out of both the shared
    snapshot and the client cache while the collector builds the first complete
    value.
    """

    try:
        _queue_complete_snapshot_refresh(db, snapshot_key)
    except Exception:
        logger.exception("Complete snapshot cold-start queue failed key=%s", snapshot_key)
    raise HTTPException(
        status_code=503,
        detail=detail,
        headers={"Retry-After": "1"},
    )


def _publish_cold_snapshot_or_read_winner(
    db: Session,
    snapshot_key: str,
    payload: Any,
    **publish_options: Any,
):
    """Publish a cold payload or return the complete payload that won a race."""

    try:
        return publish_complete_snapshot(
            db,
            snapshot_key,
            payload,
            **publish_options,
        )
    except SnapshotPublishConflictError as exc:
        winner = get_complete_snapshot(
            db,
            snapshot_key,
            schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
        )
        if winner is not None:
            return winner
        # An active collector lease can own a cold placeholder without having
        # published its first value yet.  The candidate has already passed the
        # validator and JSON normalization inside publish(); serve it only to
        # this request while leaving the collector's lease/queue untouched.
        if exc.attempted_snapshot is not None:
            return exc.attempted_snapshot
        raise


def _build_stock_dashboard_snapshot(db: Session, snapshot_key: str) -> SnapshotBuild:
    code = _normalize_stock_code(snapshot_key.removeprefix(STOCK_DASHBOARD_SNAPSHOT_PREFIX))
    stock = _resolve_stock_master(db, code)
    if not stock:
        raise LookupError(f"Stock not found: {code}")
    try:
        # Respect the profile service's 30-day freshness window. Forcing the
        # DART company/list/document chain on every 120-second dashboard refresh
        # can block the stock snapshot lane for tens of seconds.
        ensure_company_profile(
            db,
            stock,
            refresh=False,
            include_business_report=False,
        )
    except Exception as exc:
        db.rollback()
        logger.warning("Company profile refresh failed for %s: %s", code, exc)
    try:
        _ensure_stock_research_backfill(db, code)
    except Exception as exc:
        logger.warning("Stock research backfill failed for %s: %s", code, exc)
    ensure_stock_price_history(db, code)
    payload = build_stock_dashboard(db, code, refresh_live=True, allow_external=True)
    if not payload:
        raise LookupError(f"Stock dashboard not found: {code}")
    return SnapshotBuild(
        payload=payload,
        fresh_for_seconds=STOCK_DASHBOARD_TTL_SECONDS,
        captured_at=payload.get("as_of"),
        validator=_validate_stock_dashboard_snapshot,
    )


def _resolve_stock_master(db: Session, code: str) -> Optional[StockMaster]:
    stock = db.get(StockMaster, code)
    if not stock or not stock.is_active:
        stock = _ensure_stock_master_from_naver(db, code)
    return stock


def _ensure_stock_research_backfill(db: Session, code: str) -> int:
    """Fill a stock's report history once when the global feed is incomplete."""
    key = ("stock_research_backfill", code)
    cached = stock_research_refresh_cache.get(key)
    if cached is not None:
        return int(cached)
    count = ensure_stock_research_reports(
        db,
        code,
        days_back=180,
        max_pages=3,
        include_detail=True,
    )
    stock_research_refresh_cache.set(key, count, 6 * 60 * 60)
    return count


@app.get("/stocks/{code}/dashboard", response_model=StockDashboardOut)
def stock_dashboard(
    code: str,
    response: Response,
    refresh: bool = Query(default=False),
    include_profile: bool = Query(default=True),
    include_live: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    snapshot_key = _stock_dashboard_snapshot_key(code)
    stable_only = not include_profile and not include_live
    stock = db.get(StockMaster, code)
    if not stock or not stock.is_active:
        stock = None if stable_only else _ensure_stock_master_from_naver(db, code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    warming_shell = False
    complete = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    if complete is None:
        if stable_only:
            # Always serve the latency-sensitive detail shell from indexed DB
            # data, including in a web-only process. It is never published as a
            # "complete" snapshot; the collector enriches and atomically
            # publishes the full payload in the background.
            payload = build_stock_dashboard(db, code, allow_external=False)
            if payload:
                warming_shell = True
                _queue_complete_snapshot_refresh(db, snapshot_key)
        else:
            if not settings.runs_collectors():
                _queue_cold_snapshot_or_503(
                    db,
                    snapshot_key,
                    detail="Complete stock dashboard snapshot is being prepared",
                )
            # Preserve the existing complete cold-start behavior for callers
            # that explicitly request profile or live enrichment.
            if include_profile:
                try:
                    ensure_company_profile(db, stock, refresh=refresh)
                except Exception as exc:
                    db.rollback()
                    logger.warning("Company profile refresh failed for %s: %s", code, exc)
            try:
                _ensure_stock_research_backfill(db, code)
            except Exception as exc:
                logger.warning("Stock research backfill failed for %s: %s", code, exc)
            if refresh:
                ensure_stock_price_history(db, code)
            payload = build_stock_dashboard(db, code, allow_external=True)
            if payload:
                published = _publish_cold_snapshot_or_read_winner(
                    db,
                    snapshot_key,
                    payload,
                    fresh_for_seconds=STOCK_DASHBOARD_TTL_SECONDS,
                    schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
                    captured_at=payload.get("as_of"),
                    validator=_validate_stock_dashboard_snapshot,
                )
                payload = published.payload
    else:
        payload = complete.payload
    if refresh or (complete is not None and not complete.is_fresh):
        _queue_complete_snapshot_refresh(db, snapshot_key)
    if not payload:
        raise HTTPException(status_code=404, detail="Stock not found")
    payload = deepcopy(payload)
    if _upgrade_cached_chart_patterns(payload, code, db):
        _queue_complete_snapshot_refresh(db, snapshot_key)
    if warming_shell:
        # Let the client paint the stored shell immediately, but do not let an
        # incomplete response masquerade as a cacheable complete snapshot.
        payload["source"] = "stored_database_warming"
        response.headers["Cache-Control"] = "no-store"
    elif include_live:
        if not _enrich_cached_live_quote(payload, code, db):
            _enrich_uncached_kis_quote(payload, code, db)
        _enrich_pre_market_quote(payload, code)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    else:
        response.headers["Cache-Control"] = "private, max-age=60"
    return payload


@app.get(
    "/stocks/{code}/sector-operating-margins",
    response_model=StockSectorOperatingMarginComparisonOut,
)
def stock_sector_operating_margins(
    code: str,
    response: Response,
    limit: int = Query(default=5, ge=2, le=8),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    key = ("stock_sector_operating_margins", code, limit)
    payload = api_cache.get_or_set(
        key,
        SECTOR_MARGIN_COMPARISON_TTL_SECONDS,
        lambda: build_sector_margin_comparison(db, code, limit=limit),
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    response.headers["Cache-Control"] = "private, max-age=3600"
    return payload


@app.get("/stocks/{code}/sga-analysis", response_model=StockSgaAnalysisOut)
def stock_sga_analysis(
    code: str,
    response: Response,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    key = ("stock_sga_analysis", code)
    if refresh:
        payload = build_sga_analysis(db, code, settings=settings)
        if payload is not None:
            api_cache.set(key, payload, SGA_ANALYSIS_TTL_SECONDS)
    else:
        payload = api_cache.get_or_set(
            key,
            SGA_ANALYSIS_TTL_SECONDS,
            lambda: build_sga_analysis(db, code, settings=settings),
        )
    if payload is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    response.headers["Cache-Control"] = "no-store" if refresh else "private, max-age=3600"
    return payload


@app.get("/stocks/{code}/x-feed", response_model=StockXFeedOut)
def stock_x_feed(
    code: str,
    response: Response,
    limit: int = Query(default=20, ge=1, le=50),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    stock = db.get(StockMaster, code)
    if not stock:
        stock = _ensure_stock_master_from_naver(db, code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    key = ("stock_x_feed", code, limit)
    if refresh:
        payload = build_stock_x_feed(db, stock, settings, limit=limit, refresh=True)
        api_cache.set(key, payload, max(30, settings.x_feed_cache_seconds))
    else:
        payload = api_cache.get_or_set(
            key,
            max(30, settings.x_feed_cache_seconds),
            lambda: build_stock_x_feed(db, stock, settings, limit=limit),
        )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return payload


@app.get("/stocks/{code}/community-feed", response_model=StockCommunityFeedOut)
def stock_community_feed(
    code: str,
    response: Response,
    limit: int = Query(default=12, ge=1, le=20),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    stock = db.get(StockMaster, code)
    if not stock:
        stock = _ensure_stock_master_from_naver(db, code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    key = (
        "stock_community_feed",
        code,
        limit,
        bool(settings.threads_feed_enabled and settings.threads_access_token),
    )
    payload = api_cache.get_or_set(
        key,
        max(30, settings.threads_feed_cache_seconds),
        lambda: build_stock_community_feed(
            stock,
            settings,
            limit=limit,
            timeout_seconds=settings.threads_feed_timeout_seconds,
        ),
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return payload


@app.get("/stocks/{code}/etf-profile", response_model=StockEtfProfileOut)
def stock_etf_profile(
    code: str,
    response: Response,
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    stock = db.get(StockMaster, code)
    if not stock or not stock.is_active:
        stock = _ensure_stock_master_from_naver(db, code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    likely_etf = is_likely_etf_name(stock.name)
    complete = (
        get_complete_snapshot(
            db,
            ETF_HOLDINGS_SNAPSHOT_KEY,
            schema_version=ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION,
        )
        if likely_etf
        else None
    )
    snapshot_items = (
        complete.payload.get("items")
        if complete is not None
        and isinstance(complete.payload, dict)
        and isinstance(complete.payload.get("items"), dict)
        else {}
    )
    holdings_snapshot = snapshot_items.get(stock.code)
    if (
        likely_etf
        and settings.etf_holdings_snapshot_enabled
        and _etf_holdings_snapshot_due(complete)
    ):
        request_complete_snapshot_refresh(
            db,
            ETF_HOLDINGS_SNAPSHOT_KEY,
            schema_version=ETF_HOLDINGS_SNAPSHOT_SCHEMA_VERSION,
        )
        if complete_snapshot_runtime is not None:
            complete_snapshot_runtime.wake()
    payload = build_etf_profile(
        stock.code,
        stock.name,
        stock.isin,
        holdings_snapshot=holdings_snapshot,
    )
    response.headers["Cache-Control"] = "private, max-age=900, stale-while-revalidate=900"
    response.headers["X-ETF-Holdings-Source"] = (
        "scheduled-snapshot" if holdings_snapshot else "live-fallback"
    )
    return payload


@app.get("/stocks/{code}/home-context", response_model=StockHomeContextOut)
def stock_home_context(
    code: str,
    response: Response,
    flow_limit: int = Query(default=1500, ge=1, le=5000),
    research_limit: int = Query(default=100, ge=1, le=200),
    disclosure_limit: int = Query(default=30, ge=1, le=200),
    news_limit: int = Query(default=60, ge=1, le=200),
    community_limit: int = Query(default=12, ge=1, le=20),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    snapshot_key = _stock_home_context_snapshot_key(
        code,
        flow_limit=flow_limit,
        research_limit=research_limit,
        disclosure_limit=disclosure_limit,
        news_limit=news_limit,
        community_limit=community_limit,
    )
    complete = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    if complete is None:
        if not settings.runs_collectors():
            _queue_cold_snapshot_or_503(
                db,
                snapshot_key,
                detail="Complete stock context snapshot is being prepared",
            )
        stock = _resolve_stock_master(db, code)
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        payload = _build_stock_home_context_payload(
            db,
            stock,
            flow_limit=flow_limit,
            research_limit=research_limit,
            disclosure_limit=disclosure_limit,
            news_limit=news_limit,
            community_limit=community_limit,
            refresh_external=True,
        )
        published = _publish_cold_snapshot_or_read_winner(
            db,
            snapshot_key,
            payload,
            fresh_for_seconds=STOCK_HOME_CONTEXT_TTL_SECONDS,
            schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
            captured_at=payload.get("as_of"),
            validator=_validate_stock_home_context_snapshot,
        )
        payload = published.payload
    else:
        payload = complete.payload
        if not complete.is_fresh:
            _queue_complete_snapshot_refresh(db, snapshot_key)
    response.headers["Cache-Control"] = "private, max-age=120"
    return payload


def _stock_home_context_snapshot_key(
    code: str,
    *,
    flow_limit: int,
    research_limit: int,
    disclosure_limit: int,
    news_limit: int,
    community_limit: int,
) -> str:
    threads_enabled = int(bool(settings.threads_feed_enabled and settings.threads_access_token))
    return (
        f"{STOCK_HOME_CONTEXT_SNAPSHOT_PREFIX}{code}:{flow_limit}:{research_limit}:"
        f"{disclosure_limit}:{news_limit}:{community_limit}:{threads_enabled}"
    )


def _validate_stock_home_context_snapshot(payload: Any) -> dict[str, Any]:
    candidate = StockHomeContextOut.model_validate(payload).model_dump(mode="json")
    if candidate["community"]["code"] != candidate["code"]:
        raise ValueError("Stock context community code does not match the stock")
    providers = candidate["community"]["providers"]
    provider_keys = [str(provider.get("key") or "") for provider in providers]
    if not provider_keys or any(not key for key in provider_keys):
        raise ValueError("Stock context must retain its community provider slots")
    if len(provider_keys) != len(set(provider_keys)):
        raise ValueError("Stock context community provider slots must be unique")
    return candidate


def _preserve_stock_home_context_complete_sections(
    previous: Optional[dict[str, Any]],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Keep prior evidence when a transient source returns no replacement rows."""

    if not isinstance(previous, dict):
        return candidate
    for section in ("flows", "research_reports", "disclosures", "news_items"):
        old_items = previous.get(section)
        new_items = candidate.get(section)
        if isinstance(old_items, list) and old_items and isinstance(new_items, list) and not new_items:
            candidate[section] = deepcopy(old_items)

    old_community = previous.get("community")
    new_community = candidate.get("community")
    if not isinstance(old_community, dict) or not isinstance(new_community, dict):
        return candidate
    old_providers = {
        str(provider.get("key") or ""): provider
        for provider in old_community.get("providers") or []
        if isinstance(provider, dict)
    }
    for provider in new_community.get("providers") or []:
        if not isinstance(provider, dict) or provider.get("configured") is not False:
            continue
        old_provider = old_providers.get(str(provider.get("key") or ""))
        if old_provider and old_provider.get("items") and not provider.get("items"):
            provider["items"] = deepcopy(old_provider["items"])
    return candidate


def _build_stock_home_context_payload(
    db: Session,
    stock: StockMaster,
    *,
    flow_limit: int,
    research_limit: int,
    disclosure_limit: int,
    news_limit: int,
    community_limit: int,
    refresh_external: bool,
) -> dict[str, object]:
    if refresh_external:
        _refresh_stock_investor_flow_if_stale(db, stock.code)
        _refresh_stock_disclosure_window(db, stock.code)
        try:
            _ensure_stock_research_backfill(db, stock.code)
        except Exception as exc:
            logger.warning("Stock research backfill failed for %s: %s", stock.code, exc)
    return {
        "code": stock.code,
        "name": stock.name,
        "as_of": datetime.utcnow(),
        "flows": [
            InvestorFlowOut.model_validate(item).model_dump(mode="json")
            for item in db.scalars(
                select(InvestorFlow)
                .where(InvestorFlow.code == stock.code)
                .order_by(desc(InvestorFlow.trade_date), InvestorFlow.investor_type)
                .limit(flow_limit)
            )
        ],
        "research_reports": [
            ResearchReportOut.model_validate(item).model_dump(mode="json")
            for item in latest_research_reports(db, limit=research_limit, stock_code=stock.code)
        ],
        "disclosures": [
            DisclosureItemOut.model_validate(item).model_dump(mode="json")
            for item in latest_disclosures(db, limit=disclosure_limit, stock_code=stock.code)
        ],
        "news_items": stock_news_item_payloads(db, stock.code, limit=news_limit),
        "community": build_stock_community_feed(
            stock,
            settings,
            limit=community_limit,
            timeout_seconds=settings.threads_feed_timeout_seconds,
        ),
    }


def _build_stock_home_context_snapshot(db: Session, snapshot_key: str) -> SnapshotBuild:
    encoded = snapshot_key.removeprefix(STOCK_HOME_CONTEXT_SNAPSHOT_PREFIX)
    parts = encoded.split(":")
    if len(parts) != 7:
        raise ValueError(f"Invalid stock home context snapshot key: {snapshot_key}")
    code = _normalize_stock_code(parts[0])
    flow_limit, research_limit, disclosure_limit, news_limit, community_limit = map(int, parts[1:6])
    stock = _resolve_stock_master(db, code)
    if not stock:
        raise LookupError(f"Stock not found: {code}")
    previous = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    payload = _build_stock_home_context_payload(
        db,
        stock,
        flow_limit=flow_limit,
        research_limit=research_limit,
        disclosure_limit=disclosure_limit,
        news_limit=news_limit,
        community_limit=community_limit,
        refresh_external=True,
    )
    payload = _preserve_stock_home_context_complete_sections(
        previous.payload if previous is not None else None,
        payload,
    )
    return SnapshotBuild(
        payload=payload,
        fresh_for_seconds=STOCK_HOME_CONTEXT_TTL_SECONDS,
        captured_at=payload.get("as_of"),
        validator=_validate_stock_home_context_snapshot,
    )


def _json_ready(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _quote_observed_datetime(payload: dict[str, object]) -> datetime:
    quote = payload.get("quote") if isinstance(payload.get("quote"), dict) else {}
    raw = payload.get("observed_at") or quote.get("observed_at") or payload.get("as_of")
    if isinstance(raw, datetime):
        observed = raw
    else:
        try:
            observed = datetime.fromisoformat(str(raw or "").replace("Z", "+00:00"))
        except ValueError:
            observed = datetime.now(KST)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=KST)
    return observed.astimezone(KST)


def _stamp_quote_payload(payload: dict[str, object]) -> dict[str, object]:
    result = deepcopy(payload)
    code = str(result.get("code") or "")
    observed = _quote_observed_datetime(result)
    published = datetime.now(KST)
    with quote_stream_metadata_lock:
        current_sequence = int(quote_stream_sequences.get(code, 0))
        supplied_sequence = result.get("sequence")
        try:
            sequence = int(supplied_sequence) if supplied_sequence is not None else 0
        except (TypeError, ValueError):
            sequence = 0
        # A supplied sequence may come from an older cached frame.  Public
        # publications must never repeat or regress the process-local sequence.
        sequence = max(current_sequence + 1, sequence)
        quote_stream_sequences[code] = sequence
    result.update(
        {
            "sequence": sequence,
            "observed_at": observed.isoformat(),
            "published_at": published.isoformat(),
        }
    )
    return result


def _quote_payload_is_stale(payload: dict[str, object]) -> bool:
    code = str(payload.get("code") or "")
    if not code or payload.get("type") != "quote":
        return False
    observed_timestamp = _quote_observed_datetime(payload).timestamp()
    with quote_stream_metadata_lock:
        previous = quote_stream_last_observed_at.get(code)
        if previous is not None and observed_timestamp <= previous:
            return True
        quote_stream_last_observed_at[code] = observed_timestamp
    return False


def _mark_quote_published(payload: dict[str, object]) -> None:
    code = str(payload.get("code") or "")
    if not code:
        return
    with quote_stream_metadata_lock:
        quote_stream_last_observed_at[code] = max(
            quote_stream_last_observed_at.get(code, float("-inf")),
            _quote_observed_datetime(payload).timestamp(),
        )
        quote_stream_last_published_at[code] = time_module.monotonic()


def _stock_quote_stream_payload_uncached(code: str) -> Optional[dict[str, object]]:
    interval_seconds = _quote_poll_interval_seconds()
    current_time = datetime.now(KST)
    with SessionLocal() as db:
        normalized = _normalize_stock_code(code)
        stock = db.get(StockMaster, normalized)
        if not stock:
            stock = _ensure_stock_master_from_naver(db, normalized)
        if not stock:
            return None

        recent_prices = list(
            db.scalars(
                select(DailyPrice)
                .where(DailyPrice.code == normalized)
                .order_by(DailyPrice.trade_date.desc())
                .limit(2)
            )
        )
        latest = recent_prices[0] if recent_prices else None
        previous = recent_prices[1] if len(recent_prices) > 1 else None
        quote: dict[str, object] = {
            "trade_date": latest.trade_date if latest else None,
            "price": latest.close if latest else None,
            "change_value": None,
            "change_rate": None,
            "volume": latest.volume if latest else None,
            "trading_value": latest.trading_value if latest else None,
            "market_cap": latest.market_cap if latest else None,
        }
        if latest and previous and latest.close is not None and previous.close not in (None, 0):
            quote["change_value"] = latest.close - previous.close
            quote["change_rate"] = _change_rate_from_prices(latest.close, previous.close)

        live_quote, source = _fetch_uncached_current_quote(
            normalized,
            extended_hours=True,
            now=current_time,
        )
        live_quote_is_safe = _live_quote_can_override_stored_close(
            live_quote,
            latest.trade_date if latest else None,
            now=current_time,
        )
        as_of = (
            current_time
            if live_quote_is_safe
            else datetime.combine(latest.trade_date, time(15, 30), tzinfo=KST)
            if latest
            else current_time
        )
        if live_quote_is_safe:
            quote.update({key: value for key, value in live_quote.items() if value is not None})
        else:
            source = "stored_daily_price"
            quote.update(_korea_quote_session(current_time))
        container = {"quote": quote}
        _enrich_pre_market_quote(container, normalized, current_time)
        return _json_ready(
            {
                "type": "quote",
                "code": normalized,
                "name": stock.name,
                "market": stock.market,
                "as_of": as_of,
                "source": source,
                "interval_seconds": interval_seconds,
                "quote": quote,
            }
        )


def _stock_quote_stream_payload(code: str) -> Optional[dict[str, object]]:
    normalized = _normalize_stock_code(code)
    return live_quote_cache.get_or_set(
        ("live_quote", normalized),
        1,
        lambda: _stock_quote_stream_payload_uncached(normalized),
    )


async def _stock_quote_stream_payload_async(code: str) -> Optional[dict[str, object]]:
    """Fetch one public quote once per process even during a reconnect surge."""
    normalized = _normalize_stock_code(code)
    cached = live_quote_cache.get(("live_quote", normalized))
    if cached is not None:
        return cached  # type: ignore[return-value]

    async with live_quote_async_lock:
        task = live_quote_async_tasks.get(normalized)
        if task is None or task.done():
            async def fetch() -> Optional[dict[str, object]]:
                async with live_quote_fetch_semaphore:
                    return await asyncio.to_thread(_stock_quote_stream_payload, normalized)

            task = asyncio.create_task(fetch())
            live_quote_async_tasks[normalized] = task
    try:
        return await asyncio.shield(task)
    finally:
        if task.done():
            async with live_quote_async_lock:
                if live_quote_async_tasks.get(normalized) is task:
                    live_quote_async_tasks.pop(normalized, None)


async def _quote_payloads_for_codes(codes: list[str]) -> list[dict[str, object]]:
    ordered = list(dict.fromkeys(codes))
    if not ordered:
        return []
    payloads = await asyncio.gather(
        *(_stock_quote_stream_payload_async(code) for code in ordered),
        return_exceptions=True,
    )
    return [
        payload
        for payload in payloads
        if isinstance(payload, dict) and payload.get("type") == "quote"
    ]


async def _send_polling_quote(websocket: WebSocket, code: str) -> bool:
    payload = await _stock_quote_stream_payload_async(code)
    if payload is None:
        await websocket.send_json({"type": "error", "message": "Stock quote not found"})
        return False
    stamped = _stamp_quote_payload(payload)
    _mark_quote_published(stamped)
    await websocket.send_json(stamped)
    return True


def _kis_realtime_payload(
    code: str,
    tick: dict[str, object],
    *,
    now: Optional[datetime] = None,
) -> dict[str, object]:
    current = now or datetime.now(KST)
    session = _korea_quote_session(current)
    quote = {
        "trade_date": current.astimezone(KST).date() if current.tzinfo else current.date(),
        "price": tick.get("price"),
        "change_value": tick.get("change_value"),
        "change_rate": tick.get("change_rate"),
        "trade_volume": tick.get("trade_volume"),
        "volume": tick.get("volume"),
        "trading_value": tick.get("trading_value"),
        "market_cap": None,
    }
    _decorate_extended_quote(
        quote,
        session,
        actual_market_division=str(session.get("market_division") or "J"),
        trade_time=str(tick.get("trade_time") or ""),
        observed_at=current,
    )
    return _json_ready(
        {
            "type": "quote",
            "code": code,
            "as_of": current,
            "source": "kis_realtime",
            "interval_seconds": 0,
            "quote": quote,
        }
    )


def _kis_status_payload(code: str, status: str, message: str) -> dict[str, object]:
    return {
        "type": "status",
        "code": code,
        "source": "kis_realtime",
        "status": status,
        "message": message,
    }


async def _fanout_quote_payload(
    code: str,
    payload: dict[str, object],
) -> Optional[dict[str, object]]:
    queues = list(kis_quote_subscribers.get(code, set()))
    if not queues:
        return None
    outgoing = payload
    if payload.get("type") == "quote":
        if _quote_payload_is_stale(payload):
            _increment_quote_stream_metric("stale_quotes_suppressed")
            return None
        unstamped = dict(payload)
        unstamped.pop("sequence", None)
        outgoing = _stamp_quote_payload(unstamped)
        _mark_quote_published(outgoing)
        _increment_quote_stream_metric("quotes_published")
    for queue in queues:
        _enqueue_quote_message(queue, outgoing)
    return outgoing


async def _flush_coalesced_kis_quote(code: str, delay: float) -> None:
    try:
        await asyncio.sleep(max(0.0, delay))
        payload = kis_quote_pending_payloads.pop(code, None)
        if payload is None:
            return
        kis_quote_last_broadcast_at[code] = time_module.monotonic()
        outgoing = await _fanout_quote_payload(code, payload)
        if outgoing is not None:
            live_quote_cache.set(
                ("live_quote", code),
                outgoing,
                max(2, int(settings.quote_stream_fallback_poll_seconds)),
            )
    finally:
        if kis_quote_flush_tasks.get(code) is asyncio.current_task():
            kis_quote_flush_tasks.pop(code, None)


def _cancel_coalesced_kis_quote(code: str) -> None:
    kis_quote_pending_payloads.pop(code, None)
    task = kis_quote_flush_tasks.pop(code, None)
    if task is not None and task is not asyncio.current_task() and not task.done():
        task.cancel()


async def _broadcast_kis_quote(code: str, payload: dict[str, object]) -> None:
    if not kis_quote_subscribers.get(code):
        return
    if payload.get("type") == "quote" and payload.get("source") == "kis_realtime":
        interval = max(0, int(settings.quote_stream_min_broadcast_interval_ms)) / 1000
        now = time_module.monotonic()
        kis_quote_last_received_at[code] = now
        last_broadcast_at = kis_quote_last_broadcast_at.get(code)
        if interval and last_broadcast_at is not None and now - last_broadcast_at < interval:
            kis_quote_pending_payloads[code] = payload
            _increment_quote_stream_metric("quotes_coalesced")
            if code not in kis_quote_flush_tasks or kis_quote_flush_tasks[code].done():
                kis_quote_flush_tasks[code] = asyncio.create_task(
                    _flush_coalesced_kis_quote(
                        code,
                        interval - (now - last_broadcast_at),
                    )
                )
            return
        _cancel_coalesced_kis_quote(code)
        kis_quote_last_broadcast_at[code] = now
        outgoing = await _fanout_quote_payload(code, payload)
        if outgoing is not None:
            live_quote_cache.set(
                ("live_quote", code),
                outgoing,
                max(2, int(settings.quote_stream_fallback_poll_seconds)),
            )
        return
    await _fanout_quote_payload(code, payload)


def _select_quote_fallback_codes(now: Optional[float] = None) -> list[str]:
    current = time_module.monotonic() if now is None else float(now)
    stale_after = max(1, int(settings.quote_stream_realtime_stale_seconds))
    candidates = [
        code
        for code in kis_quote_subscribers
        if code not in kis_realtime_active_codes
        or current - kis_quote_last_received_at.get(code, float("-inf")) >= stale_after
    ]
    candidates.sort(key=lambda code: (quote_fallback_last_polled_at.get(code, 0.0), code))
    limit = max(1, int(settings.quote_stream_fallback_max_codes_per_cycle))
    selected = candidates[:limit]
    for code in selected:
        quote_fallback_last_polled_at[code] = current
    return selected


async def _quote_fallback_poll_worker() -> None:
    """Poll only codes without a fresh realtime tick, under a fixed cycle budget."""
    try:
        while kis_quote_subscribers:
            started_at = time_module.monotonic()
            codes = _select_quote_fallback_codes(started_at)
            _increment_quote_stream_metric("fallback_cycles")
            _increment_quote_stream_metric("fallback_codes_polled", len(codes))
            payloads = await _quote_payloads_for_codes(codes)
            for payload in payloads:
                code = str(payload.get("code") or "")
                if code:
                    await _broadcast_kis_quote(code, payload)
            interval = max(2, int(settings.quote_stream_fallback_poll_seconds))
            elapsed = time_module.monotonic() - started_at
            await asyncio.sleep(max(0.25, interval - elapsed))
    except asyncio.CancelledError:
        raise
    except Exception:  # pragma: no cover - operational safeguard
        logger.exception("Shared quote fallback poller failed")
    finally:
        async with kis_quote_lock:
            global quote_fallback_poll_task
            if quote_fallback_poll_task is asyncio.current_task():
                quote_fallback_poll_task = None


def _kis_subscription_message(code: str, subscribe: bool = True) -> str:
    return json.dumps(
        {
            "header": {
                "approval_key": kis_realtime_provider._approval_key or "",
                "custtype": "P",
                "tr_type": "1" if subscribe else "2",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": KIS_REALTIME_STOCK_TR_ID,
                    "tr_key": code,
                }
            },
        },
        ensure_ascii=False,
    )


async def _send_kis_subscription(websocket, code: str, subscribe: bool = True) -> None:
    await websocket.send(_kis_subscription_message(code, subscribe=subscribe))


async def _broadcast_kis_status_to_active(status: str, message: str) -> None:
    public_message = _public_kis_status_message(status, message)
    if status == "fallback":
        for code in kis_realtime_active_codes:
            kis_quote_last_received_at.pop(code, None)
    for code in list(kis_realtime_active_codes):
        await _broadcast_kis_quote(
            code,
            _kis_status_payload(code, status, public_message),
        )


def _kis_connection_ready_status(reconnect_attempt: int) -> tuple[str, str]:
    if reconnect_attempt > 0:
        return "recovered", "KIS realtime recovered"
    return "connected", "KIS realtime connected"


def _kis_approval_is_invalid(message: str) -> bool:
    normalized = str(message or "").strip().lower()
    return "approval" in normalized and any(
        token in normalized
        for token in ("invalid", "expired", "verify", "verification", "reject")
    )


def _kis_session_is_busy(message: str) -> bool:
    normalized = str(message or "").strip().lower()
    return "session busy" in normalized or (
        "already in use" in normalized and "appkey" in normalized
    )


def _public_kis_status_message(status: str, message: str) -> str:
    """Expose operational state without leaking approval keys or upstream text."""
    normalized_status = str(status or "").strip().lower()
    raw_message = str(message or "").strip()
    if normalized_status == "connected":
        return "KIS realtime connected"
    if normalized_status == "recovered":
        return "KIS realtime recovered"
    if _kis_approval_is_invalid(raw_message):
        return "KIS realtime approval rejected"
    if _kis_session_is_busy(raw_message):
        return "KIS realtime session busy"
    return "KIS realtime temporarily unavailable"


def _kis_reconnect_delay_seconds(message: str, reconnect_attempt: int) -> float:
    delay = min(30, 2 ** min(max(1, int(reconnect_attempt)), 5))
    if _kis_session_is_busy(message):
        delay = max(
            delay,
            max(1, int(settings.kis_realtime_contention_backoff_seconds)),
        )
    return float(delay)


def _desired_kis_realtime_codes() -> set[str]:
    """Keep the single KIS session inside its documented 41-registration cap."""
    if not kis_realtime_provider.is_configured():
        return set()
    limit = max(0, min(int(settings.kis_realtime_max_codes), 40))
    if not limit:
        return set()
    ranked = sorted(
        kis_quote_subscribers,
        key=lambda code: (
            -len(kis_quote_subscribers.get(code, set())),
            0 if code in kis_realtime_active_codes else 1,
            code,
        ),
    )
    return set(ranked[:limit])


async def _sync_kis_realtime_codes_locked() -> None:
    global kis_realtime_active_codes, kis_realtime_hub_task
    global kis_realtime_idle_disconnect_task, quote_fallback_poll_task
    desired = _desired_kis_realtime_codes()
    if desired:
        idle_task = kis_realtime_idle_disconnect_task
        if (
            idle_task
            and idle_task is not asyncio.current_task()
            and not idle_task.done()
        ):
            idle_task.cancel()
        kis_realtime_idle_disconnect_task = None
    elif (
        kis_realtime_active_codes
        and settings.kis_realtime_idle_grace_seconds > 0
        and kis_realtime_hub_task is not None
        and not kis_realtime_hub_task.done()
    ):
        desired = set(kis_realtime_active_codes)
        if (
            kis_realtime_idle_disconnect_task is None
            or kis_realtime_idle_disconnect_task.done()
        ):
            kis_realtime_idle_disconnect_task = asyncio.create_task(
                _disconnect_idle_kis_realtime_after_grace()
            )
    removed = kis_realtime_active_codes - desired
    added = desired - kis_realtime_active_codes
    kis_realtime_active_codes = desired
    if removed or added:
        if kis_realtime_control_queue.empty():
            try:
                kis_realtime_control_queue.put_nowait("sync")
            except asyncio.QueueFull:
                _increment_quote_stream_metric("control_sync_coalesced")
        else:
            _increment_quote_stream_metric("control_sync_coalesced")
    if desired and (kis_realtime_hub_task is None or kis_realtime_hub_task.done()):
        kis_realtime_hub_task = asyncio.create_task(_kis_realtime_hub_worker())
    elif not desired and kis_realtime_hub_task and not kis_realtime_hub_task.done():
        kis_realtime_hub_task.cancel()
    if kis_quote_subscribers and (quote_fallback_poll_task is None or quote_fallback_poll_task.done()):
        quote_fallback_poll_task = asyncio.create_task(_quote_fallback_poll_worker())
    elif not kis_quote_subscribers and quote_fallback_poll_task and not quote_fallback_poll_task.done():
        quote_fallback_poll_task.cancel()


async def _disconnect_idle_kis_realtime_after_grace() -> None:
    """Keep one KIS session warm across short browser reconnects, then close it."""
    current_task = asyncio.current_task()
    try:
        await asyncio.sleep(
            max(0.0, float(settings.kis_realtime_idle_grace_seconds))
        )
        async with kis_quote_lock:
            global kis_realtime_active_codes, kis_realtime_hub_task
            if kis_quote_subscribers:
                return
            kis_realtime_active_codes = set()
            hub_task = kis_realtime_hub_task
            if hub_task and hub_task is not current_task and not hub_task.done():
                hub_task.cancel()
    except asyncio.CancelledError:
        raise
    finally:
        global kis_realtime_idle_disconnect_task
        if kis_realtime_idle_disconnect_task is current_task:
            kis_realtime_idle_disconnect_task = None


async def _pace_kis_subscription() -> None:
    delay = max(0, int(settings.kis_realtime_subscription_delay_ms)) / 1000
    if delay:
        await asyncio.sleep(delay)


async def _kis_realtime_hub_worker() -> None:
    subscribed: set[str] = set()
    reconnect_attempt = 0
    try:
        while kis_realtime_active_codes:
            try:
                approval_key = await kis_realtime_provider.approval_key()
                kis_realtime_provider._approval_key = approval_key
                async with websockets.connect(
                    kis_realtime_provider._websocket_url(),
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                ) as kis_socket:
                    ready_status, ready_message = _kis_connection_ready_status(
                        reconnect_attempt
                    )
                    subscribed.clear()
                    for active_code in sorted(kis_realtime_active_codes):
                        await _send_kis_subscription(kis_socket, active_code, subscribe=True)
                        subscribed.add(active_code)
                        await _pace_kis_subscription()
                    await _broadcast_kis_status_to_active(ready_status, ready_message)
                    reconnect_attempt = 0

                    receive_task = asyncio.create_task(kis_socket.recv())
                    control_task = asyncio.create_task(kis_realtime_control_queue.get())
                    try:
                        while kis_realtime_active_codes:
                            done, pending = await asyncio.wait(
                                {receive_task, control_task},
                                return_when=asyncio.FIRST_COMPLETED,
                                timeout=30,
                            )
                            if not done:
                                continue
                            if receive_task in done:
                                raw = receive_task.result()
                                if isinstance(raw, bytes):
                                    raw = raw.decode("utf-8", errors="ignore")
                                if raw.startswith("{"):
                                    message = json.loads(raw)
                                    if message.get("header", {}).get("tr_id") == "PINGPONG":
                                        await kis_socket.send(raw)
                                    else:
                                        body = message.get("body") or {}
                                        if body.get("rt_cd") not in (None, "0"):
                                            error_message = (
                                                body.get("msg1")
                                                or body.get("msg_cd")
                                                or "KIS realtime request failed"
                                            )
                                            if _kis_approval_is_invalid(error_message):
                                                kis_realtime_provider.invalidate_approval_key(approval_key)
                                                raise KisRealtimeError(
                                                    _public_kis_status_message(
                                                        "fallback", error_message
                                                    )
                                                )
                                            if _kis_session_is_busy(error_message):
                                                raise KisRealtimeError(
                                                    _public_kis_status_message(
                                                        "fallback", error_message
                                                    )
                                                )
                                            await _broadcast_kis_status_to_active(
                                                "fallback", error_message
                                            )
                                else:
                                    tick = parse_kis_stock_tick(raw)
                                    tick_code = str(tick.get("code")) if tick else ""
                                    if tick_code:
                                        await _broadcast_kis_quote(tick_code, _kis_realtime_payload(tick_code, tick))
                                receive_task = asyncio.create_task(kis_socket.recv())
                            if control_task in done:
                                control_task.result()
                                desired_codes = set(kis_realtime_active_codes)
                                for control_code in sorted(subscribed - desired_codes):
                                    await _send_kis_subscription(kis_socket, control_code, subscribe=False)
                                    subscribed.discard(control_code)
                                    await _pace_kis_subscription()
                                for control_code in sorted(desired_codes - subscribed):
                                    await _send_kis_subscription(kis_socket, control_code, subscribe=True)
                                    subscribed.add(control_code)
                                    await _pace_kis_subscription()
                                control_task = asyncio.create_task(kis_realtime_control_queue.get())
                    finally:
                        for task in (receive_task, control_task):
                            if not task.done():
                                task.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error_message = _public_kis_status_message("fallback", str(exc))
                await _broadcast_kis_status_to_active("fallback", error_message)
                reconnect_attempt += 1
                delay = _kis_reconnect_delay_seconds(
                    error_message,
                    reconnect_attempt,
                ) + (secrets.randbelow(1000) / 1000)
                await asyncio.sleep(delay)
    finally:
        subscribed.clear()
        async with kis_quote_lock:
            global kis_realtime_hub_task
            if kis_realtime_hub_task is asyncio.current_task():
                kis_realtime_hub_task = None
                if kis_realtime_active_codes and kis_quote_subscribers:
                    # A subscriber can arrive while an idle-grace cancellation
                    # is finishing. Start the replacement only after the old
                    # socket has fully closed so the appkey is never concurrent.
                    kis_realtime_hub_task = asyncio.create_task(
                        _kis_realtime_hub_worker()
                    )


async def _subscribe_kis_quote(code: str) -> Optional[asyncio.Queue]:
    if not kis_realtime_provider.is_configured():
        return None
    queue: asyncio.Queue = asyncio.Queue(maxsize=20)
    accepted, _rejected = await _set_kis_quote_subscriptions(queue, set(), {code})
    return queue if code in accepted else None


async def _set_kis_quote_subscriptions(
    queue: asyncio.Queue,
    current_codes: set[str],
    desired_codes: set[str],
) -> tuple[set[str], set[str]]:
    async with kis_quote_lock:
        for code in current_codes - desired_codes:
            subscribers = kis_quote_subscribers.get(code)
            if not subscribers:
                continue
            subscribers.discard(queue)
            if not subscribers:
                kis_quote_subscribers.pop(code, None)
                kis_quote_last_broadcast_at.pop(code, None)
                kis_quote_last_received_at.pop(code, None)
                quote_fallback_last_polled_at.pop(code, None)
                _cancel_coalesced_kis_quote(code)
        existing_codes = set(kis_quote_subscribers)
        already_available = set(desired_codes) & existing_codes
        new_codes = sorted(set(desired_codes) - existing_codes)
        available_slots = max(
            0,
            int(settings.quote_stream_max_unique_codes) - len(existing_codes),
        )
        accepted_codes = already_available | set(new_codes[:available_slots])
        rejected_codes = set(desired_codes) - accepted_codes
        for code in accepted_codes - current_codes:
            kis_quote_subscribers.setdefault(code, set()).add(queue)
        await _sync_kis_realtime_codes_locked()
    return accepted_codes, rejected_codes


async def _unsubscribe_kis_quote(code: str, queue: Optional[asyncio.Queue]) -> None:
    if queue is None:
        return
    await _set_kis_quote_subscriptions(queue, {code}, set())


def _normalize_quote_code_list(values: list[object], *, limit: Optional[int] = None) -> list[str]:
    max_codes = max(1, int(limit or settings.quote_stream_max_codes_per_client))
    normalized: list[str] = []
    for value in values:
        code = _normalize_stock_code(str(value or ""))
        if not re.fullmatch(r"\d{6}", code) or code in normalized:
            continue
        normalized.append(code)
        if len(normalized) > max_codes:
            raise ValueError(f"A client can subscribe to at most {max_codes} quote codes")
    return normalized


def _active_stock_quote_codes(codes: list[str]) -> set[str]:
    if not codes:
        return set()
    with SessionLocal() as db:
        return set(
            str(code)
            for code in db.scalars(
                select(StockMaster.code).where(
                    StockMaster.code.in_(tuple(codes)),
                    StockMaster.is_active.is_(True),
                )
            )
        )


def _enqueue_quote_message(queue: asyncio.Queue, payload: dict[str, object]) -> None:
    if queue.full():
        _increment_quote_stream_metric("client_queue_overflows")
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        pass


async def _quote_stream_connection_opened(*, legacy: bool = False) -> None:
    global quote_stream_connections, quote_stream_legacy_connections, quote_stream_peak_connections
    async with quote_stream_connection_lock:
        if legacy:
            quote_stream_legacy_connections += 1
        else:
            quote_stream_connections += 1
        quote_stream_peak_connections = max(
            quote_stream_peak_connections,
            quote_stream_connections + quote_stream_legacy_connections,
        )


async def _quote_stream_connection_closed(*, legacy: bool = False) -> None:
    global quote_stream_connections, quote_stream_legacy_connections
    async with quote_stream_connection_lock:
        if legacy:
            quote_stream_legacy_connections = max(0, quote_stream_legacy_connections - 1)
        else:
            quote_stream_connections = max(0, quote_stream_connections - 1)


@app.get("/realtime/status")
async def realtime_status():
    async with kis_quote_lock:
        now_monotonic = time_module.monotonic()
        subscriber_queues = {
            id(queue)
            for queues in kis_quote_subscribers.values()
            for queue in queues
        }
        with quote_stream_metrics_lock:
            delivery_metrics = dict(quote_stream_metrics)
        with quote_stream_metadata_lock:
            realtime_ages = [
                max(0.0, now_monotonic - observed)
                for code, observed in kis_quote_last_received_at.items()
                if code in kis_quote_subscribers
            ]
            publish_ages = [
                max(0.0, now_monotonic - observed)
                for code, observed in quote_stream_last_published_at.items()
                if code in kis_quote_subscribers
            ]
            fallback_ages = [
                max(0.0, now_monotonic - observed)
                for code, observed in quote_fallback_last_polled_at.items()
                if code in kis_quote_subscribers
            ]
        stale_after = max(1, int(settings.quote_stream_realtime_stale_seconds))
        subscribed_realtime_codes = (
            set(kis_quote_subscribers) & kis_realtime_active_codes
        )
        stale_realtime_codes = sum(
            1
            for code in subscribed_realtime_codes
            if now_monotonic - kis_quote_last_received_at.get(code, float("-inf"))
            >= stale_after
        )
        with ai_signal_revision_lock:
            revision_state = {
                "revision": int(ai_signal_revision_state.get("revision") or 0),
                "as_of": ai_signal_revision_state.get("as_of"),
                "subscriber_queues": len(ai_signal_revision_clients),
            }
        return {
            "connections": {
                "multiplex": quote_stream_connections,
                "legacy": quote_stream_legacy_connections,
                "total": quote_stream_connections + quote_stream_legacy_connections,
                "peak": quote_stream_peak_connections,
            },
            "public_quote_channels": {
                "unique_codes": len(kis_quote_subscribers),
                "subscriber_queues": len(subscriber_queues),
                "kis_realtime_codes": len(subscribed_realtime_codes),
                "fallback_codes": len(set(kis_quote_subscribers) - kis_realtime_active_codes),
                "stale_realtime_codes": stale_realtime_codes,
                "kis_session_codes": len(kis_realtime_active_codes),
                "idle_grace_active": bool(
                    kis_realtime_active_codes and not kis_quote_subscribers
                ),
                "idle_grace_seconds": settings.kis_realtime_idle_grace_seconds,
                "contention_backoff_seconds": (
                    settings.kis_realtime_contention_backoff_seconds
                ),
                "max_codes_per_client": settings.quote_stream_max_codes_per_client,
                "max_unique_codes": settings.quote_stream_max_unique_codes,
                "min_broadcast_interval_ms": settings.quote_stream_min_broadcast_interval_ms,
            },
            "delivery": {
                **delivery_metrics,
                "pending_coalesced_quotes": len(kis_quote_pending_payloads),
                "control_queue_depth": kis_realtime_control_queue.qsize(),
            },
            "ages_seconds": {
                "oldest_realtime_tick": round(max(realtime_ages), 3) if realtime_ages else None,
                "oldest_published_quote": round(max(publish_ages), 3) if publish_ages else None,
                "oldest_fallback_poll": round(max(fallback_ages), 3) if fallback_ages else None,
            },
            "signal_revision": revision_state,
            "private_watchlists_shared": False,
        }


@app.websocket("/ws/quotes")
async def stock_quote_multiplex_stream(websocket: WebSocket):
    await websocket.accept()
    await _quote_stream_connection_opened()
    queue: asyncio.Queue = asyncio.Queue(maxsize=max(20, settings.quote_stream_queue_size))
    current_codes: set[str] = set()
    registered_codes: set[str] = set()
    command_times: list[float] = []

    async def sender() -> None:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=25)
            except asyncio.TimeoutError:
                payload = {
                    "type": "heartbeat",
                    "as_of": datetime.now(KST).isoformat(),
                }
            code = str(payload.get("code") or "")
            if payload.get("type") in {"quote", "status"} and code and code not in current_codes:
                continue
            await asyncio.wait_for(
                websocket.send_json(payload),
                timeout=max(1, settings.quote_stream_send_timeout_seconds),
            )

    await asyncio.to_thread(_current_ai_signal_revision_frame)
    sender_task = asyncio.create_task(sender())
    _enqueue_quote_message(
        queue,
        {
            "type": "ready",
            "transport": "multiplex",
            "max_codes": settings.quote_stream_max_codes_per_client,
        },
    )
    _register_ai_signal_revision_client(
        queue,
        asyncio.get_running_loop(),
        enqueue_initial=True,
    )
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            message_type = str(message.get("type") or "set").strip().lower()
            if message_type == "ping":
                _enqueue_quote_message(
                    queue,
                    {"type": "pong", "as_of": datetime.now(KST).isoformat()},
                )
                continue
            if message_type not in {"set", "subscribe"}:
                _enqueue_quote_message(
                    queue,
                    {"type": "error", "message": "Unsupported quote stream command"},
                )
                continue
            command_now = time_module.monotonic()
            command_window = max(
                0.1,
                float(settings.quote_stream_command_window_seconds),
            )
            command_limit = max(1, int(settings.quote_stream_max_commands_per_window))
            command_times = [
                observed
                for observed in command_times
                if command_now - observed < command_window
            ]
            if len(command_times) >= command_limit:
                retry_after = max(
                    0.0,
                    command_window - (command_now - command_times[0]),
                )
                _increment_quote_stream_metric("subscription_commands_throttled")
                _enqueue_quote_message(
                    queue,
                    {
                        "type": "error",
                        "code": "subscription_rate_limited",
                        "message": "Too many quote subscription commands",
                        "retry_after_ms": max(1, int(retry_after * 1000)),
                    },
                )
                continue
            command_times.append(command_now)
            _increment_quote_stream_metric("subscription_commands")
            raw_codes = message.get("codes")
            try:
                requested = set(
                    _normalize_quote_code_list(raw_codes if isinstance(raw_codes, list) else [])
                )
            except ValueError as exc:
                _enqueue_quote_message(
                    queue,
                    {"type": "error", "message": str(exc)},
                )
                continue
            active_codes = await asyncio.to_thread(
                _active_stock_quote_codes,
                sorted(requested),
            )
            invalid_codes = requested - active_codes
            accepted_codes, capacity_rejected = await _set_kis_quote_subscriptions(
                queue,
                registered_codes,
                active_codes,
            )
            rejected_codes = invalid_codes | capacity_rejected
            _increment_quote_stream_metric("subscription_codes_rejected", len(rejected_codes))
            added = accepted_codes - current_codes
            registered_codes = accepted_codes
            current_codes = accepted_codes
            _enqueue_quote_message(
                queue,
                {
                    "type": "subscribed",
                    "codes": sorted(current_codes),
                    "count": len(current_codes),
                    "rejected_codes": sorted(rejected_codes),
                },
            )
            for payload in await _quote_payloads_for_codes(sorted(added)):
                stamped = _stamp_quote_payload(payload)
                _mark_quote_published(stamped)
                _enqueue_quote_message(queue, stamped)
    except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError):
        return
    finally:
        sender_task.cancel()
        with suppress(
            asyncio.CancelledError,
            WebSocketDisconnect,
            RuntimeError,
            asyncio.TimeoutError,
        ):
            await sender_task
        _unregister_ai_signal_revision_client(queue)
        await _set_kis_quote_subscriptions(queue, registered_codes, set())
        await _quote_stream_connection_closed()


@app.websocket("/ws/stocks/{code}/quote")
async def stock_quote_stream(websocket: WebSocket, code: str):
    await websocket.accept()
    await _quote_stream_connection_opened(legacy=True)
    normalized = _normalize_stock_code(code)
    kis_queue: Optional[asyncio.Queue] = None
    try:
        active_codes = await asyncio.to_thread(_active_stock_quote_codes, [normalized])
        if normalized not in active_codes:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "inactive_stock",
                    "message": "Stock quote subscription is not active",
                }
            )
            return
        kis_queue = await _subscribe_kis_quote(normalized)
        await _send_polling_quote(websocket, normalized)
        while True:
            if kis_queue is None:
                await asyncio.sleep(_quote_poll_interval_seconds())
                await _send_polling_quote(websocket, normalized)
                continue
            try:
                payload = await asyncio.wait_for(kis_queue.get(), timeout=_quote_poll_interval_seconds())
                await websocket.send_json(payload)
            except asyncio.TimeoutError:
                await _send_polling_quote(websocket, normalized)
    except (WebSocketDisconnect, RuntimeError):
        return
    finally:
        await _unsubscribe_kis_quote(normalized, kis_queue)
        await _quote_stream_connection_closed(legacy=True)


@app.get("/stocks/{code}/quote")
def stock_live_quote(code: str, response: Response):
    normalized = _normalize_stock_code(code)
    payload = _stock_quote_stream_payload(normalized)
    if not payload:
        raise HTTPException(status_code=404, detail="Stock quote not found")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return payload


def _korea_regular_market_open(now: Optional[datetime] = None) -> bool:
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    else:
        current = current.astimezone(KST)
    return current.weekday() < 5 and time(9, 0) <= current.time() < time(15, 31)


def _korea_intraday_session(now: Optional[datetime] = None) -> dict[str, Any]:
    session = _korea_quote_session(now)
    session_id = str(session.get("market_session") or "closed")
    if session_id == "nxt_pre_market":
        market_state = "pre_market"
    elif session_id in {"krx_regular", "integrated_regular"}:
        market_state = "regular"
    elif session_id == "nxt_after_market":
        market_state = "after_market"
    else:
        market_state = "closed"
    return {
        **session,
        "market_state": market_state,
        "market_division": (
            str(session.get("market_division") or "J")
            if session.get("is_live")
            else "J"
        ),
    }


def _seconds_until_next_korea_open(now: datetime) -> int:
    current = now.astimezone(KST) if now.tzinfo else now.replace(tzinfo=KST)
    target = datetime.combine(current.date(), time(8, 0), tzinfo=KST)
    if current >= target:
        target += timedelta(days=1)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    return max(30, int((target - current).total_seconds()) - 30)


def _previous_weekday(day: date) -> date:
    candidate = day - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _intraday_trade_date(points: list[dict[str, object]]) -> Optional[date]:
    for point in reversed(points):
        raw = str(point.get("trade_date") or "").strip()
        try:
            return datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            continue
    return None


def _closed_intraday_snapshot_is_current(
    *,
    trade_date: date,
    validated_on: date,
    now: datetime,
    latest_daily_date: Optional[date],
) -> bool:
    today = now.date()
    if validated_on == today:
        return True
    if now.weekday() < 5 and now.time() >= time(15, 31):
        return trade_date == today
    if latest_daily_date is not None:
        return trade_date >= latest_daily_date
    return trade_date == _previous_weekday(today)


def _latest_daily_trade_date(db: Session, code: str) -> Optional[date]:
    return db.scalar(
        select(DailyPrice.trade_date)
        .where(DailyPrice.code == code)
        .order_by(desc(DailyPrice.trade_date))
        .limit(1)
    )


def _intraday_record_is_usable(
    record: dict[str, Any],
    *,
    limit: int,
    now: datetime,
    latest_daily_date: Optional[date],
) -> bool:
    points = record.get("points")
    trade_date = record.get("trade_date")
    validated_on = record.get("validated_on")
    return (
        isinstance(points, list)
        and int(record.get("max_points") or 0) >= limit
        and isinstance(trade_date, date)
        and isinstance(validated_on, date)
        and _closed_intraday_snapshot_is_current(
            trade_date=trade_date,
            validated_on=validated_on,
            now=now,
            latest_daily_date=latest_daily_date,
        )
    )


def _load_closed_intraday_snapshot(
    db: Session,
    code: str,
    limit: int,
    now: datetime,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    latest_daily_date = _latest_daily_trade_date(db, code)
    cached = intraday_chart_cache.get(code)
    if isinstance(cached, dict) and _intraday_record_is_usable(
        cached,
        limit=limit,
        now=now,
        latest_daily_date=latest_daily_date,
    ):
        return cached, "memory"

    snapshot = db.get(StockIntradaySnapshot, code)
    if snapshot is None:
        return None, None
    try:
        points = json.loads(snapshot.payload)
    except (TypeError, ValueError):
        return None, None
    record = {
        "points": points,
        "trade_date": snapshot.trade_date,
        "validated_on": snapshot.validated_on,
        "max_points": snapshot.max_points,
        "fetched_at": snapshot.fetched_at,
    }
    if not _intraday_record_is_usable(
        record,
        limit=limit,
        now=now,
        latest_daily_date=latest_daily_date,
    ):
        return None, None
    intraday_chart_cache.set(code, record, INTRADAY_CLOSED_TTL_SECONDS)
    return record, "database"


def _save_closed_intraday_snapshot(
    db: Session,
    code: str,
    points: list[dict[str, object]],
    limit: int,
    now: datetime,
) -> Optional[dict[str, Any]]:
    trade_date = _intraday_trade_date(points)
    if trade_date is None or trade_date > now.date():
        return None
    fetched_at = datetime.utcnow()
    snapshot = db.get(StockIntradaySnapshot, code)
    if snapshot is None:
        snapshot = StockIntradaySnapshot(
            stock_code=code,
            trade_date=trade_date,
            source="kis_rest",
            payload="[]",
            max_points=limit,
            point_count=0,
            validated_on=now.date(),
            fetched_at=fetched_at,
        )
        db.add(snapshot)
    snapshot.trade_date = trade_date
    snapshot.source = "kis_rest"
    snapshot.payload = json.dumps(points, ensure_ascii=False, separators=(",", ":"))
    snapshot.max_points = limit
    snapshot.point_count = len(points)
    snapshot.validated_on = now.date()
    snapshot.fetched_at = fetched_at
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist closed intraday chart for %s", code)
        return None
    record = {
        "points": points,
        "trade_date": trade_date,
        "validated_on": now.date(),
        "max_points": limit,
        "fetched_at": fetched_at,
    }
    intraday_chart_cache.set(code, record, INTRADAY_CLOSED_TTL_SECONDS)
    return record


def _intraday_code_lock(code: str) -> RLock:
    with intraday_lock_guard:
        return intraday_code_locks.setdefault(code, RLock())


def _warm_closed_intraday_snapshots(now: Optional[datetime] = None) -> int:
    current = now or datetime.now(KST)
    if _korea_intraday_session(current).get("is_live") or not kis_rest_provider.is_configured():
        return 0
    with SessionLocal() as db:
        recent_codes = list(
            db.scalars(
                select(WatchlistItem.code)
                .order_by(desc(WatchlistItem.updated_at))
                .limit(INTRADAY_WARMUP_MAX_STOCKS * 4)
            )
        )
    codes = list(dict.fromkeys(_normalize_stock_code(code) for code in recent_codes))[
        :INTRADAY_WARMUP_MAX_STOCKS
    ]
    warmed = 0
    for code in codes:
        with _intraday_code_lock(code):
            with SessionLocal() as db:
                cached, _ = _load_closed_intraday_snapshot(db, code, 390, current)
                if cached is not None:
                    continue
                try:
                    points = kis_rest_provider.fetch_intraday_chart(code, max_points=390)
                    if _save_closed_intraday_snapshot(db, code, points, 390, current) is not None:
                        warmed += 1
                except Exception:
                    logger.warning("Closed intraday warmup skipped for %s", code, exc_info=True)
    return warmed


@app.get("/stocks/{code}/intraday")
def stock_intraday_chart(
    code: str,
    response: Response,
    limit: int = Query(default=390, ge=30, le=390),
    db: Session = Depends(get_db),
):
    normalized = _normalize_stock_code(code)
    now = datetime.now(KST)
    session = _korea_intraday_session(now)
    market_open = bool(session.get("is_live"))
    market_division = str(session.get("market_division") or "J")
    points: list[dict[str, object]] = []
    source = "kis_rest"
    cache_state = "live" if market_open else "miss"
    cached_at: Optional[datetime] = None
    message: Optional[str] = None

    if not market_open:
        with _intraday_code_lock(normalized):
            cached, hit = _load_closed_intraday_snapshot(db, normalized, limit, now)
            if cached is not None:
                points = list(cached["points"])[:limit]
                cache_state = hit or "database"
                cached_at = cached.get("fetched_at")
            elif not kis_rest_provider.is_configured():
                source = "unavailable"
                message = "KIS API가 설정되지 않았습니다."
            else:
                try:
                    points = kis_rest_provider.fetch_intraday_chart(
                        normalized,
                        max_points=limit,
                        market_division="J",
                    )
                    saved = _save_closed_intraday_snapshot(db, normalized, points, limit, now)
                    cached_at = saved.get("fetched_at") if saved else None
                except Exception as exc:
                    source = "unavailable"
                    message = str(exc)
    elif not kis_rest_provider.is_configured():
        source = "unavailable"
        message = "KIS API가 설정되지 않았습니다."
    else:
        try:
            points = kis_rest_provider.fetch_intraday_chart(
                normalized,
                max_points=limit,
                market_division=market_division,
            )
        except Exception as exc:
            source = "unavailable"
            message = str(exc)

    if market_open:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    elif points:
        response.headers["Cache-Control"] = f"private, max-age={_seconds_until_next_korea_open(now)}"
    else:
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Intraday-Cache"] = cache_state
    return {
        "code": normalized,
        "source": source,
        "as_of": now,
        "market_state": session.get("market_state") or "closed",
        "market_session": session.get("market_session"),
        "market_session_label": session.get("market_session_label"),
        "market_venue": session.get("market_venue"),
        "market_division": market_division,
        "cache_state": cache_state,
        "cached_at": cached_at,
        "trade_date": _intraday_trade_date(points),
        "message": message,
        "points": points,
    }


@app.get("/stocks/{code}/ai-analysis", response_model=StockAIAnalysisOut)
def stock_ai_analysis(
    code: str,
    request: Request,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "stock_ai_analysis", limit=20, window_seconds=60)
    code = _normalize_stock_code(code)
    snapshot_key = _stock_dashboard_snapshot_key(code)
    complete = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    if complete is None:
        if not settings.runs_collectors():
            _queue_cold_snapshot_or_503(
                db,
                snapshot_key,
                detail="Complete stock dashboard snapshot is being prepared",
            )
        if not db.get(StockMaster, code):
            _ensure_stock_master_from_naver(db, code)
        dashboard = stock_dashboard(
            code,
            Response(),
            refresh=False,
            include_profile=True,
            include_live=False,
            db=db,
        )
    else:
        dashboard = complete.payload
    if refresh or (complete is not None and not complete.is_fresh):
        _queue_complete_snapshot_refresh(db, snapshot_key)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Stock not found")
    dashboard = deepcopy(dashboard)
    if not _enrich_cached_live_quote(dashboard, code, db):
        _enrich_uncached_kis_quote(dashboard, code, db)
    rules = build_stock_ai_analysis(dashboard)
    return enrich_stock_ai_analysis(dashboard, rules)


@app.get("/stocks/{code}/quant-signals", response_model=StockQuantSignalsOut)
def stock_quant_signals(
    code: str,
    request: Request,
    response: Response,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "stock_quant_signals", limit=30, window_seconds=60)
    code = _normalize_stock_code(code)
    payload = load_external_stock_quant_signal_payload(
        settings.market_quant_signal_source_url,
        code,
        timeout_seconds=settings.market_quant_signal_source_timeout_seconds,
    )
    if payload and quant_payload_has_trade_metadata(payload):
        live_quote, _source = _fetch_uncached_current_quote(code)
        payload = synchronize_quant_payload_live_quote(
            payload,
            live_quote,
            now=datetime.now(KST),
        )
        payload = apply_stock_signal_reconciliations(payload, now=datetime.now(KST)) or payload
        payload = sanitize_pending_entry_signal_payload(payload)
        payload = enrich_quant_signal_payload_sector(db, payload, code)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return payload
    if not db.get(StockMaster, code):
        _ensure_stock_master_from_naver(db, code)
    if not db.get(StockMaster, code):
        raise HTTPException(status_code=404, detail="Stock not found")

    ensure_stock_price_history(db, code, require_recent_complete_ohlc=True)
    live_quote, _source = _fetch_uncached_current_quote(code)
    payload = load_reference_quant_signal_payload(
        db,
        code,
        live_quote=live_quote,
    )
    if not payload:
        raise HTTPException(status_code=404, detail="Stock not found")
    payload = sanitize_pending_entry_signal_payload(payload)
    payload = enrich_quant_signal_payload_sector(db, payload, code)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return payload


@app.get("/stocks/{code}/prices", response_model=list[DailyPriceOut])
def stock_prices(
    code: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=250, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    statement = (
        select(DailyPrice)
        .where(DailyPrice.code == code)
        .order_by(desc(DailyPrice.trade_date))
        .limit(limit)
    )
    if from_date:
        statement = statement.where(DailyPrice.trade_date >= from_date)
    if to_date:
        statement = statement.where(DailyPrice.trade_date <= to_date)
    return list(db.scalars(statement))


@app.get("/stocks/{code}/flows", response_model=list[InvestorFlowOut])
def stock_flows(
    code: str,
    response: Response,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    investor_type: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    refresh: bool = Query(default=False),
    pages: int = Query(default=13, ge=1, le=20),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    _refresh_stock_investor_flow_if_stale(
        db,
        code,
        pages=pages if refresh else 1,
        force=refresh,
    )
    statement = (
        select(InvestorFlow)
        .where(InvestorFlow.code == code)
        .order_by(desc(InvestorFlow.trade_date), InvestorFlow.investor_type)
        .limit(limit)
    )
    if from_date:
        statement = statement.where(InvestorFlow.trade_date >= from_date)
    if to_date:
        statement = statement.where(InvestorFlow.trade_date <= to_date)
    if investor_type:
        statement = statement.where(InvestorFlow.investor_type == investor_type)
    response.headers["Cache-Control"] = "no-store" if refresh else "private, max-age=300"
    return list(db.scalars(statement))


@app.get("/stocks/{code}/financials", response_model=list[FinancialStatementLineOut])
def stock_financials(
    code: str,
    year: Optional[str] = Query(default=None, pattern=r"^\d{4}$"),
    report: Optional[str] = Query(default=None),
    fs_div: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    statement = (
        select(FinancialStatementLine)
        .where(FinancialStatementLine.stock_code == code)
        .order_by(
            desc(FinancialStatementLine.bsns_year),
            desc(FinancialStatementLine.reprt_code),
            FinancialStatementLine.sj_div,
            FinancialStatementLine.ord,
        )
        .limit(limit)
    )
    if year:
        statement = statement.where(FinancialStatementLine.bsns_year == year)
    if report:
        statement = statement.where(FinancialStatementLine.reprt_code == report)
    if fs_div:
        statement = statement.where(FinancialStatementLine.fs_div == fs_div)
    return list(db.scalars(statement))


def _ranking_snapshot_json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _surge_change_rate(item: dict[str, Any]) -> Decimal:
    try:
        return Decimal(str(item.get("change_rate") or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _build_surge_ranking_snapshot_payload(
    db: Session,
    *,
    refresh_live: bool,
) -> dict[str, Any]:
    captured_at = datetime.now(KST)
    markets: dict[str, dict[str, Any]] = {}
    all_items: list[dict[str, Any]] = []
    source_values: list[str] = []

    for target_market in SURGE_RANKING_MARKETS:
        payload = build_market_rankings(
            db,
            category="surge",
            market=target_market,
            limit=SURGE_RANKING_SNAPSHOT_PER_MARKET_LIMIT,
            refresh_live=refresh_live,
        )
        items = [dict(item) for item in list(payload.get("items") or [])]
        markets[target_market] = {
            "source": str(payload.get("source") or "database"),
            "universe_count": int(payload.get("universe_count") or 0),
            "matching_count": int(payload.get("matching_count") or len(items)),
            "items": items,
        }
        source_values.append(str(payload.get("source") or "database"))
        all_items.extend(dict(item) for item in items)

    all_items.sort(key=_surge_change_rate, reverse=True)
    for rank, item in enumerate(all_items, start=1):
        item["rank"] = rank
        item["category"] = "surge"

    markets["ALL"] = {
        "source": (
            "naver_market_rise"
            if "naver_market_rise" in source_values
            else (source_values[0] if source_values else "database")
        ),
        "universe_count": sum(
            int(markets[name]["universe_count"]) for name in SURGE_RANKING_MARKETS
        ),
        "matching_count": len(all_items),
        "items": all_items,
    }
    return {
        "as_of": captured_at.isoformat(),
        "markets": markets,
    }


def _load_surge_ranking_snapshot(
    db: Session,
    *,
    snapshot_id: Optional[str],
    refresh: bool,
) -> MarketRankingSnapshot:
    now = datetime.utcnow()
    if snapshot_id and not refresh:
        requested = db.get(MarketRankingSnapshot, snapshot_id)
        if (
            requested is not None
            and requested.category == "surge"
            and requested.expires_at >= now
        ):
            return requested

    if not refresh:
        latest = db.scalar(
            select(MarketRankingSnapshot)
            .where(
                MarketRankingSnapshot.category == "surge",
                MarketRankingSnapshot.captured_at
                >= now - timedelta(seconds=SURGE_RANKING_SNAPSHOT_REUSE_SECONDS),
                MarketRankingSnapshot.expires_at >= now,
            )
            .order_by(desc(MarketRankingSnapshot.captured_at))
            .limit(1)
        )
        if latest is not None:
            return latest

    captured_at = datetime.utcnow()
    built_payload = _build_surge_ranking_snapshot_payload(db, refresh_live=refresh)
    snapshot = MarketRankingSnapshot(
        snapshot_id=secrets.token_urlsafe(18),
        category="surge",
        payload=json.dumps(
            built_payload,
            ensure_ascii=False,
            default=_ranking_snapshot_json_default,
        ),
        captured_at=captured_at,
        expires_at=captured_at + SURGE_RANKING_SNAPSHOT_RETENTION,
    )
    if not _surge_snapshot_has_complete_shape(snapshot):
        raise ValueError("Surge ranking builder returned an incomplete snapshot")
    db.add(snapshot)
    db.commit()
    try:
        db.execute(
            delete(MarketRankingSnapshot).where(
                MarketRankingSnapshot.category == "surge",
                MarketRankingSnapshot.expires_at < captured_at,
                MarketRankingSnapshot.snapshot_id != snapshot.snapshot_id,
            )
        )
        db.commit()
    except Exception as exc:
        # Retention cleanup must never prevent a newly validated complete
        # snapshot from being published by the runtime.
        db.rollback()
        logger.warning("Expired surge snapshot cleanup failed: %s", exc)
    return snapshot


def _surge_ranking_snapshot_response(
    snapshot: MarketRankingSnapshot,
    *,
    market: Optional[str],
    limit: int,
) -> dict[str, Any]:
    payload = json.loads(snapshot.payload)
    normalized_market = (market or "ALL").upper()
    if normalized_market not in {"ALL", *SURGE_RANKING_MARKETS}:
        normalized_market = "ALL"
    bucket = dict((payload.get("markets") or {}).get(normalized_market) or {})
    items = [dict(item) for item in list(bucket.get("items") or [])[:limit]]
    try:
        as_of = datetime.fromisoformat(str(payload.get("as_of")))
    except (TypeError, ValueError):
        as_of = snapshot.captured_at.replace(tzinfo=KST)
    return {
        "category": "surge",
        "mode": "daily",
        "market": None if normalized_market == "ALL" else normalized_market,
        "as_of": as_of,
        "source": str(bucket.get("source") or "database"),
        "universe_count": int(bucket.get("universe_count") or 0),
        "matching_count": int(bucket.get("matching_count") or len(items)),
        "items": items,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_captured_at": as_of,
    }


def _surge_snapshot_has_complete_shape(snapshot: MarketRankingSnapshot) -> bool:
    try:
        payload = json.loads(snapshot.payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    markets = payload.get("markets") if isinstance(payload, dict) else None
    if not isinstance(markets, dict) or not payload.get("as_of"):
        return False
    for market_name in ("KOSPI", "KOSDAQ", "ALL"):
        bucket = markets.get(market_name)
        if not isinstance(bucket, dict) or not isinstance(bucket.get("items"), list):
            return False
        items = bucket["items"]
        try:
            universe_count = int(bucket.get("universe_count") or 0)
            matching_count = int(bucket.get("matching_count") or 0)
        except (TypeError, ValueError):
            return False
        if universe_count <= 0:
            return False
        if matching_count < len(items):
            return False
        # A real session may contain no rising stocks.  That is complete when
        # the universe was loaded and its matching count is exactly zero.  An
        # empty item list with a positive match count is truncated/incomplete.
        if not items and matching_count != 0:
            return False
        for item in items:
            if not isinstance(item, dict):
                return False
            if not str(item.get("code") or "").strip() or not str(item.get("name") or "").strip():
                return False
            if str(item.get("market") or "").upper() not in SURGE_RANKING_MARKETS:
                return False
            if (
                item.get("change_rate") is None
                or int(item.get("rank") or 0) <= 0
                or str(item.get("category") or "") != "surge"
            ):
                return False
    all_codes = [str(item.get("code") or "") for item in markets["ALL"]["items"]]
    expected_codes = [
        str(item.get("code") or "")
        for market_name in SURGE_RANKING_MARKETS
        for item in markets[market_name]["items"]
    ]
    if sorted(all_codes) != sorted(expected_codes):
        return False
    return True


def _latest_complete_surge_ranking_snapshot(db: Session) -> Optional[MarketRankingSnapshot]:
    candidates = db.scalars(
        select(MarketRankingSnapshot)
        .where(MarketRankingSnapshot.category == "surge")
        .order_by(desc(MarketRankingSnapshot.captured_at))
        .limit(12)
    )
    return next((snapshot for snapshot in candidates if _surge_snapshot_has_complete_shape(snapshot)), None)


def _validate_surge_complete_snapshot(payload: Any) -> dict[str, Any]:
    candidate = _json_ready(payload)
    if not isinstance(candidate, dict) or not str(candidate.get("snapshot_id") or "").strip():
        raise ValueError("Surge snapshot marker requires snapshot_id")
    if not candidate.get("captured_at"):
        raise ValueError("Surge snapshot marker requires captured_at")
    return candidate


def _publish_surge_complete_snapshot_marker(
    db: Session,
    snapshot: MarketRankingSnapshot,
) -> None:
    _publish_cold_snapshot_or_read_winner(
        db,
        SURGE_COMPLETE_SNAPSHOT_KEY,
        {
            "snapshot_id": snapshot.snapshot_id,
            "captured_at": snapshot.captured_at,
        },
        fresh_for_seconds=MARKET_RANKING_TTL_SECONDS,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
        captured_at=snapshot.captured_at,
        validator=_validate_surge_complete_snapshot,
    )


def _build_surge_complete_snapshot(db: Session, _snapshot_key: str) -> SnapshotBuild:
    snapshot = _load_surge_ranking_snapshot(db, snapshot_id=None, refresh=True)
    if not _surge_snapshot_has_complete_shape(snapshot):
        raise ValueError("Surge ranking builder returned an incomplete snapshot")
    return SnapshotBuild(
        payload={
            "snapshot_id": snapshot.snapshot_id,
            "captured_at": snapshot.captured_at,
        },
        fresh_for_seconds=MARKET_RANKING_TTL_SECONDS,
        captured_at=snapshot.captured_at,
        validator=_validate_surge_complete_snapshot,
    )


def _ensure_market_ranking_stock_masters(
    db: Session,
    items: list[dict[str, Any]],
) -> None:
    changed = False
    seen_date = datetime.now(KST).date()
    for raw_item in items:
        code = _normalize_stock_code(str(raw_item.get("code") or ""))
        name = str(raw_item.get("name") or "").strip()
        market = str(raw_item.get("market") or "").strip().upper()
        if not re.fullmatch(r"[0-9A-Z]{6}", code) or not name or market not in {"KOSPI", "KOSDAQ"}:
            continue
        stock = db.get(StockMaster, code)
        if stock is None:
            stock = StockMaster(code=code, name=name, market=market)
            db.add(stock)
            changed = True
        if stock.name != name or stock.market != market or not stock.is_active or stock.last_seen_date != seen_date:
            stock.name = name
            stock.market = market
            stock.is_active = True
            stock.last_seen_date = seen_date
            changed = True
    if changed:
        db.commit()


@app.get("/market/rankings", response_model=MarketRankingOut)
def market_rankings(
    category: str = Query(
        default="surge",
        pattern="^(surge|volume|market_cap|etf|dividend|per|low52|high52|trading_value|valuation|momentum|sentiment)$",
    ),
    market: Optional[str] = Query(default=None),
    mode: str = Query(default="", pattern="^(|daily|week|month|market_cap|volume|yield|amount|low)$"),
    limit: int = Query(default=50, ge=1, le=3000),
    refresh: bool = Query(default=False),
    snapshot_id: Optional[str] = Query(default=None, min_length=8, max_length=128),
    db: Session = Depends(get_db),
):
    # FastAPI injects the declared string default for HTTP requests. Direct
    # callers (maintenance jobs and tests) receive the Query descriptor unless
    # they pass ``mode`` explicitly, so normalize it to the public default.
    mode = mode if isinstance(mode, str) else ""
    if category == "surge" and mode in {"", "daily"}:
        try:
            marker = get_complete_snapshot(
                db,
                SURGE_COMPLETE_SNAPSHOT_KEY,
                schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
            )
            snapshot: Optional[MarketRankingSnapshot] = None
            if snapshot_id:
                requested = db.get(MarketRankingSnapshot, snapshot_id)
                if (
                    requested is not None
                    and requested.category == "surge"
                    and requested.expires_at >= datetime.utcnow()
                    and _surge_snapshot_has_complete_shape(requested)
                ):
                    snapshot = requested
            elif marker is not None:
                marked_id = str(marker.payload.get("snapshot_id") or "")
                marked = db.get(MarketRankingSnapshot, marked_id) if marked_id else None
                if marked is not None and _surge_snapshot_has_complete_shape(marked):
                    snapshot = marked
            if snapshot is None:
                snapshot = _latest_complete_surge_ranking_snapshot(db)
            if snapshot is None:
                if not settings.runs_collectors():
                    _queue_cold_snapshot_or_503(
                        db,
                        SURGE_COMPLETE_SNAPSHOT_KEY,
                        detail="Complete surge ranking snapshot is being prepared",
                    )
                snapshot = _load_surge_ranking_snapshot(
                    db,
                    snapshot_id=snapshot_id,
                    refresh=False,
                )
                if not _surge_snapshot_has_complete_shape(snapshot):
                    raise ValueError("Surge ranking cold-start snapshot is incomplete")
                _publish_surge_complete_snapshot_marker(db, snapshot)
                marker = get_complete_snapshot(
                    db,
                    SURGE_COMPLETE_SNAPSHOT_KEY,
                    schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
                )
            if refresh or marker is None or not marker.is_fresh:
                _queue_complete_snapshot_refresh(db, SURGE_COMPLETE_SNAPSHOT_KEY)
            payload = _surge_ranking_snapshot_response(
                snapshot,
                market=market,
                limit=limit,
            )
            _ensure_market_ranking_stock_masters(db, list(payload.get("items") or []))
            payload["items"] = enrich_market_ranking_sector_fields(
                db,
                list(payload.get("items") or []),
            )
            return payload
        except HTTPException:
            raise
        except Exception:
            logger.exception("Surge ranking snapshot load failed")
            fallback = _latest_complete_surge_ranking_snapshot(db)
            if fallback is not None:
                payload = _surge_ranking_snapshot_response(fallback, market=market, limit=limit)
                payload["items"] = enrich_market_ranking_sector_fields(
                    db,
                    list(payload.get("items") or []),
                )
                return payload
            try:
                _queue_complete_snapshot_refresh(db, SURGE_COMPLETE_SNAPSHOT_KEY)
            except Exception:
                logger.exception("Surge ranking cold-start refresh queue failed")
            raise HTTPException(
                status_code=503,
                detail="Complete surge ranking snapshot not available",
            )

    key = ("market_rankings", category, mode, market or "", limit)
    cached_payload = api_cache.get(key)
    try:
        if refresh or cached_payload is None:
            payload = build_market_rankings(
                db,
                category=category,
                market=market,
                limit=limit,
                refresh_live=refresh,
                mode=mode,
            )
            api_cache.set(key, payload, MARKET_RANKING_TTL_SECONDS)
            return payload
        return cached_payload
    except Exception:
        logging.getLogger(__name__).exception("Market ranking refresh failed")
        if cached_payload is not None:
            return cached_payload
        return {
            "category": category,
            "market": market,
            "mode": mode,
            "as_of": datetime.now(KST),
            "source": "unavailable",
            "universe_count": 0,
            "matching_count": 0,
            "items": [],
        }


@app.get("/market/rankings/returns")
def market_ranking_period_returns(
    codes: str = Query(..., min_length=6, max_length=699),
):
    parsed_codes = [code.strip().upper() for code in codes.split(",")]
    return {"items": build_market_period_returns(parsed_codes)}


@app.get("/market/recommendations", response_model=MarketRecommendationOut)
def market_recommendations(
    request: Request,
    response: Response,
    limit: int = Query(default=8, ge=1, le=20),
    candidate_limit: int = Query(default=50, ge=10, le=100),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "market_recommendations", limit=10, window_seconds=60)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    key = ("market_recommendations", limit, candidate_limit)
    if refresh:
        payload = build_recommendations(db, limit=limit, candidate_limit=candidate_limit, refresh_live=True)
        api_cache.set(
            key,
            payload,
            RECOMMENDATION_TTL_SECONDS
            if payload.get("items")
            else RECOMMENDATION_EMPTY_CACHE_TTL_SECONDS,
        )
        return payload
    cached = api_cache.get(key)
    if isinstance(cached, dict) and cached.get("items"):
        return cached
    if cached is not None:
        # An empty result is often a transient signal-refresh state. Expire it
        # before rebuilding so an old empty response cannot hide new picks for
        # the full recommendation cache window.
        api_cache.set(key, cached, 0)
    payload = build_recommendations(db, limit=limit, candidate_limit=candidate_limit)
    api_cache.set(
        key,
        payload,
        RECOMMENDATION_TTL_SECONDS
        if payload.get("items")
        else RECOMMENDATION_EMPTY_CACHE_TTL_SECONDS,
    )
    return payload


@app.get("/market/impact", response_model=MarketImpactOut)
def market_impact(
    request: Request,
    refresh: bool = Query(default=False),
):
    _enforce_rate_limit(request, "market_impact", limit=20, window_seconds=60)
    key = ("market_impact",)
    if refresh:
        payload = build_market_impact()
        api_cache.set(key, payload, MARKET_IMPACT_TTL_SECONDS)
        return payload
    return api_cache.get_or_set(key, MARKET_IMPACT_TTL_SECONDS, build_market_impact)


@app.get("/market/trends", response_model=TrendAnalysisOut)
def market_trends(
    request: Request,
    days: int = Query(default=7, ge=1, le=14),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "market_trends", limit=12, window_seconds=60)
    key = ("market_trends", days)
    if refresh:
        payload = build_trend_analysis(db, days=days)
        api_cache.set(key, payload, TREND_ANALYSIS_TTL_SECONDS)
        return payload
    return api_cache.get_or_set(key, TREND_ANALYSIS_TTL_SECONDS, lambda: build_trend_analysis(db, days=days))


@app.get("/market/trends/{event_id}/graph", response_model=TrendEventGraphOut)
def market_trend_graph(
    event_id: str,
    request: Request,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "market_trend_graph", limit=20, window_seconds=60)
    key = ("market_trend_graph", event_id)
    if refresh:
        payload = build_event_graph(db, event_id)
        api_cache.set(key, payload, TREND_GRAPH_TTL_SECONDS)
    else:
        payload = api_cache.get_or_set(key, TREND_GRAPH_TTL_SECONDS, lambda: build_event_graph(db, event_id))
    if not payload:
        raise HTTPException(status_code=404, detail="Trend event not found")
    return payload


@app.get("/macro", response_model=list[MacroObservationOut])
def macro_observations(
    source: Optional[str] = None,
    series_code: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    statement = select(MacroObservation).order_by(desc(MacroObservation.period)).limit(limit)
    if source:
        statement = statement.where(MacroObservation.source == source)
    if series_code:
        statement = statement.where(MacroObservation.series_code == series_code)
    return list(db.scalars(statement))


@app.get("/market/indices")
def market_indices(
    response: Response,
    limit: int = Query(default=30, ge=2, le=120),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    snapshot_key = f"{MARKET_INDICES_SNAPSHOT_PREFIX}{limit}"
    complete = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    if complete is None:
        if not settings.runs_collectors():
            _queue_cold_snapshot_or_503(
                db,
                snapshot_key,
                detail="Complete market index snapshot is being prepared",
            )
        payload = build_market_indices(db, limit=limit)
        if kis_rest_provider.is_configured():
            try:
                payload = merge_live_market_indices(payload, kis_rest_provider.fetch_market_indices())
            except Exception:
                logger.exception("KIS market index cold-start refresh failed")
        published = _publish_cold_snapshot_or_read_winner(
            db,
            snapshot_key,
            payload,
            fresh_for_seconds=_market_indices_fresh_seconds(),
            schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
            validator=_validate_market_indices_snapshot,
        )
        return published.payload
    if refresh or not complete.is_fresh:
        _queue_complete_snapshot_refresh(db, snapshot_key)
    return complete.payload


def _market_indices_fresh_seconds(now: Optional[datetime] = None) -> int:
    return 5 if is_korea_regular_market_session(now or datetime.now(KST)) else 30


def _validate_market_indices_snapshot(payload: Any) -> dict[str, Any]:
    candidate = _json_ready(payload)
    items = candidate.get("items") if isinstance(candidate, dict) else None
    actual = [str(item.get("code") or "") for item in items or []]
    if actual != ["KOSPI", "KOSDAQ"]:
        raise ValueError("Market index snapshot must contain KOSPI and KOSDAQ in order")
    for item in items:
        if item.get("current") is None or item.get("previous_close") is None:
            raise ValueError("Market index snapshot is missing current or previous values")
        if item.get("change") is None or item.get("change_rate") is None:
            raise ValueError("Market index snapshot is missing change values")
        points = item.get("points")
        if not isinstance(points, list) or not points:
            raise ValueError("Market index snapshot must retain chart history")
        if not item.get("as_of"):
            raise ValueError("Market index snapshot is missing its as-of date")
    return candidate


def _build_market_indices_snapshot(db: Session, snapshot_key: str) -> SnapshotBuild:
    limit = max(2, min(int(snapshot_key.removeprefix(MARKET_INDICES_SNAPSHOT_PREFIX)), 120))
    previous = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    stored_payload = build_market_indices(db, limit=limit)
    payload = previous.payload if previous is not None else stored_payload
    if kis_rest_provider.is_configured():
        live_items = kis_rest_provider.fetch_market_indices()
        if previous is not None and not live_items:
            raise RuntimeError("No live market indices were returned")
        payload = merge_live_market_indices(payload, live_items)
    return SnapshotBuild(
        payload=payload,
        fresh_for_seconds=_market_indices_fresh_seconds(),
        validator=_validate_market_indices_snapshot,
    )


@app.get("/market/global-assets")
def global_market_assets(
    response: Response,
    limit: int = Query(default=30, ge=2, le=120),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    snapshot_key = f"{GLOBAL_MARKET_ASSETS_SNAPSHOT_PREFIX}{limit}"
    complete = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    if complete is None:
        if not settings.runs_collectors():
            _queue_cold_snapshot_or_503(
                db,
                snapshot_key,
                detail="Complete global market snapshot is being prepared",
            )
        stored_payload = build_stored_global_market_assets(db, limit=limit)
        try:
            live_items = fetch_live_global_market_assets()
        except Exception:
            logger.exception("Global market asset cold-start refresh failed")
            live_items = []
        payload = merge_global_market_assets(stored_payload, live_items or [])
        published = _publish_cold_snapshot_or_read_winner(
            db,
            snapshot_key,
            payload,
            fresh_for_seconds=GLOBAL_MARKET_ASSETS_TTL_SECONDS,
            schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
            validator=_validate_global_market_assets_snapshot,
        )
        return published.payload
    if not complete.is_fresh:
        _queue_complete_snapshot_refresh(db, snapshot_key)
    return complete.payload


def _validate_global_market_assets_snapshot(payload: Any) -> dict[str, Any]:
    candidate = _json_ready(payload)
    items = candidate.get("items") if isinstance(candidate, dict) else None
    expected = [definition[0] for definition in GLOBAL_MARKET_DEFINITIONS]
    actual = [str(item.get("code") or "") for item in items or []]
    if actual != expected:
        raise ValueError("Global market snapshot must contain every configured asset in order")
    for item in items:
        if item.get("current") is None or item.get("previous_close") is None:
            raise ValueError("Global market snapshot is missing current or previous values")
        if item.get("change") is None or item.get("change_rate") is None:
            raise ValueError("Global market snapshot is missing change values")
        points = item.get("points")
        if not isinstance(points, list) or not points:
            raise ValueError("Global market snapshot must retain chart history")
        if not item.get("as_of"):
            raise ValueError("Global market snapshot is missing its as-of time")
    return candidate


def _build_global_market_assets_snapshot(db: Session, snapshot_key: str) -> SnapshotBuild:
    limit = max(2, min(int(snapshot_key.removeprefix(GLOBAL_MARKET_ASSETS_SNAPSHOT_PREFIX)), 120))
    previous = get_complete_snapshot(
        db,
        snapshot_key,
        schema_version=COMPLETE_SNAPSHOT_SCHEMA_VERSION,
    )
    stored_payload = build_stored_global_market_assets(db, limit=limit)
    base_payload = previous.payload if previous is not None else stored_payload
    live_items = fetch_live_global_market_assets()
    if previous is not None and not live_items:
        raise RuntimeError("No live global market assets were returned")
    payload = merge_global_market_assets(base_payload, live_items)
    return SnapshotBuild(
        payload=payload,
        fresh_for_seconds=GLOBAL_MARKET_ASSETS_TTL_SECONDS,
        validator=_validate_global_market_assets_snapshot,
    )


@app.get("/ingestions", response_model=list[IngestionRunOut])
def ingestions(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    statement = select(IngestionRun).order_by(desc(IngestionRun.started_at)).limit(limit)
    return list(db.scalars(statement))


@app.get("/briefings/status", response_model=BriefingRuntimeStatusOut)
def briefing_status():
    return briefing_runtime.status()


@app.get("/briefings/history", response_model=list[BriefingSnapshotSummaryOut])
def briefing_history(
    kind: str = Query(default="home"),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return list_briefing_snapshots(db, kind=kind, limit=limit)


@app.get("/briefings/latest", response_model=BriefingSnapshotOut)
def latest_briefing(
    kind: str = Query(default="home"),
    db: Session = Depends(get_db),
):
    snapshot = latest_briefing_snapshot(db, kind=kind)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Briefing not found")

    return BriefingSnapshotOut.model_validate(
        {
            "id": snapshot.id,
            "briefing_kind": snapshot.briefing_kind,
            "source": snapshot.source,
            "transport": snapshot.transport,
            "market_status": snapshot.market_status,
            "is_live": snapshot.is_live,
            "as_of": snapshot.as_of,
            "summary": snapshot.summary,
            "created_at": snapshot.created_at,
            "metrics": briefing_metrics(db, snapshot.id),
            "quotes": briefing_quotes(db, snapshot.id),
            "movers": briefing_movers(db, snapshot.id),
            "events": briefing_events(db, snapshot.id),
        }
    )


@app.get("/briefings/morning-money", response_model=MorningMoneyBriefingOut)
def morning_money_briefing(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    edition_key = money_briefing_edition().edition_key
    return morning_money_briefing_cache.get_or_set(
        ("current", edition_key),
        MORNING_MONEY_BRIEFING_CACHE_SECONDS,
        lambda: build_morning_money_briefing(db),
    )


@app.get(
    "/briefings/morning-money/history",
    response_model=list[MorningMoneyBriefingOut],
)
def morning_money_briefing_history(
    response: Response,
    days: int = Query(default=7, ge=1, le=7),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    edition_key = money_briefing_edition().edition_key
    return morning_money_briefing_cache.get_or_set(
        ("history", edition_key, days),
        MORNING_MONEY_HISTORY_CACHE_SECONDS,
        lambda: build_morning_money_briefing_history(db, days=days),
    )


@app.get("/research-reports", response_model=list[ResearchReportOut])
def research_reports(
    limit: int = Query(default=50, ge=1, le=500),
    stock_code: Optional[str] = None,
    category: Optional[str] = None,
    company_name: Optional[str] = None,
    broker_name: Optional[str] = None,
    opinion: Optional[str] = None,
    query: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    if stock_code:
        try:
            _ensure_stock_research_backfill(db, _normalize_stock_code(stock_code))
        except Exception as exc:
            logger.warning("Stock research backfill failed for %s: %s", stock_code, exc)
    return latest_research_reports(
        db,
        limit=limit,
        stock_code=stock_code,
        source_category=category,
        company_name=company_name,
        broker_name=broker_name,
        opinion=opinion,
        query=query,
        from_at=datetime.combine(from_date, time.min) if from_date else None,
        to_at=_end_of_day(to_date),
    )


@app.get("/disclosures", response_model=list[DisclosureItemOut])
def disclosures(
    limit: int = Query(default=50, ge=1, le=500),
    stock_code: Optional[str] = None,
    category: Optional[str] = None,
    company_name: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return latest_disclosures(
        db,
        limit=limit,
        stock_code=stock_code,
        category=category,
        company_name=company_name,
        from_at=datetime.combine(from_date, time.min) if from_date else None,
        to_at=_end_of_day(to_date),
    )


@app.get("/news-items", response_model=list[NewsItemOut])
def news_items(
    limit: int = Query(default=50, ge=1, le=500),
    category: Optional[str] = None,
    press_name: Optional[str] = None,
    query: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return [
        _news_item_payload(item)
        for item in latest_news_items(
            db,
            limit=limit,
            category=category,
            press_name=press_name,
            query=query,
            from_at=datetime.combine(from_date, time.min) if from_date else None,
            to_at=_end_of_day(to_date),
        )
    ]


@app.get("/stocks/{code}/news-items", response_model=list[NewsItemOut])
def stock_news_items(
    code: str,
    response: Response,
    limit: int = Query(default=20, ge=1, le=60),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    stock = db.get(StockMaster, code)
    if not stock or not stock.is_active:
        stock = _ensure_stock_master_from_naver(db, code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    response.headers["Cache-Control"] = "private, max-age=120, stale-while-revalidate=120"
    response.headers["X-Stock-News-Source"] = "naver-stock-code"
    return stock_news_item_payloads(db, stock.code, limit=limit)


@app.get("/insight/feed")
def insight_feed(
    research_limit: int = Query(default=200, ge=1, le=200),
    disclosure_limit: int = Query(default=200, ge=1, le=200),
    news_limit: int = Query(default=200, ge=1, le=200),
    company_brief_limit: int = Query(default=240, ge=1, le=500),
    db: Session = Depends(get_db),
):
    snapshot = latest_briefing_snapshot(db, kind="home")
    quote_rows = briefing_quotes(db, snapshot.id) if snapshot else []
    research_items = latest_research_reports(db, limit=research_limit)
    disclosure_items = latest_disclosures(db, limit=disclosure_limit)
    news_rows = latest_news_items(db, limit=news_limit)
    company_briefs = build_company_briefs(
        db,
        research_items=research_items,
        disclosure_items=disclosure_items,
        news_items=news_rows,
        limit=company_brief_limit,
    )
    price_codes: list[str] = []
    seen_codes: set[str] = set()
    for item in research_items:
        code = (item.stock_code or "").strip()
        if code and code not in seen_codes:
            price_codes.append(code)
            seen_codes.add(code)
    for item in company_briefs:
        code = (item.get("stock_code") or "").strip()
        if code and code not in seen_codes:
            price_codes.append(code)
            seen_codes.add(code)
    price_map = latest_prices_by_codes(
        db,
        price_codes,
    )
    return {
        "briefing": BriefingSnapshotSummaryOut.model_validate(snapshot).model_dump(mode="json") if snapshot else None,
        "research_reports": [
            ResearchReportOut.model_validate(item).model_dump(mode="json") for item in research_items
        ],
        "disclosures": [
            DisclosureItemOut.model_validate(item).model_dump(mode="json") for item in disclosure_items
        ],
        "news_items": [_news_item_payload(item) for item in news_rows],
        "company_briefs": [CompanyBriefOut.model_validate(item).model_dump(mode="json") for item in company_briefs],
        "briefing_quotes": [BriefingQuoteOut.model_validate(item).model_dump(mode="json") for item in quote_rows],
        "watch_codes": settings.briefing_watch_code_list(),
        "latest_prices": {
            code: {
                "trade_date": row.trade_date.isoformat(),
                "close": row.close,
            }
            for code, row in price_map.items()
        },
    }


@app.get("/company-briefs", response_model=list[CompanyBriefOut])
def company_briefs(
    research_limit: int = Query(default=200, ge=1, le=400),
    disclosure_limit: int = Query(default=200, ge=1, le=400),
    news_limit: int = Query(default=200, ge=1, le=400),
    limit: int = Query(default=240, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return build_company_briefs(
        db,
        research_items=latest_research_reports(db, limit=research_limit),
        disclosure_items=latest_disclosures(db, limit=disclosure_limit),
        news_items=latest_news_items(db, limit=news_limit),
        limit=limit,
    )
