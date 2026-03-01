"""Service de Inventario — Lógica de negocio.

Gestión de stock con alertas de mínimos.
"""

from uuid import UUID

import structlog

from app.core.exceptions import ValidationError
from app.models.inventario import InventarioResponse, InventarioUpdate
from app.repositories.inventario_repository import InventarioRepository

logger = structlog.get_logger()


class InventarioService:
    """Servicio de inventario con reglas de negocio.

    Args:
        repository: Repositorio de inventario inyectado.
    """

    STOCK_MAXIMO: int = 10_000

    def __init__(self, repository: InventarioRepository) -> None:
        self.repository = repository

    async def consultar_stock(self, producto_id: UUID) -> InventarioResponse:
        """Consulta el stock de un producto.

        Args:
            producto_id: UUID del producto.

        Returns:
            Datos de inventario del producto.
        """
        return await self.repository.get_by_producto_id(producto_id)

    async def listar_inventario(self) -> list[dict]:
        """Lista todo el inventario con datos de producto.

        Returns:
            Lista completa del inventario.
        """
        return await self.repository.get_all()

    async def obtener_alertas_stock(self) -> list[dict]:
        """Obtiene productos con stock bajo.

        Returns:
            Lista de productos con stock igual o bajo al mínimo.
        """
        return await self.repository.get_stock_bajo()

    async def actualizar_stock(
        self, producto_id: UUID, data: InventarioUpdate
    ) -> InventarioResponse:
        """Actualiza el stock validando límites.

        Args:
            producto_id: UUID del producto.
            data: Nuevos valores de stock.

        Returns:
            Inventario actualizado.

        Raises:
            ValidationError: Si la cantidad excede el máximo permitido.
        """
        if data.cantidad_actual > self.STOCK_MAXIMO:
            raise ValidationError(
                message=(
                    f"Cantidad {data.cantidad_actual} excede el máximo "
                    f"permitido ({self.STOCK_MAXIMO})"
                ),
            )

        result = await self.repository.update_stock(producto_id, data)

        # Alerta si el stock queda bajo
        if result.stock_bajo:
            logger.warning(
                "stock_bajo_detectado",
                producto_id=str(producto_id),
                cantidad=result.cantidad_actual,
                minimo=result.cantidad_minima,
            )

        return result
