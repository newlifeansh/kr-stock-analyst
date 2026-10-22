from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import subprocess

from app.services import us_position_lifecycle as lifecycle
from app.services.us_market import build_us_quant_signals
from app.services.public_signal import public_market_signal_payload


def test_us_performance_display_hides_only_repeated_window_samples():
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
assert.equal(kr(fifteen, seven).sameSample, false);
assert.equal(unifiedKr(fifteen, seven).sameSample, false);
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
