import pandas as pd
from google.cloud import bigquery
from etl.config.settings import settings

class BigQueryLoader:
    def __init__(self):
        """Initializes the BigQuery client using project ID from settings."""
        self.client = bigquery.Client(project=settings.PROJECT_ID)
        self.dataset = settings.DATASET_ID

    def load(
        self,
        df: pd.DataFrame,
        table_name: str,
        write_mode: str = "WRITE_TRUNCATE"
    ):
        """
        Loads a Pandas DataFrame into BigQuery.
        Default write_mode is WRITE_TRUNCATE, but can be WRITE_APPEND for chunking.
        """
        table_id = f"{self.client.project}.{self.dataset}.{table_name}"
        
        # Configure the load job
        job_config = bigquery.LoadJobConfig(
            write_disposition=write_mode,
            autodetect=True, # Automatically infer schema
        )

        print(f"Loading {len(df)} rows into {table_id} (Mode: {write_mode})...")
        job = self.client.load_table_from_dataframe(df, table_id, job_config=job_config)
        
        # Wait for the job to complete
        job.result()
        print(f"Successfully loaded data into {table_id}.")

    def read(self, table_name: str) -> pd.DataFrame:
        """Reads a table from BigQuery into a DataFrame (useful for lookups)."""
        query = f"SELECT * FROM `{self.client.project}.{self.dataset}.{table_name}`"
        return self.client.query(query).to_dataframe()
