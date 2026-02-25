"""Tool: Calculadora de Descuentos.

Tool callable por el agente LangGraph para calcular precios
con descuento aplicado, útil para ofertas especiales o
negociaciones con clientes.
"""

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()


@tool
def calcular_descuento(
    precio_original: float,
    descuento_porcentaje: float,
    cantidad: int = 1,
) -> str:
    """Calcula el precio final aplicando un descuento porcentual.

    Útil para calcular precios de oferta, negociaciones con clientes
    o promociones por volumen.

    Args:
        precio_original: Precio base del producto en soles (S/).
        descuento_porcentaje: Porcentaje de descuento a aplicar (ej: 20 para 20%).
        cantidad: Número de unidades (default: 1).

    Returns:
        Desglose del precio con descuento aplicado.
    """
    if precio_original <= 0:
        return "❌ El precio debe ser mayor a 0."

    if not 0 < descuento_porcentaje <= 100:
        return "❌ El descuento debe estar entre 1% y 100%."

    precio_descuento = precio_original * (1 - descuento_porcentaje / 100)
    ahorro_unitario = precio_original - precio_descuento
    total_sin_desc = precio_original * cantidad
    total_con_desc = precio_descuento * cantidad
    ahorro_total = ahorro_unitario * cantidad

    resultado = (
        f"🏷️ **Cálculo de descuento:**\n"
        f"• Precio original: S/{precio_original:.2f}\n"
        f"• Descuento: {descuento_porcentaje:.0f}% → -S/{ahorro_unitario:.2f}\n"
        f"• **Precio final: S/{precio_descuento:.2f}** por unidad"
    )

    if cantidad > 1:
        resultado += (
            f"\n\n📦 **Para {cantidad} unidades:**\n"
            f"• Total sin descuento: S/{total_sin_desc:.2f}\n"
            f"• **Total con descuento: S/{total_con_desc:.2f}**\n"
            f"• Ahorro total: S/{ahorro_total:.2f} 💰"
        )
    else:
        resultado += f"\n• Ahorras: S/{ahorro_unitario:.2f} 💰"

    logger.info(
        "descuento_calculado",
        precio=precio_original,
        descuento=descuento_porcentaje,
        precio_final=precio_descuento,
    )
    return resultado
