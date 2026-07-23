from __future__ import annotations

import json
import hashlib
import logging
import re
import threading
import time
from typing import Any, Callable, Optional

import requests
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings, get_settings


logger = logging.getLogger(__name__)
_CACHE_LOCK = threading.Lock()
_GENERATION_LOCK = threading.Lock()
_DRAFT_CACHE: dict[str, tuple[float, LocalAnalysisDraft]] = {}


class LocalAnalysisDraft(BaseModel):
    summary: str = Field(min_length=20, max_length=200)


_CRITICAL_NUMBER_PATTERN = re.compile(
    r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s*(?:%|원|조|억|만|배|점|건|개월|일|x))",
    re.IGNORECASE,
)


def _number_facts(text: str) -> set[str]:
    facts: set[str] = set()
    for token in _CRITICAL_NUMBER_PATTERN.findall(text):
        match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", token)
        if match:
            facts.add(match.group(0).replace(",", "").lstrip("+"))
    return facts


def _evidence_bundle(dashboard: dict[str, Any], rules: dict[str, object]) -> dict[str, object]:
    sentiment = dashboard.get("sentiment") if isinstance(dashboard.get("sentiment"), dict) else {}
    news_items = sentiment.get("latest_items") if isinstance(sentiment, dict) else []
    quote = dashboard.get("quote") if isinstance(dashboard.get("quote"), dict) else {}
    momentum = dashboard.get("momentum") if isinstance(dashboard.get("momentum"), dict) else {}
    chart = dashboard.get("chart_analysis") if isinstance(dashboard.get("chart_analysis"), dict) else {}
    revisions = dashboard.get("revisions") if isinstance(dashboard.get("revisions"), dict) else {}
    flows = dashboard.get("flows") if isinstance(dashboard.get("flows"), dict) else {}
    valuation = dashboard.get("valuation") if isinstance(dashboard.get("valuation"), dict) else {}
    return {
        "stock": {
            "code": dashboard.get("code"),
            "name": dashboard.get("name"),
            "as_of": dashboard.get("as_of"),
        },
        "signals": {
            "price": quote.get("price"),
            "day_change_rate": quote.get("change_rate"),
            "one_month_return": momentum.get("one_month_return"),
            "three_month_return": momentum.get("three_month_return"),
            "chart_stance": chart.get("stance"),
            "chart_score": chart.get("score"),
            "foreign_flow": flows.get("foreign_intensity"),
            "institution_flow": flows.get("institution_intensity"),
            "per": valuation.get("per"),
            "pbr": valuation.get("pbr"),
            "analyst_report_count": revisions.get("report_count_90d"),
            "latest_opinion": revisions.get("latest_opinion"),
            "news_score": sentiment.get("score"),
        },
        "news": {
            "headlines": [
                str(item.get("title") or "")[:120]
                for item in (news_items or [])[:2]
                if isinstance(item, dict)
            ],
        },
        "calculated_decision": {
            "stance": rules.get("stance"),
            "confidence": rules.get("confidence"),
            "summary": rules.get("summary"),
            "key_points": rules.get("key_points"),
        },
    }


def _prompt_messages(bundle: dict[str, object]) -> list[dict[str, str]]:
    system_prompt = """당신은 한국 주식 초보자를 위한 분석 편집자입니다.
입력된 데이터와 계산 결과만 사용해 쉬운 한국어로 정리하세요.
새로운 수치, 사실, 뉴스, 목표가를 만들지 마세요.
계산된 stance와 trade_levels를 변경하거나 재계산하지 마세요.
단정적인 수익 보장, 무조건 매수·매도 표현을 쓰지 말고 조건부 대응으로 설명하세요.
summary는 계산된 판단을 바꾸지 말고 가장 중요한 이유를 100자 이내 한 문장으로 설명하세요.
핵심 근거, 가격 전략과 위험 관리는 이미 계산되어 있으므로 다시 작성하지 마세요.
제목, 목록, JSON, 부연 설명 없이 요약 문장만 출력하세요."""
    user_prompt = "다음 분석 근거를 정리하세요.\n" + json.dumps(
        bundle,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _validate_numbers(draft: LocalAnalysisDraft, bundle: dict[str, object]) -> None:
    source_text = json.dumps(bundle, ensure_ascii=False, default=str)
    generated_text = draft.summary
    unexpected = _number_facts(generated_text) - _number_facts(source_text)
    if unexpected:
        raise ValueError(f"Local model introduced unsupported numeric facts: {sorted(unexpected)}")


def _first_complete_sentence(content: object) -> str:
    text = re.sub(r"\s+", " ", str(content or "")).strip().strip('"')
    if not text:
        raise ValueError("Local model returned an empty summary")
    match = re.search(r"^.{10,180}?(?:다\.|요\.)", text)
    summary = match.group(0) if match else text[:200].rstrip()
    return LocalAnalysisDraft(summary=summary).summary


def _fallback(rules: dict[str, object], note: str) -> dict[str, object]:
    output = dict(rules)
    output["generation_mode"] = "rules"
    output["model_name"] = None
    output["generation_note"] = note
    return output


def clear_local_ai_cache() -> None:
    with _CACHE_LOCK:
        _DRAFT_CACHE.clear()


def _cache_key(model: str, bundle: dict[str, object]) -> str:
    payload = json.dumps(bundle, ensure_ascii=False, default=str, sort_keys=True)
    return hashlib.sha256(f"{model}:{payload}".encode("utf-8")).hexdigest()


def _cached_draft(key: str, cache_seconds: int) -> Optional[LocalAnalysisDraft]:
    with _CACHE_LOCK:
        cached = _DRAFT_CACHE.get(key)
        if not cached:
            return None
        created_at, draft = cached
        if time.monotonic() - created_at > max(0, cache_seconds):
            _DRAFT_CACHE.pop(key, None)
            return None
        return draft


def _apply_draft(
    rules: dict[str, object],
    draft: LocalAnalysisDraft,
    model_name: str,
) -> dict[str, object]:
    output = dict(rules)
    output["summary"] = draft.summary
    output["generation_mode"] = "local_llm"
    output["model_name"] = model_name
    output["generation_note"] = "로컬 AI 핵심 요약 · 가격 전략은 데이터 엔진"
    return output


def enrich_stock_ai_analysis(
    dashboard: dict[str, Any],
    rules: dict[str, object],
    *,
    settings: Optional[Settings] = None,
    post: Callable[..., Any] = requests.post,
) -> dict[str, object]:
    config = settings or get_settings()
    if config.stock_ai_provider.strip().lower() != "ollama":
        return rules

    bundle = _evidence_bundle(dashboard, rules)
    cache_key = _cache_key(config.ollama_model, bundle)
    cached = _cached_draft(cache_key, config.ollama_cache_seconds)
    if cached:
        return _apply_draft(rules, cached, config.ollama_model)
    endpoint = f"{config.ollama_base_url.rstrip('/')}/api/chat"
    with _GENERATION_LOCK:
        cached = _cached_draft(cache_key, config.ollama_cache_seconds)
        if cached:
            return _apply_draft(rules, cached, config.ollama_model)
        try:
            response = post(
                endpoint,
                json={
                    "model": config.ollama_model,
                    "messages": _prompt_messages(bundle),
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0, "num_ctx": 1536, "num_predict": 80},
                    "keep_alive": "15m",
                },
                timeout=max(10, config.ollama_timeout_seconds),
            )
            response.raise_for_status()
            body = response.json()
            content = body.get("message", {}).get("content")
            draft = LocalAnalysisDraft(summary=_first_complete_sentence(content))
            _validate_numbers(draft, bundle)
        except (requests.RequestException, ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Local stock AI unavailable; using rule analysis: %s", exc)
            return _fallback(rules, "로컬 AI 연결 실패 · 데이터 분석 사용")
        with _CACHE_LOCK:
            _DRAFT_CACHE[cache_key] = (time.monotonic(), draft)
        return _apply_draft(rules, draft, config.ollama_model)
