import argparse

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1


def main():
    parser = argparse.ArgumentParser(description="Create Pub/Sub topic and subscription for CDC pipeline")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--topic", default="thelook-cdc-events")
    parser.add_argument("--subscription", default="thelook-cdc-events-sub")
    args = parser.parse_args()

    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    topic_path = publisher.topic_path(args.project_id, args.topic)
    sub_path = subscriber.subscription_path(args.project_id, args.subscription)

    try:
        publisher.create_topic(request={"name": topic_path})
        print(f"Created topic: {topic_path}")
    except AlreadyExists:
        print(f"Topic exists: {topic_path}")

    try:
        subscriber.create_subscription(request={"name": sub_path, "topic": topic_path})
        print(f"Created subscription: {sub_path}")
    except AlreadyExists:
        print(f"Subscription exists: {sub_path}")


if __name__ == "__main__":
    main()
