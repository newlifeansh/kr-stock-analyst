from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import NewsItem
from app.repository import finish_ingestion, latest_news_items, start_ingestion, upsert_many

KST = ZoneInfo("Asia/Seoul")
NAVER_FINANCE_BASE = "https://finance.naver.com"

NEWS_CATEGORY_URLS = {
    "breaking": "https://finance.naver.com/news/news_list.naver?mode=LSS2D&section_id=101&section_id2=258",
    "market": "https://finance.naver.com/news/news_list.naver?mode=LSS3D&section_id=101&section_id2=258&section_id3=401",
    "company": "https://finance.naver.com/news/news_list.naver?mode=LSS3D&section_id=101&section_id2=258&section_id3=402",
    "global": "https://finance.naver.com/news/news_list.naver?mode=LSS3D&section_id=101&section_id2=258&section_id3=403",
    "bond": "https://finance.naver.com/news/news_list.naver?mode=LSS3D&section_id=101&section_id2=258&section_id3=404",
    "disclosure_memo": "https://finance.naver.com/news/news_list.naver?mode=LSS3D&section_id=101&section_id2=258&section_id3=406",
    "fx": "https://finance.naver.com/news/news_list.naver?mode=LSS3D&section_id=101&section_id2=258&section_id3=429",
}


@dataclass
class NewsListItem:
    source: str
    source_category: str
    external_id: str
    title: str
    summary: Optional[str]
    press_name: Optional[str]
    image_url: Optional[str]
    detail_url: Optional[str]
    published_at: Optional[datetime]
    raw: Optional[str] = None

    def as_row(self) -> dict[str, object]:
        return {
            "source": self.source,
            "source_category": self.source_category,
            "external_id": self.external_id,
            "title": self.title,
            "summary": self.summary,
            "press_name": self.press_name,
            "image_url": self.image_url,
            "detail_url": self.detail_url,
            "published_at": self.published_at,
            "raw": self.raw,
        }


def _naver_get_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    return response.content.decode("euc-kr", errors="ignore")


def _parse_news_datetime(value: str) -> Optional[datetime]:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        parsed = datetime.strptime(cleaned, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=KST).replace(tzinfo=None)


def _extract_news_external_id(href: Optional[str]) -> str:
    if not href:
        return ""
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    article_id = (params.get("article_id") or [""])[0]
    office_id = (params.get("office_id") or [""])[0]
    if article_id and office_id:
        return f"{office_id}:{article_id}"
    if article_id:
        return article_id
    return href


def normalize_naver_news_url(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    normalized = href.replace("%C2%A7ion_", "&section_").replace("§ion_", "&section_")
    return urljoin(NAVER_FINANCE_BASE, normalized)


def parse_naver_news_list_html(html: str, category: str) -> list[NewsListItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[NewsListItem] = []

    for li in soup.select("ul.realtimeNewsList > li.newsList"):
        link = li.select_one("dd.articleSubject a[href]")
        if not link:
            continue

        summary_node = li.select_one("dd.articleSummary")
        summary_text = None
        press_name = None
        published_at = None

        if summary_node:
            summary_copy = BeautifulSoup(str(summary_node), "html.parser")
            press = summary_copy.select_one("span.press")
            wdate = summary_copy.select_one("span.wdate")
            if press:
                press_name = press.get_text(strip=True)
                press.extract()
            if wdate:
                published_at = _parse_news_datetime(wdate.get_text(strip=True))
                wdate.extract()
            for node in summary_copy.select("span.bar"):
                node.extract()
            summary_text = summary_copy.get_text(" ", strip=True) or None

        image = li.select_one("dt.thumb img")
        href = link.get("href")
        detail_url = normalize_naver_news_url(href)
        items.append(
            NewsListItem(
                source="naver_finance",
                source_category=category,
                external_id=_extract_news_external_id(detail_url or href),
                title=link.get("title") or link.get_text(strip=True),
                summary=summary_text,
                press_name=press_name,
                image_url=image.get("src") if image else None,
                detail_url=detail_url,
                published_at=published_at,
                raw=json.dumps(
                    {
                        "category": category,
                        "href": href,
                        "image_url": image.get("src") if image else None,
                    },
                    ensure_ascii=False,
                ),
            )
        )

    return items


def fetch_naver_news_items(
    categories: list[str],
    max_pages: int,
    days_back: int,
    now: Optional[datetime] = None,
) -> list[NewsListItem]:
    now = now or datetime.now(KST)
    cutoff = (now - timedelta(days=days_back)).replace(tzinfo=None)
    items: list[NewsListItem] = []

    for category in categories:
        base_url = NEWS_CATEGORY_URLS.get(category)
        if not base_url:
            continue

        stop_category = False
        for page in range(1, max_pages + 1):
            html = _naver_get_html(f"{base_url}&page={page}")
            page_items = parse_naver_news_list_html(html, category)
            if not page_items:
                break

            for item in page_items:
                if item.published_at and item.published_at < cutoff:
                    stop_category = True
                    continue
                items.append(item)

            if stop_category:
                break

    return items


def collect_news_items(
    db: Session,
    settings: Optional[Settings] = None,
    categories: Optional[list[str]] = None,
    max_pages: Optional[int] = None,
    days_back: Optional[int] = None,
) -> int:
    settings = settings or get_settings()
    categories = categories or settings.news_category_list()
    max_pages = max_pages or settings.news_max_pages
    days_back = days_back or settings.news_days_back

    run = start_ingestion(db, "news", "naver_finance")
    try:
        items = fetch_naver_news_items(
            categories=categories,
            max_pages=max_pages,
            days_back=days_back,
        )
        count = upsert_many(db, NewsItem, [item.as_row() for item in items])
        db.commit()
        finish_ingestion(db, run, "success", rows_loaded=count, message=f"categories={','.join(categories)}")
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def latest_news_events(db: Session, limit: int = 10) -> list[dict[str, object]]:
    items = latest_news_items(db, limit=limit)
    return [
        {
            "event_type": "news",
            "source": item.source,
            "title": item.title,
            "company_name": item.press_name,
            "stock_code": None,
            "url": item.detail_url,
            "published_at": item.published_at,
            "raw": item.raw,
        }
        for item in items
    ]
