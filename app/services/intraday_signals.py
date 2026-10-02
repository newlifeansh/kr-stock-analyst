"""Durable, non-repainting intraday *signals*, never brokerage orders.

Versioned separately from daily replay. Only the latest completed five-minute
window can open a position; exits use the latest fresh observed price, never a
retrospective high/low fill. Shadow and alert ledgers are strictly separate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy.exc import IntegrityError

from app.db import Base

VERSION = "intraday-top100-v1-rc1"
UTC = timezone.utc


@lru_cache(maxsize=1)
def implementation_digest() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for relative in ("services/intraday_signals.py", "services/intraday_monitor.py", "static/intraday-alerts.html"):
        digest.update(relative.encode())
        digest.update((root / relative).read_bytes())
    return digest.hexdigest()


class IntradayState(Base):
    __tablename__ = "intraday_signal_state"
    key: Mapped[str] = mapped_column(String(180), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class IntradayEvent(Base):
    __tablename__ = "intraday_signal_event"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market: Mapped[str] = mapped_column(String(2), index=True)
    mode: Mapped[str] = mapped_column(String(10), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class IntradayMinute(Base):
    __tablename__ = "intraday_signal_minute"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    market: Mapped[str] = mapped_column(String(2), index=True)
    code: Mapped[str] = mapped_column(String(16), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timezone required")
    return value.astimezone(UTC)


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@dataclass(frozen=True)
class Minute:
    start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def valid(self) -> bool:
        values = (self.open, self.high, self.low, self.close, self.volume)
        return (self.start.tzinfo is not None and all(math.isfinite(x) for x in values)
                and min(values[:4]) > 0 and self.volume >= 0
                and self.low <= min(self.open, self.close)
                and self.high >= max(self.open, self.close))


def decide(state: dict, *, market: str, code: str, name: str, mode: str,
           minutes: list[Minute], context: dict, now: datetime,
           session_open: datetime, session_close: datetime,
           in_universe: bool, max_age: int = 90) -> tuple[dict, dict | None, str]:
    """Pure transition function. A confirmed event can never be withdrawn."""
    now, session_open, session_close = map(utc, (now, session_open, session_close))
    state = dict(state)
    if mode not in {"shadow", "alerts"} or market not in {"kr", "us"}:
        return state, None, "disabled"
    if not session_open <= now < session_close:
        return state, None, "closed"
    if not minutes or any(not row.valid() for row in minutes):
        return state, None, "invalid_bars"
    by_time = {}
    for row in minutes:
        stamp = utc(row.start)
        if stamp > now:
            return state, None, "future_bars"
        if stamp in by_time and by_time[stamp] != row:
            return state, None, "conflicting_bars"
        if session_open <= stamp < session_close:
            by_time[stamp] = row
    if not by_time:
        return state, None, "wrong_session"
    latest_at = max(by_time)
    if (now - latest_at).total_seconds() > max_age:
        return state, None, "stale"
    price = by_time[latest_at].close
    previous_observation = state.get("observed_at")
    if previous_observation and latest_at < datetime.fromisoformat(previous_observation):
        return state, None, "out_of_order"
    state["observed_at"] = latest_at.isoformat()
    side, reason, fraction = None, None, 0.0
    remaining = float(state.get("remaining", 0))
    if remaining:
        entry = float(state["entry_price"])
        if price <= float(state["stop_price"]):
            side, reason, fraction = "sell", "protective_stop", remaining
        elif price >= entry * 1.05:
            side, reason, fraction = "sell", "target_5", remaining
        elif not state.get("partial") and price >= entry * 1.03:
            side, reason, fraction = "partial_sell", "target_3", 0.5
        if side:
            state["remaining"] = max(0.0, remaining - fraction)
            state["proceeds"] = float(state.get("proceeds", 0)) + fraction * price
            if side == "partial_sell":
                state["partial"] = True
                # Explicit model cost, not a claim about the user's broker fee.
                state["stop_price"] = max(float(state["stop_price"]), entry * 1.004)
            else:
                state["exit_session"] = session_open.isoformat()
    else:
        if not in_universe:
            return state, None, "outside_top100"
        # Require a fresh new session after an exit; no oscillating same-day
        # buy/sell loop. This is a conservative RC policy, not the daily policy.
        if state.get("exit_session") == session_open.isoformat():
            return state, None, "reentry_blocked"
        if not context.get("ready") or not context.get("evidence_allowed"):
            return state, None, "evidence_unavailable"
        if context.get("session_open") != session_open.isoformat():
            return state, None, "stale_context"
        required = ("score", "atr_percent", "momentum5", "volume_ratio",
                    "average_trading_value", "ema20", "ema60", "previous_close")
        try:
            if not all(math.isfinite(float(context[k])) for k in required):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return state, None, "invalid_context"
        if (context["score"] < (64 if market == "kr" else 65)
                or not 0 < context["atr_percent"] <= (0.045 if market == "kr" else 0.055)
                or context["momentum5"] < 0.005 or context["momentum5"] > 0.10
                or context["volume_ratio"] < 1.0
                or context["average_trading_value"] < (5e9 if market == "kr" else 5e7)):
            return state, None, "quality_filter"
        # Align to the exchange open, not UTC clock or a forming 5m candle.
        elapsed = int((now - session_open).total_seconds() // 300)
        end = session_open + timedelta(minutes=5 * elapsed)
        if elapsed < 4 or now - end > timedelta(seconds=max_age):
            return state, None, "await_completed_bar"
        starts = [end - timedelta(minutes=i) for i in range(20, 0, -1)]
        if not all(stamp in by_time for stamp in starts):
            return state, None, "minute_gap"
        rows = [by_time[stamp] for stamp in starts]
        if sum(r.volume for r in rows) <= 0:
            return state, None, "no_volume"
        # Rolling 20-minute volume-weighted typical price, explicitly not
        # falsely labelled full-session VWAP or real-time institutional flow.
        vwap = sum((r.high + r.low + r.close) / 3 * r.volume for r in rows) / sum(r.volume for r in rows)
        previous, current = rows[-10:-5], rows[-5:]
        trigger_close = current[-1].close
        previous_close = previous[-1].close
        reclaim = previous_close <= vwap < trigger_close
        retest = min(r.low for r in current) <= vwap and trigger_close > vwap and trigger_close > previous_close
        if not (reclaim or retest):
            return state, None, "await_reclaim"
        if (state.get("entry_bar") == end.isoformat()
                or trigger_close <= max(context["ema20"], context["ema60"])
                or price <= vwap or price > vwap * 1.01
                or abs(price / context["previous_close"] - 1) > 0.03
                or price > trigger_close * 1.005):
            return state, None, "chase_guard"
        risk = min(0.04, max(0.01, context["atr_percent"] * 1.75))
        state.update(entry_price=price, remaining=1.0, partial=False,
                     stop_price=price * (1 - risk), proceeds=0.0,
                     entry_bar=end.isoformat(), entry_at=now.isoformat())
        side, reason, fraction = "buy", "completed_5m_reclaim", 1.0
    if side is None:
        return state, None, "holding"
    sequence = int(state.get("sequence", 0)) + 1
    state["sequence"] = sequence
    identity = f"{VERSION}:{mode}:{market}:{code}:{sequence}:{state['entry_at']}"
    event_id = hashlib.sha256(identity.encode()).hexdigest()
    event = dict(event_id=event_id, strategy_version=VERSION, mode=mode,
                 market=market, code=code, name=name, side=side, reason=reason,
                 occurred_at=now.isoformat(), observed_at=latest_at.isoformat(),
                 reference_price=price, entry_price=state["entry_price"],
                 fraction=fraction, remaining=state["remaining"],
                 stop_price=state["stop_price"], confirmation_bar=state["entry_bar"],
                 status="confirmed", execution="signal_only_not_broker_fill",
                 currency="KRW" if market == "kr" else "USD")
    return state, event, "confirmed"


def record(db: Session, *, market: str, code: str, mode: str, member=None, **kwargs) -> str:
    key = f"{VERSION}:{mode}:{market}:{code}"
    row = db.scalar(select(IntradayState).where(IntradayState.key == key).with_for_update())
    if row is None:
        try:
            with db.begin_nested():
                row = IntradayState(key=key, payload="{}", updated_at=datetime.utcnow())
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.scalar(select(IntradayState).where(IntradayState.key == key).with_for_update())
    state, event, status = decide(json.loads(row.payload), market=market,
                                  code=code, mode=mode, **kwargs)
    if member is not None:
        state["member"] = member
    row.payload, row.updated_at = encode(state), utc(kwargs["now"]).replace(tzinfo=None)
    if event:
        db.add(IntradayEvent(event_id=event["event_id"], market=market, mode=mode,
                            occurred_at=row.updated_at, payload=encode(event)))
    db.commit()
    return status


def feed(db: Session, market: str, mode: str, limit: int = 100) -> dict:
    state = db.get(IntradayState, f"monitor:{market}")
    items = db.scalars(select(IntradayEvent).where(
        IntradayEvent.market == market, IntradayEvent.mode == mode
    ).order_by(IntradayEvent.occurred_at.desc()).limit(limit))
    monitor = json.loads(state.payload) if state else {"state": "not_started"}
    if state and monitor.get("state") in {"monitoring", "degraded"}:
        if datetime.utcnow() - state.updated_at > timedelta(minutes=3):
            monitor = dict(monitor, state="stale")
    if mode == "off":
        monitor = dict(monitor, state="disabled")
    return dict(strategy_version=VERSION, market=market, mode=mode,
                implementation_digest=implementation_digest(),
                monitor=monitor,
                items=[json.loads(item.payload) for item in items],
                execution="signal_only_not_broker_fill")
