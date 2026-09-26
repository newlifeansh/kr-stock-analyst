from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import Settings
from app.mcp_server import (
    FastMCP,
    _db_session,
    _json_safe,
    _transport_security,
    mcp_sdk_available,
)
from app.services.public_signal import (
    public_market_signal_payload,
    public_quant_signal_payload,
    public_stock_ai_analysis_payload,
)
from app.services.stock_ai_analysis import build_stock_ai_analysis
from app.services.ttl_cache import TTLCache
from app.services.us_market import (
    build_us_dashboard,
    build_us_quant_signals,
    resolve_us_stock,
)
from app.services.us_position_lifecycle import (
    load_us_position_lifecycle_snapshot,
    us_position_lifecycle_preparing_payload,
)

US_MCP_ANALYSIS_CACHE_SECONDS = 120
US_MCP_ANALYSIS_CACHE = TTLCache(maxsize=128)
US_FLOW_SEMANTICS = "dollar_volume_participation_proxy"
US_SIGNAL_ACTIONS = {
    "entry_pending",
    "entry_watch",
    "entered",
    "holding",
    "full_exit_pending",
    "exited",
}


def _symbol_key(value: object) -> str:
    return str(value or "").strip().upper().replace("-", ".")


def _snapshot_summary(feed: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": feed.get("status"),
        "data_state": feed.get("data_state"),
        "snapshot_id": feed.get("snapshot_id"),
        "snapshot_checksum": feed.get("snapshot_checksum"),
        "snapshot_generated_at": feed.get("snapshot_generated_at"),
        "universe_as_of": feed.get("universe_as_of"),
        "universe_count": feed.get("universe_count", 0),
        "evaluated_count": feed.get("evaluated_count", 0),
        "data_coverage_count": feed.get("data_coverage_count", 0),
        "new_entries_allowed": feed.get("new_entries_allowed", False),
        "strategy_version": feed.get("strategy_version"),
        "execution_enabled": False,
    }


def _load_us_feed(now: Optional[datetime] = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    with _db_session() as db:
        feed = load_us_position_lifecycle_snapshot(db, now=current)
    return feed or us_position_lifecycle_preparing_payload(now=current)


def _matching_row(rows: object, symbol: str) -> Optional[dict[str, Any]]:
    if not isinstance(rows, list):
        return None
    normalized = _symbol_key(symbol)
    return next(
        (
            dict(item)
            for item in rows
            if isinstance(item, dict) and _symbol_key(item.get("code")) == normalized
        ),
        None,
    )


def _public_reasons_ready(value: object) -> bool:
    if not isinstance(value, list):
        return False
    reasons = [item for item in value if isinstance(item, dict)]
    return bool(
        [str(item.get("key") or "") for item in reasons]
        == ["trend_20d", "trend_60d", "flow"]
        and all(item.get("available") is True for item in reasons)
    )


def _public_signal_for_symbol(
    feed: dict[str, Any],
    symbol: str,
    *,
    member: Optional[dict[str, Any]],
    signal: Optional[dict[str, Any]],
    member_evidence: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if signal is not None:
        one_item_feed = deepcopy(feed)
        one_item_feed["items"] = [signal]
        public_feed = public_market_signal_payload(
            build_us_quant_signals(limit=1, recent_days=30, feed=one_item_feed)
        )
        items = public_feed.get("items")
        if isinstance(items, list) and items:
            return dict(items[0])
    if member is None or member_evidence is None:
        return None
    fallback = {
        **member_evidence,
        "code": member.get("code") or symbol,
        "name": member.get("name") or symbol,
        "market": member.get("market") or "NASDAQ",
        "currency": "USD",
        "strategy_version": feed.get("strategy_version"),
        "data_state": member_evidence.get("data_state") or feed.get("data_state"),
        "current": dict(member_evidence.get("current") or {}),
    }
    return public_quant_signal_payload(fallback, context=fallback)


def list_us_stock_signals_payload(
    limit: int = 20,
    recent_days: int = 30,
) -> dict[str, Any]:
    """Read the stored US Top100 signal snapshot without upstream refreshes."""

    feed = _load_us_feed()
    payload = build_us_quant_signals(
        limit=max(1, min(int(limit), 50)),
        recent_days=max(1, min(int(recent_days), 90)),
        feed=feed,
    )
    result = public_market_signal_payload(payload)
    result["delivery"] = {
        "market": "US",
        "source_mode": "stored_snapshot",
        "upstream_refresh_allowed": False,
        "execution_enabled": False,
    }
    return _json_safe(result)


def get_us_stock_analysis_payload(symbol: str) -> dict[str, Any]:
    """Return one public US analysis plus its canonical stored signal identity."""

    try:
        stock = resolve_us_stock(symbol)
    except Exception:
        return {
            "ok": False,
            "symbol": str(symbol or "").strip().upper(),
            "message": "미국 종목을 찾지 못했습니다.",
        }

    code = str(stock.get("code") or symbol).strip().upper()
    feed = _load_us_feed()
    member = _matching_row(feed.get("universe_members"), code)
    signal = _matching_row(feed.get("items"), code)
    member_evidence = _matching_row(feed.get("public_member_signals"), code)
    evidence_source = member_evidence or signal

    snapshot_ready = bool(
        feed.get("status") == "ready"
        and feed.get("data_state") == "ready"
        and str(feed.get("snapshot_id") or "").strip()
        and str(feed.get("snapshot_checksum") or "").strip()
    )
    is_current_member = member is not None if snapshot_ready else None
    member_ready = bool(
        snapshot_ready
        and feed.get("new_entries_allowed") is True
        and member is not None
        and evidence_source is not None
        and evidence_source.get("data_state") == "ready"
        and _public_reasons_ready(evidence_source.get("public_reasons"))
    )
    action = "no_signal"
    source_current = dict(signal.get("current") or {}) if signal else {}
    source_action = str(source_current.get("action") or "")
    if member_ready and signal is not None and source_action in US_SIGNAL_ACTIONS:
        action = source_action
    label_by_action = {
        "entry_pending": "예비 매수",
        "entry_watch": "예비 포착",
        "entered": "전략 매수 확정",
        "holding": "전략 보유",
        "full_exit_pending": "전략 매도 대기",
        "exited": "전략 매도 확정",
        "no_signal": "관망",
    }
    evidence_session_date = (
        evidence_source.get("signal_date")
        if member_ready and evidence_source is not None
        else feed.get("universe_as_of") if snapshot_ready else None
    )
    canonical_as_of = (
        evidence_source.get("signal_at")
        if evidence_source is not None and evidence_source.get("signal_at")
        else feed.get("universe_as_of") or feed.get("as_of")
    )
    canonical_current = {
        "action": action,
        "label": label_by_action[action],
        "position_open": action in {"entered", "holding", "full_exit_pending"},
        "model_exposure_percent": (
            100 if action in {"entered", "holding", "full_exit_pending"} else 0
        ),
        "live_observation": False,
        "as_of": evidence_session_date or canonical_as_of,
    }
    if action in {"entered", "holding", "full_exit_pending", "exited"}:
        canonical_current.update(
            {
                "lifecycle": dict(source_current.get("lifecycle") or {}),
                "entry_date": source_current.get("entry_date"),
                "entry_price": source_current.get("entry_price"),
                "unrealized_return": source_current.get("unrealized_return"),
            }
        )

    try:
        dashboard = US_MCP_ANALYSIS_CACHE.get_or_set(
            ("dashboard", code),
            US_MCP_ANALYSIS_CACHE_SECONDS,
            lambda: build_us_dashboard(code, refresh=False),
        )
    except Exception:
        return {
            "ok": False,
            "symbol": code,
            "snapshot": _json_safe(_snapshot_summary(feed)),
            "message": "미국 종목 분석 자료를 불러오지 못했습니다.",
        }

    analysis = dict(build_stock_ai_analysis(dashboard))
    public_evidence_status = (
        "ready"
        if member_ready
        else "not_applicable"
        if snapshot_ready and is_current_member is False
        else "preparing"
        if not snapshot_ready
        else "unavailable"
    )
    public_reasons = (
        list(evidence_source.get("public_reasons") or [])
        if member_ready and evidence_source is not None
        else []
    )
    analysis.update(
        {
            "code": code,
            "name": stock.get("name") or code,
            "market": stock.get("market") or "NASDAQ",
            "as_of": canonical_as_of,
            "stance": label_by_action[action],
            "flow_semantics": US_FLOW_SEMANTICS,
            "strategy_version": feed.get("strategy_version"),
            "rollout_mode": feed.get("rollout_mode"),
            "execution_enabled": False,
            "status": feed.get("status"),
            "data_state": feed.get("data_state"),
            "snapshot_id": feed.get("snapshot_id"),
            "snapshot_checksum": feed.get("snapshot_checksum"),
            "new_entries_allowed": member_ready,
            "is_current_universe_member": is_current_member,
            "public_evidence_status": public_evidence_status,
            "evidence_session_date": evidence_session_date,
            "current": canonical_current,
            "public_reasons": public_reasons,
        }
    )
    public_analysis = public_stock_ai_analysis_payload(
        analysis,
        context={
            "as_of": canonical_as_of,
            "flow_semantics": US_FLOW_SEMANTICS,
        },
    )
    public_signal = _public_signal_for_symbol(
        feed,
        code,
        member=member,
        signal=signal,
        member_evidence=member_evidence,
    )
    return _json_safe(
        {
            "ok": True,
            "symbol": code,
            "snapshot": _snapshot_summary(feed),
            "signal": public_signal,
            "analysis": public_analysis,
            "delivery": {
                "market": "US",
                "source_mode": "stored_signal_plus_cached_analysis",
                "upstream_refresh_allowed": False,
                "analysis_cache_seconds": US_MCP_ANALYSIS_CACHE_SECONDS,
                "execution_enabled": False,
            },
        }
    )


def build_us_mcp_server(settings: Settings):
    if not mcp_sdk_available() or FastMCP is None:
        return None

    server = FastMCP(
        name=settings.us_mcp_server_name,
        instructions=(
            "이 서버는 개인용 미국 주식 시그널과 종목 분석을 읽기 전용으로 제공합니다. "
            "list_us_stock_signals는 마지막 완료 미국장 Top100 스냅샷을 읽고, "
            "get_us_stock_analysis는 종목의 공개 분석과 동일 스냅샷의 시그널을 함께 반환합니다. "
            "도구는 강제 데이터 갱신이나 주문을 실행하지 않습니다. 모델 보유·매도 상태는 "
            "전략 재현 결과이며 실제 주문이나 사용자의 개인 보유 내역이 아닙니다."
        ),
        website_url=settings.mcp_public_base_url,
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=_transport_security(settings),
        log_level=settings.mcp_log_level,
    )

    @server.prompt(
        name="us_stock_signal_review",
        title="미국 종목 시그널 점검",
        description="저장 시그널과 종목 분석을 같은 스냅샷 기준으로 확인합니다.",
    )
    def us_stock_signal_review(symbol: str = "NVDA") -> str:
        return (
            "먼저 list_us_stock_signals로 최신 snapshot_id와 상태를 확인하고, "
            f"get_us_stock_analysis(symbol='{symbol}')로 같은 종목의 분석을 조회하세요. "
            "근거가 unavailable이면 추정하지 말고 준비 중이라고 설명하며, 모델 상태를 실제 주문으로 표현하지 마세요."
        )

    @server.tool(
        name="list_us_stock_signals",
        title="미국 종목 시그널 목록",
        description=(
            "마지막 완료 미국장 Top100의 저장 시그널을 조회합니다. "
            "호출 중 외부 시세 갱신이나 재계산을 시작하지 않습니다."
        ),
        structured_output=True,
    )
    def list_us_stock_signals(
        limit: int = 20,
        recent_days: int = 30,
    ) -> dict[str, Any]:
        return list_us_stock_signals_payload(limit=limit, recent_days=recent_days)

    @server.tool(
        name="get_us_stock_analysis",
        title="미국 종목 시그널·분석",
        description=(
            "티커 기준으로 공개 종목 분석과 저장된 canonical 시그널을 함께 조회합니다. "
            "예: NVDA, AAPL, BRK.B. 강제 갱신과 주문 실행은 지원하지 않습니다."
        ),
        structured_output=True,
    )
    def get_us_stock_analysis(symbol: str) -> dict[str, Any]:
        return get_us_stock_analysis_payload(symbol)

    return server
