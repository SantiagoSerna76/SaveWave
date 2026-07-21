const CACHE_NAME = 'savewave-v17';
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
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
    'https://code.jquery.com/jquery-3.7.1.min.js'
];

// ==================== INSTALL ====================
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(ASSETS_TO_CACHE))
    );
    self.skipWaiting();
});

// ==================== ACTIVATE ====================
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME && cacheName !== OFFLINE_AUDIO_CACHE) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// ==================== FETCH ====================
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // ---------- OFFLINE AUDIO CACHE (with Range Request support) ----------
    if (url.pathname.startsWith('/offline-cache/')) {
        event.respondWith(handleOfflineAudio(event.request));
        return;
    }

    // ---------- STREAM / DOWNLOAD audio files ----------
    if (url.pathname.startsWith('/stream/') || url.pathname.startsWith('/stream-native/') || url.pathname.startsWith('/downloads/')) {
        event.respondWith(handleStreamRequest(event.request));
        return;
    }

    // ---------- API Requests ----------
    if (url.pathname.startsWith('/api/')) {
        // API always goes to network
        event.respondWith(fetch(event.request));
        return;
    }

    // ---------- HTML pages: Network first, update cache, fallback to cache ----------
    const isHTML = event.request.headers.get('Accept')?.includes('text/html');
    if (isHTML) {
        event.respondWith(
            fetch(event.request).then(response => {
                if (response && response.status === 200) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            }).catch(() => caches.match(event.request))
        );
        return;
    }

    // ---------- Static assets: network first, cache fallback ----------
    event.respondWith(
        fetch(event.request).then(response => {
            if (response && response.status === 200 && event.request.method === 'GET') {
                const responseClone = response.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, responseClone);
                });
            }
            return response;
        }).catch(() => caches.match(event.request))
    );
});


// ==================== HELPER: Handle offline audio with Range Requests ====================
async function handleOfflineAudio(request) {
    try {
        const cache = await caches.open(OFFLINE_AUDIO_CACHE);
        const cachedResponse = await cache.match(request);

        if (!cachedResponse) {
            return fetch(request);
        }

        const rangeHeader = request.headers.get('Range');
        if (!rangeHeader) {
            return cachedResponse;
        }

        const blob = await cachedResponse.blob();
        const totalSize = blob.size;
        const rangeMatch = rangeHeader.match(/bytes=(\d+)-(\d*)/);

        if (!rangeMatch) {
            return cachedResponse;
        }

        const start = parseInt(rangeMatch[1], 10);
        const end = rangeMatch[2] ? parseInt(rangeMatch[2], 10) : totalSize - 1;
        const chunkSize = end - start + 1;
        const slicedBlob = blob.slice(start, end + 1);

        return new Response(slicedBlob, {
            status: 206,
            statusText: 'Partial Content',
            headers: {
                'Content-Type': cachedResponse.headers.get('Content-Type') || 'audio/mpeg',
                'Content-Length': chunkSize,
                'Content-Range': `bytes ${start}-${end}/${totalSize}`,
                'Accept-Ranges': 'bytes',
            }
        });

    } catch (err) {
        return fetch(request).catch(() => {
            return new Response('Audio not available offline', { status: 404 });
        });
    }
}


// ==================== HELPER: Handle /stream/ requests ====================
async function handleStreamRequest(request) {
    // First check the offline audio cache
    try {
        const cache = await caches.open(OFFLINE_AUDIO_CACHE);
        const keys = await cache.keys();
        
        for (const key of keys) {
            const keyUrl = new URL(key.url);
            if (request.url.includes(keyUrl.searchParams.get('url'))) {
                const cached = await cache.match(key);
                if (cached) return cached;
            }
        }
    } catch(e) { /* ignore */ }

    const staticCached = await caches.match(request);
    if (staticCached) return staticCached;

    return fetch(request);
}
