-- ============================================================
-- BASE DE DATOS: DescargarVideo
-- ============================================================
-- Esquema completo para MySQL.
-- Crea la base de datos y todas las tablas necesarias.
-- ============================================================

CREATE DATABASE IF NOT EXISTS descargarvideo
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE descargarvideo;

-- ============================================================
-- TABLA: users (Usuarios registrados)
-- ============================================================
-- Almacena la informacion basica de cada usuario.
-- La contrasena se guarda hasheada (nunca en texto plano).
CREATE TABLE IF NOT EXISTS users (
    id              INT             AUTO_INCREMENT  PRIMARY KEY,
    username        VARCHAR(80)     NOT NULL,
    email           VARCHAR(120)    NOT NULL,
    password_hash   VARCHAR(256)    NOT NULL,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    is_active       TINYINT(1)      DEFAULT 1,

    -- Restricciones
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email),

    -- Indices para busquedas rapidas
    INDEX idx_users_username (username),
    INDEX idx_users_email    (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLA: subscriptions (Suscripciones de usuarios)
-- ============================================================
-- Cada usuario tiene UNA suscripcion activa.
-- Por defecto es 'free' al registrarse.
-- Los planes de pago tienen fecha de expiracion.
CREATE TABLE IF NOT EXISTS subscriptions (
    id                      INT             AUTO_INCREMENT  PRIMARY KEY,
    user_id                 INT             NOT NULL,
    plan                    ENUM('free', 'pro', 'premium') NOT NULL DEFAULT 'free',
    stripe_subscription_id  VARCHAR(100)    DEFAULT NULL,
    started_at              DATETIME        DEFAULT CURRENT_TIMESTAMP,
    expires_at              DATETIME        DEFAULT NULL,
    is_active               TINYINT(1)      DEFAULT 1,

    -- Restricciones
    CONSTRAINT uq_subscriptions_user_id UNIQUE (user_id),
    CONSTRAINT fk_subscriptions_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,

    -- Indices
    INDEX idx_subscriptions_plan (plan),
    INDEX idx_subscriptions_stripe (stripe_subscription_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLA: downloads (Historial de descargas)
-- ============================================================
-- Registra cada descarga realizada para controlar limites diarios
-- y mostrar el historial al usuario.
CREATE TABLE IF NOT EXISTS downloads (
    id              INT             AUTO_INCREMENT  PRIMARY KEY,
    user_id         INT             DEFAULT NULL,   -- NULL = usuario anonimo
    url             VARCHAR(500)    NOT NULL,
    platform        VARCHAR(20)     NOT NULL,       -- youtube, instagram, tiktok
    quality         VARCHAR(10)     NOT NULL,       -- 720p, 1080p, 2160p
    file_size       INT             DEFAULT NULL,   -- Tamanio en bytes
    file_path       VARCHAR(500)    DEFAULT NULL,
    status          ENUM('pending', 'downloading', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    error_message   TEXT            DEFAULT NULL,
    ip_address      VARCHAR(45)     DEFAULT NULL,
    created_at      DATETIME        DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME        DEFAULT NULL,

    -- Restricciones
    CONSTRAINT fk_downloads_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE SET NULL,

    -- Indices
    INDEX idx_downloads_user    (user_id),
    INDEX idx_downloads_status  (status),
    INDEX idx_downloads_date    (created_at),
    INDEX idx_downloads_user_date (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- VISTA: v_user_stats (Estadisticas de uso)
-- ============================================================
-- Muestra para cada usuario cuantas descargas lleva hoy
-- y su plan actual. Util para el dashboard.
CREATE OR REPLACE VIEW v_user_stats AS
SELECT
    u.id,
    u.username,
    u.email,
    s.plan,
    CASE
        WHEN s.expires_at IS NULL THEN -1
        WHEN s.expires_at > NOW() THEN DATEDIFF(s.expires_at, NOW())
        ELSE 0
    END AS days_remaining,
    COUNT(d.id) AS downloads_today
FROM users u
LEFT JOIN subscriptions s ON s.user_id = u.id AND s.is_active = 1
LEFT JOIN downloads d ON d.user_id = u.id
    AND DATE(d.created_at) = CURDATE()
    AND d.status = 'completed'
GROUP BY u.id, u.username, u.email, s.plan, s.expires_at;

-- ============================================================
-- DATOS INICIALES (opcional)
-- ============================================================
-- Insertar un usuario administrador de ejemplo:
-- Usuario: admin
-- Email: admin@descargarvideo.com
-- Password: admin123 (hash generado con werkzeug)
-- 
-- NOTA: El hash de abajo es solo un ejemplo.
-- En produccion, registrar usuarios desde la aplicacion.
-- 
-- INSERT INTO users (username, email, password_hash)
-- VALUES ('admin', 'admin@descargarvideo.com',
--         'pbkdf2:sha256:600000$...');
-- 
-- INSERT INTO subscriptions (user_id, plan)
-- VALUES (1, 'free');