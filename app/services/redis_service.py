
import redis.asyncio as redis
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class RedisService:
    """Servicio Singleton para interactuar con Redis."""

    _instance = None
    _redis: redis.Redis | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisService, cls).__new__(cls)
        return cls._instance

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
        except Exception as exc:
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
        except Exception as exc:
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
        except Exception as exc:
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
        except Exception as exc:
            logger.error("redis_delete_failed", key=key, error=str(exc))
            return False
