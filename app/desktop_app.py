from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import websockets
from fastapi import Cookie, FastAPI, HTTPException, Request, Response as FastAPIResponse, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from urllib.parse import quote, urlsplit, urlunsplit


STATIC_DIR = Path(__file__).resolve().parent / "static"
DESKTOP_INDEX = STATIC_DIR / "desktop" / "index.html"
DESKTOP_SERVICE_WORKER = STATIC_DIR / "desktop" / "desktop-sw.js"
UPSTREAM_BASE = os.getenv("DESKTOP_UPSTREAM_BASE", "https://secretnote.cloud").rstrip("/")
PROXY_TIMEOUT = httpx.Timeout(90.0, connect=15.0)
DEFAULT_DOCUMENT_TITLE = "한국증시 비밀노트"
DESKTOP_SESSION_COOKIE = "sn_desktop_session"
DESKTOP_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
DESKTOP_SESSION_SECRET = os.getenv("DESKTOP_SESSION_SECRET", "secret-note-desktop-local-development")
WATCHLIST_ID_RE = re.compile(r"^[0-9A-Za-z가-힣_.-]{2,40}$")
STOCK_CODE_RE = re.compile(r"^[0-9A-Za-z.-]{1,12}$")
DEFAULT_DATABASE_PATH = Path(os.getenv("DESKTOP_DATA_DIR", Path(__file__).resolve().parents[1] / "data")) / "desktop_preferences.db"
DESKTOP_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+pysqlite:///{DEFAULT_DATABASE_PATH}")
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
}

desktop_metadata = MetaData()
desktop_preferences = Table(
    "desktop_user_preferences",
    desktop_metadata,
    Column("share_id", String(40), primary_key=True),
    Column("document_title", String(80), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
_desktop_engine: Engine | None = None
_desktop_table_ready = False
_desktop_db_lock = threading.Lock()


class DesktopSessionIn(BaseModel):
    share_id: str = Field(..., min_length=2, max_length=40)


class DesktopPreferenceIn(BaseModel):
    document_title: str = Field(..., min_length=1, max_length=80)


def _normalize_share_id(value: str) -> str:
    share_id = str(value or "").strip()
    if not WATCHLIST_ID_RE.fullmatch(share_id):
        raise HTTPException(
            status_code=422,
            detail="아이디는 2~40자의 한글, 영문, 숫자, _, -, .만 사용할 수 있습니다.",
        )
    return share_id


def _sqlalchemy_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def _preferences_engine() -> Engine:
    global _desktop_engine, _desktop_table_ready
    if _desktop_engine is not None and _desktop_table_ready:
        return _desktop_engine
    with _desktop_db_lock:
        if _desktop_engine is None:
            if DESKTOP_DATABASE_URL.startswith("sqlite"):
                DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
            _desktop_engine = create_engine(
                _sqlalchemy_database_url(DESKTOP_DATABASE_URL),
                pool_pre_ping=True,
                connect_args={"check_same_thread": False} if DESKTOP_DATABASE_URL.startswith("sqlite") else {},
            )
        if not _desktop_table_ready:
            desktop_metadata.create_all(_desktop_engine)
            _desktop_table_ready = True
    return _desktop_engine


def _read_document_preference(share_id: str) -> dict[str, Any]:
    with _preferences_engine().connect() as connection:
        row = connection.execute(
            select(desktop_preferences.c.document_title, desktop_preferences.c.updated_at).where(
                desktop_preferences.c.share_id == share_id
            )
        ).mappings().one_or_none()
    if row is None:
        return {"document_title": DEFAULT_DOCUMENT_TITLE, "updated_at": None}
    updated_at = row["updated_at"]
    return {
        "document_title": row["document_title"],
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _save_document_preference(share_id: str, document_title: str) -> dict[str, Any]:
    engine = _preferences_engine()
    updated_at = datetime.now(timezone.utc)
    with engine.begin() as connection:
        result = connection.execute(
            update(desktop_preferences)
            .where(desktop_preferences.c.share_id == share_id)
            .values(document_title=document_title, updated_at=updated_at)
        )
    if result.rowcount == 0:
        try:
            with engine.begin() as connection:
                connection.execute(
                    insert(desktop_preferences).values(
                        share_id=share_id,
                        document_title=document_title,
                        updated_at=updated_at,
                    )
                )
        except IntegrityError:
            with engine.begin() as connection:
                connection.execute(
                    update(desktop_preferences)
                    .where(desktop_preferences.c.share_id == share_id)
                    .values(document_title=document_title, updated_at=updated_at)
                )
    return {"document_title": document_title, "updated_at": updated_at.isoformat()}


def _session_value(share_id: str, issued_at: int | None = None) -> str:
    encoded_id = base64.urlsafe_b64encode(share_id.encode("utf-8")).decode("ascii").rstrip("=")
    payload = f"{encoded_id}.{issued_at or int(time.time())}"
    signature = hmac.new(DESKTOP_SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _share_id_from_session(value: str | None) -> str:
    try:
        encoded_id, timestamp, signature = str(value or "").split(".", 2)
        payload = f"{encoded_id}.{timestamp}"
        expected = hmac.new(
            DESKTOP_SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        issued_at = int(timestamp)
        age = int(time.time()) - issued_at
        if age < -300 or age > DESKTOP_SESSION_TTL_SECONDS:
            raise ValueError("expired session")
        padding = "=" * (-len(encoded_id) % 4)
        return _normalize_share_id(base64.urlsafe_b64decode(encoded_id + padding).decode("utf-8"))
    except (ValueError, UnicodeError, TypeError):
        raise HTTPException(status_code=401, detail="PC 세션이 만료되었습니다.") from None


def _request_is_secure(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    return forwarded == "https" or request.url.scheme == "https"


def _upstream_websocket_url(path: str) -> str:
    parsed = urlsplit(UPSTREAM_BASE)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    base_path = parsed.path.rstrip("/")
    return urlunsplit((scheme, parsed.netloc, f"{base_path}/{path.lstrip('/')}", "", ""))


async def _authorize_upstream_session(share_id: str, request: Request) -> None:
    headers = {
        "content-type": "application/json",
        "x-forwarded-host": request.headers.get("host", ""),
        "x-forwarded-proto": request.headers.get("x-forwarded-proto", request.url.scheme),
    }
    if request.headers.get("cookie"):
        headers["cookie"] = request.headers["cookie"]
    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT, follow_redirects=False) as client:
            upstream = await client.post(
                f"{UPSTREAM_BASE}/session/dashboard-access",
                headers=headers,
                json={"share_id": share_id},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="사용자 권한을 확인하지 못했습니다.") from exc
    if upstream.status_code >= 400:
        try:
            detail = upstream.json().get("detail", "사용자 권한을 확인하지 못했습니다.")
        except ValueError:
            detail = "사용자 권한을 확인하지 못했습니다."
        raise HTTPException(status_code=upstream.status_code, detail=detail)

app = FastAPI(title="Secret Note Desktop", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/assets/desktop", StaticFiles(directory=STATIC_DIR / "desktop"), name="desktop-assets")


@app.get("/")
def root():
    return RedirectResponse(url="/desktop", status_code=307)


@app.get("/desktop")
def desktop_shell():
    if not DESKTOP_INDEX.exists():
        raise HTTPException(status_code=404, detail="Desktop UI not found")
    return HTMLResponse(
        DESKTOP_INDEX.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/desktop-sw.js")
def desktop_service_worker():
    if not DESKTOP_SERVICE_WORKER.exists():
        raise HTTPException(status_code=404, detail="Desktop service worker not found")
    return Response(
        DESKTOP_SERVICE_WORKER.read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Service-Worker-Allowed": "/desktop",
        },
    )


@app.get("/healthz")
@app.get("/readyz")
def health():
    return {"status": "ok", "service": "secret-note-desktop"}


@app.websocket("/ws/stocks/{code}/quote")
async def proxy_stock_quote_stream(websocket: WebSocket, code: str):
    normalized = str(code or "").strip()
    if not STOCK_CODE_RE.fullmatch(normalized):
        await websocket.close(code=1008, reason="Invalid stock code")
        return
    await websocket.accept()
    target = _upstream_websocket_url(f"ws/stocks/{quote(normalized, safe='')}/quote")
    try:
        async with websockets.connect(target, open_timeout=15, close_timeout=5, ping_interval=20) as upstream:
            async for message in upstream:
                if isinstance(message, bytes):
                    await websocket.send_bytes(message)
                else:
                    await websocket.send_text(message)
    except WebSocketDisconnect:
        return
    except websockets.exceptions.ConnectionClosed:
        return
    except Exception:
        try:
            await websocket.send_json(
                {"type": "status", "code": normalized, "status": "fallback", "message": "실시간 연결을 다시 시도합니다."}
            )
        except (WebSocketDisconnect, RuntimeError):
            return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass


@app.post("/desktop/session")
async def create_desktop_session(
    payload: DesktopSessionIn,
    request: Request,
    response: FastAPIResponse,
):
    share_id = _normalize_share_id(payload.share_id)
    await _authorize_upstream_session(share_id, request)
    response.set_cookie(
        DESKTOP_SESSION_COOKIE,
        _session_value(share_id),
        max_age=DESKTOP_SESSION_TTL_SECONDS,
        httponly=True,
        secure=_request_is_secure(request),
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return {"authorized": True, "share_id": share_id, "expires_in_seconds": DESKTOP_SESSION_TTL_SECONDS}


@app.get("/desktop/preferences")
def get_desktop_preferences(
    response: FastAPIResponse,
    desktop_session: str | None = Cookie(default=None, alias=DESKTOP_SESSION_COOKIE),
):
    share_id = _share_id_from_session(desktop_session)
    try:
        preference = _read_document_preference(share_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="PC 설정 저장소에 연결하지 못했습니다.") from exc
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return {"share_id": share_id, **preference}


@app.put("/desktop/preferences")
def update_desktop_preferences(
    payload: DesktopPreferenceIn,
    response: FastAPIResponse,
    desktop_session: str | None = Cookie(default=None, alias=DESKTOP_SESSION_COOKIE),
):
    share_id = _share_id_from_session(desktop_session)
    document_title = payload.document_title.strip()
    if not document_title:
        raise HTTPException(status_code=422, detail="문서 제목을 입력해주세요.")
    try:
        preference = _save_document_preference(share_id, document_title)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="PC 설정을 저장하지 못했습니다.") from exc
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return {"share_id": share_id, **preference}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_backend(path: str, request: Request):
    if path.startswith("assets/desktop") or path == "desktop":
        raise HTTPException(status_code=404, detail="Not found")

    target = f"{UPSTREAM_BASE}/{path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "host"
    }
    headers["x-forwarded-host"] = request.headers.get("host", "")
    headers["x-forwarded-proto"] = request.url.scheme

    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target,
                headers=headers,
                content=await request.body(),
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Backend connection failed") from exc

    response_headers = {
        key: value
        for key, value in upstream.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "set-cookie"
    }
    response = Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)
    for cookie in upstream.headers.get_list("set-cookie"):
        response.headers.append("set-cookie", cookie)
    return response
