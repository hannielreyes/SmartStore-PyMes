import json
import os

import flet as ft
from views.voz import VoiceService
from views.reservar import reservar_view
import database as db
from utils import configurar_retroceso, imagen_disponible


def _show_full_image(page: ft.Page, src: str, src_2: str | None = None):
    """Muestra las imágenes del producto en una pantalla independiente con zoom."""
    imagenes = [imagen for imagen in (src, src_2) if imagen]
    indice = 0
    previous_controls = list(page.controls)
    imagen_control = ft.Image(src=imagenes[0], fit="contain", expand=True)

    def siguiente(e):
        nonlocal indice
        indice = (indice + 1) % len(imagenes)
        imagen_control.src = imagenes[indice]
        page.update()

    def cerrar(e):
        page.clean()
        page.bgcolor = "white"
        for control in previous_controls:
            page.add(control)
        page.update()

    ancho_disponible = max((page.width or 360) - 32, 260)
    ancho_imagen = min(ancho_disponible, 600)
    ancho_botones = min(ancho_disponible, 420)

    botones = ft.Column(
        [
            ft.ElevatedButton(
                "Ver siguiente imagen →",
                on_click=siguiente,
                visible=len(imagenes) > 1,
                bgcolor="#040D4A",
                color="white",
                height=44,
                width=ancho_botones,
            ),
            ft.ElevatedButton(
                "Cerrar",
                on_click=cerrar,
                bgcolor="#EFA520",
                color="#040D4A",
                height=44,
                width=ancho_botones,
            ),
        ],
        spacing=12,
        width=ancho_botones,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    vista_imagen = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondopro.png", fit="cover"),
        padding=20,
        content=ft.Column(
            [
                ft.Container(
                    content=ft.InteractiveViewer(
                        content=imagen_control,
                        min_scale=1,
                        max_scale=4,
                        scale_enabled=True,
                        pan_enabled=True,
                    ),
                    width=ancho_imagen,
                    height=560,
                    border_radius=24,
                    bgcolor="transparent",
                    padding=0,
                ),
                ft.Container(
                    content=botones,
                    padding=12,
                    border_radius=24,
                    bgcolor="rgba(255,255,255,0.18)",
                    alignment=ft.Alignment(0, 0),
                    width=min(ancho_disponible, 420),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
    )

    page.clean()
    page.bgcolor = "white"
    page.add(vista_imagen)
    page.update()

# ==========================================
# RECONOCIMIENTO DE VOZ (Flet STT nativo de Android)
# ==========================================
try:
    from flet_stt import FletStt
    STT_DISPONIBLE = True
except ImportError:
    FletStt = None
    STT_DISPONIBLE = False
    print("⚠️ flet-stt no instalado. Instala con: pip install flet-stt")


def buscar_voz_view(page: ft.Page, usuario, go_back):
    # PANTALLA: búsqueda de productos mediante entrada de voz.
    # Pantalla de búsqueda por voz y presentación de sus resultados.
    """Pantalla de búsqueda por voz usando el micrófono nativo del sistema."""
    configurar_retroceso(page, go_back)
    try:
        page.overlay.clear()
    except Exception:
        pass

    page.clean()
    page.controls.clear()
    page.bgcolor = "white"

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )

    nombre = usuario['nombre'] if usuario else "usuario"
    resultado_texto = ft.Text("", size=16)
    productos_encontrados = ft.ListView(
        spacing=10,
        auto_scroll=True,
        scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        expand=True,
        height=320,
    )

    voz = VoiceService(page=page, voice_name="es-MX-JorgeNeural")
    stt = FletStt() if STT_DISPONIBLE else None
    escuchando = False
    transcripcion_voz = ft.TextField(
        label="Lo que estoy escuchando",
        value="",
        read_only=True,
        multiline=True,
        min_lines=2,
        max_lines=4,
        width=360,
        visible=False,
    )

    def hablar_mensaje(mensaje, callback=None):
        def on_end():
            if callback:
                callback()

        if not getattr(voz, "audio_disponible", False):
            if callback:
                callback()
            return

        voz.hablar(mensaje, on_end=on_end)

    def parse_event_data(event):
        if event is None:
            return {}
        data = getattr(event, "data", None)
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return {"text": data}
        if isinstance(data, dict):
            return data
        return {}

    def actualizar_boton_escucha():
        nonlocal escuchando
        if btn_escuchar is not None:
            btn_escuchar.content = ft.Row(
                [
                    ft.Icon(ft.Icons.MIC, size=20),
                    ft.Text(
                        "Detener escucha" if escuchando else "Toca para hablar",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            )
            btn_escuchar.bgcolor = "#0A7A41" if escuchando else "#040D4A"
            btn_escuchar.color = "white"
            transcripcion_voz.visible = escuchando or bool(transcripcion_voz.value)
            page.update()

    def iniciar_escucha(e=None):
        nonlocal escuchando
        if not STT_DISPONIBLE or stt is None:
            resultado_texto.value = "⚠️ Esta versión no tiene activada la voz nativa del sistema. Usa la búsqueda escrita."
            resultado_texto.color = "orange"
            page.update()
            return

        if escuchando:
            page.run_task(detener_escucha)
            return

        page.run_task(escuchar)

    async def detener_escucha():
        nonlocal escuchando
        escuchando = False
        try:
            if stt is not None:
                await stt.stop()
        except Exception:
            pass
        finally:
            transcripcion_voz.value = ""
            actualizar_boton_escucha()
            resultado_texto.value = "🔇 Escucha terminada."
            resultado_texto.color = "#040D4A"
            page.update()

    async def escuchar():
        nonlocal escuchando, stt
        if not STT_DISPONIBLE:
            return

        stt = FletStt()
        resultado_recibido = False
        escuchando = True
        transcripcion_voz.value = "Habla ahora..."
        actualizar_boton_escucha()
        resultado_texto.value = "Escuchando... habla ahora."
        resultado_texto.color = "#040D4A"
        page.update()

        try:
            def on_result(e):
                nonlocal resultado_recibido
                payload = parse_event_data(e)
                final = bool(payload.get("final", False))
                texto = str(payload.get("text", "")).strip()
                if not texto:
                    return
                transcripcion_voz.value = texto
                transcripcion_voz.visible = True
                if final:
                    resultado_recibido = True
                    texto_buscado = texto.lower()
                    resultado_texto.value = f"🔍 Buscando: '{texto_buscado}'"
                    resultado_texto.color = "#040D4A"
                    page.update()
                    buscar_en_bd(texto_buscado)

            def on_error(e):
                nonlocal escuchando
                payload = parse_event_data(e)
                detalle = str(payload.get("error") or "Error del micrófono")
                escuchando = False
                actualizar_boton_escucha()
                detalle_lower = detalle.lower()
                if "no_match" in detalle_lower or "no match" in detalle_lower:
                    resultado_texto.value = "🎙️ No entendí bien lo que dijiste. Inténtalo otra vez."
                    resultado_texto.color = "orange"
                else:
                    resultado_texto.value = f"❌ {detalle}"
                    resultado_texto.color = "red"
                page.update()

            def on_status(e):
                payload = parse_event_data(e)
                status = str(payload.get("status") or "").lower()
                if status in {"listening", "listening_started"}:
                    resultado_texto.value = "Escuchando... habla ahora."
                    resultado_texto.color = "#040D4A"
                    page.update()
                elif status in {"done", "notlistening", "not_listening"}:
                    nonlocal escuchando
                    if escuchando:
                        escuchando = False
                        actualizar_boton_escucha()
                        if not resultado_recibido:
                            resultado_texto.value = "🎙️ No se detectó ninguna palabra. Inténtalo otra vez."
                            resultado_texto.color = "orange"
                    page.update()

            stt.on_result = on_result
            stt.on_error = on_error
            stt.on_status = on_status

            inicializado = await stt.initialize()
            if not inicializado:
                raise RuntimeError("No se pudo inicializar el reconocimiento nativo.")

            permisos = await stt.has_permission()
            if not permisos:
                escuchando = False
                transcripcion_voz.value = ""
                actualizar_boton_escucha()
                resultado_texto.value = "📵 Debes permitir el micrófono en Android para usar la búsqueda por voz."
                resultado_texto.color = "red"
                page.update()
                return

            await stt.listen(
                locale_id="es_MX",
                listen_mode="search",
                partial_results=True,
                continuous=True,
                on_device=False,
                cancel_on_error=True,
                listen_for_seconds=60,
                pause_for_seconds=5,
                cloud_timeout_seconds=60,
            )

        except Exception as e:
            escuchando = False
            actualizar_boton_escucha()
            resultado_texto.value = f"❌ No se pudo escuchar: {e}"
            resultado_texto.color = "red"
            page.update()

    def buscar_en_bd(texto):
        nonlocal escuchando
        productos = db.obtener_productos_por_nombre(texto)
        cantidad = len(productos)
        escuchando = False
        actualizar_boton_escucha()

        productos_encontrados.controls.clear()

        if cantidad > 0:
            mensaje = f"✅ ¡Excelente {nombre}! Encontré {cantidad} opciones para ti. Éxito en tu compra."
            resultado_texto.value = mensaje
            resultado_texto.color = "green"

            for p in productos:
                id_producto = p[0]
                nombre_producto = p[1]
                marca = p[2] or "Sin marca"
                talla = p[3] or "Sin talla"
                precio_c = float(p[4]) if p[4] else 0
                precio_d = float(p[5]) if p[5] else 0
                stock = int(p[6]) if p[6] else 0
                imagen = p[8] if len(p) > 8 else None
                imagen_2 = p[9] if len(p) > 9 else None

                thumb = ft.Container(width=70, height=70, bgcolor="#EAEAF5", border_radius=12)
                if imagen and imagen_disponible(imagen):
                    thumb = ft.Container(
                        content=ft.Image(src=imagen, width=70, height=70, fit="cover"),
                        width=70,
                        height=70,
                        border_radius=12,
                        bgcolor="#EAEAF5",
                    )
                thumb_clickable = ft.Container(
                    content=thumb,
                    on_click=(lambda e, s=imagen, s2=imagen_2: _show_full_image(page, s, s2)) if imagen else None,
                    border_radius=12,
                )

                card = ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    thumb_clickable,
                                    ft.Column(
                                        [
                                            ft.Text(nombre_producto, weight=ft.FontWeight.BOLD, size=15, color="#040D4A"),
                                            ft.Text(f"Marca: {marca} • Talla: {talla}", size=12, color="#555555"),
                                            ft.Text(f"C$ {precio_c:,.2f} / US$ {precio_d:,.2f}", size=13, weight=ft.FontWeight.W_600, color="#0A7A41"),
                                            ft.Text(f"Stock: {stock}", size=12, color="#666666"),
                                        ],
                                        spacing=4,
                                        expand=True,
                                    ),
                                ],
                                spacing=12,
                                alignment=ft.MainAxisAlignment.START,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.ElevatedButton(
                                "Reservar",
                                on_click=lambda e, id_p=id_producto, nom=nombre_producto, cant=stock: reservar_view(
                                    page,
                                    usuario,
                                    id_p,
                                    nom,
                                    cant,
                                    lambda: buscar_voz_view(page, usuario, go_back),
                                ),
                                bgcolor="#0A7A41",
                                color="white",
                                width=220,
                            ),
                        ],
                        spacing=10,
                    ),
                    padding=12,
                    bgcolor=ft.Colors.WHITE,
                    border_radius=16,
                    border=ft.Border(
                        left=ft.BorderSide(1, "#E7E7F0"),
                        right=ft.BorderSide(1, "#E7E7F0"),
                        top=ft.BorderSide(1, "#E7E7F0"),
                        bottom=ft.BorderSide(1, "#E7E7F0"),
                    ),
                    width=340,
                )
                productos_encontrados.controls.append(card)

            hablar_mensaje(f"Encontré {cantidad} opciones para ti. Éxito en tu compra.")
        else:
            mensaje = f"😅 Lo siento {nombre}, no encontré coincidencias. ¿Quieres probar con otro término?"
            resultado_texto.value = mensaje
            resultado_texto.color = "orange"
            productos_encontrados.controls.append(
                ft.Text("No se encontraron productos", size=14, color="#888888")
            )
            hablar_mensaje(f"Lo siento {nombre}, no encontré coincidencias. ¿Quieres probar con otro término?")

        page.update()

    btn_escuchar = ft.ElevatedButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.MIC, size=20),
                ft.Text("Toca para hablar", size=16, weight=ft.FontWeight.BOLD),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        on_click=iniciar_escucha,
        bgcolor="#040D4A",
        color="white",
        width=260,
        height=56,
    )

    async def salir_de_busqueda():
        if escuchando:
            await detener_escucha()
        elif stt is not None:
            try:
                await stt.stop()
            except Exception:
                pass
        go_back()

    btn_volver = ft.ElevatedButton(
        "Volver",
        on_click=lambda e=None: page.run_task(salir_de_busqueda),
        bgcolor="#E0E0E0",
        color="#040D4A",
        width=200,
    )

    content = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("🔊 Buscar por voz", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
                ft.Text("Toca el botón y habla para buscar productos", size=14, color="#666666"),
                ft.Divider(height=20, color="transparent"),
                resultado_texto,
                ft.Divider(height=10, color="transparent"),
                btn_escuchar,
                transcripcion_voz,
                ft.Divider(height=20, color="transparent"),
                ft.Container(
                    content=productos_encontrados,
                    width=360,
                    height=320,
                    border_radius=18,
                    bgcolor="rgba(255,255,255,0.7)",
                    padding=8,
                ),
                ft.Divider(height=20, color="transparent"),
                btn_volver,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=20,
    )

    page.add(ft.Stack([fondo, ft.SafeArea(content)], expand=True))
