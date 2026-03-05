"""Service de Telegram — Envío y parseo de mensajes.

Maneja la comunicación con la Telegram Bot API.
Parsea updates entrantes, envía texto e imágenes al usuario.
"""

import httpx
import structlog
from httpx import AsyncClient

from app.core.config import settings

logger = structlog.get_logger()

TELEGRAM_API_URL = "https://api.telegram.org"


class TelegramService:
    """Servicio para interactuar con la Telegram Bot API.

    Parsea updates entrantes y envía respuestas (texto e imágenes).
    """

    @property
    def _base_url(self) -> str:
        """URL base de la API del bot."""
        return f"{TELEGRAM_API_URL}/bot{settings.telegram_bot_token}"

    @staticmethod
    def parse_update(update: dict) -> dict | None:
        """Extrae el mensaje del update de Telegram.

        Args:
            update: JSON del update de Telegram.

        Returns:
            Dict con chat_id, text, update_id, name, type.
            None si no es un mensaje procesable.
        """
        try:
            message = update.get("message")
            if not message:
                return None

            chat = message.get("chat", {})
            chat_id = str(chat.get("id", ""))
            if not chat_id:
                return None

            # Nombre del usuario
            from_user = message.get("from", {})
            first_name = from_user.get("first_name", "")
            last_name = from_user.get("last_name", "")
            name = f"{first_name} {last_name}".strip()

            update_id = str(update.get("update_id", ""))

            # Determinar tipo de mensaje
            if "text" in message:
                return {
                    "chat_id": chat_id,
                    "text": message["text"],
                    "update_id": update_id,
                    "name": name,
                    "type": "text",
                }

            if "voice" in message or "audio" in message:
                media = message.get("voice") or message.get("audio", {})
                return {
                    "chat_id": chat_id,
                    "update_id": update_id,
                    "name": name,
                    "type": "audio",
                    "file_id": media.get("file_id", ""),
                    "mime_type": media.get("mime_type", "audio/ogg"),
                }

            if "photo" in message:
                # Telegram envía varias resoluciones; tomamos la mayor
                photos = message["photo"]
                best_photo = photos[-1] if photos else {}
                return {
                    "chat_id": chat_id,
                    "update_id": update_id,
                    "name": name,
                    "type": "image",
                    "file_id": best_photo.get("file_id", ""),
                    "mime_type": "image/jpeg",
                    "text": message.get("caption", ""),
                }

            logger.info("telegram_msg_type_unsupported", msg_keys=list(message.keys()))
            return None

        except (IndexError, KeyError) as exc:
            logger.error("telegram_parse_failed", error=str(exc))
            return None

    async def download_file(self, file_id: str) -> bytes | None:
        """Descarga un archivo de Telegram.

        Flujo en 2 pasos:
        1. getFile → obtiene file_path.
        2. GET file/{file_path} → descarga bytes.

        Args:
            file_id: ID del archivo en Telegram.

        Returns:
            Bytes del archivo, o None si falla.
        """
        if not settings.telegram_bot_token:
            logger.warning("telegram_not_configured")
            return None

        try:
            # Paso 1: Obtener file_path
            async with AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/getFile",
                    params={"file_id": file_id},
                    timeout=10.0,
                )

            if response.status_code != 200:
                logger.error(
                    "telegram_get_file_failed",
                    status=response.status_code,
                    body=response.text,
                )
                return None

            result = response.json().get("result", {})
            file_path = result.get("file_path")
            if not file_path:
                logger.error("telegram_no_file_path")
                return None

            # Paso 2: Descargar bytes
            download_url = f"{TELEGRAM_API_URL}/file/bot{settings.telegram_bot_token}/{file_path}"
            async with AsyncClient() as client:
                download = await client.get(download_url, timeout=30.0)

            if download.status_code != 200:
                logger.error(
                    "telegram_file_download_failed",
                    status=download.status_code,
                )
                return None

            logger.info(
                "telegram_file_downloaded",
                file_id=file_id,
                size=len(download.content),
            )
            return download.content

        except httpx.HTTPError as exc:
            logger.error("telegram_file_download_error", error=str(exc))
            return None

    async def send_message(self, to: str, text: str) -> bool:
        """Envía un mensaje de texto al usuario vía Telegram.

        Args:
            to: chat_id del destinatario.
            text: Texto del mensaje a enviar.

        Returns:
            True si se envió correctamente, False si falló.
        """
        if not settings.telegram_bot_token:
            logger.warning("telegram_not_configured")
            return False

        try:
            async with AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": to,
                        "text": text,
                        "parse_mode": "Markdown",
                    },
                    timeout=10.0,
                )

            if response.status_code == 200:
                logger.info("telegram_message_sent", to=to)
                return True

            logger.error(
                "telegram_send_failed",
                status_code=response.status_code,
                body=response.text,
            )
            return False

        except httpx.HTTPError as exc:
            logger.error("telegram_send_error", error=str(exc))
            return False

    async def send_image(self, to: str, image_path: str, caption: str = "") -> bool:
        """Envía una imagen al usuario vía Telegram.

        Args:
            to: chat_id del destinatario.
            image_path: Ruta local de la imagen a enviar.
            caption: Texto descriptivo de la imagen (opcional).

        Returns:
            True si se envió correctamente, False si falló.
        """
        if not settings.telegram_bot_token:
            logger.warning("telegram_not_configured")
            return False

        try:
            with open(image_path, "rb") as f:
                files = {"photo": (image_path.split("/")[-1], f, "image/png")}
                data: dict[str, str] = {"chat_id": to}
                if caption:
                    data["caption"] = caption

                async with AsyncClient() as client:
                    response = await client.post(
                        f"{self._base_url}/sendPhoto",
                        files=files,
                        data=data,
                        timeout=30.0,
                    )

            if response.status_code == 200:
                logger.info("telegram_image_sent", to=to)
                return True

            logger.error(
                "telegram_image_send_failed",
                status_code=response.status_code,
                body=response.text,
            )
            return False

        except httpx.HTTPError as exc:
            logger.error("telegram_image_send_error", error=str(exc))
            return False
        except FileNotFoundError:
            logger.error("telegram_image_file_not_found", path=image_path)
            return False
