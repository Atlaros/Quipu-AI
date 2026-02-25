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

from app.agent.graph import agent
from app.core.config import settings
from app.repositories.conversation_repository import ConversationRepository
from app.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger()

router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])

wa_service = WhatsAppService()
conversation_repo = ConversationRepository()


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
    """Procesa el mensaje, invoca el agente y envía la respuesta por WhatsApp.

    Se ejecuta en background para no bloquear el webhook y evitar reintentos de Meta.

    Args:
        message_data: Diccionario con los datos del mensaje parseado.
    """
    phone = message_data["phone"]
    msg_type = message_data.get("type", "text")
    message_id = message_data["message_id"]
    name = message_data.get("name", "")

    # Marcar mensaje como leído
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

        text = f"{caption}\n\n[Imagen: {description}]" if caption else f"[El usuario envió una imagen: {description}]"
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

    try:
        from langchain_core.messages import AIMessage, HumanMessage

        history = await conversation_repo.get_history(phone)
        messages: list = []
        for msg in history:
            if msg["role"] == "human":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=text))

        result = agent.invoke({"messages": messages})

        last_msg = result["messages"][-1]
        if isinstance(last_msg.content, str):
            response_text = last_msg.content
        elif isinstance(last_msg.content, list):
            response_text = " ".join(
                part.get("text", "") for part in last_msg.content
                if isinstance(part, dict) and "text" in part
            )
        else:
            response_text = str(last_msg.content)

        await conversation_repo.save_message(phone, "human", text)
        await conversation_repo.save_message(phone, "ai", response_text)

    except Exception as exc:
        logger.error("webhook_agent_failed", error=str(exc))
        response_text = (
            "⚠️ Hubo un problema procesando tu mensaje. "
            "Intenta de nuevo en unos segundos."
        )

    # Enviar respuesta (texto o imagen)
    if response_text.startswith("[IMAGE:"):
        try:
            end_idx = response_text.find("]")
            if end_idx != -1:
                image_path = response_text[7:end_idx]
                caption = response_text[end_idx + 1:].strip()
            else:
                image_path = response_text.replace("[IMAGE:", "")
                caption = ""

            media_id = await wa_service.upload_media(image_path)
            if media_id:
                await wa_service.send_image(to=phone, media_id=media_id, caption=caption)
            else:
                await wa_service.send_message(to=phone, text=caption or response_text)
        except (ValueError, OSError) as exc:
            logger.error("webhook_image_send_failed", error=str(exc))
            await wa_service.send_message(to=phone, text=response_text)
    else:
        await wa_service.send_message(to=phone, text=response_text)

