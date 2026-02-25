"""Tool: Exportar Reporte a CSV.

Tool callable por el agente LangGraph para exportar el historial
de ventas en formato CSV descargable.
"""

import csv
import tempfile
from datetime import date, timedelta

import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client

logger = structlog.get_logger()


@tool
def exportar_reporte(periodo: str = "semana") -> str:
    """Exporta el historial de ventas a un archivo CSV.

    Genera un reporte descargable con todas las ventas del período
    especificado, incluyendo producto, cliente, cantidad y monto.

    Args:
        periodo: Período del reporte. Valores: "semana", "mes", "todo".

    Returns:
        La ruta del archivo CSV generado y su contenido en texto.
    """
    db = get_supabase_client()

    try:
        today = date.today()
        if periodo == "semana":
            desde = today - timedelta(days=7)
        elif periodo == "mes":
            desde = today.replace(day=1)
        else:  # "todo"
            desde = date(2020, 1, 1)

        result = db.table("transacciones").select(
            "created_at, descripcion, cantidad, precio_unitario, monto_total"
        ).gte("created_at", desde.isoformat()).order("created_at", desc=True).execute()

        if not result.data:
            return f"📊 No hay ventas en el período '{periodo}'."

        # Generar CSV en directorio temporal
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix=f"ventas_{periodo}_",
            delete=False,
            encoding="utf-8",
            newline="",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Fecha", "Descripción", "Cantidad", "Precio Unitario", "Total"],
            )
            writer.writeheader()

            total_acumulado = 0.0
            for row in result.data:
                fecha = row.get("created_at", "")[:10]
                monto = float(row.get("monto_total", 0))
                total_acumulado += monto
                writer.writerow({
                    "Fecha": fecha,
                    "Descripción": row.get("descripcion", ""),
                    "Cantidad": row.get("cantidad", 1),
                    "Precio Unitario": f"S/{float(row.get('precio_unitario', 0)):.2f}",
                    "Total": f"S/{monto:.2f}",
                })

            csv_path = f.name

        logger.info("reporte_exportado", path=csv_path, ventas=len(result.data), total=total_acumulado)

        return (
            f"📊 **Reporte '{periodo}' generado:**\n"
            f"• {len(result.data)} transacciones\n"
            f"• Total: S/{total_acumulado:.2f}\n"
            f"• Archivo: `{csv_path}`\n\n"
            f"💡 El archivo CSV está listo en el servidor. "
            f"Puedes descargarlo desde la API: GET /api/v1/ventas/export"
        )

    except Exception as exc:
        logger.error("tool_exportar_reporte_failed", error=str(exc))
        return f"❌ Error al exportar reporte: {str(exc)}"
