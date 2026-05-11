import json
import logging
from datetime import datetime, timezone

from google.cloud import pubsub_v1


class ClickstreamEventPublisher:
    def __init__(self, project_id: str, topic_name: str, publish_timeout: int = 30):
        self.project_id = project_id
        self.topic_name = topic_name
        self.publish_timeout = publish_timeout
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project_id, topic_name)
        logging.info("Clickstream publisher initialized for topic %s with timeout %ds", self.topic_path, publish_timeout)

    @staticmethod
    def _normalize_timestamp(value) -> str:
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return str(value)

    def _build_payload(self, event) -> dict:
        return {
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

    def publish_async(self, event):
        payload = self._build_payload(event)
        return self.publisher.publish(
            self.topic_path,
            json.dumps(payload).encode("utf-8"),
            source="datagen",
            event_type=event.event_type,
        )

    def publish(self, event) -> None:
        self.publish_async(event).result(timeout=30)

    def publish_batch(self, events, timeout: int | None = None) -> int:
        effective_timeout = timeout if timeout is not None else self.publish_timeout
        futures = [self.publish_async(event) for event in events]
        for future in futures:
            future.result(timeout=effective_timeout)
        return len(events)
