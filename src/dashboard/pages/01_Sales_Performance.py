import concurrent.futures

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from utils.data_provider import data_provider
from utils.filters import fmt_int, render_kpi_card, select_time_range
from utils.theme import apply_theme


@st.cache_data(ttl=300, show_spinner=False)
def load_dashboard_data(start_date: str, end_date: str) -> dict:
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            "kpis": executor.submit(data_provider.get_sales_kpis, start_date, end_date),
            "comparison": executor.submit(data_provider.get_sales_comparison, start_date, end_date),
            "trend": executor.submit(data_provider.get_revenue_trend, start_date, end_date),
            "top_products": executor.submit(data_provider.get_top_products, start_date, end_date),
            "order_values": executor.submit(data_provider.get_order_value_distribution, start_date, end_date),
            "order_status": executor.submit(data_provider.get_order_status_stats, start_date, end_date),
            "order_type": executor.submit(data_provider.get_order_type_stats, start_date, end_date),
            "orders_by_city": executor.submit(data_provider.get_orders_by_city, start_date, end_date),
            "events_daily": executor.submit(data_provider.get_daily_events_and_purchases, start_date, end_date),
        }
        return {key: future.result() for key, future in futures.items()}


def resolve_active_window(window_days: int = 30) -> tuple[str, str]:
    active_start = st.session_state.get("start_date")
    active_end = st.session_state.get("end_date")

    if not active_start or not active_end:
        active_start, active_end = data_provider.get_default_date_range(window_days=window_days)

    return str(active_start), str(active_end)


def normalize_money_values(values: pd.Series) -> tuple[pd.Series, float]:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0)
    p95 = float(numeric.quantile(0.95)) if not numeric.empty else 0
    scale = 1_000_000_000 if p95 > 1_000_000 else 1
    return numeric / scale, scale


@st.fragment
def render_dashboard() -> None:
    data = load_dashboard_data(query_start_date, query_end_date)
    kpi_df = data["kpis"]
    comp_df = data["comparison"]
    trend_df = data["trend"]
    top_products_df = data["top_products"]
    order_values_df = data["order_values"]
    order_status_df = data["order_status"]
    order_type_df = data["order_type"]
    orders_by_city_df = data["orders_by_city"]
    events_daily_df = data["events_daily"]

    kpis = kpi_df.iloc[0].to_dict() if not kpi_df.empty else {}
    comp = comp_df.iloc[0].to_dict() if not comp_df.empty else {}
    
    def fmt_growth(val):
        if pd.isna(val): return None
        return f"{'+' if val >= 0 else ''}{val:.1%}"

    kpi_cols = st.columns(4)
    render_kpi_card(kpi_cols[0], "Revenue", f"${float(kpis.get('revenue') or 0):,.0f}", "Gross sales", delta=fmt_growth(comp.get("revenue_growth")))
    render_kpi_card(kpi_cols[1], "AOV", f"${float(kpis.get('aov') or 0):,.2f}", "Avg order value", delta=fmt_growth(comp.get("aov_growth")))
    render_kpi_card(kpi_cols[2], "Orders", fmt_int(kpis.get("orders")), "Total successful", delta=fmt_growth(comp.get("orders_growth")))
    render_kpi_card(kpi_cols[3], "Margin Rate", f"{float(kpis.get('margin_rate') or 0):.1%}", "Net profitability")

    render_section_header("Revenue and Margin Trend", icon="trending_up")
    if trend_df.empty:
        st.info("No revenue trend data for the selected date range.")
    else:
        trend_long = trend_df.melt(
            id_vars=["date"],
            value_vars=["revenue", "margin"],
            var_name="metric",
            value_name="value",
        )
        chart = (
            alt.Chart(trend_long)
            .mark_area(opacity=0.4, line={"strokeWidth": 2})
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("value:Q", stack=None, title=None),
                color=alt.Color(
                    "metric:N",
                    title=None,
                    scale=alt.Scale(range=["#3b82f6", "#f59e0b"]),
                ),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("metric:N", title="Metric"),
                    alt.Tooltip("value:Q", title="Amount", format="$,.0f"),
                ],
            )
            .properties(height=320)
            .interactive()
        )
        st.altair_chart(chart, width="stretch")

    render_section_header("Daily Event Traffic", icon="stacked_line_chart")
    if events_daily_df.empty:
        st.info("No event traffic data available.")
    else:
        # Create a line chart for events and purchases
        events_base = alt.Chart(events_daily_df).encode(x=alt.X("event_date:T", title=None))
        
        events_line = events_base.mark_line(color="#3b82f6", strokeWidth=3, point=True).encode(
            y=alt.Y("total_events:Q", title="Total Events"),
            tooltip=["event_date:T", "total_events:Q"]
        )
        
        purchases_line = events_base.mark_line(color="#ef4444", strokeWidth=3, point=True).encode(
            y=alt.Y("purchase_events:Q", title="Purchase Events"),
            tooltip=["event_date:T", "purchase_events:Q"]
        )
        
        # Layer them and resolve scales to see both clearly
        combined_chart = alt.layer(events_line, purchases_line).resolve_scale(
            y="independent"
        ).properties(height=300).interactive()
        
        st.altair_chart(combined_chart, width="stretch")

    render_section_header("Top Products by Performance", icon="inventory_2")
    if top_products_df.empty:
        st.info("No product data available for the selected period.")
    else:
        top_products = top_products_df.sort_values("revenue", ascending=False).head(10).copy()
        top_products["display_name"] = top_products["product_name"].str.slice(0, 40)
        
        product_chart = (
            alt.Chart(top_products)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("revenue:Q", title="Revenue ($)"),
                y=alt.Y("display_name:N", sort="-x", title=None),
                color=alt.Color("margin:Q", scale=alt.Scale(scheme="blues"), title="Margin ($)"),
                tooltip=[
                    alt.Tooltip("product_name:N", title="Product"),
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                    alt.Tooltip("margin:Q", title="Margin", format="$,.0f"),
                    alt.Tooltip("items_sold:Q", title="Volume", format=",.0f"),
                ],
            )
            .properties(height=400)
        )
        st.altair_chart(product_chart, width="stretch")

    col_l, col_r = st.columns(2)
    with col_l:
        render_section_header("Order Value Distribution", icon="bar_chart")
        if order_values_df.empty:
            st.info("No order value data.")
        else:
            histogram = (
                alt.Chart(order_values_df)
                .mark_bar(color="#3b82f6", opacity=0.8, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("order_value:Q", bin=alt.Bin(maxbins=25), title="Order Value ($)"),
                    y=alt.Y("count():Q", title="Orders"),
                )
                .properties(height=280)
            )
            st.altair_chart(histogram, width="stretch")

    with col_r:
        render_section_header("Orders by Status", icon="pie_chart")
        if order_status_df.empty:
            st.info("No status data.")
        else:
            status_chart = (
                alt.Chart(order_status_df)
                .mark_arc(innerRadius=70, outerRadius=110, cornerRadius=4)
                .encode(
                    theta=alt.Theta("order_count:Q"),
                    color=alt.Color("status:N", scale=alt.Scale(scheme="tableau10"), title=None),
                    tooltip=[
                        alt.Tooltip("status:N", title="Status"),
                        alt.Tooltip("order_count:Q", title="Order Count", format=",.0f"),
                    ]
                )
                .properties(height=280)
            )
            st.altair_chart(status_chart, width="stretch")

    render_section_header("Customer Geography", icon="public")
    if orders_by_city_df.empty:
        st.info("No location data.")
    else:
        map_df = orders_by_city_df.rename(columns={"latitude": "lat", "longitude": "lon"}).dropna(subset=["lat", "lon"])
        if not map_df.empty:
            view_state = pdk.ViewState(latitude=map_df["lat"].mean(), longitude=map_df["lon"].mean(), zoom=1.5)
            layer = pdk.Layer(
                "ScatterplotLayer",
                map_df,
                get_position="[lon, lat]",
                get_radius=50000,
                get_fill_color=[59, 130, 246, 160],
                pickable=True,
            )
            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=True))


from utils.theme import render_page_header, render_section_header
apply_theme()
render_page_header("Sales Performance", "Executive overview of revenue, margins, and growth trends.", icon="payments")

with st.sidebar:
    st.markdown("---")
    st.subheader("Sales controls")
    if st.button("Refresh sales view"):
        st.cache_data.clear()
        st.rerun()

start_date, end_date = resolve_active_window(window_days=30)
range_start, range_end = select_time_range(start_date, end_date, key_prefix="global")
query_start_date = str(range_start.date())
query_end_date = str(range_end.date())

render_dashboard()
