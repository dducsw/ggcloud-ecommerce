import datetime as dt
import streamlit as st
from utils.data_provider import data_provider
from utils.theme import apply_theme, render_hero

st.set_page_config(page_title="TheLook Ecommerce Analytics", page_icon="🛍️", layout="wide", initial_sidebar_state="expanded")

def build_sidebar():
    latest_date = data_provider.get_latest_date()
    default_end = latest_date or dt.date.today()
    default_start = default_end - dt.timedelta(days=30)

    st.sidebar.markdown("### 🛍️ TheLook Analytics")
    st.sidebar.caption("Source: Gold Layer (Data Warehouse)")
    
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(default_start, default_end),
        max_value=default_end,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = default_start
        end_date = default_end

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
