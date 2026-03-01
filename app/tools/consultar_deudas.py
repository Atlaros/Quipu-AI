"""Tool: Consultar Deudas Pendientes.

Tool callable por el agente LangGraph para listar las deudas
o créditos pendientes de cobro. Usa DeudaRepository.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client
from app.core.exceptions import DatabaseError
from app.repositories.deuda_repository import DeudaRepository

logger = structlog.get_logger()


@tool
def consultar_deudas(cliente_nombre: str = "") -> str:
    """Consulta las deudas pendientes de cobro.

    Permite buscar por cliente específico o ver todas las deudas activas.

    Args:
        cliente_nombre: Nombre del cliente a buscar (opcional).
                        Si está vacío, muestra todas las deudas pendientes.

    Returns:
        Lista de deudas pendientes con monto total.
    """
    db = get_supabase_client()
    deuda_repo = DeudaRepository(db)

    try:
        deudas = deuda_repo.get_pendientes(cliente_nombre)

        if not deudas:
            if cliente_nombre:
                return f"✅ {cliente_nombre} no tiene deudas pendientes."
            return "✅ No hay deudas pendientes. ¡Todo cobrado!"

        total = sum(float(row["monto"]) for row in deudas)
        titulo = (
            f"💳 **Deudas de {cliente_nombre}:**"
            if cliente_nombre
            else f"💳 **Deudas pendientes ({len(deudas)} clientes):**"
        )
        lines = [titulo]

        for row in deudas:
            venc = f" | vence {row['fecha_vencimiento']}" if row.get("fecha_vencimiento") else ""
            lines.append(
                f"• {row['cliente_nombre']}: S/{float(row['monto']):.2f} "
                f"— {row['descripcion']}{venc}"
            )

        lines.append(f"\n💰 **Total pendiente: S/{total:.2f}**")

        logger.info("consultar_deudas", num_deudas=len(deudas), total=total)
        return "\n".join(lines)

    except DatabaseError as exc:
        logger.error("tool_consultar_deudas_db_error", error=str(exc))
        return f"❌ Error de base de datos: {exc.message}"
    except Exception as exc:
        logger.error("tool_consultar_deudas_failed", error=str(exc))
        return f"❌ Error al consultar deudas: {exc!s}"
