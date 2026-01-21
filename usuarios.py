from db import conectar
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def crear_usuario(nombre, email, password, rol, clases_semana):
    conn = conectar()
    c = conn.cursor()





    c.execute("""
        INSERT INTO usuarios
        (nombre, email, password, rol, clases_semana,desactivo)
        VALUES (?, ?, ?, ?, ?,0)
    """, (
        nombre,
        email,
        hash_password(password),
        rol,
        clases_semana
  
    ))

    conn.commit()
    conn.close()


def validar_login(email, password):
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        SELECT id, nombre, rol
        FROM usuarios
        WHERE email=? AND password=?
    """, (email, hash_password(password)))

    user = c.fetchone()
    conn.close()
    return user

def obtener_usuarios():
    conn = conectar()
    c = conn.cursor()

    usuarios = c.execute("""
        SELECT id, nombre, clases_semana
        FROM usuarios
        WHERE rol = 'usuario' and desactivo = 0
        ORDER BY nombre COLLATE ES
    """).fetchall()

    conn.close()
    return usuarios


def obtener_usuario_por_id(usuario_id):
    conn = conectar()
    c = conn.cursor()

    usuario = c.execute("""
        SELECT id, nombre, email, clases_semana
        FROM usuarios
        WHERE id = ?
        order by nombre COLLATE ES
    """, (usuario_id,)).fetchone()

    conn.close()
    return usuario

from datetime import date
from db import conectar

def obtener_usuarios_con_pagos(year, month):
    conn = conectar()
    c = conn.cursor()

    usuarios = c.execute("""
        SELECT
           u.id,
           u.nombre,
           u.clases_semana,
           IFNULL(p.pagado, 0) AS pagado,
           p.metodo_pago,
           p.cuota
        FROM usuarios u
        LEFT JOIN pagos p
           ON u.id = p.usuario_id
           AND p.year = ?
           AND p.month = ?
        WHERE u.rol = 'usuario'
        ORDER BY u.nombre COLLATE ES;
    """, (year, month)).fetchall()

    conn.close()
    return usuarios


def obtener_resumen_usuario(usuario_id, year, month):
    conn = conectar()
    c = conn.cursor()

    # Datos del usuario
    usuario = c.execute("""
        SELECT nombre
        FROM usuarios
        WHERE id = ?
    """, (usuario_id,)).fetchone()

    # Clases fijas a la semana
    clases_semana = c.execute("""
        SELECT clases_semana
        FROM usuarios
        WHERE id = ?
    """, (usuario_id,)).fetchone()[0]

    # Pago del mes
    pago = c.execute("""
        SELECT pagado, cuota
        FROM pagos
        WHERE usuario_id = ?
          AND year = ?
          AND month = ?
    """, (usuario_id, year, month)).fetchone()

    pagado = pago[0] if pago else 0
    cuota = pago[1] if pago else (55 if clases_semana == 1 else 90)

    # Recuperaciones activas
    recuperaciones = c.execute("""
        SELECT COUNT(*)
        FROM recuperaciones r
        JOIN clases c ON c.id = r.clase_original_id
        WHERE r.usuario_id = ?
          AND r.asignada = 0
          AND substr(r.fecha_clase, 1, 7) = ?
    """, (usuario_id, f"{year}-{month:02d}")).fetchone()[0]

    conn.close()

    return {
        "nombre": usuario[0],
        "clases_semana": clases_semana,
        "pagado": pagado,
        "cuota": cuota,
        "recuperaciones": recuperaciones
    }
