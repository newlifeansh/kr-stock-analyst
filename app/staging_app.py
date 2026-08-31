"""Staging-only ASGI entry point for the TDS video-fidelity review.

The production application is imported without modification.  This wrapper only
adds the staging presentation assets to HTML responses when Railway starts
``app.staging_app:app``.  Running ``app.main:app`` therefore keeps the existing
mobile service byte-for-byte unchanged.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
import html as html_lib
import json
import os
import re
from time import monotonic
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

import httpx

from app.db import SessionLocal
from app.main import MANUAL_STOCK_LOGO_DIR, app as production_app
from app.models import NewsItem
from app.schemas import MorningMoneyBriefingOut
from app.services.morning_money_briefing import (
    KST,
    build_morning_money_briefing_history,
)
from app.services.dashboard_market_data import (
    DashboardMarketDataError,
    build_korea_market_calendar,
    fetch_stock_week_chart,
)
from app.services.chart_patterns import CHART_PATTERN_SCHEMA_VERSION, detect_chart_patterns
from app.services.quant_signals import STRATEGY_VERSION


Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

THEME_VERSION = "20260828-tds-adaptive-v77-shortcuts"
STAGING_IA_VERSION = "20260831-header-action-icons-signal-copy-v61"
STAGING_STYLE_VERSION = (
    f"{THEME_VERSION}-contextual-safe-area-v128-stock-search-v129-ai-response-v130-home-signal-action-v131-notification-sheet-v132-ai-signal-spacing-v133-chart-pattern-integrity-v134-ai-stock-response-v135-morning-preliminary-v136-multi-signal-response-v137-discovery-search-contrast-v138-ai-signal-basis-stack-v140-ai-response-beginner-v141-semantic-focus-v142-header-action-icons-v143"
)
STAGING_ENVIRONMENT_META = '<meta name="secret-note-environment" content="staging" />'
SERVICE_UPDATE_META = (
    '<meta name="secret-note-service-update" content="20260829-chart-analysis-v1" />'
)
THEME_HEAD = (
    '<meta name="color-scheme" content="light dark" />'
    f'{STAGING_ENVIRONMENT_META}'
    f'{SERVICE_UPDATE_META}'
    '<meta id="staging-theme-color" name="theme-color" content="#17161b" />'
    f'<script src="/assets/staging/adaptive-theme.js?v={THEME_VERSION}" '
    'data-staging-theme-bootstrap></script>'
    f'<link rel="stylesheet" href="/assets/staging/dark-theme.css?v={STAGING_STYLE_VERSION}" '
    'media="(prefers-color-scheme: dark)" data-staging-dark-fallback />'
    f'<link rel="stylesheet" href="/assets/staging/toss-fidelity.css?v={STAGING_STYLE_VERSION}" />'
    f'<script src="/assets/staging/ai-stock-response-logic.js?v={STAGING_IA_VERSION}" defer></script>'
    f'<script src="/assets/staging/stock-change-copy-logic.js?v={STAGING_IA_VERSION}" defer></script>'
    f'<script src="/assets/staging/toss-ia.js?v={STAGING_IA_VERSION}" defer></script>'
)

# The staging service intentionally has no production database credentials or
# market-data secrets.  When explicitly configured, it may read the public GET
# APIs from the canonical service instead.  Mutating, session, push, and
# internal endpoints always stay on the isolated staging app.
STAGING_DATA_UPSTREAM = os.getenv("STAGING_DATA_UPSTREAM", "").strip().rstrip("/")
STAGING_DATA_TIMEOUT_SECONDS = 25.0
STAGING_WEEK_CHART_PATTERN = re.compile(
    r"^/staging-data/stocks/(?P<code>[0-9]{6})/week-chart$"
)
STAGING_LOCAL_STOCK_NEWS_PATTERN = re.compile(
    r"^/stocks/[0-9]{6}/news-items$"
)
STAGING_STOCK_READ_PATTERN = re.compile(
    r"^/stocks/(?P<code>[0-9]{6})/(?P<resource>quote|dashboard|ai-analysis|quant-signals)$"
)
STAGING_KOREA_CALENDAR_PATH = "/staging-data/korea-calendar"
STAGING_MORNING_MONEY_HISTORY_PATH = "/briefings/morning-money/history"
STAGING_MORNING_MONEY_HISTORY_TTL_SECONDS = 120.0
_staging_morning_money_history_cache: dict[int, tuple[float, bytes]] = {}
STAGING_READ_EXACT_PATHS = frozenset(
    {
        "/stocks",
        "/macro",
        "/research-reports",
        "/disclosures",
        "/news-items",
        "/insight/feed",
        "/company-briefs",
        "/realtime/status",
    }
)
STAGING_READ_PATH_PREFIXES = (
    "/stocks/",
    "/stock-logos/",
    "/market/",
    "/us/",
    "/briefings/",
    "/meta/",
)

_UPSTREAM_RESPONSE_HEADERS = frozenset(
    {
        b"content-type",
        b"content-disposition",
        b"last-modified",
    }
)


def _header_value(headers: list[tuple[bytes, bytes]], name: bytes) -> str:
    target = name.lower()
    for key, value in headers:
        if key.lower() == target:
            return value.decode("latin-1")
    return ""


def _is_staging_read_proxy_request(scope: dict[str, Any]) -> bool:
    if not STAGING_DATA_UPSTREAM or scope.get("method") != "GET":
        return False
    path = str(scope.get("path") or "")
    if path == "/market/calendar" or re.fullmatch(
        r"/stocks/[0-9]{6}/week-chart", path
    ):
        return False
    if STAGING_LOCAL_STOCK_NEWS_PATTERN.fullmatch(path):
        return False
    if path.startswith("/stock-logos/"):
        logo_name = path.removeprefix("/stock-logos/")
        if re.fullmatch(r"[0-9A-Z]{6}\.png", logo_name) and (MANUAL_STOCK_LOGO_DIR / logo_name).is_file():
            return False
    return path in STAGING_READ_EXACT_PATHS or path.startswith(
        STAGING_READ_PATH_PREFIXES
    )


def _scope_header(scope: dict[str, Any], name: bytes) -> str:
    return _header_value(list(scope.get("headers", [])), name)


def _rewrite_staging_quality_contract(path: str, body: bytes) -> bytes:
    if path != "/meta/signal-data-quality":
        return body
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return body
    if not isinstance(payload, dict):
        return body
    payload["strategy_version"] = STRATEGY_VERSION
    return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")


async def _read_staging_upstream(
    scope: dict[str, Any],
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    path = str(scope.get("path") or "/")
    query = bytes(scope.get("query_string") or b"").decode("latin-1")
    url = f"{STAGING_DATA_UPSTREAM}{path}{f'?{query}' if query else ''}"
    accept = _scope_header(scope, b"accept") or "*/*"
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=STAGING_DATA_TIMEOUT_SECONDS,
    ) as client:
        response = await client.get(
            url,
            headers={
                "Accept": accept,
                "User-Agent": "SecretNote-TDS-Video-Staging-ReadProxy/1.0",
            },
        )
        body = response.content
        if response.status_code == 200 and "application/json" in response.headers.get("content-type", ""):
            body = await _sanitize_staging_stock_payload(client, path, body)
            body = _rewrite_staging_quality_contract(path, body)
    headers = [
        (key.lower(), value)
        for key, value in response.headers.raw
        if key.lower() in _UPSTREAM_RESPONSE_HEADERS
    ]
    headers.extend(
        [
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store, no-cache, must-revalidate"),
            (b"x-robots-tag", b"noindex, nofollow, noarchive"),
            (b"x-staging-theme", THEME_VERSION.encode("ascii")),
            (b"x-staging-data-source", b"secretnote.cloud-read-only"),
        ]
    )
    return response.status_code, headers, body


def _as_date(value: Any) -> date | None:
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


def _completed_quote_from_prices(
    prices: list[dict[str, Any]],
    *,
    session_quote: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    rows = sorted(
        (row for row in prices if _as_date(row.get("trade_date")) is not None),
        key=lambda row: _as_date(row.get("trade_date")) or date.min,
        reverse=True,
    )
    if not rows or not rows[0].get("close"):
        return None
    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else None
    close = int(latest["close"])
    previous_close = int(previous["close"]) if previous and previous.get("close") else None
    change_value = close - previous_close if previous_close else None
    change_rate = round(change_value * 100 / previous_close, 2) if previous_close else None
    session = session_quote or {}
    return {
        "trade_date": latest.get("trade_date"),
        "price": close,
        "change_value": change_value,
        "change_rate": change_rate,
        "volume": latest.get("volume"),
        "trading_value": latest.get("trading_value"),
        "market_cap": latest.get("market_cap"),
        "open": latest.get("open"),
        "high": latest.get("high"),
        "low": latest.get("low"),
        "trade_date_verified": True,
        "quote_source": "stored_daily_price",
        "market_session": session.get("market_session") or "closed",
        "market_session_label": session.get("market_session_label") or "장 마감",
        "market_venue": session.get("market_venue") or "KRX",
        "market_division": session.get("market_division") or "J",
        "is_live": False,
    }


def _staging_quote_needs_completed_fallback(
    quote: dict[str, Any] | None,
    completed_quote: dict[str, Any] | None,
    *,
    now: datetime,
) -> bool:
    if not isinstance(quote, dict) or not isinstance(completed_quote, dict):
        return False
    if quote.get("is_live") is True:
        return False
    quote_date = _as_date(quote.get("trade_date"))
    completed_date = _as_date(completed_quote.get("trade_date"))
    if quote_date and completed_date and quote_date > completed_date:
        return True
    current = now if now.tzinfo else now.replace(tzinfo=KST)
    current = current.astimezone(KST)
    market_closed = current.weekday() >= 5 or not (time(8, 0) <= current.time() < time(20, 0))
    return bool(
        market_closed
        and quote.get("price") not in (None, completed_quote.get("price"))
    )


async def _sanitize_staging_stock_payload(
    client: httpx.AsyncClient,
    path: str,
    body: bytes,
) -> bytes:
    match = STAGING_STOCK_READ_PATTERN.fullmatch(path)
    if match is None:
        return body
    try:
        payload = json.loads(body)
    except (TypeError, ValueError, json.JSONDecodeError):
        return body
    if not isinstance(payload, dict):
        return body

    code = match.group("code")
    resource = match.group("resource")
    payload_changed = False
    if resource == "quant-signals":
        try:
            feed_response = await client.get(
                f"{STAGING_DATA_UPSTREAM}/market/quant-signals",
                params={"universe_limit": 100, "limit": 0, "recent_days": 30},
                headers={"Accept": "application/json"},
            )
            feed_response.raise_for_status()
            feed = feed_response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            return body
        current_item = next(
            (
                item
                for item in feed.get("items", [])
                if isinstance(item, dict)
                and item.get("code") == code
                and isinstance(item.get("current"), dict)
            ),
            None,
        )
        if current_item is None:
            return body
        payload["current"] = current_item["current"]
        payload["as_of"] = feed.get("as_of") or payload.get("as_of")
        for key in (
            "display_return_rate",
            "display_return_kind",
            "display_return_event_date",
            "display_return_event_side",
        ):
            if key in current_item:
                payload[key] = current_item[key]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    try:
        prices_response = await client.get(
            f"{STAGING_DATA_UPSTREAM}/stocks/{code}/prices",
            params={"limit": 250 if resource == "dashboard" else 2},
            headers={"Accept": "application/json"},
        )
        prices_response.raise_for_status()
        prices = prices_response.json()
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        return body
    if not isinstance(prices, list):
        return body

    if resource == "dashboard":
        analysis = payload.get("chart_analysis")
        try:
            pattern_schema_version = int(
                analysis.get("pattern_schema_version") or 0
            ) if isinstance(analysis, dict) else 0
        except (TypeError, ValueError):
            pattern_schema_version = 0
        if isinstance(analysis, dict) and pattern_schema_version < CHART_PATTERN_SCHEMA_VERSION:
            ordered_prices = sorted(
                (
                    item for item in prices
                    if isinstance(item, dict) and _as_date(item.get("trade_date")) is not None
                ),
                key=lambda item: _as_date(item.get("trade_date")) or date.min,
            )
            analysis["patterns"] = detect_chart_patterns(
                SimpleNamespace(**item) for item in ordered_prices
            )
            analysis["pattern_schema_version"] = CHART_PATTERN_SCHEMA_VERSION
            payload_changed = True

    quote = payload.get("quote") if resource != "quote" else payload.get("quote")
    completed_quote = _completed_quote_from_prices(prices, session_quote=quote)
    if not _staging_quote_needs_completed_fallback(
        quote,
        completed_quote,
        now=datetime.now(KST),
    ):
        return (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if payload_changed
            else body
        )
    payload["quote"] = completed_quote
    payload["source"] = "stored_daily_price"
    latest_date = _as_date(completed_quote.get("trade_date")) if completed_quote else None
    if latest_date:
        payload["as_of"] = datetime.combine(latest_date, time(15, 30), tzinfo=KST).isoformat()
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


async def _read_staging_week_chart(
    scope: dict[str, Any],
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    path = str(scope.get("path") or "")
    match = STAGING_WEEK_CHART_PATTERN.fullmatch(path)
    if match is None:
        raise ValueError("invalid staging week chart path")
    payload = await fetch_stock_week_chart(match.group("code"))
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store, no-cache, must-revalidate"),
        (b"x-robots-tag", b"noindex, nofollow, noarchive"),
        (b"x-staging-theme", THEME_VERSION.encode("ascii")),
        (b"x-staging-data-source", b"naver-finance-public-week-chart"),
    ]
    return 200, headers, body


async def _read_staging_korea_calendar(
    scope: dict[str, Any],
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    query = parse_qs(bytes(scope.get("query_string") or b"").decode("latin-1"))
    try:
        future_days = max(1, min(int((query.get("days") or ["14"])[0]), 31))
    except (TypeError, ValueError):
        future_days = 14
    payload = await build_korea_market_calendar(days=future_days)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"public, max-age=300"),
        (b"x-robots-tag", b"noindex, nofollow, noarchive"),
        (b"x-staging-theme", THEME_VERSION.encode("ascii")),
        (b"x-staging-data-source", b"bank-of-korea-statistical-calendar"),
    ]
    return 200, headers, body


def _staging_news_item(payload: dict[str, Any]) -> NewsItem | None:
    published_raw = str(payload.get("published_at") or "").strip()
    try:
        published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return NewsItem(
        id=int(payload.get("id") or 0),
        source=str(payload.get("source") or "naver_finance"),
        source_category=str(payload.get("source_category") or "market"),
        external_id=str(payload.get("external_id") or payload.get("id") or ""),
        title=str(payload.get("title") or "").strip(),
        summary=str(payload.get("summary") or "").strip() or None,
        press_name=str(payload.get("press_name") or "").strip() or None,
        image_url=str(payload.get("image_url") or "").strip() or None,
        detail_url=str(payload.get("detail_url") or "").strip() or None,
        published_at=published_at,
        raw=None,
    )


async def _read_staging_morning_money_history(
    scope: dict[str, Any],
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    query = parse_qs(bytes(scope.get("query_string") or b"").decode("latin-1"))
    try:
        history_days = max(1, min(int((query.get("days") or ["7"])[0]), 7))
    except (TypeError, ValueError):
        history_days = 7
    cached = _staging_morning_money_history_cache.get(history_days)
    if cached is not None and cached[0] > monotonic():
        body = cached[1]
        return 200, [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", b"no-store, no-cache, must-revalidate"),
            (b"x-robots-tag", b"noindex, nofollow, noarchive"),
            (b"x-staging-theme", THEME_VERSION.encode("ascii")),
            (b"x-staging-data-source", b"secretnote.cloud-seven-day-editorial-history-cache"),
        ], body
    current = datetime.now(KST)
    # The oldest 06:00 edition starts at 16:00 on the previous calendar day.
    # Fetch one extra source date while still returning only the requested
    # seven publication dates, so that edition is not silently incomplete.
    publication_dates = [
        (current.date() - timedelta(days=offset)).isoformat()
        for offset in range(history_days + 1)
    ]
    # The canonical news endpoint caps one request at 500 rows.  Weekdays can
    # exceed that volume, which would otherwise trim the 09:00–12:00 edition
    # from a whole-day query.  A second request for the high-volume `breaking`
    # stream restores that publication window while the unfiltered request
    # retains the other finance-specific source categories.
    source_queries = [
        (publication_date, category)
        for publication_date in publication_dates
        for category in (None, "breaking")
    ]

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=STAGING_DATA_TIMEOUT_SECONDS,
    ) as client:
        responses = await asyncio.gather(
            *(
                client.get(
                    f"{STAGING_DATA_UPSTREAM}/news-items",
                    params={
                        "limit": 500,
                        "from_date": publication_date,
                        "to_date": publication_date,
                        **({"category": category} if category else {}),
                    },
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "SecretNote-TDS-Video-Staging-Briefing-History/1.0",
                    },
                )
                for publication_date, category in source_queries
            )
        )

    news_by_key: dict[tuple[str, str, str], NewsItem] = {}
    for response in responses:
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            news_item = _staging_news_item(item)
            if news_item is None or not news_item.title:
                continue
            key = (
                str(news_item.source),
                str(news_item.source_category),
                str(news_item.external_id),
            )
            news_by_key.setdefault(key, news_item)

    db = SessionLocal()
    try:
        history = build_morning_money_briefing_history(
            db,
            now=current,
            days=history_days,
            news_rows=news_by_key.values(),
        )
    finally:
        db.close()
    serialized = [
        MorningMoneyBriefingOut.model_validate(item).model_dump(mode="json")
        for item in history
    ]
    body = json.dumps(serialized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _staging_morning_money_history_cache[history_days] = (
        monotonic() + STAGING_MORNING_MONEY_HISTORY_TTL_SECONDS,
        body,
    )
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store, no-cache, must-revalidate"),
        (b"x-robots-tag", b"noindex, nofollow, noarchive"),
        (b"x-staging-theme", THEME_VERSION.encode("ascii")),
        (b"x-staging-data-source", b"secretnote.cloud-seven-day-editorial-history"),
    ]
    return 200, headers, body


def _staging_headers(
    headers: list[tuple[bytes, bytes]], *, html_response: bool
) -> list[tuple[bytes, bytes]]:
    omitted = {b"content-length", b"etag"} if html_response else set()
    result = [(key, value) for key, value in headers if key.lower() not in omitted]
    result = [
        (key, value)
        for key, value in result
        if key.lower() not in {b"x-robots-tag", b"x-staging-theme"}
    ]
    result.extend(
        [
            (b"x-robots-tag", b"noindex, nofollow, noarchive"),
            (b"x-staging-theme", THEME_VERSION.encode("ascii")),
        ]
    )
    return result


def _staging_quote_stream_meta() -> str:
    """Route staging browsers to the canonical public quote WebSocket."""
    if not STAGING_DATA_UPSTREAM:
        return ""
    parsed = urlparse(STAGING_DATA_UPSTREAM)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    base_path = parsed.path.rstrip("/")
    stream_url = urlunparse(
        (
            "wss" if parsed.scheme == "https" else "ws",
            parsed.netloc,
            f"{base_path}/ws/quotes",
            "",
            "",
            "",
        )
    )
    escaped_url = html_lib.escape(stream_url, quote=True)
    return (
        '<meta name="secret-note-quote-stream-url" '
        f'content="{escaped_url}" />'
    )


def _inject_theme(document: bytes) -> bytes:
    try:
        html = document.decode("utf-8")
    except UnicodeDecodeError:
        return document

    quote_stream_meta = _staging_quote_stream_meta()
    quote_stream_meta_pattern = (
        r'<meta\s+name="secret-note-quote-stream-url"\s+content="[^"]*"\s*/?>'
    )
    html = re.sub(quote_stream_meta_pattern, "", html)

    if "/assets/staging/toss-fidelity.css" in html:
        html = re.sub(
            r'(/assets/staging/adaptive-theme\.js\?v=)[^"&]+',
            rf'\g<1>{THEME_VERSION}',
            html,
            count=1,
        )
        html = re.sub(
            r'(/assets/staging/(?:dark-theme|toss-fidelity)\.css\?v=)[^"&]+',
            lambda match: f"{match.group(1)}{STAGING_STYLE_VERSION}",
            html,
        )
        html = re.sub(
            r'(/assets/staging/(?:ai-stock-response-logic|stock-change-copy-logic|toss-ia)\.js\?v=)[^"&]+',
            rf'\g<1>{STAGING_IA_VERSION}',
            html,
        )
        if STAGING_ENVIRONMENT_META not in html:
            html = html.replace("</head>", f"  {STAGING_ENVIRONMENT_META}\n</head>", 1)
        if quote_stream_meta:
            html = html.replace("</head>", f"  {quote_stream_meta}\n</head>", 1)
        return html.encode("utf-8")
    if "</head>" in html:
        dynamic_head = f"{THEME_HEAD}{quote_stream_meta}"
        html = html.replace("</head>", f"  {dynamic_head}\n</head>", 1)
    else:
        html = f"{THEME_HEAD}{quote_stream_meta}{html}"
    return html.encode("utf-8")


class StagingTDSVideoApp:
    """Inject the TDS video review layer while preserving production."""

    def __init__(self, inner_app: Callable[..., Awaitable[None]]) -> None:
        self.inner_app = inner_app

    async def __call__(self, scope: dict[str, Any], receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.inner_app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if scope.get("method") == "GET" and path == STAGING_KOREA_CALENDAR_PATH:
            try:
                status, headers, body = await _read_staging_korea_calendar(scope)
            except (DashboardMarketDataError, ValueError, TypeError):
                body = json.dumps(
                    {"message": "한국 주요 일정을 불러오지 못했습니다."},
                    ensure_ascii=False,
                ).encode("utf-8")
                status = 502
                headers = [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    (b"x-robots-tag", b"noindex, nofollow, noarchive"),
                    (b"x-staging-theme", THEME_VERSION.encode("ascii")),
                ]
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": headers,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                    "more_body": False,
                }
            )
            return

        if (
            scope.get("method") == "GET"
            and path == STAGING_MORNING_MONEY_HISTORY_PATH
            and STAGING_DATA_UPSTREAM
        ):
            try:
                status, headers, body = await _read_staging_morning_money_history(scope)
            except (httpx.HTTPError, ValueError, json.JSONDecodeError):
                body = json.dumps(
                    {"message": "최근 7일 돈이 되는 소식을 불러오지 못했습니다."},
                    ensure_ascii=False,
                ).encode("utf-8")
                status = 502
                headers = [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    (b"x-robots-tag", b"noindex, nofollow, noarchive"),
                    (b"x-staging-theme", THEME_VERSION.encode("ascii")),
                ]
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": headers,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                    "more_body": False,
                }
            )
            return

        if scope.get("method") == "GET" and STAGING_WEEK_CHART_PATTERN.fullmatch(path):
            try:
                status, headers, body = await _read_staging_week_chart(scope)
            except (
                DashboardMarketDataError,
                httpx.HTTPError,
                ValueError,
                json.JSONDecodeError,
            ):
                body = json.dumps(
                    {"message": "일주일 실시간 차트를 불러오지 못했습니다."},
                    ensure_ascii=False,
                ).encode("utf-8")
                status = 502
                headers = [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    (b"x-robots-tag", b"noindex, nofollow, noarchive"),
                    (b"x-staging-theme", THEME_VERSION.encode("ascii")),
                ]
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": headers,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                    "more_body": False,
                }
            )
            return

        if _is_staging_read_proxy_request(scope):
            try:
                status, headers, body = await _read_staging_upstream(scope)
            except httpx.HTTPError:
                # Preserve the isolated staging response if the canonical
                # service is briefly unreachable.
                pass
            else:
                await send(
                    {
                        "type": "http.response.start",
                        "status": status,
                        "headers": headers,
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": body,
                        "more_body": False,
                    }
                )
                return

        response_start: Message | None = None
        html_response = False
        body_chunks: list[bytes] = []

        async def staging_send(message: Message) -> None:
            nonlocal response_start, html_response

            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                content_type = _header_value(raw_headers, b"content-type").lower()
                content_encoding = _header_value(raw_headers, b"content-encoding").lower()
                html_response = (
                    scope.get("method") != "HEAD"
                    and "text/html" in content_type
                    and not content_encoding
                )
                updated = dict(message)
                updated["headers"] = _staging_headers(
                    raw_headers, html_response=html_response
                )
                if html_response:
                    response_start = updated
                else:
                    await send(updated)
                return

            if message["type"] != "http.response.body" or not html_response:
                await send(message)
                return

            body_chunks.append(message.get("body", b""))
            if message.get("more_body", False):
                return

            if response_start is None:
                raise RuntimeError("HTML response body arrived before response headers")
            themed_body = _inject_theme(b"".join(body_chunks))
            response_start["headers"].append(
                (b"content-length", str(len(themed_body)).encode("ascii"))
            )
            await send(response_start)
            await send(
                {
                    "type": "http.response.body",
                    "body": themed_body,
                    "more_body": False,
                }
            )

        await self.inner_app(scope, receive, staging_send)


app = StagingTDSVideoApp(production_app)
