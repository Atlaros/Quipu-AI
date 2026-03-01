"""Dependency Injection para FastAPI.

Aquí se definen las dependencias que se inyectan en los routers
usando Depends(). Centraliza la creación de clientes, servicios, etc.
"""

from collections.abc import Generator

from supabase import Client

from app.core.database import get_supabase_client
from app.services.redis_service import RedisService, redis_service


def get_db() -> Generator[Client, None, None]:
    """Provee un cliente Supabase para inyectar en los endpoints.

    Yields:
        Client: Instancia del cliente Supabase.
    """
    client = get_supabase_client()
    yield client


def get_redis() -> RedisService:
    """Provee la instancia singleton de RedisService.

    Returns:
        RedisService: Instancia configurada del servicio Redis.
    """
    return redis_service
