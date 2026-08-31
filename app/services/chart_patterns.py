from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable, Optional


RECENT_PATTERN_MAX_AGE = 10
PATTERN_DISPLAY_WINDOW = 30
MIN_CLASSICAL_FORMATION_DAYS = 8
MIN_LINE_TOUCHES = 5
MIN_LINE_SIDE_TOUCHES = 2
MIN_BREAKOUT_VOLUME_RATIO = 1.15
CHART_PATTERN_SCHEMA_VERSION = 2

_BULLISH_REVERSAL_KEYS = {
    "double-bottom",
    "inverse-head-shoulders",
    "triple-bottom",
    "rounding-bottom",
}
_BEARISH_REVERSAL_KEYS = {
    "double-top",
    "head-shoulders",
    "triple-top",
    "rounding-top",
}
_BULLISH_CANDLE_REVERSAL_KEYS = {
    "hammer",
    "bullish-engulfing",
    "bullish-harami",
    "piercing-line",
    "morning-star",
}
_BEARISH_CANDLE_REVERSAL_KEYS = {
    "shooting-star",
    "bearish-engulfing",
    "bearish-harami",
    "dark-cloud-cover",
    "evening-star",
}


@dataclass(frozen=True)
class PricePoint:
    index: int
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ohlc_complete: bool


@dataclass(frozen=True)
class Pivot:
    index: int
    date: str
    price: float
    kind: str


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _date_text(row: Any) -> str:
    value = getattr(row, "trade_date", None) or getattr(row, "date", None) or ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _normalise(rows: Iterable[Any]) -> list[PricePoint]:
    result: list[PricePoint] = []
    for row in rows:
        close = _number(getattr(row, "close", None))
        if close <= 0:
            continue
        raw_open = _number(getattr(row, "open", None))
        raw_high = _number(getattr(row, "high", None))
        raw_low = _number(getattr(row, "low", None))
        ohlc_complete = (
            raw_open > 0
            and raw_high > 0
            and raw_low > 0
            and raw_high >= max(raw_open, close)
            and raw_low <= min(raw_open, close)
        )
        open_price = raw_open or close
        high = raw_high or close
        low = raw_low or close
        if open_price <= 0:
            open_price = close
        if high <= 0:
            high = max(open_price, close)
        if low <= 0:
            low = min(open_price, close)
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        result.append(
            PricePoint(
                index=len(result),
                date=_date_text(row),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=max(0.0, _number(getattr(row, "volume", None))),
                ohlc_complete=ohlc_complete,
            )
        )
    return result


def _atr(rows: list[PricePoint], window: int = 14) -> float:
    if len(rows) < 2:
        return 0.0
    ranges: list[float] = []
    for index in range(max(1, len(rows) - window), len(rows)):
        row = rows[index]
        previous = rows[index - 1]
        ranges.append(max(row.high - row.low, abs(row.high - previous.close), abs(row.low - previous.close)))
    return mean(ranges) if ranges else 0.0


def _linear(values: list[tuple[int, float]]) -> tuple[float, float]:
    if len(values) < 2:
        return 0.0, values[0][1] if values else 0.0
    xs = [float(item[0]) for item in values]
    ys = [float(item[1]) for item in values]
    x_mean = mean(xs)
    y_mean = mean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0, y_mean
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    return slope, y_mean - slope * x_mean


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _point_indexes(pattern: dict[str, object]) -> list[int]:
    return sorted(
        {
            int(point["index"])
            for point in pattern.get("points", [])
            if isinstance(point, dict) and isinstance(point.get("index"), int)
        }
    )


def _trend_rate_before(
    rows: list[PricePoint],
    start_index: int,
    *,
    lookback: int,
    minimum_rows: int = 8,
) -> Optional[float]:
    prior = rows[max(0, start_index - lookback) : start_index]
    if len(prior) < minimum_rows or prior[0].close <= 0:
        return None
    return prior[-1].close / prior[0].close - 1


def _has_required_pattern_context(
    pattern: dict[str, object], rows: list[PricePoint]
) -> bool:
    """Reject reversal shapes that do not occur after the trend they reverse."""
    indexes = _point_indexes(pattern)
    start = indexes[0] if indexes else len(rows) - 1
    key = str(pattern.get("key") or "")
    family = str(pattern.get("family") or "")

    if family == "반전" and key in _BULLISH_REVERSAL_KEYS | _BEARISH_REVERSAL_KEYS:
        if indexes and indexes[-1] - indexes[0] + 1 < MIN_CLASSICAL_FORMATION_DAYS:
            return False
        trend_rate = _trend_rate_before(rows, start, lookback=20)
        required = -0.03 if key in _BULLISH_REVERSAL_KEYS else 0.03
        valid = (
            trend_rate is not None
            and ((required < 0 and trend_rate <= required) or (required > 0 and trend_rate >= required))
        )
        if valid:
            pattern["evidence"] = [
                *list(pattern.get("evidence") or []),
                f"선행 20일 흐름 {trend_rate * 100:+.1f}%",
            ]
        return valid

    if family == "캔들" and key in _BULLISH_CANDLE_REVERSAL_KEYS | _BEARISH_CANDLE_REVERSAL_KEYS:
        trend_rate = _trend_rate_before(rows, start, lookback=10, minimum_rows=6)
        required = -0.02 if key in _BULLISH_CANDLE_REVERSAL_KEYS else 0.02
        valid = (
            trend_rate is not None
            and ((required < 0 and trend_rate <= required) or (required > 0 and trend_rate >= required))
        )
        if valid:
            pattern["evidence"] = [
                *list(pattern.get("evidence") or []),
                f"선행 10일 흐름 {trend_rate * 100:+.1f}%",
            ]
        return valid

    return True


def _volume_ratio_at(rows: list[PricePoint], index: int, window: int = 20) -> Optional[float]:
    if not 0 <= index < len(rows) or rows[index].volume <= 0:
        return None
    prior = [item.volume for item in rows[max(0, index - window) : index] if item.volume > 0]
    if len(prior) < 5:
        return None
    average_volume = mean(prior)
    return rows[index].volume / average_volume if average_volume > 0 else None


def _boundary_price(pattern: dict[str, object], index: int) -> Optional[float]:
    boundaries = pattern.get("boundaries")
    if not isinstance(boundaries, dict):
        return None
    direction = str(pattern.get("direction") or "")
    boundary = boundaries.get("upper" if direction == "bullish" else "lower")
    if not isinstance(boundary, dict):
        return None
    start_index = boundary.get("start_index")
    start_price = boundary.get("start_price")
    slope = boundary.get("slope_per_day")
    if not all(isinstance(value, (int, float)) for value in (start_index, start_price, slope)):
        return None
    return float(start_price) + float(slope) * (index - int(start_index))


def _apply_breakout_confirmation(
    pattern: dict[str, object], rows: list[PricePoint]
) -> dict[str, object]:
    """Require a close beyond the boundary and supporting volume for confirmation."""
    if str(pattern.get("family") or "") == "캔들":
        return pattern
    direction = str(pattern.get("direction") or "")
    trigger = pattern.get("trigger")
    indexes = _point_indexes(pattern)
    if direction not in {"bullish", "bearish"} or not isinstance(trigger, (int, float)):
        return pattern
    if not indexes:
        pattern["status"] = "후보"
        pattern["confirmation"] = {
            "price_crossed": False,
            "volume_confirmed": False,
            "volume_ratio": None,
            "required_volume_ratio": MIN_BREAKOUT_VOLUME_RATIO,
            "crossing_date": None,
            "crossing_index": None,
        }
        return pattern

    formation_end = indexes[-1]

    def threshold(index: int) -> float:
        return _boundary_price(pattern, index) or float(trigger)

    def crossed(row: PricePoint) -> bool:
        level = threshold(row.index)
        return row.close > level if direction == "bullish" else row.close < level

    current_crossed = crossed(rows[-1])
    crossing = next(
        (row for row in rows[min(len(rows), formation_end + 1) :] if crossed(row)),
        None,
    )
    volume_ratio = _volume_ratio_at(rows, crossing.index) if crossing is not None else None
    volume_confirmed = volume_ratio is not None and volume_ratio >= MIN_BREAKOUT_VOLUME_RATIO
    confirmed = current_crossed and crossing is not None and volume_confirmed
    pattern["status"] = "확인" if confirmed else "후보"
    pattern["confirmation"] = {
        "price_crossed": bool(current_crossed and crossing is not None),
        "volume_confirmed": volume_confirmed,
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "required_volume_ratio": MIN_BREAKOUT_VOLUME_RATIO,
        "crossing_date": crossing.date if crossing is not None else None,
        "crossing_index": crossing.index if crossing is not None else None,
    }
    if current_crossed and crossing is not None:
        volume_text = (
            f"돌파 거래량 {volume_ratio:.2f}배"
            if volume_ratio is not None
            else "돌파 거래량 확인 불가"
        )
        pattern["evidence"] = [
            *list(pattern.get("evidence") or []),
            volume_text if confirmed else f"{volume_text} · 확인 대기",
        ]
    return pattern


def _line_fit_quality(
    points: list[Pivot],
    slope: float,
    intercept: float,
    *,
    base: float,
    atr: float,
) -> tuple[bool, float, float]:
    errors = [abs(item.price - (slope * item.index + intercept)) for item in points]
    if not errors:
        return False, 0.0, 0.0
    rmse = (sum(error * error for error in errors) / len(errors)) ** 0.5
    tolerance = max(base * 0.015, atr * 0.9)
    maximum_tolerance = max(base * 0.035, atr * 1.8)
    valid = rmse <= tolerance and max(errors) <= maximum_tolerance
    quality = _clamp(1 - rmse / max(tolerance * 1.5, 1))
    return valid, quality, rmse / base if base > 0 else 1.0


def _pivots(rows: list[PricePoint], window: int = 3) -> list[Pivot]:
    if len(rows) < window * 2 + 1:
        return []
    atr = _atr(rows)
    min_move = max(atr * 0.55, rows[-1].close * 0.012)
    candidates: list[Pivot] = []
    for index in range(window, len(rows) - window):
        span = rows[index - window : index + window + 1]
        row = rows[index]
        if row.high >= max(item.high for item in span) and row.high - min(item.low for item in span) >= min_move:
            candidates.append(Pivot(index, row.date, row.high, "high"))
        if row.low <= min(item.low for item in span) and max(item.high for item in span) - row.low >= min_move:
            candidates.append(Pivot(index, row.date, row.low, "low"))
    candidates.sort(key=lambda item: (item.index, 0 if item.kind == "low" else 1))
    compressed: list[Pivot] = []
    for pivot in candidates:
        if not compressed:
            compressed.append(pivot)
            continue
        previous = compressed[-1]
        if pivot.kind == previous.kind:
            more_extreme = pivot.price > previous.price if pivot.kind == "high" else pivot.price < previous.price
            if more_extreme:
                compressed[-1] = pivot
            continue
        if pivot.index - previous.index < 2:
            continue
        compressed.append(pivot)
    return compressed


def _point(pivot: Pivot) -> dict[str, object]:
    return {"index": pivot.index, "date": pivot.date, "price": round(pivot.price), "kind": pivot.kind}


def _status(direction: str, latest: float, trigger: float, invalidation: float) -> str:
    if direction == "bullish":
        if latest <= invalidation:
            return "무효"
        return "확인" if latest > trigger else "후보"
    if latest >= invalidation:
        return "무효"
    return "확인" if latest < trigger else "후보"


def _pattern(
    *,
    key: str,
    name: str,
    family: str,
    direction: str,
    confidence: float,
    status: str,
    points: list[Pivot],
    trigger: Optional[float],
    target: Optional[float],
    invalidation: Optional[float],
    summary: str,
    evidence: list[str],
) -> dict[str, object]:
    return {
        "key": key,
        "name": name,
        "family": family,
        "direction": direction,
        "confidence": round(max(0, min(100, confidence)), 1),
        "score_kind": "pattern_fit",
        "status": status,
        "points": [_point(item) for item in points],
        "trigger": round(trigger) if trigger else None,
        "target": round(target) if target else None,
        "invalidation": round(invalidation) if invalidation else None,
        "summary": summary,
        "evidence": evidence,
    }


def _annotate_pattern_recency(
    pattern: dict[str, object], rows: list[PricePoint]
) -> dict[str, object]:
    """Attach the date when a pattern became actionable and how old it is.

    Classical patterns can start well before the latest candle. Ranking them by
    confidence alone made an old, already-confirmed shape look like today's
    signal. The actionable date is the first trigger crossing after the final
    pattern point; candidates use their latest pattern point.
    """
    if not rows:
        pattern.update({"signal_date": None, "age_days": 0, "window_days": 0, "is_recent": False})
        return pattern

    point_indexes = _point_indexes(pattern)
    formation_start = point_indexes[0] if point_indexes else len(rows) - 1
    formation_end = point_indexes[-1] if point_indexes else len(rows) - 1
    signal_index = formation_end
    trigger = pattern.get("trigger")
    direction = str(pattern.get("direction") or "")

    confirmation = pattern.get("confirmation")
    crossing_index = (
        confirmation.get("crossing_index")
        if isinstance(confirmation, dict)
        else None
    )
    if pattern.get("status") == "확인" and isinstance(crossing_index, int):
        signal_index = crossing_index
    elif pattern.get("status") == "확인" and isinstance(trigger, (int, float)):
        for row in rows[min(len(rows), formation_end + 1) :]:
            crossed = (direction == "bullish" and row.close > float(trigger)) or (
                direction == "bearish" and row.close < float(trigger)
            )
            if crossed:
                signal_index = row.index
                break

    signal_index = max(0, min(signal_index, len(rows) - 1))
    age_days = max(0, rows[-1].index - signal_index)
    pattern.update(
        {
            "signal_date": rows[signal_index].date,
            "age_days": age_days,
            "window_days": max(1, formation_end - formation_start + 1),
            "is_recent": age_days <= RECENT_PATTERN_MAX_AGE,
        }
    )
    return pattern


def _reversal_patterns(rows: list[PricePoint], pivots: list[Pivot], atr: float) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    latest = rows[-1].close
    recent = pivots[-12:]
    for index in range(len(recent) - 2):
        first, middle, last = recent[index : index + 3]
        if last.index < len(rows) - 100:
            continue
        if min(first.price, middle.price, last.price) <= 0:
            continue
        if [first.kind, middle.kind, last.kind] == ["low", "high", "low"]:
            tolerance = abs(first.price - last.price) / max(first.price, last.price)
            depth = middle.price - mean([first.price, last.price])
            if tolerance <= 0.065 and depth / middle.price >= 0.035:
                invalidation = min(first.price, last.price) - atr
                status = _status("bullish", latest, middle.price, invalidation)
                confidence = 68 + (1 - tolerance / 0.065) * 16
                found.append(_pattern(
                    key="double-bottom", name="W형 이중바닥", family="반전", direction="bullish",
                    confidence=confidence, status=status, points=[first, middle, last], trigger=middle.price,
                    target=middle.price + depth, invalidation=invalidation,
                    summary="두 저점이 비슷한 가격에서 지지됐습니다. 중간 고점 돌파 여부가 전환의 핵심입니다.",
                    evidence=[f"저점 차이 {tolerance * 100:.1f}%", f"전환 기준 {middle.price:,.0f}원"],
                ))
        if [first.kind, middle.kind, last.kind] == ["high", "low", "high"]:
            tolerance = abs(first.price - last.price) / max(first.price, last.price)
            height = mean([first.price, last.price]) - middle.price
            if tolerance <= 0.065 and height / middle.price >= 0.035:
                invalidation = max(first.price, last.price) + atr
                status = _status("bearish", latest, middle.price, invalidation)
                confidence = 68 + (1 - tolerance / 0.065) * 16
                found.append(_pattern(
                    key="double-top", name="M형 이중천장", family="반전", direction="bearish",
                    confidence=confidence, status=status, points=[first, middle, last], trigger=middle.price,
                    target=max(1, middle.price - height), invalidation=invalidation,
                    summary="두 고점이 비슷한 가격에서 막혔습니다. 중간 저점 이탈 여부를 확인해야 합니다.",
                    evidence=[f"고점 차이 {tolerance * 100:.1f}%", f"이탈 기준 {middle.price:,.0f}원"],
                ))

    for index in range(max(0, len(recent) - 8), len(recent) - 4):
        points = recent[index : index + 5]
        kinds = [item.kind for item in points]
        if kinds == ["high", "low", "high", "low", "high"]:
            left, low1, head, low2, right = points
            shoulder_gap = abs(left.price - right.price) / max(left.price, right.price)
            if head.price > max(left.price, right.price) * 1.035 and shoulder_gap <= 0.09:
                neckline = mean([low1.price, low2.price])
                invalidation = head.price + atr
                status = _status("bearish", latest, neckline, invalidation)
                found.append(_pattern(
                    key="head-shoulders", name="헤드앤숄더", family="반전", direction="bearish",
                    confidence=72 - shoulder_gap * 60, status=status,
                    points=points, trigger=neckline, target=max(1, neckline - (head.price - neckline)),
                    invalidation=invalidation, summary="가운데 고점이 가장 높고 양쪽 어깨가 비슷합니다. 넥라인 이탈 시 약세 전환으로 봅니다.",
                    evidence=[f"어깨 차이 {shoulder_gap * 100:.1f}%", f"넥라인 {neckline:,.0f}원"],
                ))
            peak_average = mean([left.price, head.price, right.price])
            peak_spread = (max(left.price, head.price, right.price) - min(left.price, head.price, right.price)) / peak_average
            trough = mean([low1.price, low2.price])
            if peak_spread <= 0.055 and (peak_average - trough) / trough >= 0.035:
                invalidation = max(left.price, head.price, right.price) + atr
                status = _status("bearish", latest, trough, invalidation)
                found.append(_pattern(
                    key="triple-top", name="삼중천장", family="반전", direction="bearish",
                    confidence=72 - peak_spread * 80, status=status,
                    points=points, trigger=trough, target=max(1, trough - (peak_average - trough)),
                    invalidation=invalidation, summary="세 고점이 비슷한 가격에서 반복해서 막혔습니다. 두 저점의 평균 이탈이 하락 전환 기준입니다.",
                    evidence=[f"고점 편차 {peak_spread * 100:.1f}%", f"이탈 기준 {trough:,.0f}원"],
                ))
        if kinds == ["low", "high", "low", "high", "low"]:
            left, high1, head, high2, right = points
            shoulder_gap = abs(left.price - right.price) / max(left.price, right.price)
            if head.price < min(left.price, right.price) * 0.965 and shoulder_gap <= 0.09:
                neckline = mean([high1.price, high2.price])
                invalidation = head.price - atr
                status = _status("bullish", latest, neckline, invalidation)
                found.append(_pattern(
                    key="inverse-head-shoulders", name="역헤드앤숄더", family="반전", direction="bullish",
                    confidence=72 - shoulder_gap * 60, status=status,
                    points=points, trigger=neckline, target=neckline + (neckline - head.price),
                    invalidation=invalidation, summary="가운데 저점이 가장 낮고 양쪽 어깨가 비슷합니다. 넥라인 돌파 시 반전 가능성이 커집니다.",
                    evidence=[f"어깨 차이 {shoulder_gap * 100:.1f}%", f"넥라인 {neckline:,.0f}원"],
                ))
            trough_average = mean([left.price, head.price, right.price])
            trough_spread = (max(left.price, head.price, right.price) - min(left.price, head.price, right.price)) / trough_average
            peak = mean([high1.price, high2.price])
            if trough_spread <= 0.055 and (peak - trough_average) / peak >= 0.035:
                invalidation = min(left.price, head.price, right.price) - atr
                status = _status("bullish", latest, peak, invalidation)
                found.append(_pattern(
                    key="triple-bottom", name="삼중바닥", family="반전", direction="bullish",
                    confidence=72 - trough_spread * 80, status=status,
                    points=points, trigger=peak, target=peak + (peak - trough_average),
                    invalidation=invalidation, summary="세 저점이 비슷한 가격에서 반복해서 지지됐습니다. 두 고점의 평균 돌파가 상승 전환 기준입니다.",
                    evidence=[f"저점 편차 {trough_spread * 100:.1f}%", f"전환 기준 {peak:,.0f}원"],
                ))
    return found


def _consolidation_patterns(rows: list[PricePoint], pivots: list[Pivot], atr: float) -> list[dict[str, object]]:
    # The product shows the detected structure on a 30-session chart. Keep the
    # detector on the same window so every claimed touch is visible to users.
    recent = [item for item in pivots if item.index >= len(rows) - PATTERN_DISPLAY_WINDOW]
    highs = [item for item in recent if item.kind == "high"][-5:]
    lows = [item for item in recent if item.kind == "low"][-5:]
    if (
        len(highs) < MIN_LINE_SIDE_TOUCHES
        or len(lows) < MIN_LINE_SIDE_TOUCHES
        or len(highs) + len(lows) < MIN_LINE_TOUCHES
    ):
        return []
    high_slope, high_intercept = _linear([(item.index, item.price) for item in highs])
    low_slope, low_intercept = _linear([(item.index, item.price) for item in lows])
    base = rows[-1].close
    high_fit_valid, high_fit_quality, high_rmse = _line_fit_quality(
        highs,
        high_slope,
        high_intercept,
        base=base,
        atr=atr,
    )
    low_fit_valid, low_fit_quality, low_rmse = _line_fit_quality(
        lows,
        low_slope,
        low_intercept,
        base=base,
        atr=atr,
    )
    if not high_fit_valid or not low_fit_valid:
        return []
    high_norm = high_slope / base
    low_norm = low_slope / base
    start = min(highs[0].index, lows[0].index)
    end = len(rows) - 1
    gap_start = (high_slope * start + high_intercept) - (low_slope * start + low_intercept)
    high_end = high_slope * end + high_intercept
    low_end = low_slope * end + low_intercept
    gap_end = high_end - low_end
    converging = gap_start > 0 and 0 < gap_end < gap_start * 0.78
    containment_tolerance = max(base * 0.012, atr * 0.75)
    formation_rows = rows[start : end + 1]
    boundary_violations = sum(
        1
        for row in formation_rows
        if (
            row.high > high_slope * row.index + high_intercept + containment_tolerance
            or row.low < low_slope * row.index + low_intercept - containment_tolerance
        )
    )
    containment_rate = 1 - boundary_violations / max(1, len(formation_rows))
    if containment_rate < 0.78:
        return []
    flat = 0.0008
    slope = 0.00055
    key = name = direction = summary = ""
    if abs(high_norm) <= flat and low_norm >= slope and converging:
        key, name, direction = "ascending-triangle", "상승 삼각수렴", "bullish"
        summary = "고점은 일정하고 저점이 높아집니다. 상단 돌파와 거래량 증가를 함께 확인합니다."
    elif high_norm <= -slope and abs(low_norm) <= flat and converging:
        key, name, direction = "descending-triangle", "하락 삼각수렴", "bearish"
        summary = "저점은 일정하고 고점이 낮아집니다. 하단 이탈 여부를 우선 확인합니다."
    elif high_norm <= -slope and low_norm >= slope and converging:
        key, name = "symmetrical-triangle", "대칭 삼각수렴"
        direction = "bullish" if rows[-1].close >= mean([high_end, low_end]) else "bearish"
        summary = "고점과 저점이 함께 좁아집니다. 수렴 구간을 벗어나는 방향이 다음 추세의 기준입니다."
    elif high_norm > slope and low_norm > slope and converging:
        key, name, direction = "rising-wedge", "상승 쐐기", "bearish"
        summary = "상승 폭이 좁아지는 쐐기입니다. 하단 추세선 이탈 시 조정 위험이 커집니다."
    elif high_norm < -slope and low_norm < -slope and converging:
        key, name, direction = "falling-wedge", "하락 쐐기", "bullish"
        summary = "하락 폭이 좁아지는 쐐기입니다. 상단 추세선 돌파 시 반전 후보가 됩니다."
    elif abs(high_norm) <= flat and abs(low_norm) <= flat:
        key, name = "rectangle", "박스권"
        direction = "bullish" if rows[-1].close >= mean([high_end, low_end]) else "bearish"
        summary = "상단과 하단이 평행한 횡보 구간입니다. 박스권 이탈 전까지 방향을 단정하지 않습니다."
    elif abs(high_norm - low_norm) <= 0.0008:
        direction = "bullish" if mean([high_norm, low_norm]) > 0 else "bearish"
        key = "rising-channel" if direction == "bullish" else "falling-channel"
        name = "상승 채널" if direction == "bullish" else "하락 채널"
        summary = "고점과 저점이 비슷한 기울기로 이동합니다. 채널 경계 이탈 여부가 추세 변화 기준입니다."
    if not key:
        return []
    trigger = high_end if direction == "bullish" else low_end
    invalidation = low_end - atr if direction == "bullish" else high_end + atr
    status = _status(direction, rows[-1].close, trigger, invalidation)
    height = max(gap_end, atr * 2)
    target = trigger + height if direction == "bullish" else max(1, trigger - height)
    gap_ratio = gap_end / gap_start
    fit_quality = mean([high_fit_quality, low_fit_quality])
    convergence_quality = _clamp((0.78 - gap_ratio) / 0.58)
    confidence = (
        50
        + min(14, (len(highs) + len(lows) - 4) * 3.5)
        + fit_quality * 20
        + convergence_quality * 8
        + containment_rate * 8
    )
    pattern = _pattern(
        key=key, name=name, family="수렴·추세", direction=direction, confidence=confidence,
        status=status, points=sorted(highs + lows, key=lambda item: item.index), trigger=trigger,
        target=target, invalidation=invalidation, summary=summary,
        evidence=[
            f"최근 {end - start + 1}거래일 경계 접점 {len(highs) + len(lows)}개",
            f"상단 기울기 {high_norm * 100:.2f}%/일 · 오차 {high_rmse * 100:.2f}%",
            f"하단 기울기 {low_norm * 100:.2f}%/일 · 오차 {low_rmse * 100:.2f}%",
        ],
    )
    pattern["score_kind"] = "pattern_fit"
    pattern["boundaries"] = {
        "window_days": end - start + 1,
        "touch_count": len(highs) + len(lows),
        "upper_touch_count": len(highs),
        "lower_touch_count": len(lows),
        "containment_rate": round(containment_rate, 3),
        "upper": {
            "start_index": start,
            "end_index": end,
            "start_date": rows[start].date,
            "end_date": rows[end].date,
            "start_price": round(high_slope * start + high_intercept),
            "end_price": round(high_end),
            "slope_per_day": round(high_slope, 6),
        },
        "lower": {
            "start_index": start,
            "end_index": end,
            "start_date": rows[start].date,
            "end_date": rows[end].date,
            "start_price": round(low_slope * start + low_intercept),
            "end_price": round(low_end),
            "slope_per_day": round(low_slope, 6),
        },
    }
    return [pattern]


def _continuation_patterns(rows: list[PricePoint], pivots: list[Pivot], atr: float) -> list[dict[str, object]]:
    if len(rows) < 35:
        return []
    found: list[dict[str, object]] = []
    impulse_start = rows[-30].close
    impulse_end = rows[-12].close
    impulse = impulse_end / impulse_start - 1 if impulse_start else 0
    consolidation = rows[-12:]
    range_rate = (max(item.high for item in consolidation) - min(item.low for item in consolidation)) / impulse_end
    slope, _ = _linear([(item.index, item.close) for item in consolidation])
    if abs(impulse) >= 0.10 and range_rate <= 0.13:
        direction = "bullish" if impulse > 0 else "bearish"
        counter = slope < 0 if direction == "bullish" else slope > 0
        name = "상승 깃발" if direction == "bullish" else "하락 깃발"
        key = "bull-flag" if direction == "bullish" else "bear-flag"
        if abs(slope / impulse_end) < 0.0008:
            name = "페넌트"
            key = "pennant"
        trigger = max(item.high for item in consolidation) if direction == "bullish" else min(item.low for item in consolidation)
        invalidation = min(item.low for item in consolidation) - atr if direction == "bullish" else max(item.high for item in consolidation) + atr
        status = _status(direction, rows[-1].close, trigger, invalidation)
        found.append(_pattern(
            key=key, name=name, family="지속", direction=direction,
            confidence=64 + (8 if counter else 0), status=status,
            points=[item for item in pivots if item.index >= len(rows) - 30], trigger=trigger,
            target=trigger * (1 + impulse) if direction == "bullish" else max(1, trigger * (1 + impulse)),
            invalidation=invalidation,
            summary="강한 선행 움직임 뒤 짧은 조정이 이어집니다. 조정 구간 이탈과 거래량을 확인합니다.",
            evidence=[f"선행 움직임 {impulse * 100:+.1f}%", f"조정 폭 {range_rate * 100:.1f}%"],
        ))

    window = rows[-160:] if len(rows) >= 80 else rows
    if len(window) >= 60:
        left = max(window[: max(8, len(window) // 4)], key=lambda item: item.high)
        bottom = min(window[len(window) // 5 : len(window) * 4 // 5], key=lambda item: item.low)
        right = max(window[len(window) * 3 // 5 :], key=lambda item: item.high)
        rim_gap = abs(left.high - right.high) / max(left.high, right.high)
        depth = mean([left.high, right.high]) - bottom.low
        if left.index < bottom.index < right.index and rim_gap <= 0.09 and depth / mean([left.high, right.high]) >= 0.14:
            trigger = mean([left.high, right.high])
            handle_rows = [item for item in rows if item.index > right.index]
            handle_low = min((item.low for item in handle_rows), default=right.low)
            if handle_low >= trigger * 0.86:
                invalidation = handle_low - atr
                status = _status("bullish", rows[-1].close, trigger, invalidation)
                cup_points = [
                    Pivot(left.index, left.date, left.high, "high"),
                    Pivot(bottom.index, bottom.date, bottom.low, "low"),
                    Pivot(right.index, right.date, right.high, "high"),
                ]
                found.append(_pattern(
                    key="cup-handle", name="컵앤핸들", family="지속", direction="bullish",
                    confidence=70 - rim_gap * 40, status=status,
                    points=cup_points, trigger=trigger, target=trigger + depth, invalidation=invalidation,
                    summary="완만한 바닥 뒤 이전 고점에 복귀하고 짧은 손잡이 조정이 나타났습니다.",
                    evidence=[f"컵 깊이 {depth / trigger * 100:.1f}%", f"림 차이 {rim_gap * 100:.1f}%"],
                ))
    return found


def _rounding_pattern(rows: list[PricePoint], pivots: list[Pivot], atr: float) -> list[dict[str, object]]:
    if len(rows) < 75:
        return []
    window = rows[-90:]
    third = len(window) // 3
    left = mean(item.close for item in window[:third])
    middle = mean(item.close for item in window[third : third * 2])
    right = mean(item.close for item in window[third * 2 :])
    side_gap = abs(left - right) / max(left, right)
    if side_gap > 0.14:
        return []
    if middle < min(left, right) * 0.92:
        direction, key, name = "bullish", "rounding-bottom", "라운딩 바닥"
        trigger, invalidation = max(left, right), middle - atr
        summary = "가격 평균이 완만한 U자형으로 회복됩니다. 이전 평균 가격 회복이 확인 기준입니다."
    elif middle > max(left, right) * 1.08:
        direction, key, name = "bearish", "rounding-top", "라운딩 천장"
        trigger, invalidation = min(left, right), middle + atr
        summary = "가격 평균이 완만한 역U자형으로 둔화됩니다. 이전 평균 가격 이탈을 확인합니다."
    else:
        return []
    status = _status(direction, rows[-1].close, trigger, invalidation)
    depth = abs(trigger - middle)
    target = trigger + depth if direction == "bullish" else max(1, trigger - depth)
    return [_pattern(
        key=key, name=name, family="반전", direction=direction, confidence=64,
        status=status, points=[item for item in pivots if item.index >= len(rows) - 90], trigger=trigger,
        target=target, invalidation=invalidation, summary=summary,
        evidence=[f"중앙부 괴리 {abs(middle / mean([left, right]) - 1) * 100:.1f}%"],
    )]


def _candlestick_pattern_at_end(rows: list[PricePoint], atr: float) -> list[dict[str, object]]:
    if len(rows) < 3 or not rows[-1].ohlc_complete:
        return []
    previous, latest = rows[-2:]
    found: list[dict[str, object]] = []
    body = abs(latest.close - latest.open)
    span = max(latest.high - latest.low, 1)
    upper = latest.high - max(latest.open, latest.close)
    lower = min(latest.open, latest.close) - latest.low
    direction = "bullish" if latest.close >= latest.open else "bearish"
    name = key = summary = ""
    if body / span <= 0.12:
        key, name = "doji", "도지"
        direction = "neutral"
        summary = "시가와 종가가 가까워 매수·매도 힘이 균형을 이룹니다. 다음 봉의 방향 확인이 필요합니다."
    elif lower >= body * 2.2 and upper <= body * 0.8:
        key, name, direction = "hammer", "망치형", "bullish"
        summary = "아래꼬리가 길어 저가 매수 유입이 확인됩니다. 다음 봉의 고점 돌파를 확인합니다."
    elif upper >= body * 2.2 and lower <= body * 0.8:
        key, name, direction = "shooting-star", "유성형", "bearish"
        summary = "위꼬리가 길어 고가 매도 압력이 확인됩니다. 다음 봉의 저점 이탈을 확인합니다."
    elif previous.ohlc_complete and previous.close < previous.open and latest.close > latest.open and latest.open <= previous.close and latest.close >= previous.open:
        key, name, direction = "bullish-engulfing", "상승 장악형", "bullish"
        summary = "양봉 몸통이 직전 음봉을 감쌌습니다. 단기 매수 전환 후보입니다."
    elif previous.ohlc_complete and previous.close > previous.open and latest.close < latest.open and latest.open >= previous.close and latest.close <= previous.open:
        key, name, direction = "bearish-engulfing", "하락 장악형", "bearish"
        summary = "음봉 몸통이 직전 양봉을 감쌌습니다. 단기 매도 전환 후보입니다."
    if key:
        trigger = latest.high if direction != "bearish" else latest.low
        invalidation = latest.low - atr * 0.3 if direction != "bearish" else latest.high + atr * 0.3
        found.append(_pattern(
            key=key, name=name, family="캔들", direction=direction, confidence=58 if direction == "neutral" else 66,
            status="후보", points=[Pivot(latest.index, latest.date, latest.close, "close")], trigger=trigger,
            target=None, invalidation=invalidation, summary=summary,
            evidence=[f"몸통 비율 {body / span * 100:.1f}%"],
        ))
    return found


def _additional_candlestick_patterns(
    rows: list[PricePoint], atr: float, lookback: int
) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    complete_indexes = [item.index for item in rows[-30:] if item.ohlc_complete][-lookback:]
    if not complete_indexes:
        return found

    def add(
        key: str,
        name: str,
        direction: str,
        confidence: float,
        summary: str,
        candle_rows: list[PricePoint],
        evidence: str,
    ) -> None:
        latest = candle_rows[-1]
        age = len(rows) - 1 - latest.index
        trigger = latest.high if direction != "bearish" else latest.low
        invalidation = latest.low - atr * 0.3 if direction != "bearish" else latest.high + atr * 0.3
        found.append(_pattern(
            key=key,
            name=name,
            family="캔들",
            direction=direction,
            confidence=confidence - age * 2,
            status="후보",
            points=[Pivot(item.index, item.date, item.close, "close") for item in candle_rows],
            trigger=trigger,
            target=None,
            invalidation=invalidation,
            summary=summary,
            evidence=[evidence, f"{age}거래일 전" if age else "최신 봉"],
        ))

    start = max(2, complete_indexes[0])
    for index in range(start, len(rows)):
        latest = rows[index]
        if not latest.ohlc_complete:
            continue
        body = abs(latest.close - latest.open)
        span = max(latest.high - latest.low, 1)
        upper = latest.high - max(latest.open, latest.close)
        lower = min(latest.open, latest.close) - latest.low
        bullish = latest.close > latest.open
        bearish = latest.close < latest.open
        previous = rows[index - 1]

        if previous.ohlc_complete:
            previous_body = abs(previous.close - previous.open)
            if (
                previous.close < previous.open
                and bullish
                and body < previous_body * 0.8
                and latest.open >= previous.close
                and latest.close <= previous.open
            ):
                add(
                    "bullish-harami", "상승 하라미", "bullish", 64,
                    "작은 양봉이 직전 큰 음봉 몸통 안에 있어 하락세 둔화 후보입니다.",
                    [previous, latest], "직전 음봉 내부에 양봉 몸통",
                )
            elif (
                previous.close > previous.open
                and bearish
                and body < previous_body * 0.8
                and latest.open <= previous.close
                and latest.close >= previous.open
            ):
                add(
                    "bearish-harami", "하락 하라미", "bearish", 64,
                    "작은 음봉이 직전 큰 양봉 몸통 안에 있어 상승세 둔화 후보입니다.",
                    [previous, latest], "직전 양봉 내부에 음봉 몸통",
                )
            elif previous.close < previous.open and bullish:
                midpoint = mean([previous.open, previous.close])
                if latest.open < previous.close and midpoint < latest.close < previous.open:
                    add(
                        "piercing-line", "관통형", "bullish", 68,
                        "양봉이 직전 음봉 몸통의 절반 이상을 회복해 반등 후보가 됩니다.",
                        [previous, latest], "직전 음봉 중간값 회복",
                    )
            elif previous.close > previous.open and bearish:
                midpoint = mean([previous.open, previous.close])
                if latest.open > previous.close and previous.open < latest.close < midpoint:
                    add(
                        "dark-cloud-cover", "흑운형", "bearish", 68,
                        "음봉이 직전 양봉 몸통의 절반 아래로 밀려 조정 후보가 됩니다.",
                        [previous, latest], "직전 양봉 중간값 이탈",
                    )

        first, middle = rows[index - 2], rows[index - 1]
        if first.ohlc_complete and middle.ohlc_complete:
            first_body = abs(first.close - first.open)
            middle_body = abs(middle.close - middle.open)
            small_middle = middle_body <= max(first_body, body) * 0.45
            if first.close < first.open and bullish and small_middle and latest.close >= mean([first.open, first.close]):
                add(
                    "morning-star", "샛별형", "bullish", 74,
                    "큰 음봉 뒤 작은 몸통과 회복 양봉이 이어져 상승 반전 후보가 됩니다.",
                    [first, middle, latest], "3거래일 상승 반전 구조",
                )
            elif first.close > first.open and bearish and small_middle and latest.close <= mean([first.open, first.close]):
                add(
                    "evening-star", "석별형", "bearish", 74,
                    "큰 양봉 뒤 작은 몸통과 하락 음봉이 이어져 하락 반전 후보가 됩니다.",
                    [first, middle, latest], "3거래일 하락 반전 구조",
                )

        body_ratio = body / span
        if 0.12 < body_ratio <= 0.3 and upper >= body and lower >= body:
            add(
                "spinning-top", "팽이형", "neutral", 55,
                "몸통은 작고 위아래 꼬리가 있어 단기 방향성이 약해진 구간입니다.",
                [latest], f"몸통 비율 {body_ratio * 100:.1f}%",
            )
        elif body_ratio >= 0.8 and upper / span <= 0.1 and lower / span <= 0.1 and (bullish or bearish):
            direction = "bullish" if bullish else "bearish"
            add(
                f"{direction}-marubozu", "상승 장대봉" if bullish else "하락 장대봉", direction, 65,
                "꼬리가 짧고 몸통이 길어 한쪽 방향의 압력이 강한 구간입니다.",
                [latest], f"몸통 비율 {body_ratio * 100:.1f}%",
            )

    return found


def _candlestick_patterns(rows: list[PricePoint], atr: float, lookback: int = 8) -> list[dict[str, object]]:
    """Scan several recent, complete OHLC bars instead of only the latest row."""
    found: list[dict[str, object]] = []
    complete_ends = [item.index + 1 for item in rows[-30:] if item.ohlc_complete][-lookback:]
    for end in complete_ends:
        patterns = _candlestick_pattern_at_end(rows[:end], atr)
        age = len(rows) - end
        for pattern in patterns:
            pattern["confidence"] = round(max(35, float(pattern["confidence"]) - age * 2), 1)
            pattern["evidence"] = [
                *list(pattern.get("evidence") or []),
                f"{age}거래일 전" if age else "최신 봉",
            ]
        found.extend(patterns)
    found.extend(_additional_candlestick_patterns(rows, atr, lookback))
    return found


def detect_chart_patterns(price_rows: Iterable[Any], limit: int = 8) -> list[dict[str, object]]:
    """Detect classical chart patterns without future data or model-generated guesses."""
    rows = _normalise(price_rows)
    if len(rows) < 20:
        return []
    pivots = _pivots(rows)
    atr = _atr(rows)
    candidates = [
        *_reversal_patterns(rows, pivots, atr),
        *_consolidation_patterns(rows, pivots, atr),
        *_continuation_patterns(rows, pivots, atr),
        *_rounding_pattern(rows, pivots, atr),
        *_candlestick_patterns(rows, atr),
    ]
    candidates = [item for item in candidates if item["status"] != "무효"]
    candidates = [item for item in candidates if _has_required_pattern_context(item, rows)]
    candidates = [_apply_breakout_confirmation(item, rows) for item in candidates]
    candidates = [_annotate_pattern_recency(item, rows) for item in candidates]
    status_rank = {"확인": 2, "후보": 1}
    candidates.sort(
        key=lambda item: (
            bool(item["is_recent"]),
            float(item["confidence"])
            + status_rank.get(str(item["status"]), 0) * 4
            - min(30, int(item["age_days"])) * 2.5,
            -int(item["age_days"]),
        ),
        reverse=True,
    )
    unique: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item["key"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique
