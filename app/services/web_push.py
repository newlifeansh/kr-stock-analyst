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
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import PushSessionLocal
from app.models import (
    DisclosureItem,
    PushDelivery,
    PushNotificationHistory,
    PushSubscription,
    ResearchReport,
    StockMaster,
    WatchlistItem,
)
from app.services.stock_dashboard import _naver_snapshot
from app.services.quant_signals import load_quant_signal_payload
from app.services.trends import (
    _matched_template_sectors,
    _stock_sectors,
    _template_by_id,
    build_trend_analysis,
)

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
NOTIFICATION_HISTORY_RETENTION = timedelta(days=3)

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
DEFAULT_PUSH_CONDITIONS = ("ai_signal", "price_move", "disclosure_report", "major_event")
REQUIRED_PUSH_CONDITIONS = {"ai_signal"}
PUSH_KIND_TO_CONDITION = {
    "ai_signal": "ai_signal",
    "price_move": "price_move",
    "report": "disclosure_report",
    "disclosure": "disclosure_report",
    "major_event": "major_event",
}


@dataclass(frozen=True)
class NotificationCandidate:
    event_key: str
    kind: str
    title: str
    body: str
    url: str
    tag: str
    occurred_at: Optional[datetime] = None
    stock_codes: tuple[str, ...] = ()


def subscription_conditions(subscription: PushSubscription) -> set[str]:
    raw = subscription.notification_preferences
    if not raw:
        return set(DEFAULT_PUSH_CONDITIONS)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return set(DEFAULT_PUSH_CONDITIONS)
    if not isinstance(parsed, list):
        return set(DEFAULT_PUSH_CONDITIONS)
    allowed = set(DEFAULT_PUSH_CONDITIONS)
    normalized = {str(item) for item in parsed if str(item) in allowed}
    return REQUIRED_PUSH_CONDITIONS | (normalized or set(DEFAULT_PUSH_CONDITIONS))


def candidate_enabled(subscription: PushSubscription, candidate: NotificationCandidate) -> bool:
    if candidate.kind == "test":
        return True
    condition = PUSH_KIND_TO_CONDITION.get(candidate.kind)
    if not condition:
        return True
    return condition in subscription_conditions(subscription)


def _signal_date(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ai_signal_candidate(
    item: WatchlistItem,
    payload: Optional[dict[str, object]],
    now: datetime,
) -> Optional[NotificationCandidate]:
    current = payload.get("current") if payload else None
    if not isinstance(current, dict):
        return None
    action = str(current.get("action") or "")
    signal_labels = {
        "entry_pending": "매수 확인",
        "entered": "매수 완료",
        "partial_exit_pending": "일부 매도 확인",
        "partially_exited": "일부 매도",
        "full_exit_pending": "매도 확인",
        "exited": "매도 완료",
    }
    label = signal_labels.get(action)
    if not label:
        return None
    lifecycle = current.get("lifecycle") if isinstance(current.get("lifecycle"), dict) else {}
    transition = lifecycle.get("latest_transition") if isinstance(lifecycle.get("latest_transition"), dict) else {}
    completed = action in {"entered", "partially_exited", "exited"}
    basis_value = transition.get("transition_date") if completed else payload.get("price_through")
    basis = _signal_date(basis_value)
    if basis is None or basis.date() != now.date():
        return None
    detail = str(current.get("next_confirmation") or "종목상세에서 신호 기준을 확인하세요.")
    return NotificationCandidate(
        event_key=f"ai-signal:{item.code}:{action}:{basis.date().isoformat()}",
        kind="ai_signal",
        title=f"{item.name} AI 매매신호 · {label}",
        body=detail,
        url=_stock_url(item.name),
        tag=f"ai-signal-{item.code}",
        occurred_at=now,
        stock_codes=(item.code,),
    )


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
        stock_codes=(item.code,),
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
        stock_codes=(item.stock_code,) if item.stock_code else (),
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
        stock_codes=(item.stock_code,) if item.stock_code else (),
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
                matched_codes = []
                for item in items:
                    stock = stocks.get(item.code)
                    if stock and _matched_template_sectors(template, _stock_sectors(stock)):
                        matched_names.append(item.name)
                        matched_codes.append(item.code)
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
                        stock_codes=tuple(matched_codes),
                    )
                )
        return output

    def _ai_signal_candidates(
        self,
        db: Session,
        watchlists: dict[str, list[WatchlistItem]],
        now: datetime,
    ) -> dict[str, list[NotificationCandidate]]:
        output = {share_id: [] for share_id in watchlists}
        payloads: dict[str, Optional[dict[str, object]]] = {}
        for items in watchlists.values():
            for item in items:
                if item.code not in payloads:
                    try:
                        payloads[item.code] = load_quant_signal_payload(
                            db,
                            item.code,
                            now=now,
                            include_context=False,
                        )
                    except Exception:
                        logger.exception("AI signal calculation failed for %s", item.code)
                        payloads[item.code] = None
        for share_id, items in watchlists.items():
            for item in items:
                candidate = _ai_signal_candidate(item, payloads.get(item.code), now)
                if candidate:
                    output[share_id].append(candidate)
        return output

    def _send(self, db: Session, subscription: PushSubscription, candidate: NotificationCandidate) -> bool:
        if not candidate_enabled(subscription, candidate):
            return False
        if candidate.kind in {"report", "disclosure"} and candidate.occurred_at:
            if candidate.occurred_at < subscription.created_at:
                return False
        delivery = db.scalar(
            select(PushDelivery).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.event_key == candidate.event_key,
            )
        )
        if delivery and (delivery.status in {"sent", "baseline"} or delivery.attempts >= 3):
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
            history_cutoff = datetime.utcnow() - NOTIFICATION_HISTORY_RETENTION
            db.execute(
                delete(PushNotificationHistory).where(
                    PushNotificationHistory.created_at < history_cutoff
                )
            )
            history = db.scalar(
                select(PushNotificationHistory).where(
                    PushNotificationHistory.share_id == subscription.share_id,
                    PushNotificationHistory.event_key == candidate.event_key,
                )
            )
            if history is None:
                db.add(
                    PushNotificationHistory(
                        share_id=subscription.share_id,
                        event_key=candidate.event_key,
                        notification_kind=candidate.kind,
                        title=candidate.title,
                        body=candidate.body,
                        url=candidate.url,
                    )
                )
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

    @staticmethod
    def _baseline_marker_key(subscription: PushSubscription, item: WatchlistItem) -> str:
        subscription_epoch = subscription.created_at.isoformat(timespec="microseconds")
        watch_epoch = item.created_at.isoformat(timespec="microseconds")
        return f"watch-baseline:{item.code}:{subscription_epoch}:{watch_epoch}"

    def _initialized_watch_codes(
        self,
        db: Session,
        subscription: PushSubscription,
        items: list[WatchlistItem],
    ) -> set[str]:
        marker_by_code = {
            item.code: self._baseline_marker_key(subscription, item)
            for item in items
        }
        if not marker_by_code:
            return set()
        existing = set(
            db.scalars(
                select(PushDelivery.event_key).where(
                    PushDelivery.subscription_id == subscription.id,
                    PushDelivery.event_key.in_(tuple(marker_by_code.values())),
                    PushDelivery.status == "baseline",
                )
            )
        )
        return {code for code, marker in marker_by_code.items() if marker in existing}

    @staticmethod
    def _record_candidate_baseline(
        db: Session,
        subscription: PushSubscription,
        candidate: NotificationCandidate,
    ) -> None:
        delivery = db.scalar(
            select(PushDelivery).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.event_key == candidate.event_key,
            )
        )
        if delivery is None:
            db.add(
                PushDelivery(
                    subscription_id=subscription.id,
                    event_key=candidate.event_key,
                    notification_kind=candidate.kind,
                    title=candidate.title,
                    status="baseline",
                    attempts=0,
                )
            )
        elif delivery.status not in {"sent", "baseline"}:
            delivery.status = "baseline"
            delivery.error = None

    def _mark_watchlist_initialized(
        self,
        db: Session,
        subscription: PushSubscription,
        items: list[WatchlistItem],
        initialized_codes: set[str],
    ) -> None:
        for item in items:
            if item.code in initialized_codes:
                continue
            db.add(
                PushDelivery(
                    subscription_id=subscription.id,
                    event_key=self._baseline_marker_key(subscription, item),
                    notification_kind="baseline",
                    title=f"{item.name} 알림 기준선",
                    status="baseline",
                    attempts=0,
                )
            )

    def run_once(self) -> int:
        if not self.configured:
            return 0
        now_utc = datetime.utcnow()
        now_kst = datetime.now(KST).replace(tzinfo=None)
        with PushSessionLocal() as db:
            db.execute(
                delete(PushNotificationHistory).where(
                    PushNotificationHistory.created_at < now_utc - NOTIFICATION_HISTORY_RETENTION
                )
            )
            db.commit()
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
                self._ai_signal_candidates(db, watchlists, now_kst),
                self._content_candidates(db, watchlists, now_utc),
                self._event_candidates(db, watchlists, now_kst),
            ):
                for share_id, candidates in source.items():
                    candidates_by_share[share_id].extend(candidates)

            sent = 0
            for subscription in subscriptions:
                items = watchlists.get(subscription.share_id, [])
                initialized_codes = self._initialized_watch_codes(db, subscription, items)
                for candidate in candidates_by_share.get(subscription.share_id, []):
                    related_codes = set(candidate.stock_codes)
                    if related_codes and not (related_codes & initialized_codes):
                        self._record_candidate_baseline(db, subscription, candidate)
                        continue
                    sent += int(self._send(db, subscription, candidate))
                self._mark_watchlist_initialized(db, subscription, items, initialized_codes)
                db.commit()
            return sent

    def send_test(self, db: Session, subscription: PushSubscription) -> bool:
        now = datetime.utcnow()
        return self._send(
            db,
            subscription,
            NotificationCandidate(
                event_key=f"test:{subscription.id}:{now.isoformat(timespec='seconds')}",
                kind="test",
                title="알림 설정 완료",
                body="관심종목 AI 매매신호, 급등락, 중요 공시·리포트, 주요 이벤트를 알려드립니다.",
                url="/dashboard?view=watchlist",
                tag="push-test",
                occurred_at=now,
            ),
        )


web_push_runtime = WebPushRuntime()
