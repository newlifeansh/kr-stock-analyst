import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]


def test_watchlist_v15_shell_and_asset_version():
    client = TestClient(app)
    shell = client.get("/dashboard?view=watchlist")

    assert shell.status_code == 200
    assert 'id="portfolio-view" class="app-page app-portfolio" data-ui-version="5.0" data-watch-group-layout="true" data-watchlist-layout="compact"' in shell.text
    assert 'id="watchlist-view" class="watchlist-v15 watchlist-v2 watchlist-v3" data-ui-version="3.0"' in shell.text
    assert 'name="application-version" content="5.8"' in shell.text
    assert 'src="/dashboard-app-v170.js?v=20260910v508"' in shell.text
    assert 'id="push-notification-disable-button"' not in shell.text
    assert '<h1 id="watch-group-heading">관심</h1>' in shell.text
    assert 'id="watch-group-edit" type="button" aria-pressed="false">편집</button>' in shell.text
    assert 'id="watchlist-search" type="button" aria-label="관심종목 검색해서 추가"' in shell.text
    assert 'id="watch-group-tabs" role="tablist" aria-label="관심 그룹 선택"' in shell.text
    assert 'data-watch-group="default">기본그룹</button>' in shell.text
    assert 'data-watch-group="pinned">핀종목</button>' in shell.text
    assert 'id="watch-group-meta" role="status" aria-live="polite">0개</p>' in shell.text
    assert 'id="watch-group-create"' in shell.text
    assert 'id="watch-group-dialog"' in shell.text
    assert 'id="watch-stock-add-dialog"' in shell.text
    assert 'id="watch-stock-search-input"' in shell.text
    assert 'id="watch-stock-add-results"' in shell.text
    assert 'id="watch-stock-group-options"' in shell.text
    assert 'id="watch-stock-group-complete"' in shell.text
    assert 'id="watch-group-add-stock"' not in shell.text
    assert 'id="watch-group-share"' not in shell.text
    assert "이 그룹 공유하기" not in shell.text
    assert "+ 관심 추가" not in shell.text
    assert 'class="watchlist-card-list watch-v2-list-surface watch-compact-list"' in shell.text

    styles = client.get("/assets/dashboard/styles.css").text
    assert "Compact interest hub v499" in styles
    assert '#portfolio-view[data-watchlist-layout="compact"] .watch-compact-row' in styles
    assert 'class="watch-v2-list-head"' not in shell.text
    assert 'id="watchlist-filter-summary"' not in shell.text

    for view_id in ("home-view", "search-view", "portfolio-view", "chart-view"):
        view_markup = shell.text.split(f'id="{view_id}"', 1)[1].split("</section>", 1)[0]
        assert 'class="app-page-intro' not in view_markup


def test_watchlist_v508_uses_shared_product_icon_system():
    client = TestClient(app)
    shell = client.get("/dashboard?view=portfolio").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text
    sprite = client.get("/assets/staging/streamline-plump-icons.svg").text
    portfolio = shell.split('id="portfolio-view"', 1)[1].split('id="chart-view"', 1)[0]

    assert 'data-staging-top-icon="search"' in portfolio
    assert 'streamline-plump-icons.svg?v=20260910-v65#folder-add' in portfolio
    assert 'streamline-plump-icons.svg?v=20260910-v65#back' in portfolio
    assert 'streamline-plump-icons.svg?v=20260910-v65#search' in portfolio
    assert portfolio.count('streamline-plump-icons.svg?v=20260910-v65#close') == 3
    assert ">×</button>" not in portfolio

    for icon_name in ("folder", "folder-add", "add", "check", "close", "remove"):
        assert f'id="{icon_name}"' in sprite
    for expected in (
        'const WATCH_UI_ICON_SPRITE_PATH = "/assets/staging/streamline-plump-icons.svg?v=20260910-v65";',
        "function createWatchUiIcon(symbol, className = \"\")",
        'createWatchUiIcon("interest", "watch-stock-add-empty-glyph")',
        'createWatchUiIcon(saved ? "check" : "add", "watch-stock-search-action-icon")',
        'createWatchUiIcon("folder", "watch-stock-group-folder")',
        'createWatchUiIcon("check", "watch-stock-group-check-icon")',
        'createWatchUiIcon("remove", "watch-compact-remove-icon")',
        ".watch-stock-group-option input:checked + .watch-stock-group-check",
        ".watch-stock-group-option input:disabled + .watch-stock-group-check",
    ):
        assert expected in source or expected in styles
    disabled_input_rules = styles.split(
        ".watch-stock-group-option input:disabled {", 1
    )[1].split("}", 1)[0]
    assert "opacity: 0;" in disabled_input_rules
    assert "opacity: 1;" not in disabled_input_rules
    for removed in (
        'el("span", "watch-stock-add-empty-icon", "+")',
        'saved ? "✓" : "+"',
        'removeButton.textContent = "−"',
        ".watch-stock-group-folder::before",
    ):
        assert removed not in source
        assert removed not in styles

    assert "/* Interest icon system v508" in styles
    assert ".watchlist-search > svg.staging-top-action-icon" in styles
    assert "stroke-width: 2.6px !important;" in styles
    assert ".watch-stock-group-option input:focus-visible + .watch-stock-group-check" in styles


def test_watchlist_v15_uses_compact_logo_sparkline_price_rows():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    for expected in (
        "function watchCompactSeries",
        "function createWatchCompactSparkline",
        "function appendWatchCompactRow",
        'card.className = `watch-compact-row${pinned ? " is-pinned" : ""}`;',
        'link.className = "watch-compact-link";',
        'const logo = createStockListLogo(item.code, "watch-compact-logo");',
        'copy.append(el("strong", "", item.name), el("small", "", item.code || ""));',
        'const quote = el("span", "watch-stock-quote watch-compact-quote");',
        'price.dataset.field = "price";',
        'today.dataset.field = "change_rate";',
        "link.append(identity, createWatchCompactSparkline(item, dashboard, prices), quote);",
        'removeButton.dataset.watchAction = pinned ? "unpin" : customGroup ? "remove-group" : "remove-watchlist";',
        "async function loadHomeWatchMarketMap",
        "async function loadWatchlist",
    ):
        assert expected in source

    compact_source = source.split("function appendWatchCompactRow", 1)[1].split(
        "function appendWatchRow", 1
    )[0]
    for removed in ("watch-v15-metrics", "watch-pin-metrics", "market_cap", "rank"):
        assert removed not in compact_source

    styles = client.get("/assets/dashboard/styles.css").text
    for expected in (
        '#portfolio-view[data-watchlist-layout="compact"] .watch-compact-link',
        "grid-template-columns: minmax(118px, 1fr) clamp(64px, 18vw, 96px) minmax(82px, auto);",
        '#portfolio-view[data-watchlist-layout="compact"] .watch-compact-sparkline',
        '#portfolio-view[data-watchlist-layout="compact"] .watch-compact-quote',
        '#portfolio-view[data-watchlist-layout="compact"][data-watch-editing="true"] .watch-compact-remove',
    ):
        assert expected in styles


def test_watchlist_market_cap_bubbles_use_active_folder_timeline_and_bottom_sheet():
    client = TestClient(app)
    shell = client.get("/dashboard?view=watchlist").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text
    home = shell.split('id="home-view"', 1)[1].split('id="search-view"', 1)[0]
    portfolio = shell.split('id="portfolio-view"', 1)[1].split('id="chart-view"', 1)[0]

    for expected in (
        'id="watch-market-map"',
        'id="watch-market-map-stage" role="group"',
        'id="watch-market-map-legend"',
        'id="watch-market-map-timeline"',
        'id="watch-market-map-timeline-input-zone"',
        'id="watch-market-map-timeline-track" type="range"',
        'id="watch-market-map-timeline-time"',
        'id="watch-market-map-sheet"',
        'id="watch-market-map-sheet-list"',
    ):
        assert expected in home or expected in source
    assert 'button.setAttribute("aria-haspopup", "dialog");' in source
    assert home.index('id="watch-market-map"') < home.index('id="home-surge"')
    assert 'id="watch-market-map"' not in portfolio
    assert 'data-unified-market-scope' not in portfolio

    for expected in (
        "function watchMarketMapEntries",
        "function packWatchMarketMapBubbles",
        "function computeWatchMarketMapLayout",
        "function watchMarketMapPhysicsConfig",
        "function resolveWatchMarketMapCollisions",
        "function watchMarketMapMotionSnapshot",
        "function animateWatchMarketMapLayout",
        "function bindWatchMarketMapDrag",
        "function watchMarketMapTimelineSnapshot",
        "function watchMarketMapTimelineRange",
        "function watchMarketMapEntrySnapshot",
        "function watchMarketMapEntriesAtTimeline",
        "function renderWatchMarketMapTimeline",
        "function handleWatchMarketMapTimelineInput",
        "function watchMarketMapCanonicalTradeDate",
        "function watchMarketMapZonedEpoch",
        "function normalizeWatchMarketMapIntraday",
        "async function loadWatchMarketMapIntraday",
        "function renderWatchMarketMap",
        "async function loadHomeWatchMarketMap",
        "function openWatchMarketMapSheet",
        "function createWatchMarketMapSheetRow",
        'tile.href = viewStockUrl(entry.item.code || entry.item.name, entry.item);',
        'link.href = viewStockUrl(entry.item.code || entry.item.name, entry.item);',
        'const groupId = state.activeWatchGroup;',
        'const items = watchlistItemsForGroup(groupId);',
        'const url = options.force ? "/us/fx/usdkrw?refresh=true" : "/us/fx/usdkrw";',
        'renderWatchMarketMap([], { loading: true, totalCount: items.length });',
        "renderWatchMarketMap(state.watchMarketMapResults);",
        'gravitationalConstant: 0.02,',
        'stage.dataset.motionModel = "packedbubble-physics";',
        'tile.setPointerCapture?.(event.pointerId);',
        'physics.stage.dataset.motion = motionKind === "dragging" ? "dragging" : "settling";',
        'elements.watchMarketMapStage.dataset.sizeEncoding = "absolute-return";',
        '? `/us/stocks/${code}/intraday?range=1d&interval=1m`',
        ': `/stocks/${code}/intraday?limit=390`;',
        'elements.watchMarketMapTimelineTrack?.addEventListener("input", handleWatchMarketMapTimelineInput);',
        '"(prefers-reduced-motion: reduce)"',
        'elements.watchMarketMapStage?.querySelector(".watch-market-map-tile.is-overflow")',
    ):
        assert expected in source

    bubble_source = source.split("function createWatchMarketMapTile", 1)[1].split(
        "function renderWatchMarketMapLegend", 1
    )[0]
    sheet_source = source.split("function createWatchMarketMapSheetRow", 1)[1].split(
        "function watchMarketMapSheetOpen", 1
    )[0]
    for removed in (
        "watch-market-map-rank",
        "watch-market-map-origin",
        "watch-market-map-tile-top",
        "formatWatchMarketCap",
    ):
        assert removed not in bubble_source
        assert removed not in sheet_source
    assert 'identity.append(nameRow, el("small", "", entry.item.code || ""));' in sheet_source
    assert '`${entry.item.name}, ${timeLabel} ${tone.label} ${formatPercent(change)}, 종목 상세 보기`' in source

    for expected in (
        "/* Watch groups and return timeline v506",
        "#home-view .watch-market-map {",
        ".watch-market-map-stage {",
        ".watch-market-map-tile.is-overflow",
        ".watch-market-map-tile[data-watch-motion]",
        ".watch-market-map-tile.is-dragging",
        ".watch-market-map-timeline-control {",
        "#watch-market-map-timeline-track::-webkit-slider-thumb",
        "#watch-market-map-timeline-track:focus-visible",
        ".watch-market-map-sheet::backdrop",
        ".watch-market-map-sheet-row:focus-visible",
        "@media (max-width: 359px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert expected in styles
    for removed in (
        ".watch-market-map-rank",
        ".watch-market-map-origin",
        ".watch-market-map-sheet-rank",
        ".watch-market-map-sheet-name em",
    ):
        assert removed not in styles


def test_watchlist_return_timeline_recomputes_bubble_size_color_inputs_and_overflow():
    script = r'''
const fs = require("fs");
const source = fs.readFileSync("app/static/dashboard/app.js", "utf8");
function functionSource(name, nextName) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf(`function ${nextName}(`, start + 1);
  if (start < 0 || end < 0) throw new Error(`${name} not found`);
  return source.slice(start, end);
}
const state = {
  watchMarketMapResults: [],
  watchMarketMapUsdKrw: 1300,
  watchMarketMapIntradayByKey: new Map(),
  watchMarketMapTimelineMinutes: 600,
  watchMarketMapTimelineLatestMinutes: null,
};
function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
function marketScopeForItem(item = {}) {
  return item.market_scope === "us" ? "us" : "kr";
}
function watchMarketMapMarketCap(result = {}) {
  return toNumber(result.dashboard?.quote?.market_cap);
}
function previousCloseFromQuote(quote) {
  const price = toNumber(quote?.price);
  const changeValue = toNumber(quote?.change_value);
  if (price !== null && changeValue !== null) return price - changeValue;
  const changeRate = toNumber(quote?.change_rate);
  return price !== null && changeRate !== null && changeRate !== -100
    ? price / (1 + changeRate / 100)
    : null;
}
eval(functionSource("watchMarketMapEntries", "packWatchMarketMapBubbles"));
eval(functionSource("packWatchMarketMapBubbles", "computeWatchMarketMapLayout"));
eval(functionSource("computeWatchMarketMapLayout", "watchMarketMapTimeParts"));
eval(functionSource("watchMarketMapPhysicsConfig", "watchMarketMapMotionKey"));
eval(functionSource("watchMarketMapTimeParts", "watchMarketMapTimelineSnapshot"));
eval(functionSource("watchMarketMapTimelineSnapshot", "renderWatchMarketMapTimeline"));
const result = (code, marketScope, marketCap, changeRate = 0) => ({
  item: { code, market_scope: marketScope },
  dashboard: {
    quote: {
      market_cap: marketCap,
      price: 100 * (1 + changeRate / 100),
      change_rate: changeRate,
      change_value: changeRate,
      as_of: "2026-09-09T12:00:00+09:00",
    },
  },
});
const entries = watchMarketMapEntries([
  result("005930", "kr", 500e12, 2.1),
  result("NVDA", "us", 3e12, 4.8),
  result("AAPL", "us", 2.5e12, -0.8),
  result("000660", "kr", 150e12, -3.2),
  result("MSFT", "us", 0.1e12, 1.5),
  result("GOOGL", "us", 0.08e12, -2.3),
  result("AMZN", "us", 0.06e12, 0.4),
  result("035420", "kr", 50e12, 3.7),
  result("005380", "kr", 40e12, 0),
  result("SMALL1", "us", 1e9, -1.1),
  result("SMALL2", "us", 0.7e9, 0.2),
  result("NULL", "kr", null, 0),
]);
const layout = computeWatchMarketMapLayout(entries, 320, 300);
const overlaps = layout.nodes.some((left, leftIndex) => layout.nodes.some((right, rightIndex) => (
  leftIndex < rightIndex
  && Math.hypot(left.cx - right.cx, left.cy - right.cy)
    < left.radius + right.radius + 4.9
)));
const outside = layout.nodes.some((node) => (
  node.x < 0 || node.y < 0 || node.x + node.width > 320.0001 || node.y + node.height > 300.0001
));
const responsiveSafe = [
  [260, 286],
  [310, 343],
  [1070, 460],
].every(([width, height]) => {
  const candidate = computeWatchMarketMapLayout(entries, width, height);
  const overlapsAtWidth = candidate.nodes.some((left, leftIndex) => candidate.nodes.some((right, rightIndex) => (
    leftIndex < rightIndex
    && Math.hypot(left.cx - right.cx, left.cy - right.cy)
      < left.radius + right.radius + 4.9
  )));
  const outsideAtWidth = candidate.nodes.some((node) => (
    node.x < 0 || node.y < 0
    || node.x + node.width > width + 0.0001
    || node.y + node.height > height + 0.0001
  ));
  const readable = candidate.nodes.every((node) => node.radius >= (node.kind === "overflow" ? 26 : width < 520 ? 22 : 31));
  return !overlapsAtWidth && !outsideAtWidth && readable;
});
const singleLayout = computeWatchMarketMapLayout([
  watchMarketMapEntries([result("ONLY", "kr", 500e12, 0)])[0],
], 320, 300);
const singleBubbleReadable = singleLayout.nodes.length === 1 && singleLayout.nodes[0].radius >= 22;

const dynamicEntries = watchMarketMapEntries([
  result("FAST", "kr", 300e12, 2),
  result("SLOW", "us", 200e12, -3),
  result("FLAT", "kr", 100e12, 0),
]);
const intradayPayloads = {
  FAST: {
    code: "FAST",
    trade_date: "20260909",
    reference_price: 100,
    points: [
      {trade_date: "20260909", trade_time: "090000", price: 101},
      {trade_date: "20260909", trade_time: "100000", price: 103},
      {trade_date: "20260909", trade_time: "100000", price: 104},
      {trade_date: "20260909", trade_time: "120000", price: 102},
    ],
  },
  SLOW: {
    code: "SLOW",
    trade_date: "2026-09-09",
    market_timezone: "Asia/Seoul",
    reference_price: 100,
    points: [
      {trade_date: "2026-09-09", trade_time: "090000", price: 96},
      {trade_date: "2026-09-09", trade_time: "100000", price: 99.5},
      {trade_date: "2026-09-09", trade_time: "120000", price: 97},
    ],
  },
  FLAT: {
    code: "FLAT",
    trade_date: "2026-09-09",
    reference_price: 100,
    points: [
      {trade_date: "2026-09-09", trade_time: "090000", price: 100},
      {trade_date: "2026-09-09", trade_time: "120000", price: 100},
    ],
  },
};
for (const entry of dynamicEntries) {
  state.watchMarketMapIntradayByKey.set(
    watchMarketMapEntryKey(entry),
    normalizeWatchMarketMapIntraday(intradayPayloads[entry.item.code], entry),
  );
}
const timezoneEntry = result("TZ", "us", 1e12, 0);
const timezoneSeries = normalizeWatchMarketMapIntraday({
  code: "TZ",
  trade_date: "2026-09-09",
  market_timezone: "America/New_York",
  reference_price: 100,
  points: [
    {trade_date: "2026-09-09", trade_time: "093000", price: 101},
    {trade_date: "2026-09-09", trade_time: "110000", price: 102},
    {trade_date: "2026-09-09", trade_time: "160000", price: 103},
  ],
}, timezoneEntry);
state.watchMarketMapIntradayByKey.set(watchMarketMapEntryKey(timezoneEntry), timezoneSeries);
const timezoneAfterClose = watchMarketMapEntrySnapshot(timezoneEntry, {
  dateKey: "2026-09-10",
  latestMinutes: 720,
  selectedMinutes: 480,
});
const timelineAtTen = watchMarketMapTimelineRange(dynamicEntries);
const entriesAtTen = watchMarketMapEntriesAtTimeline(dynamicEntries, timelineAtTen);
const layoutAtTen = computeWatchMarketMapLayout(entriesAtTen, 620, 400);
const radiiAtTen = Object.fromEntries(
  layoutAtTen.nodes.filter(node => node.kind === "stock").map(node => [node.entry.item.code, node.radius]),
);
state.watchMarketMapTimelineMinutes = 540;
const timelineAtNine = watchMarketMapTimelineRange(dynamicEntries);
const entriesAtNine = watchMarketMapEntriesAtTimeline(dynamicEntries, timelineAtNine);
const layoutAtNine = computeWatchMarketMapLayout(entriesAtNine, 620, 400);
const radiiAtNine = Object.fromEntries(
  layoutAtNine.nodes.filter(node => node.kind === "stock").map(node => [node.entry.item.code, node.radius]),
);
state.watchMarketMapTimelineMinutes = 615;
const nearestPrior = watchMarketMapEntrySnapshot(dynamicEntries[0], watchMarketMapTimelineRange(dynamicEntries));
state.watchMarketMapTimelineMinutes = 480;
const unavailableBeforeOpen = watchMarketMapEntriesAtTimeline(
  dynamicEntries,
  watchMarketMapTimelineRange(dynamicEntries),
).every(entry => entry.marketMapSnapshot.available === false);
const physicsConfig = watchMarketMapPhysicsConfig(320);
const collisionNodes = [
  {x: 100, y: 100, radius: 30, scale: 1, vx: 0, vy: 0},
  {x: 120, y: 100, radius: 30, scale: 1, vx: 0, vy: 0},
];
const collisionCount = resolveWatchMarketMapCollisions(
  collisionNodes,
  320,
  300,
  physicsConfig,
);
const collisionDistance = Math.hypot(
  collisionNodes[0].x - collisionNodes[1].x,
  collisionNodes[0].y - collisionNodes[1].y,
);
const timeline = watchMarketMapTimelineSnapshot([
  {dashboard: {quote: {as_of: "2026-09-09T05:30:00+09:00"}}},
]);
console.log(JSON.stringify({
  order: entries.map((entry) => entry.item.code),
  visible: layout.visibleEntries.map((entry) => entry.item.code),
  hidden: layout.hiddenEntries.map((entry) => entry.item.code),
  hasOverflow: layout.nodes.some((node) => node.kind === "overflow"),
  overlaps,
  outside,
  responsiveSafe,
  singleBubbleReadable,
  timelineLatestMinutes: timelineAtTen.latestMinutes,
  timelineSelectedMinutes: timelineAtTen.selectedMinutes,
  intradayReturnsAtTen: Object.fromEntries(entriesAtTen.map(entry => [
    entry.item.code,
    Number(entry.marketMapSnapshot.changeRate.toFixed(2)),
  ])),
  intradayReturnsAtNine: Object.fromEntries(entriesAtNine.map(entry => [
    entry.item.code,
    Number(entry.marketMapSnapshot.changeRate.toFixed(2)),
  ])),
  returnSizingSwaps: radiiAtTen.FAST > radiiAtTen.SLOW && radiiAtNine.SLOW > radiiAtNine.FAST,
  dedupedMinuteUsesLatestPoint: entriesAtTen.find(entry => entry.item.code === "FAST").marketMapSnapshot.price === 104,
  nearestPriorMinute: nearestPrior.pointMinute,
  unavailableBeforeOpen,
  compactDomesticDateNormalized: state.watchMarketMapIntradayByKey.get("kr:FAST").tradeDate,
  newYorkToSeoul: timezoneSeries.points.map(point => ({
    dateKey: point.dateKey,
    minute: point.minute,
  })),
  newYorkAfterCloseCarry: {
    minute: timezoneAfterClose.pointMinute,
    change: Number(timezoneAfterClose.changeRate.toFixed(2)),
  },
  endpoints: Object.fromEntries(dynamicEntries.map(entry => [entry.item.code, watchMarketMapIntradayEndpoint(entry)])),
  physics: {
    splitSeries: physicsConfig.splitSeries,
    gravitationalConstant: physicsConfig.gravitationalConstant,
    maxDurationMs: physicsConfig.maxDurationMs,
    collisionCount,
    collisionDistance,
  },
  timelineMinutes: timeline.minutes,
}));
'''
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "order": ["NVDA", "AAPL", "005930", "000660", "MSFT", "GOOGL", "AMZN", "035420", "005380", "SMALL1", "SMALL2", "NULL"],
        "visible": ["NVDA", "AAPL", "005930", "000660", "MSFT", "GOOGL", "AMZN", "035420", "005380"],
        "hidden": ["SMALL1", "SMALL2", "NULL"],
        "hasOverflow": True,
        "overlaps": False,
        "outside": False,
        "responsiveSafe": True,
        "singleBubbleReadable": True,
        "timelineLatestMinutes": 720,
        "timelineSelectedMinutes": 600,
        "intradayReturnsAtTen": {"SLOW": -0.5, "FAST": 4, "FLAT": 0},
        "intradayReturnsAtNine": {"SLOW": -4, "FAST": 1, "FLAT": 0},
        "returnSizingSwaps": True,
        "dedupedMinuteUsesLatestPoint": True,
        "nearestPriorMinute": 600,
        "unavailableBeforeOpen": True,
        "compactDomesticDateNormalized": "2026-09-09",
        "newYorkToSeoul": [
            {"dateKey": "2026-09-09", "minute": 1350},
            {"dateKey": "2026-09-10", "minute": 0},
            {"dateKey": "2026-09-10", "minute": 300},
        ],
        "newYorkAfterCloseCarry": {"minute": 300, "change": 3},
        "endpoints": {
            "SLOW": "/us/stocks/SLOW/intraday?range=1d&interval=1m",
            "FAST": "/stocks/FAST/intraday?limit=390",
            "FLAT": "/stocks/FLAT/intraday?limit=390",
        },
        "physics": {
            "splitSeries": False,
            "gravitationalConstant": 0.02,
            "maxDurationMs": 960,
            "collisionCount": 1,
            "collisionDistance": 64,
        },
        "timelineMinutes": 330,
    }


def test_interest_groups_inline_add_compact_list_and_edit_actions():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'const WATCHLIST_GROUP_KEY = "analyst.watchlistGroups.v1";',
        'default: Object.freeze({ id: "default", name: "기본그룹" })',
        'pinned: Object.freeze({ id: "pinned", name: "핀종목" })',
        "function watchlistItemsForGroup",
        'if (groupId === "pinned")',
        "function openWatchlistGroupDialog",
        "function saveWatchlistGroupFromDialog",
        "function removeCodeFromActiveWatchlistGroup",
        "function openWatchStockAddDialog",
        "function searchWatchStockAdd",
        "function openWatchStockGroupStep",
        "function applyWatchStockAddSelection",
        "function completeWatchStockAdd",
        "const focusedGroupId = elements.watchGroupTabs.contains(document.activeElement)",
        'const currentTab = event.target.closest("[data-watch-group]");',
        'const nextGroupId = tabs[nextIndex].dataset.watchGroup || "default";',
        "fetchRemoteWatchlistGroups(normalizedId)",
        "saveRemoteWatchlistGroups(localGroups, normalizedId)",
        'state.activeWatchGroup = "pinned";',
        'card.className = `watch-compact-row${pinned ? " is-pinned" : ""}`;',
        'card.dataset.watchGroupKind = "pinned";',
        'removeButton.dataset.watchAction = pinned ? "unpin" : customGroup ? "remove-group" : "remove-watchlist";',
        'removeWatchlistCodeFromGroups(code);',
        'elements.portfolioView.dataset.watchEditing = String(state.watchlistEditing);',
        'elements.watchGroupMeta.textContent = watchlistGroupMetaText();',
        'elements.watchlistSearch?.addEventListener("click", () => openWatchStockAddDialog',
        'action.textContent = groupId === "pinned" ? "추천 종목 보기" : "종목 추가";',
        'else openWatchStockAddDialog(action);',
    ):
        assert expected in source

    empty_state_source = source[
        source.index("function renderWatchlistMessage")
        : source.index("function clearWatchlistLoadingOverlay")
    ]
    assert "종목 추가에서 검색해 이 폴더에 바로 담아보세요." in empty_state_source
    assert empty_state_source.index('edit.textContent = "폴더 편집"') < empty_state_source.index(
        'action.textContent = groupId === "pinned" ? "추천 종목 보기" : "종목 추가"'
    )
    assert "else openWatchStockAddDialog(action);" in empty_state_source

    for expected in (
        "/* Interest groups v493:",
        ".watch-group-rail {",
        ".watch-group-chip.active",
        ".watch-group-dialog::backdrop",
        '#portfolio-view[data-watchlist-layout="compact"] .watch-hub-toolbar',
        '#portfolio-view[data-watchlist-layout="compact"] .watch-compact-row',
        "/* Watchlist inline add v507:",
        ".watch-stock-add-dialog::backdrop",
        ".watch-stock-search-form:focus-within",
        ".watch-stock-search-row",
        ".watch-stock-group-option",
        ".watch-stock-group-complete",
        'margin-inline: auto !important;',
        'padding-right: max(var(--tc-gutter), env(safe-area-inset-right, 0px)) !important;',
        '#portfolio-view[data-watchlist-layout="compact"][data-watch-editing="true"] .watch-compact-remove',
        "@media (max-width: 359px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert expected in styles

    shell = client.get("/dashboard?view=watchlist").text
    for removed in (
        'id="watch-group-share"',
        'id="watch-group-add-stock"',
        "이 그룹 공유하기",
        "+ 관심 추가",
        "function shareActiveWatchlistGroup",
    ):
        assert removed not in shell
        assert removed not in source


def test_inline_watchlist_add_selection_updates_only_selected_custom_groups():
    script = r'''
const fs = require("fs");
const source = fs.readFileSync("app/static/dashboard/app.js", "utf8");
function functionSource(name, nextName) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf(`function ${nextName}(`, start + 1);
  if (start < 0 || end < 0) throw new Error(`${name} not found`);
  return source.slice(start, end);
}
function marketScopeForItem(item = {}) {
  return item.market_scope === "us" ? "us" : "kr";
}
function normalizeWatchlistItems(items = []) {
  const seen = new Set();
  return items.filter(item => {
    const key = `${marketScopeForItem(item)}:${item.code}`;
    if (!item.code || !item.name || seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 100);
}
function normalizeWatchlistGroups(groups = []) {
  return groups.map(group => ({...group, codes: [...new Set(group.codes || [])].slice(0, 100)}));
}
eval(functionSource("watchStockItemKey", "watchStockIsSaved"));
eval(functionSource("applyWatchStockAddSelection", "renderWatchStockAddEmpty"));
const items = [
  {code: "005930", name: "삼성전자", market_scope: "kr"},
  {code: "000660", name: "SK하이닉스", market_scope: "kr"},
];
const groups = [
  {id: "chips", name: "반도체", codes: ["005930"]},
  {id: "income", name: "배당주", codes: ["000660"]},
];
const added = applyWatchStockAddSelection(
  {code: "035720", name: "카카오", market_scope: "kr"},
  ["chips"],
  items,
  groups,
);
const moved = applyWatchStockAddSelection(items[0], ["income"], added.nextItems, added.nextGroups);
console.log(JSON.stringify({added, moved}));
'''
    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert [item["code"] for item in payload["added"]["nextItems"]] == [
        "005930",
        "000660",
        "035720",
    ]
    assert payload["added"]["nextGroups"] == [
        {"id": "chips", "name": "반도체", "codes": ["005930", "035720"]},
        {"id": "income", "name": "배당주", "codes": ["000660"]},
    ]
    assert payload["moved"]["alreadySaved"] is True
    assert [item["code"] for item in payload["moved"]["nextItems"]] == [
        "005930",
        "000660",
        "035720",
    ]
    assert payload["moved"]["nextGroups"] == [
        {"id": "chips", "name": "반도체", "codes": ["035720"]},
        {"id": "income", "name": "배당주", "codes": ["000660", "005930"]},
    ]


def test_recommendation_cards_use_one_compact_action_row():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'actions.append(watchButton, trackButton, explainButton);',
        'isWatched(item.code) ? "관심 해제" : "관심 추가"',
        'isTrackedRecommendation(item.code) ? "핀 종목 보기" : "핀 설정하기"',
        'el("button", "recommend-ai-button", "AI 시그널 보기")',
        "grid-template-columns: repeat(3, minmax(0, 1fr));",
    ):
        assert expected in source or expected in styles

    assert 'el("button", "recommend-refresh", "새로고침")' not in source


def test_recommendation_ai_explanation_opens_on_a_dedicated_page():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'id="recommend-detail-page"',
        'function openRecommendationDetail(item)',
        'setView("recommend-detail");',
        'openRecommendationDetail(card.recommendationItem);',
        'Ollama AI 분석 완료',
    ):
        assert expected in source or expected in client.get("/dashboard?view=recommend-detail").text

    assert 'renderRecommendationAIExplanation(card)' not in source
    assert 'detailsSummary.textContent = "세부 점수와 근거 보기"' not in source
    assert ".recommend-detail-page" in styles


def test_recommendation_detail_is_single_column_and_action_first_on_mobile():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    detail_render = source.split("function renderRecommendationDetail", 1)[1].split("async function loadRecommendationDetail", 1)[0]
    signal_flow = detail_render.index("createRecommendationDecisionFlow(item, {")
    assert detail_render.index("hero,") < signal_flow
    assert signal_flow < detail_render.index("action,")
    assert 'options.detail ? "AI 시그널 여정" : "현재 단계"' in source
    assert '"AI 대응 · 지금 할 일"' in source

    assert ".recommend-detail-content {\n  display: grid;\n  grid-template-columns: minmax(0, 1fr);" in styles
    assert ".recommend-detail-content > .recommend-decision-flow.is-detail {\n  grid-area: auto;" in styles
    assert "overflow-wrap: break-word;\n  word-break: keep-all;" in styles


def test_recommendation_detail_revalidates_current_recommendation_before_rendering():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    detail_loader = source.split("async function loadRecommendationDetail", 1)[1].split("function openRecommendationDetail", 1)[0]

    assert "RECOMMENDATION_DETAIL_CACHE_VERSION = 2" in source
    assert "RECOMMENDATION_DETAIL_CACHE_TTL_MS = 5 * 60_000" in source
    assert 'parsed.pathname === "/market/recommendations"' in source
    assert "const payload = await fetchRecommendationsForScope({ limit: 20, candidateLimit: 100, force: true, ttlMs: 0 });" in detail_loader
    assert detail_loader.index("const payload = await fetchRecommendationsForScope") < detail_loader.index("saveRecommendationDetailItem(item)")
    assert "clearRecommendationDetailItem();" in detail_loader


def test_recommendation_cards_show_linked_signal_status_and_load_full_history_on_demand():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "function recommendationSignalStageView",
        "function recommendationShouldCollectSignal",
        'headline: "시그널 수집 중"',
        'if (action === "entry_watch")',
        'headline: "예비 포착"',
        '`${profitStage || 1}차 수익확정 후 보유`',
        'headline: "전량 매도"',
        'headline: "조건 해제"',
        'stage.changedLabel || "마지막 변경"',
        'el("dt", "", "다음 조건")',
        'function recommendationSignalTimelineItems',
        '"추천 전 이력"',
        'const [aiResult, signalResult] = await Promise.all([',
        'liveUrl(`/stocks/${encodeURIComponent(item.code)}/quant-signals`)',
        '"시그널 다시 불러오기"',
    ):
        assert expected in source

    card_render = source.split("function createRecommendationCard", 1)[1].split("function appendRecommendationCard", 1)[0]
    assert "createRecommendationDecisionFlow(item)" in card_render
    assert 'el("section", "recommend-card-reason")' in card_render
    assert 'recommendationReasonSummary(item)' in card_render
    assert card_render.index('const reason = el("section", "recommend-card-reason")') < card_render.index("createRecommendationDecisionFlow(item)")
    assert "createRecommendationUsSectorSummary(item)" not in card_render
    assert 'const metrics = el("div", "recommend-metrics")' not in card_render

    for expected in (
        "/* Recommendation lifecycle 5.4",
        ".recommend-signal-stage",
        ".recommend-signal-facts",
        ".recommend-signal-timeline",
        ".recommend-signal-retry:focus-visible",
        "/* Recommendation context 5.5",
        ".recommend-card-reason",
        ".recommend-signal-stage.is-collecting",
        "font-size: var(--app-type-button) !important;",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert expected in styles

    detail_render = source.split("function renderRecommendationDetail", 1)[1].split("async function loadRecommendationDetail", 1)[0]
    assert 'el("h1", "", "추천한 핵심 이유")' in detail_render
    assert 'recommendationReasonSummary(item)' in detail_render
    assert '"추천 이후 신규 매수 시그널을 수집하고 있습니다."' in detail_render


def test_recommendation_score_explains_scale_and_interpretation():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'el("span", "", "/ 100")',
        'help.setAttribute("aria-label", "추천 점수 설명")',
        '"70점 이상은 우수, 55~69점은 관찰, 55점 미만은 신중 구간입니다."',
        '"매수 확정이나 수익률 보장을 뜻하지 않습니다."',
        'return { label: "우수", guide: "70점 이상", className: "high" };',
        'return { label: "관찰", guide: "55~69점", className: "watch" };',
        'return { label: "신중", guide: "55점 미만", className: "cautious" };',
    ):
        assert expected in source

    assert '"recommend-as-of"' not in source
    assert '`추천 기준 ${recommendationMoment(recommendedAt)}`' not in source

    for expected in (
        "#recommend-view .recommend-score-value",
        "#recommend-view .recommend-score-help::after",
        "#recommend-view .recommend-score-level.high",
    ):
        assert expected in styles


def test_tracked_recommendation_uses_readable_values_and_stock_detail_table():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "function sanitizeRecommendationTrackPoint",
        "function recommendationPinSummary",
        "function recommendationPinHighlights",
        'return "1개월·3개월 수익률 데이터가 부족해 최근 가격과 거래대금을 우선 확인합니다.";',
        'return "판단 정보 없음";',
        'return `${formatNumber(score)}점 / 100점`;',
        '["핀 시작일", track.tracked_at ? formatDateLabel',
        '["핀 시작가", trackedPrice !== null',
        '["현재가", currentPrice !== null',
        '["수익률", profit.rate !== null',
        '["시작 판단", recommendationTrackDecisionLabel',
        'el("h3", "", "핀 시작 정보")',
        'el("h3", "", "핵심 요약")',
        'el("h3", "", "확인할 것")',
        "setRecommendationTrackExpanded(nextCard, keepExpanded);",
        'open.className = "recommend-track-stock-link";',
        'el("button", "recommend-track-remove track-delete", "핀 해제하기")',
        'stockDetail.textContent = "종목 상세";',
        'metrics.className = "recommend-track-metrics";',
        'el("span", "recommend-track-detail-toggle-label", "핵심 정보 보기")',
        'el("span", "recommend-track-detail-toggle-icon", "+")',
    ):
        assert expected in source

    assert 'open.className = "snapshot-button";' not in source
    assert 'el("button", "snapshot-delete track-delete", "추적 해제")' not in source
    assert '["주당 손익"' not in source
    for old_label in ('"추적 보기"', '"추적 종목"', '"추적 해제"', '["추적가"'):
        assert old_label not in source

    for expected in (
        "/* Tracked recommendation tables match the continuous stock-detail table. */",
        "/* Tracked recommendations use the same flat section language as stock detail. */",
        "/* Final tracking layout overrides legacy dashboard card rules. */",
        "/* Pin portfolio 5.0 final precedence: mirror the stock-detail visual system. */",
        "#recommend-history-view :is(",
        ".recommend-track-signals > div:last-child",
        ".recommend-track-saved-info",
        ".recommend-track-stock-link",
        ".recommend-track-remove",
        ".recommend-track-detail-toggle-icon",
        "grid-template-columns: repeat(2, minmax(0, 1fr));",
    ):
        assert expected in styles

    shell = client.get("/dashboard?view=recommend-history").text
    assert '>핀 종목</button>' in shell
    assert "핀 종목 없음" in shell
    assert "추적종목" not in shell


def test_watchlist_v15_is_responsive_and_matches_stock_detail_tokens():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "/* Dashboard stock-detail fidelity 3.3 */",
        "#recommend-history-view .recommend-history.archive-page",
        "#recommend-history-view > .app-section-heading",
        "padding: 16px 20px 14px;",
        "#portfolio-tracking-panel",
        "#trend-view .trend-tabs",
        "width: calc(100% + 40px) !important;",
        ".market-impact-hero",
        ".market-impact-factor-row",
        ".market-impact-factor-track",
        ".market-impact-balance-track",
        ".market-impact-metric",
        ".market-impact-stock-tags a",
        ".push-notification-condition",
        "box-shadow: none !important;",
        "border-radius: 8px;",
        "border-radius: 6px;",
        "border-radius: 0;",
    ):
        assert expected in styles

    for expected in (
        "/* Watchlist 3.1:",
        "#watchlist-view.watchlist-v3",
        "grid-template-columns: minmax(0, 1fr);",
        "grid-template-columns: repeat(2, minmax(0, 1fr));",
        "@media (max-width: 720px)",
        "grid-template-columns: repeat(3, minmax(0, 1fr));",
        '"Apple SD Gothic Neo"',
        "overflow: clip;",
        "flex-direction: row;",
        "align-items: flex-start;",
        ".watch-v3-tabs button.active::after",
        "font-size: 16px !important;",
    ):
        assert expected in styles

    assert "#watchlist-view.watchlist-v3 .watch-v2-list-surface" in styles
    assert "#watchlist-view.watchlist-v3 .watchlist-empty-card" in styles


def test_event_calendar_uses_week_strip_and_dedicated_impact_detail():
    client = TestClient(app)
    shell = client.get("/dashboard?view=trend").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "function renderTrendCalendar(payload = state.homeTrendContext || {})",
        "function appendTrendEvent(item, parent = elements.trendEvents)",
        'button.dataset.trendEventOpen = item.id || "";',
        "function renderTrendEventDetail(item)",
        'el("span", "event-detail-eyebrow", "한눈에 보기")',
        'el("h3", "", "이번 발표에서 볼 것")',
        'el("h3", "", "3단계로 확인하세요")',
        "function appendTrendScenario(parent, label, stocks = [], tone = \"neutral\")",
        'el("summary", "", "영향 경로 자세히 보기")',
        "function renderTrendGraph(card, graph)",
        'el("h3", "", "시장은 이렇게 반응할 수 있어요")',
        'setView("event-detail");',
        'elements.homePastToggleLabel.textContent = pastEventsExpanded ? "지난 이벤트 접기" : "지난 이벤트 펼치기"',
    ):
        assert expected in source

    for expected in (
        "/* News preview, trading calendar, and event analysis 7.0. */",
        ".trend-calendar-days",
        ".trend-calendar-day.active",
        ".trend-calendar-event",
        ".event-detail-hero",
        ".event-detail-watch-list",
        ".event-detail-graph > .event-flow",
        ".event-detail-graph .impact-columns",
        "#trend-events-panel .trend-past-toggle",
    ):
        assert expected in styles

    assert 'id="trend-calendar-days" role="tablist"' in shell
    assert 'id="trend-calendar-selected-date"' not in shell
    assert 'id="trend-calendar-event-count" aria-live="polite">0개 일정</span>' in shell
    assert "trendCalendarSelectedDate" not in source
    assert 'id="event-detail-view" class="app-page event-detail-page"' in shell
    assert 'id="event-detail-back"' in shell
    assert 'id="home-past-toggle"' in shell
    assert 'aria-controls="trend-past-panel"' in shell
    assert 'id="home-past-toggle-label">지난 이벤트 펼치기</strong>' in shell
    assert '<small>최근 2주</small>' in shell
    assert 'aria-label="최근 2주 지난 이벤트"' in shell
    assert 'data-trend-tab="impact" data-archived="true"' in shell
    assert '#trend-view [data-archived="true"]' in styles
    assert 'class="trend-panel home-market-card home-news-card"' in shell
    assert 'class="trend-panel home-market-card home-events-card"' in shell
    assert '#trend-view.home-market-sections' in styles
    assert '#trend-view .home-market-card' in styles


def test_market_impact_uses_beginner_signal_summary_without_five_element_metaphor():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "const MARKET_BEGINNER_FACTOR_ORDER",
        "const MARKET_BEGINNER_COPY",
        "function marketImpactBeginnerStatus",
        "function marketImpactBeginnerShortStatus",
        "function marketImpactBeginnerSummary",
        "function marketImpactEvidenceItems",
        "function appendMarketBeginnerThreadItem",
        "function createMarketBeginnerImpactChart",
        'el("section", "market-beginner-signals")',
        'el("h2", "", "5개 변수를 한 줄씩 읽어보세요")',
        'detailsSummary.textContent = "숫자와 공식 출처 확인"',
        'el("div", "market-impact-source-list")',
        'el("div", "market-thread-list")',
        'el("article", `market-thread-item',
        'el("div", "market-beginner-impact-chart")',
        'period: "5일", value: item.change_5d_text',
        'period: "현재", value: item.value_text || "자료 없음"',
    ):
        assert expected in source

    for expected in (
        "/* Market impact beginner mode: answer",
        ".market-beginner-dashboard",
        ".market-beginner-summary",
        ".market-beginner-signal-row",
        ".market-beginner-status",
        ".market-beginner-impact-chart",
        ".market-beginner-impact-bar-fill",
        ".market-beginner-signal-evidence",
        ".market-beginner-disclosure",
        "/* Market impact thread 3.0:",
        ".market-thread-list",
        ".market-thread-item",
        ".market-thread-avatar",
        ".market-thread-metric",
        ".market-thread-sector",
    ):
        assert expected in styles

    assert 'label: "금리", percent:' not in source
    assert "외부 변수 → 국내증시 → 영향 종목" not in source
    assert "채권 가격이 오르면 채권금리는 내려갑니다." in source
    assert "나스닥은 오르고 비트코인은 내리는 엇갈린 신호" in source
    assert "좋은 신호" in source
    assert "주의 신호" in source
    assert "function appendMarketBeginnerSignalRow" not in source
    assert "시장 변수 연결도" not in source
    assert "오행별" not in source
    assert 'el("span", `market-impact-icon ${factor.key || factor.className || ""}`, factor.label)' not in source
    assert source.count("appendMarketImpactDetail(detailGrid, factor)") == 1


def test_dashboard_v32_uses_stock_detail_typography_on_every_page():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        "/* Dashboard typography system 3.2:",
        "--app-type-page: 24px;",
        "--app-type-section: 20px;",
        "--app-type-body: 14px;",
        "--app-type-label: 11px;",
        "--app-type-metric: 15px;",
        "--app-type-page: 20px;",
        "--app-type-tab: 16px;",
        "--app-type-section: 19px;",
        "--app-type-body: 15px;",
        "--app-type-label: 12px;",
        ".market-leaderboard-name strong",
        ".recommend-name strong",
        ".watch-chart-row-main strong",
        ".loading-modal-card h2",
        ".push-notification-sheet-head h2",
        ".login-card h1",
    ):
        assert expected in styles


def test_market_lists_share_stock_logo_identity():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'function createStockListLogo(code, className = "")',
        "`/stock-logos/${encodeURIComponent(normalizedCode)}.png?v=${encodeURIComponent(DASHBOARD_CLIENT_VERSION)}`",
        "fallbackIcon.src = STOCK_LOGO_FALLBACK_DATA_URL;",
        'image.loading = "eager";',
        'image.addEventListener("error", () => {',
        'function createRankingStockLogo(item = {})',
            'const logo = createStockListLogo(item.code);',
            'if (item.currency === "USD") logo.classList.add("is-us-stock-logo");',
        "identity.append(\n    createRankingStockLogo(item),\n    createStockListCopy(item.name, item.code)",
        "createStockListCopy(item.name, item.code)",
    ):
        assert expected in source

    for expected in (
        ".stock-list-logo {",
        ".stock-list-logo-image {",
        "object-fit: contain;",
        ".home-surge-identity {",
        ".recommend-name .stock-list-copy",
    ):
        assert expected in styles


def test_market_ranking_tabs_reserve_their_full_mobile_grid_row():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    assert "/* Market movers 5.1: reserve the tabs' full mobile height before the stock list. */" in styles
    assert "grid-template-rows: auto auto minmax(0, 1fr);" in styles
    assert "#market-view.app-market-rankings .market-ranking-commandbar,\n#market-view.app-market-rankings .market-ranking-tabs {\n  box-sizing: border-box;" in styles
    assert "#market-view.app-market-rankings .market-ranking-tabs {\n  align-self: start;" in styles
