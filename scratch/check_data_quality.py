from google.cloud import bigquery
import pandas as pd
import json

project_id = "cloud-data-project-492514"
dataset_id = "thelook_clickstream"
client = bigquery.Client(project=project_id)

def run_query(sql):
    try:
        return client.query(sql).to_dataframe()
    except Exception as e:
        return str(e)

results = {}

# 1. Basic Stats
results["basic_stats"] = run_query(f"""
    SELECT 
        count(*) as total_rows, 
        count(DISTINCT event_id) as unique_events,
        MIN(event_timestamp) as min_timestamp,
        MAX(event_timestamp) as max_timestamp,
        count(DISTINCT session_id) as unique_sessions,
        count(DISTINCT user_id) as unique_users
    FROM `{project_id}.{dataset_id}.events_raw`
""").to_dict(orient="records")

# 2. Null Checks
results["null_checks"] = run_query(f"""
    SELECT
        countIF(user_id IS NULL) as null_users,
        countIF(product_id IS NULL AND event_type IN ('product', 'cart', 'purchase')) as null_products_in_product_events,
        countIF(product_name IS NULL AND product_id IS NOT NULL) as failed_enrichments,
        countIF(city IS NULL) as null_city,
        countIF(traffic_source IS NULL) as null_traffic_source
    FROM `{project_id}.{dataset_id}.events_raw`
""").to_dict(orient="records")

# 3. Data Distribution
results["event_type_distribution"] = run_query(f"""
    SELECT event_type, COUNT(*) as count
    FROM `{project_id}.{dataset_id}.events_raw`
    GROUP BY 1 ORDER BY 2 DESC
""").to_dict(orient="records")

# 4. Deadletter Check
results["deadletter_stats"] = run_query(f"""
    SELECT error_message, count(*) as count
    FROM `{project_id}.{dataset_id}.events_deadletter`
    GROUP BY 1 ORDER BY 2 DESC
""").to_dict(orient="records")

# 5. Enrichment Samples (Check if product names are joining correctly)
results["enrichment_samples"] = run_query(f"""
    SELECT product_id, product_name, product_category, count(*) as count
    FROM `{project_id}.{dataset_id}.events_raw`
    WHERE product_id IS NOT NULL
    GROUP BY 1, 2, 3
    LIMIT 10
""").to_dict(orient="records")

print(json.dumps(results, indent=2, default=str))
