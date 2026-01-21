from auth import login_required, role_required
from flask import Flask, render_template, request, redirect, session, abort, flash,url_for
from db import conectar
from usuarios import validar_login,crear_usuario,obtener_usuarios, obtener_usuario_por_id,obtener_resumen_usuario
from clases import generar_clases_mes_desde_base
from clases import crear_clase_base, obtener_clases_base
from clases import obtener_clases_mes, mes_ya_generado
from clases import (
    obtener_clases_base,
    obtener_asignaciones_usuario,
    obtener_clases_base_con_ocupacion,
    asignar_clase_fija,
    quitar_asignacion
)
from clases import generar_inscripciones_mes
from clases import obtener_calendario_mes
from clases import inscribir_usuario_desde_hoy
import hashlib
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response
from werkzeug.middleware.proxy_fix import ProxyFix







app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = "clave_secreta_clinica"



@app.route("/debug-sesion")
def debug_sesion():
    return {
        "user_id": session.get("user_id"),
        "role": session.get("rol")
    }


@app.route("/", methods=["GET", "POST"])
def login():
    error = None



    if request.method == "POST":
        user = validar_login(
            request.form["email"],
            request.form["password"]
        )

        if user:
            session["user_id"] = user[0]
            session["nombre"]=user[1]
            session["rol"] = user[2]

            if user[2] == "admin":
                return redirect("/pilates/admin")
            else:
                return redirect("/pilates/usuario")
        else:
            error = "Usuario o contraseña incorrectos"

    return render_template("login.html", error=error)


@app.route("/admin")
@login_required
@role_required("admin")

def admin():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

   

    return render_template("admin.html")

#GENERAR MES

@app.route("/admin/generar_mes", methods=["GET"])
@login_required
@role_required("admin")
def admin_generar_mes():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    return render_template("generar_mes.html")


@app.route("/admin/generar_mes", methods=["POST"])
@login_required
@role_required("admin")
def admin_generar_mes_post():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    mes = request.form.get("mes")  # formato YYYY-MM
    year, month = map(int, mes.split("-"))


    ok, mensaje = generar_inscripciones_mes(year, month)
    flash(mensaje, "success" if ok else "warning")

    return redirect("/pilates/admin")

#mes activo

@app.route("/admin/mes_activo", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_mes_activo():
    if session.get("rol") != "admin":
        abort(403)

    if request.method == "POST":
        mes = request.form["mes"]           # "2026-01"
        year, month = map(int, mes.split("-"))
        
        
        conn = conectar()
        c = conn.cursor()

        c.execute("""
        UPDATE configuracion
        SET year = ?, month = ?
        WHERE id = 1
        """, (year, month))

        conn.commit()
        conn.close()
        
                
        flash("Mes activo actualizado correctamente", "success")
        return redirect("/pilates/admin/mes_activo/")

    year, month = obtener_mes_activo()

    mes_activo = f"{year}-{month:02d}"     # 🔑 para el input type="month"

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    mes_literal = meses[month - 1]

    return render_template(
        "admin_mes_activo.html",
        year=year,
        month=month,
        mes_activo=mes_activo,
        mes_literal=mes_literal
    )


def obtener_mes_activo():
    conn = conectar()
    c = conn.cursor()

    fila = c.execute("""
        SELECT year, month
        FROM configuracion
        WHERE id = 1
    """).fetchone()

    conn.close()

    return fila[0], fila[1]



#obtener las clases del mes

@app.route("/admin/clases_mes")
@login_required
@role_required("admin")
def admin_clases_mes():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    mes = request.args.get("mes")

    if mes:
        year, month = map(int, mes.split("-"))
    else:
        year, month = obtener_mes_activo()

    #calendario = obtener_calendario_mes(year, month)

    calendario, offset = obtener_calendario_mes(year, month)
  


    return render_template(
        "clases_mes.html",
        calendario=calendario,
        offset=offset,
        year=year,
        month=month
    )


#quitar usuarios en el mes

@app.route("/admin/clases_mes/quitar", methods=["POST"])
@login_required
@role_required("admin")
def admin_quitar_usuario_clase():
    if session.get("rol") != "admin":
        abort(403)

    usuario_id = int(request.form["usuario_id"])
    clase_id = int(request.form["clase_id"])

    conn = conectar()
    c = conn.cursor()

    # 1️⃣ Obtener fecha de la clase
    fecha = c.execute("""
        SELECT fecha FROM clases WHERE id = ?
    """, (clase_id,)).fetchone()[0]

    # 2️⃣ Borrar inscripción
    c.execute("""
        DELETE FROM inscripciones
        WHERE usuario_id = ? AND clase_id = ?
    """, (usuario_id, clase_id))

    # 3️⃣ Insertar recuperación pendiente
    c.execute("""
        INSERT INTO recuperaciones
        (usuario_id, clase_original_id, fecha_clase, fecha_creacion)
        VALUES (?, ?, ?, date('now'))
    """, (usuario_id, clase_id, fecha))

    conn.commit()
    conn.close()

    flash("Usuario quitado y marcado para recuperación", "success")
    #return redirect(url_for("admin_clases_mes"))
    return redirect("/pilates/admin_clases_mes")

#recuperaciones 

@app.route("/admin/recuperaciones")
@login_required
@role_required("admin")
def admin_recuperaciones():
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()
    year, month = obtener_mes_activo()

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    mes_literal = meses[month - 1]

    pendientes = c.execute("""
        SELECT
           r.id,
           u.nombre,
           c.fecha,
           c.hora,
           r.especial
        FROM recuperaciones r
        JOIN usuarios u ON u.id = r.usuario_id
        JOIN clases c ON c.id = r.clase_original_id
        WHERE r.asignada = 0
           AND substr(c.fecha, 1, 7) = ?
        ORDER BY c.fecha
    """, (f"{year}-{month:02d}",)).fetchall()




    conn.close()

    return render_template(
        "recuperaciones.html",
        pendientes=pendientes,
        mes_literal=mes_literal,
        year=year
    )


import calendar
from datetime import date

@app.route("/admin/recuperaciones/asignar/<int:recuperacion_id>")
@login_required
@role_required("admin")
def admin_recuperaciones_asignar(recuperacion_id):
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()

    # 1️⃣ Datos de la recuperación
    rec = c.execute("""
        SELECT r.usuario_id, u.nombre
        FROM recuperaciones r
        JOIN usuarios u ON u.id = r.usuario_id
        WHERE r.id = ? AND r.asignada = 0
    """, (recuperacion_id,)).fetchone()

    if not rec:
        conn.close()
        flash("Recuperación no válida", "error")
        #return redirect(url_for("admin_recuperaciones"))
        return redirect("/pilates/admin_recuperaciones")
    usuario_id, nombre = rec

    # 2️⃣ Mes activo
    year, month = obtener_mes_activo()

    # 3️⃣ Clases del mes con hueco
    filas = c.execute("""
        SELECT
            c.id,
            c.fecha,
            c.hora,
            c.descripcion,
            c.capacidad,
            COUNT(i.id) AS ocupacion
        FROM clases c
        LEFT JOIN inscripciones i ON i.clase_id = c.id
        WHERE c.es_festivo = 0
          AND substr(c.fecha, 1, 7) = ?
        GROUP BY c.id, c.fecha, c.hora, c.descripcion, c.capacidad
        HAVING ocupacion < c.capacidad
        ORDER BY c.fecha, c.hora
    """, (f"{year}-{month:02d}",)).fetchall()

    conn.close()

    # 4️⃣ Agrupar clases por fecha
    clases_por_fecha = {}

    for clase_id, fecha, hora, descripcion, capacidad, ocupacion in filas:
        if fecha not in clases_por_fecha:
            clases_por_fecha[fecha] = []

        clases_por_fecha[fecha].append({
            "id": clase_id,
            "hora": hora,
            "descripcion": descripcion,
            "capacidad": capacidad,
            "ocupacion": ocupacion
        })

    # 5️⃣ Construir mes completo
    primer_dia_semana_full, total_dias = calendar.monthrange(year, month)

    # offset para calendario L-V: si el día 1 es sábado/domingo, offset = 0 (empieza el lunes 2 en columna lunes)
    primer_dia_semana = primer_dia_semana_full if primer_dia_semana_full < 5 else 0
    dias_mes = []

    for dia in range(1, total_dias + 1):
        fecha = date(year, month, dia).isoformat()
        fecha_obj = date(year, month, dia)

        # ❌ Saltamos sábados y domingos
        if fecha_obj.weekday() >= 5:
            continue

        dias_mes.append({
            "fecha": fecha,
            "dia_num": dia,
            "dia_semana": DIAS[fecha_obj.weekday()],
            "weekday": fecha_obj.weekday(),
            "clases": clases_por_fecha.get(fecha, [])
        })

    return render_template(
        "reasignar_recuperacion.html",
        recuperacion_id=recuperacion_id,
        usuario_id=usuario_id,
        nombre=nombre,
        dias_mes=dias_mes,
        primer_dia_semana=primer_dia_semana
    )




@app.route("/admin/recuperaciones/confirmar", methods=["POST"])
@login_required
@role_required("admin")
def admin_recuperaciones_confirmar():
    if session.get("rol") != "admin":
        abort(403)

    recuperacion_id = int(request.form["recuperacion_id"])
    usuario_id = int(request.form["usuario_id"])
    clase_id = int(request.form["clase_id"])

    conn = conectar()
    c = conn.cursor()

    existe = c.execute("""
        SELECT 1
        FROM inscripciones
        WHERE usuario_id = ? AND clase_id = ?
    """, (usuario_id, clase_id)).fetchone()



    if existe:
        conn.close()
        flash("El usuario ya está inscrito en esta clase", "error")
        #return redirect(url_for("admin_recuperaciones"))
        return redirect("/pilates/admin_recuperaciones")

    # Insertar nueva inscripción
    c.execute("""
        INSERT INTO inscripciones (usuario_id, clase_id)
        VALUES (?, ?)
    """, (usuario_id, clase_id))

    # Marcar recuperación como asignada
    c.execute("""
        UPDATE recuperaciones
        SET asignada = 1
        WHERE id = ?
    """, (recuperacion_id,))

    conn.commit()
    conn.close()

    #flash("Recuperación asignada correctamente", "success")
    #return redirect(url_for("admin_recuperaciones"))
    return redirect("/pilates/admin_recuperaciones")




#pagos usuarios

from datetime import date
from usuarios import obtener_usuarios_con_pagos

@app.route("/admin/pagos")
@login_required
@role_required("admin")
def admin_pagos():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    hoy = date.today()
    year, month = obtener_mes_activo()

    mes_activo = f"{year}-{month:02d}"     

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    mes_literal = meses[month - 1]


    usuarios = obtener_usuarios_con_pagos(year, month)

    return render_template(
        "pagos.html",
        usuarios=usuarios,
        year=year,
        mes_literal=mes_literal
    )

from datetime import date
from flask import request, redirect, flash

@app.route("/admin/pagos/toggle/<int:usuario_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_toggle_pago(usuario_id):
    hoy = date.today().isoformat()

    year, month = obtener_mes_activo()  # ✅ mes activo real del sistema

    cuota_str = (request.form.get("cuota") or "").strip()
    metodo_pago = (request.form.get("metodo_pago") or "Tpv").strip()

    if metodo_pago not in ("Tpv", "Efectivo"):
        flash("Método de pago no válido", "error")
        return redirect("/pilates/admin/pagos")

    cuota_val = None
    if cuota_str != "":
        try:
            cuota_val = float(cuota_str)
            if cuota_val < 0:
                raise ValueError()
        except:
            flash("Cuota no válida", "error")
            return redirect("/pilates/admin/pagos")

    conn = conectar()
    c = conn.cursor()

    # 1) Asegurar que exista el registro del mes (si no existe)
    #    (ajusta columnas si tu tabla tiene más campos obligatorios)
    c.execute("""
        INSERT OR IGNORE INTO pagos (usuario_id, year, month, pagado, cuota, fecha_pago, metodo_pago)
        VALUES (?, ?, ?, 0, NULL, NULL, 'Tpv')
    """, (usuario_id, year, month))

    # 2) Guardar cuota/método (si cuota está vacía, no pisamos la que hubiese)
    if cuota_val is not None:
        c.execute("""
            UPDATE pagos
            SET cuota = ?, metodo_pago = ?
            WHERE usuario_id = ? AND year = ? AND month = ?
        """, (cuota_val, metodo_pago, usuario_id, year, month))
    else:
        c.execute("""
            UPDATE pagos
            SET metodo_pago = ?
            WHERE usuario_id = ? AND year = ? AND month = ?
        """, (metodo_pago, usuario_id, year, month))

    # 3) Toggle pagado/impago + fecha_pago
    c.execute("""
        UPDATE pagos
        SET pagado = CASE WHEN pagado = 1 THEN 0 ELSE 1 END,
            fecha_pago = CASE WHEN pagado = 1 THEN NULL ELSE ? END
        WHERE usuario_id = ? AND year = ? AND month = ?
    """, (hoy, usuario_id, year, month))

    conn.commit()
    conn.close()

    return redirect("/pilates/admin/pagos")





@app.route("/admin/pagos/historico")
@login_required
@role_required("admin")
def admin_pagos_historico():
    if session.get("rol") != "admin":
        abort(403)


    

    mes = request.args.get("mes")
    
    if mes:
        year, month = map(int, mes.split("-"))
    else:
        year, month = obtener_mes_activo()

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    mes_literal = meses[month - 1]

    conn = conectar()
    c = conn.cursor()


    tot = c.execute("""
    SELECT
      COALESCE(SUM(COALESCE(p.cuota, 0)), 0) AS total_cuotas,
      COALESCE(SUM(CASE WHEN p.pagado = 1 THEN COALESCE(p.cuota, 0) ELSE 0 END), 0) AS total_pagado,
      COALESCE(SUM(CASE WHEN p.pagado = 1 AND p.metodo_pago = 'Tpv' THEN COALESCE(p.cuota, 0) ELSE 0 END), 0) AS total_tpv,
      COALESCE(SUM(CASE WHEN p.pagado = 1 AND p.metodo_pago = 'Efectivo' THEN COALESCE(p.cuota, 0) ELSE 0 END), 0) AS total_efectivo
    FROM pagos p
    WHERE p.year = ? AND p.month = ?
    """, (year, month)).fetchone()

    resumen = {
        "total_cuotas": tot[0],
        "total_pagado": tot[1],
        "total_tpv": tot[2],
        "total_efectivo": tot[3],
    }

    query = """
        SELECT
            p.id,
            u.nombre,
            p.year,
            p.month,
            p.cuota,
            p.metodo_pago,
            p.pagado,
            p.fecha_pago            
        FROM pagos p
        JOIN usuarios u ON u.id = p.usuario_id
        WHERE 1=1 and pagado=1
    """
    params = []

    if year:
        query += " AND p.year = ?"
        params.append(int(year))

    if month:
        query += " AND p.month = ?"
        params.append(int(month))

    query += " ORDER BY p.year DESC, p.month DESC, u.nombre"

    pagos = c.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "admin_pagos_historico.html",
        pagos=pagos,
        year=year,
        month=month,
        mes_literal=mes_literal,
        resumen=resumen
    )



@app.route("/usuario/pagos")
@login_required
@role_required("admin")
def usuario_pagos():
    if session.get("rol") != "usuario":
        abort(403)

    usuario_id = session["user_id"]

    conn = conectar()
    c = conn.cursor()

    pagos = c.execute("""
        SELECT
            year,
            month,
            cuota,
            pagado,
            fecha_pago
        FROM pagos
        WHERE usuario_id = ? and pagado=1
        ORDER BY year DESC, month DESC
    """, (usuario_id,)).fetchall()

    conn.close()

    return render_template(
        "usuario_pagos.html",
        pagos=pagos
    )


#CREAR USUARIO


@app.route("/admin/usuarios/nuevo")
@login_required
@role_required("admin")
def admin_nuevo_usuario():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    return render_template("crear_usuario.html")

@app.route("/admin/usuarios/nuevo", methods=["POST"])
@login_required
@role_required("admin")
def admin_nuevo_usuario_post():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)


    password = request.form["password"]
    password2 = request.form["password2"]
    rol = request.form["rol"]



    if password != password2:
        flash("❌ Las contraseñas no coinciden", "error")
        #return redirect(url_for("admin_nuevo_usuario"))
        return redirect("/pilates/admin_nuevo_usuario")

    if rol not in ("usuario", "admin"):
        flash("Rol no válido", "error")
        #return redirect(url_for("admin_nuevo_usuario"))
        return redirect("/pilates/admin_nuevo_usuario")


    crear_usuario(
        nombre=request.form["nombre"],
        email=request.form["email"],
        password=request.form["password"],
        rol=request.form["rol"],
        clases_semana=int(request.form["clases_semana"])
    )

    flash("Usuario creado correctamente", "success")
    return redirect("/pilates/admin")

#gestionar usuarios admin


from flask import request

@app.route("/admin/usuarios")
@login_required
@role_required("admin")
def admin_usuarios():
    if session.get("rol") != "admin":
        abort(403)

    estado = request.args.get("estado", "activos")  # activos | desactivados | todos

    conn = conectar()
    c = conn.cursor()

    sql = """
        SELECT id, nombre, email, rol, clases_semana, desactivo
        FROM usuarios
    """
    params = ()

    if estado == "activos":
        sql += " WHERE desactivo = 0"
    elif estado == "desactivados":
        sql += " WHERE desactivo = 1"
    else:
        estado = "todos"  # por si llega algo raro

    sql += " ORDER BY nombre"

    usuarios = c.execute(sql, params).fetchall()
    conn.close()

    return render_template(
        "admin_usuarios.html",
        usuarios=usuarios,
        estado=estado
    )


@app.route("/admin/usuarios/editar/<int:usuario_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_usuarios_editar(usuario_id):
    if session.get("rol") != "admin":
        abort(403)

    nombre = request.form["nombre"]
    rol = request.form["rol"]
    clases = int(request.form["clases_semana"])

    conn = conectar()
    c = conn.cursor()

    c.execute("""
        UPDATE usuarios
        SET nombre = ?, rol = ?, clases_semana = ?
        WHERE id = ?
    """, (nombre, rol, clases, usuario_id))

    conn.commit()
    conn.close()

    flash("Usuario actualizado correctamente", "success")
    return redirect("/pilates/admin/usuarios")

@app.route("/admin/usuarios/eliminar/<int:usuario_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_usuarios_eliminar(usuario_id):
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()

    
    

    #cuando elimine el usuario debo eliminarlo de inscripciones, asignaciones_fijas, clases, pagos , y usuuarios
    c.execute("DELETE FROM asignaciones_fijas WHERE usuario_id = ?", (usuario_id,))
    conn.commit()
   

    c.execute("DELETE FROM inscripciones WHERE usuario_id = ?", (usuario_id,))
    conn.commit()
    
    c.execute("DELETE FROM recuperaciones WHERE usuario_id = ?", (usuario_id,))
    conn.commit()

    c.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
    conn.commit()

    conn.close()



    flash("Usuario eliminado", "success")
    return redirect("/pilates/admin/usuarios")


@app.route("/admin/usuarios/desactivar/<int:usuario_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_usuarios_desactivar(usuario_id):
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()
        

    #cuando desactive el usuario
    c.execute("DELETE FROM asignaciones_fijas WHERE usuario_id = ?", (usuario_id,))
    conn.commit()
   

    c.execute("DELETE FROM inscripciones WHERE usuario_id = ?", (usuario_id,))
    conn.commit()
    
    c.execute("DELETE FROM recuperaciones WHERE usuario_id = ?", (usuario_id,))
    conn.commit()


    c.execute("update usuarios set desactivo=? WHERE id = ?", (1,usuario_id,))
    conn.commit()


    conn.close()


    flash("Usuario desactivado", "success")
    return redirect("/pilates/admin/usuarios")


@app.route("/admin/usuarios/activar/<int:usuario_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_usuarios_activar(usuario_id):
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()
        

    #cuando desactive el usuario no hago nada, solo lo activo



    c.execute("update usuarios set desactivo=? WHERE id = ?", (0,usuario_id,))
    conn.commit()


    conn.close()


    flash("Usuario Activado, acuerdate de que tendrás que volver a asignarle sus clases", "success")
    return redirect("/pilates/admin/usuarios")


#admin cambiar password


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()



@app.route("/admin/usuarios/<int:usuario_id>/password", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_cambiar_password(usuario_id):
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()

    # Obtener nombre del usuario (para mostrarlo)
    usuario = c.execute(
        "SELECT nombre FROM usuarios WHERE id = ?",
        (usuario_id,)
    ).fetchone()

    if not usuario:
        conn.close()
        flash("Usuario no encontrado", "error")
        #return redirect(url_for("admin_usuarios"))
        return redirect("/pilates/admin_usuarios")

    nombre = usuario[0]

    # 🔹 SI ES GET → solo mostrar formulario
    if request.method == "GET":
        conn.close()
        return render_template(
            "admin_cambiar_password.html",
            usuario_id=usuario_id,
            nombre=nombre
        )

    # 🔹 SI ES POST → procesar formulario
    password = request.form.get("password")
    password2 = request.form.get("password2")

    if not password or not password2:
        conn.close()
        flash("Debes rellenar ambos campos", "error")
        return redirect(request.url)

    if password != password2:
        conn.close()
        flash("Las contraseñas no coinciden", "error")
        return redirect(request.url)

    # Aquí ya puedes hashear y guardar
    password_hash = hash_password(password)

    c.execute(
        "UPDATE usuarios SET password = ? WHERE id = ?",
        (password_hash, usuario_id)
    )
    conn.commit()
    conn.close()

    flash("Contraseña actualizada correctamente", "success")
    #return redirect(url_for("admin_usuarios"))
    return redirect("/pilates/admin_usuarios")


#clases base
from clases import obtener_clases_base_con_ocupacion

@app.route("/admin/clases_base")
@login_required
@role_required("admin")
def admin_clases_base():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    clases = obtener_clases_base_con_ocupacion()

    dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

    return render_template(
        "clases_base.html",
        clases=clases,
        dias=dias
    )


@app.route("/admin/clases_base", methods=["POST"])
@login_required
@role_required("admin")
def admin_clases_base_post():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    dia_semana = int(request.form["dia_semana"])
    hora = request.form["hora"]

    if not hora.endswith((":00", ":30")):
        flash("La hora debe ser en intervalos de 30 minutos", "error")
        return redirect(request.path)

    h = int(hora.split(":")[0])
    if h < 9 or h > 21:
        flash("La hora debe estar entre las 09:00 y las 21:00", "error")
        return redirect(request.path)

    capacidad = int(request.form["capacidad"])
    descripcion = request.form["descripcion"]

    crear_clase_base(dia_semana, hora, capacidad,descripcion)

    flash("Clase base creada correctamente", "success")
    return redirect("/pilates/admin/clases_base")


#gestion de festivos


@app.route("/admin/festivos", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_festivos():
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()

    if request.method == "POST":
        fecha = request.form["fecha"]
        motivo = request.form.get("motivo", "").strip()

        existe = c.execute("""
            SELECT 1
            FROM festivos
            WHERE fecha = ?
            """, (fecha,)).fetchone()

        if existe:
            conn.close()
            flash("⚠️ Ya existe un festivo en esa fecha", "error")
            return redirect("/pilates/admin/festivos")

        c.execute("""
            INSERT OR IGNORE INTO festivos (fecha, motivo)
            VALUES (?, ?)
        """, (fecha, motivo))

        conn.commit()

        c.execute("""
            UPDATE clases
            SET es_festivo = 1,
            motivo_festivo = ?
            WHERE fecha = ?
         """, (motivo,fecha,))

        conn.commit()



    festivos = c.execute("""
        SELECT fecha, motivo
        FROM festivos
        ORDER BY fecha
    """).fetchall()

    conn.close()

    return render_template("festivos.html", festivos=festivos)


@app.route("/admin/festivos/eliminar/<fecha>", methods=["POST"])
@login_required
@role_required("admin")
def eliminar_festivo(fecha):
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()

    c.execute("""
        DELETE FROM festivos
        WHERE fecha = ?
    """, (fecha,))

    conn.commit()
    
    c.execute("""
            UPDATE clases
            SET es_festivo = 0,
            motivo_festivo = null
            WHERE fecha = ?
         """, (fecha,))

    conn.commit()
    
    
    conn.close()

    flash("Festivo eliminado correctamente", "success")
    return redirect("/pilates/admin/festivos")


# =========================
# LISTA DE USUARIOS
# =========================

@app.route("/admin/asignaciones")
@login_required
@role_required("admin")
def admin_asignaciones():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    usuarios = obtener_usuarios()
    return render_template("asignaciones.html", usuarios=usuarios)



# =========================
# ASIGNAR A UN USUARIO
# =========================

@app.route("/admin/asignaciones/<int:usuario_id>")
@login_required
@role_required("admin")
def admin_asignar_usuario(usuario_id):
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    usuario = obtener_usuario_por_id(usuario_id)
    clases = obtener_clases_base_con_ocupacion()
    asignadas = obtener_asignaciones_usuario(usuario_id)

    return render_template(
        "asignar_usuario.html",
        usuario=usuario,
        clases=clases,
        asignadas=asignadas
    )

# =========================
# ASIGNAR (POST)
# =========================

@app.route("/admin/asignaciones/<int:usuario_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_asignar_usuario_post(usuario_id):
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    clase_id = request.form.get("clase_id")
    checked = request.form.get("checked")  # existe solo si está marcado

    if not clase_id:
        return redirect(f"/pilates/admin/asignaciones/{usuario_id}")

    clase_id = int(clase_id)

    conn = conectar()
    c = conn.cursor()

    # Máximo de clases permitidas al usuario (1 o 2)
    max_clases = obtener_usuario_por_id(usuario_id)[3]

    # Clases ya asignadas
    actuales = c.execute("""
        SELECT COUNT(*) 
        FROM asignaciones_fijas
        WHERE usuario_id = ?
    """, (usuario_id,)).fetchone()[0]

    if checked:
        # Si intenta añadir y ya llegó al límite → bloquear
        if actuales >= max_clases:
            conn.close()
            flash(
                f"Este usuario ya tiene el máximo de {max_clases} clases permitidas",
                "warning"
            )
            return redirect(f"/pilates/admin/asignaciones/{usuario_id}")

        # Insertar si no existe
        c.execute("""
            INSERT OR IGNORE INTO asignaciones_fijas (usuario_id, clase_base_id)
            VALUES (?, ?)
        """, (usuario_id, clase_id))

    else:
        # Si se desmarca → eliminar
        c.execute("""
            DELETE FROM asignaciones_fijas
            WHERE usuario_id = ? AND clase_base_id = ?
        """, (usuario_id, clase_id))

    conn.commit()
    conn.close()

    inscribir_usuario_desde_hoy(usuario_id)


    return redirect(f"/pilates/admin/asignaciones/{usuario_id}")





# =========================
# QUITAR ASIGNACIÓN
# =========================

@app.route("/admin/asignaciones/<int:usuario_id>/quitar", methods=["POST"])
@login_required
@role_required("admin")
def admin_quitar_asignacion(usuario_id):
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    clase_base_id = int(request.form["clase_base_id"])
    quitar_asignacion(usuario_id, clase_base_id)

    flash("Asignación eliminada", "success")
    return redirect(f"/pilates/admin/asignaciones/{usuario_id}")

@app.route("/admin/asignar_mes", methods=["POST"])
@login_required
@role_required("admin")
def admin_asignar_mes():
    if "rol" not in session or session["rol"] != "admin":
        abort(403)

    year = int(request.form["year"])
    month = int(request.form["month"])

    generar_inscripciones_mes(year, month)

    flash("Usuarios asignados automáticamente al mes", "success")
    return redirect("/pilates/admin")

@app.route("/admin/clases_base/activar/<int:clase_id>", methods=["POST"])
@login_required
@role_required("admin")
def activar_clase_base(clase_id):
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        UPDATE clases_base
        SET activa = 1
        WHERE id = ?
    """, (clase_id,))

    conn.commit()
    conn.close()

    flash("Clase base activada", "success")
    return redirect("/pilates/admin/clases_base")


@app.route("/admin/clases_base/desactivar/<int:clase_id>", methods=["POST"])
@login_required
@role_required("admin")
def desactivar_clase_base(clase_id):
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        UPDATE clases_base
        SET activa = 0
        WHERE id = ?
    """, (clase_id,))

    conn.commit()
    conn.close()

    flash("Clase base activada", "success")
    return redirect("/pilates/admin/clases_base")




#borrar mes

@app.route("/admin/clases_mes/borrar", methods=["POST"])
@login_required
@role_required("admin")
def admin_borrar_clases_mes():
    if session.get("rol") != "admin":
        abort(403)

    year = int(request.form["year"])
    month = int(request.form["month"])

    conn = conectar()
    c = conn.cursor()

    # 1️⃣ borrar inscripciones del mes
    c.execute("""
        DELETE FROM inscripciones
        WHERE clase_id IN (
            SELECT id FROM clases
            WHERE substr(fecha, 1, 7) = ?
        )
    """, (f"{year}-{month:02d}",))

    # 2️⃣ borrar clases del mes
    c.execute("""
        DELETE FROM clases
        WHERE substr(fecha, 1, 7) = ?
    """, (f"{year}-{month:02d}",))

    #borrar tambien recuperaciones pendientes

    c.execute("""
        DELETE FROM recuperaciones
        WHERE substr(fecha_clase, 1, 7) = ?
    """, (f"{year}-{month:02d}",))

    conn.commit()
    conn.close()

    flash("Clases del mes eliminadas correctamente", "success")
    #return redirect(url_for("admin_clases_mes"))
    return redirect("/pilates/admin_clases_mes")


##PANEL DE USUARIO
@app.route("/usuario")
def panel_usuario():
    if session.get("rol") != "usuario":
        abort(403)

    usuario_id = session["user_id"]

    hoy = date.today()
    year, month = obtener_mes_activo()

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    mes_literal = meses[month - 1]

    resumen = obtener_resumen_usuario(usuario_id, year, month)

    return render_template(
        "usuario_panel.html",
        resumen=resumen,
        year=year,
        month=month,
        mes_literal=mes_literal
    )




@app.route("/usuario/clases")
def usuario_clases_mes():
    if session.get("rol") != "usuario":
        abort(403)

    usuario_id = session["user_id"]

    hoy = date.today()
    year, month = obtener_mes_activo()

    calendario = obtener_clases_usuario_mes(usuario_id, year, month)

    return render_template(
        "usuario_clases_mes.html",
        calendario=calendario,
        year=year,
        month=month
    )


@app.route("/usuario/password", methods=["GET", "POST"])
def usuario_cambiar_password():
    if session.get("rol") != "usuario":
        abort(403)

    usuario_id = session["user_id"]

    if request.method == "POST":
        nueva = request.form["nueva"]
        repetir = request.form["repetir"]


        if nueva != repetir:
            flash("Las contraseñas nuevas no coinciden", "error")
            #return redirect(url_for("usuario_cambiar_password"))
            return redirect("/pilates/usuario_cambiar_password")

        conn = conectar()
        c = conn.cursor()

        nuevo_hash = hash_password(nueva)

        c.execute(
            "UPDATE usuarios SET password = ? WHERE id = ?",
            (nuevo_hash, usuario_id)
        )
        conn.commit()
        conn.close()

        flash("Contraseña actualizada correctamente", "success")
        return redirect("/pilates/usuario")




    return render_template("usuario_cambiar_password.html")




from datetime import date
import calendar

DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

def obtener_clases_usuario_mes(usuario_id, year, month):
    conn = conectar()
    c = conn.cursor()

    HOY = date.today()

    filas = c.execute("""
        SELECT
            c.id,
            c.fecha,
            c.hora,
            c.descripcion,
            c.es_festivo,
            datetime(c.fecha || ' ' || c.hora) >= datetime('now','localtime','+12 hours') AS puede_borrarse
        FROM clases c
        JOIN inscripciones i ON i.clase_id = c.id
        WHERE i.usuario_id = ?
          AND substr(c.fecha,1,7) = ?
        ORDER BY c.fecha, c.hora
    """, (usuario_id, f"{year}-{month:02d}")).fetchall()

    conn.close()

    # 🔹 Agrupar clases por fecha
    clases_por_fecha = {}

    for clase_id, fecha, hora, descripcion, es_festivo, puede_borrarse in filas:
        clases_por_fecha.setdefault(fecha, []).append({
            "id": clase_id,
            "hora": hora,
            "descripcion": descripcion,
            "es_festivo": bool(es_festivo),
            "puede_borrarse": bool(puede_borrarse)
        })

    # 🔹 Construir calendario COMPLETO del mes
    _, dias_mes = calendar.monthrange(year, month)
    calendario = []

    for dia in range(1, dias_mes + 1):
        fecha_obj = date(year, month, dia)
        fecha_str = fecha_obj.isoformat()

        clases_dia = clases_por_fecha.get(fecha_str, [])

        calendario.append({
            "fecha": fecha_str,
            "dia_num": dia,
            "dia_semana_num": fecha_obj.weekday(),  # 0=lunes
            "dia_semana": DIAS[fecha_obj.weekday()],
            "tiene_clases": bool(clases_dia),
            "es_hoy": fecha_obj == HOY,
            "clases": clases_dia
        })

    return calendario




@app.route("/usuario/clase/baja", methods=["POST"])
def usuario_baja_clase():
    if session.get("rol") != "usuario":
        abort(403)

    usuario_id = session["user_id"]
    clase_id = int(request.form["clase_id"])

    conn = conectar()
    c = conn.cursor()

    # 1️⃣ Obtener fecha de la clase
    fecha = c.execute("""
        SELECT fecha FROM clases WHERE id = ?
    """, (clase_id,)).fetchone()[0]

    # Comprobar si está dentro del plazo permitido
    existe = c.execute("""
         SELECT 1
         FROM clases c
         JOIN inscripciones i ON i.clase_id = c.id
         WHERE i.usuario_id = ?
            AND c.id = ?
            AND datetime(c.fecha || ' ' || c.hora) >= datetime('now','localtime','+24 hours')
    """, (usuario_id, clase_id)).fetchone()

    if not existe:
        conn.close()
        flash("No puedes darte de baja con menos de 24 horas", "error")
        return redirect("/pilates/usuario")

    es_festivo = c.execute("""
        SELECT es_festivo
        FROM clases
        WHERE id = ?
    """, (clase_id,)).fetchone()[0]

    if es_festivo:
        conn.close()
        flash("Esta clase es festiva y no se puede cancelar", "warning")
        return redirect("/pilates/usuario")



    # Borrar inscripción
    c.execute("""
        DELETE FROM inscripciones
        WHERE usuario_id = ? AND clase_id = ?
    """, (usuario_id, clase_id))

    # Crear recuperación
    c.execute("""
        INSERT INTO recuperaciones (usuario_id, clase_original_id, fecha_clase, fecha_creacion)
        VALUES (?, ?,?,date('now'))
    """, (usuario_id, clase_id,fecha))

    conn.commit()
    conn.close()

    flash("Te has dado de baja y se ha creado una recuperación", "success")
    return redirect("/pilates/usuario")




def obtener_recuperaciones_pendientes(usuario_id):
    conn = conectar()
    c = conn.cursor()

    usuario_id = session["user_id"]
    year, month = obtener_mes_activo()

    total = c.execute("""
        SELECT COUNT(*)
        FROM recuperaciones r
        JOIN clases c ON c.id = r.clase_original_id
        WHERE r.usuario_id = ?
          AND r.asignada = 0
          AND substr(r.fecha_clase, 1, 7) = ?
    """, (usuario_id, f"{year}-{month:02d}")).fetchone()[0]


    conn.close()
    return total


from datetime import date
import calendar

def obtener_clases_mes_disponibles(year, month):
    conn = conectar()
    c = conn.cursor()

    filas = c.execute("""
        SELECT
            c.id,
            c.fecha,
            c.hora,
            c.descripcion,
            c.capacidad,
            COUNT(i.id) AS ocupacion
        FROM clases c
        LEFT JOIN inscripciones i ON i.clase_id = c.id
        WHERE substr(c.fecha,1,7) = ?
          AND c.es_festivo = 0
          AND datetime(c.fecha || ' ' || c.hora) >= datetime('now','localtime')
        GROUP BY c.id, c.fecha, c.hora, c.descripcion, c.capacidad
        HAVING ocupacion < c.capacidad
        ORDER BY c.fecha, c.hora
    """, (f"{year}-{month:02d}",)).fetchall()

    conn.close()

    # 🔹 Día de la semana del día 1 (lunes=0)
    primer_dia = date(year, month, 1)
    offset = primer_dia.weekday()  # 0=lunes

    calendario = {
        "offset": offset,
        "dias": []
    }

    _, num_dias = calendar.monthrange(year, month)

    # Crear días del mes
    for dia in range(1, num_dias + 1):
        fecha = date(year, month, dia)
        fecha_str = fecha.isoformat()

        calendario["dias"].append({
            "fecha": fecha_str,
            "dia_num": dia,
            "dia_semana": fecha.weekday(),  # 0-6
            "clases": []
        })

    # Meter clases
    for clase_id, fecha, hora, descripcion, capacidad, ocupacion in filas:
        for d in calendario["dias"]:
            if d["fecha"] == fecha:
                d["clases"].append({
                    "id": clase_id,
                    "hora": hora,
                    "descripcion": descripcion,
                    "ocupacion": ocupacion,
                    "capacidad": capacidad
                })

    return calendario




@app.route("/usuario/recuperaciones")
def usuario_recuperaciones():
    if session.get("rol") != "usuario":
        abort(403)

    usuario_id = session["user_id"]

    hoy = date.today()
    year, month = obtener_mes_activo()

    calendario = obtener_clases_mes_disponibles(year, month)

    meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    mes_literal = meses[month - 1]

    # Recuperaciones pendientes
    conn = conectar()
    c = conn.cursor()

    recuperaciones = c.execute("""
        SELECT COUNT(*)
        FROM recuperaciones r
        JOIN clases c ON c.id = r.clase_original_id
        WHERE r.usuario_id = ?
          AND r.asignada = 0
          AND substr(r.fecha_clase, 1, 7) = ?
    """, (usuario_id, f"{year}-{month:02d}")).fetchone()[0]




    conn.close()

    return render_template(
        "usuario_recuperaciones.html",
        calendario=calendario,
        recuperaciones=recuperaciones,
        year=year,
        month=month,
        mes_literal=mes_literal
    )


@app.route("/usuario/recuperaciones/apuntar", methods=["POST"])
def usuario_apuntar_recuperacion():
    if session.get("rol") != "usuario":
        abort(403)

    usuario_id = session["user_id"]
    clase_id = int(request.form["clase_id"])

    conn = conectar()
    c = conn.cursor()


    year, month = obtener_mes_activo()
    # 1️⃣ ¿Tiene recuperaciones disponibles?
    rec = c.execute("""
         SELECT r.id
         FROM recuperaciones r
         JOIN clases c ON c.id = r.clase_original_id
         WHERE r.usuario_id = ?
          AND r.asignada = 0
          AND substr(c.fecha, 1, 7) = ?
    """, (usuario_id, f"{year}-{month:02d}")).fetchone()


    if not rec:
        conn.close()
        flash("No tienes recuperaciones disponibles", "error")
        return redirect("/pilates/usuario/recuperaciones")

    recuperacion_id = rec[0]

    # 2️⃣ ¿Ya está inscrito?
    existe = c.execute("""
        SELECT 1 FROM inscripciones
        WHERE usuario_id = ? AND clase_id = ?
    """, (usuario_id, clase_id)).fetchone()

    if existe:
        conn.close()
        flash("Ya estás inscrito en esta clase", "error")
        return redirect("/pilates/usuario/recuperaciones")

    # 3️⃣ Insertar inscripción
    c.execute("""
        INSERT INTO inscripciones (usuario_id, clase_id)
        VALUES (?, ?)
    """, (usuario_id, clase_id))

    # 4️⃣ Consumir recuperación
    c.execute("""
        UPDATE recuperaciones
        SET asignada = 1
        WHERE id = ?
    """, (recuperacion_id,))

    conn.commit()
    conn.close()

    flash("Clase asignada correctamente", "success")
    return redirect("/pilates/usuario")



#crear una clase manual
@app.route("/admin/clases_manual", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_crear_clase_manual():
    if session.get("rol") != "admin":
        abort(403)

    conn = conectar()
    c = conn.cursor()

    if request.method == "POST":
        fecha = request.form["fecha"]        # YYYY-MM-DD
        hora = request.form["hora"]          # HH:MM
        descripcion = request.form["descripcion"]
        capacidad = int(request.form["capacidad"])

        # 🔒 1. Comprobar si ya existe clase ese día y hora
        existe = c.execute("""
            SELECT 1 FROM clases
            WHERE fecha = ? AND hora = ?
        """, (fecha, hora)).fetchone()

        if existe:
            conn.close()
            flash("Ya existe una clase ese día a esa hora", "error")
            #return redirect(url_for("admin_crear_clase_manual"))
            return redirect("/pilates/admin_crear_clase_manual")

        # 2️⃣ Insertar clase
        c.execute("""
            INSERT INTO clases (
                fecha, hora, descripcion, capacidad, es_festivo
            ) VALUES (?, ?, ?, ?, 0)
        """, (fecha, hora, descripcion, capacidad))

        conn.commit()
        conn.close()

        flash("Clase creada correctamente", "success")
        #return redirect(url_for("admin_clases_mes"))
        return redirect("/pilates/admin_clases_mes")

    conn.close()
    return render_template("admin_clase_manual.html")


#insertar recuperacion manualmente


@app.route("/admin/recuperaciones_nueva", methods=["GET"])
@login_required
@role_required("admin")
def nueva_recuperacion():

    conn = conectar()
    c = conn.cursor()

    c.execute("""
        SELECT id, nombre
        FROM usuarios
        WHERE rol = 'usuario' and desactivo=0
        ORDER BY nombre
    """)
    usuarios = c.fetchall()

    conn.close()

    return render_template(
        "recuperacion_nueva.html",
        usuarios=usuarios
    )



@app.route("/admin/recuperaciones_nueva", methods=["POST"])
@login_required
@role_required("admin")
def guardar_recuperacion():
    if session.get("rol") != "admin":
        abort(403)

    usuario_id = request.form["id_usuario"]

    

    conn = conectar()
    c = conn.cursor()

    year, month = obtener_mes_activo()

    # 1️⃣ Obtener primera clase del mes activo
    clase = c.execute("""
        SELECT id, fecha
        FROM clases
        WHERE fecha LIKE ?
        ORDER BY fecha ASC
        LIMIT 1
    """, (f"{year}-{month:02d}%",)).fetchone()

    if not clase:
       conn.close()
       flash("No hay clases en el mes activo", "error")
       return redirect("/pilates/admin/recuperaciones_nueva")

    clase_id, fecha_clase = clase



    # 2️⃣ Insertar recuperación
    c.execute("""
        INSERT INTO recuperaciones (
            usuario_id,
           clase_original_id,
            fecha_clase,
            fecha_creacion,
            asignada,
            especial
        ) VALUES (?, ?, ?, DATE('now'), 0,1)
    """, (usuario_id, clase_id, fecha_clase))

    conn.commit()
    conn.close()

    flash("Recuperación añadida correctamente", "success")
    return redirect("/pilates/admin/recuperaciones")




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


application = DispatcherMiddleware(Response("Not Found", status=404), {
    "/pilates": app,
})
