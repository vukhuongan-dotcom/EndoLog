/* EndoLog Service Worker v0.2.3 — Zero-PHI Cache Allowlist (NetworkOnly for all /api/*) */
const CACHE_NAME = 'endolog-static-v0.2.3';
const STATIC_ALLOWLIST = [
  '/',
  '/index.html',
  '/manifest.json',
  '/css/fonts.css?v=0.2.3',
  '/css/tokens.css?v=0.2.3',
  '/css/app.css?v=0.2.3',
  '/js/app.js?v=0.2.3',
  '/icons/favicon.svg',
  '/fonts/noto-sans-latin-var.woff2',
  '/fonts/noto-sans-vietnamese-var.woff2',
  '/fonts/plus-jakarta-sans-latin-var.woff2',
  '/fonts/plus-jakarta-sans-vietnamese-var.woff2',
  '/fonts/jetbrains-mono-latin-var.woff2',
  '/fonts/jetbrains-mono-vietnamese-var.woff2'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ALLOWLIST)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/')) {
    /* Strict Zero-PHI NetworkOnly: do not intercept or proxy /api/* through Service Worker or Cache Storage */
    return;
  }
  if (event.request.method !== 'GET') {
    return;
  }
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
