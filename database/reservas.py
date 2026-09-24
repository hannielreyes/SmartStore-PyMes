# Módulo generado automáticamente a partir de `legado.py`.
# No editar manualmente; los cambios deben hacerse en `legado.py` y volver a ejecutar este script.

from .conexion import (
    get_db_connection,
    _supabase_activo,
    _supabase_unico,
    _supabase_lista,
    _supabase_insertar,
    _supabase_actualizar,
    _supabase_borrar,
    _marcar_supabase_caido,
)
from supabase_config import supabase_rpc
import bcrypt, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import quote


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