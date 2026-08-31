from datetime import date, timedelta
from types import SimpleNamespace

from app import main as main_module
from app.schemas import DashboardChartPatternOut
from app.services.chart_patterns import detect_chart_patterns


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
    for row in rows[44:]:
        row.volume = 4_000

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
    for row in rows[44:]:
        row.volume = 4_000

    patterns = detect_chart_patterns(rows, limit=10)
    pattern = next(item for item in patterns if item["key"] == "double-top")

    assert pattern["name"] == "M형 이중천장"
    assert pattern["direction"] == "bearish"
    assert pattern["status"] == "확인"
    assert pattern["target"] < pattern["trigger"]
    assert pattern["invalidation"] > pattern["trigger"]
    assert len(pattern["points"]) == 3


def test_zero_ohlc_placeholder_falls_back_to_close_without_division_error():
    rows = _price_rows([(0, 75), (12, 110), (24, 88), (36, 109), (48, 82), (60, 78)])
    rows[24].open = 0
    rows[24].high = 0
    rows[24].low = 0

    patterns = detect_chart_patterns(rows, limit=10)

    assert any(item["key"] == "double-top" for item in patterns)
    assert all(
        point["price"] > 0
        for pattern in patterns
        for point in pattern["points"]
    )


def test_missing_latest_ohlc_is_not_misclassified_as_a_candle_pattern():
    rows = _price_rows([(0, 100), (20, 110), (40, 104), (60, 115)])
    rows[-1].open = None
    rows[-1].high = None
    rows[-1].low = None

    patterns = detect_chart_patterns(rows, limit=20)
    latest_index = len(rows) - 1

    assert not any(
        item["family"] == "캔들" and item["points"][-1]["index"] == latest_index
        for item in patterns
    )


def test_detects_multiple_patterns_across_recent_candles():
    rows = _price_rows([(0, 100), (20, 104), (40, 102), (60, 106)])
    rows[-4].open, rows[-4].high, rows[-4].low, rows[-4].close = 106, 107, 99, 100
    rows[-3].open, rows[-3].high, rows[-3].low, rows[-3].close = 99, 108, 98, 107
    rows[-2].open, rows[-2].high, rows[-2].low, rows[-2].close = 106, 112, 105, 111
    rows[-1].open, rows[-1].high, rows[-1].low, rows[-1].close = 112, 113, 104, 105

    patterns = detect_chart_patterns(rows, limit=20)
    keys = {item["key"] for item in patterns}

    assert "bullish-engulfing" in keys
    assert "bearish-engulfing" in keys


def test_detects_added_three_candle_reversal_pattern():
    rows = _price_rows([(0, 105), (45, 110), (57, 100), (60, 99)])
    rows[-3].open, rows[-3].high, rows[-3].low, rows[-3].close = 110, 111, 99, 100
    rows[-2].open, rows[-2].high, rows[-2].low, rows[-2].close = 99, 101, 97, 99
    rows[-1].open, rows[-1].high, rows[-1].low, rows[-1].close = 100, 109, 99, 107

    patterns = detect_chart_patterns(rows, limit=20)

    assert any(item["key"] == "morning-star" for item in patterns)


def test_pattern_output_is_bounded_and_excludes_invalid_candidates():
    rows = _price_rows([(0, 100), (20, 120), (40, 109), (60, 130), (80, 121), (100, 136)])

    patterns = detect_chart_patterns(rows, limit=3)

    assert len(patterns) <= 3
    assert all(pattern["status"] in {"확인", "후보"} for pattern in patterns)
    assert all(0 <= pattern["confidence"] <= 100 for pattern in patterns)


def test_recent_signal_is_ranked_before_an_older_candidate_structure():
    rows = _price_rows([(0, 110), (12, 80), (24, 102), (36, 81), (48, 108), (60, 112)])

    patterns = detect_chart_patterns(rows, limit=10)
    old_double_bottom = next(item for item in patterns if item["key"] == "double-bottom")

    assert patterns[0]["is_recent"] is True
    assert old_double_bottom["is_recent"] is False
    assert old_double_bottom["age_days"] > 10
    assert old_double_bottom["status"] == "후보"
    assert old_double_bottom["signal_date"] == old_double_bottom["points"][-1]["date"]
    assert old_double_bottom["window_days"] > 1


def test_classical_breakout_stays_candidate_without_supporting_volume():
    rows = _price_rows([(0, 110), (12, 80), (24, 102), (36, 81), (48, 108), (60, 112)])

    pattern = next(
        item for item in detect_chart_patterns(rows, limit=10)
        if item["key"] == "double-bottom"
    )

    assert pattern["status"] == "후보"
    assert pattern["score_kind"] == "pattern_fit"
    assert pattern["confirmation"]["price_crossed"] is True
    assert pattern["confirmation"]["volume_confirmed"] is False
    assert pattern["confirmation"]["required_volume_ratio"] == 1.15


def test_reversal_shape_is_rejected_without_a_preceding_trend():
    rows = _price_rows(
        [(0, 100), (11, 100), (12, 80), (24, 102), (36, 81), (48, 108), (60, 112)]
    )

    patterns = detect_chart_patterns(rows, limit=20)

    assert not any(item["key"] == "double-bottom" for item in patterns)


def test_falling_wedge_uses_visible_window_and_exposes_two_boundaries():
    rows = _price_rows(
        [
            (0, 125),
            (14, 115),
            (16, 110),
            (20, 90),
            (24, 104),
            (28, 87),
            (32, 98),
            (36, 84),
            (40, 92),
            (44, 96),
        ]
    )

    pattern = next(
        item for item in detect_chart_patterns(rows, limit=20)
        if item["key"] == "falling-wedge"
    )
    boundaries = pattern["boundaries"]

    assert boundaries["window_days"] <= 30
    assert boundaries["touch_count"] >= 5
    assert boundaries["upper_touch_count"] >= 2
    assert boundaries["lower_touch_count"] >= 2
    assert boundaries["upper"]["end_index"] == len(rows) - 1
    assert boundaries["lower"]["end_index"] == len(rows) - 1
    assert boundaries["upper"]["slope_per_day"] < boundaries["lower"]["slope_per_day"] < 0

    contract = DashboardChartPatternOut.model_validate(pattern).model_dump(mode="json")
    assert contract["score_kind"] == "pattern_fit"
    assert contract["boundaries"]["touch_count"] >= 5
    assert contract["confirmation"]["required_volume_ratio"] == "1.15"


def test_line_pattern_older_than_visible_30_sessions_is_not_reused():
    rows = _price_rows(
        [
            (0, 125),
            (14, 115),
            (16, 110),
            (20, 90),
            (24, 104),
            (28, 87),
            (32, 98),
            (36, 84),
            (40, 92),
            (44, 96),
            (75, 96),
        ]
    )

    patterns = detect_chart_patterns(rows, limit=20)

    assert not any(item["key"] == "falling-wedge" for item in patterns)


def test_cached_dashboard_patterns_are_upgraded_without_reusing_old_confirmation():
    rows = _price_rows(
        [
            (0, 125), (14, 115), (16, 110), (20, 90), (24, 104),
            (28, 87), (32, 98), (36, 84), (40, 92), (44, 96),
        ]
    )

    class FakeSession:
        def scalars(self, _statement):
            return list(reversed(rows))

    payload = {
        "chart_analysis": {
            "patterns": [{"key": "falling-wedge", "status": "확인"}],
        }
    }

    assert main_module._upgrade_cached_chart_patterns(payload, "005930", FakeSession()) is True
    assert payload["chart_analysis"]["pattern_schema_version"] == 2
    pattern = next(
        item for item in payload["chart_analysis"]["patterns"]
        if item["key"] == "falling-wedge"
    )
    assert pattern["status"] == "후보"
    assert pattern["boundaries"]["window_days"] <= 30
    assert pattern["confirmation"]["volume_confirmed"] is False
    assert main_module._upgrade_cached_chart_patterns(payload, "005930", FakeSession()) is False
