from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
import datetime
import jwt

app = Flask(__name__)
CORS(app)

# -------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "clave_secreta_segura_2025")
ADMIN_USER = os.getenv("ADMIN_USER", "sol")
ADMIN_PASS = os.getenv("ADMIN_PASS", "sable")

# -------------------------------------------------------
# CONEXIÓN A LA BASE DE DATOS
# -------------------------------------------------------
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    return conn

# -------------------------------------------------------
# PÁGINA PRINCIPAL (TEST)
# -------------------------------------------------------
@app.route("/")
def index():
    return "Backend funcionando correctamente 🌳 El servidor Flask está en ejecución en Render."

# -------------------------------------------------------
# REGISTRO DE USUARIO
# -------------------------------------------------------
@app.route("/api/registrar", methods=["POST"])
def registrar_usuario():
    try:
        data = request.get_json()
        nombre = data.get("nombre", "").strip()
        contrasena = data.get("contrasena", "").strip()

        if not nombre or not contrasena:
            return jsonify({"error": "Nombre y contraseña requeridos"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM usuarios WHERE nombre = %s;", (nombre,))
        if cur.fetchone():
            conn.close()
            return jsonify({"error": "El nombre de usuario ya existe"}), 400

        hashed = generate_password_hash(contrasena)
        cur.execute("INSERT INTO usuarios (nombre, contrasena) VALUES (%s, %s) RETURNING id;", (nombre, hashed))
        usuario_id = cur.fetchone()[0]
        conn.commit()
        conn.close()

        return jsonify({"message": "Usuario registrado con éxito", "usuario_id": usuario_id}), 200

    except Exception as e:
        print(f"❌ Error registrar_usuario(): {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

# -------------------------------------------------------
# LOGIN DE USUARIO
# -------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login_usuario():
    try:
        data = request.get_json()
        nombre = data.get("nombre", "").strip()
        contrasena = data.get("contrasena", "").strip()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, contrasena FROM usuarios WHERE nombre = %s;", (nombre,))
        row = cur.fetchone()
        conn.close()

        if not row or not check_password_hash(row[1], contrasena):
            return jsonify({"error": "Credenciales incorrectas"}), 401

        return jsonify({"message": "Login correcto", "usuario_id": row[0]}), 200

    except Exception as e:
        print(f"❌ Error login_usuario(): {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

# -------------------------------------------------------
# OBTENER PREGUNTAS ACTIVAS
# -------------------------------------------------------
@app.route("/api/preguntas_activas", methods=["GET"])
def preguntas_activas():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, tipo, texto, peso FROM preguntas WHERE activa = TRUE ORDER BY tipo;")
        preguntas = [dict(p) for p in cur.fetchall()]
        conn.close()
        return jsonify(preguntas)
    except Exception as e:
        print(f"❌ Error en /api/preguntas_activas: {e}")
        return jsonify({"error": "No se pudieron obtener las preguntas"}), 500

# -------------------------------------------------------
# GUARDAR RESPUESTAS (UNA POR DÍA Y USUARIO)
# -------------------------------------------------------
@app.route("/api/answer", methods=["POST"])
def guardar_respuestas():
    try:
        data = request.get_json()
        usuario_id = data.get("usuario_id")
        respuestas = data.get("respuestas", [])

        hoy = datetime.date.today()

        conn = get_db_connection()
        cur = conn.cursor()

        # Limitar a una participación por día
        cur.execute("SELECT COUNT(*) FROM respuestas WHERE usuario_id = %s AND fecha = %s;", (usuario_id, hoy))
        if cur.fetchone()[0] > 0:
            conn.close()
            return jsonify({"error": "Ya has participado hoy"}), 400

        # Guardar respuestas
        for r in respuestas:
            pregunta_id = r.get("pregunta_id")
            valor = r.get("valor")
            cur.execute(
                "INSERT INTO respuestas (usuario_id, pregunta_id, valor, fecha) VALUES (%s, %s, %s, %s);",
                (usuario_id, pregunta_id, valor, hoy)
            )

        conn.commit()
        conn.close()
        return jsonify({"message": "Respuestas registradas correctamente"}), 200

    except Exception as e:
        print(f"❌ Error en guardar_respuestas(): {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

# -------------------------------------------------------
# ESTADO DEL ÁRBOL
# -------------------------------------------------------
@app.route("/api/status", methods=["GET"])
def status():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT p.tipo, COALESCE(AVG(r.valor), 0)
            FROM preguntas p
            LEFT JOIN respuestas r ON p.id = r.pregunta_id
            WHERE p.activa = TRUE
            GROUP BY p.tipo;
        """)

        datos = dict(cur.fetchall())
        tronco = round(datos.get("tronco", 0), 2)
        ramas  = round(datos.get("ramas", 0), 2)
        hojas  = round(datos.get("hojas", 0), 2)

        cur.execute("SELECT COUNT(DISTINCT usuario_id) FROM respuestas;")
        participantes = cur.fetchone()[0]

        conn.close()
        return jsonify({
            "participantes": participantes,
            "tronco": tronco,
            "ramas": ramas,
            "hojas": hojas
        })

    except Exception as e:
        print(f"❌ Error en /api/status: {e}")
        return jsonify({"error": "Error al obtener el estado del árbol"}), 500

# -------------------------------------------------------
# LOGIN ADMINISTRADOR
# -------------------------------------------------------
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    try:
        data = request.get_json()
        usuario = data.get("usuario", "")
        password = data.get("password", "")

        if usuario == ADMIN_USER and password == ADMIN_PASS:
            token = jwt.encode(
                {"usuario": usuario, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=3)},
                SECRET_KEY,
                algorithm="HS256"
            )
            return jsonify({"token": token})

        return jsonify({"error": "Credenciales incorrectas"}), 401

    except Exception as e:
        print(f"❌ Error en admin_login(): {e}")
        return jsonify({"error": "Error interno"}), 500

# -------------------------------------------------------
# MIDDLEWARE AUTORIZACIÓN ADMIN
# -------------------------------------------------------
def verificar_token(req):
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return None
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded["usuario"]
    except:
        return None

# -------------------------------------------------------
# ADMIN: OBTENER TODAS LAS PREGUNTAS
# -------------------------------------------------------
@app.route("/api/admin/preguntas", methods=["GET"])
def admin_preguntas():
    admin = verificar_token(request)
    if not admin:
        return jsonify({"error": "No autorizado"}), 403
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT id, tipo, texto, peso, activa FROM preguntas ORDER BY tipo;")
        preguntas = [dict(p) for p in cur.fetchall()]
        conn.close()
        return jsonify(preguntas)
    except Exception as e:
        print(f"❌ Error en admin_preguntas(): {e}")
        return jsonify({"error": "No se pudieron obtener las preguntas"}), 500

# -------------------------------------------------------
# ADMIN: CREAR PREGUNTA NUEVA
# -------------------------------------------------------
@app.route("/api/admin/preguntas", methods=["POST"])
def admin_crear_pregunta():
    admin = verificar_token(request)
    if not admin:
        return jsonify({"error": "No autorizado"}), 403
    try:
        data = request.get_json()
        tipo = data.get("tipo")
        texto = data.get("texto")
        peso = data.get("peso", 1.0)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE preguntas SET activa = FALSE WHERE tipo = %s;", (tipo,))
        cur.execute("INSERT INTO preguntas (tipo, texto, peso, activa) VALUES (%s, %s, %s, TRUE);", (tipo, texto, peso))
        conn.commit()
        conn.close()
        return jsonify({"message": "Pregunta creada correctamente"}), 200

    except Exception as e:
        print(f"❌ Error en admin_crear_pregunta(): {e}")
        return jsonify({"error": "Error al crear pregunta"}), 500

# -------------------------------------------------------
# ADMIN: EDITAR PREGUNTA
# -------------------------------------------------------
@app.route("/api/admin/preguntas/<int:id>", methods=["PUT"])
def admin_editar_pregunta(id):
    admin = verificar_token(request)
    if not admin:
        return jsonify({"error": "No autorizado"}), 403
    try:
        data = request.get_json()
        texto = data.get("texto")
        peso = data.get("peso")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE preguntas SET texto=%s, peso=%s WHERE id=%s;", (texto, peso, id))
        conn.commit()
        conn.close()
        return jsonify({"message": "Pregunta actualizada correctamente"}), 200

    except Exception as e:
        print(f"❌ Error en admin_editar_pregunta(): {e}")
        return jsonify({"error": "Error al actualizar"}), 500

# -------------------------------------------------------
# ADMIN: BORRAR PREGUNTA
# -------------------------------------------------------
@app.route("/api/admin/preguntas/<int:id>", methods=["DELETE"])
def admin_borrar_pregunta(id):
    admin = verificar_token(request)
    if not admin:
        return jsonify({"error": "No autorizado"}), 403
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM preguntas WHERE id=%s;", (id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Pregunta eliminada"}), 200

    except Exception as e:
        print(f"❌ Error en admin_borrar_pregunta(): {e}")
        return jsonify({"error": "Error al eliminar"}), 500

# -------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
