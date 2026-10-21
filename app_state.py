"""Estado de datos de la sesión actual y precarga desde Supabase."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import database as db
from database.models import AlertaInventario


def cargar_contexto_usuario(usuario_id):
    """Carga el contexto inicial sin bloquear el hilo de interfaz de Flet."""
    tiendas = db.obtener_tiendas_usuario(usuario_id)
    tienda_ids = [tienda.id for tienda in tiendas]

    def cargar_productos():
        return db.obtener_productos_usuario(usuario_id)

    def cargar_paypal():
        return db.obtener_paypal_email(usuario_id)

    def cargar_reservas():
        reservas = []
        for tienda_id in tienda_ids:
            try:
                reservas.extend(db.obtener_reservas_por_tienda(tienda_id))
            except Exception:
                continue
        return reservas

    def cargar_reservas_usuario():
        return db.obtener_reservas_usuario(usuario_id)

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

    return {
        "usuario_id": usuario_id,
        "tiendas": tiendas,
        "tienda_actual": tiendas[0] if tiendas else None,
        "productos": productos,
        "stock_total": sum(int(producto.stock or 0) for producto in productos),
        "alertas_inventario": alertas,
        "reservas": reservas,
        "reservas_usuario": reservas_usuario,
        "paypal": paypal,
        "actualizado_en": datetime.now(),
    }
