from datetime import datetime, timedelta

import flet as ft

import database as db
from utils import configurar_retroceso


def ajustes_adicionales_view(page: ft.Page, usuario, go_back, abrir_estadisticas, abrir_perfil_usuario):
	# PANTALLA: ajustes adicionales con accesos al perfil y a estadísticas.
	configurar_retroceso(page, lambda: go_back(usuario))
	page.clean()
	page.bgcolor = "#FFFFFF"

	fondo = ft.Container(
		expand=True,
		image=ft.DecorationImage(src="fondo.png", fit="cover"),
	)

	# BOTONES DE AJUSTES: perfil, estadísticas y regreso al menú.
	ancho_btn_perfil = 260
	ancho_btn_estadisticas = 260
	ancho_btn_volver = 260

	# CONTROLES: título y botones principales de la pantalla de ajustes.
	contenido = ft.Container(
		content=ft.Column(
			[
				ft.Container(height=35),
				ft.Text("⚙️ Ajustes Adicionales", size=28, weight=ft.FontWeight.BOLD, color="#040D4A", text_align=ft.TextAlign.CENTER),
				ft.Text("Personaliza tu cuenta y negocio", size=14, color="#555555", text_align=ft.TextAlign.CENTER),
				# BOTÓN: abre el perfil personal del usuario.
				ft.ElevatedButton(
					"👤 Mi Perfil",
					on_click=lambda e: abrir_perfil_usuario(usuario),
					bgcolor="#168AAD",
					color="#FFFFFF",
					width=ancho_btn_perfil,
				),
				# BOTÓN: abre el resumen de estadísticas de ventas.
				ft.ElevatedButton(
					"📊 Estadísticas",
					on_click=lambda e: abrir_estadisticas(usuario),
					bgcolor="#040D4A",
					color="#FFFFFF",
					width=ancho_btn_estadisticas,
				),
				# BOTÓN: regresa al menú principal.
				ft.ElevatedButton(
					"↩️ Volver al Menú",
					on_click=lambda e: go_back(usuario),
					bgcolor="#E0E0E0",
					color="#040D4A",
					width=ancho_btn_volver,
				),
			],
			horizontal_alignment=ft.CrossAxisAlignment.CENTER,
			alignment=ft.MainAxisAlignment.CENTER,
			spacing=18,
			scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
		),
		padding=20,
	)

	page.add(ft.Stack([fondo, ft.SafeArea(contenido)], expand=True))


def estadisticas_view(page: ft.Page, usuario, go_back):
	# PANTALLA: resumen semanal, total vendido y barras de ventas.
	configurar_retroceso(page, go_back)
	page.clean()
	page.bgcolor = "#FFFFFF"

	fondo = ft.Container(
		expand=True,
		image=ft.DecorationImage(src="fondo.png", fit="cover"),
	)

	ventas_por_fecha = {
		venta.fecha: venta.total for venta in db.obtener_ventas_semana(usuario["id"])
	}
	hoy = datetime.now().date()
	inicio_semana = hoy - timedelta(days=(hoy.weekday() + 1) % 7)
	dias = [inicio_semana + timedelta(days=posicion) for posicion in range(7)]
	valores = [float(ventas_por_fecha.get(dia.isoformat(), 0)) for dia in dias]
	total_semana = sum(valores)
	maximo = max(valores, default=0)
	nombres_dias = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
	nombres_meses = [
		"Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
		"Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
	]
	fecha_actual = (
		f"{nombres_dias[(hoy.weekday() + 1) % 7]} {hoy.day} de "
		f"{nombres_meses[hoy.month - 1]} de {hoy.year}"
	)

	barras = ft.Column(spacing=10, width=360)
	for nombre_dia, valor in zip(nombres_dias, valores):
		ancho = 280 * valor / maximo if maximo else 0
		barras.controls.append(
			ft.Row(
				[
					ft.Text(nombre_dia, width=78, size=12),
					ft.Container(
						content=ft.Text(
							f"C${valor:.2f}" if valor else "Sin ventas",
							size=11,
							color="#FFFFFF" if valor else "#555555",
						),
						width=max(ancho, 82 if valor else 82),
						height=28,
						bgcolor="#168AAD" if valor else "#D9E2EC",
						padding=6,
						border_radius=6,
					),
				],
				spacing=8,
			)
		)

	# CONTROLES: resultados calculados y botón para regresar a Ajustes.
	contenido = ft.Container(
		content=ft.Column(
			[
				ft.Container(height=35),
				ft.Text("📊 Ventas de la semana", size=28, weight=ft.FontWeight.BOLD, color="#040D4A", text_align=ft.TextAlign.CENTER),
				ft.Text(f"Fecha actual: {fecha_actual} 😊", size=14, color="#555555", text_align=ft.TextAlign.CENTER),
				ft.Container(
					content=ft.Text(f"Total vendido: C${total_semana:.2f}", size=20, weight=ft.FontWeight.BOLD, color="#040D4A", text_align=ft.TextAlign.CENTER),
					bgcolor="#F8FAFC",
					padding=15,
					border_radius=12,
					width=360,
				),
				barras,
				# BOTÓN: regresa a la pantalla de ajustes adicionales.
				ft.ElevatedButton("↩️ Volver a Ajustes adicionales", on_click=lambda e: go_back()),
			],
			horizontal_alignment=ft.CrossAxisAlignment.CENTER,
			alignment=ft.MainAxisAlignment.CENTER,
			spacing=18,
			scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
		),
		padding=20,
	)

	page.add(ft.Stack([fondo, ft.SafeArea(contenido)], expand=True))
