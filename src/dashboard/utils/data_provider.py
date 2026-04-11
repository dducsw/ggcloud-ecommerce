import streamlit as st
import pandas as pd
import os
from google.cloud import bigquery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DataProvider:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.dataset_id = os.getenv("DATASET_ID")
        try:
            if not self.project_id:
                raise ValueError("GCP_PROJECT_ID is not set in .env")
            self.client = bigquery.Client(project=self.project_id)
            print(f"Connected to BigQuery: {self.project_id}")
        except Exception as e:
            st.error(f"❌ BigQuery Connection Error: {e}")
            st.stop()

    @st.cache_data(ttl=600)
    def query(_self, table_name: str, query: str = None) -> pd.DataFrame:
        """
        Fetches data from BigQuery.
        If query is provided, it will be used directly.
        """
        if not query:
            query = f"SELECT * FROM `{_self.project_id}.{_self.dataset_id}.{table_name}`"
        return _self.client.query(query).to_dataframe()

    @st.cache_data(ttl=600)
    def get_kpis(_self):
        query = f"""
        SELECT 
            SUM(total_revenue) as total_revenue,
            COUNT(order_id) as total_orders,
            AVG(margin_percentage) * 100 as avg_margin_pct
        FROM `{_self.project_id}.{_self.dataset_id}.fact_orders`
        """
        df = _self.client.query(query).to_dataframe()
        return df.iloc[0].to_dict()

    @st.cache_data(ttl=120)
    def get_latest_freshness(_self):
        query = f"""
        SELECT run_id, status, started_at, finished_at, duration_seconds,
               users_changed, orders_changed, order_items_changed, events_changed
        FROM `{_self.project_id}.{_self.dataset_id}.etl_freshness`
        ORDER BY finished_at DESC
        LIMIT 1
        """
        try:
            df = _self.client.query(query).to_dataframe()
            if df.empty:
                return None
            return df.iloc[0].to_dict()
        except Exception:
            return None

data_provider = DataProvider()
