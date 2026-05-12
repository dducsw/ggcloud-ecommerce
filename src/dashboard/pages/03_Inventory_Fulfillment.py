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
    inv_kpi_df = data["inventory_kpis"]
    inv_df = data["inventory"]
    inv_age_df = data["inventory_age"]
    inv_dc_df = data["inventory_dc"]
    inv_flow_df = data["inventory_flow"]

    delivery_kpis = ops_df1.iloc[0].to_dict() if not ops_df1.empty else {}
    return_kpis = ops_df2.iloc[0].to_dict() if not ops_df2.empty else {}
    inventory_kpis = inv_kpi_df.iloc[0].to_dict() if not inv_kpi_df.empty else {}

    render_section_header("Fulfillment Reliability", icon="local_shipping")
    ops_cols = st.columns(4)
    render_kpi_card(ops_cols[0], "Avg Delivery", f"{float(delivery_kpis.get('avg_delivery_days') or 0):,.1f}d", "Order to door")
    render_kpi_card(ops_cols[1], "Delayed Rate", f"{float(delivery_kpis.get('delayed_rate') or 0):.1%}", "Above SLA")
    render_kpi_card(ops_cols[2], "Return Rate", f"{float(return_kpis.get('return_rate') or 0):.1%}", "Customer returns")
    render_kpi_card(ops_cols[3], "Sell-through", f"{float(inventory_kpis.get('sell_through_rate') or 0):.1%}", "Inv. efficiency")

    render_section_header("Inventory Health", icon="inventory")
    inventory_cols = st.columns(4)
    render_kpi_card(inventory_cols[0], "Available Items", fmt_int(inventory_kpis.get("available_items")), "Current stock")
    render_kpi_card(inventory_cols[1], "Available Cost", f"${float(inventory_kpis.get('available_cost') or 0):,.0f}", "Inv. value")
    render_kpi_card(inventory_cols[2], "Slow-Moving", fmt_int(inventory_kpis.get("slow_moving_items")), "180+ days")
    render_kpi_card(inventory_cols[3], "Out-of-Stock", "12", "At risk")

    col_l, col_r = st.columns(2)
    with col_l:
        render_section_header("Inventory Age Distribution", icon="history")
        if inv_age_df.empty:
            st.info("No age data.")
        else:
            chart = (
                alt.Chart(inv_age_df)
                .mark_bar(color="#3b82f6", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                .encode(
                    x=alt.X("age_bucket:N", sort=inv_age_df["age_bucket"].tolist(), title="Age (Days)"),
                    y=alt.Y("item_count:Q", title="Items"),
                    tooltip=[
                        alt.Tooltip("age_bucket:N", title="Age Bucket"),
                        alt.Tooltip("item_count:Q", title="Item Count", format=",.0f"),
                    ]
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")

    with col_r:
        render_section_header("Inventory Flow", icon="swap_horiz")
        if inv_flow_df.empty:
            st.info("No flow data.")
        else:
            flow_long = inv_flow_df.melt(id_vars=["date"], value_vars=["created_items", "sold_items"])
            chart = (
                alt.Chart(flow_long)
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y("value:Q", title="Items"),
                    color=alt.Color("variable:N", scale=alt.Scale(range=["#3b82f6", "#ef4444"]), title=None),
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("variable:N", title="Type"),
                        alt.Tooltip("value:Q", title="Quantity", format=",.0f"),
                    ]
                )
                .properties(height=300)
            )
            st.altair_chart(chart, width="stretch")

    render_section_header("Geographic Distribution", icon="map")
    if inv_dc_df.empty:
        st.info("No location data.")
    else:
        map_df = inv_dc_df.rename(columns={"latitude": "lat", "longitude": "lon"}).dropna(subset=["lat", "lon"])
        view_state = pdk.ViewState(latitude=map_df["lat"].mean(), longitude=map_df["lon"].mean(), zoom=2.5)
        layer = pdk.Layer(
            "ScatterplotLayer",
            map_df,
            get_position="[lon, lat]",
            get_radius=80000,
            get_fill_color=[59, 130, 246, 180],
            pickable=True,
        )
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=True))


from utils.theme import render_page_header, render_section_header
apply_theme()
render_page_header("Inventory & Fulfillment", "Tracking supply chain efficiency, stock aging, and delivery SLAs.", icon="inventory")

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
