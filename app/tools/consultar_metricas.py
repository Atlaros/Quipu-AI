"""Tool: Consultar Métricas de Ventas.

Tool callable por el agente para obtener métricas de ventas
en un periodo determinado (hoy, semana, mes).
Usa VentaRepository.get_por_rango() para acceso a datos.
"""

from datetime import UTC, datetime, timedelta

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client
from app.core.exceptions import DatabaseError
from app.repositories.venta_repository import VentaRepository

logger = structlog.get_logger()


def _get_date_range(periodo: str) -> tuple[str, str]:
    """Calcula rango de fechas según el periodo solicitado.

    Args:
        periodo: "hoy", "semana", o "mes".

    Returns:
        Tupla (fecha_inicio, fecha_fin) en formato ISO.
    """
    now = datetime.now(tz=UTC)
    end = now.isoformat()

    if periodo == "semana":
        start = (now - timedelta(days=7)).isoformat()
    elif periodo == "mes":
        start = (now - timedelta(days=30)).isoformat()
    else:  # "hoy" por defecto
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    return start, end


@tool
def consultar_metricas(periodo: str = "hoy") -> str:
    """Consulta métricas de ventas de la bodega en un periodo.

    Retorna un resumen con: total de ventas, monto facturado,
    productos más vendidos, y clientes únicos.

    Args:
        periodo: Periodo a consultar. Opciones: "hoy", "semana", "mes".

    Returns:
        Mensaje con el resumen de métricas de ventas.
    """
    db = get_supabase_client()
    venta_repo = VentaRepository(db)

    try:
        start, end = _get_date_range(periodo)
        ventas = venta_repo.get_por_rango(start, end)

        if not ventas:
            periodo_label = {
                "hoy": "hoy",
                "semana": "esta semana",
                "mes": "este mes",
            }
            return f"📊 No hay ventas registradas {periodo_label.get(periodo, periodo)}."

        # Calcular métricas
        total_ventas = len(ventas)
        monto_total = sum(float(v.get("monto_total", 0)) for v in ventas)

        # Top productos
        producto_count: dict[str, int] = {}
        clientes_unicos: set[str] = set()

        for v in ventas:
            prod = v.get("productos")
            if isinstance(prod, dict):
                nombre = prod.get("nombre", "Desconocido")
            elif isinstance(prod, list) and prod:
                nombre = prod[0].get("nombre", "Desconocido")
            else:
                nombre = "Desconocido"

            producto_count[nombre] = producto_count.get(nombre, 0) + v.get("cantidad", 1)

            cliente = v.get("clientes")
            if isinstance(cliente, dict) and cliente.get("nombre"):
                clientes_unicos.add(cliente["nombre"])
            elif isinstance(cliente, list) and cliente and cliente[0].get("nombre"):
                clientes_unicos.add(cliente[0]["nombre"])

        # Top 3 productos
        top_productos = sorted(producto_count.items(), key=lambda x: x[1], reverse=True)[:3]

        periodo_label = {
            "hoy": "📅 Hoy",
            "semana": "📅 Esta semana",
            "mes": "📅 Este mes",
        }

        lines = [
            f"📊 **Métricas {periodo_label.get(periodo, periodo)}:**",
            f"• Ventas totales: {total_ventas}",
            f"• Facturado: S/{monto_total:.2f}",
            f"• Clientes únicos: {len(clientes_unicos)}",
            "",
            "🏆 **Top productos:**",
        ]

        for i, (nombre, qty) in enumerate(top_productos, 1):
            lines.append(f"  {i}. {nombre}: {qty} unidades")

        logger.info(
            "metricas_consultadas",
            periodo=periodo,
            total_ventas=total_ventas,
            monto=monto_total,
        )

        return "\n".join(lines)

    except DatabaseError as exc:
        logger.error("tool_consultar_metricas_db_error", error=str(exc))
        return f"❌ Error de base de datos: {exc.message}"
    except Exception as exc:
        logger.error("tool_consultar_metricas_failed", error=str(exc))
        return f"❌ Error al consultar métricas: {exc!s}"
