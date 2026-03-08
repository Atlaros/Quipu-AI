"""Unit tests para MessageProcessor.

Testea la lógica de procesamiento agnóstica al canal.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.message_processor import MessageProcessor


@pytest.fixture
def processor() -> MessageProcessor:
    """Instancia del procesador de mensajes."""
    return MessageProcessor()


@pytest.fixture
def mock_send_text() -> AsyncMock:
    """Callback mock para envío de texto."""
    return AsyncMock(return_value=True)


@pytest.fixture
def mock_send_image() -> AsyncMock:
    """Callback mock para envío de imagen."""
    return AsyncMock(return_value=True)


class TestSendResponse:
    """Tests para _send_response (lógica de envío)."""

    @pytest.mark.asyncio
    async def test_enviar_texto_simple(
        self,
        processor: MessageProcessor,
        mock_send_text: AsyncMock,
        mock_send_image: AsyncMock,
    ) -> None:
        """Debe llamar send_text_fn para respuestas de texto."""
        await processor._send_response(
            user_id="123",
            response_text="¡Hola! ¿En qué te ayudo?",
            send_text_fn=mock_send_text,
            send_image_fn=mock_send_image,
        )

        mock_send_text.assert_called_once_with("123", "¡Hola! ¿En qué te ayudo?")
        mock_send_image.assert_not_called()

    @pytest.mark.asyncio
    async def test_enviar_imagen(
        self,
        processor: MessageProcessor,
        mock_send_text: AsyncMock,
        mock_send_image: AsyncMock,
    ) -> None:
        """Debe llamar send_image_fn para respuestas con [IMAGE:...]."""
        await processor._send_response(
            user_id="123",
            response_text="[IMAGE:/tmp/reporte.png] Aquí está tu reporte",
            send_text_fn=mock_send_text,
            send_image_fn=mock_send_image,
        )

        mock_send_image.assert_called_once_with("123", "/tmp/reporte.png", "Aquí está tu reporte")
        mock_send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_a_texto_si_imagen_falla(
        self,
        processor: MessageProcessor,
        mock_send_text: AsyncMock,
    ) -> None:
        """Si send_image_fn retorna False, debe enviar texto como fallback."""
        mock_send_image_fail = AsyncMock(return_value=False)

        await processor._send_response(
            user_id="123",
            response_text="[IMAGE:/tmp/fail.png] Reporte",
            send_text_fn=mock_send_text,
            send_image_fn=mock_send_image_fail,
        )

        mock_send_image_fail.assert_called_once()
        mock_send_text.assert_called_once_with("123", "Reporte")


class TestProcess:
    """Tests para process (flujo completo)."""

    @pytest.mark.asyncio
    async def test_procesa_texto_y_llama_agente(
        self,
        processor: MessageProcessor,
        mock_send_text: AsyncMock,
        mock_send_image: AsyncMock,
    ) -> None:
        """Debe cargar historial, invocar agente, guardar y responder."""
        mock_response = MagicMock()
        mock_response.content = "¡Tenemos Nike Air en talla 42! ¿Te lo separo?"

        with (
            patch.object(
                processor.conversation_repo,
                "get_history",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                processor.conversation_repo,
                "save_message",
                new_callable=AsyncMock,
            ) as mock_save,
            patch("app.services.message_processor.agent") as mock_agent,
        ):
            mock_agent.invoke.return_value = {"messages": [mock_response]}

            await processor.process(
                user_id="tg:123456",
                text="¿Hay Nike Air en 42?",
                name="María",
                channel="telegram",
                send_text_fn=mock_send_text,
                send_image_fn=mock_send_image,
            )

            # Verificar que se invocó el agente
            mock_agent.invoke.assert_called_once()

            # Verificar que se guardaron ambos mensajes
            assert mock_save.call_count == 2
            mock_save.assert_any_call("tg:123456", "human", "¿Hay Nike Air en 42?")
            mock_save.assert_any_call(
                "tg:123456", "ai", "¡Tenemos Nike Air en talla 42! ¿Te lo separo?"
            )

            # Verificar que se envió la respuesta
            mock_send_text.assert_called_once_with(
                "tg:123456", "¡Tenemos Nike Air en talla 42! ¿Te lo separo?"
            )

    @pytest.mark.asyncio
    async def test_error_agente_envia_mensaje_disculpa(
        self,
        processor: MessageProcessor,
        mock_send_text: AsyncMock,
        mock_send_image: AsyncMock,
    ) -> None:
        """Si el agente falla, debe enviar un mensaje de error amigable."""
        with (
            patch.object(
                processor.conversation_repo,
                "get_history",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.services.message_processor.agent") as mock_agent,
        ):
            mock_agent.invoke.side_effect = RuntimeError("LLM unavailable")

            await processor.process(
                user_id="51999111222",
                text="Hola",
                name="Test",
                channel="whatsapp",
                send_text_fn=mock_send_text,
                send_image_fn=mock_send_image,
            )

            # Debe enviar mensaje de error
            mock_send_text.assert_called_once()
            error_msg = mock_send_text.call_args[0][1]
            assert "⚠️" in error_msg
            assert "problema" in error_msg

    @pytest.mark.asyncio
    async def test_carga_historial_previo(
        self,
        processor: MessageProcessor,
        mock_send_text: AsyncMock,
        mock_send_image: AsyncMock,
    ) -> None:
        """Debe cargar y pasar el historial al agente."""
        history = [
            {"role": "human", "content": "Hola"},
            {"role": "ai", "content": "¡Hola! ¿En qué te ayudo?"},
        ]

        mock_response = MagicMock()
        mock_response.content = "Respuesta del agente"

        with (
            patch.object(
                processor.conversation_repo,
                "get_history",
                new_callable=AsyncMock,
                return_value=history,
            ),
            patch.object(
                processor.conversation_repo,
                "save_message",
                new_callable=AsyncMock,
            ),
            patch("app.services.message_processor.agent") as mock_agent,
        ):
            mock_agent.invoke.return_value = {"messages": [mock_response]}

            await processor.process(
                user_id="tg:999",
                text="¿Qué tienen?",
                channel="telegram",
                send_text_fn=mock_send_text,
                send_image_fn=mock_send_image,
            )

            # Verificar que el agente recibió historial + nuevo mensaje (3 msgs)
            call_args = mock_agent.invoke.call_args[0][0]
            assert len(call_args["messages"]) == 3
