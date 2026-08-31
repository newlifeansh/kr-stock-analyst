from __future__ import annotations

import json
from pathlib import Path
import subprocess


LOGIC_PATH = Path("app/static/staging/ai-stock-response-logic.js").resolve()


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


def _complete_payload() -> dict[str, object]:
    return {
        "code": "005930",
        "dashboard": {
            "code": "005930",
            "name": "삼성전자",
            "as_of": "2026-08-29T12:00:00+09:00",
            "quote": {"trade_date": "2026-08-28"},
            "coverage": {"price": True},
            "company_profile": {"sector": "반도체", "industry": "반도체 제조"},
            "chart_analysis": {
                "score": 80,
                "trend": "상승 추세",
                "setup": "돌파 대기",
                "signals": ["현재가가 20일선 위"],
                "risks": [],
                "support": 250_000,
            },
            "flows": {},
            "sentiment": {
                "score": 40,
                "positive_count": 6,
                "negative_count": 2,
                "neutral_count": 2,
                "latest_items": [
                    {
                        "title": "반도체 수요 회복",
                        "published_at": "2026-08-29T09:00:00+09:00",
                    }
                ],
            },
        },
        "quant": {
            "code": "005930",
            "name": "삼성전자",
            "sector": "반도체",
            "industry": "반도체 제조",
            "as_of": "2026-08-29T12:00:00+09:00",
            "confirmation": {
                "vetoes": [],
                "evidence": [
                    {
                        "key": "flow",
                        "available": True,
                        "score": -50,
                        "state": "caution",
                        "summary": "외국인 -1,200억원 · 기관 +100억원",
                        "source": "투자자별 매매동향",
                        "as_of": "2026-08-28T15:30:00+09:00",
                    },
                    {
                        "key": "disclosure",
                        "available": True,
                        "score": 0,
                        "state": "neutral",
                        "summary": "최근 90일 중대 위험 공시 없음",
                        "source": "OpenDART 공시",
                        "as_of": "2026-08-29T08:00:00+09:00",
                    },
                ],
            },
        },
        "marketImpact": {
            "as_of": "2026-08-29T11:00:00+09:00",
            "data_quality": "확인",
            "summary": "시장 위험 우위",
            "good_weight": 30,
            "bad_weight": 70,
            "factors": [
                {
                    "key": "risk",
                    "label": "투자심리",
                    "direction": "악재",
                    "percent": 30,
                    "confidence": 80,
                    "affected_sectors": ["반도체"],
                    "leader_stocks": ["SK하이닉스"],
                },
                {
                    "key": "commodity",
                    "label": "원자재",
                    "direction": "호재",
                    "percent": 20,
                    "confidence": 60,
                    "affected_sectors": ["화학"],
                    "leader_stocks": ["LG화학"],
                },
            ],
        },
    }


def test_multi_signal_response_uses_fixed_weights_and_surfaces_conflict() -> None:
    result = _build(_complete_payload())
    metrics = {item["key"]: item for item in result["metrics"]}

    assert result["version"] == "20260829-multi-signal-v1"
    assert [item["key"] for item in result["metrics"]] == [
        "chart",
        "flow",
        "disclosure",
        "news",
        "market",
    ]
    assert {key: item["weight"] for key, item in metrics.items()} == {
        "chart": 30,
        "flow": 25,
        "disclosure": 15,
        "news": 10,
        "market": 20,
    }
    assert metrics["chart"]["value"] == "80점"
    assert metrics["chart"]["score"] == 60
    assert metrics["market"]["score"] == -80
    assert metrics["market"]["relevance"] == "direct"
    assert "종목·업종 관련 축" in metrics["market"]["evidence"]
    assert result["coverageCount"] == 5
    assert result["coverageWeight"] == 100
    assert result["conflict"] is True
    assert result["stance"] == "혼조 · 확인 우선"
    assert result["confidence"] <= 72
    assert "신호 충돌" in result["warnings"][0]


def test_hard_disclosure_veto_overrides_a_positive_composite() -> None:
    payload = _complete_payload()
    payload["quant"]["confirmation"] = {
        "vetoes": ["중대 공시: 주주배정 유상증자 결정"],
        "evidence": [
            {
                "key": "flow",
                "available": True,
                "score": 100,
                "state": "supportive",
                "summary": "외국인·기관 동반 순매수",
            },
            {
                "key": "disclosure_risk",
                "available": True,
                "score": -100,
                "state": "caution",
                "summary": "최근 14일 중대 공시 1건",
            },
            {
                "key": "news",
                "available": True,
                "score": 100,
                "state": "supportive",
                "summary": "긍정 뉴스 우위",
            },
        ],
    }

    result = _build(payload)
    disclosure = next(item for item in result["metrics"] if item["key"] == "disclosure")

    assert result["hardRisk"] is True
    assert result["stance"] == "신규 접근 보류"
    assert "점수보다 중대 공시" in result["action"]
    assert disclosure["hardRisk"] is True
    assert disclosure["value"] == "위험 공시"


def test_recent_raw_hard_disclosure_overrides_generic_quant_disclosure_context() -> None:
    payload = _complete_payload()
    payload["homeContext"] = {
        "code": "005930",
        "name": "삼성전자",
        "as_of": "2026-08-29T12:00:00+09:00",
        "disclosures": [
            {
                "report_name": "주주배정 유상증자 결정",
                "published_at": "2026-08-28T10:00:00+09:00",
            }
        ],
        "news_items": [],
    }

    result = _build(payload)
    disclosure = next(item for item in result["metrics"] if item["key"] == "disclosure")

    assert result["hardRisk"] is True
    assert result["stance"] == "신규 접근 보류"
    assert disclosure["hardRisk"] is True
    assert "유상증자 결정" in disclosure["evidence"]

    payload.pop("dashboard")
    payload.pop("marketImpact")
    partial_result = _build(payload)
    assert partial_result["limited"] is True
    assert partial_result["hardRisk"] is True
    assert partial_result["stance"] == "신규 접근 보류"


def test_canonical_full_exit_signal_overrides_a_positive_weighted_score() -> None:
    payload = _complete_payload()
    payload["quant"]["current"] = {
        "action": "full_exit_pending",
        "label": "전량 매도 대기",
        "next_confirmation": "다음 거래일 시가에 잔여 비중 전량 매도",
    }
    payload["quant"]["confirmation"]["evidence"][0]["score"] = 100
    payload["quant"]["confirmation"]["evidence"][0]["state"] = "supportive"
    payload["marketImpact"]["factors"][0]["direction"] = "호재"

    result = _build(payload)

    assert result["score"] > 0
    assert result["signalAction"] == "full_exit_pending"
    assert result["stance"] == "매도 신호 우선"
    assert result["action"] == "다음 거래일 시가에 잔여 비중 전량 매도"
    assert "현재 시그널은 전량 매도 대기" in result["summary"]


def test_partial_sources_never_manufacture_confidence_or_safe_disclosure() -> None:
    result = _build(
        {
            "code": "005930",
            "dashboard": {
                "code": "005930",
                "name": "삼성전자",
                "as_of": "2026-08-29T12:00:00+09:00",
                "quote": {"trade_date": "2026-08-28"},
                "coverage": {"price": True},
                "chart_analysis": {
                    "score": 78,
                    "trend": "상승 추세",
                    "setup": "돌파 대기",
                    "signals": ["20일선 위"],
                    "risks": [],
                },
                "flows": {},
                "sentiment": {"score": None, "latest_items": []},
            },
            "homeContext": {"disclosures": [], "news_items": []},
        }
    )
    metrics = {item["key"]: item for item in result["metrics"]}

    assert result["coverageCount"] == 1
    assert result["coverageWeight"] == 30
    assert result["limited"] is True
    assert result["stance"] == "정보 확인 우선"
    assert result["confidence"] <= 55
    assert metrics["disclosure"]["available"] is False
    assert metrics["disclosure"]["value"] == "자료 확인 중"
    assert "미확인 지표" in result["warnings"][0]


def test_unmatched_market_factors_are_labeled_as_broad_market_influence() -> None:
    payload = _complete_payload()
    payload["quant"]["sector"] = "은행"
    payload["quant"]["industry"] = "금융"
    payload["dashboard"]["company_profile"] = {"sector": "은행", "industry": "금융"}

    result = _build(payload)
    market = next(item for item in result["metrics"] if item["key"] == "market")

    assert market["relevance"] == "broad"
    assert market["source"] == "시장 5개 축·광역 영향"
    assert any("광역 시장 영향" in item for item in result["warnings"])
