import threading

import flet as ft
import database as db
from utils import configurar_retroceso


def recuperar_view(page: ft.Page, go_to_menu):
    # PANTALLA: recuperación de contraseña y carga de datos para volver al login.
    # Pantalla para recuperar el acceso mediante los datos registrados.
    def volver_login_desde_retroceso():
        from views.login import login_view
        login_view(page, None, go_to_menu)

    configurar_retroceso(page, volver_login_desde_retroceso)
    page.clean()
    page.update()
    page.bgcolor = "white"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )

    correo_field = ft.TextField(label="Correo electrónico", width=300)
    codigo_sesion_field = ft.TextField(label="Código de sesión", width=300)
    codigo_correo_field = ft.TextField(label="Código recibido por correo", width=300, visible=False)
    nueva_contraseña_field = ft.TextField(label="Nueva contraseña", password=True, can_reveal_password=True, width=300, visible=False)
    confirmar_contraseña_field = ft.TextField(label="Confirmar nueva contraseña", password=True, can_reveal_password=True, width=300, visible=False)
    resultado_texto = ft.Text("", size=14)
    spinner_reconexion = ft.Container(
        visible=False,
        content=ft.ProgressRing(width=24, height=24, stroke_width=3, color="#4D5F7A"),
        width=28,
        height=28,
        alignment=ft.Alignment(0.5, 0.5),
        opacity=0,
    )
    btn_enviar_codigo = ft.ElevatedButton("Enviar código al correo")
    btn_validar_codigo_sesion = ft.ElevatedButton("Validar código de sesión")
    btn_validar_codigo_correo = ft.ElevatedButton("Validar código del correo", visible=False)
    btn_guardar_contrasena = ft.ElevatedButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.LOGIN),
                ft.Text("Guardar contraseña e iniciar sesión"),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
        ),
        visible=False,
    )
    controles_verificacion = ft.Column(
        [
            correo_field,
            ft.Text("Opción 1: código de sesión", weight=ft.FontWeight.BOLD),
            codigo_sesion_field,
            btn_validar_codigo_sesion,
            ft.Divider(),
            ft.Text("Opción 2: código por correo", weight=ft.FontWeight.BOLD),
            btn_enviar_codigo,
            codigo_correo_field,
            btn_validar_codigo_correo,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
    )
    datos_recuperados = {
        "correo": "",
        "correo_codigo_email": "",
        "metodo": "",
        "codigo_sesion": "",
        "codigo_verificado": False,
    }

    def mostrar_resultado(mensaje, color="red"):
        resultado_texto.value = str(mensaje)
        resultado_texto.color = color
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

    def mostrar_paso_contrasena(metodo, codigo):
        datos_recuperados["correo"] = (correo_field.value or "").strip()
        datos_recuperados["metodo"] = metodo
        datos_recuperados["codigo_sesion"] = codigo if metodo == "sesion" else ""
        datos_recuperados["codigo_verificado"] = True
        controles_verificacion.visible = False
        nueva_contraseña_field.visible = True
        confirmar_contraseña_field.visible = True
        btn_guardar_contrasena.visible = True
        mostrar_resultado("✅ Código validado. Crea una nueva contraseña para iniciar sesión. 😊", "green")
        page.update()

    def validar_codigo_sesion(e=None):
        correo = (correo_field.value or "").strip()
        codigo = (codigo_sesion_field.value or "").strip()
        if not correo or not codigo:
            mostrar_resultado("Escribe el correo de la cuenta y su código de sesión. 😊", "red")
            return
        if not db._supabase_activo():
            mostrar_resultado("⚠️ La recuperación no está disponible porque Supabase no está activo.", "red")
            return
        try:
            if not db.validar_codigo_sesion_recuperacion_auth(correo, codigo):
                mostrar_resultado("❌ El correo o el código de sesión no coincide.", "red")
                return
        except RuntimeError as exc:
            mostrar_resultado(f"⚠️ No se pudo validar el código de sesión: {exc}", "red")
            return
        mostrar_paso_contrasena("sesion", codigo)

    def enviar_codigo_correo(e=None):
        correo = (correo_field.value or "").strip()
        if not correo:
            mostrar_resultado("Escribe el correo donde quieres recibir el código. 😊", "red")
            return
        if not db._supabase_activo():
            mostrar_resultado("⚠️ La recuperación no está disponible porque Supabase no está activo.", "red")
            return
        mostrar_spinner_temporal()
        try:
            if not db.solicitar_codigo_recuperacion_auth(correo):
                mostrar_resultado("⚠️ No se pudo iniciar la recuperación de contraseña.", "red")
                return
        except RuntimeError as exc:
            ocultar_spinner_reconexion()
            detalle = str(exc).lower()
            if "over_email_send_rate_limit" in detalle or "email rate limit" in detalle or "http 429" in detalle:
                mensaje = "Supabase limitó temporalmente los correos. Espera un minuto antes de pedir otro código."
            elif "smtp" in detalle or "email_provider" in detalle:
                mensaje = "Supabase no pudo enviar el correo. Revisa la configuración del proveedor de email."
            else:
                mensaje = f"No se pudo enviar el código: {exc}"
            mostrar_resultado(f"⚠️ {mensaje}", "red")
            return

        datos_recuperados["correo_codigo_email"] = correo
        codigo_correo_field.value = ""
        codigo_correo_field.visible = True
        btn_validar_codigo_correo.visible = True
        mostrar_resultado("✅ Si el correo está registrado, recibirás el código. Revisa también spam.", "green")
        page.update()

    def validar_codigo_correo(e=None):
        correo = (correo_field.value or "").strip()
        correo_enviado = datos_recuperados["correo_codigo_email"]
        codigo = (codigo_correo_field.value or "").strip()
        if not correo_enviado or correo.casefold() != correo_enviado.casefold():
            mostrar_resultado("Envía el código al correo que escribiste antes de validarlo. 😊", "red")
            return
        if not codigo:
            mostrar_resultado("Escribe el código que recibiste por correo. 😊", "red")
            return
        try:
            if not db.validar_codigo_recuperacion_auth(correo_enviado, codigo):
                mostrar_resultado("❌ El código del correo no coincide o ya venció.", "red")
                return
        except RuntimeError as exc:
            mostrar_resultado(f"⚠️ No se pudo validar el código del correo: {exc}", "red")
            return
        mostrar_paso_contrasena("correo", "")

    def guardar_contrasena_e_iniciar_sesion(e):
        correo = datos_recuperados["correo"]
        nueva_contraseña = nueva_contraseña_field.value or ""
        confirmar_contraseña = confirmar_contraseña_field.value or ""
        if not datos_recuperados["codigo_verificado"]:
            mostrar_resultado("Primero valida el código de recuperación. 😊", "red")
            return
        if not nueva_contraseña:
            mostrar_resultado("Escribe una nueva contraseña. 😊", "red")
            return
        if len(nueva_contraseña) < 6:
            mostrar_resultado("La contraseña debe tener al menos 6 caracteres. 😊", "red")
            return
        if nueva_contraseña != confirmar_contraseña:
            mostrar_resultado("❌ Las contraseñas no coinciden. 😊", "red")
            return
        try:
            if datos_recuperados["metodo"] == "sesion":
                actualizada = db.cambiar_contrasena_con_codigo_sesion_auth(
                    correo,
                    datos_recuperados["codigo_sesion"],
                    nueva_contraseña,
                )
            else:
                actualizada = db.establecer_contraseña_auth(nueva_contraseña)
            if not actualizada:
                mostrar_resultado("❌ Supabase no pudo cambiar la contraseña. Solicita un código nuevo e inténtalo otra vez.", "red")
                return
        except RuntimeError as exc:
            mostrar_resultado(f"⚠️ No se pudo cambiar la contraseña: {exc}", "red")
            return
        from views.login import login_view
        login_view(page, None, go_to_menu, correo, nueva_contraseña)

    btn_enviar_codigo.on_click = enviar_codigo_correo
    btn_validar_codigo_sesion.on_click = validar_codigo_sesion
    btn_validar_codigo_correo.on_click = validar_codigo_correo
    btn_guardar_contrasena.on_click = guardar_contrasena_e_iniciar_sesion
    codigo_sesion_field.on_submit = validar_codigo_sesion
    codigo_correo_field.on_submit = validar_codigo_correo

    def volver_login(e):
        from views.login import login_view
        login_view(page, None, go_to_menu)

    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("Recuperar Contraseña", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
                ft.Text(
                    "Valida uno de los dos códigos para crear una contraseña nueva 😊",
                    size=14,
                    color="#555555",
                ),
                controles_verificacion,
                nueva_contraseña_field,
                confirmar_contraseña_field,
                btn_guardar_contrasena,
                resultado_texto,
                ft.ElevatedButton("↩️ Volver al Login", on_click=volver_login),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
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
