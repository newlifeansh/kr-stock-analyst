from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

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
        assert calls[0]["ttl"] == web_push.PUSH_DELIVERY_TTL_SECONDS
        assert calls[0]["headers"] == {"Urgency": "high"}
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
        title="✅ [매수 확정] 삼성전자",
        body="초기 위험선을 확인합니다.",
        url="/dashboard/삼성전자",
        tag="ai-signal-005930",
    )

    assert "ai_signal" in web_push.subscription_conditions(subscription)
    assert web_push.candidate_enabled(subscription, candidate) is True


def test_market_notifications_are_enabled_for_legacy_defaults_but_not_custom_preferences():
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
    assert "market_session" in web_push.subscription_conditions(legacy_subscription)
    assert "recommendation_update" not in web_push.subscription_conditions(legacy_subscription)
    assert "market_ai_signal" not in web_push.subscription_conditions(custom_subscription)
    assert "market_session" not in web_push.subscription_conditions(custom_subscription)
    assert "recommendation_update" not in web_push.subscription_conditions(custom_subscription)


def _recommendation_item(
    code: str,
    name: str,
    rank: int,
    score: str,
    signal_action: str,
    *,
    profit_stage: int = 0,
    pending_profit_stage=None,
    signal_label=None,
    latest_transition=None,
):
    current = {
        "action": signal_action,
        "profit_stage": profit_stage,
        "next_confirmation": "다음 거래일 조건을 확인합니다.",
    }
    if pending_profit_stage is not None:
        current["pending_profit_stage"] = pending_profit_stage
    if signal_label is not None:
        current["label"] = signal_label
    if latest_transition is not None:
        current["lifecycle"] = {"latest_transition": latest_transition}
    return {
        "code": code,
        "name": name,
        "rank": rank,
        "score": Decimal(score),
        "action": "분할 접근",
        "ai_trade_signal": {
            "current": current
        },
    }


def test_recommendation_updates_baseline_current_list_and_ignore_rank_or_score_noise(monkeypatch):
    db = _session()
    calls = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/recommendation-baseline",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["recommendation_update"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: calls.append(kwargs))
        runtime = web_push.WebPushRuntime(_settings())
        now = datetime(2026, 8, 24, 10, 0)
        initial = {
            "items": [
                _recommendation_item("005930", "삼성전자", 1, "82", "entry_pending"),
                _recommendation_item("000660", "SK하이닉스", 2, "79", "holding"),
            ]
        }

        assert runtime._process_recommendation_updates(db, subscription, initial, now) == 0
        assert calls == []
        initialized, codes, signals = runtime._recommendation_state(db, subscription)
        assert initialized is True
        assert codes == {"005930", "000660"}
        assert signals == {"005930": "buy-pending", "000660": "holding"}

        reordered = {
            "items": [
                _recommendation_item("000660", "SK하이닉스", 1, "81.5", "holding"),
                _recommendation_item("005930", "삼성전자", 2, "80.5", "entry_pending"),
            ]
        }
        assert runtime._process_recommendation_updates(db, subscription, reordered, now) == 0
        assert calls == []
    finally:
        db.close()


def test_recommendation_push_scan_uses_ten_minute_poll_interval(monkeypatch):
    db = _session()
    calls = []
    try:
        monkeypatch.setattr(
            web_push,
            "build_recommendations",
            lambda *_args, **kwargs: calls.append(kwargs) or {"items": []},
        )
        runtime = web_push.WebPushRuntime(_settings())
        now = datetime(2026, 8, 24, 10, 0)

        assert runtime._recommendation_snapshot(db, now) == {"items": []}
        assert runtime._recommendation_snapshot(db, now + timedelta(minutes=9, seconds=59)) is None
        assert runtime._recommendation_snapshot(db, now + timedelta(minutes=10)) == {"items": []}
        assert len(calls) == 2
        assert calls[0] == {
            "limit": 10,
            "candidate_limit": 45,
            "refresh_live": False,
            "ensure_signal_history": False,
        }
    finally:
        db.close()


def test_recommendation_updates_alert_new_top_ten_entry_and_open_its_detail(monkeypatch):
    db = _session()
    payloads = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/recommendation-entry",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["recommendation_update"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: payloads.append(json.loads(kwargs["data"])))
        runtime = web_push.WebPushRuntime(_settings())
        now = datetime(2026, 8, 24, 10, 0)
        initial = {"items": [_recommendation_item("005930", "삼성전자", 1, "82", "holding")]}
        runtime._process_recommendation_updates(db, subscription, initial, now)

        updated = {
            "items": [
                _recommendation_item("005930", "삼성전자", 1, "82", "holding"),
                _recommendation_item("000660", "SK하이닉스", 2, "80", "entry_pending"),
            ]
        }
        assert runtime._process_recommendation_updates(db, subscription, updated, now) == 1
        assert len(payloads) == 1
        assert payloads[0]["title"] == "SK하이닉스 추천 상위 10 신규 진입"
        assert payloads[0]["url"] == "/dashboard?view=recommend-detail&code=000660"
        assert payloads[0]["kind"] == "recommendation_update"

        initialized, codes, signals = runtime._recommendation_state(db, subscription)
        assert initialized is True
        assert codes == {"005930", "000660"}
        assert signals["000660"] == "buy-pending"
    finally:
        db.close()


def test_recommendation_updates_batch_three_or_more_changes_into_one_summary_alert(monkeypatch):
    db = _session()
    payloads = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/recommendation-batch",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["recommendation_update"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: payloads.append(json.loads(kwargs["data"])))
        runtime = web_push.WebPushRuntime(_settings())
        now = datetime(2026, 8, 24, 10, 0)
        initial = {
            "items": [
                _recommendation_item("005930", "삼성전자", 1, "82", "entry_pending"),
            ]
        }
        runtime._process_recommendation_updates(db, subscription, initial, now)

        updated = {
            "items": [
                _recommendation_item("005930", "삼성전자", 1, "82", "holding"),
                _recommendation_item("000660", "SK하이닉스", 2, "80", "entry_pending"),
                _recommendation_item("035420", "NAVER", 3, "79", "entry_pending"),
            ]
        }
        assert runtime._process_recommendation_updates(db, subscription, updated, now) == 1
        assert len(payloads) == 1
        assert payloads[0]["title"] == "삼성전자 외 2건의 추천종목이 업데이트되었어요"
        assert payloads[0]["body"] == "추천종목 3건이 변경되었어요. 삼성전자의 상세에서 변경 내용을 확인하세요."
        assert payloads[0]["url"] == "/dashboard?view=recommend-detail&code=005930"
        assert payloads[0]["kind"] == "recommendation_update"

        # The summarized delivery is idempotent and must not repeat on the
        # next scan when the recommendation state has not changed.
        assert runtime._process_recommendation_updates(db, subscription, updated, now) == 0
        assert len(payloads) == 1
        initialized, codes, signals = runtime._recommendation_state(db, subscription)
        assert initialized is True
        assert codes == {"005930", "000660", "035420"}
        assert signals == {
            "005930": "holding",
            "000660": "buy-pending",
            "035420": "buy-pending",
        }
    finally:
        db.close()


def test_recommendation_updates_alert_only_when_ai_buy_or_sell_stage_changes(monkeypatch):
    db = _session()
    payloads = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/recommendation-signal",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["recommendation_update"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: payloads.append(json.loads(kwargs["data"])))
        runtime = web_push.WebPushRuntime(_settings())
        now = datetime(2026, 8, 24, 15, 45)
        initial = {"items": [_recommendation_item("005930", "삼성전자", 1, "82", "entry_pending")]}
        runtime._process_recommendation_updates(db, subscription, initial, now)

        holding = {"items": [_recommendation_item("005930", "삼성전자", 1, "82", "holding")]}
        assert runtime._process_recommendation_updates(db, subscription, holding, now) == 1
        assert payloads[-1]["title"] == "✅ [매수 확정·보유] 삼성전자"
        assert payloads[-1]["url"] == "/dashboard?view=recommend-detail&code=005930"

        assert runtime._process_recommendation_updates(db, subscription, holding, now) == 0
        assert len(payloads) == 1

        sell_pending = {
            "items": [_recommendation_item("005930", "삼성전자", 1, "81", "full_exit_pending")]
        }
        assert runtime._process_recommendation_updates(db, subscription, sell_pending, now) == 1
        assert payloads[-1]["title"] == "⚠️ [전량 매도 대기] 삼성전자"
        assert len(payloads) == 2
    finally:
        db.close()


def test_recommendation_pending_profit_waits_for_prior_market_confirmation(monkeypatch):
    db = _session()
    payloads = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/ordered-recommendation-signal",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["recommendation_update", "market_ai_signal"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(
            web_push,
            "webpush",
            lambda **kwargs: payloads.append(json.loads(kwargs["data"])),
        )
        runtime = web_push.WebPushRuntime(_settings())
        initial = {
            "items": [
                _recommendation_item(
                    "090430",
                    "아모레퍼시픽",
                    6,
                    "63.62",
                    "holding",
                    profit_stage=1,
                )
            ]
        }
        assert runtime._process_recommendation_updates(
            db,
            subscription,
            initial,
            datetime(2026, 8, 25, 15, 40),
        ) == 0

        pending = {
            "items": [
                _recommendation_item(
                    "090430",
                    "아모레퍼시픽",
                    6,
                    "63.62",
                    "partial_exit_pending",
                    profit_stage=1,
                    pending_profit_stage=3,
                    signal_label="3차 수익확정 대기",
                    latest_transition={
                        "side": "partial_sell",
                        "label": "1차 수익확정",
                        "transition_date": "2026-08-25",
                        "profit_stage": 1,
                    },
                )
            ]
        }

        # The shared market snapshot has not published the first confirmed
        # transition yet, so the next pending step must remain deferred.
        assert runtime._process_recommendation_updates(
            db,
            subscription,
            pending,
            datetime(2026, 8, 25, 15, 49),
        ) == 0
        assert payloads == []
        assert runtime._recommendation_state(db, subscription)[2]["090430"] == "holding"

        db.add(
            PushDelivery(
                subscription_id=subscription.id,
                event_key="market-ai-signal:090430:partial_sell:2026-08-25",
                notification_kind="market_ai_signal",
                title="💰 [1차 수익확정] 아모레퍼시픽",
                status="sent",
                attempts=1,
                sent_at=datetime(2026, 8, 25, 6, 49),
            )
        )
        db.commit()

        # Provider acceptance alone is not enough: wait through the 120-second
        # push TTL so the predecessor cannot still be queued on the device.
        assert runtime._process_recommendation_updates(
            db,
            subscription,
            pending,
            datetime(2026, 8, 25, 15, 50, 59),
        ) == 0
        assert payloads == []

        assert runtime._process_recommendation_updates(
            db,
            subscription,
            pending,
            datetime(2026, 8, 25, 15, 51, 1),
        ) == 1
        assert [payload["title"] for payload in payloads] == [
            "⏳ [3차 수익확정 대기] 아모레퍼시픽"
        ]
        assert "2차 수익확정" not in payloads[0]["title"]
    finally:
        db.close()


def test_signal_order_gate_respects_a_disabled_market_channel(monkeypatch):
    db = _session()
    calls = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/recommendation-only",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["recommendation_update"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: calls.append(kwargs))
        candidate = web_push.NotificationCandidate(
            event_key="recommendation-signal:090430:partial-sell-pending-3:2026-08-25",
            kind="recommendation_update",
            title="⏳ [3차 수익확정 대기] 아모레퍼시픽",
            body="다음 거래일 시가를 확인합니다.",
            url="/dashboard?view=recommend-detail&code=090430",
            tag="recommendation-signal-090430",
            occurred_at=datetime(2026, 8, 25, 15, 49),
            predecessor_event_key="market-ai-signal:090430:partial_sell:2026-08-25",
        )

        assert web_push.WebPushRuntime(_settings())._send(
            db,
            subscription,
            candidate,
        ) is True
        assert len(calls) == 1
    finally:
        db.close()


def test_market_session_candidates_send_the_requested_copy_five_minutes_before(monkeypatch):
    monkeypatch.setattr(web_push, "is_korea_market_session_date", lambda *_args: True)
    runtime = web_push.WebPushRuntime(_settings())

    opening = runtime._market_session_candidates(datetime(2026, 8, 4, 8, 55))
    closing = runtime._market_session_candidates(datetime(2026, 8, 4, 15, 25))

    assert [(item.kind, item.event_key, item.title, item.body) for item in opening] == [
        (
            "market_session",
            "market-session:open:2026-08-04",
            "국내장 시작 5분 전",
            "잠시 뒤 국내 정규장이 시작돼요",
        )
    ]
    assert [(item.kind, item.event_key, item.title, item.body) for item in closing] == [
        (
            "market_session",
            "market-session:close:2026-08-04",
            "국내장 마감 5분 전",
            "잠시 뒤 국내 정규장이 마감돼요",
        )
    ]


def test_market_session_candidates_skip_non_trading_days_and_other_times(monkeypatch):
    runtime = web_push.WebPushRuntime(_settings())
    monkeypatch.setattr(web_push, "is_korea_market_session_date", lambda *_args: False)
    assert runtime._market_session_candidates(datetime(2026, 8, 8, 8, 55)) == []

    monkeypatch.setattr(web_push, "is_korea_market_session_date", lambda *_args: True)
    assert runtime._market_session_candidates(datetime(2026, 8, 4, 8, 54, 59)) == []
    assert runtime._market_session_candidates(datetime(2026, 8, 4, 15, 30)) == []


def test_money_briefing_candidates_send_three_daily_editions_in_kst():
    runtime = web_push.WebPushRuntime(_settings())

    assert runtime._morning_briefing_candidates(datetime(2026, 8, 15, 7, 59, 59)) == []
    morning = runtime._morning_briefing_candidates(datetime(2026, 8, 15, 8, 0))[0]
    morning_late = runtime._morning_briefing_candidates(datetime(2026, 8, 15, 8, 4, 59))[0]
    assert runtime._morning_briefing_candidates(datetime(2026, 8, 15, 8, 5)) == []

    assert runtime._morning_briefing_candidates(datetime(2026, 8, 15, 11, 59, 59)) == []
    midday = runtime._morning_briefing_candidates(datetime(2026, 8, 15, 12, 0))[0]
    midday_late = runtime._morning_briefing_candidates(datetime(2026, 8, 15, 12, 4, 59))[0]
    assert runtime._morning_briefing_candidates(datetime(2026, 8, 15, 12, 5)) == []

    assert runtime._morning_briefing_candidates(datetime(2026, 8, 15, 15, 59, 59)) == []
    afternoon = runtime._morning_briefing_candidates(datetime(2026, 8, 15, 16, 0))[0]
    afternoon_late = runtime._morning_briefing_candidates(datetime(2026, 8, 15, 16, 4, 59))[0]
    assert runtime._morning_briefing_candidates(datetime(2026, 8, 15, 16, 5)) == []

    assert morning.event_key == "morning-briefing:2026-08-15"
    assert midday.event_key == "morning-briefing:2026-08-15:12"
    assert afternoon.event_key == "morning-briefing:2026-08-15:16"
    assert morning.tag == "morning-briefing-2026-08-15"
    assert midday.tag == "morning-briefing-2026-08-15-12"
    assert afternoon.tag == "morning-briefing-2026-08-15-16"
    assert morning.title == "아침에 보는 돈이 되는 소식"
    assert midday.title == "점심에 보는 돈이 되는 소식"
    assert afternoon.title == "오후에 보는 돈이 되는 소식"
    assert all("판" not in candidate.title for candidate in (morning, midday, afternoon))
    assert "오전 9시부터 낮 12시" in midday.body
    assert "낮 12시부터 오후 4시" in afternoon.body
    assert all(
        candidate.kind == "morning_briefing"
        and candidate.url == "/dashboard?view=morning-briefing"
        and candidate.ttl_seconds == 5 * 60
        for candidate in (morning, midday, afternoon)
    )
    assert morning_late.event_key == morning.event_key
    assert midday_late.event_key == midday.event_key
    assert afternoon_late.event_key == afternoon.event_key

    # 2026-08-15 is Saturday; the daily briefing is not limited to trading days.
    assert morning.occurred_at.date().isoformat() == "2026-08-15"
    morning_from_utc = runtime._morning_briefing_candidates(
        datetime(2026, 8, 14, 23, 0, tzinfo=timezone.utc)
    )[0]
    midday_from_utc = runtime._morning_briefing_candidates(
        datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)
    )[0]
    afternoon_from_utc = runtime._morning_briefing_candidates(
        datetime(2026, 8, 15, 7, 0, tzinfo=timezone.utc)
    )[0]
    assert morning_from_utc.event_key == morning.event_key
    assert midday_from_utc.event_key == midday.event_key
    assert afternoon_from_utc.event_key == afternoon.event_key


def test_money_briefing_notification_is_required_and_sent_once_per_edition(monkeypatch):
    db = _session()
    calls = []
    try:
        subscription = PushSubscription(
            share_id="tester",
            endpoint="https://push.example/morning-briefing",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["price_move"]',
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: calls.append(kwargs))
        runtime = web_push.WebPushRuntime(_settings())
        candidates = [
            runtime._morning_briefing_candidates(datetime(2026, 8, 15, hour, 0))[0]
            for hour in (8, 12, 16)
        ]

        assert "morning_briefing" in web_push.subscription_conditions(subscription)
        for candidate in candidates:
            assert web_push.candidate_enabled(subscription, candidate) is True
            assert runtime._send(db, subscription, candidate) is True
            assert runtime._send(db, subscription, candidate) is False
        assert len(calls) == 3
        assert all(call["ttl"] == 5 * 60 for call in calls)
        payloads = [json.loads(call["data"]) for call in calls]
        assert all(payload["kind"] == "morning_briefing" for payload in payloads)
        assert all(
            payload["url"] == "/dashboard?view=morning-briefing"
            for payload in payloads
        )
        assert {payload["tag"] for payload in payloads} == {
            "morning-briefing-2026-08-15",
            "morning-briefing-2026-08-15-12",
            "morning-briefing-2026-08-15-16",
        }
        assert db.query(PushDelivery).count() == 3
        assert db.query(PushNotificationHistory).count() == 3

        next_day = runtime._morning_briefing_candidates(datetime(2026, 8, 16, 8, 0))[0]
        assert runtime._send(db, subscription, next_day) is True
        assert len(calls) == 4
        assert db.query(PushNotificationHistory).count() == 4
    finally:
        db.close()


def test_market_session_reminder_respects_the_toggle_and_is_sent_once(monkeypatch):
    db = _session()
    calls = []
    try:
        enabled = PushSubscription(
            share_id="enabled",
            endpoint="https://push.example/enabled",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["ai_signal", "market_session"]',
        )
        disabled = PushSubscription(
            share_id="disabled",
            endpoint="https://push.example/disabled",
            p256dh="p" * 64,
            auth="a" * 24,
            notification_preferences='["ai_signal", "price_move"]',
        )
        db.add_all([enabled, disabled])
        db.commit()
        monkeypatch.setattr(web_push, "webpush", lambda **kwargs: calls.append(kwargs))
        candidate = web_push.NotificationCandidate(
            event_key="market-session:open:2026-08-04",
            kind="market_session",
            title="국내장 시작 5분 전",
            body="잠시 뒤 국내 정규장이 시작돼요",
            url="/dashboard?view=home",
            tag="market-session-open-2026-08-04",
        )
        runtime = web_push.WebPushRuntime(_settings())

        assert runtime._send(db, disabled, candidate) is False
        assert runtime._send(db, enabled, candidate) is True
        assert runtime._send(db, enabled, candidate) is False
        assert len(calls) == 1
    finally:
        db.close()


def test_market_ai_signal_candidates_are_built_from_saved_market_snapshot(monkeypatch):
    db = _session()
    try:
        monkeypatch.setattr(web_push, "is_korea_daily_signal_window", lambda _now=None: True)
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
                    {
                        "code": "035420",
                        "name": "NAVER",
                        "side": "buy",
                        "execution_date": "2026-07-03",
                    },
                ]
            },
        )

        candidates = web_push.WebPushRuntime(_settings())._market_ai_signal_candidates(
            db,
            datetime(2026, 7, 28, 9, 30),
        )

        assert [candidate.kind for candidate in candidates] == [
            "market_ai_signal",
            "market_ai_signal",
        ]
        assert candidates[0].event_key == "market-ai-signal:005930:buy:2026-07-28"
        assert candidates[0].title == "✅ [매수 확정] 삼성전자"
        assert candidates[0].body == (
            "2026-07-28 매수 확정 신호예요. 종목 상세에서 가격과 기준을 확인하세요."
        )
        assert candidates[1].event_key == "market-ai-signal:000660:sell:2026-07-28"
        assert candidates[1].title == "🚨 [전량 매도] SK하이닉스"
        assert all("2026-07-03" not in candidate.event_key for candidate in candidates)
    finally:
        db.close()


def test_market_ai_signal_candidates_use_canonical_source_when_configured(monkeypatch):
    db = _session()
    try:
        monkeypatch.setattr(web_push, "is_korea_daily_signal_window", lambda _now=None: True)
        monkeypatch.setattr(
            web_push,
            "load_external_market_quant_signal_feed",
            lambda *_args, **_kwargs: {
                "status": "ready",
                "items": [
                    {
                        "code": "086790",
                        "name": "하나금융지주",
                        "side": "sell",
                        "execution_date": "2026-08-03",
                    }
                ],
            },
        )
        monkeypatch.setattr(
            web_push,
            "load_market_quant_signal_snapshot",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("local snapshot used")),
        )
        settings = _settings().model_copy(
            update={"market_quant_signal_source_url": "https://signals.example"}
        )

        candidates = web_push.WebPushRuntime(settings)._market_ai_signal_candidates(
            db,
            datetime(2026, 8, 3, 16, 0),
        )

        assert len(candidates) == 1
        assert candidates[0].event_key == "market-ai-signal:086790:sell:2026-08-03"
    finally:
        db.close()


def test_market_ai_signal_candidates_include_oci_strategy_reconciliation(monkeypatch):
    db = _session()
    try:
        monkeypatch.setattr(web_push, "is_korea_daily_signal_window", lambda _now=None: True)
        monkeypatch.setattr(
            web_push,
            "load_market_quant_signal_snapshot",
            lambda *_args, **_kwargs: {
                "status": "ready",
                "strategy_version": "position-lifecycle-v7.0",
                "recent_days": 30,
                "items": [],
            },
        )

        candidates = web_push.WebPushRuntime(_settings())._market_ai_signal_candidates(
            db,
            datetime(2026, 8, 20, 16, 0),
        )

        assert len(candidates) == 1
        assert candidates[0].event_key == "market-ai-signal:010060:sell:2026-08-20"
        assert candidates[0].title == "🚨 [전량 매도] OCI홀딩스"
    finally:
        db.close()


def test_market_ai_preliminary_candidates_are_labeled_and_deduplicated_separately(monkeypatch):
    db = _session()
    try:
        monkeypatch.setattr(web_push, "is_korea_daily_signal_window", lambda _now=None: False)
        monkeypatch.setattr(web_push, "is_korea_regular_market_session", lambda _now=None: True)
        monkeypatch.setattr(
            web_push,
            "load_market_quant_signal_snapshot",
            lambda *_args, **_kwargs: {
                "items": [
                    {
                        "code": "005930",
                        "name": "삼성전자",
                        "side": "buy",
                        "signal_date": "2026-08-03",
                        "status": "preliminary",
                        "is_preliminary": True,
                    },
                    {
                        "code": "000660",
                        "name": "SK하이닉스",
                        "side": "sell",
                        "signal_date": "2026-08-03",
                        "status": "preliminary",
                        "is_preliminary": True,
                    },
                ]
            },
        )

        candidates = web_push.WebPushRuntime(_settings())._market_ai_signal_candidates(
            db,
            datetime(2026, 8, 3, 13, 20),
        )

        assert [candidate.event_key for candidate in candidates] == [
            "market-ai-preliminary:005930:buy:2026-08-03",
            "market-ai-preliminary:000660:sell:2026-08-03",
        ]
        assert candidates[0].title == "✨ [예비 매수] 삼성전자"
        assert candidates[1].title == "⚠️ [예비 매도] SK하이닉스"
        assert all("15:40 확정 전에는 바뀔 수 있어요" in candidate.body for candidate in candidates)
        assert all(candidate.kind == "market_ai_signal" for candidate in candidates)
    finally:
        db.close()


def test_signal_notification_history_requires_event_and_receipt_on_same_kst_date():
    received_at = datetime(2026, 7, 29, 14, 46)

    assert web_push.notification_history_is_valid(
        "market_ai_signal",
        "market-ai-signal:005930:buy:2026-07-29",
        received_at,
    ) is True
    assert web_push.notification_history_is_valid(
        "market_ai_signal",
        "market-ai-signal:005930:buy:2026-07-22",
        received_at,
    ) is False
    assert web_push.notification_history_is_valid(
        "report",
        "report:naver:existing",
        received_at,
    ) is True


def test_signal_notification_history_reads_current_and_legacy_stock_names():
    assert web_push.notification_history_signal_name("✨ [예비 매수] 삼성전자") == "삼성전자"
    assert web_push.notification_history_signal_name("⚠️ [예비 매도] GS") == "GS"
    assert (
        web_push.notification_history_signal_name("삼성전자 시장 AI 시그널 · 예비 매수")
        == "삼성전자"
    )


def test_signal_notification_history_exposes_structured_preliminary_context():
    assert web_push.notification_history_signal_context(
        "market_ai_signal",
        "market-ai-preliminary:003550:buy:2026-08-13",
    ) == {
        "code": "003550",
        "side": "buy",
        "phase": "preliminary",
        "action": "entry_pending",
        "event_date": "2026-08-13",
    }
    assert web_push.notification_history_signal_context(
        "ai_signal",
        "ai-signal:003230:full_exit_pending:2026-08-13",
    ) == {
        "code": "003230",
        "side": "sell",
        "phase": "preliminary",
        "action": "full_exit_pending",
        "event_date": "2026-08-13",
    }
    assert web_push.notification_history_signal_context(
        "ai_signal",
        "ai-signal:035420:entry_watch:2026-08-13",
    ) == {
        "code": "035420",
        "side": "buy",
        "phase": "preliminary",
        "action": "entry_watch",
        "event_date": "2026-08-13",
    }
    assert web_push.notification_history_signal_context(
        "market_ai_signal",
        "market-ai-signal:003550:buy:2026-08-13",
    ) is None


def test_market_notification_history_rejects_weekend_events():
    received_at = datetime(2026, 8, 2, 1, 0)

    assert web_push.notification_history_is_valid(
        "market_ai_signal",
        "market-ai-signal:078930:buy:2026-08-02",
        received_at,
    ) is False
    assert web_push.notification_history_is_valid(
        "price_move",
        "price:2026-08-02:078930:rise:5.0",
        received_at,
    ) is False


def test_invalid_backfilled_signal_history_is_pruned():
    db = _session()
    try:
        db.add_all(
            [
                PushNotificationHistory(
                    share_id="tester",
                    event_key="market-ai-signal:005930:buy:2026-07-29",
                    notification_kind="market_ai_signal",
                    title="정상 알림",
                    body="당일 확정 신호",
                    created_at=datetime(2026, 7, 29, 14, 46),
                ),
                PushNotificationHistory(
                    share_id="tester",
                    event_key="market-ai-signal:000660:sell:2026-07-22",
                    notification_kind="market_ai_signal",
                    title="과거 신호 재적재",
                    body="뒤늦게 적재된 과거 신호",
                    created_at=datetime(2026, 7, 29, 14, 46),
                ),
            ]
        )
        db.commit()

        assert web_push._prune_invalid_signal_notification_history(db) == 1
        db.commit()

        histories = db.query(PushNotificationHistory).all()
        assert [item.title for item in histories] == ["정상 알림"]
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
            title="✅ [매수 확정] 삼성전자",
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
            title="🚨 [전량 매도] SK하이닉스",
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
        monkeypatch.setattr(web_push, "is_korea_daily_signal_window", lambda _now=None: True)
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
        assert candidates["tester"][0].title == "✨ [예비 매수] 삼성전자"
        assert candidates["tester"][0].event_key == "ai-signal:005930:entry_pending:2026-07-25"
    finally:
        db.close()


def test_watchlist_ai_signal_uses_canonical_stock_state_when_configured(monkeypatch):
    db = _session()
    try:
        monkeypatch.setattr(web_push, "is_korea_daily_signal_window", lambda _now=None: True)
        watch = WatchlistItem(share_id="tester", code="175330", name="JB금융지주", market="KOSPI")
        db.add(watch)
        db.commit()
        calls = []

        def canonical_loader(*_args, **kwargs):
            calls.append(kwargs)
            return {
                "price_through": "2026-08-04",
                "signal_source": "canonical",
                "current": {
                    "action": "entry_pending",
                    "next_confirmation": "다음 거래일 시가를 확인합니다.",
                    "lifecycle": {"latest_transition": None},
                },
            }

        monkeypatch.setattr(web_push, "load_reference_quant_signal_payload", canonical_loader)
        monkeypatch.setattr(
            web_push,
            "load_quant_signal_payload",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("local signal used")),
        )
        settings = _settings().model_copy(
            update={"market_quant_signal_source_url": "https://signals.example"}
        )

        candidates = web_push.WebPushRuntime(settings)._ai_signal_candidates(
            db,
            {"tester": [watch]},
            datetime(2026, 8, 4, 16, 0),
        )

        assert calls[0]["source_url"] == "https://signals.example"
        assert candidates["tester"][0].event_key == "ai-signal:175330:entry_pending:2026-08-04"
        assert candidates["tester"][0].title == "✨ [예비 매수] JB금융지주"
    finally:
        db.close()


def test_watchlist_ai_signal_uses_latest_confirmed_sell_when_engine_returns_entry_pending():
    watch = WatchlistItem(share_id="tester", code="105560", name="KB금융", market="KOSPI")
    now = datetime(2026, 8, 8, 16, 0)
    candidate = web_push._ai_signal_candidate(
        watch,
        {
            "price_through": "2026-08-08",
            "current": {
                "action": "entry_pending",
                "position_open": False,
                "live_observation": False,
                "next_confirmation": "다음 매수 조건을 기다립니다.",
                "lifecycle": {
                    "latest_transition": {
                        "transition_date": "2026-08-08",
                        "label": "전략상 청산",
                    }
                },
            },
        },
        now,
    )

    assert candidate is not None
    assert candidate.event_key == "ai-signal:105560:exited:2026-08-08"
    assert candidate.title == "🚨 [전량 매도] KB금융"


def test_watchlist_ai_signal_candidate_uses_profit_ladder_stage_labels():
    watch = WatchlistItem(share_id="tester", code="005830", name="DB손해보험", market="KOSPI")
    now = datetime(2026, 8, 20, 13, 20)

    pending = web_push._ai_signal_candidate(
        watch,
        {
            "price_through": "2026-08-19",
            "current": {
                "action": "partial_exit_pending",
                "profit_stage": 1,
                "as_of": "2026-08-20T13:20:00+09:00",
                "live_observation": True,
                "next_confirmation": "다음 거래일 시가에 수익확정을 반영합니다.",
                "lifecycle": {"latest_transition": None},
            },
        },
        now,
    )
    confirmed = web_push._ai_signal_candidate(
        watch,
        {
            "price_through": "2026-08-20",
            "current": {
                "action": "partially_exited",
                "profit_stage": 2,
                "live_observation": False,
                "next_confirmation": "3차 수익확정가와 수익 보호선을 확인합니다.",
                "lifecycle": {
                    "latest_transition": {
                        "transition_date": "2026-08-20",
                        "label": "2차 수익확정",
                    }
                },
            },
        },
        now,
    )

    assert pending is not None
    assert pending.title == "⏳ [2차 수익확정 대기] DB손해보험"
    assert confirmed is not None
    assert confirmed.title == "💰 [2차 수익확정] DB손해보험"


def test_watchlist_pending_profit_uses_actual_target_stage():
    watch = WatchlistItem(
        share_id="tester",
        code="090430",
        name="아모레퍼시픽",
        market="KOSPI",
    )
    candidate = web_push._ai_signal_candidate(
        watch,
        {
            "price_through": "2026-08-25",
            "current": {
                "action": "partial_exit_pending",
                "label": "3차 수익확정 대기",
                "profit_stage": 1,
                "pending_profit_stage": 3,
                "profit_steps_total": 3,
                "live_observation": False,
                "next_confirmation": "다음 거래일 시가에 잔여비중을 55%로 축소합니다.",
                "lifecycle": {
                    "label": "3차 수익확정 대기",
                    "latest_transition": {
                        "side": "partial_sell",
                        "label": "1차 수익확정",
                        "transition_date": "2026-08-25",
                        "profit_stage": 1,
                    },
                },
            },
        },
        datetime(2026, 8, 25, 15, 49),
    )

    assert candidate is not None
    assert candidate.title == "⏳ [3차 수익확정 대기] 아모레퍼시픽"


def test_watchlist_ai_signal_candidate_emits_intraday_preliminary_action(monkeypatch):
    db = _session()
    try:
        monkeypatch.setattr(web_push, "is_korea_daily_signal_window", lambda _now=None: False)
        monkeypatch.setattr(web_push, "is_korea_regular_market_session", lambda _now=None: True)
        watch = WatchlistItem(share_id="tester", code="005930", name="삼성전자", market="KOSPI")
        db.add(watch)
        db.commit()
        monkeypatch.setattr(
            web_push,
            "load_quant_signal_payload",
            lambda *_args, **_kwargs: {
                "price_through": "2026-07-31",
                "current": {
                    "action": "entry_pending",
                    "as_of": "2026-08-03T13:20:00+09:00",
                    "live_observation": True,
                    "next_confirmation": "종가에서 조건을 다시 확인합니다.",
                    "lifecycle": {"latest_transition": None},
                },
            },
        )

        candidates = web_push.WebPushRuntime(_settings())._ai_signal_candidates(
            db,
            {"tester": [watch]},
            datetime(2026, 8, 3, 13, 20),
            {"005930": {"price": 80_000, "volume": 1_000_000}},
        )

        candidate = candidates["tester"][0]
        assert candidate.event_key == "ai-signal:005930:entry_pending:2026-08-03"
        assert candidate.title == "✨ [예비 매수] 삼성전자"
        assert "장 마감 전에는 바뀔 수 있어요" in candidate.body
    finally:
        db.close()


def test_watchlist_ai_signal_candidate_emits_confirmed_close_entry_watch():
    watch = WatchlistItem(share_id="tester", code="035420", name="NAVER", market="KOSPI")
    candidate = web_push._ai_signal_candidate(
        watch,
        {
            "price_through": "2026-08-20",
            "current": {
                "action": "entry_watch",
                "live_observation": False,
                "next_confirmation": "5일 흐름이 2.0%를 넘으면 매수 조건을 확인합니다.",
                "lifecycle": {"latest_transition": None},
            },
        },
        datetime(2026, 8, 20, 16, 0),
    )

    assert candidate is not None
    assert candidate.event_key == "ai-signal:035420:entry_watch:2026-08-20"
    assert candidate.title == "🔎 [예비 포착] NAVER"
    assert "장 마감 전에는" not in candidate.body


def test_ai_signal_candidates_are_blocked_outside_daily_close_window(monkeypatch):
    db = _session()
    try:
        watch = WatchlistItem(share_id="tester", code="005930", name="삼성전자", market="KOSPI")
        monkeypatch.setattr(web_push, "is_korea_daily_signal_window", lambda _now=None: False)
        monkeypatch.setattr(
            web_push,
            "load_quant_signal_payload",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("signal engine must not run")),
        )

        candidates = web_push.WebPushRuntime(_settings())._ai_signal_candidates(
            db,
            {"tester": [watch]},
            datetime(2026, 8, 2, 9, 35),
        )

        assert candidates == {"tester": []}
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
