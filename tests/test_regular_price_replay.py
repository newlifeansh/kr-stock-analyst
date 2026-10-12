from datetime import date, timedelta

import pytest

from app.models import DailyPrice
from app.services.regular_price_replay import RegularPriceEnvelope, turnover_decision_certificate
from app.services.regular_session_prices import UnverifiedRegularSessionPrice


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
