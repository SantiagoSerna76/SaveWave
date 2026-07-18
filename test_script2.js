
    function showToast(message) {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.style.cssText = `
            background: rgba(20, 20, 35, 0.95);
            backdrop-filter: blur(10px);
            color: #fff;
            padding: 12px 20px;
            border-radius: 12px;
            font-size: 0.9rem;
            font-weight: 500;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            pointer-events: auto;
        `;
        toast.textContent = message;
        container.appendChild(toast);
        
        // Trigger reflow for animation
        toast.offsetHeight;
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-20px)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ========== DETECTAR APP NATIVA ==========
    const isNativeApp = () => {
        return window.location.search.includes('native=1') || 
               (typeof Capacitor !== 'undefined' && Capacitor.isNativePlatform());
    };

    // ========== STATE ==========
    let currentPlaylistId = null;
    let currentPlaylistItems = [];
    let currentTrackIndex = -1;
    let isPlaying = false;
    let isShuffled = false;
    // repeatMode: 0 = off, 1 = repeat all, 2 = repeat one
    let repeatMode = 0;
    let shuffleOrder = [];
    let shuffleIndex = -1;
    let currentFetchController = null;

    const audioPlayer = document.getElementById('audioPlayer');
    const playPauseBtn = document.getElementById('playPauseBtn');

    // ========== MOBILE SIDEBAR TOGGLE ==========
    function toggleSidebar() {
        const sidebar = document.getElementById('playlistSidebar');
        const overlay = document.getElementById('sidebarOverlay');
        sidebar.classList.toggle('show');
        overlay.classList.toggle('show');
    }

    function closeSidebarOnMobile() {
        if (window.innerWidth <= 768) {
            const sidebar = document.getElementById('playlistSidebar');
            const overlay = document.getElementById('sidebarOverlay');
            sidebar.classList.remove('show');
            overlay.classList.remove('show');
        }
    }

    // ========== LOAD PLAYLIST ==========
    async function loadPlaylist(id, evt) {
        document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active'));
        if (evt && evt.currentTarget) evt.currentTarget.classList.add('active');
        currentPlaylistId = id;

        try {
            const res = await fetch(`/api/playlists/${id}`);
            const data = await res.json();

            if (data.success) {
                renderPlaylist(data.playlist);
                currentPlaylistItems = data.playlist.items;
                generateShuffleOrder();
                closeSidebarOnMobile();
            } else {
                showOfflineMessage('No se pudo cargar la playlist. ' + (data.error || ''));
            }
        } catch (e) {
            console.error(e);
            // Show friendly offline message instead of alert
            const main = document.getElementById('playlistMain');
            main.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon" style="background: rgba(239,68,68,0.1);">
                        <i class="fas fa-wifi" style="color: #ef4444;"></i>
                    </div>
                    <h2>Sin conexión</h2>
                    <p>No se puede cargar esta playlist porque no hay conexión a internet. Abre la app cuando tengas conexión para que se guarden los datos, luego podrás usarla offline.</p>
                    <button class="btn-action mt-3" onclick="loadPlaylist(${id})">
                        <i class="fas fa-redo"></i> Reintentar
                    </button>
                </div>
            `;
        }
    }

    // ========== RENDER PLAYLIST ==========
    function renderPlaylist(playlist) {
        const main = document.getElementById('playlistMain');
        const coverContent = playlist.items.length > 0 && playlist.items[0].thumbnail
            ? `<img src="${playlist.items[0].thumbnail}" alt="Cover">`
            : `<i class="fas fa-music"></i>`;

        let rows = '';
        if (playlist.items.length === 0) {
            rows = `<tr><td colspan="4" class="text-center py-5">
                <div class="text-muted">
                    <i class="fas fa-plus-circle fa-2x mb-3 d-block" style="opacity:0.3;"></i>
                    <p class="mb-1 fw-semibold">Esta playlist está vacía</p>
                    <p class="small">Descarga un video desde la página principal y guárdalo aquí.</p>
                </div>
            </td></tr>`;
        } else {
            playlist.items.forEach((item, index) => {
                const safeUrl = encodeURIComponent(item.url);
                const safeThumb = encodeURIComponent(item.thumbnail || '');
                const safeTitle = item.title.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                const platformLabel = item.platform === 'audio_local' ? 'Archivo local' : item.platform === 'video_local' ? 'Video local' : item.platform;
                rows += `
                    <tr class="track-row" ondblclick="playTrack(${index})" onclick="handleTrackTap(event, ${index}, ${playlist.id}, ${item.id}, '${safeUrl}', '${safeThumb}', '${safeTitle}')" id="trackRow${index}">
                        <td class="track-number">${index + 1}</td>
                        <td style="width:100%;">
                            <div style="display:flex; align-items:center; gap:12px; min-width:0;">
                                <img src="${item.thumbnail || ''}" class="track-thumb" alt="">
                                <div style="min-width:0; flex:1;">
                                    <div style="display:flex; align-items:center; gap:6px; min-width:0; width:100%;">
                                        <span class="track-title" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; flex:1; min-width:0; color:var(--text-color); font-weight:500; font-size:0.95rem;">${item.title}</span>
                                        <span class="offline-badge d-none" id="offlineBadge${index}" style="flex-shrink:0;"><i class="fas fa-check-circle"></i> Offline</span>
                                    </div>
                                    <div class="text-muted" style="font-size: 0.8rem;">${platformLabel}</div>
                                </div>
                            </div>
                        </td>
                        <td class="text-end text-muted col-duration" style="font-size: 0.85rem; white-space:nowrap;">${item.duration_formatted || '—'}</td>
                        <td class="text-end" style="white-space:nowrap; padding-right:8px;">
                            <div class="track-actions" style="display:flex; align-items:center; justify-content:flex-end;">
                                <button class="track-action-btn btn-play-track" title="Reproducir" onclick="playTrack(${index})"><i class="fas fa-play"></i></button>
                                <button class="track-action-btn btn-download-track" title="Descargar MP3" onclick="downloadTrack(decodeURIComponent('${safeUrl}'))"><i class="fas fa-download"></i></button>
                                <button class="track-action-btn btn-add-track" title="Agregar a otra playlist" onclick="openAddToPlaylistModal(${index})"><i class="fas fa-plus-circle"></i></button>
                                <button class="track-action-btn btn-delete-track" style="color:rgba(239,68,68,0.7);" title="Eliminar" onclick="removeTrack(${playlist.id}, ${item.id}, '${safeUrl}')"><i class="fas fa-trash"></i></button>
                            </div>
                            <button class="btn-three-dots" style="display:none;" title="Opciones"
                                onclick="openTrackSheet(${index}, ${playlist.id}, ${item.id}, '${safeUrl}', '${safeThumb}', '${safeTitle}')"
                            ><i class="fas fa-ellipsis-v"></i></button>
                        </td>
                    </tr>
                `;
            });
        }

        main.innerHTML = `
            <div class="pl-header">
                <div class="pl-cover">${coverContent}</div>
                <div class="pl-meta">
                    <div class="sidebar-label mb-1">PLAYLIST</div>
                    <h1 id="playlistName">${playlist.name}</h1>
                    <div class="pl-stats">
                        <span>${playlist.items.length} ${playlist.items.length === 1 ? 'canción' : 'canciones'}</span>
                    </div>
                </div>
            </div>

            <div class="pl-controls">
                <button class="btn-play-main" onclick="playTrack(0)" title="Reproducir todo">
                    <i class="fas fa-play" style="margin-left: 3px;"></i>
                </button>
                <button class="btn-action" onclick="showDownloadOptions(${playlist.id})">
                    <i class="fas fa-download"></i> Descargar Todo
                </button>
                <button class="btn-action ms-2" onclick="document.getElementById('uploadFileInput').click()">
                    <i class="fas fa-upload"></i> Subir MP3/MP4
                </button>
                <button class="btn-action btn-danger ms-auto" onclick="deletePlaylist(${playlist.id})">
                    <i class="fas fa-trash"></i> <span class="d-none d-sm-inline">Eliminar</span>
                </button>
                <input type="file" id="uploadFileInput" class="d-none" accept=".mp3,.mp4,.wav,.m4a,.aac,.ogg,.webm" onchange="uploadLocalFile(${playlist.id})">
            </div>

            {% if ads_enabled %}
            <div class="mt-4 mb-4 text-center">
                <div style="font-size: 0.6rem; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 6px;">Anuncio</div>
                <div class="sw-ad-slot mx-auto" style="width:100%;max-width:320px;height:50px;border-radius:12px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.2);"></div>
            </div>
            {% endif %}

            ${playlist.items.length > 0 ? `
            <div class="info-note" style="background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.2); border-radius: 12px; padding: 14px 18px; color: rgba(255,255,255,0.7); font-size: 0.85rem; margin-bottom: 24px; display: flex; align-items: flex-start; gap: 12px;">
                <i class="fas fa-info-circle" style="color: #6366f1; font-size: 1.1rem; flex-shrink: 0; margin-top: 1px;"></i>
                <div>
                    <strong style="color: #a5b4fc;">Nota sobre la reproducción:</strong> La primera vez que reproduces una canción desde un link externo (como YouTube), puede tardar un momento mientras nuestro servidor procesa el audio. 
                    Para escuchar sin retrasos, usa <strong style="color: #a5b4fc;">Descargar Todo</strong> primero. 
                    <strong style="color: #a5b4fc;">Descarga nuestra App</strong> para escuchar música sin conexión desde tu celular.
                </div>
            </div>
            ` : ''}

            <table class="tracklist">
                <thead>
                    <tr>
                        <th class="track-number">#</th>
                        <th>Título</th>
                        <th class="text-end"><i class="far fa-clock"></i></th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;

        // Re-highlight if a track is already playing
        highlightCurrentTrack();
        // Check which tracks are available offline
        checkOfflineStatus();
    }

    // ========== CREATE PLAYLIST ==========
    async function createPlaylist() {
        const nameInput = document.getElementById('newPlaylistName');
        const descInput = document.getElementById('newPlaylistDesc');
        const btn = document.getElementById('createPlaylistBtn');
        const name = nameInput.value.trim();

        if (!name) {
            nameInput.style.borderColor = '#ef4444';
            nameInput.focus();
            return;
        }

        btn.disabled = true;
        btn.textContent = 'Creando...';

        try {
            const res = await fetch('/api/playlists/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: name,
                    description: descInput ? descInput.value.trim() : ''
                })
            });
            const data = await res.json();

            if (data.success) {
                location.reload();
            } else {
                showToast(data.error || 'Error al crear la playlist.');
                btn.disabled = false;
                btn.textContent = 'Crear Playlist';
            }
        } catch(e) {
            showToast('Error de conexión. Inténtalo de nuevo.');
            btn.disabled = false;
            btn.textContent = 'Crear Playlist';
        }
    }

    document.getElementById('newPlaylistName').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') createPlaylist();
        this.style.borderColor = '';
    });

    // ========== AUDIO PLAYER ==========

    function highlightCurrentTrack() {
        document.querySelectorAll('.track-row').forEach((row, i) => {
            row.classList.toggle('playing', i === currentTrackIndex);
        });
    }

    function setupMediaSession(track) {
        if ('mediaSession' in navigator) {
            const plNameEl = document.getElementById('playlistName');
            const playlistTitle = plNameEl ? plNameEl.textContent : 'SaveWave';
            
            navigator.mediaSession.metadata = new MediaMetadata({
                title: track.title,
                artist: track.platform === 'audio_local' ? 'Archivo local' : track.platform,
                album: playlistTitle,
                artwork: [
                    { src: track.thumbnail || '/static/Savewave.png', sizes: '512x512', type: 'image/png' }
                ]
            });

            navigator.mediaSession.setActionHandler('play', function() {
                audioPlayer.play();
                isPlaying = true;
                updatePlayPauseUI();
            });
            navigator.mediaSession.setActionHandler('pause', function() {
                audioPlayer.pause();
                isPlaying = false;
                updatePlayPauseUI();
            });
            navigator.mediaSession.setActionHandler('previoustrack', function() {
                playPrev();
            });
            navigator.mediaSession.setActionHandler('nexttrack', function() {
                playNext();
            });
        }
    }

    async function preloadNextTrack() {
        const nextIndex = getNextIndex();
        if (nextIndex === -1) return;
        const track = currentPlaylistItems[nextIndex];
        
        // No hacer preload si es local o ya está cacheada offline
        if (track.platform === 'audio_local' || track.platform === 'video_local' || track.cached_url) return;
        
        if (!window.preloadPromises) window.preloadPromises = {};
        if (window.preloadPromises[track.url]) return;

        // Disparar la conexión con el VPS en background silenciosamente
        window.preloadPromises[track.url] = fetch('/api/stream-proxy', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'url=' + encodeURIComponent(track.url)
        }).then(r => {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        }).catch(err => {
            // Si falla el preload en background, borrar la promesa para que reintente en vivo
            delete window.preloadPromises[track.url];
        });
    }

    async function playTrack(index) {
        // Helper to safely set text/html on an element
        const safeText = (el, txt) => { if (el) el.textContent = txt; };
        const safeHtml = (el, html) => { if (el) el.innerHTML = html; };

        try {
            // Force player to be visible
            const stickyPlayer = document.getElementById('stickyPlayer');
            if (stickyPlayer) {
                stickyPlayer.style.display = 'flex';
                stickyPlayer.style.opacity = '1';
                stickyPlayer.style.visibility = 'visible';
                stickyPlayer.style.zIndex = '999999';
            }

            // Unlock audio context synchronously for mobile auto-play policy
            if (audioPlayer) {
                audioPlayer.play().catch(e => { console.warn("Unlock play rejected:", e); });
            }
            
            // Auto-expand the Spotify-like full player on mobile
            if (window.innerWidth <= 768) {
                expandPlayer();
            }

            const statusEl = document.getElementById('playerTitle');
            
            if (index < 0 || index >= currentPlaylistItems.length) {
                safeText(statusEl, '⚠ Índice de pista inválido');
                return;
            }

            if (currentTrackIndex === index && audioPlayer.src && !audioPlayer.paused) {
                audioPlayer.pause();
                isPlaying = false;
                updatePlayPauseUI();
                return;
            }

            if (currentFetchController) {
                currentFetchController.abort();
                currentFetchController = null;
            }

            currentTrackIndex = index;
            const track = currentPlaylistItems[index];

            const platformLabel = track.platform === 'audio_local' ? 'Archivo local' : track.platform === 'video_local' ? 'Video local' : track.platform;
            
            const artistEl = document.getElementById('playerArtist');
            safeText(artistEl, platformLabel);
            
            const coverEl = document.getElementById('playerCover');
            if (coverEl) {
                if (track.thumbnail) {
                    coverEl.src = track.thumbnail;
                    coverEl.classList.remove('d-none');
                } else {
                    coverEl.classList.add('d-none');
                }
            }
            highlightCurrentTrack();
            setupMediaSession(track);

            isPlaying = false;
            updatePlayPauseUI();
            safeHtml(statusEl, '⏳ Paso 1: Preparando...');

            const progBar = document.getElementById('progressBar');
            if (progBar) progBar.style.width = '0%';
            
            const tc = document.getElementById('timeCurrent');
            safeText(tc, '0:00');
            
            const tt = document.getElementById('timeTotal');
            safeText(tt, '0:00');

            try {
                if ('caches' in window) {
                    const offlineCache = await caches.open(OFFLINE_CACHE_NAME);
                    const cacheKey = '/offline-cache/?url=' + encodeURIComponent(track.url);
                    const cachedRes = await offlineCache.match(cacheKey);
                    if (cachedRes) {
                        safeText(statusEl, '⏳ Cargando offline...');
                        audioPlayer.src = cacheKey;
                        audioPlayer.load();
                        try {
                            await audioPlayer.play();
                            isPlaying = true;
                            safeText(statusEl, track.title);
                            updatePlayPauseUI();
                            setTimeout(preloadNextTrack, 1000);
                            return;
                        } catch(err) {
                            console.warn('Caché offline corrupto detectado, eliminando y usando red...', err);
                            await offlineCache.delete(cacheKey);
                        }
                    }
                }
            } catch(e) { }

            if (track.platform === 'audio_local' || track.platform === 'video_local' || track.cached_url) {
                const localSrc = track.cached_url || track.url;
                safeText(statusEl, '⏳ Cargando archivo local...');
                audioPlayer.src = localSrc;
                audioPlayer.load();
                try {
                    await audioPlayer.play();
                    isPlaying = true;
                    safeText(statusEl, track.title);
                    setTimeout(preloadNextTrack, 1000);
                } catch(err) {
                    safeText(statusEl, '❌ Error reproduciendo archivo: ' + err.message);
                }
                updatePlayPauseUI();
                return;
            }

            safeHtml(statusEl, '⏳ Conectando con el servidor...');
            currentFetchController = new AbortController();
            
            try {
                // Usar promesa cacheadas si hay un preload activo
                if (!window.preloadPromises) window.preloadPromises = {};
                
                let dataPromise = window.preloadPromises[track.url];
                if (!dataPromise) {
                    dataPromise = fetch('/api/stream-proxy', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: 'url=' + encodeURIComponent(track.url),
                        signal: currentFetchController.signal
                    }).then(r => {
                        if (!r.ok) throw new Error('HTTP ' + r.status);
                        return r.json();
                    });
                    window.preloadPromises[track.url] = dataPromise;
                }
                
                const data = await dataPromise;
                currentFetchController = null;
                
                if (currentTrackIndex !== index) return;

                if (!data.success) {
                    safeText(statusEl, '❌ ' + (data.error || 'Sin respuesta del servidor'));
                    updatePlayPauseUI();
                    return;
                }

                safeHtml(statusEl, '⏳ Paso 3: Cargando audio...');
                
                // Intentar con la URL directa de YouTube primero (más rápido, el móvil descarga directo)
                // Si falla por CORS, usar el proxy como respaldo
                const tryPlay = async (url) => {
                    return new Promise((resolve, reject) => {
                        const audio = new Audio();
                        audio.preload = 'auto';
                        
                        audio.oncanplay = () => {
                            audioPlayer.src = url;
                            audioPlayer.load();
                            resolve();
                            setTimeout(preloadNextTrack, 1000);
                        };
                        audio.onerror = () => {
                            reject(new Error('CORS or load error'));
                        };
                        audio.src = url;
                        audio.load();
                        
                        // Timeout de 3 segundos para la carga directa
                        setTimeout(() => {
                            if (!audio.readyState || audio.readyState < 2) {
                                audio.src = '';
                                reject(new Error('Timeout'));
                            }
                        }, 3000);
                    });
                };

                try {
                    // Primero intentar con la URL directa de YouTube
                    await tryPlay(data.direct_url);
                    track.cached_url = data.direct_url;
                    safeHtml(statusEl, '⏳ Reproduciendo (directo desde YouTube)...');
                } catch (directErr) {
                    // Fallback al proxy si CORS bloquea
                    safeHtml(statusEl, '⏳ Usando proxy de streaming...');
                    track.cached_url = data.proxy_url;
                    audioPlayer.src = data.proxy_url;
                    audioPlayer.load();
                }
                
                safeHtml(statusEl, '⏳ Paso 4: Reproduciendo...');
                
                try {
                    await audioPlayer.play();
                    isPlaying = true;
                    safeText(statusEl, '🎵 ' + track.title);
                } catch(playErr) {
                    safeText(statusEl, '❌ Play falló: ' + playErr.message);
                }
            } catch(e) {
                if (e.name !== 'AbortError') {
                    safeText(statusEl, '❌ Error: ' + e.message);
                }
                currentFetchController = null;
            }
            
            if (currentTrackIndex === index) {
                updatePlayPauseUI();
            }

        } catch (fatalErr) {
            console.error("FATAL ERROR IN playTrack:", fatalErr);
            alert("Error fatal en el reproductor: " + fatalErr.message);
        }
    }

    // ========== PLAY / PAUSE ==========
    function togglePlay() {
        if (currentTrackIndex === -1 && currentPlaylistItems.length > 0) {
            playTrack(0);
            return;
        }

        if (currentFetchController !== null) return;

        if (!audioPlayer.src || audioPlayer.error || audioPlayer.readyState < 1) {
            playTrack(currentTrackIndex);
            return;
        }

        if (audioPlayer.paused) {
            audioPlayer.play().then(() => {
                isPlaying = true;
                updatePlayPauseUI();
            }).catch((err) => {
                console.error("Play error:", err);
                const pt = document.getElementById('playerTitle');
                if (pt) pt.innerHTML = '<span style="color:#f87171;"><i class="fas fa-exclamation-triangle me-1"></i>Error al reproducir el archivo</span>';
            });
        } else {
            audioPlayer.pause();
            isPlaying = false;
            updatePlayPauseUI();
        }
    }

    function updatePlayPauseUI() {
        if (playPauseBtn) {
            playPauseBtn.innerHTML = isPlaying
                ? '<i class="fas fa-pause"></i>'
                : '<i class="fas fa-play" style="margin-left:2px;"></i>';
        }
        const mobileBtn = document.getElementById('mobilePlayBtn');
        if (mobileBtn) {
            mobileBtn.innerHTML = isPlaying
                ? '<i class="fas fa-pause"></i>'
                : '<i class="fas fa-play"></i>';
        }
    }

    // ========== MOBILE FULLSCREEN PLAYER ==========
    function expandPlayer() {
        const player = document.getElementById('stickyPlayer');
        if (player) {
            player.classList.add('expanded');
            document.body.style.overflow = 'hidden';
        }
        const adBanner = document.getElementById('stickyAdBanner');
        if (adBanner) {
            adBanner.classList.add('expanded-mode');
        }
    }

    function collapsePlayer() {
        const player = document.getElementById('stickyPlayer');
        if (player) {
            player.classList.remove('expanded');
            document.body.style.overflow = '';
        }
        const adBanner = document.getElementById('stickyAdBanner');
        if (adBanner) {
            adBanner.classList.remove('expanded-mode');
        }
    }

    document.getElementById('stickyPlayer').addEventListener('click', function(e) {
        if (window.innerWidth > 768) return;
        if (this.classList.contains('expanded')) return;
        if (e.target.closest('button') || e.target.closest('input')) return;
        expandPlayer();
    });

    // ========== NEXT / PREV ==========
    function getNextIndex() {
        if (currentPlaylistItems.length === 0) return -1;

        if (isShuffled) {
            shuffleIndex++;
            if (shuffleIndex >= shuffleOrder.length) {
                if (repeatMode >= 1) {
                    generateShuffleOrder();
                    shuffleIndex = 0;
                } else {
                    return -1;
                }
            }
            return shuffleOrder[shuffleIndex];
        } else {
            const next = currentTrackIndex + 1;
            if (next < currentPlaylistItems.length) {
                return next;
            } else if (repeatMode >= 1) {
                return 0;
            }
            return -1;
        }
    }

    function getPrevIndex() {
        if (currentPlaylistItems.length === 0) return -1;

        if (isShuffled) {
            shuffleIndex--;
            if (shuffleIndex < 0) {
                if (repeatMode >= 1) {
                    shuffleIndex = shuffleOrder.length - 1;
                } else {
                    shuffleIndex = 0;
                    return shuffleOrder[0];
                }
            }
            return shuffleOrder[shuffleIndex];
        } else {
            const prev = currentTrackIndex - 1;
            if (prev >= 0) {
                return prev;
            } else if (repeatMode >= 1) {
                return currentPlaylistItems.length - 1;
            }
            return 0;
        }
    }

    function playNext() {
        const next = getNextIndex();
        if (next !== -1) {
            playTrack(next);
        } else {
            isPlaying = false;
            updatePlayPauseUI();
            const pt = document.getElementById('playerTitle');
            if (pt) pt.textContent = 'Fin de la playlist';
        }
    }

    function playPrev() {
        if (audioPlayer.currentTime > 3) {
            audioPlayer.currentTime = 0;
            if (audioPlayer.paused) {
                audioPlayer.play().then(() => {
                    isPlaying = true;
                    updatePlayPauseUI();
                });
            }
            return;
        }
        const prev = getPrevIndex();
        if (prev !== -1) {
            playTrack(prev);
        }
    }

    // ========== SHUFFLE ==========
    function generateShuffleOrder() {
        shuffleOrder = Array.from({length: currentPlaylistItems.length}, (_, i) => i);
        for (let i = shuffleOrder.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffleOrder[i], shuffleOrder[j]] = [shuffleOrder[j], shuffleOrder[i]];
        }
        shuffleIndex = -1;
    }

    function toggleShuffle() {
        isShuffled = !isShuffled;
        const btn = document.getElementById('shuffleBtn');
        btn.style.color = isShuffled ? 'var(--primary-color)' : '';
        btn.style.opacity = isShuffled ? '1' : '';
        const existingDot = btn.querySelector('.active-dot');
        if (isShuffled && !existingDot) {
            const dot = document.createElement('span');
            dot.className = 'active-dot';
            btn.appendChild(dot);
        } else if (!isShuffled && existingDot) {
            existingDot.remove();
        }
        if (isShuffled) {
            generateShuffleOrder();
            if (currentTrackIndex >= 0) {
                const idx = shuffleOrder.indexOf(currentTrackIndex);
                if (idx > 0) {
                    [shuffleOrder[0], shuffleOrder[idx]] = [shuffleOrder[idx], shuffleOrder[0]];
                }
                shuffleIndex = 0;
            }
        }
    }

    // ========== REPEAT ==========
    function updateRepeatUI() {
        const btn = document.getElementById('repeatBtn');
        btn.style.color = '';
        btn.style.opacity = '';
        btn.innerHTML = '<i class="fas fa-redo"></i>';

        if (repeatMode === 0) {
            btn.title = 'Repetir: Desactivado';
        } else if (repeatMode === 1) {
            btn.style.color = 'var(--primary-color)';
            btn.style.opacity = '1';
            btn.innerHTML = '<i class="fas fa-redo"></i><span class="active-dot"></span>';
            btn.title = 'Repetir: Toda la playlist';
        } else {
            btn.style.color = 'var(--primary-color)';
            btn.style.opacity = '1';
            btn.innerHTML = '<i class="fas fa-redo"></i><span style="font-size:0.55em;font-weight:900;line-height:1;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;">1</span><span class="active-dot"></span>';
            btn.title = 'Repetir: Una canción';
        }
    }

    function toggleRepeat() {
        repeatMode = (repeatMode + 1) % 3;
        updateRepeatUI();
    }

    // ========== SEEK ==========
    function seekAudio(e) {
        if (!audioPlayer.duration || isNaN(audioPlayer.duration)) return;
        const bar = document.getElementById('progressBarContainer');
        const rect = bar.getBoundingClientRect();
        const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        audioPlayer.currentTime = percent * audioPlayer.duration;
    }

    // ========== PROGRESS UPDATES ==========
    audioPlayer.addEventListener('timeupdate', function() {
        if (!audioPlayer.duration || isNaN(audioPlayer.duration)) return;
        const pct = (audioPlayer.currentTime / audioPlayer.duration) * 100;
        const pb = document.getElementById('progressBar');
        if (pb) pb.style.width = pct + '%';
        const tcEl = document.getElementById('timeCurrent');
        if (tcEl) tcEl.textContent = formatTime(audioPlayer.currentTime);
        const ttEl = document.getElementById('timeTotal');
        if (ttEl) ttEl.textContent = formatTime(audioPlayer.duration);
    });

    audioPlayer.addEventListener('error', function(e) {
        if (!audioPlayer.src || audioPlayer.src === window.location.href) return;
        if (currentFetchController !== null) return;

        if (currentTrackIndex >= 0) {
            const pt = document.getElementById('playerTitle');
            if (pt) pt.innerHTML = `<span style="color:#f87171;"><i class="fas fa-exclamation-triangle me-1"></i>Error al cargar el audio. Intenta de nuevo.</span>`;
        }
        isPlaying = false;
        currentFetchController = null;
        updatePlayPauseUI();
    });

    audioPlayer.addEventListener('canplay', function() {
        if (currentTrackIndex >= 0 && currentPlaylistItems[currentTrackIndex]) {
            const track = currentPlaylistItems[currentTrackIndex];
            const pt = document.getElementById('playerTitle');
            if (pt && (pt.innerHTML.includes('spinner-border') || pt.innerHTML.includes('fa-spinner'))) {
                pt.textContent = track.title;
            }
        }
    });

    audioPlayer.addEventListener('ended', function() {
        if (repeatMode === 2) {
            audioPlayer.currentTime = 0;
            audioPlayer.play().then(() => {
                isPlaying = true;
                updatePlayPauseUI();
            });
        } else {
            // Mostrar anuncio intersticial cada 3 canciones (solo usuarios free)
            if ({{ ads_enabled|tojson }} && shouldShowInterstitialAd()) {
                showInterstitialAd(() => playNext());
            } else {
                playNext();
            }
        }
    });

    audioPlayer.addEventListener('play', function() {
        isPlaying = true;
        if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';
        updatePlayPauseUI();
        startBgAdImpressions();
    });
    audioPlayer.addEventListener('pause', function() {
        if (!currentFetchController) {
            isPlaying = false;
            if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
            updatePlayPauseUI();
        }
        stopBgAdImpressions();
    });

    // Manejar cuando el usuario sale y vuelve a la app (visibilitychange)
    // En móvil, algunos navegadores pausan el audio al ir al fondo.
    // Al volver, verificamos si debería seguir sonando y lo reanudamos.
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible' && isPlaying && audioPlayer.paused) {
            // El usuario volvió a la app y la música debería estar sonando pero se pausó
            audioPlayer.play().then(() => {
                if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';
                updatePlayPauseUI();
            }).catch(() => {});
        }
    });

    let bgAdInterval = null;
    function startBgAdImpressions() {
        if (!{{ ads_enabled|tojson }}) return;
        if (bgAdInterval) return;

        let iframe = document.getElementById('bgAdIframe');
        if (!iframe) {
            iframe = document.createElement('iframe');
            iframe.id = 'bgAdIframe';
            iframe.style.position = 'absolute';
            iframe.style.width = '0px';
            iframe.style.height = '0px';
            iframe.style.border = 'none';
            iframe.style.visibility = 'hidden';
            document.body.appendChild(iframe);
        }

        iframe.src = '/?bg_ad=true';

        bgAdInterval = setInterval(() => {
            if (audioPlayer && !audioPlayer.paused) {
                iframe.src = '/?bg_ad=true&t=' + Date.now();
            }
        }, 30000);
    }

    function stopBgAdImpressions() {
        if (bgAdInterval) {
            clearInterval(bgAdInterval);
            bgAdInterval = null;
        }
    }

    // ========== INTERSTITIAL AD ==========
    let songsSinceLastAd = 0;
    let interstitialPending = null;
    let adCountdownTimer = null;

    function shouldShowInterstitialAd() {
        songsSinceLastAd++;
        if (songsSinceLastAd >= 3) {
            songsSinceLastAd = 0;
            return true;
        }
        return false;
    }

    function showInterstitialAd(onDone) {
        const overlay = document.getElementById('interstitialAdOverlay');
        const countdownEl = document.getElementById('adCountdown');
        const skipBtn = document.getElementById('skipAdBtn');
        if (!overlay) { onDone(); return; }

        // Show overlay
        overlay.style.display = 'flex';
        interstitialPending = onDone;
        let remaining = 5;
        countdownEl.textContent = remaining;
        skipBtn.style.display = 'none';

        // Refresh the ad slot
        try {
            const slot = document.getElementById('interstitialAdSlot');
            if (slot && slot.dataset.adsbygoogleStatus) {
                slot.dataset.adsbygoogleStatus = '';
                (adsbygoogle = window.adsbygoogle || []).push({});
            }
        } catch(e) {}

        adCountdownTimer = setInterval(() => {
            remaining--;
            countdownEl.textContent = remaining;
            if (remaining <= 0) {
                clearInterval(adCountdownTimer);
                skipBtn.style.display = 'inline-block';
                // Auto-close after 2 more seconds if user hasn't clicked
                setTimeout(() => skipInterstitialAd(), 2000);
            }
        }, 1000);
    }

    function skipInterstitialAd() {
        clearInterval(adCountdownTimer);
        const overlay = document.getElementById('interstitialAdOverlay');
        if (overlay) overlay.style.display = 'none';
        if (interstitialPending) {
            interstitialPending();
            interstitialPending = null;
        }
    }

    // Ajustar el sticky player cuando el banner de anuncios esta visible
    (function adjustPlayerForAd() {
        const adBanner = document.getElementById('stickyAdBanner');
        const player = document.getElementById('stickyPlayer');
        if (adBanner && player) {
            const adH = adBanner.offsetHeight || 60;
            player.style.bottom = adH + 'px';
        }
    })();

    // ========== VOLUME ==========
    function setVolume(val) {
        audioPlayer.volume = val / 100;
        const icon = document.getElementById('volumeIcon').querySelector('i');
        if (val == 0) icon.className = 'fas fa-volume-mute';
        else if (val < 50) icon.className = 'fas fa-volume-down';
        else icon.className = 'fas fa-volume-up';
    }

    function toggleMute() {
        audioPlayer.muted = !audioPlayer.muted;
        const slider = document.getElementById('volumeSlider');
        const icon = document.getElementById('volumeIcon').querySelector('i');
        if (audioPlayer.muted) {
            icon.className = 'fas fa-volume-mute';
            slider.value = 0;
        } else {
            icon.className = 'fas fa-volume-up';
            slider.value = audioPlayer.volume * 100;
        }
    }

    audioPlayer.volume = 0.8;

    function formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    // ========== KEYBOARD SHORTCUTS ==========
    document.addEventListener('keydown', function(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        switch(e.code) {
            case 'Space':
                e.preventDefault();
                togglePlay();
                break;
            case 'ArrowRight':
                if (e.shiftKey) { playNext(); } 
                else if (audioPlayer.duration) { audioPlayer.currentTime = Math.min(audioPlayer.duration, audioPlayer.currentTime + 5); }
                break;
            case 'ArrowLeft':
                if (e.shiftKey) { playPrev(); }
                else if (audioPlayer.duration) { audioPlayer.currentTime = Math.max(0, audioPlayer.currentTime - 5); }
                break;
        }
    });

    // ========== UPLOAD LOCAL FILE ==========
    async function uploadLocalFile(playlistId) {
        const fileInput = document.getElementById('uploadFileInput');
        if (!fileInput.files || fileInput.files.length === 0) return;
        
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('playlist_id', playlistId);
        formData.append('file', file);

        const btns = document.querySelectorAll('.btn-action');
        let uploadBtn = null;
        btns.forEach(b => { if(b.innerHTML.includes('fa-upload')) uploadBtn = b; });
        const originalHTML = uploadBtn ? uploadBtn.innerHTML : '';
        if(uploadBtn) {
            uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subiendo...';
            uploadBtn.disabled = true;
        }

        try {
            const res = await fetch('/api/playlists/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (data.success) {
                loadPlaylist(playlistId);
            } else {
                showToast(data.error || 'Error al subir el archivo.');
            }
        } catch (e) {
            showToast('Error de conexión al subir el archivo.');
        } finally {
            if(uploadBtn) {
                uploadBtn.innerHTML = originalHTML;
                uploadBtn.disabled = false;
            }
            fileInput.value = '';
        }
    }

    // Single tap handler: on mobile opens bottom sheet, on desktop does nothing (dblclick plays)
    function handleTrackTap(event, index, playlistId, itemId, safeUrl, safeThumb, safeTitle) {
        // Don't trigger if tapping a button inside the row
        if (event.target.closest('button')) return;
        
        const isMobile = window.innerWidth <= 768;
        if (isMobile) {
            openTrackSheet(index, playlistId, itemId, safeUrl, safeThumb, safeTitle);
        }
    }

    function openTrackSheet(index, playlistId, itemId, safeUrl, safeThumb, title) {
        const url = decodeURIComponent(safeUrl);
        const thumb = decodeURIComponent(safeThumb);
        
        document.getElementById('bsTitle').textContent = title;
        document.getElementById('bsSub').textContent = currentPlaylistItems[index]?.platform || '';
        document.getElementById('bsThumb').src = thumb;

        const overlay = document.getElementById('trackBottomSheet');
        overlay.classList.add('open');
        document.body.style.overflow = 'hidden';

        const btnPlay = document.getElementById('bsBtnPlay');
        const btnDl = document.getElementById('bsBtnDownload');
        const btnAdd = document.getElementById('bsBtnAddToPlaylist');
        const btnDel = document.getElementById('bsBtnDelete');
        
        btnPlay.onclick = () => { closeTrackSheet(); playTrack(index); };
        btnDl.onclick = () => { closeTrackSheet(); downloadTrack(url); };
        btnAdd.onclick = () => { closeTrackSheet(); openAddToPlaylistModal(index); };
        btnDel.onclick = () => { closeTrackSheet(); removeTrack(playlistId, itemId, safeUrl); };
    }

    // ========== ADD TO PLAYLIST ==========
    let currentItemToAdd = null;

    function openAddToPlaylistModal(index) {
        currentItemToAdd = currentPlaylistItems[index];
        if (!currentItemToAdd) return;
        
        const modalEl = document.getElementById('addToPlaylistModal');
        const modal = new bootstrap.Modal(modalEl);
        modal.show();

        fetch('/api/playlists/list')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    let html = '';
                    data.playlists.forEach(pl => {
                        if (pl.id == currentPlaylistId) return; // Skip current
                        html += `<button class="btn w-100 mb-2 text-start fw-semibold" onclick="executeAddToPlaylist(${pl.id})" style="background: rgba(255,255,255,0.04); color: #cdd6f4; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px 16px; transition: all 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.08)'; this.style.borderColor='rgba(255,255,255,0.2)';" onmouseout="this.style.background='rgba(255,255,255,0.04)'; this.style.borderColor='rgba(255,255,255,0.08)';"><i class="fas fa-music me-3" style="color:#a6e3a1;"></i>${pl.name}</button>`;
                    });
                    if (!html) html = '<p class="text-secondary small"><i class="fas fa-info-circle me-1"></i>No hay otras playlists disponibles.</p>';
                    document.getElementById('addToPlaylistList').innerHTML = html;
                }
            })
            .catch(() => {
                document.getElementById('addToPlaylistList').innerHTML = '<p class="text-danger small">Error al cargar playlists.</p>';
            });
    }

    function executeAddToPlaylist(playlistId) {
        if (!currentItemToAdd) return;
        const payload = {
            title: currentItemToAdd.title,
            url: currentItemToAdd.url,
            thumbnail: currentItemToAdd.thumbnail,
            platform: currentItemToAdd.platform,
            duration: currentItemToAdd.duration,
            duration_formatted: currentItemToAdd.duration_formatted
        };
        fetch(`/api/playlists/${playlistId}/add`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        })
        .then(r => r.json())
        .then(data => {
            const modalEl = document.getElementById('addToPlaylistModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
            
            if (data.success) {
                showToast('<i class="fas fa-check-circle" style="color:#10b981;"></i> Agregado a la playlist.');
            } else {
                showToast('<i class="fas fa-exclamation-circle" style="color:#ef4444;"></i> Error: ' + data.error);
            }
        });
    }

    function closeTrackSheet(e) {
        if (e && e.target !== document.getElementById('trackBottomSheet')) return;
        const overlay = document.getElementById('trackBottomSheet');
        overlay.classList.remove('open');
        document.body.style.overflow = '';
    }

    function showConfirm(message) {
        return new Promise((resolve) => {
            const modal = document.getElementById('customConfirmModal');
            document.getElementById('confirmModalMsg').textContent = message;
            modal.style.display = 'flex';
            const ok = document.getElementById('confirmModalOk');
            const cancel = document.getElementById('confirmModalCancel');
            function cleanup(result) {
                modal.style.display = 'none';
                ok.removeEventListener('click', onOk);
                cancel.removeEventListener('click', onCancel);
                resolve(result);
            }
            function onOk() { cleanup(true); }
            function onCancel() { cleanup(false); }
            ok.addEventListener('click', onOk);
            cancel.addEventListener('click', onCancel);
        });
    }

    // ========== DOWNLOAD ==========
    const OFFLINE_CACHE_NAME = 'savewave-offline';

    async function removeTrack(playlistId, itemId, url) {
        const confirmed = await showConfirm('¿Eliminar esta canción de tu playlist?');
        if (!confirmed) return;
        
        try {
            const res = await fetch(`/api/playlists/${playlistId}/remove/${itemId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                try {
                    const offlineCache = await caches.open(OFFLINE_CACHE_NAME);
                    await offlineCache.delete(decodeURIComponent(url));
                } catch(e) {}
                
                loadPlaylist(playlistId);
            } else {
                showToast('Error al eliminar: ' + data.error);
            }
        } catch(e) {
            showToast('Error de conexión');
        }
    }

    function showDownloadOptions(playlistId) {
        document.getElementById('downloadZipBtn').onclick = function() {
            bootstrap.Modal.getInstance(document.getElementById('downloadOptionsModal')).hide();
            downloadPlaylistAll(playlistId);
        };
        document.getElementById('offlineProgressContainer').classList.add('d-none');
        new bootstrap.Modal(document.getElementById('downloadOptionsModal')).show();
    }

    async function checkOfflineStatus() {
        try {
            const offlineCache = await caches.open(OFFLINE_CACHE_NAME);
            for (let i = 0; i < currentPlaylistItems.length; i++) {
                const track = currentPlaylistItems[i];
                const cacheKey = '/offline-cache/?url=' + encodeURIComponent(track.url);
                const cached = await offlineCache.match(cacheKey);
                const badge = document.getElementById('offlineBadge' + i);
                if (badge) {
                    if (cached || track.platform === 'audio_local' || track.platform === 'video_local') {
                        badge.classList.remove('d-none');
                    } else {
                        badge.classList.add('d-none');
                    }
                }
            }
        } catch(e) {
        }
    }

    async function downloadPlaylistOffline() {
        if (currentPlaylistItems.length === 0) return;

        const progressContainer = document.getElementById('offlineProgressContainer');
        const progressBar = document.getElementById('offlineProgressBar');
        const progressText = document.getElementById('offlineProgressText');
        const progressCount = document.getElementById('offlineProgressCount');

        const modalEl = document.getElementById('downloadOptionsModal');
        const closeBtn = document.getElementById('downloadModalCloseBtn');
        
        // La única forma 100% segura en Bootstrap 5 de evitar que se cierre
        window.isDownloadingOffline = true;
        if (!window.downloadModalListenerAdded) {
            modalEl.addEventListener('hide.bs.modal', function (e) {
                if (window.isDownloadingOffline) {
                    e.preventDefault(); // Bloquea completamente el cierre
                }
            });
            window.downloadModalListenerAdded = true;
        }

        if (closeBtn) closeBtn.classList.add('d-none');
        
        document.querySelectorAll('#downloadOptionsBody .dl-option').forEach(b => b.classList.add('d-none'));
        progressContainer.classList.remove('d-none');

        const total = currentPlaylistItems.length;
        let completed = 0;
        let errors = 0;

        try {
            const offlineCache = await caches.open(OFFLINE_CACHE_NAME);
            
            // Limitar concurrencia a 2 para evitar saturar el CPU del VPS (deno gasta mucho CPU)
            const limit = 2;
            const items = [...currentPlaylistItems];
            
            let wakeLock = null;
            try {
                if ('wakeLock' in navigator) {
                    wakeLock = await navigator.wakeLock.request('screen');
                }
            } catch (err) {
                console.log('Wake Lock no soportado o denegado');
            }

            const downloadTrackOffline = async (track) => {
                const cacheKey = '/offline-cache/?url=' + encodeURIComponent(track.url);
                const existing = await offlineCache.match(cacheKey);
                
                if (existing || track.platform === 'audio_local' || track.platform === 'video_local') {
                    completed++;
                    updateUI(track.title, '✓ Ya guardada');
                    return;
                }

                const shortTitle = (track.title || 'canción').substring(0, 28);

                try {
                    progressText.textContent = `⬇️ Descargando: ${shortTitle}...`;
                    
                    let audioRes = null;
                    let lastError = '';

                    // Intentar hasta 2 veces (1 reintento automático)
                    for (let attempt = 1; attempt <= 2; attempt++) {
                        try {
                            audioRes = await fetch('/api/download-proxy', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                body: 'url=' + encodeURIComponent(track.url)
                            });

                            if (audioRes && audioRes.ok) {
                                break; // Éxito, salir del loop
                            } else {
                                lastError = `HTTP ${audioRes ? audioRes.status : 'null'}`;
                                console.warn(`[Offline] ${shortTitle}: intento ${attempt} falló (${lastError})`);
                                if (attempt < 2) {
                                    await new Promise(r => setTimeout(r, 2000)); // Esperar 2s antes de reintentar
                                }
                                audioRes = null;
                            }
                        } catch(fetchErr) {
                            lastError = fetchErr.message || 'Network error';
                            console.warn(`[Offline] ${shortTitle}: intento ${attempt} excepción: ${lastError}`);
                            if (attempt < 2) {
                                await new Promise(r => setTimeout(r, 2000));
                            }
                            audioRes = null;
                        }
                    }

                    if (audioRes && audioRes.ok) {
                        await offlineCache.put(cacheKey, audioRes.clone());
                        console.log(`[Offline] ✓ ${shortTitle}`);
                    } else {
                        console.error(`[Offline] ✗ ${shortTitle}: ${lastError}`);
                        errors++;
                    }
                } catch(trackErr) {
                    console.error(`[Offline] ✗ ${shortTitle}: ${trackErr.message}`);
                    errors++;
                }

                completed++;
                updateUI(track.title);
            };

            function updateUI(currentTitle, statusMsg) {
                progressCount.textContent = `${completed}/${total}`;
                progressBar.style.width = `${(completed / total) * 100}%`;
                if (completed >= total) {
                    window.isDownloadingOffline = false; // Permitir cerrar
                    
                    if (wakeLock !== null) {
                        wakeLock.release().catch(() => {});
                        wakeLock = null;
                    }
                    
                    if (errors > 0) {
                        progressText.textContent = `✅ Listo. ${completed - errors} guardadas, ${errors} con error.`;
                    } else {
                        progressText.textContent = '✅ Todas las canciones guardadas para escuchar offline.';
                    }
                    // Solo cerrar automáticamente si no hubo errores, para que el usuario pueda leer el resultado
                    if (errors === 0) {
                        setTimeout(() => {
                            try { bootstrap.Modal.getInstance(modalEl).hide(); } catch(e){}
                            location.reload();
                        }, 2500);
                    } else {
                        if (closeBtn) closeBtn.classList.remove('d-none'); // Mostrar el botón de cerrar si hubo errores
                    }
                } else if (statusMsg) {
                    progressText.textContent = statusMsg;
                }
            }

            let poolIndex = 0;
            const workers = [];
            const worker = async () => {
                while (poolIndex < items.length) {
                    const idx = poolIndex++;
                    await downloadTrackOffline(items[idx]);
                }
            };

            for (let i = 0; i < Math.min(limit, items.length); i++) {
                workers.push(worker());
            }
            await Promise.all(workers);

        } catch(e) {
            console.error(e);
            window.isDownloadingOffline = false; // Permitir cerrar
            progressText.textContent = 'Error crítico al descargar.';
            setTimeout(() => {
                const modal = bootstrap.Modal.getInstance(document.getElementById('downloadOptionsModal'));
                if (modal) modal.hide();
                document.querySelectorAll('#downloadOptionsBody .dl-option').forEach(b => b.classList.remove('d-none'));
                progressContainer.classList.add('d-none');
            }, 3000);
        }
    }

    async function downloadTrack(url) {
        try {
            const res = await fetch('/api/download-audio', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'url=' + encodeURIComponent(url) + '&quality=320'
            });
            const data = await res.json();
            if (data.success) {
                showToast('Descarga iniciada');
                const a = document.createElement('a');
                a.href = data.download_url;
                a.download = '';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            } else {
                showToast(data.error);
            }
        } catch(e) {
            showToast('Error al descargar la canción.');
        }
    }

    async function downloadPlaylistAll(id) {
        if (currentPlaylistItems.length === 0) return;
        const urls = currentPlaylistItems.map(i => i.url);
        const btn = document.querySelector('.btn-action');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Preparando...';
        btn.disabled = true;

        try {
            const res = await fetch('/api/download-multiple', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ urls: urls })
            });
            const data = await res.json();
            if (data.success) {
                showToast('Descarga iniciada');
                window.location.href = data.download_url;
            } else {
                showToast(data.error);
            }
        } catch(e) {
            showToast('Error al descargar la playlist.');
        } finally {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }
    }

