import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import clickhouse_connect
import plotly.express as px
from streamlit_echarts import st_echarts
from streamlit_autorefresh import st_autorefresh

# 1. Configuración de página (Debe ser lo primero)
st.set_page_config(page_title="Comando Taquería", page_icon="🌮", layout="wide", initial_sidebar_state="collapsed")

# 2. Configurar el Autorefresco (Cada 2 segundos = 2000 ms)
count = st_autorefresh(interval=2000, limit=None, key="taqueria_refresh")

# 3. Caché de Conexiones
@st.cache_resource
def get_pg_engine():
    # Conexión Postgres usando SQLAlchemy (Elimina el warning de Pandas)
    return create_engine("postgresql+psycopg://admin:admin123@postgres:5432/taqueria_don_puerco")

@st.cache_resource
def get_ch_client():
    # Conexión ClickHouse
    return clickhouse_connect.get_client(
        host='clickhouse',
        port=8123,
        username='admin',
        password='admin123',
        database='taqueria_don_puerco'
    )

pg_engine = get_pg_engine()

# 4. Funciones de extracción de datos
def fetch_data_pg(query):
    """Extrae datos de PostgreSQL"""
    with pg_engine.connect() as conn:
        return pd.read_sql(query, conn)

def fetch_data_ch(query):
    """Extrae datos de ClickHouse y devuelve un DataFrame de pandas"""
    client = get_ch_client()
    return client.query_df(query)

# --- INTERFAZ GRÁFICA: ENCABEZADO PODEROSO ---
col_logo, col_texto = st.columns([1, 4], vertical_alignment="center")

with col_logo:
    st.image("el_tio.png", use_container_width=True)

with col_texto:
    st.title("🌮 Centro de Comando: Taquería Don Poc chuc norris")
    st.markdown("### Monitor de operaciones en tiempo real")

st.markdown("---")

# 5. Función que renderiza el dashboard
def render_dashboard(fetch_func, tab_key):
    is_clickhouse = (tab_key == "clickhouse")

    # --- EXTRACCIÓN DE DATOS CON PROTECCIÓN ---
    try:
        if is_clickhouse:
            # ClickHouse usa ReplacingMergeTree: FINAL fuerza la deduplicación
            # en tiempo de lectura, y filtramos _peerdb_is_deleted como respaldo
            # (independiente de si el row policy en ClickHouse ya lo hace).
            df_kpi = fetch_func("""
                SELECT COUNT(*) as total_orders, COALESCE(SUM(total_amount), 0) as total_revenue
                FROM orders FINAL
                WHERE _peerdb_is_deleted = 0
            """)
            df_status = fetch_func("""
                SELECT status, COUNT(*) as count
                FROM orders FINAL
                WHERE _peerdb_is_deleted = 0
                GROUP BY status
            """)
            query_sunburst = """
                SELECT m.category, m.meat_type, SUM(oi.quantity) as sold_qty, SUM(oi.quantity * oi.unit_price) as revenue
                FROM order_items oi FINAL
                JOIN menu_items m FINAL ON oi.item_id = m.item_id
                WHERE oi._peerdb_is_deleted = 0
                GROUP BY m.category, m.meat_type
            """
        else:
            df_kpi = fetch_func("SELECT COUNT(*) as total_orders, COALESCE(SUM(total_amount), 0) as total_revenue FROM orders")
            df_status = fetch_func("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
            query_sunburst = """
                SELECT m.category, m.meat_type, SUM(oi.quantity) as sold_qty, SUM(oi.quantity * oi.unit_price) as revenue
                FROM order_items oi
                JOIN menu_items m ON oi.item_id = m.item_id
                GROUP BY m.category, m.meat_type
            """

        df_sunburst = fetch_func(query_sunburst)

    except Exception as e:
        # Si PeerDB aún no replica las tablas, mostramos un aviso en vez de crashear
        st.warning(f"Esperando sincronización de base de datos... ({e})")
        return

    # --- PROCESAMIENTO ---
    # Validación por si las tablas existen pero aún están vacías
    if (df_kpi.empty or 
        pd.isna(df_kpi['total_orders'].iloc[0]) or 
        df_kpi['total_orders'].iloc[0] == 0):
        
        st.info("Base de datos lista. Esperando a que el generador envíe las primeras órdenes...")
        return

    total_orders = df_kpi['total_orders'].iloc[0]
    total_revenue = float(df_kpi['total_revenue'].iloc[0])

    status_dict = dict(zip(df_status['status'], df_status['count']))
    pending = status_dict.get('pending', 0)
    preparing = status_dict.get('preparing', 0)
    delivering = status_dict.get('delivering', 0)
    completed = status_dict.get('completed', 0)
    canceled = status_dict.get('canceled', 0)

    cocina_load = pending + preparing

    # --- RENDERIZADO DEL DASHBOARD ---
    # Fila 1: KPIs Rápidos
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Órdenes Totales", f"{total_orders:,}")
    col2.metric("Ingresos (MXN)", f"${total_revenue:,.2f}")
    col3.metric("Fuego en Cocina (Pendientes)", cocina_load, delta=f"{pending} en cola, {preparing} al fuego", delta_color="inverse")
    col4.metric("Entregados / Completados", completed)

    st.markdown("---")

    # Fila 2: Gráficas
    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        st.subheader("🌋 Termómetro de Estrés (Cocina)")
        gauge_options = {
            "tooltip": {"formatter": "{a} <br/>{b} : {c}"},
            "series": [{
                "name": "Órdenes Activas",
                "type": "gauge",
                "max": 1000,
                "progress": {"show": True},
                "detail": {"valueAnimation": True, "formatter": "{value}"},
                "axisLine": {
                    "lineStyle": {
                        "width": 20,
                        "color": [[0.3, '#67e0e3'], [0.7, '#37a2da'], [1, '#fd666d']]
                    }
                },
                "data": [{"value": cocina_load, "name": "Órdenes en Cocina"}]
            }]
        }
        st_echarts(options=gauge_options, height="400px", key=f"gauge_{tab_key}")

    with col_der:
        st.subheader("🌪 Anatomía de las Ventas (Sunburst)")
        if not df_sunburst.empty:
            fig_sunburst = px.sunburst(
                df_sunburst,
                path=['category', 'meat_type'],
                values='revenue',
                color='meat_type',
                color_discrete_map={
                    'Relleno Negro': '#1c1c1c',
                    'Cochinita': '#d9534f',
                    'Pavo Asado': '#f0ad4e',
                    'Castacán': '#8b4513'
                },
                hover_data=['sold_qty']
            )
            fig_sunburst.update_layout(margin=dict(t=0, l=0, r=0, b=0))
            st.plotly_chart(fig_sunburst, key=f"sunburst_{tab_key}")
        else:
            st.info("Esperando ventas para graficar...")

    st.markdown("---")

    # Fila 3: Funnel de Conversión de Órdenes
    st.subheader("🚰 Embudo de Operaciones")
    funnel_data = pd.DataFrame([
        {"Estado": "1. Pendiente", "Volumen": pending},
        {"Estado": "2. Preparando", "Volumen": preparing},
        {"Estado": "3. En Camino", "Volumen": delivering},
        {"Estado": "4. Completado", "Volumen": completed}
    ])

    fig_funnel = px.funnel(funnel_data, x='Volumen', y='Estado', color='Estado')
    fig_funnel.update_layout(showlegend=False, margin=dict(t=0, b=0))
    st.plotly_chart(fig_funnel, key=f"funnel_{tab_key}")


# 6. Creación de las pestañas
tab_pg, tab_ch = st.tabs(["🐘 PostgreSQL", "🚀 ClickHouse"])

with tab_pg:
    render_dashboard(fetch_data_pg, tab_key="postgres")

with tab_ch:
    render_dashboard(fetch_data_ch, tab_key="clickhouse")