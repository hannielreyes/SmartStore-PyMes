import flet as ft
import database as db
from database.models import ProductoDestacado
from utils import mostrar_snackbar, configurar_retroceso


def top_productos_view(page: ft.Page, usuario, go_back):
    # PANTALLA: ranking de productos más comprados y navegación de regreso.
    # Pantalla de productos destacados según compras pagadas.
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "white"

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
        lista.controls.append(ft.Text("Aún no hay productos con al menos 3 compras pagadas 😊", width=300, text_align=ft.TextAlign.CENTER))
    else:
        for p in productos:
            nombre = p.nombre
            precio_c = float(p.precio_cordobas or 0)
            precio_d = float(p.precio_dolares or 0)
            stock = int(p.stock or 0)
            compras = int(p.compras or 0)
            # La clasificación del top refleja popularidad, no reseñas manuales:
            # 3 compras = 1 estrella; cada 2 compras adicionales suma una estrella.
            estrellas_llenas = 1 if compras == 3 else min(5, ((compras - 4) // 2) + 2)
            estrellas = "★" * estrellas_llenas + "☆" * (5 - estrellas_llenas)
            rating_text = f"{estrellas}  Popularidad: {estrellas_llenas}/5"

            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Column([
                            ft.Text(nombre, weight=ft.FontWeight.BOLD),
                            ft.Text(f"C${precio_c:.2f} / ${precio_d:.2f}"),
                            ft.Text(f"Compras: {compras}"),
                            ft.Text(rating_text, color="#EFA520", weight=ft.FontWeight.BOLD),
                        ]),
                    ],
                ),
                bgcolor=ft.Colors.WHITE,
                border_radius=12,
                padding=10,
            )
            lista.controls.append(card)

    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("Top Productos", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
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
