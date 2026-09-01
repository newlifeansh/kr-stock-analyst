from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


DASHBOARD_SOURCE = Path("app/static/dashboard/app.js").resolve()


def _function_source(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index(f"function {next_name}(", start + 1)]


@pytest.mark.qa_gate
def test_stock_detail_hydrates_current_quote_before_first_numeric_render() -> None:
    source = DASHBOARD_SOURCE.read_text(encoding="utf-8")
    load_source = source[
        source.index("async function loadStockRequest") : source.index(
            "function load(", source.index("async function loadStockRequest")
        )
    ]
    render_source = _function_source(source, "render", "resolveStock")
    hydrate_source = _function_source(
        source, "hydrateInitialStockQuote", "loadStockRequest"
    )

    assert "const initialQuoteRequest = fetchInitialStockQuote(stock.code);" in load_source
    assert "Promise.all([dashboardRequest, initialQuoteRequest])" in load_source
    assert load_source.index("hydrateInitialStockQuote(") < load_source.index("render(dashboard")
    assert "state.stockQuoteReadyCode = normalizedCode;" in hydrate_source
    assert "stockQuotePayloadIsDisplayReady(payload)" in hydrate_source
    assert "const dashboardSource = dashboard.source;" in hydrate_source
    assert "dashboard.source = dashboardSource;" in hydrate_source
    assert 'state.stockQuoteReadyCode === String(data.code || "")' in render_source
    assert "resetStockQuoteDisplay();" in render_source
    assert render_source.index("resetStockQuoteDisplay();") < render_source.index(
        "connectQuoteStream(state.currentStock);"
    )

    navigation_source = _function_source(source, "navigateToStock", "readWatchlist")
    sync_source = source[
        source.index("async function syncViewFromLocation") : source.index(
            "async function handleDashboardPopState"
        )
    ]
    assert navigation_source.index("setLoading(normalized);") < navigation_source.index(
        'setView("stock", { historyMode: "none" });'
    )
    assert sync_source.index("setLoading(stockQuery);") < sync_source.index(
        'setView("stock", { historyMode: "none" });'
    )


@pytest.mark.qa_gate
def test_stock_quote_readiness_rejects_active_stored_and_stale_frames() -> None:
    source_path = str(DASHBOARD_SOURCE)
    script = f"""
const fs = require("fs");
const source = fs.readFileSync({json.dumps(source_path)}, "utf8");
const start = source.indexOf("function quoteFrameTimestamp(");
const end = source.indexOf("function quoteFrameSequence(", start);
const AI_SIGNAL_REALTIME_QUOTE_MAX_AGE_MS = 5_000;
const AI_SIGNAL_DELAYED_QUOTE_MAX_AGE_MS = 30_000;
let marketLive = true;
function koreaExtendedQuoteLive() {{ return marketLive; }}
function aiSignalQuoteUsesActiveSession(quote) {{
  return ["krx_opening_auction", "krx_regular", "integrated_regular", "nxt_after_market"]
    .includes(String(quote?.market_session || ""));
}}
eval(source.slice(start, end));
const now = Date.parse("2026-09-01T10:00:00+09:00");
const frame = (sourceName, asOf, session = "krx_regular") => ({{
  type: "quote", code: "005930", source: sourceName, as_of: asOf,
  quote: {{ price: 120000, market_session: session }},
}});
const result = {{
  realtime: stockQuotePayloadIsDisplayReady(
    frame("kis_realtime", "2026-09-01T09:59:58+09:00"), now,
  ),
  staleRealtime: stockQuotePayloadIsDisplayReady(
    frame("kis_realtime", "2026-09-01T09:59:40+09:00"), now,
  ),
  delayedRest: stockQuotePayloadIsDisplayReady(
    frame("kis_rest", "2026-09-01T09:59:50+09:00"), now,
  ),
  activeStored: stockQuotePayloadIsDisplayReady(
    frame("stored_daily_price", "2026-08-31T15:30:00+09:00"), now,
  ),
}};
marketLive = false;
result.closedStored = stockQuotePayloadIsDisplayReady(
  frame("stored_daily_price", "2026-08-31T15:30:00+09:00", "closed"), now,
);
result.openingAuctionStored = stockQuotePayloadIsDisplayReady(
  frame("stored_daily_price", "2026-08-31T15:30:00+09:00", "krx_opening_auction"), now,
);
process.stdout.write(JSON.stringify(result));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "realtime": True,
        "staleRealtime": False,
        "delayedRest": True,
        "activeStored": False,
        "closedStored": True,
        "openingAuctionStored": False,
    }


@pytest.mark.qa_gate
def test_ai_signal_entry_suppresses_snapshot_return_until_quote_is_ready() -> None:
    source_path = str(DASHBOARD_SOURCE)
    script = f"""
const fs = require("fs");
const source = fs.readFileSync({json.dumps(source_path)}, "utf8");
const start = source.indexOf("function aiSignalItemWithLiveOverlay(");
const end = source.indexOf("function formatAiSignalLiveTime(", start);
let freshness = "checking";
const state = {{ aiSignalLiveQuotes: new Map() }};
function aiSignalLiveFreshnessState() {{ return freshness; }}
function isCurrentAiSignalHolding() {{ return true; }}
function toNumber(value) {{
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}}
function aiSignalLiveReturnRate(_item, quote) {{ return Number(quote.return_rate); }}
eval(source.slice(start, end));
const base = {{
  code: "005930",
  display_return_rate: 7.5,
  return_rate: 7.5,
  current: {{ position_open: true, unrealized_return: 7.5 }},
}};
const pending = aiSignalItemWithLiveOverlay(base, 1);
state.aiSignalLiveQuotes.set("005930", {{
  displayReady: false,
  payload: {{
    source: "stored_daily_price",
    as_of: "2026-08-31T15:30:00+09:00",
    quote: {{ price: 115000, return_rate: 5.0 }},
  }},
  receivedAt: 1,
}});
const activeStoredFallback = aiSignalItemWithLiveOverlay(base, 1);
state.aiSignalLiveQuotes.set("005930", {{
  displayReady: false,
  payload: {{
    source: "kis_realtime",
    as_of: "2026-09-01T10:00:00+09:00",
    quote: {{ price: 120000, return_rate: 8.25 }},
  }},
  receivedAt: 1,
}});
freshness = "realtime";
const realtime = aiSignalItemWithLiveOverlay(base, 1);
freshness = "checking";
const checkingWithAcceptedQuote = aiSignalItemWithLiveOverlay(base, 1);
process.stdout.write(JSON.stringify({{ pending, activeStoredFallback, checkingWithAcceptedQuote, realtime }}));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["pending"]["live_return_pending"] is True
    assert result["pending"]["display_return_rate"] is None
    assert result["activeStoredFallback"]["live_return_pending"] is True
    assert result["activeStoredFallback"]["display_return_rate"] is None
    assert result["checkingWithAcceptedQuote"]["live_return_pending"] is False
    assert result["checkingWithAcceptedQuote"]["display_return_rate"] == 8.25
    assert result["checkingWithAcceptedQuote"]["display_return_kind"] == "stale_open_position"
    assert result["realtime"]["live_return_pending"] is False
    assert result["realtime"]["live_return_rate"] == 8.25
    assert result["realtime"]["display_return_kind"] == "live_open_position"

    outcome_source = _function_source(
        DASHBOARD_SOURCE.read_text(encoding="utf-8"),
        "aiSignalOutcomeMetrics",
        "aiSignalOutcomeLine",
    )
    assert "pendingEntry || item.live_return_pending === true" in outcome_source
    assert 'value: freshnessState === "offline" ? "연결 후 확인" : "현재가 확인 중"' in outcome_source


@pytest.mark.qa_gate
def test_ai_signal_navigation_clears_previous_surface_before_reloading() -> None:
    source = DASHBOARD_SOURCE.read_text(encoding="utf-8")
    prepare_source = _function_source(
        source, "prepareAiSignalEntrySurface", "activeAiSignalList"
    )
    set_view_source = _function_source(source, "setView", "renderEvents")

    assert "state.aiSignalLiveQuotes.clear();" in prepare_source
    assert "state.aiSignalQuoteStatuses.clear();" in prepare_source
    assert "elements.aiSignalsPageList.replaceChildren(pending);" in prepare_source
    assert "renderPendingHomeAiSignals();" in prepare_source
    assert '["home", "ai-signals"].includes(view) && previousView !== view' in set_view_source
    assert set_view_source.index("prepareAiSignalEntrySurface(view);") < set_view_source.index(
        "elements.aiSignalsView.hidden = view !== \"ai-signals\";"
    )
