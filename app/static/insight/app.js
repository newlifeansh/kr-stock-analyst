const SECTION_CONFIG = {
  company_brief: {
    label: "종목브리핑",
    defaultCategory: "all",
    categories: [
      ["all", "전체"],
      ["reports", "리포트 포함"],
      ["disclosures", "공시 포함"],
      ["news", "뉴스 포함"],
    ],
  },
  portfolio: {
    label: "토스증권",
    defaultCategory: "holdings",
    categories: [
      ["holdings", "보유종목"],
      ["orders", "주문내역"],
      ["accounts", "계좌요약"],
    ],
  },
  research: {
    label: "증권사리포트",
    defaultCategory: "company",
    categories: [
      ["all", "전체"],
      ["company", "종목분석"],
      ["industry", "산업분석"],
      ["market", "시황전략"],
      ["economy", "경제분석"],
      ["invest", "투자정보"],
      ["debenture", "채권분석"],
    ],
  },
  disclosure: {
    label: "공시·IR",
    defaultCategory: "all",
    categories: [
      ["all", "전체"],
      ["filings", "공시목록"],
      ["earnings_flash", "실적속보"],
      ["ir", "기업설명회"],
      ["insider_trade", "내부자거래"],
      ["major_holder", "대량보유자거래"],
      ["dividend", "배당"],
      ["treasury_stock", "자사주"],
      ["supply_contract", "공급계약"],
      ["facility_investment", "시설투자"],
      ["rights_offering", "유상증자"],
      ["business_report", "사업보고서"],
    ],
  },
  news: {
    label: "뉴스",
    defaultCategory: "all",
    categories: [
      ["all", "전체"],
      ["breaking", "실시간속보"],
      ["market", "시황"],
      ["company", "기업·종목"],
      ["global", "해외증시"],
      ["bond", "채권·선물"],
      ["disclosure_memo", "공시메모"],
      ["fx", "환율"],
    ],
  },
};

const ARCHIVED_SECTIONS = new Set(["portfolio"]);
const DEFAULT_SECTION = "company_brief";

const state = {
  section: DEFAULT_SECTION,
  category: SECTION_CONFIG.company_brief.defaultCategory,
  companyBriefGroup: "all",
  keyword: "",
  startDate: "",
  endDate: "",
  auxOne: "all",
  auxTwo: "all",
  detail: null,
};

const AUTO_REFRESH_MS = 60 * 1000;
const WATCH_CODES_STORAGE_KEY = "insight.watchCodes";

const store = {
  briefing: null,
  runtime: null,
  companyBriefs: [],
  briefingQuotes: [],
  researchReports: [],
  disclosures: [],
  newsItems: [],
  tossStatus: null,
  tossAccounts: [],
  tossHoldings: [],
  tossOrders: [],
  watchCodes: [],
  userWatchCodes: [],
  latestPrices: {},
  priceHistory: {},
  priceHistoryStatus: {},
};

let loadPromise = null;
let autoRefreshHandle = null;
let overlayObserver = null;

function fallbackSection() {
  return ARCHIVED_SECTIONS.has(DEFAULT_SECTION) ? "company_brief" : DEFAULT_SECTION;
}

function visibleSectionEntries() {
  return Object.entries(SECTION_CONFIG).filter(([sectionKey]) => !ARCHIVED_SECTIONS.has(sectionKey));
}

function normalizeSection(sectionKey) {
  if (!sectionKey || ARCHIVED_SECTIONS.has(sectionKey) || !SECTION_CONFIG[sectionKey]) {
    return fallbackSection();
  }
  return sectionKey;
}

const elements = {
  body: document.body,
  sidebarStatus: document.getElementById("sidebar-status"),
  sectionTitle: document.getElementById("section-title"),
  sectionMeta: document.getElementById("section-meta"),
  primarySectionTabs: document.getElementById("primary-section-tabs"),
  secondarySectionTabs: document.getElementById("secondary-section-tabs"),
  filters: document.querySelector(".filters"),
  viewModeIndicator: document.getElementById("view-mode-indicator"),
  sidebarViewMode: document.getElementById("sidebar-view-mode"),
  categorySelect: document.getElementById("category-select"),
  auxOne: document.getElementById("aux-select-one"),
  auxTwo: document.getElementById("aux-select-two"),
  keywordInput: document.getElementById("keyword-input"),
  startDate: document.getElementById("start-date"),
  endDate: document.getElementById("end-date"),
  desktopBoard: document.getElementById("desktop-board"),
  mobileBoard: document.getElementById("mobile-board"),
  refreshButton: document.getElementById("refresh-button"),
  resetFilters: document.getElementById("reset-filters"),
  portfolioSubnav: document.getElementById("portfolio-subnav"),
  disclosureSubnav: document.getElementById("disclosure-subnav"),
  newsSubnav: document.getElementById("news-subnav"),
};

function detectViewMode() {
  const path = window.location.pathname;
  const params = new URLSearchParams(window.location.search);
  const requestedSection = params.get("section");
  const requestedCategory = params.get("category");
  const requestedGroup = params.get("group");
  const requestedView = params.get("view");
  const normalizedRequestedSection = normalizeSection(requestedSection);
  const sectionConfig = requestedSection ? SECTION_CONFIG[normalizedRequestedSection] : null;

  if (sectionConfig) {
    state.section = normalizedRequestedSection;
    state.category = sectionConfig.defaultCategory;
  } else if (path === "/insight") {
    state.section = "company_brief";
    state.category = SECTION_CONFIG.company_brief.defaultCategory;
  } else {
    state.section = normalizeSection(state.section);
    state.category = SECTION_CONFIG[state.section].defaultCategory;
  }

  if (sectionConfig && requestedCategory) {
    const allowedCategories = new Set(sectionConfig.categories.map(([value]) => value));
    if (allowedCategories.has(requestedCategory)) {
      state.category = requestedCategory;
    }
  }

  if (requestedGroup && ["all", "holdings", "watchlist"].includes(requestedGroup)) {
    state.companyBriefGroup = requestedGroup;
  }

  elements.body.classList.remove("force-mobile", "force-desktop");
  if (requestedView === "mobile") {
    elements.body.classList.add("force-mobile");
  } else if (requestedView === "desktop") {
    elements.body.classList.add("force-desktop");
  }
}

function currentResponsiveMode() {
  if (elements.body.classList.contains("force-mobile")) {
    return "모바일";
  }
  if (elements.body.classList.contains("force-desktop")) {
    return "PC";
  }
  return window.matchMedia("(max-width: 860px)").matches ? "모바일" : "PC";
}

function renderResponsiveIndicators() {
  const label = `자동 감지 · ${currentResponsiveMode()}`;
  if (elements.viewModeIndicator) {
    elements.viewModeIndicator.textContent = label;
  }
  if (elements.sidebarViewMode) {
    elements.sidebarViewMode.textContent = label;
  }
}

function disableBrowserCommentOverlay() {
  const overlay = document.getElementById("codex-browser-sidebar-comments-root");
  if (!(overlay instanceof HTMLElement)) {
    return;
  }
  overlay.style.pointerEvents = "none";
  overlay.style.background = "transparent";
}

function watchBrowserCommentOverlay() {
  disableBrowserCommentOverlay();
  if (overlayObserver || !document.body) {
    return;
  }
  overlayObserver = new MutationObserver(() => {
    disableBrowserCommentOverlay();
  });
  overlayObserver.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["style", "class"],
  });
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value).replace("T", " ").slice(0, 16);
  }
  return date.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDateOnly(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value).slice(0, 10).replaceAll("-", ". ");
  }
  return date.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return Number(value).toLocaleString("ko-KR");
}

function normalizeStockCode(value) {
  const text = String(value ?? "").trim().toUpperCase();
  if (!text) {
    return "";
  }
  const match = text.match(/(\d{6})$/);
  if (match) {
    return match[1];
  }
  return text;
}

function uniqueStockCodes(values) {
  return [...new Set((values || []).map((value) => normalizeStockCode(value)).filter(Boolean))].sort();
}

function readStoredWatchCodes() {
  try {
    const raw = window.localStorage.getItem(WATCH_CODES_STORAGE_KEY);
    if (raw === null) {
      return null;
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? uniqueStockCodes(parsed) : [];
  } catch {
    return null;
  }
}

function saveStoredWatchCodes(codes) {
  try {
    window.localStorage.setItem(WATCH_CODES_STORAGE_KEY, JSON.stringify(uniqueStockCodes(codes)));
  } catch {
    // localStorage can be unavailable in restricted browser contexts.
  }
}

function initializeUserWatchCodes(seedCodes) {
  const storedCodes = readStoredWatchCodes();
  if (storedCodes === null) {
    store.userWatchCodes = uniqueStockCodes(seedCodes);
    saveStoredWatchCodes(store.userWatchCodes);
    return;
  }
  store.userWatchCodes = storedCodes;
}

function toggleUserWatchCode(stockCode) {
  const normalized = normalizeStockCode(stockCode);
  if (!normalized) {
    return;
  }
  const codes = new Set(uniqueStockCodes(store.userWatchCodes));
  if (codes.has(normalized)) {
    codes.delete(normalized);
  } else {
    codes.add(normalized);
  }
  store.userWatchCodes = [...codes].sort();
  saveStoredWatchCodes(store.userWatchCodes);
  renderAll();
}

function formatPercent(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${Number(value).toFixed(1)}%`;
}

function formatRatioPercent(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function toneClass(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return "neutral";
  }
  if (numeric > 0) {
    return "positive";
  }
  if (numeric < 0) {
    return "negative";
  }
  return "neutral";
}

function formatWon(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${Number(value).toLocaleString("ko-KR")}원`;
}

function formatDollar(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) {
    return "-";
  }
  return `$${Number(value).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function formatMoneyByCurrency(value, currency) {
  if (currency === "USD") {
    return formatDollar(value);
  }
  return formatWon(value);
}

function formatTossAccountMoney(krwValue, usdValue) {
  if (krwValue !== null && krwValue !== undefined && krwValue !== "") {
    return formatWon(krwValue);
  }
  if (usdValue !== null && usdValue !== undefined && usdValue !== "") {
    return formatDollar(usdValue);
  }
  return "-";
}

function latestPortfolioSync() {
  return (
    store.tossAccounts.map((item) => item.synced_at).filter(Boolean).sort().at(-1) ||
    store.tossHoldings.map((item) => item.synced_at).filter(Boolean).sort().at(-1) ||
    store.tossOrders.map((item) => item.synced_at).filter(Boolean).sort().at(-1) ||
    null
  );
}

function cadenceLabel(seconds) {
  const numeric = Number(seconds);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "-";
  }
  if (numeric < 60) {
    return `${numeric}초`;
  }
  if (numeric % 3600 === 0) {
    return `${numeric / 3600}시간`;
  }
  return `${Math.round(numeric / 60)}분`;
}

function insightCadenceSummary() {
  const runtime = store.runtime;
  if (!runtime) {
    return "";
  }
  const parts = [];
  if (!ARCHIVED_SECTIONS.has("portfolio") && runtime.toss_enabled && runtime.toss_sync_holdings_enabled) {
    parts.push(`보유 ${cadenceLabel(runtime.toss_poll_seconds)}`);
  }
  if (runtime.research_enabled) {
    parts.push(`리포트 ${cadenceLabel(runtime.research_poll_seconds)}`);
  }
  if (runtime.disclosure_enabled) {
    parts.push(`공시 ${cadenceLabel(runtime.disclosure_poll_seconds)}`);
  }
  if (runtime.news_enabled) {
    parts.push(`뉴스 ${cadenceLabel(runtime.news_poll_seconds)}`);
  }
  if (runtime.price_enabled) {
    parts.push(`시세 ${cadenceLabel(runtime.price_poll_seconds)}`);
  }
  return parts.join(" · ");
}

function primaryAccount() {
  return store.tossAccounts[0] || null;
}

function priceInfo(stockCode) {
  if (!stockCode) {
    return null;
  }
  return store.latestPrices[stockCode] || null;
}

function briefingQuoteInfo(stockCode) {
  const normalized = normalizeStockCode(stockCode);
  if (!normalized) {
    return null;
  }
  return store.briefingQuotes.find((item) => normalizeStockCode(item.code) === normalized) || null;
}

function holdingCodeSet() {
  return new Set(store.tossHoldings.map((item) => normalizeStockCode(item.symbol)).filter(Boolean));
}

function watchCodeSet() {
  return new Set(uniqueStockCodes(store.userWatchCodes));
}

function companyBriefMembership(item) {
  const code = normalizeStockCode(item.stock_code);
  const holdings = holdingCodeSet();
  const watchlist = watchCodeSet();
  return {
    holding: Boolean(code) && holdings.has(code),
    watchlist: Boolean(code) && watchlist.has(code),
  };
}

function companyBriefGroupOptions() {
  const holdings = holdingCodeSet();
  const watchlist = watchCodeSet();
  const holdingCount = store.companyBriefs.filter((item) => holdings.has(normalizeStockCode(item.stock_code))).length;
  const watchlistCount = store.companyBriefs.filter((item) => watchlist.has(normalizeStockCode(item.stock_code))).length;

  return [
    ["all", "전체", store.companyBriefs.length],
    ["holdings", "보유", holdingCount],
    ["watchlist", "관심", watchlistCount],
  ];
}

function companyBriefPriceView(item) {
  const quote = briefingQuoteInfo(item.stock_code);
  if (quote && quote.price !== null && quote.price !== undefined && quote.price !== "") {
    return {
      label: "최근시세",
      value: quote.price,
      asOf: store.briefing?.as_of ? formatDateTime(store.briefing.as_of) : "-",
    };
  }
  return {
    label: "종가",
    value: item.latest_close,
    asOf: formatDateOnly(item.latest_trade_date),
  };
}

function impliedReturn(targetPrice, stockCode) {
  const latest = priceInfo(stockCode);
  const currentPrice = latest?.close;
  if (!targetPrice || !currentPrice) {
    return null;
  }
  return ((Number(targetPrice) / Number(currentPrice)) - 1) * 100;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function currentSectionItems() {
  if (state.section === "company_brief") {
    return store.companyBriefs;
  }
  if (state.section === "portfolio") {
    if (state.category === "accounts") {
      return store.tossAccounts;
    }
    if (state.category === "orders") {
      return store.tossOrders;
    }
    return store.tossHoldings;
  }
  if (state.section === "research") {
    return store.researchReports;
  }
  if (state.section === "disclosure") {
    return store.disclosures;
  }
  return store.newsItems;
}

function matchesDateRange(value) {
  if (!value) {
    return true;
  }
  const itemDate = new Date(value);
  if (Number.isNaN(itemDate.getTime())) {
    return true;
  }
  if (state.startDate) {
    const start = new Date(`${state.startDate}T00:00:00`);
    if (itemDate < start) {
      return false;
    }
  }
  if (state.endDate) {
    const end = new Date(`${state.endDate}T23:59:59`);
    if (itemDate > end) {
      return false;
    }
  }
  return true;
}

function filteredItems() {
  const keyword = state.keyword.trim().toLowerCase();
  return currentSectionItems().filter((item) => {
    if (state.section === "company_brief") {
      const membership = companyBriefMembership(item);
      const haystack = [
        item.company_name,
        item.stock_code,
        item.market,
        item.latest_report_title,
        item.latest_disclosure_title,
        item.latest_news_title,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return (
        (state.companyBriefGroup === "all" ||
          (state.companyBriefGroup === "holdings" && membership.holding) ||
          (state.companyBriefGroup === "watchlist" && membership.watchlist)) &&
        (state.category === "all" ||
          (state.category === "reports" && item.report_count > 0) ||
          (state.category === "disclosures" && item.disclosure_count > 0) ||
          (state.category === "news" && item.news_count > 0)) &&
        (!keyword || haystack.includes(keyword)) &&
        matchesDateRange(item.latest_published_at) &&
        (state.auxOne === "all" || item.market === state.auxOne)
      );
    }

    if (state.section === "portfolio") {
      if (state.category === "accounts") {
        const haystack = [item.account_no, item.account_type, item.broker_name].filter(Boolean).join(" ").toLowerCase();
        return (
          (!keyword || haystack.includes(keyword)) &&
          matchesDateRange(item.synced_at) &&
          (state.auxOne === "all" || item.account_type === state.auxOne)
        );
      }

      if (state.category === "orders") {
        const haystack = [item.symbol, item.status, item.side, item.order_type, item.currency]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return (
          (!keyword || haystack.includes(keyword)) &&
          matchesDateRange(item.ordered_at || item.synced_at) &&
          (state.auxOne === "all" || item.status === state.auxOne) &&
          (state.auxTwo === "all" || item.side === state.auxTwo)
        );
      }

      const haystack = [item.name, item.symbol, item.currency, item.market_country].filter(Boolean).join(" ").toLowerCase();
      return (
        (!keyword || haystack.includes(keyword)) &&
        matchesDateRange(item.synced_at) &&
        (state.auxOne === "all" || item.currency === state.auxOne) &&
        (state.auxTwo === "all" || item.market_country === state.auxTwo)
      );
    }

    if (state.section === "research") {
      const haystack = [item.company_name, item.subject_name, item.title, item.broker_name, item.opinion]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return (
        (state.category === "all" || item.source_category === state.category) &&
        (!keyword || haystack.includes(keyword)) &&
        matchesDateRange(item.published_at) &&
        (state.auxOne === "all" || item.broker_name === state.auxOne) &&
        (state.auxTwo === "all" || item.opinion === state.auxTwo)
      );
    }

    if (state.section === "disclosure") {
      const haystack = [item.company_name, item.report_name, item.filer_name, item.remark]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return (
        (state.category === "all" || item.disclosure_category === state.category) &&
        (!keyword || haystack.includes(keyword)) &&
        matchesDateRange(item.published_at) &&
        (state.auxOne === "all" || item.filer_name === state.auxOne) &&
        (state.auxTwo === "all" || item.corp_class === state.auxTwo)
      );
    }

    const haystack = [item.title, item.summary, item.press_name].filter(Boolean).join(" ").toLowerCase();
    return (
      (state.category === "all" || item.source_category === state.category) &&
      (!keyword || haystack.includes(keyword)) &&
      matchesDateRange(item.published_at) &&
      (state.auxOne === "all" || item.press_name === state.auxOne)
    );
  });
}

function optionMarkup(value, label, selectedValue) {
  const selected = value === selectedValue ? "selected" : "";
  return `<option value="${escapeHtml(value)}" ${selected}>${escapeHtml(label)}</option>`;
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), "ko"));
}

function renderSidebar() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button.dataset.section === state.section;
    button.classList.toggle("active", active);
  });

  const disclosureItems = SECTION_CONFIG.disclosure.categories
    .map(
      ([value, label]) =>
        `<button class="subnav-item ${state.section === "disclosure" && state.category === value ? "active" : ""}" data-section="disclosure" data-category="${escapeHtml(value)}">${escapeHtml(label)}</button>`
    )
    .join("");
  const newsItems = SECTION_CONFIG.news.categories
    .map(
      ([value, label]) =>
        `<button class="subnav-item ${state.section === "news" && state.category === value ? "active" : ""}" data-section="news" data-category="${escapeHtml(value)}">${escapeHtml(label)}</button>`
    )
    .join("");
  const portfolioItems = SECTION_CONFIG.portfolio.categories
    .map(
      ([value, label]) =>
        `<button class="subnav-item ${state.section === "portfolio" && state.category === value ? "active" : ""}" data-section="portfolio" data-category="${escapeHtml(value)}">${escapeHtml(label)}</button>`
    )
    .join("");
  if (elements.portfolioSubnav) {
    elements.portfolioSubnav.innerHTML = ARCHIVED_SECTIONS.has("portfolio") ? "" : portfolioItems;
  }
  if (elements.disclosureSubnav) {
    elements.disclosureSubnav.innerHTML = disclosureItems;
  }
  if (elements.newsSubnav) {
    elements.newsSubnav.innerHTML = newsItems;
  }
}

function renderFilters() {
  const config = SECTION_CONFIG[state.section];
  elements.sectionTitle.textContent = config.label;
  if (elements.filters) {
    elements.filters.hidden = state.section === "company_brief";
  }

  if (elements.primarySectionTabs) {
    elements.primarySectionTabs.innerHTML = "";
  }

  if (state.section === "company_brief") {
    elements.secondarySectionTabs.innerHTML = companyBriefGroupOptions()
      .map(
        ([value, label, count]) => `
          <button
            class="secondary-section-tab ${state.companyBriefGroup === value ? "active" : ""}"
            data-company-group="${escapeHtml(value)}"
            type="button"
          >
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(String(count))}</strong>
          </button>
        `
      )
      .join("");
  } else {
    elements.secondarySectionTabs.innerHTML = "";
  }

  elements.categorySelect.innerHTML = config.categories
    .map(([value, label]) => optionMarkup(value, label, state.category))
    .join("");

  if (state.section === "company_brief") {
    const marketOptions = ["all", ...uniqueSorted(store.companyBriefs.map((item) => item.market))];
    elements.auxOne.disabled = false;
    elements.auxTwo.disabled = true;
    elements.auxOne.innerHTML = marketOptions
      .map((value) => optionMarkup(value, value === "all" ? "시장" : value, state.auxOne))
      .join("");
    elements.auxTwo.innerHTML = optionMarkup("all", "추가필터", "all");
  } else if (state.section === "research") {
    const brokerOptions = ["all", ...uniqueSorted(store.researchReports.map((item) => item.broker_name))];
    const opinionOptions = ["all", ...uniqueSorted(store.researchReports.map((item) => item.opinion))];
    elements.auxOne.disabled = false;
    elements.auxTwo.disabled = false;
    elements.auxOne.innerHTML = brokerOptions
      .map((value) => optionMarkup(value, value === "all" ? "증권사" : value, state.auxOne))
      .join("");
    elements.auxTwo.innerHTML = opinionOptions
      .map((value) => optionMarkup(value, value === "all" ? "투자의견" : value, state.auxTwo))
      .join("");
  } else if (state.section === "disclosure") {
    const filerOptions = ["all", ...uniqueSorted(store.disclosures.map((item) => item.filer_name))];
    const corpClassOptions = ["all", ...uniqueSorted(store.disclosures.map((item) => item.corp_class))];
    elements.auxOne.disabled = false;
    elements.auxTwo.disabled = false;
    elements.auxOne.innerHTML = filerOptions
      .map((value) => optionMarkup(value, value === "all" ? "제출자" : value, state.auxOne))
      .join("");
    elements.auxTwo.innerHTML = corpClassOptions
      .map((value) => optionMarkup(value, value === "all" ? "시장구분" : value, state.auxTwo))
      .join("");
  } else if (state.section === "portfolio") {
    if (state.category === "holdings") {
      const currencyOptions = ["all", ...uniqueSorted(store.tossHoldings.map((item) => item.currency))];
      const marketOptions = ["all", ...uniqueSorted(store.tossHoldings.map((item) => item.market_country))];
      elements.auxOne.disabled = false;
      elements.auxTwo.disabled = false;
      elements.auxOne.innerHTML = currencyOptions
        .map((value) => optionMarkup(value, value === "all" ? "통화" : value, state.auxOne))
        .join("");
      elements.auxTwo.innerHTML = marketOptions
        .map((value) => optionMarkup(value, value === "all" ? "시장" : value, state.auxTwo))
        .join("");
    } else if (state.category === "orders") {
      const statusOptions = ["all", ...uniqueSorted(store.tossOrders.map((item) => item.status))];
      const sideOptions = ["all", ...uniqueSorted(store.tossOrders.map((item) => item.side))];
      elements.auxOne.disabled = false;
      elements.auxTwo.disabled = false;
      elements.auxOne.innerHTML = statusOptions
        .map((value) => optionMarkup(value, value === "all" ? "주문상태" : value, state.auxOne))
        .join("");
      elements.auxTwo.innerHTML = sideOptions
        .map((value) => optionMarkup(value, value === "all" ? "매수/매도" : value, state.auxTwo))
        .join("");
    } else {
      const accountTypeOptions = ["all", ...uniqueSorted(store.tossAccounts.map((item) => item.account_type))];
      elements.auxOne.disabled = false;
      elements.auxTwo.disabled = true;
      elements.auxOne.innerHTML = accountTypeOptions
        .map((value) => optionMarkup(value, value === "all" ? "계좌유형" : value, state.auxOne))
        .join("");
      elements.auxTwo.innerHTML = optionMarkup("all", "추가필터", "all");
    }
  } else {
    const pressOptions = ["all", ...uniqueSorted(store.newsItems.map((item) => item.press_name))];
    elements.auxOne.disabled = false;
    elements.auxTwo.disabled = true;
    elements.auxOne.innerHTML = pressOptions
      .map((value) => optionMarkup(value, value === "all" ? "언론사" : value, state.auxOne))
      .join("");
    elements.auxTwo.innerHTML = optionMarkup("all", "추가필터", "all");
  }

  elements.keywordInput.value = state.keyword;
  elements.startDate.value = state.startDate;
  elements.endDate.value = state.endDate;
}

function renderMeta(count) {
  const runtime = store.runtime;
  const briefing = store.briefing;
  const disclosureFallback =
    runtime?.last_disclosure_source === "dart_web" && runtime?.last_disclosure_message
      ? " · 공시 web"
      : "";
  const tossRetryLabel = runtime?.next_toss_retry_at
    ? ` · 재시도 ${formatDateTime(runtime.next_toss_retry_at)}`
    : "";
  if (state.section === "portfolio") {
    elements.sectionMeta.textContent = `${count.toLocaleString("ko-KR")}건 · ${
      latestPortfolioSync() ? formatDateTime(latestPortfolioSync()) : "토스 동기화 대기"
    }`;
    elements.sidebarStatus.textContent = store.tossStatus?.configured
      ? `계좌 ${store.tossStatus.account_seq || "-"} 연결${tossRetryLabel}`
      : "토스 미설정";
  } else if (state.section === "company_brief") {
    elements.sectionMeta.textContent = `${count.toLocaleString("ko-KR")}종목 · ${
      briefing?.as_of ? formatDateTime(briefing.as_of) : "브리핑 없음"
    } · 자동갱신`;
    elements.sidebarStatus.textContent = insightCadenceSummary() || (
      runtime?.last_success_at ? `${formatDateTime(runtime.last_success_at)} 갱신${disclosureFallback}` : "수집 대기"
    );
  } else {
    elements.sectionMeta.textContent = `${count.toLocaleString("ko-KR")}건 · ${
      briefing?.as_of ? formatDateTime(briefing.as_of) : "브리핑 없음"
    }`;
    elements.sidebarStatus.textContent = runtime?.last_success_at
      ? `${formatDateTime(runtime.last_success_at)} 갱신${disclosureFallback}`
      : "수집 대기";
  }
}

function linkOrText(url, label) {
  if (!url) {
    return `<span>${escapeHtml(label)}</span>`;
  }
  return `<a class="text-link" href="${escapeHtml(url)}" rel="noreferrer">${escapeHtml(label)}</a>`;
}

function companyBriefStreamRow(label, count, title, url, meta) {
  const hasData = Boolean(count);
  return `
    <div class="company-brief-stream-row">
      <div class="company-brief-stream-side">
        <span class="company-brief-stream-label">${escapeHtml(label)}</span>
        <span class="company-brief-stream-count">${escapeHtml(`${count || 0}건`)}</span>
      </div>
      <div class="company-brief-stream-body">
        <div class="company-brief-stream-title">${hasData ? linkOrText(url, title || "-") : '<span class="muted">데이터 없음</span>'}</div>
        <div class="company-brief-stream-meta">${escapeHtml(hasData ? meta || "-" : "최근 연결 없음")}</div>
      </div>
    </div>
  `;
}

function companyBriefStat(label, value) {
  return `
    <div class="company-brief-stat">
      <label>${escapeHtml(label)}</label>
      <strong>${escapeHtml(String(value ?? "-"))}</strong>
    </div>
  `;
}

function companyBriefBadges(item) {
  const membership = companyBriefMembership(item);
  const badges = [];
  if (membership.holding) {
    badges.push('<span class="pill pill-dark">보유</span>');
  }
  if (membership.watchlist) {
    badges.push('<span class="pill pill-accent">관심</span>');
  }
  badges.push(`<span class="pill">${escapeHtml(item.market || "기업")}</span>`);
  return badges.join("");
}

function companyBriefPanelTitle() {
  if (state.companyBriefGroup === "holdings") {
    return "보유 기업";
  }
  if (state.companyBriefGroup === "watchlist") {
    return "관심 기업";
  }
  return "국내 전체기업";
}

function companyBriefSortLabel() {
  if (state.category === "reports") {
    return "리포트 신호 순";
  }
  if (state.category === "disclosures") {
    return "공시 신호 순";
  }
  if (state.category === "news") {
    return "뉴스 신호 순";
  }
  return "브리핑 신호 순";
}

function companyBriefSortedItems(items) {
  return [...items].sort((a, b) => {
    const signalDiff = Number(b.total_count || 0) - Number(a.total_count || 0);
    if (signalDiff !== 0) {
      return signalDiff;
    }
    return new Date(b.latest_published_at || 0).getTime() - new Date(a.latest_published_at || 0).getTime();
  });
}

function companyBriefMoveInfo(item) {
  const quote = briefingQuoteInfo(item.stock_code);
  const price = quote?.price ?? item.latest_close;
  const changeValue = quote?.change_value;
  const changeRate = quote?.change_rate;
  const hasMove = changeValue !== null && changeValue !== undefined && changeValue !== "";
  return {
    price,
    changeValue,
    changeRate,
    hasMove,
    tone: hasMove ? toneClass(changeValue) : "neutral",
    asOf: quote ? formatDateTime(store.briefing?.as_of) : formatDateOnly(item.latest_trade_date),
  };
}

function companyBriefLatestSignal(item) {
  const candidates = [
    {
      label: "리포트",
      count: item.report_count,
      title: item.latest_report_title,
      url: item.latest_report_url,
      meta: item.latest_report_broker,
      at: item.latest_report_at,
    },
    {
      label: "공시",
      count: item.disclosure_count,
      title: item.latest_disclosure_title,
      url: item.latest_disclosure_url,
      meta: labelForCategory("disclosure", item.latest_disclosure_category),
      at: item.latest_disclosure_at,
    },
    {
      label: "뉴스",
      count: item.news_count,
      title: item.latest_news_title,
      url: item.latest_news_url,
      meta: item.latest_news_press,
      at: item.latest_news_at,
    },
  ]
    .filter((entry) => entry.count && entry.title)
    .sort((a, b) => new Date(b.at || 0).getTime() - new Date(a.at || 0).getTime());

  return candidates[0] || null;
}

function companyBriefOverviewRow(item, index) {
  const move = companyBriefMoveInfo(item);
  const latest = companyBriefLatestSignal(item);
  const membership = companyBriefMembership(item);
  const stockCode = normalizeStockCode(item.stock_code);
  const watchLabel = membership.watchlist
    ? `${item.company_name} 관심 해제`
    : `${item.company_name} 관심 추가`;
  const watchControl = stockCode
    ? `<button
        class="company-brief-star ${membership.watchlist ? "active" : ""}"
        data-watch-code="${escapeHtml(stockCode)}"
        type="button"
        aria-pressed="${membership.watchlist ? "true" : "false"}"
        aria-label="${escapeHtml(watchLabel)}"
        title="${escapeHtml(watchLabel)}"
      >★</button>`
    : '<span class="company-brief-star is-disabled" aria-hidden="true">★</span>';
  const signalText = `리포트 ${formatNumber(item.report_count)} · 공시 ${formatNumber(item.disclosure_count)} · 뉴스 ${formatNumber(item.news_count)}`;
  const moveText = move.hasMove
    ? `${Number(move.changeValue) > 0 ? "+" : ""}${formatNumber(move.changeValue)}원 (${formatPercent(move.changeRate)})`
    : "최근 종가";

  return `
    <article class="company-brief-overview-row">
      <div class="company-brief-rank">${escapeHtml(String(index + 1))}</div>
      ${watchControl}
      <div class="company-brief-row-main">
        <div class="company-brief-row-title">
          <strong>${escapeHtml(item.company_name)}</strong>
          ${membership.holding ? '<span class="mini-badge">보유</span>' : ""}
          ${membership.watchlist ? '<span class="mini-badge accent">관심</span>' : ""}
        </div>
        <div class="company-brief-row-meta">
          <span>${escapeHtml(item.stock_code || "-")}</span>
          <span>${escapeHtml(item.market || "-")}</span>
          <span>${escapeHtml(signalText)}</span>
        </div>
        <div class="company-brief-row-signal">
          ${
            latest
              ? `<span>${escapeHtml(latest.label)}</span>${linkOrText(latest.url, latest.title)}`
              : '<span class="muted">연결된 최신 신호가 없습니다.</span>'
          }
        </div>
      </div>
      <div class="company-brief-row-price">
        <strong>${move.price ? formatNumber(move.price) : "-"}</strong>
        <span class="${escapeHtml(move.tone)}">${escapeHtml(moveText)}</span>
        <small>${escapeHtml(move.asOf || "-")}</small>
      </div>
    </article>
  `;
}

function companyBriefOverviewPanel(items) {
  const sortedItems = companyBriefSortedItems(items);
  return `
    <section class="company-brief-overview-panel">
      <div class="company-brief-overview-head">
        <div>
          <div class="company-brief-overview-title">
            <strong>${escapeHtml(companyBriefPanelTitle())}</strong>
            <span aria-hidden="true">⌄</span>
          </div>
          <div class="company-brief-overview-subtitle">
            <span>${escapeHtml(companyBriefSortLabel())}</span>
            <span>${escapeHtml(`${formatNumber(sortedItems.length)}개 기업`)}</span>
          </div>
        </div>
        <span class="company-brief-overview-more">자세히 보기</span>
      </div>
      <div class="company-brief-overview-list">
        ${sortedItems.map((item, index) => companyBriefOverviewRow(item, index)).join("")}
      </div>
    </section>
  `;
}

function findBriefByCode(stockCode) {
  const normalized = normalizeStockCode(stockCode);
  if (!normalized) {
    return null;
  }
  return store.companyBriefs.find((item) => normalizeStockCode(item.stock_code) === normalized) || null;
}

function findQuoteByCode(stockCode) {
  const normalized = normalizeStockCode(stockCode);
  if (!normalized) {
    return null;
  }
  return store.briefingQuotes.find((item) => normalizeStockCode(item.code) === normalized) || null;
}

function entityCompanyName(item) {
  return item.company_name || item.subject_name || item.name || "-";
}

function entityStockCode(item) {
  return normalizeStockCode(item.stock_code || item.code || item.symbol);
}

function overviewMoveInfo(item) {
  const code = entityStockCode(item);
  const brief = findBriefByCode(code);
  const quote = findQuoteByCode(code);
  const price = quote?.price ?? brief?.latest_close ?? null;
  const changeValue = quote?.change_value;
  const changeRate = quote?.change_rate;
  const hasMove = changeValue !== null && changeValue !== undefined && changeValue !== "";
  return {
    price,
    changeValue,
    changeRate,
    hasMove,
    tone: hasMove ? toneClass(changeValue) : "neutral",
  };
}

function overviewWatchButton(stockCode, companyName) {
  const code = normalizeStockCode(stockCode);
  if (!code) {
    return '<span class="overview-star is-disabled" aria-hidden="true">★</span>';
  }
  const active = watchCodeSet().has(code);
  const label = active ? `${companyName} 관심 해제` : `${companyName} 관심 추가`;
  return `
    <button
      class="overview-star ${active ? "active" : ""}"
      data-watch-code="${escapeHtml(code)}"
      type="button"
      aria-pressed="${active ? "true" : "false"}"
      aria-label="${escapeHtml(label)}"
      title="${escapeHtml(label)}"
    >★</button>
  `;
}

function overviewPriceBlock(item) {
  const move = overviewMoveInfo(item);
  const moveText = move.hasMove
    ? `${Number(move.changeValue) > 0 ? "+" : ""}${formatNumber(move.changeValue)}원 (${formatPercent(move.changeRate)})`
    : "시세 대기";
  return `
    <div class="overview-row-price">
      <strong>${move.price ? formatNumber(move.price) : "-"}</strong>
      <span class="${escapeHtml(move.tone)}">${escapeHtml(moveText)}</span>
    </div>
  `;
}

function reportById(reportId) {
  return store.researchReports.find((item) => String(item.id) === String(reportId)) || null;
}

function disclosureById(disclosureId) {
  return store.disclosures.find((item) => String(item.id) === String(disclosureId)) || null;
}

function newsById(newsId) {
  return store.newsItems.find((item) => String(item.id) === String(newsId)) || null;
}

function overviewReportRows(limit = 5) {
  return [...store.researchReports]
    .filter((item) => item.company_name || item.stock_code)
    .sort((a, b) => {
      const viewDiff = Number(b.views || 0) - Number(a.views || 0);
      if (viewDiff !== 0) {
        return viewDiff;
      }
      return new Date(b.published_at || 0).getTime() - new Date(a.published_at || 0).getTime();
    })
    .slice(0, limit);
}

function overviewDisclosureRows(limit = 5) {
  return [...store.disclosures]
    .sort((a, b) => new Date(b.published_at || 0).getTime() - new Date(a.published_at || 0).getTime())
    .slice(0, limit);
}

function overviewNewsRows(limit = 5) {
  const sorted = [...store.newsItems].sort(
    (a, b) => new Date(b.published_at || 0).getTime() - new Date(a.published_at || 0).getTime()
  );
  const matched = sorted.filter((item) => newsCompanyGuess(item));
  return (matched.length ? matched : sorted).slice(0, limit);
}

function overviewHoldingRows(limit = 5) {
  const holdings = holdingCodeSet();
  return companyBriefSortedItems(store.companyBriefs)
    .filter((item) => holdings.has(normalizeStockCode(item.stock_code)))
    .slice(0, limit);
}

function overviewReportRow(item) {
  const companyName = entityCompanyName(item);
  const broker = [item.broker_name, item.opinion].filter(Boolean).join(" · ") || "증권사 리포트";
  const target = item.target_price ? `${formatNumber(item.target_price)}원` : "-";
  return `
    <article class="overview-feed-row">
      ${overviewWatchButton(item.stock_code, companyName)}
      <button class="overview-row-button" data-report-detail="${escapeHtml(item.id)}" type="button">
        <div class="overview-row-company">
          <strong>${escapeHtml(companyName)}</strong>
          <span>${escapeHtml(item.stock_code || item.source_category || "-")}</span>
        </div>
        ${overviewPriceBlock(item)}
        <div class="overview-row-copy">
          <span>${escapeHtml(broker)} · 목표 ${escapeHtml(target)}</span>
          <strong>${escapeHtml(item.title || "-")}</strong>
        </div>
      </button>
    </article>
  `;
}

function overviewDisclosureRow(item) {
  const companyName = entityCompanyName(item);
  const category = labelForCategory("disclosure", item.disclosure_category);
  return `
    <article class="overview-feed-row">
      ${overviewWatchButton(item.stock_code, companyName)}
      <button
        class="overview-row-button"
        data-disclosure-drill="${escapeHtml(item.id)}"
        type="button"
      >
        <div class="overview-row-company">
          <strong>${escapeHtml(companyName)}</strong>
          <span>${escapeHtml(item.stock_code || item.corp_class || "-")}</span>
        </div>
        ${overviewPriceBlock(item)}
        <div class="overview-row-copy">
          <span>${escapeHtml(category)}</span>
          <strong>${escapeHtml(item.report_name || "-")}</strong>
        </div>
      </button>
    </article>
  `;
}

function overviewNewsRow(item) {
  const companyName = newsCompanyGuess(item);
  return `
    <article class="overview-feed-row">
      ${overviewWatchButton(companyName?.stock_code, companyName?.company_name || "뉴스")}
      <button
        class="overview-row-button"
        data-news-drill="${escapeHtml(item.id)}"
        type="button"
      >
        <div class="overview-row-company">
          <strong>${escapeHtml(companyName?.company_name || "뉴스")}</strong>
          <span>${escapeHtml(companyName?.stock_code || item.source_category || "-")}</span>
        </div>
        ${overviewPriceBlock(companyName || item)}
        <div class="overview-row-copy">
          <span>${escapeHtml(item.press_name || "뉴스")} · ${escapeHtml(formatDateTime(item.published_at))}</span>
          <strong>${escapeHtml(item.title || "-")}</strong>
        </div>
        ${item.image_url ? `<img class="overview-news-thumb" src="${escapeHtml(item.image_url)}" alt="" loading="lazy" />` : ""}
      </button>
    </article>
  `;
}

function newsCompanyGuess(newsItem) {
  const haystack = [newsItem.title, newsItem.summary].filter(Boolean).join(" ");
  return (
    store.companyBriefs.find((item) => item.company_name && haystack.includes(item.company_name)) ||
    store.companyBriefs.find((item) => item.stock_code && haystack.includes(item.stock_code)) ||
    null
  );
}

function overviewBriefRow(item) {
  const latest = companyBriefLatestSignal(item);
  return `
    <article class="overview-feed-row">
      ${overviewWatchButton(item.stock_code, item.company_name)}
      <button class="overview-row-button" data-company-drill="${escapeHtml(item.stock_code || item.company_name)}" type="button">
        <div class="overview-row-company">
          <strong>${escapeHtml(item.company_name)}</strong>
          <span>${escapeHtml(item.stock_code || item.market || "-")}</span>
        </div>
        ${overviewPriceBlock(item)}
        <div class="overview-row-copy">
          <span>${escapeHtml(latest?.label || "브리핑")} · 신호 ${escapeHtml(formatNumber(item.total_count))}건</span>
          <strong>${escapeHtml(latest?.title || "연결된 최신 신호가 없습니다.")}</strong>
        </div>
      </button>
    </article>
  `;
}

function overviewSection(title, count, target, rows, emptyText) {
  return `
    <section class="overview-section">
      <button class="overview-section-head" data-overview-target="${escapeHtml(target)}" type="button">
        <strong>${escapeHtml(title)}</strong>
        <span>전체 ${escapeHtml(formatNumber(count))}건</span>
        <span aria-hidden="true">›</span>
      </button>
      <div class="overview-feed-list">
        ${rows.length ? rows.join("") : `<div class="overview-empty">${escapeHtml(emptyText)}</div>`}
      </div>
    </section>
  `;
}

function overviewUpdateCards() {
  const cards = [
    ["research", "증권사리포트", store.researchReports.length],
    ["disclosure", "공시·IR", store.disclosures.length],
    ["news", "뉴스", store.newsItems.length],
  ];
  return cards
    .map(
      ([target, label, count]) => `
        <button class="overview-update-card" data-overview-target="${escapeHtml(target)}" type="button">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(formatNumber(count))}<small>건</small></strong>
        </button>
      `
    )
    .join("");
}

function overviewPortfolioBlock() {
  const account = primaryAccount();
  const holdings = overviewHoldingRows(3);
  return `
    <section class="overview-section overview-portfolio-block">
      <button class="overview-section-head" data-overview-target="portfolio" type="button">
        <strong>포트폴리오</strong>
        <span>${account ? "계좌 연결됨" : "보류"}</span>
        <span aria-hidden="true">›</span>
      </button>
      ${
        holdings.length
          ? `<div class="overview-feed-list">${holdings.map((item) => overviewBriefRow(item)).join("")}</div>`
          : `<div class="overview-empty">토스증권 연동은 보류되어 있습니다.</div>`
      }
    </section>
  `;
}

function overviewHelpBlock() {
  const items = [
    ["리포트 읽기", "목표주가와 투자의견 흐름 확인"],
    ["공시 분류 보기", "자사주, 배당, 공급계약 등 이벤트 추적"],
    ["뉴스 묶어보기", "종목별 최신 기사 흐름 확인"],
    ["관심기업 설정", "별표로 브리핑 필터 저장"],
  ];
  return `
    <section class="overview-section">
      <button class="overview-section-head" data-overview-target="help" type="button">
        <strong>사용법</strong>
        <span>핵심 흐름</span>
        <span aria-hidden="true">›</span>
      </button>
      <div class="overview-guide-list">
        ${items
          .map(
            ([title, copy]) => `
              <button class="overview-guide-row" data-overview-target="help" type="button">
                <strong>${escapeHtml(title)}</strong>
                <span>${escapeHtml(copy)}</span>
              </button>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

function overviewIndexBlock() {
  const quotes = store.briefingQuotes.slice(0, 5);
  return `
    <section class="overview-section">
      <button class="overview-section-head" data-overview-target="indices" type="button">
        <strong>주요 지수</strong>
        <span>시세 ${escapeHtml(cadenceLabel(store.runtime?.price_poll_seconds))}</span>
        <span aria-hidden="true">›</span>
      </button>
      <div class="overview-feed-list">
        ${
          quotes.length
            ? quotes
                .map(
                  (item) => `
                    <button class="overview-index-row" data-company-drill="${escapeHtml(item.code)}" type="button">
                      <strong>${escapeHtml(item.name || item.code)}</strong>
                      <span>${escapeHtml(formatNumber(item.price))}</span>
                      <em class="${escapeHtml(toneClass(item.change_value))}">${escapeHtml(formatPercent(item.change_rate))}</em>
                    </button>
                  `
                )
                .join("")
            : '<div class="overview-empty">시세 데이터 수집 대기 중입니다.</div>'
        }
      </div>
    </section>
  `;
}

function overviewRightRail() {
  const watchCount = watchCodeSet().size;
  const holdingCount = holdingCodeSet().size;
  return `
    <aside class="overview-side-panel">
      <div class="overview-account-card">
        <strong>자산 관리</strong>
        <span>계좌 연동은 아카이빙되어 있습니다.</span>
        <button class="overview-cta" data-overview-target="watchlist" type="button">관심기업 보기</button>
      </div>
      <div class="overview-side-tabs">
        <button data-overview-target="holdings" type="button"><strong>${escapeHtml(formatNumber(holdingCount))}</strong><span>보유기업</span></button>
        <button data-overview-target="watchlist" type="button"><strong>${escapeHtml(formatNumber(watchCount))}</strong><span>관심기업</span></button>
        <button data-overview-target="all-companies" type="button"><strong>${escapeHtml(formatNumber(store.companyBriefs.length))}</strong><span>전체기업</span></button>
        <button data-overview-target="indices" type="button"><strong>${escapeHtml(formatNumber(store.briefingQuotes.length))}</strong><span>주요지수</span></button>
      </div>
    </aside>
  `;
}

function butlerOverviewShell() {
  const reportRows = overviewReportRows().map((item) => overviewReportRow(item));
  const disclosureRows = overviewDisclosureRows().map((item) => overviewDisclosureRow(item));
  const newsRows = overviewNewsRows().map((item) => overviewNewsRow(item));
  const holdingRows = overviewHoldingRows().map((item) => overviewBriefRow(item));
  return `
    <div class="butler-overview-shell">
      <main class="overview-main-card">
        <section class="overview-update-section">
          <h2>오늘의 업데이트</h2>
          <div class="overview-update-grid">${overviewUpdateCards()}</div>
        </section>
        ${overviewSection("지금 많이 보는 리포트", store.researchReports.length, "research", reportRows, "표시할 리포트가 없습니다.")}
        ${overviewSection("주요 공시", store.disclosures.length, "disclosure", disclosureRows, "표시할 공시가 없습니다.")}
        ${overviewSection("최신 뉴스", store.newsItems.length, "news", newsRows, "표시할 뉴스가 없습니다.")}
        ${overviewPortfolioBlock()}
        ${overviewSection("보유기업 주요소식", holdingRows.length, "holdings", holdingRows, "보유기업 연동 데이터가 없습니다.")}
        ${overviewHelpBlock()}
        ${overviewIndexBlock()}
      </main>
      ${overviewRightRail()}
    </div>
  `;
}

function companyBriefDesktopCard(item) {
  const marketLabel = [item.stock_code || "-", item.market || "-"].filter(Boolean).join(" · ");
  const priceView = companyBriefPriceView(item);
  return `
    <article class="company-brief-card">
      <div class="company-brief-head">
        <div class="company-brief-name-block">
          <div class="company-brief-title-row">
            <strong>${escapeHtml(item.company_name)}</strong>
            ${companyBriefBadges(item)}
          </div>
          <div class="company-brief-subline">
            <span>${escapeHtml(marketLabel)}</span>
            <span>총 신호 ${escapeHtml(String(item.total_count || 0))}건</span>
            <span>${formatDateTime(item.latest_published_at)}</span>
          </div>
        </div>
        <div class="company-brief-price-block">
          <label>${escapeHtml(priceView.label)}</label>
          <strong>${priceView.value ? formatNumber(priceView.value) : "-"}</strong>
          <span>${escapeHtml(priceView.asOf)}</span>
        </div>
      </div>
      <div class="company-brief-stats">
        ${companyBriefStat("리포트", formatNumber(item.report_count))}
        ${companyBriefStat("공시", formatNumber(item.disclosure_count))}
        ${companyBriefStat("뉴스", formatNumber(item.news_count))}
        ${companyBriefStat("최근갱신", formatDateOnly(item.latest_published_at))}
      </div>
      <div class="company-brief-streams">
        ${companyBriefStreamRow(
          "리포트",
          item.report_count,
          item.latest_report_title,
          item.latest_report_url,
          [item.latest_report_broker, formatDateTime(item.latest_report_at)].filter((value) => value && value !== "-").join(" · ")
        )}
        ${companyBriefStreamRow(
          "공시",
          item.disclosure_count,
          item.latest_disclosure_title,
          item.latest_disclosure_url,
          [labelForCategory("disclosure", item.latest_disclosure_category), formatDateTime(item.latest_disclosure_at)]
            .filter((value) => value && value !== "-")
            .join(" · ")
        )}
        ${companyBriefStreamRow(
          "뉴스",
          item.news_count,
          item.latest_news_title,
          item.latest_news_url,
          [item.latest_news_press, formatDateTime(item.latest_news_at)].filter((value) => value && value !== "-").join(" · ")
        )}
      </div>
    </article>
  `;
}

function renderDesktop(items) {
  if (state.section === "company_brief") {
    elements.desktopBoard.innerHTML = butlerOverviewShell();
    return;
  }

  if (!items.length) {
    const message =
      state.section === "company_brief" && state.companyBriefGroup === "holdings"
        ? "토스 보유 종목이 아직 동기화되지 않았습니다."
        : state.section === "company_brief" && state.companyBriefGroup === "watchlist"
          ? "관심 종목과 연결된 브리핑 카드가 아직 없습니다."
          : "표시할 데이터가 없습니다.";
    elements.desktopBoard.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
    return;
  }

  if (state.section === "portfolio") {
    if (state.category === "accounts") {
      const rows = items
        .map(
          (item) => `
            <tr>
              <td><strong>${escapeHtml(item.account_no || "-")}</strong><span class="muted">${escapeHtml(item.account_type || "-")}</span></td>
              <td class="number">${formatTossAccountMoney(item.total_purchase_amount_krw, item.total_purchase_amount_usd)}</td>
              <td class="number">${formatTossAccountMoney(item.market_value_krw, item.market_value_usd)}</td>
              <td class="number ${toneClass(item.profit_loss_rate)}">${formatRatioPercent(item.profit_loss_rate)}</td>
              <td class="number ${toneClass(item.daily_profit_loss_rate)}">${formatRatioPercent(item.daily_profit_loss_rate)}</td>
              <td class="number">${formatDateTime(item.synced_at)}</td>
            </tr>
          `
        )
        .join("");
      elements.desktopBoard.innerHTML = `
        <table class="data-table">
          <thead>
            <tr>
              <th>계좌</th>
              <th>투자원금</th>
              <th>평가금액</th>
              <th>누적수익률</th>
              <th>일간수익률</th>
              <th>동기화</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      return;
    }

    if (state.category === "orders") {
      const rows = items
        .map(
          (item) => `
            <tr>
              <td><strong>${escapeHtml(item.symbol)}</strong><span class="muted">${escapeHtml(item.currency || "-")}</span></td>
              <td><span class="pill">${escapeHtml(item.side || "-")}</span></td>
              <td>${escapeHtml(item.order_type || "-")} / ${escapeHtml(item.time_in_force || "-")}</td>
              <td><span class="pill">${escapeHtml(item.status || "-")}</span></td>
              <td class="number">${formatMoneyByCurrency(item.price, item.currency)}</td>
              <td class="number">${formatNumber(item.quantity)}</td>
              <td class="number">${formatNumber(item.filled_quantity)}</td>
              <td class="number">${formatDateTime(item.ordered_at)}</td>
            </tr>
          `
        )
        .join("");
      elements.desktopBoard.innerHTML = `
        <table class="data-table">
          <thead>
            <tr>
              <th>종목</th>
              <th>방향</th>
              <th>주문조건</th>
              <th>상태</th>
              <th>가격</th>
              <th>주문수량</th>
              <th>체결수량</th>
              <th>주문시각</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      return;
    }

    const rows = items
      .map(
        (item) => `
          <tr>
            <td><strong>${escapeHtml(item.name)}</strong><span class="muted">${escapeHtml(item.symbol)}</span></td>
            <td>${escapeHtml(item.currency || "-")} / ${escapeHtml(item.market_country || "-")}</td>
            <td class="number">${formatNumber(item.quantity)}</td>
            <td class="number">${formatMoneyByCurrency(item.last_price, item.currency)}</td>
            <td class="number">${formatMoneyByCurrency(item.average_purchase_price, item.currency)}</td>
            <td class="number">${formatMoneyByCurrency(item.market_value, item.currency)}</td>
            <td class="number ${toneClass(item.profit_loss_rate)}">${formatRatioPercent(item.profit_loss_rate)}</td>
            <td class="number ${toneClass(item.daily_profit_loss_rate)}">${formatRatioPercent(item.daily_profit_loss_rate)}</td>
          </tr>
        `
      )
      .join("");
    elements.desktopBoard.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>종목</th>
            <th>시장</th>
            <th>보유수량</th>
            <th>현재가</th>
            <th>평균단가</th>
            <th>평가금액</th>
            <th>누적수익률</th>
            <th>일간수익률</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    return;
  }

  if (state.section === "research") {
    const rows = items
      .map((item) => {
        const latest = priceInfo(item.stock_code);
        const returnRate = impliedReturn(item.target_price, item.stock_code);
        return `
          <tr>
            <td><strong>${escapeHtml(item.company_name || item.subject_name || "-")}</strong><span class="muted">${escapeHtml(item.stock_code || item.source_category || "-")}</span></td>
            <td>${linkOrText(item.detail_url || item.pdf_url, item.title)}</td>
            <td class="number">${latest?.close ? formatNumber(latest.close) : "-"}</td>
            <td class="number">${item.target_price ? formatNumber(item.target_price) : "-"}</td>
            <td class="number ${returnRate > 0 ? "positive" : returnRate < 0 ? "negative" : "neutral"}">${formatPercent(returnRate)}</td>
            <td>${escapeHtml(item.broker_name || "-")}</td>
            <td><span class="pill">${escapeHtml(item.opinion || "-")}</span></td>
            <td class="number">${formatDateTime(item.published_at)}</td>
          </tr>
        `;
      })
      .join("");

    elements.desktopBoard.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>기업명</th>
            <th>리포트</th>
            <th>현재가</th>
            <th>목표주가</th>
            <th>기대수익률</th>
            <th>증권사</th>
            <th>투자의견</th>
            <th>작성일</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    return;
  }

  if (state.section === "disclosure") {
    const rows = items
      .map(
        (item) => `
          <tr>
            <td><strong>${escapeHtml(item.company_name)}</strong><span class="muted">${escapeHtml(item.stock_code || item.corp_class || "-")}</span></td>
            <td><span class="pill">${escapeHtml(labelForCategory("disclosure", item.disclosure_category))}</span></td>
            <td>${linkOrText(item.detail_url, item.report_name)}</td>
            <td>${escapeHtml(item.filer_name || "-")}</td>
            <td>${escapeHtml(item.remark || "-")}</td>
            <td class="number">${formatDateTime(item.published_at)}</td>
          </tr>
        `
      )
      .join("");

    elements.desktopBoard.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>기업명</th>
            <th>구분</th>
            <th>공시명</th>
            <th>제출자</th>
            <th>비고</th>
            <th>작성일</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    return;
  }

  const rows = items
    .map(
      (item) => `
        <tr>
          <td><span class="pill">${escapeHtml(labelForCategory("news", item.source_category))}</span></td>
          <td><strong>${linkOrText(item.detail_url, item.title)}</strong></td>
          <td>${escapeHtml(item.press_name || "-")}</td>
          <td class="muted">${escapeHtml(item.summary || "-")}</td>
          <td class="number">${formatDateTime(item.published_at)}</td>
        </tr>
      `
    )
    .join("");

  elements.desktopBoard.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>구분</th>
          <th>제목</th>
          <th>언론사</th>
          <th>요약</th>
          <th>작성일</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderMobile(items) {
  if (state.section === "company_brief") {
    elements.mobileBoard.innerHTML = butlerOverviewShell();
    return;
  }

  if (!items.length) {
    const message =
      state.section === "company_brief" && state.companyBriefGroup === "holdings"
        ? "토스 보유 종목이 아직 동기화되지 않았습니다."
        : state.section === "company_brief" && state.companyBriefGroup === "watchlist"
          ? "관심 종목과 연결된 브리핑 카드가 아직 없습니다."
          : "표시할 데이터가 없습니다.";
    elements.mobileBoard.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
    return;
  }

  const cards = items.map((item) => {
    if (state.section === "portfolio") {
      if (state.category === "accounts") {
        return `
          <article class="mobile-card">
            <div class="mobile-card-header">
              <div class="mobile-card-title">
                <strong>${escapeHtml(item.account_no || "-")}</strong>
                <span class="muted">${escapeHtml(item.account_type || "-")}</span>
              </div>
              <span class="pill">${escapeHtml(item.broker_name || "toss")}</span>
            </div>
            <div class="mobile-card-grid">
              <div class="mobile-kv"><label>투자원금</label><span>${formatTossAccountMoney(item.total_purchase_amount_krw, item.total_purchase_amount_usd)}</span></div>
              <div class="mobile-kv"><label>평가금액</label><span>${formatTossAccountMoney(item.market_value_krw, item.market_value_usd)}</span></div>
              <div class="mobile-kv"><label>누적수익률</label><span class="${toneClass(item.profit_loss_rate)}">${formatRatioPercent(item.profit_loss_rate)}</span></div>
              <div class="mobile-kv"><label>일간수익률</label><span class="${toneClass(item.daily_profit_loss_rate)}">${formatRatioPercent(item.daily_profit_loss_rate)}</span></div>
            </div>
            <div class="mobile-card-meta"><span>${formatDateTime(item.synced_at)}</span></div>
          </article>
        `;
      }

      if (state.category === "orders") {
        return `
          <article class="mobile-card">
            <div class="mobile-card-header">
              <div class="mobile-card-title">
                <strong>${escapeHtml(item.symbol)}</strong>
                <span class="muted">${escapeHtml(item.currency || "-")}</span>
              </div>
              <span class="pill">${escapeHtml(item.status || "-")}</span>
            </div>
            <div class="mobile-card-grid">
              <div class="mobile-kv"><label>방향</label><span>${escapeHtml(item.side || "-")}</span></div>
              <div class="mobile-kv"><label>주문조건</label><span>${escapeHtml(item.order_type || "-")}</span></div>
              <div class="mobile-kv"><label>가격</label><span>${formatMoneyByCurrency(item.price, item.currency)}</span></div>
              <div class="mobile-kv"><label>주문수량</label><span>${formatNumber(item.quantity)}</span></div>
              <div class="mobile-kv"><label>체결수량</label><span>${formatNumber(item.filled_quantity)}</span></div>
              <div class="mobile-kv"><label>시간</label><span>${formatDateTime(item.ordered_at)}</span></div>
            </div>
          </article>
        `;
      }

      return `
        <article class="mobile-card">
          <div class="mobile-card-header">
            <div class="mobile-card-title">
              <strong>${escapeHtml(item.name)}</strong>
              <span class="muted">${escapeHtml(item.symbol)}</span>
            </div>
            <span class="pill">${escapeHtml(item.currency || "-")}</span>
          </div>
          <div class="mobile-card-grid">
            <div class="mobile-kv"><label>보유수량</label><span>${formatNumber(item.quantity)}</span></div>
            <div class="mobile-kv"><label>현재가</label><span>${formatMoneyByCurrency(item.last_price, item.currency)}</span></div>
            <div class="mobile-kv"><label>평균단가</label><span>${formatMoneyByCurrency(item.average_purchase_price, item.currency)}</span></div>
            <div class="mobile-kv"><label>평가금액</label><span>${formatMoneyByCurrency(item.market_value, item.currency)}</span></div>
            <div class="mobile-kv"><label>누적수익률</label><span class="${toneClass(item.profit_loss_rate)}">${formatRatioPercent(item.profit_loss_rate)}</span></div>
            <div class="mobile-kv"><label>일간수익률</label><span class="${toneClass(item.daily_profit_loss_rate)}">${formatRatioPercent(item.daily_profit_loss_rate)}</span></div>
          </div>
        </article>
      `;
    }

    if (state.section === "research") {
      const latest = priceInfo(item.stock_code);
      const returnRate = impliedReturn(item.target_price, item.stock_code);
      return `
        <article class="mobile-card">
          <div class="mobile-card-header">
            <div class="mobile-card-title">
              <strong>${escapeHtml(item.company_name || item.subject_name || "-")}</strong>
              <span class="muted">${escapeHtml(item.stock_code || item.source_category || "-")}</span>
            </div>
            <span class="pill">${escapeHtml(item.opinion || "-")}</span>
          </div>
          <div>${linkOrText(item.detail_url || item.pdf_url, item.title)}</div>
          <div class="mobile-card-grid">
            <div class="mobile-kv"><label>현재가</label><span>${latest?.close ? formatNumber(latest.close) : "-"}</span></div>
            <div class="mobile-kv"><label>목표주가</label><span>${item.target_price ? formatNumber(item.target_price) : "-"}</span></div>
            <div class="mobile-kv"><label>기대수익률</label><span class="${returnRate > 0 ? "positive" : returnRate < 0 ? "negative" : "neutral"}">${formatPercent(returnRate)}</span></div>
            <div class="mobile-kv"><label>증권사</label><span>${escapeHtml(item.broker_name || "-")}</span></div>
          </div>
          <div class="mobile-card-meta"><span>${formatDateTime(item.published_at)}</span></div>
        </article>
      `;
    }

    if (state.section === "disclosure") {
      return `
        <article class="mobile-card">
          <div class="mobile-card-header">
            <div class="mobile-card-title">
              <strong>${escapeHtml(item.company_name)}</strong>
              <span class="muted">${escapeHtml(item.stock_code || item.corp_class || "-")}</span>
            </div>
            <span class="pill">${escapeHtml(labelForCategory("disclosure", item.disclosure_category))}</span>
          </div>
          <div>${linkOrText(item.detail_url, item.report_name)}</div>
          <div class="mobile-card-meta">
            <span>${escapeHtml(item.filer_name || "-")}</span>
            <span>${escapeHtml(item.remark || "-")}</span>
            <span>${formatDateTime(item.published_at)}</span>
          </div>
        </article>
      `;
    }

    return `
      <article class="mobile-card">
        <div class="mobile-card-header">
          <div class="mobile-card-title">
            <strong>${linkOrText(item.detail_url, item.title)}</strong>
          </div>
          <span class="pill">${escapeHtml(labelForCategory("news", item.source_category))}</span>
        </div>
        <div class="mobile-card-meta">
          <span>${escapeHtml(item.press_name || "-")}</span>
          <span>${formatDateTime(item.published_at)}</span>
        </div>
        <div class="muted">${escapeHtml(item.summary || "-")}</div>
      </article>
    `;
  });

  elements.mobileBoard.innerHTML = cards.join("");
}

function setSection(section, options = {}) {
  state.section = normalizeSection(section);
  state.category = SECTION_CONFIG[state.section].defaultCategory;
  state.companyBriefGroup = options.group || "all";
  state.keyword = options.keyword || "";
  state.startDate = "";
  state.endDate = "";
  state.auxOne = "all";
  state.auxTwo = "all";
  if (options.category) {
    state.category = options.category;
  }
  state.detail = null;
  renderAll();
}

function openOverviewTarget(target) {
  if (target === "research") {
    setSection("research", { category: "all" });
    return;
  }
  if (target === "disclosure") {
    setSection("disclosure", { category: "all" });
    return;
  }
  if (target === "news") {
    setSection("news", { category: "all" });
    return;
  }
  if (target === "watchlist") {
    state.companyBriefGroup = "watchlist";
    renderAll();
    return;
  }
  if (target === "holdings") {
    state.companyBriefGroup = "holdings";
    renderAll();
    return;
  }
  if (target === "all-companies") {
    state.companyBriefGroup = "all";
    renderAll();
    return;
  }
  if (target === "indices" || target === "help" || target === "portfolio") {
    renderAll();
  }
}

function openReportDetail(reportId) {
  const report = reportById(reportId);
  if (!report) {
    return;
  }
  state.detail = { type: "report", id: String(report.id) };
  renderDetailModal();
  ensurePriceHistory(report.stock_code);
}

async function ensurePriceHistory(stockCode) {
  const code = normalizeStockCode(stockCode);
  if (!code || store.priceHistory[code] || store.priceHistoryStatus[code] === "loading") {
    return;
  }
  store.priceHistoryStatus[code] = "loading";
  renderDetailModal();
  try {
    const rows = await fetchJson(`/stocks/${encodeURIComponent(code)}/prices?limit=180`);
    store.priceHistory[code] = Array.isArray(rows) ? rows : [];
    store.priceHistoryStatus[code] = "ready";
  } catch {
    store.priceHistory[code] = [];
    store.priceHistoryStatus[code] = "error";
  }
  const activeReport = state.detail?.type === "report" ? reportById(state.detail.id) : null;
  if (activeReport && normalizeStockCode(activeReport.stock_code) === code) {
    renderDetailModal();
  }
}

function drillToDisclosure(disclosureId) {
  const item = disclosureById(disclosureId);
  if (!item) {
    return;
  }
  setSection("disclosure", {
    category: item.disclosure_category || "all",
    keyword: item.company_name || "",
  });
}

function drillToNews(newsId) {
  const item = newsById(newsId);
  if (!item) {
    return;
  }
  const company = newsCompanyGuess(item);
  setSection("news", {
    category: "all",
    keyword: company?.company_name || "",
  });
}

function drillToCompany(value) {
  const code = normalizeStockCode(value);
  const brief =
    findBriefByCode(code) ||
    store.companyBriefs.find((item) => item.company_name === value) ||
    null;
  if (!brief) {
    return;
  }
  setSection("research", {
    category: "all",
    keyword: brief.company_name || brief.stock_code || "",
  });
}

function reportDetailPayload() {
  if (!state.detail || state.detail.type !== "report") {
    return null;
  }
  const report = reportById(state.detail.id);
  if (!report) {
    return null;
  }
  const brief = findBriefByCode(report.stock_code);
  const quote = findQuoteByCode(report.stock_code);
  const move = overviewMoveInfo(report);
  const returnRate = impliedReturn(report.target_price, report.stock_code);
  const reports = overviewReportRows(50);
  const index = reports.findIndex((item) => String(item.id) === String(report.id));
  const code = normalizeStockCode(report.stock_code);
  return {
    report,
    brief,
    quote,
    move,
    returnRate,
    priceHistory: code ? store.priceHistory[code] || [] : [],
    priceHistoryStatus: code ? store.priceHistoryStatus[code] || "idle" : "idle",
    previousId: index > 0 ? reports[index - 1].id : null,
    nextId: index >= 0 && index < reports.length - 1 ? reports[index + 1].id : null,
  };
}

function detailMetric(label, value) {
  return `
    <div class="detail-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || "-")}</strong>
    </div>
  `;
}

function numericValue(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) {
    return null;
  }
  return Number(value);
}

function chartDateValue(value) {
  if (!value) {
    return null;
  }
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? null : time;
}

function targetHistoryForReport(report) {
  const code = normalizeStockCode(report.stock_code);
  if (!code) {
    return [];
  }
  return store.researchReports
    .filter((item) => normalizeStockCode(item.stock_code) === code && numericValue(item.target_price) !== null && item.published_at)
    .map((item) => ({
      date: item.published_at,
      time: chartDateValue(item.published_at),
      value: numericValue(item.target_price),
      label: item.broker_name || "목표주가",
    }))
    .filter((item) => item.time !== null && item.value !== null)
    .sort((a, b) => a.time - b.time);
}

function closeHistoryForPayload(payload) {
  return (payload.priceHistory || [])
    .map((item) => ({
      date: item.trade_date,
      time: chartDateValue(item.trade_date),
      value: numericValue(item.close),
      label: "종가",
    }))
    .filter((item) => item.time !== null && item.value !== null)
    .sort((a, b) => a.time - b.time);
}

function polylinePoints(points, xFor, yFor) {
  return points.map((item) => `${xFor(item.time).toFixed(1)},${yFor(item.value).toFixed(1)}`).join(" ");
}

function detailChart(payload) {
  const targetPoints = targetHistoryForReport(payload.report);
  const closePoints = closeHistoryForPayload(payload);
  const hasTargetLine = targetPoints.length >= 2;
  const hasCloseLine = closePoints.length >= 2;

  if (payload.priceHistoryStatus === "loading") {
    return `
      <div class="detail-chart detail-chart-empty">
        <strong>실제 차트 데이터 불러오는 중</strong>
        <span>일봉과 목표주가 이력을 확인하고 있습니다.</span>
      </div>
    `;
  }

  if (!hasTargetLine && !hasCloseLine) {
    const reason = targetPoints.length || closePoints.length
      ? "선 그래프를 그리려면 같은 종목의 날짜별 데이터가 2개 이상 필요합니다."
      : "이 종목의 목표주가 이력 또는 일봉 데이터가 아직 충분히 적재되지 않았습니다.";
    return `
      <div class="detail-chart detail-chart-empty">
        <strong>차트 데이터 부족</strong>
        <span>${escapeHtml(reason)}</span>
      </div>
    `;
  }

  const allPoints = [...targetPoints, ...closePoints];
  const minTime = Math.min(...allPoints.map((item) => item.time));
  const maxTime = Math.max(...allPoints.map((item) => item.time));
  const values = allPoints.map((item) => item.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const width = 520;
  const height = 300;
  const pad = { top: 42, right: 28, bottom: 48, left: 52 };
  const timeSpan = maxTime === minTime ? 1 : maxTime - minTime;
  const valueSpan = maxValue === minValue ? 1 : maxValue - minValue;
  const xFor = (time) => pad.left + ((time - minTime) / timeSpan) * (width - pad.left - pad.right);
  const yFor = (value) => height - pad.bottom - ((value - minValue) / valueSpan) * (height - pad.top - pad.bottom);
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const value = minValue + valueSpan * ratio;
    const y = yFor(value);
    return { value, y };
  });
  const closeLimited = closePoints.slice(-120);
  const targetLimited = targetPoints.slice(-24);

  return `
    <div class="detail-chart detail-chart-real">
      <div class="detail-chart-title">목표주가 / 종가 추이</div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="실제 목표주가와 종가 추이">
        ${yTicks
          .map(
            (tick) => `
              <line class="chart-grid-line" x1="${pad.left}" x2="${width - pad.right}" y1="${tick.y.toFixed(1)}" y2="${tick.y.toFixed(1)}"></line>
              <text class="chart-axis-label" x="${pad.left - 8}" y="${(tick.y + 4).toFixed(1)}">${escapeHtml(formatNumber(Math.round(tick.value)))}</text>
            `
          )
          .join("")}
        ${
          hasCloseLine
            ? `<polyline class="chart-close-line" points="${escapeHtml(polylinePoints(closeLimited, xFor, yFor))}"></polyline>`
            : ""
        }
        ${
          hasTargetLine
            ? `<polyline class="chart-target-line" points="${escapeHtml(polylinePoints(targetLimited, xFor, yFor))}"></polyline>`
            : ""
        }
        ${targetLimited
          .map(
            (item) => `
              <circle class="chart-target-dot" cx="${xFor(item.time).toFixed(1)}" cy="${yFor(item.value).toFixed(1)}" r="4"></circle>
            `
          )
          .join("")}
      </svg>
      <div class="detail-chart-legend">
        <span><i class="legend-accent"></i>목표주가 ${escapeHtml(formatNumber(targetPoints.length))}개</span>
        <span><i class="legend-muted"></i>종가 ${escapeHtml(formatNumber(closePoints.length))}개</span>
      </div>
    </div>
  `;
}

function reportSummaryBullets(payload) {
  const { report, brief, returnRate } = payload;
  const bullets = [
    ["투자 의견 및 목표주가", `${report.opinion || "의견 없음"} · 목표주가 ${report.target_price ? `${formatNumber(report.target_price)}원` : "미제시"}${returnRate !== null ? ` · 기대수익률 ${formatPercent(returnRate)}` : ""}`],
    ["최근 연결 신호", brief ? `리포트 ${formatNumber(brief.report_count)}건 · 공시 ${formatNumber(brief.disclosure_count)}건 · 뉴스 ${formatNumber(brief.news_count)}건` : "종목 브리핑 연결 대기"],
    ["리포트 핵심", report.title || "제목 없음"],
  ];
  return bullets
    .map(
      ([title, body]) => `
        <div class="detail-bullet">
          <strong>${escapeHtml(title)}</strong>
          <p>${escapeHtml(body)}</p>
        </div>
      `
    )
    .join("");
}

function reportDetailModal(payload) {
  const { report, brief, move, returnRate, previousId, nextId } = payload;
  const companyName = entityCompanyName(report);
  const price = move.price ? `${formatNumber(move.price)}원` : "-";
  const change = move.hasMove
    ? `${Number(move.changeValue) > 0 ? "+" : ""}${formatNumber(move.changeValue)}원 · ${formatPercent(move.changeRate)}`
    : "시세 대기";
  return `
    <div class="detail-backdrop" data-detail-close="true">
      <section class="detail-modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(companyName)} 리포트 상세">
        <header class="detail-head">
          <div>
            <strong>${escapeHtml(companyName)}</strong>
            <span class="${escapeHtml(move.tone)}">${escapeHtml(price)} · ${escapeHtml(change)}</span>
          </div>
          <div class="detail-actions">
            ${overviewWatchButton(report.stock_code, companyName)}
            <button class="detail-close" data-detail-close="true" type="button" aria-label="닫기">×</button>
          </div>
        </header>
        <div class="detail-metric-strip">
          ${detailMetric("종목코드", report.stock_code || "-")}
          ${detailMetric("시장", brief?.market || "-")}
          ${detailMetric("투자의견", report.opinion || "-")}
          ${detailMetric("기대수익률", returnRate !== null ? formatPercent(returnRate) : "-")}
          ${detailMetric("작성일", formatDateOnly(report.published_at))}
        </div>
        <div class="detail-title-row">
          <h2>${escapeHtml(report.title || "-")}</h2>
          <span>${escapeHtml(report.broker_name || "증권사")}</span>
        </div>
        <div class="detail-body-grid">
          ${detailChart(payload)}
          <aside class="detail-side">
            ${detailMetric("목표주가", report.target_price ? `${formatNumber(report.target_price)}원` : "-")}
            ${detailMetric("현재가", price)}
            ${detailMetric("브리핑 갱신", formatDateTime(brief?.latest_published_at))}
            ${report.detail_url || report.pdf_url ? `<a class="detail-source-link" href="${escapeHtml(report.detail_url || report.pdf_url)}" rel="noreferrer">원문 보기</a>` : ""}
          </aside>
        </div>
        <div class="detail-summary">${reportSummaryBullets(payload)}</div>
        <footer class="detail-nav">
          <button data-detail-nav="${escapeHtml(previousId || "")}" ${previousId ? "" : "disabled"} type="button">‹ 이전</button>
          <button data-detail-nav="${escapeHtml(nextId || "")}" ${nextId ? "" : "disabled"} type="button">다음 ›</button>
        </footer>
      </section>
    </div>
  `;
}

function renderDetailModal() {
  let root = document.getElementById("detail-modal-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "detail-modal-root";
    document.body.appendChild(root);
  }
  const payload = reportDetailPayload();
  root.innerHTML = payload ? reportDetailModal(payload) : "";
}

function labelForCategory(section, value) {
  const entry = SECTION_CONFIG[section].categories.find(([itemValue]) => itemValue === value);
  return entry ? entry[1] : value;
}

function renderBoards() {
  const items = filteredItems();
  renderMeta(items.length);
  renderDesktop(items);
  renderMobile(items);
  renderDetailModal();
}

function renderAll() {
  disableBrowserCommentOverlay();
  renderResponsiveIndicators();
  renderSidebar();
  renderFilters();
  renderBoards();
}

function resetSectionFilters() {
  state.category = SECTION_CONFIG[state.section].defaultCategory;
  state.companyBriefGroup = "all";
  state.auxOne = "all";
  state.auxTwo = "all";
  state.detail = null;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function scheduleAutoRefresh() {
  if (autoRefreshHandle) {
    window.clearInterval(autoRefreshHandle);
  }
  autoRefreshHandle = window.setInterval(() => {
    if (document.visibilityState === "visible") {
      loadData({ silent: true });
    }
  }, AUTO_REFRESH_MS);
}

async function loadData(options = {}) {
  const { silent = false } = options;
  if (loadPromise) {
    return loadPromise;
  }

  if (!silent) {
    elements.desktopBoard.innerHTML = '<div class="empty-state">불러오는 중...</div>';
    elements.mobileBoard.innerHTML = '<div class="empty-state">불러오는 중...</div>';
  }

  loadPromise = (async () => {
    try {
      const [feed, runtime] = await Promise.all([
        fetchJson("/insight/feed?research_limit=200&disclosure_limit=200&news_limit=200&company_brief_limit=240"),
        fetchJson("/briefings/status"),
      ]);
      store.briefing = feed.briefing;
      store.runtime = runtime;
      store.companyBriefs = feed.company_briefs || [];
      store.briefingQuotes = feed.briefing_quotes || [];
      store.researchReports = feed.research_reports || [];
      store.disclosures = feed.disclosures || [];
      store.newsItems = feed.news_items || [];
      store.tossStatus = feed.toss_status || null;
      store.tossAccounts = feed.toss_accounts || [];
      store.tossHoldings = feed.toss_holdings || [];
      store.tossOrders = feed.toss_orders || [];
      store.watchCodes = feed.watch_codes || [];
      initializeUserWatchCodes(store.watchCodes);
      store.latestPrices = feed.latest_prices || {};
      renderAll();
      scheduleAutoRefresh();
    } catch (error) {
      elements.desktopBoard.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "데이터를 불러오지 못했습니다.")}</div>`;
      elements.mobileBoard.innerHTML = elements.desktopBoard.innerHTML;
      elements.sidebarStatus.textContent = "연결 오류";
    } finally {
      loadPromise = null;
    }
  })();

  return loadPromise;
}

function bindEvents() {
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    if (target.dataset.detailClose === "true") {
      event.preventDefault();
      state.detail = null;
      renderDetailModal();
      return;
    }

    const watchButton = target.closest("[data-watch-code]");
    if (watchButton instanceof HTMLElement && watchButton.dataset.watchCode) {
      event.preventDefault();
      event.stopPropagation();
      toggleUserWatchCode(watchButton.dataset.watchCode);
      return;
    }

    const detailNav = target.closest("[data-detail-nav]");
    if (detailNav instanceof HTMLElement && detailNav.dataset.detailNav) {
      event.preventDefault();
      openReportDetail(detailNav.dataset.detailNav);
      return;
    }

    const reportDetail = target.closest("[data-report-detail]");
    if (reportDetail instanceof HTMLElement && reportDetail.dataset.reportDetail) {
      event.preventDefault();
      openReportDetail(reportDetail.dataset.reportDetail);
      return;
    }

    const disclosureDrill = target.closest("[data-disclosure-drill]");
    if (disclosureDrill instanceof HTMLElement && disclosureDrill.dataset.disclosureDrill) {
      event.preventDefault();
      drillToDisclosure(disclosureDrill.dataset.disclosureDrill);
      return;
    }

    const newsDrill = target.closest("[data-news-drill]");
    if (newsDrill instanceof HTMLElement && newsDrill.dataset.newsDrill) {
      event.preventDefault();
      drillToNews(newsDrill.dataset.newsDrill);
      return;
    }

    const companyDrill = target.closest("[data-company-drill]");
    if (companyDrill instanceof HTMLElement && companyDrill.dataset.companyDrill) {
      event.preventDefault();
      drillToCompany(companyDrill.dataset.companyDrill);
      return;
    }

    const overviewTarget = target.closest("[data-overview-target]");
    if (overviewTarget instanceof HTMLElement && overviewTarget.dataset.overviewTarget) {
      event.preventDefault();
      openOverviewTarget(overviewTarget.dataset.overviewTarget);
      return;
    }

    const textLink = target.closest("a.text-link[href]");
    if (textLink instanceof HTMLAnchorElement) {
      const href = textLink.getAttribute("href");
      if (href) {
        event.preventDefault();
        window.location.assign(href);
      }
      return;
    }

    const nav = target.closest("[data-section]");
    if (nav instanceof HTMLElement && nav.dataset.section) {
      state.section = normalizeSection(nav.dataset.section);
      resetSectionFilters();
      if (nav.dataset.category && !ARCHIVED_SECTIONS.has(nav.dataset.section)) {
        state.category = nav.dataset.category;
      }
      renderAll();
      return;
    }

    const tab = target.closest("[data-category]");
    if (tab instanceof HTMLElement && tab.dataset.category) {
      state.category = tab.dataset.category;
      renderAll();
      return;
    }

    const companyGroupTab = target.closest("[data-company-group]");
    if (companyGroupTab instanceof HTMLElement && companyGroupTab.dataset.companyGroup) {
      state.companyBriefGroup = companyGroupTab.dataset.companyGroup;
      renderAll();
    }
  });

  elements.categorySelect.addEventListener("change", (event) => {
    state.category = event.target.value;
    renderAll();
  });
  elements.auxOne.addEventListener("change", (event) => {
    state.auxOne = event.target.value;
    renderAll();
  });
  elements.auxTwo.addEventListener("change", (event) => {
    state.auxTwo = event.target.value;
    renderAll();
  });
  elements.keywordInput.addEventListener("input", (event) => {
    state.keyword = event.target.value;
    renderBoards();
  });
  elements.startDate.addEventListener("change", (event) => {
    state.startDate = event.target.value;
    renderBoards();
  });
  elements.endDate.addEventListener("change", (event) => {
    state.endDate = event.target.value;
    renderBoards();
  });
  elements.resetFilters.addEventListener("click", () => {
    state.keyword = "";
    state.startDate = "";
    state.endDate = "";
    resetSectionFilters();
    elements.keywordInput.value = "";
    elements.startDate.value = "";
    elements.endDate.value = "";
    renderAll();
  });
  elements.refreshButton.addEventListener("click", () => {
    loadData();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      loadData({ silent: true });
    }
  });
  window.addEventListener("resize", () => {
    renderResponsiveIndicators();
  });
}

detectViewMode();
watchBrowserCommentOverlay();
bindEvents();
loadData();
