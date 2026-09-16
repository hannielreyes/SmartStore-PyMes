import json
import os
import threading
from datetime import datetime
from pathlib import Path

import flet as ft

import database as db
from utils import abrir_selector_imagen, guardar_imagen_en_assets, mostrar_snackbar, configurar_retroceso, log_error, boton_glossy

from views.recuperar import recuperar_view

def _obtener_ruta_sesion():
    almacenamiento_app = os.environ.get("FLET_APP_STORAGE_DATA")
    if almacenamiento_app:
        directorio = Path(almacenamiento_app)
        directorio.mkdir(parents=True, exist_ok=True)
        return directorio / "sesion.json"
    return Path(__file__).resolve().parent.parent / "sesion.json"


SESION_FILE = _obtener_ruta_sesion()
SESION_KEY = "smartstore_session"


def guardar_sesion(page, correo, password):
    correo = (correo or "").strip()
    password = (password or "").strip()

    if not correo or not password:
        return

    if not db.obtener_usuario(correo, password):
        return

    try:
        page.client_storage.set(SESION_KEY, {"correo": correo, "password": password})
        return
    except Exception:
        pass
    try:
        with open(SESION_FILE, "w", encoding="utf-8") as f:
            json.dump({"correo": correo, "password": password}, f)
    except Exception:
        pass


def cargar_sesion(page):
    try:
        datos = page.client_storage.get(SESION_KEY)
        if datos:
            correo = str(datos.get("correo") or "").strip()
            password = str(datos.get("password") or "").strip()
            if correo and password and db.obtener_usuario(correo, password):
                return correo, password
            borrar_sesion(page)
            return None, None
    except Exception:
        pass
    try:
        if SESION_FILE.exists():
            with open(SESION_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
            correo = str(datos.get("correo") or "").strip()
            password = str(datos.get("password") or "").strip()
            if correo and password and db.obtener_usuario(correo, password):
                return correo, password
            borrar_sesion(page)
            return None, None
    except Exception:
        pass
    return None, None


def borrar_sesion(page):
    try:
        page.client_storage.remove(SESION_KEY)
    except Exception:
        pass
    try:
        if SESION_FILE.exists():
            SESION_FILE.unlink()
    except Exception:
        pass


def login_view(page: ft.Page, usuario_actual, go_to_menu, correo_inicial="", password_inicial=""):
    # PANTALLA: acceso y registro, con campos, botones y validaciones.
    configurar_retroceso(page, lambda: None)
    page.clean()
    page.update()
    page.bgcolor = "white"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(
            src="fondo.png",
            fit="cover",
        ),
    )

    es_registro = False

    # CAMPOS: controles compartidos por los modos iniciar sesión y registrarse.
    titulo = ft.Text("Iniciar Sesión", size=28, weight=ft.FontWeight.BOLD, color="#040D4A")
    ancho_campos = 340
    ancho_boton_login = 220
    correo_input = ft.TextField(label="Correo electrónico", value=correo_inicial, width=ancho_campos)
    password_input = ft.TextField(label="Contraseña", value=password_inicial, password=True, can_reveal_password=True, width=ancho_campos)
    nombre_input = ft.TextField(label="Nombre completo", width=ancho_campos, visible=False)
    telefono_input = ft.TextField(label="Teléfono", width=ancho_campos, visible=False)
    fecha_input = ft.TextField(label="Fecha de nacimiento (2009-05-15)", width=ancho_campos, visible=False)
    imagen_perfil_path = None
    imagen_perfil_preview = ft.Container(width=48, height=48, bgcolor="#F3F3F3", border_radius=12, visible=False)

    mensaje_estado = ft.Text("", size=14, visible=False, color="red")
    spinner_reconexion = ft.Container(
        visible=False,
        content=ft.ProgressRing(width=24, height=24, stroke_width=3, color="#4D5F7A"),
        width=28,
        height=28,
        alignment=ft.Alignment(0.5, 0.5),
        opacity=0,
    )

    # BOTÓN PRINCIPAL: cambia entre ingresar y registrar según el modo activo.
    btn_accion = boton_glossy("Ingresar", width=ancho_boton_login, color="#EAF2FF", text_color="#4D5F7A")

    # BOTÓN SECUNDARIO: alterna entre iniciar sesión y crear una cuenta.
    btn_alternar = boton_glossy(
        "Crear una cuenta nueva",
        width=ancho_boton_login,
        color="#EAF2FF",
        text_color="#3A0EFD",
    )

    # BOTÓN/ENLACE: abre la pantalla de recuperación de contraseña.
    btn_recuperar = ft.TextButton(
        content=ft.Text("¿Olvidaste tu contraseña?", color="#4D5F7A"),
        on_click=lambda e: recuperar_view(page, go_to_menu),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=22),
            padding=ft.Padding(4, 2, 4, 2),
        ),
    )

    def procesar_imagen_perfil(ruta, image_data=None):
        nonlocal imagen_perfil_path
        if ruta:
            imagen_perfil_path = ruta
            imagen_perfil_preview.content = ft.Image(src=ruta, width=48, height=48, fit="cover")
            imagen_perfil_preview.visible = True
            mostrar_snackbar(page, "✅ Imagen de perfil cargada", color="green")
            page.update()

    # BOTÓN: selecciona una imagen para el perfil durante el registro.
    btn_imagen_perfil = ft.TextButton(
        "🖼️ Agregar imagen a su perfil",
        on_click=lambda e: abrir_selector_imagen(
            page,
            procesar_imagen_perfil,
            title="Seleccionar imagen de perfil",
        ),
        visible=False,
    )

    def mostrar_mensaje(texto, color="red"):
        mensaje_estado.value = str(texto)
        mensaje_estado.color = color
        mensaje_estado.visible = True
        page.update()

    def mostrar_spinner_reconexion():
        spinner_reconexion.visible = True
        spinner_reconexion.opacity = 1
        page.update()

    def ocultar_spinner_reconexion():
        spinner_reconexion.visible = False
        spinner_reconexion.opacity = 0
        page.update()

    def mostrar_spinner_temporal():
        mostrar_spinner_reconexion()
        threading.Timer(2.2, ocultar_spinner_reconexion).start()

    def calcular_edad(fecha_nac_str):
        try:
            fecha_nac = datetime.strptime(fecha_nac_str, "%Y-%m-%d")
            hoy = datetime.now()
            edad = hoy.year - fecha_nac.year
            if (hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day):
                edad -= 1
            return edad
        except Exception:
            return -1

    def cambiar_vista(limpiar_credenciales=True):
        # ACCIÓN: alterna los campos visibles y textos entre login y registro.
        nonlocal es_registro
        es_registro = not es_registro

        titulo.value = "Crear Cuenta" if es_registro else "Iniciar Sesión"
        btn_accion.content = ft.Text("Registrarse" if es_registro else "Ingresar")
        btn_alternar.content = ft.Text(
            "Volver a Iniciar Sesión" if es_registro else "Crear cuenta nueva"
        )

        nombre_input.visible = es_registro
        telefono_input.visible = es_registro
        fecha_input.visible = es_registro
        btn_imagen_perfil.visible = es_registro
        imagen_perfil_preview.visible = es_registro and imagen_perfil_path is not None

        if limpiar_credenciales:
            correo_input.value = ""
            password_input.value = ""

            mensaje_estado.value = ""
            mensaje_estado.visible = False


    def toggle(e):
        cambiar_vista(limpiar_credenciales=True)

    def accion(e):
        if es_registro:
            nombre = nombre_input.value.strip()
            correo = correo_input.value.strip()
            telefono = telefono_input.value.strip()
            fecha_str = fecha_input.value.strip()
            password = password_input.value

            if not nombre or not correo or not telefono or not fecha_str or not password:
                mostrar_mensaje("Por favor, completa todos los campos para continuar. 😊")
                return

            edad = calcular_edad(fecha_str)
            if edad == -1:
                mostrar_mensaje("⚠️ La fecha no tiene un formato válido. Usa AAAA-MM-DD, por ejemplo: 2009-05-15 😊")
                return

            if edad < 17:
                mostrar_mensaje(f"⚠️ Debes tener al menos 17 años para registrarte. Actualmente tienes {edad} años 😊")
                return

            imagen_rel = guardar_imagen_en_assets(imagen_perfil_path, prefijo="perfil") if imagen_perfil_path else None
            try:
                exitoso, mensaje = db.registrar_usuario(nombre, correo, telefono, fecha_str, password, imagen_rel)
            except Exception as e:
                log_error(f"Error registrar usuario: {e}")
                mostrar_snackbar(page, f"❌ Error al registrar usuario: {e}", color="red")
                return
            mostrar_mensaje(mensaje)

            if exitoso:
                guardar_sesion(page, correo, password)
                correo_input.value = correo
                password_input.value = password
                cambiar_vista(limpiar_credenciales=False)
        else:
            correo = correo_input.value.strip()
            password = password_input.value

            if not correo or not password:
                mostrar_mensaje("🔐 Ingresa tu correo y contraseña para continuar 😊")
                return

            try:
                db.verificar_conexion_remota()
                mostrar_spinner_temporal()
            except RuntimeError:
                mostrar_spinner_reconexion()
                return

            try:
                correo_existe = db.verificar_correo_existe(correo)
            except RuntimeError:
                mostrar_spinner_reconexion()
                mostrar_mensaje("⚠️ Parece que no tienes conexión a internet 😅 Revisa tu red y vuelve a intentarlo cuando estés listo 😊")
                return

            if not correo_existe:
                mostrar_mensaje("❌ Este correo aún no está registrado 😌 Puedes revisarlo o crear tu cuenta nueva con gusto 😊")
                return

            try:
                usuario = db.obtener_usuario(correo, password)
            except RuntimeError:
                mostrar_spinner_reconexion()
                mostrar_mensaje("⚠️ Parece que no tienes conexión a internet 😅 Revisa tu red y vuelve a intentarlo cuando estés listo 😊")
                return

            if usuario:
                guardar_sesion(page, correo, password)
                usuario_dict = {"id": usuario[0], "nombre": usuario[1], "correo": usuario[2]}
                go_to_menu(usuario_dict)
            else:
                mostrar_mensaje("❌ El correo o la contraseña no coinciden 😅 Revisa los datos y prueba otra vez, aquí estamos para ayudarte 😊")

    btn_accion.on_click = accion
    btn_alternar.on_click = toggle
    correo_input.on_submit = accion
    password_input.on_submit = accion
    nombre_input.on_submit = accion
    telefono_input.on_submit = accion
    fecha_input.on_submit = accion

    form = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                titulo,
                correo_input,
                password_input,
                nombre_input,
                telefono_input,
                fecha_input,
                btn_imagen_perfil,
                imagen_perfil_preview,
                spinner_reconexion,
                btn_accion,
                mensaje_estado,
                btn_alternar,
                btn_recuperar,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=20,
    )

    # IMPORTANTE: esta estructura centralizada es la base del layout del app.
    # NO MODIFICAR ni mover el Stack/SafeArea aunque se agreguen más campos,
    # más textos o nuevas opciones; debe mantenerse siempre centrado.
    page.add(
        ft.Stack(
            [
                fondo,
                ft.SafeArea(form),
            ],
            expand=True,
        )
    )