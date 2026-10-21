import asyncio
import flet as ft
from utils import (
    abrir_selector_imagen,
    guardar_imagen_en_assets,
    mostrar_snackbar,
    configurar_retroceso,
    establecer_notificaciones,
    notificaciones_activas,
)
import database as db
import os
from views.login import codigo_sesion_valido

def perfil_usuario_view(page: ft.Page, usuario, go_back):
    # PANTALLA: perfil del usuario, datos personales, avisos y cambio de contraseña.
    # Este bloque limpia la vista anterior y configura el retroceso hacia Ajustes.
    """Vista para editar datos personales, cambiar contraseña e imagen de perfil"""
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "white"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )

    datos_usuario = db.obtener_usuario_por_id(usuario["id"])
    telefono_actual = datos_usuario.telefono if datos_usuario else ""
    fecha_actual = datos_usuario.fecha_nacimiento if datos_usuario else ""

    # DIÁLOGO: abre el formulario para editar los datos personales del usuario.
    def editar_datos_personales(e):
        # CAMPOS: datos que se muestran dentro del diálogo de edición.
        nombre_input = ft.TextField(label="Nombre", value=str(usuario.get("nombre", "")), width=300)
        correo_input = ft.TextField(label="Correo electrónico", value=str(usuario.get("correo", "")), width=300)
        telefono_input = ft.TextField(label="Teléfono", value=str(telefono_actual or ""), width=300)
        fecha_input = ft.TextField(label="Fecha de nacimiento", value=str(fecha_actual or ""), width=300)
        codigo_input = ft.TextField(label="Código de seguridad de esta sesión", password=True, width=300)
        mensaje = ft.Text("", size=12, color="red")

        # ACCIÓN: valida y guarda los datos personales en la base de datos.
        def guardar(e):
            nombre = nombre_input.value.strip()
            correo = correo_input.value.strip()
            if not nombre or not correo or "@" not in correo:
                mensaje.value = "⚠️ Escribe un nombre y un correo válido."
                page.update()
                return
            if not codigo_sesion_valido(page, codigo_input.value.strip()):
                mensaje.value = "🔐 El código de seguridad no es válido o ya expiró."
                page.update()
                return
            if db.verificar_correo_existe(correo) and correo != usuario.get("correo"):
                mensaje.value = "⚠️ Ese correo ya está registrado."
                page.update()
                return
            if not db.actualizar_perfil_usuario(
                usuario["id"], nombre, correo, telefono_input.value.strip(), fecha_input.value.strip()
            ):
                mensaje.value = "❌ No se pudieron actualizar tus datos."
                page.update()
                return
            usuario["nombre"] = nombre
            usuario["correo"] = correo
            codigo_input.value = ""
            dialogo.open = False
            page.update()
            mostrar_snackbar(page, "✅ Datos personales actualizados.", color="green")
            perfil_usuario_view(page, usuario, go_back)

        # ACCIÓN: cierra el diálogo sin guardar cambios.
        def cancelar(e):
            dialogo.open = False
            page.update()

        # DIÁLOGO: contiene los campos y los botones Cancelar/Guardar.
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("✏️ Editar datos personales"),
            content=ft.Column(
                [nombre_input, correo_input, telefono_input, fecha_input, codigo_input, mensaje],
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

    # BOTÓN: abre el diálogo para editar nombre, correo, teléfono y fecha.
    # BOTONES DE DATOS PERSONALES: abre y guarda la edición del perfil.
    btn_editar_perfil = ft.ElevatedButton(
        "✏️ Editar datos personales",
        on_click=editar_datos_personales,
        bgcolor="#168AAD",
        color="white",
        height=36,
        width=240,
    )

    # BLOQUE: controles y estado del flujo de cambio de contraseña.
    nueva_pass = ft.TextField(label="Nueva contraseña", password=True, can_reveal_password=True, width=300)
    confirm_pass = ft.TextField(label="Confirmar contraseña", password=True, can_reveal_password=True, width=300, visible=False)
    codigo_pass = ft.TextField(label="Código de seguridad de esta sesión", password=True, can_reveal_password=False, width=300)
    mensaje_pass = ft.Text("", size=12, color="red", visible=False)
    en_confirmacion = False
    nueva_pass_contenedor = ft.Container(
        content=nueva_pass,
        width=300,
    )
    confirm_pass_contenedor = ft.Container(
        content=confirm_pass,
        width=300,
        offset=ft.Offset(-1, 0),
        opacity=0,
    )

    def pasar_a_confirmacion(e):
        # ACCIÓN: valida la nueva contraseña y muestra el campo de confirmación.
        nonlocal en_confirmacion
        if not nueva_pass.value.strip():
            mensaje_pass.value = "Escribe una contraseña nueva para continuar 😊"
            mensaje_pass.color = "#D84315"
            mensaje_pass.visible = True
            page.update()
            return

        en_confirmacion = True
        nueva_pass_contenedor.opacity = 0
        nueva_pass_contenedor.offset = ft.Offset(0.5, 0)
        nueva_pass.disabled = True
        confirm_pass.visible = True
        mensaje_pass.visible = False
        btn_siguiente.visible = False
        btn_actualizar.visible = True
        btn_regresar.visible = True
        confirm_pass_contenedor.offset = ft.Offset(0, 0)
        confirm_pass_contenedor.opacity = 1
        page.update()
        page.run_task(ocultar_nueva_pass)

    async def ocultar_nueva_pass():
        await asyncio.sleep(0.65)
        nueva_pass_contenedor.visible = False
        confirm_pass.focus()
        page.update()

    def regresar_a_nueva_pass(e):
        # ACCIÓN: vuelve al primer paso del formulario de contraseña.
        nonlocal en_confirmacion
        en_confirmacion = False
        nueva_pass_contenedor.visible = True
        nueva_pass_contenedor.offset = ft.Offset(-0.5, 0)
        nueva_pass_contenedor.opacity = 0
        nueva_pass.disabled = False
        confirm_pass.visible = False
        confirm_pass.value = ""
        confirm_pass_contenedor.offset = ft.Offset(-1, 0)
        confirm_pass_contenedor.opacity = 0
        btn_siguiente.visible = True
        btn_actualizar.visible = False
        btn_regresar.visible = False
        mensaje_pass.visible = False
        page.update()
        nueva_pass_contenedor.offset = ft.Offset(0, 0)
        nueva_pass_contenedor.opacity = 1
        page.update()

    async def cambiar_pass(e):
        # ACCIÓN: valida ambas contraseñas y actualiza la contraseña del usuario.
        nonlocal en_confirmacion
        if not en_confirmacion:
            pasar_a_confirmacion(e)
            return
        if not confirm_pass.value.strip():
            mensaje_pass.value = "Confirma tu contraseña para continuar 😊"
            mensaje_pass.color = "#D84315"
            mensaje_pass.visible = True
            page.update()
            return
        if nueva_pass.value != confirm_pass.value:
            mensaje_pass.value = "Las contraseñas no coinciden. Revisa e inténtalo nuevamente 😊"
            mensaje_pass.color = "#D84315"
            mensaje_pass.visible = True
            page.update()
            return
        if not codigo_sesion_valido(page, codigo_pass.value.strip()):
            mensaje_pass.value = "🔐 El código de seguridad no es válido o ya expiró."
            mensaje_pass.color = "#D84315"
            mensaje_pass.visible = True
            page.update()
            return

        try:
            correo_usuario = usuario.get("correo", "")
            if db._supabase_activo() and not db.establecer_contraseña_auth(nueva_pass.value):
                raise RuntimeError("No se pudo actualizar la contraseña de Supabase Auth")
            if not db.actualizar_contraseña_por_correo(correo_usuario, nueva_pass.value):
                raise RuntimeError("No se encontró el usuario")
        except Exception as exc:
            mostrar_snackbar(page, f"❌ No se pudo actualizar la contraseña. {exc}", color="red")
            return

        mostrar_snackbar(page, "✅ Contraseña actualizada correctamente 😊", color="green", duracion=2500)
        await asyncio.sleep(0.06)

        def cerrar_dialog(e):
            try:
                dlg.open = False
            except Exception:
                pass

            nueva_pass.value = ""
            confirm_pass.value = ""
            codigo_pass.value = ""
            nonlocal en_confirmacion
            en_confirmacion = False
            nueva_pass.disabled = False
            nueva_pass_contenedor.visible = True
            nueva_pass_contenedor.offset = ft.Offset(0, 0)
            nueva_pass_contenedor.opacity = 1
            confirm_pass.visible = False
            confirm_pass_contenedor.offset = ft.Offset(-1, 0)
            confirm_pass_contenedor.opacity = 0
            btn_siguiente.visible = True
            btn_actualizar.visible = False
            btn_regresar.visible = False
            mensaje_pass.visible = False
            page.update()

        # DIÁLOGO: confirma que la contraseña fue actualizada correctamente.
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("🔐 Contraseña actualizada", size=18, weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Text("¡Listo! Tu contraseña se actualizó correctamente.", size=14),
                ft.Text("Recuerda guardarla en un lugar seguro. 😊", size=13, color="#555555")
            ], spacing=6, tight=True),
            actions=[
                # BOTÓN: cierra el aviso de contraseña actualizada.
                ft.ElevatedButton("Aceptar", on_click=cerrar_dialog, bgcolor="#040D4A", color="white")
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # BOTONES DE CONTRASEÑA: avanzan, actualizan y regresan dentro del cambio seguro.
    btn_siguiente = ft.ElevatedButton("Siguiente", on_click=pasar_a_confirmacion, width=150)
    btn_actualizar = ft.ElevatedButton(
        "Actualizar contraseña",
        on_click=lambda e: page.run_task(cambiar_pass, e),
        visible=False,
        width=210,
    )
    btn_regresar = ft.IconButton(
        icon=ft.Icons.ARROW_BACK,
        tooltip="Volver a editar la nueva contraseña",
        on_click=regresar_a_nueva_pass,
        visible=False,
    )

    bloque_contraseña = ft.Column(
        [
            ft.Divider(height=20),
            ft.Text("🔑 Cambiar Contraseña", size=16, weight=ft.FontWeight.BOLD),
            nueva_pass_contenedor,
            btn_siguiente,
            confirm_pass_contenedor,
            codigo_pass,
            mensaje_pass,
            ft.Row(
                [btn_regresar, btn_actualizar],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
        visible=True,
    )

    nueva_pass.on_submit = pasar_a_confirmacion
    
    def on_confirm_submit(e):
        page.run_task(cambiar_pass, e)
    
    confirm_pass.on_submit = on_confirm_submit

    # Imagen de perfil
    datos_usuario = db.obtener_usuario_por_id(usuario["id"])
    imagen_perfil = datos_usuario.imagen if datos_usuario else None
    perfil_imagen_control = ft.Container(width=48, height=48, bgcolor="#F3F3F3", border_radius=12)
    texto_imagen_perfil = "✏️ Editar imagen de perfil" if imagen_perfil else "🖼️ Agregar imagen a su perfil"

    if imagen_perfil:
        es_url_externa = isinstance(imagen_perfil, str) and imagen_perfil.startswith(("http://", "https://", "data:"))
        if es_url_externa:
            perfil_imagen_control.content = ft.Image(src=imagen_perfil, width=48, height=48, fit="cover")
        else:
            imagen_path = imagen_perfil if os.path.isabs(imagen_perfil) else os.path.join(os.getcwd(), imagen_perfil)
            if os.path.exists(imagen_path):
                perfil_imagen_control.content = ft.Image(src=imagen_perfil, width=48, height=48, fit="cover")

    async def guardar_imagen_perfil(ruta):
        imagen_rel = await asyncio.to_thread(guardar_imagen_en_assets, ruta, "perfil")
        if not imagen_rel:
            mostrar_snackbar(page, "❌ No se pudo preparar tu imagen de perfil.", color="red")
            return

        actualizado = await asyncio.to_thread(
            db.actualizar_imagen_usuario,
            usuario["id"],
            imagen_rel,
        )
        if not actualizado:
            mostrar_snackbar(page, "❌ No se pudo actualizar tu imagen de perfil.", color="red")
            return

        perfil_imagen_control.content = ft.Image(src=imagen_rel, width=48, height=48, fit="cover")
        texto_imagen_perfil_control.value = "✏️ Editar imagen de perfil"
        page.update()
        mostrar_snackbar(page, "✅ Imagen de perfil actualizada.", color="green")

    def procesar_imagen_perfil(ruta, image_data=None):
        if not ruta:
            return
        perfil_imagen_control.content = ft.Image(src=ruta, width=48, height=48, fit="cover")
        page.update()
        mostrar_snackbar(page, "⏳ Guardando imagen de perfil...", color="#040D4A")
        page.run_task(guardar_imagen_perfil, ruta)

    # Botón de imagen: abre el selector común para agregar o cambiar la foto del perfil.
    texto_imagen_perfil_control = ft.TextButton(
        texto_imagen_perfil,
        on_click=lambda e: abrir_selector_imagen(
            page,
            procesar_imagen_perfil,
            title="Seleccionar imagen de perfil",
            on_cancel=lambda: page.update(),
        ),
    )

    # Interruptor de avisos: tamaño, color y estado persistente de las notificaciones.
    notificaciones_switch = ft.Switch(
        value=notificaciones_activas(page),
        active_color="#168AAD",
        scale=0.55,   # Ajuste del tamaño y color del boton que activa 
        # y desactiva el boton de notificaciones
    )

    def cambiar_notificaciones(e):
        establecer_notificaciones(page, notificaciones_switch.value)
        mostrar_snackbar(
            page,
            "✅ Avisos activados." if notificaciones_switch.value else "🔕 Avisos desactivados.",
            color="green" if notificaciones_switch.value else "#555555",
        )

    notificaciones_switch.on_change = cambiar_notificaciones

    # Estructura visual del perfil con textos, campos y botones centrados.
    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=20),
                ft.Text("👤 Mi Perfil", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
                ft.Divider(height=10),
                ft.Text("👤 Datos Personales", size=16, weight=ft.FontWeight.BOLD),
                perfil_imagen_control,
                texto_imagen_perfil_control,
                ft.Text(f"📝 {usuario['nombre']}", size=16),
                ft.Text(f"📧 {usuario['correo']}", size=14, color="#666666"),
                btn_editar_perfil,
                ft.Divider(height=12),
                ft.Row(
                    [
                        ft.Text("🔔 Avisos de SmartStore", size=15, weight=ft.FontWeight.BOLD),
                        notificaciones_switch,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                ft.Text(
                    "Controla los avisos de inventario, tiendas y reservas.",
                    size=12,
                    color="#666666",
                    text_align=ft.TextAlign.CENTER,
                ),
                bloque_contraseña,
                ft.Container(height=10),
                # BOTÓN DE NAVEGACIÓN: regresa a Ajustes Adicionales.
                ft.ElevatedButton("↩️ Volver a Ajustes", on_click=lambda e: go_back(usuario), height=36, width=190),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=14,
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
