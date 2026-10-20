"""Read the latest immutable US universe; do not fetch or mutate data."""
import json
from sqlalchemy import text
from app.db import SessionLocal
from app.models import MarketQuantSignalSnapshot
from app.services.us_position_lifecycle import US_POSITION_LIFECYCLE_SNAPSHOT_KEY
from app.services.us_signal_universe import load_latest_us_signal_universe_snapshot
from app.services.us_sector_classification import sector_etf_for_cik

with SessionLocal() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    readonly = db.execute(text('SHOW transaction_read_only')).scalar()
    payload = load_latest_us_signal_universe_snapshot(db) or {}
    members = payload.get('items') or payload.get('members') or []
    row = db.get(MarketQuantSignalSnapshot, US_POSITION_LIFECYCLE_SNAPSHOT_KEY)
    stored = json.loads(row.payload) if row else {}
    stored_summary = {k: stored.get(k) for k in ('status', 'data_state', 'universe_as_of', 'sector_classification_version', 'data_coverage_count', 'universe_count')}
    stored_summary['generated_at'] = str(row.generated_at) if row else None
    print(json.dumps({'transaction_read_only': readonly, 'universe_as_of': payload.get('universe_as_of'),
                      'keys': sorted(payload), 'member_count':len(members),
                      'unclassified':[ {k:row.get(k) for k in ('code','name','cik','sector','market_cap_rank')}
                                       for row in members if not sector_etf_for_cik(row.get('cik'))],
                      'stored_daily_snapshot': stored_summary, 'writes':0,'notifications_sent':0}, ensure_ascii=False))
    db.rollback()
