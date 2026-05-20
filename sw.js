// v4 — Network-first for the app shell (HTML + MANIFEST.json), cache-first
// for everything else (chapter JSON, fonts, CDN libs, icons).
//
// Why: under cache-first-for-everything, iOS Safari (and any browser doing a
// normal reload) would happily serve the stale cached index.html forever — a
// hard-reload was the only way to ever see a new deploy. Network-first for
// the shell means a refresh on any browser always pulls the latest app code
// when online, while still falling back to the cached copy when offline.
//
// Chapter JSON / fonts / React / Tailwind stay cache-first because they're
// effectively immutable: chapter anchors are pinned to the PDF SHA-256, and
// CDN URLs are version-locked. Once cached they should never refetch.
const CACHE = 'beelzebub-v4';

const SHELL = [
  './',
  'index.html',
  'manifest.webmanifest',
  'icon-192.png',
  'icon-512.png',
  'icon-maskable-512.png',
  'apple-touch-icon-180.png',
];

const CDN = [
  'https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&display=swap',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/react@18.2.0/umd/react.production.min.js',
  'https://unpkg.com/react-dom@18.2.0/umd/react-dom.production.min.js',
  'https://unpkg.com/@babel/standalone@7.24.0/babel.min.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await c.addAll(SHELL);
    await Promise.all(CDN.map(async (u) => {
      try {
        const res = await fetch(u, { mode: 'no-cors' });
        await c.put(u, res);
      } catch {}
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// A request is "shell" if it's the page itself (navigation) or one of the
// mutable same-origin documents that can change between deploys. The data
// manifest is included so a future v0.3 with new chapters propagates without
// a manual cache clear.
function isShellRequest(req) {
  if (req.mode === 'navigate') return true;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return false;
  const p = url.pathname;
  return p.endsWith('/') ||
         p.endsWith('/index.html') ||
         p.endsWith('/MANIFEST.json');
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  e.respondWith(isShellRequest(req) ? networkFirst(req) : cacheFirst(req));
});

async function networkFirst(req) {
  try {
    // {cache: 'reload'} skips the browser HTTP cache so we always see the
    // freshest copy from origin (GitHub Pages' default Cache-Control would
    // otherwise let us re-serve a 10-minute-old HTML).
    const res = await fetch(req, { cache: 'reload' });
    if (res && res.ok) {
      const clone = res.clone();
      caches.open(CACHE).then(c => c.put(req, clone)).catch(() => {});
    }
    return res;
  } catch (err) {
    const cached = await caches.match(req);
    if (cached) return cached;
    if (req.mode === 'navigate') {
      const fallback = await caches.match('index.html');
      if (fallback) return fallback;
    }
    throw err;
  }
}

async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res && (res.ok || res.type === 'opaque')) {
      const clone = res.clone();
      caches.open(CACHE).then(c => c.put(req, clone)).catch(() => {});
    }
    return res;
  } catch (err) {
    if (req.mode === 'navigate') {
      const fallback = await caches.match('index.html');
      if (fallback) return fallback;
    }
    throw err;
  }
}
