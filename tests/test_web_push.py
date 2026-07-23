from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base
from app.models import DisclosureItem, PushDelivery, PushSubscription, StockMaster, WatchlistItem
from app.services import web_push
from app.services.trends import EVENT_TEMPLATES


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _settings() -> Settings:
    return Settings(
        web_push_enabled=True,
        web_push_vapid_private_key="A" * 43,
        web_push_vapid_public_key="B" * 87,
    )


def test_price_candidate_requires_five_percent_move():
    item = WatchlistItem(share_id="tester", code="005930", name="삼성전자", market="KOSPI")
    now = datetime(2026, 7, 22, 10, 0)

    assert web_push._price_candidate(item, {"change_rate_abs": Decimal("4.99")}, now, Decimal("5")) is None
    candidate = web_push._price_candidate(
        item,
        {"change_rate_abs": Decimal("-5.25"), "price": 250000},
        now,
        Decimal("5"),
    )

    assert candidate is not None
    assert candidate.kind == "price_move"
    assert "급락 -5.25%" in candidate.title
    assert candidate.event_key == "price:2026-07-22:005930:fall:5"


def test_important_disclosure_filters_generic_filing():
    generic = DisclosureItem(
        source="dart",
        external_id="1",
        disclosure_category="filings",
        company_name="삼성전자",
        report_name="투자설명서",
    )
    important = DisclosureItem(
        source="dart",
        external_id="2",
        disclosure_category="filings",
        company_name="삼성전자",
        report_name="단일판매·공급계약체결",
    )

    assert web_push._is_important_disclosure(generic) is False
    assert web_push._is_important_disclosure(important) is True


def test_event_candidate_requires_watchlist_sector_match(monkeypatch):
    db = _session()
    try:
        stock = StockMaster(code="005930", name="삼성전자", market="KOSPI")
        watch = WatchlistItem(share_id="tester", code="005930", name="삼성전자", market="KOSPI")
        db.add_all([stock, watch])
        db.commit()
        now = datetime(2026, 7, 22, 10, 0)
        template = next(item for item in EVENT_TEMPLATES if item.key == "us-pce")
        event_id = "us-pce-20260722T200000"
        monkeypatch.setattr(
            web_push,
            "build_trend_analysis",
            lambda _db, days=7: {
                "events": [
                    {
                        "id": event_id,
                        "title": template.title,
                        "importance": "매우 중요",
                        "starts_at": now + timedelta(hours=10),
                    }
                ]
            },
        )
        monkeypatch.setattr(web_push, "_template_by_id", lambda _event_id: (template, now + timedelta(hours=10)))

        candidates = web_push.WebPushRuntime(_settings())._event_candidates(
            db,
            {"tester": [watch]},
            now,
        )

        assert len(candidates["tester"]) == 1
        assert "삼성전자" in candidates["tester"][0].body
        assert candidates["tester"][0].kind == "major_event"
    finally:
        db.close()


def test_delivery_is_sent_only_once(monkeypatch):
    db = _session()
    calls = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/subscription",
            p256dh="p" * 64,
            auth="a" * 24,
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: calls.append(kwargs))
        candidate = web_push.NotificationCandidate(
            event_key="price:2026-07-22:005930:rise:5",
            kind="price_move",
            title="삼성전자 급등 +5.20%",
            body="기준을 넘었습니다.",
            url="/dashboard/삼성전자",
            tag="price-005930-rise",
            occurred_at=datetime.utcnow(),
        )
        runtime = web_push.WebPushRuntime(_settings())

        assert runtime._send(db, subscription, candidate) is True
        assert runtime._send(db, subscription, candidate) is False
        assert len(calls) == 1
        delivery = db.query(PushDelivery).one()
        assert delivery.status == "sent"
        assert delivery.attempts == 1
    finally:
        db.close()


def test_delivery_respects_saved_notification_preferences(monkeypatch):
    db = _session()
    calls = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/subscription",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["price_move"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: calls.append(kwargs))
        runtime = web_push.WebPushRuntime(_settings())

        report_candidate = web_push.NotificationCandidate(
            event_key="report:naver:123",
            kind="report",
            title="삼성전자 새 애널리스트 리포트",
            body="리포트 알림",
            url="/dashboard/삼성전자",
            tag="report-123",
            occurred_at=datetime.utcnow(),
        )
        price_candidate = web_push.NotificationCandidate(
            event_key="price:2026-07-23:005930:rise:5",
            kind="price_move",
            title="삼성전자 급등 +5.20%",
            body="기준을 넘었습니다.",
            url="/dashboard/삼성전자",
            tag="price-005930-rise",
            occurred_at=datetime.utcnow(),
        )

        assert runtime._send(db, subscription, report_candidate) is False
        assert runtime._send(db, subscription, price_candidate) is True
        assert len(calls) == 1
    finally:
        db.close()


def test_test_notification_title_does_not_repeat_service_name(monkeypatch):
    db = _session()
    payloads = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/subscription",
            p256dh="p" * 64,
            auth="a" * 24,
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        def capture_webpush(**kwargs):
            payloads.append(kwargs["data"])

        monkeypatch.setattr(web_push, "webpush", capture_webpush)

        assert web_push.WebPushRuntime(_settings()).send_test(db, subscription) is True
        assert payloads
        assert '"title": "알림 설정 완료"' in payloads[0]
        assert "비밀노트" not in payloads[0]
    finally:
        db.close()
