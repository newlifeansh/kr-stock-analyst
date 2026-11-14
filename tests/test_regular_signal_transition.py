from copy import deepcopy
from datetime import date, datetime, timedelta
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import DailyPrice, IngestionRun, MarketQuantSignalSnapshot, QuantSignalEvidenceSnapshot, QuantSignalIntradayPathSnapshot, QuantSignalObservedEntry, QuantSignalTransitionBaseline, StockMaster
from app.services import regular_signal_transition as transition
from app.services import quant_signals as qs
from app.services.regular_session_prices import UnverifiedRegularSessionPrice, store_regular_session_evidence, regular_session_evidence
from tests.test_regular_session_prices import minute_rows


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def history(code="005930"):
    return [DailyPrice(code=code, trade_date=date(2026, 10, 12) - timedelta(days=349-i),
                      open=100, high=101, low=99, close=100, volume=1000,
                      trading_value=101_000_000_000, market_cap=100_000_000_000) for i in range(350)]


def test_forward_baseline_is_immutable_and_detects_tampering(db):
    rows = history()
    original = transition.frozen_legacy_price_rows(db, "005930", rows)
    rows[-1].close = 105
    assert transition.frozen_legacy_price_rows(db, "005930", rows)[-1].close == original[-1].close
    record = db.scalar(select(QuantSignalTransitionBaseline))
    record.payload += " "
    db.flush()
    with pytest.raises(UnverifiedRegularSessionPrice, match="무결성"):
        transition.frozen_legacy_price_rows(db, "005930", rows)


def test_forward_baseline_concurrent_insert_keeps_first_verified_value(db, monkeypatch):
    key = "krx-regular-forward-v1:prices:005930"
    first = {"source": "first"}
    assert transition._freeze(db, key, first) == first
    original_load = transition._load
    reads = 0

    def miss_before_concurrent_insert(session, lookup_key):
        nonlocal reads
        reads += 1
        return None if reads == 1 else original_load(session, lookup_key)

    monkeypatch.setattr(transition, "_load", miss_before_concurrent_insert)
    assert transition._freeze(db, key, {"source": "second"}) == first
    record = db.get(QuantSignalTransitionBaseline, key)
    assert json.loads(record.payload) == first
    assert reads == 2


def test_forward_publication_preserves_return_but_never_realerts_or_claims_a_holding(db):
    old = {"strategy_version":"position-lifecycle-v8.0", "items":[{
        "code":"005930", "market_cap_rank":1, "is_preliminary":False,
        "signal_date":"2026-10-12", "execution_date":"2026-10-12", "event_side":"sell",
        "state_after":"exited", "return_rate":-2.75, "entry_price":101,
        "price":98, "current":{"position_open":False}, "alert_eligible":True,
    }]}
    record = MarketQuantSignalSnapshot(cache_key="v35:150:0:30", payload=json.dumps(old), generated_at=datetime(2026,10,12,21))
    db.add(record)
    db.commit()
    archive = transition.freeze_legacy_market_publication(db, 150, 0, 30)
    record.payload = json.dumps({"items":[]})
    db.flush()
    assert transition.freeze_legacy_market_publication(db, 150, 0, 30) == archive
    items = transition.archived_market_items(archive, as_of=date(2026,10,13), recent_days=30)
    assert len(items) == 1 and items[0]["return_rate"] == -2.75
    assert items[0]["entry_price"] == 101 and items[0]["price"] == 98
    assert items[0]["history_frozen"] and not items[0]["alert_eligible"]
    assert not items[0]["is_current_holding"] and "current" not in items[0]
    assert not transition.legacy_open_codes(archive)
    assert old["items"][0]["alert_eligible"]  # caller input was not rewritten


def test_forward_inputs_never_fall_back_to_display_ohlc(db):
    rows = history()
    rows.append(DailyPrice(code="005930", trade_date=date(2026,10,13), open=100, high=110,
                           low=80, close=90, volume=999, trading_value=100_000))
    now = datetime(2026,10,13,17,tzinfo=qs.KST)
    with pytest.raises(UnverifiedRegularSessionPrice):
        transition.prepare_forward_inputs(db, "005930", rows, now=now)
    minutes = minute_rows()
    for item in minutes:
        item["trade_date"] = "20261013"
    evidence = regular_session_evidence("005930", date(2026,10,13), minutes, observed_at=now)
    store_regular_session_evidence(db, evidence, observed_at=now)
    db.flush()
    envelope, paths = transition.prepare_forward_inputs(db, "005930", rows, now=now)
    assert envelope.lower[-1].close == 100 and envelope.lower[-1].volume == 3810
    assert rows[-1].close == 90
    assert len(paths[date(2026,10,13)]) == 381
    lightweight, no_paths = transition.prepare_forward_inputs(db, "005930", rows, now=now, include_paths=False)
    assert lightweight.evidence == {} and no_paths == {}
    assert [(row.trade_date, row.close) for row in lightweight.lower] == [(row.trade_date, row.close) for row in envelope.lower]


def _flat_replay_fixture(db, monkeypatch, *, conflict_date=date(2026, 10, 30),
                         published_event=False, stale=False, observed=False,
                         warmup_date=None):
    from app.services.regular_price_replay import RegularPriceEnvelope

    code = "005930"
    warmup = warmup_date or transition.FLAT_REPLAY_WARMUP_DATE
    source_day = warmup - timedelta(days=1) if stale else warmup
    rows = history(code) + [DailyPrice(
        code=code, trade_date=warmup, open=100, high=101, low=99,
        close=100, volume=1000, trading_value=101_000_000_000,
        market_cap=100_000_000_000,
    )]
    envelope = RegularPriceEnvelope(rows, rows, {warmup: {"regular_rows": []}})
    item = {"code": code, "signal_date": "2026-10-30", "execution_date": "2026-10-30",
            "event_side": "buy"} if published_event else None
    sources = {}
    for days in (30, 90):
        payload = {
            "strategy_version": transition.REGULAR_FORWARD_STRATEGY_VERSION,
            "as_of": f"{source_day.isoformat()}T22:00:00+09:00",
            "universe_as_of": source_day.isoformat(),
            "items": [item] if item else [],
        }
        key = qs.market_quant_signal_snapshot_key(150, 0, days)
        record = MarketQuantSignalSnapshot(
            cache_key=key, payload=json.dumps(payload),
            generated_at=datetime(source_day.year, source_day.month, source_day.day, 13),
        )
        db.add(record)
        sources[key] = record.payload
    if observed:
        db.add(QuantSignalObservedEntry(
            stock_code=code, trade_date=date(2026, 10, 30),
            policy_version="test", status="watching", payload="{}",
            updated_at=datetime(2026, 10, 30, 1),
        ))
    db.flush()
    calls = []

    def paths(_db, stock_code, _envelope, *, now, min_trade_date=None):
        assert stock_code == code and _envelope is envelope
        calls.append(min_trade_date)
        if min_trade_date is None:
            raise transition.HistoricalPathConflict(conflict_date, "과거 분봉 불일치")
        return {warmup: []}

    monkeypatch.setattr(transition, "prepare_forward_paths", paths)
    timeline = {warmup: {
        "strategy_version": transition.REGULAR_FORWARD_STRATEGY_VERSION,
        "policy_version": transition.REGULAR_FORWARD_ENTRY_POLICY,
        "quality": {"state": "blocked"},
    }}
    return code, envelope, timeline, sources, calls


def test_flat_replay_restarts_only_after_frozen_publications_and_flat_warmup(db, monkeypatch):
    code, envelope, timeline, sources, calls = _flat_replay_fixture(db, monkeypatch)
    now = datetime(2026, 11, 4, 9, tzinfo=qs.KST)
    paths, lifecycle_start, baseline = transition.prepare_forward_paths_with_flat_replay(
        db, code, envelope, now=now, evidence_timeline=timeline,
    )
    assert paths == {transition.FLAT_REPLAY_WARMUP_DATE: []}
    assert lifecycle_start == transition.FLAT_REPLAY_WARMUP_DATE
    assert baseline["conflict_date"] == "2026-10-30"
    assert baseline["flat_events"] == 0 and not baseline["flat_position"]
    assert calls == [None, transition.FLAT_REPLAY_WARMUP_DATE]
    assert {key: db.get(MarketQuantSignalSnapshot, key).payload for key in sources} == sources
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") == baseline
    paths_again, start_again, baseline_again = transition.prepare_forward_paths_with_flat_replay(
        db, code, envelope, now=now, evidence_timeline=timeline,
    )
    assert (paths_again, start_again, baseline_again) == (paths, lifecycle_start, baseline)
    assert calls[-1] == transition.FLAT_REPLAY_WARMUP_DATE


def test_flat_replay_skips_old_snapshot_but_revalidates_new_paths(db, monkeypatch):
    from app.services import regular_price_replay
    from app.services.regular_price_replay import RegularPriceEnvelope

    code = "005930"
    old_day = date(2026, 10, 30)
    new_day = transition.FLAT_REPLAY_WARMUP_DATE
    old = QuantSignalIntradayPathSnapshot(
        stock_code=code, trade_date=old_day, strategy_version="position-lifecycle-v8.1",
        source="kis_rest", payload="frozen-old-path", is_final=True,
        observed_at=datetime(2026, 10, 30, 7),
    )
    db.add(old)
    db.flush()
    envelope = RegularPriceEnvelope([], [], {
        old_day: {"regular_rows": ["old"]},
        new_day: {"regular_rows": ["new"]},
    })
    monkeypatch.setattr(regular_price_replay, "regular_ordered_paths",
                        lambda _envelope: {old_day: ["old"], new_day: ["new"]})
    checked = []

    def store(_db, stock_code, day, rows, **_kwargs):
        checked.append((stock_code, day, rows))
        if day == old_day:
            raise qs.UnverifiedIntradayPathError("old path differs")

    monkeypatch.setattr(qs, "_store_verified_intraday_path", store)
    with pytest.raises(transition.HistoricalPathConflict) as conflict:
        transition.prepare_forward_paths(
            db, code, envelope, now=datetime(2026, 11, 4, 9, tzinfo=qs.KST),
        )
    assert conflict.value.trade_date == old_day
    checked.clear()
    paths = transition.prepare_forward_paths(
        db, code, envelope, now=datetime(2026, 11, 4, 9, tzinfo=qs.KST),
        min_trade_date=new_day,
    )
    assert paths == {new_day: ["new"]}
    assert checked == []
    assert db.get(QuantSignalIntradayPathSnapshot, (code, old_day)).payload == "frozen-old-path"
    db.add(QuantSignalIntradayPathSnapshot(
        stock_code=code, trade_date=new_day, strategy_version="position-lifecycle-v8.1",
        source="kis_rest", payload="new-path", is_final=True,
        observed_at=datetime(2026, 11, 3, 7),
    ))
    db.flush()
    transition.prepare_forward_paths(
        db, code, envelope, now=datetime(2026, 11, 4, 9, tzinfo=qs.KST),
        min_trade_date=new_day,
    )
    assert checked == [(code, new_day, ["new"])]


def _assert_flat_replay_quarantined(db, monkeypatch, *, published_event=False,
                                    stale=False, observed=False,
                                    conflict_date=date(2026, 10, 30)):
    code, envelope, timeline, _, _ = _flat_replay_fixture(
        db, monkeypatch, conflict_date=conflict_date, published_event=published_event,
        stale=stale, observed=observed,
    )
    with pytest.raises(UnverifiedRegularSessionPrice):
        transition.prepare_forward_paths_with_flat_replay(
            db, code, envelope, now=datetime(2026, 11, 4, 9, tzinfo=qs.KST),
            evidence_timeline=timeline,
        )
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") is None


def test_flat_replay_keeps_published_path_quarantined(db, monkeypatch):
    _assert_flat_replay_quarantined(db, monkeypatch, published_event=True)


def test_flat_replay_keeps_stale_publication_quarantined(db, monkeypatch):
    _assert_flat_replay_quarantined(db, monkeypatch, stale=True)


def test_flat_replay_keeps_observed_entry_quarantined(db, monkeypatch):
    _assert_flat_replay_quarantined(db, monkeypatch, observed=True)


def test_flat_replay_keeps_new_path_conflict_quarantined(db, monkeypatch):
    _assert_flat_replay_quarantined(db, monkeypatch, conflict_date=date(2026, 11, 3))


def test_flat_replay_rejects_first_activation_after_entry_day(db, monkeypatch):
    code, envelope, timeline, _, _ = _flat_replay_fixture(db, monkeypatch)
    with pytest.raises(UnverifiedRegularSessionPrice):
        transition.prepare_forward_paths_with_flat_replay(
            db, code, envelope, now=datetime(2026, 11, 5, 9, tzinfo=qs.KST),
            evidence_timeline=timeline,
        )
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") is None


def test_flat_replay_requires_new_close_if_first_activated_after_market(db, monkeypatch):
    code, envelope, timeline, _, _ = _flat_replay_fixture(db, monkeypatch)
    with pytest.raises(UnverifiedRegularSessionPrice, match="최신 공개"):
        transition.prepare_forward_paths_with_flat_replay(
            db, code, envelope, now=datetime(2026, 11, 4, 16, tzinfo=qs.KST),
            evidence_timeline=timeline,
        )
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") is None


def test_flat_replay_requires_publication_payload_to_cover_completed_close(db, monkeypatch):
    code, envelope, timeline, _, _ = _flat_replay_fixture(db, monkeypatch)
    for days in (30, 90):
        record = db.get(MarketQuantSignalSnapshot, qs.market_quant_signal_snapshot_key(150, 0, days))
        payload = json.loads(record.payload)
        payload["as_of"] = "2026-11-03T14:30:00+09:00"
        record.payload = json.dumps(payload)
    db.flush()
    with pytest.raises(UnverifiedRegularSessionPrice, match="공개된 진입"):
        transition.prepare_forward_paths_with_flat_replay(
            db, code, envelope, now=datetime(2026, 11, 4, 9, tzinfo=qs.KST),
            evidence_timeline=timeline,
        )
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") is None


def test_flat_replay_rejects_stale_universe_even_with_new_generation_clock(db, monkeypatch):
    code, envelope, timeline, _, _ = _flat_replay_fixture(db, monkeypatch)
    for days in (30, 90):
        record = db.get(MarketQuantSignalSnapshot, qs.market_quant_signal_snapshot_key(150, 0, days))
        payload = json.loads(record.payload)
        payload["universe_as_of"] = "2026-11-02"
        record.payload = json.dumps(payload)
    db.flush()
    with pytest.raises(UnverifiedRegularSessionPrice, match="공개된 진입"):
        transition.prepare_forward_paths_with_flat_replay(
            db, code, envelope, now=datetime(2026, 11, 4, 9, tzinfo=qs.KST),
            evidence_timeline=timeline,
        )
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") is None



def test_rolling_flat_replay_recovers_proven_flat_stock_before_next_open(db, monkeypatch):
    warmup = date(2026, 11, 10)
    code, envelope, timeline, sources, calls = _flat_replay_fixture(
        db, monkeypatch, warmup_date=warmup,
    )
    now = datetime(2026, 11, 11, 8, 30, tzinfo=qs.KST)
    paths, lifecycle_start, baseline = transition.prepare_forward_paths_with_flat_replay(
        db, code, envelope, now=now, evidence_timeline=timeline,
    )
    assert paths == {warmup: []}
    assert lifecycle_start == warmup
    assert baseline["policy"] == transition.FLAT_REPLAY_ROLLING_POLICY
    assert baseline["entry_date"] == "2026-11-11"
    assert baseline["conflict_date"] == "2026-10-30"
    assert calls == [None, warmup]
    assert {key: db.get(MarketQuantSignalSnapshot, key).payload for key in sources} == sources
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") == baseline
    again = transition.prepare_forward_paths_with_flat_replay(
        db, code, envelope, now=datetime(2026, 11, 12, 8, tzinfo=qs.KST),
        evidence_timeline=timeline,
    )
    assert again == (paths, lifecycle_start, baseline)
    assert calls[-1] == warmup


@pytest.mark.parametrize("fixture_changes", [
    {"published_event": True},
    {"stale": True},
    {"observed": True},
    {"conflict_date": date(2026, 11, 10)},
], ids=["published_event", "stale", "observed", "conflict_date"])
def test_rolling_flat_replay_keeps_unproven_stocks_quarantined(db, monkeypatch, fixture_changes):
    code, envelope, timeline, _, _ = _flat_replay_fixture(
        db, monkeypatch, warmup_date=date(2026, 11, 10), **fixture_changes,
    )
    with pytest.raises(UnverifiedRegularSessionPrice):
        transition.prepare_forward_paths_with_flat_replay(
            db, code, envelope, now=datetime(2026, 11, 11, 8, 30, tzinfo=qs.KST),
            evidence_timeline=timeline,
        )
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") is None


def test_rolling_flat_replay_refuses_first_activation_after_market_open(db, monkeypatch):
    code, envelope, timeline, _, _ = _flat_replay_fixture(
        db, monkeypatch, warmup_date=date(2026, 11, 10),
    )
    with pytest.raises(UnverifiedRegularSessionPrice):
        transition.prepare_forward_paths_with_flat_replay(
            db, code, envelope, now=datetime(2026, 11, 11, 9, 0, tzinfo=qs.KST),
            evidence_timeline=timeline,
        )
    assert transition._load(db, f"{transition.REGULAR_FORWARD_VERSION}:flat-replay:{code}") is None

def test_flat_replay_stock_detail_uses_same_start_and_exposes_policy(db, monkeypatch):
    from app.services.regular_price_replay import RegularPriceEnvelope

    code = "005930"
    rows = history(code)
    db.add(StockMaster(code=code, name="삼성전자", market="KOSPI", is_active=True))
    db.add_all(rows)
    db.commit()
    captured = {}
    baseline = {"policy": transition.FLAT_REPLAY_POLICY,
                "entry_date": "2026-11-04", "warmup_date": "2026-11-03"}
    monkeypatch.setattr(qs, "prepare_forward_envelope",
                        lambda *_args, **_kwargs: RegularPriceEnvelope(rows, rows, {}))
    monkeypatch.setattr(qs, "forward_entry_timeline", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(qs, "prepare_forward_paths_with_flat_replay",
                        lambda *_args, **_kwargs: ({}, transition.FLAT_REPLAY_WARMUP_DATE, baseline))

    def build(*_args, **kwargs):
        captured.update(kwargs)
        return {"items": [], "current": {"action": "waiting"}}

    monkeypatch.setattr(qs, "_market_stock_payload_with_intraday_path", build)
    payload = qs.load_quant_signal_payload(
        db, code, now=datetime(2026, 11, 4, 9, tzinfo=qs.KST),
    )
    assert captured["lifecycle_start_date"] == transition.FLAT_REPLAY_WARMUP_DATE
    assert payload["forward_replay_rebase"] == baseline


def test_forward_first_day_never_executes_a_legacy_setup():
    rows = history()
    stock = StockMaster(code="005930", name="삼성전자", market="KOSPI")
    payload = qs.build_quant_signal_payload(stock, rows, now=datetime(2026,10,13,8,tzinfo=qs.KST),
                lifecycle_start_date=transition.REGULAR_FORWARD_START)
    assert payload["events"] == [] and payload["trades"] == []
    assert payload["current"]["action"] == "waiting"
    assert not payload["current"]["position_open"]
    assert payload["performance"]["completed_trades"] == 0
    assert payload["price_basis"]["warmup_basis"].startswith("frozen_legacy")


def test_forward_entry_policy_does_not_reuse_legacy_confirmation(db, monkeypatch):
    from app.services import signal_entry_evidence as entry
    stock = StockMaster(code="005930", name="삼성전자", market="KOSPI")
    rows = history()
    assert transition.forward_entry_timeline(db, stock, rows, flow_prices=rows,
                now=datetime(2026,10,13,8,tzinfo=qs.KST)) == {}
    day = date(2026,10,13)
    rows.append(DailyPrice(code=stock.code, trade_date=day, close=100))
    captured = {}
    def ensure(*args, **kwargs):
        captured.update(kwargs)
        return {"strategy_version":kwargs["strategy_version"], "policy_version":kwargs["policy_version"], "quality":{"state":"blocked"}}
    monkeypatch.setattr(entry, "ensure_entry_evidence_snapshot", ensure)
    result = transition.forward_entry_timeline(db, stock, rows, flow_prices=[],
                now=datetime(2026,10,13,17,tzinfo=qs.KST), relative_context={"signal_date":day.isoformat()})
    assert result[day]["quality"]["state"] == "blocked"
    assert captured["flow_prices"] == []
    assert captured["policy_version"] == transition.REGULAR_FORWARD_ENTRY_POLICY
    assert captured["strategy_version"] != entry.ENTRY_EVIDENCE_STRATEGY_VERSION


def test_forward_collection_does_not_call_sources_before_first_close(db):
    class Provider:
        def fetch_regular_session_data(self, *_):
            raise AssertionError("must not fetch a forming session")
    assert transition.collect_forward_session(db, Provider(), now=datetime(2026,10,13,9,tzinfo=qs.KST))["attempted"] == 0


def test_forward_collection_keeps_recent_members_after_rank_exit(db, monkeypatch):
    from app.services import regular_session_prices

    previous, current = date(2026, 10, 23), date(2026, 10, 26)
    for day, first_cap, second_cap in (
        (previous, 200, 100), (current, 100, 200),
    ):
        db.add_all([
            DailyPrice(code="000001", trade_date=day, market_cap=first_cap),
            DailyPrice(code="000002", trade_date=day, market_cap=second_cap),
        ])
    db.flush()
    captured = {}

    def collect(_db, _provider, **kwargs):
        captured.update(kwargs)
        return {"attempted": 0, "state": "ready"}

    monkeypatch.setattr(regular_session_prices, "collect_regular_session_prices", collect)
    transition.collect_forward_session(
        db, object(), now=datetime(2026, 10, 27, 8, tzinfo=qs.KST),
        universe_limit=1,
    )
    assert captured["codes"] == ["000001", "000002"]
    assert captured["start"] == transition.REGULAR_FORWARD_START
    assert captured["end"] == current


def test_forward_collection_uses_explicit_qa_scope_without_retention(db, monkeypatch):
    from app.services import regular_session_prices

    captured = {}

    def collect(_db, _provider, **kwargs):
        captured.update(kwargs)
        return {"attempted": 0, "state": "ready"}

    monkeypatch.setattr(regular_session_prices, "collect_regular_session_prices", collect)
    transition.collect_forward_session(
        db,
        object(),
        now=datetime(2026, 10, 27, 8, tzinfo=qs.KST),
        codes=["000002", "000001", "000002"],
        retry_cooldown=timedelta(minutes=1),
    )

    assert captured["codes"] == ["000001", "000002"]
    assert captured["retry_cooldown"] == timedelta(minutes=1)


def test_forward_market_feed_preserves_published_returns_without_legacy_alerts(db):
    stock = StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True)
    db.add(stock)
    db.add_all(history())
    legacy = {"strategy_version":"position-lifecycle-v8.0", "items":[{
        "code":"005930", "name":"삼성전자", "market":"KOSPI", "market_cap_rank":1,
        "signal_date":"2026-10-12", "execution_date":"2026-10-12", "signal_at":"2026-10-12T15:00:00+09:00",
        "is_preliminary":False, "status":"confirmed", "event_side":"sell", "side":"sell", "state_after":"exited",
        "return_rate":-2.75, "entry_price":101, "target_sell_price":105, "price":98,
    }]}
    db.add(MarketQuantSignalSnapshot(cache_key="v35:150:0:30", payload=json.dumps(legacy), generated_at=datetime(2026,10,12,21)))
    db.commit()
    result = qs.load_market_quant_signal_feed(db, universe_limit=150, limit=0, recent_days=30,
                    now=datetime(2026,10,13,8,tzinfo=qs.KST))
    assert result["strategy_version"] == transition.REGULAR_FORWARD_STRATEGY_VERSION
    assert result["data_state"] == "ready"
    assert result["items"][0]["return_rate"] == -2.75
    assert result["items"][0]["alert_eligible"] is False
    assert all(item.get("history_frozen") for item in result["items"])
    stored = json.loads(db.get(MarketQuantSignalSnapshot, "v35:150:0:30").payload)
    assert stored == legacy


def test_forward_feed_freezes_current_entry_evidence_before_old_path_is_quarantined(db, monkeypatch):
    from app.services.regular_price_replay import RegularPriceEnvelope

    day = date(2026, 10, 13)
    db.add(StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True))
    db.add_all(history())
    db.add(DailyPrice(
        code="005930", trade_date=day, open=100, high=101, low=99,
        close=100, volume=1_000, trading_value=101_000_000_000,
        market_cap=100_000_000_000,
    ))
    db.commit()

    calls = []
    def prepare_envelope(_db, code, rows, *, now):
        assert code == "005930"
        calls.append("envelope")
        return RegularPriceEnvelope(rows, rows, {})

    def prepare_paths(*_args, **_kwargs):
        calls.append("paths")
        raise UnverifiedRegularSessionPrice("과거 체결 분봉이 미봉인입니다")

    def relative_context(_db, signal_date, *, prices_by_code):
        assert signal_date == day
        assert list(prices_by_code) == ["005930"]
        calls.append("peer_context")
        return {}

    monkeypatch.setattr(qs, "prepare_forward_envelope", prepare_envelope)
    monkeypatch.setattr(qs, "prepare_forward_paths_with_flat_replay", prepare_paths)
    monkeypatch.setattr(qs, "build_relative_strength_context", relative_context)
    result = qs.load_market_quant_signal_feed(
        db, universe_limit=150, limit=0, recent_days=30,
        now=datetime(2026, 10, 13, 17, tzinfo=qs.KST),
    )
    db.expire_all()
    evidence = db.scalar(select(QuantSignalEvidenceSnapshot).where(
        QuantSignalEvidenceSnapshot.stock_code == "005930",
        QuantSignalEvidenceSnapshot.signal_date == day,
        QuantSignalEvidenceSnapshot.strategy_version == transition.REGULAR_FORWARD_STRATEGY_VERSION,
    ))
    assert evidence is not None
    assert evidence.policy_version == transition.REGULAR_FORWARD_ENTRY_POLICY
    assert calls == ["envelope", "peer_context", "paths"]
    assert result["execution_replay_unverified_codes"] == ["005930"]
    assert result["items"] == []


def test_forward_detail_and_feed_do_not_inherit_or_block_a_frozen_legacy_holding(db):
    code = "005930"
    db.add(StockMaster(code=code, name="삼성전자", market="KOSPI", is_active=True))
    db.add_all(history(code))
    legacy = {"strategy_version": "position-lifecycle-v8.0", "items": [{
        "code": code, "name": "삼성전자", "market": "KOSPI", "market_cap_rank": 1,
        "signal_date": "2026-10-12", "execution_date": "2026-10-12",
        "is_preliminary": False, "status": "confirmed", "event_side": "buy",
        "side": "buy", "state_after": "holding", "entry_price": 101,
        "current": {"position_open": True}, "is_current_holding": True,
        "alert_eligible": True,
    }]}
    db.add(MarketQuantSignalSnapshot(
        cache_key="v35:150:0:90", payload=json.dumps(legacy),
        generated_at=datetime(2026, 10, 12, 21),
    ))
    db.commit()
    original = db.get(MarketQuantSignalSnapshot, "v35:150:0:90").payload
    now = datetime(2026, 10, 13, 8, tzinfo=qs.KST)

    detail = qs.load_quant_signal_payload(db, code, now=now)
    assert detail is not None
    assert detail["data_state"] == "ready"
    assert detail["events"] == []
    assert detail["current"]["position_open"] is False
    assert detail["performance"]["completed_trades"] == 0
    assert len(detail["legacy_history"]) == 1
    assert detail["legacy_history"][0]["history_frozen"] is True
    assert detail["legacy_history"][0]["is_current_holding"] is False
    assert detail["legacy_history"][0]["alert_eligible"] is False

    feed = qs.load_market_quant_signal_feed(
        db, universe_limit=150, limit=0, recent_days=90, now=now,
    )
    assert code not in feed["execution_replay_unverified_codes"]
    assert feed["data_state"] == "ready"
    assert all(not item.get("alert_eligible") for item in feed["items"])
    assert db.get(MarketQuantSignalSnapshot, "v35:150:0:90").payload == original


def test_forward_shadow_uses_same_verified_paths_and_never_promotes(db, monkeypatch):
    from app.services import entry_filter_backtest as shadow
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026,10,13,17,tzinfo=qs.KST)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    monkeypatch.setattr(shadow, "datetime", Clock)
    db.add(StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True))
    db.add_all(history())
    db.add(DailyPrice(code="005930", trade_date=date(2026,10,13), open=100, high=110, low=90,
                     close=100, volume=100, trading_value=10000, market_cap=100_000_000_000))
    rows = minute_rows()
    for row in rows:
        row["trade_date"] = "20261013"
    evidence = regular_session_evidence("005930", date(2026,10,13), rows, observed_at=Clock.now(qs.KST))
    store_regular_session_evidence(db, evidence, observed_at=Clock.now(qs.KST))
    db.commit()
    original = qs._simulate
    calls = []
    def replay(*args, **kwargs):
        calls.append((kwargs["entry_filter_version"], deepcopy(kwargs["intraday_minutes_by_date"])))
        assert kwargs["lifecycle_start_date"] == date(2026,10,13)
        return original(*args, **kwargs)
    monkeypatch.setattr(qs, "_simulate", replay)
    report = shadow._build_regular_forward_shadow_report(db, universe_limit=1, recent_trading_days=22)
    assert len(calls) == 8 and {version for version, _paths in calls} == set(shadow.FILTER_VERSIONS)
    assert all(paths == calls[0][1] for _version, paths in calls)
    assert report["symbols_evaluated"] == 1
    assert report["price_basis"]["version"] == "krx-regular-forward-v1"
    assert report["forward_comparison"]["promotion_assessment"]["automatic_promotion"] is False


def test_forward_execution_uses_prior_close_risk_not_current_day_hindsight(monkeypatch):
    from tests.test_quant_signals import _strategy_test_inputs, _set_entry_indicator
    bars, indicators = _strategy_test_inputs(67)
    start = date(2026,10,13)
    bars[65] = qs.PriceBar(start, 100, 101, 99, 100, 1_000_000, 50_000_000_000)
    bars[66] = qs.PriceBar(start + timedelta(days=1), 100, 106, 100, 105, 1_000_000, 50_000_000_000)
    _set_entry_indicator(indicators[65])
    indicators[66]["atr"] = 999  # unknowable at the day's first execution
    observed = []
    monkeypatch.setattr(qs, "entry_confirmation_decision", lambda *args, **kwargs: {"allowed":True,"state":"approved","reason":"fixture"})
    real = qs._ordered_intraday_exit_decisions
    def exits(position, minutes, indicator):
        observed.append(indicator["atr"])
        return real(position, minutes, indicator)
    monkeypatch.setattr(qs, "_ordered_intraday_exit_decisions", exits)
    result = qs._simulate(bars, indicators, lifecycle_start_date=start,
                          intraday_minutes_by_date={bars[66].trade_date:[bars[66]]})
    assert any(event["side"] == "buy" for event in result["events"])
    assert observed and all(value == indicators[65]["atr"] for value in observed)


def test_forward_regular_quote_does_not_use_preopen_open_and_keeps_date_validation():
    now = datetime(2026,10,14,9,3,tzinfo=qs.KST)
    rows = [{"trade_date":"20261014", "trade_time":f"090{minute}00", "open":100,
             "high":102,"low":99,"price":101,"volume":10} for minute in range(3)]
    quote = {"price":101,"open":90,"high":105,"low":90,"volume":999,
             "observed_at":now,"intraday_minutes_observed_at":now,"intraday_minutes":rows}
    regular = transition.regular_intraday_quote(quote)
    assert regular["open"] == 100 and regular["volume"] == 30
    bar = qs.PriceBar(date(2026,10,14), regular["open"],regular["high"],regular["low"],regular["price"],30,1)
    assert len(qs._verified_intraday_minutes(regular, bar)) == 3
    bad = deepcopy(regular)
    bad["intraday_minutes"][0]["trade_date"] = "20261013"
    assert qs._verified_intraday_minutes(bad, bar) is None


def test_forward_quality_marks_corrupt_seal_invalid_without_crashing(db):
    from app.config import Settings
    from app.models import QuantSignalIntradayPathSnapshot
    from app.services.signal_data_quality import signal_data_quality_status
    now = datetime(2026,10,13,17,tzinfo=qs.KST)
    db.add(QuantSignalIntradayPathSnapshot(stock_code="005930", trade_date=now.date(),
        strategy_version=qs.STRATEGY_VERSION, source="kis_rest", payload="{invalid",
        is_final=True, observed_at=now.replace(tzinfo=None)))
    db.commit()
    report = signal_data_quality_status(db, Settings(_env_file=None), now=now)
    assert report["intraday_path_seal"]["sample"]["state"] == "invalid"


def test_forward_quality_counts_new_policy_without_retagging_legacy_evidence(db, monkeypatch):
    from app.config import Settings
    from app.models import QuantSignalEvidenceSnapshot
    from app.services import signal_data_quality as quality
    day = date(2026,10,13)
    monkeypatch.setattr(quality, "latest_completed_korea_market_session_date", lambda *_: day)
    db.add(StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True))
    db.add(DailyPrice(code="005930", trade_date=day, open=100,high=101,low=99,close=100,volume=10,trading_value=1000,market_cap=100_000))
    legacy = QuantSignalEvidenceSnapshot(stock_code="005930",signal_date=day,strategy_version="position-lifecycle-v7.0",
        policy_version="legacy", quality_state="ready",payload="{}",generated_at=datetime(2026,10,13,9))
    db.add(legacy)
    db.commit()
    now = datetime(2026,10,13,19,tzinfo=qs.KST)
    before = quality.signal_data_quality_status(db, Settings(_env_file=None), now=now)["datasets"]["entry_evidence_snapshot"]
    assert before["strategy_version"] == qs.STRATEGY_VERSION and before["covered"] == 0
    assert before["missing_codes"] == ["005930"]
    db.add(IngestionRun(
        source="kis",
        dataset="qa_regular_session_evidence",
        status="partial",
        rows_loaded=0,
        finished_at=now.replace(tzinfo=None),
        message=json.dumps({
            "observed_at": now.isoformat(),
            "attempted": 1,
            "ready": 0,
            "already_ready": 0,
            "deferred": 0,
            "unverified": [{
                "code": "005930",
                "trade_date": day.isoformat(),
                "reason": "source_unavailable",
                "error_type": "RuntimeError",
            }],
        }),
    ))
    db.commit()
    diagnosed = quality.signal_data_quality_status(db, Settings(_env_file=None), now=now)["datasets"]["entry_evidence_snapshot"]
    assert diagnosed["qa_regular_evidence"]["unverified"] == [{
        "code": "005930",
        "trade_date": day.isoformat(),
        "reason": "source_unavailable",
        "error_type": "RuntimeError",
    }]
    db.add(QuantSignalEvidenceSnapshot(stock_code="005930",signal_date=day,strategy_version=qs.STRATEGY_VERSION,
        policy_version=transition.REGULAR_FORWARD_ENTRY_POLICY,quality_state="ready",payload="{}",generated_at=datetime(2026,10,13,9)))
    db.commit()
    after = quality.signal_data_quality_status(db, Settings(_env_file=None), now=now)["datasets"]["entry_evidence_snapshot"]
    assert after["covered"] == 1 and after["state"] == "ready"
    assert legacy.strategy_version == "position-lifecycle-v7.0"
