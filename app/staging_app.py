"""Staging-only ASGI entry point for the TDS video-fidelity review.

The production application is imported without modification.  This wrapper only
adds the staging presentation assets to HTML responses when Railway starts
``app.staging_app:app``.  Running ``app.main:app`` therefore keeps the existing
mobile service byte-for-byte unchanged.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import json
import os
import re
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, time, timedelta
from time import monotonic
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

import httpx

from app.db import SessionLocal
from app.main import MANUAL_STOCK_LOGO_DIR
from app.main import app as production_app
from app.models import NewsItem
from app.schemas import MorningMoneyBriefingOut
from app.services.chart_patterns import (
    CHART_PATTERN_SCHEMA_VERSION,
    detect_chart_patterns,
)
from app.services.dashboard_market_data import (
    DashboardMarketDataError,
    build_korea_market_calendar,
    fetch_stock_week_chart,
)
from app.services.morning_money_briefing import (
    KST,
    build_morning_money_briefing_history,
)
from app.services.quant_signals import STRATEGY_VERSION
from app.services.recommendations import _score_dashboard
from app.services.staging_page_summary import summarize_staging_page

Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

THEME_VERSION = "20260828-tds-adaptive-v77-shortcuts"
STAGING_IA_VERSION = "20260904-production-gpt-v93"
STAGING_STYLE_VERSION = (
    f"{THEME_VERSION}-contextual-safe-area-v128-stock-search-v129-ai-response-v130-home-signal-action-v131-notification-sheet-v132-ai-signal-spacing-v133-chart-pattern-integrity-v134-ai-stock-response-v135-morning-preliminary-v136-multi-signal-response-v137-discovery-search-contrast-v138-ai-signal-basis-stack-v140-ai-response-beginner-v141-semantic-focus-v142-header-action-icons-v143-gpt-page-summary-v144-gpt-briefing-v145-plain-language-detail-v146-investor-action-copy-v147-investor-situation-loading-v148-position-guide-v149-position-input-v150-live-quote-decision-plan-v151-manual-refresh-holding-map-v152-notification-consent-v153"
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
STAGING_CROSS_MARKET_PATH = "/market/cross-market"
STAGING_MORNING_MONEY_HISTORY_PATH = "/briefings/morning-money/history"
STAGING_RECOMMENDATIONS_PATH = "/market/recommendations"
STAGING_RECOMMENDATION_SUPPLEMENT_TTL_SECONDS = 120.0
STAGING_RECOMMENDATION_REFRESHING_MAX_AGE_SECONDS = 30 * 60
STAGING_MORNING_MONEY_HISTORY_TTL_SECONDS = 120.0
_staging_morning_money_history_cache: dict[int, tuple[float, bytes]] = {}
_staging_recommendation_supplement_cache: dict[
    tuple[str, str], tuple[float, dict[str, Any]]
] = {}
STAGING_PAGE_SUMMARY_PATH = "/staging-ai/page-summary"
STAGING_PAGE_SUMMARY_MAX_BODY_BYTES = 64 * 1024
STAGING_PAGE_SUMMARY_RATE_WINDOW_SECONDS = 60.0
STAGING_PAGE_SUMMARY_RATE_PER_CLIENT = 15
STAGING_PAGE_SUMMARY_RATE_GLOBAL = 120
_staging_page_summary_client_requests: dict[str, deque[float]] = {}
_staging_page_summary_global_requests: deque[float] = deque()
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


class _StagingRequestBodyTooLarge(ValueError):
    pass


async def _read_staging_request_body(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message.get("type") == "http.disconnect":
            raise ConnectionError("client disconnected")
        if message.get("type") != "http.request":
            continue
        chunk = bytes(message.get("body") or b"")
        size += len(chunk)
        if size > STAGING_PAGE_SUMMARY_MAX_BODY_BYTES:
            raise _StagingRequestBodyTooLarge("request body is too large")
        chunks.append(chunk)
        if not message.get("more_body", False):
            return b"".join(chunks)


def _allow_staging_page_summary_request(scope: dict[str, Any]) -> bool:
    now = monotonic()
    cutoff = now - STAGING_PAGE_SUMMARY_RATE_WINDOW_SECONDS
    while _staging_page_summary_global_requests and _staging_page_summary_global_requests[0] <= cutoff:
        _staging_page_summary_global_requests.popleft()
    for key, requests in list(_staging_page_summary_client_requests.items()):
        while requests and requests[0] <= cutoff:
            requests.popleft()
        if not requests:
            _staging_page_summary_client_requests.pop(key, None)
    client = scope.get("client")
    client_key = str(client[0]) if isinstance(client, (tuple, list)) and client else "unknown"
    client_requests = _staging_page_summary_client_requests.setdefault(client_key, deque())
    if (
        len(client_requests) >= STAGING_PAGE_SUMMARY_RATE_PER_CLIENT
        or len(_staging_page_summary_global_requests) >= STAGING_PAGE_SUMMARY_RATE_GLOBAL
    ):
        return False
    client_requests.append(now)
    _staging_page_summary_global_requests.append(now)
    return True


async def _send_staging_json(
    send: Send,
    *,
    status: int,
    payload: Mapping[str, Any],
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store"),
        (b"x-content-type-options", b"nosniff"),
        (b"x-robots-tag", b"noindex, nofollow, noarchive"),
        (b"x-staging-theme", THEME_VERSION.encode("ascii")),
    ]
    headers.extend(extra_headers or [])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body, "more_body": False})


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
    if path.startswith("/us/stock/"):
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


def _staging_date_value(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _staging_recommendation_state(
    current: object,
    *,
    today: date,
) -> str | None:
    if not isinstance(current, dict) or current.get("live_observation"):
        return None
    action = str(current.get("action") or "")
    position_open = bool(current.get("position_open"))
    confirmation = current.get("entry_confirmation")
    confirmation_allowed = (
        isinstance(confirmation, dict) and confirmation.get("allowed") is True
    )
    if action == "entry_pending" and not position_open and confirmation_allowed:
        return "entry_confirmed"
    if action not in {"entered", "holding"} or not position_open:
        return None

    lifecycle = current.get("lifecycle")
    transition = (
        lifecycle.get("latest_transition")
        if isinstance(lifecycle, dict) and isinstance(lifecycle.get("latest_transition"), dict)
        else {}
    )
    if (
        _staging_date_value(current.get("entry_date")) == today
        and _staging_date_value(transition.get("transition_date")) == today
        and str(transition.get("side") or "").lower() == "buy"
        and confirmation_allowed
    ):
        return "entered_today"
    return None


def _staging_recommendation_signal_date(item: Mapping[str, Any]) -> date | None:
    direct = _staging_date_value(item.get("signal_date"))
    if direct is not None:
        return direct
    current = item.get("current")
    lifecycle = current.get("lifecycle") if isinstance(current, Mapping) else None
    transition = (
        lifecycle.get("latest_transition") if isinstance(lifecycle, Mapping) else None
    )
    return (
        _staging_date_value(transition.get("signal_date"))
        if isinstance(transition, Mapping)
        else None
    )


def _staging_recommendation_universe_eligible(item: Mapping[str, Any]) -> bool:
    try:
        market_cap_rank = int(item.get("market_cap_rank"))
    except (TypeError, ValueError):
        market_cap_rank = None
    if market_cap_rank is not None and market_cap_rank > 100:
        return False
    return str(item.get("universe_tier") or "").lower() != "extended"


def _staging_recommendation_signal_usable(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("status") == "ready":
        return True
    if payload.get("status") != "refreshing" or not isinstance(payload.get("items"), list):
        return False
    try:
        snapshot_age_seconds = float(payload.get("snapshot_age_seconds"))
    except (TypeError, ValueError):
        return False
    return 0 <= snapshot_age_seconds <= STAGING_RECOMMENDATION_REFRESHING_MAX_AGE_SECONDS


async def _build_staging_recommendation_supplements(
    client: httpx.AsyncClient,
    signal_payload: dict[str, Any] | None,
    existing_items: list[dict[str, Any]],
    *,
    reference_date: date | None = None,
    max_items: int = 20,
) -> list[dict[str, Any]]:
    """Rebuild missing staging cards from canonical public, rule-owned data.

    The canonical recommendation response may remove a condition-confirmed
    stock at the instant its next-session opening entry is applied.  Staging
    keeps that same-day record visible by recomputing the separate
    recommendation score from the public stock dashboard and reading the
    condition-day close from public price history.  The market signal score is
    never substituted for the recommendation score.
    """

    if not _staging_recommendation_signal_usable(signal_payload):
        return []
    today = reference_date or datetime.now(KST).date()
    existing_codes = {
        str(item.get("code") or "").strip()
        for item in existing_items
        if isinstance(item, dict)
    }
    eligible: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for raw_item in signal_payload.get("items") or []:
        if not isinstance(raw_item, dict):
            continue
        code = str(raw_item.get("code") or "").strip()
        if not code or code in existing_codes or code in seen_codes:
            continue
        if not _staging_recommendation_universe_eligible(raw_item):
            continue
        if _staging_recommendation_state(raw_item.get("current"), today=today) is None:
            continue
        if _staging_recommendation_signal_date(raw_item) is None:
            continue
        seen_codes.add(code)
        eligible.append(raw_item)
    eligible.sort(
        key=lambda item: float(
            item.get("score")
            or (item.get("current") or {}).get("score")
            or 0
        ),
        reverse=True,
    )

    async def build_one(signal_item: dict[str, Any]) -> dict[str, Any] | None:
        code = str(signal_item.get("code") or "").strip()
        signal_date = _staging_recommendation_signal_date(signal_item)
        if not code or signal_date is None:
            return None
        cache_key = (code, signal_date.isoformat())
        cached = _staging_recommendation_supplement_cache.get(cache_key)
        if cached and monotonic() - cached[0] <= STAGING_RECOMMENDATION_SUPPLEMENT_TTL_SECONDS:
            return dict(cached[1])
        try:
            dashboard_response, prices_response = await asyncio.gather(
                client.get(
                    f"{STAGING_DATA_UPSTREAM}/stocks/{code}/dashboard",
                    params={"include_profile": 0, "include_live": 0},
                    headers={"Accept": "application/json"},
                ),
                client.get(
                    f"{STAGING_DATA_UPSTREAM}/stocks/{code}/prices",
                    params={
                        "from_date": signal_date.isoformat(),
                        "to_date": signal_date.isoformat(),
                        "limit": 5,
                    },
                    headers={"Accept": "application/json"},
                ),
            )
            dashboard_response.raise_for_status()
            prices_response.raise_for_status()
            dashboard = dashboard_response.json()
            prices = prices_response.json()
            if not isinstance(dashboard, dict) or not isinstance(prices, list):
                return None
            condition_row = next(
                (
                    row
                    for row in prices
                    if isinstance(row, dict)
                    and _staging_date_value(row.get("trade_date")) == signal_date
                    and row.get("close") not in (None, "")
                ),
                None,
            )
            if condition_row is None:
                return None
            item = _score_dashboard(dashboard)
        except (httpx.HTTPError, AttributeError, ArithmeticError, TypeError, ValueError, KeyError):
            return None
        item.pop("_quant_live_quote", None)
        item["price"] = condition_row["close"]
        item["condition_price"] = condition_row["close"]
        item["recommended_at"] = (
            signal_item.get("signal_at")
            or signal_item.get("signal_date")
            or signal_payload.get("as_of")
        )
        for key in (
            "sector",
            "industry",
            "investment_sector",
            "investment_sector_label",
        ):
            if signal_item.get(key) not in (None, ""):
                item[key] = signal_item[key]
        _staging_recommendation_supplement_cache[cache_key] = (monotonic(), dict(item))
        return item

    results = await asyncio.gather(*(build_one(item) for item in eligible[:max_items]))
    return [item for item in results if isinstance(item, dict)]


def _rewrite_staging_recommendation_contract(
    body: bytes,
    signal_payload: dict[str, Any] | None,
    *,
    requested_limit: int | None = None,
    reference_date: date | None = None,
    supplemental_items: list[dict[str, Any]] | None = None,
) -> bytes:
    """Expose confirmed entries through the day their opening entry is applied."""

    try:
        payload = json.loads(body)
    except (TypeError, ValueError, json.JSONDecodeError):
        return body
    if not isinstance(payload, dict):
        return body

    signal_ready = _staging_recommendation_signal_usable(signal_payload)
    signal_items = (
        signal_payload.get("items")
        if signal_ready and isinstance(signal_payload.get("items"), list)
        else []
    )
    today = reference_date or datetime.now(KST).date()
    eligible_by_code: dict[str, tuple[str, dict[str, Any]]] = {}
    for raw_item in signal_items:
        if not isinstance(raw_item, dict):
            continue
        if not _staging_recommendation_universe_eligible(raw_item):
            continue
        current = raw_item.get("current")
        recommendation_state = _staging_recommendation_state(current, today=today)
        if recommendation_state is None:
            continue
        code = str(raw_item.get("code") or "").strip()
        if code:
            eligible_by_code[code] = (recommendation_state, raw_item)

    source_items = list(payload.get("items")) if isinstance(payload.get("items"), list) else []
    source_codes = {
        str(item.get("code") or "").strip()
        for item in source_items
        if isinstance(item, dict)
    }
    for supplemental in supplemental_items or []:
        code = str(supplemental.get("code") or "").strip()
        if code and code not in source_codes:
            source_items.append(supplemental)
            source_codes.add(code)
    filtered: list[dict[str, Any]] = []
    for raw_item in source_items:
        if not isinstance(raw_item, dict):
            continue
        code = str(raw_item.get("code") or "").strip()
        eligible_record = eligible_by_code.get(code)
        if eligible_record is None:
            continue
        recommendation_state, signal_item = eligible_record
        current = signal_item.get("current")
        if not isinstance(current, dict):
            continue
        entered_today = recommendation_state == "entered_today"
        recommendation_label = "보유 유지" if entered_today else "신규 매수 대기"
        item = dict(raw_item)
        if item.get("condition_price") in (None, ""):
            item["condition_price"] = item.get("price")
        compact_signal = (
            dict(item.get("ai_trade_signal"))
            if isinstance(item.get("ai_trade_signal"), dict)
            else {}
        )
        compact_current = (
            dict(compact_signal.get("current"))
            if isinstance(compact_signal.get("current"), dict)
            else {}
        )
        compact_current.update(current)
        signal_as_of = signal_payload.get("as_of") if isinstance(signal_payload, dict) else None
        signal_strategy = (
            signal_payload.get("strategy_version")
            if isinstance(signal_payload, dict)
            else None
        )
        compact_signal.update(
            {
                "data_state": "ready",
                "as_of": compact_signal.get("as_of") or signal_as_of,
                "strategy_version": compact_signal.get("strategy_version")
                or signal_strategy,
                "current": compact_current,
            }
        )
        item["ai_trade_signal"] = compact_signal
        item["score_action"] = item.get("action")
        item["score_decision_reason"] = item.get("decision_reason")
        item["action"] = recommendation_label
        item["decision_reason"] = (
            "추천 기준을 통과한 뒤 AI 전략이 보유 중이며, 현재는 추가 매수보다 보유 기준을 확인하는 단계입니다."
            if entered_today
            else "추천 기준과 가격 조건, 서로 다른 확인 자료를 모두 통과해 신규 매수를 기다리는 단계입니다."
        )
        item["recommendation_state"] = recommendation_state
        item["recommendation_label"] = recommendation_label
        item["buy_condition_met"] = True
        item["buy_condition_as_of"] = (
            signal_item.get("signal_at")
            or signal_item.get("signal_date")
            or current.get("as_of")
        )
        item["recommendation_entry_date"] = current.get("entry_date") if entered_today else None
        item["strategy_entry_price"] = current.get("entry_price") if entered_today else None
        filtered.append(item)

    filtered.sort(
        key=lambda item: float(item.get("score") or 0),
        reverse=True,
    )
    for rank, item in enumerate(filtered, start=1):
        item["rank"] = rank

    qualified_count = len(filtered)
    pending_count = sum(
        1 for item in filtered if item.get("recommendation_state") == "entry_confirmed"
    )
    entered_today_count = sum(
        1 for item in filtered if item.get("recommendation_state") == "entered_today"
    )
    if requested_limit is not None:
        filtered = filtered[: max(0, requested_limit)]

    original_candidate_count = int(payload.get("candidate_count") or len(source_items))
    payload["screened_count"] = int(payload.get("universe_count") or original_candidate_count)
    payload["candidate_count"] = len(eligible_by_code)
    payload["qualified_count"] = qualified_count
    payload["pending_count"] = pending_count
    payload["entered_today_count"] = entered_today_count
    payload["selection_rule"] = "confirmed_entry_pending_or_entered_today"
    payload["selection_state"] = "ready" if signal_ready else "unavailable"
    payload["selection_refreshing"] = bool(
        signal_ready
        and isinstance(signal_payload, dict)
        and signal_payload.get("status") == "refreshing"
    )
    payload["selection_message"] = (
        (
            "최신 시장 데이터를 확인 중이며, 확인이 끝난 종목의 현재 AI 판단을 보여드립니다."
            if payload["selection_refreshing"]
            else "추천 기준을 통과한 종목을 신규 매수 대기와 보유 유지 상태로 나눠 보여드립니다."
        )
        if payload["selection_state"] == "ready"
        else "현재 판단을 확인하지 못해 추천 종목을 표시하지 않습니다. 잠시 후 다시 확인해 주세요."
    )
    payload["methodology"] = [
        "시장 대표 종목 가운데 추천 기준과 가격 조건을 모두 통과한 종목만 보여드립니다.",
        "아직 매수 전이면 신규 매수 대기, 이미 AI 전략이 매수했다면 보유 유지로 구분합니다.",
        "조건을 확인 중이거나 매도 판단이 나온 종목은 제외하고, 기준을 통과한 종목끼리 추천 점수로 비교합니다.",
    ]
    payload["items"] = filtered
    return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")


async def _read_staging_upstream(
    scope: dict[str, Any],
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    path = str(scope.get("path") or "/")
    query = bytes(scope.get("query_string") or b"").decode("latin-1")
    requested_limit: int | None = None
    upstream_query = query
    if path == STAGING_RECOMMENDATIONS_PATH:
        parsed_query = parse_qs(query, keep_blank_values=True)
        try:
            requested_limit = max(1, min(20, int((parsed_query.get("limit") or ["8"])[-1])))
        except (TypeError, ValueError):
            requested_limit = 8
        parsed_query["limit"] = ["20"]
        parsed_query["candidate_limit"] = ["100"]
        upstream_query = "&".join(
            f"{key}={value}"
            for key, values in parsed_query.items()
            for value in values
        )
    url = f"{STAGING_DATA_UPSTREAM}{path}{f'?{upstream_query}' if upstream_query else ''}"
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
            if path == STAGING_RECOMMENDATIONS_PATH:
                signal_payload: dict[str, Any] | None = None
                try:
                    signal_response = await client.get(
                        f"{STAGING_DATA_UPSTREAM}/market/quant-signals",
                        params={"universe_limit": 150, "limit": 0, "recent_days": 30},
                        headers={"Accept": "application/json"},
                    )
                    signal_response.raise_for_status()
                    decoded_signal_payload = signal_response.json()
                    if isinstance(decoded_signal_payload, dict):
                        signal_payload = decoded_signal_payload
                except (httpx.HTTPError, ValueError, json.JSONDecodeError):
                    signal_payload = None
                try:
                    source_payload = json.loads(body)
                    source_items = (
                        source_payload.get("items")
                        if isinstance(source_payload, dict)
                        and isinstance(source_payload.get("items"), list)
                        else []
                    )
                    supplemental_items = await _build_staging_recommendation_supplements(
                        client,
                        signal_payload,
                        [item for item in source_items if isinstance(item, dict)],
                        max_items=max(requested_limit or 8, 8),
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    supplemental_items = []
                body = _rewrite_staging_recommendation_contract(
                    body,
                    signal_payload,
                    requested_limit=requested_limit,
                    supplemental_items=supplemental_items,
                )
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


async def _build_staging_cross_market(scope: dict[str, Any]) -> dict[str, Any]:
    query = bytes(scope.get("query_string") or b"").decode("latin-1")
    parsed_query = parse_qs(query, keep_blank_values=True)
    try:
        limit = max(2, min(120, int((parsed_query.get("limit") or ["30"])[-1])))
    except (TypeError, ValueError):
        limit = 30
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=STAGING_DATA_TIMEOUT_SECONDS,
    ) as client:
        korea_response, us_response = await asyncio.gather(
            client.get(
                f"{STAGING_DATA_UPSTREAM}/market/indices",
                params={"limit": limit},
                headers={"Accept": "application/json"},
            ),
            client.get(
                f"{STAGING_DATA_UPSTREAM}/market/global-assets",
                params={"limit": limit},
                headers={"Accept": "application/json"},
            ),
        )
    korea_response.raise_for_status()
    us_response.raise_for_status()
    korea = korea_response.json()
    us = us_response.json()
    if not isinstance(korea, dict) or not isinstance(us, dict):
        raise ValueError("cross-market upstream payload must be an object")
    items = [
        item
        for payload in (korea, us)
        for item in (payload.get("items") or [])
        if isinstance(item, dict) and item.get("as_of")
    ]
    as_of_values = sorted(str(item["as_of"]) for item in items)
    return {
        "korea": korea,
        "us": us,
        "as_of": as_of_values[-1] if as_of_values else None,
        "source": "snapshot-composite",
        "refresh_interval_seconds": 30,
    }


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
        if scope.get("method") == "POST" and path == STAGING_PAGE_SUMMARY_PATH:
            fetch_site = _scope_header(scope, b"sec-fetch-site").lower()
            if fetch_site == "cross-site":
                await _send_staging_json(
                    send,
                    status=403,
                    payload={"message": "교차 사이트 요청은 허용하지 않습니다."},
                )
                return
            if not _allow_staging_page_summary_request(scope):
                await _send_staging_json(
                    send,
                    status=429,
                    payload={"message": "요약 요청이 잠시 많습니다. 기존 데이터 문구를 유지합니다."},
                    extra_headers=[(b"retry-after", b"60")],
                )
                return
            try:
                raw_body = await _read_staging_request_body(receive)
                payload = json.loads(raw_body or b"{}")
                if not isinstance(payload, dict):
                    raise TypeError("request payload must be an object")
                result = await summarize_staging_page(payload)
            except _StagingRequestBodyTooLarge:
                await _send_staging_json(
                    send,
                    status=413,
                    payload={"message": "요약 요청 크기가 제한을 초과했습니다."},
                )
                return
            except (ConnectionError, json.JSONDecodeError, TypeError, ValueError):
                await _send_staging_json(
                    send,
                    status=400,
                    payload={"message": "요약 요청 형식을 확인해 주세요."},
                )
                return
            await _send_staging_json(
                send,
                status=200,
                payload=result.model_dump(mode="json"),
            )
            return

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
            and path == STAGING_CROSS_MARKET_PATH
            and STAGING_DATA_UPSTREAM
        ):
            try:
                cross_market_payload = await _build_staging_cross_market(scope)
            except (httpx.HTTPError, TypeError, ValueError, json.JSONDecodeError):
                await _send_staging_json(
                    send,
                    status=502,
                    payload={"message": "국내·미국 시장 데이터를 불러오지 못했습니다."},
                )
                return
            await _send_staging_json(
                send,
                status=200,
                payload=cross_market_payload,
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
