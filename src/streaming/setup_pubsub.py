import argparse

from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1


def main():
    parser = argparse.ArgumentParser(description="Create Pub/Sub topic and subscription for CDC pipeline")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--topic", default="thelook-cdc-events")
    parser.add_argument("--subscription", default="thelook-cdc-events-sub")
    parser.add_argument("--events-topic", default="thelook_clickstream_events", help="Dedicated topic for events table")
    parser.add_argument("--events-subscription", default="thelook_clickstream_events-sub", help="Dedicated subscription for events table")
    args = parser.parse_args()

    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    topics_to_create = [
        (args.topic, args.subscription),
        (args.events_topic, args.events_subscription)
    ]

    for t_name, s_name in topics_to_create:
        topic_path = publisher.topic_path(args.project_id, t_name)
        sub_path = subscriber.subscription_path(args.project_id, s_name)

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
