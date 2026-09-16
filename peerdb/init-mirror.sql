-- Peer del Postgres origen
CREATE PEER postgres_peer FROM POSTGRES WITH
(
    host = 'postgres',
    port = '5432',
    user = 'admin',
    password = 'admin123',
    database = 'taqueria_don_puerco'
);

-- Peer del ClickHouse destino
CREATE PEER clickhouse_peer FROM CLICKHOUSE WITH
(
    host = 'clickhouse',
    port = 9000,
    user = 'admin',
    password = 'admin123',
    database = 'taqueria_don_puerco',
    disable_tls = true,
    s3_path = 's3://peerdb',
    access_key_id = 'minioadmin',
    secret_access_key = 'minioadmin',
    region = 'us-east-1',
    endpoint = 'http://minio:9000'
);

-- Mirror CDC
CREATE MIRROR IF NOT EXISTS taqueria_cdc
FROM postgres_peer TO clickhouse_peer
WITH TABLE MAPPING
(
  public.customers:customers,
  public.menu_items:menu_items,
  public.orders:orders,
  public.order_items:order_items
)
WITH (
  do_initial_copy = true,
  publication_name = 'peerdb_pub',
  soft_delete = true,
  soft_delete_col_name = '_peerdb_is_deleted'
);