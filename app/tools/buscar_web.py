"""Tool: Búsqueda Web con Tavily.

Tool callable por el agente LangGraph para buscar información
actualizada en internet: tendencias de moda, precios de competencia,
noticias relevantes para el negocio.
"""

import structlog
from langchain_core.tools import tool

from app.core.config import settings

logger = structlog.get_logger()


@tool
def buscar_web(query: str) -> str:
    """Busca información actualizada en internet.

    Útil para consultar tendencias de moda, verificar precios de
    competidores, o buscar cualquier información externa relevante
    para la tienda.

    Args:
        query: Término de búsqueda (ej: "tendencias calzado 2025 Perú").

    Returns:
        Resumen de los resultados más relevantes encontrados.
    """
    if not settings.tavily_api_key:
        return "⚠️ Búsqueda web no disponible (API key de Tavily no configurada)."

    try:
        from tavily import TavilyClient  # type: ignore[import-untyped]

        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(
            query=query,
            max_results=3,
            search_depth="basic",
        )

        results = response.get("results", [])
        if not results:
            return f"🔍 No encontré resultados para: '{query}'."

        lines = [f"🌐 **Resultados para '{query}':**"]
        for r in results:
            title = r.get("title", "Sin título")
            content = r.get("content", "")[:200].strip()
            url = r.get("url", "")
            lines.append(f"\n• **{title}**\n  {content}…\n  🔗 {url}")

        logger.info("buscar_web_success", query=query, num_results=len(results))
        return "\n".join(lines)

    except ImportError:
        return "⚠️ Módulo 'tavily-python' no instalado. Ejecuta: uv pip install tavily-python"
    except Exception as exc:
        logger.error("tool_buscar_web_failed", query=query, error=str(exc))
        return f"❌ Error al buscar: {exc!s}"
