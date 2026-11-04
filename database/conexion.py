"""Conexión SQLite y helpers compartidos para Supabase.

Este módulo contiene la infraestructura común de persistencia. Los módulos
de dominio reutilizan estas funciones para conservar un único estado de
conexión y el mismo mecanismo de recuperación ante fallos remotos.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from supabase_config import supabase_esta_configurado, supabase_request

DB_NAME = "smartstore.db"


def _obtener_ruta_base_datos():
    almacenamiento_app = os.environ.get("FLET_APP_STORAGE_DATA")
    if almacenamiento_app:
        directorio = Path(almacenamiento_app)
        directorio.mkdir(parents=True, exist_ok=True)
        return str(directorio / DB_NAME)
    return str(Path(__file__).resolve().parent.parent / DB_NAME)


DB_PATH = _obtener_ruta_base_datos()
USAR_SUPABASE = os.getenv("SMARTSTORE_USAR_SUPABASE", "1").strip().lower() in {
    "1", "true", "si", "sí", "yes", "on"
}
_SUPABASE_FALLIDA = False
_SUPABASE_FALLIDA_HASTA = None
_SUPABASE_FALLIDA_COOLDOWN = timedelta(seconds=45)


class SupabaseNoDisponible(RuntimeError):
    """Raised only when a transient network/server failure prevents a request."""


PAYPAL_VENDEDOR_SANDBOX = "sb-zfl8251875274@business.example.com"
PAYPAL_COMPRADOR_SANDBOX = "sb-ysdcv52256136@personal.example.com"


def _marcar_supabase_caido(mensaje=""):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    if "42703" in str(mensaje) or "column" in str(mensaje).lower() and "does not exist" in str(mensaje).lower():
        print(f"[Supabase] El esquema necesita una migración; se conserva la conexión remota. {mensaje}")
        return
    if not _es_fallo_transitorio(mensaje):
        return
    if _SUPABASE_FALLIDA:
        return
    _SUPABASE_FALLIDA = True
    _SUPABASE_FALLIDA_HASTA = datetime.now() + _SUPABASE_FALLIDA_COOLDOWN
    print(f"[Supabase] Fallo temporal detectado; se reintentará más tarde sin forzar SQLite local. {mensaje}")


def _supabase_activo():
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    if not USAR_SUPABASE:
        return False
    if not supabase_esta_configurado():
        print(
            "[Supabase] Configuración no válida o placeholder. "
            "Reemplaza SMARTSTORE_SUPABASE_URL y SMARTSTORE_SUPABASE_KEY en .env "
            "con tus valores reales para usar Supabase."
        )
        return False
    if _SUPABASE_FALLIDA:
        if _SUPABASE_FALLIDA_HASTA is not None and datetime.now() >= _SUPABASE_FALLIDA_HASTA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
            print("[Supabase] Reintentando conexion con Supabase tras recuperacion temporal.")
    return True


def _supabase_en_cooldown():
    if not _SUPABASE_FALLIDA:
        return False
    if _SUPABASE_FALLIDA_HASTA is not None and datetime.now() >= _SUPABASE_FALLIDA_HASTA:
        return False
    return True


def _es_fallo_transitorio(exc):
    detalle = str(exc).lower()
    return (
        "no se pudo contactar supabase" in detalle
        or "timed out" in detalle
        or any(f"http {codigo}" in detalle for codigo in (500, 502, 503, 504))
    )


def _error_remoto(tabla, accion, exc):
    _marcar_supabase_caido(f"Error {accion} en {tabla}: {exc}")
    mensaje = f"No hay conexión a internet o Supabase no está disponible: {exc}"
    if _es_fallo_transitorio(exc):
        return SupabaseNoDisponible(mensaje)
    return RuntimeError(mensaje)


def _supabase_lista(tabla, parametros=""):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    if _supabase_en_cooldown():
        raise SupabaseNoDisponible("Supabase está temporalmente no disponible.")
    try:
        _, datos = supabase_request(tabla, parametros=parametros)
        if _SUPABASE_FALLIDA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
        return datos or []
    except Exception as exc:
        # Un HTTP 400 con Postgres 42703 indica una migración pendiente,
        # no una caída de red. Mantén Supabase activo para no mezclar datos
        # remotos con el SQLite local.
        if "42703" in str(exc) or "column" in str(exc).lower() and "does not exist" in str(exc).lower():
            raise RuntimeError(f"El esquema de Supabase necesita una migración: {exc}") from exc
        raise _error_remoto(tabla, "de consulta", exc) from exc


def _supabase_unico(tabla, parametros=""):
    filas = _supabase_lista(tabla, parametros)
    return filas[0] if filas else None


def _supabase_insertar(tabla, datos):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    if _supabase_en_cooldown():
        raise SupabaseNoDisponible("Supabase está temporalmente no disponible.")
    try:
        _, resultado = supabase_request(tabla, metodo="POST", datos=datos)
        if _SUPABASE_FALLIDA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
        return resultado[0] if isinstance(resultado, list) and resultado else resultado
    except Exception as exc:
        raise _error_remoto(tabla, "al insertar", exc) from exc


def _supabase_actualizar(tabla, datos, parametros):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    if _supabase_en_cooldown():
        raise SupabaseNoDisponible("Supabase está temporalmente no disponible.")
    try:
        _, resultado = supabase_request(tabla, metodo="PATCH", datos=datos, parametros=parametros)
        if _SUPABASE_FALLIDA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
        return resultado
    except Exception as exc:
        raise _error_remoto(tabla, "al actualizar", exc) from exc


def _supabase_borrar(tabla, parametros):
    global _SUPABASE_FALLIDA, _SUPABASE_FALLIDA_HASTA
    if _supabase_en_cooldown():
        raise SupabaseNoDisponible("Supabase está temporalmente no disponible.")
    try:
        supabase_request(tabla, metodo="DELETE", parametros=parametros)
        if _SUPABASE_FALLIDA:
            _SUPABASE_FALLIDA = False
            _SUPABASE_FALLIDA_HASTA = None
    except Exception as exc:
        raise _error_remoto(tabla, "al borrar", exc) from exc


def get_db_connection():
    """Abre SQLite con claves foráneas activadas."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    # Mantiene utilizable el respaldo local incluso si Supabase aún está
    # recuperándose. En una instalación remota normal este bloque no se usa.
    tabla = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'reservas'"
    ).fetchone()
    if tabla:
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(reservas)")}
        for nombre, tipo in (
            ("fecha_expiracion", "TEXT"),
            ("codigo_retiro", "TEXT"),
            ("codigo_retiro_usado_en", "TEXT"),
        ):
            if nombre not in columnas:
                conn.execute(f"ALTER TABLE reservas ADD COLUMN {nombre} {tipo}")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_reservas_codigo_retiro "
            "ON reservas(codigo_retiro) WHERE codigo_retiro IS NOT NULL"
        )
        conn.execute(
            "UPDATE reservas SET fecha_expiracion = datetime(fecha, '+10 minutes') "
            "WHERE estado = 'Reservado' AND fecha IS NOT NULL "
            "AND (fecha_expiracion IS NULL OR fecha_expiracion > datetime(fecha, '+10 minutes'))"
        )
    return conn


def verificar_conexion_remota():
    """Comprueba que Supabase esté activo y responda a una consulta básica."""
    if not USAR_SUPABASE:
        raise RuntimeError("Supabase está desactivado localmente.")
    if not supabase_esta_configurado():
        raise RuntimeError("Supabase no está configurado.")
    try:
        supabase_request("usuarios", parametros="?select=id&limit=1")
        return True
    except Exception as exc:
        _marcar_supabase_caido(f"Verificacion de conexión remota fallida: {exc}")
        raise RuntimeError("No hay conexión a internet o la base de datos no está disponible.") from exc
