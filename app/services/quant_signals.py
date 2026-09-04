from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from math import isfinite, sqrt
from typing import Any, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    DailyPrice,
    DisclosureItem,
    InvestorFlow,
    MarketQuantSignalSnapshot,
    NewsItem,
    ResearchReport,
    StockCompanySnapshot,
    StockMaster,
    StockNewsSnapshot,
)
from app.services.sector_taxonomy import investment_sector_fields
from app.services.market_calendar import (
    is_korea_market_session_date,
    latest_completed_korea_market_session_date,
)
from app.services.signal_reconciliations import (
    apply_market_signal_reconciliations,
    apply_stock_signal_reconciliations,
)
from app.services.signal_entry_evidence import (
    ENTRY_EVIDENCE_EFFECTIVE_DATE,
    build_relative_strength_context,
    confirmation_response_payload,
    ensure_entry_evidence_snapshot,
    entry_confirmation_decision,
    load_entry_evidence_timeline,
)


KST = ZoneInfo("Asia/Seoul")
LEGACY_STRATEGY_VERSION = "position-lifecycle-legacy"
V7_1_STRATEGY_VERSION = "position-lifecycle-v7.1"
V7_3_STRATEGY_VERSION = "position-lifecycle-v7.3"
STRATEGY_VERSION = "position-lifecycle-v7.4"
# The released v7.4 line remains the comparison baseline until the H1
# candidate is explicitly promoted.  Keeping the candidate separate makes
# yesterday's release and the new entry gate independently reproducible.
CANDIDATE_STRATEGY_VERSION = "position-lifecycle-v7.5-rc1"
STRATEGY_NAME = "독립 근거 확인·조기 추세 포착·단기 전술형 수익확정 전략"
MIN_HISTORY_ROWS = 125
WARMUP_ROWS = 65
BACKTEST_ROWS = 252
MIN_BACKTEST_HISTORY_ROWS = WARMUP_ROWS + BACKTEST_ROWS
SIGNAL_HISTORY_ROWS = 900
# v7.3 thresholds are retained for historical replay. v7.4 tightens the
# current entry gate after the latest completed session in this release.
STABLE_PROFIT_EFFECTIVE_DATE = date(2026, 9, 4)
V7_3_ENTRY_SCORE = 62.0
V7_3_EARLY_ENTRY_SCORE = 61.0
V7_3_MAX_ENTRY_ATR_PERCENT = 0.06
ENTRY_SCORE = 64.0
ENTRY_MOMENTUM_MIN = 0.005
EARLY_ENTRY_SCORE = 64.0
EARLY_ENTRY_MOMENTUM_5_MIN = 0.02
EARLY_ENTRY_MOMENTUM_20_FLOOR = -0.01
EARLY_ENTRY_EMA60_GAP_MAX = 0.005
EARLY_ENTRY_VOLUME_MIN = 1.1
PRE_ENTRY_SCORE = 54.0
PRE_ENTRY_MOMENTUM_5_MIN = 0.0
MAX_ENTRY_ATR_PERCENT = 0.045
MAX_ENTRY_EXTENSION_ATR = 2.5
MAX_ENTRY_GAP_ATR = 1.5
MAX_ENTRY_GAP_PERCENT = 0.05
MIN_AVERAGE_TRADING_VALUE = 5_000_000_000.0
# Entry-filter versions are intentionally independent from the position
# lifecycle version.  H1 is the active candidate; H2/H3 are shadow-only
# comparison profiles and never change a user's signal by themselves.
ENTRY_FILTER_BASELINE_VERSION = "buy-filter-v7.4-baseline"
ENTRY_FILTER_H1_VERSION = "buy-filter-h1"
ENTRY_FILTER_H2_VERSION = "buy-filter-h2"
ENTRY_FILTER_H3_VERSION = "buy-filter-h3"
ENTRY_FILTER_VERSION = ENTRY_FILTER_H1_VERSION
ENTRY_FILTER_EFFECTIVE_DATE = date(2026, 9, 4)
ENTRY_FILTER_SHADOW_VERSIONS = (
    ENTRY_FILTER_H2_VERSION,
    ENTRY_FILTER_H3_VERSION,
)
STRATEGY_VERSION_HISTORY = (
    {
        "version": LEGACY_STRATEGY_VERSION,
        "effective_from": None,
        "effective_to": "2026-08-23",
        "status": "historical",
        "scope": "3R·5R·8R 수익확정 사다리",
    },
    {
        "version": V7_1_STRATEGY_VERSION,
        "effective_from": "2026-08-24",
        "effective_to": "2026-08-24",
        "status": "historical",
        "scope": "2R·4R·6R 수익보호 사다리",
    },
    {
        "version": V7_3_STRATEGY_VERSION,
        "effective_from": "2026-08-25",
        "effective_to": "2026-09-03",
        "status": "historical",
        "scope": "1R·1.6R·2.5R 전술형 사다리",
    },
    {
        "version": STRATEGY_VERSION,
        "effective_from": "2026-09-04",
        "effective_to": None,
        "status": "baseline",
        "scope": "+3%·+5% 고정 수익확정·runner 0%",
    },
    {
        "version": CANDIDATE_STRATEGY_VERSION,
        "effective_from": "2026-09-04",
        "effective_to": None,
        "status": "candidate",
        "scope": "v7.4 baseline + buy-filter-h1; promotion pending",
    },
)
EXIT_SCORE = 42.0
# Each step is (trigger in initial-risk multiples, fraction of the original
# position to sell, locked-profit floor in R, volatility trailing width in ATR).
# v7.2 realizes most of a tactical position earlier while retaining a 30%
# trend-following runner. Historical ladders remain available so an old signal
# is never rewritten with rules that did not exist on its decision date.
LEGACY_PROFIT_LADDER_STEPS = (
    (3.0, 0.10, 1.0, 3.2),
    (5.0, 0.15, 3.0, 2.9),
    (8.0, 0.15, 5.5, 2.6),
)
PROFIT_PRESERVATION_EFFECTIVE_DATE = date(2026, 8, 24)
PROFIT_PRESERVATION_LADDER_STEPS = (
    (2.0, 0.15, 1.0, 3.2),
    (4.0, 0.15, 3.0, 2.9),
    (6.0, 0.10, 5.5, 2.6),
)
TACTICAL_EXIT_EFFECTIVE_DATE = date(2026, 8, 25)
# v7.3 ladder, used for all decisions before the v7.4 effective date.
TACTICAL_PROFIT_LADDER_STEPS = (
    (1.0, 0.30, 0.25, 2.6),
    (1.6, 0.25, 1.0, 2.2),
    (2.5, 0.15, 1.8, 1.8),
)
# v7.4 uses price-percent targets. The first and third fields are percentages
# of entry price and are converted to R only after the position's initial risk
# is known.
PROFIT_LADDER_STEPS = (
    (0.03, 0.50, 0.02, 1.8),
    (0.05, 0.50, 0.05, 1.2),
)
V7_3_MIN_RUNNER_FRACTION = 0.30
MIN_RUNNER_FRACTION = 0.0
MAX_TACTICAL_TRANSITION_SELL_FRACTION = 0.30
INITIAL_STOP_ATR = 1.75
V7_3_MAX_INITIAL_RISK_PERCENT = 0.06
MAX_INITIAL_RISK_PERCENT = 0.04
BASE_TRAILING_STOP_ATR = 3.4
PRE_TACTICAL_MIN_HOLDING_BARS = 5
MIN_HOLDING_BARS = 3
REENTRY_COOLDOWN_BARS = 10
PRE_TACTICAL_EXIT_CONFIRMATION_BARS = 2
EXIT_CONFIRMATION_BARS = 1
MIN_COMPLETED_TRADES_FOR_SAMPLE = 20
LEGACY_BREAK_EVEN_TRIGGER_R = 2.0
PROFIT_PRESERVATION_BREAK_EVEN_TRIGGER_R = 1.5
BREAK_EVEN_TRIGGER_R = 0.75
BREAK_EVEN_BUFFER = 0.001
MIN_EXECUTION_COST_PER_SIDE = 0.00125
MAX_EXECUTION_COST_PER_SIDE = 0.005
DEFAULT_EXECUTION_COST_PER_SIDE = 0.002
MARKET_SIGNAL_CORE_UNIVERSE_LIMIT = 100
MARKET_SIGNAL_UNIVERSE_LIMIT = 150
MARKET_SIGNAL_EXTENDED_MIN_AVERAGE_TRADING_VALUE = 20_000_000_000.0
MARKET_SIGNAL_EXTENDED_EFFECTIVE_DATE = date(2026, 8, 27)
# Zero means that every transition inside the recent-day window is returned.
# The market universe is already capped separately, so the feed should not
# silently discard events that are also eligible for push notifications.
MARKET_SIGNAL_FEED_LIMIT = 0
MARKET_SIGNAL_RECENT_DAYS = 30
MARKET_SIGNAL_SNAPSHOT_VERSION = "v31"

POSITIVE_WORDS = (
    "상향",
    "호조",
    "개선",
    "증가",
    "수주",
    "흑자",
    "서프라이즈",
    "강세",
    "성장",
    "돌파",
    "수혜",
    "상승",
    "회복",
    "호재",
    "매수",
)
NEGATIVE_WORDS = (
    "하향",
    "부진",
    "감소",
    "적자",
    "쇼크",
    "약세",
    "하락",
    "악화",
    "손실",
    "둔화",
    "우려",
    "급락",
    "악재",
    "위기",
    "매도",
)
FOREIGN_TYPES = ("외국인", "외국인합계", "외국계")
INSTITUTION_TYPES = ("기관합계", "기관", "금융투자", "투신", "연기금")


@dataclass(frozen=True)
class PriceBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    trading_value: float
    ohlc_complete: bool = True


def _decimal(value: Optional[float], places: str = "0.01") -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _price(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _has_complete_ohlc(
    open_price: Optional[float],
    high: Optional[float],
    low: Optional[float],
    close: Optional[float],
) -> bool:
    if None in (open_price, high, low, close):
        return False
    return bool(
        high >= max(open_price, close)
        and low <= min(open_price, close)
        and high >= low
    )


def _normalize_prices(rows: list[DailyPrice]) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for row in sorted(rows, key=lambda item: item.trade_date):
        if row.trade_date.weekday() >= 5:
            continue
        close = _safe_number(row.close)
        if close is None:
            continue
        observed_open = _safe_number(row.open)
        observed_high = _safe_number(row.high)
        observed_low = _safe_number(row.low)
        ohlc_complete = _has_complete_ohlc(
            observed_open,
            observed_high,
            observed_low,
            close,
        )
        volume = max(0.0, float(row.volume or 0))
        reported_trading_value = max(0.0, float(row.trading_value or 0))
        if not ohlc_complete and volume == 0 and reported_trading_value == 0:
            # Suspended stocks can receive a weekday close/market-cap
            # placeholder even though no trade occurred.  It is not a candle
            # and must neither break the verified OHLC window nor create a
            # synthetic zero-range session.
            continue
        open_price = observed_open or close
        high = max(observed_high or close, close, open_price)
        low = min(observed_low or close, close, open_price)
        estimated_trading_value = close * volume
        bars.append(
            PriceBar(
                trade_date=row.trade_date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                trading_value=reported_trading_value or estimated_trading_value,
                ohlc_complete=ohlc_complete,
            )
        )
    return bars


def _is_non_trading_placeholder_row(row: DailyPrice) -> bool:
    return bool(
        _safe_number(row.close) is not None
        and not _has_complete_ohlc(
            _safe_number(row.open),
            _safe_number(row.high),
            _safe_number(row.low),
            _safe_number(row.close),
        )
        and int(row.volume or 0) == 0
        and int(row.trading_value or 0) == 0
    )


def _confirmed_bars(bars: list[PriceBar], now: datetime) -> list[PriceBar]:
    if not bars:
        return []
    latest = bars[-1]
    market_is_forming = (
        latest.trade_date == now.date()
        and now.weekday() < 5
        and time(8, 0) <= now.time() < time(15, 40)
    )
    return bars[:-1] if market_is_forming else bars


def _forming_bar_quote(bars: list[PriceBar], now: datetime) -> Optional[dict[str, Any]]:
    if not bars:
        return None
    latest = bars[-1]
    market_is_forming = (
        latest.trade_date == now.date()
        and now.weekday() < 5
        and time(8, 0) <= now.time() < time(15, 40)
    )
    if not market_is_forming:
        return None
    return {
        "trade_date": latest.trade_date,
        "trade_date_verified": True,
        "price": latest.close,
        "open": latest.open,
        "high": latest.high,
        "low": latest.low,
        "ohlc_complete": latest.ohlc_complete,
        "volume": latest.volume,
        "trading_value": latest.trading_value,
        "market_venue": "KRX",
        "market_division": "J",
        "quote_source": "stored_daily_price",
    }


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append((value * alpha) + (result[-1] * (1.0 - alpha)))
    return result


def _rolling_average(values: list[float], window: int) -> list[Optional[float]]:
    result: list[Optional[float]] = []
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        result.append(total / window if index >= window - 1 else None)
    return result


def _indicator_rows(bars: list[PriceBar]) -> list[dict[str, float]]:
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]
    trading_values = [bar.trading_value for bar in bars]
    ema10 = _ema(closes, 10)
    ema20 = _ema(closes, 20)
    ema60 = _ema(closes, 60)

    true_ranges: list[float] = []
    for index, bar in enumerate(bars):
        previous_close = closes[index - 1] if index else bar.close
        true_ranges.append(
            max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        )
    atr14 = _ema(true_ranges, 14)
    volume20 = _rolling_average(volumes, 20)
    trading_value20 = _rolling_average(trading_values, 20)

    indicators: list[dict[str, float]] = []
    for index, bar in enumerate(bars):
        reference5 = closes[index - 5] if index >= 5 else closes[0]
        reference10 = closes[index - 10] if index >= 10 else closes[0]
        reference20 = closes[index - 20] if index >= 20 else closes[0]
        momentum5 = (bar.close / reference5) - 1.0 if reference5 else 0.0
        momentum10 = (bar.close / reference10) - 1.0 if reference10 else 0.0
        momentum20 = (bar.close / reference20) - 1.0 if reference20 else 0.0
        prior_highs = [item.high for item in bars[max(0, index - 20) : index]]
        prior_high = max(prior_highs) if prior_highs else bar.high
        high_distance = (bar.close / prior_high) - 1.0 if prior_high else 0.0
        average_volume = volume20[index] or 0.0
        volume_ratio = bar.volume / average_volume if average_volume > 0 else 1.0
        atr_percent = atr14[index] / bar.close if bar.close else 0.0
        ema20_extension_atr = (
            (bar.close - ema20[index]) / atr14[index]
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
        trend_raw += 0.45 if bar.close >= ema20[index] else -0.45
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


def strategy_version_for_date(strategy_date: Optional[date]) -> str:
    """Return the immutable position-lifecycle version for a decision date."""

    if strategy_date is None or strategy_date >= STABLE_PROFIT_EFFECTIVE_DATE:
        return STRATEGY_VERSION
    if strategy_date >= TACTICAL_EXIT_EFFECTIVE_DATE:
        return V7_3_STRATEGY_VERSION
    if strategy_date >= PROFIT_PRESERVATION_EFFECTIVE_DATE:
        return V7_1_STRATEGY_VERSION
    return LEGACY_STRATEGY_VERSION


def _entry_filter_parameters(
    strategy_date: Optional[date],
    entry_filter_version: Optional[str],
) -> dict[str, float]:
    """Overlay one independently versioned entry filter on base parameters."""

    parameters = _entry_parameters(strategy_date)
    if entry_filter_version in (None, ENTRY_FILTER_BASELINE_VERSION):
        return parameters
    if entry_filter_version == ENTRY_FILTER_H1_VERSION:
        return {
            **parameters,
            "min_momentum5": 0.005,
            "min_volume_ratio": 1.0,
        }
    if entry_filter_version == ENTRY_FILTER_H2_VERSION:
        return {
            **parameters,
            "min_momentum5": 0.01,
            "min_volume_ratio": 1.1,
        }
    if entry_filter_version == ENTRY_FILTER_H3_VERSION:
        return {
            **parameters,
            "max_entry_atr_percent": 0.04,
            "max_entry_extension_atr": 2.0,
            "min_momentum5": 0.005,
            "min_volume_ratio": 1.0,
        }
    raise ValueError(f"Unknown entry filter version: {entry_filter_version}")


def active_entry_filter_version(strategy_date: Optional[date]) -> str:
    """Return H1 only after its effective date; preserve historical baseline."""

    if strategy_date is not None and strategy_date < ENTRY_FILTER_EFFECTIVE_DATE:
        return ENTRY_FILTER_BASELINE_VERSION
    return ENTRY_FILTER_VERSION


def _entry_parameters(strategy_date: Optional[date]) -> dict[str, float]:
    if strategy_date is not None and strategy_date < STABLE_PROFIT_EFFECTIVE_DATE:
        return {
            "entry_score": V7_3_ENTRY_SCORE,
            "early_entry_score": V7_3_EARLY_ENTRY_SCORE,
            "max_entry_atr_percent": V7_3_MAX_ENTRY_ATR_PERCENT,
            "min_momentum5": -float("inf"),
            "min_volume_ratio": -float("inf"),
        }
    return {
        "entry_score": ENTRY_SCORE,
        "early_entry_score": EARLY_ENTRY_SCORE,
        "max_entry_atr_percent": MAX_ENTRY_ATR_PERCENT,
        "min_momentum5": 0.0,
        "min_volume_ratio": 0.8,
    }


def _entry_quality_allowed(
    bar: PriceBar,
    indicator: dict[str, float],
    *,
    strategy_date: Optional[date] = None,
    entry_filter_version: Optional[str] = None,
) -> bool:
    decision_date = strategy_date or bar.trade_date
    parameters = _entry_filter_parameters(
        decision_date,
        entry_filter_version or active_entry_filter_version(decision_date),
    )
    return bool(
        bar.ohlc_complete
        and indicator["atr_percent"] <= parameters["max_entry_atr_percent"]
        and indicator.get("ema20_extension_atr", 0.0)
        <= parameters.get("max_entry_extension_atr", MAX_ENTRY_EXTENSION_ATR)
        and indicator.get("average_trading_value", 0.0) >= MIN_AVERAGE_TRADING_VALUE
        and indicator.get("momentum5", 0.0) >= parameters["min_momentum5"]
        and indicator.get("volume_ratio", 0.0) >= parameters["min_volume_ratio"]
    )


def _entry_setup_kind(
    bar: PriceBar,
    indicator: dict[str, float],
    *,
    entry_filter_version: Optional[str] = None,
) -> Optional[str]:
    """Return the confirmed setup without looking beyond the current close.

    ``trend_continuation`` keeps the established medium-term trend filter but
    accepts a smaller positive return so the strategy does not wait for a move
    to become crowded. ``early_turn`` may trigger before EMA20 clears EMA60,
    but only after the faster average, short momentum and participation turn
    together. Both paths share the same liquidity, volatility and extension
    guardrails.
    """

    decision_filter = entry_filter_version or active_entry_filter_version(bar.trade_date)
    parameters = _entry_filter_parameters(bar.trade_date, decision_filter)
    if not _entry_quality_allowed(
        bar,
        indicator,
        strategy_date=bar.trade_date,
        entry_filter_version=decision_filter,
    ):
        return None
    trend_continuation = bool(
        indicator["score"] >= parameters["entry_score"]
        and bar.close > indicator["ema20"] > indicator["ema60"]
        and indicator["ema20_slope"] > 0
        and indicator["momentum20"] > ENTRY_MOMENTUM_MIN
    )
    if trend_continuation:
        return "trend_continuation"
    early_turn = bool(
        indicator["score"] >= parameters["early_entry_score"]
        and bar.close > indicator["ema10"] > indicator["ema20"]
        and indicator["ema20"] >= indicator["ema60"] * (1.0 - EARLY_ENTRY_EMA60_GAP_MAX)
        and indicator.get("ema10_slope", 0.0) > 0
        and indicator["ema20_slope"] > -0.002
        and indicator.get("momentum5", 0.0) > EARLY_ENTRY_MOMENTUM_5_MIN
        and indicator["momentum20"] > EARLY_ENTRY_MOMENTUM_20_FLOOR
        and indicator.get("volume_ratio", 0.0) >= EARLY_ENTRY_VOLUME_MIN
    )
    return "early_turn" if early_turn else None


def _entry_signal(
    bar: PriceBar,
    indicator: dict[str, float],
    *,
    entry_filter_version: Optional[str] = None,
) -> bool:
    return (
        _entry_setup_kind(
            bar,
            indicator,
            entry_filter_version=entry_filter_version,
        )
        is not None
    )


def compare_entry_filter_candidates(
    bar: PriceBar,
    indicator: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """Compare baseline/H1/H2/H3 eligibility without changing active state.

    This is deliberately a pure backend diagnostic.  Only H1 is used by the
    active signal path after its effective date; H2 and H3 are returned for
    shadow backtests and are not promoted to notifications or orders.
    """

    result: dict[str, dict[str, Any]] = {}
    for version in (
        ENTRY_FILTER_BASELINE_VERSION,
        ENTRY_FILTER_H1_VERSION,
        ENTRY_FILTER_H2_VERSION,
        ENTRY_FILTER_H3_VERSION,
    ):
        setup = _entry_setup_kind(
            bar,
            indicator,
            entry_filter_version=version,
        )
        parameters = _entry_filter_parameters(bar.trade_date, version)
        result[version] = {
            "allowed": setup is not None,
            "entry_setup": setup,
            "entry_score": parameters["entry_score"],
            "max_entry_atr_percent": parameters["max_entry_atr_percent"],
            "max_entry_extension_atr": parameters.get(
                "max_entry_extension_atr", MAX_ENTRY_EXTENSION_ATR
            ),
            "min_momentum5": parameters["min_momentum5"],
            "min_volume_ratio": parameters["min_volume_ratio"],
        }
    return result


def _pre_entry_signal(bar: PriceBar, indicator: dict[str, float]) -> bool:
    """Identify a near-ready setup without presenting it as an executable buy."""

    if _entry_signal(bar, indicator) or not _entry_quality_allowed(
        bar,
        indicator,
        strategy_date=bar.trade_date,
    ):
        return False
    return bool(
        indicator["score"] >= PRE_ENTRY_SCORE
        and bar.close >= indicator["ema20"] * 0.99
        and indicator.get("ema10_slope", 0.0) > 0
        and indicator.get("momentum5", 0.0) > PRE_ENTRY_MOMENTUM_5_MIN
        and indicator["momentum20"] > -0.05
        and indicator.get("high_distance", -1.0) >= -0.08
        and indicator.get("volume_ratio", 0.0) >= 0.75
    )


def _pre_entry_next_confirmation(bar: PriceBar, indicator: dict[str, float]) -> str:
    if bar.close <= indicator["ema20"]:
        return "종가가 20일선을 회복하면 조기 매수 조건을 다시 확인"
    if indicator["ema10"] <= indicator["ema20"]:
        return "10일선이 20일선 위로 정렬되면 조기 매수 조건을 확인"
    if indicator["ema20"] < indicator["ema60"] * (1.0 - EARLY_ENTRY_EMA60_GAP_MAX):
        return "20일선이 60일선 부근까지 회복하면 조기 매수 조건을 확인"
    if indicator.get("momentum5", 0.0) <= EARLY_ENTRY_MOMENTUM_5_MIN:
        return f"5일 흐름이 {EARLY_ENTRY_MOMENTUM_5_MIN * 100:.1f}%를 넘으면 매수 조건을 확인"
    if indicator.get("momentum20", 0.0) <= EARLY_ENTRY_MOMENTUM_20_FLOOR:
        return "20일 흐름이 -1% 위로 회복하면 조기 매수 조건을 확인"
    if indicator.get("volume_ratio", 0.0) < EARLY_ENTRY_VOLUME_MIN:
        return f"거래량이 20일 평균의 {EARLY_ENTRY_VOLUME_MIN:.1f}배를 넘으면 매수 조건을 확인"
    return f"종합 신호가 {EARLY_ENTRY_SCORE:.0f}점에 도달하면 조기 매수 조건을 확정"


def _execution_cost(indicator: dict[str, float]) -> float:
    """Estimate one-way fees, slippage, and liquidity impact without order-book hindsight."""
    cost = 0.0015
    average_value = indicator.get("average_trading_value", 0.0)
    if average_value <= 0:
        cost += 0.0005
    elif average_value < 5_000_000_000:
        cost += 0.0020
    elif average_value < 20_000_000_000:
        cost += 0.0010
    elif average_value >= 100_000_000_000:
        cost -= 0.00025

    atr_percent = indicator.get("atr_percent", 0.0)
    if atr_percent > 0.05:
        cost += min(0.0015, (atr_percent - 0.05) * 0.03)
    return _clamp(cost, MIN_EXECUTION_COST_PER_SIDE, MAX_EXECUTION_COST_PER_SIDE)


def _initial_risk(
    entry_price: float,
    atr: float,
    *,
    strategy_date: Optional[date] = None,
) -> float:
    """Cap planned risk so a volatile ATR cannot create an unbounded stop distance."""
    minimum_risk = entry_price * 0.01
    volatility_risk = max(0.0, atr) * INITIAL_STOP_ATR
    maximum_risk_percent = (
        V7_3_MAX_INITIAL_RISK_PERCENT
        if strategy_date is not None and strategy_date < STABLE_PROFIT_EFFECTIVE_DATE
        else MAX_INITIAL_RISK_PERCENT
    )
    maximum_risk = entry_price * maximum_risk_percent
    return min(max(volatility_risk, minimum_risk), maximum_risk)


def _entry_execution_allowed(execution_price: float, pending: dict[str, Any]) -> bool:
    """Cancel a stale close signal when the next open gaps beyond its risk envelope."""
    signal_price = _safe_number(pending.get("signal_price"))
    if signal_price is None:
        return True
    atr = max(0.0, float(pending.get("atr") or 0.0))
    percent_limit = signal_price * MAX_ENTRY_GAP_PERCENT
    volatility_limit = atr * MAX_ENTRY_GAP_ATR if atr > 0 else percent_limit
    allowed_gap = max(signal_price * 0.005, min(percent_limit, volatility_limit))
    return abs(float(execution_price) - signal_price) <= allowed_gap


def _profit_ladder_steps(
    strategy_date: Optional[date],
) -> tuple[tuple[float, float, float, float], ...]:
    """Keep audited historical exits intact across each strategy release."""

    if strategy_date is not None and strategy_date < PROFIT_PRESERVATION_EFFECTIVE_DATE:
        return LEGACY_PROFIT_LADDER_STEPS
    if strategy_date is not None and strategy_date < TACTICAL_EXIT_EFFECTIVE_DATE:
        return PROFIT_PRESERVATION_LADDER_STEPS
    if strategy_date is not None and strategy_date < STABLE_PROFIT_EFFECTIVE_DATE:
        return TACTICAL_PROFIT_LADDER_STEPS
    return PROFIT_LADDER_STEPS


def _stable_profit_mode(strategy_date: Optional[date]) -> bool:
    return strategy_date is None or strategy_date >= STABLE_PROFIT_EFFECTIVE_DATE


def _resolved_profit_ladder_steps(
    position: dict[str, Any],
    strategy_date: Optional[date],
) -> tuple[tuple[float, float, float, float], ...]:
    steps = _profit_ladder_steps(strategy_date)
    if not _stable_profit_mode(strategy_date):
        return steps
    entry_price = float(position["entry_price"])
    initial_risk = max(float(position["initial_risk"]), entry_price * 0.01)
    return tuple(
        (
            (entry_price * target_percent) / initial_risk,
            sell_fraction,
            (entry_price * locked_percent) / initial_risk,
            trailing_atr,
        )
        for target_percent, sell_fraction, locked_percent, trailing_atr in steps
    )


def _resolved_break_even_trigger_r(
    position: dict[str, Any],
    strategy_date: Optional[date],
) -> float:
    if _stable_profit_mode(strategy_date):
        entry_price = float(position["entry_price"])
        initial_risk = max(float(position["initial_risk"]), entry_price * 0.01)
        return (entry_price * 0.02) / initial_risk
    return _break_even_trigger_r(strategy_date)


def _minimum_runner_fraction(strategy_date: Optional[date]) -> float:
    return MIN_RUNNER_FRACTION if _stable_profit_mode(strategy_date) else V7_3_MIN_RUNNER_FRACTION


def _break_even_trigger_r(strategy_date: Optional[date]) -> float:
    if strategy_date is not None and strategy_date < PROFIT_PRESERVATION_EFFECTIVE_DATE:
        return LEGACY_BREAK_EVEN_TRIGGER_R
    if strategy_date is not None and strategy_date < TACTICAL_EXIT_EFFECTIVE_DATE:
        return PROFIT_PRESERVATION_BREAK_EVEN_TRIGGER_R
    return BREAK_EVEN_TRIGGER_R


def _minimum_holding_bars(strategy_date: Optional[date]) -> int:
    if strategy_date is not None and strategy_date < TACTICAL_EXIT_EFFECTIVE_DATE:
        return PRE_TACTICAL_MIN_HOLDING_BARS
    return MIN_HOLDING_BARS


def _exit_confirmation_bars(strategy_date: Optional[date]) -> int:
    if strategy_date is not None and strategy_date < TACTICAL_EXIT_EFFECTIVE_DATE:
        return PRE_TACTICAL_EXIT_CONFIRMATION_BARS
    return EXIT_CONFIRMATION_BARS


def _position_levels(
    position: dict[str, Any],
    indicator: dict[str, float],
    peak_price: float,
    *,
    strategy_date: Optional[date] = None,
) -> dict[str, Any]:
    profit_ladder_steps = _resolved_profit_ladder_steps(position, strategy_date)
    break_even_trigger_r = _resolved_break_even_trigger_r(position, strategy_date)
    entry_price = float(position["entry_price"])
    initial_risk = max(float(position["initial_risk"]), entry_price * 0.01)
    current_stage = max(
        0,
        min(int(position.get("profit_stage") or 0), len(profit_ladder_steps)),
    )
    peak_r = (peak_price - entry_price) / initial_risk
    reached_stage = 0
    locked_r = 0.0
    trailing_atr = BASE_TRAILING_STOP_ATR
    for stage, (trigger_r, _sell_fraction, step_locked_r, step_trailing_atr) in enumerate(
        profit_ladder_steps,
        start=1,
    ):
        if peak_r + 1e-9 < trigger_r:
            break
        reached_stage = stage
        locked_r = max(locked_r, step_locked_r)
        trailing_atr = min(trailing_atr, step_trailing_atr)
    entry_date = position.get("entry_date")
    transition_ladders: list[tuple[tuple[float, float, float, float], ...]] = []
    if (
        strategy_date is not None
        and strategy_date >= TACTICAL_EXIT_EFFECTIVE_DATE
        and isinstance(entry_date, date)
        and entry_date < TACTICAL_EXIT_EFFECTIVE_DATE
    ):
        transition_ladders.append(PROFIT_PRESERVATION_LADDER_STEPS)
    if (
        strategy_date is not None
        and strategy_date >= STABLE_PROFIT_EFFECTIVE_DATE
        and isinstance(entry_date, date)
        and entry_date < STABLE_PROFIT_EFFECTIVE_DATE
    ):
        transition_ladders.append(TACTICAL_PROFIT_LADDER_STEPS)
    # A migrated position may already have secured a stronger floor than the
    # new ladder assigns to the same stage number. Preserve the strongest
    # previously earned floor and never widen its trailing band.
    for previous_steps in transition_ladders:
        for (
            previous_trigger_r,
            _previous_sell_fraction,
            previous_locked_r,
            previous_trailing_atr,
        ) in previous_steps:
            if peak_r + 1e-9 < previous_trigger_r:
                break
            locked_r = max(locked_r, previous_locked_r)
            trailing_atr = min(trailing_atr, previous_trailing_atr)
    next_stage = current_stage + 1 if current_stage < len(profit_ladder_steps) else None
    next_partial_target = (
        entry_price + (initial_risk * profit_ladder_steps[next_stage - 1][0])
        if next_stage is not None
        else None
    )
    volatility_stop = peak_price - (indicator["atr"] * trailing_atr)
    entry_cost = float(position.get("entry_cost") or DEFAULT_EXECUTION_COST_PER_SIDE)
    exit_cost = _execution_cost(indicator)
    break_even_floor = (
        entry_price
        * (1.0 + entry_cost)
        * (1.0 + BREAK_EVEN_BUFFER)
        / max(0.9, 1.0 - exit_cost)
    )
    profit_protection_active = peak_price >= entry_price + (initial_risk * break_even_trigger_r)
    locked_profit_floor = (
        entry_price + (initial_risk * locked_r)
        if reached_stage
        else break_even_floor if profit_protection_active else float(position["initial_stop"])
    )
    hard_floor = max(
        float(position["initial_stop"]),
        break_even_floor if profit_protection_active else float(position["initial_stop"]),
        locked_profit_floor,
    )
    trend_stop = indicator["ema20"] if current_stage else float(position["initial_stop"])
    trailing_stop = max(hard_floor, trend_stop, volatility_stop)
    return {
        "initial_risk": initial_risk,
        "current_stage": current_stage,
        "reached_stage": reached_stage,
        "next_stage": next_stage,
        "next_partial_target": next_partial_target,
        # Kept as a compatibility alias for clients that have not yet moved to
        # the explicit profit-ladder fields.
        "partial_target": next_partial_target,
        "trailing_stop": trailing_stop,
        "volatility_stop": volatility_stop,
        "locked_profit_floor": locked_profit_floor,
        "hard_floor": hard_floor,
        "peak_r": peak_r,
        "trailing_atr": trailing_atr,
        "profit_ladder_steps": profit_ladder_steps,
        "break_even_trigger_r": break_even_trigger_r,
        "break_even_floor": break_even_floor,
        "profit_protection_active": profit_protection_active,
        "profit_ladder_mode": "fixed_percent" if _stable_profit_mode(strategy_date) else "risk_multiple",
    }


def _full_exit_signal(
    bar: PriceBar,
    indicator: dict[str, float],
    position: dict[str, Any],
    peak_price: float,
) -> tuple[bool, str, dict[str, Any], bool]:
    levels = _position_levels(
        position,
        indicator,
        peak_price,
        strategy_date=bar.trade_date,
    )
    if bar.close <= float(position["initial_stop"]):
        return True, "초기 급락 위험선 이탈", levels, True
    profit_target_reached = bool(
        levels["reached_stage"] > levels["current_stage"]
        and levels["reached_stage"] > 0
        and bar.close
        >= float(position["entry_price"])
        + levels["initial_risk"]
        * levels["profit_ladder_steps"][levels["reached_stage"] - 1][0]
    )
    if (
        levels["profit_protection_active"]
        and bar.close <= levels["hard_floor"]
        and not (_stable_profit_mode(bar.trade_date) and profit_target_reached)
    ):
        if levels["reached_stage"]:
            return True, f"{levels['reached_stage']}단계 수익 보호선 이탈", levels, True
        return True, "비용 차감 손익분기 보호선 이탈", levels, True
    if bar.close <= levels["trailing_stop"] and not (
        _stable_profit_mode(bar.trade_date) and profit_target_reached
    ):
        return True, "고점 대비 변동성 추적선 이탈", levels, bool(levels["current_stage"])
    if indicator["score"] <= EXIT_SCORE:
        return True, "종합 점수가 전량 매도 기준보다 약해짐", levels, False
    if bar.close < indicator["ema20"] and indicator["ema10"] < indicator["ema20"]:
        return True, "20일선과 단기 추세가 함께 이탈됨", levels, False
    return False, "추세 유지", levels, False


def _partial_exit_signal(
    bar: PriceBar,
    indicator: dict[str, float],
    position: dict[str, Any],
    peak_price: float,
) -> tuple[bool, str, dict[str, Any]]:
    levels = _position_levels(
        position,
        indicator,
        peak_price,
        strategy_date=bar.trade_date,
    )
    profit_ladder_steps = levels["profit_ladder_steps"]
    current_stage = int(levels["current_stage"])
    target_stage = current_stage
    for stage, (trigger_r, _sell_fraction, _locked_r, _trailing_atr) in enumerate(
        profit_ladder_steps,
        start=1,
    ):
        target = float(position["entry_price"]) + (levels["initial_risk"] * trigger_r)
        if stage > current_stage and bar.close >= target:
            target_stage = stage

    entry_date = position.get("entry_date")
    stable_transition = bool(
        bar.trade_date >= STABLE_PROFIT_EFFECTIVE_DATE
        and isinstance(entry_date, date)
        and entry_date < STABLE_PROFIT_EFFECTIVE_DATE
    )
    tactical_transition = bool(
        bar.trade_date >= TACTICAL_EXIT_EFFECTIVE_DATE
        and isinstance(entry_date, date)
        and entry_date < TACTICAL_EXIT_EFFECTIVE_DATE
    )
    runner_fraction = _minimum_runner_fraction(bar.trade_date)
    evaluated_stage = max(current_stage, target_stage)
    intended_remaining_fraction = (
        max(
            runner_fraction,
            1.0 - sum(step[1] for step in profit_ladder_steps[:evaluated_stage]),
        )
        if evaluated_stage > 0
        else 1.0
    )
    default_current_remaining = max(
        runner_fraction,
        1.0 - sum(step[1] for step in profit_ladder_steps[:current_stage]),
    )
    current_remaining_fraction = float(
        position.get("remaining_fraction")
        if position.get("remaining_fraction") is not None
        else default_current_remaining
    )
    transition_gap = max(0.0, current_remaining_fraction - intended_remaining_fraction)
    should_rebalance_transition = bool(
        tactical_transition
        and evaluated_stage > 0
        and transition_gap > 1e-9
    )

    if target_stage > current_stage or should_rebalance_transition:
        target_stage = evaluated_stage
        trigger_r = profit_ladder_steps[target_stage - 1][0]
        levels["target_stage"] = target_stage
        levels["target_remaining_fraction"] = intended_remaining_fraction
        sell_fraction = max(
            0.0,
            current_remaining_fraction - intended_remaining_fraction,
        )
        if tactical_transition:
            sell_fraction = min(
                sell_fraction,
                MAX_TACTICAL_TRANSITION_SELL_FRACTION,
            )
        levels["sell_fraction"] = sell_fraction
        levels["remaining_after_fraction"] = max(
            runner_fraction,
            current_remaining_fraction - sell_fraction,
        )
        levels["target_price"] = (
            float(position["entry_price"]) + (levels["initial_risk"] * trigger_r)
        )
        transition_label = (
            "안정 수익확정형 전환 · "
            if stable_transition
            else "단기 전술형 전환 · "
            if tactical_transition
            else ""
        )
        if _stable_profit_mode(bar.trade_date):
            target_label = f"{PROFIT_LADDER_STEPS[target_stage - 1][0] * 100:.0f}% 수익"
        else:
            target_label = f"초기 위험의 {trigger_r:.1f}배 수익"
        return (
            True,
            f"{transition_label}{target_label} · {target_stage}차 수익확정",
            levels,
        )
    if current_stage >= len(profit_ladder_steps):
        return False, "수익확정 완료·추세 잔여분 보유", levels
    next_trigger_r = profit_ladder_steps[current_stage][0]
    if _stable_profit_mode(bar.trade_date):
        next_label = f"다음 {PROFIT_LADDER_STEPS[current_stage][0] * 100:.0f}% 수익확정 기준 미도달"
    else:
        next_label = f"다음 {next_trigger_r:.1f}R 수익확정 기준 미도달"
    return False, next_label, levels


def _signal_reason(indicator: dict[str, float], side: str) -> str:
    momentum = indicator["momentum20"] * 100.0
    if side == "buy":
        setup = "조기 추세 전환" if indicator.get("entry_setup") == "early_turn" else "상승 추세"
        return f"{setup}과 20일 흐름 {momentum:+.1f}%가 함께 확인됨"
    return f"추세 점수가 {indicator['score']:.1f}점으로 약화됨"


def _signal_at(signal_date: Optional[date]) -> Optional[datetime]:
    """Return the deterministic end-of-session timestamp for a daily signal."""
    if signal_date is None:
        return None
    return datetime.combine(signal_date, time(15, 40), tzinfo=KST)


def _target_sell_status(actual_price: Optional[float], target_price: Optional[float]) -> Optional[str]:
    if actual_price is None or target_price is None:
        return None
    return "hit" if actual_price >= target_price else "missed"


def _target_sell_delta(actual_price: Optional[float], target_price: Optional[float]) -> Optional[int]:
    if actual_price is None or target_price is None:
        return None
    return _price(actual_price - target_price)


def _simulate(
    bars: list[PriceBar],
    indicators: list[dict[str, float]],
    entry_evidence_by_date: Optional[dict[date, dict[str, Any]]] = None,
    *,
    performance_start_index_override: Optional[int] = None,
) -> dict[str, Any]:
    lifecycle_start_index = WARMUP_ROWS
    performance_start_index = (
        max(WARMUP_ROWS, min(int(performance_start_index_override), len(bars) - 1))
        if performance_start_index_override is not None
        else max(WARMUP_ROWS, len(bars) - BACKTEST_ROWS)
    )
    period_start = bars[performance_start_index].trade_date
    lifecycle_events: list[dict[str, Any]] = []
    lifecycle_trades: list[dict[str, Any]] = []
    pending: Optional[dict[str, Any]] = None
    position: Optional[dict[str, Any]] = None
    cash = 1.0
    shares = 0.0
    marked_equity = 1.0
    performance_base_equity = 1.0
    performance_equity_curve: list[float] = []
    performance_dates: list[date] = []
    performance_exposure_curve: list[float] = []
    drawdown_curve: list[float] = []
    peak_equity = 1.0
    max_drawdown = 0.0
    execution_costs: list[float] = []
    turnover = 0.0
    rejected_entries = 0
    rejected_evidence_entries = 0
    rejected_missing_open_executions = 0
    last_exit_index: Optional[int] = None

    for index in range(lifecycle_start_index, len(bars)):
        bar = bars[index]
        indicator = indicators[index]

        if index == performance_start_index:
            if index > lifecycle_start_index and position:
                previous_bar = bars[index - 1]
                previous_indicator = indicators[index - 1]
                performance_base_equity = cash + (
                    shares * previous_bar.close * (1.0 - _execution_cost(previous_indicator))
                )
            else:
                performance_base_equity = cash
            peak_equity = performance_base_equity

        if pending:
            active_pending = pending
            pending = None
            execution_price = bar.open
            execution_data_available = bar.ohlc_complete
            execution_allowed = execution_data_available and (
                active_pending["side"] != "buy"
                or _entry_execution_allowed(execution_price, active_pending)
            )
            protective_floor = _safe_number(active_pending.get("protective_floor"))
            if (
                active_pending["side"] == "partial_sell"
                and position
                and execution_data_available
                and bar.trade_date >= PROFIT_PRESERVATION_EFFECTIVE_DATE
                and protective_floor is not None
                and execution_price <= protective_floor
            ):
                active_pending = {
                    **active_pending,
                    "side": "sell",
                    "reason": "수익확정 예정 후 시가가 수익 보호선을 하회해 잔여비중 전량 매도",
                    "target_sell_price": protective_floor,
                }
            if not execution_data_available:
                rejected_missing_open_executions += 1
            elif not execution_allowed:
                if index >= performance_start_index and active_pending["side"] == "buy":
                    rejected_entries += 1
            else:
                execution_cost = float(active_pending["execution_cost"])
                if index >= performance_start_index:
                    execution_costs.append(execution_cost)

            if active_pending["side"] == "buy" and execution_allowed:
                strategy_equity_at_entry = cash
                initial_risk = _initial_risk(
                    execution_price,
                    float(active_pending["atr"]),
                    strategy_date=bar.trade_date,
                )
                shares = strategy_equity_at_entry / (execution_price * (1.0 + execution_cost))
                cash = 0.0
                if index >= performance_start_index:
                    turnover += 1.0
                position = {
                    "entry_date": bar.trade_date,
                    "entry_price": execution_price,
                    "entry_index": index,
                    "signal_date": active_pending["signal_date"],
                    "score": active_pending["score"],
                    "entry_setup": active_pending.get("entry_setup") or "trend_continuation",
                    "entry_confirmation": deepcopy(active_pending.get("entry_confirmation")),
                    "entry_cost": execution_cost,
                    "peak_price": execution_price,
                    "initial_stop": max(1.0, execution_price - initial_risk),
                    "initial_risk": initial_risk,
                    "target_sell_price": None,
                    "initial_shares": shares,
                    "entry_equity": strategy_equity_at_entry,
                    "realized_proceeds": 0.0,
                    "gross_realized_value": 0.0,
                    "partial_exit_done": False,
                    "partial_exit_date": None,
                    "partial_exit_price": None,
                    "partial_exits": [],
                    "profit_stage": 0,
                    "remaining_fraction": 1.0,
                    "exit_confirmation_count": 0,
                    "exit_confirmation_reason": None,
                }
                entry_profit_steps = _resolved_profit_ladder_steps(position, bar.trade_date)
                position["target_sell_price"] = execution_price + (
                    initial_risk * entry_profit_steps[0][0]
                )
                lifecycle_events.append(
                    {
                        "signal_date": active_pending["signal_date"],
                        "signal_at": _signal_at(active_pending["signal_date"]),
                        "execution_date": bar.trade_date,
                        "side": "buy",
                        "label": "전략상 진입",
                        "price": _price(execution_price),
                        "entry_price": _price(position["entry_price"]),
                        "target_sell_price": _price(position["target_sell_price"]),
                        "target_sell_status": "planned",
                        "target_sell_delta": None,
                        "score": _decimal(active_pending["score"]),
                        "reason": active_pending["reason"],
                        "entry_setup": position["entry_setup"],
                        "entry_confirmation": deepcopy(position.get("entry_confirmation")),
                        "position_percent": _decimal(100.0),
                        "state_after": "holding",
                    }
                )
            elif active_pending["side"] == "partial_sell" and position and execution_allowed:
                target_sell_price = active_pending.get("target_sell_price") or position.get("target_sell_price")
                execution_profit_steps = _resolved_profit_ladder_steps(position, bar.trade_date)
                requested_stage = max(
                    1,
                    min(
                        int(active_pending.get("target_stage") or 1),
                        len(execution_profit_steps),
                    ),
                )
                target_stage = max(
                    int(position.get("profit_stage") or 0),
                    requested_stage,
                )
                sell_fraction = max(0.0, float(active_pending.get("sell_fraction") or 0.0))
                if sell_fraction <= 0:
                    sell_fraction = execution_profit_steps[target_stage - 1][1]
                sold_shares = min(
                    shares,
                    float(position["initial_shares"]) * sell_fraction,
                )
                sold_fraction = sold_shares / float(position["initial_shares"])
                if index >= performance_start_index:
                    turnover += sold_fraction
                proceeds = sold_shares * execution_price * (1.0 - execution_cost)
                cash += proceeds
                shares -= sold_shares
                position["realized_proceeds"] += proceeds
                position["gross_realized_value"] += sold_shares * execution_price
                position["partial_exit_done"] = True
                position["partial_exit_date"] = bar.trade_date
                position["partial_exit_price"] = execution_price
                position["profit_stage"] = target_stage
                position["remaining_fraction"] = shares / float(position["initial_shares"])
                partial_exit_record = {
                    "stage": target_stage,
                    "execution_date": bar.trade_date,
                    "price": _price(execution_price),
                    "sold_percent": _decimal(sold_fraction * 100.0),
                    "remaining_percent": _decimal(position["remaining_fraction"] * 100.0),
                    "target_price": _price(target_sell_price),
                }
                position["partial_exits"].append(partial_exit_record)
                next_stage = target_stage + 1
                position["target_sell_price"] = (
                    None
                    if next_stage > len(execution_profit_steps)
                    else float(position["entry_price"])
                    + (
                        float(position["initial_risk"])
                        * execution_profit_steps[next_stage - 1][0]
                    )
                )
                lifecycle_events.append(
                    {
                        "signal_date": active_pending["signal_date"],
                        "signal_at": _signal_at(active_pending["signal_date"]),
                        "execution_date": bar.trade_date,
                        "side": "partial_sell",
                        "label": f"{target_stage}차 수익확정",
                        "price": _price(execution_price),
                        "entry_price": _price(position["entry_price"]),
                        "target_sell_price": _price(target_sell_price),
                        "target_sell_status": _target_sell_status(execution_price, target_sell_price),
                        "target_sell_delta": _target_sell_delta(execution_price, target_sell_price),
                        "score": _decimal(active_pending["score"]),
                        "reason": active_pending["reason"],
                        "profit_stage": target_stage,
                        "sold_percent": _decimal(sold_fraction * 100.0),
                        "position_percent": _decimal(position["remaining_fraction"] * 100.0),
                        "state_after": "partially_exited",
                    }
                )
            elif active_pending["side"] == "sell" and position and execution_allowed:
                target_sell_price = active_pending.get("target_sell_price") or position.get("target_sell_price")
                target_stage = active_pending.get("target_stage")
                if target_stage is not None:
                    position["profit_stage"] = max(
                        int(position.get("profit_stage") or 0),
                        int(target_stage),
                    )
                sold_fraction = shares / float(position["initial_shares"])
                if index >= performance_start_index:
                    turnover += sold_fraction
                proceeds = shares * execution_price * (1.0 - execution_cost)
                cash += proceeds
                position["realized_proceeds"] += proceeds
                position["gross_realized_value"] += shares * execution_price
                net_return = (
                    float(position["realized_proceeds"]) / float(position["entry_equity"])
                ) - 1.0
                gross_return = (
                    float(position["gross_realized_value"])
                    / (float(position["initial_shares"]) * float(position["entry_price"]))
                ) - 1.0
                holding_days = max(1, index - int(position["entry_index"]))
                trade = {
                    "entry_date": position["entry_date"],
                    "entry_price": _price(position["entry_price"]),
                    "target_sell_price": _price(target_sell_price),
                    "partial_exit_date": position.get("partial_exit_date"),
                    "partial_exit_price": _price(position.get("partial_exit_price")),
                    "partial_exits": list(position.get("partial_exits") or []),
                    "profit_stage": int(position.get("profit_stage") or 0),
                    "exit_date": bar.trade_date,
                    "exit_price": _price(execution_price),
                    "gross_return": _decimal(gross_return * 100.0),
                    "net_return": _decimal(net_return * 100.0),
                    "holding_days": holding_days,
                    "status": "closed",
                    "exit_reason": active_pending["reason"],
                    "remaining_percent": _decimal(0.0),
                }
                lifecycle_trades.append(trade)
                lifecycle_events.append(
                    {
                        "signal_date": active_pending["signal_date"],
                        "signal_at": _signal_at(active_pending["signal_date"]),
                        "execution_date": bar.trade_date,
                        "side": "sell",
                        "label": "전략상 전량 매도",
                        "price": _price(execution_price),
                        "entry_price": _price(position["entry_price"]),
                        "target_sell_price": _price(target_sell_price),
                        "target_sell_status": _target_sell_status(execution_price, target_sell_price),
                        "target_sell_delta": _target_sell_delta(execution_price, target_sell_price),
                        "score": _decimal(active_pending["score"]),
                        "reason": active_pending["reason"],
                        "return_rate": trade["net_return"],
                        "holding_days": holding_days,
                        "profit_stage": int(position.get("profit_stage") or 0),
                        "position_percent": _decimal(0.0),
                        "state_after": "exited",
                    }
                )
                shares = 0.0
                position = None
                last_exit_index = index

        if position:
            position["peak_price"] = max(position["peak_price"], bar.close)
            marked_equity = cash + (shares * bar.close * (1.0 - _execution_cost(indicator)))
        else:
            marked_equity = cash
        if index >= performance_start_index:
            performance_equity_curve.append(marked_equity)
            performance_dates.append(bar.trade_date)
            market_value = (
                shares * bar.close * (1.0 - _execution_cost(indicator))
                if position
                else 0.0
            )
            performance_exposure_curve.append(
                market_value / marked_equity if marked_equity > 0 else 0.0
            )
            peak_equity = max(peak_equity, marked_equity)
            drawdown = (marked_equity / peak_equity) - 1.0
            drawdown_curve.append(drawdown)
            max_drawdown = min(max_drawdown, drawdown)

        if index >= len(bars) - 1:
            continue
        if position:
            should_exit, reason, exit_levels, is_hard_exit = _full_exit_signal(
                bar,
                indicator,
                position,
                position["peak_price"],
            )
            should_partial, partial_reason, partial_levels = _partial_exit_signal(
                bar,
                indicator,
                position,
                position["peak_price"],
            )
            position["target_sell_price"] = exit_levels.get("next_partial_target")
            holding_bars = index - int(position["entry_index"])
            minimum_holding_bars = _minimum_holding_bars(bar.trade_date)
            confirmation_bars = _exit_confirmation_bars(bar.trade_date)
            normal_exit_eligible = holding_bars >= minimum_holding_bars
            if should_exit and not is_hard_exit and normal_exit_eligible:
                prior_reason = position.get("exit_confirmation_reason")
                position["exit_confirmation_count"] = (
                    int(position.get("exit_confirmation_count") or 0) + 1
                    if prior_reason == reason
                    else 1
                )
                position["exit_confirmation_reason"] = reason
            elif not should_exit or not normal_exit_eligible:
                position["exit_confirmation_count"] = 0
                position["exit_confirmation_reason"] = None

            exit_confirmed = bool(
                should_exit
                and (
                    is_hard_exit
                    or (
                        normal_exit_eligible
                        and int(position.get("exit_confirmation_count") or 0) >= confirmation_bars
                    )
                )
            )
            if exit_confirmed:
                pending = {
                    "side": "sell",
                    "signal_date": bar.trade_date,
                    "score": indicator["score"],
                    "reason": reason if is_hard_exit else f"{reason} 종가 {confirmation_bars}일 연속 확인",
                    "target_sell_price": exit_levels.get("trailing_stop"),
                    "execution_cost": _execution_cost(indicator),
                }
            elif should_partial and not should_exit:
                current_remaining_fraction = float(position.get("remaining_fraction") or 0.0)
                final_profit_exit = bool(
                    _stable_profit_mode(bar.trade_date)
                    and float(partial_levels.get("sell_fraction") or 0.0)
                    >= current_remaining_fraction - 1e-9
                )
                pending = {
                    "side": "sell" if final_profit_exit else "partial_sell",
                    "signal_date": bar.trade_date,
                    "score": indicator["score"],
                    "reason": partial_reason,
                    "target_sell_price": partial_levels.get("target_price"),
                    "target_stage": partial_levels.get("target_stage"),
                    "sell_fraction": partial_levels.get("sell_fraction"),
                    "protective_floor": partial_levels.get("hard_floor"),
                    "profit_exit": final_profit_exit,
                    "execution_cost": _execution_cost(indicator),
                }
        elif _entry_signal(bar, indicator) and (
            last_exit_index is None
            or index - last_exit_index > REENTRY_COOLDOWN_BARS
        ):
            entry_setup = _entry_setup_kind(bar, indicator) or "trend_continuation"
            evidence = (entry_evidence_by_date or {}).get(bar.trade_date)
            confirmation = entry_confirmation_decision(
                evidence,
                entry_setup,
                signal_date=bar.trade_date,
            )
            if confirmation["allowed"]:
                reason_indicator = {**indicator, "entry_setup": entry_setup}
                pending = {
                    "side": "buy",
                    "signal_date": bar.trade_date,
                    "score": indicator["score"],
                    "reason": (
                        f"{_signal_reason(reason_indicator, 'buy')} · "
                        f"{confirmation['reason']}"
                        if confirmation["state"] != "legacy"
                        else _signal_reason(reason_indicator, "buy")
                    ),
                    "entry_setup": entry_setup,
                    "entry_confirmation": confirmation,
                    "atr": indicator["atr"],
                    "signal_price": bar.close,
                    "execution_cost": _execution_cost(indicator),
                }
            elif index >= performance_start_index:
                rejected_evidence_entries += 1

    final_equity = performance_equity_curve[-1] if performance_equity_curve else performance_base_equity

    if position:
        final_cost = _execution_cost(indicators[-1])
        marked_proceeds = shares * bars[-1].close * (1.0 - final_cost)
        current_return = (
            (float(position["realized_proceeds"]) + marked_proceeds) / float(position["entry_equity"])
        ) - 1.0
        gross_return = (
            (float(position["gross_realized_value"]) + shares * bars[-1].close)
            / (float(position["initial_shares"]) * float(position["entry_price"]))
        ) - 1.0
        lifecycle_trades.append(
            {
                "entry_date": position["entry_date"],
                "entry_price": _price(position["entry_price"]),
                "target_sell_price": _price(position.get("target_sell_price")),
                "partial_exit_date": position.get("partial_exit_date"),
                "partial_exit_price": _price(position.get("partial_exit_price")),
                "partial_exits": list(position.get("partial_exits") or []),
                "profit_stage": int(position.get("profit_stage") or 0),
                "exit_date": None,
                "exit_price": None,
                "gross_return": _decimal(gross_return * 100.0),
                "net_return": _decimal(current_return * 100.0),
                "holding_days": max(1, (len(bars) - 1) - int(position["entry_index"])),
                "status": "open",
                "exit_reason": None,
                "remaining_percent": _decimal(float(position["remaining_fraction"]) * 100.0),
            }
        )

    events = [
        event
        for event in lifecycle_events
        if event.get("execution_date") and event["execution_date"] >= period_start
    ]
    trades = [
        trade
        for trade in lifecycle_trades
        if trade.get("status") == "open"
        or (trade.get("exit_date") and trade["exit_date"] >= period_start)
    ]
    closed_trades = [trade for trade in trades if trade["status"] == "closed"]
    winners = [trade for trade in closed_trades if float(trade["net_return"] or 0) > 0]
    net_returns = [float(trade["net_return"] or 0) for trade in closed_trades]
    holding_days = [int(trade["holding_days"] or 0) for trade in closed_trades]
    benchmark = (
        (bars[-1].close / bars[performance_start_index].close) - 1.0
        if len(bars) > performance_start_index
        else 0.0
    )

    daily_returns: list[float] = []
    previous_equity = performance_base_equity
    for equity in performance_equity_curve:
        if previous_equity > 0:
            daily_returns.append((equity / previous_equity) - 1.0)
        previous_equity = equity
    daily_mean = sum(daily_returns) / len(daily_returns) if daily_returns else 0.0
    daily_variance = (
        sum((value - daily_mean) ** 2 for value in daily_returns) / (len(daily_returns) - 1)
        if len(daily_returns) > 1
        else 0.0
    )
    daily_volatility = sqrt(max(0.0, daily_variance))
    annualized_volatility = daily_volatility * sqrt(252.0)
    annualized_return = (
        (final_equity / performance_base_equity) ** (252.0 / len(performance_equity_curve)) - 1.0
        if performance_equity_curve and performance_base_equity > 0 and final_equity > 0
        else 0.0
    )
    risk_adjusted_return = (
        daily_mean / daily_volatility * sqrt(252.0)
        if daily_volatility > 0
        else None
    )
    calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown < 0 else None
    negative_drawdowns = [value for value in drawdown_curve if value < 0]
    average_drawdown = (
        sum(negative_drawdowns) / len(negative_drawdowns)
        if negative_drawdowns
        else 0.0
    )

    monthly_last_equity: dict[tuple[int, int], float] = {}
    for trade_date, equity in zip(performance_dates, performance_equity_curve):
        monthly_last_equity[(trade_date.year, trade_date.month)] = equity
    monthly_returns: list[float] = []
    previous_month_equity = performance_base_equity
    for equity in monthly_last_equity.values():
        if previous_month_equity > 0:
            monthly_returns.append((equity / previous_month_equity) - 1.0)
        previous_month_equity = equity

    completed = len(closed_trades)
    history_complete = len(bars) >= MIN_BACKTEST_HISTORY_ROWS
    sample_state = (
        "sufficient"
        if history_complete and completed >= MIN_COMPLETED_TRADES_FOR_SAMPLE
        else "limited"
    )
    if not history_complete:
        sample_note = (
            f"검증 구간이 {len(performance_equity_curve)}거래일로 1년 기준 {BACKTEST_ROWS}거래일보다 짧아 "
            "안정성을 판단하기 어렵습니다."
        )
    elif completed < MIN_COMPLETED_TRADES_FOR_SAMPLE:
        sample_note = (
            f"최근 {len(performance_equity_curve)}거래일 완료 거래 {completed}회로 "
            f"최소 표본 {MIN_COMPLETED_TRADES_FOR_SAMPLE}회보다 적습니다. 수익률보다 최대 낙폭을 우선 확인하세요."
        )
    else:
        sample_note = (
            f"최근 {len(performance_equity_curve)}거래일 완료 거래 {completed}회의 고정 규칙 모의검증입니다. "
            "실거래 성과를 보장하지 않습니다."
        )
    return {
        "start_index": performance_start_index,
        "lifecycle_start_index": lifecycle_start_index,
        "events": events,
        "lifecycle_events": lifecycle_events,
        "trades": trades,
        "lifecycle_trades": lifecycle_trades,
        "position": position,
        "performance": {
            "period_start": period_start,
            "period_end": bars[-1].trade_date,
            "trading_days": len(performance_equity_curve),
            "history_complete": history_complete,
            "completed_trades": completed,
            "win_rate": _decimal((len(winners) / completed) * 100.0) if completed else None,
            "average_return": _decimal(sum(net_returns) / completed) if completed else None,
            "strategy_return": _decimal(
                ((final_equity / performance_base_equity) - 1.0) * 100.0
                if performance_base_equity > 0
                else 0.0
            ),
            "annualized_return": _decimal(annualized_return * 100.0),
            "annualized_volatility": _decimal(annualized_volatility * 100.0),
            "risk_adjusted_return": _decimal(risk_adjusted_return) if risk_adjusted_return is not None else None,
            "calmar_ratio": _decimal(calmar_ratio) if calmar_ratio is not None else None,
            "benchmark_return": _decimal(benchmark * 100.0),
            "max_return": _decimal(max(net_returns)) if net_returns else None,
            "max_drawdown": _decimal(max_drawdown * 100.0),
            "average_drawdown": _decimal(average_drawdown * 100.0),
            "positive_month_ratio": _decimal(
                sum(1 for value in monthly_returns if value > 0) / len(monthly_returns) * 100.0
            )
            if monthly_returns
            else None,
            "worst_month_return": _decimal(min(monthly_returns) * 100.0) if monthly_returns else None,
            "average_model_exposure_percent": _decimal(
                sum(performance_exposure_curve) / len(performance_exposure_curve) * 100.0
            )
            if performance_exposure_curve
            else _decimal(0.0),
            "turnover_percent": _decimal(turnover * 100.0),
            "execution_count": len(execution_costs),
            "rejected_gap_entries": rejected_entries,
            "rejected_evidence_entries": rejected_evidence_entries,
            "rejected_missing_open_executions": rejected_missing_open_executions,
            "average_holding_days": _decimal(sum(holding_days) / completed, "0.1") if completed else None,
            "transaction_cost_per_side": _decimal(
                (sum(execution_costs) / len(execution_costs) if execution_costs else DEFAULT_EXECUTION_COST_PER_SIDE)
                * 100.0
            ),
            "sample_state": sample_state,
            "minimum_required_trades": MIN_COMPLETED_TRADES_FOR_SAMPLE,
            "sample_note": sample_note,
        },
        "pending": pending,
        "last_exit_index": last_exit_index,
        "bar_count": len(bars),
    }


def _factor_state(score: float) -> str:
    if score >= 0.2:
        return "positive"
    if score <= -0.2:
        return "negative"
    return "neutral"


def _factor_payload(indicator: dict[str, float], bar: PriceBar) -> list[dict[str, Any]]:
    trend_detail = (
        "20일선이 60일선 위이고 기울기도 상승"
        if bar.close > indicator["ema20"] > indicator["ema60"] and indicator["ema20_slope"] > 0
        else "이동평균선의 상승 정렬이 아직 불완전"
    )
    return [
        {
            "key": "trend",
            "label": "추세",
            "score": _decimal(indicator["trend_score"] * 100.0),
            "state": _factor_state(indicator["trend_score"]),
            "detail": trend_detail,
        },
        {
            "key": "momentum",
            "label": "20일 흐름",
            "score": _decimal(indicator["momentum_score"] * 100.0),
            "state": _factor_state(indicator["momentum_score"]),
            "detail": f"20거래일 수익률 {indicator['momentum20'] * 100.0:+.1f}%",
        },
        {
            "key": "breakout",
            "label": "가격 강도",
            "score": _decimal(indicator["breakout_score"] * 100.0),
            "state": _factor_state(indicator["breakout_score"]),
            "detail": f"직전 20일 고점 대비 {indicator['high_distance'] * 100.0:+.1f}%",
        },
        {
            "key": "volume",
            "label": "거래량",
            "score": _decimal(indicator["volume_score"] * 100.0),
            "state": _factor_state(indicator["volume_score"]),
            "detail": f"20일 평균의 {indicator['volume_ratio']:.2f}배",
        },
        {
            "key": "liquidity",
            "label": "유동성",
            "score": _decimal(
                _clamp(
                    indicator["average_trading_value"] / MIN_AVERAGE_TRADING_VALUE * 50.0,
                    0.0,
                    100.0,
                )
            ),
            "state": (
                "positive"
                if indicator["average_trading_value"] >= MIN_AVERAGE_TRADING_VALUE * 4
                else "neutral"
                if indicator["average_trading_value"] >= MIN_AVERAGE_TRADING_VALUE
                else "negative"
            ),
            "detail": f"20일 평균 거래대금 {indicator['average_trading_value'] / 100_000_000:,.0f}억원",
        },
        {
            "key": "volatility",
            "label": "변동성",
            "score": _decimal(indicator["atr_percent"] * 100.0),
            "state": "negative" if indicator["atr_percent"] >= 0.06 else "neutral",
            "detail": f"ATR 기준 일 변동폭 {indicator['atr_percent'] * 100.0:.1f}%",
        },
    ]


def _live_bar(confirmed: list[PriceBar], live_quote: Optional[dict[str, Any]], now: datetime) -> tuple[list[PriceBar], bool]:
    if not confirmed or not live_quote:
        return confirmed, False
    if not _live_quote_is_active_krx_observation(confirmed, live_quote, now):
        return confirmed, False
    live_price = _safe_number(live_quote.get("price"))
    if live_price is None:
        return confirmed, False
    live_date = _live_quote_trade_date(live_quote)
    if live_date is None:
        return confirmed, False
    live_volume = max(0.0, float(live_quote.get("volume") or 0))
    observed_open = _safe_number(live_quote.get("open"))
    observed_high = _safe_number(live_quote.get("high"))
    observed_low = _safe_number(live_quote.get("low"))
    live_ohlc_complete = _has_complete_ohlc(
        observed_open,
        observed_high,
        observed_low,
        live_price,
    ) and live_quote.get("ohlc_complete") is not False
    live_open = observed_open or live_price
    live_high = max(observed_high or live_price, live_open, live_price)
    live_low = min(observed_low or live_price, live_open, live_price)
    live_trading_value = max(
        0.0,
        float(live_quote.get("trading_value") or 0),
        live_price * live_volume,
    )
    bars = list(confirmed)
    if bars[-1].trade_date == live_date:
        previous = bars[-1]
        bars[-1] = PriceBar(
            trade_date=previous.trade_date,
            open=_safe_number(live_quote.get("open")) or previous.open,
            high=max(previous.high, live_high),
            low=min(previous.low, live_low),
            close=live_price,
            volume=live_volume or previous.volume,
            trading_value=max(previous.trading_value, live_trading_value),
            ohlc_complete=previous.ohlc_complete or live_ohlc_complete,
        )
    elif live_date > bars[-1].trade_date:
        if not live_ohlc_complete:
            # A price-only quote may mark an existing position to market, but
            # it cannot stand in for a candle used by ATR or entry/exit rules.
            return confirmed, False
        bars.append(
            PriceBar(
                trade_date=live_date,
                open=live_open,
                high=live_high,
                low=live_low,
                close=live_price,
                volume=live_volume,
                trading_value=live_trading_value,
                ohlc_complete=live_ohlc_complete,
            )
        )
    else:
        return confirmed, False
    return bars, True


def _live_quote_trade_date(live_quote: Optional[dict[str, Any]]) -> Optional[date]:
    """Return an explicitly observed quote business date, never a guessed date."""
    if not live_quote or live_quote.get("trade_date") in (None, ""):
        return None
    value = live_quote.get("trade_date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _live_quote_is_active_krx_observation(
    confirmed: list[PriceBar],
    live_quote: Optional[dict[str, Any]],
    now: datetime,
) -> bool:
    """Accept only a fresh quote from the currently forming KRX session.

    A KIS response without a business date is useful while the regular session
    is active, but its synthetic request date is not a completed candle.  In
    particular it must never replace the previous close after midnight or on a
    weekend, which would change both the displayed price and signal score.
    """
    if not confirmed or not live_quote:
        return False
    current = now.replace(tzinfo=KST) if now.tzinfo is None else now.astimezone(KST)
    live_date = _live_quote_trade_date(live_quote)
    if (
        live_date is None
        or live_date != current.date()
        or live_date <= confirmed[-1].trade_date
        or current.weekday() >= 5
        or not (time(9, 0) <= current.time() < time(15, 40))
    ):
        return False

    trade_date_verified = live_quote.get("trade_date_verified")
    if trade_date_verified is not True:
        if trade_date_verified is not False or live_quote.get("quote_source") != "kis_rest":
            return False
        observed_at = live_quote.get("observed_at")
        if isinstance(observed_at, str):
            try:
                observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            except ValueError:
                observed_at = None
        if isinstance(observed_at, datetime):
            observed_at = (
                observed_at.replace(tzinfo=KST)
                if observed_at.tzinfo is None
                else observed_at.astimezone(KST)
            )
        if not isinstance(observed_at, datetime) or abs((current - observed_at).total_seconds()) > 180:
            return False

    market_session = str(live_quote.get("market_session") or "").lower()
    market_venue = str(live_quote.get("market_venue") or "").upper()
    market_division = str(live_quote.get("market_division") or "").upper()
    return bool(
        is_korea_market_session_date(current.date(), current)
        and latest_completed_korea_market_session_date(current) == confirmed[-1].trade_date
        and "nxt" not in market_session
        and market_venue == "KRX"
        and market_division == "J"
    )


def _live_execution_bars(
    confirmed: list[PriceBar],
    live_quote: Optional[dict[str, Any]],
    now: datetime,
) -> tuple[list[PriceBar], bool]:
    """Append one fail-closed KRX bar used only to execute prior-close orders.

    The forming bar stays last, so ``_simulate`` may execute the prior order at
    its open but cannot create and execute a same-day signal. Price-only,
    stale, pre-market, NXT, halted, and synthetic-date quotes are rejected.
    """
    if not confirmed or not live_quote:
        return confirmed, False
    current = now.replace(tzinfo=KST) if now.tzinfo is None else now.astimezone(KST)
    live_date = _live_quote_trade_date(live_quote)
    trade_date_verified = live_quote.get("trade_date_verified")
    synthetic_kis_date = trade_date_verified is False
    if trade_date_verified is not True and not synthetic_kis_date:
        return confirmed, False
    if synthetic_kis_date:
        observed_at = live_quote.get("observed_at")
        if isinstance(observed_at, str):
            try:
                observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            except ValueError:
                observed_at = None
        if isinstance(observed_at, datetime):
            observed_at = (
                observed_at.replace(tzinfo=KST)
                if observed_at.tzinfo is None
                else observed_at.astimezone(KST)
            )
        quote_is_fresh = bool(
            isinstance(observed_at, datetime)
            and abs((current - observed_at).total_seconds()) <= 180
        )
        if (
            live_quote.get("quote_source") != "kis_rest"
            or not quote_is_fresh
        ):
            return confirmed, False
    if (
        live_date is None
        or live_date != current.date()
        or live_date <= confirmed[-1].trade_date
        or current.weekday() >= 5
        or not (time(9, 0) <= current.time() < time(15, 40))
    ):
        return confirmed, False
    market_session = str(live_quote.get("market_session") or "").lower()
    market_venue = str(live_quote.get("market_venue") or "").upper()
    market_division = str(live_quote.get("market_division") or "").upper()
    if (
        not is_korea_market_session_date(current.date(), current)
        or latest_completed_korea_market_session_date(current) != confirmed[-1].trade_date
        or "nxt" in market_session
        or market_venue != "KRX"
        or market_division != "J"
    ):
        return confirmed, False
    live_price = _safe_number(live_quote.get("price"))
    live_open = _safe_number(live_quote.get("open"))
    live_high = _safe_number(live_quote.get("high"))
    live_low = _safe_number(live_quote.get("low"))
    live_volume = max(0.0, float(live_quote.get("volume") or 0))
    if (
        live_quote.get("ohlc_complete") is False
        or live_volume <= 0
        or not _has_complete_ohlc(live_open, live_high, live_low, live_price)
    ):
        return confirmed, False
    observed, _live_observation = _live_bar(confirmed, live_quote, current)
    if len(observed) != len(confirmed) + 1 or observed[-1].trade_date != live_date:
        return confirmed, False
    return observed, True


def _keyword_score(text: str) -> int:
    score = sum(1 for word in POSITIVE_WORDS if word in text)
    score -= sum(1 for word in NEGATIVE_WORDS if word in text)
    return score


def _compact_krw(value: Optional[int | float]) -> str:
    if value is None:
        return "-"
    number = float(value)
    sign = "+" if number > 0 else "" if number == 0 else "-"
    absolute = abs(number)
    if absolute >= 1_000_000_000_000:
        return f"{sign}{absolute / 1_000_000_000_000:.1f}조원"
    if absolute >= 100_000_000:
        return f"{sign}{absolute / 100_000_000:.0f}억원"
    if absolute >= 10_000:
        return f"{sign}{absolute / 10_000:.0f}만원"
    return f"{number:,.0f}원"


def _context_item(
    key: str,
    label: str,
    state: str,
    summary: str,
    source: str,
    *,
    as_of: Optional[datetime] = None,
    score: Optional[float] = None,
    available: bool = True,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "state": state,
        "summary": summary,
        "source": source,
        "as_of": as_of,
        "score": _decimal(score),
        "available": available,
    }


def _load_current_context(
    db: Session,
    stock: StockMaster,
    rows: list[DailyPrice],
    *,
    live_quote: Optional[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    state_scores: list[int] = []
    naive_utc_now = (
        now.astimezone(timezone.utc).replace(tzinfo=None)
        if now.tzinfo is not None
        else now
    )

    recent_prices = rows[-20:]
    first_flow_date = recent_prices[0].trade_date if recent_prices else now.date() - timedelta(days=45)
    flow_rows = list(
        db.scalars(
            select(InvestorFlow)
            .where(InvestorFlow.code == stock.code)
            .where(InvestorFlow.trade_date >= first_flow_date)
        )
    )
    if flow_rows:
        foreign = sum(
            int(item.net_buy_value or 0)
            for item in flow_rows
            if any(kind in item.investor_type for kind in FOREIGN_TYPES)
        )
        institution = sum(
            int(item.net_buy_value or 0)
            for item in flow_rows
            if any(kind in item.investor_type for kind in INSTITUTION_TYPES)
        )
        flow_score = (1 if foreign > 0 else -1 if foreign < 0 else 0) + (
            1 if institution > 0 else -1 if institution < 0 else 0
        )
        state = "supportive" if flow_score > 0 else "caution" if flow_score < 0 else "neutral"
        latest_flow_date = max(item.trade_date for item in flow_rows)
        evidence.append(
            _context_item(
                "flow",
                "20일 수급",
                state,
                f"외국인 {_compact_krw(foreign)} · 기관 {_compact_krw(institution)}",
                "네이버금융 투자자별 매매동향",
                as_of=datetime.combine(latest_flow_date, time(15, 30), tzinfo=KST),
                score=float(flow_score * 50),
            )
        )
        state_scores.append(1 if flow_score > 0 else -1 if flow_score < 0 else 0)
    else:
        evidence.append(
            _context_item(
                "flow",
                "20일 수급",
                "unavailable",
                "최근 수급 데이터가 아직 없습니다.",
                "네이버금융 투자자별 매매동향",
                available=False,
            )
        )

    news_since = naive_utc_now - timedelta(days=30)
    news_rows = list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.published_at >= news_since)
            .where(or_(NewsItem.title.contains(stock.name), NewsItem.summary.contains(stock.name)))
            .order_by(NewsItem.published_at.desc(), NewsItem.id.desc())
            .limit(40)
        )
    )
    snapshot = db.get(StockNewsSnapshot, stock.code)
    snapshot_items: list[dict[str, Any]] = []
    if snapshot:
        try:
            parsed = json.loads(snapshot.payload)
            if isinstance(parsed, list):
                snapshot_items = [item for item in parsed[:20] if isinstance(item, dict)]
        except (TypeError, ValueError):
            snapshot_items = []
    news_texts = [f"{item.title} {item.summary or ''}" for item in news_rows]
    news_texts.extend(str(item.get("title") or "") for item in snapshot_items)
    if news_texts:
        news_scores = [_keyword_score(text) for text in news_texts]
        positive = sum(1 for score in news_scores if score > 0)
        negative = sum(1 for score in news_scores if score < 0)
        net_news = positive - negative
        state = "supportive" if net_news > 1 else "caution" if net_news < -1 else "neutral"
        latest_news_at = news_rows[0].published_at if news_rows else snapshot.fetched_at if snapshot else None
        evidence.append(
            _context_item(
                "news",
                "30일 뉴스",
                state,
                f"긍정 {positive}건 · 부정 {negative}건 · 중립 {len(news_scores) - positive - negative}건",
                "저장 뉴스 + 네이버금융 종목뉴스",
                as_of=latest_news_at,
                score=float(_clamp(net_news * 10.0, -100.0, 100.0)),
            )
        )
        state_scores.append(1 if net_news > 1 else -1 if net_news < -1 else 0)
    else:
        evidence.append(
            _context_item(
                "news",
                "30일 뉴스",
                "unavailable",
                "판단할 최근 기사가 없습니다.",
                "저장 뉴스 + 네이버금융 종목뉴스",
                available=False,
            )
        )

    report_since = naive_utc_now - timedelta(days=180)
    reports = list(
        db.scalars(
            select(ResearchReport)
            .where(ResearchReport.stock_code == stock.code)
            .where(ResearchReport.published_at >= report_since)
            .order_by(ResearchReport.published_at.asc(), ResearchReport.id.asc())
        )
    )
    if reports:
        revision_up = 0
        revision_down = 0
        prior_by_broker: dict[str, Decimal] = {}
        for report in reports:
            if report.target_price is None:
                continue
            broker = report.broker_name or "unknown"
            previous = prior_by_broker.get(broker)
            if previous is not None:
                revision_up += int(report.target_price > previous)
                revision_down += int(report.target_price < previous)
            prior_by_broker[broker] = report.target_price
        latest = reports[-1]
        opinion = (latest.opinion or "").upper()
        report_score = revision_up - revision_down
        if any(token in opinion for token in ("매수", "BUY", "OUTPERFORM")):
            report_score += 1
        if any(token in opinion for token in ("매도", "SELL", "REDUCE")):
            report_score -= 1
        state = "supportive" if report_score > 0 else "caution" if report_score < 0 else "neutral"
        target_text = f" · 목표가 {_price(float(latest.target_price)):,}원" if latest.target_price else ""
        evidence.append(
            _context_item(
                "research",
                "증권사 리포트",
                state,
                f"180일 {len(reports)}건 · 상향 {revision_up} · 하향 {revision_down}{target_text}",
                "증권사 발간 리포트",
                as_of=latest.published_at,
                score=float(_clamp(report_score * 25.0, -100.0, 100.0)),
            )
        )
        state_scores.append(1 if report_score > 0 else -1 if report_score < 0 else 0)
    else:
        evidence.append(
            _context_item(
                "research",
                "증권사 리포트",
                "unavailable",
                "최근 180일 연결된 리포트가 없습니다.",
                "증권사 발간 리포트",
                available=False,
            )
        )

    disclosure_since = naive_utc_now - timedelta(days=90)
    disclosures = list(
        db.scalars(
            select(DisclosureItem)
            .where(DisclosureItem.stock_code == stock.code)
            .where(DisclosureItem.published_at >= disclosure_since)
            .order_by(DisclosureItem.published_at.desc(), DisclosureItem.id.desc())
            .limit(30)
        )
    )
    if disclosures:
        disclosure_score = sum(_keyword_score(item.report_name) for item in disclosures)
        state = "supportive" if disclosure_score > 0 else "caution" if disclosure_score < 0 else "neutral"
        evidence.append(
            _context_item(
                "disclosure",
                "90일 공시",
                state,
                f"{len(disclosures)}건 · 최근 {disclosures[0].report_name[:44]}",
                "OpenDART 공시",
                as_of=disclosures[0].published_at,
                score=float(_clamp(disclosure_score * 20.0, -100.0, 100.0)),
            )
        )
        state_scores.append(1 if disclosure_score > 0 else -1 if disclosure_score < 0 else 0)
    else:
        evidence.append(
            _context_item(
                "disclosure",
                "90일 공시",
                "unavailable",
                "최근 90일 연결된 공시가 없습니다.",
                "OpenDART 공시",
                available=False,
            )
        )

    trading_values = [
        int(item.trading_value or ((item.close or 0) * (item.volume or 0)))
        for item in recent_prices
        if item.trading_value or (item.close and item.volume)
    ]
    if trading_values:
        average_value = sum(trading_values) / len(trading_values)
        if average_value >= 20_000_000_000:
            liquidity_state = "supportive"
            liquidity_text = "일평균 거래대금이 충분한 편"
            liquidity_score = 1
        elif average_value < 5_000_000_000:
            liquidity_state = "caution"
            liquidity_text = "일평균 거래대금이 낮아 체결 비용 주의"
            liquidity_score = -1
        else:
            liquidity_state = "neutral"
            liquidity_text = "평균적인 체결 여건"
            liquidity_score = 0
        evidence.append(
            _context_item(
                "liquidity",
                "체결 여건",
                liquidity_state,
                f"{liquidity_text} · {_compact_krw(average_value)}",
                "저장 일봉 거래대금",
                as_of=datetime.combine(recent_prices[-1].trade_date, time(15, 30), tzinfo=KST),
                score=float(liquidity_score * 100),
            )
        )
        state_scores.append(liquidity_score)
    else:
        evidence.append(
            _context_item(
                "liquidity",
                "체결 여건",
                "unavailable",
                "거래대금이 없어 유동성 비용은 기본값으로 계산합니다.",
                "저장 일봉 거래대금",
                available=False,
            )
        )

    available_count = sum(1 for item in evidence if item["available"])
    total_score = sum(state_scores)
    if available_count < 2:
        state = "limited"
        label = "확인 근거 부족"
    elif total_score >= 2:
        state = "supportive"
        label = "보조 근거 우호"
    elif total_score <= -2:
        state = "caution"
        label = "보조 근거 주의"
    else:
        state = "mixed"
        label = "보조 근거 혼재"
    return {
        "state": state,
        "label": label,
        "score": _decimal(float(total_score)),
        "available_count": available_count,
        "total_count": len(evidence),
        "note": "수급·뉴스·리포트·공시는 오늘의 확인 근거이며, 과거 신호를 다시 쓰지 않습니다.",
        "evidence": evidence,
    }


def _reentry_cooldown_remaining(
    simulation: dict[str, Any],
    observation_bars: list[PriceBar],
) -> int:
    last_exit_index = simulation.get("last_exit_index")
    if last_exit_index is None or not observation_bars:
        return 0
    elapsed_bars = (len(observation_bars) - 1) - int(last_exit_index)
    return max(0, REENTRY_COOLDOWN_BARS - elapsed_bars + 1)


def _current_signal(
    confirmed: list[PriceBar],
    simulation: dict[str, Any],
    live_quote: Optional[dict[str, Any]],
    now: datetime,
    entry_evidence_by_date: Optional[dict[date, dict[str, Any]]] = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    observation_bars, live_observation = _live_bar(confirmed, live_quote, now)
    indicators = _indicator_rows(observation_bars)
    bar = observation_bars[-1]
    indicator = indicators[-1]
    position = simulation.get("position")
    lifecycle_events = simulation.get("lifecycle_events") or simulation.get("events") or []
    last_event = lifecycle_events[-1] if lifecycle_events else None

    state = "waiting"
    label = "진입 전 관망"
    next_confirmation = "종가에서 진입 조건이 완성되는지 확인"
    reasons: list[str] = []
    stop_reference: Optional[float] = None
    partial_target: Optional[float] = None
    locked_profit_reference: Optional[float] = None
    profit_stage = 0
    pending_profit_stage: Optional[int] = None
    pending_sell_fraction: Optional[float] = None
    expected_remaining_fraction: Optional[float] = None
    partial_exits: list[dict[str, Any]] = []
    entry_setup: Optional[str] = None
    entry_confirmation: Optional[dict[str, Any]] = None
    levels: list[dict[str, Any]] = []
    if position:
        peak_price = max(float(position["peak_price"]), bar.close)
        should_exit, exit_reason, position_levels, is_hard_exit = _full_exit_signal(
            bar, indicator, position, peak_price
        )
        should_partial, partial_reason, partial_levels = _partial_exit_signal(
            bar, indicator, position, peak_price
        )
        stop_reference = position_levels["trailing_stop"]
        partial_target = position_levels["next_partial_target"]
        locked_profit_reference = position_levels["locked_profit_floor"]
        active_profit_steps = position_levels["profit_ladder_steps"]
        profit_stage = int(position.get("profit_stage") or 0)
        partial_exits = list(position.get("partial_exits") or [])
        entry_setup = position.get("entry_setup")
        entry_confirmation = deepcopy(position.get("entry_confirmation"))
        holding_bars = max(0, (len(observation_bars) - 1) - int(position["entry_index"]))
        prior_confirmations = int(position.get("exit_confirmation_count") or 0)
        prior_confirmation_reason = position.get("exit_confirmation_reason")
        minimum_holding_bars = _minimum_holding_bars(bar.trade_date)
        confirmation_bars = _exit_confirmation_bars(bar.trade_date)
        next_confirmation_count = (
            prior_confirmations + 1
            if prior_confirmation_reason == exit_reason
            else 1
        )
        exit_confirmed = bool(
            should_exit
            and (
                is_hard_exit
                or (
                    holding_bars >= minimum_holding_bars
                    and next_confirmation_count >= confirmation_bars
                )
            )
        )
        if exit_confirmed:
            state = "full_exit_pending"
            label = "전량 매도 조건 확인"
            pending_sell_fraction = float(position["remaining_fraction"])
            expected_remaining_fraction = 0.0
            reasons.append(exit_reason if is_hard_exit else f"{exit_reason} 종가 {confirmation_bars}일 연속 확인")
            next_confirmation = "종가에서 이탈이 확정되면 다음 거래일 시가에 남은 비중 전량 매도"
        elif should_exit and not is_hard_exit:
            state = "holding" if not position.get("partial_exit_done") else "partially_exited"
            label = "전량 매도 조건 재확인"
            reasons.append(f"{exit_reason} 1차 확인·다음 종가까지 보유")
            next_confirmation = "다음 종가에서도 이탈하면 남은 비중 전량 매도"
        elif should_partial and bool(
            _stable_profit_mode(bar.trade_date)
            and float(partial_levels.get("sell_fraction") or 0.0)
            >= float(position["remaining_fraction"]) - 1e-9
        ):
            state = "full_exit_pending"
            label = "2차 수익확정·전량 매도 대기"
            pending_stage = int(partial_levels.get("target_stage") or (profit_stage + 1))
            pending_profit_stage = max(1, min(pending_stage, len(active_profit_steps)))
            pending_sell_fraction = float(position["remaining_fraction"])
            expected_remaining_fraction = 0.0
            pending_target = _safe_number(partial_levels.get("target_price"))
            if pending_target is not None:
                partial_target = pending_target
            reasons.append(partial_reason)
            next_confirmation = "종가 기준 +5% 수익확정 후 다음 거래일 시가에 잔여비중 전량 매도"
        elif should_partial:
            state = "partial_exit_pending"
            pending_stage = int(partial_levels.get("target_stage") or (profit_stage + 1))
            pending_profit_stage = max(1, min(pending_stage, len(active_profit_steps)))
            pending_sell_fraction = max(0.0, float(partial_levels.get("sell_fraction") or 0.0))
            pending_target = _safe_number(partial_levels.get("target_price"))
            if pending_target is not None:
                # A tactical strategy migration can jump directly to a later
                # target while limiting the amount sold on any one day.  The
                # pending state must expose that actual target, not the next
                # sequential target implied by the last completed stage.
                partial_target = pending_target
            remaining_after = float(
                partial_levels.get("remaining_after_fraction")
                if partial_levels.get("remaining_after_fraction") is not None
                else max(
                    _minimum_runner_fraction(bar.trade_date),
                    float(position["remaining_fraction"])
                    - float(partial_levels.get("sell_fraction") or 0.0),
                )
            )
            expected_remaining_fraction = remaining_after
            label = f"{pending_profit_stage}차 수익확정 대기"
            reasons.append(partial_reason)
            next_confirmation = (
                "종가 기준 확정 후 다음 거래일 시가에 "
                f"전략 잔여비중을 {remaining_after * 100:.0f}%로 축소"
            )
        elif position.get("partial_exit_done"):
            state = "partially_exited"
            label = f"{profit_stage}차 수익확정 후 보유"
            reasons.append(
                f"수익을 {profit_stage}단계까지 확정하고 잔여비중 "
                f"{float(position['remaining_fraction']) * 100:.0f}%의 상승 추세를 추적 중"
            )
            next_confirmation = (
                (
                    f"다음 {PROFIT_LADDER_STEPS[profit_stage][0] * 100:.0f}% 수익확정과 보호선을 확인"
                    if position_levels["profit_ladder_mode"] == "fixed_percent"
                    else f"다음 {active_profit_steps[profit_stage][0]:.1f}R 수익확정과 보호선을 확인"
                )
                if profit_stage < len(active_profit_steps)
                else f"남은 {_minimum_runner_fraction(bar.trade_date) * 100:.0f}%는 고점 대비 변동성 추적선으로 상승 추세를 끝까지 추적"
            )
        elif position["entry_date"] == confirmed[-1].trade_date:
            state = "entered"
            label = "전략상 진입 완료"
            reasons.append("전일 종가 신호를 다음 거래일 시가에 반영함")
            next_confirmation = "초기 위험선과 1차 계단형 수익확정 기준을 매일 확인"
        else:
            state = "holding"
            label = "전략상 보유 중"
            reasons.append("추세가 유지되고 계단형 수익확정·전량 매도 기준은 미도달")
            next_confirmation = "1차 수익확정 가격과 변동성 추적선을 매일 확인"

        if partial_target is not None:
            next_stage = pending_profit_stage or (profit_stage + 1)
            next_stage = max(1, min(next_stage, len(active_profit_steps)))
            trigger_r, configured_sell_fraction, _locked_r, _trailing_atr = active_profit_steps[
                next_stage - 1
            ]
            target_remaining_fraction = max(
                _minimum_runner_fraction(bar.trade_date),
                1.0 - sum(step[1] for step in active_profit_steps[:next_stage]),
            )
            sell_fraction = (
                pending_sell_fraction
                if pending_sell_fraction is not None and pending_sell_fraction > 0
                else max(
                    0.0,
                    float(position["remaining_fraction"]) - target_remaining_fraction,
                )
                or configured_sell_fraction
            )
            target_condition_prefix = (
                f"{PROFIT_LADDER_STEPS[next_stage - 1][0] * 100:.0f}% 수익에서 원래 비중의 "
                if position_levels["profit_ladder_mode"] == "fixed_percent"
                else f"초기 위험의 {trigger_r:.1f}배 수익에서 원래 비중의 "
            )
            levels.append(
                {
                    "key": "partial_exit",
                    "label": f"{next_stage}차 수익확정",
                    "price": _price(partial_target),
                    "condition": f"{target_condition_prefix}{sell_fraction * 100:.0f}% 매도",
                }
            )
        levels.append(
            {
                "key": "full_exit",
                "label": "수익 보호·전량 매도선" if position_levels["profit_protection_active"] else "초기 위험선",
                "price": _price(stop_reference),
                "condition": (
                    "수익 보호선·초기 위험선 이탈은 즉시, "
                    f"일반 추세 이탈은 종가 {confirmation_bars}일 확인"
                ),
            }
        )
    elif (reentry_wait_bars := _reentry_cooldown_remaining(simulation, observation_bars)) > 0:
        state = "exited"
        label = "전량 매도 후 재진입 유예"
        reasons.append(
            f"전량 매도 후 재진입 유예 {REENTRY_COOLDOWN_BARS}거래일을 적용 중"
        )
        next_confirmation = f"약 {reentry_wait_bars}거래일 뒤 새 매수 조건을 다시 확인"
    elif _entry_signal(bar, indicator):
        entry_setup = _entry_setup_kind(bar, indicator)
        reason_indicator = {**indicator, "entry_setup": entry_setup}
        evidence = (entry_evidence_by_date or {}).get(bar.trade_date)
        entry_confirmation = entry_confirmation_decision(
            evidence,
            entry_setup,
            signal_date=bar.trade_date,
        )
        if entry_confirmation["allowed"]:
            state = "entry_pending"
            label = "매수 조건 확정"
            reasons.append(_signal_reason(reason_indicator, "buy"))
            if entry_confirmation["state"] != "legacy":
                reasons.append(str(entry_confirmation["reason"]))
            next_confirmation = "독립 근거 확인 후 다음 거래일 시가의 갭 범위를 확인해 매수"
        else:
            state = "entry_watch"
            label = (
                "신규매수 차단"
                if entry_confirmation["state"] == "blocked"
                else "매수 근거 확인 중"
            )
            reasons.append(f"가격 조건은 충족했지만 {entry_confirmation['reason']}")
            next_confirmation = str(entry_confirmation["reason"])
        levels.append(
            {
                "key": "entry" if entry_confirmation["allowed"] else "entry_evidence",
                "label": "진입 확인선" if entry_confirmation["allowed"] else "독립 근거 확인",
                "price": _price(max(indicator["ema20"], indicator["prior_high"])),
                "condition": (
                    f"기존 추세·조기 전환 {ENTRY_SCORE:.0f}점 이상·"
                    "5일 흐름 0% 이상·거래량 20일 평균의 0.8배 이상·"
                    f"ATR {MAX_ENTRY_ATR_PERCENT * 100:.1f}% 이하·"
                    f"20일선 이격 {MAX_ENTRY_EXTENSION_ATR:.1f}ATR 이하·"
                    f"20일 평균 거래대금 {MIN_AVERAGE_TRADING_VALUE / 100_000_000:.0f}억원 이상"
                ),
            }
        )
    elif _pre_entry_signal(bar, indicator):
        state = "entry_watch"
        label = "예비 매수 포착"
        reasons.append(
            f"5일 흐름 {indicator.get('momentum5', 0.0) * 100:+.1f}%·"
            "단기 추세가 먼저 개선되어 조기 전환을 관찰 중"
        )
        next_confirmation = _pre_entry_next_confirmation(bar, indicator)
        levels.append(
            {
                "key": "entry_watch",
                "label": "다음 매수 확인",
                "price": _price(max(indicator["ema10"], indicator["ema20"])),
                "condition": next_confirmation,
            }
        )
    else:
        reasons.append(
            f"예비 기준 {PRE_ENTRY_SCORE:.0f}점 또는 매수 확정 조건을 아직 충족하지 않음"
        )
        if last_event and last_event.get("side") == "sell":
            state = "exited"
            label = "전량 매도 후 관망"
            exit_reason = last_event.get("reason") or "전량 매도 기준 충족"
            reasons[0] = f"{exit_reason} 판단으로 전략 포지션이 0%가 됨"

    reasons.append(f"종합 신호 {indicator['score']:.1f}점")
    current_price = (
        _safe_number(live_quote.get("price"))
        if live_observation and live_quote
        else None
    )
    current_price = current_price or bar.close
    entry_price = float(position["entry_price"]) if position else None
    unrealized_return = None
    return_basis = None
    holding_days = None
    if position and entry_price:
        current_cost = _execution_cost(indicator)
        remaining_shares = float(position["initial_shares"]) * float(position["remaining_fraction"])
        marked_proceeds = remaining_shares * current_price * (1.0 - current_cost)
        unrealized_return = (
            (float(position["realized_proceeds"]) + marked_proceeds) / float(position["entry_equity"])
        ) - 1.0
        # The return is affine in the live price while the current signal bar is
        # active.  Exposing that slope lets the UI apply every WebSocket quote
        # without dropping the strategy's entry/exit costs or partial proceeds.
        return_basis = {
            "price": _price(current_price),
            "return_rate": _decimal(unrealized_return * 100.0, "0.00000001"),
            "return_rate_per_price": _decimal(
                remaining_shares
                * (1.0 - current_cost)
                / float(position["entry_equity"])
                * 100.0,
                "0.00000001",
            ),
        }
        holding_days = max(1, (len(observation_bars) - 1) - int(position["entry_index"]))

    stage_index = {
        "waiting": 0,
        "entry_watch": 1,
        "entry_pending": 2,
        "entered": 3,
        "holding": 3,
        "partial_exit_pending": 4,
        "partially_exited": 4,
        "full_exit_pending": 5,
        "exited": 5,
    }[state]
    latest_transition = None
    if last_event:
        latest_transition = {
            "label": last_event.get("label"),
            "side": last_event.get("side"),
            "signal_at": last_event.get("signal_at"),
            "signal_date": last_event.get("signal_date"),
            "transition_date": last_event.get("execution_date"),
            "price": last_event.get("price"),
            "entry_price": last_event.get("entry_price"),
            "target_sell_price": last_event.get("target_sell_price"),
            "target_sell_status": last_event.get("target_sell_status"),
            "target_sell_delta": last_event.get("target_sell_delta"),
            "profit_stage": last_event.get("profit_stage"),
            "sold_percent": last_event.get("sold_percent"),
        }
    if position:
        target_sell_price = partial_target
        target_sell_status = "planned" if partial_target is not None else None
        target_sell_delta = None
    elif state in {"entry_watch", "entry_pending"}:
        # A new entry has not executed yet.  The latest lifecycle transition can
        # still describe the previous closed trade, but its target/outcome must
        # never become the target for this pending entry.
        target_sell_price = None
        target_sell_status = None
        target_sell_delta = None
    else:
        target_sell_price = last_event.get("target_sell_price") if last_event else None
        target_sell_status = last_event.get("target_sell_status") if last_event else None
        target_sell_delta = last_event.get("target_sell_delta") if last_event else None

    return (
        {
            "action": state,
            "label": label,
            "score": _decimal(indicator["score"]),
            "price": _price(current_price),
            "as_of": now,
            "live_observation": live_observation,
            "position_open": bool(position),
            "model_exposure_percent": _decimal(
                float(position["remaining_fraction"]) * 100.0 if position else 0.0
            ),
            "lifecycle": {
                "state": state,
                "label": label,
                "stage_index": stage_index,
                "stages": ["관망", "예비 포착", "매수 대기", "보유", "수익확정", "전량 매도"],
                "latest_transition": latest_transition,
            },
            "entry_date": position["entry_date"] if position else None,
            "entry_price": _price(entry_price),
            "target_sell_price": _price(target_sell_price),
            "target_sell_status": target_sell_status,
            "target_sell_delta": target_sell_delta,
            "partial_exit_date": position.get("partial_exit_date") if position else None,
            "partial_exit_price": _price(position.get("partial_exit_price")) if position else None,
            "partial_exits": partial_exits,
            "profit_stage": profit_stage,
            "pending_profit_stage": pending_profit_stage,
            "pending_sell_percent": (
                _decimal(pending_sell_fraction * 100.0)
                if pending_sell_fraction is not None
                else None
            ),
            "expected_remaining_percent": (
                _decimal(expected_remaining_fraction * 100.0)
                if expected_remaining_fraction is not None
                else None
            ),
            "profit_steps_total": len(active_profit_steps) if position else len(PROFIT_LADDER_STEPS),
            "entry_setup": entry_setup,
            "entry_confirmation": entry_confirmation,
            "holding_days": holding_days,
            "unrealized_return": _decimal(unrealized_return * 100.0) if unrealized_return is not None else None,
            "return_basis": return_basis,
            "stop_reference": _price(stop_reference),
            "locked_profit_reference": _price(locked_profit_reference),
            "partial_exit_reference": _price(partial_target),
            "levels": levels,
            "reasons": reasons,
            "next_confirmation": next_confirmation,
        },
        _factor_payload(indicator, bar),
    )


def build_quant_signal_payload(
    stock: StockMaster,
    rows: list[DailyPrice],
    *,
    live_quote: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
    context: Optional[dict[str, Any]] = None,
    entry_evidence_by_date: Optional[dict[date, dict[str, Any]]] = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(KST)
    bars = _normalize_prices(rows)
    confirmed = _confirmed_bars(bars, current_time)
    source_data_rows = len(confirmed)
    incomplete_ohlc = [bar for bar in confirmed if not bar.ohlc_complete]
    latest_incomplete_date = incomplete_ohlc[-1].trade_date if incomplete_ohlc else None
    if incomplete_ohlc:
        last_incomplete_index = max(
            index for index, bar in enumerate(confirmed) if not bar.ohlc_complete
        )
        complete_suffix = confirmed[last_incomplete_index + 1 :]
    else:
        complete_suffix = confirmed
    current_context = context or {
        "state": "limited",
        "label": "확인 근거 부족",
        "score": None,
        "available_count": 0,
        "total_count": 0,
        "note": "가격·거래량 외 보조 데이터가 없습니다.",
        "evidence": [],
    }
    price_through = complete_suffix[-1].trade_date if complete_suffix else None
    completed_target = latest_completed_korea_market_session_date(current_time)
    placeholder_rows = [row for row in rows if _is_non_trading_placeholder_row(row)]
    latest_placeholder_date = max(
        (row.trade_date for row in placeholder_rows),
        default=None,
    )
    non_trading_state = bool(
        price_through
        and completed_target
        and price_through < completed_target
        and latest_placeholder_date
        and latest_placeholder_date >= completed_target
    )
    base = {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        **investment_sector_fields(stock.sector, stock.industry),
        "as_of": current_time,
        "strategy_name": STRATEGY_NAME,
        "strategy_version": STRATEGY_VERSION,
        "candidate_strategy_version": CANDIDATE_STRATEGY_VERSION,
        "strategy_version_history": [dict(item) for item in STRATEGY_VERSION_HISTORY],
        "entry_filter_version": ENTRY_FILTER_VERSION,
        "entry_filter_effective_date": ENTRY_FILTER_EFFECTIVE_DATE,
        "entry_filter_shadow_versions": list(ENTRY_FILTER_SHADOW_VERSIONS),
        "profit_preservation_effective_date": PROFIT_PRESERVATION_EFFECTIVE_DATE,
        "tactical_exit_effective_date": TACTICAL_EXIT_EFFECTIVE_DATE,
        "entry_score_threshold": _decimal(ENTRY_SCORE),
        "source": (
            "저장 일봉 + KIS 실시간 현재가 + 정규화 수급·실적·리포트·Yahoo/네이버 시장지수·공시"
            if live_quote
            else "저장 일봉 + 정규화 수급·실적·리포트·Yahoo/네이버 시장지수·공시"
        )
        if context is not None or entry_evidence_by_date
        else ("저장 일봉 + KIS 실시간 현재가" if live_quote else "저장 일봉"),
        "data_rows": len(complete_suffix),
        "price_through": price_through,
        "trading_state": "non_trading" if non_trading_state else "active",
        "trading_state_label": "거래정지·무거래 확인" if non_trading_state else "정상 거래",
        "confirmation": current_context,
        "methodology": [
            "EMA 10·20·60일, 5·10·20일 흐름, 20일 고점, 거래량, ATR14를 동일 규칙으로 계산합니다.",
            "각 종목은 관망→예비 포착→매수 대기→보유→+3%·+5% 수익확정→전량 매도로 전환합니다.",
            "수익률은 종목별 매수가·각 수익확정가·최종 매도가와 거래비용만으로 계산합니다.",
            "신호는 종가에서 판정하고 다음 거래일의 검증된 KRX 실제 시가에 즉시 반영하여 미래 가격을 참조하지 않습니다.",
            "시가·고가·저가·종가가 모두 확인된 일봉만 신호와 다음 시가 체결 계산에 사용합니다.",
            f"{STABLE_PROFIT_EFFECTIVE_DATE.isoformat()}부터 +3%에서 50%, +5%에서 잔여 50%를 수익확정하고 수익이 큰 종목도 빠르게 전량 확정합니다.",
            f"{PROFIT_PRESERVATION_EFFECTIVE_DATE.isoformat()}의 2R·4R·6R 규칙과 그 이전 3R·5R·8R 이력은 각 결정일 기준으로 보존하고 소급해 바꾸지 않습니다.",
            f"기존 보유 종목을 단기 전술형으로 전환할 때는 하루 최대 {MAX_TACTICAL_TRANSITION_SELL_FRACTION * 100:.0f}%만 수익확정합니다.",
            "기존 v7.1 보유 종목이 이미 확보한 더 높은 수익 보호선은 v7.2 전환 후에도 낮추지 않습니다.",
            f"최초 위험폭은 ATR을 사용하되 매수가의 {MAX_INITIAL_RISK_PERCENT * 100:.0f}% 이내로 제한합니다.",
            f"초기·수익 보호선의 종가 이탈은 확인 대기 없이 다음 거래일 시가에 전량 매도하고, 일반 추세 이탈은 최소 {MIN_HOLDING_BARS}거래일 후 종가 1회로 확인합니다.",
            f"기준 v7.4 신규 진입은 {ENTRY_SCORE:.0f}점 이상과 5일 흐름 0% 이상·거래량 20일 평균의 0.8배 이상, ATR {MAX_ENTRY_ATR_PERCENT * 100:.1f}% 이하·20일선 이격 {MAX_ENTRY_EXTENSION_ATR:.1f}ATR 이하·20일 평균 거래대금 {MIN_AVERAGE_TRADING_VALUE / 100_000_000:.0f}억원 이상을 요구합니다.",
            f"후보 {CANDIDATE_STRATEGY_VERSION}의 활성 H1 매수필터는 {ENTRY_FILTER_EFFECTIVE_DATE.isoformat()}부터 5일 흐름 {0.5:.1f}% 이상·거래량 20일 평균의 {1.0:.1f}배 이상을 추가 요구하며, H2·H3({', '.join(ENTRY_FILTER_SHADOW_VERSIONS)})는 백엔드 비교만 수행합니다.",
            f"{ENTRY_EVIDENCE_EFFECTIVE_DATE.isoformat()}부터 가격 조건 뒤 실적·컨센서스, 시장·섹터 상대강도, 거래대금 정규화 수급을 독립 확인하며 기존 추세는 우호 근거 1개, 조기 전환은 2개를 요구합니다.",
            "OpenDART 중대 위험 공시와 시장 급락·고변동 국면은 점수와 무관하게 신규매수를 보류합니다.",
            "외부 근거는 종목·신호일·전략 버전별 스냅샷으로 고정하여 나중 데이터가 과거 매수 판단을 바꾸지 못하게 합니다.",
            f"매수 확정 전에는 {PRE_ENTRY_SCORE:.0f}점 이상·단기 흐름 개선 종목을 예비 포착으로 분리해 다음 부족 조건을 표시합니다.",
            f"종가 신호 뒤 다음 시가가 {MAX_ENTRY_GAP_ATR:.1f}ATR 또는 {MAX_ENTRY_GAP_PERCENT * 100:.0f}% 범위를 벗어나면 오래된 진입 주문을 취소합니다.",
            "매수가 대비 +2%에 도달하면 매수·매도 예상 비용을 반영한 수익 보호선을 적용합니다.",
            "수익확정 예정 다음 시가가 이미 수익 보호선 아래면 소량만 매도하지 않고 잔여비중을 전량 매도합니다.",
            f"전량 매도 후 {REENTRY_COOLDOWN_BARS}거래일은 동일 종목 재진입을 유예해 반복 매매를 줄입니다.",
            "거래대금과 변동성에 따라 양방향 체결비용을 0.125%~0.50%로 차등 반영합니다.",
            "뉴스 키워드 수는 설명용으로만 유지하며 확정매수 점수에는 사용하지 않습니다.",
        ],
        "applied_principles": [
            "실시간·백테스트에서 같은 신호 함수 사용",
            "슬라이딩 윈도우와 상태 순차 갱신",
            "목표 보유비중과 현재 비중의 차이로 상태 전환",
            "변동성 위험선·+3%/+5% 고정 수익확정·잔여 비중 최소화",
            "유동성·변동성을 반영한 체결비용",
            "종목별 매수·단계별 수익확정·전량 매도 가격을 반영한 손익률",
            "장기 상태 프리롤 후 최근 252거래일 성과만 분리 측정",
            "미래 참조 방지와 모든 종목 동일 규칙",
            "가격과 독립적인 매수 근거의 시점별 고정·최신성 검증",
            "수급 금액의 거래대금 정규화와 시장·섹터 비교 기준 통일",
            "버전이 고정된 소수 매개변수로 결과 재현",
            "수익률뿐 아니라 최대 낙폭과 표본 수를 함께 검증",
            "거래비용 차감 수익률·회전율·최대 낙폭을 동시 검증",
        ],
        "excluded_principles": [
            "호가잔량 마이크로프라이스는 실시간 호가 이력이 없어 미적용",
            "VWAP·TWAP 주문 분할은 실제 주문 수량·체결 이력이 없어 미적용",
            "Kelly 최적화·공분산 포트폴리오 배분은 종목별 시그널 범위 밖이므로 미적용",
            "대체데이터·머신러닝 신호는 시점별 학습 데이터가 검증되지 않아 미적용",
            "시장 전체 백테스트의 생존편향 검증은 상장폐지 종목 이력이 완비되지 않아 미적용",
        ],
        "disclaimer": "교육·연구용 참고 신호이며 실제 주문이나 수익을 보장하지 않습니다.",
    }
    if source_data_rows < MIN_HISTORY_ROWS:
        result = {
            **base,
            "data_state": "insufficient",
            "data_message": f"신호 계산에는 최소 {MIN_HISTORY_ROWS}거래일이 필요합니다. 현재 {source_data_rows}거래일입니다.",
            "current": None,
            "performance": None,
            "factors": [],
            "events": [],
            "trades": [],
        }
        result.update(quant_signal_display_return_fields(result))
        return result

    if incomplete_ohlc and len(complete_suffix) < MIN_HISTORY_ROWS:
        result = {
            **base,
            "data_state": "incomplete",
            "data_message": (
                "시가·고가·저가가 불완전한 일봉 "
                f"{len(incomplete_ohlc)}건(최근 {latest_incomplete_date})을 발견해 "
                f"그 이후의 완전한 일봉 {len(complete_suffix)}건만으로는 신호를 계산할 수 없습니다. "
                "가격 이력을 보강한 뒤 다시 계산합니다."
            ),
            "current": None,
            "performance": None,
            "factors": [],
            "events": [],
            "trades": [],
        }
        result.update(quant_signal_display_return_fields(result))
        return result

    # A stale close-only row must not invalidate hundreds of newer, verified
    # candles.  Keep execution and ATR calculations strict by discarding the
    # history through the final incomplete candle and using only the latest
    # contiguous complete-OHLC window.
    confirmed = complete_suffix
    indicators = _indicator_rows(confirmed)
    evidence_timeline = entry_evidence_by_date or {}
    historical_simulation = _simulate(confirmed, indicators, evidence_timeline)
    simulation_bars, live_execution = _live_execution_bars(
        confirmed,
        live_quote,
        current_time,
    )
    if live_execution:
        simulation = _simulate(
            simulation_bars,
            _indicator_rows(simulation_bars),
            evidence_timeline,
            performance_start_index_override=historical_simulation["start_index"],
        )
        # A forming candle may execute yesterday's order, but it must not
        # change the completed-candle backtest until the session is complete.
        simulation["performance"] = historical_simulation["performance"]
    else:
        simulation = historical_simulation
    current, factors = _current_signal(
        simulation_bars,
        simulation,
        live_quote,
        current_time,
        evidence_timeline,
    )
    latest_signal_date = confirmed[-1].trade_date
    confirmation_signal_date = latest_signal_date
    if current.get("live_observation") and live_quote:
        live_date_value = live_quote.get("trade_date")
        if isinstance(live_date_value, datetime):
            confirmation_signal_date = live_date_value.date()
        elif isinstance(live_date_value, date):
            confirmation_signal_date = live_date_value
        elif live_date_value:
            try:
                confirmation_signal_date = date.fromisoformat(str(live_date_value)[:10])
            except ValueError:
                confirmation_signal_date = current_time.date()
    latest_setup = current.get("entry_setup") or _entry_setup_kind(
        confirmed[-1],
        indicators[-1],
    )
    if confirmation_signal_date >= ENTRY_EVIDENCE_EFFECTIVE_DATE:
        base["confirmation"] = confirmation_response_payload(
            evidence_timeline.get(confirmation_signal_date),
            setup=latest_setup,
            signal_date=confirmation_signal_date,
        )
    result = {
        **base,
        "data_state": "ready",
        "data_message": (
            (
                f"마지막 정상 거래일 {price_through.isoformat()} 기준으로 계산했습니다. "
                "거래정지 또는 무거래 구간의 종가 반복 행은 신호 산출에서 제외했습니다."
            )
            if non_trading_state
            else f"{len(confirmed)}거래일로 계산했습니다."
            if not incomplete_ohlc
            else (
                f"최근의 완전한 일봉 {len(confirmed)}거래일로 계산했습니다. "
                f"그보다 오래된 불완전 일봉 {len(incomplete_ohlc)}건은 제외했습니다."
            )
        ),
        "current": current,
        "performance": simulation["performance"],
        "factors": factors,
        "events": simulation["events"],
        "trades": list(reversed(simulation["trades"][-12:])),
    }
    result.update(quant_signal_display_return_fields(result))
    return result


def quant_signal_display_return_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve the one return value shared by the signal list and stock detail.

    An open position is always marked to market.  Once the position is closed,
    the latest completed trade return becomes the canonical display value.  A
    pending entry has neither an execution price nor a return, so the previous
    closed trade must not leak into that new signal.  Keeping this decision on
    the server prevents each client surface from choosing a different event or
    return basis.
    """
    empty = {
        "display_return_rate": None,
        "display_return_kind": None,
        "display_return_event_date": None,
        "display_return_event_side": None,
    }
    current = payload.get("current")
    if (
        isinstance(current, dict)
        and current.get("action") in {"entry_watch", "entry_pending"}
        and not current.get("position_open")
    ):
        return empty
    if isinstance(current, dict) and current.get("position_open"):
        return_rate = current.get("unrealized_return")
        if return_rate is not None:
            transition = (
                current.get("lifecycle", {}).get("latest_transition", {})
                if isinstance(current.get("lifecycle"), dict)
                else {}
            )
            return {
                "display_return_rate": return_rate,
                "display_return_kind": "open_position",
                "display_return_event_date": (
                    transition.get("transition_date")
                    or current.get("partial_exit_date")
                    or current.get("entry_date")
                ),
                "display_return_event_side": transition.get("side") or "buy",
            }

    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        if event.get("side") != "sell" or event.get("return_rate") is None:
            continue
        return {
            "display_return_rate": event.get("return_rate"),
            "display_return_kind": "closed_trade",
            "display_return_event_date": event.get("execution_date"),
            "display_return_event_side": "sell",
        }
    return empty


CURRENT_PRELIMINARY_ACTIONS = {
    "entry_watch",
    "entry_pending",
    "partial_exit_pending",
    "full_exit_pending",
}
PENDING_ENTRY_ACTIONS = {"entry_watch", "entry_pending"}


def _signal_date_value(*values: Any) -> Optional[date]:
    for value in values:
        if isinstance(value, datetime):
            candidate = value
            if candidate.tzinfo is not None:
                candidate = candidate.astimezone(KST)
            return candidate.date()
        if isinstance(value, date):
            return value
        raw = str(value or "").strip()[:10]
        if not raw:
            continue
        try:
            return date.fromisoformat(raw)
        except ValueError:
            continue
    return None


def quant_signal_current_summary_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return one immutable list-row contract for the stock's current state.

    Stock detail keeps the full event ledger, while account/watchlist responses
    need a compact row.  Building that row from the same canonical transition
    prevents clients from substituting a live quote timestamp for the actual
    signal date or resurrecting metrics from a previous closed trade.
    """

    result = sanitize_pending_entry_signal_payload(payload)
    current = result.get("current") if isinstance(result.get("current"), dict) else {}
    lifecycle = current.get("lifecycle") if isinstance(current.get("lifecycle"), dict) else {}
    transition = (
        lifecycle.get("latest_transition")
        if isinstance(lifecycle.get("latest_transition"), dict)
        else {}
    )
    events = result.get("events") if isinstance(result.get("events"), list) else []
    latest_event = events[-1] if events and isinstance(events[-1], dict) else {}
    if not transition:
        transition = latest_event

    action = str(current.get("action") or "")
    preliminary = action in CURRENT_PRELIMINARY_ACTIONS
    pending_entry = action in PENDING_ENTRY_ACTIONS and not current.get("position_open")
    if action in PENDING_ENTRY_ACTIONS:
        side = "buy"
        event_side = "buy"
    elif action in {"partial_exit_pending", "full_exit_pending"}:
        side = "sell"
        event_side = "partial_sell" if action == "partial_exit_pending" else "sell"
    else:
        event_side = str(transition.get("side") or latest_event.get("side") or "")
        side = "buy" if event_side == "buy" else "sell" if event_side in {"partial_sell", "sell"} else ""

    live_preliminary = bool(preliminary and current.get("live_observation"))
    signal_date = (
        _signal_date_value(
            *(
                (
                    current.get("as_of"),
                    result.get("as_of"),
                    result.get("price_through"),
                )
                if live_preliminary
                else (
                    result.get("price_through"),
                    current.get("as_of"),
                    result.get("as_of"),
                )
            )
        )
        if preliminary
        else _signal_date_value(
            transition.get("signal_date"),
            latest_event.get("signal_date"),
            transition.get("signal_at"),
        )
    )
    execution_date = None if preliminary else _signal_date_value(
        transition.get("transition_date"),
        latest_event.get("execution_date"),
    )
    signal_at = (
        (
            current.get("as_of") or result.get("as_of") or signal_date
            if live_preliminary
            else _signal_at(signal_date) or signal_date
        )
        if preliminary
        else transition.get("signal_at") or latest_event.get("signal_at") or signal_date
    )
    # ``build_quant_signal_payload`` already resolves the canonical return
    # shown by stock detail (including a fresh intraday mark for an open
    # position).  Recomputing it from the compact event list can accidentally
    # replace that value with an older closed-trade return, so the list summary
    # copies the canonical fields whenever they are present.  Pending entries
    # are safe because ``sanitize_pending_entry_signal_payload`` clears these
    # fields before this point.
    display_field_names = (
        "display_return_rate",
        "display_return_kind",
        "display_return_event_date",
        "display_return_event_side",
    )
    if any(field in result for field in display_field_names):
        display_fields = {field: result.get(field) for field in display_field_names}
    else:
        display_fields = quant_signal_display_return_fields(result)
    display_return_rate = display_fields.get("display_return_rate")
    entry_price = None if pending_entry else next(
        (
            value
            for value in (
                current.get("entry_price"),
                transition.get("entry_price"),
                latest_event.get("entry_price"),
            )
            if value is not None
        ),
        None,
    )
    target_sell_price = None if pending_entry else (
        current.get("target_sell_price")
        or current.get("partial_exit_reference")
        or transition.get("target_sell_price")
        or latest_event.get("target_sell_price")
    )
    target_sell_status = None if pending_entry else (
        current.get("target_sell_status")
        or transition.get("target_sell_status")
        or latest_event.get("target_sell_status")
    )
    target_sell_delta = None if pending_entry else next(
        (
            value
            for value in (
                current.get("target_sell_delta"),
                transition.get("target_sell_delta"),
                latest_event.get("target_sell_delta"),
            )
            if value is not None
        ),
        None,
    )
    signal_origin = transition.get("signal_origin") or current.get("signal_origin")
    reconciliation_id = transition.get("reconciliation_id") or current.get("reconciliation_id")

    return {
        "strategy_version": result.get("strategy_version") or STRATEGY_VERSION,
        "data_state": result.get("data_state"),
        "data_message": result.get("data_message"),
        "trading_state": result.get("trading_state"),
        "trading_state_label": result.get("trading_state_label"),
        "as_of": result.get("as_of"),
        "price_through": result.get("price_through"),
        "signal_source": result.get("signal_source"),
        "signal": (
            current.get("label")
            if preliminary
            else transition.get("label") or latest_event.get("label")
        ),
        "side": side or None,
        "event_side": event_side or None,
        "signal_date": signal_date,
        "signal_at": signal_at,
        "execution_date": execution_date,
        "price": current.get("price") if preliminary else transition.get("price") or latest_event.get("price"),
        "entry_price": entry_price,
        "target_sell_price": target_sell_price,
        "target_sell_status": target_sell_status,
        "target_sell_delta": target_sell_delta,
        "return_rate": display_return_rate,
        "display_return_rate": display_return_rate,
        "display_return_kind": display_fields.get("display_return_kind"),
        "display_return_event_date": display_fields.get("display_return_event_date"),
        "display_return_event_side": display_fields.get("display_return_event_side"),
        "status": "preliminary" if preliminary else "confirmed",
        "is_preliminary": preliminary,
        "action": action or None,
        "is_current_holding": bool(current.get("position_open")),
        "signal_origin": signal_origin,
        "reconciliation_id": reconciliation_id,
        "current": current or None,
    }


PENDING_ENTRY_TRADE_FIELDS = (
    "entry_date",
    "entry_price",
    "target_sell_price",
    "target_sell_status",
    "target_sell_delta",
    "partial_exit_date",
    "partial_exit_price",
    "holding_days",
    "unrealized_return",
    "return_basis",
    "stop_reference",
    "locked_profit_reference",
    "partial_exit_reference",
)


def sanitize_pending_entry_signal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove stale trade metrics from a not-yet-executed entry signal.

    The previous execution remains available under ``events``, ``trades`` and
    ``current.lifecycle.latest_transition`` for audit/history views.  Only the
    current pending-entry trade context is cleared.
    """

    result = deepcopy(payload)
    current = result.get("current")
    action = current.get("action") if isinstance(current, dict) else result.get("action")
    position_open = (
        current.get("position_open")
        if isinstance(current, dict)
        else result.get("is_current_holding")
    )
    if (
        action not in {"entry_watch", "entry_pending"}
        or position_open
    ):
        return result

    if isinstance(current, dict):
        for field in PENDING_ENTRY_TRADE_FIELDS:
            current[field] = None
        current["partial_exits"] = []
        current["profit_stage"] = 0
        result["current"] = current
    for field in (
        "entry_price",
        "target_sell_price",
        "target_sell_status",
        "target_sell_delta",
        "return_rate",
    ):
        if field in result:
            result[field] = None
    result.update(quant_signal_display_return_fields(result))
    return result


def sanitize_pending_entry_signal_items(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply the pending-entry contract to active and archived market cards."""

    result = deepcopy(payload)
    for collection_name in ("items", "preliminary_history"):
        collection = result.get(collection_name)
        if not isinstance(collection, list):
            continue
        result[collection_name] = [
            sanitize_pending_entry_signal_payload(item)
            if isinstance(item, dict)
            else item
            for item in collection
        ]
    return result


def load_quant_signal_payload(
    db: Session,
    code: str,
    *,
    live_quote: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
    limit: int = SIGNAL_HISTORY_ROWS,
    include_context: bool = True,
    include_stored_intraday: bool = False,
) -> Optional[dict[str, Any]]:
    stock = db.get(StockMaster, code)
    if not stock or not stock.is_active:
        return None
    rows = list(
        reversed(
            list(
                db.scalars(
                    select(DailyPrice)
                    .where(DailyPrice.code == code)
                    .order_by(DailyPrice.trade_date.desc())
                    .limit(limit)
                )
            )
        )
    )
    current_time = now or datetime.now(KST)
    effective_live_quote = live_quote
    if effective_live_quote is None and include_stored_intraday:
        effective_live_quote = _forming_bar_quote(_normalize_prices(rows), current_time)
    normalized = _normalize_prices(rows)
    confirmed = _confirmed_bars(normalized, current_time)
    evidence_timeline = load_entry_evidence_timeline(db, stock.code)
    latest_confirmed_date = confirmed[-1].trade_date if confirmed else None
    if (
        latest_confirmed_date is not None
        and latest_confirmed_date >= ENTRY_EVIDENCE_EFFECTIVE_DATE
        and latest_confirmed_date not in evidence_timeline
    ):
        snapshot = ensure_entry_evidence_snapshot(
            db,
            stock,
            rows,
            signal_date=latest_confirmed_date,
            now=current_time,
        )
        if snapshot:
            evidence_timeline[latest_confirmed_date] = snapshot
    context = None
    if include_context and (
        latest_confirmed_date is None
        or latest_confirmed_date < ENTRY_EVIDENCE_EFFECTIVE_DATE
    ):
        context = _load_current_context(
            db,
            stock,
            rows,
            live_quote=effective_live_quote,
            now=current_time,
        )
    return build_quant_signal_payload(
        stock,
        rows,
        live_quote=effective_live_quote,
        now=current_time,
        context=context,
        entry_evidence_by_date=evidence_timeline,
    )


MARKET_SIGNAL_PENDING_ACTIONS = {
    "entry_watch",
    "entry_pending",
    "partial_exit_pending",
    "full_exit_pending",
}


def _market_signal_date_value(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def _market_signal_complete_suffix(bars: list[PriceBar]) -> list[PriceBar]:
    last_incomplete_index = max(
        (index for index, bar in enumerate(bars) if not bar.ohlc_complete),
        default=-1,
    )
    return bars[last_incomplete_index + 1 :]


def _market_signal_average_trading_value(
    bars: list[PriceBar],
    *,
    through: date,
    window: int = 20,
) -> Optional[float]:
    through_bars = [bar for bar in bars if bar.trade_date <= through]
    complete = [
        bar
        for bar in _market_signal_complete_suffix(through_bars)
        if bar.trading_value > 0
    ]
    if len(complete) < window:
        return None
    return sum(bar.trading_value for bar in complete[-window:]) / float(window)


def _extended_market_signal_qualification(
    bars: list[PriceBar],
    current: Optional[dict[str, Any]],
    *,
    required_price_date: Optional[date],
) -> dict[str, Any]:
    latest = bars[-1] if bars else None
    complete_price = bool(
        latest
        and required_price_date
        and latest.trade_date == required_price_date
        and latest.ohlc_complete
    )
    average_trading_value = (
        _market_signal_average_trading_value(bars, through=required_price_date)
        if complete_price and required_price_date
        else None
    )
    liquidity_ready = bool(
        average_trading_value is not None
        and average_trading_value >= MARKET_SIGNAL_EXTENDED_MIN_AVERAGE_TRADING_VALUE
    )
    confirmation = (
        current.get("entry_confirmation")
        if isinstance(current, dict) and isinstance(current.get("entry_confirmation"), dict)
        else {}
    )
    evidence_ready = bool(
        isinstance(current, dict)
        and current.get("action") == "entry_pending"
        and confirmation.get("allowed") is True
        and confirmation.get("state") == "approved"
    )
    return {
        "allowed": bool(complete_price and liquidity_ready and evidence_ready),
        "complete_price": complete_price,
        "liquidity_ready": liquidity_ready,
        "evidence_ready": evidence_ready,
        "average_trading_value_20": (
            int(round(average_trading_value))
            if average_trading_value is not None
            else None
        ),
    }


def _extended_market_signal_event_qualification(
    event: dict[str, Any],
    bars: list[PriceBar],
) -> dict[str, Any]:
    signal_date = _market_signal_date_value(event.get("signal_date"))
    bar_by_date = {bar.trade_date: bar for bar in bars}
    signal_bar = bar_by_date.get(signal_date) if signal_date else None
    complete_price = bool(signal_bar and signal_bar.ohlc_complete)
    average_trading_value = (
        _market_signal_average_trading_value(bars, through=signal_date)
        if complete_price and signal_date
        else None
    )
    confirmation = (
        event.get("entry_confirmation")
        if isinstance(event.get("entry_confirmation"), dict)
        else {}
    )
    evidence_ready = bool(
        confirmation.get("allowed") is True
        and confirmation.get("state") == "approved"
    )
    allowed = bool(
        signal_date
        and signal_date >= MARKET_SIGNAL_EXTENDED_EFFECTIVE_DATE
        and complete_price
        and average_trading_value is not None
        and average_trading_value >= MARKET_SIGNAL_EXTENDED_MIN_AVERAGE_TRADING_VALUE
        and evidence_ready
    )
    return {
        "allowed": allowed,
        "complete_price": complete_price,
        "liquidity_ready": bool(
            average_trading_value is not None
            and average_trading_value >= MARKET_SIGNAL_EXTENDED_MIN_AVERAGE_TRADING_VALUE
        ),
        "evidence_ready": evidence_ready,
        "average_trading_value_20": (
            int(round(average_trading_value))
            if average_trading_value is not None
            else None
        ),
    }


def _market_signal_retention_state(
    db: Session,
    *,
    universe_limit: int,
    limit: int,
    recent_days: int,
) -> dict[str, dict[str, Any]]:
    """Return open or pending signal codes from the previous full snapshot."""

    cache_key = market_quant_signal_snapshot_key(universe_limit, limit, recent_days)
    snapshot = db.get(MarketQuantSignalSnapshot, cache_key)
    if snapshot is None:
        return {}
    try:
        payload = json.loads(snapshot.payload)
    except (TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}

    retained: dict[str, dict[str, Any]] = {}
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        current = item.get("current") if isinstance(item.get("current"), dict) else {}
        action = str(current.get("action") or item.get("action") or "")
        is_pending = bool(
            (item.get("is_preliminary") or item.get("status") == "preliminary")
            and action in MARKET_SIGNAL_PENDING_ACTIONS
        )
        is_holding = bool(
            current.get("position_open")
            or item.get("is_current_holding")
            or item.get("holding_context")
        )
        if not code or not (is_pending or is_holding):
            continue
        prior = retained.get(code, {})
        tier = str(item.get("universe_tier") or prior.get("universe_tier") or "core")
        retained[code] = {
            "market_cap_rank": item.get("market_cap_rank") or prior.get("market_cap_rank"),
            "universe_tier": tier if tier in {"core", "extended"} else "core",
            "action": action or prior.get("action"),
            "position_open": bool(is_holding or prior.get("position_open")),
            "average_trading_value_20": (
                item.get("average_trading_value_20")
                or prior.get("average_trading_value_20")
            ),
        }
    return retained


def _market_signal_universe_fields(
    *,
    tier: str,
    is_current_member: bool,
    qualification: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    normalized_tier = "extended" if tier == "extended" else "core"
    qualification = qualification or {}
    return {
        "universe_tier": normalized_tier,
        "universe_tier_label": (
            "확장 유니버스" if normalized_tier == "extended" else "핵심 유니버스"
        ),
        "universe_tracking_state": "current" if is_current_member else "retained",
        "universe_tracking_label": "현재 편입" if is_current_member else "진행 시그널 유지",
        "extended_universe_qualified": bool(
            normalized_tier == "extended" and qualification.get("allowed")
        ),
        "average_trading_value_20": qualification.get("average_trading_value_20"),
    }


def _market_preliminary_signal_item(
    stock: StockMaster,
    market_cap_rank: int,
    payload: dict[str, Any],
    now: datetime,
) -> Optional[dict[str, Any]]:
    payload = sanitize_pending_entry_signal_payload(payload)
    current = payload.get("current")
    if not isinstance(current, dict):
        return None
    action = str(current.get("action") or "")
    if action == "entry_watch":
        side = "buy"
    elif action == "entry_pending":
        side = "buy"
    elif action in {"partial_exit_pending", "full_exit_pending"}:
        side = "sell"
    else:
        return None
    reasons = current.get("reasons") if isinstance(current.get("reasons"), list) else []
    live_observation = bool(current.get("live_observation"))
    signal_date = now.date() if live_observation else payload.get("price_through")
    signal_at = (
        current.get("as_of") or now
        if live_observation
        else _signal_at(signal_date) or current.get("as_of") or now
    )
    item = {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        **investment_sector_fields(stock.sector, stock.industry),
        "market_cap_rank": market_cap_rank,
        "signal": "예비 포착" if action == "entry_watch" else "예비 매수" if side == "buy" else "예비 매도",
        "side": side,
        "event_side": "partial_sell" if action == "partial_exit_pending" else side,
        "signal_date": signal_date,
        "signal_at": signal_at,
        "execution_date": None,
        "price": current.get("price"),
        "entry_price": current.get("entry_price"),
        "target_sell_price": current.get("target_sell_price") or current.get("partial_exit_reference"),
        "target_sell_status": current.get("target_sell_status"),
        "target_sell_delta": current.get("target_sell_delta"),
        "score": current.get("score"),
        "reason": reasons[0] if reasons else None,
        "action": action,
        "status": "preliminary",
        "is_preliminary": True,
        "updated_at": signal_at,
        "current": current,
        "is_current_holding": bool(current.get("position_open")),
    }
    display_return_fields = quant_signal_display_return_fields(payload)
    item["return_rate"] = display_return_fields.get("display_return_rate")
    item.update(display_return_fields)
    return item


def load_market_quant_signal_feed(
    db: Session,
    *,
    universe_limit: int = MARKET_SIGNAL_UNIVERSE_LIMIT,
    limit: int = MARKET_SIGNAL_FEED_LIMIT,
    recent_days: int = MARKET_SIGNAL_RECENT_DAYS,
    now: Optional[datetime] = None,
    live_quotes: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Build recent transitions for stocks that belonged to the market universe.

    The top-N market-cap boundary can change from one session to the next.  If
    only the latest ranking is used, a confirmed transition disappears from the
    home feed as soon as its stock slips just outside that boundary. The core
    universe remains ranks 1-100. Ranks 101-150 are admitted only with a complete
    latest candle, at least 20 billion won of 20-day average trading value, and
    approved independent entry evidence. Once a pending or open signal is
    admitted, the previous snapshot keeps it tracked until execution or cancel.
    """
    current_time = now or datetime.now(KST)
    capped_universe_limit = max(1, min(int(universe_limit), MARKET_SIGNAL_UNIVERSE_LIMIT))
    core_universe_limit = min(
        capped_universe_limit,
        MARKET_SIGNAL_CORE_UNIVERSE_LIMIT,
    )
    capped_limit = max(0, min(int(limit), 1000))
    capped_recent_days = max(1, min(int(recent_days), 90))
    market_cap_date = db.scalar(
        select(func.max(DailyPrice.trade_date)).where(DailyPrice.market_cap.is_not(None))
    )
    required_price_date = (
        current_time.date()
        if current_time.time() >= time(15, 40)
        and is_korea_market_session_date(current_time.date(), current_time)
        else latest_completed_korea_market_session_date(current_time)
    )
    empty = {
        "status": "ready",
        "strategy_version": STRATEGY_VERSION,
        "as_of": current_time,
        "universe_as_of": market_cap_date,
        "universe_count": 0,
        "current_universe_count": 0,
        "core_universe_count": 0,
        "extended_universe_count": 0,
        "extended_qualified_count": 0,
        "retained_signal_count": 0,
        "universe_policy": {
            "core_limit": core_universe_limit,
            "extended_limit": capped_universe_limit,
            "extended_min_average_trading_value": int(
                MARKET_SIGNAL_EXTENDED_MIN_AVERAGE_TRADING_VALUE
            ),
            "extended_effective_date": MARKET_SIGNAL_EXTENDED_EFFECTIVE_DATE,
            "relative_strength_benchmark_limit": MARKET_SIGNAL_CORE_UNIVERSE_LIMIT,
        },
        "recent_days": capped_recent_days,
        "preliminary_count": 0,
        "confirmed_count": 0,
        "items": [],
    }
    if market_cap_date is None:
        return empty

    cutoff = current_time.date() - timedelta(days=capped_recent_days)
    daily_ranked_universe = (
        select(
            DailyPrice.code.label("code"),
            DailyPrice.trade_date.label("trade_date"),
            func.row_number()
            .over(
                partition_by=DailyPrice.trade_date,
                order_by=(DailyPrice.market_cap.desc(), DailyPrice.code),
            )
            .label("market_cap_rank"),
        )
        .join(StockMaster, StockMaster.code == DailyPrice.code)
        .where(
            StockMaster.is_active.is_(True),
            StockMaster.market.in_(("KOSPI", "KOSDAQ")),
            DailyPrice.trade_date >= cutoff,
            DailyPrice.trade_date <= market_cap_date,
            DailyPrice.market_cap.is_not(None),
            DailyPrice.market_cap > 0,
            DailyPrice.close.is_not(None),
        )
        .subquery()
    )
    membership_rows = list(
        db.execute(
            select(
                daily_ranked_universe.c.code,
                daily_ranked_universe.c.trade_date,
                daily_ranked_universe.c.market_cap_rank,
            )
            .where(daily_ranked_universe.c.market_cap_rank <= capped_universe_limit)
            .order_by(
                daily_ranked_universe.c.trade_date.desc(),
                daily_ranked_universe.c.market_cap_rank,
                daily_ranked_universe.c.code,
            )
        )
    )
    retention_state = _market_signal_retention_state(
        db,
        universe_limit=capped_universe_limit,
        limit=capped_limit,
        recent_days=capped_recent_days,
    )
    if not membership_rows and not retention_state:
        return empty

    latest_membership_by_code: dict[str, tuple[date, int]] = {}
    membership_rank_by_code_date: dict[tuple[str, date], int] = {}
    current_universe_codes: set[str] = set()
    for code, membership_date, market_cap_rank in membership_rows:
        normalized_code = str(code)
        normalized_rank = int(market_cap_rank)
        membership_rank_by_code_date[(normalized_code, membership_date)] = normalized_rank
        if normalized_code not in latest_membership_by_code:
            latest_membership_by_code[normalized_code] = (
                membership_date,
                normalized_rank,
            )
        if membership_date == market_cap_date:
            current_universe_codes.add(normalized_code)

    retained_outside_history = set(retention_state) - set(latest_membership_by_code)
    if retained_outside_history:
        retained_current_ranks = {
            str(code): int(market_cap_rank)
            for code, market_cap_rank in db.execute(
                select(
                    daily_ranked_universe.c.code,
                    daily_ranked_universe.c.market_cap_rank,
                ).where(
                    daily_ranked_universe.c.trade_date == market_cap_date,
                    daily_ranked_universe.c.code.in_(tuple(retained_outside_history)),
                )
            )
        }
        for code in retained_outside_history:
            prior_rank = retention_state.get(code, {}).get("market_cap_rank")
            try:
                fallback_rank = int(prior_rank)
            except (TypeError, ValueError):
                fallback_rank = capped_universe_limit + 1
            latest_membership_by_code[code] = (
                market_cap_date,
                retained_current_ranks.get(code, fallback_rank),
            )

    current_rank_by_code = {
        code: latest_membership_by_code[code][1]
        for code in current_universe_codes
    }
    core_history_codes = {
        code
        for (code, _membership_date), membership_rank in membership_rank_by_code_date.items()
        if membership_rank <= core_universe_limit
    }

    stocks_by_code = {
        stock.code: stock
        for stock in db.scalars(
            select(StockMaster).where(
                StockMaster.code.in_(tuple(latest_membership_by_code)),
                StockMaster.is_active.is_(True),
            )
        )
    }
    ordered_codes = sorted(
        stocks_by_code,
        key=lambda code: (
            -latest_membership_by_code[code][0].toordinal(),
            latest_membership_by_code[code][1],
            code,
        ),
    )
    stock_by_code = {code: stocks_by_code[code] for code in ordered_codes}
    rank_by_code = {
        code: latest_membership_by_code[code][1]
        for code in stock_by_code
    }
    ranked_price_ids = (
        select(
            DailyPrice.id.label("price_id"),
            func.row_number()
            .over(
                partition_by=DailyPrice.code,
                order_by=DailyPrice.trade_date.desc(),
            )
            .label("history_rank"),
        )
        .where(
            DailyPrice.code.in_(tuple(stock_by_code)),
            DailyPrice.trade_date <= market_cap_date,
        )
        .subquery()
    )
    price_rows = list(
        db.scalars(
            select(DailyPrice)
            .join(ranked_price_ids, ranked_price_ids.c.price_id == DailyPrice.id)
            .where(ranked_price_ids.c.history_rank <= SIGNAL_HISTORY_ROWS)
            .order_by(DailyPrice.code, DailyPrice.trade_date)
        )
    )
    prices_by_code: dict[str, list[DailyPrice]] = {code: [] for code in stock_by_code}
    for price_row in price_rows:
        prices_by_code.setdefault(price_row.code, []).append(price_row)

    current_quotes = live_quotes or {}
    items: list[dict[str, Any]] = []
    extended_qualified_codes: set[str] = set()
    current_extended_qualified_codes: set[str] = set()
    retained_signal_codes: set[str] = set()
    evidence_snapshots_pending = False
    relative_context_by_date: dict[date, dict[str, Any]] = {}
    for code, stock in stock_by_code.items():
        stock_price_rows = prices_by_code.get(code, [])
        normalized_stock_bars = _normalize_prices(stock_price_rows)
        confirmed_stock_bars = _confirmed_bars(normalized_stock_bars, current_time)
        stored_forming_quote = _forming_bar_quote(normalized_stock_bars, current_time) or {}
        live_quote = current_quotes.get(code) or {}
        forming_quote = {**stored_forming_quote, **live_quote} or None
        evidence_timeline = load_entry_evidence_timeline(db, code)
        latest_confirmed_date = (
            confirmed_stock_bars[-1].trade_date if confirmed_stock_bars else None
        )
        if (
            latest_confirmed_date is not None
            and latest_confirmed_date >= ENTRY_EVIDENCE_EFFECTIVE_DATE
            and latest_confirmed_date not in evidence_timeline
        ):
            relative_context = relative_context_by_date.get(latest_confirmed_date)
            if relative_context is None:
                relative_context = build_relative_strength_context(
                    db,
                    latest_confirmed_date,
                )
                relative_context_by_date[latest_confirmed_date] = relative_context
            snapshot = ensure_entry_evidence_snapshot(
                db,
                stock,
                stock_price_rows,
                signal_date=latest_confirmed_date,
                now=current_time,
                relative_context=relative_context,
                commit_on_persist=False,
                latest_market_date_override=market_cap_date,
            )
            if snapshot:
                evidence_timeline[latest_confirmed_date] = snapshot
                evidence_snapshots_pending = True
        payload = build_quant_signal_payload(
            stock,
            stock_price_rows,
            live_quote=forming_quote,
            now=current_time,
            context=None,
            entry_evidence_by_date=evidence_timeline,
        )
        current = payload.get("current") if isinstance(payload.get("current"), dict) else None
        events = payload.get("events") or []
        previous_tracking = retention_state.get(code, {})
        previous_tier = str(previous_tracking.get("universe_tier") or "core")
        is_current_member = code in current_universe_codes
        current_rank = current_rank_by_code.get(code)
        is_current_core = bool(
            is_current_member
            and current_rank is not None
            and current_rank <= core_universe_limit
        )
        is_current_extended = bool(
            is_current_member
            and current_rank is not None
            and core_universe_limit < current_rank <= capped_universe_limit
        )
        current_extended_qualification = _extended_market_signal_qualification(
            confirmed_stock_bars,
            current,
            required_price_date=required_price_date,
        )
        if is_current_extended and current_extended_qualification["allowed"]:
            extended_qualified_codes.add(code)
            current_extended_qualified_codes.add(code)

        code_has_core_history = code in core_history_codes
        lifecycle_tracked = bool(
            code_has_core_history or previous_tracking.get("position_open")
        )
        lifecycle_tier = "core" if code_has_core_history else previous_tier
        lifecycle_qualification: dict[str, Any] = (
            previous_tracking if lifecycle_tier == "extended" else {}
        )
        eligible_event_contexts: dict[int, tuple[bool, str, dict[str, Any]]] = {}
        for event_index, event in enumerate(events):
            if not isinstance(event, dict):
                eligible_event_contexts[event_index] = (False, lifecycle_tier, {})
                continue
            event_side = str(event.get("side") or "")
            event_signal_date = _market_signal_date_value(event.get("signal_date"))
            event_execution_date = _market_signal_date_value(event.get("execution_date"))
            event_rank = (
                membership_rank_by_code_date.get((code, event_signal_date))
                if event_signal_date
                else None
            ) or (
                membership_rank_by_code_date.get((code, event_execution_date))
                if event_execution_date
                else None
            )
            event_qualification: dict[str, Any] = {}
            if event_side == "buy":
                if code_has_core_history or (
                    event_rank is not None and event_rank <= core_universe_limit
                ):
                    lifecycle_tracked = True
                    lifecycle_tier = "core"
                    lifecycle_qualification = {}
                elif previous_tracking.get("position_open"):
                    lifecycle_tracked = True
                    lifecycle_tier = previous_tier
                    lifecycle_qualification = previous_tracking
                elif (
                    event_rank is not None
                    and core_universe_limit < event_rank <= capped_universe_limit
                ):
                    event_qualification = _extended_market_signal_event_qualification(
                        event,
                        confirmed_stock_bars,
                    )
                    lifecycle_tracked = bool(event_qualification.get("allowed"))
                    lifecycle_tier = "extended"
                    lifecycle_qualification = event_qualification
                    if lifecycle_tracked:
                        extended_qualified_codes.add(code)
                else:
                    lifecycle_tracked = False
            event_is_tracked = lifecycle_tracked
            eligible_event_contexts[event_index] = (
                event_is_tracked,
                lifecycle_tier,
                lifecycle_qualification or event_qualification,
            )
            if event_side == "sell":
                lifecycle_tracked = False

        current_action = str((current or {}).get("action") or "")
        retained_pending_entry = bool(
            previous_tracking
            and previous_tracking.get("action") in {"entry_watch", "entry_pending"}
            and current_action in {"entry_watch", "entry_pending"}
        )
        retained_open_signal = bool(
            previous_tracking.get("position_open")
            and current
            and current.get("position_open")
        )
        current_tier = (
            "core"
            if is_current_core
            else "extended"
            if is_current_extended
            else previous_tier
        )
        preliminary_allowed = bool(
            is_current_core
            or (is_current_extended and current_extended_qualification["allowed"])
            or retained_pending_entry
            or retained_open_signal
            or (
                current
                and current.get("position_open")
                and lifecycle_tracked
                and current_action in {"partial_exit_pending", "full_exit_pending"}
            )
        )
        preliminary_item = (
            _market_preliminary_signal_item(
                stock,
                rank_by_code[code],
                payload,
                current_time,
            )
            if preliminary_allowed
            else None
        )
        if preliminary_item:
            preliminary_qualification = (
                current_extended_qualification
                if current_tier == "extended"
                else previous_tracking
            )
            preliminary_item.update(
                _market_signal_universe_fields(
                    tier=current_tier,
                    is_current_member=is_current_member,
                    qualification=preliminary_qualification,
                )
            )
            items.append(preliminary_item)
            if not is_current_member:
                retained_signal_codes.add(code)
        latest_event = events[-1] if events else None
        display_return_fields = quant_signal_display_return_fields(payload)
        for event_index, event in enumerate(events):
            event_is_tracked, event_tier, event_qualification = eligible_event_contexts.get(
                event_index,
                (False, current_tier, {}),
            )
            execution_date = event.get("execution_date")
            if (
                not event_is_tracked
                or event.get("side") not in {"buy", "partial_sell", "sell"}
                or not execution_date
                or execution_date < cutoff
            ):
                continue
            event_side = str(event.get("side") or "")
            is_buy = event_side == "buy"
            default_signal = (
                "매수"
                if is_buy
                else "수익확정" if event_side == "partial_sell" else "전량 매도"
            )
            item = {
                "code": code,
                "name": stock.name,
                "market": stock.market,
                **investment_sector_fields(stock.sector, stock.industry),
                "market_cap_rank": rank_by_code[code],
                "signal": event.get("label") or default_signal,
                "side": "buy" if is_buy else "sell",
                "event_side": event_side,
                "signal_date": event.get("signal_date"),
                "signal_at": event.get("signal_at") or _signal_at(event.get("signal_date")),
                "execution_date": execution_date,
                "price": event.get("price"),
                "entry_price": event.get("entry_price"),
                "target_sell_price": event.get("target_sell_price"),
                "target_sell_status": event.get("target_sell_status"),
                "target_sell_delta": event.get("target_sell_delta"),
                "score": event.get("score"),
                "reason": event.get("reason"),
                "entry_confirmation": event.get("entry_confirmation"),
                "return_rate": event.get("return_rate"),
                "holding_days": event.get("holding_days"),
                "position_percent": event.get("position_percent"),
                "profit_stage": event.get("profit_stage"),
                "sold_percent": event.get("sold_percent"),
                "state_after": event.get("state_after"),
                "status": "confirmed",
                "is_preliminary": False,
            }
            item.update(
                _market_signal_universe_fields(
                    tier=event_tier,
                    is_current_member=is_current_member,
                    qualification=event_qualification,
                )
            )
            is_current_transition = event is latest_event
            current_position_open = bool(
                is_current_transition
                and current is not None
                and current.get("position_open")
            )
            if current_position_open:
                # A preliminary exit is rendered as its own card, but the
                # confirmed buy/holding card still needs the same live return
                # basis as stock detail. Keep that basis separate so the
                # pending action cannot relabel the confirmed card.
                item["holding_context"] = {
                    key: deepcopy(current.get(key))
                    for key in (
                        "price",
                        "entry_price",
                        "unrealized_return",
                        "return_basis",
                        "model_exposure_percent",
                    )
                }
                item["is_current_holding"] = True
                item.update(display_return_fields)
                if not is_current_member:
                    retained_signal_codes.add(code)
            if is_current_transition and preliminary_item is None and current is not None:
                item["current"] = current
                item["is_current_holding"] = bool(current.get("position_open"))
                item.update(display_return_fields)
            elif not current_position_open and event.get("return_rate") is not None:
                item.update(
                    {
                        "display_return_rate": event.get("return_rate"),
                        "display_return_kind": "closed_trade",
                        "display_return_event_date": event.get("execution_date"),
                        "display_return_event_side": "sell",
                    }
                )
            items.append(item)

    if evidence_snapshots_pending:
        try:
            db.commit()
        except IntegrityError:
            # Another worker may have persisted the same fixed snapshot while
            # this batch was calculating. The feed result remains deterministic.
            db.rollback()

    items.sort(
        key=lambda item: (
            item.get("execution_date") or item.get("signal_date") or date.min,
            int(bool(item.get("is_preliminary"))),
            -(int(item.get("market_cap_rank") or capped_universe_limit + 1)),
        ),
        reverse=True,
    )
    preliminary_count = sum(1 for item in items if item.get("is_preliminary"))
    current_core_count = sum(
        1
        for code in current_universe_codes
        if current_rank_by_code.get(code, capped_universe_limit + 1) <= core_universe_limit
    )
    current_extended_count = max(0, len(current_universe_codes) - current_core_count)
    result = {
        "status": "ready",
        "strategy_version": STRATEGY_VERSION,
        "as_of": current_time,
        "universe_as_of": market_cap_date,
        "universe_count": len(stock_by_code),
        "current_universe_count": len(current_universe_codes),
        "core_universe_count": current_core_count,
        "extended_universe_count": current_extended_count,
        "extended_qualified_count": len(current_extended_qualified_codes),
        "extended_tracked_count": len(extended_qualified_codes),
        "retained_signal_count": len(retained_signal_codes),
        "universe_policy": {
            "core_limit": core_universe_limit,
            "extended_limit": capped_universe_limit,
            "extended_min_average_trading_value": int(
                MARKET_SIGNAL_EXTENDED_MIN_AVERAGE_TRADING_VALUE
            ),
            "extended_effective_date": MARKET_SIGNAL_EXTENDED_EFFECTIVE_DATE,
            "relative_strength_benchmark_limit": MARKET_SIGNAL_CORE_UNIVERSE_LIMIT,
        },
        "recent_days": capped_recent_days,
        "preliminary_count": preliminary_count,
        "confirmed_count": len(items) - preliminary_count,
        "items": items,
    }
    result = apply_market_signal_reconciliations(result, now=current_time) or result
    if capped_limit:
        result["items"] = result["items"][:capped_limit]
    return result


def enrich_quant_signal_payload_sector(
    db: Session,
    payload: dict[str, Any],
    code: Optional[str] = None,
) -> dict[str, Any]:
    """Attach the local source and normalized sector to a stock signal payload."""

    result = deepcopy(payload)
    normalized_code = str(code or result.get("code") or "").strip()
    stock = db.get(StockMaster, normalized_code) if normalized_code else None
    snapshot = db.get(StockCompanySnapshot, normalized_code) if normalized_code else None
    sector = (
        (stock.sector if stock else None)
        or (snapshot.sector if snapshot else None)
        or result.get("sector")
    )
    industry = (
        (stock.industry if stock else None)
        or (snapshot.industry if snapshot else None)
        or result.get("industry")
    )
    result.update(investment_sector_fields(sector, industry))
    return result


def enrich_market_quant_signal_sectors(
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Attach one stable investment-sector group to every market signal item."""

    result = deepcopy(payload)
    items = result.get("items") if isinstance(result.get("items"), list) else []
    codes = {
        str(item.get("code") or "").strip()
        for item in items
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    }
    stocks_by_code = {
        stock.code: stock
        for stock in db.scalars(select(StockMaster).where(StockMaster.code.in_(tuple(codes))))
    } if codes else {}
    snapshots_by_code = {
        snapshot.stock_code: snapshot
        for snapshot in db.scalars(
            select(StockCompanySnapshot).where(StockCompanySnapshot.stock_code.in_(tuple(codes)))
        )
    } if codes else {}
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        stock = stocks_by_code.get(code)
        snapshot = snapshots_by_code.get(code)
        sector = (
            (stock.sector if stock else None)
            or (snapshot.sector if snapshot else None)
            or item.get("sector")
        )
        industry = (
            (stock.industry if stock else None)
            or (snapshot.industry if snapshot else None)
            or item.get("industry")
        )
        item.update(investment_sector_fields(sector, industry))
    return result


def market_quant_signal_snapshot_key(
    universe_limit: int,
    limit: int,
    recent_days: int,
) -> str:
    return f"{MARKET_SIGNAL_SNAPSHOT_VERSION}:{int(universe_limit)}:{int(limit)}:{int(recent_days)}"


def load_external_market_quant_signal_feed(
    source_url: Optional[str],
    *,
    universe_limit: int = MARKET_SIGNAL_UNIVERSE_LIMIT,
    limit: int = MARKET_SIGNAL_FEED_LIMIT,
    recent_days: int = MARKET_SIGNAL_RECENT_DAYS,
    timeout_seconds: int = 12,
    fetcher: Any = requests.get,
) -> Optional[dict[str, Any]]:
    """Load the canonical market signal feed used by another deployment.

    Deployments may keep user/session data in separate databases while sharing
    one market signal history. A failed or incomplete upstream response falls
    back to the deployment's local snapshot.
    """
    normalized = str(source_url or "").strip().rstrip("/")
    if not normalized:
        return None
    endpoint = (
        normalized
        if normalized.endswith("/market/quant-signals")
        else f"{normalized}/market/quant-signals"
    )
    try:
        response = fetcher(
            endpoint,
            params={
                "universe_limit": max(20, min(int(universe_limit), MARKET_SIGNAL_UNIVERSE_LIMIT)),
                "limit": max(0, min(int(limit), 1000)),
                "recent_days": max(1, min(int(recent_days), 90)),
            },
            headers={"Accept": "application/json", "User-Agent": "secret-note-market-signal-sync/1.0"},
            timeout=max(3, min(int(timeout_seconds), 30)),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("status") != "ready":
        return None
    if not isinstance(payload.get("items"), list):
        return None
    result = dict(payload)
    result["signal_source"] = "canonical"
    return result


def _external_signal_base_url(source_url: Optional[str]) -> str:
    normalized = str(source_url or "").strip().rstrip("/")
    market_suffix = "/market/quant-signals"
    if normalized.endswith(market_suffix):
        return normalized[: -len(market_suffix)].rstrip("/")
    return normalized


def load_external_stock_quant_signal_payload(
    source_url: Optional[str],
    code: str,
    *,
    timeout_seconds: int = 12,
    fetcher: Any = requests.get,
) -> Optional[dict[str, Any]]:
    """Load one stock's full strategy state from the canonical signal service."""
    base_url = _external_signal_base_url(source_url)
    normalized_code = str(code or "").strip().upper()
    if not base_url or not normalized_code:
        return None
    try:
        response = fetcher(
            f"{base_url}/stocks/{quote(normalized_code, safe='')}/quant-signals",
            headers={"Accept": "application/json", "User-Agent": "secret-note-stock-signal-sync/1.0"},
            timeout=max(3, min(int(timeout_seconds), 30)),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("code") or "").strip().upper() != normalized_code:
        return None
    if payload.get("data_state") not in {"ready", "insufficient", "incomplete"}:
        return None
    result = dict(payload)
    result.setdefault("entry_score_threshold", _decimal(ENTRY_SCORE))
    result["signal_source"] = "canonical"
    return result


def quant_payload_has_trade_metadata(payload: Optional[dict[str, Any]]) -> bool:
    """Require complete execution and cost-basis fields from an upstream payload."""
    if not isinstance(payload, dict):
        return False
    if payload.get("strategy_version") != STRATEGY_VERSION:
        return False
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    if events:
        return all(
            isinstance(event, dict)
            and "signal_at" in event
            and "entry_price" in event
            and "target_sell_price" in event
            for event in events
        )
    current = payload.get("current")
    return current is None or (
        isinstance(current, dict)
        and "entry_price" in current
        and "target_sell_price" in current
    )


def market_payload_has_trade_metadata(payload: Optional[dict[str, Any]]) -> bool:
    """Return whether an upstream market feed includes the trade display fields."""
    if not isinstance(payload, dict):
        return False
    if payload.get("strategy_version") != STRATEGY_VERSION:
        return False
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items:
        return True
    return all(
        isinstance(item, dict)
        and "signal_at" in item
        and "entry_price" in item
        and "target_sell_price" in item
        and (item.get("side") != "sell" or "return_rate" in item)
        for item in items
    )


def load_reference_quant_signal_payload(
    db: Session,
    code: str,
    *,
    source_url: Optional[str] = None,
    source_timeout_seconds: int = 12,
    live_quote: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
    limit: int = SIGNAL_HISTORY_ROWS,
    include_context: bool = True,
    include_stored_intraday: bool = False,
) -> Optional[dict[str, Any]]:
    """Use the configured canonical service first, with local calculation as fallback."""
    external = load_external_stock_quant_signal_payload(
        source_url,
        code,
        timeout_seconds=source_timeout_seconds,
    )
    if external is not None and quant_payload_has_trade_metadata(external):
        synchronized = synchronize_quant_payload_live_quote(external, live_quote, now=now)
        return apply_stock_signal_reconciliations(synchronized, now=now)
    local = load_quant_signal_payload(
        db,
        code,
        live_quote=live_quote,
        now=now,
        limit=limit,
        include_context=include_context,
        include_stored_intraday=include_stored_intraday,
    )
    if local is None:
        return None
    result = dict(local)
    result["signal_source"] = "local"
    return apply_stock_signal_reconciliations(result, now=now)


def synchronize_quant_payload_live_quote(
    payload: dict[str, Any],
    live_quote: Optional[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Reprice an upstream open position with this deployment's latest quote.

    A canonical signal service remains authoritative for the lifecycle and
    execution history.  Its last HTTP response can still be older than the
    quote stream, so only the mark-to-market fields are rebased here.
    """
    result = sanitize_pending_entry_signal_payload(payload)
    current = result.get("current")
    current_time = now or datetime.now(KST)
    live_price = _safe_number((live_quote or {}).get("price"))
    price_through = _live_quote_trade_date({"trade_date": result.get("price_through")})
    guard_bar = (
        PriceBar(
            trade_date=price_through,
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1.0,
            trading_value=1.0,
        )
        if price_through is not None
        else None
    )
    live_quote_is_safe = bool(
        guard_bar
        and _live_quote_is_active_krx_observation(
            [guard_bar],
            live_quote,
            current_time,
        )
    )
    if (
        not isinstance(current, dict)
        or not current.get("position_open")
        or live_price is None
        or not live_quote_is_safe
    ):
        result.update(quant_signal_display_return_fields(result))
        return result

    basis = current.get("return_basis") if isinstance(current.get("return_basis"), dict) else {}
    try:
        basis_price = float(basis.get("price"))
        basis_return = float(basis.get("return_rate"))
        rate_per_price = float(basis.get("return_rate_per_price"))
    except (TypeError, ValueError):
        basis_price = basis_return = rate_per_price = float("nan")

    if all(isfinite(value) for value in (basis_price, basis_return, rate_per_price)) and basis_price > 0:
        live_return = basis_return + ((live_price - basis_price) * rate_per_price)
    else:
        # Compatibility path for an older canonical deployment.  Preserve its
        # cost-adjusted return and move it only by the live price delta.
        try:
            base_price = float(current.get("price"))
            base_return = float(current.get("unrealized_return"))
            entry_price = float(current.get("entry_price"))
            exposure = float(current.get("model_exposure_percent") or 100.0) / 100.0
        except (TypeError, ValueError):
            base_price = base_return = entry_price = float("nan")
            exposure = 1.0
        if (
            all(isfinite(value) for value in (base_price, base_return, entry_price, exposure))
            and base_price > 0
            and entry_price > 0
        ):
            live_return = base_return + ((live_price - base_price) / entry_price * exposure * 100.0)
        else:
            live_return = None

    current["price"] = _price(live_price)
    current["as_of"] = current_time
    if live_return is not None:
        current["unrealized_return"] = _decimal(live_return)
    result["current"] = current
    result["as_of"] = current_time
    result.update(quant_signal_display_return_fields(result))
    return result


MARKET_PRELIMINARY_HISTORY_FIELDS = (
    "code",
    "name",
    "market",
    "sector",
    "industry",
    "investment_sector",
    "investment_sector_label",
    "market_cap_rank",
    "universe_tier",
    "universe_tier_label",
    "universe_tracking_state",
    "universe_tracking_label",
    "extended_universe_qualified",
    "average_trading_value_20",
    "side",
    "signal",
    "signal_date",
    "signal_at",
    "price",
    "score",
    "reason",
    "action",
)


def _market_signal_date_token(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(KST)
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    candidate = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return ""


def merge_market_preliminary_history(
    payload: dict[str, Any],
    previous_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Keep every preliminary signal seen today and mark its current state."""

    result = deepcopy(payload)
    event_date = _market_signal_date_token(result.get("as_of"))
    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    history_sources = []
    if isinstance(previous_payload, dict):
        history_sources.extend(previous_payload.get("preliminary_history") or [])
    history_sources.extend(result.get("preliminary_history") or [])
    for item in history_sources:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        side = str(item.get("side") or "").strip().lower()
        signal_date = _market_signal_date_token(item.get("signal_date"))
        if not code or side not in {"buy", "sell"} or not signal_date:
            continue
        if event_date and signal_date != event_date:
            continue
        records[(code, side, signal_date)] = deepcopy(item)

    active_keys: set[tuple[str, str, str]] = set()
    for item in result.get("items") or []:
        if not isinstance(item, dict):
            continue
        preliminary = bool(item.get("is_preliminary")) or item.get("status") == "preliminary"
        if not preliminary:
            continue
        code = str(item.get("code") or "").strip()
        side = str(item.get("side") or "").strip().lower()
        signal_date = _market_signal_date_token(item.get("signal_date"))
        if not event_date:
            event_date = signal_date
        if (
            not code
            or side not in {"buy", "sell"}
            or not signal_date
            or (event_date and signal_date != event_date)
        ):
            continue
        key = (code, side, signal_date)
        active_keys.add(key)
        previous = records.get(key, {})
        observed_at = (
            item.get("updated_at")
            or item.get("signal_at")
            or result.get("as_of")
            or signal_date
        )
        merged = deepcopy(previous)
        for field in MARKET_PRELIMINARY_HISTORY_FIELDS:
            value = item.get(field)
            if value is not None and value != "":
                merged[field] = value
        merged.update(
            {
                "code": code,
                "side": side,
                "signal_date": signal_date,
                "first_seen_at": previous.get("first_seen_at") or observed_at,
                "last_seen_at": observed_at,
                "active": True,
            }
        )
        records[key] = merged

    for key, item in records.items():
        item["active"] = key in active_keys
    result["preliminary_history"] = sorted(
        records.values(),
        key=lambda item: str(item.get("first_seen_at") or item.get("signal_at") or ""),
        reverse=True,
    )
    return result


def load_market_quant_signal_snapshot(
    db: Session,
    *,
    universe_limit: int = MARKET_SIGNAL_UNIVERSE_LIMIT,
    limit: int = MARKET_SIGNAL_FEED_LIMIT,
    recent_days: int = MARKET_SIGNAL_RECENT_DAYS,
) -> Optional[dict[str, Any]]:
    cache_key = market_quant_signal_snapshot_key(universe_limit, limit, recent_days)
    snapshot = db.get(MarketQuantSignalSnapshot, cache_key)
    if snapshot is None:
        return None
    try:
        payload = json.loads(snapshot.payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if not market_payload_has_trade_metadata(payload):
        return None
    if payload.get("strategy_version") != STRATEGY_VERSION:
        return None
    payload["status"] = "ready"
    generated_at = snapshot.generated_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    payload["snapshot_generated_at"] = generated_at.isoformat()
    return payload


def save_market_quant_signal_snapshot(
    db: Session,
    payload: dict[str, Any],
    *,
    universe_limit: int = MARKET_SIGNAL_UNIVERSE_LIMIT,
    limit: int = MARKET_SIGNAL_FEED_LIMIT,
    recent_days: int = MARKET_SIGNAL_RECENT_DAYS,
    generated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    cache_key = market_quant_signal_snapshot_key(universe_limit, limit, recent_days)
    stored_at = (generated_at or datetime.utcnow()).replace(tzinfo=None)
    snapshot = db.get(MarketQuantSignalSnapshot, cache_key)
    previous_payload = None
    if snapshot is not None:
        try:
            decoded = json.loads(snapshot.payload)
            previous_payload = decoded if isinstance(decoded, dict) else None
        except (TypeError, ValueError):
            previous_payload = None
    stored_payload = merge_market_preliminary_history(payload, previous_payload)
    serialized = json.dumps(
        stored_payload,
        ensure_ascii=False,
        default=lambda value: value.isoformat() if isinstance(value, (date, datetime)) else str(value),
    )
    if snapshot is None:
        snapshot = MarketQuantSignalSnapshot(
            cache_key=cache_key,
            payload=serialized,
            generated_at=stored_at,
        )
        db.add(snapshot)
    else:
        snapshot.payload = serialized
        snapshot.generated_at = stored_at
    db.commit()
    result = dict(stored_payload)
    result["status"] = "ready"
    result["snapshot_generated_at"] = stored_at.replace(tzinfo=timezone.utc).isoformat()
    return result
