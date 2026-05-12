import concurrent.futures

import altair as alt
import pandas as pd
import streamlit as st

from utils.data_provider import data_provider
from utils.filters import render_kpi_card, select_time_range
from utils.theme import apply_theme


@st.cache_data(ttl=300, show_spinner=False)
def load_dashboard_data(start_date: str, end_date: str, brand_filter: tuple[str, ...]) -> dict:
    brands = list(brand_filter)
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            "category_performance": executor.submit(data_provider.get_category_performance_by_brand, start_date, end_date, brands),
            "category_trend": executor.submit(data_provider.get_category_trend_by_brand, start_date, end_date, brands),
            "product_scatter": executor.submit(data_provider.get_product_scatter_by_brand, start_date, end_date, brands),
            "top_products": executor.submit(data_provider.get_top_products_by_brand, start_date, end_date, brands),
            "brand_performance": executor.submit(data_provider.get_brand_performance_by_brand, start_date, end_date, brands),
            "department_performance": executor.submit(data_provider.get_department_performance_by_brand, start_date, end_date, brands),
            "brand_trend": executor.submit(data_provider.get_brand_trend_by_brand, start_date, end_date, brands),
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
    data = load_dashboard_data(query_start_date, query_end_date, selected_brand_filter)
    cat_perf_df = data["category_performance"]
    scatter_df = data["product_scatter"]
    top_products_df = data["top_products"]
    brand_perf_df = data["brand_performance"]
    dept_perf_df = data["department_performance"]

    total_revenue = float(cat_perf_df["revenue"].sum()) if not cat_perf_df.empty else 0
    total_margin = float(cat_perf_df["margin"].sum()) if not cat_perf_df.empty else 0
    avg_margin_rate = total_margin / total_revenue if total_revenue else 0
    
    top_category = cat_perf_df.iloc[0].to_dict() if not cat_perf_df.empty else {}
    top_brand = brand_perf_df.iloc[0].to_dict() if not brand_perf_df.empty else {}

    kpi_cols = st.columns(4)
    render_kpi_card(kpi_cols[0], "Top Category", str(top_category.get("category") or "n/a"), "Best revenue")
    render_kpi_card(kpi_cols[1], "Total Margin", f"${total_margin:,.0f}", "Net profit")
    render_kpi_card(kpi_cols[2], "Margin Rate", f"{avg_margin_rate:.1%}", "Profitability")
    render_kpi_card(kpi_cols[3], "Top Brand", str(top_brand.get("brand") or "n/a"), "Best revenue")

    render_section_header("Performance by Category & Brand", icon="category")
    col_l, col_r = st.columns(2)
    
    with col_l:
        render_section_header("Category Revenue Mix", icon="splitscreen")
        if cat_perf_df.empty:
            st.info("No data.")
        else:
            chart = (
                alt.Chart(cat_perf_df.head(10))
                .mark_bar(cornerRadiusEnd=4, color="#3b82f6")
                .encode(
                    x=alt.X("revenue:Q", title="Revenue ($)"),
                    y=alt.Y("category:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("category:N", title="Category"),
                        alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                        alt.Tooltip("margin:Q", title="Margin", format="$,.0f"),
                    ]
                )
                .properties(height=320)
            )
            st.altair_chart(chart, width="stretch")

    with col_r:
        render_section_header("Brand Performance", icon="stars")
        if brand_perf_df.empty:
            st.info("No data.")
        else:
            chart = (
                alt.Chart(brand_perf_df.head(10))
                .mark_bar(cornerRadiusEnd=4, color="#f59e0b")
                .encode(
                    x=alt.X("revenue:Q", title="Revenue ($)"),
                    y=alt.Y("brand:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("brand:N", title="Brand"),
                        alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                        alt.Tooltip("margin:Q", title="Margin", format="$,.0f"),
                    ]
                )
                .properties(height=320)
            )
            st.altair_chart(chart, width="stretch")

    render_section_header("Product Profitability Matrix", icon="grid_view")
    if scatter_df.empty:
        st.info("Insufficient product data.")
    else:
        # Create classification lines
        avg_price = scatter_df["avg_price"].mean()
        avg_profit = scatter_df["total_profit"].mean()
        
        scatter_chart = (
            alt.Chart(scatter_df)
            .mark_circle(size=100, opacity=0.6)
            .encode(
                x=alt.X("avg_price:Q", title="Avg Price ($)"),
                y=alt.Y("total_profit:Q", title="Total Profit ($)"),
                color=alt.Color("category:N", title="Category", scale=alt.Scale(scheme="tableau10")),
                size=alt.Size("volume:Q", title="Sales Volume"),
                tooltip=["product_name", "category", "avg_price", "total_profit", "volume"]
            )
            .properties(height=450)
            .interactive()
        )
        
        # Add Quadrant annotations
        st.altair_chart(scatter_chart, width="stretch")
        
        cols = st.columns(4)
        cols[0].markdown("**⭐ Stars**: High Price, High Profit")
        cols[1].markdown("**💰 Cash Cows**: Low Price, High Profit")
        cols[2].markdown("**❓ Question Marks**: High Price, Low Profit")
        cols[3].markdown("**🐕 Dogs**: Low Price, Low Profit")

    render_section_header("Product Inventory & Sales Detail", icon="list_alt")
    if top_products_df.empty:
        st.info("No product details.")
    else:
        detail_df = top_products_df.copy()
        detail_df["margin_pct"] = (detail_df["margin"] / detail_df["revenue"].replace(0, pd.NA)).fillna(0)
        st.dataframe(
            detail_df[["product_name", "category", "brand", "items_sold", "revenue", "margin", "margin_pct"]].sort_values("revenue", ascending=False),
            column_config={
                "revenue": st.column_config.NumberColumn(format="$%.0f"),
                "margin": st.column_config.NumberColumn(format="$%.0f"),
                "margin_pct": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=1),
            },
            width="stretch",
            hide_index=True,
        )


from utils.theme import render_page_header, render_section_header
apply_theme()
render_page_header("Product Performance", "Detailed analysis of product profitability, category mix, and brand contribution.", icon="inventory")

with st.sidebar:
    st.markdown("---")
    st.subheader("Product controls")
    if st.button("Refresh product view"):
        st.cache_data.clear()
        st.rerun()

start_date, end_date = resolve_active_window(window_days=30)
range_start, range_end = select_time_range(start_date, end_date, key_prefix="global")
query_start_date = str(range_start.date())
query_end_date = str(range_end.date())

brand_options = data_provider.get_product_brands(query_start_date, query_end_date)
with st.sidebar:
    st.markdown("---")
    selected_brands = st.multiselect(
        "Brand Filter",
        options=brand_options,
        default=[],
        placeholder="All brands",
        key="product_brand_filter",
    )

selected_brand_filter = tuple(selected_brands)
render_dashboard()
