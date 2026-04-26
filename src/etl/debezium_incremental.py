import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1


load_dotenv()


def ensure_pubsub_resources(project_id: str, cdc_topic: str, cdc_subscription: str, events_topic: str, events_subscription: str) -> None:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    resources = [
        (cdc_topic, cdc_subscription),
        (events_topic, events_subscription),
    ]

    for topic_name, subscription_name in resources:
        topic_path = publisher.topic_path(project_id, topic_name)
        subscription_path = subscriber.subscription_path(project_id, subscription_name)

        try:
            publisher.create_topic(request={"name": topic_path})
            print(f"Created topic: {topic_path}")
        except AlreadyExists:
            print(f"Topic exists: {topic_path}")

        try:
            subscriber.create_subscription(
                request={"name": subscription_path, "topic": topic_path}
            )
            print(f"Created subscription: {subscription_path}")
        except AlreadyExists:
            print(f"Subscription exists: {subscription_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Debezium Server incremental CDC flow for local Postgres -> Pub/Sub -> GCS/BQ."
    )
    parser.add_argument(
        "--debezium-server-config",
        default="infra/cdc/debezium-server/conf/application.properties",
    )
    parser.add_argument(
        "--project-id",
        default=os.getenv("GCP_PROJECT_ID", "cloud-data-project-492514"),
    )
    parser.add_argument(
        "--gcs-prefix",
        default=f"gs://{os.getenv('GCS_BUCKET_NAME', 'etl-staging-0')}/{os.getenv('GCS_STAGING_PATH', 'raw')}",
    )
    parser.add_argument(
        "--bronze-dataset",
        default=os.getenv("BRONZE_DATASET_ID", "thelook_staging"),
    )
    parser.add_argument("--cdc-topic", default="thelook-cdc-events")
    parser.add_argument("--cdc-subscription", default="thelook-cdc-events-sub")
    parser.add_argument("--events-topic", default="thelook_clickstream_events")
    parser.add_argument("--events-subscription", default="thelook_clickstream_events-sub")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.debezium_server_config)
    if not config_path.exists():
        raise FileNotFoundError(f"Missing Debezium Server config: {config_path}")

    ensure_pubsub_resources(
        project_id=args.project_id,
        cdc_topic=args.cdc_topic,
        cdc_subscription=args.cdc_subscription,
        events_topic=args.events_topic,
        events_subscription=args.events_subscription,
    )

    print("")
    print("Incremental CDC preparation complete.")
    print("Debezium Server is configured to publish directly to Pub/Sub from:")
    print(f"  {config_path}")
    print("No Kafka Connect sink is used in this flow.")
    print("")
    print("Next steps:")
    print("1. Start `debezium-server` so PostgreSQL changes are published directly to Pub/Sub.")
    print("2. Run the streaming router so Debezium changes land in the same bronze naming layout as the full load.")
    print("Suggested local command:")
    print(
        "python src/dataflow/beam_router.py "
        f"--project {args.project_id} "
        "--runner DirectRunner "
        f"--temp_location {args.gcs_prefix.rsplit('/', 1)[0]}/tmp "
        f"--staging_location {args.gcs_prefix.rsplit('/', 1)[0]}/staging "
        f"--pubsub_subscription projects/{args.project_id}/subscriptions/{args.cdc_subscription} "
        f"--events_subscription projects/{args.project_id}/subscriptions/{args.events_subscription} "
        f"--bronze_dataset {args.bronze_dataset} "
        f"--gcs_output_prefix {args.gcs_prefix}"
    )
    print("")
    print("Cold-path CDC tables written to GCS Parquet under:")
    print(f"  {args.gcs_prefix}/users/")
    print(f"  {args.gcs_prefix}/products/")
    print(f"  {args.gcs_prefix}/dist_centers/")
    print(f"  {args.gcs_prefix}/inventory_items/")
    print(f"  {args.gcs_prefix}/orders/")
    print(f"  {args.gcs_prefix}/order_items/")
    print("Hot-path events continue to stream into BigQuery bronze table:")
    print(f"  {args.project_id}:{args.bronze_dataset}.events")


if __name__ == "__main__":
    main()
