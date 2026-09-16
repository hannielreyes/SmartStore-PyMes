import random
import threading
from urllib.parse import quote

import flet as ft
import database as db
from utils import configurar_retroceso, normalizar_whatsapp


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
    telefono_verificacion_field = ft.TextField(label="Número de teléfono / WhatsApp", width=300, visible=False)
    codigo_field = ft.TextField(label="Código recibido por WhatsApp", width=300, visible=False)
    resultado_texto = ft.Text("", size=14)
    spinner_reconexion = ft.Container(
        visible=False,
        content=ft.ProgressRing(width=24, height=24, stroke_width=3, color="#4D5F7A"),
        width=28,
        height=28,
        alignment=ft.Alignment(0.5, 0.5),
        opacity=0,
    )
    # BOTÓN: busca los datos asociados al correo introducido.
    btn_buscar = ft.ElevatedButton("Buscar mi contraseña", on_click=lambda e: buscar_contraseña())
    # btn_verificar_whatsapp = ft.ElevatedButton("Verificar por número", visible=True, on_click=lambda e: abrir_verificacion_whatsapp())
    # btn_enviar_codigo = ft.ElevatedButton("Enviar código", visible=False, on_click=lambda e: verificar_whatsapp())
    # btn_abrir_whatsapp = ft.ElevatedButton("🔗 Abrir WhatsApp", visible=False, on_click=lambda e: abrir_whatsapp_manual())
    # btn_validar_codigo = ft.ElevatedButton("Validar código", visible=False, on_click=lambda e: validar_codigo())
    # BOTÓN: devuelve al login los datos recuperados.
    btn_inyectar_datos = ft.ElevatedButton("Usar estos datos para iniciar sesión 😊", visible=False)

    # def volver_a_busqueda_por_correo(e=None):
    #     correo_field.visible = True
    #     btn_buscar.visible = True
    #     btn_verificar_whatsapp.visible = True
    #     btn_inyectar_datos.visible = False
    #     panel_verificacion.visible = False
    #     telefono_verificacion_field.visible = False
    #     codigo_field.visible = False
    #     btn_validar_codigo.visible = False
    #     btn_enviar_codigo.visible = False
    #     mostrar_resultado("Escribe tu correo para buscar tu cuenta y luego puedes continuar 😊", "green")
    #     page.update()

    # panel_verificacion = ft.Column(
    #     [
    #         telefono_verificacion_field,
    #         btn_enviar_codigo,
    #         btn_abrir_whatsapp,
    #         codigo_field,
    #         btn_validar_codigo,
    #         ft.ElevatedButton("← Volver al correo", on_click=volver_a_busqueda_por_correo),
    #     ],
    #     spacing=12,
    #     visible=False,
    # )
    datos_recuperados = {"correo": "", "contraseña": ""}
    # codigo_generado = ""
    # numero_registrado = ""
    # url_whatsapp = ""

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

    def buscar_contraseña(e=None):
        correo = (correo_field.value or "").strip()
        if not correo:
            mostrar_resultado("Escribe tu correo para verificar tu cuenta. 😊", "red")
            datos_recuperados["correo"] = ""
            datos_recuperados["contraseña"] = ""
            btn_inyectar_datos.visible = False
            # panel_verificacion.visible = False
            # codigo_field.visible = False
            # btn_validar_codigo.visible = False
            page.update()
            return

        try:
            db.verificar_conexion_remota()
            mostrar_spinner_temporal()
        except RuntimeError:
            mostrar_spinner_reconexion()
            mostrar_resultado(
                "⚠️ Parece que no tienes conexión a internet 😅 Verifica tu red e intenta nuevamente cuando estés conectado 😊",
                "red",
            )
            datos_recuperados["correo"] = ""
            datos_recuperados["contraseña"] = ""
            btn_inyectar_datos.visible = False
            page.update()
            return

        try:
            usuario = db.obtener_usuario_por_correo(correo)
        except RuntimeError:
            mostrar_spinner_reconexion()
            mostrar_resultado(
                "⚠️ Parece que no tienes conexión a internet 😅 Verifica tu red e intenta nuevamente cuando estés conectado 😊",
                "red",
            )
            datos_recuperados["correo"] = ""
            datos_recuperados["contraseña"] = ""
            btn_inyectar_datos.visible = False
            page.update()
            return

        if not usuario:
            mostrar_resultado("❌ Ese correo no está registrado. Revisa los datos o crea una cuenta nueva 😊", "red")
            datos_recuperados["correo"] = ""
            datos_recuperados["contraseña"] = ""
            btn_inyectar_datos.visible = False
            # panel_verificacion.visible = False
            # codigo_field.visible = False
            # btn_validar_codigo.visible = False
            page.update()
            return

        contraseña = usuario[5]
        correo_guardado = usuario[2]
        # telefono_registrado = usuario[3]
        # if not telefono_registrado:
        #     mostrar_resultado("❌ No encontramos un WhatsApp asociado a esta cuenta. Contacta con soporte para recuperar el acceso 😊", "red")
        #     datos_recuperados["correo"] = ""
        #     datos_recuperados["contraseña"] = ""
        #     btn_inyectar_datos.visible = False
        #     panel_verificacion.visible = False
        #     codigo_field.visible = False
        #     btn_validar_codigo.visible = False
        #     page.update()
        #     return

        # numero_registrado = str(telefono_registrado)
        # panel_verificacion.visible = False
        # telefono_verificacion_field.visible = False
        # codigo_field.visible = False
        # btn_validar_codigo.visible = False
        btn_inyectar_datos.visible = True
        datos_recuperados["correo"] = correo_guardado
        datos_recuperados["contraseña"] = contraseña
        mostrar_resultado(f"✅ Cuenta encontrada. Tu contraseña es: {contraseña}. 😊", "green")
        page.update()

    # def abrir_verificacion_whatsapp(e=None):
    #     correo_field.visible = False
    #     btn_buscar.visible = False
    #     btn_verificar_whatsapp.visible = False
    #     btn_inyectar_datos.visible = False
    #     panel_verificacion.visible = True
    #     telefono_verificacion_field.visible = True
    #     telefono_verificacion_field.value = ""
    #     codigo_field.visible = False
    #     btn_validar_codigo.visible = False
    #     btn_enviar_codigo.visible = True
    #     mostrar_resultado("Escribe el número asociado a tu cuenta para enviar el código de verificación 😊", "green")
    #     page.update()
    #
    # def abrir_whatsapp_manual(e=None):
    #     nonlocal url_whatsapp
    #     if url_whatsapp:
    #         try:
    #             page.launch_url(url_whatsapp)
    #         except Exception as ex:
    #             mostrar_resultado(f"⚠️ Error al abrir: {str(ex)}", "red")
    #
    # def verificar_whatsapp(e=None):
    #     nonlocal codigo_generado, url_whatsapp
    #
    #     numero_ingresado = (telefono_verificacion_field.value or "").strip()
    #     if not numero_ingresado:
    #         mostrar_resultado("Escribe tu número de WhatsApp para continuar 😊", "red")
    #         return
    #
    #     numero_ingresado_normalizado = normalizar_whatsapp(numero_ingresado)
    #     if not numero_ingresado_normalizado:
    #         mostrar_resultado("⚠️ Ese número no es válido. Debe verse como 50588888888 😊", "red")
    #         return
    #
    #     usuario = db.obtener_usuario_por_telefono(numero_ingresado_normalizado)
    #     if not usuario:
    #         mostrar_resultado("❌ Ese número no está registrado. Verifica la información e inténtalo nuevamente 😊", "red")
    #         return
    #
    #     numero_registrado = str(usuario[3]) if usuario[3] else numero_ingresado_normalizado
    #     numero_registrado_normalizado = normalizar_whatsapp(numero_registrado)
    #     if not numero_registrado_normalizado:
    #         mostrar_resultado("❌ Ese número nunca fue registrado en esta cuenta. Verifica la información e inténtalo nuevamente 😊", "red")
    #         return
    #
    #     if numero_ingresado_normalizado != numero_registrado_normalizado:
    #         mostrar_resultado("❌ Ese número no coincide con el WhatsApp registrado para esta cuenta 😊", "red")
    #         return
    #
    #     codigo_generado = str(random.randint(100000, 999999))
    #     mensaje = f"Tu código de verificación SmartStore es: {codigo_generado}. No lo compartas con nadie."
    #     url_whatsapp = f"https://wa.me/{numero_registrado_normalizado}?text={quote(mensaje)}"
    #     
    #     try:
    #         page.launch_url(url_whatsapp)
    #     except Exception:
    #         pass
    #
    #     codigo_field.value = ""
    #     codigo_field.visible = True
    #     btn_validar_codigo.visible = True
    #     btn_abrir_whatsapp.visible = True
    #     mostrar_resultado(f"✅ Código: {codigo_generado}", "green")
    #     page.update()
    #
    # def validar_codigo(e=None):
    #     codigo = (codigo_field.value or "").strip()
    #     if not codigo_generado:
    #         mostrar_resultado("Primero genera el código de verificación por WhatsApp 😊", "red")
    #         return
    #     if codigo != codigo_generado:
    #         mostrar_resultado("❌ El código ingresado no coincide. Revisa el número o el código y vuelve a intentarlo 😊", "red")
    #         return
    #
    #     mostrar_resultado("✅ Código verificado correctamente. Puedes usar estos datos para iniciar sesión 😊", "green")
    #     btn_inyectar_datos.visible = True
    #     page.update()

    def inyectar_datos_en_login(e):
        from views.login import login_view
        login_view(
            page,
            None,
            go_to_menu,
            datos_recuperados["correo"],
            datos_recuperados["contraseña"],
        )

    btn_inyectar_datos.on_click = inyectar_datos_en_login
    correo_field.on_submit = buscar_contraseña
    # telefono_verificacion_field.on_submit = verificar_whatsapp
    # codigo_field.on_submit = validar_codigo

    def volver_login(e):
        from views.login import login_view
        login_view(page, None, go_to_menu)

    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("Recuperar Contraseña", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
                ft.Text("Escribe tu correo para buscar tu cuenta y luego puedes continuar 😊", size=14, color="#555555"),
                correo_field,
                btn_buscar,
                # btn_verificar_whatsapp,
                btn_inyectar_datos,
                # panel_verificacion,
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
