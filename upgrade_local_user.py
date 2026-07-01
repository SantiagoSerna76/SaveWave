from app import app
from models import db, User, Subscription, PlanType
from datetime import datetime, timedelta

def upgrade_user(email, plan_name):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"Usuario con email {email} no encontrado.")
            return
        
        plan_enum = None
        if plan_name.upper() == "PRO":
            plan_enum = PlanType.PRO
        elif plan_name.upper() == "PREMIUM":
            plan_enum = PlanType.PREMIUM
        elif plan_name.upper() == "FREE":
            plan_enum = PlanType.FREE
        else:
            print("Plan invalido. Usa: PRO, PREMIUM, o FREE")
            return

        sub = Subscription.query.filter_by(user_id=user.id).first()
        if not sub:
            sub = Subscription(user_id=user.id)
            db.session.add(sub)
        
        sub.plan = plan_enum
        sub.is_active = True
        if plan_enum == PlanType.FREE:
            sub.expires_at = None
        else:
            sub.expires_at = datetime.utcnow() + timedelta(days=30)
            
        db.session.commit()
        print(f"¡Usuario {user.username} ({user.email}) actualizado exitosamente al plan {plan_enum.value}!")

if __name__ == "__main__":
    import sys
    email = "tu@gmail.com"
    plan = "PRO"
    if len(sys.argv) > 1:
        email = sys.argv[1]
    if len(sys.argv) > 2:
        plan = sys.argv[2]
        
    upgrade_user(email, plan)
