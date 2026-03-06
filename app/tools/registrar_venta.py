"""Tool: Registrar Venta.

Tool callable por el agente LangGraph para registrar una venta
en Supabase. Usa repositorios en vez de queries directas.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client, sanitize_postgrest_value
from app.core.exceptions import DatabaseError

logger = structlog.get_logger()


@tool
def registrar_venta(
    producto_nombre: str,
    cantidad: int,
    talla: str = "",
    color: str = "",
    cliente_nombre: str = "",
) -> str:
    """Registra una venta de ropa/calzado.

    Args:
        producto_nombre: Nombre del producto (ej: "Nike Air").
        cantidad: Cantidad de unidades.
        talla: Talla del producto (ej: "42", "M").
        color: Color del producto (ej: "Rojo").
        cliente_nombre: Nombre del cliente (opcional).

    Returns:
        Mensaje de confirmación.
    """
    db = get_supabase_client()

    try:
        # 1. Buscar producto con variantes (via repository)
        query = db.table("productos").select("id, nombre, precio_unitario, talla, color")
        safe_name = sanitize_postgrest_value(producto_nombre)
        query = query.or_(f"nombre.ilike.%{safe_name}%,marca.ilike.%{safe_name}%")

        if talla:
            query = query.eq("talla", talla)
        if color:
            query = query.ilike("color", color)

        productos = query.limit(1).execute()

        if not productos.data:
            msg = f"❌ No encontré el producto '{producto_nombre}'"
            if talla:
                msg += f" talla '{talla}'"
            if color:
                msg += f" color '{color}'"
            return msg + " en el catálogo."

        producto = productos.data[0]
        precio = float(producto["precio_unitario"])
        monto_total = precio * cantidad

        # 2. Buscar cliente (opcional)
        cliente_id = None
        cliente_info = "venta anónima"
        if cliente_nombre:
            cli_result = (
                db.table("clientes")
                .select("id, nombre")
                .ilike("nombre", f"%{cliente_nombre}%")
                .limit(1)
                .execute()
            )
            if cli_result.data:
                cliente_id = cli_result.data[0]["id"]
                cliente_info = cli_result.data[0]["nombre"]

        # 3. Insertar transacción
        desc_variant = (
            f" ({producto['talla']}, {producto['color']})" if producto.get("talla") else ""
        )

        payload = {
            "producto_id": producto["id"],
            "cliente_id": cliente_id,
            "tipo": "venta",
            "cantidad": cantidad,
            "precio_unitario": producto["precio_unitario"],
            "monto_total": str(monto_total),
            "descripcion": (
                f"Venta: {producto['nombre']}{desc_variant} x{cantidad} a {cliente_info}"
            ),
        }

        db.table("transacciones").insert(payload).execute()

        logger.info(
            "venta_registrada",
            producto=producto["nombre"],
            talla=producto.get("talla"),
            color=producto.get("color"),
            total=monto_total,
        )

        return (
            f"✅ Venta registrada:\n"
            f"• Producto: {producto['nombre']}{desc_variant}\n"
            f"• Cantidad: {cantidad}\n"
            f"• Total: S/{monto_total:.2f}\n"
            f"• Cliente: {cliente_info}"
        )

    except DatabaseError as exc:
        logger.error("tool_registrar_venta_db_error", error=str(exc))
        return f"❌ Error de base de datos: {exc.message}"
    except Exception as exc:
        logger.error("tool_registrar_venta_failed", error=str(exc))
        return f"❌ Error al registrar venta: {exc!s}"
