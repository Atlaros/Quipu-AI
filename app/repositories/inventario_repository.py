"""Repository de Inventario — Capa de acceso a datos.

CRUD contra la tabla 'inventario' en Supabase.
Incluye join con 'productos' para respuestas enriquecidas.
"""

from uuid import UUID

import structlog
from supabase import Client

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.inventario import InventarioResponse, InventarioUpdate

logger = structlog.get_logger()


class InventarioRepository:
    """Repositorio para operaciones de inventario.

    Args:
        db: Cliente Supabase inyectado.
    """

    def __init__(self, db: Client) -> None:
        self.db = db
        self._table = "inventario"

    async def get_by_producto_id(
        self, producto_id: UUID
    ) -> InventarioResponse:
        """Obtiene el inventario de un producto.

        Args:
            producto_id: UUID del producto.

        Returns:
            Registro de inventario.

        Raises:
            ResourceNotFoundError: Si no hay registro para ese producto.
        """
        response = (
            self.db.table(self._table)
            .select("*")
            .eq("producto_id", str(producto_id))
            .execute()
        )

        if not response.data:
            raise ResourceNotFoundError(
                resource="Inventario", resource_id=str(producto_id)
            )

        return InventarioResponse(**response.data[0])

    async def get_all(self) -> list[dict]:
        """Lista todo el inventario con datos del producto.

        Returns:
            Lista de inventario con nombre de producto.
        """
        try:
            response = (
                self.db.table(self._table)
                .select("*, productos(nombre, categoria, precio_unitario)")
                .order("cantidad_actual", desc=False)
                .execute()
            )
            return response.data
        except Exception as exc:
            raise DatabaseError(
                operation="SELECT inventario",
                detail=str(exc),
            ) from exc

    async def get_stock_bajo(self) -> list[dict]:
        """Obtiene productos con stock bajo (actual <= mínimo).

        Returns:
            Lista de productos con stock bajo.
        """
        try:
            response = (
                self.db.table(self._table)
                .select("*, productos(nombre, categoria)")
                .order("cantidad_actual", desc=False)
                .execute()
            )

            # Filtrar en Python: Supabase no soporta comparación columna-a-columna
            return [
                row for row in response.data
                if row["cantidad_actual"] <= row["cantidad_minima"]
            ]
        except Exception as exc:
            raise DatabaseError(
                operation="SELECT inventario stock_bajo",
                detail=str(exc),
            ) from exc

    async def update_stock(
        self, producto_id: UUID, data: InventarioUpdate
    ) -> InventarioResponse:
        """Actualiza el stock de un producto.

        Args:
            producto_id: UUID del producto.
            data: Nuevos valores de stock.

        Returns:
            El registro de inventario actualizado.

        Raises:
            ResourceNotFoundError: Si no hay registro para ese producto.
        """
        payload = data.model_dump()

        response = (
            self.db.table(self._table)
            .update(payload)
            .eq("producto_id", str(producto_id))
            .execute()
        )

        if not response.data:
            raise ResourceNotFoundError(
                resource="Inventario", resource_id=str(producto_id)
            )

        logger.info(
            "stock_updated",
            producto_id=str(producto_id),
            cantidad=data.cantidad_actual,
        )
        return InventarioResponse(**response.data[0])
