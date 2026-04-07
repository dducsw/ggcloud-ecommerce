import streamlit as st
import plotly.express as px
from utils.data_provider import data_provider

def display_event_distribution():
    """Renders the distribution of user events."""
    st.subheader("📊 User Event Types Distribution")
    
    if data_provider.use_local:
        # For local, maybe we sample the data
        df = data_provider.query("fact_events") # This might be large, but LocalLoader handles it
    else:
        query = f"SELECT event_type, COUNT(*) as count FROM `{data_provider.project_id}.{data_provider.dataset_id}.fact_events` GROUP BY 1"
        df = data_provider.query("fact_events", query=query)
        
    fig = px.pie(df, names="event_type", values="count" if not data_provider.use_local else None, 
                 hole=0.4, title="User Activity Breakdown")
    st.plotly_chart(fig, width='stretch')
