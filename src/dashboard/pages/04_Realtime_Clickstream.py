import altair as alt
import pandas as pd
import streamlit as st

from utils.data_provider import data_provider
from utils.theme import apply_theme


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


@st.cache_data(ttl=300, show_spinner=False)
def load_overview_data(start_date: str, end_date: str, traffic_filter: tuple[str, ...]) -> dict:
    traffic_sources = list(traffic_filter)
    return {
        "metrics": data_provider.get_overview_metrics(start_date, end_date, traffic_sources),
        "daily_df": data_provider.get_daily_events_and_purchases(start_date, end_date, traffic_sources),
        "channel_df": data_provider.get_channel_distribution(start_date, end_date, traffic_sources),
        "realtime_df": data_provider.get_realtime_windows(start_date, end_date, traffic_sources),
        "event_type_df": data_provider.get_event_type_breakdown(start_date, end_date, traffic_sources),
        "deadletter_metrics": data_provider.get_deadletter_monitor(start_date, end_date),
        "deadletter_ts_df": data_provider.get_deadletter_timeseries(start_date, end_date),
        "deadletter_samples": data_provider.get_deadletter_samples(start_date, end_date),
        "pipeline_health": data_provider.get_pipeline_health(start_date, end_date, traffic_sources),
        "event_lag_df": data_provider.get_event_lag_timeseries(start_date, end_date, traffic_sources),
    }


apply_theme()
st.title("🛰️ Realtime Clickstream")

active_start = st.session_state.get('start_date')
active_end = st.session_state.get('end_date')

if not active_start or not active_end:
    active_start, active_end = data_provider.get_default_date_range(window_days=1)
    active_start, active_end = str(active_start), str(active_end)

start_date = str(active_start)
end_date = str(active_end)
traffic_filter = []

overview_data = load_overview_data(start_date, end_date, traffic_filter)
metrics = overview_data["metrics"]
daily_df = overview_data["daily_df"]
channel_df = overview_data["channel_df"]
realtime_df = overview_data["realtime_df"]
event_type_df = overview_data["event_type_df"]
deadletter_metrics = overview_data["deadletter_metrics"]
deadletter_ts_df = overview_data["deadletter_ts_df"]
deadletter_samples = overview_data["deadletter_samples"]
pipeline_health = overview_data["pipeline_health"]
event_lag_df = overview_data["event_lag_df"]

kpi_cols = st.columns(5)
render_kpi_card(kpi_cols[0], "Total events", f"{int(metrics.get('total_events') or 0):,}", "Deduplicated events in range")
render_kpi_card(kpi_cols[1], "Sessions", f"{int(metrics.get('total_sessions') or 0):,}", "Distinct sessions")
render_kpi_card(kpi_cols[2], "Users", f"{int(metrics.get('total_users') or 0):,}", "Known users only")
render_kpi_card(kpi_cols[3], "Purchases", f"{int(metrics.get('purchase_events') or 0):,}", "Purchase events")
render_kpi_card(kpi_cols[4], "CVR", f"{float(metrics.get('conversion_rate') or 0):.2%}", "Purchases per session")

top_left, top_right = st.columns((1.7, 1))
with top_left:
    st.subheader("Events and purchases")
    if daily_df.empty:
        st.info("No events for the selected filters.")
    else:
        time_field = "event_date:T"
        if len(daily_df.index) == 1 and not realtime_df.empty:
            chart_df = realtime_df.copy()
            chart_df["purchase_events"] = chart_df["purchase_events"].fillna(0)
            time_field = "window_start:T"
        else:
            chart_df = daily_df.copy()

        base = alt.Chart(chart_df).encode(x=alt.X(time_field, title=None))
        events_line = base.mark_line(color="#315f8c", strokeWidth=2.4).encode(y=alt.Y("total_events:Q", title="Events"))
        purchase_line = base.mark_line(color="#d36c42", strokeWidth=2.2).encode(
            y=alt.Y("purchase_events:Q", title="Purchases")
        )
        chart = alt.layer(events_line, purchase_line).resolve_scale(y="independent").properties(height=320)
        st.altair_chart(chart, width="stretch")

with top_right:
    st.subheader("Dead-letter monitor")
    deadletter_count = int(deadletter_metrics.get("deadletter_count") or 0)
    latest_failure = deadletter_metrics.get("latest_failure_at")
    if deadletter_count > 0:
        st.warning(f"{deadletter_count:,} invalid records were routed to dead-letter in the selected range.")
    else:
        st.success("No dead-letter records detected in the selected range.")
    stat_cols = st.columns(2)
    stat_cols[0].metric("Dead-letter rows", f"{deadletter_count:,}")
    stat_cols[1].metric("Today", f"{int(deadletter_metrics.get('deadletter_today') or 0):,}")
    st.caption(f"Latest failure: {latest_failure if latest_failure else 'None'}")
    if not deadletter_samples.empty:
        preview = deadletter_samples.copy()
        preview["raw_message"] = preview["raw_message"].astype(str).str.slice(0, 120)
        st.dataframe(preview, width="stretch", hide_index=True)
    else:
        st.caption("No recent dead-letter samples.")

mid_left, mid_right = st.columns((1.1, 1))
with mid_left:
    st.subheader("Channel distribution")
    if channel_df.empty:
        st.info("No channel data available.")
    else:
        channel_chart = (
            alt.Chart(channel_df)
            .mark_bar(color="#4d87b9")
            .encode(
                x=alt.X("total_events:Q", title="Events"),
                y=alt.Y("traffic_source:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("traffic_source:N", title="Channel"),
                    alt.Tooltip("total_events:Q", title="Events", format=",.0f"),
                    alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                    alt.Tooltip("purchases:Q", title="Purchases", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(channel_chart, width="stretch")

with mid_right:
    st.subheader("Event type breakdown")
    if event_type_df.empty:
        st.info("No event type data available.")
    else:
        donut = (
            alt.Chart(event_type_df)
            .mark_arc(innerRadius=70, outerRadius=120)
            .encode(
                theta=alt.Theta("total_events:Q"),
                color=alt.Color(
                    "event_type:N",
                    scale=alt.Scale(
                        range=["#315f8c", "#4d87b9", "#7da8cf", "#d36c42", "#9ca9b8", "#5f7288"]
                    ),
                    legend=alt.Legend(title="Event type", orient="bottom"),
                ),
                tooltip=[
                    alt.Tooltip("event_type:N", title="Event type"),
                    alt.Tooltip("total_events:Q", title="Events", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(donut, width="stretch")

monitor_left, monitor_mid, monitor_right = st.columns(3)
monitor_left.metric("Average event lag", f"{float(pipeline_health.get('avg_event_lag_seconds') or 0):.1f} s")
monitor_mid.metric("Dead-letter rate", f"{float(pipeline_health.get('deadletter_rate') or 0):.2%}")
monitor_right.metric("Latest realtime window", str(pipeline_health.get("latest_window_start") or "None"))

bottom_left, bottom_right = st.columns((1.15, 1))
with bottom_left:
    st.subheader("Realtime activity in 5-minute windows")
    if realtime_df.empty:
        st.info("No realtime aggregate windows available for the selected range.")
    else:
        realtime_chart = (
            alt.Chart(realtime_df)
            .mark_area(color="#8db5d9", line={"color": "#315f8c", "strokeWidth": 1.6}, opacity=0.7)
            .encode(
                x=alt.X("window_start:T", title=None),
                y=alt.Y("total_events:Q", title="Events"),
                tooltip=[
                    alt.Tooltip("window_start:T", title="Window"),
                    alt.Tooltip("total_events:Q", title="Events", format=",.0f"),
                    alt.Tooltip("purchase_events:Q", title="Purchases", format=",.0f"),
                    alt.Tooltip("avg_event_lag_seconds:Q", title="Avg lag (s)", format=",.1f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(realtime_chart, width="stretch")

with bottom_right:
    st.subheader("Event lag over time")
    if event_lag_df.empty:
        st.info("No event lag data available.")
    else:
        lag_chart = (
            alt.Chart(event_lag_df)
            .mark_line(color="#5f7288", strokeWidth=2)
            .encode(
                x=alt.X("window_start:T", title=None),
                y=alt.Y("avg_event_lag_seconds:Q", title="Lag (s)"),
                tooltip=[
                    alt.Tooltip("window_start:T", title="Window"),
                    alt.Tooltip("avg_event_lag_seconds:Q", title="Avg lag (s)", format=",.1f"),
                    alt.Tooltip("total_events:Q", title="Events", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(lag_chart, width="stretch")

tech_left, tech_right = st.columns((1, 1))
with tech_left:
    st.subheader("Dead-letter by hour")
    if deadletter_ts_df.empty:
        st.info("No dead-letter activity in the selected range.")
    else:
        dl_chart = (
            alt.Chart(deadletter_ts_df)
            .mark_bar(color="#c96a50")
            .encode(
                x=alt.X("failed_hour:T", title=None),
                y=alt.Y("deadletter_count:Q", title="Dead-letter rows"),
                tooltip=[
                    alt.Tooltip("failed_hour:T", title="Hour"),
                    alt.Tooltip("deadletter_count:Q", title="Rows", format=",.0f"),
                ],
            )
            .properties(height=260)
        )
        st.altair_chart(dl_chart, width="stretch")

with tech_right:
    st.subheader("Pipeline health")
    health_rows = pd.DataFrame(
        [
            {"Metric": "Raw events ingested", "Value": f"{int(pipeline_health.get('raw_events') or 0):,}"},
            {"Metric": "Realtime events emitted", "Value": f"{int(pipeline_health.get('realtime_events') or 0):,}"},
            {"Metric": "Realtime purchases emitted", "Value": f"{int(pipeline_health.get('realtime_purchases') or 0):,}"},
            {"Metric": "Latest event timestamp", "Value": str(pipeline_health.get("latest_event_timestamp") or "None")},
            {"Metric": "Latest processing time", "Value": str(pipeline_health.get("latest_processing_time") or "None")},
            {"Metric": "Average session length", "Value": f"{float(metrics.get('avg_session_seconds') or 0) / 60:.1f} min"},
            {"Metric": "Average events per session", "Value": f"{float(metrics.get('avg_events_per_session') or 0):.2f}"},
            {"Metric": "Cart rate", "Value": f"{float(metrics.get('cart_rate') or 0):.2%}"},
        ]
    )
    st.dataframe(health_rows, width="stretch", hide_index=True)
