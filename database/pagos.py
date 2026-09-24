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
import bcrypt, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import quote


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