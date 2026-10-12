from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest


@pytest.mark.qa_gate
@pytest.mark.parametrize("path", ["/dashboard/005930", "/us/stock/AAPL"])
@pytest.mark.parametrize("popular", [True, False])
def test_cold_stock_navigation_applies_community_route_after_hydration(path, popular):
    """A notification opens a new document, not the popstate-only route handler."""
    source = Path("app/static/dashboard/app.js").read_text()
    sync = source[source.index("async function syncViewFromLocation()"):
                  source.index("async function handleDashboardPopState(")]
    initialize = source[source.index("async function initializeDashboard()"):
                        source.index("void initializeDashboard();")]
    search = "?tab=community" + ("&community_mode=popular" if popular else "")
    script = f"""
const assert = require('node:assert/strict');
const calls = [];
const state = {{view: 'stock', stockActiveTab: 'summary', stockCommunityMode: 'latest'}};
const window = {{location: {{pathname: {json.dumps(path)}, search: {json.dumps(search)}}},
  requestAnimationFrame: callback => callback()}};
const elements = {{stockCommunitySection: {{scrollIntoView() {{calls.push('scroll');}}}}}};
function initializeDashboardHistory() {{calls.push('history');}}
async function initializeWatchlistIdentity() {{calls.push('identity');}}
function setView(view) {{state.view = view;}}
function setLoading() {{}}
function setActiveStockTab(tab) {{state.stockActiveTab = tab; calls.push('tab:' + tab);}}
async function loadStockCommunityMode(mode) {{state.stockCommunityMode = mode; calls.push('mode:' + mode);}}
function pathQuery() {{return window.location.pathname.split('/').at(-1);}}
async function load(query, options) {{
  assert.equal(query, pathQuery());
  assert.equal(options.historyMode, 'none');
  if (window.location.pathname.startsWith('/us/')) assert.equal(options.marketScope, 'us');
  // The dashboard render clears old stock content before the route is restored.
  state.stockActiveTab = 'summary';
  state.stockCommunityMode = 'latest';
  await Promise.resolve();
  calls.push('hydrated');
}}
{sync}
{initialize}
initializeDashboard().then(() => {{
  assert.equal(state.stockActiveTab, 'community');
  assert.equal(state.stockCommunityMode, {json.dumps('popular' if popular else 'latest')});
  assert.ok(calls.indexOf('identity') < calls.indexOf('hydrated'));
  assert.ok(calls.indexOf('tab:community') > calls.indexOf('hydrated'));
  assert.equal(calls.filter(value => value === 'hydrated').length, 1);
}}).catch(error => {{console.error(error); process.exitCode = 1;}});
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
