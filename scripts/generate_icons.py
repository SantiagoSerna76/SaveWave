"""
Genera iconos Android desde SaveWave.png preservando transparencia
"""
import os
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "static", "Savewave.png")
OUT = os.path.join(BASE, "savewave-app", "android", "app", "src", "main", "res")

ICONS = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

def prepare_image(img, target_size):
    """Convierte a RGBA, escala manteniendo aspecto, centra en canvas cuadrado"""
    # Convertir a RGBA preservando transparencia
    if img.mode == 'P':
        img = img.convert('RGBA' if 'transparency' in img.info else 'RGB')
    elif img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Calcular escalado manteniendo aspecto
    w, h = img.size
    # Usar el lado más corto como referencia para que quepa completo
    scale = (target_size * 0.75) / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    
    # Crear canvas cuadrado transparente
    canvas = Image.new('RGBA', (target_size, target_size), (0, 0, 0, 0))
    
    # Centrar
    x = (target_size - new_w) // 2
    y = (target_size - new_h) // 2
    canvas.paste(resized, (x, y), resized)
    
    return canvas

img = Image.open(SRC)
print(f"Imagen original: {img.size}, mode: {img.mode}")

for folder, size in ICONS.items():
    out_dir = os.path.join(OUT, folder)
    os.makedirs(out_dir, exist_ok=True)
    
    icon = prepare_image(img, size)
    
    # Guardar como PNG (preserva transparencia)
    icon.save(os.path.join(out_dir, "ic_launcher.png"), "PNG")
    icon.save(os.path.join(out_dir, "ic_launcher_round.png"), "PNG")
    
    # Foreground (mismo icono con fondo transparente)
    icon.save(os.path.join(out_dir, "ic_launcher_foreground.png"), "PNG")
    
    # Background sólido oscuro
    bg = Image.new('RGBA', (size, size), (17, 17, 27, 255))
    bg.save(os.path.join(out_dir, "ic_launcher_background.png"), "PNG")
    
    print(f"  ✓ {folder}: {size}x{size}")

print("\n✅ Iconos generados correctamente (transparencia preservada)")