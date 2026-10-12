"""Replay an immutable production export in an isolated in-memory database.

No network access, orders, pushes, or changes to the source database/archive.
The archive's old publication is the control, not a regenerated old backtest.
"""
import argparse
from datetime import date, datetime
import json
from pathlib import Path

from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.db import Base
from app.models import DailyPrice, MarketQuantSignalSnapshot, StockMaster
from app.services import quant_signals as qs
from scripts.replay_regular_price_basis import decode_production_archive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    args = parser.parse_args()
    archive = decode_production_archive(json.loads(Path(args.archive).read_text()))
    codes = sorted(set(archive["metadata"]["ranked_codes"]) | set(archive["metadata"]["retained_codes"]))
    snapshots = [{**item, "payload":json.loads(item["payload"])} for item in archive["market_snapshots"]]
    known = {item["code"]: item for snapshot in snapshots for item in snapshot["payload"].get("items", [])}
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(StockMaster), [{"code":code, "name":known.get(code, {}).get("name", code),
            "market":known.get(code, {}).get("market", "KOSPI"), "is_active":True} for code in codes])
        conn.execute(insert(DailyPrice), [{**item, "trade_date":date.fromisoformat(item["trade_date"])} for item in archive["daily_prices"]])
        conn.execute(insert(MarketQuantSignalSnapshot), [{"cache_key":item["key"],
            "generated_at":datetime.fromisoformat(item["generated_at"]),
            "payload":json.dumps(item["payload"])} for item in snapshots])
    now = datetime(2026,10,13,8,tzinfo=qs.KST)
    reports = []
    with Session(engine) as db:
        for days in (30, 90):
            original = next(item["payload"] for item in snapshots if item["key"] == f"v35:150:0:{days}")
            result = qs.load_market_quant_signal_feed(db, universe_limit=150, limit=0, recent_days=days, now=now)
            old_returns = sorted((str(item.get("code")), str(item.get("execution_date")), str(item.get("return_rate")))
                for item in original["items"] if not item.get("is_preliminary") and item.get("return_rate") is not None)
            new_returns = sorted((str(item.get("code")), str(item.get("execution_date")), str(item.get("return_rate")))
                for item in result["items"] if item.get("history_frozen") and item.get("return_rate") is not None)
            reports.append({"recent_days":days, "universe_count":result["universe_count"],
                "data_state":result["data_state"], "unverified_codes":result["execution_replay_unverified_codes"],
                "archived_items":sum(bool(item.get("history_frozen")) for item in result["items"]),
                "old_return_count":len(old_returns), "preserved_return_count":len(new_returns),
                "returns_identical":old_returns == new_returns,
                "fresh_buy_count":sum(item.get("side") == "buy" and not item.get("history_frozen") for item in result["items"]),
                "archive_alerts_eligible":sum(item.get("alert_eligible") is not False for item in result["items"] if item.get("history_frozen"))})
    print(json.dumps({"source_observed_at":archive["metadata"]["observed_at"], "as_of":now.isoformat(),
                      "production_writes":0, "notifications_sent":0,
                      "scope_note":"Actual archived prices/publications; missing StockMaster names/markets use placeholders. This is publication preservation evidence, not a full production eligibility certification.",
                      "reports":reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
