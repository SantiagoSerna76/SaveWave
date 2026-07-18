from PIL import Image

def create_solid_icons(source_path):
    print(f"Abriendo {source_path}...")
    img = Image.open(source_path).convert("RGBA")
    
    # 1. Recortar al cuadrado central
    width, height = img.size
    size = min(width, height)
    left = (width - size) / 2
    top = (height - size) / 2
    right = (width + size) / 2
    bottom = (height + size) / 2
    img_square = img.crop((left, top, right, bottom))
    
    # 2. Crear un fondo solido con el color del tema de la app (#1e1e2e)
    bg_color = (30, 30, 46, 255) # Equivalente a #1e1e2e
    solid_bg = Image.new("RGBA", (size, size), bg_color)
    
    # 3. Pegar el logo (que tiene partes transparentes) sobre el fondo solido
    solid_bg.paste(img_square, (0, 0), img_square)
    
    # Generar favicon (32x32)
    favicon = solid_bg.resize((32, 32), Image.Resampling.LANCZOS)
    favicon.save('static/favicon.png')
    print("Guardado static/favicon.png")

    # Generar icon-192.png
    icon192 = solid_bg.resize((192, 192), Image.Resampling.LANCZOS)
    icon192.save('static/icon-192.png')
    print("Guardado static/icon-192.png")

    # Generar icon-512.png
    icon512 = solid_bg.resize((512, 512), Image.Resampling.LANCZOS)
    icon512.save('static/icon-512.png')
    print("Guardado static/icon-512.png")
    
    # Generar Savewave.png (para la navbar, podemos dejarlo con fondo solido o transparente)
    # Como la navbar ya es oscura, el fondo solido se vera perfecto y solucionara el bug blanco en otros lados
    icon512.save('static/Savewave.png')
    print("Guardado static/Savewave.png")

if __name__ == '__main__':
    create_solid_icons('static/Savewave_backup.png')
