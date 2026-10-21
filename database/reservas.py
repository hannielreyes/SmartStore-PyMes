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
from .models import EntregaTienda, ReservaCliente, ReservaTienda
import bcrypt, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import quote


def agregar_reserva(usuario_id, producto_id, cantidad, tienda_id):
    if int(cantidad) <= 0:
        return False, "La cantidad debe ser positiva", None
    if _supabase_activo():
        try:
            resultado = supabase_rpc(
                "crear_reserva",
                {"p_usuario_id": usuario_id, "p_producto_id": producto_id, "p_cantidad": cantidad, "p_tienda_id": tienda_id},
            ) or {}
            return bool(resultado.get("ok")), resultado.get("message", "No se pudo crear la reserva"), resultado.get("id")
        except Exception as exc:
            _marcar_supabase_caido(f"Error al crear reserva remota: {exc}")
            return False, "No se pudo confirmar el stock. Intenta nuevamente.", None
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
            return False, "El producto no pertenece a esa tienda", None

        cursor.execute(
            "SELECT id, cantidad FROM reservas WHERE producto_id = ? "
            "AND estado = 'Reservado' AND fecha_expiracion IS NOT NULL AND fecha_expiracion <= ?",
            (producto_id, str(datetime.now())),
        )
        vencidas = cursor.fetchall()
        for reserva_vencida_id, cantidad_vencida in vencidas:
            cursor.execute(
                "UPDATE productos SET stock = stock + ? WHERE id = ?",
                (cantidad_vencida, producto_id),
            )
            cursor.execute(
                "UPDATE reservas SET estado = 'Vencido' WHERE id = ? AND estado = 'Reservado'",
                (reserva_vencida_id,),
            )

        cursor.execute(
            "UPDATE productos SET stock = stock - ? WHERE id = ? AND stock >= ?",
            (cantidad, producto_id, cantidad),
        )
        if cursor.rowcount != 1:
            cursor.execute(
                "SELECT 1 FROM reservas WHERE producto_id = ? AND estado = 'Reservado' "
                "AND fecha_expiracion > ? LIMIT 1",
                (producto_id, str(datetime.now())),
            )
            en_proceso = cursor.fetchone() is not None
            cursor.execute("ROLLBACK")
            mensaje = (
                "Otra persona está completando su pago. Te avisaremos si el producto vuelve a estar disponible."
                if en_proceso else "El producto ya no tiene suficiente stock disponible."
            )
            return False, mensaje, None

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
                str(fecha + timedelta(minutes=10)),
            ),
        )
        reserva_id = cursor.lastrowid
        cursor.execute("COMMIT")
        return True, "Reserva creada", reserva_id
    except Exception as error:
        try:
            cursor.execute("ROLLBACK")
        finally:
            conn.close()
        return False, str(error), None
    finally:
        if conn:
            conn.close()


def obtener_reservas_usuario(usuario_id):
    if _supabase_activo():
        filas = _supabase_lista(
            "reservas",
            f"?select=id,productos(nombre,precio_cordobas,precio_dolares),cantidad,estado,tienda_id,codigo_retiro&usuario_id=eq.{usuario_id}&estado=in.(Pagado,Preparando,Listo%20para%20entregar,Entregado)",
        )
        return [
            ReservaCliente(fila["id"], fila.get("productos", {}).get("nombre"), fila["cantidad"],
                           fila.get("productos", {}).get("precio_cordobas"), fila.get("productos", {}).get("precio_dolares"),
                           fila["estado"], fila["tienda_id"], fila.get("codigo_retiro"))
            for fila in filas
        ]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, p.nombre, r.cantidad, p.precio_cordobas, p.precio_dolares, r.estado, r.tienda_id, r.codigo_retiro
        FROM reservas r
        JOIN productos p ON r.producto_id = p.id
        WHERE r.usuario_id = ? AND r.estado IN ('Pagado', 'Preparando', 'Listo para entregar', 'Entregado')
    """,
        (usuario_id,),
    )
    reservas = cursor.fetchall()
    conn.close()
    return [ReservaCliente.desde_fila(fila) for fila in reservas]


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
            ReservaTienda(fila["id"], fila.get("productos", {}).get("nombre"), fila["cantidad"],
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
        WHERE r.tienda_id = ? AND r.estado IN ('Pagado', 'Preparando', 'Listo para entregar')
        ORDER BY r.fecha ASC
    """,
        (tienda_id,),
    )
    reservas = cursor.fetchall()
    conn.close()
    return [ReservaTienda.desde_fila(fila) for fila in reservas]


def obtener_entregas_completadas_por_tienda(tienda_id):
    if _supabase_activo():
        filas = _supabase_lista(
            "reservas",
            f"?select=id,productos(nombre,precio_cordobas),cantidad,usuarios(nombre),fecha_entrega&tienda_id=eq.{tienda_id}&estado=eq.Entregado&order=fecha_entrega.desc",
        )
        return [
            EntregaTienda(fila["id"], fila.get("productos", {}).get("nombre"), fila["cantidad"],
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
    return [EntregaTienda.desde_fila(fila) for fila in entregas]


def eliminar_reserva(reserva_id):
    if _supabase_activo():
        try:
            resultado = supabase_rpc("cancelar_reserva_compra_rpc", {"p_reserva_id": reserva_id}) or {}
            return bool(resultado.get("ok"))
        except Exception as exc:
            _marcar_supabase_caido(f"Error al cancelar reserva remota: {exc}")
            return False
    conn = get_db_connection()
    conn.isolation_level = None
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT producto_id, cantidad FROM reservas WHERE id = ? AND estado = 'Reservado'",
            (reserva_id,),
        )
        reserva = cursor.fetchone()
        if not reserva:
            cursor.execute("ROLLBACK")
            return False
        cursor.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (reserva[1], reserva[0]))
        cursor.execute("UPDATE reservas SET estado = 'Cancelado' WHERE id = ? AND estado = 'Reservado'", (reserva_id,))
        cursor.execute("COMMIT")
        return True
    except Exception:
        cursor.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def obtener_estado_disponibilidad_producto(producto_id):
    """Devuelve un estado anónimo para la pantalla que espera disponibilidad."""
    if _supabase_activo():
        resultado = supabase_rpc(
            "obtener_estado_disponibilidad_producto_rpc",
            {"p_producto_id": producto_id},
        ) or {}
        return resultado.get("estado", "no_disponible")
    cancelar_reservas_vencidas()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock FROM productos WHERE id = ?", (producto_id,))
    producto = cursor.fetchone()
    if not producto:
        conn.close()
        return "no_disponible"
    if int(producto[0] or 0) > 0:
        conn.close()
        return "disponible"
    cursor.execute(
        "SELECT 1 FROM reservas WHERE producto_id = ? AND estado = 'Reservado' "
        "AND fecha_expiracion > ? LIMIT 1",
        (producto_id, str(datetime.now())),
    )
    en_proceso = cursor.fetchone() is not None
    conn.close()
    return "en_proceso" if en_proceso else "no_disponible"


def reserva_pago_vigente(reserva_id):
    """Confirma que una reserva sigue en proceso antes de capturar dinero."""
    if _supabase_activo():
        reserva = _supabase_unico(
            "reservas",
            f"?select=estado,fecha_expiracion&id=eq.{reserva_id}&limit=1",
        )
        if not reserva or reserva.get("estado") != "Reservado":
            return False
        vencimiento = reserva.get("fecha_expiracion")
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT estado, fecha_expiracion FROM reservas WHERE id = ?", (reserva_id,))
        reserva = cursor.fetchone()
        conn.close()
        if not reserva or reserva[0] != "Reservado":
            return False
        vencimiento = reserva[1]
    if not vencimiento:
        return False
    fecha = datetime.fromisoformat(str(vencimiento).replace("Z", "+00:00"))
    ahora = datetime.now(fecha.tzinfo) if fecha.tzinfo else datetime.now()
    return fecha > ahora


def canjear_codigo_retiro(tienda_id, usuario_id, codigo):
    """Valida código y propietario, y marca la compra entregada de forma atómica."""
    codigo = str(codigo or "").strip().upper()
    if not codigo:
        return False, "Ingresa el código que muestra el cliente."
    if _supabase_activo():
        resultado = supabase_rpc(
            "canjear_codigo_retiro_rpc",
            {"p_tienda_id": tienda_id, "p_codigo": codigo},
        ) or {}
        return bool(resultado.get("ok")), resultado.get("message", "No se pudo validar el código.")
    conn = get_db_connection()
    conn.isolation_level = None
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT usuario_id FROM tiendas WHERE id = ?", (tienda_id,))
        propietario = cursor.fetchone()
        if not propietario or int(propietario[0]) != int(usuario_id):
            cursor.execute("ROLLBACK")
            return False, "No se pudo validar el código para esta tienda."
        cursor.execute(
            "SELECT r.id, r.estado, p.nombre FROM reservas r JOIN productos p ON p.id = r.producto_id "
            "WHERE r.tienda_id = ? AND r.codigo_retiro = ?",
            (tienda_id, codigo),
        )
        reserva = cursor.fetchone()
        if not reserva:
            cursor.execute("ROLLBACK")
            return False, "El código no corresponde a una compra de esta tienda o ya fue utilizado."
        reserva_id, estado, producto_nombre = reserva
        if estado != "Listo para entregar":
            cursor.execute("ROLLBACK")
            return False, "El pedido debe estar listo para entregar antes de canjear el código."
        ahora = datetime.now().isoformat()
        cursor.execute(
            "UPDATE reservas SET estado = 'Entregado', fecha_entrega = ?, codigo_retiro = NULL, codigo_retiro_usado_en = ? "
            "WHERE id = ? AND tienda_id = ? AND codigo_retiro = ? AND estado = 'Listo para entregar'",
            (ahora, ahora, reserva_id, tienda_id, codigo),
        )
        if cursor.rowcount != 1:
            cursor.execute("ROLLBACK")
            return False, "El código ya fue utilizado o el pedido cambió de estado."
        cursor.execute("COMMIT")
        return True, f"Compra pagada: {producto_nombre}. Entrega registrada."
    except Exception:
        cursor.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def confirmar_reserva(reserva_id):
    """Deshabilitado: una compra se marca pagada solo al completar el checkout."""
    return False


def marcar_como_entregada(reserva_id):
    """Deshabilitado: registrar entrega requiere el código de retiro del cliente."""
    return False


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
