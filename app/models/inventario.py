"""Pydantic models para el recurso Inventario.

DTOs para control de stock. Relación 1:1 con productos.
Incluye cantidad_minima para alertas de stock bajo.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InventarioUpdate(BaseModel):
    """Schema para actualizar el stock de un producto.

    Attributes:
        cantidad_actual: Nueva cantidad en stock.
        cantidad_minima: Umbral mínimo para alertas.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "cantidad_actual": 45,
                    "cantidad_minima": 10,
                }
            ]
        }
    )

    cantidad_actual: int = Field(..., ge=0, description="Stock actual")
    cantidad_minima: int = Field(default=5, ge=0, description="Umbral de alerta")


class InventarioResponse(BaseModel):
    """Schema de respuesta para inventario, incluye datos del producto."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    producto_id: UUID
    cantidad_actual: int
    cantidad_minima: int
    updated_at: datetime

    @property
    def stock_bajo(self) -> bool:
        """Indica si el stock está por debajo del mínimo.

        Returns:
            True si cantidad_actual <= cantidad_minima.
        """
        return self.cantidad_actual <= self.cantidad_minima
