import logging
from pathlib import Path
import argparse

from src.clickstream.pipeline import run_pipeline


def run(argv=None):
    logging.getLogger().setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description="Advanced clickstream processing from Pub/Sub to BigQuery")
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="asia-southeast1")
    parser.add_argument("--runner", default="DataflowRunner")
    parser.add_argument("--temp_location", required=True)
    parser.add_argument("--staging_location", required=True)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--dataset", default="thelook_clickstream")
    parser.add_argument("--raw_table", default="events_raw")
    parser.add_argument("--deadletter_table", default="events_deadletter")
    parser.add_argument("--aggregate_table", default="events_5m")
    parser.add_argument("--session_table", default="session_metrics")
    parser.add_argument("--product_lookup_project", default=None)
    parser.add_argument("--product_lookup_dataset", default="thelook_staging")
    parser.add_argument("--product_lookup_table", default="products")
    parser.add_argument("--product_refresh_minutes", type=int, default=15)
    parser.add_argument("--products_csv", default=str(Path("datagen/thelook-ecomm/src/data/products.csv")))
    parser.add_argument("--allowed_lateness_seconds", type=int, default=600)
    parser.add_argument("--early_firing_delay_seconds", type=int, default=60)
    parser.add_argument("--late_firing_count", type=int, default=1)
    parser.add_argument("--session_gap_minutes", type=int, default=30)
    parser.add_argument("--dedup_ttl_minutes", type=int, default=60)

    known_args, pipeline_args = parser.parse_known_args(argv)
    run_pipeline(known_args, pipeline_args)


if __name__ == "__main__":
    run()
