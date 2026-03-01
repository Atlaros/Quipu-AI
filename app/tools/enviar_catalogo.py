"""Tool: Enviar Catálogo de Productos.

Tool callable por el agente LangGraph para mostrar al cliente
el catálogo completo de productos disponibles con stock.
Usa ProductoRepository.buscar_catalogo() para acceso a datos.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client
from app.core.exceptions import DatabaseError
from app.repositories.producto_repository import ProductoRepository

logger = structlog.get_logger()


@tool
def enviar_catalogo(categoria: str = "") -> str:
    """Muestra el catálogo de productos disponibles con stock.

    Úsalo cuando el cliente pida ver qué hay disponible, pida el catálogo,
    o pregunte qué productos maneja la tienda.

    Args:
        categoria: Categoría a filtrar (ej: "zapatillas", "polo", "jean").
                   Vacío = mostrar todo el catálogo.

    Returns:
        Catálogo formateado con productos disponibles y precios.
    """
    db = get_supabase_client()
    producto_repo = ProductoRepository(db)

    try:
        productos = producto_repo.buscar_catalogo(categoria, limit=15)

        if not productos:
            msg = (
                f"No tenemos productos en la categoría '{categoria}'."
                if categoria
                else "El catálogo está vacío."
            )
            return f"❌ {msg}"

        # Filtrar solo productos con stock
        disponibles = []
        for prod in productos:
            inv = prod.get("inventario")
            if isinstance(inv, list) and inv:
                inv = inv[0]
            stock = inv.get("cantidad_actual", 0) if isinstance(inv, dict) else 0
            if stock > 0:
                disponibles.append((prod, stock))

        if not disponibles:
            return "❌ Todos los productos están sin stock por el momento."

        titulo = f"📋 **Catálogo{'— ' + categoria if categoria else ''}:**"
        lines = [titulo, ""]

        for prod, stock in disponibles:
            detalles = []
            if prod.get("talla"):
                detalles.append(f"T{prod['talla']}")
            if prod.get("color"):
                detalles.append(prod["color"])
            variante = f" ({', '.join(detalles)})" if detalles else ""
            marca = f" [{prod['marca']}]" if prod.get("marca") else ""
            precio = float(prod.get("precio_unitario", 0))

            lines.append(f"👟 **{prod['nombre']}{variante}**{marca}")
            lines.append(f"   💰 S/{precio:.2f} | 📦 {stock} disponibles")

        lines.append("\n¿Te interesa alguno? Dime talla y color 😊")

        logger.info(
            "catalogo_enviado",
            num_productos=len(disponibles),
            categoria=categoria,
        )
        return "\n".join(lines)

    except DatabaseError as exc:
        logger.error("tool_enviar_catalogo_db_error", error=str(exc))
        return f"❌ Error de base de datos: {exc.message}"
    except Exception as exc:
        logger.error("tool_enviar_catalogo_failed", error=str(exc))
        return f"❌ Error al cargar el catálogo: {exc!s}"
