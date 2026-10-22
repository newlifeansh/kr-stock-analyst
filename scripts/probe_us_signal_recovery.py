"""Export public signal evidence and missing sessions without database writes."""
import json
from datetime import datetime,timezone
from sqlalchemy import text
from app.db import SessionLocal
from app.services import us_position_lifecycle as us
from app.services.us_signal_universe import load_latest_us_signal_universe_snapshot
from app.services.us_market_calendar import recent_us_market_session_dates
from app.services.us_hybrid_signals import read_us_hybrid_state
now=datetime.now(timezone.utc)
with SessionLocal() as db:
 db.execute(text('SET TRANSACTION READ ONLY'))
 universe=load_latest_us_signal_universe_snapshot(db)
 ledger=read_us_hybrid_state(db)
 db.rollback()
members=universe['items']
symbols=sorted(set(['SPY','QQQ']+[m['code'] for m in members]+[us._sector_etf(m) for m in members]))
histories,errors=us._load_histories(symbols,us._history_loader)
bars={s:us.us_price_bars(r,now=now) for s,r in histories.items()}
from datetime import date
through=date.fromisoformat(str(universe['universe_as_of'])[:10])
expected=recent_us_market_session_dates(through,us.US_MIN_HISTORY_ROWS)
bad=[]
for symbol in symbols:
 values=bars.get(symbol,[])
 missing=sorted(set(expected)-{r.trade_date for r in values})
 if missing:
  bad.append({'code':symbol,'count':len(values),'last':str(values[-1].trade_date) if values else None,'missing':missing,
              'raw_missing':[vars(x) for x in histories.get(symbol,[]) if x.trade_date in missing]})
report={'as_of':now,'universe':universe,'histories_errors':errors,'bad_histories':bad,
        'hybrid_ledger':{k:ledger[k] for k in ('version','initialized_at','updated_at','revision','checksum','events','positions')},
        'benchmarks':{s:[vars(r) for r in histories.get(s,[]) if str(r.trade_date)>='2026-10-01'] for s in ('SPY','QQQ','XLV')},
        'writes':0,'notifications_sent':0}
print(json.dumps(report,ensure_ascii=False,default=str))
