import os
import asyncio
import shutil
from datetime import datetime
import flet as ft
from utils import (
    abrir_selector_imagen,
    guardar_imagen_en_assets,
    mostrar_snackbar,
    configurar_retroceso,
)
import database as db
from database.models import ProductoPendiente
import flet_camera as fc
import base64

def crear_tienda_view(page: ft.Page, usuario, go_back):
    # PANTALLA: formulario para crear una tienda y cargar sus imágenes.
    # Pantalla para crear una tienda y registrar sus primeros productos.
    configurar_retroceso(page, lambda: go_back(usuario))
    page.bgcolor = "#FFFFFF"

    contexto = getattr(page, "_smartstore_context", None) or {}
    tiendas_usuario = contexto.get("tiendas")
    if tiendas_usuario is None:
        tiendas_usuario = db.obtener_tiendas_usuario(usuario["id"])

    if tiendas_usuario:
        def volver_desde_aviso(e):
            aviso.open = False
            page.update()
            go_back(usuario)

        ancho_aviso = min(max((page.width or 360) - 80, 280), 520)
        aviso = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "💙 Aviso importante",
                size=18,
                weight=ft.FontWeight.BOLD,
                color="#030F61",
            ),
            content=ft.Container(
                width=ancho_aviso,
                content=ft.Text(
                    "Estimado usuario, usted ya es proveedor en SmartStore. "
                    "La función de múltiples tiendas será una función premium de pago.",
                    size=14,
                    color="#555555",
                ),
            ),
            actions=[
                ft.TextButton("↩️ Volver", on_click=volver_desde_aviso),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(aviso)
        aviso.open = True
        page.update()
        return

    page.clean()

    fondo = ft.Container(
        expand=True,
        image=ft.DecorationImage(src="fondo.png", fit="cover"),
    )

    def mostrar_aviso_camara_no_disponible():
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("💙 Aviso importante", weight=ft.FontWeight.BOLD, color="#040D4A"),
            content=ft.Text(
                "Estimado usuario, te informamos que la cámara solo está disponible "
                "en la versión Android. 📱✨",
                size=15,
            ),
            actions=[
                ft.ElevatedButton(
                    "Entendido 😊",
                    on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                    bgcolor="#040D4A",
                    color="#FFFFFF",
                )
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    nombre_input = ft.TextField(label="Nombre de la tienda", width=300)
    whatsapp_input = ft.TextField(label="WhatsApp (ej: 50588888888)", width=300)
    direccion_input = ft.TextField(label="Dirección exacta de la tienda", width=300)
    tasa_input = ft.TextField(label="Tasa de cambio o ingrese el valor actual del dolar", value="36.5", width=300)

    nombre_prod_input = ft.TextField(label="Nombre del producto", width=300)
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
    precio_input = ft.TextField(label="Precio en C$", width=300)
    cantidad_input = ft.TextField(label="Cantidad", width=300)
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

    productos_layout = ft.Column(spacing=5)
    productos_temp: list[ProductoPendiente] = []
    tienda_imagen_path = None
    tienda_imagen_data = None
    producto_imagen_path = None
    producto_imagen_data = None
    producto_imagen_2_path = None
    producto_imagen_2_data = None
    tienda_imagen_preview = ft.Container(bgcolor="#F3F3F3", border_radius=12, visible=False)
    producto_imagen_preview = ft.Container(bgcolor="#F3F3F3", border_radius=12, visible=False)

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

    def procesar_imagen_tienda(ruta, image_data=None):
        nonlocal tienda_imagen_path, tienda_imagen_data
        if ruta:
            tienda_imagen_data = normalizar_datos_imagen(image_data)
            if not tienda_imagen_data and os.path.exists(ruta):
                with open(ruta, "rb") as image_file:
                    tienda_imagen_data = image_file.read()
            ruta_guardada = guardar_imagen_en_assets(ruta, prefijo="tienda_seleccion")
            tienda_imagen_path = ruta_guardada or ruta
            tienda_imagen_preview.content = crear_miniatura(tienda_imagen_path, tienda_imagen_data)
            tienda_imagen_preview.visible = True
            btn_reemplazar_logo.visible = True
            btn_quitar_logo.visible = True
            mostrar_snackbar(page, "✅ Logo cargado", color="#1B5E20")
            page.update()

    def quitar_logo(e):
        nonlocal tienda_imagen_path, tienda_imagen_data
        tienda_imagen_path = None
        tienda_imagen_data = None
        tienda_imagen_preview.content = None
        tienda_imagen_preview.visible = False
        btn_reemplazar_logo.visible = False
        btn_quitar_logo.visible = False
        mostrar_snackbar(page, "✅ Logo quitado correctamente 😊", color="#1B5E20")
        page.update()

    def procesar_imagen_producto(ruta, image_data=None):
        nonlocal producto_imagen_path, producto_imagen_data
        if ruta:
            producto_imagen_data = normalizar_datos_imagen(image_data)
            if not producto_imagen_data and os.path.exists(ruta):
                with open(ruta, "rb") as image_file:
                    producto_imagen_data = image_file.read()
            ruta_guardada = guardar_imagen_en_assets(ruta, prefijo="producto_seleccion")
            producto_imagen_path = ruta_guardada or ruta
            producto_imagen_preview.content = crear_miniatura(producto_imagen_path, producto_imagen_data)
            producto_imagen_preview.visible = True
            btn_reemplazar_imagen.visible = True
            btn_quitar_imagen.visible = True
            if producto_imagen_2_path:
                btn_reemplazar_imagen.text = "Reemplazar imagen 1"
                btn_quitar_imagen.text = "Quitar imagen 1"
            mostrar_snackbar(page, "✅ Imagen cargada", color="#1B5E20")
            page.update()

    def procesar_imagen_producto_2(ruta, image_data=None):
        nonlocal producto_imagen_2_path, producto_imagen_2_data
        if ruta:
            producto_imagen_2_data = normalizar_datos_imagen(image_data)
            if not producto_imagen_2_data and os.path.exists(ruta):
                with open(ruta, "rb") as image_file:
                    producto_imagen_2_data = image_file.read()
            ruta_guardada = guardar_imagen_en_assets(ruta, prefijo="producto_2_seleccion")
            producto_imagen_2_path = ruta_guardada or ruta
            producto_imagen_preview_2.content = crear_miniatura(producto_imagen_2_path, producto_imagen_2_data)
            producto_imagen_preview_2.visible = True
            btn_reemplazar_imagen_2.visible = True
            btn_quitar_imagen_2.visible = True
            btn_reemplazar_imagen.text = "Reemplazar imagen 1"
            btn_quitar_imagen.text = "Quitar imagen 1"
            page.update()

    def quitar_imagen(e):
        nonlocal producto_imagen_path, producto_imagen_data
        producto_imagen_path = None
        producto_imagen_data = None
        producto_imagen_preview.content = None
        producto_imagen_preview.visible = False
        btn_reemplazar_imagen.visible = False
        btn_quitar_imagen.visible = False
        mostrar_snackbar(page, "✅ Imagen quitada correctamente 😊", color="#1B5E20")
        page.update()

    def quitar_imagen_2(e):
        nonlocal producto_imagen_2_path, producto_imagen_2_data
        producto_imagen_2_path = None
        producto_imagen_2_data = None
        producto_imagen_preview_2.content = None
        producto_imagen_preview_2.visible = False
        btn_reemplazar_imagen_2.visible = False
        btn_quitar_imagen_2.visible = False
        btn_reemplazar_imagen.text = "Reemplazar imagen"
        btn_quitar_imagen.text = "Quitar imagen"
        page.update()

    # ==========================================
    # Controles de cámara y galería usados por el selector común de imágenes.
    # ==========================================
    camera_container = ft.Container(
        width=380,
        height=400,
        bgcolor="#1a1a2e",
        border_radius=10,
        visible=False,
    )
    imagen_capturada = ft.Image(src="", width=300, height=200, visible=False)
    camera = None
    destino_imagen = None
    controles_anteriores = []
    file_picker = ft.FilePicker()
    page.services.append(file_picker)
    page.update()

    def procesar_imagen_capturada(image_data):
        if image_data:
            if isinstance(image_data, str):
                b64_data = image_data.split(",", 1)[1] if "," in image_data else image_data
                image_data = base64.b64decode(b64_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ruta = f"temp/foto_{timestamp}.jpg"
            os.makedirs("temp", exist_ok=True)
            with open(ruta, "wb") as f:
                f.write(image_data)
            
            restaurar_formulario()
            if destino_imagen:
                destino_imagen(ruta, image_data)
            page.update()
            mostrar_snackbar(page, "✅ Foto capturada", color="#1B5E20")

    async def capturar_foto(e):
        nonlocal camera
        if camera:
            try:
                image_data = await camera.take_picture()
                await limpiar_camara()
                procesar_imagen_capturada(image_data)
            except Exception as ex:
                mostrar_snackbar(page, f"❌ Error: {ex}", color="#B3261E")

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
            mostrar_snackbar(page, f"❌ Error: {ex}", color="#B3261E")
            page.update()

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
                        color="#8A4B08",
                    )
                    return
                datos_imagen = normalizar_datos_imagen(archivo.bytes)
                ruta = archivo.path
                if datos_imagen:
                    os.makedirs("temp", exist_ok=True)
                    extension = extension or ".jpg"
                    ruta = os.path.join(
                        "temp",
                        f"seleccion_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{extension}",
                    )
                    with open(ruta, "wb") as image_file:
                        image_file.write(datos_imagen)
                if not ruta:
                    mostrar_snackbar(page, "❌ Android no entregó la imagen seleccionada", color="#B3261E")
                    return
                await limpiar_camara()
                restaurar_formulario()
                if destino_imagen:
                    destino_imagen(ruta, datos_imagen)
                else:
                    mostrar_snackbar(page, "❌ No se encontró el destino de la imagen", color="#B3261E")
            else:
                mostrar_snackbar(page, "Selección cancelada", color="#8A4B08")
        except Exception as ex:
            mostrar_snackbar(page, f"❌ Error: {ex}", color="#B3261E")

    async def seleccionar_galeria(callback_imagen):
        nonlocal destino_imagen
        destino_imagen = callback_imagen
        await abrir_galeria_accion(None)

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
        modal = ft.Container(
            expand=True,
            bgcolor="#FFFFFF",
            content=ft.Container(
                content=ft.Image(**obtener_fuente_imagen(ruta, image_data), fit="contain"),
                width=360,
                height=520,
                bgcolor="#FFFFFF",
                padding=10,
                alignment=ft.Alignment(0, 0),
            ),
            alignment=ft.Alignment(0, 0),
            on_click=lambda e: (page.overlay.remove(modal), page.update()),
        )
        page.overlay.append(modal)
        page.update()

    def mostrar_interfaz_camara(callback_imagen):
        """Muestra la interfaz de cámara como en camera_test"""
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
                        imagen_capturada,
                        ft.Divider(height=20, color="#00000000"),
                        ft.Row(
                            [
                                ft.ElevatedButton("🖼️ Abrir Galería", on_click=abrir_galeria_accion, bgcolor="#168AAD", color="#040D4A", width=180),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        ft.Row(
                            [
                                ft.ElevatedButton("📸 Capturar", on_click=capturar_foto, bgcolor="#EFA520", color="#040D4A", width=180),
                                ft.ElevatedButton("↩️ Cerrar", on_click=cerrar_camara, bgcolor="#B3261E", color="#FFFFFF", width=180),
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

    # ==========================================
    # Botones de selección, reemplazo y eliminación de logo e imágenes.
    # ==========================================
    def abrir_selector_tienda(e):
        abrir_selector_imagen(
            page,
            procesar_imagen_tienda,
            title="Seleccionar logo de tienda",
            on_cancel=lambda: page.update(),
        )

    def abrir_selector_producto(e, callback_imagen=procesar_imagen_producto):
        abrir_selector_imagen(
            page,
            callback_imagen,
            title="Seleccionar imagen",
            on_cancel=lambda: page.update(),
        )

    # BOTONES DE IMÁGENES: seleccionan, reemplazan o quitan logo y fotos de productos.
    ancho_btn_logo = 280
    ancho_btn_imagen_producto = 280
    ancho_btn_imagen_producto_2 = 280
    btn_imagen = ft.ElevatedButton("📷 Seleccionar logo de tienda", on_click=abrir_selector_tienda, width=ancho_btn_logo)
    producto_imagen_preview_2 = ft.Container(bgcolor="#F3F3F3", border_radius=12, visible=False)
    btn_imagen_producto = ft.ElevatedButton("📷 Seleccionar imagen de producto", on_click=abrir_selector_producto, width=ancho_btn_imagen_producto)
    btn_imagen_producto_2 = ft.ElevatedButton("📷 Seleccionar segunda imagen", on_click=lambda e: abrir_selector_producto(e, procesar_imagen_producto_2), width=ancho_btn_imagen_producto_2)
    btn_reemplazar_logo = ft.TextButton("Reemplazar logo", on_click=abrir_selector_tienda, visible=False)
    btn_reemplazar_imagen = ft.TextButton("Reemplazar imagen", on_click=abrir_selector_producto, visible=False)
    btn_quitar_logo = ft.TextButton("Quitar logo", on_click=quitar_logo, visible=False)
    btn_quitar_imagen = ft.TextButton("Quitar imagen", on_click=quitar_imagen, visible=False)
    btn_reemplazar_imagen_2 = ft.TextButton("Reemplazar segunda imagen", on_click=lambda e: abrir_selector_producto(e, procesar_imagen_producto_2), visible=False)
    btn_quitar_imagen_2 = ft.TextButton("Quitar segunda imagen", on_click=quitar_imagen_2, visible=False)

    def agregar_producto(e):
        nonlocal producto_imagen_path, producto_imagen_data, producto_imagen_2_path, producto_imagen_2_data
        nombre = nombre_prod_input.value
        if not nombre:
            mostrar_snackbar(page, "Escribe el nombre del producto para continuar, por favor 😊")
            return
        try:
            precio = float(precio_input.value)
            cantidad = int(cantidad_input.value)
            tasa = float(tasa_input.value) if tasa_input.value else 36.5
        except:
            mostrar_snackbar(page, "Revisa los datos ingresados para continuar, por favor 😊")
            return

        descripcion = descripcion_input.value.strip() if descripcion_input.value else ""
        estado_producto = estado_input.value or "Nuevo"
        etiquetas = etiquetas_input.value.strip() if etiquetas_input.value else ""
        color_principal = color_input.value.strip() if color_input.value else ""
        material = material_input.value.strip() if material_input.value else ""
        garantia = garantia_input.value.strip() if garantia_input.value else ""
        especificacion = especificacion_input.value.strip() if especificacion_input.value else ""

        productos_temp.append(ProductoPendiente(
            nombre=nombre,
            marca=marca_input.value,
            talla=talla_input.value,
            precio_cordobas=precio,
            precio_dolares=precio / tasa,
            cantidad=cantidad,
            imagen=producto_imagen_path,
            categoria=categoria_input.value,
            imagen_2=producto_imagen_2_path,
            descripcion=descripcion,
            estado_producto=estado_producto,
            etiquetas=etiquetas,
            color_principal=color_principal,
            material=material,
            garantia=garantia,
            especificacion=especificacion,
        ))
        productos_layout.controls.append(ft.Container(content=ft.Text(f"{nombre} | {categoria_input.value} | {marca_input.value or '-'} | {talla_input.value or '-'} | C${precio:.2f} | x{cantidad}"), padding=5, bgcolor="#F5F5F5", border_radius=10))
        nombre_prod_input.value = ""
        categoria_input.value = "General"
        marca_input.value = ""
        talla_input.value = ""
        precio_input.value = ""
        cantidad_input.value = ""
        descripcion_input.value = ""
        estado_input.value = "Nuevo"
        etiquetas_input.value = ""
        color_input.value = ""
        material_input.value = ""
        garantia_input.value = ""
        especificacion_input.value = ""
        producto_imagen_path = None
        producto_imagen_data = None
        producto_imagen_2_path = None
        producto_imagen_2_data = None
        producto_imagen_preview.visible = False
        producto_imagen_preview_2.visible = False
        btn_reemplazar_imagen.visible = False
        btn_quitar_imagen.visible = False
        page.update()

    def guardar_tienda(e):
        tiendas_existentes = db.obtener_tiendas_usuario(usuario['id'])
        if tiendas_existentes:
            mostrar_snackbar(
                page,
                "⚠️ Ya eres proveedor. Crear más tiendas es una función Pro de pago.",
                color="#8A4B08",
            )
            return

        nombre = nombre_input.value.strip()
        if not nombre:
            mostrar_snackbar(page, "Escribe el nombre de tu tienda para continuar, por favor 😊")
            return
        try:
            tasa = float(tasa_input.value) if tasa_input.value else 36.5
        except:
            mostrar_snackbar(page, "⚠️ La tasa de cambio no es válida. Revisa el valor ingresado 😊")
            return

        producto_pendiente = any([
            nombre_prod_input.value,
            marca_input.value,
            talla_input.value,
            precio_input.value,
            cantidad_input.value,
            descripcion_input.value,
            etiquetas_input.value,
            color_input.value,
            material_input.value,
            garantia_input.value,
            especificacion_input.value,
            producto_imagen_path,
            producto_imagen_2_path,
        ])
        if producto_pendiente:
            if not nombre_prod_input.value.strip():
                mostrar_snackbar(page, "Escribe el nombre del producto para guardar sus datos 😊")
                return
            try:
                precio = float(precio_input.value)
                cantidad = int(cantidad_input.value)
            except (TypeError, ValueError):
                mostrar_snackbar(page, "Revisa el precio y la cantidad del producto 😊")
                return
            descripcion = descripcion_input.value.strip() if descripcion_input.value else ""
            estado_producto = estado_input.value or "Nuevo"
            etiquetas = etiquetas_input.value.strip() if etiquetas_input.value else ""
            color_principal = color_input.value.strip() if color_input.value else ""
            material = material_input.value.strip() if material_input.value else ""
            garantia = garantia_input.value.strip() if garantia_input.value else ""
            especificacion = especificacion_input.value.strip() if especificacion_input.value else ""
            productos_temp.append(ProductoPendiente(
                nombre=nombre_prod_input.value.strip(),
                marca=marca_input.value,
                talla=talla_input.value,
                precio_cordobas=precio,
                precio_dolares=precio / tasa,
                cantidad=cantidad,
                imagen=producto_imagen_path,
                categoria=categoria_input.value,
                imagen_2=producto_imagen_2_path,
                descripcion=descripcion,
                estado_producto=estado_producto,
                etiquetas=etiquetas,
                color_principal=color_principal,
                material=material,
                garantia=garantia,
                especificacion=especificacion,
            ))

        imagen_tienda_rel = None
        if tienda_imagen_path:
            imagen_tienda_rel = guardar_imagen_en_assets(tienda_imagen_path, prefijo="tienda")

        tienda_id = db.guardar_tienda(nombre, whatsapp_input.value, tasa, usuario['id'], direccion_input.value.strip(), imagen_tienda_rel)
        if tienda_id is None:
            mostrar_snackbar(
                page,
                "⚠️ Ya eres proveedor. Crear más tiendas es una función Pro de pago.",
                color="#8A4B08",
            )
            return

        for prod in productos_temp:
            imagen_prod_rel = guardar_imagen_en_assets(prod.imagen, prefijo="producto") if prod.imagen else None
            imagen_prod_rel_2 = (
                guardar_imagen_en_assets(prod.imagen_2, prefijo="producto_2")
                if prod.imagen and prod.imagen_2
                else None
            )
            db.registrar_producto(
                prod.nombre,
                prod.marca,
                prod.talla,
                prod.precio_cordobas,
                prod.precio_dolares,
                prod.cantidad,
                tienda_id,
                imagen=imagen_prod_rel,
                usuario_id=usuario["id"],
                categoria=prod.categoria or "General",
                imagen_2=imagen_prod_rel_2,
                descripcion=prod.descripcion,
                estado_producto=prod.estado_producto,
                etiquetas=prod.etiquetas,
                color_principal=prod.color_principal,
                material=prod.material,
                garantia=prod.garantia,
                especificacion=prod.especificacion,
            )

        mostrar_snackbar(page, "✅ ¡Tu tienda fue creada correctamente!")
        go_back(usuario)

    nombre_input.on_submit = guardar_tienda
    whatsapp_input.on_submit = guardar_tienda
    direccion_input.on_submit = guardar_tienda
    tasa_input.on_submit = guardar_tienda
    nombre_prod_input.on_submit = agregar_producto
    marca_input.on_submit = agregar_producto
    talla_input.on_submit = agregar_producto
    precio_input.on_submit = agregar_producto
    cantidad_input.on_submit = agregar_producto

    form = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("Crear Tienda", size=28, weight=ft.FontWeight.BOLD, color="#040D4A"),
                ft.Container(
                    content=ft.Column([
                        ft.Text("1. Datos de la tienda", size=18, weight=ft.FontWeight.BOLD),
                        ft.Column(
                            [btn_imagen, btn_reemplazar_logo, btn_quitar_logo, tienda_imagen_preview],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                        nombre_input, whatsapp_input, direccion_input, tasa_input,
                    ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=15, width=360,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("2. Registrar productos", size=18, weight=ft.FontWeight.BOLD),
                        nombre_prod_input, categoria_input, marca_input, talla_input, precio_input, cantidad_input,
                        descripcion_input, estado_input, etiquetas_input, color_input, material_input, garantia_input, especificacion_input,
                        ft.Column(
                            [btn_imagen_producto, btn_reemplazar_imagen, btn_quitar_imagen, producto_imagen_preview, btn_imagen_producto_2, btn_reemplazar_imagen_2, btn_quitar_imagen_2, producto_imagen_preview_2],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                    ], spacing=14, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=18, width=360,
                ),
                productos_layout,
                ft.Row([
                    ft.ElevatedButton(
                        "Guardar",
                        on_click=guardar_tienda,
                        bgcolor="#FFA726",
                        style=ft.ButtonStyle(
                            padding=ft.Padding(left=24, right=24, top=0, bottom=0),
                        ),
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10, width=360),
                ft.ElevatedButton("↩️ Volver al Menu", on_click=lambda e: go_back(usuario)),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15,
            scroll=ft.Scrollbar(thickness=4, radius=4, interactive=True),
        ),
        padding=20,
    )

    # IMPORTANTE: esta lógica de centrado es parte del sistema visual del app.
    # NO MODIFICAR ni mover el Stack/SafeArea aunque se agreguen más campos,
    # más botones o más contenido; todo debe mantenerse centrado.
    page.add(ft.Stack([fondo, ft.SafeArea(form)], expand=True))