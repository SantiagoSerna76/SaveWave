/**
 * SCRIPT GLOBAL - SaveWave
 */
$(document).ready(function() {
    console.log("[INFO] SaveWave iniciado");

    // Auto-cerrar alertas
    setTimeout(function() {
        $(".alert-dismissible").fadeOut("slow");
    }, 5000);

    // ============================================================
    // MODO OSCURO
    // ============================================================
    const toggle = document.getElementById("darkModeToggle");
    const icon = toggle ? toggle.querySelector("i") : null;

    if (localStorage.getItem("darkMode") === "true") {
        document.body.classList.add("dark-mode");
        if (icon) icon.className = "fas fa-sun";
    }

    if (toggle) {
        toggle.addEventListener("click", function() {
            document.body.classList.toggle("dark-mode");
            const isDark = document.body.classList.contains("dark-mode");
            localStorage.setItem("darkMode", isDark);
            if (icon) icon.className = isDark ? "fas fa-sun" : "fas fa-moon";
        });
    }

    // ============================================================
    // PWA - INSTALAR APP (siempre visible)
    // ============================================================
    let deferredPrompt;
    const installBtn = document.getElementById("installAppBtn");

    // Mostrar el boton siempre (no importa si ya esta instalado o no)
    if (installBtn) {
        installBtn.style.display = "inline-block";
    }

    window.addEventListener("beforeinstallprompt", function(e) {
        e.preventDefault();
        deferredPrompt = e;
    });

    if (installBtn) {
        installBtn.addEventListener("click", async function() {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                await deferredPrompt.userChoice;
                deferredPrompt = null;
            } else {
                // Si no hay prompt disponible, ir al manifest
                window.open("/manifest.json", "_blank");
            }
        });
    }

    // ============================================================
    // PLAYLISTS - Reproducir
    // ============================================================
    $(document).on("click", ".play-track", function() {
        const url = $(this).data("url");
        const title = $(this).data("title");
        if (url) {
            // Abrir en una nueva pestaña para descargar
            window.open(url, "_blank");
        }
    });

    // ============================================================
    // PLAYLISTS - Agregar a playlist desde el index
    // ============================================================
    $(document).on("click", ".save-to-playlist", function() {
        const videoUrl = $(this).data("url");
        const videoTitle = $(this).data("title");
        const videoThumb = $(this).data("thumb");
        const videoPlatform = $(this).data("platform");
        const videoDuration = $(this).data("duration");

        // Obtener playlists del usuario
        $.getJSON("/api/playlists/list", function(data) {
            if (!data.success || !data.playlists.length) {
                alert("No tienes playlists. Crea una primero.");
                return;
            }
            // Mostrar selector simple
            const names = data.playlists.map(function(p) { return p.name; }).join("\n");
            const chosen = prompt("Selecciona el numero de la playlist:\n" +
                data.playlists.map(function(p, i) { return (i + 1) + ". " + p.name; }).join("\n"));
            if (!chosen) return;
            const idx = parseInt(chosen) - 1;
            if (isNaN(idx) || idx < 0 || idx >= data.playlists.length) {
                alert("Numero invalido");
                return;
            }
            const playlistId = data.playlists[idx].id;

            // Agregar item
            $.ajax({
                url: "/api/playlists/add",
                method: "POST",
                contentType: "application/json",
                data: JSON.stringify({
                    playlist_id: playlistId,
                    items: [{
                        url: videoUrl,
                        title: videoTitle,
                        thumbnail: videoThumb,
                        platform: videoPlatform,
                        duration: videoDuration || 0
                    }]
                }),
                success: function(res) {
                    if (res.success) {
                        alert("Agregado a la playlist!");
                    }
                }
            });
        });
    });
});