"""Unit tests para ClienteService.

Testea lógica de negocio: validación de duplicados por teléfono.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import DuplicateResourceError
from app.models.cliente import ClienteCreate, ClienteResponse
from app.services.cliente_service import ClienteService


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mock del repositorio de clientes."""
    return AsyncMock()


@pytest.fixture
def service(mock_repo: AsyncMock) -> ClienteService:
    """Servicio con repo mockeado."""
    return ClienteService(repository=mock_repo)


@pytest.fixture
def cliente_data() -> ClienteCreate:
    """Datos válidos para crear un cliente."""
    return ClienteCreate(
        nombre="María García",
        telefono="+51999111222",
        direccion="Jr. Comercio 123",
    )


@pytest.fixture
def cliente_response() -> ClienteResponse:
    """Respuesta esperada de un cliente."""
    return ClienteResponse(
        id=uuid4(),
        nombre="María García",
        telefono="+51999111222",
        direccion="Jr. Comercio 123",
        notas="",
        activo=True,
        created_at="2026-02-14T12:00:00Z",
        updated_at="2026-02-14T12:00:00Z",
    )


class TestRegistrarCliente:
    """Tests para registrar_cliente."""

    @pytest.mark.asyncio
    async def test_crear_cliente_nuevo(
        self,
        service: ClienteService,
        mock_repo: AsyncMock,
        cliente_data: ClienteCreate,
        cliente_response: ClienteResponse,
    ) -> None:
        """Debe crear el cliente cuando el teléfono no existe."""
        mock_repo.get_by_telefono.return_value = None
        mock_repo.create.return_value = cliente_response

        result = await service.registrar_cliente(cliente_data)

        assert result.nombre == "María García"
        mock_repo.get_by_telefono.assert_awaited_once_with("+51999111222")
        mock_repo.create.assert_awaited_once_with(cliente_data)

    @pytest.mark.asyncio
    async def test_rechazar_telefono_duplicado(
        self,
        service: ClienteService,
        mock_repo: AsyncMock,
        cliente_data: ClienteCreate,
        cliente_response: ClienteResponse,
    ) -> None:
        """Debe lanzar DuplicateResourceError si el teléfono ya existe."""
        mock_repo.get_by_telefono.return_value = cliente_response

        with pytest.raises(DuplicateResourceError):
            await service.registrar_cliente(cliente_data)

        mock_repo.create.assert_not_awaited()
