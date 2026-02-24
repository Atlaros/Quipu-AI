"""Unit tests para ProductoService.

Testea lógica de negocio: validación de precio máximo,
detección de duplicados, y operaciones básicas.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import DuplicateResourceError, ValidationError
from app.models.producto import ProductoCreate, ProductoResponse
from app.services.producto_service import ProductoService


@pytest.fixture
def mock_repository() -> MagicMock:
    """Mock del ProductoRepository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_all = AsyncMock()
    repo.get_by_nombre = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repository: MagicMock) -> ProductoService:
    """Instancia del servicio con repository mockeado."""
    return ProductoService(repository=mock_repository)


@pytest.fixture
def sample_producto_data() -> ProductoCreate:
    """Datos de ejemplo para crear un producto."""
    return ProductoCreate(
        nombre="Aceite Primor 1L",
        categoria="Abarrotes",
        precio_unitario=Decimal("12.50"),
        unidad_medida="litro",
    )


@pytest.fixture
def sample_producto_response() -> ProductoResponse:
    """Respuesta de ejemplo de un producto creado."""
    return ProductoResponse(
        id=uuid4(),
        nombre="Aceite Primor 1L",
        categoria="Abarrotes",
        precio_unitario=Decimal("12.50"),
        unidad_medida="litro",
        activo=True,
        created_at="2026-02-15T00:00:00Z",
        updated_at="2026-02-15T00:00:00Z",
    )


class TestCrearProducto:
    """Tests para crear_producto."""

    @pytest.mark.asyncio
    async def test_crear_producto_exitoso(
        self,
        service: ProductoService,
        mock_repository: MagicMock,
        sample_producto_data: ProductoCreate,
        sample_producto_response: ProductoResponse,
    ) -> None:
        """Debe crear un producto cuando no existe duplicado."""
        mock_repository.get_by_nombre.return_value = None
        mock_repository.create.return_value = sample_producto_response

        result = await service.crear_producto(sample_producto_data)

        assert result.nombre == "Aceite Primor 1L"
        assert result.precio_unitario == Decimal("12.50")
        mock_repository.create.assert_called_once_with(sample_producto_data)

    @pytest.mark.asyncio
    async def test_rechazar_nombre_duplicado(
        self,
        service: ProductoService,
        mock_repository: MagicMock,
        sample_producto_data: ProductoCreate,
        sample_producto_response: ProductoResponse,
    ) -> None:
        """Debe rechazar un producto con nombre duplicado."""
        mock_repository.get_by_nombre.return_value = sample_producto_response

        with pytest.raises(DuplicateResourceError):
            await service.crear_producto(sample_producto_data)

        mock_repository.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_rechazar_precio_excesivo(
        self,
        service: ProductoService,
        mock_repository: MagicMock,
    ) -> None:
        """Debe rechazar un producto con precio mayor al máximo."""
        data = ProductoCreate(
            nombre="Producto Caro",
            precio_unitario=Decimal("100000.00"),
        )

        with pytest.raises(ValidationError):
            await service.crear_producto(data)

        mock_repository.create.assert_not_called()


class TestActualizarPrecio:
    """Tests para actualizar_precio."""

    @pytest.mark.asyncio
    async def test_actualizar_precio_exitoso(
        self,
        service: ProductoService,
        mock_repository: MagicMock,
        sample_producto_response: ProductoResponse,
    ) -> None:
        """Debe actualizar el precio de un producto existente."""
        updated = sample_producto_response.model_copy(
            update={"precio_unitario": Decimal("15.00")}
        )
        mock_repository.update.return_value = updated

        result = await service.actualizar_precio(
            sample_producto_response.id, Decimal("15.00")
        )

        assert result.precio_unitario == Decimal("15.00")

    @pytest.mark.asyncio
    async def test_rechazar_precio_negativo(
        self,
        service: ProductoService,
    ) -> None:
        """Debe rechazar un precio menor o igual a 0."""
        with pytest.raises(ValidationError):
            await service.actualizar_precio(uuid4(), Decimal("-5.00"))
