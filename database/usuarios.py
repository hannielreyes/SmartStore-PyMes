# Módulo generado automáticamente a partir de `legado.py`.
# No editar manualmente; los cambios deben hacerse en `legado.py` y volver a ejecutar este script.

from .conexion import (
    _marcar_supabase_caido,
    get_db_connection,
    _supabase_activo,
    _supabase_unico,
    _supabase_insertar,
    _supabase_actualizar,
    _supabase_borrar,
    PAYPAL_VENDEDOR_SANDBOX,
)
import bcrypt, hashlib, secrets
from datetime import datetime, timedelta
from urllib.parse import quote
from .models import PerfilUsuario, SesionAutenticada, UsuarioRecuperacion, UsuarioSesion
from supabase_config import (
    supabase_request,
    supabase_auth_request,
    establecer_sesion_auth,
    limpiar_token_auth,
    refrescar_sesion_auth,
    obtener_refresh_token_auth,
    supabase_function_request,
)

def obtener_usuario(correo, contraseña):
    if _supabase_activo():
        correo_q = quote(str(correo), safe="")
        usuario = _supabase_unico(
            "usuarios",
            f"?select=id,nombre,correo,contraseña&correo=eq.{correo_q}&limit=1",
        )
        if not usuario or not usuario.get("contraseña"):
            return None
        try:
            valido = bcrypt.checkpw(
                str(contraseña).encode("utf-8"),
                str(usuario["contraseña"]).encode("utf-8"),
            )
        except (TypeError, ValueError):
            return None
        return UsuarioSesion(usuario["id"], usuario["nombre"], usuario["correo"]) if valido else None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, correo, contraseña FROM usuarios WHERE correo = ?",
        (correo,),
    )
    fila = cursor.fetchone()
    conn.close()
    if not fila:
        return None
    try:
        valido = bcrypt.checkpw(
            str(contraseña).encode("utf-8"), str(fila[3]).encode("utf-8")
        )
    except (TypeError, ValueError):
        return None
    return UsuarioSesion(fila[0], fila[1], fila[2]) if valido else None




def obtener_usuario_por_id(usuario_id):
    if _supabase_activo():
        usuario = _supabase_unico(
            "usuarios", f"?select=id,nombre,correo,telefono,fecha_nacimiento,imagen,auth_user_id&id=eq.{usuario_id}&limit=1"
        )
        return PerfilUsuario(*(usuario.get(campo) for campo in ("id", "nombre", "correo", "telefono", "fecha_nacimiento", "imagen", "auth_user_id"))) if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, correo, telefono, fecha_nacimiento, imagen, auth_user_id FROM usuarios WHERE id = ?",
        (usuario_id,),
    )
    usuario = cursor.fetchone()
    conn.close()
    return PerfilUsuario(*usuario) if usuario else None




def actualizar_perfil_usuario(usuario_id, nombre, correo, telefono, fecha_nacimiento):
    if _supabase_activo():
        resultado = _supabase_actualizar(
            "usuarios",
            {"nombre": nombre, "correo": correo, "telefono": telefono, "fecha_nacimiento": fecha_nacimiento},
            f"?id=eq.{usuario_id}",
        )
        return bool(resultado)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE usuarios
        SET nombre = ?, correo = ?, telefono = ?, fecha_nacimiento = ?
        WHERE id = ?
        """,
        (nombre, correo, telefono, fecha_nacimiento, usuario_id),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizado




def registrar_usuario(nombre, correo, telefono, fecha_nac, contraseña, imagen=None):
    hash_password = bcrypt.hashpw(
        str(contraseña).encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    if _supabase_activo():
        try:
            _supabase_insertar(
                "usuarios",
                {"nombre": nombre, "correo": correo, "telefono": telefono,
                 "fecha_nacimiento": fecha_nac, "contraseña": hash_password,
                 "paypal_email": PAYPAL_VENDEDOR_SANDBOX, "imagen": imagen},
            )
            return True, "Usuario registrado"
        except Exception:
            return False, "Error al registrar"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO usuarios (nombre, correo, telefono, fecha_nacimiento, contraseña, paypal_email, imagen)
            VALUES (?,?,?,?,?,?,?)
        """,
            (
                nombre,
                correo,
                telefono,
                fecha_nac,
                hash_password,
                PAYPAL_VENDEDOR_SANDBOX,
                imagen,
            ),
        )
        conn.commit()
        return True, "Usuario registrado"
    except:
        return False, "Error al registrar"
    finally:
        conn.close()




def registrar_usuario_auth(nombre, correo, telefono, fecha_nac, contraseña, imagen=None):
    """Registra la identidad en Supabase Auth y luego su perfil de SmartStore."""
    if not _supabase_activo():
        return False, "Supabase Auth requiere Supabase activo"
    try:
        _, respuesta = supabase_auth_request(
            "signup",
            datos={
                "email": correo,
                "password": contraseña,
                "data": {
                    "nombre": nombre,
                    "telefono": telefono,
                    "fecha_nacimiento": fecha_nac,
                    "imagen": imagen,
                },
            },
        )
        usuario_auth = respuesta.get("user") if isinstance(respuesta, dict) else None
        access_token = respuesta.get("access_token") if isinstance(respuesta, dict) else None
        if not usuario_auth or not usuario_auth.get("id"):
            return False, "Supabase no devolvió la identidad creada"
        if access_token:
            establecer_sesion_auth(access_token, respuesta.get("refresh_token"))
            perfil = _supabase_unico(
                "usuarios",
                f"?select=id&auth_user_id=eq.{quote(str(usuario_auth['id']), safe='')}&limit=1",
            )
            if not perfil:
                return False, "Supabase Auth creó la cuenta, pero no se pudo crear el perfil. Ejecuta la migración de perfil Auth."
        if access_token:
            return True, "Usuario registrado"
        return True, "Cuenta creada. Confirma tu correo antes de iniciar sesión."
    except Exception as exc:
        limpiar_token_auth()
        detalle = str(exc)
        print(f"[Supabase Auth] Error de registro: {detalle}")
        if "over_email_send_rate_limit" in detalle or "HTTP 429" in detalle:
            return False, "Supabase limitó temporalmente los correos de prueba. Espera aproximadamente un minuto y vuelve a intentarlo una sola vez."
        if any(indicador in detalle.lower() for indicador in (
            "user_already_exists",
            "already registered",
            "already been registered",
            "duplicate key",
        )):
            return False, "Ese correo ya está registrado. Vuelve a Iniciar sesión o usa Continuar con Google."
        if "password" in detalle.lower() and ("6" in detalle or "characters" in detalle.lower()):
            return False, "La contraseña debe tener al menos 6 caracteres."
        if "HTTP 401" in detalle or "HTTP 403" in detalle:
            return False, "Supabase rechazó el registro por permisos o configuración de Auth. Revisa Google/Email y las políticas RLS."
        if "HTTP 409" in detalle or "HTTP 422" in detalle:
            return False, "Supabase rechazó estos datos. El correo puede estar registrado o tener un formato no válido."
        return False, "No se pudo registrar la cuenta en Supabase. Revisa los datos e inténtalo nuevamente."




def iniciar_sesion_auth(correo, contraseña):
    """Autentica con Supabase Auth y devuelve (JWT, usuario SmartStore)."""
    if not _supabase_activo():
        return None
    try:
        _, respuesta = supabase_auth_request(
            "token?grant_type=password",
            datos={"email": correo, "password": contraseña},
        )
        access_token = respuesta.get("access_token") if isinstance(respuesta, dict) else None
        usuario_auth = respuesta.get("user") if isinstance(respuesta, dict) else None
        if not access_token or not usuario_auth or not usuario_auth.get("id"):
            return None
        establecer_sesion_auth(access_token, respuesta.get("refresh_token"))
        usuario = _supabase_unico(
            "usuarios",
            f"?select=id,nombre,correo&auth_user_id=eq.{quote(str(usuario_auth['id']), safe='')}&limit=1",
        )
        if not usuario:
            metadatos = usuario_auth.get("user_metadata") or {}
            _supabase_insertar(
                "usuarios",
                {
                    "auth_user_id": usuario_auth["id"],
                    "nombre": metadatos.get("nombre") or correo,
                    "correo": correo,
                    "telefono": metadatos.get("telefono"),
                    "fecha_nacimiento": metadatos.get("fecha_nacimiento"),
                    "imagen": metadatos.get("imagen"),
                    "paypal_email": PAYPAL_VENDEDOR_SANDBOX,
                },
            )
            usuario = _supabase_unico(
                "usuarios",
                f"?select=id,nombre,correo&auth_user_id=eq.{quote(str(usuario_auth['id']), safe='')}&limit=1",
            )
        if not usuario:
            limpiar_token_auth()
            return None
        return SesionAutenticada(
            access_token,
            obtener_refresh_token_auth(),
            UsuarioSesion(usuario["id"], usuario["nombre"], usuario["correo"]),
        )
    except Exception:
        limpiar_token_auth()
        return None




def crear_perfil_auth(auth_user_id, nombre, correo, telefono, fecha_nac, imagen=None):
    if not _supabase_activo() or not auth_user_id:
        return False, "Supabase Auth no está activo"
    try:
        auth_q = quote(str(auth_user_id), safe="")
        correo_q = quote(str(correo), safe="")
        usuario = _supabase_unico(
            "usuarios",
            f"?select=id&auth_user_id=eq.{auth_q}&limit=1",
        )
        if not usuario:
            usuario = _supabase_unico(
                "usuarios",
                f"?select=id&correo=eq.{correo_q}&limit=1",
            )
        datos = {
            "auth_user_id": auth_user_id,
            "nombre": nombre,
            "correo": correo,
            "telefono": telefono,
            "fecha_nacimiento": fecha_nac,
            "paypal_email": PAYPAL_VENDEDOR_SANDBOX,
            "imagen": imagen,
        }
        if usuario:
            _supabase_actualizar("usuarios", datos, f"?id=eq.{usuario['id']}")
        else:
            _supabase_insertar("usuarios", datos)
        return True, "Usuario registrado"
    except Exception as e:
        print(f"[crear_perfil_auth] Exception: {e}")
        return False, "No se pudo guardar el perfil"




def establecer_contraseña_auth(nueva_contraseña):
    if not _supabase_activo() or not nueva_contraseña:
        return False
    try:
        supabase_auth_request(
            "user",
            metodo="PUT",
            datos={"password": nueva_contraseña},
        )
        return True
    except RuntimeError as exc:
        detalle = str(exc)
        if "same_password" in detalle:
            return True
        detalle_minuscula = detalle.lower()
        if any(indicador in detalle_minuscula for indicador in (
            "weak_password",
            "password is too weak",
            "password is too short",
            "password should",
            "password must",
            "password needs",
        )):
            raise RuntimeError(
                "Supabase rechazó esa contraseña por ser demasiado sencilla o corta. "
                "Prueba con 8 o más caracteres y combina letras y números."
            ) from exc
        raise RuntimeError(f"No se pudo actualizar la contraseña en Supabase Auth: {detalle}") from exc


def solicitar_codigo_recuperacion_auth(correo):
    if not _supabase_activo():
        return False
    supabase_auth_request(
        "recover",
        datos={"email": str(correo or "").strip()},
    )
    return True


def validar_codigo_recuperacion_auth(correo, codigo):
    if not _supabase_activo():
        return False
    try:
        _, respuesta = supabase_auth_request(
            "verify",
            datos={
                "email": str(correo or "").strip(),
                "token": str(codigo or "").strip(),
                "type": "recovery",
            },
        )
    except RuntimeError as exc:
        detalle = str(exc).lower()
        if any(mensaje in detalle for mensaje in (
            "otp_expired",
            "email link is invalid",
            "token has expired or is invalid",
            "invalid otp",
        )):
            return False
        raise

    if not isinstance(respuesta, dict):
        return False
    usuario_auth = respuesta.get("user") or {}
    correo_auth = str(usuario_auth.get("email") or "").strip().casefold()
    if correo_auth != str(correo or "").strip().casefold():
        return False
    access_token = respuesta.get("access_token")
    if not access_token:
        return False

    establecer_sesion_auth(access_token, respuesta.get("refresh_token"))
    return True


def validar_codigo_sesion_recuperacion_auth(correo, codigo):
    if not _supabase_activo():
        return False
    _, respuesta = supabase_function_request(
        "smartstore-session-recovery",
        {
            "action": "verify_session_code",
            "email": str(correo or "").strip(),
            "code": str(codigo or "").strip(),
        },
    )
    return bool(isinstance(respuesta, dict) and respuesta.get("valid"))


def cambiar_contrasena_con_codigo_sesion_auth(correo, codigo, nueva_contrasena):
    if not _supabase_activo():
        return False
    _, respuesta = supabase_function_request(
        "smartstore-session-recovery",
        {
            "action": "reset_password_with_session_code",
            "email": str(correo or "").strip(),
            "code": str(codigo or "").strip(),
            "password": nueva_contrasena,
        },
    )
    if isinstance(respuesta, dict) and respuesta.get("ok"):
        return True
    if isinstance(respuesta, dict) and respuesta.get("error"):
        raise RuntimeError(str(respuesta["error"]))
    return False




def restaurar_sesion_auth(refresh_token):
    if not refresh_token or not _supabase_activo():
        return False
    try:
        return refrescar_sesion_auth(refresh_token)
    except RuntimeError as exc:
        detalle = str(exc).lower()
        temporal = (
            "no se pudo contactar supabase" in detalle
            or "timed out" in detalle
            or any(f"http {codigo}" in detalle for codigo in (500, 502, 503, 504))
        )
        if temporal:
            _marcar_supabase_caido(str(exc))
        else:
            limpiar_token_auth()
        return False




def actualizar_imagen_usuario(usuario_id, imagen):
    if _supabase_activo():
        return bool(_supabase_actualizar("usuarios", {"imagen": imagen}, f"?id=eq.{usuario_id}"))
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET imagen = ? WHERE id = ?", (imagen, usuario_id))
        actualizado = cursor.rowcount > 0
        conn.commit()
        return actualizado
    finally:
        conn.close()




def verificar_correo_existe(correo):
    if _supabase_activo():
        return _supabase_unico("usuarios", f"?select=id&correo=eq.{quote(str(correo), safe='')}&limit=1") is not None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE correo = ?", (correo,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None




def obtener_telefono_por_correo(correo):
    if _supabase_activo():
        usuario = _supabase_unico("usuarios", f"?select=telefono&correo=eq.{quote(str(correo), safe='')}&limit=1")
        return usuario.get("telefono") if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telefono FROM usuarios WHERE correo = ?", (correo,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None




def obtener_usuario_por_correo(correo):
    if _supabase_activo():
        usuario = _supabase_unico("usuarios", f"?select=id,nombre,correo,telefono,fecha_nacimiento&correo=eq.{quote(str(correo), safe='')}&limit=1")
        return UsuarioRecuperacion(*(usuario.get(campo) for campo in ("id", "nombre", "correo", "telefono", "fecha_nacimiento"))) if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, correo, telefono, fecha_nacimiento FROM usuarios WHERE correo = ?",
        (correo,),
    )
    resultado = cursor.fetchone()
    conn.close()
    return UsuarioRecuperacion(*resultado) if resultado else None




def obtener_usuario_por_telefono(telefono):
    valor = (telefono or "").strip()
    if not valor:
        return None

    valores_busqueda = []
    valores_busqueda.append(valor)

    solo_numeros = "".join(caracter for caracter in valor if caracter.isdigit())
    if solo_numeros:
        valores_busqueda.append(solo_numeros)
        if solo_numeros.startswith("505"):
            valores_busqueda.append(solo_numeros[3:])
        else:
            valores_busqueda.append(f"505{solo_numeros}")

    valores_unicos = []
    for item in valores_busqueda:
        if item and item not in valores_unicos:
            valores_unicos.append(item)

    if not valores_unicos:
        return None

    if _supabase_activo():
        for valor in valores_unicos:
            usuario = _supabase_unico("usuarios", f"?select=id,nombre,correo,telefono,fecha_nacimiento,contraseña&telefono=eq.{quote(valor, safe='')}&limit=1")
            if usuario:
                return UsuarioRecuperacion(usuario.get("id"), usuario.get("nombre"), usuario.get("correo"), usuario.get("telefono"), usuario.get("fecha_nacimiento"), usuario.get("contraseña"))
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    parametros = valores_unicos + [None] * (3 - len(valores_unicos))
    cursor.execute(
        """
        SELECT id, nombre, correo, telefono, fecha_nacimiento, contraseña
        FROM usuarios
        WHERE telefono IN (?, ?, ?)
        """,
        tuple(parametros),
    )
    resultado = cursor.fetchone()
    conn.close()
    return UsuarioRecuperacion(*resultado) if resultado else None




def actualizar_contraseña_por_correo(correo, nueva_contraseña):
    hash_password = bcrypt.hashpw(
        str(nueva_contraseña).encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    if _supabase_activo():
        return bool(_supabase_actualizar("usuarios", {"contraseña": hash_password}, f"?correo=eq.{quote(str(correo), safe='')}"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET contraseña = ? WHERE correo = ?",
        (hash_password, correo),
    )
    conn.commit()
    actualizado = cursor.rowcount > 0
    conn.close()
    return actualizado




def obtener_contraseña_por_correo(correo):
    if _supabase_activo():
        usuario = _supabase_unico("usuarios", f"?select=contraseña&correo=eq.{quote(str(correo), safe='')}&limit=1")
        return usuario.get("contraseña") if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT contraseña FROM usuarios WHERE correo = ?", (correo,)
    )
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None


def obtener_paypal_email(usuario_id):
    if _supabase_activo():
        usuario = _supabase_unico("usuarios", f"?select=paypal_email&id=eq.{usuario_id}&limit=1")
        return usuario.get("paypal_email") if usuario else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT paypal_email FROM usuarios WHERE id = ?", (usuario_id,))
    fila = cursor.fetchone()
    conn.close()
    return fila[0] if fila and fila[0] else None


def guardar_paypal_email(usuario_id, paypal_email):
    if _supabase_activo():
        return bool(_supabase_actualizar("usuarios", {"paypal_email": paypal_email}, f"?id=eq.{usuario_id}"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET paypal_email = ? WHERE id = ?", (paypal_email, usuario_id))
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizado