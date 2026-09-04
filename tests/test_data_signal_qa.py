from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.qa.catalog import load_qa_catalog, render_qa_catalog_markdown
from app.qa.e2e import E2E_CASE_IDS, _navigate_page, _page_url
from app.qa.runner import (
    QaFailure,
    ResultCollector,
    _public_websocket_check,
    _resolve_public_quote_stream_url,
    _validate_public_quote_frame,
    _validate_quote_status_frame,
    _validate_signal_revision_frame,
    redact,
    run_data_signal_qa,
)


@pytest.mark.qa_gate
def test_data_signal_catalog_is_complete_and_machine_readable() -> None:
    payload = load_qa_catalog()
    ids = [case["id"] for case in payload["cases"]]

    assert payload["strategy_version"] == "position-lifecycle-v7.4"
    assert len(ids) == 90
    assert len(ids) == len(set(ids))
    assert {
        "DATA-COM-001",
        "DATA-KIS-005",
        "DATA-DART-003",
        "DATA-LOGO-001",
        "DATA-COM-005",
        "DATA-ETF-001",
        "DATA-FUND-ANALYSIS-001",
        "DATA-FUND-ANALYSIS-002",
        "DATA-CALENDAR-CONTENT-004",
        "DATA-CALENDAR-CONTENT-005",
        "DATA-CALENDAR-CONTENT-006",
        "SIG-ENTRY-001",
        "SIG-ENTRY-004",
        "SIG-EXIT-001",
        "SIG-EXIT-005",
        "SIG-UI-003",
        "SIG-UI-004",
        "SIG-UI-005",
        "SIG-UI-006",
        "SIG-UI-009",
        "SIG-UI-010",
        "SIG-UI-011",
        "SIG-UI-012",
        "SIG-UI-013",
        "SIG-UI-014",
        "SIG-UI-015",
        "SIG-UI-016",
        "SIG-UI-017",
        "SIG-UI-018",
        "SIG-UI-019",
        "SIG-UI-020",
        "SIG-UI-021",
        "SIG-CONTRACT-004",
    }.issubset(ids)
    service_update = next(case for case in payload["cases"] if case["id"] == "SIG-UI-005")
    assert service_update["priority"] == "P1"
    assert service_update["inputs"]["popup_enabled"] is False
    assert service_update["inputs"]["notification_prompt_blocked"] is False
    assert all(case["priority"] in {"P0", "P1", "P2"} for case in payload["cases"])


@pytest.mark.qa_gate
def test_catalog_markdown_is_deterministic_and_traceable() -> None:
    payload = load_qa_catalog()
    first = render_qa_catalog_markdown(payload)
    second = render_qa_catalog_markdown(payload)

    assert first == second
    assert "# 데이터 연동·시그널 판단 QA 카탈로그" in first
    assert "`position-lifecycle-v7.4`" in first
    assert "SIG-CONTRACT-003" in first
    assert "QA 항목: 90개" in first
    assert Path("docs/qa/data-signal-qa-matrix.md").read_text(encoding="utf-8") == first


@pytest.mark.qa_gate
def test_live_ai_signal_cases_trace_order_revision_freeze_and_accessibility() -> None:
    cases = {case["id"]: case for case in load_qa_catalog()["cases"]}
    kis_socket = json.dumps(cases["DATA-KIS-005"], ensure_ascii=False)
    kis_fallback = json.dumps(cases["DATA-KIS-006"], ensure_ascii=False)
    signal_contract = json.dumps(cases["SIG-CONTRACT-003"], ensure_ascii=False)
    signal_ui = json.dumps(cases["SIG-UI-002"], ensure_ascii=False)

    assert cases["DATA-KIS-005"]["modes"] == ["gate", "live"]
    assert "sequence" in kis_socket and "observed_at" in kis_socket
    assert "signal_revision" in kis_socket and "rejected_codes" in kis_socket
    assert "dashboard_meta" in kis_socket
    assert "fallback" in kis_fallback and "status" in kis_fallback
    assert "closed_trade" in signal_contract and "changed_codes" in signal_contract
    assert "aria-live" in signal_ui and "aria-label" in signal_ui
    assert "보유 N개 모두 실시간" in signal_ui
    assert "예외 행만 개별 배지" in signal_ui
    assert "해제 이력에서는 현재 목록 요약을 숨긴다" in signal_ui


@pytest.mark.qa_gate
def test_websocket_control_and_order_frames_have_deterministic_contracts() -> None:
    revision = _validate_signal_revision_frame(
        {
            "type": "signal_revision",
            "revision": 7,
            "as_of": "2026-08-31T09:00:00+09:00",
            "changed_codes": ["005930"],
            "initial": False,
        },
        require_initial=False,
    )
    quote = _validate_public_quote_frame(
        {
            "type": "quote",
            "code": "005930",
            "source": "kis_realtime",
            "sequence": 11,
            "observed_at": "2026-08-31T09:00:00+09:00",
            "published_at": "2026-08-31T09:00:00.020000+09:00",
            "quote": {"price": 106000},
        },
        expected_code="005930",
    )
    status = _validate_quote_status_frame(
        {
            "type": "status",
            "code": "005930",
            "source": "kis_realtime",
            "status": "fallback",
            "message": "fixture outage",
        }
    )

    assert revision == {
        "revision": 7,
        "as_of": "2026-08-31T09:00:00+09:00",
        "changed_codes": ["005930"],
        "initial": False,
    }
    assert quote["sequence"] == 11
    assert quote["observed_at"] < quote["published_at"]
    assert status["status"] == "fallback"
    assert status["has_message"] is True

    with pytest.raises(QaFailure, match="인증정보"):
        _validate_quote_status_frame(
            {
                "type": "status",
                "code": "005930",
                "source": "kis_realtime",
                "status": "fallback",
                "message": "invalid approval : 9fdcb22a-1111-2222-3333-123456789abc",
            }
        )

    with pytest.raises(QaFailure, match="published_at"):
        _validate_public_quote_frame(
            {
                "type": "quote",
                "code": "005930",
                "sequence": 9,
                "observed_at": "2026-08-31T09:00:01+09:00",
                "published_at": "2026-08-31T09:00:00+09:00",
                "quote": {"price": 105000},
            },
            expected_code="005930",
        )
    with pytest.raises(QaFailure, match="revision"):
        _validate_signal_revision_frame(
            {
                "type": "signal_revision",
                "revision": -1,
                "as_of": "2026-08-31T09:00:00+09:00",
                "changed_codes": [],
                "initial": True,
            },
            require_initial=True,
        )


@pytest.mark.qa_gate
@pytest.mark.qa_live
def test_public_websocket_probe_matches_http_revision_and_ack_contract(monkeypatch) -> None:
    class FakeSocket:
        def __init__(self, frames: list[dict[str, object]]):
            self.frames = [json.dumps(frame) for frame in frames]
            self.sent: list[dict[str, object]] = []

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def recv(self, timeout: float) -> str:
            assert timeout == 1
            return self.frames.pop(0)

        def send(self, payload: str) -> None:
            self.sent.append(json.loads(payload))

    first = FakeSocket(
        [
            {"type": "ready", "transport": "multiplex", "max_codes": 64},
            {
                "type": "signal_revision",
                "revision": 7,
                "as_of": "2026-08-31T09:00:00+09:00",
                "changed_codes": [],
                "initial": True,
            },
            {
                "type": "subscribed",
                "codes": ["005930"],
                "count": 1,
                "rejected_codes": [],
            },
            {
                "type": "quote",
                "code": "005930",
                "source": "kis_realtime",
                "sequence": 1,
                "observed_at": "2026-08-31T09:00:00+09:00",
                "published_at": "2026-08-31T09:00:00.010000+09:00",
                "quote": {"price": 105000},
            },
            {
                "type": "subscribed",
                "codes": [],
                "count": 0,
                "rejected_codes": [],
            },
        ]
    )
    second = FakeSocket(
        [
            {"type": "ready", "transport": "multiplex", "max_codes": 64},
            {
                "type": "signal_revision",
                "revision": 7,
                "as_of": "2026-08-31T09:00:00+09:00",
                "changed_codes": [],
                "initial": True,
            },
        ]
    )
    sockets = iter([first, second])
    connected_urls: list[str] = []

    def connect(url: str, *args: object, **kwargs: object):
        connected_urls.append(url)
        return next(sockets)

    monkeypatch.setattr("websockets.sync.client.connect", connect)
    monkeypatch.setattr(
        "app.qa.runner._resolve_public_quote_stream_url",
        lambda *_args, **_kwargs: (
            "wss://canonical-fixture.test/ws/quotes",
            "dashboard_meta",
        ),
    )
    collector = ResultCollector(load_qa_catalog())

    _public_websocket_check(
        collector,
        "https://fixture-staging.test",
        1,
        expected_signal_revision=7,
    )

    [result] = collector.results
    assert result.id == "DATA-KIS-005"
    assert result.status == "pass"
    assert result.evidence["signal_revision"]["revision"] == 7
    assert result.evidence["quote"]["sequence"] == 1
    assert result.evidence["stream_resolution"] == "dashboard_meta"
    assert connected_urls == [
        "wss://canonical-fixture.test/ws/quotes",
        "wss://canonical-fixture.test/ws/quotes",
    ]
    assert first.sent == [
        {"type": "set", "codes": ["005930"]},
        {"type": "set", "codes": []},
    ]


@pytest.mark.qa_gate
@pytest.mark.qa_live
def test_public_websocket_probe_rechecks_http_revision_after_publication_race(monkeypatch) -> None:
    class FakeSocket:
        def __init__(self, frames: list[dict[str, object]]):
            self.frames = [json.dumps(frame) for frame in frames]

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def recv(self, timeout: float) -> str:
            return self.frames.pop(0)

        def send(self, payload: str) -> None:
            return None

    opening = [
        {"type": "ready", "transport": "multiplex", "max_codes": 64},
        {
            "type": "signal_revision",
            "revision": 8,
            "as_of": "2026-08-31T09:00:00+09:00",
            "changed_codes": [],
            "initial": True,
        },
    ]
    first = FakeSocket(
        opening
        + [
            {"type": "subscribed", "codes": ["005930"], "count": 1, "rejected_codes": []},
            {
                "type": "quote",
                "code": "005930",
                "source": "kis_realtime",
                "sequence": 1,
                "observed_at": "2026-08-31T09:00:00+09:00",
                "published_at": "2026-08-31T09:00:00.010000+09:00",
                "quote": {"price": 105000},
            },
            {"type": "subscribed", "codes": [], "count": 0, "rejected_codes": []},
        ]
    )
    second = FakeSocket(opening)
    sockets = iter([first, second])
    monkeypatch.setattr("websockets.sync.client.connect", lambda *_args, **_kwargs: next(sockets))
    monkeypatch.setattr(
        "app.qa.runner._resolve_public_quote_stream_url",
        lambda *_args, **_kwargs: ("wss://canonical-fixture.test/ws/quotes", "dashboard_meta"),
    )

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"signal_revision": 8}

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.qa.runner.httpx.Client", FakeClient)
    collector = ResultCollector(load_qa_catalog())

    _public_websocket_check(
        collector,
        "https://fixture-staging.test",
        1,
        expected_signal_revision=7,
    )

    [result] = collector.results
    assert result.status == "pass", result.message
    assert result.evidence["signal_revision"]["revision"] == 8


@pytest.mark.qa_gate
def test_public_quote_stream_resolution_matches_browser_metadata(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    response_text = (
        '<html><head><meta content="wss://canonical-fixture.test/ws/quotes" '
        'name="secret-note-quote-stream-url" /></head></html>'
    )
    requested: list[str] = []

    def get(url: str, **_kwargs: object) -> FakeResponse:
        requested.append(url)
        return FakeResponse(response_text)

    monkeypatch.setattr("app.qa.runner.httpx.get", get)

    assert _resolve_public_quote_stream_url("https://fixture-staging.test", 2) == (
        "wss://canonical-fixture.test/ws/quotes",
        "dashboard_meta",
    )
    assert requested == ["https://fixture-staging.test/dashboard/005930"]

    response_text = (
        '<meta name="secret-note-quote-stream-url" '
        'content="https://canonical-fixture.test/ws/quotes" />'
    )
    assert _resolve_public_quote_stream_url("https://fixture-staging.test", 2) == (
        "wss://fixture-staging.test/ws/quotes",
        "same_origin",
    )


@pytest.mark.qa_gate
def test_dashboard_quote_order_rejects_lower_sequence_until_stream_epoch_changes() -> None:
    script = r"""
const fs = require("fs");
const source = fs.readFileSync("app/static/dashboard/app.js", "utf8");
const start = source.indexOf("function quoteFrameTimestamp");
const end = source.indexOf("function pauseQuoteStreamConnection", start);
if (start < 0 || end < 0) throw new Error("quote order helpers not found");
const state = { quoteStreamLatestByCode: new Map(), quoteStreamEpoch: 3 };
eval(source.slice(start, end));
const frame = (sequence, observedAt, price, sourceName = "kis_realtime") => ({
  type: "quote",
  code: "005930",
  source: sourceName,
  sequence,
  observed_at: observedAt,
  published_at: observedAt,
  quote: { price, trade_date: "2026-08-31" },
});
const accepted10 = recordQuoteStreamPayload(frame(10, "2026-08-31T09:00:00+09:00", 105000), 1, 3);
const accepted11 = recordQuoteStreamPayload(frame(11, "2026-08-31T09:00:01+09:00", 106000), 2, 3);
const rejected9 = recordQuoteStreamPayload(frame(9, "2026-08-31T09:00:02+09:00", 109000), 3, 3);
const acceptedAfterRestart = recordQuoteStreamPayload(frame(1, "2026-08-31T09:00:03+09:00", 107000), 4, 4);
const rejectedOlderFallback = recordQuoteStreamPayload({
  ...frame(null, "2026-08-31T09:00:02+09:00", 100000, "kis_rest"),
  sequence: undefined,
}, 5, 4);
const rejectedMissingPrice = recordQuoteStreamPayload({
  ...frame(null, "2026-08-31T09:00:04+09:00", null, "stored_daily_price"),
  sequence: undefined,
}, 6, 4);
console.log(JSON.stringify({
  accepted10,
  accepted11,
  rejected9,
  acceptedAfterRestart,
  rejectedOlderFallback,
  rejectedMissingPrice,
  latest: state.quoteStreamLatestByCode.get("005930").payload,
}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "accepted10": True,
        "accepted11": True,
        "rejected9": False,
        "acceptedAfterRestart": True,
        "rejectedOlderFallback": False,
        "rejectedMissingPrice": False,
        "latest": {
            "type": "quote",
            "code": "005930",
            "source": "kis_realtime",
            "sequence": 1,
            "observed_at": "2026-08-31T09:00:03+09:00",
            "published_at": "2026-08-31T09:00:03+09:00",
            "quote": {"price": 107000, "trade_date": "2026-08-31"},
        },
    }


@pytest.mark.qa_gate
def test_dashboard_open_socket_still_falls_back_for_missing_or_stale_prices() -> None:
    source = Path("app/static/dashboard/app.js").read_text(encoding="utf-8")
    usable_start = source.index("function quoteStreamPayloadHasUsablePrice")
    usable_end = source.index("function quoteFrameSequence", usable_start)
    fallback_start = source.index("function quoteStreamFallbackCodes")
    fallback_end = source.index("function scheduleQuoteStreamFallback", fallback_start)
    scheduler_end = source.index("function scheduleQuoteStreamReconnect", fallback_end)
    script = f"""
const QUOTE_STREAM_DETAIL_STALE_MS = 4000;
const QUOTE_STREAM_OTHER_STALE_MS = 15000;
const QUOTE_STREAM_CLOSED_STALE_MS = 60000;
let live = true;
function koreaExtendedQuoteLive() {{ return live; }}
function quoteStreamCodes() {{ return ["005930", "000660", "035420"]; }}
{source[usable_start:usable_end]}
{source[fallback_start:fallback_end]}
const now = 100000;
const state = {{
  quoteStreamScopes: new Map([["detail", new Map([["005930", {{}}]])]]),
  quoteStreamLatestByCode: new Map([
    ["005930", {{ receivedAt: now - 4001, payload: {{ type: "quote", code: "005930", quote: {{ price: 70000 }} }} }}],
    ["000660", {{ receivedAt: now - 14000, payload: {{ type: "quote", code: "000660", quote: {{ price: 200000 }} }} }}],
    ["035420", {{ receivedAt: now, payload: {{ type: "quote", code: "035420", quote: {{ price: null }} }} }}],
  ]),
}};
const duringMarket = quoteStreamFallbackCodes(now);
live = false;
const afterClose = quoteStreamFallbackCodes(now);
console.log(JSON.stringify({{ duringMarket, afterClose }}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "duringMarket": ["005930", "035420"],
        "afterClose": ["035420"],
    }
    scheduler_source = source[fallback_end:scheduler_end]
    assert "readyState === WebSocket.OPEN" not in scheduler_source
    assert "/stocks/quotes?codes=" in scheduler_source


@pytest.mark.qa_gate
def test_dashboard_honors_canonical_quote_websocket_metadata() -> None:
    source = Path("app/static/dashboard/app.js").read_text(encoding="utf-8")
    start = source.index("function socketUrl")
    end = source.index("function selectorEscape", start)
    script = f"""
const window = {{ location: {{ protocol: "https:", host: "staging.example", href: "https://staging.example/dashboard" }} }};
let configured = "wss://secretnote.cloud/ws/quotes";
const document = {{ querySelector() {{ return {{ content: configured }}; }} }};
{source[start:end]}
const upstream = socketUrl("/ws/quotes");
configured = "https://unsafe.example/ws/quotes";
const fallback = socketUrl("/ws/quotes");
console.log(JSON.stringify({{ upstream, fallback }}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "upstream": "wss://secretnote.cloud/ws/quotes",
        "fallback": "wss://staging.example/ws/quotes",
    }


@pytest.mark.qa_gate
def test_nxt_extended_session_quotes_advance_and_accumulate_intraday_chart_minutes() -> None:
    script = r"""
const fs = require("fs");
const source = fs.readFileSync("app/static/staging/toss-ia.js", "utf8");
const start = source.indexOf("  const stagingChartNumeric");
const end = source.indexOf("  const stagingStockWeeklyRows", start);
if (start < 0 || end < 0) throw new Error("staging chart helpers not found");
const STAGING_WEEK_CHART_TTL_MS = 30000;
const stagingWeekChartCache = new Map();
const STAGING_LIVE_INTRADAY_SESSIONS = new Set(["nxt_pre_market", "nxt_after_market"]);
const STAGING_LIVE_INTRADAY_CACHE_KEYS = 8;
const stagingLiveIntradayRows = new Map();
const window = { location: { search: "" }, requestAnimationFrame() {} };
const document = { getElementById() { return null; } };
const state = {
  currentStock: { code: "005930" },
  currentDashboard: { code: "005930" },
  stockIntradayRows: [
    {
      trade_date: "20260901",
      trade_time: "083700",
      price: 259500,
      open: 259500,
      high: 259500,
      low: 259500,
      volume: 10,
    },
  ],
  stockPriceRows: [],
};
const stagingJsonRequest = async () => ({});
const upgradeStagingStockPriceChart = () => {};
const fixture = `
const quote = (price, session = "nxt_pre_market", isLive = true) => ({
  trade_date: "2026-09-01",
  price,
  volume: 100,
  market_session: session,
  is_live: isLive,
});
const at = (time) => ({
  date: "2026-09-01",
  time,
  weekday: "Tue",
  minutes: Number(time.slice(0, 2)) * 60 + Number(time.slice(2, 4)),
});
const pre38 = stagingStockIntradayRows(quote(259000), "preopen", at("083800"));
const pre39 = stagingStockIntradayRows(quote(260000), "preopen", at("083900"));
const same39 = stagingStockIntradayRows(quote(258500), "preopen", at("083900"));
const reference40 = stagingStockIntradayRows(
  quote(260000, "pre_market_reference", false),
  "preopen",
  at("084000"),
);
console.log(JSON.stringify({
  pre38: pre38.map(({ time, price }) => [time, price]),
  pre39: pre39.map(({ time, price }) => [time, price]),
  same39: same39.at(-1),
  reference40: reference40.map(({ time, price }) => [time, price]),
  live: {
    pre: stagingStockChartLiveSession(quote(1), "preopen"),
    reference: stagingStockChartLiveSession(
      quote(1, "pre_market_reference", false),
      "preopen",
    ),
    after: stagingStockChartLiveSession(
      quote(1, "nxt_after_market", true),
      "closed",
    ),
  },
}));
`;
eval(source.slice(start, end) + fixture);
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "pre38": [["083700", 259500], ["083800", 259000]],
        "pre39": [
            ["083700", 259500],
            ["083800", 259000],
            ["083900", 260000],
        ],
        "same39": {
            "date": "2026-09-01",
            "time": "083900",
            "open": 259000,
            "high": 260000,
            "low": 258500,
            "close": 258500,
            "price": 258500,
            "volume": 100,
        },
        "reference40": [["083700", 259500]],
        "live": {"pre": True, "reference": False, "after": True},
    }


@pytest.mark.qa_gate
def test_ai_signal_live_dom_contract_has_status_and_accessible_return_labels() -> None:
    source = Path("app/static/dashboard/app.js").read_text(encoding="utf-8")
    shell = Path("app/static/dashboard/index.html").read_text(encoding="utf-8")

    assert (
        'id="ai-signals-live-status" data-state="checking" data-mixed="false" role="status" '
        'aria-live="polite" aria-atomic="false"'
    ) in shell
    assert shell.index('id="ai-signal-stage-tabs"') < shell.index(
        'id="ai-signals-live-status"'
    ) < shell.index('id="ai-signals-page-list"')
    assert "function aiSignalItemWithLiveOverlay" in source
    assert "function prepareAiSignalEntrySurface" in source
    assert "live_return_pending: true" in source
    assert 'state.stockQuoteReadyCode = normalizedCode;' in source
    assert "function aiSignalFreshnessSummary" in source
    assert "function syncAiSignalFreshnessBadgeVisibility" in source
    assert 'badge.hidden = hideAll || ["realtime", "confirmed"].includes(stateName);' in source
    assert 'elements.aiSignalsLiveStatus.hidden = !showStatus;' in source
    assert "function updateAiSignalQuoteStatus" in source
    assert "state.aiSignalQuoteStatuses" in source
    assert "onStatus: (payload) => updateAiSignalQuoteStatus(code, payload)" in source
    assert "function handleAiSignalRevisionFrame" in source
    assert "function commitAiSignalSnapshot" in source
    for label in (
        "실시간 평가수익률",
        "보유 평가수익률",
        "최근 확인 수익률",
        "확정 수익률",
        "현재가 확인 중",
        "연결 후 확인",
    ):
        assert label in source
    assert 'value.dataset.returnKind = metric.returnKind || "";' in source
    assert 'value.dataset.freshnessState = metric.freshnessState || "";' in source
    assert 'row.setAttribute("aria-label", aiSignalDetailAriaLabel(item, view));' in source


def test_regular_e2e_cases_record_the_current_prompt_week_but_priority_case_does_not() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")

    assert "if dismiss_service_update:" in source
    assert "analyst.pushEntryPromptWeek.v1.{normalized_share_id}" in source
    assert "prompt_week_start = today_kst - timedelta(days=today_kst.weekday())" in source
    assert "prompt_week_start.isoformat()" in source
    assert "dismiss_service_update=False" in source


@pytest.mark.qa_gate
def test_push_entry_prompt_week_resets_only_at_local_monday_boundary() -> None:
    source = Path("app/static/dashboard/app.js").read_text(encoding="utf-8")
    start = source.index("function localCalendarDate")
    end = source.index("function recommendationPushPromptDecisionStorageKey", start)
    script = f"""
const values = new Map();
const localStorage = {{
  getItem(key) {{ return values.has(key) ? values.get(key) : null; }},
  setItem(key, value) {{ values.set(key, String(value)); }},
}};
const state = {{ watchlistId: "weekly-user" }};
const PUSH_ENTRY_PROMPT_WEEK_PREFIX = "analyst.pushEntryPromptWeek.v1";
function scopedStorageKey(prefix, shareId = state.watchlistId) {{
  return shareId ? `${{prefix}}.${{String(shareId).trim()}}` : "";
}}
{source[start:end]}
const monday = new Date(2026, 7, 31, 12, 0, 0);
const sunday = new Date(2026, 8, 6, 23, 59, 59);
const nextMonday = new Date(2026, 8, 7, 0, 0, 0);
const previousSunday = new Date(2026, 7, 30, 12, 0, 0);
recordPushEntryPromptShown(monday);
const firstWeek = {{
  mondayKey: localMondayWeekKey(monday),
  previousSundayKey: localMondayWeekKey(previousSunday),
  monday: pushEntryPromptShownThisWeek(monday),
  sunday: pushEntryPromptShownThisWeek(sunday),
  nextMonday: pushEntryPromptShownThisWeek(nextMonday),
}};
recordPushEntryPromptShown(nextMonday);
console.log(JSON.stringify({{
  firstWeek,
  nextWeekKey: values.get("analyst.pushEntryPromptWeek.v1.weekly-user"),
  nextMondayAfterRecord: pushEntryPromptShownThisWeek(nextMonday),
}}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "firstWeek": {
            "mondayKey": "2026-08-31",
            "previousSundayKey": "2026-08-24",
            "monday": True,
            "sunday": True,
            "nextMonday": False,
        },
        "nextWeekKey": "2026-09-07",
        "nextMondayAfterRecord": True,
    }


def test_e2e_navigation_retries_only_a_document_commit_timeout() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.url = "about:blank"
            self.goto_calls: list[tuple[str, str]] = []
            self.selector_calls: list[tuple[str, str]] = []

        def goto(self, url: str, *, wait_until: str):
            self.goto_calls.append((url, wait_until))
            if len(self.goto_calls) == 1:
                raise TimeoutError("fixture commit timeout")
            self.url = url
            return {"status": 200}

        def wait_for_selector(self, selector: str, *, state: str):
            self.selector_calls.append((selector, state))

    page = FakePage()
    response = _navigate_page(
        page,
        "https://fixture.test/dashboard?view=home",
        ready_selector="body[data-view='home']",
    )

    assert response == {"status": 200}
    assert page.goto_calls == [
        ("https://fixture.test/dashboard?view=home", "commit"),
        ("https://fixture.test/dashboard?view=home", "commit"),
    ]
    assert page.selector_calls == [("body[data-view='home']", "attached")]
    assert page._qa_navigation_retry_evidence == [
        {
            "action": "goto",
            "attempt": 1,
            "wait_until": "commit",
            "reason": "navigation_timeout",
        }
    ]


def test_e2e_navigation_does_not_replay_a_committed_page_on_app_timeout() -> None:
    class FakePage:
        url = "about:blank"

        def __init__(self) -> None:
            self.goto_calls = 0

        def goto(self, url: str, *, wait_until: str):
            self.goto_calls += 1
            self.url = url
            return {"status": 200, "wait_until": wait_until}

        def wait_for_selector(self, _selector: str, *, state: str):
            assert state == "attached"
            raise TimeoutError("fixture app readiness timeout")

    page = FakePage()
    with pytest.raises(QaFailure, match="앱 준비 상태") as exc_info:
        _navigate_page(
            page,
            "https://fixture.test/dashboard?view=search",
            ready_selector="body[data-view='search']",
        )

    assert page.goto_calls == 1
    assert exc_info.value.evidence["ready_selector"] == "body[data-view='search']"


def test_e2e_navigation_keeps_retry_evidence_on_terminal_timeout() -> None:
    class FakePage:
        url = "about:blank"

        def goto(self, _url: str, *, wait_until: str):
            assert wait_until == "commit"
            raise TimeoutError("fixture commit timeout")

    with pytest.raises(QaFailure, match="반복 초과") as exc_info:
        _navigate_page(FakePage(), "https://fixture.test/dashboard")

    evidence = exc_info.value.evidence
    assert evidence["attempts"] == 2
    assert [item["attempt"] for item in evidence["navigation_retries"]] == [1, 2]


def test_e2e_reload_retries_commit_without_replaying_app_readiness() -> None:
    class FakePage:
        url = "https://fixture.test/dashboard?view=home"

        def __init__(self) -> None:
            self.reload_calls = 0
            self.selector_calls = 0

        def reload(self, *, wait_until: str):
            assert wait_until == "commit"
            self.reload_calls += 1
            if self.reload_calls == 1:
                raise TimeoutError("fixture reload commit timeout")
            return {"status": 200}

        def wait_for_selector(self, selector: str, *, state: str):
            assert selector == "body[data-view='home']"
            assert state == "attached"
            self.selector_calls += 1

    page = FakePage()
    assert _navigate_page(
        page,
        ready_selector="body[data-view='home']",
    ) == {"status": 200}
    assert page.reload_calls == 2
    assert page.selector_calls == 1


def test_e2e_navigation_propagates_non_timeout_errors_and_rejects_load_waits() -> None:
    class BrokenPage:
        url = "about:blank"

        def goto(self, url: str, *, wait_until: str):
            self.url = url
            assert wait_until == "commit"
            return {"status": 200}

        def wait_for_selector(self, _selector: str, *, state: str):
            assert state == "attached"
            raise RuntimeError("fixture page crashed")

    page = BrokenPage()
    with pytest.raises(RuntimeError, match="page crashed"):
        _navigate_page(
            page,
            "https://fixture.test/dashboard",
            ready_selector="body[data-view='home']",
        )

    with pytest.raises(ValueError, match="only valid before document commit"):
        _navigate_page(
            page,
            "https://fixture.test/dashboard",
            wait_until="domcontentloaded",
        )


def test_portfolio_production_screens_are_registered_for_e2e() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")

    assert "SIG-UI-016" in E2E_CASE_IDS
    assert "SIG-UI-017" in E2E_CASE_IDS
    assert "SIG-UI-018" in E2E_CASE_IDS
    assert "SIG-UI-019" in E2E_CASE_IDS
    assert "SIG-UI-020" in E2E_CASE_IDS
    assert "SIG-UI-021" in E2E_CASE_IDS
    assert "def portfolio_production_screens_case" in source
    assert "feature-ai-signals-production.jpg" in source
    assert "매수 확정 종목의 전략 기준가와 수익률" in source
    assert "def stock_title_logo_case" in source
    assert '("278470", "official")' in source
    assert '("014950", "fallback")' in source
    assert '"title_logo": title_logo' in source
    assert "title_alignment" in source
    assert 'signal_label_result["case_id"] = "SIG-UI-021"' in source
    assert "부분 매도 대기(2차)" in source
    assert "부분 수익 확정(2차)" in source


def test_gpt_briefing_copy_contract_is_registered_for_e2e() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")

    assert "SIG-UI-018" in E2E_CASE_IDS
    assert "def staging_gpt_briefing_copy_case" in source
    assert 'request.get("page_type") != "briefing_edition"' in source
    assert 'request.get("facts", {}).get("edition")' in source
    assert 'visibleModelWords: /GPT|문구 정리|데이터 요약/.test' in source


def test_gpt_recommendation_detail_isolated_from_live_quote_updates() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")
    case_source = source.split("def staging_gpt_detail_copy_case", 1)[1].split(
        "def staging_gpt_briefing_copy_case", 1
    )[0]

    assert 'page.route_web_socket(' in case_source
    assert '"**/stocks/quotes*"' in case_source
    assert '"**/stocks/105560/quote*"' in case_source
    assert "content?.dataset.summaryDisplay === 'ready'" in case_source


def test_ai_signal_live_return_contract_is_registered_for_e2e() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")

    assert "SIG-CONTRACT-003" in E2E_CASE_IDS
    assert "live_return_contract = page.evaluate(" in source
    assert "quote('005930', 10, 105000" in source
    assert "quote('005930', 11, 106000" in source
    assert "quote('005930', 9, 109000" in source
    assert "status: 'fallback'" in source
    assert "status: 'recovered'" in source
    assert 'ariaLive' in source and 'ariaAtomic' in source


def test_stock_detail_e2e_waits_for_async_market_session_metadata() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")
    case_source = source.split("def search_stock_case", 1)[1].split(
        "def signal_filter_case", 1
    )[0]

    assert "state.currentDashboard?.quote" in case_source
    assert "#stock-market-status-label" in case_source
    assert "page.wait_for_function(" in case_source
    assert "displayedPrice === price" in case_source
    assert "displayedSession.includes(sessionLabel)" in case_source
    assert '"observed_quote": observed_quote' in case_source
    assert 'arg=samsung["price"]' not in case_source


def test_ai_signal_e2e_compares_one_live_revision_instead_of_stale_counts() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")
    case_source = source.split("def signal_filter_case", 1)[1].split(
        "def stock_case", 1
    )[0]

    assert "ui_signal_snapshot = page.evaluate(" in case_source
    assert "aiSignalModeCounts(state.aiSignalItems)" in case_source
    assert "domModeCounts" in case_source
    assert "stageCounts" in case_source
    assert "Number.isSafeInteger(state.aiSignalRevision)" in case_source
    assert '"ui_snapshot": ui_signal_snapshot' in case_source
    assert 'arg=market_signals["current_count"]' not in case_source
    assert 'ui_signal_snapshot["revision"],' not in case_source


def test_sticky_signal_controls_wait_for_page_load_not_a_stale_snapshot_count() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")
    case_source = source.split("def stacked_signal_controls_case", 1)[1].split(
        "def home_market_carousel_motion_case", 1
    )[0]

    assert "불러오는 중입니다." in case_source
    assert 'arg=market_signals["current_count"]' not in case_source
    assert 'data-ai-signal-stage="recent-sell"' in case_source
    assert "주의: AI의 매도 타이밍을 무조건 따라가지마세요!" in case_source
    assert "strategy_price_anchor" in case_source
    assert "strategy_price_vertical_order" in case_source
    assert 'price_alignment.get("priceTop")' in case_source
    assert 'price_alignment.get("metaBottom")' in case_source
    assert 'wait_for(state="hidden")' in case_source


def test_home_ai_response_e2e_unhides_the_fixture_parent_section() -> None:
    source = Path("app/qa/e2e.py").read_text(encoding="utf-8")
    case_source = source.split("def home_watchlist_response_detail_case", 1)[1].split(
        "def home_notification_entry_case", 1
    )[0]

    assert "const personal = document.querySelector(" in case_source
    assert "if (!list || !personal)" in case_source
    assert "state.homeAiSignalsRequestId += 1;" in case_source
    assert "state.aiSignalLoadSequence += 1;" in case_source
    assert "window.clearTimeout(state.homeAiSignalsRetryTimer);" in case_source
    assert "window.clearTimeout(state.aiSignalRevisionTimer);" in case_source
    assert "window.clearTimeout(state.aiSignalReconcileTimer);" in case_source
    assert "state.quoteStreamSignalControlActive = false;" in case_source
    assert "pauseQuoteStreamConnection('checking');" in case_source
    assert "loadHomeAiSignals = async () => false;" in case_source
    assert "renderHomeAiResponse = () => {};" in case_source
    assert "주가에 영향을 줄 핵심 이벤트" not in case_source
    assert "summary_request_count_before_return" in case_source
    assert "requests.length === expectedCount" in case_source
    assert '"change_rate": 1.25' in case_source
    assert '"현재 주당 가격"' in case_source
    assert '"오늘 등락률"' in case_source
    assert '"상승 흐름 확인선"' in case_source
    assert '"매수가 아님"' in case_source
    assert '!= [["pullback", "breakout", "wait"]]' in case_source
    assert "personal.hidden = false;" in case_source
    assert case_source.index("personal.hidden = false;") < case_source.index(
        'personal.wait_for(state="visible")'
    )
    assert "document.activeElement?.id === expected" in case_source
    assert 'arg="qa-ai-stock-response-row"' in case_source
    assert "timeout=min(int(timeout * 1000), 3_000)" in case_source


@pytest.mark.qa_gate
def test_report_redaction_removes_nested_credentials() -> None:
    payload = redact(
        {
            "authorization": "Bearer do-not-log",
            "nested": {
                "app_secret": "very-secret",
                "message": "GET https://example.test/?token_key=abc123 failed",
            },
        }
    )
    encoded = json.dumps(payload)

    assert "do-not-log" not in encoded
    assert "very-secret" not in encoded
    assert "abc123" not in encoded
    assert encoded.count("[REDACTED]") >= 3


@pytest.mark.qa_gate
def test_gate_report_exercises_current_strategy_invariants(tmp_path: Path) -> None:
    junit = tmp_path / "pytest.xml"
    junit.write_text(
        '<testsuite tests="700" failures="0" errors="0" skipped="0"/>', encoding="utf-8"
    )
    report = run_data_signal_qa(
        mode="gate",
        base_url="http://testserver",
        pytest_junit=junit,
    )
    by_id = {item["id"]: item for item in report["checks"]}

    assert report["schema_version"] == "1.0"
    assert report["strategy_version"] == "position-lifecycle-v7.4"
    assert report["catalog_case_count"] == 90
    assert len(by_id) == len(report["checks"])
    assert by_id["SIG-ENTRY-001"]["status"] == "pass"
    assert by_id["SIG-ENTRY-002"]["status"] == "pass"
    assert by_id["SIG-EXECUTION-002"]["status"] == "pass"
    assert by_id["SIG-EXIT-001"]["status"] == "pass"
    assert by_id["SIG-CONTRACT-001"]["status"] == "pass"
    assert report["deployment_blocked"] is False


@pytest.mark.qa_gate
def test_p0_failure_blocks_deployment() -> None:
    collector = ResultCollector(load_qa_catalog())
    collector.add("DATA-KRX-NAVER-002", "fail", "stale")
    collector.add("DATA-GLOBAL-002", "warn", "source outage")
    results = collector.results
    p0_failures = [
        item.id for item in results if item.priority == "P0" and item.status == "fail"
    ]

    assert p0_failures == ["DATA-KRX-NAVER-002"]


@pytest.mark.qa_gate
def test_gate_without_pytest_evidence_is_blocked() -> None:
    report = run_data_signal_qa(mode="gate", base_url="http://testserver")

    assert report["deployment_blocked"] is True
    assert report["summary"]["p0_missing"]


class FakeReadOnlyApi:
    quality_price_state = "ready"
    market_signal_items = [
        {
            "code": "005930",
            "signal_date": "2026-08-28",
            "execution_date": "2026-08-28",
            "action": "hold",
            "is_current_holding": True,
            "display_return_kind": "open_position",
            "display_return_rate": "5.0",
            "current": {
                "action": "holding",
                "position_open": True,
                "price": 105000,
                "unrealized_return": 5.0,
                "as_of": "2026-08-29T10:00:00+09:00",
            },
            "holding_context": {
                "return_basis": {
                    "price": "105000",
                    "return_rate": "5.0",
                    "return_rate_per_price": "0.0001",
                }
            },
        }
    ]

    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url
        self.timeout = timeout

    def close(self) -> None:
        return None

    @staticmethod
    def _meta(path: str) -> dict[str, object]:
        return {
            "path": path,
            "http_status": 200,
            "latency_ms": 1,
            "content_type": "application/json",
            "cache_control": "no-store",
        }

    def get(self, path: str, **params: object):
        if path == "/health":
            return {
                "status": "ok",
                "strategy_version": "position-lifecycle-v7.4",
            }, self._meta(path)
        if path == "/readyz":
            return {"status": "ok", "database_ok": True}, self._meta(path)
        if path == "/meta/integrations":
            return [{"name": "kis_market_data", "configured": True}], self._meta(path)
        if path == "/meta/signal-data-quality":
            ready = {
                "source": "fixture",
                "state": "ready",
                "coverage_rate": 1.0,
                "latest_date": "2026-08-28",
            }
            return {
                "status": "degraded",
                "strategy_version": "position-lifecycle-v7.4",
                "as_of": "2026-08-29T10:00:00+09:00",
                "datasets": {
                    "price": {**ready, "state": self.quality_price_state},
                    "investor_flow": ready,
                    "market_index": ready,
                    "fundamentals": {
                        **ready,
                        "state": "caution",
                        "coverage_rate": 0.84,
                    },
                    "research": {
                        **ready,
                        "api": {"last_success_at": "2026-08-29T09:55:00"},
                    },
                    "disclosure": {
                        **ready,
                        "api": {"last_success_at": "2026-08-29T09:55:00"},
                    },
                    "entry_evidence_snapshot": ready,
                },
                "coherence": {
                    "state": "ready",
                    "signal_window_orphan_stock_codes": {"price": 0, "flow": 0},
                    "future_dated_rows": {
                        "price": 0,
                        "flow": 0,
                        "research": 0,
                        "disclosure": 0,
                    },
                    "malformed_fundamental_snapshots": 0,
                    "flow_normalization": "합계 우선",
                },
                "api_probe": {
                    "items": [
                        {"key": "price", "state": "ready"},
                        {"key": "disclosure", "state": "unavailable"},
                    ]
                },
            }, self._meta(path)
        if path == "/market/quant-signals":
            return {
                "status": "ready",
                "strategy_version": "position-lifecycle-v7.4",
                "as_of": "2026-08-29T10:00:00+09:00",
                "snapshot_generated_at": "2026-08-29T10:00:00+09:00",
                "signal_revision": 7,
                "signal_revision_as_of": "2026-08-29T10:00:00+09:00",
                "signal_revision_scope": "canonical_market_feed",
                "recent_days": 30,
                "items": self.market_signal_items,
            }, self._meta(path)
        if path == "/market/recommendations":
            return {
                "as_of": "2026-08-29T10:00:00+09:00",
                "selection_rule": "confirmed_entry_pending_or_entered_today",
                "qualified_count": 0,
                "pending_count": 0,
                "entered_today_count": 0,
                "items": [],
            }, self._meta(path)
        if path == "/stocks/005930":
            return {
                "code": "005930",
                "name": "삼성전자",
                "market": "KOSPI",
            }, self._meta(path)
        if path == "/stocks/005930/dashboard":
            return {"stock": {"code": "005930"}}, self._meta(path)
        if path == "/stocks/005930/quote":
            return {
                "code": "005930",
                "price": 100,
                "market_state": "closed",
            }, self._meta(path)
        if path == "/stocks/005930/intraday":
            return {"points": []}, self._meta(path)
        if path == "/stocks/005930/quant-signals":
            return {
                "strategy_version": "position-lifecycle-v7.4",
                "current": {"action": "hold"},
                "as_of": "2026-08-29T10:00:00+09:00",
            }, self._meta(path)
        if path == "/realtime/status":
            return {
                "public_quote_channels": {
                    "max_codes_per_client": 64,
                    "unique_codes": 0,
                    "kis_realtime_codes": 0,
                    "fallback_codes": 0,
                    "kis_session_codes": 0,
                    "idle_grace_active": False,
                    "idle_grace_seconds": 60,
                    "contention_backoff_seconds": 30,
                    "min_broadcast_interval_ms": 1000,
                },
                "connections": {"total": 0},
            }, self._meta(path)
        if path == "/us/stocks/AAPL/dashboard":
            return {"symbol": "AAPL", "as_of": "2026-08-28"}, self._meta(path)
        return {"items": [], "status": "ready"}, self._meta(path)

    def get_text(self, path: str, **params: object):
        assert path == "/dashboard"
        return (
            '<html><head><meta name="secret-note-environment" content="staging" /></head></html>',
            self._meta(path),
        )

    def post_json(self, path: str, payload: dict[str, object]):
        assert path == "/ai/page-summary"
        fallback = dict(payload["fallback"])
        return 200, {
            **fallback,
            "generation_mode": "rules",
            "model_name": None,
            "generation_note": "fixture fallback",
            "prompt_version": "staging-page-summary-v12",
            "cache_hit": False,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "estimated_cost_usd": None,
        }, self._meta(path)


@pytest.mark.qa_live
def test_live_report_distinguishes_allowed_caution_and_source_probe_warning(
    monkeypatch,
) -> None:
    from app.qa import runner

    FakeReadOnlyApi.quality_price_state = "ready"
    monkeypatch.setattr(runner, "ReadOnlyApi", FakeReadOnlyApi)
    monkeypatch.setattr(
        runner,
        "_public_websocket_check",
        lambda collector, base_url, timeout, **kwargs: collector.add(
            "DATA-KIS-005", "pass", "fixture websocket"
        ),
    )
    report = run_data_signal_qa(mode="live", base_url="https://fixture-staging.test")
    by_id = {item["id"]: item for item in report["checks"]}

    assert by_id["DATA-FUND-RESEARCH-001"]["status"] == "warn"
    assert by_id["DATA-GLOBAL-003"]["status"] == "warn"
    assert by_id["DATA-KRX-NAVER-002"]["status"] == "pass"
    assert report["market_state"] == "closed"
    assert report["deployment_blocked"] is False


@pytest.mark.qa_live
def test_live_report_blocks_stale_core_price(monkeypatch) -> None:
    from app.qa import runner

    FakeReadOnlyApi.quality_price_state = "stale"
    monkeypatch.setattr(runner, "ReadOnlyApi", FakeReadOnlyApi)
    monkeypatch.setattr(runner, "_public_websocket_check", lambda *args, **kwargs: None)
    report = run_data_signal_qa(mode="live", base_url="https://fixture-staging.test")

    assert report["deployment_blocked"] is True
    assert "DATA-KRX-NAVER-002" in report["summary"]["p0_failures"]


@pytest.mark.qa_live
def test_live_report_blocks_weekend_refresh_time_promoted_to_signal_time(monkeypatch) -> None:
    from app.qa import runner

    FakeReadOnlyApi.quality_price_state = "ready"
    monkeypatch.setattr(
        FakeReadOnlyApi,
        "market_signal_items",
        [
            {
                "code": "373220",
                "signal_date": "2026-08-28",
                "signal_at": "2026-08-30T12:38:41+09:00",
                "action": "entry_watch",
                "status": "preliminary",
                "is_preliminary": True,
                "current": {
                    "action": "entry_watch",
                    "as_of": "2026-08-30T12:38:41+09:00",
                    "live_observation": False,
                    "position_open": False,
                },
            }
        ],
    )
    monkeypatch.setattr(runner, "ReadOnlyApi", FakeReadOnlyApi)
    monkeypatch.setattr(runner, "_public_websocket_check", lambda *args, **kwargs: None)

    report = run_data_signal_qa(mode="live", base_url="https://fixture-staging.test")
    by_id = {item["id"]: item for item in report["checks"]}

    assert by_id["SIG-CONTRACT-003"]["status"] == "fail"
    assert "373220" in json.dumps(by_id["SIG-CONTRACT-003"]["evidence"])
    assert report["deployment_blocked"] is True


@pytest.mark.qa_live
def test_live_report_blocks_open_position_without_live_return_basis(monkeypatch) -> None:
    from app.qa import runner

    FakeReadOnlyApi.quality_price_state = "ready"
    monkeypatch.setattr(
        FakeReadOnlyApi,
        "market_signal_items",
        [
            {
                "code": "005930",
                "signal_date": "2026-08-28",
                "execution_date": "2026-08-28",
                "action": "holding",
                "is_current_holding": True,
                "display_return_kind": "open_position",
                "display_return_rate": 5.0,
                "current": {"action": "holding", "position_open": True},
            }
        ],
    )
    monkeypatch.setattr(runner, "ReadOnlyApi", FakeReadOnlyApi)
    monkeypatch.setattr(runner, "_public_websocket_check", lambda *args, **kwargs: None)

    report = run_data_signal_qa(mode="live", base_url="https://fixture-staging.test")
    by_id = {item["id"]: item for item in report["checks"]}

    assert by_id["SIG-CONTRACT-003"]["status"] == "fail"
    assert "open_position" in json.dumps(by_id["SIG-CONTRACT-003"]["evidence"])
    assert report["deployment_blocked"] is True


@pytest.mark.qa_live
def test_live_report_blocks_closed_trade_return_that_is_not_frozen(monkeypatch) -> None:
    from app.qa import runner

    FakeReadOnlyApi.quality_price_state = "ready"
    monkeypatch.setattr(
        FakeReadOnlyApi,
        "market_signal_items",
        [
            {
                "code": "005930",
                "signal_date": "2026-08-28",
                "execution_date": "2026-08-28",
                "action": "exited",
                "is_current_holding": False,
                "display_return_kind": "closed_trade",
                "display_return_rate": 7.0,
                "return_rate": 5.0,
                "live_return_rate": 7.0,
                "current": {"action": "exited", "position_open": False},
            }
        ],
    )
    monkeypatch.setattr(runner, "ReadOnlyApi", FakeReadOnlyApi)
    monkeypatch.setattr(runner, "_public_websocket_check", lambda *args, **kwargs: None)

    report = run_data_signal_qa(mode="live", base_url="https://fixture-staging.test")
    by_id = {item["id"]: item for item in report["checks"]}

    assert by_id["SIG-CONTRACT-003"]["status"] == "fail"
    assert "closed_trade" in json.dumps(by_id["SIG-CONTRACT-003"]["evidence"])
    assert report["deployment_blocked"] is True


@pytest.mark.qa_live
def test_live_report_blocks_inconsistent_realtime_fallback_counts(monkeypatch) -> None:
    from app.qa import runner

    class BrokenRealtimeStatusApi(FakeReadOnlyApi):
        def get(self, path: str, **params: object):
            if path == "/realtime/status":
                return {
                    "public_quote_channels": {
                        "max_codes_per_client": 64,
                        "unique_codes": 2,
                        "kis_realtime_codes": 1,
                        "fallback_codes": 0,
                        "min_broadcast_interval_ms": 1000,
                    },
                    "connections": {"total": 1},
                }, self._meta(path)
            return super().get(path, **params)

    FakeReadOnlyApi.quality_price_state = "ready"
    monkeypatch.setattr(runner, "ReadOnlyApi", BrokenRealtimeStatusApi)
    monkeypatch.setattr(runner, "_public_websocket_check", lambda *args, **kwargs: None)

    report = run_data_signal_qa(mode="live", base_url="https://fixture-staging.test")
    by_id = {item["id"]: item for item in report["checks"]}

    assert by_id["DATA-KIS-006"]["status"] == "fail"
    assert by_id["DATA-KIS-006"]["evidence"] == {
        "unique_codes": 2,
        "kis_realtime_codes": 1,
        "fallback_codes": 0,
    }
    assert report["deployment_blocked"] is True


@pytest.mark.qa_live
def test_live_report_blocks_nonholding_signal_outside_recent_window(monkeypatch) -> None:
    from app.qa import runner

    FakeReadOnlyApi.quality_price_state = "ready"
    monkeypatch.setattr(
        FakeReadOnlyApi,
        "market_signal_items",
        [
            {
                "code": "000660",
                "signal_date": "2026-07-01",
                "execution_date": "2026-07-01",
                "action": "exited",
                "is_current_holding": False,
            },
            {
                "code": "005930",
                "signal_date": "2026-07-01",
                "execution_date": "2026-07-01",
                "action": "hold",
                "is_current_holding": True,
            },
        ],
    )
    monkeypatch.setattr(runner, "ReadOnlyApi", FakeReadOnlyApi)
    monkeypatch.setattr(runner, "_public_websocket_check", lambda *args, **kwargs: None)

    report = run_data_signal_qa(mode="live", base_url="https://fixture-staging.test")
    by_id = {item["id"]: item for item in report["checks"]}

    assert by_id["SIG-CONTRACT-004"]["status"] == "fail"
    assert "000660" in json.dumps(by_id["SIG-CONTRACT-004"]["evidence"])
    assert "005930" not in json.dumps(by_id["SIG-CONTRACT-004"]["evidence"])
    assert report["deployment_blocked"] is True


@pytest.mark.qa_gate
def test_cli_writes_gate_json_report(tmp_path: Path) -> None:
    output = tmp_path / "gate.json"
    junit = tmp_path / "pytest.xml"
    junit.write_text(
        '<testsuite tests="700" failures="0" errors="0" skipped="0"/>', encoding="utf-8"
    )
    result = CliRunner().invoke(
        app,
        [
            "qa",
            "data-signal",
            "--mode",
            "gate",
            "--base-url",
            "http://testserver",
            "--pytest-junit",
            str(junit),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "gate"
    assert payload["deployment_blocked"] is False


@pytest.mark.qa_e2e
def test_e2e_url_builder_keeps_theme_and_view() -> None:
    url = _page_url("https://example.test/", "/dashboard", view="home", theme="dark")
    assert url == "https://example.test/dashboard?view=home&theme=dark"
