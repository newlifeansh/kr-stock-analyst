"""Market-scoped daily community broadcasts; never a trade recommendation.

Off by default. Shadow prepares the exact public payload without deliveries.
The daily immutable outbox and existing per-subscription delivery ledger survive
restarts. Network acceptance and DB commit cannot provide exactly-once delivery.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import threading
from types import SimpleNamespace
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import String, Text, select, text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, PushSessionLocal
from app.models import PushDelivery, PushSubscription

UTC = timezone.utc
KST = ZoneInfo("Asia/Seoul")
VERSION = "community-popular-v1-rc1"
SCHEDULE = {"kr": (12, 0), "us": (23, 30)}
WINDOW = timedelta(minutes=5)
logger = logging.getLogger(__name__)


class CommunityDigest(Base):
    __tablename__ = "community_popular_digest"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


def implementation_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def aware(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def window(market, now, immediate_at=""):
    local = now.astimezone(KST)
    scheduled = local.replace(hour=SCHEDULE[market][0], minute=SCHEDULE[market][1], second=0, microsecond=0)
    if market == "us" and immediate_at:
        immediate = aware(immediate_at)
        if immediate <= now < immediate + WINDOW:
            return immediate, immediate + WINDOW
    if scheduled <= now < scheduled + WINDOW:
        return scheduled.astimezone(UTC), (scheduled + WINDOW).astimezone(UTC)
    return None


def scoped(subscription, market):
    scope = getattr(subscription, "market_scope", None)
    if scope is None:
        scope = "us" if subscription.share_id.startswith("us.") else "kr"
    return subscription.enabled and scope == market


def select_post(feed, stock, market, now):
    """Allow only today's original Naver post for the selected rank-one stock."""
    from app.services.community_feed import _naver_world_item_code_candidates
    codes = _naver_world_item_code_candidates(stock) if market == "us" else [stock["code"]]
    section = "worldstock" if market == "us" else "domestic"
    items = []
    for provider in feed.get("providers", []):
        if provider.get("key") != "naver_board" or not provider.get("configured"):
            continue
        for item in provider.get("items", []):
            try:
                stamp = aware(item.get("created_at_utc") or item["created_at"])
                url = urlparse(item["url"])
                valid_path = any(re.fullmatch(
                    rf"/{section}/stock/{re.escape(code)}/discussion/[0-9]+", url.path
                ) for code in codes)
                if (stamp > now or stamp.astimezone(KST).date() != now.astimezone(KST).date()
                        or url.scheme != "https" or url.netloc != "m.stock.naver.com"
                        or url.query or url.fragment or not valid_path):
                    continue
                title = " ".join(str(item.get("title") or "").split())[:110]
                if title:
                    items.append({"title": title, "url": item["url"], "created_at": stamp.isoformat(),
                                  "likes": max(0, int(item.get("like_count") or 0)),
                                  "views": max(0, int(item.get("view_count") or 0)),
                                  "replies": max(0, int(item.get("reply_count") or 0))})
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
    if not items:
        raise ValueError("no_valid_today_post")
    return max(items, key=lambda x: (x["likes"], x["views"], x["replies"], x["created_at"]))


def prepare(db, settings, market, now):
    from app.services.intraday_monitor import universe
    from app.services.community_feed import build_stock_community_feed, build_us_stock_community_feed
    if market == "us":
        from app.services.us_market_calendar import latest_completed_us_market_session
        previous = latest_completed_us_market_session(now).session_date
    else:
        from app.services.market_calendar import latest_completed_korea_market_session_date
        previous = latest_completed_korea_market_session_date(now.astimezone(KST))
    if previous is None:
        raise ValueError("ranking_unavailable")
    members = universe(db, market, previous)
    if market == "us":
        first = [item for item in members if item.get("market_cap_rank") == 1]
        if len(first) != 1:
            raise ValueError("ranking_unavailable")
        stock = first[0]
        feed = build_us_stock_community_feed(stock, mode="popular", limit=1, timeout_seconds=3)
    else:
        stock = members[0]
        feed = build_stock_community_feed(SimpleNamespace(**stock), settings, mode="popular", limit=1, timeout_seconds=3)
    post = select_post(feed, stock, market, now)
    return {"stock": {"code": stock["code"], "name": stock["name"]}, "ranking_as_of": str(previous), "post": post}


def status(db, settings, now=None):
    now = now or datetime.now(UTC)
    market = "us" if settings.us_market_enabled else "kr"
    mode = settings.community_popular_mode
    day = now.astimezone(KST).date().isoformat()
    key = f"community:{market}:{mode}:{day}"
    row = db.get(CommunityDigest, key)
    event = json.loads(row.payload) if row else None
    # Counts never identify recipients or imply actual phone receipt.
    counts = dict(db.execute(select(PushDelivery.status, func.count()).where(
        PushDelivery.event_key == key).group_by(PushDelivery.status)).all()) if event else {}
    return {"version": VERSION, "implementation_digest": implementation_digest(),
            "market": market, "mode": mode, "timezone": "Asia/Seoul",
            "daily_time": "%02d:%02d" % SCHEDULE[market], "as_of": now.isoformat(),
            "state": "off" if mode == "off" else ((event or {}).get("state") or "awaiting_window"),
            "digest": event, "delivery_counts": counts,
            "delivery_semantics": "push service acceptance, not confirmed device receipt"}


class CommunityAlertRuntime:
    def __init__(self, settings, push, session_factory=PushSessionLocal):
        self.settings, self.push, self.session_factory = settings, push, session_factory
        self.task = None
        self.lock = threading.Lock()

    async def start(self):
        if self.settings.community_popular_mode != "off" and self.task is None:
            self.task = asyncio.create_task(self.loop())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def loop(self):
        while True:
            try:
                await asyncio.to_thread(self.run_once)
            except Exception:
                logger.warning("Community broadcast cycle failed; no delivery claim")
            await asyncio.sleep(30)

    def run_once(self, now=None):
        if self.settings.community_popular_mode == "off" or not self.lock.acquire(blocking=False):
            return
        connection, acquired = None, False
        try:
            with self.session_factory() as db:
                engine = db.get_bind()
                if engine.dialect.name == "postgresql":
                    connection = engine.connect()
                    acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(73100422)")))
                    if not acquired:
                        return
                return self._run(db, now)
        finally:
            if connection is not None:
                try:
                    if acquired:
                        connection.execute(text("SELECT pg_advisory_unlock(73100422)"))
                finally:
                    connection.close()
            self.lock.release()

    def _run(self, db, fixed_now=None):
        now = fixed_now or datetime.now(UTC)
        market = "us" if self.settings.us_market_enabled else "kr"
        mode = self.settings.community_popular_mode
        due = window(market, now, self.settings.community_popular_immediate_at)
        if mode == "alerts" and not due:
            return
        key = f"community:{market}:{mode}:{now.astimezone(KST).date()}"
        row = db.get(CommunityDigest, key)
        payload = json.loads(row.payload) if row else {}
        if not payload.get("post"):
            try:
                payload = prepare(db, self.settings, market, now)
                payload.update(state="preview" if mode == "shadow" else "ready",
                               prepared_at=now.isoformat(), audience_cutoff=now.isoformat())
            except Exception:
                # No old-post fallback and no exception text/credentials on public API.
                payload = {"state": "blocked", "reason": "ranking_or_today_post_unavailable", "checked_at": now.isoformat()}
            if row is None:
                row = CommunityDigest(key=key, payload="{}")
                db.add(row)
            row.payload = json.dumps(payload, ensure_ascii=False)
            db.commit()
        if mode != "alerts" or not payload.get("post") or not self.push.configured:
            return
        from app.services.web_push import NotificationCandidate
        cutoff = aware(payload["audience_cutoff"]).replace(tzinfo=None)
        ids = list(db.scalars(select(PushSubscription.id).where(
            PushSubscription.enabled.is_(True), PushSubscription.created_at <= cutoff).order_by(PushSubscription.id)))
        for subscription_id in ids:
            observed = fixed_now or datetime.now(UTC)
            if observed >= due[1]:
                break
            # _send commits; reload for unsubscribe and market changes between sends.
            db.expire_all()
            sub = db.get(PushSubscription, subscription_id)
            if sub is None or not scoped(sub, market) or sub.updated_at > cutoff:
                continue
            post, stock = payload["post"], payload["stock"]
            candidate = NotificationCandidate(
                event_key=key, kind="community_popular",
                title=f"[{'미국' if market == 'us' else '국내'} 인기글] {stock['name']}"[:240],
                body=f"{post['title']} · 커뮤니티 의견, 사실 확인 전",
                url=post["url"], tag=key, occurred_at=aware(payload["prepared_at"]).replace(tzinfo=None),
                stock_codes=(stock["code"],), ttl_seconds=max(1, int((due[1] - observed).total_seconds())),
                **({"market_scope": market} if "market_scope" in NotificationCandidate.__dataclass_fields__ else {}))
            self.push._send(db, sub, candidate)
