"""Servicio de Ventas — Capa de lógica de negocio.

Orquesta las reglas de negocio para ventas. Recibe datos validados
del router y delega la persistencia al repository.
"""

from uuid import UUID

import structlog

from app.core.exceptions import ValidationError
from app.models.venta import VentaCreate, VentaResponse
from app.repositories.venta_repository import VentaRepository

logger = structlog.get_logger()


class VentaService:
    """Servicio que encapsula la lógica de negocio de ventas.

    Attributes:
        repository: Repositorio de ventas inyectado.
    """

    def __init__(self, repository: VentaRepository) -> None:
        self.repository = repository

    async def registrar_venta(self, venta_data: VentaCreate) -> VentaResponse:
        """Registra una nueva venta con validaciones de negocio.

        Args:
            venta_data: Datos de la venta ya validados por Pydantic.

        Returns:
            La venta registrada.

        Raises:
            ValidationError: Si las reglas de negocio no se cumplen.
        """
        # Regla de negocio: monto máximo por transacción
        monto_total = venta_data.monto_total
        monto_maximo = 50_000
        if monto_total > monto_maximo:
            raise ValidationError(
                f"Monto total ({monto_total}) excede el máximo permitido ({monto_maximo})"
            )

        logger.info(
            "registrando_venta",
            producto_id=str(venta_data.producto_id),
            monto_total=str(monto_total),
        )

        return await self.repository.create(venta_data)

    async def obtener_venta(self, venta_id: UUID) -> VentaResponse:
        """Obtiene una venta por su ID.

        Args:
            venta_id: UUID de la venta.

        Returns:
            La venta encontrada.
        """
        return await self.repository.get_by_id(venta_id)

    async def listar_ventas(
        self, limit: int = 50, offset: int = 0
    ) -> list[VentaResponse]:
        """Lista ventas con paginación.

        Args:
            limit: Máximo de resultados.
            offset: Desplazamiento.

        Returns:
            Lista de ventas.
        """
        return await self.repository.get_all(limit=limit, offset=offset)

    async def eliminar_venta(self, venta_id: UUID) -> None:
        """Elimina una venta.

        Args:
            venta_id: UUID de la venta a eliminar.
        """
        logger.info("eliminando_venta", venta_id=str(venta_id))
        await self.repository.delete(venta_id)
