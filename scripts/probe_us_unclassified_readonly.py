"""Read the latest immutable US universe; do not fetch or mutate data."""
import json
from pathlib import Path
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
    activity = [dict(r._mapping) for r in db.execute(text('''
        SELECT state, wait_event_type, wait_event, count(*) AS connections,
               max(extract(epoch from now()-xact_start)) AS max_transaction_seconds,
               max(extract(epoch from now()-query_start)) AS max_query_seconds
        FROM pg_stat_activity
        WHERE datname=current_database() AND usename=current_user AND pid<>pg_backend_pid()
        GROUP BY state, wait_event_type, wait_event
    '''))]
    proc = {line.split(':',1)[0]:line.split(':',1)[1].strip()
            for line in Path('/proc/1/status').read_text().splitlines()
            if line.split(':',1)[0] in {'Name','Threads','VmRSS'}}
    print(json.dumps({'transaction_read_only': readonly, 'universe_as_of': payload.get('universe_as_of'),
                      'keys': sorted(payload), 'member_count':len(members),
                      'unclassified':[ {k:row.get(k) for k in ('code','name','cik','sector','market_cap_rank')}
                                       for row in members if not sector_etf_for_cik(row.get('cik'))],
                      'stored_daily_snapshot': stored_summary, 'database_activity': activity, 'collector_process': proc, 'writes':0,'notifications_sent':0}, ensure_ascii=False,default=str))
    db.rollback()
