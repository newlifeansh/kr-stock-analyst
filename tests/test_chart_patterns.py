from datetime import date, timedelta
from types import SimpleNamespace

from app.services.chart_patterns import detect_chart_patterns
from app.services.stock_dashboard import _chart_analysis


def _price_rows(control_points: list[tuple[int, float]]):
    closes: list[float] = []
    for (start_index, start_price), (end_index, end_price) in zip(control_points, control_points[1:]):
        for index in range(start_index, end_index):
            ratio = (index - start_index) / (end_index - start_index)
            closes.append(start_price + (end_price - start_price) * ratio)
    closes.append(control_points[-1][1])
    return [
        SimpleNamespace(
            trade_date=date(2026, 1, 1) + timedelta(days=index),
            open=close - ((index % 3) - 1) * 0.15,
            high=close + 1.2,
            low=close - 1.2,
            close=close,
            volume=1_000 + index * 10,
        )
        for index, close in enumerate(closes)
    ]


def test_detects_confirmed_w_double_bottom_with_trade_levels():
    rows = _price_rows([(0, 110), (12, 80), (24, 102), (36, 81), (48, 108), (60, 112)])

    patterns = detect_chart_patterns(rows, limit=10)
    pattern = next(item for item in patterns if item["key"] == "double-bottom")

    assert pattern["name"] == "W형 이중바닥"
    assert pattern["direction"] == "bullish"
    assert pattern["status"] == "확인"
    assert pattern["trigger"] < pattern["target"]
    assert pattern["invalidation"] < pattern["trigger"]
    assert len(pattern["points"]) == 3


def test_detects_confirmed_m_double_top_with_trade_levels():
    rows = _price_rows([(0, 75), (12, 110), (24, 88), (36, 109), (48, 82), (60, 78)])

    patterns = detect_chart_patterns(rows, limit=10)
    pattern = next(item for item in patterns if item["key"] == "double-top")

    assert pattern["name"] == "M형 이중천장"
    assert pattern["direction"] == "bearish"
    assert pattern["status"] == "확인"
    assert pattern["target"] < pattern["trigger"]
    assert pattern["invalidation"] > pattern["trigger"]
    assert len(pattern["points"]) == 3


def test_pattern_output_is_bounded_and_excludes_invalid_candidates():
    rows = _price_rows([(0, 100), (20, 120), (40, 109), (60, 130), (80, 121), (100, 136)])

    patterns = detect_chart_patterns(rows, limit=3)

    assert len(patterns) <= 3
    assert all(pattern["status"] in {"확인", "후보"} for pattern in patterns)
    assert all(0 <= pattern["confidence"] <= 100 for pattern in patterns)


def test_chart_analysis_uses_live_quote_as_the_decision_reference():
    rows = _price_rows([(0, 100), (60, 120), (130, 130)])

    analysis = _chart_analysis(rows, current_price=160, current_volume=9_999)

    assert analysis["reference_price"] == 160
    assert analysis["daily_close"] == 130
    assert analysis["reference_price_source"] == "kis_live"
    assert analysis["distance_to_resistance"] is not None
    assert analysis["distance_to_resistance"] > 0
