"""Pydantic models para el recurso Producto.

DTOs para el catálogo de productos de la bodega.
Precios en Decimal (NUMERIC en SQL), nunca float.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductoCreate(BaseModel):
    """Schema para crear un nuevo producto.

    Attributes:
        nombre: Nombre del producto (único en el catálogo).
        categoria: Categoría del producto (Abarrotes, Bebidas, etc.).
        precio_unitario: Precio de venta por unidad.
        unidad_medida: Unidad de medida (kg, litro, unidad, paquete).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nombre": "Zapatillas Nike Air",
                    "categoria": "Ropa y Calzado",
                    "precio_unitario": "250.00",
                    "unidad_medida": "par",
                    "talla": "42",
                    "color": "Blanco",
                    "marca": "Nike",
                }
            ]
        }
    )

    nombre: str = Field(..., min_length=2, max_length=200)
    categoria: str = Field(default="Ropa y Calzado", max_length=100)
    precio_unitario: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    unidad_medida: str = Field(default="unidad", max_length=50)
    talla: str | None = Field(default=None, max_length=20)
    color: str | None = Field(default=None, max_length=50)
    marca: str | None = Field(default=None, max_length=100)


class ProductoResponse(BaseModel):
    """Schema de respuesta para un producto."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    categoria: str
    precio_unitario: Decimal
    unidad_medida: str
    talla: str | None = None
    color: str | None = None
    marca: str | None = None
    activo: bool = True
    created_at: datetime
    updated_at: datetime
