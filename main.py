 # EL main.py sirve para ejecutar todo el el programa es el que llama a todas las funciones para que se muetren en pantalla es el corazon y el motor de la es el que despierta a la computadora
import asyncio
import flet as ft 
from utils import comprobar_actualizacion, mostrar_snackbar, tema_smartstore
from app_state import cargar_contexto_usuario
import warnings
warnings.filterwarnings("ignore")

from views.pre_splash import pre_splash_view
from views.splash import splash_view
from views.login import login_view
from views.menu import menu_view
from views.registrar_producto import registrar_producto_view
from views.buscar_producto import buscar_producto_view
from views.carrito import carrito_view
from views.crear_tienda import crear_tienda_view
from views.perfil import perfil_view
from views.inventario import inventario_view
from configuaraciones_adicionales.estadisticas import ajustes_adicionales_view, estadisticas_view
from configuaraciones_adicionales.perfil_usuario import perfil_usuario_view
import database as db

def main(page: ft.Page):
    # PANTALLA/APP: configura la ventana, el tema global y la navegación de SmartStore.
    page.title = "Smart-Store-PyMEs"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = tema_smartstore()

    if page.platform not in (ft.PagePlatform.ANDROID, ft.PagePlatform.ANDROID_TV):
        page.window_width = 420
        page.window_height = 980

    page.padding = 0
    page.spacing = 0
    page.margin = 0
    page.expand = True

    # Alineación global para centrar la pantalla a cualquier tip o de pantalla de celulares
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    try:
        db.inicializar_bd()
    except Exception as e:
        from utils import log_error
        log_error(f"Error initializing DB: {e}")
        mostrar_snackbar(page, "❌ Error initializing database", color="red")
    if not db.USAR_SUPABASE:
        try:
            db.cancelar_reservas_vencidas()
        except Exception as e:
            from utils import log_error
            log_error(f"Error canceling reservations: {e}")
            mostrar_snackbar(page, "❌ Error canceling reservations", color="red")
    usuario_actual = None

    def mostrar_transicion(texto="Cargando..."):
        # PANTALLA TEMPORAL: muestra carga mientras se construye la siguiente vista.
        page.clean()
        page.bgcolor = "#F5F7FA"
        page.add(
            ft.SafeArea(
                ft.Column(
                    [
                        ft.ProgressRing(width=34, height=34, stroke_width=3),
                        ft.Text(texto, color="#555555"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    expand=True,
                ),
                expand=True,
            )
        )
        page.update()

    def cancelar_animaciones_menu():
        for tarea in getattr(page, "_menu_animation_tasks", []):
            try:
                tarea.cancel()
            except Exception:
                pass
        page._menu_animation_tasks = []

    def go_to_splash():
        cancelar_animaciones_menu()
        splash_view(page, go_to_login)

    def go_to_login():
        cancelar_animaciones_menu()
        from views.login import cargar_sesion
        usuario_precargado = getattr(page, "_smartstore_start_user", None)
        contexto_precargado = getattr(page, "_smartstore_context", None)
        if usuario_precargado and contexto_precargado:
            go_to_menu(usuario_precargado)
            return
        correo, token = cargar_sesion(page)
        if correo and token:
            usuario = db.obtener_usuario_por_token(token)
            if usuario:
                usuario_dict = {"id": usuario.id, "nombre": usuario.nombre, "correo": usuario.correo}
                go_to_menu(usuario_dict)
                return
        login_view(page, usuario_actual, go_to_menu)

    def go_to_menu(usuario):
        # NAVEGACIÓN: abre la pantalla principal después de autenticar al usuario.
        nonlocal usuario_actual
        usuario_actual = usuario

        contexto_existente = getattr(page, "_smartstore_context", None)
        if contexto_existente and contexto_existente.get("usuario_id") == usuario_actual["id"]:
            menu_view(page, usuario_actual, logout,
                      go_to_registrar_producto,
                      go_to_buscar_producto,
                      go_to_carrito,
                      go_to_crear_tienda,
                      go_to_perfil,
                      go_to_inventario,
                      go_to_ajustes_adicionales,
                      go_to_control_reservas,
                      contexto=contexto_existente)
            return

        mostrar_transicion("Cargando menú...")

        async def preparar_menu():
            contexto = None
            try:
                contexto = await asyncio.to_thread(cargar_contexto_usuario, usuario_actual["id"])
                page._smartstore_context = contexto
            except Exception as error:
                page._smartstore_context = None
                from utils import log_error
                log_error(f"No se pudo precargar el contexto del usuario: {error}")

            menu_view(page, usuario_actual, logout,
                      go_to_registrar_producto,
                      go_to_buscar_producto,
                      go_to_carrito,
                      go_to_crear_tienda,
                      go_to_perfil,
                      go_to_inventario,
                      go_to_ajustes_adicionales,
                      go_to_control_reservas,
                      contexto=getattr(page, "_smartstore_context", None))

        page.run_task(preparar_menu)

    def go_to_registrar_producto():
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando productos...")
        registrar_producto_view(page, usuario_actual, go_to_menu)

    def go_to_buscar_producto():
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando búsqueda...")
        buscar_producto_view(page, usuario_actual, go_to_menu)

    def go_to_carrito():
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando carrito...")
        carrito_view(page, usuario_actual, go_to_menu)

    def go_to_crear_tienda():
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando tienda...")
        crear_tienda_view(page, usuario_actual, go_to_menu)

    def go_to_perfil():
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando perfil...")
        perfil_view(page, usuario_actual, go_to_menu, logout, go_to_control_reservas)

    def go_to_control_reservas(tienda_id=None, mostrar_billetera=True, mostrar_entregas=True):
        # NAVEGACIÓN: abre el panel de tienda, billetera, reservas y entregas.
        cancelar_animaciones_menu()
        import views.control_reservas
        if tienda_id is None:
            tiendas = db.obtener_tiendas_usuario(usuario_actual['id'])
            if tiendas:
                tienda_id = tiendas[0].id
            else:
                mostrar_snackbar(page, "❌ Aún no tienes tiendas creadas. Crea una para continuar 😊")
                return
        mostrar_transicion("Cargando reservas...")
        views.control_reservas.control_reservas_view(
            page, 
            go_to_perfil,
            lambda: go_to_menu(usuario_actual),
            tienda_id,
            mostrar_billetera,
            mostrar_entregas,
        )

    def go_to_inventario():
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando inventario...")
        inventario_view(page, usuario_actual, go_to_menu)

    def go_to_perfil_usuario(usuario=None):
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando perfil...")
        perfil_usuario_view(page, usuario or usuario_actual, go_to_ajustes_adicionales)

    def go_to_ajustes_adicionales(usuario=None):
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando ajustes...")
        ajustes_adicionales_view(
            page,
            usuario or usuario_actual,
            go_to_menu,
            go_to_estadisticas,
            go_to_perfil_usuario,
        )

    def go_to_estadisticas(usuario=None):
        cancelar_animaciones_menu()
        mostrar_transicion("Cargando estadísticas...")
        estadisticas_view(page, usuario or usuario_actual, go_to_ajustes_adicionales)

    def logout():
        nonlocal usuario_actual
        usuario_actual = None
        from views.login import borrar_sesion
        borrar_sesion(page)
        login_view(page, usuario_actual, go_to_menu)

    async def precargar_inicio():
        """Prepara la sesión y sus datos mientras se muestra el pre-splash."""
        from views.login import cargar_sesion

        try:
            correo, token = cargar_sesion(page)
            if not correo or not token:
                return
            usuario = await asyncio.to_thread(db.obtener_usuario_por_token, token)
            if not usuario:
                return
            usuario_dict = {"id": usuario.id, "nombre": usuario.nombre, "correo": usuario.correo}
            contexto = await asyncio.to_thread(cargar_contexto_usuario, usuario_dict["id"])
            page._smartstore_start_user = usuario_dict
            page._smartstore_context = contexto
        except Exception as error:
            from utils import log_error
            log_error(f"No se pudo precargar el inicio: {error}")
        finally:
            page._smartstore_start_ready.set()

    # ARRANQUE: muestra la primera pantalla de carga y después inicia la actualización.
    page._smartstore_start_ready = asyncio.Event()
    pre_splash_view(page, go_to_splash)
    page.run_task(precargar_inicio)
    page.update()
    page.run_task(comprobar_actualizacion, page)

ft.run(main, assets_dir="assets")
