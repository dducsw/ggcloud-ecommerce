import streamlit as st
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# App Configuration
st.set_page_config(
    page_title="TheLook eCommerce BI",
    page_icon="📊",
    layout="wide"
)

# Sidebar Navigation Header
st.sidebar.title("📊 TheLook BI Suite")
st.sidebar.markdown("---")

# Main Page Content
st.title("🏠 Welcome to TheLook BI Dashboard")
st.markdown("""
### Data Architecture
This dashboard is powered by the **TheLook eCommerce Data Warehouse**. 
It utilizes a Star Schema architecture optimized for high-performance analytical queries.

### Navigation
Please use the sidebar to navigate through the different domains:
1.  **Executive Overview**: High-level KPIs and sales trends.
2.  **Logistics Performance**: Shipping durations and status tracking.
""")

st.image("https://images.unsplash.com/photo-1551288049-bbbda546697c?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80", 
         caption="Data Warehousing Insights")

# Footer
st.sidebar.markdown("---")
st.sidebar.info(f"Environment: {'Local CSV' if os.getenv('USE_LOCAL_DWH', 'false').lower() == 'true' else 'BigQuery'}")
st.sidebar.write("Developed by AI Assistant")
