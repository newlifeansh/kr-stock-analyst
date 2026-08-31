from datetime import date, datetime

from app.services import market_calendar


def test_parse_latest_market_session_date_ignores_weekend_through_date():
    payload = b"""
    <item data="20260730|1|2|1|2|100" />
    <item data="20260731|1|2|1|2|100" />
    """

    assert market_calendar._parse_latest_market_session_date(payload, date(2026, 8, 2)) == date(2026, 7, 31)


def test_market_windows_require_latest_real_session(monkeypatch):
    monkeypatch.setattr(
        market_calendar,
        "latest_korea_market_session_date",
        lambda now=None: date(2026, 7, 31),
    )

    assert market_calendar.is_korea_regular_market_session(datetime(2026, 7, 31, 10, 0)) is True
    assert market_calendar.is_korea_daily_signal_window(datetime(2026, 7, 31, 16, 0)) is True
    assert market_calendar.is_korea_regular_market_session(datetime(2026, 8, 2, 10, 0)) is False
    assert market_calendar.is_korea_daily_signal_window(datetime(2026, 8, 2, 16, 0)) is False


def test_latest_market_session_cache_is_scoped_to_lookup_date(monkeypatch):
    calls = []

    def fetch(through):
        calls.append(through)
        return through

    market_calendar.MARKET_SESSION_CACHE.clear()
    monkeypatch.setattr(market_calendar, "_fetch_latest_market_session_date", fetch)

    assert market_calendar.latest_korea_market_session_date(datetime(2026, 8, 11, 12, 0)) == date(2026, 8, 11)
    assert market_calendar.latest_korea_market_session_date(datetime(2026, 8, 12, 12, 0)) == date(2026, 8, 12)
    assert calls == [date(2026, 8, 11), date(2026, 8, 12)]


def test_completed_market_session_uses_yesterday_until_flow_publication(monkeypatch):
    lookups = []

    def latest(now=None):
        lookups.append(now)
        return now.date()

    monkeypatch.setattr(market_calendar, "latest_korea_market_session_date", latest)

    morning = market_calendar.latest_completed_korea_market_session_date(datetime(2026, 8, 12, 9, 27))
    evening = market_calendar.latest_completed_korea_market_session_date(datetime(2026, 8, 12, 18, 5))

    assert morning == date(2026, 8, 11)
    assert evening == date(2026, 8, 12)
    assert lookups[0].hour == 23 and lookups[0].date() == date(2026, 8, 11)
