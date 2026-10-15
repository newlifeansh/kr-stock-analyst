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


def test_signal_page_commits_market_scan_metadata_and_updates_the_universe_label():
    source = SOURCE.read_text()

    assert "Number(payload.current_universe_count) || Number(payload.universe_count) || 0" in source
    assert "Number(payload.execution_replay_unverified_count) || 0" in source
    assert "execution_replay_unverified_count: Number(payload.execution_replay_unverified_count) || 0" in source
    assert "`시총 상위 ${formatNumber(state.aiSignalUniverseCount)}개에서`" in source
    assert 'buyCandidates: stageCounts["preliminary-buy"]' in source
    assert 'sellCandidates: stageCounts["preliminary-sell"]' in source

