import flet as ft
import database as db
from views.reservar import reservar_view
from views.top_productos import top_productos_view
import os
from utils import (
    mostrar_snackbar,
    abrir_whatsapp,
    configurar_retroceso,
    imagen_disponible,
)


def _normalizar_texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _show_full_image(page: ft.Page, src: str, src_2: str | None = None):
    """PANTALLA AUXILIAR: muestra imágenes del producto con zoom."""
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

    # BOTONES: permite ver la siguiente imagen o cerrar el visor.
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
                width=ancho_botones
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

def buscar_producto_view(page: ft.Page, usuario, go_back):
    # PANTALLA: búsqueda global, detalles de producto y flujo de reserva.
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "white"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )

    buscar_entry = ft.TextField(label="Buscar productos en toda la base de datos", width=300)
    resultados = ft.Column(
        spacing=10,
        scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        width=360,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # El buscador es un escaparate global; el inventario privado se muestra en Inventario.
    try:
        productos_aleatorios = db.obtener_productos_aleatorios(limit=5)
    except RuntimeError:
        productos_aleatorios = []
        mostrar_snackbar(page, "⚠️ No hay conexión a internet en este momento 😅 Revisa tu red e intenta nuevamente.", color="orange")

    tiendas_usuario = db.obtener_tiendas_usuario(usuario["id"])
    ids_tiendas_usuario = {tienda[0] for tienda in tiendas_usuario}

    def iniciar_reserva(id_producto, nombre_producto, cantidad, tienda_id):
        # ACCIÓN: inicia la reserva y confirma si el producto pertenece al usuario.
        def salir(e):
            # BOTÓN SALIR: cierra el aviso; no permite reservar productos propios.
            dialogo.open = False
            page.update()

        # Los productos de otras tiendas pasan directamente al flujo normal de reserva.
        if tienda_id not in ids_tiendas_usuario:
            reservar_view(
                page,
                usuario,
                id_producto,
                nombre_producto,
                cantidad,
                lambda: buscar_producto_view(page, usuario, go_back),
            )
            return

        # DIÁLOGO: evita reservas accidentales de productos propios.
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ Producto de tu propia tienda"),
            content=ft.Text(
                "Estás intentando reservar un producto que pertenece a tu propia tienda. "
                "¿Deseas continuar de todos modos?"
            ),
            actions=[
                ft.TextButton("Salir", on_click=salir),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    aleatorios_column = ft.Row(spacing=12, wrap=False, scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True), width=570, alignment=ft.MainAxisAlignment.CENTER)
    if not productos_aleatorios:
        aleatorios_column.controls.append(ft.Text("⚠️ No hay conexión a internet por el momento 😅\nPrueba de nuevo cuando la red vuelva.", width=300, text_align=ft.TextAlign.CENTER, color="#4D5F7A"))
    else:
        for p in productos_aleatorios:
            pid = p[0]
            nombre = p[1]
            precio_c = float(p[4]) if p[4] else 0
            precio_d = float(p[5]) if p[5] else 0
            cantidad = int(p[6]) if p[6] else 0
            imagen = p[8] if len(p) > 8 else None
            imagen_2 = p[9] if len(p) > 9 else None
            tienda_producto = db.obtener_tienda_por_id(p[7]) if p[7] else None
            whatsapp_aleatorio = tienda_producto[2] if tienda_producto else None
            logo_tienda = tienda_producto[7] if tienda_producto and len(tienda_producto) > 7 else None

            def abrir_whatsapp_aleatorio(e, numero_whatsapp=whatsapp_aleatorio, nombre_producto=nombre):
                try:
                    mensaje = f"Hola, quiero consultar el producto: {nombre_producto}"
                    if not abrir_whatsapp(page, numero_whatsapp, mensaje):
                        mostrar_snackbar(page, "❌ Esta tienda no tiene un número de WhatsApp válido o no se pudo abrir.", color="orange")
                except Exception as error:
                    mostrar_snackbar(page, f"❌ No se pudo abrir WhatsApp: {error}", color="orange")

            thumb = ft.Container(width=80, height=80, bgcolor="#F3F3F3", border_radius=12)
            if imagen and imagen_disponible(imagen):
                thumb = ft.Container(content=ft.Image(src=imagen, width=80, height=80, fit="cover"), width=80, height=80, border_radius=12)
                # Miniatura clicable para mostrar imagen completa
                thumb = ft.Container(content=thumb, on_click=(lambda e, s=imagen, s2=imagen_2: _show_full_image(page, s, s2)), border_radius=12)

            logo_thumb = ft.Container(width=48, height=48, bgcolor="#F3F3F3", border_radius=10)
            if logo_tienda and imagen_disponible(logo_tienda):
                logo_thumb = ft.Container(
                    content=ft.Image(src=logo_tienda, width=48, height=48, fit="cover"),
                    width=48,
                    height=48,
                    border_radius=10,
                    bgcolor="#F3F3F3",
                )

            card = ft.Container(
                content=ft.Column([
                    thumb,
                    logo_thumb,
                    ft.Text("Logo de la tienda", size=10, color="#666666"),
                    ft.Text(nombre, size=12, weight=ft.FontWeight.BOLD),
                    ft.Text(f"C${precio_c:.2f}" , size=12),
                    ft.Text(f"x{cantidad}", size=11, color="#666666"),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Reservar",
                                on_click=lambda e, id_p=pid, nom=nombre, cant=cantidad, tid=p[7]: iniciar_reserva(id_p, nom, cant, tid),
                                width=108,
                            ),
                            ft.Container(
                                content=ft.Image(
                                    src="/whats_icon.png",
                                    width=42,
                                    height=42,
                                    fit="contain",
                                ),
                                on_click=abrir_whatsapp_aleatorio,
                                bgcolor="#F5FFF7",
                                border_radius=22,
                                padding=2,
                                width=44,
                                height=44,
                            ),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=ft.Colors.WHITE,
                border_radius=12,
                padding=10,
                width=170,
            )
            aleatorios_column.controls.append(card)

    def buscar(e):
        resultados.controls.clear()
        busqueda = buscar_entry.value.strip()

        # Cuando se hace una búsqueda, ocultar los productos aleatorios
        if busqueda:
            aleatorios_column.controls.clear()

        if not busqueda:
            resultados.controls.append(
                ft.Text(
                    "Escribe el nombre del producto que deseas encontrar 😊🔎",
                    width=300,
                    text_align=ft.TextAlign.CENTER,
                )
            )
            page.update()
            return

        try:
            productos = db.obtener_productos_por_nombre(busqueda)
        except RuntimeError:
            resultados.controls.append(
                ft.Container(
                    content=ft.Text(
                        "⚠️ No hay conexión a internet 😅\nNo puedo consultar productos en este momento. Vuelve a intentarlo cuando la red esté disponible.",
                        width=300,
                        text_align=ft.TextAlign.CENTER,
                        color="#4D5F7A",
                    ),
                    width=320,
                    padding=10,
                )
            )
            page.update()
            return

        if not productos or len(productos) == 0:
            resultados.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No se encontraron productos en la base de datos. "
                        "Prueba con otro nombre, por favor 😊🔎",
                        width=300,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    width=320,
                    padding=10,
                )
            )
            page.update()
            return

        for p in productos:
            try:
                id_producto = p[0]
                nombre = p[1]
                precio_c = float(p[4]) if p[4] else 0
                precio_d = float(p[5]) if p[5] else 0
                cantidad = int(p[6]) if p[6] else 0
                tienda_id = p[7]
                tienda_producto = db.obtener_tienda_por_id(tienda_id) if tienda_id else None
                whatsapp_producto = tienda_producto[2] if tienda_producto else None
                marca = p[2] or "No indicada"
                talla = p[3] or "No indicada"
                categoria_producto = p[10] if len(p) > 10 and p[10] else "General"
                descripcion_producto = p[11] if len(p) > 11 and p[11] else ""
                estado_producto = p[12] if len(p) > 12 and p[12] else "Nuevo"
                etiquetas_producto = p[13] if len(p) > 13 and p[13] else ""
                color_principal = p[15] if len(p) > 15 and p[15] else ""
                material_producto = p[16] if len(p) > 16 and p[16] else ""
                garantia_producto = p[17] if len(p) > 17 and p[17] else ""
                especificacion_producto = p[18] if len(p) > 18 and p[18] else ""
                garantia_mostrada = _normalizar_texto(garantia_producto) or _normalizar_texto(especificacion_producto) or "No indicada"
                nombre_tienda_producto = tienda_producto[1] if tienda_producto else "Sin tienda"
                direccion_producto = tienda_producto[5] if tienda_producto and len(tienda_producto) > 5 else "No indicada"
                whatsapp_tienda_producto = tienda_producto[2] if tienda_producto and tienda_producto[2] else "No indicado"
                logo_tienda = tienda_producto[7] if tienda_producto and len(tienda_producto) > 7 else None
                imagen_producto = p[8] if len(p) > 8 else None
                imagen_producto_2 = p[9] if len(p) > 9 else None

                def abrir_whatsapp_producto(e, numero_whatsapp=whatsapp_producto, nombre_producto=nombre):
                    try:
                        mensaje = f"Hola, quiero consultar el producto: {nombre_producto}"
                        if not abrir_whatsapp(page, numero_whatsapp, mensaje):
                            mostrar_snackbar(page, "❌ No hay un número de WhatsApp válido para esta tienda. Revisa la información 😊", color="orange")
                    except Exception as error:
                        mostrar_snackbar(page, f"❌ Error al abrir WhatsApp: {error}", color="orange")

                
                thumb = ft.Container(width=48, height=48, bgcolor="#F3F3F3", border_radius=12)
                if imagen_producto and imagen_disponible(imagen_producto):
                    thumb = ft.Container(
                        content=ft.Image(src=imagen_producto, width=48, height=48, fit="cover"),
                        width=48,
                        height=48,
                        border_radius=12,
                        bgcolor="#F3F3F3",
                        padding=0,
                    )

                thumb_clickable = ft.Container(
                    content=thumb,
                    on_click=(lambda e, s=imagen_producto, s2=imagen_producto_2: _show_full_image(page, s, s2)) if imagen_producto else None,
                    border_radius=12,
                )

                logo_thumb = ft.Container(width=64, height=64, bgcolor="#F3F3F3", border_radius=10)
                if logo_tienda and imagen_disponible(logo_tienda):
                    logo_thumb = ft.Container(
                        content=ft.Image(src=logo_tienda, width=64, height=64, fit="cover"),
                        width=64,
                        height=64,
                        border_radius=10,
                        bgcolor="#F3F3F3",
                    )

                info_column = ft.Column(
                    [
                        ft.Row([logo_thumb, ft.Text("Logo de la tienda", size=11, color="#666666")], spacing=8),
                        ft.Text(nombre, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Categoría: {categoria_producto}", size=13, color="#555555"),
                        ft.Text(f"Estado: {estado_producto}", size=13, color="#555555"),
                        ft.Text(f"{('Raza / especie' if categoria_producto == 'Mascotas' else 'Marca')}: {marca}", size=13, color="#555555"),
                        ft.Text(f"Detalle: {talla}", size=13, color="#555555"),
                        ft.Text(f"Color: {color_principal or 'No indicado'} • Material: {material_producto or 'No indicado'}", size=13, color="#555555"),
                        ft.Text(f"Etiquetas: {etiquetas_producto or 'Sin etiquetas'}", size=13, color="#555555"),
                        ft.Text(f"Descripción: {descripcion_producto or 'Sin descripción'}", size=13, color="#555555"),
                        ft.Text(f"Garantía / especificación: {garantia_mostrada}", size=13, color="#555555"),
                        ft.Text(f"Tienda: {nombre_tienda_producto}", size=13, color="#555555"),
                        ft.Text(f"Dirección: {direccion_producto}", size=13, color="#555555"),
                        ft.Text(f"WhatsApp: {whatsapp_tienda_producto}", size=13, color="#555555"),
                        ft.Text(f"Precio: C${precio_c:.2f} / ${precio_d:.2f}"),
                        ft.Text(f"Cantidad disponible: {cantidad}"),
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Reservar",
                                    on_click=lambda e, id_p=id_producto, nom=nombre, cant=cantidad, tid=tienda_id: iniciar_reserva(id_p, nom, cant, tid)
                                ),
                                ft.Container(
                                    content=ft.Image(
                                        src="/whats_icon.png",
                                        width=48,
                                        height=48,
                                        fit="contain",
                                    ),
                                    on_click=abrir_whatsapp_producto,
                                    bgcolor="#F5FFF7",
                                    border_radius=24,
                                    padding=4,
                                    width=48,
                                    height=48,
                                ) if whatsapp_producto else ft.Container(),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=5,
                )

                card = ft.Container(
                    content=ft.Column(
                        [
                            thumb_clickable,
                            info_column,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.START,
                        spacing=10,
                    ),
                    bgcolor=ft.Colors.WHITE,
                    border_radius=15,
                    padding=10,
                )
                resultados.controls.append(card)
            except Exception as error:
                resultados.controls.append(
                    ft.Text(
                        f"Ups, ocurrió un problema al mostrar este producto 😔: {error}",
                        width=300,
                        text_align=ft.TextAlign.CENTER,
                    )
                )

        page.update()

    buscar_entry.on_submit = buscar

    # Función para ir a top_productos y que vuelva a buscar_producto
    def ir_a_top_productos(e):
        top_productos_view(
            page, 
            usuario, 
            lambda u: buscar_producto_view(page, u, go_back)
        )

    def ir_a_buscar_voz(e):
        from views.buscar_voz import buscar_voz_view
        buscar_voz_view(
            page,
            usuario,
            lambda: buscar_producto_view(page, usuario, go_back),
        )

    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("🔎 Buscar productos", size=24, weight=ft.FontWeight.BOLD, color="#040D4A", text_align=ft.TextAlign.CENTER),
                ft.Text("Productos aleatorios", weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                aleatorios_column,
                buscar_entry,
                ft.Row(
                    [
                        ft.ElevatedButton("Buscar", on_click=buscar),
                        ft.ElevatedButton(
                            "🔊 Buscar por voz",
                            on_click=ir_a_buscar_voz,
                            bgcolor="#040D4A",
                            color="white",
                            # Búsqueda por voz conservada para activarla más adelante.
                            visible=False,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                ft.Row([
                    ft.ElevatedButton("📊 Productos Más Comprados", on_click=ir_a_top_productos),
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(content=resultados, width=360),
                ft.Row([
                    ft.ElevatedButton("↩️ Volver al Menu", on_click=lambda e: go_back(usuario))
                ], alignment=ft.MainAxisAlignment.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=22,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=20,
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