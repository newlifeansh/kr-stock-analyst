from datetime import date, datetime, timedelta

import pytest

from app.services import live_order_guard


KST = live_order_guard.KST
NOW = datetime(2026, 10, 23, 10, 0, tzinfo=KST)


def item(side: str = "buy") -> dict:
    event_side = "partial_sell" if side == "partial_sell" else side
    return {
        "status": "confirmed",
        "side": "buy" if side == "buy" else "sell",
        "event_side": event_side,
        "execution_date": date(2026, 10, 23),
        "confirmed_at": NOW - timedelta(seconds=60),
        "decision_minute_at": NOW - timedelta(seconds=60),
        "intraday_execution_verified": True,
        "intraday_order_verified": True,
        "price": 101_000,
    }


@pytest.mark.parametrize("side", ["buy", "partial_sell", "sell"])
def test_fresh_completed_minute_buy_and_sell_are_order_eligible(side):
    result = live_order_guard.evaluate_live_order_candidate(item(side), now=NOW)
    assert result["eligible"] is True
    assert result["side"] == side
    assert result["expires_at"] == NOW + timedelta(seconds=120)


@pytest.mark.parametrize(
    ("now", "reason"),
    [
        (NOW.replace(hour=8, minute=59), "outside_regular_session"),
        (NOW.replace(hour=15, minute=30), "outside_regular_session"),
        (NOW.replace(hour=18, minute=0), "outside_regular_session"),
    ],
    ids=["before-open", "at-close", "after-close"],
)
def test_no_buy_or_sell_order_is_created_outside_regular_session(now, reason):
    assert live_order_guard.evaluate_live_order_candidate(
        item("sell"), now=now
    )["reason"] == reason


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"intraday_execution_verified": False}, "execution_not_verified"),
        ({"intraday_order_verified": False}, "minute_path_not_verified"),
        ({"execution_date": date(2026, 10, 22)}, "not_current_session"),
        ({"confirmed_at": None, "decision_minute_at": None}, "missing_event_clock"),
        ({"confirmed_at": NOW - timedelta(seconds=181)}, "stale_or_future_event"),
        ({"confirmed_at": NOW + timedelta(seconds=1)}, "stale_or_future_event"),
        ({"price": None}, "invalid_price"),
    ],
    ids=[
        "execution-unverified",
        "path-unverified",
        "previous-session",
        "clock-missing",
        "stale",
        "future",
        "price-missing",
    ],
)
def test_live_order_guard_fails_closed(change, reason):
    candidate = {**item(), **change}
    result = live_order_guard.evaluate_live_order_candidate(candidate, now=NOW)
    assert result["eligible"] is False
    assert result["reason"] == reason
