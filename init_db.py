import psycopg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# -------------------------------------------------------
# Definición del esquema de base de datos
# -------------------------------------------------------
schema_sql = """
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nombre TEXT UNIQUE NOT NULL,
    contrasena TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS respuestas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    aire INTEGER DEFAULT 0,
    ruido INTEGER DEFAULT 0,
    limpieza INTEGER DEFAULT 0,
    fecha DATE NOT NULL,
    CONSTRAINT respuestas_usuario_id_fkey
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
);
"""

# -------------------------------------------------------
# Ejecución
# -------------------------------------------------------
def main():
    print("🌱 Inicializando base de datos Árbol de la Vida de Barcelona...")

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
                conn.commit()

                # Comprobar que las tablas existen
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
                tablas = [t[0] for t in cur.fetchall()]
                print(f"✅ Tablas disponibles: {', '.join(tablas)}")

                # Comprobar la clave foránea
                cur.execute("""
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE table_name='respuestas' AND constraint_type='FOREIGN KEY';
                """)
                fk = cur.fetchone()
                if fk:
                    print(f"🔗 Clave foránea activa: {fk[0]}")
                else:
                    print("⚠️ No se encontró clave foránea en 'respuestas'.")

        print("✅ Base de datos inicializada correctamente.")

    except Exception as e:
        print(f"❌ Error al inicializar la base de datos: {e}")


if __name__ == "__main__":
    main()
