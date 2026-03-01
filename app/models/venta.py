"""Pydantic models para el recurso Venta.

Define los DTOs (Data Transfer Objects) para crear, leer y responder
transacciones de venta. Usa Decimal para valores monetarios.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VentaCreate(BaseModel):
    """Schema para crear una nueva venta.

    Attributes:
        producto_id: ID del producto vendido.
        cliente_id: ID del cliente que compró (opcional para ventas anónimas).
        cantidad: Unidades vendidas (mínimo 1).
        precio_unitario: Precio por unidad en moneda local (Decimal, no float).
        descripcion: Descripción libre de la venta.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "producto_id": "550e8400-e29b-41d4-a716-446655440000",
                    "cliente_id": "660e8400-e29b-41d4-a716-446655440001",
                    "cantidad": 5,
                    "precio_unitario": "12.50",
                    "descripcion": "Arroz Premium 1kg x5",
                }
            ]
        }
    )

    producto_id: UUID
    cliente_id: UUID | None = None
    tipo: str = Field(
        default="venta", pattern=r"^(venta|compra)$", description="Tipo: venta o compra"
    )
    cantidad: int = Field(..., gt=0, description="Cantidad vendida (mínimo 1)")
    precio_unitario: Decimal = Field(
        ..., gt=0, max_digits=10, decimal_places=2, description="Precio unitario"
    )
    descripcion: str = Field(default="", max_length=500, description="Descripción de la venta")

    @property
    def monto_total(self) -> Decimal:
        """Calcula el monto total de la venta.

        Returns:
            Cantidad * precio_unitario.
        """
        return self.cantidad * self.precio_unitario


class VentaResponse(BaseModel):
    """Schema de respuesta para una venta.

    Attributes:
        id: ID único de la venta en la base de datos.
        producto_id: ID del producto vendido.
        cliente_id: ID del cliente (None si fue venta anónima).
        cantidad: Unidades vendidas.
        precio_unitario: Precio por unidad.
        monto_total: Total calculado (cantidad * precio_unitario).
        descripcion: Descripción de la venta.
        created_at: Timestamp de creación.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    producto_id: UUID
    cliente_id: UUID | None = None
    tipo: str = "venta"
    cantidad: int
    precio_unitario: Decimal
    monto_total: Decimal
    descripcion: str = ""
    created_at: datetime
