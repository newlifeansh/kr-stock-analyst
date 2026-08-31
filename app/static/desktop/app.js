(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const COLS = 24;
  const ROWS = 140;
  const FIXED_SHEETS = [
    { id: "home", label: "홈" },
    { id: "search", label: "검색" },
    { id: "portfolio", label: "내 종목" },
    { id: "notifications", label: "알림", utility: true },
  ];
  const UTILITY_SHEETS = {
    briefing: { id: "briefing", label: "돈이 되는 소식", utility: true },
    signals: { id: "signals", label: "AI 시그널", utility: true },
    movers: { id: "movers", label: "급등주", utility: true },
  };
  const VIEW_ALIASES = new Set([...FIXED_SHEETS.map((sheet) => sheet.id), ...Object.keys(UTILITY_SHEETS), "chart"]);
  const WATCHLIST_ID_KEY = "analyst.watchlistId";
  const RECOMMENDATION_TRACK_KEY = "analyst.recommendationTracks";
  const DEFAULT_DOCUMENT_TITLE = "한국증시 비밀노트";
  const DOCUMENT_TITLE_KEY_PREFIX = "analyst.desktop.documentTitle.";
  const DOCUMENT_TITLE_PENDING_PREFIX = "analyst.desktop.documentTitlePending.";
  const SIDE_PANEL_COLLAPSED_KEY = "analyst.desktop.sidePanelCollapsed";
  const DESKTOP_SW_VERSION = "20260829h4";
  const state = {
    active: "home",
    details: new Map(),
    cache: new Map(),
    selectedCell: "A1",
    watchlistId: "",
    writeToken: "",
    renderToken: 0,
    inviteRequired: true,
    inviteAuthorized: false,
    notificationFilter: "all",
    notificationItems: [],
    notificationRetentionDays: 3,
    desktopPushConfig: null,
    desktopPushEnabled: false,
    desktopPushConditions: [],
    desktopPushBusy: false,
    desktopPushMessage: "알림 상태 확인 중…",
    desktopPushTone: "",
    desktopSessionReady: false,
    documentTitle: DEFAULT_DOCUMENT_TITLE,
    documentTitlePending: false,
    documentTitleSaveTimer: 0,
    documentTitleSaveVersion: 0,
    liveQuoteSocket: null,
    liveQuoteReconnectTimer: 0,
    liveQuoteFallbackTimer: 0,
    liveQuoteReconnectAttempt: 0,
    liveQuoteModels: new Map(),
    liveMarketRefreshTimer: 0,
    liveGeneration: 0,
    detailTabs: new Map(),
    detailPricePeriods: new Map(),
    detailFinancialMetrics: new Map(),
    detailFinancialScopes: new Map(),
    detailFlowModes: new Map(),
    detailFlowPeriods: new Map(),
    detailReportModes: new Map(),
    detailDisclosuresExpanded: new Map(),
    detailIssueKeywords: new Map(),
    portfolioTab: "watchlist",
    portfolioContentTab: "strategy",
    portfolioFilter: "all",
    portfolioNewsCode: "all",
    openUtilitySheets: new Set(),
    recommendationDetails: new Map(),
    marketSignalStage: "all",
    marketSignalSector: "all",
    moversMarket: "ALL",
    moversSector: "all",
  };

  const elements = {
    app: document.querySelector(".desk-app"),
    sheet: $("desk-sheet"), tabs: $("desk-tabs"), columnHeaders: $("desk-column-headers"),
    rowHeaders: $("desk-row-headers"), gridShell: $("desk-grid-shell"), status: $("desk-status"),
    nameBox: $("desk-name-box"), formulaValue: $("desk-formula-value"), account: $("desk-account-button"),
    marketClock: $("desk-market-clock"), login: $("desk-login"), loginForm: $("desk-login-form"),
    loginId: $("desk-login-id"), inviteWrap: $("desk-invite-wrap"), inviteCode: $("desk-invite-code"),
    loginStatus: $("desk-login-status"), documentTitle: $("desk-document-title"),
    saveState: $("desk-save-state"), sidePanel: $("desk-side-panel"), sideToggle: $("desk-side-toggle"),
  };

  function text(value, fallback = "-") {
    if (value === null || value === undefined || value === "") return fallback;
    return String(value);
  }

  function number(value, digits = 0) {
    if (value === null || value === undefined || value === "") return "-";
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return "-";
    return parsed.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
  }

  function percent(value) {
    if (value === null || value === undefined || value === "") return "-";
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${parsed > 0 ? "+" : ""}${number(parsed, 2)}%` : "-";
  }

  function ratioPercent(value, digits = 2) {
    if (value === null || value === undefined || value === "") return "-";
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${number(parsed, digits)}%` : "-";
  }

  function multiple(value, digits = 2) {
    if (value === null || value === undefined || value === "") return "-";
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${number(parsed, digits)}배` : "-";
  }

  function signedMoney(value) {
    if (value === null || value === undefined || value === "") return "-";
    const parsed = Number(value);
    return Number.isFinite(parsed) ? `${parsed > 0 ? "+" : ""}${shortMoney(parsed)}` : "-";
  }

  function dateLabel(value, fallback = "-") {
    const raw = String(value || "");
    const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? `${match[1]}.${match[2]}.${match[3]}` : raw || fallback;
  }

  function previousClose(quote = {}) {
    const price = finiteNumber(quote.price), change = finiteNumber(quote.change_value);
    return price === null || change === null ? null : price - change;
  }

  function normalizePriceRows(prices = [], quote = null) {
    const rows = (Array.isArray(prices) ? prices : []).map((row) => ({
      ...row,
      date: String(row.trade_date || row.date || ""),
      open: finiteNumber(row.open), high: finiteNumber(row.high), low: finiteNumber(row.low),
      close: finiteNumber(row.close), volume: finiteNumber(row.volume),
    })).filter((row) => row.date && row.close !== null).sort((a, b) => a.date.localeCompare(b.date));
    const livePrice = finiteNumber(quote?.price), liveDate = String(quote?.trade_date || "");
    if (livePrice !== null && liveDate) {
      const liveRow = rows.find((row) => row.date === liveDate);
      if (liveRow) {
        liveRow.close = livePrice;
        liveRow.volume = finiteNumber(quote?.volume) ?? liveRow.volume;
        liveRow.high = Math.max(liveRow.high ?? livePrice, livePrice);
        liveRow.low = Math.min(liveRow.low ?? livePrice, livePrice);
      }
    }
    return rows;
  }

  function detailItemUrl(row = {}) {
    if (row.source === "naver_finance" && row.source_category === "company" && /^\d{6}$/.test(String(row.stock_code || "")) && /^\d+$/.test(String(row.external_id || ""))) {
      return `https://m.stock.naver.com/domestic/stock/${encodeURIComponent(row.stock_code)}/research/${encodeURIComponent(row.external_id)}`;
    }
    const newsMatch = row.source === "naver_finance" ? String(row.external_id || "").match(/^(\d+):(\d+)$/) : null;
    if (newsMatch) return `https://n.news.naver.com/mnews/article/${encodeURIComponent(newsMatch[1])}/${encodeURIComponent(newsMatch[2])}`;
    return row.pdf_url || row.detail_url || row.url || "";
  }

  function escapeMarkup(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
  }

  function shortMoney(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return "-";
    if (Math.abs(parsed) >= 1e12) return `${number(parsed / 1e12, 1)}조`;
    if (Math.abs(parsed) >= 1e8) return `${number(parsed / 1e8, 0)}억`;
    if (Math.abs(parsed) >= 1e4) return `${number(parsed / 1e4, 0)}만`;
    return number(parsed);
  }

  function financialSeriesAmount(value, unit = "억원", compact = false) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return "-";
    const normalizedUnit = text(unit, "억원");
    if (normalizedUnit === "억원") {
      if (compact && Math.abs(parsed) >= 10000) return `${number(parsed / 10000, 1)}조`;
      return `${number(parsed)}억`;
    }
    if (normalizedUnit === "원") return shortMoney(parsed);
    return `${number(parsed)}${normalizedUnit.replace(/원$/, "")}`;
  }

  function financialPeriodLabel(value, estimated = false, compact = false) {
    const normalized = text(value, "-").replace(/\s*\(E\)\s*$/i, "");
    const period = compact ? normalized.replace(/^20/, "") : normalized;
    return `${period}${estimated ? compact ? "E" : " (E)" : ""}`;
  }

  function colName(index) {
    let result = "";
    for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) result = String.fromCharCode(65 + ((n - 1) % 26)) + result;
    return result;
  }

  function cellName(col, row) { return `${colName(col)}${row}`; }

  function initializeHeaders() {
    elements.columnHeaders.replaceChildren(...Array.from({ length: COLS }, (_, index) => {
      const span = document.createElement("span"); span.textContent = colName(index); return span;
    }));
    elements.rowHeaders.replaceChildren(...Array.from({ length: ROWS }, (_, index) => {
      const span = document.createElement("span"); span.textContent = String(index + 1); return span;
    }));
  }

  function grid() {
    const node = document.createElement("div");
    node.className = "desk-sheet-grid";
    node.setAttribute("role", "grid");
    node.setAttribute("aria-rowcount", String(ROWS));
    node.setAttribute("aria-colcount", String(COLS));
    return node;
  }

  function addCell(root, value, col, row, options = {}) {
    const node = document.createElement(options.tag || "div");
    const spanCols = options.cols || 1;
    const spanRows = options.rows || 1;
    node.className = `desk-cell ${options.className || ""}`.trim();
    node.style.gridColumn = `${col + 1} / span ${spanCols}`;
    node.style.gridRow = `${row} / span ${spanRows}`;
    node.dataset.cell = cellName(col, row);
    node.setAttribute("role", "gridcell");
    node.tabIndex = options.click || options.selectable ? 0 : -1;
    if (options.html) node.innerHTML = value;
    else node.textContent = text(value, options.fallback ?? "");
    if (options.href) {
      node.href = options.href;
      node.target = "_blank";
      node.rel = "noopener noreferrer";
    }
    if (options.title) node.title = options.title;
    if (options.ariaLabel) node.setAttribute("aria-label", options.ariaLabel);
    if (options.click) node.addEventListener("click", options.click);
    root.appendChild(node);
    return node;
  }

  function section(root, title, col, row, cols) {
    return addCell(root, title, col, row, { cols, className: "desk-cell-subtitle" });
  }

  function detailTab(root, code, id, label, col, width = 2) {
    const active = (state.detailTabs.get(code) || "summary") === id;
    const cell = addCell(root, "", col, 2, { cols: width, className: `desk-cell-detail-tab${active ? " is-active" : ""}` });
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(active));
    button.addEventListener("click", () => {
      state.detailTabs.set(code, id);
      activate(`detail:${code}`, { replaceHistory: true });
    });
    cell.appendChild(button);
  }

  function detailOptionButton(root, code, stateMap, defaultValue, id, label, col, row, width = 1) {
    const active = (stateMap.get(code) || defaultValue) === id;
    const cell = addCell(root, "", col, row, { cols: width, className: `desk-cell-option${active ? " is-active" : ""}` });
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-pressed", String(active));
    button.addEventListener("click", () => {
      stateMap.set(code, id);
      activate(`detail:${code}`, { replaceHistory: true });
    });
    cell.appendChild(button);
    return cell;
  }

  function detailActionButton(root, label, col, row, width, action, options = {}) {
    const cell = addCell(root, "", col, row, { cols: width, className: `desk-cell-button ${options.className || ""}`.trim() });
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    if (options.ariaLabel) button.setAttribute("aria-label", options.ariaLabel);
    button.addEventListener("click", action);
    cell.appendChild(button);
    return button;
  }

  function portfolioSheetTab(root, group, id, label, col, row, width = 2) {
    const stateKey = group === "primary" ? "portfolioTab" : "portfolioContentTab";
    const active = state[stateKey] === id;
    const cell = addCell(root, "", col, row, { cols: width, className: `desk-cell-detail-tab${active ? " is-active" : ""}` });
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(active));
    button.addEventListener("click", () => {
      state[stateKey] = id;
      activate("portfolio", { replaceHistory: true });
    });
    cell.appendChild(button);
  }

  function sheetOptionButton(root, id, label, col, row, width, active, action, options = {}) {
    const cell = addCell(root, "", col, row, {
      cols: width,
      className: `desk-cell-option${active ? " is-active" : ""}${options.className ? ` ${options.className}` : ""}`,
    });
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.dataset.option = id;
    button.setAttribute(options.role === "tab" ? "aria-selected" : "aria-pressed", String(active));
    if (options.role) button.setAttribute("role", options.role);
    if (options.ariaLabel) button.setAttribute("aria-label", options.ariaLabel);
    button.addEventListener("click", action);
    cell.appendChild(button);
    return cell;
  }

  function safeExternalUrl(value) {
    if (!value) return "";
    try {
      const target = new URL(value, location.origin);
      return ["http:", "https:"].includes(target.protocol) ? target.href : "";
    } catch {
      return "";
    }
  }

  function quantSignalState(payload = {}) {
    const current = payload.current || {}, events = Array.isArray(payload.events) ? payload.events : [];
    const latest = events.length ? events[events.length - 1] : null;
    const action = String(current.action || "waiting");
    if (action === "entry_watch") return ["예비 매수 포착", current.next_confirmation || "다음 매수 확정 조건을 확인하고 있어요.", "buy"];
    if (action === "entry_pending") return ["매수 대기중", "다음 거래일 시가에 매수로 반영할 예정이에요.", "buy"];
    if (action === "partial_exit_pending") return [`${Number(current.pending_profit_stage || (Number(current.profit_stage || 0) + 1))}차 수익확정 대기중`, current.next_confirmation || "다음 거래일 시가에 수익확정으로 반영할 예정이에요.", "sell"];
    if (action === "full_exit_pending") return ["전량 매도 대기중", current.next_confirmation || "다음 거래일 시가에 전량 매도로 반영할 예정이에요.", "sell"];
    if (current.position_open || ["entered", "holding", "partially_exited"].includes(action) || ["buy", "partial_sell"].includes(latest?.side)) {
      const partial = action === "partially_exited" || latest?.side === "partial_sell";
      return [partial ? `${Number(current.profit_stage || latest?.profit_stage || 1)}차 수익확정 후 보유중` : "매수 후 보유중", current.next_confirmation || "다음 매도 신호를 확인하고 있어요.", "hold"];
    }
    if (action === "exited" || latest?.side === "sell") return ["전량 매도 후 대기중", "현재는 미보유 상태이며, 다음 매수 신호를 기다리고 있어요.", "sell"];
    return ["관망 중", "현재는 새 매수 신호를 기다리고 있어요.", "hold"];
  }

  function renderDesktopQuantSignal(root, payload = {}) {
    if (payload.data_state !== "ready") {
      addCell(root, payload.data_message || "AI 시그널을 계산할 가격 데이터가 부족합니다.", 0, 7, { cols: 12, className: "desk-cell-status" });
      return;
    }
    const current = payload.current || {}, performance = payload.performance || {}, events = Array.isArray(payload.events) ? payload.events.slice().reverse() : [];
    const [headline, next, tone] = quantSignalState(payload);
    section(root, "AI 지금 이렇게 판단해요", 0, 6, 12);
    addCell(root, headline, 0, 7, { cols: 3, className: `desk-cell-signal-state desk-badge-${tone}` });
    addCell(root, next, 3, 7, { cols: 9, className: "desk-cell-wrap" });
    headers(root, ["현재가(원)", "전략 잔여비중(%)", "목표 매도가(원)", "매수 후 수익률(%)", "신호 판단 시점", "데이터 원천"], 0, 10, [2,2,2,2,2,2]);
    addCell(root, current.price ? `${number(current.price)}원` : "-", 0, 11, { cols: 2, className: "desk-cell-number" });
    addCell(root, `${number(current.model_exposure_percent || 0)}%`, 2, 11, { cols: 2, className: "desk-cell-number" });
    addCell(root, current.partial_exit_reference || current.target_sell_price ? `${number(current.partial_exit_reference || current.target_sell_price)}원` : "-", 4, 11, { cols: 2, className: "desk-cell-number" });
    addCell(root, percent(current.unrealized_return), 6, 11, { cols: 2, className: `desk-cell-number ${changeClass(current.unrealized_return)}` });
    addCell(root, text(current.as_of || payload.as_of), 8, 11, { cols: 2 });
    addCell(root, payload.signal_source === "canonical" ? "공통 기준 시그널" : "로컬 계산", 10, 11, { cols: 2 });
    section(root, "최근 1년 AI 시그널", 0, 15, 12);
    headers(root, ["체결일", "구분", "체결가(원)", "목표 매도가(원)", "목표 결과", "수익률(%)", "보유 상태", "판단 이유"], 0, 16, [1,1,2,2,2,1,1,2]);
    events.slice(0, 18).forEach((event, index) => {
      const row = 17 + index, side = event.side === "buy" ? "확정 매수" : event.side === "partial_sell" ? event.label || `${number(event.profit_stage || 1)}차 수익확정` : "전량 매도";
      const targetResult = event.target_sell_status === "hit" ? "목표 도달" : event.target_sell_status === "missed" ? "목표 미달" : "확인 중";
      addCell(root, text(event.execution_date || event.signal_date).slice(0, 10), 0, row);
      addCell(root, side, 1, row, { className: `desk-cell-${event.side === "buy" ? "positive" : "negative"}` });
      addCell(root, event.price ? `${number(event.price)}원` : "-", 2, row, { cols: 2, className: "desk-cell-number" });
      addCell(root, event.target_sell_price ? `${number(event.target_sell_price)}원` : "-", 4, row, { cols: 2, className: "desk-cell-number" });
      addCell(root, targetResult, 6, row, { cols: 2 });
      addCell(root, percent(event.return_rate), 8, row, { className: `desk-cell-number ${changeClass(event.return_rate)}` });
      addCell(root, event.side === "partial_sell" ? `잔여 ${number(event.position_percent)}%` : event.side === "sell" ? "보유 종료" : "보유 100%", 9, row);
      addCell(root, event.reason, 10, row, { cols: 2, title: event.reason });
    });
    if (!events.length) addCell(root, "최근 1년 매매내역이 없습니다.", 0, 17, { cols: 12, className: "desk-cell-status" });
    section(root, "같은 규칙을 최근 1년 가격에 적용한 결과", 0, 38, 12);
    headers(root, ["1년 모의 누적수익률(%)", "최대 낙폭(%)", "연환산 변동성(%)", "평균 전략 보유비중(%)", "매매 적중률(%)", "완료 매매(회)"], 0, 39, [2,2,2,2,2,2]);
    addCell(root, percent(performance.strategy_return), 0, 40, { cols: 2, className: `desk-cell-number ${changeClass(performance.strategy_return)}` });
    addCell(root, percent(performance.max_drawdown), 2, 40, { cols: 2, className: "desk-cell-number desk-cell-negative" });
    addCell(root, percent(performance.annualized_volatility), 4, 40, { cols: 2, className: "desk-cell-number" });
    addCell(root, percent(performance.average_model_exposure_percent), 6, 40, { cols: 2, className: "desk-cell-number" });
    addCell(root, performance.win_rate == null ? "-" : `${number(performance.win_rate, 1)}%`, 8, 40, { cols: 2, className: "desk-cell-number" });
    addCell(root, `${number(performance.completed_trades || 0)}회`, 10, 40, { cols: 2, className: "desk-cell-number" });
    addCell(root, performance.sample_note || "같은 규칙을 최근 1년 가격에 적용한 결과입니다.", 0, 42, { cols: 12, className: "desk-cell-muted" });
    addCell(root, "AI가 과거 데이터로 계산한 교육·연구용 참고 신호이며, 투자 권유·자문·수익 보장 또는 실제 주문이 아닙니다.", 0, 44, { cols: 12, className: "desk-cell-status" });
  }

  function headers(root, labels, col, row, widths = []) {
    let cursor = col;
    labels.forEach((label, index) => {
      const width = widths[index] || 1;
      addCell(root, label, cursor, row, { cols: width, className: "desk-cell-header" });
      cursor += width;
    });
  }

  function statusRow(root, message, row, className = "desk-cell-status") {
    addCell(root, message, 0, row, { cols: 12, className });
  }

  async function api(path, options = {}) {
    const response = await fetch(path, { credentials: "same-origin", cache: "no-store", ...options });
    if (!response.ok) throw new Error(`${response.status} ${path}`);
    return response.json();
  }

  async function cached(path, ttl = 60000) {
    const hit = state.cache.get(path);
    if (hit && Date.now() - hit.at < ttl) return structuredClone(hit.data);
    const data = await api(path);
    state.cache.set(path, { at: Date.now(), data });
    return structuredClone(data);
  }

  function sheetTitle(root, title, subtitle) {
    addCell(root, title, 0, 1, { cols: 7, className: "desk-cell-title" });
    addCell(root, subtitle, 7, 1, { cols: 5, className: "desk-cell-muted desk-cell-number" });
  }

  function changeClass(value) {
    const n = Number(value);
    return n > 0 ? "desk-cell-positive" : n < 0 ? "desk-cell-negative" : "";
  }

  function sparkline(points, color = "#0f9d58", unit = "") {
    const rows = (points || []).map((point, index) => ({ point, index, value: Number(point.value ?? point.close) })).filter((row) => Number.isFinite(row.value));
    const values = rows.map((row) => row.value);
    if (values.length < 2) return "";
    const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
    const coordinates = values.map((value, index) => `${(index / (values.length - 1)) * 100},${36 - ((value - min) / range) * 31}`).join(" ");
    const hits = rows.map((row, index) => {
      const cx = (index / (values.length - 1)) * 100, cy = 36 - ((row.value - min) / range) * 31;
      const date = row.point.date || row.point.trade_date || row.point.label || `${index + 1}번째`;
      const label = `${date} · ${number(row.value, 2)}${unit}`;
      return `<circle class="desk-chart-hit" cx="${cx}" cy="${cy}" r="4" ${chartPointAttributes(label)}></circle>`;
    }).join("");
    return `<svg class="desk-sparkline" viewBox="0 0 100 40" preserveAspectRatio="none" aria-label="가격 흐름"><polyline style="stroke:${color}" points="${coordinates}"></polyline>${hits}</svg>`;
  }

  function chartPointAttributes(label) {
    const safeLabel = escapeMarkup(label);
    return `tabindex="0" role="img" aria-label="${safeLabel}" data-chart-tooltip="${safeLabel}"`;
  }

  function chartTooltipEvents() {
    const tooltip = document.createElement("div");
    tooltip.className = "desk-chart-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    document.body.appendChild(tooltip);
    const hide = () => { tooltip.hidden = true; };
    const place = (target, event = null) => {
      const message = target?.dataset?.chartTooltip;
      if (!message) return hide();
      tooltip.textContent = message;
      tooltip.hidden = false;
      const rect = target.getBoundingClientRect();
      const clientX = event?.clientX ?? rect.left + rect.width / 2;
      const clientY = event?.clientY ?? rect.top;
      const width = tooltip.offsetWidth, height = tooltip.offsetHeight;
      tooltip.style.left = `${Math.min(window.innerWidth - width - 10, Math.max(10, clientX + 12))}px`;
      tooltip.style.top = `${Math.max(10, clientY - height - 12)}px`;
    };
    document.addEventListener("pointerover", (event) => { const target = event.target.closest?.("[data-chart-tooltip]"); if (target) place(target, event); });
    document.addEventListener("pointermove", (event) => { const target = event.target.closest?.("[data-chart-tooltip]"); if (target) place(target, event); });
    document.addEventListener("pointerout", (event) => { if (event.target.closest?.("[data-chart-tooltip]")) hide(); });
    document.addEventListener("focusin", (event) => { const target = event.target.closest?.("[data-chart-tooltip]"); if (target) place(target); });
    document.addEventListener("focusout", (event) => { if (event.target.closest?.("[data-chart-tooltip]")) hide(); });
    window.addEventListener("scroll", hide, true);
  }

  function finiteNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function averageNumbers(values) {
    const usable = values.map(finiteNumber).filter((value) => value !== null);
    return usable.length ? usable.reduce((sum, value) => sum + value, 0) / usable.length : null;
  }

  function standardDeviationNumbers(values) {
    const usable = values.map(finiteNumber).filter((value) => value !== null);
    if (usable.length < 2) return null;
    const mean = averageNumbers(usable);
    return Math.sqrt(usable.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / usable.length);
  }

  function clampNumber(value, min, max) { return Math.min(max, Math.max(min, value)); }

  function rebasePeriodReturn(periodReturn, previousPrice, livePrice) {
    const rate = finiteNumber(periodReturn), previous = finiteNumber(previousPrice), next = finiteNumber(livePrice);
    if (rate === null || previous === null || next === null || previous <= 0 || next <= 0) return periodReturn;
    return ((1 + rate / 100) * (next / previous) - 1) * 100;
  }

  function markLiveCell(node, code, field, value, format = field) {
    if (!node || !code) return node;
    node.dataset.liveCode = String(code);
    node.dataset.liveField = field;
    node.dataset.liveFormat = format;
    const parsed = finiteNumber(value);
    if (parsed !== null) node.dataset.rawValue = String(parsed);
    return node;
  }

  function markMarketCell(node, group, code, field, value, format = field) {
    if (!node || !code) return node;
    node.dataset.marketGroup = group;
    node.dataset.marketCode = String(code);
    node.dataset.marketField = field;
    node.dataset.liveFormat = format;
    const parsed = finiteNumber(value);
    if (parsed !== null) node.dataset.rawValue = String(parsed);
    return node;
  }

  function liveCellText(format, value) {
    if (format === "price-won") return `${number(value)}원`;
    if (format === "money") return shortMoney(value);
    if (format === "percent") return percent(value);
    if (format === "change") return `${finiteNumber(value) > 0 ? "+" : ""}${number(value)}`;
    if (format === "number-2") return number(value, 2);
    if (format === "asset-index") return `${number(value, 2)}포인트`;
    if (format === "asset-USD") return `$${number(value, 2)}`;
    return number(value);
  }

  function globalAssetValue(value, unit = "") {
    if (unit === "index") return `${number(value, 2)}포인트`;
    if (String(unit).toUpperCase() === "USD") return `$${number(value, 2)}`;
    return `${number(value, 2)}${unit ? ` ${unit}` : ""}`;
  }

  function animateLiveCellValue(node, previous, next, nextText) {
    if (node._deskLiveAnimationFrame) window.cancelAnimationFrame(node._deskLiveAnimationFrame);
    const rendered = finiteNumber(node.dataset.renderedValue);
    const startValue = rendered ?? previous;
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (startValue === null || startValue === next || reducedMotion) {
      node.textContent = nextText; node.dataset.renderedValue = String(next); node._deskLiveAnimationFrame = 0; return;
    }
    const startedAt = performance.now(), duration = 620;
    const tick = (now) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = startValue + (next - startValue) * eased;
      node.textContent = liveCellText(node.dataset.liveFormat, value); node.dataset.renderedValue = String(value);
      if (progress < 1) node._deskLiveAnimationFrame = window.requestAnimationFrame(tick);
      else { node.textContent = nextText; node.dataset.renderedValue = String(next); node._deskLiveAnimationFrame = 0; }
    };
    node._deskLiveAnimationFrame = window.requestAnimationFrame(tick);
  }

  function updateLiveCell(node, value) {
    const next = finiteNumber(value);
    if (next === null) return;
    const previous = finiteNumber(node.dataset.rawValue);
    const nextText = liveCellText(node.dataset.liveFormat, next);
    node.dataset.rawValue = String(next);
    if (["percent", "change"].includes(node.dataset.liveFormat)) {
      node.classList.remove("desk-cell-positive", "desk-cell-negative");
      const tone = changeClass(next); if (tone) node.classList.add(tone);
    }
    if (node.textContent === nextText && previous === next) return;
    animateLiveCellValue(node, previous, next, nextText);
    node.classList.remove("desk-live-up", "desk-live-down", "desk-live-flat");
    void node.offsetWidth;
    node.classList.add(previous === null || previous === next ? "desk-live-flat" : next > previous ? "desk-live-up" : "desk-live-down");
    node.title = `실시간 갱신 ${new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
  }

  function liveValue(model, field) {
    if (field === "one_month_return") return model.oneMonthReturn;
    if (field === "three_month_return") return model.threeMonthReturn;
    return model.quote?.[field];
  }

  function updateLiveCells(code, model) {
    elements.sheet.querySelectorAll("[data-live-code]").forEach((node) => {
      if (node.dataset.liveCode === String(code)) updateLiveCell(node, liveValue(model, node.dataset.liveField));
    });
  }

  function liveSocketUrl() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${location.host}/ws/quotes`;
  }

  function noteLiveUpdate(payload) {
    const source = payload?.source === "kis_realtime" ? "KIS 실시간" : payload?.source === "kis_rest" ? "KIS 갱신" : "보조 갱신";
    const session = payload?.quote?.market_session_label || "";
    const time = payload?.as_of ? new Date(payload.as_of) : new Date();
    const label = Number.isNaN(time.getTime()) ? new Date().toLocaleTimeString("ko-KR") : time.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setStatus(`${session ? `${session} · ` : ""}${source} · ${label}`);
  }

  function applyLiveQuotePayload(payload) {
    if (payload?.type !== "quote" || !payload.code || !payload.quote) return;
    const model = state.liveQuoteModels.get(String(payload.code));
    if (!model) return;
    const previousPrice = finiteNumber(model.quote?.price), nextPrice = finiteNumber(payload.quote.price);
    if (previousPrice !== null && nextPrice !== null && previousPrice !== nextPrice) {
      model.oneMonthReturn = rebasePeriodReturn(model.oneMonthReturn, previousPrice, nextPrice);
      model.threeMonthReturn = rebasePeriodReturn(model.threeMonthReturn, previousPrice, nextPrice);
    }
    model.quote = { ...(model.quote || {}), ...payload.quote };
    updateLiveCells(payload.code, model);
    if (typeof model.onQuote === "function") model.onQuote(model, payload);
    noteLiveUpdate(payload);
  }

  function liveQuoteCodes() {
    return [...state.liveQuoteModels.keys()].slice(0, 64);
  }

  function sendLiveQuoteSubscriptions() {
    if (state.liveQuoteSocket?.readyState !== WebSocket.OPEN) return;
    state.liveQuoteSocket.send(JSON.stringify({ type: "set", codes: liveQuoteCodes() }));
  }

  function scheduleLiveQuoteFallback(generation = state.liveGeneration, delay = 800) {
    window.clearTimeout(state.liveQuoteFallbackTimer);
    if (generation !== state.liveGeneration || !state.liveQuoteModels.size) return;
    state.liveQuoteFallbackTimer = window.setTimeout(async () => {
      if (generation !== state.liveGeneration || !state.liveQuoteModels.size) return;
      try {
        const codes = liveQuoteCodes();
        const payload = await api(`/stocks/quotes?codes=${encodeURIComponent(codes.join(","))}`);
        (payload.items || []).forEach(applyLiveQuotePayload);
      } catch {
        setStatus("실시간 재연결 중 · 기존 시세 유지");
      }
      if (generation === state.liveGeneration && state.liveQuoteSocket?.readyState !== WebSocket.OPEN) {
        scheduleLiveQuoteFallback(generation, 10000 + Math.floor(Math.random() * 2500));
      }
    }, delay);
  }

  function scheduleLiveQuoteReconnect(generation = state.liveGeneration) {
    window.clearTimeout(state.liveQuoteReconnectTimer);
    if (generation !== state.liveGeneration || !state.liveQuoteModels.size || document.hidden) return;
    const attempt = state.liveQuoteReconnectAttempt++;
    const delay = Math.min(30000, 1000 * (2 ** Math.min(attempt, 5))) + Math.floor(Math.random() * 750);
    setStatus("실시간 재연결 중 · 기존 시세 유지");
    state.liveQuoteReconnectTimer = window.setTimeout(() => connectLiveQuoteStream(generation), delay);
    scheduleLiveQuoteFallback(generation);
  }

  function connectLiveQuoteStream(generation = state.liveGeneration) {
    if (!("WebSocket" in window) || generation !== state.liveGeneration || !state.liveQuoteModels.size || document.hidden) return;
    if (state.liveQuoteSocket && state.liveQuoteSocket.readyState <= WebSocket.OPEN) return;
    window.clearTimeout(state.liveQuoteReconnectTimer);
    const socket = new WebSocket(liveSocketUrl());
    state.liveQuoteSocket = socket;
    socket.onopen = () => {
      if (state.liveQuoteSocket !== socket || generation !== state.liveGeneration) return;
      state.liveQuoteReconnectAttempt = 0;
      window.clearTimeout(state.liveQuoteFallbackTimer);
      sendLiveQuoteSubscriptions();
      setStatus("실시간 연결 완료");
    };
    socket.onmessage = (event) => {
      let payload; try { payload = JSON.parse(event.data); } catch { return; }
      if (payload?.type === "quote") applyLiveQuotePayload(payload);
      else if (payload?.type === "error") setStatus("실시간 연결 지연 · 기존 시세 유지");
    };
    socket.onclose = () => {
      if (state.liveQuoteSocket === socket) state.liveQuoteSocket = null;
      if (generation !== state.liveGeneration || !state.liveQuoteModels.size) return;
      scheduleLiveQuoteReconnect(generation);
    };
    socket.onerror = () => socket.close();
  }

  function syncLiveQuoteStream() {
    if (!state.liveQuoteModels.size) return;
    if (state.liveQuoteSocket?.readyState === WebSocket.OPEN) sendLiveQuoteSubscriptions();
    else connectLiveQuoteStream();
  }

  function registerLiveQuote(code, seed = {}) {
    const normalized = String(code || ""); if (!normalized) return;
    const current = state.liveQuoteModels.get(normalized) || { quote: {}, oneMonthReturn: null, threeMonthReturn: null, onQuote: null };
    current.quote = { ...current.quote, ...(seed.quote || {}) };
    if (finiteNumber(seed.momentum?.one_month_return) !== null) current.oneMonthReturn = seed.momentum.one_month_return;
    if (finiteNumber(seed.momentum?.three_month_return) !== null) current.threeMonthReturn = seed.momentum.three_month_return;
    if (seed.onQuote) current.onQuote = seed.onQuote;
    state.liveQuoteModels.set(normalized, current);
    syncLiveQuoteStream();
  }

  function updateMarketCells(group, items) {
    const byCode = new Map((items || []).map((item) => [String(item.code || item.name || item.label), item]));
    elements.sheet.querySelectorAll("[data-market-group]").forEach((node) => {
      if (node.dataset.marketGroup !== group) return;
      const item = byCode.get(node.dataset.marketCode); if (!item) return;
      updateLiveCell(node, item[node.dataset.marketField]);
    });
  }

  function startHomeMarketRefresh() {
    const generation = state.liveGeneration;
    const refresh = async () => {
      if (generation !== state.liveGeneration || state.active !== "home") return;
      try {
        const [indices, globalAssets] = await Promise.all([api("/market/indices?limit=30"), api("/market/global-assets?limit=30")]);
        updateMarketCells("indices", indices.items); updateMarketCells("assets", globalAssets.items); noteLiveUpdate({ source: "kis_rest", as_of: new Date().toISOString() });
      } catch { setStatus("종목 실시간 연결 · 시장지수 갱신 지연"); }
      if (generation === state.liveGeneration && state.active === "home") state.liveMarketRefreshTimer = window.setTimeout(refresh, 15000);
    };
    state.liveMarketRefreshTimer = window.setTimeout(refresh, 15000);
  }

  function pauseLiveQuoteStream() {
    window.clearTimeout(state.liveQuoteReconnectTimer); state.liveQuoteReconnectTimer = 0;
    window.clearTimeout(state.liveQuoteFallbackTimer); state.liveQuoteFallbackTimer = 0;
    if (state.liveQuoteSocket) {
      state.liveQuoteSocket.onclose = null;
      state.liveQuoteSocket.close();
      state.liveQuoteSocket = null;
    }
  }

  function resetLiveUpdates() {
    state.liveGeneration += 1;
    window.clearTimeout(state.liveMarketRefreshTimer); state.liveMarketRefreshTimer = 0;
    pauseLiveQuoteStream();
    state.liveQuoteReconnectAttempt = 0;
    state.liveQuoteModels.clear();
  }

  function computeDesktopChartAnalysis(prices) {
    const rows = (prices || []).filter((row) => finiteNumber(row?.close) !== null).slice().reverse();
    const closes = rows.map((row) => finiteNumber(row.close));
    const current = closes.at(-1) ?? null;
    if (current === null || rows.length < 30) {
      return { available: false, reason: "5일·10일 예상 범위를 계산하려면 최소 30거래일의 가격이 필요합니다." };
    }

    const chartRows = rows.map((row, index) => ({
      ...row,
      close: closes[index],
      ma5: index >= 4 ? averageNumbers(closes.slice(index - 4, index + 1)) : null,
      ma10: index >= 9 ? averageNumbers(closes.slice(index - 9, index + 1)) : null,
      ma20: index >= 19 ? averageNumbers(closes.slice(index - 19, index + 1)) : null,
    }));
    const returns = [];
    for (let index = 1; index < closes.length; index += 1) {
      if (closes[index - 1] > 0 && closes[index] > 0) returns.push(Math.log(closes[index] / closes[index - 1]));
    }
    const shortDrift = averageNumbers(returns.slice(-5)) ?? 0;
    const mediumDrift = averageNumbers(returns.slice(-20)) ?? 0;
    const ma5 = chartRows.at(-1).ma5;
    const ma10 = chartRows.at(-1).ma10;
    const ma20 = chartRows.at(-1).ma20;
    const trendGap = ma5 && ma20 ? (ma5 - ma20) / ma20 : 0;
    const trueRanges = [];
    for (let index = Math.max(1, rows.length - 14); index < rows.length; index += 1) {
      const high = finiteNumber(rows[index].high) ?? closes[index];
      const low = finiteNumber(rows[index].low) ?? closes[index];
      const previous = closes[index - 1];
      trueRanges.push(Math.max(high - low, Math.abs(high - previous), Math.abs(low - previous)) / previous);
    }
    const dailyDrift = clampNumber(shortDrift * .48 + mediumDrift * .38 + trendGap * .014, -.025, .025);
    const returnVolatility = standardDeviationNumbers(returns.slice(-20)) ?? 0;
    const atrVolatility = averageNumbers(trueRanges) ?? 0;
    const dailyVolatility = clampNumber(returnVolatility * .72 + atrVolatility * .28, .005, .06);
    const points = [];
    for (let day = 1; day <= 10; day += 1) {
      const center = current * Math.exp(dailyDrift * day);
      const band = Math.min(.35, 1.28 * dailyVolatility * Math.sqrt(day));
      points.push({ day, center, lower: center * (1 - band), upper: center * (1 + band) });
    }
    const buildForecast = (days) => {
      const forecastPoints = points.slice(0, days);
      const expected = forecastPoints.at(-1).center;
      const expectedRate = ((expected - current) / current) * 100;
      const trendAligned = (dailyDrift >= 0 && ma20 && current >= ma20) || (dailyDrift < 0 && ma20 && current < ma20);
      const confidenceScore = clampNumber(48 + Math.min(18, rows.length / 10) + (trendAligned ? 10 : 0) - Math.max(0, dailyVolatility * 240), 35, 82);
      return {
        days,
        points: forecastPoints,
        expected,
        expectedRate,
        confidenceScore,
        confidence: confidenceScore >= 68 ? "높음" : confidenceScore >= 52 ? "보통" : "낮음",
        direction: expectedRate > 1 ? "상승 우위" : expectedRate < -1 ? "하락 우위" : "횡보 가능성",
      };
    };
    const recent = rows.slice(-20);
    return {
      available: true,
      rows: chartRows,
      current,
      ma5,
      ma10,
      ma20,
      support: Math.min(...recent.map((row) => finiteNumber(row.low) ?? finiteNumber(row.close))),
      resistance: Math.max(...recent.map((row) => finiteNumber(row.high) ?? finiteNumber(row.close))),
      forecast5: buildForecast(5),
      forecast10: buildForecast(10),
    };
  }

  function desktopForecastChartSvg(analysis) {
    if (!analysis?.available) return "";
    const actual = analysis.rows.slice(-90);
    const future = analysis.forecast10.points;
    const width = 920, height = 330, left = 36, right = 66, top = 22, bottom = 48;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const values = [
      ...actual.flatMap((row) => [row.close, row.ma5, row.ma10].filter((value) => value !== null)),
      ...future.flatMap((point) => [point.lower, point.center, point.upper]),
    ];
    let min = Math.min(...values), max = Math.max(...values);
    const padding = Math.max(1, (max - min) * .1); min -= padding; max += padding;
    const span = max - min || 1, totalSteps = actual.length - 1 + future.length;
    const x = (step) => left + (step / totalSteps) * plotWidth;
    const y = (value) => top + ((max - value) / span) * plotHeight;
    const path = (points) => points.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ");
    const actualPoints = actual.map((row, index) => [x(index), y(row.close)]);
    const maPoints = (key) => actual.map((row, index) => row[key] === null ? null : [x(index), y(row[key])]).filter(Boolean);
    const currentIndex = actual.length - 1, currentX = x(currentIndex), currentY = y(analysis.current);
    const centerPoints = [[currentX, currentY], ...future.map((point) => [x(currentIndex + point.day), y(point.center)])];
    const fiveDayPoints = centerPoints.slice(0, 6);
    const upperPoints = [[currentX, currentY], ...future.map((point) => [x(currentIndex + point.day), y(point.upper)])];
    const lowerPoints = [[currentX, currentY], ...future.map((point) => [x(currentIndex + point.day), y(point.lower)])];
    const bandPoints = [...upperPoints, ...lowerPoints.slice().reverse()];
    const grids = [0, .333, .666, 1].map((ratio) => {
      const gridY = top + plotHeight * ratio, value = max - span * ratio;
      return `<line x1="${left}" y1="${gridY.toFixed(1)}" x2="${width - right}" y2="${gridY.toFixed(1)}"></line><text x="${width - right + 8}" y="${(gridY + 4).toFixed(1)}">${number(value)}</text>`;
    }).join("");
    const day5 = future[4], day10 = future[9], day5X = x(currentIndex + 5), day10X = x(totalSteps);
    const actualHits = actual.map((row, index) => { const label = `${row.trade_date || row.date || "최근"} · 실제 ${number(row.close)}원${row.ma5 ? ` · 5일선 ${number(row.ma5)}원` : ""}${row.ma10 ? ` · 10일선 ${number(row.ma10)}원` : ""}`; return `<circle class="desk-chart-hit" cx="${x(index).toFixed(1)}" cy="${y(row.close).toFixed(1)}" r="7" ${chartPointAttributes(label)}></circle>`; }).join("");
    const forecastHits = future.map((point) => { const label = `${point.day}일 후 · 예상 ${number(point.center)}원 · 범위 ${number(point.lower)}~${number(point.upper)}원`; return `<circle class="desk-chart-hit" cx="${x(currentIndex + point.day).toFixed(1)}" cy="${y(point.center).toFixed(1)}" r="8" ${chartPointAttributes(label)}></circle>`; }).join("");
    return `<svg class="desk-forecast-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="실제 가격, 5일선, 10일선과 5일·10일 예상 범위">
      <g class="desk-forecast-grid">${grids}</g>
      <rect class="desk-forecast-future-zone" x="${currentX.toFixed(1)}" y="${top}" width="${(width - right - currentX).toFixed(1)}" height="${plotHeight}"></rect>
      <path class="desk-forecast-band" d="${path(bandPoints)} Z"></path>
      <path class="desk-forecast-ma5" d="${path(maPoints("ma5"))}"></path>
      <path class="desk-forecast-ma10" d="${path(maPoints("ma10"))}"></path>
      <path class="desk-forecast-actual" d="${path(actualPoints)}"></path>
      <path class="desk-forecast-10" d="${path(centerPoints)}"></path>
      <path class="desk-forecast-5" d="${path(fiveDayPoints)}"></path>
      <line class="desk-forecast-now" x1="${currentX.toFixed(1)}" y1="${top}" x2="${currentX.toFixed(1)}" y2="${top + plotHeight}"></line>
      <circle class="desk-forecast-current-dot" cx="${currentX.toFixed(1)}" cy="${currentY.toFixed(1)}" r="5"></circle>
      <circle class="desk-forecast-5-dot" cx="${day5X.toFixed(1)}" cy="${y(day5.center).toFixed(1)}" r="5"></circle>
      <circle class="desk-forecast-10-dot" cx="${day10X.toFixed(1)}" cy="${y(day10.center).toFixed(1)}" r="5"></circle>
      ${actualHits}${forecastHits}
      <text class="desk-forecast-axis-label" x="${left}" y="${height - 12}">최근 흐름</text>
      <text class="desk-forecast-axis-label current" x="${currentX.toFixed(1)}" y="${height - 12}" text-anchor="middle">현재</text>
      <text class="desk-forecast-axis-label day5" x="${day5X.toFixed(1)}" y="${height - 27}" text-anchor="middle">5일 후</text>
      <text class="desk-forecast-axis-label day10" x="${day10X.toFixed(1)}" y="${height - 12}" text-anchor="end">10일 후</text>
    </svg>`;
  }

  function financialBarChart(series, metric = "operating_profit", unit = "억원") {
    const rows = (series || []).filter((row) => Number.isFinite(Number(row?.[metric]))).slice(-8);
    if (!rows.length) return "";
    const values = rows.map((row) => Number(row[metric]));
    const min = Math.min(0, ...values), max = Math.max(0, ...values), span = max - min || 1;
    const width = 760, height = 245, left = 55, right = 18, top = 20, bottom = 205, plot = bottom - top;
    const y = (value) => top + ((max - value) / span) * plot, baseline = y(0), slot = (width - left - right) / rows.length, barWidth = Math.min(54, slot * .58);
    const grid = Array.from({ length: 4 }, (_, index) => { const ratio = index / 3, gy = top + ratio * plot, value = max - ratio * span; return `<line class="desk-fin-grid" x1="${left}" y1="${gy}" x2="${width-right}" y2="${gy}"></line><text class="desk-fin-label" x="${left-7}" y="${gy+4}" text-anchor="end">${financialSeriesAmount(value, unit, true)}</text>`; }).join("");
    const metricLabel = { revenue: "매출액", operating_profit: "영업이익", net_income: "순이익" }[metric] || metric;
    const bars = rows.map((row, index) => { const value = Number(row[metric]), x = left + slot * index + (slot - barWidth) / 2, valueY = y(value), barY = value >= 0 ? valueY : baseline, barHeight = Math.max(2, Math.abs(valueY - baseline)), label = `${financialPeriodLabel(row.period, row.estimated)} · ${metricLabel} ${financialSeriesAmount(value, unit)}`; return `<g><rect class="desk-fin-bar${row.estimated ? " is-estimate" : ""}" x="${x}" y="${barY}" width="${barWidth}" height="${barHeight}" rx="3" ${chartPointAttributes(label)}></rect><text class="desk-fin-value" x="${x + barWidth/2}" y="${Math.max(12, barY-6)}" text-anchor="middle">${financialSeriesAmount(value, unit, true)}</text></g>`; }).join("");
    return `<svg class="desk-financial-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${metricLabel} 실적 그래프">${grid}<line class="desk-fin-baseline" x1="${left}" y1="${baseline}" x2="${width-right}" y2="${baseline}"></line>${bars}</svg>`;
  }

  function marginLineChart(series) {
    const rows = (series || []).filter((row) => Number.isFinite(Number(row?.operating_margin)) || Number.isFinite(Number(row?.net_margin))).slice(-8);
    if (rows.length < 2) return "";
    const all = rows.flatMap((row) => [Number(row.operating_margin), Number(row.net_margin)]).filter(Number.isFinite), min = Math.min(0, ...all), max = Math.max(0, ...all), span = max - min || 1;
    const width = 380, height = 245, left = 40, right = 15, top = 20, bottom = 205, plotWidth = width-left-right, plotHeight = bottom-top;
    const point = (value, index) => `${left + index * (plotWidth / (rows.length - 1))},${top + ((max - value) / span) * plotHeight}`;
    const path = (key) => rows.map((row, index) => Number.isFinite(Number(row[key])) ? point(Number(row[key]), index) : null).filter(Boolean).join(" ");
    const hits = rows.flatMap((row, index) => [["operating_margin", "영업이익률"], ["net_margin", "순이익률"]].map(([key, metricLabel]) => { const label = `${financialPeriodLabel(row.period, row.estimated)} · ${metricLabel} ${number(row[key], 1)}%`; return Number.isFinite(Number(row[key])) ? `<circle class="desk-chart-hit" cx="${left + index * (plotWidth / (rows.length - 1))}" cy="${top + ((max - Number(row[key])) / span) * plotHeight}" r="8" ${chartPointAttributes(label)}></circle>` : ""; })).join("");
    return `<svg class="desk-financial-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="분기별 영업이익률과 순이익률 그래프"><line class="desk-fin-grid" x1="${left}" y1="${bottom}" x2="${width-right}" y2="${bottom}"></line><polyline class="desk-margin-line is-operating" points="${path("operating_margin")}"></polyline><polyline class="desk-margin-line is-net" points="${path("net_margin")}"></polyline>${hits}<text class="desk-margin-legend" x="45" y="14">● 영업이익률</text><text class="desk-margin-legend is-net" x="135" y="14">● 순이익률</text></svg>`;
  }

  function sectorMarginLineChart(payload) {
    const periods = Array.isArray(payload?.periods) ? payload.periods.map(String) : [];
    const companies = (payload?.companies || []).map((company) => ({
      ...company,
      points: (company.points || []).filter((point) => Number.isFinite(Number(point?.operating_margin))),
    })).filter((company) => company.points.length >= 2);
    if (periods.length < 2 || !companies.length) return "";
    const values = companies.flatMap((company) => company.points.map((point) => Number(point.operating_margin)));
    let min = Math.min(...values), max = Math.max(...values);
    const padding = Math.max(3, (max - min) * .12); min -= padding; max += padding;
    const span = max - min || 1, width = 780, height = 286, left = 58, right = 72, top = 22, bottom = 244;
    const plotWidth = width - left - right, plotHeight = bottom - top;
    const x = (period) => left + Math.max(0, periods.indexOf(String(period))) * (plotWidth / Math.max(1, periods.length - 1));
    const y = (value) => top + ((max - value) / span) * plotHeight;
    const peerColors = ["#4f7fdc", "#3f8a70", "#a46b3b", "#7858c8", "#5f6f82", "#c15c90"];
    let peerIndex = 0;
    const grids = Array.from({ length: 5 }, (_, index) => {
      const ratio = index / 4, gridY = top + ratio * plotHeight, value = max - ratio * span;
      return `<line class="desk-sector-grid" x1="${left}" y1="${gridY.toFixed(1)}" x2="${width - right}" y2="${gridY.toFixed(1)}"></line><text class="desk-sector-axis" x="${left - 9}" y="${(gridY + 4).toFixed(1)}" text-anchor="end">${number(value, 0)}%</text>`;
    }).join("");
    const lines = companies.map((company) => {
      const color = company.is_target ? "#d62f3f" : peerColors[peerIndex++ % peerColors.length];
      const points = company.points.map((point) => [x(point.year || point.period), y(Number(point.operating_margin)), Number(point.operating_margin)]);
      const path = points.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ");
      const dots = points.map((point, index) => { const label = `${company.name} · ${company.points[index]?.year || company.points[index]?.period || ""} · 영업이익률 ${number(point[2], 1)}%`; return `<circle cx="${point[0].toFixed(1)}" cy="${point[1].toFixed(1)}" r="${company.is_target ? 5 : 3.3}" style="stroke:${color}"></circle><circle class="desk-chart-hit" cx="${point[0].toFixed(1)}" cy="${point[1].toFixed(1)}" r="9" ${chartPointAttributes(label)}></circle>`; }).join("");
      const labels = points.map((point, index) => {
        if (!company.is_target && index !== points.length - 1) return "";
        const anchor = index === points.length - 1 ? "start" : "middle", dx = index === points.length - 1 ? 8 : 0;
        return `<text class="desk-sector-value${company.is_target ? " is-target" : ""}" x="${(point[0] + dx).toFixed(1)}" y="${Math.max(13, point[1] - 9).toFixed(1)}" text-anchor="${anchor}" style="fill:${color}">${number(point[2], 1)}%</text>`;
      }).join("");
      return `<g class="desk-sector-series${company.is_target ? " is-target" : ""}" aria-label="${escapeMarkup(company.name)}"><path d="${path}" style="stroke:${color}"></path>${dots}${labels}</g>`;
    }).join("");
    return `<svg class="desk-sector-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="동종 업계 기업의 연도별 영업이익률 추이">${grids}${lines}</svg>`;
  }

  function sgaDetailText(category) {
    return (category?.details || []).map((detail) => `${text(detail.name)} ${financialSeriesAmount(detail.amount, "억원", true)}`).join(" · ");
  }

  function detailPriceRows(prices, intraday, period, quote) {
    if (period === "1D") {
      return (intraday?.points || []).map((point) => ({
        date: String(point.trade_time || ""),
        label: String(point.trade_time || "").replace(/^(\d{2})(\d{2}).*$/, "$1:$2"),
        close: finiteNumber(point.price),
        volume: finiteNumber(point.volume),
      })).filter((row) => row.date && row.close !== null);
    }
    const counts = { "1M": 22, "3M": 66, "6M": 132, "1Y": 264 };
    return normalizePriceRows(prices, quote).slice(-(counts[period] || 22));
  }

  function detailPriceChartSvg(prices, intraday, period, quote) {
    const rows = detailPriceRows(prices, intraday, period, quote);
    if (rows.length < 2) return "";
    const width = 760, height = 250, left = 52, right = 18, top = 18, priceBottom = 170, volumeTop = 184, bottom = 220;
    const values = rows.map((row) => Number(row.close));
    let min = Math.min(...values), max = Math.max(...values);
    const padding = Math.max(1, (max - min) * .08); min -= padding; max += padding;
    const x = (index) => left + (index / Math.max(1, rows.length - 1)) * (width - left - right);
    const y = (value) => top + ((max - value) / (max - min || 1)) * (priceBottom - top);
    const path = rows.map((row, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(row.close).toFixed(1)}`).join(" ");
    const maxVolume = Math.max(1, ...rows.map((row) => Number(row.volume || 0)));
    const volumeSlot = (width - left - right) / Math.max(1, rows.length);
    const volumeBars = rows.map((row, index) => {
      const barHeight = Math.max(1, (Number(row.volume || 0) / maxVolume) * (bottom - volumeTop));
      return `<rect class="desk-price-volume" x="${(left + index * volumeSlot).toFixed(1)}" y="${(bottom - barHeight).toFixed(1)}" width="${Math.max(.7, volumeSlot * .72).toFixed(1)}" height="${barHeight.toFixed(1)}"></rect>`;
    }).join("");
    const hitStep = Math.max(1, Math.ceil(rows.length / 90));
    const hits = rows.map((row, index) => {
      if (index % hitStep && index !== rows.length - 1) return "";
      const date = period === "1D" ? row.label : dateLabel(row.date);
      const label = `${date} · ${number(row.close)}원${row.volume === null ? "" : ` · 거래량 ${number(row.volume)}주`}`;
      return `<circle class="desk-chart-hit" cx="${x(index).toFixed(1)}" cy="${y(row.close).toFixed(1)}" r="8" ${chartPointAttributes(label)}></circle>`;
    }).join("");
    const grid = [0, .5, 1].map((ratio) => {
      const gridY = top + (priceBottom - top) * ratio, value = max - (max - min) * ratio;
      return `<line class="desk-price-grid" x1="${left}" y1="${gridY.toFixed(1)}" x2="${width-right}" y2="${gridY.toFixed(1)}"></line><text class="desk-price-axis" x="${left-7}" y="${(gridY+4).toFixed(1)}" text-anchor="end">${number(value)}</text>`;
    }).join("");
    return `<svg class="desk-price-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${period} 실제 가격과 거래량 흐름">${grid}<path class="desk-price-area" d="${path} L${x(rows.length-1).toFixed(1)},${priceBottom} L${x(0).toFixed(1)},${priceBottom} Z"></path><path class="desk-price-line" d="${path}"></path>${volumeBars}${hits}</svg>`;
  }

  function renderDesktopDetailHeader(root, code, dashboard, prices, intraday) {
    const quote = dashboard.quote || {}, momentum = dashboard.momentum || {};
    sheetTitle(root, `${dashboard.name} · ${dashboard.code}`, `${dashboard.market} · ${dateLabel(dashboard.as_of)}`);
    detailTab(root, code, "summary", "종목홈", 0);
    detailTab(root, code, "company", "기업분석", 2);
    detailTab(root, code, "strategy", "AI 시그널", 4);
    section(root, "실시간 시세", 0, 3, 6);
    headers(root, ["현재가(원)", "전일대비(원)", "등락률(%)"], 0, 4, [2,2,2]);
    markLiveCell(addCell(root, `${number(quote.price)}원`, 0, 5, { cols: 2, className: "desk-cell-number desk-cell-quote-price" }), code, "price", quote.price, "price-won");
    markLiveCell(addCell(root, number(quote.change_value), 2, 5, { cols: 2, className: `desk-cell-number ${changeClass(quote.change_value)}` }), code, "change_value", quote.change_value, "change");
    markLiveCell(addCell(root, percent(quote.change_rate), 4, 5, { cols: 2, className: `desk-cell-number ${changeClass(quote.change_rate)}` }), code, "change_rate", quote.change_rate, "percent");
    headers(root, ["거래량(주)", "거래대금(원)", "시가총액(원)", "전일 종가(원)"], 0, 7, [1,2,2,1]);
    markLiveCell(addCell(root, number(quote.volume), 0, 8, { className: "desk-cell-number" }), code, "volume", quote.volume, "count");
    markLiveCell(addCell(root, shortMoney(quote.trading_value), 1, 8, { cols: 2, className: "desk-cell-number" }), code, "trading_value", quote.trading_value, "money");
    addCell(root, shortMoney(quote.market_cap), 3, 8, { cols: 2, className: "desk-cell-number" });
    addCell(root, previousClose(quote) === null ? "-" : `${number(previousClose(quote))}원`, 5, 8, { className: "desk-cell-number" });
    const preMarket = finiteNumber(quote.pre_market_price);
    addCell(root, preMarket === null ? "장전 시세 없음" : `장전 ${number(preMarket)}원 · ${percent(quote.pre_market_change_rate)}`, 0, 10, { cols: 3, className: "desk-cell-muted" });
    addCell(root, `1개월 ${percent(momentum.one_month_return)} · 3개월 ${percent(momentum.three_month_return)}`, 3, 10, { cols: 3, className: "desk-cell-muted desk-cell-number" });

    section(root, "가격 흐름 · 실제 가격과 거래량", 6, 3, 6);
    const period = state.detailPricePeriods.get(code) || "1D";
    [["1D","1일"],["1M","1개월"],["3M","3개월"],["6M","6개월"],["1Y","1년"]].forEach(([id, label], index) => detailOptionButton(root, code, state.detailPricePeriods, "1D", id, label, 6 + index, 4));
    const chart = detailPriceChartSvg(prices, intraday, period, quote);
    addCell(root, chart || (period === "1D" ? intraday?.message : "가격 데이터가 부족합니다."), 6, 5, { cols: 6, rows: 6, html: Boolean(chart), className: chart ? "desk-cell-chart" : "desk-cell-status" });
    addCell(root, `${period === "1D" ? intraday?.source || "분봉 데이터" : "일별 종가"} · 마우스 또는 키보드 포커스로 상세값 확인`, 6, 11, { cols: 6, className: "desk-cell-muted" });
    return 13;
  }

  function groupInvestorFlows(flows = [], amountKey = "net_buy_value") {
    const grouped = new Map();
    for (const flow of Array.isArray(flows) ? flows : []) {
      const date = String(flow?.trade_date || ""), value = finiteNumber(flow?.[amountKey]);
      if (!date || value === null) continue;
      const row = grouped.get(date) || { date, foreign: 0, institution: 0 };
      const type = String(flow.investor_type || "");
      if (type.includes("외국")) row.foreign += value;
      if (type.includes("기관")) row.institution += value;
      grouped.set(date, row);
    }
    return [...grouped.values()].sort((a, b) => a.date.localeCompare(b.date)).map((row) => ({ ...row, personal: -(row.foreign + row.institution) }));
  }

  function investorFlowChartSvg(flows, options = {}) {
    const rows = groupInvestorFlows(flows, options.amountKey || "net_buy_value").slice(-(options.count || 7));
    if (rows.length < 2) return "";
    const width = options.width || 760, height = options.height || 250, left = 64, right = 22, top = 22, bottom = height - 42;
    const keys = ["personal", "foreign", "institution"], labels = { personal: "개인(추정)", foreign: "외국인", institution: "기관" };
    const maxAbs = Math.max(1, ...rows.flatMap((row) => keys.map((key) => Math.abs(row[key]))));
    const x = (index) => left + index * ((width-left-right) / Math.max(1, rows.length-1));
    const y = (value) => top + ((maxAbs - value) / (maxAbs * 2)) * (bottom-top);
    const colors = { personal: "#8b5cf6", foreign: "#d93025", institution: "#1a73e8" };
    const grid = [1,.5,0,-.5,-1].map((ratio) => `<line class="desk-flow-grid${ratio === 0 ? " is-zero" : ""}" x1="${left}" y1="${y(maxAbs*ratio).toFixed(1)}" x2="${width-right}" y2="${y(maxAbs*ratio).toFixed(1)}"></line><text class="desk-flow-axis" x="${left-7}" y="${(y(maxAbs*ratio)+4).toFixed(1)}" text-anchor="end">${shortMoney(maxAbs*ratio)}</text>`).join("");
    const series = keys.map((key) => {
      const path = rows.map((row,index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(row[key]).toFixed(1)}`).join(" ");
      const dots = rows.map((row,index) => `<circle style="stroke:${colors[key]}" cx="${x(index).toFixed(1)}" cy="${y(row[key]).toFixed(1)}" r="3.5"></circle><circle class="desk-chart-hit" cx="${x(index).toFixed(1)}" cy="${y(row[key]).toFixed(1)}" r="9" ${chartPointAttributes(`${dateLabel(row.date)} · ${labels[key]} ${signedMoney(row[key])}`)}></circle>`).join("");
      return `<path class="desk-flow-line" style="stroke:${colors[key]}" d="${path}"></path>${dots}`;
    }).join("");
    return `<svg class="desk-flow-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 ${rows.length}거래일 개인 추정, 외국인, 기관 순매수 비교">${grid}${series}<text class="desk-flow-legend personal" x="${left}" y="14">● 개인(추정)</text><text class="desk-flow-legend foreign" x="${left+90}" y="14">● 외국인</text><text class="desk-flow-legend institution" x="${left+155}" y="14">● 기관</text></svg>`;
  }

  function investorHistoryRows(flows, mode, period) {
    const counts = { "3M": 66, "6M": 132, "1Y": 264 };
    const rows = groupInvestorFlows(flows, "net_buy_volume").slice(-(counts[period] || 66));
    if (mode !== "cumulative") return rows;
    let foreign = 0, institution = 0;
    return rows.map((row) => ({ ...row, foreign: foreign += row.foreign, institution: institution += row.institution, personal: -(foreign + institution) }));
  }

  function investorHistoryChartSvg(flows, mode, period) {
    const rows = investorHistoryRows(flows, mode, period);
    if (rows.length < 2) return "";
    const sampleStep = Math.max(1, Math.ceil(rows.length / 90));
    const sampled = rows.filter((_, index) => index % sampleStep === 0 || index === rows.length - 1);
    return investorFlowChartSvg(sampled.flatMap((row) => [
      { trade_date: row.date, investor_type: "외국인", net_buy_volume: row.foreign },
      { trade_date: row.date, investor_type: "기관합계", net_buy_volume: row.institution },
    ]), { amountKey: "net_buy_volume", count: sampled.length, height: 285 });
  }

  const DETAIL_KEYWORD_STOPWORDS = new Set(["관련","대한","위한","통해","최근","전망","주가","증권","투자","리포트","뉴스","공시","분석","기업","시장","종목","이번","올해","내년","상승","하락","강세","약세","확대","감소","증가","발표","기준","가능","예상","코스피","코스닥","the","and","with","for","from"]);

  function detailKeywords(dashboard, context) {
    const texts = [dashboard.company_profile?.industry, dashboard.company_profile?.sector,
      ...(context.research_reports || []).map((row) => row.title),
      ...(context.disclosures || []).map((row) => row.report_name || row.title),
      ...(context.news_items || []).map((row) => row.title)].filter(Boolean);
    const stockName = String(dashboard.name || "").toLowerCase(), counts = new Map();
    for (const source of texts) {
      for (const raw of String(source).match(/[가-힣A-Za-z0-9]{2,}/g) || []) {
        const normalized = raw.toLowerCase();
        if (normalized === stockName || DETAIL_KEYWORD_STOPWORDS.has(normalized) || /^\d+$/.test(raw)) continue;
        counts.set(raw, (counts.get(raw) || 0) + 1);
      }
    }
    return [...counts.entries()].sort((a,b) => b[1]-a[1] || b[0].length-a[0].length).slice(0,10).map(([label,count]) => ({ label,count }));
  }

  function recentDisclosureRows(dashboard, disclosures) {
    const reference = String(dashboard.quote?.trade_date || dashboard.as_of || "").slice(0,10);
    const referenceDate = /^\d{4}-\d{2}-\d{2}$/.test(reference) ? new Date(`${reference}T00:00:00`) : new Date();
    const cutoff = new Date(referenceDate); cutoff.setDate(cutoff.getDate() - 30);
    const seen = new Set();
    return (disclosures || []).filter((row) => {
      const date = new Date(`${String(row.published_at || "").slice(0,10)}T00:00:00`), key = String(row.external_id || row.detail_url || row.id || "");
      if (!key || seen.has(key) || Number.isNaN(date.getTime()) || date < cutoff || date > referenceDate) return false;
      seen.add(key); return true;
    }).sort((a,b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
  }

  function dartCompanyUrl(dashboard, disclosures) {
    const params = new URLSearchParams({ textCrpNm: dashboard.name || dashboard.code, autoSearch: "Y" });
    const corpCode = (disclosures || []).find((row) => row.corp_code)?.corp_code;
    if (corpCode) params.set("textCrpCik", corpCode);
    return `https://dart.fss.or.kr/dsab001/main.do?${params.toString()}`;
  }

  function reportHistoryRows(context) {
    return (context.research_reports || []).map((row) => ({ ...row, date: String(row.published_at || "").slice(0,10), target: finiteNumber(row.target_price) })).filter((row) => row.date).sort((a,b) => a.date.localeCompare(b.date));
  }

  function reportHistoryChartSvg(context, prices, quote, mode) {
    const reports = reportHistoryRows(context);
    const width = 760, height = 280, left = 58, right = 28, top = 24, bottom = 230;
    if (mode === "issuance") {
      const monthly = new Map();
      reports.forEach((row) => monthly.set(row.date.slice(0,7), (monthly.get(row.date.slice(0,7)) || 0) + 1));
      const rows = [...monthly].slice(-6).map(([month,count]) => ({ month,count }));
      if (!rows.length) return "";
      const max = Math.max(1,...rows.map((row) => row.count)), slot = (width-left-right)/rows.length, barWidth = Math.min(60,slot*.55);
      const bars = rows.map((row,index) => { const h = row.count/max*(bottom-top), x = left+slot*index+(slot-barWidth)/2, y=bottom-h; return `<rect class="desk-report-bar" x="${x}" y="${y}" width="${barWidth}" height="${h}" rx="4" ${chartPointAttributes(`${row.month.replace("-", ".")} · 리포트 ${row.count}건`)}></rect><text class="desk-report-value" x="${x+barWidth/2}" y="${Math.max(14,y-7)}" text-anchor="middle">${row.count}건</text>`; }).join("");
      return `<svg class="desk-report-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="월별 리포트 발행 추이"><line class="desk-fin-baseline" x1="${left}" y1="${bottom}" x2="${width-right}" y2="${bottom}"></line>${bars}</svg>`;
    }
    if (mode === "broker") {
      const counts = new Map(); reports.forEach((row) => counts.set(row.broker_name || "증권사", (counts.get(row.broker_name || "증권사") || 0)+1));
      const rows = [...counts].map(([broker,count]) => ({broker,count})).sort((a,b) => b.count-a.count).slice(0,8);
      if (!rows.length) return "";
      const max = Math.max(...rows.map((row)=>row.count),1), rowHeight=(bottom-top)/rows.length;
      const bars = rows.map((row,index) => { const y=top+index*rowHeight, barWidth=(row.count/max)*(width-left-right-150); return `<text class="desk-price-axis" x="${left}" y="${y+15}">${escapeMarkup(row.broker)}</text><rect class="desk-report-broker" x="${left+120}" y="${y+3}" width="${barWidth}" height="14" rx="3" ${chartPointAttributes(`${row.broker} · 리포트 ${row.count}건`)}></rect><text class="desk-report-value" x="${left+128+barWidth}" y="${y+15}">${row.count}건</text>`; }).join("");
      return `<svg class="desk-report-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="증권사별 리포트 발행 건수">${bars}</svg>`;
    }
    const priceRows = normalizePriceRows(prices, quote).slice(-132), targets = reports.filter((row) => row.target !== null && row.target > 0);
    if (priceRows.length < 2) return "";
    const values = [...priceRows.map((row)=>row.close),...targets.map((row)=>row.target)], rawMin=Math.min(...values), rawMax=Math.max(...values), pad=Math.max(1,(rawMax-rawMin)*.08), min=Math.max(0,rawMin-pad), max=rawMax+pad;
    const x=(index)=>left+index*((width-left-right)/Math.max(1,priceRows.length-1)), y=(value)=>top+((max-value)/(max-min||1))*(bottom-top);
    const pricePath=priceRows.map((row,index)=>`${index?"L":"M"}${x(index).toFixed(1)},${y(row.close).toFixed(1)}`).join(" ");
    let currentTarget=null; const targetPoints=[];
    priceRows.forEach((row,index)=>{ targets.filter((report)=>report.date<=row.date).forEach((report)=>{ currentTarget=report.target; }); if(currentTarget!==null) targetPoints.push([x(index),y(currentTarget),currentTarget]); });
    const targetPath=targetPoints.map((point,index)=>`${index?"L":"M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ");
    const hits=priceRows.filter((_,i)=>i%Math.max(1,Math.ceil(priceRows.length/60))===0||i===priceRows.length-1).map((row)=>{ const i=priceRows.indexOf(row); return `<circle class="desk-chart-hit" cx="${x(i).toFixed(1)}" cy="${y(row.close).toFixed(1)}" r="8" ${chartPointAttributes(`${dateLabel(row.date)} · 주가 ${number(row.close)}원`)}></circle>`; }).join("");
    return `<svg class="desk-report-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 6개월 목표가와 실제 주가 비교"><path class="desk-report-price" d="${pricePath}"></path>${targetPath?`<path class="desk-report-target" d="${targetPath}"></path>`:""}${hits}<text class="desk-report-legend target" x="${left}" y="14">● 목표가</text><text class="desk-report-legend price" x="${left+72}" y="14">● 주가</text></svg>`;
  }

  function newsTemperatureChartSvg(dashboard, prices) {
    const sentiment = dashboard.sentiment || {}, rows = normalizePriceRows(prices, dashboard.quote).slice(-30);
    if (rows.length < 2) return "";
    const width=600,height=190,left=30,right=20,top=20,bottom=155,min=Math.min(...rows.map((row)=>row.close)),max=Math.max(...rows.map((row)=>row.close)),span=max-min||1;
    const x=(index)=>left+index*((width-left-right)/Math.max(1,rows.length-1)), y=(value)=>top+((max-value)/span)*(bottom-top);
    const path=rows.map((row,index)=>`${index?"L":"M"}${x(index).toFixed(1)},${y(row.close).toFixed(1)}`).join(" ");
    const markers=(sentiment.latest_items||[]).map((item)=>{ const date=String(item.published_at||"").slice(0,10),index=rows.findIndex((row)=>row.date>=date); if(index<0)return""; const tone=item.impact==="호재"?"positive":item.impact==="악재"?"negative":"neutral"; return `<circle class="desk-news-marker ${tone}" cx="${x(index).toFixed(1)}" cy="${y(rows[index].close).toFixed(1)}" r="5" ${chartPointAttributes(`${dateLabel(date)} · ${item.impact||"중립"} · ${item.title||"뉴스"}`)}></circle>`; }).join("");
    return `<svg class="desk-news-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 30일 뉴스 분류와 실제 주가 흐름"><path class="desk-news-price" d="${path}"></path>${markers}</svg>`;
  }

  function renderDesktopStockHome(root, code, dashboard, prices, context) {
    const quote = dashboard.quote || {}, flows = dashboard.flows || {}, priceRows = normalizePriceRows(prices, quote);
    const reports = context.research_reports || [], disclosures = context.disclosures || [], news = context.news_items || dashboard.sentiment?.latest_items || [];
    const latestVolume = finiteNumber(quote.volume) ?? priceRows.at(-1)?.volume, previousVolumes = priceRows.slice(-21,-1).map((row)=>row.volume).filter((value)=>value>0);
    const averageVolume = previousVolumes.length ? previousVolumes.reduce((sum,value)=>sum+value,0)/previousVolumes.length : null;
    const volumeRatio = latestVolume !== null && averageVolume ? latestVolume/averageVolume*100 : null;
    const yearRows = priceRows.slice(-260), yearHigh = yearRows.length ? Math.max(...yearRows.map((row)=>row.high ?? row.close)) : null;
    const distanceFromHigh = finiteNumber(quote.price) !== null && yearHigh ? (Number(quote.price)/yearHigh-1)*100 : null;
    const coverage = Object.values(dashboard.coverage || {}), coverageText = coverage.length ? `${coverage.filter(Boolean).length}/${coverage.length}` : "-";

    section(root, "오늘 브리핑 · 오늘의 요약", 0, 13, 6);
    addCell(root, `• ${number(quote.price)}원 (${percent(quote.change_rate)})${distanceFromHigh === null ? "" : ` · 52주 고점 대비 ${percent(distanceFromHigh)}`}`, 0, 14, { cols: 6, className: "desk-cell-wrap" });
    addCell(root, `• 외국인 ${signedMoney(flows.foreign_net_buy_20d)} · 기관 ${signedMoney(flows.institution_net_buy_20d)} (최근 20거래일)`, 0, 15, { cols: 6, className: "desk-cell-wrap" });
    addCell(root, `• 거래량 ${number(latestVolume)}주${volumeRatio === null ? "" : ` · 최근 20일 평균의 ${number(volumeRatio,0)}%`}`, 0, 16, { cols: 6, className: "desk-cell-wrap" });
    addCell(root, `• ${dashboard.market || "시장"} · ${dashboard.company_profile?.industry || dashboard.company_profile?.sector || "업종 정보 확인 중"} · 분석 데이터 ${coverageText}`, 0, 17, { cols: 6, className: "desk-cell-wrap" });
    addCell(root, `${dateLabel(quote.trade_date || dashboard.as_of)} 기준`, 0, 18, { cols: 6, className: "desk-cell-muted" });

    section(root, "최근 정보 · 종목 소식", 6, 13, 6);
    headers(root, ["구분", "일자", "제목·원문"], 6, 14, [1,1,4]);
    const latestItems = [
      ["리포트", reports[0], reports[0]?.title],
      ["공시", disclosures[0], disclosures[0]?.report_name || disclosures[0]?.title],
      ["뉴스", news[0], news[0]?.title],
    ];
    latestItems.forEach(([kind,item,title],index)=>{ const row=15+index,href=detailItemUrl(item||{}); addCell(root,kind,6,row,{className:"desk-cell-center"}); addCell(root,item?dateLabel(item.published_at):"-",7,row); addCell(root,title||"최근 자료가 없습니다.",8,row,{cols:4,tag:href?"a":"div",href,className:href?"desk-cell-link":"desk-cell-muted",title:title||"최근 자료가 없습니다."}); });

    const analysis = computeDesktopChartAnalysis(prices);
    section(root, "차트분석 · 5일·10일 전망", 0, 20, 12);
    addCell(root, analysis.available ? desktopForecastChartSvg(analysis) : analysis.reason, 0, 21, { cols: 8, rows: 12, html: analysis.available, className: analysis.available ? "desk-cell-chart desk-cell-forecast-chart" : "desk-cell-status" });
    headers(root, ["구분", "방향", "예상가(원)", "예상수익률(%)"], 8, 21, [1,1,1,1]);
    [["5일",analysis.forecast5],["10일",analysis.forecast10]].forEach(([label,item],index)=>{ const row=22+index; addCell(root,label,8,row); addCell(root,item?.direction||"-",9,row); addCell(root,item?number(item.expected):"-",10,row,{className:"desk-cell-number"}); addCell(root,item?percent(item.expectedRate):"-",11,row,{className:`desk-cell-number ${changeClass(item?.expectedRate)}`}); });
    addCell(root, "지지선(원)", 8, 25, { cols: 2, className: "desk-cell-header" }); addCell(root, analysis.available?number(analysis.support):"-", 10, 25, { cols: 2, className: "desk-cell-number" });
    addCell(root, "저항선(원)", 8, 26, { cols: 2, className: "desk-cell-header" }); addCell(root, analysis.available?number(analysis.resistance):"-", 10, 26, { cols: 2, className: "desk-cell-number" });
    addCell(root, "예상 범위는 최근 가격·변동성으로 계산한 참고값이며 실제 수익을 보장하지 않습니다.", 8, 29, { cols: 4, rows: 3, className: "desk-cell-wrap desk-cell-status" });

    const oneMonthDisclosures = recentDisclosureRows(dashboard, disclosures), disclosuresExpanded = state.detailDisclosuresExpanded.get(code) === true;
    section(root, `DART 공시 · 최근 1개월 공시 · 총 ${oneMonthDisclosures.length}건`, 0, 36, 6);
    headers(root, ["일자", "분류", "공시 제목·원문"], 0, 37, [1,1,4]);
    const visibleDisclosures = oneMonthDisclosures.slice(0, disclosuresExpanded ? 8 : 5);
    visibleDisclosures.forEach((item,index)=>{ const row=38+index,href=detailItemUrl(item); addCell(root,dateLabel(item.published_at),0,row); addCell(root,item.disclosure_category||"공시",1,row); addCell(root,item.report_name||item.title,2,row,{cols:4,tag:href?"a":"div",href,className:href?"desk-cell-link":"",title:item.filer_name?`${item.report_name} · 제출인 ${item.filer_name}`:item.report_name}); });
    if (!visibleDisclosures.length) addCell(root,"최근 30일 내 공시가 없습니다. DART 전체 보기에서 과거 공시를 확인할 수 있습니다.",0,38,{cols:6,className:"desk-cell-status"});
    addCell(root,"DART 전체 보기 ↗",0,46,{cols:2,tag:"a",href:dartCompanyUrl(dashboard,disclosures),className:"desk-cell-link"});
    if (oneMonthDisclosures.length>5) detailActionButton(root,disclosuresExpanded?"공시 접기":"공시 더보기",2,46,2,()=>{ state.detailDisclosuresExpanded.set(code,!disclosuresExpanded); activate(`detail:${code}`,{replaceHistory:true}); },{ariaLabel:`${dashboard.name} 공시 ${disclosuresExpanded?"접기":"더보기"}`});

    section(root, "수급 확인 · 최근 7일 수급", 6, 36, 6);
    const sevenDayChart = investorFlowChartSvg(context.flows || [], { count: 7, height: 280 });
    addCell(root, sevenDayChart || "최근 7거래일 수급을 불러오지 못했습니다.", 6, 37, { cols: 6, rows: 9, html: Boolean(sevenDayChart), className: sevenDayChart ? "desk-cell-chart" : "desk-cell-status" });
    addCell(root,"개인은 외국인·기관 일별 순매수 합계의 반대값으로 추정합니다.",6,46,{cols:6,className:"desk-cell-muted"});

    const keywords = detailKeywords(dashboard, context);
    section(root, "최근 반복 단어 · 핵심 키워드", 0, 49, 4);
    addCell(root, keywords.length ? keywords.map((item)=>`${item.label}(${item.count})`).join(" · ") : "키워드 집계에 필요한 자료가 부족합니다.", 0, 50, { cols: 4, rows: 4, className: "desk-cell-wrap" });
    section(root, "연관 정보 · 종목 이슈", 4, 49, 8);
    const issueKeywords = keywords.slice(0,5), selectedKeyword = state.detailIssueKeywords.get(code) || issueKeywords[0]?.label || "";
    if (selectedKeyword && !state.detailIssueKeywords.has(code)) state.detailIssueKeywords.set(code,selectedKeyword);
    issueKeywords.forEach((item,index)=>detailOptionButton(root,code,state.detailIssueKeywords,selectedKeyword,item.label,item.label,4+index,50));
    const candidates=[...news.map((item)=>({...item,kind:"뉴스",displayTitle:item.title})),...reports.map((item)=>({...item,kind:"리포트",displayTitle:item.title})),...disclosures.map((item)=>({...item,kind:"공시",displayTitle:item.report_name||item.title}))].filter((item)=>item.displayTitle);
    const issue=candidates.find((item)=>String(item.displayTitle).toLowerCase().includes(String(selectedKeyword).toLowerCase()))||candidates[0];
    if(issue){ const href=detailItemUrl(issue); addCell(root,issue.displayTitle,4,52,{cols:8,tag:href?"a":"div",href,className:href?"desk-cell-link desk-cell-wrap":"desk-cell-wrap",title:issue.displayTitle}); addCell(root,`${issue.kind} · ${dateLabel(issue.published_at)} · ${selectedKeyword||"최근 이슈"}`,4,53,{cols:8,className:"desk-cell-muted"}); }
    else addCell(root,"연결된 이슈가 없습니다.",4,52,{cols:8,className:"desk-cell-status"});

    section(root, "수급 · 투자자별 매매동향", 0, 56, 12);
    const flowMode=state.detailFlowModes.get(code)||"cumulative",flowPeriod=state.detailFlowPeriods.get(code)||"3M";
    detailOptionButton(root,code,state.detailFlowModes,"cumulative","cumulative","누적매매",0,57,2); detailOptionButton(root,code,state.detailFlowModes,"cumulative","daily","일별매매",2,57,2);
    [["3M","3개월"],["6M","6개월"],["1Y","1년"]].forEach(([id,label],index)=>detailOptionButton(root,code,state.detailFlowPeriods,"3M",id,label,7+index,57));
    const flowHistory=investorHistoryChartSvg(context.flows||[],flowMode,flowPeriod),flowRows=investorHistoryRows(context.flows||[],flowMode,flowPeriod),lastFlow=flowRows.at(-1)||{};
    addCell(root,flowHistory||"표시할 수급 이력이 부족합니다.",0,59,{cols:9,rows:11,html:Boolean(flowHistory),className:flowHistory?"desk-cell-chart":"desk-cell-status"});
    headers(root,["투자자","선택 기간 순매수(주)"],9,59,[1,2]);
    [["개인(추정)",lastFlow.personal],["외국인",lastFlow.foreign],["기관",lastFlow.institution]].forEach(([label,value],index)=>{addCell(root,label,9,60+index);addCell(root,value===undefined?"-":number(value),10,60+index,{cols:2,className:`desk-cell-number ${changeClass(value)}`});});
    addCell(root,`${flowPeriod} · ${flowMode==="cumulative"?"누적":"일별"} 기준 · 같은 날짜의 외국인·기관 흐름 비교`,9,65,{cols:3,rows:2,className:"desk-cell-wrap desk-cell-muted"});

    section(root,"증권사 자료 · 리포트 분석",0,73,7);
    const reportMode=state.detailReportModes.get(code)||"target";
    [["target","목표가 추이"],["issuance","발행 추이"],["broker","발행 증권사"]].forEach(([id,label],index)=>detailOptionButton(root,code,state.detailReportModes,"target",id,label,index*2,74,2));
    const reportChart=reportHistoryChartSvg(context,prices,quote,reportMode);
    addCell(root,reportChart||"최근 발행된 증권사 리포트가 없습니다.",0,75,{cols:7,rows:9,html:Boolean(reportChart),className:reportChart?"desk-cell-chart":"desk-cell-status"});
    const targetReports=reportHistoryRows(context).filter((row)=>row.target!==null&&row.target>0),latestTarget=targetReports.at(-1)?.target,currentPrice=finiteNumber(quote.price),upside=currentPrice&&latestTarget?(latestTarget/currentPrice-1)*100:null;
    addCell(root,`최근 목표가 ${latestTarget?`${number(latestTarget)}원`:"-"} · 목표가 대비 현재가 ${upside===null?"-":percent(upside)} · 최근 리포트 ${reports.length}건`,0,84,{cols:7,className:"desk-cell-muted"});
    headers(root,["일자","증권사","의견","목표가(원)","제목·원문"],0,86,[1,1,1,1,3]);
    reports.slice(0,6).forEach((item,index)=>{const row=87+index,href=detailItemUrl(item);addCell(root,dateLabel(item.published_at),0,row);addCell(root,item.broker_name,1,row);addCell(root,item.opinion,2,row);addCell(root,item.target_price?number(item.target_price):"-",3,row,{className:"desk-cell-number"});addCell(root,item.title,4,row,{cols:3,tag:href?"a":"div",href,className:href?"desk-cell-link":"",title:item.title});});

    section(root,"최근 기사 · 종목뉴스",7,73,5);
    const filteredNews=news.filter((item)=>item.source_category!=="breaking");
    headers(root,["일자","언론사","제목·원문"],7,74,[1,1,3]);
    filteredNews.slice(0,7).forEach((item,index)=>{const row=75+index,href=detailItemUrl(item);addCell(root,dateLabel(item.published_at),7,row);addCell(root,item.press_name||item.source,8,row);addCell(root,item.title,9,row,{cols:3,tag:href?"a":"div",href,className:href?"desk-cell-link":"",title:item.summary||item.title});});
    if(!filteredNews.length)addCell(root,"최근 종목뉴스가 없습니다.",7,75,{cols:5,className:"desk-cell-status"});
    section(root,"기사 분석 · 뉴스 온도",7,85,5);
    const sentiment=dashboard.sentiment||{},positive=Math.max(0,Number(sentiment.positive_count||0)),neutral=Math.max(0,Number(sentiment.neutral_count||0)),negative=Math.max(0,Number(sentiment.negative_count||0)),total=positive+neutral+negative,temperature=positive>negative*1.25?"호재 우위":negative>positive*1.25?"악재 우위":"혼재";
    addCell(root,`${temperature} · 기사 ${total}건 · 긍정 ${positive} · 중립 ${neutral} · 부정 ${negative}`,7,86,{cols:5,className:"desk-cell-muted"});
    const newsChart=newsTemperatureChartSvg(dashboard,prices);addCell(root,newsChart||"가격 이력이 부족합니다.",7,87,{cols:5,rows:6,html:Boolean(newsChart),className:newsChart?"desk-cell-chart":"desk-cell-status"});

    const providers=(context.community?.providers||[]).filter((provider)=>provider.key!=="threads"),communityItems=providers.flatMap((provider)=>(provider.items||[]).map((item)=>({...item,providerLabel:provider.label,searchUrl:provider.search_url})));
    section(root,"시장 반응 · 커뮤니티",0,96,12);addCell(root,context.community?.message||"커뮤니티 글은 사실 확인 전 시장 반응 참고용으로만 확인하세요.",0,97,{cols:12,className:"desk-cell-muted"});
    headers(root,["출처","작성자","반응","작성 시각","내용","조회(건)","공감(건)","댓글(건)","원문"],0,98,[1,1,1,1,4,1,1,1,1]);
    communityItems.slice(0,10).forEach((item,index)=>{const row=99+index,href=item.url||item.searchUrl;addCell(root,item.providerLabel||item.provider_key,0,row);addCell(root,item.author_name||item.username,1,row);addCell(root,item.impact||"중립",2,row,{className:item.impact==="호재"?"desk-cell-positive":item.impact==="악재"?"desk-cell-negative":""});addCell(root,dateLabel(item.created_at),3,row);addCell(root,item.text||item.title,4,row,{cols:4,title:item.text||item.title});addCell(root,number(item.view_count||0),8,row,{className:"desk-cell-number"});addCell(root,number(item.like_count||0),9,row,{className:"desk-cell-number"});addCell(root,number(item.reply_count||0),10,row,{className:"desk-cell-number"});addCell(root,href?"원문 ↗":"-",11,row,{tag:href?"a":"div",href,className:href?"desk-cell-link":""});});
    if(!communityItems.length)addCell(root,context.community?.message||"관련 커뮤니티 글을 찾지 못했습니다.",0,99,{cols:12,className:"desk-cell-status"});
  }

  const DESKTOP_COMPANY_REPORT_LABELS = { "11013":"1분기", "11012":"반기", "11014":"3분기", "11011":"연간" };
  const DESKTOP_COMPANY_REPORT_RANKS = { "11013":1, "11012":2, "11014":3, "11011":4 };

  function companyGrowth(current, previous) {
    const a=finiteNumber(current),b=finiteNumber(previous); return a===null||b===null||b<=0?null:(a/b-1)*100;
  }

  function desktopCompanyPerformance(dashboard) {
    const quarterly=(dashboard.financial_series?.quarterly||[]).filter((row)=>!row.estimated),annual=(dashboard.financial_series?.annual||[]).filter((row)=>!row.estimated);
    let scope="quarterly",rows=quarterly,latest=rows.at(-1)||null,previous=rows.length>=5?rows.at(-5):null;
    if(!latest||!previous){scope="annual";rows=annual;latest=rows.at(-1)||latest;previous=rows.length>=2?rows.at(-2):previous;}
    const operatingMargin=finiteNumber(latest?.operating_margin),previousOperatingMargin=finiteNumber(previous?.operating_margin),netMargin=finiteNumber(latest?.net_margin),previousNetMargin=finiteNumber(previous?.net_margin);
    return {scope,latest,previous,revenueGrowth:companyGrowth(latest?.revenue,previous?.revenue),operatingProfitGrowth:companyGrowth(latest?.operating_profit,previous?.operating_profit),netIncomeGrowth:companyGrowth(latest?.net_income,previous?.net_income),epsGrowth:companyGrowth(latest?.eps,previous?.eps),operatingMarginChange:operatingMargin===null||previousOperatingMargin===null?null:operatingMargin-previousOperatingMargin,netMarginChange:netMargin===null||previousNetMargin===null?null:netMargin-previousNetMargin};
  }

  function selectDesktopCompanyStatement(lines) {
    const groups=new Map();
    for(const line of Array.isArray(lines)?lines:[]){if(finiteNumber(line?.current_amount)===null)continue;const key=[line.bsns_year,line.reprt_code,line.fs_div||""].join(":"),group=groups.get(key)||{year:String(line.bsns_year||""),report:String(line.reprt_code||""),fs:String(line.fs_div||""),rows:[]};group.rows.push(line);groups.set(key,group);}
    return [...groups.values()].sort((a,b)=>Number(b.year||0)-Number(a.year||0)||(DESKTOP_COMPANY_REPORT_RANKS[b.report]||0)-(DESKTOP_COMPANY_REPORT_RANKS[a.report]||0)||(b.fs==="CFS"?1:0)-(a.fs==="CFS"?1:0))[0]||null;
  }

  function desktopStatementLine(group,options={}) {
    const statements=Array.isArray(options.statement)?options.statement:[options.statement],rows=options.statement?(group?.rows||[]).filter((row)=>statements.includes(String(row.sj_div||"").toUpperCase())):(group?.rows||[]);
    for(const id of options.ids||[]){const match=rows.find((row)=>String(row.account_id||"")===id);if(match)return match;}
    for(const name of options.names||[]){const match=rows.find((row)=>String(row.account_name||"").replace(/\s/g,"")===String(name).replace(/\s/g,""));if(match)return match;}
    return options.pattern?rows.find((row)=>options.pattern.test(String(row.account_name||"")))||null:null;
  }

  function desktopStatementValue(group,options={},amountKey="current_amount"){return finiteNumber(desktopStatementLine(group,options)?.[amountKey]);}
  function desktopStatementSum(group,entries,amountKey="current_amount"){const seen=new Set();let total=0,found=false;for(const options of entries){const row=desktopStatementLine(group,options);if(!row)continue;const key=`${row.sj_div||""}:${row.account_id||""}:${row.account_name||""}`;if(seen.has(key))continue;const value=finiteNumber(row[amountKey]);if(value===null)continue;seen.add(key);total+=Math.abs(value);found=true;}return found?total:null;}
  function companyRatio(value,total,multiplier=100){const a=finiteNumber(value),b=finiteNumber(total);return a===null||b===null||b===0?null:(a/b)*multiplier;}
  function companyAnnualization(report){return {"11013":4,"11012":2,"11014":4/3,"11011":1}[report]||1;}

  function desktopCompanyMetrics(dashboard, lines) {
    const group=selectDesktopCompanyStatement(lines);
    if(!group)return {group:null};
    const balance={
      assets:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_Assets"],names:["자산총계"]}),currentAssets:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_CurrentAssets"],names:["유동자산"]}),cash:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_CashAndCashEquivalents"],names:["현금및현금성자산"]}),shortDeposits:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_ShorttermDepositsNotClassifiedAsCashEquivalents"],names:["단기금융상품"]}),receivables:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_CurrentTradeReceivables","ifrs-full_TradeAndOtherCurrentReceivables"],names:["매출채권","매출채권및기타채권"]}),inventory:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_Inventories"],names:["재고자산"]}),liabilities:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_Liabilities"],names:["부채총계"]}),currentLiabilities:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_CurrentLiabilities"],names:["유동부채"]}),equity:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_Equity"],names:["자본총계"]}),
    };
    const previous={assets:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_Assets"],names:["자산총계"]},"previous_amount"),equity:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_Equity"],names:["자본총계"]},"previous_amount"),receivables:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_CurrentTradeReceivables","ifrs-full_TradeAndOtherCurrentReceivables"],names:["매출채권","매출채권및기타채권"]},"previous_amount"),inventory:desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_Inventories"],names:["재고자산"]},"previous_amount")};
    const combinedBorrowings=desktopStatementValue(group,{statement:"BS",ids:["ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"],names:["유동성차입금","단기및유동성장기차입금"]});
    const currentBorrowings=combinedBorrowings!==null?Math.abs(combinedBorrowings):desktopStatementSum(group,[{statement:"BS",ids:["ifrs-full_ShorttermBorrowings"],names:["단기차입금"]},{statement:"BS",ids:["ifrs-full_CurrentPortionOfLongtermBorrowings"],names:["유동성장기부채","유동성장기차입금"]},{statement:"BS",ids:["ifrs-full_CurrentPortionOfNoncurrentBondsIssued"],names:["유동성사채"]}]);
    const noncurrentBorrowings=desktopStatementSum(group,[{statement:"BS",ids:["ifrs-full_LongtermBorrowings","ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived"],names:["장기차입금"]},{statement:"BS",ids:["ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued"],names:["사채"]}]);
    const debt=currentBorrowings===null&&noncurrentBorrowings===null?null:(currentBorrowings||0)+(noncurrentBorrowings||0),incomeStatements=["IS","CIS"];
    const operatingCashFlow=desktopStatementValue(group,{statement:"CF",ids:["ifrs-full_CashFlowsFromUsedInOperatingActivities"],names:["영업활동현금흐름"]}),investingCashFlow=desktopStatementValue(group,{statement:"CF",ids:["ifrs-full_CashFlowsFromUsedInInvestingActivities"],names:["투자활동현금흐름"]}),financingCashFlow=desktopStatementValue(group,{statement:"CF",ids:["ifrs-full_CashFlowsFromUsedInFinancingActivities"],names:["재무활동현금흐름"]}),reportedCashChange=desktopStatementValue(group,{statement:"CF",ids:["ifrs-full_IncreaseDecreaseInCashAndCashEquivalents"],names:["현금및현금성자산의순증감","현금및현금성자산의증가(감소)"]}),exchangeEffect=desktopStatementValue(group,{statement:"CF",ids:["ifrs-full_EffectOfExchangeRateChangesOnCashAndCashEquivalents"],names:["현금및현금성자산의환율변동효과"]});
    const capex=desktopStatementSum(group,[{statement:"CF",ids:["ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],names:["유형자산의취득"]},{statement:"CF",ids:["ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities"],names:["무형자산의취득"]}]);
    const revenue=desktopStatementValue(group,{statement:incomeStatements,ids:["ifrs-full_Revenue"],names:["매출액","영업수익"]}),operatingProfit=desktopStatementValue(group,{statement:incomeStatements,ids:["dart_OperatingIncomeLoss","ifrs-full_ProfitLossFromOperatingActivities"],names:["영업이익","영업이익(손실)"]}),netIncome=desktopStatementValue(group,{statement:incomeStatements,ids:["ifrs-full_ProfitLoss"],names:["당기순이익","분기순이익","반기순이익","당기순이익(손실)"]}),grossProfit=desktopStatementValue(group,{statement:incomeStatements,ids:["ifrs-full_GrossProfit"],names:["매출총이익"]}),costOfSales=desktopStatementValue(group,{statement:incomeStatements,ids:["ifrs-full_CostOfSales"],names:["매출원가"]}),financeCosts=desktopStatementValue(group,{statement:incomeStatements,ids:["ifrs-full_FinanceCosts"],names:["금융비용","이자비용"]});
    const liquidFunds=balance.cash===null&&balance.shortDeposits===null?null:(balance.cash||0)+(balance.shortDeposits||0),freeCashFlow=operatingCashFlow===null?null:operatingCashFlow-(capex||0),annualization=companyAnnualization(group.report),marketCap=finiteNumber(dashboard.quote?.market_cap),averageEquity=balance.equity!==null&&previous.equity!==null?(balance.equity+previous.equity)/2:balance.equity,averageAssets=balance.assets!==null&&previous.assets!==null?(balance.assets+previous.assets)/2:balance.assets,averageInventory=balance.inventory!==null&&previous.inventory!==null?(balance.inventory+previous.inventory)/2:balance.inventory,annualizedCostOfSales=costOfSales===null?null:Math.abs(costOfSales)*annualization,netDebt=liquidFunds===null||debt===null?null:debt-liquidFunds;
    const coreValues=[operatingCashFlow,investingCashFlow,financingCashFlow],coreCashFlow=coreValues.every((value)=>value!==null)?coreValues.reduce((sum,value)=>sum+value,0):null,calculatedChange=coreCashFlow===null?null:coreCashFlow+(exchangeEffect||0),cashChange=reportedCashChange===null?calculatedChange:reportedCashChange;
    return {group,...balance,debt,liquidFunds,netCash:netDebt===null?null:-netDebt,netDebtRatio:companyRatio(netDebt,balance.equity),operatingCashFlow,investingCashFlow,financingCashFlow,cashChange,cashFlowResidual:cashChange===null||coreCashFlow===null?null:cashChange-coreCashFlow,capex,freeCashFlow,revenue,operatingProfit,netIncome,grossMargin:companyRatio(grossProfit,revenue),cashConversion:companyRatio(operatingCashFlow,netIncome),freeCashFlowMargin:companyRatio(freeCashFlow,revenue),freeCashFlowYield:freeCashFlow===null||marketCap===null?null:companyRatio(freeCashFlow*annualization,marketCap),debtRatio:companyRatio(balance.liabilities,balance.equity),currentRatio:companyRatio(balance.currentAssets,balance.currentLiabilities),interestCoverage:companyRatio(operatingProfit,Math.abs(financeCosts||0),1),roe:companyRatio(netIncome===null?null:netIncome*annualization,averageEquity),assetTurnover:companyRatio(revenue===null?null:revenue*annualization,averageAssets,1),receivablesGrowth:companyGrowth(balance.receivables,previous.receivables),inventoryGrowth:companyGrowth(balance.inventory,previous.inventory),inventoryDays:companyRatio(averageInventory,annualizedCostOfSales,365),liabilityShare:companyRatio(balance.liabilities,balance.assets),equityShare:companyRatio(balance.equity,balance.assets)};
  }

  function companyStatementAmount(value){const parsed=finiteNumber(value);return parsed===null?"-":shortMoney(parsed);}
  function financialInstitution(dashboard){return /은행|금융|증권|보험|카드|캐피탈/.test(`${dashboard.company_profile?.industry||""} ${dashboard.company_profile?.sector||""}`);}
  function companyStatementLabel(metrics,performance){return metrics.group?`${metrics.group.year} ${DESKTOP_COMPANY_REPORT_LABELS[metrics.group.report]||metrics.group.report} · ${metrics.group.fs==="CFS"?"연결":"별도"}`:performance.latest?.period||"자료 확인 중";}

  function desktopCompanySnapshotRows(dashboard,performance,metrics){
    const valuation=dashboard.valuation||{},revenueGrowth=performance.revenueGrowth,profitGrowth=performance.operatingProfitGrowth,margin=finiteNumber(performance.latest?.operating_margin),marginChange=performance.operatingMarginChange;
    const growthStatus=revenueGrowth===null||profitGrowth===null?"정보 부족":revenueGrowth>0&&profitGrowth>0?"성장":revenueGrowth<0&&profitGrowth<0?"감소":"엇갈림",profitabilityStatus=margin===null?"정보 부족":margin<0?"적자":marginChange===null?"확인":marginChange>=0?"개선":"둔화",cashStatus=metrics.operatingCashFlow===null?"정보 부족":metrics.operatingCashFlow>0?"현금 유입":"현금 유출",isFinancial=financialInstitution(dashboard),stabilityStatus=isFinancial?"비교 주의":metrics.debtRatio===null||metrics.currentRatio===null?"정보 부족":metrics.debtRatio<=100&&metrics.currentRatio>=100?"양호":metrics.debtRatio>=200||metrics.currentRatio<80?"주의":"확인",efficiencyStatus=metrics.roe===null?"정보 부족":metrics.roe>=10?"양호":metrics.roe<5?"주의":"확인",per=finiteNumber(valuation.per),industryPer=finiteNumber(valuation.industry_per),valuationStatus=per===null||industryPer===null||per<=0||industryPer<=0?"비교 제한":per<=industryPer*.9?"업종 대비 낮음":per>=industryPer*1.1?"업종 대비 높음":"업종과 비슷";
    return [
      ["성장",growthStatus,revenueGrowth===null?"-":percent(revenueGrowth),revenueGrowth===null?"매출의 전년 비교 자료가 부족합니다.":`매출 ${percent(revenueGrowth)} · 영업이익 ${profitGrowth===null?"비교 불가":percent(profitGrowth)}`],
      ["수익성",profitabilityStatus,margin===null?"-":ratioPercent(margin),marginChange===null?"영업이익률 추이를 확인하세요.":`영업이익률이 비교 기간보다 ${number(Math.abs(marginChange),2)}%p ${marginChange>=0?"높아졌습니다.":"낮아졌습니다."}`],
      ["현금",cashStatus,companyStatementAmount(metrics.operatingCashFlow),metrics.cashConversion===null?"순이익이 실제 현금으로 들어오는지 확인 중입니다.":`현금이익비율 ${ratioPercent(metrics.cashConversion)}`],
      ["안정성",stabilityStatus,isFinancial?"업종 별도 기준":ratioPercent(metrics.debtRatio),isFinancial?"금융업은 일반 기업의 부채비율 기준으로 판단하기 어렵습니다.":`부채비율 ${ratioPercent(metrics.debtRatio)} · 유동비율 ${ratioPercent(metrics.currentRatio)}`],
      ["효율",efficiencyStatus,ratioPercent(metrics.roe),metrics.roe===null?"자본이익률 계산 자료가 부족합니다.":`단순 연환산 ROE · 자산회전율 ${metrics.assetTurnover===null?"-":`${number(metrics.assetTurnover,2)}회`}`],
      ["가격",valuationStatus,multiple(per),industryPer===null?"업종 PER 비교 자료가 없습니다.":`동일업종 PER ${multiple(industryPer)}`],
    ];
  }

  function desktopRevenueBreakdownRows(dashboard){return (dashboard.financial_series?.annual||[]).map((row)=>{const revenue=finiteNumber(row.revenue),profit=finiteNumber(row.operating_profit),margin=finiteNumber(row.operating_margin)??companyRatio(profit,revenue);return revenue===null||revenue<=0||profit===null||margin===null?null:{...row,revenue,operatingProfit:profit,operatingMargin:margin,operatingCostRate:100-margin};}).filter(Boolean).slice(-4);}

  function revenueBreakdownChartSvg(dashboard){
    const rows=desktopRevenueBreakdownRows(dashboard);if(!rows.length)return"";
    const width=760,height=270,left=52,right=20,top=26,bottom=220,scaleMax=clampNumber(Math.ceil(Math.max(100,...rows.map((row)=>Math.max(0,row.operatingCostRate)))/10)*10,100,160),slot=(width-left-right)/rows.length,barWidth=Math.min(90,slot*.48),y=(value)=>bottom-(value/scaleMax)*(bottom-top);
    const grid=[0,50,100,...(scaleMax>100?[scaleMax]:[])].map((value)=>`<line class="desk-revenue-grid${value===100?" is-reference":""}" x1="${left}" y1="${y(value).toFixed(1)}" x2="${width-right}" y2="${y(value).toFixed(1)}"></line><text class="desk-price-axis" x="${left-8}" y="${(y(value)+4).toFixed(1)}" text-anchor="end">${value}%</text>`).join("");
    const bars=rows.map((row,index)=>{const isLoss=row.operatingMargin<0,cost=Math.max(0,row.operatingCostRate),result=Math.abs(row.operatingMargin),x=left+slot*index+(slot-barWidth)/2,costHeight=Math.min(scaleMax,cost)/scaleMax*(bottom-top),resultHeight=Math.min(Math.max(0,scaleMax-Math.min(scaleMax,cost)),result)/scaleMax*(bottom-top),year=String(row.period||"").match(/\d{4}/)?.[0]||row.period,label=`${year}년 ${row.estimated?"추정":"실제"} · 매출 ${financialSeriesAmount(row.revenue,dashboard.financial_series?.unit||"억원")} · 영업비용 ${number(cost,1)}% · ${isLoss?"영업손실률":"영업이익률"} ${number(row.operatingMargin,1)}%`;return `<rect class="desk-revenue-cost" x="${x}" y="${(bottom-costHeight).toFixed(1)}" width="${barWidth}" height="${costHeight.toFixed(1)}" ${chartPointAttributes(label)}></rect><rect class="desk-revenue-result ${isLoss?"is-loss":"is-profit"}" x="${x}" y="${(bottom-costHeight-resultHeight).toFixed(1)}" width="${barWidth}" height="${Math.max(2,resultHeight).toFixed(1)}" ${chartPointAttributes(label)}></rect><text class="desk-report-value" x="${x+barWidth/2}" y="${Math.max(14,bottom-costHeight-resultHeight-7)}" text-anchor="middle">${number(row.operatingMargin,1)}%</text>`;}).join("");
    return `<svg class="desk-revenue-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="연간 매출 대비 영업비용과 영업이익 구조">${grid}${bars}<text class="desk-revenue-legend cost" x="${left}" y="14">■ 영업비용</text><text class="desk-revenue-legend profit" x="${left+82}" y="14">■ 영업이익</text><text class="desk-revenue-legend loss" x="${left+164}" y="14">■ 영업손실</text></svg>`;
  }

  function balanceCompositionSvg(metrics){
    if(metrics.assets===null||metrics.liabilities===null||metrics.equity===null)return"";
    const liability=clampNumber(metrics.liabilityShare||0,0,100),equity=clampNumber(metrics.equityShare||0,0,100),width=620,height=130,left=105,barWidth=width-left-20;
    return `<svg class="desk-balance-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="자산, 부채와 자본 조달 구조"><text x="8" y="34">자산</text><rect class="desk-balance-assets" x="${left}" y="14" width="${barWidth}" height="28" rx="3" ${chartPointAttributes(`자산 ${companyStatementAmount(metrics.assets)} · 100%`)}></rect><text x="8" y="90">부채 + 자본</text><rect class="desk-balance-liability" x="${left}" y="68" width="${barWidth*liability/100}" height="28" rx="3" ${chartPointAttributes(`부채 ${companyStatementAmount(metrics.liabilities)} · ${number(liability,1)}%`)}></rect><rect class="desk-balance-equity" x="${left+barWidth*liability/100}" y="68" width="${barWidth*equity/100}" height="28" rx="3" ${chartPointAttributes(`자본 ${companyStatementAmount(metrics.equity)} · ${number(equity,1)}%`)}></rect><text class="desk-price-axis" x="${left}" y="122">부채비율 ${ratioPercent(metrics.debtRatio,1)}</text></svg>`;
  }

  function cashflowWaterfallSvg(metrics){
    const source=[metrics.operatingCashFlow,metrics.investingCashFlow,metrics.financingCashFlow];if(source.some((value)=>value===null))return"";
    const cashChange=metrics.cashChange??source.reduce((sum,value)=>sum+value,0),rows=[["영업활동",metrics.operatingCashFlow],["투자활동",metrics.investingCashFlow],["재무활동",metrics.financingCashFlow],["현금 증감",cashChange]],width=620,height=235,left=54,right=20,top=30,bottom=185,maxAbs=Math.max(1,...rows.map(([,value])=>Math.abs(value))),baseline=(top+bottom)/2,slot=(width-left-right)/rows.length,barWidth=Math.min(70,slot*.48),scale=(bottom-top)/2/maxAbs;
    const grid=`<line class="desk-flow-grid is-zero" x1="${left}" y1="${baseline}" x2="${width-right}" y2="${baseline}"></line>`;
    const bars=rows.map(([label,value],index)=>{const h=Math.max(2,Math.abs(value)*scale),x=left+slot*index+(slot-barWidth)/2,y=value>=0?baseline-h:baseline,tone=value>=0?"is-inflow":"is-outflow",tip=`${label} ${value>0?"+":""}${companyStatementAmount(value)}`;return `<rect class="desk-cashflow-bar ${tone}" x="${x}" y="${y}" width="${barWidth}" height="${h}" rx="3" ${chartPointAttributes(tip)}></rect><text class="desk-report-value" x="${x+barWidth/2}" y="${value>=0?Math.max(14,y-7):Math.min(height-32,y+h+15)}" text-anchor="middle">${value>0?"+":""}${companyStatementAmount(value)}</text><text class="desk-price-axis" x="${x+barWidth/2}" y="222" text-anchor="middle">${label}</text>`;}).join("");
    return `<svg class="desk-cashflow-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="영업, 투자, 재무활동과 최종 현금 증감">${grid}${bars}</svg>`;
  }

  function perComparisonChartSvg(dashboard,sectorMargins){
    const comparison=sectorMargins?.valuation_comparison;if(!comparison?.target||!comparison?.peer)return"";
    const target={...comparison.target,name:dashboard.name,current_per:finiteNumber(dashboard.valuation?.per)??comparison.target.current_per,forward_per:finiteNumber(dashboard.valuation?.estimated_per)??comparison.target.forward_per},companies=[target,comparison.peer],values=companies.flatMap((company)=>[finiteNumber(company.current_per),finiteNumber(company.forward_per)]).filter((value)=>value!==null&&value>0);if(!values.length)return"";
    const width=650,height=250,left=58,right=20,top=30,bottom=198,max=Math.max(...values)*1.16,groupSlot=(width-left-right)/companies.length,barWidth=58;
    const bars=companies.map((company,index)=>[["current_per","현재 PER","is-current"],["forward_per","예상 PER","is-forward"]].map(([key,label,tone],barIndex)=>{const value=finiteNumber(company[key]),h=value&&value>0?(value/max)*(bottom-top):0,x=left+groupSlot*index+groupSlot/2+(barIndex?8:-barWidth-8),y=bottom-h,tip=`${company.name} · ${label} ${value&&value>0?multiple(value):"자료 없음"}`;return `<rect class="desk-per-bar ${tone}" x="${x}" y="${y}" width="${barWidth}" height="${Math.max(2,h)}" rx="3" ${chartPointAttributes(tip)}></rect><text class="desk-report-value" x="${x+barWidth/2}" y="${Math.max(15,y-7)}" text-anchor="middle">${value&&value>0?multiple(value):"-"}</text>`;}).join("")+`<text class="desk-price-axis" x="${left+groupSlot*index+groupSlot/2}" y="230" text-anchor="middle">${escapeMarkup(company.name)}</text>`).join("");
    return `<svg class="desk-per-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="선택 종목과 동종 경쟁사의 현재 및 예상 PER 비교">${bars}<text class="desk-report-legend target" x="${left}" y="15">■ 현재 PER</text><text class="desk-report-legend price" x="${left+92}" y="15">■ 예상 PER</text></svg>`;
  }

  function desktopCompanyMetricGroups(dashboard,performance,metrics){
    const opMargin=finiteNumber(performance.latest?.operating_margin),netMargin=finiteNumber(performance.latest?.net_margin),isFinancial=financialInstitution(dashboard);
    return [
      ["수익성 구조",[["매출총이익률",ratioPercent(metrics.grossMargin),"매출총이익 ÷ 매출"],["영업이익률",ratioPercent(opMargin),"본업의 수익성"],["순이익률",ratioPercent(netMargin),"최종적으로 남은 이익"],["EPS 성장률",percent(performance.epsGrowth),"전년 동기/전년 대비"]]],
      ["이익의 질",[["영업현금흐름",companyStatementAmount(metrics.operatingCashFlow),"본업에서 들어온 현금"],["잉여현금흐름 FCF",companyStatementAmount(metrics.freeCashFlow),"영업현금 - 설비·무형자산 투자"],["현금이익비율",ratioPercent(metrics.cashConversion),"영업현금 ÷ 순이익"],["FCF 수익률",ratioPercent(metrics.freeCashFlowYield),"연환산 FCF ÷ 시가총액"]]],
      ["재무 안정성",[["부채비율",ratioPercent(metrics.debtRatio),isFinancial?"금융업은 별도 기준 필요":"부채 ÷ 자본"],["유동비율",ratioPercent(metrics.currentRatio),"유동자산 ÷ 유동부채"],["순현금",companyStatementAmount(metrics.netCash),"현금성자산 - 차입금·사채"],["이자보상배율",metrics.interestCoverage===null?"-":`${number(metrics.interestCoverage,1)}배`,"영업이익 ÷ 금융비용"]]],
      ["운영 효율",[["ROE",ratioPercent(metrics.roe),"순이익 ÷ 평균자본 · 단순 연환산"],["자산회전율",metrics.assetTurnover===null?"-":`${number(metrics.assetTurnover,2)}회`,"연환산 매출 ÷ 평균자산"],["매출채권 증감",percent(metrics.receivablesGrowth),"외상매출 현금화 점검"],["재고 증감",percent(metrics.inventoryGrowth),"재고 부담 점검"]]],
    ];
  }

  function desktopCompanyCheckpoints(dashboard,performance,metrics){
    const strengths=[],risks=[];
    if(performance.revenueGrowth!==null&&performance.operatingProfitGrowth!==null){if(performance.revenueGrowth>0&&performance.operatingProfitGrowth>0)strengths.push(`매출 ${percent(performance.revenueGrowth)}, 영업이익 ${percent(performance.operatingProfitGrowth)}로 함께 성장했습니다.`);if(performance.revenueGrowth<0)risks.push(`매출이 비교 기간보다 ${ratioPercent(Math.abs(performance.revenueGrowth))} 감소했습니다.`);if(performance.operatingProfitGrowth<0)risks.push(`영업이익이 비교 기간보다 ${ratioPercent(Math.abs(performance.operatingProfitGrowth))} 감소했습니다.`);}
    if(performance.operatingMarginChange>=1)strengths.push(`영업이익률이 ${number(performance.operatingMarginChange,2)}%p 개선됐습니다.`);if(performance.operatingMarginChange<=-1)risks.push(`영업이익률이 ${number(Math.abs(performance.operatingMarginChange),2)}%p 낮아졌습니다.`);
    if(metrics.operatingCashFlow!==null)(metrics.operatingCashFlow>0?strengths:risks).push(`본업 현금흐름 ${companyStatementAmount(metrics.operatingCashFlow)}${metrics.operatingCashFlow>0?" 유입":" 유출"}입니다.`);
    if(metrics.freeCashFlow!==null)(metrics.freeCashFlow>0?strengths:risks).push(`투자 지출 후 잉여현금흐름이 ${companyStatementAmount(metrics.freeCashFlow)}${metrics.freeCashFlow>0?" 남았습니다.":"로 음수입니다."}`);
    if(metrics.netCash!==null)(metrics.netCash>0?strengths:risks).push(metrics.netCash>0?`현금성자산이 이자성 부채보다 ${companyStatementAmount(metrics.netCash)} 많습니다.`:`이자성 부채가 현금성자산보다 ${companyStatementAmount(Math.abs(metrics.netCash))} 많습니다.`);
    if(!financialInstitution(dashboard)){if(metrics.currentRatio!==null&&metrics.currentRatio<80)risks.push(`유동비율이 ${ratioPercent(metrics.currentRatio)}로 단기 지급 여력을 점검해야 합니다.`);if(metrics.debtRatio!==null&&metrics.debtRatio>200)risks.push(`부채비율이 ${ratioPercent(metrics.debtRatio)}로 재무 부담이 높습니다.`);}
    if(metrics.receivablesGrowth!==null&&performance.revenueGrowth!==null&&metrics.receivablesGrowth>performance.revenueGrowth+10)risks.push(`매출채권 증가율 ${percent(metrics.receivablesGrowth)}가 매출 증가율보다 빠릅니다.`);if(metrics.inventoryGrowth!==null&&performance.revenueGrowth!==null&&metrics.inventoryGrowth>performance.revenueGrowth+10)risks.push(`재고 증가율 ${percent(metrics.inventoryGrowth)}가 매출 증가율보다 빠릅니다.`);
    const per=finiteNumber(dashboard.valuation?.per),industryPer=finiteNumber(dashboard.valuation?.industry_per);if(per!==null&&industryPer!==null&&per>industryPer*1.2)risks.push(`현재 PER(${multiple(per)})은 동일업종(${multiple(industryPer)})보다 높습니다.`);
    return {strengths:strengths.length?strengths.slice(0,4):["현재 자료만으로 확정할 강점이 부족합니다. 다음 공시의 추세를 확인하세요."],risks:risks.length?risks.slice(0,4):["현재 수치에서 뚜렷한 경고는 제한적이지만 업종·경쟁사 비교가 필요합니다."]};
  }

  function renderDesktopCompany(root, code, dashboard, prices, financials, sectorMargins, sgaAnalysis) {
    const performance=desktopCompanyPerformance(dashboard),metrics=desktopCompanyMetrics(dashboard,financials),statementLabel=companyStatementLabel(metrics,performance),profile=dashboard.company_profile||{},valuation=dashboard.valuation||{};
    section(root,"투자자 관점 · 기업 체력 한눈에 보기",0,13,7);headers(root,["항목","상태","값","해석"],0,14,[1,1,2,3]);
    desktopCompanySnapshotRows(dashboard,performance,metrics).forEach(([label,status,value,detail],index)=>{const row=15+index,tone=["성장","개선","양호","현금 유입","업종 대비 낮음"].includes(status)?"desk-cell-positive":["감소","둔화","적자","현금 유출","주의","업종 대비 높음"].includes(status)?"desk-cell-negative":"";addCell(root,label,0,row,{className:"desk-cell-header"});addCell(root,status,1,row,{className:tone});addCell(root,value,2,row,{cols:2,className:"desk-cell-number"});addCell(root,detail,4,row,{cols:3,title:detail});});
    addCell(root,`${statementLabel} 기준 · 성장, 수익성, 현금, 부채, 효율, 가격을 함께 비교합니다.`,0,21,{cols:7,className:"desk-cell-muted"});

    section(root,"사업 이해 · 이 회사는",7,13,5);addCell(root,profile.short_summary||profile.summary||"기업 설명을 확인할 수 없습니다.",7,14,{cols:5,rows:3,className:"desk-cell-wrap"});
    headers(root,["업종","대표자","설립일","결산월"],7,18,[2,1,1,1]);addCell(root,[profile.industry,profile.sector].filter((item,index,items)=>item&&items.indexOf(item)===index).join(" · ")||"-",7,19,{cols:2});addCell(root,profile.ceo_name,9,19);addCell(root,dateLabel(profile.established_date),10,19);addCell(root,profile.fiscal_month?`${Number(profile.fiscal_month)}월`:"-",11,19,{className:"desk-cell-number"});
    addCell(root,profile.address||"본사 주소 정보 없음",7,20,{cols:5,title:profile.address});
    if(profile.homepage_url)addCell(root,"회사 홈페이지 ↗",7,21,{cols:2,tag:"a",href:profile.homepage_url,className:"desk-cell-link"});if(profile.ir_url)addCell(root,"IR 홈페이지 ↗",9,21,{cols:2,tag:"a",href:profile.ir_url,className:"desk-cell-link"});if(profile.source_url)addCell(root,`${profile.source_label||"기업 정보"} 원문 ↗`,7,22,{cols:3,tag:"a",href:profile.source_url,className:"desk-cell-link"});

    section(root,"성장과 수익성 · 실적 분석",0,24,12);
    const metric=state.detailFinancialMetrics.get(code)||"revenue",scope=state.detailFinancialScopes.get(code)||"quarterly",metricLabels={revenue:"매출액",operating_profit:"영업이익",net_income:"순이익"};
    [["revenue","매출액"],["operating_profit","영업이익"],["net_income","순이익"]].forEach(([id,label],index)=>detailOptionButton(root,code,state.detailFinancialMetrics,"revenue",id,label,index*2,25,2));
    detailOptionButton(root,code,state.detailFinancialScopes,"quarterly","quarterly","분기",9,25);detailOptionButton(root,code,state.detailFinancialScopes,"quarterly","annual","연간",10,25);
    const series=(dashboard.financial_series?.[scope]||[]).filter((item)=>finiteNumber(item[metric])!==null),financialUnit=dashboard.financial_series?.unit||"억원",financialChart=financialBarChart(series,metric,financialUnit);
    addCell(root,financialChart||"표시할 실적 시계열이 없습니다.",0,26,{cols:8,rows:9,html:Boolean(financialChart),className:financialChart?"desk-cell-chart":"desk-cell-status"});
    const latest=series.at(-1),comparisonIndex=scope==="quarterly"&&series.length>4?series.length-5:series.length-2,previous=comparisonIndex>=0?series[comparisonIndex]:null,growth=finiteNumber(previous?.[metric])?((Number(latest?.[metric])/Number(previous[metric]))-1)*100:null;
    headers(root,["항목","값"],8,26,[2,2]);addCell(root,"선택 지표",8,27,{cols:2});addCell(root,metricLabels[metric],10,27,{cols:2});addCell(root,latest?.period||"최신",8,28,{cols:2});addCell(root,latest?financialSeriesAmount(latest[metric],financialUnit):"-",10,28,{cols:2,className:"desk-cell-number"});addCell(root,scope==="quarterly"?"전년 동기 대비":"전년 대비",8,29,{cols:2});addCell(root,growth===null?"-":percent(growth),10,29,{cols:2,className:`desk-cell-number ${changeClass(growth)}`});addCell(root,"영업이익률",8,30,{cols:2});addCell(root,latest?percent(latest.operating_margin):"-",10,30,{cols:2,className:"desk-cell-number"});addCell(root,`${dashboard.financial_series?.source||"금융 데이터"} · 단위 ${financialUnit} · E는 추정치`,8,32,{cols:4,rows:2,className:"desk-cell-wrap desk-cell-muted"});

    const breakdownRows=desktopRevenueBreakdownRows(dashboard),breakdownChart=revenueBreakdownChartSvg(dashboard),actualRows=breakdownRows.filter((item)=>!item.estimated),breakdownLatest=actualRows.at(-1)||breakdownRows.at(-1),breakdownPrevious=actualRows.length>=2?actualRows.at(-2):null,breakdownEstimate=breakdownRows.find((item)=>item.estimated&&item!==breakdownLatest);
    section(root,`수익구조 변화 · ${dashboard.name} 매출 심층 분석`,0,38,12);addCell(root,breakdownChart||"표시할 연간 매출·영업이익 자료가 없습니다.",0,39,{cols:8,rows:10,html:Boolean(breakdownChart),className:breakdownChart?"desk-cell-chart":"desk-cell-status"});
    addCell(root,"매출을 100%로 놓고 영업비용과 영업이익이 차지하는 비중을 비교합니다.",8,39,{cols:4,rows:2,className:"desk-cell-wrap desk-cell-muted"});
    if(breakdownLatest){addCell(root,`${String(breakdownLatest.period||"").match(/\d{4}/)?.[0]||"최신"}년 ${breakdownLatest.estimated?"추정":"실제"}`,8,42,{cols:4,className:"desk-cell-header"});addCell(root,`매출 100% 중 영업비용 ${number(breakdownLatest.operatingCostRate,1)}%, ${breakdownLatest.operatingMargin<0?"영업손실":"영업이익"} ${number(Math.abs(breakdownLatest.operatingMargin),1)}% 구조입니다.`,8,43,{cols:4,rows:2,className:"desk-cell-wrap"});addCell(root,`연간 매출 ${financialSeriesAmount(breakdownLatest.revenue,financialUnit)} · 영업이익률 ${ratioPercent(breakdownLatest.operatingMargin)}`,8,45,{cols:4,className:"desk-cell-muted"});if(breakdownPrevious)addCell(root,`직전 실제 연도보다 영업이익률 ${number(Math.abs(breakdownLatest.operatingMargin-breakdownPrevious.operatingMargin),2)}%p ${breakdownLatest.operatingMargin>=breakdownPrevious.operatingMargin?"개선":"하락"}`,8,46,{cols:4,className:breakdownLatest.operatingMargin>=breakdownPrevious.operatingMargin?"desk-cell-positive":"desk-cell-negative"});if(breakdownEstimate)addCell(root,`${String(breakdownEstimate.period||"").match(/\d{4}/)?.[0]}년 추정 영업이익률 ${ratioPercent(breakdownEstimate.operatingMargin)}`,8,47,{cols:4,className:"desk-cell-muted"});}

    const companies=sectorMargins?.companies||[];section(root,"업계 수익성 비교 · 동종 업계 영업이익률 추이",0,52,12);
    const sectorChart=sectorMarginLineChart(sectorMargins);addCell(root,sectorChart||"같은 업종에서 비교 가능한 실제 연간 실적이 부족합니다.",0,53,{cols:8,rows:10,html:Boolean(sectorChart),className:sectorChart?"desk-cell-chart desk-cell-sector-chart":"desk-cell-status"});
    addCell(root,sectorMargins?.basis||"동일 업종 · 매출 상위 5개사",8,53,{cols:4,className:"desk-cell-muted"});headers(root,["기업","매출순위(위)","최근 영업이익률(%)"],8,55,[2,1,1]);companies.slice(0,5).forEach((company,index)=>{const row=56+index;addCell(root,`${company.is_target?"●":"○"} ${company.name}`,8,row,{cols:2,className:company.is_target?"desk-cell-sector-target":""});addCell(root,`${number(company.revenue_rank)}위`,10,row,{className:"desk-cell-number"});addCell(root,ratioPercent(company.latest_operating_margin),11,row,{className:`desk-cell-number ${company.is_target?"desk-cell-sector-target":""}`});});addCell(root,`선택 종목 ${number(sectorMargins?.target_margin_rank)}위 / ${companies.length}개사 · 업계 중앙값 ${ratioPercent(sectorMargins?.peer_median_margin)} · 중앙값 대비 ${percent(sectorMargins?.target_margin_gap)}`,8,62,{cols:4,rows:2,className:"desk-cell-wrap desk-cell-muted"});

    section(root,`판관비 구조 · 판관비 심층분석 · ${text(sgaAnalysis?.period,"-")}년`,0,66,12);
    if(sgaAnalysis?.available&&(sgaAnalysis.categories||[]).length){headers(root,["카테고리","매출 대비(%)","금액(억원)","판관비 비중(%)","세부 계정"],0,67,[2,2,2,2,4]);(sgaAnalysis.categories||[]).slice(0,8).forEach((category,index)=>{const row=68+index,detail=sgaDetailText(category);addCell(root,`${index===0?"▰":"▱"} ${category.label}`,0,row,{cols:2,className:index===0?"desk-cell-sga-largest":""});addCell(root,ratioPercent(category.sales_ratio),2,row,{cols:2,className:"desk-cell-number"});addCell(root,financialSeriesAmount(category.amount,"억원",true),4,row,{cols:2,className:"desk-cell-number"});addCell(root,ratioPercent(category.share_of_sga,1),6,row,{cols:2,className:"desk-cell-number"});addCell(root,detail||"세부 계정 미공시",8,row,{cols:4,title:detail});});addCell(root,`판관비 ${financialSeriesAmount(sgaAnalysis.total_amount,"억원",true)} · 매출 대비 ${ratioPercent(sgaAnalysis.sales_ratio)} · 분류 일치 ${ratioPercent(sgaAnalysis.coverage_ratio,1)}`,0,76,{cols:8,className:"desk-cell-header"});if(sgaAnalysis.source_url)addCell(root,"DART 사업보고서 주석 ↗",8,76,{cols:4,tag:"a",href:sgaAnalysis.source_url,className:"desk-cell-link"});addCell(root,"연결 사업보고서 주석을 우선하며 중간합계와 연구개발 중복은 제외합니다.",0,77,{cols:12,className:"desk-cell-muted"});}else addCell(root,sgaAnalysis?.message||"사업보고서에 자동 분류 가능한 판관비 세부 주석이 없습니다.",0,67,{cols:12,className:"desk-cell-status"});

    section(root,"현금과 재무체력 · 현금 흐름 심층 분석",0,80,6);headers(root,["지표","값","상태"],0,81,[2,2,2]);
    const isFinancial=financialInstitution(dashboard),healthRows=[
      ["순차입금비율",isFinancial?"-":ratioPercent(metrics.netDebtRatio),isFinancial?"업종 별도 기준":metrics.netDebtRatio===null?"계산 자료 부족":metrics.netDebtRatio<=0?"순현금 구조":metrics.netDebtRatio<=50?"안정권":metrics.netDebtRatio<=100?"점검 필요":"부담 높음"],
      ["ROE(자기자본이익률)",ratioPercent(metrics.roe),metrics.roe===null?"계산 자료 부족":metrics.roe<0?"손실 구간":metrics.roe>=15?"자본 효율 높음":metrics.roe>=8?"자본 효율 양호":"효율 점검"],
      ["영업활동 현금흐름",companyStatementAmount(metrics.operatingCashFlow),metrics.operatingCashFlow===null?"계산 자료 부족":metrics.operatingCashFlow>=0?"현금 유입":"현금 유출"],
      ["재고보유일수",metrics.inventoryDays===null?"-":`${number(metrics.inventoryDays,0)}일`,metrics.inventoryDays===null?"재고 자료 없음":metrics.inventoryDays<=90?"회전 속도 빠름":metrics.inventoryDays<=120?"회전 속도 보통":"회전 속도 점검"],
    ];healthRows.forEach(([label,value,status],index)=>{const row=82+index;addCell(root,label,0,row,{cols:2});addCell(root,value,2,row,{cols:2,className:"desk-cell-number"});addCell(root,status,4,row,{cols:2});});
    const balanceChart=balanceCompositionSvg(metrics);addCell(root,balanceChart||"자산·부채·자본 구성 자료가 부족합니다.",0,87,{cols:6,rows:5,html:Boolean(balanceChart),className:balanceChart?"desk-cell-chart":"desk-cell-status"});addCell(root,"순차입금비율은 (차입금·사채 - 현금성자산) ÷ 자본입니다.",0,92,{cols:6,className:"desk-cell-muted"});

    section(root,"보유 현금의 변화 · 현금 사용 추적",6,80,6);const cashflowChart=cashflowWaterfallSvg(metrics);addCell(root,cashflowChart||"영업·투자·재무활동 현금흐름 자료가 모두 필요합니다.",6,81,{cols:6,rows:9,html:Boolean(cashflowChart),className:cashflowChart?"desk-cell-chart":"desk-cell-status"});addCell(root,`기말 보유 현금 ${companyStatementAmount(metrics.cash)} · 단기금융상품 포함 유동성 ${companyStatementAmount(metrics.liquidFunds)}`,6,90,{cols:6,className:"desk-cell-muted"});const coreCash=[metrics.operatingCashFlow,metrics.investingCashFlow,metrics.financingCashFlow].every((value)=>value!==null)?metrics.operatingCashFlow+metrics.investingCashFlow+metrics.financingCashFlow:null;addCell(root,`세 활동 합계 ${coreCash===null?"-":`${coreCash>0?"+":""}${companyStatementAmount(coreCash)}`} · 최종 현금 증감 ${metrics.cashChange===null?"-":`${metrics.cashChange>0?"+":""}${companyStatementAmount(metrics.cashChange)}`}`,6,91,{cols:6,className:"desk-cell-wrap"});addCell(root,"플러스는 현금 유입, 마이너스는 현금 유출입니다.",6,92,{cols:6,className:"desk-cell-muted"});

    section(root,"재무제표 비교 · 현금·안정성·효율",0,95,12);desktopCompanyMetricGroups(dashboard,performance,metrics).forEach(([groupName,rows],groupIndex)=>{const col=groupIndex*3;section(root,groupName,col,96,3);rows.forEach(([label,value,note],index)=>{const row=97+index;addCell(root,label,col,row,{cols:2,title:`${label} · ${note}`});addCell(root,value,col+2,row,{className:"desk-cell-number",title:note});});});addCell(root,`${statementLabel} 재무제표 기준 · 금액은 이해를 돕기 위해 억원/조원으로 환산했습니다.`,0,102,{cols:12,className:"desk-cell-muted"});

    section(root,"이익 대비 주가 · 밸류에이션 비교",0,105,7);const perChart=perComparisonChartSvg(dashboard,sectorMargins);addCell(root,perChart||"같은 업종에서 현재·예상 PER을 비교할 경쟁사 자료가 부족합니다.",0,106,{cols:7,rows:8,html:Boolean(perChart),className:perChart?"desk-cell-chart":"desk-cell-status"});const comparison=sectorMargins?.valuation_comparison;addCell(root,comparison?.selection_reason||"같은 업종에서 실제 연간 매출 규모가 가까운 비교 기업을 선정합니다.",0,114,{cols:7,rows:2,className:"desk-cell-wrap desk-cell-muted"});headers(root,["현재 PER(배)","예상 PER(배)","PBR(배)","EPS(원)","BPS(원)","배당수익률(%)"],0,116,[1,1,1,1,1,2]);addCell(root,multiple(valuation.per),0,117,{className:"desk-cell-number"});addCell(root,multiple(valuation.estimated_per),1,117,{className:"desk-cell-number"});addCell(root,multiple(valuation.pbr),2,117,{className:"desk-cell-number"});addCell(root,number(valuation.eps),3,117,{className:"desk-cell-number"});addCell(root,number(valuation.bps),4,117,{className:"desk-cell-number"});addCell(root,ratioPercent(valuation.dividend_yield),5,117,{cols:2,className:"desk-cell-number"});

    const checkpoints=desktopCompanyCheckpoints(dashboard,performance,metrics);section(root,"숫자 해석 · 투자 체크포인트",7,105,5);addCell(root,"확인된 강점",7,106,{cols:5,className:"desk-cell-header"});checkpoints.strengths.forEach((item,index)=>addCell(root,`• ${item}`,7,107+index,{cols:5,className:"desk-cell-wrap desk-cell-positive"}));addCell(root,"추가 확인할 점",7,112,{cols:5,className:"desk-cell-header"});checkpoints.risks.forEach((item,index)=>addCell(root,`• ${item}`,7,113+index,{cols:5,className:"desk-cell-wrap desk-cell-negative"}));addCell(root,"지표는 업종 특성과 일회성 손익에 따라 달라질 수 있습니다. 최근 추세와 동종업계 비교를 함께 확인하세요.",7,118,{cols:5,rows:2,className:"desk-cell-wrap desk-cell-muted"});
  }

  function quantTargetOutcome(event={},current={}){const status=event.target_sell_status||current.target_sell_status,delta=finiteNumber(event.target_sell_delta??current.target_sell_delta);if(status==="hit"||(delta!==null&&delta>=0))return delta>0?`목표 대비 +${number(delta)}원 초과`:"목표가 일치";if(status==="missed"||delta!==null)return`목표 대비 ${number(Math.abs(delta))}원 미달`;return"목표 대비 확인 중";}

  function desktopQuantStatusView(payload={}){
    const current=payload.current||{},events=Array.isArray(payload.events)?payload.events:[],trades=Array.isArray(payload.trades)?payload.trades:[],latest=events.at(-1)||{},action=String(current.action||"waiting"),currentPrice=current.price?`${number(current.price)}원`:"-",lifecycleExposure=`${number(current.model_exposure_percent||0)}%`,signalScore=current.score===null||current.score===undefined?"-":`${number(current.score)}점`;
    const baseRows=[["현재가",currentPrice],["종합 신호",signalScore],["전략 잔여비중",lifecycleExposure]];
    if(action==="entry_watch")return{headline:"예비 매수 포착",next:current.next_confirmation||"다음 매수 확정 조건을 확인하고 있어요.",tone:"buy",rows:baseRows};
    if(action==="entry_pending")return{headline:"매수 대기중",next:current.next_confirmation||"다음 거래일 시가의 갭을 확인한 뒤 매수 신호로 반영할 예정이에요.",tone:"buy",rows:[...baseRows,["최근 신호","매수 조건 확정"]]};
    if(["partial_exit_pending","full_exit_pending"].includes(action)){
      const partial=action==="partial_exit_pending",decisionPrice=partial?(current.partial_exit_reference||current.target_sell_price):(current.stop_reference||current.locked_profit_reference||current.target_sell_price);
      return{headline:partial?`${number(current.pending_profit_stage||(Number(current.profit_stage||0)+1))}차 수익확정 대기중`:"전량 매도 대기중",next:current.next_confirmation||(partial?"다음 거래일 시가에 수익확정으로 반영할 예정이에요.":"다음 거래일 시가에 전량 매도로 반영할 예정이에요."),tone:"sell",rows:[["현재가",currentPrice],[partial?"다음 수익확정가":"수익 보호선",decisionPrice?`${number(decisionPrice)}원`:"-"],["전략 잔여비중",lifecycleExposure],["매수 후 수익률",percent(current.unrealized_return)]]};
    }
    if(current.position_open||["entered","holding","partially_exited"].includes(action)||["buy","partial_sell"].includes(latest.side)){
      const partial=action==="partially_exited"||latest.side==="partial_sell",actionDate=current.partial_exit_date||current.entry_date||latest.execution_date,actionPrice=current.partial_exit_price||current.entry_price||latest.price,nextTarget=current.partial_exit_reference||current.target_sell_price,protection=current.stop_reference||current.locked_profit_reference;
      return{headline:partial?`${number(current.profit_stage||latest.profit_stage||1)}차 수익확정 후 보유중`:"매수 후 보유중",next:current.next_confirmation||"다음 매도 신호를 확인하고 있어요.",tone:"hold",rows:[[partial?"최근 수익확정일":"매수일",dateLabel(actionDate)],[partial?`${number(current.profit_stage||1)}차 확정가`:"매수가",actionPrice?`${number(actionPrice)}원`:"-"],[nextTarget?"다음 수익확정가":"수익확정 단계",nextTarget?`${number(nextTarget)}원`:`${number(current.profit_stage||0)} / ${number(current.profit_steps_total||3)}단계`],["수익 보호선",protection?`${number(protection)}원`:"-"],["전략 잔여비중",lifecycleExposure],[partial?"이번 매매 수익률":"매수 후 수익률",percent(current.unrealized_return)]]};
    }
    if(action==="exited"||latest.side==="sell"){
      const tradeReturn=latest.return_rate??trades[0]?.net_return;
      return{headline:"전량 매도 후 대기중",next:"현재는 미보유 상태이며, 다음 매수 신호를 기다리고 있어요.",tone:"sell",rows:[["매도일",dateLabel(latest.execution_date||current.exit_date)],["매도 가격",latest.price||current.exit_price?`${number(latest.price||current.exit_price)}원`:"-"],["전량 매도 기준가",latest.target_sell_price||current.target_sell_price?`${number(latest.target_sell_price||current.target_sell_price)}원`:"-"],["매도 판단",latest.reason||current.reasons?.[0]||"전량 매도 기준 충족"],["해당 매매",percent(tradeReturn)],["전략 잔여비중","0%"]]};
    }
    return{headline:"관망 중",next:current.next_confirmation||"현재는 새 매수 신호를 기다리고 있어요.",tone:"hold",rows:[...baseRows,["최근 신호","없음"]]};
  }

  function quantSignalChartSvg(payload,prices,quote){
    const rows=normalizePriceRows(prices,quote).slice(-260);if(payload?.data_state!=="ready"||rows.length<2)return"";
    const width=920,height=330,left=58,right=20,top=28,bottom=270,values=rows.map((row)=>row.close),rawMin=Math.min(...values),rawMax=Math.max(...values),pad=Math.max(1,(rawMax-rawMin)*.12),min=Math.max(0,rawMin-pad),max=rawMax+pad,x=(index)=>left+index*((width-left-right)/Math.max(1,rows.length-1)),y=(value)=>top+((max-value)/(max-min||1))*(bottom-top),line=rows.map((row,index)=>`${index?"L":"M"}${x(index).toFixed(1)},${y(row.close).toFixed(1)}`).join(" ");
    const grid=[0,.333,.666,1].map((ratio)=>{const gy=top+(bottom-top)*ratio,value=max-(max-min)*ratio;return`<line class="desk-price-grid" x1="${left}" y1="${gy}" x2="${width-right}" y2="${gy}"></line><text class="desk-price-axis" x="${left-8}" y="${gy+4}" text-anchor="end">${number(value)}</text>`;}).join("");
    const markers=(payload.events||[]).map((event)=>{const date=String(event.execution_date||event.signal_date||"").slice(0,10),index=rows.findIndex((row)=>row.date>=date);if(index<0)return"";const side=event.side==="buy"?"buy":event.side==="partial_sell"?"partial":"sell",label=event.side==="buy"?"확정 매수":event.side==="partial_sell"?event.label||`${number(event.profit_stage||1)}차 수익확정`:"전량 매도",tip=`${dateLabel(date)} · ${label} ${number(event.price)}원${event.return_rate===null||event.return_rate===undefined?"":` · 수익률 ${percent(event.return_rate)}`} · ${event.reason||"판단 근거 확인"}`;return`<path class="desk-quant-marker ${side}" d="M${x(index).toFixed(1)},${(y(rows[index].close)-9).toFixed(1)} l-7,-11 h14 Z" ${chartPointAttributes(tip)}></path>`;}).join("");
    const hitStep=Math.max(1,Math.ceil(rows.length/80)),hits=rows.map((row,index)=>index%hitStep&&index!==rows.length-1?"":`<circle class="desk-chart-hit" cx="${x(index).toFixed(1)}" cy="${y(row.close).toFixed(1)}" r="7" ${chartPointAttributes(`${dateLabel(row.date)} · 실제 ${number(row.close)}원`)}></circle>`).join("");
    return`<svg class="desk-quant-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 1년 가격과 AI 매매 시점">${grid}<path class="desk-quant-area" d="${line} L${x(rows.length-1).toFixed(1)},${bottom} L${x(0).toFixed(1)},${bottom} Z"></path><path class="desk-quant-line" d="${line}"></path>${markers}${hits}</svg>`;
  }

  function renderDesktopAISignal(root,code,dashboard,prices,payload){
    if(payload?.data_state!=="ready"){section(root,"AI 시그널",0,13,12);addCell(root,payload?.data_message||"AI 시그널을 계산할 가격 데이터가 부족합니다.",0,14,{cols:12,className:"desk-cell-status"});return;}
    const status=desktopQuantStatusView(payload),performance=payload.performance||{},current=payload.current||{};
    section(root,"AI 지금 이렇게 판단해요",0,13,10);detailActionButton(root,"새로고침",10,13,2,async()=>{setStatus(`${dashboard.name} AI 시그널 다시 계산 중…`);try{const refreshed=await api(`/stocks/${encodeURIComponent(code)}/quant-signals?refresh=1`);state.cache.set(`/stocks/${code}/quant-signals`,{at:Date.now(),data:refreshed});await activate(`detail:${code}`,{replaceHistory:true});}catch(error){setStatus(`AI 시그널 갱신 실패 · ${error.message}`);}},{ariaLabel:`${dashboard.name} AI 시그널 새로고침`});
    addCell(root,status.headline,0,14,{cols:3,className:`desk-cell-signal-state desk-badge-${status.tone}`});addCell(root,status.next,3,14,{cols:9,className:"desk-cell-wrap"});headers(root,["항목","값","항목","값","항목","값"],0,16,[1,3,1,3,1,3]);status.rows.slice(0,6).forEach(([label,value],index)=>{const group=index%3,row=17+Math.floor(index/3),col=group*4;addCell(root,label,col,row,{className:"desk-cell-header"});addCell(root,value,col+1,row,{cols:3,className:`desk-cell-number ${String(value).startsWith("+")?"desk-cell-positive":String(value).startsWith("-")?"desk-cell-negative":""}`});});addCell(root,`신호 판단 ${dateLabel(current.as_of||payload.as_of)} · ${payload.signal_source==="canonical"?"공통 기준 시그널":"로컬 계산"}`,0,20,{cols:12,className:"desk-cell-muted"});

    section(root,"신호 판단 시점 · 최근 1년 AI 시그널",0,23,12);const chart=quantSignalChartSvg(payload,prices,dashboard.quote);addCell(root,chart||"매매신호 차트를 만들 가격 데이터가 부족합니다.",0,24,{cols:12,rows:11,html:Boolean(chart),className:chart?"desk-cell-chart":"desk-cell-status"});addCell(root,"● 매수 · ● 일부 매도 · ● 매도 · 차트의 점과 신호에 마우스를 올리면 상세값을 확인할 수 있습니다.",0,35,{cols:12,className:"desk-cell-muted"});

    section(root,"같은 규칙으로 계산 · 최근 1년 전략 결과",0,38,12);headers(root,["1년 모의 누적수익률(%)","최대 낙폭(%)","연환산 변동성(%)","평균 전략 보유비중(%)","매매 적중률(%)","완료 매매(회)","체결 횟수(회)"],0,39,[2,2,2,2,2,1,1]);addCell(root,percent(performance.strategy_return),0,40,{cols:2,className:`desk-cell-number ${changeClass(performance.strategy_return)}`});addCell(root,percent(performance.max_drawdown),2,40,{cols:2,className:"desk-cell-number desk-cell-negative"});addCell(root,percent(performance.annualized_volatility),4,40,{cols:2,className:"desk-cell-number"});addCell(root,percent(performance.average_model_exposure_percent),6,40,{cols:2,className:"desk-cell-number"});addCell(root,performance.win_rate==null?"-":`${number(performance.win_rate,1)}%`,8,40,{cols:2,className:"desk-cell-number"});addCell(root,`${number(performance.completed_trades||0)}회`,10,40,{className:"desk-cell-number"});addCell(root,`${number(performance.execution_count||(payload.events||[]).length)}회`,11,40,{className:"desk-cell-number"});addCell(root,`${performance.period_start||"최근 1년"} ~ ${performance.period_end||""} · 회전율 ${number(performance.turnover_percent||0,1)}% · ${performance.sample_note||"같은 규칙을 최근 1년 가격에 적용한 결과입니다."}`,0,42,{cols:12,className:"desk-cell-muted"});

    section(root,"모든 매매내역 보기",0,45,12);headers(root,["체결일","구분","체결가(원)","수익확정·기준가(원)","기준 결과","수익률(%)","보유 상태","판단 이유"],0,46,[1,1,2,2,2,1,1,2]);const events=(payload.events||[]).slice().reverse();events.slice(0,16).forEach((event,index)=>{const row=47+index,side=event.side==="buy"?"확정 매수":event.side==="partial_sell"?event.label||`${number(event.profit_stage||1)}차 수익확정`:"전량 매도",remaining=event.side==="partial_sell"?`잔여 ${number(event.position_percent)}%`:event.side==="sell"?"보유 종료":"보유 100%";addCell(root,dateLabel(event.execution_date||event.signal_date),0,row);addCell(root,side,1,row,{className:event.side==="buy"?"desk-cell-positive":"desk-cell-negative"});addCell(root,event.price?`${number(event.price)}원`:"-",2,row,{cols:2,className:"desk-cell-number"});addCell(root,event.target_sell_price?`${number(event.target_sell_price)}원`:"-",4,row,{cols:2,className:"desk-cell-number"});addCell(root,quantTargetOutcome(event,current),6,row,{cols:2});addCell(root,event.return_rate==null?"-":percent(event.return_rate),8,row,{className:`desk-cell-number ${changeClass(event.return_rate)}`});addCell(root,remaining,9,row);addCell(root,event.reason||"-",10,row,{cols:2,title:event.reason});});if(!events.length)addCell(root,"최근 1년 매매내역이 없습니다.",0,47,{cols:12,className:"desk-cell-status"});
    section(root,"계산 기준",0,65,12);(payload.methodology||[]).slice(0,8).forEach((item,index)=>addCell(root,`• ${item}`,0,66+index,{cols:12,className:"desk-cell-wrap"}));addCell(root,payload.disclaimer||"AI가 과거 데이터로 계산한 교육·연구용 참고 신호이며, 투자 권유·자문·수익 보장 또는 실제 주문이 아닙니다.",0,75,{cols:12,rows:2,className:"desk-cell-wrap desk-cell-status"});
  }

  function renderLoading(label) {
    const root = grid(); sheetTitle(root, label, "데이터 불러오는 중"); statusRow(root, "서버에서 최신 데이터를 가져오고 있습니다…", 3); elements.sheet.replaceChildren(root);
  }

  async function loadDesktopMarketSignals30d() {
    const path = "/market/quant-signals?universe_limit=150&limit=0&recent_days=30";
    const retryDelays = [0, 1200, 2500];
    let payload = null;
    for (let index = 0; index < retryDelays.length; index += 1) {
      if (retryDelays[index]) await new Promise((resolve) => window.setTimeout(resolve, retryDelays[index]));
      if (index > 0) state.cache.delete(path);
      payload = await cached(path, index > 0 ? 0 : 120000);
      if (payload?.status !== "preparing") return payload;
    }
    return payload || { status: "preparing", recent_days: 30, items: [] };
  }

  function desktopMarketSignalLabel(item = {}) {
    const universeLabel = String(item.universe_tier || "").toLowerCase() === "extended"
      ? (item.universe_tracking_state === "retained" ? "확장·유지" : "확장")
      : item.universe_tracking_state === "retained" ? "진행 유지" : "";
    const withUniverse = (label) => universeLabel ? `${universeLabel} · ${label}` : label;
    if (item.signal) return withUniverse(item.signal);
    const side = String(item.side || "").toLowerCase();
    const preliminary = item.is_preliminary === true || item.status === "preliminary";
    if (side === "buy") return withUniverse(preliminary ? "예비 매수" : "확정 매수");
    if (side === "sell") return withUniverse(preliminary ? "예비 매도" : "확정 매도");
    return withUniverse("확인 중");
  }

  function desktopMarketSignalState(item = {}) {
    if (item.is_preliminary === true || item.status === "preliminary") return "15:40 확정 전";
    const targetStatus = String(item.target_sell_status || "");
    if (targetStatus === "hit") return "목표가 도달";
    if (targetStatus === "missed") return "목표가 미달";
    if (targetStatus === "planned") return "목표가 추적 중";
    if (String(item.side || "").toLowerCase() === "sell") return "매도 완료";
    return "확정";
  }

  function desktopMarketSignalStage(item = {}) {
    const side = String(item.side || item.current?.lifecycle?.latest_transition?.side || "").toLowerCase();
    const action = String(item.current?.action || item.action || "").toLowerCase();
    const preliminary = item.is_preliminary === true || item.status === "preliminary" || ["entry_watch", "entry_pending", "partial_exit_pending", "full_exit_pending"].includes(action);
    if (preliminary && side === "sell") return "preliminary-sell";
    if (preliminary) return "preliminary-buy";
    if (side === "sell" || action === "exited") return "recent-sell";
    return "buy-holding";
  }

  function desktopMarketSignalSector(item = {}) {
    return String(item.investment_sector || item.sector || item.industry || "other").trim() || "other";
  }

  function desktopMarketSignalSectorLabel(item = {}) {
    return text(item.investment_sector_label || item.sector || item.industry, "기타");
  }

  function morningMoneyEditionPresentation(payload = {}) {
    return {
      morning: { kicker: "오전판 · 06:00 발행", title: "밤사이 핵심만 빠르게" },
      midday: { kicker: "점심판 · 12:00 발행", title: "오전 핵심을 새로 정리했어요" },
      afternoon: { kicker: "오후판 · 16:00 발행", title: "오후 핵심을 새로 정리했어요" },
    }[payload.edition] || { kicker: payload.edition_label || "최신판", title: "핵심 소식을 새로 정리했어요" };
  }

  function desktopMorningMoneyItems(payload = {}) {
    return (payload.categories || []).flatMap((category) => (category.items || []).map((item) => ({
      ...item,
      categoryKey: category.key,
      categoryLabel: category.label,
      categoryIcon: category.icon,
    })));
  }

  function renderDesktopMorningMoneyPreview(root, payload = {}, col = 16, row = 22) {
    const presentation = morningMoneyEditionPresentation(payload);
    section(root, "오늘의 돈이 되는 소식", col, row, 8);
    addCell(root, presentation.kicker, col, row + 1, { cols: 3, className: "desk-cell-muted" });
    addCell(root, presentation.title, col + 3, row + 1, { cols: 3, className: "desk-cell-wrap" });
    addCell(root, "전체 브리핑 열기 ›", col + 6, row + 1, { cols: 2, className: "desk-cell-link desk-cell-center", click: () => openUtilitySheet("briefing") });
    headers(root, ["분류", "핵심 소식", "요약"], col, row + 3, [2, 3, 3]);
    const items = desktopMorningMoneyItems(payload).slice(0, 8);
    if (!items.length) {
      addCell(root, payload.empty_message || "뉴스 수집이 완료되면 이 화면에 자동으로 반영됩니다.", col, row + 4, { cols: 8, className: "desk-cell-status" });
      return;
    }
    items.forEach((item, index) => {
      const itemRow = row + 4 + index;
      addCell(root, `${item.categoryIcon || "📰"} ${item.categoryLabel || "주요 소식"}`, col, itemRow, { cols: 2 });
      const href = safeExternalUrl(item.detail_url);
      addCell(root, item.title, col + 2, itemRow, { cols: 3, tag: href ? "a" : "div", href, className: href ? "desk-cell-link" : "", title: item.title });
      addCell(root, item.summary || item.why_it_matters || "요약 확인 중", col + 5, itemRow, { cols: 3, title: item.summary || item.why_it_matters });
    });
  }

  function desktopHomeMarketContexts(trends = {}, impact = {}, usSectors = {}) {
    const contexts = [];
    const upcoming = (trends.events || [])[0];
    if (upcoming) contexts.push({ label: "예정", title: upcoming.title, detail: upcoming.expected_impact, asOf: upcoming.starts_at });
    const timeline = (trends.timeline || []).find((item) => item.title);
    if (timeline) contexts.push({ label: timeline.impact || "시장", title: timeline.title, detail: `${timeline.source || "시장 뉴스"} · ${timeline.category || "주요 이슈"}`, asOf: timeline.published_at });
    const factor = (impact.factors || []).slice().sort((a, b) => Number(b.confidence || 0) - Number(a.confidence || 0))[0];
    if (factor) contexts.push({ label: factor.direction || "영향", title: factor.label, detail: factor.interpretation, asOf: impact.as_of });
    const sector = (usSectors.items || []).filter((item) => Number.isFinite(Number(item.change_rate))).sort((a, b) => Math.abs(Number(b.change_rate)) - Math.abs(Number(a.change_rate)))[0];
    if (sector) contexts.push({ label: usSectors.market_session_label || "미국 섹터", title: `${sector.label || sector.symbol} ${percent(sector.change_rate)}`, detail: "국내 관련 종목의 수급과 시가를 함께 확인하세요.", asOf: usSectors.as_of });
    return contexts.slice(0, 3);
  }

  function desktopWatchlistResponseRows(identity = {}, contexts = []) {
    const signals = identity.watchSignals?.items || [];
    const watchlist = identity.watchlist?.items || [];
    const byCode = new Map(signals.map((item) => [String(item.code), item]));
    const rows = watchlist.slice(0, 5).map((item) => {
      const signal = byCode.get(String(item.code)) || {};
      const current = signal.current || {};
      const headline = current.label || current.action || "관망";
      const response = current.next_confirmation || current.reasons?.[0] || contexts[0]?.detail || "실시간 시세와 수급 변화를 확인하세요.";
      return { ...item, headline, response };
    });
    if (!rows.length && signals.length) {
      return signals.slice(0, 5).map((signal) => ({ code: signal.code, name: signal.name, headline: signal.current?.label || "관망", response: signal.current?.next_confirmation || signal.data_message }));
    }
    return rows;
  }

  function renderDesktopHomeAiResponse(root, payload = {}, col = 16, row = 3) {
    const contexts = desktopHomeMarketContexts(payload.trends, payload.impact, payload.usSectors);
    const responses = desktopWatchlistResponseRows(payload.identity, contexts);
    const asOf = contexts.map((item) => item.asOf).find(Boolean) || payload.trends?.as_of || payload.impact?.as_of;
    section(root, "AI 관심종목 대응", col, row, 8);
    addCell(root, asOf ? `${dateLabel(asOf)} 업데이트` : "실시간 변수 확인 중", col + 6, row, { cols: 2, className: "desk-cell-muted desk-cell-number" });
    headers(root, ["구분", "관심종목에 중요한 변화", "확인할 점"], col, row + 1, [1, 3, 4]);
    if (!contexts.length) addCell(root, "관심종목의 큰 변수를 확인하고 있습니다.", col, row + 2, { cols: 8, className: "desk-cell-status" });
    contexts.forEach((context, index) => {
      const contextRow = row + 2 + index;
      addCell(root, context.label, col, contextRow, { className: "desk-cell-header" });
      addCell(root, context.title, col + 1, contextRow, { cols: 3, className: "desk-cell-wrap", title: context.title });
      addCell(root, context.detail, col + 4, contextRow, { cols: 4, className: "desk-cell-wrap", title: context.detail });
    });
    section(root, "관심종목 맞춤 대응", col, row + 6, 6);
    addCell(root, "관심종목 전체보기", col + 6, row + 6, { cols: 2, className: "desk-cell-link desk-cell-center", click: () => activate("portfolio") });
    headers(root, ["종목", "현재 판단", "지금 할 일"], col, row + 7, [2, 2, 4]);
    if (!responses.length) addCell(root, "관심종목을 등록하면 시장 변수와 연결한 대응을 표시합니다.", col, row + 8, { cols: 8, className: "desk-cell-status" });
    responses.slice(0, 5).forEach((item, index) => {
      const responseRow = row + 8 + index;
      addCell(root, item.name || item.code, col, responseRow, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) });
      addCell(root, item.headline, col + 2, responseRow, { cols: 2 });
      addCell(root, item.response, col + 4, responseRow, { cols: 4, title: item.response });
    });
  }

  async function renderDesktopMorningMoneyBriefing(token) {
    renderLoading("돈이 되는 소식");
    try {
      const payload = await cached("/briefings/morning-money", 900000);
      if (token !== state.renderToken) return;
      const root = grid(), presentation = morningMoneyEditionPresentation(payload);
      sheetTitle(root, "오늘의 돈이 되는 소식", `${presentation.kicker} · ${dateLabel(payload.publication_date)}`);
      addCell(root, presentation.title, 0, 3, { cols: 8, rows: 2, className: "desk-cell-title desk-cell-wrap" });
      addCell(root, `${number(payload.selected_news_count || 0)}개 핵심 소식 · 공개 뉴스를 빠르게 훑기 위한 요약입니다.`, 8, 3, { cols: 4, rows: 2, className: "desk-cell-wrap desk-cell-status" });
      let cursor = 7;
      const categories = payload.categories || [];
      if (!categories.length) addCell(root, payload.empty_message || "아직 모인 소식이 없습니다.", 0, cursor, { cols: 12, className: "desk-cell-status" });
      categories.forEach((category) => {
        section(root, `${category.icon || "📰"} ${category.label || "주요 소식"}`, 0, cursor, 12);
        addCell(root, category.description || `${number(category.count || (category.items || []).length)}개 핵심 소식`, 8, cursor, { cols: 4, className: "desk-cell-muted" });
        cursor += 1;
        headers(root, ["발표·보도", "핵심 소식", "요약", "투자자가 확인할 점"], 0, cursor, [2, 4, 3, 3]);
        cursor += 1;
        (category.items || []).forEach((item) => {
          const href = safeExternalUrl(item.detail_url);
          addCell(root, item.published_at ? dateLabel(item.published_at) : item.status || "-", 0, cursor, { cols: 2 });
          addCell(root, item.title, 2, cursor, { cols: 4, tag: href ? "a" : "div", href, className: href ? "desk-cell-link" : "", title: item.title });
          addCell(root, item.summary || "-", 6, cursor, { cols: 3, className: "desk-cell-wrap", title: item.summary });
          addCell(root, item.why_it_matters || "원문과 최신 시세를 함께 확인하세요.", 9, cursor, { cols: 3, className: "desk-cell-wrap", title: item.why_it_matters });
          cursor += 2;
        });
        cursor += 1;
      });
      addCell(root, "※ 공개 뉴스를 빠르게 훑기 위한 요약입니다. 거래 전 원문·공시와 최신 시세를 확인하세요.", 0, Math.min(cursor, 137), { cols: 12, className: "desk-cell-status desk-cell-wrap" });
      elements.sheet.replaceChildren(root); setStatus(`${presentation.kicker} 브리핑 완료`);
    } catch (error) { renderError("돈이 되는 소식을 불러오지 못했습니다.", error); }
  }

  async function renderDesktopSignals(token) {
    renderLoading("AI 시그널");
    try {
      const payload = await loadDesktopMarketSignals30d();
      if (token !== state.renderToken) return;
      const allItems = Array.isArray(payload.items) ? payload.items : [];
      const sectors = new Map();
      allItems.forEach((item) => sectors.set(desktopMarketSignalSector(item), desktopMarketSignalSectorLabel(item)));
      if (state.marketSignalSector !== "all" && !sectors.has(state.marketSignalSector)) state.marketSignalSector = "all";
      const filtered = allItems.filter((item) => (state.marketSignalStage === "all" || desktopMarketSignalStage(item) === state.marketSignalStage) && (state.marketSignalSector === "all" || desktopMarketSignalSector(item) === state.marketSignalSector));
      const root = grid(); sheetTitle(root, "AI 시그널", `최근 30일 · ${number(filtered.length)} / ${number(allItems.length)}개`);
      const stages = [["all", "전체"], ["buy-holding", "확정 매수·보유"], ["recent-sell", "확정 매도"], ["preliminary-buy", "예비 매수"], ["preliminary-sell", "예비 매도"]];
      let stageCol = 0;
      stages.forEach(([id, label]) => { const width = id === "buy-holding" ? 3 : 2; const count = id === "all" ? allItems.length : allItems.filter((item) => desktopMarketSignalStage(item) === id).length; sheetOptionButton(root, id, `${label} ${count}`, stageCol, 3, width, state.marketSignalStage === id, () => { state.marketSignalStage = id; activate("signals", { replaceHistory: true }); }, { role: "tab" }); stageCol += width; });
      const sectorOptions = [["all", "전체 섹터"], ...Array.from(sectors.entries())].slice(0, 12);
      sectorOptions.forEach(([id, label], index) => sheetOptionButton(root, id, label, index * 2, 5, 2, state.marketSignalSector === id, () => { state.marketSignalSector = id; activate("signals", { replaceHistory: true }); }));
      headers(root, ["종목", "코드", "섹터", "신호", "점수(점)", "신호일", "체결일", "체결가(원)", "목표 매도가(원)", "현재 상태"], 0, 8, [2,1,2,2,1,1,1,2,2,2]);
      if (payload.status === "preparing") addCell(root, "최근 30일 시장 AI 시그널을 준비하고 있습니다.", 0, 9, { cols: 16, className: "desk-cell-status" });
      if (payload.status !== "preparing" && !filtered.length) addCell(root, "선택한 조건의 AI 시그널이 없습니다.", 0, 9, { cols: 16, className: "desk-cell-status" });
      filtered.slice(0, 128).forEach((item, index) => {
        const itemRow = 9 + index;
        addCell(root, item.name, 0, itemRow, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) }); addCell(root, item.code, 2, itemRow); addCell(root, desktopMarketSignalSectorLabel(item), 3, itemRow, { cols: 2 });
        addCell(root, desktopMarketSignalLabel(item), 5, itemRow, { cols: 2, className: String(item.side).toLowerCase() === "sell" ? "desk-cell-negative" : "desk-cell-positive" }); addCell(root, number(item.score, 1), 7, itemRow, { className: "desk-cell-number" });
        addCell(root, dateLabel(item.signal_date), 8, itemRow); addCell(root, dateLabel(item.execution_date), 9, itemRow); addCell(root, number(item.price), 10, itemRow, { cols: 2, className: "desk-cell-number" }); addCell(root, number(item.target_sell_price), 12, itemRow, { cols: 2, className: "desk-cell-number" }); addCell(root, desktopMarketSignalState(item), 14, itemRow, { cols: 2, title: item.reason });
      });
      elements.sheet.replaceChildren(root); setStatus(`AI 시그널 ${filtered.length}개 표시`);
    } catch (error) { renderError("AI 시그널을 불러오지 못했습니다.", error); }
  }

  async function renderDesktopMovers(token) {
    renderLoading("급등주");
    try {
      const marketQuery = state.moversMarket === "ALL" ? "" : `&market=${encodeURIComponent(state.moversMarket)}`;
      const payload = await cached(`/market/rankings?category=surge&limit=60${marketQuery}`, 60000);
      if (token !== state.renderToken) return;
      const allItems = payload.items || [], sectors = new Map();
      allItems.forEach((item) => sectors.set(String(item.investment_sector || item.sector || "other"), text(item.investment_sector_label || item.sector, "기타")));
      if (state.moversSector !== "all" && !sectors.has(state.moversSector)) state.moversSector = "all";
      const items = allItems.filter((item) => state.moversSector === "all" || String(item.investment_sector || item.sector || "other") === state.moversSector);
      const root = grid(); sheetTitle(root, "급등주", `${state.moversMarket} · ${dateLabel(payload.as_of)} · ${number(items.length)}개`);
      [["ALL", "전체"], ["KOSPI", "KOSPI"], ["KOSDAQ", "KOSDAQ"]].forEach(([id, label], index) => sheetOptionButton(root, id, label, index * 2, 3, 2, state.moversMarket === id, () => { state.moversMarket = id; state.moversSector = "all"; activate("movers", { replaceHistory: true }); }, { role: "tab" }));
      [["all", "전체 섹터"], ...Array.from(sectors.entries())].slice(0, 12).forEach(([id, label], index) => sheetOptionButton(root, id, label, index * 2, 5, 2, state.moversSector === id, () => { state.moversSector = id; activate("movers", { replaceHistory: true }); }));
      headers(root, ["순위(위)", "종목", "코드", "시장", "섹터", "현재가(원)", "등락률(%)", "1개월 수익률(%)", "3개월 수익률(%)", "거래대금(원)"], 0, 8, [1,2,1,1,2,2,2,2,2,2]);
      if (!items.length) addCell(root, "선택한 시장·섹터의 급등주가 없습니다.", 0, 9, { cols: 17, className: "desk-cell-status" });
      items.slice(0, 120).forEach((item, index) => { const itemRow = 9 + index; addCell(root, item.rank || index + 1, 0, itemRow, { className: "desk-cell-center" }); addCell(root, item.name, 1, itemRow, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) }); addCell(root, item.code, 3, itemRow); addCell(root, item.market, 4, itemRow); addCell(root, text(item.investment_sector_label || item.sector, "기타"), 5, itemRow, { cols: 2 }); markLiveCell(addCell(root, number(item.price), 7, itemRow, { cols: 2, className: "desk-cell-number" }), item.code, "price", item.price, "number"); markLiveCell(addCell(root, percent(item.change_rate), 9, itemRow, { cols: 2, className: `desk-cell-number ${changeClass(item.change_rate)}` }), item.code, "change_rate", item.change_rate, "percent"); addCell(root, percent(item.one_month_return), 11, itemRow, { cols: 2, className: `desk-cell-number ${changeClass(item.one_month_return)}` }); addCell(root, percent(item.three_month_return), 13, itemRow, { cols: 2, className: `desk-cell-number ${changeClass(item.three_month_return)}` }); addCell(root, shortMoney(item.trading_value), 15, itemRow, { cols: 2, className: "desk-cell-number" }); registerLiveQuote(item.code, { quote: { price: item.price, change_rate: item.change_rate } }); });
      elements.sheet.replaceChildren(root); setStatus(`급등주 ${items.length}개 · 실시간 연결 중`);
    } catch (error) { renderError("급등주를 불러오지 못했습니다.", error); }
  }

  async function renderHome(token) {
    renderLoading("홈");
    try {
      const identityRequest = state.watchlistId ? Promise.all([
        api(`/watchlists/${encodeURIComponent(state.watchlistId)}`).catch(() => ({ items: readLocalWatchlist() })),
        api(`/watchlists/${encodeURIComponent(state.watchlistId)}/quant-signals`).catch(() => ({ items: [] })),
      ]).then(([watchlist, watchSignals]) => ({ watchlist, watchSignals })) : Promise.resolve({ watchlist: { items: readLocalWatchlist() }, watchSignals: { items: [] } });
      const [indices, recs, rankings, trends, impact, signals, globalAssets, briefing, usSectors, identity] = await Promise.all([
        cached("/market/indices?limit=30", 30000), cached("/market/recommendations?limit=8", 120000),
        cached("/market/rankings?category=surge&limit=30", 60000), cached("/market/trends?days=7", 120000),
        cached("/market/impact", 120000).catch(() => null), loadDesktopMarketSignals30d().catch(() => ({ status: "error", items: [] })),
        cached("/market/global-assets?limit=30", 60000).catch(() => ({ items: [] })),
        cached("/briefings/morning-money", 900000).catch(() => ({ categories: [], empty_message: "브리핑을 준비하고 있습니다." })),
        cached("/market/us-sector-moves", 120000).catch(() => ({ items: [] })),
        identityRequest,
      ]);
      if (token !== state.renderToken) return;
      const root = grid(), liveSeeds = new Map(); sheetTitle(root, "홈", `실시간 연결 · ${new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}`);
      section(root, "시장 지수", 0, 3, 8); headers(root, ["지수", "현재(포인트)", "등락(포인트)", "등락률(%)", "30일 흐름(포인트)"], 0, 4, [1,1,1,1,4]);
      (indices.items || []).slice(0, 3).forEach((item, index) => {
        const row = 5 + index, marketCode = item.code || item.name || item.label; addCell(root, item.label || item.code, 0, row);
        markMarketCell(addCell(root, number(item.current, 2), 1, row, { className: "desk-cell-number" }), "indices", marketCode, "current", item.current, "number-2");
        markMarketCell(addCell(root, number(item.change, 2), 2, row, { className: `desk-cell-number ${changeClass(item.change)}` }), "indices", marketCode, "change", item.change, "number-2");
        markMarketCell(addCell(root, percent(item.change_rate), 3, row, { className: `desk-cell-number ${changeClass(item.change_rate)}` }), "indices", marketCode, "change_rate", item.change_rate, "percent");
        addCell(root, sparkline(item.points, Number(item.change_rate) < 0 ? "#1967d2" : "#d93025", "포인트"), 4, row, { cols: 4, html: true, className: "desk-cell-chart" });
      });

      section(root, "AI 주목 종목", 0, 10, 7); headers(root, ["순위(위)", "종목", "코드", "판단", "점수(점)", "현재가(원)", "등락률(%)"], 0, 11);
      (recs.items || []).slice(0, 8).forEach((item, index) => {
        const row = 12 + index; addCell(root, item.rank || index + 1, 0, row, { className: "desk-cell-center" });
        addCell(root, item.name, 1, row, { className: "desk-cell-link", click: () => openDetail(item) }); addCell(root, item.code, 2, row);
        const action = text(item.action, "관망"); const badgeClass = /매수|buy/i.test(action) ? "buy" : /매도|sell/i.test(action) ? "sell" : "hold";
        addCell(root, `<span class="desk-badge desk-badge-${badgeClass}">${action}</span>`, 3, row, { html: true, className: "desk-cell-center" });
        addCell(root, number(item.score, 1), 4, row, { className: "desk-cell-number" });
        markLiveCell(addCell(root, number(item.price), 5, row, { className: "desk-cell-number" }), item.code, "price", item.price, "number");
        markLiveCell(addCell(root, percent(item.change_rate), 6, row, { className: `desk-cell-number ${changeClass(item.change_rate)}` }), item.code, "change_rate", item.change_rate, "percent");
        if (item.code) liveSeeds.set(String(item.code), { quote: { price: item.price, change_rate: item.change_rate } });
      });

      const moversTitle = section(root, "급등주", 10, 3, 6); moversTitle.classList.add("desk-cell-link"); moversTitle.addEventListener("click", () => openUtilitySheet("movers"));
      headers(root, ["순위(위)", "종목", "현재가(원)", "등락률(%)"], 10, 4, [1,2,1,2]);
      (rankings.items || []).slice(0, 10).forEach((item, index) => {
        const row = 5 + index; addCell(root, item.rank || index + 1, 10, row, { className: "desk-cell-center" });
        addCell(root, item.name, 11, row, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) });
        markLiveCell(addCell(root, number(item.price), 13, row, { className: "desk-cell-number" }), item.code, "price", item.price, "number");
        markLiveCell(addCell(root, percent(item.change_rate), 14, row, { cols: 2, className: `desk-cell-number ${changeClass(item.change_rate)}` }), item.code, "change_rate", item.change_rate, "percent");
        if (item.code) liveSeeds.set(String(item.code), { quote: { price: item.price, change_rate: item.change_rate } });
      });
      section(root, "실시간 시장 · 주요 이벤트", 10, 17, 6); addCell(root, trends.headline || "주요 시장 이슈", 10, 18, { cols: 6, rows: 2, className: "desk-cell-wrap" });
      headers(root, ["구분", "시점", "제목", "예상 영향"], 10, 20, [1,1,2,2]);
      const trendRows = [
        ...(trends.timeline || []).slice(0, 3).map((item) => ({ category: item.impact || item.category, starts_at: item.published_at, title: item.title, expected_impact: item.source })),
        ...(trends.events || []).slice(0, 3),
      ];
      trendRows.forEach((event, index) => { const row = 21 + index; addCell(root, event.category, 10, row, { className: "desk-cell-muted" }); addCell(root, dateLabel(event.starts_at || event.published_at), 11, row); addCell(root, event.title, 12, row, { cols: 2, title: event.title }); addCell(root, event.expected_impact, 14, row, { cols: 2, title: event.expected_impact }); });
      const marketSignals = Array.isArray(signals.items) ? signals.items : [];
      const signalsTitle = section(root, `AI 시그널 · 최근 30일 전체 ${marketSignals.length}개`, 0, 23, 10); signalsTitle.classList.add("desk-cell-link"); signalsTitle.addEventListener("click", () => openUtilitySheet("signals"));
      headers(root, ["종목", "코드", "신호", "점수(점)", "신호일", "체결일", "체결가(원)", "목표 매도가(원)", "현재 상태"], 0, 24, [2,1,1,1,1,1,1,1,1]);
      if (signals.status === "preparing") addCell(root, "최근 30일 시장 AI 시그널을 준비하고 있습니다. 잠시 후 새로고침하면 자동 반영됩니다.", 0, 25, { cols: 10, className: "desk-cell-status" });
      else if (!marketSignals.length) addCell(root, "최근 30일 시장 AI 시그널이 없습니다.", 0, 25, { cols: 10, className: "desk-cell-status" });
      marketSignals.slice(0, 100).forEach((item, index) => {
        const row = 25 + index;
        addCell(root, item.name, 0, row, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) }); addCell(root, item.code, 2, row);
        addCell(root, desktopMarketSignalLabel(item), 3, row, { className: String(item.side).toLowerCase() === "sell" ? "desk-cell-negative" : "desk-cell-positive" });
        addCell(root, number(item.score, 1), 4, row, { className: "desk-cell-number" }); addCell(root, dateLabel(item.signal_date), 5, row); addCell(root, dateLabel(item.execution_date), 6, row);
        addCell(root, item.price == null ? "-" : number(item.price), 7, row, { className: "desk-cell-number" }); addCell(root, item.target_sell_price == null ? "-" : number(item.target_sell_price), 8, row, { className: "desk-cell-number" }); addCell(root, desktopMarketSignalState(item), 9, row, { title: item.reason || desktopMarketSignalState(item) });
      });
      if (marketSignals.length > 100) addCell(root, `표시 한도 100개 · 전체 ${number(marketSignals.length)}개`, 0, 125, { cols: 10, className: "desk-cell-status" });
      section(root, "시장 영향 분석", 10, 30, 6); addCell(root, impact?.summary || "시장 영향 데이터를 확인 중입니다.", 10, 31, { cols: 6, rows: 2, className: "desk-cell-wrap" });
      headers(root, ["좋은 신호(%)", "주의 신호(%)", "중립(%)", "상태"], 10, 34, [2,2,1,1]); addCell(root, percent(impact?.good_weight), 10, 35, { cols: 2, className: "desk-cell-positive desk-cell-number" }); addCell(root, percent(impact?.bad_weight), 12, 35, { cols: 2, className: "desk-cell-negative desk-cell-number" }); addCell(root, percent(impact?.neutral_weight), 14, 35, { className: "desk-cell-number" }); addCell(root, impact?.market_status, 15, 35);
      (impact?.factors || []).slice(0, 5).forEach((factor, index) => { addCell(root, factor.label, 10, 37 + index, { cols: 2 }); addCell(root, factor.interpretation, 12, 37 + index, { cols: 4, title: factor.interpretation }); });
      section(root, "글로벌 자산", 10, 44, 6); headers(root, ["자산", "현재(포인트/USD)", "등락률(%)", "기준"], 10, 45, [2,2,1,1]);
      (globalAssets.items || []).slice(0, 8).forEach((item, index) => { const row = 46 + index, marketCode = item.code || item.name || item.label, current = item.current ?? item.price, unit = String(item.unit || ""); addCell(root, item.label || item.name || item.code, 10, row, { cols: 2 }); markMarketCell(addCell(root, globalAssetValue(current, unit), 12, row, { cols: 2, className: "desk-cell-number" }), "assets", marketCode, "current", current, `asset-${unit}`); markMarketCell(addCell(root, percent(item.change_rate), 14, row, { className: `desk-cell-number ${changeClass(item.change_rate)}` }), "assets", marketCode, "change_rate", item.change_rate, "percent"); addCell(root, dateLabel(item.as_of), 15, row); });
      renderDesktopHomeAiResponse(root, { trends, impact: impact || {}, usSectors, identity }, 16, 3);
      renderDesktopMorningMoneyPreview(root, briefing, 16, 22);
      elements.sheet.replaceChildren(root); liveSeeds.forEach((seed, code) => registerLiveQuote(code, seed)); startHomeMarketRefresh(); setStatus("홈 실시간 시세 연결 중");
    } catch (error) { renderError("홈 데이터를 불러오지 못했습니다.", error); }
  }

  async function renderSearch(token) {
    const root = grid(); sheetTitle(root, "검색", "종목명 또는 6자리 종목코드");
    addCell(root, "검색어", 0, 3, { className: "desk-cell-header" });
    const inputCell = addCell(root, "", 1, 3, { cols: 5, className: "desk-cell-input" });
    const input = document.createElement("input"); input.type = "search"; input.placeholder = "예: 삼성전자, 005930"; input.setAttribute("aria-label", "종목 검색어"); inputCell.appendChild(input);
    const buttonCell = addCell(root, "", 6, 3, { className: "desk-cell-button" }); const button = document.createElement("button"); button.textContent = "검색"; buttonCell.appendChild(button);
    section(root, "검색 결과", 0, 6, 8); headers(root, ["번호", "종목명", "종목코드", "시장", "업종", "관심종목", "상세 보기"], 0, 7, [1,2,1,1,1,1,1]);
    const initialResult = addCell(root, "검색어를 입력하면 일치하는 종목이 이곳에 표시됩니다.", 0, 8, { cols: 8, className: "desk-cell-status" });
    initialResult.dataset.searchResult = "true";
    const search = async () => {
      const query = input.value.trim(); if (!query) { input.focus(); return; }
      button.disabled = true; setStatus(`‘${query}’ 검색 중`);
      try { const items = await api(`/stocks/search?query=${encodeURIComponent(query)}&limit=30`); renderSearchResults(root, items); setStatus(`${items.length}개 종목 검색됨`); }
      catch (error) { renderSearchResults(root, [], "검색 중 오류가 발생했습니다."); setStatus("검색 오류"); }
      finally { button.disabled = false; }
    };
    button.addEventListener("click", search); input.addEventListener("keydown", (event) => { if (event.key === "Enter") search(); });
    section(root, "AI 시그널 전 모니터링 종목", 9, 3, 14);
    headers(root, ["순위", "종목", "코드", "현재 판단", "점수(점)", "현재가(원)", "1개월(%)", "3개월(%)", "관심", "핀", "AI 설명"], 9, 4, [1,2,1,2,1,1,1,1,1,1,2]);
    section(root, "시장 랭킹", 9, 20, 6); headers(root, ["종목", "현재가(원)", "등락률(%)"], 9, 21, [2,2,2]);
    elements.sheet.replaceChildren(root); setStatus("추천·랭킹 불러오는 중");
    window.setTimeout(() => { if (elements.login.hidden) input.focus(); }, 0);
    try {
      const [recommendations, rankings] = await Promise.all([cached("/market/recommendations?limit=12&candidate_limit=100", 120000), cached("/market/rankings?category=surge&limit=10", 60000), hydrateRecommendationTracks()]);
      if (token !== state.renderToken) return;
      (recommendations.items || []).slice(0, 12).forEach((item, index) => {
        const row = 5 + index, signal = item.ai_trade_signal?.current || {};
        addCell(root, item.rank || index + 1, 9, row, { className: "desk-cell-center" }); addCell(root, item.name, 10, row, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) }); addCell(root, item.code, 12, row);
        addCell(root, signal.label || item.action || "관찰", 13, row, { cols: 2, title: signal.next_confirmation || item.decision_reason }); addCell(root, number(item.score, 1), 15, row, { className: "desk-cell-number" }); addCell(root, number(item.price), 16, row, { className: "desk-cell-number" }); addCell(root, percent(item.one_month_return), 17, row, { className: `desk-cell-number ${changeClass(item.one_month_return)}` }); addCell(root, percent(item.three_month_return), 18, row, { className: `desk-cell-number ${changeClass(item.three_month_return)}` });
        addCell(root, isWatched(item.code) ? "관심 해제" : "관심 추가", 19, row, { className: "desk-cell-link desk-cell-center", click: () => toggleWatch(item) });
        addCell(root, isTrackedRecommendation(item.code) ? "핀 종목 보기" : "핀 설정", 20, row, { className: "desk-cell-link desk-cell-center", click: async () => { if (isTrackedRecommendation(item.code)) { state.portfolioTab = "tracking"; activate("portfolio"); } else { await toggleRecommendationTrack(item); activate("search", { replaceHistory: true }); } } });
        addCell(root, "AI 시그널 상세", 21, row, { cols: 2, className: "desk-cell-link desk-cell-center", click: () => openRecommendationDetail(item) });
      });
      (rankings.items || []).slice(0, 10).forEach((item, index) => { const row = 22 + index; addCell(root, item.name, 9, row, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) }); markLiveCell(addCell(root, number(item.price), 11, row, { cols: 2, className: "desk-cell-number" }), item.code, "price", item.price, "number"); markLiveCell(addCell(root, percent(item.change_rate), 13, row, { cols: 2, className: `desk-cell-number ${changeClass(item.change_rate)}` }), item.code, "change_rate", item.change_rate, "percent"); registerLiveQuote(item.code, { quote: { price: item.price, change_rate: item.change_rate } }); });
      setStatus("종목 검색 준비 · 시장 랭킹 실시간 연결 중");
    } catch { setStatus("검색 가능 · 추천 데이터 일부 지연"); }
  }

  function renderSearchResults(root, items, message = "") {
    root.querySelectorAll('[data-search-result="true"]').forEach((node) => node.remove());
    if (!items.length) { const node = addCell(root, message || "검색 결과가 없습니다.", 0, 8, { cols: 8, className: "desk-cell-status" }); node.dataset.searchResult = "true"; return; }
    items.slice(0, 30).forEach((item, index) => {
      const row = 8 + index; const cells = [];
      cells.push(addCell(root, index + 1, 0, row, { className: "desk-cell-center" }));
      cells.push(addCell(root, item.name, 1, row, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) }));
      cells.push(addCell(root, item.code, 3, row)); cells.push(addCell(root, item.market, 4, row)); cells.push(addCell(root, item.sector || item.industry, 5, row));
      cells.push(addCell(root, isWatched(item.code) ? "등록됨" : "+ 추가", 6, row, { className: "desk-cell-link desk-cell-center", click: () => toggleWatch(item) }));
      cells.push(addCell(root, "열기 ›", 7, row, { className: "desk-cell-link desk-cell-center", click: () => openDetail(item) }));
      cells.forEach((node) => { node.dataset.searchResult = "true"; });
    });
  }

  function readLocalWatchlist() {
    try { const data = JSON.parse(localStorage.getItem("analyst.watchlist") || "[]"); return Array.isArray(data) ? data : []; } catch { return []; }
  }

  function recommendationTrackStorageKey() {
    return state.watchlistId ? `${RECOMMENDATION_TRACK_KEY}.${state.watchlistId}` : RECOMMENDATION_TRACK_KEY;
  }

  function normalizeRecommendationTracks(items = []) {
    const seen = new Set();
    return items.filter((item) => {
      const code = String(item?.code || "").trim();
      if (!code || !item?.name || seen.has(code)) return false;
      seen.add(code); return true;
    }).slice(0, 50);
  }

  function readRecommendationTracks() {
    try {
      const scoped = localStorage.getItem(recommendationTrackStorageKey());
      const fallback = localStorage.getItem(RECOMMENDATION_TRACK_KEY);
      return normalizeRecommendationTracks(JSON.parse(scoped ?? fallback ?? "[]"));
    } catch {
      return [];
    }
  }

  function writeRecommendationTracks(items = []) {
    const normalized = normalizeRecommendationTracks(items);
    localStorage.setItem(recommendationTrackStorageKey(), JSON.stringify(normalized));
    if (recommendationTrackStorageKey() !== RECOMMENDATION_TRACK_KEY) localStorage.removeItem(RECOMMENDATION_TRACK_KEY);
    return normalized;
  }

  function isTrackedRecommendation(code) {
    return readRecommendationTracks().some((item) => String(item.code) === String(code));
  }

  async function saveRecommendationTracks(items = []) {
    const normalized = writeRecommendationTracks(items);
    if (!state.watchlistId) return { items: normalized };
    const request = async (token) => fetch(`/watchlists/${encodeURIComponent(state.watchlistId)}/recommendation-tracks`, {
      method: "PUT", credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Write-Token": token },
      body: JSON.stringify({ items: normalized }),
    });
    let response = await request(await ensureWriteToken());
    if (response.status === 403) { state.writeToken = ""; response = await request(await ensureWriteToken()); }
    if (!response.ok) throw new Error("핀 종목 동기화 실패");
    const payload = await response.json(); writeRecommendationTracks(payload.items || normalized); return payload;
  }

  function recommendationTrackEntry(item = {}) {
    return {
      id: `${item.code}-${Date.now()}`,
      code: item.code,
      name: item.name,
      market: item.market,
      tracked_at: new Date().toISOString(),
      tracked_price: finiteNumber(item.price),
      tracked_score: finiteNumber(item.score),
      tracked_action: item.action || "",
      action: item.action || "",
      item: {
        score: item.score, action: item.action, reasons: item.reasons || [], risks: item.risks || [],
        chart_analysis: item.chart_analysis || {}, one_month_return: item.one_month_return,
        three_month_return: item.three_month_return, trading_value: item.trading_value, change_rate: item.change_rate,
      },
    };
  }

  async function toggleRecommendationTrack(item) {
    const items = readRecommendationTracks(), exists = items.some((entry) => String(entry.code) === String(item.code));
    const next = exists ? items.filter((entry) => String(entry.code) !== String(item.code)) : [recommendationTrackEntry(item), ...items];
    try { await saveRecommendationTracks(next); setStatus(exists ? `${item.name} 핀 해제` : `${item.name} 핀 설정 완료`); }
    catch (error) { writeRecommendationTracks(next); setStatus(`${error.message} · 이 PC에는 저장됨`); }
    return !exists;
  }

  async function hydrateRecommendationTracks() {
    if (!state.watchlistId) return readRecommendationTracks();
    try {
      const payload = await api(`/watchlists/${encodeURIComponent(state.watchlistId)}/recommendation-tracks`);
      return writeRecommendationTracks(payload.items || []);
    } catch {
      return readRecommendationTracks();
    }
  }

  function isWatched(code) { return readLocalWatchlist().some((item) => item.code === code); }
  async function toggleWatch(item) {
    const items = readLocalWatchlist(); const index = items.findIndex((entry) => entry.code === item.code);
    if (index >= 0) items.splice(index, 1); else items.push({ code: item.code, name: item.name, market: item.market });
    localStorage.setItem("analyst.watchlist", JSON.stringify(items));
    if (state.watchlistId) { try { await saveWatchlist(items); } catch { setStatus("관심종목은 로컬에 저장됨 · 서버 동기화 실패"); } }
    if (state.active === "portfolio") activate("portfolio", { replaceHistory: true }); else activate("search", { replaceHistory: true });
  }

  async function ensureWriteToken() {
    if (state.writeToken) return state.writeToken;
    const payload = await api(`/session/write-token?share_id=${encodeURIComponent(state.watchlistId)}`);
    state.writeToken = payload.write_token || ""; return state.writeToken;
  }
  async function saveWatchlist(items) {
    let token = await ensureWriteToken();
    let response = await fetch(`/watchlists/${encodeURIComponent(state.watchlistId)}`, { method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Write-Token": token }, body: JSON.stringify({ items }) });
    if (response.status === 403) { state.writeToken = ""; token = await ensureWriteToken(); response = await fetch(`/watchlists/${encodeURIComponent(state.watchlistId)}`, { method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Write-Token": token }, body: JSON.stringify({ items }) }); }
    if (!response.ok) throw new Error("watchlist save failed"); return response.json();
  }

  function desktopRecommendationFallback(dashboard = {}, code = "") {
    const quote = dashboard.quote || {}, momentum = dashboard.momentum || {}, chart = dashboard.chart_analysis || {}, profile = dashboard.company_profile || {};
    return {
      code: String(dashboard.code || code), name: dashboard.name || code, market: dashboard.market || "", price: quote.price,
      score: chart.score, one_month_return: momentum.one_month_return, three_month_return: momentum.three_month_return,
      chart_analysis: chart, reasons: chart.signals || [], risks: chart.risks || [],
      decision_reason: profile.short_summary || profile.summary || "종목 데이터와 AI 시그널을 함께 확인하세요.",
    };
  }

  function desktopRecommendationLevels(item = {}) {
    const price = finiteNumber(item.price), chart = item.chart_analysis || {}, support = finiteNumber(chart.support), resistance = finiteNumber(chart.resistance);
    const round = (value) => value === null ? null : Math.max(1, Math.round(value / (value >= 100000 ? 100 : value >= 10000 ? 50 : 10)) * (value >= 100000 ? 100 : value >= 10000 ? 50 : 10));
    return {
      entryLow: price === null ? null : round(Math.max(support && support < price ? support : 0, price * .985)),
      entryHigh: price === null ? null : round(price * 1.005),
      breakout: price === null ? null : round(Math.max(resistance && resistance > price ? resistance : 0, price * 1.025)),
      reduce: price === null ? null : round(Math.max(support ? support * .985 : 0, price * .965)),
    };
  }

  function openRecommendationDetail(item = {}) {
    if (!item.code) return;
    state.recommendationDetails.set(String(item.code), item);
    activate(`recommend:${item.code}`);
  }

  async function renderDesktopRecommendationDetail(code, token) {
    let item = state.recommendationDetails.get(String(code));
    renderLoading(item?.name || "AI 시그널 상세");
    try {
      if (!item) {
        const payload = await cached("/market/recommendations?limit=20&candidate_limit=100", 120000);
        item = (payload.items || []).find((candidate) => String(candidate.code) === String(code));
      }
      if (!item) {
        const dashboard = await cached(`/stocks/${encodeURIComponent(code)}/dashboard?include_profile=0`, 60000);
        item = desktopRecommendationFallback(dashboard, code);
      }
      if (!item) throw new Error("추천 정보를 찾지 못했습니다.");
      state.recommendationDetails.set(String(code), item); renderTabs();
      const [ai, quant] = await Promise.all([
        cached(`/stocks/${encodeURIComponent(code)}/ai-analysis`, 60000).catch(() => ({})),
        cached(`/stocks/${encodeURIComponent(code)}/quant-signals`, 30000).catch(() => item.ai_trade_signal || {}),
      ]);
      if (token !== state.renderToken) return;
      const root = grid(), levels = desktopRecommendationLevels(item), current = quant.current || item.ai_trade_signal?.current || {}, action = item.action || current.label || current.action || "관찰";
      sheetTitle(root, `${item.name} · ${item.code}`, `${item.market || ""} · 추천 ${number(item.score, 1)} / 100점`);
      section(root, "AI 대응 · 지금 할 일", 0, 3, 12);
      addCell(root, action, 0, 4, { cols: 2, className: /(매수|분할)/.test(action) ? "desk-cell-positive desk-cell-signal-state" : "desk-cell-signal-state" });
      addCell(root, ai.summary || item.decision_reason || current.next_confirmation || "추천 점수와 차트를 함께 확인하세요.", 2, 4, { cols: 8, rows: 2, className: "desk-cell-wrap" });
      addCell(root, isWatched(code) ? "관심 해제" : "관심 추가", 10, 4, { className: "desk-cell-link desk-cell-center", click: () => toggleWatch(item) });
      addCell(root, isTrackedRecommendation(code) ? "핀 해제" : "핀 설정", 11, 4, { className: "desk-cell-link desk-cell-center", click: async () => { await toggleRecommendationTrack(item); activate(`recommend:${code}`, { replaceHistory: true }); } });
      section(root, "가격 기준", 0, 8, 8); headers(root, ["현재가(원)", "접근 구간 하단(원)", "접근 구간 상단(원)", "매수 전환(원)", "위험 관리(원)"], 0, 9, [1,2,2,2,1]);
      [item.price, levels.entryLow, levels.entryHigh, levels.breakout, levels.reduce].forEach((value, index) => { const starts = [0,1,3,5,7][index], widths = [1,2,2,2,1][index]; addCell(root, value == null ? "-" : `${number(value)}원`, starts, 10, { cols: widths, className: "desk-cell-number" }); });
      section(root, "판단에 쓴 핵심 수치", 0, 13, 8); headers(root, ["추천 점수(점)", "차트 점수(점)", "1개월 수익률(%)", "3개월 수익률(%)", "현재 AI 시그널"], 0, 14, [1,1,2,2,2]);
      addCell(root, number(item.score, 1), 0, 15, { className: "desk-cell-number" }); addCell(root, number(item.chart_analysis?.score, 1), 1, 15, { className: "desk-cell-number" }); addCell(root, percent(item.one_month_return), 2, 15, { cols: 2, className: `desk-cell-number ${changeClass(item.one_month_return)}` }); addCell(root, percent(item.three_month_return), 4, 15, { cols: 2, className: `desk-cell-number ${changeClass(item.three_month_return)}` }); addCell(root, current.label || current.action || "신호 확인 중", 6, 15, { cols: 2 });
      section(root, "세부 근거", 0, 19, 12); headers(root, ["긍정 근거", "주의할 점", "AI 시그널 다음 확인"], 0, 20, [4,4,4]);
      const positive = item.reasons || ai.key_points || [], risks = item.risks || ai.risks || [];
      for (let index = 0; index < Math.max(positive.length, risks.length, 4); index += 1) {
        const row = 21 + index; addCell(root, positive[index] ? `• ${positive[index]}` : index === 0 ? "확인된 긍정 근거가 부족합니다." : "", 0, row, { cols: 4, className: "desk-cell-wrap desk-cell-positive" }); addCell(root, risks[index] ? `• ${risks[index]}` : index === 0 ? "두드러진 위험 신호는 없습니다." : "", 4, row, { cols: 4, className: "desk-cell-wrap desk-cell-negative" }); if (index === 0) addCell(root, current.next_confirmation || quant.data_message || "가격·수급·뉴스를 함께 확인하세요.", 8, row, { cols: 4, rows: 3, className: "desk-cell-wrap" });
      }
      addCell(root, "종목 상세 열기 ›", 0, 30, { cols: 4, className: "desk-cell-link desk-cell-center", click: () => openDetail(item) });
      addCell(root, "점수와 가격 기준은 수집된 시장 데이터 규칙으로 계산한 참고 정보입니다.", 4, 30, { cols: 8, className: "desk-cell-status desk-cell-wrap" });
      elements.sheet.replaceChildren(root); setStatus(`${item.name} AI 추천 상세 완료`);
    } catch (error) { renderError("AI 추천 상세를 불러오지 못했습니다.", error); }
  }

  async function renderPortfolio(token) {
    renderLoading("내 종목");
    try {
      let items = readLocalWatchlist(); let pinned = []; let watchSignals = { items: [] };
      if (state.watchlistId) {
        const [remote, tracks, signalPayload] = await Promise.all([api(`/watchlists/${encodeURIComponent(state.watchlistId)}`), api(`/watchlists/${encodeURIComponent(state.watchlistId)}/recommendation-tracks`).catch(() => ({ items: [] })), api(`/watchlists/${encodeURIComponent(state.watchlistId)}/quant-signals`).catch(() => ({ items: [] }))]);
        items = remote.items || items; pinned = tracks.initialized === false && readRecommendationTracks().length ? readRecommendationTracks() : tracks.items || []; watchSignals = signalPayload || { items: [] }; localStorage.setItem("analyst.watchlist", JSON.stringify(items)); writeRecommendationTracks(pinned);
      }
      const [details, contexts, pinnedDetails, usSectors, marketContext] = await Promise.all([
        Promise.all(items.slice(0, 20).map(async (item) => { try { return { ...item, dashboard: await cached(`/stocks/${encodeURIComponent(item.code)}/dashboard?include_profile=0`, 30000) }; } catch { return item; } })),
        Promise.all(items.slice(0, 6).map(async (item) => { try { return await cached(`/stocks/${encodeURIComponent(item.code)}/home-context?flow_limit=1&research_limit=1&disclosure_limit=1&news_limit=5&community_limit=1`, 120000); } catch { return null; } })),
        Promise.all(pinned.slice(0, 30).map(async (item) => { try { return { ...item, dashboard: await cached(`/stocks/${encodeURIComponent(item.code)}/dashboard?include_profile=0`, 30000) }; } catch { return item; } })),
        cached("/market/us-sector-moves", 120000).catch(() => ({ items: [] })),
        Promise.all([cached("/market/impact", 120000).catch(() => ({})), cached("/market/trends?days=7", 120000).catch(() => ({}))]).then(([impact, trends]) => ({ impact, trends })),
      ]);
      if (token !== state.renderToken) return;
      const root = grid(); sheetTitle(root, "내 종목", `${state.watchlistId || "로컬"} · ${items.length}개 · 실시간`);
      portfolioSheetTab(root, "primary", "watchlist", "관심종목", 0, 2);
      portfolioSheetTab(root, "primary", "tracking", "핀 종목", 2, 2);
      if (state.portfolioTab === "tracking") {
        section(root, "핀 종목", 0, 5, 12); headers(root, ["번호", "종목명", "코드", "핀 시작일", "핀 시작가(원)", "현재가(원)", "수익률(%)", "시작 판단", "상세", "관리"], 0, 6, [1,2,1,1,1,1,1,1,1,2]);
        if (!pinnedDetails.length) addCell(root, "핀 종목이 없습니다. 검색에서 모니터링 종목을 선택해 주세요.", 0, 7, { cols: 12, className: "desk-cell-status" });
        pinnedDetails.forEach((item, index) => {
          const row = 7 + index, currentPrice = finiteNumber(item.dashboard?.quote?.price), trackedPrice = finiteNumber(item.tracked_price), returnRate = trackedPrice && currentPrice !== null ? ((currentPrice / trackedPrice) - 1) * 100 : null;
          addCell(root, index + 1, 0, row, { className: "desk-cell-center" }); addCell(root, item.name, 1, row, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) }); addCell(root, item.code, 3, row); addCell(root, dateLabel(item.tracked_at), 4, row); addCell(root, number(trackedPrice), 5, row, { className: "desk-cell-number" }); markLiveCell(addCell(root, number(currentPrice), 6, row, { className: "desk-cell-number" }), item.code, "price", currentPrice, "number"); addCell(root, percent(returnRate), 7, row, { className: `desk-cell-number ${changeClass(returnRate)}` }); addCell(root, item.tracked_action || item.action || "관찰", 8, row); addCell(root, "AI 상세", 9, row, { className: "desk-cell-link desk-cell-center", click: () => openRecommendationDetail({ ...item.item, ...item }) }); addCell(root, "핀 해제", 10, row, { cols: 2, className: "desk-cell-link desk-cell-center", click: async () => { await saveRecommendationTracks(readRecommendationTracks().filter((entry) => String(entry.code) !== String(item.code))); activate("portfolio", { replaceHistory: true }); } });
        });
      } else {
        portfolioSheetTab(root, "content", "strategy", "AI 전략", 0, 3);
        portfolioSheetTab(root, "content", "news", "종목 뉴스", 2, 3);
        if (state.portfolioContentTab === "news") {
          const contextPairs = contexts.map((context, index) => ({ context, item: items[index] })).filter((entry) => entry.context && entry.item);
          const newsOptions = [["all", "전체"], ...contextPairs.map(({ item }) => [String(item.code), item.name])];
          if (state.portfolioNewsCode !== "all" && !newsOptions.some(([id]) => id === state.portfolioNewsCode)) state.portfolioNewsCode = "all";
          newsOptions.slice(0, 12).forEach(([id, label], index) => sheetOptionButton(root, id, label, index * 2, 5, 2, state.portfolioNewsCode === id, () => { state.portfolioNewsCode = id; activate("portfolio", { replaceHistory: true }); }, { role: "tab" }));
          section(root, "관심종목 뉴스", 0, 7, 12); headers(root, ["종목", "언론사", "게시일", "뉴스 제목·원문"], 0, 8, [2,2,2,6]);
          const newsRows = contextPairs.filter(({ item }) => state.portfolioNewsCode === "all" || String(item.code) === state.portfolioNewsCode).flatMap(({ context, item }) => (context.news_items || []).slice(0, 5).map((news) => ({ ...news, stockName: item.name, stockCode: item.code })));
          if (!newsRows.length) addCell(root, "관심종목의 최신 뉴스를 찾지 못했습니다.", 0, 9, { cols: 12, className: "desk-cell-status" });
          newsRows.slice(0, 30).forEach((news, index) => { const row = 9 + index, href = safeExternalUrl(news.detail_url || news.url); addCell(root, news.stockName, 0, row, { cols: 2, className: "desk-cell-link", click: () => openDetail({ code: news.stockCode, name: news.stockName }) }); addCell(root, news.press_name || news.source, 2, row, { cols: 2 }); addCell(root, text(news.published_at).slice(0, 10), 4, row, { cols: 2 }); addCell(root, news.title, 6, row, { cols: 6, tag: href ? "a" : "div", href, className: href ? "desk-cell-link" : "", title: news.summary || news.title }); });
        } else {
          [["all", "전체"], ["attention", "확인 필요"], ["positive", "흐름 양호"]].forEach(([id, label], index) => sheetOptionButton(root, id, label, index * 2, 5, 2, state.portfolioFilter === id, () => { state.portfolioFilter = id; activate("portfolio", { replaceHistory: true }); }, { role: "tab" }));
          const filteredDetails = details.filter((item) => { const quote = item.dashboard?.quote || {}, momentum = item.dashboard?.momentum || {}; if (state.portfolioFilter === "attention") return Number(quote.change_rate || 0) < 0 || Number(momentum.one_month_return || 0) < 0; if (state.portfolioFilter === "positive") return Number(quote.change_rate || 0) >= 0 && Number(momentum.one_month_return || 0) >= 0; return true; });
          section(root, "관심종목", 0, 7, 8); headers(root, ["번호", "종목명", "코드", "시장", "현재가(원)", "등락률(%)", "1개월 수익률(%)", "관리"], 0, 8);
          if (!filteredDetails.length) statusRow(root, details.length ? "선택한 조건의 관심종목이 없습니다." : "등록된 관심종목이 없습니다. 검색 시트에서 종목을 추가하세요.", 9);
          filteredDetails.forEach((item, index) => {
            const row = 9 + index, quote = item.dashboard?.quote || {}, momentum = item.dashboard?.momentum || {};
            addCell(root, index + 1, 0, row, { className: "desk-cell-center" }); addCell(root, item.name, 1, row, { className: "desk-cell-link", click: () => openDetail(item) });
            addCell(root, item.code, 2, row); addCell(root, item.market, 3, row);
            markLiveCell(addCell(root, number(quote.price), 4, row, { className: "desk-cell-number" }), item.code, "price", quote.price, "number");
            markLiveCell(addCell(root, percent(quote.change_rate), 5, row, { className: `desk-cell-number ${changeClass(quote.change_rate)}` }), item.code, "change_rate", quote.change_rate, "percent");
            markLiveCell(addCell(root, percent(momentum.one_month_return), 6, row, { className: `desk-cell-number ${changeClass(momentum.one_month_return)}` }), item.code, "one_month_return", momentum.one_month_return, "percent");
            addCell(root, "삭제", 7, row, { className: "desk-cell-link desk-cell-center", click: () => toggleWatch(item) });
          });
          section(root, "관심종목 시장 대응", 9, 5, 7); addCell(root, marketContext.impact?.summary || "오늘 시장 변수를 확인하고 있습니다.", 9, 6, { cols: 7, rows: 2, className: "desk-cell-wrap" });
          headers(root, ["미국 섹터", "등락률(%)", "관찰 포인트"], 9, 9, [2,2,3]);
          (usSectors.items || []).filter((item) => Number.isFinite(Number(item.change_rate))).sort((a, b) => Math.abs(Number(b.change_rate)) - Math.abs(Number(a.change_rate))).slice(0, 4).forEach((sector, index) => { const row = 10 + index; addCell(root, sector.label || sector.symbol, 9, row, { cols: 2 }); addCell(root, percent(sector.change_rate), 11, row, { cols: 2, className: `desk-cell-number ${changeClass(sector.change_rate)}` }); addCell(root, `${usSectors.market_session_label || "지난 미국장"} 기준 · 관련 종목 수급 확인`, 13, row, { cols: 3 }); });
          section(root, "관심종목 AI 전략", 0, 35, 8); headers(root, ["종목", "코드", "신호", "점수(점)", "기준일", "다음 확인"], 0, 36, [2,1,1,1,1,2]);
          (watchSignals.items || []).slice(0, 20).forEach((item, index) => { const row = 37 + index, current = item.current || {}; addCell(root, item.name, 0, row, { cols: 2, className: "desk-cell-link", click: () => openDetail(item) }); addCell(root, item.code, 2, row); addCell(root, current.label || current.action || "관찰", 3, row); addCell(root, number(current.score, 1), 4, row, { className: "desk-cell-number" }); addCell(root, item.price_through || item.as_of, 5, row); addCell(root, current.next_confirmation || item.data_message, 6, row, { cols: 2, title: current.next_confirmation || item.data_message }); });
        }
      }
      elements.sheet.replaceChildren(root); [...details, ...pinnedDetails].forEach((item) => registerLiveQuote(item.code, { quote: item.dashboard?.quote || {}, momentum: item.dashboard?.momentum || {} })); setStatus(details.length ? "내 종목 실시간 시세 연결 중" : "내 종목 동기화 완료");
    } catch (error) { renderError("내 종목을 불러오지 못했습니다.", error); }
  }

  function renderChart() {
    const root = grid(); sheetTitle(root, "차트분석", "최근 흐름 · 5일·10일 전망"); addCell(root, "종목 검색", 0, 3, { className: "desk-cell-header" });
    const inputCell = addCell(root, "", 1, 3, { cols: 4, className: "desk-cell-input" }); const input = document.createElement("input"); input.type = "search"; input.placeholder = "종목명 또는 코드"; inputCell.appendChild(input);
    const buttonCell = addCell(root, "", 5, 3, { className: "desk-cell-button" }); const button = document.createElement("button"); button.textContent = "분석"; buttonCell.appendChild(button);
    section(root, "최근 가격 + 5일·10일 전망", 0, 6, 8); const initialChart = addCell(root, "종목을 검색하면 실제 가격, 5일선·10일선과 5일·10일 예상 범위를 표시합니다.", 0, 7, { cols: 8, className: "desk-cell-status" }); initialChart.dataset.chartResult = "true";
    const run = async () => {
      const query = input.value.trim(); if (!query) return input.focus(); button.disabled = true;
      try { const results = await api(`/stocks/search?query=${encodeURIComponent(query)}&limit=1`); if (!results.length) throw new Error("not found"); await renderChartResult(root, results[0]); }
      catch { root.querySelectorAll('[data-chart-result="true"]').forEach((node) => node.remove()); const node = addCell(root, "종목을 찾거나 분석 데이터를 불러오지 못했습니다.", 0, 7, { cols: 8, className: "desk-cell-error" }); node.dataset.chartResult = "true"; }
      finally { button.disabled = false; }
    };
    button.addEventListener("click", run); input.addEventListener("keydown", (event) => { if (event.key === "Enter") run(); }); elements.sheet.replaceChildren(root); setStatus("차트분석 준비");
  }

  async function renderChartResult(root, stock) {
    setStatus(`${stock.name} 5일·10일 분석 중`); const [prices, ai] = await Promise.all([
      api(`/stocks/${encodeURIComponent(stock.code)}/prices?limit=260`),
      api(`/stocks/${encodeURIComponent(stock.code)}/ai-analysis`).catch(() => ({})),
    ]);
    root.querySelectorAll('[data-chart-result="true"]').forEach((node) => node.remove());
    const analysis = computeDesktopChartAnalysis(prices);
    if (!analysis.available) {
      const node = addCell(root, analysis.reason, 0, 7, { cols: 8, className: "desk-cell-status" }); node.dataset.chartResult = "true";
      setStatus(`${stock.name} 가격 데이터 부족`); return;
    }
    const tracked = (node) => { node.dataset.chartResult = "true"; return node; };
    tracked(addCell(root, desktopForecastChartSvg(analysis), 0, 7, { cols: 8, rows: 11, html: true, className: "desk-cell-chart desk-cell-forecast-chart" }));
    tracked(addCell(root, '<div class="desk-chart-legend" aria-label="차트 범례"><span class="actual">실제 가격</span><span class="ma5">5일선</span><span class="ma10">10일선</span><span class="forecast5">5일 예상</span><span class="forecast10">10일 예상</span><span class="range">예상 범위</span></div>', 0, 18, { cols: 8, html: true, className: "desk-cell-chart-legend" }));
    tracked(addCell(root, `${stock.name} (${stock.code}) 상세 시트 열기 ›`, 0, 20, { cols: 8, className: "desk-cell-subtitle desk-cell-link", click: () => openDetail(stock) }));
    tracked(addCell(root, "5일·10일 전망 비교", 0, 22, { cols: 8, className: "desk-cell-subtitle" }));
    ["구분", "5일 시나리오", "10일 시나리오", "현재 기준"].forEach((label, index) => tracked(addCell(root, label, index * 2, 23, { cols: 2, className: "desk-cell-header" })));
    const forecasts = [analysis.forecast5, analysis.forecast10];
    const rangeText = (forecast) => `${number(forecast.points.at(-1).lower)} ~ ${number(forecast.points.at(-1).upper)}원`;
    const comparison = [
      ["예상 중심", `${number(forecasts[0].expected)}원`, `${number(forecasts[1].expected)}원`, `${number(analysis.current)}원`],
      ["예상 등락", percent(forecasts[0].expectedRate), percent(forecasts[1].expectedRate), "현재가 대비"],
      ["예상 범위", rangeText(forecasts[0]), rangeText(forecasts[1]), "변동성 반영"],
      ["흐름 신뢰도", `${forecasts[0].confidence} · ${Math.round(forecasts[0].confidenceScore)}점`, `${forecasts[1].confidence} · ${Math.round(forecasts[1].confidenceScore)}점`, "최근 260일 기준"],
      ["방향", forecasts[0].direction, forecasts[1].direction, `지지 ${number(analysis.support)}원`],
    ];
    comparison.forEach((values, rowIndex) => values.forEach((value, colIndex) => {
      const tone = rowIndex === 1 && colIndex > 0 && colIndex < 3 ? changeClass(forecasts[colIndex - 1].expectedRate) : "";
      const node = tracked(addCell(root, value, colIndex * 2, 24 + rowIndex, { cols: 2, className: `${colIndex === 0 ? "desk-cell-header" : "desk-cell-number"} ${tone}` }));
      if (rowIndex === 0 && colIndex === 3) markLiveCell(node, stock.code, "price", analysis.current, "price-won");
    }));
    tracked(addCell(root, "이동평균선", 0, 30, { cols: 8, className: "desk-cell-subtitle" }));
    ["현재가(원)", "5일선(원)", "10일선(원)", "20일선(원)"].forEach((label, index) => tracked(addCell(root, label, index * 2, 31, { cols: 2, className: "desk-cell-header" })));
    [analysis.current, analysis.ma5, analysis.ma10, analysis.ma20].forEach((value, index) => tracked(addCell(root, `${number(value)}원`, index * 2, 32, { cols: 2, className: "desk-cell-number" })));
    tracked(addCell(root, "AI 분석", 0, 34, { cols: 8, className: "desk-cell-subtitle" }));
    [["AI 판단", ai.stance], ["신뢰도", percent(ai.confidence)], ["요약", ai.summary]].forEach(([label, value], index) => {
      tracked(addCell(root, label, 0, 35 + index, { className: "desk-cell-header" }));
      tracked(addCell(root, value, 1, 35 + index, { cols: 7, className: index === 2 ? "desk-cell-wrap" : "" }));
    });
    tracked(addCell(root, "※ 최근 가격·이동평균·변동성을 바탕으로 계산한 참고 시나리오이며 미래 가격을 보장하지 않습니다.", 0, 39, { cols: 8, className: "desk-cell-status desk-cell-wrap" }));
    registerLiveQuote(stock.code, { quote: { price: analysis.current } }); setStatus(`${stock.name} 5일·10일 분석 완료 · 현재가 실시간 연결 중`);
  }

  const NOTIFICATION_KIND_LABELS = {
    morning_briefing: "돈이 되는 소식", market_session: "국내장", ai_signal: "AI 시그널", market_ai_signal: "시장 AI 시그널",
    price_move: "시세", report: "리포트", disclosure: "공시", major_event: "주요 이벤트", test: "테스트",
  };
  const NOTIFICATION_FILTERS = [
    { id: "all", label: "전체" }, { id: "ai_signal", label: "AI 시그널" },
    { id: "watchlist", label: "관심종목" }, { id: "major_event", label: "주요 이벤트" },
  ];
  const NOTIFICATION_VIEW_MAP = new Map([
    ["home", "home"], ["search", "search"], ["watchlist", "portfolio"], ["portfolio", "portfolio"],
    ["chart", "chart"], ["trend", "home"], ["alerts", "notifications"], ["notifications", "notifications"],
  ]);
  const DESKTOP_PUSH_FALLBACK_OPTIONS = [
    { id: "morning_briefing", label: "돈이 되는 소식", required: true },
    { id: "market_session", label: "국내장 시작·마감" },
    { id: "ai_signal", label: "AI 시그널", required: true },
    { id: "market_ai_signal", label: "시장 AI 신호" },
    { id: "price_move", label: "급등락" },
    { id: "disclosure_report", label: "공시·리포트" },
    { id: "major_event", label: "주요 이벤트" },
  ];
  let desktopServiceWorkerRegistrationPromise = null;

  function desktopPushSupported() {
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }

  function registerDesktopServiceWorker() {
    if (!("serviceWorker" in navigator)) return Promise.resolve(null);
    if (!desktopServiceWorkerRegistrationPromise) {
      desktopServiceWorkerRegistrationPromise = navigator.serviceWorker.register(
        `/desktop-sw.js?v=${DESKTOP_SW_VERSION}`,
        { scope: "/desktop" },
      );
    }
    return desktopServiceWorkerRegistrationPromise;
  }

  function desktopPushApplicationServerKey(value) {
    const padding = "=".repeat((4 - (value.length % 4)) % 4);
    const base64 = `${value}${padding}`.replace(/-/g, "+").replace(/_/g, "/");
    const raw = window.atob(base64);
    return Uint8Array.from([...raw].map((character) => character.charCodeAt(0)));
  }

  function desktopPushSubscriptionUsesKey(subscription, publicKey) {
    const actualBuffer = subscription?.options?.applicationServerKey;
    if (!actualBuffer || !publicKey) return true;
    const actual = new Uint8Array(actualBuffer), expected = desktopPushApplicationServerKey(publicKey);
    return actual.length === expected.length && actual.every((value, index) => value === expected[index]);
  }

  function desktopPushOptions() {
    return state.desktopPushConfig?.condition_options || DESKTOP_PUSH_FALLBACK_OPTIONS;
  }

  function normalizeDesktopPushConditions(values) {
    const options = desktopPushOptions(), allowed = new Set(options.map((item) => item.id));
    const required = options.filter((item) => item.required).map((item) => item.id);
    const normalized = Array.isArray(values)
      ? [...new Set(values.map((item) => String(item || "").trim()).filter((item) => allowed.has(item)))]
      : [];
    const selected = normalized.length ? normalized : (state.desktopPushConfig?.conditions || options.map((item) => item.id));
    return [...new Set([...required, ...selected])];
  }

  function setDesktopPushMessage(message, tone = "") {
    state.desktopPushMessage = message;
    state.desktopPushTone = tone;
  }

  async function refreshDesktopPushState() {
    if (!desktopPushSupported()) {
      state.desktopPushEnabled = false;
      setDesktopPushMessage("이 브라우저에서는 알림 수신을 지원하지 않습니다.", "error");
      return;
    }
    try {
      state.desktopPushConfig = state.desktopPushConfig || await api("/push/config");
      state.desktopPushConditions = normalizeDesktopPushConditions(state.desktopPushConditions);
      if (!state.desktopPushConfig.enabled || !state.desktopPushConfig.public_key) {
        state.desktopPushEnabled = false;
        setDesktopPushMessage("알림 기능을 준비하고 있습니다. 잠시 후 다시 시도해주세요.");
        return;
      }
      if (Notification.permission === "denied") {
        state.desktopPushEnabled = false;
        setDesktopPushMessage("브라우저 설정에서 이 사이트의 알림 권한을 허용해주세요.", "error");
        return;
      }
      const registration = await registerDesktopServiceWorker();
      const subscription = await registration?.pushManager.getSubscription();
      if (!subscription || !desktopPushSubscriptionUsesKey(subscription, state.desktopPushConfig.public_key)) {
        state.desktopPushEnabled = false;
        setDesktopPushMessage(Notification.permission === "granted" ? "이 PC의 알림 등록이 필요합니다." : "버튼을 눌러 이 PC의 알림 권한을 허용해주세요.");
        return;
      }
      const status = await api(`/push/subscriptions/${encodeURIComponent(state.watchlistId)}/status?endpoint=${encodeURIComponent(subscription.endpoint)}`);
      state.desktopPushEnabled = status.enabled === true;
      state.desktopPushConditions = normalizeDesktopPushConditions(status.conditions || state.desktopPushConditions);
      setDesktopPushMessage(state.desktopPushEnabled ? "이 PC에서 선택한 알림을 받고 있습니다." : "이 PC의 서버 등록이 필요합니다.", state.desktopPushEnabled ? "success" : "");
    } catch {
      state.desktopPushEnabled = false;
      setDesktopPushMessage("알림 상태를 확인하지 못했습니다. 다시 시도해주세요.", "error");
    }
  }

  function paintNotifications() {
    if (state.active !== "notifications") return;
    const allItems = state.notificationItems;
    const items = allItems.filter((item) => notificationMatches(item, state.notificationFilter)).sort((a, b) => (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0));
    const root = grid(); sheetTitle(root, "알림", `${allItems.length}건 · 최근 ${state.notificationRetentionDays}일 수신`);
    section(root, "이 PC 알림", 0, 3, 12);
    addCell(root, state.desktopPushMessage, 0, 4, { cols: 4, className: state.desktopPushTone === "error" ? "desk-cell-error" : "desk-cell-status", title: state.desktopPushMessage });
    addCell(root, state.desktopPushBusy ? "처리 중…" : state.desktopPushEnabled ? "설정 저장" : "이 PC에서 알림 받기", 4, 4, { cols: 2, className: "desk-cell-link desk-cell-center", ariaLabel: state.desktopPushEnabled ? "이 PC 알림 설정 저장" : "이 PC에서 알림 받기", click: state.desktopPushBusy ? null : saveDesktopPushSettings });
    addCell(root, "시험 알림", 6, 4, { cols: 2, className: `desk-cell-center${state.desktopPushEnabled ? " desk-cell-link" : ""}`, click: state.desktopPushEnabled && !state.desktopPushBusy ? sendDesktopPushTest : null });
    addCell(root, "이 PC 알림 끄기", 8, 4, { cols: 2, className: `desk-cell-center${state.desktopPushEnabled ? " desk-cell-link" : ""}`, click: state.desktopPushEnabled && !state.desktopPushBusy ? disableDesktopPush : null });
    addCell(root, desktopPushSupported() ? `권한: ${Notification.permission === "granted" ? "허용" : Notification.permission === "denied" ? "차단" : "확인 필요"}` : "지원 안 됨", 10, 4, { cols: 2, className: "desk-cell-center desk-cell-status" });
    section(root, "받을 알림", 0, 6, 12);
    const selectedConditions = new Set(state.desktopPushConditions);
    desktopPushOptions().forEach((option, index) => {
      const selected = option.required || selectedConditions.has(option.id);
      addCell(root, `${selected ? "✓ " : ""}${option.label}${option.required ? " · 필수" : ""}`, index * 2, 7, { cols: 2, className: `desk-cell-center desk-cell-link${selected ? " desk-cell-subtitle" : ""}`, title: option.description || option.label, ariaLabel: `${option.label} 알림 ${selected ? "선택됨" : "선택 안 됨"}${option.required ? ", 필수" : ""}`, click: option.required || state.desktopPushBusy ? null : () => toggleDesktopPushCondition(option.id) });
    });
    addCell(root, "내역 필터", 0, 9, { className: "desk-cell-header" });
    NOTIFICATION_FILTERS.forEach((filter, index) => addCell(root, `${state.notificationFilter === filter.id ? "✓ " : ""}${filter.label}`, 1 + index * 2, 9, { cols: 2, className: `desk-cell-center desk-cell-link${state.notificationFilter === filter.id ? " desk-cell-subtitle" : ""}`, click: () => { state.notificationFilter = filter.id; paintNotifications(); } }));
    section(root, "알림 내역", 0, 12, 12); headers(root, ["수신일", "시간", "유형", "제목", "내용", "연결"], 0, 13, [1,1,2,3,4,1]);
    if (!items.length) addCell(root, allItems.length ? "이 유형의 알림이 없습니다." : "최근 3일 동안 받은 알림이 없습니다.", 0, 14, { cols: 12, className: "desk-cell-status" });
    items.slice(0, 50).forEach((item, index) => {
      const row = 14 + index, received = text(item.created_at, "").replace("T", " ").replace("Z", "");
      addCell(root, item.event_date || received.slice(0, 10), 0, row); addCell(root, received.slice(11, 16), 1, row); addCell(root, NOTIFICATION_KIND_LABELS[item.kind] || "알림", 2, row, { cols: 2 });
      addCell(root, item.title, 4, row, { cols: 3, title: item.title }); addCell(root, item.body, 7, row, { cols: 4, title: item.body }); addCell(root, item.url ? "열기 ›" : "-", 11, row, { className: item.url ? "desk-cell-link desk-cell-center" : "desk-cell-center", ariaLabel: item.url ? `${item.title} 열기` : "연결 없음", click: item.url ? () => openNotification(item) : null });
    });
    elements.sheet.replaceChildren(root);
    setStatus(`알림 ${items.length}건 표시 · 이 PC 수신 ${state.desktopPushEnabled ? "켜짐" : "꺼짐"}`);
  }

  function toggleDesktopPushCondition(condition) {
    const selected = new Set(state.desktopPushConditions);
    if (selected.has(condition)) selected.delete(condition); else selected.add(condition);
    state.desktopPushConditions = normalizeDesktopPushConditions([...selected]);
    setDesktopPushMessage(state.desktopPushEnabled ? "선택을 변경했습니다. 설정 저장을 눌러주세요." : "받고 싶은 알림을 선택한 뒤 알림 받기를 눌러주세요.");
    paintNotifications();
  }

  async function saveDesktopPushSettings() {
    if (state.desktopPushBusy || !state.watchlistId) return;
    state.desktopPushBusy = true; setDesktopPushMessage("이 PC의 알림을 설정하고 있습니다…"); paintNotifications();
    try {
      state.desktopPushConfig = state.desktopPushConfig || await api("/push/config");
      if (!state.desktopPushConfig.enabled || !state.desktopPushConfig.public_key) throw new Error("알림 서버를 준비 중입니다.");
      const registration = await registerDesktopServiceWorker();
      let permission = Notification.permission;
      if (permission !== "granted") permission = await Notification.requestPermission();
      if (permission !== "granted") throw new Error("브라우저 알림 권한이 필요합니다.");
      let subscription = await registration.pushManager.getSubscription();
      if (subscription && !desktopPushSubscriptionUsesKey(subscription, state.desktopPushConfig.public_key)) {
        await subscription.unsubscribe(); subscription = null;
      }
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: desktopPushApplicationServerKey(state.desktopPushConfig.public_key) });
      }
      const response = await fetch(`/push/subscriptions/${encodeURIComponent(state.watchlistId)}`, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Write-Token": await ensureWriteToken() },
        body: JSON.stringify({ ...subscription.toJSON(), conditions: normalizeDesktopPushConditions(state.desktopPushConditions) }),
      });
      if (!response.ok) throw new Error(await responseError(response, "알림 설정을 저장하지 못했습니다."));
      const result = await response.json();
      state.desktopPushEnabled = result.enabled === true;
      state.desktopPushConditions = normalizeDesktopPushConditions(result.conditions || state.desktopPushConditions);
      setDesktopPushMessage(result.test_sent === true ? "알림 설정 완료 · 시험 알림을 보냈습니다." : "알림 설정을 저장했습니다.", "success");
    } catch (error) {
      state.desktopPushEnabled = false;
      setDesktopPushMessage(error.message || "알림을 설정하지 못했습니다.", "error");
    } finally { state.desktopPushBusy = false; paintNotifications(); }
  }

  async function sendDesktopPushTest() {
    if (state.desktopPushBusy || !state.desktopPushEnabled) return;
    state.desktopPushBusy = true; setDesktopPushMessage("시험 알림을 보내고 있습니다…"); paintNotifications();
    try {
      const registration = await registerDesktopServiceWorker(), subscription = await registration.pushManager.getSubscription();
      if (!subscription) throw new Error("이 PC의 알림 등록을 찾지 못했습니다.");
      const response = await fetch(`/push/subscriptions/${encodeURIComponent(state.watchlistId)}/test`, {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-Write-Token": await ensureWriteToken() },
        body: JSON.stringify({ endpoint: subscription.endpoint }),
      });
      if (!response.ok) throw new Error(await responseError(response, "시험 알림 전송에 실패했습니다."));
      setDesktopPushMessage("시험 알림을 보냈습니다.", "success");
    } catch (error) { setDesktopPushMessage(error.message || "시험 알림을 보내지 못했습니다.", "error"); }
    finally { state.desktopPushBusy = false; paintNotifications(); }
  }

  async function disableDesktopPush() {
    if (state.desktopPushBusy || !state.desktopPushEnabled) return;
    state.desktopPushBusy = true; setDesktopPushMessage("이 PC의 알림을 끄고 있습니다…"); paintNotifications();
    try {
      const registration = await registerDesktopServiceWorker(), subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        const response = await fetch(`/push/subscriptions/${encodeURIComponent(state.watchlistId)}`, {
          method: "DELETE", credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-Write-Token": await ensureWriteToken() },
          body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
        if (!response.ok) throw new Error(await responseError(response, "알림을 끄지 못했습니다."));
        await subscription.unsubscribe();
      }
      state.desktopPushEnabled = false; setDesktopPushMessage("이 PC의 알림을 껐습니다.");
    } catch (error) { setDesktopPushMessage(error.message || "알림을 끄지 못했습니다.", "error"); }
    finally { state.desktopPushBusy = false; paintNotifications(); }
  }

  function notificationMatches(item, filter) {
    if (filter === "all") return true;
    if (filter === "ai_signal") return ["ai_signal", "market_ai_signal"].includes(item.kind);
    if (filter === "watchlist") return ["price_move", "report", "disclosure"].includes(item.kind);
    return item.kind === filter;
  }

  async function openNotification(item) {
    const target = new URL(item.url || "/desktop?view=notifications", location.origin);
    const pathMatch = target.pathname.match(/^\/(?:dashboard|stocks)\/([^/?#]+)/);
    let stockQuery = target.searchParams.get("code") || target.searchParams.get("query") || "";
    if (pathMatch?.[1]) {
      try { stockQuery = decodeURIComponent(pathMatch[1]); }
      catch { stockQuery = pathMatch[1]; }
    }
    if (stockQuery) {
      try { const stock = await api(`/stocks/resolve?query=${encodeURIComponent(stockQuery)}`); return openDetail(stock); }
      catch {
        if (/^[0-9A-Za-z.-]{1,12}$/.test(stockQuery)) return openDetail({ code: stockQuery, name: stockQuery });
        setStatus(`'${stockQuery}' 종목을 찾지 못했습니다.`);
        return activate("search");
      }
    }
    const view = target.searchParams.get("view");
    if (view === "morning-briefing") {
      openUtilitySheet("briefing");
      return;
    }
    return activate(NOTIFICATION_VIEW_MAP.get(view) || "notifications");
  }

  async function renderNotifications(token, suppliedItems = null) {
    if (!state.watchlistId) {
      const root = grid(); sheetTitle(root, "알림", "최근 3일 수신 내역"); statusRow(root, "알림 내역을 보려면 아이디로 로그인해주세요.", 3); elements.sheet.replaceChildren(root); return;
    }
    if (!suppliedItems) renderLoading("알림");
    try {
      const payload = suppliedItems ? { items: suppliedItems, retention_days: state.notificationRetentionDays } : await api(`/push/notifications/${encodeURIComponent(state.watchlistId)}?limit=100`, { headers: { "X-Write-Token": await ensureWriteToken() } });
      if (token !== state.renderToken) return;
      state.notificationItems = Array.isArray(payload.items) ? payload.items : [];
      state.notificationRetentionDays = payload.retention_days || 3;
      if (!suppliedItems) await refreshDesktopPushState();
      if (token !== state.renderToken) return;
      paintNotifications();
    } catch (error) { renderError("알림 내역을 불러오지 못했습니다.", error); }
  }

  async function openDetail(stock) {
    const code = text(stock.code, ""); if (!code) return;
    state.details.set(code, { code, name: stock.name || code, market: stock.market || "" }); renderTabs(); await activate(`detail:${code}`);
  }

  async function loadDesktopHomeContext(code) {
    const encoded = encodeURIComponent(code);
    try {
      return await cached(`/stocks/${encoded}/home-context?flow_limit=1500&research_limit=100&disclosure_limit=100&news_limit=60&community_limit=12`, 120000);
    } catch {
      const [flows, researchReports, disclosures, newsItems, community] = await Promise.all([
        cached(`/stocks/${encoded}/flows?limit=1500&pages=7`, 300000).catch(() => []),
        cached(`/research-reports?stock_code=${encoded}&limit=100`, 120000).catch(() => []),
        cached(`/disclosures?stock_code=${encoded}&limit=100`, 120000).catch(() => []),
        cached(`/news-items?query=${encoded}&limit=60`, 120000).catch(() => []),
        cached(`/stocks/${encoded}/community-feed?limit=12`, 300000).catch(() => ({ providers: [], message: "커뮤니티 글을 불러오지 못했습니다." })),
      ]);
      return { flows, research_reports: researchReports, disclosures, news_items: newsItems, community };
    }
  }

  async function renderDetail(code, token) {
    const stock = state.details.get(code) || { code, name: code };
    const encoded = encodeURIComponent(code);
    const detailView = state.detailTabs.get(code) || "summary";
    renderLoading(stock.name);
    try {
      let viewRequest;
      if (detailView === "summary") {
        viewRequest = loadDesktopHomeContext(code);
      } else if (detailView === "company") {
        viewRequest = Promise.all([
          cached(`/stocks/${encoded}/financials?limit=500`, 1800000).catch(() => []),
          cached(`/stocks/${encoded}/sector-operating-margins?limit=5&per_pair=1`, 21600000).catch(() => ({ companies: [], periods: [] })),
          cached(`/stocks/${encoded}/sga-analysis`, 43200000).catch(() => ({ available: false, categories: [], message: "판관비 세부 자료를 불러오지 못했습니다." })),
        ]);
      } else {
        viewRequest = cached(`/stocks/${encoded}/quant-signals`, 30000).catch(() => ({ data_state: "error", data_message: "AI 시그널을 불러오지 못했습니다." }));
      }

      const [dashboard, prices, intraday, viewData] = await Promise.all([
        cached(`/stocks/${encoded}/dashboard`, 30000),
        cached(`/stocks/${encoded}/prices?limit=1000`, 60000).catch(() => []),
        cached(`/stocks/${encoded}/intraday?limit=390`, 30000).catch(() => ({ points: [], message: "장중 가격 데이터가 없습니다.", source: "분봉 데이터" })),
        viewRequest,
      ]);
      if (token !== state.renderToken) return;

      state.details.set(code, { code, name: dashboard.name || stock.name, market: dashboard.market || stock.market || "" });
      renderTabs();
      const root = grid();
      renderDesktopDetailHeader(root, code, dashboard, prices, intraday);
      if (detailView === "summary") {
        renderDesktopStockHome(root, code, dashboard, prices, viewData || {});
      } else if (detailView === "company") {
        const [financials, sectorMargins, sgaAnalysis] = viewData;
        renderDesktopCompany(root, code, dashboard, prices, financials, sectorMargins, sgaAnalysis);
      } else {
        renderDesktopAISignal(root, code, dashboard, prices, viewData);
      }
      elements.sheet.replaceChildren(root);
      registerLiveQuote(code, { quote: dashboard.quote || {}, momentum: dashboard.momentum || {} });
      const viewLabel = { summary: "종목홈", company: "기업분석", strategy: "AI 시그널" }[detailView];
      setStatus(`${dashboard.name} ${viewLabel} 완료 · 실시간 시세 연결 중`);
    } catch (error) {
      renderError(`${stock.name} 상세 데이터를 불러오지 못했습니다.`, error);
    }
  }

  async function renderDetailLegacy(code, token) {
    const stock = state.details.get(code) || { code, name: code }; renderLoading(stock.name);
    try {
      const [dashboard, ai, prices, flows, financials, context, sectorMargins, sgaAnalysis, quantSignals] = await Promise.all([
        cached(`/stocks/${code}/dashboard`, 30000), cached(`/stocks/${code}/ai-analysis`, 60000), cached(`/stocks/${code}/prices?limit=90`, 60000),
        cached(`/stocks/${code}/flows?limit=40`, 120000).catch(() => []), cached(`/stocks/${code}/financials?limit=80`, 300000).catch(() => []),
        cached(`/stocks/${code}/home-context?flow_limit=40&research_limit=30&disclosure_limit=30&news_limit=60&community_limit=12`, 120000).catch(() => ({ research_reports: [], disclosures: [], news_items: [] })),
        cached(`/stocks/${code}/sector-operating-margins?limit=5`, 21600000).catch(() => ({ companies: [], periods: [] })),
        cached(`/stocks/${code}/sga-analysis`, 21600000).catch(() => ({ available: false, categories: [], message: "판관비 세부 자료를 불러오지 못했습니다." })),
        cached(`/stocks/${code}/quant-signals`, 30000).catch(() => ({ data_state: "error", data_message: "AI 시그널을 불러오지 못했습니다." })),
      ]);
      if (token !== state.renderToken) return; state.details.set(code, { code, name: dashboard.name, market: dashboard.market }); renderTabs();
      const root = grid(), quote = dashboard.quote || {}, valuation = dashboard.valuation || {}, momentum = dashboard.momentum || {};
      sheetTitle(root, `${dashboard.name} · ${dashboard.code}`, `${dashboard.market} · 실시간 시세`);
      detailTab(root, code, "summary", "종목홈", 0);
      detailTab(root, code, "company", "기업분석", 2);
      detailTab(root, code, "strategy", "AI 시그널", 4);
      const detailView = state.detailTabs.get(code) || "summary";
      if (detailView === "strategy") {
        renderDesktopQuantSignal(root, quantSignals);
        elements.sheet.replaceChildren(root);
        registerLiveQuote(code, { quote, momentum });
        setStatus(`${dashboard.name} AI 시그널 완료 · 실시간 시세 연결 중`);
        return;
      }
      section(root, "현재가", 0, 3, 4); headers(root, ["현재가(원)", "전일대비(원)", "등락률(%)", "거래대금(원)"], 0, 4);
      markLiveCell(addCell(root, `${number(quote.price)}원`, 0, 5, { className: "desk-cell-number" }), code, "price", quote.price, "price-won");
      markLiveCell(addCell(root, number(quote.change_value), 1, 5, { className: `desk-cell-number ${changeClass(quote.change_value)}` }), code, "change_value", quote.change_value, "change");
      markLiveCell(addCell(root, percent(quote.change_rate), 2, 5, { className: `desk-cell-number ${changeClass(quote.change_rate)}` }), code, "change_rate", quote.change_rate, "percent");
      markLiveCell(addCell(root, shortMoney(quote.trading_value), 3, 5, { className: "desk-cell-number" }), code, "trading_value", quote.trading_value, "money");
      section(root, "AI 분석", 0, 8, 8); headers(root, ["판단", "신뢰도(%)", "데이터(개)", "핵심 요약"], 0, 9, [1,1,1,5]);
      addCell(root, ai.stance, 0, 10); addCell(root, percent(ai.confidence), 1, 10, { className: "desk-cell-number" }); addCell(root, `${ai.data_covered || 0}/${ai.data_total || 0}`, 2, 10, { className: "desk-cell-center" }); addCell(root, ai.summary, 3, 10, { cols: 5, rows: 2, className: "desk-cell-wrap" });
      (ai.key_points || []).slice(0, 4).forEach((point, index) => addCell(root, `• ${point}`, 0, 13 + index, { cols: 8, className: "desk-cell-wrap" }));
      const detailChartAnalysis = computeDesktopChartAnalysis(prices);
      section(root, "차트분석 · 5일·10일 전망", 8, 3, 4); addCell(root, detailChartAnalysis.available ? desktopForecastChartSvg(detailChartAnalysis) : sparkline(prices.slice().reverse(), Number(quote.change_rate) < 0 ? "#1967d2" : "#d93025", "원"), 8, 4, { cols: 4, rows: 6, html: true, className: "desk-cell-chart desk-cell-forecast-chart" });
      headers(root, ["1개월 수익률(%)", "3개월 수익률(%)", "PER(배)", "PBR(배)"], 8, 11);
      markLiveCell(addCell(root, percent(momentum.one_month_return), 8, 12, { className: `desk-cell-number ${changeClass(momentum.one_month_return)}` }), code, "one_month_return", momentum.one_month_return, "percent");
      markLiveCell(addCell(root, percent(momentum.three_month_return), 9, 12, { className: `desk-cell-number ${changeClass(momentum.three_month_return)}` }), code, "three_month_return", momentum.three_month_return, "percent"); addCell(root, number(valuation.per, 2), 10, 12, { className: "desk-cell-number" }); addCell(root, number(valuation.pbr, 2), 11, 12, { className: "desk-cell-number" });
      section(root, "최근 수급", 0, 20, 6); headers(root, ["일자", "투자자", "순매수량(주)", "순매수금액(원)"], 0, 21, [1,2,1,2]);
      (flows || []).slice(0, 8).forEach((flow, index) => { const row = 22 + index; addCell(root, flow.trade_date, 0, row); addCell(root, flow.investor_type, 1, row, { cols: 2 }); addCell(root, number(flow.net_buy_volume), 3, row, { className: `desk-cell-number ${changeClass(flow.net_buy_volume)}` }); addCell(root, shortMoney(flow.net_buy_value), 4, row, { cols: 2, className: `desk-cell-number ${changeClass(flow.net_buy_value)}` }); });
      section(root, "주요 재무", 7, 20, 5); headers(root, ["연도", "계정", "당기(원)", "전기(원)"], 7, 21, [1,2,1,1]);
      (financials || []).filter((line) => line.current_amount !== null).slice(0, 8).forEach((line, index) => { const row = 22 + index; addCell(root, line.bsns_year, 7, row); addCell(root, line.account_name, 8, row, { cols: 2, title: line.account_name }); addCell(root, shortMoney(line.current_amount), 10, row, { className: "desk-cell-number" }); addCell(root, shortMoney(line.previous_amount), 11, row, { className: "desk-cell-number" }); });
      const quarterly = dashboard.financial_series?.quarterly || [];
      const financialUnit = dashboard.financial_series?.unit || "억원";
      section(root, `분기 실적 · 단위: ${financialUnit}`, 0, 33, 12);
      addCell(root, financialBarChart(quarterly, "operating_profit", financialUnit), 0, 34, { cols: 8, rows: 10, html: true, className: "desk-cell-chart" });
      addCell(root, marginLineChart(quarterly), 8, 34, { cols: 4, rows: 10, html: true, className: "desk-cell-chart" });
      headers(root, ["분기", `매출액(${financialUnit})`, `영업이익(${financialUnit})`, `순이익(${financialUnit})`, "영업이익률(%)", "순이익률(%)"], 0, 45, [2,2,2,2,2,2]);
      quarterly.slice(-6).forEach((point, index) => { const row = 46 + index; addCell(root, financialPeriodLabel(point.period, point.estimated), 0, row, { cols: 2 }); addCell(root, financialSeriesAmount(point.revenue, financialUnit), 2, row, { cols: 2, className: "desk-cell-number" }); addCell(root, financialSeriesAmount(point.operating_profit, financialUnit), 4, row, { cols: 2, className: `desk-cell-number ${changeClass(point.operating_profit)}` }); addCell(root, financialSeriesAmount(point.net_income, financialUnit), 6, row, { cols: 2, className: `desk-cell-number ${changeClass(point.net_income)}` }); addCell(root, percent(point.operating_margin), 8, row, { cols: 2, className: "desk-cell-number" }); addCell(root, percent(point.net_margin), 10, row, { cols: 2, className: "desk-cell-number" }); });

      const comparisonCompanies = sectorMargins?.companies || [];
      section(root, `동종 업계 영업이익률 · ${text(sectorMargins?.classification, "업종 분류 확인 중")}`, 0, 54, 12);
      if (comparisonCompanies.length >= 2) {
        addCell(root, sectorMarginLineChart(sectorMargins), 0, 55, { cols: 8, rows: 10, html: true, className: "desk-cell-chart desk-cell-sector-chart", ariaLabel: "동종 업계 영업이익률 추이 비교" });
        addCell(root, sectorMargins.basis, 8, 55, { cols: 4, className: "desk-cell-muted", title: sectorMargins.basis });
        addCell(root, "선택 종목 수익성 순위(위)", 8, 56, { cols: 2, className: "desk-cell-header" });
        addCell(root, `${number(sectorMargins.target_margin_rank)}위 / ${comparisonCompanies.length}개사`, 10, 56, { cols: 2, className: "desk-cell-number desk-cell-sector-highlight" });
        addCell(root, "업계 중앙값", 8, 57, { cols: 2 });
        addCell(root, ratioPercent(sectorMargins.peer_median_margin), 10, 57, { cols: 2, className: "desk-cell-number" });
        addCell(root, "중앙값 대비", 8, 58, { cols: 2 });
        addCell(root, percent(sectorMargins.target_margin_gap), 10, 58, { cols: 2, className: `desk-cell-number ${changeClass(sectorMargins.target_margin_gap)}` });
        headers(root, ["기업", "매출순위(위)", "최근 영업이익률(%)"], 8, 60, [2,1,1]);
        comparisonCompanies.slice(0, 5).forEach((company, index) => {
          const row = 61 + index;
          addCell(root, `${company.is_target ? "● " : "○ "}${company.name}`, 8, row, { cols: 2, className: company.is_target ? "desk-cell-sector-target" : "" });
          addCell(root, `${number(company.revenue_rank)}위`, 10, row, { className: "desk-cell-number" });
          addCell(root, ratioPercent(company.latest_operating_margin), 11, row, { className: `desk-cell-number ${company.is_target ? "desk-cell-sector-target" : ""}` });
        });
        addCell(root, `${sectorMargins.source} · 최근 실제 연간 실적 기준`, 0, 66, { cols: 12, className: "desk-cell-muted" });
      } else {
        addCell(root, "같은 업종에서 비교 가능한 연간 실적 기업이 부족합니다.", 0, 55, { cols: 12, className: "desk-cell-status" });
      }

      section(root, `판관비 심층분석 · ${text(sgaAnalysis?.period, "-")}년`, 0, 69, 12);
      if (sgaAnalysis?.available && (sgaAnalysis.categories || []).length) {
        headers(root, ["카테고리", "매출 대비(%)", "금액(억원)", "판관비 비중(%)", "세부 계정"], 0, 70, [2,2,2,2,4]);
        (sgaAnalysis.categories || []).slice(0, 9).forEach((category, index) => {
          const row = 71 + index, detail = sgaDetailText(category);
          addCell(root, `${index === 0 ? "▰ " : "▱ "}${category.label}`, 0, row, { cols: 2, className: index === 0 ? "desk-cell-sga-largest" : "" });
          addCell(root, ratioPercent(category.sales_ratio), 2, row, { cols: 2, className: `desk-cell-number ${index === 0 ? "desk-cell-sga-largest" : ""}` });
          addCell(root, financialSeriesAmount(category.amount, "억원", true), 4, row, { cols: 2, className: "desk-cell-number" });
          addCell(root, ratioPercent(category.share_of_sga, 1), 6, row, { cols: 2, className: "desk-cell-number" });
          addCell(root, detail || "세부 계정 미공시", 8, row, { cols: 4, title: detail || "세부 계정 미공시" });
        });
        addCell(root, "판매비와관리비 합계", 0, 81, { cols: 2, className: "desk-cell-header" });
        addCell(root, ratioPercent(sgaAnalysis.sales_ratio), 2, 81, { cols: 2, className: "desk-cell-number desk-cell-sga-total" });
        addCell(root, financialSeriesAmount(sgaAnalysis.total_amount, "억원", true), 4, 81, { cols: 2, className: "desk-cell-number desk-cell-sga-total" });
        addCell(root, `${sgaAnalysis.consolidated ? "연결" : "별도"} 기준 · 분류 일치 ${ratioPercent(sgaAnalysis.coverage_ratio, 1)}`, 6, 81, { cols: 4, className: "desk-cell-muted" });
        addCell(root, sgaAnalysis.source_url ? "DART 사업보고서 원문 ↗" : sgaAnalysis.source, 10, 81, { cols: 2, tag: sgaAnalysis.source_url ? "a" : "div", href: sgaAnalysis.source_url, className: sgaAnalysis.source_url ? "desk-cell-link" : "desk-cell-muted" });
        addCell(root, "금액은 공시 주석의 실제 계정을 투자 관점 카테고리로 묶었으며, 중간합계와 연구개발 중복은 제외했습니다.", 0, 82, { cols: 12, className: "desk-cell-muted" });
      } else {
        addCell(root, sgaAnalysis?.message || "판관비 총액은 확인되지만 세부 주석은 제공되지 않았습니다.", 0, 70, { cols: 12, className: "desk-cell-status" });
      }

      const profile = dashboard.company_profile || {};
      section(root, "기업 정보", 0, 85, 6); addCell(root, profile.summary || profile.short_summary || "기업 정보가 없습니다.", 0, 86, { cols: 6, rows: 3, className: "desk-cell-wrap" });
      headers(root, ["업종", "대표", "설립일", "홈페이지"], 0, 90, [2,1,1,2]); addCell(root, profile.industry || profile.sector, 0, 91, { cols: 2 }); addCell(root, profile.ceo_name, 2, 91); addCell(root, profile.established_date, 3, 91); addCell(root, profile.homepage_url ? "홈페이지 ↗" : "-", 4, 91, { cols: 2, tag: profile.homepage_url ? "a" : "div", href: profile.homepage_url, className: profile.homepage_url ? "desk-cell-link" : "" });
      section(root, "리서치 보고서", 7, 85, 5); headers(root, ["일자", "증권사", "의견", "목표가(원)", "제목·원문"], 7, 86);
      (context.research_reports || []).slice(0, 10).forEach((report, index) => { const row = 87 + index, href = report.detail_url || report.pdf_url; addCell(root, text(report.published_at).slice(0, 10), 7, row); addCell(root, report.broker_name, 8, row); addCell(root, report.opinion, 9, row); addCell(root, number(report.target_price), 10, row, { className: "desk-cell-number" }); addCell(root, report.title, 11, row, { tag: href ? "a" : "div", href, className: href ? "desk-cell-link" : "", title: report.title }); });
      if (!(context.research_reports || []).length) addCell(root, "등록된 리서치 보고서가 없습니다.", 7, 87, { cols: 5, className: "desk-cell-status" });

      section(root, "공시", 0, 100, 6); headers(root, ["일자", "분류", "공시 제목·원문"], 0, 101, [1,1,4]);
      (context.disclosures || []).slice(0, 10).forEach((item, index) => { const row = 102 + index; addCell(root, text(item.published_at).slice(0, 10), 0, row); addCell(root, item.disclosure_category, 1, row); addCell(root, item.report_name, 2, row, { cols: 4, tag: item.detail_url ? "a" : "div", href: item.detail_url, className: item.detail_url ? "desk-cell-link" : "", title: item.remark || item.report_name }); });
      section(root, "종목 뉴스", 7, 100, 5); headers(root, ["일자", "언론사", "뉴스 제목·원문"], 7, 101, [1,1,3]);
      (context.news_items || []).slice(0, 10).forEach((item, index) => { const row = 102 + index; addCell(root, text(item.published_at).slice(0, 10), 7, row); addCell(root, item.press_name || item.source, 8, row); addCell(root, item.title, 9, row, { cols: 3, tag: item.detail_url ? "a" : "div", href: item.detail_url, className: item.detail_url ? "desk-cell-link" : "", title: item.summary || item.title }); });

      const communityProviders = (context.community?.providers || []).filter((provider) => provider.key !== "threads");
      const communityItems = communityProviders.flatMap((provider) => (provider.items || []).map((item) => ({ ...item, providerLabel: provider.label, searchUrl: provider.search_url })));
      section(root, "커뮤니티", 0, 115, 12); headers(root, ["출처", "작성자", "반응", "내용", "공감(건)", "댓글(건)", "원문"], 0, 116, [1,1,1,5,1,1,2]);
      communityItems.slice(0, 12).forEach((item, index) => { const row = 117 + index; addCell(root, item.providerLabel || item.provider_key, 0, row); addCell(root, item.author_name || item.username, 1, row); addCell(root, item.impact || "중립", 2, row, { className: item.impact === "호재" ? "desk-cell-positive" : item.impact === "악재" ? "desk-cell-negative" : "" }); addCell(root, item.text || item.title, 3, row, { cols: 5, title: item.text || item.title }); addCell(root, number(item.like_count), 8, row, { className: "desk-cell-number" }); addCell(root, number(item.reply_count), 9, row, { className: "desk-cell-number" }); addCell(root, item.url ? "게시물 보기 ↗" : "게시판 보기 ↗", 10, row, { cols: 2, tag: item.url || item.searchUrl ? "a" : "div", href: item.url || item.searchUrl, className: item.url || item.searchUrl ? "desk-cell-link" : "" }); });
      if (!communityItems.length) addCell(root, context.community?.message || "관련 커뮤니티 글을 찾지 못했습니다.", 0, 117, { cols: 12, className: "desk-cell-status" });
      elements.sheet.replaceChildren(root); registerLiveQuote(code, { quote, momentum }); setStatus(`${dashboard.name} 상세 데이터 완료 · 실시간 시세 연결 중`);
    } catch (error) { renderError(`${stock.name} 상세 데이터를 불러오지 못했습니다.`, error); }
  }

  function renderError(message, error) {
    const root = grid(); sheetTitle(root, "오류", "데이터 연결 실패"); addCell(root, message, 0, 3, { cols: 8, className: "desk-cell-error" });
    addCell(root, "잠시 후 시트를 다시 선택해 재시도하세요.", 0, 4, { cols: 8, className: "desk-cell-status" }); elements.sheet.replaceChildren(root); setStatus(`오류 · ${error?.message || "요청 실패"}`);
  }

  function renderTabs() {
    elements.tabs.replaceChildren();
    const utilityTabs = Array.from(state.openUtilitySheets).map((id) => ({ ...UTILITY_SHEETS[id], detail: true, kind: "utility" })).filter((item) => item.id);
    const recommendationTabs = Array.from(state.recommendationDetails.values()).map((detail) => ({ id: `recommend:${detail.code}`, label: `${detail.name} AI`, detail: true, kind: "recommendation" }));
    const stockTabs = Array.from(state.details.values()).map((detail) => ({ id: `detail:${detail.code}`, label: detail.name, detail: true, kind: "stock" }));
    [...FIXED_SHEETS, ...utilityTabs, ...recommendationTabs, ...stockTabs].forEach((sheet) => {
      const button = document.createElement("button"); button.type = "button"; button.className = `desk-tab${sheet.detail ? " desk-tab-detail" : ""}${sheet.utility ? " desk-tab-utility" : ""}`; button.setAttribute("role", "tab"); button.setAttribute("aria-selected", String(state.active === sheet.id));
      button.textContent = sheet.label; button.addEventListener("click", () => activate(sheet.id));
      if (sheet.detail) {
        const close = document.createElement("span"); close.className = "desk-tab-close"; close.textContent = "×"; close.setAttribute("role", "button"); close.setAttribute("aria-label", `${sheet.label} 시트 닫기`); close.tabIndex = 0;
        close.addEventListener("click", (event) => { event.stopPropagation(); closeDynamicSheet(sheet); });
        close.addEventListener("keydown", (event) => { if (event.key !== "Enter" && event.key !== " ") return; event.preventDefault(); event.stopPropagation(); closeDynamicSheet(sheet); });
        button.appendChild(close);
      }
      elements.tabs.appendChild(button);
    });
  }

  function openUtilitySheet(id) {
    if (!UTILITY_SHEETS[id]) return;
    state.openUtilitySheets.add(id); renderTabs(); activate(id);
  }

  function closeDynamicSheet(sheet) {
    if (sheet.kind === "utility") state.openUtilitySheets.delete(sheet.id);
    else if (sheet.kind === "recommendation") state.recommendationDetails.delete(sheet.id.slice(10));
    else if (sheet.kind === "stock") state.details.delete(sheet.id.slice(7));
    if (state.active === sheet.id) activate(sheet.kind === "stock" ? "search" : "home", { replaceHistory: true });
    else renderTabs();
  }

  function closeDetail(code) {
    state.details.delete(code); if (state.active === `detail:${code}`) activate("search", { replaceHistory: true }); else renderTabs();
  }

  async function activate(id, options = {}) {
    if (!VIEW_ALIASES.has(id) && !id.startsWith("detail:") && !id.startsWith("recommend:")) id = "home";
    if (UTILITY_SHEETS[id]) state.openUtilitySheets.add(id);
    resetLiveUpdates(); state.active = id; state.renderToken += 1; const token = state.renderToken; renderTabs(); elements.gridShell.scrollTo({ top: 0, left: 0 });
    const params = new URLSearchParams();
    if (id.startsWith("detail:")) { params.set("view", "detail"); params.set("code", id.slice(7)); }
    else if (id.startsWith("recommend:")) { params.set("view", "recommend"); params.set("code", id.slice(10)); }
    else params.set("view", id);
    history[options.replaceHistory ? "replaceState" : "pushState"]({ view: id }, "", `/desktop?${params}`);
    if (id === "home") await renderHome(token);
    else if (id === "search") await renderSearch(token);
    else if (id === "portfolio") await renderPortfolio(token);
    else if (id === "chart") renderChart();
    else if (id === "notifications") await renderNotifications(token);
    else if (id === "briefing") await renderDesktopMorningMoneyBriefing(token);
    else if (id === "signals") await renderDesktopSignals(token);
    else if (id === "movers") await renderDesktopMovers(token);
    else if (id.startsWith("recommend:")) await renderDesktopRecommendationDetail(id.slice(10), token);
    else await renderDetail(id.slice(7), token);
  }

  function selectCell(node) {
    elements.sheet.querySelectorAll(".is-selected").forEach((cell) => cell.classList.remove("is-selected")); node.classList.add("is-selected");
    state.selectedCell = node.dataset.cell; elements.nameBox.textContent = state.selectedCell; elements.formulaValue.textContent = node.textContent.trim();
  }

  function setStatus(message) { elements.status.textContent = message; }

  function setLoginDialogOpen(open) {
    elements.login.hidden = !open;
    elements.app.toggleAttribute("inert", open);
    if (open) {
      window.setTimeout(() => { if (!elements.login.hidden) elements.loginId.focus(); }, 0);
      return;
    }
    elements.tabs.querySelector('[role="tab"][aria-selected="true"]')?.focus();
  }

  function trapLoginDialogFocus(event) {
    if (event.key !== "Tab" || elements.login.hidden) return;
    const controls = Array.from(elements.login.querySelectorAll("input:not(:disabled), button:not(:disabled)"))
      .filter((control) => control.offsetParent !== null);
    if (!controls.length) return;
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  }

  function setSidePanelCollapsed(collapsed) {
    document.body.classList.toggle("desk-side-collapsed", collapsed);
    elements.sideToggle.setAttribute("aria-expanded", String(!collapsed));
    elements.sideToggle.setAttribute("aria-label", collapsed ? "측면 패널 표시" : "측면 패널 숨기기");
    elements.sideToggle.title = collapsed ? "측면 패널 표시" : "측면 패널 숨기기";
    localStorage.setItem(SIDE_PANEL_COLLAPSED_KEY, collapsed ? "1" : "0");
  }

  function documentTitleStorageKey() {
    return `${DOCUMENT_TITLE_KEY_PREFIX}${state.watchlistId}`;
  }

  function documentTitlePendingKey() {
    return `${DOCUMENT_TITLE_PENDING_PREFIX}${state.watchlistId}`;
  }

  function persistDocumentTitlePending(pending) {
    if (pending) localStorage.setItem(documentTitlePendingKey(), "1");
    else localStorage.removeItem(documentTitlePendingKey());
  }

  function resizeDocumentTitle() {
    const visualLength = Array.from(elements.documentTitle.value).reduce((total, char) => total + (/[^\x00-\xff]/.test(char) ? 18 : 10), 0);
    elements.documentTitle.style.width = `${Math.min(420, Math.max(210, visualLength + 24))}px`;
  }

  function setDocumentTitle(value) {
    const title = String(value || "").trim() || DEFAULT_DOCUMENT_TITLE;
    elements.documentTitle.value = title;
    document.title = `${title} – 비밀노트`;
    resizeDocumentTitle();
    return title;
  }

  function setDocumentSaveState(message, status = "") {
    elements.saveState.textContent = message;
    if (status) elements.saveState.dataset.state = status;
    else delete elements.saveState.dataset.state;
  }

  async function responseError(response, fallback) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload?.detail;
    if (typeof detail === "string") return detail;
    if (detail?.message) return detail.message;
    return fallback;
  }

  async function establishDesktopSession(force = false) {
    if (state.desktopSessionReady && !force) return;
    if (!state.watchlistId) throw new Error("사용자 아이디가 필요합니다.");
    const response = await fetch("/desktop/session", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ share_id: state.watchlistId }),
    });
    if (!response.ok) throw new Error(await responseError(response, "PC 저장 세션을 열지 못했습니다."));
    state.desktopSessionReady = true;
  }

  async function putDocumentPreference(documentTitle, retry = true) {
    const response = await fetch("/desktop/preferences", {
      method: "PUT",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_title: documentTitle }),
    });
    if (response.status === 401 && retry) {
      state.desktopSessionReady = false;
      await establishDesktopSession(true);
      return putDocumentPreference(documentTitle, false);
    }
    if (!response.ok) throw new Error(await responseError(response, "문서 제목을 저장하지 못했습니다."));
    return response.json();
  }

  async function saveDocumentTitle() {
    window.clearTimeout(state.documentTitleSaveTimer);
    state.documentTitleSaveTimer = 0;
    const documentTitle = elements.documentTitle.value.trim();
    const saveVersion = state.documentTitleSaveVersion;
    if (!documentTitle) {
      setDocumentTitle(state.documentTitle);
      localStorage.setItem(documentTitleStorageKey(), state.documentTitle);
      persistDocumentTitlePending(state.documentTitlePending);
      setDocumentSaveState("제목은 비워둘 수 없어 이전 제목을 복원했습니다.", "local");
      return;
    }
    localStorage.setItem(documentTitleStorageKey(), documentTitle);
    setDocumentSaveState("저장 중…", "saving");
    try {
      await establishDesktopSession();
      const payload = await putDocumentPreference(documentTitle);
      if (saveVersion !== state.documentTitleSaveVersion || elements.documentTitle.value.trim() !== documentTitle) return;
      state.documentTitle = setDocumentTitle(payload.document_title || documentTitle);
      state.documentTitlePending = false;
      localStorage.setItem(documentTitleStorageKey(), state.documentTitle);
      persistDocumentTitlePending(false);
      setDocumentSaveState("클라우드에 저장됨", "saved");
    } catch {
      if (saveVersion !== state.documentTitleSaveVersion) return;
      state.documentTitle = setDocumentTitle(documentTitle);
      state.documentTitlePending = true;
      persistDocumentTitlePending(true);
      setDocumentSaveState("이 브라우저에 저장됨", "local");
    }
  }

  function scheduleDocumentTitleSave() {
    state.documentTitleSaveVersion += 1;
    resizeDocumentTitle();
    const pendingTitle = elements.documentTitle.value.trim();
    if (pendingTitle) {
      localStorage.setItem(documentTitleStorageKey(), pendingTitle);
      persistDocumentTitlePending(true);
    }
    setDocumentSaveState("저장 대기 중…", "saving");
    window.clearTimeout(state.documentTitleSaveTimer);
    state.documentTitleSaveTimer = window.setTimeout(saveDocumentTitle, 700);
  }

  async function loadDocumentPreferences() {
    if (!state.watchlistId) {
      elements.documentTitle.disabled = true;
      setDocumentSaveState("로그인 후 저장");
      return;
    }
    const loadVersion = state.documentTitleSaveVersion;
    const localTitle = (localStorage.getItem(documentTitleStorageKey()) || "").trim();
    state.documentTitlePending = localStorage.getItem(documentTitlePendingKey()) === "1";
    state.documentTitle = setDocumentTitle(localTitle || DEFAULT_DOCUMENT_TITLE);
    elements.documentTitle.disabled = false;
    setDocumentSaveState("클라우드 확인 중…", "saving");
    try {
      await establishDesktopSession();
      const response = await fetch("/desktop/preferences", { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) throw new Error(await responseError(response, "PC 설정을 불러오지 못했습니다."));
      const payload = await response.json();
      if (loadVersion !== state.documentTitleSaveVersion) {
        await saveDocumentTitle();
        return;
      }
      if ((state.documentTitlePending && localTitle) || (!payload.updated_at && localTitle && localTitle !== DEFAULT_DOCUMENT_TITLE)) {
        await saveDocumentTitle();
        return;
      }
      state.documentTitle = setDocumentTitle(payload.document_title || DEFAULT_DOCUMENT_TITLE);
      state.documentTitlePending = false;
      localStorage.setItem(documentTitleStorageKey(), state.documentTitle);
      persistDocumentTitlePending(false);
      setDocumentSaveState("클라우드에 저장됨", "saved");
    } catch {
      setDocumentSaveState("이 브라우저에 저장됨", "local");
    }
  }

  async function refreshInvite() {
    try { const payload = await api("/session/invite-status"); state.inviteRequired = payload.required !== false; state.inviteAuthorized = payload.authorized === true || !state.inviteRequired; }
    catch { state.inviteRequired = true; state.inviteAuthorized = false; }
    elements.inviteWrap.hidden = !state.inviteRequired || state.inviteAuthorized; elements.inviteCode.required = !elements.inviteWrap.hidden;
  }

  async function login(event) {
    event.preventDefault(); const id = elements.loginId.value.trim(); if (id.length < 2) { elements.loginStatus.textContent = "아이디를 두 글자 이상 입력해주세요."; return; }
    elements.loginStatus.textContent = "접속 권한을 확인하고 있습니다…";
    try {
      if (state.inviteRequired && !state.inviteAuthorized) {
        const invite = await fetch("/session/invite-access", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ invite_code: elements.inviteCode.value.trim().toUpperCase() }) });
        if (!invite.ok) throw new Error(invite.status === 429 ? "입력 횟수가 많습니다. 잠시 후 다시 시도해주세요." : "초대 코드를 확인해주세요."); state.inviteAuthorized = true;
      }
      if (state.inviteRequired) {
        const access = await fetch("/session/dashboard-access", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ share_id: id }) });
        if (!access.ok) { const payload = await access.json().catch(() => ({})); throw new Error(payload?.detail?.message || "이용 권한을 확인하지 못했습니다."); }
      }
      state.watchlistId = id; state.desktopSessionReady = false; await establishDesktopSession();
      localStorage.setItem(WATCHLIST_ID_KEY, id); elements.account.innerHTML = `<span>${id.slice(0, 1).toUpperCase()}</span>`; elements.account.title = `${id} 사용자`; setLoginDialogOpen(false);
      await loadDocumentPreferences(); await activate(state.active, { replaceHistory: true });
    } catch (error) { elements.loginStatus.textContent = error.message || "로그인하지 못했습니다."; }
  }

  async function boot() {
    initializeHeaders(); renderTabs(); chartTooltipEvents(); elements.sheet.addEventListener("click", (event) => { const cell = event.target.closest("[data-cell]"); if (cell) selectCell(cell); });
    void registerDesktopServiceWorker();
    elements.sheet.addEventListener("keydown", (event) => { if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-cell]")) event.target.click(); });
    setSidePanelCollapsed(localStorage.getItem(SIDE_PANEL_COLLAPSED_KEY) === "1");
    elements.sideToggle.addEventListener("click", () => setSidePanelCollapsed(!document.body.classList.contains("desk-side-collapsed")));
    elements.loginForm.addEventListener("submit", login); elements.login.addEventListener("keydown", trapLoginDialogFocus); window.addEventListener("popstate", () => restoreRoute());
    document.addEventListener("focusin", (event) => {
      if (!elements.login.hidden && !elements.login.contains(event.target)) elements.loginId.focus();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) pauseLiveQuoteStream();
      else if (state.liveQuoteModels.size) connectLiveQuoteStream();
    });
    window.addEventListener("online", () => { if (state.liveQuoteModels.size) connectLiveQuoteStream(); });
    window.addEventListener("offline", () => { pauseLiveQuoteStream(); setStatus("네트워크 대기 · 기존 시세 유지"); });
    elements.documentTitle.addEventListener("input", scheduleDocumentTitleSave);
    elements.documentTitle.addEventListener("blur", () => {
      if (elements.documentTitle.value.trim() !== state.documentTitle || state.documentTitleSaveTimer) saveDocumentTitle();
    });
    elements.documentTitle.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); elements.documentTitle.blur(); }
      if (event.key === "Escape") {
        event.preventDefault(); window.clearTimeout(state.documentTitleSaveTimer); state.documentTitleSaveTimer = 0; state.documentTitleSaveVersion += 1;
        setDocumentTitle(state.documentTitle); localStorage.setItem(documentTitleStorageKey(), state.documentTitle); elements.documentTitle.blur();
        persistDocumentTitlePending(state.documentTitlePending);
        setDocumentSaveState(state.documentTitlePending ? "이 브라우저에 저장됨" : "클라우드에 저장됨", state.documentTitlePending ? "local" : "saved");
      }
    });
    const timer = () => { const now = new Date(); elements.marketClock.textContent = `${now.toLocaleDateString("ko-KR")} ${now.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}`; }; timer(); window.setInterval(timer, 30000);
    await refreshInvite(); state.watchlistId = (localStorage.getItem(WATCHLIST_ID_KEY) || "").trim();
    if (state.watchlistId) { elements.account.innerHTML = `<span>${state.watchlistId.slice(0, 1).toUpperCase()}</span>`; elements.account.title = `${state.watchlistId} 사용자`; void loadDocumentPreferences(); }
    else { setLoginDialogOpen(true); await loadDocumentPreferences(); }
    await restoreRoute();
  }

  async function restoreRoute() {
    const params = new URLSearchParams(location.search); const view = params.get("view") || "home"; const code = (params.get("code") || "").replace(/[^0-9A-Za-z.-]/g, ""); const notificationUrl = params.get("notification_url") || "";
    if (notificationUrl) { await openNotification({ url: notificationUrl }); return; }
    if (view === "detail" && code) { state.details.set(code, { code, name: code }); await activate(`detail:${code}`, { replaceHistory: true }); }
    else if (view === "recommend" && code) { await activate(`recommend:${code}`, { replaceHistory: true }); }
    else await activate(VIEW_ALIASES.has(view) ? view : "home", { replaceHistory: true });
  }

  boot();
})();
