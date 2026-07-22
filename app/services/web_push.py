from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
from typing import Optional
from urllib.parse import quote

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import (
    DisclosureItem,
    PushDelivery,
    PushSubscription,
    ResearchReport,
    StockMaster,
    WatchlistItem,
)
from app.services.stock_dashboard import _naver_snapshot
from app.services.trends import (
    _matched_template_sectors,
    _stock_sectors,
    _template_by_id,
    build_trend_analysis,
)

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

IMPORTANT_DISCLOSURE_CATEGORIES = {
    "earnings_flash",
    "supply_contract",
    "rights_offering",
    "dividend",
    "treasury_stock",
    "facility_investment",
    "major_holder",
}
IMPORTANT_DISCLOSURE_KEYWORDS = (
    "잠정실적",
    "영업실적",
    "공급계약",
    "단일판매",
    "유상증자",
    "무상증자",
    "배당",
    "자기주식",
    "자사주",
    "합병",
    "분할",
    "최대주주",
    "영업정지",
    "회생절차",
    "횡령",
    "배임",
    "시설투자",
)


@dataclass(frozen=True)
class NotificationCandidate:
    event_key: str
    kind: str
    title: str
    body: str
    url: str
    tag: str
    occurred_at: Optional[datetime] = None


def _stock_url(name: str) -> str:
    return f"/dashboard/{quote(name, safe='')}"


def _is_important_disclosure(item: DisclosureItem) -> bool:
    if item.disclosure_category in IMPORTANT_DISCLOSURE_CATEGORIES:
        return True
    return any(keyword in item.report_name for keyword in IMPORTANT_DISCLOSURE_KEYWORDS)


def _price_candidate(
    item: WatchlistItem,
    snapshot: dict[str, object],
    now: datetime,
    threshold: Decimal,
) -> Optional[NotificationCandidate]:
    raw_rate = snapshot.get("change_rate_abs")
    if raw_rate is None:
        return None
    change_rate = Decimal(str(raw_rate))
    if abs(change_rate) < threshold:
        return None
    direction = "rise" if change_rate > 0 else "fall"
    direction_label = "급등" if change_rate > 0 else "급락"
    price = snapshot.get("price")
    price_text = f" · {int(price):,}원" if price is not None else ""
    return NotificationCandidate(
        event_key=f"price:{now.date().isoformat()}:{item.code}:{direction}:{threshold}",
        kind="price_move",
        title=f"{item.name} {direction_label} {change_rate:+.2f}%",
        body=f"관심종목 변동이 {threshold:.0f}% 기준을 넘었습니다{price_text}.",
        url=_stock_url(item.name),
        tag=f"price-{item.code}-{direction}",
        occurred_at=now,
    )


def _report_candidate(item: ResearchReport, stock_name: str) -> NotificationCandidate:
    details = [item.broker_name or "증권사 리포트"]
    if item.opinion:
        details.append(item.opinion)
    if item.target_price:
        details.append(f"목표가 {int(item.target_price):,}원")
    return NotificationCandidate(
        event_key=f"report:{item.source}:{item.external_id}",
        kind="report",
        title=f"{stock_name} 새 애널리스트 리포트",
        body=f"{' · '.join(details)} | {item.title}",
        url=_stock_url(stock_name),
        tag=f"report-{item.stock_code or item.external_id}",
        occurred_at=item.updated_at,
    )


def _disclosure_candidate(item: DisclosureItem, stock_name: str) -> NotificationCandidate:
    return NotificationCandidate(
        event_key=f"disclosure:{item.source}:{item.external_id}",
        kind="disclosure",
        title=f"{stock_name} 중요 공시",
        body=item.report_name,
        url=_stock_url(stock_name),
        tag=f"disclosure-{item.stock_code or item.external_id}",
        occurred_at=item.updated_at,
    )


class WebPushRuntime:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.web_push_enabled
            and self.settings.web_push_vapid_private_key
            and self.settings.web_push_vapid_public_key
        )

    async def start(self) -> None:
        if self.running or not self.configured:
            return
        self.running = True
        self.task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _loop(self) -> None:
        while self.running:
            try:
                await asyncio.to_thread(self.run_once)
                self.last_success_at = datetime.utcnow()
                self.last_error = None
            except Exception as exc:  # pragma: no cover - operational safeguard
                self.last_error = str(exc)
                logger.exception("Web push scan failed")
            await asyncio.sleep(max(30, self.settings.web_push_poll_seconds))

    def _quote_snapshots(self, codes: set[str]) -> dict[str, dict[str, object]]:
        if not codes:
            return {}
        output: dict[str, dict[str, object]] = {}
        with ThreadPoolExecutor(max_workers=min(8, len(codes))) as executor:
            futures = {executor.submit(_naver_snapshot, code, True): code for code in codes}
            for future in as_completed(futures):
                try:
                    output[futures[future]] = future.result()
                except Exception:
                    continue
        return output

    def _content_candidates(
        self,
        db: Session,
        watchlists: dict[str, list[WatchlistItem]],
        now: datetime,
    ) -> dict[str, list[NotificationCandidate]]:
        all_codes = {item.code for items in watchlists.values() for item in items}
        output = {share_id: [] for share_id in watchlists}
        if not all_codes:
            return output
        cutoff = now - timedelta(hours=24)
        reports = list(
            db.scalars(
                select(ResearchReport)
                .where(ResearchReport.stock_code.in_(all_codes))
                .where(ResearchReport.updated_at >= cutoff)
                .order_by(ResearchReport.updated_at.desc())
                .limit(200)
            )
        )
        disclosures = list(
            db.scalars(
                select(DisclosureItem)
                .where(DisclosureItem.stock_code.in_(all_codes))
                .where(DisclosureItem.updated_at >= cutoff)
                .order_by(DisclosureItem.updated_at.desc())
                .limit(200)
            )
        )
        for share_id, items in watchlists.items():
            names = {item.code: item.name for item in items}
            output[share_id].extend(
                _report_candidate(report, names[report.stock_code])
                for report in reports
                if report.stock_code in names
            )
            output[share_id].extend(
                _disclosure_candidate(disclosure, names[disclosure.stock_code])
                for disclosure in disclosures
                if disclosure.stock_code in names and _is_important_disclosure(disclosure)
            )
        return output

    def _event_candidates(
        self,
        db: Session,
        watchlists: dict[str, list[WatchlistItem]],
        now: datetime,
    ) -> dict[str, list[NotificationCandidate]]:
        output = {share_id: [] for share_id in watchlists}
        analysis = build_trend_analysis(db, days=7)
        lead_time = timedelta(hours=max(1, self.settings.web_push_event_lead_hours))
        stocks = {
            stock.code: stock
            for stock in db.scalars(
                select(StockMaster).where(
                    StockMaster.code.in_({item.code for items in watchlists.values() for item in items})
                )
            )
        }
        for event in analysis.get("events", []):
            starts_at = event.get("starts_at")
            if not isinstance(starts_at, datetime) or starts_at < now or starts_at - now > lead_time:
                continue
            if event.get("importance") not in {"중요", "매우 중요"}:
                continue
            template, _ = _template_by_id(str(event.get("id") or ""))
            if template is None:
                continue
            for share_id, items in watchlists.items():
                matched_names = []
                for item in items:
                    stock = stocks.get(item.code)
                    if stock and _matched_template_sectors(template, _stock_sectors(stock)):
                        matched_names.append(item.name)
                if not matched_names:
                    continue
                names_text = ", ".join(matched_names[:3])
                if len(matched_names) > 3:
                    names_text += f" 외 {len(matched_names) - 3}개"
                output[share_id].append(
                    NotificationCandidate(
                        event_key=f"event:{event['id']}",
                        kind="major_event",
                        title=f"주요 이벤트 임박 · {event['title']}",
                        body=f"{names_text}에 영향을 줄 수 있습니다. 발표 전 확인하세요.",
                        url="/dashboard?view=trend",
                        tag=f"event-{event['id']}",
                        occurred_at=now,
                    )
                )
        return output

    def _send(self, db: Session, subscription: PushSubscription, candidate: NotificationCandidate) -> bool:
        if candidate.kind in {"report", "disclosure"} and candidate.occurred_at:
            if candidate.occurred_at < subscription.created_at:
                return False
        delivery = db.scalar(
            select(PushDelivery).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.event_key == candidate.event_key,
            )
        )
        if delivery and (delivery.status == "sent" or delivery.attempts >= 3):
            return False
        if delivery is None:
            delivery = PushDelivery(
                subscription_id=subscription.id,
                event_key=candidate.event_key,
                notification_kind=candidate.kind,
                title=candidate.title,
                status="pending",
            )
            db.add(delivery)
        delivery.attempts = (delivery.attempts or 0) + 1
        payload = json.dumps(
            {
                "title": candidate.title,
                "body": candidate.body,
                "url": candidate.url,
                "tag": candidate.tag,
                "kind": candidate.kind,
            },
            ensure_ascii=False,
        )
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=self.settings.web_push_vapid_private_key,
                vapid_claims={"sub": self.settings.web_push_vapid_subject},
                content_encoding=subscription.content_encoding,
                ttl=60 * 60 * 6,
                timeout=12,
            )
            delivery.status = "sent"
            delivery.sent_at = datetime.utcnow()
            delivery.error = None
            db.commit()
            return True
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            delivery.status = "expired" if status_code in {404, 410} else "failed"
            delivery.error = str(exc)[:2000]
            if status_code in {404, 410}:
                subscription.enabled = False
            db.commit()
            return False
        except Exception as exc:
            delivery.status = "failed"
            delivery.error = str(exc)[:2000]
            db.commit()
            return False

    def run_once(self) -> int:
        if not self.configured:
            return 0
        now_utc = datetime.utcnow()
        now_kst = datetime.now(KST).replace(tzinfo=None)
        with SessionLocal() as db:
            subscriptions = list(
                db.scalars(
                    select(PushSubscription)
                    .where(PushSubscription.enabled.is_(True))
                    .order_by(PushSubscription.id)
                )
            )
            if not subscriptions:
                return 0
            share_ids = sorted({item.share_id for item in subscriptions})
            watch_items = list(
                db.scalars(
                    select(WatchlistItem)
                    .where(WatchlistItem.share_id.in_(share_ids))
                    .order_by(WatchlistItem.share_id, WatchlistItem.sort_order)
                )
            )
            watchlists = {share_id: [] for share_id in share_ids}
            for item in watch_items:
                watchlists[item.share_id].append(item)

            snapshots = self._quote_snapshots({item.code for item in watch_items})
            candidates_by_share = {share_id: [] for share_id in share_ids}
            threshold = Decimal(str(self.settings.web_push_price_threshold))
            for share_id, items in watchlists.items():
                for item in items:
                    candidate = _price_candidate(item, snapshots.get(item.code, {}), now_kst, threshold)
                    if candidate:
                        candidates_by_share[share_id].append(candidate)
            for source in (
                self._content_candidates(db, watchlists, now_utc),
                self._event_candidates(db, watchlists, now_kst),
            ):
                for share_id, candidates in source.items():
                    candidates_by_share[share_id].extend(candidates)

            sent = 0
            for subscription in subscriptions:
                for candidate in candidates_by_share.get(subscription.share_id, []):
                    sent += int(self._send(db, subscription, candidate))
            return sent

    def send_test(self, db: Session, subscription: PushSubscription) -> bool:
        now = datetime.utcnow()
        return self._send(
            db,
            subscription,
            NotificationCandidate(
                event_key=f"test:{subscription.id}:{now.isoformat(timespec='seconds')}",
                kind="test",
                title="비밀노트 알림 설정 완료",
                body="관심종목 급등락, 중요 공시·리포트, 주요 이벤트를 알려드립니다.",
                url="/dashboard?view=watchlist",
                tag="push-test",
                occurred_at=now,
            ),
        )


web_push_runtime = WebPushRuntime()
