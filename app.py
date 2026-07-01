"""
APLICACION PRINCIPAL - CONTROLADOR (Flask)
============================================
Punto de entrada de la aplicacion. Define las rutas (endpoints) y conecta
los servicios (auth, downloader, payments) con las plantillas HTML.

SEGURIDAD:
  - JWT para autenticacion de APIs
  - Rate limiting en endpoints sensibles
  - Validacion de entrada en formularios
  - Sesiones HTTP-only
  - Contrasenas con hash pbkdf2:sha256
"""

import os
import time
import pymysql
import stripe

# Configurar pymysql como conector MySQL para SQLAlchemy
pymysql.install_as_MySQLdb()

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_file, session, abort, current_app
)
from flask_cors import CORS
from flask_login import (
    LoginManager, login_required, current_user
)
from flask_jwt_extended import (
    JWTManager, jwt_required, get_jwt_identity, get_jwt,
    verify_jwt_in_request
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime

# Importar configuracion
from config import Config

# Importar modelos y base de datos
from models import db, init_db, User, Download, PlanType, Playlist, PlaylistItem

# Importar servicios
from downloader import (
    detect_platform, get_video_info, download_video, download_audio,
    get_available_qualities, cleanup_old_files
)
from auth import (
    register_user, authenticate_user, get_user_by_id,
    get_user_plan, check_daily_limit, can_download_platform,
    get_max_quality, login_user_web, create_jwt_token
)


# ============================================================
# INICIALIZACION DE LA APLICACION
# ============================================================

app = Flask(__name__)
app.config.from_object(Config)

# Habilitar CORS para la extension de Chrome y APIs externas
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Inicializar base de datos
init_db(app)

# Inicializar JWT para APIs
jwt = JWTManager(app)

# Inicializar Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[Config.RATELIMIT_DEFAULT],
    enabled=Config.RATELIMIT_ENABLED,
    storage_uri=Config.RATELIMIT_STORAGE_URL,
)

# Inicializar Flask-Login (sesiones de usuario web)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor inicia sesion para acceder a esta funcion."
login_manager.session_protection = "strong"  # Protege contra session hijacking


@login_manager.user_loader
def load_user(user_id):
    """Carga un usuario desde la base de datos por su ID (requerido por Flask-Login)."""
    return get_user_by_id(int(user_id))


# ============================================================
# MANEJADORES DE ERRORES JWT
# ============================================================

@jwt.invalid_token_loader
def invalid_token_callback(error):
    """Respuesta para tokens JWT invalidos."""
    return jsonify({"success": False, "error": "Token invalido o expirado."}), 401


@jwt.unauthorized_loader
def missing_token_callback(error):
    """Respuesta cuando falta el token JWT."""
    return jsonify({"success": False, "error": "Se requiere token de autenticacion."}), 401


# ============================================================
# FILTROS PARA PLANTILLAS (Jinja2)
# ============================================================

@app.template_filter("format_duration")
def format_duration(seconds):
    """Convierte segundos a formato mm:ss o hh:mm:ss para las plantillas."""
    if not seconds:
        return "0:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


@app.template_filter("format_number")
def format_number(n):
    """Formatea numeros grandes (ej: 1500000 -> 1.5M)."""
    if not n:
        return "0"
    if n >= 1000000:
        return f"{n/1000000:.1f}M"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


# ============================================================
# HELPER - Obtener usuario desde JWT o sesion web
# ============================================================

def _get_api_user():
    """
    Intenta obtener el usuario autenticado, primero via JWT (API),
    luego via sesion web (Flask-Login).
    Retorna (user, is_jwt) o (None, False) si no hay autenticacion.
    """
    # Intentar JWT primero (header Authorization: Bearer <token>)
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            user = get_user_by_id(int(user_id))
            if user:
                return user, True
    except Exception:
        pass

    # Fallback a sesion web
    if current_user.is_authenticated:
        return current_user, False

    return None, False


@app.context_processor
def inject_ads_enabled():
    """
    Inyecta globalmente si los anuncios deben mostrarse o no.
    Se ocultan para planes Pro y Premium.
    """
    ads_enabled = Config.ADS_ENABLED
    if ads_enabled and current_user.is_authenticated:
        plan_info = get_user_plan(current_user)
        if plan_info["plan"] in ("pro", "premium"):
            ads_enabled = False
    
    return dict(
        ads_enabled=ads_enabled,
        adsense_client=Config.ADSENSE_CLIENT_ID
    )

# ============================================================
# RUTAS - PAGINAS PUBLICAS
# ============================================================

@app.route("/")
def index():
    """Pagina principal con formulario de descarga."""
    return render_template(
        "index.html"
    )


@app.route("/pricing")
def pricing():
    """Pagina de precios y planes."""
    return render_template(
        "pricing.html"
    )


@app.route("/terms")
def terms():
    """Pagina de terminos de uso."""
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    """Pagina de politica de privacidad."""
    return render_template("privacy.html")


# ============================================================
# RUTAS - PWA (Progressive Web App)
# ============================================================

@app.route('/manifest.json')
def serve_manifest():
    return current_app.send_static_file('manifest.json')

@app.route('/sw.js')
def serve_sw():
    return current_app.send_static_file('sw.js')


# ============================================================
# RUTAS - AUTENTICACION WEB (Flask-Login)
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    """Inicio de sesion web."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Todos los campos son obligatorios.", "danger")
            return render_template("login.html")

        result = authenticate_user(email, password)
        if result["success"]:
            # Marcar sesion como permanente antes de loguear
            session.permanent = True
            login_user_web(result["user"])
            flash(f"Bienvenido de nuevo, {result['user'].username}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        else:
            flash(result["error"], "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Registro de nuevo usuario."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Las contrasenas no coinciden.", "danger")
            return render_template("register.html")

        result = register_user(username, email, password)
        if result["success"]:
            flash("Registro exitoso! Ahora puedes iniciar sesion.", "success")
            return redirect(url_for("login"))
        else:
            flash(result["error"], "danger")

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    """Cierra la sesion."""
    from flask_login import logout_user as flask_logout
    flask_logout()
    flash("Has cerrado sesion correctamente.", "info")
    return redirect(url_for("index"))


# ============================================================
# RUTAS - DASHBOARD (USUARIO AUTENTICADO)
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """Panel de control del usuario."""
    plan_info = get_user_plan(current_user)
    limit_info = check_daily_limit(current_user)

    recent_downloads = Download.query.filter_by(
        user_id=current_user.id
    ).order_by(Download.created_at.desc()).limit(10).all()

    return render_template(
        "dashboard.html",
        plan_info=plan_info,
        limit_info=limit_info,
        recent_downloads=recent_downloads
    )


@app.route("/subscription/cancel", methods=["POST"])
@login_required
def cancel_subscription_route():
    """Cancela la suscripcion activa."""
    from payments import cancel_subscription as cancel_sub
    result = cancel_sub(current_user)
    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["error"], "danger")
    return redirect(url_for("dashboard"))


# ============================================================
# API - INFORMACION Y DESCARGA DE VIDEOS (con rate limiting)
# ============================================================

@app.route("/api/video-info", methods=["POST"])
@limiter.limit("30 per minute")  # Max 30 consultas por minuto
def api_video_info():
    """
    API: Obtiene informacion de un video sin descargarlo.
    Acepta autenticacion via sesion web O via JWT (Authorization: Bearer <token>).
    """
    # Soportar tanto form data como JSON
    if request.is_json:
        data = request.get_json()
        url = data.get("url", "").strip() if data else ""
    else:
        url = request.form.get("url", "").strip()

    if not url:
        return jsonify({"success": False, "error": "Debes proporcionar una URL."})

    try:
        info = get_video_info(url)

        # Verificar permisos segun plataforma (sesion web o JWT)
        user, is_jwt = _get_api_user()
        if user:
            if not can_download_platform(user, info["platform"]):
                return jsonify({
                    "success": False,
                    "error": f"Tu plan no permite descargas de {info['platform']}. "
                             f"Actualiza a Pro.",
                    "upgrade_required": True,
                })

        return jsonify({
            "success": True,
            "is_playlist": info.get("is_playlist", False),
            "title": info.get("title", ""),
            "duration": info.get("duration", 0),
            "duration_formatted": format_duration(info.get("duration", 0)),
            "platform": info.get("platform", ""),
            "thumbnail": info.get("thumbnail", ""),
            "uploader": info.get("uploader", ""),
            "views": info.get("view_count", 0),
            "available_qualities": info.get("available_qualities", []),
            "items": info.get("items", [])
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)})
    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)})
    except Exception as e:
        return jsonify({"success": False, "error": f"Error inesperado: {str(e)}"})


@app.route("/api/download", methods=["POST"])
@limiter.limit("10 per minute")  # Max 10 descargas por minuto
def api_download():
    """
    API: Descarga un video.
    Acepta autenticacion via sesion web O via JWT (Authorization: Bearer <token>).
    """
    # Soportar tanto form data como JSON
    if request.is_json:
        data = request.get_json()
        url = data.get("url", "").strip() if data else ""
        quality = data.get("quality", "720p").strip() if data else "720p"
    else:
        url = request.form.get("url", "").strip()
        quality = request.form.get("quality", "720p").strip()

    if not url:
        return jsonify({"success": False, "error": "Debes proporcionar una URL."})

    # --- Verificar limites segun el usuario (sesion web o JWT) ---
    user, is_jwt = _get_api_user()

    if user:
        # Verificar limite diario
        limit_check = check_daily_limit(user)
        if not limit_check["allowed"]:
            return jsonify({"success": False, "error": limit_check["error"],
                          "upgrade_required": True})

        # Verificar calidad maxima permitida
        max_quality = get_max_quality(user)
        quality_number = int(quality.replace("p", ""))
        max_quality_number = int(max_quality.replace("p", ""))
        if quality_number > max_quality_number:
            quality = max_quality
    else:
        # Usuario anonimo: sin limite de descargas, pero solo 720p maximo
        # y solo YouTube (para mas plataformas necesita registrarse)
        try:
            platform = detect_platform(url)
            if platform not in Config.ANONYMOUS_PLATFORMS:
                return jsonify({
                    "success": False,
                    "error": "Los usuarios anonimos solo pueden descargar de YouTube. "
                             "Registrate gratis para acceder a Facebook, Twitter, Vimeo y mas.",
                    "upgrade_required": False,
                })
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)})

        # Limitar calidad maxima a 720p para anonimos
        quality_number = int(quality.replace("p", ""))
        max_anonymous = int(Config.ANONYMOUS_MAX_QUALITY.replace("p", ""))
        if quality_number > max_anonymous:
            quality = Config.ANONYMOUS_MAX_QUALITY

    # --- Realizar la descarga ---
    try:
        result = download_video(url, quality)

        if result["success"]:
            # Registrar la descarga en la base de datos
            download_record = Download(
                user_id=user.id if user else None,
                url=url,
                platform=detect_platform(url),
                quality=quality,
                file_size=result["file_size"],
                file_path=result["file_path"],
                status="completed",
                ip_address=request.remote_addr,
                completed_at=datetime.utcnow(),
            )
            db.session.add(download_record)
            db.session.commit()

            return jsonify({
                "success": True,
                "filename": result["filename"],
                "file_size": result["file_size_formatted"],
                "title": result["title"],
                "platform": result["platform"],
                "download_url": url_for("download_file", filename=result["filename"], _external=True),
            })
        else:
            return jsonify({"success": False, "error": result["error"]})

    except Exception as e:
        return jsonify({"success": False, "error": f"Error al descargar: {str(e)}"})


@app.route("/downloads/<filename>")
def download_file(filename):
    """Sirve el archivo descargado al usuario."""
    # Validar nombre de archivo para prevenir path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        abort(400)

    file_path = os.path.join(Config.DOWNLOAD_FOLDER, filename)
    # Normalizar y verificar que este dentro de DOWNLOAD_FOLDER
    real_path = os.path.realpath(file_path)
    download_folder = os.path.realpath(Config.DOWNLOAD_FOLDER)
    if not real_path.startswith(download_folder):
        abort(403)

    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)


# ============================================================
# API - JWT (para autenticacion de API externa)
# ============================================================

@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("20 per minute")
def api_auth_login():
    """
    API: Autentica a un usuario y devuelve un token JWT.
    Util para aplicaciones externas o integraciones.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Se requieren datos JSON."}), 400

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "error": "Email y contrasena requeridos."}), 400

    result = authenticate_user(email, password)
    if result["success"]:
        token = create_jwt_token(result["user"])
        return jsonify({
            "success": True,
            "token": token,
            "user": {
                "id": result["user"].id,
                "username": result["user"].username,
                "email": result["user"].email,
            }
        })
    else:
        return jsonify({"success": False, "error": result["error"]}), 401


@app.route("/api/auth/me", methods=["GET"])
@jwt_required()
def api_auth_me():
    """
    API: Obtiene informacion del usuario autenticado via JWT.
    Requiere header: Authorization: Bearer <token>
    """
    user_id = get_jwt_identity()
    claims = get_jwt()
    user = get_user_by_id(int(user_id))

    if not user:
        return jsonify({"success": False, "error": "Usuario no encontrado."}), 404

    plan_info = get_user_plan(user)
    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "plan": plan_info["plan"],
            "max_quality": plan_info["max_quality"],
            "platforms": plan_info["platforms"],
        }
    })


# ============================================================
# RUTAS - PAGOS (STRIPE)
# ============================================================

@app.route("/api/download-audio", methods=["POST"])
@limiter.limit("10 per minute")
def api_download_audio():
    """
    API: Descarga solo el audio de un video y lo convierte a MP3.
    Acepta autenticacion via sesion web O via JWT (Authorization: Bearer <token>).
    """
    # Soportar tanto form data como JSON
    if request.is_json:
        data = request.get_json()
        url = data.get("url", "").strip() if data else ""
        quality = data.get("quality", "128").strip() if data else "128"
    else:
        url = request.form.get("url", "").strip()
        quality = request.form.get("quality", "128").strip()

    if not url:
        return jsonify({"success": False, "error": "Debes proporcionar una URL."})

    # Verificar limite (sesion web o JWT)
    user, is_jwt = _get_api_user()
    if user:
        limit_check = check_daily_limit(user)
        if not limit_check["allowed"]:
            return jsonify({"success": False, "error": limit_check["error"],
                          "upgrade_required": True})

    # Solo permitir MP3 128kbps para usuarios gratuitos
    mp3_quality = "128"
    if user:
        plan_info = get_user_plan(user)
        if plan_info["plan"] in ("pro", "premium"):
            mp3_quality = "320"  # Mayor calidad para planes de pago

    try:
        result = download_audio(url, mp3_quality)
        if result["success"]:
            return jsonify({
                "success": True,
                "filename": result["filename"],
                "file_size": result["file_size_formatted"],
                "title": result["title"],
                "platform": result["platform"],
                "download_url": url_for("download_file", filename=result["filename"], _external=True),
            })
        else:
            return jsonify({"success": False, "error": result["error"]})
    except Exception as e:
        return jsonify({"success": False, "error": f"Error al convertir a MP3: {str(e)}"})


@app.route("/api/download-multiple", methods=["POST"])
@login_required
@limiter.limit("3 per minute")
def api_download_multiple():
    """
    API: Descarga multiples videos y devuelve un ZIP.
    Solo para plan Premium.
    """
    import zipfile
    from io import BytesIO

    plan_info = get_user_plan(current_user)
    if plan_info["plan"] not in ["pro", "premium"]:
        return jsonify({"success": False, "error": "Funcion disponible para planes Pro y Premium."}), 403

    data = request.get_json()
    if not data or "urls" not in data:
        return jsonify({"success": False, "error": "Debes enviar una lista de URLs en formato JSON."}), 400

    urls = data["urls"]
    if not urls or len(urls) > 10:
        return jsonify({"success": False, "error": "Maximo 10 URLs por descarga masiva."}), 400

    quality = data.get("quality", "720p")
    downloaded_files = []

    for url in urls:
        result = download_video(url.strip(), quality)
        if result["success"]:
            downloaded_files.append(result["file_path"])
        else:
            return jsonify({"success": False, "error": f"Error en {url}: {result['error']}", "url": url}), 400

    # Crear ZIP en memoria
    zip_buffer = BytesIO()
    timestamp = int(time.time())
    zip_filename = f"savewave_batch_{timestamp}.zip"

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in downloaded_files:
            arcname = os.path.basename(file_path)
            zf.write(file_path, arcname)

    zip_buffer.seek(0)

    # Guardar ZIP temporal
    zip_path = os.path.join(Config.DOWNLOAD_FOLDER, zip_filename)
    with open(zip_path, "wb") as f:
        f.write(zip_buffer.getvalue())

    return jsonify({
        "success": True,
        "filename": zip_filename,
        "count": len(downloaded_files),
        "download_url": url_for("download_file", filename=zip_filename),
    })


@app.route("/payment/create/<plan_type>", methods=["POST"])
@login_required
def payment_create(plan_type):
    """Crea una sesion de pago en Stripe."""
    plan_map = {
        "pro": PlanType.PRO,
        "premium": PlanType.PREMIUM,
    }

    plan = plan_map.get(plan_type.lower())
    if not plan:
        flash("Plan no valido.", "danger")
        return redirect(url_for("pricing"))

    from payments import create_checkout_session
    result = create_checkout_session(plan, current_user)
    if result["success"]:
        return redirect(result["session_url"])
    else:
        flash(result["error"], "danger")
        return redirect(url_for("pricing"))


@app.route("/payment/success")
@login_required
def payment_success():
    """Pagina de exito despues del pago."""
    flash("Pago exitoso! Tu suscripcion esta activa.", "success")
    return redirect(url_for("dashboard"))


@app.route("/payment/webhook", methods=["POST"])
def payment_webhook():
    """
    Webhook de Stripe.
    No tiene rate limiting ni autenticacion porque Stripe lo firma.
    """
    from payments import handle_webhook
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")

    result = handle_webhook(payload, sig_header)
    if result["success"]:
        return jsonify({"status": "ok"}), 200
    else:
        return jsonify({"error": result["error"]}), 400


# ============================================================
# RUTA - MANTENIMIENTO (LIMPIEZA)
# ============================================================

@app.route("/admin/cleanup")
def admin_cleanup():
    """Limpia archivos temporales antiguos."""
    cleanup_old_files()
    flash("Archivos temporales limpiados.", "info")
    return redirect(url_for("index"))


# ============================================================
# API - CACHE STATS
# ============================================================

@app.route("/api/cache/stats", methods=["GET"])
def api_cache_stats():
    """API: Muestra estadisticas del sistema de cache."""
    from cache import get_cache_stats
    return jsonify(get_cache_stats())


@app.route("/api/cache/clear", methods=["POST"])
@login_required
def api_cache_clear():
    """API: Invalida el cache (solo para administradores)."""
    from cache import invalidate_cache
    url = request.form.get("url", "")
    if url:
        invalidate_cache(url)
        return jsonify({"success": True, "message": f"Cache invalidado para {url}"})
    return jsonify({"success": False, "error": "Debes proporcionar una URL."})


# ============================================================
# RUTAS - SEO (Sitemap y Robots)
# ============================================================

@app.route("/sitemap.xml")
def sitemap():
    """Sirve el archivo sitemap.xml para motores de busqueda."""
    return render_template("sitemap.xml"), 200, {"Content-Type": "application/xml"}


@app.route("/robots.txt")
def robots():
    """Sirve el archivo robots.txt para motores de busqueda."""
    return render_template("robots.txt"), 200, {"Content-Type": "text/plain"}


@app.route("/google426583ef775745bf.html")
def google_verification():
    """Sirve el archivo de verificacion de Google Search Console."""
    return send_file("google426583ef775745bf.html")


# ============================================================
# RUTAS - API DOCS Y TOKEN
# ============================================================

@app.route("/api-docs")
def api_docs():
    """Pagina de documentacion de la API para usuarios Premium."""
    return render_template(
        "api_docs.html"
    )


@app.route("/api/token", methods=["POST"])
@login_required
def api_generate_token():
    """
    Genera un token JWT de larga duracion para usuarios Premium.
    Solo accesible desde el dashboard web.
    """
    plan_info = get_user_plan(current_user)
    if plan_info["plan"] != "premium":
        return jsonify({"success": False, "error": "Solo usuarios Premium pueden generar tokens de API."}), 403

    from datetime import timedelta as td
    from flask_jwt_extended import create_access_token as create_token
    token = create_token(
        identity=str(current_user.id),
        additional_claims={
            "username": current_user.username,
            "plan": "premium",
            "api_access": True,
        },
        expires_delta=td(days=30),  # Token valido por 30 dias
    )
    return jsonify({"success": True, "token": token, "expires_in": "30 dias"})


# ============================================================
# RUTAS - PLAYLISTS (API & VIEWS)
# ============================================================

@app.route("/playlists")
@login_required
def playlists_view():
    """Vista principal de Playlists (estilo Spotify)."""
    plan_info = get_user_plan(current_user)
    if plan_info["plan"] not in ("pro", "premium"):
        flash("Las Playlists son exclusivas de planes Pro y Premium.", "warning")
        return redirect(url_for("pricing"))
        
    user_playlists = Playlist.query.filter_by(user_id=current_user.id).order_by(Playlist.created_at.desc()).all()
    return render_template("playlists.html", playlists=user_playlists)

@app.route("/api/playlists/create", methods=["POST"])
@login_required
def api_playlist_create():
    """Crea una nueva playlist."""
    plan_info = get_user_plan(current_user)
    if plan_info["plan"] not in ("pro", "premium"):
        return jsonify({"success": False, "error": "Exclusivo de planes Pro/Premium."}), 403

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "El nombre es obligatorio."})

    new_playlist = Playlist(user_id=current_user.id, name=name, description=data.get("description", ""))
    db.session.add(new_playlist)
    db.session.commit()
    
    return jsonify({"success": True, "playlist": {"id": new_playlist.id, "name": new_playlist.name}})

@app.route("/api/playlists/add", methods=["POST"])
@login_required
def api_playlist_add():
    """Agrega uno o varios items a una playlist."""
    data = request.get_json() or {}
    playlist_id = data.get("playlist_id")
    items = data.get("items", []) # Lista de {title, url, platform, thumbnail, duration}
    
    if not playlist_id or not items:
        return jsonify({"success": False, "error": "Faltan datos."})

    playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
    if not playlist:
        return jsonify({"success": False, "error": "Playlist no encontrada."}), 404

    added_count = 0
    for item in items:
        existing = PlaylistItem.query.filter_by(playlist_id=playlist.id, url=item.get("url")).first()
        if not existing:
            new_item = PlaylistItem(
                playlist_id=playlist.id,
                title=item.get("title", "Desconocido"),
                url=item.get("url"),
                platform=item.get("platform", "youtube"),
                thumbnail=item.get("thumbnail"),
                duration=item.get("duration", 0)
            )
            db.session.add(new_item)
            added_count += 1
            
    db.session.commit()
    return jsonify({"success": True, "added": added_count})

@app.route("/api/playlists/<int:playlist_id>")
@login_required
def api_playlist_get(playlist_id):
    """Obtiene los detalles y canciones de una playlist."""
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
    if not playlist:
        return jsonify({"success": False, "error": "No encontrada."}), 404
        
    items = playlist.items.order_by(PlaylistItem.added_at.desc()).all()
    
    return jsonify({
        "success": True,
        "playlist": {
            "id": playlist.id,
            "name": playlist.name,
            "description": playlist.description,
            "items": [{
                "id": i.id,
                "title": i.title,
                "url": i.url,
                "platform": i.platform,
                "thumbnail": i.thumbnail,
                "duration": i.duration,
                "duration_formatted": format_duration(i.duration)
            } for i in items]
        }
    })

@app.route("/api/playlists/list")
@login_required
def api_playlists_list():
    """Devuelve la lista de playlists del usuario (para el modal del index)."""
    user_playlists = Playlist.query.filter_by(user_id=current_user.id).order_by(Playlist.created_at.desc()).all()
    return jsonify({
        "success": True,
        "playlists": [{"id": pl.id, "name": pl.name} for pl in user_playlists]
    })


@app.route("/api/playlists/upload", methods=["POST"])
@login_required
def api_playlist_upload():
    """
    Sube un archivo de audio o video desde el dispositivo del usuario
    y lo guarda en una playlist como un item local.
    """
    from werkzeug.utils import secure_filename

    ALLOWED_EXTENSIONS = {"mp3", "mp4", "wav", "ogg", "m4a", "aac", "flac", "webm", "mkv"}
    MAX_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB

    playlist_id = request.form.get("playlist_id")
    file = request.files.get("file")

    if not playlist_id:
        return jsonify({"success": False, "error": "Falta el ID de la playlist."}), 400
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "No se seleccionó ningún archivo."}), 400

    playlist = Playlist.query.filter_by(id=playlist_id, user_id=current_user.id).first()
    if not playlist:
        return jsonify({"success": False, "error": "Playlist no encontrada."}), 404

    # Validar extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"success": False, "error": f"Formato no soportado. Usa: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # Guardar el archivo
    safe_name = secure_filename(file.filename)
    timestamp = int(time.time())
    stored_name = f"upload_{current_user.id}_{timestamp}_{safe_name}"
    file_path = os.path.join(Config.DOWNLOAD_FOLDER, stored_name)

    # Leer en chunks para verificar tamaño sin cargar todo en RAM
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_SIZE_BYTES:
        return jsonify({"success": False, "error": "El archivo supera el límite de 200MB."}), 413

    file.save(file_path)

    # Detectar si es video o audio por extensión
    video_exts = {"mp4", "webm", "mkv"}
    platform = "video_local" if ext in video_exts else "audio_local"

    # Crear el item en la playlist
    display_name = os.path.splitext(safe_name)[0]
    new_item = PlaylistItem(
        playlist_id=playlist.id,
        title=display_name,
        url=f"/downloads/{stored_name}",
        platform=platform,
        thumbnail=None,
        duration=0
    )
    db.session.add(new_item)
    db.session.commit()

    return jsonify({
        "success": True,
        "item": {
            "id": new_item.id,
            "title": new_item.title,
            "url": new_item.url,
            "platform": new_item.platform,
        }
    })

# ============================================================
# INICIO DE LA APLICACION
# ============================================================

if __name__ == "__main__":
    # Crear carpeta de descargas si no existe
    os.makedirs(Config.DOWNLOAD_FOLDER, exist_ok=True)

    print("[INFO] Servidor iniciado en http://localhost:5000")
    print("[INFO] Carpeta de descargas:", Config.DOWNLOAD_FOLDER)
    app.run(debug=True, host="0.0.0.0", port=5000)