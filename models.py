"""
MODELOS DE BASE DE DATOS
========================
Define las tablas de la base de datos usando SQLAlchemy.
Relaciones:
  - User 1---N Download (un usuario tiene muchas descargas)
  - User 1---1 Subscription (un usuario tiene una suscripción activa)
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import enum

# Instancia global de SQLAlchemy (se inicializa en app.py)
db = SQLAlchemy()


class PlanType(str, enum.Enum):
    """
    Tipos de plan de suscripción.
    FREE  -> Plan gratuito (con anuncios y límites)
    PRO   -> Plan Pro ($4.99/mes)
    PREMIUM -> Plan Premium ($9.99/mes)
    """
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"


class User(UserMixin, db.Model):
    """
    Tabla de usuarios registrados.
    Hereda de UserMixin para integrarse con Flask-Login.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True) # Nullable para usuarios de Google
    google_id = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone_number = db.Column(db.String(50), unique=True, nullable=True, index=True)
    is_verified = db.Column(db.Boolean, default=False) # Para obligar a validar SMS/Email
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relaciones
    subscription = db.relationship("Subscription", backref="user", uselist=False, lazy=True)
    downloads = db.relationship("Download", backref="user", lazy="dynamic")
    playlists = db.relationship("Playlist", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username} ({self.email})>"


class Subscription(db.Model):
    """
    Tabla de suscripciones activas.
    Cada usuario tiene UNA suscripción activa (o free por defecto).
    """
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    plan = db.Column(db.Enum(PlanType), nullable=False, default=PlanType.FREE)
    stripe_subscription_id = db.Column(db.String(100), nullable=True)  # ID en Stripe
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # NULL si es free (no expira)
    is_active = db.Column(db.Boolean, default=True)

    def is_expired(self) -> bool:
        """Verifica si la suscripción ha expirado."""
        if self.expires_at is None:
            return False  # Plan gratuito no expira
        return datetime.utcnow() > self.expires_at

    def days_remaining(self) -> int:
        """Días restantes de suscripción."""
        if self.expires_at is None:
            return -1  # Ilimitado (plan free)
        remaining = (self.expires_at - datetime.utcnow()).days
        return max(0, remaining)

    def __repr__(self):
        return f"<Subscription {self.user_id} - {self.plan.value}>"


class Download(db.Model):
    """
    Tabla de descargas realizadas.
    Registra cada descarga para controlar límites diarios.
    """
    __tablename__ = "downloads"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # NULL = usuario anónimo
    url = db.Column(db.String(500), nullable=False)
    platform = db.Column(db.String(20), nullable=False)  # youtube, instagram, tiktok
    quality = db.Column(db.String(10), nullable=False)    # 720p, 1080p, 2160p
    file_size = db.Column(db.Integer, nullable=True)      # Tamaño en bytes
    file_path = db.Column(db.String(500), nullable=True)  # Ruta del archivo descargado
    status = db.Column(db.String(20), default="pending")  # pending, downloading, completed, failed
    error_message = db.Column(db.Text, nullable=True)     # Mensaje de error si falló
    ip_address = db.Column(db.String(45), nullable=True)  # IP del usuario (anónimos)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Download {self.id} - {self.platform} - {self.status}>"


class Playlist(db.Model):
    """
    Tabla de listas de reproduccion del usuario.
    Solo para planes Pro/Premium.
    """
    __tablename__ = "playlists"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    items = db.relationship("PlaylistItem", backref="playlist", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Playlist {self.name}>"


class PlaylistItem(db.Model):
    """
    Tabla de canciones/videos guardados dentro de una playlist.
    """
    __tablename__ = "playlist_items"

    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.Integer, db.ForeignKey("playlists.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    thumbnail = db.Column(db.String(500), nullable=True)
    duration = db.Column(db.Integer, nullable=True) # Segundos
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PlaylistItem {self.title}>"


def init_db(app):
    """
    Inicializa la base de datos y crea las tablas si no existen.
    Se llama desde app.py al arrancar la aplicación.
    """
    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("[OK] Base de datos inicializada correctamente.")
