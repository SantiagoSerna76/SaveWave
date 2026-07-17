from PIL import Image
import os

def create_icons(source_path):
    print(f"Abriendo {source_path}...")
    img = Image.open(source_path).convert("RGBA")
    
    # Hacer la imagen cuadrada si no lo es (anadiendo fondo blanco o transparente)
    # Como es un cubo sobre fondo blanco, vamos a recortar el centro
    width, height = img.size
    size = min(width, height)
    left = (width - size) / 2
    top = (height - size) / 2
    right = (width + size) / 2
    bottom = (height + size) / 2

    # Recortar al cuadrado central
    img_square = img.crop((left, top, right, bottom))
    
    # Generar favicon (32x32)
    favicon = img_square.resize((32, 32), Image.Resampling.LANCZOS)
    favicon.save('static/favicon.png')
    print("Guardado static/favicon.png")

    # Generar icon-192.png
    icon192 = img_square.resize((192, 192), Image.Resampling.LANCZOS)
    icon192.save('static/icon-192.png')
    print("Guardado static/icon-192.png")

    # Generar icon-512.png
    icon512 = img_square.resize((512, 512), Image.Resampling.LANCZOS)
    icon512.save('static/icon-512.png')
    print("Guardado static/icon-512.png")
    
    # Guardar Savewave.png (el principal de la navbar, tal vez un poco mas ancho o simplemente el cuadrado)
    # Lo guardaremos como 512x512 tambien para que se vea nitido en el header
    icon512.save('static/Savewave.png')
    print("Guardado static/Savewave.png")

if __name__ == '__main__':
    create_icons('static/Savewave_backup.png')
