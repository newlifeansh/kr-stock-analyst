from datetime import date, timedelta

import pytest
import base64
import gzip
import json
from hashlib import sha256

from app.models import DailyPrice
from app.services.regular_price_replay import RegularPriceEnvelope, turnover_decision_certificate
from app.services.regular_session_prices import UnverifiedRegularSessionPrice
from scripts.replay_regular_price_basis import (
    archived_path_audit, archived_publication_context,
    decode_production_archive, production_archive_inputs,
)


def envelope(low, high):
    return RegularPriceEnvelope(*[
        [DailyPrice(code="005930", trade_date=date(2026, 8, 1) + timedelta(days=i),
                    open=100, high=101, low=99, close=100, volume=100,
                    trading_value=amount) for i in range(30)]
        for amount in (low, high)
    ], {})


def test_regular_turnover_certificate_proves_liquidity_and_cost_without_claiming_full_approval():
    result = turnover_decision_certificate(envelope(101_000_000_000, 102_000_000_000))
    assert result["state"] == "invariant"
    assert not result["production_ready"]
    assert not result["independent_entry_evidence_verified"]
    assert all(row["execution_cost_identical"] for row in result["days"])


@pytest.mark.parametrize("threshold", [5_000_000_000, 20_000_000_000, 100_000_000_000])
def test_regular_turnover_certificate_rejects_any_inclusive_threshold_crossing(threshold):
    result = turnover_decision_certificate(envelope(threshold - 1, threshold))
    assert result["state"] == "ambiguous"
    assert result["days"][-1]["crossed_thresholds"] == [threshold]
    # The left edge itself is inclusive; an interval entirely above it is safe.
    assert turnover_decision_certificate(envelope(threshold, threshold + 1))["state"] == "invariant"


def test_regular_turnover_certificate_cannot_hide_price_changes_or_reverse_bounds():
    bad = envelope(20_000_000_000, 21_000_000_000)
    bad.upper[-1].close = 101
    with pytest.raises(UnverifiedRegularSessionPrice):
        turnover_decision_certificate(bad)
    with pytest.raises(UnverifiedRegularSessionPrice):
        turnover_decision_certificate(envelope(21_000_000_000, 20_000_000_000))


def _archive_fixture():
    payload = {"stock_code":"005930","signal_date":"2026-10-12","strategy_version":"position-lifecycle-v7.0","policy_version":"test","quality":{"state":"blocked"}}
    return {
        "metadata":{"transaction_read_only":"on","writes":0,"notifications_sent":0},
        "daily_prices":[{"code":"005930","trade_date":"2026-10-12","open":100,"high":102,"low":99,"close":101,"volume":100,"trading_value":10100,"market_cap":None,"listed_shares":None}],
        "entry_evidence":[{"stock_code":"005930","signal_date":"2026-10-12","strategy_version":"position-lifecycle-v7.0","policy_version":"test","payload":json.dumps(payload)}],
    }


def _packed_archive(archive):
    raw = json.dumps(archive).encode()
    return {"encoding":"gzip+base64","payload":base64.b64encode(gzip.compress(raw)).decode(),"sha256":sha256(raw).hexdigest(),"price_rows":len(archive["daily_prices"]),"evidence_rows":len(archive["entry_evidence"])}


def test_production_archive_replay_preserves_frozen_blocked_evidence_without_database_writes():
    source = _archive_fixture()
    archive = decode_production_archive(_packed_archive(source))
    prices, timeline = production_archive_inputs(archive, "005930", date(2026, 10, 12))
    assert prices[0].close == 101
    assert timeline[date(2026, 10, 12)]["quality"]["state"] == "blocked"
    assert archive == source
    with pytest.raises(ValueError, match="no prices"):
        production_archive_inputs(archive, "000660", date(2026, 10, 12))


def test_production_archive_rejects_checksum_counts_mutating_exports_and_identity_conflicts():
    packed = _packed_archive(_archive_fixture())
    for key, value in (("sha256","bad"),("price_rows",2)):
        with pytest.raises(ValueError):
            decode_production_archive({**packed,key:value})
    source = _archive_fixture()
    source["metadata"]["writes"] = 1
    with pytest.raises(ValueError):
        decode_production_archive(_packed_archive(source))
    source = _archive_fixture()
    source["entry_evidence"][0]["payload"] = source["entry_evidence"][0]["payload"].replace("005930", "000660")
    with pytest.raises(ValueError, match="identity"):
        production_archive_inputs(source, "005930", date(2026, 10, 12))
    source = _archive_fixture()
    source["entry_evidence"].append(dict(source["entry_evidence"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        production_archive_inputs(source, "005930", date(2026, 10, 12))


def test_archived_watch_retention_is_not_reported_as_a_holding_or_a_replay_checkpoint():
    source = _archive_fixture()
    source["market_snapshots"] = [{"key":"v35:150:0:30", "generated_at":"2026-10-12T20:00:00", "payload":json.dumps({"items":[
        {"code":"005930", "is_preliminary":True, "current":{"action":"entry_watch", "position_open":False}, "execution_replay_state":"unverified", "alert_eligible":False},
        {"code":"000660", "is_current_holding":True},
    ]})}]
    result = archived_publication_context(source, "005930")
    assert len(result) == 1
    assert result[0]["action"] == "entry_watch"
    assert result[0]["position_open"] is False
    assert result[0]["alert_eligible"] is False
    assert result[0]["execution_replay_state"] == "unverified"
    assert archived_publication_context(source, "000660")[0]["position_open"] is True


def test_archived_path_audit_preserves_identity_and_does_not_claim_missing_regular_evidence():
    source = _archive_fixture()
    prices, _ = production_archive_inputs(source, "005930", date(2026, 10, 12))
    path = {"stock_code":"005930", "trade_date":"2026-10-12", "is_final":False,
            "source":"kis_rest", "strategy_version":"position-lifecycle-v8.0",
            "payload":json.dumps([{"trade_date":"20261012", "trade_time":"153000", "open":101,"high":101,"low":101,"price":101,"volume":100}])}
    source["intraday_paths"] = [path]
    result = archived_path_audit(source, "005930", prices, {})[0]
    assert result["matches_regular_ohlc"] is False
    assert result["matches_legacy_daily_ohlc"] is False
    assert result["prior_price_touches_preserved"] is None
    assert result["production_seal_changed"] is False
    source["intraday_paths"].append(dict(path))
    with pytest.raises(ValueError, match="Duplicate"):
        archived_path_audit(source, "005930", prices, {})
    source["intraday_paths"] = [{**path, "payload":path["payload"].replace("20261012", "20261008")}]
    with pytest.raises(ValueError, match="identity"):
        archived_path_audit(source, "005930", prices, {})


def test_production_cohort_audit_keeps_missing_sessions_and_validates_archive_scope():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import SignalSessionPrice
    from scripts.audit_production_regular_coverage import audit

    source = _archive_fixture()
    source["metadata"].update(transaction_isolation="repeatable read", ranked_codes=["005930"], retained_codes=[], combined_count=1)
    engine = create_engine("sqlite://")
    SignalSessionPrice.__table__.create(engine)
    with Session(engine) as db:
        result = audit(source, db, date(2026, 10, 12))
        assert result["production_cohort_count"] == 1
        assert result["price_path_states"] == {"missing":1}
        assert result["complete_verified_price_path_codes"] == []
        assert result["production_ready"] is False
        assert not db.new and not db.dirty and not db.deleted
        source["metadata"]["combined_count"] = 2
        with pytest.raises(ValueError, match="cohort"):
            audit(source, db, date(2026, 10, 12))
        source["metadata"]["transaction_isolation"] = "read committed"
        with pytest.raises(ValueError, match="repeatable-read"):
            audit(source, db, date(2026, 10, 12))
