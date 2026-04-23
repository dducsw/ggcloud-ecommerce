import streamlit as st
import plotly.express as px
import datetime as dt
from utils.data_provider import data_provider
from utils.theme import apply_theme, render_hero

st.set_page_config(page_title="Marketing & Audience", layout="wide")
apply_theme()
render_hero(
    "Marketing & Audience",
    "Understand session quality, source conversion and customer composition.",
    "https://picsum.photos/seed/thelook-marketing/120/120",
)

def resolve_date_window():
    sd = st.session_state.get("start_date")
    ed = st.session_state.get("end_date")
    if sd and ed:
        return sd, ed
    start_date, end_date = data_provider.get_default_date_range(window_days=30)
    st.session_state["start_date"] = str(start_date)
    st.session_state["end_date"] = str(end_date)
    return str(start_date), str(end_date)


sd, ed = resolve_date_window()

m_kpis = data_provider.get_marketing_kpis(sd, ed)
segments = data_provider.get_user_segments()
traffic = data_provider.get_traffic_cvr(sd, ed)
traffic_note = None

if traffic.empty or traffic["sessions"].sum() == 0:
    latest_traffic_date = data_provider.get_latest_traffic_date()
    if latest_traffic_date is not None:
        fallback_traffic = data_provider.get_traffic_cvr_latest_window(latest_traffic_date)
        if not fallback_traffic.empty and fallback_traffic["sessions"].sum() > 0:
            traffic = fallback_traffic
            start_fallback = latest_traffic_date - dt.timedelta(days=29)
            traffic_note = (
                f"No traffic records for selected range ({sd} to {ed}). "
                f"Showing latest 30-day traffic window: {start_fallback} to {latest_traffic_date}."
            )

if not m_kpis.empty:
    kpis = m_kpis.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='metric-card'><div class='metric-label'>Total Users</div><div class='metric-value'>{kpis['total_users']:,}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-label'>Total Sessions</div><div class='metric-value'>{kpis['total_sessions']:,}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-label'>Checkouts</div><div class='metric-value'><span>🛒</span>{kpis['checkout_events']:,}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-card'><div class='metric-label'>Session CVR</div><div class='metric-value'>{kpis['cvr']:,.2%}</div></div>", unsafe_allow_html=True)

st.markdown("---")
c_top1, c_top2 = st.columns(2)

with c_top1:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Customer Lifecycle Status")
    if not segments.empty:
        lifecycles = segments.groupby('customer_status')['user_count'].sum().reset_index()
        fig = px.pie(lifecycles, values='user_count', names='customer_status', hole=0.6,
                     color_discrete_sequence=px.colors.qualitative.Pastel,
                     template="plotly_dark")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No customer segment data available.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c_top2:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Age Demographics")
    if not segments.empty:
        ages = segments.groupby('age_group')['user_count'].sum().reset_index()
        fig = px.pie(ages, values='user_count', names='age_group', hole=0.6,
                     color_discrete_sequence=px.colors.qualitative.Set3,
                     template="plotly_dark")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No age demographic data available.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
st.subheader("Traffic Sources vs Conversion")
if traffic_note:
    st.info(traffic_note)
if not traffic.empty:
    fig = px.bar(traffic, x="traffic_source", y="sessions", color="cvr",
                 color_continuous_scale="Tealgrn", template="plotly_dark")
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", coloraxis_colorbar_title="CVR")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.markdown("<div class='empty-note'>No traffic data in selected date range.</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

c_bottom_left, c_bottom_right = st.columns(2)

with c_bottom_left:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Sessions by Source")
    if not traffic.empty:
        by_sessions = traffic.sort_values("sessions", ascending=False).head(8)
        fig = px.bar(
            by_sessions,
            x="traffic_source",
            y="sessions",
            text="sessions",
            template="plotly_dark",
            color_discrete_sequence=["#2fb7b9"],
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No session-by-source data available.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c_bottom_right:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Source Efficiency Map")
    if not traffic.empty:
        fig = px.scatter(
            traffic,
            x="sessions",
            y="cvr",
            size="purchases",
            color="traffic_source",
            template="plotly_dark",
            hover_data=["purchases"],
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No efficiency map available.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
