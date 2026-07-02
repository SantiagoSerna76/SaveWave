"""
SISTEMA DE CACHE - SaveWave
============================
Cachea metadatos de videos para evitar consultas repetidas a YouTube.

TRES NIVELES:
  1. Redis (recomendado) — compartido entre todos los workers de Gunicorn
  2. Archivo JSON en disco — fallback compartido cuando no hay Redis
  3. Memoria local — último recurso si no se puede escribir archivo

Estrategia:
  - get_video_info: cache por 15 minutos (TTL=900)
  - Archivos descargados: cache por 1 hora (TTL=3600)
  - Si no hay Redis, usa archivo compartido en disco (funciona con --workers 4)
"""

import hashlib
import json
import os
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

# fcntl solo esta disponible en Linux/Mac (no en Windows)
_HAS_FCNTL = False
if sys.platform != "win32":
    try:
        import fcntl
        _HAS_FCNTL = True
    except ImportError:
        pass

# Cache en memoria (ultimo recurso)
_memory_cache = {}
_memory_cache_expiry = {}

# Ruta del archivo de cache compartido en disco
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache_savewave.json')
CACHE_FILE_LOCK = CACHE_FILE + '.lock'


def _get_cache_key(url: str, prefix: str = "info") -> str:
    """
    Genera una clave unica para cachear basada en la URL.

    Args:
        url: URL del video.
        prefix: Prefijo para distinguir tipos de cache.

    Returns:
        Clave de cache con hash MD5.
    """
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    return f"savewave:{prefix}:{url_hash}"


def _get_redis_client():
    """
    Intenta conectar a Redis probando distintas configuraciones.
    Retorna None si Redis no esta disponible.

    Returns:
        Cliente Redis o None.
    """
    urls_to_try = []

    # Probar desde configuracion
    try:
        from config import Config
        if hasattr(Config, 'CACHE_REDIS_URL') and Config.CACHE_REDIS_URL:
            urls_to_try.append(Config.CACHE_REDIS_URL)
        if hasattr(Config, 'CELERY_BROKER_URL') and Config.CELERY_BROKER_URL:
            urls_to_try.append(Config.CELERY_BROKER_URL)
        if hasattr(Config, 'REDIS_URL') and Config.REDIS_URL:
            urls_to_try.append(Config.REDIS_URL)
    except Exception:
        pass

    # Fallback a URL por defecto
    urls_to_try.append("redis://localhost:6379/0")
    urls_to_try.append("redis://127.0.0.1:6379/0")

    # Eliminar duplicados
    urls_to_try = list(dict.fromkeys(urls_to_try))

    for url in urls_to_try:
        try:
            import redis
            client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
            client.ping()
            return client
        except Exception:
            continue

    return None


def _read_disk_cache() -> dict:
    """
    Lee el archivo de cache compartido en disco.
    Usa lock para evitar problemas con workers simultaneos.

    Returns:
        Diccionario con todos los datos cacheados.
    """
    try:
        os.makedirs(os.path.dirname(CACHE_FILE) or '.', exist_ok=True)
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Limpiar expirados
            now = time.time()
            expired = [k for k, v in data.items() if v.get('_expires', 0) < now]
            for k in expired: del data[k]
            if expired:
                try: _write_disk_cache(data)
                except: pass
            return data
    except Exception:
        pass
    return {}


def _write_disk_cache(data: dict):
    """
    Escribe el archivo de cache compartido en disco.
    Usa lock exclusivo para evitar corrupcion.

    Args:
        data: Diccionario con datos a guardar.
    """
    try:
        os.makedirs(os.path.dirname(CACHE_FILE) or '.', exist_ok=True)
        if _HAS_FCNTL:
            with open(CACHE_FILE_LOCK, 'w') as lf:
                try: fcntl.flock(lf, fcntl.LOCK_EX)
                except Exception: pass
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                try: fcntl.flock(lf, fcntl.LOCK_UN)
                except Exception: pass
        else:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_cached_video_info(url: str) -> dict:
    """
    Obtiene metadatos de video cacheados.
    Busca en: Redis -> Archivo disco -> Memoria local

    Args:
        url: URL del video.

    Returns:
        Diccionario con metadatos, o None si no esta en cache.
    """
    cache_key = _get_cache_key(url, "info")

    # 1. Intentar Redis (compartido entre workers)
    r = _get_redis_client()
    if r:
        try:
            data = r.get(cache_key)
            if data:
                return json.loads(data)
        except Exception:
            pass

    # 2. Intentar archivo en disco (compartido entre workers)
    disk_cache = _read_disk_cache()
    if cache_key in disk_cache:
        entry = disk_cache[cache_key]
        if time.time() < entry.get('_expires', 0):
            return entry.get('data')
        else:
            # Expirado, eliminar
            del disk_cache[cache_key]
            _write_disk_cache(disk_cache)

    # 3. Fallback a memoria local
    if cache_key in _memory_cache:
        if time.time() < _memory_cache_expiry.get(cache_key, 0):
            return _memory_cache[cache_key]
        else:
            del _memory_cache[cache_key]
            if cache_key in _memory_cache_expiry:
                del _memory_cache_expiry[cache_key]

    return None


def set_cached_video_info(url: str, data: dict, ttl: int = 900):
    """
    Guarda metadatos de video en cache.
    Guarda en: Redis + Archivo disco + Memoria local

    Args:
        url: URL del video.
        data: Datos a cachear.
        ttl: Tiempo de vida en segundos (default 15 minutos).
    """
    cache_key = _get_cache_key(url, "info")
    expires_at = time.time() + ttl

    # Preparar entrada con expiracion
    entry = {'data': data, '_expires': expires_at}

    # 1. Guardar en Redis
    r = _get_redis_client()
    if r:
        try:
            r.setex(cache_key, ttl, json.dumps(data, default=str))
        except Exception:
            pass

    # 2. Guardar en archivo disco
    try:
        disk_cache = _read_disk_cache()
        disk_cache[cache_key] = entry
        # Limitar tamano del archivo a 1000 entradas
        if len(disk_cache) > 1000:
            # Eliminar las mas viejas
            sorted_keys = sorted(disk_cache.keys(),
                                 key=lambda k: disk_cache[k].get('_expires', 0))
            for old_key in sorted_keys[:-1000]:
                del disk_cache[old_key]
        _write_disk_cache(disk_cache)
    except Exception:
        pass

    # 3. Guardar en memoria local
    _memory_cache[cache_key] = entry
    _memory_cache_expiry[cache_key] = expires_at


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

    # 1. Redis
    r = _get_redis_client()
    if r:
        try:
            data = r.get(cache_key)
            if data:
                return json.loads(data)
        except Exception:
            pass

    # 2. Archivo disco
    disk_cache = _read_disk_cache()
    if cache_key in disk_cache:
        entry = disk_cache[cache_key]
        if time.time() < entry.get('_expires', 0):
            return entry.get('data')

    # 3. Memoria local
    if cache_key in _memory_cache:
        if time.time() < _memory_cache_expiry.get(cache_key, 0):
            return _memory_cache[cache_key].get('data')

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
    expires_at = time.time() + ttl
    entry = {'data': data, '_expires': expires_at}

    # Redis
    r = _get_redis_client()
    if r:
        try:
            r.setex(cache_key, ttl, json.dumps(data, default=str))
        except Exception:
            pass

    # Archivo disco
    try:
        disk_cache = _read_disk_cache()
        disk_cache[cache_key] = entry
        if len(disk_cache) > 1000:
            sorted_keys = sorted(disk_cache.keys(),
                                 key=lambda k: disk_cache[k].get('_expires', 0))
            for old_key in sorted_keys[:-1000]:
                del disk_cache[old_key]
        _write_disk_cache(disk_cache)
    except Exception:
        pass

    # Memoria local
    _memory_cache[cache_key] = entry
    _memory_cache_expiry[cache_key] = expires_at


def invalidate_cache(url: str):
    """
    Invalida el cache para una URL especifica.

    Args:
        url: URL del video a invalidar.
    """
    cache_key_info = _get_cache_key(url, "info")

    # Redis
    r = _get_redis_client()
    if r:
        try:
            r.delete(cache_key_info)
        except Exception:
            pass

    # Archivo disco
    try:
        disk_cache = _read_disk_cache()
        if cache_key_info in disk_cache:
            del disk_cache[cache_key_info]
            _write_disk_cache(disk_cache)
    except Exception:
        pass

    # Memoria local
    if cache_key_info in _memory_cache:
        del _memory_cache[cache_key_info]
        if cache_key_info in _memory_cache_expiry:
            del _memory_cache_expiry[cache_key_info]


def get_cache_stats() -> dict:
    """
    Obtiene estadisticas del cache.

    Returns:
        Diccionario con estadisticas del cache.
    """
    r = _get_redis_client()

    stats = {
        "redis_connected": r is not None,
        "memory_items": len(_memory_cache),
    }

    if r:
        try:
            info = r.info()
            stats["type"] = "redis"
            stats["redis_info"] = {
                "keys": r.dbsize(),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "memory_bytes": info.get("used_memory", 0),
                "version": info.get("redis_version", ""),
            }
        except Exception:
            stats["type"] = "redis (error)"
            stats["redis_info"] = {"error": "No disponible"}
    else:
        # Verificar si el archivo de disco funciona
        try:
            disk_cache = _read_disk_cache()
            stats["type"] = "disk_file"
            stats["disk_items"] = len(disk_cache)
            stats["disk_file"] = CACHE_FILE
            stats["disk_file_size"] = os.path.getsize(CACHE_FILE) if os.path.exists(CACHE_FILE) else 0
        except Exception:
            stats["type"] = "memory_only"
            stats["disk_items"] = 0

    return stats