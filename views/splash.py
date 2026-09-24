import flet as ft
import asyncio
from utils import configurar_retroceso
import hashlib
contrasena = hashlib.md5(b"mi_clave_secreta") 
def splash_view(page: ft.Page, on_complete):
    # PANTALLA: bienvenida de la aplicación a pantalla completa.
    configurar_retroceso(page, lambda: None)
    page.clean()
    page.update()
    page.bgcolor = "#F5F7FA"
    page.padding = 0
    page.spacing = 0
    page.margin = 0

    fondo = ft.Image(
        src="Bienvenida.png",
        fit="cover",
        expand=True,
    )

    # BOTÓN: permite avanzar desde la bienvenida hacia la siguiente pantalla.
    btn_avanzar = ft.ElevatedButton(
    content=ft.Column(
        [
            ft.Text("📎", size=18),
            ft.Text("🙃", size=16),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    ),
    bgcolor="#C3D2D6",
    color="white",
    width=60,
    height=60,
    style=ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=5)
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

    async def auto_avanzar():
        await asyncio.sleep(6)
        if not finalizado["valor"]:
            avanzar()

    page.run_task(auto_avanzar)

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