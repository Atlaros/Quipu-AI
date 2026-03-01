"""Tests unitarios para el tool registrar_venta.

Verifica los flujos principales: venta exitosa, producto no
encontrado, y venta con cliente.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_supabase():
    """Crea un mock del cliente Supabase con métodos encadenables."""
    db = MagicMock()

    def _chain_query(data=None):
        """Helper para crear mocks de queries encadenables de Supabase."""
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.or_.return_value = mock
        mock.ilike.return_value = mock
        mock.gte.return_value = mock
        mock.lte.return_value = mock
        mock.limit.return_value = mock
        mock.order.return_value = mock
        mock.insert.return_value = mock
        mock.execute.return_value = MagicMock(data=data)
        return mock

    db._chain_query = _chain_query
    return db


class TestRegistrarVenta:
    """Tests para el tool registrar_venta."""

    @patch("app.tools.registrar_venta.get_supabase_client")
    def test_venta_exitosa(self, mock_get_client, mock_supabase):
        """Test que una venta exitosa retorna confirmación."""
        from app.tools.registrar_venta import registrar_venta

        # Setup: producto encontrado
        producto_data = [
            {
                "id": "prod-123",
                "nombre": "Nike Air Max",
                "precio_unitario": 250.0,
                "talla": "42",
                "color": "Negro",
            }
        ]

        # Mock encadenado para la query de productos
        productos_query = mock_supabase._chain_query(producto_data)
        # Mock para la inserción de transacción
        insert_query = mock_supabase._chain_query([{"id": "venta-1"}])

        mock_supabase.table.side_effect = lambda t: (
            productos_query if t == "productos" else insert_query
        )
        mock_get_client.return_value = mock_supabase

        result = registrar_venta.invoke({"producto_nombre": "Nike", "cantidad": 2})

        assert "✅ Venta registrada" in result
        assert "Nike Air Max" in result
        assert "S/500.00" in result

    @patch("app.tools.registrar_venta.get_supabase_client")
    def test_producto_no_encontrado(self, mock_get_client, mock_supabase):
        """Test que retorna error cuando el producto no existe."""
        from app.tools.registrar_venta import registrar_venta

        # Setup: ningún producto encontrado
        empty_query = mock_supabase._chain_query([])
        mock_supabase.table.return_value = empty_query
        mock_get_client.return_value = mock_supabase

        result = registrar_venta.invoke({"producto_nombre": "ProductoInexistente", "cantidad": 1})

        assert "❌" in result
        assert "ProductoInexistente" in result

    @patch("app.tools.registrar_venta.get_supabase_client")
    def test_venta_con_error_db(self, mock_get_client, mock_supabase):
        """Test que maneja errores de base de datos correctamente."""
        from app.tools.registrar_venta import registrar_venta

        mock_supabase.table.side_effect = Exception("Connection refused")
        mock_get_client.return_value = mock_supabase

        result = registrar_venta.invoke({"producto_nombre": "Nike", "cantidad": 1})

        assert "❌" in result
        assert "Error" in result
