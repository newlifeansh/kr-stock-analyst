import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
APP_JS = ROOT / "app" / "static" / "dashboard" / "app.js"
DASHBOARD_CSS = ROOT / "app" / "static" / "dashboard" / "styles.css"


def _source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_pull_refresh_cancels_ios_overscroll_before_the_drag_visual_starts() -> None:
    source = _source()
    start = source.index("function handlePullRefreshMove(")
    end = source.index("function handlePullRefreshEnd(", start)
    handler_source = source[start:end]
    script = f"""
const state = {{
  pullRefreshTracking: true,
  pullRefreshRefreshing: false,
  pullRefreshReady: false,
  pullRefreshStartX: 100,
  pullRefreshStartY: 100,
  pullRefreshAxis: "pending",
}};
const PULL_REFRESH_TRIGGER_DISTANCE = 72;
const PULL_REFRESH_MAX_DISTANCE = 104;
const PULL_REFRESH_DRAG_OFFSET = 10;
let prevented = 0;
let resetCount = 0;
let indicator = null;
function currentScrollTop() {{ return 0; }}
function resetPullRefreshIndicator() {{ resetCount += 1; }}
function setPullRefreshIndicator(distance, options) {{ indicator = {{ distance, options }}; }}
{handler_source}
handlePullRefreshMove({{
  touches: [{{ clientX: 100, clientY: 104 }}],
  cancelable: true,
  preventDefault() {{ prevented += 1; }},
}});
console.log(JSON.stringify({{
  prevented,
  resetCount,
  indicator,
  axis: state.pullRefreshAxis,
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "prevented": 1,
        "resetCount": 0,
        "indicator": None,
        "axis": "vertical",
    }


def test_pull_refresh_keeps_the_page_stable_and_visible_above_the_safe_area() -> None:
    styles = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert ".app-frame.pull-refresh-active .shell" not in styles
    assert "overscroll-behavior-y: none;" in styles
    assert "top: calc(70px + env(safe-area-inset-top, 0px));" in styles
    assert "z-index: 90;" in styles
    assert ".pull-refresh-indicator.complete .pull-refresh-spinner" in styles
    assert ".pull-refresh-indicator.error .pull-refresh-spinner" in styles


def test_pull_refresh_forces_fresh_data_and_reports_completion() -> None:
    source = _source()
    start = source.index("async function refreshCurrentView(")
    end = source.index("async function triggerPullRefresh(", start)
    refresh_source = source[start:end]

    assert 'await load(query, { force: true, historyMode: "none" });' in refresh_source
    assert 'case "notifications":' in refresh_source
    assert 'case "ai-signals":' in refresh_source
    assert 'case "morning-briefing":' in refresh_source
    assert 'case "recommend-detail":' in refresh_source
    assert 'loadRecommendations({ auto: true, force: true, recompute: false })' in refresh_source
    assert 'loadRecommendations({ auto: true, force: true, recompute: true })' not in refresh_source
    assert 'setPullRefreshIndicator(0, { status: "complete" });' in source
    assert 'setPullRefreshIndicator(0, { status: "error" });' in source
    assert "최신 정보로 새로고침 완료" in source
