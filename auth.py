"""
SERVICIO DE AUTENTICACION Y JWT
================================
Maneja registro, login, logout y gestion de usuarios.
Incluye autenticacion JWT para las APIs (descargas, etc.)
y Flask-Login para la interfaz web.

Funciones:
  - register_user(username, email, password)  -> Crea un nuevo usuario
  - authenticate_user(email, password)        -> Verifica credenciales
  - login_user_web(user)                      -> Inicia sesion web (Flask-Login)
  - create_jwt_token(user)                    -> Genera token JWT para API
  - verify_jwt_token(token)                   -> Verifica token JWT
  - get_user_by_id(user_id)                   -> Obtiene usuario por ID
  - get_user_plan(user)                       -> Obtiene el plan del usuario
  - check_daily_limit(user)                   -> Verifica si puede descargar hoy
  - can_download_platform(user, platform)     -> Verifica plataforma permitida
  - get_max_quality(user)                     -> Obtiene calidad maxima
"""

import re
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user as flask_login_user
from flask_jwt_extended import create_access_token, decode_token
from models import db, User, Subscription, Download, PlanType
from config import Config
from datetime import datetime, date, timedelta


# -------------------- VALIDACIONES --------------------


def _validate_email(email: str) -> bool:
    """Valida formato de email basico."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _validate_password(password: str) -> dict:
    """
    Valida fortaleza de contrasena.
    Returns: {"valid": bool, "message": str}
    """
    if len(password) < 8:
        return {"valid": False, "message": "La contrasena debe tener al menos 8 caracteres."}
    if not re.search(r'[A-Z]', password):
        return {"valid": False, "message": "La contrasena debe tener al menos una mayuscula."}
    if not re.search(r'[a-z]', password):
        return {"valid": False, "message": "La contrasena debe tener al menos una minuscula."}
    if not re.search(r'[0-9]', password):
        return {"valid": False, "message": "La contrasena debe tener al menos un numero."}
    return {"valid": True, "message": "OK"}


# -------------------- FUNCIONES PUBLICAS --------------------


def register_user(username: str, email: str, password: str) -> dict:
    """
    Registra un nuevo usuario en el sistema.

    Args:
        username: Nombre de usuario unico.
        email: Correo electronico unico.
        password: Contrasena en texto plano (se valida y hashea).

    Returns:
        Diccionario con resultado.
    """
    # Sanitizar entradas
    username = username.strip()[:80]
    email = email.strip().lower()[:120]

    # Validar formato
    if not username or len(username) < 3:
        return {"success": False, "error": "El nombre de usuario debe tener al menos 3 caracteres."}

    if not _validate_email(email):
        return {"success": False, "error": "Formato de correo electronico invalido."}

    password_check = _validate_password(password)
    if not password_check["valid"]:
        return {"success": False, "error": password_check["message"]}

    # Validar que no exista duplicado
    if User.query.filter_by(username=username).first():
        return {"success": False, "error": "El nombre de usuario ya esta en uso."}

    if User.query.filter_by(email=email).first():
        return {"success": False, "error": "El correo electronico ya esta registrado."}

    try:
        # Crear usuario
        password_hash = generate_password_hash(password, method='pbkdf2:sha256:600000')
        user = User(username=username, email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.flush()

        # Crear suscripcion gratuita por defecto
        subscription = Subscription(user_id=user.id, plan=PlanType.FREE, is_active=True)
        db.session.add(subscription)
        db.session.commit()

        return {"success": True, "user": user}

    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": f"Error al registrar: {str(e)}"}


def authenticate_user(email: str, password: str) -> dict:
    """
    Autentica a un usuario con email y contrasena.

    Args:
        email: Correo electronico del usuario.
        password: Contrasena en texto plano.

    Returns:
        Diccionario con resultado.
    """
    email = email.strip().lower()
    user = User.query.filter_by(email=email).first()

    if not user:
        return {"success": False, "error": "Usuario no encontrado."}

    if not check_password_hash(user.password_hash, password):
        return {"success": False, "error": "Contrasena incorrecta."}

    if not user.is_active:
        return {"success": False, "error": "La cuenta esta desactivada."}

    return {"success": True, "user": user}


def login_user_web(user: User) -> bool:
    """
    Inicia sesion web usando Flask-Login.
    Configura la sesion como permanente para que no expire al cerrar el navegador.
    """
    return flask_login_user(user, remember=True, duration=timedelta(days=7))


def create_jwt_token(user: User) -> str:
    """
    Genera un token JWT para autenticacion de APIs.

    Args:
        user: Objeto User.

    Returns:
        String con token JWT.
    """
    additional_claims = {
        "username": user.username,
        "plan": user.subscription.plan.value if user.subscription else "free",
    }
    return create_access_token(
        identity=str(user.id),
        additional_claims=additional_claims,
        expires_delta=timedelta(hours=1)  # Token valido por 1 hora
    )


def verify_jwt_token(token: str) -> dict:
    """
    Verifica y decodifica un token JWT.

    Args:
        token: Token JWT a verificar.

    Returns:
        Diccionario con user_id y claims, o error.
    """
    try:
        decoded = decode_token(token)
        return {
            "success": True,
            "user_id": int(decoded["sub"]),
            "claims": decoded.get("claims", {}),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_user_by_id(user_id: int) -> User:
    """Obtiene un usuario por su ID."""
    return User.query.get(int(user_id))


def get_user_plan(user: User) -> dict:
    """
    Obtiene informacion del plan de un usuario.

    Returns:
        Diccionario con: plan, is_active, days_remaining, max_quality, platforms, daily_limit.
    """
    if not user or not user.subscription:
        return _default_free_plan()

    sub = user.subscription

    # Si la suscripcion paga expiro, degradar a free
    if sub.is_expired() and sub.plan != PlanType.FREE:
        sub.plan = PlanType.FREE
        sub.is_active = True
        sub.expires_at = None
        db.session.commit()

    if sub.plan == PlanType.PRO:
        return {
            "plan": PlanType.PRO.value,
            "is_active": sub.is_active and not sub.is_expired(),
            "days_remaining": sub.days_remaining(),
            "max_quality": Config.PRO_MAX_QUALITY,
            "platforms": Config.PRO_PLATFORMS,
            "daily_limit": -1,
        }
    elif sub.plan == PlanType.PREMIUM:
        return {
            "plan": PlanType.PREMIUM.value,
            "is_active": sub.is_active and not sub.is_expired(),
            "days_remaining": sub.days_remaining(),
            "max_quality": Config.PREMIUM_MAX_QUALITY,
            "platforms": Config.PREMIUM_PLATFORMS,
            "daily_limit": -1,
        }
    else:
        return _default_free_plan()


def check_daily_limit(user: User) -> dict:
    """
    Verifica si el usuario puede realizar una descarga hoy.
    Usa la zona horaria UTC para el conteo diario.
    """
    plan_info = get_user_plan(user)

    # Usuarios Pro/Premium ilimitados
    if plan_info["daily_limit"] == -1:
        return {"allowed": True, "remaining": -1, "error": None}

    # Contar descargas de hoy
    today = date.today()
    downloads_today = Download.query.filter(
        Download.user_id == user.id,
        db.func.date(Download.created_at) == today,
        Download.status == "completed",
    ).count()

    remaining = plan_info["daily_limit"] - downloads_today

    if remaining <= 0:
        return {
            "allowed": False,
            "remaining": 0,
            "error": "Has alcanzado el limite diario. "
                     "Actualiza a Pro para descargas ilimitadas.",
        }

    return {"allowed": True, "remaining": remaining, "error": None}


def can_download_platform(user: User, platform: str) -> bool:
    """Verifica si el usuario puede descargar desde una plataforma especifica."""
    plan_info = get_user_plan(user)
    return platform in plan_info["platforms"]


def get_max_quality(user: User) -> str:
    """Obtiene la calidad maxima permitida para el usuario."""
    plan_info = get_user_plan(user)
    return plan_info["max_quality"]


# -------------------- FUNCIONES PRIVADAS --------------------


def _default_free_plan() -> dict:
    """Retorna la configuracion del plan gratuito."""
    return {
        "plan": PlanType.FREE.value,
        "is_active": True,
        "days_remaining": -1,
        "max_quality": Config.FREE_MAX_QUALITY,
        "platforms": Config.FREE_PLATFORMS,
        "daily_limit": Config.FREE_DAILY_LIMIT,
    }