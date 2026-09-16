import flet as ft
import asyncio
from utils import configurar_retroceso

def pre_splash_view(page: ft.Page, on_complete):
    # PANTALLA: carga inicial de la aplicación y alineación general.
    configurar_retroceso(page, lambda: None)
    page.clean()
    page.padding = 0
    page.spacing = 0
    page.margin = 0
    page.bgcolor = "#EF7620"
    page.update()

    progress = ft.ProgressBar(width=200, color="white", bgcolor="#EFA52088")

    # CONTROLES: identidad visual de inicio y barra que indica el progreso de carga.
    content = ft.Column(
        [
            ft.Text("😉", size=80),
            ft.Text("🛒", size=80),
            ft.Text("¡Smart-Store!", size=32, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ft.Container(height=20),
            progress,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=20,
        alignment=ft.MainAxisAlignment.CENTER,
        expand=True,
    )
    
    # MONTAJE: agrega la pantalla inicial a la página.
    page.add(content)
    page.update()

    async def animar_progreso():
        """Anima el progreso de forma async y segura"""
        for i in range(10):
            await asyncio.sleep(0.6)
            progress.value = (i + 1) / 10
            page.update()
        
        await asyncio.sleep(0.6)
        page.clean()
        page.update()
        
        on_complete()

    page.run_task(animar_progreso)