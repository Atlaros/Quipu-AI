-- Script de corrección de stock
-- Autor: Quipu AI Agent
-- Fecha: 2026-02-17

-- 1. Insertar stock (10 unidades) para cualquier producto que NO tenga registro en inventario
INSERT INTO inventario (producto_id, cantidad_actual, cantidad_minima)
SELECT id, 10, 2
FROM productos
WHERE id NOT IN (SELECT producto_id FROM inventario);

-- 2. Asegurar que los productos existentes tengan stock positivo (por si acaso tenían 0)
UPDATE inventario
SET cantidad_actual = 10, cantidad_minima = 2
WHERE cantidad_actual = 0;

-- 3. Verificación rápida
SELECT p.nombre, p.marca, p.talla, i.cantidad_actual 
FROM productos p
JOIN inventario i ON p.id = i.producto_id;
