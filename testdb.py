from usuarios import crear_usuario

crear_usuario(
    nombre="Administrador",
    email="admin@admin.com",
    password="admin123",
    rol="admin"
)

print("Administrador creado con password hasheado")