"""Router de Productos — Endpoints CRUD del catálogo.

Endpoints para gestionar el catálogo de productos de la bodega.
Incluye creación, consulta, actualización de precio y soft delete.
"""

from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import get_supabase_client
from app.core.exceptions import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ValidationError,
)
from app.models.producto import ProductoCreate, ProductoResponse
from app.repositories.producto_repository import ProductoRepository
from app.services.producto_service import ProductoService

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/productos", tags=["Productos"])


# --- Dependency Injection ---


def _get_service() -> ProductoService:
    """Factory para inyectar ProductoService con su repository."""
    db = get_supabase_client()
    repository = ProductoRepository(db)
    return ProductoService(repository)


# --- Request Models ---


class PrecioUpdate(BaseModel):
    """Schema para actualizar el precio de un producto."""

    precio_unitario: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)


# --- Endpoints ---


@router.post("/", response_model=ProductoResponse, status_code=201)
async def crear_producto(
    data: ProductoCreate,
    service: ProductoService = Depends(_get_service),
) -> ProductoResponse:
    """Crea un nuevo producto en el catálogo.

    Args:
        data: Datos del producto a crear.
        service: Servicio inyectado.

    Returns:
        El producto creado.
    """
    try:
        return await service.crear_producto(data)

    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/", response_model=list[ProductoResponse])
async def listar_productos(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ProductoService = Depends(_get_service),
) -> list[ProductoResponse]:
    """Lista todos los productos activos con paginación.

    Args:
        limit: Máximo de resultados por página.
        offset: Desplazamiento para paginación.
        service: Servicio inyectado.

    Returns:
        Lista de productos activos.
    """
    return await service.listar_productos(limit=limit, offset=offset)


@router.get("/{producto_id}", response_model=ProductoResponse)
async def obtener_producto(
    producto_id: UUID,
    service: ProductoService = Depends(_get_service),
) -> ProductoResponse:
    """Obtiene un producto por su ID.

    Args:
        producto_id: UUID del producto.
        service: Servicio inyectado.

    Returns:
        El producto encontrado.
    """
    try:
        return await service.obtener_producto(producto_id)

    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{producto_id}/precio", response_model=ProductoResponse)
async def actualizar_precio(
    producto_id: UUID,
    data: PrecioUpdate,
    service: ProductoService = Depends(_get_service),
) -> ProductoResponse:
    """Actualiza el precio de un producto.

    Args:
        producto_id: UUID del producto.
        data: Nuevo precio.
        service: Servicio inyectado.

    Returns:
        El producto con precio actualizado.
    """
    try:
        return await service.actualizar_precio(producto_id, data.precio_unitario)

    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{producto_id}", status_code=204)
async def eliminar_producto(
    producto_id: UUID,
    service: ProductoService = Depends(_get_service),
) -> None:
    """Elimina un producto del catálogo (soft delete).

    Args:
        producto_id: UUID del producto a eliminar.
        service: Servicio inyectado.
    """
    try:
        await service.eliminar_producto(producto_id)

    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
