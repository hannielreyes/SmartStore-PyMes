from .conexion import (
    get_db_connection,
    _supabase_activo,
    _supabase_unico,
    _supabase_lista,
    _supabase_insertar,
    _supabase_actualizar,
    _supabase_borrar,
)
import bcrypt, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import quote


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