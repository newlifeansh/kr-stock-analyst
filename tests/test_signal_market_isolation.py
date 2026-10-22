"""Market selection must bind signal returns, evidence, and scan counts together."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_signal_market_metrics_follow_selected_market_without_cross_market_fallback():
    source = (ROOT / 'app/static/dashboard/app.js').read_text()
    helpers = source[source.index('function aiSignalMarketMetrics('):source.index('function commitAiSignalSnapshot(')]
    fetch = source[source.index('async function fetchMarketAiSignals('):source.index('async function fetchHomeWatchlistAiSignals(')]
    script = r'''
const assert = require('node:assert/strict');
let IS_US_ONLY_PRODUCT = false, isUsHubContext = false;
const state = {view: 'ai-signals', marketScope: 'us'};
const AI_SIGNAL_HISTORY_DAYS = 90, PAGE_ENTRY_MINUTE_MS = 60000, AI_SIGNAL_REQUEST_TIMEOUT_MS = 20000;
let calls = [], failKr = false;
const kr = {status: 'ready', universe_count: 159, current_universe_count: 150,
  execution_replay_unverified_count: 17,
  performance_summary: {windows: {'30d': {average_return: -0.84}},
    completed_trade_items: [{code: '066570', market_scope: 'kr', return_rate: 5.07}]},
  entry_safety_guard: {active: true}, filter_forward_comparison: {version: 'kr-only'},
  items: [{code: '000100', market_scope: 'kr', is_preliminary: true}]};
const us = {status: 'ready', universe_count: 100,
  performance_summary: {windows: {'30d': {average_return: 4.13}},
    completed_trade_items: [{code: 'LLY', market_scope: 'us', return_rate: 4.19}]},
  items: [{code: 'AMZN', market_scope: 'us', is_preliminary: true}]};
async function fetchJsonCached(url) {
  calls.push(url);
  if (url.startsWith('/market/') && failKr) throw new Error('KR unavailable');
  return structuredClone(url.startsWith('/us/') ? us : kr);
}
function isAiSignalMarketUpdating(status) {return status !== 'ready';}
function aiSignalRevisionFromPayload() {return 1;}
function tagMarketItems(items = [], scope) {return items.map(item => ({...item, market_scope: scope}));}
function marketScopeForItem(item) {return item.market_scope;}
function canonicalUsPayloadCanCompose() {return true;}
function failClosedUsEntryPendingItems(items) {return items;}
function entryPendingItemCount(items) {return items.filter(item => item.is_preliminary).length;}
async function delay() {}
'''
    script += helpers + fetch + r'''
(async () => {
  // A domestic product ignores a stray US query/state and never requests US data.
  let payload = await fetchMarketAiSignals();
  assert.equal(calls.length, 1);
  assert.ok(calls[0].startsWith('/market/'));
  state.aiSignalMarketMetricsByScope = payload.market_metrics_by_scope;
  applyAiSignalMarketMetrics();
  assert.equal(state.aiSignalPerformanceSummary.windows['30d'].average_return, -0.84);
  assert.equal(state.aiSignalUniverseCount, 150);
  assert.deepEqual(payload.items.map(x => x.code), ['000100']);

  // The unified shell keeps both immutable frames, but displays only one market.
  isUsHubContext = true; state.marketScope = 'kr'; calls = [];
  payload = await fetchMarketAiSignals();
  assert.equal(calls.length, 2);
  state.aiSignalMarketMetricsByScope = payload.market_metrics_by_scope;
  for (const scope of ['kr', 'us', 'kr']) {
    state.marketScope = scope;
    applyAiSignalMarketMetrics();
    assert.equal(state.aiSignalPerformanceSummary.windows['30d'].average_return, scope === 'kr' ? -0.84 : 4.13);
    assert.equal(state.aiSignalUniverseCount, scope === 'kr' ? 150 : 100);
    assert.equal(state.aiSignalUnverifiedCount, scope === 'kr' ? 17 : 0);
    assert.equal(state.aiSignalEntrySafetyGuard?.active ?? false, scope === 'kr');
    assert.equal(state.aiSignalFilterForwardComparison?.version ?? null, scope === 'kr' ? 'kr-only' : null);
    assert.ok(state.aiSignalPerformanceSummary.completed_trade_items.every(x => x.market_scope === scope));
  }
  // Loss of one market must not substitute the other market's positive performance.
  failKr = true;
  payload = await fetchMarketAiSignals();
  state.aiSignalMarketMetricsByScope = payload.market_metrics_by_scope;
  applyAiSignalMarketMetrics();
  assert.equal(state.aiSignalPerformanceSummary, null);
  assert.equal(state.aiSignalUniverseCount, 0);
  assert.equal(state.aiSignalEntrySafetyGuard, null);

  state.aiSignalMarketMetricsByScope = {kr: aiSignalMarketMetrics(us)};
  applyAiSignalMarketMetrics();
  assert.equal(state.aiSignalPerformanceSummary, null);
  state.aiSignalMarketMetricsByScope = {kr: {performance_summary: {market_scope: 'us', windows: {}}}};
  applyAiSignalMarketMetrics();
  assert.equal(state.aiSignalPerformanceSummary, null);

  IS_US_ONLY_PRODUCT = true; state.marketScope = 'us'; calls = [];
  payload = await fetchMarketAiSignals();
  assert.equal(calls.length, 1);
  assert.ok(calls[0].startsWith('/us/'));
  state.aiSignalMarketMetricsByScope = payload.market_metrics_by_scope;
  applyAiSignalMarketMetrics();
  assert.equal(state.aiSignalPerformanceSummary.windows['30d'].average_return, 4.13);
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)


def test_signal_snapshot_signature_tracks_both_markets_performance_changes():
    source = (ROOT / 'app/static/dashboard/app.js').read_text()
    signature = source[source.index('function aiSignalSnapshotSignature('):source.index('function createMarketBadge(')]
    script = "const assert = require('node:assert/strict'); function aiSignalRevisionFromPayload(){return 1;}\n" + signature + r'''
const payload = {market_scopes_received: ['kr', 'us'], market_metrics_by_scope: {
  kr: {performance_summary: {windows: {'30d': {average_return: -0.84}}}},
  us: {performance_summary: {windows: {'30d': {average_return: 4.13}}}},
}};
const before = aiSignalSnapshotSignature([], payload);
payload.market_metrics_by_scope.us.performance_summary.windows['30d'].average_return = 2.07;
assert.notEqual(aiSignalSnapshotSignature([], payload), before);
'''
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
