from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from app.models import StockMaster

NAVER_BOARD_URL = "https://finance.naver.com/item/board.naver"
NAVER_BOARD_SOURCE = "naver_finance_board"
THREADS_SOURCE = "threads_search"
THREADS_SEARCH_URL = "https://www.threads.com/search?q={query}"

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


def _threads_query(stock: StockMaster) -> str:
    return f"{stock.name} 주식"


def threads_search_url(stock: StockMaster) -> str:
    return THREADS_SEARCH_URL.format(query=quote_plus(_threads_query(stock)))


def _build_threads_provider(stock: StockMaster) -> dict[str, object]:
    return {
        "key": "threads",
        "label": "Threads",
        "source": THREADS_SOURCE,
        "configured": False,
        "search_url": threads_search_url(stock),
        "more_label": "Threads에서 더 보기 ↗",
        "message": "Threads는 공개 검색 링크로 먼저 연결했습니다. Meta API를 붙이면 종목별 실시간 글까지 바로 불러올 수 있습니다.",
        "items": [],
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
        rows.append(
            {
                "provider_key": "naver_board",
                "post_id": href.split("nid=")[-1].split("&")[0] if "nid=" in href else href,
                "title": title,
                "text": title,
                "author_name": author_name or "네이버 종토방",
                "username": None,
                "author_profile_image_url": image.get("src") if image else None,
                "url": urljoin("https://finance.naver.com", href),
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
    search_url = f"{NAVER_BOARD_URL}?code={stock.code}"
    try:
        items = _fetch_naver_board_rows(stock, limit, timeout_seconds)
        return {
            "key": "naver_board",
            "label": "네이버 종토방",
            "source": NAVER_BOARD_SOURCE,
            "configured": True,
            "search_url": search_url,
            "more_label": "종토방 더 보기 ↗",
            "message": (
                f"최근 글 {len(items)}건"
                if items
                else "최근 글을 찾지 못했습니다. 종토방 원문에서 직접 확인해 주세요."
            ),
            "items": items,
        }
    except Exception:
        return {
            "key": "naver_board",
            "label": "네이버 종토방",
            "source": NAVER_BOARD_SOURCE,
            "configured": False,
            "search_url": search_url,
            "more_label": "종토방 더 보기 ↗",
            "message": "네이버 종토방을 불러오지 못했습니다. 원문 링크에서 직접 확인해 주세요.",
            "items": [],
        }


def build_stock_community_feed(
    stock: StockMaster,
    *,
    limit: int = 12,
    timeout_seconds: int = 8,
) -> dict[str, object]:
    limit = max(1, min(20, limit))
    providers = [
        _build_naver_provider(stock, min(limit, 8), timeout_seconds),
        _build_threads_provider(stock),
    ]
    return {
        "code": stock.code,
        "name": stock.name,
        "as_of": datetime.utcnow(),
        "message": "커뮤니티 글은 사실 확인 전 시장 반응 참고용으로만 확인하세요.",
        "providers": providers,
    }
