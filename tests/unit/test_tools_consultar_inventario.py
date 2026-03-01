"""Tests unitarios para el tool consultar_inventario.

Verifica los flujos principales: inventario con productos,
inventario vacío, y filtros de talla/color.
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
        mock.limit.return_value = mock
        mock.execute.return_value = MagicMock(data=data)
        return mock

    db._chain_query = _chain_query
    return db


class TestConsultarInventario:
    """Tests para el tool consultar_inventario."""

    @patch("app.tools.consultar_inventario.get_supabase_client")
    def test_inventario_con_productos(self, mock_get_client, mock_supabase):
        """Test que retorna inventario formateado con productos disponibles."""
        from app.tools.consultar_inventario import consultar_inventario

        productos_data = [
            {
                "nombre": "Zapatilla Nike",
                "marca": "Nike",
                "talla": "42",
                "color": "Negro",
                "precio_unitario": 299.90,
                "inventario": {
                    "cantidad_actual": 15,
                    "cantidad_minima": 5,
                },
            },
            {
                "nombre": "Polo Adidas",
                "marca": "Adidas",
                "talla": "M",
                "color": "Blanco",
                "precio_unitario": 89.90,
                "inventario": {
                    "cantidad_actual": 3,
                    "cantidad_minima": 5,
                },
            },
        ]

        query_mock = mock_supabase._chain_query(productos_data)
        mock_supabase.table.return_value = query_mock
        mock_get_client.return_value = mock_supabase

        result = consultar_inventario.invoke({})

        assert "📦 **Inventario Disponible:**" in result
        assert "Zapatilla Nike" in result
        assert "15 und." in result
        assert "⚠️ STOCK BAJO" in result  # Polo Adidas tiene 3 <= 5

    @patch("app.tools.consultar_inventario.get_supabase_client")
    def test_inventario_vacio(self, mock_get_client, mock_supabase):
        """Test que retorna mensaje cuando no hay productos."""
        from app.tools.consultar_inventario import consultar_inventario

        query_mock = mock_supabase._chain_query([])
        mock_supabase.table.return_value = query_mock
        mock_get_client.return_value = mock_supabase

        result = consultar_inventario.invoke({"producto_nombre": "ProductoInexistente"})

        assert "❌" in result
        assert "ProductoInexistente" in result

    @patch("app.tools.consultar_inventario.get_supabase_client")
    def test_inventario_con_filtros(self, mock_get_client, mock_supabase):
        """Test que aplica filtros de talla y color correctamente."""
        from app.tools.consultar_inventario import consultar_inventario

        productos_data = [
            {
                "nombre": "Air Force 1",
                "marca": "Nike",
                "talla": "42",
                "color": "Blanco",
                "precio_unitario": 450.0,
                "inventario": [{"cantidad_actual": 8, "cantidad_minima": 3}],
            },
        ]

        query_mock = mock_supabase._chain_query(productos_data)
        mock_supabase.table.return_value = query_mock
        mock_get_client.return_value = mock_supabase

        result = consultar_inventario.invoke(
            {"producto_nombre": "Air Force", "talla": "42", "color": "Blanco"}
        )

        assert "Air Force 1" in result
        assert "8 und." in result
        # Verify eq and ilike were called for filters
        query_mock.eq.assert_called()
        query_mock.ilike.assert_called()

    @patch("app.tools.consultar_inventario.get_supabase_client")
    def test_inventario_lista_format(self, mock_get_client, mock_supabase):
        """Test que maneja el formato de inventario como lista (1-a-muchos)."""
        from app.tools.consultar_inventario import consultar_inventario

        productos_data = [
            {
                "nombre": "Jean Levi's",
                "marca": "Levi's",
                "talla": "32",
                "color": "Azul",
                "precio_unitario": 189.90,
                "inventario": [{"cantidad_actual": 20, "cantidad_minima": 5}],
            },
        ]

        query_mock = mock_supabase._chain_query(productos_data)
        mock_supabase.table.return_value = query_mock
        mock_get_client.return_value = mock_supabase

        result = consultar_inventario.invoke({})

        assert "Jean Levi's" in result
        assert "20 und." in result

    @patch("app.tools.consultar_inventario.get_supabase_client")
    def test_inventario_error_db(self, mock_get_client, mock_supabase):
        """Test que maneja errores de base de datos."""
        from app.tools.consultar_inventario import consultar_inventario

        mock_supabase.table.side_effect = Exception("DB timeout")
        mock_get_client.return_value = mock_supabase

        result = consultar_inventario.invoke({})

        assert "❌" in result
        assert "Error" in result
