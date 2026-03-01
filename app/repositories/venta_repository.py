"""Repositorio de Ventas — Capa de acceso a datos.

ÚNICA capa que interactúa con Supabase. Los services nunca tocan la DB directamente.
Todas las operaciones son idempotentes cuando aplica.
"""

from uuid import UUID

import structlog
from postgrest.exceptions import APIError
from supabase import Client

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.venta import VentaCreate, VentaResponse

logger = structlog.get_logger()


class VentaRepository:
    """Repositorio para operaciones CRUD de ventas en Supabase.

    Attributes:
        db: Cliente de Supabase inyectado via Depends().
    """

    def __init__(self, db: Client) -> None:
        self.db = db
        self._table = "transacciones"
        self._columns = (
            "id, producto_id, cliente_id, tipo, cantidad, "
            "precio_unitario, monto_total, descripcion, created_at"
        )

    async def create(self, venta: VentaCreate) -> VentaResponse:
        """Inserta una nueva venta en la base de datos.

        Args:
            venta: Datos validados de la venta a crear.

        Returns:
            La venta creada con ID y timestamp.

        Raises:
            DatabaseError: Si falla la inserción.
        """
        payload = {
            "producto_id": str(venta.producto_id),
            "cliente_id": str(venta.cliente_id) if venta.cliente_id else None,
            "cantidad": venta.cantidad,
            "precio_unitario": str(venta.precio_unitario),
            "monto_total": str(venta.monto_total),
            "descripcion": venta.descripcion,
        }

        try:
            response = self.db.table(self._table).insert(payload).execute()
            logger.info("venta_created", venta_id=response.data[0]["id"])
            return VentaResponse(**response.data[0])

        except APIError as exc:
            logger.error("venta_create_failed", error=str(exc), payload=payload)
            raise DatabaseError(operation="INSERT venta", detail=str(exc)) from exc

    async def get_by_id(self, venta_id: UUID) -> VentaResponse:
        """Obtiene una venta por su ID.

        Args:
            venta_id: UUID de la venta a buscar.

        Returns:
            La venta encontrada.

        Raises:
            ResourceNotFoundError: Si la venta no existe.
            DatabaseError: Si falla la consulta.
        """
        try:
            response = (
                self.db.table(self._table).select(self._columns).eq("id", str(venta_id)).execute()
            )

            if not response.data:
                raise ResourceNotFoundError(resource="Venta", resource_id=str(venta_id))

            return VentaResponse(**response.data[0])

        except ResourceNotFoundError:
            raise
        except APIError as exc:
            logger.error("venta_get_failed", venta_id=str(venta_id), error=str(exc))
            raise DatabaseError(operation="SELECT venta", detail=str(exc)) from exc

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[VentaResponse]:
        """Lista todas las ventas con paginación.

        Args:
            limit: Máximo de resultados (default 50).
            offset: Desplazamiento para paginación.

        Returns:
            Lista de ventas.

        Raises:
            DatabaseError: Si falla la consulta.
        """
        try:
            response = (
                self.db.table(self._table)
                .select(self._columns)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            return [VentaResponse(**row) for row in response.data]

        except APIError as exc:
            logger.error("ventas_list_failed", error=str(exc))
            raise DatabaseError(operation="SELECT ventas", detail=str(exc)) from exc

    async def delete(self, venta_id: UUID) -> None:
        """Elimina una venta por su ID.

        Args:
            venta_id: UUID de la venta a eliminar.

        Raises:
            ResourceNotFoundError: Si la venta no existe.
            DatabaseError: Si falla la eliminación.
        """
        # Verificar que existe antes de eliminar
        await self.get_by_id(venta_id)

        try:
            self.db.table(self._table).delete().eq("id", str(venta_id)).execute()
            logger.info("venta_deleted", venta_id=str(venta_id))

        except APIError as exc:
            logger.error("venta_delete_failed", venta_id=str(venta_id), error=str(exc))
            raise DatabaseError(operation="DELETE venta", detail=str(exc)) from exc

    def get_por_rango(
        self,
        inicio: str,
        fin: str,
        tipo: str = "venta",
    ) -> list[dict]:
        """Obtiene transacciones en un rango de fechas.

        Args:
            inicio: Fecha inicio ISO format.
            fin: Fecha fin ISO format.
            tipo: Tipo de transacción ("venta" o "compra").

        Returns:
            Lista de transacciones con datos de producto y cliente.
        """
        try:
            result = (
                self.db.table(self._table)
                .select(
                    "cantidad, monto_total, created_at, descripcion, "
                    "precio_unitario, productos(nombre), clientes(nombre)"
                )
                .eq("tipo", tipo)
                .gte("created_at", inicio)
                .lte("created_at", fin)
                .execute()
            )
            return result.data if result.data else []
        except APIError as exc:
            logger.error("ventas_rango_failed", error=str(exc))
            raise DatabaseError(operation="SELECT ventas rango", detail=str(exc)) from exc
