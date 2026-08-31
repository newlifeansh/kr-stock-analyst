const DESKTOP_SW_VERSION = "20260829h4";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: "새 알림", body: event.data?.text() || "중요한 알림이 도착했습니다." };
  }
  const sourceUrl = payload.url || "/dashboard?view=watchlist";
  const targetUrl = `/desktop?view=notifications&notification_url=${encodeURIComponent(sourceUrl)}`;
  event.waitUntil(self.registration.showNotification(payload.title || "새 알림", {
    body: payload.body || "관심종목의 중요한 변화가 있어요.",
    icon: "/assets/dashboard/icons/icon-192.png?v=20260620bq",
    badge: "/assets/dashboard/icons/icon-192.png?v=20260620bq",
    tag: payload.tag || "secret-note-desktop-push",
    renotify: true,
    data: { url: targetUrl, kind: payload.kind || "general" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = new URL(event.notification.data?.url || "/desktop?view=notifications", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        const clientUrl = new URL(client.url);
        if (clientUrl.origin === self.location.origin && clientUrl.pathname.startsWith("/desktop") && "focus" in client) {
          return client.navigate(targetUrl).then(() => client.focus());
        }
      }
      return self.clients.openWindow ? self.clients.openWindow(targetUrl) : undefined;
    })
  );
});
