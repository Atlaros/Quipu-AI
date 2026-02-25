"""Tool: Consultar Deudas Pendientes.

Tool callable por el agente LangGraph para listar las deudas
o créditos pendientes de cobro, por cliente o en total.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client

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

    try:
        query = db.table("deudas").select(
            "cliente_nombre, descripcion, monto, fecha_vencimiento, created_at"
        ).eq("pagado", False).order("created_at", desc=False)

        if cliente_nombre:
            query = query.ilike("cliente_nombre", f"%{cliente_nombre}%")

        result = query.execute()

        if not result.data:
            if cliente_nombre:
                return f"✅ {cliente_nombre} no tiene deudas pendientes."
            return "✅ No hay deudas pendientes. ¡Todo cobrado!"

        total = sum(float(row["monto"]) for row in result.data)
        titulo = (
            f"💳 **Deudas de {cliente_nombre}:**"
            if cliente_nombre
            else f"💳 **Deudas pendientes ({len(result.data)} clientes):**"
        )
        lines = [titulo]

        for row in result.data:
            venc = f" | vence {row['fecha_vencimiento']}" if row.get("fecha_vencimiento") else ""
            lines.append(
                f"• {row['cliente_nombre']}: S/{float(row['monto']):.2f} "
                f"— {row['descripcion']}{venc}"
            )

        lines.append(f"\n💰 **Total pendiente: S/{total:.2f}**")

        logger.info("consultar_deudas", num_deudas=len(result.data), total=total)
        return "\n".join(lines)

    except Exception as exc:
        logger.error("tool_consultar_deudas_failed", error=str(exc))
        return f"❌ Error al consultar deudas: {str(exc)}"
