// ============================================================
// SaveWave Extension - Popup Script
// ============================================================

// URL del backend (cambiar a https://savewave.com en produccion)
const API_BASE = "http://localhost:5000";

// Obtener la URL de la pestana activa al abrir el popup
chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
    if (tabs && tabs[0] && tabs[0].url) {
        const url = tabs[0].url;
        // Si la pestana activa tiene un video, ponerlo automaticamente
        if (url.includes("youtube.com") || url.includes("youtu.be") ||
            url.includes("instagram.com") || url.includes("tiktok.com") ||
            url.includes("facebook.com") || url.includes("x.com") ||
            url.includes("twitter.com") || url.includes("vimeo.com")) {
            document.getElementById("urlInput").value = url;
            checkUrl(url);
        }
    }
});

// Referencias a elementos DOM
const urlInput = document.getElementById("urlInput");
const downloadBtn = document.getElementById("downloadBtn");
const btnText = document.getElementById("btnText");
const spinner = document.getElementById("spinner");
const qualitySelect = document.getElementById("qualitySelect");
const resultDiv = document.getElementById("result");
const errorDiv = document.getElementById("error");
const errorText = document.getElementById("errorText");
const resultText = document.getElementById("resultText");
const downloadLink = document.getElementById("downloadLink");

// Estado del formato (video / mp3)
let currentFormat = "video";

// ============================================================
// Formato buttons
// ============================================================
document.querySelectorAll(".format-btn").forEach(function(btn) {
    btn.addEventListener("click", function() {
        document.querySelectorAll(".format-btn").forEach(function(b) {
            b.classList.remove("active");
        });
        btn.classList.add("active");
        currentFormat = btn.dataset.format;

        // Cambiar opciones de calidad segun el formato
        qualitySelect.innerHTML = "";
        if (currentFormat === "mp3") {
            qualitySelect.innerHTML = `
                <option value="128">MP3 128kbps</option>
                <option value="320">MP3 320kbps</option>
            `;
        } else {
            qualitySelect.innerHTML = `
                <option value="720p">720p</option>
                <option value="480p">480p</option>
                <option value="360p">360p</option>
            `;
        }
    });
});

// ============================================================
// Auto-detectar URL mientras escribe
// ============================================================
let checkTimeout;
urlInput.addEventListener("input", function() {
    clearTimeout(checkTimeout);
    checkTimeout = setTimeout(function() {
        checkUrl(urlInput.value.trim());
    }, 800);
});

function checkUrl(url) {
    if (!url) {
        downloadBtn.disabled = true;
        btnText.textContent = "Pega un enlace";
        return;
    }

    downloadBtn.disabled = true;
    btnText.textContent = "Verificando...";

    fetch(API_BASE + "/api/video-info", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "url=" + encodeURIComponent(url)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            downloadBtn.disabled = false;
            btnText.textContent = "Descargar " + (currentFormat === "mp3" ? "MP3" : "Video");
            errorDiv.classList.add("hidden");

            // Mostrar calidades disponibles
            qualitySelect.innerHTML = "";
            if (currentFormat === "mp3") {
                qualitySelect.innerHTML = `
                    <option value="128">MP3 128kbps</option>
                    <option value="320">MP3 320kbps</option>
                `;
            } else {
                data.available_qualities.forEach(function(q) {
                    var opt = document.createElement("option");
                    opt.value = q;
                    opt.textContent = q;
                    qualitySelect.appendChild(opt);
                });
            }
        } else {
            downloadBtn.disabled = true;
            btnText.textContent = "URL no valida";
        }
    })
    .catch(function() {
        downloadBtn.disabled = false;
        btnText.textContent = "Descargar";
    });
}

// ============================================================
// Descargar
// ============================================================
downloadBtn.addEventListener("click", function() {
    const url = urlInput.value.trim();
    const quality = qualitySelect.value;

    if (!url) return;

    // Mostrar spinner
    downloadBtn.disabled = true;
    spinner.classList.remove("hidden");
    btnText.textContent = "Descargando...";
    resultDiv.classList.add("hidden");
    errorDiv.classList.add("hidden");

    // Elegir endpoint segun formato
    const endpoint = currentFormat === "mp3" ? "/api/download-audio" : "/api/download";

    fetch(API_BASE + endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "url=" + encodeURIComponent(url) + "&quality=" + encodeURIComponent(quality)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        spinner.classList.add("hidden");
        btnText.textContent = "Descargar";

        if (data.success) {
            resultText.textContent = data.title.substring(0, 40) + " (" + data.file_size + ")";
            downloadLink.href = API_BASE + data.download_url;
            resultDiv.classList.remove("hidden");
        } else {
            showError(data.error || "Error al descargar");
        }
    })
    .catch(function() {
        spinner.classList.add("hidden");
        btnText.textContent = "Descargar";
        showError("Error de conexion con el servidor");
    });
});

function showError(msg) {
    errorText.textContent = msg;
    errorDiv.classList.remove("hidden");
}