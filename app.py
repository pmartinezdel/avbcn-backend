from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg
import os
import datetime

# -------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------
app = Flask(__name__)
CORS(app, origins="*")  # Puedes restringir a soldesable.com más adelante

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "sol_desable_arbol_vida_default")

# -------------------------------------------------------
# CONEXIÓN A LA BASE DE DATOS
# -------------------------------------------------------
def get_connection():
    """Devuelve una conexión activa a la base de datos PostgreSQL."""
    return psycopg.connect(DATABASE_URL)

# -------------------------------------------------------
# PÁGINA PRINCIPAL
# -------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -------------------------------------------------------
# ENDPOINT DE ESTADO DEL ÁRBOL
# -------------------------------------------------------
@app.route("/api/status", methods=["GET"])
def status():
    """Devuelve el estado de vitalidad del árbol y número de participantes."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(DISTINCT usuario_id), COALESCE(AVG((aire + ruido + limpieza)/3), 0) FROM respuestas;")
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
    """Registra un nuevo usuario con nombre y contraseña."""
    try:
        data = request.get_json(force=True)
        nombre = data.get("nombre", "").strip()
        contrasena = data.get("contrasena", "").strip()

        if not nombre or not contrasena:
            return jsonify({"error": "Nombre y contraseña requeridos"}), 400

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Evitar duplicados
                cur.execute("SELECT id FROM usuarios WHERE nombre = %s;", (nombre,))
                if cur.fetchone():
                    return jsonify({"error": "El usuario ya existe"}), 400

                cur.execute(
                    "INSERT INTO usuarios (nombre, contrasena) VALUES (%s, %s);",
                    (nombre, contrasena)
                )
                conn.commit()

        return jsonify({"message": f"Usuario {nombre} registrado correctamente."}), 200

    except Exception as e:
        print(f"❌ Error en /api/registrar: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

# -------------------------------------------------------
# LOGIN DE USUARIO
# -------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    """Verifica credenciales del usuario."""
    try:
        data = request.get_json(force=True)
        nombre = data.get("nombre", "").strip()
        contrasena = data.get("contrasena", "").strip()

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM usuarios WHERE nombre = %s AND contrasena = %s;", (nombre, contrasena))
                user = cur.fetchone()

        if user:
            return jsonify({"message": f"Bienvenido {nombre}", "usuario_id": user[0]}), 200
        else:
            return jsonify({"error": "Credenciales incorrectas"}), 401

    except Exception as e:
        print(f"❌ Error en /api/login: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

# -------------------------------------------------------
# ENVÍO DE RESPUESTAS
# -------------------------------------------------------
@app.route("/api/answer", methods=["POST"])
def answer():
    """Recibe respuestas del usuario y actualiza vitalidad."""
    try:
        data = request.get_json(force=True)
        usuario_id = data.get("usuario_id")
        aire = int(data.get("aire", 0))
        ruido = int(data.get("ruido", 0))
        limpieza = int(data.get("limpieza", 0))
        fecha = datetime.date.today().isoformat()

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Impedir respuestas duplicadas el mismo día
                cur.execute("SELECT id FROM respuestas WHERE usuario_id = %s AND fecha = %s;", (usuario_id, fecha))
                if cur.fetchone():
                    return jsonify({"error": "Ya has participado hoy"}), 400

                cur.execute(
                    "INSERT INTO respuestas (usuario_id, aire, ruido, limpieza, fecha) VALUES (%s, %s, %s, %s, %s);",
                    (usuario_id, aire, ruido, limpieza, fecha)
                )
                conn.commit()

        return jsonify({"message": "Respuestas registradas correctamente"}), 200

    except Exception as e:
        print(f"❌ Error en /api/answer: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
