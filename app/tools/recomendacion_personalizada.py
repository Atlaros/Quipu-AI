"""Tool: Recomendación Personalizada.

Tool callable por el agente LangGraph para sugerir productos
basándose en el historial de compras del cliente.
Usa repositorios para acceso a datos.
"""

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client
from app.core.exceptions import DatabaseError

logger = structlog.get_logger()


@tool
def recomendacion_personalizada(cliente_phone: str) -> str:
    """Genera recomendaciones de productos basadas en el historial del cliente.

    Analiza las últimas compras del cliente y sugiere productos
    similares que están disponibles en stock.

    Args:
        cliente_phone: Número de teléfono del cliente (con código de país, ej: "51987654321").

    Returns:
        Lista de productos recomendados basados en el historial de compras.
    """
    db = get_supabase_client()

    try:
        # 1. Buscar cliente por teléfono
        cliente_result = (
            db.table("clientes")
            .select("id, nombre")
            .eq("telefono", cliente_phone)
            .limit(1)
            .execute()
        )

        if not cliente_result.data:
            return "❌ No encontré historial de compras para este cliente."

        cliente = cliente_result.data[0]
        cliente_id = cliente["id"]
        cliente_nombre = cliente.get("nombre", "el cliente")

        # 2. Obtener últimas 5 compras del cliente
        compras = (
            db.table("transacciones")
            .select("producto_id, precio_unitario, descripcion")
            .eq("cliente_id", cliente_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )

        if not compras.data:
            return f"❌ {cliente_nombre} no tiene compras registradas aún."

        # 3. Calcular rango de precios para recomendaciones
        precios = [
            float(c.get("precio_unitario", 0)) for c in compras.data if c.get("precio_unitario")
        ]
        precio_promedio = sum(precios) / len(precios) if precios else 0
        precio_min = precio_promedio * 0.7
        precio_max = precio_promedio * 1.4

        # 4. Buscar productos similares con stock en ese rango de precio
        productos_ids_comprados = [c["producto_id"] for c in compras.data if c.get("producto_id")]

        sugerencias = (
            db.table("productos")
            .select("id, nombre, marca, talla, color, precio_unitario, inventario(cantidad_actual)")
            .gte("precio_unitario", precio_min)
            .lte("precio_unitario", precio_max)
            .limit(8)
            .execute()
        )

        # Filtrar: con stock, no comprados antes
        recomendados = []
        for prod in sugerencias.data:
            if prod.get("id") in productos_ids_comprados:
                continue

            inv = prod.get("inventario")
            if isinstance(inv, list) and inv:
                inv = inv[0]
            stock = inv.get("cantidad_actual", 0) if isinstance(inv, dict) else 0

            if stock > 0:
                recomendados.append(prod)

        if not recomendados:
            return (
                f"📊 {cliente_nombre} ha comprado {len(compras.data)} veces.\n"
                f"No encontré productos nuevos para recomendar en este momento."
            )

        lines = [
            f"✨ **Recomendaciones para {cliente_nombre}**",
            f"_(basado en {len(compras.data)} compras anteriores)_\n",
        ]

        for prod in recomendados[:5]:
            detalles = []
            if prod.get("talla"):
                detalles.append(f"T{prod['talla']}")
            if prod.get("color"):
                detalles.append(prod["color"])
            variante = f" ({', '.join(detalles)})" if detalles else ""
            marca = f" [{prod['marca']}]" if prod.get("marca") else ""
            precio = float(prod.get("precio_unitario", 0))

            lines.append(f"⭐ **{prod['nombre']}{variante}**{marca} — S/{precio:.2f}")

        lines.append("\n💡 ¿Le cuento al cliente sobre alguno de estos?")

        logger.info(
            "recomendacion_generada",
            cliente_phone=cliente_phone,
            num_recomendaciones=len(recomendados),
        )
        return "\n".join(lines)

    except DatabaseError as exc:
        logger.error("tool_recomendacion_db_error", error=str(exc))
        return f"❌ Error de base de datos: {exc.message}"
    except Exception as exc:
        logger.error("tool_recomendacion_personalizada_failed", error=str(exc))
        return f"❌ Error al generar recomendación: {exc!s}"
