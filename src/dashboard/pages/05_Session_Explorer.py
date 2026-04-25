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
def load_sessions_data(start_date: str, end_date: str, traffic_filter: tuple[str, ...]) -> dict:
    traffic_sources = list(traffic_filter)
    return {
        "summary": data_provider.get_session_summary(start_date, end_date, traffic_sources),
        "timeseries_df": data_provider.get_session_timeseries(start_date, end_date, traffic_sources),
        "funnel_df": data_provider.get_conversion_funnel(start_date, end_date, traffic_sources),
        "dropoff_df": data_provider.get_funnel_dropoff(start_date, end_date, traffic_sources),
        "duration_df": data_provider.get_session_duration_histogram(start_date, end_date, traffic_sources),
        "channel_cvr_df": data_provider.get_cvr_by_channel(start_date, end_date, traffic_sources),
        "browser_cvr_df": data_provider.get_cvr_by_browser(start_date, end_date, traffic_sources),
        "category_df": data_provider.get_top_categories(start_date, end_date, traffic_sources),
        "quality_df": data_provider.get_session_quality(start_date, end_date, traffic_sources),
        "popular_pages_df": data_provider.get_popular_pages(start_date, end_date, traffic_sources),
    }


apply_theme()
st.title("🕵️ Session Explorer")

active_start = st.session_state.get('start_date')
active_end = st.session_state.get('end_date')

if not active_start or not active_end:
    active_start, active_end = data_provider.get_default_date_range(window_days=1)
    active_start, active_end = str(active_start), str(active_end)

start_date = str(active_start)
end_date = str(active_end)
traffic_filter = []

session_data = load_sessions_data(start_date, end_date, traffic_filter)
summary = session_data["summary"]
timeseries_df = session_data["timeseries_df"]
funnel_df = session_data["funnel_df"]
dropoff_df = session_data["dropoff_df"]
duration_df = session_data["duration_df"]
channel_cvr_df = session_data["channel_cvr_df"]
browser_cvr_df = session_data["browser_cvr_df"]
category_df = session_data["category_df"]
quality_df = session_data["quality_df"]
popular_pages_df = session_data["popular_pages_df"]

kpi_cols = st.columns(6)
render_kpi_card(kpi_cols[0], "Sessions", f"{int(summary.get('total_sessions') or 0):,}", "Total sessions in range")
render_kpi_card(kpi_cols[1], "Avg duration", f"{float(summary.get('avg_session_seconds') or 0) / 60:.1f} min", "Average session length")
render_kpi_card(kpi_cols[2], "Median duration", f"{float(summary.get('median_session_seconds') or 0) / 60:.1f} min", "Median session length")
render_kpi_card(kpi_cols[3], "Avg events/session", f"{float(summary.get('avg_event_count') or 0):.2f}", "Interaction depth")
render_kpi_card(kpi_cols[4], "Cart rate", f"{float(summary.get('cart_rate') or 0):.2%}", "Sessions that reached cart")
render_kpi_card(kpi_cols[5], "CVR", f"{float(summary.get('conversion_rate') or 0):.2%}", "Sessions that purchased")

top_left, top_right = st.columns((1.3, 1))
with top_left:
    st.subheader("Sessions and purchases by hour")
    if timeseries_df.empty:
        st.info("No session timeseries data available.")
    else:
        base = alt.Chart(timeseries_df).encode(x=alt.X("session_hour:T", title=None))
        sessions_line = base.mark_line(color="#315f8c", strokeWidth=2.4).encode(
            y=alt.Y("sessions:Q", title="Sessions"),
            tooltip=[
                alt.Tooltip("session_hour:T", title="Hour"),
                alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                alt.Tooltip("purchased_sessions:Q", title="Purchased sessions", format=",.0f"),
                alt.Tooltip("avg_session_seconds:Q", title="Avg duration (s)", format=",.0f"),
            ],
        )
        purchased_line = base.mark_line(color="#d36c42", strokeWidth=2.1).encode(
            y=alt.Y("purchased_sessions:Q", title="Purchased sessions")
        )
        session_chart = alt.layer(sessions_line, purchased_line).resolve_scale(y="independent").properties(height=300)
        st.altair_chart(session_chart, width="stretch")

with top_right:
    st.subheader("Session operating notes")
    notes_df = pd.DataFrame(
        [
            {"Metric": "Average pageviews", "Value": f"{float(summary.get('avg_pageviews') or 0):.2f}"},
            {"Metric": "Average product views", "Value": f"{float(summary.get('avg_product_views') or 0):.2f}"},
            {"Metric": "Sessions with cart", "Value": f"{float(summary.get('cart_rate') or 0):.2%}"},
            {"Metric": "Sessions with purchase", "Value": f"{float(summary.get('conversion_rate') or 0):.2%}"},
        ]
    )
    st.dataframe(notes_df, width="stretch", hide_index=True)

mid_left, mid_right = st.columns((1.15, 1))
with mid_left:
    st.subheader("Conversion funnel")
    if funnel_df.empty:
        st.info("No session funnel data available.")
    else:
        funnel_df = funnel_df.copy()
        funnel_df["stage_label"] = funnel_df.apply(
            lambda row: f"{row['stage']} ({int(row['sessions']):,})",
            axis=1,
        )
        funnel_chart = (
            alt.Chart(funnel_df)
            .mark_bar(color="#4d87b9", size=42)
            .encode(
                x=alt.X("sessions:Q", title="Sessions"),
                y=alt.Y("stage_label:N", sort=None, title=None),
                tooltip=[
                    alt.Tooltip("stage:N", title="Stage"),
                    alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(funnel_chart, width="stretch")

with mid_right:
    st.subheader("Funnel drop-off")
    if dropoff_df.empty:
        st.info("No drop-off data available.")
    else:
        dropoff_df = dropoff_df.copy()
        dropoff_df["dropoff_rate"] = 1 - (dropoff_df["to_sessions"] / dropoff_df["from_sessions"].replace(0, pd.NA))
        dropoff_chart = (
            alt.Chart(dropoff_df)
            .mark_bar(color="#c96a50")
            .encode(
                x=alt.X("dropoff_rate:Q", axis=alt.Axis(format="%"), title="Drop-off rate"),
                y=alt.Y("transition:N", sort=None, title=None),
                tooltip=[
                    alt.Tooltip("transition:N", title="Transition"),
                    alt.Tooltip("from_sessions:Q", title="From sessions", format=",.0f"),
                    alt.Tooltip("to_sessions:Q", title="To sessions", format=",.0f"),
                    alt.Tooltip("dropoff_rate:Q", title="Drop-off", format=".2%"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(dropoff_chart, width="stretch")

third_left, third_right = st.columns((1.15, 1))
with third_left:
    st.subheader("Session duration histogram")
    if duration_df.empty:
        st.info("No session duration data available.")
    else:
        histogram = (
            alt.Chart(duration_df)
            .mark_bar(color="#8db5d9")
            .encode(
                x=alt.X("duration_bucket:N", sort=list(duration_df["duration_bucket"]), title="Duration bucket"),
                y=alt.Y("sessions:Q", title="Sessions"),
                tooltip=[
                    alt.Tooltip("duration_bucket:N", title="Duration"),
                    alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(histogram, width="stretch")

with third_right:
    st.subheader("Top categories")
    st.dataframe(category_df, width="stretch", hide_index=True)

fourth_left, fourth_right = st.columns(2)
with fourth_left:
    st.subheader("CVR by traffic channel")
    if channel_cvr_df.empty:
        st.info("No channel conversion data available.")
    else:
        channel_chart = (
            alt.Chart(channel_cvr_df)
            .mark_bar(color="#315f8c")
            .encode(
                x=alt.X("conversion_rate:Q", axis=alt.Axis(format="%"), title="Conversion rate"),
                y=alt.Y("traffic_source:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("traffic_source:N", title="Channel"),
                    alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                    alt.Tooltip("purchased_sessions:Q", title="Purchased sessions", format=",.0f"),
                    alt.Tooltip("conversion_rate:Q", title="CVR", format=".2%"),
                    alt.Tooltip("avg_session_seconds:Q", title="Avg duration (s)", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(channel_chart, width="stretch")

with fourth_right:
    st.subheader("CVR by browser")
    if browser_cvr_df.empty:
        st.info("No browser conversion data available.")
    else:
        browser_chart = (
            alt.Chart(browser_cvr_df)
            .mark_bar(color="#d36c42")
            .encode(
                x=alt.X("conversion_rate:Q", axis=alt.Axis(format="%"), title="Conversion rate"),
                y=alt.Y("browser:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("browser:N", title="Browser"),
                    alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
                    alt.Tooltip("purchased_sessions:Q", title="Purchased sessions", format=",.0f"),
                    alt.Tooltip("conversion_rate:Q", title="CVR", format=".2%"),
                    alt.Tooltip("avg_session_seconds:Q", title="Avg duration (s)", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(browser_chart, width="stretch")

bottom_left, bottom_right = st.columns((1.1, 1))
with bottom_left:
    st.subheader("Session quality by source and browser")
    st.dataframe(quality_df, width="stretch", hide_index=True)

with bottom_right:
    st.subheader("Popular pages")
    st.dataframe(popular_pages_df, width="stretch", hide_index=True)
