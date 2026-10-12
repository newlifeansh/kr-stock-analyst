"""Aggregate production signal evidence only, in a read-only DB transaction."""
import json
import sys
import base64
import gzip
from hashlib import sha256
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import func, select, text
from app.db import SessionLocal
from app.models import DailyPrice, StockMaster, QuantSignalEvidenceSnapshot, QuantSignalIntradayPathSnapshot, MarketQuantSignalSnapshot
from app.services.quant_signals import _market_signal_retention_state, STRATEGY_VERSION, SIGNAL_HISTORY_ROWS, MARKET_SIGNAL_FEED_LIMIT, market_quant_signal_snapshot_key
from app.services.signal_entry_evidence import ENTRY_EVIDENCE_EFFECTIVE_DATE

with SessionLocal() as db:
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("This production probe requires PostgreSQL read-only transactions")
    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    latest = db.scalar(select(func.max(DailyPrice.trade_date)))
    ranked = select(
        DailyPrice.code.label("code"),
        func.row_number().over(partition_by=DailyPrice.trade_date, order_by=(DailyPrice.market_cap.desc(), DailyPrice.code)).label("rank"),
    ).join(StockMaster, StockMaster.code == DailyPrice.code).where(
        StockMaster.is_active.is_(True), StockMaster.market.in_(("KOSPI", "KOSDAQ")),
        DailyPrice.trade_date >= latest - timedelta(days=90),
        DailyPrice.market_cap > 0, DailyPrice.close.is_not(None),
    ).subquery()
    ranked_codes = set(db.scalars(select(ranked.c.code).where(ranked.c.rank <= 150)))
    retained = set()
    for window in (30, 90):
        retained.update(_market_signal_retention_state(db, universe_limit=150, limit=MARKET_SIGNAL_FEED_LIMIT, recent_days=window))
    codes = sorted(ranked_codes | retained)
    coverage = db.execute(select(
        QuantSignalEvidenceSnapshot.signal_date,
        QuantSignalEvidenceSnapshot.strategy_version,
        func.count(func.distinct(QuantSignalEvidenceSnapshot.stock_code)),
    ).where(
        QuantSignalEvidenceSnapshot.stock_code.in_(codes),
        QuantSignalEvidenceSnapshot.signal_date >= date(2026, 9, 14),
    ).group_by(QuantSignalEvidenceSnapshot.signal_date, QuantSignalEvidenceSnapshot.strategy_version).order_by(QuantSignalEvidenceSnapshot.signal_date)).all()
    paths = db.execute(select(
        QuantSignalIntradayPathSnapshot.trade_date,
        QuantSignalIntradayPathSnapshot.is_final,
        func.count(),
    ).where(QuantSignalIntradayPathSnapshot.trade_date >= date(2026, 9, 14)).group_by(QuantSignalIntradayPathSnapshot.trade_date, QuantSignalIntradayPathSnapshot.is_final).order_by(QuantSignalIntradayPathSnapshot.trade_date)).all()
    output = {
        "transaction_read_only": db.scalar(text("SHOW transaction_read_only")),
        "transaction_isolation": db.scalar(text("SHOW transaction_isolation")),
        "observed_at": datetime.now(timezone.utc),
        "snapshot_feed_limit": MARKET_SIGNAL_FEED_LIMIT,
        "production_strategy": STRATEGY_VERSION, "latest_price_date": latest,
        "ranked_codes": sorted(ranked_codes), "retained_codes": sorted(retained), "combined_count":len(codes),
        "entry_evidence_by_day": [{"date":d,"strategy":v,"codes":n} for d,v,n in coverage],
        "intraday_paths_by_day": [{"date":d,"final":final,"count":n} for d,final,n in paths],
        "writes":0, "notifications_sent":0,
    }
    if "--archive" in sys.argv:
        price_fields = ("code", "trade_date", "open", "high", "low", "close", "volume", "trading_value", "market_cap", "listed_shares")
        prices = select(
            *(getattr(DailyPrice, field).label(field) for field in price_fields),
            func.row_number().over(partition_by=DailyPrice.code, order_by=DailyPrice.trade_date.desc()).label("position"),
        ).where(DailyPrice.code.in_(codes)).subquery()
        price_rows = [dict(row) for row in db.execute(select(*(getattr(prices.c, field) for field in price_fields)).where(prices.c.position <= SIGNAL_HISTORY_ROWS).order_by(prices.c.code, prices.c.trade_date)).mappings()]
        evidence = list(db.scalars(select(QuantSignalEvidenceSnapshot).where(
            QuantSignalEvidenceSnapshot.stock_code.in_(codes),
            QuantSignalEvidenceSnapshot.signal_date >= ENTRY_EVIDENCE_EFFECTIVE_DATE,
            QuantSignalEvidenceSnapshot.signal_date <= latest,
        ).order_by(QuantSignalEvidenceSnapshot.stock_code, QuantSignalEvidenceSnapshot.signal_date)))
        records = [{key:getattr(row,key) for key in ("stock_code","signal_date","strategy_version","policy_version","quality_state","payload","generated_at","updated_at")} for row in evidence]
        market_snapshots = []
        for window in (30, 90):
            key = market_quant_signal_snapshot_key(150, MARKET_SIGNAL_FEED_LIMIT, window)
            row = db.get(MarketQuantSignalSnapshot, key)
            if row is not None:
                market_snapshots.append({"key":key,"generated_at":row.generated_at,"payload":row.payload})
        intraday = [{key:getattr(row,key) for key in ("stock_code","trade_date","strategy_version","source","payload","is_final","observed_at","updated_at")} for row in db.scalars(select(QuantSignalIntradayPathSnapshot).where(QuantSignalIntradayPathSnapshot.stock_code.in_(codes),QuantSignalIntradayPathSnapshot.trade_date >= date(2026,9,14)))]
        archive = {"metadata":output,"history_rows_per_code":SIGNAL_HISTORY_ROWS,"daily_prices":price_rows,"entry_evidence":records,"market_snapshots":market_snapshots,"intraday_paths":intraday}
        encoded = json.dumps(archive, sort_keys=True, separators=(",",":"), default=str).encode()
        output = {"encoding":"gzip+base64","sha256":sha256(encoded).hexdigest(),"price_rows":len(price_rows),"evidence_rows":len(records),"payload":base64.b64encode(gzip.compress(encoded)).decode()}
    db.rollback()
print(json.dumps(output, default=str))
