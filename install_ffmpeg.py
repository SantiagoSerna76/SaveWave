import urllib.request
import zipfile
import os
import sys

def install_ffmpeg():
    bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin')
    os.makedirs(bin_dir, exist_ok=True)
    
    ffmpeg_path = os.path.join(bin_dir, 'ffmpeg.exe')
    ffprobe_path = os.path.join(bin_dir, 'ffprobe.exe')
    
    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
        print("FFmpeg y FFprobe ya estan instalados en la carpeta bin.")
        return
        
    print("Descargando FFmpeg (esto puede tardar un minuto)...")
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = os.path.join(bin_dir, "ffmpeg.zip")
    
    try:
        urllib.request.urlretrieve(url, zip_path)
        print("Descarga completa. Extrayendo...")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.endswith('ffmpeg.exe') or member.endswith('ffprobe.exe'):
                    filename = os.path.basename(member)
                    source = zip_ref.open(member)
                    target = open(os.path.join(bin_dir, filename), "wb")
                    with source, target:
                        import shutil
                        shutil.copyfileobj(source, target)
                        
        os.remove(zip_path)
        print("FFmpeg instalado correctamente en:", bin_dir)
    except Exception as e:
        print("Error al instalar FFmpeg:", str(e))
        sys.exit(1)

if __name__ == "__main__":
    install_ffmpeg()
