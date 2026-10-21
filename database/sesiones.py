# Módulo generado automáticamente a partir de `legado.py`.
# No editar manualmente; los cambios deben hacerse en `legado.py` y volver a ejecutar este script.

from .models import UsuarioSesion
from .conexion import (
    get_db_connection,
    _supabase_activo,
    _supabase_unico,
    _supabase_insertar,
    _supabase_actualizar,
    _supabase_borrar,
)
import bcrypt, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import quote

# Importaciones necesarias desde usuarios
from .usuarios import obtener_usuario_por_id, obtener_usuario


def _hash_token(token: str) -> str:
    """Genera un resumen hash SHA-256 para almacenar o comparar el token de forma segura."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def guardar_codigo_sesion(correo, codigo):
    if _supabase_activo():
        return bool(_supabase_actualizar(
            "usuarios",
            {"codigo_sesion": codigo},
            f"?correo=eq.{quote(str(correo), safe='')}",
        ))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET codigo_sesion = ? WHERE correo = ?",
        (codigo, correo),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizado


def validar_codigo_sesion(correo, codigo_ingresado):
    if _supabase_activo():
        usuario = _supabase_unico(
            "usuarios",
            f"?select=codigo_sesion&correo=eq.{quote(str(correo), safe='')}&limit=1",
        )
        codigo_guardado = usuario.get("codigo_sesion") if usuario else None
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT codigo_sesion FROM usuarios WHERE correo = ?", (correo,)
        )
        fila = cursor.fetchone()
        conn.close()
        codigo_guardado = fila[0] if fila else None

    return bool(
        codigo_guardado
        and codigo_ingresado
        and secrets.compare_digest(str(codigo_guardado), str(codigo_ingresado))
    )


def invalidar_codigo_sesion_bd(correo):
    if _supabase_activo():
        _supabase_actualizar(
            "usuarios",
            {"codigo_sesion": None},
            f"?correo=eq.{quote(str(correo), safe='')}",
        )
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET codigo_sesion = NULL WHERE correo = ?", (correo,)
    )
    conn.commit()
    conn.close()


def crear_token_sesion(correo, contraseña=None, usuario_id=None):
    usuario = obtener_usuario_por_id(usuario_id) if usuario_id else obtener_usuario(correo, contraseña)
    if not usuario:
        return None
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    if _supabase_activo():
        _supabase_insertar(
            "sesiones_dispositivo",
            {"usuario_id": usuario.id, "token_hash": token_hash, "revocado": False},
        )
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sesiones_dispositivo (usuario_id, token_hash) VALUES (?, ?)",
            (usuario.id, token_hash),
        )
        conn.commit()
        conn.close()
    return token


def obtener_usuario_por_token(token):
    if not token:
        return None
    token_hash = _hash_token(token)
    if _supabase_activo():
        sesion = _supabase_unico(
            "sesiones_dispositivo",
            f"?select=usuario_id&token_hash=eq.{quote(token_hash, safe='')}&revocado=eq.false&limit=1",
        )
        if not sesion:
            return None
        usuario = _supabase_unico(
            "usuarios",
            f"?select=id,nombre,correo&id=eq.{sesion['usuario_id']}&limit=1",
        )
        return UsuarioSesion(usuario["id"], usuario["nombre"], usuario["correo"]) if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.id, u.nombre, u.correo
        FROM usuarios u
        JOIN sesiones_dispositivo s ON s.usuario_id = u.id
        WHERE s.token_hash = ? AND s.revocado = 0
        LIMIT 1
        """,
        (token_hash,),
    )
    usuario = cursor.fetchone()
    conn.close()
    return UsuarioSesion(*usuario) if usuario else None


def revocar_token_sesion(token):
    if not token:
        return False
    token_hash = _hash_token(token)
    if _supabase_activo():
        return bool(_supabase_actualizar(
            "sesiones_dispositivo",
            {"revocado": True},
            f"?token_hash=eq.{quote(token_hash, safe='')}",
        ))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sesiones_dispositivo SET revocado = 1 WHERE token_hash = ?",
        (token_hash,),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizado