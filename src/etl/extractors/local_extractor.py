import os
import glob
import pandas as pd
from etl.config.settings import settings

class LocalExtractor:
    def __init__(self):
        """Initializes the local extractor using settings."""
        self.local_dir = settings.LOCAL_DATA_DIR

    def _read_csv(self, table_name: str) -> pd.DataFrame:
        """Helper to read and clean local CSV files."""
        # Find the file that matches the table name (e.g., thelook_ecommerce.users.csv)
        file_pattern = os.path.join(self.local_dir, f"*{table_name}.csv")
        files = glob.glob(file_pattern)
        
        if not files:
            raise FileNotFoundError(f"No CSV file found for table '{table_name}' in {self.local_dir}")
        
        file_path = files[0]
        print(f"Extracting {table_name} from {file_path}...")
        
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
            
        return df

    def get_users(self) -> pd.DataFrame:
        return self._read_csv("users")

    def get_distribution_centers(self) -> pd.DataFrame:
        return self._read_csv("distribution_centers")

    def get_products(self) -> pd.DataFrame:
        return self._read_csv("products")

    def get_inventory_items(self) -> pd.DataFrame:
        return self._read_csv("inventory_items")

    def get_orders(self) -> pd.DataFrame:
        return self._read_csv("orders")

    def get_order_items(self) -> pd.DataFrame:
        return self._read_csv("order_items")

    def get_events_chunks(self, chunk_size=100000):
        """
        Returns a generator of DataFrames for the events CSV file.
        Uses pandas chunking for memory efficiency.
        """
        file_pattern = os.path.join(self.local_dir, "*events.csv")
        files = glob.glob(file_pattern)
        
        if not files:
            raise FileNotFoundError(f"No CSV file found for table 'events' in {self.local_dir}")
        
        file_path = files[0]
        print(f"Reading {file_path} in chunks of {chunk_size}...")
        
        for df in pd.read_csv(file_path, skipinitialspace=True, chunksize=chunk_size):
            # Clean columns: remove any hidden whitespace
            df.columns = df.columns.str.strip()
            
            # Clean and parse dates
            date_cols = [c for c in df.columns if "_at" in c or "date" in c.lower()]
            for col in date_cols:
                cleaned_dates = df[col].astype(str).str.replace(" UTC", "", regex=False).str.strip()
                df[col] = pd.to_datetime(cleaned_dates, errors="coerce").dt.tz_localize(None)
                
            yield df
