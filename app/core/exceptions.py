"""Excepciones custom del proyecto Quipu AI.

Nunca usar except Exception genérico. Cada capa del sistema
lanza excepciones específicas que se mapean a HTTP status codes
en los routers.
"""


class QuipuBaseError(Exception):
    """Excepción base del proyecto. Todas las custom exceptions heredan de aquí."""

    def __init__(self, message: str = "Error interno del sistema") -> None:
        self.message = message
        super().__init__(self.message)


# --- Errores de Negocio (Service Layer) ---


class ResourceNotFoundError(QuipuBaseError):
    """El recurso solicitado no existe en la base de datos."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(f"{resource} con ID '{resource_id}' no encontrado")
        self.resource = resource
        self.resource_id = resource_id


class DuplicateResourceError(QuipuBaseError):
    """Se intentó crear un recurso que ya existe."""

    def __init__(self, resource: str, field: str, value: str) -> None:
        super().__init__(f"{resource} con {field}='{value}' ya existe")
        self.resource = resource
        self.field = field
        self.value = value


class ValidationError(QuipuBaseError):
    """Error de validación de datos de negocio (no Pydantic)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# --- Errores de Infraestructura (Repository Layer) ---


class DatabaseError(QuipuBaseError):
    """Error de conexión o query a la base de datos."""

    def __init__(self, operation: str, detail: str) -> None:
        super().__init__(f"Error en DB [{operation}]: {detail}")
        self.operation = operation
        self.detail = detail
