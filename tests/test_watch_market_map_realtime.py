"""Focused production-JS runtime and browser coverage for home bubble quotes."""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/static/dashboard/app.js'


def runtime_source():
    source = SOURCE.read_text()

    def block(start, end):
        return source[source.index(start):source.index(end, source.index(start))]

    return '\n'.join([
        block('const WATCH_MARKET_MAP_SESSIONS', 'const STOCK_ETF_NAME_PREFIXES'),
        block('function previousCloseFromQuote(', 'function carryForwardLiveQuoteToDashboard('),
        block('const QUOTE_STREAM_SCOPE_PRIORITIES', 'function setLiveCellTone('),
        block('function watchMarketMapMarketCap(', 'function watchPreOpenSummary('),
        r'''
const state = {
  view: 'home', activeWatchGroup: 'default', watchMarketMapMarketScope: 'kr',
  watchMarketMapResults: [], watchMarketMapIntradayByKey: new Map(),
  watchMarketMapQuoteRenderTimer: null, watchMarketMapTimelineRenderFrame: null,
  watchMarketMapTimelineMinutes: null, watchMarketMapTimelineLatestMinutes: null,
  watchMarketMapMotionGeneration: 0, homeWatchMarketMapLoadSequence: 0,
  watchMarketMapIntradayLoadSequence: 0, watchMarketMapTimelineLoading: false,
  quoteStreamScopes: new Map(), quoteStreamLatestByCode: new Map(),
  quoteStreamSubscribedCodes: new Set(), quoteStreamRejectedCodes: new Set(),
  quoteStreamCodeLimit: 64, quoteStreamEpoch: 0,
};
const dashboardLiveQuoteTimes = new WeakMap();
const dashboardLiveQuoteDeltas = new WeakMap();
const QUOTE_STREAM_DEFAULT_CODE_LIMIT = 64;
const QUOTE_STREAM_WATCHDOG_MS = 10000;
const AI_SIGNAL_REALTIME_QUOTE_MAX_AGE_MS = 120000;
const AI_SIGNAL_DELAYED_QUOTE_MAX_AGE_MS = 120000;
const PAGE_ENTRY_MINUTE_MS = 60000;
let elements = {watchMarketMapMarketButtons: []};
let items = [{code: '005930', name: '삼성전자', market_scope: 'kr'},
             {code: '000660', name: 'SK하이닉스', market_scope: 'kr'},
             {code: 'NVDA', name: 'NVIDIA', market_scope: 'us'}];
let fetches = [];
function toNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value); return Number.isFinite(n) ? n : null;
}
function marketScopeForItem(item) { return item?.market_scope || 'kr'; }
function activeWatchlistGroupName() { return '기본그룹'; }
function watchlistItemsForGroup() { return items; }
function pageEntryTtlMs() { return 60000; }
function marketStockDashboardUrl(code) { return `/stocks/${code}/dashboard`; }
function mapWithConcurrency(entries, _limit, callback) { return Promise.all(entries.map(callback)); }
function rejectAfter() { return new Promise(() => {}); }
function koreaExtendedQuoteLive() { return true; }
function aiSignalQuoteUsesActiveSession() { return true; }
function renderAiSignalLiveStatus() {}
function scheduleQuoteStreamFallback() {}
function handleAiSignalRevisionFrame() {}
function socketUrl(path) { return 'ws://bubble.test' + path; }
function el(tag, className, text) {
  const node = document.createElement(tag); node.className = className;
  if (text !== undefined) node.textContent = text; return node;
}
function formatNumber(n) { return String(n); }
function formatPercent(n) { return n === null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}%`; }
function formatStockPrice(n) { return String(n); }
function viewStockUrl(code) { return `/dashboard?view=stock&code=${code}`; }
function fixtureDashboard(code) {
  return {as_of: '2026-10-19T10:00:00+09:00', quote: {
    price: 101, change_value: 1, change_rate: 1, market_cap: code === '005930' ? 1000000 : 500000,
    market_session: 'integrated_regular', trade_date: '2026-10-19',
  }};
}
async function fetchJsonCached(path) {
  fetches.push(path);
  return path.includes('intraday') ? {
    trade_date: '20261019', reference_price: 100,
    points: [{trade_time: '090000', price: 99}, {trade_time: '100000', price: 101}],
  } : fixtureDashboard(path.split('/')[2]);
}
function frame(code, price, seq, time = '10:01:00') {
  return {type: 'quote', code, source: 'kis_realtime', sequence: seq,
    as_of: `2026-10-19T${time}+09:00`, quote: {
      price, change_value: price - 100, change_rate: price - 100,
      market_session: 'integrated_regular', trade_date: '2026-10-19',
    }};
}
''',
    ])


@pytest.mark.qa_gate
def test_home_bubbles_subscribe_update_and_preserve_scrubbed_history():
    script = r'''
const assert = require('node:assert/strict');
const RealDate = Date;
global.Date = class extends RealDate {
  constructor(...args) { super(...(args.length ? args : ['2026-10-19T10:02:00+09:00'])); }
  static now() { return new RealDate('2026-10-19T10:02:00+09:00').getTime(); }
};
const timers = new Map(); let timerId = 0;
global.document = {hidden: false};
global.navigator = {onLine: true};
global.window = {
  setTimeout(callback) { const id = ++timerId; timers.set(id, callback); return id; },
  clearTimeout(id) { timers.delete(id); },
};
''' + runtime_source() + r'''
let renders = 0;
function syncQuoteStreamSubscriptions() {}
function renderWatchMarketMap() { renders++; }
function scheduleWatchMarketMapTimelineRender() { renders++; }
function displayed() {
  const entries = watchMarketMapEntries(); const timeline = watchMarketMapTimelineRange(entries);
  return {timeline, values: watchMarketMapEntriesAtTimeline(entries, timeline).map(e => e.marketMapSnapshot)};
}
(async () => {
  await loadHomeWatchMarketMap();
  assert.deepEqual([...state.quoteStreamScopes.get('home-watch-map').keys()], ['005930', '000660']);
  assert.equal(displayed().values[0].price, 101);
  const requestsBeforeTicks = fetches.length;
  const rendersBeforeTicks = renders;
  dispatchQuoteStreamPayload(frame('005930', 103, 10));
  dispatchQuoteStreamPayload(frame('005930', 105, 11));
  dispatchQuoteStreamPayload(frame('000660', 97, 12));
  assert.equal(timers.size, 1, 'one render timer for all ticks in the group');
  assert.equal(renders, rendersBeforeTicks);
  const timer = state.watchMarketMapQuoteRenderTimer;
  timers.get(timer)(); timers.delete(timer);
  assert.equal(renders, rendersBeforeTicks + 1);
  assert.equal(fetches.length, requestsBeforeTicks, 'ticks never refetch dashboards');
  assert.deepEqual(displayed().values.map(v => v.price), [105, 97]);
  assert.equal(state.watchMarketMapResults[0].dashboard.quote.market_cap, 1000000);
  dispatchQuoteStreamPayload(frame('005930', 90, 9, '10:00:00'));
  assert.equal(displayed().values[0].price, 105, 'old/duplicate sequence is rejected');
  const track = {value: '540'};
  handleWatchMarketMapTimelineInput({currentTarget: track});
  dispatchQuoteStreamPayload(frame('005930', 106, 13, '10:01:30'));
  assert.equal(displayed().values[0].price, 99, 'history is not overwritten by live');
  track.value = String(state.watchMarketMapTimelineLatestMinutes);
  handleWatchMarketMapTimelineInput({currentTarget: track});
  assert.equal(state.watchMarketMapTimelineMinutes, null);
  dispatchQuoteStreamPayload(frame('005930', 108, 14, '10:02:00'));
  assert.equal(displayed().timeline.selectedMinutes, 602);
  assert.equal(displayed().values[0].price, 108);
  state.watchMarketMapIntradayByKey.get('kr:005930').points.forEach(p => p.dateKey = '2026-10-16');
  state.watchMarketMapIntradayByKey.get('kr:000660').points.forEach(p => p.dateKey = '2026-10-16');
  assert.equal(displayed().timeline.dateKey, '2026-10-19', 'new session cannot keep Friday timeline');
  // Use a premarket quote for the session hint, then preserve regular history.
  state.watchMarketMapResults.forEach(e => {
    e.dashboard.as_of = '2026-10-19T08:10:00+09:00';
    e.dashboard.quote.market_session = 'integrated_pre_market';
  });
  const preopen = watchMarketMapTimelineRange(watchMarketMapEntries(), 'kr', new RealDate('2026-10-19T08:10:00+09:00'));
  assert.equal(preopen.sessionState, 'preopen');
  assert.equal(preopen.dateKey, '2026-10-16');
  assert.equal(watchMarketMapEntrySnapshot(watchMarketMapEntries()[0], preopen).source, 'intraday');
  items = [items[1]];
  await loadHomeWatchMarketMap();
  assert.deepEqual([...state.quoteStreamScopes.get('home-watch-map').keys()], ['000660']);
  const priceBeforeRemovedTick = state.watchMarketMapResults[0].dashboard.quote.price;
  dispatchQuoteStreamPayload(frame('005930', 150, 15));
  assert.equal(state.watchMarketMapResults[0].dashboard.quote.price, priceBeforeRemovedTick);
  document.hidden = true;
  connectHomeWatchMarketMapQuoteStreams();
  assert.equal(state.quoteStreamScopes.has('home-watch-map'), false);
  assert.equal(state.watchMarketMapQuoteRenderTimer, null);
  document.hidden = false;
  state.view = 'portfolio'; connectHomeWatchMarketMapQuoteStreams();
  assert.equal(state.quoteStreamScopes.has('home-watch-map'), false);
  state.view = 'home'; state.watchMarketMapMarketScope = 'us'; connectHomeWatchMarketMapQuoteStreams();
  assert.equal(state.quoteStreamScopes.has('home-watch-map'), false);
  state.watchMarketMapMarketScope = 'kr'; items = []; await loadHomeWatchMarketMap();
  assert.equal(state.quoteStreamScopes.has('home-watch-map'), false);
  console.log('passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
'''
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'passed'


@pytest.mark.qa_gate
def test_home_bubble_stream_lifecycle_hooks():
    source = SOURCE.read_text()
    for start, end in [
        ('async function logoutWatchlistIdentity(', 'function watchlist'),
        ('function setView(', 'function '),
        ('document.addEventListener("visibilitychange"', 'refreshMarketThreadElapsedTimes();'),
    ]:
        section = source.split(start, 1)[1]
        if start == 'function setView(':
            section = section.split('\nfunction ', 1)[0]
        else:
            section = section.split(end, 1)[0]
        assert 'closeHomeWatchMarketMapQuoteStreams();' in section


@pytest.mark.qa_e2e
@pytest.mark.skipif(os.environ.get('RUN_BUBBLE_E2E') != '1', reason='opt-in browser QA')
def test_home_bubbles_websocket_browser():
    from playwright.sync_api import sync_playwright

    shell = (ROOT / 'app/static/dashboard/index.html').read_text()
    chart = re.search(r'<section[^>]+id="watch-market-map".*?</section>', shell, re.S).group()
    sheet = re.search(r'<dialog[^>]+id="watch-market-map-sheet".*?</dialog>', shell, re.S).group()
    styles = (ROOT / 'app/static/dashboard/styles.css').read_text()
    html = f'<html><head><meta charset="utf-8"><style>{styles}</style></head><body data-view="home"><div id="home-view">{chart}{sheet}</div></body></html>'
    output = ROOT / 'artifacts/qa-data-signal/bubble-realtime'
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
        page.clock.set_fixed_time('2026-10-19T01:02:00Z')
        page.route('http://bubble.test/**', lambda route: route.fulfill(body=html, content_type='text/html'))
        sockets, subscriptions, errors = [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def connect(socket):
            sockets.append(socket)

            def receive(message):
                payload = json.loads(message)
                subscriptions.append(payload['codes'])
                socket.send(json.dumps({'type': 'subscribed', 'codes': payload['codes']}))
            socket.on_message(receive)

        page.route_web_socket('ws://bubble.test/ws/quotes', connect)
        page.goto('http://bubble.test/')
        page.add_script_tag(content=runtime_source() + r'''
for (const node of document.querySelectorAll('[id^="watch-market-map"]')) {
  const key = node.id.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
  elements[key] = node;
}
elements.watchMarketMapStage.style.height = '360px';
elements.watchMarketMapTimelineTrack.addEventListener('input', handleWatchMarketMapTimelineInput);
void loadHomeWatchMarketMap();
''')
        tile = page.locator('[data-code="005930"].watch-market-map-tile')
        page.wait_for_function("document.querySelector('[data-code=\"005930\"]')?.dataset.changeRate === '1'")
        page.wait_for_function("state.quoteStreamSubscribedCodes.has('005930')")
        assert set(subscriptions[-1]) == {'005930', '000660'}
        quote_subscription = subscriptions[-1][:]
        initial_radius = float(tile.get_attribute('data-watch-bubble-radius'))

        def send(price, seq, time='10:01:00'):
            sockets[-1].send(json.dumps(page.evaluate('args => frame(...args)', ['005930', price, seq, time])))

        send(95, 10)
        page.wait_for_function("document.querySelector('[data-code=\"005930\"]')?.dataset.changeRate === '-5'")
        assert tile.inner_text().endswith('-5.00%')
        assert 'is-negative' in tile.get_attribute('class')
        assert float(tile.get_attribute('data-watch-bubble-radius')) > initial_radius
        assert '하락 1' in page.locator('#watch-market-map-legend').inner_text()
        page.locator('#watch-market-map-timeline-track').fill('540')
        page.wait_for_function("document.querySelector('#watch-market-map-timeline')?.dataset.selection === 'historical'")
        historical = tile.inner_text()
        send(106, 11, '10:01:30')
        page.wait_for_function("state.watchMarketMapResults[0].dashboard.quote.price === 106 && state.watchMarketMapQuoteRenderTimer === null")
        assert tile.inner_text() == historical
        page.locator('#watch-market-map-timeline-track').fill('601')
        send(108, 12, '10:02:00')
        page.wait_for_function("document.querySelector('[data-code=\"005930\"]')?.dataset.changeRate === '8'")
        assert page.locator('#watch-market-map-timeline-track').input_value() == '602'
        assert 'is-positive' in tile.get_attribute('class')
        send(90, 9, '10:00:00')
        page.wait_for_timeout(1100)
        assert tile.inner_text().endswith('+8.00%')
        page.locator('#watch-market-map').screenshot(path=str(output / 'e2e-latest.png'))
        page.evaluate("state.view = 'portfolio'; closeHomeWatchMarketMapQuoteStreams()")
        assert not page.evaluate("state.quoteStreamScopes.has('home-watch-map')")
        assert not errors, errors
        (output / 'e2e.json').write_text(json.dumps({
            'mode': 'e2e', 'case_id': 'SIG-UI-025', 'status': 'pass',
            'scope': 'local production JS component; mocked upstream WebSocket',
            'subscription_codes': quote_subscription,
            'checks': ['subscription', 'bubble text/color/radius/legend', 'historical selection',
                       'latest follows next minute', 'out-of-order rejection', 'unsubscribe'],
        }, ensure_ascii=False, indent=2) + '\n')
        browser.close()
