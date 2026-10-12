from datetime import date, timedelta

import pytest
import base64
import gzip
import json
from hashlib import sha256

from app.models import DailyPrice
from app.services.regular_price_replay import RegularPriceEnvelope, turnover_decision_certificate
from app.services.regular_session_prices import UnverifiedRegularSessionPrice
from scripts.replay_regular_price_basis import decode_production_archive, production_archive_inputs


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
