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
    codigo_field = ft.TextField(label="Código de seguridad de tu sesión", width=300, visible=False)
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
    # BOTÓN: busca los datos asociados al correo introducido.
    # BOTONES DE RECUPERACIÓN: buscan la cuenta y regresan al inicio de sesión.
    ancho_btn_buscar = 220
    btn_buscar = ft.ElevatedButton("Buscar mi contraseña", on_click=lambda e: buscar_contraseña(), width=ancho_btn_buscar)
    # btn_verificar_whatsapp = ft.ElevatedButton("Verificar por número", visible=True, on_click=lambda e: abrir_verificacion_whatsapp())
    # btn_enviar_codigo = ft.ElevatedButton("Enviar código", visible=False, on_click=lambda e: verificar_whatsapp())
    # btn_abrir_whatsapp = ft.ElevatedButton("🔗 Abrir WhatsApp", visible=False, on_click=lambda e: abrir_whatsapp_manual())
    btn_validar_codigo = ft.ElevatedButton("Validar código", visible=False)
    # BOTÓN: devuelve al login los datos recuperados.
    btn_inyectar_datos = ft.ElevatedButton("Guardar nueva contraseña", visible=False)

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
    datos_recuperados = {"correo": ""}
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
            btn_inyectar_datos.visible = False
            # panel_verificacion.visible = False
            # codigo_field.visible = False
            # btn_validar_codigo.visible = False
            page.update()
            return

        try:
            db.verificar_conexion_remota()
            mostrar_spinner_temporal()
        except RuntimeError as exc:
            ocultar_spinner_reconexion()
            if "desactivado" in str(exc).lower():
                mostrar_resultado("⚙️ Supabase está desactivado. Cierra y vuelve a abrir la app con SMARTSTORE_USAR_SUPABASE=1.", "red")
            else:
                mostrar_resultado("⚠️ No se pudo conectar con Supabase. Revisa la conexión y las políticas RLS.", "red")
            datos_recuperados["correo"] = ""
            btn_inyectar_datos.visible = False
            page.update()
            return

        try:
            usuario = db.obtener_usuario_por_correo(correo)
        except RuntimeError:
            ocultar_spinner_reconexion()
            mostrar_resultado("⚠️ No se pudo consultar la cuenta. Revisa la conexión y las políticas RLS.", "red")
            datos_recuperados["correo"] = ""
            btn_inyectar_datos.visible = False
            page.update()
            return

        if not usuario:
            mostrar_resultado("❌ Ese correo no está registrado. Revisa los datos o crea una cuenta nueva 😊", "red")
            datos_recuperados["correo"] = ""
            btn_inyectar_datos.visible = False
            # panel_verificacion.visible = False
            # codigo_field.visible = False
            # btn_validar_codigo.visible = False
            page.update()
            return

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
        btn_inyectar_datos.visible = False
        datos_recuperados["correo"] = correo_guardado
        codigo_field.visible = True
        btn_validar_codigo.visible = True
        mostrar_resultado("✅ Cuenta encontrada. Introduce el código que recibiste al iniciar sesión 😊", "green")
        page.update()

    def validar_codigo(e=None):
        codigo = (codigo_field.value or "").strip()
        correo = datos_recuperados["correo"]
        if not correo:
            mostrar_resultado("Primero verifica tu correo electrónico. 😊", "red")
            return
        if not db.validar_codigo_sesion(correo, codigo):
            mostrar_resultado("❌ El código no coincide. Revisa e inténtalo nuevamente 😊", "red")
            return
        try:
            db.invalidar_codigo_sesion_bd(correo)
        except RuntimeError:
            mostrar_resultado("⚠️ No se pudo invalidar el código. Intenta nuevamente. 😊", "red")
            return
        codigo_field.visible = False
        btn_validar_codigo.visible = False
        nueva_contraseña_field.visible = True
        confirmar_contraseña_field.visible = True
        btn_inyectar_datos.visible = True
        mostrar_resultado("✅ Código validado. Escribe tu nueva contraseña. 😊", "green")
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
        correo = datos_recuperados["correo"]
        nueva_contraseña = nueva_contraseña_field.value or ""
        confirmar_contraseña = confirmar_contraseña_field.value or ""
        if not nueva_contraseña:
            mostrar_resultado("Escribe una nueva contraseña. 😊", "red")
            return
        if nueva_contraseña != confirmar_contraseña:
            mostrar_resultado("❌ Las contraseñas no coinciden. 😊", "red")
            return
        try:
            if not db.actualizar_contraseña_por_correo(correo, nueva_contraseña):
                mostrar_resultado("❌ No se pudo actualizar la contraseña.", "red")
                return
            db.invalidar_codigo_sesion_bd(correo)
        except RuntimeError:
            mostrar_resultado("⚠️ No hay conexión con la base de datos. Intenta nuevamente. 😊", "red")
            return
        from views.login import login_view
        login_view(page, None, go_to_menu, correo, nueva_contraseña)

    btn_inyectar_datos.on_click = inyectar_datos_en_login
    btn_validar_codigo.on_click = validar_codigo
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
                codigo_field,
                btn_validar_codigo,
                nueva_contraseña_field,
                confirmar_contraseña_field,
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
