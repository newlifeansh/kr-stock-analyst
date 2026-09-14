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
            "score": 80.04,
            "entry_setup": "private-entry-setup",
            "entry_confirmation": {"private": "confirmation"},
            "reasons": ["private-current-reason"],
            "next_confirmation": "private-next-condition",
            "levels": [{"key": "entry", "label": "진입", "price": 77_000, "condition": "private-level-condition"}],
        },
        "events": [
            {
                "reason": "private-event-reason",
                "entry_setup": "private-event-setup",
                "score": "100",
            }
        ],
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
    assert public["current"]["score"] is None
    assert public["current"]["reasons"] == [
        item["summary"] for item in public["public_reasons"]
    ]
    assert public["events"][0]["reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert public["events"][0]["score"] is None
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
                    "score": 99,
                    "reason": "private-market-reason",
                    "public_reasons": [
                        {"key": "trend_20d", "state": "positive"},
                        {"key": "trend_60d", "state": "neutral"},
                        {"key": "flow", "state": "negative"},
                    ],
                    "current": {
                        "score": 88,
                        "reasons": ["private-current"],
                        "next_confirmation": "private-next",
                    },
                    "latest_preliminary": {
                        "reason": "private-latest",
                        "score": 77,
                    },
                }
            ],
            "preliminary_history": [
                {"reason": "private-history", "score": 66}
            ],
        }
    )

    item = public["items"][0]
    assert [reason["key"] for reason in item["public_reasons"]] == list(PUBLIC_SIGNAL_REASON_KEYS)
    assert item["reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert item["score"] is None
    assert item["current"]["score"] is None
    assert item["current"]["reasons"] == [
        reason["summary"] for reason in item["public_reasons"]
    ]
    assert item["latest_preliminary"]["reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert item["latest_preliminary"]["score"] is None
    assert public["preliminary_history"][0]["reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert public["preliminary_history"][0]["score"] is None


def test_recommendation_projection_removes_component_and_nested_reason_details() -> None:
    public = public_recommendation_signal_payload(
        {
            "items": [
                {
                    "code": "005930",
                    "score": 93,
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
    assert item["score"] == 93
    assert item["ai_trade_signal"]["current"]["score"] is None
    assert item["component_scores"] == {}
    assert item["risks"] == []
    assert item["decision_reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert item["score_decision_reason"] == PUBLIC_SIGNAL_DECISION_REASON
    assert item["reasons"] == [
        reason["summary"] for reason in item["ai_trade_signal"]["public_reasons"]
    ]


def test_us_candidate_projection_hides_shadow_diagnostics_and_numeric_evidence() -> None:
    public = public_market_signal_payload(
        {
            "strategy_version": "position-lifecycle-us-v1-rc1",
            "status": "ready",
            "data_state": "ready",
            "snapshot_id": "us-snapshot-1",
            "snapshot_checksum": "checksum-1",
            "new_entries_allowed": True,
            "flow_semantics": "dollar_volume_participation_proxy",
            "shadow_comparison": {"rejection_counts": {"chase_guard": 4}},
            "source_errors": {"BAD": "private provider error"},
            "sector_classification_errors": {"BAD": "private CIK"},
            "universe_members": [{"code": "PRIVATE", "cik": "private-cik"}],
            "methodology": [
                "1.5ATR·7% 이격과 최근 5일 10% 초과 급등은 차단",
                "private reentry threshold",
            ],
            "items": [
                {
                    "code": "NVDA",
                    "status": "preliminary",
                    "entry_score_threshold": 65,
                    "entry_setup": "private-entry-setup",
                    "chase_veto": "private-veto",
                    "flow_semantics": "dollar_volume_participation_proxy",
                    "us_evidence": {"relative_strength_20d": 0.1234},
                    "guard_state": "blocked",
                    "public_reasons": [
                        {"key": "trend_20d", "state": "positive", "available": True},
                        {"key": "trend_60d", "state": "positive", "available": True},
                        {"key": "flow", "state": "positive", "available": True},
                    ],
                    "current": {
                        "action": "entry_watch",
                        "position_open": False,
                        "entry_price": 101,
                        "target_sell_price": 120,
                        "stop_reference": 95,
                        "levels": [{"key": "entry", "price": 101}],
                        "reasons": ["private US threshold"],
                    },
                }
            ],
        }
    )

    assert "shadow_comparison" not in public
    assert "source_errors" not in public
    assert "sector_classification_errors" not in public
    assert "universe_members" not in public
    assert "us_evidence" not in public["items"][0]
    assert "guard_state" not in public["items"][0]
    assert "entry_score_threshold" not in public["items"][0]
    assert "entry_setup" not in public["items"][0]
    assert "chase_veto" not in public["items"][0]
    assert "entry_price" not in json.dumps(public, ensure_ascii=False)
    assert "target_sell_price" not in json.dumps(public, ensure_ascii=False)
    assert "stop_reference" not in json.dumps(public, ensure_ascii=False)
    assert '"levels"' not in json.dumps(public, ensure_ascii=False)
    assert "private" not in json.dumps(public, ensure_ascii=False)
    assert "1.5ATR" not in json.dumps(public, ensure_ascii=False)
    assert '"entry_score_threshold": 65' not in json.dumps(public, ensure_ascii=False)
    assert public["methodology"]
    assert all(
        token in public["methodology"][0]
        for token in ("상위 100종목", "수정 OHLC", "SPY·QQQ", "거래대금")
    )
    flow = public["items"][0]["public_reasons"][2]
    assert flow["label"] == "거래대금 참여도"
    assert "가격×거래량" in flow["summary"]
    assert "투자자 순매수나 ETF 순유입이 아닙니다" in flow["note"]


def test_us_recommendation_projection_hides_nested_internal_evidence() -> None:
    public = public_recommendation_signal_payload(
        {
            "strategy_version": "position-lifecycle-us-v1-rc1",
            "status": "ready",
            "data_state": "ready",
            "snapshot_id": "us-snapshot-1",
            "snapshot_checksum": "checksum-1",
            "new_entries_allowed": True,
            "methodology": ["1.5ATR private methodology"],
            "sector_classification_errors": {"BAD": "private CIK"},
            "universe_members": [{"code": "PRIVATE", "cik": "private-cik"}],
            "items": [
                {
                    "code": "NVDA",
                    "score": 72,
                    "decision_reason": "private US decision",
                    "score_decision_reason": "private US score decision",
                    "entry_score_threshold": 65,
                    "entry_setup": "private-entry-setup",
                    "chase_veto": "private-veto",
                    "reasons": ["private recommendation reason"],
                    "risks": ["private recommendation risk"],
                    "component_scores": {"flow": 88},
                    "ai_trade_signal": {
                        "strategy_version": "position-lifecycle-us-v1-rc1",
                        "flow_semantics": "dollar_volume_participation_proxy",
                        "status": "preliminary",
                        "entry_score_threshold": 65,
                        "entry_setup": "private-entry-setup",
                        "chase_veto": "private-veto",
                        "us_evidence": {"stock_sector_relative_strength_20d": 0.04},
                        "guard_state": "clear",
                        "public_reasons": [
                            {"key": "trend_20d", "state": "positive", "available": True},
                            {"key": "trend_60d", "state": "positive", "available": True},
                            {"key": "flow", "state": "positive", "available": True},
                        ],
                        "current": {
                            "action": "entry_watch",
                            "position_open": False,
                            "entry_price": 101,
                            "target_sell_price": 120,
                            "stop_reference": 95,
                            "levels": [{"key": "entry", "price": 101}],
                            "reasons": ["private nested threshold"],
                        },
                    },
                }
            ],
        }
    )

    signal = public["items"][0]["ai_trade_signal"]
    assert "us_evidence" not in signal
    assert "guard_state" not in signal
    assert "sector_classification_errors" not in public
    assert "universe_members" not in public
    assert "score" not in public["items"][0]
    assert "entry_score_threshold" not in public["items"][0]
    assert "score" not in signal
    assert "entry_score_threshold" not in signal
    assert "entry_setup" not in signal
    assert "chase_veto" not in signal
    assert "1.5ATR" not in json.dumps(public, ensure_ascii=False)
    assert '"score": 72' not in json.dumps(public, ensure_ascii=False)
    assert '"entry_score_threshold": 65' not in json.dumps(public, ensure_ascii=False)
    assert all(
        token in public["methodology"][0]
        for token in ("상위 100종목", "수정 OHLC", "SPY·QQQ", "거래대금")
    )
    assert "component_scores" not in public["items"][0]
    assert "entry_price" not in json.dumps(public, ensure_ascii=False)
    assert "target_sell_price" not in json.dumps(public, ensure_ascii=False)
    assert "stop_reference" not in json.dumps(public, ensure_ascii=False)
    assert '"levels"' not in json.dumps(public, ensure_ascii=False)
    assert public["items"][0]["risks"] == []
    assert "거래대금 참여도" in public["items"][0]["decision_reason"]
    assert "수급" not in public["items"][0]["decision_reason"]
    assert "거래대금 참여도" in public["items"][0]["score_decision_reason"]
    assert "private" not in json.dumps(public, ensure_ascii=False)
    flow = signal["public_reasons"][2]
    assert flow["label"] == "거래대금 참여도"
    assert "투자자 순매수나 ETF 순유입이 아닙니다" in flow["note"]


def test_us_non_ready_market_and_recommendation_projections_are_no_signal() -> None:
    signal = {
        "strategy_version": "position-lifecycle-us-v1-rc1",
        "flow_semantics": "dollar_volume_participation_proxy",
        "status": "preliminary",
        "is_preliminary": True,
        "signal": "예비 매수",
        "public_reasons": [
            {"key": "trend_20d", "state": "positive", "available": True},
            {"key": "trend_60d", "state": "positive", "available": True},
            {"key": "flow", "state": "positive", "available": True},
        ],
        "current": {
            "action": "entry_pending",
            "label": "예비 매수",
            "position_open": False,
            "entry_price": 101,
            "target_sell_price": 120,
            "stop_reference": 95,
        },
    }
    feed = {
        "strategy_version": "position-lifecycle-us-v1-rc1",
        "status": "preparing",
        "data_state": "preparing",
        "snapshot_id": None,
        "snapshot_checksum": None,
        "new_entries_allowed": False,
        "items": [signal],
    }

    market = public_market_signal_payload(feed)
    market_signal = market["items"][0]
    assert market_signal["current"]["action"] == "no_signal"
    assert market_signal["current"]["label"] == "관망"
    assert market_signal["signal"] == "관망"
    assert market_signal["is_preliminary"] is False
    assert "동일 스냅샷" in market_signal["current"]["next_confirmation"]
    assert all(reason["available"] is False for reason in market_signal["public_reasons"])

    recommendation = public_recommendation_signal_payload(
        {
            **feed,
            "items": [
                {
                    "code": "NVDA",
                    "action": "관심 매수후보",
                    "ai_trade_signal": signal,
                }
            ],
        }
    )
    recommendation_item = recommendation["items"][0]
    recommendation_signal = recommendation_item["ai_trade_signal"]
    assert recommendation_item["action"] == "관망"
    assert recommendation_signal["current"]["action"] == "no_signal"
    assert recommendation_signal["current"]["label"] == "관망"
    assert recommendation_signal["signal"] == "관망"
    assert recommendation_signal["is_preliminary"] is False
    assert "동일 스냅샷" in recommendation_signal["current"]["next_confirmation"]
    assert all(
        reason["available"] is False
        for reason in recommendation_signal["public_reasons"]
    )
    serialized = json.dumps(recommendation, ensure_ascii=False)
    assert "entry_price" not in serialized
    assert "target_sell_price" not in serialized
    assert "stop_reference" not in serialized


def test_us_ready_snapshot_with_incomplete_public_reasons_fails_closed() -> None:
    signal = {
        "strategy_version": "position-lifecycle-us-v1-rc1",
        "flow_semantics": "dollar_volume_participation_proxy",
        "status": "preliminary",
        "is_preliminary": True,
        "signal": "예비 매수",
        "public_reasons": [
            {"key": "trend_20d", "state": "positive", "available": True},
            {"key": "trend_60d", "state": "positive", "available": True},
        ],
        "current": {
            "action": "entry_pending",
            "label": "예비 매수",
            "position_open": False,
        },
    }
    feed = {
        "strategy_version": "position-lifecycle-us-v1-rc1",
        "status": "ready",
        "data_state": "ready",
        "snapshot_id": "us-snapshot-1",
        "snapshot_checksum": "checksum-1",
        "new_entries_allowed": True,
        "items": [signal],
    }

    market_signal = public_market_signal_payload(feed)["items"][0]
    assert market_signal["current"]["action"] == "no_signal"
    assert market_signal["signal"] == "관망"
    assert all(reason["available"] is False for reason in market_signal["public_reasons"])

    recommendation_item = public_recommendation_signal_payload(
        {
            **feed,
            "items": [{"code": "NVDA", "ai_trade_signal": signal}],
        }
    )["items"][0]
    recommendation_signal = recommendation_item["ai_trade_signal"]
    assert recommendation_item["action"] == "관망"
    assert recommendation_signal["current"]["action"] == "no_signal"
    assert recommendation_signal["signal"] == "관망"
    assert all(
        reason["available"] is False
        for reason in recommendation_signal["public_reasons"]
    )


def test_us_ai_analysis_projection_labels_dollar_volume_proxy_without_investor_flow() -> None:
    public = public_stock_ai_analysis_payload(
        {
            "score": 72,
            "confidence": 99,
            "summary": "private US analysis",
            "key_points": ["private flow detail"],
            "strategy": ["private strategy"],
            "risks": ["private risk"],
            "trade_levels": {
                "buy_low": 101,
                "buy_high": 102,
                "breakout": 105,
                "stop": 95,
                "first_sell": 110,
            },
            "current": {
                "action": "entry_pending",
                "label": "예비 매수",
                "position_open": False,
                "entry_price": 101,
                "target_sell_price": 110,
                "stop_reference": 95,
            },
        },
        context={
            "code": "NVDA",
            "market": "NASDAQ",
            "currency": "USD",
            "flow_semantics": "dollar_volume_participation_proxy",
            "momentum": {
                "one_month_return": 5.0,
                "three_month_return": 12.0,
                "trading_value_change": 8.0,
            },
        },
    )

    flow = public["public_reasons"][2]
    assert flow["label"] == "거래대금 참여도"
    assert "가격×거래량" in flow["summary"]
    assert "투자자 순매수나 ETF 순유입이 아닙니다" in flow["note"]
    assert "수급" not in public["summary"]
    assert "수급" not in public["strategy"][0]
    assert "관망" in public["summary"]
    assert public["current"]["action"] == "no_signal"
    assert "score" not in public
    assert "confidence" not in public
    assert "trade_levels" not in public
    serialized = json.dumps(public, ensure_ascii=False)
    assert "entry_price" not in serialized
    assert "target_sell_price" not in serialized
    assert "stop_reference" not in serialized
    assert "private" not in json.dumps(public, ensure_ascii=False)


def test_generated_ai_analysis_projection_replaces_sections_and_trade_levels() -> None:
    public = public_stock_ai_analysis_payload(
        {
            "score": 72,
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
    assert public["score"] is None
    assert public["risks"] == []
    assert "private" not in json.dumps(public, ensure_ascii=False)
