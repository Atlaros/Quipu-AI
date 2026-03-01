"""Endpoint de chat para interactuar con el agente.

Recibe mensajes de texto y retorna la respuesta del agente LangGraph.
Este endpoint será consumido por el webhook de WhatsApp.
"""

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.graph import agent

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/chat", tags=["Chat / Agente"])


class ChatRequest(BaseModel):
    """Schema de entrada para el chat.

    Attributes:
        message: Mensaje del usuario (texto).
        phone: Teléfono del usuario (para identificar al bodeguero).
    """

    message: str = Field(..., min_length=1, max_length=2000)
    phone: str = Field(default="", description="Teléfono del usuario")


class ChatResponse(BaseModel):
    """Schema de respuesta del chat.

    Attributes:
        response: Respuesta del agente.
        tool_used: Nombre del tool utilizado (si aplica).
    """

    response: str
    tool_used: str | None = None


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Envía un mensaje al agente y retorna su respuesta.

    Args:
        request: Mensaje del usuario.

    Returns:
        Respuesta del agente con tool utilizado (si aplica).
    """
    logger.info("chat_received", message=request.message, phone=request.phone)

    try:
        from langchain_core.messages import HumanMessage

        result = agent.invoke({"messages": [HumanMessage(content=request.message)]})

        # Extraer la última respuesta del agente
        last_message = result["messages"][-1]
        response_text = last_message.content

        # Detectar si se usó un tool
        tool_used = None
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_used = msg.tool_calls[0]["name"]

        logger.info(
            "chat_response_sent",
            tool_used=tool_used,
            response_length=len(response_text),
        )

        return ChatResponse(response=response_text, tool_used=tool_used)

    except Exception as exc:
        logger.error("chat_failed", error=str(exc))
        return ChatResponse(
            response="❌ Hubo un error procesando tu mensaje. Intenta de nuevo.",
            tool_used=None,
        )
