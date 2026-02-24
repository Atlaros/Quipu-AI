"""Dependency Injection para FastAPI.

Aquí se definen las dependencias que se inyectan en los routers
usando Depends(). Centraliza la creación de clientes, servicios, etc.
"""

from collections.abc import Generator

from supabase import Client

from app.core.database import get_supabase_client


def get_db() -> Generator[Client, None, None]:
    """Provee un cliente Supabase para inyectar en los endpoints.

    Yields:
        Client: Instancia del cliente Supabase.
    """
    client = get_supabase_client()
    yield client
