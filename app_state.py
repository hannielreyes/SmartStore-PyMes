"""Estado de datos de la sesión actual y precarga desde Supabase."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import database as db
from database.models import AlertaInventario
from database.conexion import SupabaseNoDisponible


def cargar_contexto_usuario(usuario_id):
    """Carga el contexto inicial sin bloquear el hilo de interfaz de Flet."""
    tiendas = db.obtener_tiendas_usuario(usuario_id)
    tienda_ids = [tienda.id for tienda in tiendas]

    def cargar_productos():
        return db.obtener_productos_usuario(usuario_id)

    def cargar_paypal():
        try:
            return db.obtener_paypal_email(usuario_id)
        except SupabaseNoDisponible:
            return None

    def cargar_reservas():
        reservas = []
        for tienda_id in tienda_ids:
            try:
                reservas.extend(db.obtener_reservas_por_tienda(tienda_id))
            except SupabaseNoDisponible:
                return []
        return reservas

    def cargar_reservas_usuario():
        try:
            return db.obtener_reservas_usuario(usuario_id)
        except SupabaseNoDisponible:
            return []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futuros = {
            "productos": executor.submit(cargar_productos),
            "paypal": executor.submit(cargar_paypal),
            "reservas": executor.submit(cargar_reservas),
            "reservas_usuario": executor.submit(cargar_reservas_usuario),
        }
        productos = futuros["productos"].result()
        paypal = futuros["paypal"].result()
        reservas = futuros["reservas"].result()
        reservas_usuario = futuros["reservas_usuario"].result()

    alertas = [
        AlertaInventario(producto.id, producto.nombre, int(producto.stock or 0))
        for producto in productos
        if int(producto.stock or 0) == 1
    ][:20]
    catalogo_completo = (
        not db._supabase_activo()
        or (
            db.tiene_catalogo_conocido(usuario_id, "tiendas")
            and db.tiene_catalogo_conocido(usuario_id, "productos")
        )
    )

    return {
        "usuario_id": usuario_id,
        "tiendas": tiendas,
        "tienda_actual": tiendas[0] if tiendas else None,
        "productos": productos,
        "stock_total": (
            sum(int(producto.stock or 0) for producto in productos)
            if catalogo_completo
            else None
        ),
        "catalogo_completo": catalogo_completo,
        "alertas_inventario": alertas,
        "reservas": reservas,
        "reservas_usuario": reservas_usuario,
        "paypal": paypal,
        "sincronizacion_pendiente": db.contar_cambios_pendientes(usuario_id),
        "conflictos_sincronizacion": db.contar_conflictos_offline(usuario_id),
        "actualizado_en": datetime.now(),
    }
