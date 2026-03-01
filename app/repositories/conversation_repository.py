"""Repository de conversaciones — Historial por teléfono.

Persiste mensajes (human/ai) en Supabase para que el agente
tenga contexto entre mensajes del mismo usuario.
"""

import json

import redis.exceptions as redis_exc
import structlog
from postgrest.exceptions import APIError

from app.core.database import get_supabase_client
from app.services.redis_service import RedisService

logger = structlog.get_logger()

# Máximo de mensajes a cargar como contexto
MAX_HISTORY_MESSAGES = 10
CACHE_TTL = 3600  # 1 hora


class ConversationRepository:
    """Acceso a datos de historial de conversaciones en Supabase + Redis.

    Attributes:
        db: Cliente Supabase inyectado.
        redis: Servicio Redis inyectado.
    """

    def __init__(self, redis: RedisService | None = None) -> None:
        self.db = get_supabase_client()
        self.redis = redis

    async def get_history(self, phone: str, limit: int = MAX_HISTORY_MESSAGES) -> list[dict]:
        """Obtiene los últimos N mensajes de un teléfono.

        Estrategia Cache-Aside:
        1. Intentar leer de Redis.
        2. Si no hay hit, leer de Supabase.
        3. Escribir en Redis.
        """
        cache_key = f"chat_history:{phone}"

        # 1. Intentar leer caché
        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    logger.debug("redis_cache_hit", phone=phone)
                    return json.loads(cached)
            except redis_exc.RedisError:
                pass  # Fallback silencioso a DB

        # 2. Leer de DB
        try:
            result = (
                self.db.table("conversaciones")
                .select("role, content, created_at")
                .eq("phone", phone)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            # Invertir para orden cronológico (más antiguo primero)
            messages = list(reversed(result.data)) if result.data else []

            # 3. Guardar en Caché (background)
            if messages and self.redis:
                try:
                    await self.redis.set(cache_key, json.dumps(messages), expire=CACHE_TTL)
                except redis_exc.RedisError as exc:
                    logger.warning("redis_cache_write_failed", error=str(exc))

            logger.debug(
                "conversation_history_loaded_db",
                phone=phone,
                count=len(messages),
            )
            return messages

        except APIError as exc:
            logger.error(
                "conversation_history_failed",
                phone=phone,
                error=str(exc),
            )
            return []

    async def save_message(self, phone: str, role: str, content: str) -> None:
        """Guarda un mensaje en el historial y borra caché."""
        try:
            # 1. Persistir en DB
            self.db.table("conversaciones").insert(
                {
                    "phone": phone,
                    "role": role,
                    "content": content,
                }
            ).execute()

            logger.debug(
                "conversation_message_saved",
                phone=phone,
                role=role,
                model_length=len(content),
            )

            # 2. Invalidar caché
            if self.redis:
                cache_key = f"chat_history:{phone}"
                await self.redis.delete(cache_key)

        except APIError as exc:
            logger.error(
                "conversation_save_failed",
                phone=phone,
                role=role,
                error=str(exc),
            )
