"""Repository de Deudas — Capa de acceso a datos.

CRUD contra la tabla 'deudas' en Supabase.
Gestiona créditos pendientes de cobro.
"""

import structlog
from postgrest.exceptions import APIError
from supabase import Client

from app.core.exceptions import DatabaseError

logger = structlog.get_logger()


class DeudaRepository:
    """Repositorio para operaciones de deudas/créditos.

    Attributes:
        db: Cliente Supabase inyectado.
    """

    def __init__(self, db: Client) -> None:
        self.db = db
        self._table = "deudas"

    def create(self, payload: dict) -> dict:
        """Inserta una nueva deuda.

        Args:
            payload: Datos de la deuda (cliente_nombre, descripcion, monto, etc.).

        Returns:
            La deuda creada.

        Raises:
            DatabaseError: Si falla la inserción.
        """
        try:
            result = self.db.table(self._table).insert(payload).execute()
            logger.info("deuda_created", cliente=payload.get("cliente_nombre"))
            return result.data[0] if result.data else {}
        except APIError as exc:
            logger.error("deuda_create_failed", error=str(exc))
            raise DatabaseError(operation="INSERT deuda", detail=str(exc)) from exc

    def get_pendientes(self, cliente_nombre: str = "") -> list[dict]:
        """Lista deudas pendientes, opcionalmente filtradas por cliente.

        Args:
            cliente_nombre: Filtro parcial por nombre de cliente.

        Returns:
            Lista de deudas no pagadas.

        Raises:
            DatabaseError: Si falla la consulta.
        """
        try:
            query = (
                self.db.table(self._table)
                .select("cliente_nombre, descripcion, monto, fecha_vencimiento, created_at")
                .eq("pagado", False)
                .order("created_at", desc=False)
            )

            if cliente_nombre:
                query = query.ilike("cliente_nombre", f"%{cliente_nombre}%")

            result = query.execute()
            return result.data if result.data else []
        except APIError as exc:
            logger.error("deudas_pendientes_failed", error=str(exc))
            raise DatabaseError(operation="SELECT deudas pendientes", detail=str(exc)) from exc
