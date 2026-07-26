from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    DailyPrice,
    DisclosureItem,
    InvestorFlow,
    NewsItem,
    ResearchReport,
    StockMaster,
    StockNewsSnapshot,
)


KST = ZoneInfo("Asia/Seoul")
STRATEGY_VERSION = "position-lifecycle-v2.0"
STRATEGY_NAME = "추세·모멘텀 포지션 상태 전략"
MIN_HISTORY_ROWS = 125
WARMUP_ROWS = 65
BACKTEST_ROWS = 252
ENTRY_SCORE = 65.0
EXIT_SCORE = 42.0
PARTIAL_EXIT_FRACTION = 0.5
PARTIAL_EXIT_R = 2.0
INITIAL_STOP_ATR = 2.0
TRAILING_STOP_ATR = 2.6
MIN_EXECUTION_COST_PER_SIDE = 0.00125
MAX_EXECUTION_COST_PER_SIDE = 0.005
DEFAULT_EXECUTION_COST_PER_SIDE = 0.002

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


def _normalize_prices(rows: list[DailyPrice]) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for row in sorted(rows, key=lambda item: item.trade_date):
        close = _safe_number(row.close)
        if close is None:
            continue
        open_price = _safe_number(row.open) or close
        high = max(_safe_number(row.high) or close, close, open_price)
        low = min(_safe_number(row.low) or close, close, open_price)
        volume = max(0.0, float(row.volume or 0))
        bars.append(
            PriceBar(
                trade_date=row.trade_date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                trading_value=max(0.0, float(row.trading_value or 0)),
            )
        )
    return bars


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
        reference20 = closes[index - 20] if index >= 20 else closes[0]
        momentum20 = (bar.close / reference20) - 1.0 if reference20 else 0.0
        prior_highs = [item.high for item in bars[max(0, index - 20) : index]]
        prior_high = max(prior_highs) if prior_highs else bar.high
        high_distance = (bar.close / prior_high) - 1.0 if prior_high else 0.0
        average_volume = volume20[index] or 0.0
        volume_ratio = bar.volume / average_volume if average_volume > 0 else 1.0
        atr_percent = atr14[index] / bar.close if bar.close else 0.0
        ema20_slope = (
            (ema20[index] / ema20[index - 5]) - 1.0
            if index >= 5 and ema20[index - 5]
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
                "ema20_slope": ema20_slope,
                "momentum20": momentum20,
                "prior_high": prior_high,
                "high_distance": high_distance,
                "volume_ratio": volume_ratio,
                "atr": atr14[index],
                "atr_percent": atr_percent,
                "trend_score": trend_score,
                "momentum_score": momentum_score,
                "breakout_score": breakout_score,
                "volume_score": volume_score,
                "average_trading_value": trading_value20[index] or 0.0,
            }
        )
    return indicators


def _entry_signal(bar: PriceBar, indicator: dict[str, float]) -> bool:
    return bool(
        indicator["score"] >= ENTRY_SCORE
        and bar.close > indicator["ema20"] > indicator["ema60"]
        and indicator["ema20_slope"] > 0
        and indicator["momentum20"] > 0.015
    )


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


def _position_levels(
    position: dict[str, Any],
    indicator: dict[str, float],
    peak_price: float,
) -> dict[str, float]:
    entry_price = float(position["entry_price"])
    initial_risk = max(float(position["initial_risk"]), entry_price * 0.01)
    partial_target = entry_price + (initial_risk * PARTIAL_EXIT_R)
    volatility_stop = peak_price - (indicator["atr"] * TRAILING_STOP_ATR)
    if position.get("partial_exit_done"):
        trailing_stop = max(entry_price, indicator["ema20"], volatility_stop)
    else:
        trailing_stop = max(float(position["initial_stop"]), volatility_stop)
    return {
        "initial_risk": initial_risk,
        "partial_target": partial_target,
        "trailing_stop": trailing_stop,
    }


def _full_exit_signal(
    bar: PriceBar,
    indicator: dict[str, float],
    position: dict[str, Any],
    peak_price: float,
) -> tuple[bool, str, dict[str, float]]:
    levels = _position_levels(position, indicator, peak_price)
    if bar.close <= levels["trailing_stop"]:
        return True, "변동성 및 추적 위험선 이탈", levels
    if indicator["score"] <= EXIT_SCORE:
        return True, "종합 점수가 청산 기준보다 약해짐", levels
    if bar.close < indicator["ema20"] and indicator["ema10"] < indicator["ema20"]:
        return True, "20일선과 단기 추세가 함께 이탈됨", levels
    return False, "추세 유지", levels


def _partial_exit_signal(
    bar: PriceBar,
    indicator: dict[str, float],
    position: dict[str, Any],
    peak_price: float,
) -> tuple[bool, str, dict[str, float]]:
    levels = _position_levels(position, indicator, peak_price)
    if position.get("partial_exit_done"):
        return False, "1차 분할매도 완료", levels
    if bar.close >= levels["partial_target"]:
        return True, "초기 위험의 2배 수익 구간에 도달함", levels
    momentum_faded = (
        peak_price >= float(position["entry_price"]) + (levels["initial_risk"] * 1.5)
        and bar.close < indicator["ema10"]
        and indicator["score"] < 58.0
    )
    if momentum_faded:
        return True, "수익 구간 진입 후 단기 탄력이 둔화됨", levels
    return False, "분할매도 기준 미도달", levels


def _signal_reason(indicator: dict[str, float], side: str) -> str:
    momentum = indicator["momentum20"] * 100.0
    if side == "buy":
        return f"상승 추세와 20일 모멘텀 {momentum:+.1f}%가 함께 확인됨"
    return f"추세 점수가 {indicator['score']:.1f}점으로 약화됨"


def _simulate(bars: list[PriceBar], indicators: list[dict[str, float]]) -> dict[str, Any]:
    start_index = max(WARMUP_ROWS, len(bars) - BACKTEST_ROWS)
    events: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    pending: Optional[dict[str, Any]] = None
    position: Optional[dict[str, Any]] = None
    cash = 1.0
    shares = 0.0
    equity_curve: list[float] = []
    peak_equity = 1.0
    max_drawdown = 0.0
    execution_costs: list[float] = []

    for index in range(start_index, len(bars)):
        bar = bars[index]
        indicator = indicators[index]

        if pending:
            execution_price = bar.open or bar.close
            execution_cost = float(pending["execution_cost"])
            execution_costs.append(execution_cost)
            if pending["side"] == "buy":
                entry_equity = cash
                shares = cash / (execution_price * (1.0 + execution_cost))
                initial_risk = max(float(pending["atr"]) * INITIAL_STOP_ATR, execution_price * 0.01)
                cash = 0.0
                position = {
                    "entry_date": bar.trade_date,
                    "entry_price": execution_price,
                    "entry_index": index,
                    "signal_date": pending["signal_date"],
                    "score": pending["score"],
                    "peak_price": execution_price,
                    "initial_stop": max(1.0, execution_price - initial_risk),
                    "initial_risk": initial_risk,
                    "initial_shares": shares,
                    "entry_equity": entry_equity,
                    "realized_proceeds": 0.0,
                    "gross_realized_value": 0.0,
                    "partial_exit_done": False,
                    "partial_exit_date": None,
                    "partial_exit_price": None,
                    "remaining_fraction": 1.0,
                }
                events.append(
                    {
                        "signal_date": pending["signal_date"],
                        "execution_date": bar.trade_date,
                        "side": "buy",
                        "label": "전략상 진입",
                        "price": _price(execution_price),
                        "score": _decimal(pending["score"]),
                        "reason": pending["reason"],
                        "position_percent": _decimal(100.0),
                        "state_after": "holding",
                    }
                )
            elif pending["side"] == "partial_sell" and position:
                sold_shares = shares * PARTIAL_EXIT_FRACTION
                proceeds = sold_shares * execution_price * (1.0 - execution_cost)
                cash += proceeds
                shares -= sold_shares
                position["realized_proceeds"] += proceeds
                position["gross_realized_value"] += sold_shares * execution_price
                position["partial_exit_done"] = True
                position["partial_exit_date"] = bar.trade_date
                position["partial_exit_price"] = execution_price
                position["remaining_fraction"] = shares / float(position["initial_shares"])
                events.append(
                    {
                        "signal_date": pending["signal_date"],
                        "execution_date": bar.trade_date,
                        "side": "partial_sell",
                        "label": "1차 분할매도",
                        "price": _price(execution_price),
                        "score": _decimal(pending["score"]),
                        "reason": pending["reason"],
                        "position_percent": _decimal(position["remaining_fraction"] * 100.0),
                        "state_after": "partially_exited",
                    }
                )
            elif position:
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
                    "partial_exit_date": position.get("partial_exit_date"),
                    "partial_exit_price": _price(position.get("partial_exit_price")),
                    "exit_date": bar.trade_date,
                    "exit_price": _price(execution_price),
                    "gross_return": _decimal(gross_return * 100.0),
                    "net_return": _decimal(net_return * 100.0),
                    "holding_days": holding_days,
                    "status": "closed",
                    "exit_reason": pending["reason"],
                    "remaining_percent": _decimal(0.0),
                }
                trades.append(trade)
                events.append(
                    {
                        "signal_date": pending["signal_date"],
                        "execution_date": bar.trade_date,
                        "side": "sell",
                        "label": "전략상 청산",
                        "price": _price(execution_price),
                        "score": _decimal(pending["score"]),
                        "reason": pending["reason"],
                        "return_rate": trade["net_return"],
                        "holding_days": holding_days,
                        "position_percent": _decimal(0.0),
                        "state_after": "exited",
                    }
                )
                shares = 0.0
                position = None
            pending = None

        if position:
            position["peak_price"] = max(position["peak_price"], bar.close)
            marked_equity = cash + (shares * bar.close * (1.0 - _execution_cost(indicator)))
        else:
            marked_equity = cash
        equity_curve.append(marked_equity)
        peak_equity = max(peak_equity, marked_equity)
        max_drawdown = min(max_drawdown, (marked_equity / peak_equity) - 1.0)

        if index >= len(bars) - 1:
            continue
        if position:
            should_exit, reason, _ = _full_exit_signal(bar, indicator, position, position["peak_price"])
            should_partial, partial_reason, _ = _partial_exit_signal(
                bar,
                indicator,
                position,
                position["peak_price"],
            )
            if should_exit:
                pending = {
                    "side": "sell",
                    "signal_date": bar.trade_date,
                    "score": indicator["score"],
                    "reason": reason,
                    "execution_cost": _execution_cost(indicator),
                }
            elif should_partial:
                pending = {
                    "side": "partial_sell",
                    "signal_date": bar.trade_date,
                    "score": indicator["score"],
                    "reason": partial_reason,
                    "execution_cost": _execution_cost(indicator),
                }
        elif _entry_signal(bar, indicator):
            pending = {
                "side": "buy",
                "signal_date": bar.trade_date,
                "score": indicator["score"],
                "reason": _signal_reason(indicator, "buy"),
                "atr": indicator["atr"],
                "execution_cost": _execution_cost(indicator),
            }

    final_equity = equity_curve[-1] if equity_curve else 1.0
    closed_trades = [trade for trade in trades if trade["status"] == "closed"]
    winners = [trade for trade in closed_trades if float(trade["net_return"] or 0) > 0]
    net_returns = [float(trade["net_return"] or 0) for trade in closed_trades]
    holding_days = [int(trade["holding_days"] or 0) for trade in closed_trades]
    benchmark = (bars[-1].close / bars[start_index].close) - 1.0 if len(bars) > start_index else 0.0

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
        trades.append(
            {
                "entry_date": position["entry_date"],
                "entry_price": _price(position["entry_price"]),
                "partial_exit_date": position.get("partial_exit_date"),
                "partial_exit_price": _price(position.get("partial_exit_price")),
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

    completed = len(closed_trades)
    sample_state = "sufficient" if completed >= 5 else "limited"
    return {
        "start_index": start_index,
        "events": events,
        "trades": trades,
        "position": position,
        "performance": {
            "period_start": bars[start_index].trade_date,
            "period_end": bars[-1].trade_date,
            "trading_days": len(bars) - start_index,
            "completed_trades": completed,
            "win_rate": _decimal((len(winners) / completed) * 100.0) if completed else None,
            "average_return": _decimal(sum(net_returns) / completed) if completed else None,
            "strategy_return": _decimal((final_equity - 1.0) * 100.0),
            "benchmark_return": _decimal(benchmark * 100.0),
            "max_return": _decimal(max(net_returns)) if net_returns else None,
            "max_drawdown": _decimal(max_drawdown * 100.0),
            "average_holding_days": _decimal(sum(holding_days) / completed, "0.1") if completed else None,
            "transaction_cost_per_side": _decimal(
                (sum(execution_costs) / len(execution_costs) if execution_costs else DEFAULT_EXECUTION_COST_PER_SIDE)
                * 100.0
            ),
            "sample_state": sample_state,
            "sample_note": (
                f"완료 거래 {completed}회로 성과 표본이 제한적입니다."
                if sample_state == "limited"
                else f"완료 거래 {completed}회의 동일 규칙 모의검증 결과입니다."
            ),
        },
        "pending": pending,
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
    live_price = _safe_number(live_quote.get("price"))
    if live_price is None:
        return confirmed, False
    live_date = live_quote.get("trade_date") or now.date()
    if isinstance(live_date, str):
        try:
            live_date = date.fromisoformat(live_date[:10])
        except ValueError:
            live_date = now.date()
    market_is_live = (
        now.weekday() < 5
        and time(8, 0) <= now.time() < time(15, 40)
        and live_date == now.date()
    )
    if live_date > confirmed[-1].trade_date and not market_is_live:
        live_date = confirmed[-1].trade_date
    live_volume = max(0.0, float(live_quote.get("volume") or 0))
    bars = list(confirmed)
    if bars[-1].trade_date == live_date:
        previous = bars[-1]
        bars[-1] = PriceBar(
            trade_date=previous.trade_date,
            open=previous.open,
            high=max(previous.high, live_price),
            low=min(previous.low, live_price),
            close=live_price,
            volume=live_volume or previous.volume,
            trading_value=max(previous.trading_value, live_price * live_volume),
        )
    elif live_date > bars[-1].trade_date:
        bars.append(
            PriceBar(
                trade_date=live_date,
                open=live_price,
                high=live_price,
                low=live_price,
                close=live_price,
                volume=live_volume,
                trading_value=live_price * live_volume,
            )
        )
    else:
        return confirmed, False
    return bars, market_is_live


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

    trading_values = [int(item.trading_value or 0) for item in recent_prices if item.trading_value]
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


def _current_signal(
    confirmed: list[PriceBar],
    simulation: dict[str, Any],
    live_quote: Optional[dict[str, Any]],
    now: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    observation_bars, live_observation = _live_bar(confirmed, live_quote, now)
    indicators = _indicator_rows(observation_bars)
    bar = observation_bars[-1]
    indicator = indicators[-1]
    position = simulation.get("position")
    last_event = simulation.get("events", [])[-1] if simulation.get("events") else None

    state = "waiting"
    label = "진입 전 관망"
    next_confirmation = "종가에서 진입 조건이 완성되는지 확인"
    reasons: list[str] = []
    stop_reference: Optional[float] = None
    partial_target: Optional[float] = None
    levels: list[dict[str, Any]] = []
    if position:
        peak_price = max(float(position["peak_price"]), bar.close)
        should_exit, exit_reason, position_levels = _full_exit_signal(
            bar, indicator, position, peak_price
        )
        should_partial, partial_reason, _ = _partial_exit_signal(
            bar, indicator, position, peak_price
        )
        stop_reference = position_levels["trailing_stop"]
        partial_target = position_levels["partial_target"]
        if should_exit:
            state = "full_exit_pending"
            label = "청산 조건 확인"
            reasons.append(exit_reason)
            next_confirmation = "종가에서 이탈가 확정되면 다음 거래일 시가에 전략상 청산"
        elif should_partial:
            state = "partial_exit_pending"
            label = "1차 분할매도 조건 확인"
            reasons.append(partial_reason)
            next_confirmation = "종가에서 기준이 확정되면 다음 거래일 시가에 모델 비중을 50%로 축소"
        elif position.get("partial_exit_done"):
            state = "partially_exited"
            label = "1차 분할매도 후 보유"
            reasons.append("수익 일부를 확정하고 나머지 50% 모델 비중을 추적 중")
            next_confirmation = "20일선·고점 대비 ATR 추적선의 청산 조건을 확인"
        elif position["entry_date"] == confirmed[-1].trade_date:
            state = "entered"
            label = "전략상 진입 완료"
            reasons.append("전일 종가 신호를 다음 거래일 시가에 반영함")
            next_confirmation = "초기 위험선과 1차 분할매도 기준을 매일 확인"
        else:
            state = "holding"
            label = "전략상 보유 중"
            reasons.append("추세가 유지되고 분할매도·청산 기준은 미도달")
            next_confirmation = "1차 분할매도 가격과 추적 위험선을 매일 확인"

        if not position.get("partial_exit_done"):
            levels.append(
                {
                    "key": "partial_exit",
                    "label": "1차 분할매도",
                    "price": _price(partial_target),
                    "condition": "초기 위험의 2배 수익 구간에 도달하면 50% 축소",
                }
            )
        levels.append(
            {
                "key": "full_exit",
                "label": "청산 위험선",
                "price": _price(stop_reference),
                "condition": "추적 위험선 이탈 또는 종합 점수 42점 이하",
            }
        )
    elif _entry_signal(bar, indicator):
        state = "entry_pending"
        label = "진입 조건 확인"
        reasons.append(_signal_reason(indicator, "buy"))
        next_confirmation = "종가에서 조건이 확정되면 다음 거래일 시가에 전략상 진입"
        levels.append(
            {
                "key": "entry",
                "label": "진입 확인선",
                "price": _price(max(indicator["ema20"], indicator["prior_high"])),
                "condition": "65점 이상·20일 상승 추세·20일 모멘텀 동시 충족",
            }
        )
    else:
        reasons.append("진입 기준 65점과 상승 추세 조건을 모두 충족하지 않음")
        if last_event and last_event.get("side") == "sell":
            state = "exited"
            label = "전략상 청산 후 관망"
            exit_reason = last_event.get("reason") or "청산 기준 충족"
            reasons[0] = f"{exit_reason} 판단으로 모델 포지션이 0%가 됨"

    reasons.append(f"종합 신호 {indicator['score']:.1f}점")
    current_price = _safe_number(live_quote.get("price")) if live_quote else None
    current_price = current_price or bar.close
    entry_price = float(position["entry_price"]) if position else None
    unrealized_return = None
    holding_days = None
    if position and entry_price:
        current_cost = _execution_cost(indicator)
        remaining_shares = float(position["initial_shares"]) * float(position["remaining_fraction"])
        marked_proceeds = remaining_shares * current_price * (1.0 - current_cost)
        unrealized_return = (
            (float(position["realized_proceeds"]) + marked_proceeds) / float(position["entry_equity"])
        ) - 1.0
        holding_days = max(1, (len(observation_bars) - 1) - int(position["entry_index"]))

    stage_index = {
        "waiting": 0,
        "entry_pending": 1,
        "entered": 2,
        "holding": 2,
        "partial_exit_pending": 3,
        "partially_exited": 3,
        "full_exit_pending": 4,
        "exited": 4,
    }[state]
    latest_transition = None
    if last_event:
        latest_transition = {
            "label": last_event.get("label"),
            "transition_date": last_event.get("execution_date"),
            "price": last_event.get("price"),
        }

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
                "stages": ["관망", "진입", "보유", "분할매도", "청산"],
                "latest_transition": latest_transition,
            },
            "entry_date": position["entry_date"] if position else None,
            "entry_price": _price(entry_price),
            "partial_exit_date": position.get("partial_exit_date") if position else None,
            "partial_exit_price": _price(position.get("partial_exit_price")) if position else None,
            "holding_days": holding_days,
            "unrealized_return": _decimal(unrealized_return * 100.0) if unrealized_return is not None else None,
            "stop_reference": _price(stop_reference),
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
) -> dict[str, Any]:
    current_time = now or datetime.now(KST)
    bars = _normalize_prices(rows)
    confirmed = _confirmed_bars(bars, current_time)
    current_context = context or {
        "state": "limited",
        "label": "확인 근거 부족",
        "score": None,
        "available_count": 0,
        "total_count": 0,
        "note": "가격·거래량 외 보조 데이터가 없습니다.",
        "evidence": [],
    }
    base = {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        "as_of": current_time,
        "strategy_name": STRATEGY_NAME,
        "strategy_version": STRATEGY_VERSION,
        "source": (
            "저장 일봉 + KIS 실시간 현재가 + 수급·뉴스·리포트·공시"
            if live_quote
            else "저장 일봉 + 수급·뉴스·리포트·공시"
        )
        if context is not None
        else ("저장 일봉 + KIS 실시간 현재가" if live_quote else "저장 일봉"),
        "data_rows": len(confirmed),
        "price_through": confirmed[-1].trade_date if confirmed else None,
        "confirmation": current_context,
        "methodology": [
            "EMA 10·20·60일, 20일 모멘텀·고점, 거래량, ATR14를 동일 규칙으로 계산합니다.",
            "전략은 모델 보유비중을 0%→100%→50%→0%로 바꾸는 유한 상태 머신입니다.",
            "신호는 종가에서 판정하고 다음 거래일 시가에 반영하여 미래 가격을 참조하지 않습니다.",
            "1차 분할매도는 초기 위험의 2배 수익 또는 수익 후 탄력 둥화에서, 청산은 ATR·EMA·종합 점수 이탈에서 판정합니다.",
            "거래대금과 변동성에 따라 양방향 체결비용을 0.125%~0.50%로 차등 반영합니다.",
            "수급·뉴스·리포트·공시는 현재 판단의 확인 근거로만 쓰고 과거 백테스트에 소급 적용하지 않습니다.",
        ],
        "applied_principles": [
            "실시간·백테스트에서 같은 신호 함수 사용",
            "슬라이딩 윈도우와 상태 순차 갱신",
            "목표 보유비중과 현재 비중의 차이로 상태 전환",
            "변동성 위험선·분할매도·추적 청산",
            "유동성·변동성을 반영한 체결비용",
            "미래 참조 방지와 모든 종목 동일 규칙",
            "버전이 고정된 소수 매개변수로 결과 재현",
            "수익률뿐 아니라 최대 낙폭과 표본 수를 함께 검증",
        ],
        "excluded_principles": [
            "호가잔량 마이크로프라이스는 실시간 호가 이력이 없어 미적용",
            "VWAP·TWAP 주문 분할은 실제 주문 수량·체결 이력이 없어 미적용",
            "Kelly·공분산 포트폴리오 배분은 계좌·전체 보유종목 맥락이 필요해 종목 단일 화면에서 미적용",
            "대체데이터·머신러닝 신호는 시점별 학습 데이터가 검증되지 않아 미적용",
            "시장 전체 백테스트의 생존편향 검증은 상장폐지 종목 이력이 완비되지 않아 미적용",
        ],
        "disclaimer": "교육·연구용 전략 상태이며 실제 계좌 체결이나 수익을 보장하지 않습니다.",
    }
    if len(confirmed) < MIN_HISTORY_ROWS:
        return {
            **base,
            "data_state": "insufficient",
            "data_message": f"신호 계산에는 최소 {MIN_HISTORY_ROWS}거래일이 필요합니다. 현재 {len(confirmed)}거래일입니다.",
            "current": None,
            "performance": None,
            "factors": [],
            "events": [],
            "trades": [],
        }

    indicators = _indicator_rows(confirmed)
    simulation = _simulate(confirmed, indicators)
    current, factors = _current_signal(confirmed, simulation, live_quote, current_time)
    return {
        **base,
        "data_state": "ready",
        "data_message": f"{len(confirmed)}거래일로 계산했습니다.",
        "current": current,
        "performance": simulation["performance"],
        "factors": factors,
        "events": simulation["events"],
        "trades": list(reversed(simulation["trades"][-12:])),
    }


def load_quant_signal_payload(
    db: Session,
    code: str,
    *,
    live_quote: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
    limit: int = 900,
    include_context: bool = True,
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
    context = (
        _load_current_context(
            db,
            stock,
            rows,
            live_quote=live_quote,
            now=current_time,
        )
        if include_context
        else None
    )
    return build_quant_signal_payload(
        stock,
        rows,
        live_quote=live_quote,
        now=current_time,
        context=context,
    )
