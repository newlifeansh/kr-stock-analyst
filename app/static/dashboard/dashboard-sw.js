const DASHBOARD_SW_VERSION = "20260722kr23";
const STATIC_CACHE = `secret-note-static-${DASHBOARD_SW_VERSION}`;
const STATIC_ASSETS = [
  "/dashboard?view=trend",
  "/assets/dashboard/styles.css?v=20260722kr20",
  "/assets/dashboard/app.js?v=20260722kr23",
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
