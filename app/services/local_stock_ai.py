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
    focus: str = Field(min_length=2, max_length=10)


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


def _rounded(value: object, digits: int = 1) -> object:
    if value is None or isinstance(value, bool):
        return value
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return value


def _evidence_bundle(dashboard: dict[str, Any], rules: dict[str, object]) -> dict[str, object]:
    sentiment = dashboard.get("sentiment") if isinstance(dashboard.get("sentiment"), dict) else {}
    quote = dashboard.get("quote") if isinstance(dashboard.get("quote"), dict) else {}
    momentum = dashboard.get("momentum") if isinstance(dashboard.get("momentum"), dict) else {}
    chart = dashboard.get("chart_analysis") if isinstance(dashboard.get("chart_analysis"), dict) else {}
    flows = dashboard.get("flows") if isinstance(dashboard.get("flows"), dict) else {}
    valuation = dashboard.get("valuation") if isinstance(dashboard.get("valuation"), dict) else {}
    return {
        "일": _rounded(quote.get("change_rate")),
        "1M": _rounded(momentum.get("one_month_return")),
        "3M": _rounded(momentum.get("three_month_return")),
        "차트": _rounded(chart.get("score"), 0),
        "외": _rounded(flows.get("foreign_intensity")),
        "기관": _rounded(flows.get("institution_intensity")),
        "PER": _rounded(valuation.get("per"), 2),
        "PBR": _rounded(valuation.get("pbr"), 2),
        "뉴스": _rounded(sentiment.get("score")),
        "판단": rules.get("stance"),
    }


def _prompt_messages(bundle: dict[str, object]) -> list[dict[str, str]]:
    system_prompt = "입력에서 가장 먼저 볼 근거를 단기, 수급, 밸류, 뉴스 중 하나로만 출력하세요."
    user_prompt = json.dumps(
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
    generated_text = draft.focus
    unexpected = _number_facts(generated_text) - _number_facts(source_text)
    if unexpected:
        raise ValueError(f"Local model introduced unsupported numeric facts: {sorted(unexpected)}")


def _focus_from_content(content: object) -> str:
    text = re.sub(r"\s+", " ", str(content or "")).strip().strip('"')
    for focus in ("단기", "수급", "밸류", "뉴스"):
        if focus in text:
            return LocalAnalysisDraft(focus=focus).focus
    raise ValueError("Local model did not select a supported focus")


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
    key_points = rules.get("key_points") if isinstance(rules.get("key_points"), list) else []
    point_index = {"단기": 0, "수급": 3, "밸류": 4, "뉴스": 5}.get(draft.focus, 0)
    point = str(key_points[point_index]) if len(key_points) > point_index else str(rules.get("summary") or "")
    output["summary"] = f"{draft.focus} 우선 · {point}"
    output["generation_mode"] = "local_llm"
    output["model_name"] = model_name
    output["generation_note"] = "Ollama AI 핵심 근거 선택 · 가격 전략은 데이터 엔진"
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
                    "options": {"temperature": 0, "num_ctx": 256, "num_predict": 6},
                    "keep_alive": "15m",
                },
                timeout=max(10, config.ollama_timeout_seconds),
            )
            response.raise_for_status()
            body = response.json()
            content = body.get("message", {}).get("content")
            draft = LocalAnalysisDraft(focus=_focus_from_content(content))
            _validate_numbers(draft, bundle)
        except (requests.RequestException, ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Local stock AI unavailable; using rule analysis: %s", exc)
            return _fallback(rules, "로컬 AI 연결 실패 · 데이터 분석 사용")
        with _CACHE_LOCK:
            _DRAFT_CACHE[cache_key] = (time.monotonic(), draft)
        return _apply_draft(rules, draft, config.ollama_model)
