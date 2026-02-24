"""Router de Ventas — Endpoints REST para el recurso venta.

Solo recibe requests y delega al service. No contiene lógica de negocio.
Todos los endpoints usan response_model tipado y Dependency Injection.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.dependencies import get_db
from app.core.exceptions import (
    DatabaseError,
    ResourceNotFoundError,
    ValidationError,
)
from app.models.venta import VentaCreate, VentaResponse
from app.repositories.venta_repository import VentaRepository
from app.services.venta_service import VentaService

router = APIRouter(prefix="/api/v1/ventas", tags=["Ventas"])


def _get_service(db: Client = Depends(get_db)) -> VentaService:
    """Factory de VentaService con inyección de dependencias.

    Args:
        db: Cliente Supabase inyectado.

    Returns:
        Instancia del servicio de ventas.
    """
    repository = VentaRepository(db=db)
    return VentaService(repository=repository)


@router.post("/", response_model=VentaResponse, status_code=201)
async def crear_venta(
    venta: VentaCreate,
    service: VentaService = Depends(_get_service),
) -> VentaResponse:
    """Registra una nueva venta.

    Args:
        venta: Datos de la venta a crear.
        service: Servicio de ventas inyectado.

    Returns:
        La venta creada con ID y timestamp.
    """
    try:
        return await service.registrar_venta(venta)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.get("/", response_model=list[VentaResponse])
async def listar_ventas(
    limit: int = Query(default=50, ge=1, le=100, description="Máximo de resultados"),
    offset: int = Query(default=0, ge=0, description="Desplazamiento"),
    service: VentaService = Depends(_get_service),
) -> list[VentaResponse]:
    """Lista ventas con paginación.

    Args:
        limit: Máximo de resultados (1-100).
        offset: Desplazamiento para paginación.
        service: Servicio de ventas inyectado.

    Returns:
        Lista de ventas ordenadas por fecha descendente.
    """
    try:
        return await service.listar_ventas(limit=limit, offset=offset)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.get("/{venta_id}", response_model=VentaResponse)
async def obtener_venta(
    venta_id: UUID,
    service: VentaService = Depends(_get_service),
) -> VentaResponse:
    """Obtiene una venta por su ID.

    Args:
        venta_id: UUID de la venta.
        service: Servicio de ventas inyectado.

    Returns:
        La venta encontrada.
    """
    try:
        return await service.obtener_venta(venta_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc


@router.delete("/{venta_id}", status_code=204)
async def eliminar_venta(
    venta_id: UUID,
    service: VentaService = Depends(_get_service),
) -> None:
    """Elimina una venta por su ID.

    Args:
        venta_id: UUID de la venta a eliminar.
        service: Servicio de ventas inyectado.
    """
    try:
        await service.eliminar_venta(venta_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc
