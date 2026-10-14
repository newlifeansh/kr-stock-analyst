const DASHBOARD_SW_VERSION = "20261014us148";
const STATIC_CACHE = `secret-note-us-static-${DASHBOARD_SW_VERSION}`;
const US_GATEWAY_PREFIX = self.location.pathname.startsWith("/us-gateway/") ? "/us-gateway" : "";
const STATIC_ASSETS = [
  "/us?view=overview",
  `${US_GATEWAY_PREFIX}/assets/nasdaq/styles.css?v=20261014us148`,
  `${US_GATEWAY_PREFIX}/assets/nasdaq/app.js?v=20261014us148`,
  `${US_GATEWAY_PREFIX}/assets/nasdaq/icons/icon-192.png?v=20260620bq`,
  `${US_GATEWAY_PREFIX}/assets/nasdaq/icons/icon-512.png?v=20260620bq`,
  `${US_GATEWAY_PREFIX}/assets/nasdaq/icons/apple-touch-icon.png?v=20260620bq`
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
    event.respondWith(fetch(request).catch(() => caches.match("/us?view=overview")));
    return;
  }
  if (url.pathname.startsWith("/assets/nasdaq/") || url.pathname.startsWith("/us-gateway/assets/nasdaq/")) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
        return response;
      }))
    );
  }
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: "미국증시 새 알림", body: event.data?.text() || "미국 시장의 중요한 변화가 있어요." };
  }
  const requestedUrl = new URL(payload.url || "/us?view=watchlist", self.location.origin);
  const targetUrl = requestedUrl.origin === self.location.origin && requestedUrl.pathname.startsWith("/us")
    ? requestedUrl.href
    : new URL("/us?view=watchlist", self.location.origin).href;
  event.waitUntil(self.registration.showNotification(payload.title || "미국증시 새 알림", {
    body: payload.body || "미국 시장의 중요한 변화가 있어요.",
    icon: `${US_GATEWAY_PREFIX}/assets/nasdaq/icons/icon-192.png?v=20260620bq`,
    badge: `${US_GATEWAY_PREFIX}/assets/nasdaq/icons/icon-192.png?v=20260620bq`,
    tag: payload.tag || "secret-note-us-push",
    renotify: true,
    data: { url: targetUrl, kind: payload.kind || "general", market_scope: "us" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const requestedUrl = new URL(
    event.notification.data?.url || "/us?view=watchlist",
    self.location.origin,
  );
  const targetUrl = requestedUrl.origin === self.location.origin && requestedUrl.pathname.startsWith("/us")
    ? requestedUrl.href
    : new URL("/us?view=watchlist", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (new URL(client.url).pathname.startsWith("/us") && "focus" in client) {
          return client.navigate(targetUrl).then(() => client.focus());
        }
      }
      return self.clients.openWindow ? self.clients.openWindow(targetUrl) : undefined;
    })
  );
});
