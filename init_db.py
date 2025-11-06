import psycopg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

schema_sql = """
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    contrasena TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS respuestas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    aire INTEGER,
    ruido INTEGER,
    limpieza INTEGER,
    fecha DATE NOT NULL
);
"""

print("🌱 Conectando a la base de datos...")

try:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
            conn.commit()
    print("✅ Tablas creadas correctamente.")
except Exception as e:
    print(f"❌ Error creando las tablas: {e}")
