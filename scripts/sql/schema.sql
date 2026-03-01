-- ============================================================
-- Quipu AI — Schema de Base de Datos
-- ============================================================
-- Ejecutar en: Supabase Dashboard → SQL Editor → New Query
-- Motor: PostgreSQL 15+ (Supabase managed)
-- ============================================================

-- 0. Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- pgvector se habilita después cuando se necesite búsqueda semántica
-- CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- 1. TABLA: clientes
-- ============================================================
-- Compradores de la bodega. Identificados por teléfono (WhatsApp).
CREATE TABLE IF NOT EXISTS clientes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre      TEXT NOT NULL,
    telefono    TEXT NOT NULL UNIQUE,  -- Identificador natural (WhatsApp)
    direccion   TEXT DEFAULT '',
    notas       TEXT DEFAULT '',       -- Observaciones del bodeguero
    activo      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para búsquedas por teléfono (lookup principal)
CREATE INDEX IF NOT EXISTS idx_clientes_telefono ON clientes (telefono);


-- ============================================================
-- 2. TABLA: productos
-- ============================================================
-- Catálogo de productos de la bodega.
CREATE TABLE IF NOT EXISTS productos (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre          TEXT NOT NULL UNIQUE,
    categoria       TEXT DEFAULT 'General',  -- Ej: Abarrotes, Bebidas, Limpieza
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario > 0),
    unidad_medida   TEXT DEFAULT 'unidad',   -- Ej: kg, litro, unidad, paquete
    activo          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para búsquedas por categoría
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos (categoria);
-- Índice para búsquedas por nombre
CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos (nombre);


-- ============================================================
-- 3. TABLA: inventario
-- ============================================================
-- Stock actual de cada producto. Relación 1:1 con productos.
CREATE TABLE IF NOT EXISTS inventario (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    producto_id      UUID NOT NULL UNIQUE REFERENCES productos(id) ON DELETE CASCADE,
    cantidad_actual  INTEGER NOT NULL DEFAULT 0 CHECK (cantidad_actual >= 0),
    cantidad_minima  INTEGER NOT NULL DEFAULT 5,  -- Umbral para alerta de stock bajo
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para detectar stock bajo rápidamente
CREATE INDEX IF NOT EXISTS idx_inventario_stock_bajo
    ON inventario (cantidad_actual)
    WHERE cantidad_actual <= cantidad_minima;


-- ============================================================
-- 4. TABLA: transacciones
-- ============================================================
-- Registro de ventas y compras de la bodega.
CREATE TABLE IF NOT EXISTS transacciones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    producto_id     UUID NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    cliente_id      UUID REFERENCES clientes(id) ON DELETE SET NULL,  -- NULL = venta anónima
    tipo            TEXT NOT NULL DEFAULT 'venta' CHECK (tipo IN ('venta', 'compra')),
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario > 0),
    monto_total     NUMERIC(10, 2) NOT NULL CHECK (monto_total > 0),
    descripcion     TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para queries frecuentes
CREATE INDEX IF NOT EXISTS idx_transacciones_producto ON transacciones (producto_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_cliente ON transacciones (cliente_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_tipo ON transacciones (tipo);
CREATE INDEX IF NOT EXISTS idx_transacciones_fecha ON transacciones (created_at DESC);


-- ============================================================
-- 5. FUNCIÓN: actualizar updated_at automáticamente
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para auto-actualizar updated_at
CREATE TRIGGER trg_clientes_updated_at
    BEFORE UPDATE ON clientes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_productos_updated_at
    BEFORE UPDATE ON productos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_inventario_updated_at
    BEFORE UPDATE ON inventario
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- 6. ROW LEVEL SECURITY (RLS)
-- ============================================================
-- Para el MVP, habilitamos RLS pero permitimos acceso total via service_role key.
-- En producción se refinarían las policies por usuario autenticado.

ALTER TABLE clientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE productos ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventario ENABLE ROW LEVEL SECURITY;
ALTER TABLE transacciones ENABLE ROW LEVEL SECURITY;

-- Policies: permitir todo para service_role (backend)
CREATE POLICY "Service role full access" ON clientes
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access" ON productos
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access" ON inventario
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access" ON transacciones
    FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- 7. DATOS DE PRUEBA (seed)
-- ============================================================
-- Productos típicos de bodega
INSERT INTO productos (nombre, categoria, precio_unitario, unidad_medida) VALUES
    ('Arroz Extra 1kg',       'Abarrotes', 4.50,  'kg'),
    ('Aceite Vegetal 1L',     'Abarrotes', 8.90,  'litro'),
    ('Azúcar Rubia 1kg',     'Abarrotes', 3.80,  'kg'),
    ('Leche Evaporada 400g', 'Lácteos',   4.20,  'unidad'),
    ('Fideos Spaghetti 500g','Abarrotes', 2.50,  'paquete'),
    ('Atún en Lata 170g',    'Conservas', 5.50,  'unidad'),
    ('Jabón Bolívar 230g',   'Limpieza',  3.20,  'unidad'),
    ('Gaseosa 500ml',        'Bebidas',   2.50,  'unidad'),
    ('Galletas Soda',        'Snacks',    1.80,  'paquete'),
    ('Huevos x10',           'Frescos',   7.50,  'paquete')
ON CONFLICT (nombre) DO NOTHING;

-- Inventario inicial para cada producto
INSERT INTO inventario (producto_id, cantidad_actual, cantidad_minima)
SELECT id, 50, 10 FROM productos
ON CONFLICT (producto_id) DO NOTHING;

-- Clientes de ejemplo
INSERT INTO clientes (nombre, telefono, direccion) VALUES
    ('María García',    '+51999111222', 'Jr. Comercio 123'),
    ('Juan Rodríguez',  '+51999333444', 'Av. Principal 456'),
    ('Rosa López',      '+51999555666', 'Calle Luna 789'),
    ('Carlos Mendoza',  '+51999777888', 'Pasaje Sol 321'),
    ('Ana Torres',      '+51999999000', 'Jr. Estrella 654')
ON CONFLICT (telefono) DO NOTHING;

-- Transacciones de ejemplo
INSERT INTO transacciones (producto_id, cliente_id, tipo, cantidad, precio_unitario, monto_total, descripcion)
SELECT
    p.id,
    c.id,
    'venta',
    3,
    p.precio_unitario,
    p.precio_unitario * 3,
    'Venta de ' || p.nombre || ' x3'
FROM productos p
CROSS JOIN clientes c
WHERE p.nombre = 'Arroz Extra 1kg' AND c.telefono = '+51999111222';


-- ============================================================
-- ✅ Schema listo. Verificar con:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
-- ============================================================
