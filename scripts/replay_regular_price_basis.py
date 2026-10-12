"""Explicit local migration diagnostic, never an operational backtest report.

The old entry evidence remains frozen. This diagnostic cannot approve a new
entry-evidence basis, overwrite published history, or send notifications.
"""
from __future__ import annotations

import argparse
import base64
import gzip
from hashlib import sha256
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from statistics import median

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DailyPrice, SignalSessionPrice
from app.services import quant_signals as qs
from app.services.regular_price_replay import (
    regular_ordered_paths, regular_price_envelope, turnover_decision_certificate,
)
from app.services.regular_session_prices import (
    PRICE_FIELDS, REGULAR_PRICE_BASIS, REGULAR_PRICE_EFFECTIVE_DATE,
    regular_session_evidence, store_regular_session_evidence,
)
from app.services.signal_entry_evidence import ENTRY_EVIDENCE_STRATEGY_VERSION, load_entry_evidence_timeline
from app.services.signal_mode_comparison import simulate_v8_intraday_ohlc_proxy


def periods(trades, through):
    result = {}
    for days in (7, 15, 30):
        start = through - timedelta(days=days - 1)
        returns = [float(trade["net_return"]) for trade in trades
                   if trade.get("exit_date") and start <= trade["exit_date"] <= through]
        result[str(days)] = {
            "completed_trades": len(returns),
            "mean_return_percent": sum(returns) / len(returns) if returns else None,
            "median_return_percent": median(returns) if returns else None,
            "win_rate_percent": 100 * sum(x > 0 for x in returns) / len(returns) if returns else None,
        }
    return result


def decode_production_archive(envelope):
    """Verify a bounded, read-only export; never import it into the local DB."""
    if envelope.get("encoding") != "gzip+base64":
        raise ValueError("Unsupported evidence archive encoding")
    raw = gzip.decompress(base64.b64decode(envelope["payload"], validate=True))
    if sha256(raw).hexdigest() != envelope.get("sha256"):
        raise ValueError("Production evidence archive checksum mismatch")
    archive = json.loads(raw)
    metadata = archive["metadata"]
    if metadata.get("transaction_read_only") != "on" or metadata.get("writes") != 0 or metadata.get("notifications_sent") != 0:
        raise ValueError("Archive is not a read-only evidence export")
    if len(archive["daily_prices"]) != envelope.get("price_rows") or len(archive["entry_evidence"]) != envelope.get("evidence_rows"):
        raise ValueError("Archive row counts differ from its manifest")
    return archive


def production_archive_inputs(archive, code, through):
    prices, timeline = {}, {}
    for item in archive["daily_prices"]:
        if item["code"] != code:
            continue
        day = date.fromisoformat(item["trade_date"])
        if day > through:
            continue
        if day in prices:
            raise ValueError("Duplicate archived daily price")
        prices[day] = DailyPrice(**{**item, "trade_date": day})
    for item in archive["entry_evidence"]:
        if item["stock_code"] != code or item["strategy_version"] != ENTRY_EVIDENCE_STRATEGY_VERSION:
            continue
        day = date.fromisoformat(item["signal_date"])
        if day > through:
            continue
        payload = json.loads(item["payload"])
        if payload.get("stock_code") != code or payload.get("signal_date") != day.isoformat() or payload.get("strategy_version") != item["strategy_version"] or payload.get("policy_version") != item["policy_version"]:
            raise ValueError("Frozen entry evidence identity mismatch")
        if day in timeline:
            raise ValueError("Duplicate archived frozen entry evidence")
        timeline[day] = payload
    if not prices:
        raise ValueError(f"{code}: no prices in scoped production archive")
    return [prices[day] for day in sorted(prices)], timeline


def run(args):
    codes = sorted(set(args.codes.split(",")))
    through = date.fromisoformat(args.through)
    archive_envelope = json.loads(args.production_archive.read_text()) if getattr(args, "production_archive", None) else None
    archive = decode_production_archive(archive_envelope) if archive_envelope else None
    report = {
        "basis_version": REGULAR_PRICE_BASIS, "production_ready": False,
        "diagnostic_only": True, "signals_published": 0, "notifications_sent": 0,
        "history_overwrite": False, "entry_evidence_basis": "unchanged_frozen_legacy",
        "limitations": [
            "Not a regular-basis independent-entry-evidence migration approval",
            "H1/H2/H3 shadow numbers remain daily OHLC proxies, not minute executions",
            "Universe coverage is limited to explicitly selected codes",
        ], "items": [],
    }
    if archive_envelope:
        report["production_archive_sha256"] = archive_envelope["sha256"]
        report["entry_evidence_basis"] = "read_only_production_frozen_legacy_archive"
        report["price_history_basis"] = "read_only_production_archive"
    with SessionLocal() as db:
        if args.materialize_retained_evidence:
            for record in db.scalars(select(SignalSessionPrice).where(
                SignalSessionPrice.code.in_(codes),
                SignalSessionPrice.basis_version == "krx-regular-session-v1",
                SignalSessionPrice.trade_date <= through,
            )).all():
                original = json.loads(record.payload)["evidence"]
                stamp = record.observed_at.replace(tzinfo=timezone.utc)
                evidence = regular_session_evidence(
                    record.code, record.trade_date, original["raw_rows"], observed_at=stamp,
                    preopen_baseline=original.get("preopen_baseline"),
                    closing_auction_evidence=original.get("closing_auction_evidence"),
                )
                store_regular_session_evidence(db, evidence, observed_at=stamp)
            db.commit()
        for code in codes:
            if archive is not None:
                rows, timeline = production_archive_inputs(archive, code, through)
            else:
                rows = list(reversed(list(db.scalars(select(DailyPrice).where(
                    DailyPrice.code == code, DailyPrice.trade_date <= through,
                ).order_by(DailyPrice.trade_date.desc()).limit(qs.SIGNAL_HISTORY_ROWS)))))
                timeline = load_entry_evidence_timeline(db, code)
            envelope = regular_price_envelope(db, code, rows, completed_through=through)
            certificate = turnover_decision_certificate(envelope)
            paths = regular_ordered_paths(envelope)
            cases = {}
            for name, scenario in (("legacy_daily_ohlc_fallback", rows), ("lower", envelope.lower), ("upper", envelope.upper)):
                bars = qs._normalize_prices(scenario)
                indicators = qs._indicator_rows(bars)
                if len(bars) <= qs.WARMUP_ROWS:
                    raise ValueError(f"{code}: insufficient warmup history")
                actual = qs._simulate(bars, indicators, timeline, intraday_minutes_by_date=paths if name != "legacy_daily_ohlc_fallback" else None)
                shadow = {version: simulate_v8_intraday_ohlc_proxy(bars, indicators, entry_filter_version=version)
                          for version in (qs.ENTRY_FILTER_H1_VERSION, qs.ENTRY_FILTER_H2_VERSION, qs.ENTRY_FILTER_H3_VERSION)}
                cases[name] = {"h1_frozen_evidence": actual, "proxy_filters": shadow,
                               "recent_completed": periods(actual["trades"], through)}
            original_by_date = {row.trade_date: row for row in rows}
            changed = []
            for day, evidence in envelope.evidence.items():
                original = original_by_date.get(day)
                old = {key: getattr(original, key) for key in PRICE_FIELDS} if original else None
                if old != evidence["prices"]:
                    changed.append({"trade_date": day.isoformat(), "legacy": old,
                                    "regular": evidence["prices"], "turnover_bounds": evidence["turnover_bounds"]})
            item = {
                "code": code, "through": through.isoformat(), "certificate": certificate,
                "all_replay_outputs_identical_at_money_bounds": cases["lower"] == cases["upper"],
                "frozen_evidence_days": len(timeline),
                "missing_post_change_entry_evidence": [day.isoformat() for day in envelope.evidence if day not in timeline],
                "regular_paths": len(paths), "changed_prices": changed,
                "scenarios": {key: value for key, value in cases.items() if key != "upper"},
            }
            report["items"].append(item)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes", required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--materialize-retained-evidence", action="store_true")
    parser.add_argument("--production-archive", type=Path, help="Read a checksummed frozen export without importing or overwriting local records")
    args = parser.parse_args()
    report = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps({"production_ready": False, "items": [{
        "code": item["code"], "certificate": item["certificate"]["state"],
        "identical_at_bounds": item["all_replay_outputs_identical_at_money_bounds"],
        "regular_paths": item["regular_paths"],
        "missing_evidence": len(item["missing_post_change_entry_evidence"]),
        "recent_completed": item["scenarios"]["lower"]["recent_completed"],
    } for item in report["items"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
