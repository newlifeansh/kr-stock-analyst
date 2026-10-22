"""Fail-closed eligibility contract for future KR broker order adapters."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.services.market_calendar import is_korea_market_session_date

KST = ZoneInfo("Asia/Seoul")
POLICY_VERSION = "kr-live-order-regular-session-v1"
MAX_SIGNAL_AGE_SECONDS = 180


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = (
            value
            if isinstance(value, datetime)
            else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        )
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(KST) if parsed.tzinfo is not None else None


def _date(value: Any) -> date | None:
    try:
        return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def evaluate_live_order_candidate(
    item: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Return whether a confirmed feed item may reach a KR broker adapter.

    Both buys and sells require a fresh, completed-minute event during the
    current KRX regular session. A daily close signal may remain visible for
    analysis, but it cannot become an order after the market closes.
    """

    local_now = now.astimezone(KST) if now.tzinfo is not None else None
    reason = None
    occurred_at = None
    side = str((item or {}).get("event_side") or (item or {}).get("side") or "")
    if local_now is None:
        reason = "naive_clock"
    elif not (
        is_korea_market_session_date(local_now.date(), local_now)
        and time(9, 0) <= local_now.time() < time(15, 30)
    ):
        reason = "outside_regular_session"
    elif not isinstance(item, dict) or item.get("status") != "confirmed":
        reason = "not_confirmed"
    elif side not in {"buy", "partial_sell", "sell"}:
        reason = "unsupported_side"
    elif item.get("intraday_execution_verified") is not True:
        reason = "execution_not_verified"
    elif item.get("intraday_order_verified") is not True:
        reason = "minute_path_not_verified"
    elif _date(item.get("execution_date")) != local_now.date():
        reason = "not_current_session"
    else:
        occurred_at = _timestamp(
            item.get("confirmed_at") or item.get("decision_minute_at")
        )
        if occurred_at is None:
            reason = "missing_event_clock"
        elif occurred_at.date() != local_now.date() or not (
            time(9, 0) <= occurred_at.time() < time(15, 30)
        ):
            reason = "event_outside_regular_session"
        else:
            age = (local_now - occurred_at).total_seconds()
            if not 0 <= age <= MAX_SIGNAL_AGE_SECONDS:
                reason = "stale_or_future_event"
            else:
                try:
                    if float(item.get("price")) <= 0:
                        reason = "invalid_price"
                except (TypeError, ValueError):
                    reason = "invalid_price"

    return {
        "eligible": reason is None,
        "reason": reason,
        "policy_version": POLICY_VERSION,
        "side": side or None,
        "occurred_at": occurred_at,
        "expires_at": (
            occurred_at + timedelta(seconds=MAX_SIGNAL_AGE_SECONDS)
            if occurred_at is not None
            else None
        ),
    }
