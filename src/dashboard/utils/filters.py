import datetime as dt
import pandas as pd
import streamlit as st

def select_time_range(
    default_start: str, 
    default_end: str, 
    key_prefix: str = "filter",
    presets: dict[str, dt.timedelta] = None
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Renders a time range selector in the sidebar with presets and custom range options.
    Similar to the one used in Clickstream page.
    """
    if presets is None:
        presets = {
            "Last 1 day": dt.timedelta(days=1),
            "Last 7 days": dt.timedelta(days=7),
            "Last 30 days": dt.timedelta(days=30),
            "Last 90 days": dt.timedelta(days=90),
            "Custom range": None,
        }
        default_index = 2 # Last 30 days
    else:
        default_index = 0

    # Initialize applied values in session state if not already present
    # We prioritize existing session state if it was set by app.py or another page
    if f"{key_prefix}_applied_start" not in st.session_state:
        # Check if we have global dates from app.py to use as starting point
        if st.session_state.get("start_date"):
            st.session_state[f"{key_prefix}_applied_start"] = pd.to_datetime(st.session_state["start_date"])
        else:
            st.session_state[f"{key_prefix}_applied_start"] = pd.to_datetime(default_start)
            
    if f"{key_prefix}_applied_end" not in st.session_state:
        if st.session_state.get("end_date"):
            st.session_state[f"{key_prefix}_applied_end"] = pd.to_datetime(st.session_state["end_date"])
        else:
            st.session_state[f"{key_prefix}_applied_end"] = pd.to_datetime(default_end)

    # Current applied values for widget defaults
    applied_start = st.session_state[f"{key_prefix}_applied_start"]
    applied_end = st.session_state[f"{key_prefix}_applied_end"]

    with st.sidebar:
        st.subheader("Time range")
        # The selectbox is outside the form to allow immediate UI changes (presets vs custom)
        selected = st.selectbox("Window", list(presets), index=default_index, key=f"{key_prefix}_window_select")

        with st.form(key=f"{key_prefix}_form"):
            if selected == "Custom range":
                col1, col2 = st.columns(2)
                with col1:
                    # Use applied_start.date() instead of default_start to preserve state after Apply
                    start_date = st.date_input("Start date", value=applied_start.date(), key=f"{key_prefix}_start_date_input")
                    start_time = st.time_input("Start time", value=applied_start.time(), key=f"{key_prefix}_start_time_input")
                with col2:
                    end_date = st.date_input("End date", value=applied_end.date(), key=f"{key_prefix}_end_date_input")
                    end_time = st.time_input("End time", value=applied_end.time(), key=f"{key_prefix}_end_time_input")
                
                curr_start = pd.Timestamp(dt.datetime.combine(start_date, start_time))
                curr_end = pd.Timestamp(dt.datetime.combine(end_date, end_time))
            else:
                ref_end = pd.to_datetime(default_end)
                curr_end = pd.Timestamp(dt.datetime.combine(ref_end.date(), dt.time(23, 59, 59)))
                curr_start = curr_end - presets[selected]
                st.info(f"Range: {curr_start.strftime('%Y-%m-%d')} to {curr_end.strftime('%Y-%m-%d')}")
            
            if st.form_submit_button("Apply Filters", width="stretch"):
                if curr_start < curr_end:
                    st.session_state[f"{key_prefix}_applied_start"] = curr_start
                    st.session_state[f"{key_prefix}_applied_end"] = curr_end
                    # Also update the global session state used by resolve_date_window
                    st.session_state["start_date"] = str(curr_start.date())
                    st.session_state["end_date"] = str(curr_end.date())
                    # st.rerun() removed to avoid double-run on form submission
                else:
                    st.error("Start time must be before end time.")

    return st.session_state[f"{key_prefix}_applied_start"], st.session_state[f"{key_prefix}_applied_end"]

def filter_by_time(df: pd.DataFrame, column: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    """
    Filters a dataframe by a timestamp column within a given range.
    """
    if df.empty or column not in df.columns:
        return df
    filtered = df.copy()
    filtered[column] = pd.to_datetime(filtered[column]).dt.tz_localize(None)
    return filtered[(filtered[column] >= start_ts) & (filtered[column] <= end_ts)]

def fmt_int(value) -> str:
    return f"{int(value or 0):,}"

def fmt_seconds(value) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    value = float(value)
    if value < 60:
        return f"{value:.1f}s"
    return f"{value / 60:.1f}m"

def render_kpi_card(column, label: str, value: str, subtitle: str) -> None:
    column.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div style="color: #bdd0ee; font-size: 0.8rem; margin-top: 4px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
