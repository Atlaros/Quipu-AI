"""Servicio de Productos — Capa de lógica de negocio.

Orquesta las reglas de negocio para productos. Recibe datos validados
del router y delega la persistencia al repository.
"""

from decimal import Decimal
from uuid import UUID

import structlog

from app.core.exceptions import DuplicateResourceError, ValidationError
from app.models.producto import ProductoCreate, ProductoResponse
from app.repositories.producto_repository import ProductoRepository

logger = structlog.get_logger()


class ProductoService:
    """Servicio que encapsula la lógica de negocio de productos.

    Attributes:
        repository: Repositorio de productos inyectado.
    """

    PRECIO_MAXIMO: Decimal = Decimal("99999.99")

    def __init__(self, repository: ProductoRepository) -> None:
        self.repository = repository

    async def crear_producto(
        self, data: ProductoCreate
    ) -> ProductoResponse:
        """Crea un nuevo producto con validaciones de negocio.

        Args:
            data: Datos del producto validados por Pydantic.

        Returns:
            El producto creado.

        Raises:
            DuplicateResourceError: Si el nombre ya existe.
            ValidationError: Si el precio excede el máximo.
        """
        # Regla: precio máximo
        if data.precio_unitario > self.PRECIO_MAXIMO:
            raise ValidationError(
                f"Precio {data.precio_unitario} excede el máximo "
                f"permitido ({self.PRECIO_MAXIMO})"
            )

        # Regla: nombre único
        existente = await self.repository.get_by_nombre(data.nombre)
        if existente:
            raise DuplicateResourceError(
                resource="Producto",
                field="nombre",
                value=data.nombre,
            )

        logger.info("creando_producto", nombre=data.nombre)
        return await self.repository.create(data)

    async def obtener_producto(self, producto_id: UUID) -> ProductoResponse:
        """Obtiene un producto por su ID.

        Args:
            producto_id: UUID del producto.

        Returns:
            El producto encontrado.
        """
        return await self.repository.get_by_id(producto_id)

    async def listar_productos(
        self, limit: int = 50, offset: int = 0
    ) -> list[ProductoResponse]:
        """Lista productos con paginación.

        Args:
            limit: Máximo de resultados.
            offset: Desplazamiento.

        Returns:
            Lista de productos activos.
        """
        return await self.repository.get_all(limit=limit, offset=offset)

    async def actualizar_precio(
        self, producto_id: UUID, nuevo_precio: Decimal
    ) -> ProductoResponse:
        """Actualiza el precio de un producto.

        Args:
            producto_id: UUID del producto.
            nuevo_precio: Nuevo precio unitario.

        Returns:
            El producto actualizado.

        Raises:
            ValidationError: Si el precio es inválido.
        """
        if nuevo_precio <= 0:
            raise ValidationError("El precio debe ser mayor a 0")

        if nuevo_precio > self.PRECIO_MAXIMO:
            raise ValidationError(
                f"Precio {nuevo_precio} excede el máximo "
                f"permitido ({self.PRECIO_MAXIMO})"
            )

        logger.info(
            "actualizando_precio",
            producto_id=str(producto_id),
            nuevo_precio=str(nuevo_precio),
        )
        return await self.repository.update(
            producto_id, {"precio_unitario": str(nuevo_precio)}
        )

    async def eliminar_producto(self, producto_id: UUID) -> None:
        """Elimina un producto (soft delete).

        Args:
            producto_id: UUID del producto a eliminar.
        """
        logger.info("eliminando_producto", producto_id=str(producto_id))
        await self.repository.delete(producto_id)
