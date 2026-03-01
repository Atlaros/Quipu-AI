"""Pydantic models para el recurso Cliente.

DTOs para crear, leer y responder datos de clientes de la bodega.
El teléfono es el identificador natural (WhatsApp).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClienteCreate(BaseModel):
    """Schema para crear un nuevo cliente.

    Attributes:
        nombre: Nombre completo del cliente.
        telefono: Número de teléfono con código de país (identificador WhatsApp).
        direccion: Dirección física (opcional).
        notas: Observaciones del bodeguero sobre el cliente.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nombre": "María García",
                    "telefono": "+51999111222",
                    "direccion": "Jr. Comercio 123",
                    "notas": "Compra arroz y aceite semanalmente",
                }
            ]
        }
    )

    nombre: str = Field(..., min_length=2, max_length=200)
    telefono: str = Field(..., pattern=r"^\+\d{10,15}$", description="Formato: +51999111222")
    direccion: str = Field(default="", max_length=500)
    notas: str = Field(default="", max_length=1000)


class ClienteResponse(BaseModel):
    """Schema de respuesta para un cliente."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    telefono: str
    direccion: str = ""
    notas: str = ""
    activo: bool = True
    created_at: datetime
    updated_at: datetime
