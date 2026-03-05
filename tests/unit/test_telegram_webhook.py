"""Unit tests para el webhook de Telegram.

Testea recepción de updates, deduplicación y validación de secret.
Sin llamadas reales a la API de Telegram.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _mock_telegram_settings():
    """Mockea settings de Telegram para tests."""
    with patch("app.api.v1.telegram_webhook.settings") as mock_settings:
        mock_settings.telegram_bot_token = "test-token-123"
        mock_settings.telegram_webhook_secret = "test-secret"
        yield mock_settings


@pytest.fixture
def _mock_redis():
    """Mockea Redis para deduplicación."""
    with patch("app.api.v1.telegram_webhook.RedisService") as mock_cls:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=None)
        mock_instance.set = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def valid_text_update() -> dict:
    """Update válido de texto para tests."""
    return {
        "update_id": 100200300,
        "message": {
            "message_id": 42,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
            },
            "chat": {
                "id": 123456789,
                "first_name": "Test",
                "type": "private",
            },
            "date": 1708000000,
            "text": "Hola, ¿qué tienen?",
        },
    }


class TestTelegramWebhook:
    """Tests para el endpoint de webhook de Telegram."""

    def test_rechazar_secret_invalido(
        self,
        _mock_telegram_settings: None,
    ) -> None:
        """Debe rechazar requests con secret token inválido."""
        # Import after mocks are set up
        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 1},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        assert response.status_code == 403

    def test_aceptar_update_sin_message(
        self,
        _mock_telegram_settings: None,
    ) -> None:
        """Debe retornar ok para updates sin message (ej: edited_message)."""
        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/telegram/webhook",
            json={"update_id": 999},
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_deduplicar_update(
        self,
        _mock_telegram_settings: None,
        _mock_redis: AsyncMock,
        valid_text_update: dict,
    ) -> None:
        """Debe ignorar updates duplicados."""
        _mock_redis.get = AsyncMock(return_value="1")

        from main import app

        client = TestClient(app)
        response = client.post(
            "/api/v1/telegram/webhook",
            json=valid_text_update,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestParseUpdate:
    """Tests para parse_update en el contexto del webhook."""

    def test_parse_text_update(self) -> None:
        """Parsea correctamente un update de texto."""
        from app.services.telegram_service import TelegramService

        service = TelegramService()
        update = {
            "update_id": 100,
            "message": {
                "message_id": 1,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 123, "type": "private"},
                "date": 170800,
                "text": "Hola",
            },
        }
        result = service.parse_update(update)
        assert result is not None
        assert result["chat_id"] == "123"
        assert result["text"] == "Hola"
        assert result["type"] == "text"
