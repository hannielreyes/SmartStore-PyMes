import asyncio
import random
import flet as ft
import database as db
from database.models import AlertaInventario, Producto, ReservaTienda, Tienda
from utils import configurar_retroceso, mostrar_snackbar, notificaciones_activas, tema_smartstore

def menu_view(page: ft.Page, usuario, logout, go_to_registrar, go_to_buscar, go_to_carrito, go_to_tienda, go_to_perfil, go_to_inventario, go_to_ajustes_adicionales, go_to_control_reservas, contexto=None):
    # PANTALLA: menú principal con navegación, tiendas, inventario y avisos.
    configurar_retroceso(page, lambda: None)
    page.clean()
    # AVISOS: se reinician al entrar nuevamente al menú.
    # Al tocar un aviso desaparece durante esta visita, pero volverá al regresar
    # desde otra pantalla. La preferencia global de notificaciones no se modifica.
    page._inventario_alerta_oculta = False
    page._reservas_alerta_terminada = False
    page.update()
    page.bgcolor = "white"
    page.theme = tema_smartstore()
    page.update()

    for tarea in getattr(page, "_menu_animation_tasks", []):
        tarea.cancel()
    page._menu_animation_tasks = []

    def salir_del_menu(callback, *args):
        for tarea in page._menu_animation_tasks:
            tarea.cancel()
        page._menu_animation_tasks.clear()
        callback(*args)

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(
            src="fondo.png",
            fit="cover",
        ),
    )

    contexto = contexto or {}
    tiendas = contexto.get("tiendas")
    if tiendas is None:
        tiendas = db.obtener_tiendas_usuario(usuario['id'])
    tiendas = [
        fila if isinstance(fila, Tienda) else Tienda.desde_fila(fila)
        for fila in tiendas
    ]
    stock_total = contexto.get("stock_total")
    if stock_total is None:
        stock_total = db.obtener_stock_total_usuario(usuario['id'])
    alertas_inventario = contexto.get("alertas_inventario")
    if alertas_inventario is None:
        alertas_inventario = db.obtener_alertas_inventario(usuario['id'])
    alertas_inventario = [
        fila if isinstance(fila, AlertaInventario) else AlertaInventario.desde_fila(fila)
        for fila in alertas_inventario
    ]
    avisos_activos = notificaciones_activas(page)
    reservas_por_entregar = contexto.get("reservas")
    if reservas_por_entregar is None:
        reservas_por_entregar = []
        for tienda in tiendas:
            try:
                reservas_por_entregar.extend(db.obtener_reservas_por_tienda(tienda.id))
            except Exception:
                continue
    reservas_por_entregar = [
        fila if isinstance(fila, ReservaTienda) else ReservaTienda.desde_fila(fila)
        for fila in reservas_por_entregar
    ]

    def abrir_inventario(e):
        # ACCIÓN: abre el inventario del usuario.
        salir_del_menu(go_to_inventario)

    def abrir_estadisticas(e):
        # ACCIÓN: abre la pantalla de ajustes adicionales.
        salir_del_menu(go_to_ajustes_adicionales)

    def confirmar_cierre_sesion(e):
        # DIÁLOGO: confirma antes de cerrar la sesión actual.
        def volver(e):
            # BOTÓN: cancela el cierre y vuelve al menú.
            dialogo.open = False
            page.update()

        def cerrar_sesion(e):
            # BOTÓN: cierra la sesión y envía al login.
            dialogo.open = False
            page.update()
            salir_del_menu(logout)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("👋 ¿Quieres cerrar sesión?", size=18, weight=ft.FontWeight.BOLD, color="#040D4A"),
            content=ft.Text(
                "Tu sesión está a punto de terminar. Cuando quieras volver, aquí estaremos para recibirte 😊",
                size=14,
                color="#555555",
            ),
            actions=[
                # BOTÓN: conserva la sesión abierta.
                ft.TextButton("↩️ Volver", on_click=volver),
                # BOTÓN: confirma el cierre de sesión.
                ft.ElevatedButton(
                    "✅ Sí, cerrar sesión",
                    on_click=cerrar_sesion,
                    bgcolor="#D84315",
                    color="white",
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    ancho_cobertura = min(max((page.width or 360) - 80, 280), 595)
    encabezado_animacion = ft.Container(
        content=ft.Container(height=0),
        width=0,
        height=0,
    )

    # BOTÓN: acceso visual a Ajustes Adicionales desde el encabezado.
    boton_estadisticas = ft.Container(
        content=ft.IconButton(
            icon=ft.Icons.SETTINGS,
            icon_color="#FF4D2D",
            on_click=abrir_estadisticas,
            tooltip="Ajustes Adicionales",
            width=42,
            height=42,
            bgcolor="transparent",
        ),
        width=46,
        height=46,
        border=ft.Border.all(1.5, "#00FF00"),
        border_radius=14,
        left=8,
        top=32,
        alignment=ft.Alignment(0.5, 0.5),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=8,
            color="#00FF00",
            offset=ft.Offset(0, 0),
            blur_style="normal",
        ),
    )

    textos_marca = ft.Row(
        [
            ft.Text("Smart", size=28, weight=ft.FontWeight.BOLD, color="#0A1A75"),
            ft.Text(" Store", size=28, weight=ft.FontWeight.BOLD, color="#EFA520"),
            ft.Text(" PyMEs", size=22, weight=ft.FontWeight.BOLD, color="#11C71A"),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        visible=False,
        opacity=0,
        offset=ft.Offset(-1.2, 0),
        animate_offset=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
    )

    async def animar_marca_header():
        try:
            while True:
                textos_marca.visible = False
                textos_marca.opacity = 0
                textos_marca.offset = ft.Offset(-1.2, 0)
                page.update()
                await asyncio.sleep(13)

                textos_marca.visible = True
                textos_marca.opacity = 1
                textos_marca.offset = ft.Offset(0, 0)
                page.update()
                await asyncio.sleep(4)

                textos_marca.opacity = 0
                textos_marca.offset = ft.Offset(1.2, 0)
                page.update()
        except asyncio.CancelledError:
            return

    # BOTONES DINÁMICOS: crea un botón por cada tienda del usuario.
    tiendas_botones = []
    for t in tiendas:
        tienda_id = t.id
        tienda_nombre = t.nombre or "Tienda"
        
        tiendas_botones.append(
            ft.Row(
                [
                    ft.ElevatedButton(
                        content=ft.Text(f"🏪 {tienda_nombre}", size=16, weight=ft.FontWeight.BOLD),
                        height=42,
                        style=ft.ButtonStyle(padding=ft.Padding(left=18, right=18, top=0, bottom=0)),
                        bgcolor="#040D4A",
                        color="white",
                        on_click=lambda e, id_tienda=tienda_id: salir_del_menu(go_to_control_reservas, id_tienda, False, True),
                    ),
                ],
                spacing=4,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        )

    lista_tiendas = ft.Row(
        tiendas_botones,
            width=ancho_cobertura,
        spacing=10,
        height=55,
        alignment=ft.MainAxisAlignment.CENTER,
                scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
    ) if tiendas_botones else ft.Text("Aún no tienes tiendas. ¡Crea la primera! 😊", size=14, color="gray")

    # Estilo compartido por los botones principales del menú.
    menu_button_style = ft.ButtonStyle(
        color="#4D5F7A",
        bgcolor="#EEF4FF",
        overlay_color="#D9E8FF",
        shadow_color="#D9E8FF",
    )

    # Mensajes reales de inventario: solo se usan si existen productos con poco stock.
    mensajes_inventario = [
        "HOLa,🖐🏿 algunos de TUs productos se an agotadO😏",
        "Oyee👀, ya casi nO quedan unidadeS de algunoS productos😅",
        "AvisoO📣, hay algunoS productos que necesitan uN poquito de atención😉",
        "Heyy🛍️, revisA alGunos proDuctos anteS de que se termineN😮",
        "AtencióN😏, quedan ProductoS con muY poquitas unidades🫣",
        "RevisA tu inventariO👀, algunOs productos ya casi se terminAn📦",
        "CuidA tu stock😅, hay productos que necesitan reposicióN prontO🛒",
        "Ojo con esas unidadeS📣, algunos productos están por agotarsE😉",
    ]
    # Mensajes reales para usuarios que todavía no tienen ninguna tienda.
    mensajes_tienda = [
        "Aún nO tienes tu PopiA tiendA🏪, anímate y Crea Una😏",
        "Oyee👀, todavía nO has creadO tu tiendA, Animate y Crea Una🛍️",
        "Tu tiendA te estA esperandO😉, Crea Una y empezA a vender📦",
        "Aún nO tienes tiendA😅, Animate y armA tu propiO negociO🏪",
        "Crea tu PopiA tiendA🛒 y empezA a mostrAr tus productos😏",
        "Dale vida a tu negociO🏪, creA tu primera tiendA cuandO quieras😉",
        "Tus productos merecen un escaparate🛍️, creA tu tiendA y compartelOs😏",
        "EmpiezA a vender📦, registrA tu primera tiendA en SmartStore👀",
    ]
    # Mensajes reales de reservas pendientes de entrega en las tiendas del usuario.
    mensajes_reservas = [
        "Genial😏, TENES reservA poR entregAr en tu tiendA📦",
        "Oyee🖐🏿, hay un clientE esperandO retirAr su pedido😉",
        "Buenisimo👀, preparA esa reservA parA entregAr en tiendA😅",
        "AviisO📣, ya tenes un pedido listO parA entregAr🛍️",
        "Heyy😏, no te olvides de entregAr esa reservA en tiendA📦",
        "RevisA tus pedidos📦, hay una reservA que esperA entregA😉",
        "Tu clientE ya está esperandO👀, preparA la reservA para entregarlA😅",
        "MomentO de entregAr🛍️, tienes una reservA pendiente en tu tiendA📣",
    ]
    # AVISOS DE OPORTUNIDAD: búsquedas sin producto registrado, sin identificar al cliente.
    busquedas_sin_resultado = list(getattr(page, "_smartstore_busquedas_sin_resultado", []))
    try:
        busquedas_sin_resultado.extend(
            db.obtener_oportunidades_productos(usuario["id"])
        )
    except Exception:
        pass
    productos_contexto = [
        fila if isinstance(fila, Producto) else Producto.desde_fila(fila)
        for fila in contexto.get("productos", [])
    ]
    nombres_productos = {
        str(producto.nombre).strip().lower()
        for producto in productos_contexto
        if producto.nombre
    }
    busquedas_sin_resultado = [
        busqueda for busqueda in busquedas_sin_resultado
        if busqueda.strip().lower() not in nombres_productos
    ]
    page._smartstore_busquedas_sin_resultado = busquedas_sin_resultado
    mensaje_busqueda = None
    if avisos_activos and busquedas_sin_resultado:
        producto_solicitado = busquedas_sin_resultado.pop(0)
        mensaje_busqueda = (
            "🔎 Un cliente buscó «{}» y todavía no aparece registrado. "
            "Podría ser una buena oportunidad para venderlo 📦"
        ).format(producto_solicitado)
    page._smartstore_busquedas_sin_resultado = busquedas_sin_resultado

    alertas_card = None
    if avisos_activos:
        # SECUENCIA: prepara frases nuevas sin repetir la primera de la visita anterior.
        def ordenar_mensajes(mensajes, clave):
            orden = random.sample(mensajes, len(mensajes))
            ultimo = getattr(page, clave, None)
            if len(orden) > 1 and orden[0] == ultimo:
                orden.append(orden.pop(0))
            setattr(page, clave, orden[0])
            return orden

        secuencia_inventario = []
        if tiendas and alertas_inventario:
            secuencia_inventario = [
                ("inventario", mensaje)
                for mensaje in ordenar_mensajes(mensajes_inventario, "_ultimo_mensaje_inventario")
            ]

        secuencia_reservas = []
        if tiendas and reservas_por_entregar:
            secuencia_reservas = [
                ("reservas", mensaje)
                for mensaje in ordenar_mensajes(mensajes_reservas, "_ultimo_mensaje_reservas")
            ]

        if not tiendas:
            secuencia_avisos = [
                ("tienda", mensaje)
                for mensaje in ordenar_mensajes(mensajes_tienda, "_ultimo_mensaje_tienda")
            ]
        elif secuencia_inventario and secuencia_reservas:
            # INTERCALADO: alterna inventario y reservas para que ninguna categoría domine.
            secuencia_avisos = []
            for indice in range(max(len(secuencia_inventario), len(secuencia_reservas))):
                if indice < len(secuencia_inventario):
                    secuencia_avisos.append(secuencia_inventario[indice])
                if indice < len(secuencia_reservas):
                    secuencia_avisos.append(secuencia_reservas[indice])
        else:
            # CADENA ÚNICA: cuando solo existe una clase de aviso real.
            secuencia_avisos = secuencia_inventario or secuencia_reservas

        if mensaje_busqueda:
            posicion_aviso = random.randint(0, len(secuencia_avisos))
            secuencia_avisos.insert(posicion_aviso, ("busqueda", mensaje_busqueda))

        if secuencia_avisos:
            contenido_aviso = ft.Column(
                spacing=5,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

            def mostrar_aviso_actual():
                # CONTENIDO: muestra el texto y, si corresponde, los productos reales afectados.
                tipo, mensaje = secuencia_avisos[0]
                contenido_aviso.controls.clear()
                contenido_aviso.controls.append(
                    ft.Text(
                        mensaje,
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        color="#8A4B00",
                        text_align=ft.TextAlign.CENTER,
                    )
                )
                if tipo == "inventario":
                    contenido_aviso.controls.extend(
                        ft.Text(
                            f"{alerta.nombre}: quedan {alerta.stock} unidades 😬",
                            size=13,
                            color="#C62828",
                            text_align=ft.TextAlign.CENTER,
                        )
                        for alerta in alertas_inventario[:5]
                    )

            def ocultar_aviso(e):
                # ACCIÓN: oculta el único aviso de esta visita al menú.
                alertas_card.visible = False
                page.update()

            mostrar_aviso_actual()
            alertas_card = ft.Container(
                content=contenido_aviso,
                bgcolor="#FFF8E1",
                border_radius=12,
                padding=10,
                width=280,
                on_click=ocultar_aviso,
            )

    # BOTONES DE NAVEGACIÓN PRINCIPAL: cada ancho se puede ajustar por separado.
    ancho_btn_registrar = 250
    ancho_btn_buscar = 250
    ancho_btn_reservas = 250
    ancho_btn_tienda = 250

    # Contenido central: textos, botones de navegación y tarjetas informativas.
    contenido_desplazable = ft.Column(
        [
            ft.Text(f"👤 Bienvenido, {usuario['nombre']}", size=18, weight=ft.FontWeight.W_600, color="#040D4A"),
            ft.Text("Gestiona tu negocio de forma inteligente", size=13, color="#555555"),
            ft.ElevatedButton("📦 Registrar Producto", on_click=lambda e: salir_del_menu(go_to_registrar), width=ancho_btn_registrar, color="#4D5F7A", bgcolor="#EEF4FF", style=menu_button_style),
            ft.ElevatedButton("🔍 Buscar Productos", on_click=lambda e: salir_del_menu(go_to_buscar), width=ancho_btn_buscar, color="#4D5F7A", bgcolor="#EEF4FF", style=menu_button_style),
            ft.ElevatedButton("🛒 Reservas y Carrito", on_click=lambda e: salir_del_menu(go_to_carrito), width=ancho_btn_reservas, color="#4D5F7A", bgcolor="#EEF4FF", style=menu_button_style),
            ft.ElevatedButton("🏪 Crear Tienda", on_click=lambda e: salir_del_menu(go_to_tienda), width=ancho_btn_tienda, color="#4D5F7A", bgcolor="#EEF4FF", style=menu_button_style),
            ft.Text("📊 Mis Tiendas", size=18, weight=ft.FontWeight.BOLD, color="#040D4A"),
            lista_tiendas,
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"Total de productos: {stock_total}", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("Estado del inventario", size=14, color="#555555"),
                        ft.Text("Toca para ver detalle →", size=11, color="#888888", italic=True),
                    ],
                    spacing=5,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.WHITE,
                border_radius=15,
                padding=15,
                on_click=abrir_inventario,
            ),
            *([alertas_card] if alertas_card else []),
            # BOTONES DE SESIÓN Y BILLETERA: accesos secundarios del menú.
            ft.Row(
                [
                    ft.TextButton("💳 Mi Billetera", on_click=lambda e: salir_del_menu(go_to_perfil), style=ft.ButtonStyle(color="#4D5F7A")),
                    ft.TextButton("🚪 Cerrar Sesión", on_click=confirmar_cierre_sesion, style=ft.ButtonStyle(color="#4D5F7A")),
                ],
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=15,
        scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        expand=True,
    )

    contenido = ft.Container(
        content=ft.Column(
            [
                encabezado_animacion,
                ft.Row(
                    textos_marca,
                    width=ancho_cobertura,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                contenido_desplazable,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
            expand=True,
        ),
        padding=20,
        expand=True,
    )

    page._menu_animation_tasks.extend([
        page.run_task(animar_marca_header),
    ])

    # IMPORTANTE: esta estructura de centrado es la base visual del app.
    # NO MODIFICAR ni reubicar el Stack/SafeArea ni el alignment aunque se agreguen
    # más campos, más contenido o nuevas secciones. La vista debe seguir centrada.
    page.add(
        ft.Stack(
            [
                fondo,
                ft.SafeArea(contenido),
                boton_estadisticas,
            ],
            expand=True,
        )
    )
