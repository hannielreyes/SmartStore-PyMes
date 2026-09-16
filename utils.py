import asyncio
import base64
import inspect
import json
import mimetypes
import os
import re
import shutil
import threading
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
import flet as ft
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

APP_VERSION = "0.1.0"  # This line remains unchanged, but is included for context

# Compatibilidad con versiones de Flet donde se usa ft.fontweight (minúsculas)
if hasattr(ft, "FontWeight") and not hasattr(ft, "fontweight"):
    ft.fontweight = ft.FontWeight

# Logging setup
_logger = None

def get_logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger("smartstore")
        _logger.setLevel(logging.INFO)
        log_path = Path(__file__).resolve().parent / "smartstore.log"
        handler = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        _logger.addHandler(handler)
    return _logger

def log_error(message, exc_info=True):
    get_logger().error(message, exc_info=exc_info)

# Intentar importar flet_camera solo si está disponible
try:
    import flet_camera as fc
    CAMERA_DISPONIBLE = True
except ImportError:
    CAMERA_DISPONIBLE = False
    print("⚠️ flet_camera no instalado. Instala con: pip install flet_camera")

# ==========================================
# DETECCIÓN DE PLATAFORMA
# ==========================================

def _es_android(page: ft.Page) -> bool:
    """Detecta si la app está corriendo en Android (APK)."""
    try:
        plataforma = getattr(page, "platform", None)
        if plataforma is not None:
            valor = str(plataforma).lower()
            if valor in {"android", "android_tv", "android-tv"}:
                return True
            if "android" in valor:
                return True
    except Exception:
        pass

    try:
        import platform
        sistema = str(platform.system()).lower()
        return sistema == "android"
    except Exception:
        return False


def obtener_ruta_archivo(archivo):
    if not archivo:
        return None
    for attr in ("path", "name", "src"):
        valor = getattr(archivo, attr, None)
        if isinstance(valor, str) and valor.strip():
            return valor
    return None


def mostrar_snackbar(page: ft.Page, mensaje, color=None, duracion=4000):
    if not page:
        return
    if isinstance(mensaje, ft.Text):
        content = mensaje
    else:
        texto = str(mensaje)
        if not any(simbolo in texto for simbolo in ("✅", "❌", "⚠️", "😊", "💙", "🔎", "⏳", "📸", "💳", "❗")):
            texto = f"💙 {texto} 😊"
        content = ft.Text(texto, color=color or "white")
    snackbar = ft.SnackBar(
        content=content,
        duration=duracion,
        bgcolor="#1E1E1E",
    )
    page.snack_bar = snackbar
    page.snack_bar.open = True
    page.update()


NOTIFICACIONES_ACTIVAS_KEY = "smartstore_notifications_enabled"


def _ruta_preferencias_notificaciones():
    directorio = os.environ.get("FLET_APP_STORAGE_DATA")
    if directorio:
        base = Path(directorio)
    else:
        base = Path(__file__).resolve().parent / "storage"
    base.mkdir(parents=True, exist_ok=True)
    return base / "preferencias_notificaciones.json"


def notificaciones_activas(page):
    """Devuelve si el usuario permite avisos informativos dentro de la app."""
    try:
        with _ruta_preferencias_notificaciones().open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if NOTIFICACIONES_ACTIVAS_KEY in datos:
            return bool(datos[NOTIFICACIONES_ACTIVAS_KEY])
    except Exception:
        pass

    try:
        valor = page.client_storage.get(NOTIFICACIONES_ACTIVAS_KEY)
        if valor is not None:
            return bool(valor)
    except Exception:
        pass
    return getattr(page, "_notificaciones_activas", True)


def establecer_notificaciones(page, activas):
    """Guarda la preferencia de avisos para futuras sesiones."""
    activas = bool(activas)
    page._notificaciones_activas = activas
    try:
        page.client_storage.set(NOTIFICACIONES_ACTIVAS_KEY, activas)
    except Exception:
        pass
    try:
        with _ruta_preferencias_notificaciones().open("w", encoding="utf-8") as archivo:
            json.dump({NOTIFICACIONES_ACTIVAS_KEY: activas}, archivo)
    except OSError:
        pass
    return activas


def boton_glossy(texto, on_click=None, color="#EFA520", text_color="#0A2540", width=None, height=46, icon=None):
    """Crea un botón reutilizable con el estilo visual principal de la aplicación."""
    # COMPONENTE DE BOTÓN: centraliza texto, icono, colores, tamaño y acción.
    contenido = ft.Text(str(texto), size=15, weight=ft.FontWeight.BOLD, color=text_color)
    if icon:
        contenido = ft.Row(
            [
                ft.Icon(icon, size=18, color=text_color),
                contenido,
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    # CONSTRUCCIÓN: devuelve el botón que utilizan varias pantallas.
    return ft.ElevatedButton(
        content=contenido,
        on_click=on_click,
        width=width,
        height=height,
        bgcolor=color,
        color=text_color,
        elevation=8,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=14),
            padding=ft.Padding(12, 10, 12, 10),
            overlay_color="rgba(255,255,255,0.18)",
        ),
    )


def configurar_retroceso(page: ft.Page, callback):
    """Conecta el botón o gesto de retroceso del teléfono con la vista actual.
    """
    # Variable global para guardar el callback de retroceso
    global _retroceso_callback
    _retroceso_callback = callback

    retroceso_en_proceso = False

    def manejar_retroceso(e=None):
        nonlocal retroceso_en_proceso
        if retroceso_en_proceso:
            return
        retroceso_en_proceso = True
        try:
            if _retroceso_callback is not None:
                _retroceso_callback()
        finally:
            retroceso_en_proceso = False

    def manejar_tecla(e):
        tecla = str(getattr(e, "key", "")).strip().lower()
        if tecla in {"goback", "browserback", "escape", "back"}:
            try:
                if hasattr(e, "prevent_default"):
                    e.prevent_default()
            except Exception:
                pass
            manejar_retroceso(e)

    page.on_view_pop = manejar_retroceso
    page.on_keyboard_event = manejar_tecla

    try:
        if hasattr(page, "window"):
            plataforma = getattr(page, "platform", None)
            if plataforma in (ft.PagePlatform.ANDROID, ft.PagePlatform.ANDROID_TV, ft.PagePlatform.IOS):
                page.window.prevent_close = True
            else:
                page.window.prevent_close = False
    except Exception:
        pass


def _obtener_directorio_imagenes():
    env_path = os.environ.get("FLET_APP_STORAGE_DATA")
    if env_path:
        try:
            path = Path(env_path)
            path.mkdir(parents=True, exist_ok=True)
            return path
        except Exception:
            pass

    cwd_path = Path.cwd()
    if cwd_path.exists():
        candidates = [cwd_path / "storage" / "data", cwd_path / "storage", cwd_path]
        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate
            except Exception:
                continue

    base_dir = Path(__file__).resolve().parent
    candidates = [base_dir / "storage" / "data", base_dir / "storage", base_dir]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue

    return Path.cwd()


def guardar_imagen_en_assets(origen: str | None, prefijo: str = "img"):
    if not origen:
        return None

    # Si ya viene como URL o data URI, no hay que volver a procesarla.
    if isinstance(origen, str) and origen.startswith(("http://", "https://", "data:")):
        return origen

    if not os.path.exists(origen):
        return None

    base_dir = _obtener_directorio_imagenes()
    uploads_dir = base_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(origen).suffix.lower() or ".png"
    nombre_archivo = f"{prefijo}_{uuid.uuid4().hex}{extension}"
    destino = uploads_dir / nombre_archivo
    shutil.copy2(origen, destino)

    ruta_local = str(destino.resolve())
    try:
        from supabase_config import subir_archivo_storage
        url_remota = subir_archivo_storage(ruta_local, carpeta=prefijo)
        if url_remota:
            return url_remota
    except Exception as error:
        log_error(f"No se pudo subir imagen a Supabase Storage: {error}", exc_info=False)

    try:
        tipo = mimetypes.guess_type(ruta_local)[0] or "image/jpeg"
        with open(ruta_local, "rb") as archivo:
            contenido = base64.b64encode(archivo.read()).decode("ascii")
        return f"data:{tipo};base64,{contenido}"
    except OSError as error:
        log_error(f"No se pudo preparar imagen compartida: {error}", exc_info=False)
    return ruta_local


def imagen_disponible(ruta):
    """Acepta una URL compartida o una ruta local existente."""
    return bool(ruta) and (
        str(ruta).startswith(("http://", "https://", "data:"))
        or os.path.exists(str(ruta))
    )


def normalizar_whatsapp(whatsapp: str | None):
    """Normaliza un número de WhatsApp para usarlo en URLs y app links."""
    if whatsapp is None:
        return None

    texto = str(whatsapp).strip()
    texto = re.sub(r"[^0-9+]", "", texto)

    if not texto:
        return None

    if texto.startswith("+"):
        texto = texto[1:]

    if len(texto) < 8 or not texto.isdigit():
        return None

    if len(texto) == 8:
        texto = f"505{texto}"

    return texto


def construir_url_whatsapp(whatsapp: str | None, mensaje: str = ""):
    numero = normalizar_whatsapp(whatsapp)
    if not numero:
        return None

    url = f"https://wa.me/{numero}"
    texto = (mensaje or "").strip()
    if texto:
        url += f"?text={quote(texto)}"
    return url


def construir_url_whatsapp_app(whatsapp: str | None, mensaje: str = ""):
    """Construye el enlace directo para abrir la aplicación WhatsApp."""
    numero = normalizar_whatsapp(whatsapp)
    if not numero:
        return None

    url = f"whatsapp://send?phone={numero}"
    texto = (mensaje or "").strip()
    if texto:
        url += f"&text={quote(texto)}"
    return url


def abrir_whatsapp(page: ft.Page, whatsapp: str | None, mensaje: str = "") -> bool:
    """Confirma la intención del cliente y abre el chat de la tienda."""
    if not page:
        return False

    numero = normalizar_whatsapp(whatsapp)
    if not numero:
        return False

    texto = (mensaje or "").strip()
    url_app = f"whatsapp://send?phone={numero}"
    if texto:
        url_app += f"&text={quote(texto)}"

    url_web = f"https://wa.me/{numero}"
    if texto:
        url_web += f"?text={quote(texto)}"

    def cerrar_dialogo(e):
        dialogo.open = False
        page.update()

    async def lanzar_url(url):
        resultado = page.launch_url(url)
        if inspect.isawaitable(resultado):
            await resultado

    async def continuar_a_whatsapp(e):
        dialogo.open = False
        page.update()
        try:
            plataforma = getattr(page, "platform", None)
            es_android = plataforma == ft.PagePlatform.ANDROID or "android" in str(plataforma).lower()

            if es_android:
                await lanzar_url(url_app)
                return

            if webbrowser.open(url_web, new=2):
                return
            await lanzar_url(url_web)
        except Exception:
            try:
                await lanzar_url(url_web)
            except Exception:
                pass

    async def abrir_enlace_web(e):
        dialogo.open = False
        page.update()
        try:
            await lanzar_url(url_web)
        except Exception:
            pass

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Contactar con la tienda 💬", size=20, weight=ft.FontWeight.BOLD),
        content=ft.Text(
            "¿Quieres escribirle a la tienda por WhatsApp? 📲\n\n"
            "Te ayudaremos a resolver tus dudas sobre este producto 😊"
        ),
        actions=[
            ft.TextButton("Ahora no", on_click=cerrar_dialogo),
            ft.TextButton("Abrir en navegador 🌐", on_click=abrir_enlace_web),
            ft.ElevatedButton("Escribir por WhatsApp 💚", on_click=continuar_a_whatsapp),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(dialogo)
    dialogo.open = True
    page.update()
    return True


async def abrir_url(page: ft.Page, url: str | None):
    if not url:
        return False
    try:
        plataforma = str(getattr(page, "platform", "")).lower()
        es_movil = "android" in plataforma or "ios" in plataforma

        if not es_movil and webbrowser.open(url, new=2):
            return True

        launcher = getattr(page, "launch_url", None)
        if launcher is None:
            return False
        resultado = launcher(url)
        if inspect.isawaitable(resultado):
            await resultado
        return True
    except Exception as exc:
        print(f"❌ No se pudo abrir la URL {url}: {exc}")
        return False


def abrir_url_en_background(page: ft.Page, url: str | None):
    if not url:
        return False

    def ejecutar_apertura():
        try:
            asyncio.run(abrir_url(page, url))
        except Exception as exc:
            print(f"❌ No se pudo abrir la URL en segundo plano {url}: {exc}")

    threading.Thread(target=ejecutar_apertura, daemon=True).start()
    return True


def _version_comparable(version):
    try:
        return tuple(int(parte) for parte in str(version).strip().lstrip("v").split("."))
    except (TypeError, ValueError):
        return ()


async def comprobar_actualizacion(page: ft.Page):
    """Muestra una actualización disponible en cada arranque, sin guardar estado."""
    try:
        await asyncio.sleep(1.5)
        from supabase_config import APP_VERSION as CONFIGURED_APP_VERSION, SUPABASE_UPDATE_URL

        update_url = SUPABASE_UPDATE_URL
        if not update_url:
            return

        def descargar_manifest():
            with urlopen(update_url, timeout=6) as response:
                return json.loads(response.read().decode("utf-8"))

        manifest = await asyncio.to_thread(descargar_manifest)
        version_remota = manifest.get("version")
        enlace = manifest.get("url")
        version_local = CONFIGURED_APP_VERSION or APP_VERSION
        if not enlace or _version_comparable(version_remota) <= _version_comparable(version_local):
            return

        def cerrar(e):
            aviso.open = False
            page.update()

        async def actualizar(e):
            aviso.open = False
            page.update()
            await abrir_url(page, enlace)

        aviso = ft.AlertDialog(
            modal=False,
            title=ft.Text("Nueva versión disponible", weight=ft.FontWeight.BOLD, color="#040D4A"),
            content=ft.Text(
                f"SmartStore tiene disponible la versión {version_remota}.\n"
                "Puedes actualizarla cuando quieras."
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=cerrar),
                ft.ElevatedButton("Actualizar", on_click=actualizar, bgcolor="#168AAD", color="white"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(aviso)
        aviso.open = True
        page.update()
    except Exception as exc:
        log_error(f"No se pudo comprobar actualizacion: {exc}", exc_info=False)
        return False


# ==========================================
# SELECCIONADOR DE IMÁGENES CON FT.CAMERA
# ==========================================

def _cerrar_dialogo_seguro(page, dialogo):
    """Cierra el diálogo activo sin dejarlo bloqueando la vista de Flet."""
    try:
        if dialogo is not None:
            try:
                dialogo.open = False
            except Exception:
                pass
            try:
                if getattr(page, "dialog", None) is dialogo:
                    page.dialog = None
            except Exception:
                pass
            try:
                if dialogo in list(getattr(page, "overlay", [])):
                    page.overlay.remove(dialogo)
            except Exception:
                pass
    except Exception:
        pass

    try:
        if hasattr(page, "overlay") and page.overlay:
            for item in list(page.overlay):
                try:
                    if hasattr(item, "open") and item is not dialogo:
                        item.open = False
                except Exception:
                    pass
    except Exception:
        pass

    try:
        if hasattr(page, "update"):
            page.update()
    except Exception:
        pass


def _mostrar_aviso_camara_no_disponible(page, on_cancel=None):
    """Muestra el mismo aviso visual de cámara no disponible en todas las vistas."""
    aviso = None

    def cerrar_aviso(e=None):
        aviso.open = False
        page.update()
        if on_cancel:
            on_cancel()

    aviso = ft.AlertDialog(
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
                on_click=cerrar_aviso,
                bgcolor="#040D4A",
                color="white",
            )
        ],
        actions_alignment=ft.MainAxisAlignment.CENTER,
    )

    page.overlay.append(aviso)
    aviso.open = True
    page.update()


def _limpiar_dialogos_selector_imagen(page):
    """Elimina diálogos del selector que podrían dejar una capa modal bloqueada."""
    try:
        for item in list(getattr(page, "overlay", [])):
            if isinstance(item, ft.AlertDialog):
                item.open = False
                page.overlay.remove(item)
        if isinstance(getattr(page, "dialog", None), ft.AlertDialog):
            page.dialog.open = False
            page.dialog = None
        page.update()
    except Exception:
        pass


def abrir_selector_imagen(page: ft.Page, callback, title="Seleccionar imagen", allowed_extensions=None, on_cancel=None):
    """Abre el selector con el mismo flujo de crear_tienda y registrar_producto."""
    # Selecciona la interfaz de cámara o galería según la plataforma actual.
    if _es_android(page):
        _abrir_selector_android(page, callback, title, on_cancel=on_cancel)
        return

    _abrir_selector_desktop(page, callback, title, on_cancel=on_cancel)


def _abrir_selector_desktop(page, callback, title="Seleccionar imagen", on_cancel=None):
    """Muestra el diálogo común y abre el selector nativo al elegir Galería."""
    # Diálogo de escritorio: botones, colores y acciones para cámara o galería.
    dialogo = None
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    def cerrar_dialogo():
        dialogo.open = False
        page.update()

    def abrir_camara(e):
        cerrar_dialogo()
        mostrar_snackbar(page, "💙 La cámara solo está disponible en Android. 📱✨", color="orange")
        _mostrar_aviso_camara_no_disponible(page, on_cancel=on_cancel)

    async def abrir_galeria(e):
        cerrar_dialogo()
        try:
            archivos = await file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if not archivos:
                if on_cancel:
                    on_cancel()
                return

            archivo = archivos[0]
            ruta = archivo.path
            if not ruta:
                mostrar_snackbar(page, "❌ No se pudo obtener la imagen seleccionada", color="red")
                return

            callback(str(Path(ruta).resolve()))
        except Exception as exc:
            mostrar_snackbar(page, f"❌ Error al abrir la galería: {exc}", color="red")
        finally:
            try:
                if file_picker in page.services:
                    page.services.remove(file_picker)
            except Exception:
                pass
            dialogo.open = False
            page.update()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=ft.Text("Elige una opción:"),
        actions=[
            ft.ElevatedButton("📷 Cámara", on_click=abrir_camara, bgcolor="#040D4A", color="white"),
            ft.ElevatedButton("🖼️ Galería", on_click=abrir_galeria, bgcolor="#168AAD", color="white"),
        ],
        actions_alignment=ft.MainAxisAlignment.CENTER,
    )
    page.overlay.append(dialogo)
    dialogo.open = True
    page.update()


def _abrir_selector_fallback(page, callback, title="Seleccionar imagen", on_cancel=None):
    """Selector nativo del sistema para la opción Galería en escritorio."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        ruta = filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("Imágenes", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                ("Todos los archivos", "*.*"),
            ],
        )
        root.update()
        root.destroy()

        if not ruta:
            if on_cancel:
                on_cancel()
            return False

        destino = Path(ruta)
        if not destino.exists():
            if on_cancel:
                on_cancel()
            return False

        callback(str(destino.resolve()))
        _limpiar_dialogos_selector_imagen(page)
        return True
    except Exception as exc:
        mostrar_snackbar(page, f"❌ Error al abrir el selector del sistema: {exc}", color="red")
        if on_cancel:
            on_cancel()
        return False


def _abrir_selector_android(page, callback, title="Seleccionar imagen", on_cancel=None):
    # Diálogo de Android: conecta los botones con FilePicker y la cámara nativa.
    file_picker = ft.FilePicker()
    if file_picker not in list(getattr(page, "services", [])):
        page.services.append(file_picker)
    page.update()

    def cerrar_dialogo():
        dialogo.open = False
        page.update()

    def finalizar_cancelacion():
        if on_cancel:
            on_cancel()

    async def abrir_galeria(e):
        cerrar_dialogo()
        try:
            archivos = await file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if not archivos:
                finalizar_cancelacion()
                return

            archivo = archivos[0]
            datos = archivo.bytes
            ruta = archivo.path
            extension = os.path.splitext(archivo.name or ruta or "")[1].lower() or ".jpg"
            if datos:
                temp_dir = _obtener_directorio_imagenes() / "temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                ruta = temp_dir / f"seleccion_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{extension}"
                with open(ruta, "wb") as image_file:
                    image_file.write(bytes(datos))

            if ruta:
                callback(str(Path(ruta).resolve()))
        except Exception as exc:
            mostrar_snackbar(page, f"❌ Error al abrir la galería: {exc}", color="red")
        finally:
            try:
                if file_picker in page.services:
                    page.services.remove(file_picker)
            except Exception:
                pass

    def abrir_camara(e):
        cerrar_dialogo()
        page.update()
        if not _es_android(page):
            _mostrar_aviso_camara_no_disponible(page, on_cancel=on_cancel)
            return
        if not CAMERA_DISPONIBLE:
            _mostrar_aviso_camara_no_disponible(page, on_cancel=on_cancel)
            return
        _abrir_camara_android(page, callback, on_cancel=finalizar_cancelacion)

    acciones = [
        ft.ElevatedButton("📷 Cámara", on_click=abrir_camara, bgcolor="#040D4A", color="white"),
        ft.ElevatedButton("🖼️ Galería", on_click=abrir_galeria, bgcolor="#168AAD", color="white"),
    ]

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=ft.Text("Elige una opción:"),
        actions=acciones,
        actions_alignment=ft.MainAxisAlignment.CENTER,
    )
    if dialogo not in list(getattr(page, "overlay", [])):
        page.overlay.append(dialogo)
    dialogo.open = True
    page.update()


def _abrir_selector_windows(page: ft.Page, callback, title="Seleccionar imagen", allowed_extensions=None, on_cancel=None):
    """Selector de archivos para Windows usando ctypes"""
    try:
        import ctypes
        from ctypes import wintypes

        class OPENFILENAMEW(ctypes.Structure):
            _fields_ = [
                ("lStructSize", wintypes.DWORD),
                ("hwndOwner", wintypes.HWND),
                ("hInstance", wintypes.HINSTANCE),
                ("lpstrFilter", wintypes.LPCWSTR),
                ("lpstrCustomFilter", wintypes.LPWSTR),
                ("nMaxCustFilter", wintypes.DWORD),
                ("nFilterIndex", wintypes.DWORD),
                ("lpstrFile", wintypes.LPWSTR),
                ("nMaxFile", wintypes.DWORD),
                ("lpstrFileTitle", wintypes.LPWSTR),
                ("nMaxFileTitle", wintypes.DWORD),
                ("lpstrInitialDir", wintypes.LPCWSTR),
                ("lpstrTitle", wintypes.LPCWSTR),
                ("Flags", wintypes.DWORD),
                ("nFileOffset", wintypes.WORD),
                ("nFileExtension", wintypes.WORD),
                ("lpstrDefExt", wintypes.LPCWSTR),
                ("lCustData", wintypes.LPARAM),
                ("lpfnHook", wintypes.LPVOID),
                ("lpTemplateName", wintypes.LPCWSTR),
                ("pvReserved", wintypes.LPVOID),
                ("dwReserved", wintypes.DWORD),
                ("FlagsEx", wintypes.DWORD),
            ]

        filter_string = "\0".join([f"Imagen\0*.jpg;*.jpeg;*.png;*.webp"]) + "\0\0"
        buffer = ctypes.create_unicode_buffer(260)
        ofn = OPENFILENAMEW()
        ofn.lStructSize = ctypes.sizeof(ofn)
        ofn.hwndOwner = None
        ofn.lpstrFilter = filter_string
        ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
        ofn.nMaxFile = len(buffer)
        ofn.lpstrFileTitle = None
        ofn.nMaxFileTitle = 0
        ofn.lpstrInitialDir = None
        ofn.lpstrTitle = title
        ofn.Flags = 0x00001000 | 0x00000800 | 0x00000008
        ofn.lpstrDefExt = None
        ofn.nFilterIndex = 1
        ofn.lCustData = 0
        ofn.lpfnHook = None
        ofn.lpTemplateName = None
        ofn.pvReserved = None
        ofn.dwReserved = 0
        ofn.FlagsEx = 0

        if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
            callback(buffer.value)
        else:
            mostrar_snackbar(page, "Selección cancelada. Puedes intentarlo nuevamente 😊", color="orange")
            if on_cancel:
                on_cancel()
    except Exception as exc:
        print(f"❌ Error en selector Windows: {exc}")
        mostrar_snackbar(page, f"Error: {exc}", color="red")


def _abrir_camara_android(page: ft.Page, callback, on_cancel=None):
    """
    Abre la cámara en Android usando el mismo flujo que ya funciona
    en registrar producto y crear tienda.
    """
    prev_controls = list(page.controls)
    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    camera_container = ft.Container(
        width=380,
        height=400,
        bgcolor="#1a1a2e",
        border_radius=10,
        visible=False,
    )
    camera = None

    def restaurar_pagina():
        page.controls.clear()
        page.controls.extend(prev_controls)
        page.update()

    def cerrar_con_retorno():
        try:
            page.controls.clear()
            page.controls.extend(prev_controls)
        except Exception:
            pass
        page.update()
        if on_cancel:
            on_cancel()

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

    def guardar_imagen_capturada(image_data):
        datos = normalizar_datos_imagen(image_data)
        if not datos:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        temp_dir = _obtener_directorio_imagenes() / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        ruta = temp_dir / f"foto_{timestamp}.jpg"
        with open(ruta, "wb") as image_file:
            image_file.write(datos)
        return str(ruta.resolve())

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

    async def abrir_galeria_accion(e=None):
        try:
            archivos = await file_picker.pick_files(
                allow_multiple=False,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
            if not archivos:
                mostrar_snackbar(page, "Selección cancelada", color="orange")
                return

            archivo = archivos[0]
            datos_imagen = normalizar_datos_imagen(archivo.bytes)
            extension = os.path.splitext(archivo.name or archivo.path or "")[1].lower() or ".jpg"
            ruta = archivo.path

            if datos_imagen:
                temp_dir = _obtener_directorio_imagenes() / "temp"
                temp_dir.mkdir(parents=True, exist_ok=True)
                ruta = temp_dir / f"seleccion_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{extension}"
                with open(ruta, "wb") as image_file:
                    image_file.write(datos_imagen)

            if not ruta:
                mostrar_snackbar(page, "❌ Android no entregó la imagen seleccionada", color="red")
                return

            await limpiar_camara()
            restaurar_pagina()
            callback(str(Path(ruta).resolve()))
        except Exception as ex:
            mostrar_snackbar(page, f"❌ Error al seleccionar imagen: {ex}", color="red")

    async def inicializar_camara():
        nonlocal camera
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
            mostrar_snackbar(page, f"❌ Error al inicializar cámara: {ex}", color="red")
            page.update()
            cerrar_con_retorno()

    async def _do_capture():
        nonlocal camera
        if not camera:
            return
        try:
            mostrar_snackbar(page, "Capturando tu imagen... 📸", color="#040D4A")
            page.update()
            image_data = await camera.take_picture()
            ruta = guardar_imagen_capturada(image_data)
            await limpiar_camara()
            restaurar_pagina()
            if ruta:
                callback(str(Path(ruta).resolve()))
            if not ruta:
                mostrar_snackbar(page, "No se capturó ninguna imagen. Inténtalo nuevamente 😊", color="orange")
        except Exception as ex:
            print(f"❌ Error al capturar imagen async: {ex}")
            mostrar_snackbar(page, f"Error al capturar imagen: {ex}", color="red")
            page.update()
            cerrar_con_retorno()

    def capturar(e):
        try:
            asyncio.create_task(_do_capture())
        except Exception as ex:
            print(f"❌ Error al iniciar captura: {ex}")
            mostrar_snackbar(page, f"Error al iniciar captura: {ex}", color="red")
            page.update()

    def cerrar_camara(e=None):
        try:
            asyncio.create_task(limpiar_camara())
        except Exception:
            pass
        restaurar_pagina()

    page.clean()
    page.add(
        ft.SafeArea(
            ft.Column(
                [
                    ft.Text("📸 Seleccionar imagen", size=24, weight=ft.FontWeight.BOLD),
                    camera_container,
                    ft.Divider(height=20, color="transparent"),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "🖼️ Abrir Galería",
                                on_click=abrir_galeria_accion,
                                bgcolor="#168AAD",
                                color="white",
                                width=180,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "📸 Capturar",
                                on_click=capturar,
                                bgcolor="#EFA520",
                                color="white",
                                width=180,
                            ),
                            ft.ElevatedButton(
                                "↩️ Cerrar",
                                on_click=cerrar_camara,
                                bgcolor="red",
                                color="white",
                                width=180,
                            ),
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
    asyncio.create_task(inicializar_camara())
        #   ./build_and_install.ps1

#flet build apk --arch arm64-v8a --yes --no-rich-output
        ## credential.helper=manager
#origin=https://github.com/hannieljosereyesmiranda-bit/TIENDASMART.git

#git add .git commit -m "Describe el cambio" git push


#probando33335888888888888888888888888