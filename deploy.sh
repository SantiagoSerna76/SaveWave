#!/bin/bash
# ============================================================
# SCRIPT DE DESPLIEGUE - SaveWave en DigitalOcean VPS
# ============================================================
# Ejecutar en el VPS como root:
#   ssh root@159.223.178.155
#   curl -sL https://raw.githubusercontent.com/SantiagoSerna76/SaveWave/main/deploy.sh | bash
#
# O subir este archivo y ejecutar:
#   chmod +x deploy.sh && ./deploy.sh
# ============================================================

set -e  # Detener si hay error

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Desplegando SaveWave en VPS${NC}"
echo -e "${GREEN}========================================${NC}"

# ============================================================
# 1. ACTUALIZAR SISTEMA E INSTalar DEPENDENCIAS
# ============================================================
echo -e "${YELLOW}[1/8] Actualizando sistema...${NC}"
apt update && apt upgrade -y

echo -e "${YELLOW}[2/8] Instalando Python, MySQL, Nginx, Redis...${NC}"
apt install -y python3 python3-pip python3-venv mysql-server nginx redis-server git curl

# ============================================================
# 2. CONFIGURAR MYSQL
# ============================================================
echo -e "${YELLOW}[3/8] Configurando MySQL...${NC}"

# Iniciar MySQL
systemctl start mysql
systemctl enable mysql

# Crear base de datos y usuario
DB_PASSWORD="savewave_$(openssl rand -hex 8)"

mysql <<EOF
CREATE DATABASE IF NOT EXISTS savewave CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'savewave'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON savewave.* TO 'savewave'@'localhost';
FLUSH PRIVILEGES;
EOF

echo -e "${GREEN}   Base de datos 'savewave' creada${NC}"
echo -e "${GREEN}   Usuario: savewave | Password: ${DB_PASSWORD}${NC}"

# ============================================================
# 3. CLONAR REPOSITORIO
# ============================================================
echo -e "${YELLOW}[4/8] Clonando repositorio...${NC}"
cd /opt
git clone https://github.com/SantiagoSerna76/SaveWave.git
cd SaveWave

# ============================================================
# 4. CONFIGURAR VARIABLES DE ENTORNO
# ============================================================
echo -e "${YELLOW}[5/8] Configurando .env...${NC}"

# Generar claves secretas
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)

cat > /opt/SaveWave/.env <<EOF
# SaveWave - Variables de entorno (produccion)
SECRET_KEY=${SECRET_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}
JWT_ACCESS_TOKEN_EXPIRES=3600
DATABASE_URL=mysql+pymysql://savewave:${DB_PASSWORD}@localhost:3306/savewave
STRIPE_PUBLIC_KEY=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRO_PRICE_ID=
STRIPE_PREMIUM_PRICE_ID=
REDIS_URL=redis://localhost:6379/0
ADSENSE_CLIENT_ID=
RATELIMIT_DEFAULT=200 per minute
RATELIMIT_STORAGE_URL=memory://
BASE_URL=http://159.223.178.155
EOF

echo -e "${GREEN}   .env creado con claves seguras${NC}"

# ============================================================
# 5. IMPORTAR ESQUEMA DE BASE DE DATOS
# ============================================================
echo -e "${YELLOW}[6/8] Importando esquema de base de datos...${NC}"
mysql -u savewave -p${DB_PASSWORD} savewave < /opt/SaveWave/database.sql 2>/dev/null || echo -e "${YELLOW}   Esquema ya importado o ignorado${NC}"

# ============================================================
# 6. INSTALAR DEPENDENCIAS PYTHON
# ============================================================
echo -e "${YELLOW}[7/8] Instalando dependencias Python...${NC}"
cd /opt/SaveWave
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn pymysql gevent

echo -e "${GREEN}   Dependencias instaladas${NC}"

# ============================================================
# 7. CREAR SERVICIO SYSTEMD
# ============================================================
echo -e "${YELLOW}[8/8] Creando servicio systemd...${NC}"

cat > /etc/systemd/system/savewave.service <<EOF
[Unit]
Description=SaveWave - Video Downloader
After=network.target mysql.service redis.service
Wants=mysql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/SaveWave
Environment=PATH=/opt/SaveWave/venv/bin:/usr/bin
ExecStart=/opt/SaveWave/venv/bin/gunicorn wsgi:app \\
    --workers 4 \\
    --worker-class gevent \\
    --bind 0.0.0.0:5000 \\
    --timeout 120 \\
    --access-logfile /var/log/savewave/access.log \\
    --error-logfile /var/log/savewave/error.log \\
    --log-level info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Crear carpeta de logs
mkdir -p /var/log/savewave

# Recargar systemd e iniciar servicio
systemctl daemon-reload
systemctl enable savewave
systemctl start savewave

echo -e "${GREEN}   Servicio savewave creado e iniciado${NC}"

# ============================================================
# 8. CONFIGURAR NGINX
# ============================================================
echo -e "${YELLOW}[8/8] Configurando Nginx como proxy...${NC}"

cat > /etc/nginx/sites-available/savewave <<EOF
server {
    listen 80;
    server_name 159.223.178.155;

    # Logs
    access_log /var/log/nginx/savewave_access.log;
    error_log /var/log/nginx/savewave_error.log;

    # Tamano maximo de subida (para descargas grandes)
    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    # Archivos estaticos (servir directamente, sin pasar por Flask)
    location /static/ {
        alias /opt/SaveWave/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /downloads/ {
        alias /opt/SaveWave/downloads/;
        expires 1h;
        add_header Cache-Control "private";
    }
}
EOF

# Habilitar sitio
ln -sf /etc/nginx/sites-available/savewave /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Probar configuracion
nginx -t

# Reiniciar Nginx
systemctl restart nginx

# ============================================================
# 9. LIMPIEZA Y RESUMEN
# ============================================================
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   DESPLIEGUE COMPLETADO!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  IP del servidor: ${GREEN}http://159.223.178.155${NC}"
echo ""
echo -e "  Base de datos:"
echo -e "    Host: localhost"
echo -e "    Puerto: 3306"
echo -e "    Base de datos: savewave"
echo -e "    Usuario: savewave"
echo -e "    Password: ${YELLOW}${DB_PASSWORD}${NC}"
echo ""
echo -e "  Comandos utiles:"
echo -e "    Ver logs: ${YELLOW}journalctl -u savewave -f${NC}"
echo -e "    Reiniciar app: ${YELLOW}systemctl restart savewave${NC}"
echo -e "    Ver estado: ${YELLOW}systemctl status savewave${NC}"
echo -e "    Actualizar codigo: ${YELLOW}cd /opt/SaveWave && git pull && systemctl restart savewave${NC}"
echo ""

# Verificar que todo este corriendo
echo -e "${GREEN}Verificando servicios...${NC}"
systemctl status savewave --no-pager | head -5
systemctl status nginx --no-pager | head -3
systemctl status mysql --no-pager | head -3