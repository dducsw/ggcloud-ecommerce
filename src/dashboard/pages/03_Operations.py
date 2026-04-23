import streamlit as st
import plotly.express as px
from utils.data_provider import data_provider
from utils.theme import apply_theme, render_hero

st.set_page_config(page_title="Operations & Logistics", layout="wide")
apply_theme()
render_hero(
    "Operations & Logistics",
    "Track inventory flow, delivery performance and fulfillment reliability.",
    "https://picsum.photos/seed/thelook-ops/120/120",
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

ops_df1, ops_df2 = data_provider.get_ops_kpis(sd, ed)
inv_df = data_provider.get_inventory_status()
del_hist = data_provider.get_delivery_histogram(sd, ed)

if not ops_df1.empty and not ops_df2.empty:
    k1 = ops_df1.iloc[0]
    k2 = ops_df2.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card'><div class='metric-label'>Avg Shipping Time</div><div class='metric-value'>{k1['avg_delivery_days']:,.1f} <span>Days</span></div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-label'>Delayed Order Rate</div><div class='metric-value'>{k1['delayed_rate']:,.1%}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-label'>Return Rate</div><div class='metric-value'>{k2['return_rate']:,.1%}</div></div>", unsafe_allow_html=True)

st.markdown("---")
c_left, c_right = st.columns(2)

with c_left:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Global Inventory Status")
    if not inv_df.empty:
        fig = px.bar(inv_df, x="status", y="item_count", text="item_count",
                     color="status", template="plotly_dark",
                     color_discrete_sequence=["#ab61c8", "#1f77b4"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No inventory status data available.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c_right:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Delivery Duration Distribution (Days)")
    if not del_hist.empty:
        fig = px.bar(del_hist, x="duration_bucket", y="orders",
                     template="plotly_dark", color_discrete_sequence=["#58a6ff"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        fig.update_xaxes(categoryorder='array', categoryarray=del_hist['duration_bucket'].tolist())
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No delivery duration data available.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

c_bottom_left, c_bottom_right = st.columns(2)

with c_bottom_left:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Inventory Mix")
    if not inv_df.empty:
        fig = px.pie(
            inv_df,
            values="item_count",
            names="status",
            hole=0.55,
            template="plotly_dark",
            color_discrete_sequence=["#ab61c8", "#1f77b4"],
        )
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=20, b=0))
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No inventory mix to visualize.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c_bottom_right:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Cumulative Delivered Orders")
    if not del_hist.empty:
        cumulative = del_hist.sort_values("delivery_duration_days").copy()
        cumulative["cumulative_orders"] = cumulative["orders"].cumsum()
        fig = px.line(
            cumulative,
            x="delivery_duration_days",
            y="cumulative_orders",
            markers=True,
            template="plotly_dark",
            color_discrete_sequence=["#58a6ff"],
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Delivery Days",
            yaxis_title="Cumulative Orders",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No cumulative delivery data available.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
