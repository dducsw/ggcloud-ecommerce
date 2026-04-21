import altair as alt
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


st.title("Sessions")

date_range = st.sidebar.date_input(
    "Date range",
    value=default_date_range(),
    key="sessions_dates_v2",
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
    key="sessions_sources_v2",
)
traffic_filter = selected_sources if selected_sources else traffic_options

summary = data_provider.get_session_summary(start_date, end_date, traffic_filter)
funnel_df = data_provider.get_conversion_funnel(start_date, end_date, traffic_filter)
duration_df = data_provider.get_session_duration_histogram(start_date, end_date, traffic_filter)
channel_cvr_df = data_provider.get_cvr_by_channel(start_date, end_date, traffic_filter)
browser_cvr_df = data_provider.get_cvr_by_browser(start_date, end_date, traffic_filter)
category_df = data_provider.get_top_categories(start_date, end_date, traffic_filter)
quality_df = data_provider.get_session_quality(start_date, end_date, traffic_filter)
popular_pages_df = data_provider.get_popular_pages(start_date, end_date, traffic_filter)

kpi_cols = st.columns(6)
render_kpi_card(kpi_cols[0], "Sessions", f"{int(summary.get('total_sessions') or 0):,}", "Total sessions in range")
render_kpi_card(kpi_cols[1], "Avg duration", f"{float(summary.get('avg_session_seconds') or 0) / 60:.1f} min", "Average session length")
render_kpi_card(kpi_cols[2], "Median duration", f"{float(summary.get('median_session_seconds') or 0) / 60:.1f} min", "Median session length")
render_kpi_card(kpi_cols[3], "Avg events/session", f"{float(summary.get('avg_event_count') or 0):.2f}", "Interaction depth")
render_kpi_card(kpi_cols[4], "Cart rate", f"{float(summary.get('cart_rate') or 0):.2%}", "Sessions that reached cart")
render_kpi_card(kpi_cols[5], "CVR", f"{float(summary.get('conversion_rate') or 0):.2%}", "Sessions that purchased")

top_left, top_right = st.columns((1.15, 1))
with top_left:
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

with top_right:
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

mid_left, mid_right = st.columns(2)
with mid_left:
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

with mid_right:
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

bottom_left, bottom_right = st.columns((1.2, 1))
with bottom_left:
    st.subheader("Top categories")
    st.dataframe(category_df, width="stretch", hide_index=True)

with bottom_right:
    st.subheader("Session quality by source and browser")
    st.dataframe(quality_df, width="stretch", hide_index=True)

st.subheader("Popular pages")
st.dataframe(popular_pages_df, width="stretch", hide_index=True)
