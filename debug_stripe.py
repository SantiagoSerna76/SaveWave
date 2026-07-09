from app import app
from models import User, PlanType
from payments import create_checkout_session
import sys
import traceback

def debug_stripe(email):
    print(f"Buscando usuario {email}...")
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print("ERROR: Usuario no encontrado en la BD.")
            return
            
        print(f"Usuario encontrado: ID={user.id}, Email={user.email}")
        
        try:
            print("Llamando a create_checkout_session...")
            result = create_checkout_session(PlanType.PREMIUM, user)
            print("Resultado:", result)
        except Exception as e:
            print("\n!!! EXCEPCION ATRAPADA !!!\n")
            traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python debug_stripe.py <tu_email>")
        sys.exit(1)
    debug_stripe(sys.argv[1])
