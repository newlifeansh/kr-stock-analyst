"""Forward-only KR preliminary capture -> completed-minute buy confirmation.

Only the canonical publisher observes candidates. Reads replay persisted orders;
historical candles can never manufacture a first observation or an entry.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QuantSignalObservedEntry

KST = ZoneInfo("Asia/Seoul")
POLICY_VERSION = "same-session-observed-entry-v1"
EXECUTION_MODEL = "observed-candidate-minute-close-v1"
EFFECTIVE_DATE = date(2026, 10, 21)
MAX_AGE_SECONDS = 180
NEXT_CHECK = "예비 포착 이후 완료된 정규장 1분봉에서 매수 조건을 확인합니다. 미충족 후보는 당일 만료됩니다."


def timestamp(value: Any) -> datetime | None:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(KST) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def _encoded(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: dict) -> str:
    return hashlib.sha256(_encoded(value).encode()).hexdigest()


def minute_signature(bar: Any) -> list[float]:
    return [float(getattr(bar, key)) for key in ("open", "high", "low", "close", "volume")]


def load_records(db: Session, code: str, now: datetime) -> dict[date, dict]:
    records = {}
    for row in db.scalars(select(QuantSignalObservedEntry).where(
        QuantSignalObservedEntry.stock_code == code,
        QuantSignalObservedEntry.trade_date <= now.date(),
        QuantSignalObservedEntry.policy_version == POLICY_VERSION,
    )):
        payload = json.loads(row.payload)
        if row.status == "confirmed":
            order = payload.get("order") or {}
            if payload.get("order_hash") != _digest(order):
                from app.services.quant_signals import UnverifiedIntradayPathError
                raise UnverifiedIntradayPathError("장중 관측 진입 기록의 무결성을 확인할 수 없습니다")
        if row.status == "watching" and (
            row.trade_date < now.date() or now.time() >= time(15, 30)
        ):
            # Expiry is a read projection too; no viewer needs write permission.
            payload = {**payload, "status": "expired"}
        records[row.trade_date] = payload
    return records


def public_state(record: dict | None) -> dict | None:
    if not record:
        return None
    return {key: record.get(key) for key in (
        "candidate_id", "policy_version", "status", "first_observed_at",
        "published_at", "confirmed_at", "decision_minute_at", "expires_at",
    )}


def mark_published(db: Session, items: list, now: datetime) -> None:
    """Arm only candidates present in a successfully saved canonical publication."""
    for item in items:
        state = item.get("observed_entry") or {}
        if state.get("status") != "watching" or not item.get("is_preliminary"):
            continue
        row = db.scalar(select(QuantSignalObservedEntry).where(
            QuantSignalObservedEntry.stock_code == item.get("code"),
            QuantSignalObservedEntry.trade_date == now.date(),
        ).with_for_update())
        if row is None or row.status != "watching":
            continue
        record = json.loads(row.payload)
        if record.get("candidate_id") != state.get("candidate_id") or record.get("published_at"):
            continue
        record["published_at"] = now.isoformat()
        row.payload = _encoded(record)
        row.updated_at = now.astimezone(timezone.utc).replace(tzinfo=None)
    db.flush()


def project_current(payload: dict, record: dict | None) -> None:
    current = payload.get("current")
    if not isinstance(current, dict) or not record:
        return
    current["observed_entry"] = public_state(record)
    if current.get("position_open"):
        return
    if record["status"] == "watching":
        current.update(action="entry_watch", label="예비 포착 · 장중 조건 대기",
                       live_observation=True, next_confirmation=NEXT_CHECK)
        current["lifecycle"].update(state="entry_watch", label=current["label"], stage_index=1)
    elif record["status"] in {"expired", "cancelled"}:
        current.update(action="waiting", label="예비 포착 만료" if record["status"] == "expired" else "예비 포착 해제",
                       next_confirmation="다음 거래일 새 후보를 확인합니다.")
        current["lifecycle"].update(state="waiting", label=current["label"], stage_index=0)


def observe(
    db: Session, code: str, *, now: datetime, bars: list, minutes: list,
    minute_at: datetime, available: bool, last_exit_index: int | None,
    guard: dict | None, evidence: dict | None, universe_eligible: bool,
    universe_rank: int | None = None,
) -> dict | None:
    """Observe only the newest verified CLOSED minute, never replay missed alerts."""
    from app.services import quant_signals as qs
    from app.services.market_calendar import (
        is_korea_market_session_date, latest_completed_korea_market_session_date,
    )

    if (
        now.tzinfo is None or minute_at.tzinfo is None or not bars or not minutes
        or now.date() < EFFECTIVE_DATE or minute_at.date() != now.date()
        or not is_korea_market_session_date(now.date(), now)
        or not time(9, 0) <= now.time() < time(15, 30)
        or not 60 <= (now - minute_at).total_seconds() <= MAX_AGE_SECONDS
        or bars[-1].trade_date != latest_completed_korea_market_session_date(now)
    ):
        return None
    row = db.scalar(select(QuantSignalObservedEntry).where(
        QuantSignalObservedEntry.stock_code == code,
        QuantSignalObservedEntry.trade_date == now.date(),
    ).with_for_update())
    record = json.loads(row.payload) if row else None
    if row and row.policy_version != POLICY_VERSION:
        return None
    if record and record["status"] != "watching":
        return record
    forming = qs.PriceBar(
        trade_date=now.date(), open=minutes[0].open,
        high=max(bar.high for bar in minutes), low=min(bar.low for bar in minutes),
        close=minutes[-1].close, volume=sum(bar.volume for bar in minutes),
        trading_value=sum(bar.trading_value or bar.close * bar.volume for bar in minutes),
    )
    decision_bars = [*bars, forming]
    indicators = qs._indicator_rows(decision_bars)
    indicator = indicators[-1]
    recent = indicators[-qs.CHASE_MOMENTUM_LOOKBACK_BARS:]
    setup = qs._entry_setup_kind(forming, indicator, recent_indicators=recent)
    risk_blocked = (
        not universe_eligible or not available
        or qs.entry_safety_guard_active(guard, now.date())
        or not qs._reentry_entry_allowed(decision_bars, indicators, len(decision_bars) - 1, last_exit_index)
        or bool(qs._chase_entry_veto_reason(forming, indicator, recent_indicators=recent))
        or bool((evidence or {}).get("vetoes"))
    )
    if row is None:
        if risk_blocked or not (setup or qs._pre_entry_signal(forming, indicator, recent_indicators=recent)):
            return None
        record = {
            "candidate_id": f"{POLICY_VERSION}:{code}:{now.date()}",
            "policy_version": POLICY_VERSION, "status": "watching",
            "first_observed_at": now.isoformat(),
            "expires_at": datetime.combine(now.date(), time(15, 30), KST).isoformat(),
            "signal_price": forming.close,
            "observation_universe_rank": universe_rank,
            "trigger_price": max(forming.close, float(indicator.get("prior_high") or forming.close)),
        }
        # Concurrent publishers must keep the first observer's identity and clock.
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        db.execute(insert(QuantSignalObservedEntry).values(
            stock_code=code, trade_date=now.date(), policy_version=POLICY_VERSION,
            status="watching", payload=_encoded(record),
            updated_at=now.astimezone(timezone.utc).replace(tzinfo=None),
        ).on_conflict_do_nothing(index_elements=["stock_code", "trade_date"]))
        db.flush()
        row = db.get(QuantSignalObservedEntry, (code, now.date()), populate_existing=True)
        return json.loads(row.payload)
    if risk_blocked:
        record.update(status="cancelled", cancelled_at=now.isoformat())
    else:
        published_at = timestamp(record.get("published_at"))
        if published_at is None:
            return record
        first_at = max(timestamp(record["first_observed_at"]), published_at)
        # Exclude the minute containing capture, including its pre-capture trades.
        first_eligible = first_at.replace(second=0, microsecond=0) + timedelta(minutes=1)
        evidence_at = timestamp((evidence or {}).get("generated_at"))
        evidence_valid = bool(
            evidence_at and evidence_at <= now
            and (now - evidence_at).total_seconds() <= MAX_AGE_SECONDS
            and str((evidence or {}).get("signal_date")) == bars[-1].trade_date.isoformat()
            and (evidence or {}).get("stock_code") == code
        )
        confirmation = qs.entry_confirmation_decision(evidence, setup or "trend_continuation", signal_date=bars[-1].trade_date)
        if (
            minute_at >= first_eligible and setup and evidence_valid and confirmation["allowed"]
            and forming.close >= record["trigger_price"]
            and qs._entry_execution_allowed(forming.close, {
                "signal_price": record["signal_price"], "atr": indicator["atr"],
            })
        ):
            order = {
                "side": "buy", "signal_date": now.date().isoformat(),
                "signal_at": now.isoformat(), "score": indicator["score"],
                "reason": "예비 포착 이후 완료 분봉에서 매수 조건·독립 근거 확인",
                "entry_setup": setup, "entry_confirmation": confirmation,
                "atr": indicator["atr"], "execution_cost": qs._execution_cost(indicator),
                "price": forming.close, "minute_index": len(minutes) - 1,
                "minute_signature": minute_signature(minutes[-1]),
                "candidate_id": record["candidate_id"], "entry_policy_version": POLICY_VERSION,
                "observation_universe_rank": universe_rank,
                "first_observed_at": record["first_observed_at"],
                "confirmed_at": now.isoformat(), "decision_minute_at": minute_at.isoformat(),
            }
            record.update(status="confirmed", order=order, order_hash=_digest(order),
                          evidence=deepcopy(evidence), confirmed_at=now.isoformat(),
                          decision_minute_at=minute_at.isoformat())
    row.status, row.payload = record["status"], _encoded(record)
    row.updated_at = now.astimezone(timezone.utc).replace(tzinfo=None)
    db.flush()
    return record


def replay_order(record: dict | None, minutes: list | None, *, forming: bool) -> dict | None:
    if not record or record.get("status") != "confirmed":
        return None
    from app.services.quant_signals import UnverifiedIntradayPathError
    if not minutes and forming:
        return None  # First projection nominates a fresh chart fetch only.
    order = deepcopy(record["order"])
    index = int(order["minute_index"])
    if (
        record.get("order_hash") != _digest(order)
        or not minutes or not 0 <= index < len(minutes)
        or minute_signature(minutes[index]) != order["minute_signature"]
    ):
        raise UnverifiedIntradayPathError("저장된 장중 관측 진입의 완료 분봉을 재검증할 수 없습니다")
    order["signal_date"] = date.fromisoformat(order["signal_date"])
    order["signal_at"] = timestamp(order["signal_at"])
    return order
