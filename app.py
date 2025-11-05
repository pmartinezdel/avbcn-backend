from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import jwt
import datetime
import os

app = Flask(__name__)
CORS(app)

# ===============================
# CONFIGURACIÓN
# ===============================
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "dev-secret-key")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/arbolvida")

# ===============================
# CONEXIÓN A BD
# ===============================
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ===============================
# AUTH DECORADOR
# ===============================
def token_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        if not token:
            return jsonify({'error': 'Token ausente'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = data['user_id']
        except Exception:
            return jsonify({'error': 'Token inválido'}), 401
        return f(user_id, *args, **kwargs)
    return decorated

# ===============================
# ENDPOINTS
# ===============================

@app.route("/")
def index():
    return jsonify({"message": "API Árbol de la Vida funcionando."})

# ---------- Registro ----------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    nombre = data.get("nombre", "").strip()
    contrasena = data.get("contrasena", "").strip()

    if not nombre or not contrasena:
        return jsonify({"error": "Faltan datos"}), 400

    hashed = generate_password_hash(contrasena)
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, password_hash) VALUES (%s,%s)", (nombre, hashed))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Usuario registrado con éxito"}), 200
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "El nombre de usuario ya existe"}), 400
    except Exception as e:
        print("❌ Error en registro:", e)
        return jsonify({"error": "Error interno"}), 500

# ---------- Login ----------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    nombre = data.get("nombre", "").strip()
    contrasena = data.get("contrasena", "").strip()

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, password_hash, is_admin FROM users WHERE username=%s", (nombre,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], contrasena):
        return jsonify({"error": "Credenciales incorrectas"}), 401

    token = jwt.encode({
        "user_id": user["id"],
        "is_admin": user["is_admin"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({"token": token, "usuario_id": user["id"], "is_admin": user["is_admin"]}), 200

# ---------- Participar ----------
@app.route("/api/answer", methods=["POST"])
@token_required
def answer(user_id):
    data = request.get_json(force=True)
    answers = data.get("answers", {})  # {question_id: value}

    if not answers:
        return jsonify({"error": "No se han recibido respuestas"}), 400

    try:
        conn = get_conn()
        cur = conn.cursor()
        for qid, value in answers.items():
            cur.execute(
                "INSERT INTO answers (user_id, question_id, value, created_at) VALUES (%s,%s,%s,NOW())",
                (user_id, qid, value)
            )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Respuestas registradas"}), 200
    except Exception as e:
        print("❌ Error en answer:", e)
        return jsonify({"error": "Error interno"}), 500

# ---------- Estado general del árbol ----------
@app.route("/api/status", methods=["GET"])
def status():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM answers")
    total_participantes = cur.fetchone()[0]

    cur.execute("""
        SELECT q.text, AVG(a.value), q.weight
        FROM questions q
        LEFT JOIN answers a ON a.question_id = q.id
        WHERE q.active = TRUE
        GROUP BY q.id
    """)
    resultados = cur.fetchall()
    cur.close()
    conn.close()

    if not resultados:
        return jsonify({"total": total_participantes, "vitality": 0, "metrics": []})

    sum_w = sum([r[2] for r in resultados])
    vitality = sum([(r[1] or 0) * r[2] for r in resultados]) / sum_w if sum_w else 0

    metrics = [{"question": r[0], "avg": r[1] or 0, "weight": r[2]} for r in resultados]
    return jsonify({"total": total_participantes, "vitality": round(vitality, 2), "metrics": metrics})

# ---------- Admin: CRUD preguntas ----------
@app.route("/api/admin/questions", methods=["GET"])
@token_required
def admin_get_questions(user_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, text, weight, active FROM questions ORDER BY id")
    data = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(data)

@app.route("/api/admin/questions", methods=["POST"])
@token_required
def admin_add_question(user_id):
    data = request.get_json(force=True)
    text = data.get("text", "")
    weight = float(data.get("weight", 1.0))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO questions (text, weight, active) VALUES (%s,%s,TRUE)", (text, weight))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Pregunta añadida"})

@app.route("/api/admin/questions/<int:qid>", methods=["PUT"])
@token_required
def admin_edit_question(user_id, qid):
    data = request.get_json(force=True)
    text = data.get("text")
    weight = float(data.get("weight", 1.0))
    active = data.get("active", True)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE questions SET text=%s, weight=%s, active=%s WHERE id=%s",
                (text, weight, active, qid))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Pregunta actualizada"})

if __name__ == "__main__":
    app.run(debug=True)
