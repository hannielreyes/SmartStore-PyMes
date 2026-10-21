"""Búsqueda lineal de productos dentro de una lista ya cargada."""

from collections.abc import Sequence

from database.models import Producto


def buscar_productos_linealmente(productos: Sequence[Producto], termino: str) -> list[Producto]:
    """Devuelve todos los productos cuyo nombre contiene el término buscado.

    La función recorre la lista completa y no se detiene al encontrar la primera
    coincidencia. La base de datos sigue limitando la consulta al catálogo
    coincidente antes de esta etapa, evitando cargar todo el catálogo en memoria.
    """
    termino_normalizado = str(termino or "").strip().casefold()
    if not termino_normalizado:
        return []

    coincidencias: list[Producto] = []
    for producto in productos:
        if termino_normalizado in str(producto.nombre or "").casefold():
            coincidencias.append(producto)
    return coincidencias
