// OpenWiz's app-shell worker (#1029). It only makes the installed app open:
//
// - It caches only the static shell: the pages `/` and `/setup`, the
//   manifest, and files under /_next/static/, /fonts/ and /icons/, each from
//   this origin, as the server answered them (200, not redirected).
// - It never handles anything else. The API (/api/...) and every request that
//   is not a GET pass straight to the network, so an answer about your
//   sessions is never stored or served from a cache, and a send, create,
//   upload or removal is never stored, queued, retried or replayed: offline,
//   it fails at once, as it would without a worker.
// - Pages come from the network first; the cached copy only when the network
//   fails, so the app can open and say it is offline. Hashed assets, fonts and
//   icons come from the cache first.
// - On install it stores `/` and the shell files that page names, so the
//   installed app opens offline from its first visit.

const CACHE = 'openwiz-shell-v1';
const PAGES = ['/', '/setup'];
const ASSETS = /^\/(_next\/static|fonts|icons)\/[A-Za-z0-9._/-]+$/;

const isShell = (url) =>
  url.origin === self.location.origin &&
  url.search === '' &&
  (PAGES.includes(url.pathname) || url.pathname === '/manifest.webmanifest' || ASSETS.test(url.pathname));

// Stores a good answer for offline use, then returns it. Storing is best
// effort: if the cache can't be written (storage full or unavailable), the
// network's answer is still served, never an older copy or a failure.
async function keep(request, response) {
  if (response.ok && response.status === 200 && !response.redirected && response.type === 'basic') {
    try {
      const cache = await caches.open(CACHE);
      await cache.put(request, response.clone());
    } catch {
      // Not stored; served anyway.
    }
  }
  return response;
}

// The stored copy, or undefined. A failed read (storage unavailable) is a
// miss, so the network is still asked.
async function stored(request) {
  try {
    return await caches.match(request, { cacheName: CACHE });
  } catch {
    return undefined;
  }
}

async function networkFirst(request) {
  try {
    return await keep(request, await fetch(request));
  } catch (error) {
    const cached = await stored(request);
    if (cached) return cached;
    throw error;
  }
}

async function cacheFirst(request) {
  const cached = await stored(request);
  return cached ?? keep(request, await fetch(request));
}

// The shell files a page names: same-origin paths under /_next/static/, /fonts/ and /icons/.
const NAMED = /(?:src|href)="(\/(?:_next\/static|fonts|icons)\/[A-Za-z0-9._/-]+)"/g;

async function install() {
  const cache = await caches.open(CACHE);
  const page = await fetch('/', { cache: 'no-store' });
  if (page.status !== 200) throw new Error('the page did not load');
  const named = new Set([...(await page.clone().text()).matchAll(NAMED)].map((m) => m[1]));
  await cache.addAll([...named, '/manifest.webmanifest']);
  await cache.put('/', page);
}

self.addEventListener('install', (event) => {
  event.waitUntil(install().then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (!isShell(url)) return;
  const page = PAGES.includes(url.pathname) || url.pathname === '/manifest.webmanifest';
  event.respondWith(page ? networkFirst(request) : cacheFirst(request));
});
