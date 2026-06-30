"""
TRABAJADOR EN SEGUNDO PLANO (CELERY)
======================================
Procesa descargas en segundo plano para no bloquear el servidor.
Las descargas largas se encolan y el usuario recibe una notificacion
cuando estan listas.

Ejecutar con: celery -A celery_worker worker --loglevel=info
"""

import os
import time
from celery import Celery
from config import Config

# Crear aplicacion Celery
celery_app = Celery(
    "savewave",
    broker=Config.CELERY_BROKER_URL,
    backend=Config.CELERY_RESULT_BACKEND,
)

# Configuracion de Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Limitar concurrencia: maximo 3 descargas simultaneas
    worker_concurrency=3,
    # Tareas que requieren mucho tiempo
    task_soft_time_limit=300,   # 5 minutos maximo
    task_time_limit=600,        # 10 minutos maximo
)


@celery_app.task(bind=True, max_retries=3)
def download_video_task(self, url: str, quality: str = "720p"):
    """
    Descarga un video en segundo plano.
    Se ejecuta en un worker separado para no bloquear el servidor web.
    """
    from downloader import download_video

    # Reportar progreso
    self.update_state(state="PROGRESS", meta={"status": "Descargando...", "percent": 10})

    try:
        result = download_video(url, quality)

        if result["success"]:
            self.update_state(state="SUCCESS", meta={
                "status": "Completado",
                "percent": 100,
                "file_path": result["file_path"],
                "filename": result["filename"],
                "file_size": result["file_size_formatted"],
            })
            return result
        else:
            raise Exception(result.get("error", "Error desconocido"))

    except Exception as exc:
        self.update_state(state="FAILURE", meta={"status": "Error", "error": str(exc)})
        raise self.retry(exc=exc, countdown=60)  # Reintentar en 60 segundos


@celery_app.task(bind=True, max_retries=3)
def download_audio_task(self, url: str, quality: str = "128"):
    """
    Convierte un video a MP3 en segundo plano.
    """
    from downloader import download_audio

    self.update_state(state="PROGRESS", meta={"status": "Convirtiendo a MP3...", "percent": 10})

    try:
        result = download_audio(url, quality)

        if result["success"]:
            self.update_state(state="SUCCESS", meta={
                "status": "Completado",
                "percent": 100,
                "file_path": result["file_path"],
                "filename": result["filename"],
                "file_size": result["file_size_formatted"],
            })
            return result
        else:
            raise Exception(result.get("error", "Error desconocido"))

    except Exception as exc:
        self.update_state(state="FAILURE", meta={"status": "Error", "error": str(exc)})
        raise self.retry(exc=exc, countdown=60)