from __future__ import annotations

"""Exchange-session calendar used by the US signal release candidate.

The signal path must know holidays and one-off early closes.  It therefore
uses the XNYS exchange schedule rather than treating every weekday as a full
09:30-16:00 session.  Nasdaq's regular equity holiday and early-close schedule
is aligned with this calendar for the securities in the signal universe.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Optional


US_SIGNAL_PUBLICATION_GRACE = timedelta(minutes=15)


@dataclass(frozen=True)
class USMarketSession:
    session_date: date
    open_at: datetime
    close_at: datetime


class USMarketCalendarUnavailable(RuntimeError):
    """Raised when an authoritative US exchange schedule cannot be loaded."""


@lru_cache(maxsize=8)
def _calendar_for_year(year: int) -> Any:
    try:
        import exchange_calendars as exchange_calendars
    except ImportError as exc:  # pragma: no cover - packaging gate
        raise USMarketCalendarUnavailable(
            "exchange_calendars is required for US signal session validation"
        ) from exc
    return exchange_calendars.get_calendar(
        "XNYS",
        start=f"{year - 1}-01-01",
        end=f"{year + 1}-12-31",
    )


def us_market_session(session_date: date) -> Optional[USMarketSession]:
    """Return the regular session, including the exchange-defined early close."""

    try:
        import pandas as pd

        calendar = _calendar_for_year(session_date.year)
        label = pd.Timestamp(session_date)
        if not bool(calendar.is_session(label)):
            return None
        session_open = calendar.session_open(label).to_pydatetime()
        session_close = calendar.session_close(label).to_pydatetime()
    except USMarketCalendarUnavailable:
        raise
    except Exception as exc:
        raise USMarketCalendarUnavailable(
            f"US exchange schedule unavailable for {session_date.isoformat()}"
        ) from exc
    if session_open.tzinfo is None:
        session_open = session_open.replace(tzinfo=timezone.utc)
    if session_close.tzinfo is None:
        session_close = session_close.replace(tzinfo=timezone.utc)
    return USMarketSession(
        session_date=session_date,
        open_at=session_open.astimezone(timezone.utc),
        close_at=session_close.astimezone(timezone.utc),
    )


@lru_cache(maxsize=256)
def recent_us_market_session_dates(
    through: date,
    count: int,
) -> tuple[date, ...]:
    """Return the exact consecutive XNYS session vector ending at ``through``."""

    normalized_count = int(count)
    if normalized_count < 1 or us_market_session(through) is None:
        return ()
    sessions: list[date] = []
    candidate = through
    # A generous bound covers weekends, exchange holidays and exceptional
    # closures without silently returning a partial vector.
    max_calendar_days = normalized_count * 3 + 30
    for _ in range(max_calendar_days):
        if us_market_session(candidate) is not None:
            sessions.append(candidate)
            if len(sessions) == normalized_count:
                return tuple(reversed(sessions))
        candidate -= timedelta(days=1)
    raise USMarketCalendarUnavailable(
        f"Could not resolve {normalized_count} XNYS sessions through {through.isoformat()}"
    )


def latest_completed_us_market_session(
    now: Optional[datetime] = None,
) -> USMarketSession:
    """Return the latest exchange session whose official close has passed."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    for offset in range(0, 15):
        candidate = current.date() - timedelta(days=offset)
        session = us_market_session(candidate)
        if session is not None and session.close_at <= current:
            return session
    raise USMarketCalendarUnavailable("No completed US exchange session in lookup window")


def us_signal_session_state(now: Optional[datetime] = None) -> dict[str, Any]:
    """Return the signal-facing regular-session state and authoritative close."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    today = us_market_session(current.date())
    latest_completed = latest_completed_us_market_session(current)
    regular = bool(today and today.open_at <= current < today.close_at)
    refresh_after = latest_completed.close_at + US_SIGNAL_PUBLICATION_GRACE
    return {
        "session": "regular" if regular else "closed",
        "is_regular": regular,
        "current_session": today,
        "latest_completed": latest_completed,
        "latest_completed_date": latest_completed.session_date,
        "latest_completed_close_at": latest_completed.close_at,
        "refresh_after": refresh_after,
        "refresh_allowed": bool(not regular and current >= refresh_after),
        "calendar_source": "exchange_calendars:XNYS",
    }


def us_signal_refresh_allowed(now: Optional[datetime] = None) -> bool:
    """Allow publication only after the official close plus provider grace."""

    return bool(us_signal_session_state(now)["refresh_allowed"])
