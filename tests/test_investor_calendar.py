from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event, Lock
from time import monotonic

from app.services import investor_calendar
from app.services.investor_calendar import _parse_ipo_events, _parse_ir_events


IPO_HTML = """
<table class="list"><tbody>
  <tr onclick="fnDetailView('20260812000001')">
    <td title="테스트테크"><img alt="코스닥" />테스트테크</td>
    <td>2026-08-01</td>
    <td>2026-08-03 ~ 2026-08-07</td>
    <td>2026-08-12 ~ 2026-08-13</td>
    <td>2026-08-17</td>
    <td>12,000</td>
    <td>24,000</td>
    <td>2026-08-21</td>
    <td>테스트증권(주), IBK투자증권(주)</td>
  </tr>
  <tr>
    <td title="지난기업">지난기업</td><td>2026-07-01</td><td>-</td>
    <td>2026-07-10 ~ 2026-07-11</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td>
  </tr>
</tbody></table>
"""

IR_HTML = """
<table class="list"><tbody>
  <tr>
    <td>2</td>
    <td><img alt="유가증권" /><a title="테스트전자">테스트전자</a></td>
    <td><a title="2026년 2분기 경영실적 발표" onclick="fnDetailView('1002')">경영실적 발표</a></td>
    <td>온라인</td><td>2026-08-13</td><td>14:00</td>
  </tr>
  <tr>
    <td>1</td>
    <td><img alt="유가증권" /><a title="테스트전자">테스트전자</a></td>
    <td><a title="2026 Q2 Earnings Results" onclick="fnDetailView('1001')">Earnings Results</a></td>
    <td>Online</td><td>2026-08-13</td><td>14:00</td>
  </tr>
  <tr>
    <td>3</td><td><a title="기타기업">기타기업</a></td>
    <td><a title="회사소개 및 투자자 미팅">투자자 미팅</a></td>
    <td>서울</td><td>2026-08-13</td><td>10:00</td>
  </tr>
</tbody></table>
"""


def test_parse_kind_ipo_schedule_keeps_upcoming_subscription_details():
    events = _parse_ipo_events(
        IPO_HTML,
        starts_on_or_after=date(2026, 8, 12),
        starts_on_or_before=date(2026, 8, 18),
    )

    assert len(events) == 1
    event = events[0]
    assert event.kind == "ipo"
    assert event.title == "8월 12~13일 · 테스트테크 공모주 청약"
    assert event.summary == "공모가는 12,000원이고 테스트증권·IBK투자증권에서 청약해요."
    assert "bzProcsNo=20260812000001" in event.detail_url
    assert "press_name" not in event.as_briefing_item()


def test_parse_kind_ir_schedule_keeps_earnings_and_deduplicates_english_copy():
    events = _parse_ir_events(
        IR_HTML,
        starts_on_or_after=date(2026, 8, 13),
        starts_on_or_before=date(2026, 8, 13),
    )

    assert len(events) == 1
    event = events[0]
    assert event.kind == "earnings"
    assert event.title == "8월 13일 · 테스트전자 실적 발표"
    assert event.summary == "14:00에 테스트전자의 2026년 2분기 실적을 발표해요."
    assert event.market == "유가증권"


def test_upcoming_investor_events_singleflights_concurrent_cache_misses(monkeypatch):
    investor_calendar.INVESTOR_CALENDAR_CACHE.clear()
    first_fetch_started = Event()
    release_first_fetch = Event()
    second_call_started = Event()
    call_counts = {"ipo": 0, "earnings": 0}
    call_counts_lock = Lock()

    def blocked_ipo_fetch(_starts_on_or_after, _starts_on_or_before):
        with call_counts_lock:
            call_counts["ipo"] += 1
        first_fetch_started.set()
        assert release_first_fetch.wait(timeout=3)
        return []

    def fake_ir_fetch(_starts_on_or_after, _starts_on_or_before):
        with call_counts_lock:
            call_counts["earnings"] += 1
        return []

    def concurrent_call():
        second_call_started.set()
        return investor_calendar.upcoming_investor_events(date(2026, 8, 31))

    monkeypatch.setattr(investor_calendar, "_fetch_ipo_events", blocked_ipo_fetch)
    monkeypatch.setattr(investor_calendar, "_fetch_ir_events", fake_ir_fetch)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                investor_calendar.upcoming_investor_events,
                date(2026, 8, 31),
            )
            assert first_fetch_started.wait(timeout=1)
            second = executor.submit(concurrent_call)
            assert second_call_started.wait(timeout=1)
            release_first_fetch.set()

            assert first.result(timeout=3) == []
            assert second.result(timeout=3) == []
    finally:
        release_first_fetch.set()
        investor_calendar.INVESTOR_CALENDAR_CACHE.clear()

    assert call_counts == {"ipo": 1, "earnings": 1}


def test_upcoming_investor_events_keeps_fast_source_at_total_deadline(monkeypatch):
    investor_calendar.INVESTOR_CALENDAR_CACHE.clear()
    release_blocked_fetch = Event()
    blocked_fetch_started = Event()
    blocked_fetch_finished = Event()
    fast_fetch_finished = Event()
    call_counts = {"ipo": 0, "earnings": 0}
    call_counts_lock = Lock()
    cached_ttls: list[int] = []
    original_cache_set = investor_calendar.INVESTOR_CALENDAR_CACHE.set
    fast_event = investor_calendar.InvestorScheduleEvent(
        key="earnings:fast:2026-09-01",
        kind="earnings",
        company_name="빠른기업",
        title="9월 1일 · 빠른기업 실적 발표",
        summary="빠른기업의 실적을 발표해요.",
        starts_on=date(2026, 9, 1),
        ends_on=date(2026, 9, 1),
        starts_at=None,
        detail_url="https://kind.krx.co.kr/fast",
    )

    def blocked_ipo_fetch(_starts_on_or_after, _starts_on_or_before):
        with call_counts_lock:
            call_counts["ipo"] += 1
        blocked_fetch_started.set()
        assert fast_fetch_finished.wait(timeout=1)
        assert release_blocked_fetch.wait(timeout=3)
        blocked_fetch_finished.set()
        return []

    def fast_ir_fetch(_starts_on_or_after, _starts_on_or_before):
        with call_counts_lock:
            call_counts["earnings"] += 1
        fast_fetch_finished.set()
        return [fast_event]

    def record_cache_set(key, value, ttl_seconds):
        cached_ttls.append(ttl_seconds)
        return original_cache_set(key, value, ttl_seconds)

    monkeypatch.setattr(investor_calendar, "KIND_FANOUT_DEADLINE_SECONDS", 0.1)
    monkeypatch.setattr(investor_calendar, "_fetch_ipo_events", blocked_ipo_fetch)
    monkeypatch.setattr(investor_calendar, "_fetch_ir_events", fast_ir_fetch)
    monkeypatch.setattr(investor_calendar.INVESTOR_CALENDAR_CACHE, "set", record_cache_set)

    try:
        started_at = monotonic()
        first = investor_calendar.upcoming_investor_events(date(2026, 8, 31))
        elapsed = monotonic() - started_at
        second = investor_calendar.upcoming_investor_events(date(2026, 8, 31))

        assert blocked_fetch_started.is_set()
        assert not blocked_fetch_finished.is_set()
        assert elapsed < 0.75
        assert first == [fast_event]
        assert second == [fast_event]
        assert call_counts == {"ipo": 1, "earnings": 1}
        assert cached_ttls == [investor_calendar.INVESTOR_CALENDAR_EMPTY_TTL_SECONDS]
    finally:
        release_blocked_fetch.set()
        assert blocked_fetch_finished.wait(timeout=1)
        investor_calendar.INVESTOR_CALENDAR_CACHE.clear()
