const CACHE_NAME = 'savewave-v13';
const OFFLINE_AUDIO_CACHE = 'savewave-offline';
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

// ==================== INSTALL ====================
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

// ==================== ACTIVATE ====================
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    return caches.delete(cacheName); // DELETE EVERYTHING
                })
            );
        })
    );
    self.clients.claim();
});

// ==================== FETCH ====================
self.addEventListener('fetch', (event) => {
    // ALWAYS go to network to prevent old HTML from being served
    event.respondWith(fetch(event.request).catch(err => console.error(err)));
});
