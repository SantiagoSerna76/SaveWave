const CACHE_NAME = 'savewave-v11';
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
                    // Keep the offline audio cache and the current static cache
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
    // This handles audio files that were downloaded via "Descargar Todo"
    if (url.pathname.startsWith('/offline-cache/')) {
        event.respondWith(handleOfflineAudio(event.request));
        return;
    }

    // ---------- STREAM / DOWNLOAD / STREAM-NATIVE audio files ----------
    // For /stream/, /stream-native/ and /downloads/ paths, check offline cache first, then network
    if (url.pathname.startsWith('/stream/') || url.pathname.startsWith('/stream-native/') || url.pathname.startsWith('/downloads/')) {
        event.respondWith(
            handleStreamRequest(event.request)
        );
        return;
    }

    // ---------- API Requests ----------
    if (url.pathname.startsWith('/api/')) {
        if (event.request.method === 'GET') {
            // Network-first for GET API calls
            event.respondWith(
                fetch(event.request).then(response => {
                    if (response && response.status === 200) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseClone));
                    }
                    return response;
                }).catch(() => caches.match(event.request))
            );
        } else {
            // POST/PUT/DELETE go to network only
            event.respondWith(fetch(event.request));
        }
        return;
    }

    // ---------- Static files only (Network-first, but DON'T cache HTML pages) ----------
    // HTML pages always go to network to ensure latest version
    const isHTML = event.request.headers.get('Accept')?.includes('text/html');
    if (isHTML) {
        event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
        return;
    }

    // Static files (CSS, JS, images, etc.) - network first with cache fallback
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
// This is THE KEY fix for stuttering in the PWA.
// HTML5 <audio> elements send Range requests (e.g., "Range: bytes=0-65535")
// to seek and stream. If we just return the full cached blob, the browser
// can't seek properly, causing stuttering and failed playback on iOS/Safari.
async function handleOfflineAudio(request) {
    try {
        const cache = await caches.open(OFFLINE_AUDIO_CACHE);
        const cachedResponse = await cache.match(request);

        if (!cachedResponse) {
            // Not in cache — try network
            return fetch(request);
        }

        // Check if this is a Range request
        const rangeHeader = request.headers.get('Range');
        if (!rangeHeader) {
            // No Range header — return the full cached response
            return cachedResponse;
        }

        // Parse Range header (e.g., "bytes=12345-" or "bytes=0-65535")
        const blob = await cachedResponse.blob();
        const totalSize = blob.size;
        const rangeMatch = rangeHeader.match(/bytes=(\d+)-(\d*)/);

        if (!rangeMatch) {
            return cachedResponse;
        }

        const start = parseInt(rangeMatch[1], 10);
        const end = rangeMatch[2] ? parseInt(rangeMatch[2], 10) : totalSize - 1;
        const chunkSize = end - start + 1;

        // Slice the blob to return only the requested range
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
        // If anything fails, try network
        return fetch(request).catch(() => {
            return new Response('Audio not available offline', { status: 404 });
        });
    }
}


// ==================== HELPER: Handle /stream/ and /downloads/ requests ====================
async function handleStreamRequest(request) {
    // First check the offline audio cache
    try {
        const cache = await caches.open(OFFLINE_AUDIO_CACHE);
        const keys = await cache.keys();
        
        // Try to find a matching cached audio by filename
        for (const key of keys) {
            const keyUrl = new URL(key.url);
            if (request.url.includes(keyUrl.searchParams.get('url'))) {
                const cached = await cache.match(key);
                if (cached) return cached;
            }
        }
    } catch(e) { /* ignore */ }

    // Check static cache
    const staticCached = await caches.match(request);
    if (staticCached) return staticCached;

    // Fallback to network
    return fetch(request);
}
