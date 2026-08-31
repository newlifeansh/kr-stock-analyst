from __future__ import annotations

import json
import re
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
NAVER_NEWS_ARTICLE_BASE = "https://n.news.naver.com/mnews/article"

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
            "detail_url": preferred_news_url(self.source, self.external_id, self.detail_url),
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


def _clean_news_title(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _preferred_news_title(link: object) -> str:
    """Prefer visible copy when a malformed title attribute is clipped at a quote."""
    visible_title = _clean_news_title(link.get_text(" ", strip=True))
    attribute_title = _clean_news_title(link.get("title"))
    candidates = [candidate for candidate in (visible_title, attribute_title) if candidate]
    return max(candidates, key=lambda candidate: (len(candidate), candidate == visible_title), default="")


def naver_news_detail_url(external_id: object) -> Optional[str]:
    """Build a stable Naver article URL from the stored press/article key."""
    raw = str(external_id or "").strip()
    if ":" not in raw:
        return None
    office_id, article_id = (part.strip() for part in raw.split(":", 1))
    if not re.fullmatch(r"\d+", office_id) or not re.fullmatch(r"\d+", article_id):
        return None
    return f"{NAVER_NEWS_ARTICLE_BASE}/{office_id}/{article_id}"


def _naver_article_url_from_candidate(candidate: str) -> Optional[str]:
    parsed = urlparse(candidate)
    path_match = re.fullmatch(r"/(?:mnews/)?article/(\d+)/(\d+)/?", parsed.path)
    if parsed.hostname in {"n.news.naver.com", "news.naver.com"} and path_match:
        office_id, article_id = path_match.groups()
        return f"{NAVER_NEWS_ARTICLE_BASE}/{office_id}/{article_id}"
    params = parse_qs(parsed.query)
    article_id = (params.get("article_id") or [""])[0]
    office_id = (params.get("office_id") or [""])[0]
    if re.fullmatch(r"\d+", office_id) and re.fullmatch(r"\d+", article_id):
        return f"{NAVER_NEWS_ARTICLE_BASE}/{office_id}/{article_id}"
    return None


def preferred_news_url(
    source: object,
    external_id: object,
    detail_url: object,
) -> Optional[str]:
    """Prefer a Naver article detail URL over a section or home URL."""
    candidate = str(detail_url or "").strip()
    if str(source or "").strip() == "naver_finance":
        normalized = normalize_naver_news_url(candidate) if candidate else None
        if normalized:
            article_url = _naver_article_url_from_candidate(normalized)
            if article_url:
                return article_url
        canonical = naver_news_detail_url(external_id)
        if canonical:
            return canonical
    return candidate or None


def parse_naver_news_list_html(html: str, category: str) -> list[NewsListItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[NewsListItem] = []

    for li in soup.select("ul.realtimeNewsList > li.newsList"):
        # Naver groups several articles inside one ``li.newsList``. Text-only
        # stories use ``dt.articleSubject`` while thumbnail stories use
        # ``dd.articleSubject``. Pair every subject with its own next summary;
        # selecting the first nodes from the whole list item mixes articles.
        for subject_node in li.select("dt.articleSubject, dd.articleSubject"):
            link = subject_node.select_one("a[href]")
            if not link:
                continue

            next_node = subject_node.find_next_sibling()
            summary_node = (
                next_node
                if next_node
                and next_node.name == "dd"
                and "articleSummary" in (next_node.get("class") or [])
                else None
            )
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

            image = None
            previous_node = subject_node.find_previous_sibling()
            if (
                previous_node
                and previous_node.name == "dt"
                and "thumb" in (previous_node.get("class") or [])
            ):
                image = previous_node.select_one("img")

            href = link.get("href")
            detail_url = normalize_naver_news_url(href)
            items.append(
                NewsListItem(
                    source="naver_finance",
                    source_category=category,
                    external_id=_extract_news_external_id(detail_url or href),
                    title=_preferred_news_title(link),
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
            "url": preferred_news_url(item.source, item.external_id, item.detail_url),
            "published_at": item.published_at,
            "raw": item.raw,
        }
        for item in items
    ]
