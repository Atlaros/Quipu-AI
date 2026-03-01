"""Repository de Clientes — Capa de acceso a datos.

CRUD contra la tabla 'clientes' en Supabase.
"""

from uuid import UUID

import structlog
from postgrest.exceptions import APIError
from supabase import Client

from app.core.exceptions import DatabaseError, ResourceNotFoundError
from app.models.cliente import ClienteCreate, ClienteResponse

logger = structlog.get_logger()


class ClienteRepository:
    """Repositorio para operaciones CRUD de clientes.

    Args:
        db: Cliente Supabase inyectado.
    """

    def __init__(self, db: Client) -> None:
        self.db = db
        self._table = "clientes"
        self._columns = "id, nombre, telefono, direccion, notas, activo, created_at, updated_at"

    async def create(self, cliente: ClienteCreate) -> ClienteResponse:
        """Crea un nuevo cliente.

        Args:
            cliente: Datos del cliente a crear.

        Returns:
            El cliente creado con ID y timestamps.

        Raises:
            DatabaseError: Si falla la inserción.
        """
        payload = cliente.model_dump()
        try:
            response = self.db.table(self._table).insert(payload).execute()
            logger.info("cliente_created", nombre=cliente.nombre)
            return ClienteResponse(**response.data[0])
        except APIError as exc:
            logger.error("cliente_create_failed", error=str(exc))
            raise DatabaseError(
                operation="INSERT cliente",
                detail=str(exc),
            ) from exc

    async def get_by_id(self, cliente_id: UUID) -> ClienteResponse:
        """Obtiene un cliente por su ID.

        Args:
            cliente_id: UUID del cliente.

        Returns:
            El cliente encontrado.

        Raises:
            ResourceNotFoundError: Si el cliente no existe.
        """
        response = (
            self.db.table(self._table).select(self._columns).eq("id", str(cliente_id)).execute()
        )

        if not response.data:
            raise ResourceNotFoundError(resource="Cliente", resource_id=str(cliente_id))

        return ClienteResponse(**response.data[0])

    async def get_by_telefono(self, telefono: str) -> ClienteResponse | None:
        """Busca un cliente por teléfono.

        Args:
            telefono: Número de teléfono del cliente.

        Returns:
            El cliente si existe, None si no.
        """
        response = (
            self.db.table(self._table).select(self._columns).eq("telefono", telefono).execute()
        )

        if not response.data:
            return None

        return ClienteResponse(**response.data[0])

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[ClienteResponse]:
        """Lista clientes con paginación.

        Args:
            limit: Máximo de resultados.
            offset: Desplazamiento.

        Returns:
            Lista de clientes.
        """
        try:
            response = (
                self.db.table(self._table)
                .select(self._columns)
                .eq("activo", True)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            return [ClienteResponse(**row) for row in response.data]
        except APIError as exc:
            raise DatabaseError(
                operation="SELECT clientes",
                detail=str(exc),
            ) from exc

    async def update(self, cliente_id: UUID, data: dict[str, str]) -> ClienteResponse:
        """Actualiza campos de un cliente.

        Args:
            cliente_id: UUID del cliente.
            data: Campos a actualizar.

        Returns:
            El cliente actualizado.

        Raises:
            ResourceNotFoundError: Si el cliente no existe.
        """
        response = self.db.table(self._table).update(data).eq("id", str(cliente_id)).execute()

        if not response.data:
            raise ResourceNotFoundError(resource="Cliente", resource_id=str(cliente_id))

        logger.info("cliente_updated", cliente_id=str(cliente_id))
        return ClienteResponse(**response.data[0])

    async def delete(self, cliente_id: UUID) -> None:
        """Desactiva un cliente (soft delete).

        Args:
            cliente_id: UUID del cliente.

        Raises:
            ResourceNotFoundError: Si el cliente no existe.
        """
        response = (
            self.db.table(self._table).update({"activo": False}).eq("id", str(cliente_id)).execute()
        )

        if not response.data:
            raise ResourceNotFoundError(resource="Cliente", resource_id=str(cliente_id))

        logger.info("cliente_deactivated", cliente_id=str(cliente_id))

    async def buscar_por_nombre(self, nombre: str) -> ClienteResponse | None:
        """Busca un cliente por nombre (búsqueda parcial).

        Args:
            nombre: Nombre parcial del cliente.

        Returns:
            El cliente si se encuentra, None si no.
        """
        try:
            response = (
                self.db.table(self._table)
                .select("id, nombre")
                .ilike("nombre", f"%{nombre}%")
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            return ClienteResponse(
                **{
                    **response.data[0],
                    "telefono": "",
                    "activo": True,
                    "created_at": "2000-01-01",
                    "updated_at": "2000-01-01",
                }
            )
        except APIError as exc:
            logger.error("cliente_buscar_nombre_failed", error=str(exc))
            return None
