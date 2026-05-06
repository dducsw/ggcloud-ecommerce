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
    cat_perf_df = normalize_money_columns(data["category_performance"], ["revenue", "margin"])
    cat_trend_df = normalize_money_columns(data["category_trend"], ["revenue"])
    scatter_df = normalize_money_columns(data["product_scatter"], ["avg_price", "total_profit"])
    top_products_df = normalize_money_columns(data["top_products"], ["revenue", "margin"])
    brand_perf_df = normalize_money_columns(data["brand_performance"], ["revenue", "margin"])
    dept_perf_df = normalize_money_columns(data["department_performance"], ["revenue", "margin"])
    brand_trend_df = normalize_money_columns(data["brand_trend"], ["revenue"])

    total_revenue = float(cat_perf_df["revenue"].sum()) if not cat_perf_df.empty else 0
    total_margin = float(cat_perf_df["margin"].sum()) if not cat_perf_df.empty else 0
    avg_margin_rate = total_margin / total_revenue if total_revenue else 0
    top_category = cat_perf_df.iloc[0].to_dict() if not cat_perf_df.empty else {}
    top_brand = brand_perf_df.iloc[0].to_dict() if not brand_perf_df.empty else {}
    top_department = dept_perf_df.iloc[0].to_dict() if not dept_perf_df.empty else {}

    kpi_cols = st.columns(3)
    render_kpi_card(kpi_cols[0], "Top Category", str(top_category.get("category") or "n/a"), f"${float(top_category.get('revenue') or 0):,.0f} revenue")
    render_kpi_card(kpi_cols[1], "Product Revenue", f"${total_revenue:,.0f}", "Sum of sale price")
    render_kpi_card(kpi_cols[2], "Product Margin Rate", f"{avg_margin_rate:.1%}", "Profit / sales price")

    secondary_kpi_cols = st.columns(3)
    render_kpi_card(secondary_kpi_cols[0], "Unique Categories", str(len(cat_perf_df)), "Active in period")
    render_kpi_card(secondary_kpi_cols[1], "Top Brand", str(top_brand.get("brand") or "n/a"), f"${float(top_brand.get('revenue') or 0):,.0f} revenue")
    render_kpi_card(secondary_kpi_cols[2], "Top Department", str(top_department.get("department") or "n/a"), f"{float(top_department.get('margin_rate') or 0):.1%} margin")

    business_left, business_right = st.columns(2)
    with business_left:
        st.subheader("Revenue and Margin by Category")
        if cat_perf_df.empty:
            st.info("No category data available for the selected period.")
        else:
            category_long = cat_perf_df.melt(
                id_vars=["category"],
                value_vars=["revenue", "margin"],
                var_name="metric",
                value_name="value",
            )
            chart = (
                alt.Chart(category_long)
                .mark_bar()
                .encode(
                    x=alt.X("category:N", sort="-y", title=None),
                    y=alt.Y("value:Q", title="Amount ($)"),
                    xOffset="metric:N",
                    color=alt.Color(
                        "metric:N",
                        title="Metric",
                        scale=alt.Scale(range=["#315f8c", "#c96a50"]),
                    ),
                    tooltip=[
                        alt.Tooltip("category:N", title="Category"),
                        alt.Tooltip("metric:N", title="Metric"),
                        alt.Tooltip("value:Q", title="Amount", format=",.0f"),
                    ],
                )
                .properties(height=360)
            )
            st.altair_chart(chart, width="stretch")

    with business_right:
        st.subheader("Category Sales Trend")
        if cat_trend_df.empty or cat_perf_df.empty:
            st.info("No category trend data available.")
        else:
            top_categories = cat_perf_df.head(5)["category"].tolist()
            trend_filtered = cat_trend_df[cat_trend_df["category"].isin(top_categories)]
            chart = (
                alt.Chart(trend_filtered)
                .mark_line(strokeWidth=2.3)
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y("revenue:Q", title="Revenue ($)"),
                    color=alt.Color("category:N", title="Category", scale=alt.Scale(scheme="tableau10")),
                    tooltip=[
                        alt.Tooltip("date:T", title="Date"),
                        alt.Tooltip("category:N", title="Category"),
                        alt.Tooltip("revenue:Q", title="Revenue", format=",.0f"),
                    ],
                )
                .properties(height=360)
            )
            st.altair_chart(chart, width="stretch")

    brand_left, brand_right = st.columns(2)
    with brand_left:
        st.subheader("Top Brands by Revenue")
        if brand_perf_df.empty:
            st.info("No brand data available for the selected period.")
        else:
            top_brands = brand_perf_df.head(12).copy()
            brand_long = top_brands.melt(
                id_vars=["brand", "items_sold", "orders", "margin_rate"],
                value_vars=["revenue", "margin"],
                var_name="metric",
                value_name="amount",
            )
            brand_chart = (
                alt.Chart(brand_long)
                .mark_bar()
                .encode(
                    x=alt.X("amount:Q", title="Amount ($)"),
                    y=alt.Y("brand:N", sort=top_brands["brand"].tolist(), title=None),
                    yOffset="metric:N",
                    color=alt.Color(
                        "metric:N",
                        title="Metric",
                        scale=alt.Scale(domain=["revenue", "margin"], range=["#8db5d9", "#c96a50"]),
                    ),
                    tooltip=[
                        alt.Tooltip("brand:N", title="Brand"),
                        alt.Tooltip("metric:N", title="Metric"),
                        alt.Tooltip("amount:Q", title="Amount", format=",.0f"),
                        alt.Tooltip("items_sold:Q", title="Items sold", format=",.0f"),
                        alt.Tooltip("margin_rate:Q", title="Margin rate", format=".1%"),
                    ],
                )
                .properties(height=360)
            )
            st.altair_chart(brand_chart, width="stretch")

    with brand_right:
        st.subheader("Department Contribution")
        if dept_perf_df.empty:
            st.info("No department data available for the selected period.")
        else:
            dept_chart = (
                alt.Chart(dept_perf_df)
                .mark_arc(innerRadius=72, outerRadius=122)
                .encode(
                    theta=alt.Theta("revenue:Q"),
                    color=alt.Color(
                        "department:N",
                        title="Department",
                        scale=alt.Scale(range=["#315f8c", "#c96a50", "#8db5d9", "#a6d854"]),
                    ),
                    tooltip=[
                        alt.Tooltip("department:N", title="Department"),
                        alt.Tooltip("revenue:Q", title="Revenue", format=",.0f"),
                        alt.Tooltip("margin:Q", title="Margin", format=",.0f"),
                        alt.Tooltip("items_sold:Q", title="Items sold", format=",.0f"),
                    ],
                )
                .properties(height=360)
            )
            st.altair_chart(dept_chart, width="stretch")

    st.subheader("Top Brand Sales Trend")
    if brand_trend_df.empty or brand_perf_df.empty:
        st.info("No brand trend data available.")
    else:
        top_brand_names = brand_perf_df.head(6)["brand"].tolist()
        brand_trend_filtered = brand_trend_df[brand_trend_df["brand"].isin(top_brand_names)]
        trend_chart = (
            alt.Chart(brand_trend_filtered)
            .mark_line(strokeWidth=2.2)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("revenue:Q", title="Revenue ($)"),
                color=alt.Color("brand:N", title="Brand", scale=alt.Scale(scheme="tableau10")),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("brand:N", title="Brand"),
                    alt.Tooltip("revenue:Q", title="Revenue", format=",.0f"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(trend_chart, width="stretch")

    st.subheader("Product Profitability Matrix")
    if scatter_df.empty:
        st.info("Insufficient product data for the selected period.")
    else:
        scatter_chart = (
            alt.Chart(scatter_df)
            .mark_circle(opacity=0.72)
            .encode(
                x=alt.X("avg_price:Q", title="Average sale price ($)"),
                y=alt.Y("total_profit:Q", title="Total profit ($)"),
                size=alt.Size("volume:Q", title="Volume", scale=alt.Scale(range=[45, 900])),
                color=alt.Color("category:N", title="Category", scale=alt.Scale(scheme="tableau10")),
                tooltip=[
                    alt.Tooltip("product_name:N", title="Product"),
                    alt.Tooltip("category:N", title="Category"),
                    alt.Tooltip("brand:N", title="Brand"),
                    alt.Tooltip("department:N", title="Department"),
                    alt.Tooltip("avg_price:Q", title="Avg price", format=",.2f"),
                    alt.Tooltip("total_profit:Q", title="Profit", format=",.0f"),
                    alt.Tooltip("volume:Q", title="Volume", format=",.0f"),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(scatter_chart, width="stretch")

    st.subheader("Product Detail")
    if top_products_df.empty:
        st.info("No product details available for the selected period.")
    else:
        detail_df = top_products_df.copy()
        detail_df["margin_pct"] = (detail_df["margin"] / detail_df["revenue"].replace(0, pd.NA)).fillna(0)
        st.dataframe(
            detail_df[["product_name", "category", "brand", "department", "items_sold", "revenue", "margin", "margin_pct"]],
            width="stretch",
            hide_index=True,
        )


apply_theme()
st.title("Product Performance")
st.caption("Category trends, product profitability and sales volume for the selected business window.")

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
        "Brand",
        options=brand_options,
        default=[],
        placeholder="All brands",
        key="product_brand_filter",
    )

selected_brand_filter = tuple(selected_brands)

render_dashboard()
