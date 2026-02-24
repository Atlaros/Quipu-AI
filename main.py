"""Quipu AI Backend — App Factory.

Punto de entrada de la aplicación FastAPI.
Configura middleware, routers, logging, y exception handlers.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.chat import router as chat_router
from app.api.v1.clientes import router as clientes_router
from app.api.v1.health import router as health_router
from app.api.v1.inventario import router as inventario_router
from app.api.v1.productos import router as productos_router
from app.api.v1.ventas import router as ventas_router
from app.api.v1.webhook import router as webhook_router
from app.core.config import settings
from app.core.exceptions import QuipuBaseError, ResourceNotFoundError
from app.core.logging import setup_logging

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifecycle hook: se ejecuta al iniciar y al apagar la app.

    Args:
        app: Instancia de FastAPI.
    """
    setup_logging(debug=settings.debug)
    
    # Iniciar servicios globales
    from app.services.redis_service import RedisService
    await RedisService().connect()
    
    await logger.ainfo("quipu_ai_started", version=settings.app_version)
    yield
    
    await RedisService().close()
    await logger.ainfo("quipu_ai_shutdown")


def create_app() -> FastAPI:
    """Factory que crea y configura la aplicación FastAPI.

    Returns:
        Instancia de FastAPI configurada con routers y handlers.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Backend del Gerente Virtual para microempresas",
        lifespan=lifespan,
    )

    # --- Exception Handlers ---
    @app.exception_handler(ResourceNotFoundError)
    async def not_found_handler(
        request: Request, exc: ResourceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @app.exception_handler(QuipuBaseError)
    async def base_error_handler(
        request: Request, exc: QuipuBaseError
    ) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": exc.message})

    from fastapi import APIRouter

    # --- Routers V1 ---
    api_v1_router = APIRouter(prefix="/api/v1")
    
    # El health check puede quedar en root también si se desea, pero lo estandarizamos en v1
    # Opcional: Rutas globales
    @app.get("/healthz", tags=["Health"])
    async def healthz():
        return {"status": "ok"}

    api_v1_router.include_router(health_router)
    api_v1_router.include_router(ventas_router)
    api_v1_router.include_router(clientes_router)
    api_v1_router.include_router(inventario_router)
    api_v1_router.include_router(productos_router)
    api_v1_router.include_router(chat_router)
    api_v1_router.include_router(webhook_router)

    app.include_router(api_v1_router)

    return app


app = create_app()
