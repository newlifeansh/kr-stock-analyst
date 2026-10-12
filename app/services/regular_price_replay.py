"""Read-only migration evidence; never a publisher or an automatic promotion.

Bounded turnover is not an observed point value.  Lower/upper values below
exist only as explicitly labelled hypothetical inputs.  Production may consume
neither until the complete input/evidence migration has been validated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models import DailyPrice
from app.services import quant_signals as qs
from app.services.regular_session_prices import (
    PRICE_FIELDS,
    REGULAR_PRICE_BASIS,
    REGULAR_PRICE_EFFECTIVE_DATE,
    UnverifiedRegularSessionPrice,
    _session_dates,
    load_regular_session_evidence,
)


@dataclass(frozen=True)
class RegularPriceEnvelope:
    lower: list[DailyPrice]
    upper: list[DailyPrice]
    evidence: dict[date, dict[str, Any]]


def regular_price_envelope(
    db: Session, code: str, rows: list[DailyPrice], *, completed_through: date,
) -> RegularPriceEnvelope:
    """Detached scenarios with unchanged OHLCV and explicit money endpoints."""
    if not rows or any(row.code != code for row in rows):
        raise UnverifiedRegularSessionPrice("한 종목의 기존 가격 이력이 필요합니다")
    originals = {row.trade_date: row for row in rows if row.trade_date <= completed_through}
    if len(originals) != len([row for row in rows if row.trade_date <= completed_through]):
        raise UnverifiedRegularSessionPrice("중복 일봉이 있습니다")
    lower: list[DailyPrice] = []
    upper: list[DailyPrice] = []
    evidence: dict[date, dict[str, Any]] = {}
    for day, row in sorted(originals.items()):
        if day < REGULAR_PRICE_EFFECTIVE_DATE:
            for target in (lower, upper):
                target.append(DailyPrice(code=code, trade_date=day, **{
                    field: getattr(row, field) for field in PRICE_FIELDS
                }, market_cap=row.market_cap, listed_shares=row.listed_shares))
    start = max(REGULAR_PRICE_EFFECTIVE_DATE, min(row.trade_date for row in rows))
    for day in _session_dates(start, completed_through):
        item = load_regular_session_evidence(db, code, day, allow_bounded=True)
        evidence[day] = item
        display = originals.get(day)
        for target, endpoint in ((lower, "lower"), (upper, "upper")):
            values = dict(item["prices"])
            if item["state"] == "bounded":
                values["trading_value"] = item["turnover_bounds"][endpoint]
            target.append(DailyPrice(
                code=code, trade_date=day, **values,
                market_cap=display.market_cap if display else None,
                listed_shares=display.listed_shares if display else None,
            ))
    return RegularPriceEnvelope(lower, upper, evidence)


def turnover_decision_certificate(envelope: RegularPriceEnvelope) -> dict[str, Any]:
    """Prove the current price-only liquidity predicates for every input day.

    Rolling sums are monotone in every positive turnover. Comparing all-low to
    all-high therefore encloses *every* mixed daily assignment, not just two
    chosen scenarios. Execution cost is piecewise constant at these thresholds.
    Independent flow/sector evidence is explicitly outside this certificate.
    """
    if len(envelope.lower) != len(envelope.upper) or any(
        any(getattr(left, key) != getattr(right, key) for key in (
            "code", "trade_date", "open", "high", "low", "close", "volume",
        )) for left, right in zip(envelope.lower, envelope.upper)
    ):
        raise UnverifiedRegularSessionPrice("원본 OHLCV가 일치하지 않습니다")
    lower = qs._normalize_prices(envelope.lower)
    upper = qs._normalize_prices(envelope.upper)
    if not lower or len(lower) != len(upper):
        raise UnverifiedRegularSessionPrice("가격 구간의 양 끝이 일치하지 않습니다")
    for left, right in zip(lower, upper):
        if any(getattr(left, key) != getattr(right, key) for key in (
            "trade_date", "open", "high", "low", "close", "volume", "ohlc_complete",
        )) or left.trading_value > right.trading_value or left.trading_value < 0:
            raise UnverifiedRegularSessionPrice("OHLCV가 같고 거래대금만 유효한 구간이어야 합니다")
    lows, highs = qs._indicator_rows(lower), qs._indicator_rows(upper)
    thresholds = sorted({
        float(qs.MIN_AVERAGE_TRADING_VALUE),
        float(qs.MARKET_SIGNAL_EXTENDED_MIN_AVERAGE_TRADING_VALUE),
        5_000_000_000.0, 20_000_000_000.0, 100_000_000_000.0,
    })
    checked = []
    for bar, low, high in zip(lower, lows, highs):
        # Detect any new continuous dependency in the shared indicator code.
        if {k: v for k, v in low.items() if k != "average_trading_value"} != {
            k: v for k, v in high.items() if k != "average_trading_value"
        }:
            raise UnverifiedRegularSessionPrice("거래대금의 새로운 지표 의존성을 검증해야 합니다")
        lo, hi = low["average_trading_value"], high["average_trading_value"]
        crossing = [int(t) for t in thresholds if lo < t <= hi]
        cost_equal = qs._execution_cost(low) == qs._execution_cost(high)
        checked.append({
            "trade_date": bar.trade_date.isoformat(),
            "average_turnover_lower": lo, "average_turnover_upper": hi,
            "crossed_thresholds": crossing, "execution_cost_identical": cost_equal,
            "invariant": not crossing and cost_equal,
        })
    return {
        "basis_version": REGULAR_PRICE_BASIS,
        "state": "invariant" if all(item["invariant"] for item in checked) else "ambiguous",
        "scope": "price_only_entry_liquidity_extended_universe_execution_cost",
        "independent_entry_evidence_verified": False,
        "production_ready": False,
        "days": checked,
    }


def regular_ordered_paths(envelope: RegularPriceEnvelope) -> dict[date, list[qs.PriceBar]]:
    """Use only the verified dated path, not an invented order of daily OHLC."""
    bars = {bar.trade_date: bar for bar in qs._normalize_prices(envelope.lower)}
    result = {}
    for day, evidence in envelope.evidence.items():
        path = qs._verified_completed_intraday_minutes(evidence["regular_rows"], bars[day])
        if path is None:
            raise UnverifiedRegularSessionPrice(f"{day}: 정규장 경로 재생 검증 실패")
        result[day] = path
    return result
