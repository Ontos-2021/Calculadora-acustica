const VERSION = "acoustic-pwa-v5";
const CACHE_PREFIX = "acoustic-pwa-";
const SHELL_CACHE = `${VERSION}-shell`;
const DATA_CACHE = `${VERSION}-data`;
const CORE_ASSETS = ["/offline-engine.json", "/offline-defaults.json"];
const SHELL_URLS = [
  "/",
  "/results",
  "/results.html",
  "/manifest.json",
  "/icon-192.png",
  "/icon-512.png",
  ...CORE_ASSETS,
];

async function cacheOne(cache, url) {
  try {
    const response = await fetch(url, { cache: "reload" });
    if (!response.ok) return null;
    await cache.put(url, response.clone());
    return response;
  } catch {
    return null;
  }
}

async function precacheShell() {
  const cache = await caches.open(SHELL_CACHE);
  const responses = await Promise.all(SHELL_URLS.map((url) => cacheOne(cache, url)));
  const assetUrls = new Set();
  for (const response of responses) {
    if (!response || !response.headers.get("Content-Type")?.includes("text/html")) continue;
    const html = await response.text();
    const pattern = /(?:src|href)=["']([^"']*\/_next\/static\/[^"']+)["']/g;
    for (const match of html.matchAll(pattern)) {
      try {
        const url = new URL(match[1], self.location.origin);
        if (url.origin === self.location.origin) assetUrls.add(url.pathname);
      } catch {
        // Ignore malformed markup references.
      }
    }
  }
  await Promise.all(Array.from(assetUrls, (url) => cacheOne(cache, url)));
}

self.addEventListener("install", (event) => {
  event.waitUntil(precacheShell().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith(CACHE_PREFIX) && name !== SHELL_CACHE && name !== DATA_CACHE).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data?.type !== "CORE_STATUS" || !event.ports[0]) return;
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    const checks = await Promise.all(CORE_ASSETS.map(async (url) => [url, Boolean(await cache.match(url))]));
    const cached = checks.filter(([, present]) => present).map(([url]) => url);
    const missing = checks.filter(([, present]) => !present).map(([url]) => url);
    event.ports[0].postMessage({ ready: missing.length === 0, cached, missing });
  })());
});

async function networkFirst(request, cacheName = SHELL_CACHE) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;
    throw error;
  }
}

async function navigationFallback(request) {
  try {
    return await networkFirst(request);
  } catch {
    const cache = await caches.open(SHELL_CACHE);
    const url = new URL(request.url);
    if (url.pathname.startsWith("/results")) {
      return (await cache.match("/results", { ignoreSearch: true }))
        || (await cache.match("/results.html", { ignoreSearch: true }))
        || (await cache.match("/"));
    }
    return (await cache.match(url.pathname, { ignoreSearch: true })) || (await cache.match("/"));
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(navigationFallback(request));
    return;
  }

  if (url.pathname.startsWith("/api/")) {
    const anonymousCacheable = !request.headers.has("X-API-Key") && (
      url.pathname.includes("/materials/defaults") || url.pathname.endsWith("/design/targets")
    );
    if (anonymousCacheable) event.respondWith(networkFirst(request, DATA_CACHE));
    return;
  }

  if (url.pathname === "/sw.js") return;
  if (url.pathname.startsWith("/_next/static/") || url.pathname.endsWith(".png") || url.pathname.endsWith(".json")) {
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith(networkFirst(request));
});
