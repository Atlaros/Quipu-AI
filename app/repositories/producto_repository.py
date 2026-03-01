"""Repositorio de Productos — Capa de acceso a datos.

ÚNICA capa que interactúa con Supabase para productos.
Incluye soft delete (activo=False) y búsqueda por nombre.
"""

from uuid import UUID

import structlog
from postgrest.exceptions import APIError
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
        self._columns = (
            "id, nombre, categoria, precio_unitario, "
            "unidad_medida, talla, color, marca, activo, created_at, updated_at"
        )

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
            response = self.db.table(self._table).insert(payload).execute()
            logger.info("producto_created", producto_id=response.data[0]["id"])
            return ProductoResponse(**response.data[0])

        except APIError as exc:
            error_msg = str(exc)
            if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                raise DuplicateResourceError(
                    resource="Producto",
                    field="nombre",
                    value=producto.nombre,
                ) from exc
            logger.error("producto_create_failed", error=error_msg)
            raise DatabaseError(operation="INSERT producto", detail=error_msg) from exc

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
                .select(self._columns)
                .eq("id", str(producto_id))
                .eq("activo", True)
                .execute()
            )

            if not response.data:
                raise ResourceNotFoundError(resource="Producto", resource_id=str(producto_id))

            return ProductoResponse(**response.data[0])

        except ResourceNotFoundError:
            raise
        except APIError as exc:
            logger.error(
                "producto_get_failed",
                producto_id=str(producto_id),
                error=str(exc),
            )
            raise DatabaseError(operation="SELECT producto", detail=str(exc)) from exc

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[ProductoResponse]:
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
                .select(self._columns)
                .eq("activo", True)
                .order("nombre")
                .range(offset, offset + limit - 1)
                .execute()
            )
            return [ProductoResponse(**row) for row in response.data]

        except APIError as exc:
            logger.error("productos_list_failed", error=str(exc))
            raise DatabaseError(operation="SELECT productos", detail=str(exc)) from exc

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
                .select(self._columns)
                .eq("nombre", nombre)
                .eq("activo", True)
                .execute()
            )
            if response.data:
                return ProductoResponse(**response.data[0])
            return None

        except APIError as exc:
            logger.error("producto_get_by_nombre_failed", error=str(exc))
            return None

    async def update(self, producto_id: UUID, data: dict) -> ProductoResponse:
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
            response = self.db.table(self._table).update(data).eq("id", str(producto_id)).execute()
            return ProductoResponse(**response.data[0])

        except APIError as exc:
            logger.error(
                "producto_update_failed",
                producto_id=str(producto_id),
                error=str(exc),
            )
            raise DatabaseError(operation="UPDATE producto", detail=str(exc)) from exc

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
            self.db.table(self._table).update({"activo": False}).eq(
                "id", str(producto_id)
            ).execute()
            logger.info("producto_deleted", producto_id=str(producto_id))

        except APIError as exc:
            logger.error(
                "producto_delete_failed",
                producto_id=str(producto_id),
                error=str(exc),
            )
            raise DatabaseError(operation="DELETE producto", detail=str(exc)) from exc

    async def buscar_por_nombre_variante(
        self,
        nombre: str,
        talla: str = "",
        color: str = "",
    ) -> ProductoResponse | None:
        """Busca un producto por nombre/marca con filtros de variante.

        Args:
            nombre: Nombre o marca del producto.
            talla: Talla a filtrar (opcional).
            color: Color a filtrar (opcional).

        Returns:
            El producto encontrado o None.
        """
        try:
            query = (
                self.db.table(self._table)
                .select("id, nombre, precio_unitario, talla, color, marca")
                .or_(f"nombre.ilike.%{nombre}%,marca.ilike.%{nombre}%")
            )
            if talla:
                query = query.eq("talla", talla)
            if color:
                query = query.ilike("color", color)

            result = query.limit(1).execute()
            if not result.data:
                return None
            return ProductoResponse(
                **{
                    **result.data[0],
                    "activo": True,
                    "created_at": "2000-01-01",
                    "updated_at": "2000-01-01",
                    "categoria": "",
                    "unidad_medida": "",
                }
            )
        except APIError as exc:
            logger.error("producto_buscar_variante_failed", error=str(exc))
            return None

    async def buscar_catalogo(
        self,
        categoria: str = "",
        limit: int = 15,
    ) -> list[dict]:
        """Lista productos con stock para catálogo.

        Args:
            categoria: Filtro de categoría/nombre/marca.
            limit: Máximo de resultados.

        Returns:
            Lista de dicts con datos de producto + inventario.
        """
        try:
            query = self.db.table(self._table).select(
                "nombre, marca, talla, color, precio_unitario, inventario(cantidad_actual)"
            )
            if categoria:
                query = query.or_(f"nombre.ilike.%{categoria}%,marca.ilike.%{categoria}%")
            result = query.limit(limit).execute()
            return result.data if result.data else []
        except APIError as exc:
            logger.error("producto_buscar_catalogo_failed", error=str(exc))
            raise DatabaseError(operation="SELECT catalogo", detail=str(exc)) from exc
