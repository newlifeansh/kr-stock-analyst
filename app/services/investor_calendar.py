from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, time, timedelta
import logging
import re
from threading import Lock
import zlib

from bs4 import BeautifulSoup
import requests

from app.services.ttl_cache import TTLCache


logger = logging.getLogger(__name__)

KIND_BASE_URL = "https://kind.krx.co.kr"
KIND_IPO_STATUS_URL = f"{KIND_BASE_URL}/listinvstg/pubofrprogcom.do"
KIND_IPO_CALENDAR_URL = (
    f"{KIND_BASE_URL}/listinvstg/pubofrschdl.do?method=searchPubofrScholMain"
)
KIND_IR_SCHEDULE_URL = f"{KIND_BASE_URL}/corpgeneral/irschedule.do"
KIND_IR_CALENDAR_URL = (
    f"{KIND_IR_SCHEDULE_URL}?method=searchIRScheduleMain&gubun=iRSchedule"
)
KIND_REQUEST_TIMEOUT_SECONDS = 7
KIND_FANOUT_DEADLINE_SECONDS = 5.0
INVESTOR_CALENDAR_CACHE = TTLCache(maxsize=32)
INVESTOR_CALENDAR_CACHE_MISS_LOCK = Lock()
INVESTOR_CALENDAR_TTL_SECONDS = 2 * 60 * 60
INVESTOR_CALENDAR_EMPTY_TTL_SECONDS = 10 * 60
INVESTOR_CALENDAR_HORIZON_DAYS = 7
KIND_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Referer": f"{KIND_BASE_URL}/",
}

EARNINGS_SCHEDULE_KEYWORDS = (
    "실적",
    "earnings",
    "earnings results",
    "결산",
)


@dataclass(frozen=True)
class InvestorScheduleEvent:
    key: str
    kind: str
    company_name: str
    title: str
    summary: str
    starts_on: date
    ends_on: date
    starts_at: time | None
    detail_url: str
    market: str = ""

    @property
    def stable_id(self) -> int:
        return -(zlib.crc32(self.key.encode("utf-8")) or 1)

    def as_briefing_item(self) -> dict[str, object]:
        why_it_matters = (
            "청약 시작·마감일과 증권사별 조건을 미리 확인해요."
            if self.kind == "ipo"
            else "발표 전후 실적 기대가 빠르게 주가에 반영될 수 있어요."
        )
        return {
            "id": self.stable_id,
            "title": self.title,
            "summary": self.summary,
            "detail_url": self.detail_url,
            "published_at": None,
            "status": "확인",
            "why_it_matters": why_it_matters,
            "schedule_kind": self.kind,
        }


def _post_kind(url: str, data: dict[str, str]) -> str:
    response = requests.post(
        url,
        data=data,
        headers=KIND_HEADERS,
        timeout=KIND_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def _parse_iso_date(value: object) -> date | None:
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(value or ""))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(0))
    except ValueError:
        return None


def _parse_date_range(value: object) -> tuple[date, date] | None:
    parsed: list[date] = []
    for raw_date in re.findall(r"\d{4}-\d{2}-\d{2}", str(value or ""))[:2]:
        try:
            parsed.append(date.fromisoformat(raw_date))
        except ValueError:
            continue
    if not parsed:
        return None
    return parsed[0], parsed[-1]


def _parse_clock(value: object) -> time | None:
    match = re.search(r"(?:^|\s)(\d{1,2}):(\d{2})(?:\s|$)", str(value or ""))
    if not match:
        return None
    try:
        return time(int(match.group(1)), int(match.group(2)))
    except ValueError:
        return None


def _date_label(starts_on: date, ends_on: date) -> str:
    if starts_on == ends_on:
        return f"{starts_on.month}월 {starts_on.day}일"
    if starts_on.year == ends_on.year and starts_on.month == ends_on.month:
        return f"{starts_on.month}월 {starts_on.day}~{ends_on.day}일"
    return (
        f"{starts_on.month}월 {starts_on.day}일~"
        f"{ends_on.month}월 {ends_on.day}일"
    )


def _clean_broker_name(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"\(주\)|주식회사", "", text)
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return "·".join(parts[:2])


def _ipo_summary(price: str, broker: str, starts_on: date, ends_on: date) -> str:
    price_text = re.sub(r"[^0-9,]", "", price)
    if price_text and broker:
        return f"공모가는 {price_text}원이고 {broker}에서 청약해요."
    if broker:
        return f"{_date_label(starts_on, ends_on)} 동안 {broker}에서 청약해요."
    return f"{_date_label(starts_on, ends_on)} 동안 공모주 청약을 진행해요."


def _parse_ipo_events(
    html: str,
    *,
    starts_on_or_after: date,
    starts_on_or_before: date,
) -> list[InvestorScheduleEvent]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[InvestorScheduleEvent] = []
    for row in soup.select("table.list tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 9:
            continue
        company_name = cells[0].get("title") or cells[0].get_text(" ", strip=True)
        company_name = re.sub(r"\s+", " ", company_name).strip()
        subscription_range = _parse_date_range(cells[3].get_text(" ", strip=True))
        if not company_name or subscription_range is None:
            continue
        starts_on, ends_on = subscription_range
        if ends_on < starts_on_or_after or starts_on > starts_on_or_before:
            continue
        detail_match = re.search(r"fnDetailView\('([^']+)'", row.get("onclick", ""))
        process_number = detail_match.group(1) if detail_match else ""
        detail_url = KIND_IPO_CALENDAR_URL
        if process_number:
            detail_url = (
                f"{KIND_BASE_URL}/listinvstg/pubofrprogcomdetail.do"
                f"?method=searchProgComDetailMain&bzProcsNo={process_number}"
            )
        price = cells[5].get_text(" ", strip=True)
        broker = _clean_broker_name(cells[8].get_text(" ", strip=True))
        events.append(
            InvestorScheduleEvent(
                key=f"ipo:{company_name}:{starts_on.isoformat()}:{ends_on.isoformat()}",
                kind="ipo",
                company_name=company_name,
                title=f"{_date_label(starts_on, ends_on)} · {company_name} 공모주 청약",
                summary=_ipo_summary(price, broker, starts_on, ends_on),
                starts_on=starts_on,
                ends_on=ends_on,
                starts_at=None,
                detail_url=detail_url,
                market=(cells[0].find("img") or {}).get("alt", ""),
            )
        )
    return events


def _fetch_ipo_events(starts_on_or_after: date, starts_on_or_before: date) -> list[InvestorScheduleEvent]:
    html = _post_kind(
        KIND_IPO_STATUS_URL,
        {
            "method": "searchPubofrProgComSub",
            "forward": "pubofrprogcom_sub",
            "searchMode": "1",
            "searchCodeType": "",
            "currentPageSize": "2000",
            "pageIndex": "1",
            "orderMode": "1",
            "orderStat": "D",
            "searchCorpName": "",
            "searchCorpNameTmp": "",
            "isurCd": "",
            "repIsuSrtCd": "",
            "bzProcsNo": "",
            "detailMarket": "",
            "marketType": "",
            "repMajAgntDesignAdvserComp": "",
            "repMajAgntComp": "",
            "designAdvserComp": "",
            "fromDate": (starts_on_or_after - timedelta(days=550)).isoformat(),
            "toDate": starts_on_or_after.isoformat(),
        },
    )
    return _parse_ipo_events(
        html,
        starts_on_or_after=starts_on_or_after,
        starts_on_or_before=starts_on_or_before,
    )


def _earnings_period(value: str) -> str:
    patterns = (
        r"20\d{2}\s*년\s*(?:회계연도\s*)?(?:[1-4]\s*분기|상반기|하반기|연간)",
        r"(?:[1-4]\s*분기|상반기|하반기|연간)",
        r"(?:Q[1-4]|[12]H)\s*20\d{2}",
        r"20\d{2}(?:Q[1-4]|\s*[12]H)",
    )
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def _earnings_summary(company_name: str, event_title: str, starts_at: time | None) -> str:
    clock = f"{starts_at.hour:02d}:{starts_at.minute:02d}에 " if starts_at else ""
    period = _earnings_period(event_title)
    subject = f"{company_name}의 {period} 실적" if period else f"{company_name}의 실적"
    return f"{clock}{subject}을 발표해요."


def _parse_ir_events(
    html: str,
    *,
    starts_on_or_after: date,
    starts_on_or_before: date,
) -> list[InvestorScheduleEvent]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[InvestorScheduleEvent, bool]] = []
    for row in soup.select("table.list tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        company_link = cells[1].find("a")
        title_link = cells[2].find("a")
        company_name = (
            company_link.get("title") if company_link else cells[1].get_text(" ", strip=True)
        )
        event_title = (
            title_link.get("title") if title_link else cells[2].get_text(" ", strip=True)
        )
        company_name = re.sub(r"\s+", " ", str(company_name or "")).strip()
        event_title = re.sub(r"\s+", " ", str(event_title or "")).strip(" -")
        event_date = _parse_iso_date(cells[4].get_text(" ", strip=True))
        if not company_name or not event_title or event_date is None:
            continue
        if not starts_on_or_after <= event_date <= starts_on_or_before:
            continue
        lowered_title = event_title.casefold()
        if not any(keyword.casefold() in lowered_title for keyword in EARNINGS_SCHEDULE_KEYWORDS):
            continue
        starts_at = _parse_clock(cells[5].get_text(" ", strip=True))
        sequence_match = re.search(r"fnDetailView\('([^']+)'", title_link.get("onclick", "") if title_link else "")
        sequence = sequence_match.group(1) if sequence_match else ""
        market_image = cells[1].find("img")
        market = market_image.get("alt", "") if market_image else ""
        event = InvestorScheduleEvent(
            key=(
                f"earnings:{company_name}:{event_date.isoformat()}:"
                f"{starts_at.isoformat(timespec='minutes') if starts_at else ''}"
            ),
            kind="earnings",
            company_name=company_name,
            title=f"{_date_label(event_date, event_date)} · {company_name} 실적 발표",
            summary=_earnings_summary(company_name, event_title, starts_at),
            starts_on=event_date,
            ends_on=event_date,
            starts_at=starts_at,
            detail_url=(
                f"{KIND_IR_SCHEDULE_URL}?method=searchIRScheduleMain"
                f"&gubun=iRSchedule&irSeq={sequence}"
                if sequence
                else KIND_IR_CALENDAR_URL
            ),
            market=market,
        )
        has_korean_title = bool(re.search(r"[가-힣]", event_title))
        candidates.append((event, has_korean_title))

    deduplicated: dict[str, tuple[InvestorScheduleEvent, bool]] = {}
    for event, has_korean_title in candidates:
        existing = deduplicated.get(event.key)
        if existing is None or (has_korean_title and not existing[1]):
            deduplicated[event.key] = (event, has_korean_title)
    return [event for event, _ in deduplicated.values()]


def _fetch_ir_events(starts_on_or_after: date, starts_on_or_before: date) -> list[InvestorScheduleEvent]:
    html = _post_kind(
        KIND_IR_SCHEDULE_URL,
        {
            "method": "searchIRScheduleSub",
            "forward": "searchirschedule_sub",
            "paxreq": "",
            "outsvcno": "",
            "currentPageSize": "3000",
            "pageIndex": "1",
            "orderMode": "4",
            "orderStat": "A",
            "searchCodeType": "",
            "repIsuSrtCd": "",
            "irSeq": "",
            "searchCorpName": "",
            "resoroomType": "",
            "searchFromDate": starts_on_or_after.isoformat(),
            "searchToDate": starts_on_or_before.isoformat(),
            "marketType": "",
            "searchName": "",
            "title": "",
            "fromDate": starts_on_or_after.isoformat(),
            "toDate": starts_on_or_before.isoformat(),
        },
    )
    return _parse_ir_events(
        html,
        starts_on_or_after=starts_on_or_after,
        starts_on_or_before=starts_on_or_before,
    )


def _event_sort_key(event: InvestorScheduleEvent) -> tuple[date, int, time, str]:
    market_priority = 0 if event.market == "유가증권" else 1
    return event.starts_on, market_priority, event.starts_at or time(23, 59), event.company_name


def upcoming_investor_events(
    as_of: date,
    *,
    horizon_days: int = INVESTOR_CALENDAR_HORIZON_DAYS,
) -> list[InvestorScheduleEvent]:
    through = as_of + timedelta(days=max(0, horizon_days))
    cache_key = ("upcoming_investor_events", as_of.isoformat(), through.isoformat())
    cached = INVESTOR_CALENDAR_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)

    # Cold-cache requests often arrive together when a briefing edition opens.
    # Only one caller should fan out to KIND; waiters re-check the cache after
    # the in-flight caller has published its result.
    with INVESTOR_CALENDAR_CACHE_MISS_LOCK:
        cached = INVESTOR_CALENDAR_CACHE.get(cache_key)
        if cached is not None:
            return list(cached)

        events: list[InvestorScheduleEvent] = []
        degraded = False
        executor = ThreadPoolExecutor(max_workers=2)
        futures = {}
        pending = set()
        try:
            for event_kind, fetcher in (
                ("ipo", _fetch_ipo_events),
                ("earnings", _fetch_ir_events),
            ):
                try:
                    futures[executor.submit(fetcher, as_of, through)] = event_kind
                except Exception as exc:
                    degraded = True
                    logger.warning(
                        "KIND %s schedule fetch could not start: %s",
                        event_kind,
                        exc,
                    )

            done, pending = wait(
                futures,
                timeout=max(0.0, float(KIND_FANOUT_DEADLINE_SECONDS)),
            )
            if pending:
                degraded = True
                logger.warning(
                    "KIND schedule fetch deadline exceeded after %.1fs: %s",
                    KIND_FANOUT_DEADLINE_SECONDS,
                    ", ".join(sorted(futures[future] for future in pending)),
                )
            for future in done:
                event_kind = futures[future]
                try:
                    events.extend(future.result())
                except Exception as exc:
                    degraded = True
                    logger.warning("KIND %s schedule fetch failed: %s", event_kind, exc)
        finally:
            for future in pending:
                future.cancel()
            # A running requests call cannot be cancelled, but it must not hold
            # the briefing response past the aggregate deadline.
            executor.shutdown(wait=False, cancel_futures=True)

        events.sort(key=_event_sort_key)
        ttl_seconds = (
            INVESTOR_CALENDAR_TTL_SECONDS
            if events and not degraded
            else INVESTOR_CALENDAR_EMPTY_TTL_SECONDS
        )
        INVESTOR_CALENDAR_CACHE.set(cache_key, tuple(events), ttl_seconds)
        return events
