from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess

import pytest

from app.services import us_market as market

NOW = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("offset,expected", [(0, "recent"), (30, "recent"), (31, "delayed"), (1800, "delayed"), (-6, "future"), (None, "unknown")])
def test_us_quote_source_age_not_request_time(monkeypatch, offset, expected):
    monkeypatch.setattr(market, "_us_market_session", lambda *a: dict(session="regular", label="정규장", is_live=True, local_time=NOW))
    raw = dict(regularMarketPrice=100, regularMarketPreviousClose=90)
    if offset is not None:
        raw["regularMarketTime"] = (NOW - timedelta(seconds=offset)).timestamp()
    monkeypatch.setattr(market, "fetch_us_quote_batch", lambda *a, **kw: {"NVDA": raw})
    item = market.us_quote_snapshots(["NVDA"], refresh=True, now=NOW)["items"][0]
    assert item["quote"]["freshness"] == expected
    assert item["quote"]["is_live"] == (expected == "recent")
    if offset is None:
        assert item["observed_at"] is None and item["as_of"] is None
        assert item["quote"]["trade_date"] is None


def test_us_quote_cache_rechecks_age_without_faking_timestamp(monkeypatch):
    monkeypatch.setattr(market, "_us_market_session", lambda *a: dict(session="regular", label="정규장", is_live=True, local_time=NOW))
    monkeypatch.setattr(market, "fetch_us_quote_batch", lambda *a, **kw: {"NVDA": dict(regularMarketPrice=100, regularMarketTime=NOW.timestamp())})
    first = market.us_quote_snapshots(["NVDA"], refresh=True, now=NOW)
    second = market.us_quote_snapshots(["NVDA"], now=NOW+timedelta(seconds=40))
    assert second["items"][0]["quote"]["freshness"] == "delayed"
    assert second["items"][0]["observed_at"] == NOW
    assert first["items"][0]["quote"]["freshness"] == "recent"
    assert market.us_quote_freshness(NOW, False, NOW+timedelta(days=1))["freshness"] == "closed"


def js_source():
    source = Path("app/static/dashboard/app.js").read_text()
    return source[source.index("const usVisibleQuotes ="):source.index("function closeQuoteStream()")]


def run_js(body):
    script = """
const assert = require('node:assert/strict');
const AI_SIGNAL_US_QUOTE_MAX_AGE_MS=30000, AI_SIGNAL_US_QUOTE_ACTIVE_REFRESH_MS=15000;
let timers=[], intervals=[], calls=[];
const document={hidden:false};
const window={setTimeout:(fn,delay)=>{timers.push({fn,delay});return timers.length},clearTimeout:()=>{},
setInterval:(fn,delay)=>{intervals.push({fn,delay});return intervals.length},clearInterval:()=>{}};
function quoteStreamPayloadHasUsablePrice(p){return p.type==='quote' && Number(p.quote?.price)>0;}
function frame(code,stamp=Date.now(),price=100){return {type:'quote',code,observed_at:new Date(stamp).toISOString(),source:'yahoo_quote_batch',quote:{price,market_session:'regular',observed_at:new Date(stamp).toISOString()}};}
let fetchJsonCached=async url=>{calls.push(url);return {items:decodeURIComponent(url.split('=')[1]).split(',').map(code=>frame(code))}};
""" + js_source() + "\n(async()=>{" + body + "})().catch(e=>{console.error(e);process.exit(1)});"
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_us_visible_quotes_batch_all_scopes_and_stop_when_hidden():
    run_js("""
let updates=0;
for(let i=0;i<45;i++)setUsVisibleQuote('watchlist','S'+i,{onQuote:()=>updates++});
setUsVisibleQuote('detail','S0',{onQuote:()=>updates++});
await pollUsVisibleQuotes(usVisibleQuotes.generation);
assert.equal(calls.length,3);assert.equal(updates,46);
assert(calls.every(u=>decodeURIComponent(u.split('=')[1]).split(',').length<=20));
assert.equal(timers.at(-1).delay,15000);
document.hidden=true;await pollUsVisibleQuotes(usVisibleQuotes.generation);assert.equal(calls.length,3);
clearUsVisibleQuotes('detail');clearUsVisibleQuotes('watchlist');assert.equal(usVisibleQuotes.scopes.size,0);
assert.equal(usVisibleQuotes.frames.size,0);
""")


def test_us_visible_quotes_navigation_generation_and_old_future_frames():
    run_js("""
let updates=0,resolve;
setUsVisibleQuote('detail','NVDA',{onQuote:()=>updates++});
fetchJsonCached=()=>new Promise(r=>resolve=r);
const pending=pollUsVisibleQuotes(usVisibleQuotes.generation);
clearUsVisibleQuotes('detail');setUsVisibleQuote('detail','AAPL',{onQuote:()=>updates++});
resolve({items:[frame('NVDA')]});await pending;assert.equal(updates,0);
fetchJsonCached=async()=>({items:[frame('AAPL')]});await pollUsVisibleQuotes(usVisibleQuotes.generation);assert.equal(updates,1);
fetchJsonCached=async()=>({items:[frame('AAPL',Date.now()-20000)]});await pollUsVisibleQuotes(usVisibleQuotes.generation);assert.equal(updates,1);
fetchJsonCached=async()=>({items:[frame('AAPL',Date.now()+60000)]});await pollUsVisibleQuotes(usVisibleQuotes.generation);assert.equal(updates,1);
fetchJsonCached=async()=>({items:[frame('AAPL')]});await pollUsVisibleQuotes(usVisibleQuotes.generation);assert.equal(updates,2);
""")


def test_us_visible_quotes_failure_staleness_missing_time_and_recovery():
    run_js("""
const now=Date.now();
assert.equal(usQuoteBasis(frame('NVDA',now-1800000),now).state,'checking');
assert.equal(usQuoteBasis({quote:{is_live:true}},now).state,'checking');
assert.equal(usQuoteBasis(frame('NVDA',now+60000),now).state,'checking');
assert.equal(usQuoteBasis(frame('NVDA',now-1000),now).state,'recent');
assert(usQuoteBasis(frame('NVDA',now),now).time.includes('KST'));
let states=[],updates=0;
setUsVisibleQuote('detail','NVDA',{onState:s=>states.push(s),onQuote:()=>updates++});
await pollUsVisibleQuotes(usVisibleQuotes.generation);assert.equal(updates,1);
fetchJsonCached=async()=>{throw Error('offline')};await pollUsVisibleQuotes(usVisibleQuotes.generation);
assert.equal(states.at(-1).state,'offline');assert.equal(updates,1);
fetchJsonCached=async()=>({items:[]});await pollUsVisibleQuotes(usVisibleQuotes.generation);assert.equal(states.at(-1).state,'offline');
fetchJsonCached=async()=>({items:[frame('NVDA')]});await pollUsVisibleQuotes(usVisibleQuotes.generation);assert.equal(states.at(-1).state,'recent');assert.equal(updates,2);
""")


def test_us_quote_detail_watchlist_visibility_and_signal_wiring():
    source = Path("app/static/dashboard/app.js").read_text()
    assert 'setUsVisibleQuote("detail", code,' in source
    assert 'setUsVisibleQuote("watchlist", code,' in source
    assert 'clearUsVisibleQuotes("detail")' in source
    assert 'clearUsVisibleQuotes("watchlist")' in source
    assert 'state.view === "stock" && state.currentStock && !stockDashboardIsUs()' not in source
    assert 'return usQuoteBasis(payload, now, fallbackActive).state;' in source
    assert 'AI_SIGNAL_US_QUOTE_MAX_AGE_MS = 30 * 60_000' not in source
    assert 'setText(elements.stockMarketStatusLabel, basis.time)' in source
    assert 'label.dataset.freshness = basis.state' in source
    render = source[source.index('function render(data'):source.index('async function resolveStock(')]
    assert 'renderUsStockResearch(data);\n    connectQuoteStream(state.currentStock);' in render
    assert 'time: usQuoteBasis({ quote: state.currentDashboard?.quote }).time' in source
    toss = Path('app/static/staging/toss-ia.js').read_text()
    visible = toss.split('const syncStockOrderability = () => {', 1)[1].split('const syncStockChangeContext', 1)[0]
    us = visible.split('if (stagingStockIsUsd()) {', 1)[1].split('return;', 1)[0]
    assert 'marketStatus.dataset.quoteLabel' in us
    assert 'detail.hidden = false' in us
    assert '실시간 주문 가능' not in us and '미국 동부시간' not in us
    from app.product_shell import render_dashboard_product_shell
    shell = Path('app/static/dashboard/index.html').read_text()
    us_html = render_dashboard_product_shell(shell, market_universe='us', client_version='20261003us133')
    kr_html = render_dashboard_product_shell(shell, market_universe='kr', client_version='kr-preserved')
    assert '/assets/staging/toss-ia.js?v=20261003us133' in us_html
    assert '/assets/staging/toss-ia.js?v=20260921-domestic-market-v116' in kr_html


def test_us_quote_candidate_workflow_staging_only():
    workflow = Path(".github/workflows/deploy-staging-production.yml").read_text()
    job = workflow.split("  intraday_shadow_staging:",1)[1].split("  validate_request:",1)[0]
    assert 'qa_us_quote_freshness.py' in job
    assert '--environment production' not in job
    assert 'needs: [validate_request, gate, build_image]' in job
