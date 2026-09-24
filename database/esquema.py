"""Inicialización y compatibilidad del esquema local de la aplicación."""

import sqlite3

import bcrypt

from .conexion import (
    _supabase_activo,
    get_db_connection,
    PAYPAL_VENDEDOR_SANDBOX,
)


def inicializar_bd():
    if _supabase_activo():
        print("Base de datos remota Supabase activa.")
        return
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            correo TEXT UNIQUE,
            telefono TEXT,
            fecha_nacimiento TEXT,
            contraseña TEXT,
            paypal_email TEXT
        )
    """
    )
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN imagen TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN codigo_sesion TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN auth_user_id TEXT UNIQUE")
    except sqlite3.OperationalError:
        pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sesiones_dispositivo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            revocado INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tiendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            whatsapp TEXT,
            tasa_cambio REAL,
            usuario_id INTEGER,
            direccion TEXT,
            saldo REAL DEFAULT 0,
            imagen TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
        )
    """
    )
    try:
        cursor.execute("ALTER TABLE tiendas ADD COLUMN imagen TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            marca TEXT,
            talla TEXT,
            precio_cordobas REAL,
            precio_dolares REAL,
            stock INTEGER,
            tienda_id INTEGER,
            imagen TEXT,
            categoria TEXT DEFAULT 'General',
            descripcion TEXT,
            estado_producto TEXT DEFAULT 'Nuevo',
            etiquetas TEXT,
            estilo TEXT,
            color_principal TEXT,
            material TEXT,
            garantia TEXT,
            especificacion TEXT,
            FOREIGN KEY (tienda_id) REFERENCES tiendas(id) ON DELETE CASCADE
        )
    """
    )
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN imagen TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN categoria TEXT DEFAULT 'General'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE productos ADD COLUMN imagen_2 TEXT")
    except sqlite3.OperationalError:
        pass
    for columna, valor in (
        ("descripcion", "TEXT"),
        ("estado_producto", "TEXT DEFAULT 'Nuevo'"),
        ("etiquetas", "TEXT"),
        ("estilo", "TEXT"),
        ("color_principal", "TEXT"),
        ("material", "TEXT"),
        ("garantia", "TEXT"),
        ("especificacion", "TEXT"),
    ):
        try:
            cursor.execute(f"ALTER TABLE productos ADD COLUMN {columna} {valor}")
        except sqlite3.OperationalError:
            pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            producto_id INTEGER,
            cantidad INTEGER,
            fecha TEXT,
            estado TEXT,
            fecha_entrega TIMESTAMP,
            tienda_id INTEGER,
            order_id TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
            FOREIGN KEY (tienda_id) REFERENCES tiendas(id) ON DELETE CASCADE
        )
    """
    )
    try:
        cursor.execute("ALTER TABLE reservas ADD COLUMN fecha_expiracion TEXT")
    except sqlite3.OperationalError:
        pass
    cursor.execute(
        "UPDATE reservas SET fecha_expiracion = datetime(fecha, '+24 hours') "
        "WHERE fecha_expiracion IS NULL AND fecha IS NOT NULL"
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resenas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER,
            usuario_id INTEGER,
            calificacion INTEGER,
            comentario TEXT,
            fecha TEXT,
            FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
        )
    """
    )

    # 1. Crear Administrador y asignarle el PayPal Vendedor Sandbox
    cursor.execute(
        "SELECT * FROM usuarios WHERE correo = 'admin@smartstore.com'"
    )
    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO usuarios (nombre, correo, telefono, fecha_nacimiento, contraseña, paypal_email)
            VALUES (?,?,?,?,?,?)
        """,
            (
                "Administrador",
                "admin@smartstore.com",
                "88888888",
                "2000-01-01",
                bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8"),
                PAYPAL_VENDEDOR_SANDBOX,
            ),
        )
    else:
        # Actualizar email de paypal si ya existía el admin
        cursor.execute(
            "UPDATE usuarios SET paypal_email = ? WHERE correo = 'admin@smartstore.com'",
            (PAYPAL_VENDEDOR_SANDBOX,),
        )

    # 2. Actualizar cualquier usuario sin paypal_email para que use el vendedor de Sandbox
    cursor.execute(
        "UPDATE usuarios SET paypal_email = ? WHERE paypal_email IS NULL OR paypal_email = ''",
        (PAYPAL_VENDEDOR_SANDBOX,),
    )

    conn.commit()
    conn.close()
    print(
        f"Base de datos local inicializada. Vendedor PayPal: {PAYPAL_VENDEDOR_SANDBOX}"
    )