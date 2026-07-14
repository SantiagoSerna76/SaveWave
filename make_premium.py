import argparse
from app import app
from models import db, User, Subscription, PlanType
from datetime import datetime, timedelta

def upgrade_user(email, plan_name):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"Error: No se encontro ningun usuario con el correo {email}")
            return

        if not user.subscription:
            sub = Subscription(user_id=user.id)
            db.session.add(sub)
        else:
            sub = user.subscription

        if plan_name.lower() == 'pro':
            sub.plan = PlanType.PRO
            sub.expires_at = datetime.utcnow() + timedelta(days=30)
            print(f"[{email}] Mejorado a plan PRO (30 dias)")
        elif plan_name.lower() == 'premium':
            sub.plan = PlanType.PREMIUM
            sub.expires_at = datetime.utcnow() + timedelta(days=30)
            print(f"[{email}] Mejorado a plan PREMIUM (30 dias)")
        elif plan_name.lower() == 'free':
            sub.plan = PlanType.FREE
            sub.expires_at = None
            print(f"[{email}] Degradado a plan FREE")
        else:
            print("Plan invalido. Usa 'free', 'pro', o 'premium'.")
            return
            
        sub.is_active = True
        db.session.commit()
        print("Operacion completada con exito.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cambiar el plan de un usuario")
    parser.add_argument("email", help="Correo del usuario")
    parser.add_argument("plan", choices=["free", "pro", "premium"], help="Plan a asignar")
    args = parser.parse_args()
    
    upgrade_user(args.email, args.plan)
