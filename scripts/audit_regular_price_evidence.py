"""Read-only audit of the retained v1 prototype against the corrected basis.

This writes an analysis artifact, never prices, signals, user state or pushes.
The original source observations are retained to reproduce every verdict.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import timezone
import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import SignalSessionPrice
from app.services.regular_session_prices import REGULAR_PRICE_BASIS, regular_session_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-raw", action="store_true")
    args = parser.parse_args()
    items = []
    with SessionLocal() as db:
        for record in db.scalars(select(SignalSessionPrice).where(
            SignalSessionPrice.basis_version == "krx-regular-session-v1",
        ).order_by(SignalSessionPrice.trade_date, SignalSessionPrice.code)):
            original = json.loads(record.payload)["evidence"]
            current = regular_session_evidence(
                record.code, record.trade_date, original["raw_rows"],
                observed_at=record.observed_at.replace(tzinfo=timezone.utc),
                preopen_baseline=original.get("preopen_baseline"),
                closing_auction_evidence=original.get("closing_auction_evidence"),
            )
            items.append({
                "code": record.code, "trade_date": record.trade_date.isoformat(),
                "prior_basis": record.basis_version, "prior_state": record.state,
                "source": current["source"], "state": current["state"],
                "reason": current["reason"], "prices": current["prices"],
                "turnover_bounds": current["turnover_bounds"],
                "observed_at": record.observed_at.replace(tzinfo=timezone.utc).isoformat(),
                **({"raw_evidence": original} if args.include_raw else {}),
            })
    report = {"basis_version": REGULAR_PRICE_BASIS, "read_only": True,
              "production_ready": False, "record_count": len(items),
              "states": dict(Counter(item["state"] for item in items)),
              "reasons": dict(Counter(str(item["reason"]) for item in items)), "items": items}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "items"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
