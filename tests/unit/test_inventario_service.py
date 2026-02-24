"""Unit tests para InventarioService.

Testea lógica de negocio: validación de stock máximo y alertas.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationError
from app.models.inventario import InventarioResponse, InventarioUpdate
from app.services.inventario_service import InventarioService


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mock del repositorio de inventario."""
    return AsyncMock()


@pytest.fixture
def service(mock_repo: AsyncMock) -> InventarioService:
    """Servicio con repo mockeado."""
    return InventarioService(repository=mock_repo)


@pytest.fixture
def producto_id():
    """UUID de producto para tests."""
    return uuid4()


@pytest.fixture
def inventario_response(producto_id) -> InventarioResponse:
    """Respuesta de inventario con stock normal."""
    return InventarioResponse(
        id=uuid4(),
        producto_id=producto_id,
        cantidad_actual=50,
        cantidad_minima=10,
        updated_at="2026-02-14T12:00:00Z",
    )


class TestActualizarStock:
    """Tests para actualizar_stock."""

    @pytest.mark.asyncio
    async def test_actualizar_stock_exitoso(
        self,
        service: InventarioService,
        mock_repo: AsyncMock,
        producto_id,
        inventario_response: InventarioResponse,
    ) -> None:
        """Debe actualizar cantidad cuando es válida."""
        update = InventarioUpdate(cantidad_actual=45, cantidad_minima=10)
        mock_repo.update_stock.return_value = inventario_response

        result = await service.actualizar_stock(producto_id, update)

        assert result.cantidad_actual == 50
        mock_repo.update_stock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rechazar_stock_excesivo(
        self,
        service: InventarioService,
        producto_id,
    ) -> None:
        """Debe lanzar ValidationError si la cantidad excede el máximo."""
        update = InventarioUpdate(cantidad_actual=15_000)

        with pytest.raises(ValidationError, match="excede el máximo"):
            await service.actualizar_stock(producto_id, update)

    @pytest.mark.asyncio
    async def test_alerta_stock_bajo(
        self,
        service: InventarioService,
        mock_repo: AsyncMock,
        producto_id,
    ) -> None:
        """Debe logear warning cuando stock queda bajo."""
        response_bajo = InventarioResponse(
            id=uuid4(),
            producto_id=producto_id,
            cantidad_actual=3,
            cantidad_minima=10,
            updated_at="2026-02-14T12:00:00Z",
        )
        update = InventarioUpdate(cantidad_actual=3)
        mock_repo.update_stock.return_value = response_bajo

        result = await service.actualizar_stock(producto_id, update)

        assert result.stock_bajo is True
