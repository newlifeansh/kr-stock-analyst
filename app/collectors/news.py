from __future__ import annotations

import json
import re
from html import unescape
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
NAVER_MOBILE_FRONT_API = "https://m.stock.naver.com/front-api"

# Naver retired the legacy ``finance.naver.com/news/news_list.naver`` and
# per-stock HTML endpoints in 2026. The mobile Finance client uses these JSON
# feeds instead. Multiple legacy labels intentionally map to one feed; the
# fetcher de-duplicates articles by their press/article key.
NAVER_NEWS_FEEDS = {
    "breaking": ("category", "flashnews"),
    "market": ("category", "mainnews"),
    "company": ("category", "ranknews"),
    "global": ("worldnews", "usa"),
    "bond": ("category", "mainnews"),
    "disclosure_memo": ("category", "mainnews"),
    "fx": ("category", "mainnews"),
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


def _naver_get_json(path: str, params: dict[str, object]) -> list[dict[str, object]]:
    response = requests.get(
        f"{NAVER_MOBILE_FRONT_API}/{path.lstrip('/')}",
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://m.stock.naver.com/",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("isSuccess") is not True:
        raise RuntimeError("Naver mobile news API returned an unsuccessful payload")
    result = payload.get("result")
    if not isinstance(result, list):
        raise RuntimeError("Naver mobile news API result is not a list")
    return [row for row in result if isinstance(row, dict)]


def _parse_news_datetime(value: str) -> Optional[datetime]:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        parsed = datetime.strptime(cleaned, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=KST).replace(tzinfo=None)


def _parse_mobile_news_datetime(value: object) -> Optional[datetime]:
    cleaned = re.sub(r"\D", "", str(value or ""))
    for pattern, length in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12)):
        if len(cleaned) != length:
            continue
        try:
            return datetime.strptime(cleaned, pattern).replace(tzinfo=KST).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _mobile_news_item(row: dict[str, object], category: str) -> Optional[NewsListItem]:
    office_id = str(row.get("officeId") or "").strip()
    article_id = str(row.get("articleId") or "").strip()
    title = _clean_news_title(unescape(str(row.get("titleFull") or row.get("title") or "")))
    if not office_id or not article_id or not title:
        return None
    external_id = f"{office_id}:{article_id}"
    return NewsListItem(
        source="naver_finance",
        source_category=category,
        external_id=external_id,
        title=title,
        summary=_clean_news_title(unescape(str(row.get("body") or ""))) or None,
        press_name=_clean_news_title(row.get("officeName")) or None,
        image_url=str(row.get("imageOriginLink") or "").strip() or None,
        detail_url=naver_news_detail_url(external_id),
        published_at=_parse_mobile_news_datetime(row.get("datetime")),
        raw=json.dumps(row, ensure_ascii=False),
    )


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
    seen: set[str] = set()
    fetched_feeds: set[tuple[str, str]] = set()
    source_rows = 0

    for category in categories:
        feed = NAVER_NEWS_FEEDS.get(category)
        if not feed or feed in fetched_feeds:
            continue
        fetched_feeds.add(feed)
        endpoint, value = feed

        stop_category = False
        for page in range(1, max_pages + 1):
            params: dict[str, object] = {"page": page, "pageSize": 20}
            if endpoint == "worldnews":
                params["regionCode"] = value
            else:
                params["category"] = value
            page_rows = _naver_get_json(f"news/{endpoint}", params)
            source_rows += len(page_rows)
            if not page_rows:
                break

            for row in page_rows:
                item = _mobile_news_item(row, category)
                if item is None or item.external_id in seen:
                    continue
                if item.published_at and item.published_at < cutoff:
                    stop_category = True
                    continue
                seen.add(item.external_id)
                items.append(item)

            if stop_category:
                break

    if fetched_feeds and source_rows == 0:
        raise RuntimeError("Naver mobile news API returned no source rows")
    return items


def fetch_naver_stock_news_items(
    code: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> list[NewsListItem]:
    rows = _naver_get_json(
        "news/stock/list",
        {
            "itemCode": str(code).strip(),
            "page": max(1, int(page)),
            "pageSize": max(1, min(100, int(page_size))),
        },
    )
    return [
        item
        for row in rows
        if (item := _mobile_news_item(row, "company")) is not None
    ]


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
        finish_ingestion(
            db,
            run,
            "success",
            rows_loaded=count,
            message=f"categories={','.join(categories)} normalized_items={len(items)}",
        )
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
