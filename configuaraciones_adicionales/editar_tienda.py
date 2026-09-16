import flet as ft

import database as db
from utils import abrir_selector_imagen, configurar_retroceso, guardar_imagen_en_assets, mostrar_snackbar


def editar_tienda_view(page: ft.Page, usuario, tienda_id, go_back):
    # PANTALLA/DIÁLOGO: edición de datos generales, logo y acciones de guardado.
    configurar_retroceso(page, go_back)
    page.clean()
    page.bgcolor = "white"
    # Mantener una base vacía en la página para que el flujo de cámara/galería
    # pueda restaurar el contenido de edición correctamente después de volver.
    page.add(ft.Container(height=0))

    tienda = db.obtener_tienda_por_id(tienda_id)
    if not tienda or tienda[4] != usuario["id"]:
        mostrar_snackbar(page, "❌ No tienes permiso para editar esta tienda.", color="red")
        go_back()
        return

    nombre_input = ft.TextField(label="Nombre de la tienda", value=str(tienda[1] or ""), width=300)
    whatsapp_input = ft.TextField(label="WhatsApp", value=str(tienda[2] or ""), width=300)
    direccion_input = ft.TextField(label="Dirección", value=str(tienda[5] or ""), width=300)
    tasa_input = ft.TextField(label="Tasa de cambio", value=str(tienda[3] or "36.5"), width=300)
    imagen_seleccionada = [tienda[7]]
    mensaje = ft.Text("", size=12, color="red")

    # ACCIÓN: recibe y prepara el nuevo logo seleccionado.
    def recibir_logo(ruta, image_data=None):
        if ruta:
            imagen_seleccionada[0] = guardar_imagen_en_assets(ruta, prefijo="tienda_editada") or ruta
            mensaje.value = "✅ Logo seleccionado"
            mensaje.color = "green"
            page.update()

    # ACCIÓN: abre el selector de imágenes para cambiar el logo.
    def seleccionar_logo(e):
        abrir_selector_imagen(
            page,
            recibir_logo,
            title="Seleccionar logo de tienda",
        )

    # ACCIÓN: marca el logo actual para eliminarlo al guardar.
    def quitar_logo(e):
        imagen_seleccionada[0] = None
        mensaje.value = "✅ El logo se quitará al guardar"
        mensaje.color = "green"
        page.update()

    # ACCIÓN: valida y guarda los cambios de la tienda.
    def guardar(e):
        nombre = nombre_input.value.strip()
        try:
            tasa = float(tasa_input.value.strip())
        except (AttributeError, ValueError):
            tasa = 0

        if not nombre or tasa <= 0:
            mensaje.value = "⚠️ El nombre y la tasa deben ser válidos."
            mensaje.color = "red"
            page.update()
            return

        if not db.actualizar_tienda(
            tienda_id,
            usuario["id"],
            nombre,
            whatsapp_input.value.strip(),
            tasa,
            direccion_input.value.strip(),
            imagen_seleccionada[0],
        ):
            mensaje.value = "❌ No se pudo actualizar la tienda."
            mensaje.color = "red"
            page.update()
            return

        dialogo.open = False
        page.update()
        mostrar_snackbar(page, "✅ Tienda actualizada correctamente.", color="green")
        go_back()

    # ACCIÓN: cierra el diálogo y vuelve sin guardar cambios.
    def cancelar(e):
        dialogo.open = False
        page.update()
        go_back()

    # CONTROLES: formulario de edición, selector de logo y botones de diálogo.
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("✏️ Editar tienda"),
        content=ft.Column(
            [
                nombre_input,
                whatsapp_input,
                direccion_input,
                tasa_input,
                ft.Row(
                    [
                        # BOTÓN: selecciona un nuevo logo desde cámara o galería.
                        ft.ElevatedButton("🖼️ Cambiar logo", on_click=seleccionar_logo),
                        # BOTÓN: elimina el logo cuando se guarden los cambios.
                        ft.TextButton("Quitar logo", on_click=quitar_logo),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                mensaje,
            ],
            tight=True,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        actions=[
            # BOTÓN: cancela la edición de la tienda.
            ft.TextButton("↩️ Cancelar", on_click=cancelar),
            # BOTÓN: guarda los datos modificados de la tienda.
            ft.ElevatedButton("💾 Guardar", on_click=guardar, bgcolor="#040D4A", color="white"),
        ],
    )
    page.overlay.append(dialogo)
    dialogo.open = True
    page.update()
