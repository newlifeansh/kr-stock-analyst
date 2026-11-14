from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import subprocess

from app.services import us_position_lifecycle as lifecycle
from app.services import quant_signals
from app.services.us_market import build_us_quant_signals
from app.services.public_signal import public_market_signal_payload


def test_us_performance_marks_repeated_window_samples():
    source_path = Path(__file__).resolve().parents[1] / "app/static/dashboard/app.js"
    script = r"""
const assert = require('node:assert/strict');
const source = require('node:fs').readFileSync(process.argv[1], 'utf8');
const begin = source.indexOf('function aiSignalPerformanceWindowState(');
const end = source.indexOf('function aiSignalCandidateScanView(', begin);
assert.ok(begin >= 0 && end > begin);
const section = source.slice(begin, end);
const toNumber = value => value == null ? null : Number(value);
const build = (isUs, marketScope) => new Function('toNumber', 'isUsHubContext', 'state',
  `${section}\nreturn aiSignalPerformanceWindowState;`)(toNumber, isUs, { marketScope });
const us = build(true, 'us');
const kr = build(false, 'kr');
const unifiedKr = build(true, 'kr');
const seven = { completed_trades: 3, average_return: 4.13, sample_state: 'limited' };
const fifteen = { ...seven };
const thirty = { ...seven };
assert.equal(us(seven, null).sameSample, false);
assert.equal(us(fifteen, seven).statusLabel, '동일 표본');
assert.equal(us(thirty, fifteen).sameSample, true);
assert.equal(us({ ...thirty, completed_trades: 4 }, fifteen).sameSample, false);
assert.equal(us({ completed_trades: 0, average_return: null }, seven).statusLabel, '표본 없음');
assert.equal(us({ completed_trades: 2, average_return: 1 }, { completed_trades: 0 }).sameSample, false);
assert.equal(kr(fifteen, seven).sameSample, true);
assert.equal(unifiedKr(fifteen, seven).sameSample, true);
"""
    subprocess.run(["node", "-e", script, str(source_path)], check=True, capture_output=True, text=True)


def test_us_performance_windows_exclude_partial_future_invalid_and_duplicates():
    as_of = datetime(2026, 10, 9, 20, tzinfo=timezone.utc)

    def exit(days, value, code="AAPL", **changes):
        return {"code": code, "name": "Apple", "market": "NASDAQ",
                "side": "sell", "state_after": "exited",
                "execution_date": (as_of - timedelta(days=days)).date(),
                "signal_date": (as_of - timedelta(days=days + 1)).date(),
                "entry_date": (as_of - timedelta(days=days + 5)).date(),
                "price": "250.00", "entry_price": "240.00",
                "return_rate": value, **changes}

    events = [exit(7, "3"), exit(15, "-1"), exit(30, "4"), exit(31, "99"),
              exit(-1, "99"), exit(1, "NaN"), exit(2, "Infinity"),
              exit(3, None), exit(4, "90", side="partial_sell"), exit(7, "3")]
    summary = lifecycle.build_us_signal_performance_summary(events, as_of=as_of)
    assert summary["return_basis"] == "completed_trade_gross_price_return"
    public = public_market_signal_payload({
        "strategy_version": "position-lifecycle-us-v2-rc1", "items": [],
        "performance_summary": summary,
    })
    assert public["performance_summary"]["cost_basis"] == "gross_before_costs_tax_fx"
    assert "return_basis" not in public["performance_summary"]
    for key, count, average in (("7d", 1, "3"), ("15d", 2, "1"), ("30d", 3, "2")):
        window = summary["windows"][key]
        assert window["completed_trades"] == count
        assert window["average_return"] == Decimal(average)
        assert window["sample_state"] == "limited"
    ledger = summary["completed_trade_items"]
    assert summary["completed_trade_window_days"] == 30
    assert len(ledger) == summary["windows"]["30d"]["completed_trades"] == 3
    assert [item["execution_date"] for item in ledger] == sorted(
        [item["execution_date"] for item in ledger], reverse=True
    )
    assert [item["code"] for item in ledger] == ["AAPL", "AAPL", "AAPL"]
    assert all(item["display_return_kind"] == "closed_trade" for item in ledger)
    assert len(public["performance_summary"]["completed_trade_items"]) == 3
    assert all(
        "entry_price" not in item
        for item in public["performance_summary"]["completed_trade_items"]
    )
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
    assert len(response["performance_summary"]["completed_trade_items"]) == 100
    assert response["performance_summary"]["windows"]["7d"]["sample_state"] == "sufficient"
    assert len(feed["items"]) == 100


def test_us_hybrid_performance_uses_one_share_cash_flows_and_keeps_legacy_mean():
    as_of = datetime(2026, 11, 13, 20, tzinfo=timezone.utc)

    def event(code, days, side, price, *, fraction=None, return_rate=None):
        row = {
            "code": code, "side": side, "price": str(price),
            "execution_date": (as_of - timedelta(days=days)).date(),
            "signal_date": (as_of - timedelta(days=days + 1)).date(),
            "state_after": "exited" if side == "sell" else "partially_exited" if side == "partial_sell" else "holding",
        }
        if fraction is not None:
            row["sell_fraction_original"] = str(fraction)
        if return_rate is not None:
            row["return_rate"] = str(return_rate)
        return row

    events = [
        event("LOW", 2, "buy", 10), event("LOW", 1, "sell", 11, fraction=1, return_rate=10),
        event("HIGH", 11, "buy", 100), event("HIGH", 10, "sell", 95, fraction=1, return_rate=-5),
        event("PART", 21, "buy", 200),
        event("PART", 20, "partial_sell", 206, fraction="0.5"),
        event("PART", 20, "sell", 210, fraction="0.5", return_rate=4),
    ]
    hybrid = lifecycle.build_us_signal_performance_summary(events, as_of=as_of, one_share=True)
    legacy = lifecycle.build_us_signal_performance_summary(events, as_of=as_of)
    assert hybrid["version"] == "us-performance-v2-one-share"
    assert hybrid["return_basis"] == "completed_trade_one_share_gross_cash_return"
    assert [hybrid["windows"][key]["average_return"] for key in ("7d", "15d", "30d")] == [
        Decimal("10.00"), Decimal("-3.64"), Decimal("1.29"),
    ]
    assert [hybrid["windows"][key]["one_share_basis_count"] for key in ("7d", "15d", "30d")] == [1, 2, 3]
    assert hybrid["windows"]["30d"]["completed_trades"] == 3
    assert legacy["version"] == "us-performance-v1"
    assert legacy["windows"]["30d"]["average_return"] == Decimal("3.00")
    public = public_market_signal_payload({
        "strategy_version": "position-lifecycle-us-v3-hybrid1", "items": [],
        "performance_summary": hybrid,
    })["performance_summary"]
    assert public["aggregation_basis"] == "one_share_gross_cash_return"
    assert public["cost_basis"] == "gross_before_costs_tax_fx"
    assert "return_basis" not in public
    assert all("entry_price" not in item for item in public["completed_trade_items"])


def test_us_one_share_performance_fails_closed_when_entry_or_exit_cash_is_unverified():
    as_of = datetime(2026, 11, 13, 20, tzinfo=timezone.utc)
    events = [
        {"code": "AAPL", "side": "sell", "state_after": "exited",
         "execution_date": as_of.date(), "price": "110", "return_rate": "10"},
    ]
    summary = lifecycle.build_us_signal_performance_summary(events, as_of=as_of, one_share=True)
    window = summary["windows"]["7d"]
    assert window["completed_trades"] == 1
    assert window["one_share_basis_count"] == 0
    assert window["average_return"] is None


def test_kr_one_share_display_uses_cash_flows_and_preserves_net_guard_mean():
    as_of = datetime(2026, 11, 14, 15, tzinfo=timezone.utc)

    def event(code, days, side, price, *, entry_price, net_return=None, sold_percent=None,
              profit_stage=0):
        row = {
            "code": code, "event_side": side, "status": "confirmed",
            "state_after": "exited" if side == "sell" else "partially_exited",
            "signal_date": (as_of - timedelta(days=days + 1)).date(),
            "execution_date": (as_of - timedelta(days=days)).date(),
            "entry_date": (as_of - timedelta(days=days + 5)).date(),
            "entry_price": entry_price, "price": price,
            "profit_stage": profit_stage,
        }
        if net_return is not None:
            row["return_rate"] = net_return
        if sold_percent is not None:
            row["sold_percent"] = sold_percent
        return row

    items = [
        event("LOW", 2, "sell", 11, entry_price=10, net_return="9.70"),
        event("HIGH", 10, "sell", 95, entry_price=100, net_return="-5.30"),
        event("PART", 20, "partial_sell", 206, entry_price=200, sold_percent=50),
        event("PART", 20, "sell", 210, entry_price=200, net_return="3.70", profit_stage=1),
    ]
    # The partial and final event belong to the same entry date.
    items[-2]["entry_date"] = items[-1]["entry_date"]
    summary = {
        "return_basis": "completed_trade_net_of_costs",
        "windows": {
            "7d": {"period_start": (as_of - timedelta(days=7)).date(), "period_end": as_of.date(),
                   "completed_trades": 1, "average_return": Decimal("9.70")},
            "15d": {"period_start": (as_of - timedelta(days=15)).date(), "period_end": as_of.date(),
                    "completed_trades": 2, "average_return": Decimal("2.20")},
            "30d": {"period_start": (as_of - timedelta(days=30)).date(), "period_end": as_of.date(),
                    "completed_trades": 3, "average_return": Decimal("2.70")},
        },
    }
    quant_signals.attach_market_one_share_performance(summary, items)
    assert summary["return_basis"] == "completed_trade_net_of_costs"
    assert summary["display_aggregation_basis"] == "one_share_gross_cash_return"
    assert [summary["windows"][key]["one_share_return"] for key in ("7d", "15d", "30d")] == [
        Decimal("10.00"), Decimal("-3.64"), Decimal("1.29"),
    ]
    assert [summary["windows"][key]["one_share_basis_count"] for key in ("7d", "15d", "30d")] == [1, 2, 3]
    assert summary["windows"]["30d"]["average_return"] == Decimal("2.70")


def test_kr_one_share_display_hides_incomplete_or_inconsistent_cash_flow():
    as_of = date(2026, 11, 14)
    base = {"code": "005930", "event_side": "sell", "status": "confirmed",
            "state_after": "exited", "signal_date": as_of, "execution_date": as_of,
            "entry_date": date(2026, 11, 10), "entry_price": 100, "price": 110,
            "return_rate": "9.70"}
    summary = {"windows": {"7d": {"period_start": date(2026, 11, 7),
                                  "period_end": as_of, "completed_trades": 2,
                                  "average_return": Decimal("1.00")}}}
    quant_signals.attach_market_one_share_performance(summary, [base])
    assert summary["windows"]["7d"]["one_share_basis_count"] == 1
    assert summary["windows"]["7d"]["one_share_return"] is None
    missing_partial = {**base, "profit_stage": 1}
    summary["windows"]["7d"]["completed_trades"] = 1
    quant_signals.attach_market_one_share_performance(summary, [missing_partial])
    assert summary["windows"]["7d"]["one_share_basis_count"] == 0
    assert summary["windows"]["7d"]["one_share_return"] is None
