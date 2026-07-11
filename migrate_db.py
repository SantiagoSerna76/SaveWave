import os
from sqlalchemy import create_engine, text
from config import Config
from app import app
from models import db

def migrate():
    with app.app_context():
        # Obtener URL de conexion (SQLite o MySQL)
        db_url = Config.SQLALCHEMY_DATABASE_URI
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Lista de comandos ALTER TABLE dependiente del motor
            if "sqlite" in db_url:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(120);"))
                except Exception as e:
                    print("Info: google_id quizas ya existe:", e)
                    
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR(50);"))
                except Exception as e:
                    print("Info: phone_number quizas ya existe:", e)
                    
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0;"))
                except Exception as e:
                    print("Info: is_verified quizas ya existe:", e)
            else:
                # MySQL
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(120) UNIQUE;"))
                except Exception as e:
                    print("Info: google_id quizas ya existe:", e)
                    
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR(50) UNIQUE;"))
                except Exception as e:
                    print("Info: phone_number quizas ya existe:", e)
                    
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;"))
                except Exception as e:
                    print("Info: is_verified quizas ya existe:", e)
                    
                # En MySQL hay que modificar password_hash para que acepte NULL
                try:
                    conn.execute(text("ALTER TABLE users MODIFY password_hash VARCHAR(256) NULL;"))
                except Exception as e:
                    print("Info: no se pudo modificar password_hash:", e)

            # Si son usuarios antiguos, los marcamos como verificados para no bloquearlos
            try:
                conn.execute(text("UPDATE users SET is_verified = 1;"))
                conn.commit()
            except Exception as e:
                print("Error actualizando usuarios antiguos:", e)
                
        print("Migracion completada con exito.")

if __name__ == "__main__":
    migrate()
