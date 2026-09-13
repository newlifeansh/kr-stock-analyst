from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.services.us_market import _us_market_session
from app.services.us_market_calendar import (
    latest_completed_us_market_session,
    recent_us_market_session_dates,
    us_market_session,
    us_signal_refresh_allowed,
    us_signal_session_state,
)


UTC = timezone.utc


def test_us_calendar_rejects_holiday_and_weekend():
    assert us_market_session(date(2026, 7, 3)) is None
    assert us_market_session(date(2026, 7, 4)) is None


def test_recent_session_vector_uses_only_consecutive_official_xnys_sessions():
    sessions = recent_us_market_session_dates(date(2026, 7, 6), 3)

    assert sessions == (
        date(2026, 7, 1),
        date(2026, 7, 2),
        date(2026, 7, 6),
    )


def test_us_market_display_session_stays_closed_on_xnys_holiday():
    state = _us_market_session(datetime(2026, 7, 3, 14, 0, tzinfo=UTC))

    assert state["session"] == "closed"
    assert state["label"] == "미국 정규장 마감/대기"
    assert state["is_regular"] is False
    assert state["is_live"] is False
    assert state["refresh_interval_seconds"] == 300


def test_us_calendar_uses_official_early_close():
    session = us_market_session(date(2026, 11, 27))

    assert session is not None
    assert session.open_at == datetime(2026, 11, 27, 14, 30, tzinfo=UTC)
    assert session.close_at == datetime(2026, 11, 27, 18, 0, tzinfo=UTC)


def test_us_market_display_session_switches_to_afterhours_at_early_close():
    premarket = _us_market_session(datetime(2026, 11, 27, 13, 0, tzinfo=UTC))
    before_close = _us_market_session(
        datetime(2026, 11, 27, 17, 59, tzinfo=UTC)
    )
    at_close = _us_market_session(datetime(2026, 11, 27, 18, 0, tzinfo=UTC))

    assert premarket["session"] == "premarket"
    assert premarket["label"] == "미국 프리장 진행 중"
    assert premarket["is_regular"] is False
    assert premarket["is_live"] is True
    assert before_close["session"] == "regular"
    assert before_close["label"] == "미국 정규장 진행 중"
    assert before_close["is_regular"] is True
    assert before_close["is_live"] is True
    assert at_close["session"] == "afterhours"
    assert at_close["label"] == "미국 애프터장 진행 중"
    assert at_close["is_regular"] is False
    assert at_close["is_live"] is True


def test_latest_completed_session_changes_at_early_close():
    before_close = latest_completed_us_market_session(
        datetime(2026, 11, 27, 17, 59, tzinfo=UTC)
    )
    after_close = latest_completed_us_market_session(
        datetime(2026, 11, 27, 18, 1, tzinfo=UTC)
    )

    assert before_close.session_date == date(2026, 11, 25)
    assert after_close.session_date == date(2026, 11, 27)


def test_signal_session_state_is_closed_after_early_close():
    state = us_signal_session_state(datetime(2026, 11, 27, 18, 1, tzinfo=UTC))

    assert state["session"] == "closed"
    assert state["latest_completed_date"] == date(2026, 11, 27)
    assert state["calendar_source"] == "exchange_calendars:XNYS"


def test_signal_publication_waits_for_post_close_provider_grace():
    assert us_signal_refresh_allowed(datetime(2026, 11, 27, 18, 14, tzinfo=UTC)) is False
    assert us_signal_refresh_allowed(datetime(2026, 11, 27, 18, 15, tzinfo=UTC)) is True
