"""Persistent backend shadow backtests for the active and candidate filters."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, MarketQuantSignalSnapshot, StockMaster
from app.services import quant_signals as qs
from app.services.signal_mode_comparison import simulate_v8_intraday_ohlc_proxy

ENTRY_FILTER_SHADOW_CACHE_KEY = (
    f"entry-filter-shadow:fixed-cohort-v1:{qs.CANDIDATE_STRATEGY_VERSION}"
)
FILTER_VERSIONS = (
    qs.ENTRY_FILTER_BASELINE_VERSION,
    qs.ENTRY_FILTER_H1_VERSION,
    qs.ENTRY_FILTER_H2_VERSION,
    qs.ENTRY_FILTER_H3_VERSION,
)
FORWARD_ROLLING_TRADE_COUNT = 20
H3_PROMOTION_MIN_FORWARD_TRADES = 40
SHADOW_HISTORY_LOOKBACK_DAYS = 600
SHADOW_HISTORY_MAX_WORKERS = 8


def _codes_needing_shadow_history(
    counts: dict[str, int],
    *,
    minimum_rows: int = qs.MIN_BACKTEST_HISTORY_ROWS,
) -> list[str]:
    """Return codes that cannot yet support the fixed-cohort replay."""

    return sorted(
        code for code, count in counts.items() if int(count or 0) < int(minimum_rows)
    )


def _ensure_shadow_history(
    db: Session,
    codes: list[str],
    *,
    latest_price_date: date,
    minimum_rows: int = qs.MIN_BACKTEST_HISTORY_ROWS,
) -> dict[str, int]:
    """Backfill the fixed cohort before treating a shadow run as complete.

    Staging can contain today's 100/100 quote coverage while still having only
    a short recent history.  The replay needs the same long history as the
    production strategy, so fill that gap through the existing KRX/FDR batch
    collector before building the report.
    """

    if not codes:
        return {"requested_codes": 0, "rows_loaded": 0}
    rows = db.execute(
        select(DailyPrice.code, func.count(DailyPrice.code))
        .where(DailyPrice.code.in_(tuple(codes)))
        .group_by(DailyPrice.code)
    ).all()
    counts = {str(code): int(count or 0) for code, count in rows}
    missing = _codes_needing_shadow_history(
        {code: counts.get(code, 0) for code in codes},
        minimum_rows=minimum_rows,
    )
    if not missing:
        return {"requested_codes": 0, "rows_loaded": 0}

    from app.collectors.krx import collect_prices_for_codes

    from_date = latest_price_date - timedelta(days=SHADOW_HISTORY_LOOKBACK_DAYS)
    rows_loaded = collect_prices_for_codes(
        db,
        missing,
        from_yyyymmdd=from_date.strftime("%Y%m%d"),
        to_yyyymmdd=latest_price_date.strftime("%Y%m%d"),
        max_workers=SHADOW_HISTORY_MAX_WORKERS,
    )
    return {"requested_codes": len(missing), "rows_loaded": int(rows_loaded)}


def _shadow_report_is_current(report: dict[str, Any] | None) -> bool:
    """Return whether a stored report contains the current comparison contract."""

    if not isinstance(report, dict):
        return False
    comparison = report.get("forward_comparison")
    if not isinstance(comparison, dict):
        return False
    filters = comparison.get("filters")
    rolling = comparison.get("rolling_last_trades")
    return bool(
        report.get("candidate_strategy_version") == qs.CANDIDATE_STRATEGY_VERSION
        and report.get("active_entry_filter_version") == qs.ENTRY_FILTER_VERSION
        and int(report.get("symbols_evaluated") or 0) > 0
        and comparison.get("version") == "entry-filter-fixed-cohort-forward-v1"
        and isinstance(filters, dict)
        and isinstance(rolling, dict)
        and all(version in filters for version in FILTER_VERSIONS)
        and all(version in rolling for version in FILTER_VERSIONS)
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


def _rolling_trade_aggregate(
    results: dict[str, list[dict[str, Any]]],
    *,
    trade_count: int = FORWARD_ROLLING_TRADE_COUNT,
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for version, items in results.items():
        trades = sorted(
            [
                trade
                for item in items
                for trade in item.get("trades", [])
                if trade.get("exit_date") is not None
            ],
            key=lambda trade: (trade["exit_date"], trade.get("entry_date") or date.min),
        )[-trade_count:]
        returns = [float(trade["net_return"]) for trade in trades]
        summaries[version] = {
            "requested_trades": trade_count,
            "completed_trades": len(returns),
            "period_start": trades[0].get("exit_date") if trades else None,
            "period_end": trades[-1].get("exit_date") if trades else None,
            "win_rate": round(sum(value > 0 for value in returns) / len(returns) * 100.0, 2)
            if returns
            else None,
            "average_trade_return": round(sum(returns) / len(returns), 2)
            if returns
            else None,
        }
    h1 = summaries[qs.ENTRY_FILTER_H1_VERSION]
    for summary in summaries.values():
        summary["delta_vs_h1"] = {
            key: round(float(summary[key]) - float(h1[key]), 2)
            if summary.get(key) is not None and h1.get(key) is not None
            else None
            for key in ("win_rate", "average_trade_return")
        }
    return summaries


def _h3_promotion_assessment(
    aggregate: dict[str, Any],
    rolling: dict[str, Any],
) -> dict[str, Any]:
    h1 = aggregate[qs.ENTRY_FILTER_H1_VERSION]
    h3 = aggregate[qs.ENTRY_FILTER_H3_VERSION]
    rolling_h1 = rolling[qs.ENTRY_FILTER_H1_VERSION]
    rolling_h3 = rolling[qs.ENTRY_FILTER_H3_VERSION]
    checks = {
        "minimum_forward_trades": int(h3.get("completed_trades") or 0)
        >= H3_PROMOTION_MIN_FORWARD_TRADES,
        "minimum_recent_trades": int(rolling_h3.get("completed_trades") or 0)
        >= FORWARD_ROLLING_TRADE_COUNT,
        "positive_recent_expectancy": (
            rolling_h3.get("average_trade_return") is not None
            and float(rolling_h3["average_trade_return"]) > 0
        ),
        "recent_expectancy_not_below_h1": (
            rolling_h3.get("average_trade_return") is not None
            and rolling_h1.get("average_trade_return") is not None
            and float(rolling_h3["average_trade_return"])
            >= float(rolling_h1["average_trade_return"])
        ),
        "forward_expectancy_not_below_h1": (
            h3.get("average_trade_return") is not None
            and h1.get("average_trade_return") is not None
            and float(h3["average_trade_return"]) >= float(h1["average_trade_return"])
        ),
        "drawdown_not_worse_than_h1": (
            h3.get("average_max_drawdown") is not None
            and h1.get("average_max_drawdown") is not None
            and float(h3["average_max_drawdown"]) >= float(h1["average_max_drawdown"])
        ),
    }
    enough_sample = checks["minimum_forward_trades"] and checks["minimum_recent_trades"]
    eligible = enough_sample and all(checks.values())
    return {
        "candidate": qs.ENTRY_FILTER_H3_VERSION,
        "current_active": qs.ENTRY_FILTER_H1_VERSION,
        "status": (
            "eligible_for_operator_review"
            if eligible
            else "shadow_not_eligible" if enough_sample else "shadow_collecting"
        ),
        "eligible_for_operator_review": eligible,
        "automatic_promotion": False,
        "operator_approval_required": True,
        "minimum_forward_trades": H3_PROMOTION_MIN_FORWARD_TRADES,
        "minimum_recent_trades": FORWARD_ROLLING_TRADE_COUNT,
        "checks": checks,
    }


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
    """Run all filters on the same universe and v8 intraday execution replay."""

    if universe_limit <= 0:
        raise ValueError("universe_limit must be positive")
    if history_rows < qs.MIN_BACKTEST_HISTORY_ROWS:
        raise ValueError(f"history_rows must be at least {qs.MIN_BACKTEST_HISTORY_ROWS}")
    if recent_trading_days <= 0:
        raise ValueError("recent_trading_days must be positive")

    latest_price_date, latest_market_cap_date = _latest_price_dates(db)
    if latest_price_date is None or latest_market_cap_date is None:
        raise RuntimeError("no daily prices are available")

    cohort_market_cap_date = db.scalar(
        select(func.max(DailyPrice.trade_date)).where(
            DailyPrice.trade_date <= qs.ENTRY_FILTER_EFFECTIVE_DATE,
            DailyPrice.market_cap.is_not(None),
            DailyPrice.close.is_not(None),
        )
    )
    cohort_market_cap_source = "krx_historical_market_cap"
    if cohort_market_cap_date is None:
        fallback_date = db.scalar(
            select(func.max(DailyPrice.trade_date)).where(
                DailyPrice.trade_date <= qs.ENTRY_FILTER_EFFECTIVE_DATE,
                DailyPrice.close.is_not(None),
            )
        )
        if fallback_date is not None:
            from app.collectors.krx import derive_market_caps_for_date

            derive_market_caps_for_date(db, fallback_date)
            cohort_market_cap_date = db.scalar(
                select(func.max(DailyPrice.trade_date)).where(
                    DailyPrice.trade_date <= qs.ENTRY_FILTER_EFFECTIVE_DATE,
                    DailyPrice.market_cap.is_not(None),
                    DailyPrice.close.is_not(None),
                )
            )
            if cohort_market_cap_date is not None:
                cohort_market_cap_source = "fdr_derived_current_listed_shares"
    if cohort_market_cap_date is None:
        raise RuntimeError("no market-cap cohort is available at the filter effective date")

    universe = db.execute(
        select(StockMaster, DailyPrice)
        .join(
            DailyPrice,
            (DailyPrice.code == StockMaster.code)
            & (DailyPrice.trade_date == cohort_market_cap_date),
        )
        .where(
            StockMaster.market.in_(("KOSPI", "KOSDAQ")),
            DailyPrice.market_cap.is_not(None),
            DailyPrice.close.is_not(None),
        )
        .order_by(desc(DailyPrice.market_cap))
        .limit(universe_limit)
    ).all()

    history_backfill = _ensure_shadow_history(
        db,
        [stock.code for stock, _latest in universe],
        latest_price_date=latest_price_date,
    )

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
        forward_start_index = next(
            (
                index
                for index, bar in enumerate(bars)
                if index >= qs.WARMUP_ROWS
                and bar.trade_date >= qs.ENTRY_FILTER_EFFECTIVE_DATE
            ),
            len(bars) - 1,
        )
        recent_start_index = max(qs.WARMUP_ROWS, len(bars) - recent_trading_days)
        for version in FILTER_VERSIONS:
            full_results[version].append(
                simulate_v8_intraday_ohlc_proxy(
                    bars,
                    indicators,
                    performance_start_index_override=forward_start_index,
                    entry_filter_version=version,
                )
            )
            recent_results[version].append(
                simulate_v8_intraday_ohlc_proxy(
                    bars,
                    indicators,
                    performance_start_index_override=recent_start_index,
                    entry_filter_version=version,
                )
            )

    forward_aggregate = _aggregate(full_results)
    rolling_trade_aggregate = _rolling_trade_aggregate(full_results)
    promotion_assessment = _h3_promotion_assessment(
        forward_aggregate,
        rolling_trade_aggregate,
    )
    return {
        "generated_at": datetime.now(UTC),
        "strategy_version": qs.STRATEGY_VERSION,
        "candidate_strategy_version": qs.CANDIDATE_STRATEGY_VERSION,
        "active_entry_filter_version": qs.ENTRY_FILTER_VERSION,
        "shadow_entry_filter_versions": list(qs.ENTRY_FILTER_SHADOW_VERSIONS),
        "latest_price_date": latest_price_date,
        "universe_market_cap_date": cohort_market_cap_date,
        "universe_market_cap_source": cohort_market_cap_source,
        "universe_limit": universe_limit,
        "history_rows_requested": history_rows,
        "history_backfill": history_backfill,
        "recent_trading_days": recent_trading_days,
        "symbols_evaluated": sum(len(items) for items in full_results.values()) // len(FILTER_VERSIONS),
        "symbols_skipped": skipped,
        "scope": {
            "execution_model": qs.EXECUTION_MODEL,
            "entry_model": "close-confirmed then next-session frozen-breakout",
            "data_warning": "일봉 OHLC 기반 보수적 장중 돌파·매도 프록시이며 실제 분봉 체결이 아닙니다.",
            "promotion_rule": "H1만 활성 신호에 사용하고 H2/H3는 shadow 비교 후 운영자 승인 없이 자동 승격하지 않음",
        },
        "aggregate": forward_aggregate,
        "recent_month_aggregate": _aggregate(recent_results),
        "forward_comparison": {
            "version": "entry-filter-fixed-cohort-forward-v1",
            "cohort_market_cap_date": cohort_market_cap_date,
            "cohort_market_cap_source": cohort_market_cap_source,
            "cohort_rule": f"{cohort_market_cap_date.isoformat()} 시가총액 상위 {universe_limit}개 고정",
            "period_start": qs.ENTRY_FILTER_EFFECTIVE_DATE,
            "period_end": latest_price_date,
            "execution_model": qs.EXECUTION_MODEL,
            "data_warning": "일봉 OHLC 기반 보수적 장중 돌파·매도 프록시이며 실제 분봉 체결이 아닙니다.",
            "filters": forward_aggregate,
            "rolling_last_trades": rolling_trade_aggregate,
            "promotion_assessment": promotion_assessment,
        },
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
        and _shadow_report_is_current(previous)
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
