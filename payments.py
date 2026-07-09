"""
SERVICIO DE PAGOS (STRIPE)
==========================
Maneja la integración con Stripe para suscripciones.
Funciones:
  - create_checkout_session(plan_type, user) -> Crea sesión de pago en Stripe
  - handle_webhook(payload, sig_header)      -> Procesa eventos de Stripe
  - cancel_subscription(user)                -> Cancela suscripción activa
  - get_subscription_status(user)            -> Obtiene estado de suscripción
"""

import stripe
try:
    # Parche para el bug de lazy loading de Stripe en Python 3.12
    import stripe.apps._secret
except ImportError:
    pass

from flask import current_app
from models import db, User, Subscription, PlanType
from config import Config
from datetime import datetime, timedelta

# Configurar Stripe con la clave secreta
stripe.api_key = Config.STRIPE_SECRET_KEY


# -------------------- CONSTANTES --------------------

# Mapeo de planes a IDs de precio en Stripe
# Estos IDs se crean en el dashboard de Stripe (Products > Prices)
# Formato: price_xxxxxxxxxxxxxx
STRIPE_PRICE_IDS = {
    PlanType.PRO: Config.STRIPE_PRO_PRICE_ID or "price_pro_placeholder",
    PlanType.PREMIUM: Config.STRIPE_PREMIUM_PRICE_ID or "price_premium_placeholder",
}

# Duración de cada plan en días
PLAN_DURATION_DAYS = {
    PlanType.PRO: 30,       # 1 mes
    PlanType.PREMIUM: 30,   # 1 mes
}


# -------------------- FUNCIONES PÚBLICAS --------------------


def create_checkout_session(plan_type: PlanType, user: User) -> dict:
    """
    Crea una sesión de pago en Stripe para que el usuario se suscriba.

    Args:
        plan_type: Tipo de plan (PRO o PREMIUM).
        user: Objeto User que va a pagar.

    Returns:
        Diccionario con:
          - success: True si se creó la sesión.
          - session_url: URL de Stripe Checkout para redirigir al usuario.
          - error: Mensaje de error (si success=False).
    """
    try:
        # Obtener el ID del precio en Stripe para este plan
        price_id = STRIPE_PRICE_IDS.get(plan_type)
        if not price_id:
            return {"success": False, "error": "Plan no configurado en Stripe."}

        # Crear la sesión de checkout
        from stripe.checkout import Session as StripeCheckoutSession
        checkout_session = StripeCheckoutSession.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=current_app.config.get("BASE_URL", "http://localhost:5000")
                        + "/payment/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=current_app.config.get("BASE_URL", "http://localhost:5000")
                       + "/pricing",
            client_reference_id=str(user.id),
            customer_email=user.email,
            metadata={
                "user_id": str(user.id),
                "plan": plan_type.value,
            },
        )

        return {
            "success": True,
            "session_url": checkout_session.url,
            "session_id": checkout_session.id,
        }

    except stripe.error.StripeError as e:
        return {"success": False, "error": f"Error de Stripe: {str(e)}"}
    except Exception as e:
        import traceback
        print("====== STRIPE EXCEPTION TRACEBACK ======")
        traceback.print_exc()
        print("========================================")
        return {"success": False, "error": f"Error inesperado: {str(e)}"}


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """
    Procesa eventos webhook de Stripe (pagos exitosos, cancelaciones, etc.).

    Args:
        payload: Cuerpo de la solicitud en bytes.
        sig_header: Firma del webhook de Stripe.

    Returns:
        Diccionario con:
          - success: True si se procesó correctamente.
          - event_type: Tipo de evento procesado.
          - error: Mensaje de error (si success=False).
    """
    try:
        # Verificar la firma del webhook
        event = stripe.Webhook.construct_event(
            payload, sig_header, Config.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return {"success": False, "error": "Firma de webhook inválida."}
    except ValueError:
        return {"success": False, "error": "Payload inválido."}

    # Procesar según el tipo de evento
    event_type = event.get("type")

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event)
    elif event_type == "invoice.payment_succeeded":
        _handle_payment_succeeded(event)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event)
    else:
        print(f"[INFO] Evento de Stripe no manejado: {event_type}")

    return {"success": True, "event_type": event_type}


def cancel_subscription(user: User) -> dict:
    """
    Cancela la suscripción activa de un usuario en Stripe y en la base de datos.

    Args:
        user: Objeto User.

    Returns:
        Diccionario con:
          - success: True si se canceló correctamente.
          - error: Mensaje de error (si success=False).
    """
    if not user.subscription or user.subscription.plan == PlanType.FREE:
        return {"success": False, "error": "No tienes una suscripción activa."}

    try:
        # Cancelar en Stripe si tiene un ID de suscripción
        if user.subscription.stripe_subscription_id:
            stripe.Subscription.delete(user.subscription.stripe_subscription_id)

        # Degradar a plan gratuito en la base de datos
        user.subscription.plan = PlanType.FREE
        user.subscription.stripe_subscription_id = None
        user.subscription.expires_at = None
        db.session.commit()

        return {"success": True, "message": "Suscripción cancelada correctamente."}

    except stripe.error.StripeError as e:
        return {"success": False, "error": f"Error al cancelar en Stripe: {str(e)}"}
    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": f"Error inesperado: {str(e)}"}


def get_subscription_status(user: User) -> dict:
    """
    Obtiene el estado detallado de la suscripción del usuario.

    Args:
        user: Objeto User.

    Returns:
        Diccionario con información de la suscripción.
    """
    if not user.subscription:
        return {"plan": "free", "is_active": True}

    sub = user.subscription
    return {
        "plan": sub.plan.value,
        "is_active": sub.is_active and not sub.is_expired(),
        "started_at": sub.started_at.isoformat() if sub.started_at else None,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "days_remaining": sub.days_remaining(),
        "stripe_subscription_id": sub.stripe_subscription_id,
    }


# -------------------- FUNCIONES PRIVADAS (Manejadores de Webhook) --------------------


def _handle_checkout_completed(event):
    """
    Maneja el evento de checkout completado.
    Activa la suscripción del usuario después del pago exitoso.
    """
    session = event["data"]["object"]
    user_id = int(session.get("metadata", {}).get("user_id", 0))
    plan_str = session.get("metadata", {}).get("plan", "free")
    stripe_subscription_id = session.get("subscription")

    if not user_id:
        print("[WARN] Webhook: user_id no encontrado en metadata.")
        return

    user = User.query.get(user_id)
    if not user:
        print(f"[WARN] Webhook: Usuario {user_id} no encontrado.")
        return

    plan_type = PlanType(plan_str) if plan_str in [p.value for p in PlanType] else PlanType.FREE
    duration_days = PLAN_DURATION_DAYS.get(plan_type, 30)

    # Actualizar suscripción en la base de datos
    if user.subscription:
        user.subscription.plan = plan_type
        user.subscription.stripe_subscription_id = stripe_subscription_id
        user.subscription.started_at = datetime.utcnow()
        user.subscription.expires_at = datetime.utcnow() + timedelta(days=duration_days)
        user.subscription.is_active = True
    else:
        subscription = Subscription(
            user_id=user.id,
            plan=plan_type,
            stripe_subscription_id=stripe_subscription_id,
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=duration_days),
            is_active=True,
        )
        db.session.add(subscription)

    db.session.commit()
    print(f"[OK] Suscripcion {plan_type.value} activada para {user.email}")


def _handle_payment_succeeded(event):
    """
    Maneja el evento de pago de factura exitoso.
    Renueva la suscripción por otro período.
    """
    invoice = event["data"]["object"]
    subscription_id = invoice.get("subscription")

    if not subscription_id:
        return

    # Buscar la suscripción en nuestra base de datos
    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_id
    ).first()

    if not subscription:
        print(f"[WARN] Webhook: Suscripcion {subscription_id} no encontrada en BD.")
        return

    # Extender la fecha de expiración
    duration_days = PLAN_DURATION_DAYS.get(subscription.plan, 30)
    subscription.expires_at = datetime.utcnow() + timedelta(days=duration_days)
    subscription.is_active = True
    db.session.commit()
    print(f"[OK] Pago recibido. Suscripcion {subscription.plan.value} extendida.")


def _handle_payment_failed(event):
    """
    Maneja el evento de pago fallido.
    Notifica al usuario (en producción se enviaría un email).
    """
    invoice = event["data"]["object"]
    subscription_id = invoice.get("subscription")

    if not subscription_id:
        return

    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_id
    ).first()

    if subscription:
        print(f"[WARN] Pago fallido para {subscription.user.email}. "
              f"La suscripcion se desactivara pronto.")


def _handle_subscription_deleted(event):
    """
    Maneja el evento de suscripción cancelada/eliminada en Stripe.
    Degrada al usuario a plan gratuito.
    """
    stripe_subscription = event["data"]["object"]
    subscription_id = stripe_subscription.get("id")

    if not subscription_id:
        return

    subscription = Subscription.query.filter_by(
        stripe_subscription_id=subscription_id
    ).first()

    if subscription:
        subscription.plan = PlanType.FREE
        subscription.stripe_subscription_id = None
        subscription.expires_at = None
        subscription.is_active = True
        db.session.commit()
        print(f"[INFO] Suscripcion cancelada para {subscription.user.email}")
