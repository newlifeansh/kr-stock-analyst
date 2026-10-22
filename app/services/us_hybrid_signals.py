"""Forward-only US hybrid signals. This module never submits broker orders.

Completed-close setups and observed regular-session minutes are distinct inputs.
Only newly observed, finished minutes can change the durable model ledger. A
restart never replays missed profit touches as a freshly executable signal.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import math
from typing import Any, Callable

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import MarketQuantSignalSnapshot
from app.services.us_market_calendar import us_signal_session_state

US_HYBRID_VERSION = "position-lifecycle-us-v3-hybrid1"
LEGACY_US_HYBRID_EXECUTION_MODEL = "completed-close-fresh-minute-confirmation-v1"
US_HYBRID_EXECUTION_MODEL = "same-session-observed-entry-us-v1"
US_HYBRID_START = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
US_HYBRID_KEY = "us-hybrid-forward-v1"
US_HYBRID_MAX_AGE_SECONDS = 90
US_HYBRID_POLL_SECONDS = 30
US_PRELIMINARY_VOLUME_RATIO = 0.75
US_CONFIRMED_VOLUME_RATIO = 1.0
LABELS = {
    "entry_pending": "장중 조건 감시", "entry_watch": "예비 포착·완료 분봉 대기",
    "entered": "전략 매수 확정",
    "holding": "전략 보유", "partially_exited": "1차 수익확정",
    "exited": "전략 전량 매도 확정", "no_signal": "관망",
}
HYBRID_NOTICE = (
    "전일 완료 일봉 근거를 바탕으로 정규장 장중 예비 포착을 새로 생성하고, "
    "포착 이후의 신선한 완료 1분봉에서 매수·매도를 확인합니다. "
    "+3%에서 원래 비중의 50%, +5%에서 잔여 비중을 매도하며 초기 손실 기준은 -4%입니다. "
    "관측·전송 지연이나 갭으로 해당 가격의 체결을 보장하지 않습니다. 실제 계좌 주문이 아닌 모델 신호입니다."
)


def _utc(value: Any) -> datetime | None:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _json(value: Any) -> str:
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(payload: dict) -> str:
    return sha256(_json({k: v for k, v in payload.items() if k != "checksum"}).encode()).hexdigest()


def read_us_hybrid_state(db: Session) -> dict | None:
    row = db.get(MarketQuantSignalSnapshot, US_HYBRID_KEY)
    if row is None:
        return None
    payload = json.loads(row.payload)
    if (payload.get("version") != US_HYBRID_VERSION
            or payload.get("checksum") != _digest(payload)):
        raise ValueError("US hybrid ledger integrity check failed")
    return payload


def build_close_setup(
    member: dict,
    decision: dict,
    bar: Any,
    history: list[Any] | None = None,
) -> dict:
    """Store a raw-price trigger alongside split-adjusted technical evidence."""
    volume = _number(getattr(bar, "volume", None)) if bar is not None else None
    notional = _number(getattr(bar, "trading_value", None)) if bar is not None else None
    adjusted_close = _number(getattr(bar, "close", None)) if bar is not None else None
    raw_close = notional / volume if notional and volume and volume > 0 else None
    atr = _number((decision.get("technical") or {}).get("atr"))
    raw_atr = atr * raw_close / adjusted_close if atr and raw_close and adjusted_close else None
    completed = list(history or ([] if bar is None else [bar]))
    recent_volumes = [
        value
        for item in completed[-20:]
        if (value := _number(getattr(item, "volume", None))) is not None and value > 0
    ]
    average_daily_volume = (
        sum(recent_volumes) / len(recent_volumes) if recent_volumes else None
    )
    action = str(decision.get("action") or "no_signal")
    return {
        "code": member["code"], "name": member["name"], "market": member["market"],
        "market_cap_rank": member.get("market_cap_rank"),
        "signal_date": str(decision.get("signal_date") or ""),
        "eligible": bool(action == "entry_pending" and raw_atr and raw_close),
        "daily_watch": bool(action in {"entry_watch", "entry_pending"}),
        "reference_close": raw_close, "atr": raw_atr,
        "average_daily_volume": average_daily_volume,
        "close_exit": bool(adjusted_close and (decision.get("technical") or {}).get("ema20")
                           and adjusted_close < float(decision["technical"]["ema20"])),
    }


def _supportive_public_reasons(feed: dict, code: str) -> bool:
    item = next(
        (
            row
            for row in feed.get("public_member_signals") or []
            if row.get("code") == code
        ),
        {},
    )
    reasons = {
        str(reason.get("key") or ""): reason
        for reason in item.get("public_reasons") or []
        if isinstance(reason, dict)
    }
    return all(
        reasons.get(key, {}).get("available") is True
        and str(reasons[key].get("state") or "").lower()
        in {"positive", "supportive"}
        for key in ("trend_20d", "trend_60d", "flow")
    )


def _intraday_volume_participation(
    points: list[dict],
    setup: dict,
    *,
    session: Any,
) -> dict[str, Any]:
    """Use elapsed-session volume until same-minute US history is persisted."""

    average_daily_volume = _number(setup.get("average_daily_volume")) or 0.0
    current_volume = sum(float(point["volume"]) for point in points)
    latest_at = _utc(points[-1]["at"])
    session_minutes = max(
        1.0,
        (session.close_at - session.open_at).total_seconds() / 60.0,
    )
    elapsed_minutes = max(
        1.0,
        min(
            session_minutes,
            ((latest_at - session.open_at).total_seconds() / 60.0) + 1.0,
        ),
    )
    expected_volume = average_daily_volume * elapsed_minutes / session_minutes
    ratio = current_volume / expected_volume if expected_volume > 0 else 0.0
    return {
        "basis": "elapsed_session_fallback",
        "ratio": round(ratio, 6),
        "current_cumulative_volume": round(current_volume, 3),
        "expected_cumulative_volume": round(expected_volume, 3),
        "sample_count": 0,
        "as_of_minute": points[-1]["at"],
    }


def verified_minutes(raw: dict, code: str, now: datetime) -> tuple[list[dict], str]:
    """No repaired OHLC, reception-time substitution, extended hours or forming bar."""
    state = us_signal_session_state(now)
    session = state["current_session"]
    if not state["is_regular"] or session is None:
        return [], "market_closed"
    meta = raw.get("meta") or {}
    if (str(meta.get("symbol") or "").replace("-", ".").upper() != code.replace("-", ".").upper()
            or meta.get("currency") != "USD"
            or str(meta.get("instrumentType") or "").upper() not in {"EQUITY", "ETF"}):
        return [], "source_identity_invalid"
    delay = _number(meta.get("exchangeDataDelayedBy"))
    if delay is not None and delay > 0:
        return [], "provider_delayed"
    quote = ((raw.get("indicators") or {}).get("quote") or [{}])[0]
    points: list[dict] = []
    seen: set[int] = set()
    previous_timestamp = -1
    last_completed_timestamp = -1
    for index, timestamp in enumerate(raw.get("timestamp") or []):
        try:
            stamp = int(timestamp)
            observed = datetime.fromtimestamp(stamp, timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            return [], "timestamp_invalid"
        if not session.open_at <= observed < session.close_at:
            continue
        # Yahoo can append a seconds-stamped, zero-volume current-price point.
        # A forming observation is never a completed minute and must not poison
        # the valid finished prefix. Finished misaligned timestamps still fail.
        if observed + timedelta(minutes=1) > now:
            continue
        if stamp in seen or stamp < previous_timestamp or stamp % 60:
            return [], "minute_order_invalid"
        seen.add(stamp)
        previous_timestamp = stamp
        last_completed_timestamp = stamp
        values = {}
        for key in ("open", "high", "low", "close", "volume"):
            series = quote.get(key) or []
            values[key] = _number(series[index]) if index < len(series) else None
        if (any(value is None or value <= 0 for value in values.values())
                or values["high"] < max(values["open"], values["close"])
                or values["low"] > min(values["open"], values["close"])):
            # A missing minute breaks the required consecutive entry pair.
            continue
        points.append({**values, "at": observed.isoformat(), "timestamp": stamp})
    if not points or points[-1]["timestamp"] != last_completed_timestamp:
        return [], "completed_minute_missing"
    latest_end = _utc(points[-1]["at"]) + timedelta(minutes=1)
    if (now - latest_end).total_seconds() > US_HYBRID_MAX_AGE_SECONDS:
        return [], "minute_stale"
    # Splits need a separately verified share/price migration, never a fake stop.
    for event in ((raw.get("events") or {}).get("splits") or {}).values():
        event_at = _number(event.get("date"))
        if event_at is not None and event_at >= session.open_at.timestamp() - 86400:
            return [], "corporate_action_review"
    return points, "fresh"


def _base_ready(feed: dict, now: datetime) -> bool:
    state = us_signal_session_state(now)
    setups = feed.get("hybrid_setups")
    return bool(
        feed.get("status") == "ready" and feed.get("data_state") == "ready"
        and feed.get("new_entries_allowed") is True
        and feed.get("snapshot_checksum") and feed.get("snapshot_id")
        and str(feed.get("universe_as_of"))[:10] == str(state["latest_completed_date"])
        and isinstance(setups, list) and len(setups) == 100
        and len({item.get("code") for item in setups}) == 100
    )


def new_us_hybrid_state(feed: dict, now: datetime) -> dict:
    if now < US_HYBRID_START or not _base_ready(feed, now):
        raise ValueError("Completed Top100 hybrid setups are not ready")
    return {
        "version": US_HYBRID_VERSION, "initialized_at": now.isoformat(),
        "updated_at": now.isoformat(), "revision": 0, "positions": {}, "events": [],
        "observations": {}, "setups": {}, "entry_candidates": {},
        "last_entry_sessions": {},
        "legacy": {
            "strategy_version": feed.get("strategy_version"),
            "snapshot_id": feed.get("snapshot_id"), "snapshot_checksum": feed.get("snapshot_checksum"),
            "frozen_at": now.isoformat(), "items": deepcopy(feed.get("items") or []),
            "performance_summary": deepcopy(feed.get("performance_summary")),
        },
    }


def advance_us_hybrid_state(state: dict, feed: dict, raw_by_code: dict, now: datetime) -> dict:
    """Pure deterministic state transition; at most one new minute per code/poll."""
    result = deepcopy(state)
    calendar = us_signal_session_state(now)
    session = calendar["current_session"]
    base_ready = _base_ready(feed, now)
    source_identity = str(feed.get("snapshot_id") or "")
    if base_ready and result.get("setup_snapshot_id") != source_identity:
        previous_setups = result["setups"]
        result["setups"] = {
            item["code"]: {**item, "armed_at": (
                previous_setups[item["code"]]["armed_at"]
                if item["code"] in previous_setups
                and previous_setups[item["code"]].get("signal_date") == item.get("signal_date")
                else now.isoformat()
            )} for item in feed["hybrid_setups"]
        }
        result["setup_snapshot_id"] = source_identity
        result["setup_date"] = str(feed.get("universe_as_of"))[:10]
    result["updated_at"] = now.isoformat()
    result["market_session"] = calendar["session"]
    result["daily_setup_ready"] = base_ready
    result["revision"] += 1
    if not calendar["is_regular"] or now < US_HYBRID_START:
        return result
    result.setdefault("entry_candidates", {})
    session_date = str(session.session_date)
    for code, raw in raw_by_code.items():
        points, quality = verified_minutes(raw, code, now)
        observation = {"state": quality, "checked_at": now.isoformat(), "session_date": session_date}
        if not points:
            candidate = result["entry_candidates"].get(code)
            if candidate and candidate.get("status") == "watching":
                candidate.update(
                    paused_at=now.isoformat(),
                    pause_reasons=[quality],
                )
            result["observations"][code] = observation
            continue
        latest = points[-1]
        latest_at = _utc(latest["at"])
        latest_end = latest_at + timedelta(minutes=1)
        # The source can repeat a previously seen completed minute after errors.
        processed_at = _utc(result.get("processed_minutes", {}).get(code))
        observation.update({"observed_at": latest["at"], "price": latest["close"],
                            "age_seconds": (now - latest_end).total_seconds(), "source": "yahoo_chart_1m"})
        result["observations"][code] = observation
        if processed_at and latest_at <= processed_at:
            continue
        result.setdefault("processed_minutes", {})[code] = latest["at"]
        if latest_at < _utc(result["initialized_at"]):
            continue
        position = result["positions"].get(code)
        setup = result["setups"].get(code) or {}
        candidate = result["entry_candidates"].get(code)
        price = latest["close"]
        side = None
        reason = ""
        fraction = 0.0
        if position and position["remaining"] > 0:
            # No same-minute buy and profit/stop inferred from unordered OHLC.
            if latest_at <= _utc(position["entry_at"]):
                continue
            gain = price / position["entry_price"] - 1.0
            # Compare quoted prices, not a binary-float percentage. Exact
            # -4%/+3%/+5% quotes can otherwise fall just outside the boundary.
            # No epsilon: a quote short of the target must never trigger early.
            quoted_price = Decimal(str(price))
            entry_price = Decimal(str(position["entry_price"]))
            stop_multiple = Decimal("0.96") if position["remaining"] == 1.0 else Decimal("1")
            if quoted_price <= entry_price * stop_multiple:
                side, fraction, reason = "sell", position["remaining"], "초기 손실 기준" if position["remaining"] == 1.0 else "잔여 비중 본전 보호"
            elif quoted_price >= entry_price * Decimal("1.05"):
                # A jump over both targets closes all at the observed price.
                side, fraction, reason = "sell", position["remaining"], "2차 수익확정"
            elif quoted_price >= entry_price * Decimal("1.03") and position["remaining"] == 1.0:
                side, fraction, reason = "partial_sell", 0.5, "1차 수익확정"
            elif base_ready and setup.get("close_exit") and setup.get("signal_date", "") > position["entry_date"]:
                side, fraction, reason = "sell", position["remaining"], "완료 종가 추세 이탈"
            if side:
                position["realized_return"] += fraction * gain * 100.0
                position["remaining"] = round(position["remaining"] - fraction, 4)
                position["last_exit_at"] = latest["at"]
                position["last_exit_price"] = price
        elif base_ready and result["last_entry_sessions"].get(code) != session_date:
            reference = _number(setup.get("reference_close"))
            atr = _number(setup.get("atr"))
            supportive = bool(
                (setup.get("daily_watch") or setup.get("eligible"))
                and _supportive_public_reasons(feed, code)
            )
            complete_from_open = points[0]["at"] == session.open_at.isoformat()
            volume = (
                _intraday_volume_participation(points, setup, session=session)
                if complete_from_open
                else None
            )
            gap = min(0.05, 1.5 * atr / reference) if reference and atr else None
            opening_ok = bool(
                reference and gap is not None
                and abs(points[0]["open"] / reference - 1.0) <= gap
            )
            price_supported = bool(
                reference and gap is not None
                and reference <= price <= reference * (1 + gap)
            )
            if candidate and candidate.get("status") == "watching":
                candidate["volume_participation"] = volume
                if not supportive:
                    candidate.update(status="cancelled", cancelled_at=now.isoformat())
                    continue
                if not complete_from_open or volume is None:
                    candidate.update(
                        paused_at=now.isoformat(),
                        pause_reasons=["completed_path_unavailable"],
                    )
                    continue
                candidate.pop("paused_at", None)
                candidate.pop("pause_reasons", None)
                captured_at = _utc(candidate.get("decision_minute_at"))
                if (
                    captured_at is not None
                    and latest_at > captured_at
                    and float(volume["ratio"]) >= US_CONFIRMED_VOLUME_RATIO
                    and opening_ok
                    and price_supported
                    and price >= float(candidate["trigger_price"])
                ):
                    position = {
                        "code": code, "name": setup["name"], "market": setup["market"],
                        "market_cap_rank": setup.get("market_cap_rank"),
                        "entry_price": price, "entry_at": latest["at"], "entry_date": session_date,
                        "signal_date": session_date, "remaining": 1.0, "realized_return": 0.0,
                        "public_reasons": next((deepcopy(item.get("public_reasons") or [])
                                                for item in feed.get("public_member_signals") or []
                                                if item.get("code") == code), []),
                    }
                    result["positions"][code] = position
                    result["last_entry_sessions"][code] = session_date
                    candidate.update(
                        status="confirmed",
                        confirmed_at=latest_end.isoformat(),
                        confirmation_minute_at=latest["at"],
                    )
                    side, fraction, reason = (
                        "buy", 1.0,
                        "장중 예비 포착 이후 완료 1분봉·거래 참여도 확인",
                    )
            elif (
                supportive
                and complete_from_open
                and volume is not None
                and float(volume["ratio"]) >= US_PRELIMINARY_VOLUME_RATIO
                and opening_ok
                and price_supported
            ):
                result["entry_candidates"][code] = {
                    "candidate_id": f"same-session-observed-entry-us-v1:{code}:{session_date}",
                    "status": "watching",
                    "first_observed_at": latest_end.isoformat(),
                    "decision_minute_at": latest["at"],
                    "trigger_price": max(reference, price),
                    "expires_at": session.close_at.isoformat(),
                    "volume_participation": volume,
                }
        if side:
            event_id = f"us-hybrid-v1:{code}:{side}:{latest['timestamp']}:{session_date}"
            action = "entered" if side == "buy" else "partially_exited" if position["remaining"] else "exited"
            event = {
                "event_id": event_id, "code": code, "name": position["name"], "side": side,
                "state_after": action, "label": LABELS[action], "reason": reason,
                "signal_date": setup.get("signal_date") or position["signal_date"],
                "execution_date": session_date, "signal_at": latest_end.isoformat(),
                "observed_at": latest["at"], "published_at": now.isoformat(),
                "price": price, "sell_fraction_original": fraction if side != "buy" else None,
                "return_rate": position["realized_return"] if not position["remaining"] else None,
                "source": "yahoo_chart_1m", "intraday_execution_verified": True,
                "intraday_order_verified": True,
                "minute_evidence": points[-2:], "strategy_version": US_HYBRID_VERSION,
                "entry_policy_version": (
                    US_HYBRID_EXECUTION_MODEL if side == "buy" else None
                ),
            }
            result["events"].append(event)
            position["last_event_id"] = event_id
    return result


def refresh_us_hybrid_signals(db: Session, *, now: datetime | None = None,
                              loader: Callable | None = None) -> dict:
    from app.services.us_market import fetch_chart_range
    from app.services.us_position_lifecycle import load_us_position_lifecycle_snapshot
    current = now or datetime.now(timezone.utc)
    if current < US_HYBRID_START:
        return {"state": "not_effective"}
    feed = load_us_position_lifecycle_snapshot(db, now=current) or {}
    state = read_us_hybrid_state(db)
    row = db.get(MarketQuantSignalSnapshot, US_HYBRID_KEY)
    old_payload = row.payload if row is not None else None
    if state is None:
        if not _base_ready(feed, current):
            return {"state": "waiting_completed_setups"}
        state = new_us_hybrid_state(feed, current)
    # Release the read transaction while the provider requests are in flight.
    db.rollback()
    codes = {code for code, value in state["positions"].items() if value["remaining"] > 0}
    if _base_ready(feed, current):
        codes.update(
            item["code"]
            for item in feed["hybrid_setups"]
            if (item.get("daily_watch") or item.get("eligible"))
            and item.get("reference_close")
            and item.get("atr")
            and item.get("average_daily_volume")
            and _supportive_public_reasons(feed, item["code"])
        )
    codes.update(
        code
        for code, candidate in state.get("entry_candidates", {}).items()
        if candidate.get("status") == "watching"
    )
    raw_by_code = {}
    if us_signal_session_state(current)["is_regular"] and codes:
        fetch = loader or (lambda code: fetch_chart_range(code, range_="1d", interval="1m", include_prepost=False, refresh=True))
        with ThreadPoolExecutor(max_workers=min(6, len(codes))) as pool:
            futures = {pool.submit(fetch, code): code for code in sorted(codes)}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    raw_by_code[code] = future.result()
                except Exception:
                    raw_by_code[code] = {}
    # Assess freshness at response completion, not at request start.
    completed_at = current if now is not None else datetime.now(timezone.utc)
    updated = advance_us_hybrid_state(state, feed, raw_by_code, completed_at)
    updated["checksum"] = _digest(updated)
    serialized = _json(updated)
    stamp = completed_at.replace(tzinfo=None)
    if old_payload is None:
        db.add(MarketQuantSignalSnapshot(cache_key=US_HYBRID_KEY, payload=serialized, generated_at=stamp))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {"state": "concurrent_publication"}
    else:
        changed = db.execute(update(MarketQuantSignalSnapshot).where(
            MarketQuantSignalSnapshot.cache_key == US_HYBRID_KEY,
            MarketQuantSignalSnapshot.payload == old_payload,
        ).values(payload=serialized, generated_at=stamp))
        if changed.rowcount != 1:
            db.rollback()
            return {"state": "concurrent_publication"}
        db.commit()
    return {"state": "ready", "revision": updated["revision"], "monitored_count": len(codes),
            "fresh_count": sum(item.get("state") == "fresh" for item in updated["observations"].values())}


def project_us_hybrid_feed(db: Session, feed: dict, *, now: datetime | None = None) -> dict:
    from app.services.us_position_lifecycle import build_us_signal_performance_summary
    current = now or datetime.now(timezone.utc)
    if current < US_HYBRID_START:
        return feed
    state = read_us_hybrid_state(db)
    result = deepcopy(feed)
    result.pop("hybrid_setups", None)
    result.update({"strategy_version": US_HYBRID_VERSION, "rollout_mode": "hybrid_forward",
                   "execution_enabled": False, "signal_execution_enabled": True,
                   "lifecycle_replay_version": US_HYBRID_EXECUTION_MODEL,
                   "execution_model": US_HYBRID_EXECUTION_MODEL, "methodology": [HYBRID_NOTICE],
                   "hybrid_notice": HYBRID_NOTICE, "items": [], "preliminary_history": []})
    if state is None:
        result.update({"status": "preparing", "data_state": "preparing", "new_entries_allowed": False,
                       "hybrid_status": "waiting_completed_setups", "confirmed_count": 0,
                       "preliminary_count": 0, "entry_pending_count": 0, "signal_execution_enabled": False})
        return result
    base_ready = _base_ready(feed, current)
    calendar = us_signal_session_state(current)
    updated_at = _utc(state["updated_at"])
    worker_fresh = bool(updated_at and 0 <= (current - updated_at).total_seconds() <= 150)
    result.update({
        "status": "ready", "data_state": "ready",
        "daily_setup_data_state": feed.get("data_state"),
        "as_of": state["updated_at"], "snapshot_generated_at": state["updated_at"],
        "snapshot_id": f"{US_HYBRID_VERSION}:{state['revision']}", "snapshot_checksum": state["checksum"],
        "hybrid_status": "monitoring" if calendar["is_regular"] and worker_fresh else "waiting_regular_session" if not calendar["is_regular"] else "collector_stale",
        "hybrid_initialized_at": state["initialized_at"], "hybrid_updated_at": state["updated_at"],
        "daily_setup_ready": base_ready, "collector_fresh": worker_fresh,
        "hybrid_ledger_ready": True,
        "market_session": calendar["session"], "new_entries_allowed": base_ready and worker_fresh,
        "legacy_strategy_version": state["legacy"]["strategy_version"],
        "legacy_performance_summary": state["legacy"]["performance_summary"],
        "performance_summary": build_us_signal_performance_summary(state["events"], as_of=current),
        "signal_revision": str(state["revision"]), "source_interval_seconds": 60,
        "confirmation_max_age_seconds": US_HYBRID_MAX_AGE_SECONDS,
    })
    evidence = {item["code"]: item for item in feed.get("public_member_signals") or []}
    # Holding evidence remains available even if the name leaves tomorrow's Top100.
    for code, position in state["positions"].items():
        if code not in evidence and position.get("public_reasons"):
            evidence[code] = {"public_reasons": position["public_reasons"]}
    latest_events = {item["code"]: item for item in state["events"]}
    codes = {
        code
        for code, setup in state["setups"].items()
        if base_ready
        and (setup.get("daily_watch") or setup.get("eligible"))
        and setup.get("reference_close")
        and setup.get("atr")
        and setup.get("average_daily_volume")
        and _supportive_public_reasons(feed, code)
    }
    codes.update(
        code
        for code, candidate in state.get("entry_candidates", {}).items()
        if candidate.get("status") == "watching"
    )
    codes.update(state["positions"])
    for code in sorted(codes):
        position = state["positions"].get(code)
        setup = state["setups"].get(code) or position or {}
        event = latest_events.get(code)
        observation = state["observations"].get(code) or {}
        candidate = state.get("entry_candidates", {}).get(code) or {}
        observed_at = _utc(observation.get("observed_at"))
        fresh = bool(worker_fresh and calendar["is_regular"] and observed_at
                     and observation.get("state") == "fresh"
                     and 60 <= (current - observed_at).total_seconds() <= 60 + US_HYBRID_MAX_AGE_SECONDS)
        remaining = position["remaining"] if position else 0
        action = (
            "partially_exited" if remaining == 0.5 else "holding" if remaining else "exited"
        ) if position else (
            "entry_watch" if candidate.get("status") == "watching" else "entry_pending"
        )
        if position and event and event["side"] == "buy" and event["execution_date"] == str(current.date()):
            action = "entered"
        reference_available = bool(observed_at and observation.get("price") and not calendar["is_regular"])
        price = observation.get("price") if fresh or reference_available else None
        return_rate = (position["realized_return"] + remaining * (price / position["entry_price"] - 1) * 100
                       if position and price else position["realized_return"] if position and not remaining else None)
        cur = {
            "action": action, "label": LABELS[action], "position_open": remaining > 0,
            "model_exposure_percent": remaining * 100, "live_observation": fresh,
            "as_of": observation.get("observed_at") or state["updated_at"], "price": price,
            "entry_date": position.get("entry_date") if position else None,
            "entry_price": position.get("entry_price") if position else None,
            "return_rate": return_rate, "unrealized_return": return_rate if remaining else None,
            "exit_date": str(position["last_exit_at"])[:10] if position and not remaining else None,
            "exit_price": position.get("last_exit_price") if position and not remaining else None,
            "next_confirmation": "정규장의 최신 완료 분봉과 데이터 시각을 확인하세요.",
            "intraday_candidate": {
                key: candidate.get(key)
                for key in (
                    "candidate_id", "status", "first_observed_at",
                    "decision_minute_at", "confirmed_at", "expires_at",
                    "paused_at", "pause_reasons", "volume_participation",
                )
                if candidate.get(key) is not None
            } or None,
            "lifecycle": {"state": action, "label": LABELS[action], "latest_transition": {
                **(event or {}), "transition_date": event.get("execution_date") if event else None,
            }},
        }
        result["items"].append({
            "code": code, "name": setup.get("name", code), "market": setup.get("market", "NASDAQ"),
            "market_cap_rank": setup.get("market_cap_rank"), "currency": "USD", "current": cur,
            "strategy_version": US_HYBRID_VERSION, "rollout_mode": "hybrid_forward", "execution_enabled": False,
            "data_state": "ready", "signal": LABELS[action], "side": "sell" if action in {"partially_exited", "exited"} else "buy",
            "status": "confirmed" if position else "preliminary", "is_preliminary": not bool(position),
            "state_after": action, "event_side": event.get("side") if event else "buy",
            "execution_date": event.get("execution_date") if event else None,
            "return_rate": return_rate, "display_return_rate": return_rate,
            "signal_date": event.get("execution_date") if event else setup.get("signal_date"),
            "signal_at": (
                event.get("signal_at") if event
                else candidate.get("first_observed_at") or setup.get("armed_at")
            ),
            "price_through": result.get("universe_as_of"), "as_of": state["updated_at"],
            "price": price, "is_current_holding": remaining > 0, "is_current_universe_member": code in evidence,
            "change_rate": ((price / setup["reference_close"] - 1) * 100
                            if price and setup.get("reference_close") else None),
            "public_reasons": evidence.get(code, {}).get("public_reasons") or [],
            "flow_semantics": "dollar_volume_participation_proxy", "reason": HYBRID_NOTICE,
            "intraday_execution_verified": bool(event), "quote_state": "fresh" if fresh else "reference" if reference_available else "awaiting_fresh_regular_quote",
            "events": [{k: v for k, v in item.items() if k != "minute_evidence"} for item in state["events"] if item["code"] == code][-10:],
        })
    # Keep the old publication visible only as frozen history, never alertable.
    for item in state["legacy"]["items"]:
        archived = deepcopy(item)
        archived.update({"history_frozen": True, "alert_eligible": False, "is_current_holding": False})
        archived["current"] = {**archived.get("current", {}), "position_open": False, "model_exposure_percent": 0}
        result["preliminary_history"].append(archived)
    result["items"].sort(key=lambda item: (item["current"]["action"] == "entry_pending", -(_utc(item.get("signal_at")) or US_HYBRID_START).timestamp(), item["code"]))
    result["confirmed_count"] = sum(item["current"]["position_open"] for item in result["items"])
    result["preliminary_count"] = sum(item["is_preliminary"] for item in result["items"])
    result["entry_pending_count"] = sum(item["current"]["action"] == "entry_pending" for item in result["items"])
    result["intraday_coverage"] = {
        "monitored_count": len(codes), "fresh_count": sum(item["quote_state"] == "fresh" for item in result["items"]),
        "source": "yahoo_chart_1m", "delayed_or_missing_blocks_confirmation": True,
    }
    return result


def fresh_us_hybrid_events(db: Session, *, now: datetime) -> list[dict]:
    if not us_signal_session_state(now)["is_regular"]:
        return []
    state = read_us_hybrid_state(db)
    if state is None:
        return []
    return [event for event in state["events"]
            if event.get("intraday_execution_verified") is True
            and (at := _utc(event.get("signal_at"))) is not None
            and 0 <= (now - at).total_seconds() <= 180
            and event.get("execution_date") == str(now.date())]
