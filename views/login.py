import json
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import secrets
import string
import threading
from datetime import datetime
from pathlib import Path

import flet as ft

import database as db
from utils import abrir_selector_imagen, guardar_imagen_en_assets, mostrar_snackbar, configurar_retroceso, log_error, boton_glossy

from views.recuperar import recuperar_view
from supabase_config import (
    crear_url_oauth_google,
    intercambiar_codigo_oauth,
    obtener_refresh_token_auth,
)

def _obtener_ruta_sesion():
    almacenamiento_app = os.environ.get("FLET_APP_STORAGE_DATA")
    if almacenamiento_app:
        directorio = Path(almacenamiento_app)
        directorio.mkdir(parents=True, exist_ok=True)
        return directorio / "sesion.json"
    return Path(__file__).resolve().parent.parent / "sesion.json"


SESION_FILE = _obtener_ruta_sesion()
SESION_KEY = "smartstore_session"


def generar_codigo_sesion(longitud=None):
    if longitud is None:
        longitud = secrets.randbelow(5) + 12
    if longitud < 3:
        raise ValueError("El código de sesión debe tener al menos 3 caracteres")

    letras = string.ascii_letters
    numeros = string.digits
    simbolos = "#*/?&%$@sebnmotyuacnq.iwxz1234567890)+,!:;=<"
    caracteres = letras + numeros + simbolos
    codigo = [
        secrets.choice(letras),
        secrets.choice(numeros),
        secrets.choice(simbolos),
    ]
    codigo.extend(secrets.choice(caracteres) for _ in range(longitud - len(codigo)))
    secrets.SystemRandom().shuffle(codigo)
    return "".join(codigo)


def invalidar_codigo_sesion(page):
    page._smartstore_session_code = None


def invalidar_codigo_recuperacion(page):
    page._smartstore_recovery_code = None


def codigo_sesion_valido(page, codigo):
    esperado = getattr(page, "_smartstore_session_code", None)
    return bool(esperado and codigo and secrets.compare_digest(str(esperado), str(codigo)))


def codigo_recuperacion_valido(page, codigo):
    esperado = getattr(page, "_smartstore_recovery_code", None)
    return bool(esperado and codigo and secrets.compare_digest(str(esperado), str(codigo)))


def guardar_sesion(page, correo, password, usuario_id=None):
    correo = (correo or "").strip()
    password = (password or "").strip()

    if not correo or (not password and usuario_id is None):
        return

    token = db.crear_token_sesion(correo, password, usuario_id=usuario_id)
    if not token:
        return
    auth_refresh_token = obtener_refresh_token_auth()

    try:
        page.client_storage.set(SESION_KEY, {"token": token, "auth_refresh_token": auth_refresh_token})
        return
    except Exception:
        pass
    try:
        with open(SESION_FILE, "w", encoding="utf-8") as f:
            json.dump({"token": token, "auth_refresh_token": auth_refresh_token}, f)
    except Exception:
        pass


def cargar_sesion(page):
    try:
        datos = page.client_storage.get(SESION_KEY)
        if datos:
            token = str(datos.get("token") or "").strip()
            refresh_token = datos.get("auth_refresh_token")
            db.restaurar_sesion_auth(refresh_token)
            nuevo_refresh_token = obtener_refresh_token_auth()
            usuario = db.obtener_usuario_por_token(token)
            if usuario:
                if nuevo_refresh_token and nuevo_refresh_token != refresh_token:
                    datos["auth_refresh_token"] = nuevo_refresh_token
                    page.client_storage.set(SESION_KEY, datos)
                return usuario[2], token
            borrar_sesion(page)
            return None, None
    except Exception:
        pass
    try:
        if SESION_FILE.exists():
            with open(SESION_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
            token = str(datos.get("token") or "").strip()
            refresh_token = datos.get("auth_refresh_token")
            db.restaurar_sesion_auth(refresh_token)
            nuevo_refresh_token = obtener_refresh_token_auth()
            usuario = db.obtener_usuario_por_token(token)
            if usuario:
                if nuevo_refresh_token and nuevo_refresh_token != refresh_token:
                    datos["auth_refresh_token"] = nuevo_refresh_token
                    with open(SESION_FILE, "w", encoding="utf-8") as f:
                        json.dump(datos, f)
                return usuario[2], token
            borrar_sesion(page)
            return None, None
    except Exception:
        pass
    return None, None


def borrar_sesion(page):
    invalidar_codigo_sesion(page)
    try:
        datos = page.client_storage.get(SESION_KEY)
        db.revocar_token_sesion((datos or {}).get("token"))
    except Exception:
        pass
    try:
        page.client_storage.remove(SESION_KEY)
    except Exception:
        pass
    try:
        if SESION_FILE.exists():
            try:
                with open(SESION_FILE, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                db.revocar_token_sesion((datos or {}).get("token"))
            except Exception:
                pass
            SESION_FILE.unlink()
    except Exception:
        pass


def iniciar_google_oauth(page, cuando_exito, cuando_error):
    """Abre Google y devuelve el resultado OAuth a la ventana de escritorio."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    redirect_to = "http://127.0.0.1:8765/auth/callback"

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            from urllib.parse import parse_qs, urlparse
            parametros = parse_qs(urlparse(self.path).query)
            codigo = parametros.get("code", [None])[0]
            error = parametros.get("error_description", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h2>Puedes volver a SmartStore.</h2>")
            self.server.resultado = (codigo, error)

            def detener():
                self.server.shutdown()

            threading.Thread(target=detener, daemon=True).start()

        def log_message(self, *_args):
            return

    try:
        servidor = HTTPServer(("127.0.0.1", 8765), CallbackHandler)
    except OSError:
        cuando_error("El puerto OAuth local está ocupado. Cierra otra instancia e inténtalo nuevamente.")
        return
    servidor.resultado = (None, None)
    url = crear_url_oauth_google(redirect_to, challenge)

    def esperar_callback():
        servidor.serve_forever()
        codigo, error = servidor.resultado
        servidor.server_close()
        if not codigo:
            cuando_error(error or "Google no completó la autenticación.")
            return
        try:
            respuesta = intercambiar_codigo_oauth(codigo, verifier)
            cuando_exito(respuesta)
        except Exception as exc:
            cuando_error(str(exc))

    threading.Thread(target=esperar_callback, daemon=True).start()

    async def abrir_navegador():
        try:
            resultado = page.launch_url(url)
            if hasattr(resultado, "__await__"):
                await resultado
        except Exception as exc:
            cuando_error(f"No se pudo abrir el navegador: {exc}")

    page.run_task(abrir_navegador)


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
    usuario_google = None

    # CAMPOS: controles compartidos por los modos iniciar sesión y registrarse.
    titulo = ft.Text("Iniciar Sesión", size=28, weight=ft.FontWeight.BOLD, color="#040D4A")
    ancho_campos = min(340, max(190, (page.width or 420) - 40))
    ancho_boton_ingresar = 120
    ancho_boton_registro = 195
    alto_boton_ingresar = 48
    alto_boton_registro = 48
    estilo_etiqueta = ft.TextStyle(size=12)
    correo_input = ft.TextField(label="Correo electrónico", label_style=estilo_etiqueta, value=correo_inicial, width=ancho_campos)
    password_input = ft.TextField(label="Contraseña", label_style=estilo_etiqueta, value=password_inicial, password=True, can_reveal_password=True, width=ancho_campos)
    nombre_input = ft.TextField(label="Nombre completo", label_style=estilo_etiqueta, width=ancho_campos, visible=False)
    telefono_input = ft.TextField(label="Teléfono", label_style=estilo_etiqueta, width=ancho_campos, visible=False)
    fecha_input = ft.TextField(label="Fecha de nacimiento (2009-05-15)", label_style=estilo_etiqueta, width=ancho_campos, visible=False)
    imagen_perfil_path = None
    imagen_perfil_preview = ft.Container(width=48, height=48, bgcolor="#F3F3F3", border_radius=12, visible=False)

    mensaje_estado = ft.Text("", size=14, visible=False, color="red")
    codigo_sesion = None
    panel_codigo = ft.Container(visible=False)
    spinner_reconexion = ft.Container(
        visible=False,
        content=ft.ProgressRing(width=24, height=24, stroke_width=3, color="#4D5F7A"),
        width=28,
        height=28,
        alignment=ft.Alignment(0.5, 0.5),
        opacity=0,
    )

    # BOTÓN PRINCIPAL: cambia entre ingresar y registrar según el modo activo.
    btn_accion = boton_glossy(
        "Ingresar",
        width=ancho_boton_ingresar,
        height=alto_boton_ingresar,
        color="#EAF2FF",
        text_color="#4D5F7A",
    )

    # BOTÓN SECUNDARIO: alterna entre iniciar sesión y crear una cuenta.
    btn_alternar = boton_glossy(
        "Crear una cuenta nueva",
        width=ancho_boton_registro,
        height=alto_boton_registro,
        color="#EAF2FF",
        text_color="#3A0EFD",
    )
    btn_alternar.visible = False

    # BOTÓN/ENLACE: abre la pantalla de recuperación de contraseña.
    btn_recuperar = ft.TextButton(
        content=ft.Text("¿Olvidaste tu contraseña?", color="#4D5F7A"),
        on_click=lambda e: recuperar_view(page, go_to_menu),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=22),
            padding=ft.Padding(4, 2, 4, 2),
        ),
    )
    
    # ================================================================
    # BOTÓN GOOGLE: RESPONSIVO CON PADDING SINTÁCTICAMENTE VÁLIDO (ft.Padding)
    # ================================================================
    ancho_google = ancho_campos
    img_google = ft.Image(
        src="whats_icon.png", 
        width=18 if ancho_campos < 310 else 20, 
        height=18 if ancho_campos < 310 else 20
    )
    texto_google = ft.Text(
        "Google" if ancho_campos < 310 else "Continuar con Google",
        size=13,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER,
        overflow=ft.TextOverflow.ELLIPSIS,
        max_lines=1,
    )
    contenido_google = ft.Row(
        [
            img_google,
            texto_google,
        ],
        spacing=8,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    btn_google = ft.ElevatedButton(
        content=contenido_google,
        width=ancho_google,
        height=54,
        style=ft.ButtonStyle(
            padding=ft.Padding(8, 0, 8, 0),
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

    def completar_google(respuesta):
        nonlocal es_registro, usuario_google
        usuario_google = respuesta.get("user") or {}
        panel_codigo.visible = False
        metadatos = usuario_google.get("user_metadata") or {}
        correo_input.value = usuario_google.get("email") or ""
        nombre_input.value = metadatos.get("full_name") or metadatos.get("name") or ""
        password_input.value = ""
        password_input.label = "Contraseña SmartStore"
        password_input.can_reveal_password = True
        password_input.visible = True
        es_registro = True
        titulo.value = "Completa tu perfil"
        btn_accion.content = ft.Text("Guardar perfil")
        btn_alternar.visible = False
        btn_google.visible = False
        btn_recuperar.visible = False
        nombre_input.visible = True
        telefono_input.visible = True
        fecha_input.visible = True
        btn_imagen_perfil.visible = True
        mostrar_mensaje("Google autenticó tu correo. Crea una contraseña propia de SmartStore y completa tu perfil.", "green")

    btn_google.on_click = lambda e: iniciar_google_oauth(
        page,
        cuando_exito=completar_google,
        cuando_error=lambda mensaje: mostrar_mensaje(f"❌ {mensaje}"),
    )

    def mostrar_codigo_y_continuar(usuario_dict, correo, password):
        nonlocal codigo_sesion
        codigo_sesion = generar_codigo_sesion()
        try:
            if not db.guardar_codigo_sesion(correo, codigo_sesion):
                raise RuntimeError("No se encontró la cuenta para guardar el código")
        except Exception as exc:
            log_error(f"Error al guardar el código de sesión: {exc}")
            mostrar_snackbar(page, "❌ No se pudo guardar el código de seguridad. Intenta nuevamente.", color="red")
            return
        guardar_sesion(page, correo, password, usuario_id=usuario_dict.get("id"))
        page._smartstore_session_code = codigo_sesion
        page._smartstore_recovery_code = codigo_sesion
        btn_accion.visible = False
        texto_codigo = ft.Text(
            codigo_sesion,
            size=20,
            weight=ft.FontWeight.BOLD,
            color="#040D4A",
            text_align=ft.TextAlign.CENTER,
        )

        async def copiar_codigo(e):
            try:
                await page.clipboard.set(codigo_sesion)
            except Exception:
                mostrar_snackbar(page, "No se pudo copiar automáticamente. Anota el código manualmente.", color="orange")
                return
            panel_codigo.visible = False
            page.update()
            go_to_menu(usuario_dict)

        panel_codigo.content = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Código de seguridad de esta sesión", size=13, color="#555555", text_align=ft.TextAlign.CENTER),
                    texto_codigo,
                    ft.Text(
                        "Guarda este código en un lugar seguro. Lo necesitarás para recuperar tu contraseña después de cerrar sesión. En tu próximo inicio de sesión se generará un código nuevo.",
                        size=12,
                        color="#555555",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.ElevatedButton("📋 Copiar código", on_click=lambda e: page.run_task(copiar_codigo, e), bgcolor="#040D4A", color="white"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=12,
            bgcolor="#FFF4E8",
            border_radius=12,
            width=ancho_campos,
        )
        panel_codigo.visible = True
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
        btn_google.visible = not es_registro
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

            if not nombre or not correo or not telefono or not fecha_str or (not password and not usuario_google):
                mostrar_mensaje("Por favor, completa todos los campos para continuar. 😊")
                return

            if not usuario_google and len(password) < 6:
                mostrar_mensaje("La contraseña debe tener al menos 6 caracteres.")
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
                if usuario_google:
                    if len(password) < 6:
                        mostrar_mensaje("La contraseña SmartStore debe tener al menos 6 caracteres.")
                        return
                    if not db.establecer_contraseña_auth(password):
                        panel_codigo.visible = False
                        mostrar_mensaje("❌ No se pudo crear la contraseña de SmartStore.")
                        return
                    exitoso, mensaje = db.crear_perfil_auth(
                        usuario_google.get("id"), nombre, correo, telefono, fecha_str, imagen_rel
                    )
                elif db._supabase_activo():
                    exitoso, mensaje = db.registrar_usuario_auth(
                        nombre, correo, telefono, fecha_str, password, imagen_rel
                    )
                else:
                    exitoso, mensaje = db.registrar_usuario(
                        nombre, correo, telefono, fecha_str, password, imagen_rel
                    )
            except Exception as e:
                log_error(f"Error registrar usuario: {e}")
                mostrar_snackbar(page, f"❌ Error al registrar usuario: {e}", color="red")
                return
            mostrar_mensaje(mensaje)

            if exitoso:
                if usuario_google:
                    usuario = db.obtener_usuario_por_correo(correo)
                    if not usuario:
                        mostrar_mensaje("❌ No se pudo preparar tu perfil.")
                        return
                    usuario_dict = {"id": usuario[0], "nombre": usuario[1], "correo": usuario[2]}
                    mostrar_codigo_y_continuar(usuario_dict, correo, "")
                    return
                if "confirma tu correo" in mensaje.lower():
                    return
                try:
                    usuario = db.obtener_usuario(correo, password)
                except Exception as error:
                    log_error(f"Error al preparar el código de la cuenta nueva: {error}")
                    mostrar_snackbar(page, "✅ Cuenta creada. Inicia sesión para recibir tu código de seguridad.", color="green")
                    correo_input.value = correo
                    password_input.value = password
                    cambiar_vista(limpiar_credenciales=False)
                    return

                if not usuario:
                    mostrar_snackbar(page, "✅ Cuenta creada. Inicia sesión para recibir tu código de seguridad.", color="green")
                    correo_input.value = correo
                    password_input.value = password
                    cambiar_vista(limpiar_credenciales=False)
                    return

                usuario_dict = {"id": usuario[0], "nombre": usuario[1], "correo": usuario[2]}
                mostrar_codigo_y_continuar(usuario_dict, correo, password)
        else:
            correo = correo_input.value.strip()
            password = password_input.value

            if not correo or not password:
                mostrar_mensaje("🔐 Ingresa tu correo y contraseña para continuar 😊")
                return

            try:
                db.verificar_conexion_remota()
                mostrar_spinner_temporal()
            except RuntimeError as exc:
                ocultar_spinner_reconexion()
                if "desactivado" in str(exc).lower():
                    mostrar_mensaje("⚙️ Supabase está desactivado. Cierra y vuelve a abrir la app con SMARTSTORE_USAR_SUPABASE=1.")
                elif "no está configurado" in str(exc).lower():
                    mostrar_mensaje("⚙️ Supabase no está configurado correctamente. Revisa la URL y la clave anon/public.")
                else:
                    mostrar_mensaje("⚠️ No se pudo conectar con Supabase. Revisa la conexión y las políticas RLS.")
                return

            try:
                if db._supabase_activo():
                    resultado_auth = db.iniciar_sesion_auth(correo, password)
                    usuario = resultado_auth[2] if resultado_auth else None
                else:
                    usuario = db.obtener_usuario(correo, password)
            except RuntimeError:
                ocultar_spinner_reconexion()
                mostrar_mensaje("⚠️ Parece que no tienes conexión a internet 😅 Revisa tu red y vuelve a intentarlo cuando estés listo 😊")
                return

            if usuario:
                usuario_dict = {"id": usuario[0], "nombre": usuario[1], "correo": usuario[2]}
                mostrar_codigo_y_continuar(usuario_dict, correo, password)
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
                btn_google,
                panel_codigo,
                mensaje_estado,
                btn_alternar,
                btn_recuperar,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=ft.Padding(10, 20, 10, 20),
    )

    def actualizar_ancho_responsive(e=None):
        ancho_disponible = min(340, max(190, (page.width or 420) - 40))
        for campo in (correo_input, password_input, nombre_input, telefono_input, fecha_input):
            campo.width = ancho_disponible
        btn_google.width = ancho_disponible

        if ancho_disponible < 310:
            texto_google.value = "Google"
            texto_google.size = 13
            img_google.width = 18
            img_google.height = 18
        else:
            texto_google.value = "Continuar con Google"
            texto_google.size = 13
            img_google.width = 20
            img_google.height = 20

        if panel_codigo.content is not None:
            panel_codigo.content.width = ancho_disponible
        form.padding = ft.Padding(10, 20, 10, 20)
        page.update()

    page.on_resized = actualizar_ancho_responsive

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

    actualizar_ancho_responsive()