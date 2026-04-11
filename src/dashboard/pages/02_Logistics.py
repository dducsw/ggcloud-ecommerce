import streamlit as st
import plotly.express as px
from utils.data_provider import data_provider

st.title("🚚 Logistics & Shipping Performance")
st.markdown("---")

def display_logistics_perf():
    query = f"""
    SELECT 
        status,
        AVG(shipping_duration_days) as avg_shipping_days,
        AVG(delivery_duration_days) as avg_delivery_days
    FROM `{data_provider.project_id}.{data_provider.dataset_id}.fact_orders`
    WHERE status NOT IN ('Cancelled', 'Processing')
    GROUP BY 1
    """
    df = data_provider.query("fact_orders", query=query)

    if df.empty:
        st.warning("No logistics data available for display.")
        return

    fig = px.bar(
        df, 
        x="status", 
        y=["avg_shipping_days", "avg_delivery_days"],
        barmode="group",
        title="Average Duration (Days) by Order Status"
    )
    st.plotly_chart(fig, width='stretch')

display_logistics_perf()
