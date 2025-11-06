from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg
import os
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------------------------------------------
# CONFIGURACIÓN GENERAL
# -------------------------------------------------------
app = Flask(__name__)

# Solo se permite acceso desde tu dominio artístico
CORS(app, resources={
    r"/*": {"origins": [
        "https://soldesable.com",
        "https://www.soldesable.com"
    ]}
})

DATABASE_URL = os.getenv("DATABASE_URL")


# -------------------------------------------------------
# CONEXIÓN A LA BASE DE DATOS
# -------------------------------------------------------
def get_connection():
    return psycopg.connect(DATABASE_URL)


# -------------------------------------------------------
# RUTA PRINCIPAL
# -------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# -------------------------------------------------------
# OBTENER ESTADO DEL ÁRBOL
# -------------------------------------------------------
@app.route("/api/status", methods=["GET"])
def status():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(DISTINCT usuario_id),
                           COALESCE(AVG((aire + ruido + limpieza)/3), 0)
                    FROM respuestas;
                """)
                row = cur.fetchone()
                participantes = row[0] or 0
                vitalidad = float(row[1]) if row[1] is not None else 0.0

        return jsonify({
            "participantes": participantes,
            "vitalidad": round(vitalidad, 2)
        })

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
                # Verificar si ya existe
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

        if not nombre or not contrasena:
            return jsonify({"error": "Nombre y contraseña requeridos"}), 400

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
# ENVÍO DE RESPUESTAS (una vez al día)
# -------------------------------------------------------
@app.route("/api/answer", methods=["POST"])
def answer():
    try:
        data = request.get_json(force=True)
        usuario_id = int(data.get("usuario_id"))
        aire = int(data.get("aire", 0))
        ruido = int(data.get("ruido", 0))
        limpieza = int(data.get("limpieza", 0))
        fecha = datetime.date.today().isoformat()

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Verificar si ya ha participado hoy
                cur.execute("""
                    SELECT id FROM respuestas
                    WHERE usuario_id = %s AND fecha = %s;
                """, (usuario_id, fecha))
                if cur.fetchone():
                    return jsonify({"error": "Ya has participado hoy"}), 400

                # Insertar nueva respuesta
                cur.execute("""
                    INSERT INTO respuestas (usuario_id, aire, ruido, limpieza, fecha)
                    VALUES (%s, %s, %s, %s, %s);
                """, (usuario_id, aire, ruido, limpieza, fecha))
                conn.commit()

        return jsonify({"message": "Respuestas registradas correctamente."}), 200

    except Exception as e:
        print(f"❌ Error en /api/answer: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


# -------------------------------------------------------
# EJECUCIÓN LOCAL (debug)
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
