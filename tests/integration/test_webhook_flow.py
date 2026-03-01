"""Test de integración para el flujo de webhook.

Verifica el ciclo completo del webhook de WhatsApp:
- GET: verificación challenge-response
- POST con payload: procesamiento
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from main import create_app


@pytest.fixture
def client():
    """Cliente de prueba FastAPI."""
    app = create_app()
    return TestClient(app)


class TestWebhookVerification:
    """Tests para el endpoint GET /api/v1/webhook (verificación)."""

    def test_verificacion_exitosa(self, client):
        """Test que el challenge-response funciona con token correcto."""
        response = client.get(
            "/api/v1/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.whatsapp_verify_token,
                "hub.challenge": "test_challenge_123",
            },
        )

        assert response.status_code == 200
        assert response.text == "test_challenge_123"

    def test_verificacion_token_invalido(self, client):
        """Test que rechaza tokens de verificación incorrectos."""
        response = client.get(
            "/api/v1/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "TOKEN_INCORRECTO",
                "hub.challenge": "test_challenge",
            },
        )

        assert response.status_code == 403


class TestWebhookPost:
    """Tests para el endpoint POST /api/v1/webhook (mensajes)."""

    def test_post_payload_es_aceptado(self, client):
        """Test que un webhook POST con payload válido responde 200.

        Nota: En CI, WHATSAPP_APP_SECRET está vacío, lo que desactiva
        la verificación HMAC. El endpoint debe retornar 200 siempre
        que reciba un payload válido.
        """
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "123"},
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

        # Solo testar si la verificación HMAC está desactivada (como en CI)
        if not settings.whatsapp_app_secret:
            response = client.post("/api/v1/webhook", json=payload)
            assert response.status_code == 200
        else:
            pytest.skip("WHATSAPP_APP_SECRET configurado — HMAC requerido")

    def test_post_sin_object_whatsapp(self, client):
        """Test que un payload sin el campo correcto responde 200 (por diseño)."""
        payload = {"object": "otro_tipo", "entry": []}

        if not settings.whatsapp_app_secret:
            response = client.post("/api/v1/webhook", json=payload)
            # El webhook retorna 200 siempre para evitar retries de Meta
            assert response.status_code == 200
        else:
            pytest.skip("WHATSAPP_APP_SECRET configurado")
