"""Búsqueda lineal de productos dentro de una lista ya cargada."""

from collections.abc import Sequence

from database.models import Producto


def buscar_productos_linealmente(productos: Sequence[Producto], termino: str) -> list[Producto]:
    if not isinstance(productos, Sequence) or isinstance(productos, (str, bytes)):
        raise TypeError("productos debe ser una secuencia de objetos Producto.")

    termino_normalizado = str(termino or "").strip().casefold()
    if not termino_normalizado:
        return []

    coincidencias: list[Producto] = []
    for indice, producto in enumerate(productos):
        if not isinstance(producto, Producto):
            raise TypeError(f"El elemento {indice} de productos no es un objeto Producto.")
        if termino_normalizado in str(producto.nombre or "").casefold():
            coincidencias.append(producto)
    return coincidencias
