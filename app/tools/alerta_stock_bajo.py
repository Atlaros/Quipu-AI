"""Tool: Alerta de Stock Bajo.

Tool callable por el agente LangGraph para identificar productos
con inventario crítico (por debajo del mínimo configurado).
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client

logger = structlog.get_logger()


@tool
def alerta_stock_bajo() -> str:
    """Revisa el inventario y alerta sobre productos con stock bajo o agotado.

    Escanea todos los productos y retorna aquellos cuya cantidad actual
    es menor o igual a la cantidad mínima configurada.

    Returns:
        Lista de productos con stock crítico o mensaje indicando que
        todo está en orden.
    """
    db = get_supabase_client()

    try:
        result = db.table("productos").select(
            "nombre, marca, talla, color, precio_unitario, "
            "inventario(cantidad_actual, cantidad_minima)"
        ).execute()

        if not result.data:
            return "📦 No hay productos registrados en el inventario."

        criticos = []
        for prod in result.data:
            inv = prod.get("inventario")

            # Normalizar inventario (puede ser dict o lista)
            if isinstance(inv, list) and inv:
                inv = inv[0]

            if not isinstance(inv, dict):
                continue

            actual = inv.get("cantidad_actual", 0)
            minimo = inv.get("cantidad_minima", 0)

            if actual <= minimo:
                detalles = []
                if prod.get("talla"):
                    detalles.append(f"T{prod['talla']}")
                if prod.get("color"):
                    detalles.append(prod["color"])
                variante = f" ({', '.join(detalles)})" if detalles else ""
                marca = prod.get("marca", "")
                marca_str = f" [{marca}]" if marca else ""
                estado = "🔴 AGOTADO" if actual == 0 else "⚠️ BAJO"

                criticos.append(
                    f"{estado} {prod['nombre']}{variante}{marca_str}: "
                    f"{actual} und. (mín: {minimo})"
                )

        if not criticos:
            return "✅ Todo el inventario está en niveles normales. ¡Bien abastecido!"

        lines = [f"🚨 **{len(criticos)} producto(s) con stock crítico:**"]
        lines.extend(f"• {item}" for item in criticos)
        lines.append("\n💡 Considera reponer stock urgentemente.")

        logger.info("alerta_stock_bajo", num_criticos=len(criticos))
        return "\n".join(lines)

    except Exception as exc:
        logger.error("tool_alerta_stock_bajo_failed", error=str(exc))
        return f"❌ Error al revisar inventario: {str(exc)}"
