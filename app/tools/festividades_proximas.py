"""Tool: Festividades Próximas.

Tool callable por el agente LangGraph para identificar fechas
especiales próximas en Perú y sugerir estrategias de venta.

No requiere API externa — usa un calendario hardcodeado.
"""

from datetime import date, timedelta

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()

# Festividades anuales de Perú con ideas de promoción para tienda de ropa/calzado
_FESTIVIDADES: list[dict] = [
    {
        "mes": 2,
        "dia": 14,
        "nombre": "Día de San Valentín",
        "emoji": "❤️",
        "promo": "Combos de pareja, ropa de colores rojo/rosado, descuentos en accesorios",
    },
    {
        "mes": 3,
        "dia": 8,
        "nombre": "Día de la Mujer",
        "emoji": "💜",
        "promo": "Descuentos especiales en moda femenina, accesorios y calzado de mujer",
    },
    {
        "mes": 5,
        "dia": 12,  # 2do domingo de mayo ~ aprox
        "nombre": "Día de la Madre",
        "emoji": "🌸",
        "promo": "Packs regalo para mamá, ropa femenina premium, zapatos elegantes",
    },
    {
        "mes": 6,
        "dia": 16,  # 3er domingo de junio ~ aprox
        "nombre": "Día del Padre",
        "emoji": "👔",
        "promo": "Ropa casual y formal para papá, zapatillas deportivas, descuentos en polos",
    },
    {
        "mes": 7,
        "dia": 28,
        "nombre": "Fiestas Patrias",
        "emoji": "🇵🇪",
        "promo": "Ropa en colores patrios (rojo y blanco), descuentos por semana de fiestas",
    },
    {
        "mes": 10,
        "dia": 31,
        "nombre": "Halloween",
        "emoji": "🎃",
        "promo": "Ropa oscura, disfraces casuales, accesorios temáticos",
    },
    {
        "mes": 11,
        "dia": 1,
        "nombre": "Día de Todos los Santos",
        "emoji": "🕯️",
        "promo": "Descuentos fin de semana largo, liquidación de temporada",
    },
    {
        "mes": 11,
        "dia": 15,  # aprox. Black Friday
        "nombre": "Black Friday",
        "emoji": "🖤",
        "promo": "Gran liquidación, hasta 50% de descuento, promociones especiales",
    },
    {
        "mes": 12,
        "dia": 25,
        "nombre": "Navidad",
        "emoji": "🎄",
        "promo": "Packs regalo, ropa de temporada, zapatillas premium como regalo",
    },
    {
        "mes": 12,
        "dia": 31,
        "nombre": "Año Nuevo",
        "emoji": "🎆",
        "promo": "Ropa de gala, outfits para la fiesta, colores dorado y plateado",
    },
    {
        "mes": 4,
        "dia": 1,  # aprox Semana Santa
        "nombre": "Semana Santa",
        "emoji": "✝️",
        "promo": "Liquidación de temporada, ropa casual para salidas y viajes",
    },
    {
        "mes": 6,
        "dia": 24,
        "nombre": "San Juan (Selva)",
        "emoji": "🌿",
        "promo": "Ropa regional, descuentos especiales para regiones amazónicas",
    },
]


def _get_fecha_festiva(mes: int, dia: int, hoy: date) -> date:
    """Devuelve la fecha de la festividad en el año actual o siguiente."""
    try:
        fecha = date(hoy.year, mes, dia)
    except ValueError:
        fecha = date(hoy.year, mes, 28)  # fallback para días inválidos

    if fecha < hoy:
        try:
            fecha = date(hoy.year + 1, mes, dia)
        except ValueError:
            fecha = date(hoy.year + 1, mes, 28)

    return fecha


@tool
def festividades_proximas(dias_anticipacion: int = 60) -> str:
    """Identifica festividades y fechas especiales próximas en Perú.

    Detecta las fechas importantes que se aproximan y sugiere
    estrategias de promoción para la tienda.

    Args:
        dias_anticipacion: Cuántos días hacia adelante buscar (default: 60).

    Returns:
        Lista de festividades próximas con ideas de promoción.
    """
    hoy = date.today()
    limite = hoy + timedelta(days=dias_anticipacion)

    proximas = []
    for fest in _FESTIVIDADES:
        fecha = _get_fecha_festiva(fest["mes"], fest["dia"], hoy)
        if hoy <= fecha <= limite:
            dias_restantes = (fecha - hoy).days
            proximas.append((dias_restantes, fecha, fest))

    # Ordenar por proximidad
    proximas.sort(key=lambda x: x[0])

    if not proximas:
        return (
            f"📅 No hay festividades destacadas en los próximos {dias_anticipacion} días.\n"
            f"Momento perfecto para preparar stock para las que vienen."
        )

    lines = [f"🗓️ **Festividades próximas (próximos {dias_anticipacion} días):**"]
    for dias_rest, fecha, fest in proximas:
        urgencia = (
            "🔥 ¡YA!" if dias_rest <= 7 else ("⚡ Pronto" if dias_rest <= 21 else "📌 En agenda")
        )
        lines.append(
            f"\n{fest['emoji']} **{fest['nombre']}** — {fecha.strftime('%d/%m/%Y')} "
            f"({dias_rest} días) {urgencia}\n"
            f"   💡 Idea: {fest['promo']}"
        )

    logger.info("festividades_proximas", num_festividades=len(proximas), dias=dias_anticipacion)
    return "\n".join(lines)
