"""Read-only production-cohort coverage and path-basis diagnostic.

The archive is never imported. Sidecar records remain local, do not count as
deployed data, and cannot approve a signal, an alert or a production release.
Run from the repository root with python -m scripts.audit_production_regular_coverage.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DailyPrice, SignalSessionPrice
from app.services.regular_session_prices import (
    REGULAR_PRICE_BASIS, REGULAR_PRICE_EFFECTIVE_DATE,
    UnverifiedRegularSessionPrice, _session_dates, load_regular_session_evidence,
)
from scripts.replay_regular_price_basis import (
    archived_path_audit, archived_publication_context, decode_production_archive,
)


def audit(archive, db, through):
    metadata = archive["metadata"]
    if metadata.get("transaction_isolation") != "repeatable read":
        raise ValueError("A coherent repeatable-read production export is required")
    codes = sorted(set(metadata["ranked_codes"]) | set(metadata["retained_codes"]))
    if len(codes) != metadata["combined_count"]:
        raise ValueError("Production cohort count does not match archive metadata")
    by_code = {code: [] for code in codes}
    for item in archive["daily_prices"]:
        if item["code"] in by_code and item["trade_date"] <= through.isoformat():
            by_code[item["code"]].append(DailyPrice(**{**item, "trade_date":date.fromisoformat(item["trade_date"])}))
    records = list(db.scalars(select(SignalSessionPrice).where(
        SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS,
        SignalSessionPrice.trade_date <= through,
    )))
    stored = {}
    for record in records:
        stored.setdefault((record.code, record.trade_date), []).append(record)
    items = []
    for code in codes:
        prices = by_code[code]
        if not prices:
            raise ValueError(f"{code}: missing archived price history")
        start = max(REGULAR_PRICE_EFFECTIVE_DATE, min(p.trade_date for p in prices))
        evidence, days = {}, []
        for day in _session_dates(start, through):
            saved = stored.get((code, day), [])
            row = {"trade_date":day.isoformat()}
            if not saved:
                row.update(state="missing", reason="not_collected")
            else:
                try:
                    value = load_regular_session_evidence(db, code, day, allow_bounded=True)
                except UnverifiedRegularSessionPrice as exc:
                    row.update(state="unverified", reason=str(exc), source_reasons=sorted({json.loads(s.payload)["evidence"].get("reason") or "unspecified" for s in saved}))
                else:
                    evidence[day] = value
                    row.update(state=value["state"], reason=None)
            days.append(row)
        published = archived_publication_context(archive, code)
        items.append({
            "code":code, "days":days,
            "states":dict(Counter(row["state"] for row in days)),
            "complete_verified_price_path":bool(days) and all(row["state"] in {"bounded","ready"} for row in days),
            "published_open_holding":any(row["position_open"] for row in published),
            "published_retained_candidate":code in metadata["retained_codes"],
            "archived_publication":published,
            "archived_path_audit":archived_path_audit(archive, code, prices, evidence),
        })
    return {
        "read_only":True, "production_ready":False, "production_writes":0,
        "notifications_sent":0, "history_overwrite":False,
        "basis_version":REGULAR_PRICE_BASIS,
        "through":through.isoformat(), "production_cohort_count":len(codes),
        "local_only_codes":sorted({r.code for r in records} - set(codes)),
        "price_path_states":dict(Counter(row["state"] for item in items for row in item["days"])),
        "complete_verified_price_path_codes":[i["code"] for i in items if i["complete_verified_price_path"]],
        "published_open_holding_codes":[i["code"] for i in items if i["published_open_holding"]],
        "limitations":["Local sidecar evidence is not deployed data", "Missing sessions are not assumed to be no-trade sessions", "Frozen entry evidence and runtime basis migration remain separately required"],
        "items":items,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-archive", type=Path, required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    envelope = json.loads(args.production_archive.read_text())
    archive = decode_production_archive(envelope)
    with SessionLocal() as db:
        result = audit(archive, db, date.fromisoformat(args.through))
        db.rollback()
    result["production_archive_sha256"] = envelope["sha256"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k not in {"items","local_only_codes"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
