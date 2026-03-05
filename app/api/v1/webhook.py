"""Webhook de WhatsApp — Recepción de mensajes de Meta.

Dos endpoints:
- GET /webhook: Verificación de Meta (challenge-response).
- POST /webhook: Recibir mensajes, procesarlos con el agente, responder.

Seguridad:
- GET protegido por verify_token (shared secret).
- POST protegido por firma HMAC-SHA256 de Meta (X-Hub-Signature-256).
"""

import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.services.message_processor import MessageProcessor
from app.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger()

router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])

wa_service = WhatsAppService()
processor = MessageProcessor()


def _verify_signature(payload: bytes, signature: str) -> bool:
    """Verifica la firma HMAC-SHA256 enviada por Meta.

    Meta firma cada POST con el app_secret. Si la firma no coincide,
    el request NO viene de Meta y se rechaza.

    Args:
        payload: Body crudo del request (bytes).
        signature: Header X-Hub-Signature-256 (formato: sha256=<hex>).

    Returns:
        True si la firma es válida.
    """
    if not settings.whatsapp_app_secret:
        # Sin app_secret configurado, skip verificación (desarrollo)
        logger.warning("webhook_signature_skip", reason="no_app_secret")
        return True

    if not signature:
        return False

    # Formato: "sha256=<hex_digest>"
    parts = signature.split("=", 1)
    if len(parts) != 2 or parts[0] != "sha256":
        return False

    expected = hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, parts[1])


@router.get("/")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> PlainTextResponse:
    """Verificación del webhook por Meta.

    Meta envía un GET con hub.mode, hub.challenge y hub.verify_token.
    Si el verify_token coincide, respondemos con el challenge.

    Args:
        hub_mode: Debe ser "subscribe".
        hub_challenge: Token de desafío que Meta espera de vuelta.
        hub_verify_token: Token que configuramos en Meta Developer.

    Returns:
        El challenge como texto plano si la verificación es correcta.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("webhook_verified")
        return PlainTextResponse(content=hub_challenge)

    logger.warning(
        "webhook_verification_failed",
        mode=hub_mode,
        token_match=hub_verify_token == settings.whatsapp_verify_token,
    )
    raise HTTPException(status_code=403, detail="Verificación fallida")


@router.post("/")
async def receive_message(request: Request, background_tasks: BackgroundTasks) -> dict:
    """Recibe mensajes de WhatsApp y responde con el agente en background.

    Flujo:
    1. Verificar firma HMAC-SHA256 de Meta.
    2. Deduplicar por message_id (Redis TTL 5min) — ignora reintentos de Meta.
    3. Retornar 200 OK inmediatamente a Meta.
    4. Procesar mensaje + invocar agente + responder en background task.

    Args:
        request: Request de FastAPI con el body JSON.
        background_tasks: FastAPI BackgroundTasks para procesamiento async.

    Returns:
        Siempre {\"status\": \"ok\"} — Meta necesita 200 para no reintentar.
    """
    from app.services.redis_service import RedisService

    # 1. Verificar firma de Meta
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(body, signature):
        logger.warning("webhook_invalid_signature")
        raise HTTPException(status_code=403, detail="Firma inválida")

    # 2. Parsear payload
    payload = json.loads(body)
    message_data = wa_service.parse_message(payload)
    if not message_data:
        return {"status": "ok"}

    message_id = message_data["message_id"]

    # 3. Deduplicación: ignorar reintentos de Meta (TTL = 5 minutos)
    redis_svc = RedisService()
    dedup_key = f"msg_processed:{message_id}"
    already_processed = await redis_svc.get(dedup_key)
    if already_processed:
        logger.info("webhook_duplicate_skipped", message_id=message_id)
        return {"status": "ok"}

    # Marcar como procesado ANTES de encolar (evita race condition)
    await redis_svc.set(dedup_key, "1", expire=300)

    # 4. Encolar procesamiento en background y retornar 200 inmediatamente
    background_tasks.add_task(_process_message, message_data)
    return {"status": "ok"}


async def _process_message(message_data: dict) -> None:
    """Procesa el mensaje de WhatsApp: media → texto → agente → respuesta.

    Se ejecuta en background para no bloquear el webhook y evitar reintentos de Meta.

    Args:
        message_data: Diccionario con los datos del mensaje parseado.
    """
    phone = message_data["phone"]
    msg_type = message_data.get("type", "text")
    message_id = message_data["message_id"]
    name = message_data.get("name", "")

    # Marcar mensaje como leído (doble check azul)
    await wa_service.mark_as_read(message_id)

    # Procesar según tipo de mensaje
    if msg_type == "audio":
        media_id = message_data.get("media_id", "")
        mime_type = message_data.get("mime_type", "audio/ogg")
        logger.info("webhook_audio_received", phone=phone, media_id=media_id)

        audio_bytes = await wa_service.download_media(media_id)
        if not audio_bytes:
            await wa_service.send_message(
                to=phone, text="⚠️ No pude descargar el audio. Intenta de nuevo."
            )
            return

        from app.services.media_service import MediaService

        text = await MediaService().transcribe_audio(audio_bytes, mime_type)

        if not text:
            await wa_service.send_message(
                to=phone, text="⚠️ No pude entender el audio. ¿Puedes escribirlo?"
            )
            return

        logger.info("webhook_audio_transcribed", phone=phone, text=text[:50])

    elif msg_type == "image":
        media_id = message_data.get("media_id", "")
        mime_type = message_data.get("mime_type", "image/jpeg")
        caption = message_data.get("text", "")
        logger.info("webhook_image_received", phone=phone, media_id=media_id)

        image_bytes = await wa_service.download_media(media_id)
        if not image_bytes:
            await wa_service.send_message(
                to=phone, text="⚠️ No pude descargar la imagen. Intenta de nuevo."
            )
            return

        from app.services.media_service import MediaService

        description = await MediaService().process_image(image_bytes, mime_type)

        if not description:
            await wa_service.send_message(
                to=phone, text="⚠️ No pude procesar la imagen. ¿Puedes describir lo que ves?"
            )
            return

        text = (
            f"{caption}\n\n[Imagen: {description}]"
            if caption
            else f"[El usuario envió una imagen: {description}]"
        )
        logger.info("webhook_image_processed", phone=phone, description=description[:50])

    else:
        text = message_data.get("text", "")

    logger.info(
        "webhook_message_received",
        phone=phone,
        text=text[:50],
        name=name,
        msg_type=msg_type,
    )

    # Delegar al procesador agnóstico de canal
    await processor.process(
        user_id=phone,
        text=text,
        name=name,
        channel="whatsapp",
        send_text_fn=_wa_send_text,
        send_image_fn=_wa_send_image,
    )


async def _wa_send_text(to: str, text: str) -> bool:
    """Callback de envío de texto para WhatsApp.

    Args:
        to: Número de teléfono del destinatario.
        text: Texto a enviar.

    Returns:
        True si se envió correctamente.
    """
    return await wa_service.send_message(to=to, text=text)


async def _wa_send_image(to: str, image_path: str, caption: str) -> bool:
    """Callback de envío de imagen para WhatsApp.

    Sube la imagen a la Media API de Meta y luego la envía.

    Args:
        to: Número de teléfono del destinatario.
        image_path: Ruta local de la imagen.
        caption: Texto descriptivo.

    Returns:
        True si se envió correctamente.
    """
    media_id = await wa_service.upload_media(image_path)
    if media_id:
        return await wa_service.send_image(to=to, media_id=media_id, caption=caption)
    return False
