import streamlit as st
from components.commerce.sales_metrics import display_kpi_metrics, display_sales_trend
from components.events.funnel import display_event_distribution

st.title("📈 Executive Overview")
st.markdown("---")

# 1. Main KPIs
display_kpi_metrics()

st.markdown("---")

# 2. Main Visuals
col_left, col_right = st.columns(2)

with col_left:
    display_sales_trend()

with col_right:
    display_event_distribution()

st.markdown("---")
st.info("Insights generated from TheLook eCommerce Data Warehouse.")
