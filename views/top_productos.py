import flet as ft
import database as db
from database.models import ProductoDestacado
from utils import mostrar_snackbar, configurar_retroceso


def top_productos_view(page: ft.Page, usuario, go_back):
    # PANTALLA: ranking de productos más comprados y navegación de regreso.
    # Pantalla de productos destacados según compras pagadas.
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "#FFFFFF"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )

    productos = [
        ProductoDestacado.desde_fila(fila)
        for fila in db.obtener_top_productos(limit=10, min_compras=3)
    ]

    # Lista de tarjetas con nombre, precios, compras y popularidad.
    lista = ft.Column(spacing=10)

    if not productos:
        lista.controls.append(ft.Text("Aún no hay productos con al menos 3 compras pagadas 😊", width=300, text_align=ft.TextAlign.CENTER, color="#FFFFFF"))
    else:
        for p in productos:
            nombre = p.nombre
            precio_c = float(p.precio_cordobas or 0)
            precio_d = float(p.precio_dolares or 0)
            stock = int(p.stock or 0)
            compras = int(p.compras or 0)
            # Las estrellas las asigna la plataforma según las compras pagadas.
            estrellas_llenas = p.estrellas_popularidad
            estrellas = "★" * estrellas_llenas + "☆" * (5 - estrellas_llenas)
            rating_text = f"{estrellas}  Popularidad por compras: {estrellas_llenas}/5"

            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Column([
                            ft.Text(nombre, weight=ft.FontWeight.BOLD),
                            ft.Text(f"C${precio_c:.2f} / ${precio_d:.2f}"),
                            ft.Text(f"Compras: {compras}"),
                            ft.Text(rating_text, color="#000000", weight=ft.FontWeight.BOLD),
                        ]),
                    ],
                ),
                bgcolor="#FFFFFF",
                border_radius=12,
                padding=10,
            )
            lista.controls.append(card)

    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("Top Productos", size=28, weight=ft.FontWeight.BOLD, color="#00D9FF"),
                lista,
                ft.ElevatedButton("↩️ Volver", on_click=lambda e: go_back(usuario)),
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
