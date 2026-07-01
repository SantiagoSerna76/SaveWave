"""
SISTEMA DE CACHE - SaveWave
============================
Cachea metadatos de videos para evitar consultas repetidas a YouTube.
Usa Redis si esta disponible, con fallback a memoria local.

Estrategia:
  - get_video_info: cache por 15 minutos (TTL=900)
  - Archivos descargados: cache por 1 hora (TTL=3600)
  - Si Redis no esta disponible, usa un diccionario en memoria
"""

import hashlib
import json
import os
import time
from datetime import datetime, timedelta

# Cache en memoria (fallback cuando Redis no esta disponible)
_memory_cache = {}
_memory_cache_expiry = {}


def _get_cache_key(url: str, prefix: str = "info") -> str:
    """
    Genera una clave unica para cachear basada en la URL.

    Args:
        url: URL del video.
        prefix: Prefijo para distinguir tipos de cache ('info', 'download').

    Returns:
        Clave de cache con hash.
    """
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return f"savewave:{prefix}:{url_hash}"


def _get_redis_client():
    """
    Intenta conectar a Redis. Si falla, retorna None.

    Returns:
        Cliente Redis o None.
    """
    try:
        import redis
        from config import Config
        client = redis.Redis.from_url(Config.CELERY_BROKER_URL)
        client.ping()  # Verifica que la conexion funcione
        return client
    except Exception:
        return None


def get_cached_video_info(url: str) -> dict:
    """
    Obtiene metadatos de video cacheados.

    Args:
        url: URL del video.

    Returns:
        Diccionario con metadatos, o None si no esta en cache.
    """
    cache_key = _get_cache_key(url, "info")
    r = _get_redis_client()

    if r:
        try:
            data = r.get(cache_key)
            if data:
                return json.loads(data)
        except Exception:
            pass
    else:
        # Fallback a memoria local
        if cache_key in _memory_cache:
            if time.time() < _memory_cache_expiry.get(cache_key, 0):
                return _memory_cache[cache_key]
            else:
                # Expirado
                del _memory_cache[cache_key]
                if cache_key in _memory_cache_expiry:
                    del _memory_cache_expiry[cache_key]

    return None


def set_cached_video_info(url: str, data: dict, ttl: int = 900):
    """
    Guarda metadatos de video en cache.

    Args:
        url: URL del video.
        data: Datos a cachear.
        ttl: Tiempo de vida en segundos (default 15 minutos).
    """
    cache_key = _get_cache_key(url, "info")
    r = _get_redis_client()

    if r:
        try:
            r.setex(cache_key, ttl, json.dumps(data, default=str))
        except Exception:
            pass
    else:
        # Fallback a memoria local
        _memory_cache[cache_key] = data
        _memory_cache_expiry[cache_key] = time.time() + ttl


def get_cached_download(url: str, quality: str) -> dict:
    """
    Obtiene informacion de descarga cacheadas.

    Args:
        url: URL del video.
        quality: Calidad descargada.

    Returns:
        Diccionario con info de la descarga, o None.
    """
    combined = f"{url}|{quality}"
    cache_key = _get_cache_key(combined, "download")
    r = _get_redis_client()

    if r:
        try:
            data = r.get(cache_key)
            if data:
                return json.loads(data)
        except Exception:
            pass
    else:
        if cache_key in _memory_cache:
            if time.time() < _memory_cache_expiry.get(cache_key, 0):
                return _memory_cache[cache_key]
            else:
                del _memory_cache[cache_key]
                if cache_key in _memory_cache_expiry:
                    del _memory_cache_expiry[cache_key]

    return None


def set_cached_download(url: str, quality: str, data: dict, ttl: int = 3600):
    """
    Guarda informacion de descarga cacheadas.

    Args:
        url: URL del video.
        quality: Calidad descargada.
        data: Datos a cachear.
        ttl: Tiempo de vida en segundos (default 1 hora).
    """
    combined = f"{url}|{quality}"
    cache_key = _get_cache_key(combined, "download")
    r = _get_redis_client()

    if r:
        try:
            r.setex(cache_key, ttl, json.dumps(data, default=str))
        except Exception:
            pass
    else:
        _memory_cache[cache_key] = data
        _memory_cache_expiry[cache_key] = time.time() + ttl


def invalidate_cache(url: str):
    """
    Invalida el cache para una URL especifica.

    Args:
        url: URL del video a invalidar.
    """
    cache_key_info = _get_cache_key(url, "info")
    r = _get_redis_client()

    if r:
        try:
            r.delete(cache_key_info)
        except Exception:
            pass
    else:
        if cache_key_info in _memory_cache:
            del _memory_cache[cache_key_info]
            if cache_key_info in _memory_cache_expiry:
                del _memory_cache_expiry[cache_key_info]


def get_cache_stats() -> dict:
    """
    Obtiene estadisticas del cache.

    Returns:
        Diccionario con estadisticas.
    """
    r = _get_redis_client()
    stats = {
        "type": "redis" if r else "memory",
        "memory_items": len(_memory_cache),
        "redis_connected": r is not None,
    }

    if r:
        try:
            stats["redis_info"] = {
                "keys": r.dbsize(),
                "uptime": r.info().get("uptime_in_seconds", 0),
            }
        except Exception:
            stats["redis_info"] = {"error": "No disponible"}

    return stats