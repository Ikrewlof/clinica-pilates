import sqlite3

def conectar():
    return sqlite3.connect("clinica.db")

def crear_tablas():
    conn = conectar()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        email TEXT,
        rol TEXT,
        clases_semana INTEGER,
        dia_fijo INTEGER,
        hora_fija TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS clases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        hora TEXT,
        capacidad INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS inscripciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        clase_id INTEGER,
        tipo TEXT,
        asistio INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS recuperaciones (
        usuario_id INTEGER,
        mes TEXT,
        disponibles INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        mes TEXT,
        importe REAL,
        estado TEXT
    )
    """)

    conn.commit()
    conn.close()


