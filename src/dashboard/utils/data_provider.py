import streamlit as st
import pandas as pd
import os
from google.cloud import bigquery
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

class DataProvider:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.dataset_id = os.getenv("DATASET_ID")
        # Default to False (BigQuery) unless specified
        self.use_local = os.getenv("USE_LOCAL_DWH", "false").lower() == "true"
        
        # Local DWH path
        self.local_dwh_path = Path(__file__).parent.parent.parent.parent / "dwh"
        
        if not self.use_local:
            try:
                if not self.project_id:
                    raise ValueError("GCP_PROJECT_ID is not set in .env")
                self.client = bigquery.Client(project=self.project_id)
                print(f"Connected to BigQuery: {self.project_id}")
            except Exception as e:
                st.error(f"❌ BigQuery Connection Error: {e}")
                st.info("To use local data, set USE_LOCAL_DWH=true in your .env file.")
                st.stop() # Stop app if BQ is requested but fails

    @st.cache_data(ttl=600)
    def query(_self, table_name: str, query: str = None) -> pd.DataFrame:
        """
        Fetches data from BigQuery or Local CSV.
        If query is provided, it's used for BigQuery.
        For local, it just reads the table_name.csv.
        """
        if _self.use_local:
            file_path = _self.local_dwh_path / f"{table_name}.csv"
            if file_path.exists():
                return pd.read_csv(file_path)
            else:
                st.error(f"Local file not found: {file_path}")
                return pd.DataFrame()
        else:
            if not query:
                query = f"SELECT * FROM `{_self.project_id}.{_self.dataset_id}.{table_name}`"
            return _self.client.query(query).to_dataframe()

    @st.cache_data(ttl=600)
    def get_kpis(_self):
        if _self.use_local:
            orders = _self.query("fact_orders")
            if orders.empty:
                return {"total_revenue": 0, "total_orders": 0, "avg_margin_pct": 0}
            return {
                "total_revenue": orders["total_revenue"].sum() if "total_revenue" in orders else 0,
                "total_orders": len(orders),
                "avg_margin_pct": orders["margin_percentage"].mean() * 100 if "margin_percentage" in orders else 0
            }
        else:
            query = f"""
            SELECT 
                SUM(total_revenue) as total_revenue,
                COUNT(order_id) as total_orders,
                AVG(margin_percentage) * 100 as avg_margin_pct
            FROM `{_self.project_id}.{_self.dataset_id}.fact_orders`
            """
            df = _self.client.query(query).to_dataframe()
            return df.iloc[0].to_dict()

data_provider = DataProvider()
