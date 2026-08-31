from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup
import requests

from app.services.ttl_cache import TTLCache


BLS_RELEASE_CALENDAR_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_CPI_RELEASE_URL = "https://www.bls.gov/schedule/news_release/cpi.htm"
BLS_CALENDAR_CACHE = TTLCache(maxsize=2)
BLS_CALENDAR_TTL_SECONDS = 6 * 60 * 60
BLS_REQUEST_TIMEOUT_SECONDS = 10
BLS_HEADERS = {
    "User-Agent": "kr-stock-analyst/0.1 contact=admin@secret-note.app",
    "Accept": "text/calendar,text/plain;q=0.9,*/*;q=0.8",
}

BOK_RELEASE_CALENDAR_URL = (
    "https://www.bok.or.kr/portal/stats/statsPublictSchdul/listCldr.do"
)
BOK_CALENDAR_CACHE = TTLCache(maxsize=8)
BOK_CALENDAR_TTL_SECONDS = 6 * 60 * 60
BOK_REQUEST_TIMEOUT_SECONDS = 10
BOK_HEADERS = {
    "User-Agent": "kr-stock-analyst/0.1 contact=admin@secret-note.app",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}
BOK_EVENT_KEYS = frozenset({"kr-bsi-esi", "kr-bank-rate"})

KST = ZoneInfo("Asia/Seoul")
US_EASTERN = ZoneInfo("America/New_York")


# Official BLS dates published for 2026. These are used only when the live BLS
# calendar is temporarily unavailable; the live iCalendar feed remains the
# primary schedule source.
BLS_CPI_FALLBACK_EASTERN = (
    datetime(2025, 12, 18, 8, 30),
    datetime(2026, 1, 13, 8, 30),
    datetime(2026, 2, 13, 8, 30),
    datetime(2026, 3, 11, 8, 30),
    datetime(2026, 4, 10, 8, 30),
    datetime(2026, 5, 12, 8, 30),
    datetime(2026, 6, 10, 8, 30),
    datetime(2026, 7, 14, 8, 30),
    datetime(2026, 8, 12, 8, 30),
    datetime(2026, 9, 11, 8, 30),
    datetime(2026, 10, 14, 8, 30),
    datetime(2026, 11, 10, 8, 30),
    datetime(2026, 12, 10, 8, 30),
)

# Bank of Korea's published 2026 statistical release schedule. The live
# calendar remains authoritative; these dates keep the staging calendar useful
# during a temporary BOK outage.
BOK_RELEASE_FALLBACK = {
    "kr-bsi-esi": (
        datetime(2026, 1, 27, 6, 0),
        datetime(2026, 2, 25, 6, 0),
        datetime(2026, 3, 27, 6, 0),
        datetime(2026, 4, 28, 6, 0),
        datetime(2026, 5, 27, 6, 0),
        datetime(2026, 6, 25, 6, 0),
        datetime(2026, 7, 30, 6, 0),
        datetime(2026, 8, 26, 6, 0),
        datetime(2026, 9, 29, 6, 0),
        datetime(2026, 10, 29, 6, 0),
        datetime(2026, 11, 25, 6, 0),
        datetime(2026, 12, 29, 6, 0),
    ),
    "kr-bank-rate": (
        datetime(2026, 1, 27, 12, 0),
        datetime(2026, 2, 27, 12, 0),
        datetime(2026, 3, 27, 12, 0),
        datetime(2026, 4, 28, 12, 0),
        datetime(2026, 5, 29, 12, 0),
        datetime(2026, 6, 26, 12, 0),
        datetime(2026, 7, 28, 12, 0),
        datetime(2026, 8, 26, 12, 0),
        datetime(2026, 9, 30, 12, 0),
        datetime(2026, 10, 29, 12, 0),
        datetime(2026, 11, 25, 12, 0),
        datetime(2026, 12, 29, 12, 0),
    ),
}


def _unfold_ical_lines(payload: str) -> list[str]:
    lines: list[str] = []
    for raw_line in payload.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    return lines


def _unescape_ical_text(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _ical_timezone(property_name: str) -> ZoneInfo:
    match = re.search(r"(?:^|;)TZID=([^;:]+)", property_name, flags=re.IGNORECASE)
    if not match:
        return US_EASTERN
    tzid = match.group(1).strip()
    if tzid.casefold() in {"us-eastern", "us/eastern", "america/new_york"}:
        return US_EASTERN
    try:
        return ZoneInfo(tzid)
    except ZoneInfoNotFoundError:
        return US_EASTERN


def _parse_ical_datetime(property_name: str, raw_value: str) -> datetime | None:
    value = raw_value.strip()
    utc_value = value.endswith("Z")
    if utc_value:
        value = value[:-1]
    match = re.fullmatch(r"(\d{8})T(\d{4}|\d{6})", value)
    if not match:
        return None
    date_part, time_part = match.groups()
    if len(time_part) == 4:
        time_part += "00"
    try:
        parsed = datetime.strptime(f"{date_part}T{time_part}", "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    source_zone = timezone.utc if utc_value else _ical_timezone(property_name)
    return parsed.replace(tzinfo=source_zone).astimezone(KST).replace(tzinfo=None)


def _parse_bls_cpi_calendar(payload: bytes | str) -> list[datetime]:
    text = payload.decode("utf-8-sig", errors="replace") if isinstance(payload, bytes) else payload
    releases: list[datetime] = []
    event: dict[str, tuple[str, str]] | None = None
    for line in _unfold_ical_lines(text):
        if line == "BEGIN:VEVENT":
            event = {}
            continue
        if line == "END:VEVENT":
            if event:
                summary_entry = event.get("SUMMARY")
                starts_entry = event.get("DTSTART")
                summary = _unescape_ical_text(summary_entry[1]).strip() if summary_entry else ""
                if starts_entry and summary.casefold().startswith("consumer price index"):
                    starts_at = _parse_ical_datetime(starts_entry[0], starts_entry[1])
                    if starts_at is not None:
                        releases.append(starts_at)
            event = None
            continue
        if event is None or ":" not in line:
            continue
        property_name, value = line.split(":", 1)
        base_name = property_name.split(";", 1)[0].upper()
        if base_name in {"SUMMARY", "DTSTART"}:
            event[base_name] = (property_name, value)
    return sorted(set(releases))


def _bok_event_key(title: str) -> str | None:
    normalized = re.sub(r"\s+", " ", title).strip()
    if "기업경기조사" in normalized and "경제심리지수" in normalized:
        return "kr-bsi-esi"
    if "금융기관 가중평균금리" in normalized:
        return "kr-bank-rate"
    return None


def _parse_bok_release_calendar(payload: bytes | str) -> list[tuple[str, datetime]]:
    text = payload.decode("utf-8-sig", errors="replace") if isinstance(payload, bytes) else payload
    soup = BeautifulSoup(text, "html.parser")
    releases: set[tuple[str, datetime]] = set()
    for row in soup.select("table tbody tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 3:
            continue
        raw_date = cells[0].get_text(" ", strip=True)
        raw_time = cells[1].get_text(" ", strip=True)
        title = cells[2].get_text(" ", strip=True)
        event_key = _bok_event_key(title)
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", raw_date)
        time_match = re.search(r"(?:^|\s)(\d{1,2}):(\d{2})(?:\s|$)", raw_time)
        if event_key is None or date_match is None or time_match is None:
            continue
        try:
            release = datetime.fromisoformat(
                f"{date_match.group(0)}T{int(time_match.group(1)):02d}:{time_match.group(2)}:00"
            )
        except ValueError:
            continue
        releases.add((event_key, release))
    return sorted(releases, key=lambda item: (item[1], item[0]))


def _fetch_bok_releases(year: int) -> tuple[tuple[str, datetime], ...]:
    response = requests.get(
        BOK_RELEASE_CALENDAR_URL,
        params={"date": f"{year}-01", "menuNo": "200775"},
        headers=BOK_HEADERS,
        timeout=BOK_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    releases = tuple(
        (event_key, release)
        for event_key, release in _parse_bok_release_calendar(response.content)
        if release.year == year
    )
    if not releases:
        raise ValueError("BOK statistical release schedule not found")
    return releases


def _fallback_bok_releases(year: int) -> tuple[tuple[str, datetime], ...]:
    return tuple(
        (event_key, release)
        for event_key, releases in BOK_RELEASE_FALLBACK.items()
        for release in releases
        if release.year == year
    )


def bok_release_occurrences_between(
    event_key: str,
    start: datetime,
    end: datetime,
) -> list[datetime]:
    if event_key not in BOK_EVENT_KEYS or start > end:
        return []
    matches: set[datetime] = set()
    for year in range(start.year, end.year + 1):
        try:
            releases = BOK_CALENDAR_CACHE.get_or_set(
                ("bok_release_calendar", year),
                BOK_CALENDAR_TTL_SECONDS,
                lambda target_year=year: _fetch_bok_releases(target_year),
            )
        except Exception:
            releases = _fallback_bok_releases(year)
        matches.update(
            release
            for release_key, release in releases
            if release_key == event_key and start <= release <= end
        )
    return sorted(matches)


def _fetch_bls_cpi_releases() -> tuple[datetime, ...]:
    response = requests.get(
        BLS_RELEASE_CALENDAR_URL,
        headers=BLS_HEADERS,
        timeout=BLS_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    releases = _parse_bls_cpi_calendar(response.content)
    if not releases:
        raise ValueError("BLS CPI schedule not found in release calendar")
    return tuple(releases)


def _fallback_cpi_releases() -> tuple[datetime, ...]:
    return tuple(
        release.replace(tzinfo=US_EASTERN).astimezone(KST).replace(tzinfo=None)
        for release in BLS_CPI_FALLBACK_EASTERN
    )


def _between(releases: Iterable[datetime], start: datetime, end: datetime) -> list[datetime]:
    return sorted(release for release in releases if start <= release <= end)


def cpi_release_occurrences_between(start: datetime, end: datetime) -> list[datetime]:
    if start > end:
        return []
    try:
        releases = BLS_CALENDAR_CACHE.get_or_set(
            ("bls_cpi_release_calendar",),
            BLS_CALENDAR_TTL_SECONDS,
            _fetch_bls_cpi_releases,
        )
        return _between(releases, start, end)
    except Exception:
        return _between(_fallback_cpi_releases(), start, end)
