"""Procesador de mensajes agnóstico al canal.

Contiene la lógica compartida entre WhatsApp y Telegram:
carga historial, invoca al agente, guarda resultado, responde vía callback.
"""

from collections.abc import Awaitable, Callable

import structlog

from app.agent.graph import agent
from app.repositories.conversation_repository import ConversationRepository
from app.services.redis_service import redis_service

logger = structlog.get_logger()

# Tipos de callback para envío de respuestas
SendTextFn = Callable[[str, str], Awaitable[bool]]
SendImageFn = Callable[[str, str, str], Awaitable[bool]]


class MessageProcessor:
    """Procesa mensajes de cualquier canal y responde vía callbacks.

    Centraliza la lógica: historial → agente → respuesta, sin acoplarse
    a ningún canal específico (WhatsApp, Telegram, etc.).
    """

    def __init__(self) -> None:
        self.conversation_repo = ConversationRepository(redis=redis_service)

    async def process(
        self,
        *,
        user_id: str,
        text: str,
        name: str = "",
        channel: str = "unknown",
        send_text_fn: SendTextFn,
        send_image_fn: SendImageFn,
    ) -> None:
        """Procesa un mensaje de texto, invoca al agente, y responde.

        Args:
            user_id: Identificador único del usuario (phone o tg:{chat_id}).
            text: Texto del mensaje (ya transcrito si era audio).
            name: Nombre del usuario (si disponible).
            channel: Canal de origen ("whatsapp" o "telegram").
            send_text_fn: Callback async(to, text) → bool para enviar texto.
            send_image_fn: Callback async(to, path, caption) → bool para enviar imagen.
        """
        logger.info(
            "message_processor_start",
            user_id=user_id,
            channel=channel,
            text=text[:50],
            name=name,
        )

        try:
            from langchain_core.messages import AIMessage, HumanMessage

            history = await self.conversation_repo.get_history(user_id)
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
                    part.get("text", "")
                    for part in last_msg.content
                    if isinstance(part, dict) and "text" in part
                )
            else:
                response_text = str(last_msg.content)

            await self.conversation_repo.save_message(user_id, "human", text)
            await self.conversation_repo.save_message(user_id, "ai", response_text)

        except Exception as exc:
            logger.error("message_processor_agent_failed", error=str(exc), channel=channel)
            response_text = (
                "⚠️ Hubo un problema procesando tu mensaje. Intenta de nuevo en unos segundos."
            )

        # Enviar respuesta (texto o imagen)
        await self._send_response(
            user_id=user_id,
            response_text=response_text,
            send_text_fn=send_text_fn,
            send_image_fn=send_image_fn,
        )

    async def _send_response(
        self,
        *,
        user_id: str,
        response_text: str,
        send_text_fn: SendTextFn,
        send_image_fn: SendImageFn,
    ) -> None:
        """Envía la respuesta al usuario, detectando si es texto o imagen.

        Args:
            user_id: Identificador único del usuario.
            response_text: Texto de respuesta del agente.
            send_text_fn: Callback para enviar texto.
            send_image_fn: Callback para enviar imagen.
        """
        if response_text.startswith("[IMAGE:"):
            try:
                end_idx = response_text.find("]")
                if end_idx != -1:
                    image_path = response_text[7:end_idx]
                    caption = response_text[end_idx + 1 :].strip()
                else:
                    image_path = response_text.replace("[IMAGE:", "")
                    caption = ""

                sent = await send_image_fn(user_id, image_path, caption)
                if not sent:
                    await send_text_fn(user_id, caption or response_text)
            except (ValueError, OSError) as exc:
                logger.error("message_processor_image_send_failed", error=str(exc))
                await send_text_fn(user_id, response_text)
        else:
            await send_text_fn(user_id, response_text)
