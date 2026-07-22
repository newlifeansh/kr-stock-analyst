from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time as time_module
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from threading import RLock
from typing import Any, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
import websockets
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, get_db, init_db, recover_interrupted_ingestions
from app.integrations.toss import (
    BROKER_NAME,
    TossInvestError,
    _holding_rows,
    _order_row,
    _to_date,
    _to_decimal,
    get_toss_client,
    refresh_toss_order_detail,
    resolve_toss_account_seq,
    sync_toss_accounts as sync_toss_accounts_cache,
    sync_toss_holdings as sync_toss_holdings_cache,
    sync_toss_orders as sync_toss_orders_cache,
)
from app.meta import integration_payload, insight_cadence_payload, research_source_payload
from app.models import (
    BrokerOrder,
    DailyPrice,
    FinancialStatementLine,
    IngestionRun,
    InvestorFlow,
    MacroObservation,
    PushSubscription,
    StockMaster,
    WatchlistItem,
)
from app.repository import (
    briefing_events,
    briefing_metrics,
    briefing_movers,
    briefing_quotes,
    list_broker_accounts,
    list_broker_holdings,
    list_broker_orders,
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
    BrokerAccountOut,
    BrokerHoldingOut,
    BrokerOrderOut,
    BrokerSyncResultOut,
    CompanyBriefOut,
    DailyPriceOut,
    DisclosureItemOut,
    FinancialStatementLineOut,
    InsightCadenceOut,
    IntegrationMetaOut,
    IngestionRunOut,
    InvestorFlowOut,
    MacroObservationOut,
    MarketImpactOut,
    MarketRankingOut,
    MarketRecommendationOut,
    NewsItemOut,
    PushSubscriptionDeleteIn,
    PushSubscriptionIn,
    ResearchSourceOut,
    ResearchReportOut,
    StockAIAnalysisOut,
    StockOut,
    StockDashboardOut,
    TossBuyingPowerOut,
    TossOrderCreateIn,
    TossOrderModifyIn,
    TossOrderOperationOut,
    TossSellableQuantityOut,
    TossStatusOut,
    TossStockInfoOut,
    TrendAnalysisOut,
    TrendEventGraphOut,
    WatchlistOut,
    WatchlistUpdateIn,
)
from app.services.briefing import briefing_runtime
from app.collectors.briefing import KisRestBriefingProvider
from app.bootstrap import bootstrap_runtime_data
from app.mcp_server import build_insight_mcp_server, mcp_sdk_available
from app.services.company_briefs import build_company_briefs
from app.services.market_rankings import build_market_period_returns, build_market_rankings
from app.services.market_impact import build_market_impact
from app.services.recommendations import build_recommendations
from app.services.stock_ai_analysis import build_stock_ai_analysis
from app.services.stock_dashboard import build_stock_dashboard, ensure_stock_price_history
from app.services.kis_realtime import KisRealtimeQuoteProvider, parse_kis_stock_tick
from app.services.ttl_cache import TTLCache
from app.services.trends import build_event_graph, build_trend_analysis
from app.services.web_push import web_push_runtime
from app.services.us_market import (
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
STOCK_DASHBOARD_INDEX = STATIC_DIR / "dashboard" / "index.html"
PORTFOLIO_INDEX = STATIC_DIR / "portfolio" / "index.html"
DASHBOARD_MANIFEST = STATIC_DIR / "dashboard" / "manifest.webmanifest"
DASHBOARD_SERVICE_WORKER = STATIC_DIR / "dashboard" / "dashboard-sw.js"
NASDAQ_DASHBOARD_INDEX = STATIC_DIR / "nasdaq" / "index.html"
NASDAQ_MANIFEST = STATIC_DIR / "nasdaq" / "manifest.webmanifest"
NASDAQ_SERVICE_WORKER = STATIC_DIR / "nasdaq" / "dashboard-sw.js"
api_cache = TTLCache(maxsize=1024)
kis_realtime_provider = KisRealtimeQuoteProvider(settings)
kis_rest_provider = KisRestBriefingProvider(settings)
mcp_server = build_insight_mcp_server(settings) if settings.mcp_enabled else None
kis_quote_subscribers: dict[str, set[asyncio.Queue]] = {}
kis_quote_lock = asyncio.Lock()
kis_realtime_hub_task: Optional[asyncio.Task] = None
kis_realtime_control_queue: asyncio.Queue = asyncio.Queue()
presence_page_clients: dict[str, set[WebSocket]] = {}
presence_client_pages: dict[WebSocket, str] = {}
presence_lock = asyncio.Lock()
write_session_cache = TTLCache(maxsize=8192)
rate_limit_lock = RLock()
rate_limit_windows: dict[tuple[str, str], list[float]] = {}

STOCK_DASHBOARD_TTL_SECONDS = 120
MARKET_RANKING_TTL_SECONDS = 120
MARKET_IMPACT_TTL_SECONDS = 900
RECOMMENDATION_TTL_SECONDS = 600
TREND_ANALYSIS_TTL_SECONDS = 120
TREND_GRAPH_TTL_SECONDS = 300
PRE_MARKET_QUOTE_TTL_SECONDS = 15
WRITE_SESSION_COOKIE = "sn_write_session"
WRITE_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
LOCAL_ONLY_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}
KST = ZoneInfo("Asia/Seoul")


async def _run_bootstrap_task() -> None:
    try:
        await asyncio.to_thread(
            bootstrap_runtime_data,
            settings,
            force_refresh=settings.bootstrap_force_refresh,
        )
    except Exception:  # pragma: no cover - operational safeguard
        logger.exception("Background bootstrap failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    recover_interrupted_ingestions()
    bootstrap_task: asyncio.Task | None = None
    async with AsyncExitStack() as stack:
        if mcp_server is not None:
            await stack.enter_async_context(mcp_server.session_manager.run())
        await briefing_runtime.start()
        await web_push_runtime.start()
        if settings.bootstrap_on_start:
            bootstrap_task = asyncio.create_task(_run_bootstrap_task())
        try:
            yield
        finally:
            if bootstrap_task is not None:
                bootstrap_task.cancel()
                with suppress(asyncio.CancelledError):
                    await bootstrap_task
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
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
if mcp_server is not None:
    app.mount("/mcp", mcp_server.streamable_http_app())


@app.get("/")
def root_shell():
    return RedirectResponse(url="/dashboard?view=trend", status_code=307)


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
            raise HTTPException(status_code=429, detail="요청이 많습니다. 잠시 후 다시 시도해주세요.")
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


def _normalize_write_scope(share_id: str, market: Optional[str] = None) -> str:
    normalized_id = _normalize_watchlist_id(share_id)
    if str(market or "").strip().lower() == "us":
        return f"us.{normalized_id}"
    return normalized_id


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


@app.middleware("http")
async def _protect_internal_routes(request: Request, call_next):
    if request.url.path.startswith("/toss") and not _request_is_local_console(request):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return await call_next(request)


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


@app.get("/dashboard")
@app.get("/dashboard/{code}")
def stock_dashboard_shell():
    if not STOCK_DASHBOARD_INDEX.exists():
        raise HTTPException(status_code=404, detail="Stock dashboard UI not found")
    return HTMLResponse(STOCK_DASHBOARD_INDEX.read_text(encoding="utf-8"))


@app.get("/portfolio")
def portfolio_shell():
    if not PORTFOLIO_INDEX.exists():
        raise HTTPException(status_code=404, detail="Portfolio UI not found")
    return HTMLResponse(PORTFOLIO_INDEX.read_text(encoding="utf-8"))


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


@app.get("/dashboard-sw.js")
def stock_dashboard_service_worker():
    if not DASHBOARD_SERVICE_WORKER.exists():
        raise HTTPException(status_code=404, detail="Dashboard service worker not found")
    return FileResponse(DASHBOARD_SERVICE_WORKER, media_type="application/javascript")


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
    return {"status": "ok", "app": settings.app_name}


@app.get("/readyz")
def readyz() -> dict[str, object]:
    with SessionLocal() as db:
        db.execute(select(1))
    return {"status": "ok", "app": settings.app_name, "database_ok": True}


WATCHLIST_ID_RE = re.compile(r"^[0-9A-Za-z가-힣_.-]{2,40}$")


def _normalize_watchlist_id(share_id: str) -> str:
    cleaned = share_id.strip()
    if not WATCHLIST_ID_RE.match(cleaned):
        raise HTTPException(status_code=422, detail="Watchlist ID must be 2-40 characters: Korean, letters, numbers, _, -, .")
    return cleaned


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
def get_watchlist(share_id: str, db: Session = Depends(get_db)):
    return _watchlist_response(db, _normalize_watchlist_id(share_id))


@app.put("/watchlists/{share_id}", response_model=WatchlistOut)
def put_watchlist(share_id: str, payload: WatchlistUpdateIn, request: Request, db: Session = Depends(get_db)):
    normalized_id = _normalize_watchlist_id(share_id)
    _require_write_access(request, normalized_id)
    seen: set[str] = set()
    rows: list[WatchlistItem] = []
    for item in payload.items:
        code = _normalize_stock_code(item.code)
        if not code or code in seen:
            continue
        seen.add(code)
        master = db.get(StockMaster, code)
        rows.append(
            WatchlistItem(
                share_id=normalized_id,
                code=code,
                name=(item.name or (master.name if master else code)).strip(),
                market=item.market or (master.market if master else None),
                sort_order=len(rows),
            )
        )
    db.execute(delete(WatchlistItem).where(WatchlistItem.share_id == normalized_id))
    db.add_all(rows)
    db.commit()
    return _watchlist_response(db, normalized_id)


@app.get("/push/config")
def push_config():
    return {
        "enabled": web_push_runtime.configured,
        "public_key": settings.web_push_vapid_public_key if web_push_runtime.configured else None,
        "conditions": ["price_move", "disclosure_report", "major_event"],
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
    return {"enabled": subscription is not None}


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
            user_agent=str(request.headers.get("user-agent") or "")[:500] or None,
        )
        db.add(subscription)
    else:
        if subscription.share_id != normalized_id or not subscription.enabled:
            subscription.created_at = datetime.utcnow()
        subscription.share_id = normalized_id
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth
        subscription.user_agent = str(request.headers.get("user-agent") or "")[:500] or None
        subscription.enabled = True
    db.commit()
    db.refresh(subscription)
    test_sent = web_push_runtime.send_test(db, subscription) if should_test else False
    return {"enabled": True, "test_sent": test_sent}


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
def market_us_sector_moves(refresh: bool = Query(default=False)):
    try:
        return us_sector_moves(refresh=refresh)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="US sector moves not available") from exc


@app.websocket("/ws/market/us-sector-moves")
async def market_us_sector_moves_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = await asyncio.to_thread(us_sector_moves, True)
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


def _toss_http_error(exc: TossInvestError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.to_detail())


def _toss_status_payload() -> dict[str, object]:
    return {
        "enabled": settings.toss_enabled,
        "configured": bool(settings.toss_client_id and settings.toss_client_secret),
        "sync_holdings_enabled": settings.toss_sync_holdings_enabled,
        "base_url": settings.toss_base_url,
        "account_no": settings.toss_account_no,
        "account_seq": settings.toss_account_seq,
        "poll_seconds": settings.toss_poll_seconds,
        "order_poll_seconds": settings.toss_order_poll_seconds,
    }


def _live_stock_payload(item: dict[str, object]) -> dict[str, object]:
    return {
        "symbol": item.get("symbol"),
        "name": item.get("name"),
        "english_name": item.get("englishName"),
        "isin_code": item.get("isinCode"),
        "market": item.get("market"),
        "security_type": item.get("securityType"),
        "is_common_share": item.get("isCommonShare"),
        "status": item.get("status"),
        "currency": item.get("currency"),
        "list_date": _to_date(item.get("listDate")),
        "delist_date": _to_date(item.get("delistDate")),
        "shares_outstanding": _to_decimal(item.get("sharesOutstanding")),
        "leverage_factor": _to_decimal(item.get("leverageFactor")),
    }


def _best_effort_refresh_order(
    db: Session,
    client,
    order_id: str,
    account_seq: int,
) -> None:
    try:
        refresh_toss_order_detail(
            db,
            order_id,
            account_seq=account_seq,
            client=client,
            settings=settings,
        )
    except TossInvestError:
        pass


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
    if not re.fullmatch(r"\d{6}", code):
        return None
    try:
        response = requests.get(
            "https://finance.naver.com/item/main.naver",
            params={"code": code},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
    except Exception:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    name_node = soup.select_one("div.wrap_company h2 a")
    name = name_node.get_text(strip=True) if name_node else ""
    if not name:
        return None
    market = "KOSDAQ" if soup.select_one("img.kosdaq") else "KOSPI" if soup.select_one("img.kospi") else ""
    if not market:
        market_text = soup.get_text(" ", strip=True)
        market = "KOSDAQ" if "코스닥" in market_text else "KOSPI" if "코스피" in market_text else "UNKNOWN"
    return {"code": code, "name": name, "market": market}


def _ensure_stock_master_from_naver(db: Session, code: str) -> Optional[StockMaster]:
    code = _normalize_stock_code(code)
    item = db.get(StockMaster, code)
    if item:
        return item
    identity = _fetch_naver_stock_identity(code)
    if not identity:
        return None
    item = StockMaster(
        code=identity["code"],
        name=identity["name"],
        market=identity["market"],
        last_seen_date=date.today(),
    )
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


@app.get("/toss/status", response_model=TossStatusOut)
def toss_status():
    return _toss_status_payload()


@app.get("/toss/accounts", response_model=list[BrokerAccountOut])
def toss_accounts(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return list_broker_accounts(db, BROKER_NAME, limit=limit)


@app.get("/toss/accounts/live", response_model=list[BrokerAccountOut])
def toss_accounts_live():
    client = get_toss_client(settings=settings)
    try:
        accounts = client.get_accounts()
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    return [BrokerAccountOut.model_validate({"id": 0, **row, "updated_at": datetime.utcnow()}) for row in [
        {
            "broker_name": BROKER_NAME,
            "account_seq": int(account["accountSeq"]),
            "account_no": account.get("accountNo"),
            "account_type": account.get("accountType"),
            "synced_at": datetime.utcnow(),
        }
        for account in accounts
    ]]


@app.post("/toss/sync/accounts", response_model=BrokerSyncResultOut)
def toss_sync_accounts(db: Session = Depends(get_db)):
    try:
        rows_loaded = sync_toss_accounts_cache(db, settings=settings)
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    return {
        "broker_name": BROKER_NAME,
        "dataset": "accounts",
        "rows_loaded": rows_loaded,
        "message": "Toss account cache refreshed.",
    }


@app.get("/toss/holdings", response_model=list[BrokerHoldingOut])
def toss_holdings(
    account_seq: Optional[int] = None,
    symbol: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    return list_broker_holdings(db, BROKER_NAME, account_seq=account_seq, symbol=symbol, limit=limit)


@app.get("/toss/holdings/live", response_model=list[BrokerHoldingOut])
def toss_holdings_live(
    account_seq: Optional[int] = None,
    symbol: Optional[str] = None,
):
    client = get_toss_client(settings=settings)
    try:
        resolved_account_seq = resolve_toss_account_seq(client, settings, explicit_account_seq=account_seq)
        overview = client.get_holdings(resolved_account_seq, symbol=symbol)
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    return [
        BrokerHoldingOut.model_validate({"id": 0, **row, "updated_at": datetime.utcnow()})
        for row in _holding_rows(
            resolved_account_seq,
            overview.get("items") or [],
        )
    ]


@app.post("/toss/sync/holdings", response_model=BrokerSyncResultOut)
def toss_sync_holdings(
    account_seq: Optional[int] = None,
    symbol: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        rows_loaded = sync_toss_holdings_cache(
            db,
            account_seq=account_seq,
            symbol=symbol,
            settings=settings,
        )
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    return {
        "broker_name": BROKER_NAME,
        "dataset": "holdings",
        "rows_loaded": rows_loaded,
        "account_seq": account_seq,
        "message": "Toss holdings cache refreshed.",
    }


@app.get("/toss/orders", response_model=list[BrokerOrderOut])
def toss_orders(
    account_seq: Optional[int] = None,
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return list_broker_orders(
        db,
        BROKER_NAME,
        account_seq=account_seq,
        status=status,
        symbol=symbol,
        limit=limit,
    )


@app.get("/toss/orders/live", response_model=list[BrokerOrderOut])
def toss_orders_live(
    account_seq: Optional[int] = None,
    status: str = Query(default="OPEN"),
):
    client = get_toss_client(settings=settings)
    try:
        resolved_account_seq = resolve_toss_account_seq(client, settings, explicit_account_seq=account_seq)
        page = client.get_orders(resolved_account_seq, status=status, limit=100)
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    orders = page.get("orders") or []
    return [
        BrokerOrderOut.model_validate(
            {
                "id": 0,
                **_order_row(
                    resolved_account_seq,
                    item,
                ),
                "updated_at": datetime.utcnow(),
            }
        )
        for item in orders
    ]


@app.post("/toss/sync/orders", response_model=BrokerSyncResultOut)
def toss_sync_orders(
    account_seq: Optional[int] = None,
    status: str = Query(default="OPEN"),
    db: Session = Depends(get_db),
):
    try:
        rows_loaded = sync_toss_orders_cache(
            db,
            account_seq=account_seq,
            status=status,
            settings=settings,
        )
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    return {
        "broker_name": BROKER_NAME,
        "dataset": "orders",
        "rows_loaded": rows_loaded,
        "account_seq": account_seq,
        "message": f"Toss order cache refreshed for status={status}.",
    }


@app.get("/toss/orders/{order_id}", response_model=BrokerOrderOut)
def toss_order_detail_cached(order_id: str, db: Session = Depends(get_db)):
    item = db.scalar(
        select(BrokerOrder).where(
            BrokerOrder.broker_name == BROKER_NAME,
            BrokerOrder.order_id == order_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Order not found")
    return item


@app.get("/toss/orders/{order_id}/live", response_model=BrokerOrderOut)
def toss_order_detail_live(
    order_id: str,
    account_seq: Optional[int] = None,
    db: Session = Depends(get_db),
):
    try:
        return refresh_toss_order_detail(
            db,
            order_id,
            account_seq=account_seq,
            settings=settings,
        )
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc


@app.post("/toss/orders", response_model=TossOrderOperationOut)
def toss_create_order(
    payload: TossOrderCreateIn,
    db: Session = Depends(get_db),
):
    client = get_toss_client(settings=settings)
    try:
        resolved_account_seq = resolve_toss_account_seq(client, settings, explicit_account_seq=payload.account_seq)
        request_body = {
            "symbol": payload.symbol,
            "side": payload.side,
            "orderType": payload.order_type,
            "confirmHighValueOrder": payload.confirm_high_value_order,
        }
        if payload.client_order_id:
            request_body["clientOrderId"] = payload.client_order_id
        if payload.time_in_force:
            request_body["timeInForce"] = payload.time_in_force
        if payload.quantity is not None:
            request_body["quantity"] = payload.quantity
        if payload.price is not None:
            request_body["price"] = payload.price
        if payload.order_amount is not None:
            request_body["orderAmount"] = payload.order_amount
        result = client.create_order(resolved_account_seq, request_body)
        _best_effort_refresh_order(db, client, result["orderId"], resolved_account_seq)
        return {
            "order_id": result["orderId"],
            "client_order_id": result.get("clientOrderId"),
        }
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc


@app.post("/toss/orders/{order_id}/modify", response_model=TossOrderOperationOut)
def toss_modify_order(
    order_id: str,
    payload: TossOrderModifyIn,
    db: Session = Depends(get_db),
):
    client = get_toss_client(settings=settings)
    try:
        resolved_account_seq = resolve_toss_account_seq(client, settings, explicit_account_seq=payload.account_seq)
        request_body = {
            "orderType": payload.order_type,
            "confirmHighValueOrder": payload.confirm_high_value_order,
        }
        if payload.quantity is not None:
            request_body["quantity"] = payload.quantity
        if payload.price is not None:
            request_body["price"] = payload.price
        result = client.modify_order(resolved_account_seq, order_id, request_body)
        _best_effort_refresh_order(db, client, result["orderId"], resolved_account_seq)
        return {"order_id": result["orderId"]}
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc


@app.post("/toss/orders/{order_id}/cancel", response_model=TossOrderOperationOut)
def toss_cancel_order(
    order_id: str,
    account_seq: Optional[int] = None,
    db: Session = Depends(get_db),
):
    client = get_toss_client(settings=settings)
    try:
        resolved_account_seq = resolve_toss_account_seq(client, settings, explicit_account_seq=account_seq)
        result = client.cancel_order(resolved_account_seq, order_id)
        _best_effort_refresh_order(db, client, result["orderId"], resolved_account_seq)
        return {"order_id": result["orderId"]}
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc


@app.get("/toss/buying-power", response_model=TossBuyingPowerOut)
def toss_buying_power(
    currency: str = Query(...),
    account_seq: Optional[int] = None,
):
    client = get_toss_client(settings=settings)
    try:
        resolved_account_seq = resolve_toss_account_seq(client, settings, explicit_account_seq=account_seq)
        result = client.get_buying_power(resolved_account_seq, currency)
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    return {
        "currency": result["currency"],
        "cash_buying_power": _to_decimal(result["cashBuyingPower"]),
    }


@app.get("/toss/sellable-quantity", response_model=TossSellableQuantityOut)
def toss_sellable_quantity(
    symbol: str = Query(...),
    account_seq: Optional[int] = None,
):
    client = get_toss_client(settings=settings)
    try:
        resolved_account_seq = resolve_toss_account_seq(client, settings, explicit_account_seq=account_seq)
        result = client.get_sellable_quantity(resolved_account_seq, symbol)
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    return {"sellable_quantity": _to_decimal(result["sellableQuantity"])}


@app.get("/toss/stocks", response_model=list[TossStockInfoOut])
def toss_stock_lookup(
    symbols: str = Query(..., description="Comma-separated symbols"),
):
    client = get_toss_client(settings=settings)
    try:
        items = client.get_stocks(symbols.split(","))
    except TossInvestError as exc:
        raise _toss_http_error(exc) from exc
    return [_live_stock_payload(item) for item in items]


@app.get("/stocks", response_model=list[StockOut])
def stocks(
    market: Optional[str] = None,
    limit: int = Query(default=5000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    return list_stocks(db, market=market, limit=limit)


@app.get("/stocks/resolve", response_model=StockOut)
def resolve_stock(
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    cleaned = query.strip()
    terms = _stock_query_terms(cleaned)
    code = _normalize_stock_code(cleaned)
    item = db.get(StockMaster, code)
    if not item:
        item = _ensure_stock_master_from_naver(db, code)
    if not item:
        item = db.scalar(select(StockMaster).where(StockMaster.name == cleaned).limit(1))
    if not item:
        candidates = list(
            db.scalars(
                select(StockMaster)
                .where(or_(StockMaster.name.contains(cleaned), StockMaster.code.startswith(code)))
                .order_by(StockMaster.market, StockMaster.code)
                .limit(5000)
            )
        )
        if not candidates:
            candidates = list(db.scalars(select(StockMaster).order_by(StockMaster.market, StockMaster.code).limit(5000)))
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
            .where(or_(StockMaster.name.contains(cleaned), StockMaster.code.startswith(code)))
            .order_by(StockMaster.market, StockMaster.code)
            .limit(5000)
        )
    )
    if not candidates:
        candidates = [
            item
            for item in db.scalars(select(StockMaster).order_by(StockMaster.market, StockMaster.code).limit(5000))
            if any(term in _normalize_stock_query(item.name) for term in terms) or code in _normalize_stock_code(item.code)
        ]

    exact_code = db.get(StockMaster, code)
    exact_name = db.scalar(select(StockMaster).where(StockMaster.name == cleaned).limit(1))
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
    return sorted(unique.values(), key=lambda item: _stock_search_sort_key(item, cleaned, market_caps))[:limit]


@app.get("/stocks/{code}", response_model=StockOut)
def stock_detail(code: str, db: Session = Depends(get_db)):
    code = _normalize_stock_code(code)
    item = db.get(StockMaster, code)
    if not item:
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


def _quote_poll_interval_seconds() -> int:
    now = datetime.now(KST).time()
    if time(8, 0) <= now <= time(9, 5) or time(15, 20) <= now <= time(15, 45):
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


def _pre_market_quote(code: str) -> dict[str, Any]:
    key = ("pre_market_quote", code)
    return api_cache.get_or_set(key, PRE_MARKET_QUOTE_TTL_SECONDS, lambda: _fetch_pre_market_quote(code))


def _enrich_pre_market_quote(payload: Optional[dict[str, Any]], code: str) -> None:
    if not payload or not isinstance(payload.get("quote"), dict):
        return
    payload["quote"].update(_pre_market_quote(code))


@app.get("/stocks/{code}/dashboard", response_model=StockDashboardOut)
def stock_dashboard(
    code: str,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    code = _normalize_stock_code(code)
    key = ("stock_dashboard", code)
    if not db.get(StockMaster, code):
        _ensure_stock_master_from_naver(db, code)
    if refresh:
        ensure_stock_price_history(db, code)
        payload = build_stock_dashboard(db, code, refresh_live=True)
        if payload:
            api_cache.set(key, payload, STOCK_DASHBOARD_TTL_SECONDS)
    else:
        payload = api_cache.get_or_set(key, STOCK_DASHBOARD_TTL_SECONDS, lambda: build_stock_dashboard(db, code))
    if not payload:
        raise HTTPException(status_code=404, detail="Stock not found")
    _enrich_pre_market_quote(payload, code)
    return payload


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


def _stock_quote_stream_payload(code: str) -> Optional[dict[str, object]]:
    interval_seconds = _quote_poll_interval_seconds()
    with SessionLocal() as db:
        normalized = _normalize_stock_code(code)
        if not db.get(StockMaster, normalized):
            _ensure_stock_master_from_naver(db, normalized)
        dashboard = build_stock_dashboard(db, normalized, refresh_live=True)
        if not dashboard:
            return None
        _enrich_pre_market_quote(dashboard, normalized)
        return _json_ready(
            {
                "type": "quote",
                "code": dashboard["code"],
                "name": dashboard["name"],
                "market": dashboard["market"],
                "as_of": dashboard["as_of"],
                "source": "naver_polling",
                "interval_seconds": interval_seconds,
                "quote": dashboard["quote"],
            }
        )


async def _send_polling_quote(websocket: WebSocket, code: str) -> bool:
    payload = await asyncio.to_thread(_stock_quote_stream_payload, code)
    if payload is None:
        await websocket.send_json({"type": "error", "message": "Stock quote not found"})
        return False
    await websocket.send_json(payload)
    return True


def _kis_realtime_payload(code: str, tick: dict[str, object]) -> dict[str, object]:
    quote = {
        "trade_date": date.today(),
        "price": tick.get("price"),
        "change_value": tick.get("change_value"),
        "change_rate": tick.get("change_rate"),
        "volume": tick.get("volume"),
        "trading_value": tick.get("trading_value"),
        "market_cap": None,
    }
    quote.update(_pre_market_quote(code))
    return _json_ready(
        {
            "type": "quote",
            "code": code,
            "as_of": datetime.now(KST),
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


async def _broadcast_kis_quote(code: str, payload: dict[str, object]) -> None:
    queues = list(kis_quote_subscribers.get(code, set()))
    for queue in queues:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass


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
                    "tr_id": "H0STCNT0",
                    "tr_key": code,
                }
            },
        },
        ensure_ascii=False,
    )


async def _send_kis_subscription(websocket, code: str, subscribe: bool = True) -> None:
    await websocket.send(_kis_subscription_message(code, subscribe=subscribe))


async def _broadcast_kis_status_to_active(status: str, message: str) -> None:
    for code in list(kis_quote_subscribers):
        await _broadcast_kis_quote(code, _kis_status_payload(code, status, message))


async def _kis_realtime_hub_worker() -> None:
    subscribed: set[str] = set()
    try:
        while kis_quote_subscribers:
            try:
                approval_key = await kis_realtime_provider.approval_key()
                kis_realtime_provider._approval_key = approval_key
                async with websockets.connect(
                    kis_realtime_provider._websocket_url(),
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                ) as kis_socket:
                    subscribed.clear()
                    for active_code in list(kis_quote_subscribers):
                        await _send_kis_subscription(kis_socket, active_code, subscribe=True)
                        subscribed.add(active_code)

                    receive_task = asyncio.create_task(kis_socket.recv())
                    control_task = asyncio.create_task(kis_realtime_control_queue.get())
                    try:
                        while kis_quote_subscribers:
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
                                            await _broadcast_kis_status_to_active("fallback", body.get("msg1") or body.get("msg_cd") or "KIS realtime request failed")
                                else:
                                    tick = parse_kis_stock_tick(raw)
                                    tick_code = str(tick.get("code")) if tick else ""
                                    if tick_code:
                                        await _broadcast_kis_quote(tick_code, _kis_realtime_payload(tick_code, tick))
                                receive_task = asyncio.create_task(kis_socket.recv())
                            if control_task in done:
                                command, control_code = control_task.result()
                                if command == "subscribe" and control_code not in subscribed and control_code in kis_quote_subscribers:
                                    await _send_kis_subscription(kis_socket, control_code, subscribe=True)
                                    subscribed.add(control_code)
                                elif command == "unsubscribe" and control_code in subscribed:
                                    await _send_kis_subscription(kis_socket, control_code, subscribe=False)
                                    subscribed.discard(control_code)
                                control_task = asyncio.create_task(kis_realtime_control_queue.get())
                    finally:
                        for task in (receive_task, control_task):
                            if not task.done():
                                task.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await _broadcast_kis_status_to_active("fallback", str(exc))
                await asyncio.sleep(10)
    finally:
        subscribed.clear()
        async with kis_quote_lock:
            global kis_realtime_hub_task
            if kis_realtime_hub_task is asyncio.current_task():
                kis_realtime_hub_task = None


async def _subscribe_kis_quote(code: str) -> Optional[asyncio.Queue]:
    if not kis_realtime_provider.is_configured():
        return None
    queue: asyncio.Queue = asyncio.Queue(maxsize=20)
    async with kis_quote_lock:
        global kis_realtime_hub_task
        subscribers = kis_quote_subscribers.setdefault(code, set())
        subscribers.add(queue)
        if kis_realtime_hub_task is None or kis_realtime_hub_task.done():
            kis_realtime_hub_task = asyncio.create_task(_kis_realtime_hub_worker())
        await kis_realtime_control_queue.put(("subscribe", code))
    return queue


async def _unsubscribe_kis_quote(code: str, queue: Optional[asyncio.Queue]) -> None:
    if queue is None:
        return
    async with kis_quote_lock:
        subscribers = kis_quote_subscribers.get(code)
        if not subscribers:
            return
        subscribers.discard(queue)
        if subscribers:
            return
        kis_quote_subscribers.pop(code, None)
        await kis_realtime_control_queue.put(("unsubscribe", code))
        if not kis_quote_subscribers:
            global kis_realtime_hub_task
            if kis_realtime_hub_task and not kis_realtime_hub_task.done():
                kis_realtime_hub_task.cancel()


@app.websocket("/ws/stocks/{code}/quote")
async def stock_quote_stream(websocket: WebSocket, code: str):
    await websocket.accept()
    normalized = _normalize_stock_code(code)
    kis_queue = await _subscribe_kis_quote(normalized)
    try:
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


@app.get("/stocks/{code}/ai-analysis", response_model=StockAIAnalysisOut)
def stock_ai_analysis(
    code: str,
    request: Request,
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "stock_ai_analysis", limit=20, window_seconds=60)
    code = _normalize_stock_code(code)
    key = ("stock_dashboard", code)
    if not db.get(StockMaster, code):
        _ensure_stock_master_from_naver(db, code)
    if refresh:
        ensure_stock_price_history(db, code)
        dashboard = build_stock_dashboard(db, code, refresh_live=True)
        if dashboard:
            api_cache.set(key, dashboard, STOCK_DASHBOARD_TTL_SECONDS)
    else:
        dashboard = api_cache.get_or_set(key, STOCK_DASHBOARD_TTL_SECONDS, lambda: build_stock_dashboard(db, code))
    if not dashboard:
        raise HTTPException(status_code=404, detail="Stock not found")
    return build_stock_ai_analysis(dashboard)


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
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    investor_type: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
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


@app.get("/market/rankings", response_model=MarketRankingOut)
def market_rankings(
    category: str = Query(default="surge", pattern="^(surge|trading_value|valuation|momentum|sentiment)$"),
    market: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=3000),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    key = ("market_rankings", category, market or "", limit)
    if refresh:
        payload = build_market_rankings(db, category=category, market=market, limit=limit, refresh_live=True)
        api_cache.set(key, payload, MARKET_RANKING_TTL_SECONDS)
        return payload
    return api_cache.get_or_set(
        key,
        MARKET_RANKING_TTL_SECONDS,
        lambda: build_market_rankings(db, category=category, market=market, limit=limit),
    )


@app.get("/market/rankings/returns")
def market_ranking_period_returns(
    codes: str = Query(..., min_length=6, max_length=699),
):
    parsed_codes = [code.strip().upper() for code in codes.split(",")]
    return {"items": build_market_period_returns(parsed_codes)}


@app.get("/market/recommendations", response_model=MarketRecommendationOut)
def market_recommendations(
    request: Request,
    limit: int = Query(default=8, ge=1, le=20),
    candidate_limit: int = Query(default=50, ge=10, le=100),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(request, "market_recommendations", limit=10, window_seconds=60)
    key = ("market_recommendations", limit, candidate_limit)
    if refresh:
        payload = build_recommendations(db, limit=limit, candidate_limit=candidate_limit, refresh_live=True)
        api_cache.set(key, payload, RECOMMENDATION_TTL_SECONDS)
        return payload
    return api_cache.get_or_set(
        key,
        RECOMMENDATION_TTL_SECONDS,
        lambda: build_recommendations(db, limit=limit, candidate_limit=candidate_limit),
    )


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
    return latest_news_items(
        db,
        limit=limit,
        category=category,
        press_name=press_name,
        query=query,
        from_at=datetime.combine(from_date, time.min) if from_date else None,
        to_at=_end_of_day(to_date),
    )


@app.get("/insight/feed")
def insight_feed(
    request: Request,
    research_limit: int = Query(default=200, ge=1, le=200),
    disclosure_limit: int = Query(default=200, ge=1, le=200),
    news_limit: int = Query(default=200, ge=1, le=200),
    company_brief_limit: int = Query(default=240, ge=1, le=500),
    account_limit: int = Query(default=10, ge=1, le=50),
    holding_limit: int = Query(default=100, ge=1, le=500),
    order_limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    include_toss = _request_is_local_console(request)
    snapshot = latest_briefing_snapshot(db, kind="home")
    quote_rows = briefing_quotes(db, snapshot.id) if snapshot else []
    research_items = latest_research_reports(db, limit=research_limit)
    disclosure_items = latest_disclosures(db, limit=disclosure_limit)
    news_rows = latest_news_items(db, limit=news_limit)
    broker_accounts = list_broker_accounts(db, BROKER_NAME, limit=account_limit) if include_toss else []
    broker_holdings = list_broker_holdings(db, BROKER_NAME, limit=holding_limit) if include_toss else []
    broker_orders = list_broker_orders(db, BROKER_NAME, limit=order_limit) if include_toss else []
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
        "news_items": [NewsItemOut.model_validate(item).model_dump(mode="json") for item in news_rows],
        "company_briefs": [CompanyBriefOut.model_validate(item).model_dump(mode="json") for item in company_briefs],
        "briefing_quotes": [BriefingQuoteOut.model_validate(item).model_dump(mode="json") for item in quote_rows],
        "watch_codes": settings.briefing_watch_code_list(),
        "toss_status": _toss_status_payload() if include_toss else None,
        "toss_accounts": [BrokerAccountOut.model_validate(item).model_dump(mode="json") for item in broker_accounts],
        "toss_holdings": [BrokerHoldingOut.model_validate(item).model_dump(mode="json") for item in broker_holdings],
        "toss_orders": [BrokerOrderOut.model_validate(item).model_dump(mode="json") for item in broker_orders],
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
