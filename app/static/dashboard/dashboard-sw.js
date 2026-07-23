const DASHBOARD_SW_VERSION = "20260724kr40";
const STATIC_CACHE = `secret-note-static-${DASHBOARD_SW_VERSION}`;
const STATIC_ASSETS = [
  "/dashboard?view=trend",
  "/assets/dashboard/styles.css?v=20260724kr40",
  "/assets/dashboard/app.js?v=20260724kr40",
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
    event.respondWith(fetch(request).catch(() => caches.match("/dashboard?view=trend")));
    return;
  }
  if (url.pathname.startsWith("/assets/dashboard/")) {
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
    payload = { title: "새 알림", body: event.data?.text() || "중요한 알림이 도착했습니다." };
  }
  const title = payload.title || "새 알림";
  const options = {
    body: payload.body || "관심종목의 중요한 변화가 있어요.",
    icon: "/assets/dashboard/icons/icon-192.png?v=20260620bq",
    badge: "/assets/dashboard/icons/icon-192.png?v=20260620bq",
    tag: payload.tag || "secret-note-push",
    renotify: true,
    data: { url: payload.url || "/dashboard?view=watchlist", kind: payload.kind || "general" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = new URL(event.notification.data?.url || "/dashboard?view=watchlist", self.location.origin).href;
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
