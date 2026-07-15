from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, filename):
    # Crear imagen con fondo transparente
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Dibujar un rectangulo redondeado con gradiente
    # Como PIL no tiene gradientes nativos faciles, dibujaremos lineas
    # Gradiente de #6366f1 a #8b5cf6
    r1, g1, b1 = 99, 102, 241
    r2, g2, b2 = 139, 92, 246
    
    radius = int(size * 0.22)
    
    for y in range(size):
        ratio = y / size
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))
        
    # Crear mascara para esquinas redondeadas
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (size, size)], radius=radius, fill=255)
    
    # Aplicar mascara al fondo
    img.putalpha(mask)
    
    # Dibujar texto "SW"
    # Intentar usar una fuente del sistema, sino usar default
    try:
        font_size = int(size * 0.5)
        # Windows font path
        font = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", font_size)
    except:
        font = ImageFont.load_default()
        
    text = "SW"
    # Obtener el cuadro del texto para centrarlo
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Ajuste manual para centrar opticamente el texto bold
    x = (size - text_width) / 2
    y = (size - text_height) / 2 - (size * 0.05)
    
    draw.text((x, y), text, fill="white", font=font)
    
    # Guardar
    path = os.path.join('static', filename)
    img.save(path)
    print(f"Creado {path} ({size}x{size})")

if __name__ == "__main__":
    create_icon(192, 'icon-192.png')
    create_icon(512, 'icon-512.png')
    create_icon(32, 'favicon.png')
