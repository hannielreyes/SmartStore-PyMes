"""Local session, catalog cache, and durable Supabase synchronization queue."""

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote

from .conexion import (
    SupabaseNoDisponible,
    _supabase_activo,
    _supabase_actualizar,
    _supabase_insertar,
    _supabase_lista,
    _supabase_unico,
    get_db_connection,
)

PUBLIC_CACHE_USER_ID = "__public__"


def inicializar_almacen_offline(conn=None):
    owns_connection = conn is None
    conn = conn or get_db_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sesiones_offline (
                token_hash TEXT PRIMARY KEY,
                usuario_id TEXT NOT NULL,
                correo TEXT NOT NULL,
                nombre TEXT NOT NULL,
                revocada INTEGER NOT NULL DEFAULT 0,
                validada_en TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalogo_offline (
                usuario_id TEXT NOT NULL,
                entidad TEXT NOT NULL,
                entidad_id TEXT NOT NULL,
                datos TEXT NOT NULL,
                actualizado_en TEXT NOT NULL,
                PRIMARY KEY (usuario_id, entidad, entidad_id)
            );
            CREATE TABLE IF NOT EXISTS catalogo_offline_estado (
                usuario_id TEXT NOT NULL,
                entidad TEXT NOT NULL,
                consultado_en TEXT NOT NULL,
                PRIMARY KEY (usuario_id, entidad)
            );
            CREATE TABLE IF NOT EXISTS cola_offline (
                id TEXT PRIMARY KEY,
                usuario_id TEXT NOT NULL,
                entidad TEXT NOT NULL,
                entidad_id TEXT NOT NULL,
                operacion TEXT NOT NULL,
                offline_uuid TEXT,
                datos TEXT NOT NULL,
                base_datos TEXT,
                estado TEXT NOT NULL DEFAULT 'pendiente',
                sincronizando_en TEXT,
                error TEXT,
                creado_en TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cola_offline_estado
                ON cola_offline (estado, creado_en);
            CREATE TABLE IF NOT EXISTS ids_offline (
                usuario_id TEXT NOT NULL,
                entidad TEXT NOT NULL,
                id_local TEXT NOT NULL,
                id_remoto TEXT NOT NULL,
                PRIMARY KEY (usuario_id, entidad, id_local)
            );
            """
        )
        columnas_cola = {
            fila[1] for fila in conn.execute("PRAGMA table_info(cola_offline)")
        }
        if "sincronizando_en" not in columnas_cola:
            conn.execute(
                "ALTER TABLE cola_offline ADD COLUMN sincronizando_en TEXT"
            )
        conn.commit()
    finally:
        if owns_connection:
            conn.close()


def _token_hash(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def guardar_sesion_offline(token, usuario_id, correo, nombre):
    if not token or usuario_id is None or not correo:
        return False
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO sesiones_offline
                (token_hash, usuario_id, correo, nombre, revocada, validada_en)
            VALUES (?, ?, ?, ?, 0, ?)
            ON CONFLICT(token_hash) DO UPDATE SET
                usuario_id = excluded.usuario_id,
                correo = excluded.correo,
                nombre = excluded.nombre,
                revocada = 0,
                validada_en = excluded.validada_en
            """,
            (
                _token_hash(token),
                str(usuario_id),
                str(correo),
                str(nombre or ""),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def obtener_sesion_offline(token):
    if not token:
        return None
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        fila = conn.execute(
            """
            SELECT usuario_id, nombre, correo
            FROM sesiones_offline
            WHERE token_hash = ? AND revocada = 0
            LIMIT 1
            """,
            (_token_hash(token),),
        ).fetchone()
        if not fila:
            return None
        usuario_id = fila[0]
        try:
            usuario_id = int(usuario_id)
        except (TypeError, ValueError):
            pass
        from .models import UsuarioSesion

        return UsuarioSesion(usuario_id, fila[1], fila[2])
    finally:
        conn.close()


def revocar_sesion_offline(token):
    if not token:
        return False
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE sesiones_offline SET revocada = 1 WHERE token_hash = ?",
            (_token_hash(token),),
        )
        actualizado = conn.total_changes > 0
        conn.commit()
        return actualizado
    finally:
        conn.close()


def guardar_catalogo(usuario_id, entidad, filas):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        ids_remotos = set()
        ahora = datetime.now().isoformat()
        for fila in filas:
            datos = dict(fila)
            entidad_id = datos.get("id")
            if entidad_id is None:
                continue
            clave = str(entidad_id)
            ids_remotos.add(clave)
            pendiente = conn.execute(
                """
                SELECT 1 FROM cola_offline
                WHERE usuario_id = ? AND entidad = ? AND entidad_id = ?
                    AND estado IN ('pendiente', 'sincronizando')
                LIMIT 1
                """,
                (str(usuario_id), entidad, clave),
            ).fetchone()
            if pendiente:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO catalogo_offline
                    (usuario_id, entidad, entidad_id, datos, actualizado_en)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(usuario_id), entidad, clave, json.dumps(datos), ahora),
            )
        existentes = conn.execute(
            """
            SELECT entidad_id FROM catalogo_offline
            WHERE usuario_id = ? AND entidad = ?
            """,
            (str(usuario_id), entidad),
        ).fetchall()
        for (entidad_id,) in existentes:
            if str(entidad_id) in ids_remotos:
                continue
            pendiente = conn.execute(
                """
                SELECT 1 FROM cola_offline
                WHERE usuario_id = ? AND entidad = ? AND entidad_id = ?
                    AND estado IN ('pendiente', 'sincronizando', 'conflicto')
                LIMIT 1
                """,
                (str(usuario_id), entidad, str(entidad_id)),
            ).fetchone()
            if not pendiente:
                conn.execute(
                    """
                    DELETE FROM catalogo_offline
                    WHERE usuario_id = ? AND entidad = ? AND entidad_id = ?
                    """,
                    (str(usuario_id), entidad, str(entidad_id)),
                )
        conn.execute(
            """
            INSERT OR REPLACE INTO catalogo_offline_estado
                (usuario_id, entidad, consultado_en)
            VALUES (?, ?, ?)
            """,
            (str(usuario_id), entidad, ahora),
        )
        conn.commit()
    finally:
        conn.close()


def marcar_catalogo_conocido(usuario_id, entidad):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO catalogo_offline_estado
                (usuario_id, entidad, consultado_en)
            VALUES (?, ?, ?)
            """,
            (str(usuario_id), entidad, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def recuperar_sincronizacion_interrumpida():
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE cola_offline
            SET estado = 'pendiente', sincronizando_en = NULL
            WHERE estado = 'sincronizando'
                AND (
                    sincronizando_en IS NULL
                    OR sincronizando_en < ?
                )
            """,
            ((datetime.now() - timedelta(minutes=10)).isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()


def tiene_catalogo_conocido(usuario_id, entidad):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        fila = conn.execute(
            """
            SELECT 1 FROM catalogo_offline_estado
            WHERE usuario_id = ? AND entidad = ?
            LIMIT 1
            """,
            (str(usuario_id), entidad),
        ).fetchone()
        return fila is not None
    finally:
        conn.close()


def agregar_elemento_catalogo(usuario_id, entidad, datos):
    inicializar_almacen_offline()
    entidad_id = datos.get("id")
    if entidad_id is None:
        return False
    conn = get_db_connection()
    try:
        pendiente = conn.execute(
            """
            SELECT 1 FROM cola_offline
            WHERE usuario_id = ? AND entidad = ? AND entidad_id = ?
                AND estado IN ('pendiente', 'sincronizando')
            LIMIT 1
            """,
            (str(usuario_id), entidad, str(entidad_id)),
        ).fetchone()
        if pendiente:
            return False
        conn.execute(
            """
            INSERT OR REPLACE INTO catalogo_offline
                (usuario_id, entidad, entidad_id, datos, actualizado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(usuario_id),
                entidad,
                str(entidad_id),
                json.dumps(dict(datos)),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def obtener_catalogo(usuario_id, entidad):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        filas = conn.execute(
            """
            SELECT entidad_id, datos FROM catalogo_offline
            WHERE usuario_id = ? AND entidad = ?
            """,
            (str(usuario_id), entidad),
        ).fetchall()
        resultado = {str(fila[0]): json.loads(fila[1]) for fila in filas}
        pendientes = conn.execute(
            """
            SELECT entidad_id, operacion, datos FROM cola_offline
            WHERE usuario_id = ? AND entidad = ?
                AND estado IN ('pendiente', 'sincronizando')
            ORDER BY creado_en, rowid
            """,
            (str(usuario_id), entidad),
        ).fetchall()
        for entidad_id, operacion, datos_json in pendientes:
            datos = json.loads(datos_json)
            clave = str(entidad_id)
            if operacion == "crear":
                resultado[clave] = datos
            elif operacion == "actualizar" and clave in resultado:
                resultado[clave].update(datos)
        return list(resultado.values())
    finally:
        conn.close()


def obtener_elemento_catalogo(usuario_id, entidad, entidad_id):
    clave = str(entidad_id)
    return next(
        (
            fila
            for fila in obtener_catalogo(usuario_id, entidad)
            if str(fila.get("id")) == clave
        ),
        None,
    )


def obtener_elemento_cache_por_id(entidad, entidad_id):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        fila = conn.execute(
            """
            SELECT usuario_id FROM catalogo_offline
            WHERE entidad = ? AND entidad_id = ?
            UNION
            SELECT usuario_id FROM cola_offline
            WHERE entidad = ? AND entidad_id = ?
                AND estado IN ('pendiente', 'sincronizando', 'conflicto')
            LIMIT 1
            """,
            (entidad, str(entidad_id), entidad, str(entidad_id)),
        ).fetchone()
    finally:
        conn.close()
    if not fila:
        return None
    return obtener_elemento_catalogo(fila[0], entidad, entidad_id)


def nuevo_id_local(usuario_id, entidad):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        while True:
            candidato = -int(uuid.uuid4().hex[:15], 16)
            encontrado = conn.execute(
                """
                SELECT 1 FROM catalogo_offline
                WHERE usuario_id = ? AND entidad = ? AND entidad_id = ?
                UNION
                SELECT 1 FROM cola_offline
                WHERE usuario_id = ? AND entidad = ? AND entidad_id = ?
                LIMIT 1
                """,
                (
                    str(usuario_id), entidad, str(candidato),
                    str(usuario_id), entidad, str(candidato),
                ),
            ).fetchone()
            if not encontrado:
                return candidato
    finally:
        conn.close()


def es_id_local(entidad_id):
    try:
        return int(entidad_id) < 0
    except (TypeError, ValueError):
        return False


def actualizar_elemento_catalogo(usuario_id, entidad, entidad_id, cambios):
    elemento = obtener_elemento_catalogo(usuario_id, entidad, entidad_id)
    if not elemento:
        return False
    elemento.update(cambios)
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO catalogo_offline
                (usuario_id, entidad, entidad_id, datos, actualizado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(usuario_id),
                entidad,
                str(entidad_id),
                json.dumps(elemento),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def encolar_creacion(usuario_id, entidad, entidad_id, datos):
    inicializar_almacen_offline()
    datos = dict(datos)
    datos["id"] = entidad_id
    offline_uuid = str(uuid.uuid4())
    datos["offline_uuid"] = offline_uuid
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO cola_offline
                (id, usuario_id, entidad, entidad_id, operacion, offline_uuid,
                 datos, creado_en)
            VALUES (?, ?, ?, ?, 'crear', ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                str(usuario_id),
                entidad,
                str(entidad_id),
                offline_uuid,
                json.dumps(datos),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def encolar_actualizacion(usuario_id, entidad, entidad_id, cambios):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        clave = str(entidad_id)
        pendiente = conn.execute(
            """
            SELECT id, operacion, datos, base_datos FROM cola_offline
            WHERE usuario_id = ? AND entidad = ? AND entidad_id = ?
                AND estado = 'pendiente'
            ORDER BY creado_en, rowid LIMIT 1
            """,
            (str(usuario_id), entidad, clave),
        ).fetchone()
        if pendiente:
            datos = json.loads(pendiente[2])
            datos.update(cambios)
            conn.execute(
                "UPDATE cola_offline SET datos = ? WHERE id = ?",
                (json.dumps(datos), pendiente[0]),
            )
        else:
            base = obtener_elemento_catalogo(usuario_id, entidad, entidad_id)
            if not base:
                return False
            base_cambios = {campo: base.get(campo) for campo in cambios}
            conn.execute(
                """
                INSERT INTO cola_offline
                    (id, usuario_id, entidad, entidad_id, operacion, datos,
                     base_datos, creado_en)
                VALUES (?, ?, ?, ?, 'actualizar', ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    str(usuario_id),
                    entidad,
                    clave,
                    json.dumps(cambios),
                    json.dumps(base_cambios),
                    datetime.now().isoformat(),
                ),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def _id_remoto(usuario_id, entidad, id_local):
    try:
        if int(id_local) < 0:
            pass
        else:
            return id_local
    except (TypeError, ValueError):
        return id_local
    conn = get_db_connection()
    try:
        fila = conn.execute(
            """
            SELECT id_remoto FROM ids_offline
            WHERE usuario_id = ? AND entidad = ? AND id_local = ?
            """,
            (str(usuario_id), entidad, str(id_local)),
        ).fetchone()
        if not fila:
            return None
        try:
            return int(fila[0])
        except (TypeError, ValueError):
            return fila[0]
    finally:
        conn.close()


def _guardar_mapeo(usuario_id, entidad, id_local, id_remoto):
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO ids_offline
                (usuario_id, entidad, id_local, id_remoto)
            VALUES (?, ?, ?, ?)
            """,
            (str(usuario_id), entidad, str(id_local), str(id_remoto)),
        )
        conn.commit()
    finally:
        conn.close()


def _actualizar_estado(operacion_id, estado, error=None):
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE cola_offline
            SET estado = ?, error = ?, sincronizando_en = ?
            WHERE id = ?
            """,
            (
                estado,
                error,
                datetime.now().isoformat() if estado == "sincronizando" else None,
                operacion_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _cachear_resultado(usuario_id, entidad, datos):
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO catalogo_offline
                (usuario_id, entidad, entidad_id, datos, actualizado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(usuario_id),
                entidad,
                str(datos["id"]),
                json.dumps(dict(datos)),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _query_por_uuid(entidad, offline_uuid, campos):
    return _supabase_unico(
        entidad,
        f"?select={campos}&offline_uuid=eq.{quote(offline_uuid, safe='')}&limit=1",
    )


def _sincronizar_creacion(usuario_id, elemento):
    entidad = elemento["entidad"]
    datos = json.loads(elemento["datos"])
    local_id = elemento["entidad_id"]
    campos = (
        "id,nombre,whatsapp,tasa_cambio,usuario_id,direccion,saldo,imagen,offline_uuid"
        if entidad == "tiendas"
        else (
            "id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,"
            "imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,"
            "color_principal,material,garantia,especificacion,offline_uuid"
        )
    )
    remoto = _query_por_uuid(entidad, elemento["offline_uuid"], campos)
    if not remoto and entidad == "tiendas":
        remoto = _supabase_unico(
            "tiendas",
            f"?select={campos}&usuario_id=eq.{quote(str(usuario_id), safe='')}&limit=1",
        )
    if not remoto:
        datos_remotos = {key: value for key, value in datos.items() if key not in {"id"}}
        if entidad == "productos":
            tienda_remota = _id_remoto(usuario_id, "tiendas", datos_remotos["tienda_id"])
            if tienda_remota is None:
                return False
            datos_remotos["tienda_id"] = tienda_remota
        try:
            remoto = _supabase_insertar(entidad, datos_remotos)
        except RuntimeError as exc:
            detalle = str(exc).lower()
            if "23505" not in detalle and "duplicate key" not in detalle and "http 409" not in detalle:
                raise
            remoto = _query_por_uuid(entidad, elemento["offline_uuid"], campos)
            if not remoto and entidad == "tiendas":
                remoto = _supabase_unico(
                    "tiendas",
                    f"?select={campos}&usuario_id=eq.{quote(str(usuario_id), safe='')}&limit=1",
                )
            if not remoto:
                raise
        if not isinstance(remoto, dict) or remoto.get("id") is None:
            raise RuntimeError(f"Supabase no devolvió el identificador de {entidad}.")
    elif entidad == "tiendas" and str(remoto.get("offline_uuid") or "") != elemento["offline_uuid"]:
        _actualizar_estado(
            elemento["id"],
            "conflicto",
            "Supabase ya tiene una tienda; se conservó la tienda remota.",
        )
    _guardar_mapeo(usuario_id, entidad, local_id, remoto["id"])
    _cachear_resultado(usuario_id, entidad, remoto)
    return True


def _sincronizar_actualizacion(usuario_id, elemento):
    entidad = elemento["entidad"]
    id_remoto = _id_remoto(usuario_id, entidad, elemento["entidad_id"])
    if id_remoto is None:
        id_remoto = elemento["entidad_id"]
    id_remoto = quote(str(id_remoto), safe="")
    campos = (
        "id,nombre,whatsapp,tasa_cambio,usuario_id,direccion,saldo,imagen"
        if entidad == "tiendas"
        else "id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id"
    )
    actual = _supabase_unico(
        entidad,
        f"?select={campos}&id=eq.{id_remoto}&limit=1",
    )
    if not actual:
        _actualizar_estado(elemento["id"], "conflicto", "El registro ya no existe en Supabase.")
        return True

    cambios = json.loads(elemento["datos"])
    base = json.loads(elemento["base_datos"] or "{}")
    if any(actual.get(campo) != base.get(campo) for campo in cambios):
        _cachear_resultado(usuario_id, entidad, actual)
        _actualizar_estado(
            elemento["id"],
            "conflicto",
            "Supabase cambió estos datos; se conservaron los valores remotos.",
        )
        return True

    parametros = f"?id=eq.{id_remoto}"
    if entidad == "tiendas":
        parametros += f"&usuario_id=eq.{quote(str(usuario_id), safe='')}"
    resultado = _supabase_actualizar(entidad, cambios, parametros)
    if not resultado:
        _actualizar_estado(elemento["id"], "conflicto", "Supabase no encontró el registro para actualizar.")
        return True
    actual.update(cambios)
    _cachear_resultado(usuario_id, entidad, actual)
    return True


def sincronizar_cambios_offline(usuario_id):
    """Uploads queued catalog changes, preserving remote values on conflicts."""
    inicializar_almacen_offline()
    if not _supabase_activo():
        return {"sincronizados": 0, "conflictos": 0}
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        recuperacion = (datetime.now() - timedelta(minutes=10)).isoformat()
        conn.execute(
            """
            UPDATE cola_offline
            SET estado = 'pendiente', sincronizando_en = NULL
            WHERE usuario_id = ? AND estado = 'sincronizando'
                AND sincronizando_en < ?
            """,
            (str(usuario_id), recuperacion),
        )
        filas = conn.execute(
            """
            SELECT id, entidad, entidad_id, operacion, offline_uuid, datos, base_datos
            FROM cola_offline
            WHERE usuario_id = ? AND estado = 'pendiente'
            ORDER BY creado_en, rowid
            """,
            (str(usuario_id),),
        ).fetchall()
        sincronizando_en = datetime.now().isoformat()
        conn.executemany(
            """
            UPDATE cola_offline
            SET estado = 'sincronizando', sincronizando_en = ?
            WHERE id = ?
            """,
            ((sincronizando_en, fila[0]) for fila in filas),
        )
        conn.commit()
    finally:
        conn.close()
    sincronizados = 0
    for fila in filas:
        elemento = {
            "id": fila[0],
            "entidad": fila[1],
            "entidad_id": fila[2],
            "operacion": fila[3],
            "offline_uuid": fila[4],
            "datos": fila[5],
            "base_datos": fila[6],
        }
        try:
            if elemento["operacion"] == "crear":
                completo = _sincronizar_creacion(usuario_id, elemento)
            else:
                completo = _sincronizar_actualizacion(usuario_id, elemento)
        except SupabaseNoDisponible:
            _devolver_cambios_a_pendiente([fila[0] for fila in filas])
            break
        except Exception:
            _devolver_cambios_a_pendiente([fila[0] for fila in filas])
            raise
        if completo:
            conn = get_db_connection()
            try:
                pendiente = conn.execute(
                    "SELECT estado FROM cola_offline WHERE id = ?",
                    (elemento["id"],),
                ).fetchone()
                if pendiente and pendiente[0] == "sincronizando":
                    conn.execute(
                        """
                        UPDATE cola_offline
                        SET estado = 'sincronizado', error = NULL,
                            sincronizando_en = NULL
                        WHERE id = ?
                        """,
                        (elemento["id"],),
                    )
                conn.commit()
            finally:
                conn.close()
            sincronizados += 1
    return {"sincronizados": sincronizados, "conflictos": contar_conflictos_offline(usuario_id)}


def _devolver_cambios_a_pendiente(operacion_ids):
    if not operacion_ids:
        return
    conn = get_db_connection()
    try:
        placeholders = ",".join("?" for _ in operacion_ids)
        conn.execute(
            f"""
            UPDATE cola_offline
            SET estado = 'pendiente', sincronizando_en = NULL
            WHERE estado = 'sincronizando' AND id IN ({placeholders})
            """,
            tuple(operacion_ids),
        )
        conn.commit()
    finally:
        conn.close()


def contar_cambios_pendientes(usuario_id):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        fila = conn.execute(
            """
            SELECT COUNT(*) FROM cola_offline
            WHERE usuario_id = ? AND estado IN ('pendiente', 'sincronizando', 'conflicto')
            """,
            (str(usuario_id),),
        ).fetchone()
        return int(fila[0] or 0)
    finally:
        conn.close()


def contar_conflictos_offline(usuario_id):
    inicializar_almacen_offline()
    conn = get_db_connection()
    try:
        fila = conn.execute(
            "SELECT COUNT(*) FROM cola_offline WHERE usuario_id = ? AND estado = 'conflicto'",
            (str(usuario_id),),
        ).fetchone()
        return int(fila[0] or 0)
    finally:
        conn.close()
