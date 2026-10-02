from datetime import datetime, timedelta, timezone
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.services.intraday_signals import (
    VERSION, Minute, IntradayState, IntradayEvent, IntradayMinute, decide, record, feed,
)
from app.services.intraday_monitor import normalize_bars, IntradayMonitor

OPEN = datetime(2026, 10, 2, 0, tzinfo=timezone.utc)


def arguments(market="kr"):
    # Last five minutes recover above the rolling weighted mean after a dip.
    rows = [Minute(OPEN + timedelta(minutes=i), 100, 101, 99, 100, 1000)
            for i in range(21)]
    rows[14] = replace(rows[14], close=99.5)
    rows[19] = replace(rows[19], close=100.5)
    rows[20] = replace(rows[20], close=100.5)
    return dict(market=market, code="005930" if market == "kr" else "AAPL",
                name="Test", mode="shadow", minutes=rows,
                context=dict(ready=True, evidence_allowed=True, score=70,
                    atr_percent=.02, momentum5=.02, volume_ratio=1.2,
                    average_trading_value=1e10, ema20=99, ema60=98,
                    previous_close=100, session_open=OPEN.isoformat()),
                now=OPEN + timedelta(minutes=20, seconds=10),
                session_open=OPEN, session_close=OPEN+timedelta(hours=6, minutes=30),
                in_universe=True)


@pytest.mark.parametrize("market", ["kr", "us"])
def test_intraday_completed_buy_is_immutable_and_not_repeated(market):
    args = arguments(market)
    state, event, reason = decide({}, **args)
    assert reason == "confirmed" and event["side"] == "buy"
    frozen = json.dumps(event)
    again, event2, _ = decide(state, **args)
    assert event2 is None and again["remaining"] == 1
    args["minutes"][-1] = replace(args["minutes"][-1], close=99.5)
    assert decide(again, **args)[1] is None
    assert json.dumps(event) == frozen


@pytest.mark.parametrize("fault,expected", [
    ("forming", "await_completed_bar"), ("gap", "minute_gap"),
    ("future", "future_bars"), ("stale", "stale"),
    ("context", "evidence_unavailable"), ("old_context", "stale_context"),
    ("universe", "outside_top100"), ("closed", "closed"),
    ("nan", "invalid_bars"), ("score", "quality_filter"),
    ("chase", "chase_guard"), ("duplicate", "conflicting_bars"),
])
def test_intraday_fail_closed(fault, expected):
    args = arguments()
    if fault == "forming":
        args["now"] = OPEN+timedelta(minutes=19, seconds=59)
        args["minutes"] = args["minutes"][:20]
    elif fault == "gap":
        args["minutes"].pop(3)
    elif fault == "future":
        args["minutes"][-1] = replace(args["minutes"][-1], start=OPEN+timedelta(days=1))
    elif fault == "stale":
        args["now"] += timedelta(minutes=10)
    elif fault == "context":
        args["context"]["evidence_allowed"] = False
    elif fault == "old_context":
        args["context"]["session_open"] = (OPEN-timedelta(days=1)).isoformat()
    elif fault == "universe":
        args["in_universe"] = False
    elif fault == "closed":
        args["now"] = args["session_close"]
    elif fault == "nan":
        args["minutes"][-1] = replace(args["minutes"][-1], close=float("nan"))
    elif fault == "score":
        args["context"]["score"] = 20
    elif fault == "chase":
        args["minutes"][-1] = replace(args["minutes"][-1], high=104, close=104)
    elif fault == "duplicate":
        args["minutes"].append(replace(args["minutes"][-1], close=100.6))
    assert decide({}, **args)[1:] == (None, expected)


def test_intraday_targets_stop_and_no_same_session_reentry():
    args = arguments()
    state, buy, _ = decide({}, **args)
    entry = state["entry_price"]
    def quote(price):
        args["minutes"][-1] = replace(args["minutes"][-1], open=price, high=price, low=price, close=price)
    quote(entry*1.03)
    state, partial, _ = decide(state, **args)
    assert partial["side"] == "partial_sell" and state["remaining"] == .5
    assert decide(state, **args)[1] is None
    # Intraday lows are not fabricated fills: only the observed price exits.
    quote(entry*1.05)
    state, sold, _ = decide(state, **args)
    assert sold["side"] == "sell" and sold["fraction"] == .5
    assert decide(state, **args)[2] == "reentry_blocked"
    quote(entry*.94)
    state2 = dict(entry_price=entry, remaining=1, stop_price=entry*.96,
                  entry_at=buy["occurred_at"], entry_bar=buy["confirmation_bar"])
    _, stop, _ = decide(state2, **args)
    assert stop["reference_price"] == entry*.94
    assert stop["reason"] == "protective_stop"


def test_intraday_exit_survives_universe_and_evidence_outage():
    args = arguments()
    state, _, _ = decide({}, **args)
    args.update(in_universe=False, context={})
    args["minutes"][-1] = replace(args["minutes"][-1], open=90, high=90, low=90, close=90)
    assert decide(state, **args)[1]["side"] == "sell"


def test_intraday_durable_restart_and_shadow_alert_isolation():
    engine = create_engine("sqlite://")
    for model in (IntradayState, IntradayEvent, IntradayMinute):
        model.__table__.create(engine)
    args = arguments()
    with Session(engine) as db:
        record(db, **args)
    with Session(engine) as db:
        record(db, **args)
        assert len(list(db.scalars(select(IntradayEvent)))) == 1
        assert feed(db, "kr", "alerts")["items"] == []
        assert feed(db, "kr", "shadow")["items"][0]["status"] == "confirmed"


def test_intraday_us_local_date_and_kr_time_normalization():
    us = normalize_bars([dict(xymd="20261001", xhms="155900", open=100,
        high=101, low=99, last=100, evol=100)], "us")[0]
    assert us.start.isoformat() == "2026-10-01T19:59:00+00:00"
    kr = normalize_bars([dict(stck_bsop_date="20261002", stck_cntg_hour="090100",
        stck_oprc=100, stck_hgpr=101, stck_lwpr=99, stck_prpr=100, cntg_vol=100)], "kr")[0]
    assert kr.start.isoformat() == "2026-10-02T00:01:00+00:00"


def test_intraday_us_provider_share_classes_and_identity():
    calls = []
    def get(path, tr, params):
        calls.append(params)
        return {"output1":{"rsym":"DNYSBRK/B"},"output2":[]}
    monitor = IntradayMonitor(SimpleNamespace(), SimpleNamespace(_get=get), None)
    assert monitor.bars("us", {"code":"BRK.B","exchange":"NYSE"}, OPEN) == []
    assert calls[0]["SYMB"] == "BRK/B" and calls[0]["NMIN"] == "1"
    with pytest.raises(ValueError, match="source_identity_mismatch"):
        monitor.bars("us", {"code":"AAPL","exchange":"NASDAQ"}, OPEN)


def test_intraday_default_off_has_no_collection_or_push():
    monitor = IntradayMonitor(SimpleNamespace(intraday_signal_mode="off"), None, None)
    assert monitor.run_once() is None


def test_intraday_us_notification_history_uses_new_york_session_date():
    from app.services.web_push import notification_history_is_valid, notification_history_signal_context
    key = "intraday:us:AAPL:buy:" + "a"*64 + ":2026-10-01"
    # October 2 in Korea, still October 1 in New York.
    created = datetime(2026, 10, 1, 19, tzinfo=timezone.utc)
    assert notification_history_is_valid("market_ai_signal", key, created)
    assert notification_history_signal_context("market_ai_signal", key)["phase"] == "confirmed"


def test_intraday_us_holiday_and_dst_calendar():
    from app.services.intraday_monitor import session_bounds
    assert session_bounds("us", datetime(2026, 12, 25, 16, tzinfo=timezone.utc)) is None
    winter = session_bounds("us", datetime(2026, 12, 1, 16, tzinfo=timezone.utc))
    summer = session_bounds("us", datetime(2026, 10, 1, 16, tzinfo=timezone.utc))
    assert winter[0].hour == 14 and summer[0].hour == 13


def test_intraday_worker_scans_top100_without_subscribers_and_retains_positions(tmp_path, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    import app.services.intraday_monitor as module
    from app.db import Base
    engine = create_engine(f"sqlite:///{tmp_path}/monitor.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(module, "SessionLocal", factory)
    args = arguments()
    bounds = (args["session_open"], args["session_close"], OPEN.date()-timedelta(days=1))
    monkeypatch.setattr(module, "session_bounds", lambda *a: bounds)
    items = [dict(code=f"{i:06}", name=f"stock {i}") for i in range(100)]
    monkeypatch.setattr(module, "universe", lambda *a: items)
    settings = SimpleNamespace(intraday_signal_mode="shadow", us_market_enabled=False,
        intraday_signal_max_age_seconds=90)
    monitor = IntradayMonitor(settings, SimpleNamespace(is_configured=lambda: True),
        SimpleNamespace(configured=False))
    monkeypatch.setattr(monitor, "bars", lambda *a: args["minutes"])
    monkeypatch.setattr(monitor, "context", lambda *a: args["context"])
    monitor.run_once(now=args["now"])
    monitor.run_once(now=args["now"])
    with factory() as db:
        result = feed(db, "kr", "shadow")
        assert len(result["items"]) == 100
        assert result["monitor"]["universe_count"] == 100
        assert result["monitor"]["evaluated"] == 100
        assert not result["monitor"]["push_ready"]
    # Losing the universe or context must NOT stop protection of held stocks.
    monkeypatch.setattr(module, "universe", lambda *a: (_ for _ in ()).throw(ValueError()))
    args["minutes"][-1] = replace(args["minutes"][-1], open=90, high=90, low=90, close=90)
    monkeypatch.setattr(monitor, "context", lambda *a: (_ for _ in ()).throw(ValueError()))
    monitor.run_once(now=args["now"])
    with factory() as db:
        result = feed(db, "kr", "shadow")
        assert result["monitor"]["state"] == "degraded"
        assert result["monitor"]["evaluated"] == 100
        events = list(db.scalars(select(IntradayEvent)))
        assert len(events) == 200
        assert sum(json.loads(e.payload)["side"] == "sell" for e in events) == 100


def test_intraday_push_optin_mode_scope_and_no_historical_delivery(tmp_path, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from app.models import PushSubscription
    import app.services.intraday_monitor as module
    engine = create_engine(f"sqlite:///{tmp_path}/push.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(module, "SessionLocal", factory)
    now = datetime.utcnow()
    with factory() as db:
        for i, (share, preferences, created) in enumerate([
            ("kr.user", '["market_ai_signal"]', now-timedelta(days=1)),
            ("us.user", '["market_ai_signal"]', now-timedelta(days=1)),
            ("no.optin", '["major_event"]', now-timedelta(days=1)),
            ("new.user", '["market_ai_signal"]', now+timedelta(seconds=1)),
        ]):
            db.add(PushSubscription(share_id=share, endpoint=f"https://example.com/{i}",
                p256dh="test", auth="test", notification_preferences=preferences,
                enabled=True, created_at=created, updated_at=created))
        for i, mode in enumerate(["shadow", "alerts"]):
            event = dict(event_id=str(i), name="Test", side="buy", reference_price=100,
                         currency="KRW", code="005930")
            db.add(IntradayEvent(event_id=str(i), market="kr", mode=mode,
                occurred_at=now, payload=json.dumps(event)))
        db.commit()
    sent = []
    push = SimpleNamespace(configured=True, _send=lambda db, sub, candidate: sent.append(sub.share_id))
    settings = SimpleNamespace(intraday_signal_mode="shadow")
    monitor = IntradayMonitor(settings, None, push)
    monitor.deliver("kr")
    assert sent == []
    settings.intraday_signal_mode = "alerts"
    monitor.deliver("kr")
    assert sent == ["kr.user"]


def test_intraday_http_market_isolation_and_monitor_page(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    import app.main as main
    from app.db import Base, get_db
    engine = create_engine(f"sqlite:///{tmp_path}/http.db", connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    def get_session():
        with factory() as session:
            yield session
    main.app.dependency_overrides[get_db] = get_session
    monkeypatch.setattr(main.settings, "intraday_signal_mode", "shadow")
    client = TestClient(main.app)
    try:
        for is_us in (False, True):
            monkeypatch.setattr(main.settings, "us_market_enabled", is_us)
            prefix, other = ("/us", "") if is_us else ("", "/us")
            response = client.get(prefix+"/market/intraday-signals")
            assert response.status_code == 200
            assert response.json()["mode"] == "shadow"
            assert response.json()["items"] == []
            assert response.headers["cache-control"] == "no-store"
            assert client.get(other+"/market/intraday-signals").status_code == 404
            page = client.get(prefix+"/intraday-alerts")
            assert page.status_code == 200
            assert "실제 주문" in page.text and "상태 조회 실패" in page.text
    finally:
        main.app.dependency_overrides.pop(get_db, None)


def test_intraday_staging_preserves_bases_and_never_promotes():
    from pathlib import Path
    workflow = Path(".github/workflows/deploy-staging-production.yml").read_text()
    job = workflow.split("  intraday_shadow_staging:", 1)[1].split("  validate_request:", 1)[0]
    assert "needs: [validate_request, gate, build_image]" in job
    assert "git merge-base --is-ancestor f794377 HEAD" in job
    assert "git merge-base --is-ancestor 2da0ebf HEAD" in job
    assert "INTRADAY_SIGNAL_MODE=shadow" in job
    assert "INTRADAY_SIGNAL_MODE=alerts" not in job
    assert "--environment staging" in job
    assert "--environment production" not in job
    assert '--expected-digest "$EXPECTED_DIGEST"' in job
    assert 'image_ref:$image' in job
