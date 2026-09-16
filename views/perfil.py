import flet as ft

import database as db
from utils import configurar_retroceso, mostrar_snackbar


def perfil_view(page: ft.Page, usuario, go_back, logout, go_to_control_reservas):
    # PANTALLA: perfil, billeteras de tiendas y configuración de pagos.
    """Vista de billetera y configuración de pagos."""
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "white"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )
    tiendas = db.obtener_tiendas_usuario(usuario["id"])

    def ir_a_billetera(e):
        # ACCIÓN: abre la billetera o explica por qué aún no está disponible.
        if tiendas:
            go_to_control_reservas(tiendas[0][0], True, False)
            return

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("🔒 Acceso restringido", weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Text("Para usar la billetera necesitas registrar una tienda."),
                    ft.Text("Ve al menú principal y selecciona 'Crear Tienda'."),
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton(
                    "Entendido",
                    on_click=lambda e: setattr(dialogo, "open", False) or page.update(),
                )
            ],
        )
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    # BOTONES DINÁMICOS: crea un acceso a la billetera por cada tienda.
    botones_billeteras = [
        ft.ElevatedButton(
            f"💰 {tienda[1]}",
            on_click=lambda e, tienda_id=tienda[0]: go_to_control_reservas(tienda_id, True, False),
            bgcolor="#EFD320",
            color="white",
            height=36,
        )
        for tienda in tiendas
    ]
    titulo_billeteras = "Billetera de tu tienda" if len(tiendas) == 1 else "Billetera de tus tiendas"
    lista_billeteras = (
        ft.Row(
            botones_billeteras,
            width=340,
            spacing=8,
            height=42,
            alignment=ft.MainAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )
        if botones_billeteras
        else ft.ElevatedButton(
            "💰 Abrir billetera",
            on_click=ir_a_billetera,
            bgcolor="#EFD320",
            color="white",
            height=36,
        )
    )

    def vincular_paypal(e):
        # DIÁLOGO: permite vincular o cambiar el correo de PayPal.
        paypal_actual = db.obtener_paypal_email(usuario["id"])
        email_input = ft.TextField(
            label="Correo de PayPal",
            value=paypal_actual or "",
            hint_text="ejemplo@correo.com",
            width=300,
        )
        mensaje = ft.Text("", size=12)

        def guardar_email(e):
            # ACCIÓN: valida y guarda el correo de PayPal.
            email = email_input.value.strip()
            if not email or "@" not in email:
                mensaje.value = "⚠️ Escribe un correo válido."
                mensaje.color = "red"
                page.update()
                return
            db.guardar_paypal_email(usuario["id"], email)
            dialogo.open = False
            page.update()
            mostrar_snackbar(page, "✅ Cuenta PayPal vinculada correctamente.", color="green")

        def cancelar(e):
            # ACCIÓN: cierra el diálogo sin guardar el correo.
            dialogo.open = False
            page.update()

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("💳 Vincular PayPal", weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Text("Ingresa el correo de PayPal donde recibirás tus pagos."),
                    email_input,
                    mensaje,
                ],
                tight=True,
                spacing=8,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=cancelar),
                ft.ElevatedButton(
                    "Guardar",
                    on_click=guardar_email,
                    bgcolor="#040D4A",
                    color="white",
                ),
            ],
        )
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    paypal_actual = db.obtener_paypal_email(usuario["id"])
    texto_paypal = "🔄 Cambiar PayPal" if paypal_actual else "💳 Vincular PayPal"

    contenido = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=20),
                ft.Text("💳 Mi Billetera", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
                ft.Divider(height=18),
                ft.Text(titulo_billeteras, size=16, weight=ft.FontWeight.BOLD),
                lista_billeteras,
                ft.Divider(height=18),
                ft.Text("💳 Configuración de pagos", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"📧 {paypal_actual}", size=13, color="green") if paypal_actual else ft.Container(),
                ft.ElevatedButton(
                    texto_paypal,
                    on_click=vincular_paypal,
                    bgcolor="#040D4A",
                    color="white",
                    height=36,
                ),
                ft.Text(
                    "📌 Vincula PayPal para recibir los pagos de tus ventas.",
                    size=12,
                    color="#555555",
                    italic=True,
                ) if not paypal_actual else ft.Container(),
                ft.Container(height=10),
                ft.ElevatedButton(
                    "↩️ Volver al menú",
                    on_click=lambda e: go_back(usuario),
                    height=36,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=14,
    )

    # IMPORTANTE: esta lógica de centrado es la base del layout.
    # NO MODIFICAR ni reordenar el Stack/SafeArea aunque se agreguen más campos,
    # más ajustes o contenido extra; todo debe mantenerse centrado y consistente.
    # esta estructura es la forma correcta y debe permanecer así por diseño.

    # ajustes o contenido extra; la vista debe seguir centrada siempre.
    # IMPORTANTE: esta lógica de centrado es parte de la estructura visual correcta.
    # NO MODIFICAR ni alterar el Stack/SafeArea aunque se agreguen más campos, ajustes
    # o contenido extra; todo debe mantenerse centrado y consistente.
    page.add(ft.Stack([fondo, ft.SafeArea(contenido)], expand=True))
