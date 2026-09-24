import flet as ft
import database as db
from utils import abrir_selector_imagen, guardar_imagen_en_assets, mostrar_snackbar, configurar_retroceso
import os
import asyncio
import base64
from datetime import datetime
import flet_camera as fc

def registrar_producto_view(page: ft.Page, usuario, go_back):
    # PANTALLA: formulario de productos y calculadora de precios.
    configurar_retroceso(page, lambda: go_back(usuario))
    page.clean()
    page.bgcolor = "white"
    page.overlay.clear()
    print 

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )

    def mostrar_aviso_camara_no_disponible():
        # DIÁLOGO: informa cuando la cámara no está disponible en la plataforma.
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("💙 Aviso importante", weight=ft.FontWeight.BOLD, color="#040D4A"),
            content=ft.Text(
                "Estimado usuario, te informamos que la cámara solo está disponible "
                "en la versión Android. 📱✨",
                size=15,
            ),
            actions=[
                # BOTÓN: cierra el aviso de cámara.
                ft.ElevatedButton(
                    "Entendido 😊",
                    on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                    bgcolor="#040D4A",
                    color="white",
                )
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ESTADO: el formulario comienza en modo registrar producto.
    modo_registrar = True

    nombre_input_reg = ft.TextField(label="Nombre del producto", width=300)
    categoria_input = ft.Dropdown(
        label="Categoría del producto",
        value="General",
        options=[ft.DropdownOption(key=opcion, text=opcion) for opcion in [
            "General", "Ropa y calzado", "Alimentos", "Bebidas", "Limpieza", "Hogar",
            "Electrónica", "Celulares y accesorios", "Computación", "Ferretería", "Construcción",
            "Salud", "Belleza", "Mascotas", "Papelería", "Oficina", "Automotriz", "Agricultura",
            "Restaurante", "Servicios", "Juguetes", "Deportes", "Muebles", "Joyas y accesorios",
            "Repuestos",
        ]],
        width=300,
    )
    marca_input = ft.TextField(label="Marca (si tiene)", width=300)
    talla_input = ft.TextField(label="Tamaño, color o tipo (si aplica)", width=300)
    precio_input_reg = ft.TextField(label="Precio en C$", width=300)
    cantidad_input = ft.TextField(label="Cantidad disponible", width=300)
    descripcion_input = ft.TextField(label="Descripción del producto", width=300, multiline=True, min_lines=2, max_lines=4)
    estado_input = ft.Dropdown(
        label="Estado del producto",
        value="Nuevo",
        options=[
            ft.DropdownOption("Nuevo"),
            ft.DropdownOption("Usado"),
            ft.DropdownOption("Seminuevo"),
        ],
        width=300,
    )
    etiquetas_input = ft.TextField(label="Etiquetas o estilo", width=300, hint_text="Ej: premium, casual, verano, elegante")
    color_input = ft.TextField(label="Color principal", width=300)
    material_input = ft.TextField(label="Material", width=300)
    garantia_input = ft.TextField(label="Garantía / especificación", width=300, hint_text="Ej: 6 meses, 1 año, para uso diario")
    especificacion_input = ft.TextField(label="Especificación extra", width=300, multiline=True, min_lines=2, max_lines=4)

    tasa_input_cal = ft.TextField(label="Valor de $1 en córdobas", value="36.5", width=300, visible=False)
    moneda_cal = ft.Dropdown(
        label="¿En qué moneda está el precio?",
        value="C$",
        options=[ft.DropdownOption(key="C$", text="Córdobas (C$)"), ft.DropdownOption(key="USD", text="Dólares ($)")],
        width=300,
        visible=False,
    )
    precio_input_cal = ft.TextField(label="Monto que deseas convertir", width=300, visible=False)
    porcentaje_input_cal = ft.TextField(label="Porcentaje que deseas calcular (opcional)", width=300, visible=False)

    resultado_texto = ft.Text("", color="green")
    imagen_producto_path = None
    imagen_producto_data = None
    imagen_producto_2_path = None
    imagen_producto_2_data = None
    imagen_preview = ft.Container(bgcolor="#F3F3F3", border_radius=12, visible=False)
    camera_container = ft.Container(bgcolor="#1a1a2e", border_radius=10, visible=False)
    camera = None
    destino_imagen = None
    controles_anteriores = []
    file_picker = ft.FilePicker()
    page.services.append(file_picker)
    tasa_calculadora = 36.5

    def actualizar_atributos(e=None):
        configuracion = {
            "Ropa y calzado": ("Marca (si tiene)", "Talla o color (si aplica)"),
            "Alimentos": ("Marca (si tiene)", "Peso, sabor o unidad (si aplica)"),
            "Bebidas": ("Marca (si tiene)", "Tamaño o cantidad (si aplica)"),
            "Electrónica": ("Marca (si tiene)", "Modelo (si aplica)"),
            "Servicios": ("Nombre del proveedor (si aplica)", "Duración del servicio (si aplica)"),
        }
        marca, detalle = configuracion.get(categoria_input.value, ("Marca (si tiene)", "Tamaño, color o tipo (si aplica)"))
        marca_input.label = marca
        talla_input.label = detalle
        page.update()

    categoria_input.on_change = actualizar_atributos

    contexto = getattr(page, "_smartstore_context", None) or {}
    tienda = contexto.get("tienda_actual")
    if tienda is None:
        tienda = db.obtener_tienda_usuario(usuario["id"])
    tasa = tienda[3] if tienda else 36.5
    tasa_calculadora = tasa
    tasa_texto = ft.Text(f"Tasa de cambio actual: C${tasa} = $1", size=12, color="#555555")
    titulo_formulario = ft.Text("Registrar Producto", size=28, weight=ft.FontWeight.BOLD, color="#040D4A")

    def cambiar_moneda(e):
        precio_input_cal.label = "Cantidad en córdobas (C$)" if moneda_cal.value == "C$" else "Cantidad en dólares ($)"
        page.update()

    moneda_cal.on_change = cambiar_moneda

    def limpiar_calculadora(e):
        precio_input_cal.value = ""
        porcentaje_input_cal.value = ""
        resultado_texto.value = ""
        page.update()

    def cambiar_modo(e):
        # ACCIÓN: alterna entre formulario de producto y calculadora.
        nonlocal modo_registrar, tasa_calculadora
        modo_registrar = not modo_registrar
        if modo_registrar:
            btn_modo.content = ft.Text("Registrar Producto")
            btn_alternativo.content = ft.Text("Cambiar a Modo Calculadora")
            titulo_formulario.value = "Registrar Producto"
            tasa_texto.visible = True
            nombre_input_reg.visible = True
            marca_input.visible = True
            talla_input.visible = True
            precio_input_reg.visible = True
            cantidad_input.visible = True
            descripcion_input.visible = True
            estado_input.visible = True
            etiquetas_input.visible = True
            color_input.visible = True
            material_input.visible = True
            garantia_input.visible = True
            especificacion_input.visible = True
            btn_imagen.visible = True
            btn_reemplazar_imagen.visible = bool(imagen_producto_path)
            btn_quitar_imagen.visible = bool(imagen_producto_path)
            imagen_preview.visible = bool(imagen_producto_path)
            btn_imagen_2.visible = True
            btn_reemplazar_imagen_2.visible = bool(imagen_producto_2_path)
            btn_quitar_imagen_2.visible = bool(imagen_producto_2_path)
            imagen_preview_2.visible = bool(imagen_producto_2_path)
            if imagen_producto_path:
                imagen_preview.visible = True
            tasa_input_cal.visible = False
            moneda_cal.visible = False
            precio_input_cal.visible = False
            porcentaje_input_cal.visible = False
            btn_limpiar_cal.visible = False
            resultado_texto.value = ""
            page.update()
        else:
            btn_modo.content = ft.Text("Calcular")
            btn_alternativo.content = ft.Text("Cambiar a Modo Registrar")
            titulo_formulario.value = "Calculadora de precios"
            tasa_texto.visible = False
            nombre_input_reg.visible = False
            marca_input.visible = False
            talla_input.visible = False
            precio_input_reg.visible = False
            cantidad_input.visible = False
            descripcion_input.visible = False
            estado_input.visible = False
            etiquetas_input.visible = False
            color_input.visible = False
            material_input.visible = False
            garantia_input.visible = False
            especificacion_input.visible = False
            btn_imagen.visible = False
            btn_reemplazar_imagen.visible = False
            btn_quitar_imagen.visible = False
            imagen_preview.visible = False
            btn_imagen_2.visible = False
            btn_reemplazar_imagen_2.visible = False
            btn_quitar_imagen_2.visible = False
            imagen_preview_2.visible = False
            tasa_input_cal.visible = True
            tasa_input_cal.value = str(tasa_calculadora)
            moneda_cal.visible = True
            precio_input_cal.visible = True
            porcentaje_input_cal.visible = True
            btn_limpiar_cal.visible = True
            resultado_texto.value = ""
            page.update()

    def normalizar_datos_imagen(image_data):
        if image_data is None:
            return None
        if isinstance(image_data, str):
            try:
                return base64.b64decode(image_data.split(",", 1)[-1], validate=True)
            except (ValueError, base64.binascii.Error):
                return None
        try:
            datos = bytes(image_data)
        except (TypeError, ValueError):
            return None
        return datos or None

    def obtener_fuente_imagen(ruta, image_data=None):
        datos = normalizar_datos_imagen(image_data)
        if datos:
            return {"src": base64.b64encode(datos).decode("ascii")}
        return {"src": ruta}

    def crear_miniatura(ruta, image_data=None):
        imagen = ft.Image(**obtener_fuente_imagen(ruta, image_data))
        return ft.Container(
            content=imagen,
            on_click=lambda e: mostrar_imagen_grande(ruta, image_data),
        )

    def procesar_imagen(ruta, image_data=None):
        nonlocal imagen_producto_path, imagen_producto_data
        if ruta:
            imagen_producto_path = ruta
            imagen_producto_data = normalizar_datos_imagen(image_data)
            if not imagen_producto_data and os.path.exists(ruta):
                with open(ruta, "rb") as image_file:
                    imagen_producto_data = image_file.read()
            imagen_preview.content = crear_miniatura(ruta, image_data)
            imagen_preview.visible = True
            btn_reemplazar_imagen.visible = True
            btn_quitar_imagen.visible = True
            if imagen_producto_2_path:
                btn_reemplazar_imagen.text = "Reemplazar imagen 1"
                btn_quitar_imagen.text = "Quitar imagen 1"
            mostrar_snackbar(page, "✅ Imagen cargada correctamente", color="green")
            page.update()

    def procesar_imagen_2(ruta, image_data=None):
        nonlocal imagen_producto_2_path, imagen_producto_2_data
        if ruta:
            imagen_producto_2_path = ruta
            imagen_producto_2_data = normalizar_datos_imagen(image_data)
            if not imagen_producto_2_data and os.path.exists(ruta):
                with open(ruta, "rb") as image_file:
                    imagen_producto_2_data = image_file.read()
            imagen_preview_2.content = crear_miniatura(ruta, image_data)
            imagen_preview_2.visible = True
            btn_reemplazar_imagen_2.visible = True
            btn_quitar_imagen_2.visible = True
            btn_reemplazar_imagen.text = "Reemplazar imagen 1"
            btn_quitar_imagen.text = "Quitar imagen 1"
            page.update()

    def quitar_imagen(e):
        nonlocal imagen_producto_path, imagen_producto_data
        imagen_producto_path = None
        imagen_producto_data = None
        imagen_preview.content = None
        imagen_preview.visible = False
        btn_reemplazar_imagen.visible = False
        btn_quitar_imagen.visible = False
        mostrar_snackbar(page, "✅ Imagen quitada correctamente 😊", color="green")
        page.update()

    def quitar_imagen_2(e):
        nonlocal imagen_producto_2_path, imagen_producto_2_data
        imagen_producto_2_path = None
        imagen_producto_2_data = None
        imagen_preview_2.content = None
        imagen_preview_2.visible = False
        btn_reemplazar_imagen_2.visible = False
        btn_quitar_imagen_2.visible = False
        btn_reemplazar_imagen.text = "Reemplazar imagen"
        btn_quitar_imagen.text = "Quitar imagen"
        page.update()

    def restaurar_formulario():
        if controles_anteriores:
            page.controls.clear()
            page.controls.extend(controles_anteriores)
            page.update()

    async def limpiar_camara():
        nonlocal camera
        if camera:
            try:
                await camera.pause_preview()
            except Exception:
                pass
        camera_container.content = None
        camera_container.visible = False
        camera = None

    def mostrar_imagen_grande(ruta, image_data=None):
        datos = normalizar_datos_imagen(image_data)
        modal = ft.Container(
            expand=True,
            bgcolor="white",
            content=ft.Container(
                content=ft.Image(**obtener_fuente_imagen(ruta, image_data), fit="contain"),
                width=340,
                height=520,
                bgcolor="white",
                padding=10,
                alignment=ft.Alignment(0, 0),
            ),
            alignment=ft.Alignment(0, 0),
            on_click=lambda e: (page.overlay.remove(modal), page.update()),
        )
        page.overlay.append(modal)
        page.update()

    def procesar_imagen_capturada(image_data):
        if not image_data:
            return
        if isinstance(image_data, str):
            image_data = base64.b64decode(image_data.split(",", 1)[-1])
        os.makedirs("temp", exist_ok=True)
        ruta = os.path.join("temp", f"foto_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg")
        with open(ruta, "wb") as image_file:
            image_file.write(image_data)
        restaurar_formulario()
        if destino_imagen:
            destino_imagen(ruta, image_data)

    async def abrir_camara_accion(e):
        nonlocal camera
        if page.platform != ft.PagePlatform.ANDROID:
            mostrar_aviso_camara_no_disponible()
            return
        try:
            camera = fc.Camera(expand=True, preview_enabled=True)
            camera_container.content = camera
            camera_container.visible = True
            page.update()
            cameras = await camera.get_available_cameras()
            if not cameras:
                raise RuntimeError("No se encontró ninguna cámara")
            await camera.initialize(cameras[0], fc.ResolutionPreset.MEDIUM, enable_audio=False)
        except Exception as ex:
            camera_container.visible = False
            mostrar_snackbar(page, f"❌ Error al abrir cámara: {ex}", color="red")

    async def capturar_foto(e):
        if camera:
            try:
                image_data = await camera.take_picture()
                await limpiar_camara()
                procesar_imagen_capturada(image_data)
            except Exception as ex:
                mostrar_snackbar(page, f"❌ Error al capturar: {ex}", color="red")

    def cerrar_camara(e):
        asyncio.create_task(limpiar_camara())
        restaurar_formulario()

    async def abrir_galeria_accion(e):
        try:
            archivos = await file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if archivos:
                archivo = archivos[0]
                extension = os.path.splitext(archivo.name or archivo.path or "")[1].lower()
                if extension in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp", ".mpeg", ".mpg"}:
                    mostrar_snackbar(
                        page,
                        "🎥 Por ahora solo puedes agregar imágenes. Los videos aún no están disponibles 😊",
                        color="orange",
                    )
                    return
                ruta = archivo.path
                datos_imagen = normalizar_datos_imagen(archivo.bytes)
                if datos_imagen:
                    os.makedirs("temp", exist_ok=True)
                    extension = extension or ".jpg"
                    ruta = os.path.join("temp", f"seleccion_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{extension}")
                    with open(ruta, "wb") as image_file:
                        image_file.write(datos_imagen)
                if not ruta:
                    mostrar_snackbar(page, "❌ No se pudo obtener la imagen seleccionada", color="red")
                    return
                await limpiar_camara()
                restaurar_formulario()
                if destino_imagen:
                    destino_imagen(ruta, datos_imagen)
        except Exception as ex:
            mostrar_snackbar(page, f"❌ Error al abrir galería: {ex}", color="red")

    def mostrar_interfaz_camara(callback_imagen):
        nonlocal destino_imagen
        controles_anteriores.clear()
        controles_anteriores.extend(page.controls)
        destino_imagen = callback_imagen
        page.clean()
        page.add(
            ft.SafeArea(
                content=ft.Column(
                    [
                        ft.Text("📸 Seleccionar imagen", size=24, weight=ft.FontWeight.BOLD),
                        camera_container,
                        ft.Row(
                            [
                                ft.ElevatedButton("🖼️ Abrir Galería", on_click=abrir_galeria_accion, bgcolor="#168AAD", color="white", width=180),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        ft.Row(
                            [
                                ft.ElevatedButton("📸 Capturar", on_click=capturar_foto, bgcolor="#EFA520", color="white", width=180),
                                ft.ElevatedButton("↩️ Cerrar", on_click=cerrar_camara, bgcolor="red", color="white", width=180),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                    expand=True,
                )
            )
        )
        page.update()

    def abrir_camara_segura(callback_imagen):
        if page.platform != ft.PagePlatform.ANDROID:
            mostrar_aviso_camara_no_disponible()
            return
        mostrar_interfaz_camara(callback_imagen)
        asyncio.create_task(abrir_camara_accion(None))

    def abrir_selector(e, callback_imagen=procesar_imagen):
        abrir_selector_imagen(
            page,
            callback_imagen,
            title="Seleccionar imagen",
            on_cancel=lambda: page.update(),
        )

    # BOTONES DE IMAGEN: seleccionar, reemplazar y quitar cada imagen del producto.
    ancho_btn_imagen_1 = 280
    ancho_btn_imagen_2 = 280
    btn_imagen = ft.ElevatedButton(
        "📷 Seleccionar imagen",
        on_click=abrir_selector,
        width=ancho_btn_imagen_1,
    )
    btn_reemplazar_imagen = ft.TextButton(
        "Reemplazar imagen",
        on_click=abrir_selector,
        visible=False,
    )
    btn_quitar_imagen = ft.TextButton(
        "Quitar imagen",
        on_click=quitar_imagen,
        visible=False,
    )
    imagen_preview_2 = ft.Container(bgcolor="#F3F3F3", border_radius=12, visible=False)
    btn_imagen_2 = ft.ElevatedButton(
        "📷 Seleccionar segunda imagen",
        on_click=lambda e: abrir_selector(e, procesar_imagen_2),
        width=ancho_btn_imagen_2,
    )
    btn_reemplazar_imagen_2 = ft.TextButton(
        "Reemplazar segunda imagen",
        on_click=lambda e: abrir_selector(e, procesar_imagen_2),
        visible=False,
    )
    btn_quitar_imagen_2 = ft.TextButton(
        "Quitar segunda imagen",
        on_click=quitar_imagen_2,
        visible=False,
    )

    # ==========================================
    # REGISTRO
    # ==========================================
    def hacer_registro(nombre, marca, talla, precio, precio_dolares, cantidad, tienda_id, descripcion="", estado_producto="Nuevo", etiquetas="", color_principal="", material="", garantia="", especificacion=""):
        nonlocal imagen_producto_path, imagen_producto_data, imagen_producto_2_path, imagen_producto_2_data
        try:
            imagen_rel = None
            imagen_rel_2 = None

            ruta_imagen_principal = imagen_producto_path or imagen_producto_2_path
            if ruta_imagen_principal:
                imagen_rel = guardar_imagen_en_assets(ruta_imagen_principal, prefijo="producto")

            if imagen_producto_path and imagen_producto_2_path:
                imagen_rel_2 = guardar_imagen_en_assets(imagen_producto_2_path, prefijo="producto_2")
            db.registrar_producto(
                nombre, marca, talla, precio, precio_dolares, cantidad,
                tienda_id, imagen_rel, usuario["id"], categoria_input.value, imagen_rel_2,
                descripcion, estado_producto, etiquetas, None, color_principal, material, garantia, especificacion,
            )
            resultado_texto.value = f"✅ '{nombre}' registrado con éxito."
            resultado_texto.color = "green"
            nombre_input_reg.value = ""
            marca_input.value = ""
            talla_input.value = ""
            precio_input_reg.value = ""
            cantidad_input.value = ""
            descripcion_input.value = ""
            estado_input.value = "Nuevo"
            etiquetas_input.value = ""
            color_input.value = ""
            material_input.value = ""
            garantia_input.value = ""
            especificacion_input.value = ""
            imagen_producto_path = None
            imagen_producto_data = None
            imagen_producto_2_path = None
            imagen_producto_2_data = None
            imagen_preview.visible = False
            imagen_preview.content = None
            imagen_preview_2.visible = False
            imagen_preview_2.content = None
            btn_reemplazar_imagen.visible = False
            btn_quitar_imagen.visible = False
            btn_reemplazar_imagen_2.visible = False
            btn_quitar_imagen_2.visible = False
            page.update()
        except Exception as e:
            print(f"❌ Error al registrar producto: {e}")
            mostrar_snackbar(page, f"❌ Error al registrar: {e}", color="red")

    def mostrar_dialogo_tienda(nombre, marca, talla, precio, precio_dolares, cantidad, descripcion="", estado_producto="Nuevo", etiquetas="", color_principal="", material="", garantia="", especificacion=""):
        tiendas_usuario = db.obtener_tiendas_usuario(usuario['id'])
        if not tiendas_usuario:
            hacer_registro(nombre, marca, talla, precio, precio_dolares, cantidad, None, descripcion, estado_producto, etiquetas, color_principal, material, garantia, especificacion)
            return

        def hacer_seleccion(id_tienda):
            def seleccionar(e):
                dlg.open = False
                page.update()
                hacer_registro(nombre, marca, talla, precio, precio_dolares, cantidad, id_tienda, descripcion, estado_producto, etiquetas, color_principal, material, garantia, especificacion)
            return seleccionar

        botones_tiendas = []
        for t in tiendas_usuario:
            botones_tiendas.append(
                ft.ElevatedButton(
                    f"🏪 {t[1]}",
                    on_click=hacer_seleccion(t[0]),
                    bgcolor="#040D4A",
                    color="white",
                    width=250,
                )
            )

        def cancelar(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("¿A qué tienda desea registrar?"),
            content=ft.Column(botones_tiendas, spacing=10, tight=True),
            actions=[ft.TextButton("↩️ Cancelar", on_click=cancelar)],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def accion_principal(e):
        nonlocal tasa_calculadora
        try:
            if modo_registrar:
                nombre = nombre_input_reg.value.strip()
                if not nombre:
                    resultado_texto.value = "Ingrese el nombre del producto"
                    resultado_texto.color = "red"
                    page.update()
                    return
                try:
                    precio = float(precio_input_reg.value)
                    cantidad = int(cantidad_input.value)
                except:
                    resultado_texto.value = "Precio y cantidad deben ser números válidos"
                    resultado_texto.color = "red"
                    page.update()
                    return
                tasa_actual = tienda[3] if tienda else 36.5
                precio_dolares = round(precio / tasa_actual, 2)
                marca = marca_input.value.strip() if marca_input.value else ""
                talla = talla_input.value.strip() if talla_input.value else ""
                descripcion = descripcion_input.value.strip() if descripcion_input.value else ""
                estado_producto = estado_input.value or "Nuevo"
                etiquetas = etiquetas_input.value.strip() if etiquetas_input.value else ""
                color_principal = color_input.value.strip() if color_input.value else ""
                material = material_input.value.strip() if material_input.value else ""
                garantia = garantia_input.value.strip() if garantia_input.value else ""
                especificacion = especificacion_input.value.strip() if especificacion_input.value else ""
                mostrar_dialogo_tienda(nombre, marca, talla, precio, precio_dolares, cantidad, descripcion, estado_producto, etiquetas, color_principal, material, garantia, especificacion)
            else:
                try:
                    precio = float(str(precio_input_cal.value).replace(",", "."))
                    tasa_actual = float(str(tasa_input_cal.value).replace(",", "."))
                    porcentaje = float(str(porcentaje_input_cal.value or "0").replace(",", "."))
                except (TypeError, ValueError):
                    resultado_texto.value = "Cantidad, tasa y porcentaje deben ser números válidos 😊"
                    resultado_texto.color = "red"
                    page.update()
                    return
                if precio < 0 or tasa_actual <= 0 or porcentaje < 0:
                    resultado_texto.value = "La cantidad y el porcentaje no pueden ser negativos; la tasa debe ser mayor que cero 😊"
                    resultado_texto.color = "red"
                    page.update()
                    return
                tasa_calculadora = tasa_actual
                if moneda_cal.value == "C$":
                    total_c = precio
                    total_d = precio / tasa_actual
                else:
                    total_d = precio
                    total_c = precio * tasa_actual
                simbolo_entrada = "C$" if moneda_cal.value == "C$" else "$"
                porcentaje_resultado = precio * porcentaje / 100
                resultado_texto.value = (
                    f"Conversión: C${total_c:.2f} / ${total_d:.2f}"
                )
                if porcentaje_input_cal.value.strip():
                    resultado_texto.value += (
                        f"\nEl {porcentaje:.2f}% de {simbolo_entrada}{precio:.2f} "
                        f"es {simbolo_entrada}{porcentaje_resultado:.2f}"
                    )
                resultado_texto.color = "green"
                precio_input_cal.value = ""
                page.update()
        except Exception as e:
            print(f"❌ Error en accion_principal: {e}")
            mostrar_snackbar(page, f"❌ Error: {e}", color="red")

    nombre_input_reg.on_submit = accion_principal
    precio_input_reg.on_submit = accion_principal
    cantidad_input.on_submit = accion_principal
    tasa_input_cal.on_submit = accion_principal
    precio_input_cal.on_submit = accion_principal
    porcentaje_input_cal.on_submit = accion_principal

    # BOTONES DE REGISTRO: alternan formulario/calculadora, limpian y regresan al menú.
    ancho_btn_modo = 190
    ancho_btn_limpiar = 150
    ancho_btn_volver = 180
    btn_modo = ft.ElevatedButton(content=ft.Text("Registrar Producto"), on_click=accion_principal, bgcolor="#EFA520", width=ancho_btn_modo)
    btn_alternativo = ft.TextButton(content=ft.Text("Cambiar a Modo Calculadora"), on_click=cambiar_modo)
    btn_limpiar_cal = ft.TextButton("Borrar datos", on_click=limpiar_calculadora, visible=False, width=ancho_btn_limpiar)
    btn_volver_menu = ft.ElevatedButton("↩️ Volver al Menu", on_click=lambda e: go_back(usuario), width=ancho_btn_volver)
    form = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                titulo_formulario,
                tasa_texto,
                nombre_input_reg,
                categoria_input,
                marca_input,
                talla_input,
                precio_input_reg,
                cantidad_input,
                descripcion_input,
                estado_input,
                etiquetas_input,
                color_input,
                material_input,
                garantia_input,
                especificacion_input,
                ft.Column([
                    btn_imagen,
                    btn_reemplazar_imagen,
                    btn_quitar_imagen,
                    imagen_preview,
                    btn_imagen_2,
                    btn_reemplazar_imagen_2,
                    btn_quitar_imagen_2,
                    imagen_preview_2,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                tasa_input_cal,
                moneda_cal,
                precio_input_cal,
                porcentaje_input_cal,
                btn_modo,
                resultado_texto,
                btn_limpiar_cal,
                ft.Row(
                    [btn_alternativo],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row(
                    [btn_volver_menu],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=12,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=20,
    )

    # IMPORTANTE: esta estructura de centrado es la base del formulario.
    # NO MODIFICAR ni mover el Stack/SafeArea aunque se agreguen más campos,
    # más imágenes o nuevos inputs. La correcta lógica es mantener todo centrado.
    page.add(
        ft.Stack(
            [
                fondo,
                ft.SafeArea(form),
            ],
            expand=True
        )
    )