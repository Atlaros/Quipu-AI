"""Router de Clientes — Endpoints REST.

CRUD de clientes con validación por teléfono (WhatsApp).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.dependencies import get_db
from app.core.exceptions import (
    DatabaseError,
    DuplicateResourceError,
    ResourceNotFoundError,
)
from app.models.cliente import ClienteCreate, ClienteResponse
from app.repositories.cliente_repository import ClienteRepository
from app.services.cliente_service import ClienteService

router = APIRouter(prefix="/api/v1/clientes", tags=["Clientes"])


def _get_service(db: Client = Depends(get_db)) -> ClienteService:
    """Factory de ClienteService con DI."""
    return ClienteService(repository=ClienteRepository(db=db))


@router.post("/", response_model=ClienteResponse, status_code=201)
async def crear_cliente(
    cliente: ClienteCreate,
    service: ClienteService = Depends(_get_service),
) -> ClienteResponse:
    """Registra un nuevo cliente."""
    try:
        return await service.registrar_cliente(cliente)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.get("/", response_model=list[ClienteResponse])
async def listar_clientes(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ClienteService = Depends(_get_service),
) -> list[ClienteResponse]:
    """Lista clientes activos con paginación."""
    try:
        return await service.listar_clientes(limit=limit, offset=offset)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.get("/{cliente_id}", response_model=ClienteResponse)
async def obtener_cliente(
    cliente_id: UUID,
    service: ClienteService = Depends(_get_service),
) -> ClienteResponse:
    """Obtiene un cliente por su ID."""
    try:
        return await service.obtener_cliente(cliente_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.delete("/{cliente_id}", status_code=204)
async def eliminar_cliente(
    cliente_id: UUID,
    service: ClienteService = Depends(_get_service),
) -> None:
    """Desactiva un cliente (soft delete)."""
    try:
        await service.eliminar_cliente(cliente_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
