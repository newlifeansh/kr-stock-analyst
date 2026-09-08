from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Optional


PUBLIC_SIGNAL_REASON_KEYS = ("trend_20d", "trend_60d", "flow")
PUBLIC_SIGNAL_DECISION_REASON = "20일·60일·수급 흐름을 함께 확인한 AI 판단입니다."
PUBLIC_SIGNAL_NEXT_CHECK = "20일·60일 가격 흐름과 수급 변화를 다시 확인하세요."
PUBLIC_SIGNAL_SCOPE_NOTE = "외부에는 20일·60일·수급 세 가지 핵심 근거만 공개합니다."

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

    return [candidates[key] for key in PUBLIC_SIGNAL_REASON_KEYS]


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
        result["methodology"] = [PUBLIC_SIGNAL_SCOPE_NOTE]
    if "source" in result:
        result["source"] = "가격·수급 공개 요약"
    if "data_message" in result:
        result["data_message"] = (
            "최신 가격·수급 자료로 계산했습니다."
            if result.get("data_state") == "ready"
            else "AI 시그널을 계산할 가격·수급 자료가 아직 부족합니다."
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
                "note": PUBLIC_SIGNAL_SCOPE_NOTE,
                "required_supports": 0,
                "supportive_count": int(public_flow["state"] == "positive"),
                "caution_count": int(public_flow["state"] == "negative"),
                "vetoes": [],
                "source_checks": [],
                "evidence": [
                    {
                        "key": "flow",
                        "label": "수급",
                        "state": public_flow["state"],
                        "summary": public_flow["summary"],
                        "source": "수급 공개 요약",
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
    return dict(_mapping(_hide_numeric_signal_scores(result)))


def public_market_signal_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Redact current and historical reasons in a market/watchlist signal feed."""

    result = deepcopy(dict(_mapping(payload)))
    public_items = []
    for item in _items(result.get("items")):
        public_item = deepcopy(dict(item))
        public_reasons = build_public_signal_reasons(public_item, context=public_item)
        public_item["public_reasons"] = public_reasons
        if "reason" in public_item:
            public_item["reason"] = PUBLIC_SIGNAL_DECISION_REASON
        if "entry_confirmation" in public_item:
            public_item["entry_confirmation"] = None
        if "current" in public_item:
            public_item["current"] = _redact_current_signal(
                public_item.get("current"),
                public_reasons,
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
    return dict(_mapping(_hide_numeric_signal_scores(result)))


def public_recommendation_signal_payload(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Keep recommendation facts while redacting every nested AI signal."""

    result = deepcopy(dict(_mapping(payload)))
    public_items = []
    for item in _items(result.get("items")):
        public_item = deepcopy(dict(item))
        signal = public_item.get("ai_trade_signal")
        if isinstance(signal, Mapping):
            public_item["ai_trade_signal"] = public_quant_signal_payload(
                signal,
                context=public_item,
            )
            public_reasons = public_item["ai_trade_signal"]["public_reasons"]
            public_item["reasons"] = [item["summary"] for item in public_reasons]
            public_item["risks"] = []
            if "decision_reason" in public_item:
                public_item["decision_reason"] = PUBLIC_SIGNAL_DECISION_REASON
            if "score_decision_reason" in public_item:
                public_item["score_decision_reason"] = PUBLIC_SIGNAL_DECISION_REASON
            if "component_scores" in public_item:
                public_item["component_scores"] = {}
        public_items.append(public_item)
    if isinstance(result.get("items"), list):
        result["items"] = public_items
    return result


def public_stock_ai_analysis_payload(
    payload: Mapping[str, Any] | None,
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reduce a generated stock analysis to the three approved public reasons."""

    result = deepcopy(dict(_mapping(payload)))
    public_reasons = build_public_signal_reasons(result, context=context)
    summaries = [item["summary"] for item in public_reasons]
    result["public_reasons"] = public_reasons
    result["summary"] = PUBLIC_SIGNAL_DECISION_REASON
    result["key_points"] = summaries
    result["strategy"] = [PUBLIC_SIGNAL_NEXT_CHECK]
    result["risks"] = []
    result["sections"] = [
        {
            "title": "공개 판단 근거",
            "items": summaries,
        }
    ]
    result["trade_levels"] = None
    if "generation_note" in result:
        result["generation_note"] = PUBLIC_SIGNAL_SCOPE_NOTE
    return dict(_mapping(_hide_numeric_signal_scores(result)))
