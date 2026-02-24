"""Unit tests para VentaService.

Testea la lógica de negocio aislada del repositorio (mockeado).
No necesita conexión a Supabase.
"""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ValidationError
from app.models.venta import VentaCreate, VentaResponse
from app.services.venta_service import VentaService


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Crea un mock del repositorio de ventas."""
    return AsyncMock()


@pytest.fixture
def service(mock_repository: AsyncMock) -> VentaService:
    """Crea un servicio con el repositorio mockeado."""
    return VentaService(repository=mock_repository)


@pytest.fixture
def venta_create() -> VentaCreate:
    """Fixture de datos válidos para crear una venta."""
    return VentaCreate(
        producto_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        cliente_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        cantidad=5,
        precio_unitario=Decimal("12.50"),
        descripcion="Arroz Premium 1kg x5",
    )


@pytest.fixture
def venta_response() -> VentaResponse:
    """Fixture de respuesta esperada de una venta."""
    return VentaResponse(
        id=uuid4(),
        producto_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        cliente_id=UUID("660e8400-e29b-41d4-a716-446655440001"),
        cantidad=5,
        precio_unitario=Decimal("12.50"),
        monto_total=Decimal("62.50"),
        descripcion="Arroz Premium 1kg x5",
        created_at="2026-02-14T12:00:00",
    )


class TestRegistrarVenta:
    """Tests para el método registrar_venta."""

    @pytest.mark.asyncio
    async def test_registrar_venta_exitosa(
        self,
        service: VentaService,
        mock_repository: AsyncMock,
        venta_create: VentaCreate,
        venta_response: VentaResponse,
    ) -> None:
        """Debe crear la venta cuando los datos son válidos."""
        mock_repository.create.return_value = venta_response

        result = await service.registrar_venta(venta_create)

        assert result == venta_response
        mock_repository.create.assert_awaited_once_with(venta_create)

    @pytest.mark.asyncio
    async def test_registrar_venta_monto_excede_maximo(
        self,
        service: VentaService,
    ) -> None:
        """Debe lanzar ValidationError si el monto excede el máximo."""
        venta_cara = VentaCreate(
            producto_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            cantidad=1000,
            precio_unitario=Decimal("100.00"),
            descripcion="Compra masiva",
        )
        # 1000 * 100 = 100,000 > 50,000 (máximo)
        with pytest.raises(ValidationError, match="excede el máximo"):
            await service.registrar_venta(venta_cara)


class TestObtenerVenta:
    """Tests para el método obtener_venta."""

    @pytest.mark.asyncio
    async def test_obtener_venta_existente(
        self,
        service: VentaService,
        mock_repository: AsyncMock,
        venta_response: VentaResponse,
    ) -> None:
        """Debe retornar la venta cuando existe."""
        mock_repository.get_by_id.return_value = venta_response
        venta_id = venta_response.id

        result = await service.obtener_venta(venta_id)

        assert result.id == venta_id
        mock_repository.get_by_id.assert_awaited_once_with(venta_id)


class TestListarVentas:
    """Tests para el método listar_ventas."""

    @pytest.mark.asyncio
    async def test_listar_ventas_con_paginacion(
        self,
        service: VentaService,
        mock_repository: AsyncMock,
        venta_response: VentaResponse,
    ) -> None:
        """Debe retornar lista de ventas con paginación."""
        mock_repository.get_all.return_value = [venta_response]

        result = await service.listar_ventas(limit=10, offset=0)

        assert len(result) == 1
        mock_repository.get_all.assert_awaited_once_with(limit=10, offset=0)

    @pytest.mark.asyncio
    async def test_listar_ventas_vacio(
        self,
        service: VentaService,
        mock_repository: AsyncMock,
    ) -> None:
        """Debe retornar lista vacía cuando no hay ventas."""
        mock_repository.get_all.return_value = []

        result = await service.listar_ventas()

        assert result == []
