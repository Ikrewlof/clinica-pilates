import calendar
from datetime import date
from db import conectar


from db import conectar

def crear_clase_base(dia_semana, hora, capacidad, descripcion):
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        INSERT INTO clases_base (dia_semana, hora, capacidad, descripcion)
        VALUES (?, ?, ?,?)
    """, (dia_semana, hora, capacidad, descripcion))

    conn.commit()
    conn.close()


def obtener_clases_base():
    conn = conectar()
    c = conn.cursor()

    clases = c.execute("""
        SELECT id, dia_semana, hora, capacidad, descripcion
        FROM clases_base
        ORDER BY dia_semana, hora
    """).fetchall()

    conn.close()
    return clases


import calendar
from datetime import date
from db import conectar

def generar_clases_mes_desde_base(year, month):
    conn = conectar()
    c = conn.cursor()

    clases_base = c.execute("""
        SELECT id, dia_semana, hora, capacidad, descripcion
        FROM clases_base
    """).fetchall()

    _, dias_mes = calendar.monthrange(year, month)

    for dia in range(1, dias_mes + 1):
        fecha = date(year, month, dia)

        for cb in clases_base:
            clase_base_id, dia_semana, hora, capacidad, descripcion = cb

            if fecha.weekday() == dia_semana:
                c.execute("""
                    INSERT INTO clases (fecha, hora, capacidad, clase_base_id, descripcion)
                    VALUES (?, ?, ?, ?,?)
                """, (
                    fecha.isoformat(),
                    hora,
                    capacidad,
                    clase_base_id
                ))

    conn.commit()
    conn.close()

def crear_clase_manual(fecha, hora, capacidad, descripcion):
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        INSERT INTO clases (fecha, hora, capacidad, clase_base_id, descripcion)
        VALUES (?, ?, ?, NULL, ?)
    """, (fecha, hora, capacidad))

    conn.commit()
    conn.close()

from db import conectar

def mes_ya_generado(year, month):
    conn = conectar()
    c = conn.cursor()

    existe = c.execute("""
        SELECT 1
        FROM clases
        WHERE substr(fecha, 1, 7) = ?
        LIMIT 1
    """, (f"{year}-{month:02d}",)).fetchone()

    conn.close()
    return existe is not None


from db import conectar

def obtener_clases_mes(year, month):
    conn = conectar()
    c = conn.cursor()

    clases = c.execute("""
        SELECT
            c.id,
            c.fecha,
            c.hora,
            c.capacidad,
            cb.dia_semana,
            cb.hora,
            cb.descripcion
        FROM clases c
        LEFT JOIN clases_base cb ON cb.id = c.clase_base_id
        WHERE substr(c.fecha, 1, 7) = ?
        ORDER BY c.fecha, c.hora
    """, (f"{year}-{month:02d}",)).fetchall()

    conn.close()
    return clases

from db import conectar

def obtener_usuarios():
    conn = conectar()
    c = conn.cursor()
    usuarios = c.execute("""
        SELECT id, nombre, clases_semana
        FROM usuarios
        WHERE rol='usuario'
        ORDER BY nombre
    """).fetchall()
    conn.close()
    return usuarios




import calendar
from datetime import date
from db import conectar

def generar_inscripciones_mes(year, month):
    conn = conectar()
    c = conn.cursor()

    # Evitar generar dos veces el mismo mes
    existe = c.execute("""
        SELECT 1 FROM clases
        WHERE substr(fecha, 1, 7) = ?
        LIMIT 1
    """, (f"{year}-{month:02d}",)).fetchone()

    if existe:
        conn.close()
        return False, "El mes ya estaba generado"

    # Clases base (incluimos hora y capacidad)
    clases_base = c.execute("""
        SELECT id, dia_semana, hora, capacidad, descripcion
        FROM clases_base where activa=1
    """).fetchall()

    _, dias_mes = calendar.monthrange(year, month)

    for dia in range(1, dias_mes + 1):
        fecha = date(year, month, dia)
        fecha_str = fecha.isoformat()
        dia_semana = fecha.weekday()  # 0 = lunes

        # 🔹 ¿Es festivo?
        festivo = c.execute("""
            SELECT motivo
            FROM festivos
            WHERE fecha = ?
        """, (fecha_str,)).fetchone()
        
        es_festivo = 1 if festivo else 0
        motivo_festivo = festivo[0] if festivo else None
        
        for clase_base_id, cb_dia, hora, capacidad, descripcion in clases_base:
            if cb_dia == dia_semana:
                # Crear clase real del mes
                c.execute("""
                    INSERT INTO clases (clase_base_id, fecha, hora, capacidad,dia_semana,es_festivo,motivo_festivo, descripcion)
                    VALUES (?, ?, ?, ?,?,?,?,?)
                """, (clase_base_id, fecha.isoformat(), hora, capacidad,dia_semana, es_festivo, motivo_festivo, descripcion))

                clase_id = c.lastrowid

                # 🔴 IMPORTANTE: si es festivo NO se inscribe nadie
                if es_festivo:
                    continue

                # Inscribir usuarios fijos
                usuarios = c.execute("""
                    SELECT usuario_id
                    FROM asignaciones_fijas
                    WHERE clase_base_id = ?
                """, (clase_base_id,)).fetchall()

                for (usuario_id,) in usuarios:
                    c.execute("""
                        INSERT OR IGNORE INTO inscripciones (usuario_id, clase_id)
                        VALUES (?, ?)
                    """, (usuario_id, clase_id))

    conn.commit()
    conn.close()
    return True, "Mes generado correctamente"


# =========================
# OBTENER ASIGNACIONES DE UN USUARIO
# =========================

def obtener_asignaciones_usuario(usuario_id):
    conn = conectar()
    c = conn.cursor()

    filas = c.execute("""
        SELECT clase_base_id
        FROM asignaciones_fijas
        WHERE usuario_id = ?
    """, (usuario_id,)).fetchall()

    conn.close()
    return [f[0] for f in filas]


# =========================
# ASIGNAR CLASE FIJA
# =========================

def asignar_clase_fija(usuario_id, clase_base_id):
    conn = conectar()
    c = conn.cursor()

    # límite de clases del usuario
    max_clases = c.execute("""
        SELECT clases_semana
        FROM usuarios
        WHERE id = ?
    """, (usuario_id,)).fetchone()[0]

    # clases ya asignadas
    actuales = c.execute("""
        SELECT COUNT(*)
        FROM asignaciones_fijas
        WHERE usuario_id = ?
    """, (usuario_id,)).fetchone()[0]

    if actuales >= max_clases:
        conn.close()
        return False, "El usuario ya tiene el máximo de clases permitidas"

    try:
        c.execute("""
            INSERT INTO asignaciones_fijas (usuario_id, clase_base_id)
            VALUES (?, ?)
        """, (usuario_id, clase_base_id))
        conn.commit()
    except:
        conn.close()
        return False, "Esta clase ya está asignada"

    conn.close()
    return True, "Clase asignada correctamente"


# =========================
# QUITAR ASIGNACIÓN
# =========================

def quitar_asignacion(usuario_id, clase_base_id):
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        DELETE FROM asignaciones_fijas
        WHERE usuario_id = ? AND clase_base_id = ?
    """, (usuario_id, clase_base_id))

    conn.commit()
    conn.close()

def obtener_clases_base_con_ocupacion():
    conn = conectar()
    c = conn.cursor()

    clases = c.execute("""
        SELECT
            cb.id,
            cb.dia_semana,
            cb.hora,
            cb.descripcion,
            COUNT(af.id) as ocupacion,
            cb.capacidad,            
            cb.activa     
        FROM clases_base cb
        LEFT JOIN asignaciones_fijas af
            ON cb.id = af.clase_base_id
        GROUP BY
            cb.id,
            cb.dia_semana,
            cb.hora,
            cb.capacidad,
            cb.activa
        ORDER BY
            cb.dia_semana,
            cb.hora
    """).fetchall()

  

    conn.close()
    return clases



from datetime import date
import calendar

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

def obtener_calendario_mes(year, month):
    conn = conectar()
    c = conn.cursor()

    filas = c.execute("""
        SELECT
            c.id,
            c.fecha,
            c.hora,
            c.descripcion,
            c.capacidad,
            u.id,
            u.nombre,
            c.es_festivo,
            c.motivo_festivo
        FROM clases c
        LEFT JOIN inscripciones i ON i.clase_id = c.id
        LEFT JOIN usuarios u ON u.id = i.usuario_id
        WHERE substr(c.fecha, 1, 7) = ?
        ORDER BY c.fecha, c.hora
    """, (f"{year}-{month:02d}",)).fetchall()

    conn.close()

    # 📅 Cuántos días tiene el mes
    _, total_dias = calendar.monthrange(year, month)

    # 🧱 Crear calendario vacío con TODOS los días
    calendario = []

    for dia in range(1, total_dias + 1):
        fecha_obj = date(year, month, dia)

        calendario.append({
            "fecha": fecha_obj.isoformat(),
            "dia_num": dia,
            "dia_semana": DIAS[fecha_obj.weekday()],
            "weekday": fecha_obj.weekday(),  # 0=lunes
            "es_hoy": fecha_obj == date.today(),
            "clases": {}
        })

    # 🔗 Index rápido por fecha
    index = {d["fecha"]: d for d in calendario}

    # ➕ Meter las clases dentro del día correcto
    for clase_id, fecha, hora, descripcion, capacidad, usuario_id, nombre, es_festivo, motivo_festivo in filas:

        dia = index[fecha]

        if clase_id not in dia["clases"]:
            dia["clases"][clase_id] = {
                "id": clase_id,
                "hora": hora,
                "descripcion": descripcion,
                "capacidad": capacidad,
                "usuarios": [],
                "es_festivo": es_festivo,
                "motivo_festivo": motivo_festivo
            }

        if usuario_id:
            dia["clases"][clase_id]["usuarios"].append({
                "id": usuario_id,
                "nombre": nombre
            })

    return calendario



from db import conectar
from datetime import datetime
from datetime import date


def inscribir_usuario_desde_hoy(usuario_id):
    hoy = date.today().isoformat()

    conn = conectar()
    c = conn.cursor()

    # Clases base asignadas al usuario
    clases_base = c.execute("""
        SELECT clase_base_id
        FROM asignaciones_fijas
        WHERE usuario_id = ?
    """, (usuario_id,)).fetchall()

    for (clase_base_id,) in clases_base:
        # Clases futuras del mes ya generadas
        clases_futuras = c.execute("""
            SELECT id
            FROM clases
            WHERE clase_base_id = ?
              AND fecha >= ?
        """, (clase_base_id, hoy)).fetchall()

        for (clase_id,) in clases_futuras:
            c.execute("""
                INSERT OR IGNORE INTO inscripciones (usuario_id, clase_id)
                VALUES (?, ?)
            """, (usuario_id, clase_id))

    conn.commit()
    conn.close()
