"""Búsqueda lineal de productos dentro de una lista ya cargada."""


def buscar_productos_linealmente(productos, termino):
    """Devuelve todas las filas cuyo nombre contiene el término buscado.

    La función recorre la lista completa y no se detiene al encontrar la primera
    coincidencia. La base de datos sigue limitando la consulta al catálogo
    coincidente antes de esta etapa, evitando cargar todo el catálogo en memoria.
    """
    termino_normalizado = str(termino or "").strip().casefold()
    if not termino_normalizado:
        return []

    coincidencias = []
    for producto in productos:
        if len(producto) > 1 and termino_normalizado in str(producto[1] or "").casefold():
            coincidencias.append(producto)
    return coincidencias
