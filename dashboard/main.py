import streamlit as st
import pandas as pd
import psycopg
from psycopg_pool import ConnectionPool
import plotly.express as px
from streamlit_echarts import st_echarts
from streamlit_autorefresh import st_autorefresh

# 1. Configuración de página (Debe ser lo primero)
st.set_page_config(page_title="Comando Taquería", page_icon="🌮", layout="wide", initial_sidebar_state="collapsed")

# 2. Configurar el Autorefresco (Cada 2 segundos = 2000 ms)
count = st_autorefresh(interval=2000, limit=None, key="taqueria_refresh")

# 3. Caché del Pool de Conexiones
# Usamos st.cache_resource para no abrir un pool nuevo cada 2 segundos
@st.cache_resource
def get_pool():
    # Asegúrate de usar 'postgres' si corre en Docker, o 'localhost' si corre fuera
    DSN = "dbname=taqueria_don_puerco user=admin password=admin123 host=postgres port=5432"
    return ConnectionPool(DSN, min_size=2, max_size=10)

pool = get_pool()

# 4. Funciones de extracción de datos
def fetch_data(query):
    with pool.connection() as conn:
        return pd.read_sql(query, conn)

# --- EXTRACCIÓN DE DATOS ---
# KPI Generales
df_kpi = fetch_data("SELECT COUNT(*) as total_orders, COALESCE(SUM(total_amount), 0) as total_revenue FROM orders")
# Estado de órdenes (Para el Funnel y el Gauge)
df_status = fetch_data("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
# Popularidad (Para el Sunburst)
query_sunburst = """
    SELECT m.category, m.meat_type, SUM(oi.quantity) as sold_qty, SUM(oi.quantity * oi.unit_price) as revenue
    FROM order_items oi
    JOIN menu_items m ON oi.item_id = m.item_id
    GROUP BY m.category, m.meat_type
"""
df_sunburst = fetch_data(query_sunburst)

# --- PROCESAMIENTO ---
total_orders = df_kpi['total_orders'].iloc[0]
total_revenue = float(df_kpi['total_revenue'].iloc[0])

status_dict = dict(zip(df_status['status'], df_status['count']))
pending = status_dict.get('pending', 0)
preparing = status_dict.get('preparing', 0)
delivering = status_dict.get('delivering', 0)
completed = status_dict.get('completed', 0)
canceled = status_dict.get('canceled', 0)

# Estrés de cocina = pendientes + preparando
cocina_load = pending + preparing

# --- INTERFAZ GRÁFICA ---
st.title("🌮 Centro de Comando: Taquería Don Puerco")
st.markdown("Monitor de operaciones en tiempo real")

# Fila 1: KPIs Rápidos
col1, col2, col3, col4 = st.columns(4)
col1.metric("Órdenes Totales", f"{total_orders:,}")
col2.metric("Ingresos (MXN)", f"${total_revenue:,.2f}")
col3.metric("Fuego en Cocina (Pendientes)", cocina_load, delta=f"{pending} en cola, {preparing} al fuego", delta_color="inverse")
col4.metric("Entregados / Completados", completed)

st.markdown("---")

# Fila 2: Gráficas Locas
col_izq, col_der = st.columns([1, 1])

with col_izq:
    st.subheader("🌋 Termómetro de Estrés (Cocina)")
    # Usamos Apache ECharts para un Gauge chart agresivo
    gauge_options = {
        "tooltip": {"formatter": "{a} <br/>{b} : {c}"},
        "series": [{
            "name": "Órdenes Activas",
            "type": "gauge",
            "max": 1000, # Ajusta esto según el volumen que genere tu script
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
    st_echarts(options=gauge_options, height="400px")

with col_der:
    st.subheader("🌪️ Anatomía de las Ventas (Sunburst)")
    # Sunburst de Plotly: Centro (Categoría) -> Anillo (Carne)
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
        st.plotly_chart(fig_sunburst, use_container_width=True)
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
st.plotly_chart(fig_funnel, use_container_width=True)