"""
CONFIGURACIÓN DE LA APLICACIÓN
===============================
Centraliza todas las variables de configuración.
Carga variables de entorno desde un archivo .env si existe.
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env (si existe)
load_dotenv()


class Config:
    """
    Configuración principal de la aplicación Flask.
    Todas las variables sensibles se cargan desde variables de entorno.
    """

    # -------------------- CLAVE SECRETA --------------------
    # Usada por Flask para firmar cookies de sesion y tokens CSRF
    SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-esta-clave-en-produccion")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cambiar-esta-clave-jwt")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600"))

    # -------------------- SEGURIDAD DE SESIONES --------------------
    # Cookie de sesion: solo HTTP (no accesible desde JS)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # No forzar HTTPS en desarrollo (solo en produccion con dominio real)
    SESSION_COOKIE_SECURE = False
    # La sesion no expira al cerrar el navegador (persiste 30 dias)
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 30 * 24 * 60 * 60  # 30 dias en segundos

    # -------------------- RATE LIMITING (Límites de peticiones) --------------------
    # Limita las peticiones a las APIs para prevenir abusos
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "True") == "True"
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "100 per minute")
    RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "memory://")

    # -------------------- BASE DE DATOS --------------------
    # MySQL para producción, SQLite para desarrollo local
    # Para usar MySQL: export DATABASE_URL=mysql+pymysql://usuario:contraseña@host:3306/savewave
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///savewave.db"  # SQLite para desarrollo local
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Connection pooling: mantiene conexiones abiertas en lugar de crear una nueva por request
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),          # Conexiones simultaneas maximas
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),    # Conexiones extra si hay pico
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),    # Segundos esperando conexion
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),  # Reciclar conexion cada 1 hora
        "pool_pre_ping": True,  # Verificar que la conexion sigue viva antes de usarla
    }

    # -------------------- CACHE (Redis) --------------------
    # Cachea consultas frecuentes para evitar llamadas repetidas a la BD
    CACHE_TYPE = os.getenv("CACHE_TYPE", "RedisCache")
    CACHE_REDIS_URL = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0")
    CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300"))  # 5 minutos

    # -------------------- LÍMITES DEL PLAN ANÓNIMO (sin cuenta) --------------------
    ANONYMOUS_MAX_QUALITY = "720p"    # Calidad máxima sin cuenta
    ANONYMOUS_PLATFORMS = ["youtube"] # Solo YouTube sin cuenta
    ANONYMOUS_UNLIMITED = True        # Sin límite diario (no tenemos como controlarlo)

    # -------------------- LÍMITES DEL PLAN GRATUITO (registrado) --------------------
    FREE_DAILY_LIMIT = 5                     # Limite de descargas para usuarios gratuitos
    FREE_MAX_QUALITY = "720p"                # Calidad máxima en plan gratuito
    FREE_PLATFORMS = ["youtube", "facebook", "twitter_x", "vimeo", "dailymotion"]

    # -------------------- LÍMITES DEL PLAN PRO ($2/mes) --------------------
    PRO_MONTHLY_PRICE = 2.00       # Precio en USD
    PRO_MAX_QUALITY = "1080p"      # Full HD
    PRO_PLATFORMS = ["youtube", "instagram", "tiktok", "facebook", "twitter_x",
                     "vimeo", "dailymotion", "twitch", "reddit", "linkedin"]

    # -------------------- LÍMITES DEL PLAN PREMIUM ($5/mes) --------------------
    PREMIUM_MONTHLY_PRICE = 5.00   # Precio en USD
    PREMIUM_MAX_QUALITY = "2160p"  # 4K
    PREMIUM_PLATFORMS = ["youtube", "instagram", "tiktok", "facebook", "twitter_x",
                         "vimeo", "dailymotion", "twitch", "reddit", "linkedin"]

    # -------------------- STRIPE (PAGOS) --------------------
    STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "")
    STRIPE_PREMIUM_PRICE_ID = os.getenv("STRIPE_PREMIUM_PRICE_ID", "")

    # -------------------- REDIS / CELERY (Tareas en segundo plano) --------------------
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # -------------------- CARPETA DE DESCARGAS TEMPORALES --------------------
    DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    # Tiempo máximo que un archivo descargado se guarda antes de eliminarse (en segundos)
    DOWNLOAD_EXPIRY_SECONDS = 3600  # 1 hora

    # Tamaño máximo de upload de archivos (200 MB)
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB

    # -------------------- ANUNCIOS --------------------
    ADS_ENABLED = True  # Activar/desactivar anuncios globalmente
    # Código de AdSense (se inyecta en las plantillas)
    ADSENSE_CLIENT_ID = os.getenv("ADSENSE_CLIENT_ID", "")