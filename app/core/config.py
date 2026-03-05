"""Configuración centralizada del proyecto Quipu AI.

Usa pydantic-settings para cargar variables de entorno desde .env.
Un solo Settings class para todo el proyecto. Nunca usar os.getenv() directamente.
"""

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración global de la aplicación.

    Carga automáticamente desde variables de entorno o archivo .env.
    Todas las variables son obligatorias salvo que tengan default.

    Attributes:
        app_name: Nombre de la aplicación.
        app_version: Versión semántica del proyecto.
        debug: Modo debug (False en producción).
        supabase_url: URL de la instancia de Supabase.
        supabase_key: API Key de Supabase (anon o service_role).
        google_api_key: API Key para Google Gemini.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Quipu AI"
    app_version: str = "0.1.0"
    debug: bool = False

    # Supabase
    supabase_url: str
    supabase_key: str

    # Redis (Cache)
    redis_url: str = "redis://localhost:6379/0"

    # Google AI (Gemini) — soporta múltiples keys separadas por coma
    google_api_key: str = ""
    # Groq (Llama 3 / Whisper)
    groq_api_key: str | None = None
    # OpenRouter (fallback multi-modelo)
    openrouter_api_key: str | None = None
    # Tavily (búsqueda web)
    tavily_api_key: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def google_api_keys(self) -> list[str]:
        """Lista de API keys de Gemini (separadas por coma en .env)."""
        return [k.strip() for k in self.google_api_key.split(",") if k.strip()]

    # WhatsApp Business API
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_verify_token: str = "quipu-ai-verify-2026"
    whatsapp_app_secret: str = ""  # Para verificar firma HMAC de Meta

    # Telegram Bot API
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""  # Secret para validar updates


# Singleton: importar esta instancia en todo el proyecto
settings = Settings()
