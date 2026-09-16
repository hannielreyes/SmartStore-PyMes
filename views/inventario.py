
import flet as ft
import database as db
import os
from utils import configurar_retroceso, mostrar_snackbar, imagen_disponible

def _show_full_image(page: ft.Page, src: str, src_2: str | None = None):
    # PANTALLA AUXILIAR: muestra una imagen ampliada y permite cambiar o cerrar.
    imagenes = [imagen for imagen in (src, src_2) if imagen]
    indice = 0
    previous_controls = list(page.controls)
    imagen_control = ft.Image(src=imagenes[0], fit="contain", expand=True)

    def siguiente(e):
        nonlocal indice
        indice = (indice + 1) % len(imagenes)
        imagen_control.src = imagenes[indice]
        page.update()

    def cerrar(e):
        page.clean()
        page.bgcolor = "white"
        for control in previous_controls:
            page.add(control)
        page.update()

    ancho_disponible = max((page.width or 360) - 32, 260)
    ancho_imagen = min(ancho_disponible, 600)
    ancho_botones = min(ancho_disponible, 420)

    # BOTONES: navegación entre imágenes y cierre de la vista ampliada.
    botones = ft.Column(
        [
            ft.ElevatedButton(
                "Ver siguiente imagen →",
                on_click=siguiente,
                visible=len(imagenes) > 1,
                bgcolor="#040D4A",
                color="white",
                height=44,
                width=ancho_botones,
            ),
            ft.ElevatedButton(
                "Cerrar",
                on_click=cerrar,
                bgcolor="#EFA520",
                color="#040D4A",
                height=44,
                width=ancho_botones,
            ),
        ],
        spacing=12,
        width=ancho_botones,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    vista_imagen = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondopro.png", fit="cover"),
        padding=20,
        content=ft.Column(
            [
                ft.Container(
                    content=ft.InteractiveViewer(
                        content=imagen_control,
                        min_scale=1,
                        max_scale=4,
                        scale_enabled=True,
                        pan_enabled=True,
                    ),
                    width=ancho_imagen,
                    height=560,
                    border_radius=24,
                    bgcolor="transparent",
                    padding=0,
                ),
                ft.Container(
                    content=botones,
                    padding=12,
                    border_radius=24,
                    bgcolor="rgba(255,255,255,0.18)",
                    alignment=ft.Alignment(0, 0),
                    width=min(ancho_disponible, 420),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
    )

    page.clean()
    page.bgcolor = "white"
    page.add(vista_imagen)
    page.update()

def inventario_view(page: ft.Page, usuario, go_back):
    # PANTALLA: consulta, edición, eliminación y vista ampliada de productos.
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "white"
    ancho_tarjeta = min(max((page.width or 360) - 96, 250), 440)

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )
    ancho_contenido_tarjeta = max(ancho_tarjeta - 84, 180)

    # Lista desplazable de productos registrados en la tienda del usuario.
    lista = ft.Column(
        spacing=10,
        scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def mostrar_edicion(id_producto, producto):
        # DIÁLOGO: formulario para editar los datos y existencias del producto.
        nombre_input = ft.TextField(label="Nombre del producto", value=str(producto[1] or ""), width=280)
        marca_input = ft.TextField(label="Marca", value=str(producto[2] or ""), width=280)
        talla_input = ft.TextField(label="Talla", value=str(producto[3] or ""), width=280)
        precio_cordobas_input = ft.TextField(label="Precio en C$", value=str(producto[4] or ""), width=280)
        precio_dolares_input = ft.TextField(label="Precio en dólares", value=str(producto[5] or ""), width=280)
        stock_input = ft.TextField(
            label="Cantidad disponible",
            value=str(producto[6] or 0),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=280,
        )
        mensaje = ft.Text("", size=12, color="red")

        def guardar(e):
            # ACCIÓN: valida y guarda los cambios del producto.
            nombre = nombre_input.value.strip()
            if not nombre:
                mensaje.value = "⚠️ El nombre es obligatorio."
                page.update()
                return
            try:
                precio_cordobas = float(precio_cordobas_input.value.strip())
                precio_dolares = float(precio_dolares_input.value.strip())
                stock = int(stock_input.value.strip())
            except (AttributeError, ValueError):
                mensaje.value = "⚠️ Revisa precios y cantidad."
                page.update()
                return
            if precio_cordobas < 0 or precio_dolares < 0 or stock < 0:
                mensaje.value = "⚠️ Los valores no pueden ser negativos."
                page.update()
                return

            if not db.actualizar_producto(
                id_producto,
                usuario["id"],
                nombre,
                marca_input.value.strip(),
                talla_input.value.strip(),
                precio_cordobas,
                precio_dolares,
                stock,
            ):
                mensaje.value = "❌ No se pudo actualizar el producto."
                page.update()
                return

            dialogo.open = False
            page.update()
            cargar()
            mostrar_snackbar(page, "✅ Producto actualizado correctamente.", color="green")

        def cancelar(e):
            # ACCIÓN: cierra la edición sin modificar el producto.
            dialogo.open = False
            page.update()

        # Diálogo de edición: campos, validaciones y botón para guardar cambios.
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("✏️ Editar producto"),
            content=ft.Column(
                [nombre_input, marca_input, talla_input, precio_cordobas_input, precio_dolares_input, stock_input, mensaje],
                tight=True,
                scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
            ),
            actions=[
                ft.TextButton("↩️ Cancelar", on_click=cancelar),
                ft.ElevatedButton("💾 Guardar", on_click=guardar, bgcolor="#040D4A", color="white"),
            ],
        )
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    def cargar():
        # CARGA: reconstruye la lista de productos del inventario.
        lista.controls.clear()
        productos = db.obtener_productos_usuario(usuario["id"])

        if not productos:
            lista.controls.append(
                ft.Text("Aún no tienes productos registrados en tu inventario 😊", color="#555555", size=16, text_align=ft.TextAlign.CENTER)
            )
            page.update()
            return

        for p in productos:
            id_p = p[0]
            nombre = p[1]
            marca = p[2]
            talla = p[3]
            precio_c = p[4]
            precio_d = p[5]
            stock = p[6]
            tienda_id = p[7]
            color_stock = "#EFA520" if stock > 5 else "red"

            def hacer_confirmar(id_producto, nombre_producto, stock_producto):
                def confirmar_eliminacion(e):
                    cantidad_input = ft.TextField(
                        label="Cantidad a eliminar",
                        hint_text=f"Máximo: {stock_producto}",
                        keyboard_type=ft.KeyboardType.NUMBER,
                        width=280,
                    )

                    def eliminar(e):
                        try:
                            cantidad = int(cantidad_input.value.strip())
                        except (AttributeError, ValueError):
                            mensaje.value = "⚠️ Escribe una cantidad válida."
                            page.update()
                            return

                        if cantidad <= 0 or cantidad > stock_producto:
                            mensaje.value = f"⚠️ La cantidad debe estar entre 1 y {stock_producto}."
                            page.update()
                            return

                        if not db.reducir_stock_producto(id_producto, cantidad, usuario["id"]):
                            mensaje.value = "❌ No se pudo actualizar el inventario."
                            page.update()
                            return

                        dlg.open = False
                        page.update()
                        mensaje_confirmacion = (
                            f"✅ Se eliminaron {cantidad} unidades de '{nombre_producto}'."
                        )
                        cargar()
                        mostrar_snackbar(page, mensaje_confirmacion, color="green")

                    def cancelar(e):
                        dlg.open = False
                        page.update()

                    dlg = ft.AlertDialog(
                        modal=True,
                        title=ft.Text("🗑 Eliminar unidades"),
                        content=ft.Column(
                            [
                                ft.Text(f"Producto: {nombre_producto}"),
                                ft.Text(f"Unidades disponibles: {stock_producto}"),
                                cantidad_input,
                                (mensaje := ft.Text("", size=12, color="red")),
                            ],
                            tight=True,
                            spacing=8,
                        ),
                        actions=[
                            ft.TextButton("↩️ Cancelar", on_click=cancelar),
                            ft.ElevatedButton(
                                "Eliminar",
                                on_click=eliminar,
                                bgcolor=ft.Colors.RED_400,
                                color="white",
                            ),
                        ],
                    )
                    page.overlay.append(dlg)
                    dlg.open = True
                    page.update()
                return confirmar_eliminacion

            btn_eliminar = ft.ElevatedButton(
                "🗑 Eliminar",
                on_click=hacer_confirmar(id_p, nombre, stock),
                bgcolor=ft.Colors.RED_400,
                color="white",
                height=40,
                width=118,
            )
            btn_editar = ft.ElevatedButton(
                "✏️ Editar",
                on_click=lambda e, id_producto=id_p, producto=p: mostrar_edicion(id_producto, producto),
                bgcolor="#168AAD",
                color="white",
                height=40,
                width=104,
            )
            acciones = ft.Column(
                [btn_editar, btn_eliminar],
                spacing=10,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

            # Prepare thumbnails with a clean, centered gallery layout
            imagen_producto = p[8] if len(p) > 8 else None
            imagen_producto_2 = p[9] if len(p) > 9 else None

            def _crear_miniatura(src, ancho, alto):
                if not src:
                    return ft.Container(
                        width=ancho,
                        height=alto,
                        bgcolor="#EAEAF5",
                        border_radius=18,
                        alignment=ft.Alignment(0, 0),
                    )

                if imagen_disponible(src):
                    return ft.Container(
                        content=ft.Image(src=src, width=ancho, height=alto, fit="cover"),
                        width=ancho,
                        height=alto,
                        border_radius=18,
                        bgcolor="#F3F3F3",
                        padding=0,
                        alignment=ft.Alignment(0, 0),
                    )

                return ft.Container(
                    width=ancho,
                    height=alto,
                    bgcolor="#EAEAF5",
                    border_radius=18,
                    alignment=ft.Alignment(0, 0),
                )

            imagen_principal = _crear_miniatura(imagen_producto, 94, 94)
            imagen_secundaria = _crear_miniatura(imagen_producto_2, 58, 58)

            thumb_clickable = ft.Container(
                content=imagen_principal,
                on_click=(lambda e, s=imagen_producto, s2=imagen_producto_2: _show_full_image(page, s, s2)) if imagen_producto else None,
                border_radius=18,
                alignment=ft.Alignment(0, 0),
            )

            segunda_imagen_clickable = ft.Container(
                content=imagen_secundaria,
                on_click=(lambda e, s=imagen_producto_2, s2=imagen_producto: _show_full_image(page, s, s2)) if imagen_producto_2 else None,
                border_radius=18,
                alignment=ft.Alignment(0, 0),
            )

            galeria = ft.Row(
                [thumb_clickable, segunda_imagen_clickable] if imagen_producto_2 else [thumb_clickable],
                spacing=12,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            info_ancho = min(max((page.width or 360) - 220, 170), max(ancho_tarjeta - 120, 170))
            info_column = ft.Column(
                [
                    ft.Text(
                        nombre,
                        weight=ft.FontWeight.BOLD,
                        size=17,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        f"Marca: {marca or '-'}    Talla: {talla or '-'}",
                        size=13,
                        color="#555555",
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        f"C${precio_c:.2f} / ${precio_d:.2f}    Stock: {stock}",
                        size=13,
                        weight=ft.FontWeight.BOLD if stock <= 5 else ft.FontWeight.NORMAL,
                        color=color_stock if stock <= 5 else "#333333",
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    acciones,
                ],
                spacing=6,
                width=info_ancho,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

            card_content = ft.Column(
                [galeria, info_column],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )

            lista.controls.append(
                ft.Container(
                    content=card_content,
                    bgcolor=ft.Colors.WHITE,
                    border_radius=18,
                    padding=12,
                    width=ancho_tarjeta,
                    alignment=ft.Alignment(0, 0),
                )
            )
        page.update()

    stock_total = db.obtener_stock_total_usuario(usuario["id"])
    total_productos = len(db.obtener_productos_usuario(usuario["id"]))
    ancho_boton_volver = min(max((page.width or 360) - 40, 180), 260)

    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("📦 Estado del Inventario", size=24, weight=ft.FontWeight.BOLD, color="#040D4A"),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"Total de productos: {total_productos}", size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Estado del inventario", size=14, color="#555555"),
                            ft.Text(f"+ {stock_total}", size=40, weight=ft.FontWeight.BOLD, color="#EFA520"),
                            ft.Text("📋 Lista de productos", size=14, weight=ft.FontWeight.BOLD, color="#040D4A"),
                        ],
                        spacing=5,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=ft.Colors.WHITE,
                    border_radius=15,
                    padding=15,
                    width=ancho_tarjeta,
                ),
                lista,
                ft.ElevatedButton(
                    "↩️ Volver al Menu",
                    on_click=lambda e: go_back(usuario),
                    width=ancho_boton_volver,
                    bgcolor="#040D4A",
                    color="white",
                    height=44,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=12,
    )

    cargar()
    page.add(
        ft.Stack(
            [fondo, ft.SafeArea(content)],
            expand=True
        )
    )