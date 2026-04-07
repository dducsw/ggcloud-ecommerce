import os
import glob
import io
import pandas as pd
from google.cloud import storage
import pyarrow.parquet as pq
from etl.config.settings import settings

class TheLookExtractor:
    def __init__(self):
        """Initializes the GCS and BigQuery clients."""
        self.storage_client = storage.Client(project=settings.PROJECT_ID)
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.staging_path = settings.GCS_STAGING_PATH

    def upload_local_to_gcs(self):
        """
        Scans local data/, converts CSV to Parquet in-memory, and uploads to GCS.
        Ensures strict data cleaning for column names and dates to prevent NaT errors.
        """
        local_dir = settings.LOCAL_DATA_DIR
        csv_files = glob.glob(os.path.join(local_dir, "*.csv"))
        
        if not csv_files:
            print(f"No CSV files found in {local_dir}")
            return

        bucket = self.storage_client.bucket(self.bucket_name)
        print(f"Converting and uploading {len(csv_files)} files to gs://{self.bucket_name}/{self.staging_path}/")
        
        for file_path in csv_files:
            original_name = os.path.basename(file_path)
            parts = original_name.split(".")
            table_name = parts[-2] if len(parts) >= 2 else parts[0]
            
            destination_blob_name = f"{self.staging_path}/{table_name}.parquet"
            blob = bucket.blob(destination_blob_name)
            
            print(f"Processing {original_name}...")
            
            # 1. Clean read: Skip initial spaces in CSV
            df = pd.read_csv(file_path, skipinitialspace=True)
            
            # 2. Clean columns: remove any hidden whitespace
            df.columns = df.columns.str.strip()
            
            # 3. Clean and parse dates
            date_cols = [c for c in df.columns if "_at" in c or "date" in c.lower()]
            for col in date_cols:
                # Force to string, strip ' UTC', then parse
                cleaned_dates = df[col].astype(str).str.replace(" UTC", "", regex=False).str.strip()
                df[col] = pd.to_datetime(cleaned_dates, errors="coerce").dt.tz_localize(None)

            # Convert to Parquet in memory
            buffer = io.BytesIO()
            df.to_parquet(buffer, index=False, engine="pyarrow")
            buffer.seek(0)
            blob.upload_from_file(buffer, content_type="application/octet-stream")
            
        print("Staging layer refreshed with clean Parquet files.")

    def _get_gcs_path(self, table_name: str) -> str:
        """Helper to construct GCS path for a parquet table."""
        return f"gs://{self.bucket_name}/{self.staging_path}/{table_name}.parquet"

    def get_users(self) -> pd.DataFrame:
        return pd.read_parquet(self._get_gcs_path("users"))

    def get_distribution_centers(self) -> pd.DataFrame:
        return pd.read_parquet(self._get_gcs_path("distribution_centers"))

    def get_products(self) -> pd.DataFrame:
        return pd.read_parquet(self._get_gcs_path("products"))

    def get_inventory_items(self) -> pd.DataFrame:
        return pd.read_parquet(self._get_gcs_path("inventory_items"))

    def get_orders(self) -> pd.DataFrame:
        return pd.read_parquet(self._get_gcs_path("orders"))

    def get_order_items(self) -> pd.DataFrame:
        return pd.read_parquet(self._get_gcs_path("order_items"))

    def get_events_chunks(self, chunk_size=100000):
        """
        Returns a generator of DataFrames for the events parquet table.
        Uses PyArrow to read row groups/batches efficiently.
        """
        path = self._get_gcs_path("events")
        print(f"Reading {path} in batches via PyArrow...")
        
        # We use a context-free approach for the generator
        parquet_file = pq.ParquetFile(path)
        
        # Iterate over record batches and convert to DataFrames
        for batch in parquet_file.iter_batches(batch_size=chunk_size):
            yield batch.to_pandas()
