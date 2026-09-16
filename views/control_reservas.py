import flet as ft
import database as db
from utils import configurar_retroceso, mostrar_snackbar, imagen_disponible
from configuaraciones_adicionales.editar_tienda import editar_tienda_view
from datetime import datetime
import threading
import time
import os

def control_reservas_view(page: ft.Page, go_to_perfil, go_to_menu, tienda_id, mostrar_billetera=True, mostrar_entregas=True):
    # PANTALLA: panel de vendedor, billetera, reservas e historial de entregas.
    configurar_retroceso(page, go_to_perfil)
    page.clean()
    page.bgcolor = "white"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )

    tienda = db.obtener_tienda_por_id(tienda_id)
    if not tienda:
        page.add(ft.Text("❌ No encontramos la tienda. Revisa la información e inténtalo nuevamente 😊", width=320, text_align=ft.TextAlign.CENTER))
        return

    logo_tienda = tienda[7] if len(tienda) > 7 else None
    logo_control = ft.Container(width=120, height=120, bgcolor="#F3F3F3", border_radius=14)
    if logo_tienda:
        if imagen_disponible(logo_tienda):
            logo_control = ft.Container(
                content=ft.Image(src=logo_tienda, width=120, height=120, fit="cover"),
                width=120,
                height=120,
                border_radius=14,
                bgcolor="#F3F3F3",
            )

    usuario_id = tienda[4]
    paypal_email = db.obtener_paypal_email(usuario_id)

    def editar_tienda(e):
        # ACCIÓN: abre la pantalla de edición de la tienda actual.
        editar_tienda_view(
            page,
            {"id": usuario_id},
            tienda_id,
            lambda: control_reservas_view(
                page,
                go_to_perfil,
                go_to_menu,
                tienda_id,
                mostrar_billetera,
                mostrar_entregas,
            ),
        )

    if not paypal_email and mostrar_billetera:
        content = ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=40),
                    ft.Text("💰 Billetera de la tienda", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
                    ft.Divider(height=10),
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text("💳 Vincula tu cuenta PayPal", size=20, weight=ft.FontWeight.BOLD, color="#040D4A"),
                                ft.Divider(height=10),
                                ft.Text("Para gestionar el dinero de tu tienda, necesitas vincular una cuenta de PayPal 😊", size=15),
                                ft.Text("Esto te permitirá recibir los pagos de tus clientes directamente en tu cuenta de PayPal y retirar el dinero a tu banco cuando lo necesites 😊", size=15),
                                ft.Divider(height=10),
                                ft.Text("👉 Ve a 'Mi Perfil' y selecciona la opción 'Vincular PayPal' para completar el proceso.", size=15, weight=ft.FontWeight.BOLD),
                                ft.Divider(height=10),
                                ft.Text("🔄 Una vez vinculada, podrás ver tu saldo y gestionar tus entregas desde aquí.", size=14, color="#555555"),
                            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=25,
                            bgcolor=ft.Colors.WHITE,
                            border_radius=15,
                            width=400,
                        )
                    ),
                    ft.Divider(height=20),
                    ft.ElevatedButton(
                        "🔙 Volver a Mi Perfil",
                        on_click=lambda e: go_to_perfil()
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
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
        page.update()
        return

    saldo_actual = db.obtener_saldo_tienda(tienda_id) if mostrar_billetera else 0
    saldo_text = ft.Text(f"Billetera: C${saldo_actual:.2f}", size=18, weight=ft.FontWeight.BOLD, color="#040D4A")

    billetera_card = ft.Card(
        content=ft.Container(
            content=ft.Column([
                saldo_text,
            ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
            bgcolor=ft.Colors.WHITE,
            border_radius=15,
            width=400,
        )
    )

    # CONTROLES: lista de pedidos pendientes y botones de cambio de estado.
    lista_por_entregar = ft.Column(spacing=10, scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True), height=250)

    def cargar_por_entregar():
        # CARGA: actualiza las reservas pendientes de entrega.
        lista_por_entregar.controls.clear()
        reservas = db.obtener_reservas_por_tienda(tienda_id)

        if not reservas:
            lista_por_entregar.controls.append(
                ft.Text("✅ No hay reservas pendientes de entrega por ahora.", size=14, color="green")
            )
            page.update()
            return

        for r in reservas:
            rid, producto, cantidad, total, usuario_nombre, fecha_compra, estado = r

            def hacer_entregar(id_reserva):
                # ACCIÓN: prepara el diálogo de confirmación de entrega.
                def confirmar_entrega(e):
                    def entregar(e):
                        dlg.open = False
                        page.update()
                        if db.marcar_como_entregada(id_reserva):
                            cargar_por_entregar()
                            cargar_entregadas()
                            mostrar_snackbar(page, "✅ Pedido enviado al historial de entregas.", color="green")
                        else:
                            mostrar_snackbar(
                                page,
                                "❌ No se pudo marcar la entrega. Verifica que el pago esté confirmado.",
                                color="red",
                            )
                        page.update()

                    def cancelar(e):
                        dlg.open = False
                        page.update()

                    dlg = ft.AlertDialog(
                        # DIÁLOGO: confirma que el pedido fue entregado al cliente.
                        modal=True,
                        title=ft.Text("✅ Confirmar entrega"),
                        content=ft.Text("¿Confirmar que el producto fue entregado al cliente? 😊"),
                        actions=[
                            ft.TextButton("↩️ Cancelar", on_click=cancelar),
                            ft.ElevatedButton(
                                "✅ Marcar como Entregada",
                                on_click=entregar,
                                bgcolor="green",
                                color="white",
                            ),
                        ],
                    )
                    page.overlay.append(dlg)
                    dlg.open = True
                    page.update()
                return confirmar_entrega

            def cambiar_estado(id_reserva, estado_nuevo, mensaje_exito):
                def ejecutar(e):
                    if db.cambiar_estado_reserva(id_reserva, estado_nuevo):
                        mostrar_snackbar(page, mensaje_exito, color="green")
                        cargar_por_entregar()
                    else:
                        mostrar_snackbar(page, "❌ No se pudo actualizar el estado del pedido.", color="red")
                return ejecutar

            acciones_estado = []
            if estado == "Pagado":
                acciones_estado.append(
                    ft.ElevatedButton(
                        "📦 Marcar como Preparando",
                        on_click=cambiar_estado(id_reserva=rid, estado_nuevo="Preparando", mensaje_exito="✅ Pedido marcado como preparando."),
                        bgcolor="#168AAD",
                        color="white",
                    )
                )
            elif estado == "Preparando":
                acciones_estado.append(
                    ft.ElevatedButton(
                        "✅ Listo para entregar",
                        on_click=cambiar_estado(id_reserva=rid, estado_nuevo="Listo para entregar", mensaje_exito="✅ Pedido listo para entregar."),
                        bgcolor="#168AAD",
                        color="white",
                    )
                )

            card = ft.Container(
                content=ft.Column([
                    ft.Text(f"#{rid} - {producto}", size=16, weight=ft.FontWeight.BOLD),
                    ft.Text(f"👤 Cliente: {usuario_nombre}", size=13, color="#555555"),
                    ft.Text(f"📦 Cantidad: {cantidad}  |  💰 Total: C${total:.2f}", size=13),
                    ft.Text(f"📅 Compra: {fecha_compra}", size=11, color="gray"),
                    ft.Text(
                        "⏳ Pendiente de pago: el cliente debe completar PayPal."
                        if estado == "Reservado"
                        else "📦 Pago confirmado: preparando pedido."
                        if estado == "Pagado"
                        else "🔧 Pedido en preparación."
                        if estado == "Preparando"
                        else "✅ Listo para entregar.",
                        size=12,
                        color="#E65100" if estado == "Reservado" else "green",
                    ),
                    *acciones_estado,
                    ft.ElevatedButton(
                        "✅ Marcar como Entregada",
                        on_click=hacer_entregar(rid),
                        bgcolor="#EFA520",
                        color="white",
                    ) if estado == "Listo para entregar" else ft.Container(),
                ], spacing=5),
                bgcolor=ft.Colors.WHITE,
                border_radius=15,
                padding=12,
                width=350,
            )
            lista_por_entregar.controls.append(card)
        page.update()

    # Historial visual de pedidos que ya fueron entregados al cliente.
    lista_entregadas = ft.Column(spacing=10, scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True), height=200)

    def cargar_entregadas():
        lista_entregadas.controls.clear()
        entregadas = db.obtener_entregas_completadas_por_tienda(tienda_id)

        if not entregadas:
            lista_entregadas.controls.append(
                ft.Text("📭 Todavía no hay entregas completadas en esta tienda.", size=14, color="gray")
            )
            page.update()
            return

        for e in entregadas:
            rid, producto, cantidad, total, usuario_nombre, fecha_entrega = e

            card = ft.Container(
                content=ft.Column([
                    ft.Text(f"#{rid} - {producto}", size=15, weight=ft.FontWeight.BOLD),
                    ft.Text(f"👤 Cliente: {usuario_nombre}", size=13, color="#555555"),
                    ft.Text(f"📦 Cantidad: {cantidad}  |  💰 Total: C${total:.2f}", size=13),
                    ft.Text(f"✅ Entregado: {fecha_entrega}", size=11, color="green"),
                ], spacing=3),
                bgcolor=ft.Colors.WHITE,
                border_radius=15,
                padding=12,
                width=350,
            )
            lista_entregadas.controls.append(card)
        page.update()

    def actualizar_saldo_periodicamente():
        def tarea():
            while True:
                time.sleep(5)
                try:
                    nuevo_saldo = db.obtener_saldo_tienda(tienda_id)
                    saldo_text.value = f"C${nuevo_saldo:.2f}"
                    page.update()
                except:
                    pass
        threading.Thread(target=tarea, daemon=True).start()

    def confirmar_eliminacion_tienda(e):
        saldo = db.obtener_saldo_tienda(tienda_id) or 0

        def volver(e):
            dialogo.open = False
            page.update()

        def ir_a_billetera(e):
            dialogo.open = False
            page.update()
            go_to_perfil()

        def eliminar(e):
            try:
                eliminado, mensaje = db.eliminar_tienda(tienda_id, tienda[4])
                if not eliminado:
                    dialogo.open = False
                    page.update()
                    mostrar_snackbar(page, f"⚠️ {mensaje}", color="orange")
                    return
                dialogo.open = False
                page.update()
                mostrar_snackbar(page, f"✅ {mensaje} 😊", color="green")
                go_to_menu()
            except Exception as exc:
                mostrar_snackbar(page, f"❌ No se pudo eliminar la tienda: {exc}", color="red")

        if saldo > 0:
            dialogo = ft.AlertDialog(
                modal=True,
                title=ft.Text("💰 Primero retira tu saldo", size=18, weight=ft.FontWeight.BOLD, color="#040D4A"),
                content=ft.Text(
                    f"La tienda '{tienda[1]}' todavía tiene C$ {saldo:,.2f} en su billetera. "
                    "La billetera no es lo que se eliminará, pero debes retirar ese dinero antes de eliminar la tienda para no perderlo. 😊",
                    size=14,
                    color="#555555",
                ),
                actions=[ft.TextButton("↩️ Volver", on_click=volver), ft.ElevatedButton("💰 Ir a Mi Perfil", on_click=ir_a_billetera, bgcolor="#EFD320", color="white")],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        else:
            dialogo = ft.AlertDialog(
                modal=True,
                title=ft.Text("🗑️ ¿Eliminar esta tienda?", size=18, weight=ft.FontWeight.BOLD, color="#040D4A"),
                content=ft.Text(
                    f"Se eliminarán '{tienda[1]}' y sus productos, reservas e información relacionada. La acción no se puede deshacer. 😔",
                    size=14,
                    color="#555555",
                ),
                actions=[ft.TextButton("↩️ Volver", on_click=volver), ft.ElevatedButton("🗑️ Sí, eliminar", on_click=eliminar, bgcolor="#D84315", color="white")],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    if mostrar_billetera:
        actualizar_saldo_periodicamente()

    contenido_principal = [
        ft.Container(height=40),
        ft.Text(
            f"🏪 Tienda - {tienda[1]}" if not mostrar_billetera else f"💰 Billetera de la tienda - {tienda[1]}",
            size=28,
            weight=ft.FontWeight.BOLD,
            color="#040D4A",
        ),
        logo_control,
        ft.Text(f"Direccion: {tienda[5] or 'No indicada'}", size=14, color="#555555"),
        ft.Text(f"WhatsApp: {tienda[2] or 'No indicado'}", size=14, color="#555555"),
        ft.Text(f"Tasa de cambio: {tienda[3] or 'No indicada'}", size=14, color="#555555"),
    ]
    if not mostrar_billetera:
        contenido_principal.append(ft.ElevatedButton("✏️ Editar tienda", on_click=editar_tienda, bgcolor="#168AAD", color="white"))
    if mostrar_billetera:
        contenido_principal.extend([ft.Divider(height=10), billetera_card])
    if mostrar_entregas:
        contenido_principal.extend([
            ft.Divider(height=10),
            ft.Text("📋 Reservas por Entregar", size=18, weight=ft.FontWeight.BOLD, color="#040D4A"),
            lista_por_entregar,
            ft.Divider(height=10),
            ft.Text("✅ Historial de Entregas Completadas", size=18, weight=ft.FontWeight.BOLD, color="#040D4A"),
            lista_entregadas,
        ])
    contenido_principal.append(ft.Divider(height=10))
    if not mostrar_billetera:
        contenido_principal.append(
            ft.ElevatedButton(
                "🗑️ Eliminar tienda",
                on_click=confirmar_eliminacion_tienda,
                bgcolor="#D84315",
                color="white",
            )
        )
    contenido_desplazable = ft.Column(
        contenido_principal,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.START,
        spacing=10,
        scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        expand=True,
    )
    boton_volver = ft.ElevatedButton(
        "↩️ Volver al Menú Principal",
        on_click=lambda e: go_to_menu(),
    )

    content = ft.Container(
        content=ft.Column(
            [
                contenido_desplazable,
                ft.Container(
                    content=boton_volver,
                    alignment=ft.Alignment(0, 0),
                    padding=ft.Padding(top=8, bottom=4, left=0, right=0),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        ),
        padding=20,
        expand=True,
    )

    if mostrar_entregas:
        cargar_por_entregar()
        cargar_entregadas()

    page.add(
        ft.Stack(
            [
                fondo,
                ft.SafeArea(content)
            ],
            expand=True
        )
    )
    page.update()