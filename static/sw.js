const CACHE_NAME = 'savewave-v3';
const ASSETS_TO_CACHE = [
    '/',
    '/static/style.css',
    '/static/script.js',
    '/static/Savewave.png',
    '/static/icon-192.png',
    '/static/icon-512.png'
];

// Install Service Worker and cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                return cache.addAll(ASSETS_TO_CACHE);
            })
    );
    self.skipWaiting();
});

// Activate the SW and clean old caches (but preserve offline audio cache)
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    // Keep the offline audio cache and the current static cache
                    if (cacheName !== CACHE_NAME && cacheName !== 'savewave-offline') {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Intercept requests
self.addEventListener('fetch', (event) => {
    // If the request is for the API, always go to network
    if (event.request.url.includes('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // For downloaded audio files, try cache first (offline playback), then network
    if (event.request.url.includes('/downloads/')) {
        event.respondWith(
            caches.match(event.request).then(cached => {
                return cached || fetch(event.request);
            })
        );
        return;
    }

    // For the rest (static files, html pages), try network first, then cache
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
