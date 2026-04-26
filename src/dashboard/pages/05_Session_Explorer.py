import concurrent.futures
import datetime as dt

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data_provider import data_provider
from utils.theme import apply_theme


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


def select_time_range(default_start: str, default_end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    presets = {
        "Last 5 minutes": dt.timedelta(minutes=5),
        "Last 15 minutes": dt.timedelta(minutes=15),
        "Last 30 minutes": dt.timedelta(minutes=30),
        "Last 1 hour": dt.timedelta(hours=1),
        "Last 6 hours": dt.timedelta(hours=6),
        "Last 1 day": dt.timedelta(days=1),
        "Custom range": None,
    }
    with st.sidebar:
        st.markdown("---")
        st.subheader("Time range")
        selected = st.selectbox("Window", list(presets), index=5)

        if selected == "Custom range":
            start_date = st.date_input("Start date", value=pd.to_datetime(default_start).date(), key="session_start_date")
            start_time = st.time_input("Start time", value=dt.time(0, 0), key="session_start_time")
            end_date = st.date_input("End date", value=pd.to_datetime(default_end).date(), key="session_end_date")
            end_time = st.time_input("End time", value=dt.time(23, 59), key="session_end_time")
            start_ts = pd.Timestamp(dt.datetime.combine(start_date, start_time))
            end_ts = pd.Timestamp(dt.datetime.combine(end_date, end_time))
        else:
            end_ts = pd.Timestamp(dt.datetime.combine(pd.to_datetime(default_end).date(), dt.time(23, 59, 59)))
            start_ts = end_ts - presets[selected]

    if start_ts >= end_ts:
        st.warning("Start time must be before end time. Falling back to the last 1 day.")
        end_ts = pd.Timestamp(dt.datetime.combine(pd.to_datetime(default_end).date(), dt.time(23, 59, 59)))
        start_ts = end_ts - dt.timedelta(days=1)
    return start_ts, end_ts


def filter_by_time(df: pd.DataFrame, column: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    filtered = df.copy()
    filtered[column] = pd.to_datetime(filtered[column]).dt.tz_localize(None)
    return filtered[(filtered[column] >= start_ts) & (filtered[column] <= end_ts)]


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
range_start, range_end = select_time_range(start_date, end_date)
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
        st.subheader("Business: session funnel")
        if funnel.empty:
            st.info("No funnel data available.")
        else:
            st.plotly_chart(build_funnel_sankey(funnel), use_container_width=True)

    with business_right:
        st.subheader("Business: top category interest")
        if categories.empty:
            st.info("No category data available.")
        else:
            category_chart = (
                alt.Chart(categories.head(10))
                .mark_arc(innerRadius=60, outerRadius=110)
                .encode(
                    theta=alt.Theta("sessions:Q"),
                    color=alt.Color(
                        "top_category:N",
                        title="Category",
                        scale=alt.Scale(scheme="tableau10"),
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

    st.subheader("Business: sessions and purchases over time")
    if session_trend.empty:
        st.info("No session trend data available.")
    else:
        base = alt.Chart(session_trend).encode(x=alt.X("session_hour:T", title=None))
        session_line = base.mark_line(color="#315f8c", strokeWidth=2.4).encode(
            y=alt.Y("sessions:Q", title="Sessions"),
            tooltip=[
                alt.Tooltip("session_hour:T", title="Hour"),
                alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                alt.Tooltip("purchased_sessions:Q", title="Purchased sessions", format=",.0f"),
            ],
        )
        purchase_line = base.mark_line(color="#d36c42", strokeWidth=2.2).encode(
            y=alt.Y("purchased_sessions:Q", title="Purchased sessions")
        )
        st.altair_chart(
            alt.layer(session_line, purchase_line).resolve_scale(y="independent").properties(height=260),
            width="stretch",
        )

    ops_cols = st.columns(4)
    render_kpi_card(ops_cols[0], "Session freshness", fmt_seconds(health.get("session_freshness_seconds")), "Latest processed_at")
    render_kpi_card(ops_cols[1], "Metric versions", fmt_int(health.get("session_metric_versions")), "Raw session_metrics")
    render_kpi_card(ops_cols[2], "Superseded rate", f"{float(health.get('superseded_version_rate') or 0):.2%}", "Late updates")
    render_kpi_card(ops_cols[3], "P95 events/session", fmt_int(health.get("p95_events_per_session")), "Depth quality")

    ops_left, ops_right = st.columns(2)
    with ops_left:
        st.subheader("Ops: sessionization output")
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
        st.subheader("Ops: session quality checks")
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
