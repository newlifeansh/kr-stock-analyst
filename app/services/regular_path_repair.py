"""Append independent minute proof before sealing an unfinalized historical path."""
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
    _json,
    load_regular_session_evidence,
    regular_session_evidence,
    store_regular_session_evidence,
)


def corroborate_unfinalized_regular_path(
    db: Session, code: str, day: date, *, observed_at: datetime,
    persist: bool = False, source_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Repair one exact dated path; never rewrite a publication or send a push."""
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
    if not isinstance(prior, list) or not prior:
        raise UnverifiedRegularSessionPrice("이전 경로가 불완전합니다")
    old = load_regular_session_evidence(db, code, day, allow_bounded=True)
    if old.get("full_minute_path_proof") is not None:
        raise UnverifiedRegularSessionPrice("이미 독립 분봉 보정 근거가 저장됐습니다")
    if source_proof is None:
        from app.collectors.briefing import fetch_regular_path_corroboration

        source_proof = fetch_regular_path_corroboration(code, day, old["regular_rows"])
    proof = {
        **source_proof,
        "prior_path": prior,
        "prior_path_hash": sha256(_json(prior).encode()).hexdigest(),
    }
    enhanced = regular_session_evidence(
        code, day, old["raw_rows"], observed_at=observed_at,
        preopen_baseline=old.get("preopen_baseline"),
        closing_auction_evidence=old.get("closing_auction_evidence"),
        minute_coverage_evidence=old.get("minute_coverage_evidence"),
        bucket_open_proof=old.get("bucket_open_proof"),
        full_minute_path_proof=proof,
    )
    if enhanced["state"] not in {"ready", "bounded"}:
        raise UnverifiedRegularSessionPrice(str(enhanced.get("reason") or "독립 분봉 검증 실패"))
    if enhanced["prices"] != old["prices"] or enhanced["turnover_bounds"] != old["turnover_bounds"]:
        raise UnverifiedRegularSessionPrice("기존 정규장 일봉 범위를 변경할 수 없습니다")
    use_cancelled_terminal_revision = proof.get("yahoo") is None
    report = {
        "code": code, "trade_date": day.isoformat(), "state": "verified",
        "coverage_basis": enhanced["coverage_basis"],
        "prior_path_hash": proof["prior_path_hash"],
        "corrected_path_hash": sha256(_json(enhanced["regular_rows"]).encode()).hexdigest(),
        "history_overwrite": False, "signal_publication": False, "notifications_sent": 0,
        "persisted": persist,
    }
    savepoint = db.begin_nested() if not persist else None
    try:
        if persist:
            store_regular_session_evidence(db, enhanced, observed_at=observed_at)
        qs._store_verified_intraday_path(
            db, code, day, enhanced["regular_rows"], observed_at=observed_at,
            is_final=True, expected_prior_path_hash=proof["prior_path_hash"],
            independently_corroborated_terminal_revision=use_cancelled_terminal_revision,
        )
        db.flush()
        if persist:
            selected = load_regular_session_evidence(db, code, day, allow_bounded=True)
            if selected["coverage_basis"] != enhanced["coverage_basis"]:
                raise UnverifiedRegularSessionPrice("보정 근거가 선택되지 않았습니다")
            db.commit()
        else:
            savepoint.rollback()
            db.expire_all()
    except Exception:
        db.rollback()
        raise
    return report
