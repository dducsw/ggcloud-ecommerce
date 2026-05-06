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
        self.realtime_ttl = int(os.getenv("REALTIME_TTL", "60"))
        if not self.project_id:
            st.error("BigQuery project is not configured. Set GCP_PROJECT_ID.")
            st.stop()
        self.client = bigquery.Client(project=self.project_id)

    @st.cache_data(ttl=300, show_spinner=False)
    def run_query(_self, query: str, params=None) -> pd.DataFrame:
        try:
            query_params = []
            if params:
                # Accept both tuple and legacy list inputs while keeping cache args hash-safe.
                if isinstance(params, list):
                    params = tuple(params)
                query_params = [
                    bigquery.ArrayQueryParameter(name, param_type, value)
                    if isinstance(value, (list, tuple))
                    else bigquery.ScalarQueryParameter(name, param_type, value)
                    for name, param_type, value in params
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

    def _brand_filter(self, brands, col_name="p.brand"):
        if not brands:
            return "", ()
        return f"AND {col_name} IN UNNEST(@brands)", (("brands", "STRING", list(brands)),)

    def _date_brand_params(self, ds, de, brands=None):
        brand_filter, brand_params = self._brand_filter(brands)
        return brand_filter, self._date_params(ds, de) + brand_params

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

    @st.cache_data(ttl=60, show_spinner=False)
    def get_latest_timestamp(_self):
        """Returns the most recent event timestamp for clickstream data."""
        q = f"SELECT MAX(event_timestamp) as m FROM {_self.table_ref('v_events_raw_dedup')}"
        try:
            df = _self.run_query(q)
            if not df.empty and not pd.isna(df.iloc[0]['m']):
                return pd.to_datetime(df.iloc[0]['m'])
        except Exception:
            pass
        return None

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
        return self.get_top_products_by_brand(ds, de)

    def get_top_products_by_brand(self, ds, de, brands=None):
        brand_filter, params = self._date_brand_params(ds, de, brands)
        q = f"""
        SELECT 
            p.product_name,
            p.category,
            p.brand,
            p.department,
            COALESCE(SUM(oi.sale_price), 0) as revenue,
            COALESCE(SUM(oi.profit), 0) as margin,
            COUNT(*) as items_sold
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
          {brand_filter}
        GROUP BY 1, 2, 3, 4 ORDER BY 5 DESC LIMIT 25
        """
        return self.run_query(q, params)

    def get_product_brands(self, ds, de):
        q = f"""
        SELECT DISTINCT COALESCE(NULLIF(TRIM(p.brand), ''), 'Unknown') as brand
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
        ORDER BY brand
        """
        df = self.run_query(q, self._date_params(ds, de))
        return df["brand"].dropna().tolist() if not df.empty else []

    def get_order_value_distribution(self, ds, de):
        q = f"""
        SELECT
            order_id,
            total_revenue as order_value,
            gross_margin as margin,
            num_of_item
        FROM {self._t('fact_orders')}
        WHERE {self._timestamp_filter('created_at')}
          AND total_revenue > 0
        ORDER BY created_at DESC
        LIMIT 5000
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_order_status_stats(self, ds, de):
        q = f"""
        SELECT 
            status,
            COUNT(*) as order_count
        FROM {self._t('fact_orders')}
        WHERE {self._timestamp_filter('created_at')}
        GROUP BY 1 ORDER BY 2 DESC
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_order_type_stats(self, ds, de):
        q = f"""
        SELECT 
            order_type,
            COUNT(*) as order_count
        FROM {self._t('fact_orders')}
        WHERE {self._timestamp_filter('created_at')}
        GROUP BY 1 ORDER BY 2 DESC
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_orders_by_city(self, ds, de):
        q = f"""
        SELECT 
            u.city,
            u.latitude,
            u.longitude,
            COUNT(DISTINCT o.user_id) as user_count,
            COUNT(o.order_id) as order_count
        FROM {self._t('fact_orders')} o
        JOIN {self._t('dim_users')} u ON o.user_id = u.user_id
        WHERE {self._timestamp_filter('o.created_at')}
        GROUP BY 1, 2, 3 ORDER BY 5 DESC LIMIT 500
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_category_performance(self, ds, de):
        return self.get_category_performance_by_brand(ds, de)

    def get_category_performance_by_brand(self, ds, de, brands=None):
        brand_filter, params = self._date_brand_params(ds, de, brands)
        q = f"""
        SELECT 
            p.category,
            COALESCE(SUM(oi.sale_price), 0) as revenue,
            COALESCE(SUM(oi.profit), 0) as margin,
            COUNT(DISTINCT oi.order_id) as orders
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
          {brand_filter}
        GROUP BY 1 ORDER BY 2 DESC
        """
        return self.run_query(q, params)

    def get_product_scatter(self, ds, de):
        return self.get_product_scatter_by_brand(ds, de)

    def get_product_scatter_by_brand(self, ds, de, brands=None):
        brand_filter, params = self._date_brand_params(ds, de, brands)
        q = f"""
        SELECT 
            p.product_name,
            p.category,
            p.brand,
            p.department,
            AVG(oi.sale_price) as avg_price,
            SUM(oi.profit) as total_profit,
            COUNT(*) as volume
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
          {brand_filter}
        GROUP BY 1, 2, 3, 4
        HAVING volume > 5
        LIMIT 100
        """
        return self.run_query(q, params)

    def get_brand_performance(self, ds, de):
        return self.get_brand_performance_by_brand(ds, de)

    def get_brand_performance_by_brand(self, ds, de, brands=None):
        brand_filter, params = self._date_brand_params(ds, de, brands)
        q = f"""
        SELECT
            COALESCE(NULLIF(TRIM(p.brand), ''), 'Unknown') as brand,
            COALESCE(SUM(oi.sale_price), 0) as revenue,
            COALESCE(SUM(oi.profit), 0) as margin,
            COUNT(*) as items_sold,
            COUNT(DISTINCT oi.order_id) as orders,
            COALESCE(SAFE_DIVIDE(SUM(oi.profit), SUM(oi.sale_price)), 0) as margin_rate
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
          {brand_filter}
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 20
        """
        return self.run_query(q, params)

    def get_department_performance(self, ds, de):
        return self.get_department_performance_by_brand(ds, de)

    def get_department_performance_by_brand(self, ds, de, brands=None):
        brand_filter, params = self._date_brand_params(ds, de, brands)
        q = f"""
        SELECT
            COALESCE(NULLIF(TRIM(p.department), ''), 'Unknown') as department,
            COALESCE(SUM(oi.sale_price), 0) as revenue,
            COALESCE(SUM(oi.profit), 0) as margin,
            COUNT(*) as items_sold,
            COUNT(DISTINCT oi.order_id) as orders,
            COALESCE(SAFE_DIVIDE(SUM(oi.profit), SUM(oi.sale_price)), 0) as margin_rate
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
          {brand_filter}
        GROUP BY 1
        ORDER BY 2 DESC
        """
        return self.run_query(q, params)

    def get_brand_trend(self, ds, de):
        return self.get_brand_trend_by_brand(ds, de)

    def get_brand_trend_by_brand(self, ds, de, brands=None):
        brand_filter, params = self._date_brand_params(ds, de, brands)
        q = f"""
        SELECT
            DATE(oi.created_at) as date,
            COALESCE(NULLIF(TRIM(p.brand), ''), 'Unknown') as brand,
            SUM(oi.sale_price) as revenue
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
          {brand_filter}
        GROUP BY 1, 2
        ORDER BY 1
        """
        return self.run_query(q, params)

    def get_category_trend(self, ds, de):
        return self.get_category_trend_by_brand(ds, de)

    def get_category_trend_by_brand(self, ds, de, brands=None):
        brand_filter, params = self._date_brand_params(ds, de, brands)
        q = f"""
        SELECT 
            DATE(oi.created_at) as date,
            p.category,
            SUM(oi.sale_price) as revenue
        FROM {self._t('fact_order_items')} oi
        JOIN {self._t('dim_products')} p ON oi.product_id = p.product_id
        WHERE {self._timestamp_filter('oi.created_at')}
          {brand_filter}
        GROUP BY 1, 2 ORDER BY 1
        """
        return self.run_query(q, params)

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

    def get_inventory_status(self, ds=None, de=None):
        q = f"""
        SELECT 
            inventory_status as status,
            COUNT(*) as item_count,
            COALESCE(SUM(cost), 0) as inventory_cost,
            AVG(
                CASE
                    WHEN is_sold THEN days_in_inventory
                    ELSE TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, DAY)
                END
            ) as avg_days_in_inv
        FROM {self._t('fact_inventory')}
        WHERE created_at < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))
          AND (sold_at IS NULL OR sold_at >= TIMESTAMP(@start_date))
        GROUP BY 1
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_inventory_kpis(self, ds, de):
        q = f"""
        SELECT
            COUNT(*) as inventory_items,
            COUNTIF(NOT is_sold) as available_items,
            COUNTIF(inventory_status = 'Slow-Moving') as slow_moving_items,
            COUNTIF(is_sold) as sold_items,
            COALESCE(SUM(IF(NOT is_sold, cost, 0)), 0) as available_cost,
            COALESCE(AVG(IF(NOT is_sold, TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, DAY), NULL)), 0) as avg_available_age_days,
            COALESCE(AVG(days_in_inventory), 0) as avg_sold_days_in_inventory,
            COALESCE(SAFE_DIVIDE(COUNTIF(is_sold), COUNT(*)), 0) as sell_through_rate
        FROM {self._t('fact_inventory')}
        WHERE created_at < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))
          AND (sold_at IS NULL OR sold_at >= TIMESTAMP(@start_date))
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_inventory_age_buckets(self, ds, de):
        q = f"""
        WITH base AS (
            SELECT
                CASE
                    WHEN is_sold THEN days_in_inventory
                    ELSE TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, DAY)
                END as age_days,
                cost
            FROM {self._t('fact_inventory')}
            WHERE created_at < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))
              AND (sold_at IS NULL OR sold_at >= TIMESTAMP(@start_date))
        )
        SELECT
            CASE
                WHEN age_days < 30 THEN '0-29 days'
                WHEN age_days < 60 THEN '30-59 days'
                WHEN age_days < 90 THEN '60-89 days'
                WHEN age_days < 180 THEN '90-179 days'
                ELSE '180+ days'
            END as age_bucket,
            CASE
                WHEN age_days < 30 THEN 1
                WHEN age_days < 60 THEN 2
                WHEN age_days < 90 THEN 3
                WHEN age_days < 180 THEN 4
                ELSE 5
            END as bucket_order,
            COUNT(*) as item_count,
            COALESCE(SUM(cost), 0) as inventory_cost
        FROM base
        GROUP BY 1, 2
        ORDER BY 2
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_inventory_by_distribution_center(self, ds, de):
        q = f"""
        SELECT
            dc.distribution_center_name,
            dc.latitude,
            dc.longitude,
            COUNT(*) as item_count,
            COUNTIF(NOT inv.is_sold) as available_items,
            COUNTIF(inv.inventory_status = 'Slow-Moving') as slow_moving_items,
            COALESCE(SUM(IF(NOT inv.is_sold, inv.cost, 0)), 0) as available_cost
        FROM {self._t('fact_inventory')} inv
        LEFT JOIN {self._t('dim_distribution_centers')} dc
          ON inv.distribution_center_id = dc.distribution_center_id
        WHERE inv.created_at < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))
          AND (inv.sold_at IS NULL OR inv.sold_at >= TIMESTAMP(@start_date))
        GROUP BY 1, 2, 3
        ORDER BY 4 DESC
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_inventory_by_product_segment(self, ds, de):
        q = f"""
        SELECT
            p.category,
            p.department,
            COUNT(*) as item_count,
            COUNTIF(NOT inv.is_sold) as available_items,
            COUNTIF(inv.inventory_status = 'Slow-Moving') as slow_moving_items,
            COALESCE(SUM(IF(NOT inv.is_sold, inv.cost, 0)), 0) as available_cost
        FROM {self._t('fact_inventory')} inv
        LEFT JOIN {self._t('dim_products')} p
          ON inv.product_id = p.product_id
        WHERE inv.created_at < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))
          AND (inv.sold_at IS NULL OR inv.sold_at >= TIMESTAMP(@start_date))
        GROUP BY 1, 2
        ORDER BY 4 DESC
        LIMIT 20
        """
        return self.run_query(q, self._date_params(ds, de))

    def get_inventory_flow(self, ds, de):
        q = f"""
        WITH created AS (
            SELECT DATE(created_at) as date, COUNT(*) as created_items
            FROM {self._t('fact_inventory')}
            WHERE created_at >= TIMESTAMP(@start_date)
              AND created_at < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))
            GROUP BY 1
        ),
        sold AS (
            SELECT DATE(sold_at) as date, COUNT(*) as sold_items
            FROM {self._t('fact_inventory')}
            WHERE sold_at >= TIMESTAMP(@start_date)
              AND sold_at < TIMESTAMP(DATE_ADD(@end_date, INTERVAL 1 DAY))
            GROUP BY 1
        )
        SELECT
            COALESCE(created.date, sold.date) as date,
            COALESCE(created.created_items, 0) as created_items,
            COALESCE(sold.sold_items, 0) as sold_items
        FROM created
        FULL OUTER JOIN sold
          ON created.date = sold.date
        ORDER BY 1
        """
        return self.run_query(q, self._date_params(ds, de))

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
    @st.cache_data(ttl=60, show_spinner=False)
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

    def get_event_type_windows(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          TIMESTAMP(window_start) AS window_start,
          COALESCE(event_type, 'Unknown') AS event_type,
          SUM(total_events) AS total_events
        FROM {self.table_ref('v_events_5m_latest')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY window_start, event_type
        ORDER BY window_start, event_type
        """
        return self.run_query(query)

    def get_source_event_flow(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          COALESCE(traffic_source, 'Unknown') AS traffic_source,
          COALESCE(event_type, 'Unknown') AS event_type,
          COUNT(*) AS total_events
        FROM {self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE(TIMESTAMP('{start_date}')) AND DATE(TIMESTAMP('{end_date}'))
          AND event_timestamp >= TIMESTAMP('{start_date}')
          AND event_timestamp <= TIMESTAMP('{end_date}')
          {traffic_filter}
        GROUP BY traffic_source, event_type
        HAVING total_events > 0
        ORDER BY total_events DESC
        LIMIT 40
        """
        return self.run_query(query)

    def get_ingestion_freshness(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> dict:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        WITH raw AS (
          SELECT
            COUNT(*) AS dedup_events,
            MAX(event_timestamp) AS latest_event_timestamp,
            MAX(ingested_at) AS latest_ingested_at,
            MAX(processing_time) AS latest_processing_time,
            AVG(event_lag_seconds) AS avg_event_lag_seconds,
            APPROX_QUANTILES(event_lag_seconds, 100)[OFFSET(95)] AS p95_event_lag_seconds
          FROM {self.table_ref('v_events_raw_dedup')}
          WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        ),
        windows AS (
          SELECT
            MAX(window_start) AS latest_window_start,
            MAX(version_emitted_at) AS latest_window_emitted_at,
            COUNT(DISTINCT window_start) AS emitted_windows,
            SUM(total_events) AS window_events
          FROM {self.table_ref('v_events_5m_latest')}
          WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        )
        SELECT
          raw.*,
          windows.latest_window_start,
          windows.latest_window_emitted_at,
          windows.emitted_windows,
          windows.window_events,
          TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), latest_processing_time, SECOND) AS processing_freshness_seconds,
          TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), latest_window_emitted_at, SECOND) AS aggregate_freshness_seconds
        FROM raw, windows
        """
        df = self.run_query(query)
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_throughput_by_window(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          TIMESTAMP(window_start) AS window_start,
          SUM(total_events) AS total_events,
          SUM(unique_sessions) AS unique_sessions,
          SUM(unique_users) AS unique_users,
          AVG(avg_event_lag_seconds) AS avg_event_lag_seconds,
          SAFE_DIVIDE(SUM(total_events), 300) AS events_per_second,
          MAX(version_emitted_at) AS version_emitted_at
        FROM {self.table_ref('v_events_5m_latest')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY window_start
        ORDER BY window_start
        """
        return self.run_query(query)

    def get_event_quality_summary(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> dict:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        WITH raw AS (
          SELECT
            COUNT(*) AS raw_rows,
            COUNT(DISTINCT event_id) AS distinct_event_ids,
            COUNTIF(session_id IS NULL OR TRIM(session_id) = '') AS missing_session_id,
            COUNTIF(user_id IS NULL) AS missing_user_id,
            COUNTIF(event_type IS NULL OR TRIM(event_type) = '') AS missing_event_type,
            COUNTIF(event_timestamp IS NULL) AS missing_event_timestamp,
            COUNTIF(event_lag_seconds < 0) AS negative_lag_events
          FROM {self.table_ref('events_raw')}
          WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        ),
        dedup AS (
          SELECT COUNT(*) AS dedup_rows
          FROM {self.table_ref('v_events_raw_dedup')}
          WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        ),
        deadletter AS (
          SELECT COUNT(*) AS deadletter_rows
          FROM {self.table_ref('events_deadletter')}
          WHERE DATE(failed_at) BETWEEN DATE('{start_date}') AND DATE('{end_date}')
        )
        SELECT
          raw.*,
          dedup.dedup_rows,
          deadletter.deadletter_rows,
          raw.raw_rows - dedup.dedup_rows AS duplicate_rows_removed,
          SAFE_DIVIDE(raw.raw_rows - dedup.dedup_rows, NULLIF(raw.raw_rows, 0)) AS duplicate_rate,
          SAFE_DIVIDE(deadletter.deadletter_rows, NULLIF(raw.raw_rows + deadletter.deadletter_rows, 0)) AS reject_rate
        FROM raw, dedup, deadletter
        """
        df = self.run_query(query)
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_quality_by_event_type(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          COALESCE(event_type, 'Unknown') AS event_type,
          COUNT(*) AS total_events,
          COUNTIF(session_id IS NULL OR TRIM(session_id) = '') AS missing_session_id,
          COUNTIF(user_id IS NULL) AS missing_user_id,
          AVG(event_lag_seconds) AS avg_event_lag_seconds,
          APPROX_QUANTILES(event_lag_seconds, 100)[OFFSET(95)] AS p95_event_lag_seconds
        FROM {self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY event_type
        ORDER BY total_events DESC
        """
        return self.run_query(query)

    def get_source_browser_matrix(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          COALESCE(traffic_source, 'Unknown') AS traffic_source,
          COALESCE(browser, 'Unknown') AS browser,
          SUM(total_events) AS total_events,
          SUM(unique_sessions) AS unique_sessions,
          AVG(avg_event_lag_seconds) AS avg_event_lag_seconds
        FROM {self.table_ref('v_events_5m_latest')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY traffic_source, browser
        ORDER BY total_events DESC
        LIMIT 25
        """
        return self.run_query(query)

    def get_session_pipeline_health(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> dict:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        WITH sessions AS (
          SELECT
            COUNT(*) AS latest_sessions,
            COUNTIF(session_id IS NULL OR TRIM(session_id) = '') AS missing_session_id,
            COUNTIF(session_duration_seconds < 0) AS negative_duration_sessions,
            COUNTIF(event_count = 0) AS zero_event_sessions,
            AVG(event_count) AS avg_events_per_session,
            APPROX_QUANTILES(event_count, 100)[OFFSET(95)] AS p95_events_per_session,
            AVG(session_duration_seconds) AS avg_session_seconds,
            APPROX_QUANTILES(session_duration_seconds, 100)[OFFSET(95)] AS p95_session_seconds,
            MAX(session_end) AS latest_session_end,
            MAX(version_emitted_at) AS latest_version_emitted_at,
            MAX(processed_at) AS latest_processed_at
          FROM {self.table_ref('v_session_metrics_latest')}
          WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        ),
        versions AS (
          SELECT
            COUNT(*) AS session_metric_versions,
            COUNT(DISTINCT session_id) AS distinct_sessions,
            COUNT(*) - COUNT(DISTINCT session_id) AS superseded_versions
          FROM {self.table_ref('session_metrics')}
          WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {traffic_filter}
        )
        SELECT
          sessions.*,
          versions.session_metric_versions,
          versions.distinct_sessions,
          versions.superseded_versions,
          SAFE_DIVIDE(versions.superseded_versions, NULLIF(versions.session_metric_versions, 0)) AS superseded_version_rate,
          TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), sessions.latest_processed_at, SECOND) AS session_freshness_seconds
        FROM sessions, versions
        """
        df = self.run_query(query)
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_sessionization_timeseries(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          TIMESTAMP_TRUNC(session_start, HOUR) AS session_hour,
          COUNT(*) AS sessions,
          SUM(event_count) AS events_in_sessions,
          AVG(event_count) AS avg_events_per_session,
          AVG(session_duration_seconds) AS avg_session_seconds,
          MAX(version_emitted_at) AS latest_version_emitted_at
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY session_hour
        ORDER BY session_hour
        """
        return self.run_query(query)

    def get_session_anomaly_buckets(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT 'zero_event_sessions' AS check_name, COUNTIF(event_count = 0) AS sessions
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        UNION ALL
        SELECT 'single_event_sessions' AS check_name, COUNTIF(event_count = 1) AS sessions
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        UNION ALL
        SELECT 'negative_duration_sessions' AS check_name, COUNTIF(session_duration_seconds < 0) AS sessions
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        UNION ALL
        SELECT 'long_sessions_over_30m' AS check_name, COUNTIF(session_duration_seconds > 1800) AS sessions
        FROM {self.table_ref('v_session_metrics_latest')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        """
        return self.run_query(query)

    def get_session_versions_by_hour(self, start_date: str, end_date: str, traffic_sources: list[str] | None = None) -> pd.DataFrame:
        traffic_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        SELECT
          TIMESTAMP_TRUNC(version_emitted_at, HOUR) AS emitted_hour,
          COUNT(*) AS emitted_versions,
          COUNT(DISTINCT session_id) AS distinct_sessions,
          COUNT(*) - COUNT(DISTINCT session_id) AS superseded_versions
        FROM {self.table_ref('session_metrics')}
        WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          {traffic_filter}
        GROUP BY emitted_hour
        ORDER BY emitted_hour
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

def get_data_provider() -> DataProvider:
    return DataProvider()

data_provider = get_data_provider()
