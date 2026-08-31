from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qs, quote, quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

from app.config import Settings
from app.models import StockMaster

NAVER_BOARD_URL = "https://finance.naver.com/item/board.naver"
NAVER_MOBILE_STOCK_URL = "https://m.stock.naver.com/domestic/stock"
NAVER_BOARD_SOURCE = "naver_finance_board"
THREADS_API_SOURCE = "threads_api"
THREADS_SEARCH_SOURCE = "threads_search"
THREADS_SEARCH_URL = "https://www.threads.com/search?q={query}"
THREADS_SEARCH_PATH = "/keyword_search"
THREADS_FIELDS = "id,text,permalink,username,timestamp,profile_picture_url"

POSITIVE_WORDS = (
    "상승",
    "강세",
    "호재",
    "수주",
    "흑자",
    "성장",
    "돌파",
    "상향",
    "매수",
)
NEGATIVE_WORDS = (
    "하락",
    "약세",
    "악재",
    "적자",
    "급락",
    "하향",
    "매도",
    "리스크",
    "우려",
)

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.naver.com/",
}


def _impact(text: str) -> str:
    positive = sum(word in text for word in POSITIVE_WORDS)
    negative = sum(word in text for word in NEGATIVE_WORDS)
    if positive > negative:
        return "호재"
    if negative > positive:
        return "악재"
    return "중립"


def _to_int(value: str) -> int:
    digits = "".join(char for char in str(value or "") if char.isdigit())
    return int(digits) if digits else 0


def _parse_naver_datetime(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y.%m.%d %H:%M")
    except ValueError:
        return None


def _naver_board_post_id(href: str) -> str:
    parsed = urlparse(str(href or "").strip())
    query_post_ids = parse_qs(parsed.query).get("nid") or []
    if query_post_ids:
        return str(query_post_ids[0]).strip()
    path_parts = [part for part in parsed.path.split("/") if part]
    for marker in ("discussion", "discuss"):
        if marker in path_parts:
            marker_index = path_parts.index(marker)
            if marker_index + 1 < len(path_parts):
                return path_parts[marker_index + 1].strip()
    return ""


def naver_mobile_discussion_url(stock_code: str, href: str) -> str:
    post_id = _naver_board_post_id(href)
    if not post_id:
        return ""
    return (
        f"{NAVER_MOBILE_STOCK_URL}/{quote(str(stock_code), safe='')}"
        f"/discussion/{quote(post_id, safe='')}"
    )


def _threads_query_candidates(stock: StockMaster) -> list[str]:
    candidates = [
        stock.name,
        stock.code,
        f"{stock.name} 주식",
        f"{stock.name} 종목",
        f"{stock.name} 실적",
        f"{stock.name} 공시",
        f"#{stock.name}",
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        compact = " ".join(str(candidate or "").split()).strip()
        if not compact or compact in seen:
            continue
        seen.add(compact)
        unique.append(compact)
    return unique


def threads_search_url(stock: StockMaster) -> str:
    return THREADS_SEARCH_URL.format(query=quote_plus(_threads_query_candidates(stock)[0]))


def _parse_threads_datetime(value: object) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _threads_title(text: str) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= 90:
        return compact
    return f"{compact[:89].rstrip()}…"


def _fetch_threads_rows_for_query(
    query: str,
    settings: Settings,
    limit: int,
    seen: set[str],
) -> list[dict[str, object]]:
    base_url = settings.threads_api_base_url.rstrip("/")
    response = requests.get(
        f"{base_url}{THREADS_SEARCH_PATH}",
        params={
            "q": query,
            "search_type": str(settings.threads_feed_search_type or "RECENT").upper(),
            "fields": THREADS_FIELDS,
            "limit": max(1, min(settings.threads_feed_max_results, limit)),
        },
        headers={"Authorization": f"Bearer {settings.threads_access_token}"},
        timeout=max(1, settings.threads_feed_timeout_seconds),
    )
    response.raise_for_status()
    payload = response.json()

    rows: list[dict[str, object]] = []
    for item in payload.get("data") or []:
        post_id = str(item.get("id") or "").strip()
        text = " ".join(str(item.get("text") or "").split())
        if not post_id or not text or post_id in seen:
            continue
        seen.add(post_id)
        username = str(item.get("username") or "").strip()
        rows.append(
            {
                "provider_key": "threads",
                "post_id": post_id,
                "title": _threads_title(text),
                "text": text,
                "author_name": username or "Threads 사용자",
                "username": username or None,
                "author_profile_image_url": item.get("profile_picture_url") or None,
                "url": item.get("permalink") or None,
                "created_at": _parse_threads_datetime(item.get("timestamp")),
                "like_count": 0,
                "dislike_count": 0,
                "reply_count": 0,
                "repost_count": 0,
                "view_count": 0,
                "impact": _impact(text),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _fetch_threads_rows(
    stock: StockMaster,
    settings: Settings,
    limit: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    last_error: Exception | None = None
    for query in _threads_query_candidates(stock):
        if len(rows) >= limit:
            break
        try:
            query_rows = _fetch_threads_rows_for_query(query, settings, limit - len(rows), seen)
        except Exception as exc:  # pragma: no cover - network failure path is exercised through fallback
            last_error = exc
            continue
        rows.extend(query_rows)
        seen.update(row["post_id"] for row in query_rows if row.get("post_id"))
    if rows:
        return rows[:limit]
    if last_error is not None:
        raise last_error
    return rows


def _build_threads_provider(
    stock: StockMaster,
    settings: Settings,
    limit: int,
) -> dict[str, object]:
    search_url = threads_search_url(stock)
    fallback = {
        "key": "threads",
        "label": "쓰레드",
        "source": THREADS_SEARCH_SOURCE,
        "configured": False,
        "search_url": search_url,
        "more_label": "쓰레드 검색 ↗",
        "message": "Threads 연결 전에는 공개 검색 링크만 제공합니다.",
        "items": [],
    }
    if not settings.threads_feed_enabled or not settings.threads_access_token:
        return fallback

    try:
        items = _fetch_threads_rows(stock, settings, limit)
    except Exception:
        return {
            **fallback,
            "message": "Threads 게시물을 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.",
        }

    return {
        "key": "threads",
        "label": "쓰레드",
        "source": THREADS_API_SOURCE,
        "configured": True,
        "search_url": search_url,
        "more_label": "쓰레드 원문",
        "message": f"최근 글 {len(items)}건" if items else "최근 글이 없습니다.",
        "items": items,
    }


def _fetch_naver_board_rows(stock: StockMaster, limit: int, timeout_seconds: int) -> list[dict[str, object]]:
    response = requests.get(
        NAVER_BOARD_URL,
        params={"code": stock.code, "page": 1},
        headers=NAVER_HEADERS,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.select_one("table.type2")
    if table is None:
        return []

    rows: list[dict[str, object]] = []
    for tr in table.select("tr"):
        title_cell = tr.select_one("td.title")
        link = title_cell.select_one("a") if title_cell else None
        cells = tr.select("td")
        if link is None or len(cells) < 6:
            continue
        title = str(link.get("title") or link.get_text(" ", strip=True)).strip()
        href = str(link.get("href") or "").strip()
        if not title or not href:
            continue
        author_cell = cells[2]
        author_name = author_cell.get_text(" ", strip=True)
        image = author_cell.select_one("img")
        post_id = _naver_board_post_id(href)
        rows.append(
            {
                "provider_key": "naver_board",
                "post_id": post_id or href,
                "title": title,
                "text": title,
                "author_name": author_name or "네이버 종토방",
                "username": None,
                "author_profile_image_url": image.get("src") if image else None,
                "url": naver_mobile_discussion_url(stock.code, href),
                "created_at": _parse_naver_datetime(cells[0].get_text(" ", strip=True)),
                "like_count": _to_int(cells[4].get_text(" ", strip=True)),
                "dislike_count": _to_int(cells[5].get_text(" ", strip=True)),
                "reply_count": 0,
                "repost_count": 0,
                "view_count": _to_int(cells[3].get_text(" ", strip=True)),
                "impact": _impact(title),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _build_naver_provider(stock: StockMaster, limit: int, timeout_seconds: int) -> dict[str, object]:
    search_url = f"{NAVER_MOBILE_STOCK_URL}/{quote(stock.code, safe='')}/discussion"
    try:
        items = _fetch_naver_board_rows(stock, limit, timeout_seconds)
        return {
            "key": "naver_board",
            "label": "네이버",
            "source": NAVER_BOARD_SOURCE,
            "configured": True,
            "search_url": search_url,
            "more_label": "종토방 더 보기",
            "message": (
                f"최근 글 {len(items)}건"
                if items
                else "최근 글을 찾지 못했습니다. 종토방 바로가기에서 직접 확인해 주세요."
            ),
            "items": items,
        }
    except Exception:
        return {
            "key": "naver_board",
            "label": "네이버",
            "source": NAVER_BOARD_SOURCE,
            "configured": False,
            "search_url": search_url,
            "more_label": "종토방 더 보기",
            "message": "네이버 종토방을 불러오지 못했습니다. 종토방 바로가기에서 직접 확인해 주세요.",
            "items": [],
        }


def build_stock_community_feed(
    stock: StockMaster,
    settings: Settings,
    *,
    limit: int = 12,
    timeout_seconds: int = 8,
) -> dict[str, object]:
    limit = max(1, min(20, limit))
    providers = [
        _build_naver_provider(stock, min(limit, 8), timeout_seconds),
        _build_threads_provider(stock, settings, min(limit, settings.threads_feed_max_results)),
    ]
    return {
        "code": stock.code,
        "name": stock.name,
        "as_of": datetime.utcnow(),
        "message": "커뮤니티 글은 사실 확인 전 시장 반응 참고용으로만 확인하세요.",
        "providers": providers,
    }
