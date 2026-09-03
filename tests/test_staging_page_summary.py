from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import staging_app as staging_module
from app.main import app as production_app
from app.services import staging_page_summary as summary_module
from app.services.staging_page_summary import (
    DEFAULT_MODEL,
    PageSummaryRequest,
    StagingPageSummaryService,
    StagingPageSummarySettings,
)


def _fallback() -> dict[str, object]:
    return {
        "headline": "삼성전자, 신규 매수를 기다리는 단계예요",
        "summary": "추천 기준은 통과했지만 아직 매수 전이에요.",
        "reason": "추천 점수와 가격 조건, 서로 다른 확인 자료가 모두 기준을 통과했어요.",
        "action_title": "지금은 새로 살 가격이 기준 안인지 확인할 때예요",
        "next_check": "다음 거래가 시작될 때 가격이 매수 기준 안인지 확인해요.",
        "evidence_refs": ["buy-condition", "recommendation-score"],
    }


def _request() -> PageSummaryRequest:
    return PageSummaryRequest.model_validate(
        {
            "page_type": "recommendation_detail",
            "facts": {
                "code": "005930",
                "name": "삼성전자",
                "score": 74.22,
                "recommendation_state": "entry_confirmed",
                "customer_state": "new-buy-wait",
                "customer_state_label": "신규 매수 대기",
                "customer_state_note": "아직 매수 전",
                "additional_buy_label": "보유 전",
                "buy_condition_met": True,
                "buy_condition_as_of": "2026-08-31T15:40:00+09:00",
                "current_price": 181100,
                "condition_price": 181100,
                "entry_reference": 180000,
                "signal_action": "entry_pending",
                "signal_score": 78.5,
                "position_open": False,
                "entry_confirmation": {
                    "allowed": True,
                    "state": "approved",
                    "required_supports": 1,
                    "supportive_count": 2,
                },
                "sources": [
                    {"id": "buy-condition", "label": "추천 기준 확인", "value": "신규 매수 대기"},
                    {"id": "recommendation-score", "label": "추천 점수", "value": 74.22},
                ],
            },
            "fallback": _fallback(),
        }
    )


def _settings(*, enabled: bool = True, api_key: str = "test-key") -> StagingPageSummarySettings:
    return StagingPageSummarySettings(
        api_key=api_key,
        enabled=enabled,
        model=DEFAULT_MODEL,
        api_base="https://api.openai.test/v1",
        timeout_seconds=2,
        cache_seconds=1800,
    )


@pytest.mark.qa_gate
def test_staging_summary_uses_responses_structured_output_and_caches_valid_copy() -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.openai.test/v1/responses"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        calls.append(body)
        user_payload = json.loads(body["input"][1]["content"])
        assert user_payload["allowed_evidence_refs"] == ["buy-condition", "recommendation-score"]
        assert "각 ID를 별도 문자열로 정확히 복사" in body["input"][0]["content"]
        assert "현재 AI 판단" in body["input"][0]["content"]
        assert "단순 후보" in body["input"][0]["content"]
        assert "customer_state가 new-buy-wait" in body["input"][0]["content"]
        assert "customer_state가 hold" in body["input"][0]["content"]
        generated = {
            "headline": "삼성전자, 신규 매수 대기 상태예요",
            "summary": "추천 기준은 통과했지만 아직 매수 전이에요.",
            "reason": "추천 점수와 가격 조건, 서로 다른 확인 자료 2개가 기준을 통과했어요.",
            "action_title": "지금은 새로 살 가격을 확인할 때예요",
            "next_check": "다음 거래가 시작될 때 가격이 매수 기준 안인지 확인해요.",
            "evidence_refs": ["buy-condition", "recommendation-score"],
        }
        return httpx.Response(
            200,
            json={
                "output": [
                    {"content": [{"type": "output_text", "text": json.dumps(generated, ensure_ascii=False)}]}
                ],
                "usage": {"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
            },
        )

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    first = asyncio.run(service.summarize(_request()))
    second = asyncio.run(service.summarize(_request()))

    assert first.generation_mode == "openai"
    assert first.model_name == DEFAULT_MODEL
    assert first.estimated_cost_usd == pytest.approx(0.00021)
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(calls) == 1
    assert calls[0]["model"] == DEFAULT_MODEL
    assert calls[0]["store"] is False
    assert calls[0]["temperature"] == 0
    assert calls[0]["text"]["format"]["type"] == "json_schema"
    assert calls[0]["text"]["format"]["strict"] is True


@pytest.mark.qa_gate
def test_staging_summary_explains_current_holding_without_operator_timing() -> None:
    fallback = {
        "headline": "삼성전자, 현재 AI 판단은 보유 유지예요",
        "summary": "AI 전략은 이미 보유 중이며 지금은 새로 더 사기보다 보유 기준을 확인해요.",
        "reason": "추천 점수와 가격 조건, 서로 다른 확인 자료 2개가 기준을 통과했어요.",
        "action_title": "지금은 추가 매수보다 보유 기준을 확인할 때예요",
        "next_check": "손실을 줄일 가격과 첫 수익 확인 가격을 살펴봐요.",
        "evidence_refs": ["buy-condition", "recommendation-score"],
    }
    request = PageSummaryRequest.model_validate(
        {
            "page_type": "recommendation_detail",
            "facts": {
                "code": "005930",
                "name": "삼성전자",
                "score": 74.22,
                "recommendation_state": "entered_today",
                "customer_state": "hold",
                "customer_state_label": "보유 유지",
                "customer_state_note": "추가 매수보다 보유 기준을 확인하는 단계",
                "additional_buy_label": "신호 없음",
                "buy_condition_met": True,
                "buy_condition_as_of": "2026-08-31T15:40:00+09:00",
                "entry_date": "2026-09-01",
                "strategy_entry_price": 169100,
                "current_price": 171600,
                "condition_price": 173300,
                "signal_action": "entered",
                "signal_score": 75.37,
                "position_open": True,
                "sources": [
                    {"id": "buy-condition", "label": "추천 기준 확인", "value": "보유 유지"},
                    {"id": "recommendation-score", "label": "추천 점수", "value": 74.22},
                ],
            },
            "fallback": fallback,
        }
    )

    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        assert "customer_state와 customer_state_label" in body["input"][0]["content"]
        assert "오늘 시가 반영" in body["input"][0]["content"]
        assert "쓰지 마세요" in body["input"][0]["content"]
        generated = {
            "headline": "보유 유지",
            "summary": "현재 삼성전자를 보유하고 계시며, 추가 매수 신호는 없습니다.",
            "reason": "추천 기준을 통과하여 보유 유지 상태입니다.",
            "action_title": "보유 기준과 위험 가격을 확인해 주세요.",
            "next_check": "다음 확인 기준은 현재가와 보유 기준을 살펴보는 것입니다.",
            "evidence_refs": ["buy-condition", "recommendation-score"],
        }
        return httpx.Response(
            200,
            json={"output_text": json.dumps(generated, ensure_ascii=False)},
        )

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(service.summarize(request))

    assert result.generation_mode == "openai"
    assert "보유" in result.summary
    assert "시가 반영" not in result.summary
    assert "보유 기준" in result.action_title


@pytest.mark.qa_gate
def test_staging_summary_rejects_holding_copy_that_returns_to_new_buy_wait() -> None:
    request = PageSummaryRequest.model_validate(
        {
            "page_type": "recommendation_detail",
            "facts": {
                "code": "005930",
                "recommendation_state": "entered_today",
                "customer_state": "hold",
                "customer_state_label": "보유 유지",
                "additional_buy_label": "신호 없음",
                "buy_condition_met": True,
                "position_open": True,
                "sources": [{"id": "buy-condition", "label": "매수 조건 확인"}],
            },
            "fallback": {
                "headline": "삼성전자, 현재 AI 판단은 보유 유지예요",
                "summary": "추천 기준을 통과한 뒤 이미 보유 중인 상태예요.",
                "reason": "추천에 필요한 조건을 모두 확인했어요.",
                "action_title": "지금은 추가 매수보다 보유 기준을 확인할 때예요",
                "next_check": "손실을 줄일 가격과 첫 수익 확인 가격을 살펴봐요.",
                "evidence_refs": ["buy-condition"],
            },
        }
    )
    generated = {
        **request.fallback.model_dump(),
        "headline": "삼성전자, 신규 매수 대기 상태예요",
        "action_title": "지금은 새로 살 가격을 확인할 때예요",
        "next_check": "다음 거래가 시작될 때 매수 가격을 확인해요.",
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(generated, ensure_ascii=False)})

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(service.summarize(request))

    assert result.generation_mode == "rules"
    assert result.action_title == "지금은 추가 매수보다 보유 기준을 확인할 때예요"


@pytest.mark.qa_gate
def test_staging_summary_restores_customer_state_when_model_omits_it() -> None:
    fallback = {
        "headline": "KB금융, 현재 AI 판단은 보유 유지예요",
        "summary": "추천 기준을 통과한 뒤 이미 보유 중인 상태예요.",
        "reason": "추천 기준과 서로 다른 확인 자료를 확인했어요.",
        "action_title": "지금은 추가 매수보다 보유 기준을 확인할 때예요.",
        "next_check": "손실을 줄일 가격과 첫 수익 확인 가격을 살펴봐요.",
        "evidence_refs": ["buy-condition"],
    }
    request = PageSummaryRequest.model_validate(
        {
            "page_type": "recommendation_detail",
            "facts": {
                "code": "105560",
                "recommendation_state": "entered_today",
                "customer_state": "hold",
                "customer_state_label": "보유 유지",
                "additional_buy_label": "신호 없음",
                "buy_condition_met": True,
                "position_open": True,
                "sources": [{"id": "buy-condition", "label": "매수 조건 확인"}],
            },
            "fallback": fallback,
        }
    )
    generated = {
        "headline": "KB금융은 추천 기준을 통과했습니다.",
        "summary": "현재 추천 점수 기준을 만족했습니다.",
        "reason": "추천 기준과 서로 다른 확인 자료를 확인했어요.",
        "action_title": "현재 상태를 확인하는 단계입니다.",
        "next_check": "손실을 줄일 가격과 첫 수익 확인 가격을 살펴봐요.",
        "evidence_refs": ["buy-condition"],
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(generated, ensure_ascii=False)})

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(service.summarize(request))

    assert result.generation_mode == "openai"
    assert result.headline == fallback["headline"]
    assert result.summary == fallback["summary"]
    assert result.action_title == fallback["action_title"]
    assert result.reason == generated["reason"]
    assert result.next_check == "손실을 줄일 가격과 첫 수익 확인 가격을 살펴봐요."


@pytest.mark.qa_gate
def test_briefing_summary_keeps_edition_facts_and_uses_exact_allowed_evidence_refs() -> None:
    fallback = {
        "headline": "오전 핵심을 새로 정리했어요",
        "summary": "시장 흐름과 기업 소식을 함께 살펴봐요.",
        "reason": "오후 흐름에 영향을 줄 공개 소식을 모았어요.",
        "action_title": "이번 브리핑에서 먼저 볼 내용",
        "next_check": "원문과 최신 시세를 함께 확인하세요.",
        "evidence_refs": ["briefing-market-1", "briefing-company-2"],
    }
    request = PageSummaryRequest.model_validate(
        {
            "page_type": "briefing_edition",
            "facts": {
                "edition": "midday",
                "edition_key": "2026-08-31:12",
                "edition_label": "점심판",
                "publication_date": "2026-08-31",
                "selected_news_count": 2,
                "sources": [
                    {
                        "id": "briefing-market-1",
                        "label": "시장 흐름",
                        "value": "오전 시장 흐름",
                    },
                    {
                        "id": "briefing-company-2",
                        "label": "기업 소식",
                        "value": "기업 실적 발표",
                    },
                ],
            },
            "fallback": fallback,
        }
    )
    generated = {
        **fallback,
        "headline": "점심에 확인할 시장 핵심이에요",
        "summary": "오전 시장 흐름과 기업 소식을 짧게 정리했어요.",
    }

    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        user_payload = json.loads(body["input"][1]["content"])
        assert "오전·점심·오후 시장 브리핑" in body["input"][0]["content"]
        assert "판 구분" in body["input"][0]["content"]
        assert user_payload["facts"]["edition"] == "midday"
        assert user_payload["facts"]["selected_news_count"] == 2
        assert user_payload["allowed_evidence_refs"] == [
            "briefing-market-1",
            "briefing-company-2",
        ]
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(generated, ensure_ascii=False),
                "usage": {"input_tokens": 400, "output_tokens": 80, "total_tokens": 480},
            },
        )

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(service.summarize(request))

    assert result.generation_mode == "openai"
    assert result.headline == generated["headline"]
    assert result.evidence_refs == fallback["evidence_refs"]


@pytest.mark.qa_gate
@pytest.mark.parametrize(
    "unsafe_copy",
    [
        {"summary": "목표 200,000원까지 확인해요."},
        {"action_title": "지금 매수하세요"},
        {"action_title": "신규 매수 조건을 확인해요", "next_check": "새로 진입할 흐름을 봐요."},
        {"summary": "현재 포지션의 진입 시그널과 수급을 확인해요."},
        {"summary": "GPT가 현재 상황을 쉽게 정리했어요."},
        {"summary": "오늘 시가 반영 완료 상태이며 전략 반영이 끝났어요."},
        {"headline": "삼성전자를 계속 보유하는 것이 좋습니다."},
        {
            "headline": "삼성전자는 아직 추천 후보예요",
            "summary": "매수 조건을 충족했지만 지금 따라 사는 건 조심해야 해요.",
        },
        {"next_check": "다음 거래일 시가가 181100원 이상인지 확인해요."},
        {"evidence_refs": ["unknown-source"]},
        {"evidence_refs": ["candidate-score", "trade-signal','chart-score"]},
    ],
)
def test_staging_summary_rejects_invented_numbers_trading_commands_and_unknown_sources(
    unsafe_copy: dict[str, object],
) -> None:
    generated = {**_fallback(), **unsafe_copy}

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(generated, ensure_ascii=False)})

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(service.summarize(_request()))

    assert result.generation_mode == "rules"
    assert result.model_dump(include=set(_fallback())) == _fallback()
    assert "검증하지 못해" in result.generation_note


@pytest.mark.qa_gate
def test_staging_summary_disabled_or_failed_keeps_deterministic_copy() -> None:
    disabled = StagingPageSummaryService(_settings(enabled=False, api_key=""))
    disabled_result = asyncio.run(disabled.summarize(_request()))

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "unavailable"}})

    failed = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    failed_result = asyncio.run(failed.summarize(_request()))

    assert disabled_result.generation_mode == "rules"
    assert failed_result.generation_mode == "rules"
    assert disabled_result.model_dump(include=set(_fallback())) == _fallback()
    assert failed_result.model_dump(include=set(_fallback())) == _fallback()


@pytest.mark.qa_gate
@pytest.mark.parametrize("failure_kind", ["timeout", "invalid_json"])
def test_staging_summary_transport_and_json_failures_keep_deterministic_copy(
    failure_kind: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure_kind == "timeout":
            raise httpx.ReadTimeout("fixture timeout", request=request)
        return httpx.Response(
            200,
            content=b"{invalid-json",
            headers={"content-type": "application/json"},
        )

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(service.summarize(_request()))

    assert result.generation_mode == "rules"
    assert result.model_dump(include=set(_fallback())) == _fallback()
    assert "검증하지 못해" in result.generation_note


@pytest.mark.qa_gate
def test_staging_stock_response_rejects_copy_that_hides_hard_risk() -> None:
    fallback = {
        **_fallback(),
        "headline": "중대 공시 위험을 먼저 확인하세요",
        "summary": "다른 지표보다 공시 원문 확인이 우선이에요.",
    }
    request = PageSummaryRequest.model_validate(
        {
            "page_type": "stock_response",
            "facts": {
                "code": "005930",
                "hard_risk": True,
                "sources": [{"id": "disclosure-risk", "label": "회사 공식 공시"}],
            },
            "fallback": {**fallback, "evidence_refs": ["disclosure-risk"]},
        }
    )
    generated = {
        **fallback,
        "headline": "차분히 다음 흐름을 확인하세요",
        "summary": "여러 자료를 함께 살펴보고 있어요.",
        "evidence_refs": ["disclosure-risk"],
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(generated, ensure_ascii=False)})

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(service.summarize(request))

    assert result.generation_mode == "rules"
    assert result.model_dump(include=set(fallback)) == {
        **fallback,
        "evidence_refs": ["disclosure-risk"],
    }


@pytest.mark.qa_gate
@pytest.mark.parametrize(
    (
        "investor_state",
        "position_mode",
        "headline",
        "summary",
        "action_title",
        "expected_term",
    ),
    [
        (
            "not_holding",
            "watching",
            "현재는 매수 관망이 필요해요",
            "가격과 외국인·기관 매매가 같은 방향으로 모일 때까지 기다리는 구간이에요.",
            "새 매수 조건을 확인할 때예요",
            "매수 관망",
        ),
        (
            "holding",
            "holding_profit",
            "현재 수익권이라 분할 매도 기준을 볼 단계예요",
            "평균 매수가보다 현재가가 높아 이익을 나눠 지킬 가격을 확인하고 있어요.",
            "이익을 지킬 기준을 확인할 단계예요",
            "수익",
        ),
        (
            "holding",
            "holding_loss",
            "현재 손실권이라 손실 제한 기준을 볼 단계예요",
            "평균 매수가보다 현재가가 낮아 회복을 확인할 가격도 함께 보고 있어요.",
            "손실과 회복 기준을 확인할 단계예요",
            "손실",
        ),
    ],
)
def test_staging_stock_response_preserves_user_selected_investor_state(
    investor_state: str,
    position_mode: str,
    headline: str,
    summary: str,
    action_title: str,
    expected_term: str,
) -> None:
    fallback = {
        "headline": headline,
        "summary": summary,
        "reason": "가격 흐름과 외국인·기관 매매가 엇갈려 있어요.",
        "action_title": action_title,
        "next_check": "가격 조건과 신호가 함께 갖춰지는지 확인해요.",
        "evidence_refs": ["metric-chart"],
    }
    request = PageSummaryRequest.model_validate(
        {
            "page_type": "stock_response",
            "facts": {
                "code": "005930",
                "name": "삼성전자",
                "investor_state": investor_state,
                "investor_state_label": {
                    "not_holding": "미보유",
                    "holding": "보유 중",
                }[investor_state],
                "position_mode": position_mode,
                "average_buy_price": 70_000 if investor_state == "holding" else None,
                "personal_return_rate": (
                    None
                    if investor_state == "not_holding"
                    else 4.25
                    if position_mode == "holding_profit"
                    else -4.25
                ),
                "sources": [{"id": "metric-chart", "label": "가격 흐름"}],
            },
            "fallback": fallback,
        }
    )

    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        prompt = body["input"][0]["content"]
        user_facts = json.loads(body["input"][1]["content"])["facts"]
        assert "investor_state는 사용자가 직접 선택" in prompt
        assert "증권사 리포트" in prompt
        assert user_facts["investor_state"] == investor_state
        assert user_facts["position_mode"] == position_mode
        return httpx.Response(
            200,
            json={"output_text": json.dumps(fallback, ensure_ascii=False)},
        )

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(service.summarize(request))

    assert result.generation_mode == "openai"
    assert expected_term in f"{result.headline} {result.summary} {result.action_title}"


@pytest.mark.qa_gate
def test_staging_stock_response_replaces_holding_copy_for_not_holding_observation() -> None:
    fallback = {
        "headline": "현재는 매수 관망이 필요해요",
        "summary": "아직 보유하지 않은 상태에서 새로 살 조건을 기다리고 있어요.",
        "reason": "가격 흐름의 주의 신호가 반영됐어요.",
        "action_title": "새 매수 조건을 확인할 때예요",
        "next_check": "새로 살 가격 조건을 확인해요.",
        "evidence_refs": ["metric-chart"],
    }
    request = PageSummaryRequest.model_validate(
        {
            "page_type": "stock_response",
            "facts": {
                "code": "005930",
                "investor_state": "not_holding",
                "position_mode": "watching",
                "sources": [{"id": "metric-chart", "label": "가격 흐름"}],
            },
            "fallback": fallback,
        }
    )
    mismatched = {
        **fallback,
        "headline": "계속 보유할 기준을 볼 때예요",
        "summary": "현재 보유 중이며 추가 매수 조건을 확인해요.",
        "action_title": "보유 기준을 확인해요",
    }

    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={"output_text": json.dumps(mismatched, ensure_ascii=False)},
            )
        ),
    )
    result = asyncio.run(service.summarize(request))

    assert result.headline == fallback["headline"]
    assert result.summary == fallback["summary"]
    assert "추가 매수" not in result.summary


@pytest.mark.qa_gate
def test_staging_stock_response_requires_average_price_for_unknown_holding_return() -> None:
    fallback = {
        "headline": "평균 매수가를 입력하면 내 보유 전략을 볼 수 있어요",
        "summary": "아직 내 수익·손실을 계산하지 않았어요.",
        "reason": "평균 매수가가 없으면 수익권·손실권을 구분할 수 없어요.",
        "action_title": "평균 매수가를 입력할 단계예요",
        "next_check": "평균 매수가와 현재가를 비교해요.",
        "evidence_refs": ["metric-research"],
    }
    request = PageSummaryRequest.model_validate(
        {
            "page_type": "stock_response",
            "facts": {
                "code": "005930",
                "investor_state": "holding",
                "position_mode": "holding_unknown",
                "average_buy_price": None,
                "sources": [{"id": "metric-research", "label": "증권사 리포트"}],
            },
            "fallback": fallback,
        }
    )
    service = StagingPageSummaryService(
        _settings(),
        transport=httpx.MockTransport(
            lambda _: pytest.fail("평균 매수가 입력 전에는 모델을 호출하면 안 됩니다.")
        ),
    )

    result = asyncio.run(service.summarize(request))

    assert result.generation_mode == "rules"
    assert result.headline == fallback["headline"]
    assert result.summary == fallback["summary"]
    assert "개인 손익 전략을 생성하지 않습니다" in (result.generation_note or "")


def test_environment_requires_explicit_enable_even_when_key_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("STAGING_OPENAI_SUMMARY_ENABLED", raising=False)

    settings = StagingPageSummarySettings.from_environment()

    assert settings.api_key == "test-key"
    assert settings.enabled is False

    monkeypatch.setenv("STAGING_OPENAI_SUMMARY_ENABLED", "true")
    assert StagingPageSummarySettings.from_environment().enabled is True


@pytest.mark.qa_gate
def test_staging_only_summary_endpoint_validates_payload_and_preserves_production(monkeypatch) -> None:
    monkeypatch.setattr(
        summary_module,
        "_service",
        StagingPageSummaryService(_settings(enabled=False, api_key="")),
    )
    staging_module._staging_page_summary_client_requests.clear()
    staging_module._staging_page_summary_global_requests.clear()
    staging_client = TestClient(staging_module.app)

    valid = staging_client.post(
        staging_module.STAGING_PAGE_SUMMARY_PATH,
        json={
            "page_type": "recommendation_detail",
            "facts": {"code": "005930", "sources": [{"id": "candidate-score"}]},
            "fallback": _fallback(),
        },
    )
    invalid = staging_client.post(staging_module.STAGING_PAGE_SUMMARY_PATH, json={"page_type": "other"})
    production = TestClient(production_app).post(
        staging_module.STAGING_PAGE_SUMMARY_PATH,
        json={
            "page_type": "recommendation_detail",
            "facts": {},
            "fallback": _fallback(),
        },
    )

    assert valid.status_code == 200
    assert valid.json()["generation_mode"] == "rules"
    assert valid.headers["cache-control"] == "no-store"
    assert invalid.status_code == 400
    assert production.status_code in {404, 405}


@pytest.mark.qa_gate
def test_staging_summary_endpoint_limits_public_client_requests(monkeypatch) -> None:
    monkeypatch.setattr(
        summary_module,
        "_service",
        StagingPageSummaryService(_settings(enabled=False, api_key="")),
    )
    staging_module._staging_page_summary_client_requests.clear()
    staging_module._staging_page_summary_global_requests.clear()
    client = TestClient(staging_module.app)
    payload = {
        "page_type": "recommendation_detail",
        "facts": {"code": "005930", "sources": [{"id": "candidate-score"}]},
        "fallback": _fallback(),
    }

    responses = [
        client.post(staging_module.STAGING_PAGE_SUMMARY_PATH, json=payload)
        for _ in range(staging_module.STAGING_PAGE_SUMMARY_RATE_PER_CLIENT)
    ]
    limited = client.post(staging_module.STAGING_PAGE_SUMMARY_PATH, json=payload)

    assert all(response.status_code == 200 for response in responses)
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    staging_module._staging_page_summary_client_requests.clear()
    staging_module._staging_page_summary_global_requests.clear()


@pytest.mark.qa_gate
def test_staging_summary_endpoint_enforces_global_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(staging_module, "STAGING_PAGE_SUMMARY_RATE_GLOBAL", 3)
    staging_module._staging_page_summary_client_requests.clear()
    staging_module._staging_page_summary_global_requests.clear()

    allowed = [
        staging_module._allow_staging_page_summary_request(
            {"client": (f"198.51.100.{index}", 443)}
        )
        for index in range(1, 4)
    ]
    rejected = staging_module._allow_staging_page_summary_request(
        {"client": ("198.51.100.4", 443)}
    )

    assert allowed == [True, True, True]
    assert rejected is False
    staging_module._staging_page_summary_client_requests.clear()
    staging_module._staging_page_summary_global_requests.clear()


@pytest.mark.qa_gate
def test_staging_summary_endpoint_rejects_cross_site_and_oversized_requests(
    monkeypatch,
) -> None:
    staging_module._staging_page_summary_client_requests.clear()
    staging_module._staging_page_summary_global_requests.clear()
    client = TestClient(staging_module.app)

    cross_site = client.post(
        staging_module.STAGING_PAGE_SUMMARY_PATH,
        json={"page_type": "recommendation_detail"},
        headers={"sec-fetch-site": "cross-site"},
    )
    monkeypatch.setattr(staging_module, "STAGING_PAGE_SUMMARY_MAX_BODY_BYTES", 32)
    oversized = client.post(
        staging_module.STAGING_PAGE_SUMMARY_PATH,
        content=b"{" + b'x' * 64 + b"}",
        headers={"content-type": "application/json"},
    )

    assert cross_site.status_code == 403
    assert oversized.status_code == 413
    staging_module._staging_page_summary_client_requests.clear()
    staging_module._staging_page_summary_global_requests.clear()
