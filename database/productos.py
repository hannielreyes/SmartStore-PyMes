# Módulo generado automáticamente a partir de `legado.py`.
# No editar manualmente; los cambios deben hacerse en `legado.py` y volver a ejecutar este script.

from .conexion import (
    SupabaseNoDisponible,
    get_db_connection,
    _supabase_activo,
    _supabase_unico,
    _supabase_lista,
    _supabase_insertar,
    _supabase_actualizar,
    _supabase_borrar,
)
from .offline import (
    PUBLIC_CACHE_USER_ID,
    agregar_elemento_catalogo,
    actualizar_elemento_catalogo,
    encolar_actualizacion,
    encolar_creacion,
    es_id_local,
    guardar_catalogo,
    marcar_catalogo_conocido,
    nuevo_id_local,
    obtener_catalogo,
)
from .models import (
    AlertaInventario,
    Producto,
    ProductoBasico,
    ProductoDestacado,
    ProductoReserva,
    ProductoTienda,
)
import bcrypt, hashlib, secrets
import random
from datetime import datetime, timedelta
from urllib.parse import quote


def obtener_productos_aleatorios(limit=5, usuario_id=None, cache_usuario_id=None):
    if _supabase_activo():
        cache_id = usuario_id if usuario_id is not None else PUBLIC_CACHE_USER_ID
        try:
            if usuario_id is not None:
                filas = _supabase_lista(
                    "productos",
                    f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion,tiendas!inner(usuario_id)&tiendas.usuario_id=eq.{usuario_id}&limit={int(limit)}",
                )
            else:
                filas = _supabase_lista(
                    "productos",
                    f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion&limit={int(limit)}",
                )
                marcar_catalogo_conocido(PUBLIC_CACHE_USER_ID, "productos")
            for fila in filas:
                agregar_elemento_catalogo(cache_id, "productos", fila)
        except SupabaseNoDisponible:
            filas_por_id = {
                str(fila.get("id")): fila
                for fila in obtener_catalogo(cache_id, "productos")
            }
            if usuario_id is None and cache_usuario_id is not None:
                filas_por_id.update(
                    {
                        str(fila.get("id")): fila
                        for fila in obtener_catalogo(cache_usuario_id, "productos")
                    }
                )
            if not filas_por_id:
                raise SupabaseNoDisponible(
                    "No hay productos guardados para consultar sin conexión."
                )
            filas = list(filas_por_id.values())
            random.shuffle(filas)
            filas = filas[: int(limit)]
        return [Producto.desde_fila(tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2", "categoria", "descripcion", "estado_producto", "etiquetas", "estilo", "color_principal", "material", "garantia", "especificacion"))) for fila in filas]
    conn = get_db_connection()
    cursor = conn.cursor()
    if usuario_id is not None:
        cursor.execute(
            """
            SELECT p.id, p.nombre, p.marca, p.talla, p.precio_cordobas, p.precio_dolares, p.stock, p.tienda_id, p.imagen, p.imagen_2, p.categoria,
            p.descripcion, p.estado_producto, p.etiquetas, p.estilo, p.color_principal, p.material, p.garantia, p.especificacion
            FROM productos p
            INNER JOIN tiendas t ON t.id = p.tienda_id
            WHERE t.usuario_id = ?
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (usuario_id, limit),
        )
    else:
        cursor.execute(
            "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen, imagen_2, categoria, descripcion, estado_producto, etiquetas, estilo, color_principal, material, garantia, especificacion FROM productos ORDER BY RANDOM() LIMIT ?",
            (limit,),
        )
    productos = cursor.fetchall()
    conn.close()
    return [Producto.desde_fila(fila) for fila in productos]




def obtener_top_productos(limit=10, min_compras=3):
    if _supabase_activo():
        filas = _supabase_lista(
            "top_productos",
            f"?select=id,nombre,precio_cordobas,precio_dolares,stock,compras"
            f"&compras=gte.{int(min_compras)}&order=compras.desc&limit={int(limit)}",
        )
        return [
            ProductoDestacado.desde_fila(
                (
                    fila.get("id"),
                    fila.get("nombre"),
                    fila.get("precio_cordobas"),
                    fila.get("precio_dolares"),
                    fila.get("stock"),
                    fila.get("compras", 0),
                )
            )
            for fila in filas
        ]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.nombre, p.precio_cordobas, p.precio_dolares, p.stock,
               COUNT(r.id) as compras
        FROM productos p
        JOIN reservas r ON r.producto_id = p.id AND r.estado = 'Pagado'
        GROUP BY p.id
        HAVING COUNT(r.id) >= ?
        ORDER BY compras DESC
        LIMIT ?
    """,
        (min_compras, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [ProductoDestacado.desde_fila(fila) for fila in rows]




def registrar_producto(
    nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen=None, usuario_id=None,
    categoria="General", imagen_2=None, descripcion=None, estado_producto="Nuevo", etiquetas=None,
    estilo=None, color_principal=None, material=None, garantia=None, especificacion=None
):
    if tienda_id is None:
        return False
    if _supabase_activo():
        datos = {
            "nombre": nombre,
            "marca": marca,
            "talla": talla,
            "precio_cordobas": precio_cordobas,
            "precio_dolares": precio_dolares,
            "stock": stock,
            "tienda_id": tienda_id,
            "imagen": imagen,
            "categoria": categoria or "General",
            "imagen_2": imagen_2,
            "descripcion": descripcion,
            "estado_producto": estado_producto or "Nuevo",
            "etiquetas": etiquetas,
            "estilo": estilo,
            "color_principal": color_principal,
            "material": material,
            "garantia": garantia,
            "especificacion": especificacion,
        }
        if es_id_local(tienda_id):
            tiendas = obtener_catalogo(usuario_id, "tiendas")
            if not any(str(fila.get("id")) == str(tienda_id) for fila in tiendas):
                return False
            producto_id = nuevo_id_local(usuario_id, "productos")
            encolar_creacion(usuario_id, "productos", producto_id, datos)
            return True
        try:
            tienda = _supabase_unico("tiendas", f"?select=id&usuario_id=eq.{usuario_id}&id=eq.{tienda_id}&limit=1")
            if not tienda:
                return False
            producto = _supabase_insertar("productos", datos)
        except SupabaseNoDisponible:
            tiendas = obtener_catalogo(usuario_id, "tiendas")
            if not any(str(fila.get("id")) == str(tienda_id) for fila in tiendas):
                return False
            producto_id = nuevo_id_local(usuario_id, "productos")
            encolar_creacion(usuario_id, "productos", producto_id, datos)
            return True
        if isinstance(producto, dict) and producto.get("id") is not None:
            agregar_elemento_catalogo(usuario_id, "productos", producto)
            agregar_elemento_catalogo(PUBLIC_CACHE_USER_ID, "productos", producto)
        return True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM tiendas WHERE id = ? AND usuario_id = ?",
        (tienda_id, usuario_id),
    )
    if not cursor.fetchone():
        conn.close()
        return False
    cursor.execute(
        """
        INSERT INTO productos (
            nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen,
            categoria, imagen_2, descripcion, estado_producto, etiquetas, estilo,
            color_principal, material, garantia, especificacion
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        (
            nombre,
            marca,
            talla,
            precio_cordobas,
            precio_dolares,
            stock,
            tienda_id,
            imagen,
            categoria or "General",
            imagen_2,
            descripcion,
            estado_producto or "Nuevo",
            etiquetas,
            estilo,
            color_principal,
            material,
            garantia,
            especificacion,
        ),
    )
    conn.commit()
    conn.close()
    return True




def actualizar_producto(producto_id, usuario_id, nombre, marca, talla, precio_cordobas, precio_dolares, stock):
    if _supabase_activo():
        cambios = {
            "nombre": nombre,
            "marca": marca,
            "talla": talla,
            "precio_cordobas": precio_cordobas,
            "precio_dolares": precio_dolares,
            "stock": stock,
        }
        if es_id_local(producto_id):
            productos = obtener_catalogo(usuario_id, "productos")
            if not any(str(fila.get("id")) == str(producto_id) for fila in productos):
                return False
            if not encolar_actualizacion(usuario_id, "productos", producto_id, cambios):
                return False
            actualizar_elemento_catalogo(usuario_id, "productos", producto_id, cambios)
            return True
        try:
            producto = _supabase_unico("productos", f"?select=tienda_id&id=eq.{producto_id}&limit=1")
            if not producto:
                return False
            tienda = _supabase_unico("tiendas", f"?select=id&usuario_id=eq.{usuario_id}&id=eq.{producto['tienda_id']}&limit=1")
            if not tienda:
                return False
            resultado = _supabase_actualizar(
                "productos",
                cambios,
                f"?id=eq.{producto_id}",
            )
        except SupabaseNoDisponible:
            productos = obtener_catalogo(usuario_id, "productos")
            if not any(str(fila.get("id")) == str(producto_id) for fila in productos):
                return False
            if not encolar_actualizacion(usuario_id, "productos", producto_id, cambios):
                return False
            actualizar_elemento_catalogo(usuario_id, "productos", producto_id, cambios)
            return True
        if resultado:
            actualizar_elemento_catalogo(usuario_id, "productos", producto_id, cambios)
        return bool(resultado)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE productos
        SET nombre = ?, marca = ?, talla = ?, precio_cordobas = ?,
            precio_dolares = ?, stock = ?
        WHERE id = ? AND tienda_id IN (SELECT id FROM tiendas WHERE usuario_id = ?)
        """,
        (nombre, marca, talla, precio_cordobas, precio_dolares, stock, producto_id, usuario_id),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return actualizado




def obtener_productos():
    if _supabase_activo():
        filas = _supabase_lista("productos", "?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2")
        return [ProductoBasico.desde_fila(tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2"))) for fila in filas]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen, imagen_2 FROM productos"
    )
    productos = cursor.fetchall()
    conn.close()
    return [ProductoBasico.desde_fila(fila) for fila in productos]




def registrar_busqueda_sin_resultado(usuario_id, termino):
    """Registra una oportunidad para otros usuarios, nunca para quien buscó."""
    termino = str(termino or "").strip()
    if not usuario_id or len(termino) < 4:
        return False

    if _supabase_activo():
        _supabase_insertar(
            "solicitudes_productos",
            {"usuario_id": usuario_id, "termino": termino, "atendida": False},
        )
        return True

    return False




def obtener_oportunidades_productos(usuario_id, limite=20):
    """Devuelve búsquedas de otros usuarios que aún no tienen producto publicado."""
    if not _supabase_activo():
        return []

    solicitudes = _supabase_lista(
        "solicitudes_productos",
        f"?select=termino&atendida=eq.false&usuario_id=neq.{usuario_id}&order=creado_en.desc&limit={int(limite)}",
    )
    productos = _supabase_lista("productos", "?select=nombre")
    nombres_productos = {
        str(fila.get("nombre") or "").strip().lower()
        for fila in productos
        if fila.get("nombre")
    }

    oportunidades = []
    vistos = set()
    for solicitud in solicitudes:
        termino = str(solicitud.get("termino") or "").strip()
        clave = termino.lower()
        if termino and clave not in nombres_productos and clave not in vistos:
            vistos.add(clave)
            oportunidades.append(termino)
    return oportunidades




def obtener_productos_usuario(usuario_id):
    if _supabase_activo():
        try:
            filas_remotas = _supabase_lista("productos", f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion,tiendas!inner(usuario_id)&tiendas.usuario_id=eq.{usuario_id}")
            guardar_catalogo(usuario_id, "productos", filas_remotas)
        except SupabaseNoDisponible:
            pass
        filas = obtener_catalogo(usuario_id, "productos")
        return [Producto.desde_fila(tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2", "categoria", "descripcion", "estado_producto", "etiquetas", "estilo", "color_principal", "material", "garantia", "especificacion"))) for fila in filas]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
         SELECT p.id, p.nombre, p.marca, p.talla, p.precio_cordobas,
             p.precio_dolares, p.stock, p.tienda_id, p.imagen, p.imagen_2, p.categoria,
             p.descripcion, p.estado_producto, p.etiquetas, p.estilo, p.color_principal, p.material, p.garantia, p.especificacion
        FROM productos p
        INNER JOIN tiendas t ON t.id = p.tienda_id
        WHERE t.usuario_id = ?
        """,
        (usuario_id,),
    )
    productos = cursor.fetchall()
    conn.close()
    return [Producto.desde_fila(fila) for fila in productos]




def obtener_producto_por_id(producto_id):
    if _supabase_activo():
        fila = _supabase_unico("productos", f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion&id=eq.{producto_id}&limit=1")
        return ProductoReserva.desde_fila(tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id"))) if fila else None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen, categoria, descripcion, estado_producto, etiquetas, estilo, color_principal, material, garantia, especificacion "
        "FROM productos WHERE id = ?",
        (producto_id,),
    )
    producto = cursor.fetchone()
    conn.close()
    return ProductoReserva.desde_fila(producto) if producto else None




def obtener_productos_por_nombre(nombre_filtro, usuario_id=None, cache_usuario_id=None):
    if _supabase_activo():
        valor = quote(str(nombre_filtro), safe="")
        if usuario_id is not None:
            try:
                filas_remotas = _supabase_lista(
                    "productos",
                    f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion,tiendas!inner(usuario_id)&tiendas.usuario_id=eq.{usuario_id}&nombre=ilike.*{valor}*&limit=50",
                )
                filas = filas_remotas
            except SupabaseNoDisponible:
                termino = str(nombre_filtro or "").casefold()
                filas = [
                    fila for fila in obtener_catalogo(usuario_id, "productos")
                    if termino in str(fila.get("nombre") or "").casefold()
                ][:50]
        else:
            try:
                filas = _supabase_lista(
                    "productos",
                    f"?select=id,nombre,marca,talla,precio_cordobas,precio_dolares,stock,tienda_id,imagen,imagen_2,categoria,descripcion,estado_producto,etiquetas,estilo,color_principal,material,garantia,especificacion&nombre=ilike.*{valor}*&limit=50",
                )
                for fila in filas:
                    agregar_elemento_catalogo(PUBLIC_CACHE_USER_ID, "productos", fila)
            except SupabaseNoDisponible:
                cache_por_id = {
                    str(fila.get("id")): fila
                    for fila in obtener_catalogo(PUBLIC_CACHE_USER_ID, "productos")
                }
                if cache_usuario_id is not None:
                    cache_por_id.update(
                        {
                            str(fila.get("id")): fila
                            for fila in obtener_catalogo(cache_usuario_id, "productos")
                        }
                    )
                if not cache_por_id:
                    raise SupabaseNoDisponible(
                        "No hay productos guardados para buscar sin conexión."
                    )
                termino = str(nombre_filtro or "").casefold()
                filas = [
                    fila for fila in cache_por_id.values()
                    if termino in str(fila.get("nombre") or "").casefold()
                ][:50]
        return [Producto.desde_fila(tuple(fila.get(campo) for campo in ("id", "nombre", "marca", "talla", "precio_cordobas", "precio_dolares", "stock", "tienda_id", "imagen", "imagen_2", "categoria", "descripcion", "estado_producto", "etiquetas", "estilo", "color_principal", "material", "garantia", "especificacion"))) for fila in filas]
    conn = get_db_connection()
    cursor = conn.cursor()
    if usuario_id is not None:
        cursor.execute(
            """
            SELECT p.id, p.nombre, p.marca, p.talla, p.precio_cordobas, p.precio_dolares, p.stock, p.tienda_id, p.imagen, p.imagen_2, p.categoria,
            p.descripcion, p.estado_producto, p.etiquetas, p.estilo, p.color_principal, p.material, p.garantia, p.especificacion
            FROM productos p
            INNER JOIN tiendas t ON t.id = p.tienda_id
            WHERE t.usuario_id = ? AND p.nombre LIKE ?
            """,
            (usuario_id, f"%{nombre_filtro}%"),
        )
    else:
        cursor.execute(
            "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock, tienda_id, imagen, imagen_2, categoria, descripcion, estado_producto, etiquetas, estilo, color_principal, material, garantia, especificacion FROM productos WHERE nombre LIKE ?",
            (f"%{nombre_filtro}%",),
        )
    productos = cursor.fetchall()
    conn.close()
    return [Producto.desde_fila(fila) for fila in productos]




def obtener_productos_por_tienda(tienda_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nombre, marca, talla, precio_cordobas, precio_dolares, stock FROM productos WHERE tienda_id = ?",
        (tienda_id,),
    )
    productos = cursor.fetchall()
    conn.close()
    return [ProductoTienda.desde_fila(fila) for fila in productos]




def obtener_stock_total():
    if _supabase_activo():
        filas = _supabase_lista("productos", "?select=stock")
        return sum(int(fila.get("stock") or 0) for fila in filas)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(stock) FROM productos")
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total




def obtener_stock_total_usuario(usuario_id):
    if _supabase_activo():
        return sum(int(fila.stock or 0) for fila in obtener_productos_usuario(usuario_id))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT SUM(p.stock)
        FROM productos p
        INNER JOIN tiendas t ON t.id = p.tienda_id
        WHERE t.usuario_id = ?
        """,
        (usuario_id,),
    )
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total




def obtener_alertas_inventario(usuario_id, limite_stock=1):
    """Devuelve productos con exactamente una unidad disponible."""
    if _supabase_activo():
        filas = _supabase_lista(
            "productos",
            f"?select=id,nombre,stock,tiendas!inner(usuario_id)&tiendas.usuario_id=eq.{usuario_id}&stock=eq.{int(limite_stock)}&order=nombre.asc&limit=20",
        )
        return [
            AlertaInventario(fila.get("id"), fila.get("nombre"), int(fila.get("stock") or 0))
            for fila in filas
        ]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.nombre, p.stock
        FROM productos p
        INNER JOIN tiendas t ON t.id = p.tienda_id
        WHERE t.usuario_id = ? AND p.stock = ?
        ORDER BY p.nombre ASC
        LIMIT 20
        """,
        (usuario_id, limite_stock),
    )
    alertas = cursor.fetchall()
    conn.close()
    return [AlertaInventario.desde_fila(fila) for fila in alertas]

def eliminar_producto(producto_id, usuario_id):
    if _supabase_activo():
        try:
            producto = _supabase_unico("productos", f"?select=tienda_id&id=eq.{producto_id}&limit=1")
            if not producto:
                return False
            tienda = _supabase_unico("tiendas", f"?select=id&usuario_id=eq.{usuario_id}&id=eq.{producto['tienda_id']}&limit=1")
            if not tienda:
                return False
            _supabase_borrar("productos", f"?id=eq.{producto_id}")
        except SupabaseNoDisponible:
            return False
        return True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM productos
        WHERE id = ? AND tienda_id IN (SELECT id FROM tiendas WHERE usuario_id = ?)
        """,
        (producto_id, usuario_id),
    )
    eliminado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return eliminado




def _reducir_stock_offline(producto_id, cantidad, usuario_id):
    productos = obtener_catalogo(usuario_id, "productos")
    tiendas = obtener_catalogo(usuario_id, "tiendas")
    producto = next(
        (fila for fila in productos if str(fila.get("id")) == str(producto_id)),
        None,
    )
    if not producto or not any(
        str(fila.get("id")) == str(producto.get("tienda_id"))
        for fila in tiendas
    ):
        return False
    stock_actual = int(producto.get("stock") or 0)
    if int(cantidad) <= 0 or int(cantidad) > stock_actual:
        return False
    cambios = {"stock": stock_actual - int(cantidad)}
    if not encolar_actualizacion(usuario_id, "productos", producto_id, cambios):
        return False
    actualizar_elemento_catalogo(usuario_id, "productos", producto_id, cambios)
    return True


def reducir_stock_producto(producto_id, cantidad, usuario_id):
    if _supabase_activo():
        try:
            producto = _supabase_unico("productos", f"?select=stock,tienda_id&id=eq.{producto_id}&limit=1")
            if not producto or int(cantidad) <= 0 or int(cantidad) > int(producto.get("stock") or 0):
                return False
            tienda = _supabase_unico("tiendas", f"?select=id&usuario_id=eq.{usuario_id}&id=eq.{producto['tienda_id']}&limit=1")
            if not tienda:
                return False
            restante = int(producto["stock"]) - int(cantidad)
            if restante == 0:
                _supabase_borrar("productos", f"?id=eq.{producto_id}")
            else:
                _supabase_actualizar("productos", {"stock": restante}, f"?id=eq.{producto_id}")
            return True
        except SupabaseNoDisponible:
            return _reducir_stock_offline(producto_id, cantidad, usuario_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.stock
        FROM productos p
        INNER JOIN tiendas t ON t.id = p.tienda_id
        WHERE p.id = ? AND t.usuario_id = ?
        """,
        (producto_id, usuario_id),
    )
    producto = cursor.fetchone()
    if not producto or cantidad <= 0 or cantidad > producto[0]:
        conn.close()
        return False

    stock_restante = producto[0] - cantidad
    if stock_restante == 0:
        cursor.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
    else:
        cursor.execute(
            "UPDATE productos SET stock = ? WHERE id = ?",
            (stock_restante, producto_id),
        )
    conn.commit()
    conn.close()
    return True
