"""Service de WhatsApp — Envío y parseo de mensajes.

Maneja la comunicación con la WhatsApp Business Cloud API de Meta.
Parsea webhooks entrantes, envía texto e imágenes al usuario.
"""

import structlog
from httpx import AsyncClient

from app.core.config import settings

logger = structlog.get_logger()

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"


class WhatsAppService:
    """Servicio para interactuar con la API de WhatsApp Business.

    Parsea mensajes entrantes del webhook de Meta y envía respuestas
    (texto e imágenes).
    """

    @staticmethod
    def parse_message(payload: dict) -> dict | None:
        """Extrae el mensaje de texto del payload del webhook de Meta.

        Args:
            payload: JSON del webhook de Meta.

        Returns:
            Dict con phone, text, message_id si es un mensaje de texto.
            None si no es un mensaje de texto procesable.
        """
        try:
            entry = payload.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None

            message = messages[0]
            msg_type = message.get("type", "")

            base = {
                "phone": message.get("from", ""),
                "message_id": message.get("id", ""),
                "name": value.get("contacts", [{}])[0].get("profile", {}).get("name", ""),
                "type": msg_type,
            }

            if msg_type == "text":
                base["text"] = message.get("text", {}).get("body", "")
                return base

            if msg_type == "audio":
                audio = message.get("audio", {})
                base["media_id"] = audio.get("id", "")
                base["mime_type"] = audio.get("mime_type", "audio/ogg")
                return base

            if msg_type == "image":
                image = message.get("image", {})
                base["media_id"] = image.get("id", "")
                base["mime_type"] = image.get("mime_type", "image/jpeg")
                base["text"] = image.get("caption", "")
                return base

            logger.info("webhook_msg_type_unsupported", msg_type=msg_type)
            return None

        except (IndexError, KeyError) as exc:
            logger.error("webhook_parse_failed", error=str(exc))
            return None

    @staticmethod
    async def download_media(media_id: str) -> bytes | None:
        """Descarga un archivo multimedia de WhatsApp.

        Flujo en 2 pasos:
        1. GET /{media_id} → obtiene la URL de descarga.
        2. GET {url} → descarga los bytes del archivo.

        Args:
            media_id: ID del medio en WhatsApp.

        Returns:
            Bytes del archivo, o None si falla.
        """
        if not settings.whatsapp_token:
            logger.warning("whatsapp_not_configured")
            return None

        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
        }

        try:
            # Paso 1: Obtener URL de descarga
            url_endpoint = f"{WHATSAPP_API_URL}/{media_id}"
            async with AsyncClient() as client:
                response = await client.get(
                    url_endpoint, headers=headers, timeout=10.0
                )

            if response.status_code != 200:
                logger.error(
                    "whatsapp_media_url_failed",
                    status=response.status_code,
                    body=response.text,
                )
                return None

            media_url = response.json().get("url")
            if not media_url:
                logger.error("whatsapp_media_no_url")
                return None

            # Paso 2: Descargar bytes
            async with AsyncClient() as client:
                download = await client.get(
                    media_url, headers=headers, timeout=30.0
                )

            if download.status_code != 200:
                logger.error(
                    "whatsapp_media_download_failed",
                    status=download.status_code,
                )
                return None

            logger.info(
                "whatsapp_media_downloaded",
                media_id=media_id,
                size=len(download.content),
            )
            return download.content

        except Exception as exc:
            logger.error("whatsapp_media_download_error", error=str(exc))
            return None

    @staticmethod
    async def send_message(to: str, text: str) -> bool:
        """Envía un mensaje de texto al usuario vía WhatsApp.

        Args:
            to: Número de teléfono del destinatario (sin +).
            text: Texto del mensaje a enviar.

        Returns:
            True si se envió correctamente, False si falló.
        """
        if not settings.whatsapp_token or not settings.whatsapp_phone_id:
            logger.warning("whatsapp_not_configured")
            return False

        url = f"{WHATSAPP_API_URL}/{settings.whatsapp_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        try:
            async with AsyncClient() as client:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=10.0
                )

            if response.status_code == 200:
                logger.info("whatsapp_message_sent", to=to)
                return True

            logger.error(
                "whatsapp_send_failed",
                status_code=response.status_code,
                body=response.text,
            )
            return False

        except Exception as exc:
            logger.error("whatsapp_send_error", error=str(exc))
            return False

    @staticmethod
    async def upload_media(file_path: str) -> str | None:
        """Sube un archivo a la WhatsApp Media API.

        Args:
            file_path: Ruta local del archivo a subir.

        Returns:
            media_id de WhatsApp, o None si falló.
        """
        if not settings.whatsapp_token or not settings.whatsapp_phone_id:
            logger.warning("whatsapp_not_configured")
            return None

        url = f"{WHATSAPP_API_URL}/{settings.whatsapp_phone_id}/media"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
        }

        try:
            with open(file_path, "rb") as f:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = "application/octet-stream"
                files = {
                    "file": (file_path.split("/")[-1], f, mime_type),
                }
                data = {
                    "messaging_product": "whatsapp",
                }
                async with AsyncClient() as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=30.0,
                    )

            if response.status_code == 200:
                media_id = response.json().get("id")
                logger.info("whatsapp_media_uploaded", media_id=media_id)
                return media_id

            logger.error(
                "whatsapp_media_upload_failed",
                status_code=response.status_code,
                body=response.text,
            )
            return None

        except Exception as exc:
            logger.error("whatsapp_media_upload_error", error=str(exc))
            return None

    @staticmethod
    async def send_image(to: str, media_id: str, caption: str = "") -> bool:
        """Envía una imagen al usuario vía WhatsApp.

        Args:
            to: Número de teléfono del destinatario.
            media_id: ID del medio subido a WhatsApp.
            caption: Texto descriptivo de la imagen (opcional).

        Returns:
            True si se envió correctamente, False si falló.
        """
        if not settings.whatsapp_token or not settings.whatsapp_phone_id:
            logger.warning("whatsapp_not_configured")
            return False

        url = f"{WHATSAPP_API_URL}/{settings.whatsapp_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        }
        image_payload: dict[str, str] = {"id": media_id}
        if caption:
            image_payload["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": image_payload,
        }

        try:
            async with AsyncClient() as client:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=10.0
                )

            if response.status_code == 200:
                logger.info("whatsapp_image_sent", to=to, media_id=media_id)
                return True

            logger.error(
                "whatsapp_image_send_failed",
                status_code=response.status_code,
                body=response.text,
            )
            return False

        except Exception as exc:
            logger.error("whatsapp_image_send_error", error=str(exc))
            return False

    @staticmethod
    async def mark_as_read(message_id: str) -> None:
        """Marca un mensaje como leído (doble check azul).

        Args:
            message_id: ID del mensaje de WhatsApp.
        """
        if not settings.whatsapp_token or not settings.whatsapp_phone_id:
            return

        url = f"{WHATSAPP_API_URL}/{settings.whatsapp_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            async with AsyncClient() as client:
                await client.post(
                    url, json=payload, headers=headers, timeout=5.0
                )
        except Exception as exc:
            logger.error("whatsapp_mark_read_failed", error=str(exc))
