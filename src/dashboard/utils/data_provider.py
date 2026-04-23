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

    @st.cache_data(ttl=300, show_spinner=False)
    def get_latest_date(_self):
        q = f"SELECT MAX(date) as m FROM {_self._t('agg_dashboard_daily')}"
        df = _self.run_query(q)
        if df.empty or pd.isna(df.iloc[0]['m']):
            q_fallback = f"SELECT MAX(DATE(created_at)) as m FROM {_self._t('fact_orders')}"
            df = _self.run_query(q_fallback)
            if df.empty or pd.isna(df.iloc[0]['m']):
                return None
        return pd.to_datetime(df.iloc[0]['m']).date()

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

@st.cache_resource(show_spinner=False)
def get_data_provider() -> DataProvider:
    return DataProvider()


data_provider = get_data_provider()
