"""
PUNTO DE ENTRADA PARA PRODUCCION (WSGI)
=======================================
Usar con: gunicorn wsgi:app --workers 4 --worker-class gevent --bind 0.0.0.0:5000
O con: waitress-serve --port=5000 wsgi:app

Configurado para alto rendimiento:
  - 4 workers (2 x numero de CPUs)
  - Gevent para manejo asincrono
  - Connection pooling a MySQL
  - Cache con Redis
  - Tareas en segundo plano con Celery
"""

import os
from app import app

if __name__ == "__main__":
    # En produccion usar gunicorn o waitress, no este modo debug
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)