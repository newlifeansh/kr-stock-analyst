from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base
from app.models import (
    DisclosureItem,
    PushDelivery,
    PushNotificationHistory,
    PushSubscription,
    StockMaster,
    WatchlistItem,
)
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
        history = db.query(PushNotificationHistory).one()
        assert history.share_id == "tester"
        assert history.title == candidate.title
        assert history.body == candidate.body
        assert history.url == candidate.url
    finally:
        db.close()


def test_notification_history_is_deduplicated_per_user_and_prunes_old_rows(monkeypatch):
    db = _session()
    try:
        subscriptions = [
            PushSubscription(
                share_id="tester",
                endpoint=f"https://push.example/subscription-{index}",
                p256dh="p" * 64,
                auth="a" * 24,
            )
            for index in range(2)
        ]
        db.add_all(subscriptions)
        db.add(
            PushNotificationHistory(
                share_id="tester",
                event_key="old:event",
                notification_kind="report",
                title="오래된 알림",
                body="보관 기간을 지났습니다.",
                url="/dashboard",
                created_at=datetime.utcnow() - timedelta(days=4),
            )
        )
        db.commit()
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: None)
        candidate = web_push.NotificationCandidate(
            event_key="event:shared-device-test",
            kind="major_event",
            title="주요 이벤트 임박",
            body="관심종목에 영향을 줄 수 있습니다.",
            url="/dashboard?view=home&home_tab=events",
            tag="event-test",
            occurred_at=datetime.utcnow(),
        )
        runtime = web_push.WebPushRuntime(_settings())

        assert runtime._send(db, subscriptions[0], candidate) is True
        assert runtime._send(db, subscriptions[1], candidate) is True

        histories = db.query(PushNotificationHistory).all()
        assert len(histories) == 1
        assert histories[0].event_key == candidate.event_key
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


def test_ai_signal_is_mandatory_even_when_only_price_alerts_are_selected():
    subscription = PushSubscription(
        share_id="tester",
        endpoint="https://push.example/subscription",
        p256dh="p" * 64,
        auth="a" * 24,
        notification_preferences='["price_move"]',
    )
    candidate = web_push.NotificationCandidate(
        event_key="ai-signal:005930:entered:2026-07-25",
        kind="ai_signal",
        title="삼성전자 AI 매매신호 · 매수 완료",
        body="초기 위험선을 확인합니다.",
        url="/dashboard/삼성전자",
        tag="ai-signal-005930",
    )

    assert "ai_signal" in web_push.subscription_conditions(subscription)
    assert web_push.candidate_enabled(subscription, candidate) is True


def test_market_ai_signal_is_enabled_for_legacy_defaults_but_not_custom_preferences():
    legacy_subscription = PushSubscription(
        share_id="legacy",
        endpoint="https://push.example/legacy",
        p256dh="p" * 64,
        auth="a" * 24,
        notification_preferences='["ai_signal", "price_move", "disclosure_report", "major_event"]',
    )
    custom_subscription = PushSubscription(
        share_id="custom",
        endpoint="https://push.example/custom",
        p256dh="p" * 64,
        auth="a" * 24,
        notification_preferences='["ai_signal", "price_move"]',
    )

    assert "market_ai_signal" in web_push.subscription_conditions(legacy_subscription)
    assert "market_ai_signal" not in web_push.subscription_conditions(custom_subscription)


def test_market_ai_signal_candidates_are_built_from_saved_market_snapshot(monkeypatch):
    db = _session()
    try:
        monkeypatch.setattr(
            web_push,
            "load_market_quant_signal_snapshot",
            lambda *_args, **_kwargs: {
                "items": [
                    {
                        "code": "005930",
                        "name": "삼성전자",
                        "side": "buy",
                        "execution_date": "2026-07-28",
                    },
                    {
                        "code": "000660",
                        "name": "SK하이닉스",
                        "side": "sell",
                        "execution_date": "2026-07-28",
                    },
                ]
            },
        )

        candidates = web_push.WebPushRuntime(_settings())._market_ai_signal_candidates(db)

        assert [candidate.kind for candidate in candidates] == [
            "market_ai_signal",
            "market_ai_signal",
        ]
        assert candidates[0].event_key == "market-ai-signal:005930:buy:2026-07-28"
        assert "삼성전자" in candidates[0].title
        assert "매수" in candidates[0].title
        assert candidates[1].event_key == "market-ai-signal:000660:sell:2026-07-28"
        assert "매도" in candidates[1].title
    finally:
        db.close()


def test_market_ai_signal_baseline_blocks_old_events_and_allows_new_events(monkeypatch):
    db = _session()
    calls = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/subscription",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["ai_signal", "market_ai_signal"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: calls.append(kwargs))
        runtime = web_push.WebPushRuntime(_settings())
        existing_candidate = web_push.NotificationCandidate(
            event_key="market-ai-signal:005930:buy:2026-07-27",
            kind="market_ai_signal",
            title="삼성전자 시장 AI 매매신호 · 매수",
            body="알림 설정 전 기존 신호",
            url="/dashboard/삼성전자",
            tag="market-ai-signal-005930",
        )

        runtime._record_candidate_baseline(db, subscription, existing_candidate)
        runtime._mark_market_signal_initialized(db, subscription)
        db.commit()

        assert runtime._market_signal_initialized(db, subscription) is True
        assert runtime._send(db, subscription, existing_candidate) is False
        assert calls == []

        new_candidate = web_push.NotificationCandidate(
            event_key="market-ai-signal:000660:sell:2026-07-28",
            kind="market_ai_signal",
            title="SK하이닉스 시장 AI 매매신호 · 매도",
            body="알림 설정 이후 새 신호",
            url="/dashboard/SK하이닉스",
            tag="market-ai-signal-000660",
        )
        assert runtime._send(db, subscription, new_candidate) is True
        assert len(calls) == 1
    finally:
        db.close()


def test_ai_signal_candidate_only_emits_a_new_action_for_today(monkeypatch):
    db = _session()
    try:
        watch = WatchlistItem(share_id="tester", code="005930", name="삼성전자", market="KOSPI")
        db.add(watch)
        db.commit()
        now = datetime(2026, 7, 25, 18, 0)
        monkeypatch.setattr(
            web_push,
            "load_quant_signal_payload",
            lambda *_args, **_kwargs: {
                "price_through": "2026-07-25",
                "current": {
                    "action": "entry_pending",
                    "next_confirmation": "종가 확정 후 매수 여부를 확인합니다.",
                    "lifecycle": {"latest_transition": None},
                },
            },
        )

        candidates = web_push.WebPushRuntime(_settings())._ai_signal_candidates(
            db,
            {"tester": [watch]},
            now,
        )

        assert len(candidates["tester"]) == 1
        assert candidates["tester"][0].kind == "ai_signal"
        assert "매수 확인" in candidates["tester"][0].title
        assert candidates["tester"][0].event_key == "ai-signal:005930:entry_pending:2026-07-25"
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


def test_new_watch_item_baselines_existing_events_before_sending_new_ones(monkeypatch):
    db = _session()
    calls = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/subscription",
            p256dh="p" * 64,
            auth="a" * 24,
        )
        watch = WatchlistItem(
            share_id="tester",
            code="005930",
            name="삼성전자",
            market="KOSPI",
        )
        db.add_all([subscription, watch])
        db.commit()
        db.refresh(subscription)
        db.refresh(watch)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: calls.append(kwargs))
        runtime = web_push.WebPushRuntime(_settings())
        existing_candidate = web_push.NotificationCandidate(
            event_key="report:naver:existing",
            kind="report",
            title="삼성전자 기존 리포트",
            body="알림 설정 전에 존재하던 리포트",
            url="/dashboard/삼성전자",
            tag="report-existing",
            occurred_at=datetime.utcnow(),
            stock_codes=("005930",),
        )

        initialized = runtime._initialized_watch_codes(db, subscription, [watch])
        assert initialized == set()
        runtime._record_candidate_baseline(db, subscription, existing_candidate)
        runtime._mark_watchlist_initialized(db, subscription, [watch], initialized)
        db.commit()

        assert runtime._send(db, subscription, existing_candidate) is False
        assert calls == []
        assert runtime._initialized_watch_codes(db, subscription, [watch]) == {"005930"}

        new_candidate = web_push.NotificationCandidate(
            event_key="report:naver:new",
            kind="report",
            title="삼성전자 새 리포트",
            body="알림 설정 이후 발행된 리포트",
            url="/dashboard/삼성전자",
            tag="report-new",
            occurred_at=datetime.utcnow(),
            stock_codes=("005930",),
        )
        assert runtime._send(db, subscription, new_candidate) is True
        assert len(calls) == 1
    finally:
        db.close()
