from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.config import Settings, get_settings
from app.models import ResearchReport
from app.repository import finish_ingestion, latest_research_reports, start_ingestion, upsert_many

KST = ZoneInfo("Asia/Seoul")
NAVER_FINANCE_BASE = "https://finance.naver.com/research/"

CATEGORY_PATHS = {
    "company": "company_list.naver",
    "industry": "industry_list.naver",
    "market": "market_info_list.naver",
    "economy": "economy_list.naver",
    "invest": "invest_list.naver",
    "debenture": "debenture_list.naver",
}


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


def enrich_company_detail(item: ResearchListItem) -> ResearchListItem:
    if item.source_category != "company" or not item.detail_url:
        return item

    html = _naver_get_html(item.detail_url)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="type_1")
    if not table:
        return item

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
    if pdf_anchor and not item.pdf_url:
        item.pdf_url = pdf_anchor.get("href")

    item.opinion = opinion
    item.target_price = target_price
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
            "url": report.pdf_url or report.detail_url,
            "published_at": report.published_at,
            "raw": report.raw,
        }
        for report in reports
    ]
