from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest


@pytest.mark.qa_gate
def test_cold_stock_navigation_opens_news_tab_and_anchors_stock_news_after_hydration():
    for path, search in (
        ("/dashboard/005930", "?tab=news"),
        ("/us/stock/AAPL", "?market_scope=us&tab=news"),
    ):
        _assert_cold_stock_news_navigation(path, search)


def _assert_cold_stock_news_navigation(path: str, search: str) -> None:
    source = Path("app/static/dashboard/app.js").read_text(encoding="utf-8")
    sync = source[
        source.index("async function syncViewFromLocation()"):
        source.index("async function handleDashboardPopState(")
    ]
    initialize = source[
        source.index("async function initializeDashboard()"):
        source.index("void initializeDashboard();")
    ]
    script = f"""
const assert = require('node:assert/strict');
const calls = [];
const state = {{view: 'stock', stockActiveTab: 'summary', stockCommunityMode: 'latest'}};
const window = {{location: {{pathname: {json.dumps(path)}, search: {json.dumps(search)}, hash: '#stock-news-section'}},
  requestAnimationFrame: callback => callback()}};
const elements = {{
  stockNewsSection: {{scrollIntoView() {{calls.push('news-scroll');}}}},
  stockCommunitySection: null,
}};
function initializeDashboardHistory() {{calls.push('history');}}
async function initializeWatchlistIdentity() {{calls.push('identity');}}
function setView(view) {{state.view = view;}}
function setLoading() {{}}
function setActiveStockTab(tab) {{state.stockActiveTab = tab; calls.push('tab:' + tab);}}
async function loadStockCommunityMode(mode) {{state.stockCommunityMode = mode;}}
function pathQuery() {{return window.location.pathname.split('/').at(-1);}}
async function load(query, options) {{
  assert.equal(query, pathQuery());
  assert.equal(options.historyMode, 'none');
  if (window.location.pathname.startsWith('/us/')) assert.equal(options.marketScope, 'us');
  state.stockActiveTab = 'summary';
  await Promise.resolve();
  calls.push('hydrated');
}}
{sync}
{initialize}
initializeDashboard().then(() => {{
  assert.equal(state.stockActiveTab, 'news');
  assert.ok(calls.indexOf('identity') < calls.indexOf('hydrated'));
  assert.ok(calls.indexOf('tab:news') > calls.indexOf('hydrated'));
  assert.ok(calls.indexOf('news-scroll') > calls.indexOf('tab:news'));
  assert.equal(calls.filter(value => value === 'hydrated').length, 1);
}}).catch(error => {{console.error(error); process.exitCode = 1;}});
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
