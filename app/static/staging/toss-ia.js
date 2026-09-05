/*
 * Secret Note — Toss Securities reference shell
 *
 * The canonical dashboard and isolated staging review share this information
 * architecture layer while keeping financial values sourced from the base app.
 */

(() => {
  "use strict";

  const isIosDevice = /iP(?:hone|ad|od)/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isStandaloneDisplay = window.matchMedia("(display-mode: standalone)").matches
    || navigator.standalone === true;
  document.documentElement.toggleAttribute(
    "data-staging-ios-standalone",
    isIosDevice && isStandaloneDisplay,
  );

  const dashboard = document.querySelector(".dashboard-detail-system");
  const bottomNav = document.getElementById("bottom-nav");
  const topbar = document.querySelector(".app-topbar");
  const originalTopbarActions = document.querySelector(".app-topbar-actions");
  if (!dashboard || !bottomNav || !topbar || !originalTopbarActions) return;

  document.documentElement.classList.add("staging-tds-video");
  document.body.dataset.stagingIa = "tds-video";
  document.body.dataset.stagingFidelity = "20260829-v66";
  document.body.dataset.stagingInput = "pointer";
  const stagingGptPageSummaryEnabled = Boolean(
    document.querySelector('meta[name="secret-note-page-summary"][content="enabled"]'),
  );

  window.addEventListener("keydown", (event) => {
    if (event.key === "Tab" || event.key.startsWith("Arrow")) {
      document.body.dataset.stagingInput = "keyboard";
    }
  }, true);
  window.addEventListener("pointerdown", () => {
    document.body.dataset.stagingInput = "pointer";
  }, true);

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const help = target?.closest(".recommend-score-help");
    if (!help) return;
    event.preventDefault();
    event.stopPropagation();
    const nextOpen = !help.classList.contains("open");
    for (const item of document.querySelectorAll(".recommend-score-help.open")) {
      item.classList.remove("open");
      item.setAttribute("aria-expanded", "false");
    }
    help.classList.toggle("open", nextOpen);
    help.setAttribute("aria-expanded", String(nextOpen));
    if (!nextOpen && help instanceof HTMLElement) help.blur();
  }, true);

  const plump = (symbol) => Object.freeze({ symbol });
  const stagingIntegerFormatter = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
  const formatNumber = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? stagingIntegerFormatter.format(number) : "-";
  };
  const formatPercent = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return "-";
    return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
  };
  const STAGING_PAGE_SUMMARY_PATH = "/ai/page-summary";
  const STAGING_PAGE_SUMMARY_TIMEOUT_MS = 9_000;
  const STAGING_PAGE_SUMMARY_CACHE_MS = 30 * 60 * 1000;
  const stagingPageSummaryCache = new Map();
  const stagingJsonRequest = async (url, options = {}) => {
    const controller = new AbortController();
    const timeoutMs = Number(options.timeoutMs) > 0 ? Number(options.timeoutMs) : 12_000;
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {
        ...options,
        timeoutMs: undefined,
        headers: {
          Accept: "application/json",
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...(options.headers || {}),
        },
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!response.ok) {
        const error = new Error(`staging request failed: ${response.status}`);
        error.status = response.status;
        throw error;
      }
      return response.json();
    } finally {
      window.clearTimeout(timeoutId);
    }
  };
  const requestStagingPageSummary = async (pageType, facts, fallback) => {
    const requestBody = { page_type: pageType, facts, fallback };
    const cacheKey = JSON.stringify(requestBody);
    const cached = stagingPageSummaryCache.get(cacheKey);
    if (cached && Date.now() - cached.savedAt <= STAGING_PAGE_SUMMARY_CACHE_MS) {
      return { ...cached.payload, cache_hit: true };
    }
    const payload = await stagingJsonRequest(STAGING_PAGE_SUMMARY_PATH, {
      method: "POST",
      cache: "no-store",
      body: JSON.stringify(requestBody),
      timeoutMs: STAGING_PAGE_SUMMARY_TIMEOUT_MS,
    });
    stagingPageSummaryCache.set(cacheKey, { savedAt: Date.now(), payload });
    return payload;
  };
  const svg = (icon, className = "") => {
    if (icon && typeof icon === "object" && icon.symbol) {
      const classes = ["staging-plump-icon", className].filter(Boolean).join(" ");
      return `
        <svg class="${classes}" viewBox="0 0 36 36" data-staging-icon="${icon.symbol}" aria-hidden="true" focusable="false">
          <use href="/assets/staging/streamline-plump-icons.svg?v=20260828-v64#${icon.symbol}"></use>
        </svg>
      `;
    }
    return `
      <svg${className ? ` class="${className}"` : ""} viewBox="0 0 24 24" aria-hidden="true" focusable="false">${icon}</svg>
    `;
  };

  /*
   * Header actions use one optical system instead of mixing the 24px outline
   * glyphs with the 36px filled sprite. Every glyph shares the same canvas,
   * stroke, caps, and rendered box so route changes do not change visual weight.
   */
  const topActionGlyphs = Object.freeze({
    bell: '<path d="M27.5 16.5a9.5 9.5 0 0 0-19 0c0 6.2-2.4 8.65-3 10.2-.35.9.34 1.8 1.3 1.8h22.4c.96 0 1.65-.9 1.3-1.8-.6-1.55-3-4-3-10.2Z"></path><path d="M14.5 31c.82.75 2.01 1.2 3.5 1.2s2.68-.45 3.5-1.2"></path>',
    ai: '<path d="M15 5.5c.64 5.34 4.16 8.86 9.5 9.5-5.34.64-8.86 4.16-9.5 9.5-.64-5.34-4.16-8.86-9.5-9.5 5.34-.64 8.86-4.16 9.5-9.5Z"></path><path d="M27.5 21.5c.25 2.64 1.86 4.25 4.5 4.5-2.64.25-4.25 1.86-4.5 4.5-.25-2.64-1.86-4.25-4.5-4.5 2.64-.25 4.25-1.86 4.5-4.5Z"></path>',
    search: '<circle cx="15.8" cy="15.8" r="9.3"></circle><path d="m22.7 22.7 7.8 7.8"></path>',
  });
  const topActionSvg = (name, className = "") => {
    const glyph = topActionGlyphs[name];
    if (!glyph) return "";
    const classes = ["staging-top-action-icon", className].filter(Boolean).join(" ");
    return `
      <svg class="${classes}" viewBox="0 0 36 36" data-staging-top-icon="${name}" aria-hidden="true" focusable="false">
        ${glyph}
      </svg>
    `;
  };

  const icons = {
    ai: '<path d="M12 2.8 9.9 8.5 4.2 10.6l5.7 2.2L12 18.5l2.2-5.7 5.7-2.2-5.7-2.1L12 2.8Z"></path><path d="m18.7 16.2-.8 2.1-2.1.8 2.1.8.8 2.1.8-2.1 2.1-.8-2.1-.8-.8-2.1Z"></path>',
    search: plump("search"),
    stockSearch: '<circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path>',
    home: plump("home"),
    interest: plump("interest"),
    discover: plump("discover"),
    feed: plump("feed"),
    back: plump("back"),
    chart: plump("chart"),
    ranking: plump("home"),
    briefing: plump("briefing"),
    chevron: plump("chevron"),
    clock: plump("clock"),
    coin: plump("coin"),
    news: plump("news"),
    globe: plump("globe"),
    flag: plump("flag"),
    external: plump("external"),
    horizontal: plump("horizontal"),
    stock: plump("stock"),
    pin: plump("pin"),
  };

  const SERVICE_UPDATE_RELEASE = Object.freeze({
    key: "20260829-chart-analysis-v1",
    label: "8월 29일 업데이트",
    title: "비밀노트가 새로워졌어요",
    startsAt: "2026-08-29T00:00:00+09:00",
    endsAt: "2026-09-05T00:00:00+09:00",
  });
  // The release page remains addressable, but the interruptive announcement is off.
  const serviceUpdatePopupEnabled = false;
  const serviceUpdateWithinPublishingWindow = (now = Date.now()) => {
    const startsAt = Date.parse(SERVICE_UPDATE_RELEASE.startsAt);
    const endsAt = Date.parse(SERVICE_UPDATE_RELEASE.endsAt);
    return Number.isFinite(startsAt) && Number.isFinite(endsAt) && now >= startsAt && now < endsAt;
  };
  const serviceUpdateEnabled = serviceUpdateWithinPublishingWindow() && Boolean(
    document.querySelector(
      `meta[name="secret-note-service-update"][content="${SERVICE_UPDATE_RELEASE.key}"]`,
    ) || document.querySelector('meta[name="secret-note-environment"][content="staging"]'),
  );
  const serviceUpdateDismissKey = `secret-note-service-update-dismissed:${SERVICE_UPDATE_RELEASE.key}`;
  const serviceUpdateSessionKey = `secret-note-service-update-session:${SERVICE_UPDATE_RELEASE.key}`;
  const serviceUpdateEntryGate = document.getElementById("login-gate");
  let serviceUpdateLastFocus = null;
  let serviceUpdateEntryGateObserver = null;
  let serviceUpdateDialog = null;
  let serviceUpdatePage = null;

  const serviceUpdateStored = (storage, key) => {
    try {
      return storage.getItem(key) === "1";
    } catch {
      return false;
    }
  };
  const storeServiceUpdate = (storage, key) => {
    try {
      storage.setItem(key, "1");
    } catch {
      // Storage can be unavailable in private browsing; dismissal remains best effort.
    }
  };
  const serviceUpdateRoute = () => new URLSearchParams(window.location.search).get("view") || "home";
  const setServiceUpdateBackgroundInert = (inert) => {
    if ("inert" in dashboard) dashboard.inert = Boolean(inert);
  };
  const serviceUpdateFocusable = (root) => Array.from(root?.querySelectorAll(
    'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
  ) || []).filter((node) => !node.hidden && node.getAttribute("aria-hidden") !== "true");
  const serviceUpdateShouldBlockNotificationPrompt = () => {
    if (!serviceUpdatePopupEnabled || !serviceUpdateEnabled) return false;
    if (serviceUpdateDialog && !serviceUpdateDialog.hidden) return true;
    if (serviceUpdatePage && !serviceUpdatePage.hidden) return true;
    return serviceUpdateRoute() !== "service-update"
      && !serviceUpdateStored(window.localStorage, serviceUpdateDismissKey)
      && !serviceUpdateStored(window.sessionStorage, serviceUpdateSessionKey);
  };
  window.secretNoteServiceUpdateGate = Object.freeze({
    release: SERVICE_UPDATE_RELEASE.key,
    startsAt: SERVICE_UPDATE_RELEASE.startsAt,
    endsAt: SERVICE_UPDATE_RELEASE.endsAt,
    popupEnabled: serviceUpdatePopupEnabled,
    isPublishing: serviceUpdateWithinPublishingWindow,
    blocksNotificationPrompt: serviceUpdateShouldBlockNotificationPrompt,
  });

  const closeServiceUpdateDialog = ({ dismissVersion = false, rememberSession = true, restoreFocus = true } = {}) => {
    if (!serviceUpdateDialog || serviceUpdateDialog.hidden) return;
    if (dismissVersion) storeServiceUpdate(window.localStorage, serviceUpdateDismissKey);
    if (rememberSession) storeServiceUpdate(window.sessionStorage, serviceUpdateSessionKey);
    serviceUpdateDialog.hidden = true;
    document.body.classList.remove("staging-update-dialog-open");
    if (!serviceUpdatePage || serviceUpdatePage.hidden) setServiceUpdateBackgroundInert(false);
    if (restoreFocus && serviceUpdateLastFocus instanceof HTMLElement) serviceUpdateLastFocus.focus();
  };

  const closeServiceUpdatePage = ({ restoreFocus = true } = {}) => {
    if (!serviceUpdatePage || serviceUpdatePage.hidden) return;
    serviceUpdatePage.hidden = true;
    document.body.classList.remove("staging-service-update-open");
    setServiceUpdateBackgroundInert(false);
    if (restoreFocus && serviceUpdateLastFocus instanceof HTMLElement) serviceUpdateLastFocus.focus();
  };

  const serviceUpdateHomeUrl = () => {
    const url = new URL(window.location.href);
    url.pathname = "/dashboard";
    url.searchParams.set("view", "home");
    url.searchParams.delete("panel");
    return `${url.pathname}${url.search}${url.hash}`;
  };

  const leaveServiceUpdatePage = () => {
    window.history.replaceState({ ...(window.history.state || {}), stagingServiceUpdate: null }, "", serviceUpdateHomeUrl());
    closeServiceUpdatePage();
    if (typeof setView === "function") setView("home", { historyMode: "none" });
    window.scrollTo({ top: 0, behavior: "auto" });
    window.dispatchEvent(new CustomEvent("secret-note:service-update-home-reentry"));
  };

  const openServiceUpdatePage = ({ historyMode = "push" } = {}) => {
    if (!serviceUpdateEnabled || !serviceUpdatePage) return;
    closeServiceUpdateDialog({ rememberSession: true, restoreFocus: false });
    serviceUpdateLastFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : serviceUpdateLastFocus;
    if (historyMode === "push") {
      const url = new URL(window.location.href);
      url.pathname = "/dashboard";
      url.searchParams.set("view", "service-update");
      url.searchParams.delete("panel");
      window.history.pushState({ ...(window.history.state || {}), stagingServiceUpdate: true }, "", url);
    }
    serviceUpdatePage.hidden = false;
    document.body.classList.add("staging-service-update-open");
    setServiceUpdateBackgroundInert(true);
    serviceUpdatePage.scrollTo({ top: 0, behavior: "auto" });
    serviceUpdatePage.querySelector("[data-service-update-back]")?.focus();
  };

  const openServiceUpdateTarget = (view) => {
    closeServiceUpdatePage({ restoreFocus: false });
    if (typeof setView === "function") {
      setView(view);
    } else {
      window.location.assign(`/dashboard?view=${encodeURIComponent(view)}`);
    }
    window.scrollTo({ top: 0, behavior: "auto" });
  };

  const openServiceUpdateDialog = () => {
    if (!serviceUpdatePopupEnabled || !serviceUpdateEnabled || !serviceUpdateDialog || !serviceUpdateDialog.hidden) return;
    if (serviceUpdateRoute() === "service-update") return;
    if (serviceUpdateEntryGate && !serviceUpdateEntryGate.hidden) return;
    if (serviceUpdateStored(window.localStorage, serviceUpdateDismissKey)) return;
    if (serviceUpdateStored(window.sessionStorage, serviceUpdateSessionKey)) return;
    window.dispatchEvent(new CustomEvent("secret-note:service-update-priority"));
    serviceUpdateLastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    serviceUpdateDialog.hidden = false;
    document.body.classList.add("staging-update-dialog-open");
    setServiceUpdateBackgroundInert(true);
    serviceUpdateDialog.querySelector("[data-service-update-detail]")?.focus();
  };

  const openServiceUpdateDialogOnFirstEntry = () => {
    if (!serviceUpdatePopupEnabled || !serviceUpdateEnabled || serviceUpdateRoute() === "service-update") return;
    if (!serviceUpdateEntryGate || serviceUpdateEntryGate.hidden) {
      serviceUpdateEntryGateObserver?.disconnect();
      serviceUpdateEntryGateObserver = null;
      openServiceUpdateDialog();
      return;
    }
    if (serviceUpdateEntryGateObserver) return;
    serviceUpdateEntryGateObserver = new MutationObserver(() => {
      if (!serviceUpdateEntryGate.hidden) return;
      serviceUpdateEntryGateObserver?.disconnect();
      serviceUpdateEntryGateObserver = null;
      openServiceUpdateDialog();
    });
    serviceUpdateEntryGateObserver.observe(serviceUpdateEntryGate, {
      attributes: true,
      attributeFilter: ["hidden"],
    });
  };

  const setupServiceUpdateExperience = () => {
    if (!serviceUpdateEnabled) return;
    serviceUpdateDialog = document.createElement("div");
    serviceUpdateDialog.id = "staging-service-update-dialog";
    serviceUpdateDialog.className = "staging-service-update-dialog";
    serviceUpdateDialog.hidden = true;
    serviceUpdateDialog.innerHTML = `
      <section class="staging-service-update-card" role="dialog" aria-modal="true" aria-labelledby="staging-service-update-title" aria-describedby="staging-service-update-summary">
        <div class="staging-service-update-creative">
          <header class="staging-service-update-card-head">
            <span><b>NEW</b>${SERVICE_UPDATE_RELEASE.label}</span>
            <span>비밀노트</span>
          </header>
          <div class="staging-service-update-card-copy">
            <small>더 빠른 투자 판단</small>
            <h2 id="staging-service-update-title">${SERVICE_UPDATE_RELEASE.title}</h2>
            <p id="staging-service-update-summary">새로운 차트 분석과 더 쉬워진 AI 시그널을 지금 확인해보세요.</p>
          </div>
          <div class="staging-service-update-visual" aria-hidden="true">
            <div class="staging-service-update-visual-card">
              <span class="staging-service-update-visual-label">차트 분석</span>
              <svg viewBox="0 0 240 92" focusable="false">
                <path class="staging-service-update-grid" d="M4 20h232M4 48h232M4 76h232"></path>
                <path class="staging-service-update-line" d="M5 70 39 57 72 62 105 34 137 48 175 18 235 31"></path>
                <circle cx="105" cy="34" r="5"></circle>
                <circle cx="175" cy="18" r="5"></circle>
              </svg>
              <div class="staging-service-update-visual-features">
                <span>5일·10일 전망</span>
                <span>AI 신호 근거</span>
                <span>하루 3번 브리핑</span>
              </div>
            </div>
          </div>
          <button class="staging-service-update-detail" type="button" data-service-update-detail>
            <span>업데이트 자세히 보기</span><span aria-hidden="true">→</span>
          </button>
        </div>
        <footer class="staging-service-update-card-actions">
          <button class="staging-service-update-dismiss" type="button" data-service-update-dismiss aria-label="이번 서비스 업데이트 안내 다시 보지 않기">다시 보지 않기</button>
          <button class="staging-service-update-close" type="button" data-service-update-close>닫기</button>
        </footer>
      </section>
    `;

    serviceUpdatePage = document.createElement("section");
    serviceUpdatePage.id = "staging-service-update-page";
    serviceUpdatePage.className = "staging-service-update-page";
    serviceUpdatePage.hidden = true;
    serviceUpdatePage.setAttribute("aria-labelledby", "staging-service-update-page-title");
    serviceUpdatePage.innerHTML = `
      <header class="staging-service-update-page-nav">
        <button type="button" data-service-update-back aria-label="서비스 업데이트 소개 닫기">${svg(icons.back)}</button>
        <h1>서비스 업데이트</h1>
        <span aria-hidden="true"></span>
      </header>
      <main class="staging-service-update-page-main">
        <header class="staging-service-update-hero">
          <span>${SERVICE_UPDATE_RELEASE.label}</span>
          <h2 id="staging-service-update-page-title">투자 판단까지 가는 길을<br>더 짧고 선명하게</h2>
          <p>필요한 정보가 흩어지지 않도록 홈, 차트, 시그널, 브리핑의 흐름을 새롭게 정리했어요.</p>
        </header>
        <section class="staging-service-update-changes" aria-label="주요 업데이트">
          <article>
            <span class="staging-service-update-index">01</span>
            <div>
              <small>새로운 분석 화면</small>
              <h3>차트 분석 페이지가 추가됐어요</h3>
              <p>최근 가격 흐름과 패턴을 바탕으로 5일·10일 시나리오를 나눠 보고, 예상 범위와 확인할 지점을 함께 살펴볼 수 있어요.</p>
              <button type="button" data-service-update-target="chart">차트 분석 보기</button>
            </div>
          </article>
          <article>
            <span class="staging-service-update-index">02</span>
            <div>
              <small>판단 과정을 투명하게</small>
              <h3>AI 매매 신호를 더 쉽게 읽을 수 있어요</h3>
              <p>매수 대기부터 보유·수익확정·매도까지 현재 단계, 판단 근거, 다음 확인 조건을 같은 순서로 보여줘요.</p>
              <button type="button" data-service-update-target="ai-signals">AI 시그널 보기</button>
            </div>
          </article>
          <article>
            <span class="staging-service-update-index">03</span>
            <div>
              <small>하루 세 번 핵심만</small>
              <h3>돈이 되는 소식이 시간대별로 나뉘었어요</h3>
              <p>아침에 보는 소식, 점심에 보는 소식, 장 마감 후 보는 소식으로 나눠 지금 필요한 시장 정보를 빠르게 확인할 수 있어요.</p>
              <button type="button" data-service-update-target="morning-briefing">돈이 되는 소식 보기</button>
            </div>
          </article>
          <article>
            <span class="staging-service-update-index">04</span>
            <div>
              <small>한눈에 보는 종목 정보</small>
              <h3>종목 상세와 홈의 정보 구조를 다듬었어요</h3>
              <p>가격·등락률·장 상태와 최근 뉴스, 기업 정보의 우선순위를 정리하고 로딩·오류 상태도 더 분명하게 안내해요.</p>
            </div>
          </article>
        </section>
        <footer class="staging-service-update-page-footer">
          <strong>새로워진 비밀노트를 둘러보세요</strong>
          <p>이 안내는 스테이징에서 먼저 제공되며 검증 후 정식 서비스에 반영됩니다.</p>
          <button type="button" data-service-update-home>홈으로 돌아가기</button>
        </footer>
      </main>
    `;
    document.body.append(serviceUpdatePage, serviceUpdateDialog);

    serviceUpdateDialog.querySelector("[data-service-update-close]")?.addEventListener("click", () => {
      closeServiceUpdateDialog({ rememberSession: true });
    });
    serviceUpdateDialog.querySelector("[data-service-update-dismiss]")?.addEventListener("click", () => {
      closeServiceUpdateDialog({ dismissVersion: true, rememberSession: true });
    });
    serviceUpdateDialog.querySelector("[data-service-update-detail]")?.addEventListener("click", () => {
      openServiceUpdatePage();
    });
    serviceUpdateDialog.addEventListener("click", (event) => {
      if (event.target === serviceUpdateDialog) closeServiceUpdateDialog({ rememberSession: true });
    });
    serviceUpdateDialog.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeServiceUpdateDialog({ rememberSession: true });
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = serviceUpdateFocusable(serviceUpdateDialog);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    serviceUpdatePage.querySelector("[data-service-update-back]")?.addEventListener("click", leaveServiceUpdatePage);
    serviceUpdatePage.querySelector("[data-service-update-home]")?.addEventListener("click", leaveServiceUpdatePage);
    for (const button of serviceUpdatePage.querySelectorAll("[data-service-update-target]")) {
      button.addEventListener("click", () => openServiceUpdateTarget(button.dataset.serviceUpdateTarget));
    }
    window.addEventListener("popstate", () => {
      window.requestAnimationFrame(() => {
        if (serviceUpdateRoute() === "service-update") {
          openServiceUpdatePage({ historyMode: "none" });
        } else {
          const wasServiceUpdatePageOpen = Boolean(serviceUpdatePage && !serviceUpdatePage.hidden);
          closeServiceUpdatePage({ restoreFocus: false });
          openServiceUpdateDialogOnFirstEntry();
          if (wasServiceUpdatePageOpen && serviceUpdateRoute() === "home") {
            window.dispatchEvent(new CustomEvent("secret-note:service-update-home-reentry"));
          }
        }
      });
    });

    if (serviceUpdateRoute() === "service-update") {
      openServiceUpdatePage({ historyMode: "none" });
    } else {
      openServiceUpdateDialogOnFirstEntry();
    }
  };

  setupServiceUpdateExperience();

  const syncServiceUpdateExperience = () => {
    if (!serviceUpdateEnabled) return;
    const route = serviceUpdateRoute();
    if (route === "service-update") {
      openServiceUpdatePage({ historyMode: "none" });
      return;
    }
    if (serviceUpdatePage && !serviceUpdatePage.hidden) {
      closeServiceUpdatePage({ restoreFocus: false });
    }
    openServiceUpdateDialogOnFirstEntry();
  };

  const emptyStackIllustration = `
    <svg class="staging-empty-illustration" viewBox="0 0 132 104" aria-hidden="true" focusable="false">
      <path class="staging-empty-shadow" d="M25 84.5c0-7.5 18.4-13.5 41-13.5s41 6 41 13.5S88.6 98 66 98s-41-6-41-13.5Z"></path>
      <path class="staging-empty-sheet staging-empty-sheet-back" d="m35 27 49-13 13 51-49 13z"></path>
      <path class="staging-empty-sheet staging-empty-sheet-middle" d="m26 42 53-8 8 52-53 8z"></path>
      <path class="staging-empty-sheet staging-empty-sheet-front" d="M43 32h56v53H43z"></path>
      <path class="staging-empty-line" d="M55 48h31M55 58h24M55 68h28"></path>
      <circle class="staging-empty-dot" cx="91" cy="76" r="13"></circle>
      <path class="staging-empty-check" d="m85.5 76 4 4 7-8"></path>
    </svg>
  `;

  const primaryRoutes = [
    { view: "home", label: "증권", icon: icons.home },
    { view: "portfolio", label: "관심", icon: icons.interest },
    { view: "search", label: "발견", icon: icons.discover },
    { view: "news", label: "피드", icon: icons.feed },
  ];

  const bindStagingRoute = (button, view) => {
    button.addEventListener("click", () => {
      if (typeof setView === "function") {
        setView(view);
        window.scrollTo({ top: 0, behavior: "auto" });
        return;
      }
      window.history.pushState({}, "", `/dashboard?view=${encodeURIComponent(view)}`);
      window.dispatchEvent(new PopStateEvent("popstate"));
      window.scrollTo({ top: 0, behavior: "auto" });
    });
  };

  bottomNav.replaceChildren();
  for (const item of primaryRoutes) {
    const button = document.createElement("button");
    button.className = "bottom-nav-item";
    button.type = "button";
    button.dataset.appView = item.view;
    button.setAttribute("aria-label", item.label);
    button.innerHTML = `${svg(item.icon)}<span>${item.label}</span>`;
    bindStagingRoute(button, item.view);
    bottomNav.appendChild(button);
  }
  bottomNav.setAttribute("aria-label", "주요 메뉴");

  const bottomNavScrim = document.createElement("div");
  bottomNavScrim.className = "staging-bottom-nav-scrim";
  bottomNavScrim.setAttribute("aria-hidden", "true");
  bottomNav.insertAdjacentElement("beforebegin", bottomNavScrim);

  const routeProxies = document.createElement("div");
  routeProxies.className = "staging-route-proxies";
  routeProxies.hidden = true;
  for (const view of ["ai-signals", "movers", "chart", "morning-briefing"]) {
    const proxy = document.createElement("button");
    proxy.type = "button";
    proxy.dataset.appView = view;
    proxy.dataset.stagingRouteProxy = view;
    proxy.tabIndex = -1;
    bindStagingRoute(proxy, view);
    routeProxies.appendChild(proxy);
  }
  dashboard.appendChild(routeProxies);

  const marketContext = document.createElement("div");
  marketContext.className = "staging-market-context";
  marketContext.innerHTML = `
    <strong data-staging-heading>증권</strong>
    <span class="staging-index-context" data-staging-index-ticker aria-live="off">
      <b data-staging-index-name>시장</b>
      <em data-staging-index-value>확인 중</em>
      <i data-staging-index-change></i>
    </span>
  `;
  topbar.querySelector(".mobile-brand")?.replaceWith(marketContext);

  const topActions = document.createElement("nav");
  topActions.className = "staging-top-actions";
  topActions.setAttribute("aria-label", "빠른 메뉴");
  topActions.innerHTML = `
    <button type="button" data-staging-top-action="notifications" aria-label="알림">${topActionSvg("bell", "staging-notification-bell")}</button>
    <button type="button" data-staging-view="search" aria-label="종목 검색">${topActionSvg("search", "staging-search-glyph")}</button>
  `;
  topbar.insertBefore(topActions, originalTopbarActions);
  originalTopbarActions.hidden = true;
  originalTopbarActions.setAttribute("aria-hidden", "true");

  const primaryTopAction = topActions.querySelector("[data-staging-top-action]");
  const syncPrimaryTopAction = (view = document.body.dataset.view || "home") => {
    if (!primaryTopAction) return;
    const isHome = view === "home";
    const action = isHome ? "notifications" : "ai-signals";
    if (primaryTopAction.dataset.stagingTopAction === action) return;
    primaryTopAction.dataset.stagingTopAction = action;
    primaryTopAction.setAttribute("aria-label", isHome ? "알림" : "AI 시그널");
    if (isHome) {
      primaryTopAction.removeAttribute("data-staging-view");
      primaryTopAction.innerHTML = topActionSvg("bell", "staging-notification-bell");
    } else {
      primaryTopAction.dataset.stagingView = "ai-signals";
      primaryTopAction.innerHTML = topActionSvg("ai", "staging-ai-signal-glyph");
    }
  };
  primaryTopAction?.addEventListener("click", (event) => {
    if (primaryTopAction.dataset.stagingTopAction !== "notifications") return;
    event.preventDefault();
    event.stopPropagation();
    document.getElementById("push-notification-button")?.click();
  });

  const contextualTopbar = document.createElement("nav");
  contextualTopbar.id = "staging-contextual-topbar";
  contextualTopbar.className = "staging-contextual-topbar";
  contextualTopbar.setAttribute("aria-label", "현재 화면 탐색");
  contextualTopbar.hidden = true;
  contextualTopbar.innerHTML = `
    <button class="staging-contextual-back" type="button" data-staging-contextual-back aria-label="이전 화면">
      ${svg(icons.back)}
    </button>
    <div class="staging-contextual-title">
      <h1 data-staging-contextual-title>현재 화면</h1>
      <span data-staging-contextual-subtitle hidden></span>
    </div>
    <button class="staging-contextual-action" type="button" data-staging-contextual-action hidden></button>
    <span class="staging-contextual-spacer" data-staging-contextual-spacer aria-hidden="true"></span>
  `;
  topbar.appendChild(contextualTopbar);

  const shortcutRail = (label = "바로가기") => {
    const rail = document.createElement("nav");
    rail.className = "staging-shortcut-rail";
    rail.setAttribute("aria-label", label);
    rail.innerHTML = `
      <button type="button" data-staging-view="movers"><span class="is-coral">${svg(icons.ranking)}</span><strong>TOP 50</strong></button>
      <button type="button" data-staging-view="ai-signals"><span class="is-ai">${svg(icons.ai)}</span><strong>AI 시그널</strong></button>
      <button type="button" data-staging-view="chart"><span class="is-blue">${svg(icons.chart)}</span><strong>차트 분석</strong></button>
      <button type="button" data-staging-view="morning-briefing"><span class="is-yellow">${svg(icons.briefing)}</span><strong>머니 브리핑</strong></button>
    `;
    return rail;
  };

  let syncHotCommunityQuoteScope = () => {};
  let syncHotCommunityRotation = () => {};
  const STAGING_AI_STOCK_RESPONSE_VIEW = "ai-stock-response";
  const STAGING_AI_STOCK_RESPONSE_STORAGE_PREFIX = "secret-note-staging-ai-response:";
  let stagingHomeResponseSection = null;
  let stagingAiStockResponsePage = null;
  let stagingAiStockResponseTrigger = null;
  let stagingAiStockResponseTriggerCode = "";
  let stagingAiStockResponseRestoreFocusPending = false;
  let stagingAiStockResponseReturnScrollY = 0;
  let stagingAiStockResponseRequestToken = 0;
  let stagingAiStockResponseAbortController = null;
  let stagingAiStockResponseSummaryToken = 0;
  let stagingAiStockResponseRenderedResult = null;
  let stagingAiStockResponseRenderedFailedSources = 0;
  let stagingAiStockResponseSelectedState = "not_holding";
  let stagingAiStockResponseAverageBuyPrice = null;
  let stagingAiStockResponseQuoteScopeSignature = "";
  let stagingAiStockResponseAnalysisBaseline = {
    code: "",
    price: null,
    asOf: null,
  };
  let stagingAiStockResponseReanalysisPending = false;
  let stagingAiStockResponseLiveQuote = {
    code: "",
    price: null,
    changeRate: null,
    state: "idle",
    isLive: false,
    marketSession: "",
    marketSessionLabel: "",
    asOf: null,
  };
  const stagingAiStockResponseCache = new Map();
  const STAGING_AI_STOCK_RESPONSE_CACHE_MS = 2 * 60 * 1000;
  const STAGING_AI_STOCK_RESPONSE_INVESTOR_STATES = Object.freeze({
    not_holding: Object.freeze({
      value: "not_holding",
      label: "미보유",
      note: "현재 보유하지 않은 상태로, 관망 이유와 매수 전환 조건을 설명해요.",
    }),
    holding: Object.freeze({
      value: "holding",
      label: "보유 중",
      note: "평균 매수가와 현재가를 비교해 수익·손실 구간별 대응 기준을 설명해요.",
    }),
  });
  const STAGING_AI_STOCK_RESPONSE_METRICS = Object.freeze([
    { key: "chart", label: "가격 흐름", guide: "가격과 추세가 버티는지 봅니다.", weight: 25 },
    { key: "flow", label: "외국인·기관 매매", guide: "외국인과 기관이 같은 방향으로 사고파는지 봅니다.", weight: 25 },
    { key: "disclosure", label: "회사 공식 공시", guide: "투자 전에 꼭 확인해야 할 공식 위험 공시를 봅니다.", weight: 15 },
    { key: "news", label: "최근 뉴스 분위기", guide: "최근 보도가 긍정과 주의 중 어느 쪽에 가까운지 봅니다.", weight: 10 },
    { key: "research", label: "증권사 리포트", guide: "최근 투자의견과 목표가 변화가 어느 방향인지 봅니다.", weight: 15 },
    { key: "market", label: "금리·환율·업종 환경", guide: "시장 환경이 이 종목에 유리한지 봅니다.", weight: 10 },
  ]);
  const STAGING_AI_STOCK_RESPONSE_METRIC_BY_KEY = new Map(
    STAGING_AI_STOCK_RESPONSE_METRICS.map((metric) => [metric.key, metric]),
  );
  const STAGING_AI_STOCK_RESPONSE_STANCE_COPY = Object.freeze({
    "신규 접근 보류": {
      badge: "중대 공시 먼저 확인",
      headline: "새로 살지 정하기 전에 중요한 공시부터 확인할 때예요",
    },
    "매도 신호 우선": {
      badge: "팔아야 할 조건 확인",
      headline: "이미 보유 중이라면 팔아야 할 조건이 가까워졌는지 볼 때예요",
    },
    "수익 관리 우선": {
      badge: "수익을 지킬 기준 확인",
      headline: "오른 가격이 다시 내려갈 때를 대비할 기준부터 볼 때예요",
    },
    "재진입 유예": {
      badge: "다시 살 조건 대기",
      headline: "지금은 다시 살 때가 아니라 조건이 갖춰지는지 기다릴 때예요",
    },
    "정보 확인 우선": {
      badge: "자료가 더 필요해요",
      headline: "자료가 더 모일 때까지 판단을 미뤄 주세요",
    },
    "혼조 · 확인 우선": {
      badge: "신호가 엇갈려요",
      headline: "좋은 신호와 주의 신호가 함께 있어요",
    },
    "보수 관찰": {
      badge: "주의 쪽으로 엇갈려요",
      headline: "주의 신호가 조금 더 강하지만 한 번 더 확인이 필요해요",
    },
    "분할 접근 검토": {
      badge: "긍정 신호 우세",
      headline: "좋은 신호가 더 많지만 가격이 안정적인지 한 번 더 볼 때예요",
    },
    "긍정 관찰": {
      badge: "조금 긍정적이에요",
      headline: "흐름은 긍정적이지만 한 번 더 확인이 필요해요",
    },
    "위험 관리 우선": {
      badge: "주의 신호 우세",
      headline: "새로 판단하기보다 위험 요인을 먼저 확인해 주세요",
    },
    "보수 대응": {
      badge: "조금 주의가 필요해요",
      headline: "반등만 보고 판단하기에는 아직 조심스러워요",
    },
    "조건 확인 중": {
      badge: "새로 살 조건 확인 중",
      headline: "새로 살 수 있는 조건이 모두 갖춰지는지 더 볼 때예요",
    },
    "진입 조건 확인": {
      badge: "다음 조건 확인",
      headline: "다음 거래일에도 같은 흐름이 이어지는지 확인할 때예요",
    },
    "수익확정 후 보유 관리": {
      badge: "남은 보유분 확인",
      headline: "일부 수익을 확보했고 남은 보유분을 계속 지켜볼 때예요",
    },
    "보유 관리": {
      badge: "계속 보유할 기준 확인",
      headline: "이미 보유 중이라면 계속 들고 갈지 판단할 기준을 볼 때예요",
    },
    "중립 관찰": {
      badge: "뚜렷한 방향이 없어요",
      headline: "아직 한쪽으로 모인 신호가 없어요",
    },
  });

  const normalizeStagingAiStockResponseInvestorState = (value = "") => {
    const normalized = String(value || "").trim();
    return normalized === "holding" ? "holding" : "not_holding";
  };

  const normalizeStagingAiStockResponseAverageBuyPrice = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const normalized = Number(String(value).replaceAll(",", ""));
    return Number.isFinite(normalized) && normalized > 0 ? normalized : null;
  };

  const stagingAiStockResponseInvestorStateForCode = (code = "") => {
    const investorStateApi = window.SecretNoteWatchlistInvestorState;
    if (typeof investorStateApi?.read === "function") {
      return normalizeStagingAiStockResponseInvestorState(investorStateApi.read(code));
    }
    try {
      const items = JSON.parse(window.localStorage.getItem("analyst.watchlist") || "[]");
      const item = Array.isArray(items)
        ? items.find((candidate) => String(candidate?.code || "") === String(code || ""))
        : null;
      return normalizeStagingAiStockResponseInvestorState(item?.investor_state);
    } catch {
      return "not_holding";
    }
  };

  const stagingAiStockResponseAverageBuyPriceForCode = (code = "") => {
    const investorStateApi = window.SecretNoteWatchlistInvestorState;
    if (typeof investorStateApi?.readAverageBuyPrice === "function") {
      return normalizeStagingAiStockResponseAverageBuyPrice(
        investorStateApi.readAverageBuyPrice(code),
      );
    }
    try {
      const items = JSON.parse(window.localStorage.getItem("analyst.watchlist") || "[]");
      const item = Array.isArray(items)
        ? items.find((candidate) => String(candidate?.code || "") === String(code || ""))
        : null;
      return normalizeStagingAiStockResponseAverageBuyPrice(item?.average_buy_price);
    } catch {
      return null;
    }
  };

  const syncStagingAiStockResponseInvestorState = (
    investorState = "not_holding",
    averageBuyPrice = undefined,
  ) => {
    if (!stagingAiStockResponsePage) return;
    const normalized = normalizeStagingAiStockResponseInvestorState(investorState);
    stagingAiStockResponseSelectedState = normalized;
    stagingAiStockResponseAverageBuyPrice = normalized === "holding"
      ? normalizeStagingAiStockResponseAverageBuyPrice(
        averageBuyPrice === undefined
          ? stagingAiStockResponseAverageBuyPriceForCode(
            stagingAiStockResponsePage.dataset.responseCode || "",
          )
          : averageBuyPrice,
      )
      : null;
    stagingAiStockResponsePage.dataset.investorState = normalized;
    for (const button of stagingAiStockResponsePage.querySelectorAll("[data-staging-response-investor-state]")) {
      const selected = button.getAttribute("data-staging-response-investor-state") === normalized;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    }
    const copy = STAGING_AI_STOCK_RESPONSE_INVESTOR_STATES[normalized];
    stagingAiStockResponseText("[data-staging-response-investor-note]", copy.note);
    const priceField = stagingAiStockResponsePage.querySelector(
      "[data-staging-response-average-price-field]",
    );
    if (priceField instanceof HTMLElement) priceField.hidden = normalized !== "holding";
    const priceInput = stagingAiStockResponsePage.querySelector(
      "[data-staging-response-average-price]",
    );
    if (priceInput instanceof HTMLInputElement) {
      priceInput.value = stagingAiStockResponseAverageBuyPrice
        ? formatNumber(stagingAiStockResponseAverageBuyPrice)
        : "";
    }
  };

  const setStagingAiStockResponseDisplay = (mode = "loading", message = "") => {
    if (!stagingAiStockResponsePage) return;
    const ready = mode === "ready";
    stagingAiStockResponsePage.dataset.responseDisplay = ready ? "ready" : "loading";
    stagingAiStockResponsePage.dataset.responseLoaded = String(ready);
    stagingAiStockResponsePage.setAttribute("aria-busy", String(!ready));
    const loader = stagingAiStockResponsePage.querySelector("[data-staging-response-loader]");
    if (loader instanceof HTMLElement) loader.hidden = ready;
    if (message) stagingAiStockResponseText("[data-staging-response-loader-message]", message);
  };

  const stagingAiStockResponseRouteActive = () => (
    new URLSearchParams(window.location.search).get("view") === STAGING_AI_STOCK_RESPONSE_VIEW
  );

  const stagingAiStockResponseCodeFromHref = (href = "") => {
    try {
      const parts = new URL(href, window.location.href).pathname.split("/").filter(Boolean);
      return decodeURIComponent(parts.at(-1) || "").trim();
    } catch {
      return "";
    }
  };

  const stagingAiStockResponseDetailFromRow = (row) => {
    if (!(row instanceof HTMLAnchorElement)) return null;
    const name = row.querySelector(".home-ai-interest-head strong")?.textContent?.trim() || "관심종목";
    const status = row.querySelector(".home-ai-interest-head em")?.textContent?.trim() || "관심종목 연관";
    const action = row.querySelector(".home-ai-interest-action")?.textContent?.trim() || "대응 내용을 확인하고 있습니다.";
    const basis = row.querySelector(".home-ai-interest-basis")?.textContent?.replace(/\s+/g, " ")?.trim() || "";
    const basisParts = basis.split(" · ").map((item) => item.trim()).filter(Boolean);
    const tone = ["negative", "positive", "event", "neutral"].find(
      (candidate) => row.classList.contains(`is-${candidate}`),
    ) || "neutral";
    return {
      code: stagingAiStockResponseCodeFromHref(row.href),
      name,
      status,
      action,
      issue: basisParts[0] || "최근 시장 이벤트와의 연결을 확인하고 있습니다.",
      relation: basisParts[1] || "관심종목 연관",
      signal: basisParts.slice(2).join(" · "),
      basis,
      updatedAt: document.getElementById("home-ai-response-asof")?.textContent?.trim() || "업데이트 확인 중",
      tone,
    };
  };

  const storeStagingAiStockResponseDetail = (detail) => {
    if (!detail?.code) return;
    try {
      window.sessionStorage.setItem(
        `${STAGING_AI_STOCK_RESPONSE_STORAGE_PREFIX}${detail.code}`,
        JSON.stringify(detail),
      );
    } catch {
      // Private browsing can disable storage; the current in-memory page still works.
    }
  };

  const readStagingAiStockResponseDetail = (code = "") => {
    if (!code) return null;
    try {
      const parsed = JSON.parse(window.sessionStorage.getItem(
        `${STAGING_AI_STOCK_RESPONSE_STORAGE_PREFIX}${code}`,
      ) || "null");
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch {
      return null;
    }
  };

  const stagingAiStockResponseText = (selector, value) => {
    const node = stagingAiStockResponsePage?.querySelector(selector);
    if (node) node.textContent = String(value ?? "");
  };

  const stagingAiStockResponseAsOf = (value) => {
    if (!value) return "업데이트 확인 중";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return `기준 ${String(value).slice(0, 16)}`;
    return `기준 ${new Intl.DateTimeFormat("ko-KR", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(parsed)}`;
  };

  const stagingAiStockResponseSetTime = (selector, value, { prefix = "" } = {}) => {
    const node = stagingAiStockResponsePage?.querySelector(selector);
    if (!(node instanceof HTMLTimeElement)) return;
    const parsed = new Date(value);
    const display = Number.isNaN(parsed.getTime())
      ? String(value || "업데이트 확인 중").replace(/^업데이트\s*/, "")
      : stagingAiStockResponseAsOf(value).replace(/^기준\s*/, "");
    node.textContent = `${prefix}${prefix && display ? " " : ""}${display}`;
    if (Number.isNaN(parsed.getTime())) node.removeAttribute("datetime");
    else node.dateTime = parsed.toISOString();
  };

  const stagingAiStockResponseMetricCopy = (metric = {}) => (
    STAGING_AI_STOCK_RESPONSE_METRIC_BY_KEY.get(metric.key)
    || { key: metric.key || "unknown", label: metric.label || "확인 자료", guide: "연결된 자료를 확인합니다.", weight: metric.weight || 0 }
  );

  const stagingAiStockResponseMetricStatus = (status = "") => ({
    우호: "긍정",
    주의: "주의",
    중립: "뚜렷한 방향 없음",
    "위험 감지": "중대 위험 감지",
    "확인 중": "자료 확인 중",
  }[status] || status || "자료 확인 중");

  const stagingAiStockResponseMetricValue = (metric = {}) => {
    if (metric.key === "disclosure" && metric.value === "차단 없음") return "중대 위험 미감지";
    return metric.value || "자료 확인 중";
  };

  const stagingAiStockResponseReplaceMetricLabels = (value = "") => {
    let text = String(value || "");
    for (const [before, after] of [
      ["차트 점수", "가격 흐름"],
      ["시장 영향", "금리·환율·업종 환경"],
      ["수급", "외국인·기관 매매"],
      ["공시", "회사 공식 공시"],
      ["뉴스", "최근 뉴스"],
    ]) text = text.replaceAll(before, after);
    return text;
  };

  const stagingAiStockResponseContext = (detail = {}) => {
    const issue = String(detail.issue || "최근 시장 이벤트와의 연결을 확인했어요.").trim();
    const relation = String(detail.relation || "관심종목 연관").trim();
    const issueSentence = /[.!?。]$/.test(issue) ? issue : `${issue}.`;
    return `${issueSentence} ${relation}으로 분류해 함께 확인했어요.`;
  };

  const stagingAiStockResponseStanceCopy = (stance = "") => (
    STAGING_AI_STOCK_RESPONSE_STANCE_COPY[stance]
    || STAGING_AI_STOCK_RESPONSE_STANCE_COPY["중립 관찰"]
  );

  const stagingAiStockResponseDirectionCopy = (result = {}) => {
    if (result.hardRisk) return {
      value: "공시부터 확인해요",
      guide: "중대 공시가 다른 신호보다 우선해요",
    };
    if (result.limited) return {
      value: "자료를 더 기다려요",
      guide: "아직 확인되지 않은 자료가 있어요",
    };
    if (result.conflict) return {
      value: "신호가 엇갈려요",
      guide: "좋은 신호와 주의 신호가 함께 있어요",
    };
    const score = Number(result.score);
    if (!Number.isFinite(score)) return {
      value: "계산 중이에요",
      guide: "긍정·주의 신호를 비교하고 있어요",
    };
    if (score >= 35) return {
      value: "좋은 신호가 많아요",
      guide: "긍정 신호가 주의 신호보다 많아요",
    };
    if (score >= 10) return {
      value: "조금 긍정적이에요",
      guide: "긍정 신호가 주의 신호보다 조금 많아요",
    };
    if (score <= -35) return {
      value: "주의 깊게 봐야 해요",
      guide: "주의 신호가 긍정 신호보다 많아요",
    };
    if (score <= -10) return {
      value: "조금 더 지켜봐요",
      guide: "주의 신호가 긍정 신호보다 조금 많아요",
    };
    return {
      value: "신호가 비슷해요",
      guide: "긍정 신호와 주의 신호가 비슷해요",
    };
  };

  const stagingAiStockResponsePerspectiveCopy = (
    result = {},
    investorState = stagingAiStockResponseSelectedState,
  ) => {
    const stateKey = normalizeStagingAiStockResponseInvestorState(investorState);
    const deterministicGuide = window.SecretNoteAiStockResponse?.buildInvestorGuide?.(
      result,
      {
        investorState: stateKey,
        averageBuyPrice: stagingAiStockResponseAverageBuyPrice,
      },
    );
    if (deterministicGuide && typeof deterministicGuide === "object") {
      return {
        ...deterministicGuide,
        guide: deterministicGuide.directionGuide,
      };
    }
    const score = Number(result.score);
    const hardRisk = Boolean(result.hardRisk);
    const limited = Boolean(result.limited) || !Number.isFinite(score);
    const conflict = Boolean(result.conflict);
    const stronglyPositive = !hardRisk && !limited && !conflict && score >= 35;
    const positive = !hardRisk && !limited && !conflict && score >= 10;
    const stronglyNegative = hardRisk || (!limited && score <= -35);
    if (stateKey === "holding") {
      if (hardRisk) return {
        headline: "보유 중이라면 중요한 공시와 매도 기준부터 확인할 때예요",
        summary: "보유 수량을 늘리기보다 현재 위험이 보유 기준을 바꾸는지 먼저 보세요.",
        direction: "매도 기준 확인",
        guide: "중대 공시가 다른 신호보다 우선해요",
      };
      if (limited) return {
        headline: "보유 기준을 바꾸기 전에 자료가 더 필요한 때예요",
        summary: "지금은 추가 매수보다 부족한 자료를 확인해 보유 기준을 먼저 점검해요.",
        direction: "보유 기준 확인",
        guide: "아직 확인되지 않은 자료가 있어요",
      };
      if (stronglyNegative) return {
        headline: "보유 수량을 늘리기보다 위험 기준부터 확인할 때예요",
        summary: "주의 신호가 많아 계속 보유할지와 보유량을 줄일 기준을 함께 봐야 해요.",
        direction: "위험 기준 확인",
        guide: "주의 신호가 긍정 신호보다 많아요",
      };
      if (conflict) return {
        headline: "계속 보유할 기준과 줄일 기준을 함께 볼 때예요",
        summary: "좋은 신호와 주의 신호가 섞여 있어 추가 매수는 서두르지 않는 구간이에요.",
        direction: "보유 기준 확인",
        guide: "좋은 신호와 주의 신호가 함께 있어요",
      };
      if (stronglyPositive) return {
        headline: "보유 기준은 유지하되 더 살 조건은 따로 확인할 때예요",
        summary: "긍정 신호가 많아도 현재가와 추가 매수 기준이 같이 맞는지 확인해야 해요.",
        direction: "추가 매수 조건 확인",
        guide: "보유 신호와 추가 매수 조건은 따로 보아요",
      };
      if (positive) return {
        headline: "보유 기준을 확인하고 추가 매수는 서두르지 않을 때예요",
        summary: "긍정 신호가 조금 많지만 더 살 조건까지 모두 갖춰졌다고 보기는 어려워요.",
        direction: "보유 기준 확인",
        guide: "추가 매수 전에 가격 조건을 더 보세요",
      };
      return {
        headline: "보유 수량을 늘리기보다 현재 기준을 점검할 때예요",
        summary: "보유을 유지할지와 위험 가격이 가까워지는지를 먼저 확인해요.",
        direction: "보유 기준 확인",
        guide: "추가 매수보다 보유·위험 기준이 우선이에요",
      };
    }
    if (hardRisk) return {
      headline: "새로 살지 정하기 전에 중요한 공시부터 확인할 때예요",
      summary: "아직 보유하지 않은 상태이므로 중대 위험이 풀리기 전에는 신규 매수 판단을 미루는 구간이에요.",
      direction: "신규 매수 대기",
      guide: "중대 공시가 다른 신호보다 우선해요",
    };
    if (limited || conflict || stronglyNegative) return {
      headline: "지금은 새로 살 때가 아니라 조건을 기다릴 때예요",
      summary: "신규 매수 관점에서는 부족하거나 엇갈린 신호가 줄어드는지 먼저 확인해요.",
      direction: "신규 매수 대기",
      guide: limited ? "아직 확인되지 않은 자료가 있어요" : "새로 살 만큼 신호가 모이지 않았어요",
    };
    if (stronglyPositive) return {
      headline: "신규 매수를 검토할 수 있지만 가격 조건부터 확인할 때예요",
      summary: "긍정 신호가 많아도 실제로 새로 살 가격과 신호가 함께 맞는지 확인해야 해요.",
      direction: "새 매수 조건 확인",
      guide: "신규 매수 가격과 신호가 함께 맞는지 보세요",
    };
    return {
      headline: "새로 살 조건이 더 갖춰지는지 확인할 때예요",
      summary: "긍정 신호가 조금 많지만 신규 매수를 정하기 전에 다음 가격 조건을 확인해요.",
      direction: "새 매수 조건 확인",
      guide: "긍정 신호가 계속되는지 한 번 더 보세요",
    };
  };

  const stagingAiStockResponseDataState = (confidence = 0, limited = false) => {
    if (limited || Number(confidence) < 55) return "부족";
    if (Number(confidence) >= 75) return "충분";
    return "보통";
  };

  const stagingAiStockResponseCoverage = (count = 0) => {
    if (Number(count) >= 6) return "6개 모두";
    if (Number(count) > 0) return `${Number(count)}개 확인`;
    return "확인된 자료 없음";
  };

  const stagingAiStockResponseReason = (result = {}) => {
    const metrics = Array.isArray(result.metrics) ? result.metrics : [];
    if (result.hardRisk) return "중대 위험 공시가 감지되어 다른 신호보다 먼저 원문을 확인해야 해요.";
    if (result.limited) return "아직 확인되지 않은 자료가 있어 한쪽 방향으로 결론 내리기 어려워요.";
    const positive = metrics.find((metric) => metric.available && Number(metric.score) >= 25);
    const negative = metrics.find((metric) => metric.available && Number(metric.score) <= -25);
    if (positive && negative) {
      return `${stagingAiStockResponseMetricCopy(positive).label}에서는 긍정 신호가, ${stagingAiStockResponseMetricCopy(negative).label}에서는 주의 신호가 나왔어요.`;
    }
    if (negative) return `${stagingAiStockResponseMetricCopy(negative).label}의 주의 신호가 현재 판단에 가장 크게 반영됐어요.`;
    if (positive) return `${stagingAiStockResponseMetricCopy(positive).label}의 긍정 신호가 현재 판단에 가장 크게 반영됐어요.`;
    return "강한 방향 신호가 아직 모이지 않아 다음 변화를 확인하고 있어요.";
  };

  const stagingAiStockResponseFriendlyAction = (value = "") => {
    let text = String(value || "").trim();
    for (const [before, after] of [
      ["현재 포지션", "현재 보유 상태"],
      ["포지션", "보유 상태"],
      ["신규 진입", "새로 사는 것"],
      ["재진입", "다시 사는 것"],
      ["진입 조건", "새로 살 조건"],
      ["매매 시그널", "AI 판단"],
      ["시그널", "AI 판단"],
      ["신규 접근을 서두르지 말고", "새로운 결정을 서두르지 말고"],
      ["신규 접근을 보류하세요", "새로운 결정을 미뤄 주세요"],
      ["신규 접근", "새로운 판단"],
      ["비중 확대보다", "보유 수량을 늘리기보다"],
      ["비중 확대", "보유 수량 늘리기"],
      ["외국인·기관 수급이", "외국인·기관 매매가"],
      ["외국인·기관 수급", "외국인·기관 매매"],
      ["수급이", "외국인·기관 매매가"],
      ["수급의", "외국인·기관 매매의"],
      ["수급을", "외국인·기관 매매를"],
      ["수급", "외국인·기관 매매"],
      ["추격보다", "가격을 따라 서두르기보다"],
      ["추격하지", "가격을 따라 서두르지"],
      ["추격", "가격을 따라 서두르기"],
    ]) text = text.replaceAll(before, after);
    if (/확인$/.test(text)) text = `${text}해 주세요.`;
    return text;
  };

  const stagingAiStockResponseFriendlyWarning = (value = "") => {
    let text = stagingAiStockResponseReplaceMetricLabels(value);
    text = text.replace(/^신호 충돌:\s*/, "긍정 신호와 주의 신호가 함께 있어요: ");
    text = text.replace(/^미확인 지표:\s*/, "아직 확인하지 못한 자료: ");
    text = text.replace(
      "금리·환율·업종 환경은 종목 직접 연결이 아닌 광역 시장 영향으로 반영",
      "시장 환경은 이 종목에 직접 연결된 정보가 아니라 전체 시장 흐름을 반영했어요.",
    );
    text = text.replace(/^일부 원천 응답 지연:\s*/, "일부 자료가 늦게 도착하고 있어요: ");
    return text;
  };

  const stagingAiStockResponseFriendlyNextCheck = (value = "") => {
    let text = String(value || "").trim();
    text = text.replace(/^현재 시그널:\s*/, "현재 AI 판단: ");
    text = text.replace(/^공시 원문과 거래 상태를 먼저 확인$/, "중대 공시 원문과 거래 가능 상태를 확인하기");
    text = text.replace(/^차트 지지 ([\d,]+)원 유지 여부$/, "주가가 $1원 아래로 내려가지 않는지");
    text = text.replace(/^차트 종가와 20일선 방향 재확인$/, "장이 끝날 때 가격이 최근 20일 평균보다 위에 있는지");
    text = text.replace(/^외국인·기관 합산 순매수 전환 확인$/, "외국인과 기관이 판 금액보다 산 금액이 많아지는지");
    text = text.replace(/^수급 우호 흐름의 연속성 확인$/, "외국인과 기관이 계속 사는지");
    text = text.replace(/^부정 뉴스의 실적·사업 영향 범위 확인$/, "부정 뉴스가 실적과 사업에 실제로 영향을 주는지");
    text = text.replace(/^관련 시장 위험축의 방향 전환 확인$/, "금리·환율·업종의 주의 요인이 줄어드는지");
    for (const [before, after] of [
      ["손실 제한선", "손실을 줄일 가격"],
      ["지지선", "가격이 버텨야 하는 기준"],
      ["저항선", "가격이 넘어서야 하는 기준"],
      ["종가", "장이 끝날 때 가격"],
      ["시그널", "AI 판단"],
      ["수급", "외국인과 기관의 매매"],
      ["진입", "새로 사는 것"],
      ["포지션", "보유 상태"],
    ]) text = text.replaceAll(before, after);
    return text;
  };

  const stagingAiStockResponseInvestorNextCheck = (
    result = {},
    investorState = stagingAiStockResponseSelectedState,
  ) => {
    const stateKey = normalizeStagingAiStockResponseInvestorState(investorState);
    const perspective = stagingAiStockResponsePerspectiveCopy(result, stateKey);
    if (Array.isArray(perspective.nextChecks) && perspective.nextChecks[0]) {
      return stagingAiStockResponseFriendlyNextCheck(perspective.nextChecks[0]);
    }
    const score = Number(result.score);
    if (result.hardRisk) return "중대 공시 원문과 거래 가능 상태를 먼저 확인하기";
    if (stateKey === "holding") {
      if (Number.isFinite(score) && score >= 35 && !result.conflict && !result.limited) {
        return "추가 매수 전에 가격 조건과 긍정 신호가 함께 유지되는지";
      }
      return "보유 기준과 손실을 줄일 가격이 유지되는지";
    }
    return "신규 매수 전에 가격 조건과 긍정 신호가 함께 갖춰지는지";
  };

  const stagingAiStockResponseSummaryInput = (
    result = {},
    investorState = stagingAiStockResponseSelectedState,
  ) => {
    const normalizedState = normalizeStagingAiStockResponseInvestorState(investorState);
    const stateCopy = STAGING_AI_STOCK_RESPONSE_INVESTOR_STATES[normalizedState];
    const perspective = stagingAiStockResponsePerspectiveCopy(result, normalizedState);
    const sources = (Array.isArray(result.metrics) ? result.metrics : []).map((metric) => ({
      id: `metric-${metric.key || "unknown"}`,
      key: metric.key,
      label: stagingAiStockResponseMetricCopy(metric).label,
      status: stagingAiStockResponseMetricStatus(metric.status),
      value: stagingAiStockResponseMetricValue(metric),
      evidence: metric.evidence,
      available: metric.available !== false,
      weight: metric.weight,
      score: metric.score,
    }));
    const perspectiveNextChecks = (Array.isArray(perspective.nextChecks) ? perspective.nextChecks : [])
      .map((item) => stagingAiStockResponseFriendlyNextCheck(item));
    const nextChecks = [
      stagingAiStockResponseInvestorNextCheck(result, normalizedState),
      ...perspectiveNextChecks,
      ...(perspectiveNextChecks.length === 0 && Array.isArray(result.nextChecks)
        ? result.nextChecks.map((item) => stagingAiStockResponseFriendlyNextCheck(item))
        : []),
    ].filter((item, index, items) => item && items.indexOf(item) === index);
    const fallback = {
      headline: perspective.headline,
      summary: perspective.summary,
      reason: perspective.reason || stagingAiStockResponseReason(result),
      action_title: perspective.headline,
      next_check: nextChecks[0] || "현재 상태를 바꿀 다음 자료를 확인하고 있어요.",
      evidence_refs: sources.slice(0, 3).map((source) => source.id),
    };
    return {
      facts: {
        code: result.code,
        name: result.name,
        stance: result.stance,
        tone: result.tone,
        action: result.action,
        investor_state: normalizedState,
        investor_state_label: stateCopy.label,
        investor_state_note: stateCopy.note,
        position_mode: perspective.positionMode,
        average_buy_price: perspective.averageBuyPrice,
        personal_return_rate: perspective.returnRate,
        current_price: perspective.currentPrice,
        guide_rows: (perspective.rows || []).slice(0, 3),
        decision_plan: (perspective.decisionPlan || []).slice(0, 3),
        hard_risk: Boolean(result.hardRisk),
        conflict: Boolean(result.conflict),
        limited: Boolean(result.limited),
        coverage_count: result.coverageCount,
        as_of: result.asOf,
        metrics: sources,
        warnings: (result.warnings || []).slice(0, 5),
        next_checks: nextChecks.slice(0, 5),
        sources,
      },
      fallback,
    };
  };

  const finishStagingAiStockResponseSummary = ({
    requestedCode,
    requestedState,
    summaryToken,
    mode = "rules",
  }) => {
    if (
      !stagingAiStockResponsePage
      || stagingAiStockResponsePage.dataset.responseCode !== requestedCode
      || stagingAiStockResponseSelectedState !== requestedState
      || summaryToken !== stagingAiStockResponseSummaryToken
    ) return;
    stagingAiStockResponsePage.dataset.summaryMode = mode;
    stagingAiStockResponseReanalysisPending = false;
    setStagingAiStockResponseDisplay("ready");
    renderStagingAiStockResponseAnalysisStatus();
    const perspective = stagingAiStockResponsePerspectiveCopy(
      stagingAiStockResponseRenderedResult || {},
      requestedState,
    );
    stagingAiStockResponseText(
      "[data-staging-response-announcement]",
      `${stagingAiStockResponseRenderedResult?.name || "종목"} 설명이 ${STAGING_AI_STOCK_RESPONSE_INVESTOR_STATES[requestedState].label} 기준으로 준비됐습니다. ${perspective.headline}`,
    );
  };

  const applyStagingAiStockResponseSummary = async (
    result = {},
    investorState = stagingAiStockResponseSelectedState,
  ) => {
    if (!stagingGptPageSummaryEnabled || !stagingAiStockResponsePage || !result.code) return;
    const requestedCode = String(result.code);
    const requestedState = normalizeStagingAiStockResponseInvestorState(investorState);
    const summaryToken = ++stagingAiStockResponseSummaryToken;
    const { facts, fallback } = stagingAiStockResponseSummaryInput(result, requestedState);
    if (facts.position_mode === "holding_unknown") {
      stagingAiStockResponseText("[data-staging-response-action]", fallback.headline);
      stagingAiStockResponseText("[data-staging-response-summary]", fallback.summary);
      stagingAiStockResponseText("[data-staging-response-reason]", fallback.reason);
      finishStagingAiStockResponseSummary({
        requestedCode,
        requestedState,
        summaryToken,
        mode: "rules",
      });
      return;
    }
    stagingAiStockResponsePage.dataset.summaryMode = "loading";
    setStagingAiStockResponseDisplay("loading", `내 상황을 ${STAGING_AI_STOCK_RESPONSE_INVESTOR_STATES[requestedState].label} 기준으로 반영해 쉬운 말로 정리하고 있어요.`);
    renderStagingAiStockResponseAnalysisStatus();
    try {
      const summary = await requestStagingPageSummary("stock_response", facts, fallback);
      if (
        stagingAiStockResponsePage.dataset.responseCode !== requestedCode
        || stagingAiStockResponseSelectedState !== requestedState
        || summaryToken !== stagingAiStockResponseSummaryToken
      ) return;
      if (typeof summary?.headline !== "string") {
        finishStagingAiStockResponseSummary({
          requestedCode,
          requestedState,
          summaryToken,
          mode: "rules",
        });
        return;
      }
      stagingAiStockResponseText("[data-staging-response-action]", summary.headline);
      stagingAiStockResponseText("[data-staging-response-summary]", summary.summary);
      stagingAiStockResponseText("[data-staging-response-reason]", summary.reason);
      finishStagingAiStockResponseSummary({
        requestedCode,
        requestedState,
        summaryToken,
        mode: summary.generation_mode || "rules",
      });
    } catch {
      finishStagingAiStockResponseSummary({
        requestedCode,
        requestedState,
        summaryToken,
        mode: "rules",
      });
    }
  };

  const stagingAiStockResponseKeyReasonRow = (metric, { loading = false } = {}) => {
    const copy = stagingAiStockResponseMetricCopy(metric);
    const row = document.createElement("article");
    row.className = "staging-ai-stock-response-key-reason";
    row.dataset.metricTone = loading ? "loading" : metric.tone || "neutral";
    const head = document.createElement("header");
    const label = document.createElement("h4");
    label.textContent = copy.label;
    const status = document.createElement("span");
    status.textContent = loading ? "확인 중" : stagingAiStockResponseMetricStatus(metric.status);
    head.append(label, status);
    const evidence = document.createElement("p");
    evidence.textContent = loading
      ? `${copy.label} 자료를 확인하고 있어요.`
      : metric.evidence || `${copy.label} 자료를 아직 확인하지 못했어요.`;
    row.append(head, evidence);
    return row;
  };

  const stagingAiStockResponseMetricRow = (metric, { loading = false } = {}) => {
    const copy = stagingAiStockResponseMetricCopy(metric);
    const row = document.createElement("article");
    row.className = "staging-ai-stock-response-metric";
    row.dataset.metricKey = metric.key || "loading";
    row.dataset.metricTone = loading ? "loading" : metric.tone || "neutral";
    row.dataset.metricAvailable = String(!loading && metric.available !== false);

    const head = document.createElement("header");
    const identity = document.createElement("div");
    const label = document.createElement("h4");
    label.textContent = copy.label;
    const badge = document.createElement("span");
    badge.className = "staging-ai-stock-response-metric-status";
    badge.textContent = loading ? "확인 중" : stagingAiStockResponseMetricStatus(metric.status);
    identity.append(label, badge);
    const value = document.createElement("strong");
    value.className = "staging-ai-stock-response-metric-value";
    value.textContent = loading ? "--" : stagingAiStockResponseMetricValue(metric);
    head.append(identity, value);

    const guide = document.createElement("p");
    guide.className = "staging-ai-stock-response-metric-guide";
    guide.textContent = copy.guide;
    const evidence = document.createElement("p");
    evidence.className = "staging-ai-stock-response-metric-evidence";
    evidence.textContent = loading
      ? `${copy.label} 데이터를 연결하고 있습니다.`
      : metric.evidence || "연결된 근거를 확인하고 있습니다.";
    const meta = document.createElement("footer");
    const source = document.createElement("span");
    source.className = "staging-ai-stock-response-metric-source";
    source.textContent = loading ? "자료 확인 중" : metric.source || "자료 확인 중";
    const asOf = document.createElement("time");
    asOf.textContent = loading ? "" : `자료 시각 ${stagingAiStockResponseAsOf(metric.asOf).replace(/^기준 /, "")}`;
    const parsedAsOf = metric.asOf ? new Date(metric.asOf) : null;
    if (!loading && parsedAsOf && !Number.isNaN(parsedAsOf.getTime())) asOf.dateTime = parsedAsOf.toISOString();
    const weight = document.createElement("span");
    weight.textContent = `판단 반영 ${metric.weight || copy.weight || 0}%`;
    meta.append(source, asOf, weight);
    row.append(head, guide, evidence, meta);
    return row;
  };

  const stagingAiStockResponseGuideRow = (item = {}) => {
    const row = document.createElement("article");
    row.className = "staging-ai-stock-response-guide-row";
    row.dataset.guideKey = item.key || "guide";
    row.dataset.guideTone = item.tone || "neutral";
    const head = document.createElement("div");
    head.className = "staging-ai-stock-response-guide-row-head";
    const identity = document.createElement("div");
    const label = document.createElement("h4");
    label.textContent = item.label || "확인 기준";
    const status = document.createElement("span");
    status.textContent = item.status || "확인";
    identity.append(label, status);
    const value = document.createElement("strong");
    value.textContent = item.value || "자료 부족";
    head.append(identity, value);
    const evidence = document.createElement("p");
    evidence.textContent = item.evidence || "연결된 가격 자료를 확인하고 있어요.";
    row.append(head, evidence);
    return row;
  };

  const stagingAiStockResponseDecisionStepRow = (item = {}) => {
    const row = document.createElement("li");
    row.className = "staging-ai-stock-response-decision-step";
    row.dataset.decisionKey = item.key || "check";
    row.dataset.decisionTone = item.tone || "neutral";
    const head = document.createElement("div");
    head.className = "staging-ai-stock-response-decision-step-head";
    const label = document.createElement("span");
    label.textContent = item.label || "다음에 볼 때";
    const status = document.createElement("em");
    status.textContent = item.status || "조건 확인";
    head.append(label, status);
    const value = document.createElement("strong");
    value.textContent = item.value || "가격 자료 부족";
    const evidence = document.createElement("p");
    evidence.textContent = item.evidence || "가격과 외국인·기관 매매가 함께 달라지는지 확인해요.";
    row.append(head, value, evidence);
    return row;
  };

  const stagingAiStockResponseFinitePrice = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  };

  const renderStagingAiStockResponseHoldingStrategy = (perspective = {}) => {
    const section = stagingAiStockResponsePage?.querySelector(
      "[data-staging-response-holding-strategy]",
    );
    if (!(section instanceof HTMLElement)) return;
    const strategy = perspective?.holdingStrategy;
    const visible = stagingAiStockResponseSelectedState === "holding"
      && strategy
      && typeof strategy === "object";
    section.hidden = !visible;
    if (!visible) {
      delete section.dataset.strategyMode;
      return;
    }
    section.dataset.strategyMode = perspective.positionMode || "holding";
    stagingAiStockResponseText(
      "[data-staging-response-holding-stage]",
      strategy.stage || "보유 전략",
    );
    stagingAiStockResponseText(
      "[data-staging-response-holding-summary]",
      strategy.summary || "내 평균 매수가와 현재가를 비교해 보유 기준을 확인해요.",
    );
    const averagePrice = stagingAiStockResponseFinitePrice(strategy.averageBuyPrice);
    const currentPrice = stagingAiStockResponseFinitePrice(strategy.currentPrice);
    const returnRate = Number(strategy.returnRate);
    stagingAiStockResponseText(
      "[data-staging-response-holding-average]",
      averagePrice === null ? "입력 필요" : `${formatNumber(Math.round(averagePrice))}원`,
    );
    stagingAiStockResponseText(
      "[data-staging-response-holding-current]",
      currentPrice === null ? "시세 확인 중" : `${formatNumber(Math.round(currentPrice))}원`,
    );
    stagingAiStockResponseText(
      "[data-staging-response-holding-return]",
      Number.isFinite(returnRate) ? formatPercent(returnRate) : "계산 전",
    );
    stagingAiStockResponseText(
      "[data-staging-response-holding-action]",
      strategy.action || "보유 기준 확인",
    );
  };

  const stagingAiStockResponseSvgNode = (name, attributes = {}, textContent = "") => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) {
      node.setAttribute(key, String(value));
    }
    if (textContent) node.textContent = textContent;
    return node;
  };

  const renderStagingAiStockResponsePriceMap = (perspective = {}, decisionLevels = {}) => {
    const figure = stagingAiStockResponsePage?.querySelector(
      "[data-staging-response-price-map]",
    );
    const plot = figure?.querySelector("[data-staging-response-price-map-plot]");
    if (!(figure instanceof HTMLElement) || !(plot instanceof HTMLElement)) return;
    const currentPrice = stagingAiStockResponseFinitePrice(decisionLevels.currentPrice);
    const buyTrigger = stagingAiStockResponseFinitePrice(decisionLevels.buyTrigger);
    const rawWatchLow = stagingAiStockResponseFinitePrice(decisionLevels.watchLow);
    const rawWatchHigh = stagingAiStockResponseFinitePrice(decisionLevels.watchHigh);
    const riskLine = stagingAiStockResponseFinitePrice(decisionLevels.riskLine);
    const visible = stagingAiStockResponseSelectedState === "not_holding"
      && perspective?.state === "not_holding"
      && currentPrice !== null
      && buyTrigger !== null
      && rawWatchLow !== null
      && rawWatchHigh !== null;
    figure.hidden = !visible;
    if (!visible) {
      figure.dataset.priceMapState = "hidden";
      plot.replaceChildren();
      return;
    }

    const watchLow = Math.min(rawWatchLow, rawWatchHigh);
    const watchHigh = Math.max(rawWatchLow, rawWatchHigh);
    const values = [currentPrice, buyTrigger, watchLow, watchHigh, riskLine]
      .filter((value) => value !== null);
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const spread = Math.max(rawMax - rawMin, currentPrice * 0.01, 1);
    const domainMin = rawMin - spread * 0.16;
    const domainMax = rawMax + spread * 0.16;
    const width = 360;
    const top = 20;
    const bottom = 216;
    const chartLeft = 76;
    const chartRight = 278;
    const yFor = (value) => top + ((domainMax - value) / (domainMax - domainMin)) * (bottom - top);
    const currentY = yFor(currentPrice);
    const triggerY = yFor(buyTrigger);
    const watchTopY = yFor(watchHigh);
    const watchBottomY = yFor(watchLow);
    const watchMidY = (watchTopY + watchBottomY) / 2;
    const riskY = riskLine === null ? null : yFor(riskLine);
    const riskInWatchZone = riskLine !== null
      && riskLine >= watchLow
      && riskLine <= watchHigh;

    const svgElement = stagingAiStockResponseSvgNode("svg", {
      viewBox: `0 0 ${width} 236`,
      role: "img",
      "aria-label": `현재가 ${formatNumber(Math.round(currentPrice))}원, 눌림목 ${formatNumber(Math.round(watchLow))}원에서 ${formatNumber(Math.round(watchHigh))}원, 상승 흐름 확인선 ${formatNumber(Math.round(buyTrigger))}원을 비교한 가격 지도`,
      focusable: "false",
    });
    const title = stagingAiStockResponseSvgNode("title", {}, "미보유 가격 확인 지도");
    const description = stagingAiStockResponseSvgNode(
      "desc",
      {},
      "현재가에서 내려오면 눌림목, 올라가면 상승 흐름 확인선을 보도록 가격의 상대적 위치를 보여줍니다.",
    );
    const defs = stagingAiStockResponseSvgNode("defs");
    const marker = stagingAiStockResponseSvgNode("marker", {
      id: "staging-ai-stock-response-price-arrow",
      viewBox: "0 0 8 8",
      refX: 7,
      refY: 4,
      markerWidth: 7,
      markerHeight: 7,
      orient: "auto-start-reverse",
    });
    marker.appendChild(stagingAiStockResponseSvgNode("path", {
      d: "M 0 0 L 8 4 L 0 8 z",
      class: "staging-ai-stock-response-price-map-arrowhead",
    }));
    defs.appendChild(marker);
    svgElement.append(title, description, defs);

    svgElement.appendChild(stagingAiStockResponseSvgNode("line", {
      x1: chartLeft,
      y1: top,
      x2: chartLeft,
      y2: bottom,
      class: "staging-ai-stock-response-price-map-axis",
    }));
    svgElement.appendChild(stagingAiStockResponseSvgNode("rect", {
      x: chartLeft,
      y: watchTopY,
      width: chartRight - chartLeft,
      height: Math.max(5, watchBottomY - watchTopY),
      rx: 4,
      class: "staging-ai-stock-response-price-map-zone",
    }));

    const levels = [
      {
        key: "breakout",
        label: "상승 확인",
        price: buyTrigger,
        y: triggerY,
        className: "is-breakout",
        dashed: true,
      },
      {
        key: "current",
        label: "현재가",
        price: currentPrice,
        y: currentY,
        className: "is-current",
      },
      {
        key: "watch",
        label: riskInWatchZone ? "눌림목·위험선" : "눌림목",
        priceText: `${formatNumber(Math.round(watchLow))}~${formatNumber(Math.round(watchHigh))}원`,
        y: watchMidY,
        className: "is-watch",
      },
    ];
    if (riskLine !== null && !riskInWatchZone) {
      levels.push({
        key: "risk",
        label: "위험선",
        price: riskLine,
        y: riskY,
        className: "is-risk",
        dashed: true,
      });
    }
    levels.sort((left, right) => left.y - right.y);
    const labelGap = 19;
    levels.forEach((level, index) => {
      level.labelY = Math.max(level.y, index === 0 ? top : levels[index - 1].labelY + labelGap);
    });
    if (levels.at(-1)?.labelY > bottom) {
      levels.at(-1).labelY = bottom;
      for (let index = levels.length - 2; index >= 0; index -= 1) {
        levels[index].labelY = Math.min(levels[index].labelY, levels[index + 1].labelY - labelGap);
      }
    }
    if (levels[0]?.labelY < top) {
      const shift = top - levels[0].labelY;
      levels.forEach((level) => { level.labelY += shift; });
    }

    levels.forEach((level) => {
      const line = stagingAiStockResponseSvgNode("line", {
        x1: chartLeft,
        y1: level.y,
        x2: chartRight,
        y2: level.y,
        class: `staging-ai-stock-response-price-map-level ${level.className}${level.dashed ? " is-dashed" : ""}`,
      });
      svgElement.appendChild(line);
      if (level.key === "current") {
        svgElement.appendChild(stagingAiStockResponseSvgNode("circle", {
          cx: chartLeft,
          cy: level.y,
          r: 5,
          class: "staging-ai-stock-response-price-map-current-dot",
        }));
      }
      svgElement.appendChild(stagingAiStockResponseSvgNode("path", {
        d: `M ${chartRight} ${level.y} L 288 ${level.y} L 296 ${level.labelY}`,
        class: "staging-ai-stock-response-price-map-connector",
      }));
      svgElement.appendChild(stagingAiStockResponseSvgNode("text", {
        x: 4,
        y: level.labelY + 4,
        class: `staging-ai-stock-response-price-map-label ${level.className}`,
      }, level.label));
      svgElement.appendChild(stagingAiStockResponseSvgNode("text", {
        x: 356,
        y: level.labelY + 4,
        "text-anchor": "end",
        class: "staging-ai-stock-response-price-map-price",
      }, level.priceText || `${formatNumber(Math.round(level.price))}원`));
    });

    if (watchMidY - currentY > 12) {
      svgElement.appendChild(stagingAiStockResponseSvgNode("line", {
        x1: 160,
        y1: currentY + 7,
        x2: 160,
        y2: watchMidY - 7,
        class: "staging-ai-stock-response-price-map-route is-pullback",
        "marker-end": "url(#staging-ai-stock-response-price-arrow)",
      }));
      svgElement.appendChild(stagingAiStockResponseSvgNode("text", {
        x: 168,
        y: (currentY + watchMidY) / 2 + 4,
        class: "staging-ai-stock-response-price-map-route-number",
      }, "①"));
    }
    if (currentY - triggerY > 12) {
      svgElement.appendChild(stagingAiStockResponseSvgNode("line", {
        x1: 222,
        y1: currentY - 7,
        x2: 222,
        y2: triggerY + 7,
        class: "staging-ai-stock-response-price-map-route is-breakout",
        "marker-end": "url(#staging-ai-stock-response-price-arrow)",
      }));
      svgElement.appendChild(stagingAiStockResponseSvgNode("text", {
        x: 230,
        y: (currentY + triggerY) / 2 + 4,
        class: "staging-ai-stock-response-price-map-route-number",
      }, "②"));
    }
    plot.replaceChildren(svgElement);
    figure.dataset.priceMapState = "ready";
  };

  const stagingAiStockResponseQuoteTone = (value = stagingAiStockResponseLiveQuote.changeRate) => {
    if (value === null || value === undefined || value === "") return "muted";
    const rate = Number(value);
    return Number.isFinite(rate) && rate > 0
      ? "positive"
      : Number.isFinite(rate) && rate < 0
        ? "negative"
        : "muted";
  };

  const renderStagingAiStockResponseAnalysisStatus = () => {
    if (!stagingAiStockResponsePage) return;
    const control = stagingAiStockResponsePage.querySelector(
      "[data-staging-response-analysis-refresh]",
    );
    const status = stagingAiStockResponsePage.querySelector(
      "[data-staging-response-analysis-status]",
    );
    const button = stagingAiStockResponsePage.querySelector(
      "[data-staging-response-reanalyze]",
    );
    if (!(control instanceof HTMLElement) || !(button instanceof HTMLButtonElement)) return;
    const code = String(stagingAiStockResponsePage.dataset.responseCode || "");
    const livePrice = stagingAiStockResponseFinitePrice(stagingAiStockResponseLiveQuote.price);
    const baselinePrice = stagingAiStockResponseAnalysisBaseline.code === code
      ? stagingAiStockResponseFinitePrice(stagingAiStockResponseAnalysisBaseline.price)
      : null;
    const explanationReady = stagingAiStockResponsePage.dataset.responseDisplay === "ready";
    const changed = livePrice !== null
      && baselinePrice !== null
      && Math.round(livePrice) !== Math.round(baselinePrice);
    let state = "ready";
    let statusText = baselinePrice === null
      ? "설명 기준 가격을 준비하고 있어요."
      : `아래 설명은 ${formatNumber(Math.round(baselinePrice))}원을 기준으로 정리했어요.`;
    let buttonText = "다시 분석하기";
    if (!explanationReady || stagingAiStockResponseReanalysisPending) {
      state = "loading";
      if (stagingAiStockResponseReanalysisPending) {
        statusText = "현재 시세와 6가지 자료로 설명을 다시 정리하고 있어요.";
        buttonText = "다시 분석 중";
      } else if (baselinePrice !== null) {
        statusText = "내 상황에 맞는 설명을 정리하고 있어요.";
        buttonText = "설명 정리 중";
      } else {
        buttonText = "분석 준비 중";
      }
    } else if (changed) {
      state = "stale";
      statusText = `현재가는 ${formatNumber(Math.round(livePrice))}원으로 바뀌었어요. 아래 설명은 ${formatNumber(Math.round(baselinePrice))}원 기준이에요.`;
      buttonText = "현재 시세로 다시 분석";
    } else if (baselinePrice !== null && livePrice !== null) {
      statusText = `아래 설명은 현재 시세 ${formatNumber(Math.round(baselinePrice))}원을 기준으로 정리했어요.`;
    }
    control.dataset.analysisState = state;
    if (status) status.textContent = statusText;
    button.textContent = buttonText;
    button.disabled = !explanationReady
      || stagingAiStockResponseReanalysisPending
      || baselinePrice === null;
    button.setAttribute("aria-busy", String(state === "loading"));
    button.setAttribute(
      "aria-label",
      state === "stale" ? "변경된 현재 시세로 종목 설명 다시 분석하기" : buttonText,
    );
  };

  const renderStagingAiStockResponseLiveQuote = () => {
    if (!stagingAiStockResponsePage) return;
    const price = stagingAiStockResponseLiveQuote.price;
    const changeRate = stagingAiStockResponseLiveQuote.changeRate;
    const hasPrice = price !== null && price !== undefined && Number.isFinite(Number(price));
    const hasRate = changeRate !== null && changeRate !== undefined && Number.isFinite(Number(changeRate));
    const tone = stagingAiStockResponseQuoteTone(changeRate);
    const quote = stagingAiStockResponsePage.querySelector("[data-staging-response-live-quote]");
    const priceNode = stagingAiStockResponsePage.querySelector("[data-staging-response-live-price]");
    const rateNode = stagingAiStockResponsePage.querySelector("[data-staging-response-live-rate]");
    const stateNode = stagingAiStockResponsePage.querySelector("[data-staging-response-live-state]");
    if (priceNode) priceNode.textContent = hasPrice
      ? `${formatNumber(Math.round(Number(price)))}원`
      : "시세 확인 중";
    if (rateNode) {
      rateNode.textContent = hasRate ? formatPercent(changeRate) : "--";
      rateNode.dataset.quoteTone = tone;
    }
    const marketSession = String(stagingAiStockResponseLiveQuote.marketSession || "").toLowerCase();
    const marketSessionLabel = String(
      stagingAiStockResponseLiveQuote.marketSessionLabel || "",
    ).trim();
    const closedSession = ["closed", "krx_reference", "after_market_reference"].includes(
      marketSession,
    );
    const stateText = stagingAiStockResponseLiveQuote.state === "connected"
      ? closedSession
        ? (marketSessionLabel || "장 마감 시세")
        : stagingAiStockResponseLiveQuote.isLive
          ? "실시간으로 반영 중"
          : (marketSessionLabel || "가장 최근 시세")
      : stagingAiStockResponseLiveQuote.state === "connecting"
        ? "실시간 시세 연결 중"
        : hasPrice
          ? (stagingAiStockResponseLiveQuote.isLive ? "실시간 시세" : "가장 최근 시세")
          : "시세를 불러오고 있어요";
    if (stateNode) stateNode.textContent = stateText;
    if (quote instanceof HTMLElement) {
      quote.dataset.liveQuoteState = stagingAiStockResponseLiveQuote.state;
      quote.dataset.quoteTone = tone;
    }
    renderStagingAiStockResponseAnalysisStatus();
  };

  const updateStagingAiStockResponseLiveQuote = (code, quote = {}) => {
    if (String(code || "") !== stagingAiStockResponseLiveQuote.code || !quote) return;
    const price = quote.price !== null && quote.price !== undefined
      ? Number(quote.price)
      : Number.NaN;
    const changeRate = quote.change_rate !== null && quote.change_rate !== undefined
      ? Number(quote.change_rate)
      : Number.NaN;
    if (Number.isFinite(price)) stagingAiStockResponseLiveQuote.price = price;
    if (Number.isFinite(changeRate)) stagingAiStockResponseLiveQuote.changeRate = changeRate;
    stagingAiStockResponseLiveQuote.marketSession = String(quote.market_session || "");
    stagingAiStockResponseLiveQuote.marketSessionLabel = String(
      quote.market_session_label || "",
    );
    stagingAiStockResponseLiveQuote.asOf = quote.as_of || quote.trade_date || null;
    stagingAiStockResponseLiveQuote.state = "connected";
    stagingAiStockResponseLiveQuote.isLive = typeof quote.is_live === "boolean"
      ? quote.is_live
      : ["regular", "open"].includes(
        stagingAiStockResponseLiveQuote.marketSession.toLowerCase(),
      );
    renderStagingAiStockResponseLiveQuote();
  };

  const syncStagingAiStockResponseQuoteScope = () => {
    const active = Boolean(
      !document.hidden
      && stagingAiStockResponsePage
      && !stagingAiStockResponsePage.hidden,
    );
    const code = active ? String(stagingAiStockResponsePage?.dataset.responseCode || "") : "";
    const signature = `${active ? "detail" : "off"}:${code}`;
    if (active && code && stagingAiStockResponseLiveQuote.code !== code) {
      stagingAiStockResponseLiveQuote = {
        code,
        price: null,
        changeRate: null,
        state: "connecting",
        isLive: false,
        marketSession: "",
        marketSessionLabel: "",
        asOf: null,
      };
    }
    if (active && code && stagingAiStockResponseLiveQuote.state !== "connected") {
      stagingAiStockResponseLiveQuote.state = "connecting";
    }
    renderStagingAiStockResponseLiveQuote();
    if (typeof replaceQuoteStreamScope !== "function") {
      stagingAiStockResponseQuoteScopeSignature = "";
      return;
    }
    if (signature === stagingAiStockResponseQuoteScopeSignature) return;
    stagingAiStockResponseQuoteScopeSignature = signature;
    replaceQuoteStreamScope("staging-ai-stock-response", code ? [{
      code,
      handlers: {
        onStatus: () => {
          if (stagingAiStockResponseLiveQuote.code !== code) return;
          if (stagingAiStockResponseLiveQuote.state !== "connected") {
            stagingAiStockResponseLiveQuote.state = "connecting";
          }
          renderStagingAiStockResponseLiveQuote();
        },
        onQuote: (payload) => updateStagingAiStockResponseLiveQuote(code, payload.quote),
      },
    }] : []);
  };

  const renderStagingAiStockResponseLoading = (detail) => {
    if (!stagingAiStockResponsePage || !detail) return;
    stagingAiStockResponseSummaryToken += 1;
    stagingAiStockResponseRenderedResult = null;
    stagingAiStockResponseRenderedFailedSources = 0;
    if (stagingAiStockResponseAnalysisBaseline.code !== String(detail.code || "")) {
      stagingAiStockResponseAnalysisBaseline = {
        code: String(detail.code || ""),
        price: null,
        asOf: null,
      };
      stagingAiStockResponseReanalysisPending = false;
    }
    stagingAiStockResponsePage.dataset.responseTone = detail.tone || "neutral";
    stagingAiStockResponsePage.dataset.responseCode = detail.code || "";
    if (stagingAiStockResponseLiveQuote.code !== String(detail.code || "")) {
      stagingAiStockResponseLiveQuote = {
        code: String(detail.code || ""),
        price: null,
        changeRate: null,
        state: "connecting",
        isLive: false,
        marketSession: "",
        marketSessionLabel: "",
        asOf: null,
      };
    }
    renderStagingAiStockResponseLiveQuote();
    syncStagingAiStockResponseInvestorState(
      stagingAiStockResponseInvestorStateForCode(detail.code),
      stagingAiStockResponseAverageBuyPriceForCode(detail.code),
    );
    setStagingAiStockResponseDisplay("loading", "6가지 자료를 확인하고 있어요.");
    renderStagingAiStockResponseAnalysisStatus();
    stagingAiStockResponseText("[data-staging-response-name]", detail.name || detail.code || "관심종목");
    stagingAiStockResponseText("[data-staging-response-status]", "자료 확인 중");
    stagingAiStockResponseSetTime(
      "[data-staging-response-updated]",
      detail.updatedAt || "업데이트 확인 중",
      { prefix: "홈에서 본 시각" },
    );
    stagingAiStockResponseText("[data-staging-response-context]", stagingAiStockResponseContext(detail));
    stagingAiStockResponseText(
      "[data-staging-response-action]",
      "6가지 자료를 확인하고 있어요",
    );
    stagingAiStockResponseText("[data-staging-response-summary]", "잠시만 기다리면 쉬운 말로 정리해 드릴게요.");
    stagingAiStockResponseText("[data-staging-response-reason]", detail.action || "종목별 판단 근거를 연결하고 있습니다.");
    stagingAiStockResponseText("[data-staging-response-direction]", "계산 중");
    stagingAiStockResponseText("[data-staging-response-data-state]", "확인 중");
    stagingAiStockResponseText("[data-staging-response-confidence]", "--");
    stagingAiStockResponseText("[data-staging-response-coverage-label]", "확인 중");
    stagingAiStockResponseText("[data-staging-response-score]", "--");
    stagingAiStockResponseText("[data-staging-response-coverage]", "6개 중 0개");
    stagingAiStockResponseText("[data-staging-response-original-stance]", "계산 중");
    stagingAiStockResponseText(
      "[data-staging-response-lead]",
      "가격 흐름 25 · 외국인·기관 매매 25 · 회사 공시 15 · 뉴스 10 · 증권사 리포트 15 · 시장 환경 10 가중 종합",
    );
    const keyReasonList = stagingAiStockResponsePage.querySelector("[data-staging-response-key-reasons]");
    if (keyReasonList) {
      keyReasonList.replaceChildren(...STAGING_AI_STOCK_RESPONSE_METRICS.slice(0, 3).map(
        (metric) => stagingAiStockResponseKeyReasonRow(metric, { loading: true }),
      ));
    }
    const metricList = stagingAiStockResponsePage.querySelector("[data-staging-response-metrics]");
    if (metricList) {
      metricList.replaceChildren(...STAGING_AI_STOCK_RESPONSE_METRICS.map(
        (metric) => stagingAiStockResponseMetricRow(metric, { loading: true }),
      ));
    }
    const warnings = stagingAiStockResponsePage.querySelector("[data-staging-response-warnings]");
    const next = stagingAiStockResponsePage.querySelector("[data-staging-response-next]");
    const retry = stagingAiStockResponsePage.querySelector("[data-staging-response-retry]");
    if (warnings) warnings.hidden = true;
    if (next) next.hidden = true;
    if (retry instanceof HTMLButtonElement) retry.hidden = true;
    stagingAiStockResponseText("[data-staging-response-announcement]", "AI 분석 자료를 불러오는 중입니다.");
    storeStagingAiStockResponseDetail(detail);
  };

  const renderStagingAiStockResponseResult = (result, { failedSources = 0 } = {}) => {
    if (!stagingAiStockResponsePage || !result) return;
    stagingAiStockResponseRenderedResult = result;
    stagingAiStockResponseRenderedFailedSources = failedSources;
    const investorState = normalizeStagingAiStockResponseInvestorState(
      stagingAiStockResponseSelectedState,
    );
    const perspective = stagingAiStockResponsePerspectiveCopy(result, investorState);
    const holdingInputRequired = perspective.positionMode === "holding_unknown";
    stagingAiStockResponsePage.dataset.responseTone = result.tone || "neutral";
    stagingAiStockResponsePage.dataset.responseCode = result.code || "";
    const decisionLevels = result.decisionLevels || {};
    const resultCode = String(result.code || "");
    const resultPrice = decisionLevels.currentPrice;
    const resultChangeRate = decisionLevels.changeRate;
    stagingAiStockResponseAnalysisBaseline = {
      code: resultCode,
      price: stagingAiStockResponseFinitePrice(resultPrice),
      asOf: decisionLevels.quoteAsOf || result.asOf || null,
    };
    if (stagingAiStockResponseLiveQuote.code !== resultCode) {
      stagingAiStockResponseLiveQuote = {
        code: resultCode,
        price: resultPrice !== null && resultPrice !== undefined && Number.isFinite(Number(resultPrice))
          ? Number(resultPrice)
          : null,
        changeRate: resultChangeRate !== null && resultChangeRate !== undefined && Number.isFinite(Number(resultChangeRate))
          ? Number(resultChangeRate)
          : null,
        state: "snapshot",
        isLive: decisionLevels.quoteIsLive === true,
        marketSession: String(decisionLevels.marketSession || ""),
        marketSessionLabel: String(decisionLevels.marketSessionLabel || ""),
        asOf: decisionLevels.quoteAsOf || null,
      };
    } else {
      if (
        stagingAiStockResponseLiveQuote.price === null
        && resultPrice !== null
        && resultPrice !== undefined
        && Number.isFinite(Number(resultPrice))
      ) stagingAiStockResponseLiveQuote.price = Number(resultPrice);
      if (
        stagingAiStockResponseLiveQuote.changeRate === null
        && resultChangeRate !== null
        && resultChangeRate !== undefined
        && Number.isFinite(Number(resultChangeRate))
      ) stagingAiStockResponseLiveQuote.changeRate = Number(resultChangeRate);
      stagingAiStockResponseLiveQuote.isLive = stagingAiStockResponseLiveQuote.isLive
        || decisionLevels.quoteIsLive === true;
      if (!stagingAiStockResponseLiveQuote.marketSession) {
        stagingAiStockResponseLiveQuote.marketSession = String(
          decisionLevels.marketSession || "",
        );
      }
      if (!stagingAiStockResponseLiveQuote.marketSessionLabel) {
        stagingAiStockResponseLiveQuote.marketSessionLabel = String(
          decisionLevels.marketSessionLabel || "",
        );
      }
      if (!stagingAiStockResponseLiveQuote.asOf) {
        stagingAiStockResponseLiveQuote.asOf = decisionLevels.quoteAsOf || null;
      }
    }
    renderStagingAiStockResponseLiveQuote();
    setStagingAiStockResponseDisplay("loading", `내 상황을 ${STAGING_AI_STOCK_RESPONSE_INVESTOR_STATES[investorState].label} 기준으로 반영해 쉬운 말로 정리하고 있어요.`);
    renderStagingAiStockResponseAnalysisStatus();
    const detail = readStagingAiStockResponseDetail(result.code) || {};
    const stanceCopy = stagingAiStockResponseStanceCopy(result.stance);
    stagingAiStockResponseText("[data-staging-response-name]", result.name || result.code || "관심종목");
    stagingAiStockResponseText("[data-staging-response-status]", stanceCopy.badge);
    stagingAiStockResponsePage.querySelector("[data-staging-response-status]")
      ?.setAttribute("data-original-stance", result.stance || "정보 확인 우선");
    stagingAiStockResponseSetTime("[data-staging-response-updated]", result.asOf, { prefix: "가장 최근 자료" });
    stagingAiStockResponseText("[data-staging-response-context]", stagingAiStockResponseContext(detail));
    stagingAiStockResponseText("[data-staging-response-action]", perspective.headline);
    stagingAiStockResponseText("[data-staging-response-summary]", perspective.summary);
    stagingAiStockResponseText(
      "[data-staging-response-reason]",
      perspective.reason || stagingAiStockResponseReason(result),
    );
    stagingAiStockResponseText("[data-staging-response-direction]", perspective.direction);
    stagingAiStockResponseText("[data-staging-response-direction-guide]", perspective.guide);
    stagingAiStockResponseText(
      "[data-staging-response-data-state]",
      stagingAiStockResponseDataState(result.confidence, result.limited),
    );
    stagingAiStockResponseText(
      "[data-staging-response-score]",
      result.scoreDisplay === "--" ? "--" : `${result.scoreDisplay}점`,
    );
    stagingAiStockResponseText("[data-staging-response-confidence]", `${result.confidence}/100`);
    stagingAiStockResponseText(
      "[data-staging-response-coverage-label]",
      stagingAiStockResponseCoverage(result.coverageCount),
    );
    stagingAiStockResponseText("[data-staging-response-coverage]", `6개 중 ${result.coverageCount}개`);
    stagingAiStockResponseText("[data-staging-response-original-stance]", result.stance || "정보 확인 우선");
    stagingAiStockResponseText("[data-staging-response-lead]", result.lead);
    const stockLink = stagingAiStockResponsePage.querySelector("[data-staging-response-stock-link]");
    if (stockLink instanceof HTMLAnchorElement) {
      stockLink.href = `/dashboard/${encodeURIComponent(result.code || "")}`;
      stockLink.setAttribute("aria-label", `${result.name || result.code || "종목"} 상세에서 차트 보기`);
    }

    const buyTrigger = decisionLevels.buyTrigger !== null && decisionLevels.buyTrigger !== undefined
      ? Number(decisionLevels.buyTrigger)
      : Number.NaN;
    const buyTriggerText = Number.isFinite(buyTrigger)
      ? `${formatNumber(Math.round(buyTrigger))}원`
      : "상승 흐름 확인선";
    stagingAiStockResponseText(
      "[data-staging-response-guide-title]",
      perspective.positionMode === "holding_profit"
        ? "수익을 지킬 가격을 나눠 보세요"
        : perspective.positionMode === "holding_loss"
          ? "손실 제한선과 회복선을 나눠 보세요"
          : perspective.positionMode === "holding_unknown"
            ? "평균 매수가를 입력해 손익 기준을 확인하세요"
            : "가격이 내려올 때와 올라갈 때를 나눠 보세요",
    );
    stagingAiStockResponseText(
      "[data-staging-response-guide-intro]",
      perspective.positionMode?.startsWith("holding")
        ? "현재가와 내 평균 매수가, 가격 흐름을 함께 비교한 참고 기준이에요."
        : `${buyTriggerText}은 바로 사는 가격이 아니라 상승 흐름이 살아나는지 확인하는 선이에요. 가격이 내려오면 눌림목에서 하락이 멈추는지도 따로 봐요.`,
    );
    renderStagingAiStockResponseHoldingStrategy(perspective);
    renderStagingAiStockResponsePriceMap(perspective, decisionLevels);
    const guideSection = stagingAiStockResponsePage.querySelector(
      ".staging-ai-stock-response-guide",
    );
    if (guideSection instanceof HTMLElement) guideSection.hidden = holdingInputRequired;
    const guideRows = stagingAiStockResponsePage.querySelector("[data-staging-response-guide-rows]");
    if (guideRows) {
      guideRows.replaceChildren(...(perspective.rows || []).map(
        (item) => stagingAiStockResponseGuideRow(item),
      ));
    }

    const keyReasonList = stagingAiStockResponsePage.querySelector("[data-staging-response-key-reasons]");
    if (keyReasonList) {
      const rankedMetrics = [...(result.metrics || [])].sort((left, right) => {
        if (left.hardRisk !== right.hardRisk) return Number(right.hardRisk) - Number(left.hardRisk);
        if (left.available !== right.available) return Number(right.available) - Number(left.available);
        return Math.abs(Number(right.score) * Number(right.weight))
          - Math.abs(Number(left.score) * Number(left.weight));
      });
      keyReasonList.replaceChildren(...rankedMetrics.slice(0, 3).map(
        (metric) => stagingAiStockResponseKeyReasonRow(metric),
      ));
    }

    const metricList = stagingAiStockResponsePage.querySelector("[data-staging-response-metrics]");
    if (metricList) {
      metricList.replaceChildren(...result.metrics.map((metric) => stagingAiStockResponseMetricRow(metric)));
    }

    const warningSection = stagingAiStockResponsePage.querySelector("[data-staging-response-warnings]");
    const warningList = warningSection?.querySelector("ul");
    const warningItems = [...(result.warnings || [])];
    if (failedSources > 0) {
      warningItems.push(`일부 원천 응답 지연: 연결된 ${result.coverageCount}/6개 지표만 반영`);
    }
    if (warningList) {
      warningList.replaceChildren(...warningItems.map((item) => {
        const row = document.createElement("li");
        row.textContent = stagingAiStockResponseFriendlyWarning(item);
        return row;
      }));
    }
    if (warningSection) warningSection.hidden = warningItems.length === 0;

    const nextSection = stagingAiStockResponsePage.querySelector("[data-staging-response-next]");
    const nextList = nextSection?.querySelector("[data-staging-response-decision-plan]");
    const deterministicNextChecks = (perspective.nextChecks || []).map(
      (item) => stagingAiStockResponseFriendlyNextCheck(item),
    );
    const perspectiveNextChecks = [
      stagingAiStockResponseInvestorNextCheck(result, investorState),
      ...deterministicNextChecks,
      ...(deterministicNextChecks.length === 0
        ? (result.nextChecks || []).map((item) => stagingAiStockResponseFriendlyNextCheck(item))
        : []),
    ].filter((item, index, items) => item && items.indexOf(item) === index).slice(0, 5);
    const decisionPlan = holdingInputRequired
      ? []
      : Array.isArray(perspective.decisionPlan) && perspective.decisionPlan.length
        ? perspective.decisionPlan
        : perspectiveNextChecks.slice(0, 3).map((item, index) => ({
          key: `check_${index + 1}`,
          label: `${index + 1}번째 확인`,
          status: "조건 확인",
          value: "가격과 매매 흐름",
          evidence: item,
          tone: "neutral",
        }));
    if (nextList) {
      nextList.replaceChildren(...decisionPlan.map(
        (item) => stagingAiStockResponseDecisionStepRow(item),
      ));
    }
    stagingAiStockResponseText(
      "[data-staging-response-next-summary]",
      perspective.positionMode === "holding_profit"
        ? "오르면 일부 이익을 지키고, 내려오면 남은 수량의 보호 기준을 확인하세요."
        : perspective.positionMode === "holding_loss"
          ? "더 내려갈 때 손실을 줄일 기준과 다시 회복할 때 확인할 조건을 나눠 보세요."
          : perspective.positionMode?.startsWith("holding")
            ? "내 평균 매수가와 현재가를 비교해 계속 보유할 기준과 수량을 줄일 기준을 나눠 보세요."
            : "가격이 내려오면 하락이 멈추는지, 올라가면 확인선 위에서 흐름을 유지하는지 순서대로 보세요.",
    );
    if (nextSection) nextSection.hidden = decisionPlan.length === 0;
    const retry = stagingAiStockResponsePage.querySelector("[data-staging-response-retry]");
    if (retry instanceof HTMLButtonElement) retry.hidden = failedSources === 0;
    if (holdingInputRequired) {
      const summaryToken = ++stagingAiStockResponseSummaryToken;
      finishStagingAiStockResponseSummary({
        requestedCode: String(result.code),
        requestedState: investorState,
        summaryToken,
        mode: "rules",
      });
    } else if (stagingGptPageSummaryEnabled) {
      void applyStagingAiStockResponseSummary(result, investorState);
    } else {
      const summaryToken = ++stagingAiStockResponseSummaryToken;
      finishStagingAiStockResponseSummary({
        requestedCode: String(result.code),
        requestedState: investorState,
        summaryToken,
        mode: "rules",
      });
    }
  };

  const fetchStagingAiStockResponseJson = async (url, signal, { force = false } = {}) => {
    for (let attempt = 0; attempt < 20; attempt += 1) {
      if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
      if (typeof fetchJsonCached === "function") {
        return fetchJsonCached(url, {
          force,
          ttlMs: force ? 0 : STAGING_AI_STOCK_RESPONSE_CACHE_MS,
          timeoutMs: 25_000,
        });
      }
      await new Promise((resolve) => window.setTimeout(resolve, 25));
    }
    throw new Error("AI stock response data client unavailable");
  };

  const stagingAiStockResponseDashboardWithLatestQuote = (dashboard, code = "") => {
    if (!dashboard || typeof dashboard !== "object") return dashboard;
    const livePrice = stagingAiStockResponseFinitePrice(stagingAiStockResponseLiveQuote.price);
    if (
      String(stagingAiStockResponseLiveQuote.code || "") !== String(code || "")
      || livePrice === null
    ) return dashboard;
    const liveChangeRate = Number(stagingAiStockResponseLiveQuote.changeRate);
    return {
      ...dashboard,
      quote: {
        ...(dashboard.quote && typeof dashboard.quote === "object" ? dashboard.quote : {}),
        price: livePrice,
        ...(Number.isFinite(liveChangeRate) ? { change_rate: liveChangeRate } : {}),
        market_session: stagingAiStockResponseLiveQuote.marketSession
          || dashboard.quote?.market_session
          || "",
        market_session_label: stagingAiStockResponseLiveQuote.marketSessionLabel
          || dashboard.quote?.market_session_label
          || "",
        is_live: stagingAiStockResponseLiveQuote.isLive === true,
        as_of: stagingAiStockResponseLiveQuote.asOf
          || dashboard.quote?.as_of
          || dashboard.as_of
          || null,
      },
    };
  };

  const loadStagingAiStockResponse = async (detail, { force = false } = {}) => {
    const code = String(detail?.code || "").trim();
    if (!code || !stagingAiStockResponsePage) return;
    const cached = stagingAiStockResponseCache.get(code);
    if (!force && cached && Date.now() - cached.cachedAt < STAGING_AI_STOCK_RESPONSE_CACHE_MS) {
      renderStagingAiStockResponseResult(cached.result, { failedSources: cached.failedSources });
      return;
    }
    const logic = window.SecretNoteAiStockResponse;
    if (!logic?.buildResponse) {
      const fallback = {
        code,
        name: detail.name,
        asOf: null,
        stance: "정보 확인 우선",
        tone: "limited",
        action: "세부 판단 모듈을 불러오지 못했습니다. 잠시 후 다시 열어 주세요.",
        summary: "종목별 6개 자료를 아직 계산하지 못했습니다.",
        score: null,
        scoreDisplay: "--",
        confidence: 0,
        coverageLabel: "0/6개",
        coverageCount: 0,
        hardRisk: false,
        conflict: false,
        limited: true,
        lead: "가격 흐름 25 · 외국인·기관 매매 25 · 회사 공시 15 · 뉴스 10 · 증권사 리포트 15 · 시장 환경 10 가중 종합",
        metrics: STAGING_AI_STOCK_RESPONSE_METRICS.map((metric) => ({
          ...metric,
          available: false,
          score: null,
          status: "확인 중",
          tone: "limited",
          value: "자료 확인 중",
          evidence: `${metric.label} 자료를 아직 불러오지 못했어요.`,
          source: "연결 재시도 필요",
          asOf: null,
        })),
        warnings: ["판단 모듈 로드 실패"],
        nextChecks: [],
      };
      renderStagingAiStockResponseResult(fallback, { failedSources: 4 });
      return;
    }
    const requestToken = ++stagingAiStockResponseRequestToken;
    stagingAiStockResponseAbortController?.abort();
    stagingAiStockResponseAbortController = new AbortController();
    const signal = stagingAiStockResponseAbortController.signal;
    const encodedCode = encodeURIComponent(code);
    const requests = [
      ["quant", `/stocks/${encodedCode}/quant-signals`],
      ["dashboard", `/stocks/${encodedCode}/dashboard?include_profile=0&include_live=0`],
      ["homeContext", `/stocks/${encodedCode}/home-context?flow_limit=1500&research_limit=100&disclosure_limit=100&news_limit=60&community_limit=12`],
      ["marketImpact", "/market/impact"],
    ];
    const settled = await Promise.allSettled(
      requests.map(([, url]) => fetchStagingAiStockResponseJson(url, signal, { force })),
    );
    if (signal.aborted || requestToken !== stagingAiStockResponseRequestToken) return;
    const payloads = {};
    let failedSources = 0;
    settled.forEach((outcome, index) => {
      if (outcome.status === "fulfilled") payloads[requests[index][0]] = outcome.value;
      else failedSources += 1;
    });
    const result = logic.buildResponse({
      code,
      fallbackDetail: detail,
      quant: payloads.quant,
      dashboard: stagingAiStockResponseDashboardWithLatestQuote(payloads.dashboard, code),
      homeContext: payloads.homeContext,
      marketImpact: payloads.marketImpact,
    });
    stagingAiStockResponseCache.set(code, { result, failedSources, cachedAt: Date.now() });
    if (stagingAiStockResponsePage.dataset.responseCode === code) {
      renderStagingAiStockResponseResult(result, { failedSources });
    }
  };

  const stagingAiStockResponseDetailForRoute = () => {
    const code = new URLSearchParams(window.location.search).get("code")?.trim() || "";
    const matchingRow = Array.from(document.querySelectorAll(
      "#home-ai-response-personal-list .home-ai-interest-row",
    )).find((row) => stagingAiStockResponseCodeFromHref(row.href) === code);
    return stagingAiStockResponseDetailFromRow(matchingRow)
      || readStagingAiStockResponseDetail(code)
      || {
        code,
        name: code || "관심종목",
        status: "대응 확인 중",
        action: "홈의 AI 종목 대응에서 최신 내용을 다시 확인해 주세요.",
        issue: "관심종목과 최근 시장 이벤트의 연결을 불러오고 있습니다.",
        relation: "관심종목 연관",
        signal: "",
        updatedAt: "업데이트 확인 중",
        tone: "neutral",
      };
  };

  const openStagingAiStockResponse = (detail, { historyMode = "push", focusBack = true } = {}) => {
    if (!stagingAiStockResponsePage || !homeView || !detail) return;
    if (stagingAiStockResponsePage.hidden) {
      stagingAiStockResponseReturnScrollY = Math.max(0, window.scrollY);
    }
    storeStagingAiStockResponseDetail(detail);
    syncStagingAiStockResponseInvestorState(
      stagingAiStockResponseInvestorStateForCode(detail.code),
      stagingAiStockResponseAverageBuyPriceForCode(detail.code),
    );
    const cached = stagingAiStockResponseCache.get(detail.code);
    if (cached && Date.now() - cached.cachedAt < STAGING_AI_STOCK_RESPONSE_CACHE_MS) {
      renderStagingAiStockResponseResult(cached.result, { failedSources: cached.failedSources });
    } else {
      renderStagingAiStockResponseLoading(detail);
    }
    if (historyMode !== "none") {
      const url = new URL(window.location.href);
      url.pathname = "/dashboard";
      url.searchParams.set("view", STAGING_AI_STOCK_RESPONSE_VIEW);
      if (detail.code) url.searchParams.set("code", detail.code);
      else url.searchParams.delete("code");
      const historyState = {
        ...(window.history.state || {}),
        stagingPanel: STAGING_AI_STOCK_RESPONSE_VIEW,
        responseCode: detail.code || "",
      };
      window.history.pushState(historyState, "", url);
    }
    homeView.hidden = true;
    stagingAiStockResponsePage.hidden = false;
    document.body.dataset.stagingAiStockResponse = "open";
    document.body.dataset.view = STAGING_AI_STOCK_RESPONSE_VIEW;
    window.scrollTo({ top: 0, behavior: "auto" });
    syncStagingAiStockResponseQuoteScope();
    void loadStagingAiStockResponse(detail);
    if (focusBack) {
      window.requestAnimationFrame(() => contextualBack?.focus());
    }
  };

  const restoreStagingAiStockResponseTriggerFocus = () => {
    if (!stagingAiStockResponseRestoreFocusPending) return;
    const connectedTrigger = stagingAiStockResponseTrigger?.isConnected
      ? stagingAiStockResponseTrigger
      : null;
    const matchingTrigger = Array.from(document.querySelectorAll(
      "#home-ai-response-personal-list .home-ai-interest-row",
    )).find((row) => stagingAiStockResponseCodeFromHref(row.href) === stagingAiStockResponseTriggerCode);
    const trigger = connectedTrigger || matchingTrigger;
    if (!(trigger instanceof HTMLElement) || trigger.getClientRects().length === 0) return;
    trigger.focus({ preventScroll: true });
    stagingAiStockResponseTrigger = trigger;
    stagingAiStockResponseRestoreFocusPending = document.activeElement !== trigger;
  };

  const closeStagingAiStockResponse = ({ restoreFocus = true } = {}) => {
    if (!stagingAiStockResponsePage || !homeView) return;
    stagingAiStockResponseAbortController?.abort();
    stagingAiStockResponseAbortController = null;
    stagingAiStockResponseRequestToken += 1;
    stagingAiStockResponseSummaryToken += 1;
    stagingAiStockResponseQuoteScopeSignature = "";
    stagingAiStockResponseLiveQuote.state = "idle";
    stagingAiStockResponseReanalysisPending = false;
    if (typeof clearQuoteStreamScope === "function") {
      clearQuoteStreamScope("staging-ai-stock-response");
    }
    stagingAiStockResponsePage.hidden = true;
    homeView.hidden = false;
    delete document.body.dataset.stagingAiStockResponse;
    if (document.body.dataset.view === STAGING_AI_STOCK_RESPONSE_VIEW) {
      document.body.dataset.view = "home";
    }
    stagingAiStockResponseRestoreFocusPending = restoreFocus;
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: stagingAiStockResponseReturnScrollY, behavior: "auto" });
      restoreStagingAiStockResponseTriggerFocus();
    });
    window.setTimeout(restoreStagingAiStockResponseTriggerFocus, 120);
    window.setTimeout(restoreStagingAiStockResponseTriggerFocus, 420);
  };

  const syncStagingAiStockResponseRoute = () => {
    if (!stagingAiStockResponsePage || !homeView) return;
    if (stagingAiStockResponseRouteActive()) {
      if (stagingAiStockResponsePage.hidden) {
        openStagingAiStockResponse(stagingAiStockResponseDetailForRoute(), {
          historyMode: "none",
          focusBack: false,
        });
      }
      return;
    }
    if (!stagingAiStockResponsePage.hidden) closeStagingAiStockResponse();
  };

  const homeView = document.getElementById("home-view");
  if (homeView) {
    const market = document.getElementById("home-market-indices");
    const aiSignals = document.getElementById("home-ai-signals");
    const signalTicker = document.getElementById("home-market-signal-ticker");
    const signalKicker = signalTicker?.querySelector(".home-market-signal-kicker");
    const homeResponse = document.getElementById("home-ai-response");
    const marketTitle = market?.querySelector(".home-flat-section-head h2");
    const marketEyebrow = market?.querySelector(".home-flat-section-head span");
    market?.querySelector("#home-index-shared-asof")?.remove();
    document.getElementById("trend-calendar-window")?.remove();
    if (marketTitle) marketTitle.textContent = "오늘의 시장";
    if (marketEyebrow) marketEyebrow.textContent = "주요 지수";
    if (aiSignals && signalTicker && signalKicker) {
      aiSignals.classList.add("staging-home-signal-section");
      aiSignals.removeAttribute("aria-labelledby");
      aiSignals.setAttribute("aria-label", "최신 AI 시그널");
      signalTicker.classList.add("staging-home-signal-card");
      signalTicker.setAttribute("aria-label", "최신 AI 시그널");
      signalKicker.innerHTML = `
        <span class="staging-home-signal-icon" aria-hidden="true">${svg(icons.ai)}</span>
        <strong>AI 시그널</strong>
        <small data-staging-home-signal-meta>시총 100위내 매매신호를 확인하세요</small>
      `;
      const signalChevron = document.createElement("a");
      signalChevron.className = "staging-home-signal-chevron";
      signalChevron.href = "/dashboard?view=ai-signals";
      signalChevron.dataset.aiSignalListLink = "true";
      signalChevron.setAttribute("aria-label", "AI 시그널 전체 목록 보기");
      signalChevron.innerHTML = svg(icons.chevron);
      signalTicker.appendChild(signalChevron);

    }
    if (homeResponse) {
      const responseSection = document.createElement("section");
      stagingHomeResponseSection = responseSection;
      responseSection.className = "staging-home-response-section";
      responseSection.setAttribute("aria-labelledby", "staging-home-response-title");
      responseSection.hidden = true;
      responseSection.innerHTML = `
        <header class="staging-home-response-head">
          <div class="staging-home-response-heading">
            <div><span>관심종목 기반</span><h2 id="staging-home-response-title">AI 종목 대응</h2></div>
          </div>
        </header>
      `;
      const responseTime = homeResponse.querySelector("#home-ai-response-asof");
      if (responseTime) responseSection.querySelector(".staging-home-response-head")?.appendChild(responseTime);
      homeResponse.querySelector(":scope > header")?.remove();
      homeResponse.setAttribute("aria-labelledby", "staging-home-response-title");
      if (aiSignals) aiSignals.insertAdjacentElement("afterend", responseSection);
      else if (market) market.insertAdjacentElement("afterend", responseSection);
      else homeView.prepend(responseSection);
      responseSection.appendChild(homeResponse);

      const personal = homeResponse.querySelector(".home-ai-response-personal");
      const personalHeader = personal?.querySelector(":scope > header");
      const personalStatus = homeResponse.querySelector("#home-ai-response-summary");
      if (personal) {
        personal.removeAttribute("aria-labelledby");
        personal.setAttribute("aria-label", "종목별 AI 대응");
      }
      if (personalHeader) {
        personalHeader.hidden = true;
        personalHeader.setAttribute("aria-hidden", "true");
      }
      if (personalStatus) personalStatus.setAttribute("aria-hidden", "true");

      const shell = dashboard.querySelector(".shell[data-ui-version='3.0']");
      const serviceFooter = shell?.querySelector(":scope > .service-footer");
      if (shell && !document.getElementById("staging-ai-stock-response-view")) {
        stagingAiStockResponsePage = document.createElement("section");
        stagingAiStockResponsePage.id = "staging-ai-stock-response-view";
        stagingAiStockResponsePage.className = "app-page staging-ai-stock-response-page";
        stagingAiStockResponsePage.hidden = true;
        stagingAiStockResponsePage.setAttribute("aria-labelledby", "staging-ai-stock-response-name");
        stagingAiStockResponsePage.innerHTML = `
          <header class="staging-ai-stock-response-hero">
            <span class="staging-ai-stock-response-eyebrow">AI가 확인한 종목별 대응</span>
            <div class="staging-ai-stock-response-identity">
              <h2 id="staging-ai-stock-response-name" data-staging-response-name>관심종목</h2>
              <span class="staging-ai-stock-response-status" data-staging-response-status>자료 확인 중</span>
            </div>
            <div class="staging-ai-stock-response-time-row">
              <time class="staging-ai-stock-response-updated" data-staging-response-updated>업데이트 확인 중</time>
              <span>자료마다 기준시각이 달라요</span>
            </div>
            <section class="staging-ai-stock-response-live-quote" data-staging-response-live-quote aria-label="현재 주가">
              <dl>
                <div>
                  <dt>현재 주당 가격</dt>
                  <dd data-staging-response-live-price>시세 확인 중</dd>
                </div>
                <div>
                  <dt>오늘 등락률</dt>
                  <dd data-staging-response-live-rate>--</dd>
                </div>
              </dl>
              <p data-staging-response-live-state>실시간 시세 연결 중</p>
              <div class="staging-ai-stock-response-analysis-refresh" data-staging-response-analysis-refresh data-analysis-state="loading">
                <p data-staging-response-analysis-status>설명 기준 가격을 준비하고 있어요.</p>
                <button type="button" data-staging-response-reanalyze disabled aria-busy="true">분석 준비 중</button>
              </div>
            </section>
          </header>
          <section class="staging-ai-stock-response-context" aria-labelledby="staging-ai-stock-response-context-title">
            <span id="staging-ai-stock-response-context-title">이 화면이 열린 이유</span>
            <p data-staging-response-context>최근 시장 이벤트와 이 종목의 연결을 확인했어요.</p>
          </section>
          <section class="staging-ai-stock-response-investor-state" aria-labelledby="staging-ai-stock-response-investor-state-title">
            <header>
              <div>
                <span>내 상황에 맞춰 볼게요</span>
                <h3 id="staging-ai-stock-response-investor-state-title">현재 이 종목을 보유하고 있나요?</h3>
              </div>
              <p>보유 여부와 평균 매수가에 맞춰 확인할 가격이 달라져요.</p>
            </header>
            <div class="staging-ai-stock-response-investor-options" role="group" aria-label="이 종목에 대한 내 상황">
              <button type="button" class="active" aria-pressed="true" data-staging-response-investor-state="not_holding">미보유</button>
              <button type="button" aria-pressed="false" data-staging-response-investor-state="holding">보유 중</button>
            </div>
            <p class="staging-ai-stock-response-investor-note" data-staging-response-investor-note>
              현재 보유하지 않은 상태로, 관망 이유와 매수 전환 조건을 설명해요.
            </p>
            <form class="staging-ai-stock-response-average-price" data-staging-response-average-price-field hidden novalidate>
              <label for="staging-ai-stock-response-average-price">
                <strong>내 평균 매수가</strong>
                <span>현재 손익과 가격별 대응 기준을 계산할 때 사용해요.</span>
              </label>
              <div>
                <span class="staging-ai-stock-response-average-price-control">
                  <input
                    id="staging-ai-stock-response-average-price"
                    type="text"
                    inputmode="decimal"
                    autocomplete="off"
                    placeholder="예: 72,000"
                    aria-describedby="staging-ai-stock-response-average-price-help staging-ai-stock-response-average-price-status"
                    data-staging-response-average-price
                  >
                  <span aria-hidden="true">원</span>
                </span>
                <button type="submit">적용</button>
              </div>
              <p id="staging-ai-stock-response-average-price-help">직접 입력한 값이며 실제 계좌·주문 내역과 자동 연동되지 않아요.</p>
              <p id="staging-ai-stock-response-average-price-status" role="status" aria-live="polite" data-staging-response-average-price-status></p>
            </form>
          </section>
          <section class="staging-ai-stock-response-loader" data-staging-response-loader role="status" aria-live="polite">
            <span class="staging-ai-stock-response-loader-spinner" aria-hidden="true"></span>
            <div>
              <strong>종목 판단을 정리하고 있어요</strong>
              <p data-staging-response-loader-message>6가지 자료를 확인하고 있어요.</p>
            </div>
          </section>
          <section class="staging-ai-stock-response-action" aria-labelledby="staging-ai-stock-response-action-title" aria-describedby="staging-ai-stock-response-disclaimer">
            <div class="staging-page-summary-head">
              <span>쉽게 풀어보면</span>
            </div>
            <h3 id="staging-ai-stock-response-action-title" data-staging-response-action>6가지 자료를 확인하고 있어요</h3>
            <p class="staging-ai-stock-response-summary" data-staging-response-summary>잠시만 기다리면 쉬운 말로 정리해 드릴게요.</p>
            <div class="staging-ai-stock-response-explanation">
              <span>왜 이렇게 보나요?</span>
              <p class="staging-ai-stock-response-reason" data-staging-response-reason>종목별 판단 근거를 연결하고 있습니다.</p>
            </div>
            <dl class="staging-ai-stock-response-overview" aria-label="현재 AI 분석 요약">
              <div>
                <dt>지금 판단</dt>
                <dd><strong data-staging-response-direction>계산 중이에요</strong><small data-staging-response-direction-guide>긍정·주의 신호를 비교하고 있어요</small></dd>
              </div>
              <div>
                <dt>자료가 충분한가요?</dt>
                <dd><strong data-staging-response-data-state>확인 중</strong><small>완성도와 신호 일치 정도</small></dd>
              </div>
              <div>
                <dt>확인한 자료</dt>
                <dd><strong data-staging-response-coverage-label>확인 중</strong><small>가격·외국인/기관·공시·뉴스·리포트·시장</small></dd>
              </div>
            </dl>
            <p class="staging-ai-stock-response-disclaimer" id="staging-ai-stock-response-disclaimer">
              공개 데이터와 직접 입력한 평균 매수가를 바탕으로 한 대응 참고 정보예요. 실제 계좌·주문 내역과 자동 연동되지 않아요.
            </p>
          </section>
          <section class="staging-ai-stock-response-guide" aria-labelledby="staging-ai-stock-response-guide-title">
            <header>
              <span>내 상황별 가격 가이드</span>
              <h3 id="staging-ai-stock-response-guide-title" data-staging-response-guide-title>가격이 내려올 때와 올라갈 때를 나눠 보세요</h3>
              <p data-staging-response-guide-intro>높은 확인선은 바로 사는 가격이 아니며, 눌림목과 상승 흐름을 따로 확인해요.</p>
            </header>
            <section class="staging-ai-stock-response-holding-strategy" data-staging-response-holding-strategy hidden aria-labelledby="staging-ai-stock-response-holding-strategy-title">
              <header>
                <span>입력한 평균가 기준</span>
                <h4 id="staging-ai-stock-response-holding-strategy-title">내 보유 전략 한눈에</h4>
                <strong data-staging-response-holding-stage>보유 기준 확인</strong>
              </header>
              <p data-staging-response-holding-summary>평균 매수가와 현재가를 비교해 보유 기준을 확인해요.</p>
              <dl>
                <div><dt>평균 매수가</dt><dd data-staging-response-holding-average>--</dd></div>
                <div><dt>현재가</dt><dd data-staging-response-holding-current>--</dd></div>
                <div><dt>내 수익률</dt><dd data-staging-response-holding-return>--</dd></div>
                <div><dt>현재 전략</dt><dd data-staging-response-holding-action>보유 기준 확인</dd></div>
              </dl>
            </section>
            <figure class="staging-ai-stock-response-price-map" data-staging-response-price-map hidden>
              <figcaption>
                <span>미보유 가격 지도</span>
                <strong>현재가에서 두 가지 확인 경로를 비교해 보세요</strong>
              </figcaption>
              <div class="staging-ai-stock-response-price-map-plot" data-staging-response-price-map-plot></div>
              <ol>
                <li><strong>① 내려오면</strong><span>눌림목 구간에서 하락이 멈추고 반등하는지 확인해요.</span></li>
                <li><strong>② 올라가면</strong><span>확인선 위에서 장을 마친 뒤 다시 그 가격을 지키는지 확인해요.</span></li>
              </ol>
              <p>미래 가격을 예측한 차트가 아니라, 확인할 가격 위치를 비교한 그림이에요.</p>
            </figure>
            <div class="staging-ai-stock-response-guide-rows" data-staging-response-guide-rows></div>
            <p class="staging-ai-stock-response-guide-note">가격만으로 결정하지 말고 같은 시점의 외국인·기관 매매, 뉴스, 회사 공시, 증권사 리포트를 함께 확인해 주세요.</p>
          </section>
          <section class="staging-ai-stock-response-next" data-staging-response-next hidden aria-labelledby="staging-ai-stock-response-next-title">
            <span>앞으로 볼 것</span>
            <h3 id="staging-ai-stock-response-next-title">앞으로 이렇게 확인하세요</h3>
            <p data-staging-response-next-summary>가격이 내려올 때와 올라갈 때를 나눠 순서대로 확인해요.</p>
            <ol data-staging-response-decision-plan></ol>
          </section>
          <section class="staging-ai-stock-response-warnings" data-staging-response-warnings hidden aria-labelledby="staging-ai-stock-response-warning-title">
            <h3 id="staging-ai-stock-response-warning-title">엇갈리거나 부족한 부분</h3>
            <ul></ul>
            <button type="button" data-staging-response-retry hidden>자료 다시 불러오기</button>
          </section>
          <section class="staging-ai-stock-response-evidence" aria-labelledby="staging-ai-stock-response-evidence-title">
            <header>
              <span>판단 근거</span>
              <h3 id="staging-ai-stock-response-evidence-title">왜 이렇게 봤나요?</h3>
              <p>현재 판단에 크게 반영된 이유부터 보여드려요.</p>
            </header>
            <div class="staging-ai-stock-response-key-reasons" data-staging-response-key-reasons></div>
            <details class="staging-ai-stock-response-all-reasons">
              <summary>6가지 자료 자세히 보기</summary>
              <p>각 점수는 상승 확률이 아니라 자료별 긍정·주의 방향을 비교하기 위한 값이에요.</p>
              <div class="staging-ai-stock-response-metrics" data-staging-response-metrics></div>
            </details>
          </section>
          <details class="staging-ai-stock-response-method">
            <summary>점수와 계산 방법 알아보기</summary>
            <div>
              <dl aria-label="AI 분석 계산 정보">
                <div><dt>AI 전략의 원래 상태</dt><dd data-staging-response-original-stance>계산 중</dd></div>
                <div><dt>분석 점수 (-100~+100)</dt><dd data-staging-response-score>--</dd></div>
                <div><dt>내부 근거 충실도</dt><dd data-staging-response-confidence>--</dd></div>
                <div><dt>반영한 자료</dt><dd data-staging-response-coverage>6개 중 0개</dd></div>
              </dl>
              <p>내부 근거 충실도는 과거 적중률이나 주가 상승 확률이 아니에요. 자료 완성도와 신호가 같은 방향을 가리키는 정도를 함께 나타냅니다.</p>
              <p class="staging-ai-stock-response-lead" data-staging-response-lead>가격 흐름 25 · 외국인·기관 매매 25 · 회사 공시 15 · 뉴스 10 · 증권사 리포트 15 · 시장 환경 10 가중 종합</p>
            </div>
          </details>
          <nav class="staging-ai-stock-response-links" aria-label="종목 추가 확인">
            <a href="/dashboard" data-staging-response-stock-link>종목 상세에서 차트 보기</a>
          </nav>
          <aside class="staging-ai-stock-response-note" aria-label="AI 종목 분석 이용 안내">
            중대 공시는 다른 점수보다 먼저 반영해요. 실제 판단 전 각 자료의 원문과 최신 시세를 다시 확인해 주세요.
          </aside>
          <p class="sr-only" role="status" aria-live="polite" aria-atomic="true" data-staging-response-announcement></p>
        `;
        stagingAiStockResponsePage.addEventListener("click", (event) => {
          const reanalyze = event.target instanceof Element
            ? event.target.closest("[data-staging-response-reanalyze]")
            : null;
          if (reanalyze instanceof HTMLButtonElement) {
            event.preventDefault();
            if (reanalyze.disabled || stagingAiStockResponseReanalysisPending) return;
            const detail = stagingAiStockResponseDetailForRoute();
            if (!detail?.code) return;
            const previousResult = stagingAiStockResponseRenderedResult;
            const previousFailedSources = stagingAiStockResponseRenderedFailedSources;
            stagingAiStockResponseReanalysisPending = true;
            renderStagingAiStockResponseAnalysisStatus();
            renderStagingAiStockResponseLoading(detail);
            void loadStagingAiStockResponse(detail, { force: true }).catch(() => {
              if (stagingAiStockResponsePage?.dataset.responseCode !== String(detail.code)) return;
              stagingAiStockResponseReanalysisPending = false;
              if (previousResult) {
                renderStagingAiStockResponseResult(previousResult, {
                  failedSources: previousFailedSources,
                });
              } else {
                renderStagingAiStockResponseAnalysisStatus();
              }
            });
            return;
          }
          const target = event.target instanceof Element
            ? event.target.closest("[data-staging-response-investor-state]")
            : null;
          if (!(target instanceof HTMLButtonElement)) return;
          const nextState = normalizeStagingAiStockResponseInvestorState(
            target.dataset.stagingResponseInvestorState,
          );
          if (nextState === stagingAiStockResponseSelectedState) return;
          syncStagingAiStockResponseInvestorState(nextState);
          stagingAiStockResponseText("[data-staging-response-average-price-status]", "");
          const code = stagingAiStockResponsePage?.dataset.responseCode || "";
          const investorStateApi = window.SecretNoteWatchlistInvestorState;
          if (typeof investorStateApi?.update === "function") {
            investorStateApi.update(code, nextState);
          }
          if (stagingAiStockResponseRenderedResult) {
            renderStagingAiStockResponseResult(stagingAiStockResponseRenderedResult, {
              failedSources: stagingAiStockResponseRenderedFailedSources,
            });
          } else {
            setStagingAiStockResponseDisplay(
              "loading",
              `내 상황을 ${STAGING_AI_STOCK_RESPONSE_INVESTOR_STATES[nextState].label} 기준으로 반영해 정리하고 있어요.`,
            );
          }
        });
        const averagePriceForm = stagingAiStockResponsePage.querySelector(
          "[data-staging-response-average-price-field]",
        );
        averagePriceForm?.addEventListener("submit", (event) => {
          event.preventDefault();
          const priceInput = stagingAiStockResponsePage?.querySelector(
            "[data-staging-response-average-price]",
          );
          if (!(priceInput instanceof HTMLInputElement)) return;
          const averageBuyPrice = normalizeStagingAiStockResponseAverageBuyPrice(priceInput.value);
          if (averageBuyPrice === null) {
            priceInput.setAttribute("aria-invalid", "true");
            stagingAiStockResponseText(
              "[data-staging-response-average-price-status]",
              "0원보다 큰 평균 매수가를 입력해 주세요.",
            );
            priceInput.focus({ preventScroll: true });
            return;
          }
          priceInput.removeAttribute("aria-invalid");
          stagingAiStockResponseAverageBuyPrice = averageBuyPrice;
          priceInput.value = formatNumber(averageBuyPrice);
          const code = stagingAiStockResponsePage?.dataset.responseCode || "";
          const investorStateApi = window.SecretNoteWatchlistInvestorState;
          if (typeof investorStateApi?.updateAverageBuyPrice === "function") {
            investorStateApi.updateAverageBuyPrice(code, averageBuyPrice);
          }
          syncStagingAiStockResponseInvestorState("holding", averageBuyPrice);
          stagingAiStockResponseText(
            "[data-staging-response-average-price-status]",
            `평균 매수가 ${formatNumber(averageBuyPrice)}원을 반영했어요.`,
          );
          if (stagingAiStockResponseRenderedResult) {
            renderStagingAiStockResponseResult(stagingAiStockResponseRenderedResult, {
              failedSources: stagingAiStockResponseRenderedFailedSources,
            });
          }
        });
        shell.insertBefore(stagingAiStockResponsePage, serviceFooter || null);
      }
    }

    const homeRanking = document.getElementById("home-surge");
    const homeRankingTabs = document.getElementById("home-ranking-category-tabs");
    const homeRankingFilters = document.getElementById("home-surge-sector-filters");
    const homeRankingList = document.getElementById("home-surge-list");
    const homeRankingMore = document.getElementById("home-surge-more");
    const homeRankingHead = homeRanking?.querySelector(".home-surge-head > div");
    const homeRankingTitle = document.getElementById("home-surge-title");
    const homeRankingMeta = document.getElementById("home-surge-meta");
    const homeRankingOrder = ["surge", "volume", "market_cap", "etf", "dividend", "per", "low52", "high52"];

    if (homeRanking) homeRanking.classList.add("staging-home-top50");
    if (homeRankingHead && homeRankingTitle && homeRankingMeta) {
      homeRankingHead.append(homeRankingTitle, homeRankingMeta);
    }
    if (homeRankingTabs) {
      homeRankingTabs.classList.add("staging-primary-tabs");
      homeRankingTabs.dataset.stagingControlLevel = "primary";
      homeRankingTabs.setAttribute("aria-label", "TOP 50 순위 기준 탭");
      for (const category of homeRankingOrder) {
        const tab = homeRankingTabs.querySelector(`[data-home-ranking-category="${category}"]`);
        if (tab) homeRankingTabs.appendChild(tab);
      }
    }
    if (homeRankingFilters) {
      homeRankingFilters.classList.add("staging-filter-chips");
      homeRankingFilters.dataset.stagingControlLevel = "secondary";
      homeRankingFilters.setAttribute("aria-label", "선택한 순위의 세부 필터");
    }
    if (homeRankingMore) {
      homeRankingMore.textContent = "더 보기";
      homeRankingMore.setAttribute("aria-label", "TOP 50 전체 순위 보기");
    }

    const rankingPriceFormatter = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
    const currentHomeRankingItem = (code) => {
      try {
        const items = typeof state === "object" && Array.isArray(state.homeSurgeItems)
          ? state.homeSurgeItems
          : [];
        return items.find((item) => String(item?.code || "") === String(code || "")) || null;
      } catch {
        return null;
      }
    };
    const homeRankingIsWatched = (code) => {
      try {
        return typeof isWatched === "function" && isWatched(code);
      } catch {
        return false;
      }
    };
    const rankingUsdPriceFormatter = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 });
    const rankingPriceText = (value, currency = "KRW") => {
      const number = Number(value);
      if (!Number.isFinite(number)) return "현재가 확인 중";
      return currency === "USD"
        ? `$${rankingUsdPriceFormatter.format(number)}`
        : `${rankingPriceFormatter.format(Math.round(number))}원`;
    };
    const rankingRatePresentation = (value) => {
      const number = value === null || value === undefined || value === "" ? null : Number(value);
      if (!Number.isFinite(number)) return { text: "등락률 확인 중", tone: "neutral" };
      const sign = number > 0 ? "+" : "";
      return {
        text: `${sign}${number.toFixed(2)}%`,
        tone: number > 0 ? "positive" : number < 0 ? "negative" : "neutral",
      };
    };
    const syncHomeRankingHeart = (button, item) => {
      const code = String(item?.code || button.dataset.code || "");
      const name = String(item?.name || button.dataset.name || "종목");
      const market = String(item?.market || button.dataset.market || "");
      const currency = String(item?.currency || button.dataset.currency || "KRW");
      button.dataset.currency = currency;
      button.hidden = currency === "USD";
      button.disabled = currency === "USD";
      if (currency === "USD") {
        button.setAttribute("aria-hidden", "true");
        return;
      }
      button.removeAttribute("aria-hidden");
      const active = homeRankingIsWatched(code);
      button.dataset.code = code;
      button.dataset.name = name;
      button.dataset.market = market;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
      button.setAttribute("aria-label", `${name} 관심종목 ${active ? "해제" : "추가"}`);
      button.title = active ? "관심종목 해제" : "관심종목 추가";
    };
    const syncHomeRankingCard = (card) => {
      const code = card.dataset.code || "";
      const item = currentHomeRankingItem(code);
      const price = card.querySelector(".staging-home-ranking-price");
      const rate = card.querySelector(".staging-home-ranking-rate");
      const heart = card.querySelector(".staging-home-ranking-watch");
      if (item && price) {
        const text = rankingPriceText(item.price, item.currency);
        if (price.textContent !== text) price.textContent = text;
      }
      if (item && rate) {
        const presentation = rankingRatePresentation(item.change_rate);
        if (rate.textContent !== presentation.text) rate.textContent = presentation.text;
        rate.className = `staging-home-ranking-rate ${presentation.tone}`;
      }
      if (heart) syncHomeRankingHeart(heart, item);
    };
    const upgradeHomeRankingRows = () => {
      if (!homeRankingList) return;
      const sourceRows = homeRankingList.querySelectorAll(":scope > a.home-ranking-row");
      for (const sourceRow of sourceRows) {
        const originalClassName = sourceRow.className;
        const code = sourceRow.dataset.code || "";
        const item = currentHomeRankingItem(code);
        const rank = sourceRow.querySelector(".home-surge-rank");
        const identity = sourceRow.querySelector(".home-surge-identity");
        const logo = identity?.querySelector(".stock-list-logo");
        const stockCopy = identity?.querySelector(".stock-list-copy");
        const sourceMetric = sourceRow.querySelector(".ranking-metric-block");
        const fallbackName = stockCopy?.querySelector("strong")?.textContent?.trim() || code || "종목";
        const name = String(item?.name || fallbackName);
        const market = String(item?.market || "");
        const currency = String(item?.currency || "KRW");

        const detail = document.createElement("span");
        detail.className = "staging-home-ranking-copy";
        if (stockCopy) detail.appendChild(stockCopy);
        else detail.appendChild(Object.assign(document.createElement("strong"), { textContent: name }));
        const quote = document.createElement("span");
        quote.className = "staging-home-ranking-quote";
        quote.append(
          Object.assign(document.createElement("span"), { className: "staging-home-ranking-price" }),
          Object.assign(document.createElement("span"), { className: "staging-home-ranking-rate neutral" }),
        );
        detail.appendChild(quote);

        sourceRow.className = "staging-home-ranking-main";
        sourceRow.removeAttribute("data-code");
        sourceRow.setAttribute("aria-label", `${name} 종목 상세 보기`);
        sourceRow.replaceChildren(...[rank, logo, detail].filter(Boolean));

        const card = document.createElement("article");
        card.className = `${originalClassName} staging-home-ranking-row`;
        card.dataset.code = code;
        card.dataset.name = name;
        card.dataset.market = market;
        card.dataset.currency = currency;
        card.classList.toggle("is-us-market", currency === "USD");

        const heart = document.createElement("button");
        heart.className = "staging-home-ranking-watch";
        heart.type = "button";
        heart.innerHTML = svg(icons.interest);

        sourceRow.replaceWith(card);
        card.append(sourceRow);
        if (currency !== "USD") card.append(heart);
        if (sourceMetric) {
          sourceMetric.classList.add("staging-home-ranking-source");
          sourceMetric.hidden = true;
          sourceMetric.setAttribute("aria-hidden", "true");
          card.appendChild(sourceMetric);
        }
        syncHomeRankingCard(card);
      }
      for (const card of homeRankingList.querySelectorAll(":scope > .staging-home-ranking-row")) {
        syncHomeRankingCard(card);
      }
    };
    let homeRankingUpgradeFrame = 0;
    const scheduleHomeRankingUpgrade = () => {
      if (homeRankingUpgradeFrame) return;
      homeRankingUpgradeFrame = window.requestAnimationFrame(() => {
        homeRankingUpgradeFrame = 0;
        upgradeHomeRankingRows();
      });
    };

    if (homeRankingList) {
      const homeRankingObserver = new MutationObserver(scheduleHomeRankingUpgrade);
      homeRankingObserver.observe(homeRankingList, { childList: true, subtree: true });
      homeRankingList.addEventListener("click", (event) => {
        const button = event.target.closest(".staging-home-ranking-watch");
        if (!button || !homeRankingList.contains(button)) return;
        event.preventDefault();
        event.stopPropagation();
        const card = button.closest(".staging-home-ranking-row");
        const item = currentHomeRankingItem(card?.dataset.code || button.dataset.code) || {
          code: button.dataset.code,
          name: button.dataset.name,
          market: button.dataset.market,
        };
        try {
          if (typeof toggleWatchlistItem !== "function") return;
          toggleWatchlistItem(item);
          if (typeof updateWatchButton === "function") updateWatchButton();
          if (typeof updateRecommendationWatchButtons === "function") updateRecommendationWatchButtons();
        } catch {
          return;
        }
        for (const peer of homeRankingList.querySelectorAll(".staging-home-ranking-watch")) {
          if (peer.dataset.code === item.code) syncHomeRankingHeart(peer, item);
        }
      });
      scheduleHomeRankingUpgrade();
    }
    homeRankingTabs?.addEventListener("click", () => {
      window.requestAnimationFrame(() => {
        const selected = homeRankingTabs.querySelector('[aria-selected="true"], .active');
        if (homeRanking && selected?.dataset.homeRankingCategory) {
          homeRanking.dataset.stagingRankingCategory = selected.dataset.homeRankingCategory;
        }
        scheduleHomeRankingUpgrade();
      });
    });
    window.addEventListener("focus", scheduleHomeRankingUpgrade);
    window.addEventListener("storage", scheduleHomeRankingUpgrade);
    window.addEventListener("load", () => {
      const returnTab = homeRankingTabs?.querySelector('[data-home-ranking-category="surge"]');
      if (returnTab && !returnTab.classList.contains("active")) returnTab.click();
      else scheduleHomeRankingUpgrade();
    }, { once: true });

    const hotCommunitySection = document.createElement("section");
    hotCommunitySection.className = "staging-hot-community";
    hotCommunitySection.setAttribute("aria-labelledby", "staging-hot-community-title");
    hotCommunitySection.innerHTML = `
      <header class="staging-hot-community-head">
        <h2 id="staging-hot-community-title">핫한 커뮤니티</h2>
      </header>
      <nav class="staging-hot-community-tabs" role="tablist" aria-label="핫한 커뮤니티 순위 기준">
        <button id="staging-hot-community-surge-tab" class="active" type="button" role="tab" aria-selected="true" aria-controls="staging-hot-community-panel" data-hot-community-mode="surge">수익률 순</button>
        <button id="staging-hot-community-market-cap-tab" type="button" role="tab" aria-selected="false" aria-controls="staging-hot-community-panel" tabindex="-1" data-hot-community-mode="market_cap">시총 순</button>
      </nav>
      <div class="staging-hot-community-panel" id="staging-hot-community-panel" role="tabpanel" aria-labelledby="staging-hot-community-surge-tab" aria-live="polite">
        <div class="staging-hot-community-stocks" data-staging-hot-community-stocks aria-label="상위 15개 종목"></div>
        <div class="staging-hot-community-posts" data-staging-hot-community-posts aria-live="polite"></div>
        <button class="staging-hot-community-more" type="button" data-staging-hot-community-more disabled>
          <span>커뮤니티 더 보기</span><i aria-hidden="true">${svg(icons.chevron)}</i>
        </button>
      </div>
    `;
    const trendView = document.getElementById("trend-view");
    if (homeRanking) homeRanking.insertAdjacentElement("afterend", hotCommunitySection);
    else if (trendView) trendView.insertAdjacentElement("beforebegin", hotCommunitySection);
    else homeView.appendChild(hotCommunitySection);

    const hotCommunityState = {
      mode: "surge",
      selectedCode: "",
      rankings: new Map(),
      feeds: new Map(),
      feedPromises: new Map(),
      rankingRequestId: 0,
      feedRequestId: 0,
      rotationTimer: 0,
      railVisible: false,
      pointerStartX: null,
    };
    const hotCommunityStocks = hotCommunitySection.querySelector("[data-staging-hot-community-stocks]");
    const hotCommunityPosts = hotCommunitySection.querySelector("[data-staging-hot-community-posts]");
    const hotCommunityPanel = hotCommunitySection.querySelector("#staging-hot-community-panel");
    const hotCommunityMore = hotCommunitySection.querySelector("[data-staging-hot-community-more]");
    const hotCommunityCompactNumber = new Intl.NumberFormat("ko-KR", {
      notation: "compact",
      maximumFractionDigits: 1,
    });

    const hotCommunityRequest = async (url) => {
      for (let attempt = 0; attempt < 20; attempt += 1) {
        if (typeof fetchJsonCached === "function") {
          return fetchJsonCached(url, { ttlMs: 60_000, timeoutMs: 20_000 });
        }
        await new Promise((resolve) => window.setTimeout(resolve, 25));
      }
      throw new Error("community data client unavailable");
    };
    const hotCommunityDate = (value, options = {}) => {
      if (!value) return options.fallback || "";
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return options.fallback || "";
      if (options.timeOnly) {
        return `${new Intl.DateTimeFormat("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }).format(parsed)} 기준`;
      }
      const elapsed = Math.max(0, Date.now() - parsed.getTime());
      const minute = 60_000;
      if (elapsed < minute) return "방금 전";
      if (elapsed < 60 * minute) return `${Math.max(1, Math.floor(elapsed / minute))}분 전`;
      if (elapsed < 24 * 60 * minute) return `${Math.floor(elapsed / (60 * minute))}시간 전`;
      if (elapsed < 7 * 24 * 60 * minute) return `${Math.floor(elapsed / (24 * 60 * minute))}일 전`;
      return new Intl.DateTimeFormat("ko-KR", { month: "numeric", day: "numeric" }).format(parsed);
    };
    const hotCommunityMetric = (item, mode = hotCommunityState.mode) => {
      if (mode === "market_cap") {
        const marketCap = Number(item?.market_cap);
        return Number.isFinite(marketCap) ? `시총 ${hotCommunityCompactNumber.format(marketCap)}원` : "시총 확인 중";
      }
      const rate = Number(item?.change_rate);
      if (!Number.isFinite(rate)) return "수익률 확인 중";
      return `${rate > 0 ? "+" : ""}${rate.toFixed(2)}%`;
    };
    const hotCommunityTone = (item, mode = hotCommunityState.mode) => {
      if (mode === "market_cap") return "neutral";
      const rate = Number(item?.change_rate);
      return rate > 0 ? "positive" : rate < 0 ? "negative" : "neutral";
    };
    const hotCommunityItems = () => hotCommunityState.rankings.get(hotCommunityState.mode)?.items || [];
    const hotCommunitySelectedItem = () => hotCommunityItems().find(
      (item) => String(item?.code || "") === hotCommunityState.selectedCode,
    ) || null;
    const HOT_COMMUNITY_ROTATION_MS = 5_000;
    const hotCommunityReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)") || null;
    const clearHotCommunityRotation = () => {
      if (hotCommunityState.rotationTimer) {
        window.clearTimeout(hotCommunityState.rotationTimer);
        hotCommunityState.rotationTimer = 0;
      }
    };
    const hotCommunityCanRotate = () => (
      !document.hidden
      && (document.body.dataset.view || "home") === "home"
      && hotCommunityState.railVisible
      && hotCommunityItems().length > 1
      && !hotCommunityReducedMotion?.matches
    );
    const scheduleHotCommunityRotation = () => {
      clearHotCommunityRotation();
      const canRotate = hotCommunityCanRotate();
      hotCommunitySection.dataset.autoAdvance = canRotate ? "scheduled" : "paused";
      hotCommunitySection.dataset.autoAdvanceMs = String(HOT_COMMUNITY_ROTATION_MS);
      if (!canRotate) return;
      hotCommunityState.rotationTimer = window.setTimeout(() => {
        hotCommunityState.rotationTimer = 0;
        const items = hotCommunityItems();
        const currentIndex = items.findIndex(
          (item) => String(item?.code || "") === hotCommunityState.selectedCode,
        );
        const nextItem = items[(Math.max(-1, currentIndex) + 1) % items.length];
        if (!nextItem) {
          scheduleHotCommunityRotation();
          return;
        }
        hotCommunitySection.dataset.autoAdvanceCount = String(
          Number(hotCommunitySection.dataset.autoAdvanceCount || 0) + 1,
        );
        selectHotCommunityItem(nextItem, { source: "auto", scrollBehavior: "smooth" });
      }, HOT_COMMUNITY_ROTATION_MS);
    };
    syncHotCommunityRotation = scheduleHotCommunityRotation;
    let hotCommunityQuoteScopeSignature = "";
    const updateHotCommunityQuote = (code, quote = {}) => {
      const normalizedCode = String(code || "");
      if (!normalizedCode || !quote) return;
      let changed = false;
      for (const ranking of hotCommunityState.rankings.values()) {
        const item = (ranking?.items || []).find((entry) => String(entry?.code || "") === normalizedCode);
        if (!item) continue;
        for (const field of ["price", "change_rate", "volume", "trading_value", "market_cap"]) {
          if (quote[field] === null || quote[field] === undefined || quote[field] === "") continue;
          item[field] = quote[field];
          changed = true;
        }
      }
      if (!changed || !hotCommunityStocks) return;
      for (const button of hotCommunityStocks.querySelectorAll("[data-hot-community-code]")) {
        if (button.dataset.hotCommunityCode !== normalizedCode) continue;
        const item = hotCommunityItems().find((entry) => String(entry?.code || "") === normalizedCode);
        const metric = button.querySelector("[data-hot-community-live-metric]");
        if (!item || !metric) continue;
        metric.className = hotCommunityTone(item);
        metric.textContent = hotCommunityMetric(item);
        button.setAttribute(
          "aria-label",
          `${button.querySelector(".staging-hot-community-rank")?.textContent || ""}위 ${item.name || normalizedCode}, ${hotCommunityMetric(item)} 커뮤니티 최신글 보기`,
        );
        metric.classList.remove("is-live-updated");
        window.requestAnimationFrame(() => metric.classList.add("is-live-updated"));
      }
      hotCommunitySection.dataset.liveQuoteState = "updating";
      hotCommunitySection.dataset.liveQuoteUpdates = String(Number(hotCommunitySection.dataset.liveQuoteUpdates || 0) + 1);
    };
    syncHotCommunityQuoteScope = () => {
      const active = !document.hidden && (document.body.dataset.view || "") === "home";
      const items = active ? hotCommunityItems().slice(0, 15) : [];
      const signature = `${active ? hotCommunityState.mode : "off"}:${items.map((item) => item.code).join(",")}`;
      if (signature === hotCommunityQuoteScopeSignature) return;
      hotCommunityQuoteScopeSignature = signature;
      hotCommunitySection.dataset.liveQuoteState = items.length ? "subscribing" : "idle";
      hotCommunitySection.dataset.liveQuoteCount = String(items.length);
      if (typeof replaceQuoteStreamScope !== "function") return;
      replaceQuoteStreamScope("staging-hot-community", items.map((item) => ({
        code: String(item.code),
        handlers: {
          onStatus: () => {
            hotCommunitySection.dataset.liveQuoteState = "connected";
          },
          onQuote: (payload) => updateHotCommunityQuote(item.code, payload.quote),
        },
      })));
    };

    const renderHotCommunityStockLoading = () => {
      clearHotCommunityRotation();
      hotCommunityPanel?.setAttribute("aria-busy", "true");
      if (hotCommunityStocks) {
        hotCommunityStocks.innerHTML = `
          <div class="staging-hot-community-stock-skeleton is-wide" aria-hidden="true"></div>
          <div class="staging-hot-community-stock-skeleton" aria-hidden="true"></div>
          <div class="staging-hot-community-stock-skeleton" aria-hidden="true"></div>
          <div class="staging-hot-community-stock-skeleton" aria-hidden="true"></div>
        `;
      }
      if (hotCommunityPosts) {
        hotCommunityPosts.innerHTML = `
          <p class="staging-hot-community-status" role="status">상위 종목을 불러오고 있어요.</p>
        `;
      }
      if (hotCommunityMore) hotCommunityMore.disabled = true;
    };
    const renderHotCommunityStockError = () => {
      clearHotCommunityRotation();
      hotCommunityPanel?.setAttribute("aria-busy", "false");
      hotCommunityStocks?.replaceChildren();
      if (hotCommunityPosts) {
        hotCommunityPosts.innerHTML = `
          <div class="staging-hot-community-status is-error" role="status">
            <strong>종목 순위를 불러오지 못했어요.</strong>
            <button type="button" data-hot-community-retry="ranking">다시 불러오기</button>
          </div>
        `;
      }
      if (hotCommunityMore) hotCommunityMore.disabled = true;
    };
    const syncHotCommunityStockSelection = (options = {}) => {
      if (!hotCommunityStocks) return;
      let activeStock = null;
      for (const button of hotCommunityStocks.querySelectorAll("[data-hot-community-code]")) {
        const selected = button.dataset.hotCommunityCode === hotCommunityState.selectedCode;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-pressed", String(selected));
        if (selected) activeStock = button;
      }
      const selectedCode = hotCommunityState.selectedCode;
      const revealActiveStock = (behavior = "auto") => {
        if (!(activeStock instanceof HTMLElement)) return;
        if (hotCommunityState.selectedCode !== selectedCode || !activeStock.classList.contains("active")) return;
        const railRect = hotCommunityStocks.getBoundingClientRect();
        const activeRect = activeStock.getBoundingClientRect();
        const edgeInset = 20;
        let targetLeft = hotCommunityStocks.scrollLeft;
        if (activeRect.left < railRect.left + edgeInset) {
          targetLeft -= (railRect.left + edgeInset) - activeRect.left;
        } else if (activeRect.right > railRect.right - edgeInset) {
          targetLeft += activeRect.right - (railRect.right - edgeInset);
        }
        const maxLeft = Math.max(0, hotCommunityStocks.scrollWidth - hotCommunityStocks.clientWidth);
        targetLeft = Math.min(maxLeft, Math.max(0, targetLeft));
        if (Math.abs(targetLeft - hotCommunityStocks.scrollLeft) < 1) return;
        hotCommunityStocks.scrollTo({
          left: Math.round(targetLeft),
          top: hotCommunityStocks.scrollTop,
          behavior: hotCommunityReducedMotion?.matches ? "auto" : behavior,
        });
      };
      window.requestAnimationFrame(() => {
        revealActiveStock(options.scrollBehavior || "auto");
        window.setTimeout(() => revealActiveStock("auto"), 320);
      });
    };
    const renderHotCommunityStocks = (options = {}) => {
      if (!hotCommunityStocks) return;
      const items = hotCommunityItems();
      hotCommunityStocks.replaceChildren();
      if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "staging-hot-community-status";
        empty.textContent = "현재 표시할 상위 종목이 없어요.";
        hotCommunityStocks.appendChild(empty);
        return;
      }
      for (const [index, item] of items.entries()) {
        const code = String(item?.code || "");
        const name = String(item?.name || code || "종목");
        const selected = code === hotCommunityState.selectedCode;
        const button = document.createElement("button");
        button.type = "button";
        button.className = `staging-hot-community-stock${selected ? " active" : ""}`;
        button.dataset.hotCommunityCode = code;
        button.setAttribute("aria-pressed", String(selected));
        button.setAttribute("aria-label", `${index + 1}위 ${name}, ${hotCommunityMetric(item)} 커뮤니티 최신글 보기`);
        const rank = document.createElement("span");
        rank.className = "staging-hot-community-rank";
        rank.textContent = String(index + 1);
        rank.setAttribute("aria-hidden", "true");
        button.append(rank, createStockLogoFrame(code, "staging-hot-community-logo"));
        const copy = document.createElement("span");
        copy.className = "staging-hot-community-stock-copy";
        const stockName = document.createElement("strong");
        stockName.textContent = name;
        const metric = document.createElement("small");
        metric.dataset.hotCommunityLiveMetric = code;
        metric.className = hotCommunityTone(item);
        metric.textContent = hotCommunityMetric(item);
        copy.append(stockName, metric);
        button.appendChild(copy);
        hotCommunityStocks.appendChild(button);
      }
      syncHotCommunityStockSelection(options);
      syncHotCommunityQuoteScope();
    };
    const renderHotCommunityFeedStatus = (message, options = {}) => {
      if (!hotCommunityPosts) return;
      hotCommunityPosts.replaceChildren();
      const status = document.createElement("div");
      status.className = `staging-hot-community-status${options.error ? " is-error" : ""}`;
      status.setAttribute("role", "status");
      const strong = document.createElement("strong");
      strong.textContent = message;
      status.appendChild(strong);
      if (options.retry) {
        const retry = document.createElement("button");
        retry.type = "button";
        retry.dataset.hotCommunityRetry = "feed";
        retry.textContent = "다시 불러오기";
        status.appendChild(retry);
      }
      hotCommunityPosts.appendChild(status);
    };
    const renderHotCommunityPosts = (payload = {}) => {
      if (!hotCommunityPosts) return;
      const providers = Array.isArray(payload?.providers) ? payload.providers : [];
      const provider = providers.find((entry) => entry?.key === "naver_board" && entry?.items?.length)
        || providers.find((entry) => Array.isArray(entry?.items) && entry.items.length);
      const rows = Array.isArray(provider?.items)
        ? [...provider.items]
          .sort((left, right) => new Date(right?.created_at || 0) - new Date(left?.created_at || 0))
          .slice(0, 3)
        : [];
      hotCommunityPosts.replaceChildren();
      if (!rows.length) {
        const selectedName = hotCommunitySelectedItem()?.name || payload?.name || "선택한 종목";
        renderHotCommunityFeedStatus(`${selectedName}의 최근 커뮤니티 글이 아직 없어요.`);
        return;
      }
      const list = document.createElement("ul");
      list.className = "staging-hot-community-post-list";
      for (const row of rows) {
        const item = document.createElement("li");
        const target = row?.url ? document.createElement("a") : document.createElement("button");
        target.className = "staging-hot-community-post";
        if (target instanceof HTMLAnchorElement) {
          target.href = row.url;
          target.target = "_blank";
          target.rel = "noopener noreferrer";
        } else {
          target.type = "button";
          target.dataset.hotCommunityOpen = "selected";
        }
        const body = document.createElement("span");
        body.className = "staging-hot-community-post-body";
        const copy = document.createElement("strong");
        copy.textContent = String(row?.text || row?.title || "게시물 내용을 확인해보세요.").replace(/\s+/g, " ").trim();
        const meta = document.createElement("span");
        meta.className = "staging-hot-community-post-meta";
        const avatar = document.createElement("span");
        avatar.className = "staging-hot-community-post-avatar";
        const author = String(row?.author_name || row?.username || "커뮤니티").trim();
        avatar.textContent = author.slice(0, 1) || "커";
        if (row?.author_profile_image_url) {
          const image = document.createElement("img");
          image.src = row.author_profile_image_url;
          image.alt = "";
          image.loading = "lazy";
          image.referrerPolicy = "no-referrer";
          image.addEventListener("error", () => image.remove(), { once: true });
          avatar.appendChild(image);
        }
        const metaText = document.createElement("small");
        metaText.textContent = `${author} · ${hotCommunityDate(row?.created_at, { fallback: "최근" })}`;
        meta.append(avatar, metaText);
        body.append(copy, meta);
        target.setAttribute("aria-label", `${copy.textContent}, ${metaText.textContent}`);
        target.append(body);
        item.appendChild(target);
        list.appendChild(item);
      }
      hotCommunityPosts.appendChild(list);
      hotCommunityPosts.classList.remove("is-changing");
      window.requestAnimationFrame(() => hotCommunityPosts.classList.add("is-changing"));
    };
    const openHotCommunityDetail = async () => {
      const selected = hotCommunitySelectedItem();
      if (!selected?.code) return;
      const code = String(selected.code);
      const activateCommunity = () => {
        const tab = document.querySelector('#stock-view [data-stock-tab="community"]');
        if (tab instanceof HTMLButtonElement) tab.click();
      };
      if (typeof navigateToStock === "function") {
        try {
          await navigateToStock(code, `/dashboard/${encodeURIComponent(code)}`);
          window.setTimeout(activateCommunity, 0);
          return;
        } catch {
          // Fall through to a full route change if the in-app router is unavailable.
        }
      }
      window.location.assign(`/dashboard/${encodeURIComponent(code)}#stock-community-section`);
    };
    const fetchHotCommunityFeed = (code, options = {}) => {
      const normalizedCode = String(code || "");
      if (!normalizedCode) return Promise.reject(new Error("missing stock code"));
      if (!options.force && hotCommunityState.feeds.has(normalizedCode)) {
        return Promise.resolve(hotCommunityState.feeds.get(normalizedCode));
      }
      if (!options.force && hotCommunityState.feedPromises.has(normalizedCode)) {
        return hotCommunityState.feedPromises.get(normalizedCode);
      }
      const request = hotCommunityRequest(`/stocks/${encodeURIComponent(normalizedCode)}/community-feed?limit=5`)
        .then((payload) => {
          hotCommunityState.feeds.set(normalizedCode, payload);
          return payload;
        })
        .finally(() => {
          if (hotCommunityState.feedPromises.get(normalizedCode) === request) {
            hotCommunityState.feedPromises.delete(normalizedCode);
          }
        });
      hotCommunityState.feedPromises.set(normalizedCode, request);
      return request;
    };
    const prefetchHotCommunityFeeds = (items = hotCommunityItems()) => {
      for (const item of items) {
        const code = String(item?.code || "");
        if (!code || code === hotCommunityState.selectedCode || hotCommunityState.feeds.has(code)) continue;
        void fetchHotCommunityFeed(code).catch(() => {});
      }
    };
    const loadHotCommunityFeed = async (item, options = {}) => {
      const code = String(item?.code || "");
      if (!code) return;
      const requestId = ++hotCommunityState.feedRequestId;
      if (hotCommunityMore) hotCommunityMore.disabled = false;
      if (hotCommunityPosts) hotCommunityPosts.setAttribute("aria-live", options.announce ? "polite" : "off");
      if (!options.force && hotCommunityState.feeds.has(code)) {
        renderHotCommunityPosts(hotCommunityState.feeds.get(code));
        hotCommunityPanel?.setAttribute("aria-busy", "false");
        return;
      }
      hotCommunityPanel?.setAttribute("aria-busy", "true");
      renderHotCommunityFeedStatus(`${item?.name || "선택한 종목"}의 최신글을 불러오고 있어요.`);
      try {
        const payload = await fetchHotCommunityFeed(code, options);
        if (requestId !== hotCommunityState.feedRequestId || code !== hotCommunityState.selectedCode) return;
        renderHotCommunityPosts(payload);
      } catch {
        if (requestId !== hotCommunityState.feedRequestId || code !== hotCommunityState.selectedCode) return;
        renderHotCommunityFeedStatus("최신글을 불러오지 못했어요.", { error: true, retry: true });
      } finally {
        if (requestId === hotCommunityState.feedRequestId) hotCommunityPanel?.setAttribute("aria-busy", "false");
      }
    };
    const selectHotCommunityItem = (item, options = {}) => {
      const code = String(item?.code || "");
      if (!code) return;
      hotCommunityState.selectedCode = code;
      syncHotCommunityStockSelection({ scrollBehavior: options.scrollBehavior || "smooth" });
      void loadHotCommunityFeed(item, { announce: options.source === "user" });
      scheduleHotCommunityRotation();
    };
    const loadHotCommunityRankings = async (mode = hotCommunityState.mode, options = {}) => {
      clearHotCommunityRotation();
      hotCommunityState.mode = mode === "market_cap" ? "market_cap" : "surge";
      const requestId = ++hotCommunityState.rankingRequestId;
      const cached = hotCommunityState.rankings.get(hotCommunityState.mode);
      if (!options.force && cached) {
        const items = cached.items || [];
        hotCommunityState.selectedCode = items.some((item) => String(item?.code || "") === hotCommunityState.selectedCode)
          ? hotCommunityState.selectedCode
          : String(items[0]?.code || "");
        renderHotCommunityStocks();
        const selected = hotCommunitySelectedItem();
        if (selected) void loadHotCommunityFeed(selected);
        else renderHotCommunityFeedStatus("현재 표시할 상위 종목이 없어요.");
        prefetchHotCommunityFeeds(items);
        scheduleHotCommunityRotation();
        return;
      }
      renderHotCommunityStockLoading();
      try {
        const modeQuery = hotCommunityState.mode === "surge" ? "&mode=daily" : "";
        const payload = await hotCommunityRequest(`/market/rankings?category=${hotCommunityState.mode}${modeQuery}&limit=15`);
        if (requestId !== hotCommunityState.rankingRequestId || hotCommunityState.mode !== mode) return;
        const items = (Array.isArray(payload?.items) ? payload.items : [])
          .filter((item) => item?.code && item?.name)
          .slice(0, 15);
        hotCommunityState.rankings.set(hotCommunityState.mode, { ...payload, items });
        hotCommunityState.selectedCode = items.some((item) => String(item?.code || "") === hotCommunityState.selectedCode)
          ? hotCommunityState.selectedCode
          : String(items[0]?.code || "");
        renderHotCommunityStocks();
        const selected = hotCommunitySelectedItem();
        if (selected) void loadHotCommunityFeed(selected);
        else renderHotCommunityFeedStatus("현재 표시할 상위 종목이 없어요.");
        prefetchHotCommunityFeeds(items);
        scheduleHotCommunityRotation();
      } catch {
        if (requestId === hotCommunityState.rankingRequestId) renderHotCommunityStockError();
      }
    };

    hotCommunitySection.addEventListener("click", (event) => {
      const modeTab = event.target instanceof Element ? event.target.closest("[data-hot-community-mode]") : null;
      if (modeTab instanceof HTMLButtonElement) {
        const mode = modeTab.dataset.hotCommunityMode === "market_cap" ? "market_cap" : "surge";
        for (const tab of hotCommunitySection.querySelectorAll("[data-hot-community-mode]")) {
          const selected = tab === modeTab;
          tab.classList.toggle("active", selected);
          tab.setAttribute("aria-selected", String(selected));
          tab.tabIndex = selected ? 0 : -1;
        }
        if (hotCommunityPanel) hotCommunityPanel.setAttribute("aria-labelledby", modeTab.id);
        void loadHotCommunityRankings(mode);
        return;
      }
      const stockButton = event.target instanceof Element ? event.target.closest("[data-hot-community-code]") : null;
      if (stockButton instanceof HTMLButtonElement) {
        const code = String(stockButton.dataset.hotCommunityCode || "");
        const item = hotCommunityItems().find((entry) => String(entry?.code || "") === code);
        if (!item) return;
        if (code === hotCommunityState.selectedCode) {
          scheduleHotCommunityRotation();
          return;
        }
        selectHotCommunityItem(item, { source: "user", scrollBehavior: "smooth" });
        return;
      }
      const retry = event.target instanceof Element ? event.target.closest("[data-hot-community-retry]") : null;
      if (retry instanceof HTMLButtonElement) {
        if (retry.dataset.hotCommunityRetry === "ranking") void loadHotCommunityRankings(hotCommunityState.mode, { force: true });
        else {
          const selected = hotCommunitySelectedItem();
          if (selected) void loadHotCommunityFeed(selected, { force: true });
        }
        return;
      }
      const detail = event.target instanceof Element
        ? event.target.closest("[data-staging-hot-community-more], [data-hot-community-open]")
        : null;
      if (detail instanceof HTMLButtonElement) void openHotCommunityDetail();
    });

    hotCommunityStocks?.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const items = hotCommunityItems();
      if (items.length < 2) return;
      event.preventDefault();
      const focusedButton = event.target instanceof Element
        ? event.target.closest("[data-hot-community-code]")
        : null;
      const focusedCode = focusedButton instanceof HTMLButtonElement
        ? String(focusedButton.dataset.hotCommunityCode || "")
        : hotCommunityState.selectedCode;
      const currentIndex = items.findIndex((item) => String(item?.code || "") === focusedCode);
      const delta = event.key === "ArrowRight" ? 1 : -1;
      const nextItem = items[(Math.max(0, currentIndex) + delta + items.length) % items.length];
      if (!nextItem) return;
      selectHotCommunityItem(nextItem, { source: "user", scrollBehavior: "smooth" });
      window.requestAnimationFrame(() => {
        hotCommunityStocks.querySelector(`[data-hot-community-code="${CSS.escape(String(nextItem.code))}"]`)?.focus();
      });
    });
    hotCommunityStocks?.addEventListener("pointerdown", (event) => {
      hotCommunityState.pointerStartX = Number(event.clientX);
      clearHotCommunityRotation();
    }, { passive: true });
    hotCommunityStocks?.addEventListener("pointerup", (event) => {
      const startX = hotCommunityState.pointerStartX;
      hotCommunityState.pointerStartX = null;
      const distance = Number(event.clientX) - Number(startX);
      if (!Number.isFinite(startX) || Math.abs(distance) < 42) {
        scheduleHotCommunityRotation();
        return;
      }
      const items = hotCommunityItems();
      const currentIndex = items.findIndex(
        (item) => String(item?.code || "") === hotCommunityState.selectedCode,
      );
      const delta = distance < 0 ? 1 : -1;
      const nextItem = items[(Math.max(0, currentIndex) + delta + items.length) % items.length];
      if (nextItem) selectHotCommunityItem(nextItem, { source: "user", scrollBehavior: "smooth" });
      else scheduleHotCommunityRotation();
    }, { passive: true });
    hotCommunityStocks?.addEventListener("pointercancel", () => {
      hotCommunityState.pointerStartX = null;
      scheduleHotCommunityRotation();
    }, { passive: true });

    if ("IntersectionObserver" in window) {
      const hotCommunityObserver = new IntersectionObserver((entries) => {
        hotCommunityState.railVisible = entries.some(
          (entry) => entry.isIntersecting && entry.intersectionRatio >= 0.3,
        );
        scheduleHotCommunityRotation();
      }, { threshold: [0, 0.3, 0.75] });
      hotCommunityObserver.observe(hotCommunitySection);
    } else {
      hotCommunityState.railVisible = true;
    }
    hotCommunityReducedMotion?.addEventListener?.("change", scheduleHotCommunityRotation);
    window.setTimeout(() => void loadHotCommunityRankings("surge"), 0);
  }

  const decorateHomeAiStockResponseRows = () => {
    const list = document.getElementById("home-ai-response-personal-list");
    const rows = Array.from(list?.querySelectorAll(".home-ai-interest-row") || []);
    if (stagingHomeResponseSection) {
      stagingHomeResponseSection.hidden = rows.length === 0;
      stagingHomeResponseSection.dataset.responseCount = String(rows.length);
    }
    for (const row of rows) {
      const detail = stagingAiStockResponseDetailFromRow(row);
      if (!detail) continue;
      row.dataset.stagingAiResponseLink = "true";
      row.dataset.stagingResponseCode = detail.code;
      row.setAttribute("aria-label", `${detail.name} AI 종목 대응 보기`);
      if (
        stagingAiStockResponseRouteActive()
        && !stagingAiStockResponsePage?.hidden
        && stagingAiStockResponsePage?.dataset.responseCode === detail.code
      ) {
        storeStagingAiStockResponseDetail(detail);
        stagingAiStockResponseText("[data-staging-response-context]", stagingAiStockResponseContext(detail));
        if (
          stagingAiStockResponsePage?.dataset.responseLoaded !== "true"
          && stagingAiStockResponsePage?.getAttribute("aria-busy") !== "true"
        ) {
          renderStagingAiStockResponseLoading(detail);
          void loadStagingAiStockResponse(detail);
        }
      }
    }
    restoreStagingAiStockResponseTriggerFocus();
  };

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const row = target?.closest(
      "#home-ai-response-personal-list .home-ai-interest-row[data-staging-ai-response-link='true']",
    );
    if (!(row instanceof HTMLAnchorElement)) return;
    const detail = stagingAiStockResponseDetailFromRow(row);
    if (!detail) return;
    event.preventDefault();
    stagingAiStockResponseTrigger = row;
    stagingAiStockResponseTriggerCode = detail.code;
    openStagingAiStockResponse(detail);
  }, true);

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const retry = target?.closest("[data-staging-response-retry]");
    if (!(retry instanceof HTMLButtonElement)) return;
    event.preventDefault();
    const detail = stagingAiStockResponseDetailForRoute();
    if (!detail?.code) return;
    renderStagingAiStockResponseLoading(detail);
    void loadStagingAiStockResponse(detail, { force: true });
  });

  const upgradePreopenMarketCharts = () => {
    const carousel = document.getElementById("home-market-carousel");
    if (!carousel || typeof marketIndexChartMarkup !== "function") return;
    let marketItems = [];
    try {
      marketItems = typeof state === "object" && Array.isArray(state.homeMarketIndexItems)
        ? state.homeMarketIndexItems
        : [];
    } catch {
      marketItems = [];
    }
    const marketItemsByCode = new Map(
      marketItems.map((item) => [String(item?.code || ""), item]),
    );
    for (const card of carousel.querySelectorAll(".home-index-card.is-preopen")) {
      const chartNode = card.querySelector(".home-index-chart");
      if (!chartNode || chartNode.querySelector("svg")) continue;
      const item = marketItemsByCode.get(String(card.dataset.code || ""));
      if (!item) continue;
      const chartMarkup = marketIndexChartMarkup(item);
      if (!chartMarkup) continue;
      chartNode.innerHTML = chartMarkup;
      chartNode.classList.add("staging-preopen-chart");
      chartNode.removeAttribute("aria-hidden");
      chartNode.setAttribute("role", "img");
      const label = card.querySelector("h2")?.textContent?.trim()
        || card.dataset.code
        || "시장 지수";
      chartNode.setAttribute("aria-label", `${label} 직전 거래일 차트`);
    }
  };

  const homeMarketMarquee = {
    frame: 0,
    lastTime: 0,
    cycleAt: 0,
    position: 0,
    signature: "",
    pausedUntil: 0,
    visible: true,
  };
  const homeMarketReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  const pauseHomeMarketMarquee = (duration = 3600) => {
    homeMarketMarquee.pausedUntil = Math.max(homeMarketMarquee.pausedUntil, performance.now() + duration);
  };
  const tickHomeMarketMarquee = (time) => {
    const carousel = document.getElementById("home-market-carousel");
    const elapsed = homeMarketMarquee.lastTime ? Math.min(40, time - homeMarketMarquee.lastTime) : 0;
    homeMarketMarquee.lastTime = time;
    const canMove = carousel
      && document.body.dataset.view === "home"
      && !document.hidden
      && homeMarketMarquee.visible
      && !carousel.classList.contains("is-auto-scrolling")
      && !carousel.querySelector(":scope > .home-market-track")
      && !homeMarketReducedMotion?.matches
      && time >= homeMarketMarquee.pausedUntil
      && homeMarketMarquee.cycleAt > carousel.clientWidth;
    if (canMove && elapsed) {
      homeMarketMarquee.position += elapsed * 0.018;
      if (homeMarketMarquee.position >= homeMarketMarquee.cycleAt) {
        homeMarketMarquee.position -= homeMarketMarquee.cycleAt;
      }
      carousel.scrollLeft = homeMarketMarquee.position;
    }
    homeMarketMarquee.frame = window.requestAnimationFrame(tickHomeMarketMarquee);
  };
  const syncHomeMarketMarquee = () => {
    const carousel = document.getElementById("home-market-carousel");
    if (!carousel) return;
    const mainTrack = carousel.querySelector(":scope > .home-market-track");
    if (carousel.classList.contains("is-auto-scrolling") || mainTrack) {
      carousel.querySelectorAll(":scope > [data-marquee-clone]").forEach((clone) => clone.remove());
      window.cancelAnimationFrame(homeMarketMarquee.frame);
      homeMarketMarquee.frame = 0;
      homeMarketMarquee.lastTime = 0;
      homeMarketMarquee.cycleAt = 0;
      homeMarketMarquee.position = 0;
      homeMarketMarquee.signature = "";
      return;
    }
    const originals = [...carousel.querySelectorAll(":scope > .home-index-card:not([data-marquee-clone])")];
    const signature = originals.map((card) => `${card.dataset.code}:${card.textContent.trim()}`).join("|");
    const existingClones = [...carousel.querySelectorAll(":scope > [data-marquee-clone]")];
    if (!originals.length) return;
    if (
      signature === homeMarketMarquee.signature
      && existingClones.length === originals.length
    ) return;
    const previousProgress = homeMarketMarquee.cycleAt > 0
      ? carousel.scrollLeft % homeMarketMarquee.cycleAt
      : carousel.scrollLeft;
    existingClones.forEach((clone) => clone.remove());
    homeMarketMarquee.signature = signature;
    const clones = originals.map((card) => {
      const clone = card.cloneNode(true);
      clone.dataset.marqueeClone = "true";
      clone.setAttribute("aria-hidden", "true");
      clone.inert = true;
      return clone;
    });
    carousel.append(...clones);
    homeMarketMarquee.cycleAt = clones[0]
      ? clones[0].offsetLeft - originals[0].offsetLeft
      : 0;
    if (homeMarketMarquee.cycleAt > 0) {
      homeMarketMarquee.position = Math.max(0, previousProgress) % homeMarketMarquee.cycleAt;
      carousel.scrollLeft = homeMarketMarquee.position;
    }
    if (!carousel.dataset.marqueeReady) {
      carousel.dataset.marqueeReady = "true";
      carousel.addEventListener("pointerdown", () => pauseHomeMarketMarquee(), { passive: true });
      carousel.addEventListener("pointerup", () => pauseHomeMarketMarquee(), { passive: true });
      carousel.addEventListener("pointercancel", () => pauseHomeMarketMarquee(), { passive: true });
      carousel.addEventListener("wheel", () => pauseHomeMarketMarquee(), { passive: true });
      carousel.addEventListener("focusin", () => pauseHomeMarketMarquee(8000));
      if ("IntersectionObserver" in window) {
        new IntersectionObserver((entries) => {
          homeMarketMarquee.visible = entries.some((entry) => entry.isIntersecting);
        }, { threshold: 0.05 }).observe(carousel);
      }
    }
    if (!homeMarketMarquee.frame) {
      homeMarketMarquee.frame = window.requestAnimationFrame(tickHomeMarketMarquee);
    }
  };

  const createStockLogoFrame = (code = "", className = "") => {
    const normalizedCode = String(code || "").trim();
    const frame = document.createElement("span");
    frame.className = `staging-stock-logo ${className}`.trim();
    frame.setAttribute("aria-hidden", "true");

    const fallback = document.createElement("span");
    fallback.className = "staging-stock-logo-fallback";
    fallback.innerHTML = svg(icons.stock);
    frame.appendChild(fallback);

    if (normalizedCode) {
      const image = document.createElement("img");
      image.className = "staging-stock-logo-image";
      image.alt = "";
      image.decoding = "async";
      image.loading = "eager";
      image.addEventListener("load", () => frame.classList.add("has-stock-logo"), { once: true });
      image.addEventListener("error", () => image.remove(), { once: true });
      image.src = `/stock-logos/${encodeURIComponent(normalizedCode)}.png?v=20260828-official-ci-v1`;
      frame.appendChild(image);
      if (image.complete && image.naturalWidth > 0) frame.classList.add("has-stock-logo");
    }
    return frame;
  };

  const RECENT_STOCKS_KEY = "secret-note-staging-recent-stocks-v1";
  const RECENT_STOCKS_LIMIT = 30;
  const recentStockTone = (rate) => {
    const value = Number(rate);
    return Number.isFinite(value) && value > 0 ? "positive" : Number.isFinite(value) && value < 0 ? "negative" : "muted";
  };
  const normalizeRecentStocks = (items = []) => {
    const seen = new Set();
    const normalized = [];
    for (const source of Array.isArray(items) ? items : []) {
      const code = String(source?.code || "").trim();
      const name = String(source?.name || "").trim();
      if (!code || !name || seen.has(code)) continue;
      seen.add(code);
      const numericRate = Number(source?.changeRate);
      normalized.push({
        code,
        name,
        market: String(source?.market || "").trim(),
        priceText: String(source?.priceText || "-").trim() || "-",
        rateText: String(source?.rateText || "-").trim() || "-",
        changeRate: Number.isFinite(numericRate) ? numericRate : null,
        viewedAt: Number(source?.viewedAt) || 0,
      });
    }
    return normalized.slice(0, RECENT_STOCKS_LIMIT);
  };
  const readRecentStocks = () => {
    try {
      return normalizeRecentStocks(JSON.parse(window.localStorage.getItem(RECENT_STOCKS_KEY) || "[]"));
    } catch {
      return [];
    }
  };
  const writeRecentStocks = (items) => {
    const normalized = normalizeRecentStocks(items);
    try {
      window.localStorage.setItem(RECENT_STOCKS_KEY, JSON.stringify(normalized));
    } catch {
      // The staging UI still works when private browsing blocks local storage.
    }
    return normalized;
  };
  const recentStocksRouteActive = () => {
    const params = new URLSearchParams(window.location.search);
    return params.get("view") === "search" && params.get("panel") === "recent-stocks";
  };
  const recentStockPriceLabel = (item) => {
    if (!item?.priceText || item.priceText === "-") return "시세 확인 중";
    const domestic = /KOSPI|KOSDAQ|KONEX/i.test(item.market) || /^\d{6}$/.test(item.code);
    return domestic && !/원$/.test(item.priceText) ? `${item.priceText}원` : item.priceText;
  };
  const makeRecentStockIdentity = (item, className) => {
    const identity = document.createElement("span");
    identity.className = className;
    identity.appendChild(createStockLogoFrame(item.code, `${className}-logo`));
    const copy = document.createElement("span");
    copy.className = `${className}-copy`;
    const name = document.createElement("strong");
    name.textContent = item.name;
    copy.append(name);
    identity.appendChild(copy);
    return identity;
  };

  let recentStocksPreview = null;
  let recentStocksRail = null;
  let recentStocksPage = null;
  let recentStocksList = null;
  let recentStockQuoteScopeSignature = "";

  const updateRecentStockQuote = (code, quote = {}) => {
    const normalizedCode = String(code || "");
    if (!normalizedCode || !quote) return;
    const items = readRecentStocks();
    const item = items.find((entry) => entry.code === normalizedCode);
    if (!item) return;
    let changed = false;
    const price = Number(quote.price);
    const changeRate = Number(quote.change_rate);
    if (Number.isFinite(price)) {
      item.priceText = formatNumber(Math.round(price));
      changed = true;
    }
    if (Number.isFinite(changeRate)) {
      item.changeRate = changeRate;
      item.rateText = formatPercent(changeRate);
      changed = true;
    }
    if (!changed) return;
    writeRecentStocks(items);
    for (const surface of [recentStocksRail, recentStocksList]) {
      if (!surface) continue;
      for (const node of surface.querySelectorAll("[data-recent-stock-code]")) {
        if (node.dataset.recentStockCode !== normalizedCode) continue;
        const rate = node.querySelector("[data-recent-stock-rate]");
        const priceNode = node.querySelector("[data-recent-stock-price]");
        if (rate) {
          rate.className = `${rate.matches("strong") ? "" : "staging-recent-stock-rate "}${recentStockTone(item.changeRate)}`.trim();
          rate.textContent = item.rateText;
          rate.classList.remove("is-live-updated");
          window.requestAnimationFrame(() => rate.classList.add("is-live-updated"));
        }
        if (priceNode) priceNode.textContent = recentStockPriceLabel(item);
        const open = node.querySelector("[data-recent-stock-open]");
        if (open) open.setAttribute("aria-label", `${item.name}, ${item.rateText}, ${recentStockPriceLabel(item)} 상세 보기`);
      }
    }
    for (const surface of [recentStocksPreview, recentStocksPage]) {
      if (!surface) continue;
      surface.dataset.liveQuoteState = "updating";
      surface.dataset.liveQuoteUpdates = String(Number(surface.dataset.liveQuoteUpdates || 0) + 1);
    }
  };

  const syncRecentStockQuoteScope = () => {
    const inSearch = (document.body.dataset.view || "") === "search";
    const active = !document.hidden && (inSearch || recentStocksRouteActive());
    const items = active
      ? readRecentStocks().slice(0, recentStocksRouteActive() ? RECENT_STOCKS_LIMIT : 5)
      : [];
    const signature = `${recentStocksRouteActive() ? "page" : inSearch ? "preview" : "off"}:${items.map((item) => item.code).join(",")}`;
    if (signature === recentStockQuoteScopeSignature) return;
    recentStockQuoteScopeSignature = signature;
    for (const surface of [recentStocksPreview, recentStocksPage]) {
      if (!surface) continue;
      surface.dataset.liveQuoteState = items.length ? "subscribing" : "idle";
      surface.dataset.liveQuoteCount = String(items.length);
    }
    if (typeof replaceQuoteStreamScope !== "function") return;
    replaceQuoteStreamScope("staging-recent-stocks", items.map((item) => ({
      code: item.code,
      handlers: {
        onStatus: () => {
          for (const surface of [recentStocksPreview, recentStocksPage]) {
            if (surface) surface.dataset.liveQuoteState = "connected";
          }
        },
        onQuote: (payload) => updateRecentStockQuote(item.code, payload.quote),
      },
    })));
  };

  const renderRecentStocks = () => {
    const items = readRecentStocks();
    if (recentStocksRail) {
      recentStocksRail.replaceChildren();
      recentStocksRail.classList.toggle("is-empty", !items.length);
      if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "staging-recent-stocks-empty";
        empty.textContent = "종목을 열어보면 최근 조회한 종목이 여기에 표시돼요.";
        recentStocksRail.appendChild(empty);
      } else {
        for (const item of items.slice(0, 5)) {
          const card = document.createElement("article");
          card.className = "staging-recent-stock-card";
          card.dataset.recentStockCode = item.code;
          const open = document.createElement("button");
          open.className = "staging-recent-stock-card-open";
          open.type = "button";
          open.dataset.recentStockOpen = item.code;
          open.setAttribute("aria-label", `${item.name} 종목 상세 보기`);
          open.appendChild(makeRecentStockIdentity(item, "staging-recent-stock-card-identity"));
          const rate = document.createElement("span");
          rate.dataset.recentStockRate = item.code;
          rate.className = `staging-recent-stock-rate ${recentStockTone(item.changeRate)}`;
          rate.textContent = item.rateText;
          open.appendChild(rate);
          const remove = document.createElement("button");
          remove.className = "staging-recent-stock-remove";
          remove.type = "button";
          remove.dataset.recentStockRemove = item.code;
          remove.setAttribute("aria-label", `${item.name} 최근 본 종목에서 삭제`);
          remove.textContent = "×";
          card.append(open, remove);
          recentStocksRail.appendChild(card);
        }
      }
    }

    if (recentStocksList) {
      recentStocksList.replaceChildren();
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "staging-recent-stocks-page-empty";
        empty.innerHTML = emptyStackIllustration;
        const title = document.createElement("strong");
        title.textContent = "최근 본 종목이 없어요";
        const description = document.createElement("span");
        description.textContent = "발견에서 궁금한 종목을 열어보세요.";
        empty.append(title, description);
        recentStocksList.appendChild(empty);
      } else {
        for (const item of items) {
          const row = document.createElement("article");
          row.className = "staging-recent-stock-row";
          row.dataset.recentStockCode = item.code;
          const open = document.createElement("button");
          open.className = "staging-recent-stock-row-open";
          open.type = "button";
          open.dataset.recentStockOpen = item.code;
          open.setAttribute("aria-label", `${item.name}, ${item.rateText}, ${recentStockPriceLabel(item)} 상세 보기`);
          open.appendChild(makeRecentStockIdentity(item, "staging-recent-stock-row-identity"));
          const quote = document.createElement("span");
          quote.className = "staging-recent-stock-quote";
          const rate = document.createElement("strong");
          rate.dataset.recentStockRate = item.code;
          rate.className = recentStockTone(item.changeRate);
          rate.textContent = item.rateText;
          const price = document.createElement("small");
          price.dataset.recentStockPrice = item.code;
          price.textContent = recentStockPriceLabel(item);
          quote.append(rate, price);
          open.appendChild(quote);
          const remove = document.createElement("button");
          remove.className = "staging-recent-stock-row-remove";
          remove.type = "button";
          remove.dataset.recentStockRemove = item.code;
          remove.setAttribute("aria-label", `${item.name} 최근 본 종목에서 삭제`);
          remove.textContent = "×";
          row.append(open, remove);
          recentStocksList.appendChild(row);
        }
      }
    }
    syncRecentStockQuoteScope();
  };

  const recommendationDetailItem = () => {
    try {
      return typeof state === "object" ? state.currentRecommendationDetailItem : null;
    } catch {
      return null;
    }
  };
  let recommendationDetailQuoteScopeSignature = "";
  let recommendationDetailLiveQuote = { code: "", price: null, changeRate: null };
  const recommendationDetailQuoteTone = (value = recommendationDetailLiveQuote.changeRate) => {
    const rate = Number(value);
    return Number.isFinite(rate) && rate > 0 ? "positive" : Number.isFinite(rate) && rate < 0 ? "negative" : "muted";
  };
  const recommendationDetailQuoteText = () => {
    const price = Number(recommendationDetailLiveQuote.price);
    const rate = Number(recommendationDetailLiveQuote.changeRate);
    if (!Number.isFinite(price)) return "실시간 시세 확인 중";
    return `${formatNumber(Math.round(price))}원${Number.isFinite(rate) ? ` (${formatPercent(rate)})` : ""}`;
  };
  const renderRecommendationDetailLiveQuote = () => {
    const text = recommendationDetailQuoteText();
    const tone = recommendationDetailQuoteTone();
    const subtitle = contextualTopbar.querySelector("[data-staging-contextual-subtitle]");
    if (subtitle && activeContextualView === "recommend-detail") {
      subtitle.textContent = text;
      subtitle.hidden = false;
      subtitle.className = tone;
    }
    const livePrice = document.querySelector("[data-staging-recommend-live-price]");
    const liveRate = document.querySelector("[data-staging-recommend-live-rate]");
    if (livePrice) livePrice.textContent = Number.isFinite(Number(recommendationDetailLiveQuote.price))
      ? `${formatNumber(Math.round(Number(recommendationDetailLiveQuote.price)))}원`
      : "시세 확인 중";
    if (liveRate) {
      const rate = Number(recommendationDetailLiveQuote.changeRate);
      liveRate.textContent = Number.isFinite(rate) ? formatPercent(rate) : "";
      liveRate.className = tone;
    }
    for (const metric of document.querySelectorAll("#recommend-detail-content .recommend-detail-metric")) {
      if (metric.querySelector("span")?.textContent?.trim() !== "현재가") continue;
      const value = metric.querySelector("strong");
      if (value && Number.isFinite(Number(recommendationDetailLiveQuote.price))) {
        value.textContent = `${formatNumber(Math.round(Number(recommendationDetailLiveQuote.price)))}원`;
      }
    }
  };
  const updateRecommendationDetailLiveQuote = (code, quote = {}) => {
    if (String(code || "") !== recommendationDetailLiveQuote.code || !quote) return;
    const price = Number(quote.price);
    const changeRate = Number(quote.change_rate);
    if (Number.isFinite(price)) recommendationDetailLiveQuote.price = price;
    if (Number.isFinite(changeRate)) recommendationDetailLiveQuote.changeRate = changeRate;
    const item = recommendationDetailItem();
    if (item && item.code === recommendationDetailLiveQuote.code) {
      if (Number.isFinite(price)) {
        item.current_price = price;
        if (item.ai_trade_signal?.current && typeof item.ai_trade_signal.current === "object") {
          item.ai_trade_signal.current.price = price;
        }
      }
      if (Number.isFinite(changeRate)) item.change_rate = changeRate;
    }
    const page = document.getElementById("recommend-detail-page");
    if (page) {
      page.dataset.liveQuoteState = "updating";
      page.dataset.liveQuoteUpdates = String(Number(page.dataset.liveQuoteUpdates || 0) + 1);
    }
    renderRecommendationDetailLiveQuote();
  };
  const syncRecommendationDetailQuoteScope = () => {
    const item = recommendationDetailItem();
    const active = !document.hidden && (document.body.dataset.view || "") === "recommend-detail";
    const code = active ? String(item?.code || new URLSearchParams(window.location.search).get("code") || "") : "";
    const signature = `${active ? "detail" : "off"}:${code}`;
    const page = document.getElementById("recommend-detail-page");
    if (code && (recommendationDetailLiveQuote.code !== code || recommendationDetailLiveQuote.price === null)) {
      const initialPrice = [
        item?.ai_trade_signal?.current?.price,
        item?.current_price,
        item?.price,
      ].find((value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)));
      recommendationDetailLiveQuote = {
        code,
        price: initialPrice === undefined ? null : Number(initialPrice),
        changeRate: Number.isFinite(Number(item?.change_rate)) ? Number(item.change_rate) : null,
      };
    }
    renderRecommendationDetailLiveQuote();
    if (signature === recommendationDetailQuoteScopeSignature) return;
    recommendationDetailQuoteScopeSignature = signature;
    if (page) {
      page.dataset.liveQuoteState = code ? "subscribing" : "idle";
      page.dataset.liveQuoteCount = code ? "1" : "0";
    }
    if (typeof replaceQuoteStreamScope !== "function") return;
    replaceQuoteStreamScope("staging-recommend-detail", code ? [{
      code,
      handlers: {
        onStatus: () => {
          if (page) page.dataset.liveQuoteState = "connected";
        },
        onQuote: (payload) => updateRecommendationDetailLiveQuote(code, payload.quote),
      },
    }] : []);
  };

  const recommendationCustomerState = (item = {}) => {
    const current = item?.ai_trade_signal?.current || {};
    const action = String(current.action || "").trim();
    const positionOpen = current.position_open === true;
    const name = item?.name || "이 종목";
    const base = {
      key: "checking",
      label: "현재 판단 확인 중",
      guide: "AI 판단 확인 중",
      headline: `${name}, 현재 AI 판단을 확인하고 있어요`,
      summary: "추천 기준을 통과한 기록과 현재 AI 판단을 함께 확인하고 있어요.",
      actionTitle: "지금은 현재 판단이 확인될 때까지 기다릴 단계예요",
      nextFallback: "현재 판단이 확인되면 새로 살지, 보유할지, 팔지 구분해 보여드려요.",
      reason: "추천 점수와 가격 조건이 기준을 통과해 추천 목록에 들어왔어요.",
      additionalBuyLabel: "확인 중",
      positionOpen,
    };
    if (action === "entry_pending") {
      return positionOpen
        ? {
          ...base,
          key: "add-buy-wait",
          label: "추가 매수 대기",
          guide: "보유 중 · 더 살 조건 확인",
          headline: `${name}, 보유하면서 추가 매수 조건을 기다리고 있어요`,
          summary: "AI 전략은 이미 이 종목을 보유 중이며, 정해진 가격 조건이 맞을 때만 추가 매수를 검토해요.",
          actionTitle: "지금은 보유하면서 추가 매수 가격을 확인할 때예요",
          nextFallback: "추가 매수 가격과 손실을 줄일 가격이 바뀌는지 확인해요.",
          reason: "추천 점수와 가격 조건, 서로 다른 확인 자료가 모두 기준을 통과했어요.",
          additionalBuyLabel: "조건 확인 중",
        }
        : {
          ...base,
          key: "new-buy-wait",
          label: "신규 매수 대기",
          guide: "아직 매수 전",
          headline: `${name}, 신규 매수를 기다리는 단계예요`,
          summary: "추천 기준은 통과했지만 아직 매수 전이에요. 다음 거래가 시작될 때 가격 조건을 다시 확인해요.",
          actionTitle: "지금은 새로 살 가격이 기준 안인지 확인할 때예요",
          nextFallback: "다음 거래가 시작될 때 가격이 매수 기준 안인지 확인해요.",
          reason: "추천 점수와 가격 조건, 서로 다른 확인 자료가 모두 기준을 통과했어요.",
          additionalBuyLabel: "보유 전",
        };
    }
    if (action === "entry_watch") {
      return {
        ...base,
        key: positionOpen ? "add-buy-checking" : "new-buy-checking",
        label: positionOpen ? "추가 매수 조건 확인 중" : "신규 매수 조건 확인 중",
        guide: positionOpen ? "보유 중 · 조건 확인" : "아직 매수 전 · 조건 확인",
        headline: `${name}, ${positionOpen ? "추가" : "신규"} 매수 조건을 확인하고 있어요`,
        summary: `아직 ${positionOpen ? "추가" : "신규"} 매수 판단이 확정되지 않았어요. 필요한 가격과 자료가 갖춰지는지 확인하고 있어요.`,
        actionTitle: "지금은 매수 조건이 갖춰지는지 확인할 때예요",
        nextFallback: "추천 기준과 가격 조건이 모두 갖춰지는지 확인해요.",
        additionalBuyLabel: positionOpen ? "조건 확인 중" : "보유 전",
      };
    }
    if (action === "partial_exit_pending") {
      return {
        ...base,
        key: "partial-sell-wait",
        label: "일부 수익 확인 대기",
        guide: "보유 중 · 일부 매도 조건 확인",
        headline: `${name}, 일부 수익을 확인할 가격을 기다리고 있어요`,
        summary: "AI 전략은 일부만 팔고 나머지는 보유할 조건을 확인하고 있어요.",
        actionTitle: "지금은 일부 수익을 확인할 가격을 볼 때예요",
        nextFallback: "일부 매도 기준과 남은 보유 물량의 위험 기준을 확인해요.",
        additionalBuyLabel: "신호 없음",
      };
    }
    if (action === "full_exit_pending") {
      return {
        ...base,
        key: "sell-wait",
        label: "매도 대기",
        guide: "보유 중 · 매도 조건 확인",
        headline: `${name}, 현재 AI 판단은 매도 대기예요`,
        summary: "AI 전략은 보유를 끝낼 조건이 확인되어 실제 매도 가격을 기다리고 있어요.",
        actionTitle: "지금은 보유를 끝낼 가격을 확인할 때예요",
        nextFallback: "다음 거래가 시작될 때 매도 가격을 확인해요.",
        additionalBuyLabel: "신호 없음",
      };
    }
    if (action === "exited" && !positionOpen) {
      return {
        ...base,
        key: "sold",
        label: "매도 완료",
        guide: "미보유 · 다음 기회 확인",
        headline: `${name}, AI 전략은 현재 보유하지 않아요`,
        summary: "이전 보유는 끝났고, 새로운 매수 조건이 생기는지 기다리는 상태예요.",
        actionTitle: "지금은 새로운 매수 조건을 기다릴 때예요",
        nextFallback: "새로운 매수 조건이 다시 갖춰지는지 확인해요.",
        additionalBuyLabel: "해당 없음",
      };
    }
    if (positionOpen || ["entered", "holding", "partially_exited"].includes(action)) {
      const partial = action === "partially_exited";
      return {
        ...base,
        key: partial ? "partial-hold" : "hold",
        label: partial ? "일부 수익 확인 후 보유" : "보유 유지",
        guide: "추가 매수 신호 없음",
        headline: `${name}, 현재 AI 판단은 ${partial ? "일부 수익 확인 후 보유" : "보유 유지"}예요`,
        summary: partial
          ? "AI 전략은 일부 수익을 확인하고 남은 물량을 보유 중이에요. 지금은 추가 매수보다 남은 보유 기준을 확인해요."
          : "AI 전략은 이미 이 종목을 보유 중이에요. 지금은 새로 더 사기보다 계속 보유할 기준과 위험 가격을 확인해요.",
        actionTitle: "지금은 추가 매수보다 보유 기준을 확인할 때예요",
        nextFallback: "손실을 줄일 가격과 첫 수익 확인 가격이 바뀌는지 살펴봐요.",
        reason: "추천 기준을 통과한 뒤 AI 전략이 매수했고, 현재는 보유 상태를 점검하고 있어요.",
        additionalBuyLabel: "신호 없음",
      };
    }
    if (item?.recommendation_state === "entry_confirmed") {
      return {
        ...base,
        key: "new-buy-wait",
        label: "신규 매수 대기",
        guide: "아직 매수 전",
        headline: `${name}, 신규 매수를 기다리는 단계예요`,
        summary: "추천 기준은 통과했지만 아직 매수 전이에요. 새로 살 가격이 기준 안인지 확인하고 있어요.",
        actionTitle: "지금은 새로 살 가격이 기준 안인지 확인할 때예요",
        nextFallback: "새로 살 가격이 매수 기준 안인지 확인해요.",
        additionalBuyLabel: "보유 전",
      };
    }
    return base;
  };

  const decorateRecommendationCards = () => {
    const status = document.getElementById("recommend-status");
    if (status?.textContent?.includes("추천 후보를 찾지 못했습니다")) {
      status.textContent = "지금 새로 매수를 검토할 종목이 없어요. 추천 기준을 통과하면 현재 AI 판단과 함께 이곳에 표시됩니다.";
    }
    for (const card of document.querySelectorAll("#recommend-view .recommend-card")) {
      const item = card.recommendationItem || {};
      const customerState = recommendationCustomerState(item);
      card.dataset.recommendationState = item.recommendation_state === "entered_today" ? "entered-today" : "entry-confirmed";
      card.dataset.customerState = customerState.key;
      const itemName = card.querySelector(".recommend-name strong")?.textContent?.trim() || "추천 종목";
      const rank = card.querySelector(".recommend-rank");
      if (rank) {
        rank.textContent = `#${item.rank || "-"} · ${customerState.label}`;
        rank.classList.remove("watch");
        rank.classList.add("buy");
      }
      const stage = card.querySelector(".recommend-signal-stage");
      if (stage) stage.textContent = customerState.label;
      const stageLabel = card.querySelector(".recommend-decision-flow-head > span");
      if (stageLabel) stageLabel.textContent = "지금 AI 판단";
      const changedLabel = card.querySelector(".recommend-signal-facts dt");
      if (changedLabel) changedLabel.textContent = "최근 판단 변경";
      const reasonLabel = card.querySelector(".recommend-card-reason-label");
      if (reasonLabel) reasonLabel.textContent = "왜 추천에 들어왔나요?";
      const reason = card.querySelector(".recommend-card-reason p");
      if (reason) reason.textContent = customerState.reason;
      const scoreLevelRow = card.querySelector(".recommend-score-level");
      const scoreLevel = scoreLevelRow?.querySelector("b") || card.querySelector(".recommend-score em");
      const scoreGuide = scoreLevelRow?.querySelector("span");
      if (scoreLevel) scoreLevel.textContent = "추천 기준 통과";
      if (scoreGuide) scoreGuide.textContent = `· ${customerState.guide}`;
      scoreLevelRow?.classList.remove("high", "watch", "cautious");
      scoreLevelRow?.classList.add("qualified");
      const detailButton = card.querySelector(".recommend-ai-button");
      if (detailButton) {
        detailButton.textContent = "자세히 보기";
        detailButton.setAttribute("aria-label", `${itemName} 추천 근거 자세히 보기`);
      }
      const help = card.querySelector(".recommend-score-help");
      if (help) {
        help.dataset.tooltip = "추천 점수는 기준을 통과한 종목끼리 비교한 순위예요. 지금 새로 살 차례인지, 보유할 차례인지는 현재 AI 판단에서 확인할 수 있어요.";
        help.setAttribute("aria-label", "추천 점수와 현재 AI 판단 설명");
        help.setAttribute("aria-expanded", String(help.classList.contains("open")));
        help.setAttribute("aria-haspopup", "true");
      }
    }
  };

  const recommendationDetailFriendlyText = (value = "") => {
    let text = String(value || "").replace(/\s+/g, " ").trim();
    for (const [before, after] of [
      ["추천 점수 기준과 장 마감 매수 조건, 독립 근거를 통과해 오늘 시가에 전략 반영이 끝났습니다", "추천 기준을 통과한 뒤 AI 전략이 매수했고, 현재는 보유 기준을 확인하고 있어요"],
      ["장 마감 매수 조건과 독립 근거를 통과해 오늘 시가에 전략 반영이 끝났어요", "추천 기준을 통과한 뒤 AI 전략이 매수했고, 현재는 보유 기준을 확인하고 있어요"],
      ["오늘 시가 반영이 끝나 현재는 보유 기준을 확인할 단계예요", "지금은 추가 매수보다 보유 기준을 확인할 때예요"],
      ["오늘 시가 반영 완료", "보유 유지"],
      ["오늘 시가 반영", "AI 전략 매수"],
      ["장 마감 매수 조건", "추천 가격 조건"],
      ["다음 거래일 시가의 갭 범위", "다음 거래 시작 가격 범위"],
      ["시가의 갭 범위", "거래 시작 가격 범위"],
      ["다음 거래일 시가", "다음 거래 시작 가격"],
      ["독립 우호 근거", "서로 다른 확인 자료"],
      ["독립 근거", "서로 다른 확인 자료"],
      ["초기 위험선과 1차 계단형 수익을 나눠 확인하는 단계 기준", "처음 정한 위험 기준과 첫 수익 확인 기준"],
      ["초기 위험선과 1차 수익확정 기준", "처음 정한 위험 기준과 첫 수익 확인 기준"],
      ["점수와 차트가 기준을 통과해 진입 가격과 거래대금 확인이 우선입니다", "점수와 차트가 기준을 통과해 새로 살 가격과 실제 거래 규모 확인이 우선입니다"],
      ["1차 수익확정 가격과 변동성 추적선을 매일 확인", "첫 수익을 확인할 가격과 가격이 흔들릴 때 손실을 줄일 기준을 매일 확인해요"],
      ["새 매수보다 현재 포지션 관리가 우선이에요", "이미 보유 중이라면 새로 사기보다 계속 들고 갈지 판단할 기준을 먼저 볼 때예요"],
      ["현재 포지션 관리가 우선입니다", "이미 보유 중이라면 계속 들고 갈지 판단할 기준을 먼저 볼 때예요"],
      ["보유·매도 조건을 확인하세요", "이미 보유 중이라면 계속 들고 갈지, 팔지 판단할 기준을 볼 때예요"],
      ["매수 우선검토", "매수 조건을 우선 확인하는 단계"],
      ["가격 모멘텀 기준 선별", "최근 가격 흐름 기준으로 고른 후보"],
      ["상승 추세", "가격이 오르는 흐름"],
      ["하락 추세", "가격이 내리는 흐름"],
      ["진입 가격", "새로 살 가격"],
      ["거래대금", "실제 거래 규모"],
      ["차트 지지", "가격이 버틴 기준"],
      ["저항", "가격이 넘어서야 할 기준"],
      ["수익확정", "수익을 나눠 확인하는 단계"],
      ["추적선", "손실을 줄일 기준"],
      ["모멘텀", "최근 가격 흐름"],
      ["손실 제한선", "손실을 줄일 가격"],
      ["AI 매매 시그널", "현재 AI 판단"],
      ["매매 시그널", "AI 판단"],
      ["매수 시그널", "새로 살 수 있다는 AI 판단"],
      ["시그널", "AI 판단"],
      ["신규 진입", "새로 사는 것"],
      ["재진입", "다시 사는 것"],
      ["진입 조건", "새로 살 조건"],
      ["진입", "새로 사는 것"],
      ["현재 포지션", "현재 보유 상태"],
      ["포지션", "보유 상태"],
      ["수급", "외국인과 기관의 매매"],
      ["종가", "장이 끝날 때 가격"],
      ["지지선", "가격이 버텨야 하는 기준"],
      ["저항선", "가격이 넘어서야 하는 기준"],
      ["변동성", "가격 움직임"],
      ["추격 매수", "오른 가격을 따라 바로 사는 것"],
      ["추격", "오른 가격을 따라 바로 사는 것"],
    ]) text = text.replaceAll(before, after);
    return text;
  };

  const recommendationDetailSummaryInput = (item, hero, action) => {
    const score = Number(item?.score);
    const currentSignal = item?.ai_trade_signal?.current || {};
    const customerState = recommendationCustomerState(item);
    const signalScore = Number(currentSignal.score);
    const entryConfirmation = currentSignal.entry_confirmation || {};
    const entryLevel = (currentSignal.levels || []).find((level) => level?.key === "entry") || {};
    const explanation = typeof buildRecommendationAIExplanation === "function"
      ? buildRecommendationAIExplanation(item)
      : {};
    const title = recommendationDetailFriendlyText(
      hero?.querySelector("h1")?.textContent?.trim()
        || customerState.headline,
    );
    const verdict = recommendationDetailFriendlyText(
      hero?.querySelector(".recommend-detail-verdict")?.textContent?.trim()
        || customerState.summary,
    );
    const actionTitle = recommendationDetailFriendlyText(
      action?.querySelector(":scope > h2")?.textContent?.trim()
        || customerState.actionTitle,
    );
    const nextCheck = recommendationDetailFriendlyText(
      action?.querySelector(".staging-recommend-detail-next-check strong")?.textContent?.trim()
        || currentSignal.next_confirmation
        || customerState.nextFallback,
    );
    const sources = [{
      id: "buy-condition",
      label: "추천 기준 확인",
      value: customerState.label,
      evidence: customerState.reason,
    }];
    if (Number.isFinite(score)) sources.push({ id: "recommendation-score", label: "추천 점수", value: score });
    sources.push({ id: "next-session-check", label: "다음 확인", value: actionTitle, evidence: nextCheck });
    return {
      facts: {
        code: item?.code,
        name: item?.name,
        rank: item?.rank,
        score: Number.isFinite(score) ? score : null,
        recommendation_state: item?.recommendation_state,
        customer_state: customerState.key,
        customer_state_label: customerState.label,
        customer_state_note: customerState.summary,
        additional_buy_label: customerState.additionalBuyLabel,
        buy_condition_met: item?.buy_condition_met === true,
        buy_condition_as_of: item?.buy_condition_as_of,
        entry_date: item?.recommendation_entry_date || currentSignal.entry_date,
        strategy_entry_price: item?.strategy_entry_price || currentSignal.entry_price,
        action: recommendationDetailFriendlyText(item?.action),
        decision_reason: recommendationDetailFriendlyText(item?.decision_reason),
        signal_action: currentSignal.action,
        signal_score: Number.isFinite(signalScore) ? signalScore : null,
        signal_label: actionTitle,
        signal_next: nextCheck,
        position_open: currentSignal.position_open,
        current_price: currentSignal.price,
        condition_price: item?.condition_price ?? item?.price,
        entry_reference: entryLevel.price,
        entry_confirmation: entryConfirmation,
        entry_low: explanation.entryLow,
        entry_high: explanation.entryHigh,
        reasons: (item?.reasons || []).slice(0, 5).map(recommendationDetailFriendlyText),
        risks: (item?.risks || []).slice(0, 5).map(recommendationDetailFriendlyText),
        sources,
      },
      fallback: {
        headline: title,
        summary: verdict,
        reason: customerState.reason,
        action_title: actionTitle,
        next_check: nextCheck,
        evidence_refs: sources.slice(0, 3).map((source) => source.id),
      },
    };
  };

  let stagingRecommendationDetailSummaryToken = 0;
  const setRecommendationDetailSummaryDisplay = (content, mode = "loading") => {
    if (!(content instanceof HTMLElement)) return;
    const ready = mode === "ready";
    content.dataset.summaryDisplay = ready ? "ready" : "loading";
    content.setAttribute("aria-busy", String(!ready));
    const loader = content.querySelector(":scope > [data-staging-recommend-detail-loader]");
    if (loader instanceof HTMLElement) loader.hidden = ready;
  };

  const applyRecommendationDetailSummary = async (item, hero, action, source) => {
    const content = document.getElementById("recommend-detail-content");
    if (!stagingGptPageSummaryEnabled || !content || !hero || !action || !item?.code) return;
    const requestedCode = String(item.code);
    const summaryToken = ++stagingRecommendationDetailSummaryToken;
    content.dataset.summaryMode = "loading";
    setRecommendationDetailSummaryDisplay(content, "loading");
    const { facts, fallback } = recommendationDetailSummaryInput(item, hero, action);
    try {
      const summary = await requestStagingPageSummary("recommendation_detail", facts, fallback);
      if (
        !hero.isConnected
        || String(recommendationDetailItem()?.code || "") !== requestedCode
        || summaryToken !== stagingRecommendationDetailSummaryToken
      ) return;
      if (typeof summary?.headline !== "string") {
        content.dataset.summaryMode = "rules";
        setRecommendationDetailSummaryDisplay(content, "ready");
        return;
      }
      const title = hero.querySelector("h1");
      const verdict = hero.querySelector(".recommend-detail-verdict");
      const actionTitle = action.querySelector(":scope > h2");
      const reason = action.querySelector("[data-staging-recommend-detail-reason]");
      const nextCheck = action.querySelector(".staging-recommend-detail-next-check strong");
      if (title) title.textContent = recommendationDetailFriendlyText(summary.headline);
      if (verdict) verdict.textContent = recommendationDetailFriendlyText(summary.summary);
      if (actionTitle) actionTitle.textContent = recommendationDetailFriendlyText(summary.action_title);
      if (reason) reason.textContent = recommendationDetailFriendlyText(summary.reason);
      if (nextCheck) nextCheck.textContent = recommendationDetailFriendlyText(summary.next_check);
      content.dataset.summaryMode = summary.generation_mode || "rules";
      setRecommendationDetailSummaryDisplay(content, "ready");
      if (source && summary.generation_mode === "openai") {
        source.textContent = "설명은 이해하기 쉽게 풀어썼고, 추천 여부와 점수·가격은 공개 시장 데이터를 기준으로 계산했어요.";
      }
    } catch {
      if (summaryToken !== stagingRecommendationDetailSummaryToken) return;
      content.dataset.summaryMode = "rules";
      setRecommendationDetailSummaryDisplay(content, "ready");
    }
  };

  const kstTodayToken = () => {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  };

  const decorateRecommendationDetail = () => {
    const content = document.getElementById("recommend-detail-content");
    const hero = content?.querySelector(":scope > .recommend-detail-hero");
    if (!content || !hero || hero.classList.contains("staging-recommend-detail-hero")) return;
    const item = recommendationDetailItem() || {};
    hero.classList.add("staging-recommend-detail-hero");

    const children = Array.from(content.children);
    const decision = children.find((node) => node.matches?.(".recommend-decision-flow.is-detail"));
    const action = children.find((node) => node.matches?.(".recommend-detail-action"));
    const sections = children.filter((node) => node.matches?.(".recommend-detail-section:not(.recommend-detail-action)"));
    const sectionByTitle = (text) => sections.find((section) => section.querySelector(":scope > h2")?.textContent?.includes(text));
    const levels = sectionByTitle("추천 후보 가격 기준");
    const snapshot = sectionByTitle("판단에 쓴 핵심 수치");
    const evidence = sectionByTitle("세부 근거");
    const source = children.find((node) => node.matches?.(".recommend-detail-source"));
    const currentStageText = decision?.querySelector(".recommend-signal-stage")?.textContent?.trim() || "";
    const currentSignal = item.ai_trade_signal?.current || {};
    const customerState = recommendationCustomerState(item);
    const recommendationEntryDate = String(
      item.recommendation_entry_date || currentSignal.entry_date || "",
    ).slice(0, 10);
    const recommendationStillActive = /매수 대기|매수 조건 (?:충족|확정)/.test(currentStageText);
    const enteredToday = Boolean(
      item.recommendation_state === "entered_today"
      && recommendationEntryDate === kstTodayToken()
      && /보유|진입 완료|확정 매수/.test(currentStageText),
    );
    const recommendationStillVisible = recommendationStillActive || enteredToday;
    content.dataset.recommendationState = recommendationStillActive
      ? "active"
      : enteredToday
        ? "entered-today"
        : "changed";
    content.dataset.customerState = customerState.key;

    const score = Number(item.score);
    const signalScore = Number(currentSignal.score);
    const entryConfirmation = currentSignal.entry_confirmation || {};
    const supportiveCount = Number(entryConfirmation.supportive_count);
    const requiredSupports = Number(entryConfirmation.required_supports);
    const entryLevel = (currentSignal.levels || []).find((level) => level?.key === "entry") || {};
    const conditionPrice = Number(item.condition_price ?? item.price);
    const entryReference = Number(entryLevel.price);
    const strategyEntryPrice = Number(item.strategy_entry_price || currentSignal.entry_price);
    const currentPrice = Number(currentSignal.price);
    const heroHead = hero.querySelector(".recommend-detail-hero-head");
    const eyebrow = hero.querySelector(".recommend-detail-eyebrow");
    const title = hero.querySelector("h1");
    const lead = hero.querySelector(".recommend-detail-lead");
    const verdict = hero.querySelector(".recommend-detail-verdict");
    if (eyebrow) {
      eyebrow.textContent = recommendationStillVisible
        ? `추천 #${item.rank || "-"} · ${customerState.label}`
        : `추천 당시 #${item.rank || "-"} · 현재 ${customerState.label}`;
    }
    if (title) {
      title.textContent = customerState.headline;
    }
    if (verdict) {
      verdict.textContent = recommendationStillVisible
        ? customerState.summary
        : `${customerState.summary} 이 종목은 오늘의 신규 추천 목록에는 포함되지 않아요.`;
    }
    const scoreWrap = hero.querySelector(".recommend-detail-score");
    if (scoreWrap && Number.isFinite(score)) {
      const scoreLevel = scoreWrap.querySelector("em");
      if (scoreLevel) scoreLevel.textContent = recommendationStillVisible
        ? "추천 기준 통과"
        : "추천 당시 통과";
      scoreWrap.setAttribute(
        "aria-label",
        `추천 점수 ${formatNumber(score)}점, 현재 AI 판단 ${customerState.label}`,
      );
    }
    const scoreTrack = document.createElement("div");
    scoreTrack.className = "staging-recommend-detail-score-track";
    scoreTrack.setAttribute("role", "progressbar");
    scoreTrack.setAttribute("aria-label", "추천 점수");
    scoreTrack.setAttribute("aria-valuemin", "0");
    scoreTrack.setAttribute("aria-valuemax", "100");
    scoreTrack.setAttribute("aria-valuenow", Number.isFinite(score) ? String(Math.max(0, Math.min(100, score))) : "0");
    scoreTrack.style.setProperty("--staging-recommend-score", `${Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0}%`);
    scoreTrack.appendChild(document.createElement("span"));
    heroHead?.insertAdjacentElement("afterend", scoreTrack);

    const quickMetrics = document.createElement("dl");
    quickMetrics.className = "staging-recommend-detail-quick-metrics";
    const addQuickMetric = (label, value, rawValue = null) => {
      const metric = document.createElement("div");
      const term = Object.assign(document.createElement("dt"), { textContent: label });
      const description = Object.assign(document.createElement("dd"), { textContent: value });
      if (Number.isFinite(rawValue)) {
        description.className = rawValue > 0 ? "positive" : rawValue < 0 ? "negative" : "muted";
      }
      metric.append(term, description);
      quickMetrics.appendChild(metric);
    };
    addQuickMetric("추천 점수", Number.isFinite(score) ? `${formatNumber(score)}점` : "확인 중");
    addQuickMetric("AI 판단 점수", Number.isFinite(signalScore) ? `${formatNumber(signalScore)}점` : "확인 중");
    addQuickMetric("지금 판단", customerState.label);
    lead?.remove();
    (verdict || scoreTrack).insertAdjacentElement("afterend", quickMetrics);

    let recommendationDataPending = false;
    let recommendationSummaryReady = recommendationStillVisible;
    if (action) {
      action.classList.add("staging-recommend-detail-action");
      const label = action.querySelector(".recommend-detail-section-head > div");
      if (label) label.textContent = "지금 어떻게 보면 되나요?";
      const badge = action.querySelector(".recommend-detail-ai-badge");
      recommendationDataPending = /분석 중|대기/.test(badge?.textContent || "");
      recommendationSummaryReady = recommendationStillVisible && !recommendationDataPending;
      badge?.remove();
      const actionTitle = action.querySelector(":scope > h2");
      if (actionTitle) {
        actionTitle.textContent = customerState.actionTitle;
      }
      const actionCopy = action.querySelector(":scope > p");
      if (actionCopy) {
        const next = document.createElement("div");
        next.className = "staging-recommend-detail-next-check";
        next.append(
          Object.assign(document.createElement("span"), { textContent: "다음에 볼 것" }),
          Object.assign(document.createElement("strong"), {
            textContent: recommendationDetailFriendlyText(
              currentSignal.next_confirmation
                || actionCopy.textContent?.trim()
                || customerState.nextFallback,
            ),
          }),
        );
        actionCopy.replaceWith(next);
      }
      const reason = document.createElement("div");
      reason.className = "staging-recommend-detail-reason";
      reason.append(
        Object.assign(document.createElement("span"), {
          textContent: recommendationStillVisible ? "왜 추천에 들어왔나요?" : "추천 당시 왜 들어왔나요?",
        }),
        Object.assign(document.createElement("p"), {
          textContent: customerState.reason,
        }),
      );
      reason.querySelector("p").dataset.stagingRecommendDetailReason = "true";
      action.querySelector(".staging-recommend-detail-next-check")?.insertAdjacentElement("beforebegin", reason);
    }
    if (levels) levels.classList.add("staging-recommend-detail-levels");
    if (levels?.querySelector(":scope > h2")) {
      levels.querySelector(":scope > h2").textContent = "지금 판단에 필요한 가격";
    }
    const levelGrid = levels?.querySelector(".recommend-detail-table");
    if (levelGrid) {
      const addConditionMetric = (label, value) => {
        const metric = document.createElement("div");
        metric.className = "recommend-detail-metric";
        metric.append(
          Object.assign(document.createElement("span"), { textContent: label }),
          Object.assign(document.createElement("strong"), { textContent: value }),
        );
        levelGrid.appendChild(metric);
      };
      levelGrid.replaceChildren();
      addConditionMetric("추천 기준", recommendationStillVisible ? "통과" : "추천 당시 통과");
      addConditionMetric("추천 당시 가격", Number.isFinite(conditionPrice) ? `${formatNumber(conditionPrice)}원` : "확인 완료");
      if (Number.isFinite(strategyEntryPrice)) {
        addConditionMetric("AI 전략 매수가", `${formatNumber(strategyEntryPrice)}원`);
      } else {
        addConditionMetric("새로 살 기준 가격", Number.isFinite(entryReference) ? `${formatNumber(entryReference)}원` : "확인 중");
      }
      addConditionMetric("현재가", Number.isFinite(currentPrice) ? `${formatNumber(currentPrice)}원` : "확인 중");
      addConditionMetric(
        "확인한 자료",
        Number.isFinite(supportiveCount) && Number.isFinite(requiredSupports)
          ? `${formatNumber(supportiveCount)}개 · 기준 ${formatNumber(requiredSupports)}개`
          : "확인 완료",
      );
      addConditionMetric("지금 판단", customerState.label);
      addConditionMetric("추가 매수", customerState.additionalBuyLabel);
    }
    if (snapshot?.querySelector(":scope > h2")) snapshot.querySelector(":scope > h2").textContent = "추천 점수를 만든 핵심 수치";
    if (evidence) evidence.classList.add("staging-recommend-detail-evidence-section");
    if (evidence?.querySelector(":scope > h2")) evidence.querySelector(":scope > h2").textContent = "추천 근거와 꼭 볼 위험";
    for (const entry of evidence?.querySelectorAll("li") || []) {
      entry.textContent = recommendationDetailFriendlyText(entry.textContent);
    }
    if (decision) {
      decision.classList.add("staging-recommend-detail-journey");
      const journeyTitle = decision.querySelector(".recommend-decision-flow-head > span");
      if (journeyTitle) journeyTitle.textContent = "추천 뒤 AI 판단 변화";
      const journeyStage = decision.querySelector(".recommend-signal-stage");
      if (journeyStage) journeyStage.textContent = customerState.label;
      const independence = decision.querySelector(".recommend-signal-independence");
      if (independence) {
        independence.textContent = "추천 점수는 종목을 고른 결과이고, 현재 AI 판단은 지금 새로 살지·보유할지·팔지를 따로 보여줘요.";
      }
      const timelineItems = Array.from(decision.querySelectorAll(".recommend-signal-timeline-item"));
      for (const entry of timelineItems) {
        const timelineTitle = entry.querySelector(".recommend-signal-timeline-head strong");
        const timelineCopy = entry.querySelector(".recommend-signal-timeline-content > p");
        if (timelineTitle?.textContent?.trim() === "추천 후보 평가") {
          timelineTitle.textContent = "추천 조건 통과";
        } else if (timelineTitle?.textContent?.trim() === "매수 대기") {
          timelineTitle.textContent = customerState.positionOpen ? "추가 매수 대기" : "신규 매수 대기";
        } else if (timelineTitle?.textContent?.trim() === "확정 매수") {
          timelineTitle.textContent = "AI 전략 매수";
        }
        if (timelineCopy) {
          timelineCopy.textContent = recommendationDetailFriendlyText(timelineCopy.textContent)
            .replaceAll("관찰 후보", "추천 기준 통과")
            .replace(/서로 다른 확인 자료 확인 후 다음 거래 시작 가격 범위를 확인해 매수/g, "서로 다른 확인 자료와 새로 살 가격을 확인");
        }
      }
      if (timelineItems.length > 4) {
        timelineItems.slice(4).forEach((entry) => { entry.hidden = true; });
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "staging-recommend-history-toggle";
        toggle.dataset.stagingRecommendHistoryToggle = "true";
        toggle.setAttribute("aria-expanded", "false");
        toggle.dataset.hiddenCount = String(timelineItems.length - 4);
        toggle.textContent = `지난 판단 ${timelineItems.length - 4}개 더 보기`;
        decision.querySelector(".recommend-signal-history")?.appendChild(toggle);
      }
    }
    if (source) source.textContent = "추천 점수와 현재 AI 판단은 공개 시장 데이터를 기준으로 계산했어요.";
    const loader = document.createElement("section");
    loader.className = "staging-recommend-detail-loader";
    loader.dataset.stagingRecommendDetailLoader = "true";
    loader.setAttribute("role", "status");
    loader.setAttribute("aria-live", "polite");
    loader.innerHTML = `
      <span class="staging-ai-stock-response-loader-spinner" aria-hidden="true"></span>
      <div>
        <strong>추천 상태를 정리하고 있어요</strong>
        <p>추천 기준과 현재 AI 판단을 쉬운 말로 풀고 있어요.</p>
      </div>
    `;
    content.replaceChildren(loader, ...[hero, action, levels, evidence, decision, source].filter(Boolean));
    renderRecommendationDetailLiveQuote();
    if (recommendationDataPending) {
      stagingRecommendationDetailSummaryToken += 1;
      content.dataset.summaryMode = "loading";
      setRecommendationDetailSummaryDisplay(content, "loading");
    } else if (stagingGptPageSummaryEnabled && recommendationSummaryReady) {
      setRecommendationDetailSummaryDisplay(content, "loading");
      void applyRecommendationDetailSummary(item, hero, action, source);
    } else {
      stagingRecommendationDetailSummaryToken += 1;
      content.dataset.summaryMode = "rules";
      setRecommendationDetailSummaryDisplay(content, "ready");
    }
  };

  const handleRecentStocksClick = (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const remove = target.closest("[data-recent-stock-remove]");
    if (remove) {
      event.preventDefault();
      const code = remove.getAttribute("data-recent-stock-remove") || "";
      writeRecentStocks(readRecentStocks().filter((item) => item.code !== code));
      renderRecentStocks();
      return;
    }
    const open = target.closest("[data-recent-stock-open]");
    if (open) {
      event.preventDefault();
      const code = open.getAttribute("data-recent-stock-open") || "";
      if (code) void navigateToStock(code, `/dashboard/${encodeURIComponent(code)}`);
    }
  };

  const searchView = document.getElementById("search-view");
  if (searchView) {
    const searchForm = searchView.querySelector(".discovery-search");
    const recommendationModule = document.getElementById("recommend-view");
    const overview = document.createElement("section");
    overview.className = "staging-discovery-overview";
    overview.setAttribute("aria-labelledby", "staging-discovery-overview-title");
    overview.innerHTML = `
      <header class="staging-discovery-intro">
        <span>빠른 탐색</span>
        <h2 id="staging-discovery-overview-title">종목을 찾아보세요</h2>
      </header>
    `;
    searchView.insertBefore(overview, recommendationModule || searchView.firstChild);
    if (searchForm) {
      const searchIcon = searchForm.querySelector(":scope > svg");
      if (searchIcon) searchIcon.outerHTML = svg(icons.search);
      overview.appendChild(searchForm);
    }

    const rail = shortcutRail("탐색 도구");
    rail.classList.add("staging-discovery-shortcuts");
    rail.querySelector('[data-staging-view="ai-signals"]')?.remove();
    overview.appendChild(rail);

    recentStocksPreview = document.createElement("section");
    recentStocksPreview.className = "staging-recent-stocks-preview";
    recentStocksPreview.setAttribute("aria-labelledby", "staging-recent-stocks-preview-title");
    recentStocksPreview.innerHTML = `
      <header>
        <h3 id="staging-recent-stocks-preview-title">최근 본 종목</h3>
        <button type="button" data-staging-recent-more>더 보기 ${svg(icons.chevron)}</button>
      </header>
      <div class="staging-recent-stocks-rail" data-staging-recent-stocks-rail aria-live="polite"></div>
    `;
    recentStocksRail = recentStocksPreview.querySelector("[data-staging-recent-stocks-rail]");
    recentStocksPreview.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target : null;
      const more = target?.closest("[data-staging-recent-more]");
      if (more) {
        event.preventDefault();
        const url = new URL(window.location.href);
        url.pathname = "/dashboard";
        url.search = "?view=search&panel=recent-stocks";
        window.history.pushState({ ...(window.history.state || {}), stagingPanel: "recent-stocks" }, "", url);
        syncShell();
        window.scrollTo({ top: 0, behavior: "auto" });
        window.requestAnimationFrame(() => contextualBack?.focus());
        return;
      }
      handleRecentStocksClick(event);
    });
    overview.appendChild(recentStocksPreview);

    recentStocksPage = document.createElement("section");
    recentStocksPage.id = "staging-recent-stocks-view";
    recentStocksPage.className = "app-page staging-recent-stocks-page";
    recentStocksPage.hidden = true;
    recentStocksPage.innerHTML = `
      <div class="staging-recent-stocks-page-intro">
        <p>최근 조회한 순서예요</p>
      </div>
      <section class="staging-recent-stocks-list" data-staging-recent-stocks-list aria-live="polite"></section>
    `;
    recentStocksList = recentStocksPage.querySelector("[data-staging-recent-stocks-list]");
    recentStocksPage.addEventListener("click", handleRecentStocksClick);
    searchView.insertAdjacentElement("afterend", recentStocksPage);
    renderRecentStocks();
    const recommendationTitle = document.getElementById("recommend-stage-title");
    if (recommendationTitle) recommendationTitle.textContent = "지금 확인할 추천 종목";
    const recommendationHeading = recommendationTitle?.closest(".discovery-module-head");
    const recommendationHeadingGroup = recommendationTitle?.parentElement;
    if (recommendationHeadingGroup) {
      const kicker = document.createElement("span");
      kicker.className = "staging-recommend-kicker";
      kicker.textContent = "AI 종목 추천";
      recommendationHeadingGroup.prepend(kicker);
      const description = document.createElement("p");
      description.className = "staging-recommend-description";
      description.textContent = "추천 기준을 통과한 종목을 현재 AI 판단과 함께 보여드려요. 새로 살 차례인지, 보유할 차례인지 먼저 확인해 보세요.";
      recommendationHeadingGroup.appendChild(description);
    }
    recommendationHeading?.setAttribute("aria-describedby", "staging-recommend-description");
    const recommendationDescription = recommendationHeading?.querySelector(".staging-recommend-description");
    if (recommendationDescription) recommendationDescription.id = "staging-recommend-description";
  }

  let syncStagingWatchlist = () => {};
  const portfolioView = document.getElementById("portfolio-view");
  if (portfolioView) {
    const portfolioTabs = Array.from(portfolioView.querySelectorAll("[data-portfolio-tab]"));
    const watchlistContentTabs = document.getElementById("watchlist-content-tabs");
    const watchlistStockSection = document.querySelector("#watchlist-view .watch-v3-stock-section");
    const watchlistMeta = document.getElementById("watchlist-meta");
    const watchlistBody = document.getElementById("watchlist-body");
    const watchlistNewsHead = document.querySelector("#trend-watchlist-panel .trend-watchlist-head");
    const watchlistNewsTitle = watchlistNewsHead?.querySelector("h2");
    const watchlistNewsRail = document.getElementById("trend-watch-stock-rail");

    const resetPortfolioScroll = () => {
      window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "auto" }));
    };
    for (const tab of portfolioTabs) tab.addEventListener("click", resetPortfolioScroll);
    for (const tab of watchlistContentTabs?.querySelectorAll("[data-watch-content-tab]") || []) {
      tab.addEventListener("click", resetPortfolioScroll);
    }

    if (watchlistStockSection && !watchlistStockSection.querySelector(".staging-watchlist-list-head")) {
      const listHead = document.createElement("header");
      listHead.className = "staging-watchlist-list-head";
      listHead.innerHTML = `
        <div><span>실시간 시세</span><h2>내 관심종목</h2></div>
        <p data-staging-watchlist-count>0개</p>
      `;
      watchlistStockSection.prepend(listHead);
    }
    if (watchlistNewsTitle) watchlistNewsTitle.textContent = "종목별 최신 소식";

    syncStagingWatchlist = () => {
      const rows = Array.from(watchlistBody?.querySelectorAll("[data-watch-card]") || []);
      const loadingRows = Array.from(watchlistBody?.querySelectorAll(".watch-stock-loading") || []);
      const count = rows.length || loadingRows.length;
      const countNode = watchlistStockSection?.querySelector("[data-staging-watchlist-count]");
      const sourceMeta = watchlistMeta?.textContent?.replace(/\s+/g, " ")?.trim() || "";
      if (countNode) countNode.textContent = sourceMeta || `${count}개 종목`;

      const briefingEyebrow = document.querySelector("#watchlist-view .watch-v2-briefing-title > span");
      if (briefingEyebrow && briefingEyebrow.textContent !== "오늘의 관심 브리핑") {
        briefingEyebrow.textContent = "오늘의 관심 브리핑";
      }
      const actionLabel = document.querySelector("#watchlist-view .watch-v2-action > span");
      if (actionLabel && actionLabel.textContent !== "지금 확인할 것") {
        actionLabel.textContent = "지금 확인할 것";
      }

      document.querySelector("#watchlist-view .watch-v2-briefing-context")?.remove();
      for (const footer of watchlistBody?.querySelectorAll(".watch-v2-row-footer") || []) {
        footer.remove();
      }

      const monitor = document.querySelector("#watchlist-view .watch-v2-monitoring");
      monitor?.classList.toggle("is-single", rows.length <= 1);

      for (const button of watchlistNewsRail?.querySelectorAll(".trend-watch-stock-chip") || []) {
        if (button.dataset.stagingWatchStock === "true") continue;
        const name = button.textContent?.replace(/\s+/g, " ")?.trim() || "종목";
        const label = document.createElement("span");
        label.textContent = name;
        button.replaceChildren(createStockLogoFrame(button.dataset.code, "staging-watch-news-logo"), label);
        button.dataset.stagingWatchStock = "true";
        button.setAttribute("aria-label", `${name} 최신 소식 보기`);
      }

      for (const card of document.querySelectorAll("#portfolio-tracking-panel .recommend-track-card")) {
        const link = card.querySelector(".recommend-track-stock-link");
        if (!link || link.querySelector(".staging-pin-logo")) continue;
        link.prepend(createStockLogoFrame(card.dataset.code, "staging-pin-logo"));
      }
    };
  }

  let syncStagingFeed = () => {};
  let stagingEditorialSignalPayload = null;
  const stagingBriefingTitle = (edition = "") => ({
    morning: "아침에 보는 돈이 되는 소식",
    midday: "점심에 보는 돈이 되는 소식",
    afternoon: "장 마감 후 보는 돈이 되는 소식",
  })[edition] || "돈이 되는 소식";
  const stagingBriefingPresentation = (payload = {}) => ({
    morning: {
      label: "아침판",
      feedTitle: stagingBriefingTitle("morning"),
      title: "밤사이 핵심만 빠르게",
      accent: "개장 전 확인할 소식을 한데 모았어요.",
    },
    midday: {
      label: "점심판",
      feedTitle: stagingBriefingTitle("midday"),
      title: "오전 핵심을 새로 정리했어요",
      accent: "장중 흐름과 오후에 볼 포인트를 한데 모았어요.",
    },
    afternoon: {
      label: "장 마감판",
      feedTitle: stagingBriefingTitle("afternoon"),
      title: "오후 핵심을 새로 정리했어요",
      accent: "장 마감 뒤 이어질 변수와 다음 일정을 한데 모았어요.",
    },
  })[payload.edition] || {
    label: payload.edition_label || "최신판",
    feedTitle: stagingBriefingTitle(payload.edition),
    title: "시장 핵심을 새로 정리했어요",
    accent: "내 돈의 흐름에 영향을 줄 소식을 한데 모았어요.",
  };
  const stagingBriefingSummaryInput = (payload = {}) => {
    const presentation = stagingBriefingPresentation(payload);
    const categoryLabels = new Map(
      (Array.isArray(payload.categories) ? payload.categories : [])
        .map((category) => [String(category?.key || ""), String(category?.label || "주요 소식")]),
    );
    const highlights = (Array.isArray(payload.highlights) ? payload.highlights : [])
      .filter((item) => String(item?.title || "").trim());
    const candidates = highlights.length
      ? highlights
      : (Array.isArray(payload.categories) ? payload.categories : [])
        .flatMap((category) => (Array.isArray(category?.items) ? category.items : [])
          .map((item) => ({ ...item, category_key: item?.category_key || category?.key, category_label: item?.category_label || category?.label })));
    const seenIds = new Set();
    const sources = candidates.slice(0, 8).flatMap((item, index) => {
      const title = String(item?.title || "").replace(/\s+/g, " ").trim();
      if (!title) return [];
      const categoryKey = String(item?.category_key || "news").replace(/[^a-z0-9_-]/gi, "-").slice(0, 16) || "news";
      const itemKey = String(item?.id || index + 1).replace(/[^a-z0-9_-]/gi, "-").slice(0, 20) || String(index + 1);
      let id = `briefing-${categoryKey}-${itemKey}`.slice(0, 48);
      if (seenIds.has(id)) id = `${id.slice(0, 44)}-${index + 1}`;
      seenIds.add(id);
      return [{
        id,
        label: String(item?.category_label || categoryLabels.get(String(item?.category_key || "")) || "주요 소식"),
        value: title,
        evidence: String(item?.why_it_matters || item?.summary || item?.status || "공개 소식").replace(/\s+/g, " ").trim(),
      }];
    });
    if (!sources.length) return null;
    const summary = sources.slice(0, 3).map((source) => source.value).join(" · ");
    return {
      facts: {
        edition: payload.edition,
        edition_key: payload.edition_key,
        edition_label: payload.edition_label,
        publication_date: payload.publication_date,
        selected_news_count: payload.selected_news_count,
        opportunity_count: payload.opportunity_count,
        caution_count: payload.caution_count,
        sources,
      },
      fallback: {
        headline: presentation.title,
        summary: summary || presentation.accent,
        reason: sources[0]?.evidence || presentation.accent,
        action_title: `이번 ${presentation.label}에서 먼저 볼 내용`,
        next_check: "원문·공시와 최신 시세를 함께 확인하세요.",
        evidence_refs: sources.slice(0, 3).map((source) => source.id),
      },
    };
  };
  const stagingBriefingSummaryPromises = new Map();
  const requestStagingBriefingSummary = (payload = {}) => {
    const input = stagingBriefingSummaryInput(payload);
    if (!input) return Promise.resolve(null);
    const key = JSON.stringify({ edition_key: payload.edition_key, ...input });
    const cached = stagingBriefingSummaryPromises.get(key);
    if (cached) return cached;
    const request = requestStagingPageSummary("briefing_edition", input.facts, input.fallback)
      .catch((error) => {
        stagingBriefingSummaryPromises.delete(key);
        throw error;
      });
    stagingBriefingSummaryPromises.set(key, request);
    return request;
  };
  const applyStagingBriefingCardSummary = async (payload = {}, editorialFeed = null) => {
    if (!stagingGptPageSummaryEnabled || !editorialFeed || !payload?.edition_key) return;
    const card = Array.from(editorialFeed.querySelectorAll("[data-staging-edition]"))
      .find((node) => node.dataset.stagingEdition === String(payload.edition_key));
    if (!card) return;
    try {
      const summary = await requestStagingBriefingSummary(payload);
      if (!summary || !card.isConnected) return;
      const title = card.querySelector("h3");
      const lead = card.querySelector(".staging-editorial-summary");
      if (title) title.textContent = summary.headline;
      if (lead) lead.textContent = summary.summary;
      card.dataset.summaryMode = summary.generation_mode || "rules";
    } catch {
      card.dataset.summaryMode = "rules";
    }
  };
  const applyStagingBriefingArticleSummary = async (payload = {}) => {
    if (!stagingGptPageSummaryEnabled || !payload?.edition_key) return;
    const view = document.getElementById("morning-money-briefing-view");
    const overview = view?.querySelector(".morning-money-overview");
    if (!view || !overview || !stagingBriefingSummaryInput(payload)) return;
    view.dataset.summaryEdition = String(payload.edition_key);
    view.dataset.summaryMode = "loading";
    try {
      const summary = await requestStagingBriefingSummary(payload);
      if (!summary || view.dataset.summaryEdition !== String(payload.edition_key)) return;
      const title = overview.querySelector("#morning-money-overview-title");
      const intro = overview.querySelector("#morning-money-overview-intro");
      const digestTitle = overview.querySelector("#morning-money-digest-title");
      if (title) title.textContent = summary.headline;
      if (intro) intro.textContent = summary.summary;
      if (digestTitle) digestTitle.textContent = summary.action_title;
      let next = overview.querySelector("[data-staging-briefing-next]");
      if (!next) {
        next = document.createElement("p");
        next.className = "staging-briefing-ai-next";
        next.dataset.stagingBriefingNext = "true";
        next.append(document.createElement("span"), document.createElement("strong"));
        overview.querySelector(".morning-money-digest")?.insertAdjacentElement("afterend", next);
      }
      const nextLabel = next.querySelector("span");
      const nextValue = next.querySelector("strong");
      if (nextLabel) nextLabel.textContent = "다음 확인";
      if (nextValue) nextValue.textContent = summary.next_check;
      view.dataset.summaryMode = summary.generation_mode || "rules";
    } catch {
      view.dataset.summaryMode = "rules";
    }
  };
  const stagingConfirmedBuyDate = (item = {}) => String(
    item.execution_date
      || item.current?.entry_date
      || item.current?.lifecycle?.latest_transition?.transition_date
      || item.signal_date
      || "",
  ).slice(0, 10);
  const stagingConfirmedBuyReason = (item = {}, maxLength = 0) => {
    const raw = String(
      item.reason
        || item.current?.reasons?.[0]
        || item.current?.lifecycle?.latest_transition?.reason
        || "종가 기준 추세와 거래대금 조건이 충족돼 확정 매수로 전환됐어요.",
    )
      .replace(/상승 추세과/g, "상승 추세와")
      .replace(/\s+/g, " ")
      .trim();
    if (!maxLength || raw.length <= maxLength) return raw;
    return `${raw.slice(0, Math.max(1, maxLength - 1)).trim()}…`;
  };
  const stagingConfirmedBuyScore = (item = {}) => {
    const value = Number(item.score ?? item.current?.score);
    return Number.isFinite(value) ? `${formatNumber(Math.round(value * 10) / 10)}점` : "조건 충족";
  };
  const stagingSignalDateToken = (value) => String(value || "").trim().slice(0, 10);
  const stagingKstSignalMoment = (value) => {
    const raw = String(value || "").trim();
    if (!raw) return Number.NaN;
    const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(raw)
      ? `${raw}+09:00`
      : raw;
    return Date.parse(normalized);
  };
  const stagingPreliminaryBuyReason = (item = {}) => String(
    item.reason
      || item.current?.reasons?.[0]
      || "장중 가격·추세 조건이 충족돼 예비 매수로 관찰 중이에요.",
  )
    .replace(/상승 추세과/g, "상승 추세와")
    .replace(/\s+/g, " ")
    .trim();
  const stagingPreliminaryBuyDataAvailableForEdition = (payload = {}) => {
    if (payload.edition !== "midday") return false;
    if (typeof payload.preliminary_buys_available === "boolean") {
      return payload.preliminary_buys_available;
    }
    if (Array.isArray(payload.preliminary_buys)) return true;
    const publicationDate = stagingSignalDateToken(payload.publication_date || payload.published_at);
    const signalDate = stagingSignalDateToken(stagingEditorialSignalPayload?.as_of);
    return Boolean(publicationDate && signalDate && publicationDate === signalDate);
  };
  const stagingPreliminaryBuysForEdition = (payload = {}) => {
    if (!stagingPreliminaryBuyDataAvailableForEdition(payload)) return [];
    const publicationDate = stagingSignalDateToken(payload.publication_date || payload.published_at);
    const directSource = Array.isArray(payload.preliminary_buys)
      ? payload.preliminary_buys
      : null;
    const source = directSource || [
      ...(Array.isArray(stagingEditorialSignalPayload?.items) ? stagingEditorialSignalPayload.items : []),
      ...(Array.isArray(stagingEditorialSignalPayload?.preliminary_history) ? stagingEditorialSignalPayload.preliminary_history : []),
    ];
    const editionStart = stagingKstSignalMoment(payload.window_start);
    const editionEnd = stagingKstSignalMoment(payload.window_end || payload.published_at);
    const selected = new Map();
    for (const item of source) {
      const action = String(item?.action || item?.current?.action || "");
      const side = String(item?.side || (action.startsWith("entry_") ? "buy" : "")).toLowerCase();
      const preliminary = item?.is_preliminary === true
        || item?.status === "preliminary"
        || ["entry_watch", "entry_pending"].includes(action);
      const signalDate = stagingSignalDateToken(
        item?.signal_date || item?.first_seen_at || item?.signal_at,
      );
      const firstSeenAt = stagingKstSignalMoment(item?.first_seen_at || item?.signal_at || item?.updated_at);
      if (
        !item?.code
        || side !== "buy"
        || !preliminary
        || item?.active === false
        || signalDate !== publicationDate
        || (Number.isFinite(firstSeenAt) && Number.isFinite(editionEnd) && firstSeenAt >= editionEnd)
      ) continue;
      const code = String(item.code);
      const previous = selected.get(code) || {};
      selected.set(code, {
        ...previous,
        ...item,
        current: item.current || previous.current,
        first_seen_at: item.first_seen_at || previous.first_seen_at,
        last_seen_at: item.last_seen_at || previous.last_seen_at,
        active: item.active ?? previous.active ?? true,
      });
    }
    return [...selected.values()]
      .map((item) => {
        const firstSeenAt = stagingKstSignalMoment(item.first_seen_at || item.signal_at || item.updated_at);
        const briefingChange = item.briefing_change || (
          Number.isFinite(firstSeenAt)
          && Number.isFinite(editionStart)
          && firstSeenAt >= editionStart
            ? "신규"
            : "업데이트"
        );
        return { ...item, briefing_change: briefingChange };
      })
      .sort((left, right) => {
        const changeOrder = Number(right.briefing_change === "신규") - Number(left.briefing_change === "신규");
        if (changeOrder) return changeOrder;
        return Number(right.score ?? right.current?.score ?? 0) - Number(left.score ?? left.current?.score ?? 0);
      })
      .slice(0, 3);
  };
  const stagingConfirmedBuysForEdition = (payload = {}) => {
    if (payload.edition !== "afternoon") return [];
    const publicationDate = String(payload.publication_date || payload.published_at || "").slice(0, 10);
    const source = Array.isArray(payload.confirmed_buys)
      ? payload.confirmed_buys
      : (Array.isArray(stagingEditorialSignalPayload?.items) ? stagingEditorialSignalPayload.items : []);
    const selected = new Map();
    for (const item of source) {
      const side = String(item?.side || item?.current?.lifecycle?.latest_transition?.side || "").toLowerCase();
      const preliminary = item?.is_preliminary === true
        || item?.status === "preliminary"
        || ["entry_watch", "entry_pending"].includes(String(item?.current?.action || ""));
      if (!item?.code || side !== "buy" || preliminary || stagingConfirmedBuyDate(item) !== publicationDate) continue;
      if (!selected.has(String(item.code))) selected.set(String(item.code), item);
    }
    return [...selected.values()]
      .sort((left, right) => Number(right.score ?? right.current?.score ?? 0) - Number(left.score ?? left.current?.score ?? 0))
      .slice(0, 3);
  };
  const newsView = document.getElementById("news-view");
  if (newsView) {
    const commandTitle = newsView.querySelector(".news-commandbar h1");
    const newsTitle = document.getElementById("news-page-title");
    if (commandTitle) commandTitle.textContent = "피드";
    if (newsTitle) newsTitle.textContent = "오늘의 피드";

    const feedModes = document.createElement("nav");
    feedModes.className = "staging-feed-modes";
    feedModes.setAttribute("aria-label", "피드 보기");
    feedModes.setAttribute("role", "tablist");
    feedModes.innerHTML = `
      <button class="active" id="staging-feed-news-tab" type="button" role="tab" data-staging-feed-mode="news" aria-selected="true" aria-controls="staging-feed-news-panel">뉴스</button>
      <button id="staging-feed-content-tab" type="button" role="tab" data-staging-feed-mode="content" aria-selected="false" aria-controls="staging-feed-content-panel" tabindex="-1">콘텐츠</button>
      <button id="staging-feed-calendar-tab" type="button" role="tab" data-staging-feed-mode="calendar" aria-selected="false" aria-controls="staging-feed-calendar-panel" tabindex="-1">일정</button>
    `;

    const feedPanels = document.createElement("div");
    feedPanels.className = "staging-feed-panels";
    const newsPanel = document.createElement("section");
    newsPanel.id = "staging-feed-news-panel";
    newsPanel.className = "staging-feed-panel staging-feed-news-panel active";
    newsPanel.dataset.stagingFeedPanel = "news";
    newsPanel.setAttribute("role", "tabpanel");
    newsPanel.setAttribute("aria-labelledby", "staging-feed-news-tab");
    for (const node of [
      document.getElementById("news-page-filters"),
      document.getElementById("news-page-result-meta"),
      document.getElementById("news-page-list"),
    ]) {
      if (node) newsPanel.appendChild(node);
    }

    const contentPanel = document.createElement("section");
    contentPanel.id = "staging-feed-content-panel";
    contentPanel.className = "staging-feed-panel staging-feed-content-panel";
    contentPanel.dataset.stagingFeedPanel = "content";
    contentPanel.setAttribute("role", "tabpanel");
    contentPanel.setAttribute("aria-labelledby", "staging-feed-content-tab");
    contentPanel.hidden = true;
    contentPanel.innerHTML = `
      <header class="staging-feed-section-head">
        <div><span>최근 7일 · 하루 세 번</span><h2>돈이 되는 소식</h2></div>
        <p>아침, 점심, 장 마감 후에 꼭 볼 시장 소식을 한 편씩 정리했어요.</p>
      </header>
      <div class="staging-editorial-feed" data-staging-editorial-feed aria-live="polite">
        <p class="staging-feed-loading">오늘의 콘텐츠를 불러오고 있어요.</p>
      </div>
    `;

    const calendarPanel = document.createElement("section");
    calendarPanel.id = "staging-feed-calendar-panel";
    calendarPanel.className = "staging-feed-panel staging-feed-calendar-panel";
    calendarPanel.dataset.stagingFeedPanel = "calendar";
    calendarPanel.setAttribute("role", "tabpanel");
    calendarPanel.setAttribute("aria-labelledby", "staging-feed-calendar-tab");
    calendarPanel.hidden = true;
    calendarPanel.innerHTML = `
      <header class="staging-calendar-head">
        <h2 data-staging-calendar-month>캘린더</h2>
        <span>${svg(icons.clock)} 현지 기준</span>
      </header>
      <div class="staging-calendar-list" data-staging-calendar-list aria-live="polite">
        <p class="staging-feed-loading">주요 일정을 불러오고 있어요.</p>
      </div>
      <button class="staging-calendar-today" type="button" data-staging-calendar-today>${svg(icons.chevron)}<span>오늘</span></button>
    `;

    feedPanels.append(newsPanel, contentPanel, calendarPanel);
    newsView.querySelector(".news-page-hero")?.insertAdjacentElement("afterend", feedModes);
    feedModes.insertAdjacentElement("afterend", feedPanels);

    const editorialFeed = contentPanel.querySelector("[data-staging-editorial-feed]");
    const calendarList = calendarPanel.querySelector("[data-staging-calendar-list]");
    const calendarMonth = calendarPanel.querySelector("[data-staging-calendar-month]");
    let activeFeedMode = "news";
    let editorialSignature = "";
    let editorialEditions = [];
    let calendarSignature = "";
    let stagingCalendarPayload = null;
    let stagingKoreaCalendarPayload = null;

    const dateKey = (value) => {
      const parsed = value instanceof Date ? value : new Date(value || "");
      if (Number.isNaN(parsed.getTime())) return "";
      const parts = new Intl.DateTimeFormat("en-US", {
        timeZone: "Asia/Seoul",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).formatToParts(parsed).reduce((result, part) => {
        result[part.type] = part.value;
        return result;
      }, {});
      return `${parts.year}-${parts.month}-${parts.day}`;
    };
    const addDays = (key, amount) => {
      const parsed = new Date(`${key}T00:00:00Z`);
      if (Number.isNaN(parsed.getTime())) return "";
      parsed.setUTCDate(parsed.getUTCDate() + amount);
      return parsed.toISOString().slice(0, 10);
    };
    const dateParts = (key) => {
      const parsed = new Date(`${key}T00:00:00Z`);
      if (Number.isNaN(parsed.getTime())) return null;
      const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
      const weekdayIndex = parsed.getUTCDay();
      return {
        year: parsed.getUTCFullYear(),
        month: parsed.getUTCMonth() + 1,
        day: parsed.getUTCDate(),
        weekday: weekdays[weekdayIndex],
        weekend: weekdayIndex === 0 || weekdayIndex === 6,
      };
    };
    const escapeText = (value = "") => String(value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
    const formatFeedTime = (value) => {
      const parsed = new Date(value || "");
      if (Number.isNaN(parsed.getTime())) return "최신판";
      return new Intl.DateTimeFormat("ko-KR", {
        timeZone: "Asia/Seoul",
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      }).format(parsed);
    };
    const formatFeedDay = (value) => {
      const parsed = new Date(value || "");
      if (Number.isNaN(parsed.getTime())) return "날짜 확인 중";
      return new Intl.DateTimeFormat("ko-KR", {
        timeZone: "Asia/Seoul",
        month: "long",
        day: "numeric",
        weekday: "long",
      }).format(parsed);
    };
    const editorialPresentation = stagingBriefingPresentation;
    const editorialPreliminaryBuysMarkup = (payload = {}) => {
      if (!stagingPreliminaryBuyDataAvailableForEdition(payload)) return "";
      const preliminaryBuys = stagingPreliminaryBuysForEdition(payload);
      const rows = preliminaryBuys.map((item) => `
        <div class="staging-editorial-preliminary-buy" data-staging-preliminary-buy-code="${escapeText(item.code)}">
          <strong>${escapeText(item.name || item.code)}</strong>
          <span>${escapeText(item.briefing_change || "업데이트")} · ${escapeText(stagingConfirmedBuyScore(item))}</span>
        </div>
      `).join("");
      return `
        <section class="staging-editorial-preliminary-buys" aria-label="오전 신규 또는 업데이트 예비 매수 종목">
          <header><span>AI 예비 매수</span><strong>신규·업데이트 ${formatNumber(preliminaryBuys.length)}종목</strong></header>
          ${rows || '<p class="staging-editorial-preliminary-buy-empty">오전에 새로 잡히거나 업데이트된 예비 매수는 없었어요.</p>'}
          <p class="staging-editorial-preliminary-buy-note">장 마감 전에는 신호가 바뀔 수 있어요.</p>
        </section>
      `;
    };
    const editorialConfirmedBuysMarkup = (payload = {}) => {
      if (payload.edition !== "afternoon") return "";
      const confirmedBuys = stagingConfirmedBuysForEdition(payload);
      const rows = confirmedBuys.map((item) => `
        <div class="staging-editorial-confirmed-buy" data-staging-confirmed-buy-code="${escapeText(item.code)}">
          <div><strong>${escapeText(item.name || item.code)}</strong><span>확정 매수 · ${escapeText(stagingConfirmedBuyScore(item))}</span></div>
          <p>${escapeText(stagingConfirmedBuyReason(item, 88))}</p>
        </div>
      `).join("");
      return `
        <section class="staging-editorial-confirmed-buys" aria-label="장 마감 확정 매수 종목">
          <header><span>AI 매매 신호</span><strong>오늘 확정 매수 ${formatNumber(confirmedBuys.length)}종목</strong></header>
          ${rows || '<p class="staging-editorial-confirmed-buy-empty">오늘 새로 확정된 매수 종목은 없었어요.</p>'}
        </section>
      `;
    };
    const eventFlag = (item = {}) => {
      const text = `${item.title || ""} ${item.category || ""}`;
      if (/한국|국내|원달러|원\/달러/.test(text)) return "🇰🇷";
      if (/중국|차이신|PMI/.test(text)) return "🇨🇳";
      if (/유럽|ECB|유로/.test(text)) return "🇪🇺";
      if (/미국|연준|FOMC|CPI|PCE|고용|실업/.test(text)) return "🇺🇸";
      return "🌐";
    };
    const editorialArtwork = (index, category = "") => {
      const variants = ["coral", "blue", "mint", "violet"];
      const variant = variants[index % variants.length];
      return `
        <div class="staging-editorial-art is-${variant}" aria-hidden="true">
          <svg viewBox="0 0 640 330" preserveAspectRatio="xMidYMid slice" focusable="false">
            <defs><linearGradient id="feed-gradient-${index}" x1="0" y1="0" x2="1" y2="1"><stop offset="0"/><stop offset="1"/></linearGradient></defs>
            <rect width="640" height="330" rx="32" fill="url(#feed-gradient-${index})"/>
            <path class="grid" d="M60 70H580M60 130H580M60 190H580M60 250H580M120 42V286M220 42V286M320 42V286M420 42V286M520 42V286"/>
            <path class="trend" d="M70 244 145 212 214 228 296 150 366 174 446 96 570 120"/>
            <circle class="point" cx="296" cy="150" r="12"/><circle class="point" cx="446" cy="96" r="12"/>
            <text x="64" y="52">SECRET NOTE · ${escapeText(category || "MARKET BRIEF")}</text>
          </svg>
        </div>
      `;
    };
    const briefingPayload = () => {
      try {
        return typeof state === "object" ? state.morningMoneyBriefing : null;
      } catch {
        return null;
      }
    };
    const calendarPayload = () => {
      if (stagingCalendarPayload) return stagingCalendarPayload;
      try {
        return typeof state === "object" ? {
          events: state.trendEventsItems || [],
          past_events: state.trendPastEventsItems || [],
        } : null;
      } catch {
        return null;
      }
    };
    const renderEditorialFeed = () => {
      const currentPayload = briefingPayload();
      if (!editorialFeed) return;
      const rows = (editorialEditions.length ? editorialEditions : [currentPayload])
        .filter((payload) => payload && payload.edition_key)
        .sort((left, right) => new Date(right.published_at || 0) - new Date(left.published_at || 0));
      const latestPublicationDate = String(rows[0]?.publication_date || "");
      const latestEditions = rows
        .filter((payload) => String(payload?.publication_date || "") === latestPublicationDate)
        .slice(0, 3);
      const signature = rows.map((payload) => {
        const buys = stagingConfirmedBuysForEdition(payload);
        const preliminaryBuys = stagingPreliminaryBuysForEdition(payload);
        const preliminaryAvailable = stagingPreliminaryBuyDataAvailableForEdition(payload);
        return `${payload.edition_key}:${payload.selected_news_count || 0}:${preliminaryAvailable}:${preliminaryBuys.map((item) => `${item.code}:${item.briefing_change}:${item.score || ""}`).join(",")}:${buys.map((item) => `${item.code}:${item.score || ""}`).join(",")}`;
      }).join("|");
      const shouldApplyGptCopy = stagingGptPageSummaryEnabled
        && activeFeedMode === "content"
        && (document.body.dataset.view || "") === "news";
      const applyLatestGptCopy = () => {
        if (!shouldApplyGptCopy) return;
        for (const payload of latestEditions) {
          void applyStagingBriefingCardSummary(payload, editorialFeed);
        }
      };
      if (signature === editorialSignature) {
        applyLatestGptCopy();
        return;
      }
      editorialSignature = signature;
      if (!rows.length) {
        editorialFeed.innerHTML = `<section class="staging-feed-empty"><strong>최근 콘텐츠를 준비하고 있어요</strong><p>${escapeText(currentPayload?.empty_message || "발행된 브리핑이 확인되면 자동으로 표시됩니다.")}</p></section>`;
        return;
      }
      const grouped = rows.reduce((result, payload) => {
        const key = payload.publication_date || dateKey(payload.published_at) || "unknown";
        const group = result.find((item) => item.key === key);
        if (group) group.items.push(payload);
        else result.push({ key, items: [payload] });
        return result;
      }, []);
      let cardIndex = 0;
      editorialFeed.innerHTML = grouped.map((group) => {
        const first = group.items[0] || {};
        const cards = group.items.map((payload) => {
          const presentation = editorialPresentation(payload);
          const highlights = (Array.isArray(payload.highlights) ? payload.highlights : [])
            .map((item) => String(item?.title || "").trim())
            .filter(Boolean)
            .slice(0, 3);
          const summary = highlights.length ? highlights.join(" · ") : presentation.accent;
          const index = cardIndex;
          cardIndex += 1;
          return `
            <article class="staging-editorial-post" data-staging-edition="${escapeText(payload.edition_key)}">
              <button type="button" data-staging-content-open data-staging-content-key="${escapeText(payload.edition_key)}" aria-label="${escapeText(presentation.feedTitle)} 전체 내용 읽기">
                <header class="staging-editorial-author">
                  <span class="staging-editorial-avatar" aria-hidden="true">${svg(icons.briefing)}</span>
                  <p><strong>${escapeText(presentation.feedTitle)}</strong><small>${escapeText(presentation.label)} · ${escapeText(formatFeedTime(payload.published_at))}</small></p>
                </header>
                <h3>${escapeText(presentation.title)}</h3>
                <p class="staging-editorial-summary">${escapeText(summary)}</p>
                ${editorialPreliminaryBuysMarkup(payload)}
                ${editorialConfirmedBuysMarkup(payload)}
                ${editorialArtwork(index, `${presentation.label} BRIEF`)}
                <footer><span>핵심 소식 ${formatNumber(payload.selected_news_count || 0)}건 전체 읽기</span>${svg(icons.chevron)}</footer>
              </button>
            </article>
          `;
        }).join("");
        return `
          <section class="staging-editorial-day" data-staging-editorial-day="${escapeText(group.key)}">
            <header class="staging-editorial-day-head"><h3>${escapeText(formatFeedDay(first.published_at))}</h3><span>${formatNumber(group.items.length)}개 발행</span></header>
            ${cards}
          </section>
        `;
      }).join("");
      applyLatestGptCopy();
    };
    const renderCalendar = () => {
      const payload = calendarPayload() || {};
      const koreaPayload = stagingKoreaCalendarPayload || {};
      if (!calendarList) return;
      const events = [
        ...(Array.isArray(payload.past_events) ? payload.past_events : []),
        ...(Array.isArray(payload.events) ? payload.events : []),
        ...(Array.isArray(koreaPayload.past_events) ? koreaPayload.past_events : []),
        ...(Array.isArray(koreaPayload.events) ? koreaPayload.events : []),
      ]
        .filter((item, index, rows) => item?.starts_at && rows.findIndex((candidate) => String(candidate?.id || `${candidate?.title}|${candidate?.starts_at}`) === String(item?.id || `${item?.title}|${item?.starts_at}`)) === index);
      const today = dateKey(new Date());
      const keys = Array.from({ length: 18 }, (_, index) => addDays(today, index - 2));
      const signature = `${today}:${events.map((item) => `${item.id || item.title}:${item.starts_at}`).join("|")}`;
      if (signature === calendarSignature) return;
      calendarSignature = signature;
      const first = dateParts(keys[0]);
      const last = dateParts(keys[keys.length - 1]);
      if (calendarMonth && first && last) {
        calendarMonth.textContent = first.month === last.month
          ? `${first.year}년 ${first.month}월`
          : `${first.year}년 ${first.month}월 – ${last.month}월`;
      }
      calendarList.innerHTML = keys.map((key) => {
        const parts = dateParts(key);
        const dayEvents = events.filter((item) => dateKey(item.starts_at) === key);
        const eventMarkup = dayEvents.map((item) => {
          const holiday = /휴장|휴일|연휴/.test(String(item.title || ""));
          return `<article class="staging-calendar-event${holiday ? " is-holiday" : ""}"><span aria-hidden="true">${eventFlag(item)}</span><div><strong>${escapeText(item.title || "주요 일정")}</strong>${item.expected_impact ? `<small>${escapeText(item.expected_impact)}</small>` : ""}</div></article>`;
        }).join("");
        return `
          <section class="staging-calendar-day${parts?.weekend ? " is-weekend" : ""}${key === today ? " is-today" : ""}" data-staging-calendar-date="${key}">
            <time datetime="${key}"><strong>${parts?.day || ""}</strong><span>${parts?.weekday || ""}</span></time>
            <div class="staging-calendar-events">${eventMarkup}</div>
          </section>
        `;
      }).join("");
    };
    const activateFeedMode = (mode, options = {}) => {
      activeFeedMode = ["content", "calendar"].includes(mode) ? mode : "news";
      for (const button of feedModes.querySelectorAll("[data-staging-feed-mode]")) {
        const selected = button.dataset.stagingFeedMode === activeFeedMode;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-selected", String(selected));
        button.tabIndex = selected ? 0 : -1;
      }
      for (const panel of feedPanels.querySelectorAll("[data-staging-feed-panel]")) {
        const selected = panel.dataset.stagingFeedPanel === activeFeedMode;
        panel.hidden = !selected;
        panel.classList.toggle("active", selected);
      }
      if (activeFeedMode === "content") renderEditorialFeed();
      if (activeFeedMode === "calendar") renderCalendar();
      if (options.scroll !== false) window.scrollTo({ top: 0, behavior: "auto" });
    };
    feedModes.addEventListener("click", (event) => {
      const control = event.target instanceof Element ? event.target.closest("[data-staging-feed-mode]") : null;
      if (!control) return;
      activateFeedMode(control.dataset.stagingFeedMode);
    });
    contentPanel.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target : null;
      const control = target?.closest("[data-staging-content-open]");
      if (!control) return;
      event.preventDefault();
      const selected = editorialEditions.find((payload) => payload.edition_key === control.dataset.stagingContentKey);
      if (selected && typeof window.openMorningMoneyBriefingEdition === "function") {
        window.openMorningMoneyBriefingEdition({
          ...selected,
          preliminary_buys: stagingPreliminaryBuysForEdition(selected),
          preliminary_buys_available: stagingPreliminaryBuyDataAvailableForEdition(selected),
          confirmed_buys: stagingConfirmedBuysForEdition(selected),
        });
      } else {
        routeButton("morning-briefing")?.click();
      }
      window.scrollTo({ top: 0, behavior: "auto" });
    });
    calendarPanel.querySelector("[data-staging-calendar-today]")?.addEventListener("click", () => {
      calendarList.querySelector(`[data-staging-calendar-date="${dateKey(new Date())}"]`)?.scrollIntoView({ block: "start", behavior: "smooth" });
    });

    const requestFeedData = async () => {
      for (let attempt = 0; attempt < 80; attempt += 1) {
        if (typeof loadMorningMoneyBriefing === "function" && typeof fetchJsonCached === "function") {
          try {
            await loadMorningMoneyBriefing({ render: false, force: false });
          } catch {
            // The current-edition popup remains independent from the history feed.
          }
          try {
            const historyPayload = await fetchJsonCached("/briefings/morning-money/history?days=7", { ttlMs: 120_000, timeoutMs: 25_000 });
            editorialEditions = Array.isArray(historyPayload) ? historyPayload : [];
          } catch {
            editorialEditions = [];
          }
          try {
            const signalPayload = await fetchJsonCached("/market/quant-signals?universe_limit=150&limit=0&recent_days=30", { ttlMs: 120_000, timeoutMs: 25_000 });
            stagingEditorialSignalPayload = signalPayload && typeof signalPayload === "object"
              ? signalPayload
              : null;
          } catch {
            stagingEditorialSignalPayload = null;
          }
          try {
            stagingCalendarPayload = await fetchJsonCached("/market/trends?days=14", { ttlMs: 120_000, timeoutMs: 20_000 });
          } catch {
            stagingCalendarPayload = null;
          }
          try {
            stagingKoreaCalendarPayload = await fetchJsonCached("/market/calendar?days=14", { ttlMs: 300_000, timeoutMs: 12_000 });
          } catch {
            stagingKoreaCalendarPayload = null;
          }
          renderEditorialFeed();
          renderCalendar();
          decorateStagingBriefingArticle();
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 50));
      }
    };
    syncStagingFeed = () => {
      renderEditorialFeed();
      renderCalendar();
      if ((document.body.dataset.view || "") === "news") activateFeedMode(activeFeedMode, { scroll: false });
    };
    activateFeedMode("news", { scroll: false });
    window.addEventListener("load", () => void requestFeedData(), { once: true });
  }

  const decorateStagingBriefingArticle = () => {
    const view = document.getElementById("morning-money-briefing-view");
    const overview = view?.querySelector(".morning-money-overview");
    if (!view || !overview) return;
    view.classList.add("staging-editorial-detail");
    let payload = null;
    try {
      payload = typeof state === "object"
        ? (state.morningMoneyBriefingSelection || state.morningMoneyBriefing)
        : null;
    } catch {
      payload = null;
    }

    let tag = overview.querySelector(".staging-article-tag");
    if (!tag) {
      tag = document.createElement("span");
      tag.className = "staging-article-tag";
      tag.textContent = "#비밀노트 리서치";
      overview.prepend(tag);
    }

    const heading = overview.querySelector(".morning-money-overview-head");
    let meta = overview.querySelector(".staging-article-meta");
    if (!meta) {
      meta = document.createElement("p");
      meta.className = "staging-article-meta";
      heading?.insertAdjacentElement("afterend", meta);
    }
    const selectedCount = Number(payload?.selected_news_count || 0);
    const briefingTitle = stagingBriefingTitle(payload?.edition);
    const sourceCommandTitle = view.querySelector(".morning-money-command-title h1");
    if (sourceCommandTitle) sourceCommandTitle.textContent = briefingTitle;
    const published = payload?.published_at ? new Date(payload.published_at) : null;
    const dateLabel = published && !Number.isNaN(published.getTime())
      ? new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).format(published)
      : "발행일 확인 중";
    if (meta) meta.textContent = `${dateLabel} · 핵심 소식 ${formatNumber(selectedCount)}건`;

    let author = overview.querySelector(".staging-article-author");
    if (!author) {
      author = document.createElement("section");
      author.className = "staging-article-author";
      author.innerHTML = `
        <span class="staging-article-author-mark" aria-hidden="true">${svg(icons.briefing)}</span>
        <p><strong>안녕하세요, 비밀노트 에디터입니다.</strong><span>시장과 내 돈에 영향을 줄 소식을 빠르게 읽을 수 있도록 정리했어요.</span></p>
      `;
      meta?.insertAdjacentElement("afterend", author);
    }

    const intro = overview.querySelector(".morning-money-overview-intro");
    if (intro) intro.classList.add("staging-article-lead");

    let preliminaryBuySection = overview.querySelector(".staging-article-preliminary-buys");
    if (stagingPreliminaryBuyDataAvailableForEdition(payload || {})) {
      const preliminaryBuys = stagingPreliminaryBuysForEdition(payload);
      if (!preliminaryBuySection) {
        preliminaryBuySection = document.createElement("section");
        preliminaryBuySection.className = "staging-article-preliminary-buys";
        preliminaryBuySection.setAttribute("aria-labelledby", "staging-article-preliminary-buy-title");
        overview.querySelector(".morning-money-digest")?.insertAdjacentElement("afterend", preliminaryBuySection);
      }
      const signature = preliminaryBuys.map((item) => `${item.code}:${item.briefing_change}:${item.score || ""}:${stagingPreliminaryBuyReason(item)}`).join("|");
      if (preliminaryBuySection.dataset.signature !== signature) {
        preliminaryBuySection.dataset.signature = signature;
        preliminaryBuySection.replaceChildren();
        const sectionHead = document.createElement("header");
        sectionHead.innerHTML = `<span>오전의 AI 매매 신호</span><h3 id="staging-article-preliminary-buy-title">신규·업데이트 예비 매수</h3><p>오전 중 새로 잡히거나 조건이 갱신된 종목이에요. 장 마감 전에는 바뀔 수 있어요.</p>`;
        preliminaryBuySection.appendChild(sectionHead);
        if (!preliminaryBuys.length) {
          const empty = document.createElement("p");
          empty.className = "staging-article-preliminary-buy-empty";
          empty.textContent = "오전에 새로 잡히거나 업데이트된 예비 매수는 없었어요.";
          preliminaryBuySection.appendChild(empty);
        } else {
          const list = document.createElement("div");
          list.className = "staging-article-preliminary-buy-list";
          for (const item of preliminaryBuys) {
            const link = document.createElement("a");
            link.className = "staging-article-preliminary-buy";
            link.href = `/dashboard/${encodeURIComponent(item.code)}`;
            link.setAttribute("aria-label", `${item.name || item.code} ${item.briefing_change || "업데이트"} 예비 매수 근거와 종목 상세 보기`);
            const identity = document.createElement("div");
            identity.append(
              createStockLogoFrame(item.code, "staging-article-preliminary-buy-logo"),
              Object.assign(document.createElement("strong"), { textContent: item.name || item.code }),
              Object.assign(document.createElement("span"), { textContent: `${item.briefing_change || "업데이트"} · ${stagingConfirmedBuyScore(item)}` }),
            );
            const reason = document.createElement("p");
            reason.textContent = stagingPreliminaryBuyReason(item);
            link.append(identity, reason, Object.assign(document.createElement("span"), { className: "staging-article-preliminary-buy-arrow", textContent: "›" }));
            list.appendChild(link);
          }
          preliminaryBuySection.appendChild(list);
        }
      }
    } else {
      preliminaryBuySection?.remove();
    }

    let confirmedBuySection = overview.querySelector(".staging-article-confirmed-buys");
    if (payload?.edition === "afternoon") {
      const confirmedBuys = stagingConfirmedBuysForEdition(payload);
      if (!confirmedBuySection) {
        confirmedBuySection = document.createElement("section");
        confirmedBuySection.className = "staging-article-confirmed-buys";
        confirmedBuySection.setAttribute("aria-labelledby", "staging-article-confirmed-buy-title");
        overview.querySelector(".morning-money-digest")?.insertAdjacentElement("afterend", confirmedBuySection);
      }
      const signature = confirmedBuys.map((item) => `${item.code}:${item.score || ""}:${stagingConfirmedBuyReason(item)}`).join("|");
      if (confirmedBuySection.dataset.signature !== signature) {
        confirmedBuySection.dataset.signature = signature;
        confirmedBuySection.replaceChildren();
        const sectionHead = document.createElement("header");
        sectionHead.innerHTML = `<span>오늘의 AI 매매 신호</span><h3 id="staging-article-confirmed-buy-title">장 마감 확정 매수</h3><p>종가 기준 조건을 통과해 확정된 종목과 실제 판단 근거예요.</p>`;
        confirmedBuySection.appendChild(sectionHead);
        if (!confirmedBuys.length) {
          const empty = document.createElement("p");
          empty.className = "staging-article-confirmed-buy-empty";
          empty.textContent = "오늘 새로 확정된 매수 종목은 없었어요.";
          confirmedBuySection.appendChild(empty);
        } else {
          const list = document.createElement("div");
          list.className = "staging-article-confirmed-buy-list";
          for (const item of confirmedBuys) {
            const link = document.createElement("a");
            link.className = "staging-article-confirmed-buy";
            link.href = `/dashboard/${encodeURIComponent(item.code)}`;
            link.setAttribute("aria-label", `${item.name || item.code} 확정 매수 근거와 종목 상세 보기`);
            const identity = document.createElement("div");
            identity.append(
              createStockLogoFrame(item.code, "staging-article-confirmed-buy-logo"),
              Object.assign(document.createElement("strong"), { textContent: item.name || item.code }),
              Object.assign(document.createElement("span"), { textContent: `확정 매수 · ${stagingConfirmedBuyScore(item)}` }),
            );
            const reason = document.createElement("p");
            reason.textContent = stagingConfirmedBuyReason(item);
            link.append(identity, reason, Object.assign(document.createElement("span"), { className: "staging-article-confirmed-buy-arrow", textContent: "›" }));
            list.appendChild(link);
          }
          confirmedBuySection.appendChild(list);
        }
      }
    } else {
      confirmedBuySection?.remove();
    }
    for (const [index, section] of Array.from(view.querySelectorAll(".morning-money-category-section")).entries()) {
      section.dataset.stagingArticleSection = String(index + 1).padStart(2, "0");
      const header = section.querySelector(".morning-money-category-head");
      if (header && !header.querySelector(".staging-article-section-index")) {
        const marker = document.createElement("span");
        marker.className = "staging-article-section-index";
        marker.textContent = String(index + 1).padStart(2, "0");
        header.prepend(marker);
      }
    }
    if (
      stagingGptPageSummaryEnabled
      && (document.body.dataset.view || "") === "morning-briefing"
    ) void applyStagingBriefingArticleSummary(payload || {});
  };

  const aiSignalsView = document.getElementById("ai-signals-view");
  if (aiSignalsView) {
    const modeTabs = document.getElementById("ai-signal-mode-tabs");
    if (modeTabs && !aiSignalsView.querySelector(".staging-ai-signals-intro")) {
      const intro = document.createElement("header");
      intro.className = "staging-ai-signals-intro";
      intro.setAttribute("aria-labelledby", "staging-ai-signals-title");
      intro.innerHTML = `
        <span>시총 Top 100 에서</span>
        <h2 id="staging-ai-signals-title">AI는 무엇을 사고 팔까?</h2>
      `;
      modeTabs.insertAdjacentElement("beforebegin", intro);
    }
    const stageLabels = {
      all: "전체",
      "buy-holding": "매수 확정",
      "recent-sell": "매도 확정",
      "preliminary-buy": "매수 대기",
      "preliminary-sell": "매도 대기",
    };
    for (const tab of aiSignalsView.querySelectorAll("[data-ai-signal-stage]")) {
      const count = tab.querySelector("span");
      const label = stageLabels[tab.dataset.aiSignalStage];
      if (label && count) tab.replaceChildren(document.createTextNode(`${label} `), count);
    }
  }

  const chartView = document.getElementById("chart-view");
  if (chartView && !chartView.querySelector(".staging-chart-commandbar")) {
    const commandbar = document.createElement("header");
    commandbar.className = "secondary-commandbar staging-chart-commandbar";
    commandbar.innerHTML = `
      <button class="secondary-commandbar-back" id="chart-back" type="button" data-staging-view="search" aria-label="발견으로 돌아가기">←</button>
      <h1>차트 분석</h1>
      <span class="secondary-commandbar-spacer" aria-hidden="true"></span>
    `;
    chartView.prepend(commandbar);
  }

  const contextualViewConfig = Object.freeze({
    "recent-stocks": {
      title: "최근 본 종목",
      owner: "search",
    },
    "ai-stock-response": {
      title: "AI 종목 대응",
      owner: "home",
    },
    "ai-signals": {
      title: "AI 시그널",
      source: "#ai-signals-view .ai-signals-commandbar",
      back: "#ai-signals-back",
      owner: "home",
    },
    movers: {
      title: "TOP 50",
      titleSelector: "#market-ranking-command-title",
      source: "#market-view .market-ranking-commandbar",
      back: "#market-ranking-back",
      owner: "home",
    },
    chart: {
      title: "차트 분석",
      source: "#chart-view .staging-chart-commandbar",
      back: "#chart-back",
      owner: "search",
    },
    "chart-study": {
      title: "차트 공부",
      source: "#chart-study-view .chart-study-commandbar",
      back: "#chart-study-back",
      owner: "chart",
    },
    "chart-history": {
      title: "지난 차트 분석",
      source: "#chart-history-view .chart-history-commandbar",
      back: "#chart-history-back-button",
      owner: "search",
    },
    "morning-briefing": {
      title: "오늘의 돈이 되는 소식",
      titleSelector: "#morning-money-briefing-view .morning-money-command-title h1",
      source: "#morning-money-briefing-view .morning-money-commandbar",
      back: "#morning-money-briefing-back",
      owner: "news",
    },
    notifications: {
      title: "알림",
      titleSelector: "#push-history-title",
      source: "#notifications-view .notifications-commandbar",
      back: "#push-history-back",
      action: "#push-history-settings",
      owner: "home",
    },
    "event-detail": {
      title: "이벤트 분석",
      source: "#event-detail-view .event-detail-commandbar",
      back: "#event-detail-back",
      owner: "news",
    },
    "recommend-detail": {
      title: "추천 종목",
      titleSelector: "#recommend-detail-name",
      source: "#recommend-detail-page .recommend-detail-topbar",
      back: "#recommend-detail-back",
      owner: "search",
    },
  });

  for (const config of Object.values(contextualViewConfig)) {
    if (!config.source) continue;
    const source = document.querySelector(config.source);
    if (!source) continue;
    source.classList.add("staging-proxied-commandbar");
    source.setAttribute("aria-hidden", "true");
  }

  let activeContextualView = "";
  const contextualBack = contextualTopbar.querySelector("[data-staging-contextual-back]");
  const contextualAction = contextualTopbar.querySelector("[data-staging-contextual-action]");

  contextualBack?.addEventListener("click", () => {
    const config = contextualViewConfig[activeContextualView];
    if (activeContextualView === STAGING_AI_STOCK_RESPONSE_VIEW) {
      if (window.history.state?.stagingPanel === STAGING_AI_STOCK_RESPONSE_VIEW) {
        window.history.back();
      } else {
        const url = new URL(window.location.href);
        url.pathname = "/dashboard";
        url.searchParams.set("view", "home");
        url.searchParams.delete("code");
        window.history.replaceState(
          { ...(window.history.state || {}), stagingPanel: null, responseCode: null },
          "",
          url,
        );
        if (typeof setView === "function") setView("home", { historyMode: "none" });
        closeStagingAiStockResponse();
      }
      return;
    }
    if (activeContextualView === "recent-stocks") {
      if (window.history.state?.stagingPanel === "recent-stocks") {
        window.history.back();
      } else {
        const url = new URL(window.location.href);
        url.pathname = "/dashboard";
        url.search = "?view=search";
        window.history.replaceState({ ...(window.history.state || {}), stagingPanel: null }, "", url);
        syncShell();
        window.scrollTo({ top: 0, behavior: "auto" });
      }
      return;
    }
    const sourceBack = config ? document.querySelector(config.back) : null;
    if (["chart-study", "chart-history"].includes(activeContextualView) && sourceBack instanceof HTMLButtonElement) {
      sourceBack.click();
      return;
    }
    const trackedOwner = contextualOwners.get(activeContextualView);
    if (trackedOwner) {
      window.history.back();
      return;
    }
    const ownerButton = config ? bottomNav.querySelector(`[data-app-view="${config.owner}"]`) : null;
    if (ownerButton instanceof HTMLButtonElement) ownerButton.click();
  });

  contextualAction?.addEventListener("click", () => {
    const config = contextualViewConfig[activeContextualView];
    const sourceAction = config?.action ? document.querySelector(config.action) : null;
    if (sourceAction instanceof HTMLButtonElement) sourceAction.click();
  });

  let stockHero = null;

  const stockTabs = document.querySelector("#stock-view .stock-detail-tabs");
  const stockSummaryPanel = document.getElementById("stock-summary-section");
  const stockCompanyPanel = document.getElementById("stock-company-section");
  const stockStrategyPanel = document.getElementById("stock-strategy-section");
  if (stockTabs && stockSummaryPanel && stockCompanyPanel && stockStrategyPanel) {
    const summaryTab = stockTabs.querySelector('[data-stock-tab="summary"]');
    const companyTab = stockTabs.querySelector('[data-stock-tab="company"]');
    const strategyTab = stockTabs.querySelector('[data-stock-tab="strategy"]');
    if (summaryTab) summaryTab.textContent = "차트";
    if (companyTab) companyTab.textContent = "종목정보";
    if (strategyTab) strategyTab.textContent = "AI 시그널";

    const stockSearchButton = document.querySelector("#stock-form > button");
    if (stockSearchButton) {
      stockSearchButton.classList.add("staging-stock-nav-search");
      stockSearchButton.setAttribute("aria-label", "종목 검색 열기");
      stockSearchButton.setAttribute("aria-controls", "stock-code");
      stockSearchButton.setAttribute("aria-expanded", "false");
      stockSearchButton.innerHTML = svg(icons.stockSearch, "staging-stock-search-glyph");

      const stockSearchForm = stockSearchButton.closest("form");
      const stockSearchBox = stockSearchForm?.querySelector(".search-box");
      const stockSearchInput = stockSearchBox?.querySelector("input");
      const stockSuggestions = stockSearchBox?.querySelector(".suggestions");
      if (stockSearchForm && stockSearchBox && stockSearchInput) {
        stockSearchInput.placeholder = "종목명 또는 종목코드 검색";
        const leadingIcon = document.createElement("span");
        leadingIcon.className = "staging-stock-search-leading";
        leadingIcon.setAttribute("aria-hidden", "true");
        leadingIcon.innerHTML = svg(icons.search);
        stockSearchBox.prepend(leadingIcon);

        const closeSearch = document.createElement("button");
        closeSearch.type = "button";
        closeSearch.className = "staging-stock-search-close";
        closeSearch.setAttribute("aria-label", "종목 검색 닫기");
        closeSearch.textContent = "취소";
        stockSearchBox.insertBefore(closeSearch, stockSuggestions || null);

        const syncStockSearchState = () => {
          const expanded = stockSearchForm.classList.contains("expanded");
          stockSearchButton.setAttribute("aria-expanded", String(expanded));
          stockSearchBox.setAttribute("aria-hidden", String(!expanded));
        };
        stockSearchButton.addEventListener("click", (event) => {
          if (stockSearchForm.classList.contains("expanded")) return;
          event.preventDefault();
          stockSearchForm.classList.add("expanded");
          syncStockSearchState();
          window.requestAnimationFrame(() => {
            stockSearchInput.focus();
            stockSearchInput.select();
          });
        });
        closeSearch.addEventListener("click", (event) => {
          event.preventDefault();
          stockSearchForm.classList.remove("expanded");
          if (stockSuggestions) {
            stockSuggestions.hidden = true;
            stockSuggestions.replaceChildren();
          }
          stockSearchInput.setAttribute("aria-expanded", "false");
          stockSearchInput.blur();
          syncStockSearchState();
          stockSearchButton.focus();
        });
        new MutationObserver(syncStockSearchState).observe(stockSearchForm, {
          attributes: true,
          attributeFilter: ["class"],
        });
        syncStockSearchState();
      }
    }

    const createStockTab = (id, key, label) => {
      const tab = document.createElement("button");
      tab.id = `${id}-tab`;
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.dataset.stockTab = key;
      tab.setAttribute("aria-controls", `${id}-panel`);
      tab.setAttribute("aria-selected", "false");
      tab.textContent = label;
      return tab;
    };
    const createStockPanel = (id, key) => {
      const panel = document.createElement("section");
      panel.id = `${id}-panel`;
      panel.className = `stock-tab-panel staging-stock-secondary-panel stock-v3-${key}`;
      panel.dataset.stockPanel = key;
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", `${id}-tab`);
      panel.hidden = true;
      return panel;
    };

    const newsTab = createStockTab("stock-news", "news", "소식");
    const communityTab = createStockTab("stock-community", "community", "커뮤니티");
    const newsPanel = createStockPanel("stock-news", "news");
    const communityPanel = createStockPanel("stock-community", "community");
    stockTabs.replaceChildren(summaryTab, strategyTab, newsTab, companyTab, communityTab);

    const panelParent = stockStrategyPanel.parentElement;
    if (panelParent) {
      panelParent.insertBefore(newsPanel, stockCompanyPanel);
      panelParent.insertBefore(communityPanel, stockCompanyPanel.nextSibling);
    }

    const newsNodes = [
      document.getElementById("stock-home-updates")?.closest("article"),
      document.getElementById("stock-home-disclosures")?.closest("article"),
      stockSummaryPanel.querySelector(".stock-v3-issues"),
      document.getElementById("stock-research-section"),
      document.getElementById("stock-news-section"),
      stockSummaryPanel.querySelector(".stock-v3-news-temperature-section"),
    ];
    for (const node of newsNodes) if (node) newsPanel.appendChild(node);
    const communitySection = document.getElementById("stock-community-section");
    if (communitySection) communityPanel.appendChild(communitySection);
    const companyProfile = document.getElementById("stock-company-profile");
    if (companyProfile) stockCompanyPanel.prepend(companyProfile);

    const quoteCard = document.querySelector("#stock-view .stock-v3-quote-card");
    if (quoteCard) stockSummaryPanel.prepend(quoteCard);
    const sentinel = document.getElementById("stock-detail-tabs-sentinel");
    stockHero = document.createElement("section");
    stockHero.className = "staging-stock-hero";
    stockHero.setAttribute("aria-label", "현재 종목 시세");
    stockHero.innerHTML = `
      <div class="staging-stock-hero-name-row">
        <h2 data-staging-stock-name>종목 분석</h2>
      </div>
      <p class="staging-stock-hero-price"><strong data-staging-stock-price>-</strong><span>원</span></p>
      <p class="staging-stock-hero-change">
        <span data-staging-stock-change-context>최근 장에서</span>
        <strong data-staging-stock-change>-</strong>
        <strong data-staging-stock-rate></strong>
      </p>
    `;
    const stockTitleLogo = document.getElementById("stock-title-logo");
    const stockHeroNameRow = stockHero.querySelector(".staging-stock-hero-name-row");
    if (stockTitleLogo && stockHeroNameRow) stockHeroNameRow.prepend(stockTitleLogo);
    const marketStatusButton = document.getElementById("stock-pre-market");
    if (marketStatusButton) {
      marketStatusButton.classList.add("staging-stock-market-status");
      const orderability = document.createElement("span");
      orderability.className = "staging-stock-orderability";
      orderability.setAttribute("aria-live", "polite");
      orderability.textContent = "장 상태 확인 중";
      const separator = document.createElement("span");
      separator.className = "staging-stock-status-separator";
      separator.setAttribute("aria-hidden", "true");
      separator.textContent = "·";
      marketStatusButton.prepend(orderability, separator);
      stockHero.appendChild(marketStatusButton);
    }
    if (sentinel?.parentElement) sentinel.parentElement.insertBefore(stockHero, sentinel);

    const stockBack = document.getElementById("stock-detail-back");
    const stockStar = document.getElementById("watch-toggle");
    const stockSearch = document.getElementById("stock-form");
    if (stockSearch && stockStar && stockSearch.parentElement === stockStar.parentElement) {
      stockStar.parentElement.insertBefore(stockSearch, stockStar);
    }
    if (stockBack) stockBack.innerHTML = svg(icons.back);
    if (stockStar) stockStar.innerHTML = svg(icons.interest);

    const activateStagingSecondaryTab = (tab, panel) => {
      for (const control of stockTabs.querySelectorAll("[data-stock-tab]")) {
        const active = control === tab;
        control.classList.toggle("active", active);
        control.setAttribute("aria-selected", String(active));
      }
      for (const panelNode of document.querySelectorAll("#stock-view [data-stock-panel]")) {
        panelNode.hidden = panelNode !== panel;
      }
      stockTabs.dataset.stagingActiveTab = tab.dataset.stockTab || "";
      window.requestAnimationFrame(scheduleStockScrollChrome);
    };
    const anchorStockTabToTop = () => {
      const commandbar = document.querySelector("#stock-view .stock-v3-commandbar");
      const tabsSentinel = document.getElementById("stock-detail-tabs-sentinel");
      if (!commandbar || !tabsSentinel || window.innerWidth > 980) return;
      const pinnedTop = commandbar.getBoundingClientRect().height || 68;
      const targetTop = Math.max(0, window.scrollY + tabsSentinel.getBoundingClientRect().top - pinnedTop);
      window.scrollTo({ top: Math.round(targetTop), behavior: "auto" });
      window.requestAnimationFrame(scheduleStockScrollChrome);
    };
    stockTabs.addEventListener("click", (event) => {
      const tab = event.target instanceof Element ? event.target.closest("[data-stock-tab]") : null;
      if (!(tab instanceof HTMLButtonElement) || tab.parentElement !== stockTabs) return;
      const alreadyActive = tab.classList.contains("active") || tab.getAttribute("aria-selected") === "true";
      if (!alreadyActive) window.requestAnimationFrame(anchorStockTabToTop);
    }, { capture: true });
    for (const [tab, panel] of [[newsTab, newsPanel], [communityTab, communityPanel]]) {
      tab.addEventListener("click", (event) => {
        event.preventDefault();
        activateStagingSecondaryTab(tab, panel);
      });
    }
    for (const tab of [summaryTab, strategyTab, companyTab]) {
      tab?.addEventListener("click", () => {
        newsPanel.hidden = true;
        communityPanel.hidden = true;
        newsTab.classList.remove("active");
        communityTab.classList.remove("active");
        newsTab.setAttribute("aria-selected", "false");
        communityTab.setAttribute("aria-selected", "false");
        stockTabs.dataset.stagingActiveTab = tab.dataset.stockTab || "";
      });
    }

  }

  const STAGING_STOCK_CHART_PERIODS = Object.freeze([
    { key: "1D", label: "1일", count: 0 },
    { key: "1W", label: "1주", count: Number.POSITIVE_INFINITY },
    { key: "3M", label: "3달", count: 66 },
    { key: "1Y", label: "1년", count: 260 },
    { key: "5Y", label: "5년", count: 1300 },
    { key: "ALL", label: "전체", count: Number.POSITIVE_INFINITY },
  ]);
  const stagingChartNumber = new Intl.NumberFormat("ko-KR", {
    maximumFractionDigits: 0,
  });
  let stagingSelectedChartPeriod = "1D";
  let stagingSelectedChartType = "line";
  const STAGING_WEEK_CHART_TTL_MS = 30_000;
  const stagingWeekChartCache = new Map();
  const STAGING_LIVE_INTRADAY_SESSIONS = new Set([
    "nxt_pre_market",
    "nxt_after_market",
  ]);
  const STAGING_LIVE_INTRADAY_CACHE_KEYS = 8;
  const stagingLiveIntradayRows = new Map();

  const stagingChartNumeric = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };

  const stagingChartClamp = (value, minimum, maximum) => (
    Math.min(maximum, Math.max(minimum, value))
  );

  const stagingChartDateKey = (value) => {
    const text = String(value || "").trim();
    const digits = text.replace(/[^0-9]/g, "");
    if (digits.length >= 8) {
      return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`;
    }
    return "";
  };

  const stagingChartDateLabel = (value) => {
    const key = stagingChartDateKey(value);
    return key ? key.replaceAll("-", ".") : "날짜 확인 중";
  };

  const stagingChartTimeLabel = (value) => {
    const digits = String(value || "").replace(/[^0-9]/g, "").padStart(6, "0");
    return `${digits.slice(0, 2)}:${digits.slice(2, 4)}`;
  };

  const stagingNormalizeWeekChart = (payload) => {
    const groups = payload?.priceInfos && typeof payload.priceInfos === "object"
      ? Object.entries(payload.priceInfos)
      : [];
    const rows = groups.flatMap(([groupDate, values]) => (
      (Array.isArray(values) ? values : []).map((row) => {
        const timestamp = String(row?.localDateTime || "").replace(/[^0-9]/g, "");
        const date = stagingChartDateKey(timestamp.slice(0, 8) || groupDate);
        const time = timestamp.length >= 12 ? `${timestamp.slice(8, 12)}00` : "";
        const close = stagingChartNumeric(row?.currentPrice);
        if (!date || !time || close === null) return null;
        const open = stagingChartNumeric(row?.openPrice) ?? close;
        return {
          date,
          time,
          open,
          high: Math.max(stagingChartNumeric(row?.highPrice) ?? close, open, close),
          low: Math.min(stagingChartNumeric(row?.lowPrice) ?? close, open, close),
          close,
          price: close,
          volume: stagingChartNumeric(row?.accumulatedTradingVolume) || 0,
        };
      })
    )).filter(Boolean)
      .sort((left, right) => `${left.date}${left.time}`.localeCompare(`${right.date}${right.time}`));
    return {
      rows,
      referencePrice: stagingChartNumeric(payload?.lastClosePrice),
      tradeBaseAt: stagingChartDateKey(payload?.tradeBaseAt),
      marketStatus: String(payload?.marketStatus || ""),
    };
  };

  const ensureStagingWeekChartData = (code, force = false) => {
    const normalizedCode = String(code || "").trim();
    if (!/^[0-9]{6}$/.test(normalizedCode)) return Promise.resolve(null);
    const now = Date.now();
    const current = stagingWeekChartCache.get(normalizedCode);
    if (!force && current?.status === "loading" && current.promise) return current.promise;
    if (!force && current?.status === "error") return Promise.resolve(current);
    if (
      !force
      && current?.status === "ready"
      && current.rows?.length > 1
      && now - current.fetchedAt < STAGING_WEEK_CHART_TTL_MS
    ) {
      return Promise.resolve(current);
    }

    const loading = {
      status: "loading",
      rows: current?.rows || [],
      referencePrice: current?.referencePrice ?? null,
      fetchedAt: current?.fetchedAt || 0,
      error: "",
      promise: null,
    };
    const request = (async () => {
      try {
        const payload = await stagingJsonRequest(`/stocks/${encodeURIComponent(normalizedCode)}/week-chart`, {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        const normalized = stagingNormalizeWeekChart(payload);
        if (normalized.rows.length < 2) throw new Error("week chart has insufficient rows");
        const ready = {
          ...normalized,
          status: "ready",
          fetchedAt: Date.now(),
          error: "",
          promise: null,
        };
        stagingWeekChartCache.set(normalizedCode, ready);
        return ready;
      } catch (error) {
        const hasStaleRows = loading.rows.length > 1;
        const failed = {
          ...loading,
          status: hasStaleRows ? "ready" : "error",
          error: "일주일 차트를 불러오지 못했습니다.",
          promise: null,
        };
        stagingWeekChartCache.set(normalizedCode, failed);
        return failed;
      } finally {
        const chart = document.getElementById("stock-mini-chart");
        chart?.removeAttribute("data-staging-chart-signature");
        window.requestAnimationFrame(() => upgradeStagingStockPriceChart());
      }
    })();
    loading.promise = request;
    stagingWeekChartCache.set(normalizedCode, loading);
    return request;
  };

  const stagingKoreaClock = (date = new Date()) => {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(date).reduce((result, part) => {
      result[part.type] = part.value;
      return result;
    }, {});
    const hour = Number(parts.hour || 0);
    const minute = Number(parts.minute || 0);
    const result = {
      date: `${parts.year}-${parts.month}-${parts.day}`,
      time: `${String(hour).padStart(2, "0")}${String(minute).padStart(2, "0")}00`,
      weekday: parts.weekday || "",
      minutes: hour * 60 + minute,
    };
    const params = new URLSearchParams(window.location.search);
    const requestedDate = stagingChartDateKey(params.get("stagingChartDate"));
    const requestedTime = String(params.get("stagingChartTime") || "").replace(/[^0-9]/g, "");
    if (requestedTime.length >= 4) {
      const debugHour = Number(requestedTime.slice(0, 2));
      const debugMinute = Number(requestedTime.slice(2, 4));
      if (debugHour >= 0 && debugHour < 24 && debugMinute >= 0 && debugMinute < 60) {
        result.date = requestedDate || result.date;
        result.time = `${String(debugHour).padStart(2, "0")}${String(debugMinute).padStart(2, "0")}00`;
        result.minutes = debugHour * 60 + debugMinute;
      }
    }
    return result;
  };

  const stagingStockChartPhase = (quote = null) => {
    const requested = new URLSearchParams(window.location.search).get("stagingChartPhase");
    if (["preopen", "regular", "closed"].includes(requested)) return requested;
    const clock = stagingKoreaClock();
    if (["Sat", "Sun"].includes(clock.weekday)) return "closed";
    if (clock.minutes >= 7 * 60 && clock.minutes < 9 * 60) return "preopen";
    if (clock.minutes >= 9 * 60 && clock.minutes < 15 * 60 + 30) {
      const quoteDate = stagingChartDateKey(quote?.trade_date);
      return !quoteDate || quoteDate === clock.date ? "regular" : "closed";
    }
    return "closed";
  };

  const stagingStockChartLiveSession = (quote = null, phase = "closed") => {
    if (phase === "regular") return quote?.is_live !== false;
    return quote?.is_live === true
      && STAGING_LIVE_INTRADAY_SESSIONS.has(String(quote?.market_session || ""));
  };

  const stagingStockDailyRows = (quote = null) => {
    const sourceRows = typeof state !== "undefined" && Array.isArray(state.stockPriceRows)
      ? state.stockPriceRows
      : [];
    const rows = sourceRows.map((row) => {
      const close = stagingChartNumeric(row?.close);
      if (close === null) return null;
      const open = stagingChartNumeric(row?.open) ?? close;
      const high = Math.max(stagingChartNumeric(row?.high) ?? close, open, close);
      const low = Math.min(stagingChartNumeric(row?.low) ?? close, open, close);
      return {
        date: stagingChartDateKey(row?.trade_date || row?.date),
        open,
        high,
        low,
        close,
        price: close,
        volume: stagingChartNumeric(row?.volume) || 0,
      };
    }).filter((row) => row?.date && row.price !== null)
      .sort((left, right) => left.date.localeCompare(right.date));
    const quotePrice = stagingChartNumeric(quote?.price);
    const quoteDate = stagingChartDateKey(quote?.trade_date);
    if (quotePrice !== null && quoteDate) {
      const matching = rows.find((row) => row.date === quoteDate);
      if (matching) {
        matching.open ??= quotePrice;
        matching.high = Math.max(matching.high ?? quotePrice, quotePrice);
        matching.low = Math.min(matching.low ?? quotePrice, quotePrice);
        matching.close = quotePrice;
        matching.price = quotePrice;
        matching.volume = stagingChartNumeric(quote?.volume) || matching.volume;
      } else {
        rows.push({
          date: quoteDate,
          open: quotePrice,
          high: quotePrice,
          low: quotePrice,
          close: quotePrice,
          price: quotePrice,
          volume: stagingChartNumeric(quote?.volume) || 0,
        });
      }
    }
    return rows;
  };

  const stagingStockIntradayRows = (quote = null, phase = "closed", clockOverride = null) => {
    const sourceRows = typeof state !== "undefined" && Array.isArray(state.stockIntradayRows)
      ? state.stockIntradayRows
      : [];
    let rows = sourceRows.map((row) => {
      const close = stagingChartNumeric(row?.price ?? row?.close);
      if (close === null) return null;
      const open = stagingChartNumeric(row?.open) ?? close;
      const high = Math.max(stagingChartNumeric(row?.high) ?? close, open, close);
      const low = Math.min(stagingChartNumeric(row?.low) ?? close, open, close);
      return {
        date: stagingChartDateKey(row?.trade_date),
        time: String(row?.trade_time || "").replace(/[^0-9]/g, "").padStart(6, "0"),
        open,
        high,
        low,
        close,
        price: close,
        volume: stagingChartNumeric(row?.volume) || 0,
      };
    }).filter((row) => row?.date && row.time && row.price !== null)
      .sort((left, right) => `${left.date}${left.time}`.localeCompare(`${right.date}${right.time}`));
    const clock = clockOverride || stagingKoreaClock();
    const quoteDate = stagingChartDateKey(quote?.trade_date);
    const quotePrice = stagingChartNumeric(quote?.price);
    const latestDate = rows.some((row) => row.date === quoteDate) ? quoteDate : rows.at(-1)?.date;
    if (latestDate) rows = rows.filter((row) => row.date === latestDate);
    const liveSession = stagingStockChartLiveSession(quote, phase);
    if (liveSession && quotePrice !== null && quoteDate === clock.date) {
      rows = rows.filter((row) => row.time <= clock.time);
      const isDebugClock = new URLSearchParams(window.location.search).has("stagingChartTime");
      const stockCode = String(state.currentStock?.code || state.currentDashboard?.code || "").trim();
      const liveCacheKey = `${stockCode || "unknown"}|${quoteDate}`;
      const cachedRows = stagingLiveIntradayRows.get(liveCacheKey) || new Map();
      const sourceLatestTime = rows.at(-1)?.time || "";
      const rowsByTime = new Map(rows.map((row) => [row.time, row]));
      for (const [time, cachedRow] of cachedRows) {
        if (time < sourceLatestTime || time > clock.time) {
          cachedRows.delete(time);
          continue;
        }
        const existing = rowsByTime.get(time);
        if (existing) {
          existing.open = existing.open ?? cachedRow.open;
          existing.high = Math.max(existing.high ?? cachedRow.high, cachedRow.high);
          existing.low = Math.min(existing.low ?? cachedRow.low, cachedRow.low);
          existing.close = cachedRow.close;
          existing.price = cachedRow.price;
          existing.volume = Math.max(existing.volume || 0, cachedRow.volume || 0);
        } else {
          const restored = { ...cachedRow };
          rows.push(restored);
          rowsByTime.set(time, restored);
        }
      }
      rows.sort((left, right) => `${left.date}${left.time}`.localeCompare(`${right.date}${right.time}`));
      const latest = rows.at(-1);
      const startsNewMinute = !latest || latest.time < clock.time;
      const liveRow = {
        date: quoteDate,
        time: clock.time,
        open: startsNewMinute ? latest?.close ?? quotePrice : latest?.open ?? quotePrice,
        high: startsNewMinute ? quotePrice : Math.max(latest?.high ?? quotePrice, quotePrice),
        low: startsNewMinute ? quotePrice : Math.min(latest?.low ?? quotePrice, quotePrice),
        close: quotePrice,
        price: quotePrice,
        volume: stagingChartNumeric(quote?.volume) || latest?.volume || 0,
      };
      const last = latest;
      if (!isDebugClock) {
        if (!last || `${last.date}${last.time}` < `${liveRow.date}${liveRow.time}`) rows.push(liveRow);
        else if (last.date === liveRow.date) Object.assign(last, liveRow);
        cachedRows.set(liveRow.time, { ...liveRow });
        while (cachedRows.size > 390) cachedRows.delete(cachedRows.keys().next().value);
        stagingLiveIntradayRows.set(liveCacheKey, cachedRows);
        while (stagingLiveIntradayRows.size > STAGING_LIVE_INTRADAY_CACHE_KEYS) {
          stagingLiveIntradayRows.delete(stagingLiveIntradayRows.keys().next().value);
        }
      }
    }
    return rows;
  };

  const stagingStockWeeklyRows = (quote = null, phase = "closed", entry = null) => {
    const rows = Array.isArray(entry?.rows) ? entry.rows.map((row) => ({ ...row })) : [];
    if (!rows.length) return rows;
    const quoteDate = stagingChartDateKey(quote?.trade_date);
    const quotePrice = stagingChartNumeric(quote?.price);
    const clock = stagingKoreaClock();
    const last = rows.at(-1);
    if (quoteDate && quotePrice !== null && quoteDate >= (last?.date || "")) {
      if (phase === "regular" && quoteDate === clock.date) {
        const time = clock.time;
        const matching = rows.find((row) => row.date === quoteDate && row.time === time);
        const previous = rows.filter((row) => row.date === quoteDate).at(-1) || last;
        const liveRow = {
          date: quoteDate,
          time,
          open: previous?.close ?? quotePrice,
          high: Math.max(previous?.close ?? quotePrice, quotePrice),
          low: Math.min(previous?.close ?? quotePrice, quotePrice),
          close: quotePrice,
          price: quotePrice,
          volume: stagingChartNumeric(quote?.volume) || previous?.volume || 0,
        };
        if (matching) Object.assign(matching, liveRow);
        else rows.push(liveRow);
      } else if (last?.date === quoteDate) {
        last.high = Math.max(last.high ?? quotePrice, quotePrice);
        last.low = Math.min(last.low ?? quotePrice, quotePrice);
        last.close = quotePrice;
        last.price = quotePrice;
        last.volume = stagingChartNumeric(quote?.volume) || last.volume;
      }
    }
    rows.sort((left, right) => `${left.date}${left.time}`.localeCompare(`${right.date}${right.time}`));
    const visibleDates = [...new Set(rows.map((row) => row.date))].sort().slice(-5);
    const visibleDateSet = new Set(visibleDates);
    return rows.filter((row) => visibleDateSet.has(row.date));
  };

  const renderStagingWeekChartStatus = (chart, status = "loading", code = "") => {
    const failed = status === "error";
    chart.innerHTML = `
      <div class="staging-toss-week-chart-status ${failed ? "is-error" : "is-loading"}" role="status" aria-live="polite">
        <span class="staging-toss-week-chart-status-mark" aria-hidden="true"></span>
        <p>${failed ? "일주일 차트를 불러오지 못했어요." : "최근 5거래일 시세를 불러오고 있어요."}</p>
        ${failed ? '<button type="button" data-staging-week-chart-retry>다시 불러오기</button>' : ""}
      </div>
    `;
    chart.dataset.stagingChartSignature = `1W|${status}|${code}`;
    chart.querySelector("[data-staging-week-chart-retry]")?.addEventListener("click", () => {
      ensureStagingWeekChartData(code, true);
      renderStagingWeekChartStatus(chart, "loading", code);
    });
  };

  const stagingStockPreviousClose = (quote = null, dailyRows = []) => {
    const price = stagingChartNumeric(quote?.price);
    const change = stagingChartNumeric(quote?.change_value);
    if (price !== null && change !== null) return price - change;
    return dailyRows.length > 1 ? dailyRows.at(-2)?.price ?? null : null;
  };

  const stagingIntradayMinute = (value) => {
    const digits = String(value || "").replace(/[^0-9]/g, "").padStart(4, "0");
    return Number(digits.slice(0, 2)) * 60 + Number(digits.slice(2, 4));
  };

  const stagingChartTone = (end, reference) => {
    if (end > reference) return "positive";
    if (end < reference) return "negative";
    return "neutral";
  };

  const stagingCandleTimestampLabel = (row) => {
    const startDate = stagingChartDateLabel(row?.date);
    const endDate = stagingChartDateLabel(row?.endDate || row?.date);
    const startTime = row?.time ? stagingChartTimeLabel(row.time) : "";
    const endTime = row?.endTime ? stagingChartTimeLabel(row.endTime) : startTime;
    if (startTime) {
      if (startDate === endDate && startTime !== endTime) return `${startDate} · ${startTime}~${endTime}`;
      if (startDate !== endDate) return `${startDate} ${startTime}~${endDate} ${endTime}`;
      return `${startDate} · ${startTime}`;
    }
    return startDate === endDate ? startDate : `${startDate}~${endDate}`;
  };

  const stagingAggregateCandleRows = (sourceRows, maximumCount = 78) => {
    const rows = sourceRows.map((row) => {
      const close = stagingChartNumeric(row?.close ?? row?.price);
      if (close === null) return null;
      const open = stagingChartNumeric(row?.open) ?? close;
      return {
        ...row,
        open,
        high: Math.max(stagingChartNumeric(row?.high) ?? close, open, close),
        low: Math.min(stagingChartNumeric(row?.low) ?? close, open, close),
        close,
        price: close,
      };
    }).filter(Boolean);
    if (rows.length <= maximumCount) return rows;

    const bucketSize = Math.ceil(rows.length / maximumCount);
    const aggregated = [];
    for (let index = 0; index < rows.length; index += bucketSize) {
      const bucket = rows.slice(index, index + bucketSize);
      const first = bucket[0];
      const last = bucket.at(-1);
      aggregated.push({
        ...first,
        endDate: last.date,
        endTime: last.time || "",
        open: first.open,
        high: Math.max(...bucket.map((row) => row.high)),
        low: Math.min(...bucket.map((row) => row.low)),
        close: last.close,
        price: last.close,
        volume: bucket.reduce((total, row) => total + (stagingChartNumeric(row.volume) || 0), 0),
        sourceCount: bucket.length,
      });
    }
    return aggregated;
  };

  const stagingChartExtremaMarkup = (label, row, point, type, width, value = row.price) => {
    const labelX = stagingChartClamp(point.x, 54, width - 54);
    const labelY = stagingChartClamp(point.y + (type === "high" ? -18 : 27), 18, 284);
    return `
      <g class="staging-toss-chart-extrema ${type}">
        <circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="2.5"></circle>
        <text x="${labelX.toFixed(2)}" y="${labelY.toFixed(2)}" text-anchor="middle">${label} ${stagingChartNumber.format(Math.round(value))}원</text>
      </g>
    `;
  };

  const bindStagingStockChartScrubber = (chart, rows, points, width, height, chartType = "line") => {
    const stage = chart.querySelector(".staging-toss-chart-stage");
    const scrubber = chart.querySelector(".staging-toss-chart-scrubber");
    const crosshair = chart.querySelector("[data-staging-chart-crosshair]");
    const focusPoint = chart.querySelector("[data-staging-chart-focus-point]");
    const tooltip = chart.querySelector(".staging-toss-chart-tooltip");
    const tooltipTime = tooltip?.querySelector("[data-staging-chart-tooltip-time]");
    const tooltipPrice = tooltip?.querySelector("[data-staging-chart-tooltip-price]");
    if (!stage || !scrubber || !crosshair || !focusPoint || !tooltip || !tooltipTime || !tooltipPrice) return;

    let dragging = false;
    let hideTimer = 0;
    const hide = () => {
      window.clearTimeout(hideTimer);
      chart.classList.remove("is-scrubbing");
      crosshair.hidden = true;
      focusPoint.hidden = true;
      tooltip.hidden = true;
    };
    const reveal = (index) => {
      const safeIndex = stagingChartClamp(Number(index) || 0, 0, rows.length - 1);
      const row = rows[safeIndex];
      const point = points[safeIndex];
      const isCandle = chartType === "candle";
      const timestamp = isCandle
        ? stagingCandleTimestampLabel(row)
        : row.time
          ? `${stagingChartDateLabel(row.date)} · ${stagingChartTimeLabel(row.time)}`
          : stagingChartDateLabel(row.date);
      const price = stagingChartNumeric(row.close ?? row.price) ?? 0;
      const priceText = `${stagingChartNumber.format(Math.round(price))}원`;
      const ohlcText = isCandle
        ? [
          `시가 ${stagingChartNumber.format(Math.round(row.open))}원`,
          `고가 ${stagingChartNumber.format(Math.round(row.high))}원`,
          `저가 ${stagingChartNumber.format(Math.round(row.low))}원`,
          `종가 ${priceText}`,
        ]
        : [];
      scrubber.value = String(safeIndex);
      scrubber.setAttribute("aria-valuetext", `${timestamp}, ${ohlcText.length ? ohlcText.join(", ") : priceText}`);
      crosshair.setAttribute("x1", point.x.toFixed(2));
      crosshair.setAttribute("x2", point.x.toFixed(2));
      focusPoint.setAttribute("cx", point.x.toFixed(2));
      focusPoint.setAttribute("cy", point.y.toFixed(2));
      const stageBounds = stage.getBoundingClientRect();
      const stickyTabs = document.querySelector('#stock-view [role="tablist"][aria-label="종목 상세 탭"]');
      const protectedViewportTop = Math.max(0, stickyTabs?.getBoundingClientRect().bottom || 0) + 8;
      const pointViewportY = stageBounds.top + (point.y / height) * stageBounds.height;
      const estimatedTooltipHeight = isCandle ? 146 : 66;
      const showBelow = pointViewportY - estimatedTooltipHeight < protectedViewportTop;
      const estimatedTooltipViewHeight = estimatedTooltipHeight / Math.max(1, stageBounds.height) * height;
      const protectedViewTop = Math.max(0, protectedViewportTop - stageBounds.top) / Math.max(1, stageBounds.height) * height;
      const tooltipViewTop = showBelow
        ? stagingChartClamp(point.y + 17, protectedViewTop, height - estimatedTooltipViewHeight - 8)
        : stagingChartClamp(point.y - 14, estimatedTooltipViewHeight + 8, height - 8);
      tooltip.classList.toggle("is-below", showBelow);
      tooltip.style.left = `${stagingChartClamp(point.x / width * 100, isCandle ? 27 : 17, isCandle ? 73 : 83)}%`;
      tooltip.style.top = `${stagingChartClamp(tooltipViewTop / height * 100, 2, 96)}%`;
      tooltipTime.textContent = timestamp;
      tooltipPrice.textContent = isCandle ? `종가 ${priceText}` : priceText;
      for (const key of ["open", "high", "low", "close"]) {
        const value = key === "close" ? price : row[key];
        const target = tooltip.querySelector(`[data-staging-candle-value="${key}"]`);
        if (target) target.textContent = `${stagingChartNumber.format(Math.round(value))}원`;
      }
      chart.classList.add("is-scrubbing");
      crosshair.hidden = false;
      focusPoint.hidden = false;
      tooltip.hidden = false;
    };
    const nearestIndex = (clientX) => {
      const bounds = stage.getBoundingClientRect();
      const viewX = stagingChartClamp((clientX - bounds.left) / Math.max(1, bounds.width) * width, 0, width);
      let result = 0;
      let distance = Number.POSITIVE_INFINITY;
      for (let index = 0; index < points.length; index += 1) {
        const nextDistance = Math.abs(points[index].x - viewX);
        if (nextDistance < distance) {
          result = index;
          distance = nextDistance;
        }
      }
      return result;
    };
    const revealFromPointer = (event) => reveal(nearestIndex(event.clientX));

    scrubber.addEventListener("pointerdown", (event) => {
      dragging = true;
      window.clearTimeout(hideTimer);
      scrubber.setPointerCapture?.(event.pointerId);
      revealFromPointer(event);
    });
    scrubber.addEventListener("pointermove", (event) => {
      if (dragging || event.pointerType === "mouse") revealFromPointer(event);
    });
    scrubber.addEventListener("pointerup", (event) => {
      dragging = false;
      scrubber.releasePointerCapture?.(event.pointerId);
      if (event.pointerType !== "mouse") hideTimer = window.setTimeout(hide, 900);
    });
    scrubber.addEventListener("pointercancel", () => {
      dragging = false;
      hide();
    });
    scrubber.addEventListener("pointerleave", (event) => {
      if (!dragging && event.pointerType === "mouse") hide();
    });
    scrubber.addEventListener("input", () => reveal(Number(scrubber.value)));
    scrubber.addEventListener("keydown", () => window.requestAnimationFrame(() => reveal(Number(scrubber.value))));
    scrubber.addEventListener("focus", () => reveal(Number(scrubber.value)));
    scrubber.addEventListener("blur", hide);
  };

  const ensureStagingStockChartPeriods = (periods) => {
    if (periods.dataset.stagingTossPeriods === "true") return;
    const sessionIcon = document.createElement("span");
    sessionIcon.className = "staging-toss-chart-session-icon";
    sessionIcon.setAttribute("aria-hidden", "true");
    sessionIcon.innerHTML = `
      <svg viewBox="0 0 28 28" focusable="false">
        <path d="M7 18.5a7 7 0 0 1 14 0"></path>
        <path d="M4 21h20M14 4v3M5.5 9.5l2.2 2.2M22.5 9.5l-2.2 2.2"></path>
      </svg>
    `;
    const chartTypeIcon = document.createElement("button");
    chartTypeIcon.type = "button";
    chartTypeIcon.className = "staging-toss-chart-type-icon staging-toss-chart-type-toggle";
    chartTypeIcon.dataset.stagingChartTypeToggle = "true";
    chartTypeIcon.setAttribute("aria-pressed", "false");
    chartTypeIcon.setAttribute("aria-label", "캔들 차트로 보기");
    chartTypeIcon.title = "캔들 차트로 보기";
    chartTypeIcon.innerHTML = `
      <svg viewBox="0 0 28 28" focusable="false" aria-hidden="true">
        <path class="up" d="M8 4v20M4.5 9h7v9h-7z"></path>
        <path class="down" d="M20 5v19M16.5 11h7v8h-7z"></path>
      </svg>
    `;
    const fragment = document.createDocumentFragment();
    fragment.appendChild(sessionIcon);
    for (const item of STAGING_STOCK_CHART_PERIODS) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.stagingChartPeriod = item.key;
      button.textContent = item.label;
      fragment.appendChild(button);
    }
    fragment.appendChild(chartTypeIcon);
    periods.replaceChildren(fragment);
    periods.dataset.stagingTossPeriods = "true";
    periods.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target : null;
      const chartTypeToggle = target?.closest("[data-staging-chart-type-toggle]");
      if (chartTypeToggle instanceof HTMLButtonElement) {
        stagingSelectedChartType = stagingSelectedChartType === "candle" ? "line" : "candle";
        const chart = document.getElementById("stock-mini-chart");
        chart?.removeAttribute("data-staging-chart-signature");
        upgradeStagingStockPriceChart();
        return;
      }
      const button = target?.closest("[data-staging-chart-period]");
      if (!(button instanceof HTMLButtonElement)) return;
      stagingSelectedChartPeriod = button.dataset.stagingChartPeriod || "1D";
      const chart = document.getElementById("stock-mini-chart");
      chart?.removeAttribute("data-staging-chart-signature");
      upgradeStagingStockPriceChart();
    });
  };

  const upgradeStagingStockPriceChart = () => {
    if (!window.location.pathname.startsWith("/dashboard/") || typeof state === "undefined") return;
    const chart = document.getElementById("stock-mini-chart");
    const periods = document.getElementById("stock-v2-price-periods");
    if (!chart || !periods || !state.currentDashboard) return;

    ensureStagingStockChartPeriods(periods);
    const quote = state.currentDashboard?.quote || null;
    const phase = stagingStockChartPhase(quote);
    const liveSession = stagingStockChartLiveSession(quote, phase);
    const dailyRows = stagingStockDailyRows(quote);
    const periodConfig = STAGING_STOCK_CHART_PERIODS.find((item) => item.key === stagingSelectedChartPeriod)
      || STAGING_STOCK_CHART_PERIODS[0];
    const isIntraday = periodConfig.key === "1D";
    const isDenseWeek = periodConfig.key === "1W";
    const stockCode = String(state.currentStock?.code || state.currentDashboard?.code || "").trim();
    const isCandle = stagingSelectedChartType === "candle";
    for (const button of periods.querySelectorAll("[data-staging-chart-period]")) {
      const active = button.dataset.stagingChartPeriod === periodConfig.key;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    const chartTypeToggle = periods.querySelector("[data-staging-chart-type-toggle]");
    if (chartTypeToggle instanceof HTMLButtonElement) {
      const label = isCandle ? "라인 차트로 보기" : "캔들 차트로 보기";
      chartTypeToggle.setAttribute("aria-pressed", String(isCandle));
      chartTypeToggle.setAttribute("aria-label", label);
      chartTypeToggle.title = label;
    }
    periods.classList.toggle("is-live", liveSession);
    periods.classList.toggle("is-candle", isCandle);
    periods.dataset.stagingChartPhase = phase;
    periods.dataset.stagingChartType = stagingSelectedChartType;

    let weekEntry = null;
    if (isDenseWeek) {
      ensureStagingWeekChartData(stockCode);
      weekEntry = stagingWeekChartCache.get(stockCode) || null;
      if (!Array.isArray(weekEntry?.rows) || weekEntry.rows.length < 2) {
        renderStagingWeekChartStatus(chart, weekEntry?.status === "error" ? "error" : "loading", stockCode);
        return;
      }
    }
    const allRows = isIntraday
      ? stagingStockIntradayRows(quote, phase)
      : isDenseWeek
        ? stagingStockWeeklyRows(quote, phase, weekEntry)
        : dailyRows;
    const periodRows = isIntraday || isDenseWeek || !Number.isFinite(periodConfig.count)
      ? allRows
      : allRows.slice(-periodConfig.count);
    const rows = isCandle ? stagingAggregateCandleRows(periodRows) : periodRows;
    if (rows.length < 2) return;

    const previousClose = stagingStockPreviousClose(quote, dailyRows);
    const referencePrice = isIntraday && previousClose !== null
      ? previousClose
      : isDenseWeek && stagingChartNumeric(weekEntry?.referencePrice) !== null
        ? stagingChartNumeric(weekEntry.referencePrice)
        : rows[0].price;
    const lastRow = rows.at(-1);
    const signature = [
      state.currentStock?.code || "",
      periodConfig.key,
      stagingSelectedChartType,
      phase,
      rows.length,
      `${rows[0].date}${rows[0].time || ""}${rows[0].open ?? ""}${rows[0].high ?? ""}${rows[0].low ?? ""}${rows[0].price}`,
      `${lastRow.date}${lastRow.time || ""}${lastRow.open ?? ""}${lastRow.high ?? ""}${lastRow.low ?? ""}${lastRow.price}`,
      stagingChartNumeric(quote?.price) || "",
    ].join("|");
    if (chart.dataset.stagingChartSignature === signature && chart.querySelector(".staging-toss-stock-chart")) return;

    const width = 360;
    const height = 300;
    const left = 4;
    const right = 4;
    const top = 34;
    const bottom = 262;
    const plotWidth = width - left - right;
    const plotHeight = bottom - top;
    const priceValues = isCandle
      ? rows.flatMap((row) => [row.low, row.high])
      : rows.map((row) => row.price);
    if (referencePrice !== null) priceValues.push(referencePrice);
    const rawMin = Math.min(...priceValues);
    const rawMax = Math.max(...priceValues);
    const rawSpan = rawMax === rawMin ? Math.max(rawMax * 0.015, 1) : rawMax - rawMin;
    const minimum = Math.max(0, rawMin - rawSpan * 0.1);
    const maximum = rawMax + rawSpan * 0.1;
    const span = maximum - minimum || 1;
    const pointY = (value) => top + ((maximum - value) / span) * plotHeight;
    const intradayMinutes = isIntraday
      ? rows.map((row) => stagingIntradayMinute(row.endTime || row.time))
      : [];
    const observedIntradayStartMinute = intradayMinutes.length
      ? Math.min(...intradayMinutes)
      : 0;
    const observedIntradayEndMinute = intradayMinutes.length
      ? Math.max(...intradayMinutes)
      : observedIntradayStartMinute;
    const observedIntradaySpan = observedIntradayEndMinute - observedIntradayStartMinute;
    const points = rows.map((row, index) => {
      const timeRatio = isIntraday
        ? observedIntradaySpan > 0
          ? stagingChartClamp(
            (stagingIntradayMinute(row.endTime || row.time) - observedIntradayStartMinute) / observedIntradaySpan,
            0,
            1,
          )
          : index / Math.max(1, rows.length - 1)
        : index / Math.max(1, rows.length - 1);
      return {
        x: left + timeRatio * plotWidth,
        y: pointY(row.close ?? row.price),
      };
    });
    const linePath = points.map((point, index) => (
      `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`
    )).join(" ");
    const pointSpacing = points.length > 1
      ? Math.min(...points.slice(1).map((point, index) => point.x - points[index].x).filter((value) => value > 0))
      : plotWidth;
    const candleWidth = stagingChartClamp((Number.isFinite(pointSpacing) ? pointSpacing : plotWidth / rows.length) * 0.62, 2, 9);
    const candleMarkup = isCandle ? rows.map((row, index) => {
      const point = points[index];
      const openY = pointY(row.open);
      const closeY = pointY(row.close);
      const highY = pointY(row.high);
      const lowY = pointY(row.low);
      const bodyHeight = Math.max(1.6, Math.abs(closeY - openY));
      const bodyY = (openY + closeY) / 2 - bodyHeight / 2;
      const direction = row.close > row.open ? "rise" : row.close < row.open ? "fall" : "flat";
      const title = `${stagingCandleTimestampLabel(row)} · 시가 ${stagingChartNumber.format(Math.round(row.open))}원 · 고가 ${stagingChartNumber.format(Math.round(row.high))}원 · 저가 ${stagingChartNumber.format(Math.round(row.low))}원 · 종가 ${stagingChartNumber.format(Math.round(row.close))}원`;
      return `
        <g class="staging-toss-chart-candle is-${direction}" data-staging-candle-index="${index}">
          <title>${title}</title>
          <line class="wick" x1="${point.x.toFixed(2)}" y1="${highY.toFixed(2)}" x2="${point.x.toFixed(2)}" y2="${lowY.toFixed(2)}"></line>
          <rect class="body" x="${(point.x - candleWidth / 2).toFixed(2)}" y="${bodyY.toFixed(2)}" width="${candleWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" rx="0.65"></rect>
        </g>
      `;
    }).join("") : "";
    const tone = stagingChartTone(lastRow.price, referencePrice);
    const highPrice = Math.max(...rows.map((row) => isCandle ? row.high : row.price));
    const lowPrice = Math.min(...rows.map((row) => isCandle ? row.low : row.price));
    const highIndex = rows.findIndex((row) => (isCandle ? row.high : row.price) === highPrice);
    const lowIndex = rows.findIndex((row) => (isCandle ? row.low : row.price) === lowPrice);
    const baselineY = referencePrice === null
      ? null
      : top + ((maximum - referencePrice) / span) * plotHeight;
    const baseline = baselineY === null ? "" : `
      <line class="staging-toss-chart-baseline" x1="${left}" y1="${baselineY.toFixed(2)}" x2="${width - right}" y2="${baselineY.toFixed(2)}"></line>
    `;
    const highPoint = isCandle ? { x: points[highIndex].x, y: pointY(highPrice) } : points[highIndex];
    const lowPoint = isCandle ? { x: points[lowIndex].x, y: pointY(lowPrice) } : points[lowIndex];
    const extrema = highIndex === lowIndex && highPrice === lowPrice ? "" : [
      stagingChartExtremaMarkup("최고", rows[highIndex], highPoint, "high", width, highPrice),
      stagingChartExtremaMarkup("최저", rows[lowIndex], lowPoint, "low", width, lowPrice),
    ].join("");
    const livePoint = liveSession ? `
      <g class="staging-toss-chart-live-point" transform="translate(${points.at(-1).x.toFixed(2)} ${points.at(-1).y.toFixed(2)})">
        <circle class="pulse-far" r="15"></circle>
        <circle class="pulse-near" r="9"></circle>
        <circle class="core" r="4.5"></circle>
        <path class="spark spark-a" d="M0-16v-4M-16 0h-4"></path>
        <path class="spark spark-b" d="M12-12l3-3M12 12l3 3"></path>
      </g>
    ` : "";
    const marketSession = String(quote?.market_session || "");
    const phaseLabel = marketSession === "nxt_pre_market" && liveSession
      ? "프리장 실시간"
      : marketSession === "nxt_after_market" && liveSession
        ? "애프터장 실시간"
        : phase === "regular" && liveSession
          ? "장중 실시간"
          : phase === "preopen" ? "장전" : "장마감";
    const rangeLabel = isIntraday
      ? `${stagingChartDateLabel(rows[0].date)} ${stagingChartTimeLabel(rows[0].time)}부터 ${stagingChartTimeLabel(lastRow.endTime || lastRow.time)}`
      : isDenseWeek
        ? `${stagingChartDateLabel(rows[0].date)} ${stagingChartTimeLabel(rows[0].time)}부터 ${stagingChartDateLabel(lastRow.date)} ${stagingChartTimeLabel(lastRow.endTime || lastRow.time)}`
      : `${stagingChartDateLabel(rows[0].date)}부터 ${stagingChartDateLabel(lastRow.endDate || lastRow.date)}`;
    const chartLabel = isCandle ? "캔들 차트" : "가격 차트";
    const chartFlowLabel = isCandle ? "시가·고가·저가·종가 흐름" : "가격 흐름";
    const candleTooltip = isCandle ? `
      <dl class="staging-toss-chart-tooltip-ohlc" data-staging-chart-tooltip-ohlc>
        <div><dt>시가</dt><dd data-staging-candle-value="open">-</dd></div>
        <div><dt>고가</dt><dd data-staging-candle-value="high">-</dd></div>
        <div><dt>저가</dt><dd data-staging-candle-value="low">-</dd></div>
        <div><dt>종가</dt><dd data-staging-candle-value="close">-</dd></div>
      </dl>
    ` : "";

    chart.innerHTML = `
      <div class="staging-toss-stock-chart ${tone}${liveSession ? " is-live" : ""}${isDenseWeek ? " is-week" : ""}${isCandle ? " is-candle" : ""}" data-chart-phase="${phase}" data-chart-live="${liveSession}" data-chart-period="${periodConfig.key}" data-chart-type="${stagingSelectedChartType}"${isDenseWeek ? ' data-chart-source="naver-week-ten-minute"' : ""} aria-label="${periodConfig.label} ${phaseLabel} ${chartLabel}">
        <div class="staging-toss-chart-stage">
          <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="${rangeLabel} ${chartFlowLabel}">
            ${baseline}
            ${isCandle ? candleMarkup : `<path class="staging-toss-chart-line" d="${linePath}"></path>`}
            ${extrema}
            ${livePoint}
            <line class="staging-toss-chart-crosshair" data-staging-chart-crosshair x1="0" y1="${top}" x2="0" y2="${bottom}" hidden></line>
            <circle class="staging-toss-chart-focus-point" data-staging-chart-focus-point cx="0" cy="0" r="5" hidden></circle>
          </svg>
          <div class="staging-toss-chart-tooltip${isCandle ? " is-candle" : ""}" role="status" aria-live="polite" hidden>
            <span data-staging-chart-tooltip-time></span>
            <strong data-staging-chart-tooltip-price></strong>
            ${candleTooltip}
          </div>
          <input class="staging-toss-chart-scrubber" type="range" min="0" max="${rows.length - 1}" value="${rows.length - 1}" step="1" aria-label="${periodConfig.label} ${isCandle ? "캔들" : "가격"} 시점 탐색" />
        </div>
        <p class="staging-toss-chart-accessible-help">차트를 누른 채 좌우로 움직이면 해당 시점의 ${isCandle ? "시가, 고가, 저가, 종가를" : "날짜와 금액을"} 확인할 수 있습니다.</p>
      </div>
    `;
    chart.dataset.stagingChartSignature = signature;
    bindStagingStockChartScrubber(chart.querySelector(".staging-toss-stock-chart"), rows, points, width, height, stagingSelectedChartType);
  };

  const routeButton = (view) => document.querySelector(`[data-staging-route-proxy="${view}"]`)
    || bottomNav.querySelector(`[data-app-view="${view}"]`);

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const control = target.closest("[data-staging-view]");
    if (!control) return;
    event.preventDefault();
    const view = control.dataset.stagingView;
    const anchorId = control.dataset.stagingAnchor;
    routeButton(view)?.click();
    if (anchorId) {
      window.requestAnimationFrame(() => document.getElementById(anchorId)?.scrollIntoView({ block: "start", behavior: "smooth" }));
    } else {
      window.scrollTo({ top: 0, behavior: "auto" });
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const historyToggle = target.closest("[data-staging-recommend-history-toggle]");
    if (historyToggle) {
      event.preventDefault();
      const expanded = historyToggle.getAttribute("aria-expanded") === "true";
      const journey = historyToggle.closest(".staging-recommend-detail-journey");
      const entries = Array.from(journey?.querySelectorAll(".recommend-signal-timeline-item") || []);
      entries.slice(4).forEach((entry) => { entry.hidden = expanded; });
      historyToggle.setAttribute("aria-expanded", String(!expanded));
      const hiddenCount = Number(historyToggle.dataset.hiddenCount || Math.max(0, entries.length - 4));
      historyToggle.textContent = expanded ? `지난 시그널 ${hiddenCount}개 더 보기` : "지난 시그널 접기";
      return;
    }
    if (target.closest(".recommend-score-help")) {
      window.requestAnimationFrame(() => {
        for (const help of document.querySelectorAll(".recommend-score-help")) {
          const open = help.classList.contains("open");
          help.setAttribute("aria-expanded", String(open));
          if (!open && help instanceof HTMLElement) help.blur();
        }
      });
    }
  });

  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    for (const help of document.querySelectorAll(".recommend-score-help.open")) {
      help.classList.remove("open");
      help.setAttribute("aria-expanded", "false");
      if (help instanceof HTMLElement) help.blur();
    }
  });

  const headings = {
    home: "증권", portfolio: "관심", search: "발견", news: "피드",
    "recent-stocks": "최근 본 종목",
    "ai-stock-response": "AI 종목 대응",
    "ai-signals": "AI 시그널", movers: "TOP 50", chart: "차트 분석",
    "chart-history": "지난 차트 분석", "morning-briefing": "머니 브리핑",
    notifications: "알림", "event-detail": "이벤트 분석",
    "recommend-detail": "추천 종목",
  };
  const rootViews = new Set(primaryRoutes.map((route) => route.view));
  const STAGING_MARKET_CONTEXT_CODES = ["KOSPI", "KOSDAQ", "NASDAQ", "SP500", "DOW", "SOX"];
  const STAGING_MARKET_CONTEXT_LABELS = Object.freeze({
    KOSPI: "코스피",
    KOSDAQ: "코스닥",
    NASDAQ: "나스닥",
    SP500: "S&P500",
    DOW: "다우",
    SOX: "반도체",
  });
  const STAGING_MARKET_CONTEXT_ROTATION_MS = 4_000;
  const marketContextReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)") || null;
  const marketIndexContext = marketContext.querySelector("[data-staging-index-ticker]");
  let marketContextIndex = 0;
  let marketContextRotationTimer = 0;
  const contextualOwners = new Map();
  const initialRequestedContextualView = (() => {
    if (recentStocksRouteActive()) return "recent-stocks";
    const requested = new URLSearchParams(window.location.search).get("view") || "";
    return contextualViewConfig[requested] ? requested : "";
  })();
  let initialContextualRouteSettled = !initialRequestedContextualView;
  let previousSyncedView = document.body.dataset.view || "";

  const primaryViewFor = (view) => {
    if (rootViews.has(view)) return view;
    if (contextualViewConfig[view]) {
      return contextualOwners.get(view) || contextualViewConfig[view].owner;
    }
    return "";
  };

  const normalizedText = (node) => node?.textContent?.replace(/\s+/g, " ")?.trim() || "";

  const syncContextualHeader = (view = document.body.dataset.view || "home") => {
    const effectiveView = recentStocksRouteActive() ? "recent-stocks" : view;
    const config = contextualViewConfig[effectiveView];
    const contextual = Boolean(config);
    activeContextualView = contextual ? effectiveView : "";
    topbar.classList.toggle("is-staging-contextual", contextual);
    contextualTopbar.classList.toggle("is-recommend-live", effectiveView === "recommend-detail");
    document.body.dataset.stagingNavigation = contextual ? "contextual" : view === "stock" ? "detail" : "root";

    marketContext.hidden = contextual;
    topActions.hidden = contextual;
    contextualTopbar.hidden = !contextual;
    if (contextual) {
      marketContext.setAttribute("aria-hidden", "true");
      topActions.setAttribute("aria-hidden", "true");
      contextualTopbar.removeAttribute("aria-hidden");
    } else {
      marketContext.removeAttribute("aria-hidden");
      topActions.removeAttribute("aria-hidden");
      contextualTopbar.setAttribute("aria-hidden", "true");
      return;
    }

    const titleNode = contextualTopbar.querySelector("[data-staging-contextual-title]");
    const subtitleNode = contextualTopbar.querySelector("[data-staging-contextual-subtitle]");
    const spacer = contextualTopbar.querySelector("[data-staging-contextual-spacer]");
    const sourceBack = config.back ? document.querySelector(config.back) : null;
    const sourceAction = config.action ? document.querySelector(config.action) : null;
    const title = normalizedText(config.titleSelector ? document.querySelector(config.titleSelector) : null)
      || config.title;
    const subtitle = effectiveView === "recommend-detail"
      ? recommendationDetailQuoteText()
      : normalizedText(config.subtitleSelector ? document.querySelector(config.subtitleSelector) : null);

    if (titleNode) titleNode.textContent = title;
    if (subtitleNode) {
      subtitleNode.textContent = subtitle;
      subtitleNode.hidden = !subtitle;
      subtitleNode.className = effectiveView === "recommend-detail"
        ? recommendationDetailQuoteTone()
        : "";
    }
    if (contextualBack) {
      contextualBack.setAttribute("aria-label", sourceBack?.getAttribute("aria-label") || `${title} 이전 화면`);
    }
    if (contextualAction) {
      const actionLabel = normalizedText(sourceAction);
      contextualAction.hidden = !sourceAction;
      contextualAction.textContent = actionLabel;
      contextualAction.setAttribute("aria-label", sourceAction?.getAttribute("aria-label") || actionLabel || "화면 설정");
      if (sourceAction?.hasAttribute("aria-haspopup")) {
        contextualAction.setAttribute("aria-haspopup", sourceAction.getAttribute("aria-haspopup"));
      } else {
        contextualAction.removeAttribute("aria-haspopup");
      }
    }
    if (spacer) spacer.hidden = Boolean(sourceAction);
  };

  const syncRecentStocksRoute = () => {
    if (!searchView || !recentStocksPage) return;
    const active = recentStocksRouteActive();
    document.body.classList.toggle("is-staging-recent-stocks", active);
    document.body.dataset.stagingRecentStocks = active ? "open" : "closed";
    recentStocksPage.hidden = !active;
    if (active) {
      searchView.hidden = true;
      renderRecentStocks();
    } else if ((document.body.dataset.view || "") === "search") {
      searchView.hidden = false;
    }
  };

  const marketContextCards = () => {
    const byCode = new Map(
      [...document.querySelectorAll("#home-market-carousel .home-index-card")]
        .map((card) => [String(card.dataset.code || "").toUpperCase(), card]),
    );
    const cards = STAGING_MARKET_CONTEXT_CODES.map((code) => byCode.get(code)).filter(Boolean);
    const available = cards.filter((card) => !card.classList.contains("is-empty"));
    return available.length ? available : cards.slice(0, 1);
  };

  const renderMarketContextCard = (card, { animate = false } = {}) => {
    if (!card || !marketIndexContext) return;
    const cards = marketContextCards();
    const code = String(card.dataset.code || "").toUpperCase();
    const position = Math.max(0, cards.findIndex((candidate) => candidate === card));
    const name = STAGING_MARKET_CONTEXT_LABELS[code]
      || card.querySelector("h2")?.textContent?.trim()
      || code;
    const value = card.querySelector(".home-index-current")?.textContent?.trim() || "확인 중";
    const change = card.querySelector(".home-index-change-rate")?.textContent?.trim() || "";
    const nameNode = marketContext.querySelector("[data-staging-index-name]");
    const valueNode = marketContext.querySelector("[data-staging-index-value]");
    const changeNode = marketContext.querySelector("[data-staging-index-change]");
    if (nameNode) nameNode.textContent = name;
    if (valueNode) valueNode.textContent = value;
    if (changeNode) {
      changeNode.textContent = change;
      changeNode.className = card.classList.contains("positive")
        ? "positive"
        : card.classList.contains("negative")
        ? "negative"
        : "";
    }
    marketContextIndex = position;
    marketIndexContext.dataset.stagingIndexCode = code;
    marketIndexContext.dataset.stagingIndexPosition = String(position + 1);
    marketIndexContext.dataset.stagingIndexTotal = String(cards.length);
    marketIndexContext.setAttribute(
      "aria-label",
      `주요 지수 ${position + 1}/${cards.length}, ${name} ${value}${change ? `, 등락률 ${change}` : ""}`,
    );
    if (animate) {
      marketIndexContext.classList.remove("is-rolling");
      void marketIndexContext.offsetWidth;
      marketIndexContext.classList.add("is-rolling");
    }
  };

  const clearMarketContextRotation = () => {
    if (marketContextRotationTimer) {
      window.clearTimeout(marketContextRotationTimer);
      marketContextRotationTimer = 0;
    }
  };

  const marketContextCanRotate = () => (
    !document.hidden
    && !marketContext.hidden
    && rootViews.has(document.body.dataset.view || "home")
    && marketContextCards().length > 1
    && !marketContextReducedMotion?.matches
  );

  const scheduleMarketContextRotation = () => {
    if (!marketContextCanRotate()) {
      clearMarketContextRotation();
      marketContext.dataset.autoAdvance = "paused";
      return;
    }
    marketContext.dataset.autoAdvance = "scheduled";
    marketContext.dataset.autoAdvanceMs = String(STAGING_MARKET_CONTEXT_ROTATION_MS);
    if (marketContextRotationTimer) return;
    marketContextRotationTimer = window.setTimeout(() => {
      marketContextRotationTimer = 0;
      const cards = marketContextCards();
      if (cards.length < 2) {
        scheduleMarketContextRotation();
        return;
      }
      marketContextIndex = (marketContextIndex + 1) % cards.length;
      marketContext.dataset.autoAdvanceCount = String(
        Number(marketContext.dataset.autoAdvanceCount || 0) + 1,
      );
      renderMarketContextCard(cards[marketContextIndex], { animate: true });
      scheduleMarketContextRotation();
    }, STAGING_MARKET_CONTEXT_ROTATION_MS);
  };

  const syncMarketContext = () => {
    const cards = marketContextCards();
    if (!cards.length) return;
    const currentCode = marketIndexContext?.dataset.stagingIndexCode || "";
    const currentIndex = cards.findIndex(
      (card) => String(card.dataset.code || "").toUpperCase() === currentCode,
    );
    marketContextIndex = currentIndex >= 0
      ? currentIndex
      : Math.min(marketContextIndex, cards.length - 1);
    renderMarketContextCard(cards[marketContextIndex]);
    scheduleMarketContextRotation();
  };

  if (marketContextReducedMotion?.addEventListener) {
    marketContextReducedMotion.addEventListener("change", scheduleMarketContextRotation);
  }

  const decorateWatchRows = () => {
    for (const row of document.querySelectorAll("#watchlist-body .watch-v2-stock-row")) {
      const head = row.querySelector(".watch-v2-stock-head");
      if (!head || head.querySelector(".staging-watch-logo")) continue;
      head.prepend(createStockLogoFrame(row.dataset.code, "staging-watch-logo"));
      const removeButton = row.querySelector(".remove-watch");
      if (removeButton && !removeButton.querySelector("svg")) {
        removeButton.innerHTML = svg(icons.interest);
      }
    }
  };

  const compactAiSignalLabel = (value = "") => {
    const label = String(value || "").trim();
    if (/^부분 매도 대기\(\d+차\)$/.test(label)) return label;
    if (/^부분 수익 확정\(\d+차\)$/.test(label)) return label;
    const pendingProfitStage = label.match(/^(\d+)차 수익확정 대기/);
    if (pendingProfitStage) return `부분 매도 대기(${pendingProfitStage[1]}차)`;
    const confirmedProfitStage = label.match(/^(\d+)차 수익확정/);
    if (confirmedProfitStage) return `부분 수익 확정(${confirmedProfitStage[1]}차)`;
    if (/^전량 매도 대기/.test(label)) return "전량 매도 대기";
    if (/^전량 매도/.test(label)) return "전량 매도 확정";
    if (/^확정 매수/.test(label)) return "매수 확정";
    if (/^확정 매도/.test(label)) return "전량 매도 확정";
    if (/^예비 포착/.test(label)) return "매수 관찰";
    if (/^예비 매수/.test(label)) return "매수 대기";
    if (/^예비 매도/.test(label)) return "매도 대기";
    if (/매수 조건 해제/.test(label)) return "매수 해제";
    if (/매도 조건 해제/.test(label)) return "매도 해제";
    if (/수익확정.*대기/.test(label)) return "부분 매도 대기";
    if (/수익확정/.test(label)) return "부분 수익 확정";
    return label;
  };

  const selectAiSignalSummaryMetrics = (metrics = []) => {
    const byKey = new Map(metrics.map((metric) => [metric.dataset.metric || "", metric]));
    const selected = [];
    const take = (...keys) => {
      const candidate = keys.map((key) => byKey.get(key)).find(Boolean);
      if (candidate && !selected.includes(candidate)) selected.push(candidate);
    };
    take("price", "capture-price", "sell-price", "target", "target-status");
    take("release-result", "condition-status");
    take("execution", "confirmation", "reason", "source");
    if (!selected.length) selected.push(...metrics.filter((metric) => !["score", "capture-score"].includes(metric.dataset.metric)).slice(0, 2));
    return selected.slice(0, 2);
  };

  const decorateAiRows = () => {
    for (const row of document.querySelectorAll("#ai-signals-page-list .home-ai-signal-row")) {
      const headline = row.querySelector(".home-ai-signal-headline");
      if (!headline) continue;
      row.dataset.stagingListRow = "true";
      if (!headline.querySelector(".staging-ai-logo")) {
        headline.prepend(createStockLogoFrame(row.dataset.code, "staging-ai-logo"));
      }

      const identity = headline.querySelector(".home-ai-signal-identity");
      identity?.querySelector(".staging-ai-code")?.remove();

      const state = headline.querySelector(".home-ai-signal-state");
      if (state && !state.dataset.stagingFullLabel) {
        state.dataset.stagingFullLabel = state.textContent.trim();
        state.textContent = compactAiSignalLabel(state.textContent);
      }

      const status = headline.querySelector(".home-ai-signal-status");
      const metrics = Array.from(row.querySelectorAll(".home-ai-signal-metrics > .home-ai-signal-metric"));
      const scoreMetric = metrics.find((metric) => ["score", "capture-score"].includes(metric.dataset.metric));
      const returnMetric = metrics.find((metric) => metric.dataset.metric === "return");
      const scoreValue = scoreMetric?.querySelector(".home-ai-signal-metric-value")?.textContent?.trim() || "";
      let score = status?.querySelector(".staging-ai-score");
      if (status && scoreValue) {
        if (!score) {
          score = document.createElement("small");
          score.className = "staging-ai-score";
          status.appendChild(score);
        }
        score.textContent = scoreValue;
      } else {
        score?.remove();
      }
      const returnValueNode = returnMetric?.querySelector(".home-ai-signal-metric-value");
      const returnValue = returnValueNode?.textContent?.trim() || "";
      let statusReturn = status?.querySelector(".staging-ai-return");
      if (status && returnValue) {
        if (!statusReturn) {
          statusReturn = document.createElement("small");
          statusReturn.className = "staging-ai-return";
          status.appendChild(statusReturn);
        }
        statusReturn.textContent = returnValue;
        statusReturn.className = `staging-ai-return${returnValueNode.classList.contains("positive") ? " positive" : returnValueNode.classList.contains("negative") ? " negative" : ""}`;
      } else {
        statusReturn?.remove();
      }

      for (const metric of metrics) metric.classList.remove("is-staging-visible", "is-staging-first", "is-staging-second");
      selectAiSignalSummaryMetrics(metrics)
        .sort((left, right) => metrics.indexOf(left) - metrics.indexOf(right))
        .forEach((metric, index) => {
        metric.classList.add("is-staging-visible", index === 0 ? "is-staging-first" : "is-staging-second");
        });

      if (!headline.querySelector(".staging-ai-chevron")) {
        const chevron = document.createElement("span");
        chevron.className = "staging-ai-chevron";
        chevron.innerHTML = svg(icons.chevron);
        headline.appendChild(chevron);
      }
    }
  };

  const decoratePinnedEmptyState = () => {
    const heading = document.querySelector("#recommend-history-view > .app-section-heading");
    const headingEyebrow = heading?.querySelector("span");
    const headingTitle = heading?.querySelector("h2");
    if (headingEyebrow) headingEyebrow.hidden = true;
    if (headingTitle) headingTitle.textContent = "핀한 종목";

    const list = document.getElementById("recommend-history-list");
    const meta = document.getElementById("recommend-history-meta");
    const hasCards = Boolean(list?.querySelector(".recommend-track-card"));
    if (meta) meta.hidden = !hasCards;
    if (!list || hasCards) return;
    const message = Array.from(list.children).find((node) => (
      node.matches?.("p.muted") && /핀 설정하기/.test(node.textContent || "")
    ));
    if (!message || message.classList.contains("staging-pinned-empty")) return;
    message.className = "staging-pinned-empty";
    message.setAttribute("role", "status");
    message.innerHTML = `
      <span class="staging-pinned-empty-figure" aria-hidden="true">
        <svg viewBox="0 0 96 96" focusable="false">
          <circle cx="48" cy="48" r="39"></circle>
          <path d="M35 28h26v22l7 9H28l7-9V28Z"></path>
          <path d="M48 59v12"></path>
          <path class="is-spark" d="m67 23 1.8 4.6 4.7 1.8-4.7 1.8-1.8 4.6-1.8-4.6-4.7-1.8 4.7-1.8L67 23Z"></path>
        </svg>
      </span>
      <strong>핀한 종목이 없어요</strong>
      <span>추천에서 핀을 누르면 시작일과 이후 수익률을 한곳에서 확인할 수 있어요.</span>
      <button type="button" data-staging-view="search">종목 찾아보기</button>
    `;
  };

  let lastCapturedRecentCode = "";
  const parseRecentStockRate = (value = "") => {
    const parsed = Number(String(value).replace(/[()%+,\s]/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  };
  const captureCurrentRecentStock = () => {
    if ((document.body.dataset.view || "") !== "stock") return;
    let stock = null;
    let dashboardData = null;
    try {
      stock = typeof state === "object" ? state.currentStock : null;
      dashboardData = typeof state === "object" ? state.currentDashboard : null;
    } catch {
      return;
    }
    const code = String(stock?.code || dashboardData?.code || "").trim();
    const name = String(stock?.name || dashboardData?.name || dashboardData?.profile?.name || "").trim();
    if (!code || !name) return;
    const quote = dashboardData?.quote || {};
    const priceFromDom = document.getElementById("quote-price")?.textContent?.replace(/\s+/g, " ")?.trim() || "";
    const rateFromDom = document.getElementById("quote-change")?.textContent?.replace(/[()]/g, "")?.trim() || "";
    const numericPrice = Number(quote?.price);
    const numericRate = Number(quote?.change_rate);
    const item = {
      code,
      name,
      market: String(stock?.market || dashboardData?.market || dashboardData?.profile?.market || "").trim(),
      priceText: priceFromDom && priceFromDom !== "-"
        ? priceFromDom
        : Number.isFinite(numericPrice) ? formatNumber(Math.round(numericPrice)) : "-",
      rateText: rateFromDom && rateFromDom !== "-"
        ? rateFromDom
        : Number.isFinite(numericRate) ? formatPercent(numericRate) : "-",
      changeRate: Number.isFinite(numericRate) ? numericRate : parseRecentStockRate(rateFromDom),
      viewedAt: Date.now(),
    };
    const items = readRecentStocks();
    const existingIndex = items.findIndex((recent) => recent.code === code);
    const existing = existingIndex >= 0 ? items[existingIndex] : null;
    const shouldPromote = lastCapturedRecentCode !== code;
    if (!shouldPromote && existing) {
      item.viewedAt = existing.viewedAt || item.viewedAt;
      const unchanged = ["name", "market", "priceText", "rateText", "changeRate"]
        .every((key) => existing[key] === item[key]);
      if (unchanged) return;
    }
    if (existingIndex >= 0) items.splice(existingIndex, 1);
    if (shouldPromote) items.unshift(item);
    else items.splice(Math.max(0, existingIndex), 0, item);
    lastCapturedRecentCode = code;
    writeRecentStocks(items);
    renderRecentStocks();
  };

  const syncStockOrderability = () => {
    const marketStatus = stockHero?.querySelector(".staging-stock-market-status");
    const orderability = marketStatus?.querySelector(".staging-stock-orderability");
    const separator = marketStatus?.querySelector(".staging-stock-status-separator");
    const detail = marketStatus?.querySelector("#stock-market-status-label");
    if (!marketStatus || !orderability || !separator || !detail) return;

    const detailText = detail.textContent?.replace(/\s+/g, " ")?.trim() || "장 상태 확인 중";
    const tone = marketStatus.dataset.statusTone || "";
    const isClosed = tone === "closed" || /마감|종료|휴장/.test(detailText);
    const isWaiting = tone === "waiting" || /대기/.test(detailText);
    const isLive = tone === "live" || /진행중/.test(detailText);
    const state = isClosed ? "closed" : isWaiting ? "waiting" : isLive ? "live" : "loading";
    const summary = isClosed
      ? "장 마감"
      : isWaiting
        ? "주문 대기"
        : isLive
          ? "실시간 주문 가능"
          : "장 상태 확인 중";
    const showDetail = (isLive || isWaiting) && detailText !== summary;

    if (orderability.textContent !== summary) orderability.textContent = summary;
    separator.hidden = !showDetail;
    detail.hidden = !showDetail;
    marketStatus.dataset.stagingOrderability = state;
    const spokenStatus = showDetail ? `${summary}, ${detailText}` : summary;
    marketStatus.setAttribute("aria-label", `${spokenStatus}, 국내주식 거래시간 안내 열기`);
  };

  const syncStockChangeContext = () => {
    const target = stockHero?.querySelector("[data-staging-stock-change-context]");
    if (!target) return;

    let dashboardData = null;
    let priceRows = [];
    try {
      dashboardData = typeof state === "object" ? state.currentDashboard : null;
      priceRows = typeof state === "object" && Array.isArray(state.stockPriceRows)
        ? state.stockPriceRows
        : [];
    } catch {
      dashboardData = null;
      priceRows = [];
    }
    const quote = dashboardData?.quote || null;
    const clock = stagingKoreaClock();
    const quoteDate = stagingChartDateKey(quote?.trade_date);
    const tradeDates = priceRows
      .map((row) => stagingChartDateKey(row?.trade_date || row?.date))
      .filter(Boolean);
    const sessionStarted = quoteDate === clock.date
      && (quote?.is_live === true || clock.minutes >= 9 * 60 || tradeDates.includes(clock.date));
    const context = window.SecretNoteStockChangeCopy?.resolveChangeContext?.({
      currentDate: clock.date,
      quoteTradeDate: quoteDate,
      tradeDates,
      sessionStarted,
    }) || { label: "최근 장에서", mode: "completed-session", quoteDate: "", referenceDate: "" };

    if (target.textContent !== context.label) target.textContent = context.label;
    target.dataset.stagingChangeContext = context.mode;
    if (context.quoteDate) target.dataset.stagingQuoteDate = context.quoteDate;
    else delete target.dataset.stagingQuoteDate;
    if (context.referenceDate) target.dataset.stagingReferenceDate = context.referenceDate;
    else delete target.dataset.stagingReferenceDate;
  };

  const syncStockHero = () => {
    if (!stockHero) return;
    const copyText = (targetSelector, sourceSelector, fallback = "") => {
      const target = stockHero.querySelector(targetSelector);
      const source = document.querySelector(sourceSelector);
      const value = source?.textContent?.replace(/\s+/g, " ")?.trim() || fallback;
      if (target && target.textContent !== value) target.textContent = value;
    };
    copyText("[data-staging-stock-name]", "#stock-name", "종목 분석");
    copyText("[data-staging-stock-price]", "#quote-price", "-");

    const changeTarget = stockHero.querySelector("[data-staging-stock-change]");
    const changeSource = document.getElementById("stock-change-value")?.textContent?.replace(/\s+/g, " ")?.trim() || "-";
    const formattedChange = changeSource === "-" || changeSource.endsWith("원") ? changeSource : `${changeSource}원`;
    if (changeTarget && changeTarget.textContent !== formattedChange) {
      changeTarget.textContent = formattedChange;
    }
    const rateTarget = stockHero.querySelector("[data-staging-stock-rate]");
    const rateSource = document.getElementById("quote-change")?.textContent?.replace(/\s+/g, " ")?.trim() || "";
    const formattedRate = !rateSource || rateSource.startsWith("(") ? rateSource : `(${rateSource})`;
    if (rateTarget && rateTarget.textContent !== formattedRate) {
      rateTarget.textContent = formattedRate;
    }
    syncStockChangeContext();

    const trendSource = document.querySelector("#stock-change-value.positive, #quote-change.positive, #stock-change-value.negative, #quote-change.negative");
    const changeRow = stockHero.querySelector(".staging-stock-hero-change");
    const isPositive = Boolean(trendSource?.classList.contains("positive"));
    const isNegative = Boolean(trendSource?.classList.contains("negative"));
    for (const toneTarget of [stockHero, changeRow]) {
      if (!toneTarget) continue;
      toneTarget.classList.toggle("positive", isPositive);
      toneTarget.classList.toggle("negative", isNegative);
      toneTarget.classList.toggle("muted", !isPositive && !isNegative);
    }
    syncStockOrderability();
    captureCurrentRecentStock();
  };

  const decorateMobileIllustrations = () => {
    const watchToggle = document.getElementById("watch-toggle");
    if (watchToggle && !watchToggle.querySelector("svg")) {
      watchToggle.innerHTML = svg(icons.interest);
    }

    const digestIcon = document.querySelector(".morning-money-digest-head > span");
    if (digestIcon && !digestIcon.querySelector("svg")) digestIcon.innerHTML = svg(icons.clock);
    const coinIcon = document.querySelector(".morning-money-popover-coin");
    if (coinIcon && !coinIcon.querySelector("svg")) coinIcon.innerHTML = svg(icons.coin);

    for (const icon of document.querySelectorAll(".morning-money-category-icon")) {
      if (icon.dataset.stagingVectorIcon === "true") continue;
      const category = icon.closest("[data-category]")?.getAttribute("data-category") || "";
      icon.innerHTML = svg(/global|world|macro|해외/i.test(category) ? icons.globe : icons.news);
      icon.dataset.stagingVectorIcon = "true";
    }
    for (const control of document.querySelectorAll("a, button, span")) {
      if (control.dataset.stagingExternalVector === "true" || control.childElementCount > 0) continue;
      const original = control.textContent || "";
      if (!original.includes("↗")) continue;
      const label = original.replaceAll("↗", "").trimEnd();
      control.replaceChildren(document.createTextNode(label ? `${label} ` : ""));
      control.insertAdjacentHTML("beforeend", svg(icons.external, "staging-external-icon"));
      control.dataset.stagingExternalVector = "true";
    }

    for (const hint of document.querySelectorAll(".stock-sector-margin-scrub-hint")) {
      if (hint.dataset.stagingVectorHint === "true") continue;
      const label = (hint.textContent || "").replace(/^\s*↔\s*/, "").trim();
      hint.replaceChildren();
      hint.insertAdjacentHTML("afterbegin", svg(icons.horizontal));
      hint.append(document.createTextNode(label));
      hint.dataset.stagingVectorHint = "true";
    }

    const emptySelectors = [
      ".watchlist-empty-card",
      ".push-history-state:has(strong)",
      ".morning-money-empty-state",
      ".app-empty-state",
      ".stock-community-empty",
    ];
    for (const emptyState of document.querySelectorAll(emptySelectors.join(","))) {
      if (emptyState.querySelector(".staging-empty-illustration")) continue;
      emptyState.insertAdjacentHTML("afterbegin", emptyStackIllustration);
    }
  };

  let stockChromeFrame = 0;
  const syncStockScrollChrome = () => {
    stockChromeFrame = 0;
    const commandbar = document.querySelector("#stock-view .stock-v3-commandbar");
    const stockView = document.getElementById("stock-view");
    const tabsSentinel = document.getElementById("stock-detail-tabs-sentinel");
    const active = document.body.dataset.view === "stock" && !stockView?.hidden;
    if (!commandbar || !stockHero || !active || window.innerWidth > 980) {
      commandbar?.classList.remove("is-scrolled");
      stockTabs?.classList.remove("is-staging-pinned");
      stockTabs?.style.removeProperty("--staging-stock-tabs-top");
      return;
    }
    const heroBottom = stockHero.getBoundingClientRect().bottom;
    const commandBottom = commandbar.getBoundingClientRect().bottom;
    commandbar.classList.toggle("is-scrolled", heroBottom <= commandBottom + 1);
    const pinnedTop = commandbar.getBoundingClientRect().height || 68;
    const tabsHeight = stockTabs?.getBoundingClientRect().height || 56;
    const tabsWithinStockView = (stockView?.getBoundingClientRect().bottom ?? Infinity) > pinnedTop + tabsHeight;
    const shouldPinTabs = Boolean(tabsSentinel)
      && tabsSentinel.getBoundingClientRect().top <= pinnedTop + 1
      && tabsWithinStockView;
    stockTabs?.style.setProperty("--staging-stock-tabs-top", `${pinnedTop}px`);
    stockTabs?.classList.toggle("is-staging-pinned", shouldPinTabs);
  };
  const scheduleStockScrollChrome = () => {
    if (stockChromeFrame) return;
    stockChromeFrame = window.requestAnimationFrame(syncStockScrollChrome);
  };

  const replaceStrategyLanguage = (value = "") => {
    const replacements = [
      ["예상 매수가", "예상 전략 기준가"],
      ["매수 후 수익률", "신호 이후 수익률"],
      ["해당 매매 수익률", "해당 신호 수익률"],
      ["매수가", "전략 기준가"],
      ["매도가", "전략 종료가"],
    ];
    return replacements.reduce(
      (result, [source, target]) => result.replaceAll(source, target),
      String(value || ""),
    );
  };

  const clarifyStrategyScope = () => {
    const stageTab = document.getElementById("ai-signal-stage-buy-holding");
    const stageLabel = stageTab
      ? Array.from(stageTab.childNodes).find((node) => node.nodeType === Node.TEXT_NODE)
      : null;
    if (stageLabel && stageLabel.textContent?.includes("확정 매수·보유")) {
      stageLabel.textContent = "확정 매수 신호 ";
    }

    for (const label of document.querySelectorAll(
      "#ai-signals-view .home-ai-signal-metric-label",
    )) {
      const clarified = replaceStrategyLanguage(label.textContent);
      if (clarified !== label.textContent) label.textContent = clarified;
    }
    for (const labelled of document.querySelectorAll(
      "#ai-signals-view .home-ai-signal-row[aria-label], #ai-signals-view .home-ai-signal-metrics[aria-label]",
    )) {
      const current = labelled.getAttribute("aria-label") || "";
      const clarified = replaceStrategyLanguage(current);
      if (clarified !== current) labelled.setAttribute("aria-label", clarified);
    }

    const nextConfirmation = document.getElementById("quant-next-confirmation");
    if (nextConfirmation?.textContent.includes("현재 보유 비중은")) {
      nextConfirmation.textContent = nextConfirmation.textContent.replace(
        "현재 보유 비중은",
        "현재 AI 전략 비중은",
      );
    }
  };

  const markTDSContracts = () => {
    const roleSelectors = {
      Top: [
        ".app-topbar", ".staging-market-context", ".staging-contextual-topbar", ".secondary-commandbar",
        "#stock-view .stock-v3-commandbar",
      ],
      ListHeader: [
        ".home-flat-section-head", ".home-ai-signals-head", ".home-surge-head",
        ".trend-calendar-head", ".app-section-heading", ".trend-watchlist-head",
        ".stock-v3-section-head", ".morning-money-category-head",
      ],
      ListRow: [
        ".watch-v2-stock-row", ".market-ranking-row", ".market-rank-row",
        ".home-ai-signal-row", ".push-history-item", ".thread-item",
        ".morning-money-news-item", ".stock-etf-distribution-row",
      ],
      Badge: [
        ".market-chip", ".thread-tag", ".event-detail-tag",
        ".home-ai-signal-state", ".recommend-detail-ai-badge",
      ],
      Tab: [
        ".portfolio-tabs", ".watchlist-content-tabs", ".ai-signal-mode-tabs", ".stock-detail-tabs",
      ],
      SegmentedControl: [
        ".market-segment", ".staging-feed-modes",
        ".watch-v3-tabs", ".ai-signal-stage-tabs", ".ai-signal-history-filters",
        ".home-ranking-subfilters",
      ],
      SearchField: [".discovery-search", ".stock-v3-search .search-box"],
      Skeleton: [".page-loading-indicator", ".skeleton", "[class*='skeleton']"],
      BottomSheet: [
        ".install-sheet-card", ".push-notification-sheet-card",
      ],
      BottomCTA: [".stock-purchase-button", ".stock-order-cta", ".fixed-bottom-cta"],
      BottomInfo: [
        ".service-footer", ".morning-money-disclaimer",
      ],
      Result: [".watchlist-empty-card", ".staging-pinned-empty", ".app-empty-state"],
    };
    for (const [role, selectors] of Object.entries(roleSelectors)) {
      for (const node of document.querySelectorAll(selectors.join(","))) {
        node.dataset.tdsRole = role;
      }
    }

    const textSelectors = {
      title: [
        "[data-staging-heading]", ".home-flat-section-head h2",
        ".home-ai-signals-head h2", ".home-surge-head h2",
        ".app-section-heading h2", ".stock-v3-section-head h2",
        ".event-detail-section h3", ".recommend-detail-section h2",
        ".watch-v2-stock-name-row > strong", ".market-leaderboard-name strong",
        ".recommend-name strong", ".home-ai-signal-name",
      ],
      body: [
        ".thread-item-story", ".morning-money-news-summary",
        ".morning-money-news-letter", ".event-detail-section > p",
        ".recommend-detail-lead", ".recommend-detail-verdict",
      ],
      value: [
        ".home-index-current", ".home-index-change", ".stock-v3-price-line",
        ".watch-stock-inline-price", ".watch-stock-inline-change",
        ".market-ranking-price", ".market-ranking-change",
      ],
    };
    for (const [kind, selectors] of Object.entries(textSelectors)) {
      for (const node of document.querySelectorAll(selectors.join(","))) {
        node.dataset.tdsText = kind;
      }
    }
    const pageHeading = document.querySelector("[data-staging-heading]");
    if (pageHeading) {
      pageHeading.setAttribute("role", "heading");
      pageHeading.setAttribute("aria-level", "1");
    }
  };

  let syncFrame = 0;
  const scheduleContentSync = () => {
    if (syncFrame) return;
    syncFrame = window.requestAnimationFrame(() => {
      syncFrame = 0;
      syncMarketContext();
      upgradePreopenMarketCharts();
      syncHomeMarketMarquee();
      decorateHomeAiStockResponseRows();
      decorateRecommendationCards();
      decorateRecommendationDetail();
      syncStagingFeed();
      decorateStagingBriefingArticle();
      syncRecommendationDetailQuoteScope();
      syncStagingAiStockResponseQuoteScope();
      syncContextualHeader();
      syncStagingWatchlist();
      decorateWatchRows();
      decorateAiRows();
      decoratePinnedEmptyState();
      decorateMobileIllustrations();
      syncStockHero();
      upgradeStagingStockPriceChart();
      clarifyStrategyScope();
      markTDSContracts();
      scheduleStockScrollChrome();
    });
  };

  const syncShell = () => {
    syncStagingAiStockResponseRoute();
    const observedView = document.body.dataset.view || "";
    const view = observedView || "home";
    if (view !== "stock") lastCapturedRecentCode = "";
    if (rootViews.has(previousSyncedView) && contextualViewConfig[view]) {
      if (!initialContextualRouteSettled && view === initialRequestedContextualView) {
        initialContextualRouteSettled = true;
      } else {
        contextualOwners.set(view, previousSyncedView);
      }
    } else if (!initialContextualRouteSettled && view === initialRequestedContextualView) {
      initialContextualRouteSettled = true;
    }
    const activeView = primaryViewFor(view);
    for (const item of bottomNav.querySelectorAll("[data-app-view]")) {
      const active = item.dataset.appView === activeView;
      item.classList.toggle("active", active);
      if (active) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    }
    const heading = marketContext.querySelector("[data-staging-heading]");
    if (heading) heading.textContent = headings[view] || "비밀노트";
    syncPrimaryTopAction(view);
    syncRecentStocksRoute();
    syncRecommendationDetailQuoteScope();
    syncStagingAiStockResponseQuoteScope();
    syncContextualHeader(view);
    scheduleMarketContextRotation();
    syncHotCommunityQuoteScope();
    syncHotCommunityRotation();
    syncRecentStockQuoteScope();
    if (observedView) previousSyncedView = view;
    syncServiceUpdateExperience();
    scheduleContentSync();
    scheduleStockScrollChrome();
  };

  new MutationObserver(syncShell).observe(document.body, { attributes: true, attributeFilter: ["data-view"] });
  const dataObserver = new MutationObserver(scheduleContentSync);
  for (const node of [
    document.getElementById("home-market-carousel"),
    document.getElementById("home-market-signal-window"),
    document.getElementById("home-ai-response-personal-list"),
    document.getElementById("watchlist-body"),
    document.getElementById("watchlist-meta"),
    document.getElementById("watchlist-strategy"),
    document.getElementById("trend-watch-stock-rail"),
    document.getElementById("trend-watchlist-meta"),
    document.getElementById("trend-watch-news-board"),
    document.getElementById("recommend-history-list"),
    document.getElementById("ai-signals-page-list"),
    document.getElementById("quant-signal-content"),
    document.getElementById("stock-view"),
    document.getElementById("push-history-list"),
    document.getElementById("morning-money-briefing-content"),
    document.getElementById("trend-events"),
    document.getElementById("market-ranking-command-title"),
    document.getElementById("push-history-title"),
    document.getElementById("recommend-detail-name"),
    document.getElementById("recommend-detail-code"),
    document.getElementById("recommend-status"),
    document.getElementById("recommend-list"),
    document.getElementById("recommend-detail-content"),
  ]) {
    if (node) dataObserver.observe(node, { childList: true, subtree: true, characterData: true });
  }
  window.addEventListener("scroll", scheduleStockScrollChrome, { passive: true, capture: true });
  window.addEventListener("resize", scheduleStockScrollChrome, { passive: true });
  window.addEventListener("orientationchange", scheduleStockScrollChrome, { passive: true });
  window.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearMarketContextRotation();
      marketContext.dataset.autoAdvance = "paused";
      syncHotCommunityQuoteScope();
      syncHotCommunityRotation();
      syncRecentStockQuoteScope();
      syncRecommendationDetailQuoteScope();
      syncStagingAiStockResponseQuoteScope();
      if (typeof clearQuoteStreamScope === "function") {
        clearQuoteStreamScope("staging-recent-stocks");
        clearQuoteStreamScope("staging-hot-community");
        clearQuoteStreamScope("staging-recommend-detail");
        clearQuoteStreamScope("staging-ai-stock-response");
      }
      return;
    }
    scheduleMarketContextRotation();
    syncHotCommunityQuoteScope();
    syncHotCommunityRotation();
    syncRecentStockQuoteScope();
    syncRecommendationDetailQuoteScope();
    syncStagingAiStockResponseQuoteScope();
  });
  window.addEventListener("popstate", (event) => {
    const returningFromAiStockResponse = !stagingAiStockResponsePage?.hidden;
    if (returningFromAiStockResponse && !stagingAiStockResponseRouteActive()) {
      event.stopImmediatePropagation();
      closeStagingAiStockResponse();
      syncShell();
      return;
    }
    window.requestAnimationFrame(() => {
      syncShell();
      window.scrollTo({
        top: returningFromAiStockResponse && !stagingAiStockResponseRouteActive()
          ? stagingAiStockResponseReturnScrollY
          : 0,
        behavior: "auto",
      });
    });
  });
  window.requestAnimationFrame(() => {
    syncShell();
    scheduleContentSync();
    scheduleStockScrollChrome();
  });
})();
