"""Tool: Registrar Deuda de Cliente.

Tool callable por el agente LangGraph para registrar cuando
un cliente se lleva mercadería a crédito o debe dinero.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client

logger = structlog.get_logger()


@tool
def registrar_deuda(
    cliente_nombre: str,
    descripcion: str,
    monto: float,
    cliente_phone: str = "",
    fecha_vencimiento: str = "",
) -> str:
    """Registra una deuda o crédito pendiente de un cliente.

    Úsalo cuando el cliente se lleva productos a crédito, queda de
    pagar después, o debe dinero de una compra anterior.

    Args:
        cliente_nombre: Nombre del cliente deudor.
        descripcion: Qué debe (ej: "2x Nike Air Force T42 negras").
        monto: Monto adeudado en soles (S/).
        cliente_phone: Número de teléfono del cliente (opcional).
        fecha_vencimiento: Fecha límite de pago en formato YYYY-MM-DD (opcional).

    Returns:
        Confirmación del registro de la deuda.
    """
    db = get_supabase_client()

    try:
        payload: dict = {
            "cliente_nombre": cliente_nombre.strip(),
            "descripcion": descripcion.strip(),
            "monto": monto,
            "pagado": False,
        }

        if cliente_phone:
            payload["cliente_phone"] = cliente_phone.strip()
        if fecha_vencimiento:
            payload["fecha_vencimiento"] = fecha_vencimiento

        db.table("deudas").insert(payload).execute()

        vencimiento_str = f"\n• Vence: {fecha_vencimiento}" if fecha_vencimiento else ""
        logger.info(
            "deuda_registrada",
            cliente=cliente_nombre,
            monto=monto,
        )

        return (
            f"✅ Deuda registrada:\n"
            f"• Cliente: {cliente_nombre}\n"
            f"• Descripción: {descripcion}\n"
            f"• Monto: S/{monto:.2f}{vencimiento_str}\n"
            f"💡 Recuérdale cuando veas al cliente."
        )

    except Exception as exc:
        logger.error("tool_registrar_deuda_failed", error=str(exc))
        return f"❌ Error al registrar deuda: {str(exc)}"
