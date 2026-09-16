import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from supabase_config import SUPABASE_KEY, supabase_esta_configurado, supabase_request, supabase_rpc

DB_NAME = "smartstore.db"
# La base puede vivir en almacenamiento de la app o en la carpeta del proyecto.


def _obtener_ruta_base_datos():
    almacenamiento_app = os.environ.get("FLET_APP_STORAGE_DATA")
    if almacenamiento_app:
        directorio = Path(almacenamiento_app)
        directorio.mkdir(parents=True, exist_ok=True)
        return str(directorio / DB_NAME)

    return str(Path(__file__).resolve().parent / DB_NAME)


DB_PATH = _obtener_ruta_base_datos()
USAR_SUPABASE = os.getenv("SMARTSTORE_USAR_SUPABASE", "1").strip().lower() in {
    "1", "true", "si", "sí", "yes", "on"
}
_SUPABASE_FALLIDA = False
_SUPABASE_FALLIDA_HASTA = None
_SUPABASE_FALLIDA_COOLDOWN = timedelta(seconds=45)


def _marcar_supabase_caido(mensaje=""):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    if _SUPABASE_FALLIDA:
        return

    _SUPABASE_FALLIDA = True
    _SUPABASE_FALLIDA_HASTA = datetime.now() + _SUPABASE_FALLIDA_COOLDOWN
    print(f"[Supabase] Fallo temporal detectado; se reintentará más tarde sin forzar SQLite local. {mensaje}")


def _supabase_activo():
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA

    if not USAR_SUPABASE:
        return False

    if not supabase_esta_configurado():
        print(
            "[Supabase] Configuración no válida o placeholder. "
            "Reemplaza SMARTSTORE_SUPABASE_URL y SMARTSTORE_SUPABASE_KEY en .env "
            "con tus valores reales para usar Supabase."
        )
        return False

    if _SUPABASE_FALLIDA:
        if _SUPABASE_FALLIDA_HASTA is not None and datetime.now() >= _SUPABASE_FALLIDA_HASTA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
            print("[Supabase] Reintentando conexion con Supabase tras recuperacion temporal.")
        else:
            return False

    return True


def _supabase_lista(tabla, parametros=""):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    try:
        _, datos = supabase_request(tabla, parametros=parametros)
        if _SUPABASE_FALLIDA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
        return datos or []
    except Exception as exc:
        _marcar_supabase_caido(f"Error en consulta a {tabla}: {exc}")
        raise RuntimeError(f"No hay conexión a internet o la base de datos no está disponible: {exc}") from exc


def _supabase_unico(tabla, parametros=""):
    filas = _supabase_lista(tabla, parametros)
    return filas[0] if filas else None


def _supabase_insertar(tabla, datos):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    try:
        _, resultado = supabase_request(tabla, metodo="POST", datos=datos)
        if _SUPABASE_FALLIDA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
        return resultado[0] if isinstance(resultado, list) and resultado else resultado
    except Exception as exc:
        _marcar_supabase_caido(f"Error al insertar en {tabla}: {exc}")
        raise RuntimeError(f"No hay conexión a internet o la base de datos no está disponible: {exc}") from exc


def _supabase_actualizar(tabla, datos, parametros):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    try:
        _, resultado = supabase_request(
            tabla,
            metodo="PATCH",
            datos=datos,
            parametros=parametros,
        )
        if _SUPABASE_FALLIDA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
        return resultado
    except Exception as exc:
        _marcar_supabase_caido(f"Error al actualizar en {tabla}: {exc}")
        raise RuntimeError(f"No hay conexión a internet o la base de datos no está disponible: {exc}") from exc


def _supabase_borrar(tabla, parametros):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    try:
        supabase_request(tabla, metodo="DELETE", parametros=parametros)
        if _SUPABASE_FALLIDA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
    except Exception as exc:
        _marcar_supabase_caido(f"Error al borrar en {tabla}: {exc}")
        raise RuntimeError(f"No hay conexión a internet o la base de datos no está disponible: {exc}") from exc

# ==========================================
# 🧪 CORREOS SIMULADOS PARA PRUEBAS (SANDBOX)
# ==========================================
PAYPAL_VENDEDOR_SANDBOX = "sb-zfl8251875274@business.example.com"
PAYPAL_COMPRADOR_SANDBOX = "sb-ysdcv52256136@personal.example.com"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


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
                "admin123",
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


def obtener_usuario(correo, contraseña):
    if _supabase_activo():
        correo_q = quote(str(correo), safe="")
        password_q = quote(str(contraseña), safe="")
        usuario = _supabase_unico(
            "usuarios",
            f"?select=id,nombre,correo&correo=eq.{correo_q}&contraseña=eq.{password_q}&limit=1",
        )
        return (usuario["id"], usuario["nombre"], usuario["correo"]) if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, correo FROM usuarios WHERE correo = ? AND contraseña = ?",
        (correo, contraseña),
    )
    user = cursor.fetchone()
    conn.close()
    return user


def obtener_usuario_por_id(usuario_id):
    if _supabase_activo():
        usuario = _supabase_unico(
            "usuarios", f"?select=id,nombre,correo,telefono,fecha_nacimiento,imagen&id=eq.{usuario_id}&limit=1"
        )
        return tuple(usuario.get(campo) for campo in ("id", "nombre", "correo", "telefono", "fecha_nacimiento", "imagen")) if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, correo, telefono, fecha_nacimiento, imagen FROM usuarios WHERE id = ?",
        (usuario_id,),
    )
    usuario = cursor.fetchone()
    conn.close()
    return usuario


def actualizar_perfil_usuario(usuario_id, nombre, correo, telefono, fecha_nacimiento):
    if _supabase_activo():
        resultado = _supabase_actualizar(
            "usuarios",
            {"nombre": nombre, "correo": correo, "telefono": telefono, "fecha_nacimiento": fecha_nacimiento},
            f"?id=eq.{usuario_id}",
        )
        return bool(resultado)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE usuarios
        SET nombre = ?, correo = ?, telefono = ?, fecha_nacimiento = ?
        WHERE id = ?
        """,
        (nombre, correo, telefono, fecha_nacimiento, usuario_id),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizado


def registrar_usuario(nombre, correo, telefono, fecha_nac, contraseña, imagen=None):
    if _supabase_activo():
        try:
            _supabase_insertar(
                "usuarios",
                {"nombre": nombre, "correo": correo, "telefono": telefono,
                 "fecha_nacimiento": fecha_nac, "contraseña": contraseña,
                 "paypal_email": PAYPAL_VENDEDOR_SANDBOX, "imagen": imagen},
            )
            return True, "Usuario registrado"
        except Exception:
            return False, "Error al registrar"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO usuarios (nombre, correo, telefono, fecha_nacimiento, contraseña, paypal_email, imagen)
            VALUES (?,?,?,?,?,?,?)
        """,
            (
                nombre,
                correo,
                telefono,
                fecha_nac,
                contraseña,
                PAYPAL_VENDEDOR_SANDBOX,
                imagen,
            ),
        )
        conn.commit()
        return True, "Usuario registrado"
    except:
        return False, "Error al registrar"
    finally:
        conn.close()


def actualizar_imagen_usuario(usuario_id, imagen):
    if _supabase_activo():
        return bool(_supabase_actualizar("usuarios", {"imagen": imagen}, f"?id=eq.{usuario_id}"))
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET imagen = ? WHERE id = ?", (imagen, usuario_id))
        actualizado = cursor.rowcount > 0
        conn.commit()
        return actualizado
    finally:
        conn.close()


def obtener_tienda():
    """Compatibilidad: devuelve la primera tienda disponible para usos legacy.
    Para los flujos del usuario actual se debe usar obtener_tienda_usuario(usuario_id)."""
    if _supabase_activo():
        tienda = _supabase_unico(
            "tiendas", "?select=id,nombre,whatsapp,tasa_cambio,usuario_id,direccion,saldo,imagen&limit=1"
        )
        return tuple(tienda.get(campo) for campo in ("id", "nombre", "whatsapp", "tasa_cambio", "usuario_id", "direccion", "saldo", "imagen")) if tienda else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
            "SELECT id, nombre, whatsapp, tasa_cambio, usuario_id, direccion, saldo, imagen FROM tiendas LIMIT 1"
    )
    tienda = cursor.fetchone()
    conn.close()
    return tienda


def obtener_tienda_usuario(usuario_id):
    if _supabase_activo():
        tienda = _supabase_unico(
            "tiendas",
            f"?select=id,nombre,whatsapp,tasa_cambio,usuario_id,direccion,saldo,imagen&usuario_id=eq.{usuario_id}&limit=1",
        )
        return tuple(tienda.get(campo) for campo in ("id", "nombre", "whatsapp", "tasa_cambio", "usuario_id", "direccion", "saldo", "imagen")) if tienda else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, whatsapp, tasa_cambio, usuario_id, direccion, saldo, imagen FROM tiendas WHERE usuario_id = ? LIMIT 1",
        (usuario_id,),
    )
    tienda = cursor.fetchone()
    conn.close()
    return tienda


def obtener_tienda_por_id(tienda_id):
    if _supabase_activo():
        tienda = _supabase_unico(
            "tiendas", f"?select=id,nombre,whatsapp,tasa_cambio,usuario_id,direccion,saldo,imagen&id=eq.{tienda_id}&limit=1"
        )
        return tuple(tienda.get(campo) for campo in ("id", "nombre", "whatsapp", "tasa_cambio", "usuario_id", "direccion", "saldo", "imagen")) if tienda else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
            "SELECT id, nombre, whatsapp, tasa_cambio, usuario_id, direccion, saldo, imagen FROM tiendas WHERE id = ?",
        (tienda_id,),
    )
    tienda = cursor.fetchone()
    conn.close()
    return tienda


def obtener_productos_aleatorios(limit=5, usuario_id=None):
    if _supabase_activo():
        if usuario_id is not None:
            filas = _supabase_lista(
                "productos",
                f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion,tiendas!inner(usuario_id)&tiendas.usuario_id=eq.{usuario_id}&limit={int(limit)}",
            )
        else:
            filas = _supabase_lista(
                "productos",
                f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion&limit={int(limit)}",
            )
        return [tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2", "categoria", "descripcion", "estado_producto", "etiquetas", "estilo", "color_principal", "material", "garantia", "especificacion")) for fila in filas]
    conn = get_db_connection()
    cursor = conn.cursor()
    if usuario_id is not None:
        cursor.execute(
            """
            SELECT p.id, p.nombre, p.marca, p.talla, p.precio_cordobas, p.precio_dolares, p.stock, p.tienda_id, p.imagen, p.imagen_2, p.categoria,
            p.descripcion, p.estado_producto, p.etiquetas, p.estilo, p.color_principal, p.material, p.garantia, p.especificacion
            FROM productos p
            INNER JOIN tiendas t ON t.id = p.tienda_id
            WHERE t.usuario_id = ?
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (usuario_id, limit),
        )
    else:
        cursor.execute(
            "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen, imagen_2, categoria, descripcion, estado_producto, etiquetas, estilo, color_principal, material, garantia, especificacion FROM productos ORDER BY RANDOM() LIMIT ?",
            (limit,),
        )
    productos = cursor.fetchall()
    conn.close()
    return productos


def obtener_top_productos(limit=10, min_compras=3):
    if _supabase_activo():
        filas = _supabase_lista("reservas", "?select=producto_id&estado=eq.Pagado")
        conteo = {}
        for fila in filas:
            producto_id = fila.get("producto_id")
            conteo[producto_id] = conteo.get(producto_id, 0) + 1
        resultados = []
        for producto_id, compras in sorted(conteo.items(), key=lambda item: item[1], reverse=True):
            if compras < min_compras:
                continue
            producto = _supabase_unico("productos", f"?select=id,nombre,precio_cordobas,precio_dolares,stock&id=eq.{producto_id}&limit=1")
            if producto:
                resultados.append((producto["id"], producto["nombre"], producto.get("precio_cordobas"), producto.get("precio_dolares"), producto.get("stock"), compras, obtener_promedio_calificacion(producto_id)))
            if len(resultados) >= limit:
                break
        return resultados
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.nombre, p.precio_cordobas, p.precio_dolares, p.stock,
               COUNT(r.id) as compras,
               AVG(res.calificacion) as promedio_calificacion
        FROM productos p
        JOIN reservas r ON r.producto_id = p.id AND r.estado = 'Pagado'
        LEFT JOIN resenas res ON res.producto_id = p.id
        GROUP BY p.id
        HAVING COUNT(r.id) >= ?
        ORDER BY compras DESC
        LIMIT ?
    """,
        (min_compras, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def obtener_promedio_calificacion(producto_id):
    if _supabase_activo():
        filas = _supabase_lista("resenas", f"?select=calificacion&producto_id=eq.{producto_id}")
        valores = [fila.get("calificacion") for fila in filas if fila.get("calificacion") is not None]
        return sum(valores) / len(valores) if valores else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT AVG(calificacion) FROM resenas WHERE producto_id = ?",
        (producto_id,),
    )
    r = cursor.fetchone()
    conn.close()
    return float(r[0]) if r and r[0] is not None else None


def obtener_resumen_calificacion(producto_id):
    """Devuelve promedio y cantidad de reseñas verificables del producto."""
    if _supabase_activo():
        filas = _supabase_lista("resenas", f"?select=calificacion&producto_id=eq.{producto_id}")
        valores = [int(fila["calificacion"]) for fila in filas if fila.get("calificacion") is not None]
        return (sum(valores) / len(valores), len(valores)) if valores else (None, 0)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT AVG(calificacion), COUNT(calificacion) FROM resenas WHERE producto_id = ?",
        (producto_id,),
    )
    promedio, cantidad = cursor.fetchone()
    conn.close()
    return (float(promedio), int(cantidad)) if promedio is not None else (None, 0)


def obtener_tiendas_usuario(usuario_id):
    if _supabase_activo():
        filas = _supabase_lista("tiendas", f"?select=id,nombre,whatsapp,tasa_cambio,usuario_id,direccion,saldo,imagen&usuario_id=eq.{usuario_id}")
        return [tuple(fila.get(campo) for campo in ("id", "nombre", "whatsapp", "tasa_cambio", "usuario_id", "direccion", "saldo", "imagen")) for fila in filas]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
            "SELECT id, nombre, whatsapp, tasa_cambio, usuario_id, direccion, saldo, imagen FROM tiendas WHERE usuario_id = ?",
        (usuario_id,),
    )
    tiendas = cursor.fetchall()
    conn.close()
    return tiendas


def eliminar_tienda(tienda_id, usuario_id):
    """Elimina una tienda y sus datos relacionados solo si no conserva saldo."""
    if _supabase_activo():
        tienda = _supabase_unico("tiendas", f"?select=saldo&id=eq.{tienda_id}&usuario_id=eq.{usuario_id}&limit=1")
        if not tienda:
            return False, "No se encontró la tienda o no tienes permiso para eliminarla."
        if float(tienda.get("saldo") or 0) > 0:
            return False, "Retira primero el saldo de la billetera para no perder tus fondos."
        _supabase_borrar("tiendas", f"?id=eq.{tienda_id}&usuario_id=eq.{usuario_id}")
        return True, "Tienda eliminada correctamente."
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT saldo, imagen FROM tiendas WHERE id = ? AND usuario_id = ?",
            (tienda_id, usuario_id),
        )
        tienda = cursor.fetchone()
        if not tienda:
            return False, "No se encontró la tienda o no tienes permiso para eliminarla."

        saldo = float(tienda[0] or 0)
        if saldo > 0:
            return False, "Retira primero el saldo de la billetera para no perder tus fondos."

        cursor.execute("DELETE FROM reservas WHERE tienda_id = ?", (tienda_id,))
        cursor.execute("DELETE FROM productos WHERE tienda_id = ?", (tienda_id,))
        cursor.execute(
            "DELETE FROM tiendas WHERE id = ? AND usuario_id = ?",
            (tienda_id, usuario_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False, "No se pudo eliminar la tienda."
        conn.commit()
        return True, "Tienda eliminada correctamente."
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def guardar_tienda(
    nombre, whatsapp, tasa_cambio, usuario_id=None, direccion="", imagen=None
):
    if _supabase_activo():
        try:
            tienda = _supabase_insertar(
                "tiendas",
                {"nombre": nombre, "whatsapp": whatsapp, "tasa_cambio": tasa_cambio,
                 "usuario_id": usuario_id, "direccion": direccion, "saldo": 0, "imagen": imagen},
            )
            return tienda.get("id") if isinstance(tienda, dict) else None
        except Exception:
            return None
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if usuario_id is not None:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT 1 FROM tiendas WHERE usuario_id = ? LIMIT 1", (usuario_id,))
            if cursor.fetchone():
                conn.rollback()
                return None
        cursor.execute(
            """
            INSERT INTO tiendas (nombre, whatsapp, tasa_cambio, usuario_id, direccion, saldo, imagen)
            VALUES (?,?,?,?,?,?,?)
        """,
            (nombre, whatsapp, tasa_cambio, usuario_id, direccion, 0.0, imagen),
        )
        tienda_id = cursor.lastrowid
        conn.commit()
        return tienda_id
    finally:
        conn.close()


def actualizar_tienda(tienda_id, usuario_id, nombre, whatsapp, tasa_cambio, direccion, imagen):
    if _supabase_activo():
        resultado = _supabase_actualizar(
            "tiendas",
            {"nombre": nombre, "whatsapp": whatsapp, "tasa_cambio": tasa_cambio, "direccion": direccion, "imagen": imagen},
            f"?id=eq.{tienda_id}&usuario_id=eq.{usuario_id}",
        )
        return bool(resultado)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tiendas
        SET nombre = ?, whatsapp = ?, tasa_cambio = ?, direccion = ?, imagen = ?
        WHERE id = ? AND usuario_id = ?
        """,
        (nombre, whatsapp, tasa_cambio, direccion, imagen, tienda_id, usuario_id),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizado


def registrar_producto(
    nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen=None, usuario_id=None,
    categoria="General", imagen_2=None, descripcion=None, estado_producto="Nuevo", etiquetas=None,
    estilo=None, color_principal=None, material=None, garantia=None, especificacion=None
):
    if _supabase_activo():
        if tienda_id is None:
            return False
        try:
            tienda = _supabase_unico("tiendas", f"?select=id&usuario_id=eq.{usuario_id}&id=eq.{tienda_id}&limit=1")
            if not tienda:
                return False
            _supabase_insertar(
                "productos",
                {"nombre": nombre, "marca": marca, "talla": talla,
                 "precio_cordobas": precio_cordobas, "precio_dolares": precio_dolares,
                 "stock": stock, "tienda_id": tienda_id, "imagen": imagen,
                 "categoria": categoria or "General", "imagen_2": imagen_2,
                 "descripcion": descripcion, "estado_producto": estado_producto or "Nuevo",
                 "etiquetas": etiquetas, "estilo": estilo, "color_principal": color_principal,
                 "material": material, "garantia": garantia, "especificacion": especificacion},
            )
            return True
        except Exception:
            return False
    conn = get_db_connection()
    cursor = conn.cursor()
    if tienda_id is not None:
        cursor.execute(
            "SELECT 1 FROM tiendas WHERE id = ? AND usuario_id = ?",
            (tienda_id, usuario_id),
        )
        if not cursor.fetchone():
            conn.close()
            return False
    cursor.execute(
        """
        INSERT INTO productos (
            nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen,
            categoria, imagen_2, descripcion, estado_producto, etiquetas, estilo,
            color_principal, material, garantia, especificacion
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        (
            nombre,
            marca,
            talla,
            precio_cordobas,
            precio_dolares,
            stock,
            tienda_id,
            imagen,
            categoria or "General",
            imagen_2,
            descripcion,
            estado_producto or "Nuevo",
            etiquetas,
            estilo,
            color_principal,
            material,
            garantia,
            especificacion,
        ),
    )
    conn.commit()
    conn.close()
    return True


def actualizar_producto(producto_id, usuario_id, nombre, marca, talla, precio_cordobas, precio_dolares, stock):
    if _supabase_activo():
        producto = _supabase_unico("productos", f"?select=tienda_id&id=eq.{producto_id}&limit=1")
        if not producto:
            return False
        tienda = _supabase_unico("tiendas", f"?select=id&usuario_id=eq.{usuario_id}&id=eq.{producto['tienda_id']}&limit=1")
        if not tienda:
            return False
        resultado = _supabase_actualizar(
            "productos",
            {"nombre": nombre, "marca": marca, "talla": talla, "precio_cordobas": precio_cordobas, "precio_dolares": precio_dolares, "stock": stock},
            f"?id=eq.{producto_id}",
        )
        return bool(resultado)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE productos
        SET nombre = ?, marca = ?, talla = ?, precio_cordobas = ?,
            precio_dolares = ?, stock = ?
        WHERE id = ? AND tienda_id IN (SELECT id FROM tiendas WHERE usuario_id = ?)
        """,
        (nombre, marca, talla, precio_cordobas, precio_dolares, stock, producto_id, usuario_id),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizado


def obtener_productos():
    if _supabase_activo():
        return [tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2")) for fila in _supabase_lista("productos", "?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2")]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen, imagen_2 FROM productos"
    )
    productos = cursor.fetchall()
    conn.close()
    return productos


def obtener_productos_usuario(usuario_id):
    if _supabase_activo():
        filas = _supabase_lista("productos", f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion,tiendas!inner(usuario_id)&tiendas.usuario_id=eq.{usuario_id}")
        return [tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2", "categoria", "descripcion", "estado_producto", "etiquetas", "estilo", "color_principal", "material", "garantia", "especificacion")) for fila in filas]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
         SELECT p.id, p.nombre, p.marca, p.talla, p.precio_cordobas,
             p.precio_dolares, p.stock, p.tienda_id, p.imagen, p.imagen_2, p.categoria,
             p.descripcion, p.estado_producto, p.etiquetas, p.estilo, p.color_principal, p.material, p.garantia, p.especificacion
        FROM productos p
        INNER JOIN tiendas t ON t.id = p.tienda_id
        WHERE t.usuario_id = ?
        """,
        (usuario_id,),
    )
    productos = cursor.fetchall()
    conn.close()
    return productos


def obtener_producto_por_id(producto_id):
    if _supabase_activo():
        fila = _supabase_unico("productos", f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion&id=eq.{producto_id}&limit=1")
        return tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2", "categoria", "descripcion", "estado_producto", "etiquetas", "estilo", "color_principal", "material", "garantia", "especificacion")) if fila else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen, categoria, descripcion, estado_producto, etiquetas, estilo, color_principal, material, garantia, especificacion "
        "FROM productos WHERE id = ?",
        (producto_id,),
    )
    producto = cursor.fetchone()
    conn.close()
    return producto


def obtener_productos_por_nombre(nombre_filtro, usuario_id=None):
    if _supabase_activo():
        valor = quote(str(nombre_filtro), safe="")
        if usuario_id is not None:
            filas = _supabase_lista(
                "productos",
                f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion,tiendas!inner(usuario_id)&tiendas.usuario_id=eq.{usuario_id}&nombre=ilike.*{valor}*&limit=50",
            )
        else:
            filas = _supabase_lista(
                "productos",
                f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion&nombre=ilike.*{valor}*&limit=50",
            )
        return [tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2", "categoria", "descripcion", "estado_producto", "etiquetas", "estilo", "color_principal", "material", "garantia", "especificacion")) for fila in filas]
    conn = get_db_connection()
    cursor = conn.cursor()
    if usuario_id is not None:
        cursor.execute(
            """
            SELECT p.id, p.nombre, p.marca, p.talla, p.precio_cordobas, p.precio_dolares, p.stock, p.tienda_id, p.imagen, p.imagen_2, p.categoria,
            p.descripcion, p.estado_producto, p.etiquetas, p.estilo, p.color_principal, p.material, p.garantia, p.especificacion
            FROM productos p
            INNER JOIN tiendas t ON t.id = p.tienda_id
            WHERE t.usuario_id = ? AND p.nombre LIKE ?
            """,
            (usuario_id, f"%{nombre_filtro}%"),
        )
    else:
        cursor.execute(
            "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen, imagen_2, categoria, descripcion, estado_producto, etiquetas, estilo, color_principal, material, garantia, especificacion FROM productos WHERE nombre LIKE ?",
            (f"%{nombre_filtro}%",),
        )
    productos = cursor.fetchall()
    conn.close()
    return productos


def obtener_productos_por_tienda(tienda_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock FROM productos WHERE tienda_id = ?",
        (tienda_id,),
    )
    productos = cursor.fetchall()
    conn.close()
    return productos


def obtener_stock_total():
    if _supabase_activo():
        filas = _supabase_lista("productos", "?select=stock")
        return sum(int(fila.get("stock") or 0) for fila in filas)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(stock) FROM productos")
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total


def obtener_stock_total_usuario(usuario_id):
    if _supabase_activo():
        return sum(int(fila[6] or 0) for fila in obtener_productos_usuario(usuario_id))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT SUM(p.stock)
        FROM productos p
        INNER JOIN tiendas t ON t.id = p.tienda_id
        WHERE t.usuario_id = ?
        """,
        (usuario_id,),
    )
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total


def obtener_alertas_inventario(usuario_id, limite_stock=1):
    """Devuelve productos con exactamente una unidad disponible."""
    if _supabase_activo():
        filas = _supabase_lista(
            "productos",
            f"?select=id,nombre,stock,tiendas!inner(usuario_id)&tiendas.usuario_id=eq.{usuario_id}&stock=eq.{int(limite_stock)}&order=nombre.asc&limit=20",
        )
        return [
            (fila.get("id"), fila.get("nombre"), int(fila.get("stock") or 0))
            for fila in filas
        ]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.nombre, p.stock
        FROM productos p
        INNER JOIN tiendas t ON t.id = p.tienda_id
        WHERE t.usuario_id = ? AND p.stock = ?
        ORDER BY p.nombre ASC
        LIMIT 20
        """,
        (usuario_id, limite_stock),
    )
    alertas = cursor.fetchall()
    conn.close()
    return alertas


def obtener_saldo_tienda(tienda_id):
    if _supabase_activo():
        tienda = _supabase_unico("tiendas", f"?select=saldo&id=eq.{tienda_id}&limit=1")
        return tienda.get("saldo", 0.0) if tienda else 0.0
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT saldo FROM tiendas WHERE id = ?", (tienda_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else 0.0


def agregar_saldo_tienda(tienda_id, monto):
    if _supabase_activo():
        saldo = float(obtener_saldo_tienda(tienda_id) or 0) + float(monto)
        _supabase_actualizar("tiendas", {"saldo": saldo}, f"?id=eq.{tienda_id}")
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    saldo_actual = obtener_saldo_tienda(tienda_id)
    nuevo_saldo = saldo_actual + monto
    cursor.execute(
        "UPDATE tiendas SET saldo = ? WHERE id = ?", (nuevo_saldo, tienda_id)
    )
    conn.commit()
    conn.close()


def retirar_saldo_tienda(tienda_id, monto):
    if _supabase_activo():
        saldo = float(obtener_saldo_tienda(tienda_id) or 0)
        if float(monto) <= saldo:
            _supabase_actualizar("tiendas", {"saldo": saldo - float(monto)}, f"?id=eq.{tienda_id}")
            return True
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    saldo_actual = obtener_saldo_tienda(tienda_id)
    if monto <= saldo_actual:
        nuevo_saldo = saldo_actual - monto
        cursor.execute(
            "UPDATE tiendas SET saldo = ? WHERE id = ?",
            (nuevo_saldo, tienda_id),
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def agregar_reserva(usuario_id, producto_id, cantidad, tienda_id):
    if _supabase_activo():
        try:
            resultado = supabase_rpc(
                "crear_reserva",
                {"p_usuario_id": usuario_id, "p_producto_id": producto_id, "p_cantidad": cantidad, "p_tienda_id": tienda_id},
            ) or {}
            return bool(resultado.get("ok")), resultado.get("message", "No se pudo crear la reserva")
        except Exception as exc:
            _marcar_supabase_caido(f"Error al crear reserva remota: {exc}")
    conn = get_db_connection()
    conn.isolation_level = None
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT tienda_id FROM productos WHERE id = ?",
            (producto_id,),
        )
        producto = cursor.fetchone()
        if not producto or producto[0] != tienda_id:
            cursor.execute("ROLLBACK")
            return False, "El producto no pertenece a esa tienda"

        cursor.execute(
            "UPDATE productos SET stock = stock - ? WHERE id = ? AND stock >= ?",
            (cantidad, producto_id, cantidad),
        )
        if cursor.rowcount != 1:
            cursor.execute("ROLLBACK")
            return False, "No hay suficiente stock disponible"

        fecha = datetime.now()
        cursor.execute(
            """
            INSERT INTO reservas (usuario_id, producto_id, cantidad, fecha, estado, tienda_id, fecha_expiracion)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                usuario_id,
                producto_id,
                cantidad,
                str(fecha),
                "Reservado",
                tienda_id,
                str(fecha + timedelta(hours=24)),
            ),
        )
        cursor.execute("COMMIT")
        return True, "Reserva creada"
    except Exception as error:
        try:
            cursor.execute("ROLLBACK")
        finally:
            conn.close()
        return False, str(error)
    finally:
        if conn:
            conn.close()


def obtener_reservas_usuario(usuario_id):
    if _supabase_activo():
        filas = _supabase_lista(
            "reservas",
            f"?select=id,productos(nombre,precio_cordobas,precio_dolares),cantidad,estado,tienda_id&usuario_id=eq.{usuario_id}",
        )
        return [
            (fila["id"], fila.get("productos", {}).get("nombre"), fila["cantidad"],
             fila.get("productos", {}).get("precio_cordobas"), fila.get("productos", {}).get("precio_dolares"),
             fila["estado"], fila["tienda_id"])
            for fila in filas
        ]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, p.nombre, r.cantidad, p.precio_cordobas, p.precio_dolares, r.estado, r.tienda_id
        FROM reservas r
        JOIN productos p ON r.producto_id = p.id
        WHERE r.usuario_id = ?
    """,
        (usuario_id,),
    )
    reservas = cursor.fetchall()
    conn.close()
    return reservas


def cancelar_reservas_vencidas():
    """Cancela reservas pendientes vencidas y devuelve su stock al inventario."""
    if _supabase_activo():
        try:
            return int(supabase_rpc("cancelar_reservas_vencidas_rpc") or 0)
        except Exception as exc:
            _marcar_supabase_caido(f"Error al cancelar reservas remotas vencidas: {exc}")
    conn = get_db_connection()
    conn.isolation_level = None
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT id, producto_id, cantidad FROM reservas "
            "WHERE estado = 'Reservado' AND fecha_expiracion IS NOT NULL "
            "AND fecha_expiracion <= ?",
            (str(datetime.now()),),
        )
        vencidas = cursor.fetchall()
        for reserva_id, producto_id, cantidad in vencidas:
            cursor.execute(
                "UPDATE productos SET stock = stock + ? WHERE id = ?",
                (cantidad, producto_id),
            )
            cursor.execute(
                "UPDATE reservas SET estado = 'Vencido' WHERE id = ? AND estado = 'Reservado'",
                (reserva_id,),
            )
        cursor.execute("COMMIT")
        return len(vencidas)
    except Exception:
        cursor.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def obtener_reservas_por_tienda(tienda_id):
    if _supabase_activo():
        filas = _supabase_lista(
            "reservas",
            f"?select=id,productos(nombre,precio_cordobas),cantidad,usuarios(nombre),fecha,estado&tienda_id=eq.{tienda_id}&estado=in.(Reservado,Pagado,Preparando,Listo para entregar)&order=fecha.asc",
        )
        return [
            (fila["id"], fila.get("productos", {}).get("nombre"), fila["cantidad"],
             (fila.get("productos", {}).get("precio_cordobas") or 0) * fila["cantidad"],
             fila.get("usuarios", {}).get("nombre"), fila.get("fecha"), fila.get("estado"))
            for fila in filas
        ]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, p.nombre, r.cantidad, p.precio_cordobas * r.cantidad, u.nombre, r.fecha, r.estado
        FROM reservas r
        JOIN productos p ON r.producto_id = p.id
        JOIN usuarios u ON r.usuario_id = u.id
        WHERE r.tienda_id = ? AND r.estado IN ('Reservado', 'Pagado', 'Preparando', 'Listo para entregar')
        ORDER BY r.fecha ASC
    """,
        (tienda_id,),
    )
    reservas = cursor.fetchall()
    conn.close()
    return reservas


def obtener_ventas_semana(usuario_id):
    """Devuelve las ventas pagadas de las tiendas del usuario por día."""
    if _supabase_activo():
        filas = _supabase_lista(
            "reservas",
            f"?select=fecha,cantidad,productos(precio_cordobas),tiendas!inner(usuario_id)&estado=eq.Pagado&tiendas.usuario_id=eq.{usuario_id}",
        )
        ventas = {}
        for fila in filas:
            fecha = (fila.get("fecha") or "")[:10]
            ventas[fecha] = ventas.get(fecha, 0) + (fila.get("productos", {}).get("precio_cordobas") or 0) * fila.get("cantidad", 0)
        return list(ventas.items())

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date(r.fecha), COALESCE(SUM(p.precio_cordobas * r.cantidad), 0)
        FROM reservas r
        JOIN productos p ON r.producto_id = p.id
        JOIN tiendas t ON r.tienda_id = t.id
        WHERE t.usuario_id = ? AND r.estado = 'Pagado'
        GROUP BY date(r.fecha)
        ORDER BY date(r.fecha)
        """,
        (usuario_id,),
    )
    ventas = cursor.fetchall()
    conn.close()
    return ventas


def obtener_entregas_completadas_por_tienda(tienda_id):
    if _supabase_activo():
        filas = _supabase_lista(
            "reservas",
            f"?select=id,productos(nombre,precio_cordobas),cantidad,usuarios(nombre),fecha_entrega&tienda_id=eq.{tienda_id}&estado=eq.Entregado&order=fecha_entrega.desc",
        )
        return [
            (fila["id"], fila.get("productos", {}).get("nombre"), fila["cantidad"],
             (fila.get("productos", {}).get("precio_cordobas") or 0) * fila["cantidad"],
             fila.get("usuarios", {}).get("nombre"), fila.get("fecha_entrega"))
            for fila in filas
        ]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, p.nombre, r.cantidad, p.precio_cordobas * r.cantidad, u.nombre, r.fecha_entrega
        FROM reservas r
        JOIN productos p ON r.producto_id = p.id
        JOIN usuarios u ON r.usuario_id = u.id
        WHERE r.tienda_id = ? AND r.estado = 'Entregado'
        ORDER BY r.fecha_entrega DESC
    """,
        (tienda_id,),
    )
    entregas = cursor.fetchall()
    conn.close()
    return entregas


def eliminar_reserva(reserva_id):
    if _supabase_activo():
        reserva = _supabase_unico("reservas", f"?select=producto_id,cantidad,estado&id=eq.{reserva_id}&limit=1")
        if reserva and reserva.get("estado") == "Reservado":
            producto = _supabase_unico("productos", f"?select=stock&id=eq.{reserva['producto_id']}&limit=1")
            if producto:
                _supabase_actualizar("productos", {"stock": int(producto.get("stock") or 0) + int(reserva["cantidad"])}, f"?id=eq.{reserva['producto_id']}")
        _supabase_borrar("reservas", f"?id=eq.{reserva_id}")
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT producto_id, cantidad, estado FROM reservas WHERE id = ?",
        (reserva_id,),
    )
    reserva = cursor.fetchone()
    if reserva and reserva[2] == "Reservado":
        cursor.execute(
            "UPDATE productos SET stock = stock + ? WHERE id = ?",
            (reserva[1], reserva[0]),
        )
    cursor.execute("DELETE FROM reservas WHERE id = ?", (reserva_id,))
    conn.commit()
    conn.close()


def confirmar_reserva(reserva_id):
    if _supabase_activo():
        _supabase_actualizar("reservas", {"estado": "Pagado"}, f"?id=eq.{reserva_id}")
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE reservas SET estado = 'Pagado' WHERE id = ?", (reserva_id,)
    )
    conn.commit()
    conn.close()


# ==========================================
# CÓDIGO DE REEMPLAZO (En database.py)
# ==========================================
def procesar_pago_reserva(reserva_id, monto, tienda_id):
    if _supabase_activo():
        try:
            resultado = supabase_rpc(
                "procesar_pago_reserva_rpc",
                {"p_reserva_id": reserva_id, "p_monto": monto, "p_tienda_id": tienda_id},
            ) or {}
            return bool(resultado.get("ok")), resultado.get("message", "No se pudo procesar el pago")
        except Exception as exc:
            _marcar_supabase_caido(f"Error al procesar pago remoto: {exc}")
    conn = get_db_connection()
    # Desactivar manejo implícito de transacciones para control manual
    conn.isolation_level = None
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")
        
        # 1. Obtenemos estado, producto_id y cantidad asociada a la reserva
        cursor.execute("SELECT estado, tienda_id FROM reservas WHERE id = ?", (reserva_id,))
        res = cursor.fetchone()
        if not res:
            cursor.execute("ROLLBACK;")
            conn.close()
            print(f"⚠️ procesar_pago_reserva: Reserva #{reserva_id} no encontrada")
            return False, "Reserva no encontrada"
        
        estado, tienda_reserva_id = res[0], res[1]
        if estado != "Reservado":
            cursor.execute("ROLLBACK;")
            conn.close()
            print(f"⚠️ procesar_pago_reserva: Reserva #{reserva_id} ya está en estado: {estado}")
            return False, f"La reserva ya está en estado: {estado}"

        if tienda_reserva_id != tienda_id:
            cursor.execute("ROLLBACK;")
            conn.close()
            return False, "La tienda del pago no coincide con la reserva"

        # El stock ya fue apartado al confirmar la reserva.
        cursor.execute("UPDATE reservas SET estado = 'Pagado' WHERE id = ?", (reserva_id,))
        cursor.execute("UPDATE tiendas SET saldo = saldo + ? WHERE id = ?", (monto, tienda_id))

        cursor.execute("COMMIT;")
        conn.close()
        return True, "Pago procesado y saldo acreditado a la tienda"

    except Exception as e:
        cursor.execute("ROLLBACK;")
        conn.close()
        print(f"❌ Error en procesar_pago_reserva: {e}")
        return False, str(e)
        
        return False, f"Error al procesar: {str(e)}"


def marcar_como_entregada(reserva_id):
    if _supabase_activo():
        resultado = _supabase_actualizar(
            "reservas",
            {"estado": "Entregado", "fecha_entrega": datetime.now().isoformat()},
            f"?id=eq.{reserva_id}&estado=in.(Pagado,Preparando,Listo%20para%20entregar)",
        )
        return bool(resultado)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE reservas 
        SET estado = 'Entregado', fecha_entrega = ? 
        WHERE id = ? AND estado IN ('Pagado', 'Preparando', 'Listo para entregar')
    """,
        (datetime.now(), reserva_id),
    )
    actualizada = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizada


def verificar_conexion_remota():
    if not USAR_SUPABASE:
        raise RuntimeError("Supabase está desactivado localmente.")
    if not supabase_esta_configurado():
        raise RuntimeError("Supabase no está configurado.")
    try:
        supabase_request("usuarios", parametros="?select=id&limit=1")
        return True
    except Exception as exc:
        _marcar_supabase_caido(f"Verificacion de conexión remota fallida: {exc}")
        raise RuntimeError("No hay conexión a internet o la base de datos no está disponible.") from exc


def verificar_correo_existe(correo):
    if _supabase_activo():
        return _supabase_unico("usuarios", f"?select=id&correo=eq.{quote(str(correo), safe='')}&limit=1") is not None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE correo = ?", (correo,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None


def obtener_telefono_por_correo(correo):
    if _supabase_activo():
        usuario = _supabase_unico("usuarios", f"?select=telefono&correo=eq.{quote(str(correo), safe='')}&limit=1")
        return usuario.get("telefono") if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telefono FROM usuarios WHERE correo = ?", (correo,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None


def obtener_usuario_por_correo(correo):
    if _supabase_activo():
        usuario = _supabase_unico("usuarios", f"?select=id,nombre,correo,telefono,fecha_nacimiento,contraseña&correo=eq.{quote(str(correo), safe='')}&limit=1")
        return tuple(usuario.get(campo) for campo in ("id", "nombre", "correo", "telefono", "fecha_nacimiento", "contraseña")) if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, correo, telefono, fecha_nacimiento, contraseña FROM usuarios WHERE correo = ?",
        (correo,),
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado


def obtener_usuario_por_telefono(telefono):
    valor = (telefono or "").strip()
    if not valor:
        return None

    valores_busqueda = []
    valores_busqueda.append(valor)

    solo_numeros = "".join(caracter for caracter in valor if caracter.isdigit())
    if solo_numeros:
        valores_busqueda.append(solo_numeros)
        if solo_numeros.startswith("505"):
            valores_busqueda.append(solo_numeros[3:])
        else:
            valores_busqueda.append(f"505{solo_numeros}")

    valores_unicos = []
    for item in valores_busqueda:
        if item and item not in valores_unicos:
            valores_unicos.append(item)

    if not valores_unicos:
        return None

    if _supabase_activo():
        for valor in valores_unicos:
            usuario = _supabase_unico("usuarios", f"?select=id,nombre,correo,telefono,fecha_nacimiento,contraseña&telefono=eq.{quote(valor, safe='')}&limit=1")
            if usuario:
                return tuple(usuario.get(campo) for campo in ("id", "nombre", "correo", "telefono", "fecha_nacimiento", "contraseña"))
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    parametros = valores_unicos + [None] * (3 - len(valores_unicos))
    cursor.execute(
        """
        SELECT id, nombre, correo, telefono, fecha_nacimiento, contraseña
        FROM usuarios
        WHERE telefono IN (?, ?, ?)
        """,
        tuple(parametros),
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado


def actualizar_contraseña_por_correo(correo, nueva_contraseña):
    if _supabase_activo():
        return bool(_supabase_actualizar("usuarios", {"contraseña": nueva_contraseña}, f"?correo=eq.{quote(str(correo), safe='')}"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET contraseña = ? WHERE correo = ?",
        (nueva_contraseña, correo),
    )
    conn.commit()
    actualizado = cursor.rowcount > 0
    conn.close()
    return actualizado


def obtener_contraseña_por_correo(correo):
    if _supabase_activo():
        usuario = _supabase_unico("usuarios", f"?select=contraseña&correo=eq.{quote(str(correo), safe='')}&limit=1")
        return usuario.get("contraseña") if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT contraseña FROM usuarios WHERE correo = ?", (correo,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None


def eliminar_producto(producto_id, usuario_id):
    if _supabase_activo():
        producto = _supabase_unico("productos", f"?select=tienda_id&id=eq.{producto_id}&limit=1")
        if not producto:
            return False
        tienda = _supabase_unico("tiendas", f"?select=id&usuario_id=eq.{usuario_id}&id=eq.{producto['tienda_id']}&limit=1")
        if not tienda:
            return False
        _supabase_borrar("productos", f"?id=eq.{producto_id}")
        return True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM productos
        WHERE id = ? AND tienda_id IN (SELECT id FROM tiendas WHERE usuario_id = ?)
        """,
        (producto_id, usuario_id),
    )
    eliminado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return eliminado


def reducir_stock_producto(producto_id, cantidad, usuario_id):
    if _supabase_activo():
        producto = _supabase_unico("productos", f"?select=stock,tienda_id&id=eq.{producto_id}&limit=1")
        if not producto or int(cantidad) <= 0 or int(cantidad) > int(producto.get("stock") or 0):
            return False
        tienda = _supabase_unico("tiendas", f"?select=id&usuario_id=eq.{usuario_id}&id=eq.{producto['tienda_id']}&limit=1")
        if not tienda:
            return False
        restante = int(producto["stock"]) - int(cantidad)
        if restante == 0:
            _supabase_borrar("productos", f"?id=eq.{producto_id}")
        else:
            _supabase_actualizar("productos", {"stock": restante}, f"?id=eq.{producto_id}")
        return True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.stock
        FROM productos p
        INNER JOIN tiendas t ON t.id = p.tienda_id
        WHERE p.id = ? AND t.usuario_id = ?
        """,
        (producto_id, usuario_id),
    )
    producto = cursor.fetchone()
    if not producto or cantidad <= 0 or cantidad > producto[0]:
        conn.close()
        return False

    stock_restante = producto[0] - cantidad
    if stock_restante == 0:
        cursor.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
    else:
        cursor.execute(
            "UPDATE productos SET stock = ? WHERE id = ?",
            (stock_restante, producto_id),
        )
    conn.commit()
    conn.close()
    return True


# ====================
# 💳 PAYPAL
# ====================


def guardar_paypal_email(usuario_id, email):
    if _supabase_activo():
        return bool(_supabase_actualizar("usuarios", {"paypal_email": email}, f"?id=eq.{usuario_id}"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET paypal_email = ? WHERE id = ?", (email, usuario_id)
    )
    conn.commit()
    conn.close()


def obtener_paypal_email(usuario_id):
    if _supabase_activo():
        usuario = _supabase_unico("usuarios", f"?select=paypal_email&id=eq.{usuario_id}&limit=1")
        return (usuario.get("paypal_email") or PAYPAL_VENDEDOR_SANDBOX) if usuario else PAYPAL_VENDEDOR_SANDBOX
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT paypal_email FROM usuarios WHERE id = ?", (usuario_id,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return (
        resultado[0]
        if (resultado and resultado[0])
        else PAYPAL_VENDEDOR_SANDBOX
    )


def guardar_order_id(reserva_id, order_id):
    if _supabase_activo():
        return bool(_supabase_actualizar("reservas", {"order_id": order_id}, f"?id=eq.{reserva_id}"))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE reservas ADD COLUMN order_id TEXT")
        conn.commit()
    except:
        pass
    cursor.execute(
        "UPDATE reservas SET order_id = ? WHERE id = ?", (order_id, reserva_id)
    )
    conn.commit()
    conn.close()


def obtener_estado_reserva(reserva_id):
    if _supabase_activo():
        reserva = _supabase_unico("reservas", f"?select=estado&id=eq.{reserva_id}&limit=1")
        return reserva.get("estado") if reserva else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT estado FROM reservas WHERE id = ?", (reserva_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None


def obtener_order_id(reserva_id):
    """Obtiene el ID de la orden de PayPal"""
    if _supabase_activo():
        reserva = _supabase_unico("reservas", f"?select=order_id&id=eq.{reserva_id}&limit=1")
        return reserva.get("order_id") if reserva else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_id FROM reservas WHERE id = ?", (reserva_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None


def cambiar_estado_reserva(reserva_id, nuevo_estado):
    """Cambia el estado de una reserva"""
    if _supabase_activo():
        return bool(_supabase_actualizar("reservas", {"estado": nuevo_estado}, f"?id=eq.{reserva_id}"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE reservas SET estado = ? WHERE id = ?",
        (nuevo_estado, reserva_id)
    )
    conn.commit()
    conn.close()


def actualizar_estado_pago(order_id):
    if _supabase_activo():
        return bool(_supabase_actualizar("reservas", {"estado": "Pagado"}, f"?order_id=eq.{quote(str(order_id), safe='')}"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, tienda_id, estado FROM reservas WHERE order_id = ?", (order_id,)
    )
    reserva = cursor.fetchone()
    conn.close()
    if reserva:
        reserva_id, tienda_id, estado = reserva
        if estado == "Reservado":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT precio_cordobas * cantidad FROM reservas r JOIN productos p ON r.producto_id = p.id WHERE r.id = ?",
                (reserva_id,),
            )
            total = cursor.fetchone()[0]
            conn.close()
            procesar_pago_reserva(reserva_id, total, tienda_id)