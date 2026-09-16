"""Configuracion segura para la conexion de prueba con Supabase."""

import importlib.util
import json
import os
import mimetypes
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def _cargar_config_build_temporal():
    """Lee la config de build si existe; evita warnings de importación cuando no existe."""
    ruta = os.path.join(os.path.dirname(__file__), "supabase_build_config.py")
    if not os.path.exists(ruta):
        return "", "", "", ""

    spec = importlib.util.spec_from_file_location("supabase_build_config", ruta)
    if spec is None or spec.loader is None:
        return "", "", "", ""

    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return (
        getattr(modulo, "SUPABASE_URL", ""),
        getattr(modulo, "SUPABASE_KEY", ""),
        getattr(modulo, "UPDATE_URL", ""),
        getattr(modulo, "APP_VERSION", ""),
    )


BUILT_SUPABASE_URL, BUILT_SUPABASE_KEY, BUILT_UPDATE_URL, BUILT_APP_VERSION = _cargar_config_build_temporal()
# Estos valores permiten que la app local y la APK compartan la misma configuración remota.


def _cargar_env_local():
    """Carga .env desde la raiz del proyecto y otros ubicaciones comunes."""
    directorios = []
    base_dir = os.path.dirname(__file__)
    for ruta in (base_dir, os.path.dirname(base_dir), os.getcwd()):
        if ruta and ruta not in directorios:
            directorios.append(ruta)

    rutas_env = []
    for directorio in directorios:
        for nombre_archivo in (".env", ".env.local"):
            ruta = os.path.join(directorio, nombre_archivo)
            if os.path.exists(ruta) and ruta not in rutas_env:
                rutas_env.append(ruta)

    for ruta_env in rutas_env:
        try:
            with open(ruta_env, "r", encoding="utf-8") as archivo:
                for linea in archivo:
                    linea = linea.strip()
                    if not linea or linea.startswith("#") or "=" not in linea:
                        continue
                    nombre, valor = linea.split("=", 1)
                    nombre = nombre.strip()
                    valor = valor.strip()
                    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in {'"', "'"}:
                        valor = valor[1:-1]
                    os.environ.setdefault(nombre, valor)
        except OSError:
            continue


_cargar_env_local()

SUPABASE_URL = os.getenv(
    "SMARTSTORE_SUPABASE_URL",
    os.getenv("SUPABASE_URL", BUILT_SUPABASE_URL),
).rstrip("/")
SUPABASE_KEY = os.getenv(
    "SMARTSTORE_SUPABASE_KEY",
    os.getenv("SUPABASE_KEY", BUILT_SUPABASE_KEY),
).strip()
SUPABASE_UPDATE_URL = os.getenv(
    "SMARTSTORE_UPDATE_URL",
    os.getenv("UPDATE_URL", BUILT_UPDATE_URL),
).strip()
APP_VERSION = os.getenv(
    "SMARTSTORE_APP_VERSION",
    os.getenv("APP_VERSION", BUILT_APP_VERSION),
).strip() or "0.1.0"


def _valor_es_placeholder(valor):
    if not valor:
        return True

    valor_limpio = valor.strip().lower()
    placeholders = (
        "tu-proyecto",
        "tu_proyecto",
        "tu-clave",
        "tu_clave_anon_public",
        "tu_clave_anon",
        "tu_key",
        "tu-llave",
        "your-project",
        "your_project",
        "your-key",
        "your_key",
        "example.com",
        "business.example.com",
    )

    if valor_limpio in placeholders:
        return True

    if valor_limpio.startswith("https://tu-proyecto") or valor_limpio.startswith("http://tu-proyecto"):
        return True

    if "tu_proyecto" in valor_limpio or "tu-proyecto" in valor_limpio:
        return True

    if "tu_clave" in valor_limpio or "tu-key" in valor_limpio or "tu_llave" in valor_limpio:
        return True

    return False


def supabase_esta_configurado():
    return (
        bool(SUPABASE_URL)
        and bool(SUPABASE_KEY)
        and not _valor_es_placeholder(SUPABASE_URL)
        and not _valor_es_placeholder(SUPABASE_KEY)
    )


def _headers():
    if not SUPABASE_KEY:
        raise RuntimeError(
            "Falta SMARTSTORE_SUPABASE_KEY. Configura la clave anon/public "
            "antes de probar Supabase."
        )
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def comprobar_conexion():
    """Comprueba que Supabase responde con la clave publica configurada."""
    request = Request(f"{SUPABASE_URL}/auth/v1/settings", headers=_headers(), method="GET")
    try:
        with urlopen(request, timeout=8) as response:
            contenido = response.read().decode("utf-8")
            return response.status, contenido
    except HTTPError as error:
        detalle = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase respondio HTTP {error.code}: {detalle}") from error
    except URLError as error:
        raise RuntimeError(f"No se pudo contactar Supabase: {error.reason}") from error


def supabase_request(tabla, metodo="GET", datos=None, parametros=""):
    """Realiza una peticion REST basica; la API central usara esta funcion."""
    url = f"{SUPABASE_URL}/rest/v1/{tabla}{parametros}"
    url = quote(url, safe=":/?&=,*().-_'%")
    cuerpo = None if datos is None else json.dumps(datos).encode("utf-8")

    ultimo_error = None
    for intento in range(3):
        request = Request(url, data=cuerpo, headers=_headers(), method=metodo.upper())
        try:
            with urlopen(request, timeout=8) as response:
                contenido = response.read().decode("utf-8")
                return response.status, json.loads(contenido) if contenido else None
        except HTTPError as error:
            detalle = error.read().decode("utf-8", errors="replace")
            ultimo_error = RuntimeError(f"Supabase respondio HTTP {error.code}: {detalle}")
            if error.code in (408, 429, 500, 502, 503, 504) and intento < 2:
                continue
            raise ultimo_error from error
        except URLError as error:
            ultimo_error = RuntimeError(f"No se pudo contactar Supabase: {error.reason}")
            if intento < 2:
                continue
            raise ultimo_error from error

    if ultimo_error is not None:
        raise ultimo_error
    raise RuntimeError("Supabase respondió sin datos válidos.")


def supabase_rpc(nombre, datos=None):
    """Invoca una funcion PostgreSQL publicada como RPC en Supabase."""
    _, resultado = supabase_request(
        f"rpc/{nombre}", metodo="POST", datos=datos or {}
    )
    return resultado


def subir_archivo_storage(ruta_archivo, carpeta="uploads"):
    """Sube una imagen al bucket publico compartido y devuelve su URL."""
    if not ruta_archivo or not os.path.exists(ruta_archivo) or not SUPABASE_URL or not SUPABASE_KEY:
        return None

    nombre = f"{carpeta}/{uuid.uuid4().hex}{os.path.splitext(ruta_archivo)[1].lower() or '.jpg'}"
    url = f"{SUPABASE_URL}/storage/v1/object/smartstore-media/{nombre}"
    tipo, _ = mimetypes.guess_type(ruta_archivo)
    headers = _headers()
    headers["Content-Type"] = tipo or "application/octet-stream"
    headers["x-upsert"] = "true"

    with open(ruta_archivo, "rb") as archivo:
        request = Request(url, data=archivo.read(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=30):
            return f"{SUPABASE_URL}/storage/v1/object/public/smartstore-media/{nombre}"
    except (HTTPError, URLError):
        return None
