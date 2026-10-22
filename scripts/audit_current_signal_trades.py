"""Read-only forward-trade audit with exact-minute, original-weight benchmarks.

Run from the project root with ``python -m scripts.audit_current_signal_trades``.
No broker orders, signal publication, database writes, or notification sends.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from app.services.us_hybrid_signals import US_HYBRID_VERSION
from app.services.us_market import fetch_chart_range
from app.services.us_market_calendar import us_market_session


def _number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("nonfinite_number")
    return result


def _at(value):
    result = datetime.fromisoformat(str(value))
    if result.tzinfo is None:
        raise ValueError("missing_timezone")
    return result.astimezone(timezone.utc)


def reconstruct_trades(events):
    """Pair each close with its own buy, including same-symbol reentries."""
    unique = {}
    for event in events:
        if event.get("strategy_version") != US_HYBRID_VERSION:
            raise ValueError("wrong_strategy")
        key = event["event_id"]
        if key in unique and unique[key] != event:
            raise ValueError("conflicting_event_identity")
        unique[key] = event
    positions, closed = {}, []
    for event in sorted(unique.values(), key=lambda e: (_at(e["observed_at"]), e["event_id"])):
        code, side = event["code"], event["side"]
        price = _number(event["price"])
        if price <= 0 or event.get("intraday_execution_verified") is not True:
            raise ValueError("unverified_event")
        if side == "buy":
            if code in positions:
                raise ValueError("overlapping_entry")
            positions[code] = {"code": code, "entry_event_id": event["event_id"],
                               "entry_at": event["observed_at"], "entry_price": price,
                               "remaining": Decimal(1), "exits": []}
            continue
        if side not in {"partial_sell", "sell"} or code not in positions:
            raise ValueError("missing_entry")
        trade = positions[code]
        fraction = _number(event["sell_fraction_original"])
        if not 0 < fraction <= trade["remaining"] or _at(event["observed_at"]) <= _at(trade["entry_at"]):
            raise ValueError("invalid_exit")
        trade["exits"].append({"event_id": event["event_id"], "at": event["observed_at"],
                              "price": price, "fraction_original": fraction})
        trade["remaining"] -= fraction
        if side == "sell":
            if trade["remaining"] != 0 or event.get("state_after") != "exited":
                raise ValueError("incomplete_terminal_exit")
            realized = sum(x["fraction_original"] * (x["price"] / trade["entry_price"] - 1) * 100 for x in trade["exits"])
            if abs(realized - _number(event["return_rate"])) > Decimal("0.000001"):
                raise ValueError("ledger_return_mismatch")
            trade.update(exit_at=event["observed_at"], return_rate=realized,
                         exit_event_id=event["event_id"])
            closed.append(positions.pop(code))
        elif trade["remaining"] <= 0:
            raise ValueError("partial_exit_exhausted_position")
    return closed, list(positions.values())


def benchmark_minutes(symbol, raw, *, as_of):
    meta = raw.get("meta") or {}
    if meta.get("symbol") != symbol or meta.get("currency") != "USD" or meta.get("instrumentType") != "ETF":
        raise ValueError("benchmark_identity")
    quote = ((raw.get("indicators") or {}).get("quote") or [{}])[0]
    prices = {}
    for i, timestamp in enumerate(raw.get("timestamp") or []):
        stamp = int(timestamp)
        at = datetime.fromtimestamp(stamp, timezone.utc)
        session = us_market_session(at.astimezone(ZoneInfo('America/New_York')).date())
        if not session or not session.open_at <= at < session.close_at or stamp + 60 > as_of.timestamp():
            continue
        if stamp % 60 or stamp in prices:
            raise ValueError("benchmark_minute_order")
        try:
            values = {k: _number(quote[k][i]) for k in ("open", "high", "low", "close", "volume")}
        except (KeyError, IndexError, TypeError, ArithmeticError, ValueError):
            continue
        if (any(v <= 0 for v in values.values()) or values['high'] < max(values['open'], values['close'])
                or values['low'] > min(values['open'], values['close'])):
            continue
        prices[stamp] = values["close"]
    return prices


def compare_trades(trades, benchmarks, *, split_events=None):
    result = []
    for trade in trades:
        row = {**trade, "benchmarks": {}}
        start = int(_at(trade["entry_at"]).timestamp())
        end = int(_at(trade["exit_at"]).timestamp())
        for symbol, prices in benchmarks.items():
            required = [start] + [int(_at(x["at"]).timestamp()) for x in trade["exits"]]
            if any(start <= t <= end for t in (split_events or {}).get(symbol, [])):
                row["benchmarks"][symbol] = {"state": "corporate_action_review"}
                continue
            if any(t not in prices for t in required):
                row["benchmarks"][symbol] = {"state": "missing_exact_minute"}
                continue
            weighted = sum(x["fraction_original"] * (prices[int(_at(x['at']).timestamp())] / prices[start] - 1) * 100 for x in trade['exits'])
            holding = (prices[end] / prices[start] - 1) * 100
            row["benchmarks"][symbol] = {"state": "matched", "entry_price": prices[start],
                "terminal_price": prices[end], "same_holding_period_return": holding,
                "same_exit_weights_return": weighted, "excess_same_exit_weights_pp": trade["return_rate"] - weighted}
        result.append(row)
    return result


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2,
                      default=lambda v: float(v) if isinstance(v, Decimal) else str(v), allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--us-url', default='https://us-market-web-production-production.up.railway.app')
    parser.add_argument('--kr-url', default='https://secretnote.cloud')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    def get(url):
        response = requests.get(url, timeout=60); response.raise_for_status(); return response.json()
    us = get(args.us_url.rstrip('/') + '/us/market/quant-signals?limit=50&recent_days=90')
    kr = get(args.kr_url.rstrip('/') + '/market/quant-signals?universe_limit=150&limit=0&recent_days=90')
    (args.output/'us-feed.json').write_text(_json(us));(args.output/'kr-feed.json').write_text(_json(kr))
    events = [event for item in us.get('items',[]) for event in item.get('events',[])]
    trades, opened = reconstruct_trades(events)
    prices, split_events = {}, {}
    for symbol in ('SPY','QQQ','XLV'):
        raw = fetch_chart_range(symbol, range_='8d', interval='1m', include_prepost=False, refresh=True)
        (args.output/f'{symbol}-1m.json').write_text(_json(raw))
        prices[symbol] = benchmark_minutes(symbol,raw,as_of=now)
        split_events[symbol] = [int(x['date']) for x in ((raw.get('events') or {}).get('splits') or {}).values()]
    comparison = compare_trades(trades,prices,split_events=split_events)
    expected = ((us.get('performance_summary') or {}).get('windows') or {}).get('30d',{}).get('completed_trades')
    recent = [t for t in trades if (now-_at(t['exit_at'])).total_seconds() <= 30*86400]
    summaries = {}
    for symbol in prices:
        matched = [t for t in comparison if t['benchmarks'][symbol]['state']=='matched']
        n=len(matched)
        summaries[symbol] = {'matched_trades':n,
            'average_strategy_return':sum(t['return_rate'] for t in matched)/n if n else None,
            'average_same_exit_weights_return':sum(t['benchmarks'][symbol]['same_exit_weights_return'] for t in matched)/n if n else None,
            'average_excess_same_exit_weights_pp':sum(t['benchmarks'][symbol]['excess_same_exit_weights_pp'] for t in matched)/n if n else None}
    report = {'as_of':now,'us_strategy_version':us.get('strategy_version'),'return_basis':'gross_price_return_USD_no_fees_tax_fx_or_dividends',
        'benchmark_basis':'exact_same_completed_minute_close_and_original_position_exit_weights',
        'aggregation':'equal_weight_mean_of_closed_trades_not_a_portfolio_return',
        'coverage_complete_for_public_30d_summary':expected==len(recent),'public_expected_closed_30d':expected,
        'closed_trades':len(trades),'open_positions':len(opened),'sample_state':'limited' if len(trades)<20 else 'descriptive_sample',
        'trades':comparison,'summary':summaries,'kr_strategy_version':kr.get('strategy_version'),
        'kr_forward_events':[e for e in kr.get('items',[]) if not e.get('history_frozen') and str(e.get('execution_date') or e.get('signal_date') or '')>='2026-10-13' and not e.get('is_preliminary')],
        'kr_performance_summary':kr.get('performance_summary'),'kr_unverified_codes':kr.get('execution_replay_unverified_codes'),
        'writes_to_services':0,'notifications_sent':0}
    (args.output/'comparison.json').write_text(_json(report))
    manifest = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.glob('*.json') if p.name!='sha256.json'}
    (args.output/'sha256.json').write_text(_json(manifest))
    print(_json({k:report[k] for k in ('closed_trades','open_positions','coverage_complete_for_public_30d_summary','summary')}))


if __name__ == '__main__':
    main()
