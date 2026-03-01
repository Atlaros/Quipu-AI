"""Tests para ConversationRepository.

Verifica get_history y save_message con mocks de Supabase.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from postgrest.exceptions import APIError


class TestConversationRepository:
    """Tests para el repositorio de conversaciones."""

    @pytest.fixture
    def mock_db(self) -> MagicMock:
        """Mock de Supabase client."""
        return MagicMock()

    @pytest.fixture
    def repo(self, mock_db: MagicMock) -> Any:
        """Instancia de repository con DB mockeada."""
        with patch(
            "app.repositories.conversation_repository.get_supabase_client",
            return_value=mock_db,
        ):
            from app.repositories.conversation_repository import (
                ConversationRepository,
            )

            return ConversationRepository()

    @pytest.mark.asyncio
    async def test_get_history_retorna_mensajes_ordenados(
        self, repo: Any, mock_db: MagicMock
    ) -> None:
        """get_history retorna mensajes en orden cronológico."""
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"role": "ai", "content": "¡Hola!", "created_at": "2026-02-15T20:01:00Z"},
            {"role": "human", "content": "cuánto arroz", "created_at": "2026-02-15T20:00:00Z"},
        ]

        history = await repo.get_history("59160891791")

        # Debe invertir el orden (más antiguo primero)
        assert len(history) == 2
        assert history[0]["role"] == "human"
        assert history[1]["role"] == "ai"

    @pytest.mark.asyncio
    async def test_get_history_vacio(self, repo: Any, mock_db: MagicMock) -> None:
        """get_history retorna lista vacía si no hay historial."""
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        history = await repo.get_history("59199999999")

        assert history == []

    @pytest.mark.asyncio
    async def test_get_history_error_retorna_vacio(self, repo: Any, mock_db: MagicMock) -> None:
        """get_history no falla si Supabase lanza error."""
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = APIError(
            {"message": "DB error", "code": "500", "details": "", "hint": ""}
        )

        history = await repo.get_history("59160891791")

        assert history == []

    @pytest.mark.asyncio
    async def test_save_message_exitoso(self, repo: Any, mock_db: MagicMock) -> None:
        """save_message inserta correctamente en Supabase."""
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock()

        # No debe lanzar excepción
        await repo.save_message("59160891791", "human", "vendí 3 arroz")

        mock_db.table.assert_called_with("conversaciones")

    @pytest.mark.asyncio
    async def test_save_message_error_no_falla(self, repo: Any, mock_db: MagicMock) -> None:
        """save_message no falla si Supabase lanza error."""
        mock_db.table.return_value.insert.return_value.execute.side_effect = APIError(
            {"message": "DB error", "code": "500", "details": "", "hint": ""}
        )

        # No debe lanzar excepción
        await repo.save_message("59160891791", "ai", "Respuesta del agente")
