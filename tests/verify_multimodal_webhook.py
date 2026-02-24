
import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

# Adjust path to include app
sys.path.append(".")

from main import app
from app.services.whatsapp_service import WhatsAppService
from app.services.media_service import MediaService

client = TestClient(app)

# Mock headers for valid signature (or bypass if we can)
# The webhook verify_signature checks settings.whatsapp_app_secret
# We can mock the settings or valid signature.
# Or just mock _verify_signature in webhook.py

@patch("app.api.v1.webhook._verify_signature", return_value=True)
@patch.object(WhatsAppService, "download_media")
@patch.object(WhatsAppService, "mark_as_read")
@patch.object(WhatsAppService, "send_message")
@patch.object(WhatsAppService, "send_image")
@patch.object(MediaService, "transcribe_audio")
@patch.object(MediaService, "process_image")
@patch("app.api.v1.webhook.agent.invoke")
def test_multimodal_webhook(
    mock_agent_invoke,
    mock_process_image,
    mock_transcribe_audio,
    mock_send_image,
    mock_send_message,
    mock_mark_read,
    mock_download,
    mock_verify_signature
):
    print("🚀 Iniciando Verificación de Multimodalidad (Webhook)...")

    # Setup mocks
    mock_download.return_value = b"fake_bytes"
    mock_mark_read.return_value = None
    mock_send_message.return_value = True
    mock_send_image.return_value = True
    
    # Mock Agent Response
    from langchain_core.messages import AIMessage
    mock_agent_invoke.return_value = {"messages": [AIMessage(content="Respuesta simulada del agente")]}

    # 1. Test AUDIO
    print("\n🎧 Probando flujo de AUDIO...")
    mock_transcribe_audio.return_value = "Quiero comprar unas zapatillas Nike talla 42"
    
    audio_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "TestUser"}}],
                    "messages": [{
                        "from": "51999999999",
                        "id": "msg_audio_123",
                        "type": "audio",
                        "audio": {"id": "media_audio_123", "mime_type": "audio/ogg"}
                    }]
                }
            }]
        }]
    }

    response = client.post("/api/v1/webhook/", json=audio_payload)
    
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.text}")
    assert response.status_code == 200
    mock_download.assert_called_with("media_audio_123")
    mock_transcribe_audio.assert_called_with(b"fake_bytes", "audio/ogg")
    
    # Verify agent response was sent
    if mock_send_message.called:
        kwargs = mock_send_message.call_args.kwargs
        print(f"✅ Respuesta del Agente a Audio: {kwargs.get('text')}")
    else:
        print("❌ El agente no respondió al audio.")

    # 2. Test IMAGE
    print("\n📸 Probando flujo de IMAGEN...")
    mock_process_image.return_value = "Unas zapatillas Adidas Superstar blancas"
    
    image_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "TestUser"}}],
                    "messages": [{
                        "from": "51999999999",
                        "id": "msg_image_123",
                        "type": "image",
                        "image": {"id": "media_image_123", "mime_type": "image/jpeg", "caption": "¿Tienen esto?"}
                    }]
                }
            }]
        }]
    }

    # Reset mocks for clarity
    mock_send_message.reset_mock()
    mock_download.reset_mock()

    response = client.post("/api/v1/webhook/", json=image_payload)

    assert response.status_code == 200
    mock_download.assert_called_with("media_image_123")
    mock_process_image.assert_called_with(b"fake_bytes", "image/jpeg")

    # Verify agent response was sent
    if mock_send_message.called:
        kwargs = mock_send_message.call_args.kwargs
        print(f"✅ Respuesta del Agente a Imagen: {kwargs.get('text')}")
    else:
        print("❌ El agente no respondió a la imagen.")

    # 3. Test Agent sends IMAGE
    print("\n📊 Probando flujo de RESPUESTA CON IMAGEN...")
    # Simulate agent returning [IMAGE:path]
    mock_agent_invoke.return_value = {"messages": [AIMessage(content="[IMAGE:/tmp/chart.png]\nReporte de ventas")]}
    
    text_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "TestUser"}}],
                    "messages": [{
                        "from": "51999999999",
                        "id": "msg_text_123",
                        "type": "text",
                        "text": {"body": "genera un reporte"}
                    }]
                }
            }]
        }]
    }

    mock_send_image.reset_mock()
    mock_send_message.reset_mock()
    # Mock upload media
    with patch.object(WhatsAppService, "upload_media", return_value="media_id_555") as mock_upload:
        response = client.post("/api/v1/webhook/", json=text_payload)
        
        assert response.status_code == 200
        mock_upload.assert_called_with("/tmp/chart.png")
        if mock_send_image.called:
            kwargs = mock_send_image.call_args.kwargs
            print(f"✅ Agente envió imagen: ID={kwargs.get('media_id')} Caption='{kwargs.get('caption')}'")
        else:
            print("❌ El agente no envió la imagen.")

if __name__ == "__main__":
    test_multimodal_webhook()
