from datetime import date, datetime
from types import SimpleNamespace

from app.services import market_calendar


def test_fetch_latest_market_session_has_history_for_collector_backfill(monkeypatch):
    calls = []

    def get(_url, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            content=b'<item data="20260918|1|2|1|2|100" />',
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(market_calendar.requests, "get", get)

    assert market_calendar._fetch_latest_market_session_date(date(2026, 9, 19)) == date(
        2026, 9, 18
    )
    assert calls[0]["params"]["count"] == "60"


def test_parse_latest_market_session_date_ignores_weekend_through_date():
    payload = b"""
    <item data="20260730|1|2|1|2|100" />
    <item data="20260731|1|2|1|2|100" />
    """

    assert market_calendar._parse_latest_market_session_date(payload, date(2026, 8, 2)) == date(2026, 7, 31)


def test_market_windows_follow_exchange_schedule():
    assert market_calendar.is_korea_regular_market_session(datetime(2026, 7, 31, 10, 0)) is True
    assert market_calendar.is_korea_daily_signal_window(datetime(2026, 7, 31, 16, 0)) is True
    assert market_calendar.is_korea_regular_market_session(datetime(2026, 8, 2, 10, 0)) is False
    assert market_calendar.is_korea_daily_signal_window(datetime(2026, 8, 2, 16, 0)) is False


def test_scheduled_krx_session_is_open_before_todays_closing_index_exists(monkeypatch):
    monkeypatch.setattr(
        market_calendar,
        "latest_korea_market_session_date",
        lambda _now=None: date(2026, 10, 7),
    )

    assert market_calendar.is_scheduled_korea_market_session_date(date(2026, 10, 8))
    assert market_calendar.is_korea_market_session_date(
        date(2026, 10, 8), datetime(2026, 10, 8, 8, 30)
    )
    assert market_calendar.is_korea_regular_market_session(
        datetime(2026, 10, 8, 9, 3)
    )
    assert market_calendar.is_korea_daily_signal_window(
        datetime(2026, 10, 8, 15, 45)
    )
    assert not market_calendar.is_scheduled_korea_market_session_date(date(2026, 10, 9))
    assert not market_calendar.is_korea_regular_market_session(
        datetime(2026, 10, 9, 9, 3)
    )


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


def test_published_investor_flow_session_uses_separate_naver_sla(monkeypatch):
    lookups = []

    def latest(now=None):
        lookups.append(now)
        return now.date()

    monkeypatch.setattr(market_calendar, "latest_korea_market_session_date", latest)

    publication_gap = market_calendar.latest_published_korea_investor_flow_date(
        datetime(2026, 8, 12, 18, 5)
    )
    published = market_calendar.latest_published_korea_investor_flow_date(
        datetime(2026, 8, 12, 19, 5)
    )

    assert publication_gap == date(2026, 8, 11)
    assert published == date(2026, 8, 12)
    assert lookups[0].hour == 23 and lookups[0].date() == date(2026, 8, 11)
