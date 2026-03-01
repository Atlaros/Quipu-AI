"""Tool: Generar Reporte Visual de Ventas.

Genera un gráfico de barras con las ventas de los últimos 7 días.
Usa VentaRepository para acceso a datos.
"""

import tempfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import structlog
from langchain_core.tools import tool

from app.core.database import get_supabase_client
from app.core.exceptions import DatabaseError
from app.repositories.venta_repository import VentaRepository

# Backend no interactivo para servidores sin display
matplotlib.use("Agg")

logger = structlog.get_logger()


def _generar_chart_ventas(ventas_por_dia: dict[str, float], output_path: str) -> None:
    """Genera gráfico de barras de ventas por día.

    Args:
        ventas_por_dia: Dict con fecha(str) → monto total(float).
        output_path: Ruta donde guardar el PNG.
    """
    dias = list(ventas_por_dia.keys())
    montos = list(ventas_por_dia.values())

    # Formatear labels de fechas (solo día/mes)
    labels = []
    for d in dias:
        try:
            dt = datetime.fromisoformat(d)
            labels.append(dt.strftime("%d/%m"))
        except ValueError:
            labels.append(d)

    fig, ax = plt.subplots(figsize=(8, 4))

    bars = ax.bar(labels, montos, color="#4CAF50", edgecolor="#388E3C", width=0.6)

    # Agregar valores sobre las barras
    for bar, monto in zip(bars, montos, strict=True):
        if monto > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() + 0.5,
                f"S/{monto:.0f}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

    ax.set_title("📊 Ventas de los últimos 7 días", fontsize=14, fontweight="bold")
    ax.set_xlabel("Día")
    ax.set_ylabel("Monto (S/)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


@tool
def generar_reporte_ventas() -> str:
    """Genera un reporte visual con gráfico de barras de las ventas de los últimos 7 días.

    Crea un gráfico de barras mostrando el monto vendido por día,
    lo guarda como imagen y retorna la ruta para enviarlo por WhatsApp.

    Returns:
        Ruta del archivo de imagen generado, o mensaje de error.
    """
    db = get_supabase_client()
    venta_repo = VentaRepository(db)

    try:
        now = datetime.now(tz=UTC)
        start = (now - timedelta(days=7)).isoformat()
        end = now.isoformat()

        ventas = venta_repo.get_por_rango(start, end)

        # Agrupar por día
        ventas_por_dia: dict[str, float] = defaultdict(float)

        # Inicializar los 7 días (para que aparezcan días sin ventas)
        for i in range(7):
            dia = (now - timedelta(days=6 - i)).strftime("%Y-%m-%d")
            ventas_por_dia[dia] = 0.0

        for v in ventas:
            created = v.get("created_at", "")
            try:
                dia = datetime.fromisoformat(created).strftime("%Y-%m-%d")
                ventas_por_dia[dia] += float(v.get("monto_total", 0))
            except (ValueError, TypeError):
                continue

        # Ordenar por fecha
        ventas_ordenadas = dict(sorted(ventas_por_dia.items()))

        # Generar chart
        tmp_path = Path(tempfile.mkdtemp()) / "reporte_ventas.png"
        _generar_chart_ventas(ventas_ordenadas, str(tmp_path))

        total = sum(ventas_ordenadas.values())
        num_ventas = len(ventas)

        logger.info(
            "reporte_ventas_generado",
            path=str(tmp_path),
            total=total,
            num_ventas=num_ventas,
        )

        # Retornar con prefijo especial para que webhook detecte imagen
        return (
            f"[IMAGE:{tmp_path}]\n"
            f"📊 Reporte generado: {num_ventas} ventas, "
            f"total S/{total:.2f} en los últimos 7 días."
        )

    except DatabaseError as exc:
        logger.error("tool_generar_reporte_db_error", error=str(exc))
        return f"❌ Error de base de datos: {exc.message}"
    except Exception as exc:
        logger.error("tool_generar_reporte_failed", error=str(exc))
        return f"❌ Error al generar reporte: {exc!s}"
