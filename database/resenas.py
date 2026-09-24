"""Consultas de calificación y resumen de reseñas de productos."""

from .conexion import (
    _supabase_activo,
    _supabase_lista,
    get_db_connection,
)


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