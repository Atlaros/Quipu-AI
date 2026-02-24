"""Router de Inventario — Endpoints REST.

Gestión de stock: consultar, listar, alertas, actualizar.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.api.dependencies import get_db
from app.core.exceptions import (
    DatabaseError,
    ResourceNotFoundError,
    ValidationError,
)
from app.models.inventario import InventarioResponse, InventarioUpdate
from app.repositories.inventario_repository import InventarioRepository
from app.services.inventario_service import InventarioService

router = APIRouter(prefix="/api/v1/inventario", tags=["Inventario"])


def _get_service(db: Client = Depends(get_db)) -> InventarioService:
    """Factory de InventarioService con DI."""
    return InventarioService(repository=InventarioRepository(db=db))


@router.get("/", response_model=list[dict])
async def listar_inventario(
    service: InventarioService = Depends(_get_service),
) -> list[dict]:
    """Lista todo el inventario con datos de producto."""
    try:
        return await service.listar_inventario()
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.get("/alertas", response_model=list[dict])
async def alertas_stock(
    service: InventarioService = Depends(_get_service),
) -> list[dict]:
    """Obtiene productos con stock bajo."""
    try:
        return await service.obtener_alertas_stock()
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.get("/{producto_id}", response_model=InventarioResponse)
async def consultar_stock(
    producto_id: UUID,
    service: InventarioService = Depends(_get_service),
) -> InventarioResponse:
    """Consulta el stock de un producto específico."""
    try:
        return await service.consultar_stock(producto_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.put("/{producto_id}", response_model=InventarioResponse)
async def actualizar_stock(
    producto_id: UUID,
    data: InventarioUpdate,
    service: InventarioService = Depends(_get_service),
) -> InventarioResponse:
    """Actualiza el stock de un producto."""
    try:
        return await service.actualizar_stock(producto_id, data)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc
