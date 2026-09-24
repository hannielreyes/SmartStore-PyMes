import flet as ft
from utils import mostrar_snackbar, configurar_retroceso, imagen_disponible, boton_glossy
import database as db
from datetime import datetime, timedelta
import os

def reservar_view(page: ft.Page, usuario, producto_id, producto_nombre, producto_stock, go_back):
    # PANTALLA: formulario de reserva de un producto y confirmación del pedido.
    # Pantalla de confirmación de reserva y cálculo del total a pagar.
    configurar_retroceso(page, go_back)
    page.clean()
    page.bgcolor = "white"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondopro_Copy.png", fit="cover"),
    )

    # Obtener el precio del producto
    productos = [db.obtener_producto_por_id(producto_id)]
    precio_c = 0.0
    tienda_id = None
    marca = "No indicada"
    talla = "No indicada"
    direccion = "No indicada"
    nombre_tienda = "Tienda no identificada"
    logo_tienda = None
    for p in productos:
        if p and p[0] == producto_id:
            precio_c = float(p[4])  # precio_cordobas
            tienda_id = p[7]  # tienda_id
            marca = p[2] or marca
            talla = p[3] or talla
            break
    tienda = db.obtener_tienda_por_id(tienda_id) if tienda_id else None
    if tienda:
        nombre_tienda = tienda[1] or nombre_tienda
        direccion = tienda[5] or direccion
        logo_tienda = tienda[7] if len(tienda) > 7 else None

    logo_control = ft.Container(width=64, height=64, bgcolor="#F3F3F3", border_radius=12)
    if logo_tienda:
        logo_path = logo_tienda if os.path.isabs(logo_tienda) else os.path.join(os.getcwd(), logo_tienda)
        if imagen_disponible(logo_tienda):
            logo_control = ft.Container(
                content=ft.Image(src=logo_tienda, width=64, height=64, fit="cover"),
                width=64,
                height=64,
                border_radius=12,
                bgcolor="#F3F3F3",
            )

    # Campo de cantidad y texto de total; ambos se actualizan mientras el cliente escribe.
    cantidad_field = ft.TextField(
        label="¿Cuántos deseas reservar?",
        value="1",
        width=300,
        label_style=ft.TextStyle(color="#0A2540", weight=ft.FontWeight.BOLD),
        text_style=ft.TextStyle(color="#0A2540", weight=ft.FontWeight.BOLD),
        border_color="#0A2540",
        focused_border_color="#0A2540",
    )
    total_text = ft.Text(f"Total: C${precio_c:.2f} por unidad", size=16, color="#E61A1A", weight=ft.FontWeight.BOLD)

    def actualizar_total(e):
        try:
            cant = int(cantidad_field.value)
            if cant > 0 and cant <= producto_stock:
                total_text.value = f"Total: C${precio_c * cant:.2f} por {cant} unidad(es)"
            else:
                total_text.value = f"Total: C${precio_c:.2f} por unidad"
            page.update()
        except:
            pass

    cantidad_field.on_change = actualizar_total

    def confirmar_reserva(e):
        try:
            cant = int(cantidad_field.value)
            if not (1 <= cant <= producto_stock):
                mostrar_snackbar(page, ft.Text(f"⚠️ Indica una cantidad válida entre 1 y {producto_stock} unidades disponibles 😊", color="red"))
                return

            if tienda_id is None:
                mostrar_snackbar(page, "❌ Error: Producto sin tienda asociada", color="red")
                return

            # Guardar la reserva
            creada, mensaje = db.agregar_reserva(usuario['id'], producto_id, cant, tienda_id)
            if not creada:
                mostrar_snackbar(page, ft.Text(f"❌ {mensaje}", color="red"))
                return

            # Calcular total
            total = precio_c * cant

            # Mostrar el diálogo con el mensaje estilizado
            mostrar_mensaje_exito(page, producto_nombre, nombre_tienda, cant, total, go_back)

        except Exception as error:
            mostrar_snackbar(page, ft.Text(f"❌ Error: {str(error)}", color="red"))

    def mostrar_mensaje_exito(page, producto, tienda_nombre, cantidad, total, go_back):
        """Muestra un diálogo con el mensaje de éxito estilizado."""
        
        def cerrar_dialogo(e):
            dlg.open = False
            page.update()
            go_back()  # Volver a la búsqueda

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "🎉 ¡Genial, tu reserva está casi lista!",
                size=20,
                weight=ft.FontWeight.BOLD,
                color="#0A2540",
            ),
            content=ft.Column(
                [
                    ft.Text(
                        f"Has reservado {cantidad} x {producto} por un total de C${total:.2f}",
                        size=16,
                        color="#2E7D32",
                    ),
                    ft.Text(
                        f"🏪 Tienda: {tienda_nombre}",
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        color="#040D4A",
                    ),
                    ft.Divider(height=10),
                    ft.Text(
                        "📌 Recuerda estos pasos para que el producto sea tuyo:",
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        color="#E65100",
                    ),
                    ft.Text(
                        "1️⃣ Tienes 24 horas para completar el pago.",
                        size=14,
                        color="#C62828",
                    ),
                    ft.Text(
                        "2️⃣ Si no confirmas en ese tiempo, tu reserva se cancelará automáticamente.",
                        size=14,
                        color="#C62828",
                    ),
                    ft.Text(
                        "3️⃣ Para pagar y hacer tuya la reserva, ve a 'Reservas y Carrito'.",
                        size=14,
                        color="#6A1B9A",
                    ),
                    ft.Divider(height=10),
                    ft.Text(
                        "🎉 ¡Gracias por confiar en nosotros!",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color="#2E7D32",
                    ),
                    ft.Text(
                        "Estamos felices de que formes parte de nuestra comunidad.",
                        size=13,
                        color="#4E342E",
                        italic=True,
                    ),
                ],
                spacing=8,
                tight=True,
            ),
            actions=[
                ft.ElevatedButton(
                    "✅ Entendido",
                    on_click=cerrar_dialogo,
                    bgcolor="#0A2540",
                    color="white",
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    cantidad_field.on_submit = confirmar_reserva

    # Formulario visual de reserva: tienda, producto, cantidad y botones finales.
    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("Realizar Reserva", size=28, weight=ft.FontWeight.BOLD, color="#0A2540"),
                ft.Text(f"Producto: {producto_nombre}", size=18, weight=ft.FontWeight.BOLD, color="#0A2540"),
                ft.Text(
                    f"🏪 Reservarás en la tienda: {nombre_tienda}",
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color="#0A2540",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(f"Marca: {marca} | Talla: {talla}", size=14, color="#0A2540", weight=ft.FontWeight.BOLD),
                ft.Text(f"Dirección de la tienda: {direccion}", size=14, color="#0A2540", weight=ft.FontWeight.BOLD),
                logo_control,
                ft.Text("Logo de la tienda", size=12, color="#0A2540", weight=ft.FontWeight.BOLD),
                ft.Text(f"Precio: C${precio_c:.2f}", size=16, color="#0A2540", weight=ft.FontWeight.BOLD),
                ft.Text(f"Stock disponible: {producto_stock}", size=14, color="#0A2540", weight=ft.FontWeight.BOLD),
                cantidad_field,
                total_text,
                boton_glossy("Confirmar Reserva", on_click=confirmar_reserva, color="#EFA520", text_color="#0A2540", width=220),
                boton_glossy("↩️ Volver a Buscar", on_click=lambda e: go_back(), color="#E7ECF3", text_color="#0A2540", width=220),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=20,
        border_radius=22,
        bgcolor=None,
    )

    page.add(
        ft.Stack(
            [
                fondo, 
                ft.SafeArea(content)
            ], 
            expand=True
        )
    )