from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from math import sqrt
from statistics import fmean
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, StockMaster

OPPOSITE_MOVE_LOOKBACK_SESSIONS = 120
OPPOSITE_MOVE_MIN_OBSERVATIONS = 60
OPPOSITE_MOVE_RECENT_SESSIONS = 60
OPPOSITE_MOVE_UNIVERSE_LIMIT = 500
OPPOSITE_MOVE_MIN_TRADING_VALUE = 500_000_000
OPPOSITE_MOVE_MIN_MARKET_CAP = 100_000_000_000
OPPOSITE_MOVE_COMPLETED_CLOSE_READY_TIME = time(15, 40)
KST = ZoneInfo("Asia/Seoul")


def opposite_moves_completed_through(now: datetime | None = None) -> date:
    current = now or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    else:
        current = current.astimezone(KST)
    through = current.date()
    if current.time() < OPPOSITE_MOVE_COMPLETED_CLOSE_READY_TIME:
        through -= timedelta(days=1)
    return through


def _daily_returns(rows: Iterable[DailyPrice]) -> dict[date, float]:
    ordered = sorted(
        (
            row
            for row in rows
            if row.close is not None and row.close > 0
        ),
        key=lambda row: row.trade_date,
    )
    returns: dict[date, float] = {}
    previous_close: int | None = None
    for row in ordered:
        current_close = int(row.close or 0)
        if previous_close not in (None, 0):
            returns[row.trade_date] = current_close / previous_close - 1.0
        previous_close = current_close
    return returns


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = fmean(left)
    right_mean = fmean(right)
    left_delta = [value - left_mean for value in left]
    right_delta = [value - right_mean for value in right]
    denominator = sqrt(
        sum(value * value for value in left_delta)
        * sum(value * value for value in right_delta)
    )
    if denominator == 0:
        return None
    return sum(a * b for a, b in zip(left_delta, right_delta, strict=True)) / denominator


def _market_group(market: str) -> tuple[str, ...]:
    normalized = str(market or "").upper()
    if normalized in {"KOSPI", "KOSDAQ"}:
        return ("KOSPI", "KOSDAQ")
    return (normalized,)


def _relationship_label(
    correlation: float,
    recent_correlation: float,
    down_day_opposite_rate: float,
) -> str:
    if (
        correlation <= -0.25
        and recent_correlation <= -0.20
        and down_day_opposite_rate >= 0.62
    ):
        return "자주 반대로 움직임"
    return "가끔 반대로 움직임"


def _empty_payload(
    stock: StockMaster,
    *,
    status: str,
    message: str,
    as_of: date | None = None,
    observations: int = 0,
) -> dict[str, Any]:
    return {
        "code": stock.code,
        "name": stock.name,
        "status": status,
        "message": message,
        "as_of": as_of,
        "lookback_sessions": OPPOSITE_MOVE_LOOKBACK_SESSIONS,
        "observations": observations,
        "items": [],
    }


def build_opposite_moves(
    db: Session,
    code: str,
    *,
    limit: int = 3,
    completed_through: date | None = None,
) -> dict[str, Any]:
    """Find liquid domestic stocks whose completed closes moved oppositely.

    The relationship is descriptive rather than predictive. It is computed
    from completed daily closes and deliberately kept separate from the live
    quote that the client overlays on each returned instrument.
    """

    stock = db.get(StockMaster, code)
    if stock is None or not stock.is_active:
        raise LookupError("Stock not found")

    completed_through = completed_through or opposite_moves_completed_through()
    target_rows = list(
        db.scalars(
            select(DailyPrice)
            .where(
                DailyPrice.code == stock.code,
                DailyPrice.trade_date <= completed_through,
                DailyPrice.close.is_not(None),
            )
            .order_by(DailyPrice.trade_date.desc())
            .limit(OPPOSITE_MOVE_LOOKBACK_SESSIONS + 1)
        )
    )
    target_rows.reverse()
    target_returns = _daily_returns(target_rows)
    if len(target_returns) < OPPOSITE_MOVE_MIN_OBSERVATIONS:
        return _empty_payload(
            stock,
            status="insufficient_history",
            message="최근 가격 기록이 더 쌓이면 다른 방향으로 움직인 종목을 보여드릴게요.",
            as_of=target_rows[-1].trade_date if target_rows else None,
            observations=len(target_returns),
        )

    target_dates = [row.trade_date for row in target_rows]
    latest_date = target_dates[-1]
    candidate_latest_rows = list(
        db.execute(
            select(StockMaster, DailyPrice)
            .join(DailyPrice, DailyPrice.code == StockMaster.code)
            .where(
                StockMaster.is_active.is_(True),
                StockMaster.code != stock.code,
                StockMaster.market.in_(_market_group(stock.market)),
                DailyPrice.trade_date == latest_date,
                DailyPrice.close.is_not(None),
                DailyPrice.close > 0,
            )
            .order_by(
                func.coalesce(DailyPrice.market_cap, 0).desc(),
                func.coalesce(DailyPrice.trading_value, 0).desc(),
                StockMaster.code,
            )
            .limit(OPPOSITE_MOVE_UNIVERSE_LIMIT)
        ).all()
    )
    liquid_candidates: dict[str, tuple[StockMaster, DailyPrice]] = {}
    for candidate, latest in candidate_latest_rows:
        trading_value = int(latest.trading_value or 0)
        market_cap = int(latest.market_cap or 0)
        if (
            trading_value < OPPOSITE_MOVE_MIN_TRADING_VALUE
            and market_cap < OPPOSITE_MOVE_MIN_MARKET_CAP
        ):
            continue
        liquid_candidates[candidate.code] = (candidate, latest)

    if not liquid_candidates:
        return _empty_payload(
            stock,
            status="no_stable_opposite",
            message="최근에는 꾸준히 다른 방향으로 움직인 종목을 찾지 못했어요.",
            as_of=latest_date,
            observations=len(target_returns),
        )

    history_by_code: dict[str, list[DailyPrice]] = defaultdict(list)
    history_rows = db.scalars(
        select(DailyPrice)
        .where(
            DailyPrice.code.in_(tuple(liquid_candidates)),
            DailyPrice.trade_date.in_(tuple(target_dates)),
            DailyPrice.close.is_not(None),
        )
        .order_by(DailyPrice.code, DailyPrice.trade_date)
    )
    for row in history_rows:
        history_by_code[row.code].append(row)

    scored: list[tuple[float, dict[str, Any]]] = []
    for candidate_code, (candidate, _latest) in liquid_candidates.items():
        candidate_returns = _daily_returns(history_by_code.get(candidate_code, []))
        common_dates = sorted(set(target_returns).intersection(candidate_returns))
        if len(common_dates) < OPPOSITE_MOVE_MIN_OBSERVATIONS:
            continue
        target_values = [target_returns[day] for day in common_dates]
        candidate_values = [candidate_returns[day] for day in common_dates]
        correlation = _pearson(target_values, candidate_values)
        recent_count = min(OPPOSITE_MOVE_RECENT_SESSIONS, len(common_dates))
        recent_correlation = _pearson(
            target_values[-recent_count:],
            candidate_values[-recent_count:],
        )
        if correlation is None or recent_correlation is None:
            continue

        down_pairs = [
            candidate_value
            for target_value, candidate_value in zip(
                target_values,
                candidate_values,
                strict=True,
            )
            if target_value < 0
        ]
        opposite_up_days = sum(value > 0 for value in down_pairs)
        down_day_rate = opposite_up_days / len(down_pairs) if down_pairs else 0.0
        opposite_direction_days = sum(
            (target_value < 0 < candidate_value)
            or (candidate_value < 0 < target_value)
            for target_value, candidate_value in zip(
                target_values,
                candidate_values,
                strict=True,
            )
        )
        opposite_direction_rate = opposite_direction_days / len(common_dates)

        if (
            correlation > -0.08
            or recent_correlation > -0.05
            or down_day_rate < 0.55
            or opposite_direction_rate < 0.52
        ):
            continue

        score = (
            abs(correlation) * 0.45
            + abs(recent_correlation) * 0.25
            + max(0.0, down_day_rate - 0.5) * 0.20
            + max(0.0, opposite_direction_rate - 0.5) * 0.10
        )
        scored.append(
            (
                score,
                {
                    "code": candidate.code,
                    "name": candidate.name,
                    "market": candidate.market,
                    "sector": candidate.sector,
                    "industry": candidate.industry,
                    "relationship_label": _relationship_label(
                        correlation,
                        recent_correlation,
                        down_day_rate,
                    ),
                    "correlation": round(correlation, 4),
                    "recent_correlation": round(recent_correlation, 4),
                    "observations": len(common_dates),
                    "target_down_days": len(down_pairs),
                    "candidate_up_on_target_down_days": opposite_up_days,
                    "down_day_opposite_rate": round(down_day_rate, 4),
                    "opposite_direction_rate": round(opposite_direction_rate, 4),
                    "comparison_start": common_dates[0],
                    "comparison_end": common_dates[-1],
                    "logo_url": candidate.logo_url,
                },
            )
        )

    scored.sort(key=lambda entry: (-entry[0], entry[1]["code"]))
    items = [item for _score, item in scored[: max(1, min(limit, 5))]]
    if not items:
        return _empty_payload(
            stock,
            status="no_stable_opposite",
            message="최근에는 꾸준히 다른 방향으로 움직인 종목을 찾지 못했어요.",
            as_of=latest_date,
            observations=len(target_returns),
        )

    return {
        "code": stock.code,
        "name": stock.name,
        "status": "ready",
        "message": "최근 완료된 종가 흐름을 비교했어요.",
        "as_of": latest_date,
        "lookback_sessions": OPPOSITE_MOVE_LOOKBACK_SESSIONS,
        "observations": len(target_returns),
        "items": items,
    }
