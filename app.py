from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg
import os
import datetime
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------------------------------------------
# CONFIGURACIÓN GENERAL
# -------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://soldesable.com", "https://www.soldesable.com"]}})

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "1234")

admin_sessions = {}  # tokens activos para el panel admin


def get_connection():
    return psycopg.connect(DATABASE_URL)


# -------------------------------------------------------
# RUTA PRINCIPAL
# -------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# -------------------------------------------------------
# ESTADO DEL ÁRBOL: cálculo de tronco, ramas y hojas
# -------------------------------------------------------
@app.route("/api/status", methods=["GET"])
def status():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # obtener promedios por tipo de pregunta
                cur.execute("""
                    SELECT p.tipo, COALESCE(AVG(r.valor), 0)
                    FROM preguntas p
                    LEFT JOIN respuestas r ON p.id = r.pregunta_id
                    WHERE p.activa = TRUE
                    GROUP BY p.tipo;
                """)
                datos = dict(cur.fetchall())

                # número total de participantes (usuarios únicos que respondieron hoy)
                cur.execute("SELECT COUNT(DISTINCT usuario_id) FROM respuestas;")
                participantes = cur.fetchone()[0]

        resultado = {
            "participantes": participantes,
            "tronco": round(datos.get("tronco", 0), 2),
            "ramas": round(datos.get("ramas", 0), 2),
            "hojas": round(datos.get("hojas", 0), 2)
        }
        return jsonify(resultado)

    except Exception as e:
        print(f"❌ Error en /api/status: {e}")
        return jsonify({"error": "Error al obtener el estado del árbol"}), 500


# -------------------------------------------------------
# REGISTRO DE USUARIO
# -------------------------------------------------------
@app.route("/api/registrar", methods=["POST"])
def registrar():
    try:
        data = request.get_json(force=True)
        nombre = data.get("nombre", "").strip()
        contrasena = data.get("contrasena", "").strip()

        if not nombre or not contrasena:
            return jsonify({"error": "Nombre y contraseña requeridos"}), 400

        hashed = generate_password_hash(contrasena)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM usuarios WHERE nombre = %s;", (nombre,))
                if cur.fetchone():
                    return jsonify({"error": "El usuario ya existe"}), 400

                cur.execute("INSERT INTO usuarios (nombre, contrasena) VALUES (%s, %s);", (nombre, hashed))
                conn.commit()

        return jsonify({"message": "Usuario registrado correctamente."}), 200

    except Exception as e:
        print(f"❌ Error en /api/registrar: {e}")
        return jsonify({"error": "Error interno en el servidor"}), 500


# -------------------------------------------------------
# LOGIN DE USUARIO
# -------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json(force=True)
        nombre = data.get("nombre", "").strip()
        contrasena = data.get("contrasena", "").strip()

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, contrasena FROM usuarios WHERE nombre = %s;", (nombre,))
                user = cur.fetchone()

        if not user or not check_password_hash(user[1], contrasena):
            return jsonify({"error": "Credenciales incorrectas"}), 401

        return jsonify({"message": "Login correcto", "usuario_id": user[0]}), 200

    except Exception as e:
        print(f"❌ Error en /api/login: {e}")
        return jsonify({"error": "Error interno en el servidor"}), 500


# -------------------------------------------------------
# PARTICIPACIÓN (una vez por día, tres respuestas)
# -------------------------------------------------------
@app.route("/api/answer", methods=["POST"])
def answer():
    try:
        data = request.get_json(force=True)
        usuario_id = int(data.get("usuario_id"))
        respuestas = data.get("respuestas", [])
        fecha = datetime.date.today().isoformat()

        with get_connection() as conn:
            with conn.cursor() as cur:
                # verificar si ya participó hoy
                cur.execute("SELECT id FROM respuestas WHERE usuario_id = %s AND fecha = %s;", (usuario_id, fecha))
                if cur.fetchone():
                    return jsonify({"error": "Ya has participado hoy"}), 400

                # guardar las tres respuestas
                for r in respuestas:
                    pregunta_id = int(r["pregunta_id"])
                    valor = int(r["valor"])
                    cur.execute(
                        "INSERT INTO respuestas (usuario_id, pregunta_id, valor, fecha) VALUES (%s, %s, %s, %s);",
                        (usuario_id, pregunta_id, valor, fecha)
                    )
                conn.commit()

        return jsonify({"message": "Respuestas registradas correctamente"}), 200

    except Exception as e:
        print(f"❌ Error en /api/answer: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


# -------------------------------------------------------
# OBTENER PREGUNTAS ACTIVAS (para usuarios)
# -------------------------------------------------------
@app.route("/api/preguntas_activas", methods=["GET"])
def preguntas_activas():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, tipo, texto, peso FROM preguntas WHERE activa = TRUE;")
                preguntas = [{"id": r[0], "tipo": r[1], "texto": r[2], "peso": r[3]} for r in cur.fetchall()]
        return jsonify(preguntas)
    except Exception as e:
        print(f"❌ Error en /api/preguntas_activas: {e}")
        return jsonify({"error": "Error al obtener las preguntas"}), 500


# -------------------------------------------------------
# MÓDULO ADMINISTRADOR
# -------------------------------------------------------

# --- Login de administrador ---
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(force=True)
    user = data.get("usuario")
    pwd = data.get("password")
    if user == ADMIN_USER and pwd == ADMIN_PASS:
        token = secrets.token_hex(16)
        admin_sessions[token] = True
        return jsonify({"token": token})
    return jsonify({"error": "Credenciales incorrectas"}), 401


# --- Middleware simple de autenticación ---
def require_admin(func):
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token not in admin_sessions:
            return jsonify({"error": "Acceso no autorizado"}), 403
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# --- Listar todas las preguntas ---
@app.route("/api/admin/preguntas", methods=["GET"])
@require_admin
def admin_get_preguntas():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, tipo, texto, peso, activa FROM preguntas ORDER BY tipo;")
                data = [{"id": r[0], "tipo": r[1], "texto": r[2], "peso": r[3], "activa": r[4]} for r in cur.fetchall()]
        return jsonify(data)
    except Exception as e:
        print(f"❌ Error admin_get_preguntas: {e}")
        return jsonify({"error": "Error al obtener preguntas"}), 500


# --- Crear o reemplazar pregunta por tipo ---
@app.route("/api/admin/preguntas", methods=["POST"])
@require_admin
def admin_crear_pregunta():
    try:
        data = request.get_json(force=True)
        tipo = data.get("tipo")
        texto = data.get("texto")
        peso = float(data.get("peso", 1.0))

        if tipo not in ("tronco", "ramas", "hojas"):
            return jsonify({"error": "Tipo inválido"}), 400

        with get_connection() as conn:
            with conn.cursor() as cur:
                # desactivar la anterior de ese tipo
                cur.execute("UPDATE preguntas SET activa = FALSE WHERE tipo = %s;", (tipo,))
                # insertar nueva activa
                cur.execute("INSERT INTO preguntas (tipo, texto, peso, activa) VALUES (%s, %s, %s, TRUE);",
                            (tipo, texto, peso))
                conn.commit()

        return jsonify({"message": f"Nueva pregunta activa creada para {tipo}."}), 200

    except Exception as e:
        print(f"❌ Error admin_crear_pregunta: {e}")
        return jsonify({"error": "Error al crear pregunta"}), 500


# --- Editar peso o texto ---
@app.route("/api/admin/preguntas/<int:pid>", methods=["PUT"])
@require_admin
def admin_editar_pregunta(pid):
    try:
        data = request.get_json(force=True)
        texto = data.get("texto")
        peso = float(data.get("peso", 1.0))

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE preguntas SET texto=%s, peso=%s WHERE id=%s;", (texto, peso, pid))
                conn.commit()
        return jsonify({"message": "Pregunta actualizada"}), 200

    except Exception as e:
        print(f"❌ Error admin_editar_pregunta: {e}")
        return jsonify({"error": "Error al editar pregunta"}), 500


# --- Eliminar pregunta ---
@app.route("/api/admin/preguntas/<int:pid>", methods=["DELETE"])
@require_admin
def admin_borrar_pregunta(pid):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM preguntas WHERE id=%s;", (pid,))
                conn.commit()
        return jsonify({"message": "Pregunta eliminada"}), 200
    except Exception as e:
        print(f"❌ Error admin_borrar_pregunta: {e}")
        return jsonify({"error": "Error al eliminar pregunta"}), 500


# -------------------------------------------------------
# EJECUCIÓN LOCAL
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
