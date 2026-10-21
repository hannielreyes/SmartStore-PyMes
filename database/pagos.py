# Módulo generado automáticamente a partir de `legado.py`.
# No editar manualmente; los cambios deben hacerse en `legado.py` y volver a ejecutar este script.

from .conexion import (
    get_db_connection,
    _supabase_activo,
    _supabase_unico,
    _supabase_insertar,
    _supabase_actualizar,
    _supabase_borrar,
    _marcar_supabase_caido,
)
from supabase_config import supabase_rpc
import secrets

_ALFABETO_CODIGO_RETIRO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generar_codigo_retiro():
    return "".join(secrets.choice(_ALFABETO_CODIGO_RETIRO) for _ in range(12))
import bcrypt, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import quote


def procesar_pago_reserva(reserva_id, monto, tienda_id):
    codigo_retiro = _generar_codigo_retiro()
    if _supabase_activo():
        try:
            resultado = supabase_rpc(
                "procesar_pago_reserva_rpc",
                {"p_reserva_id": reserva_id, "p_monto": monto, "p_tienda_id": tienda_id, "p_codigo_retiro": codigo_retiro},
            ) or {}
            return bool(resultado.get("ok")), resultado.get("message", "No se pudo procesar el pago"), codigo_retiro if resultado.get("ok") else None
        except Exception as exc:
            _marcar_supabase_caido(f"Error al procesar pago remoto: {exc}")
            return False, "No se pudo confirmar el pago con la base de datos.", None
    conn = get_db_connection()
    # Desactivar manejo implícito de transacciones para control manual
    conn.isolation_level = None
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")
        
        # 1. Obtenemos estado, producto_id y cantidad asociada a la reserva
        cursor.execute("SELECT estado, tienda_id, fecha_expiracion, producto_id, cantidad FROM reservas WHERE id = ?", (reserva_id,))
        res = cursor.fetchone()
        if not res:
            cursor.execute("ROLLBACK;")
            conn.close()
            print(f"⚠️ procesar_pago_reserva: Reserva #{reserva_id} no encontrada")
            return False, "Reserva no encontrada", None
        
        estado, tienda_reserva_id, fecha_expiracion, producto_id, cantidad = res
        if estado != "Reservado":
            cursor.execute("ROLLBACK;")
            conn.close()
            print(f"⚠️ procesar_pago_reserva: Reserva #{reserva_id} ya está en estado: {estado}")
            return False, f"La reserva ya está en estado: {estado}", None

        if fecha_expiracion and datetime.fromisoformat(str(fecha_expiracion)) <= datetime.now():
            cursor.execute("SELECT producto_id, cantidad FROM reservas WHERE id = ?", (reserva_id,))
            producto_id, cantidad = cursor.fetchone()
            cursor.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, producto_id))
            cursor.execute("UPDATE reservas SET estado = 'Vencido' WHERE id = ? AND estado = 'Reservado'", (reserva_id,))
            cursor.execute("COMMIT;")
            conn.close()
            return False, "El tiempo para completar el pago terminó; el producto volvió a estar disponible.", None

        if tienda_reserva_id != tienda_id:
            cursor.execute("ROLLBACK;")
            conn.close()
            return False, "La tienda del pago no coincide con la reserva", None

        cursor.execute(
            "SELECT precio_cordobas FROM productos WHERE id = ? AND tienda_id = ?",
            (producto_id, tienda_id),
        )
        producto = cursor.fetchone()
        monto_real = float(producto[0] or 0) * int(cantidad) if producto else 0
        if producto is None or abs(float(monto) - monto_real) > 0.01:
            cursor.execute("ROLLBACK;")
            conn.close()
            return False, "El total de la compra no coincide con el precio del producto.", None

        # El stock ya fue apartado al confirmar la reserva.
        cursor.execute("UPDATE reservas SET estado = 'Pagado', codigo_retiro = ? WHERE id = ?", (codigo_retiro, reserva_id))
        cursor.execute("UPDATE tiendas SET saldo = saldo + ? WHERE id = ?", (monto_real, tienda_id))

        cursor.execute("COMMIT;")
        conn.close()
        return True, "Pago procesado y saldo acreditado a la tienda", codigo_retiro

    except Exception as e:
        cursor.execute("ROLLBACK;")
        conn.close()
        print(f"❌ Error en procesar_pago_reserva: {e}")
        return False, str(e), None
