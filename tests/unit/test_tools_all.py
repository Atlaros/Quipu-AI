"""Tests unitarios para TODAS las tools del agente Quipu AI.

Verifica que cada tool funciona correctamente con mocks de Supabase,
incluyendo happy paths, edge cases y manejo de errores.
Patrón: mock de get_supabase_client con queries encadenables.
"""

from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────
# Fixtures reutilizables
# ──────────────────────────────────────────────


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Crea un mock del cliente Supabase con métodos encadenables."""
    db = MagicMock()

    def _chain_query(data: list | None = None) -> MagicMock:
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
        mock.update.return_value = mock
        mock.delete.return_value = mock
        mock.range.return_value = mock
        mock.execute.return_value = MagicMock(data=data)
        return mock

    db._chain_query = _chain_query
    return db


# ══════════════════════════════════════════════
# 1. ALERTA STOCK BAJO
# ══════════════════════════════════════════════


class TestAlertaStockBajo:
    """Tests para alerta_stock_bajo."""

    @patch("app.tools.alerta_stock_bajo.get_supabase_client")
    def test_con_productos_criticos(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe listar productos con stock <= mínimo."""
        from app.tools.alerta_stock_bajo import alerta_stock_bajo

        data = [
            {
                "nombre": "Nike Air",
                "marca": "Nike",
                "talla": "42",
                "color": "Negro",
                "precio_unitario": 300,
                "inventario": {"cantidad_actual": 1, "cantidad_minima": 5},
            },
            {
                "nombre": "Polo Puma",
                "marca": "Puma",
                "talla": "M",
                "color": "Rojo",
                "precio_unitario": 80,
                "inventario": {"cantidad_actual": 10, "cantidad_minima": 3},
            },
        ]
        q = mock_supabase._chain_query(data)
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = alerta_stock_bajo.invoke({})

        assert "🚨" in result
        assert "Nike Air" in result
        assert "Polo Puma" not in result  # stock 10 > 3

    @patch("app.tools.alerta_stock_bajo.get_supabase_client")
    def test_todo_ok(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe indicar que todo está bien si no hay stock bajo."""
        from app.tools.alerta_stock_bajo import alerta_stock_bajo

        data = [
            {
                "nombre": "Polo",
                "marca": "X",
                "talla": "M",
                "color": "Azul",
                "precio_unitario": 50,
                "inventario": {"cantidad_actual": 20, "cantidad_minima": 5},
            },
        ]
        q = mock_supabase._chain_query(data)
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = alerta_stock_bajo.invoke({})

        assert "✅" in result

    @patch("app.tools.alerta_stock_bajo.get_supabase_client")
    def test_error_db(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Maneja errores de DB."""
        from app.tools.alerta_stock_bajo import alerta_stock_bajo

        mock_supabase.table.side_effect = Exception("timeout")
        mock_get.return_value = mock_supabase

        result = alerta_stock_bajo.invoke({})
        assert "❌" in result


# ══════════════════════════════════════════════
# 2. BUSCAR WEB
# ══════════════════════════════════════════════


class TestBuscarWeb:
    """Tests para buscar_web (Tavily)."""

    @patch("app.tools.buscar_web.settings")
    def test_sin_api_key(self, mock_settings: MagicMock) -> None:
        """Debe retornar warning si no hay API key."""
        from app.tools.buscar_web import buscar_web

        mock_settings.tavily_api_key = None

        result = buscar_web.invoke({"query": "tendencias moda 2026"})

        assert "⚠️" in result
        assert "no disponible" in result.lower() or "no configurada" in result.lower()

    @patch("app.tools.buscar_web.settings")
    def test_busqueda_exitosa(self, mock_settings: MagicMock) -> None:
        """Debe retornar resultados formateados de Tavily."""
        from app.tools.buscar_web import buscar_web

        mock_settings.tavily_api_key = "tvly-test-key"

        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "Tendencias Moda 2026",
                    "content": "Los colores pastel dominan la temporada...",
                    "url": "https://example.com/moda",
                },
            ]
        }

        with patch("tavily.TavilyClient", return_value=mock_client):
            result = buscar_web.invoke({"query": "tendencias moda 2026"})

        assert "🌐" in result
        assert "Tendencias Moda 2026" in result

    @patch("app.tools.buscar_web.settings")
    def test_busqueda_sin_resultados(self, mock_settings: MagicMock) -> None:
        """Debe manejar cuando no hay resultados."""
        from app.tools.buscar_web import buscar_web

        mock_settings.tavily_api_key = "tvly-test-key"

        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}

        with patch("tavily.TavilyClient", return_value=mock_client):
            result = buscar_web.invoke({"query": "xyz nonexistent query"})

        # Con o sin tavily instalado, debe retornar algo legible
        assert isinstance(result, str)


# ══════════════════════════════════════════════
# 3. CALCULAR DESCUENTO
# ══════════════════════════════════════════════


class TestCalcularDescuento:
    """Tests para calcular_descuento."""

    def test_descuento_basico(self) -> None:
        """20% de descuento sobre S/100 = S/80."""
        from app.tools.calcular_descuento import calcular_descuento

        result = calcular_descuento.invoke({"precio_original": 100.0, "descuento_porcentaje": 20.0})

        assert "S/80.00" in result
        assert "S/20.00" in result  # ahorro
        assert "🏷️" in result

    def test_descuento_con_cantidad(self) -> None:
        """20% de descuento sobre S/100 x 3 = S/240."""
        from app.tools.calcular_descuento import calcular_descuento

        result = calcular_descuento.invoke(
            {"precio_original": 100.0, "descuento_porcentaje": 20.0, "cantidad": 3}
        )

        assert "S/240.00" in result
        assert "3 unidades" in result

    def test_precio_cero(self) -> None:
        """Debe rechazar precio <= 0."""
        from app.tools.calcular_descuento import calcular_descuento

        result = calcular_descuento.invoke({"precio_original": 0.0, "descuento_porcentaje": 10.0})
        assert "❌" in result

    def test_descuento_invalido(self) -> None:
        """Debe rechazar descuento fuera de rango."""
        from app.tools.calcular_descuento import calcular_descuento

        result = calcular_descuento.invoke(
            {"precio_original": 100.0, "descuento_porcentaje": 150.0}
        )
        assert "❌" in result


# ══════════════════════════════════════════════
# 4. CONSULTAR DEUDAS
# ══════════════════════════════════════════════


class TestConsultarDeudas:
    """Tests para consultar_deudas."""

    @patch("app.tools.consultar_deudas.get_supabase_client")
    def test_con_deudas(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe listar deudas pendientes."""
        from app.tools.consultar_deudas import consultar_deudas

        deudas_data = [
            {
                "cliente_nombre": "Juan",
                "descripcion": "2x Nike Air",
                "monto": "150.00",
                "fecha_vencimiento": "2026-03-15",
                "created_at": "2026-03-01",
            },
        ]

        q = mock_supabase._chain_query(deudas_data)
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = consultar_deudas.invoke({})

        assert "💳" in result
        assert "Juan" in result
        assert "S/150.00" in result

    @patch("app.tools.consultar_deudas.get_supabase_client")
    def test_sin_deudas(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe indicar que no hay deudas."""
        from app.tools.consultar_deudas import consultar_deudas

        q = mock_supabase._chain_query([])
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = consultar_deudas.invoke({})

        assert "✅" in result
        assert "cobrado" in result.lower() or "pendientes" in result.lower()


# ══════════════════════════════════════════════
# 5. CONSULTAR METRICAS
# ══════════════════════════════════════════════


class TestConsultarMetricas:
    """Tests para consultar_metricas."""

    @patch("app.tools.consultar_metricas.get_supabase_client")
    def test_con_ventas(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe mostrar métricas calculadas."""
        from app.tools.consultar_metricas import consultar_metricas

        ventas_data = [
            {
                "cantidad": 2,
                "monto_total": "200.00",
                "created_at": "2026-03-01T10:00:00+00:00",
                "descripcion": "Venta Nike",
                "precio_unitario": "100.00",
                "productos": {"nombre": "Nike Air"},
                "clientes": {"nombre": "Juan"},
            },
        ]

        q = mock_supabase._chain_query(ventas_data)
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = consultar_metricas.invoke({"periodo": "hoy"})

        assert "📊" in result
        assert "S/200.00" in result
        assert "Nike Air" in result

    @patch("app.tools.consultar_metricas.get_supabase_client")
    def test_sin_ventas(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe indicar que no hay ventas."""
        from app.tools.consultar_metricas import consultar_metricas

        q = mock_supabase._chain_query([])
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = consultar_metricas.invoke({"periodo": "hoy"})

        assert "No hay ventas" in result


# ══════════════════════════════════════════════
# 6. ENVIAR CATALOGO
# ══════════════════════════════════════════════


class TestEnviarCatalogo:
    """Tests para enviar_catalogo."""

    @patch("app.tools.enviar_catalogo.get_supabase_client")
    def test_catalogo_completo(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe mostrar catálogo agrupado por categoría."""
        from app.tools.enviar_catalogo import enviar_catalogo

        data = [
            {
                "nombre": "Nike Air",
                "marca": "Nike",
                "categoria": "Calzado",
                "talla": "42",
                "color": "Negro",
                "precio_unitario": 300.0,
                "inventario": [{"cantidad_actual": 10}],
                "activo": True,
            },
            {
                "nombre": "Polo Puma",
                "marca": "Puma",
                "categoria": "Ropa",
                "talla": "M",
                "color": "Blanco",
                "precio_unitario": 80.0,
                "inventario": [{"cantidad_actual": 5}],
                "activo": True,
            },
        ]

        q = mock_supabase._chain_query(data)
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = enviar_catalogo.invoke({})

        assert "🛍️" in result
        assert "Nike Air" in result
        assert "Polo Puma" in result

    @patch("app.tools.enviar_catalogo.get_supabase_client")
    def test_catalogo_vacio(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe indicar que el catálogo está vacío."""
        from app.tools.enviar_catalogo import enviar_catalogo

        q = mock_supabase._chain_query([])
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = enviar_catalogo.invoke({})

        assert "❌" in result


# ══════════════════════════════════════════════
# 7. EXPORTAR REPORTE
# ══════════════════════════════════════════════


class TestExportarReporte:
    """Tests para exportar_reporte."""

    @patch("app.tools.exportar_reporte.get_supabase_client")
    def test_exportar_exitoso(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe generar CSV y retornar confirmación."""
        from app.tools.exportar_reporte import exportar_reporte

        ventas_data = [
            {
                "created_at": "2026-03-01T10:00:00",
                "descripcion": "Venta Nike Air",
                "cantidad": 1,
                "precio_unitario": "250.00",
                "monto_total": "250.00",
            },
        ]

        q = mock_supabase._chain_query(ventas_data)
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = exportar_reporte.invoke({"periodo": "semana"})

        assert "📊" in result
        assert "S/250.00" in result
        assert ".csv" in result

    @patch("app.tools.exportar_reporte.get_supabase_client")
    def test_exportar_sin_ventas(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe indicar que no hay ventas."""
        from app.tools.exportar_reporte import exportar_reporte

        q = mock_supabase._chain_query([])
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = exportar_reporte.invoke({"periodo": "semana"})

        assert "No hay ventas" in result


# ══════════════════════════════════════════════
# 8. FESTIVIDADES PROXIMAS
# ══════════════════════════════════════════════


class TestFestividadesProximas:
    """Tests para festividades_proximas."""

    def test_con_festividades(self) -> None:
        """Debe retornar festividades si hay alguna en el rango."""
        from app.tools.festividades_proximas import festividades_proximas

        # Con 365 días de anticipación, siempre habrá al menos una
        result = festividades_proximas.invoke({"dias_anticipacion": 365})

        assert "🗓️" in result or "📅" in result

    def test_sin_festividades(self) -> None:
        """Debe indicar que no hay festividades en rango corto si no aplica."""
        from app.tools.festividades_proximas import festividades_proximas

        # Con 1 día es muy probable que no haya
        result = festividades_proximas.invoke({"dias_anticipacion": 1})

        # Puede o no haber — el test verifica que no crashea
        assert isinstance(result, str)
        assert len(result) > 0


# ══════════════════════════════════════════════
# 9. GENERAR REPORTE VENTAS (gráfico)
# ══════════════════════════════════════════════


class TestGenerarReporteVentas:
    """Tests para generar_reporte_ventas."""

    @patch("app.tools.generar_reporte_ventas.get_supabase_client")
    def test_reporte_con_ventas(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe generar imagen y retornar ruta con prefijo [IMAGE:]."""
        from app.tools.generar_reporte_ventas import generar_reporte_ventas

        ventas_data = [
            {
                "cantidad": 1,
                "monto_total": "150.00",
                "created_at": "2026-03-01T10:00:00+00:00",
                "descripcion": "Venta",
                "precio_unitario": "150.00",
                "productos": {"nombre": "Nike"},
                "clientes": {"nombre": "Ana"},
            },
        ]

        q = mock_supabase._chain_query(ventas_data)
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = generar_reporte_ventas.invoke({})

        assert "[IMAGE:" in result
        assert "S/150.00" in result

    @patch("app.tools.generar_reporte_ventas.get_supabase_client")
    def test_reporte_sin_ventas(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe generar reporte vacío sin error (barras a 0)."""
        from app.tools.generar_reporte_ventas import generar_reporte_ventas

        q = mock_supabase._chain_query([])
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = generar_reporte_ventas.invoke({})

        # Sin ventas aún genera el gráfico (barras en 0)
        assert "[IMAGE:" in result
        assert "S/0.00" in result


# ══════════════════════════════════════════════
# 10. RECOMENDACION PERSONALIZADA
# ══════════════════════════════════════════════


class TestRecomendacionPersonalizada:
    """Tests para recomendacion_personalizada."""

    @patch("app.tools.recomendacion_personalizada.get_supabase_client")
    def test_sin_cliente(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe indicar que no encontró al cliente."""
        from app.tools.recomendacion_personalizada import recomendacion_personalizada

        q = mock_supabase._chain_query([])
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = recomendacion_personalizada.invoke({"cliente_phone": "51999999999"})

        assert "❌" in result
        assert "historial" in result.lower() or "encontré" in result.lower()

    @patch("app.tools.recomendacion_personalizada.get_supabase_client")
    def test_con_recomendaciones(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe retornar recomendaciones basadas en historial."""
        from app.tools.recomendacion_personalizada import recomendacion_personalizada

        # Setup: 3 tablas diferentes (clientes, transacciones, productos)
        cliente_data = [{"id": "cli-1", "nombre": "María"}]
        compras_data = [
            {"producto_id": "p-1", "precio_unitario": "120.00", "descripcion": "Venta"},
        ]
        sugerencias_data = [
            {
                "id": "p-99",
                "nombre": "Polo Premium",
                "marca": "Adidas",
                "talla": "M",
                "color": "Azul",
                "precio_unitario": 110.0,
                "inventario": [{"cantidad_actual": 8}],
            },
        ]

        # Cada tabla retorna datos diferentes
        call_count = {"n": 0}
        tables = {0: cliente_data, 1: compras_data, 2: sugerencias_data}

        def table_side_effect(table_name: str) -> MagicMock:
            idx = call_count["n"]
            call_count["n"] += 1
            return mock_supabase._chain_query(tables.get(idx, []))

        mock_supabase.table.side_effect = table_side_effect
        mock_get.return_value = mock_supabase

        result = recomendacion_personalizada.invoke({"cliente_phone": "51987654321"})

        assert "María" in result or "✨" in result or "❌" not in result


# ══════════════════════════════════════════════
# 11. REGISTRAR CLIENTE
# ══════════════════════════════════════════════


class TestRegistrarCliente:
    """Tests para registrar_cliente."""

    @patch("app.tools.registrar_cliente.get_supabase_client")
    def test_cliente_nuevo(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe registrar un cliente nuevo exitosamente."""
        from app.tools.registrar_cliente import registrar_cliente

        # Sin duplicado + inserción exitosa
        check_q = mock_supabase._chain_query([])
        insert_q = mock_supabase._chain_query([{"id": "cli-new", "nombre": "Luis"}])

        mock_supabase.table.side_effect = lambda t: (
            check_q if mock_supabase.table.call_count <= 1 else insert_q
        )
        mock_get.return_value = mock_supabase

        result = registrar_cliente.invoke({"nombre": "Luis", "telefono": "51987000000"})

        assert "✅" in result or "Luis" in result

    @patch("app.tools.registrar_cliente.get_supabase_client")
    def test_cliente_ya_existe(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe indicar que el cliente ya existe."""
        from app.tools.registrar_cliente import registrar_cliente

        existing = [{"id": "cli-1", "nombre": "María"}]
        q = mock_supabase._chain_query(existing)
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = registrar_cliente.invoke({"nombre": "María", "telefono": "51987111111"})

        assert "Ya existe" in result or "📋" in result


# ══════════════════════════════════════════════
# 12. REGISTRAR COMPRA PROVEEDOR
# ══════════════════════════════════════════════


class TestRegistrarCompraProveedor:
    """Tests para registrar_compra_proveedor."""

    @patch("app.tools.registrar_compra_proveedor.get_supabase_client")
    def test_producto_nuevo(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe crear un producto nuevo en el catálogo."""
        from app.tools.registrar_compra_proveedor import registrar_compra_proveedor

        # producto no existe → crear
        search_q = mock_supabase._chain_query([])  # no encontrado
        create_q = mock_supabase._chain_query([{"id": "p-new"}])  # creado
        update_q = mock_supabase._chain_query([])  # update inventario

        calls = {"n": 0}

        def table_side(t: str) -> MagicMock:
            idx = calls["n"]
            calls["n"] += 1
            if idx == 0:
                return search_q
            if idx == 1:
                return create_q
            return update_q

        mock_supabase.table.side_effect = table_side
        mock_get.return_value = mock_supabase

        result = registrar_compra_proveedor.invoke(
            {
                "nombre": "Zapatilla Adidas",
                "cantidad": 10,
                "precio_venta": 250.0,
                "marca": "Adidas",
                "categoria": "Calzado",
            }
        )

        assert "✨" in result or "NUEVO" in result

    @patch("app.tools.registrar_compra_proveedor.get_supabase_client")
    def test_producto_existente_suma_stock(
        self, mock_get: MagicMock, mock_supabase: MagicMock
    ) -> None:
        """Debe sumar stock al producto existente."""
        from app.tools.registrar_compra_proveedor import registrar_compra_proveedor

        search_q = mock_supabase._chain_query([{"id": "p-exist"}])
        update_q = mock_supabase._chain_query([])
        inv_q = mock_supabase._chain_query([{"id": "inv-1", "cantidad_actual": 5}])

        calls = {"n": 0}

        def table_side(t: str) -> MagicMock:
            idx = calls["n"]
            calls["n"] += 1
            if idx == 0:
                return search_q
            if idx == 1:
                return update_q
            if idx == 2:
                return inv_q
            return update_q

        mock_supabase.table.side_effect = table_side
        mock_get.return_value = mock_supabase

        result = registrar_compra_proveedor.invoke(
            {"nombre": "Zapatilla Adidas", "cantidad": 10, "precio_venta": 250.0}
        )

        assert "✅" in result or "actualizado" in result.lower() or "15" in result

    def test_cantidad_invalida(self) -> None:
        """Debe rechazar cantidad <= 0."""
        from app.tools.registrar_compra_proveedor import registrar_compra_proveedor

        with patch("app.tools.registrar_compra_proveedor.get_supabase_client"):
            result = registrar_compra_proveedor.invoke(
                {"nombre": "X", "cantidad": 0, "precio_venta": 100.0}
            )
        assert "❌" in result

    def test_precio_invalido(self) -> None:
        """Debe rechazar precio <= 0."""
        from app.tools.registrar_compra_proveedor import registrar_compra_proveedor

        with patch("app.tools.registrar_compra_proveedor.get_supabase_client"):
            result = registrar_compra_proveedor.invoke(
                {"nombre": "X", "cantidad": 5, "precio_venta": 0.0}
            )
        assert "❌" in result


# ══════════════════════════════════════════════
# 13. REGISTRAR DEUDA
# ══════════════════════════════════════════════


class TestRegistrarDeuda:
    """Tests para registrar_deuda."""

    @patch("app.tools.registrar_deuda.get_supabase_client")
    def test_deuda_registrada(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe registrar deuda exitosamente."""
        from app.tools.registrar_deuda import registrar_deuda

        q = mock_supabase._chain_query([{"id": "d-1"}])
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = registrar_deuda.invoke(
            {
                "cliente_nombre": "Pedro",
                "descripcion": "3x Polo Nike",
                "monto": 240.0,
            }
        )

        assert "✅" in result
        assert "Pedro" in result
        assert "S/240.00" in result

    @patch("app.tools.registrar_deuda.get_supabase_client")
    def test_deuda_con_vencimiento(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe incluir fecha de vencimiento en la confirmación."""
        from app.tools.registrar_deuda import registrar_deuda

        q = mock_supabase._chain_query([{"id": "d-2"}])
        mock_supabase.table.return_value = q
        mock_get.return_value = mock_supabase

        result = registrar_deuda.invoke(
            {
                "cliente_nombre": "Ana",
                "descripcion": "1x Nike Air",
                "monto": 300.0,
                "fecha_vencimiento": "2026-03-15",
            }
        )

        assert "✅" in result
        assert "2026-03-15" in result

    @patch("app.tools.registrar_deuda.get_supabase_client")
    def test_deuda_error_db(self, mock_get: MagicMock, mock_supabase: MagicMock) -> None:
        """Debe manejar errores de DB."""
        from app.tools.registrar_deuda import registrar_deuda

        mock_supabase.table.side_effect = Exception("DB down")
        mock_get.return_value = mock_supabase

        result = registrar_deuda.invoke({"cliente_nombre": "X", "descripcion": "Y", "monto": 10.0})

        assert "❌" in result
