"""Modelos tipados para representar registros de la base de datos."""

from __future__ import annotations

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
    def desde_fila(cls, fila: Sequence[Any] | "Tienda") -> "Tienda":
        """Convierte una fila existente en un objeto con campos nombrados."""
        return fila if isinstance(fila, cls) else cls(*fila[:8])


@dataclass(frozen=True, slots=True)
class SesionAutenticada:
    """Tokens y cuenta entregados al completar el inicio de sesión remoto."""

    access_token: str
    refresh_token: str | None
    usuario: UsuarioSesion


@dataclass(frozen=True, slots=True)
class UsuarioSesion:
    """Datos mínimos de una cuenta autenticada para la sesión de la app."""

    id: int | str
    nombre: str
    correo: str


@dataclass(frozen=True, slots=True)
class PerfilUsuario:
    """Datos de perfil necesarios para mostrar y editar una cuenta."""

    id: int | str
    nombre: str
    correo: str
    telefono: str | None = None
    fecha_nacimiento: str | None = None
    imagen: str | None = None
    auth_user_id: str | None = None


@dataclass(frozen=True, slots=True)
class UsuarioRecuperacion:
    """Datos de cuenta consultados durante recuperación de acceso."""

    id: int | str
    nombre: str
    correo: str
    telefono: str | None = None
    fecha_nacimiento: str | None = None
    contrasena_hash: str | None = None


@dataclass(frozen=True, slots=True)
class Producto:
    """Producto utilizado como objeto en las listas de búsqueda."""

    id: int
    nombre: str | None
    marca: str | None
    talla: str | None
    precio_cordobas: float | None
    precio_dolares: float | None
    stock: int | None
    tienda_id: int | None
    imagen: str | None
    imagen_2: str | None
    categoria: str | None
    descripcion: str | None
    estado_producto: str | None
    etiquetas: str | None
    estilo: str | None
    color_principal: str | None
    material: str | None
    garantia: str | None
    especificacion: str | None

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "Producto") -> "Producto":
        """Convierte una fila del resultado SQL/Supabase en un Producto."""
        if isinstance(fila, cls):
            return fila
        if len(fila) < 19:
            raise ValueError(f"Se esperaban 19 campos para Producto; se recibieron {len(fila)}")
        return cls(*fila[:19])


@dataclass(frozen=True, slots=True)
class ProductoPendiente:
    """Producto capturado en el formulario antes de guardarse en la tienda."""

    nombre: str
    marca: str | None
    talla: str | None
    precio_cordobas: float
    precio_dolares: float
    cantidad: int
    imagen: str | None
    categoria: str | None
    imagen_2: str | None
    descripcion: str
    estado_producto: str
    etiquetas: str
    color_principal: str
    material: str
    garantia: str
    especificacion: str


@dataclass(frozen=True, slots=True)
class ProductoBasico:
    """Campos generales usados para mostrar productos en listados compactos."""

    id: int
    nombre: str | None
    marca: str | None
    talla: str | None
    precio_cordobas: float | None
    precio_dolares: float | None
    stock: int | None
    tienda_id: int | None
    imagen: str | None
    imagen_2: str | None

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "ProductoBasico") -> "ProductoBasico":
        return fila if isinstance(fila, cls) else cls(*fila[:10])


@dataclass(frozen=True, slots=True)
class ProductoTienda:
    """Campos compactos de producto asociados a una tienda."""

    id: int
    nombre: str | None
    marca: str | None
    talla: str | None
    precio_cordobas: float | None
    precio_dolares: float | None
    stock: int | None

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "ProductoTienda") -> "ProductoTienda":
        return fila if isinstance(fila, cls) else cls(*fila[:7])


@dataclass(frozen=True, slots=True)
class VentaDiaria:
    """Total de ventas agrupado por día."""

    fecha: str
    total: float

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "VentaDiaria") -> "VentaDiaria":
        return fila if isinstance(fila, cls) else cls(*fila[:2])


@dataclass(frozen=True, slots=True)
class AlertaInventario:
    """Producto con existencias que requieren atención."""

    id: int
    nombre: str | None
    stock: int

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "AlertaInventario") -> "AlertaInventario":
        return fila if isinstance(fila, cls) else cls(*fila[:3])


@dataclass(frozen=True, slots=True)
class ProductoReserva:
    """Campos de producto necesarios para iniciar una reserva."""

    id: int
    nombre: str | None
    marca: str | None
    talla: str | None
    precio_cordobas: float | None
    precio_dolares: float | None
    stock: int | None
    tienda_id: int | None

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "ProductoReserva") -> "ProductoReserva":
        return fila if isinstance(fila, cls) else cls(*fila[:8])


@dataclass(frozen=True, slots=True)
class ProductoDestacado:
    """Producto del top, clasificado automáticamente por compras pagadas."""

    id: int
    nombre: str | None
    precio_cordobas: float | None
    precio_dolares: float | None
    stock: int | None
    compras: int

    @property
    def estrellas_popularidad(self) -> int:
        """Asigna una a cinco estrellas según la cantidad de compras pagadas.

        Tres compras obtienen una estrella; cada dos compras adicionales
        suman otra, hasta un máximo de cinco.
        """
        return max(1, min(5, 1 + (self.compras - 3) // 2))

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "ProductoDestacado") -> "ProductoDestacado":
        return fila if isinstance(fila, cls) else cls(*fila[:6])


@dataclass(frozen=True, slots=True)
class ReservaCliente:
    """Reserva mostrada al cliente en su carrito."""

    id: int
    producto: str | None
    cantidad: int
    precio_cordobas: float | None
    precio_dolares: float | None
    estado: str | None
    tienda_id: int | None

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "ReservaCliente") -> "ReservaCliente":
        return fila if isinstance(fila, cls) else cls(*fila[:7])


@dataclass(frozen=True, slots=True)
class ReservaTienda:
    """Reserva activa presentada en el panel de una tienda."""

    id: int
    producto: str | None
    cantidad: int
    total: float | None
    cliente: str | None
    fecha: str | None
    estado: str | None

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "ReservaTienda") -> "ReservaTienda":
        return fila if isinstance(fila, cls) else cls(*fila[:7])


@dataclass(frozen=True, slots=True)
class EntregaTienda:
    """Entrega completada presentada en el historial de la tienda."""

    id: int
    producto: str | None
    cantidad: int
    total: float | None
    cliente: str | None
    fecha_entrega: str | None

    @classmethod
    def desde_fila(cls, fila: Sequence[Any] | "EntregaTienda") -> "EntregaTienda":
        return fila if isinstance(fila, cls) else cls(*fila[:6])
