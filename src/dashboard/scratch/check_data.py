import os
from dotenv import load_dotenv
from google.cloud import bigquery
import pandas as pd

load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")
dataset = os.getenv("DWH_DATASET_ID") or "thelook_datawarehouse"
client = bigquery.Client(project=project_id)

def check_dates():
    q_orders = f"SELECT * FROM `{project_id}.{dataset}.fact_orders` LIMIT 1"
    df_orders = client.query(q_orders).to_dataframe()
    print("fact_orders columns:")
    print(df_orders.columns.tolist())
    
    q_users = f"SELECT * FROM `{project_id}.{dataset}.dim_users` LIMIT 1"
    df_users = client.query(q_users).to_dataframe()
    print("\ndim_users columns:")
    print(df_users.columns.tolist())






if __name__ == "__main__":
    check_dates()
