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
    palette = ["#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"]

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
                    "color": "rgba(59, 130, 246, 0.2)",
                },
            )
        ]
    )
    fig.update_layout(
        height=280,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#0f172a", "size": 13},
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


def resolve_active_window(window_days: int = 1) -> tuple[str, str]:
    active_start = st.session_state.get("start_date")
    active_end = st.session_state.get("end_date")
    if not active_start or not active_end:
        active_start, active_end = data_provider.get_default_date_range(window_days=window_days)
    return str(active_start), str(active_end)


session_presets = {
    "Last 1h": dt.timedelta(hours=1),
    "Last 6h": dt.timedelta(hours=6),
    "Last 1d": dt.timedelta(days=1),
    "Last 7d": dt.timedelta(days=7),
    "Custom": None,
}

from utils.theme import render_page_header, render_section_header
apply_theme()
render_page_header("Session Analysis", "In-depth exploration of user journeys, session quality, and conversion paths.", icon="explore")

with st.sidebar:
    st.markdown("---")
    st.subheader("Session controls")
    auto_refresh = st.toggle("Auto-refresh (60s)", value=True)
    if st.button("Refresh view"):
        st.cache_data.clear()
        st.rerun()

start_date, end_date = resolve_active_window(window_days=1)
range_start, range_end = select_time_range(
    str(start_date), 
    str(end_date), 
    key_prefix="session", 
    presets=session_presets, 
    reference_time=data_provider.get_latest_session_timestamp(),
    default_index=2
)
query_start_date = str(range_start.date())
query_end_date = str(range_end.date())
traffic_filter: tuple[str, ...] = tuple()


@st.fragment(run_every=60 if auto_refresh else None)
def render_dashboard():
    data = load_dashboard_data(query_start_date, query_end_date, traffic_filter)
    summary = data["summary"]
    funnel = data["funnel"]
    categories = data["categories"]
    session_trend = filter_by_time(data["session_trend"], "session_hour", range_start, range_end, freq="1H")
    health = data["health"]
    timeseries = filter_by_time(data["timeseries"], "session_hour", range_start, range_end, freq="1H")
    anomalies = data["anomalies"]

    if not session_trend.empty:
        summary["total_sessions"] = session_trend["sessions"].sum()

    render_section_header("Session Insights", icon="insights")
    business_cols = st.columns(4)
    render_kpi_card(business_cols[0], "Sessions", fmt_int(summary.get("total_sessions")), "In selection")
    render_kpi_card(business_cols[1], "Avg duration", fmt_seconds(summary.get("avg_session_seconds")), "Per session")
    render_kpi_card(business_cols[2], "Cart rate", f"{float(summary.get('cart_rate') or 0):.2%}", "Added to cart")
    render_kpi_card(business_cols[3], "Conv. Rate", f"{float(summary.get('conversion_rate') or 0):.2%}", "Purchases")

    col_l, col_r = st.columns(2)
    with col_l:
        render_section_header("Conversion Funnel", icon="account_tree")
        if funnel.empty:
            st.info("No data.")
        else:
            st.plotly_chart(build_funnel_sankey(funnel), use_container_width=True)

    with col_r:
        render_section_header("Top Category Interest", icon="pie_chart")
        if categories.empty:
            st.info("No data.")
        else:
            chart = (
                alt.Chart(categories.head(8))
                .mark_arc(innerRadius=60, outerRadius=110, cornerRadius=4)
                .encode(
                    theta=alt.Theta("sessions:Q"),
                    color=alt.Color("top_category:N", scale=alt.Scale(scheme="blues"), title=None),
                    tooltip=[
                        alt.Tooltip("top_category:N", title="Category"),
                        alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                    ]
                )
                .properties(height=280)
            )
            st.altair_chart(chart, width="stretch")

    render_section_header("Session & Purchase Volume", icon="show_chart")
    if session_trend.empty:
        st.info("No trend data.")
    else:
        base = alt.Chart(session_trend).encode(x=alt.X("session_hour:T", title=None))
        session_line = base.mark_area(color="#3b82f6", opacity=0.3).encode(y=alt.Y("sessions:Q", title="Volume"))
        purchase_line = base.mark_line(color="#ef4444", strokeWidth=2).encode(y=alt.Y("purchased_sessions:Q", title="Purchases"))
        st.altair_chart(alt.layer(session_line, purchase_line).resolve_scale(y="independent").properties(height=260), width="stretch")

    render_section_header("Sessionization Quality", icon="admin_panel_settings")
    ops_cols = st.columns(4)
    render_kpi_card(ops_cols[0], "Freshness", fmt_seconds(health.get("session_freshness_seconds")), "Metric lag")
    render_kpi_card(ops_cols[1], "Metric versions", fmt_int(health.get("session_metric_versions")), "Output count")
    render_kpi_card(ops_cols[2], "Superseded", f"{float(health.get('superseded_version_rate') or 0):.2%}", "Update rate")
    render_kpi_card(ops_cols[3], "P95 Depth", fmt_int(health.get("p95_events_per_session")), "Events/session")


render_dashboard()
