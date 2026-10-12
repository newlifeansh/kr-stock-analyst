from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services import us_position_lifecycle as lifecycle
from app.services.us_market import build_us_quant_signals


def test_us_performance_windows_exclude_partial_future_invalid_and_duplicates():
    as_of = datetime(2026, 10, 9, 20, tzinfo=timezone.utc)

    def exit(days, value, code="AAPL", **changes):
        return {"code": code, "side": "sell", "state_after": "exited",
                "execution_date": (as_of - timedelta(days=days)).date(),
                "return_rate": value, **changes}

    events = [exit(7, "3"), exit(15, "-1"), exit(30, "4"), exit(31, "99"),
              exit(-1, "99"), exit(1, "NaN"), exit(2, "Infinity"),
              exit(3, None), exit(4, "90", side="partial_sell"), exit(7, "3")]
    summary = lifecycle.build_us_signal_performance_summary(events, as_of=as_of)
    assert summary["return_basis"] == "completed_trade_gross_price_return"
    for key, count, average in (("7d", 1, "3"), ("15d", 2, "1"), ("30d", 3, "2")):
        window = summary["windows"][key]
        assert window["completed_trades"] == count
        assert window["average_return"] == Decimal(average)
        assert window["sample_state"] == "limited"
    empty = lifecycle.build_us_signal_performance_summary([], as_of=as_of)
    assert all(w["average_return"] is None for w in empty["windows"].values())


def test_us_performance_is_independent_of_public_row_limit():
    as_of = datetime(2026, 10, 9, 20, tzinfo=timezone.utc)
    events = [{"code": str(i), "side": "sell", "state_after": "exited",
               "execution_date": as_of.date(), "return_rate": i - 10} for i in range(100)]
    summary = lifecycle.build_us_signal_performance_summary(events, as_of=as_of)
    feed = {"items": [{"code": str(i)} for i in range(100)],
            "performance_summary": summary, "universe_as_of": as_of.date()}
    response = build_us_quant_signals(limit=1, feed=feed)
    assert len(response["items"]) == 1
    assert response["performance_summary"]["windows"]["7d"]["completed_trades"] == 100
    assert response["performance_summary"]["windows"]["7d"]["sample_state"] == "sufficient"
    assert len(feed["items"]) == 100
