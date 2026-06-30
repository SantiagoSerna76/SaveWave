/**
 * SCRIPT GLOBAL - SaveWave
 * ===============================
 * Funciones JavaScript compartidas en toda la aplicacion.
 */

$(document).ready(function() {
    console.log("[INFO] SaveWave iniciado");

    // Auto-cerrar alertas despues de 5 segundos
    setTimeout(function() {
        $(".alert-dismissible").fadeOut("slow");
    }, 5000);

    // ============================================================
    // MODO OSCURO
    // ============================================================
    const toggle = document.getElementById("darkModeToggle");
    const icon = toggle ? toggle.querySelector("i") : null;

    // Cargar preferencia guardada
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
});