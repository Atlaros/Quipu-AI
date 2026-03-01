"""Tool: Enviar Catálogo de Productos.

Tool callable por el agente LangGraph para mostrar al cliente
el catálogo completo de productos disponibles con stock.
Agrupa por categoría y muestra detalles de variantes.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client
from app.core.exceptions import DatabaseError
from app.repositories.producto_repository import ProductoRepository

logger = structlog.get_logger()

# Emojis por categoría para un catálogo visualmente atractivo
CATEGORIA_EMOJI: dict[str, str] = {
    "calzado": "👟",
    "zapatillas": "👟",
    "zapatos": "👟",
    "ropa": "👕",
    "polos": "👕",
    "camisas": "👔",
    "jeans": "👖",
    "pantalones": "👖",
    "casacas": "🧥",
    "chaquetas": "🧥",
    "accesorios": "🎒",
    "general": "🏷️",
}


def _emoji_para(categoria: str) -> str:
    """Retorna el emoji apropiado para la categoría."""
    cat_lower = categoria.lower().strip()
    return CATEGORIA_EMOJI.get(cat_lower, "🏷️")


@tool
def enviar_catalogo(categoria: str = "") -> str:
    """Muestra el catálogo de productos disponibles con stock.

    Úsalo cuando el cliente pida ver qué hay disponible, pida el catálogo,
    o pregunte qué productos maneja la tienda.

    Args:
        categoria: Categoría a filtrar (ej: "calzado", "ropa", "jeans").
                   Vacío = mostrar todo el catálogo.

    Returns:
        Catálogo formateado agrupado por categoría con precios y stock.
    """
    db = get_supabase_client()
    producto_repo = ProductoRepository(db)

    try:
        productos = producto_repo.buscar_catalogo(categoria, limit=20)

        if not productos:
            msg = (
                f"No tenemos productos en la categoría '{categoria}'."
                if categoria
                else "El catálogo está vacío."
            )
            return f"❌ {msg}"

        # Filtrar solo con stock y agrupar por categoría
        por_categoria: dict[str, list[tuple[dict, int]]] = {}
        for prod in productos:
            inv = prod.get("inventario")
            if isinstance(inv, list) and inv:
                inv = inv[0]
            stock = inv.get("cantidad_actual", 0) if isinstance(inv, dict) else 0
            if stock <= 0:
                continue

            cat = prod.get("categoria", "General") or "General"
            if cat not in por_categoria:
                por_categoria[cat] = []
            por_categoria[cat].append((prod, stock))

        if not por_categoria:
            return "❌ Todos los productos están sin stock por el momento."

        # Construir catálogo agrupado
        total_productos = sum(len(items) for items in por_categoria.values())
        lines = [f"🛍️ **Catálogo Disponible** ({total_productos} productos):", ""]

        for cat, items in por_categoria.items():
            emoji = _emoji_para(cat)
            lines.append(f"{emoji} **{cat.upper()}**:")

            for prod, stock in items:
                nombre = prod["nombre"]
                detalles = []
                if prod.get("talla"):
                    detalles.append(f"T{prod['talla']}")
                if prod.get("color"):
                    detalles.append(prod["color"])
                variante = f" ({', '.join(detalles)})" if detalles else ""
                marca = f" *{prod['marca']}*" if prod.get("marca") else ""
                precio = float(prod.get("precio_unitario", 0))

                alerta = " ⚠️" if stock <= 5 else ""
                lines.append(
                    f"  • {nombre}{variante}{marca} — S/{precio:.2f} | {stock} und.{alerta}"
                )

            lines.append("")  # Línea vacía entre categorías

        lines.append("¿Te interesa alguno? Dime cuál y tu talla 😊")

        logger.info(
            "catalogo_enviado",
            num_productos=total_productos,
            categorias=list(por_categoria.keys()),
        )
        return "\n".join(lines)

    except DatabaseError as exc:
        logger.error("tool_enviar_catalogo_db_error", error=str(exc))
        return f"❌ Error de base de datos: {exc.message}"
    except Exception as exc:
        logger.error("tool_enviar_catalogo_failed", error=str(exc))
        return f"❌ Error al cargar el catálogo: {exc!s}"
