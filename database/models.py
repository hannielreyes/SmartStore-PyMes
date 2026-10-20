"""Modelos tipados para representar registros da base de dados."""

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class Tienda:
    """Datos de una tienda devueltos por las consultas de la base de datos."""

    id: int
    nombre: str | None
    whatsapp: str | None
    tasa_cambio: float | None
    usuario_id: int | None
    direccion: str | None
    saldo: float
    imagen: str | None

    @classmethod
    def desde_fila(cls, fila: Sequence[Any]) -> "Tienda":
        """Convierte la tupla de tienda existente en un objeto con campos nombrados."""
        return cls(*fila[:8])
