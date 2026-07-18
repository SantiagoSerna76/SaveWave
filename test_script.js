
    // Lógica para el Auto-Refresh inteligente del Banner usando iframe
    function loadAdsterraBanner() {
        const container = document.getElementById('adsterra-banner-container');
        if (!container) return;

        // Limpiar anuncio anterior
        container.innerHTML = '';

        // Usar iframe para aislar el document.write de Adsterra y evitar que borre la página
        const adFrame = document.createElement('iframe');
        adFrame.src = '/bg_ad';
        adFrame.width = '320';
        adFrame.height = '50';
        adFrame.frameBorder = '0';
        adFrame.scrolling = 'no';
        adFrame.style.border = 'none';
        adFrame.style.overflow = 'hidden';
        
        container.appendChild(adFrame);
    }

    // Cargar la primera vez cuando la página esté lista
    document.addEventListener('DOMContentLoaded', () => {
        loadAdsterraBanner();
        
        // Auto-refresh cada 30 segundos, SOLO si la pestaña está visible
        setInterval(() => {
            if (document.visibilityState === 'visible') {
                loadAdsterraBanner();
            }
        }, 30000);
    });
