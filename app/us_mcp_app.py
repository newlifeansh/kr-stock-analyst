from __future__ import annotations

import secrets
from collections import defaultdict, deque
from contextlib import AsyncExitStack, asynccontextmanager
from time import monotonic
from typing import Deque

from sqlalchemy import text
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.config import Settings, get_settings
from app.db import SessionLocal, init_db
from app.mcp_server import mcp_sdk_available
from app.us_mcp_server import build_us_mcp_server


class PersonalMCPAccessMiddleware(BaseHTTPMiddleware):
    """Protect the personal MCP endpoint and cap accidental request bursts."""

    def __init__(
        self,
        app,
        *,
        bearer_token: str | None,
        rate_limit_per_minute: int,
        require_configured_token: bool,
    ) -> None:
        super().__init__(app)
        self.bearer_token = str(bearer_token or "").strip()
        self.rate_limit_per_minute = max(1, int(rate_limit_per_minute))
        self.require_configured_token = bool(require_configured_token)
        self._request_windows: dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request, call_next):
        if request.url.path in {"/health", "/healthz", "/readyz"}:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        if self.require_configured_token and not self.bearer_token:
            return JSONResponse(
                {"error": "us_mcp_auth_not_configured"},
                status_code=503,
            )
        if self.bearer_token:
            authorization = str(request.headers.get("authorization") or "")
            scheme, _, submitted = authorization.partition(" ")
            if (
                scheme.lower() != "bearer"
                or not submitted
                or not secrets.compare_digest(submitted.strip(), self.bearer_token)
            ):
                return JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )

        client_host = request.client.host if request.client else "unknown"
        key = f"{client_host}:{self.bearer_token[:8]}"
        now = monotonic()
        window = self._request_windows[key]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= self.rate_limit_per_minute:
            retry_after = max(1, int(60 - (now - window[0])))
            return JSONResponse(
                {"error": "rate_limit_exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)
        return await call_next(request)


def us_mcp_health_payload(settings: Settings, server_available: bool) -> dict[str, object]:
    public_endpoint_configured = bool(str(settings.mcp_public_base_url or "").strip())
    auth_configured = bool(str(settings.us_mcp_bearer_token or "").strip())
    return {
        "status": "ok",
        "app": settings.app_name,
        "market": "us",
        "mcp_server_name": settings.us_mcp_server_name,
        "tools": ["list_us_stock_signals", "get_us_stock_analysis"],
        "read_only": True,
        "upstream_refresh_allowed": False,
        "auth_configured": auth_configured,
        "remote_access_ready": bool(
            server_available and (not public_endpoint_configured or auth_configured)
        ),
        "rate_limit_per_minute": max(1, settings.us_mcp_rate_limit_per_minute),
    }


def build_us_mcp_app(settings: Settings | None = None) -> Starlette:
    active_settings = settings or get_settings()
    mcp_server = build_us_mcp_server(active_settings)
    if mcp_server is None:  # pragma: no cover - depends on runtime
        raise RuntimeError(
            "US MCP server is unavailable. Use Python 3.10+ and install the mcp package."
        )

    async def health(_: object) -> JSONResponse:
        return JSONResponse(us_mcp_health_payload(active_settings, True))

    async def ready(_: object) -> JSONResponse:
        database_ok = False
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
                database_ok = True
        except Exception:
            database_ok = False
        payload = {
            **us_mcp_health_payload(active_settings, True),
            "database_ok": database_ok,
            "mcp_sdk_available": mcp_sdk_available(),
            "mcp_server_available": True,
        }
        ready_ok = bool(
            database_ok
            and payload["mcp_sdk_available"]
            and payload["remote_access_ready"]
        )
        return JSONResponse(payload, status_code=200 if ready_ok else 503)

    class HealthcheckMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path in {"/health", "/healthz"}:
                return await health(request)
            if request.url.path == "/readyz":
                return await ready(request)
            return await call_next(request)

    @asynccontextmanager
    async def lifespan(_: Starlette):
        init_db()
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(mcp_server.session_manager.run())
            yield

    app = Starlette(routes=[], lifespan=lifespan)
    app.add_middleware(HealthcheckMiddleware)
    app.add_middleware(
        PersonalMCPAccessMiddleware,
        bearer_token=active_settings.us_mcp_bearer_token,
        rate_limit_per_minute=active_settings.us_mcp_rate_limit_per_minute,
        require_configured_token=bool(active_settings.mcp_public_base_url),
    )
    app.mount("/", mcp_server.streamable_http_app())
    return CORSMiddleware(
        app,
        allow_origins=[
            item
            for item in active_settings.mcp_allowed_origins.split(",")
            if item.strip()
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id", "mcp-session-id", "MCP-Protocol-Version"],
    )


settings = get_settings()
app = build_us_mcp_app(settings)
