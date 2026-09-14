from __future__ import annotations

"""Market-neutral price primitives shared by position-lifecycle strategies.

The module intentionally contains no exchange calendar, currency, data-source,
or evidence assumptions.  Market adapters own those decisions and pass an
immutable policy into the common entry/chase/re-entry rules.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional, Protocol, Sequence


class LifecycleBar(Protocol):
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    trading_value: float
    ohlc_complete: bool


@dataclass(frozen=True)
class EntryPolicy:
    entry_score: float
    early_entry_score: float
    max_entry_atr_percent: float
    max_entry_extension_atr: float
    min_average_trading_value: float
    min_momentum5: float
    min_volume_ratio: float
    entry_momentum20_min: float = 0.005
    early_momentum5_min: float = 0.02
    early_momentum20_floor: float = -0.01
    early_ema60_gap_max: float = 0.005
    early_volume_min: float = 1.1


@dataclass(frozen=True)
class ChasePolicy:
    effective_date: Optional[date]
    max_extension_atr: float
    max_extension_percent: float
    momentum5_max: float
    momentum_lookback_bars: int


@dataclass(frozen=True)
class ReentryPolicy:
    event_effective_date: Optional[date]
    legacy_cooldown_bars: int
    retest_lookback_bars: int
    retest_ema20_buffer: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ema(values: Sequence[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [float(values[0])]
    for value in values[1:]:
        result.append((float(value) * alpha) + (result[-1] * (1.0 - alpha)))
    return result


def _rolling_average(values: Sequence[float], window: int) -> list[Optional[float]]:
    result: list[Optional[float]] = []
    total = 0.0
    for index, value in enumerate(values):
        total += float(value)
        if index >= window:
            total -= float(values[index - window])
        result.append(total / window if index >= window - 1 else None)
    return result


def calculate_indicators(bars: Sequence[LifecycleBar]) -> list[dict[str, float]]:
    """Calculate the common EMA/momentum/ATR/participation feature set."""

    closes = [float(bar.close) for bar in bars]
    volumes = [float(bar.volume) for bar in bars]
    trading_values = [float(bar.trading_value) for bar in bars]
    ema10 = _ema(closes, 10)
    ema20 = _ema(closes, 20)
    ema60 = _ema(closes, 60)

    true_ranges: list[float] = []
    for index, bar in enumerate(bars):
        previous_close = closes[index - 1] if index else float(bar.close)
        true_ranges.append(
            max(
                float(bar.high) - float(bar.low),
                abs(float(bar.high) - previous_close),
                abs(float(bar.low) - previous_close),
            )
        )
    atr14 = _ema(true_ranges, 14)
    volume20 = _rolling_average(volumes, 20)
    trading_value20 = _rolling_average(trading_values, 20)

    indicators: list[dict[str, float]] = []
    for index, bar in enumerate(bars):
        close = float(bar.close)
        reference5 = closes[index - 5] if index >= 5 else closes[0]
        reference10 = closes[index - 10] if index >= 10 else closes[0]
        reference20 = closes[index - 20] if index >= 20 else closes[0]
        momentum5 = (close / reference5) - 1.0 if reference5 else 0.0
        momentum10 = (close / reference10) - 1.0 if reference10 else 0.0
        momentum20 = (close / reference20) - 1.0 if reference20 else 0.0
        prior_highs = [float(item.high) for item in bars[max(0, index - 20) : index]]
        prior_high = max(prior_highs) if prior_highs else float(bar.high)
        high_distance = (close / prior_high) - 1.0 if prior_high else 0.0
        average_volume = volume20[index] or 0.0
        volume_ratio = float(bar.volume) / average_volume if average_volume > 0 else 1.0
        atr_percent = atr14[index] / close if close else 0.0
        ema20_extension_atr = (
            (close - ema20[index]) / atr14[index]
            if atr14[index] > 0
            else 0.0
        )
        ema20_slope = (
            (ema20[index] / ema20[index - 5]) - 1.0
            if index >= 5 and ema20[index - 5]
            else 0.0
        )
        ema10_slope = (
            (ema10[index] / ema10[index - 3]) - 1.0
            if index >= 3 and ema10[index - 3]
            else 0.0
        )

        trend_raw = 0.0
        trend_raw += 0.45 if close >= ema20[index] else -0.45
        trend_raw += 0.35 if ema20[index] >= ema60[index] else -0.35
        trend_raw += 0.20 if ema20_slope >= 0 else -0.20
        trend_score = _clamp(trend_raw, -1.0, 1.0)
        momentum_score = _clamp(momentum20 / 0.12, -1.0, 1.0)
        breakout_score = _clamp((high_distance + 0.04) / 0.04, -1.0, 1.0)
        volume_score = _clamp((volume_ratio - 1.0) / 1.2, -0.5, 1.0)
        volatility_penalty = _clamp((atr_percent - 0.035) / 0.065, 0.0, 1.0)
        total_score = _clamp(
            50.0
            + (trend_score * 24.0)
            + (momentum_score * 18.0)
            + (breakout_score * 10.0)
            + (volume_score * 6.0)
            - (volatility_penalty * 8.0),
            0.0,
            100.0,
        )
        indicators.append(
            {
                "score": total_score,
                "ema10": ema10[index],
                "ema20": ema20[index],
                "ema60": ema60[index],
                "ema10_slope": ema10_slope,
                "ema20_slope": ema20_slope,
                "momentum5": momentum5,
                "momentum10": momentum10,
                "momentum20": momentum20,
                "prior_high": prior_high,
                "high_distance": high_distance,
                "volume_ratio": volume_ratio,
                "atr": atr14[index],
                "atr_percent": atr_percent,
                "ema20_extension_atr": ema20_extension_atr,
                "trend_score": trend_score,
                "momentum_score": momentum_score,
                "breakout_score": breakout_score,
                "volume_score": volume_score,
                "average_trading_value": trading_value20[index] or 0.0,
            }
        )
    return indicators


def entry_quality_allowed(
    bar: LifecycleBar,
    indicator: dict[str, float],
    policy: EntryPolicy,
) -> bool:
    return bool(
        bar.ohlc_complete
        and indicator["atr_percent"] <= policy.max_entry_atr_percent
        and indicator.get("ema20_extension_atr", 0.0)
        <= policy.max_entry_extension_atr
        and indicator.get("average_trading_value", 0.0)
        >= policy.min_average_trading_value
        and indicator.get("momentum5", 0.0) >= policy.min_momentum5
        and indicator.get("volume_ratio", 0.0) >= policy.min_volume_ratio
    )


def base_entry_setup_kind(
    bar: LifecycleBar,
    indicator: dict[str, float],
    policy: EntryPolicy,
) -> Optional[str]:
    if not entry_quality_allowed(bar, indicator, policy):
        return None
    trend_continuation = bool(
        indicator["score"] >= policy.entry_score
        and bar.close > indicator["ema20"] > indicator["ema60"]
        and indicator["ema20_slope"] > 0
        and indicator["momentum20"] > policy.entry_momentum20_min
    )
    if trend_continuation:
        return "trend_continuation"
    early_turn = bool(
        indicator["score"] >= policy.early_entry_score
        and bar.close > indicator["ema10"] > indicator["ema20"]
        and indicator["ema20"]
        >= indicator["ema60"] * (1.0 - policy.early_ema60_gap_max)
        and indicator.get("ema10_slope", 0.0) > 0
        and indicator["ema20_slope"] > -0.002
        and indicator.get("momentum5", 0.0) > policy.early_momentum5_min
        and indicator["momentum20"] > policy.early_momentum20_floor
        and indicator.get("volume_ratio", 0.0) >= policy.early_volume_min
    )
    return "early_turn" if early_turn else None


def chase_entry_veto_reason(
    bar: LifecycleBar,
    indicator: dict[str, float],
    recent_indicators: Sequence[dict[str, float]],
    policy: ChasePolicy,
) -> Optional[str]:
    if policy.effective_date is not None and bar.trade_date < policy.effective_date:
        return None
    if indicator.get("ema20_extension_atr", 0.0) >= policy.max_extension_atr:
        return "ema20_extension_atr"
    ema20 = float(indicator.get("ema20") or 0.0)
    if ema20 > 0 and (float(bar.close) / ema20) - 1.0 >= policy.max_extension_percent:
        return "ema20_extension_percent"
    momentum_window = list(recent_indicators or [indicator])[-policy.momentum_lookback_bars :]
    if any(
        float(item.get("momentum5") or 0.0) > policy.momentum5_max
        for item in momentum_window
    ):
        return "momentum5_cooldown"
    return None


def fresh_reentry_trigger(
    bars: Sequence[LifecycleBar],
    indicators: Sequence[dict[str, float]],
    index: int,
    last_exit_index: int,
    policy: ReentryPolicy,
) -> bool:
    current_bar = bars[index]
    current_indicator = indicators[index]
    fresh_breakout = False
    if index > 0:
        prior_high = float(current_indicator.get("prior_high") or 0.0)
        previous_prior_high = float(indicators[index - 1].get("prior_high") or 0.0)
        fresh_breakout = bool(
            prior_high > 0
            and previous_prior_high > 0
            and current_bar.close > prior_high
            and bars[index - 1].close <= previous_prior_high
        )

    legacy_cooldown_applies = bool(
        policy.event_effective_date is not None
        and current_bar.trade_date < policy.event_effective_date
    )
    first_eligible_index = last_exit_index + (
        policy.legacy_cooldown_bars + 1 if legacy_cooldown_applies else 1
    )
    if index < first_eligible_index:
        return False
    retest_start = max(
        first_eligible_index,
        index - policy.retest_lookback_bars + 1,
        0,
    )
    recent_retest = any(
        float(indicators[cursor].get("ema20") or 0.0) > 0
        and bars[cursor].low
        <= float(indicators[cursor]["ema20"])
        * (1.0 + policy.retest_ema20_buffer)
        for cursor in range(retest_start, index + 1)
    )
    pullback_recovery = bool(
        recent_retest
        and current_bar.close > float(current_indicator.get("ema20") or 0.0)
        and float(current_indicator.get("momentum5") or 0.0) > 0.0
    )
    return fresh_breakout or pullback_recovery


def entry_decision(
    bar: LifecycleBar,
    indicator: dict[str, float],
    recent_indicators: Sequence[dict[str, float]],
    *,
    entry_policy: EntryPolicy,
    chase_policy: ChasePolicy,
) -> dict[str, Any]:
    setup = base_entry_setup_kind(bar, indicator, entry_policy)
    veto = chase_entry_veto_reason(
        bar,
        indicator,
        recent_indicators,
        chase_policy,
    )
    return {
        "allowed": bool(setup and not veto),
        "entry_setup": setup,
        "veto_reason": veto,
    }
