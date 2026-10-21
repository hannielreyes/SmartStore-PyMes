"""Consultas de ventas y datos agregados para estadísticas."""

from .models import VentaDiaria
from .conexion import (
    _supabase_activo,
    _supabase_lista,
    get_db_connection,
)


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
        return [VentaDiaria(fecha, total) for fecha, total in ventas.items()]

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
    return [VentaDiaria.desde_fila(fila) for fila in ventas]