import os
import time

import pandas as pd
import streamlit as st
from google.cloud import bigquery


st.set_page_config(page_title="TheLook Realtime Dashboard", page_icon="📈", layout="wide")


@st.cache_resource
def get_bq_client() -> bigquery.Client:
    project_id = os.getenv("GCP_PROJECT_ID")
    return bigquery.Client(project=project_id) if project_id else bigquery.Client()


def fetch_metrics(client: bigquery.Client, project_id: str, gold_dataset: str, bronze_dataset: str) -> dict:
    metric_query = f"""
        with revenue_cte as (
            select coalesce(sum(sale_price), 0) as total_revenue
            from `{project_id}.{gold_dataset}.fact_orders`
        ),
        active_users_cte as (
            select count(distinct user_id) as active_users
            from `{project_id}.{gold_dataset}.fact_orders`
            where order_created_at >= timestamp_sub(current_timestamp(), interval 1 hour)
        ),
        live_events_cte as (
            select count(*) as live_events_count
            from `{project_id}.{bronze_dataset}.events`
            where coalesce(
                timestamp_millis(safe_cast(cdc_timestamp as int64)),
                cast(cdc_timestamp as timestamp)
            ) >= timestamp_sub(current_timestamp(), interval 5 minute)
        )
        select
            r.total_revenue,
            a.active_users,
            l.live_events_count
        from revenue_cte r
        cross join active_users_cte a
        cross join live_events_cte l
    """
    row = next(client.query(metric_query).result())
    return {
        "total_revenue": float(row.total_revenue or 0),
        "active_users": int(row.active_users or 0),
        "live_events_count": int(row.live_events_count or 0),
    }


def fetch_orders_last_hour(client: bigquery.Client, project_id: str, gold_dataset: str) -> pd.DataFrame:
    chart_query = f"""
        select
            timestamp_trunc(order_created_at, minute) as minute_bucket,
            count(*) as order_count
        from `{project_id}.{gold_dataset}.fact_orders`
        where order_created_at >= timestamp_sub(current_timestamp(), interval 1 hour)
        group by minute_bucket
        order by minute_bucket
    """
    return client.query(chart_query).to_dataframe()


def main() -> None:
    client = get_bq_client()
    project_id = client.project
    gold_dataset = os.getenv("GOLD_DATASET_ID", "thelook_datawarehouse")
    bronze_dataset = os.getenv("BRONZE_DATASET_ID", "thelook_staging")

    st.title("TheLook Realtime Lakehouse Dashboard")
    st.caption("Nguon du lieu: BigQuery Gold + Bronze")

    try:
        metrics = fetch_metrics(client, project_id, gold_dataset, bronze_dataset)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Revenue", f"${metrics['total_revenue']:,.2f}")
        col2.metric("Active Users (1h)", f"{metrics['active_users']:,}")
        col3.metric("Live Events (5m)", f"{metrics['live_events_count']:,}")

        st.subheader("Orders In The Last 1 Hour")
        orders_df = fetch_orders_last_hour(client, project_id, gold_dataset)
        if orders_df.empty:
            st.info("No orders in the last hour yet.")
        else:
            st.line_chart(orders_df.set_index("minute_bucket")["order_count"])
    except Exception as exc:
        st.error(f"Failed to query BigQuery: {exc}")

    st.sidebar.header("Realtime Controls")
    auto_refresh = st.sidebar.toggle("Auto refresh every 5s", value=True)
    st.sidebar.write(f"Project: {project_id}")
    st.sidebar.write(f"Gold dataset: {gold_dataset}")
    st.sidebar.write(f"Bronze dataset: {bronze_dataset}")

    if auto_refresh:
        time.sleep(5)
        st.rerun()


if __name__ == "__main__":
    main()
