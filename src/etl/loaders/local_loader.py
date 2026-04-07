import os
import pandas as pd
from etl.config.settings import settings

class LocalLoader:
    def __init__(self):
        """Initializes the local loader using settings."""
        self.dwh_dir = settings.LOCAL_DWH_DIR
        # Ensure the dwh directory exists
        os.makedirs(self.dwh_dir, exist_ok=True)

    def load(
        self,
        df: pd.DataFrame,
        table_name: str,
        write_mode: str = "WRITE_TRUNCATE"
    ):
        """
        Loads a Pandas DataFrame into a local CSV file.
        Default write_mode is WRITE_TRUNCATE (overwrites).
        Can be WRITE_APPEND for chunking (appends to existing file).
        """
        file_path = os.path.join(self.dwh_dir, f"{table_name}.csv")
        
        # 1. Handle write mode
        if write_mode == "WRITE_TRUNCATE":
            print(f"Loading {len(df)} rows into {file_path} (Mode: {write_mode})...")
            df.to_csv(file_path, index=False)
        elif write_mode == "WRITE_APPEND":
            print(f"Appending {len(df)} rows into {file_path}...")
            # Append to file, if file does not exist, include header
            header = not os.path.exists(file_path)
            df.to_csv(file_path, mode='a', index=False, header=header)
        else:
            raise ValueError(f"Unsupported write_mode: {write_mode}")

        print(f"Successfully saved data to {file_path}.")

    def read(self, table_name: str) -> pd.DataFrame:
        """Reads a table from the local dwh folder into a DataFrame (useful for lookups)."""
        file_path = os.path.join(self.dwh_dir, f"{table_name}.csv")
        if not os.path.exists(file_path):
             raise FileNotFoundError(f"DWH table '{table_name}' not found at {file_path}. Did you run the Dimensions Pipeline first?")
        
        print(f"Reading {table_name} from {file_path} for lookup...")
        return pd.read_csv(file_path)
