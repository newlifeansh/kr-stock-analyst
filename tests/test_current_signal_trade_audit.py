from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from scripts.audit_current_signal_trades import reconstruct_trades,compare_trades,benchmark_minutes
from app.services.us_hybrid_signals import US_HYBRID_VERSION

BASE=datetime(2026,10,13,14,tzinfo=timezone.utc)

def event(side,minute,price,**extra):
    return {'event_id':f'A:{side}:{minute}','code':'A','side':side,'observed_at':(BASE+timedelta(minutes=minute)).isoformat(),
            'price':price,'strategy_version':US_HYBRID_VERSION,'intraday_execution_verified':True,**extra}

def events():
    return [event('buy',0,100),event('partial_sell',1,103,sell_fraction_original=.5,state_after='partially_exited'),
            event('sell',2,105,sell_fraction_original=.5,state_after='exited',return_rate=4),event('buy',3,200)]

def test_trade_audit_pairs_reentry_and_original_exit_weights_without_mutation():
    source=events();original=deepcopy(source)
    closed,opened=reconstruct_trades(source+[source[0]])
    assert source==original and len(closed)==1 and len(opened)==1
    assert closed[0]['entry_price']==100 and opened[0]['entry_price']==200
    prices={int((BASE+timedelta(minutes=i)).timestamp()):Decimal(p) for i,p in enumerate([100,102,106])}
    row=compare_trades(closed,{'SPY':prices})[0]['benchmarks']['SPY']
    assert row['same_holding_period_return']==6
    assert row['same_exit_weights_return']==4
    assert row['excess_same_exit_weights_pp']==0

def test_trade_audit_never_fills_missing_minutes_or_unreviewed_splits():
    closed,_=reconstruct_trades(events())
    prices={int(BASE.timestamp()):Decimal(100),int(BASE.timestamp()+120):Decimal(106)}
    assert compare_trades(closed,{'SPY':prices})[0]['benchmarks']['SPY']['state']=='missing_exact_minute'
    assert compare_trades(closed,{'SPY':prices},split_events={'SPY':[int(BASE.timestamp()+60)]})[0]['benchmarks']['SPY']['state']=='corporate_action_review'

def test_trade_audit_rejects_incomplete_or_conflicting_observed_ledger():
    for fault in ('entry_missing','return_mismatch','unverified','duplicate_conflict','over_exit'):
        data=events()
        if fault=='entry_missing':data=data[1:]
        if fault=='return_mismatch':data[2]['return_rate']=5
        if fault=='unverified':data[0]['intraday_execution_verified']=False
        if fault=='duplicate_conflict':data.append({**data[0],'price':999})
        if fault=='over_exit':data[2]['sell_fraction_original']=1
        with pytest.raises(ValueError):reconstruct_trades(data)

def test_trade_audit_benchmark_requires_identity_valid_closed_regular_minute():
    raw={'meta':{'symbol':'SPY','currency':'USD','instrumentType':'ETF'},'timestamp':[int(BASE.timestamp())],
         'indicators':{'quote':[{'open':[100],'high':[101],'low':[99],'close':[100],'volume':[1]}]}}
    assert benchmark_minutes('SPY',raw,as_of=BASE+timedelta(seconds=59))=={}
    assert benchmark_minutes('SPY',raw,as_of=BASE+timedelta(minutes=1))=={int(BASE.timestamp()):100}
    raw['meta']['symbol']='QQQ'
    with pytest.raises(ValueError):benchmark_minutes('SPY',raw,as_of=BASE+timedelta(minutes=1))
