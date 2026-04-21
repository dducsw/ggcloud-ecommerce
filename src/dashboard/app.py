import datetime as dt

import streamlit as st

from utils.data_provider import data_provider


st.set_page_config(page_title="Clickstream Analysis", layout="wide", initial_sidebar_state="expanded")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 1.2rem;
            max-width: 1400px;
        }
        .metric-card {
            border: 1px solid #d9dee7;
            background: #ffffff;
            border-radius: 4px;
            padding: 16px 18px;
            min-height: 108px;
        }
        .metric-label {
            font-size: 0.85rem;
            color: #5d6b82;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 1.9rem;
            font-weight: 600;
            color: #1e2a3a;
            line-height: 1.1;
        }
        .metric-subtle {
            font-size: 0.82rem;
            color: #6e7b8f;
            margin-top: 8px;
        }
        div[data-testid="stMetric"] {
            border: 1px solid #d9dee7;
            background: #ffffff;
            padding: 14px 16px;
            border-radius: 4px;
        }
        h1, h2, h3 {
            color: #172231;
            letter-spacing: -0.02em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def build_sidebar():
    latest_date = data_provider.get_latest_event_date()
    default_end = latest_date or dt.date.today()
    default_start = default_end - dt.timedelta(days=6)

    st.sidebar.title("Clickstream Analysis")
    st.sidebar.caption("BigQuery source")
    date_range = st.sidebar.date_input(
        "Date range",
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
    st.sidebar.write(f"Dataset: `{data_provider.clickstream_dataset}`")
    st.sidebar.write(f"Latest event date: `{default_end}`")
    return start_date, end_date


def main():
    inject_styles()
    start_date, end_date = build_sidebar()

    st.title("Clickstream Analysis")
    st.caption("Operational dashboard for clickstream monitoring, session quality and conversion flow")

    overview_metrics = data_provider.get_overview_metrics(str(start_date), str(end_date))
    cols = st.columns(4)
    metric_specs = [
        ("Total events", f"{int(overview_metrics.get('total_events', 0)):,}", "Raw deduped events in range"),
        ("Total sessions", f"{int(overview_metrics.get('total_sessions', 0)):,}", "Distinct sessions in range"),
        ("Conversion rate", f"{float(overview_metrics.get('conversion_rate') or 0):.2%}", "Purchases per session"),
        ("Avg. session length", f"{float(overview_metrics.get('avg_session_seconds') or 0) / 60:.1f} min", "Average session duration"),
    ]
    for col, (label, value, subtle) in zip(cols, metric_specs):
        col.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-subtle">{subtle}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        This dashboard is organized into two focused pages:
        Clickstream Overview for operational monitoring, and Sessions for funnel and session-depth analysis.
        Use the page navigation in the sidebar to move between the two views.
        """
    )


if __name__ == "__main__":
    main()
