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
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            "ops_kpis": executor.submit(data_provider.get_ops_kpis, start_date, end_date),
            "inventory_kpis": executor.submit(data_provider.get_inventory_kpis, start_date, end_date),
            "inventory": executor.submit(data_provider.get_inventory_status, start_date, end_date),
            "inventory_age": executor.submit(data_provider.get_inventory_age_buckets, start_date, end_date),
            "inventory_dc": executor.submit(data_provider.get_inventory_by_distribution_center, start_date, end_date),
            "inventory_segments": executor.submit(data_provider.get_inventory_by_product_segment, start_date, end_date),
            "inventory_flow": executor.submit(data_provider.get_inventory_flow, start_date, end_date),
            "delivery_histogram": executor.submit(data_provider.get_delivery_histogram, start_date, end_date),
        }
        return {key: future.result() for key, future in futures.items()}


def resolve_active_window(window_days: int = 30) -> tuple[str, str]:
    active_start = st.session_state.get("start_date")
    active_end = st.session_state.get("end_date")

    if not active_start or not active_end:
        active_start, active_end = data_provider.get_default_date_range(window_days=window_days)

    return str(active_start), str(active_end)


def normalize_money_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df

    normalized = df.copy()
    values = pd.concat(
        [pd.to_numeric(normalized[column], errors="coerce") for column in columns if column in normalized],
        ignore_index=True,
    ).dropna()
    p95 = float(values.quantile(0.95)) if not values.empty else 0
    scale = 1_000_000_000 if p95 > 1_000_000 else 1

    for column in columns:
        if column in normalized:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0) / scale

    return normalized


@st.fragment
def render_dashboard() -> None:
    data = load_dashboard_data(query_start_date, query_end_date)
    ops_df1, ops_df2 = data["ops_kpis"]
    inv_kpi_df = normalize_money_columns(data["inventory_kpis"], ["available_cost"])
    inv_df = normalize_money_columns(data["inventory"], ["inventory_cost"])
    inv_age_df = normalize_money_columns(data["inventory_age"], ["inventory_cost"])
    inv_dc_df = normalize_money_columns(data["inventory_dc"], ["available_cost"])
    inv_segments_df = normalize_money_columns(data["inventory_segments"], ["available_cost"])
    inv_flow_df = data["inventory_flow"]
    del_hist = data["delivery_histogram"]

    delivery_kpis = ops_df1.iloc[0].to_dict() if not ops_df1.empty else {}
    return_kpis = ops_df2.iloc[0].to_dict() if not ops_df2.empty else {}
    inventory_kpis = inv_kpi_df.iloc[0].to_dict() if not inv_kpi_df.empty else {}

    ops_cols = st.columns(3)
    render_kpi_card(ops_cols[0], "Avg Delivery Time", f"{float(delivery_kpis.get('avg_delivery_days') or 0):,.1f} days", "Order to delivery")
    render_kpi_card(ops_cols[1], "Delayed Order Rate", f"{float(delivery_kpis.get('delayed_rate') or 0):.1%}", "Delivery above target")
    render_kpi_card(ops_cols[2], "Return Rate", f"{float(return_kpis.get('return_rate') or 0):.1%}", "Returned items")

    inventory_cols = st.columns(3)
    render_kpi_card(inventory_cols[0], "Available Items", fmt_int(inventory_kpis.get("available_items")), "Unsold inventory")
    render_kpi_card(inventory_cols[1], "Slow-Moving Items", fmt_int(inventory_kpis.get("slow_moving_items")), "180+ days in stock")
    render_kpi_card(inventory_cols[2], "Sell-through Rate", f"{float(inventory_kpis.get('sell_through_rate') or 0):.1%}", "Sold / inventory")

    ops_left, ops_right = st.columns(2)
    with ops_left:
        st.subheader("Inventory Status")
        if inv_df.empty:
            st.info("No inventory status data available.")
        else:
            chart = (
                alt.Chart(inv_df)
                .mark_bar()
                .encode(
                    x=alt.X("status:N", title=None),
                    y=alt.Y("item_count:Q", title="Items"),
                    color=alt.Color("status:N", title="Status", scale=alt.Scale(range=["#315f8c", "#c96a50"])),
                    tooltip=[
                        alt.Tooltip("status:N", title="Status"),
                        alt.Tooltip("item_count:Q", title="Items", format=",.0f"),
                        alt.Tooltip("avg_days_in_inv:Q", title="Avg days in inventory", format=",.1f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")

    with ops_right:
        st.subheader("Inventory Status Share")
        if inv_df.empty:
            st.info("No inventory mix data available.")
        else:
            mix_chart = (
                alt.Chart(inv_df)
                .mark_arc(innerRadius=65, outerRadius=115)
                .encode(
                    theta=alt.Theta("item_count:Q"),
                    color=alt.Color("status:N", title="Status", scale=alt.Scale(range=["#315f8c", "#c96a50"])),
                    tooltip=[
                        alt.Tooltip("status:N", title="Status"),
                        alt.Tooltip("item_count:Q", title="Items", format=",.0f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(mix_chart, width="stretch")

    logistics_left, logistics_right = st.columns(2)
    with logistics_left:
        st.subheader("Inventory Age Distribution")
        if inv_age_df.empty:
            st.info("No inventory age data available.")
        else:
            age_chart = (
                alt.Chart(inv_age_df)
                .mark_bar(color="#8db5d9")
                .encode(
                    x=alt.X("age_bucket:N", sort=inv_age_df["age_bucket"].tolist(), title="Age bucket"),
                    y=alt.Y("item_count:Q", title="Items"),
                    tooltip=[
                        alt.Tooltip("age_bucket:N", title="Age"),
                        alt.Tooltip("item_count:Q", title="Items", format=",.0f"),
                        alt.Tooltip("inventory_cost:Q", title="Inventory cost", format=",.0f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(age_chart, width="stretch")

    with logistics_right:
        st.subheader("Inventory Created vs Sold")
        if inv_flow_df.empty:
            st.info("No inventory flow data available for the selected period.")
        else:
            flow_long = inv_flow_df.melt(
                id_vars=["date"],
                value_vars=["created_items", "sold_items"],
                var_name="metric",
                value_name="items",
            )
            flow_chart = (
                alt.Chart(flow_long)
                .mark_line(strokeWidth=2.3)
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y("items:Q", title="Items"),
                    color=alt.Color(
                        "metric:N",
                        title="Metric",
                        scale=alt.Scale(domain=["created_items", "sold_items"], range=["#315f8c", "#c96a50"]),
                    ),
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("metric:N", title="Metric"),
                        alt.Tooltip("items:Q", title="Items", format=",.0f"),
                    ],
                )
                .properties(height=300)
            )
            st.altair_chart(flow_chart, width="stretch")

    dc_left, dc_right = st.columns([1, 1])
    with dc_left:
        st.subheader("Inventory by Distribution Center")
        if inv_dc_df.empty:
            st.info("No distribution center inventory data available.")
        else:
            top_dc = inv_dc_df.head(12).copy()
            dc_chart = (
                alt.Chart(top_dc)
                .mark_bar()
                .encode(
                    x=alt.X("available_items:Q", title="Available items"),
                    y=alt.Y("distribution_center_name:N", sort="-x", title=None),
                    color=alt.Color(
                        "slow_moving_items:Q",
                        title="Slow-moving",
                        scale=alt.Scale(range=["#8db5d9", "#c96a50"]),
                    ),
                    tooltip=[
                        alt.Tooltip("distribution_center_name:N", title="DC"),
                        alt.Tooltip("available_items:Q", title="Available", format=",.0f"),
                        alt.Tooltip("slow_moving_items:Q", title="Slow-moving", format=",.0f"),
                        alt.Tooltip("available_cost:Q", title="Available cost", format=",.0f"),
                    ],
                )
                .properties(height=360)
            )
            st.altair_chart(dc_chart, width="stretch")

    with dc_right:
        st.subheader("Distribution Center Stock Map")
        if inv_dc_df.empty:
            st.info("No distribution center map data available.")
        else:
            map_df = inv_dc_df[
                (inv_dc_df["latitude"].notna())
                & (inv_dc_df["longitude"].notna())
                & (inv_dc_df["latitude"] != 0)
                & (inv_dc_df["longitude"] != 0)
            ].copy()
            if map_df.empty:
                st.info("No valid distribution center coordinates available.")
            else:
                max_items = float(map_df["available_items"].max() or 1)
                map_df["radius"] = 35000 + ((map_df["available_items"].astype(float) / max_items) ** 0.55) * 180000
                map_df["fill_color"] = map_df["slow_moving_items"].map(
                    lambda value: [207, 55, 24, int(95 + 145 * min(float(value or 0) / max_items, 1))]
                )
                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=map_df,
                    get_position="[longitude, latitude]",
                    get_radius="radius",
                    get_fill_color="fill_color",
                    pickable=True,
                    opacity=0.78,
                    stroked=True,
                    get_line_color=[120, 25, 12, 180],
                    line_width_min_pixels=1,
                )
                deck = pdk.Deck(
                    map_style=None,
                    initial_view_state=pdk.ViewState(
                        latitude=float(map_df["latitude"].mean()),
                        longitude=float(map_df["longitude"].mean()),
                        zoom=2.4,
                    ),
                    layers=[layer],
                    tooltip={
                        "html": "<b>{distribution_center_name}</b><br/>Available: {available_items}<br/>Slow-moving: {slow_moving_items}<br/>Cost: ${available_cost}",
                        "style": {"backgroundColor": "#172231", "color": "white"},
                    },
                )
                st.pydeck_chart(deck, width="stretch", height=360)

    st.subheader("Inventory by Product Segment")
    if inv_segments_df.empty:
        st.info("No product segment inventory data available.")
    else:
        segment_chart = (
            alt.Chart(inv_segments_df.head(18))
            .mark_bar()
            .encode(
                x=alt.X("available_items:Q", title="Available items"),
                y=alt.Y("category:N", sort="-x", title=None),
                color=alt.Color("department:N", title="Department", scale=alt.Scale(range=["#315f8c", "#c96a50", "#8db5d9"])),
                tooltip=[
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("department:N", title="Department"),
                    alt.Tooltip("available_items:Q", title="Available", format=",.0f"),
                    alt.Tooltip("slow_moving_items:Q", title="Slow-moving", format=",.0f"),
                    alt.Tooltip("available_cost:Q", title="Available cost", format=",.0f"),
                ],
            )
            .properties(height=360)
        )
        st.altair_chart(segment_chart, width="stretch")

    st.subheader("Delivery Duration Distribution")
    if del_hist.empty:
        st.info("No delivery duration data available for the selected period.")
    else:
        duration_chart = (
            alt.Chart(del_hist)
            .mark_bar(color="#8db5d9")
            .encode(
                x=alt.X("duration_bucket:N", sort=del_hist["duration_bucket"].tolist(), title="Delivery duration"),
                y=alt.Y("orders:Q", title="Orders"),
                tooltip=[
                    alt.Tooltip("duration_bucket:N", title="Duration"),
                    alt.Tooltip("orders:Q", title="Orders", format=",.0f"),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(duration_chart, width="stretch")

    st.subheader("Cumulative Delivered Orders")
    if del_hist.empty:
        st.info("No cumulative delivery data available.")
    else:
        cumulative = del_hist.sort_values("delivery_duration_days").copy()
        cumulative["cumulative_orders"] = cumulative["orders"].cumsum()
        chart = (
            alt.Chart(cumulative)
            .mark_line(point=True, color="#315f8c", strokeWidth=2.3)
            .encode(
                x=alt.X("delivery_duration_days:Q", title="Delivery days"),
                y=alt.Y("cumulative_orders:Q", title="Cumulative orders"),
                tooltip=[
                    alt.Tooltip("delivery_duration_days:Q", title="Delivery days", format=",.0f"),
                    alt.Tooltip("cumulative_orders:Q", title="Cumulative orders", format=",.0f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, width="stretch")


apply_theme()
st.title("Inventory & Fulfillment")
st.caption("Inventory health, distribution center stock, and delivery reliability for the selected business window.")

with st.sidebar:
    st.markdown("---")
    st.subheader("Inventory controls")
    if st.button("Refresh inventory view"):
        st.cache_data.clear()
        st.rerun()

start_date, end_date = resolve_active_window(window_days=30)
range_start, range_end = select_time_range(start_date, end_date, key_prefix="global")
query_start_date = str(range_start.date())
query_end_date = str(range_end.date())

render_dashboard()
