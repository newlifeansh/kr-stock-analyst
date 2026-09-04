"""Persistent backend shadow backtests for the active and candidate filters."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, MarketQuantSignalSnapshot, StockMaster
from app.services import quant_signals as qs
from app.services.signal_mode_comparison import simulate_hybrid_ohlc_proxy

ENTRY_FILTER_SHADOW_CACHE_KEY = (
    f"entry-filter-shadow:{qs.CANDIDATE_STRATEGY_VERSION}"
)
FILTER_VERSIONS = (
    qs.ENTRY_FILTER_BASELINE_VERSION,
    qs.ENTRY_FILTER_H1_VERSION,
    qs.ENTRY_FILTER_H2_VERSION,
    qs.ENTRY_FILTER_H3_VERSION,
)


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
    for summary in summaries.values():
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


def _latest_price_dates(db: Session) -> tuple[date | None, date | None]:
    return (
        db.scalar(
            select(func.max(DailyPrice.trade_date)).where(
                DailyPrice.close.is_not(None),
            )
        ),
        db.scalar(
            select(func.max(DailyPrice.trade_date)).where(
                DailyPrice.market_cap.is_not(None),
                DailyPrice.close.is_not(None),
            )
        ),
    )


def build_entry_filter_shadow_report(
    db: Session,
    *,
    universe_limit: int = qs.MARKET_SIGNAL_CORE_UNIVERSE_LIMIT,
    history_rows: int = 400,
    recent_trading_days: int = 22,
) -> dict[str, Any]:
    """Run all filters on the same universe and hybrid execution replay."""

    if universe_limit <= 0:
        raise ValueError("universe_limit must be positive")
    if history_rows < qs.MIN_BACKTEST_HISTORY_ROWS:
        raise ValueError(f"history_rows must be at least {qs.MIN_BACKTEST_HISTORY_ROWS}")
    if recent_trading_days <= 0:
        raise ValueError("recent_trading_days must be positive")

    latest_price_date, latest_market_cap_date = _latest_price_dates(db)
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
        for version in FILTER_VERSIONS:
            full_results[version].append(
                simulate_hybrid_ohlc_proxy(
                    bars,
                    indicators,
                    entry_filter_version=version,
                )
            )
            recent_results[version].append(
                simulate_hybrid_ohlc_proxy(
                    bars,
                    indicators,
                    performance_start_index_override=recent_start_index,
                    entry_filter_version=version,
                )
            )

    return {
        "generated_at": datetime.now(UTC),
        "strategy_version": qs.STRATEGY_VERSION,
        "candidate_strategy_version": qs.CANDIDATE_STRATEGY_VERSION,
        "active_entry_filter_version": qs.ENTRY_FILTER_VERSION,
        "shadow_entry_filter_versions": list(qs.ENTRY_FILTER_SHADOW_VERSIONS),
        "latest_price_date": latest_price_date,
        "universe_market_cap_date": latest_market_cap_date,
        "universe_limit": universe_limit,
        "history_rows_requested": history_rows,
        "recent_trading_days": recent_trading_days,
        "symbols_evaluated": sum(len(items) for items in full_results.values()) // len(FILTER_VERSIONS),
        "symbols_skipped": skipped,
        "scope": {
            "execution_model": "hybrid_sell_intraday_ohlc_proxy",
            "entry_model": "close-confirmed then next-open",
            "data_warning": "일봉 OHLC 기반 보수적 장중 매도 프록시이며 실제 분봉 체결이 아닙니다.",
            "promotion_rule": "H1만 활성 신호에 사용하고 H2/H3는 shadow backtest로만 계산",
        },
        "aggregate": _aggregate(full_results),
        "recent_month_aggregate": _aggregate(recent_results),
    }


def load_entry_filter_shadow_snapshot(db: Session) -> dict[str, Any] | None:
    snapshot = db.get(MarketQuantSignalSnapshot, ENTRY_FILTER_SHADOW_CACHE_KEY)
    if snapshot is None:
        return None
    try:
        payload = json.loads(snapshot.payload)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def save_entry_filter_shadow_snapshot(
    db: Session,
    report: dict[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    stored_at = (generated_at or datetime.now(UTC)).replace(tzinfo=None)
    serialized = json.dumps(
        report,
        ensure_ascii=False,
        default=lambda value: value.isoformat()
        if isinstance(value, (date, datetime))
        else str(value),
    )
    snapshot = db.get(MarketQuantSignalSnapshot, ENTRY_FILTER_SHADOW_CACHE_KEY)
    if snapshot is None:
        db.add(
            MarketQuantSignalSnapshot(
                cache_key=ENTRY_FILTER_SHADOW_CACHE_KEY,
                payload=serialized,
                generated_at=stored_at,
            )
        )
    else:
        snapshot.payload = serialized
        snapshot.generated_at = stored_at
    db.commit()
    return report


def refresh_entry_filter_shadow_snapshot(
    db: Session,
    *,
    force: bool = False,
    universe_limit: int = qs.MARKET_SIGNAL_CORE_UNIVERSE_LIMIT,
    history_rows: int = 400,
    recent_trading_days: int = 22,
) -> dict[str, Any]:
    """Refresh once for each new completed price date and persist the result."""

    latest_price_date, _latest_market_cap_date = _latest_price_dates(db)
    previous = load_entry_filter_shadow_snapshot(db)
    if (
        not force
        and latest_price_date is not None
        and previous is not None
        and str(previous.get("latest_price_date")) == latest_price_date.isoformat()
    ):
        return {"status": "unchanged", "report": previous}
    report = build_entry_filter_shadow_report(
        db,
        universe_limit=universe_limit,
        history_rows=history_rows,
        recent_trading_days=recent_trading_days,
    )
    if report["symbols_evaluated"] <= 0:
        return {"status": "skipped", "report": report}
    save_entry_filter_shadow_snapshot(db, report)
    return {"status": "refreshed", "report": report}
