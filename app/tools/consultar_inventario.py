"""Tool: Consultar Inventario.

Tool callable por el agente LangGraph para verificar el stock
de uno o todos los productos en la bodega.
Usa ProductoRepository para acceso a datos.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client, sanitize_postgrest_value
from app.core.exceptions import DatabaseError

logger = structlog.get_logger()


def _extraer_stock(inv: dict | list | None) -> tuple[int, int] | None:
    """Extrae cantidad_actual y cantidad_minima del dato de inventario.

    Supabase puede retornar inventario como dict (relación 1-a-1)
    o como lista (relación 1-a-muchos). Esta función normaliza ambos.

    Args:
        inv: Dato de inventario de Supabase (dict, list, o None).

    Returns:
        Tupla (cantidad_actual, cantidad_minima) o None si no hay datos.
    """
    if inv is None:
        return None

    # Relación 1-a-1: Supabase retorna dict directamente
    if isinstance(inv, dict):
        return inv.get("cantidad_actual", 0), inv.get("cantidad_minima", 0)

    # Relación 1-a-muchos: Supabase retorna lista
    if isinstance(inv, list) and len(inv) > 0:
        return inv[0].get("cantidad_actual", 0), inv[0].get("cantidad_minima", 0)

    return None


@tool
def consultar_inventario(
    producto_nombre: str = "",
    talla: str = "",
    color: str = "",
) -> str:
    """Consulta el inventario de la tienda de ropa/calzado.

    Permite filtrar por nombre, talla y color.

    Args:
        producto_nombre: Nombre o marca del producto (ej: "Nike Air", "Polo").
        talla: Talla a buscar (ej: "42", "M").
        color: Color a buscar (ej: "Rojo", "Negro").

    Returns:
        Lista de productos encontrados con su stock y detalles.
    """
    db = get_supabase_client()

    try:
        query = db.table("productos").select(
            "nombre, marca, talla, color, precio_unitario, "
            "inventario(cantidad_actual, cantidad_minima)"
        )

        # Filtros dinámicos
        if producto_nombre:
            safe_name = sanitize_postgrest_value(producto_nombre)
            query = query.or_(f"nombre.ilike.%{safe_name}%,marca.ilike.%{safe_name}%")

        if talla:
            query = query.eq("talla", talla)
        if color:
            query = query.ilike("color", color)

        result = query.limit(10).execute()

        if not result.data:
            msg = "❌ No encontré productos"
            if producto_nombre:
                msg += f" con nombre '{producto_nombre}'"
            if talla:
                msg += f" talla '{talla}'"
            if color:
                msg += f" color '{color}'"
            return msg + "."

        lines = ["📦 **Inventario Disponible:**"]
        for prod in result.data:
            stock_data = _extraer_stock(prod.get("inventario"))
            stock = 0
            minimo = 0

            if stock_data:
                stock, minimo = stock_data

            detalles = []
            if prod.get("talla"):
                detalles.append(f"Talla {prod['talla']}")
            if prod.get("color"):
                detalles.append(prod["color"])
            info_extra = ", ".join(detalles)

            marca = prod.get("marca", "Generico")
            nombre_completo = f"{prod['nombre']} ({info_extra})" if info_extra else prod["nombre"]

            precio = prod.get("precio_unitario", 0)
            alerta = " ⚠️ STOCK BAJO" if stock <= minimo else ""

            lines.append(f"• {nombre_completo} [{marca}]: {stock} und. (S/{precio:.2f}){alerta}")

        return "\n".join(lines)

    except DatabaseError as exc:
        logger.error("tool_consultar_inventario_db_error", error=str(exc))
        return f"❌ Error de base de datos: {exc.message}"
    except Exception as exc:
        logger.error("tool_consultar_inventario_failed", error=str(exc))
        if "column" in str(exc) and "does not exist" in str(exc):
            return "❌ Error de config: La base de datos no tiene las columnas de talla/color aún."
        return f"❌ Error al consultar: {exc!s}"
