"""
Genera todos los iconos de Android desde SaveWave.png
"""
import os
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "static", "Savewave.png")
OUT = os.path.join(BASE, "savewave-app", "android", "app", "src", "main", "res")

# Tamaños de iconos Android
ICONS = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

# Tamaños del icono de launcher adaptativo
FOREGROUND_SIZE = 108  # tamaño del foreground en dp (72% del adaptive icon)

img = Image.open(SRC)

# Convertir a RGBA
if img.mode != 'RGBA':
    img = img.convert('RGBA')

# Crear icono redondeado cuadrado (como Android requiere)
def make_square_rounded(img, size):
    # Crear lienzo cuadrado
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    
    # Escalar imagen a ocupar ~70% del canvas con padding
    pad = int(size * 0.15)
    inner_size = size - 2 * pad
    resized = img.resize((inner_size, inner_size), Image.LANCZOS)
    
    # Pegar en el centro
    x = (size - inner_size) // 2
    y = (size - inner_size) // 2
    canvas.paste(resized, (x, y), resized if resized.mode == 'RGBA' else None)
    
    return canvas

# Generar iconos para cada densidad
for folder, size in ICONS.items():
    out_dir = os.path.join(OUT, folder)
    os.makedirs(out_dir, exist_ok=True)
    
    icon = make_square_rounded(img, size)
    icon.save(os.path.join(out_dir, "ic_launcher.png"))
    icon.save(os.path.join(out_dir, "ic_launcher_round.png"))
    
    # También generar el foreground para adaptive icon
    foreground = make_square_rounded(img, size)
    foreground.save(os.path.join(out_dir, "ic_launcher_foreground.png"))
    
    # Background: color sólido
    bg = Image.new('RGBA', (size, size), (17, 17, 27, 255))  # #11111b
    bg.save(os.path.join(out_dir, "ic_launcher_background.png"))
    
    print(f"  ✓ {folder}: {size}x{size}")

print("\n✅ Iconos generados correctamente")
print(f"   Origen: {SRC}")
print(f"   Destino: {OUT}")