"""Repositorio de Productos — Capa de acceso a datos.

ÚNICA capa que interactúa con Supabase para productos.
Incluye soft delete (activo=False) y búsqueda por nombre.
"""

from uuid import UUID

import structlog
from supabase import Client

from app.core.exceptions import (
    DatabaseError,
    DuplicateResourceError,
    ResourceNotFoundError,
)
from app.models.producto import ProductoCreate, ProductoResponse

logger = structlog.get_logger()


class ProductoRepository:
    """Repositorio para operaciones CRUD de productos en Supabase.

    Attributes:
        db: Cliente de Supabase inyectado via Depends().
    """

    def __init__(self, db: Client) -> None:
        self.db = db
        self._table = "productos"

    async def create(self, producto: ProductoCreate) -> ProductoResponse:
        """Inserta un nuevo producto en la base de datos.

        Args:
            producto: Datos validados del producto a crear.

        Returns:
            El producto creado con ID y timestamps.

        Raises:
            DuplicateResourceError: Si el nombre ya existe.
            DatabaseError: Si falla la inserción.
        """
        payload = {
            "nombre": producto.nombre,
            "categoria": producto.categoria,
            "precio_unitario": str(producto.precio_unitario),
            "unidad_medida": producto.unidad_medida,
            "talla": producto.talla,
            "color": producto.color,
            "marca": producto.marca,
        }

        try:
            response = (
                self.db.table(self._table).insert(payload).execute()
            )
            logger.info("producto_created", producto_id=response.data[0]["id"])
            return ProductoResponse(**response.data[0])

        except Exception as exc:
            error_msg = str(exc)
            if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                raise DuplicateResourceError(
                    resource="Producto",
                    field="nombre",
                    value=producto.nombre,
                ) from exc
            logger.error("producto_create_failed", error=error_msg)
            raise DatabaseError(
                operation="INSERT producto", detail=error_msg
            ) from exc

    async def get_by_id(self, producto_id: UUID) -> ProductoResponse:
        """Obtiene un producto por su ID.

        Args:
            producto_id: UUID del producto.

        Returns:
            El producto encontrado.

        Raises:
            ResourceNotFoundError: Si el producto no existe.
            DatabaseError: Si falla la consulta.
        """
        try:
            response = (
                self.db.table(self._table)
                .select("*")
                .eq("id", str(producto_id))
                .eq("activo", True)
                .execute()
            )

            if not response.data:
                raise ResourceNotFoundError(
                    resource="Producto", resource_id=str(producto_id)
                )

            return ProductoResponse(**response.data[0])

        except ResourceNotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "producto_get_failed",
                producto_id=str(producto_id),
                error=str(exc),
            )
            raise DatabaseError(
                operation="SELECT producto", detail=str(exc)
            ) from exc

    async def get_all(
        self, limit: int = 50, offset: int = 0
    ) -> list[ProductoResponse]:
        """Lista todos los productos activos con paginación.

        Args:
            limit: Máximo de resultados (default 50).
            offset: Desplazamiento para paginación.

        Returns:
            Lista de productos activos.

        Raises:
            DatabaseError: Si falla la consulta.
        """
        try:
            response = (
                self.db.table(self._table)
                .select("*")
                .eq("activo", True)
                .order("nombre")
                .range(offset, offset + limit - 1)
                .execute()
            )
            return [ProductoResponse(**row) for row in response.data]

        except Exception as exc:
            logger.error("productos_list_failed", error=str(exc))
            raise DatabaseError(
                operation="SELECT productos", detail=str(exc)
            ) from exc

    async def get_by_nombre(self, nombre: str) -> ProductoResponse | None:
        """Busca un producto por nombre exacto.

        Args:
            nombre: Nombre del producto a buscar.

        Returns:
            El producto si existe, None si no.
        """
        try:
            response = (
                self.db.table(self._table)
                .select("*")
                .eq("nombre", nombre)
                .eq("activo", True)
                .execute()
            )
            if response.data:
                return ProductoResponse(**response.data[0])
            return None

        except Exception as exc:
            logger.error("producto_get_by_nombre_failed", error=str(exc))
            return None

    async def update(
        self, producto_id: UUID, data: dict
    ) -> ProductoResponse:
        """Actualiza un producto existente.

        Args:
            producto_id: UUID del producto a actualizar.
            data: Campos a actualizar.

        Returns:
            El producto actualizado.

        Raises:
            ResourceNotFoundError: Si el producto no existe.
            DatabaseError: Si falla la actualización.
        """
        # Verificar que existe
        await self.get_by_id(producto_id)

        try:
            response = (
                self.db.table(self._table)
                .update(data)
                .eq("id", str(producto_id))
                .execute()
            )
            return ProductoResponse(**response.data[0])

        except Exception as exc:
            logger.error(
                "producto_update_failed",
                producto_id=str(producto_id),
                error=str(exc),
            )
            raise DatabaseError(
                operation="UPDATE producto", detail=str(exc)
            ) from exc

    async def delete(self, producto_id: UUID) -> None:
        """Soft delete: marca un producto como inactivo.

        Args:
            producto_id: UUID del producto a desactivar.

        Raises:
            ResourceNotFoundError: Si el producto no existe.
            DatabaseError: Si falla la actualización.
        """
        await self.get_by_id(producto_id)

        try:
            self.db.table(self._table).update(
                {"activo": False}
            ).eq("id", str(producto_id)).execute()
            logger.info("producto_deleted", producto_id=str(producto_id))

        except Exception as exc:
            logger.error(
                "producto_delete_failed",
                producto_id=str(producto_id),
                error=str(exc),
            )
            raise DatabaseError(
                operation="DELETE producto", detail=str(exc)
            ) from exc
