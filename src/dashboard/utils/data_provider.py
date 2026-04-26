import os
import datetime as dt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

class DataProvider:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.dataset = os.getenv("DWH_DATASET_ID") or os.getenv("GOLD_DATASET_ID", "thelook_datawarehouse")
        self.clickstream_dataset = os.getenv("CLICKSTREAM_DATASET_ID", "thelook_clickstream")
        if not self.project_id:
            st.error("BigQuery project is not configured. Set GCP_PROJECT_ID.")
            st.stop()
        self.client = bigquery.Client(project=self.project_id)

    @st.cache_data(ttl=300, show_spinner=False)
    def run_query(_self, query: str, _params=None) -> pd.DataFrame:
        try:
            query_params = []
            if _params:
                # Accept both tuple and legacy list inputs while keeping cache args hash-safe.
                if isinstance(_params, list):
                    _params = tuple(_params)
                query_params = [
                    bigquery.ScalarQueryParameter(name, param_type, value)
                    for name, param_type, value in _params
                ]
            job_config = bigquery.QueryJobConfig(
                query_parameters=query_params,
                use_query_cache=True,
            )
            return _self.client.query(query, job_config=job_config).to_dataframe(create_bqstorage_client=True)
        except Exception as e:
            st.error(f"SQL Error: {e}")
            return pd.DataFrame()

    def _t(self, table: str) -> str:
        return f"`{self.project_id}.{self.dataset}.{table}`"

    def table_ref(self, table: str) -> str:
        """Alias for _t to support clickstream legacy code, using clickstream dataset."""
        return f"`{self.project_id}.{self.clickstream_dataset}.{table}`"

    def _date_params(self, ds, de):
        return (
            ("start_date", "DATE", str(ds)),
            ("end_date", "DATE", str(de)),
        )

    def _timestamp_filter(self, column: str = "created_at") -> str:
        return (
            f"{column} >= TIMESTAMP(@start_date) "
            f"AND {column} < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))"
        )

    def _traffic_source_filter(self, traffic_sources, col_name="traffic_source"):
        if not traffic_sources:
            return ""
        sources_str = ", ".join([f"'{s}'" for s in traffic_sources])
        return f"AND {col_name} IN ({sources_str})"

    @st.cache_data(ttl=300, show_spinner=False)
    def get_latest_date(_self):
        # We want the latest date across all primary data sources
        queries = [
            f"SELECT MAX(date) as m FROM {_self._t('agg_dashboard_daily')}",
            f"SELECT MAX(DATE(created_at)) as m FROM {_self._t('fact_orders')}",
            f"SELECT MAX(event_date) as m FROM {_self.table_ref('v_events_raw_dedup')}"
        ]
        
        latest_dates = []
        for q in queries:
            try:
                df = _self.run_query(q)
                if not df.empty and not pd.isna(df.iloc[0]['m']):
                    latest_dates.append(pd.to_datetime(df.iloc[0]['m']).date())
            except Exception:
                continue
        
        if not latest_dates:
            return None
        return max(latest_dates)

    def get_default_date_range(self, window_days: int = 30):
        latest = self.get_latest_date() or dt.date.today()
        safe_window = max(int(window_days), 1)
        start = latest - dt.timedelta(days=safe_window - 1)
        return start, latest

    # --- 01 Executive Sales ---
    def get_sales_kpis(self, ds, de):
        q = f"""
        SELECT 
            COALESCE(SUM(revenue), 0) as revenue,
            COALESCE(SUM(cost), 0) as cost,
            COALESCE(SUM(margin), 0) as margin,
            COALESCE(SUM(orders), 0) as orders,
            COALESCE(SAFE_DIVIDE(SUM(margin), SUM(revenue)), 0) as margin_rate
        FROM {self._t('agg_dashboard_daily')}
        WHERE date BETWEEN @start_date AND @end_date
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_revenue_trend(self, ds, de):
        q = f"""
        SELECT 
            date,
            COALESCE(revenue, 0) as revenue,
            COALESCE(margin, 0) as margin
        FROM {self._t('agg_dashboard_daily')}
        WHERE date BETWEEN @start_date AND @end_date
        ORDER BY 1
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_top_products(self, ds, de):
        q = f"""
        SELECT 
            p.product_name,
            p.category,
            COALESCE(SUM(oi.sale_price), 0) as revenue,
            COALESCE(SUM(oi.profit), 0) as margin
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
        GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15
        """
        return self.run_query(q, self._date_params(ds, de))

    # --- 02 Marketing & Audience ---
    def get_marketing_kpis(self, ds, de):
        q = f"""
        SELECT 
            COALESCE(SUM(total_users), 0) as total_users,
            COALESCE(SUM(total_sessions), 0) as total_sessions,
            COALESCE(SUM(checkout_events), 0) as checkout_events,
            COALESCE(SAFE_DIVIDE(SUM(checkout_events), SUM(total_sessions)), 0) as cvr
        FROM {self._t('agg_dashboard_daily')}
        WHERE date BETWEEN @start_date AND @end_date
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_user_segments(self):
        q = f"""
        SELECT 
            customer_status,
            age_group,
            COUNT(*) as user_count
        FROM {self._t('dim_users')}
        GROUP BY 1, 2
        """
        return self.run_query(q)

    def get_traffic_cvr(self, ds, de):
        q = f"""
        SELECT 
            traffic_source,
            COUNT(DISTINCT session_id) as sessions,
            COUNT(DISTINCT IF(is_checkout_event, session_id, NULL)) as purchases,
            COALESCE(
                SAFE_DIVIDE(
                    COUNT(DISTINCT IF(is_checkout_event, session_id, NULL)),
                    COUNT(DISTINCT session_id)
                ),
                0
            ) as cvr
        FROM {self._t('fact_events')}
        WHERE {self._timestamp_filter('created_at')}
          AND COALESCE(TRIM(traffic_source), '') != ''
        GROUP BY 1 ORDER BY 2 DESC
        """
        return self.run_query(q, self._date_params(ds, de))

    @st.cache_data(ttl=300, show_spinner=False)
    def get_latest_traffic_date(self):
        q = f"""
        SELECT MAX(DATE(created_at)) as latest_traffic_date
        FROM {self._t('fact_events')}
        WHERE COALESCE(TRIM(traffic_source), '') != ''
        """
        df = self.run_query(q)
        if df.empty or pd.isna(df.iloc[0]['latest_traffic_date']):
            return None
        return pd.to_datetime(df.iloc[0]['latest_traffic_date']).date()

    def get_traffic_cvr_latest_window(self, end_date):
        q = f"""
        SELECT
            traffic_source,
            COUNT(DISTINCT session_id) as sessions,
            COUNT(DISTINCT IF(is_checkout_event, session_id, NULL)) as purchases,
            COALESCE(
                SAFE_DIVIDE(
                    COUNT(DISTINCT IF(is_checkout_event, session_id, NULL)),
                    COUNT(DISTINCT session_id)
                ),
                0
            ) as cvr
        FROM {self._t('fact_events')}
        WHERE created_at >= TIMESTAMP(DATE_SUB(@end_date, INTERVAL 29 DAY))
          AND created_at < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))
          AND COALESCE(TRIM(traffic_source), '') != ''
        GROUP BY 1
        ORDER BY 2 DESC
        """
        params = (("end_date", "DATE", str(end_date)),)
        return self.run_query(q, params)

    # --- 03 Operations & Logistics ---
    def get_ops_kpis(self, ds, de):
        q1 = f"""
        SELECT 
            COALESCE(AVG(delivery_duration_days), 0) as avg_delivery_days,
            COALESCE(SAFE_DIVIDE(COUNTIF(is_delayed), COUNT(*)), 0) as delayed_rate
        FROM {self._t('fact_orders')}
        WHERE {self._timestamp_filter('created_at')} AND delivery_duration_days IS NOT NULL AND delivery_duration_days > 0
        """
        q2 = f"""
        SELECT COALESCE(SAFE_DIVIDE(COUNTIF(is_returned), COUNT(*)), 0) as return_rate
        FROM {self._t('fact_order_items')}
        WHERE {self._timestamp_filter('created_at')}
        """
        params = self._date_params(ds, de)
        return self.run_query(q1, params), self.run_query(q2, params)

    def get_inventory_status(self):
        q = f"""
        SELECT 
            CASE WHEN is_sold THEN 'Sold' ELSE 'In Stock' END as status,
            COUNT(*) as item_count,
            AVG(days_in_inventory) as avg_days_in_inv
        FROM {self._t('dim_inventory')}
        GROUP BY 1
        """
        return self.run_query(q)

    def get_delivery_histogram(self, ds, de):
        q = f"""
        SELECT 
            CAST(delivery_duration_days AS STRING) || ' Days' as duration_bucket,
            delivery_duration_days,
            COUNT(*) as orders
        FROM {self._t('fact_orders')}
        WHERE {self._timestamp_filter('created_at')} AND delivery_duration_days IS NOT NULL
        GROUP BY 1, 2 ORDER BY 2
        """
        return self.run_query(q, self._date_params(ds, de))

    # --- 04 Realtime Clickstream (Merged) ---
    @st.cache_data(ttl=900, show_spinner=False)
    def get_traffic_sources(_self, start_date: str, end_date: str) -> list[str]:
        query = f"""
        SELECT DISTINCT traffic_source
        FROM {_self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          AND traffic_source IS NOT NULL
        ORDER BY traffic_source
        """
        df = _self.run_query(query)
        return df["traffic_source"].dropna().tolist() if not df.empty else []

    def get_overview_metrics(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> dict:
        event_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
            COUNT(*) AS total_events,
            COUNT(DISTINCT session_id) AS total_sessions,
            COUNT(DISTINCT user_id) AS total_users,
            COUNTIF(event_type = 'purchase') AS purchase_events,
            SAFE_DIVIDE(COUNTIF(event_type = 'purchase'), COUNT(DISTINCT session_id)) AS conversion_rate
        FROM {self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {event_filter}
        """
        df = self.run_query(query)
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_daily_events_and_purchases(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          event_date,
          COUNT(*) AS total_events,
          COUNTIF(event_type = 'purchase') AS purchase_events
        FROM {self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY event_date
        ORDER BY event_date
        """
        return self.run_query(query)

    def get_channel_distribution(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          traffic_source,
          COUNT(*) AS total_events,
          COUNT(DISTINCT session_id) AS sessions,
          COUNTIF(event_type = 'purchase') AS purchases
        FROM {self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY traffic_source
        ORDER BY total_events DESC
        """
        return self.run_query(query)

    def get_realtime_windows(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          TIMESTAMP(window_start) AS window_start,
          SUM(total_events) AS total_events,
          SUM(purchase_events) AS purchase_events,
          AVG(avg_event_lag_seconds) AS avg_event_lag_seconds
        FROM {self.table_ref('v_events_5m_latest')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY window_start
        ORDER BY window_start
        """
        return self.run_query(query)

    def get_event_type_breakdown(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          event_type,
          COUNT(*) AS total_events
        FROM {self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY event_type
        ORDER BY total_events DESC
        """
        return self.run_query(query)

    def get_deadletter_monitor(self, start_date: str, end_date: str) -> dict:
        query = f"""
        SELECT
          COUNT(*) AS deadletter_count,
          COUNTIF(DATE(failed_at) = CURRENT_DATE()) AS deadletter_today,
          MAX(failed_at) AS latest_failure_at
        FROM {self.table_ref('events_deadletter')}
        WHERE DATE(failed_at) BETWEEN DATE('{start_date}') AND DATE('{end_date}')
        """
        df = self.run_query(query)
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_deadletter_samples(self, start_date: str, end_date: str, limit: int = 8) -> pd.DataFrame:
        query = f"""
        SELECT
          failed_at,
          error_message,
          raw_message
        FROM {self.table_ref('events_deadletter')}
        WHERE DATE(failed_at) BETWEEN DATE('{start_date}') AND DATE('{end_date}')
        ORDER BY failed_at DESC
        LIMIT {int(limit)}
        """
        return self.run_query(query)

    def get_deadletter_timeseries(self, start_date: str, end_date: str) -> pd.DataFrame:
        query = f"""
        SELECT
          TIMESTAMP_TRUNC(failed_at, HOUR) AS failed_hour,
          COUNT(*) AS deadletter_count
        FROM {self.table_ref('events_deadletter')}
        WHERE DATE(failed_at) BETWEEN DATE('{start_date}') AND DATE('{end_date}')
        GROUP BY failed_hour
        ORDER BY failed_hour
        """
        return self.run_query(query)

    def get_pipeline_health(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> dict:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        WITH realtime AS (
          SELECT
            SUM(total_events) AS realtime_events,
            SUM(purchase_events) AS realtime_purchases,
            AVG(avg_event_lag_seconds) AS avg_event_lag_seconds,
            MAX(window_start) AS latest_window_start
          FROM {self.table_ref('v_events_5m_latest')}
          WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        ),
        raw_events AS (
          SELECT
            COUNT(*) AS raw_events,
            MAX(event_timestamp) AS latest_event_timestamp,
            MAX(processing_time) AS latest_processing_time
          FROM {self.table_ref('v_events_raw_dedup')}
          WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        ),
        deadletter AS (
          SELECT
            COUNT(*) AS deadletter_count
          FROM {self.table_ref('events_deadletter')}
          WHERE DATE(failed_at) BETWEEN DATE('{start_date}') AND DATE('{end_date}')
        )
        SELECT
          realtime.realtime_events,
          realtime.realtime_purchases,
          realtime.avg_event_lag_seconds,
          realtime.latest_window_start,
          raw_events.raw_events,
          raw_events.latest_event_timestamp,
          raw_events.latest_processing_time,
          deadletter.deadletter_count,
          SAFE_DIVIDE(deadletter.deadletter_count, NULLIF(raw_events.raw_events, 0)) AS deadletter_rate
        FROM realtime, raw_events, deadletter
        """
        df = self.run_query(query)
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_event_lag_timeseries(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          TIMESTAMP(window_start) AS window_start,
          AVG(avg_event_lag_seconds) AS avg_event_lag_seconds,
          SUM(total_events) AS total_events
        FROM {self.table_ref('v_events_5m_latest')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY window_start
        ORDER BY window_start
        """
        return self.run_query(query)

    def get_session_summary(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> dict:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          COUNT(*) AS total_sessions,
          AVG(session_duration_seconds) AS avg_session_seconds,
          APPROX_QUANTILES(session_duration_seconds, 100)[OFFSET(50)] AS median_session_seconds,
          AVG(event_count) AS avg_event_count,
          AVG(pageview_count) AS avg_pageviews,
          AVG(product_view_count) AS avg_product_views,
          SAFE_DIVIDE(COUNTIF(added_to_cart), COUNT(*)) AS cart_rate,
          SAFE_DIVIDE(COUNTIF(purchased), COUNT(*)) AS conversion_rate
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        """
        df = self.run_query(query)
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_session_timeseries(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          TIMESTAMP_TRUNC(session_start, HOUR) AS session_hour,
          COUNT(*) AS sessions,
          COUNTIF(purchased) AS purchased_sessions,
          AVG(session_duration_seconds) AS avg_session_seconds
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY session_hour
        ORDER BY session_hour
        """
        return self.run_query(query)

    def get_conversion_funnel(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT 'Home' AS stage, COUNTIF(saw_home) AS sessions FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        UNION ALL
        SELECT 'Product' AS stage, COUNTIF(saw_product) AS sessions FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        UNION ALL
        SELECT 'Cart' AS stage, COUNTIF(added_to_cart) AS sessions FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        UNION ALL
        SELECT 'Purchase' AS stage, COUNTIF(purchased) AS sessions FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        """
        return self.run_query(query)

    def get_funnel_dropoff(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        WITH base AS (
          SELECT
            COUNTIF(saw_home) AS home_sessions,
            COUNTIF(saw_product) AS product_sessions,
            COUNTIF(added_to_cart) AS cart_sessions,
            COUNTIF(purchased) AS purchased_sessions
          FROM {self.table_ref('v_session_metrics_latest')}
          WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        )
        SELECT 'Home -> Product' AS transition, home_sessions AS from_sessions, product_sessions AS to_sessions FROM base
        UNION ALL
        SELECT 'Product -> Cart' AS transition, product_sessions AS from_sessions, cart_sessions AS to_sessions FROM base
        UNION ALL
        SELECT 'Cart -> Purchase' AS transition, cart_sessions AS from_sessions, purchased_sessions AS to_sessions FROM base
        """
        return self.run_query(query)

    def get_session_duration_histogram(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        WITH base AS (
          SELECT session_duration_seconds
          FROM {self.table_ref('v_session_metrics_latest')}
          WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        )
        SELECT
          CASE
            WHEN session_duration_seconds < 60 THEN '0-1m'
            WHEN session_duration_seconds < 180 THEN '1-3m'
            WHEN session_duration_seconds < 300 THEN '3-5m'
            WHEN session_duration_seconds < 600 THEN '5-10m'
            WHEN session_duration_seconds < 900 THEN '10-15m'
            WHEN session_duration_seconds < 1800 THEN '15-30m'
            ELSE '30m+'
          END AS duration_bucket,
          CASE
            WHEN session_duration_seconds < 60 THEN 1
            WHEN session_duration_seconds < 180 THEN 2
            WHEN session_duration_seconds < 300 THEN 3
            WHEN session_duration_seconds < 600 THEN 4
            WHEN session_duration_seconds < 900 THEN 5
            WHEN session_duration_seconds < 1800 THEN 6
            ELSE 7
          END AS bucket_order,
          COUNT(*) AS sessions
        FROM base
        GROUP BY duration_bucket, bucket_order
        ORDER BY bucket_order
        """
        return self.run_query(query)

    def get_cvr_by_channel(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          traffic_source,
          COUNT(*) AS sessions,
          COUNTIF(purchased) AS purchased_sessions,
          SAFE_DIVIDE(COUNTIF(purchased), COUNT(*)) AS conversion_rate,
          AVG(session_duration_seconds) AS avg_session_seconds
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY traffic_source
        ORDER BY sessions DESC
        """
        return self.run_query(query)

    def get_cvr_by_browser(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          browser,
          COUNT(*) AS sessions,
          COUNTIF(purchased) AS purchased_sessions,
          SAFE_DIVIDE(COUNTIF(purchased), COUNT(*)) AS conversion_rate,
          AVG(session_duration_seconds) AS avg_session_seconds
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY browser
        ORDER BY sessions DESC
        """
        return self.run_query(query)

    def get_top_categories(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          COALESCE(top_category, 'Unknown') AS top_category,
          COUNT(*) AS sessions,
          COUNTIF(purchased) AS purchased_sessions,
          SAFE_DIVIDE(COUNTIF(purchased), COUNT(*)) AS conversion_rate,
          AVG(session_duration_seconds) AS avg_session_seconds,
          AVG(product_view_count) AS avg_product_views
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY top_category
        ORDER BY sessions DESC
        LIMIT 12
        """
        return self.run_query(query)

    def get_popular_pages(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          uri,
          page_type,
          COUNT(*) AS total_events,
          COUNT(DISTINCT session_id) AS sessions,
          COUNTIF(event_type = 'purchase') AS purchases
        FROM {self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY uri, page_type
        ORDER BY total_events DESC
        LIMIT 12
        """
        return self.run_query(query)

    def get_session_quality(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          traffic_source,
          browser,
          COUNT(*) AS sessions,
          AVG(session_duration_seconds) AS avg_session_seconds,
          AVG(event_count) AS avg_event_count,
          AVG(pageview_count) AS avg_pageviews,
          SAFE_DIVIDE(COUNTIF(purchased), COUNT(*)) AS conversion_rate
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY traffic_source, browser
        ORDER BY sessions DESC
        LIMIT 20
        """
        return self.run_query(query)

@st.cache_resource(show_spinner=False)
def get_data_provider() -> DataProvider:
    return DataProvider()

data_provider = get_data_provider()
