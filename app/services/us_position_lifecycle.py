from __future__ import annotations

"""US market adapter for the position-lifecycle v1 release candidate.

RC1 is deliberately shadow/preliminary-only.  It scans a point-in-time US
top-100 universe with the common technical/chase/re-entry primitives, while
US-specific market-regime, relative-strength, and dollar-volume evidence must
all be fresh before a row can become ``entry_pending``.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import logging
from typing import Any, Callable, Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.services.position_lifecycle_core import (
    ChasePolicy,
    EntryPolicy,
    LifecycleBar,
    ReentryPolicy,
    calculate_indicators,
    chase_entry_veto_reason,
    entry_decision,
    entry_quality_allowed,
    fresh_reentry_trigger,
)
from app.services.public_signal import (
    PUBLIC_SIGNAL_REASON_KEYS,
    US_DOLLAR_VOLUME_NOTICE,
    build_public_signal_reasons,
)
from app.services.us_sector_classification import (
    US_SECTOR_ETF_CLASSIFICATION_VERSION,
    US_SECTOR_ETFS,
    sector_etf_for_cik,
)
from app.services.us_market_calendar import US_SIGNAL_PUBLICATION_GRACE
from app.services.us_signal_universe import (
    US_SIGNAL_UNIVERSE_LIMIT,
    US_SIGNAL_UNIVERSE_VERSION,
    _decode_valid_snapshot as _decode_valid_universe_snapshot,
    _snapshot_payload_is_valid as _universe_snapshot_payload_is_valid,
    build_us_signal_universe,
)


logger = logging.getLogger(__name__)


US_STRATEGY_VERSION = "position-lifecycle-us-v2-rc1"
US_BASELINE_STRATEGY_VERSION = "us-momentum-watch-v1"
# The US feed remains a model-only product: no broker order is ever sent.  The
# v2 candidate does, however, replay a completed-session lifecycle so the UI
# can distinguish a close-time candidate from a next-session model entry.
US_ROLLOUT_MODE = "model_replay"
US_LIFECYCLE_REPLAY_VERSION = "us-next-open-model-replay-v1"
US_STATEFUL_LIFECYCLE_REPLAY_ENABLED = True
US_REENTRY_RUNTIME_ENABLED = True
US_BASELINE_ENTRY_SCORE = Decimal("60")
US_BASELINE_VALUE_SCORE = Decimal("45")
US_BASELINE_LIQUIDITY_SCORE = Decimal("60")
US_BASELINE_SENTIMENT_SCORE = Decimal("50")
US_MIN_HISTORY_ROWS = 125
US_ENTRY_WATCH_SCORE = 56.0
US_RELATIVE_STRENGTH_FLOOR = -0.02
US_MIN_STOCK_PARTICIPATION = 0.90
US_MIN_SECTOR_PARTICIPATION = 0.85
US_MAX_ENTRY_GAP_ATR = 1.5
US_MAX_ENTRY_GAP_PERCENT = 0.05
US_LIFECYCLE_INITIAL_STOP_ATR = 2.0
US_LIFECYCLE_MAX_STOP_PERCENT = 0.05
US_LIFECYCLE_MIN_HOLDING_BARS = 2
US_LIFECYCLE_TREND_EXIT_CONFIRMATIONS = 2

US_ENTRY_POLICY = EntryPolicy(
    entry_score=65.0,
    early_entry_score=67.0,
    max_entry_atr_percent=0.055,
    max_entry_extension_atr=2.5,
    min_average_trading_value=50_000_000.0,
    min_momentum5=0.005,
    min_volume_ratio=0.90,
)
US_CHASE_POLICY = ChasePolicy(
    effective_date=None,
    max_extension_atr=1.5,
    max_extension_percent=0.07,
    momentum5_max=0.10,
    momentum_lookback_bars=3,
)
US_REENTRY_POLICY = ReentryPolicy(
    event_effective_date=None,
    legacy_cooldown_bars=0,
    retest_lookback_bars=3,
    retest_ema20_buffer=0.02,
)


@dataclass(frozen=True)
class USLifecycleBar:
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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _complete_ohlc(row: Any) -> bool:
    try:
        open_price = float(row.open)
        high = float(row.high)
        low = float(row.low)
        close = float(row.close)
    except (TypeError, ValueError):
        return False
    return bool(
        min(open_price, high, low, close) > 0
        and high >= max(open_price, close)
        and low <= min(open_price, close)
    )


def us_price_bars(
    rows: list[Any],
    *,
    now: Optional[datetime] = None,
    market_session: Optional[str] = None,
) -> list[USLifecycleBar]:
    """Normalize adjusted Yahoo rows and exclude a forming regular-session bar."""

    from app.services.us_market import NEW_YORK_TZ
    from app.services.us_market_calendar import us_signal_session_state

    current = now or datetime.now(timezone.utc)
    session = market_session or str(us_signal_session_state(current)["session"])
    local_date = current.astimezone(NEW_YORK_TZ).date()
    bars: list[USLifecycleBar] = []
    for row in sorted(rows, key=lambda item: item.trade_date):
        if (
            row.trade_date.weekday() >= 5
            or getattr(row, "adjusted_ohlc_complete", None) is False
            or not _complete_ohlc(row)
        ):
            continue
        if row.trade_date == local_date and session == "regular":
            continue
        volume = max(0.0, float(row.volume or 0))
        close = float(row.close)
        trading_value = max(0.0, float(row.trading_value or (close * volume)))
        bars.append(
            USLifecycleBar(
                trade_date=row.trade_date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=close,
                volume=volume,
                trading_value=trading_value,
            )
        )
    return bars


def _average(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _dollar_volume_evidence(bars: list[USLifecycleBar]) -> dict[str, Optional[float]]:
    if len(bars) < 25:
        return {"participation_ratio": None, "accumulation_pressure": None}
    recent = [bar.trading_value for bar in bars[-5:]]
    baseline = [bar.trading_value for bar in bars[-25:-5]]
    recent_average = _average(recent)
    baseline_average = _average(baseline)
    participation = (
        recent_average / baseline_average
        if recent_average is not None and baseline_average not in (None, 0.0)
        else None
    )
    signed = 0.0
    absolute = 0.0
    previous_close: Optional[float] = None
    for bar in bars[-20:]:
        if previous_close is not None:
            direction = 1.0 if bar.close > previous_close else -1.0 if bar.close < previous_close else 0.0
            signed += direction * bar.trading_value
            absolute += bar.trading_value
        previous_close = bar.close
    pressure = signed / absolute if absolute > 0 else None
    return {
        "participation_ratio": participation,
        "accumulation_pressure": pressure,
    }


def evaluate_us_momentum_watch_baseline(
    stock_bars: list[USLifecycleBar],
    legacy_inputs: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Reproduce the legacy US momentum-watch decision on its quote inputs.

    The retired feed used Yahoo's 50/200-day-average change percentages, current
    quote change, trailing P/E and price/book. The point-in-time universe keeps
    those exact fields from its validation quote so the shadow comparison does
    not silently substitute trailing close returns or a fixed valuation score.
    """

    if not stock_bars:
        return {
            "data_state": "insufficient",
            "action": "no_signal",
            "score": None,
        }
    inputs = legacy_inputs or {}

    def value(key: str) -> Optional[Decimal]:
        raw = inputs.get(key)
        if raw is None:
            return None
        try:
            parsed = Decimal(str(raw))
        except Exception:
            return None
        return parsed if parsed.is_finite() else None

    one_day_return = value("legacy_regular_market_change_percent") or Decimal("0")
    one_month_return = (
        value("legacy_fifty_day_average_change_percent") or Decimal("0")
    ) * Decimal("100")
    one_month_return = one_month_return.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    three_month_return = (
        value("legacy_two_hundred_day_average_change_percent") or Decimal("0")
    ) * Decimal("100")
    three_month_return = three_month_return.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    price_momentum_score = max(
        Decimal("0"),
        min(
            Decimal("100"),
            Decimal("50")
            + one_month_return * Decimal("1.2")
            + three_month_return * Decimal("0.35")
            + one_day_return * Decimal("0.25"),
        ),
    )
    per = value("legacy_trailing_pe")
    pbr = value("legacy_price_to_book")
    value_score = (
        max(
            Decimal("0"),
            Decimal("100") - min(Decimal("80"), per + pbr * Decimal("4")),
        )
        if per is not None and pbr is not None
        else US_BASELINE_VALUE_SCORE
    )
    liquidity_score = (
        US_BASELINE_LIQUIDITY_SCORE
        if (value("legacy_regular_market_volume") or Decimal("0")) > 0
        else Decimal("45")
    )
    score = (
        price_momentum_score * Decimal("0.65")
        + value_score * Decimal("0.15")
        + liquidity_score * Decimal("0.12")
        + US_BASELINE_SENTIMENT_SCORE * Decimal("0.08")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    action = "entry_pending" if score >= US_BASELINE_ENTRY_SCORE else "entry_watch"
    return {
        "data_state": "ready",
        "action": action,
        "score": score,
        "price_momentum_score": price_momentum_score.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        "value_score": value_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "one_day_return": one_day_return,
        "one_month_return": one_month_return,
        "three_month_return": three_month_return,
    }


def _sector_etf(item: dict[str, Any]) -> str:
    # Display-sector strings are not GICS-equivalent and can map payment,
    # networking, staples, and industrial issuers to the wrong ETF. Only the
    # reviewed, versioned SEC-CIK taxonomy is signal-bearing.
    return sector_etf_for_cik(item.get("cik"))


def _market_regime(
    spy_indicators: list[dict[str, float]],
    spy_bars: list[USLifecycleBar],
    qqq_indicators: list[dict[str, float]],
    qqq_bars: list[USLifecycleBar],
) -> dict[str, Any]:
    if not spy_indicators or not qqq_indicators or not spy_bars or not qqq_bars:
        return {"state": "unavailable", "score": None, "supportive": False}
    conditions: list[bool] = []
    for bars, indicators in ((spy_bars, spy_indicators), (qqq_bars, qqq_indicators)):
        bar = bars[-1]
        indicator = indicators[-1]
        conditions.extend(
            [
                bar.close > indicator["ema20"],
                indicator["ema20"] > indicator["ema60"],
                indicator["momentum20"] > -0.02,
            ]
        )
    score = 100.0 * sum(conditions) / len(conditions)
    state = "risk_on" if score >= 66.0 else "neutral" if score >= 50.0 else "risk_off"
    return {"state": state, "score": score, "supportive": state != "risk_off"}


def _aligned_recent_sessions(
    *series: list[USLifecycleBar],
    window: int = US_MIN_HISTORY_ROWS,
) -> bool:
    """Require the exact consecutive XNYS vector across every signal input."""

    if not series or any(len(bars) < window for bars in series):
        return False
    date_vectors = [tuple(bar.trade_date for bar in bars[-window:]) for bars in series]
    reference = date_vectors[0]
    try:
        from app.services.us_market_calendar import recent_us_market_session_dates

        official = recent_us_market_session_dates(reference[-1], window)
    except Exception:
        return False
    return bool(
        len(set(reference)) == window
        and reference == official
        and all(dates == reference for dates in date_vectors[1:])
    )


def _aligned_short_history_sessions(
    stock_bars: list[USLifecycleBar],
    spy_bars: list[USLifecycleBar],
    qqq_bars: list[USLifecycleBar],
    sector_bars: list[USLifecycleBar],
    *,
    universe_date: date,
) -> bool:
    """Accept a complete short listing history while keeping it signal-ineligible.

    A newly listed Top-100 member can legitimately have fewer than 125 sessions.
    Its entire available vector must still be an exact suffix of XNYS, SPY, QQQ
    and its reviewed sector ETF.  This distinguishes a continuous short history
    from a provider gap; the member remains ``no_signal`` until 125 rows accrue.
    """

    available = len(stock_bars)
    references = (spy_bars, qqq_bars, sector_bars)
    if (
        available < 1
        or available >= US_MIN_HISTORY_ROWS
        or any(len(bars) < US_MIN_HISTORY_ROWS for bars in references)
        or stock_bars[-1].trade_date != universe_date
        or any(bars[-1].trade_date != universe_date for bars in references)
    ):
        return False
    stock_dates = tuple(bar.trade_date for bar in stock_bars)
    try:
        from app.services.us_market_calendar import recent_us_market_session_dates

        official = recent_us_market_session_dates(universe_date, available)
    except Exception:
        return False
    return bool(
        len(set(stock_dates)) == available
        and stock_dates == official
        and all(
            tuple(bar.trade_date for bar in reference[-available:]) == official
            for reference in references
        )
    )


def evaluate_us_entry_candidate(
    stock_bars: list[USLifecycleBar],
    spy_bars: list[USLifecycleBar],
    qqq_bars: list[USLifecycleBar],
    sector_bars: list[USLifecycleBar],
    *,
    new_entries_allowed: bool = True,
) -> dict[str, Any]:
    """Return the deterministic latest-close US entry state and evidence."""

    if min(len(stock_bars), len(spy_bars), len(qqq_bars), len(sector_bars)) < US_MIN_HISTORY_ROWS:
        return {
            "data_state": "insufficient",
            "action": "no_signal",
            "score": None,
            "entry_setup": None,
            "chase_veto": None,
            "next_confirmation": "수정 일봉과 시장·섹터 근거가 125거래일 이상 쌓여야 합니다.",
        }
    stock_indicators = calculate_indicators(stock_bars)
    spy_indicators = calculate_indicators(spy_bars)
    qqq_indicators = calculate_indicators(qqq_bars)
    sector_indicators = calculate_indicators(sector_bars)
    latest = stock_indicators[-1]
    spy_latest = spy_indicators[-1]
    sector_latest = sector_indicators[-1]
    stock_flow = _dollar_volume_evidence(stock_bars)
    sector_flow = _dollar_volume_evidence(sector_bars)
    regime = _market_regime(spy_indicators, spy_bars, qqq_indicators, qqq_bars)
    relative_strength20 = latest["momentum20"] - spy_latest["momentum20"]
    stock_sector_relative20 = latest["momentum20"] - sector_latest["momentum20"]
    sector_market_relative20 = sector_latest["momentum20"] - spy_latest["momentum20"]
    relative_score = _clamp(50.0 + relative_strength20 * 500.0, 0.0, 100.0)
    participation = stock_flow["participation_ratio"]
    pressure = stock_flow["accumulation_pressure"]
    sector_participation = sector_flow["participation_ratio"]
    flow_score = _clamp(
        50.0
        + ((participation or 1.0) - 1.0) * 40.0
        + (pressure or 0.0) * 20.0
        + ((sector_participation or 1.0) - 1.0) * 20.0,
        0.0,
        100.0,
    )
    regime_score = float(regime.get("score") or 0.0)
    composite_score = _clamp(
        latest["score"] * 0.68
        + regime_score * 0.10
        + relative_score * 0.12
        + flow_score * 0.10,
        0.0,
        100.0,
    )
    one_day_return = (
        (stock_bars[-1].close / stock_bars[-2].close) - 1.0
        if len(stock_bars) >= 2 and stock_bars[-2].close
        else 0.0
    )
    three_month_return = (
        (stock_bars[-1].close / stock_bars[-64].close) - 1.0
        if len(stock_bars) >= 64 and stock_bars[-64].close
        else None
    )
    enriched = {**latest, "score": composite_score}
    recent = [dict(item) for item in stock_indicators[-US_CHASE_POLICY.momentum_lookback_bars :]]
    recent[-1] = enriched
    technical_decision = entry_decision(
        stock_bars[-1],
        enriched,
        recent,
        entry_policy=US_ENTRY_POLICY,
        chase_policy=US_CHASE_POLICY,
    )
    aligned = _aligned_recent_sessions(
        stock_bars,
        spy_bars,
        qqq_bars,
        sector_bars,
    )
    market_relative_supportive = (
        relative_strength20 >= US_RELATIVE_STRENGTH_FLOOR
    )
    sector_relative_supportive = stock_sector_relative20 >= -0.03
    relative_supportive = market_relative_supportive and sector_relative_supportive
    stock_flow_supportive = bool(
        participation is not None
        and participation >= US_MIN_STOCK_PARTICIPATION
        and (pressure is None or pressure >= -0.15)
    )
    sector_supportive = bool(
        sector_participation is not None
        and sector_participation >= US_MIN_SECTOR_PARTICIPATION
        and sector_market_relative20 >= -0.03
    )
    evidence_available = bool(
        aligned
        and regime.get("state") != "unavailable"
        and participation is not None
        and sector_participation is not None
    )
    evidence_allowed = bool(
        evidence_available
        and regime["supportive"]
        and relative_supportive
        and (stock_flow_supportive or sector_supportive)
    )
    allowed = bool(
        new_entries_allowed
        and technical_decision["allowed"]
        and evidence_allowed
    )
    chase_veto = technical_decision.get("veto_reason")
    quality_allowed = entry_quality_allowed(stock_bars[-1], enriched, US_ENTRY_POLICY)
    near_ready = bool(
        not chase_veto
        and quality_allowed
        and composite_score >= US_ENTRY_WATCH_SCORE
        and stock_bars[-1].close >= enriched["ema20"] * 0.99
        and enriched.get("momentum20", 0.0) > -0.05
    )
    action = "entry_pending" if allowed else "entry_watch" if near_ready else "no_signal"
    if not new_entries_allowed:
        next_confirmation = "완료 세션의 시총 상위 100 스냅샷이 새로 확정돼야 합니다."
    elif chase_veto:
        next_confirmation = "과열 이격 또는 최근 급등이 해소된 뒤 다시 확인합니다."
    elif not evidence_available:
        next_confirmation = "같은 미국 정규장 기준의 시장·섹터·거래대금 근거가 필요합니다."
    elif not regime["supportive"]:
        next_confirmation = "SPY·QQQ 시장 국면이 위험회피에서 벗어나야 합니다."
    elif not relative_supportive:
        next_confirmation = "SPY와 섹터 ETF 대비 20일 상대강도가 회복돼야 합니다."
    elif not (stock_flow_supportive or sector_supportive):
        next_confirmation = "종목 또는 섹터 ETF의 달러 거래대금 참여도가 회복돼야 합니다."
    elif not technical_decision["entry_setup"]:
        next_confirmation = "종가 추세·모멘텀·거래량 조건을 더 확인합니다."
    else:
        next_confirmation = "다음 미국 정규장 종가에서 조건 지속 여부를 확인합니다."

    return {
        "data_state": "ready",
        "action": action,
        "score": composite_score,
        "entry_setup": technical_decision.get("entry_setup"),
        "chase_veto": chase_veto,
        "price": stock_bars[-1].close,
        "signal_date": stock_bars[-1].trade_date,
        "change_rate": one_day_return * 100.0,
        "one_month_return": latest["momentum20"] * 100.0,
        "three_month_return": (
            three_month_return * 100.0 if three_month_return is not None else None
        ),
        "trading_value": stock_bars[-1].trading_value,
        "trading_value_change": (
            (participation - 1.0) * 100.0 if participation is not None else None
        ),
        "next_confirmation": next_confirmation,
        "technical": enriched,
        "confirmation": {
            "quality_state": "ready" if evidence_available else "unavailable",
            "allowed": evidence_allowed,
            "market_regime": regime,
            "relative_strength_20d": relative_strength20,
            "stock_sector_relative_strength_20d": stock_sector_relative20,
            "sector_market_relative_strength_20d": sector_market_relative20,
            "market_relative_supportive": market_relative_supportive,
            "sector_relative_supportive": sector_relative_supportive,
            "stock_dollar_volume_participation": participation,
            "stock_accumulation_pressure": pressure,
            "sector_dollar_volume_participation": sector_participation,
            "supportive_count": sum(
                (regime["supportive"], relative_supportive, stock_flow_supportive, sector_supportive)
            ),
            "available_count": 4 if evidence_available else 0,
            "source": "Yahoo adjusted OHLC + USD dollar-volume proxy + SPY/QQQ + versioned SEC-CIK sector ETF proxy",
            "proxy_notice": "섹터 ETF는 검토된 SEC CIK 분류를 버전 고정한 프록시이며, 거래대금은 투자자 순매수나 ETF 순유입이 아닙니다.",
        },
    }


def us_reentry_allowed(
    bars: list[LifecycleBar],
    indicators: list[dict[str, float]],
    index: int,
    last_exit_index: Optional[int],
) -> bool:
    if last_exit_index is None:
        return True
    return fresh_reentry_trigger(
        bars,
        indicators,
        index,
        last_exit_index,
        US_REENTRY_POLICY,
    )


def us_entry_execution_allowed(execution_price: float, signal_price: float, atr: float) -> bool:
    execution_value = Decimal(str(execution_price))
    signal_value = Decimal(str(signal_price))
    atr_value = Decimal(str(atr))
    if min(execution_value, signal_value, atr_value) <= 0:
        return False
    percent_limit = signal_value * Decimal(str(US_MAX_ENTRY_GAP_PERCENT))
    volatility_limit = atr_value * Decimal(str(US_MAX_ENTRY_GAP_ATR))
    allowed_gap = min(percent_limit, volatility_limit)
    return abs(execution_value - signal_value) <= allowed_gap


def _us_model_initial_stop(entry_price: float, atr: float) -> float:
    """Return the persisted model-risk floor for a next-open US entry.

    The replay intentionally uses only completed daily OHLC.  It is not a
    broker stop order and must never be described as one in the public API.
    """

    entry = max(0.0, float(entry_price))
    bounded_atr_risk = min(
        entry * US_LIFECYCLE_MAX_STOP_PERCENT,
        max(entry * 0.01, max(0.0, float(atr)) * US_LIFECYCLE_INITIAL_STOP_ATR),
    )
    return max(0.0, entry - bounded_atr_risk)


def _us_model_exit_reason(
    position: dict[str, Any],
    bar: USLifecycleBar,
    indicator: dict[str, float],
    *,
    allow_trend_exit: bool,
) -> Optional[str]:
    """Return a close-confirmed model exit reason, never an intraday order.

    A protective floor exits at the following regular-session open.  A softer
    trend exit needs two completed closes below the 20-day average, avoiding a
    one-day reaction to noise while still keeping the replay deterministic.
    """

    if float(bar.close) <= float(position["stop_reference"]):
        return "위험선 하회"
    if not allow_trend_exit:
        position["trend_exit_confirmations"] = 0
        return None
    below_trend = bool(
        float(bar.close) < float(indicator.get("ema20") or 0.0)
        and float(indicator.get("momentum5") or 0.0) < 0.0
    )
    position["trend_exit_confirmations"] = (
        int(position.get("trend_exit_confirmations") or 0) + 1
        if below_trend
        else 0
    )
    if (
        int(position["trend_exit_confirmations"])
        >= US_LIFECYCLE_TREND_EXIT_CONFIRMATIONS
    ):
        return "20일 가격 흐름 약화 확인"
    return None


def _us_model_lifecycle_label(action: str) -> str:
    return {
        "entry_watch": "예비 포착",
        "entry_pending": "예비 매수",
        "entered": "전략 매수 확정",
        "holding": "전략 보유",
        "full_exit_pending": "전략 매도 대기",
        "exited": "전략 매도 확정",
        "no_signal": "관망",
    }.get(action, "관망")


def replay_us_position_lifecycle(
    stock_bars: list[USLifecycleBar],
    spy_bars: list[USLifecycleBar],
    qqq_bars: list[USLifecycleBar],
    sector_bars: list[USLifecycleBar],
    *,
    latest_decision: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Replay US model entries on the next completed session open.

    A candidate is created at a completed close.  It becomes a *model*
    confirmed entry only when the following completed session's opening price
    is inside the stored gap envelope.  This provides a deterministic,
    inspectable lifecycle without claiming an actual user order or holding.
    """

    series = (stock_bars, spy_bars, qqq_bars, sector_bars)
    if min(len(rows) for rows in series) < US_MIN_HISTORY_ROWS:
        return {
            "complete": False,
            "action": "no_signal",
            "events": [],
            "position": None,
            "last_exit": None,
        }
    if not _aligned_recent_sessions(*series):
        return {
            "complete": False,
            "action": "no_signal",
            "events": [],
            "position": None,
            "last_exit": None,
        }

    stock_indicators = calculate_indicators(stock_bars)
    position: Optional[dict[str, Any]] = None
    pending: Optional[dict[str, Any]] = None
    last_exit_index: Optional[int] = None
    events: list[dict[str, Any]] = []
    last_exit: Optional[dict[str, Any]] = None
    start_index = US_MIN_HISTORY_ROWS - 1

    for index in range(start_index, len(stock_bars)):
        bar = stock_bars[index]
        indicator = stock_indicators[index]

        if pending is not None:
            active_pending = pending
            pending = None
            if not bar.ohlc_complete or float(bar.open) <= 0:
                continue
            if active_pending["side"] == "buy":
                if not us_entry_execution_allowed(
                    float(bar.open),
                    float(active_pending["signal_price"]),
                    float(active_pending["atr"]),
                ):
                    continue
                entry_price = float(bar.open)
                position = {
                    "entry_date": bar.trade_date,
                    "entry_index": index,
                    "entry_price": entry_price,
                    "signal_date": active_pending["signal_date"],
                    "signal_price": float(active_pending["signal_price"]),
                    "score": float(active_pending["score"]),
                    "stop_reference": _us_model_initial_stop(
                        entry_price,
                        float(active_pending["atr"]),
                    ),
                    "peak_price": max(entry_price, float(bar.high)),
                    "trend_exit_confirmations": 0,
                }
                events.append(
                    {
                        "signal_date": active_pending["signal_date"],
                        "signal_at": _signal_close_at(active_pending["signal_date"]),
                        "execution_date": bar.trade_date,
                        "side": "buy",
                        "label": "전략상 진입",
                        "price": _decimal(entry_price),
                        "entry_price": _decimal(entry_price),
                        "reason": "다음 미국 정규장 시가가 갭 제한 안에서 확인됐습니다.",
                        "state_after": "holding",
                    }
                )
            elif active_pending["side"] == "sell" and position is not None:
                exit_price = float(bar.open)
                entry_price = float(position["entry_price"])
                net_return = ((exit_price / entry_price) - 1.0) * 100.0
                last_exit = {
                    "signal_date": active_pending["signal_date"],
                    "exit_date": bar.trade_date,
                    "exit_price": exit_price,
                    "entry_date": position["entry_date"],
                    "entry_price": entry_price,
                    "return_rate": net_return,
                    "reason": active_pending["reason"],
                }
                events.append(
                    {
                        "signal_date": active_pending["signal_date"],
                        "signal_at": _signal_close_at(active_pending["signal_date"]),
                        "execution_date": bar.trade_date,
                        "side": "sell",
                        "label": "전략상 전량 매도",
                        "price": _decimal(exit_price),
                        "entry_price": _decimal(entry_price),
                        "return_rate": _decimal(net_return),
                        "reason": active_pending["reason"],
                        "state_after": "exited",
                    }
                )
                position = None
                last_exit_index = index

        if position is not None:
            position["peak_price"] = max(
                float(position["peak_price"]), float(bar.high)
            )

        # A condition raised at today's close cannot be modeled as a confirmed
        # entry until a later completed session supplies its opening price.
        if index >= len(stock_bars) - 1:
            continue

        if position is not None:
            reason = _us_model_exit_reason(
                position,
                bar,
                indicator,
                allow_trend_exit=(
                    index - int(position["entry_index"])
                    >= US_LIFECYCLE_MIN_HOLDING_BARS
                ),
            )
            if reason:
                pending = {
                    "side": "sell",
                    "signal_date": bar.trade_date,
                    "reason": reason,
                }
            continue

        decision = evaluate_us_entry_candidate(
            stock_bars[: index + 1],
            spy_bars[: index + 1],
            qqq_bars[: index + 1],
            sector_bars[: index + 1],
            new_entries_allowed=True,
        )
        if (
            decision.get("data_state") == "ready"
            and decision.get("action") == "entry_pending"
            and us_reentry_allowed(stock_bars, stock_indicators, index, last_exit_index)
        ):
            pending = {
                "side": "buy",
                "signal_date": bar.trade_date,
                "signal_price": float(decision["price"]),
                "atr": float((decision.get("technical") or {}).get("atr") or 0.0),
                "score": float(decision.get("score") or 0.0),
            }

    latest = latest_decision or evaluate_us_entry_candidate(
        stock_bars,
        spy_bars,
        qqq_bars,
        sector_bars,
        new_entries_allowed=True,
    )
    latest_bar = stock_bars[-1]
    latest_indicator = stock_indicators[-1]
    if position is not None:
        reason = _us_model_exit_reason(
            position,
            latest_bar,
            latest_indicator,
            allow_trend_exit=(
                len(stock_bars) - 1 - int(position["entry_index"])
                >= US_LIFECYCLE_MIN_HOLDING_BARS
            ),
        )
        action = "full_exit_pending" if reason else (
            "entered"
            if position["entry_date"] == latest_bar.trade_date
            else "holding"
        )
        pending_exit_reason = reason
    elif last_exit is not None:
        action = "exited"
        pending_exit_reason = None
    else:
        action = str(latest.get("action") or "no_signal")
        pending_exit_reason = None
    return {
        "complete": True,
        "action": action,
        "events": events,
        "position": position,
        "last_exit": last_exit,
        "pending_exit_reason": pending_exit_reason,
        "latest_decision": latest,
    }


def _history_loader(symbol: str) -> list[Any]:
    from app.services.us_market import chart_prices_range

    _, prices = chart_prices_range(
        symbol,
        range_="2y",
        interval="1d",
        refresh=True,
        limit=520,
        require_adjusted_ohlc=True,
    )
    return prices


def build_us_member_public_evidence(
    symbol: str,
    *,
    universe_date: date,
    now: Optional[datetime] = None,
    history_loader: Optional[Callable[[str], list[Any]]] = None,
) -> dict[str, Any]:
    """Build completed-session public evidence for one US stock.

    Older ready snapshots do not contain ``public_member_signals``. Rebuilding
    the full Top-100 snapshot can take several minutes or fail when an
    unrelated ticker is throttled, so the stock-detail endpoint may repair its
    three non-actionable public reasons from that stock's own adjusted daily
    history. Membership and the decision state still come from the immutable
    canonical snapshot; this helper never promotes an entry signal, including
    when the requested stock is outside the current Top-100 universe.
    """

    current = now or datetime.now(timezone.utc)
    loader = history_loader or _history_loader
    rows = loader(symbol)
    bars = us_price_bars(rows, now=current)
    if len(bars) < 64 or bars[-1].trade_date != universe_date:
        raise ValueError("completed-session member history is incomplete")

    from app.services.us_market_calendar import recent_us_market_session_dates

    expected_dates = recent_us_market_session_dates(universe_date, 64)
    observed_dates = tuple(bar.trade_date for bar in bars[-64:])
    if observed_dates != expected_dates:
        raise ValueError("completed-session member history has a session gap")

    indicators = calculate_indicators(bars)
    latest = indicators[-1]
    participation = _dollar_volume_evidence(bars)["participation_ratio"]
    if participation is None:
        raise ValueError("completed-session dollar-volume evidence is incomplete")
    three_month_return = (
        (bars[-1].close / bars[-64].close) - 1.0
        if bars[-64].close
        else None
    )
    if three_month_return is None:
        raise ValueError("completed-session 60-day evidence is incomplete")

    signal_at = _signal_close_at(universe_date)
    if signal_at is None:
        raise ValueError("US universe date is not an exchange session")
    public_reasons = build_public_signal_reasons(
        {},
        context={
            "as_of": signal_at,
            "flow_semantics": "dollar_volume_participation_proxy",
            "one_month_return": _decimal(latest["momentum20"] * 100.0),
            "three_month_return": _decimal(three_month_return * 100.0),
            "trading_value_change": _decimal((participation - 1.0) * 100.0),
        },
    )
    if not all(reason.get("available") is True for reason in public_reasons):
        raise ValueError("completed-session public evidence is unavailable")
    return {
        "code": symbol,
        "signal_date": universe_date,
        "signal_at": signal_at,
        "data_state": "ready",
        "flow_semantics": "dollar_volume_participation_proxy",
        "public_reasons": public_reasons,
        "current": {
            "action": "no_signal",
            "label": "관망",
            "position_open": False,
            "live_observation": False,
            "as_of": signal_at,
        },
    }


def _load_histories(
    symbols: list[str],
    loader: Callable[[str], list[Any]],
) -> tuple[dict[str, list[Any]], dict[str, str]]:
    histories: dict[str, list[Any]] = {}
    errors: dict[str, str] = {}
    pending = list(dict.fromkeys(symbols))
    # A single Yahoo transport failure previously invalidated the whole
    # 100-name publication until the next five-minute collector cycle. Retry
    # only failed symbols with progressively lower concurrency so a transient
    # throttle cannot leave every stock-detail screen without evidence.
    for max_workers in (12, 4, 1):
        if not pending:
            break
        errors = {}
        with ThreadPoolExecutor(
            max_workers=min(max_workers, max(1, len(pending)))
        ) as executor:
            futures = {executor.submit(loader, symbol): symbol for symbol in pending}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    histories[symbol] = future.result()
                except Exception as exc:
                    errors[symbol] = str(exc)
        pending = list(errors)
    return histories, errors


def _signal_close_at(signal_date: object) -> datetime | None:
    if not isinstance(signal_date, date):
        return None
    from app.services.us_market_calendar import us_market_session

    signal_session = us_market_session(signal_date)
    if signal_session is None:
        raise ValueError("US signal date is not an exchange session")
    return signal_session.close_at


def _decision_public_reasons(
    decision: dict[str, Any],
    *,
    as_of: datetime,
) -> list[dict[str, Any]]:
    confirmation = dict(decision.get("confirmation") or {})
    return build_public_signal_reasons(
        {},
        context={
            "as_of": as_of,
            "flow_semantics": "dollar_volume_participation_proxy",
            "one_month_return": _decimal(
                float((decision.get("technical") or {}).get("momentum20") or 0.0)
                * 100.0
            ),
            "three_month_return": _decimal(decision.get("three_month_return")),
            "trading_value_change": _decimal(
                (
                    float(
                        confirmation.get("stock_dollar_volume_participation")
                        or 1.0
                    )
                    - 1.0
                )
                * 100.0
            ),
        },
    )


def _public_member_signal(
    member: dict[str, Any],
    decision: dict[str, Any],
    *,
    as_of: datetime,
    universe_date: date | None,
) -> dict[str, Any]:
    """Persist public evidence for every Top100 member, including no-signal rows."""

    signal_date = decision.get("signal_date")
    if not isinstance(signal_date, date):
        signal_date = universe_date
    signal_at = _signal_close_at(signal_date) or as_of
    ready = decision.get("data_state") == "ready"
    action = str(decision.get("action") or "no_signal")
    if action not in {"entry_pending", "entry_watch"}:
        action = "no_signal"
    label = {
        "entry_pending": "예비 매수",
        "entry_watch": "예비 포착",
        "no_signal": "관망",
    }[action]
    public_reasons = (
        _decision_public_reasons(decision, as_of=signal_at)
        if ready
        else build_public_signal_reasons(
            {},
            context={
                "as_of": signal_at,
                "flow_semantics": "dollar_volume_participation_proxy",
            },
        )
    )
    return {
        "code": member["code"],
        "data_state": "ready" if ready else "insufficient",
        "signal_date": signal_date,
        "signal_at": signal_at,
        "flow_semantics": "dollar_volume_participation_proxy",
        "public_reasons": public_reasons,
        "current": {
            "action": action,
            "label": label,
            "position_open": False,
            "live_observation": False,
            "as_of": signal_at,
            "next_confirmation": decision.get("next_confirmation"),
        },
    }


def _candidate_item(
    member: dict[str, Any],
    decision: dict[str, Any],
    sector_symbol: str,
    as_of: datetime,
) -> dict[str, Any]:
    action = str(decision["action"])
    signal_label = "예비 매수" if action == "entry_pending" else "예비 포착"
    signal_date = decision.get("signal_date")
    signal_close_at = _signal_close_at(signal_date)
    confirmation = dict(decision.get("confirmation") or {})
    public_reasons = _decision_public_reasons(
        decision,
        as_of=signal_close_at or as_of,
    )
    return {
        "data_state": "ready",
        "strategy_version": US_STRATEGY_VERSION,
        "rollout_mode": US_ROLLOUT_MODE,
        "execution_enabled": False,
        "stateful_lifecycle_replay_enabled": US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
        "reentry_runtime_enabled": US_REENTRY_RUNTIME_ENABLED,
        "lifecycle_replay_version": US_LIFECYCLE_REPLAY_VERSION,
        "side": "buy",
        "status": "preliminary",
        "is_preliminary": True,
        "signal": signal_label,
        "signal_date": signal_date,
        "signal_at": signal_close_at or as_of,
        "updated_at": as_of,
        "price": _decimal(decision.get("price")),
        "change_rate": _decimal(decision.get("change_rate")),
        "one_month_return": _decimal(decision.get("one_month_return")),
        "three_month_return": _decimal(decision.get("three_month_return")),
        "trading_value": _decimal(decision.get("trading_value"), "0.01"),
        "trading_value_change": _decimal(decision.get("trading_value_change")),
        "score": _decimal(decision.get("score")),
        "entry_setup": decision.get("entry_setup"),
        "chase_veto": decision.get("chase_veto"),
        "reason": "미국 시장·상대강도·달러 거래대금 근거를 함께 확인했습니다.",
        "flow_semantics": "dollar_volume_participation_proxy",
        "flow_notice": "가격×거래량 기반 참여도이며 투자자 순매수나 ETF 순유입이 아닙니다.",
        "entry_score_threshold": _decimal(US_ENTRY_POLICY.entry_score),
        "public_reasons": public_reasons,
        "events": [],
        "code": member["code"],
        "name": member["name"],
        "market": member["market"],
        "currency": "USD",
        "sector": member.get("sector"),
        "signal_scope": "market",
        "market_cap_rank": member["market_cap_rank"],
        "market_cap": member.get("market_cap"),
        "universe_tier": "core",
        "is_current_universe_member": True,
        "price_through": str(signal_date or ""),
        "as_of": as_of,
        "current": {
            "action": action,
            "label": signal_label,
            "position_open": False,
            "model_exposure_percent": Decimal("0"),
            "live_observation": False,
            "score": _decimal(decision.get("score")),
            "price": _decimal(decision.get("price")),
            "as_of": as_of,
            "reasons": [
                "수정주가 기준 추세와 추격매수 제한을 확인",
                "SPY·QQQ 및 섹터 대비 상대강도를 확인",
                "종목·섹터 ETF 달러 거래대금 참여도 프록시를 확인",
            ],
            "next_confirmation": decision.get("next_confirmation"),
            "lifecycle": {
                "state": action,
                "label": signal_label,
                "stages": ["관망", "예비 포착", "매수 대기", "보유", "수익확정", "전량 매도"],
                "latest_transition": {
                    "label": signal_label,
                    "side": "buy",
                    "signal_date": signal_date,
                    "transition_date": signal_date,
                    "price": _decimal(decision.get("price")),
                },
            },
        },
        "us_evidence": {
            **confirmation,
            "sector_etf": sector_symbol,
        },
        "guard_state": "blocked" if decision.get("chase_veto") else "clear",
    }


def _model_lifecycle_item(
    member: dict[str, Any],
    decision: dict[str, Any],
    sector_symbol: str,
    replay: dict[str, Any],
    *,
    as_of: datetime,
    universe_date: date,
) -> dict[str, Any]:
    """Project one replayed model lifecycle row into the public feed shape."""

    action = str(replay.get("action") or "no_signal")
    position = replay.get("position") if isinstance(replay.get("position"), dict) else None
    # A replay may retain an earlier exit after re-entry. That historical
    # event belongs in `events`, not in the current open position fields.
    last_exit = (
        replay.get("last_exit")
        if position is None and isinstance(replay.get("last_exit"), dict)
        else None
    )
    signal_date = (
        position.get("signal_date")
        if position is not None
        else last_exit.get("signal_date")
        if last_exit is not None
        else universe_date
    )
    if not isinstance(signal_date, date):
        signal_date = universe_date
    signal_at = _signal_close_at(signal_date)
    label = _us_model_lifecycle_label(action)
    is_open = action in {"entered", "holding", "full_exit_pending"}
    is_confirmed = action in {"entered", "holding", "exited"}
    current_price = _decimal(decision.get("price"))
    entry_price = _decimal(position.get("entry_price")) if position else _decimal(
        last_exit.get("entry_price") if last_exit else None
    )
    # A re-entered model position can legitimately have an older exit in its
    # replay history. That historical exit must not be projected as the exit
    # of the *current* open position: an open row has no current exit date,
    # exit price, or realised return.
    exit_price = (
        _decimal(last_exit.get("exit_price"))
        if action == "exited" and last_exit
        else None
    )
    entry_date = (
        position.get("entry_date")
        if position
        else last_exit.get("entry_date")
        if last_exit
        else None
    )
    exit_date = (
        last_exit.get("exit_date") if action == "exited" and last_exit else None
    )
    unrealized_return = (
        _decimal((float(decision.get("price") or 0.0) / float(position["entry_price"]) - 1.0) * 100.0)
        if position is not None and float(position.get("entry_price") or 0.0) > 0
        else None
    )
    return_rate = (
        _decimal(last_exit.get("return_rate"))
        if action == "exited" and last_exit is not None
        else unrealized_return
    )
    latest_transition = {
        "label": label,
        "side": "sell" if action in {"full_exit_pending", "exited"} else "buy",
        "signal_date": signal_date,
        "transition_date": (
            exit_date if action == "exited" else entry_date if entry_date else universe_date
        ),
        "price": exit_price if action == "exited" else entry_price or current_price,
        "entry_price": entry_price,
    }
    confirmation = dict(decision.get("confirmation") or {})
    public_reasons = _decision_public_reasons(
        decision,
        as_of=_signal_close_at(universe_date) or as_of,
    )
    next_confirmation = (
        "다음 미국 정규장 시가에서 전략상 매도를 확인합니다."
        if action == "full_exit_pending"
        else "다음 완료 미국장 종가에서 위험선과 20일 가격 흐름을 다시 확인합니다."
        if is_open
        else "다음 완료 미국장에서 새 진입 조건을 다시 확인합니다."
    )
    return {
        "data_state": "ready",
        "strategy_version": US_STRATEGY_VERSION,
        "rollout_mode": US_ROLLOUT_MODE,
        "execution_enabled": False,
        "stateful_lifecycle_replay_enabled": US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
        "reentry_runtime_enabled": US_REENTRY_RUNTIME_ENABLED,
        "lifecycle_replay_version": US_LIFECYCLE_REPLAY_VERSION,
        "side": "sell" if action in {"full_exit_pending", "exited"} else "buy",
        "status": "confirmed" if is_confirmed else "preliminary",
        "is_preliminary": not is_confirmed,
        "signal": label,
        "signal_date": signal_date,
        "signal_at": signal_at or as_of,
        "updated_at": as_of,
        "price": current_price,
        "change_rate": _decimal(decision.get("change_rate")),
        "one_month_return": _decimal(decision.get("one_month_return")),
        "three_month_return": _decimal(decision.get("three_month_return")),
        "trading_value": _decimal(decision.get("trading_value"), "0.01"),
        "trading_value_change": _decimal(decision.get("trading_value_change")),
        "reason": "완료된 미국장 종가와 다음 정규장 시가를 기준으로 재현한 전략 상태입니다.",
        "flow_semantics": "dollar_volume_participation_proxy",
        "flow_notice": "가격×거래량 기반 참여도이며 투자자 순매수나 ETF 순유입이 아닙니다.",
        "public_reasons": public_reasons,
        "events": list(replay.get("events") or [])[-4:],
        "code": member["code"],
        "name": member["name"],
        "market": member["market"],
        "currency": "USD",
        "sector": member.get("sector"),
        "signal_scope": "market",
        "market_cap_rank": member["market_cap_rank"],
        "market_cap": member.get("market_cap"),
        "universe_tier": "core",
        "is_current_universe_member": True,
        "is_current_holding": is_open,
        "price_through": universe_date.isoformat(),
        "as_of": as_of,
        "current": {
            "action": action,
            "label": label,
            "position_open": is_open,
            "model_exposure_percent": _decimal(100.0 if is_open else 0.0),
            "live_observation": False,
            "price": current_price,
            "as_of": _signal_close_at(universe_date) or as_of,
            "entry_date": entry_date,
            "entry_price": entry_price,
            "exit_date": exit_date,
            "exit_price": exit_price,
            "holding_days": (
                max(0, (universe_date - entry_date).days) if isinstance(entry_date, date) else None
            ),
            "unrealized_return": unrealized_return,
            "return_rate": return_rate,
            "stop_reference": _decimal(position.get("stop_reference")) if position else None,
            "reasons": [
                "완료된 미국장 종가와 다음 정규장 시가만 사용한 모델 재현 결과입니다."
            ],
            "next_confirmation": next_confirmation,
            "lifecycle": {
                "state": action,
                "label": label,
                "stages": ["관망", "예비 포착", "예비 매수", "전략 보유", "전략 매도"],
                "latest_transition": latest_transition,
            },
        },
        "us_evidence": {
            **confirmation,
            "sector_etf": sector_symbol,
        },
        "guard_state": "blocked" if decision.get("chase_veto") else "clear",
    }


def build_us_position_lifecycle_feed(
    *,
    limit: int = 20,
    recent_days: int = 30,
    db: Optional[Session] = None,
    now: Optional[datetime] = None,
    history_loader: Optional[Callable[[str], list[Any]]] = None,
    universe_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    normalized_limit = max(1, min(US_SIGNAL_UNIVERSE_LIMIT, int(limit)))
    universe = universe_payload or build_us_signal_universe(db=db, now=current)
    members = list(universe.get("items") or [])
    new_entries_allowed = bool(
        universe.get("data_state") == "ready"
        and universe.get("universe_count") == US_SIGNAL_UNIVERSE_LIMIT
        and universe.get("new_entries_allowed", True)
    )
    base = {
        "status": "ready" if members else str(universe.get("status") or "unavailable"),
        "strategy_version": US_STRATEGY_VERSION,
        "baseline_strategy_version": US_BASELINE_STRATEGY_VERSION,
        "rollout_mode": US_ROLLOUT_MODE,
        "execution_enabled": False,
        "stateful_lifecycle_replay_enabled": US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
        "reentry_runtime_enabled": US_REENTRY_RUNTIME_ENABLED,
        "lifecycle_replay_version": US_LIFECYCLE_REPLAY_VERSION,
        "as_of": current,
        "snapshot_generated_at": current,
        "universe_as_of": universe.get("universe_as_of"),
        "ranking_as_of": universe.get("ranking_as_of"),
        "universe_count": len(members),
        "universe_members": [dict(member) for member in members],
        "universe_version": US_SIGNAL_UNIVERSE_VERSION,
        "sector_classification_version": US_SECTOR_ETF_CLASSIFICATION_VERSION,
        "universe_checksum": universe.get("checksum"),
        "universe_data_state": universe.get("data_state"),
        "recent_days": max(1, min(90, int(recent_days))),
        "confirmed_count": 0,
        "preliminary_history": [],
        "methodology": [
            "NYSE·Nasdaq 보통주와 ADR을 검증한 완료 정규장 시총 상위 100종목만 평가합니다.",
            "분할·배당 수정 OHLC와 USD 거래대금으로 공통 EMA·ATR·모멘텀 규칙을 계산합니다.",
            "125개 XNYS 세션이 쌓이지 않은 신규 상장 종목은 해당 종목만 관망하고 나머지 Top 100 평가는 계속합니다.",
            "SPY·QQQ 시장 국면, SPY·버전 고정 SEC CIK 섹터 ETF 프록시 대비 상대강도, 종목·ETF 거래대금 참여도를 독립 확인합니다.",
            "1.5ATR·7% 이격과 최근 5일 10% 초과 급등은 점수와 무관하게 추격매수로 차단합니다.",
            "재진입은 고정 유예 없이 새 20일 돌파 또는 EMA20 눌림·회복을 요구합니다.",
            "예비 매수는 다음 미국 정규장 시가가 갭 제한 안에 있을 때만 전략상 매수 확정으로 전환합니다.",
            "전략상 보유·매도는 완료 일봉으로 재현한 모델 상태이며 실제 주문·개인 보유 내역이 아닙니다.",
        ],
        "universe_policy": {
            "limit": US_SIGNAL_UNIVERSE_LIMIT,
            "version": US_SIGNAL_UNIVERSE_VERSION,
            "ranking": "completed-session market cap descending, issuer/ticker deterministic tie-break",
            "new_entries_allowed": new_entries_allowed,
            "stale_behavior": "block_new_entries_keep_last_complete_snapshot",
        },
        "public_member_signals": [],
        "items": [],
    }
    if not members:
        return {
            **base,
            "data_state": str(universe.get("data_state") or "unavailable"),
            "new_entries_allowed": False,
            "preliminary_count": 0,
            "entry_pending_count": 0,
            "evaluated_count": 0,
            "data_coverage_count": 0,
            "signal_eligible_count": 0,
            "insufficient_history_count": 0,
            "insufficient_history_codes": [],
            "history_error_count": 0,
            "sector_classification_error_count": 0,
            "source_error": universe.get("source_error"),
        }

    loader = history_loader or _history_loader
    sector_by_code = {str(item["code"]): _sector_etf(item) for item in members}
    sector_classification_errors = {
        str(item["code"]): str(item.get("cik") or "missing_cik")
        for item in members
        if not sector_by_code[str(item["code"])]
    }
    symbols = list(
        dict.fromkeys(
            ["SPY", "QQQ"]
            + [str(item["code"]) for item in members]
            + [symbol for symbol in sector_by_code.values() if symbol]
        )
    )
    histories, errors = _load_histories(symbols, loader)
    from app.services.us_market_calendar import us_signal_session_state

    market_session = str(us_signal_session_state(current)["session"])
    bars_by_symbol = {
        symbol: us_price_bars(rows, now=current, market_session=market_session)
        for symbol, rows in histories.items()
    }
    spy_bars = bars_by_symbol.get("SPY", [])
    qqq_bars = bars_by_symbol.get("QQQ", [])
    universe_date_value = universe.get("universe_as_of")
    if isinstance(universe_date_value, datetime):
        universe_date = universe_date_value.date()
    elif isinstance(universe_date_value, date):
        universe_date = universe_date_value
    else:
        try:
            universe_date = date.fromisoformat(str(universe_date_value)[:10])
        except ValueError:
            universe_date = None
    if universe_date is not None:
        incomplete_symbols = [
            symbol
            for symbol in symbols
            if not bars_by_symbol.get(symbol)
            or bars_by_symbol[symbol][-1].trade_date != universe_date
        ]
        if incomplete_symbols:
            refreshed_histories, refreshed_errors = _load_histories(
                incomplete_symbols,
                loader,
            )
            histories.update(refreshed_histories)
            for symbol in incomplete_symbols:
                if symbol in refreshed_histories:
                    errors.pop(symbol, None)
            errors.update(refreshed_errors)
            bars_by_symbol.update(
                {
                    symbol: us_price_bars(
                        rows,
                        now=current,
                        market_session=market_session,
                    )
                    for symbol, rows in refreshed_histories.items()
                }
            )
    covered_codes: set[str] = set()
    signal_eligible_codes: set[str] = set()
    insufficient_history_codes: set[str] = set()
    if (
        universe_date is not None
        and len(spy_bars) >= US_MIN_HISTORY_ROWS
        and len(qqq_bars) >= US_MIN_HISTORY_ROWS
    ):
        for member in members:
            code = str(member["code"])
            sector_symbol = sector_by_code[code]
            stock_bars = bars_by_symbol.get(code, [])
            sector_bars = bars_by_symbol.get(sector_symbol, [])
            series = (stock_bars, spy_bars, qqq_bars, sector_bars)
            if (
                _aligned_recent_sessions(*series)
                and all(bars[-1].trade_date == universe_date for bars in series)
            ):
                covered_codes.add(code)
                signal_eligible_codes.add(code)
            elif _aligned_short_history_sessions(
                stock_bars,
                spy_bars,
                qqq_bars,
                sector_bars,
                universe_date=universe_date,
            ):
                covered_codes.add(code)
                insufficient_history_codes.add(code)
    complete_source_coverage = bool(
        len(members) == US_SIGNAL_UNIVERSE_LIMIT
        and len(covered_codes) == US_SIGNAL_UNIVERSE_LIMIT
        and not errors
        and not sector_classification_errors
    )
    effective_new_entries_allowed = bool(
        new_entries_allowed and complete_source_coverage
    )
    items: list[dict[str, Any]] = []
    public_member_signals: list[dict[str, Any]] = []
    rejection_counts: Counter[str] = Counter()
    lifecycle_no_signal_count = 0
    candidate_actions: dict[str, str] = {}
    baseline_actions: dict[str, str] = {}
    comparison_codes: set[str] = set()
    replay_complete_codes: set[str] = set()
    data_coverage_count = len(covered_codes)
    for member in members:
        code = str(member["code"])
        sector_symbol = sector_by_code[code]
        stock_bars = bars_by_symbol.get(code, [])
        sector_bars = bars_by_symbol.get(sector_symbol, [])
        member_new_entries_allowed = bool(
            effective_new_entries_allowed and code in signal_eligible_codes
        )
        decision = evaluate_us_entry_candidate(
            stock_bars,
            spy_bars,
            qqq_bars,
            sector_bars,
            new_entries_allowed=member_new_entries_allowed,
        )
        action = str(decision.get("action") or "no_signal")
        candidate_actions[code] = action
        public_member_signal = _public_member_signal(
            member,
            decision,
            as_of=current,
            universe_date=universe_date,
        )
        baseline_decision = evaluate_us_momentum_watch_baseline(
            stock_bars if code in covered_codes else [],
            member,
        )
        baseline_actions[code] = str(
            baseline_decision.get("action") or "no_signal"
        )
        if code in covered_codes and baseline_decision.get("data_state") == "ready":
            comparison_codes.add(code)
        replay = replay_us_position_lifecycle(
            stock_bars,
            spy_bars,
            qqq_bars,
            sector_bars,
            latest_decision=decision,
        )
        if replay.get("complete") is True and code in signal_eligible_codes:
            replay_complete_codes.add(code)
        replay_action = str(replay.get("action") or "no_signal")
        if action == "no_signal":
            if replay_action in {
                "entered", "holding", "full_exit_pending", "exited",
            }:
                # A replayed position is not a rejected close-time candidate.
                lifecycle_no_signal_count += 1
            else:
                rejection_counts[
                    "insufficient_history"
                    if code in insufficient_history_codes
                    else "chase_guard"
                    if decision.get("chase_veto")
                    else "technical_or_evidence"
                ] += 1
        if (
            complete_source_coverage
            and universe_date is not None
            and replay.get("complete") is True
            and replay_action in {"entered", "holding", "full_exit_pending", "exited"}
        ):
            lifecycle_item = _model_lifecycle_item(
                member,
                decision,
                sector_symbol,
                replay,
                as_of=current,
                universe_date=universe_date,
            )
            if replay_action == "exited":
                exit_date = (replay.get("last_exit") or {}).get("exit_date")
                if not isinstance(exit_date, date) or exit_date < (
                    universe_date - timedelta(days=max(1, int(recent_days)))
                ):
                    lifecycle_item = None
            if lifecycle_item is not None:
                items.append(lifecycle_item)
                public_member_signal["current"] = {
                    key: value
                    for key, value in dict(lifecycle_item["current"]).items()
                    if key in {
                        "action",
                        "label",
                        "position_open",
                        "model_exposure_percent",
                        "live_observation",
                        "as_of",
                        "next_confirmation",
                    }
                }
        elif decision.get("data_state") == "ready" and action in {
            "entry_watch",
            "entry_pending",
        }:
            items.append(_candidate_item(member, decision, sector_symbol, current))
        public_member_signals.append(public_member_signal)
    stateful_replay_complete = bool(
        replay_complete_codes == signal_eligible_codes
    )
    items.sort(
        key=lambda item: (
            {
                "entered": 0,
                "holding": 1,
                "full_exit_pending": 2,
                "exited": 3,
                "entry_pending": 4,
                "entry_watch": 5,
            }.get(str(item["current"].get("action") or ""), 9),
            -float(item.get("score") or 0),
            int(item["market_cap_rank"]),
        )
    )
    selected = items[:normalized_limit]
    ordered_comparison_codes = [
        str(member["code"])
        for member in members
        if str(member["code"]) in comparison_codes
    ]
    candidate_action_counts = Counter(
        candidate_actions[code] for code in ordered_comparison_codes
    )
    baseline_action_counts = Counter(
        baseline_actions[code] for code in ordered_comparison_codes
    )
    candidate_pending_codes = {
        code
        for code in ordered_comparison_codes
        if candidate_actions[code] == "entry_pending"
    }
    baseline_pending_codes = {
        code
        for code in ordered_comparison_codes
        if baseline_actions[code] == "entry_pending"
    }
    agreement_codes = {
        code
        for code in ordered_comparison_codes
        if candidate_actions[code] == baseline_actions[code]
    }
    comparison_count = len(ordered_comparison_codes)
    agreement_rate = (
        Decimal(len(agreement_codes) * 100) / Decimal(comparison_count)
        if comparison_count
        else Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    universe_policy = {
        **dict(base["universe_policy"]),
        "new_entries_allowed": effective_new_entries_allowed and stateful_replay_complete,
    }
    projected_preliminary_count = sum(
        1 for item in selected if item.get("is_preliminary") is True
    )
    projected_confirmed_count = sum(
        1
        for item in selected
        if isinstance(item.get("current"), dict)
        and item["current"].get("position_open") is True
    )
    return {
        **base,
        "status": "ready" if effective_new_entries_allowed and stateful_replay_complete else "degraded",
        "data_state": "ready" if effective_new_entries_allowed and stateful_replay_complete else "degraded",
        "new_entries_allowed": effective_new_entries_allowed and stateful_replay_complete,
        "universe_policy": universe_policy,
        "stateful_lifecycle_replay_complete": stateful_replay_complete,
        "stateful_lifecycle_replay_eligible_count": len(signal_eligible_codes),
        "stateful_lifecycle_replay_completed_count": len(replay_complete_codes),
        "confirmed_count": projected_confirmed_count,
        "preliminary_count": projected_preliminary_count,
        "entry_pending_count": sum(
            1 for item in selected if item["current"]["action"] == "entry_pending"
        ),
        "evaluated_count": len(members),
        "data_coverage_count": data_coverage_count,
        "signal_eligible_count": len(signal_eligible_codes),
        "insufficient_history_count": len(insufficient_history_codes),
        "insufficient_history_codes": sorted(insufficient_history_codes),
        "history_error_count": len(errors),
        "sector_classification_error_count": len(sector_classification_errors),
        "sector_classification_errors": sector_classification_errors,
        "source_errors": errors,
        "shadow_comparison": {
            "candidate": US_STRATEGY_VERSION,
            "baseline": US_BASELINE_STRATEGY_VERSION,
            "universe_version": US_SIGNAL_UNIVERSE_VERSION,
            "universe_as_of": universe.get("universe_as_of"),
            "universe_checksum": universe.get("checksum"),
            "universe_count": len(members),
            "same_snapshot_evaluated_count": comparison_count,
            "comparison_complete": comparison_count == US_SIGNAL_UNIVERSE_LIMIT,
            "candidate_preliminary_count": sum(
                1
                for action in candidate_actions.values()
                if action in {"entry_watch", "entry_pending"}
            ),
            "candidate_actions": dict(candidate_actions),
            "candidate_action_counts": dict(candidate_action_counts),
            "baseline_action_counts": dict(baseline_action_counts),
            "candidate_entry_pending_count": len(candidate_pending_codes),
            "lifecycle_no_signal_count": lifecycle_no_signal_count,
            "displayed_entry_pending_count": sum(
                1
                for item in selected
                if item["current"]["action"] == "entry_pending"
            ),
            "baseline_entry_pending_count": len(baseline_pending_codes),
            "entry_pending_overlap_count": len(
                candidate_pending_codes & baseline_pending_codes
            ),
            "entry_pending_overlap_codes": sorted(
                candidate_pending_codes & baseline_pending_codes
            ),
            "candidate_only_entry_pending_count": len(
                candidate_pending_codes - baseline_pending_codes
            ),
            "baseline_only_entry_pending_count": len(
                baseline_pending_codes - candidate_pending_codes
            ),
            "action_agreement_count": len(agreement_codes),
            "action_agreement_rate": agreement_rate,
            "candidate_only_entry_pending_codes": sorted(
                candidate_pending_codes - baseline_pending_codes
            ),
            "baseline_only_entry_pending_codes": sorted(
                baseline_pending_codes - candidate_pending_codes
            ),
            "action_disagreement_codes": sorted(
                set(ordered_comparison_codes) - agreement_codes
            ),
            "baseline_method": {
                "entry_score": US_BASELINE_ENTRY_SCORE,
                "point_in_time_inputs": [
                    "regularMarketChangePercent",
                    "fiftyDayAverageChangePercent",
                    "twoHundredDayAverageChangePercent",
                    "regularMarketVolume",
                    "trailingPE",
                    "priceToBook",
                ],
                "price_weights": {
                    "one_month_return": Decimal("1.2"),
                    "three_month_return": Decimal("0.35"),
                    "one_day_return": Decimal("0.25"),
                },
                "composite_weights": {
                    "price_momentum": Decimal("0.65"),
                    "valuation": Decimal("0.15"),
                    "liquidity": Decimal("0.12"),
                    "sentiment": Decimal("0.08"),
                },
                "fallback_scores": {
                    "valuation": US_BASELINE_VALUE_SCORE,
                    "liquidity_with_regular_market_volume": US_BASELINE_LIQUIDITY_SCORE,
                    "sentiment": US_BASELINE_SENTIMENT_SCORE,
                },
            },
            "rejection_counts": dict(rejection_counts),
            "promotion_state": "simulation_only",
            "promotion_reason": "완료 일봉과 다음 정규장 시가의 모델 replay만 제공합니다. 실제 주문·개인 보유·자동 실행은 비활성입니다.",
        },
        "public_member_signals": public_member_signals,
        "items": selected,
    }


# The HTTP surface always reads this full, canonical result.  Keep the storage
# key stable across model schema upgrades: a v1 row can then trigger the
# one-time completed-session rebuild instead of leaving the US product empty
# until the next market close.
US_POSITION_LIFECYCLE_SNAPSHOT_KEY = (
    f"us-signal:position-lifecycle-us-v1-rc1:{US_SIGNAL_UNIVERSE_VERSION}:full"
)
US_POSITION_LIFECYCLE_MAX_SNAPSHOT_AGE_DAYS = 7


def _snapshot_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: value.isoformat()
        if isinstance(value, (date, datetime))
        else str(value),
    )


def _snapshot_member_checksum(payload: dict[str, Any]) -> str:
    import hashlib
    import json

    # Cover the full persisted semantic payload. Only the identity derived from
    # this digest and request-local delivery flags are excluded.
    semantic_payload = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "snapshot_id",
            "snapshot_checksum",
            "refresh_requested",
            "refresh_enqueued",
        }
    }
    encoded = json.dumps(
        semantic_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: value.isoformat()
        if isinstance(value, (date, datetime))
        else str(value),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_snapshot_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _parse_snapshot_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _sha256_is_valid(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _snapshot_universe_members(value: Any) -> Optional[dict[str, dict[str, Any]]]:
    if not isinstance(value, list) or len(value) != US_SIGNAL_UNIVERSE_LIMIT:
        return None
    members: dict[str, dict[str, Any]] = {}
    for expected_rank, member in enumerate(value, start=1):
        if not isinstance(member, dict):
            return None
        code = member.get("code")
        rank = member.get("market_cap_rank")
        market = member.get("market")
        if (
            not isinstance(code, str)
            or not code.strip()
            or code != code.strip().upper()
            or code in members
            or type(rank) is not int
            or rank != expected_rank
            or market not in {"NASDAQ", "NYSE"}
        ):
            return None
        members[code] = dict(member)
    return members


def _finite_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None
    return parsed if parsed.is_finite() else None


def _snapshot_public_reasons_are_valid(
    value: Any,
    *,
    expected_as_of: Optional[datetime],
) -> bool:
    if not isinstance(value, list) or len(value) != len(PUBLIC_SIGNAL_REASON_KEYS):
        return False
    if tuple(
        reason.get("key") if isinstance(reason, dict) else None for reason in value
    ) != PUBLIC_SIGNAL_REASON_KEYS:
        return False
    expected_labels = {
        "trend_20d": "20일 가격",
        "trend_60d": "60일 가격",
        "flow": "거래대금 참여도",
    }
    for reason in value:
        if not isinstance(reason, dict):
            return False
        observed_as_of = _parse_snapshot_datetime(reason.get("as_of"))
        if (
            reason.get("label") != expected_labels[reason["key"]]
            or reason.get("state")
            not in {"positive", "negative", "neutral"}
            or reason.get("available") is not True
            or not str(reason.get("summary") or "").strip()
            or observed_as_of is None
            or (
                expected_as_of is not None
                and observed_as_of != expected_as_of.astimezone(timezone.utc)
            )
        ):
            return False
        if reason["key"] == "flow" and reason.get("note") != US_DOLLAR_VOLUME_NOTICE:
            return False
    return True


def _snapshot_public_member_signals_are_valid(
    value: Any,
    *,
    universe_date: Optional[date],
    universe_members: Optional[dict[str, dict[str, Any]]],
    insufficient_history_codes: set[str],
    expected_close_at: Optional[datetime],
) -> bool:
    """Validate new per-member evidence while accepting legacy snapshots without it."""

    if value is None:
        return True
    if (
        not isinstance(value, list)
        or len(value) != US_SIGNAL_UNIVERSE_LIMIT
        or universe_date is None
        or universe_members is None
    ):
        return False
    observed_codes: set[str] = set()
    for signal in value:
        if not isinstance(signal, dict):
            return False
        code = signal.get("code")
        current = signal.get("current")
        signal_date = _parse_snapshot_date(signal.get("signal_date"))
        signal_at = _parse_snapshot_datetime(signal.get("signal_at"))
        reasons = signal.get("public_reasons")
        is_insufficient = code in insufficient_history_codes
        if (
            not isinstance(code, str)
            or code not in universe_members
            or code in observed_codes
            or not isinstance(current, dict)
            or signal_date != universe_date
            or signal_at is None
            or (
                expected_close_at is not None
                and signal_at != expected_close_at.astimezone(timezone.utc)
            )
            or signal.get("flow_semantics")
            != "dollar_volume_participation_proxy"
            or signal.get("data_state")
            != ("insufficient" if is_insufficient else "ready")
            or current.get("action")
            not in {
                "no_signal",
                "entry_watch",
                "entry_pending",
                "entered",
                "holding",
                "full_exit_pending",
                "exited",
            }
            or current.get("position_open")
            is not (current.get("action") in {"entered", "holding", "full_exit_pending"})
            or current.get("live_observation") is not False
            or _parse_snapshot_datetime(current.get("as_of")) != signal_at
        ):
            return False
        if is_insufficient:
            if (
                current.get("action") != "no_signal"
                or not isinstance(reasons, list)
                or [
                    reason.get("key") if isinstance(reason, dict) else None
                    for reason in reasons
                ]
                != list(PUBLIC_SIGNAL_REASON_KEYS)
                or any(
                    not isinstance(reason, dict)
                    or reason.get("available") is not False
                    or reason.get("state") != "unavailable"
                    or _parse_snapshot_datetime(reason.get("as_of")) != signal_at
                    for reason in reasons
                )
                or reasons[-1].get("label") != "거래대금 참여도"
                or reasons[-1].get("note") != US_DOLLAR_VOLUME_NOTICE
            ):
                return False
        elif not _snapshot_public_reasons_are_valid(
            reasons,
            expected_as_of=expected_close_at,
        ):
            return False
        observed_codes.add(code)
    return observed_codes == set(universe_members)


def _snapshot_model_lifecycle_item_is_valid(
    item: dict[str, Any],
    *,
    universe_date: date,
    member: dict[str, Any],
    expected_close_at: Optional[datetime],
) -> bool:
    """Validate a replayed model position separately from a close candidate."""

    current = item.get("current")
    if not isinstance(current, dict):
        return False
    action = str(current.get("action") or "")
    lifecycle = current.get("lifecycle")
    transition = lifecycle.get("latest_transition") if isinstance(lifecycle, dict) else None
    signal_date = _parse_snapshot_date(item.get("signal_date"))
    signal_at = _parse_snapshot_datetime(item.get("signal_at"))
    current_as_of = _parse_snapshot_datetime(current.get("as_of"))
    entry_date = _parse_snapshot_date(current.get("entry_date"))
    exit_date = _parse_snapshot_date(current.get("exit_date"))
    entry_price = _finite_decimal(current.get("entry_price"))
    current_price = _finite_decimal(current.get("price"))
    exposure = _finite_decimal(current.get("model_exposure_percent"))
    expected_open = action in {"entered", "holding", "full_exit_pending"}
    expected_confirmed = action in {"entered", "holding", "exited"}
    expected_exposure = Decimal("100") if expected_open else Decimal("0")
    expected_label = _us_model_lifecycle_label(action)
    expected_signal_at = _signal_close_at(signal_date) if signal_date else None
    expected_sector_etf = sector_etf_for_cik(member.get("cik"))
    public_reasons = item.get("public_reasons")
    evidence = item.get("us_evidence")
    events = item.get("events")
    if (
        action not in {"entered", "holding", "full_exit_pending", "exited"}
        or item.get("status") != ("confirmed" if expected_confirmed else "preliminary")
        or item.get("is_preliminary") is not (not expected_confirmed)
        or item.get("side") != ("sell" if action in {"full_exit_pending", "exited"} else "buy")
        or item.get("lifecycle_replay_version") != US_LIFECYCLE_REPLAY_VERSION
        or item.get("stateful_lifecycle_replay_enabled")
        is not US_STATEFUL_LIFECYCLE_REPLAY_ENABLED
        or item.get("reentry_runtime_enabled") is not US_REENTRY_RUNTIME_ENABLED
        or item.get("price_through") != universe_date.isoformat()
        or signal_date is None
        or signal_date > universe_date
        or signal_at is None
        or expected_signal_at is None
        or signal_at != expected_signal_at.astimezone(timezone.utc)
        or current_as_of is None
        or (
            expected_close_at is not None
            and current_as_of != expected_close_at.astimezone(timezone.utc)
        )
        or current.get("position_open") is not expected_open
        or exposure != expected_exposure
        or current.get("live_observation") is not False
        or current.get("label") != expected_label
        or not isinstance(lifecycle, dict)
        or lifecycle.get("state") != action
        or lifecycle.get("label") != expected_label
        or not isinstance(transition, dict)
        or transition.get("label") != expected_label
        or not isinstance(events, list)
        or not events
        or entry_date is None
        or entry_date > universe_date
        or entry_price is None
        or entry_price <= 0
        or current_price is None
        or current_price <= 0
        or not isinstance(evidence, dict)
        or evidence.get("quality_state") != "ready"
        or evidence.get("sector_etf") != expected_sector_etf
        or not _snapshot_public_reasons_are_valid(
            public_reasons,
            expected_as_of=expected_close_at,
        )
    ):
        return False
    if expected_open:
        stop_reference = _finite_decimal(current.get("stop_reference"))
        if stop_reference is None or stop_reference <= 0 or stop_reference >= entry_price:
            return False
    if action == "exited":
        if exit_date is None or exit_date > universe_date or _finite_decimal(current.get("exit_price")) is None:
            return False
    elif exit_date is not None:
        return False
    return True


def _snapshot_items_are_valid(
    value: Any,
    *,
    universe_date: Optional[date],
    universe_members: Optional[dict[str, dict[str, Any]]],
    expected_close_at: Optional[datetime] = None,
) -> bool:
    if not isinstance(value, list):
        return False
    if universe_date is None or universe_members is None:
        return False
    codes: set[str] = set()
    ranks: set[int] = set()
    for item in value:
        if not isinstance(item, dict):
            return False
        code = item.get("code")
        rank = item.get("market_cap_rank")
        current = item.get("current")
        member = universe_members.get(str(code or ""))
        signal_date = _parse_snapshot_date(item.get("signal_date"))
        signal_at = _parse_snapshot_datetime(item.get("signal_at"))
        if (
            not isinstance(code, str)
            or not code.strip()
            or code != code.strip().upper()
            or code in codes
            or member is None
            or type(rank) is not int
            or not 1 <= rank <= US_SIGNAL_UNIVERSE_LIMIT
            or rank != member.get("market_cap_rank")
            or rank in ranks
            or item.get("data_state") != "ready"
            or item.get("strategy_version") != US_STRATEGY_VERSION
            or item.get("rollout_mode") != US_ROLLOUT_MODE
            or item.get("execution_enabled") is not False
            or item.get("stateful_lifecycle_replay_enabled")
            is not US_STATEFUL_LIFECYCLE_REPLAY_ENABLED
            or item.get("reentry_runtime_enabled") is not US_REENTRY_RUNTIME_ENABLED
            or item.get("lifecycle_replay_version") != US_LIFECYCLE_REPLAY_VERSION
            or item.get("currency") != "USD"
            or item.get("market") != member.get("market")
            or item.get("signal_scope") != "market"
            or item.get("universe_tier") != "core"
            or item.get("is_current_universe_member") is not True
            or item.get("price_through") != universe_date.isoformat()
            or signal_at is None
            or item.get("flow_semantics") != "dollar_volume_participation_proxy"
            or not isinstance(current, dict)
        ):
            return False
        action = current.get("action")
        if action in {"entered", "holding", "full_exit_pending", "exited"}:
            if not _snapshot_model_lifecycle_item_is_valid(
                item,
                universe_date=universe_date,
                member=member,
                expected_close_at=expected_close_at,
            ):
                return False
            codes.add(code)
            ranks.add(rank)
            continue
        lifecycle = current.get("lifecycle")
        if not isinstance(lifecycle, dict):
            return False
        exposure = current.get("model_exposure_percent")
        exposure_value = _finite_decimal(exposure)
        score = _finite_decimal(item.get("score"))
        current_score = _finite_decimal(current.get("score"))
        entry_threshold = _finite_decimal(item.get("entry_score_threshold"))
        price = _finite_decimal(item.get("price"))
        current_price = _finite_decimal(current.get("price"))
        evidence = item.get("us_evidence")
        public_reasons = item.get("public_reasons")
        transition = lifecycle.get("latest_transition")
        expected_sector_etf = (
            sector_etf_for_cik(member.get("cik")) if isinstance(member, dict) else ""
        )
        expected_label = "예비 매수" if action == "entry_pending" else "예비 포착"
        if (
            action not in {"entry_watch", "entry_pending"}
            or item.get("side") != "buy"
            or item.get("status") != "preliminary"
            or item.get("is_preliminary") is not True
            or signal_date != universe_date
            or str(item.get("signal_date")) != universe_date.isoformat()
            or signal_at.date() != universe_date
            or (
                expected_close_at is not None
                and signal_at != expected_close_at.astimezone(timezone.utc)
            )
            or item.get("events") != []
            or current.get("position_open") is not False
            or current.get("live_observation") is not False
            or exposure_value is None
            or exposure_value != 0
            or lifecycle.get("state") != action
            or lifecycle.get("label") != expected_label
            or current.get("label") != expected_label
            or item.get("signal") != expected_label
            or score is None
            or not Decimal("0") <= score <= Decimal("100")
            or current_score != score
            or entry_threshold != Decimal(str(US_ENTRY_POLICY.entry_score))
            or price is None
            or price <= 0
            or current_price != price
            or item.get("guard_state") not in {"clear", "blocked"}
            or item.get("entry_setup") not in {None, "trend_continuation", "early_turn"}
            or item.get("chase_veto")
            not in {
                None,
                "ema20_extension_atr",
                "ema20_extension_percent",
                "momentum5_cooldown",
            }
            or (item.get("guard_state") == "clear")
            != (item.get("chase_veto") is None)
            or not isinstance(evidence, dict)
            or evidence.get("quality_state") != "ready"
            or type(evidence.get("available_count")) is not int
            or evidence.get("available_count") != 4
            or not expected_sector_etf
            or expected_sector_etf not in US_SECTOR_ETFS
            or evidence.get("sector_etf") != expected_sector_etf
            or not _snapshot_public_reasons_are_valid(
                public_reasons,
                expected_as_of=expected_close_at,
            )
            or not isinstance(transition, dict)
            or transition.get("side") != "buy"
            or _parse_snapshot_date(transition.get("signal_date")) != universe_date
            or _parse_snapshot_date(transition.get("transition_date"))
            != universe_date
        ):
            return False
        market_regime = evidence.get("market_regime")
        regime_score = (
            _finite_decimal(market_regime.get("score"))
            if isinstance(market_regime, dict)
            else None
        )
        relative_strength = _finite_decimal(evidence.get("relative_strength_20d"))
        stock_sector_relative = _finite_decimal(
            evidence.get("stock_sector_relative_strength_20d")
        )
        sector_market_relative = _finite_decimal(
            evidence.get("sector_market_relative_strength_20d")
        )
        stock_participation = _finite_decimal(
            evidence.get("stock_dollar_volume_participation")
        )
        stock_pressure = _finite_decimal(evidence.get("stock_accumulation_pressure"))
        sector_participation = _finite_decimal(
            evidence.get("sector_dollar_volume_participation")
        )
        if (
            regime_score is None
            or not Decimal("0") <= regime_score <= Decimal("100")
            or relative_strength is None
            or stock_sector_relative is None
            or sector_market_relative is None
            or stock_participation is None
            or sector_participation is None
            or (
                evidence.get("stock_accumulation_pressure") is not None
                and stock_pressure is None
            )
        ):
            return False
        expected_regime_state = (
            "risk_on"
            if regime_score >= Decimal("66")
            else "neutral"
            if regime_score >= Decimal("50")
            else "risk_off"
        )
        regime_supportive = expected_regime_state != "risk_off"
        market_relative_supportive = relative_strength >= Decimal(
            str(US_RELATIVE_STRENGTH_FLOOR)
        )
        sector_relative_supportive = stock_sector_relative >= Decimal("-0.03")
        relative_supportive = (
            market_relative_supportive and sector_relative_supportive
        )
        stock_flow_supportive = bool(
            stock_participation >= Decimal(str(US_MIN_STOCK_PARTICIPATION))
            and (stock_pressure is None or stock_pressure >= Decimal("-0.15"))
        )
        sector_flow_supportive = bool(
            sector_participation >= Decimal(str(US_MIN_SECTOR_PARTICIPATION))
            and sector_market_relative >= Decimal("-0.03")
        )
        evidence_allowed = bool(
            regime_supportive
            and relative_supportive
            and (stock_flow_supportive or sector_flow_supportive)
        )
        supportive_count = sum(
            (
                regime_supportive,
                relative_supportive,
                stock_flow_supportive,
                sector_flow_supportive,
            )
        )
        if (
            not isinstance(market_regime, dict)
            or market_regime.get("state") != expected_regime_state
            or market_regime.get("supportive") is not regime_supportive
            or evidence.get("market_relative_supportive")
            is not market_relative_supportive
            or evidence.get("sector_relative_supportive")
            is not sector_relative_supportive
            or evidence.get("allowed") is not evidence_allowed
            or type(evidence.get("supportive_count")) is not int
            or evidence.get("supportive_count") != supportive_count
        ):
            return False
        if action == "entry_pending" and (
            item.get("guard_state") != "clear"
            or item.get("entry_setup") not in {"trend_continuation", "early_turn"}
            or item.get("chase_veto") is not None
            or score < entry_threshold
            or not evidence_allowed
        ):
            return False
        codes.add(code)
        ranks.add(rank)
    return True


def _action_counts(value: Any) -> Optional[dict[str, int]]:
    if not isinstance(value, dict):
        return None
    allowed = {"entry_pending", "entry_watch", "no_signal"}
    if any(key not in allowed for key in value):
        return None
    counts = {key: 0 for key in allowed}
    for key, raw_count in value.items():
        if type(raw_count) is not int or raw_count < 0:
            return None
        counts[key] = raw_count
    return counts


def _decimal_mapping_equals(value: Any, expected: dict[str, Decimal]) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == set(expected)
        and all(_finite_decimal(value.get(key)) == target for key, target in expected.items())
    )


def _code_set(value: Any, universe_codes: set[str]) -> Optional[set[str]]:
    if not isinstance(value, list):
        return None
    if any(not isinstance(code, str) for code in value):
        return None
    codes = set(value)
    if len(codes) != len(value) or not codes.issubset(universe_codes):
        return None
    return codes


def _shadow_comparison_is_valid(
    payload: dict[str, Any],
    *,
    universe_date: Optional[date],
    universe_members: Optional[dict[str, dict[str, Any]]],
) -> bool:
    shadow = payload.get("shadow_comparison")
    items = payload.get("items")
    if (
        not isinstance(shadow, dict)
        or not isinstance(items, list)
        or universe_date is None
        or universe_members is None
    ):
        return False
    universe_codes = set(universe_members)
    candidate_counts = _action_counts(shadow.get("candidate_action_counts"))
    baseline_counts = _action_counts(shadow.get("baseline_action_counts"))
    candidate_actions = shadow.get("candidate_actions")
    if (
        candidate_counts is None
        or baseline_counts is None
        or not isinstance(candidate_actions, dict)
        or set(candidate_actions) != universe_codes
        or any(action not in {"entry_pending", "entry_watch", "no_signal"} for action in candidate_actions.values())
    ):
        return False
    expected_baseline_actions = {
        code: str(
            evaluate_us_momentum_watch_baseline([object()], member).get("action")
            or "no_signal"
        )
        for code, member in universe_members.items()
    }
    expected_baseline_counts = Counter(expected_baseline_actions.values())
    expected_baseline_pending_codes = {
        code
        for code, action in expected_baseline_actions.items()
        if action == "entry_pending"
    }
    expected_candidate_actions = {
        code: str(candidate_actions[code]) for code in universe_codes
    }
    pending_codes = {
        code for code, action in expected_candidate_actions.items()
        if action == "entry_pending"
    }
    watch_count = sum(
        1 for action in expected_candidate_actions.values()
        if action == "entry_watch"
    )
    expected_disagreement_codes = {
        code
        for code in universe_codes
        if expected_candidate_actions[code] != expected_baseline_actions[code]
    }
    expected_agreement_count = US_SIGNAL_UNIVERSE_LIMIT - len(
        expected_disagreement_codes
    )
    overlap_codes = _code_set(shadow.get("entry_pending_overlap_codes"), universe_codes)
    candidate_only_codes = _code_set(
        shadow.get("candidate_only_entry_pending_codes"), universe_codes
    )
    baseline_only_codes = _code_set(
        shadow.get("baseline_only_entry_pending_codes"), universe_codes
    )
    disagreement_codes = _code_set(
        shadow.get("action_disagreement_codes"), universe_codes
    )
    if any(
        value is None
        for value in (
            overlap_codes,
            candidate_only_codes,
            baseline_only_codes,
            disagreement_codes,
        )
    ):
        return False
    assert overlap_codes is not None
    assert candidate_only_codes is not None
    assert baseline_only_codes is not None
    assert disagreement_codes is not None
    candidate_pending_count = shadow.get("candidate_entry_pending_count")
    lifecycle_no_signal_count = shadow.get("lifecycle_no_signal_count")
    displayed_pending_count = shadow.get("displayed_entry_pending_count")
    baseline_pending_count = shadow.get("baseline_entry_pending_count")
    overlap_count = shadow.get("entry_pending_overlap_count")
    candidate_only_count = shadow.get("candidate_only_entry_pending_count")
    baseline_only_count = shadow.get("baseline_only_entry_pending_count")
    agreement_count = shadow.get("action_agreement_count")
    agreement_rate = _finite_decimal(shadow.get("action_agreement_rate"))
    baseline_method = shadow.get("baseline_method")
    rejection_counts = shadow.get("rejection_counts")
    rejection_counts_valid = bool(
        isinstance(rejection_counts, dict)
        and type(lifecycle_no_signal_count) is int
        and lifecycle_no_signal_count >= 0
        and set(rejection_counts).issubset(
            {"chase_guard", "technical_or_evidence", "insufficient_history"}
        )
        and all(type(count) is int and count >= 0 for count in rejection_counts.values())
        and sum(rejection_counts.values()) + lifecycle_no_signal_count
        == candidate_counts["no_signal"]
    )
    required_baseline_inputs = [
        "regularMarketChangePercent",
        "fiftyDayAverageChangePercent",
        "twoHundredDayAverageChangePercent",
        "regularMarketVolume",
        "trailingPE",
        "priceToBook",
    ]
    numeric_counts = (
        candidate_pending_count,
        lifecycle_no_signal_count,
        displayed_pending_count,
        baseline_pending_count,
        overlap_count,
        candidate_only_count,
        baseline_only_count,
        agreement_count,
    )
    if any(type(value) is not int or value < 0 for value in numeric_counts):
        return False
    expected_rate = (
        Decimal(expected_agreement_count * 100) / Decimal(US_SIGNAL_UNIVERSE_LIMIT)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return bool(
        shadow.get("candidate") == US_STRATEGY_VERSION
        and shadow.get("baseline") == US_BASELINE_STRATEGY_VERSION
        and shadow.get("universe_version") == US_SIGNAL_UNIVERSE_VERSION
        and str(shadow.get("universe_as_of")) == universe_date.isoformat()
        and shadow.get("universe_checksum") == payload.get("universe_checksum")
        and shadow.get("universe_count") == US_SIGNAL_UNIVERSE_LIMIT
        and shadow.get("same_snapshot_evaluated_count") == US_SIGNAL_UNIVERSE_LIMIT
        and shadow.get("comparison_complete") is True
        and shadow.get("candidate_preliminary_count")
        == candidate_counts["entry_pending"] + candidate_counts["entry_watch"]
        and sum(candidate_counts.values()) == US_SIGNAL_UNIVERSE_LIMIT
        and sum(baseline_counts.values()) == US_SIGNAL_UNIVERSE_LIMIT
        and baseline_counts
        == {
            "entry_pending": expected_baseline_counts.get("entry_pending", 0),
            "entry_watch": expected_baseline_counts.get("entry_watch", 0),
            "no_signal": expected_baseline_counts.get("no_signal", 0),
        }
        and candidate_counts["entry_pending"] == len(pending_codes)
        and candidate_counts["entry_watch"] == watch_count
        and candidate_counts["no_signal"]
        == US_SIGNAL_UNIVERSE_LIMIT - candidate_counts["entry_pending"] - candidate_counts["entry_watch"]
        and candidate_pending_count == len(pending_codes)
        # Candidate actions are calculated at the completed close. A
        # candidate can subsequently become an entered/holding model position
        # after its next regular-session open, so the UI's pending count is a
        # separate display-state metric.
        and displayed_pending_count
        == sum(
            1
            for item in items
            if isinstance(item, dict)
            and isinstance(item.get("current"), dict)
            and item["current"].get("action") == "entry_pending"
        )
        and payload.get("entry_pending_count") == displayed_pending_count
        and baseline_counts["entry_pending"] == baseline_pending_count
        and overlap_count == len(overlap_codes)
        and candidate_only_count == len(candidate_only_codes)
        and baseline_only_count == len(baseline_only_codes)
        and candidate_pending_count == overlap_count + candidate_only_count
        and baseline_pending_count == overlap_count + baseline_only_count
        and pending_codes == overlap_codes | candidate_only_codes
        and expected_baseline_pending_codes
        == overlap_codes | baseline_only_codes
        and not (overlap_codes & candidate_only_codes)
        and not (overlap_codes & baseline_only_codes)
        and not (candidate_only_codes & baseline_only_codes)
        and (candidate_only_codes | baseline_only_codes).issubset(disagreement_codes)
        and not (overlap_codes & disagreement_codes)
        and disagreement_codes == expected_disagreement_codes
        and agreement_count == expected_agreement_count
        and agreement_rate == expected_rate
        and shadow.get("promotion_state") == "simulation_only"
        and "실제 주문" in str(shadow.get("promotion_reason") or "")
        and isinstance(baseline_method, dict)
        and _finite_decimal(baseline_method.get("entry_score"))
        == US_BASELINE_ENTRY_SCORE
        and baseline_method.get("point_in_time_inputs") == required_baseline_inputs
        and _decimal_mapping_equals(
            baseline_method.get("price_weights"),
            {
                "one_month_return": Decimal("1.2"),
                "three_month_return": Decimal("0.35"),
                "one_day_return": Decimal("0.25"),
            },
        )
        and _decimal_mapping_equals(
            baseline_method.get("composite_weights"),
            {
                "price_momentum": Decimal("0.65"),
                "valuation": Decimal("0.15"),
                "liquidity": Decimal("0.12"),
                "sentiment": Decimal("0.08"),
            },
        )
        and _decimal_mapping_equals(
            baseline_method.get("fallback_scores"),
            {
                "valuation": US_BASELINE_VALUE_SCORE,
                "liquidity_with_regular_market_volume": US_BASELINE_LIQUIDITY_SCORE,
                "sentiment": US_BASELINE_SENTIMENT_SCORE,
            },
        )
        and rejection_counts_valid
    )


def _ready_snapshot_semantics_are_valid(
    payload: dict[str, Any],
    *,
    expected_close_at: Optional[datetime] = None,
    expected_generated_at: Optional[datetime] = None,
    current_time: Optional[datetime] = None,
) -> bool:
    universe_date = _parse_snapshot_date(payload.get("universe_as_of"))
    payload_as_of = _parse_snapshot_datetime(payload.get("as_of"))
    payload_generated_at = _parse_snapshot_datetime(
        payload.get("snapshot_generated_at")
    )
    normalized_expected_generated_at = (
        _parse_snapshot_datetime(expected_generated_at)
        if expected_generated_at is not None
        else None
    )
    normalized_current_time = (
        _parse_snapshot_datetime(current_time) if current_time is not None else None
    )
    temporal_metadata_valid = bool(
        payload_as_of is not None
        and payload_generated_at is not None
        and payload_as_of == payload_generated_at
        and (
            normalized_expected_generated_at is None
            or payload_generated_at == normalized_expected_generated_at
        )
        and (
            normalized_current_time is None
            or payload_generated_at <= normalized_current_time + timedelta(minutes=5)
        )
        and (
            expected_close_at is None
            or payload_generated_at
            >= expected_close_at.astimezone(timezone.utc)
            + US_SIGNAL_PUBLICATION_GRACE
        )
    )
    universe_members = _snapshot_universe_members(payload.get("universe_members"))
    universe_manifest_valid = _universe_snapshot_payload_is_valid(
        {
            "status": "ready",
            "data_state": "ready",
            "universe_version": payload.get("universe_version"),
            "universe_as_of": payload.get("universe_as_of"),
            "ranking_as_of": payload.get("ranking_as_of"),
            "universe_count": payload.get("universe_count"),
            "checksum": payload.get("universe_checksum"),
            "items": payload.get("universe_members"),
        },
        require_source_evidence=False,
    )
    coverage = payload.get("coverage")
    universe_policy = payload.get("universe_policy")
    items = payload.get("items")
    if not isinstance(items, list):
        return False
    pending_count = sum(
        1
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get("current"), dict)
        and item["current"].get("action") == "entry_pending"
    )
    return bool(
        payload.get("strategy_version") == US_STRATEGY_VERSION
        and payload.get("baseline_strategy_version")
        == US_BASELINE_STRATEGY_VERSION
        and payload.get("universe_version") == US_SIGNAL_UNIVERSE_VERSION
        and payload.get("sector_classification_version")
        == US_SECTOR_ETF_CLASSIFICATION_VERSION
        and payload.get("rollout_mode") == US_ROLLOUT_MODE
        and payload.get("execution_enabled") is False
        and payload.get("stateful_lifecycle_replay_enabled")
        is US_STATEFUL_LIFECYCLE_REPLAY_ENABLED
        and payload.get("reentry_runtime_enabled") is US_REENTRY_RUNTIME_ENABLED
        and payload.get("lifecycle_replay_version") == US_LIFECYCLE_REPLAY_VERSION
        and payload.get("stateful_lifecycle_replay_complete") is True
        and payload.get("stateful_lifecycle_replay_eligible_count")
        == payload.get("signal_eligible_count")
        and payload.get("stateful_lifecycle_replay_completed_count")
        == payload.get("signal_eligible_count")
        and payload.get("status") == "ready"
        and payload.get("data_state") == "ready"
        and payload.get("universe_data_state") == "ready"
        and payload.get("new_entries_allowed") is True
        and temporal_metadata_valid
        and universe_date is not None
        and str(payload.get("universe_as_of")) == universe_date.isoformat()
        and _sha256_is_valid(payload.get("universe_checksum"))
        and universe_members is not None
        and universe_manifest_valid
        and type(payload.get("universe_count")) is int
        and payload.get("universe_count") == US_SIGNAL_UNIVERSE_LIMIT
        and type(payload.get("evaluated_count")) is int
        and payload.get("evaluated_count") == US_SIGNAL_UNIVERSE_LIMIT
        and type(payload.get("data_coverage_count")) is int
        and payload.get("data_coverage_count") == US_SIGNAL_UNIVERSE_LIMIT
        and type(payload.get("signal_eligible_count")) is int
        and 0 <= payload.get("signal_eligible_count") <= US_SIGNAL_UNIVERSE_LIMIT
        and type(payload.get("insufficient_history_count")) is int
        and 0
        <= payload.get("insufficient_history_count")
        <= US_SIGNAL_UNIVERSE_LIMIT
        and payload.get("signal_eligible_count")
        + payload.get("insufficient_history_count")
        == US_SIGNAL_UNIVERSE_LIMIT
        and isinstance(payload.get("insufficient_history_codes"), list)
        and len(payload.get("insufficient_history_codes"))
        == payload.get("insufficient_history_count")
        and len(set(payload.get("insufficient_history_codes")))
        == payload.get("insufficient_history_count")
        and set(payload.get("insufficient_history_codes"))
        <= set(universe_members)
        and type(payload.get("history_error_count")) is int
        and payload.get("history_error_count") == 0
        and type(payload.get("sector_classification_error_count")) is int
        and payload.get("sector_classification_error_count") == 0
        and payload.get("source_errors") in ({}, None)
        and payload.get("sector_classification_errors") in ({}, None)
        and payload.get("preliminary_history") == []
        and type(payload.get("confirmed_count")) is int
        and payload.get("confirmed_count")
        == sum(
            1
            for item in items
            if isinstance(item, dict)
            and isinstance(item.get("current"), dict)
            and item["current"].get("position_open") is True
        )
        and type(payload.get("preliminary_count")) is int
        and payload.get("preliminary_count")
        == sum(
            1 for item in items if isinstance(item, dict) and item.get("is_preliminary") is True
        )
        and type(payload.get("entry_pending_count")) is int
        and payload.get("entry_pending_count") == pending_count
        and isinstance(coverage, dict)
        and coverage.get("complete") is True
        and type(coverage.get("universe_count")) is int
        and coverage.get("universe_count") == US_SIGNAL_UNIVERSE_LIMIT
        and type(coverage.get("evaluated_count")) is int
        and coverage.get("evaluated_count") == US_SIGNAL_UNIVERSE_LIMIT
        and type(coverage.get("data_coverage_count")) is int
        and coverage.get("data_coverage_count") == US_SIGNAL_UNIVERSE_LIMIT
        and coverage.get("signal_eligible_count")
        == payload.get("signal_eligible_count")
        and coverage.get("insufficient_history_count")
        == payload.get("insufficient_history_count")
        and type(coverage.get("history_error_count")) is int
        and coverage.get("history_error_count") == 0
        and type(coverage.get("sector_classification_error_count")) is int
        and coverage.get("sector_classification_error_count") == 0
        and coverage.get("coverage_percent") == 100.0
        and isinstance(universe_policy, dict)
        and universe_policy.get("limit") == US_SIGNAL_UNIVERSE_LIMIT
        and universe_policy.get("version") == US_SIGNAL_UNIVERSE_VERSION
        and universe_policy.get("new_entries_allowed") is True
        and _snapshot_public_member_signals_are_valid(
            payload.get("public_member_signals"),
            universe_date=universe_date,
            universe_members=universe_members,
            insufficient_history_codes=set(
                payload.get("insufficient_history_codes") or []
            ),
            expected_close_at=expected_close_at,
        )
        and _snapshot_items_are_valid(
            items,
            universe_date=universe_date,
            universe_members=universe_members,
            expected_close_at=expected_close_at,
        )
        and _shadow_comparison_is_valid(
            payload,
            universe_date=universe_date,
            universe_members=universe_members,
        )
    )


def _authoritative_universe_matches(db: Session, payload: dict[str, Any]) -> bool:
    """Bind the lifecycle snapshot to the immutable daily universe DB row."""

    from app.models import MarketRankingSnapshot

    universe_date = _parse_snapshot_date(payload.get("universe_as_of"))
    if universe_date is None:
        return False
    snapshot_id = f"{US_SIGNAL_UNIVERSE_VERSION}:{universe_date.isoformat()}"
    try:
        snapshot = db.get(MarketRankingSnapshot, snapshot_id)
        authoritative = (
            _decode_valid_universe_snapshot(snapshot) if snapshot is not None else None
        )
    except Exception:
        return False
    if authoritative is None:
        return False
    return bool(
        authoritative.get("checksum") == payload.get("universe_checksum")
        and authoritative.get("universe_as_of")
        == str(payload.get("universe_as_of"))
        and authoritative.get("ranking_as_of")
        == str(payload.get("ranking_as_of"))
        and authoritative.get("universe_count") == payload.get("universe_count")
        and _snapshot_json({"items": authoritative.get("items")})
        == _snapshot_json({"items": payload.get("universe_members")})
    )


def expected_completed_us_session_date(now: Optional[datetime] = None) -> date:
    """Return the latest official XNYS session whose close has passed."""

    from app.services.us_market_calendar import latest_completed_us_market_session

    return latest_completed_us_market_session(now).session_date


def _block_snapshot_entries(
    payload: dict[str, Any],
    *,
    data_state: str,
    reason: str,
) -> dict[str, Any]:
    from copy import deepcopy

    result = deepcopy(payload)
    result["status"] = "degraded" if result.get("items") else "preparing"
    result["data_state"] = data_state
    result["new_entries_allowed"] = False
    result["refresh_required"] = True
    result["state_reason"] = reason
    universe_policy = dict(result.get("universe_policy") or {})
    universe_policy["new_entries_allowed"] = False
    result["universe_policy"] = universe_policy
    for collection_name in ("items", "public_member_signals"):
        for item in list(result.get(collection_name) or []):
            if not isinstance(item, dict):
                continue
            current = item.get("current") if isinstance(item.get("current"), dict) else {}
            lifecycle = (
                current.get("lifecycle")
                if isinstance(current.get("lifecycle"), dict)
                else {}
            )
            lifecycle["state"] = "no_signal"
            lifecycle["label"] = "관망"
            current.update(
                {
                    "action": "no_signal",
                    "label": "관망",
                    "position_open": False,
                    "model_exposure_percent": 0,
                    "live_observation": False,
                    "next_confirmation": reason,
                    "lifecycle": lifecycle,
                }
            )
            item.update(
                {
                    "action": "no_signal",
                    "signal": "관망",
                    "is_preliminary": False,
                    "is_current_holding": False,
                    "latest_preliminary": None,
                    "current": current,
                }
            )
    shadow = (
        dict(result.get("shadow_comparison") or {})
        if isinstance(result.get("shadow_comparison"), dict)
        else {}
    )
    if shadow:
        shadow["candidate_entry_pending_count"] = 0
        shadow["displayed_entry_pending_count"] = 0
        result["shadow_comparison"] = shadow
    result["confirmed_count"] = 0
    result["preliminary_count"] = 0
    result["total_preliminary_count"] = 0
    result["entry_pending_count"] = 0
    return result


def canonical_us_position_lifecycle_snapshot(
    payload: dict[str, Any],
    *,
    generated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Attach one immutable identity and strict coverage state to a full scan."""

    current = generated_at or datetime.now(timezone.utc)
    universe_count = int(payload.get("universe_count") or 0)
    evaluated_count = int(payload.get("evaluated_count") or 0)
    coverage_count = int(payload.get("data_coverage_count") or 0)
    signal_eligible_count = int(payload.get("signal_eligible_count") or 0)
    insufficient_history_count = int(payload.get("insufficient_history_count") or 0)
    history_error_count = int(payload.get("history_error_count") or 0)
    sector_classification_error_count = int(
        payload.get("sector_classification_error_count") or 0
    )
    count_complete = bool(
        payload.get("status") == "ready"
        and payload.get("universe_data_state") == "ready"
        and universe_count == US_SIGNAL_UNIVERSE_LIMIT
        and evaluated_count == US_SIGNAL_UNIVERSE_LIMIT
        and coverage_count == US_SIGNAL_UNIVERSE_LIMIT
        and 0 <= signal_eligible_count <= US_SIGNAL_UNIVERSE_LIMIT
        and 0 <= insufficient_history_count <= US_SIGNAL_UNIVERSE_LIMIT
        and signal_eligible_count + insufficient_history_count
        == US_SIGNAL_UNIVERSE_LIMIT
        and history_error_count == 0
        and sector_classification_error_count == 0
    )
    result = dict(payload)
    result.update(
        {
            "status": "ready" if count_complete else "degraded",
            "data_state": "ready" if count_complete else "degraded",
            "snapshot_generated_at": current,
            "sector_classification_error_count": sector_classification_error_count,
            "coverage": {
                "universe_count": universe_count,
                "evaluated_count": evaluated_count,
                "data_coverage_count": coverage_count,
                "signal_eligible_count": signal_eligible_count,
                "insufficient_history_count": insufficient_history_count,
                "history_error_count": history_error_count,
                "sector_classification_error_count": sector_classification_error_count,
                "coverage_percent": round(
                    (coverage_count / US_SIGNAL_UNIVERSE_LIMIT) * 100.0,
                    2,
                ),
                "complete": count_complete,
            },
            "new_entries_allowed": count_complete,
            "stateful_lifecycle_replay_enabled": US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
            "reentry_runtime_enabled": US_REENTRY_RUNTIME_ENABLED,
            "refresh_required": not count_complete,
            "confirmed_count": sum(
                1
                for item in list(payload.get("items") or [])
                if isinstance(item, dict)
                and isinstance(item.get("current"), dict)
                and item["current"].get("position_open") is True
            ),
            "preliminary_count": sum(
                1
                for item in list(payload.get("items") or [])
                if isinstance(item, dict) and item.get("is_preliminary") is True
            ),
            "entry_pending_count": sum(
                1
                for item in list(payload.get("items") or [])
                if isinstance(item, dict)
                and isinstance(item.get("current"), dict)
                and item["current"].get("action") == "entry_pending"
            ),
        }
    )
    structure_complete = False
    if count_complete:
        universe_date = _parse_snapshot_date(result.get("universe_as_of"))
        try:
            from app.services.us_market_calendar import us_market_session

            universe_session = (
                us_market_session(universe_date) if universe_date is not None else None
            )
        except Exception:
            universe_session = None
        structure_complete = bool(
            universe_session is not None
            and _ready_snapshot_semantics_are_valid(
                result,
                expected_close_at=universe_session.close_at,
                expected_generated_at=current,
                current_time=current,
            )
        )
    complete = bool(count_complete and structure_complete)
    if not complete:
        result["status"] = "degraded"
        result["data_state"] = "degraded"
        result["new_entries_allowed"] = False
        result["refresh_required"] = True
        result["coverage"] = {
            **dict(result.get("coverage") or {}),
            "complete": False,
        }
        result = _block_snapshot_entries(
            result,
            data_state="degraded",
            reason="미국 상위 100종목의 동일 완료 세션 데이터가 모두 확정돼야 합니다.",
        )
    checksum = _snapshot_member_checksum(result)
    result["snapshot_checksum"] = checksum
    result["snapshot_id"] = (
        f"{US_STRATEGY_VERSION}:{result.get('universe_as_of') or 'unknown'}:{checksum[:16]}"
    )
    return result


def us_position_lifecycle_preparing_payload(
    *,
    now: Optional[datetime] = None,
    source_error: Optional[str] = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "status": "preparing",
        "data_state": "preparing",
        "strategy_version": US_STRATEGY_VERSION,
        "baseline_strategy_version": US_BASELINE_STRATEGY_VERSION,
        "rollout_mode": US_ROLLOUT_MODE,
        "execution_enabled": False,
        "stateful_lifecycle_replay_enabled": US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
        "reentry_runtime_enabled": US_REENTRY_RUNTIME_ENABLED,
        "lifecycle_replay_version": US_LIFECYCLE_REPLAY_VERSION,
        "as_of": current,
        "snapshot_generated_at": None,
        "snapshot_id": None,
        "snapshot_checksum": None,
        "universe_as_of": None,
        "ranking_as_of": None,
        "universe_count": 0,
        "universe_version": US_SIGNAL_UNIVERSE_VERSION,
        "sector_classification_version": US_SECTOR_ETF_CLASSIFICATION_VERSION,
        "evaluated_count": 0,
        "data_coverage_count": 0,
        "signal_eligible_count": 0,
        "insufficient_history_count": 0,
        "insufficient_history_codes": [],
        "confirmed_count": 0,
        "preliminary_count": 0,
        "entry_pending_count": 0,
        "new_entries_allowed": False,
        "refresh_required": True,
        "coverage": {
            "universe_count": 0,
            "evaluated_count": 0,
            "data_coverage_count": 0,
            "signal_eligible_count": 0,
            "insufficient_history_count": 0,
            "history_error_count": 0,
            "sector_classification_error_count": 0,
            "coverage_percent": 0.0,
            "complete": False,
        },
        "methodology": [
            "완료된 미국 정규장의 시총 상위 100종목 스냅샷을 준비하고 있습니다."
        ],
        "items": [],
        "preliminary_history": [],
    }
    if source_error:
        result["source_error"] = source_error
    return result


def save_us_position_lifecycle_snapshot(
    db: Session,
    payload: dict[str, Any],
    *,
    generated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Atomically replace the one canonical full-feed snapshot."""

    from app.models import MarketQuantSignalSnapshot

    current = generated_at or datetime.now(timezone.utc)
    prepared = canonical_us_position_lifecycle_snapshot(
        payload,
        generated_at=current,
    )
    universe_date = _parse_snapshot_date(prepared.get("universe_as_of"))
    try:
        from app.services.us_market_calendar import us_market_session

        universe_session = (
            us_market_session(universe_date) if universe_date is not None else None
        )
    except Exception:
        universe_session = None
    if (
        prepared.get("data_state") != "ready"
        or universe_session is None
        or not _ready_snapshot_semantics_are_valid(
            prepared,
            expected_close_at=universe_session.close_at,
            expected_generated_at=current,
            current_time=current,
        )
        or not _authoritative_universe_matches(db, prepared)
    ):
        raise ValueError("Refusing to replace the last-good US signal snapshot with degraded data")
    stored_at = current.astimezone(timezone.utc).replace(tzinfo=None)
    serialized = _snapshot_json(prepared)
    try:
        snapshot = db.get(MarketQuantSignalSnapshot, US_POSITION_LIFECYCLE_SNAPSHOT_KEY)
        if snapshot is None:
            snapshot = MarketQuantSignalSnapshot(
                cache_key=US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
                payload=serialized,
                generated_at=stored_at,
            )
            db.add(snapshot)
        else:
            existing_generated_at = snapshot.generated_at
            if (
                existing_generated_at.tzinfo is not None
                and existing_generated_at.utcoffset() is not None
            ):
                existing_generated_at = existing_generated_at.astimezone(
                    timezone.utc
                ).replace(tzinfo=None)
            try:
                existing_payload = json.loads(snapshot.payload)
            except (TypeError, ValueError):
                existing_payload = None
            existing_universe_date = (
                _parse_snapshot_date(existing_payload.get("universe_as_of"))
                if isinstance(existing_payload, dict)
                else None
            )
            if (
                existing_universe_date is not None
                and universe_date is not None
                and existing_universe_date > universe_date
            ):
                raise ValueError("Refusing to overwrite a newer US signal session")
            if existing_generated_at >= stored_at:
                if (
                    existing_generated_at == stored_at
                    and isinstance(existing_payload, dict)
                    and existing_payload.get("snapshot_checksum")
                    == prepared.get("snapshot_checksum")
                ):
                    return dict(existing_payload)
                raise ValueError("Refusing to overwrite a newer US signal snapshot")

            # Compare-and-swap at the database layer prevents a slower worker
            # from overwriting a snapshot committed by another app instance
            # after the read above.
            updated = db.execute(
                update(MarketQuantSignalSnapshot)
                .where(
                    MarketQuantSignalSnapshot.cache_key
                    == US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
                    MarketQuantSignalSnapshot.generated_at < stored_at,
                )
                .values(payload=serialized, generated_at=stored_at)
                .execution_options(synchronize_session=False)
            )
            if updated.rowcount != 1:
                raise ValueError("US signal snapshot compare-and-swap lost")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return dict(prepared)


def load_us_position_lifecycle_snapshot(
    db: Session,
    *,
    now: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    """Load and validate the canonical full feed without upstream I/O."""

    import json

    from app.models import MarketQuantSignalSnapshot

    current = now or datetime.now(timezone.utc)
    snapshot = db.get(MarketQuantSignalSnapshot, US_POSITION_LIFECYCLE_SNAPSHOT_KEY)
    if snapshot is None:
        return None
    try:
        payload = json.loads(snapshot.payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("strategy_version") != US_STRATEGY_VERSION:
        # A release that changes lifecycle semantics must not render the old
        # row as if it were compatible.  Return a fail-closed marker that lets
        # the collector perform its bounded schema rebuild even during a US
        # regular session (using the most recent completed daily bars).
        upgrade = us_position_lifecycle_preparing_payload(now=current)
        upgrade["schema_upgrade_required"] = True
        upgrade["source_strategy_version"] = payload.get("strategy_version")
        return upgrade
    generated_at = snapshot.generated_at
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    else:
        generated_at = generated_at.astimezone(timezone.utc)
    universe_date = _parse_snapshot_date(payload.get("universe_as_of"))
    checksum = str(payload.get("snapshot_checksum") or "")
    if (
        not _ready_snapshot_semantics_are_valid(
            payload,
            expected_generated_at=generated_at,
            current_time=current,
        )
        or universe_date is None
        or not _sha256_is_valid(checksum)
        or checksum != _snapshot_member_checksum(payload)
        or payload.get("snapshot_id")
        != f"{US_STRATEGY_VERSION}:{universe_date.isoformat()}:{checksum[:16]}"
    ):
        return None
    if not _authoritative_universe_matches(db, payload):
        return None
    payload["snapshot_generated_at"] = generated_at.isoformat()
    try:
        from app.services.us_market_calendar import us_market_session

        universe_session = us_market_session(universe_date)
        if universe_session is None or not _ready_snapshot_semantics_are_valid(
            payload,
            expected_close_at=universe_session.close_at,
            expected_generated_at=generated_at,
            current_time=current,
        ):
            return None
        expected_date = expected_completed_us_session_date(current)
    except Exception:
        return _block_snapshot_entries(
            payload,
            data_state="calendar_unavailable",
            reason="미국 거래소 캘린더 확인 전에는 새 진입을 차단합니다.",
        )
    too_old = (current.astimezone(timezone.utc) - generated_at).days > (
        US_POSITION_LIFECYCLE_MAX_SNAPSHOT_AGE_DAYS
    )
    if universe_date is None or universe_date != expected_date or too_old:
        payload = _block_snapshot_entries(
            payload,
            data_state="stale",
            reason="최근 완료된 미국 정규장 스냅샷 갱신을 기다리고 있습니다.",
        )
    else:
        payload["refresh_required"] = False
        payload["new_entries_allowed"] = True
    return payload


def us_position_lifecycle_refresh_due(
    payload: Optional[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> bool:
    if not payload or payload.get("refresh_required"):
        return True
    if payload.get("status") != "ready" or payload.get("data_state") != "ready":
        return True
    if us_position_lifecycle_schema_upgrade_due(payload):
        return True
    universe_date = _parse_snapshot_date(payload.get("universe_as_of"))
    try:
        expected_date = expected_completed_us_session_date(now)
    except Exception:
        return True
    return bool(universe_date is None or universe_date != expected_date)


def us_position_lifecycle_schema_upgrade_due(
    payload: Optional[dict[str, Any]],
) -> bool:
    """Require a one-time rebuild for snapshots predating per-member evidence."""

    if payload and payload.get("schema_upgrade_required") is True:
        return True
    if (
        not payload
        or payload.get("status") != "ready"
        or payload.get("data_state") != "ready"
        or payload.get("universe_count") != US_SIGNAL_UNIVERSE_LIMIT
        or not isinstance(payload.get("universe_members"), list)
        or len(payload["universe_members"]) != US_SIGNAL_UNIVERSE_LIMIT
    ):
        return False
    public_member_signals = payload.get("public_member_signals")
    return bool(
        not isinstance(public_member_signals, list)
        or len(public_member_signals) != US_SIGNAL_UNIVERSE_LIMIT
    )


def refresh_us_position_lifecycle_snapshot(
    db: Session,
    *,
    now: Optional[datetime] = None,
    history_loader: Optional[Callable[[str], list[Any]]] = None,
    universe_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the expensive 100-name scan off-request and publish only complete data."""

    current = now or datetime.now(timezone.utc)
    try:
        generated = build_us_position_lifecycle_feed(
            limit=US_SIGNAL_UNIVERSE_LIMIT,
            recent_days=90,
            db=db,
            now=current,
            history_loader=history_loader,
            universe_payload=universe_payload,
        )
        canonical = canonical_us_position_lifecycle_snapshot(
            generated,
            generated_at=current,
        )
        if canonical.get("data_state") != "ready":
            logger.warning(
                "US position-lifecycle refresh produced degraded data: "
                "universe_status=%s universe_state=%s universe_as_of=%s "
                "universe_count=%s evaluated_count=%s data_coverage_count=%s "
                "history_error_count=%s sector_error_count=%s source_error=%s "
                "source_errors=%s",
                generated.get("status"),
                generated.get("universe_data_state") or generated.get("data_state"),
                generated.get("universe_as_of"),
                generated.get("universe_count"),
                generated.get("evaluated_count"),
                generated.get("data_coverage_count"),
                generated.get("history_error_count"),
                generated.get("sector_classification_error_count"),
                generated.get("source_error"),
                generated.get("source_errors"),
            )
            db.rollback()
            previous = load_us_position_lifecycle_snapshot(db, now=current)
            return previous or canonical
        return save_us_position_lifecycle_snapshot(
            db,
            canonical,
            generated_at=current,
        )
    except Exception as exc:
        logger.exception("US position-lifecycle refresh failed before publication")
        db.rollback()
        previous = load_us_position_lifecycle_snapshot(db, now=current)
        if previous is not None:
            return _block_snapshot_entries(
                previous,
                data_state="degraded",
                reason="미국 신호 스냅샷 갱신 실패로 새 진입을 잠시 차단합니다.",
            )
        return us_position_lifecycle_preparing_payload(
            now=current,
            source_error=str(exc),
        )
