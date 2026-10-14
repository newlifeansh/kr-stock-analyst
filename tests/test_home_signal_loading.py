import json
import subprocess
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "app/static/dashboard/app.js"


def run_home_loader(scenario: str) -> dict:
    source = SOURCE.read_text()
    loader = source[source.index("async function fetchHomeWatchlistAiSignals(") : source.index("function scheduleAiSignalRevisionReconcile(")]
    status = source[source.index("function showHomeMarketSignalStatus(") : source.index("function compactHoldingSignalSummary(")]
    script = """
const assert = require('node:assert/strict');
const timers = new Map();
let timerId = 0;
const window = {
  setTimeout(fn, ms) { timers.set(++timerId, {fn, ms}); return timerId; },
  clearTimeout(id) { timers.delete(id); },
};
function node() {
  return {
    textContent: '', innerHTML: '', rows: [], attrs: {},
    classList: {loading: false, remove() {this.loading = false;}},
    querySelector() {return this.rows.length ? this.rows[0] : null;},
    replaceChildren(...rows) {this.rows = rows; this.textContent = rows.map(r => r.textContent).join('');},
    setAttribute(k, v) {this.attrs[k] = v;},
    removeAttribute(k) {delete this.attrs[k];},
  };
}
const elements = {homeAiSignalsList: node(), homeAiSignalsMeta: node(), homeMarketSignalWindow: node()};
const state = {
  view: 'home', watchlistId: 'user-a', aiSignalItems: [], marketScope: 'kr',
  homeAiSignalsRequestId: 0, aiSignalLoadSequence: 0, aiSignalSnapshotReceivedAt: 0,
};
const PAGE_ENTRY_MINUTE_MS = 60000, AI_SIGNAL_HISTORY_DAYS = 30, AI_SIGNAL_REQUEST_TIMEOUT_MS = 10000;
const isUsHubContext = false;
const personal = [];
const renders = [];
const calls = [];
let resolveWatchlist;
const watchlistPending = new Promise(resolve => {resolveWatchlist = resolve;});
let market = {status: 'ready', items: [{code: '005930', signal_scope: 'market'}]};
let marketError = false;
async function fetchJsonCached(url, options) {calls.push({url, ...options}); return watchlistPending;}
async function fetchMarketAiSignals() {if (marketError) throw new Error('offline'); return market;}
function combineAiSignalPayloads(watchlist, market) {
  return {...market, market_status: market.status, watchlist_items: watchlist.items};
}
function isAiSignalMarketUpdating() {return ['preparing', 'refreshing'].includes(state.aiSignalMarketStatus);}
function readCachedHomeAiSignals() {return null;}
function writeCachedHomeAiSignals() {}
function stopHomeMarketSignalTicker() {}
function showHomeMarketSignalLoading() {elements.homeMarketSignalWindow.classList.loading = true;}
function renderPendingHomeAiSignals() {showHomeMarketSignalLoading();}
function normalizedAiSignalItems(items) {return items;}
function renderHomeAiResponse(items) {personal.push(items.map(i => i.code));}
function refreshAiSignalLiveRows() {}
function scheduleAiSignalRevisionReconcile() {}
function el(tag, cls, text) {return {...node(), textContent: text};}
function renderHomeAiSignals(payload, options = {}) {
  renders.push(payload.items.map(i => i.code));
  state.aiSignalItems = payload.items;
  state.aiSignalMarketStatus = payload.market_status;
  state.aiSignalSnapshotReceivedAt = options.receivedAt ?? 12345;
  state.aiSignalReconcilePending = false;
  elements.homeAiSignalsList.rows = payload.items;
  elements.homeMarketSignalWindow.classList.loading = false;
  elements.homeMarketSignalWindow.textContent = payload.items.length ? payload.items[0].code : '신호 없음';
  return true;
}
const flush = async () => {for (let i=0; i<20; i++) await Promise.resolve();};
""" + loader + status + "\n(async () => {\n" + scenario + "\n})().catch(e => {console.error(e); process.exit(1);});"
    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True, timeout=10)
    return json.loads(completed.stdout)


def test_home_market_signals_do_not_wait_for_personal_signals():
    result = run_home_loader("""
let finished = false;
loadHomeAiSignals().then(() => {finished = true;});
await flush();
assert.equal(finished, true, 'public market rendering waited for the personal API');
assert.equal(elements.homeMarketSignalWindow.textContent, '005930');
assert.equal(calls.length, 1, 'the watchlist should only be requested once');
assert.equal(calls[0].timeoutMs, 10000);
resolveWatchlist({items: [{code: '000660'}]});
await flush();
console.log(JSON.stringify({finished, renders, personal}));
""")
    assert result == {"finished": True, "renders": [["005930"]], "personal": [["000660"]]}


def test_home_late_personal_response_cannot_overwrite_new_identity_or_request():
    for invalidate in (
        "state.watchlistId = 'user-b';",
        "state.homeAiSignalsRequestId += 1;",
        "state.aiSignalLoadSequence += 1;",
        "state.view = 'ai-signals';",
    ):
        result = run_home_loader("""
await loadHomeAiSignals();
""" + invalidate + """
resolveWatchlist({items: [{code: '000660'}]});
await flush();
console.log(JSON.stringify({personal}));
""")
        assert result == {"personal": []}


def test_home_first_failure_and_exhausted_preparation_leave_loading_state():
    result = run_home_loader("""
marketError = true;
await loadHomeAiSignals();
assert.equal(elements.homeMarketSignalWindow.classList.loading, false);
assert.match(elements.homeMarketSignalWindow.textContent, /연결이 지연/);
assert.equal([...timers.values()].filter(t => t.ms === 3000).length, 1);
await loadHomeAiSignals({preparingRetry: 3});
assert.equal(timers.size, 0);
assert.equal(elements.homeMarketSignalWindow.classList.loading, false);
assert.match(elements.homeMarketSignalWindow.textContent, /불러오지 못/);
marketError = false;
market = {status: 'preparing', items: []};
await loadHomeAiSignals({preparingRetry: 3});
assert.equal(elements.homeMarketSignalWindow.classList.loading, false);
assert.match(elements.homeMarketSignalWindow.textContent, /준비하고/);
market = {status: 'ready', items: []};
await loadHomeAiSignals();
console.log(JSON.stringify({loading: elements.homeMarketSignalWindow.classList.loading, text: elements.homeMarketSignalWindow.textContent}));
""")
    assert result == {"loading": False, "text": "신호 없음"}


def test_home_failed_refresh_keeps_last_snapshot_age_and_recovers():
    result = run_home_loader("""
await loadHomeAiSignals();
state.aiSignalSnapshotReceivedAt = 100;
marketError = true;
await loadHomeAiSignals({restartTicker: true});
assert.equal(elements.homeMarketSignalWindow.textContent, '005930');
assert.equal(state.aiSignalSnapshotReceivedAt, 100);
assert.equal(state.aiSignalReconcilePending, true);
assert.match(elements.homeAiSignalsMeta.textContent, /마지막 확인 목록/);
marketError = false;
market = {status: 'ready', items: [{code: '000660'}]};
const retry = [...timers.values()].find(t => t.ms === 3000);
retry.fn();
await flush();
console.log(JSON.stringify({text: elements.homeMarketSignalWindow.textContent, pending: state.aiSignalReconcilePending}));
""")
    assert result == {"text": "000660", "pending": False}


def test_market_signal_request_timeout_aborts_hung_transport():
    source = SOURCE.read_text()
    cached = source[source.index("async function fetchJsonCached(") : source.index("function koreaClockParts(")]
    market = source[source.index("async function fetchMarketAiSignals(") : source.index("async function fetchHomeWatchlistAiSignals(")]
    script = """
const assert = require('node:assert/strict');
const state = {responseCache: new Map(), pendingRequests: new Map(), view: 'home', marketScope: 'kr'};
const window = {setTimeout(fn, ms) {assert.equal(ms, 10000); queueMicrotask(fn); return 1;}, clearTimeout() {}};
const AI_SIGNAL_REQUEST_TIMEOUT_MS = 10000, AI_SIGNAL_HISTORY_DAYS = 30, PAGE_ENTRY_MINUTE_MS = 60000;
const IS_US_ONLY_PRODUCT = false, isUsHubContext = false, UI_CACHE_TTL_MS = 60000;
const clonePayload = value => structuredClone(value);
const isUncachedKoreaMarketDataUrl = () => false;
let aborted = false;
const fetch = (url, {signal}) => new Promise((resolve, reject) => {
  signal.addEventListener('abort', () => {aborted = true; reject(new Error('timeout'));});
});
""" + cached + market + """
(async () => {
  await assert.rejects(fetchMarketAiSignals(), /timeout/);
  assert.equal(aborted, true);
  assert.equal(state.pendingRequests.size, 0);
})().catch(e => {console.error(e); process.exit(1);});
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True, timeout=10)
