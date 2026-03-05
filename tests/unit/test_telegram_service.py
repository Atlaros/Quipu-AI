"""Unit tests para TelegramService.

Testea parsing de updates de Telegram y lógica de servicio.
Sin llamadas reales a la API de Telegram.
"""

import pytest

from app.services.telegram_service import TelegramService


@pytest.fixture
def tg_service() -> TelegramService:
    """Instancia del servicio de Telegram."""
    return TelegramService()


@pytest.fixture
def valid_text_update() -> dict:
    """Update válido de un mensaje de texto de Telegram."""
    return {
        "update_id": 100200300,
        "message": {
            "message_id": 42,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "María",
                "last_name": "García",
                "language_code": "es",
            },
            "chat": {
                "id": 123456789,
                "first_name": "María",
                "last_name": "García",
                "type": "private",
            },
            "date": 1708000000,
            "text": "¿Hay Nike Air en 42?",
        },
    }


@pytest.fixture
def valid_photo_update() -> dict:
    """Update válido de un mensaje con foto de Telegram."""
    return {
        "update_id": 100200301,
        "message": {
            "message_id": 43,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Carlos",
                "last_name": "López",
            },
            "chat": {
                "id": 123456789,
                "first_name": "Carlos",
                "last_name": "López",
                "type": "private",
            },
            "date": 1708000001,
            "photo": [
                {"file_id": "small_photo_id", "width": 90, "height": 90},
                {"file_id": "medium_photo_id", "width": 320, "height": 320},
                {"file_id": "large_photo_id", "width": 800, "height": 800},
            ],
            "caption": "Este es mi producto",
        },
    }


@pytest.fixture
def valid_voice_update() -> dict:
    """Update válido de un mensaje de audio/voz de Telegram."""
    return {
        "update_id": 100200302,
        "message": {
            "message_id": 44,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Ana",
            },
            "chat": {
                "id": 987654321,
                "first_name": "Ana",
                "type": "private",
            },
            "date": 1708000002,
            "voice": {
                "file_id": "voice_file_123",
                "duration": 5,
                "mime_type": "audio/ogg",
            },
        },
    }


class TestParseUpdate:
    """Tests para parse_update."""

    def test_parse_texto_valido(
        self,
        tg_service: TelegramService,
        valid_text_update: dict,
    ) -> None:
        """Debe extraer texto, chat_id y nombre de un mensaje válido."""
        result = tg_service.parse_update(valid_text_update)

        assert result is not None
        assert result["chat_id"] == "123456789"
        assert result["text"] == "¿Hay Nike Air en 42?"
        assert result["update_id"] == "100200300"
        assert result["name"] == "María García"
        assert result["type"] == "text"

    def test_parse_foto_valida(
        self,
        tg_service: TelegramService,
        valid_photo_update: dict,
    ) -> None:
        """Debe parsear foto tomando la de mayor resolución."""
        result = tg_service.parse_update(valid_photo_update)

        assert result is not None
        assert result["type"] == "image"
        assert result["file_id"] == "large_photo_id"  # Mayor resolución
        assert result["text"] == "Este es mi producto"
        assert result["name"] == "Carlos López"

    def test_parse_audio_valido(
        self,
        tg_service: TelegramService,
        valid_voice_update: dict,
    ) -> None:
        """Debe parsear mensajes de voz con file_id."""
        result = tg_service.parse_update(valid_voice_update)

        assert result is not None
        assert result["type"] == "audio"
        assert result["file_id"] == "voice_file_123"
        assert result["mime_type"] == "audio/ogg"
        assert result["name"] == "Ana"

    def test_ignorar_update_sin_message(
        self,
        tg_service: TelegramService,
    ) -> None:
        """Debe retornar None para updates sin campo message."""
        # Ej: callback_query, edited_message, etc.
        result = tg_service.parse_update({"update_id": 999})
        assert result is None

    def test_ignorar_update_vacio(
        self,
        tg_service: TelegramService,
    ) -> None:
        """Debe retornar None para payloads vacíos."""
        result = tg_service.parse_update({})
        assert result is None

    def test_ignorar_mensaje_tipo_no_soportado(
        self,
        tg_service: TelegramService,
    ) -> None:
        """Debe retornar None para tipos no soportados (sticker, video, etc)."""
        update = {
            "update_id": 100200303,
            "message": {
                "message_id": 45,
                "from": {"id": 111, "first_name": "Test"},
                "chat": {"id": 111, "type": "private"},
                "date": 1708000003,
                "sticker": {"file_id": "sticker_123"},
            },
        }
        result = tg_service.parse_update(update)
        assert result is None

    def test_parse_nombre_solo_first_name(
        self,
        tg_service: TelegramService,
    ) -> None:
        """Debe manejar usuarios sin last_name."""
        update = {
            "update_id": 100200304,
            "message": {
                "message_id": 46,
                "from": {"id": 222, "first_name": "Rosa"},
                "chat": {"id": 222, "type": "private"},
                "date": 1708000004,
                "text": "Hola",
            },
        }
        result = tg_service.parse_update(update)

        assert result is not None
        assert result["name"] == "Rosa"

    def test_parse_foto_sin_caption(
        self,
        tg_service: TelegramService,
        valid_photo_update: dict,
    ) -> None:
        """Debe manejar fotos sin caption."""
        del valid_photo_update["message"]["caption"]

        result = tg_service.parse_update(valid_photo_update)

        assert result is not None
        assert result["type"] == "image"
        assert result["text"] == ""
