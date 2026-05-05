import concurrent.futures
import datetime as dt

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_provider import data_provider
from utils.theme import apply_theme
from utils.filters import select_time_range, filter_by_time, fmt_int, fmt_seconds, render_kpi_card


def build_funnel_sankey(funnel_df: pd.DataFrame) -> go.Figure:
    ordered = funnel_df.copy()
    stages = ordered["stage"].astype(str).tolist()
    values = ordered["sessions"].fillna(0).astype(float).tolist()
    source = list(range(max(len(stages) - 1, 0)))
    target = list(range(1, len(stages)))
    link_values = [values[idx + 1] for idx in source]
    palette = ["#ff9f1c", "#66c7c7", "#a6d854", "#006bd6"]

    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="fixed",
                node={
                    "pad": 16,
                    "thickness": 10,
                    "line": {"color": "rgba(255,255,255,0)", "width": 0},
                    "label": [f"{stage}: {int(value):,}" for stage, value in zip(stages, values)],
                    "color": palette[: len(stages)],
                    "x": [idx / max(len(stages) - 1, 1) for idx in range(len(stages))],
                    "y": [0.50 for _ in stages],
                },
                link={
                    "source": source,
                    "target": target,
                    "value": link_values,
                    "color": [
                        "rgba(255, 159, 28, 0.42)",
                        "rgba(102, 199, 199, 0.42)",
                        "rgba(166, 216, 84, 0.42)",
                    ][: len(link_values)],
                },
            )
        ]
    )
    fig.update_layout(
        height=280,
        margin={"l": 4, "r": 12, "t": 4, "b": 4},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#dbeafe", "size": 13},
    )
    return fig


@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_data(start_date: str, end_date: str, traffic_filter: tuple[str, ...]) -> dict:
    traffic_sources = list(traffic_filter)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            "summary": executor.submit(data_provider.get_session_summary, start_date, end_date, traffic_sources),
            "funnel": executor.submit(data_provider.get_conversion_funnel, start_date, end_date, traffic_sources),
            "categories": executor.submit(data_provider.get_top_categories, start_date, end_date, traffic_sources),
            "session_trend": executor.submit(data_provider.get_session_timeseries, start_date, end_date, traffic_sources),
            "health": executor.submit(data_provider.get_session_pipeline_health, start_date, end_date, traffic_sources),
            "timeseries": executor.submit(data_provider.get_sessionization_timeseries, start_date, end_date, traffic_sources),
            "anomalies": executor.submit(data_provider.get_session_anomaly_buckets, start_date, end_date, traffic_sources),
        }
        return {key: future.result() for key, future in futures.items()}


apply_theme()
st.title("Session Analysis")

with st.sidebar:
    st.markdown("---")
    st.subheader("Session controls")
    auto_refresh = st.toggle("Auto-refresh every 60s", value=True)
    if st.button("Refresh session view"):
        st.cache_data.clear()
        st.rerun()

active_start = st.session_state.get("start_date")
active_end = st.session_state.get("end_date")

if not active_start or not active_end:
    active_start, active_end = data_provider.get_default_date_range(window_days=1)
    active_start, active_end = str(active_start), str(active_end)

start_date = str(active_start)
end_date = str(active_end)

session_presets = {
    "Last 1 hour": dt.timedelta(hours=1),
    "Last 6 hours": dt.timedelta(hours=6),
    "Last 1 day": dt.timedelta(days=1),
    "Last 7 days": dt.timedelta(days=7),
    "Last 30 days": dt.timedelta(days=30),
    "Custom range": None,
}

range_start, range_end = select_time_range(start_date, end_date, key_prefix="session", presets=session_presets)
query_start_date = str(range_start.date())
query_end_date = str(range_end.date())
traffic_filter: tuple[str, ...] = tuple()


@st.fragment(run_every=60 if auto_refresh else None)
def render_dashboard():
    data = load_dashboard_data(query_start_date, query_end_date, traffic_filter)
    summary = data["summary"]
    funnel = data["funnel"]
    categories = data["categories"]
    session_trend = filter_by_time(data["session_trend"], "session_hour", range_start, range_end)
    health = data["health"]
    timeseries = filter_by_time(data["timeseries"], "session_hour", range_start, range_end)
    anomalies = data["anomalies"]

    if not session_trend.empty:
        summary["total_sessions"] = session_trend["sessions"].sum()

    business_cols = st.columns(4)
    render_kpi_card(business_cols[0], "Sessions", fmt_int(summary.get("total_sessions")), "Latest session view")
    render_kpi_card(business_cols[1], "Avg duration", fmt_seconds(summary.get("avg_session_seconds")), "Business engagement")
    render_kpi_card(business_cols[2], "Cart rate", f"{float(summary.get('cart_rate') or 0):.2%}", "Reached cart")
    render_kpi_card(business_cols[3], "Purchase/session", f"{float(summary.get('conversion_rate') or 0):.2%}", "Purchased sessions")

    business_left, business_right = st.columns(2)
    with business_left:
        st.subheader("Session Funnel")
        if funnel.empty:
            st.info("No funnel data available.")
        else:
            st.plotly_chart(build_funnel_sankey(funnel), width="stretch")

    with business_right:
        st.subheader("Top Category Interest")
        if categories.empty:
            st.info("No category data available.")
        else:
            category_chart = (
                alt.Chart(categories.head(10))
                .mark_bar()
                .encode(
                    x=alt.X("sessions:Q", title="Sessions"),
                    y=alt.Y("top_category:N", sort="-x", title=None),
                    color=alt.Color(
                        "conversion_rate:Q",
                        title="Purchase/session",
                        scale=alt.Scale(range=["#8db5d9", "#c96a50"]),
                    ),
                    tooltip=[
                        alt.Tooltip("top_category:N", title="Category"),
                        alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                        alt.Tooltip("avg_product_views:Q", title="Avg product views", format=",.2f"),
                        alt.Tooltip("conversion_rate:Q", title="Purchase/session", format=".2%"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(category_chart, width="stretch")

    st.subheader("Session and Purchase Trend")
    if session_trend.empty:
        st.info("No session trend data available.")
    else:
        trend_long = session_trend.melt(
            id_vars=["session_hour"],
            value_vars=["sessions", "purchased_sessions"],
            var_name="metric",
            value_name="value",
        )
        trend_chart = (
            alt.Chart(trend_long)
            .mark_line(strokeWidth=2.3)
            .encode(
                x=alt.X("session_hour:T", title=None),
                y=alt.Y("value:Q", title="Sessions"),
                color=alt.Color(
                    "metric:N",
                    title="Metric",
                    scale=alt.Scale(
                        domain=["sessions", "purchased_sessions"],
                        range=["#315f8c", "#d36c42"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("session_hour:T", title="Hour"),
                    alt.Tooltip("metric:N", title="Metric"),
                    alt.Tooltip("value:Q", title="Sessions", format=",.0f"),
                ],
            )
            .properties(height=260)
        )
        st.altair_chart(trend_chart, width="stretch")

    ops_cols = st.columns(4)
    render_kpi_card(ops_cols[0], "Session freshness", fmt_seconds(health.get("session_freshness_seconds")), "Latest processed_at")
    render_kpi_card(ops_cols[1], "Metric versions", fmt_int(health.get("session_metric_versions")), "Raw session_metrics")
    render_kpi_card(ops_cols[2], "Superseded rate", f"{float(health.get('superseded_version_rate') or 0):.2%}", "Late updates")
    render_kpi_card(ops_cols[3], "P95 events/session", fmt_int(health.get("p95_events_per_session")), "Depth quality")

    ops_left, ops_right = st.columns(2)
    with ops_left:
        st.subheader("Sessionization Output Trend")
        if timeseries.empty:
            st.info("No sessionization data available.")
        else:
            base = alt.Chart(timeseries).encode(x=alt.X("session_hour:T", title=None))
            sessions = base.mark_area(color="#8db5d9", opacity=0.65, line={"color": "#315f8c"}).encode(
                y=alt.Y("sessions:Q", title="Sessions"),
                tooltip=[
                    alt.Tooltip("session_hour:T", title="Hour"),
                    alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                    alt.Tooltip("events_in_sessions:Q", title="Events in sessions", format=",.0f"),
                    alt.Tooltip("avg_events_per_session:Q", title="Avg events/session", format=",.2f"),
                ],
            )
            avg_events = base.mark_line(color="#c96a50", strokeWidth=2).encode(
                y=alt.Y("avg_events_per_session:Q", title="Avg events/session")
            )
            st.altair_chart(alt.layer(sessions, avg_events).resolve_scale(y="independent").properties(height=280), width="stretch")

    with ops_right:
        st.subheader("Session Quality Snapshot")
        if anomalies.empty:
            st.info("No anomaly data available.")
        else:
            anomaly_chart = (
                alt.Chart(anomalies)
                .mark_bar(color="#c96a50")
                .encode(
                    x=alt.X("sessions:Q", title="Sessions"),
                    y=alt.Y("check_name:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("check_name:N", title="Check"),
                        alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                    ],
                )
                .properties(height=220)
            )
            st.altair_chart(anomaly_chart, width="stretch")

        state_rows = pd.DataFrame(
            [
                {"Check": "Latest session_end", "Value": str(health.get("latest_session_end") or "None")},
                {"Check": "Latest version_emitted_at", "Value": str(health.get("latest_version_emitted_at") or "None")},
                {"Check": "Missing session_id", "Value": fmt_int(health.get("missing_session_id"))},
                {"Check": "Negative durations", "Value": fmt_int(health.get("negative_duration_sessions"))},
            ]
        )
        st.dataframe(state_rows, width="stretch", hide_index=True)


render_dashboard()
