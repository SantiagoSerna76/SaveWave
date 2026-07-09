"""
SERVICIO DE DESCARGA DE VIDEOS
===============================
Contiene toda la lógica para descargar videos usando yt-dlp.
Soporta YouTube, Instagram y TikTok.
Funciones:
  - detect_platform(url)       -> Detecta la plataforma del enlace
  - get_video_info(url)        -> Obtiene metadatos del video (título, calidad, etc.)
  - download_video(url, quality, output_path) -> Descarga el video
  - get_available_qualities(url) -> Lista las calidades disponibles
  - cleanup_old_files()        -> Elimina archivos temporales antiguos
"""

import os

# INYECTAR DENO AL PATH:
# Systemd no carga el PATH completo del usuario root. Si yt-dlp no encuentra un motor JS (Deno),
# falla al resolver las firmas de YouTube (sig/n) y devuelve "Requested format is not available".
if "/root/.deno/bin" not in os.environ.get("PATH", ""):
    os.environ["PATH"] = os.environ.get("PATH", "") + ":/root/.deno/bin"

import re
import time
import shutil
import hashlib
import glob
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
import yt_dlp
from config import Config


# -------------------- CONSTANTES --------------------

# Patrones para detectar la plataforma según la URL
# yt-dlp soporta cientos de sitios (Facebook, Twitter, Vimeo, Dailymotion, etc.)
# Estos patrones son solo para reconocimiento rapido en la UI.
# Si no coincide, se usa el extractor de yt-dlp para detectar automaticamente.
PLATFORM_PATTERNS = {
    "youtube": [
        r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/",
    ],
    "instagram": [
        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv|stories)\/",
    ],
    "tiktok": [
        r"(?:https?:\/\/)?(?:www\.)?(?:tiktok\.com|vm\.tiktok\.com)\/",
    ],
    "facebook": [
        r"(?:https?:\/\/)?(?:www\.)?facebook\.com\/",
        r"(?:https?:\/\/)?(?:www\.)?fb\.com\/",
    ],
    "twitter_x": [
        r"(?:https?:\/\/)?(?:www\.)?twitter\.com\/",
        r"(?:https?:\/\/)?(?:www\.)?x\.com\/",
    ],
    "vimeo": [
        r"(?:https?:\/\/)?(?:www\.)?vimeo\.com\/",
    ],
    "dailymotion": [
        r"(?:https?:\/\/)?(?:www\.)?dailymotion\.com\/",
    ],
    "twitch": [
        r"(?:https?:\/\/)?(?:www\.)?twitch\.tv\/",
    ],
    "reddit": [
        r"(?:https?:\/\/)?(?:www\.)?reddit\.com\/",
    ],
    "linkedin": [
        r"(?:https?:\/\/)?(?:www\.)?linkedin\.com\/",
    ],
}

# Mapeo de calidad a formato yt-dlp
# Formato: bv*[height<=X]+ba/b[height<=X]
#   bv*    = best video (con * para que sea opcional si no existe)
#   ba     = best audio
#   /b     = fallback: best overall si no se puede separar
# Esto funciona con YouTube, Instagram y TikTok.
QUALITY_MAP = {
    "144p": "bv*[height<=144]+ba/b[height<=144]/best/bv+ba",
    "360p": "bv*[height<=360]+ba/b[height<=360]/best/bv+ba",
    "480p": "bv*[height<=480]+ba/b[height<=480]/best/bv+ba",
    "720p": "bv*[height<=720]+ba/b[height<=720]/best/bv+ba",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]/best/bv+ba",
    "2160p": "bv*[height<=2160]+ba/b[height<=2160]/best/bv+ba",  # 4K
}


# -------------------- FUNCIONES PÚBLICAS --------------------


def detect_platform(url: str) -> str:
    """
    Detecta de qué plataforma es un enlace.

    Args:
        url: URL del video a analizar.

    Returns:
        Nombre de la plataforma: 'youtube', 'instagram', 'tiktok'.
        Si no se reconoce, lanza ValueError.
    """
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    raise ValueError(f"URL no soportada o plataforma no reconocida: {url}")


def _bgutil_server_running() -> bool:
    """Comprueba si el servidor bgutil HTTP está activo en puerto 4416 (IPv4 o IPv6)."""
    import socket
    for host in ('127.0.0.1', '::1'):
        try:
            family = socket.AF_INET if '.' in host else socket.AF_INET6
            s = socket.socket(family, socket.SOCK_STREAM)
            s.settimeout(0.8)
            s.connect((host, 4416))
            s.close()
            return True
        except Exception:
            pass
    return False


def _get_ydl_opts(extra_opts: dict = None, url: str = None) -> dict:
    """
    Construye las opciones base para yt-dlp.

    Estrategia de velocidad:
    1. Si el servidor bgutil (Deno persistente) está corriendo en :4416 → usarlo (rápido: ~0.5s/canción).
    2. Si no → cold-start de Deno por cada canción (lento: ~7s/canción).

    Args:
        extra_opts: Opciones adicionales para yt-dlp.
        url: URL opcional para aplicar configuraciones específicas por plataforma.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    opts = {
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    # Determinar la plataforma para cargar cookies específicas
    platform = None
    if url:
        try:
            platform = detect_platform(url)
        except ValueError:
            platform = None

    # Buscar archivo de cookies específico según la plataforma.
    if platform == "youtube":
        cookie_candidates = ['www.youtube.com_cookies.txt', 'youtube_cookies.txt']
    elif platform == "instagram":
        cookie_candidates = ['instagram_cookies.txt', 'www.instagram.com_cookies.txt']
    else:
        cookie_candidates = []

    for cookie_name in cookie_candidates:
        cookies_path = os.path.join(base_dir, cookie_name)
        if os.path.exists(cookies_path):
            opts['cookiefile'] = cookies_path
            break

    if platform == "youtube":
        # Dejar que yt-dlp use sus clientes por defecto (mix de web, ios, android).
        # Ya que el usuario subió cookies.txt, esto funcionará de manera 100% estable
        # para todos los videos, sin los cuelgues (hangs) de android_vr puro.
        pass


    # Usar ffmpeg local si existe en la carpeta bin
    bin_dir = os.path.join(base_dir, 'bin')
    if os.path.exists(os.path.join(bin_dir, 'ffmpeg.exe')):
        opts['ffmpeg_location'] = bin_dir

    # Configuraciones específicas por plataforma
    if url:
        try:
            platform = detect_platform(url)
        except ValueError:
            platform = None

        if platform == "instagram":
            from config import Config
            if Config.INSTAGRAM_USERNAME and Config.INSTAGRAM_PASSWORD:
                opts["username"] = Config.INSTAGRAM_USERNAME
                opts["password"] = Config.INSTAGRAM_PASSWORD

    if extra_opts:
        opts.update(extra_opts)
    return opts




def get_video_info(url: str) -> dict:
    """
    Obtiene metadatos del video sin descargarlo.
    Usa cache para evitar consultas repetidas a YouTube (TTL 15 min).

    Args:
        url: URL del video.

    Returns:
        Diccionario con: title, duration, platform, thumbnail, available_qualities.
    """
    from cache import get_cached_video_info, set_cached_video_info

    # Intentar obtener del cache primero
    cached = get_cached_video_info(url)
    if cached:
        return cached

    ydl_opts = _get_ydl_opts({
        "noplaylist": False,
    }, url)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Verificar si es una playlist
            if "entries" in info:
                playlist_items = []
                platform = detect_platform(url)
                for entry in info["entries"]:
                    if not entry:
                        continue

                    item_url = entry.get("url", "")
                    if not item_url and entry.get("id"):
                        if platform == "youtube":
                            item_url = f"https://www.youtube.com/watch?v={entry['id']}"
                        else:
                            item_url = url

                    playlist_items.append({
                        "title": entry.get("title", "Sin título"),
                        "duration": entry.get("duration", 0),
                        "url": item_url,
                        "thumbnail": entry.get("thumbnail") or info.get("thumbnail", ""),
                        "platform": platform
                    })

                result = {
                    "is_playlist": True,
                    "title": info.get("title", "Lista de reproducción"),
                    "platform": platform,
                    "items": playlist_items
                }
                set_cached_video_info(url, result, ttl=300)
                return result

            # Flujo normal para un solo video
            # Obtener calidades desde los formatos
            available_qualities = set()
            if "formats" in info:
                for fmt in info["formats"]:
                    height = fmt.get("height")
                    if height:
                        available_qualities.add(f"{height}p")

            # Si no hay formatos con altura, agregar calidades comunes
            if not available_qualities:
                available_qualities = {"360p", "720p", "1080p"}

            sorted_qualities = sorted(
                available_qualities,
                key=lambda q: int(q.replace("p", "")),
            )

            result = {
                "is_playlist": False,
                "title": info.get("title", "Sin título"),
                "duration": info.get("duration", 0),
                "platform": detect_platform(url),
                "thumbnail": info.get("thumbnail", ""),
                "available_qualities": sorted_qualities if sorted_qualities else ["720p"],
                "uploader": info.get("uploader", "Desconocido"),
                "view_count": info.get("view_count", 0),
            }

            set_cached_video_info(url, result, ttl=900)
            return result

    except Exception as e:
        raise RuntimeError(f"Error al obtener informacion del video: {str(e)}")


def download_audio(url: str, quality: str = "128", output_path: str = None) -> dict:
    """
    Descarga solo el audio de un video y lo convierte a MP3.

    Args:
        url: URL del video.
        quality: Calidad del audio: '128' para 128kbps, '320' para 320kbps.
        output_path: Ruta donde guardar el archivo.

    Returns:
        Diccionario con resultado de la descarga.
    """
    if output_path is None:
        output_path = Config.DOWNLOAD_FOLDER

    os.makedirs(output_path, exist_ok=True)

    url_hash = hashlib.md5(url.encode()).hexdigest()

    # Fast path: check if we already downloaded this exact audio
    existing_files = glob.glob(os.path.join(output_path, f"audio_{url_hash}.mp3"))
    if existing_files:
        downloaded_file = existing_files[0]
        file_size = os.path.getsize(downloaded_file)
        if file_size < 100 * 1024:
            # File is corrupt or empty (under 100KB), delete it to force re-download
            os.remove(downloaded_file)
        else:
            return {
                "success": True,
                "file_path": downloaded_file,
                "file_size": file_size,
                "file_size_formatted": _format_file_size(file_size),
                "title": "Audio", # No longer used by frontend
                "platform": detect_platform(url),
                "duration": 0,
                "filename": os.path.basename(downloaded_file),
            }

    output_template = os.path.join(output_path, f"audio_{url_hash}.%(ext)s")

    # Formato: priorizar opus/m4a nativos para evitar re-encoding lento.
    # Solo convertir a mp3 al final con FFmpeg (más rápido que re-codificar desde cero).
    if quality == "128":
        format_spec = "bestaudio[abr<=128][ext=m4a]/bestaudio[abr<=128][ext=webm]/bestaudio[abr<=128]/bestaudio/best"
    else:
        format_spec = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"

    ydl_opts = _get_ydl_opts({
        "format": format_spec,
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,
        }],
        "progress_hooks": [_progress_hook],
    }, url)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Buscar el archivo .mp3 generado
            downloaded_file = _find_audio_file(output_path, url_hash)

            file_size = os.path.getsize(downloaded_file) if downloaded_file else 0

            return {
                "success": True,
                "file_path": downloaded_file,
                "file_size": file_size,
                "file_size_formatted": _format_file_size(file_size),
                "title": info.get("title", "Sin titulo"),
                "platform": detect_platform(url),
                "duration": info.get("duration", 0),
                "filename": os.path.basename(downloaded_file) if downloaded_file else "desconocido.mp3",
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error al convertir a MP3: {str(e)}",
        }


def get_audio_direct_url(url: str, quality: str = 'best') -> dict:
    """
    Extrae la URL directa del mejor audio disponible SIN descargar nada.
    El servidor solo hace la negociación (<1 segundo) y devuelve la URL.
    Luego el móvil/PC descarga DIRECTAMENTE desde los servidores de YouTube
    usando su propia CPU y ancho de banda. ¡Esto es lo que hace rápida la extensión de Chrome!

    Args:
        url: URL del video.

    Returns:
        Diccionario con: success, direct_url, title, platform, format, thumbnail, duration.
    """
    # Seleccionar calidad según el parámetro:
    # - "low": archivo más pequeño posible para descarga offline rápida (~1.5MB vs ~5MB)
    # - "best": mejor calidad para reproducción en streaming
    # Siempre preferir m4a (AAC) sobre webm (Opus) para compatibilidad con iOS/Safari.
    if quality == "low":
        format_spec = "worstaudio[ext=m4a]/worstaudio/best"
    else:
        format_spec = "bestaudio[ext=m4a]/bestaudio/best"

    ydl_opts = _get_ydl_opts({
        "noplaylist": True,
        "format": format_spec,
    }, url)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # yt-dlp con format selector resuelve el mejor formato directamente
            # La URL está en info['url'] cuando format fue seleccionado
            best_audio_url = info.get("url")
            best_format = info.get("ext", "m4a")

            # Si no vino url directa, buscar en formats
            if not best_audio_url and "formats" in info:
                # Preferir audio puro m4a > webm > cualquier cosa con audio
                candidates = [f for f in info["formats"] if f.get("url") and f.get("acodec") not in (None, "none")]
                # Ordenar: audio-only m4a primero, luego webm, luego mixtos
                def fmt_score(f):
                    has_video = f.get("vcodec") not in (None, "none")
                    ext = f.get("ext", "")
                    abr = f.get("abr") or 0
                    if not has_video and ext == "m4a": return (3, abr)
                    if not has_video and ext == "webm": return (2, abr)
                    if not has_video: return (1, abr)
                    return (0, abr)
                candidates.sort(key=fmt_score, reverse=True)
                if candidates:
                    best_audio_url = candidates[0]["url"]
                    best_format = candidates[0].get("ext", "m4a")

            if not best_audio_url:
                return {
                    "success": False,
                    "error": "No se pudo extraer la URL directa del audio.",
                }

            return {
                "success": True,
                "direct_url": best_audio_url,
                "title": info.get("title", "Sin titulo"),
                "platform": detect_platform(url),
                "format": best_format,
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0),
                "http_headers": info.get("http_headers", {})
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error al extraer URL directa: {str(e)}",
        }


def download_audio_native(url: str, output_path: str = None) -> dict:
    """
    Descarga audio en formato nativo (M4A/Opus) SIN reconversión a MP3.
    Esto es MUCHO más rápido porque evita FFmpeg por completo.
    El navegador/móvil reproduce M4A nativamente.

    Args:
        url: URL del video.
        output_path: Ruta donde guardar el archivo.

    Returns:
        Diccionario con resultado de la descarga.
    """
    if output_path is None:
        output_path = Config.DOWNLOAD_FOLDER

    os.makedirs(output_path, exist_ok=True)

    url_hash = hashlib.md5(url.encode()).hexdigest()

    # Fast path: check if we already downloaded this exact audio natively
    existing_files = glob.glob(os.path.join(output_path, f"native_{url_hash}.*"))
    if existing_files:
        downloaded_file = existing_files[0]
        file_size = os.path.getsize(downloaded_file)
        if file_size < 50 * 1024:
            os.remove(downloaded_file)
        else:
            ext = os.path.splitext(downloaded_file)[1].lstrip('.')
            return {
                "success": True,
                "file_path": downloaded_file,
                "file_size": file_size,
                "file_size_formatted": _format_file_size(file_size),
                "title": "Audio",
                "platform": detect_platform(url),
                "duration": 0,
                "filename": os.path.basename(downloaded_file),
                "format": ext,
            }

    output_template = os.path.join(output_path, f"native_{url_hash}.%(ext)s")

    # Descargar el mejor audio disponible SIN post-procesamiento (sin FFmpeg)
    format_spec = "bestaudio/best"

    ydl_opts = _get_ydl_opts({
        "noplaylist": True,
        "format": format_spec,
        "outtmpl": output_template,
        "concurrent_fragment_downloads": 4,
        "retries": 3,
        "progress_hooks": [_progress_hook],
    }, url)
    # Añadir ffmpeg local si existe
    bin_dir2 = os.path.join(base_dir2, 'bin')
    if os.path.exists(os.path.join(bin_dir2, 'ffmpeg.exe')):
        ydl_opts['ffmpeg_location'] = bin_dir2

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Buscar el archivo descargado (puede ser .m4a, .webm, etc.)
            downloaded_file = _find_native_file(output_path, url_hash)

            if not downloaded_file:
                return {
                    "success": False,
                    "error": "No se pudo encontrar el archivo de audio descargado.",
                }

            file_size = os.path.getsize(downloaded_file)
            ext = os.path.splitext(downloaded_file)[1].lstrip('.')

            return {
                "success": True,
                "file_path": downloaded_file,
                "file_size": file_size,
                "file_size_formatted": _format_file_size(file_size),
                "title": info.get("title", "Sin titulo"),
                "platform": detect_platform(url),
                "duration": info.get("duration", 0),
                "filename": os.path.basename(downloaded_file),
                "format": ext,
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error al descargar audio nativo: {str(e)}",
        }


def download_video(url: str, quality: str = "720p", output_path: str = None) -> dict:
    """
    Descarga un video desde la URL especificada.

    Args:
        url: URL del video a descargar.
        quality: Calidad deseada (ej: '720p', '1080p', '2160p').
        output_path: Ruta donde guardar el archivo. Si es None, usa la carpeta
                     de descargas temporales de la configuracion.

    Returns:
        Diccionario con: file_path, file_size, title, platform, duration.
    """
    # Determinar ruta de salida
    if output_path is None:
        output_path = Config.DOWNLOAD_FOLDER

    # Crear carpeta si no existe
    os.makedirs(output_path, exist_ok=True)

    url_hash = hashlib.md5(f"{url}_{quality}".encode()).hexdigest()

    # Fast path: check if we already downloaded this exact video at this quality
    existing_files = glob.glob(os.path.join(output_path, f"video_{url_hash}_*.*"))
    if existing_files:
        downloaded_file = existing_files[0]
        file_size = os.path.getsize(downloaded_file)
        return {
            "success": True,
            "file_path": downloaded_file,
            "file_size": file_size,
            "file_size_formatted": _format_file_size(file_size),
            "title": os.path.basename(downloaded_file).replace(f"video_{url_hash}_", "").rsplit('.', 1)[0],
            "platform": detect_platform(url),
            "duration": 0,
            "filename": os.path.basename(downloaded_file),
        }

    output_template = os.path.join(output_path, f"video_{url_hash}_%(title)s.%(ext)s")

    # Mapear calidad al formato de yt-dlp
    format_spec = QUALITY_MAP.get(quality, "bv*[height<=720]+ba/b[height<=720]")

    # Opciones de yt-dlp
    ydl_opts = _get_ydl_opts({
        "format": format_spec,
        "outtmpl": output_template,
        "progress_hooks": [_progress_hook],  # Para seguimiento de progreso
    }, url)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Buscar el archivo descargado
            downloaded_file = _find_downloaded_file(output_path, url_hash)

            # Obtener tamano del archivo
            file_size = os.path.getsize(downloaded_file) if downloaded_file else 0

            return {
                "success": True,
                "file_path": downloaded_file,
                "file_size": file_size,
                "file_size_formatted": _format_file_size(file_size),
                "title": info.get("title", "Sin titulo"),
                "platform": detect_platform(url),
                "duration": info.get("duration", 0),
                "filename": os.path.basename(downloaded_file) if downloaded_file else "desconocido",
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error al descargar: {str(e)}",
        }


def get_available_qualities(url: str) -> list:
    """
    Obtiene la lista de calidades disponibles para un video.

    Args:
        url: URL del video.

    Returns:
        Lista de strings con calidades (ej: ['144p', '360p', '720p', '1080p']).
    """
    info = get_video_info(url)
    return info.get("available_qualities", ["720p"])


def cleanup_old_files():
    """
    Elimina archivos de descarga temporales que hayan expirado.
    Se ejecuta periodicamente para no acumular archivos en el servidor.
    """
    download_folder = Config.DOWNLOAD_FOLDER
    if not os.path.exists(download_folder):
        return

    now = time.time()
    expiry_seconds = Config.DOWNLOAD_EXPIRY_SECONDS

    for filename in os.listdir(download_folder):
        file_path = os.path.join(download_folder, filename)
        if os.path.isfile(file_path):
            # Si el archivo es mas antiguo que el tiempo de expiracion, lo borra
            file_age = now - os.path.getmtime(file_path)
            if file_age > expiry_seconds:
                try:
                    os.remove(file_path)
                    print(f"[LIMPIEZA] Archivo temporal eliminado: {filename}")
                except Exception as e:
                    print(f"[ERROR] No se pudo eliminar {filename}: {e}")


# -------------------- FUNCIONES PRIVADAS --------------------


def _progress_hook(d):
    """
    Hook de progreso para yt-dlp.
    Se llama durante la descarga para reportar el avance.
    """
    if d["status"] == "downloading":
        # d['_percent_str'] tiene el porcentaje descargado
        percent = d.get("_percent_str", "0%").strip()
        speed = d.get("_speed_str", "?")
        print(f"[DESCARGANDO] {percent} a {speed}")
    elif d["status"] == "finished":
        print("[OK] Descarga completada. Procesando archivo...")


def _find_audio_file(download_folder: str, url_hash: str) -> str:
    """Busca el archivo .mp3 generado por la conversion de audio."""
    prefix = f"audio_{url_hash}_"
    for filename in os.listdir(download_folder):
        if filename.endswith(".mp3") and filename.startswith(prefix):
            return os.path.join(download_folder, filename)
    # Si no encuentra por prefix, buscar cualquier mp3 recien creado
    mp3_files = [f for f in os.listdir(download_folder) if f.endswith(".mp3")]
    if mp3_files:
        return os.path.join(download_folder, max(mp3_files, key=lambda f: os.path.getmtime(os.path.join(download_folder, f))))
    return None


def _find_downloaded_file(download_folder: str, url_hash: str) -> str:
    """
    Busca el archivo descargado mas reciente que coincida con el hash.

    Args:
        download_folder: Carpeta donde se busco.
        url_hash: Hash usado en el nombre del archivo.

    Returns:
        Ruta completa del archivo encontrado, o None si no se encuentra.
    """
    prefix = f"video_{url_hash}_"
    for filename in os.listdir(download_folder):
        if filename.startswith(prefix):
            return os.path.join(download_folder, filename)
    return None


def _find_native_file(download_folder: str, url_hash: str) -> str:
    """Busca el archivo de audio nativo descargado (m4a, webm, etc.) que coincida con el hash."""
    prefix = f"native_{url_hash}."
    for filename in os.listdir(download_folder):
        if filename.startswith(prefix):
            return os.path.join(download_folder, filename)
    # Fallback: buscar cualquier archivo recién creado con el hash
    for filename in os.listdir(download_folder):
        if url_hash in filename and not filename.endswith('.part'):
            return os.path.join(download_folder, filename)
    return None


def _format_file_size(size_bytes: int) -> str:
    """
    Convierte bytes a formato legible (KB, MB, GB).

    Args:
        size_bytes: Tamano en bytes.

    Returns:
        String formateado (ej: '15.2 MB').
    """
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {size_names[i]}"