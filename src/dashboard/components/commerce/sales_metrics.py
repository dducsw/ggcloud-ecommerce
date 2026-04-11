import streamlit as st
import plotly.express as px
from utils.data_provider import data_provider

def display_kpi_metrics():
    """Renders the top row of KPI metrics."""
    kpis = data_provider.get_kpis()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Revenue", f"${kpis.get('total_revenue', 0):,.2f}")
    col2.metric("Total Orders", f"{kpis.get('total_orders', 0):,}")
    col3.metric("Avg Margin %", f"{kpis.get('avg_margin_pct', 0):.2f}%")

def display_sales_trend():
    """Renders the monthly sales trend line chart."""
    st.subheader("📈 Monthly Sales Trend")
    query = f"""
    SELECT 
        FORMAT_DATE('%Y-%m', PARSE_DATE('%Y%m%d', CAST(created_date_key AS STRING))) as month,
        SUM(total_revenue) as monthly_revenue
    FROM `{data_provider.project_id}.{data_provider.dataset_id}.fact_orders`
    GROUP BY 1 ORDER BY 1
    """
    trend_df = data_provider.query("fact_orders", query=query)

    fig = px.line(trend_df, x="month", y="monthly_revenue", 
                  markers=True, title="Revenue Over Time")
    st.plotly_chart(fig, width='stretch')
