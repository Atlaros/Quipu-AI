-- Migración: Adaptación a Tienda de Ropa y Calzado
-- Autor: Quipu AI Agent
-- Fecha: 2026-02-17

-- 1. Añadir columnas para variantes de productos
ALTER TABLE productos
ADD COLUMN IF NOT EXISTS talla text,
ADD COLUMN IF NOT EXISTS color text,
ADD COLUMN IF NOT EXISTS marca text,
ADD COLUMN IF NOT EXISTS categoria text;

-- 1.1 ELIMINAR restricción de nombre único (Para variantes, el nombre se repite)
ALTER TABLE productos DROP CONSTRAINT IF EXISTS productos_nombre_key;

-- 1.2 Añadir restricción compuesta (Nombre + Talla + Color deben ser únicos)
ALTER TABLE productos ADD CONSTRAINT productos_nombre_talla_color_key UNIQUE (nombre, talla, color);

-- 2. Crear índices para búsquedas rápidas por talla/color/marca
CREATE INDEX IF NOT EXISTS idx_productos_talla ON productos(talla);
CREATE INDEX IF NOT EXISTS idx_productos_color ON productos(color);
CREATE INDEX IF NOT EXISTS idx_productos_marca ON productos(marca);

-- 3. Cargar stock inicial para la Demo
-- OJO: Asegúrate de borrar o truncar la tabla si ya tienes datos basura
-- TRUNCATE TABLE productos CASCADE;

INSERT INTO productos (nombre, marca, talla, color, precio_unitario, categoria) VALUES
('Air Force 1', 'Nike', '42', 'Blanco', 350.00, 'Calzado'),
('Air Force 1', 'Nike', '40', 'Blanco', 350.00, 'Calzado'),
('Superstar', 'Adidas', '38', 'Negro', 320.00, 'Calzado'),
('Polo Básico', 'H&M', 'M', 'Azul', 29.90, 'Ropa'),
('Polo Básico', 'H&M', 'L', 'Azul', 29.90, 'Ropa'),
('Jeans Skinny', 'Zara', '32', 'Azul', 120.00, 'Ropa')
ON CONFLICT (nombre, talla, color) DO NOTHING;

-- Crear inventario inicial (asumiendo que los IDs se autogeneran, esto es tricky en SQL puro sin saber IDs)
-- Mejor crea solo los productos y deja que el inventario se cree manualmente o asume stock por defecto si tu lógica lo soporta.
-- O usa una función/trigger si la tienes.
-- Para esta demo simple, insertamos directo en inventario si conoces los IDs, o lo simulamos.
-- Supongamos que tu sistema ya maneja la creación de inventario al crear producto, o lo haces manual.
-- Si no tienes trigger, ejecuta esto DESPUÉS de ver los IDs o usa un script más complejo.
-- AQUI SIMPLIFICAMOS: La tool 'consultar_inventario' hace un JOIN. Si no hay registro en 'inventario', muestra "Sin registro".
-- RECOMENDACIÓN: Inserta esto manual en Supabase o crea un trigger simple:

CREATE OR REPLACE FUNCTION crear_inventario_inicial()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO inventario (producto_id, cantidad_actual, cantidad_minima)
    VALUES (NEW.id, 10, 2); -- Stock inicial 10 para todos
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_crear_inventario
AFTER INSERT ON productos
FOR EACH ROW
EXECUTE FUNCTION crear_inventario_inicial();

