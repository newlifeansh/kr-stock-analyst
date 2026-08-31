from datetime import datetime

from app.services import economic_calendar


BLS_SAMPLE_ICS = b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
DTSTART;TZID=US-Eastern:20260113T083000\r
SUMMARY:Consumer Price Index\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART;TZID=US-Eastern:20260812T083000\r
SUMMARY:Consumer Price Index\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART;TZID=US-Eastern:20260813T083000\r
SUMMARY:Producer Price Index\r
END:VEVENT\r
END:VCALENDAR\r
"""

BOK_SAMPLE_HTML = """<!doctype html>
<html lang="ko"><body><table><tbody>
<tr><td>2026-08-25</td><td>6:00</td><td class="title">2026년 8월 소비자동향조사 결과</td></tr>
<tr><td>2026-08-26</td><td>12:00</td><td class="title">2026년 7월 금융기관 가중평균금리</td></tr>
<tr><td>2026-08-26</td><td>6:00</td><td class="title">2026년 8월 기업경기조사 결과 및 경제심리지수(ESI)</td></tr>
</tbody></table></body></html>"""


def test_parse_bls_cpi_calendar_converts_eastern_time_to_kst():
    assert economic_calendar._parse_bls_cpi_calendar(BLS_SAMPLE_ICS) == [
        datetime(2026, 1, 13, 22, 30),
        datetime(2026, 8, 12, 21, 30),
    ]


def test_cpi_release_schedule_uses_cached_live_bls_calendar(monkeypatch):
    calls = []

    def fetch():
        calls.append(True)
        return tuple(economic_calendar._parse_bls_cpi_calendar(BLS_SAMPLE_ICS))

    economic_calendar.BLS_CALENDAR_CACHE.clear()
    monkeypatch.setattr(economic_calendar, "_fetch_bls_cpi_releases", fetch)

    first = economic_calendar.cpi_release_occurrences_between(
        datetime(2026, 8, 10),
        datetime(2026, 8, 14),
    )
    second = economic_calendar.cpi_release_occurrences_between(
        datetime(2026, 8, 10),
        datetime(2026, 8, 14),
    )

    assert first == [datetime(2026, 8, 12, 21, 30)]
    assert second == first
    assert calls == [True]


def test_cpi_release_schedule_falls_back_when_bls_is_unavailable(monkeypatch):
    economic_calendar.BLS_CALENDAR_CACHE.clear()

    def fail():
        raise RuntimeError("BLS unavailable")

    monkeypatch.setattr(economic_calendar, "_fetch_bls_cpi_releases", fail)

    assert economic_calendar.cpi_release_occurrences_between(
        datetime(2026, 8, 10),
        datetime(2026, 8, 14),
    ) == [datetime(2026, 8, 12, 21, 30)]


def test_live_bls_calendar_does_not_mix_in_fallback_dates(monkeypatch):
    economic_calendar.BLS_CALENDAR_CACHE.clear()
    monkeypatch.setattr(
        economic_calendar,
        "_fetch_bls_cpi_releases",
        lambda: (datetime(2026, 8, 13, 21, 30),),
    )

    assert economic_calendar.cpi_release_occurrences_between(
        datetime(2026, 8, 12),
        datetime(2026, 8, 12, 23, 59),
    ) == []


def test_parse_bok_calendar_keeps_supported_korean_market_events():
    assert economic_calendar._parse_bok_release_calendar(BOK_SAMPLE_HTML) == [
        ("kr-bsi-esi", datetime(2026, 8, 26, 6, 0)),
        ("kr-bank-rate", datetime(2026, 8, 26, 12, 0)),
    ]


def test_bok_release_schedule_uses_one_cached_official_year(monkeypatch):
    calls = []

    def fetch(year):
        calls.append(year)
        return tuple(economic_calendar._parse_bok_release_calendar(BOK_SAMPLE_HTML))

    economic_calendar.BOK_CALENDAR_CACHE.clear()
    monkeypatch.setattr(economic_calendar, "_fetch_bok_releases", fetch)

    bsi = economic_calendar.bok_release_occurrences_between(
        "kr-bsi-esi",
        datetime(2026, 8, 24),
        datetime(2026, 8, 27),
    )
    bank_rate = economic_calendar.bok_release_occurrences_between(
        "kr-bank-rate",
        datetime(2026, 8, 24),
        datetime(2026, 8, 27),
    )

    assert bsi == [datetime(2026, 8, 26, 6, 0)]
    assert bank_rate == [datetime(2026, 8, 26, 12, 0)]
    assert calls == [2026]


def test_bok_release_schedule_falls_back_when_official_calendar_is_unavailable(monkeypatch):
    economic_calendar.BOK_CALENDAR_CACHE.clear()
    monkeypatch.setattr(
        economic_calendar,
        "_fetch_bok_releases",
        lambda _year: (_ for _ in ()).throw(RuntimeError("BOK unavailable")),
    )

    assert economic_calendar.bok_release_occurrences_between(
        "kr-bsi-esi",
        datetime(2026, 8, 26),
        datetime(2026, 8, 26, 23, 59),
    ) == [datetime(2026, 8, 26, 6, 0)]
