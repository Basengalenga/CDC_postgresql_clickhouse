-- ============================================================================
-- init.sql — PostgreSQL (origen para PeerDB CDC)
-- ============================================================================
-- Requisitos de servidor (fuera de este script, en postgresql.conf):
--   wal_level = logical
--   max_replication_slots >= 4
--   max_wal_senders >= 4
-- (si usas RDS/Cloud SQL, esto se configura via parameter group, no aquí)
--
-- Nota sobre REPLICA IDENTITY: al tener PRIMARY KEY en todas las tablas,
-- Postgres ya usa REPLICA IDENTITY DEFAULT (la PK), suficiente para que
-- PeerDB identifique filas en UPDATE/DELETE. No hace falta REPLICA IDENTITY
-- FULL salvo que quieras ver los valores anteriores completos en cada evento.
-- ============================================================================

-- 1. Customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Menu Items (Tacos y Tortas)
CREATE TABLE IF NOT EXISTS menu_items (
    item_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) CHECK (category IN ('Taco', 'Torta')),
    meat_type VARCHAR(50) CHECK (meat_type IN ('Relleno Negro', 'Cochinita', 'Pavo Asado', 'Castacán')),
    current_price DECIMAL(8, 2) NOT NULL
);

-- 3. Orders
CREATE TABLE IF NOT EXISTS orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'preparing', 'delivering', 'completed', 'canceled')),
    total_amount DECIMAL(10, 2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

-- 4. Order Items
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(8, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES menu_items(item_id) ON DELETE RESTRICT
);

-- Índices operativos (uso normal de Postgres como OLTP)
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- ============================================================================
-- Publication para PeerDB
-- PeerDB lee esta publicación via logical replication (slot + publication).
-- Debe existir ANTES de crear el mirror en PeerDB.
-- ============================================================================
DROP PUBLICATION IF EXISTS peerdb_pub;
CREATE PUBLICATION peerdb_pub FOR TABLE customers, menu_items, orders, order_items;