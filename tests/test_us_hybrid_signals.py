from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import math

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import MarketQuantSignalSnapshot
from app.services import us_hybrid_signals as hybrid

OPEN = datetime(2026, 10, 13, 13, 30, tzinfo=timezone.utc)


def feed():
    setups = [{"code": "AAPL" if index == 0 else f"X{index}", "name": "Apple" if index == 0 else f"Name{index}",
               "market": "NASDAQ", "market_cap_rank": index + 1, "signal_date": "2026-10-12",
               "eligible": index == 0, "daily_watch": index == 0,
               "reference_close": 100.0, "atr": 2.0,
               "average_daily_volume": 1_000_000.0, "close_exit": False}
              for index in range(100)]
    reasons = [{"key": key, "state": "positive", "available": True, "as_of": "2026-10-12"}
               for key in ("trend_20d", "trend_60d", "flow")]
    return {"status": "ready", "data_state": "ready", "new_entries_allowed": True,
            "strategy_version": "position-lifecycle-us-v2-rc1", "snapshot_id": "daily-v2",
            "snapshot_checksum": "verified", "universe_as_of": "2026-10-12",
            "universe_count": 100, "hybrid_setups": setups,
            "public_member_signals": [{"code": item["code"], "public_reasons": reasons} for item in setups],
            "items": [{"code": "OLD", "current": {"position_open": True}, "events": []}],
            "performance_summary": {"old": "unchanged"}}


def chart(prices=(100, 100.1), *, start=OPEN, volumes=None):
    volume_values = list(volumes or ([10000] * len(prices)))
    return {"meta": {"symbol": "AAPL", "currency": "USD", "instrumentType": "EQUITY"},
            "timestamp": [int((start + timedelta(minutes=index)).timestamp()) for index in range(len(prices))],
            "indicators": {"quote": [{"open": list(prices), "high": [value + .1 for value in prices],
                                      "low": [value - .1 for value in prices], "close": list(prices),
                                      "volume": volume_values}]}}


def initial():
    daily = feed()
    now = OPEN - timedelta(minutes=5)
    state = hybrid.new_us_hybrid_state(daily, now)
    return hybrid.advance_us_hybrid_state(state, daily, {}, now)


def entered():
    captured = hybrid.advance_us_hybrid_state(
        initial(), feed(), {"AAPL": chart((100,))},
        OPEN + timedelta(minutes=1, seconds=5),
    )
    return hybrid.advance_us_hybrid_state(
        captured, feed(), {"AAPL": chart()},
        OPEN + timedelta(minutes=2, seconds=5),
    )


def save(db, state):
    state = json.loads(hybrid._json(state))
    state["checksum"] = hybrid._digest(state)
    db.add(MarketQuantSignalSnapshot(cache_key=hybrid.US_HYBRID_KEY, payload=hybrid._json(state), generated_at=OPEN.replace(tzinfo=None)))
    db.commit()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_hybrid_two_fresh_minutes_enter_once_and_restart_is_idempotent():
    candidate = hybrid.advance_us_hybrid_state(
        initial(), feed(), {"AAPL": chart((100,), volumes=(2000,))},
        OPEN + timedelta(minutes=1, seconds=5),
    )
    assert candidate["events"] == []
    assert candidate["entry_candidates"]["AAPL"]["status"] == "watching"
    assert candidate["entry_candidates"]["AAPL"]["volume_participation"]["ratio"] >= .75
    state = hybrid.advance_us_hybrid_state(
        candidate, feed(), {"AAPL": chart((100, 100.1), volumes=(2000, 4000))},
        OPEN + timedelta(minutes=2, seconds=5),
    )
    assert len(state["events"]) == 1
    assert state["positions"]["AAPL"]["entry_price"] == 100.1
    restarted = json.loads(hybrid._json(state))
    result = hybrid.advance_us_hybrid_state(restarted, feed(), {"AAPL": chart()}, OPEN + timedelta(minutes=2, seconds=30))
    assert result["events"] == state["events"]


def test_hybrid_candidate_waits_for_h1_volume_and_survives_transient_minute_failure():
    candidate = hybrid.advance_us_hybrid_state(
        initial(), feed(), {"AAPL": chart((100,), volumes=(2000,))},
        OPEN + timedelta(minutes=1, seconds=5),
    )
    below_h1 = hybrid.advance_us_hybrid_state(
        candidate, feed(), {"AAPL": chart((100, 100.1), volumes=(2000, 2500))},
        OPEN + timedelta(minutes=2, seconds=5),
    )
    assert below_h1["events"] == []
    assert below_h1["entry_candidates"]["AAPL"]["status"] == "watching"

    broken = chart((100, 100.1, 100.2), volumes=(2000, 2500, 4000))
    broken["indicators"]["quote"][0]["close"][-1] = None
    paused = hybrid.advance_us_hybrid_state(
        below_h1, feed(), {"AAPL": broken},
        OPEN + timedelta(minutes=3, seconds=5),
    )
    assert paused["entry_candidates"]["AAPL"]["status"] == "watching"
    assert paused["entry_candidates"]["AAPL"]["pause_reasons"] == [
        "completed_minute_missing"
    ]

    resumed = hybrid.advance_us_hybrid_state(
        paused,
        feed(),
        {"AAPL": chart((100, 100.1, 100.2, 100.3), volumes=(2000, 2500, 4000, 4000))},
        OPEN + timedelta(minutes=4, seconds=5),
    )
    assert resumed["events"][-1]["side"] == "buy"
    assert resumed["events"][-1]["entry_policy_version"] == hybrid.US_HYBRID_EXECUTION_MODEL


@pytest.mark.parametrize("prices,expected_side,remaining", [
    ((100, 100.1, 103.11), "partial_sell", .5),
    ((100, 100.1, 106), "sell", 0),
    ((100, 100.1, 95), "sell", 0),
])
def test_hybrid_profit_and_stop_use_observed_prices_not_ideal_threshold(prices, expected_side, remaining):
    state = hybrid.advance_us_hybrid_state(entered(), feed(), {"AAPL": chart(prices)}, OPEN + timedelta(minutes=3, seconds=5))
    event = state["events"][-1]
    assert event["side"] == expected_side
    assert event["price"] == prices[-1]
    assert state["positions"]["AAPL"]["remaining"] == remaining
    if prices[-1] == 95:
        assert event["return_rate"] < -4  # Gaps are not clipped to the stop.


def test_hybrid_exact_decimal_exit_boundaries_and_adjacent_quotes():
    entries = (100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 125, 150, 200, 333, 500, 1000)
    for entry in entries:
        for multiple, expected in (("0.96", "sell"), ("1.03", "partial_sell"), ("1.05", "sell")):
            boundary = float(Decimal(str(entry)) * Decimal(multiple))
            for direction in (-1, 0, 1):
                quote = boundary if direction == 0 else math.nextafter(boundary, math.inf * direction)
                state = entered()
                state["positions"]["AAPL"]["entry_price"] = entry
                original = deepcopy(state)
                result = hybrid.advance_us_hybrid_state(
                    state, feed(), {"AAPL": chart((entry, entry, quote))},
                    OPEN + timedelta(minutes=3, seconds=5),
                )
                actual = result["events"][-1]["side"] if len(result["events"]) > 1 else None
                expected_side = expected
                if multiple == "0.96" and direction == 1:
                    expected_side = None
                elif multiple == "1.03" and direction == -1:
                    expected_side = None
                elif multiple == "1.05" and direction == -1:
                    expected_side = "partial_sell"
                assert actual == expected_side, (entry, multiple, direction, quote)
                assert state == original
                if actual:
                    assert result["events"][-1]["price"] == quote
                replay = hybrid.advance_us_hybrid_state(
                    result, feed(), {"AAPL": chart((entry, entry, quote))},
                    OPEN + timedelta(minutes=3, seconds=10),
                )
                assert replay["events"] == result["events"]


def test_hybrid_partial_breakeven_boundary_does_not_exit_early():
    for quote, expected in ((math.nextafter(333.0, math.inf), None), (333.0, "sell"),
                            (math.nextafter(333.0, -math.inf), "sell")):
        state = entered()
        state["positions"]["AAPL"].update(entry_price=333.0, remaining=.5, realized_return=1.5)
        result = hybrid.advance_us_hybrid_state(
            state, feed(), {"AAPL": chart((333, 333, quote))}, OPEN + timedelta(minutes=3, seconds=5),
        )
        assert (result["events"][-1]["side"] if len(result["events"]) > 1 else None) == expected
        if expected:
            assert result["events"][-1]["sell_fraction_original"] == .5
            assert result["events"][-1]["return_rate"] == pytest.approx(1.5)


def test_hybrid_partial_then_remaining_exit_weighted_return_and_no_same_day_reentry():
    state = entered()
    for minute, prices in [(3, (100, 100.1, 103.11)), (4, (100, 100.1, 103.11, 105.2))]:
        state = hybrid.advance_us_hybrid_state(state, feed(), {"AAPL": chart(prices)}, OPEN + timedelta(minutes=minute, seconds=5))
    assert [item["side"] for item in state["events"]] == ["buy", "partial_sell", "sell"]
    expected = ((103.11 / 100.1 - 1) + (105.2 / 100.1 - 1)) * 50
    assert state["events"][-1]["return_rate"] == pytest.approx(expected)
    state = hybrid.advance_us_hybrid_state(state, feed(), {"AAPL": chart((100, 100.1, 103.11, 105.2, 100.1))}, OPEN + timedelta(minutes=5, seconds=5))
    assert len(state["events"]) == 3


def test_hybrid_profit_after_entry_does_not_read_same_minute_high():
    captured = hybrid.advance_us_hybrid_state(
        initial(), feed(), {"AAPL": chart((100,))},
        OPEN + timedelta(minutes=1, seconds=5),
    )
    raw = chart()
    raw["indicators"]["quote"][0]["high"][-1] = 200
    state = hybrid.advance_us_hybrid_state(
        captured, feed(), {"AAPL": raw}, OPEN + timedelta(minutes=2, seconds=5)
    )
    assert len(state["events"]) == 1 and state["events"][0]["side"] == "buy"


@pytest.mark.parametrize("mutation", ["old", "forming", "missing", "reverse", "duplicate", "wrong_code", "currency", "delayed", "split", "geometry", "nan", "future"])
def test_hybrid_bad_minutes_never_confirm(mutation):
    raw = chart()
    now = OPEN + timedelta(minutes=2, seconds=5)
    if mutation == "old":
        now += timedelta(minutes=10)
    elif mutation == "forming":
        now = OPEN + timedelta(minutes=1, seconds=30)
    elif mutation == "missing":
        raw["indicators"]["quote"][0]["volume"][-1] = None
    elif mutation == "reverse":
        raw["timestamp"].reverse()
    elif mutation == "duplicate":
        raw["timestamp"][-1] = raw["timestamp"][0]
    elif mutation == "wrong_code":
        raw["meta"]["symbol"] = "MSFT"
    elif mutation == "currency":
        raw["meta"]["currency"] = "KRW"
    elif mutation == "delayed":
        raw["meta"]["exchangeDataDelayedBy"] = 15
    elif mutation == "split":
        raw["events"] = {"splits": {"x": {"date": int(OPEN.timestamp())}}}
    elif mutation == "geometry":
        raw["indicators"]["quote"][0]["high"][-1] = 90
    elif mutation == "nan":
        raw["indicators"]["quote"][0]["close"][-1] = float("nan")
    elif mutation == "future":
        raw["timestamp"][-1] += 600
    state = hybrid.advance_us_hybrid_state(initial(), feed(), {"AAPL": raw}, now)
    assert not state["events"]


@pytest.mark.parametrize("now", [OPEN - timedelta(seconds=1), OPEN + timedelta(hours=6, minutes=30),
                                datetime(2026, 10, 17, 15, tzinfo=timezone.utc),
                                datetime(2026, 11, 26, 15, tzinfo=timezone.utc)])
def test_hybrid_regular_calendar_only(now):
    state = hybrid.advance_us_hybrid_state(initial(), feed(), {"AAPL": chart()}, now)
    assert not state["events"]


def test_hybrid_early_close_and_dst_are_exchange_calendared():
    from app.services.us_market_calendar import us_market_session
    early = us_market_session(datetime(2026, 11, 27).date())
    assert early.open_at.hour == 14
    assert early.close_at.hour == 18
    assert hybrid.verified_minutes(chart(), "AAPL", early.close_at)[1] == "market_closed"


def test_hybrid_late_start_gap_and_stale_daily_setup_block_entry():
    daily = feed()
    now = OPEN + timedelta(minutes=2, seconds=5)
    late = hybrid.new_us_hybrid_state(daily, now)
    assert not hybrid.advance_us_hybrid_state(late, daily, {"AAPL": chart()}, now)["events"]
    assert not hybrid.advance_us_hybrid_state(initial(), daily, {"AAPL": chart((105, 105))}, now)["events"]
    daily["universe_as_of"] = "2026-10-09"
    assert not hybrid.advance_us_hybrid_state(initial(), daily, {"AAPL": chart()}, now)["events"]


def test_hybrid_dropped_or_stale_daily_feed_does_not_disable_position_stops():
    daily = feed()
    daily["new_entries_allowed"] = False
    state = hybrid.advance_us_hybrid_state(entered(), daily, {"AAPL": chart((100, 100.1, 90))}, OPEN + timedelta(minutes=3, seconds=5))
    assert state["events"][-1]["side"] == "sell"


def test_hybrid_freezes_old_publications_and_separates_forward_performance(db):
    old = feed()
    state = entered()
    save(db, state)
    projected = hybrid.project_us_hybrid_feed(db, old, now=OPEN + timedelta(minutes=2, seconds=10))
    assert old == feed()
    assert projected["rollout_mode"] == "hybrid_forward"
    assert projected["execution_enabled"] is False
    assert projected["items"][0]["current"]["action"] == "entered"
    assert projected["preliminary_history"][0]["history_frozen"] is True
    assert projected["preliminary_history"][0]["current"]["position_open"] is False
    assert projected["performance_summary"]["windows"]["7d"]["completed_trades"] == 0
    assert projected["legacy_performance_summary"] == old["performance_summary"]


def test_hybrid_ledger_tampering_is_not_reinitialized(db):
    save(db, entered())
    row = db.get(MarketQuantSignalSnapshot, hybrid.US_HYBRID_KEY)
    data = json.loads(row.payload)
    data["positions"]["AAPL"]["entry_price"] = 1
    row.payload = hybrid._json(data)
    db.commit()
    with pytest.raises(ValueError, match="integrity"):
        hybrid.read_us_hybrid_state(db)


def test_hybrid_notifications_are_fresh_confirmed_scoped_and_expire(db):
    from app.services.web_push import WebPushRuntime, notification_history_is_valid, notification_history_signal_context
    state = entered()
    save(db, state)
    now = OPEN + timedelta(minutes=2, seconds=20)
    candidates = WebPushRuntime()._us_market_ai_signal_candidates(db, now)
    assert len(candidates) == 1
    item = candidates[0]
    assert item.market_scope == "us" and item.stock_codes == ("AAPL",)
    assert "실제 계좌 주문이 아닌" in item.body
    assert notification_history_is_valid(item.kind, item.event_key, now)
    assert notification_history_signal_context(item.kind, item.event_key)["phase"] == "confirmed"
    assert not WebPushRuntime()._us_market_ai_signal_candidates(db, now + timedelta(minutes=4))


def test_hybrid_public_redaction_keeps_intraday_contract_without_daily_replay_copy(db):
    from app.services.public_signal import public_market_signal_payload, public_recommendation_signal_payload
    save(db, entered())
    projected = hybrid.project_us_hybrid_feed(db, feed(), now=OPEN + timedelta(minutes=2, seconds=10))
    public = public_market_signal_payload(projected)
    assert public["items"][0]["current"]["action"] == "entered"
    assert "완료 1분봉" in public["items"][0]["reason"]
    serialized = hybrid._json(public["items"])
    assert "minute_evidence" not in serialized and "entry_price" not in serialized
    assert "다음 정규장 시가를 기준으로" not in serialized
    recommendation = public_recommendation_signal_payload(projected)
    assert "완료 1분봉" in recommendation["methodology"][0]
    for payload in (public, recommendation):
        assert all(token in payload["methodology"][0] for token in ("수정 OHLC", "SPY·QQQ", "거래대금", "완료 1분봉"))
        assert "다음 정규장 시가를 통과한 모델 재현" not in payload["methodology"][0]


@pytest.mark.parametrize("stage", ["preparing", "pending", "entered", "exited"])
def test_hybrid_counts_never_inherit_legacy_daily_positions(db, stage):
    from app.services.us_market import build_us_quant_signals
    daily = feed()
    daily.update({"confirmed_count": 99, "preliminary_count": 98, "entry_pending_count": 97})
    state = initial() if stage == "pending" else entered()
    current = OPEN + timedelta(minutes=2, seconds=10)
    if stage == "exited":
        current = OPEN + timedelta(minutes=3, seconds=10)
        state = hybrid.advance_us_hybrid_state(state, daily, {"AAPL": chart((100, 100.1, 106))}, current)
    if stage != "preparing":
        save(db, state)
    projected = hybrid.project_us_hybrid_feed(db, daily, now=current)
    for payload in (projected, build_us_quant_signals(limit=1, feed=projected)):
        assert payload["entry_pending_count"] == int(stage == "pending")
        assert payload["preliminary_count"] == int(stage == "pending")
        assert payload["confirmed_count"] == int(stage == "entered")


def test_hybrid_raw_price_basis_uses_unadjusted_notional():
    from types import SimpleNamespace
    setup = hybrid.build_close_setup({"code":"AAPL", "name":"Apple", "market":"NASDAQ"},
        {"action":"entry_pending", "signal_date":"2026-10-12", "technical":{"atr":1.8}},
        SimpleNamespace(volume=1000, trading_value=100000, close=90))
    assert setup["reference_close"] == 100
    assert setup["atr"] == 2


def test_hybrid_minute_transport_explicitly_requests_split_evidence(monkeypatch):
    from types import SimpleNamespace
    from app.services import us_market
    raw = chart()
    raw["events"] = {"splits": {"today": {"date": int(OPEN.timestamp())}}}
    requests = []
    def get(url, **kwargs):
        requests.append(kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"chart": {"result": [raw]}})
    monkeypatch.setattr(us_market.requests, "get", get)
    result = us_market._fetch_yahoo_chart_once("AAPL", us_market.YAHOO_CHART_URL, "1d", "1m", False)
    assert requests[0]["params"]["events"] == "splits"
    assert requests[0]["params"]["includePrePost"] == "false"
    assert hybrid.verified_minutes(result, "AAPL", OPEN + timedelta(minutes=2, seconds=5)) == ([], "corporate_action_review")


def test_hybrid_ignores_seconds_stamped_forming_tail_not_finished_misalignment():
    raw = chart((100, 100.1, 100.2))
    raw["timestamp"][-1] = int((OPEN + timedelta(minutes=1, seconds=38)).timestamp())
    raw["indicators"]["quote"][0]["volume"][-1] = 0
    now = OPEN + timedelta(minutes=2, seconds=5)
    points, quality = hybrid.verified_minutes(raw, "AAPL", now)
    assert quality == "fresh" and len(points) == 2
    captured = hybrid.advance_us_hybrid_state(
        initial(), feed(), {"AAPL": chart((100,))},
        OPEN + timedelta(minutes=1, seconds=5),
    )
    state = hybrid.advance_us_hybrid_state(captured, feed(), {"AAPL": raw}, now)
    assert state["positions"]["AAPL"]["entry_price"] == 100.1
    malformed = chart()
    malformed["timestamp"][0] += 1
    assert hybrid.verified_minutes(malformed, "AAPL", now) == ([], "minute_order_invalid")


def test_hybrid_collector_persists_without_provider_calls_outside_session(db, monkeypatch):
    monkeypatch.setattr("app.services.us_position_lifecycle.load_us_position_lifecycle_snapshot", lambda *args, **kwargs: feed())
    def forbidden(code):
        raise AssertionError("provider must not run before regular session")
    result = hybrid.refresh_us_hybrid_signals(db, now=OPEN - timedelta(minutes=1), loader=forbidden)
    assert result["state"] == "ready"
    first = hybrid.read_us_hybrid_state(db)
    result = hybrid.refresh_us_hybrid_signals(
        db, now=OPEN + timedelta(minutes=1, seconds=5),
        loader=lambda code: chart((100,)),
    )
    assert result["state"] == "ready"
    result = hybrid.refresh_us_hybrid_signals(
        db, now=OPEN + timedelta(minutes=2, seconds=5), loader=lambda code: chart()
    )
    assert result["state"] == "ready"
    second = hybrid.read_us_hybrid_state(db)
    assert len(second["events"]) == 1
    assert second["legacy"] == first["legacy"]
    hybrid.refresh_us_hybrid_signals(db, now=OPEN + timedelta(minutes=2, seconds=30), loader=lambda code: chart())
    assert len(hybrid.read_us_hybrid_state(db)["events"]) == 1


def test_hybrid_collector_compare_and_swap_never_overwrites_competing_publication(db, monkeypatch):
    monkeypatch.setattr("app.services.us_position_lifecycle.load_us_position_lifecycle_snapshot", lambda *args, **kwargs: feed())
    save(db, initial())
    def competing_publication(code):
        with Session(db.get_bind()) as competitor:
            state = hybrid.read_us_hybrid_state(competitor)
            state["revision"] = 999
            state["checksum"] = hybrid._digest(state)
            row = competitor.get(MarketQuantSignalSnapshot, hybrid.US_HYBRID_KEY)
            row.payload = hybrid._json(state)
            competitor.commit()
        return chart()
    # Use a synchronous executor so the in-memory SQLite database stays on its
    # owning connection; it models a second publisher racing after the read.
    from concurrent.futures import Future
    class InlineExecutor:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def submit(self, call, *args):
            result = Future()
            result.set_result(call(*args))
            return result
    monkeypatch.setattr(hybrid, "ThreadPoolExecutor", InlineExecutor)
    result = hybrid.refresh_us_hybrid_signals(db, now=OPEN + timedelta(minutes=2, seconds=5), loader=competing_publication)
    assert result["state"] == "concurrent_publication"
    assert hybrid.read_us_hybrid_state(db)["revision"] == 999


def test_hybrid_current_api_uses_durable_intraday_ledger(db, monkeypatch):
    from fastapi import BackgroundTasks, Response
    from starlette.requests import Request
    from app import main
    save(db, entered())
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return OPEN + timedelta(minutes=2, seconds=10)
    monkeypatch.setattr(main, "datetime", Clock)
    monkeypatch.setattr(main, "load_us_position_lifecycle_snapshot", lambda *args, **kwargs: feed())
    monkeypatch.setattr(main, "_enforce_rate_limit", lambda *args, **kwargs: None)
    result = main.us_market_quant_signals(Request({"type":"http", "headers":[]}), BackgroundTasks(), Response(),
                                          limit=20, recent_days=30, refresh=False, db=db)
    assert result["strategy_version"] == hybrid.US_HYBRID_VERSION
    assert result["items"][0]["current"]["action"] == "entered"
    assert result["items"][0]["current"]["live_observation"] is True


def test_hybrid_watchlist_and_market_notifications_share_one_dedupe_key(db):
    from types import SimpleNamespace
    from app.services.web_push import WebPushRuntime
    save(db, entered())
    now = OPEN + timedelta(minutes=2, seconds=10)
    projected = hybrid.project_us_hybrid_feed(db, feed(), now=now)
    watch = WebPushRuntime._us_watchlist_signal_candidates({"user":[SimpleNamespace(code="AAPL", name="Apple")]}, projected, now)
    market = WebPushRuntime()._us_market_ai_signal_candidates(db, now)
    assert watch["user"][0].event_key == market[0].event_key
    assert watch["user"][0].market_scope == "us"
    assert WebPushRuntime._us_watchlist_signal_candidates({"user":[SimpleNamespace(code="OTHER", name="Other")]}, projected, now) == {"user":[]}


def test_hybrid_stale_collector_blocks_readiness_but_does_not_hide_open_ledger(db):
    from app.services.public_signal import public_market_signal_payload
    save(db, entered())
    projected = hybrid.project_us_hybrid_feed(db, feed(), now=OPEN + timedelta(minutes=10))
    assert projected["collector_fresh"] is False
    assert projected["new_entries_allowed"] is False
    public = public_market_signal_payload(projected)
    assert public["items"][0]["current"]["position_open"] is True
    assert public["items"][0]["current"]["live_observation"] is False


def test_hybrid_latest_invalid_minute_cannot_reuse_older_fresh_confirmation():
    raw = chart((100, 100.1, 100.2))
    raw["indicators"]["quote"][0]["close"][-1] = None
    state = hybrid.advance_us_hybrid_state(initial(), feed(), {"AAPL": raw}, OPEN + timedelta(minutes=3, seconds=5))
    assert not state["events"]


def test_hybrid_ui_uses_verified_minute_return_and_expires_without_tick_substitution():
    import re
    import subprocess
    from pathlib import Path
    source = Path("app/static/dashboard/app.js").read_text()
    normalization = source.split("function marketAiSignalItems(", 1)[1].split("function ", 1)[0]
    assert "rollout_mode: item.rollout_mode || payload.rollout_mode" in normalization
    assert "quote_state: item.quote_state" in normalization
    function = re.search(r"function aiSignalItemWithLiveOverlay\(.*?\n\}", source, re.S).group(0)
    script = """
    const toNumber = value => value == null ? null : Number(value);
    const isCurrentAiSignalHolding = item => item.current.position_open;
    const item = {rollout_mode:'hybrid_forward', quote_state:'fresh', current:{
      position_open:true, as_of:'2026-10-13T13:31:00Z', price:103, return_rate:2.9, live_observation:true}};
    """ + function + """
    const fresh = aiSignalItemWithLiveOverlay(item, Date.parse('2026-10-13T13:32:10Z'));
    const old = aiSignalItemWithLiveOverlay(item, Date.parse('2026-10-13T13:35:10Z'));
    if (fresh.display_return_rate !== 2.9 || fresh.live_freshness_state !== 'recent') throw Error('fresh');
    if (old.display_return_rate !== null || !old.live_return_pending) throw Error('stale');
    """
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


def test_hybrid_partial_and_terminal_projection_keep_original_weight_returns(db):
    from app.services.public_signal import public_market_signal_payload
    state = hybrid.advance_us_hybrid_state(entered(), feed(), {"AAPL": chart((100, 100.1, 103.11))}, OPEN + timedelta(minutes=3, seconds=5))
    save(db, state)
    public = public_market_signal_payload(hybrid.project_us_hybrid_feed(db, feed(), now=OPEN + timedelta(minutes=3, seconds=10)))
    item = public["items"][0]
    assert item["event_side"] == "partial_sell"
    assert item["current"]["model_exposure_percent"] == 50
    assert item["return_rate"] == pytest.approx((103.11 / 100.1 - 1) * 100)
    assert item["execution_date"] == "2026-10-13"


def test_hybrid_send_rechecks_age_at_delivery_not_scan_start(monkeypatch):
    from app.services import web_push
    event = entered()["events"][0]
    candidate = web_push._us_hybrid_candidate(event)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return OPEN + timedelta(minutes=6)
    monkeypatch.setattr(web_push, "datetime", Clock)
    assert web_push.WebPushRuntime()._send(None, None, candidate) is False
