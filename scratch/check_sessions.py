import os
from google.cloud import bigquery
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")
dataset = os.getenv("CLICKSTREAM_DATASET_ID", "thelook_clickstream")
client = bigquery.Client(project=project_id)

q = f"SELECT MAX(session_end) as m FROM `{project_id}.{dataset}.v_session_metrics_latest`"
df = client.query(q).to_dataframe()
print("Raw MAX(session_end) from v_session_metrics_latest:")
print(df)
