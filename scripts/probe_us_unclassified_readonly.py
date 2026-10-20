"""Read the latest immutable US universe; do not fetch or mutate data."""
import json
from sqlalchemy import text
from app.db import SessionLocal
from app.services.us_signal_universe import load_latest_us_signal_universe_snapshot
from app.services.us_sector_classification import sector_etf_for_cik

with SessionLocal() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    readonly = db.execute(text('SHOW transaction_read_only')).scalar()
    payload = load_latest_us_signal_universe_snapshot(db) or {}
    members = payload.get('items') or payload.get('members') or []
    print(json.dumps({'transaction_read_only': readonly, 'universe_as_of': payload.get('universe_as_of'),
                      'keys': sorted(payload), 'member_count':len(members),
                      'unclassified':[ {k:row.get(k) for k in ('code','name','cik','sector','market_cap_rank')}
                                       for row in members if not sector_etf_for_cik(row.get('cik'))],
                      'writes':0,'notifications_sent':0}, ensure_ascii=False))
    db.rollback()
