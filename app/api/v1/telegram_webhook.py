"""Webhook de Telegram — Recepción de updates del bot.

Endpoint:
- POST /telegram/webhook: Recibir updates, procesarlos con el agente, responder.

Seguridad:
- Validación de secret_token enviado por Telegram en el header
  X-Telegram-Bot-Api-Secret-Token.
"""

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.core.config import settings
from app.services.message_processor import MessageProcessor
from app.services.redis_service import RedisService
from app.services.telegram_service import TelegramService

logger = structlog.get_logger()

router = APIRouter(prefix="/telegram", tags=["Telegram Webhook"])

tg_service = TelegramService()
processor = MessageProcessor()


@router.post("/webhook")
async def receive_telegram_update(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """Recibe updates de Telegram y responde con el agente en background.

    Flujo:
    1. Validar secret_token (si configurado).
    2. Parsear update.
    3. Deduplicar por update_id (Redis TTL 5min).
    4. Procesar en background.

    Args:
        request: Request de FastAPI con el body JSON.
        background_tasks: FastAPI BackgroundTasks para procesamiento async.

    Returns:
        Siempre {"status": "ok"} — Telegram necesita 200 para no reintentar.
    """
    # 1. Validar secret_token
    if settings.telegram_webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != settings.telegram_webhook_secret:
            logger.warning("telegram_webhook_invalid_secret")
            raise HTTPException(status_code=403, detail="Secret token inválido")

    # 2. Parsear update
    update = await request.json()
    message_data = tg_service.parse_update(update)
    if not message_data:
        return {"status": "ok"}

    update_id = message_data["update_id"]

    # 3. Deduplicación por update_id (TTL = 5 minutos)
    redis_svc = RedisService()
    dedup_key = f"tg_processed:{update_id}"
    already_processed = await redis_svc.get(dedup_key)
    if already_processed:
        logger.info("telegram_duplicate_skipped", update_id=update_id)
        return {"status": "ok"}

    await redis_svc.set(dedup_key, "1", expire=300)

    # 4. Procesar en background
    background_tasks.add_task(_process_telegram_message, message_data)
    return {"status": "ok"}


async def _process_telegram_message(message_data: dict) -> None:
    """Procesa un mensaje de Telegram: media → texto → agente → respuesta.

    Args:
        message_data: Diccionario con los datos del update parseado.
    """
    chat_id = message_data["chat_id"]
    msg_type = message_data.get("type", "text")
    name = message_data.get("name", "")

    # Prefijo para identificar usuario de Telegram en el historial
    user_id = f"tg:{chat_id}"

    # Procesar según tipo de mensaje
    if msg_type == "audio":
        file_id = message_data.get("file_id", "")
        mime_type = message_data.get("mime_type", "audio/ogg")
        logger.info("telegram_audio_received", chat_id=chat_id, file_id=file_id)

        audio_bytes = await tg_service.download_file(file_id)
        if not audio_bytes:
            await tg_service.send_message(
                to=chat_id, text="⚠️ No pude descargar el audio. Intenta de nuevo."
            )
            return

        from app.services.media_service import MediaService

        text = await MediaService().transcribe_audio(audio_bytes, mime_type)

        if not text:
            await tg_service.send_message(
                to=chat_id, text="⚠️ No pude entender el audio. ¿Puedes escribirlo?"
            )
            return

        logger.info("telegram_audio_transcribed", chat_id=chat_id, text=text[:50])

    elif msg_type == "image":
        file_id = message_data.get("file_id", "")
        mime_type = message_data.get("mime_type", "image/jpeg")
        caption = message_data.get("text", "")
        logger.info("telegram_image_received", chat_id=chat_id, file_id=file_id)

        image_bytes = await tg_service.download_file(file_id)
        if not image_bytes:
            await tg_service.send_message(
                to=chat_id, text="⚠️ No pude descargar la imagen. Intenta de nuevo."
            )
            return

        from app.services.media_service import MediaService

        description = await MediaService().process_image(image_bytes, mime_type)

        if not description:
            await tg_service.send_message(
                to=chat_id,
                text="⚠️ No pude procesar la imagen. ¿Puedes describir lo que ves?",
            )
            return

        text = (
            f"{caption}\n\n[Imagen: {description}]"
            if caption
            else f"[El usuario envió una imagen: {description}]"
        )
        logger.info("telegram_image_processed", chat_id=chat_id, description=description[:50])

    else:
        text = message_data.get("text", "")

    logger.info(
        "telegram_message_received",
        chat_id=chat_id,
        text=text[:50],
        name=name,
        msg_type=msg_type,
    )

    # Delegar al procesador agnóstico
    await processor.process(
        user_id=user_id,
        text=text,
        name=name,
        channel="telegram",
        send_text_fn=_tg_send_text,
        send_image_fn=_tg_send_image,
    )


async def _tg_send_text(to: str, text: str) -> bool:
    """Callback de envío de texto para Telegram.

    Adapta el user_id (tg:{chat_id}) al chat_id real.

    Args:
        to: user_id con prefijo tg:.
        text: Texto a enviar.

    Returns:
        True si se envió correctamente.
    """
    chat_id = to.removeprefix("tg:")
    return await tg_service.send_message(to=chat_id, text=text)


async def _tg_send_image(to: str, image_path: str, caption: str) -> bool:
    """Callback de envío de imagen para Telegram.

    Args:
        to: user_id con prefijo tg:.
        image_path: Ruta local de la imagen.
        caption: Texto descriptivo.

    Returns:
        True si se envió correctamente.
    """
    chat_id = to.removeprefix("tg:")
    return await tg_service.send_image(to=chat_id, image_path=image_path, caption=caption)
