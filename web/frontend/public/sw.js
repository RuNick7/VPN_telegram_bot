/* KairaVPN Service Worker
 *
 * Назначение:
 *   1. Получать web-push (VAPID) и показывать notifications.
 *   2. Минимальный offline-fallback на корневой URL — НИКАКОГО кэша /api/*.
 *
 * Стратегия кэша:
 *   - precache: только заранее известные статические ассеты (manifest, favicon).
 *   - runtime:  только GET-запросы к /_next/static/* и /icons/* — stale-while-revalidate.
 *   - fetch к /api/* и любым POST/PUT/PATCH/DELETE всегда уходит в сеть, минуя SW.
 */

const SW_VERSION = "v1";
const STATIC_CACHE = `kaira-static-${SW_VERSION}`;
const RUNTIME_CACHE = `kaira-runtime-${SW_VERSION}`;
const PRECACHE_URLS = [
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-maskable-512.png",
  "/icons/badge-72.png",
  "/apple-touch-icon.png",
  "/favicon.ico",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE_URLS).catch(() => undefined)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== RUNTIME_CACHE)
          .map((key) => caches.delete(key)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  if (request.method !== "GET") return;

  let url;
  try {
    url = new URL(request.url);
  } catch {
    return;
  }

  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  const isAsset =
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname === "/manifest.webmanifest" ||
    url.pathname === "/favicon.ico" ||
    url.pathname === "/apple-touch-icon.png";

  if (!isAsset) return;

  event.respondWith(
    caches.open(RUNTIME_CACHE).then(async (cache) => {
      const cached = await cache.match(request);
      const networkPromise = fetch(request)
        .then((response) => {
          if (response && response.ok) {
            cache.put(request, response.clone()).catch(() => undefined);
          }
          return response;
        })
        .catch(() => cached || Response.error());
      return cached || networkPromise;
    }),
  );
});

self.addEventListener("push", (event) => {
  let payload = {};
  if (event.data) {
    try {
      payload = event.data.json();
    } catch {
      payload = { title: "KairaVPN", body: event.data.text() };
    }
  }

  const title = payload.title || "KairaVPN";
  const options = {
    body: payload.body || "",
    icon: payload.icon || "/icons/icon-192.png",
    badge: payload.badge || "/icons/badge-72.png",
    tag: payload.tag || "kaira-default",
    renotify: Boolean(payload.renotify),
    requireInteraction: Boolean(payload.require_interaction),
    data: {
      url: payload.url || "/cabinet",
      ...(payload.data || {}),
    },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/cabinet";
  event.waitUntil(
    (async () => {
      const allClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of allClients) {
        if (client.url.endsWith(targetUrl) && "focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
      return undefined;
    })(),
  );
});

self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    (async () => {
      try {
        const old = event.oldSubscription;
        const newSub = await self.registration.pushManager.subscribe(
          old ? old.options : { userVisibleOnly: true },
        );
        await fetch("/api/push/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Requested-With": "fetch" },
          credentials: "include",
          body: JSON.stringify({
            endpoint: newSub.endpoint,
            keys: newSub.toJSON().keys,
          }),
        });
      } catch {
        // нет валидной сессии или подписка отозвана — будем пере-подписываться при следующем визите
      }
    })(),
  );
});
