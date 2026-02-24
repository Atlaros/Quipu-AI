"""Conexión asíncrona a Supabase.

Provee un cliente async reutilizable para interactuar con la API REST
de Supabase. Se inyecta en los repositorios via FastAPI Depends().
"""

from supabase import Client, create_client

from app.core.config import settings


def get_supabase_client() -> Client:
    """Crea y retorna un cliente de Supabase.

    Returns:
        Client: Instancia del cliente Supabase configurada.
    """
    return create_client(settings.supabase_url, settings.supabase_key)
