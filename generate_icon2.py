from PIL import Image, ImageDraw
import os

def create_padded_icon(size, filename):
    # Cargar el logo original
    original = Image.open('static/Savewave_backup.png' if os.path.exists('static/Savewave_backup.png') else 'static/Savewave.png')
    
    # Hacer backup si no existe
    if not os.path.exists('static/Savewave_backup.png') and filename == 'icon-512.png':
        original.save('static/Savewave_backup.png')
        
    # Crear fondo cuadrado oscuro
    img = Image.new('RGBA', (size, size), (24, 24, 42, 255)) # Color oscuro de fondo
    
    # Calcular nueva escala manteniendo la proporcion
    # Queremos que el logo ocupe el 80% del ancho
    target_width = int(size * 0.8)
    aspect_ratio = original.width / original.height
    target_height = int(target_width / aspect_ratio)
    
    # Redimensionar el logo original
    resized_logo = original.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    # Calcular posicion para centrar
    x = (size - target_width) // 2
    y = (size - target_height) // 2
    
    # Pegar el logo en el centro
    img.paste(resized_logo, (x, y), resized_logo if resized_logo.mode == 'RGBA' else None)
    
    # Guardar
    path = os.path.join('static', filename)
    img.save(path)
    print(f"Creado {path} ({size}x{size})")

if __name__ == "__main__":
    create_padded_icon(192, 'icon-192.png')
    create_padded_icon(512, 'icon-512.png')
    create_padded_icon(32, 'favicon.png')
