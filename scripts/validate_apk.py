"""Reject Android packages that contain development data or lack runtime files."""

import base64
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath


REQUIRED_APP_FILES = {
    "main.pyc",
    "supabase_config.pyc",
    "supabase_build_config.pyc",
    "app_state.pyc",
    "utils.pyc",
    "database/__init__.pyc",
    "database/conexion.pyc",
    "database/esquema.pyc",
    "database/estadisticas.pyc",
    "database/models.pyc",
    "database/pagos.pyc",
    "database/productos.pyc",
    "database/reservas.pyc",
    "database/sesiones.pyc",
    "database/tiendas.pyc",
    "database/usuarios.pyc",
    "services/__init__.pyc",
    "services/busqueda_lineal.pyc",
    "services/cola_tareas.pyc",
    "configuaraciones_adicionales/editar_tienda.pyc",
    "configuaraciones_adicionales/estadisticas.pyc",
    "configuaraciones_adicionales/perfil_usuario.pyc",
    "views/__init__.pyc",
    "views/buscar_producto.pyc",
    "views/carrito.pyc",
    "views/control_reservas.pyc",
    "views/crear_tienda.pyc",
    "views/inventario.pyc",
    "views/login.pyc",
    "views/menu.pyc",
    "views/perfil.pyc",
    "views/pre_splash.pyc",
    "views/recuperar.pyc",
    "views/registrar_producto.pyc",
    "views/reservar.pyc",
    "views/splash.pyc",
    "views/top_productos.pyc",
}
REQUIRED_ASSETS = {
    "assets/bienvenida.png",
    "assets/fondo.png",
    "assets/fondopro.png",
    "assets/goog_ico.png",
    "assets/whats_icon.png",
}
FORBIDDEN_COMPONENTS = {
    ".git",
    ".venv",
    "venv",
    ".flet",
    ".pytest_cache",
    ".vscode",
    ".idea",
    "__pycache__",
    "node_modules",
    "build",
    "storage",
    "temp",
    "scripts",
    "supabase",
    "tests",
    "test",
    ".github",
    ".devcontainer",
}
FORBIDDEN_NAMES = {
    ".gitignore",
    ".gitattributes",
    ".fletignore",
    "flet.yaml",
    "pyproject.toml",
    "requirements.txt",
    "build_and_install.ps1",
    "supabase_build_config.py",
    "check_supabase.pyc",
    "camera_test.pyc",
    "inspect_fc.pyc",
    "webhook.pyc",
    "proyecto.pyc",
    "Untitled.pyc",
}
FORBIDDEN_SUFFIXES = {
    ".log",
    ".sql",
    ".md",
    ".ps1",
    ".pyo",
    ".key",
    ".pem",
    ".p8",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
}
DATABASE_NAME = re.compile(r"(?i)(?:\.db|\.sqlite|\.sqlite3)(?:-(?:journal|wal|shm))?$")
PRIVATE_MARKERS = (
    re.compile(rb"sb_secret_[A-Za-z0-9_-]{8,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(rb"GOCSPX-[A-Za-z0-9_-]{15,}"),
)
JWT_PATTERN = re.compile(rb"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def _is_forbidden_path(name):
    normalized = name.replace("\\", "/").strip("/")
    parts = PurePosixPath(normalized).parts
    if not parts:
        return False
    if any(part.lower() in FORBIDDEN_COMPONENTS for part in parts):
        return True
    for part in parts:
        if (
            part.lower() == ".env"
            or part.lower().startswith(".env.")
            or part.lower() == "sesion.json"
            or part.lower() in FORBIDDEN_NAMES
            or part.lower().endswith(tuple(FORBIDDEN_SUFFIXES))
            or DATABASE_NAME.search(part)
        ):
            return True
    return False


def _contains_privileged_jwt(data):
    for match in JWT_PATTERN.finditer(data):
        payload = match.group(0).split(b".")[1]
        payload += b"=" * (-len(payload) % 4)
        try:
            claims = json.loads(base64.urlsafe_b64decode(payload))
        except (ValueError, TypeError):
            continue
        if isinstance(claims, dict) and claims.get("role") in {
            "service_role",
            "admin",
        }:
            return True
    return False


def _validate_app_archive(archive):
    violations = []
    entries = archive.namelist()
    names = {name.rstrip("/") for name in entries}
    files = {name for name in entries if not name.endswith("/")}

    forbidden = sorted(name for name in names if _is_forbidden_path(name))
    if forbidden:
        violations.append(
            f"Se encontraron {len(forbidden)} rutas prohibidas; ejemplos: "
            + ", ".join(forbidden[:12])
        )

    missing = sorted((REQUIRED_APP_FILES | REQUIRED_ASSETS) - files)
    if missing:
        violations.append(
            "Faltan archivos necesarios de runtime: " + ", ".join(missing)
        )

    if forbidden:
        return violations

    for name in sorted(files):
        try:
            data = archive.read(name)
        except (KeyError, OSError, zipfile.BadZipFile) as error:
            violations.append(f"No se pudo leer {name}: {error}")
            continue
        if any(marker.search(data) for marker in PRIVATE_MARKERS):
            violations.append(f"Posible credencial privada encontrada en {name}")
        elif _contains_privileged_jwt(data):
            violations.append(f"JWT con privilegios no permitido encontrado en {name}")

    return violations


def validate_apk(apk_path):
    apk_path = Path(apk_path)
    if not apk_path.is_file():
        return [f"No existe el APK indicado: {apk_path}"]

    try:
        with zipfile.ZipFile(apk_path) as apk:
            if "assets/app.zip" not in apk.namelist():
                return ["El APK no contiene assets/app.zip."]
            with apk.open("assets/app.zip") as app_file:
                with zipfile.ZipFile(app_file) as app_archive:
                    return _validate_app_archive(app_archive)
    except (OSError, zipfile.BadZipFile) as error:
        return [f"No se pudo inspeccionar el APK: {error}"]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Uso: python validate_apk.py <archivo.apk>", file=sys.stderr)
        return 2

    violations = validate_apk(argv[0])
    if violations:
        print("ERROR: APK rechazado por la validación de seguridad.")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print(
        "APK validado: sin archivos prohibidos, sin credenciales privadas "
        "y con runtime completo."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
