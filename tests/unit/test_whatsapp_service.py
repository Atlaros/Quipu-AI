"""Unit tests para WhatsAppService.

Testea parsing de payloads de Meta y lógica de servicio.
Sin llamadas reales a la API de WhatsApp.
"""

import pytest

from app.services.whatsapp_service import WhatsAppService


@pytest.fixture
def wa_service() -> WhatsAppService:
    """Instancia del servicio de WhatsApp."""
    return WhatsAppService()


@pytest.fixture
def valid_text_payload() -> dict:
    """Payload válido de un mensaje de texto de Meta."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "María García"},
                                    "wa_id": "51999111222",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "51999111222",
                                    "id": "wamid.abc123",
                                    "timestamp": "1708000000",
                                    "type": "text",
                                    "text": {"body": "vendí 3 arroz a Juan"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def status_update_payload() -> dict:
    """Payload de actualización de estado (no es un mensaje)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "987654321",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.abc123",
                                    "status": "delivered",
                                    "timestamp": "1708000000",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


class TestParseMessage:
    """Tests para parse_message."""

    def test_parse_texto_valido(
        self,
        wa_service: WhatsAppService,
        valid_text_payload: dict,
    ) -> None:
        """Debe extraer texto, teléfono y nombre de un mensaje válido."""
        result = wa_service.parse_message(valid_text_payload)

        assert result is not None
        assert result["phone"] == "51999111222"
        assert result["text"] == "vendí 3 arroz a Juan"
        assert result["message_id"] == "wamid.abc123"
        assert result["name"] == "María García"

    def test_ignorar_status_updates(
        self,
        wa_service: WhatsAppService,
        status_update_payload: dict,
    ) -> None:
        """Debe retornar None para status updates (no son mensajes)."""
        result = wa_service.parse_message(status_update_payload)
        assert result is None

    def test_ignorar_payload_vacio(
        self,
        wa_service: WhatsAppService,
    ) -> None:
        """Debe retornar None para payloads vacíos."""
        result = wa_service.parse_message({})
        assert result is None

    def test_parse_mensaje_audio(
        self,
        wa_service: WhatsAppService,
        valid_text_payload: dict,
    ) -> None:
        """Debe parsear mensajes de audio con media_id."""
        msg = valid_text_payload["entry"][0]["changes"][0]["value"]["messages"][0]
        msg["type"] = "audio"
        msg["audio"] = {"id": "media_audio_123", "mime_type": "audio/ogg; codecs=opus"}

        result = wa_service.parse_message(valid_text_payload)

        assert result is not None
        assert result["type"] == "audio"
        assert result["media_id"] == "media_audio_123"
        assert result["phone"] == "51999111222"

    def test_parse_mensaje_imagen(
        self,
        wa_service: WhatsAppService,
        valid_text_payload: dict,
    ) -> None:
        """Debe parsear mensajes de imagen con media_id y caption."""
        msg = valid_text_payload["entry"][0]["changes"][0]["value"]["messages"][0]
        msg["type"] = "image"
        msg["image"] = {
            "id": "media_img_456",
            "mime_type": "image/jpeg",
            "caption": "Este es mi producto",
        }

        result = wa_service.parse_message(valid_text_payload)

        assert result is not None
        assert result["type"] == "image"
        assert result["media_id"] == "media_img_456"
        assert result["text"] == "Este es mi producto"

    def test_ignorar_mensaje_video(
        self,
        wa_service: WhatsAppService,
        valid_text_payload: dict,
    ) -> None:
        """Debe retornar None para tipos no soportados (video, sticker, etc)."""
        msg = valid_text_payload["entry"][0]["changes"][0]["value"]["messages"][0]
        msg["type"] = "video"

        result = wa_service.parse_message(valid_text_payload)
        assert result is None
