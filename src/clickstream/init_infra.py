import argparse
import logging
from google.cloud import bigquery
from google.cloud import pubsub_v1
from google.api_core import exceptions

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def create_bq_resources(project_id, dataset_id, location="asia-southeast1"):
    client = bigquery.Client(project=project_id)
    
    # Create Dataset
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        client.get_dataset(dataset_ref)
        logging.info(f"Dataset {dataset_id} already exists.")
    except exceptions.NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = location
        dataset.description = "Clickstream analytics dataset"
        client.create_dataset(dataset)
        logging.info(f"Created dataset {dataset_id} in {location}")

    # Helper for DDL
    def run_query(sql):
        query_job = client.query(sql)
        query_job.result()
        logging.info(f"Executed DDL: {sql[:50]}...")

    # Tables DDL
    tables = {
        "events_raw": f"""
            CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.events_raw` (
              event_id INT64 NOT NULL,
              user_id INT64,
              sequence_number INT64,
              session_id STRING,
              ip_address STRING,
              city STRING,
              state STRING,
              postal_code STRING,
              browser STRING,
              traffic_source STRING,
              uri STRING,
              event_type STRING,
              event_timestamp TIMESTAMP NOT NULL,
              event_date DATE NOT NULL,
              ingested_at TIMESTAMP NOT NULL,
              page_type STRING,
              product_id INT64,
              product_category STRING,
              product_department STRING,
              product_name STRING,
              is_conversion BOOL NOT NULL,
              processing_time TIMESTAMP NOT NULL,
              event_lag_seconds FLOAT64
            )
            PARTITION BY event_date
            CLUSTER BY event_type, traffic_source, browser
        """,
        "events_deadletter": f"""
            CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.events_deadletter` (
              raw_message STRING,
              error_message STRING NOT NULL,
              failed_at TIMESTAMP NOT NULL
            )
            PARTITION BY DATE(failed_at)
        """,
        "events_5m": f"""
            CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.events_5m` (
              aggregate_id STRING NOT NULL,
              window_start TIMESTAMP NOT NULL,
              window_end TIMESTAMP NOT NULL,
              event_date DATE NOT NULL,
              traffic_source STRING,
              browser STRING,
              event_type STRING,
              page_type STRING,
              total_events INT64 NOT NULL,
              unique_sessions INT64 NOT NULL,
              unique_users INT64 NOT NULL,
              purchase_events INT64 NOT NULL,
              avg_event_lag_seconds FLOAT64,
              version_emitted_at TIMESTAMP NOT NULL
            )
            PARTITION BY event_date
            CLUSTER BY aggregate_id, traffic_source, event_type, page_type
        """,
        "session_metrics": f"""
            CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.session_metrics` (
              session_record_id STRING NOT NULL,
              session_id STRING NOT NULL,
              user_id INT64,
              traffic_source STRING,
              browser STRING,
              session_start TIMESTAMP NOT NULL,
              session_end TIMESTAMP NOT NULL,
              session_duration_seconds FLOAT64 NOT NULL,
              event_count INT64 NOT NULL,
              pageview_count INT64 NOT NULL,
              product_view_count INT64 NOT NULL,
              cart_count INT64 NOT NULL,
              purchase_count INT64 NOT NULL,
              saw_home BOOL NOT NULL,
              saw_product BOOL NOT NULL,
              added_to_cart BOOL NOT NULL,
              purchased BOOL NOT NULL,
              top_category STRING,
              session_date DATE NOT NULL,
              version_emitted_at TIMESTAMP NOT NULL,
              processed_at TIMESTAMP NOT NULL
            )
            PARTITION BY session_date
            CLUSTER BY session_record_id, traffic_source, browser, purchased
        """
    }

    for table_name, ddl in tables.items():
        run_query(ddl)

    # Views DDL
    views = {
        "v_events_5m_latest": f"""
            CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.v_events_5m_latest` AS
            SELECT * FROM `{project_id}.{dataset_id}.events_5m`
            QUALIFY ROW_NUMBER() OVER (PARTITION BY aggregate_id ORDER BY version_emitted_at DESC) = 1
        """,
        "v_events_raw_dedup": f"""
            CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.v_events_raw_dedup` AS
            SELECT * FROM `{project_id}.{dataset_id}.events_raw`
            QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY ingested_at DESC, processing_time DESC) = 1
        """,
        "v_session_metrics_latest": f"""
            CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.v_session_metrics_latest` AS
            SELECT * FROM `{project_id}.{dataset_id}.session_metrics`
            QUALIFY ROW_NUMBER() OVER (PARTITION BY session_record_id ORDER BY version_emitted_at DESC) = 1
        """,
        "v_session_funnel": f"""
            CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.v_session_funnel` AS
            SELECT
              session_id, user_id, traffic_source, browser, session_start AS session_started_at,
              saw_home, saw_product, added_to_cart, purchased, session_duration_seconds, event_count, top_category
            FROM `{project_id}.{dataset_id}.v_session_metrics_latest`
        """,
        "v_daily_channel_kpis": f"""
            CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.v_daily_channel_kpis` AS
            SELECT
              event_date, traffic_source, COUNT(*) AS total_events, COUNT(DISTINCT session_id) AS total_sessions,
              COUNT(DISTINCT user_id) AS total_users, COUNTIF(event_type = 'purchase') AS purchase_events,
              SAFE_DIVIDE(COUNTIF(event_type = 'purchase'), COUNT(DISTINCT session_id)) AS purchase_per_session
            FROM `{project_id}.{dataset_id}.v_events_raw_dedup`
            GROUP BY 1, 2
        """,
        "v_product_interest": f"""
            CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.v_product_interest` AS
            SELECT
              event_date, product_id, product_name, product_category, product_department,
              COUNTIF(event_type = 'product') AS product_views,
              COUNTIF(event_type = 'cart') AS add_to_cart_events,
              COUNTIF(event_type = 'purchase') AS purchase_events
            FROM `{project_id}.{dataset_id}.v_events_raw_dedup`
            WHERE product_id IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5
        """
    }

    for view_name, ddl in views.items():
        run_query(ddl)

def truncate_bq_tables(project_id, dataset_id):
    client = bigquery.Client(project=project_id)
    tables = ["events_raw", "events_deadletter", "events_5m", "session_metrics"]
    
    for table_id in tables:
        full_table_id = f"{project_id}.{dataset_id}.{table_id}"
        query = f"TRUNCATE TABLE `{full_table_id}`"
        try:
            client.query(query).result()
            logging.info(f"Successfully truncated table: {full_table_id}")
        except Exception as e:
            logging.warning(f"Could not truncate table {full_table_id} (it might not exist yet): {e}")

def create_pubsub_resources(project_id, topic_id, subscription_id):
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    
    topic_path = publisher.topic_path(project_id, topic_id)
    subscription_path = subscriber.subscription_path(project_id, subscription_id)

    # Create Topic
    try:
        publisher.get_topic(request={"topic": topic_path})
        logging.info(f"Topic {topic_path} already exists.")
    except exceptions.NotFound:
        publisher.create_topic(request={"name": topic_path})
        logging.info(f"Created topic {topic_path}")

    # Create Subscription
    try:
        subscriber.get_subscription(request={"subscription": subscription_path})
        logging.info(f"Subscription {subscription_path} already exists.")
    except exceptions.NotFound:
        subscriber.create_subscription(request={"name": subscription_path, "topic": topic_path, "ack_deadline_seconds": 20})
        logging.info(f"Created subscription {subscription_path}")

def main():
    parser = argparse.ArgumentParser(description="Setup Clickstream Infrastructure (BigQuery & Pub/Sub)")
    parser.add_argument("--project", required=True, help="GCP Project ID")
    parser.add_argument("--dataset", default="thelook_clickstream", help="BigQuery Dataset ID")
    parser.add_argument("--location", default="asia-southeast1", help="BigQuery Dataset Location")
    parser.add_argument("--topic", default="clickstream_topic", help="Pub/Sub Topic ID")
    parser.add_argument("--subscription", default="clickstream_topic-sub", help="Pub/Sub Subscription ID")
    parser.add_argument("--truncate", action="store_true", help="Truncate existing BigQuery tables for a clean start")
    
    args = parser.parse_args()
    
    logging.info(f"Configuring Clickstream infrastructure for project: {args.project}")
    create_bq_resources(args.project, args.dataset, args.location)
    
    if args.truncate:
        logging.info("Truncating BigQuery tables as requested...")
        truncate_bq_tables(args.project, args.dataset)
        
    create_pubsub_resources(args.project, args.topic, args.subscription)
    logging.info("Infrastructure setup complete.")

if __name__ == "__main__":
    main()
