from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

import requests
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import NewsItem, StockMaster
from app.repository import upsert_many

X_RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
X_SOURCE = "x_api"

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


def _category(code: str) -> str:
    return f"stock_x:{code}"


def _parse_datetime(value: object) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _impact(text: str) -> str:
    positive = sum(word in text for word in POSITIVE_WORDS)
    negative = sum(word in text for word in NEGATIVE_WORDS)
    if positive > negative:
        return "호재"
    if negative > positive:
        return "악재"
    return "중립"


def stock_x_query(stock: StockMaster) -> str:
    return (
        f'"{stock.name}" (주식 OR 주가 OR 증권 OR 실적 OR 공시 OR 투자) '
        "lang:ko -is:retweet -is:reply"
    )


def stock_x_search_url(stock: StockMaster) -> str:
    return f"https://x.com/search?q={quote_plus(stock_x_query(stock))}&src=typed_query&f=live"


def _stored_rows(db: Session, code: str, limit: int) -> list[NewsItem]:
    return list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.source == X_SOURCE, NewsItem.source_category == _category(code))
            .order_by(NewsItem.published_at.desc(), NewsItem.id.desc())
            .limit(limit)
        )
    )


def _row_payload(row: NewsItem) -> dict[str, object]:
    raw: dict[str, object] = {}
    if row.raw:
        try:
            parsed = json.loads(row.raw)
            if isinstance(parsed, dict):
                raw = parsed
        except (TypeError, ValueError):
            pass
    username = str(raw.get("username") or "").lstrip("@")
    return {
        "post_id": row.external_id,
        "text": row.summary or row.title,
        "author_name": raw.get("author_name") or row.press_name or username or "X 사용자",
        "username": username or None,
        "author_profile_image_url": raw.get("author_profile_image_url"),
        "url": row.detail_url,
        "created_at": row.published_at,
        "like_count": int(raw.get("like_count") or 0),
        "repost_count": int(raw.get("repost_count") or 0),
        "reply_count": int(raw.get("reply_count") or 0),
        "quote_count": int(raw.get("quote_count") or 0),
        "impact": raw.get("impact") or _impact(row.summary or row.title),
    }


def _cached_payload(
    db: Session,
    stock: StockMaster,
    *,
    limit: int,
    configured: bool,
    message: Optional[str] = None,
    source: str = X_SOURCE,
) -> dict[str, object]:
    rows = _stored_rows(db, stock.code, limit)
    return {
        "code": stock.code,
        "name": stock.name,
        "configured": configured,
        "source": source,
        "query": stock_x_query(stock),
        "search_url": stock_x_search_url(stock),
        "as_of": datetime.utcnow(),
        "message": message,
        "items": [_row_payload(row) for row in rows],
    }


def _fetch_recent_posts(stock: StockMaster, settings: Settings, limit: int) -> list[dict[str, object]]:
    max_results = max(10, min(100, limit))
    response = requests.get(
        X_RECENT_SEARCH_URL,
        params={
            "query": stock_x_query(stock),
            "max_results": max_results,
            "tweet.fields": "author_id,created_at,lang,public_metrics",
            "expansions": "author_id",
            "user.fields": "name,username,profile_image_url,verified",
        },
        headers={"Authorization": f"Bearer {settings.x_bearer_token}"},
        timeout=settings.x_feed_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    users = {
        str(user.get("id")): user
        for user in payload.get("includes", {}).get("users", [])
        if isinstance(user, dict) and user.get("id")
    }
    posts: list[dict[str, object]] = []
    for post in payload.get("data", []):
        if not isinstance(post, dict) or not post.get("id") or not post.get("text"):
            continue
        author = users.get(str(post.get("author_id")), {})
        username = str(author.get("username") or "").lstrip("@")
        metrics = post.get("public_metrics") if isinstance(post.get("public_metrics"), dict) else {}
        post_id = str(post["id"])
        text = str(post["text"]).strip()
        posts.append(
            {
                "post_id": post_id,
                "text": text,
                "author_name": author.get("name") or username or "X 사용자",
                "username": username or None,
                "author_profile_image_url": author.get("profile_image_url"),
                "url": f"https://x.com/{username}/status/{post_id}" if username else f"https://x.com/i/web/status/{post_id}",
                "created_at": _parse_datetime(post.get("created_at")),
                "like_count": int(metrics.get("like_count") or 0),
                "repost_count": int(metrics.get("retweet_count") or 0),
                "reply_count": int(metrics.get("reply_count") or 0),
                "quote_count": int(metrics.get("quote_count") or 0),
                "impact": _impact(text),
            }
        )
    return posts


def _store_posts(
    db: Session,
    stock: StockMaster,
    posts: list[dict[str, object]],
    *,
    retention_days: int,
) -> None:
    now = datetime.utcnow()
    rows: list[dict[str, object]] = []
    for post in posts:
        text = str(post["text"])
        raw = {
            key: value
            for key, value in post.items()
            if key not in {"post_id", "text", "url", "created_at"}
        }
        rows.append(
            {
                "source": X_SOURCE,
                "source_category": _category(stock.code),
                "external_id": str(post["post_id"]),
                "title": text[:240],
                "summary": text,
                "press_name": (
                    f"@{post['username']}"
                    if post.get("username")
                    else str(post.get("author_name") or "X 사용자")
                ),
                "detail_url": post.get("url"),
                "published_at": post.get("created_at"),
                "raw": json.dumps(raw, ensure_ascii=False, default=str),
                "updated_at": now,
            }
        )
    if rows:
        upsert_many(db, NewsItem, rows)
    retention_cutoff = now - timedelta(days=max(1, retention_days))
    db.execute(
        delete(NewsItem).where(
            NewsItem.source == X_SOURCE,
            NewsItem.source_category == _category(stock.code),
            NewsItem.published_at < retention_cutoff,
        )
    )
    db.commit()


def build_stock_x_feed(
    db: Session,
    stock: StockMaster,
    settings: Settings,
    *,
    limit: int = 20,
    refresh: bool = False,
) -> dict[str, object]:
    limit = max(1, min(50, limit))
    cached_rows = _stored_rows(db, stock.code, limit)
    newest_cache_at = max((row.updated_at for row in cached_rows), default=None)
    cache_cutoff = datetime.utcnow() - timedelta(seconds=max(30, settings.x_feed_cache_seconds))

    if not settings.x_feed_enabled:
        return _cached_payload(
            db,
            stock,
            limit=limit,
            configured=False,
            message="X 피드가 비활성화되어 있습니다.",
            source="x_search_link",
        )
    if not settings.x_bearer_token:
        return _cached_payload(
            db,
            stock,
            limit=limit,
            configured=False,
            message="X 연결을 준비 중입니다.",
            source="x_search_link",
        )
    if not refresh and newest_cache_at and newest_cache_at >= cache_cutoff:
        return _cached_payload(db, stock, limit=limit, configured=True)

    try:
        posts = _fetch_recent_posts(stock, settings, max(limit, settings.x_feed_max_results))
        _store_posts(
            db,
            stock,
            posts,
            retention_days=settings.x_feed_retention_days,
        )
    except Exception:
        db.rollback()
        return _cached_payload(
            db,
            stock,
            limit=limit,
            configured=True,
            message="X 피드를 갱신하지 못해 최근 저장 결과를 표시합니다.",
            source="x_api_cache",
        )
    return _cached_payload(
        db,
        stock,
        limit=limit,
        configured=True,
        message=None if posts else "최근 7일 동안 조건에 맞는 X 게시물이 없습니다.",
    )
