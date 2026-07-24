from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPrice, StockMaster


KST = ZoneInfo("Asia/Seoul")
STRATEGY_VERSION = "quant-trend-v1.0"
STRATEGY_NAME = "추세·모멘텀 공통 전략"
MIN_HISTORY_ROWS = 125
WARMUP_ROWS = 65
BACKTEST_ROWS = 252
ENTRY_SCORE = 65.0
EXIT_SCORE = 42.0
TRANSACTION_COST_PER_SIDE = 0.002
HYPOTHETICAL_CAPITAL = 10_000_000


@dataclass(frozen=True)
class PriceBar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


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


def _exit_signal(
    bar: PriceBar,
    indicator: dict[str, float],
    *,
    entry_price: float,
    peak_price: float,
) -> tuple[bool, str, float]:
    trailing_stop = max(entry_price - (indicator["atr"] * 2.0), peak_price - (indicator["atr"] * 2.6))
    if bar.close <= trailing_stop:
        return True, "변동성 기준 이탈", trailing_stop
    if indicator["score"] <= EXIT_SCORE:
        return True, "종합 점수 약화", trailing_stop
    if bar.close < indicator["ema20"] and indicator["ema10"] < indicator["ema20"]:
        return True, "단기 추세 이탈", trailing_stop
    return False, "추세 유지", trailing_stop


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
    equity = 1.0
    shares = 0.0
    equity_curve: list[float] = []
    peak_equity = 1.0
    max_drawdown = 0.0

    for index in range(start_index, len(bars)):
        bar = bars[index]
        indicator = indicators[index]

        if pending:
            execution_price = bar.open or bar.close
            if pending["side"] == "buy":
                shares = equity / (execution_price * (1.0 + TRANSACTION_COST_PER_SIDE))
                position = {
                    "entry_date": bar.trade_date,
                    "entry_price": execution_price,
                    "entry_index": index,
                    "signal_date": pending["signal_date"],
                    "score": pending["score"],
                    "peak_price": execution_price,
                }
                events.append(
                    {
                        "signal_date": pending["signal_date"],
                        "execution_date": bar.trade_date,
                        "side": "buy",
                        "label": "모의 매수",
                        "price": _price(execution_price),
                        "score": _decimal(pending["score"]),
                        "reason": pending["reason"],
                    }
                )
            elif position:
                equity = shares * execution_price * (1.0 - TRANSACTION_COST_PER_SIDE)
                net_return = (
                    (execution_price * (1.0 - TRANSACTION_COST_PER_SIDE))
                    / (position["entry_price"] * (1.0 + TRANSACTION_COST_PER_SIDE))
                ) - 1.0
                gross_return = (execution_price / position["entry_price"]) - 1.0
                holding_days = max(1, index - int(position["entry_index"]))
                trade = {
                    "entry_date": position["entry_date"],
                    "entry_price": _price(position["entry_price"]),
                    "exit_date": bar.trade_date,
                    "exit_price": _price(execution_price),
                    "gross_return": _decimal(gross_return * 100.0),
                    "net_return": _decimal(net_return * 100.0),
                    "holding_days": holding_days,
                    "status": "closed",
                    "exit_reason": pending["reason"],
                }
                trades.append(trade)
                events.append(
                    {
                        "signal_date": pending["signal_date"],
                        "execution_date": bar.trade_date,
                        "side": "sell",
                        "label": "모의 매도",
                        "price": _price(execution_price),
                        "score": _decimal(pending["score"]),
                        "reason": pending["reason"],
                        "return_rate": trade["net_return"],
                        "holding_days": holding_days,
                    }
                )
                shares = 0.0
                position = None
            pending = None

        if position:
            position["peak_price"] = max(position["peak_price"], bar.close)
            marked_equity = shares * bar.close * (1.0 - TRANSACTION_COST_PER_SIDE)
        else:
            marked_equity = equity
        equity_curve.append(marked_equity)
        peak_equity = max(peak_equity, marked_equity)
        max_drawdown = min(max_drawdown, (marked_equity / peak_equity) - 1.0)

        if index >= len(bars) - 1:
            continue
        if position:
            should_exit, reason, _ = _exit_signal(
                bar,
                indicator,
                entry_price=position["entry_price"],
                peak_price=position["peak_price"],
            )
            if should_exit:
                pending = {
                    "side": "sell",
                    "signal_date": bar.trade_date,
                    "score": indicator["score"],
                    "reason": reason,
                }
        elif _entry_signal(bar, indicator):
            pending = {
                "side": "buy",
                "signal_date": bar.trade_date,
                "score": indicator["score"],
                "reason": _signal_reason(indicator, "buy"),
            }

    final_equity = equity_curve[-1] if equity_curve else 1.0
    closed_trades = [trade for trade in trades if trade["status"] == "closed"]
    winners = [trade for trade in closed_trades if float(trade["net_return"] or 0) > 0]
    net_returns = [float(trade["net_return"] or 0) for trade in closed_trades]
    holding_days = [int(trade["holding_days"] or 0) for trade in closed_trades]
    benchmark = (bars[-1].close / bars[start_index].close) - 1.0 if len(bars) > start_index else 0.0

    if position:
        current_return = (
            (bars[-1].close * (1.0 - TRANSACTION_COST_PER_SIDE))
            / (position["entry_price"] * (1.0 + TRANSACTION_COST_PER_SIDE))
        ) - 1.0
        trades.append(
            {
                "entry_date": position["entry_date"],
                "entry_price": _price(position["entry_price"]),
                "exit_date": None,
                "exit_price": None,
                "gross_return": _decimal(((bars[-1].close / position["entry_price"]) - 1.0) * 100.0),
                "net_return": _decimal(current_return * 100.0),
                "holding_days": max(1, (len(bars) - 1) - int(position["entry_index"])),
                "status": "open",
                "exit_reason": None,
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
            "transaction_cost_per_side": _decimal(TRANSACTION_COST_PER_SIDE * 100.0),
            "hypothetical_start": HYPOTHETICAL_CAPITAL,
            "hypothetical_end": _price(HYPOTHETICAL_CAPITAL * final_equity),
            "sample_state": sample_state,
            "sample_note": (
                f"완료 거래 {completed}회로 성과 표본이 제한적입니다."
                if sample_state == "limited"
                else f"완료 거래 {completed}회의 동일 규칙 모의검증 결과입니다."
            ),
        },
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
            )
        )
    else:
        return confirmed, False
    return bars, True


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

    action = "wait"
    label = "관망"
    next_confirmation = "종가 기준 신호를 다음 거래일에 다시 확인"
    reasons: list[str] = []
    stop_reference: Optional[float] = None
    if position:
        peak_price = max(float(position["peak_price"]), bar.close)
        should_exit, exit_reason, stop_reference = _exit_signal(
            bar,
            indicator,
            entry_price=float(position["entry_price"]),
            peak_price=peak_price,
        )
        if should_exit:
            action = "sell_watch"
            label = "축소 관찰"
            reasons.append(exit_reason)
            next_confirmation = "종가 신호 확정 후 다음 거래일 시가에 모의 매도"
        else:
            action = "hold"
            label = "보유 유지"
            reasons.append("상승 추세가 아직 유지됨")
            next_confirmation = "20일선과 변동성 이탈 여부를 매일 확인"
    elif _entry_signal(bar, indicator):
        action = "buy_watch"
        label = "매수 관찰"
        reasons.append(_signal_reason(indicator, "buy"))
        next_confirmation = "종가 신호 확정 후 다음 거래일 시가에 모의 매수"
    else:
        reasons.append("진입 기준 65점과 상승 추세 조건을 모두 충족하지 않음")

    reasons.append(f"종합 신호 {indicator['score']:.1f}점")
    current_price = _safe_number(live_quote.get("price")) if live_quote else None
    current_price = current_price or bar.close
    entry_price = float(position["entry_price"]) if position else None
    unrealized_return = None
    holding_days = None
    if position and entry_price:
        unrealized_return = (
            (current_price * (1.0 - TRANSACTION_COST_PER_SIDE))
            / (entry_price * (1.0 + TRANSACTION_COST_PER_SIDE))
        ) - 1.0
        holding_days = max(1, (len(observation_bars) - 1) - int(position["entry_index"]))

    return (
        {
            "action": action,
            "label": label,
            "score": _decimal(indicator["score"]),
            "price": _price(current_price),
            "as_of": now,
            "live_observation": live_observation,
            "position_open": bool(position),
            "entry_date": position["entry_date"] if position else None,
            "entry_price": _price(entry_price),
            "holding_days": holding_days,
            "unrealized_return": _decimal(unrealized_return * 100.0) if unrealized_return is not None else None,
            "stop_reference": _price(stop_reference),
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
) -> dict[str, Any]:
    current_time = now or datetime.now(KST)
    bars = _normalize_prices(rows)
    confirmed = _confirmed_bars(bars, current_time)
    base = {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        "as_of": current_time,
        "strategy_name": STRATEGY_NAME,
        "strategy_version": STRATEGY_VERSION,
        "source": "저장 일봉 + KIS 실시간 현재가" if live_quote else "저장 일봉",
        "data_rows": len(confirmed),
        "price_through": confirmed[-1].trade_date if confirmed else None,
        "methodology": [
            "EMA 10·20·60일, 20일 모멘텀·고점, 거래량, ATR14를 같은 비중 규칙으로 계산합니다.",
            "당일 종가에서 만든 신호는 다음 거래일 시가에 체결된 것으로만 모의검증합니다.",
            "모든 종목에 동일한 기준을 적용하며 종목별 최적화와 미래 데이터 사용을 하지 않습니다.",
            "매수·매도마다 0.20% 비용을 가정하고 최근 252거래일을 비교합니다.",
        ],
        "disclaimer": "교육·연구용 모의 신호이며 실제 주문이나 수익을 보장하지 않습니다.",
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
    return build_quant_signal_payload(stock, rows, live_quote=live_quote, now=now)
