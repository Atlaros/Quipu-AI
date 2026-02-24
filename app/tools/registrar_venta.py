"""Tool: Registrar Venta.

Tool callable por el agente LangGraph para registrar una venta
en Supabase. Busca producto por nombre y cliente por nombre/teléfono.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client
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
        # 1. Buscar producto con variantes
        query = db.table("productos").select("id, nombre, precio_unitario, talla, color")
        # Buscamos por nombre O marca
        query = query.or_(f"nombre.ilike.%{producto_nombre}%,marca.ilike.%{producto_nombre}%")
        
        if talla:
            query = query.eq("talla", talla)
        if color:
            query = query.ilike("color", color)
            
        productos = query.limit(1).execute()

        if not productos.data:
            msg = f"❌ No encontré el producto '{producto_nombre}'"
            if talla: msg += f" talla '{talla}'"
            if color: msg += f" color '{color}'"
            return msg + " en el catálogo."

        producto = productos.data[0]
        
        # Validación extra: si no pidieron talla pero el producto tiene variantes
        # Esto es complejo de manejar aquí simple, asumimos que el agente ya preguntó.
        
        precio = float(producto["precio_unitario"])
        monto_total = precio * cantidad

        # 2. Buscar cliente (opcional)
        cliente_id = None
        cliente_info = "venta anónima"
        if cliente_nombre:
            clientes = (
                db.table("clientes")
                .select("id, nombre")
                .ilike("nombre", f"%{cliente_nombre}%")
                .limit(1)
                .execute()
            )
            if clientes.data:
                cliente_id = clientes.data[0]["id"]
                cliente_info = clientes.data[0]["nombre"]

        # 3. Insertar transacción
        # Descripción incluye variantes
        desc_variant = f" ({producto['talla']}, {producto['color']})" if producto.get('talla') else ""
        
        payload = {
            "producto_id": producto["id"],
            "cliente_id": cliente_id,
            "tipo": "venta",
            "cantidad": cantidad,
            "precio_unitario": producto["precio_unitario"],
            "monto_total": str(monto_total),
            "descripcion": f"Venta: {producto['nombre']}{desc_variant} x{cantidad} a {cliente_info}",
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

    except Exception as exc:
        logger.error("tool_registrar_venta_failed", error=str(exc))
        if "column" in str(exc) and "does not exist" in str(exc):
             return "❌ Error: La base de datos no tiene columnas de talla/color."
        return f"❌ Error al registrar venta: {str(exc)}"
