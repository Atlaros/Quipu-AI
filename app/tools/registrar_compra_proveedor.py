"""Tool: Registrar Compra al Proveedor.

Tool callable por el agente LangGraph para registrar ingreso de
nueva mercadería (abastecimiento). Si el producto existe, suma stock;
si no existe, lo crea.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client

logger = structlog.get_logger()


@tool
def registrar_compra_proveedor(
    nombre: str,
    cantidad: int,
    precio_venta: float,
    precio_costo: float = 0.0,
    talla: str = "",
    color: str = "",
    marca: str = "",
    categoria: str = "",
) -> str:
    """Registra la compra de mercadería para abastecer la tienda.

    Si el producto ya existe (mismo nombre, talla y color), le suma el stock al
    inventario actual y actualiza su precio.
    Si el producto no existe, lo crea en el catálogo con el stock inicial indicado.

    Args:
        nombre: Nombre del producto (ej: "Polera Nike", "Zapatillas Samba").
        cantidad: Unidades ingresadas (ej: 10).
        precio_venta: Precio al que se venderá al público (S/).
        precio_costo: Precio de costo comprado al proveedor (S/) (opcional).
        talla: Talla del producto (ej: "42", "M") (opcional).
        color: Color del producto (ej: "Blanco", "Negro") (opcional).
        marca: Marca del producto (ej: "Nike") (opcional).
        categoria: Categoría general (ej: "Calzado", "Ropa") (opcional).

    Returns:
        Confirmación de creación o actualización del inventario.
    """
    db = get_supabase_client()

    try:
        # Validación básica
        if tuple(x.lower() for x in (nombre, talla, color)) == ("abarrotes", "", ""):
             return "❌ No ingreses más abarrotes, solo ropa o calzado."
        if cantidad <= 0:
            return "❌ La cantidad ingresada debe ser mayor a 0."
        if precio_venta <= 0:
            return "❌ El precio de venta debe ser mayor a 0."

        # 1. Buscar si el producto ya existe
        query = db.table("productos").select("id").eq("nombre", nombre)
        if talla:
            query = query.eq("talla", talla)
        if color:
            query = query.eq("color", color)

        result_prod = query.execute()

        variante_str = f"T{talla} " if talla else ""
        variante_str += color if color else ""
        if variante_str:
            variante_str = f"({variante_str.strip()})"

        if result_prod.data:
            # EL PRODUCTO EXISTE -> SUMAR STOCK
            producto_id = result_prod.data[0]["id"]

            # Actualizar precios
            db.table("productos").update({
                "precio_unitario": precio_venta,
            }).eq("id", producto_id).execute()

            # Obtener inventario actual
            inv_result = db.table("inventario").select("id, cantidad_actual").eq("producto_id", producto_id).execute()

            if inv_result.data:
                inv_id = inv_result.data[0]["id"]
                stock_actual = int(inv_result.data[0]["cantidad_actual"])
                nuevo_stock = stock_actual + cantidad

                # Actualizar stock
                db.table("inventario").update({
                    "cantidad_actual": nuevo_stock
                }).eq("id", inv_id).execute()

                logger.info("stock_aumentado", producto_id=producto_id, sumado=cantidad, nuevo_stock=nuevo_stock)
                return (
                    f"✅ **Stock actualizado (Ya existía):**\n"
                    f"• Producto: {nombre} {variante_str}\n"
                    f"• Agregados: +{cantidad} und.\n"
                    f"• Stock Total Ahora: {nuevo_stock} und.\n"
                    f"• Nuevo Precio Venta: S/{precio_venta:.2f}"
                )
            else:
                # Caso raro: el producto existe pero no tiene registro de inventario, lo creamos
                db.table("inventario").insert({
                    "producto_id": producto_id,
                    "cantidad_actual": cantidad,
                    "cantidad_minima": 2
                }).execute()
                return f"✅ **Inventario creado para producto existente:** {nombre} {variante_str} (+{cantidad} und.)"

        else:
            # EL PRODUCTO NO EXISTE -> CREARLO
            nuevo_prod = {
                "nombre": nombre,
                "descripcion": f"Ingresado por WhatsApp: {nombre} {variante_str}",
                "precio_unitario": precio_venta,
            }
            if marca:
                nuevo_prod["marca"] = marca
            if talla:
                nuevo_prod["talla"] = talla
            if color:
                nuevo_prod["color"] = color

            crear_result = db.table("productos").insert(nuevo_prod).execute()

            if not crear_result.data:
                 return "❌ Error al crear el nuevo producto en la base de datos."

            nuevo_id = crear_result.data[0]["id"]

            # Crear el inventario inicial
            db.table("inventario").insert({
                "producto_id": nuevo_id,
                "cantidad_actual": cantidad,
                "cantidad_minima": 2  # default razonable
            }).execute()

            # También registrar el costo si se proporcionó (opcional, como futura tabla de gastos)
            # Por ahora lo dejamos en logs
            logger.info("nuevo_producto_creado", producto_id=nuevo_id, costo=precio_costo)

            return (
                f"✨ **¡Producto NUEVO ingresado al catálogo!**\n"
                f"• Producto: {nombre} {variante_str}\n"
                f"• Marca: {marca if marca else '-'}\n"
                f"• Ingresados: {cantidad} und.\n"
                f"• Precio de Venta: S/{precio_venta:.2f}"
            )

    except Exception as exc:
        logger.error("tool_registrar_compra_proveedor_failed", error=str(exc))
        return f"❌ Error al registrar compra: {str(exc)}"
