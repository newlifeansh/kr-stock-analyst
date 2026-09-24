"""Same-origin front door for the independently operated US product.

Only the canonical web service sets ``US_PUBLIC_BACKEND_URL``.  An unset or
unavailable backend never falls back to domestic data for a routed request.
"""

from __future__ import annotations

import asyncio
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

import httpx
import websockets
from fastapi import Request, WebSocket
from fastapi.responses import Response
from starlette.websockets import WebSocketDisconnect


GATEWAY_PREFIX = "/us-gateway"
COOKIE_PREFIX = "us_"
SESSION_COOKIE_NAMES = frozenset({"sn_invite_access", "sn_write_session", "sn_desktop_session"})
US_DIRECT_PATHS = frozenset({"/us", "/us-version", "/us-refresh", "/us.webmanifest", "/us-sw.js"})
GATEWAY_FORBIDDEN_PREFIXES = ("/internal", "/mcp", "/docs", "/openapi", "/debug")
HOP_HEADERS = frozenset({
    "connection", "content-length", "content-encoding", "host", "keep-alive",
    "proxy-authenticate", "proxy-authorization", "te", "trailer",
    "transfer-encoding", "upgrade", "set-cookie",
})


def gateway_target(path: str) -> str | None:
    if path.startswith(f"{GATEWAY_PREFIX}/"):
        target = path[len(GATEWAY_PREFIX):]
        if target.startswith(GATEWAY_FORBIDDEN_PREFIXES) or ".." in target.split("/"):
            return None
        return target
    if path in US_DIRECT_PATHS or path.startswith("/us/"):
        return path
    return None


def should_freeze_us_write(method: str, path: str, referer: str, host: str) -> bool:
    if method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    if path == "/us" or path.startswith(("/us/", "/us-gateway/", "/watchlists/us.")):
        return True
    parsed = urlsplit(referer)
    return bool(
        parsed.hostname
        and parsed.hostname.lower() == host.lower()
        and (parsed.path == "/us" or parsed.path.startswith("/us/"))
    )


def checked_backend_url(configured: str | None, public_host: str) -> str | None:
    if not configured:
        return None
    parsed = urlsplit(configured.strip())
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.hostname.lower() == public_host.lower()
    ):
        raise ValueError("US_PUBLIC_BACKEND_URL must be a distinct HTTPS origin")
    return f"https://{parsed.netloc.rstrip('/')}"


def _upstream_cookie_header(raw: str) -> str:
    parsed = SimpleCookie()
    try:
        parsed.load(raw)
    except Exception:
        return ""
    return "; ".join(
        f"{name[len(COOKIE_PREFIX):]}={morsel.value}"
        for name, morsel in parsed.items()
        if name.startswith(COOKIE_PREFIX) and name[len(COOKIE_PREFIX):] in SESSION_COOKIE_NAMES
    )


def _public_set_cookie(raw: str) -> str:
    parsed = SimpleCookie()
    try:
        parsed.load(raw)
    except Exception:
        return ""
    if len(parsed) != 1:
        return ""
    name, morsel = next(iter(parsed.items()))
    if name not in SESSION_COOKIE_NAMES:
        return ""
    # Browser data/auth requests are rewritten under this prefix. Scope US
    # cookies to it so the domestic dashboard never receives them.
    morsel["path"] = GATEWAY_PREFIX
    morsel["domain"] = ""
    return morsel.OutputString().replace(f"{name}=", f"{COOKIE_PREFIX}{name}=", 1)


def _upstream_headers(request: Request) -> dict[str, str]:
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in HOP_HEADERS
        and key.lower() not in {"cookie", "x-forwarded-host", "x-forwarded-proto", "accept-encoding"}
    }
    cookies = _upstream_cookie_header(request.headers.get("cookie", ""))
    if cookies:
        headers["cookie"] = cookies
    headers["x-forwarded-host"] = request.url.hostname or ""
    headers["x-forwarded-proto"] = "https"
    return headers


def _rewrite_us_document(body: bytes) -> bytes:
    document = body.decode("utf-8")
    if '<meta name="secret-note-market-universe" content="us"' not in document:
        raise ValueError("US backend returned a non-US shell")
    document = document.replace('="/assets/', '="/us-gateway/assets/')
    document = document.replace('="/dashboard-app-v170.js', '="/us-gateway/dashboard-app-v170.js')
    document = document.replace('="/us.webmanifest', '="/us-gateway/us.webmanifest')
    marker = '<meta name="secret-note-market-universe" content="us" />'
    if marker not in document:
        raise ValueError("US backend shell is missing its routing insertion point")
    document = document.replace(
        marker,
        marker + '\n    <script src="/us-gateway/assets/us-public-bridge.js"></script>',
        1,
    )
    return document.encode("utf-8")


def _rewrite_us_script(body: bytes) -> bytes:
    # The US worker's precache and dynamic SVG sprites must not fetch an older
    # domestic release's files while the two products promote independently.
    return body.replace(b'"/assets/', b'"/us-gateway/assets/').replace(
        b"'/assets/", b"'/us-gateway/assets/"
    ).replace(b'"/dashboard-app-v170.js', b'"/us-gateway/dashboard-app-v170.js')


async def forward_us_http(request: Request, backend_url: str, target_path: str) -> Response:
    query = request.url.query
    upstream_url = f"{backend_url}{target_path}{'?' + query if query else ''}"
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                upstream_url,
                headers=_upstream_headers(request),
                content=await request.body(),
            )
    except httpx.HTTPError:
        return Response(
            content=b'US market service unavailable',
            status_code=502,
            media_type="text/plain",
            headers={"Cache-Control": "no-store", "X-US-Market-Route": "upstream-unavailable"},
        )
    body = upstream.content
    content_type = upstream.headers.get("content-type", "")
    if upstream.is_success and (
        target_path in {"/us", "/us/"} or target_path.startswith("/us/stock/")
    ):
        try:
            body = _rewrite_us_document(body)
        except (UnicodeDecodeError, ValueError):
            return Response(
                content=b'US market shell contract unavailable',
                status_code=502,
                media_type="text/plain",
                headers={"Cache-Control": "no-store", "X-US-Market-Route": "invalid-upstream-shell"},
            )
    elif upstream.is_success and (
        target_path == "/us-sw.js"
        or target_path in {"/dashboard-app-v170.js", "/assets/staging/toss-ia.js"}
    ):
        body = _rewrite_us_script(body)
    headers = {
        key: value for key, value in upstream.headers.items()
        if key.lower() not in HOP_HEADERS and key.lower() != "location"
    }
    location = upstream.headers.get("location")
    if location:
        upstream_origin = backend_url.rstrip("/")
        headers["location"] = (
            location.replace(upstream_origin, str(request.base_url).rstrip("/"), 1)
            if location.startswith(upstream_origin)
            else location
        )
    headers["X-US-Market-Route"] = "dedicated-service"
    if "text/html" in content_type:
        headers["Cache-Control"] = "no-store"
    response = Response(content=body, status_code=upstream.status_code, headers=headers)
    for raw in upstream.headers.get_list("set-cookie"):
        rewritten = _public_set_cookie(raw)
        if rewritten:
            response.headers.append("set-cookie", rewritten)
    return response


async def forward_us_websocket(websocket: WebSocket, backend_url: str, path: str) -> None:
    if not path.startswith("ws/"):
        await websocket.close(code=1008)
        return
    target = path[3:]
    if target not in {"market/us-sector-moves"} and not target.startswith("us/stocks/"):
        await websocket.close(code=1008)
        return
    query = websocket.url.query
    url = f"wss://{urlsplit(backend_url).netloc}/ws/{target}{'?' + query if query else ''}"
    try:
        async with websockets.connect(url, open_timeout=10, close_timeout=2) as upstream:
            await websocket.accept(headers=[(b"x-us-market-route", b"dedicated-service")])

            async def client_to_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        break
                    if message.get("text") is not None:
                        await upstream.send(message["text"])
                    elif message.get("bytes") is not None:
                        await upstream.send(message["bytes"])

            async def upstream_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                try:
                    task.result()
                except (WebSocketDisconnect, websockets.ConnectionClosed):
                    pass
    except (OSError, TimeoutError, websockets.WebSocketException):
        if websocket.application_state.name == "CONNECTING":
            await websocket.close(code=1013)
