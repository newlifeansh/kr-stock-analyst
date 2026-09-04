const DASHBOARD_SW_VERSION = "20260904v464";
const DASHBOARD_BUILD_VERSION = "20260904v464";
const STATIC_CACHE = `secret-note-static-${DASHBOARD_SW_VERSION}-${DASHBOARD_BUILD_VERSION}`;
const STATIC_ASSETS = [
  "/assets/dashboard/styles.css?v=20260904v464&build=20260904v464",
  "/assets/staging/adaptive-theme.js?v=20260828-tds-adaptive-v77-shortcuts",
  "/assets/staging/dark-theme.css?v=20260828-tds-adaptive-v77-shortcuts-contextual-safe-area-v128-stock-search-v129-ai-response-v130-home-signal-action-v131-notification-sheet-v132-ai-signal-spacing-v133-chart-pattern-integrity-v134-ai-stock-response-v135-morning-preliminary-v136-multi-signal-response-v137-discovery-search-contrast-v138-ai-signal-basis-stack-v140-ai-response-beginner-v141-semantic-focus-v142-header-action-icons-v143-gpt-page-summary-v144-gpt-briefing-v145-plain-language-detail-v146-investor-action-copy-v147-investor-situation-loading-v148-position-guide-v149-position-input-v150-live-quote-decision-plan-v151-manual-refresh-holding-map-v152-notification-consent-v153",
  "/assets/staging/toss-fidelity.css?v=20260828-tds-adaptive-v77-shortcuts-contextual-safe-area-v128-stock-search-v129-ai-response-v130-home-signal-action-v131-notification-sheet-v132-ai-signal-spacing-v133-chart-pattern-integrity-v134-ai-stock-response-v135-morning-preliminary-v136-multi-signal-response-v137-discovery-search-contrast-v138-ai-signal-basis-stack-v140-ai-response-beginner-v141-semantic-focus-v142-header-action-icons-v143-gpt-page-summary-v144-gpt-briefing-v145-plain-language-detail-v146-investor-action-copy-v147-investor-situation-loading-v148-position-guide-v149-position-input-v150-live-quote-decision-plan-v151-manual-refresh-holding-map-v152-notification-consent-v153",
  "/assets/staging/ai-stock-response-logic.js?v=20260904-production-gpt-v93",
  "/assets/staging/stock-change-copy-logic.js?v=20260904-production-gpt-v93",
  "/assets/staging/toss-ia.js?v=20260904-production-gpt-v93",
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
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("secret-note-static-") && key !== STATIC_CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
      // Installed dashboard pages can keep an old script in memory even after
      // this worker takes control. Reload them once to activate the new shell.
      .then(() => self.clients.matchAll({ type: "window", includeUncontrolled: true }))
      .then((clients) => Promise.all(clients.map((client) => {
        const url = new URL(client.url);
        if (url.origin !== self.location.origin || !url.pathname.startsWith("/dashboard")) {
          return undefined;
        }
        const currentBuild = url.searchParams.get("app_build");
        if (!currentBuild || currentBuild === DASHBOARD_BUILD_VERSION) {
          return undefined;
        }
        url.searchParams.set("app_build", DASHBOARD_BUILD_VERSION);
        return client.navigate(url.href).catch(() => undefined);
      })))
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
  if (url.pathname.startsWith("/stocks/") || url.pathname.startsWith("/market/") || url.pathname.startsWith("/watchlists/")) {
    return;
  }
  if (request.mode === "navigate") {
    // Always request the current HTML shell. Static files are versioned and
    // cached below, but an old shell can otherwise keep referencing old files.
    event.respondWith(fetch(request));
    return;
  }
  if (url.pathname.startsWith("/assets/dashboard/") || url.pathname.startsWith("/assets/staging/")) {
    // The HTML shell versions every asset, but a network-first strategy also
    // prevents a dormant service worker from masking a newly deployed bundle.
    event.respondWith(
      fetch(request, { cache: "no-store" })
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || Response.error()))
    );
  }
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: "새 알림", body: event.data?.text() || "중요한 알림이 도착했습니다." };
  }
  const title = payload.title || "새 알림";
  const options = {
    body: payload.body || "관심종목의 중요한 변화가 있어요.",
    icon: "/assets/dashboard/icons/icon-192.png?v=20260620bq",
    badge: "/assets/dashboard/icons/icon-192.png?v=20260620bq",
    tag: payload.tag || "secret-note-push",
    renotify: true,
    data: { url: payload.url || "/dashboard?view=portfolio", kind: payload.kind || "general" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = new URL(event.notification.data?.url || "/dashboard?view=portfolio", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          return client.navigate(targetUrl).then(() => client.focus());
        }
      }
      return self.clients.openWindow ? self.clients.openWindow(targetUrl) : undefined;
    })
  );
});
