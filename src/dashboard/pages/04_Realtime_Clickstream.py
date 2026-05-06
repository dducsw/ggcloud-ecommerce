import concurrent.futures
import datetime as dt

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_provider import data_provider
from utils.theme import apply_theme
from utils.filters import select_time_range, filter_by_time, fmt_int, fmt_seconds, render_kpi_card



@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_data(start_date: str, end_date: str, range_start_value: str, range_end_value: str, traffic_filter: tuple[str, ...]) -> dict:
    traffic_sources = list(traffic_filter)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            "business": executor.submit(data_provider.get_overview_metrics, start_date, end_date, traffic_sources),
            "event_mix": executor.submit(data_provider.get_event_type_breakdown, start_date, end_date, traffic_sources),
            "event_type_windows": executor.submit(data_provider.get_event_type_windows, start_date, end_date, traffic_sources),
            "business_windows": executor.submit(data_provider.get_realtime_windows, start_date, end_date, traffic_sources),
            "freshness": executor.submit(data_provider.get_ingestion_freshness, start_date, end_date, traffic_sources),
            "quality": executor.submit(data_provider.get_event_quality_summary, start_date, end_date, traffic_sources),
            "throughput": executor.submit(data_provider.get_throughput_by_window, start_date, end_date, traffic_sources),
        }
        return {key: future.result() for key, future in futures.items()}


apply_theme()
st.title("Realtime Clickstream")

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
    "Last 5 minutes": dt.timedelta(minutes=5),
    "Last 15 minutes": dt.timedelta(minutes=15),
    "Last 30 minutes": dt.timedelta(minutes=30),
    "Last 1 hour": dt.timedelta(hours=1),
    "Last 6 hours": dt.timedelta(hours=6),
    "Last 1 day": dt.timedelta(days=1),
    "Custom range": None,
}

range_presets = rt_presets.copy()
latest_ts = data_provider.get_latest_window_timestamp()

range_start, range_end = select_time_range(
    start_date, 
    end_date, 
    key_prefix="rt", 
    presets=range_presets, 
    reference_time=latest_ts,
    default_index=2 # Default to Last 30 minutes
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
    business_windows = filter_by_time(data["business_windows"], "window_start", range_start, range_end, freq="5min")
    freshness = data["freshness"]
    quality = data["quality"]
    throughput = filter_by_time(data["throughput"], "window_start", range_start, range_end, freq="5min")

    if not event_type_windows.empty:
        event_mix = (
            event_type_windows.groupby("event_type", as_index=False)["total_events"]
            .sum()
            .sort_values("total_events", ascending=False)
        )
        business["total_events"] = event_mix["total_events"].sum()
    else:
        event_mix = data["event_mix"]

    business_cols = st.columns(4)
    render_kpi_card(business_cols[0], "Events", fmt_int(business.get("total_events")), "Deduplicated clickstream")
    render_kpi_card(business_cols[1], "Sessions", fmt_int(business.get("total_sessions")), "Distinct sessions")
    render_kpi_card(business_cols[2], "Users", fmt_int(business.get("total_users")), "Known users")
    render_kpi_card(business_cols[3], "Purchase/session", f"{float(business.get('conversion_rate') or 0):.2%}", "Light business signal")

    st.subheader("Business: traffic by event type")
    if event_type_windows.empty:
        st.info("No event type window data available.")
    else:
        traffic_chart = (
            alt.Chart(event_type_windows)
            .mark_line(strokeWidth=2.5, interpolate="monotone", point=True)
            .encode(
                x=alt.X("window_start:T", title="Window"),
                y=alt.Y("total_events:Q", title="Events"),
                color=alt.Color(
                    "event_type:N",
                    title="Event type",
                    scale=alt.Scale(range=["#d47465", "#66bcc7", "#8ccf68", "#9a68cc", "#cf65b5", "#5f7288"]),
                ),
                tooltip=[
                    alt.Tooltip("window_start:T", title="Window"),
                    alt.Tooltip("event_type:N", title="Event"),
                    alt.Tooltip("total_events:Q", title="Events", format=",.0f"),
                ],
            )
            .properties(height=300)
            .interactive()
        )
        st.altair_chart(traffic_chart, width="stretch")

    business_left, business_right = st.columns(2)
    with business_left:
        st.subheader("Business: event share")
        if event_mix.empty:
            st.info("No event data available.")
        else:
            chart = (
                alt.Chart(event_mix)
                .mark_arc(innerRadius=65, outerRadius=115)
                .encode(
                    theta=alt.Theta("total_events:Q"),
                    color=alt.Color(
                        "event_type:N",
                        title="Event type",
                        scale=alt.Scale(range=["#d47465", "#66bcc7", "#8ccf68", "#9a68cc", "#cf65b5", "#5f7288"]),
                    ),
                    tooltip=[
                        alt.Tooltip("event_type:N", title="Event"),
                        alt.Tooltip("total_events:Q", title="Events", format=",.0f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, width="stretch")

    with business_right:
        st.subheader("Business: purchases over time")
        if business_windows.empty:
            st.info("No realtime windows available.")
        else:
            chart = (
                alt.Chart(business_windows)
                .mark_line(color="#d36c42", strokeWidth=2.3)
                .encode(
                    x=alt.X("window_start:T", title=None),
                    y=alt.Y("purchase_events:Q", title="Purchases"),
                    tooltip=[
                        alt.Tooltip("window_start:T", title="Window"),
                        alt.Tooltip("total_events:Q", title="Events", format=",.0f"),
                        alt.Tooltip("purchase_events:Q", title="Purchases", format=",.0f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, width="stretch")

    ops_cols = st.columns(4)
    render_kpi_card(ops_cols[0], "Processing freshness", fmt_seconds(freshness.get("processing_freshness_seconds")), "Latest processing_time")
    render_kpi_card(ops_cols[1], "Aggregate freshness", fmt_seconds(freshness.get("aggregate_freshness_seconds")), "Latest 5m emit")
    render_kpi_card(ops_cols[2], "P95 lag", fmt_seconds(freshness.get("p95_event_lag_seconds")), "Event to processing")
    render_kpi_card(ops_cols[3], "Reject rate", f"{float(quality.get('reject_rate') or 0):.2%}", "Dead-letter ratio")

    ops_left, ops_right = st.columns(2)
    with ops_left:
        st.subheader("Ops: throughput and lag")
        if throughput.empty:
            st.info("No throughput data available.")
        else:
            base = alt.Chart(throughput).encode(x=alt.X("window_start:T", title=None))
            events = base.mark_area(color="#8db5d9", opacity=0.65, line={"color": "#315f8c"}).encode(
                y=alt.Y("events_per_second:Q", title="Events/sec"),
                tooltip=[
                    alt.Tooltip("window_start:T", title="Window"),
                    alt.Tooltip("events_per_second:Q", title="Events/sec", format=",.2f"),
                    alt.Tooltip("avg_event_lag_seconds:Q", title="Avg lag (s)", format=",.1f"),
                ],
            )
            lag = base.mark_line(color="#c96a50", strokeWidth=2).encode(
                y=alt.Y("avg_event_lag_seconds:Q", title="Avg lag (s)")
            )
            st.altair_chart(alt.layer(events, lag).resolve_scale(y="independent").properties(height=280), width="stretch")

    with ops_right:
        st.subheader("Ops: quality checks")
        quality_rows = pd.DataFrame(
            [
                {"Check": "Raw rows", "Value": fmt_int(quality.get("raw_rows"))},
                {"Check": "Duplicate rows removed", "Value": fmt_int(quality.get("duplicate_rows_removed"))},
                {"Check": "Missing session_id", "Value": fmt_int(quality.get("missing_session_id"))},
                {"Check": "Missing user_id", "Value": fmt_int(quality.get("missing_user_id"))},
                {"Check": "Negative lag events", "Value": fmt_int(quality.get("negative_lag_events"))},
                {"Check": "Latest 5m window", "Value": str(freshness.get("latest_window_start") or "None")},
            ]
        )
        st.dataframe(quality_rows, width="stretch", hide_index=True)


render_dashboard()
