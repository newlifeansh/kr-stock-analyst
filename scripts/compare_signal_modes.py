"""Compare the current daily-open signal model with the hybrid sell model.

This report is intentionally an analysis artifact.  It uses the same daily
entries, strategy-date-aware rules, and execution-cost model for both runs.
The hybrid side only changes hard-stop and profit-target sells, replayed with a
conservative daily OHLC proxy because persistent intraday history is not yet
available in the application database.
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
from app.services.signal_mode_comparison import (
    aggregate_mode_comparison,
    simulate_full_intraday_ohlc_proxy,
    simulate_hybrid_ohlc_proxy,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-limit", type=int, default=100)
    parser.add_argument("--history-rows", type=int, default=400)
    parser.add_argument("--recent-trading-days", type=int, default=22)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/qa-data-signal/signal-mode-comparison.json"),
    )
    return parser


def _metric_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": result["mode"],
        "period_start": result["period_start"],
        "period_end": result["period_end"],
        "strategy_return": result["strategy_return"],
        "max_drawdown": result["max_drawdown"],
        "completed_trades": result["completed_trades"],
        "win_rate": result["win_rate"],
        "average_return": result["average_return"],
        "turnover_percent": result["turnover_percent"],
        "open_position_return": result.get("open_position_return"),
        "trades": result.get("trades", []),
    }


def _run_pair(
    bars: list[qs.PriceBar],
    indicators: list[dict[str, float]],
    *,
    performance_start_index: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    daily = qs._simulate(
        bars,
        indicators,
        performance_start_index_override=performance_start_index,
    )
    hybrid = simulate_hybrid_ohlc_proxy(
        bars,
        indicators,
        performance_start_index_override=daily["start_index"],
    )
    full_intraday = simulate_full_intraday_ohlc_proxy(
        bars,
        indicators,
        performance_start_index_override=daily["start_index"],
    )
    daily_period_start = daily["performance"]["period_start"]
    daily_closed_trades = [
        trade
        for trade in daily["trades"]
        if trade.get("status") == "closed"
        and trade.get("exit_date") is not None
        and trade["exit_date"] >= daily_period_start
    ]
    return (
        _metric_snapshot(
            daily["performance"]
            | {"trades": daily_closed_trades, "mode": "daily_open"}
        ),
        _metric_snapshot(hybrid),
        _metric_snapshot(full_intraday),
    )


def build_report(
    *,
    universe_limit: int,
    history_rows: int,
    recent_trading_days: int,
) -> dict[str, Any]:
    if universe_limit <= 0:
        raise ValueError("universe-limit must be positive")
    if history_rows < qs.MIN_BACKTEST_HISTORY_ROWS:
        raise ValueError(
            f"history-rows must be at least {qs.MIN_BACKTEST_HISTORY_ROWS}"
        )
    if recent_trading_days <= 0:
        raise ValueError("recent-trading-days must be positive")

    with SessionLocal() as db:
        latest_price_date = db.scalar(
            select(func.max(DailyPrice.trade_date)).where(
                DailyPrice.close.is_not(None),
            )
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
            full_daily, full_hybrid, full_intraday = _run_pair(bars, indicators)
            recent_start_index = max(qs.WARMUP_ROWS, len(bars) - recent_trading_days)
            recent_daily, recent_hybrid, recent_full_intraday = _run_pair(
                bars,
                indicators,
                performance_start_index=recent_start_index,
            )
            rows.append(
                {
                    "code": stock.code,
                    "name": stock.name,
                    "history_rows": len(bars),
                    "daily": full_daily,
                    "hybrid": full_hybrid,
                    "full_intraday": full_intraday,
                    "recent_month": {
                        "daily": recent_daily,
                        "hybrid": recent_hybrid,
                        "full_intraday": recent_full_intraday,
                    },
                }
            )

    aggregate = aggregate_mode_comparison(rows)
    recent_rows = [
        {
            "code": row["code"],
            "name": row["name"],
            "daily": row["recent_month"]["daily"],
            "hybrid": row["recent_month"]["hybrid"],
            "full_intraday": row["recent_month"]["full_intraday"],
        }
        for row in rows
    ]
    recent_aggregate = aggregate_mode_comparison(recent_rows)
    return {
        "generated_at": datetime.now(timezone.utc),
        "strategy_version": qs.STRATEGY_VERSION,
        "comparison_candidate": "hybrid-sell-intraday-v7.5-rc2",
        "latest_price_date": latest_price_date,
        "universe_market_cap_date": latest_market_cap_date,
        "universe_limit": universe_limit,
        "history_rows_requested": history_rows,
        "recent_trading_days": recent_trading_days,
        "symbols_evaluated": len(rows),
        "symbols_skipped": skipped,
        "scope": {
            "entries": "same close-confirmed entries and next-open execution",
            "normal_trend_exits": "same close-confirmed exits and next-open execution",
            "hybrid_sell_exits": "hard stop and +3%/+5% profit targets within the current OHLC bar",
            "full_intraday_proxy": "signal-day close entry plus the same OHLC-bar intraday sell rules",
            "costs": "same liquidity/volatility-dependent one-way execution cost",
            "intraday_data": "not available; daily OHLC conservative proxy, not a minute-level fill replay",
        },
        "aggregate": aggregate,
        "recent_month_aggregate": recent_aggregate,
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
    aggregate = report["aggregate"]
    daily = aggregate["daily_open"]
    hybrid = aggregate["hybrid_intraday_sell"]
    full_intraday = aggregate["full_intraday_buy_sell"]
    delta = aggregate["delta_hybrid_minus_daily"]
    recent = report["recent_month_aggregate"]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "latest_price_date": report["latest_price_date"],
                "universe_market_cap_date": report["universe_market_cap_date"],
                "symbols_evaluated": report["symbols_evaluated"],
                "daily_open": daily,
                "hybrid_intraday_sell": hybrid,
                "full_intraday_buy_sell": full_intraday,
                "delta_hybrid_minus_daily": delta,
                "delta_full_minus_hybrid": aggregate["delta_full_minus_hybrid"],
                "delta_full_minus_daily": aggregate["delta_full_minus_daily"],
                "recent_month_aggregate": {
                    "daily_open": recent["daily_open"],
                    "hybrid_intraday_sell": recent["hybrid_intraday_sell"],
                    "full_intraday_buy_sell": recent["full_intraday_buy_sell"],
                    "delta_hybrid_minus_daily": recent["delta_hybrid_minus_daily"],
                    "delta_full_minus_hybrid": recent["delta_full_minus_hybrid"],
                    "delta_full_minus_daily": recent["delta_full_minus_daily"],
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
