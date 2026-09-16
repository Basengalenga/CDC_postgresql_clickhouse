-- ============================================================================
-- init.sql — ClickHouse (destino del mirror CDC de PeerDB)
-- ============================================================================
-- IMPORTANTE: si dejas que PeerDB cree las tablas automáticamente al iniciar
-- el mirror (comportamiento por defecto, CREATE TABLE IF NOT EXISTS), este
-- script es redundante. Pre-créalas tú mismo solo si quieres:
--   a) un ORDER BY distinto a la sola PK (mejor rendimiento en tus queries), o
--   b) engine distribuido/replicado (SharedReplacingMergeTree en Cloud, etc.)
-- Si pre-creas, la PK original de Postgres SIEMPRE debe ir al final del
-- ORDER BY, para que la deduplicación funcione bien.
--
-- Tipos: category/meat_type/status se mapean como String (no Enum8), porque
-- así es como PeerDB los infiere desde VARCHAR de Postgres. Si migras esas
-- columnas a Enum8 luego, hazlo en una materialized view derivada, no en la
-- tabla que recibe el CDC directo.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS taqueria_don_puerco;
USE taqueria_don_puerco;

-- 1. Customers
CREATE TABLE IF NOT EXISTS customers
(
    customer_id        Int32,
    name                String,
    phone               String,
    created_at          DateTime64(6),
    _peerdb_synced_at   DateTime64(9) DEFAULT now64(),
    _peerdb_is_deleted  Int8,
    _peerdb_version     Int64
)
ENGINE = ReplacingMergeTree(_peerdb_version)
PRIMARY KEY customer_id
ORDER BY customer_id;

-- 2. Menu Items
CREATE TABLE IF NOT EXISTS menu_items
(
    item_id             Int32,
    name                String,
    category            String,
    meat_type           String,
    current_price       Decimal(8, 2),
    _peerdb_synced_at   DateTime64(9) DEFAULT now64(),
    _peerdb_is_deleted  Int8,
    _peerdb_version     Int64
)
ENGINE = ReplacingMergeTree(_peerdb_version)
PRIMARY KEY item_id
ORDER BY item_id;

-- 3. Orders
CREATE TABLE IF NOT EXISTS orders
(
    order_id            Int32,
    customer_id         Int32,
    status              String,
    total_amount        Decimal(10, 2),
    created_at          DateTime64(6),
    _peerdb_synced_at   DateTime64(9) DEFAULT now64(),
    _peerdb_is_deleted  Int8,
    _peerdb_version     Int64
)
ENGINE = ReplacingMergeTree(_peerdb_version)
PRIMARY KEY order_id
ORDER BY order_id; 

-- 4. Order Items
CREATE TABLE IF NOT EXISTS order_items
(
    order_item_id       Int32,
    order_id            Int32,
    item_id             Int32,
    quantity            Int32,
    unit_price          Decimal(8, 2),
    _peerdb_synced_at   DateTime64(9) DEFAULT now64(),
    _peerdb_is_deleted  Int8,
    _peerdb_version     Int64
)
ENGINE = ReplacingMergeTree(_peerdb_version)
PRIMARY KEY order_item_id
ORDER BY order_item_id;

-- ============================================================================
-- Row policies para ocultar filas borradas automáticamente en SELECT
-- (sin esto, tienes que acordarte de filtrar _peerdb_is_deleted = 0 siempre)
-- "TO admin" es explícito: sin un target, ClickHouse no garantiza a qué
-- usuario se aplica el policy. Ajusta "admin" si tu dashboard usa otro user.
-- ============================================================================
CREATE ROW POLICY IF NOT EXISTS hide_deleted_customers ON customers FOR SELECT USING _peerdb_is_deleted = 0 TO admin;
CREATE ROW POLICY IF NOT EXISTS hide_deleted_menu_items ON menu_items FOR SELECT USING _peerdb_is_deleted = 0 TO admin;
CREATE ROW POLICY IF NOT EXISTS hide_deleted_orders ON orders FOR SELECT USING _peerdb_is_deleted = 0 TO admin;
CREATE ROW POLICY IF NOT EXISTS hide_deleted_order_items ON order_items FOR SELECT USING _peerdb_is_deleted = 0 TO admin;