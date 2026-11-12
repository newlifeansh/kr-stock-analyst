"""Seal a confirmed entry's later placeholder with independent minute evidence."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QuantSignalIntradayPathSnapshot
from app.services import quant_signals as qs
from app.services.regular_session_prices import (
    UnverifiedRegularSessionPrice,
    _integer,
    _json,
    load_regular_session_evidence,
)


def corroborate_confirmed_placeholder_path(
    db: Session, code: str, day: date, *, observed_at: datetime,
    source_proof: dict[str, Any], persist: bool = False,
) -> dict[str, Any]:
    """Replace one terminal zero-volume placeholder; preserve confirmed entry."""
    if observed_at.tzinfo is None or day >= observed_at.astimezone(qs.KST).date():
        raise UnverifiedRegularSessionPrice("완료된 과거 거래일만 재검증할 수 있습니다")
    snapshot = (
        db.scalar(select(QuantSignalIntradayPathSnapshot).where(
            QuantSignalIntradayPathSnapshot.stock_code == code,
            QuantSignalIntradayPathSnapshot.trade_date == day,
        ).with_for_update())
        if persist else db.get(QuantSignalIntradayPathSnapshot, (code, day))
    )
    if snapshot is None or snapshot.is_final or snapshot.strategy_version != qs.STRATEGY_VERSION:
        raise UnverifiedRegularSessionPrice("같은 전략 버전의 미봉인 경로가 필요합니다")
    try:
        prior = json.loads(snapshot.payload)
    except (TypeError, ValueError) as exc:
        raise UnverifiedRegularSessionPrice("이전 경로를 읽을 수 없습니다") from exc
    if not isinstance(prior, list) or len(prior) < 2:
        raise UnverifiedRegularSessionPrice("이전 경로가 불완전합니다")
    regular = load_regular_session_evidence(db, code, day, allow_bounded=True)
    current = regular["regular_rows"]
    naver = source_proof.get("naver") or {}
    yahoo = source_proof.get("yahoo") or {}
    target = day.strftime("%Y%m%d")
    if (
        source_proof.get("trade_date") != target
        or naver.get("source") != "naver_fchart_minute"
        or naver.get("code") != code
        or naver.get("trade_date") != target
        or naver.get("timeframe") != "minute"
        or not isinstance(naver.get("rows"), list)
        or len(naver["rows"]) != len(current)
        or yahoo.get("ticker") not in {f"{code}.KS", f"{code}.KQ"}
        or yahoo.get("trade_date") != target
        or yahoo.get("exchange_timezone") != "Asia/Seoul"
        or yahoo.get("interval") != "1m"
        or yahoo.get("trade_time") != prior[-1].get("trade_time")
    ):
        raise UnverifiedRegularSessionPrice("독립 분봉 근거의 종목·날짜·범위가 다릅니다")
    cumulative = 0
    for minute, independent in zip(current, naver["rows"]):
        cumulative += _integer(minute["volume"], positive=True)
        if (
            minute["trade_time"] != independent.get("trade_time")
            or _integer(minute["price"], positive=True)
            != _integer(independent.get("close"), positive=True)
            or cumulative != _integer(independent.get("cumulative_volume"), positive=True)
        ):
            raise UnverifiedRegularSessionPrice("독립 종가·누적 거래량 경로가 KIS와 충돌합니다")
    terminal = next(
        (minute for minute in current if minute["trade_time"] == prior[-1]["trade_time"]),
        None,
    )
    if terminal is None or any(
        _integer(terminal[field], positive=True)
        != _integer(yahoo.get("close" if field == "price" else field), positive=True)
        for field in ("open", "high", "low", "price")
    ):
        raise UnverifiedRegularSessionPrice("확정 후 임시 봉의 실제 OHLC를 제3원천으로 확인하지 못했습니다")
    prior_hash = sha256(_json(prior).encode()).hexdigest()
    report = {
        "code": code, "trade_date": day.isoformat(), "state": "verified",
        "corrected_minute": prior[-1]["trade_time"],
        "prior_path_hash": prior_hash,
        "corrected_path_hash": sha256(_json(current).encode()).hexdigest(),
        "history_overwrite": False, "signal_publication": False,
        "notifications_sent": 0, "persisted": persist,
    }
    savepoint = db.begin_nested() if not persist else None
    try:
        qs._store_verified_intraday_path(
            db, code, day, current, observed_at=observed_at, is_final=True,
            expected_prior_path_hash=prior_hash,
            independently_corroborated_confirmed_placeholder_revision=True,
        )
        db.flush()
        if persist:
            db.commit()
        else:
            savepoint.rollback()
            db.expire_all()
    except Exception:
        db.rollback()
        raise
    return report
