/*
 * The service worker that makes the site installable and gives it an offline
 * page.
 *
 * It is deliberately narrow, because a worker sits in front of every request
 * the site makes and outlives the page that installed it:
 *
 *  - The API is never touched. Not cached, not even proxied: a request this
 *    file does not answer goes to the network exactly as if there were no
 *    worker. A subscription link or a session answer sitting in a cache is
 *    something that survives sign-out.
 *  - Pages are never cached either. A navigation goes to the network, and only
 *    when there is no network at all does the offline page answer instead.
 *  - Scripts and the stylesheet are network-first. They change on every deploy
 *    under the same name and must move with the markup (see cachePolicyFor in
 *    internal/static); serving them from a cache while online is how a
 *    returning visitor runs last week's code against today's page. The cached
 *    copy only exists so the offline page can render.
 *  - Fonts and images are cache-first: the server already calls them
 *    immutable, and a new file ships under a new name.
 *
 * Bump VERSION when the precache list changes; old caches are dropped on
 * activation.
 */

const VERSION = "v1";
const CACHE = `kaira-${VERSION}`;
const OFFLINE = "/offline";

const PRECACHE = [
  OFFLINE,
  "/assets/css/app.css",
  "/assets/js/core.js",
  "/assets/js/footer.js",
  "/assets/js/pwa.js",
  "/assets/fonts/inter-cyrillic.woff2",
  "/assets/fonts/inter-latin.woff2",
  "/assets/img/favicon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE.map((url) => new Request(url, { cache: "reload" }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((name) => name !== CACHE).map((name) => caches.delete(name))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => offlinePage()));
    return;
  }

  // The video is excluded: it is large, arrives in byte ranges, and is
  // decoration the offline page does not have.
  if (url.pathname.startsWith("/assets/fonts/") || url.pathname.startsWith("/assets/img/")) {
    event.respondWith(cacheFirst(request));
    return;
  }
  if (url.pathname.startsWith("/assets/css/") || url.pathname.startsWith("/assets/js/")) {
    event.respondWith(networkFirst(request));
  }
});

async function offlinePage() {
  const cached = await caches.match(OFFLINE);
  return cached || new Response("Нет связи с сервером.", {
    status: 503,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && response.type === "basic") {
    const copy = response.clone();
    caches.open(CACHE).then((cache) => cache.put(request, copy));
  }
  return response;
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok && response.type === "basic") {
      const copy = response.clone();
      caches.open(CACHE).then((cache) => cache.put(request, copy));
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw error;
  }
}
