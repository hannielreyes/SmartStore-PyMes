import flet as ft
import asyncio
import time
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

    progress = ft.ProgressRing(
        width=40,       # Ancho del circulito en píxeles.
        height=40,      # Alto del circulito en píxeles.
        stroke_width=5, # Grosor de la línea del circulito en píxeles.
        color="#040D4A",
    )

    # CONTROLES: identidad visual de inicio e indicador de precarga de datos.
    content = ft.Column(
        [
            ft.Text("😉", size=80),
            ft.Text("🛒", size=80),
            ft.Text("¡Smart-Store!", size=32, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ft.Container(height=6), #espaciado entre el título y el indicador de progreso.
            progress,
            ft.Text("Cargando datos...", size=15, color="#FFFFFF"),
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
        """Mantiene el indicador visible al menos 6 segundos y luego avanza."""
        inicio = time.monotonic()
        try:
            await asyncio.wait_for(page._smartstore_start_ready.wait(), timeout=30)
        except asyncio.TimeoutError:
            # La interfaz puede continuar aunque el servidor tarde demasiado.
            pass

        transcurrido = time.monotonic() - inicio
        if transcurrido < 6:
            await asyncio.sleep(6 - transcurrido)

        page.clean()
        page.update()
        on_complete()

    page.run_task(animar_progreso)