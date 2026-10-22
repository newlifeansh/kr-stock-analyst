from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    DisclosureItem,
    IngestionRun,
    PushSubscription,
    QuantSignalIntradayPathSnapshot,
    QuantSignalObservedEntry,
    StockMaster,
    WatchlistItem,
)
from app.services import live_order_guard, observed_entry as oe, quant_signals as qs, web_push
from app.services.public_signal import public_quant_signal_payload
from app.services.signal_entry_evidence import _disclosure_evidence
from test_quant_signals import _strategy_test_inputs, _set_entry_indicator, _daily_rows_from_bars
from test_web_push import _settings

DAY = date(2026, 10, 22)
START = datetime(2026, 10, 22, 9, 2, tzinfo=oe.KST)


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    bars, indicators = _strategy_test_inputs(125)
    days = []
    cursor = DAY - timedelta(days=1)
    while len(days) < len(bars):
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    bars = [replace(bar, trade_date=day) for bar, day in zip(bars, reversed(days))]
    live_indicator = dict(indicators[-1])
    _set_entry_indicator(live_indicator)
    live_indicator.update(atr=2.0, ema20=100.0, prior_high=101.0)
    monkeypatch.setattr(qs, "_indicator_rows", lambda values: [
        dict(live_indicator if bar.trade_date == DAY else indicators[-1]) for bar in values
    ])
    monkeypatch.setattr(oe, "_same_time_volume_context", lambda *args, **kwargs: {
        "basis": "test_same_minute", "ratio": live_indicator["volume_ratio"],
        "current_cumulative_volume": 1000.0, "expected_cumulative_volume": 1000.0,
        "sample_count": 20, "as_of_minute": kwargs["minute_at"].isoformat(),
    })
    with Session(engine, autoflush=False) as db:
        stock = StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True)
        db.add(stock)
        db.commit()
        yield db, stock, bars, live_indicator


def evidence(now):
    return {
        "signal_date": "2026-10-21", "stock_code": "005930",
        "generated_at": now.isoformat(), "quality": {"state": "ready"},
        "supportive_count": 2, "caution_count": 0, "vetoes": [],
        "required_supports": {"trend_continuation": 1, "early_turn": 2},
    }


def minute(close=100, *, high=None, low=None, closed_at=None):
    return qs.PriceBar(
        DAY, close, high or close, low or close, close, 1000, 100000,
        closed_at=closed_at,
    )


def test_preliminary_volume_gate_is_distinct_from_confirmed_h1_gate():
    bars, indicators = _strategy_test_inputs(1)
    bar = replace(bars[0], trade_date=DAY, close=101.0)
    indicator = dict(indicators[0])
    _set_entry_indicator(indicator)
    indicator.update(
        volume_ratio=oe.PRELIMINARY_VOLUME_RATIO,
        ema20=100.0,
        ema60=99.0,
        high_distance=-0.01,
    )

    assert qs._pre_entry_signal(bar, indicator) is True
    assert qs._entry_setup_kind(bar, indicator) is None
    indicator["volume_ratio"] = oe.CONFIRMED_VOLUME_RATIO
    assert qs._entry_setup_kind(bar, indicator) == "trend_continuation"


def test_intraday_volume_uses_finalized_same_minute_history_before_daily_fallback():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for offset in range(1, 4):
            historical_day = DAY - timedelta(days=offset)
            db.add(QuantSignalIntradayPathSnapshot(
                stock_code="005930",
                trade_date=historical_day,
                strategy_version=qs.STRATEGY_VERSION,
                source="kis_rest",
                payload='[{"trade_time":"090000","volume":400},{"trade_time":"090100","volume":600},{"trade_time":"100000","volume":9999}]',
                is_final=True,
                observed_at=datetime.combine(historical_day, datetime.min.time()),
            ))
        db.flush()
        daily_bars, _ = _strategy_test_inputs(20)
        context = oe._same_time_volume_context(
            db,
            "005930",
            bars=daily_bars,
            minutes=[minute(), minute()],
            minute_at=START.replace(hour=9, minute=1),
        )
        fallback = oe._same_time_volume_context(
            db,
            "000660",
            bars=daily_bars,
            minutes=[minute(), minute()],
            minute_at=START.replace(hour=9, minute=1),
        )

    assert context["basis"] == "historical_same_minute"
    assert context["sample_count"] == 3
    assert context["current_cumulative_volume"] == 2000
    assert context["expected_cumulative_volume"] == 1000
    assert context["ratio"] == 2.0
    assert fallback["basis"] == "elapsed_session_fallback"
    assert fallback["sample_count"] == 0
    assert fallback["expected_cumulative_volume"] == pytest.approx(5128.205, abs=0.001)
    assert fallback["ratio"] == pytest.approx(0.39, abs=0.001)


def observe(setup, now=START, *, minutes=None, minute_at=None, publish=True, **changes):
    db, stock, bars, _ = setup
    args = dict(now=now, bars=bars, minutes=minutes or [minute()],
                minute_at=minute_at or now.replace(second=0) - timedelta(minutes=1),
                available=True, last_exit_index=None, guard=None, evidence=evidence(now),
                universe_eligible=True, universe_rank=3)
    args.update(changes)
    record = oe.observe(db, stock.code, **args)
    if publish and record and record["status"] == "watching":
        oe.mark_published(db, [{"code": stock.code, "is_preliminary": True,
                               "observed_entry": oe.public_state(record)}], now)
        return oe.load_records(db, stock.code, now)[DAY]
    return record


def confirmed(setup):
    minutes = [minute(high=130, low=70), minute(), minute(101)]
    first = observe(setup, minutes=minutes[:1])
    result = observe(setup, START + timedelta(minutes=2), minutes=minutes)
    assert first["status"] == "watching"
    assert result["status"] == "confirmed"
    return result, minutes


def test_capture_then_later_closed_minute_confirms_once_across_restart(setup):
    db, stock, _, _ = setup
    first = observe(setup, minutes=[minute(102)])
    assert first["status"] == "watching"  # Even a full setup cannot buy on capture.
    db.commit()
    db.expire_all()
    same_minute = observe(setup, START + timedelta(seconds=30), minutes=[minute(102)])
    assert same_minute["first_observed_at"] == first["first_observed_at"]
    assert same_minute["status"] == "watching"
    containing = observe(setup, START + timedelta(minutes=1), minutes=[minute(102), minute(102)])
    assert containing["status"] == "watching"
    later = observe(setup, START + timedelta(minutes=2), minutes=[minute(102)] * 3)
    assert later["status"] == "confirmed"
    assert later["order"]["minute_index"] == 2
    assert later["order"]["price"] == 102
    db.commit()
    with Session(db.bind) as restarted:
        saved = oe.load_records(restarted, stock.code, START + timedelta(minutes=3))[DAY]
        assert saved == later
    assert observe(setup, START + timedelta(minutes=3), minutes=[minute(105)] * 4) == later
    assert len(list(db.scalars(select(QuantSignalObservedEntry)))) == 1


def test_no_retroactive_touch_or_unfinished_minute_confirmation(setup):
    observe(setup, minutes=[minute(102)])
    now = START + timedelta(minutes=2)
    result = observe(setup, now, minutes=[minute(102), minute(104), minute(100)])
    assert result["status"] == "watching"  # Old high touched, newest close did not.
    assert observe(setup, now, minutes=[minute(103)] * 3, minute_at=now) is None
    assert observe(setup, now, minutes=[minute(103)] * 3, minute_at=now - timedelta(minutes=4)) is None
    assert oe.load_records(setup[0], "005930", now)[DAY]["status"] == "watching"


def test_unpublished_preliminary_cannot_confirm(setup):
    first = observe(setup, publish=False)
    assert first["status"] == "watching"
    assert not first.get("published_at")
    later = observe(setup, START + timedelta(minutes=2), minutes=[minute(101)] * 3, publish=False)
    assert later["status"] == "watching"
    oe.mark_published(setup[0], [{"code": "005930", "is_preliminary": True,
                                "observed_entry": oe.public_state(later)}], START + timedelta(minutes=2))
    # Publication itself must also precede the entire confirming minute.
    assert observe(setup, START + timedelta(minutes=3), minutes=[minute(101)] * 4)["status"] == "watching"
    assert observe(setup, START + timedelta(minutes=4), minutes=[minute(101)] * 5)["status"] == "confirmed"


@pytest.mark.parametrize("failure", ["missing", "stale", "future", "wrong_day", "wrong_stock", "limited", "support", "veto"])
def test_missing_or_invalid_independent_evidence_never_confirms(setup, failure):
    observe(setup)
    now = START + timedelta(minutes=2)
    item = evidence(now)
    if failure == "missing":
        item = None
    elif failure == "stale":
        item["generated_at"] = START.isoformat().replace("09:02", "08:00")
    elif failure == "future":
        item["generated_at"] = (now + timedelta(seconds=1)).isoformat()
    elif failure == "wrong_day":
        item["signal_date"] = DAY.isoformat()
    elif failure == "wrong_stock":
        item["stock_code"] = "000660"
    elif failure == "limited":
        item["quality"]["state"] = "limited"
    elif failure == "support":
        item["supportive_count"] = 0
    else:
        item["vetoes"] = ["중대 공시"]
    result = observe(setup, now, minutes=[minute(101)] * 3, evidence=item)
    assert result["status"] == ("cancelled" if failure == "veto" else "watching")
    assert "order" not in result
    if failure != "veto":
        assert result["pause_reasons"]


@pytest.mark.parametrize("failure", ["position", "universe", "chase", "guard", "reentry"])
def test_invalidation_cancels_without_same_day_rearming(setup, monkeypatch, failure):
    observe(setup)
    kwargs = {}
    if failure == "position":
        kwargs["available"] = False
    elif failure == "universe":
        kwargs["universe_eligible"] = False
    elif failure == "chase":
        monkeypatch.setattr(qs, "_chase_entry_veto_reason", lambda *a, **k: "overheated")
    elif failure == "guard":
        monkeypatch.setattr(qs, "entry_safety_guard_active", lambda *a: True)
    else:
        monkeypatch.setattr(qs, "_reentry_entry_allowed", lambda *a: False)
    result = observe(setup, START + timedelta(minutes=2), minutes=[minute(101)] * 3, **kwargs)
    assert result["status"] == "cancelled"
    assert observe(setup, START + timedelta(minutes=3), minutes=[minute(101)] * 4) == result


def test_transient_pause_resumes_on_a_new_completed_minute(setup):
    first = observe(setup)
    paused_at = START + timedelta(minutes=1)
    paused = oe.mark_paused(setup[0], "005930", paused_at, "intraday_path_unavailable")
    assert paused["status"] == "watching"
    assert paused["pause_reasons"] == ["intraday_path_unavailable"]

    recovered = observe(
        setup,
        START + timedelta(minutes=2),
        minutes=[minute(100), minute(100), minute(101)],
    )
    assert recovered["status"] == "confirmed"
    assert "pause_reasons" not in recovered
    assert recovered["resumed_at"] == (START + timedelta(minutes=2)).isoformat()
    assert recovered["decision_minute_at"] > first["first_observed_at"]


def test_expiry_and_forward_only_without_historical_backfill(setup):
    assert observe(setup, START - timedelta(days=1)) is None
    observe(setup)
    close = START.replace(hour=15, minute=30)
    assert observe(setup, close) is None
    assert oe.load_records(setup[0], "005930", close)[DAY]["status"] == "expired"
    assert oe.load_records(setup[0], "005930", START + timedelta(days=1))[DAY]["status"] == "expired"
    assert oe.load_records(setup[0], "000660", close) == {}


def test_v1_observation_ledger_remains_readable_after_v2_cutover(setup):
    prior_day = date(2026, 10, 21)
    payload = {
        "candidate_id": f"{oe.LEGACY_POLICY_VERSION}:005930:{prior_day}",
        "policy_version": oe.LEGACY_POLICY_VERSION,
        "status": "watching",
        "first_observed_at": "2026-10-21T09:02:00+09:00",
        "expires_at": "2026-10-21T15:30:00+09:00",
    }
    setup[0].add(QuantSignalObservedEntry(
        stock_code="000660",
        trade_date=prior_day,
        policy_version=oe.LEGACY_POLICY_VERSION,
        status="watching",
        payload=oe._encoded(payload),
        updated_at=datetime(2026, 10, 21, 0, 2),
    ))
    setup[0].flush()

    loaded = oe.load_records(setup[0], "000660", START)
    assert loaded[prior_day]["policy_version"] == oe.LEGACY_POLICY_VERSION
    assert loaded[prior_day]["status"] == "expired"

    legacy_minute = qs.PriceBar(prior_day, 100, 101, 99, 100, 1000, 100000)
    legacy_order = {
        "side": "buy",
        "signal_date": prior_day.isoformat(),
        "signal_at": "2026-10-21T09:05:00+09:00",
        "price": 100,
        "minute_index": 0,
        "minute_signature": oe.minute_signature(legacy_minute),
        "entry_policy_version": oe.LEGACY_POLICY_VERSION,
    }
    legacy_record = {
        "policy_version": oe.LEGACY_POLICY_VERSION,
        "status": "confirmed",
        "order": legacy_order,
        "order_hash": oe._digest(legacy_order),
    }
    replayed = oe.replay_order(legacy_record, [legacy_minute], forming=False)
    assert replayed["execution_model"] == oe.LEGACY_EXECUTION_MODEL


def test_replay_uses_close_and_excludes_pre_entry_stop_and_peak(setup):
    record, minutes = confirmed(setup)
    _, _, bars, indicator = setup
    forming = replace(minutes[-1], open=100, high=130, low=70)
    values = [*bars, forming]
    simulation = qs._simulate(
        values, qs._indicator_rows(values), lifecycle_start_date=DAY,
        forming_bar_date=DAY, intraday_minutes=minutes, observed_entries={DAY: record},
    )
    assert [event["side"] for event in simulation["events"]] == ["buy"]
    assert simulation["position"]["entry_price"] == 101
    assert simulation["position"]["peak_price"] == 101
    assert simulation["events"][0]["signal_at"] == START + timedelta(minutes=2)
    assert simulation["events"][0]["execution_model"] == oe.EXECUTION_MODEL
    # A later minute can sell half; the pre-entry 130 high never sells anything.
    sell_confirmed_at = START + timedelta(minutes=3)
    next_minutes = [*minutes, minute(105, closed_at=sell_confirmed_at)]
    later = qs._simulate(
        [*bars, replace(forming, close=105)], qs._indicator_rows(values),
        lifecycle_start_date=DAY, forming_bar_date=DAY, intraday_minutes=next_minutes,
        observed_entries={DAY: record},
    )
    assert [event["side"] for event in later["events"]] == ["buy", "partial_sell"]
    sell_event = later["events"][-1]
    assert sell_event["sold_percent"] == 50
    assert sell_event["signal_at"] == sell_confirmed_at
    assert sell_event["confirmed_at"] == sell_confirmed_at
    assert sell_event["decision_minute_at"] == sell_confirmed_at
    assert live_order_guard.evaluate_live_order_candidate(
        {**sell_event, "status": "confirmed"},
        now=sell_confirmed_at + timedelta(seconds=30),
    )["eligible"] is True
    # Final-day replay retains the same entry; no reconstructed daily-price buy.
    replay = qs._simulate(values, qs._indicator_rows(values), lifecycle_start_date=DAY,
                          intraday_minutes_by_date={DAY: minutes}, observed_entries={DAY: record})
    assert replay["events"][0]["price"] == simulation["events"][0]["price"]
    assert replay["events"][0]["signal_at"] == simulation["events"][0]["signal_at"]
    assert qs._simulate(values, qs._indicator_rows(values), lifecycle_start_date=DAY)["events"] == []


def test_changed_or_missing_confirmation_evidence_quarantines_replay(setup):
    record, minutes = confirmed(setup)
    with pytest.raises(qs.UnverifiedIntradayPathError):
        oe.replay_order(record, [*minutes[:-1], minute(103)], forming=False)
    with pytest.raises(qs.UnverifiedIntradayPathError):
        oe.replay_order(record, None, forming=False)
    changed = deepcopy(record)
    changed["order"]["price"] = 999
    with pytest.raises(qs.UnverifiedIntradayPathError):
        oe.replay_order(changed, minutes, forming=False)


def test_canonical_builder_captures_then_confirms_and_detail_only_reads(setup):
    db, stock, bars, _ = setup
    daily = _daily_rows_from_bars(stock.code, bars)

    def build(now, count, publisher, loader=None):
        rows = [{
            "trade_date": DAY.strftime("%Y%m%d"), "trade_time": f"090{i + 1}00",
            "open": 101, "high": 101, "low": 101, "price": 101, "volume": 1000,
        } for i in range(count)]
        quote = dict(trade_date=DAY, trade_date_verified=True, quote_source="kis_rest",
                     market_venue="KRX", market_division="J", price=101, open=101,
                     high=101, low=101, volume=count * 1000, observed_at=now)
        return qs._market_stock_payload_with_intraday_path(
            db, stock, daily, bars, quote, {}, None, now,
            loader or (lambda _: (rows, now)), None,
            verified_paths={}, lifecycle_start_date=qs.REGULAR_FORWARD_START, observe_entry=publisher,
            entry_universe_eligible=lambda _: True, observation_universe_rank=3,
            fresh_entry_evidence=lambda: evidence(now),
        )

    build(START, 1, False)
    assert not oe.load_records(db, stock.code, START)
    capture = build(START, 1, True)
    assert capture["current"]["observed_entry"]["status"] == "watching"
    assert capture["events"] == []
    qs.save_market_quant_signal_snapshot(
        db, {"status": "ready", "as_of": START, "items": [
            qs._market_preliminary_signal_item(stock, 3, capture, START),
        ]}, universe_limit=150, limit=0, recent_days=30, generated_at=START,
    )
    assert oe.load_records(db, stock.code, START)[DAY].get("published_at") == START.isoformat()
    paused = build(
        START + timedelta(minutes=1),
        1,
        True,
        loader=lambda _: ([], START + timedelta(minutes=1)),
    )
    assert paused["current"]["observed_entry"]["pause_reasons"] == [
        "intraday_path_unavailable"
    ]
    assert paused["current"]["label"] == "예비 포착 · 데이터 복구 대기"
    detail = build(START + timedelta(minutes=2), 3, False)
    assert detail["current"]["observed_entry"]["status"] == "watching"
    result = build(START + timedelta(minutes=2), 3, True)
    assert result["current"]["position_open"] is True, result["current"]
    assert result["events"][0]["entry_policy_version"] == oe.POLICY_VERSION
    assert "_observed_entry_context" not in result
    public = public_quant_signal_payload(result)
    assert public["current"]["observed_entry"]["confirmed_at"]
    assert "order" not in public["current"]["observed_entry"]
    assert "evidence" not in public["current"]["observed_entry"]


def test_two_distinct_pushes_dedupe_watchlist_and_reject_stale_unverified(setup, monkeypatch):
    db, stock, _, _ = setup
    record, _ = confirmed(setup)
    now = START + timedelta(minutes=2)
    preliminary = dict(code=stock.code, name=stock.name, side="buy",
                       signal_date=DAY.isoformat(), status="preliminary",
                       observed_entry={**oe.public_state(record), "status": "watching"})
    buy = dict(code=stock.code, name=stock.name, side="buy", event_side="buy",
               execution_date=DAY.isoformat(), status="confirmed",
               intraday_execution_verified=True, execution_model=oe.EXECUTION_MODEL,
               entry_policy_version=oe.POLICY_VERSION, confirmed_at=now.isoformat())
    snapshot = dict(status="ready", execution_model=qs.EXECUTION_MODEL,
                    snapshot_generated_at=now.isoformat(), items=[preliminary, buy])
    monkeypatch.setattr(web_push, "load_external_market_quant_signal_feed", lambda *a, **k: snapshot)
    runtime = web_push.WebPushRuntime(_settings())
    candidates = runtime._market_ai_signal_candidates(db, now)
    assert len(candidates) == 2
    assert "예비 포착" in candidates[0].title and "매수 확정" in candidates[1].title
    assert candidates[0].event_key != candidates[1].event_key
    watch = WatchlistItem(code=stock.code, name=stock.name, share_id="tester")
    monkeypatch.setattr(web_push, "load_quant_signal_payload",
                        lambda *a, **k: pytest.fail("observed watchlist alert must use canonical publication"))
    from_watchlist = runtime._ai_signal_candidates(db, {"tester": [watch]}, now)["tester"]
    assert [item.event_key for item in from_watchlist] == [item.event_key for item in candidates]
    assert all(item.kind == "ai_signal" for item in from_watchlist)
    payload = {"current": {
        "action": "entry_watch", "live_observation": True, "as_of": now,
        "observed_entry": preliminary["observed_entry"], "lifecycle": {},
    }}
    assert web_push._ai_signal_candidate(watch, payload, now).event_key == candidates[0].event_key
    payload["current"].update(action="entered", lifecycle={"latest_transition": {
        "side": "buy", "transition_date": DAY.isoformat(), "entry_policy_version": oe.POLICY_VERSION,
        "confirmed_at": now.isoformat(), "intraday_execution_verified": True,
    }}, observed_entry=oe.public_state(record))
    assert web_push._ai_signal_candidate(watch, payload, now).event_key == candidates[1].event_key
    payload["current"]["lifecycle"]["latest_transition"]["intraday_execution_verified"] = False
    assert web_push._ai_signal_candidate(watch, payload, now) is None
    payload["current"].update(action="partial_exit_pending", as_of=now + timedelta(minutes=4))
    exit_alert = web_push._ai_signal_candidate(watch, payload, now + timedelta(minutes=4))
    assert ":partial_exit_pending:" in exit_alert.event_key
    buy["execution_replay_state"] = "unverified"
    assert len(runtime._market_ai_signal_candidates(db, now)) == 1
    buy.pop("execution_replay_state")
    buy["entry_policy_version"] = None
    assert len(runtime._market_ai_signal_candidates(db, now)) == 1
    buy["entry_policy_version"] = oe.POLICY_VERSION
    snapshot["snapshot_generated_at"] = (now + timedelta(minutes=4)).isoformat()
    assert len(runtime._market_ai_signal_candidates(db, now + timedelta(minutes=4))) == 1
    assert candidates[1].expires_at == now + timedelta(seconds=180)


def test_push_delivery_dedupes_two_paths_and_rechecks_expiry(setup, monkeypatch):
    db = setup[0]
    clock = [START]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0].astimezone(tz) if tz else clock[0].replace(tzinfo=None)

    monkeypatch.setattr(web_push, "datetime", Clock)
    sent = []
    monkeypatch.setattr(web_push, "webpush", lambda **kwargs: sent.append(kwargs))
    subscription = PushSubscription(share_id="tester", endpoint="https://push.example/observed",
                                    p256dh="p" * 64, auth="a" * 24)
    db.add(subscription)
    db.commit()
    runtime = web_push.WebPushRuntime(_settings())
    preliminary = web_push.NotificationCandidate(
        event_key=f"market-ai-preliminary:005930:buy:{DAY}", kind="market_ai_signal",
        title="예비 포착", body="완료 분봉 조건 대기", url="/dashboard/005930", tag="signal-005930",
    )
    buy = replace(preliminary, event_key=f"market-ai-signal:005930:buy:{DAY}",
                  title="매수 확정", occurred_at=START, expires_at=START + timedelta(seconds=180))
    assert runtime._send(db, subscription, preliminary)
    assert not runtime._send(db, subscription, replace(preliminary, kind="ai_signal"))
    assert runtime._send(db, subscription, buy)
    assert not runtime._send(db, subscription, replace(buy, kind="ai_signal"))
    assert len(sent) == 2
    clock[0] += timedelta(seconds=181)
    assert not runtime._send(db, subscription, replace(buy, event_key=f"market-ai-signal:000660:buy:{DAY}"))
    assert len(sent) == 2


def test_intraday_disclosure_includes_today_and_excludes_future(setup):
    db = setup[0]
    now = START.astimezone(timezone.utc).replace(tzinfo=None)
    db.add(IngestionRun(source="disclosure", dataset="dart_api", status="success",
                        started_at=now - timedelta(minutes=2), finished_at=now, rows_loaded=1))
    for index, at in enumerate((now - timedelta(minutes=1), now + timedelta(minutes=1))):
        db.add(DisclosureItem(source="dart_api", external_id=f"observed-{index}",
                             disclosure_category="major", company_name="삼성전자",
                             stock_code="005930", report_name="유상증자결정", published_at=at))
    db.commit()
    _, _, old_vetoes = _disclosure_evidence(db, stock_code="005930", signal_date=DAY - timedelta(days=1),
                                          generated_at=START)
    _, _, live_vetoes = _disclosure_evidence(db, stock_code="005930", signal_date=DAY - timedelta(days=1),
                                           generated_at=START, observed_through=now)
    assert old_vetoes == []
    assert len(live_vetoes) == 1


def test_observed_candidate_public_copy_and_ui_contract():
    payload = {"current": {"observed_entry": {"status": "watching"}, "lifecycle": {}},
               "_observed_entry_context": {"available": True}}
    public = public_quant_signal_payload(payload)
    assert "완료된 정규장 1분봉" in public["current"]["next_confirmation"]
    assert "_observed_entry_context" not in public
    source = Path("app/static/dashboard/app.js").read_text()
    assert 'value: "포착 후 완료 1분봉"' in source
    assert '"same-session-observed-entry-v2"].includes(current.observed_entry?.policy_version)' in source
