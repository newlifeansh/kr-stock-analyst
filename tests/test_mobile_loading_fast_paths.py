import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.db import Base, get_db
from app.main import app
from app.models import CompletePayloadSnapshot, NewsItem, StockMaster, StockNewsSnapshot
from app.services import stock_dashboard
from app.services.complete_snapshots import publish


def _dashboard_source() -> str:
    return TestClient(app).get("/assets/dashboard/app.js").text


def _function_source(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index(f"function {next_name}(", start + 1)]


def test_stock_detail_hydrates_stable_snapshot_before_live_quote_stream():
    source = _dashboard_source()
    load_source = _function_source(source, "loadStockRequest", "load")
    render_source = _function_source(source, "render", "resolveStock")

    assert "/dashboard?include_profile=0&include_live=0" in load_source
    assert "include_live=1" not in load_source
    assert "const loadSequence = ++state.stockLoadSequence;" in load_source
    assert load_source.count("loadSequence !== state.stockLoadSequence") >= 4
    assert "const initialQuoteRequest = fetchInitialStockQuote(stock.code);" in load_source
    assert "Promise.all([dashboardRequest, initialQuoteRequest])" in load_source
    assert load_source.index("hydrateInitialStockQuote(") < load_source.index("render(dashboard")
    assert 'state.stockQuoteReadyCode === String(data.code || "")' in render_source
    assert "resetStockQuoteDisplay();" in render_source
    assert "connectQuoteStream(state.currentStock);" in render_source
    assert "dashboard.momentum.latest_trading_value = quoteDelta.trading_value;" in source
    assert "value !== null && value !== undefined" in source
    assert render_source.index("void loadStockHomeDetails(data);") < render_source.index("ensureStockAIAnalysis();")


def test_stock_detail_secondary_loaders_keep_dashboard_visible_and_retry_context_only():
    source = _dashboard_source()
    price_source = _function_source(source, "loadStockPriceSummary", "loadStockIntraday")
    intraday_source = _function_source(source, "loadStockIntraday", "loadStockCommunity")
    legacy_source = _function_source(source, "loadStockHomeDetailsLegacy", "loadStockHomeDetails")
    home_source = _function_source(source, "loadStockHomeDetails", "formatMultiple")

    assert "resetStockPriceSummary();" not in price_source
    assert "state.stockPriceRows = [];" not in price_source
    assert "const previousPrices = Array.isArray(state.stockPriceRows)" in price_source
    assert "resetStockHomeDetails();" not in home_source
    assert "loadStockIntraday(code, requestId)" not in legacy_source
    assert "state.stockIntradayPending.get(code)" in intraday_source
    assert "state.stockIntradayPending.set(code, pending)" in intraday_source
    assert "const contextRetry = options.contextRetry === true;" in home_source
    assert "state.stockFlowHistoryLoading = false;" in home_source
    assert 'state.stockFlowHistoryError = "";' in home_source
    assert "? Promise.resolve()" in home_source
    assert "void loadStockHomeDetails(data, { contextRetry: true });" in home_source
    assert "/stocks/${encodeURIComponent(code)}/news-items?limit=30" in legacy_source
    assert "const stockNewsPromise" in home_source
    assert "const stockNewsRows = await stockNewsPromise;" in home_source
    assert "state.stockNewsRows = stockNewsRows;" in home_source


def test_page_loading_cancels_stale_animation_frame_before_it_can_restore_overlay():
    source = _dashboard_source()
    refresh_source = _function_source(source, "refreshPageLoading", "clearPageLoading")
    clear_source = _function_source(source, "clearPageLoading", "beginPageLoading")
    script = """
let nextId = 1;
let lastFrame = null;
let lastTimer = null;
const classes = new Set();
const state = {
  pageLoadingTokens: new Map([[1, { label: "추천 종목을 분석하는 중" }]]),
  pageLoadingFrameId: null,
  pageLoadingHideTimer: null,
};
const elements = {
  pageLoading: {
    hidden: true,
    classList: {
      add(value) { classes.add(value); },
      remove(value) { classes.delete(value); },
    },
  },
  pageLoadingLabel: { textContent: "" },
};
const document = {
  body: {
    setAttribute() {},
    removeAttribute() {},
  },
};
const window = {
  requestAnimationFrame(callback) { lastFrame = callback; return nextId++; },
  cancelAnimationFrame() {},
  setTimeout(callback) { lastTimer = callback; return nextId++; },
  clearTimeout() {},
};
""" + refresh_source + clear_source + """
refreshPageLoading();
const staleFrame = lastFrame;
state.pageLoadingTokens.clear();
refreshPageLoading();
staleFrame();
lastTimer();
const hiddenAfterEnd = elements.pageLoading.hidden;
const visibleAfterEnd = classes.has("visible");

state.pageLoadingTokens.set(2, { label: "관심 종목을 점검하는 중" });
refreshPageLoading();
const staleFrameAfterClear = lastFrame;
clearPageLoading();
staleFrameAfterClear();
console.log(JSON.stringify({
  hiddenAfterEnd,
  visibleAfterEnd,
  hiddenAfterClear: elements.pageLoading.hidden,
  visibleAfterClear: classes.has("visible"),
}));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result == {
        "hiddenAfterEnd": True,
        "visibleAfterEnd": False,
        "hiddenAfterClear": True,
        "visibleAfterClear": False,
    }


def test_stock_news_snapshot_refreshes_by_code_and_deduplicates_in_latest_order(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    db.add(StockMaster(code="373220", name="LG에너지솔루션", market="KOSPI", is_active=True))
    db.add(
        StockNewsSnapshot(
            stock_code="373220",
            source="naver_finance",
            payload="[]",
            fetched_at=datetime.utcnow() - timedelta(days=1),
        )
    )
    db.commit()
    monkeypatch.setattr(
        stock_dashboard,
        "_naver_item_news",
        lambda _code: [
            {
                "title": "오전 기사",
                "source": "테스트경제",
                "url": "https://finance.naver.com/item/news_read.naver?article_id=2&office_id=011",
                "published_at": datetime(2026, 8, 28, 9, 0),
            },
            {
                "title": "오후 최신 기사",
                "source": "테스트경제",
                "url": "https://finance.naver.com/item/news_read.naver?article_id=3&office_id=011",
                "published_at": datetime(2026, 8, 28, 15, 0),
            },
            {
                "title": "오후 최신 기사 중복",
                "source": "테스트경제",
                "url": "https://finance.naver.com/item/news_read.naver?article_id=3&office_id=011",
                "published_at": datetime(2026, 8, 28, 15, 0),
            },
        ],
    )
    try:
        rows = stock_dashboard.stock_news_item_payloads(db, "373220", limit=10)
        assert [row["title"] for row in rows] == ["오후 최신 기사", "오전 기사"]
        assert rows[0]["external_id"] == "011:3"
        assert rows[0]["source_category"] == "company"
        assert rows[0]["detail_url"] == "https://n.news.naver.com/mnews/article/011/3"
        assert db.get(StockNewsSnapshot, "373220").fetched_at > datetime.utcnow() - timedelta(minutes=1)
    finally:
        db.close()


def test_naver_stock_news_excludes_cluster_related_rows(monkeypatch):
    class FakeResponse:
        text = """
        <table class="type5"><tbody>
          <tr class="first relation_tit">
            <td class="title"><a href="/item/news_read.naver?article_id=10&amp;office_id=011">종목 대표 기사</a></td>
            <td class="info">서울경제</td><td class="date">2026.08.28 17:00</td>
          </tr>
          <tr class="relation_lst _clusterId01110"><td colspan="3"><table><tbody>
            <tr><td class="title"><a href="/item/news_read.naver?article_id=11&amp;office_id=009">연관 기사</a></td>
            <td class="info">매일경제</td><td class="date">2026.08.28 16:50</td></tr>
          </tbody></table></td></tr>
          <tr>
            <td class="title"><a href="/item/news_read.naver?article_id=12&amp;office_id=018">다음 종목 기사</a></td>
            <td class="info">이데일리</td><td class="date">2026.08.28 16:00</td>
          </tr>
        </tbody></table>
        """
        encoding = None

        def raise_for_status(self):
            return None

    monkeypatch.setattr(stock_dashboard.requests, "get", lambda *args, **kwargs: FakeResponse())

    rows = stock_dashboard._fetch_naver_item_news("373220", strict=True)

    assert [row["title"] for row in rows] == ["종목 대표 기사", "다음 종목 기사"]


def test_stock_sentiment_prioritizes_fresh_code_news_over_an_older_exact_name_match(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    stock = StockMaster(code="373220", name="LG에너지솔루션", market="KOSPI", is_active=True)
    db.add(stock)
    db.add(
        NewsItem(
            source="naver_finance",
            source_category="company",
            external_id="018:old",
            title="LG에너지솔루션 7월 기사",
            press_name="이데일리",
            detail_url="https://n.news.naver.com/mnews/article/018/1",
            published_at=datetime.utcnow() - timedelta(days=28),
        )
    )
    db.add(
        StockNewsSnapshot(
            stock_code="373220",
            source="naver_finance",
            payload=json.dumps(
                [
                    {
                        "title": "LG엔솔 오늘 최신 기사",
                        "source": "서울경제",
                        "url": "https://finance.naver.com/item/news_read.naver?article_id=3&office_id=011",
                        "published_at": datetime.utcnow().isoformat(),
                    }
                ],
                ensure_ascii=False,
            ),
            fetched_at=datetime.utcnow(),
        )
    )
    db.commit()
    monkeypatch.setattr(
        stock_dashboard,
        "_naver_item_news",
        lambda _code: (_ for _ in ()).throw(AssertionError("fresh snapshot should not refetch")),
    )
    try:
        payload = stock_dashboard._sentiment(db, stock, [], {}, allow_external=True)
        assert [item["title"] for item in payload["latest_items"]] == [
            "LG엔솔 오늘 최신 기사",
            "LG에너지솔루션 7월 기사",
        ]
        assert payload["latest_items"][0]["url"] == "https://n.news.naver.com/mnews/article/011/3"
    finally:
        db.close()


def test_stock_flow_rechecks_latest_rows_even_when_snapshot_has_full_history():
    source = _dashboard_source()
    ensure_start = source.index("async function ensureStockFlowHistory(")
    ensure_source = source[ensure_start : source.index("function formatSignedShares(", ensure_start)]
    script = """
const calls = [];
let latestFlowRenders = 0;
let historyRenders = 0;
const STOCK_FLOW_PERIODS = {
  "3M": { count: 66, months: 3, label: "3개월" },
};
const state = {
  stockFlowRows: Array.from({ length: 66 }, (_, index) => ({ id: index })),
  stockFlowPeriod: "3M",
  stockFlowHistoryTargetCount: 0,
  stockFlowHistoryError: "",
  stockFlowHistoryLoading: false,
  stockHomeDetailsRequestId: 7,
  currentStock: { code: "011200" },
  currentDashboard: { flows: {} },
};
function stockFlowGroupedRows() { return state.stockFlowRows; }
function renderStockFlowHistoryChart() { historyRenders += 1; }
function liveUrl(url) { return `${url}&_=fresh`; }
function fetchJsonCached(url, options) {
  calls.push({ url, options });
  return Promise.resolve([{ id: 67, trade_date: "2026-08-24", investor_type: "외국인" }]);
}
function mergeStockFlowRows(currentRows, incomingRows) { return [...currentRows, ...incomingRows]; }
function renderLatestStockFlowRows() { latestFlowRenders += 1; }
""" + ensure_source + """
(async () => {
  await ensureStockFlowHistory("011200", "3M", 7);
  console.log(JSON.stringify({ calls, latestFlowRenders, historyRenders, loading: state.stockFlowHistoryLoading }));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert len(result["calls"]) == 1
    assert "/stocks/011200/flows?limit=1500" in result["calls"][0]["url"]
    assert "refresh=true" not in result["calls"][0]["url"]
    assert result["calls"][0]["options"] == {
        "force": True,
        "ttlMs": 0,
        "timeoutMs": 15_000,
    }
    assert result["latestFlowRenders"] == 2
    assert result["historyRenders"] == 1
    assert result["loading"] is False


def test_warming_dashboard_is_rechecked_without_blocking_or_cache_reuse():
    source = _dashboard_source()
    warm_source = _function_source(
        source,
        "scheduleStockDashboardWarmRefresh",
        "loadStockRequest",
    )

    assert 'const STOCK_DASHBOARD_WARMING_SOURCE = "stored_database_warming";' in source
    assert "force: true" in warm_source
    assert "state.responseCache.delete(dashboardUrl);" in warm_source
    assert "scheduleStockDashboardWarmRefresh(stock, attempt + 1);" in warm_source
    assert warm_source.count("expectedSequence !== state.stockLoadSequence") >= 2
    assert warm_source.index("dashboard?.source === STOCK_DASHBOARD_WARMING_SOURCE") < warm_source.index(
        "render(dashboard, { previousCode: code });"
    )


def test_hidden_stock_analysis_is_loaded_only_when_its_tab_is_selected():
    source = _dashboard_source()
    render_source = _function_source(source, "render", "resolveStock")
    load_source = _function_source(source, "loadStockRequest", "load")

    assert "void loadStockCompanyAnalysis(data);" not in render_source
    assert "const quantSignalPrefetch" not in load_source
    assert 'return tabName === "strategy" && Boolean(state.currentStock?.code);' in source
    assert 'state.stockActiveTab !== "company"' in source
    assert "ensureStockCompanyAnalysis();" in source


def test_live_quote_merge_preserves_complete_values_and_rejects_older_ticks():
    source = _dashboard_source()
    merge_source = _function_source(source, "applyLiveQuoteToDashboard", "formatChangeValue")
    strip_source = _function_source(source, "updateQuoteStrip", "updateWatchlistStreamStatus")
    price_source = _function_source(source, "loadStockPriceSummary", "loadStockIntraday")

    assert "value !== null && value !== undefined && value !== \"\"" in merge_source
    assert "Object.assign(mergedQuote, quoteDelta);" in merge_source
    assert "observedAt < previousObservedAt" in merge_source
    assert "return false;" in merge_source
    assert "const displayQuote = state.currentDashboard?.quote || quote;" in strip_source
    assert "if (!accepted)" in strip_source
    assert "const currentQuote = state.currentDashboard?.quote || quote;" in price_source
    assert price_source.count("state.currentStock?.code !== code") >= 2


def test_stale_quote_is_rejected_before_detail_quant_and_watchlist_updates_and_live_delta_carries_forward():
    project_root = Path(__file__).resolve().parents[1]
    script = r"""
const fs = require("fs");
const source = fs.readFileSync("app/static/dashboard/app.js", "utf8");
function functionSource(name, nextName) {
  const start = source.indexOf(`function ${name}`);
  const end = source.indexOf(`function ${nextName}`, start + 1);
  if (start < 0 || end < 0) throw new Error(`${name} not found`);
  return source.slice(start, end);
}
const dashboardLiveQuoteTimes = new WeakMap();
const dashboardLiveQuoteDeltas = new WeakMap();
function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}
function renderQuantCurrentStatus() {}
function selectorEscape(value) { return String(value); }
eval(functionSource("rebasePeriodReturn", "applyLiveQuoteToDashboard"));
eval(functionSource("applyLiveQuoteToDashboard", "carryForwardLiveQuoteToDashboard"));
eval(functionSource("carryForwardLiveQuoteToDashboard", "formatChangeValue"));
eval(functionSource("quantSignalLiveReturnRate", "applyStockQuantSignalLiveQuote"));
eval(functionSource("applyStockQuantSignalLiveQuote", "updateAiSignalLiveQuote"));
eval(functionSource("updateQuoteStrip", "quoteStreamCodes"));
eval(functionSource("updateWatchlistRowQuote", "connectWatchlistQuoteStream"));

const newer = { code: "005930", market: "KOSPI", as_of: "2026-08-13T10:01:00+09:00", source: "test" };
const older = { code: "005930", market: "KOSPI", as_of: "2026-08-13T10:00:00+09:00", source: "test" };
const detail = {
  code: "005930",
  market: "KOSPI",
  quote: { price: 100, market_cap: 1000 },
  momentum: { one_month_return: 1, three_month_return: 2 },
};
const state = {
  currentStock: { code: "005930" },
  currentDashboard: detail,
  stockQuantRequestedCode: "005930",
  stockQuantSignals: {
    current: {
      position_open: true,
      price: 110,
      return_basis: { price: 100, return_rate: 0, return_rate_per_price: 1 },
    },
    display_return_rate: 10,
  },
};
const watchDashboard = {
  code: "005930",
  quote: { price: 100, market_cap: 1000 },
  momentum: { one_month_return: 1, three_month_return: 2 },
};
const watchCard = { watchDashboard, querySelector: () => null };
const elements = { watchlistBody: { querySelector: () => watchCard } };

applyLiveQuoteToDashboard(detail, { price: 110, market_cap: null }, newer);
applyLiveQuoteToDashboard(watchDashboard, { price: 110 }, newer);
const staleDetailAccepted = updateQuoteStrip({ price: 90 }, older);
const staleWatchAccepted = updateWatchlistRowQuote("005930", { price: 90 }, older);
const refreshed = {
  code: "005930",
  market: "KOSPI",
  quote: { price: 101, market_cap: 2000 },
  momentum: { one_month_return: 3, three_month_return: 4 },
};
const carried = carryForwardLiveQuoteToDashboard(refreshed, detail);
console.log(JSON.stringify({
  staleDetailAccepted,
  staleWatchAccepted,
  detailPrice: detail.quote.price,
  detailMarketCap: detail.quote.market_cap,
  quantPrice: state.stockQuantSignals.current.price,
  watchPrice: watchDashboard.quote.price,
  carried,
  refreshedPrice: refreshed.quote.price,
  refreshedMarketCap: refreshed.quote.market_cap,
}));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "staleDetailAccepted": False,
        "staleWatchAccepted": False,
        "detailPrice": 110,
        "detailMarketCap": 1000,
        "quantPrice": 110,
        "watchPrice": 110,
        "carried": True,
        "refreshedPrice": 110,
        "refreshedMarketCap": 2000,
    }


def test_stock_async_results_are_scoped_and_same_stock_failure_keeps_last_complete_view():
    source = _dashboard_source()
    view_source = _function_source(source, "setView", "renderEvents")
    loading_source = _function_source(source, "setLoading", "render")
    load_source = _function_source(source, "loadStockRequest", "load")
    ai_source = _function_source(source, "loadAIAnalysis", "readRecommendationHistory")

    assert 'if (view !== "stock") {' in view_source
    assert "state.stockLoadSequence += 1;" in view_source
    assert "state.stockAIRequestSequence += 1;" in view_source
    assert "closeQuoteStream();" in loading_source
    assert "const sameStock = previousStock?.code === stock.code;" in load_source
    assert "if (!sameStock) {" in load_source
    assert "carryForwardLiveQuoteToDashboard(dashboard, previousDashboard);" in load_source
    assert "error?.status === 503" in load_source
    assert "state.stockLoadRetryTimer = window.setTimeout" in load_source
    assert "loadSequence === state.stockLoadSequence" in load_source
    assert "requestSequence !== state.stockAIRequestSequence" in ai_source
    assert "state.currentStock?.code !== code" in ai_source


def test_switching_stocks_clears_previous_stock_content_before_resolution():
    source = _dashboard_source()
    loading_source = _function_source(source, "setLoading", "render")
    load_source = _function_source(source, "loadStockRequest", "load")
    quote_reset_source = _function_source(source, "resetStockQuoteDisplay", "resetStockPriceSummary")
    price_reset_source = _function_source(source, "resetStockPriceSummary", "renderStockHomeChartMessage")
    home_reset_source = _function_source(source, "resetStockHomeDetails", "renderStockPriceSummaryFromPrices")
    profile_reset_source = _function_source(source, "resetStockCompanyProfile", "renderStockDerivedIndicators")
    company_reset_source = _function_source(source, "resetStockCompanyAnalysis", "loadStockCompanyAnalysis")
    quote_animation_source = _function_source(source, "animateQuoteNumber", "updateQuoteStrip")

    assert load_source.index("setLoading(normalized);") < load_source.index("await resolveStock(normalized)")
    for stock_value in (
        "elements.quotePrice",
        "elements.stockChangeValue",
        "elements.quoteChange",
        "elements.stockVolume",
        "elements.quoteValue",
        "elements.quoteCap",
    ):
        assert stock_value in quote_reset_source
    assert "resetStockQuoteDisplay();" in price_reset_source
    assert "delete node.dataset.rawValue;" in quote_reset_source
    assert "quoteAnimationSequence" in quote_reset_source
    assert "새 종목의 시세와 수급을 확인하는 중입니다." in home_reset_source
    assert 'setText(elements.stockFlowSummary, "수급 이력 준비 중")' in home_reset_source
    assert "elements.stockResearchList.innerHTML" in home_reset_source
    assert "elements.newsList.innerHTML" in home_reset_source
    assert "elements.stockNewsTemperature.innerHTML" in home_reset_source
    assert 'setText(elements.stockCompanySummary, "기업 정보를 불러오는 중입니다.")' in profile_reset_source
    assert 'setText(elements.stockRevenueBreakdownTitle, "매출 심층 분석")' in company_reset_source
    assert 'setText(elements.stockSectorMarginSource, "동일 업종 · 매출 상위 5개사")' in company_reset_source
    assert "resetStockCompanyProfile();" in loading_source
    assert "updateWatchButton();" in loading_source
    assert "node.dataset.quoteAnimationSequence !== String(animationSequence)" in quote_animation_source


def test_mobile_stock_search_is_not_closed_by_background_stock_retries():
    source = _dashboard_source()
    collapse_source = _function_source(source, "collapseStockSearch", "setActiveSuggestion")
    choose_source = _function_source(source, "chooseSuggestion", "renderSuggestions")
    load_source = _function_source(source, "loadStockRequest", "load")
    submit_start = source.index('elements.form.addEventListener("submit"')
    submit_end = source.index('document.addEventListener("click"', submit_start)
    submit_source = source[submit_start:submit_end]

    assert "hideSuggestions();" in collapse_source
    assert 'elements.form?.classList.remove("expanded");' in collapse_source
    assert "collapseStockSearch" not in load_source
    assert 'classList.remove("expanded")' not in load_source
    assert "hideSuggestions();" not in load_source
    assert choose_source.index("collapseStockSearch") < choose_source.index(
        "load(item.name, { resolvedStock: item })"
    )
    assert "const resolvedCandidate = options.resolvedStock;" in load_source
    assert "candidateMatches ? resolvedCandidate : await resolveStock(normalized)" in load_source
    assert "state.responseCache.delete(dashboardUrl);" in load_source
    assert "scheduleStockDashboardWarmRefresh(stock);" in load_source
    assert submit_source.index("collapseStockSearch") < submit_source.index("load(query)")


def test_company_analysis_sections_settle_independently_and_retry_only_errors():
    source = _dashboard_source()
    company_source = _function_source(source, "loadStockCompanyAnalysis", "stockFlowGroupedRows")

    assert "Promise.allSettled" not in company_source
    assert 'includes(state.stockFinancialLinesStatus)' in company_source
    assert 'includes(state.stockSectorMarginsStatus)' in company_source
    assert 'includes(state.stockSgaAnalysisStatus)' in company_source
    assert company_source.count("renderStockCompanyAnalysis(data);") >= 4


def test_first_home_entry_reuses_five_item_snapshot_without_forcing_ranking_rebuild():
    source = _dashboard_source()

    assert 'function pageEntryRefreshOptions(view, key = "", options = {})' in source
    assert "const firstEntry = lastRefreshAt === 0;" in source
    assert "options.forceOnFirst !== false" in source
    assert 'pageEntryRefreshOptions("market", "home", { forceOnFirst: false })' in source
    assert "limit: 5" in _function_source(source, "loadHomeSurgeRankings", "currentMarketFilter")


def test_retryable_complete_snapshot_gaps_never_blank_last_rendered_home_data():
    source = _dashboard_source()
    home_details = _function_source(source, "loadStockHomeDetails", "formatMultiple")
    home_rankings = _function_source(source, "loadHomeSurgeRankings", "currentMarketFilter")
    home_indices = _function_source(source, "loadHomeMarketIndices", "stopHomeMarketIndexRefresh")
    sector_moves = _function_source(source, "loadUsSectorMoves", "clearUsSectorRefreshTimer")

    assert "error?.status === 503" in home_details
    retry_branch = home_details[home_details.index("error?.status === 503") :]
    assert retry_branch.index("else {") < retry_branch.index("loadStockHomeDetailsLegacy")
    assert '!elements.homeSurgeList.querySelector(".home-surge-row")' in home_rankings
    assert "incomingByCode.get(code) || previousByCode.get(code)" in home_indices
    assert "mergedItems.length !== expectedCodes.size" in home_indices
    assert "return state.usSectorMoves || null;" in sector_moves


def test_public_home_and_stock_load_in_parallel_with_identity_sync():
    source = _dashboard_source()
    initialize_source = source[source.index("async function initializeDashboard()") : source.index("void initializeDashboard();")]

    assert 'state.view === "home" || state.view === "stock"' in initialize_source
    assert "const identityPromise = initializeWatchlistIdentity();" in initialize_source
    assert "deferIdentityData: true" in initialize_source
    assert "await Promise.all([" in initialize_source
    assert initialize_source.index("const identityPromise") < initialize_source.index('setView("stock"')
    assert "await identityPromise;" in initialize_source
    assert "delay(LOGIN_SPLASH_DURATION_MS)" not in _function_source(
        source,
        "initializeWatchlistIdentity",
        "isWatched",
    )


def test_personal_home_ai_waits_for_identity_and_refreshes_before_gate_hides():
    source = _dashboard_source()
    home_branch = source[source.index('} else if (view === "home") {') : source.index('} else if (view === "search") {')]
    identity_source = _function_source(source, "initializeWatchlistIdentity", "isWatched")

    assert "options.deferIdentityData !== true" in home_branch
    assert identity_source.index("refreshHomeAiSignalsAfterLogin();") < identity_source.index("hideLoginGate();")


def test_identity_switch_invalidates_old_home_ai_before_the_gate_hides():
    source = _dashboard_source()
    refresh_source = _function_source(
        source,
        "refreshHomeAiSignalsAfterLogin",
        "resetHomeAiSignalsForIdentity",
    )
    reset_source = _function_source(
        source,
        "resetHomeAiSignalsForIdentity",
        "stopHomeMarketSignalTicker",
    )
    logout_source = _function_source(source, "logoutWatchlistIdentity", "initializeWatchlistIdentity")

    assert refresh_source.index("resetHomeAiSignalsForIdentity();") < refresh_source.index("loadHomeAiSignals(")
    assert "state.homeAiSignalsRequestId += 1;" in reset_source
    assert "state.aiSignalItems = [];" in reset_source
    assert 'state.aiSignalMarketStatus = "loading";' in reset_source
    assert "closeAiSignalQuoteStreams();" in reset_source
    assert "renderPendingHomeAiSignals();" in reset_source
    assert "resetHomeAiSignalsForIdentity();" in logout_source


def test_stable_dashboard_builder_never_calls_external_providers(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    db.add(StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True))
    db.commit()
    statements = []

    def record_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)

    def external_call(*_args, **_kwargs):
        raise AssertionError("stable dashboard requested an external provider")

    monkeypatch.setattr(stock_dashboard, "_naver_snapshot", external_call)
    monkeypatch.setattr(stock_dashboard, "fetch_company_detail_fields", external_call)
    monkeypatch.setattr(stock_dashboard, "_naver_item_news", external_call)
    try:
        payload = stock_dashboard.build_stock_dashboard(
            db,
            "005930",
            allow_external=False,
        )
        assert payload is not None
        assert payload["code"] == "005930"
        assert set(payload) >= {
            "quote",
            "revisions",
            "surprise",
            "guidance",
            "momentum",
            "chart_analysis",
            "flows",
            "valuation",
            "financial_series",
            "sentiment",
            "coverage",
        }
        assert not any("FROM news_item" in statement for statement in statements)
        assert sum("FROM disclosure_item" in statement for statement in statements) == 1
        assert payload["sentiment"] == {
            "score": None,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "latest_items": [],
        }
        assert payload["coverage"]["news"] is False
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)
        db.close()


def test_complete_dashboard_refresh_respects_company_profile_freshness(monkeypatch):
    stock = StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True)
    profile_calls = []

    monkeypatch.setattr(main_module, "_resolve_stock_master", lambda _db, _code: stock)
    monkeypatch.setattr(
        main_module,
        "ensure_company_profile",
        lambda _db, _stock, **kwargs: profile_calls.append(kwargs),
    )
    monkeypatch.setattr(main_module, "_ensure_stock_research_backfill", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(main_module, "ensure_stock_price_history", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(
        main_module,
        "build_stock_dashboard",
        lambda *_args, **_kwargs: {"as_of": None},
    )

    built = main_module._build_stock_dashboard_snapshot(
        object(),
        main_module._stock_dashboard_snapshot_key("005930"),
    )

    assert built.payload == {"as_of": None}
    assert profile_calls == [{"refresh": False, "include_business_report": False}]


def test_web_role_cold_stable_dashboard_serves_db_only_and_queues_complete_refresh(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        db.add(StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True))
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    def external_call(*_args, **_kwargs):
        raise AssertionError("cold stable endpoint requested an external provider")

    build_calls = []

    def db_only_builder(db, code, *args, **kwargs):
        build_calls.append(kwargs.copy())
        return stock_dashboard.build_stock_dashboard(db, code, *args, **kwargs)

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module.settings, "process_role", "web")
    monkeypatch.setattr(main_module, "complete_snapshot_runtime", None)
    monkeypatch.setattr(main_module, "build_stock_dashboard", db_only_builder)
    monkeypatch.setattr(main_module, "publish_complete_snapshot", external_call)
    monkeypatch.setattr(main_module, "_ensure_stock_research_backfill", external_call)
    monkeypatch.setattr(main_module, "ensure_company_profile", external_call)
    monkeypatch.setattr(main_module, "ensure_stock_price_history", external_call)
    monkeypatch.setattr(main_module, "_ensure_stock_master_from_naver", external_call)
    monkeypatch.setattr(main_module, "_enrich_cached_live_quote", external_call)
    monkeypatch.setattr(main_module, "_enrich_uncached_kis_quote", external_call)
    monkeypatch.setattr(stock_dashboard, "_naver_snapshot", external_call)
    monkeypatch.setattr(stock_dashboard, "fetch_company_detail_fields", external_call)
    monkeypatch.setattr(stock_dashboard, "_naver_item_news", external_call)
    try:
        response = TestClient(app).get(
            "/stocks/005930/dashboard?include_profile=0&include_live=0"
        )
        assert response.status_code == 200
        assert response.json()["code"] == "005930"
        assert response.json()["source"] == "stored_database_warming"
        assert response.headers["Cache-Control"] == "no-store"
        assert build_calls == [{"allow_external": False}]
        assert set(response.json()) >= {
            "quote",
            "revisions",
            "surprise",
            "guidance",
            "momentum",
            "chart_analysis",
            "flows",
            "valuation",
            "financial_series",
            "sentiment",
            "coverage",
        }
        with factory() as db:
            queued = db.get(
                CompletePayloadSnapshot,
                main_module._stock_dashboard_snapshot_key("005930"),
            )
            assert queued is not None
            assert queued.payload is None
            assert queued.refresh_requested_at is not None
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_default_live_dashboard_cold_path_keeps_existing_enrichment_flow(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        db.add(StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True))
        db.commit()
        payload = stock_dashboard.build_stock_dashboard(db, "005930", allow_external=False)

    def override_db():
        with factory() as db:
            yield db

    calls = []

    def enriched_builder(_db, code, *args, **kwargs):
        calls.append(("build", code, kwargs.copy()))
        return payload

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "build_stock_dashboard", enriched_builder)
    monkeypatch.setattr(
        main_module,
        "ensure_company_profile",
        lambda *_args, **_kwargs: calls.append(("profile",)),
    )
    monkeypatch.setattr(
        main_module,
        "_ensure_stock_research_backfill",
        lambda *_args, **_kwargs: calls.append(("research",)),
    )
    monkeypatch.setattr(
        main_module,
        "_enrich_cached_live_quote",
        lambda *_args, **_kwargs: calls.append(("live",)) or True,
    )
    monkeypatch.setattr(
        main_module,
        "_enrich_pre_market_quote",
        lambda *_args, **_kwargs: calls.append(("pre_market",)),
    )
    try:
        response = TestClient(app).get("/stocks/005930/dashboard")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
        assert ("profile",) in calls
        assert ("research",) in calls
        assert ("build", "005930", {"allow_external": True}) in calls
        assert ("live",) in calls
        assert ("pre_market",) in calls
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_seeded_stable_dashboard_endpoint_never_calls_external_providers(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        db.add(StockMaster(code="005930", name="삼성전자", market="KOSPI", is_active=True))
        db.commit()
        payload = stock_dashboard.build_stock_dashboard(db, "005930", allow_external=False)
        publish(
            db,
            main_module._stock_dashboard_snapshot_key("005930"),
            payload,
            fresh_for_seconds=120,
            validator=main_module._validate_stock_dashboard_snapshot,
        )

    def override_db():
        with factory() as db:
            yield db

    def external_call(*_args, **_kwargs):
        raise AssertionError("stable endpoint requested an external provider")

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "build_stock_dashboard", external_call)
    monkeypatch.setattr(main_module, "_ensure_stock_research_backfill", external_call)
    monkeypatch.setattr(main_module, "ensure_company_profile", external_call)
    monkeypatch.setattr(main_module, "_ensure_stock_master_from_naver", external_call)
    try:
        response = TestClient(app).get(
            "/stocks/005930/dashboard?include_profile=0&include_live=0"
        )
        assert response.status_code == 200
        assert response.json()["code"] == "005930"
        assert set(response.json()) == set(payload) | {"source"}
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
