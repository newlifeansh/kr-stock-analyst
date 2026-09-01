import json
import subprocess
from pathlib import Path


APP_JS = Path(__file__).parents[1] / "app" / "static" / "dashboard" / "app.js"
DASHBOARD_CSS = Path(__file__).parents[1] / "app" / "static" / "dashboard" / "styles.css"


def app_source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def dashboard_styles() -> str:
    return DASHBOARD_CSS.read_text(encoding="utf-8")


def test_quote_stream_rejects_same_epoch_sequence_regressions_and_old_http_fallbacks() -> None:
    source = app_source()
    start = source.index("function quoteFrameTimestamp(")
    end = source.index("function pauseQuoteStreamConnection(", start)
    ordering_source = source[start:end]
    script = f"""
const state = {{ quoteStreamLatestByCode: new Map(), quoteStreamEpoch: 7 }};
{ordering_source}
const initial = {{
  type: "quote", code: "005930", sequence: 10,
  observed_at: "2026-08-31T10:00:00+09:00", source: "kis_realtime",
  quote: {{ trade_date: "2026-08-31", price: 70000 }},
}};
const newer = {{ ...initial, sequence: 11, observed_at: "2026-08-31T10:01:00+09:00" }};
const regressed = {{ ...initial, sequence: 9, observed_at: "2026-08-31T10:02:00+09:00" }};
const oldHttp = {{
  ...initial, sequence: undefined, source: "naver_finance",
  observed_at: "2026-08-31T10:00:30+09:00",
}};
const newerHttp = {{
  ...initial, sequence: undefined, source: "naver_finance",
  observed_at: "2026-08-31T10:02:30+09:00",
}};
const postFallbackRegression = {{ ...initial, sequence: 10, observed_at: "2026-08-31T10:02:45+09:00" }};
const restarted = {{ ...initial, sequence: 1, observed_at: "2026-08-31T10:03:00+09:00" }};
const result = {{
  initial: recordQuoteStreamPayload(initial, 1, 7),
  newer: recordQuoteStreamPayload(newer, 2, 7),
  regressed: recordQuoteStreamPayload(regressed, 3, 7),
  oldHttp: recordQuoteStreamPayload(oldHttp, 4, 7),
  newerHttp: recordQuoteStreamPayload(newerHttp, 5, 7),
  postFallbackRegression: recordQuoteStreamPayload(postFallbackRegression, 6, 7),
  restarted: recordQuoteStreamPayload(restarted, 7, 8),
}};
result.latest = state.quoteStreamLatestByCode.get("005930").payload.sequence;
result.epoch = state.quoteStreamLatestByCode.get("005930").epoch;
console.log(JSON.stringify(result));
"""

    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert json.loads(completed.stdout) == {
        "initial": True,
        "newer": True,
        "regressed": False,
        "oldHttp": False,
        "newerHttp": True,
        "postFallbackRegression": False,
        "restarted": True,
        "latest": 1,
        "epoch": 8,
    }


def test_quote_stream_selection_prioritizes_visible_signal_rows_and_reports_overflow() -> None:
    source = app_source()
    start = source.index("const QUOTE_STREAM_SCOPE_PRIORITIES")
    end = source.index("function quoteStreamSelection(", start)
    selection_source = source[start:end]
    script = f"""
const QUOTE_STREAM_DEFAULT_CODE_LIMIT = 64;
{selection_source}
const scopes = new Map([
  ["market", new Map([["000660", {{}}], ["035420", {{}}]])],
  ["ai-signals", new Map([["005930", {{}}], ["000660", {{}}]])],
  ["detail", new Map([["373220", {{}}]])],
]);
console.log(JSON.stringify(buildQuoteStreamSelection(scopes, 3)));
"""

    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert json.loads(completed.stdout) == {
        "selected": ["373220", "005930", "000660"],
        "overflow": ["035420"],
    }


def test_signal_snapshot_is_immutable_accepts_newer_http_token_and_prunes_full_exits() -> None:
    source = app_source()
    start = source.index("function aiSignalRevisionFromPayload(")
    end = source.index("function aiSignalQuoteUsesActiveSession(", start)
    snapshot_source = source[start:end]
    script = f"""
"use strict";
const state = {{
  aiSignalItems: [], aiSignalMarketStatus: "loading", aiSignalRevision: null,
  aiSignalPendingRevision: 101, aiSignalReconcilePending: true,
  aiSignalSnapshotReceivedAt: 0, aiSignalSnapshotAsOf: "",
  aiSignalLiveQuotes: new Map([["005930", {{}}], ["000660", {{}}]]),
  aiSignalQuoteStatuses: new Map([["005930", {{ status: "fallback" }}]]),
  aiSignalLastStaleState: true, aiSignalRevisionRetryCount: 2,
}};
let renders = 0;
function currentAiSignalItems(items) {{ return items; }}
function isCurrentAiSignalHolding(item) {{ return item?.current?.position_open === true; }}
function renderAiSignalLiveStatus() {{ renders += 1; }}
{snapshot_source}
const holding = {{ code: "005930", name: "삼성전자", current: {{ position_open: true }} }};
const newerTokenAccepted = commitAiSignalSnapshot(
  [holding],
  {{ signal_revision: 202, snapshot_generated_at: "2026-08-31T10:00:00+09:00" }},
  {{ expectedRevision: 101 }},
);
let mutationBlocked = false;
try {{ state.aiSignalItems[0].name = "변조"; }} catch {{ mutationBlocked = true; }}
const revisionAfterNewerToken = state.aiSignalRevision;
const missingTokenRejected = commitAiSignalSnapshot(
  [{{ code: "005930", current: {{ position_open: true }} }}],
  {{ signal_revision: 0 }},
  {{ expectedRevision: 303 }},
);
const fullExitAccepted = commitAiSignalSnapshot(
  [{{ code: "005930", current: {{ position_open: false }} }}],
  {{ signal_revision: 404 }},
  {{ expectedRevision: 404 }},
);
console.log(JSON.stringify({{
  newerTokenAccepted, revisionAfterNewerToken, missingTokenRejected, fullExitAccepted,
  frozen: Object.isFrozen(state.aiSignalItems) && Object.isFrozen(state.aiSignalItems[0]),
  mutationBlocked,
  overlaySize: state.aiSignalLiveQuotes.size,
  statusSize: state.aiSignalQuoteStatuses.size,
  revision: state.aiSignalRevision,
  pending: state.aiSignalReconcilePending,
  retryCount: state.aiSignalRevisionRetryCount,
  renders,
}}));
"""

    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert json.loads(completed.stdout) == {
        "newerTokenAccepted": True,
        "revisionAfterNewerToken": 202,
        "missingTokenRejected": False,
        "fullExitAccepted": True,
        "frozen": True,
        "mutationBlocked": True,
        "overlaySize": 0,
        "statusSize": 0,
        "revision": 404,
        "pending": False,
        "retryCount": 0,
        "renders": 2,
    }


def test_kis_realtime_quote_clears_fallback_status_without_mutating_snapshot() -> None:
    source = app_source()
    start = source.index("function updateAiSignalLiveQuote(")
    end = source.index("function closeAiSignalQuoteStreams(", start)
    update_source = source[start:end]
    script = f"""
const holding = Object.freeze({{ code: "005930", current: Object.freeze({{ position_open: true }}) }});
const state = {{
  aiSignalItems: Object.freeze([holding]), aiSignalLiveQuotes: new Map(),
  aiSignalQuoteStatuses: new Map([["005930", {{ status: "fallback" }}]]),
  quoteStreamLatestByCode: new Map(), aiSignalLiveAsOf: "",
}};
let refreshes = 0;
function currentAiSignalItems(items) {{ return items; }}
function isCurrentAiSignalHolding(item) {{ return item?.current?.position_open === true; }}
function aiSignalLiveReturnRate(_item, quote) {{ return Number(quote.price) > 0 ? 1.25 : null; }}
function quotePayloadIsStoredFallbackDuringActiveSession(payload) {{
  return payload?.source === "stored_daily_price";
}}
function refreshAiSignalLiveRows() {{ refreshes += 1; }}
{update_source}
const quotePayload = {{
  type: "quote", code: "005930", source: "kis_realtime", sequence: 12,
  observed_at: "2026-08-31T10:30:00+09:00", quote: {{ price: 71000 }},
}};
state.quoteStreamLatestByCode.set("005930", {{ payload: quotePayload, receivedAt: 123 }});
const quoteAccepted = updateAiSignalLiveQuote("005930", quotePayload.quote, quotePayload);
const fallbackClearedByQuote = !state.aiSignalQuoteStatuses.has("005930");
state.aiSignalLiveQuotes.get("005930").displayReady = true;
const storedFallbackPayload = {{
  type: "quote", code: "005930", source: "stored_daily_price",
  as_of: "2026-08-29T15:30:00+09:00", quote: {{ price: 69000 }},
}};
const storedFallbackAccepted = updateAiSignalLiveQuote(
  "005930", storedFallbackPayload.quote, storedFallbackPayload,
);
updateAiSignalQuoteStatus("005930", {{ status: "fallback", message: "temporary" }});
const fallbackStored = state.aiSignalQuoteStatuses.get("005930")?.status;
updateAiSignalQuoteStatus("005930", {{ status: "recovered" }});
console.log(JSON.stringify({{
  quoteAccepted, fallbackClearedByQuote, storedFallbackAccepted, fallbackStored,
  recovered: !state.aiSignalQuoteStatuses.has("005930"),
  overlaySource: state.aiSignalLiveQuotes.get("005930")?.payload?.source,
  overlayPrice: state.aiSignalLiveQuotes.get("005930")?.payload?.quote?.price,
  snapshotPrice: holding.current.price ?? null,
  refreshes,
}}));
"""

    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    assert json.loads(completed.stdout) == {
        "quoteAccepted": True,
        "fallbackClearedByQuote": True,
        "storedFallbackAccepted": False,
        "fallbackStored": "fallback",
        "recovered": True,
        "overlaySource": "kis_realtime",
        "overlayPrice": 71000,
        "snapshotPrice": None,
        "refreshes": 4,
    }


def test_ai_signal_freshness_color_tokens_keep_small_text_contrast() -> None:
    styles = dashboard_styles()

    def luminance(color: str) -> float:
        channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def contrast(left: str, right: str) -> float:
        brighter, darker = sorted((luminance(left), luminance(right)), reverse=True)
        return (brighter + 0.05) / (darker + 0.05)

    light_tokens = ("#096b4f", "#754500", "#4f5966", "#46566d")
    dark_tokens = ("#72deb8", "#f3bd64", "#c3cad3", "#bdcbe0")
    for token in (*light_tokens, *dark_tokens):
        assert token in styles
    assert all(contrast(token, "#f1f1f1") >= 4.5 for token in light_tokens)
    assert all(contrast(token, "#17161b") >= 4.5 for token in dark_tokens)


def test_ai_signal_freshness_summary_collapses_normal_state_and_counts_exceptions() -> None:
    source = app_source()
    start = source.index("const AI_SIGNAL_FRESHNESS_SUMMARY_ORDER")
    end = source.index("function aiSignalLifecycleIsActive", start)
    summary_source = source[start:end]
    script = f"""
{summary_source}
const summarize = states => {{
  const summary = aiSignalFreshnessSummary(states);
  return {{ ...summary, label: aiSignalFreshnessSummaryLabel(summary) }};
}};
console.log(JSON.stringify({{
  healthy: summarize(["realtime", "realtime"]),
  mixed: summarize(["realtime", "delayed", "checking"]),
  closed: summarize(["closed", "closed"]),
}}));
"""

    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    result = json.loads(completed.stdout)
    assert result["healthy"] == {
        "state": "realtime",
        "counts": {
            "realtime": 2,
            "delayed": 0,
            "checking": 0,
            "offline": 0,
            "closed": 0,
        },
        "heldCount": 2,
        "mixed": False,
        "label": "보유 2개 모두 실시간",
    }
    assert result["mixed"]["state"] == "checking"
    assert result["mixed"]["mixed"] is True
    assert result["mixed"]["label"] == "실시간 1 · 약 10초 지연 1 · 확인 중 1"
    assert result["closed"]["label"] == "장 마감 · 보유 2개"


def test_home_ai_signal_view_accepts_a_missing_watchlist_signal() -> None:
    source = app_source()
    start = source.index("function isPreliminaryAiSignal(")
    end = source.index("function aiSignalTransitionKey(", start)
    function_source = source[start:end]
    script = f"{function_source}\nconsole.log(JSON.stringify(homeAiSignalView(null)));"

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) is None


def test_pending_state_uses_last_completed_trade_date_during_weekend_refresh() -> None:
    source = app_source()
    start = source.index("function isPreliminaryAiSignal(")
    end = source.index("function aiSignalTransitionKey(", start)
    function_source = source[start:end]
    script = f"""
{function_source}
const view = homeAiSignalView({{
  code: "035420",
  status: "confirmed",
  is_preliminary: false,
  signal_date: "2026-08-19",
  signal_at: "2026-08-19T15:40:00+09:00",
  execution_date: "2026-08-20",
  price_through: "2026-08-28",
  current: {{
    action: "entry_pending",
    position_open: false,
    live_observation: false,
    as_of: "2026-08-30T12:38:41+09:00",
    lifecycle: {{
      latest_transition: {{
        label: "전략상 전량 매도",
        signal_date: "2026-08-19",
        transition_date: "2026-08-20",
      }},
    }},
  }},
}});
console.log(JSON.stringify({{
  label: view.label,
  preliminary: view.preliminary,
  signalDate: view.signalDate,
  signalAt: view.signalAt,
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "label": "예비 매수",
        "preliminary": True,
        "signalDate": "2026-08-28",
        "signalAt": "2026-08-28",
    }


def test_market_signal_adapter_promotes_canonical_pending_state() -> None:
    source = app_source()
    start = source.index("function marketAiSignalItems(")
    end = source.index("function combineAiSignalPayloads(", start)
    function_source = source[start:end]
    script = f"""
{function_source}
const [item] = marketAiSignalItems({{
  as_of: "2026-08-21T15:41:00+09:00",
  items: [{{
    code: "035420",
    name: "NAVER",
    side: "sell",
    event_side: "sell",
    status: "confirmed",
    is_preliminary: false,
    signal: "전략상 전량 매도",
    signal_date: "2026-08-19",
    signal_at: "2026-08-19T15:40:00+09:00",
    execution_date: "2026-08-20",
    price: 210500,
    entry_price: 225500,
    return_rate: -6.91,
    score: 48.92,
    state_after: "exited",
    current: {{
      action: "entry_pending",
      label: "매수 조건 확정",
      position_open: false,
      score: 68.24,
      price: 222000,
      as_of: "2026-08-21T15:40:55+09:00",
      live_observation: false,
      reasons: ["독립 우호 근거 3/1개와 최신성 확인 완료"],
    }},
  }}],
}});
console.log(JSON.stringify({{
  side: item.side,
  status: item.status,
  preliminary: item.is_preliminary,
  signalDate: item.signal_date,
  signalAt: item.signal_at,
  executionDate: item.execution_date,
  price: item.price,
  entryPrice: item.entry_price,
  score: item.score,
  returnRate: item.return_rate,
  displayReturnRate: item.display_return_rate,
  reason: item.reason,
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "side": "buy",
        "status": "preliminary",
        "preliminary": True,
        "signalDate": "2026-08-21",
        "signalAt": "2026-08-21T15:40:55+09:00",
        "executionDate": None,
        "price": 222000,
        "entryPrice": None,
        "score": 68.24,
        "returnRate": None,
        "displayReturnRate": None,
        "reason": "독립 우호 근거 3/1개와 최신성 확인 완료",
    }


def test_market_signal_adapter_rejects_weekend_refresh_time_as_signal_time() -> None:
    source = app_source()
    start = source.index("function marketAiSignalItems(")
    end = source.index("function combineAiSignalPayloads(", start)
    function_source = source[start:end]
    script = f"""
{function_source}
const [item] = marketAiSignalItems({{
  as_of: "2026-08-30T12:38:41+09:00",
  items: [{{
    code: "373220",
    name: "LG에너지솔루션",
    side: "buy",
    status: "preliminary",
    is_preliminary: true,
    signal_date: "2026-08-28",
    signal_at: "2026-08-30T12:38:41+09:00",
    updated_at: "2026-08-30T12:38:41+09:00",
    price_through: "2026-08-28",
    current: {{
      action: "entry_watch",
      live_observation: false,
      position_open: false,
      as_of: "2026-08-30T12:38:41+09:00",
      reasons: ["금요일 종가 기준"],
    }},
  }}],
}});
console.log(JSON.stringify({{
  signalDate: item.signal_date,
  signalAt: item.signal_at,
  updatedAt: item.updated_at,
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "signalDate": "2026-08-28",
        "signalAt": "2026-08-28",
        "updatedAt": "2026-08-30T12:38:41+09:00",
    }


def test_preliminary_signal_date_line_uses_market_basis_without_weekend_new_badge() -> None:
    source = app_source()
    date_start = source.index("function aiSignalDateLine(")
    date_end = source.index("function isReleasedPreliminaryAiSignal(", date_start)
    badge_start = source.index("function aiSignalActivityBadge(")
    badge_end = source.index("function createHomeAiSignalRow(", badge_start)
    function_source = source[date_start:date_end] + source[badge_start:badge_end]
    script = f"""
function compactSignalDate(value) {{
  const match = String(value || "").match(/^(\\d{{4}})-(\\d{{2}})-(\\d{{2}})/);
  return match ? `${{match[1]}}.${{match[2]}}.${{match[3]}}` : "날짜 확인 중";
}}
function isSignalReconciliation() {{ return false; }}
let today = "2026-08-30";
function seoulDateKey() {{ return today; }}
{function_source}
const weekend = {{
  signal_date: "2026-08-28",
  signal_at: "2026-08-30T12:38:41+09:00",
  last_seen_at: "2026-08-30T12:38:41+09:00",
  current: {{
    action: "entry_watch",
    live_observation: false,
    as_of: "2026-08-30T12:38:41+09:00",
  }},
}};
const weekendView = {{ preliminary: true, signalDate: "2026-08-28" }};
today = "2026-08-31";
const intraday = {{
  signal_date: "2026-08-31",
  signal_at: "2026-08-31T10:15:00+09:00",
  current: {{ action: "entry_pending", live_observation: true }},
}};
const intradayView = {{ preliminary: true, signalDate: "2026-08-31" }};
console.log(JSON.stringify({{
  weekendLine: aiSignalDateLine(weekend, weekendView),
  weekendBadge: aiSignalActivityBadge(weekend, weekendView),
  intradayLine: aiSignalDateLine(intraday, intradayView),
  intradayBadge: aiSignalActivityBadge(intraday, intradayView),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "weekendLine": "2026.08.28 장 마감 기준",
        "weekendBadge": "",
        "intradayLine": "2026.08.31 장중 기준",
        "intradayBadge": "NEW",
    }


def test_current_ai_signal_items_keep_only_latest_effective_state_per_stock() -> None:
    source = app_source()
    view_start = source.index("function isPreliminaryAiSignal(")
    view_end = source.index("function aiSignalTransitionKey(", view_start)
    market_start = source.index("function marketAiSignalItems(")
    market_end = source.index("function combineAiSignalPayloads(", market_start)
    sort_start = source.index("function aiSignalSortValue(")
    sort_end = source.index("function isAiSignalWithinDays(", sort_start)
    released_start = source.index("function isReleasedPreliminaryAiSignal(")
    released_end = source.index("function aiSignalReleasedSide(", released_start)
    stage_start = source.index("function aiSignalStageKey(")
    stage_end = source.index("function aiSignalStageCounts(", stage_start)
    function_source = "\n".join((
        source[view_start:view_end],
        source[market_start:market_end],
        source[sort_start:sort_end],
        source[released_start:released_end],
        source[stage_start:stage_end],
    ))
    script = f"""
const state = {{ aiSignalItems: [], aiSignalMode: "current" }};
{function_source}
const items = marketAiSignalItems({{
  as_of: "2026-08-21T15:35:00+09:00",
  items: [
    {{
      code: "035420",
      name: "NAVER",
      side: "buy",
      status: "preliminary",
      is_preliminary: true,
      signal_date: "2026-08-21",
      signal_at: "2026-08-21T15:30:00+09:00",
      price: 222000,
      current: {{ action: "entry_watch", position_open: false, score: 68.24, as_of: "2026-08-21T15:35:00+09:00" }},
    }},
    {{
      code: "035420",
      name: "NAVER",
      side: "sell",
      event_side: "sell",
      status: "confirmed",
      signal_date: "2026-08-19",
      execution_date: "2026-08-20",
      price: 210500,
      entry_price: 225500,
      return_rate: -6.91,
      state_after: "exited",
    }},
    {{
      code: "035420",
      name: "NAVER",
      side: "buy",
      event_side: "buy",
      status: "confirmed",
      signal_date: "2026-08-14",
      execution_date: "2026-08-18",
      price: 225500,
      entry_price: 225500,
      state_after: "holding",
    }},
    {{
      code: "010950",
      name: "S-Oil",
      side: "buy",
      event_side: "buy",
      status: "confirmed",
      signal_date: "2026-08-18",
      execution_date: "2026-08-19",
      price: 152800,
      entry_price: 152800,
      state_after: "holding",
      is_current_holding: true,
      current: {{ action: "holding", position_open: true, entry_price: 152800 }},
    }},
  ],
}});
items.push({{
  code: "000810",
  name: "삼성화재",
  side: "buy",
  status: "preliminary",
  is_preliminary: true,
  preliminary_active: false,
  signal_date: "2026-08-21",
  current: {{ action: "entry_pending", position_open: false }},
}});
const current = aiSignalItemsForMode(items, "current");
const history = aiSignalItemsForMode(items, "history");
console.log(JSON.stringify({{
  current: current.map((item) => ({{
    code: item.code,
    stage: aiSignalStageKey(item),
    label: homeAiSignalView(item).label,
    positionOpen: item.current.position_open,
  }})),
  navers: current.filter((item) => item.code === "035420").length,
  historyCodes: history.map((item) => item.code),
  counts: aiSignalModeCounts(items),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "current": [
            {
                "code": "035420",
                "stage": "preliminary-buy",
                "label": "예비 포착",
                "positionOpen": False,
            },
            {
                "code": "010950",
                "stage": "buy-holding",
                "label": "확정 매수",
                "positionOpen": True,
            },
        ],
        "navers": 1,
        "historyCodes": ["000810"],
        "counts": {"current": 2, "history": 1},
    }


def test_closed_sell_card_shows_execution_price_instead_of_planned_target() -> None:
    source = app_source()
    start = source.index("function aiSignalOutcomeMetrics(")
    end = source.index("function aiSignalOutcomeLine(", start)
    function_source = source[start:end]
    script = f"""
function toNumber(value) {{
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}}
function formatNumber(value) {{ return Number(value).toLocaleString("en-US"); }}
function formatPercent(value) {{ return `${{Number(value) >= 0 ? "+" : ""}}${{Number(value).toFixed(2)}}%`; }}
function isSignalReconciliation() {{ return false; }}
{function_source}
const metrics = aiSignalOutcomeMetrics({{
  side: "sell",
  price: 210500,
  entry_price: 225500,
  target_sell_price: 211970,
  score: 48.92,
  return_rate: -6.91,
  display_return_kind: "closed_trade",
  current: {{ action: "exited", position_open: false }},
}}, {{ key: "recent-sell", preliminary: false }});
console.log(JSON.stringify(metrics.map((metric) => [metric.label, metric.value])));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == [
        ["점수", "48.92점"],
        ["매도가", "210,500원"],
        ["확정 수익률", "-6.91%"],
    ]


def test_open_partial_profit_card_shows_the_next_profit_target() -> None:
    source = app_source()
    start = source.index("function aiSignalOutcomeMetrics(")
    end = source.index("function aiSignalOutcomeLine(", start)
    function_source = source[start:end]
    script = f"""
function toNumber(value) {{
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}}
function formatNumber(value) {{ return Number(value).toLocaleString("en-US"); }}
function formatPercent(value) {{ return `${{Number(value) >= 0 ? "+" : ""}}${{Number(value).toFixed(2)}}%`; }}
function isSignalReconciliation() {{ return false; }}
{function_source}
const metrics = aiSignalOutcomeMetrics({{
  side: "sell",
  event_side: "partial_sell",
  target_sell_price: 257660,
  score: 93.42,
  display_return_rate: 29.95,
  display_return_kind: "open_position",
  current: {{
    action: "partially_exited",
    position_open: true,
    partial_exit_reference: 269552,
    target_sell_price: 269552,
  }},
}}, {{ key: "recent-buy", preliminary: false }});
console.log(JSON.stringify(metrics.map((metric) => [metric.label, metric.value])));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == [
        ["점수", "93.42점"],
        ["다음 수익확정가", "269,552원"],
        ["보유 평가수익률", "+29.95%"],
    ]


def test_home_market_ticker_uses_current_preliminary_date_over_old_transition() -> None:
    source = app_source()
    start = source.index("function homeMarketSignalItems(")
    end = source.index("function homeHoldingSignalItems(", start)
    function_source = source[start:end]
    script = f"""
function normalizedAiSignalItems(items) {{ return items; }}
function currentAiSignalItems(items) {{ return items; }}
function compactSignalDate(value) {{
  const match = String(value || "").match(/^(\\d{{4}})-(\\d{{2}})-(\\d{{2}})/);
  return match ? `${{match[1]}}.${{match[2]}}.${{match[3]}}` : "날짜 확인 중";
}}
function homeAiSignalView(item) {{
  return {{
    key: "recent-buy",
    label: "예비 매수",
    preliminary: true,
    signalDate: item.signal_date,
    signalAt: item.signal_at,
  }};
}}
{function_source}
const [result] = homeMarketSignalItems([{{
  code: "035420",
  name: "NAVER",
  signal_date: "2026-08-18",
  signal_at: "2026-08-18T10:05:56+09:00",
  current: {{
    action: "entry_pending",
    lifecycle: {{
      latest_transition: {{
        label: "전략상 청산",
        side: "sell",
        transition_date: "2026-02-19",
      }},
    }},
  }},
}}]);
console.log(JSON.stringify(result.tickerSignal));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "label": "예비 매수",
        "side": "buy",
        "date": "2026.08.18",
        "preliminary": True,
    }


def test_signal_and_recommendation_history_dates_always_include_year() -> None:
    source = app_source()
    helper_start = source.index("function formatDottedDate(")
    helper_end = source.index("function formatDateOnlyBasis(", helper_start)
    compact_start = source.index("function compactSignalDate(")
    compact_end = source.index("function homeMarketSignalItems(", compact_start)
    quant_start = source.index("function formatQuantActionDate(")
    quant_end = source.index("function quantSignalCurrentState(", quant_start)
    recommendation_start = source.index("function recommendationMoment(")
    recommendation_end = source.index("function recommendationReleasedPreliminary(", recommendation_start)
    function_source = "\n".join((
        source[helper_start:helper_end],
        source[compact_start:compact_end],
        source[quant_start:quant_end],
        source[recommendation_start:recommendation_end],
    ))
    script = f"""
function formatDateLabel(value) {{
  return value ? String(value).replace("T", " ").slice(0, 10) : "-";
}}
{function_source}
console.log(JSON.stringify({{
  activeSignal: compactSignalDate("2026-08-20T12:56:00+09:00"),
  releasedSignal: compactSignalDate("2025-02-27"),
  tradeJournal: formatQuantActionDate("2024-12-03"),
  recommendationTrade: recommendationMoment("2026-06-17T15:40:00+09:00"),
  recommendationDateOnly: recommendationMoment("2025-01-30"),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "activeSignal": "2026.08.20",
        "releasedSignal": "2025.02.27",
        "tradeJournal": "2024.12.03",
        "recommendationTrade": "2026.06.17 15:40",
        "recommendationDateOnly": "2025.01.30",
    }


def test_recommendation_signal_stage_uses_only_post_recommendation_trade_state() -> None:
    source = app_source()
    start = source.index("function recommendationTimestampValue(")
    end = source.index("function recommendationAiSignalStageView(", start)
    function_source = source[start:end]
    script = f"""
{function_source}
const recommendation = {{ recommended_at: "2026-08-21T07:43:00+09:00" }};
function readySignal(action, transitionAt, positionOpen = false) {{
  return {{
    data_state: "ready",
    current: {{
      action,
      position_open: positionOpen,
      next_confirmation: "종가 진입 조건 확인",
      lifecycle: {{
        latest_transition: transitionAt ? {{ signal_at: transitionAt, label: action === "exited" ? "전량 매도" : "확정 매수" }} : {{}},
      }},
    }},
  }};
}}
console.log(JSON.stringify({{
  oldExit: recommendationSignalStageView(
    readySignal("exited", "2026-06-17T15:40:00+09:00"),
    recommendation,
  ),
  newExit: recommendationSignalStageView(
    readySignal("exited", "2026-08-21T15:40:00+09:00"),
    recommendation,
  ),
  activePosition: recommendationSignalStageView(
    readySignal("holding", "2026-06-16T15:40:00+09:00", true),
    recommendation,
  ),
  outsideRecommendation: recommendationSignalStageView(
    readySignal("exited", "2026-06-17T15:40:00+09:00"),
  ),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["oldExit"] == {
        "key": "collecting",
        "headline": "시그널 수집 중",
        "tone": "collecting",
        "changedAt": "2026-08-21T07:43:00+09:00",
        "changedLabel": "수집 시작",
        "next": "종가 진입 조건 확인",
    }
    assert result["newExit"]["key"] == "sold"
    assert result["activePosition"]["key"] == "holding"
    assert result["outsideRecommendation"]["key"] == "sold"


def test_recommendation_reason_summary_puts_comparable_evidence_first() -> None:
    source = app_source()
    start = source.index("function recommendationReasonFacts(")
    end = source.index("function recommendationCandidateStageView(", start)
    function_source = source[start:end]
    script = f"""
function toNumber(value) {{
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}}
function formatPercent(value) {{
  const number = Number(value);
  return `${{number >= 0 ? "+" : ""}}${{number.toFixed(2)}}%`;
}}
function formatNumber(value) {{ return String(Number(value)); }}
{function_source}
console.log(recommendationReasonSummary({{
  one_month_return: 44.85,
  three_month_return: 58.28,
  chart_analysis: {{ score: 73, trend: "상승 추세" }},
  decision_reason: "단기 상승 부담으로 분할 접근합니다.",
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "1개월 +44.85% · 3개월 +58.28% · 차트 73점 · 상승 추세"


def test_recommendation_live_quote_preserves_snapshot_momentum_evidence() -> None:
    source = app_source()
    start = source.index("function updateRecommendationCardQuote(")
    end = source.index("function connectRecommendationQuoteStream(", start)
    updater = source[start:end]

    assert "item.price = quote.price;" in updater
    assert "item.change_rate = quote.change_rate;" in updater
    assert "rebasePeriodReturn" not in updater
    assert "item.one_month_return =" not in updater
    assert "item.three_month_return =" not in updater


def test_ai_signal_preliminary_buy_hides_previous_trade_metrics() -> None:
    source = app_source()
    sanitizer_start = source.index("function sanitizePendingEntryAiSignal(")
    sanitizer_end = source.index("function combineAiSignalPayloads(", sanitizer_start)
    metrics_start = source.index("function aiSignalTradeContext(")
    metrics_end = source.index("function createAiSignalMetricRow(", metrics_start)
    function_source = source[sanitizer_start:sanitizer_end] + source[metrics_start:metrics_end]
    script = f"""
function homeAiSignalView() {{ return null; }}
function isSignalReconciliation() {{ return false; }}
function toNumber(value) {{
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}}
function formatNumber(value) {{ return String(Number(value)); }}
function formatPercent(value) {{ return `${{Number(value) >= 0 ? "+" : ""}}${{Number(value).toFixed(2)}}%`; }}
{function_source}
const raw = {{
  entry_price: 4830,
  target_sell_price: 5593,
  target_sell_status: "missed",
  target_sell_delta: -603,
  return_rate: 10.21,
  display_return_rate: 10.21,
  display_return_kind: "closed_trade",
  display_return_event_date: "2026-05-29",
  display_return_event_side: "sell",
  status: "preliminary",
  is_preliminary: true,
  score: 84.63,
  current: {{
    action: "entry_pending",
    live_observation: true,
    position_open: false,
    price: 5460,
    entry_price: null,
    target_sell_price: 5593,
    target_sell_status: "missed",
    target_sell_delta: -603,
    lifecycle: {{ latest_transition: {{ side: "sell", entry_price: 4830, target_sell_price: 5593 }} }},
  }},
}};
const sanitized = sanitizePendingEntryAiSignal(raw);
const view = {{ key: "recent-buy", label: "예비 매수", preliminary: true }};
console.log(JSON.stringify({{
  metrics: aiSignalDetailMetrics(sanitized, view),
  entryPrice: sanitized.entry_price,
  targetPrice: sanitized.target_sell_price,
  returnRate: sanitized.display_return_rate,
  currentTarget: sanitized.current.target_sell_price,
  historicalEntry: sanitized.current.lifecycle.latest_transition.entry_price,
  originalEntry: raw.entry_price,
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "metrics": [
            {"key": "price", "label": "예상 매수가", "value": "확인 중"},
            {"key": "score", "label": "점수", "value": "84.63점"},
            {"key": "execution", "label": "체결 기준", "value": "다음 거래일 시가"},
        ],
        "entryPrice": None,
        "targetPrice": None,
        "returnRate": None,
        "currentTarget": None,
        "historicalEntry": 4830,
        "originalEntry": 4830,
    }


def test_confirmed_signal_date_and_key_do_not_follow_live_observation_time() -> None:
    source = app_source()
    start = source.index("function isPreliminaryAiSignal(")
    end = source.index("function isCurrentAiSignalHolding(", start)
    function_source = source[start:end]
    script = f"""
{function_source}
function signal(liveObservation, asOf) {{
  return {{
    code: "090430",
    current: {{
      action: "holding",
      position_open: true,
      live_observation: liveObservation,
      as_of: asOf,
      lifecycle: {{
        latest_transition: {{
          label: "확정 매수",
          side: "buy",
          signal_at: "2026-07-29T15:40:00+09:00",
          signal_date: "2026-07-29",
          transition_date: "2026-07-30",
        }},
      }},
    }},
  }};
}}
const morning = signal(true, "2026-08-21T09:24:00+09:00");
const afternoon = signal(false, "2026-08-21T15:40:00+09:00");
console.log(JSON.stringify({{
  morningView: homeAiSignalView(morning),
  afternoonView: homeAiSignalView(afternoon),
  morningKey: aiSignalTransitionKey(morning),
  afternoonKey: aiSignalTransitionKey(afternoon),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["morningView"]["preliminary"] is False
    assert result["morningView"]["signalDate"] == "2026-07-29"
    assert result["afternoonView"]["signalDate"] == "2026-07-29"
    assert result["morningKey"] == "090430:confirmed:buy:2026-07-30"
    assert result["afternoonKey"] == result["morningKey"]


def test_public_ai_signal_items_are_identical_for_different_accounts() -> None:
    source = app_source()
    preliminary_start = source.index("function isPreliminaryAiSignal(")
    preliminary_end = source.index("function isSignalReconciliation(", preliminary_start)
    market_start = source.index("function marketAiSignalItems(")
    market_end = source.index("function combineAiSignalPayloads(", market_start)
    combine_start = source.index("function combineAiSignalPayloads(")
    combine_end = source.index("function preliminaryHistoryAiSignalItems(", combine_start)
    function_source = "\n".join((
        source[preliminary_start:preliminary_end],
        source[market_start:market_end],
        source[combine_start:combine_end],
    ))
    script = f"""
{function_source}
const market = {{
  status: "ready",
  as_of: "2026-08-21T12:20:00+09:00",
  items: [{{
    code: "090430",
    name: "아모레퍼시픽",
    side: "buy",
    signal: "확정 매수",
    signal_date: "2026-07-29",
    execution_date: "2026-07-30",
    price: 121900,
    entry_price: 121900,
    status: "confirmed",
    is_preliminary: false,
  }}],
}};
const venti = combineAiSignalPayloads({{ items: [{{ code: "088350", name: "한화생명" }}] }}, market);
const other = combineAiSignalPayloads({{ items: [{{ code: "005930", name: "삼성전자" }}] }}, market);
const stale = combineAiSignalPayloads({{ items: [] }}, {{
  status: "refreshing",
  items: [
    ...market.items,
    {{ code: "035420", name: "NAVER", side: "buy", signal_date: "2026-08-21", status: "preliminary", is_preliminary: true }},
  ],
}});
console.log(JSON.stringify({{
  samePublicItems: JSON.stringify(venti.items) === JSON.stringify(other.items),
  ventiCodes: venti.items.map((item) => item.code),
  otherCodes: other.items.map((item) => item.code),
  personalizedCodes: [venti.watchlist_items[0].code, other.watchlist_items[0].code],
  staleCodes: stale.items.map((item) => item.code),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "samePublicItems": True,
        "ventiCodes": ["090430"],
        "otherCodes": ["090430"],
        "personalizedCodes": ["088350", "005930"],
        "staleCodes": ["090430"],
    }


def test_public_market_signal_cache_is_shared_while_watchlist_cache_is_scoped() -> None:
    source = app_source()
    start = source.index("function readCachedHomeAiSignals(")
    end = source.index("function pushEnabledStorageKey(", start)
    function_source = source[start:end]
    script = f"""
const HOME_AI_SIGNALS_MARKET_CACHE_KEY = "analyst.homeAiSignals.market.v2";
const HOME_AI_SIGNALS_WATCHLIST_CACHE_PREFIX = "analyst.homeAiSignals.watchlist.v2";
const HOME_AI_SIGNALS_CACHE_MAX_AGE_MS = 120000;
const HOME_MARKET_SIGNAL_RECENT_DAYS = 30;
const state = {{ watchlistId: "venti.ice" }};
const storage = new Map();
function scopedStorageKey(prefix, shareId = state.watchlistId) {{
  return shareId ? `${{prefix}}.${{shareId}}` : "";
}}
function readStoredJson(key, fallback = null) {{
  return key && storage.has(key) ? JSON.parse(storage.get(key)) : fallback;
}}
function writeStoredJson(key, value) {{
  if (key) storage.set(key, JSON.stringify(value));
}}
{function_source}
writeCachedHomeAiSignals({{
  as_of: "2026-08-21T12:20:00+09:00",
  items: [{{ code: "090430" }}],
  market_items: [{{ code: "090430" }}],
  watchlist_items: [{{ code: "088350" }}],
}}, 30);
state.watchlistId = "another";
const beforeAnotherWrite = readCachedHomeAiSignals(30);
writeCachedHomeAiSignals({{
  as_of: "2026-08-21T12:20:00+09:00",
  items: [{{ code: "090430" }}],
  market_items: [{{ code: "090430" }}],
  watchlist_items: [{{ code: "005930" }}],
}}, 30);
const another = readCachedHomeAiSignals(30);
state.watchlistId = "venti.ice";
const venti = readCachedHomeAiSignals(30);
console.log(JSON.stringify({{
  marketKeyCount: [...storage.keys()].filter((key) => key === HOME_AI_SIGNALS_MARKET_CACHE_KEY).length,
  beforeAnotherMarket: beforeAnotherWrite.market_items.map((item) => item.code),
  beforeAnotherWatchlist: beforeAnotherWrite.watchlist_items,
  anotherMarket: another.market_items.map((item) => item.code),
  ventiMarket: venti.market_items.map((item) => item.code),
  anotherWatchlist: another.watchlist_items.map((item) => item.code),
  ventiWatchlist: venti.watchlist_items.map((item) => item.code),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "marketKeyCount": 1,
        "beforeAnotherMarket": ["090430"],
        "beforeAnotherWatchlist": [],
        "anotherMarket": ["090430"],
        "ventiMarket": ["090430"],
        "anotherWatchlist": ["005930"],
        "ventiWatchlist": ["088350"],
    }


def test_confirmed_holding_card_uses_separate_live_basis_during_preliminary_exit() -> None:
    source = app_source()
    market_start = source.index("function marketAiSignalItems(")
    market_end = source.index("function combineAiSignalPayloads(", market_start)
    live_start = source.index("function aiSignalLiveReturnRate(")
    live_end = source.index("function applyStockQuantSignalLiveQuote(", live_start)
    function_source = source[market_start:market_end] + source[live_start:live_end]
    script = f"""
function toNumber(value) {{
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}}
function isCurrentAiSignalHolding(item = {{}}) {{
  return item.is_current_holding === true || item.current?.position_open === true;
}}
{function_source}
const [item] = marketAiSignalItems({{
  as_of: "2026-08-21T13:20:00+09:00",
  items: [{{
    code: "010950",
    name: "S-Oil",
    side: "buy",
    event_side: "buy",
    signal_date: "2026-08-18",
    execution_date: "2026-08-19",
    price: 80500,
    entry_price: 80500,
    display_return_rate: -7.03,
    display_return_kind: "open_position",
    status: "confirmed",
    is_preliminary: false,
    is_current_holding: true,
    holding_context: {{
      price: 80000,
      entry_price: 80500,
      unrealized_return: -7.03,
      return_basis: {{
        price: 80000,
        return_rate: -7.03,
        return_rate_per_price: 0.001,
      }},
    }},
  }}],
}});
console.log(JSON.stringify({{
  action: item.current.action,
  preliminary: item.is_preliminary,
  holding: isCurrentAiSignalHolding(item),
  holdingBasis: item.holding_context.return_basis.return_rate,
  liveReturn: aiSignalLiveReturnRate(item, {{ price: 81000 }}),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "action": "entered",
        "preliminary": False,
        "holding": True,
        "holdingBasis": -7.03,
        "liveReturn": -6.03,
    }


def test_home_watchlist_impact_omits_ranked_market_factor_list() -> None:
    source = app_source()
    shell = (APP_JS.parent / "index.html").read_text(encoding="utf-8")
    styles = dashboard_styles()
    card_start = styles.rindex('body:not([data-view="stock"]) .home-ai-response {')
    card_rule = styles[card_start:styles.index("}\n", card_start) + 1]

    assert "min-height" not in card_rule
    assert 'id="home-ai-response-factors"' not in shell
    assert "home-ai-response-factor-rank" not in shell
    assert 'id="home-ai-response-watch-label">관심종목 영향도<' in shell
    assert 'id="home-ai-response-personal-list"' in shell
    assert "homeAiResponseFactors" not in source
    assert "renderHomeInterestMarketFactors" not in source
    assert ".home-ai-response-factors" not in styles
    assert ".home-ai-response-factor-rank" not in styles


def test_home_ai_response_uses_realtime_market_context() -> None:
    source = app_source()

    assert 'const US_SECTOR_STREAM_VIEWS = new Set(["home", "search", "portfolio"]);' in source
    assert "function majorMarketIssueContext" in source
    assert "function recentMarketNewsContext" in source
    assert "function homeMarketFactScore" in source
    assert "function marketNewsHeadlineSentence" in source
    assert "function isMarketReactionHeadline" in source
    assert "function isFinancialConflictMetaphorHeadline" in source
    assert "function isMilitaryDeescalationHeadline" in source
    assert "function isMilitaryThreatHeadline" in source
    assert "function isFreshHomeMarketNews" in source
    assert "function homeMarketNewsSentence" in source
    assert "function homeMarketEventKey" in source
    assert "function homeMarketEventState" in source
    assert "function consolidatedHomeMarketNews" in source
    assert "function recentMarketNewsContexts" in source
    assert "function majorMarketIssueContexts" in source
    assert "function upcomingMarketEventContexts" in source
    assert "function upcomingMarketEventContext" in source
    assert "function usSectorMarketContexts" in source
    assert "function usSectorMarketContext" in source
    assert "function commodityMarketContexts" in source
    assert "function globalUsMarketContext" in source
    assert "function homeUsMarketSessionLabel" in source
    assert 'return "현재 미국 프리마켓 기준";' in source
    assert 'return "현재 미국장 기준";' in source
    assert 'return "현재 미국 애프터장 기준";' in source
    assert 'return "지난 미국장 기준";' in source
    assert 'dataMode === "latest_regular_close" || session === "closed"' in source
    assert "function selectHomeMarketContexts" in source
    assert "function homeAiMarketJudgment" in source
    assert "function homeAiEvidenceParts" in source
    assert "const contexts = homeInterestMarketContextCandidates();" in source
    assert "const selections = selectHomeInterestMarketContexts(contexts, readWatchlist(), 3);" in source
    assert "renderHomeInterestResponses(selections, items)" in source
    assert "function homeContextResponseAction" in source
    assert "function homeInterestMarketContextCandidates" in source
    assert "function homeInterestItemContextScore" in source
    assert "function homeInterestContextUrgency" in source
    assert "function selectHomeInterestMarketContexts" in source
    assert "function homeInterestVariableType" in source
    assert "function homeInterestResponseItems" in source
    assert "function renderHomeInterestResponses" in source
    assert "function homeAiResponseUpdatedAt(contexts = [], fallback = \"\")" in source
    assert "function formatHomeAiResponseUpdatedAt" in source
    assert "function renderHomeInterestMarketFactors" not in source
    assert "home-ai-response-factor-rank" not in source
    assert 'elements.homeAiResponseWatchLabel.textContent = responses.length' in source
    assert 'elements.homeAiResponseWatch.setAttribute("aria-label", "관심종목 영향도 전체보기");' in source
    assert "homeAiResponseEvidence" not in source
    assert "home-ai-response-evidence" not in source
    assert "최근 시장 뉴스:" not in source
    assert "마감/대기" not in source[source.index("function usSectorMarketContext"):source.index("function usSectorDataAsOf")]
    assert "국내 연관 종목의 장중 수급 변화를 확인하세요." not in source
    assert "function isRetrospectiveMajorIssueReference" in source
    assert "!isMarketReactionHeadline(item.title)" in source
    assert "|| isMilitaryDeescalationHeadline(item.title)" in source
    assert "majorIssuePattern.test(item.title) || isMilitaryDeescalationHeadline(item.title)" in source
    assert "!isRetrospectiveMajorIssueReference(item.title)" in source


def test_market_core_only_uses_specific_market_moving_facts() -> None:
    source = app_source()
    start = source.index("function marketNewsHeadlineSentence")
    end = source.index("function isFreshHomeMarketNews", start)
    sentence_builder = source[start:end]
    recent_context_start = source.index("function recentMarketNewsContext")
    recent_context_end = source.index("function isRetrospectiveMajorIssueReference", recent_context_start)
    recent_context = source[recent_context_start:recent_context_end]

    assert '"금융위원회가 증시 긴급조치권 도입을 추진한다는 보도가 나왔습니다."' in sentence_builder
    assert '"트럼프가 전쟁 중단을 선언했다는 보도가 나왔습니다."' in sentence_builder
    assert '"미국이 이란 공습을 취소했다는 보도가 나왔습니다."' in sentence_builder
    assert sentence_builder.index("isMilitaryDeescalationHeadline") < sentence_builder.index("if (/전쟁|공습")
    assert 'return "";' in sentence_builder
    assert "if (isMarketReactionHeadline(headline) && !isDeescalation)" in sentence_builder
    assert 'return "군사 공격 가능성 또는 경고 관련 보도가 나왔습니다.";' in sentence_builder
    assert 'return "환율·통화정책을 둘러싼 정책 변화 가능성이 보도됐습니다.";' in sentence_builder
    assert "!isFinancialConflictMetaphor" in source
    assert 'return "fx:policy";' in source
    assert "&& !isFinancialConflictMetaphorHeadline(item.title)" in source
    assert "consolidatedHomeMarketNews(payload, now)" in recent_context
    assert "factScore: homeMarketFactScore(item)" in recent_context
    assert "item.factScore >= 6 && item.sentence" in recent_context
    assert "HOME_MARKET_NEWS_MAX_AGE_MS = 6 * 60 * 60 * 1000" in source
    assert "HOME_DEESCALATION_NEWS_MAX_AGE_MS = 4 * 60 * 60 * 1000" in source
    assert "now + 7 * 24 * 60 * 60 * 1000" in source
    assert "(importanceScore[event.importance] || 0) >= 2" in source


def test_home_trend_payload_refreshes_ai_response() -> None:
    source = app_source()
    refresh_start = source.index("function refreshHomeAiResponseContext")
    refresh_end = source.index("function renderHomeAiResponse", refresh_start)
    refresh_logic = source[refresh_start:refresh_end]

    assert "state.homeTrendContext = payload;" in source
    assert 'if (state.view === "home") {\n      renderHomeAiResponse();' in source
    assert "function refreshHomeAiResponseContext" in source
    assert "state.homeAiResponseRefreshPromise" in refresh_logic
    assert "Promise.allSettled(requests)" in refresh_logic
    assert "loadHomeAiSignals({ force, ttlMs: 0 })" in refresh_logic
    assert "loadTrends(trendTab, { force, ttlMs: 0 })" in refresh_logic
    assert "loadHomeMarketImpact({ force, ttlMs: 0 })" in refresh_logic
    assert "refreshUsSectorMoves({ force, ttlMs: 0 })" in refresh_logic
    assert 'quant-signals${force ? "?refresh=1" : ""}' in source
    assert 'liveUrl("/market/trends?days=7&refresh=true")' in source
    assert "startHomeAiResponseRefresh();" in source
    assert "connectUsSectorStream();" in source


def test_market_context_priority_is_explicit() -> None:
    source = app_source()
    start = source.index("function selectHomeMarketContexts()")
    end = source.index("function normalizedHomeThemes", start)
    selector = source[start:end]
    candidate_order = selector[selector.index("const candidates ="):]

    assert selector.index("majorMarketIssueContext") < selector.index("usSectorMarketContext")
    assert selector.index("recentMarketNewsContext") < selector.index("usSectorMarketContext")
    assert candidate_order.index("majorIssue") < candidate_order.index("marketNews")
    assert candidate_order.index("marketNews") < candidate_order.index("event")
    assert candidate_order.index("event") < candidate_order.index("sector || globalIndex")
    assert "context.eventKey || context.id" in selector
    assert "slice(0, 3)" in selector


def test_home_ai_response_keeps_market_data_in_the_data_panels() -> None:
    source = app_source()

    assert "function homeMarketVolatilitySentence" in source
    assert "function homeAiResponseBasisLabel" not in source


def test_home_ai_response_shows_update_time_and_market_based_watchlist_action() -> None:
    source = app_source()
    shell = (APP_JS.parent / "index.html").read_text(encoding="utf-8")
    styles = dashboard_styles()

    assert 'id="home-ai-response-asof"' in shell
    assert '>시장 변수<' not in shell
    assert 'id="home-ai-response-factors"' not in shell
    assert 'aria-label="관심종목에 중요한 변화"' not in shell
    assert '확인 근거' not in shell
    assert 'home-ai-response-evidence' not in shell
    assert 'id="home-ai-response-watch-label">관심종목 영향도<' in shell
    assert 'id="home-ai-response-personal-list"' in shell
    assert "context?.kind !== \"event\"" in source
    assert "const contextCandidates = contexts" in source
    assert "state.homeTrendContext?.as_of" in source
    assert "state.homeAiSignalsAsOf" in source
    assert "return [state.homeTrendContext?.as_of, state.homeAiSignalsAsOf, fallback]" in source
    assert "헤드라인보다 지수·유가 반응을 우선 보세요." in source
    assert "뉴스만으로 비중을 바꾸지 마세요." in source
    assert "EIA 재고 결과 뒤 WTI와 에너지 업종이 같은 방향인지 확인하고" in source
    assert "직접 연관된 관심종목은 없습니다." not in source
    assert "확정 매도 신호를 우선해 뉴스 반등만으로 재진입하지 마세요." not in source
    assert "재진입을 서두르지 마세요." not in source
    assert "AI 확정 매도 상태 · 신호 발생 이후 가격과 거래대금 변화를 추적 중입니다." in source
    assert "AI 예비 매도 상태 · 15:40 확정 전까지 결과가 바뀔 수 있습니다." in source
    assert "AI 예비 매수 상태 · 15:40 확정 전까지 결과가 바뀔 수 있습니다." in source
    assert "나스닥과 비트코인이 함께 강하고 VIX가 내려" not in source
    assert "미국 기술주와 가상자산은 강세이고, 시장 불안 지표는 낮아" in source
    assert "미국 증시 불안지수(VIX)" in source
    assert 'return String(context.sentence || context.title || "투자심리 변화를 확인 중입니다.").trim();' in source
    assert "compactMarketHeadline(context.sentence || context.title, 48)" not in source
    assert '.home-ai-response > header time {' in styles
    assert '.home-ai-response-factors {' not in styles
    assert '.home-ai-response-factor-rank {' not in styles
    assert '.home-ai-interest-row {' in styles
    assert '.home-ai-interest-action {' in styles


def test_home_ai_response_synthesizes_news_price_and_event_state() -> None:
    source = app_source()

    assert "const context = payload || {};" in source
    assert 'return `military:${actors.sort().join("-")' in source
    assert 'return "resolved";' in source
    assert 'return "threat";' in source
    assert "item.timestamp > current.timestamp" in source
    assert "eventKey: item.eventKey" in source
    assert "sourceCount: item.sourceCount" in source
    assert "미국 지수·업종 전반에서 확인됐습니다." in source
    assert "EIA 전까지 정유·항공 변동성은 열어두세요." in source
    assert "보도 ${news.sourceCount}건 최신 상태 통합" in source


def test_home_ai_response_is_personalized_from_interest_stocks_and_dominant_event() -> None:
    source = app_source()
    shell = (APP_JS.parent / "index.html").read_text(encoding="utf-8")
    styles = dashboard_styles()

    start = source.index("function homeInterestMarketContextCandidates")
    end = source.index("function homeAiResponseUpdatedAt", start)
    interest_logic = source[start:end]

    assert "...homeDirectInterestNewsContexts(state.homeTrendContext, watchlist)" in interest_logic
    assert "...majorMarketIssueContexts().slice(0, 10)" in interest_logic
    assert "...recentMarketNewsContexts().slice(0, 12)" in interest_logic
    assert "...upcomingMarketEventContexts().slice(0, 10)" in interest_logic
    assert "...macroMarketContexts()" in interest_logic
    assert "...usSectorMarketContexts().slice(0, 12)" in interest_logic
    assert "...commodityMarketContexts()" in interest_logic
    assert "watchlist = readWatchlist()" in interest_logic
    assert "homeInterestItemContextScore(item, context)" in interest_logic
    assert "strongestRelation + Math.min(36, directCoverage * 12) + homeInterestContextUrgency(context)" in interest_logic
    assert "Math.min(3, Math.floor(toNumber(limit) || 3))" in interest_logic
    assert ".filter((selection) => selection.matches.some((match) => match.relation >= 60))" in interest_logic
    assert "const ranked = contexts" in interest_logic
    assert "const seenExposure = new Set();" in interest_logic
    assert "const seenFamilies = new Set();" in interest_logic
    assert "addSelection(selection, true);" in interest_logic
    assert "requireNewFamily && seenFamilies.has(family)" in interest_logic
    assert "homeInterestVariableType(selection.context)" in interest_logic
    assert "seenExposure.has(exposureKey)" in interest_logic
    assert "selected.length >= normalizedLimit" in interest_logic
    assert "if (name && contextText.includes(name))" in interest_logic
    assert 'context.kind === "company-news" ? 150 : 130' in interest_logic
    assert 'context.kind !== "market-news"' in interest_logic
    assert "const themeMatches = theme !== \"기타\"" in interest_logic
    assert "&& themeMatches" in interest_logic
    assert 'if (context.kind === "event") return 100;' in interest_logic
    assert 'if (context.kind === "macro-factor") return 108;' in interest_logic
    assert 'if (context.kind === "us-sector") return 105;' in interest_logic
    assert 'if (context.kind === "commodity") return 98;' in interest_logic
    assert 'if (context.kind === "market-news") return 70;' in interest_logic
    assert 'if (["major-issue", "market-news"].includes(context.kind)) return "뉴스";' in interest_logic
    assert 'if (context.kind === "company-news") return context.sourceType || "기업";' in interest_logic
    assert 'if (context.kind === "us-sector") return "업종";' in interest_logic
    assert 'if (context.kind === "us-index") return "미장";' in interest_logic
    assert 'if (context.kind === "macro-factor") return context.label || "거시";' in interest_logic
    assert 'if (context.kind === "commodity") return "원자재";' in interest_logic
    assert 'if (context.kind === "event") return "일정";' in interest_logic
    assert '`${context.basisLabel || "지난 미국장 기준"} · 미국 ${sector} ${formatPercent(context.rate)}`' in interest_logic
    assert '`${context.basisLabel || "지난 미국장 기준"} · ${context.marketLabel || "미국 지수"} ${formatPercent(context.rate)}`' in interest_logic
    assert 'const isDirect = context.kind === "company-news"' in interest_logic
    assert 'match.relation >= 60 ? "민감 업종" : "참고"' in interest_logic
    assert "const responseLimit = 2;" in interest_logic
    assert "candidates.length >= responseLimit" in interest_logic
    assert 'row.href = viewStockUrl(item.code || item.name || "");' in interest_logic
    assert '`${homeInterestContextLabel(selection.context)} · ${watchlistTheme(match.item)} 연관' in interest_logic
    assert '"현재 관심종목과 직접 연결되는 주요 이벤트가 없습니다. 새로운 뉴스·일정이 확인되면 바로 반영합니다."' in interest_logic
    assert "function isUserHoldingSignal" not in source
    assert "function homeHoldingContextScore" not in source
    assert "function homeHoldingResponseItems" not in source

    assert ">AI 관심종목 대응<" in shell
    assert '>관심종목 영향도<' in shell
    assert ">관심종목 전체보기<" in shell
    assert 'id="home-ai-response-factors"' not in shell
    assert '확인 근거' not in shell
    assert 'home-ai-response-evidence' not in shell
    assert ".home-ai-response-personal > header > button" in styles
    assert "min-height: 44px;" in styles
    assert ".home-ai-interest-row" in styles
    assert 'if (theme === "정유")' in source
    assert 'if (theme === "항공")' in source
    assert 'if (theme === "해운")' in source
    assert 'entry.kind === "commodity" && entry.code === "OIL"' in source
    assert 'context.kind === "company-news"' in source
    assert 'context.kind === "macro-factor"' in source
    assert 'function loadHomeMarketImpact' in source
    assert 'state.homeMarketImpact = payload;' in source
    assert "loadHomeMarketImpact({ force, ttlMs: 0 })" in source
    assert 'fetchJsonCached("/market/impact"' in source
    assert "JB금융|BNK금융|DGB금융" in source
    assert '`${item.name || "해운주"}: 유가보다 운임과 거래대금이 함께 버티는지를 우선 확인하세요.`' in source
    assert "제품 스프레드와 거래대금 반응" in source
    assert 'aiSignalMatchesStage(item, state.aiSignalStage)' in source
