"""Tool: Registrar Cliente.

Tool callable por el agente LangGraph para registrar un nuevo
cliente en Supabase.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client

logger = structlog.get_logger()


@tool
def registrar_cliente(nombre: str, telefono: str = "") -> str:
    """Registra un nuevo cliente en la bodega.

    Args:
        nombre: Nombre completo del cliente.
        telefono: Teléfono del cliente (opcional).

    Returns:
        Mensaje de confirmación o error.
    """
    db = get_supabase_client()

    try:
        # Verificar si ya existe
        if telefono:
            existente = (
                db.table("clientes")
                .select("id, nombre")
                .eq("telefono", telefono)
                .limit(1)
                .execute()
            )

            if existente.data:
                return (
                    f"ℹ️ Ya existe un cliente con ese teléfono: "
                    f"{existente.data[0]['nombre']}"
                )

        # Insertar nuevo cliente
        payload: dict[str, str] = {"nombre": nombre}
        if telefono:
            payload["telefono"] = telefono

        result = db.table("clientes").insert(payload).execute()

        if result.data:
            logger.info(
                "cliente_registrado_via_agente",
                nombre=nombre,
                telefono=telefono,
            )
            return (
                f"✅ Cliente registrado:\n"
                f"• Nombre: {nombre}\n"
                f"• Teléfono: {telefono or 'No proporcionado'}"
            )

        return "❌ No se pudo registrar el cliente."

    except Exception as exc:
        logger.error("tool_registrar_cliente_failed", error=str(exc))
        return f"❌ Error al registrar cliente: {str(exc)}"
