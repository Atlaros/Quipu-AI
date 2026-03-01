"""Servicio de Redis — Cache y almacenamiento efímero.

Provee operaciones async de get/set/delete contra Redis.
Se instancia UNA vez a nivel de módulo y se inyecta donde se necesite.
"""

import redis.asyncio as redis
import redis.exceptions as redis_exc
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class RedisService:
    """Servicio para interactuar con Redis.

    Instanciado una sola vez a nivel de módulo (`redis_service`).
    Se inyecta en repositorios y endpoints que lo necesiten.
    """

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Inicializa la conexión a Redis."""
        if self._redis:
            return

        try:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
            )
            await self._redis.ping()
            logger.info("redis_connected", url=settings.redis_url)
        except redis_exc.RedisError as exc:
            logger.error("redis_connection_failed", error=str(exc))
            self._redis = None

    async def close(self) -> None:
        """Cierra la conexión a Redis."""
        if self._redis:
            await self._redis.close()
            logger.info("redis_closed")
            self._redis = None

    async def get(self, key: str) -> str | None:
        """Obtiene un valor de Redis."""
        if not self._redis:
            await self.connect()
            if not self._redis:
                return None

        try:
            return await self._redis.get(key)
        except redis_exc.RedisError as exc:
            logger.error("redis_get_failed", key=key, error=str(exc))
            return None

    async def set(self, key: str, value: str, expire: int = 3600) -> bool:
        """Guarda un valor en Redis con expiración (default 1h)."""
        if not self._redis:
            await self.connect()
            if not self._redis:
                return False

        try:
            await self._redis.set(key, value, ex=expire)
            return True
        except redis_exc.RedisError as exc:
            logger.error("redis_set_failed", key=key, error=str(exc))
            return False

    async def delete(self, key: str) -> bool:
        """Elimina una clave de Redis."""
        if not self._redis:
            await self.connect()
            if not self._redis:
                return False

        try:
            await self._redis.delete(key)
            return True
        except redis_exc.RedisError as exc:
            logger.error("redis_delete_failed", key=key, error=str(exc))
            return False


# Instancia única a nivel de módulo — se inyecta vía DI
redis_service = RedisService()
