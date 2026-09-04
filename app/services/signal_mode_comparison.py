"""Compare the audited daily-open policy with a hybrid intraday exit policy.

The application still runs the audited daily policy by default.  This module is
an analysis-only replay: it keeps daily close-based entries and trend exits, but
uses daily OHLC as a conservative proxy for intraday hard-stop and profit-target
execution.  It is deliberately not used by the production signal endpoints
until real intraday history is available.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any

from app.services import quant_signals as qs


@dataclass(frozen=True)
class IntradayExitDecision:
    """One conservative OHLC-proxy action taken during a trading session."""

    side: str
    price: float
    reason: str
    target_stage: int | None = None
    sell_fraction: float | None = None


def _sell_price(bar: qs.PriceBar, trigger: float, *, protective: bool) -> float:
    """Use the open only when the session gaps through the relevant trigger."""

    if protective:
        return float(bar.open) if float(bar.open) <= trigger else float(trigger)
    return float(bar.open) if float(bar.open) >= trigger else float(trigger)


def intraday_exit_decision(
    position: dict[str, Any],
    bar: qs.PriceBar,
    indicator: dict[str, float],
) -> IntradayExitDecision | None:
    """Return the first hybrid sell action for one daily OHLC proxy bar.

    The proxy is intentionally conservative: if both the low and a profit
    target are touched on the same daily candle, the adverse hard floor wins.
    This avoids inventing an optimistic intraday price path from OHLC alone.
    """

    prior_peak = float(position.get("peak_price") or position["entry_price"])
    levels = qs._position_levels(
        position,
        indicator,
        prior_peak,
        strategy_date=bar.trade_date,
    )
    hard_floor = float(levels["hard_floor"])
    if float(bar.low) <= hard_floor:
        return IntradayExitDecision(
            side="sell",
            price=_sell_price(bar, hard_floor, protective=True),
            reason="장중 하드 리스크선 이탈(OHLC 보수적 프록시)",
        )

    steps = qs._resolved_profit_ladder_steps(position, bar.trade_date)
    current_stage = max(0, int(position.get("profit_stage") or 0))
    current_remaining = float(position.get("remaining_fraction") or 0.0)
    runner = qs._minimum_runner_fraction(bar.trade_date)
    for stage in range(current_stage + 1, len(steps) + 1):
        trigger_r, _configured_fraction, _locked_r, _trailing_atr = steps[stage - 1]
        target = float(position["entry_price"]) + float(position["initial_risk"]) * trigger_r
        if float(bar.high) + 1e-9 < target:
            break
        intended_remaining = max(
            runner,
            1.0 - sum(step[1] for step in steps[:stage]),
        )
        sell_fraction = max(0.0, current_remaining - intended_remaining)
        if sell_fraction <= 1e-9:
            continue
        if sell_fraction >= current_remaining - 1e-9:
            return IntradayExitDecision(
                side="sell",
                price=_sell_price(bar, target, protective=False),
                reason=f"장중 {stage}차 수익확정·잔여분 전량 매도(OHLC 보수적 프록시)",
                target_stage=stage,
                sell_fraction=current_remaining,
            )
        return IntradayExitDecision(
            side="partial_sell",
            price=_sell_price(bar, target, protective=False),
            reason=f"장중 {stage}차 수익확정(OHLC 보수적 프록시)",
            target_stage=stage,
            sell_fraction=sell_fraction,
        )
    return None


def _new_position(
    bar: qs.PriceBar,
    pending: dict[str, Any],
    cash: float,
    *,
    entry_price: float | None = None,
) -> tuple[dict[str, Any], float, float]:
    cost = float(pending["execution_cost"])
    executed_entry_price = float(entry_price if entry_price is not None else bar.open)
    shares = cash / (executed_entry_price * (1.0 + cost))
    initial_risk = qs._initial_risk(
        executed_entry_price,
        float(pending["atr"]),
        strategy_date=bar.trade_date,
    )
    position = {
        "entry_date": bar.trade_date,
        "entry_price": executed_entry_price,
        "entry_index": pending["entry_index"],
        "signal_date": pending["signal_date"],
        "entry_cost": cost,
        "initial_risk": initial_risk,
        "initial_shares": shares,
        "entry_equity": cash,
        "realized_proceeds": 0.0,
        "gross_realized_value": 0.0,
        "peak_price": executed_entry_price,
        "initial_stop": max(1.0, executed_entry_price - initial_risk),
        "profit_stage": 0,
        "remaining_fraction": 1.0,
        "partial_exit_date": None,
        "partial_exit_price": None,
        "partial_exits": [],
        "exit_confirmation_count": 0,
        "exit_confirmation_reason": None,
    }
    steps = qs._resolved_profit_ladder_steps(position, bar.trade_date)
    position["target_sell_price"] = executed_entry_price + initial_risk * steps[0][0]
    return position, 0.0, shares


def _apply_partial(
    position: dict[str, Any],
    bar: qs.PriceBar,
    indicator: dict[str, float],
    decision: IntradayExitDecision,
    shares: float,
    cash: float,
) -> tuple[dict[str, Any], float, float]:
    stage = int(decision.target_stage or (int(position.get("profit_stage") or 0) + 1))
    fraction = min(
        shares / float(position["initial_shares"]),
        float(decision.sell_fraction or 0.0),
    )
    sold_shares = float(position["initial_shares"]) * fraction
    sold_shares = min(shares, sold_shares)
    cost = qs._execution_cost(indicator)
    proceeds = sold_shares * float(decision.price) * (1.0 - cost)
    cash += proceeds
    shares -= sold_shares
    position["realized_proceeds"] += proceeds
    position["gross_realized_value"] += sold_shares * float(decision.price)
    position["profit_stage"] = stage
    position["remaining_fraction"] = shares / float(position["initial_shares"])
    position["partial_exit_date"] = bar.trade_date
    position["partial_exit_price"] = float(decision.price)
    position["partial_exits"].append(
        {
            "stage": stage,
            "execution_date": bar.trade_date,
            "price": round(float(decision.price)),
            "sold_percent": round(fraction * 100.0, 2),
            "remaining_percent": round(position["remaining_fraction"] * 100.0, 2),
        }
    )
    return position, cash, shares


def _close_position(
    position: dict[str, Any],
    bar: qs.PriceBar,
    indicator: dict[str, float],
    price: float,
    reason: str,
    shares: float,
    cash: float,
    index: int,
) -> tuple[dict[str, Any], float, float]:
    cost = qs._execution_cost(indicator)
    gross_value = shares * price
    proceeds = gross_value * (1.0 - cost)
    cash += proceeds
    position["realized_proceeds"] += proceeds
    position["gross_realized_value"] += gross_value
    net_return = float(position["realized_proceeds"]) / float(position["entry_equity"]) - 1.0
    gross_return = (
        float(position["gross_realized_value"])
        / (float(position["initial_shares"]) * float(position["entry_price"]))
        - 1.0
    )
    position["closed_trade"] = {
        "entry_date": position["entry_date"],
        "entry_price": round(float(position["entry_price"])),
        "exit_date": bar.trade_date,
        "exit_price": round(price),
        "gross_return": round(gross_return * 100.0, 2),
        "net_return": round(net_return * 100.0, 2),
        "holding_days": max(1, index - int(position["entry_index"])),
        "exit_reason": reason,
        "partial_exits": deepcopy(position.get("partial_exits") or []),
        "status": "closed",
    }
    return position, cash, 0.0


def _schedule_close_action(
    bar: qs.PriceBar,
    indicator: dict[str, float],
    position: dict[str, Any],
    index: int,
) -> dict[str, Any] | None:
    should_exit, reason, levels, is_hard_exit = qs._full_exit_signal(
        bar,
        indicator,
        position,
        float(position["peak_price"]),
    )
    holding_bars = max(0, index - int(position["entry_index"]))
    eligible = holding_bars >= qs._minimum_holding_bars(bar.trade_date)
    confirmation_bars = qs._exit_confirmation_bars(bar.trade_date)
    if should_exit and not is_hard_exit and eligible:
        prior_reason = position.get("exit_confirmation_reason")
        position["exit_confirmation_count"] = (
            int(position.get("exit_confirmation_count") or 0) + 1
            if prior_reason == reason
            else 1
        )
        position["exit_confirmation_reason"] = reason
    elif not should_exit or not eligible:
        position["exit_confirmation_count"] = 0
        position["exit_confirmation_reason"] = None
    exit_confirmed = bool(
        should_exit
        and (
            is_hard_exit
            or (
                eligible
                and int(position.get("exit_confirmation_count") or 0) >= confirmation_bars
            )
        )
    )
    if exit_confirmed:
        return {
            "side": "sell",
            "signal_date": bar.trade_date,
            "reason": reason if is_hard_exit else f"{reason} 종가 {confirmation_bars}일 연속 확인",
            "target_sell_price": levels.get("trailing_stop"),
            "execution_cost": qs._execution_cost(indicator),
        }
    return None


def _simulate_ohlc_proxy(
    bars: list[qs.PriceBar],
    indicators: list[dict[str, float]],
    *,
    performance_start_index_override: int | None = None,
    entry_mode: str,
    mode: str,
    entry_filter_version: str | None = None,
) -> dict[str, Any]:
    """Replay one entry policy with conservative intraday OHLC-proxy exits."""

    if entry_mode not in {"next_open", "same_close"}:
        raise ValueError(f"unsupported entry mode: {entry_mode}")

    if not bars or len(bars) != len(indicators):
        raise ValueError("bars and indicators must be non-empty and aligned")
    start_index = (
        max(qs.WARMUP_ROWS, min(int(performance_start_index_override), len(bars) - 1))
        if performance_start_index_override is not None
        else max(qs.WARMUP_ROWS, len(bars) - qs.BACKTEST_ROWS)
    )
    pending: dict[str, Any] | None = None
    position: dict[str, Any] | None = None
    cash = 1.0
    shares = 0.0
    last_exit_index: int | None = None
    closed_trades: list[dict[str, Any]] = []
    equity_curve: list[float] = []
    dates: list[date] = []
    turnover = 0.0
    performance_base_equity = 1.0

    for index in range(qs.WARMUP_ROWS, len(bars)):
        bar = bars[index]
        indicator = indicators[index]
        if index == start_index:
            if index > qs.WARMUP_ROWS and position is not None:
                previous_bar = bars[index - 1]
                previous_indicator = indicators[index - 1]
                performance_base_equity = cash + (
                    shares
                    * float(previous_bar.close)
                    * (1.0 - qs._execution_cost(previous_indicator))
                )
            else:
                performance_base_equity = cash

        if pending:
            action = pending
            pending = None
            if action["side"] == "buy" and position is None and qs._entry_execution_allowed(
                bar.open, action
            ):
                position, cash, shares = _new_position(bar, {**action, "entry_index": index}, cash)
                turnover += 1.0 if index >= start_index else 0.0
            elif action["side"] == "partial_sell" and position is not None:
                decision = IntradayExitDecision(
                    side="partial_sell",
                    price=float(bar.open),
                    reason=str(action["reason"]),
                    target_stage=action.get("target_stage"),
                    sell_fraction=action.get("sell_fraction"),
                )
                before_shares = shares
                position, cash, shares = _apply_partial(position, bar, indicator, decision, shares, cash)
                if index >= start_index and before_shares > 0:
                    turnover += (before_shares - shares) / float(position["initial_shares"])
            elif action["side"] == "sell" and position is not None:
                sold_fraction = shares / float(position["initial_shares"])
                position, cash, shares = _close_position(
                    position,
                    bar,
                    indicator,
                    float(bar.open),
                    str(action["reason"]),
                    shares,
                    cash,
                    index,
                )
                closed_trades.append(position.pop("closed_trade"))
                position = None
                last_exit_index = index
                if index >= start_index:
                    turnover += sold_fraction

        if position is not None:
            decision = intraday_exit_decision(position, bar, indicator)
            if decision is not None:
                if decision.side == "partial_sell" and decision.sell_fraction is not None:
                    before_shares = shares
                    position, cash, shares = _apply_partial(
                        position, bar, indicator, decision, shares, cash
                    )
                    if index >= start_index and before_shares > 0:
                        turnover += (before_shares - shares) / float(position["initial_shares"])
                else:
                    sold_fraction = shares / float(position["initial_shares"])
                    position, cash, shares = _close_position(
                        position,
                        bar,
                        indicator,
                        decision.price,
                        decision.reason,
                        shares,
                        cash,
                        index,
                    )
                    closed_trades.append(position.pop("closed_trade"))
                    position = None
                    last_exit_index = index
                    if index >= start_index:
                        turnover += sold_fraction

        if position is not None:
            position["peak_price"] = max(float(position["peak_price"]), float(bar.high))
            pending_close = _schedule_close_action(bar, indicator, position, index)
            if pending_close is not None:
                pending = pending_close
        elif index < len(bars) - 1 and (
            last_exit_index is None or index - last_exit_index > qs.REENTRY_COOLDOWN_BARS
        ) and (
            qs._entry_signal(bar, indicator)
            if entry_filter_version is None
            else qs._entry_signal(
                bar,
                indicator,
                entry_filter_version=entry_filter_version,
            )
        ):
            setup = (
                qs._entry_setup_kind(bar, indicator)
                if entry_filter_version is None
                else qs._entry_setup_kind(
                    bar,
                    indicator,
                    entry_filter_version=entry_filter_version,
                )
            ) or "trend_continuation"
            entry_action = {
                "side": "buy",
                "signal_date": bar.trade_date,
                "score": indicator["score"],
                "reason": qs._signal_reason({**indicator, "entry_setup": setup}, "buy"),
                "atr": indicator["atr"],
                "signal_price": bar.close,
                "execution_cost": qs._execution_cost(indicator),
            }
            if entry_mode == "same_close":
                position, cash, shares = _new_position(
                    bar,
                    {**entry_action, "entry_index": index},
                    cash,
                    entry_price=bar.close,
                )
                if index >= start_index:
                    turnover += 1.0
            else:
                pending = entry_action

        marked_equity = cash
        if position is not None:
            marked_equity += shares * float(bar.close) * (1.0 - qs._execution_cost(indicator))
        if index >= start_index:
            equity_curve.append(marked_equity)
            dates.append(bar.trade_date)

    if position is not None:
        marked = shares * float(bars[-1].close) * (1.0 - qs._execution_cost(indicators[-1]))
        current_return = (float(position["realized_proceeds"]) + marked) / float(position["entry_equity"]) - 1.0
    else:
        current_return = None
    base = performance_base_equity
    final_equity = equity_curve[-1] if equity_curve else base
    peak = base
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    period_start = bars[start_index].trade_date
    period_trades = [
        trade
        for trade in closed_trades
        if trade.get("exit_date") is not None and trade["exit_date"] >= period_start
    ]
    returns = [float(item["net_return"]) for item in period_trades]
    return {
        "mode": mode,
        "period_start": dates[0] if dates else bars[start_index].trade_date,
        "period_end": dates[-1] if dates else bars[-1].trade_date,
        "strategy_return": round((final_equity / base - 1.0) * 100.0, 2),
        "max_drawdown": round(max_drawdown * 100.0, 2),
        "completed_trades": len(period_trades),
        "win_rate": round(sum(value > 0 for value in returns) / len(returns) * 100.0, 2)
        if returns
        else None,
        "average_return": round(sum(returns) / len(returns), 2) if returns else None,
        "turnover_percent": round(turnover * 100.0, 2),
        "open_position_return": round(current_return * 100.0, 2)
        if current_return is not None
        else None,
        "trades": period_trades,
    }


def simulate_hybrid_ohlc_proxy(
    bars: list[qs.PriceBar],
    indicators: list[dict[str, float]],
    *,
    performance_start_index_override: int | None = None,
    entry_filter_version: str | None = None,
) -> dict[str, Any]:
    """Replay next-open entries with conservative intraday exits."""

    return _simulate_ohlc_proxy(
        bars,
        indicators,
        performance_start_index_override=performance_start_index_override,
        entry_mode="next_open",
        mode="hybrid_sell_intraday_ohlc_proxy",
        entry_filter_version=entry_filter_version,
    )


def simulate_full_intraday_ohlc_proxy(
    bars: list[qs.PriceBar],
    indicators: list[dict[str, float]],
    *,
    performance_start_index_override: int | None = None,
    entry_filter_version: str | None = None,
) -> dict[str, Any]:
    """Replay same-close entries with conservative intraday exits.

    Daily OHLC cannot identify the minute at which a signal became true.  The
    same-close entry is therefore the safest available proxy for an intraday
    buy; it must not be presented as a true minute-level backtest.
    """

    return _simulate_ohlc_proxy(
        bars,
        indicators,
        performance_start_index_override=performance_start_index_override,
        entry_mode="same_close",
        mode="full_intraday_ohlc_proxy",
        entry_filter_version=entry_filter_version,
    )


def compare_entry_filter_backtest(
    bars: list[qs.PriceBar],
    indicators: list[dict[str, float]],
    *,
    performance_start_index_override: int | None = None,
) -> dict[str, Any]:
    """Replay H1/H2/H3 as a backend shadow comparison under hybrid exits."""

    versions = (
        qs.ENTRY_FILTER_BASELINE_VERSION,
        qs.ENTRY_FILTER_H1_VERSION,
        qs.ENTRY_FILTER_H2_VERSION,
        qs.ENTRY_FILTER_H3_VERSION,
    )
    results: dict[str, dict[str, Any]] = {}
    for version in versions:
        result = simulate_hybrid_ohlc_proxy(
            bars,
            indicators,
            performance_start_index_override=performance_start_index_override,
            entry_filter_version=version,
        )
        results[version] = result
    baseline = results[qs.ENTRY_FILTER_BASELINE_VERSION]

    def delta(result: dict[str, Any]) -> dict[str, float | None]:
        keys = (
            "strategy_return",
            "max_drawdown",
            "win_rate",
            "average_return",
            "turnover_percent",
        )
        return {
            key: round(float(result[key]) - float(baseline[key]), 2)
            if result.get(key) is not None and baseline.get(key) is not None
            else None
            for key in keys
        }

    return {
        "execution_model": "hybrid_sell_intraday_ohlc_proxy",
        "data_warning": "일봉 OHLC 기반 보수적 장중 매도 프록시이며 실제 분봉 체결이 아닙니다.",
        "active_version": qs.ENTRY_FILTER_VERSION,
        "shadow_versions": list(qs.ENTRY_FILTER_SHADOW_VERSIONS),
        "results": {
            version: {
                key: value
                for key, value in result.items()
                if key != "trades"
            }
            | {"delta_vs_baseline": delta(result)}
            for version, result in results.items()
        },
    }


def aggregate_mode_comparison(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-symbol daily, hybrid, and optional full-intraday results."""

    valid = [row for row in rows if row.get("daily") and row.get("hybrid")]
    daily = [row["daily"] for row in valid]
    hybrid = [row["hybrid"] for row in valid]

    def aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
        returns = [trade["net_return"] for item in items for trade in item.get("trades", [])]
        symbol_returns = [item["strategy_return"] for item in items]
        drawdowns = [item["max_drawdown"] for item in items]
        completed = sum(int(item.get("completed_trades") or 0) for item in items)
        return {
            "symbols": len(items),
            "average_symbol_return": round(sum(symbol_returns) / len(symbol_returns), 2)
            if symbol_returns
            else None,
            "median_symbol_return": round(float(median(symbol_returns)), 2)
            if symbol_returns
            else None,
            "average_max_drawdown": round(sum(drawdowns) / len(drawdowns), 2)
            if drawdowns
            else None,
            "worst_symbol_drawdown": round(min(drawdowns), 2) if drawdowns else None,
            "completed_trades": completed,
            "win_rate": round(sum(value > 0 for value in returns) / len(returns) * 100.0, 2)
            if returns
            else None,
            "average_trade_return": round(sum(returns) / len(returns), 2) if returns else None,
            "turnover_percent_sum": round(sum(float(item.get("turnover_percent") or 0) for item in items), 2),
        }

    daily_summary = aggregate(daily)
    hybrid_summary = aggregate(hybrid)
    summaries: dict[str, Any] = {
        "daily_open": daily_summary,
        "hybrid_intraday_sell": hybrid_summary,
    }
    full_valid = [row for row in valid if row.get("full_intraday")]
    if full_valid:
        summaries["full_intraday_buy_sell"] = aggregate(
            [row["full_intraday"] for row in full_valid]
        )

    def delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float | None]:
        return {
            key: round(float(left[key]) - float(right[key]), 2)
            if left.get(key) is not None and right.get(key) is not None
            else None
            for key in (
                "average_symbol_return",
                "median_symbol_return",
                "average_max_drawdown",
                "worst_symbol_drawdown",
                "win_rate",
                "average_trade_return",
                "turnover_percent_sum",
            )
        }

    comparison: dict[str, Any] = {
        "comparison_scope": "same strategy rules and costs; only entry timing and hard-stop/profit-target timing differ",
        "data_warning": "OHLC cannot reconstruct the true intraday path. Same-candle low and target touches assume the adverse stop first.",
        **summaries,
        "delta_hybrid_minus_daily": delta(hybrid_summary, daily_summary),
        "symbols": valid,
    }
    if full_valid:
        full_summary = summaries["full_intraday_buy_sell"]
        comparison["delta_full_minus_hybrid"] = delta(full_summary, hybrid_summary)
        comparison["delta_full_minus_daily"] = delta(full_summary, daily_summary)
    return comparison
