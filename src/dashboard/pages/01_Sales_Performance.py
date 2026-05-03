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
            "trend": executor.submit(data_provider.get_revenue_trend, start_date, end_date),
            "top_products": executor.submit(data_provider.get_top_products, start_date, end_date),
            "order_values": executor.submit(data_provider.get_order_value_distribution, start_date, end_date),
            "order_status": executor.submit(data_provider.get_order_status_stats, start_date, end_date),
            "order_type": executor.submit(data_provider.get_order_type_stats, start_date, end_date),
            "orders_by_city": executor.submit(data_provider.get_orders_by_city, start_date, end_date),
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
    trend_df = data["trend"]
    top_products_df = data["top_products"]
    order_values_df = data["order_values"]
    order_status_df = data["order_status"]
    order_type_df = data["order_type"]
    orders_by_city_df = data["orders_by_city"]

    kpis = kpi_df.iloc[0].to_dict() if not kpi_df.empty else {}
    kpi_cols = st.columns(4)
    render_kpi_card(kpi_cols[0], "Total Revenue", f"${float(kpis.get('revenue') or 0):,.0f}", "Gross sales value")
    render_kpi_card(kpi_cols[1], "Gross Margin", f"${float(kpis.get('margin') or 0):,.0f}", "Revenue - Cost")
    render_kpi_card(kpi_cols[2], "Margin Rate", f"{float(kpis.get('margin_rate') or 0):.1%}", "Profitability ratio")
    render_kpi_card(kpi_cols[3], "Total Orders", fmt_int(kpis.get("orders")), "Success orders")

    st.subheader("Revenue and Margin Trend")
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
            .mark_area(opacity=0.68, line=True)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("value:Q", title="Amount ($)"),
                color=alt.Color(
                    "metric:N",
                    title="Metric",
                    scale=alt.Scale(range=["#315f8c", "#c96a50"]),
                ),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("metric:N", title="Metric"),
                    alt.Tooltip("value:Q", title="Amount", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, width="stretch")

    st.subheader("Top Products by Revenue and Margin")
    if top_products_df.empty:
        st.info("No product data available for the selected period.")
    else:
        top_products = top_products_df.sort_values("revenue", ascending=False).head(12).copy()
        top_products["display_name"] = top_products["product_name"].str.slice(0, 34)
        product_metrics = top_products.melt(
            id_vars=["product_name", "display_name", "category", "items_sold"],
            value_vars=["revenue", "margin"],
            var_name="metric",
            value_name="amount",
        )
        product_chart = (
            alt.Chart(product_metrics)
            .mark_bar()
            .encode(
                x=alt.X("amount:Q", stack="zero", title="Amount ($)"),
                y=alt.Y("display_name:N", sort=top_products["display_name"].tolist(), title=None),
                color=alt.Color(
                    "metric:N",
                    title="Metric",
                    scale=alt.Scale(domain=["revenue", "margin"], range=["#8db5d9", "#c96a50"]),
                ),
                tooltip=[
                    alt.Tooltip("product_name:N", title="Product"),
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("metric:N", title="Metric"),
                    alt.Tooltip("amount:Q", title="Amount", format=",.0f"),
                    alt.Tooltip("items_sold:Q", title="Items sold", format=",.0f"),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(product_chart, width="stretch")

    st.subheader("Order Value Distribution")
    if order_values_df.empty:
        st.info("No order value data available for the selected period.")
    else:
        histogram_df = order_values_df.copy()
        histogram_df["order_value_usd"], _ = normalize_money_values(histogram_df["order_value"])
        histogram_df = histogram_df[histogram_df["order_value_usd"] > 0]
        p99_order_value = histogram_df["order_value_usd"].quantile(0.99) if not histogram_df.empty else 0
        if p99_order_value > 0:
            histogram_df = histogram_df[histogram_df["order_value_usd"] <= p99_order_value]
        if histogram_df.empty:
            st.info("No positive order value data available for the selected period.")
        else:
            histogram = (
                alt.Chart(histogram_df)
                .mark_bar(color="#315f8c")
                .encode(
                    x=alt.X("order_value_usd:Q", bin=alt.Bin(maxbins=30), title="Order value ($)"),
                    y=alt.Y("count():Q", title="Orders"),
                    tooltip=[
                        alt.Tooltip("count():Q", title="Orders", format=",.0f"),
                        alt.Tooltip("order_value_usd:Q", title="Order value", bin=True, format=",.2f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(histogram, width="stretch")

    bar_left, bar_right = st.columns(2)
    with bar_left:
        st.subheader("Orders by Status")
        if order_status_df.empty:
            st.info("No order status data available.")
        else:
            status_chart = (
                alt.Chart(order_status_df)
                .mark_arc(innerRadius=62, outerRadius=118)
                .encode(
                    theta=alt.Theta("order_count:Q"),
                    color=alt.Color(
                        "status:N",
                        title="Status",
                        scale=alt.Scale(range=["#315f8c", "#8db5d9", "#c96a50", "#a6d854", "#7d5ba6"]),
                    ),
                    tooltip=[
                        alt.Tooltip("status:N", title="Status"),
                        alt.Tooltip("order_count:Q", title="Orders", format=",.0f"),
                    ],
                )
                .properties(height=320)
            )
            st.altair_chart(status_chart, width="stretch")

    with bar_right:
        st.subheader("Orders by Type")
        if order_type_df.empty:
            st.info("No order type data available.")
        else:
            type_chart = (
                alt.Chart(order_type_df)
                .mark_arc(innerRadius=62, outerRadius=118)
                .encode(
                    theta=alt.Theta("order_count:Q"),
                    color=alt.Color(
                        "order_type:N",
                        title="Order type",
                        scale=alt.Scale(range=["#c96a50", "#315f8c", "#8db5d9"]),
                    ),
                    tooltip=[
                        alt.Tooltip("order_type:N", title="Order type"),
                        alt.Tooltip("order_count:Q", title="Orders", format=",.0f"),
                    ],
                )
                .properties(height=320)
            )
            st.altair_chart(type_chart, width="stretch")

    st.subheader("Customer Order Locations")
    if orders_by_city_df.empty:
        st.info("No location data available for the selected period.")
    else:
        map_df = orders_by_city_df.copy()
        map_df = map_df[
            (map_df["latitude"].notna())
            & (map_df["longitude"].notna())
            & (map_df["latitude"] != 0)
            & (map_df["longitude"] != 0)
        ].rename(columns={"latitude": "lat", "longitude": "lon"})
        if map_df.empty:
            st.info("No valid latitude/longitude data available for the selected period.")
        else:
            map_df["heat_score"] = (
                map_df["order_count"].astype(float) + map_df["user_count"].astype(float)
            ).clip(lower=1)
            max_score = float(map_df["heat_score"].max() or 1)
            map_df["radius"] = 45000 + ((map_df["heat_score"] / max_score) ** 0.52) * 260000
            map_df["fill_color"] = map_df["heat_score"].map(
                lambda score: [207, 55, 24, int(95 + 145 * ((float(score) / max_score) ** 0.35))]
            )
            view_state = pdk.ViewState(
                latitude=float(map_df["lat"].mean()),
                longitude=float(map_df["lon"].mean()),
                zoom=2.2,
                pitch=0,
            )
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_df,
                get_position="[lon, lat]",
                get_radius="radius",
                get_fill_color="fill_color",
                pickable=True,
                opacity=0.82,
                stroked=True,
                get_line_color=[120, 25, 12, 180],
                line_width_min_pixels=1,
            )
            deck = pdk.Deck(
                map_style=None,
                initial_view_state=view_state,
                layers=[layer],
                tooltip={
                    "html": "<b>{city}</b><br/>Orders: {order_count}<br/>Users: {user_count}",
                    "style": {"backgroundColor": "#172231", "color": "white"},
                },
            )
            st.pydeck_chart(
                deck,
                width="stretch",
                height=560,
            )


apply_theme()
st.title("Sales Performance")
st.caption("Revenue, margin and product contribution for the selected business window.")

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
