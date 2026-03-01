"""Service de Clientes — Lógica de negocio.

Valida duplicados por teléfono antes de crear.
"""

from uuid import UUID

import structlog

from app.core.exceptions import DuplicateResourceError
from app.models.cliente import ClienteCreate, ClienteResponse
from app.repositories.cliente_repository import ClienteRepository

logger = structlog.get_logger()


class ClienteService:
    """Servicio de clientes con reglas de negocio.

    Args:
        repository: Repositorio de clientes inyectado.
    """

    def __init__(self, repository: ClienteRepository) -> None:
        self.repository = repository

    async def registrar_cliente(self, data: ClienteCreate) -> ClienteResponse:
        """Registra un nuevo cliente, validando duplicados por teléfono.

        Args:
            data: Datos del cliente.

        Returns:
            El cliente creado.

        Raises:
            DuplicateResourceError: Si ya existe un cliente con ese teléfono.
        """
        existente = await self.repository.get_by_telefono(data.telefono)
        if existente:
            raise DuplicateResourceError(
                resource="Cliente",
                field="telefono",
                value=data.telefono,
            )

        logger.info("registrando_cliente", nombre=data.nombre)
        return await self.repository.create(data)

    async def obtener_cliente(self, cliente_id: UUID) -> ClienteResponse:
        """Obtiene un cliente por ID.

        Args:
            cliente_id: UUID del cliente.

        Returns:
            El cliente encontrado.
        """
        return await self.repository.get_by_id(cliente_id)

    async def listar_clientes(self, limit: int = 50, offset: int = 0) -> list[ClienteResponse]:
        """Lista clientes con paginación.

        Args:
            limit: Máximo de resultados.
            offset: Desplazamiento.

        Returns:
            Lista de clientes activos.
        """
        return await self.repository.get_all(limit=limit, offset=offset)

    async def actualizar_cliente(self, cliente_id: UUID, data: dict[str, str]) -> ClienteResponse:
        """Actualiza campos de un cliente.

        Args:
            cliente_id: UUID del cliente.
            data: Campos a actualizar.

        Returns:
            El cliente actualizado.
        """
        return await self.repository.update(cliente_id, data)

    async def eliminar_cliente(self, cliente_id: UUID) -> None:
        """Desactiva un cliente (soft delete).

        Args:
            cliente_id: UUID del cliente.
        """
        await self.repository.delete(cliente_id)
