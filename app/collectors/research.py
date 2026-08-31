from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.config import Settings, get_settings
from app.models import ResearchReport
from app.repository import finish_ingestion, latest_research_reports, start_ingestion, upsert_many

KST = ZoneInfo("Asia/Seoul")
NAVER_FINANCE_BASE = "https://finance.naver.com/research/"
NAVER_MOBILE_RESEARCH_BASE = "https://m.stock.naver.com/domestic/stock"
STOCKHUB_STOCK_BASE = "https://www.stockhub.kr/stock/"

CATEGORY_PATHS = {
    "company": "company_list.naver",
    "industry": "industry_list.naver",
    "market": "market_info_list.naver",
    "economy": "economy_list.naver",
    "invest": "invest_list.naver",
    "debenture": "debenture_list.naver",
}


def naver_mobile_research_url(stock_code: object, external_id: object) -> Optional[str]:
    """Return Naver's mobile report detail URL when the report identifiers are usable."""
    code = str(stock_code or "").strip()
    report_id = str(external_id or "").strip()
    if not re.fullmatch(r"\d{6}", code) or not re.fullmatch(r"\d+", report_id):
        return None
    return f"{NAVER_MOBILE_RESEARCH_BASE}/{code}/research/{report_id}"


def preferred_research_url(
    stock_code: object,
    external_id: object,
    pdf_url: object,
    detail_url: object,
) -> Optional[str]:
    """Prefer a report-specific mobile page, then a direct PDF, over Naver's desktop page."""
    mobile_url = naver_mobile_research_url(stock_code, external_id)
    if mobile_url:
        return mobile_url
    for candidate in (pdf_url, detail_url):
        normalized = str(candidate or "").strip()
        if normalized:
            return normalized
    return None


@dataclass
class ResearchListItem:
    source: str
    source_category: str
    external_id: str
    title: str
    subject_name: Optional[str]
    company_name: Optional[str]
    stock_code: Optional[str]
    broker_name: Optional[str]
    detail_url: Optional[str]
    pdf_url: Optional[str]
    published_at: Optional[datetime]
    views: Optional[int]
    opinion: Optional[str] = None
    target_price: Optional[Decimal] = None
    raw: Optional[str] = None

    def as_row(self) -> dict[str, object]:
        return {
            "source": self.source,
            "source_category": self.source_category,
            "external_id": self.external_id,
            "title": self.title,
            "subject_name": self.subject_name,
            "company_name": self.company_name,
            "stock_code": self.stock_code,
            "broker_name": self.broker_name,
            "opinion": self.opinion,
            "target_price": self.target_price,
            "detail_url": self.detail_url,
            "pdf_url": self.pdf_url,
            "published_at": self.published_at,
            "views": self.views,
            "raw": self.raw,
        }


def _naver_get_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    return response.content.decode("euc-kr", errors="ignore")


def _stockhub_get_html(url: str) -> str:
    """Fetch the public stockhub page used as a supplementary report index."""
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    response.raise_for_status()
    return response.text


def _parse_naver_date(value: str) -> Optional[datetime]:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        parsed = datetime.strptime(cleaned, "%y.%m.%d")
    except ValueError:
        try:
            parsed = datetime.strptime(cleaned, "%Y.%m.%d")
        except ValueError:
            return None
    return parsed.replace(tzinfo=KST).replace(tzinfo=None)


def _parse_int(value: str) -> Optional[int]:
    digits = value.replace(",", "").strip()
    if not digits:
        return None
    if digits.isdigit():
        return int(digits)
    return None


def _parse_decimal(value: str) -> Optional[Decimal]:
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _extract_external_id(href: Optional[str]) -> str:
    if not href:
        return ""
    if "nid=" in href:
        return href.split("nid=", 1)[1].split("&", 1)[0]
    return href


def parse_naver_listing_html(html: str, category: str) -> list[ResearchListItem]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="type_1")
    if not table:
        return []

    items: list[ResearchListItem] = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue

        anchors = tr.find_all("a", href=True)
        if not anchors:
            continue

        company_name: Optional[str] = None
        stock_code: Optional[str] = None
        subject_name: Optional[str] = None
        title_anchor = None
        pdf_url = None

        if category == "company":
            if len(cells) < 6:
                continue
            company_anchor = anchors[0]
            title_anchor = anchors[1] if len(anchors) > 1 else None
            pdf_anchor = next((anchor for anchor in anchors if "stock-research" in anchor.get("href", "")), None)
            company_name = company_anchor.get_text(strip=True)
            href = company_anchor.get("href", "")
            if "code=" in href:
                stock_code = href.split("code=", 1)[1].split("&", 1)[0]
            broker_name = cells[2].get_text(strip=True)
            published_text = cells[4].get_text(strip=True)
            views_text = cells[5].get_text(strip=True)
        else:
            if len(cells) < 5:
                continue
            title_anchor = anchors[0]
            pdf_anchor = next((anchor for anchor in anchors if "stock-research" in anchor.get("href", "")), None)
            subject_name = cells[0].get_text(strip=True) if category == "industry" else None
            broker_name = cells[2 if category == "industry" else 1].get_text(strip=True)
            published_text = cells[4 if category == "industry" else 3].get_text(strip=True)
            views_text = cells[5 if category == "industry" else 4].get_text(strip=True)

        if title_anchor is None:
            continue

        detail_href = title_anchor.get("href")
        detail_url = urljoin(NAVER_FINANCE_BASE, detail_href) if detail_href else None
        pdf_url = pdf_anchor.get("href") if pdf_anchor else None
        external_id = _extract_external_id(detail_href)

        items.append(
            ResearchListItem(
                source="naver_finance",
                source_category=category,
                external_id=external_id,
                title=title_anchor.get_text(strip=True),
                subject_name=subject_name,
                company_name=company_name,
                stock_code=stock_code,
                broker_name=broker_name,
                detail_url=detail_url,
                pdf_url=pdf_url,
                published_at=_parse_naver_date(published_text),
                views=_parse_int(views_text),
                raw=json.dumps(
                    {
                        "category": category,
                        "title": title_anchor.get_text(strip=True),
                        "detail_href": detail_href,
                        "pdf_url": pdf_url,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    return items


def fetch_company_detail_fields(detail_url: str) -> dict[str, object]:
    html = _naver_get_html(detail_url)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="type_1")
    if not table:
        return {}

    text = table.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    opinion = None
    target_price = None
    for idx, line in enumerate(lines):
        if line == "투자의견" and idx + 1 < len(lines):
            opinion = lines[idx + 1]
        if line == "목표가" and idx + 1 < len(lines):
            target_price = _parse_decimal(lines[idx + 1])

    pdf_anchor = next((anchor for anchor in table.find_all("a", href=True) if ".pdf" in anchor.get("href", "").lower()), None)
    return {
        "opinion": opinion,
        "target_price": target_price,
        "pdf_url": pdf_anchor.get("href") if pdf_anchor else None,
    }


def enrich_company_detail(item: ResearchListItem) -> ResearchListItem:
    if item.source_category != "company" or not item.detail_url:
        return item

    fields = fetch_company_detail_fields(item.detail_url)
    if fields.get("pdf_url") and not item.pdf_url:
        item.pdf_url = str(fields["pdf_url"])

    item.opinion = fields.get("opinion")
    item.target_price = fields.get("target_price")
    return item


def fetch_naver_research_reports(
    categories: list[str],
    max_pages: int,
    days_back: int,
    include_detail: bool = True,
    now: Optional[datetime] = None,
) -> list[ResearchListItem]:
    now = now or datetime.now(KST)
    cutoff = (now - timedelta(days=days_back)).replace(tzinfo=None)
    reports: list[ResearchListItem] = []

    for category in categories:
        path = CATEGORY_PATHS.get(category)
        if not path:
            continue

        stop_category = False
        for page in range(1, max_pages + 1):
            html = _naver_get_html(f"{NAVER_FINANCE_BASE}{path}?page={page}")
            page_items = parse_naver_listing_html(html, category)
            if not page_items:
                break

            for item in page_items:
                if item.published_at and item.published_at < cutoff:
                    stop_category = True
                    continue
                if include_detail and category == "company":
                    item = enrich_company_detail(item)
                reports.append(item)

            if stop_category:
                break

    return reports


def fetch_naver_company_reports_for_stock(
    stock_code: object,
    days_back: int = 180,
    max_pages: int = 3,
    include_detail: bool = True,
    now: Optional[datetime] = None,
) -> list[ResearchListItem]:
    """Fetch the company-report history for one code using Naver's item filter.

    The general research board is ordered globally, so a small global page
    window can miss perfectly valid reports for less frequently covered names.
    Naver exposes an itemCode filter that keeps the same report metadata and
    links while making the lookup deterministic for a stock detail page.
    """
    code = str(stock_code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return []
    now = now or datetime.now(KST)
    cutoff = (now - timedelta(days=max(1, int(days_back)))).replace(tzinfo=None)
    reports: list[ResearchListItem] = []
    page_limit = max(1, min(int(max_pages), 20))
    for page in range(1, page_limit + 1):
        query = urlencode({"searchType": "itemCode", "itemCode": code, "page": page})
        html = _naver_get_html(f"{NAVER_FINANCE_BASE}{CATEGORY_PATHS['company']}?{query}")
        page_items = parse_naver_listing_html(html, "company")
        if not page_items:
            break
        stop = False
        for item in page_items:
            if item.stock_code != code:
                continue
            if item.published_at and item.published_at < cutoff:
                stop = True
                continue
            reports.append(item)
        if stop:
            break
    if include_detail and reports:
        # A stock can have dozens of reports in the requested window.  Detail
        # pages are independent, so fetching them concurrently keeps a first
        # stock-detail request responsive without changing the returned data.
        def enrich_safely(item: ResearchListItem) -> ResearchListItem:
            try:
                return enrich_company_detail(item)
            except requests.RequestException:
                # Keep the listing row and its PDF/detail link even when one
                # broker detail page is temporarily unavailable.
                return item

        worker_count = min(8, len(reports))
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="research-detail") as executor:
            reports = list(executor.map(enrich_safely, reports))
    return reports


def _parse_stockhub_report_date(value: object) -> Optional[datetime]:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    try:
        return datetime.strptime(cleaned[:10], "%Y-%m-%d")
    except ValueError:
        return None


def fetch_stockhub_reports_for_stock(
    html: str,
    stock_code: object,
    days_back: int = 180,
    now: Optional[datetime] = None,
) -> list[ResearchListItem]:
    """Parse Stockhub's embedded analyst report list for one stock.

    The page is server-rendered and carries a small JSON ``analystReports``
    payload.  We only consume report metadata and retain each broker's public
    source URL; no Stockhub page content is copied into the application.
    """
    code = str(stock_code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return []
    now = now or datetime.now(KST)
    cutoff = (now - timedelta(days=max(1, int(days_back)))).replace(tzinfo=None)
    match = re.search(
        r'\\?"analystReports\\?"\s*:\s*(\[.*?\])\s*,\s*\\?"(?:usConsensus|forwardConsensus)\\?"',
        html,
        flags=re.DOTALL,
    )
    if not match:
        return []
    try:
        reports = json.loads(match.group(1).replace('\\"', '"'))
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(reports, list):
        return []

    items: list[ResearchListItem] = []
    for report in reports:
        if not isinstance(report, dict) or str(report.get("ticker") or "").strip() != code:
            continue
        published_at = _parse_stockhub_report_date(report.get("report_date"))
        if published_at and published_at < cutoff:
            continue
        report_id = str(report.get("id") or "").strip()
        if not report_id:
            continue
        title = str(report.get("report_title") or "").strip()
        broker_name = str(report.get("broker") or "").strip() or None
        source_url = str(report.get("source_url") or "").strip() or None
        pdf_url = str(report.get("pdf_url") or "").strip() or None
        target_raw = report.get("target_price")
        target_price = _parse_decimal(str(target_raw)) if target_raw not in (None, "") else None
        items.append(
            ResearchListItem(
                source="stockhub",
                source_category="company",
                external_id=f"stockhub-{report_id}",
                title=title or f"{broker_name or '증권사'} 리포트",
                subject_name=None,
                company_name=None,
                stock_code=code,
                broker_name=broker_name,
                detail_url=source_url,
                pdf_url=pdf_url,
                published_at=published_at,
                views=None,
                opinion=str(report.get("opinion_raw") or report.get("opinion_normalized") or "").strip() or None,
                target_price=target_price,
                raw=json.dumps(
                    {
                        "source": "stockhub",
                        "report_id": report_id,
                        "source_url": source_url,
                        "pdf_url": pdf_url,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    return items


def ensure_stock_research_reports(
    db: Session,
    stock_code: object,
    days_back: int = 180,
    max_pages: int = 3,
    include_detail: bool = True,
) -> int:
    """Backfill a stock's report history when the shared board missed it.

    Naver is the canonical report feed, but its global board can omit less
    frequently covered stocks.  Stockhub's public analyst-report index is
    queried as a supplementary source so broker reports (for example DB and
    BNK reports for GS) are not silently lost when Naver has only a partial
    listing.
    """
    code = str(stock_code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return 0
    cutoff = (datetime.now(KST) - timedelta(days=max(1, int(days_back)))).replace(tzinfo=None)
    items: list[ResearchListItem] = []
    try:
        items.extend(
            fetch_naver_company_reports_for_stock(
                code,
                days_back=days_back,
                max_pages=max_pages,
                include_detail=include_detail,
            )
        )
    except requests.RequestException:
        # Keep the supplementary source available during a transient Naver
        # failure.  The route-level caller also logs a complete failure.
        pass
    try:
        stockhub_html = _stockhub_get_html(f"{STOCKHUB_STOCK_BASE}{code}")
        items.extend(fetch_stockhub_reports_for_stock(stockhub_html, code, days_back=days_back))
    except requests.RequestException:
        pass
    if not items:
        return 0

    # Avoid a second copy when both feeds expose the same broker/date/title.
    existing = latest_research_reports(db, limit=500, stock_code=code, from_at=cutoff)
    seen: set[tuple[str, str, str]] = set()
    for report in existing:
        seen.add(
            (
                (report.broker_name or "").strip().casefold(),
                report.published_at.date().isoformat() if report.published_at else "",
                (report.title or "").strip().casefold(),
            )
        )
    unique_items: list[ResearchListItem] = []
    for item in items:
        key = (
            (item.broker_name or "").strip().casefold(),
            item.published_at.date().isoformat() if item.published_at else "",
            (item.title or "").strip().casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    if not unique_items:
        return 0
    count = upsert_many(db, ResearchReport, [item.as_row() for item in unique_items])
    db.commit()
    return count


def collect_research_reports(
    db: Session,
    settings: Optional[Settings] = None,
    categories: Optional[list[str]] = None,
    max_pages: Optional[int] = None,
    days_back: Optional[int] = None,
    include_detail: Optional[bool] = None,
) -> int:
    settings = settings or get_settings()
    categories = categories or settings.research_category_list()
    max_pages = max_pages or settings.research_max_pages
    days_back = days_back or settings.research_days_back
    include_detail = settings.research_include_detail if include_detail is None else include_detail

    run = start_ingestion(db, "research", "naver_finance")
    try:
        items = fetch_naver_research_reports(
            categories=categories,
            max_pages=max_pages,
            days_back=days_back,
            include_detail=include_detail,
        )
        count = upsert_many(db, ResearchReport, [item.as_row() for item in items])
        db.commit()
        finish_ingestion(db, run, "success", rows_loaded=count, message=f"categories={','.join(categories)}")
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def latest_report_events(db: Session, limit: int = 10) -> list[dict[str, object]]:
    reports = latest_research_reports(db, limit=limit)
    return [
        {
            "event_type": "research_report",
            "source": report.source,
            "title": report.title,
            "company_name": report.company_name or report.subject_name,
            "stock_code": report.stock_code,
            "url": preferred_research_url(
                report.stock_code,
                report.external_id,
                report.pdf_url,
                report.detail_url,
            ),
            "published_at": report.published_at,
            "raw": report.raw,
        }
        for report in reports
    ]
