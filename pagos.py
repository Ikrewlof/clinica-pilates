def registrar_pago(usuario_id, mes, importe):
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        INSERT INTO pagos (usuario_id, mes, importe, estado)
        VALUES (?, ?, ?, 'pagado')
    """, (usuario_id, mes, importe))
    conn.commit()
    conn.close()
