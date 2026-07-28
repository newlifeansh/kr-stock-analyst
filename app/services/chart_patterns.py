from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class PricePoint:
    index: int
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


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
        result.append(
            PricePoint(
                index=len(result),
                date=_date_text(row),
                open=_number(getattr(row, "open", None), close),
                high=_number(getattr(row, "high", None), close),
                low=_number(getattr(row, "low", None), close),
                close=close,
                volume=_number(getattr(row, "volume", None)),
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
        "status": status,
        "points": [_point(item) for item in points],
        "trigger": round(trigger) if trigger else None,
        "target": round(target) if target else None,
        "invalidation": round(invalidation) if invalidation else None,
        "summary": summary,
        "evidence": evidence,
    }


def _reversal_patterns(rows: list[PricePoint], pivots: list[Pivot], atr: float) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    latest = rows[-1].close
    recent = pivots[-12:]
    for index in range(len(recent) - 2):
        first, middle, last = recent[index : index + 3]
        if last.index < len(rows) - 100:
            continue
        if [first.kind, middle.kind, last.kind] == ["low", "high", "low"]:
            tolerance = abs(first.price - last.price) / max(first.price, last.price)
            depth = middle.price - mean([first.price, last.price])
            if tolerance <= 0.065 and depth / middle.price >= 0.035:
                invalidation = min(first.price, last.price) - atr
                status = _status("bullish", latest, middle.price, invalidation)
                confidence = 68 + (1 - tolerance / 0.065) * 16 + (10 if status == "확인" else 0)
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
                confidence = 68 + (1 - tolerance / 0.065) * 16 + (10 if status == "확인" else 0)
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
                    confidence=72 + (9 if status == "확인" else 0) - shoulder_gap * 60, status=status,
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
                    confidence=72 + (9 if status == "확인" else 0) - peak_spread * 80, status=status,
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
                    confidence=72 + (9 if status == "확인" else 0) - shoulder_gap * 60, status=status,
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
                    confidence=72 + (9 if status == "확인" else 0) - trough_spread * 80, status=status,
                    points=points, trigger=peak, target=peak + (peak - trough_average),
                    invalidation=invalidation, summary="세 저점이 비슷한 가격에서 반복해서 지지됐습니다. 두 고점의 평균 돌파가 상승 전환 기준입니다.",
                    evidence=[f"저점 편차 {trough_spread * 100:.1f}%", f"전환 기준 {peak:,.0f}원"],
                ))
    return found


def _consolidation_patterns(rows: list[PricePoint], pivots: list[Pivot], atr: float) -> list[dict[str, object]]:
    recent = [item for item in pivots if item.index >= len(rows) - 80]
    highs = [item for item in recent if item.kind == "high"][-5:]
    lows = [item for item in recent if item.kind == "low"][-5:]
    if len(highs) < 2 or len(lows) < 2:
        return []
    high_slope, high_intercept = _linear([(item.index, item.price) for item in highs])
    low_slope, low_intercept = _linear([(item.index, item.price) for item in lows])
    base = rows[-1].close
    high_norm = high_slope / base
    low_norm = low_slope / base
    start = min(highs[0].index, lows[0].index)
    end = len(rows) - 1
    gap_start = (high_slope * start + high_intercept) - (low_slope * start + low_intercept)
    high_end = high_slope * end + high_intercept
    low_end = low_slope * end + low_intercept
    gap_end = high_end - low_end
    converging = gap_start > 0 and gap_end < gap_start * 0.78
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
    confidence = 62 + min(18, len(highs) + len(lows)) + (8 if status == "확인" else 0)
    return [_pattern(
        key=key, name=name, family="수렴·추세", direction=direction, confidence=confidence,
        status=status, points=sorted(highs + lows, key=lambda item: item.index), trigger=trigger,
        target=target, invalidation=invalidation, summary=summary,
        evidence=[f"상단 기울기 {high_norm * 100:.2f}%/일", f"하단 기울기 {low_norm * 100:.2f}%/일"],
    )]


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
            confidence=64 + (8 if counter else 0) + (8 if status == "확인" else 0), status=status,
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
                    confidence=70 + (8 if status == "확인" else 0) - rim_gap * 40, status=status,
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
        key=key, name=name, family="반전", direction=direction, confidence=64 + (8 if status == "확인" else 0),
        status=status, points=[item for item in pivots if item.index >= len(rows) - 90], trigger=trigger,
        target=target, invalidation=invalidation, summary=summary,
        evidence=[f"중앙부 괴리 {abs(middle / mean([left, right]) - 1) * 100:.1f}%"],
    )]


def _candlestick_patterns(rows: list[PricePoint], atr: float) -> list[dict[str, object]]:
    if len(rows) < 3:
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
    elif previous.close < previous.open and latest.close > latest.open and latest.open <= previous.close and latest.close >= previous.open:
        key, name, direction = "bullish-engulfing", "상승 장악형", "bullish"
        summary = "양봉 몸통이 직전 음봉을 감쌌습니다. 단기 매수 전환 후보입니다."
    elif previous.close > previous.open and latest.close < latest.open and latest.open >= previous.close and latest.close <= previous.open:
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


def detect_chart_patterns(price_rows: Iterable[Any], limit: int = 5) -> list[dict[str, object]]:
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
    status_rank = {"확인": 2, "후보": 1}
    candidates.sort(key=lambda item: (status_rank.get(str(item["status"]), 0), float(item["confidence"])), reverse=True)
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
