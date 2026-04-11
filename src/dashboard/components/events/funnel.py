import streamlit as st
import plotly.express as px
from utils.data_provider import data_provider

def display_event_distribution():
    """Renders the distribution of user events."""
    st.subheader("📊 User Event Types Distribution")

    query = f"SELECT event_type, COUNT(*) as count FROM `{data_provider.project_id}.{data_provider.dataset_id}.fact_events` GROUP BY 1"
    df = data_provider.query("fact_events", query=query)

    fig = px.pie(df, names="event_type", values="count", 
                 hole=0.4, title="User Activity Breakdown")
    st.plotly_chart(fig, width='stretch')
