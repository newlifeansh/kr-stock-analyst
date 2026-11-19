"""Backtest independently versioned entry filters as a backend shadow report.

H1 is the active candidate for the current signal path. H2 and H3 are replayed
with identical prices, exits, costs, and v8 intraday OHLC-proxy execution so their
performance can be compared without changing user-facing notifications.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import DailyPrice, QuantSignalTransitionBaseline, StockMaster
from app.services import quant_signals as qs
from app.services.regular_price_replay import regular_ordered_paths
from app.services.regular_signal_transition import (
    REGULAR_FORWARD_STRATEGY_VERSION,
    REGULAR_FORWARD_VERSION,
    forward_price_envelope,
)
from app.services.regular_session_prices import UnverifiedRegularSessionPrice
from app.services.signal_entry_evidence import load_entry_evidence_timeline
from app.services.signal_mode_comparison import simulate_v8_intraday_ohlc_proxy


FILTER_VERSIONS = (
    qs.ENTRY_FILTER_BASELINE_VERSION,
    qs.ENTRY_FILTER_H1_VERSION,
    qs.ENTRY_FILTER_H2_VERSION,
    qs.ENTRY_FILTER_H3_VERSION,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-limit", type=int, default=100)
    parser.add_argument(
        "--compare-initial", action="store_true",
        help="Compare the original price rule with current H1 on verified next-open data.",
    )
    parser.add_argument("--history-rows", type=int, default=400)
    parser.add_argument("--recent-trading-days", type=int, default=22)
    parser.add_argument(
        "--output",
        type=Path,
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
                full = simulate_v8_intraday_ohlc_proxy(
                    bars,
                    indicators,
                    entry_filter_version=version,
                )
                recent = simulate_v8_intraday_ohlc_proxy(
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
            "execution_model": qs.EXECUTION_MODEL,
            "entry_model": "close-confirmed then next-session frozen-breakout",
            "exit_model": "intraday hard stop and +3%/+5% targets using daily OHLC proxy",
            "costs": "same liquidity/volatility-dependent one-way execution cost",
            "data_warning": "daily OHLC cannot reconstruct true minute-level path or fill timing",
            "promotion_rule": "H1 only; H2/H3 do not alter notifications, lifecycle state, or orders",
        },
        "aggregate": _aggregate(full_results),
        "recent_month_aggregate": _aggregate(recent_results),
        "symbols": rows,
    }


INITIAL_COMPARISON_VERSIONS = ("initial-price-rule", qs.ENTRY_FILTER_VERSION)


def _compare_initial_entries(bars, timeline, paths, guard) -> dict[str, dict[str, Any]]:
    indicators = qs._indicator_rows(bars)
    results = {}
    for version in INITIAL_COMPARISON_VERSIONS:
        outcomes: dict[date, str] = {}
        replay = qs._simulate(
            bars, indicators, timeline,
            lifecycle_start_date=qs.NEXT_OPEN_ENTRY_EFFECTIVE_DATE,
            performance_start_index_override=qs.WARMUP_ROWS,
            intraday_minutes_by_date=paths,
            entry_safety_guard=guard,
            entry_outcomes=outcomes,
            entry_filter_version=qs.ENTRY_FILTER_VERSION,
            initial_quant_comparison=version == "initial-price-rule",
        )
        performance = replay["performance"]
        closed = [trade for trade in replay["trades"] if trade["status"] == "closed"]
        results[version] = {
            "confirmed": sum(outcome == "confirmed" for outcome in outcomes.values()),
            "gap_rejected": sum(outcome == "opening_gap_exceeded" for outcome in outcomes.values()),
            "pending_next_open": sum(outcome == "awaiting_next_open" for outcome in outcomes.values()),
            "closed_returns_percent": [float(trade["net_return"]) for trade in closed],
            "strategy_return_percent": float(performance["strategy_return"]),
            "max_drawdown_percent": float(performance["max_drawdown"]),
        }
    return results


def _aggregate_initial_entries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    confirmed = sum(row["confirmed"] for row in rows)
    rejected = sum(row["gap_rejected"] for row in rows)
    pending = sum(row["pending_next_open"] for row in rows)
    returns = [value for row in rows for value in row["closed_returns_percent"]]
    return {
        "close_approved_candidates": confirmed + rejected + pending,
        "confirmed": confirmed,
        "gap_rejected": rejected,
        "pending_next_open": pending,
        "confirmation_rate_percent": round(100 * confirmed / (confirmed + rejected), 2) if confirmed + rejected else None,
        "completed_trades": len(returns),
        "average_net_trade_return_percent": round(sum(returns) / len(returns), 2) if returns else None,
        "average_symbol_return_percent": round(sum(row["strategy_return_percent"] for row in rows) / len(rows), 2) if rows else None,
        "worst_symbol_max_drawdown_percent": min((row["max_drawdown_percent"] for row in rows), default=None),
    }


def build_initial_comparison(db: Session, *, universe_limit: int, now: datetime) -> dict[str, Any]:
    if universe_limit <= 0:
        raise ValueError("universe-limit must be positive")
    start = qs.NEXT_OPEN_ENTRY_EFFECTIVE_DATE
    completed = qs.latest_completed_korea_market_session_date(now)
    if now.time() >= time(15, 40) and qs.is_korea_market_session_date(now.date(), now):
        completed = now.date()
    domestic = (
        DailyPrice.market_cap > 0, DailyPrice.close > 0,
        StockMaster.market.in_(("KOSPI", "KOSDAQ")),
    )
    cohort_day = db.scalar(select(func.max(DailyPrice.trade_date))
        .join(StockMaster, StockMaster.code == DailyPrice.code)
        .where(DailyPrice.trade_date < start, *domestic))
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    if cohort_day is not None and completed is not None and completed >= start:
        codes = list(db.scalars(select(DailyPrice.code)
            .join(StockMaster, StockMaster.code == DailyPrice.code)
            .where(DailyPrice.trade_date == cohort_day, *domestic)
            .order_by(DailyPrice.market_cap.desc(), DailyPrice.code).limit(universe_limit)))
        guard = qs.load_entry_safety_guard(db)
        for code in codes:
            try:
                # The comparison consumes frozen inputs and does not create a baseline.
                key = f"{REGULAR_FORWARD_VERSION}:prices:{code}"
                if db.get(QuantSignalTransitionBaseline, key) is None:
                    raise UnverifiedRegularSessionPrice("동결된 가격 준비 자료 없음")
                rows = list(db.scalars(select(DailyPrice).where(
                    DailyPrice.code == code, DailyPrice.trade_date <= completed,
                ).order_by(DailyPrice.trade_date.desc()).limit(qs.SIGNAL_HISTORY_ROWS)))
                envelope = forward_price_envelope(db, code, rows, completed_through=completed)
                bars = qs._market_signal_complete_suffix(qs._normalize_prices(envelope.lower))
                if len(bars) <= qs.WARMUP_ROWS or bars[qs.WARMUP_ROWS - 1].trade_date >= start:
                    raise UnverifiedRegularSessionPrice("비교 시작 전 완전 일봉 부족")
                timeline = load_entry_evidence_timeline(db, code, strategy_version=REGULAR_FORWARD_STRATEGY_VERSION)
                days = [bar.trade_date for bar in bars if bar.trade_date >= start]
                if not days or days[-1] != completed:
                    raise UnverifiedRegularSessionPrice("비교 종료일까지 완료 일봉 부족")
                # A frozen veto is a completed decision, including during broad selloffs.
                if any(((timeline.get(day) or {}).get("quality") or {}).get("state") not in {"ready", "blocked"} for day in days):
                    raise UnverifiedRegularSessionPrice("비교 기간의 시점별 독립 근거 부족")
                paths = regular_ordered_paths(envelope)
                if any(not paths.get(day) for day in days):
                    raise UnverifiedRegularSessionPrice("비교 기간의 검증된 정규장 분봉 부족")
                results.append({"code": code, "rules": _compare_initial_entries(bars, timeline, paths, guard)})
            except UnverifiedRegularSessionPrice as error:
                skipped.append({"code": code, "reason": str(error)})
    aggregate = {
        version: _aggregate_initial_entries([row["rules"][version] for row in results])
        for version in INITIAL_COMPARISON_VERSIONS
    }
    return {
        "status": "computed" if results else "insufficient_data",
        "cohort_market_cap_date": cohort_day,
        "period_start": start,
        "period_end": completed,
        "symbols_evaluated": len(results),
        "symbols_skipped": skipped,
        "execution_model": qs.NEXT_OPEN_ENTRY_EXECUTION_MODEL,
        "assumptions": [
            "비교 시작일 이전 시총으로 순위를 고정하고 두 규칙을 같은 종목·기간에 적용합니다.",
            "정규장 시가 갭 제한·분봉 기반 매도·체결비용·재진입·공통 성과 안전 규칙을 공유합니다.",
            "초기 가격 조건과 이전 H1·독립 근거 조건의 차이만 비교합니다.",
            "비용 차감 수익률을 사용하고 미확정 후보는 전환율 분모에서 제외합니다.",
            "두 규칙 모두 검증 가능한 종목만 포함하며 운영 포트폴리오 수익률과 구분합니다.",
        ],
        "aggregate": aggregate,
        "symbols": results,
    }


def main() -> int:
    args = _parser().parse_args()
    if args.compare_initial:
        output = args.output or Path("artifacts/qa-data-signal/initial-entry-comparison.json")
        with SessionLocal() as db:
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            try:
                report = build_initial_comparison(db, universe_limit=args.universe_limit, now=datetime.now(qs.KST))
            except OperationalError as error:
                if db.get_bind().dialect.name != "sqlite" or "no such table" not in str(error.orig):
                    raise
                report = {"status": "insufficient_data", "symbols_evaluated": 0, "reason": "로컬 가격·시그널 테이블 없음"}
        console = {key: value for key, value in report.items() if key not in {"symbols", "symbols_skipped"}}
    else:
        output = args.output or Path("artifacts/qa-data-signal/entry-filter-shadow-comparison.json")
        report = build_report(
            universe_limit=args.universe_limit,
            history_rows=args.history_rows,
            recent_trading_days=args.recent_trading_days,
        )
        console = {key: report[key] for key in (
            "active_entry_filter_version", "shadow_entry_filter_versions", "aggregate", "recent_month_aggregate",
        )}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **console}, ensure_ascii=False, indent=2, default=str))
    return 2 if report.get("status") == "insufficient_data" else 0


if __name__ == "__main__":
    raise SystemExit(main())
