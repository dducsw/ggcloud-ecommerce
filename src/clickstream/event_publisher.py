import json
import logging
from datetime import datetime, timezone

from google.cloud import pubsub_v1


class ClickstreamEventPublisher:
    def __init__(self, project_id: str, topic_name: str):
        self.project_id = project_id
        self.topic_name = topic_name
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project_id, topic_name)
        logging.info("Clickstream publisher initialized for topic %s", self.topic_path)

    @staticmethod
    def _normalize_timestamp(value) -> str:
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return str(value)

    def publish(self, event) -> None:
        payload = {
            "event_id": int(event.id),
            "user_id": int(event.user_id) if event.user_id is not None else None,
            "sequence_number": int(event.sequence_number),
            "session_id": event.session_id,
            "ip_address": event.ip_address,
            "city": event.city,
            "state": event.state,
            "postal_code": event.postal_code,
            "browser": event.browser,
            "traffic_source": event.traffic_source,
            "uri": event.uri,
            "event_type": event.event_type,
            "event_timestamp": self._normalize_timestamp(event.created_at),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        future = self.publisher.publish(
            self.topic_path,
            json.dumps(payload).encode("utf-8"),
            source="datagen",
            event_type=event.event_type,
        )
        future.result(timeout=30)

