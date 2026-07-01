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
import re
import time
import shutil
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


def _get_ydl_opts(extra_opts: dict = None) -> dict:
    """
    Construye las opciones base para yt-dlp.
    Usa player_client android para evitar bloqueos de YouTube sin necesidad de cookies.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "noplaylist": True,
        # Usar android como player client evita muchos bloqueos de YouTube
        # sin requerir cookies del navegador
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }

    if extra_opts:
        opts.update(extra_opts)

    return opts


def get_video_info(url: str) -> dict:
    """
    Obtiene metadatos del video sin descargarlo.

    Args:
        url: URL del video.

    Returns:
        Diccionario con: title, duration, platform, thumbnail, available_qualities.
    """
    ydl_opts = _get_ydl_opts({
        "extract_flat": "in_playlist",
        "noplaylist": False,
    })

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
                            item_url = url # Fallback
                            
                    playlist_items.append({
                        "title": entry.get("title", "Sin título"),
                        "duration": entry.get("duration", 0),
                        "url": item_url,
                        "thumbnail": entry.get("thumbnail") or info.get("thumbnail", ""),
                        "platform": platform
                    })
                    
                return {
                    "is_playlist": True,
                    "title": info.get("title", "Lista de reproducción"),
                    "platform": platform,
                    "items": playlist_items
                }

            # Flujo normal para un solo video
            available_qualities = set()
            if "formats" in info:
                for fmt in info["formats"]:
                    height = fmt.get("height")
                    if height:
                        available_qualities.add(f"{height}p")

            # Ordenar calidades de menor a mayor
            sorted_qualities = sorted(
                available_qualities,
                key=lambda q: int(q.replace("p", "")),
            )

            return {
                "is_playlist": False,
                "title": info.get("title", "Sin título"),
                "duration": info.get("duration", 0),  # En segundos
                "platform": detect_platform(url),
                "thumbnail": info.get("thumbnail", ""),
                "available_qualities": sorted_qualities if sorted_qualities else ["720p"],
                "uploader": info.get("uploader", "Desconocido"),
                "view_count": info.get("view_count", 0),
            }

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

    timestamp = int(time.time())
    output_template = os.path.join(output_path, f"audio_{timestamp}_%(title)s.%(ext)s")

    # Formato: extraer mejor audio y convertirlo a mp3
    format_spec = "bestaudio[abr<=128]/bestaudio" if quality == "128" else "bestaudio"

    ydl_opts = _get_ydl_opts({
        "format": format_spec,
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,
        }],
        "progress_hooks": [_progress_hook],
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Buscar el archivo .mp3 generado
            downloaded_file = _find_downloaded_file(output_path, timestamp)
            # Si no encuentra con el timestamp, buscar el .mp3 mas reciente
            if not downloaded_file:
                downloaded_file = _find_audio_file(output_path, timestamp)

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

    # Generar nombre de archivo unico con timestamp
    timestamp = int(time.time())
    output_template = os.path.join(output_path, f"video_{timestamp}_%(title)s.%(ext)s")

    # Mapear calidad al formato de yt-dlp
    format_spec = QUALITY_MAP.get(quality, "bv*[height<=720]+ba/b[height<=720]")

    # Opciones de yt-dlp
    ydl_opts = _get_ydl_opts({
        "format": format_spec,
        "outtmpl": output_template,
        "progress_hooks": [_progress_hook],  # Para seguimiento de progreso
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Buscar el archivo descargado
            downloaded_file = _find_downloaded_file(output_path, timestamp)

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


def _find_audio_file(download_folder: str, timestamp: int) -> str:
    """Busca el archivo .mp3 generado por la conversion de audio."""
    for filename in os.listdir(download_folder):
        if filename.endswith(".mp3") and filename.startswith("audio_"):
            return os.path.join(download_folder, filename)
    # Si no encuentra por prefix, buscar cualquier mp3 recien creado
    mp3_files = [f for f in os.listdir(download_folder) if f.endswith(".mp3")]
    if mp3_files:
        return os.path.join(download_folder, max(mp3_files, key=lambda f: os.path.getmtime(os.path.join(download_folder, f))))
    return None


def _find_downloaded_file(download_folder: str, timestamp: int) -> str:
    """
    Busca el archivo descargado mas reciente que coincida con el timestamp.

    Args:
        download_folder: Carpeta donde se busco.
        timestamp: Timestamp usado en el nombre del archivo.

    Returns:
        Ruta completa del archivo encontrado, o None si no se encuentra.
    """
    prefix = f"video_{timestamp}_"
    for filename in os.listdir(download_folder):
        if filename.startswith(prefix):
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