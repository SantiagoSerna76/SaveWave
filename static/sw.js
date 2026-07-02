const CACHE_NAME = 'savewave-v6';
const ASSETS_TO_CACHE = [
    '/',
    '/playlists',
    '/manifest.json',
    '/static/style.css',
    '/static/script.js',
    '/static/Savewave.png',
    '/static/icon-192.png',
    '/static/icon-512.png',
    // CDN dependencies (critical for offline rendering)
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
    'https://code.jquery.com/jquery-3.7.1.min.js'
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
    // API Requests
    if (event.request.url.includes('/api/')) {
        // Cache GET requests (like playlist data) using Network-First
        if (event.request.method === 'GET') {
            event.respondWith(
                fetch(event.request).then(response => {
                    if (response && response.status === 200) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseClone));
                    }
                    return response;
                }).catch(() => {
                    // Offline fallback
                    return caches.match(event.request);
                })
            );
        } else {
            // POST/PUT/DELETE (like creating playlists, downloading) go to network only
            event.respondWith(fetch(event.request));
        }
        return;
    }

    // For downloaded audio files, try cache first (offline playback), then network
    if (event.request.url.includes('/downloads/') || event.request.url.includes('/stream/')) {
        event.respondWith(
            caches.match(event.request).then(cached => {
                return cached || fetch(event.request);
            })
        );
        return;
    }

    // For the rest (static files, html pages), try network first, then fallback to cache
    event.respondWith(
        fetch(event.request).then(response => {
            if (response && response.status === 200 && event.request.method === 'GET') {
                const responseClone = response.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, responseClone);
                });
            }
            return response;
        }).catch(() => {
            return caches.match(event.request);
        })
    );
});
