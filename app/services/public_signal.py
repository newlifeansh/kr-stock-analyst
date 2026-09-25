from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Optional


PUBLIC_SIGNAL_REASON_KEYS = ("trend_20d", "trend_60d", "flow")
PUBLIC_SIGNAL_DECISION_REASON = "20일·60일·수급 흐름을 함께 확인한 AI 판단입니다."
PUBLIC_SIGNAL_NEXT_CHECK = "20일·60일 가격 흐름과 수급 변화를 다시 확인하세요."
PUBLIC_SIGNAL_SCOPE_NOTE = "외부에는 20일·60일·수급 세 가지 핵심 근거만 공개합니다."
US_DOLLAR_VOLUME_FLOW_SEMANTICS = "dollar_volume_participation_proxy"
US_DOLLAR_VOLUME_NOTICE = "가격×거래량 기반 참여도이며 투자자 순매수나 ETF 순유입이 아닙니다."
US_PUBLIC_SIGNAL_DECISION_REASON = "20일·60일 가격 흐름과 거래대금 참여도를 함께 확인한 예비 판단입니다."
US_PUBLIC_SIGNAL_NEXT_CHECK = "20일·60일 가격 흐름과 거래대금 참여도를 다시 확인하세요."
US_PUBLIC_MODEL_LIFECYCLE_REASON = (
    "완료된 미국장 종가 신호와 다음 정규장 시가를 기준으로 재현한 전략 상태입니다. 실제 주문이나 개인 보유 내역이 아닙니다."
)
US_PUBLIC_MODEL_LIFECYCLE_NEXT_CHECK = (
    "다음 완료 미국장에서 위험선과 20일·60일 가격 흐름, 거래대금 참여도를 다시 확인하세요."
)
US_PUBLIC_SIGNAL_UNAVAILABLE_REASON = (
    "현재 공개 근거로는 예비 매수 조건이 확인되지 않아 관망합니다."
)
US_PUBLIC_SIGNAL_UNAVAILABLE_NEXT_CHECK = (
    "다음 완료 정규장의 상위 100종목과 가격·거래대금 참여도를 다시 확인하세요."
)
US_PUBLIC_SIGNAL_PREPARING_REASON = (
    "완료된 미국 정규장 스냅샷을 준비 중이어서 관망합니다."
)
US_PUBLIC_SIGNAL_PREPARING_NEXT_CHECK = (
    "준비 완료된 동일 스냅샷에서 상위 100종목과 공개 근거를 다시 확인하세요."
)
US_PUBLIC_SIGNAL_OUTSIDE_REASON = (
    "현재 미국 시가총액 상위 100종목 밖이어서 관망합니다."
)
US_PUBLIC_SIGNAL_METHODOLOGY = (
    "완료된 미국 정규장의 시가총액 상위 100종목에서 분할·배당 수정 OHLC 가격 흐름, "
    "SPY·QQQ 시장 국면, 검토된 섹터 ETF 대비 상대 흐름과 거래대금 참여도를 비교한 "
    f"예비·전략 상태 신호입니다. 확정은 다음 정규장 시가를 통과한 모델 재현이며 실제 주문이 아닙니다. {US_DOLLAR_VOLUME_NOTICE}"
)

_POSITIVE_STATES = {"positive", "supportive", "approved", "ready", "bullish"}
_NEGATIVE_STATES = {"negative", "caution", "blocked", "risk", "bearish"}
_UNAVAILABLE_STATES = {"unavailable", "missing", "stale", "limited"}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _items(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _hide_numeric_signal_scores(value: object) -> object:
    """Keep response shapes stable while removing public numeric signal scores."""

    if isinstance(value, Mapping):
        return {
            key: None if key == "score" else _hide_numeric_signal_scores(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_hide_numeric_signal_scores(item) for item in value]
    return value


_FORBIDDEN_US_PUBLIC_FIELDS = {
    "score",
    "confidence",
    "entry_score_threshold",
    "strategy_version_history",
    "entry_setup",
    "entry_confirmation",
    "chase_veto",
    "guard_state",
    "us_evidence",
    "source_checks",
    "vetoes",
    "component_scores",
    "recommendation_observed_weight",
    "weights",
    "detailed_methodology",
    "trade_levels",
    "strategy_entry_price",
    "condition_price",
    "entry_price",
    "target_sell_price",
    "target_sell_status",
    "target_sell_delta",
    "partial_exit_price",
    "partial_exits",
    "stop_reference",
    "locked_profit_reference",
    "partial_exit_reference",
    "return_basis",
    "levels",
    "buy_low",
    "buy_high",
    "entry_low",
    "entry_high",
    "breakout",
    "stop",
    "first_sell",
    "target_price",
    "support_reference",
    "resistance_reference",
}


def _remove_forbidden_us_public_fields(value: object) -> object:
    """Remove private US decision inputs instead of publishing null placeholders."""

    if isinstance(value, Mapping):
        return {
            key: _remove_forbidden_us_public_fields(item)
            for key, item in value.items()
            if key not in _FORBIDDEN_US_PUBLIC_FIELDS
        }
    if isinstance(value, list):
        return [_remove_forbidden_us_public_fields(item) for item in value]
    return value


def _us_public_snapshot_identity_ready(payload: Mapping[str, Any]) -> bool:
    return bool(
        str(payload.get("status") or "").lower() == "ready"
        and str(payload.get("data_state") or "").lower() == "ready"
        and str(payload.get("snapshot_id") or "").strip()
        and str(payload.get("snapshot_checksum") or "").strip()
    )


def _us_public_snapshot_ready(payload: Mapping[str, Any]) -> bool:
    return bool(
        _us_public_snapshot_identity_ready(payload)
        and payload.get("new_entries_allowed") is True
    )


def _us_public_reasons_ready(value: object) -> bool:
    reasons = _items(value)
    return bool(
        [str(item.get("key") or "") for item in reasons]
        == list(PUBLIC_SIGNAL_REASON_KEYS)
        and all(item.get("available") is True for item in reasons)
    )


def _unavailable_us_public_reasons(as_of: object = None) -> list[dict[str, Any]]:
    reasons = [
        _reason(key, "unavailable", as_of=as_of)
        for key in PUBLIC_SIGNAL_REASON_KEYS
    ]
    flow = reasons[-1]
    flow["label"] = "거래대금 참여도"
    flow["summary"] = "가격×거래량 기반 거래대금 참여도를 확인할 자료가 부족합니다."
    flow["note"] = US_DOLLAR_VOLUME_NOTICE
    return reasons


def _fail_closed_us_public_signal(
    value: Mapping[str, Any],
    *,
    reason: str = US_PUBLIC_SIGNAL_PREPARING_NEXT_CHECK,
) -> dict[str, Any]:
    result = deepcopy(dict(value))
    current = dict(_mapping(result.get("current")))
    lifecycle = dict(_mapping(current.get("lifecycle")))
    lifecycle.update({"state": "no_signal", "label": "관망"})
    current.update(
        {
            "action": "no_signal",
            "label": "관망",
            "position_open": False,
            "model_exposure_percent": 0,
            "live_observation": False,
            "next_confirmation": reason,
        }
    )
    if lifecycle:
        current["lifecycle"] = lifecycle
    result.update(
        {
            "action": "no_signal",
            "signal": "관망",
            "is_preliminary": False,
            "current": current,
            "latest_preliminary": None,
        }
    )
    return result


def _normalized_state(value: object, *, available: bool = True) -> str:
    state = str(value or "neutral").strip().lower()
    if not available or state in _UNAVAILABLE_STATES:
        return "unavailable"
    if state in _POSITIVE_STATES:
        return "positive"
    if state in _NEGATIVE_STATES:
        return "negative"
    return "neutral"


def _state_from_number(value: object, *, midpoint: Optional[float] = None) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unavailable"
    if midpoint is not None:
        if number > midpoint + 5:
            return "positive"
        if number < midpoint - 5:
            return "negative"
        return "neutral"
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "neutral"


def _state_summary(key: str, state: str) -> str:
    copy = {
        "trend_20d": {
            "positive": "최근 20일 가격 흐름이 우호적입니다.",
            "negative": "최근 20일 가격 흐름이 주의 구간입니다.",
            "neutral": "최근 20일 가격 흐름의 방향이 뚜렷하지 않습니다.",
            "unavailable": "최근 20일 가격 흐름을 확인할 자료가 부족합니다.",
        },
        "trend_60d": {
            "positive": "20일선과 60일선의 흐름이 우호적입니다.",
            "negative": "20일선과 60일선의 흐름이 주의 구간입니다.",
            "neutral": "20일선과 60일선의 방향이 뚜렷하지 않습니다.",
            "unavailable": "60일 가격 흐름을 확인할 자료가 부족합니다.",
        },
        "flow": {
            "positive": "최근 수급 흐름이 우호적입니다.",
            "negative": "최근 수급 흐름이 주의 구간입니다.",
            "neutral": "최근 수급 방향이 뚜렷하지 않습니다.",
            "unavailable": "최근 수급을 확인할 자료가 부족합니다.",
        },
    }
    return copy[key][state]


def _reason(
    key: str,
    state: str,
    *,
    as_of: object = None,
) -> dict[str, Any]:
    normalized_state = _normalized_state(state, available=state != "unavailable")
    return {
        "key": key,
        "label": {"trend_20d": "20일", "trend_60d": "60일", "flow": "수급"}[key],
        "state": normalized_state,
        "summary": _state_summary(key, normalized_state),
        "as_of": as_of,
        "available": normalized_state != "unavailable",
    }


def _existing_public_reasons(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("key")): item
        for item in _items(payload.get("public_reasons"))
        if str(item.get("key")) in PUBLIC_SIGNAL_REASON_KEYS
    }


def build_public_signal_reasons(
    payload: Mapping[str, Any] | None,
    *,
    context: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return the only three explanations allowed on public signal surfaces."""

    source = _mapping(payload)
    fallback = _mapping(context)
    existing = _existing_public_reasons(source)
    factor_by_key = {
        str(item.get("key")): item for item in _items(source.get("factors"))
    }
    confirmation = _mapping(source.get("confirmation"))
    evidence_by_key = {
        str(item.get("key")): item for item in _items(confirmation.get("evidence"))
    }
    current = _mapping(source.get("current"))
    default_as_of = (
        source.get("price_through")
        or current.get("as_of")
        or source.get("as_of")
        or fallback.get("as_of")
    )

    momentum = factor_by_key.get("trend_20d") or factor_by_key.get("momentum")
    trend = factor_by_key.get("trend_60d") or factor_by_key.get("trend")
    flow = evidence_by_key.get("flow")

    fallback_momentum = _mapping(fallback.get("momentum"))
    one_month = fallback.get("one_month_return")
    if one_month is None:
        one_month = fallback_momentum.get("one_month_return")
    three_month = fallback.get("three_month_return")
    if three_month is None:
        three_month = fallback_momentum.get("three_month_return")
    component_scores = _mapping(fallback.get("component_scores"))
    fallback_flows = _mapping(fallback.get("flows"))
    flow_value = component_scores.get("flows")
    if flow_value is None:
        flow_value = fallback.get("trading_value_change")
    if flow_value is None:
        flow_value = fallback_momentum.get("trading_value_change")
    if flow_value is None:
        flow_values = [
            fallback_flows.get("foreign_net_buy_20d"),
            fallback_flows.get("institution_net_buy_20d"),
        ]
        numeric_flow_values = []
        for value in flow_values:
            try:
                numeric_flow_values.append(float(value))
            except (TypeError, ValueError):
                continue
        flow_value = sum(numeric_flow_values) if numeric_flow_values else None

    candidates: dict[str, dict[str, Any]] = {}
    for key in PUBLIC_SIGNAL_REASON_KEYS:
        saved = existing.get(key)
        if saved:
            available = saved.get("available") is not False
            state = _normalized_state(saved.get("state"), available=available)
            candidates[key] = _reason(
                key,
                state,
                as_of=saved.get("as_of") or default_as_of,
            )

    if "trend_20d" not in candidates:
        state = (
            _normalized_state(momentum.get("state"), available=momentum.get("available") is not False)
            if momentum
            else _state_from_number(one_month)
        )
        candidates["trend_20d"] = _reason("trend_20d", state, as_of=default_as_of)

    if "trend_60d" not in candidates:
        state = (
            _normalized_state(trend.get("state"), available=trend.get("available") is not False)
            if trend
            else _state_from_number(three_month)
        )
        candidates["trend_60d"] = _reason("trend_60d", state, as_of=default_as_of)

    if "flow" not in candidates:
        state = (
            _normalized_state(flow.get("state"), available=flow.get("available") is not False)
            if flow
            else _state_from_number(
                flow_value,
                midpoint=50.0 if component_scores.get("flows") is not None else None,
            )
        )
        candidates["flow"] = _reason(
            "flow",
            state,
            as_of=(flow.get("as_of") if flow else None) or default_as_of,
        )

    result = [candidates[key] for key in PUBLIC_SIGNAL_REASON_KEYS]
    flow_semantics = str(
        source.get("flow_semantics") or fallback.get("flow_semantics") or ""
    )
    if flow_semantics == US_DOLLAR_VOLUME_FLOW_SEMANTICS:
        result[0]["label"] = "20일 가격"
        result[1]["label"] = "60일 가격"
        flow_reason = result[-1]
        flow_reason["label"] = "거래대금 참여도"
        flow_reason["summary"] = {
            "positive": "최근 가격×거래량 기반 거래대금 참여도가 우호적입니다.",
            "negative": "최근 가격×거래량 기반 거래대금 참여도가 주의 구간입니다.",
            "neutral": "최근 가격×거래량 기반 거래대금 참여도 방향이 뚜렷하지 않습니다.",
            "unavailable": "가격×거래량 기반 거래대금 참여도를 확인할 자료가 부족합니다.",
        }[flow_reason["state"]]
        flow_reason["note"] = US_DOLLAR_VOLUME_NOTICE
    return result


def _redact_current_signal(
    current_value: object,
    public_reasons: list[dict[str, Any]],
) -> object:
    if not isinstance(current_value, Mapping):
        return current_value
    current = deepcopy(dict(current_value))
    current["entry_setup"] = None
    current["entry_confirmation"] = None
    current["reasons"] = [item["summary"] for item in public_reasons]
    current["next_confirmation"] = PUBLIC_SIGNAL_NEXT_CHECK
    levels = []
    for level in _items(current.get("levels")):
        public_level = deepcopy(dict(level))
        if "condition" in public_level:
            public_level["condition"] = PUBLIC_SIGNAL_DECISION_REASON
        levels.append(public_level)
    if isinstance(current.get("levels"), list):
        current["levels"] = levels
    return current


def _redact_preliminary_signal(value: object) -> object:
    if not isinstance(value, Mapping):
        return value
    preliminary = deepcopy(dict(value))
    if "reason" in preliminary:
        preliminary["reason"] = PUBLIC_SIGNAL_DECISION_REASON
    return preliminary


def public_quant_signal_payload(
    payload: Mapping[str, Any] | None,
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Redact one detailed signal payload at the public API boundary."""

    result = deepcopy(dict(_mapping(payload)))
    is_us_candidate = str(result.get("strategy_version") or "").startswith(
        "position-lifecycle-us-"
    )
    if is_us_candidate:
        result.pop("us_evidence", None)
        result.pop("guard_state", None)
        result.pop("entry_setup", None)
        result.pop("chase_veto", None)
    public_reasons = build_public_signal_reasons(result, context=context)
    result["public_reasons"] = public_reasons

    if "strategy_name" in result:
        result["strategy_name"] = "비밀노트 AI 시그널"
    for key in (
        "candidate_strategy_version",
        "entry_filter_version",
        "entry_filter_effective_date",
        "profit_preservation_effective_date",
        "tactical_exit_effective_date",
        "entry_score_threshold",
    ):
        if key in result:
            result[key] = None
    for key in (
        "strategy_version_history",
        "entry_filter_shadow_versions",
        "applied_principles",
        "excluded_principles",
    ):
        if key in result:
            result[key] = []
    if "methodology" in result:
        result["methodology"] = [
            US_DOLLAR_VOLUME_NOTICE if is_us_candidate else PUBLIC_SIGNAL_SCOPE_NOTE
        ]
    if "source" in result:
        result["source"] = (
            "가격·거래대금 참여도 공개 요약"
            if is_us_candidate
            else "가격·수급 공개 요약"
        )
    if "data_message" in result:
        result["data_message"] = (
            (
                "최신 가격·거래대금 참여도 자료로 계산했습니다."
                if is_us_candidate
                else "최신 가격·수급 자료로 계산했습니다."
            )
            if result.get("data_state") == "ready"
            else (
                "예비 시그널을 계산할 가격·거래대금 참여도 자료가 아직 부족합니다."
                if is_us_candidate
                else "AI 시그널을 계산할 가격·수급 자료가 아직 부족합니다."
            )
        )
    if "reason" in result and is_us_candidate:
        action = str(_mapping(result.get("current")).get("action") or "")
        result["reason"] = (
            US_PUBLIC_MODEL_LIFECYCLE_REASON
            if action in {"entered", "holding", "full_exit_pending", "exited"}
            else US_PUBLIC_SIGNAL_DECISION_REASON
        )

    result["factors"] = [
        {
            "key": item["key"],
            "label": item["label"],
            "score": None,
            "state": item["state"],
            "detail": item["summary"],
        }
        for item in public_reasons[:2]
    ]
    if isinstance(result.get("confirmation"), Mapping):
        confirmation = deepcopy(dict(result["confirmation"]))
        public_flow = public_reasons[2]
        confirmation.update(
            {
                "score": None,
                "available_count": int(public_flow["available"]),
                "total_count": 1,
                "note": (
                    US_DOLLAR_VOLUME_NOTICE
                    if is_us_candidate
                    else PUBLIC_SIGNAL_SCOPE_NOTE
                ),
                "required_supports": 0,
                "supportive_count": int(public_flow["state"] == "positive"),
                "caution_count": int(public_flow["state"] == "negative"),
                "vetoes": [],
                "source_checks": [],
                "evidence": [
                    {
                        "key": "flow",
                        "label": public_flow["label"],
                        "state": public_flow["state"],
                        "summary": public_flow["summary"],
                        "source": (
                            "가격·거래대금 참여도 공개 요약"
                            if is_us_candidate
                            else "수급 공개 요약"
                        ),
                        "as_of": public_flow["as_of"],
                        "score": None,
                        "available": public_flow["available"],
                        "used_for_entry": False,
                    }
                ],
            }
        )
        result["confirmation"] = confirmation

    if "current" in result:
        result["current"] = _redact_current_signal(result.get("current"), public_reasons)
        if is_us_candidate and isinstance(result["current"], dict):
            action = str(result["current"].get("action") or "")
            result["current"]["next_confirmation"] = (
                US_PUBLIC_MODEL_LIFECYCLE_NEXT_CHECK
                if action in {"entered", "holding", "full_exit_pending", "exited"}
                else US_PUBLIC_SIGNAL_NEXT_CHECK
            )

    if "latest_preliminary" in result:
        result["latest_preliminary"] = _redact_preliminary_signal(
            result.get("latest_preliminary")
        )

    if isinstance(result.get("events"), list):
        events = []
        for event in _items(result["events"]):
            public_event = deepcopy(dict(event))
            public_event["reason"] = PUBLIC_SIGNAL_DECISION_REASON
            public_event["entry_setup"] = None
            public_event["entry_confirmation"] = None
            events.append(public_event)
        result["events"] = events

    if isinstance(result.get("signal_reconciliations"), list):
        reconciliations = []
        for item in _items(result["signal_reconciliations"]):
            public_item = deepcopy(dict(item))
            public_item["reason"] = PUBLIC_SIGNAL_DECISION_REASON
            reconciliations.append(public_item)
        result["signal_reconciliations"] = reconciliations

    if isinstance(result.get("trades"), list):
        trades = []
        for trade in _items(result["trades"]):
            public_trade = deepcopy(dict(trade))
            if public_trade.get("exit_reason"):
                public_trade["exit_reason"] = PUBLIC_SIGNAL_DECISION_REASON
            trades.append(public_trade)
        result["trades"] = trades
    public_result = _hide_numeric_signal_scores(result)
    if is_us_candidate:
        public_result = _remove_forbidden_us_public_fields(public_result)
    return dict(_mapping(public_result))


def public_market_signal_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Redact current and historical reasons in a market/watchlist signal feed."""

    result = deepcopy(dict(_mapping(payload)))
    is_us_candidate = str(result.get("strategy_version") or "").startswith(
        "position-lifecycle-us-"
    )
    us_snapshot_ready = bool(
        is_us_candidate and _us_public_snapshot_ready(result)
    )
    if is_us_candidate:
        # RC diagnostics remain available in the backend snapshot and QA
        # artifact, but the user-facing market feed exposes only the three
        # concise evidence summaries and the preliminary conclusion.
        result.pop("shadow_comparison", None)
        result.pop("source_errors", None)
        result.pop("source_error", None)
        result.pop("sector_classification_errors", None)
        result.pop("universe_members", None)
        result.pop("public_member_signals", None)
        result["methodology"] = [US_PUBLIC_SIGNAL_METHODOLOGY]
        if not us_snapshot_ready:
            # A previous-session lifecycle is diagnostic history, not a
            # current signal. Do not let legacy side/is_current_holding fields
            # reconstruct confirmed rows in the browser while the canonical
            # snapshot is stale or degraded.
            result["items"] = []
            result["preliminary_history"] = []
            result["confirmed_count"] = 0
            result["preliminary_count"] = 0
            result["total_preliminary_count"] = 0
            result["entry_pending_count"] = 0
    public_items = []
    for item in _items(result.get("items")):
        public_item = deepcopy(dict(item))
        us_item_ready = bool(
            us_snapshot_ready
            and _us_public_reasons_ready(public_item.get("public_reasons"))
        )
        if is_us_candidate:
            if not us_item_ready:
                public_item = _fail_closed_us_public_signal(public_item)
            public_item.pop("us_evidence", None)
            public_item.pop("guard_state", None)
            public_item.pop("entry_setup", None)
            public_item.pop("chase_veto", None)
            if "entry_score_threshold" in public_item:
                public_item["entry_score_threshold"] = None
        public_reasons = (
            _unavailable_us_public_reasons(
                result.get("universe_as_of") or result.get("as_of")
            )
            if is_us_candidate and not us_item_ready
            else build_public_signal_reasons(public_item, context=public_item)
        )
        public_item["public_reasons"] = public_reasons
        if "reason" in public_item:
            action = str(_mapping(public_item.get("current")).get("action") or "")
            public_item["reason"] = (
                US_PUBLIC_MODEL_LIFECYCLE_REASON
                if is_us_candidate
                and us_item_ready
                and action in {"entered", "holding", "full_exit_pending", "exited"}
                else US_PUBLIC_SIGNAL_DECISION_REASON
                if is_us_candidate
                else PUBLIC_SIGNAL_DECISION_REASON
            )
        if "entry_confirmation" in public_item:
            public_item["entry_confirmation"] = None
        if "current" in public_item:
            public_item["current"] = _redact_current_signal(
                public_item.get("current"),
                public_reasons,
            )
            if is_us_candidate and isinstance(public_item["current"], dict):
                action = str(public_item["current"].get("action") or "")
                public_item["current"]["next_confirmation"] = (
                    US_PUBLIC_MODEL_LIFECYCLE_NEXT_CHECK
                    if us_item_ready
                    and action in {"entered", "holding", "full_exit_pending", "exited"}
                    else US_PUBLIC_SIGNAL_NEXT_CHECK
                    if us_item_ready
                    else US_PUBLIC_SIGNAL_PREPARING_NEXT_CHECK
                )
        if "latest_preliminary" in public_item:
            public_item["latest_preliminary"] = _redact_preliminary_signal(
                public_item.get("latest_preliminary")
            )
        public_items.append(public_item)
    if isinstance(result.get("items"), list):
        result["items"] = public_items

    if isinstance(result.get("preliminary_history"), list):
        result["preliminary_history"] = [
            _redact_preliminary_signal(item)
            for item in _items(result.get("preliminary_history"))
        ]
    public_result = _hide_numeric_signal_scores(result)
    if is_us_candidate:
        public_result = _remove_forbidden_us_public_fields(public_result)
    return dict(_mapping(public_result))


def public_recommendation_signal_payload(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Keep recommendation facts while redacting every nested AI signal."""

    result = deepcopy(dict(_mapping(payload)))
    is_us_candidate = str(result.get("strategy_version") or "").startswith(
        "position-lifecycle-us-"
    )
    us_snapshot_ready = bool(
        is_us_candidate and _us_public_snapshot_ready(result)
    )
    if is_us_candidate:
        result.pop("source_errors", None)
        result.pop("source_error", None)
        result.pop("sector_classification_errors", None)
        result.pop("universe_members", None)
        result.pop("public_member_signals", None)
        result["methodology"] = [US_PUBLIC_SIGNAL_METHODOLOGY]
        if not us_snapshot_ready:
            result["items"] = []
            result["candidate_count"] = 0
            result["total_candidate_count"] = 0
            result["selection_state"] = "unavailable"
    public_items = []
    for item in _items(result.get("items")):
        public_item = deepcopy(dict(item))
        independent_us_recommendation = bool(
            is_us_candidate
            and str(public_item.get("recommendation_model_version") or "").startswith(
                "us-independent-recommendation-"
            )
        )
        if is_us_candidate:
            if not us_snapshot_ready:
                public_item["action"] = "관망"
            public_item.pop("entry_setup", None)
            public_item.pop("chase_veto", None)
        signal = public_item.get("ai_trade_signal")
        if isinstance(signal, Mapping):
            us_signal_ready = bool(
                us_snapshot_ready
                and _us_public_reasons_ready(signal.get("public_reasons"))
            )
            if is_us_candidate and not us_signal_ready:
                if not independent_us_recommendation:
                    public_item["action"] = "관망"
                signal = _fail_closed_us_public_signal(signal)
                signal["public_reasons"] = _unavailable_us_public_reasons(
                    result.get("universe_as_of") or result.get("as_of")
                )
            public_item["ai_trade_signal"] = public_quant_signal_payload(
                signal,
                context=public_item,
            )
            if (
                is_us_candidate
                and not us_signal_ready
                and isinstance(public_item["ai_trade_signal"].get("current"), dict)
            ):
                public_item["ai_trade_signal"]["current"][
                    "next_confirmation"
                ] = US_PUBLIC_SIGNAL_PREPARING_NEXT_CHECK
            public_reasons = public_item["ai_trade_signal"]["public_reasons"]
            if independent_us_recommendation:
                public_item["reasons"] = list(
                    public_item.get("recommendation_reasons") or []
                )
                public_item["risks"] = [
                    "추천 순위는 매수 시점이 아니며 현재 시그널 상태를 따로 확인해야 합니다."
                ]
            else:
                public_item["reasons"] = [item["summary"] for item in public_reasons]
                public_item["risks"] = []
            if "decision_reason" in public_item:
                if not independent_us_recommendation:
                    public_item["decision_reason"] = (
                        US_PUBLIC_SIGNAL_DECISION_REASON
                        if is_us_candidate
                        else PUBLIC_SIGNAL_DECISION_REASON
                    )
            if "score_decision_reason" in public_item:
                if not independent_us_recommendation:
                    public_item["score_decision_reason"] = (
                        US_PUBLIC_SIGNAL_DECISION_REASON
                        if is_us_candidate
                        else PUBLIC_SIGNAL_DECISION_REASON
                    )
            if "component_scores" in public_item:
                public_item["component_scores"] = {}
        elif is_us_candidate:
            public_item["action"] = "관망"
        if is_us_candidate and "score" in public_item:
            public_item["score"] = None
        if is_us_candidate and "entry_score_threshold" in public_item:
            public_item["entry_score_threshold"] = None
        public_items.append(public_item)
    if isinstance(result.get("items"), list):
        result["items"] = public_items
    if is_us_candidate:
        return dict(_mapping(_remove_forbidden_us_public_fields(result)))
    return result


def public_stock_ai_analysis_payload(
    payload: Mapping[str, Any] | None,
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reduce a generated stock analysis to the three approved public reasons."""

    result = deepcopy(dict(_mapping(payload)))
    source = _mapping(payload)
    fallback = _mapping(context)
    is_us_proxy = str(
        source.get("flow_semantics") or fallback.get("flow_semantics") or ""
    ) == US_DOLLAR_VOLUME_FLOW_SEMANTICS
    public_evidence_status = str(source.get("public_evidence_status") or "")
    public_reasons = (
        []
        if is_us_proxy and public_evidence_status == "not_applicable"
        else build_public_signal_reasons(result, context=context)
    )
    current_action = str(_mapping(result.get("current")).get("action") or "")
    us_public_evidence_ready = bool(
        is_us_proxy
        and _us_public_snapshot_identity_ready(result)
        and result.get("data_state") == "ready"
        and result.get("is_current_universe_member") is True
        and all(item.get("available") is True for item in public_reasons)
    )
    if is_us_proxy:
        status_ready = _us_public_snapshot_identity_ready(result)
        if us_public_evidence_ready:
            if current_action in {"entry_pending", "entry_watch"}:
                decision_reason = US_PUBLIC_SIGNAL_DECISION_REASON
                next_check = US_PUBLIC_SIGNAL_NEXT_CHECK
            elif current_action in {"entered", "holding", "full_exit_pending", "exited"}:
                decision_reason = US_PUBLIC_MODEL_LIFECYCLE_REASON
                next_check = US_PUBLIC_MODEL_LIFECYCLE_NEXT_CHECK
            else:
                decision_reason = US_PUBLIC_SIGNAL_UNAVAILABLE_REASON
                next_check = US_PUBLIC_SIGNAL_UNAVAILABLE_NEXT_CHECK
        elif not status_ready:
            decision_reason = US_PUBLIC_SIGNAL_PREPARING_REASON
            next_check = US_PUBLIC_SIGNAL_PREPARING_NEXT_CHECK
        elif result.get("is_current_universe_member") is False:
            decision_reason = US_PUBLIC_SIGNAL_OUTSIDE_REASON
            next_check = US_PUBLIC_SIGNAL_UNAVAILABLE_NEXT_CHECK
        else:
            decision_reason = US_PUBLIC_SIGNAL_UNAVAILABLE_REASON
            next_check = US_PUBLIC_SIGNAL_UNAVAILABLE_NEXT_CHECK
        if public_evidence_status == "not_applicable":
            public_reasons = []
            result = _fail_closed_us_public_signal(result, reason=next_check)
        elif not us_public_evidence_ready:
            public_reasons = _unavailable_us_public_reasons(
                result.get("as_of") or fallback.get("as_of")
            )
            result = _fail_closed_us_public_signal(result, reason=next_check)
    else:
        decision_reason = PUBLIC_SIGNAL_DECISION_REASON
        next_check = PUBLIC_SIGNAL_NEXT_CHECK
    summaries = [item["summary"] for item in public_reasons]
    result["public_reasons"] = public_reasons
    result["summary"] = decision_reason
    result["key_points"] = summaries
    result["strategy"] = [next_check]
    result["risks"] = []
    result["sections"] = [
        {
            "title": "공개 판단 근거",
            "items": summaries,
        }
    ]
    result["trade_levels"] = None
    if is_us_proxy:
        result["generation_note"] = US_DOLLAR_VOLUME_NOTICE
    elif "generation_note" in result:
        result["generation_note"] = PUBLIC_SIGNAL_SCOPE_NOTE
    public_result = _hide_numeric_signal_scores(result)
    if is_us_proxy:
        public_result = _remove_forbidden_us_public_fields(public_result)
    return dict(_mapping(public_result))
