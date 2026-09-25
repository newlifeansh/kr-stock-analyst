const DASHBOARD_SW_VERSION = "20260925us116";
const STATIC_CACHE = `secret-note-us-static-${DASHBOARD_SW_VERSION}`;
const STATIC_ASSETS = [
  "/us?view=home",
  "/assets/dashboard/styles.css?v=20260925us116&build=20260925us116",
  "/assets/staging/adaptive-theme.js?v=20260828-tds-adaptive-v77-shortcuts",
  "/assets/staging/dark-theme.css?v=20260828-tds-adaptive-v77-shortcuts-contextual-safe-area-v128-stock-search-v129-ai-response-v130-home-signal-action-v131-notification-sheet-v132-ai-signal-spacing-v133-chart-pattern-integrity-v134-ai-stock-response-v135-morning-preliminary-v136-multi-signal-response-v137-discovery-search-contrast-v138-ai-signal-basis-stack-v140-ai-response-beginner-v141-semantic-focus-v142-header-action-icons-v143-gpt-page-summary-v144-gpt-briefing-v145-plain-language-detail-v146-investor-action-copy-v147-investor-situation-loading-v148-position-guide-v149-position-input-v150-live-quote-decision-plan-v151-manual-refresh-holding-map-v152-notification-consent-v153-us-ranking-v154-public-signal-v155-signal-summary-v157-ai-signal-market-toggle-v158-feed-market-toggle-v159-watchlist-compact-v160-stable-loading-v161-ai-signal-landing-v165-recommendation-overview-v166-recommendation-evidence-v169-domestic-market-v170",
  "/assets/staging/toss-fidelity.css?v=20260828-tds-adaptive-v77-shortcuts-contextual-safe-area-v128-stock-search-v129-ai-response-v130-home-signal-action-v131-notification-sheet-v132-ai-signal-spacing-v133-chart-pattern-integrity-v134-ai-stock-response-v135-morning-preliminary-v136-multi-signal-response-v137-discovery-search-contrast-v138-ai-signal-basis-stack-v140-ai-response-beginner-v141-semantic-focus-v142-header-action-icons-v143-gpt-page-summary-v144-gpt-briefing-v145-plain-language-detail-v146-investor-action-copy-v147-investor-situation-loading-v148-position-guide-v149-position-input-v150-live-quote-decision-plan-v151-manual-refresh-holding-map-v152-notification-consent-v153-us-ranking-v154-public-signal-v155-signal-summary-v157-ai-signal-market-toggle-v158-feed-market-toggle-v159-watchlist-compact-v160-stable-loading-v161-ai-signal-landing-v165-recommendation-overview-v166-recommendation-evidence-v169-domestic-market-v170",
  "/assets/staging/ai-stock-response-logic.js?v=20260921-domestic-market-v116",
  "/assets/staging/stock-change-copy-logic.js?v=20260921-domestic-market-v116",
  "/assets/staging/toss-ia.js?v=20260921-domestic-market-v116",
  "/dashboard-app-v170.js?v=20260925us116",
  "/assets/dashboard/icons/icon-192.png?v=20260620bq",
  "/assets/dashboard/icons/icon-512.png?v=20260620bq",
  "/assets/dashboard/icons/apple-touch-icon.png?v=20260620bq"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => undefined))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("secret-note-us-static-") && key !== STATIC_CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  if (url.pathname.startsWith("/us/stocks/") || url.pathname.startsWith("/us/market/") || url.pathname.startsWith("/us/watchlists/") || url.pathname.startsWith("/market/")) {
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/us?view=home")));
    return;
  }
  if (url.pathname === "/dashboard-app-v170.js" || url.pathname.startsWith("/assets/dashboard/") || url.pathname.startsWith("/assets/staging/")) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
        return response;
      }))
    );
  }
});
