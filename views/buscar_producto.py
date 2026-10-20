import flet as ft
import database as db
from views.reservar import reservar_view
from views.top_productos import top_productos_view
from services.cola_tareas import encolar_busqueda_sin_resultado
from services.busqueda_lineal import buscar_productos_linealmente
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
    error_carga_productos = False
    try:
        productos_aleatorios = db.obtener_productos_aleatorios(limit=5)
    except RuntimeError:
        productos_aleatorios = []
        error_carga_productos = True
        mostrar_snackbar(
            page,
            "⚠️ No se pudieron cargar los productos desde la base de datos. Intenta nuevamente más tarde.",
            color="orange",
        )

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
    if error_carga_productos:
        aleatorios_column.controls.append(
            ft.Text(
                "No se pudieron consultar los productos. Intenta nuevamente más tarde.",
                width=300,
                text_align=ft.TextAlign.CENTER,
                color="#4D5F7A",
            )
        )
    elif not productos_aleatorios:
        aleatorios_column.controls.append(
            ft.Text(
                "Aún no hay productos registrados en SmartStore. Cuando una tienda publique productos, aparecerán aquí.",
                width=300,
                text_align=ft.TextAlign.CENTER,
                color="#4D5F7A",
            )
        )
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
            marca_aleatoria = p[2] or "No indicada"
            talla_aleatoria = p[3] or "No indicada"
            categoria_aleatoria = p[10] if len(p) > 10 and p[10] else "General"
            descripcion_aleatoria = p[11] if len(p) > 11 and p[11] else "Sin descripción"
            estado_aleatorio = p[12] if len(p) > 12 and p[12] else "Nuevo"
            etiquetas_aleatorias = p[13] if len(p) > 13 and p[13] else "Sin etiquetas"
            color_aleatorio = p[15] if len(p) > 15 and p[15] else "No indicado"
            material_aleatorio = p[16] if len(p) > 16 and p[16] else "No indicado"
            garantia_aleatoria = _normalizar_texto(p[17] if len(p) > 17 else None) or _normalizar_texto(p[18] if len(p) > 18 else None) or "No indicada"

            def abrir_whatsapp_aleatorio(e, numero_whatsapp=whatsapp_aleatorio, nombre_producto=nombre):
                try:
                    mensaje = f"Hola, quiero consultar el producto: {nombre_producto}"
                    if not abrir_whatsapp(page, numero_whatsapp, mensaje):
                        mostrar_snackbar(page, "❌ Esta tienda no tiene un número de WhatsApp válido o no se pudo abrir.", color="orange")
                except Exception as error:
                    mostrar_snackbar(page, f"❌ No se pudo abrir WhatsApp: {error}", color="orange")

            thumb = ft.Container(width=110, height=110, bgcolor="#F3F3F3", border_radius=12)
            if imagen and imagen_disponible(imagen):
                thumb = ft.Container(content=ft.Image(src=imagen, width=110, height=110, fit="cover"), width=110, height=110, border_radius=12)
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

            detalles_aleatorios = ft.Column(
                [
                    ft.Text(f"Categoría: {categoria_aleatoria}", size=11, color="#555555"),
                    ft.Text(f"Estado: {estado_aleatorio}", size=11, color="#555555"),
                    ft.Text(f"Marca: {marca_aleatoria}", size=11, color="#555555"),
                    ft.Text(f"Detalle: {talla_aleatoria}", size=11, color="#555555"),
                    ft.Text(f"Color: {color_aleatorio} • Material: {material_aleatorio}", size=11, color="#555555"),
                    ft.Text(f"Etiquetas: {etiquetas_aleatorias}", size=11, color="#555555"),
                    ft.Text(f"Descripción: {descripcion_aleatoria}", size=11, color="#555555"),
                    ft.Text(f"Garantía / especificación: {garantia_aleatoria}", size=11, color="#555555"),
                    ft.Text(f"Tienda: {tienda_producto[1] if tienda_producto else 'Sin tienda'}", size=11, color="#555555"),
                    ft.Text(f"Dirección: {tienda_producto[5] if tienda_producto and len(tienda_producto) > 5 else 'No indicada'}", size=11, color="#555555"),
                ],
                spacing=3,
                visible=False,
            )
            texto_detalles = ft.Text("Ver más información", color="#315B91")
            boton_detalles = ft.TextButton(content=texto_detalles)

            def alternar_detalles(e, detalles=detalles_aleatorios, texto=texto_detalles):
                detalles.visible = not detalles.visible
                texto.value = "Ver menos" if detalles.visible else "Ver más información"
                page.update()

            boton_detalles.on_click = alternar_detalles

            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Column([thumb, ft.Text("Imagen del producto", size=9, color="#666666")], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Column([logo_thumb, ft.Text("Logo de la tienda", size=9, color="#666666")], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=8),
                    ft.Text(nombre, size=12, weight=ft.FontWeight.BOLD),
                    ft.Text(f"C${precio_c:.2f}" , size=12),
                    ft.Text(f"x{cantidad}", size=11, color="#666666"),
                    boton_detalles,
                    detalles_aleatorios,
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
                width=230,
            )
            aleatorios_column.controls.append(card)

    def buscar(e):
        resultados.controls.clear()
        busqueda = buscar_entry.value.strip()

        if busqueda:
            boton_volver_menu.visible = False
            boton_volver_atras.visible = True
        else:
            boton_volver_menu.visible = True
            boton_volver_atras.visible = False

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
            productos = buscar_productos_linealmente(productos, busqueda)
        except RuntimeError:
            resultados.controls.append(
                ft.Container(
                    content=ft.Text(
                        "⚠️ No se pudieron consultar los productos desde la base de datos. Intenta nuevamente más tarde.",
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
            solicitud = busqueda.strip()
            if len(solicitud) >= 4:
                encolada = encolar_busqueda_sin_resultado(usuario["id"], solicitud)
                if not encolada:
                    solicitudes = getattr(page, "_smartstore_busquedas_sin_resultado", [])
                    if solicitud.lower() not in {item.lower() for item in solicitudes}:
                        solicitudes.append(solicitud)
                        page._smartstore_busquedas_sin_resultado = solicitudes[-10:]
            if len(solicitud) <= 3:
                mensaje_sin_resultados = (
                    "No encontramos resultados. Asegúrate de que el nombre esté bien escrito "
                    "o escribe el nombre completo del producto para buscarlo mejor 😊🔎"
                )
            else:
                mensaje_sin_resultados = (
                    "No se encontraron productos con ese nombre. "
                    "Asegúrate de que esté bien escrito o prueba con otro nombre 😊🔎"
                )
            resultados.controls.append(
                ft.Container(
                    content=ft.Text(
                        mensaje_sin_resultados,
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

                
                thumb = ft.Container(width=180, height=180, bgcolor="#F3F3F3", border_radius=12)
                if imagen_producto and imagen_disponible(imagen_producto):
                    thumb = ft.Container(
                        content=ft.Image(src=imagen_producto, width=180, height=180, fit="cover"),
                        width=180,
                        height=180,
                        border_radius=12,
                        bgcolor="#F3F3F3",
                        padding=0,
                    )

                thumb_clickable = ft.Container(
                    content=thumb,
                    on_click=(lambda e, s=imagen_producto, s2=imagen_producto_2: _show_full_image(page, s, s2)) if imagen_producto else None,
                    border_radius=12,
                )

                logo_thumb = ft.Container(width=52, height=52, bgcolor="#F3F3F3", border_radius=10)
                if logo_tienda and imagen_disponible(logo_tienda):
                    logo_thumb = ft.Container(
                        content=ft.Image(src=logo_tienda, width=52, height=52, fit="cover"),
                        width=52,
                        height=52,
                        border_radius=10,
                        bgcolor="#F3F3F3",
                    )

                info_column = ft.Column(
                    [
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
                            ft.Row(
                                [
                                    ft.Column([thumb_clickable, ft.Text("Imagen del producto", size=9, color="#666666")], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                    ft.Column([logo_thumb, ft.Text("Logo de la tienda", size=9, color="#666666")], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                ],
                                width=320,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                spacing=8,
                            ),
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

    def volver_al_menu(e):
        go_back(usuario)

    def volver_atras_busqueda(e):
        buscar_producto_view(page, usuario, go_back)

    boton_volver_menu = ft.ElevatedButton("↩️ Volver al menú", on_click=volver_al_menu)
    boton_volver_atras = ft.ElevatedButton("↩️ Volver atrás", on_click=volver_atras_busqueda, visible=False)

    # Función para ir a top_productos y que vuelva a buscar_producto
    def ir_a_top_productos(e):
        top_productos_view(
            page, 
            usuario, 
            lambda u: buscar_producto_view(page, u, go_back)
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
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                ft.Row([
                    ft.ElevatedButton("📊 Productos Más Comprados", on_click=ir_a_top_productos),
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(content=resultados, width=360),
                ft.Row([
                    boton_volver_menu,
                    boton_volver_atras,
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
