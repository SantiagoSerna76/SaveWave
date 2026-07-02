/**
 * SCRIPT GLOBAL - SaveWave
 * Dark mode + PWA install are handled in base.html inline script.
 */
$(document).ready(function() {
    console.log("[INFO] SaveWave v5 iniciado");

    // Auto-cerrar alertas flash
    setTimeout(function() {
        $(".alert-dismissible").fadeOut("slow");
    }, 5000);

    // ============================================================
    // PLAYLISTS - Reproducir desde el index (opcional)
    // ============================================================
    $(document).on("click", ".play-track", function() {
        const url = $(this).data("url");
        if (url) {
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
                alert("No tienes playlists. Crea una primero en la seccion Playlists.");
                return;
            }
            const chosen = prompt("Selecciona el numero de la playlist:\n" +
                data.playlists.map(function(p, i) { return (i + 1) + ". " + p.name; }).join("\n"));
            if (!chosen) return;
            const idx = parseInt(chosen) - 1;
            if (isNaN(idx) || idx < 0 || idx >= data.playlists.length) {
                alert("Numero invalido");
                return;
            }
            const playlistId = data.playlists[idx].id;

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
                        alert("¡Agregado a la playlist!");
                    } else {
                        alert("Error: " + (res.error || "No se pudo agregar"));
                    }
                },
                error: function() {
                    alert("Error de conexion. Intenta de nuevo.");
                }
            });
        });
    });
});