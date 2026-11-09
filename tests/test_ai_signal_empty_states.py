import json
import subprocess
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "app/static/dashboard/app.js"


def _run_state_helpers(assertions: str) -> dict:
    source = SOURCE.read_text()
    helpers = source[
        source.index("function aiSignalPerformanceWindowState(") :
        source.index("function formatAiSignalRate(")
    ]
    script = """
const assert = require('node:assert/strict');
const toNumber = value => value === null || value === undefined || value === ''
  ? null
  : Number.isFinite(Number(value)) ? Number(value) : null;
const formatNumber = value => String(Number(value));
const isUsHubContext = false;
""" + helpers + "\n" + assertions
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(completed.stdout)


def test_zero_completed_trades_are_an_empty_sample_not_an_endless_loading_state():
    result = _run_state_helpers("""
const empty = aiSignalPerformanceWindowState({
  completed_trades: 0,
  average_return: null,
  sample_state: 'limited',
});
const limited = aiSignalPerformanceWindowState({
  completed_trades: 2,
  average_return: '1.25',
  sample_state: 'limited',
});
assert.deepEqual(empty, {
  completed: 0,
  average: null,
  empty: true,
  sameSample: false,
  statusState: 'empty',
  statusLabel: '표본 없음',
});
assert.equal(limited.empty, false);
assert.equal(limited.statusLabel, '참고 표본');
assert.equal(limited.average, 1.25);
console.log(JSON.stringify({empty, limited}));
""")

    assert result["empty"]["statusLabel"] == "표본 없음"
    assert result["limited"]["statusLabel"] == "참고 표본"


def test_candidate_scan_status_reports_zero_candidates_and_revalidation_separately():
    result = _run_state_helpers("""
const active = aiSignalCandidateScanView({
  universeCount: 150,
  buyCandidates: 0,
  sellCandidates: 0,
  unverifiedCount: 10,
  closed: false,
});
const healthy = aiSignalCandidateScanView({
  universeCount: 150,
  buyCandidates: 2,
  sellCandidates: 1,
  unverifiedCount: 0,
  closed: false,
});
assert.equal(active.state, 'delayed');
assert.equal(active.label, '시총 상위 150개 탐색 완료');
assert.equal(active.detail, '매수 후보 0개 · 매도 대기 0개 · 10개 종목 재검증 중');
assert.equal(healthy.state, 'realtime');
assert.equal(healthy.detail, '매수 후보 2개 · 매도 대기 1개 · 5분마다 다시 탐색해요');
console.log(JSON.stringify({active, healthy}));
""")

    assert result["active"]["state"] == "delayed"
    assert result["healthy"]["state"] == "realtime"


def test_us_signal_status_explains_stale_daily_setup_while_preserving_holdings():
    source = SOURCE.read_text()
    function_source = source[
        source.index("function aiSignalPageFreshnessView(") :
        source.index("function syncAiSignalFreshnessBadgeVisibility(")
    ]
    script = f"""
const assert = require('node:assert/strict');
const state = {{
  marketScope: 'us', aiSignalMarketMetricsByScope: {{ us: {{
    new_entries_allowed: false, universe_as_of: '2026-11-04',
    state_reason: '최근 완료된 미국 정규장 스냅샷 갱신을 기다리고 있습니다.',
  }} }},
}};
const isUsHubContext = true;
let visible = [];
const visibleAiSignalSnapshotItems = () => visible;
const isCurrentAiSignalHolding = item => item.current?.position_open === true;
const isAiSignalSnapshotStale = () => true;
{function_source}
const empty = aiSignalPageFreshnessView();
visible = [{{ current: {{ position_open: true }} }}];
const held = aiSignalPageFreshnessView();
assert.equal(empty.state, 'delayed');
assert.equal(empty.label, '미국 신규 진입 보류');
assert.match(empty.detail, /2026-11-04 자료 기준/);
assert.equal(held.heldCount, 1);
assert.match(held.label, /보유 신호 유지/);
console.log(JSON.stringify({{ empty, held }}));
"""
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True, timeout=10,
    )
    result = json.loads(completed.stdout)
    assert result["empty"]["state"] == "delayed"
    assert result["held"]["heldCount"] == 1


def test_domestic_held_signal_status_explains_unverified_paths_without_changing_quote_state():
    source = SOURCE.read_text()
    function_source = source[
        source.index("function aiSignalPageFreshnessView(") :
        source.index("function syncAiSignalFreshnessBadgeVisibility(")
    ]
    script = f"""
const assert = require('node:assert/strict');
const state = {{
  marketScope: 'kr', aiSignalUnverifiedCount: 3,
  aiSignalMarketMetricsByScope: {{}}, aiSignalItems: [],
}};
let isUsHubContext = false;
const navigator = {{ onLine: true }};
const visibleAiSignalSnapshotItems = () => [{{ code: '005930' }}];
const isCurrentAiSignalHolding = () => true;
const isAiSignalSnapshotStale = () => false;
const itemMatchesMarketScope = () => true;
const aiSignalItemWithLiveOverlay = () => ({{ live_freshness_state: 'closed' }});
const aiSignalFreshnessSummary = () => ({{ state: 'closed', mixed: false }});
const aiSignalFreshnessSummaryLabel = () => '장 마감 · 보유 1개';
const formatAiSignalLiveTime = () => '';
const formatNumber = value => String(value);
{function_source}
const held = aiSignalPageFreshnessView();
assert.equal(held.state, 'closed');
assert.match(held.detail, /3개 종목의 매매 기록을 재검증 중/);
assert.match(held.detail, /새 확정 신호는 보류/);
state.aiSignalUnverifiedCount = 0;
const verified = aiSignalPageFreshnessView();
assert.equal(verified.detail, '마지막 확인 가격 기준이며 확정 수익률은 바뀌지 않아요.');
state.marketScope = 'us';
isUsHubContext = true;
state.aiSignalUnverifiedCount = 3;
const us = aiSignalPageFreshnessView();
assert.doesNotMatch(us.detail, /재검증 중/);
console.log(JSON.stringify({{ held, verified, us }}));
"""
    completed = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True, timeout=10,
    )
    result = json.loads(completed.stdout)
    assert result["held"]["state"] == "closed"
    assert "재검증 중" in result["held"]["detail"]


def test_recommendation_list_keeps_stale_us_status_when_ranked_items_exist():
    source = SOURCE.read_text()
    function_source = source[
        source.index("async function fetchRecommendationsForScope("):
        source.index("async function loadRecommendations(")
    ]
    script = f"""
const assert = require('node:assert/strict');
const isUsHubContext = true;
const state = {{ marketScope: 'us' }};
const RECOMMENDATION_LIMIT = 8;
const pageEntryTtlMs = () => 0;
const fetchJsonCached = async () => ({{
  status: 'ready', data_state: 'ready', selection_state: 'stale',
  selection_message: '2026-11-04 자료 기준 추천입니다.',
  as_of: '2026-11-04', items: [{{ code: 'AAA' }}],
}});
const tagMarketItems = (items, scope) => items.map(item => ({{ ...item, market_scope: scope }}));
const canonicalUsPayloadCanCompose = () => true;
const failClosedUsEntryPendingItems = items => items;
const entryPendingItemCount = () => 0;
{function_source}
fetchRecommendationsForScope().then(payload => {{
  assert.equal(payload.items.length, 1);
  assert.equal(payload.selection_state, 'stale');
  assert.match(payload.selection_message, /2026-11-04/);
}}).catch(error => {{ console.error(error); process.exitCode = 1; }});
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True, timeout=10)


def test_recommendation_list_keeps_partial_signal_status_with_ranked_items():
    source = SOURCE.read_text()
    scope_source = source[
        source.index("async function fetchRecommendationsForScope("):
        source.index("async function loadRecommendations(")
    ]
    render_source = source[
        source.index("function renderRecommendations("):
        source.index("function setTrendTab(")
    ]
    script = f"""
const assert = require('node:assert/strict');
const isUsHubContext = false;
const state = {{ marketScope: 'kr', usSectorMoves: null }};
const RECOMMENDATION_LIMIT = 8;
const pageEntryTtlMs = () => 0;
const fetchJsonCached = async () => ({{
  selection_state: 'ready', signal_state: 'partial', signal_unavailable_count: 1,
  signal_message: '추천 후보 1개의 AI 매매 시그널 근거를 확인하지 못했습니다.',
  as_of: '2026-11-09', items: [{{ code: '005930' }}],
}});
const tagMarketItems = (items, scope) => items.map(item => ({{ ...item, market_scope: scope }}));
const canonicalUsPayloadCanCompose = () => true;
const failClosedUsEntryPendingItems = items => items;
const entryPendingItemCount = () => 0;
const elements = {{
  recommendMeta: {{ textContent: '', dateTime: '', hidden: true }},
  recommendList: {{ innerHTML: '', dataset: {{}} }},
}};
let status = '';
let cards = 0;
const closeRecommendationQuoteStreams = () => {{}};
const recommendationIsTerminalExit = () => false;
const rerankRecommendationItems = items => items;
const updateRecommendationTrackMeta = () => {{}};
const formatDataBasis = value => value;
const setRecommendStatus = value => {{ status = value; }};
const appendRecommendationCard = () => {{ cards += 1; }};
const connectRecommendationQuoteStream = () => {{}};
const scheduleUsSectorRefresh = () => {{}};
{scope_source}
{render_source}
fetchRecommendationsForScope().then(payload => {{
  renderRecommendations(payload);
  assert.equal(cards, 1);
  assert.equal(payload.signal_unavailable_count, 1);
  assert.match(status, /1개/);
}}).catch(error => {{ console.error(error); process.exitCode = 1; }});
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True, timeout=10)


def test_recommendation_stage_marks_unverified_signal_unavailable():
    source = SOURCE.read_text()
    stage_source = source[
        source.index("function recommendationSignalStageView("):
        source.index("function recommendationAiSignalStageView(")
    ]
    script = f"""
const assert = require('node:assert/strict');
{stage_source}
const stage = recommendationSignalStageView({{
  data_state: 'unavailable', current: null,
  data_message: '이전 장중 매매 기록을 재검증 중입니다.',
}});
assert.equal(stage.key, 'unavailable');
assert.equal(stage.headline, '시그널 확인 불가');
assert.match(stage.next, /재검증 중/);
assert.equal(stage.changedAt, null);
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True, timeout=10)


def test_ranked_recommendation_cards_show_stale_status_notice():
    source = SOURCE.read_text()
    function_source = source[
        source.index("function renderRecommendations("):
        source.index("function setTrendTab(")
    ]
    script = f"""
const assert = require('node:assert/strict');
const RECOMMENDATION_LIMIT = 8;
const state = {{ usSectorMoves: null }};
const elements = {{
  recommendMeta: {{ textContent: '', dateTime: '', hidden: true }},
  recommendList: {{ innerHTML: '', dataset: {{}} }},
}};
let status = '';
let cards = 0;
const closeRecommendationQuoteStreams = () => {{}};
const recommendationIsTerminalExit = () => false;
const rerankRecommendationItems = items => items;
const updateRecommendationTrackMeta = () => {{}};
const formatDataBasis = value => value;
const setRecommendStatus = value => {{ status = value; }};
const appendRecommendationCard = () => {{ cards += 1; }};
const connectRecommendationQuoteStream = () => {{}};
const scheduleUsSectorRefresh = () => {{}};
{function_source}
renderRecommendations({{
  as_of: '2026-11-04', selection_state: 'stale',
  selection_message: '2026-11-04 자료 기준 추천입니다.',
  items: [{{ code: 'AAA' }}],
}});
assert.equal(cards, 1);
assert.match(status, /2026-11-04/);
assert.equal(elements.recommendList.dataset.selectionState, 'stale');
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True, timeout=10)


def test_signal_page_commits_market_scan_metadata_and_updates_the_universe_label():
    source = SOURCE.read_text()

    assert "Number(payload.current_universe_count) || Number(payload.universe_count) || 0" in source
    assert "Number(payload.execution_replay_unverified_count) || 0" in source
    assert "execution_replay_unverified_count: Number(payload.execution_replay_unverified_count) || 0" in source
    assert "`시총 상위 ${formatNumber(state.aiSignalUniverseCount)}개에서`" in source
    assert 'buyCandidates: stageCounts["preliminary-buy"]' in source
    assert 'sellCandidates: stageCounts["preliminary-sell"]' in source

