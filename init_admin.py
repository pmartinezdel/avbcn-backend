import psycopg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# -------------------------------------------------------
# SQL de creación de tablas y configuración base
# -------------------------------------------------------
schema_sql = """
-- Crear tabla de preguntas
CREATE TABLE IF NOT EXISTS preguntas (
    id SERIAL PRIMARY KEY,
    tipo TEXT CHECK(tipo IN ('tronco','ramas','hojas')) NOT NULL,
    texto TEXT NOT NULL,
    peso REAL DEFAULT 1.0,
    activa BOOLEAN DEFAULT TRUE
);

-- Crear tabla de respuestas (si no existe)
CREATE TABLE IF NOT EXISTS respuestas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    pregunta_id INTEGER NOT NULL REFERENCES preguntas(id) ON DELETE CASCADE,
    valor INTEGER CHECK(valor BETWEEN 1 AND 10),
    fecha DATE NOT NULL
);
"""

# Preguntas iniciales (las tres dimensiones del árbol)
preguntas_base = [
    ("tronco", "¿Cómo valoras la calidad del aire hoy en tu entorno?", 1.0, True),
    ("ramas", "¿Cómo valoras el nivel de ruido o tranquilidad?", 1.0, True),
    ("hojas", "¿Cómo valoras la limpieza de tu entorno?", 1.0, True)
]

# -------------------------------------------------------
# Función principal
# -------------------------------------------------------
def main():
    print("🌿 Inicializando base de datos con módulo de administración...")

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                # Crear tablas
                cur.execute(schema_sql)
                conn.commit()

                # Comprobar si ya hay preguntas
                cur.execute("SELECT COUNT(*) FROM preguntas;")
                count = cur.fetchone()[0]

                if count == 0:
                    print("🪴 Insertando preguntas base...")
                    cur.executemany(
                        "INSERT INTO preguntas (tipo, texto, peso, activa) VALUES (%s, %s, %s, %s);",
                        preguntas_base
                    )
                    conn.commit()
                    print("✅ Preguntas iniciales creadas.")
                else:
                    print(f"ℹ️ Ya existen {count} preguntas registradas. No se insertaron nuevas.")

                # Verificar estructura final
                cur.execute("SELECT id, tipo, texto, activa FROM preguntas;")
                rows = cur.fetchall()
                print("\n📋 Preguntas disponibles:")
                for r in rows:
                    estado = "🟢" if r[3] else "🔴"
                    print(f" {estado} [{r[1]}] {r[2]} (ID {r[0]})")

        print("\n✅ Base de datos actualizada correctamente para el módulo de administración.")

    except Exception as e:
        print(f"❌ Error al inicializar la base de datos: {e}")


if __name__ == "__main__":
    main()
