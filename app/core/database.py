"""Conexión a Supabase — Singleton reutilizable.

Provee un cliente Supabase que se crea una sola vez y se reutiliza
en todas las invocaciones. Se inyecta en los repositorios vía DI.
"""

from supabase import Client, create_client

from app.core.config import settings

_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """Retorna el cliente singleton de Supabase.

    Crea la instancia en la primera llamada y la reutiliza en las
    siguientes. Hilo-safe para aplicaciones ASGI single-process.

    Returns:
        Client: Instancia del cliente Supabase configurada.
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase_client
