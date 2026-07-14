import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "savewave.db")

def migrate():
    if not os.path.exists(db_path):
        print(f"Base de datos no encontrada en {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns_to_add = {
        "google_id": "VARCHAR(120)",
        "phone_number": "VARCHAR(50)",
        "is_verified": "BOOLEAN DEFAULT 0"
    }

    # Obtener columnas actuales
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [info[1] for info in cursor.fetchall()]

    for col, data_type in columns_to_add.items():
        if col not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {data_type}")
                print(f"[OK] Columna '{col}' agregada a la tabla users.")
            except Exception as e:
                print(f"[ERROR] No se pudo agregar la columna '{col}': {e}")
        else:
            print(f"[INFO] La columna '{col}' ya existe.")

    conn.commit()
    conn.close()
    print("Migración completada con éxito.")

if __name__ == "__main__":
    migrate()
