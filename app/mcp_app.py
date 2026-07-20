from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager, suppress

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import text

from app.bootstrap import bootstrap_runtime_data
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.mcp_server import build_insight_mcp_server, mcp_sdk_available
from app.services.briefing import briefing_runtime

settings = get_settings()
mcp_server = build_insight_mcp_server(settings)
if mcp_server is None:  # pragma: no cover - depends on runtime
    raise RuntimeError("MCP server is unavailable. Use Python 3.10+ and install the mcp package.")
logger = logging.getLogger(__name__)


def mcp_health_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "mcp_server_name": settings.mcp_server_name,
        "bootstrap_on_start": settings.bootstrap_on_start,
    }


async def mcp_health(_: object) -> JSONResponse:
    return JSONResponse(mcp_health_payload())


def mcp_ready_payload() -> dict[str, object]:
    database_ok = False
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        database_ok = True
    return {
        **mcp_health_payload(),
        "database_ok": database_ok,
        "mcp_sdk_available": mcp_sdk_available(),
        "mcp_server_available": mcp_server is not None,
        "briefing_runtime_running": briefing_runtime.status().get("running", False),
    }


async def mcp_ready(_: object) -> JSONResponse:
    payload = mcp_ready_payload()
    status_code = 200 if payload["database_ok"] and payload["mcp_server_available"] else 503
    return JSONResponse(payload, status_code=status_code)


async def _run_bootstrap_task() -> None:
    try:
        await asyncio.to_thread(
            bootstrap_runtime_data,
            settings,
            force_refresh=settings.bootstrap_force_refresh,
        )
    except Exception:  # pragma: no cover - operational safeguard
        logger.exception("Background bootstrap failed")


class HealthcheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in {"/health", "/healthz"}:
            return await mcp_health(request)
        if request.url.path == "/readyz":
            return await mcp_ready(request)
        return await call_next(request)


@asynccontextmanager
async def lifespan(_: Starlette):
    init_db()
    bootstrap_task: asyncio.Task | None = None
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp_server.session_manager.run())
        await briefing_runtime.start()
        if settings.bootstrap_on_start:
            bootstrap_task = asyncio.create_task(_run_bootstrap_task())
        try:
            yield
        finally:
            if bootstrap_task is not None:
                bootstrap_task.cancel()
                with suppress(asyncio.CancelledError):
                    await bootstrap_task
            await briefing_runtime.stop()


app = Starlette(
    routes=[],
    lifespan=lifespan,
)
app.add_middleware(HealthcheckMiddleware)
app.mount("/", mcp_server.streamable_http_app())
app = CORSMiddleware(
    app,
    allow_origins=[item for item in settings.mcp_allowed_origins.split(",") if item.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id", "mcp-session-id", "MCP-Protocol-Version"],
)
