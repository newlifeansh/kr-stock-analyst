from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest


LOGIC_PATH = Path("app/static/staging/ai-stock-response-logic.js").resolve()
PUBLIC_REASON_KEYS = ["trend_20d", "trend_60d", "flow"]


def _build(payload: dict[str, object]) -> dict[str, object]:
    script = f"""
const fs = require("fs");
const logic = require({json.dumps(str(LOGIC_PATH))});
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(logic.buildResponse(payload)));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(payload, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _build_guide(
    payload: dict[str, object],
    *,
    investor_state: str,
    average_buy_price: float | None = None,
) -> dict[str, object]:
    script = f"""
const fs = require("fs");
const logic = require({json.dumps(str(LOGIC_PATH))});
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const result = logic.buildResponse(input.payload);
process.stdout.write(JSON.stringify(logic.buildInvestorGuide(result, {{
  investorState: input.investorState,
  averageBuyPrice: input.averageBuyPrice,
}})));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(
            {
                "payload": payload,
                "investorState": investor_state,
                "averageBuyPrice": average_buy_price,
            },
            ensure_ascii=False,
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _complete_payload() -> dict[str, object]:
    """Older six-source fixture retained to prove private inputs stay unrendered."""

    return {
        "code": "005930",
        "dashboard": {
            "code": "005930",
            "name": "삼성전자",
            "market": "KOSPI",
            "as_of": "2026-08-29T12:00:00+09:00",
            "quote": {
                "price": 275_000,
                "change_rate": 1.82,
                "trade_date": "2026-08-28",
                "as_of": "2026-08-29T12:00:00+09:00",
                "market_session": "regular",
                "market_session_label": "장중",
                "is_live": True,
            },
            "momentum": {
                "one_month_return": 12.0,
                "three_month_return": -4.0,
                "trading_value_change": 8.0,
            },
            "chart_analysis": {
                "score": 80,
                "trend": "상승 추세",
                "setup": "돌파 대기",
                "signals": ["현재가가 20일선 위"],
                "risks": [],
                "support": 250_000,
                "resistance": 285_000,
                "atr_percent": 3.2,
            },
            "revisions": {
                "report_count_90d": 3,
                "target_up_count": 2,
                "latest_opinion": "매수",
            },
            "flows": {},
            "sentiment": {
                "score": 40,
                "latest_items": [{"title": "비공개 뉴스 근거"}],
            },
        },
        "quant": {
            "code": "005930",
            "name": "삼성전자",
            "as_of": "2026-08-29T12:00:00+09:00",
            "confirmation": {
                "entry_allowed": False,
                "vetoes": ["비공개 공시 차단 규칙"],
                "evidence": [
                    {
                        "key": "flow",
                        "available": True,
                        "score": -50,
                        "state": "caution",
                        "summary": "외국인 -1,200억원 · 기관 +100억원",
                        "source": "비공개 수급 원천",
                    },
                    {
                        "key": "research",
                        "available": True,
                        "score": 50,
                        "state": "supportive",
                        "summary": "비공개 리포트 상세",
                    },
                ],
            },
            "current": {
                "action": "entry_watch",
                "label": "진입 관찰",
                "price": 275_000,
                "stop_reference": 259_000,
                "partial_exit_reference": 292_000,
                "next_confirmation": "비공개 다음 조건",
            },
        },
        "homeContext": {
            "disclosures": [{"report_name": "비공개 공시 상세"}],
            "news_items": [{"title": "비공개 뉴스 상세"}],
        },
        "marketImpact": {
            "factors": [{"label": "비공개 시장 가중치", "confidence": 80}],
        },
    }


def test_public_response_exposes_only_20d_60d_and_flow() -> None:
    result = _build(_complete_payload())

    assert result["version"] == "20260908-public-reasons-v7"
    assert [item["key"] for item in result["publicReasons"]] == PUBLIC_REASON_KEYS
    assert [item["label"] for item in result["publicReasons"]] == ["20일", "60일", "수급"]
    assert [item["state"] for item in result["publicReasons"]] == [
        "positive",
        "negative",
        "negative",
    ]
    assert result["coverageLabel"] == "3/3개"
    assert result["conflict"] is True
    assert result["stance"] == "진입 관찰"
    for private_key in ("metrics", "score", "confidence", "lead", "coverageWeight"):
        assert private_key not in result

    serialized = json.dumps(result, ensure_ascii=False)
    for private_copy in (
        "비공개 뉴스",
        "비공개 공시",
        "비공개 리포트",
        "비공개 시장",
        "-1,200억원",
        "비공개 다음 조건",
    ):
        assert private_copy not in serialized


def test_supplied_public_reasons_keep_order_but_not_raw_detail_copy() -> None:
    payload = _complete_payload()
    payload["quant"]["public_reasons"] = [
        {"key": "flow", "state": "positive", "summary": "원천 상세 수급"},
        {"key": "trend_60d", "state": "neutral", "summary": "원천 상세 60일"},
        {"key": "trend_20d", "state": "negative", "summary": "원천 상세 20일"},
    ]

    result = _build(payload)

    assert [item["key"] for item in result["publicReasons"]] == PUBLIC_REASON_KEYS
    assert [item["state"] for item in result["publicReasons"]] == [
        "negative",
        "neutral",
        "positive",
    ]
    assert "원천 상세" not in json.dumps(result, ensure_ascii=False)


def test_missing_public_inputs_stay_unavailable() -> None:
    result = _build({"code": "005930", "dashboard": {"code": "005930"}})

    assert result["limited"] is True
    assert result["coverageCount"] == 0
    assert [item["state"] for item in result["publicReasons"]] == [
        "unavailable",
        "unavailable",
        "unavailable",
    ]
    assert all("자료가 부족" in item["summary"] for item in result["publicReasons"])


def test_client_bundle_contains_no_private_scoring_contract() -> None:
    source = LOGIC_PATH.read_text(encoding="utf-8")

    for private_contract in (
        "const WEIGHTS",
        "chart: 25",
        "disclosure: 15",
        "entry_score_threshold",
        "HARD_DISCLOSURE_RISK_TOKENS",
        "weightedScore",
        "coverageWeight",
    ):
        assert private_contract not in source


def test_not_holding_guide_uses_only_three_public_reasons() -> None:
    guide = _build_guide(_complete_payload(), investor_state="not_holding")
    rows = {row["key"]: row for row in guide["rows"]}

    assert guide["positionMode"] == "watching"
    assert guide["headline"] == "현재는 20일·60일·수급을 확인하며 기다릴 때예요"
    assert "20일" in guide["reason"]
    assert "60일" in guide["reason"]
    assert "수급" in guide["reason"]
    assert "뉴스" not in guide["reason"]
    assert "리포트" not in guide["reason"]
    assert rows["buy_trigger"]["value"] == "285,000원"
    assert rows["risk_line"]["value"] == "259,000원"
    assert [step["key"] for step in guide["decisionPlan"]] == [
        "pullback",
        "breakout",
        "wait",
    ]


def test_holding_guides_keep_personal_price_behavior_without_private_reasons() -> None:
    profit = _build_guide(
        _complete_payload(),
        investor_state="holding",
        average_buy_price=240_000,
    )
    loss = _build_guide(
        _complete_payload(),
        investor_state="holding",
        average_buy_price=310_000,
    )

    assert profit["positionMode"] == "holding_profit"
    assert profit["returnRate"] == pytest.approx(14.583333, rel=1e-5)
    assert profit["holdingStrategy"]["stage"] == "수익 관리"
    assert [step["key"] for step in profit["decisionPlan"]] == [
        "take_profit",
        "protect_profit",
        "keep_holding",
    ]
    assert loss["positionMode"] == "holding_loss"
    assert loss["returnRate"] == pytest.approx(-11.290322, rel=1e-5)
    assert loss["holdingStrategy"]["stage"] == "손실 관리"
    assert [step["key"] for step in loss["decisionPlan"]] == [
        "limit_loss",
        "recovery",
        "hold_loss",
    ]
    assert "뉴스" not in json.dumps({"profit": profit, "loss": loss}, ensure_ascii=False)


def test_holding_without_average_price_does_not_manufacture_personal_return() -> None:
    guide = _build_guide(_complete_payload(), investor_state="holding")

    assert guide["positionMode"] == "holding_unknown"
    assert guide["returnRate"] is None
    assert guide["holdingStrategy"] is None
    assert guide["rows"] == []
    assert guide["decisionPlan"] == []


def test_us_price_guide_uses_usd_without_exposing_extra_reasons() -> None:
    payload = {
        "code": "NVDA",
        "dashboard": {
            "code": "NVDA",
            "name": "NVIDIA",
            "market": "NASDAQ",
            "currency": "USD",
            "quote": {"price": 185.25},
            "momentum": {"one_month_return": 3, "three_month_return": 7},
            "flows": {"foreign_intensity": -0.2},
            "chart_analysis": {"support": 178.5, "resistance": 192.5},
        },
    }

    result = _build(payload)
    guide = _build_guide(payload, investor_state="not_holding")

    assert [item["key"] for item in result["publicReasons"]] == PUBLIC_REASON_KEYS
    assert guide["rows"][1]["value"].startswith("$")
