"""Freeze verified historical warmup prices without changing display candles."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPrice
from app.services import quant_signals as qs
from app.services.regular_signal_transition import (
    REGULAR_FORWARD_START,
    REGULAR_FORWARD_VERSION,
    _freeze,
    _load,
    frozen_legacy_price_rows,
)
from app.services.regular_session_prices import PRICE_FIELDS, UnverifiedRegularSessionPrice


def restore_legacy_warmup(
    db: Session, code: str, proof: dict[str, Any], *, persist: bool = False,
) -> dict[str, Any]:
    """Add one immutable forward-only price baseline from dated original prices."""
    if proof.get("source") != "kis_dated_daily:FHKST03010100:J:original":
        raise UnverifiedRegularSessionPrice("과거 일봉 원천이 다릅니다")
    independent = proof.get("independent_last_close") or {}
    if (
        independent.get("source") not in {"krx_kind", "naver_month"}
        or independent.get("trade_date") != "2026-10-12"
    ):
        raise UnverifiedRegularSessionPrice("전환 직전 독립 종가 근거가 없습니다")
    raw = proof.get("rows")
    if not isinstance(raw, list) or len(raw) < qs.MIN_HISTORY_ROWS:
        raise UnverifiedRegularSessionPrice("125개 이상의 완료 일봉이 필요합니다")
    rows: list[DailyPrice] = []
    seen: set[date] = set()
    for item in raw:
        if not isinstance(item, dict) or item.get("code") != code:
            raise UnverifiedRegularSessionPrice("과거 일봉의 종목이 다릅니다")
        try:
            day = date.fromisoformat(str(item["trade_date"]))
            values = {field: int(item[field]) for field in (*PRICE_FIELDS, "market_cap", "listed_shares")
                      if item.get(field) is not None}
            prices = [values[field] for field in ("open", "high", "low", "close", "volume", "trading_value")]
        except (KeyError, TypeError, ValueError) as exc:
            raise UnverifiedRegularSessionPrice("과거 일봉 값이 불완전합니다") from exc
        if (
            day in seen or day >= REGULAR_FORWARD_START
            or any(value <= 0 for value in prices)
            or values["low"] > min(values["open"], values["close"])
            or values["high"] < max(values["open"], values["close"])
            or values["high"] < values["low"]
        ):
            raise UnverifiedRegularSessionPrice("과거 일봉의 날짜·OHLC가 잘못됐습니다")
        seen.add(day)
        rows.append(DailyPrice(code=code, trade_date=day, **values))
    if [row.trade_date for row in rows] != sorted(seen) or rows[-1].trade_date != date(2026, 10, 12):
        raise UnverifiedRegularSessionPrice("전환 직전까지 이어진 정렬 일봉이 아닙니다")
    if rows[-1].close != independent.get("close"):
        raise UnverifiedRegularSessionPrice("전환 직전 종가가 독립 근거와 다릅니다")
    existing = list(db.scalars(select(DailyPrice).where(
        DailyPrice.code == code, DailyPrice.trade_date < REGULAR_FORWARD_START,
    ).order_by(DailyPrice.trade_date)))
    by_date = {row.trade_date: row for row in rows}
    matching = [
        row for row in existing
        if row.trade_date <= date(2026, 9, 11)
        and row.trade_date in by_date
        and all(getattr(row, field) == getattr(by_date[row.trade_date], field)
                for field in ("open", "high", "low", "close", "volume"))
    ]
    if len(matching) < 20:
        raise UnverifiedRegularSessionPrice("기존 완료 일봉과 20일 이상 교차 검증되지 않았습니다")
    key = f"{REGULAR_FORWARD_VERSION}:prices:{code}"
    if _load(db, key) is not None:
        raise UnverifiedRegularSessionPrice("전환 가격 기준선이 이미 고정돼 있습니다")
    frozen = [{
        "code": code, "trade_date": row.trade_date,
        **{field: getattr(row, field) for field in (*PRICE_FIELDS, "market_cap", "listed_shares")},
    } for row in rows]
    report = {
        "code": code, "state": "verified", "warmup_rows": len(rows),
        "existing_matching_rows": len(matching),
        "history_overwrite": False, "signal_publication": False,
        "notifications_sent": 0, "persisted": persist,
    }
    savepoint = db.begin_nested() if not persist else None
    try:
        _freeze(db, key, frozen)
        checked = frozen_legacy_price_rows(db, code, existing)
        if len(checked) != len(rows) or checked[-1].close != rows[-1].close:
            raise UnverifiedRegularSessionPrice("고정된 준비 일봉을 재검증할 수 없습니다")
        if persist:
            db.commit()
        else:
            savepoint.rollback()
            db.expire_all()
    except Exception:
        db.rollback()
        raise
    return report
