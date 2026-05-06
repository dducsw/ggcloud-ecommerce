import os
from google.cloud import bigquery
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")
dataset = os.getenv("CLICKSTREAM_DATASET_ID", "thelook_clickstream")
client = bigquery.Client(project=project_id)

q = f"SELECT MAX(event_timestamp) as m FROM `{project_id}.{dataset}.v_events_raw_dedup`"
df = client.query(q).to_dataframe()
print("Raw MAX(event_timestamp):")
print(df)
print("Type:", type(df.iloc[0]['m']))

if not df.empty and not pd.isna(df.iloc[0]['m']):
    ts = pd.to_datetime(df.iloc[0]['m'])
    print("\nAfter pd.to_datetime:")
    print(ts)
    print("tzinfo:", ts.tzinfo)

q2 = f"SELECT MAX(window_start) as m FROM `{project_id}.{dataset}.v_events_5m_latest`"
df2 = client.query(q2).to_dataframe()
print("\nRaw MAX(window_start) from v_events_5m_latest:")
print(df2)
