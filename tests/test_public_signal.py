from __future__ import annotations

from copy import deepcopy
import json

from app.services.public_signal import (
    PUBLIC_SIGNAL_DECISION_REASON,
    PUBLIC_SIGNAL_REASON_KEYS,
    public_market_signal_payload,
    public_quant_signal_payload,
    public_recommendation_signal_payload,
    public_stock_ai_analysis_payload,
)


def _private_quant_payload() -> dict[str, object]:
    return {
        "code": "005930",
        "name": "삼성전자",
        "strategy_name": "private-strategy",
        "strategy_version": "private-v99",
        "candidate_strategy_version": "private-candidate",
        "strategy_version_history": [{"version": "private-old"}],
        "entry_filter_version": "private-filter",
        "entry_score_threshold": 64,
        "source": "private-source",
        "price_through": "2026-09-08",
        "data_state": "ready",
        "data_message": "private-data-message",
        "factors": [
            {"key": "momentum", "label": "모멘텀", "score": 91, "state": "positive", "detail": "private-momentum"},
            {"key": "trend", "label": "추세", "score": 82, "state": "caution", "detail": "private-trend"},
            {"key": "volatility", "label": "변동성", "score": 44, "state": "neutral", "detail": "private-volatility"},
        ],
        "confirmation": {
            "state": "caution",
            "label": "private-confirmation",
            "score": 77,
            "available_count": 5,
            "total_count": 7,
            "note": "private-note",
            "entry_allowed": False,
            "required_supports": 3,
            "supportive_count": 2,
            "caution_count": 1,
            "vetoes": ["private-veto"],
            "source_checks": [{"source": "private-check"}],
            "evidence": [
                {
                    "key": "flow",
                    "label": "수급",
                    "state": "supportive",
                    "summary": "private-flow-detail",
                    "source": "private-flow-source",
                    "as_of": "2026-09-08",
                    "score": 80,
                    "available": True,
                },
                {
                    "key": "research",
                    "label": "리서치",
                    "state": "positive",
                    "summary": "private-research",
                    "source": "private-research-source",
                    "available": True,
                },
            ],
        },
        "current": {
            "action": "entry_watch",
            "label": "진입 관찰",
            "entry_setup": "private-entry-setup",
            "entry_confirmation": {"private": "confirmation"},
            "reasons": ["private-current-reason"],
            "next_confirmation": "private-next-condition",
            "levels": [{"key": "entry", "label": "진입", "price": 77_000, "condition": "private-level-condition"}],
        },
        "events": [{"reason": "private-event-reason", "entry_setup": "private-event-setup"}],
        "signal_reconciliations": [{"reason": "private-reconciliation"}],
        "trades": [{"exit_reason": "private-exit-reason"}],
        "methodology": ["private-methodology"],
        "applied_principles": ["private-principle"],
        "excluded_principles": ["private-excluded"],
    }


def test_quant_projection_exposes_only_three_public_reasons_and_keeps_input_immutable() -> None:
    private_payload = _private_quant_payload()
    original = deepcopy(private_payload)

    public = public_quant_signal_payload(private_payload)

    assert private_payload == original
    assert [item["key"] for item in public["public_reasons"]] == list(PUBLIC_SIGNAL_REASON_KEYS)
    assert [item["label"] for item in public["public_reasons"]] == ["20일", "60일", "수급"]
    assert [item["state"] for item in public["public_reasons"]] == [
        "positive",
        "negative",
        "positive",
    ]
    assert [item["key"] for item in public["factors"]] == ["trend_20d", "trend_60d"]
    assert [item["key"] for item in public["confirmation"]["evidence"]] == ["flow"]
    assert public["entry_score_threshold"] is None
    assert public["strategy_version_history"] == []
    assert public["current"]["entry_setup"] is None
    assert public["current"]["entry_confirmation"] is None
    assert public["current"]["reasons"] == [
        item["summary"] for item in public["public_reasons"]
    ]
    assert public["events"][0]["reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert public["trades"][0]["exit_reason"] == PUBLIC_SIGNAL_DECISION_REASON

    serialized = json.dumps(public, ensure_ascii=False)
    for private_token in (
        "private-momentum",
        "private-trend",
        "private-volatility",
        "private-flow-detail",
        "private-research",
        "private-entry-setup",
        "private-next-condition",
        "private-methodology",
        "private-veto",
        "private-filter",
    ):
        assert private_token not in serialized


def test_market_projection_redacts_live_and_preliminary_history_reasons() -> None:
    public = public_market_signal_payload(
        {
            "items": [
                {
                    "code": "005930",
                    "reason": "private-market-reason",
                    "public_reasons": [
                        {"key": "trend_20d", "state": "positive"},
                        {"key": "trend_60d", "state": "neutral"},
                        {"key": "flow", "state": "negative"},
                    ],
                    "current": {
                        "reasons": ["private-current"],
                        "next_confirmation": "private-next",
                    },
                    "latest_preliminary": {"reason": "private-latest"},
                }
            ],
            "preliminary_history": [{"reason": "private-history"}],
        }
    )

    item = public["items"][0]
    assert [reason["key"] for reason in item["public_reasons"]] == list(PUBLIC_SIGNAL_REASON_KEYS)
    assert item["reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert item["current"]["reasons"] == [
        reason["summary"] for reason in item["public_reasons"]
    ]
    assert item["latest_preliminary"]["reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert public["preliminary_history"][0]["reason"] == PUBLIC_SIGNAL_DECISION_REASON


def test_recommendation_projection_removes_component_and_nested_reason_details() -> None:
    public = public_recommendation_signal_payload(
        {
            "items": [
                {
                    "code": "005930",
                    "one_month_return": 5,
                    "three_month_return": -2,
                    "component_scores": {"chart": 75, "research": 90},
                    "decision_reason": "private-decision",
                    "score_decision_reason": "private-score-decision",
                    "reasons": ["private-reason"],
                    "risks": ["private-risk"],
                    "ai_trade_signal": _private_quant_payload(),
                }
            ]
        }
    )

    item = public["items"][0]
    assert item["component_scores"] == {}
    assert item["risks"] == []
    assert item["decision_reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert item["score_decision_reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert item["reasons"] == [
        reason["summary"] for reason in item["ai_trade_signal"]["public_reasons"]
    ]


def test_generated_ai_analysis_projection_replaces_sections_and_trade_levels() -> None:
    public = public_stock_ai_analysis_payload(
        {
            "summary": "private-summary",
            "key_points": ["private-key-point"],
            "strategy": ["private-strategy"],
            "risks": ["private-risk"],
            "sections": [{"title": "private-section", "items": ["private-item"]}],
            "trade_levels": {"buy_low": 70_000},
            "generation_note": "private-generation-note",
        },
        context={
            "as_of": "2026-09-08",
            "momentum": {
                "one_month_return": 2,
                "three_month_return": 0,
                "trading_value_change": -1,
            },
        },
    )

    assert [item["key"] for item in public["public_reasons"]] == list(PUBLIC_SIGNAL_REASON_KEYS)
    assert public["key_points"] == [item["summary"] for item in public["public_reasons"]]
    assert public["sections"] == [
        {"title": "공개 판단 근거", "items": public["key_points"]}
    ]
    assert public["trade_levels"] is None
    assert public["risks"] == []
    assert "private" not in json.dumps(public, ensure_ascii=False)
