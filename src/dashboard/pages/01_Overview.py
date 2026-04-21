import altair as alt
import pandas as pd
import streamlit as st

from utils.data_provider import data_provider
from utils.page_state import default_date_range


def render_kpi_card(column, label: str, value: str, subtitle: str) -> None:
    column.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-subtle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.title("Clickstream Overview")

date_range = st.sidebar.date_input(
    "Date range",
    value=default_date_range(),
    key="overview_dates_v2",
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_date_range()

start_date = str(start_date)
end_date = str(end_date)

traffic_options = data_provider.get_traffic_sources(start_date, end_date)
selected_sources = st.sidebar.multiselect(
    "Traffic source",
    options=traffic_options,
    default=traffic_options,
    key="overview_sources_v2",
)
traffic_filter = selected_sources if selected_sources else traffic_options

metrics = data_provider.get_overview_metrics(start_date, end_date, traffic_filter)
daily_df = data_provider.get_daily_events_and_purchases(start_date, end_date, traffic_filter)
channel_df = data_provider.get_channel_distribution(start_date, end_date, traffic_filter)
realtime_df = data_provider.get_realtime_windows(start_date, end_date, traffic_filter)
event_type_df = data_provider.get_event_type_breakdown(start_date, end_date, traffic_filter)
deadletter_metrics = data_provider.get_deadletter_monitor(start_date, end_date)
deadletter_samples = data_provider.get_deadletter_samples(start_date, end_date)

kpi_cols = st.columns(5)
render_kpi_card(kpi_cols[0], "Total events", f"{int(metrics.get('total_events') or 0):,}", "Deduplicated events in range")
render_kpi_card(kpi_cols[1], "Sessions", f"{int(metrics.get('total_sessions') or 0):,}", "Distinct sessions")
render_kpi_card(kpi_cols[2], "Users", f"{int(metrics.get('total_users') or 0):,}", "Known users only")
render_kpi_card(kpi_cols[3], "Purchases", f"{int(metrics.get('purchase_events') or 0):,}", "Purchase events")
render_kpi_card(kpi_cols[4], "CVR", f"{float(metrics.get('conversion_rate') or 0):.2%}", "Purchases per session")

top_left, top_right = st.columns((1.7, 1))
with top_left:
    st.subheader("Events and purchases by day")
    if daily_df.empty:
        st.info("No events for the selected filters.")
    else:
        base = alt.Chart(daily_df).encode(x=alt.X("event_date:T", title=None))
        events_line = base.mark_line(color="#315f8c", strokeWidth=2.4).encode(
            y=alt.Y("total_events:Q", title="Events"),
            tooltip=[
                alt.Tooltip("event_date:T", title="Date"),
                alt.Tooltip("total_events:Q", title="Events", format=",.0f"),
                alt.Tooltip("purchase_events:Q", title="Purchases", format=",.0f"),
            ],
        )
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

bottom_left, bottom_right = st.columns((1.8, 1))
with bottom_left:
    st.subheader("Realtime trend in 5-minute windows")
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
    st.subheader("Operational notes")
    summary_rows = pd.DataFrame(
        [
            {"Metric": "Average session length", "Value": f"{float(metrics.get('avg_session_seconds') or 0) / 60:.1f} min"},
            {"Metric": "Average events per session", "Value": f"{float(metrics.get('avg_events_per_session') or 0):.2f}"},
            {"Metric": "Average pageviews per session", "Value": f"{float(metrics.get('avg_pageviews_per_session') or 0):.2f}"},
            {"Metric": "Average product views per session", "Value": f"{float(metrics.get('avg_product_views_per_session') or 0):.2f}"},
            {"Metric": "Cart rate", "Value": f"{float(metrics.get('cart_rate') or 0):.2%}"},
            {"Metric": "Session purchase rate", "Value": f"{float(metrics.get('session_purchase_rate') or 0):.2%}"},
        ]
    )
    st.dataframe(summary_rows, width="stretch", hide_index=True)
