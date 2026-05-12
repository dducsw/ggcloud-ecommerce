import concurrent.futures
import datetime as dt

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_provider import data_provider
from utils.theme import apply_theme
from utils.filters import select_time_range, filter_by_time, fmt_int, fmt_seconds, render_kpi_card



def fmt_time_ago(ts):
    if ts is None or pd.isna(ts):
        return "Unknown"
    now = dt.datetime.now(dt.timezone.utc)
    if isinstance(ts, str):
        ts = pd.to_datetime(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    
    diff = now - ts
    seconds = diff.total_seconds()
    
    if seconds < 0:
        return "Just now"
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_data(start_date: str, end_date: str, range_start_value: str, range_end_value: str, traffic_filter: tuple[str, ...]) -> dict:
    traffic_sources = list(traffic_filter)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            "business": executor.submit(data_provider.get_overview_metrics, start_date, end_date, traffic_sources),
            "event_mix": executor.submit(data_provider.get_event_type_breakdown, start_date, end_date, traffic_sources),
            "event_type_windows": executor.submit(data_provider.get_event_type_windows, start_date, end_date, traffic_sources),
            "business_windows": executor.submit(data_provider.get_realtime_windows, start_date, end_date, traffic_sources),
            "freshness": executor.submit(data_provider.get_ingestion_freshness, start_date, end_date, traffic_sources),
            "quality": executor.submit(data_provider.get_event_quality_summary, start_date, end_date, traffic_sources),
            "throughput": executor.submit(data_provider.get_throughput_by_window, start_date, end_date, traffic_sources),
            "funnel": executor.submit(data_provider.get_realtime_funnel, 60),
            "bounces": executor.submit(data_provider.get_top_bounce_pages, start_date, end_date, traffic_sources),
        }
        return {key: future.result() for key, future in futures.items()}


from utils.theme import render_page_header, render_section_header
apply_theme()
render_page_header("Realtime Clickstream", "Live monitoring of user behavior and pipeline health.", icon="bolt")

with st.sidebar:
    st.markdown("---")
    st.subheader("Realtime controls")
    auto_refresh = st.toggle("Auto-refresh every 60s", value=True)
    if st.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()

active_start = st.session_state.get("start_date")
active_end = st.session_state.get("end_date")

if not active_start or not active_end:
    active_start, active_end = data_provider.get_default_date_range(window_days=1)
    active_start, active_end = str(active_start), str(active_end)

start_date = str(active_start)
end_date = str(active_end)

rt_presets = {
    "Last 5m": dt.timedelta(minutes=5),
    "Last 15m": dt.timedelta(minutes=15),
    "Last 30m": dt.timedelta(minutes=30),
    "Last 1h": dt.timedelta(hours=1),
    "Last 6h": dt.timedelta(hours=6),
    "Custom": None,
}

latest_ts = data_provider.get_latest_window_timestamp()

range_start, range_end = select_time_range(
    start_date, 
    end_date, 
    key_prefix="rt", 
    presets=rt_presets, 
    reference_time=latest_ts,
    default_index=2
)
query_start_date = str(range_start.date())
query_end_date = str(range_end.date())
traffic_filter: tuple[str, ...] = tuple()


@st.fragment(run_every=60 if auto_refresh else None)
def render_dashboard():
    data = load_dashboard_data(
        query_start_date,
        query_end_date,
        range_start.isoformat(sep=" "),
        range_end.isoformat(sep=" "),
        traffic_filter,
    )
    business = data["business"]
    event_type_windows = filter_by_time(data["event_type_windows"], "window_start", range_start, range_end, freq="5min")
    freshness = data["freshness"]
    quality = data["quality"]
    throughput = filter_by_time(data["throughput"], "window_start", range_start, range_end, freq="5min")
    funnel_df = data["funnel"]
    bounces_df = data["bounces"]

    # --- System Status Banner ---
    status_cols = st.columns(4)
    latest_event = freshness.get("latest_event_timestamp")
    latest_proc = freshness.get("latest_processing_time")
    
    with status_cols[0]:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Latest Event</div>
                <div class="metric-value">{fmt_time_ago(latest_event)}</div>
                <div class="metric-subtitle">{latest_event.strftime('%H:%M:%S') if latest_event else '-'}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with status_cols[1]:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Latest Processed</div>
                <div class="metric-value">{fmt_time_ago(latest_proc)}</div>
                <div class="metric-subtitle">{latest_proc.strftime('%H:%M:%S') if latest_proc else '-'}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with status_cols[2]:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Current UTC</div>
                <div class="metric-value">{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')}</div>
                <div class="metric-subtitle">{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')}</div>
            </div>
        """, unsafe_allow_html=True)

    with status_cols[3]:
        is_active = freshness.get("processing_freshness_seconds", 999) < 300
        badge_class = "status-badge-active" if is_active else "status-badge-idle"
        status_text = "ACTIVE" if is_active else "IDLE"
        st.markdown(f"""
            <div class="metric-card" style="align-items: center; justify-content: center;">
                <div class="metric-label">Pipeline Status</div>
                <div class="status-badge {badge_class}" style="font-size: 1.25rem; padding: 8px 24px;">{status_text}</div>
            </div>
        """, unsafe_allow_html=True)

    render_section_header("Stream Insights", icon="analytics")
    business_cols = st.columns(4)
    render_kpi_card(business_cols[0], "Live Events", fmt_int(business.get("total_events")), "Total in window")
    render_kpi_card(business_cols[1], "Sessions", fmt_int(business.get("total_sessions")), "Active visits")
    render_kpi_card(business_cols[2], "Active Users", fmt_int(business.get("total_users")), "Identified")
    render_kpi_card(business_cols[3], "Conv. Rate", f"{float(business.get('conversion_rate') or 0):.2%}", "Purchases/Sessions")

    col_l, col_r = st.columns([3, 2])
    with col_l:
        render_section_header("Conversion Funnel", icon="filter_list")
        if funnel_df.empty:
            st.info("No funnel data.")
        else:
            # Add drop-off %
            funnel_df["prev_sessions"] = funnel_df["sessions"].shift(1)
            funnel_df["retention"] = (funnel_df["sessions"] / funnel_df["prev_sessions"]).fillna(1)
            funnel_df["dropoff"] = 1 - funnel_df["retention"]
            
            fig = go.Figure(go.Funnel(
                y=funnel_df["stage"],
                x=funnel_df["sessions"],
                textinfo="value+percent initial",
                marker={"color": ["#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"]}
            ))
            fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        render_section_header("Top Bounce Pages", icon="exit_to_app")
        if bounces_df.empty:
            st.info("No bounces detected.")
        else:
            chart = (
                alt.Chart(bounces_df)
                .mark_bar(color="#ef4444", cornerRadiusEnd=4)
                .encode(
                    x=alt.X("bounces:Q", title="Bounce Count"),
                    y=alt.Y("uri:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("uri:N", title="Page URI"),
                        alt.Tooltip("bounces:Q", title="Bounce Count", format=",.0f"),
                    ]
                )
                .properties(height=350)
            )
            st.altair_chart(chart, width="stretch")

    render_section_header("Pipeline Operations", icon="settings")
    ops_cols = st.columns(4)
    render_kpi_card(ops_cols[0], "Proc. Lag", fmt_seconds(freshness.get("processing_freshness_seconds")), "Latency")
    render_kpi_card(ops_cols[1], "Agg. Freshness", fmt_seconds(freshness.get("aggregate_freshness_seconds")), "DWH Delay")
    render_kpi_card(ops_cols[2], "Throughput", f"{throughput['events_per_second'].mean():.1f} eps", "Avg events/sec")
    render_kpi_card(ops_cols[3], "DLQ Rate", f"{float(quality.get('reject_rate') or 0):.2%}", "Reject rate")

    if not throughput.empty:
        render_section_header("Throughput & Event Lag Trend", icon="speed")
        base = alt.Chart(throughput).encode(x=alt.X("window_start:T", title=None))
        events = base.mark_area(color="#3b82f6", opacity=0.3).encode(y=alt.Y("events_per_second:Q", title="EPS"))
        lag = base.mark_line(color="#ef4444", strokeWidth=2).encode(y=alt.Y("avg_event_lag_seconds:Q", title="Lag (s)"))
        st.altair_chart(alt.layer(events, lag).resolve_scale(y="independent").properties(height=300), width="stretch")

    with st.expander("🛠️ Testing Guide", expanded=False):
        st.code("""
# Start Dataflow
.\\src\\clickstream\\run_clickstream_pipeline.ps1

# Generate Data
cd datagen
.\\manage_data.ps1 -Action gen-events
        """, language="powershell")


render_dashboard()
