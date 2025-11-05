-- TABLAS
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS answers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    question_id INTEGER REFERENCES questions(id),
    value INTEGER CHECK (value BETWEEN 1 AND 10),
    created_at TIMESTAMP DEFAULT NOW()
);

-- USUARIO ADMIN
INSERT INTO users (username, password_hash, is_admin)
VALUES ('admin', '$pbkdf2-sha256$29000$adminhashfalso', TRUE)
ON CONFLICT DO NOTHING;

-- PREGUNTAS INICIALES
INSERT INTO questions (text, weight) VALUES
('Nivel de limpieza de la ciudad', 1.0),
('Calidad del aire', 1.5),
('Nivel de ruido urbano', 0.8);
