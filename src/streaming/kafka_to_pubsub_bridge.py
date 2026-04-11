import argparse
import json
from datetime import datetime, timezone

from confluent_kafka import Consumer
from google.cloud import pubsub_v1


def main():
    parser = argparse.ArgumentParser(description="Bridge Debezium Kafka topics to Google Pub/Sub")
    parser.add_argument("--bootstrap-servers", default="localhost:29092")
    parser.add_argument("--group-id", default="thelook-kafka-pubsub-bridge")
    parser.add_argument(
        "--topics",
        default="thelook.public.users,thelook.public.orders,thelook.public.order_items,thelook.public.events,thelook.public.products,thelook.public.distribution_centers",
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--pubsub-topic", required=True, help="Pub/Sub topic name (not full path)")
    args = parser.parse_args()

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(args.project_id, args.pubsub_topic)

    consumer = Consumer(
        {
            "bootstrap.servers": args.bootstrap_servers,
            "group.id": args.group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )

    topics = [t.strip() for t in args.topics.split(",") if t.strip()]
    consumer.subscribe(topics)
    print(f"Bridging Kafka topics {topics} -> Pub/Sub {topic_path}")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Kafka error: {msg.error()}")
                continue

            payload = {
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
                "key_json": msg.key().decode("utf-8") if msg.key() else None,
                "value_json": msg.value().decode("utf-8") if msg.value() else None,
            }

            future = publisher.publish(
                topic_path,
                json.dumps(payload).encode("utf-8"),
                source_topic=msg.topic(),
            )
            future.result()
    except KeyboardInterrupt:
        print("Stopping Kafka->Pub/Sub bridge...")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
