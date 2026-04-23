import streamlit as st
import plotly.express as px
import pandas as pd
from utils.data_provider import data_provider
from utils.theme import apply_theme, render_hero

st.set_page_config(page_title="Executive Sales", layout="wide")
apply_theme()
render_hero(
    "Executive Sales Overview",
    "Revenue, margin and product contribution for the selected business window.",
    "https://picsum.photos/seed/thelook-sales/120/120",
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

kpi_df = data_provider.get_sales_kpis(sd, ed)
trend_df = data_provider.get_revenue_trend(sd, ed)
top_products_df = data_provider.get_top_products(sd, ed)

if not kpi_df.empty:
    kpis = kpi_df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='metric-card'><div class='metric-label'>Total Revenue</div><div class='metric-value'><span>$</span>{kpis['revenue']:,.0f}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-label'>Gross Margin</div><div class='metric-value'><span>$</span>{kpis['margin']:,.0f}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-label'>Margin Rate</div><div class='metric-value'>{kpis['margin_rate']:,.1%}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-card'><div class='metric-label'>Total Orders</div><div class='metric-value'>{kpis['orders']:,}</div></div>", unsafe_allow_html=True)

st.markdown("---")
c_left, c_right = st.columns([2, 1])

with c_left:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Revenue & Margin Trend")
    if not trend_df.empty:
        fig = px.area(trend_df, x="date", y=["revenue", "margin"], 
                      color_discrete_sequence=["#58a6ff", "#bc8cff"],
                      template="plotly_dark")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No revenue trend data for selected date range.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c_right:
    st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
    st.subheader("Top Performers (By Margin)")
    if not top_products_df.empty:
        top_margin = top_products_df.sort_values("margin", ascending=False).head(8)
        fig = px.bar(
            top_margin,
            x="margin",
            y="product_name",
            orientation="h",
            color="margin",
            color_continuous_scale="Blues",
            template="plotly_dark",
        )
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=20, b=0),
            yaxis_title="",
            xaxis_title="Margin",
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<div class='empty-note'>No top product data to display yet.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
st.subheader("Top Products Detail")
if not top_products_df.empty:
    display_df = top_products_df.copy()
    display_df["margin_pct"] = (display_df["margin"] / display_df["revenue"].replace(0, pd.NA)).fillna(0)
    st.dataframe(
        display_df[["product_name", "category", "revenue", "margin", "margin_pct"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.markdown("<div class='empty-note'>No product detail available for selected period.</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
