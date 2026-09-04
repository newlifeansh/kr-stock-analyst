"""Backtest independently versioned entry filters as a backend shadow report.

H1 is the active candidate for the current signal path. H2 and H3 are replayed
with identical prices, exits, costs, and hybrid OHLC-proxy execution so their
performance can be compared without changing user-facing notifications.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select

from app.db import SessionLocal
from app.models import DailyPrice, StockMaster
from app.services import quant_signals as qs
from app.services.signal_mode_comparison import simulate_hybrid_ohlc_proxy


FILTER_VERSIONS = (
    qs.ENTRY_FILTER_BASELINE_VERSION,
    qs.ENTRY_FILTER_H1_VERSION,
    qs.ENTRY_FILTER_H2_VERSION,
    qs.ENTRY_FILTER_H3_VERSION,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-limit", type=int, default=100)
    parser.add_argument("--history-rows", type=int, default=400)
    parser.add_argument("--recent-trading-days", type=int, default=22)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/qa-data-signal/entry-filter-shadow-comparison.json"),
    )
    return parser


def _metric_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: result.get(key)
        for key in (
            "mode",
            "period_start",
            "period_end",
            "strategy_return",
            "max_drawdown",
            "completed_trades",
            "win_rate",
            "average_return",
            "turnover_percent",
            "open_position_return",
        )
    }


def _aggregate(results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for version, items in results.items():
        returns = [
            float(trade["net_return"])
            for item in items
            for trade in item.get("trades", [])
        ]
        symbol_returns = [float(item["strategy_return"]) for item in items]
        drawdowns = [float(item["max_drawdown"]) for item in items]
        summaries[version] = {
            "symbols": len(items),
            "average_symbol_return": round(sum(symbol_returns) / len(symbol_returns), 2)
            if symbol_returns
            else None,
            "average_max_drawdown": round(sum(drawdowns) / len(drawdowns), 2)
            if drawdowns
            else None,
            "completed_trades": sum(int(item.get("completed_trades") or 0) for item in items),
            "win_rate": round(sum(value > 0 for value in returns) / len(returns) * 100.0, 2)
            if returns
            else None,
            "average_trade_return": round(sum(returns) / len(returns), 2)
            if returns
            else None,
            "turnover_percent_sum": round(
                sum(float(item.get("turnover_percent") or 0) for item in items),
                2,
            ),
        }
    baseline = summaries[qs.ENTRY_FILTER_BASELINE_VERSION]
    for version, summary in summaries.items():
        summary["delta_vs_baseline"] = {
            key: round(float(summary[key]) - float(baseline[key]), 2)
            if summary.get(key) is not None and baseline.get(key) is not None
            else None
            for key in (
                "average_symbol_return",
                "average_max_drawdown",
                "win_rate",
                "average_trade_return",
                "turnover_percent_sum",
            )
        }
    return summaries


def build_report(
    *,
    universe_limit: int,
    history_rows: int,
    recent_trading_days: int,
) -> dict[str, Any]:
    if universe_limit <= 0:
        raise ValueError("universe-limit must be positive")
    if history_rows < qs.MIN_BACKTEST_HISTORY_ROWS:
        raise ValueError(f"history-rows must be at least {qs.MIN_BACKTEST_HISTORY_ROWS}")
    if recent_trading_days <= 0:
        raise ValueError("recent-trading-days must be positive")

    with SessionLocal() as db:
        latest_price_date = db.scalar(
            select(func.max(DailyPrice.trade_date)).where(DailyPrice.close.is_not(None))
        )
        latest_market_cap_date = db.scalar(
            select(func.max(DailyPrice.trade_date)).where(
                DailyPrice.market_cap.is_not(None),
                DailyPrice.close.is_not(None),
            )
        )
        if latest_price_date is None or latest_market_cap_date is None:
            raise RuntimeError("no daily prices are available")

        universe = db.execute(
            select(StockMaster, DailyPrice)
            .join(
                DailyPrice,
                (DailyPrice.code == StockMaster.code)
                & (DailyPrice.trade_date == latest_market_cap_date),
            )
            .where(
                StockMaster.is_active.is_(True),
                DailyPrice.market_cap.is_not(None),
                DailyPrice.close.is_not(None),
            )
            .order_by(desc(DailyPrice.market_cap))
            .limit(universe_limit)
        ).all()

        full_results = {version: [] for version in FILTER_VERSIONS}
        recent_results = {version: [] for version in FILTER_VERSIONS}
        rows: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for stock, _latest in universe:
            price_rows = list(
                db.scalars(
                    select(DailyPrice)
                    .where(DailyPrice.code == stock.code)
                    .order_by(DailyPrice.trade_date.desc())
                    .limit(history_rows)
                )
            )
            bars = qs._normalize_prices(price_rows)
            if len(bars) < qs.MIN_BACKTEST_HISTORY_ROWS:
                skipped.append(
                    {
                        "code": stock.code,
                        "name": stock.name,
                        "reason": "insufficient_complete_daily_history",
                        "normalized_bars": len(bars),
                    }
                )
                continue

            indicators = qs._indicator_rows(bars)
            recent_start_index = max(qs.WARMUP_ROWS, len(bars) - recent_trading_days)
            stock_row: dict[str, Any] = {"code": stock.code, "name": stock.name}
            for version in FILTER_VERSIONS:
                full = simulate_hybrid_ohlc_proxy(
                    bars,
                    indicators,
                    entry_filter_version=version,
                )
                recent = simulate_hybrid_ohlc_proxy(
                    bars,
                    indicators,
                    performance_start_index_override=recent_start_index,
                    entry_filter_version=version,
                )
                full_results[version].append(full)
                recent_results[version].append(recent)
                stock_row[version] = {
                    "full": _metric_snapshot(full),
                    "recent_month": _metric_snapshot(recent),
                }
            rows.append(stock_row)

    return {
        "generated_at": datetime.now(timezone.utc),
        "strategy_version": qs.STRATEGY_VERSION,
        "candidate_strategy_version": qs.CANDIDATE_STRATEGY_VERSION,
        "active_entry_filter_version": qs.ENTRY_FILTER_VERSION,
        "shadow_entry_filter_versions": list(qs.ENTRY_FILTER_SHADOW_VERSIONS),
        "latest_price_date": latest_price_date,
        "universe_market_cap_date": latest_market_cap_date,
        "universe_limit": universe_limit,
        "history_rows_requested": history_rows,
        "recent_trading_days": recent_trading_days,
        "symbols_evaluated": len(rows),
        "symbols_skipped": skipped,
        "scope": {
            "execution_model": "hybrid_sell_intraday_ohlc_proxy",
            "entry_model": "close-confirmed then next-open",
            "exit_model": "intraday hard stop and +3%/+5% targets using daily OHLC proxy",
            "costs": "same liquidity/volatility-dependent one-way execution cost",
            "data_warning": "daily OHLC cannot reconstruct true minute-level path or fill timing",
            "promotion_rule": "H1 only; H2/H3 do not alter notifications, lifecycle state, or orders",
        },
        "aggregate": _aggregate(full_results),
        "recent_month_aggregate": _aggregate(recent_results),
        "symbols": rows,
    }


def main() -> int:
    args = _parser().parse_args()
    report = build_report(
        universe_limit=args.universe_limit,
        history_rows=args.history_rows,
        recent_trading_days=args.recent_trading_days,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "active_entry_filter_version": report["active_entry_filter_version"],
                "shadow_entry_filter_versions": report["shadow_entry_filter_versions"],
                "aggregate": report["aggregate"],
                "recent_month_aggregate": report["recent_month_aggregate"],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
