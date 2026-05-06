import datetime as dt
import pandas as pd
import streamlit as st

def select_time_range(
    default_start: str, 
    default_end: str, 
    key_prefix: str = "filter",
    presets: dict[str, dt.timedelta] = None,
    reference_time: pd.Timestamp = None,
    default_index: int = None
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
        if default_index is None:
            default_index = 2 # Last 30 days
    else:
        if default_index is None:
            default_index = 0

    # Initialize applied values in session state if not already present
    if f"{key_prefix}_applied_start" not in st.session_state or f"{key_prefix}_applied_end" not in st.session_state:
        # Use preset if specified and available
        if presets and default_index is not None:
            preset_labels = list(presets.keys())
            if 0 <= default_index < len(preset_labels):
                selected_label = preset_labels[default_index]
                delta = presets[selected_label]
                
                if delta is not None:
                    if reference_time is not None:
                        curr_end = reference_time.floor("min")
                    else:
                        ref_end = pd.to_datetime(default_end)
                        curr_end = pd.Timestamp(dt.datetime.combine(ref_end.date(), dt.time(23, 59, 59)))
                    
                    st.session_state[f"{key_prefix}_applied_start"] = curr_end - delta
                    st.session_state[f"{key_prefix}_applied_end"] = curr_end
                else:
                    # Fallback for "Custom range" or None delta
                    st.session_state[f"{key_prefix}_applied_start"] = pd.to_datetime(default_start)
                    st.session_state[f"{key_prefix}_applied_end"] = reference_time if reference_time is not None else pd.to_datetime(default_end)
            else:
                st.session_state[f"{key_prefix}_applied_start"] = pd.to_datetime(default_start)
                st.session_state[f"{key_prefix}_applied_end"] = reference_time if reference_time is not None else pd.to_datetime(default_end)
        else:
            st.session_state[f"{key_prefix}_applied_start"] = pd.to_datetime(default_start)
            st.session_state[f"{key_prefix}_applied_end"] = reference_time if reference_time is not None else pd.to_datetime(default_end)

    # Current applied values for widget defaults
    applied_start = st.session_state[f"{key_prefix}_applied_start"]
    applied_end = st.session_state[f"{key_prefix}_applied_end"]

    with st.sidebar:
        st.subheader("Time range")
        selected = st.selectbox("Window", list(presets), index=default_index, key=f"{key_prefix}_window_select")

        with st.form(key=f"{key_prefix}_form"):
            if selected == "Custom range":
                col1, col2 = st.columns(2)
                with col1:
                    start_date = st.date_input("Start date", value=applied_start.date(), key=f"{key_prefix}_start_date_input")
                    start_time = st.time_input("Start time", value=applied_start.time(), key=f"{key_prefix}_start_time_input")
                with col2:
                    end_date = st.date_input("End date", value=applied_end.date(), key=f"{key_prefix}_end_date_input")
                    end_time = st.time_input("End time", value=applied_end.time(), key=f"{key_prefix}_end_time_input")
                
                curr_start = pd.Timestamp(dt.datetime.combine(start_date, start_time))
                curr_end = pd.Timestamp(dt.datetime.combine(end_date, end_time))
            else:
                if reference_time is not None:
                    # Round to nearest minute to align with window boundaries
                    curr_end = reference_time.floor("min")
                else:
                    ref_end = pd.to_datetime(default_end)
                    curr_end = pd.Timestamp(dt.datetime.combine(ref_end.date(), dt.time(23, 59, 59)))
                
                curr_start = curr_end - presets[selected]
                
                # Show more detail in info box for smaller windows
                if presets[selected] < dt.timedelta(days=1):
                    st.info(f"Range: {curr_start.strftime('%Y-%m-%d %H:%M')} to {curr_end.strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.info(f"Range: {curr_start.strftime('%Y-%m-%d')} to {curr_end.strftime('%Y-%m-%d')}")
            
            if st.form_submit_button("Apply Filters", width="stretch"):
                if curr_start < curr_end:
                    st.session_state[f"{key_prefix}_applied_start"] = curr_start
                    st.session_state[f"{key_prefix}_applied_end"] = curr_end
                    st.session_state["start_date"] = str(curr_start.date())
                    st.session_state["end_date"] = str(curr_end.date())
                else:
                    st.error("Start time must be before end time.")

    return st.session_state[f"{key_prefix}_applied_start"], st.session_state[f"{key_prefix}_applied_end"]

def filter_by_time(df: pd.DataFrame, column: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp, freq: str = None) -> pd.DataFrame:
    """
    Filters a dataframe by a timestamp column within a given range.
    Ensures all timestamps are timezone-naive for safe comparison.
    If freq is provided, floors the start_ts to avoid losing overlapping buckets.
    """
    if df.empty or column not in df.columns:
        return df
    
    # Normalize comparison bounds to naive UTC
    if hasattr(start_ts, "tzinfo") and start_ts.tzinfo is not None:
        start_ts = start_ts.tz_localize(None)
    if hasattr(end_ts, "tzinfo") and end_ts.tzinfo is not None:
        end_ts = end_ts.tz_localize(None)

    # Floor start_ts to frequency if requested to include partially overlapping buckets
    if freq:
        start_ts = start_ts.floor(freq)

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
