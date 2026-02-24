"""Fixtures compartidas para todos los tests.

Define factories de datos y mocks reutilizables.
Todos los archivos de test importan estas fixtures automáticamente.
"""

import pytest


@pytest.fixture
def sample_venta_data() -> dict:
    """Fixture con datos de ejemplo para una venta.

    Returns:
        Diccionario con campos válidos de una venta.
    """
    return {
        "producto_id": "550e8400-e29b-41d4-a716-446655440000",
        "cliente_id": "660e8400-e29b-41d4-a716-446655440001",
        "cantidad": 5,
        "precio_unitario": "12.50",
        "descripcion": "Arroz Premium 1kg x5",
    }
