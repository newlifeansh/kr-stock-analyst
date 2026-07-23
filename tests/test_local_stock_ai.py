from app.config import Settings
from app.services.local_stock_ai import clear_local_ai_cache, enrich_stock_ai_analysis


class _Response:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


def _settings(provider: str = "ollama") -> Settings:
    return Settings(
        stock_ai_provider=provider,
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="qwen3:0.6b",
        ollama_timeout_seconds=15,
    )


def _dashboard():
    return {
        "code": "006400",
        "name": "삼성SDI",
        "market": "KOSPI",
        "as_of": "2026-07-23T09:00:00",
        "quote": {"price": 533000, "change_rate": 2.1, "trading_value": 238830000000},
        "momentum": {"one_month_return": -5.45, "three_month_return": 37.04},
        "chart_analysis": {"stance": "관망 우선", "score": 34},
        "revisions": {"report_count_90d": 3},
        "surprise": {"operating_profit_growth": -47.99},
        "flows": {"foreign_intensity": 2.79, "institution_intensity": -2.62},
        "valuation": {"per": -71.76, "pbr": 1.86},
        "sentiment": {"score": 10, "latest_items": [{"title": "관련 뉴스"}]},
        "macro_sensitivity": {"interest_rate": 3.56},
        "coverage": {"price": True, "chart": True},
    }


def _rules():
    return {
        "code": "006400",
        "name": "삼성SDI",
        "market": "KOSPI",
        "stance": "관망 우선",
        "confidence": 100,
        "summary": "1개월 -5.45% 흐름이므로 관망 우선입니다.",
        "key_points": ["현재가 533,000입니다.", "3개월 +37.04%입니다.", "차트 점수 34점입니다."],
        "strategy": [
            "신규 진입은 보류합니다.",
            "전환 가격은 550,000입니다.",
            "보유 대응은 510,000 이탈을 확인합니다.",
            "이익 관리는 570,000에서 확인합니다.",
        ],
        "risks": ["1개월 -5.45%입니다.", "영업이익 변화 -47.99%입니다."],
        "sections": [],
        "trade_levels": {"breakout": 550000, "stop": 510000, "first_sell": 570000},
        "generation_mode": "rules",
        "model_name": None,
        "generation_note": "데이터 기반 규칙 분석",
    }


def test_rules_provider_does_not_call_local_model():
    clear_local_ai_cache()
    calls = []

    result = enrich_stock_ai_analysis(
        _dashboard(),
        _rules(),
        settings=_settings("rules"),
        post=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert result["generation_mode"] == "rules"
    assert calls == []


def test_ollama_rewrites_prose_without_changing_calculated_decision():
    clear_local_ai_cache()
    draft = "삼성SDI는 단기 흐름이 약해 관망 우선 판단입니다. 1개월 -5.45% 흐름을 먼저 확인해야 합니다."
    captured = {}

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response(draft)

    rules = _rules()
    result = enrich_stock_ai_analysis(_dashboard(), rules, settings=_settings(), post=post)

    assert result["generation_mode"] == "local_llm"
    assert result["model_name"] == "qwen3:0.6b"
    assert result["summary"] == "삼성SDI는 단기 흐름이 약해 관망 우선 판단입니다."
    assert result["key_points"] == rules["key_points"]
    assert result["strategy"] == rules["strategy"]
    assert result["risks"] == rules["risks"]
    assert result["stance"] == rules["stance"]
    assert result["trade_levels"] == rules["trade_levels"]
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert "format" not in captured["json"]
    assert captured["json"]["think"] is False


def test_ollama_output_with_unsupported_number_falls_back_to_rules():
    clear_local_ai_cache()
    draft = "삼성SDI가 99.99% 상승할 수 있다는 근거 없는 문장입니다."

    result = enrich_stock_ai_analysis(
        _dashboard(),
        _rules(),
        settings=_settings(),
        post=lambda *args, **kwargs: _Response(draft),
    )

    assert result["generation_mode"] == "rules"
    assert result["summary"] == _rules()["summary"]
    assert "연결 실패" in result["generation_note"]
