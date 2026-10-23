import flet as ft
from utils import configurar_retroceso
import hashlib
contrasena = hashlib.md5(b"mi_clave_secreta") 
def splash_view(page: ft.Page, on_complete):
    # PANTALLA: bienvenida de la aplicación a pantalla completa.
    configurar_retroceso(page, lambda: None)
    page.clean()
    page.update()
    page.bgcolor = "#020526"
    page.padding = 0
    page.spacing = 0
    page.margin = 0

    fondo = ft.Image(
        src="bienvenida.png",
        fit="cover",
        expand=True,
    )

    # BOTÓN: permite avanzar desde la bienvenida hacia la siguiente pantalla.
    btn_avanzar = ft.ElevatedButton(
        content=ft.Icon(ft.Icons.ARROW_FORWARD, size=28),
        tooltip="Continuar",
        bgcolor="#02032415",
        color="#EE580DDF",
        width=58,
        height=58,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=5),
            side=ft.BorderSide(color="#030526", width=0),
        )
    )

    finalizado = {"valor": False}

    def avanzar(e=None):
        # ACCIÓN: limpia la bienvenida y continúa con el flujo de inicio.
        if finalizado["valor"]:
            return
        finalizado["valor"] = True
        page.clean()
        page.update()
        on_complete()

    btn_avanzar.on_click = avanzar

    # LAYOUT: coloca el botón de entrada abajo y a la derecha.
    capa_contenido = ft.Container(
        content=ft.Column(
            [btn_avanzar],
            alignment=ft.MainAxisAlignment.END,          # Botón abajo
            horizontal_alignment=ft.CrossAxisAlignment.END,  # Botón derecha
        ),
        expand=True,
        padding=30,  # Margen desde los bordes
    )

    # MONTAJE: superpone la imagen de bienvenida y el botón de entrada.
    stack = ft.Stack(
        [
            fondo,
            capa_contenido,
        ],
        expand=True
    )

    page.add(stack)
    page.update()