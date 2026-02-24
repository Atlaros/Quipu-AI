"""Health check endpoint.

Endpoint obligatorio en toda API de producción.
Usado por load balancers, monitoring, y despliegues para verificar estado.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Verifica que la API está operativa.

    Returns:
        Estado de salud de la aplicación.
    """
    return {"status": "healthy", "service": "quipu-ai-backend"}
