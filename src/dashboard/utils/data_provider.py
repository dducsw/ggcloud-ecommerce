import os
from dataclasses import dataclass

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.cloud import bigquery


load_dotenv()


@dataclass(frozen=True)
class ClickstreamDatasets:
    project_id: str
    clickstream_dataset: str


class DataProvider:
    def __init__(self):
        project_id = os.getenv("GCP_PROJECT_ID")
        clickstream_dataset = os.getenv("CLICKSTREAM_DATASET_ID", "thelook_clickstream")
        if not project_id:
            st.error("BigQuery project is not configured. Set GCP_PROJECT_ID.")
            st.stop()

        self.config = ClickstreamDatasets(
            project_id=project_id,
            clickstream_dataset=clickstream_dataset,
        )
        self.client = bigquery.Client(project=project_id)

    @property
    def project_id(self) -> str:
        return self.config.project_id

    @property
    def clickstream_dataset(self) -> str:
        return self.config.clickstream_dataset

    @st.cache_data(ttl=300, show_spinner=False)
    def run_query(_self, query: str) -> pd.DataFrame:
        return _self.client.query(query).to_dataframe()

    def table_ref(self, table_name: str) -> str:
        return f"`{self.project_id}.{self.clickstream_dataset}.{table_name}`"

    @staticmethod
    def _quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _traffic_source_filter(self, traffic_sources: list[str] | None, column: str = "traffic_source") -> str:
        if not traffic_sources:
            return ""
        quoted = ", ".join(self._quote(source) for source in traffic_sources)
        return f" AND {column} IN ({quoted})"

    def latest_date_query(self) -> str:
        return f"SELECT MAX(event_date) AS max_date FROM {self.table_ref('v_events_raw_dedup')}"

    @st.cache_data(ttl=300, show_spinner=False)
    def get_latest_event_date(_self):
        df = _self.run_query(_self.latest_date_query())
        if df.empty or pd.isna(df.iloc[0]["max_date"]):
            return None
        return pd.to_datetime(df.iloc[0]["max_date"]).date()

    def get_traffic_sources(self, start_date: str, end_date: str) -> list[str]:
        query = f"""
        SELECT DISTINCT traffic_source
        FROM {self.table_ref('v_events_raw_dedup')}
        WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
          AND traffic_source IS NOT NULL
        ORDER BY traffic_source
        """
        df = self.run_query(query)
        return df["traffic_source"].dropna().tolist() if not df.empty else []

    def get_overview_metrics(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> dict:
        event_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        session_filter = self._traffic_source_filter(traffic_sources, "traffic_source")
        query = f"""
        WITH base AS (
          SELECT *
          FROM {self.table_ref('v_events_raw_dedup')}
          WHERE event_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {event_filter}
        ),
        sessions AS (
          SELECT *
          FROM {self.table_ref('v_session_metrics_latest')}
          WHERE session_date BETWEEN DATE('{start_date}') AND DATE('{end_date}')
            {session_filter}
        )
        SELECT
          (SELECT COUNT(*) FROM base) AS total_events,
          (SELECT COUNT(DISTINCT session_id) FROM base) AS total_sessions,
          (SELECT COUNT(DISTINCT user_id) FROM base WHERE user_id IS NOT NULL) AS total_users,
          (SELECT COUNTIF(event_type = 'purchase') FROM base) AS purchase_events,
          (SELECT SAFE_DIVIDE(COUNTIF(event_type = 'purchase'), COUNT(DISTINCT session_id)) FROM base) AS conversion_rate,
          (SELECT AVG(session_duration_seconds) FROM sessions) AS avg_session_seconds,
          (SELECT AVG(event_count) FROM sessions) AS avg_events_per_session,
          (SELECT AVG(pageview_count) FROM sessions) AS avg_pageviews_per_session,
          (SELECT AVG(product_view_count) FROM sessions) AS avg_product_views_per_session,
          (SELECT SAFE_DIVIDE(COUNTIF(added_to_cart), COUNT(*)) FROM sessions) AS cart_rate,
          (SELECT SAFE_DIVIDE(COUNTIF(purchased), COUNT(*)) FROM sessions) AS session_purchase_rate
        """
        df = self.run_query(query)
        return df.iloc[0].to_dict() if not df.empty else {}

    def get_daily_events_and_purchases(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_channel_distribution(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_realtime_windows(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_event_type_breakdown(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_session_summary(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> dict:
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

    def get_conversion_funnel(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_session_duration_histogram(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_cvr_by_channel(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_cvr_by_browser(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_top_categories(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_popular_pages(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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

    def get_session_quality(
        self, start_date: str, end_date: str, traffic_sources: list[str] | None = None
    ) -> pd.DataFrame:
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


data_provider = DataProvider()
