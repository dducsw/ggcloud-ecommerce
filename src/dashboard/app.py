import datetime as dt
import streamlit as st
from utils.data_provider import data_provider
from utils.theme import apply_theme, render_hero
from utils.filters import select_time_range

st.set_page_config(page_title="TheLook Ecommerce Analytics", page_icon="🛍️", layout="wide", initial_sidebar_state="expanded")

def build_sidebar():
    latest_date = data_provider.get_latest_date()
    default_end = latest_date or dt.date.today()
    default_start = default_end - dt.timedelta(days=30)

    st.sidebar.markdown("### 🛍️ TheLook Analytics")
    st.sidebar.caption("Source: Gold Layer (Data Warehouse)")
    
    range_start, range_end = select_time_range(
        str(default_start), 
        str(default_end), 
        key_prefix="global"
    )
    
    start_date = range_start.date()
    end_date = range_end.date()

    st.sidebar.markdown("---")
    st.sidebar.write(f"Project: `{data_provider.project_id}`")
    st.sidebar.write(f"Dataset: `{data_provider.dataset}`")
    
    # Store dates in session state for pages to access
    st.session_state['start_date'] = str(start_date)
    st.session_state['end_date'] = str(end_date)

def main():
    apply_theme()
    build_sidebar()
    render_hero(
        "TheLook Unified Intelligence",
        "Unified retail operations view across sales, customer and logistics.",
        "https://picsum.photos/seed/thelook-home/120/120",
    )

if __name__ == "__main__":
    main()
