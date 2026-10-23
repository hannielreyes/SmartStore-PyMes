import asyncio
import os

import flet as ft

import database as db
from database.models import ProductoReserva, Tienda
from utils import boton_glossy, configurar_retroceso, imagen_disponible, mostrar_snackbar
from views.carrito import iniciar_pago_reserva


def reservar_view(page: ft.Page, usuario, producto_id, producto_nombre, producto_stock, go_back):
    configurar_retroceso(page, go_back)
    page.clean()
    page.bgcolor = "#FFFFFF"
    producto_fila = db.obtener_producto_por_id(producto_id)
    producto = ProductoReserva.desde_fila(producto_fila) if producto_fila else None
    precio = float(producto.precio_cordobas or 0) if producto else 0.0
    tienda_id = producto.tienda_id if producto else None
    tienda_fila = db.obtener_tienda_por_id(tienda_id) if tienda_id else None
    tienda = Tienda.desde_fila(tienda_fila) if tienda_fila else None
    nombre_tienda = tienda.nombre if tienda else "Tienda no identificada"
    direccion = tienda.direccion if tienda else "No indicada"
    marca = producto.marca or "No indicada" if producto else "No indicada"
    talla = producto.talla or "No indicada" if producto else "No indicada"
    logo = ft.Container(width=64, height=64, bgcolor="#F3F3F3", border_radius=12)
    if tienda and tienda.imagen and imagen_disponible(tienda.imagen):
        logo = ft.Image(src=tienda.imagen, width=64, height=64, fit="cover", border_radius=12)

    cantidad = ft.TextField(label="Cantidad", value="1", width=300, keyboard_type=ft.KeyboardType.NUMBER)
    total = ft.Text(f"Total: C${precio:.2f}", size=16, color="#E61A1A", weight=ft.FontWeight.BOLD)

    def actualizar(_):
        try:
            cant = int(cantidad.value)
            total.value = f"Total: C${precio * cant:.2f}" if 0 < cant <= producto_stock else "Cantidad no válida"
            page.update()
        except (TypeError, ValueError):
            pass

    cantidad.on_change = actualizar

    async def observar_disponibilidad():
        anterior = "en_proceso"
        for _ in range(150):
            await asyncio.sleep(4)
            estado = await asyncio.to_thread(db.obtener_estado_disponibilidad_producto, producto_id)
            if estado != anterior:
                anterior = estado
                if estado == "disponible":
                    mostrar_snackbar(page, "El producto volvió a estar disponible.", color="#1B5E20", duracion=6000)
                    return
                if estado == "no_disponible":
                    mostrar_snackbar(page, "El producto ya no está disponible.", color="#8A4B08", duracion=6000)
                    return

    def mostrar_espera(mensaje):
        en_proceso = "completando su pago" in mensaje.lower()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Producto en proceso" if en_proceso else "Producto no disponible"),
            content=ft.Text(mensaje),
            actions=[ft.TextButton("Entendido", on_click=lambda e: (setattr(dlg, "open", False), page.update(), go_back()))],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()
        if en_proceso:
            page.run_task(observar_disponibilidad)

    def confirmar(_):
        try:
            cant = int(cantidad.value)
        except (TypeError, ValueError):
            mostrar_snackbar(page, "Ingresa una cantidad válida.", color="#B3261E")
            return
        if not producto or not tienda_id or not 1 <= cant <= producto_stock:
            mostrar_snackbar(page, "La cantidad indicada no está disponible.", color="#B3261E")
            return
        creada, mensaje, reserva_id = db.agregar_reserva(usuario["id"], producto_id, cant, tienda_id)
        if not creada:
            mostrar_espera(mensaje)
            return
        iniciar_pago_reserva(page, reserva_id, tienda_id, precio * cant, go_back)

    contenido = ft.Column(
        [
            ft.Container(height=24),
            ft.Text("Reservar y pagar", size=28, weight=ft.FontWeight.BOLD, color="#0A2540"),
            ft.Text(f"Producto: {producto_nombre}", size=18, weight=ft.FontWeight.BOLD),
            ft.Text(f"Tienda: {nombre_tienda}"),
            ft.Text(f"Marca: {marca} | Talla: {talla}"),
            ft.Text(f"Dirección: {direccion}"),
            logo,
            ft.Text(f"Precio: C${precio:.2f}  ·  Disponibles: {producto_stock}"),
            cantidad,
            total,
            boton_glossy("Continuar al pago", on_click=confirmar, color="#EFA520", text_color="#0A2540", width=220),
            boton_glossy("↩️ Volver a buscar", on_click=lambda e: go_back(), color="#E7ECF3", text_color="#0A2540", width=220),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=14,
        scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
    )
    page.add(ft.Stack([ft.Container(expand=True, image=ft.DecorationImage(src="fondopro.png", fit="cover")), ft.SafeArea(ft.Container(contenido, padding=20))], expand=True))
