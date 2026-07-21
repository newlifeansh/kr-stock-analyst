from app.services.stock_ai_analysis import build_stock_ai_analysis


def _base_dashboard():
    return {
        "code": "006400",
        "name": "삼성SDI",
        "market": "KOSPI",
        "as_of": "2026-06-22T10:00:00",
        "quote": {"price": 533000, "trading_value": 238_830_000_000},
        "momentum": {"one_month_return": -5.45, "three_month_return": 37.04, "trading_value_change": -42.35},
        "chart_analysis": {
            "score": 34,
            "stance": "관망 우선",
            "trend": "단기 약세",
            "setup": "추세 확인",
            "support": 375000,
            "resistance": 723000,
            "atr_percent": 3.6,
            "moving_averages": {"ma5": 520000, "ma20": 548000, "ma60": 501000},
            "signals": ["20일선 아래"],
            "risks": ["현재가가 20일선 아래라 단기 추세 확인 필요"],
        },
        "revisions": {"target_up_ratio": None, "report_count_90d": 0, "estimated_eps": 4364},
        "surprise": {"operating_profit_growth": -47.99},
        "guidance": {},
        "flows": {
            "foreign_intensity": 2.79,
            "institution_intensity": -2.62,
            "foreign_net_buy_20d": 239_150_000_000,
            "institution_net_buy_20d": -224_670_000_000,
        },
        "valuation": {"per": -71.76, "pbr": 1.86, "estimated_per": 122.0, "per_zscore": None, "pbr_zscore": 2.4},
        "sentiment": {"score": 100, "latest_items": [{"title": "삼성SDI 관련 뉴스"}]},
        "macro_sensitivity": {"interest_rate": 3.56, "fx_usdkrw": 6.49, "commodity": -10.47, "exports": 11.26},
        "coverage": {"price": True, "chart": True, "flows": True, "sentiment": True},
    }


def test_stock_ai_analysis_uses_near_current_trade_levels_for_strategy():
    payload = build_stock_ai_analysis(_base_dashboard())
    strategy_text = " ".join(payload["strategy"])
    summary_text = payload["summary"]
    trade_levels = payload["trade_levels"]

    assert "375,000" not in strategy_text
    assert "723,000" not in strategy_text
    assert "533,000" not in strategy_text
    assert "1차 매수" not in strategy_text
    assert "매수권" not in summary_text
    assert "신규 매수: 보류" in strategy_text
    assert "보유 대응" in strategy_text
    assert trade_levels["actionable"] is False
    assert trade_levels["entry_label"] == "관찰 가격대"
    assert trade_levels["support_reference"] == 375000
    assert trade_levels["resistance_reference"] == 723000
    assert payload["data_covered"] == 4
    assert payload["data_total"] == 4
    assert payload["confidence"] == 100
    assert 500000 <= trade_levels["buy_low"] <= 533000
    assert 533000 <= trade_levels["buy_high"] <= 560000
    assert 505000 <= trade_levels["stop"] <= 533000
    assert 533000 <= trade_levels["breakout"] <= 570000


def test_stock_ai_analysis_uses_buy_language_only_for_actionable_stance():
    dashboard = _base_dashboard()
    dashboard["chart_analysis"] = {
        **dashboard["chart_analysis"],
        "score": 82,
        "stance": "추세 추종 관심",
        "trend": "상승 추세",
        "risks": [],
    }
    dashboard["momentum"] = {
        **dashboard["momentum"],
        "one_month_return": 18,
        "three_month_return": 35,
        "trading_value_change": 45,
    }
    dashboard["surprise"] = {"operating_profit_growth": 38}
    dashboard["valuation"] = {**dashboard["valuation"], "pbr_zscore": 0.4}

    payload = build_stock_ai_analysis(dashboard)
    strategy_text = " ".join(payload["strategy"])
    trade_levels = payload["trade_levels"]

    assert trade_levels["actionable"] is True
    assert trade_levels["entry_label"] == "1차 매수권"
    assert "1차 매수" in strategy_text


def test_stock_ai_analysis_explains_intraday_rebound_inside_weak_month():
    dashboard = _base_dashboard()
    dashboard["quote"] = {**dashboard["quote"], "change_rate": 4.92}
    dashboard["momentum"] = {**dashboard["momentum"], "one_month_return": -27.54}

    payload = build_stock_ai_analysis(dashboard)

    assert "오늘 +4.92% 강세" in payload["summary"]
    assert "급락 뒤 반등인지 추세 전환인지" in payload["summary"]
    assert payload["key_points"][0].startswith("오늘 +4.92% 강세")
