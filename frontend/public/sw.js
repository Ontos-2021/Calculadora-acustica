const CACHE_NAME = "acoustic-calc-v1";

const PRECACHE_URLS = [
  "/",
  "/results",
  "/manifest.json",
];

const API_CACHE = "api-cache-v1";
const PYODIDE_CACHE = "pyodide-cache-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Pyodide CDN files: cache-first
  if (url.hostname === "cdn.jsdelivr.net" && url.pathname.includes("pyodide")) {
    event.respondWith(
      caches.open(PYODIDE_CACHE).then((cache) =>
        cache.match(event.request).then((cached) => {
          const fetchPromise = fetch(event.request).then((response) => {
            cache.put(event.request, response.clone());
            return response;
          });
          return cached || fetchPromise;
        }),
      ),
    );
    return;
  }

  // API responses: stale-while-revalidate
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      caches.open(API_CACHE).then((cache) =>
        cache.match(event.request).then((cached) => {
          const fetchPromise = fetch(event.request).then((response) => {
            cache.put(event.request, response.clone());
            return response;
          });
          return cached || fetchPromise;
        }),
      ),
    );
    return;
  }

  // Static assets: cache-first
  if (
    url.pathname.startsWith("/_next/") ||
    url.pathname.startsWith("/pyodide/")
  ) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(event.request).then((cached) => {
          const fetchPromise = fetch(event.request).then((response) => {
            cache.put(event.request, response.clone());
            return response;
          });
          return cached || fetchPromise;
        }),
      ),
    );
    return;
  }

  // Pages: network-first
  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match(event.request).then((cached) => cached || caches.match("/")),
    ),
  );
});
