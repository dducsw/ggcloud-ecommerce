import json
import logging
import threading

import apache_beam as beam
from apache_beam.coders import BooleanCoder
from apache_beam.metrics import Metrics
from apache_beam.transforms.userstate import ReadModifyWriteStateSpec, TimeDomain, TimerSpec, on_timer

from src.clickstream.pipeline.utils import parse_iso8601, parse_uri, to_timestamp_string, utc_now

PAGEVIEW_TYPES = {"home", "department", "category", "product"}
VALID_EVENT_TYPES = {"home", "department", "category", "product", "cart", "purchase", "cancel", "return"}
MAX_EVENTS_PER_SESSION = 5000


class ParseValidateDoFn(beam.DoFn):
    DEADLETTER_TAG = "deadletter"
    _processed_lock = threading.Lock()
    _total_processed = 0

    def __init__(self, log_every_n_valid: int = 100, log_invalid_messages: bool = True):
        self.log_every_n_valid = log_every_n_valid
        self.log_invalid_messages = log_invalid_messages
        self.valid_counter = Metrics.counter("clickstream", "valid_events")
        self.invalid_counter = Metrics.counter("clickstream", "invalid_events")

    def process(self, message: bytes):
        try:
            raw_text = message.decode("utf-8")
            payload = json.loads(raw_text)

            event_id = payload.get("event_id", payload.get("id"))
            event_timestamp_raw = payload.get("event_timestamp", payload.get("created_at"))
            ingested_at_raw = payload.get("ingested_at", event_timestamp_raw)

            required_values = {
                "event_id": event_id,
                "session_id": payload.get("session_id"),
                "event_type": payload.get("event_type"),
                "event_timestamp": event_timestamp_raw,
                "ingested_at": ingested_at_raw,
            }
            missing = [field for field, value in required_values.items() if value in (None, "")]
            if missing:
                raise ValueError(f"Missing required fields: {', '.join(missing)}")

            event_type = str(payload.get("event_type"))
            if event_type not in VALID_EVENT_TYPES:
                raise ValueError(f"Unknown event_type: {event_type}")

            event_ts = parse_iso8601(str(event_timestamp_raw))
            ingested_at = parse_iso8601(str(ingested_at_raw))
            row = {
                "event_id": int(event_id),
                "user_id": int(payload["user_id"]) if payload.get("user_id") is not None else None,
                "sequence_number": int(payload["sequence_number"]) if payload.get("sequence_number") is not None else None,
                "session_id": str(payload["session_id"]),
                "ip_address": payload.get("ip_address"),
                "city": payload.get("city"),
                "state": payload.get("state"),
                "postal_code": payload.get("postal_code"),
                "browser": payload.get("browser"),
                "traffic_source": payload.get("traffic_source"),
                "uri": payload.get("uri"),
                "event_type": event_type,
                "event_timestamp": to_timestamp_string(event_ts),
                "event_date": event_ts.date().isoformat(),
                "ingested_at": to_timestamp_string(ingested_at),
            }
            self.valid_counter.inc()
            
            with ParseValidateDoFn._processed_lock:
                ParseValidateDoFn._total_processed += 1
                current_count = ParseValidateDoFn._total_processed
            
            if self.log_every_n_valid > 0 and current_count % self.log_every_n_valid == 0:
                logging.info(f" >>> [Dataflow] Total records processed: {current_count}")
            yield beam.window.TimestampedValue(row, event_ts.timestamp())
        except Exception as exc:
            self.invalid_counter.inc()
            if self.log_invalid_messages:
                logging.warning("Invalid clickstream message: %s", exc)
            yield beam.pvalue.TaggedOutput(
                self.DEADLETTER_TAG,
                {
                    "raw_message": message.decode("utf-8", errors="replace"),
                    "error_message": str(exc),
                    "failed_at": to_timestamp_string(utc_now()),
                },
            )


class EnrichEventDoFn(beam.DoFn):
    def __init__(self):
        self.enriched_counter = Metrics.counter("clickstream", "enriched_events")

    def process(self, row: dict, product_map: dict):
        enriched = dict(row)
        uri = enriched.get("uri")
        try:
            uri_info = parse_uri(uri)
        except Exception as e:
            logging.warning(f"Failed to parse URI {uri}: {e}")
            uri_info = {"page_type": "unknown", "product_id": None}
            
        product_id = uri_info["product_id"]
        product = product_map.get(product_id) if product_id is not None else None
        event_ts = parse_iso8601(enriched["event_timestamp"])
        ingested_at = parse_iso8601(enriched["ingested_at"])
        now = utc_now()

        enriched["page_type"] = uri_info["page_type"]
        enriched["product_id"] = product_id
        enriched["product_category"] = product.get("category") if product else None
        enriched["product_department"] = product.get("department") if product else None
        enriched["product_name"] = product.get("name") if product else None
        enriched["is_conversion"] = enriched.get("event_type") == "purchase"
        enriched["processing_time"] = to_timestamp_string(now)
        enriched["event_lag_seconds"] = max(0.0, (ingested_at - event_ts).total_seconds())
        
        self.enriched_counter.inc()
        yield enriched


class LogCountDoFn(beam.DoFn):
    """A simple DoFn to log progress every N records."""
    _count_lock = threading.Lock()
    _counts = {}

    def __init__(self, name: str, interval: int = 100):
        self.name = name
        self.interval = interval

    def process(self, element):
        with LogCountDoFn._count_lock:
            LogCountDoFn._counts[self.name] = LogCountDoFn._counts.get(self.name, 0) + 1
            current = LogCountDoFn._counts[self.name]

        if current % self.interval == 0:
            logging.info(f" [Progress] {self.name}: {current} records processed")
        yield element


class DeduplicateEventsDoFn(beam.DoFn):
    SEEN_STATE = ReadModifyWriteStateSpec("seen", BooleanCoder())
    CLEAR_TIMER = TimerSpec("clear", TimeDomain.WATERMARK)

    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self.duplicate_counter = Metrics.counter("clickstream", "duplicate_events")

    def process(
        self,
        element,
        timestamp=beam.DoFn.TimestampParam,
        seen_state=beam.DoFn.StateParam(SEEN_STATE),
        clear_timer=beam.DoFn.TimerParam(CLEAR_TIMER),
    ):
        _, row = element
        if seen_state.read():
            self.duplicate_counter.inc()
            return

        seen_state.write(True)
        clear_timer.set(timestamp + self.ttl_seconds)
        yield row

    @on_timer(CLEAR_TIMER)
    def clear_seen(self, seen_state=beam.DoFn.StateParam(SEEN_STATE)):
        seen_state.clear()




def to_aggregate_key(row: dict):
    return (
        row.get("event_date"),
        row.get("traffic_source"),
        row.get("browser"),
        row.get("event_type"),
        row.get("page_type"),
    )


def create_aggregate_record(element, window=beam.DoFn.WindowParam):
    key, rows = element
    rows = list(rows)
    now = utc_now()
    event_date, traffic_source, browser, event_type, page_type = key
    window_start = to_timestamp_string(window.start.to_utc_datetime())
    window_end = to_timestamp_string(window.end.to_utc_datetime())
    aggregate_id = "|".join(
        [
            window_start,
            event_date or "",
            traffic_source or "",
            browser or "",
            event_type or "",
            page_type or "",
        ]
    )
    session_ids = {row.get("session_id") for row in rows if row.get("session_id")}
    user_ids = {row.get("user_id") for row in rows if row.get("user_id") is not None}
    purchase_events = sum(1 for row in rows if row.get("is_conversion"))
    lags = [row["event_lag_seconds"] for row in rows if row.get("event_lag_seconds") is not None]

    return {
        "aggregate_id": aggregate_id,
        "window_start": window_start,
        "window_end": window_end,
        "event_date": event_date,
        "traffic_source": traffic_source,
        "browser": browser,
        "event_type": event_type,
        "page_type": page_type,
        "total_events": len(rows),
        "unique_sessions": len(session_ids),
        "unique_users": len(user_ids),
        "purchase_events": purchase_events,
        "avg_event_lag_seconds": (sum(lags) / len(lags)) if lags else None,
        "version_emitted_at": to_timestamp_string(now),
    }


def build_session_metric(element):
    session_id, rows = element
    rows_list = list(rows)
    if len(rows_list) > MAX_EVENTS_PER_SESSION:
        logging.warning(
            "Session %s has %d events, capping at %d",
            session_id,
            len(rows_list),
            MAX_EVENTS_PER_SESSION,
        )
        rows_list = rows_list[:MAX_EVENTS_PER_SESSION]

    rows = sorted(rows_list, key=lambda row: row["event_timestamp"])
    if not rows:
        return None

    now = utc_now()
    start_ts = parse_iso8601(rows[0]["event_timestamp"])
    end_ts = parse_iso8601(rows[-1]["event_timestamp"])
    category_counts = {}
    for row in rows:
        category = row.get("product_category")
        if category:
            category_counts[category] = category_counts.get(category, 0) + 1

    top_category = max(category_counts, key=category_counts.get) if category_counts else None
    cart_count = sum(1 for row in rows if row.get("event_type") == "cart")
    purchase_count = sum(1 for row in rows if row.get("event_type") == "purchase")

    return {
        "session_record_id": session_id,
        "session_id": session_id,
        "user_id": rows[0].get("user_id"),
        "traffic_source": rows[0].get("traffic_source"),
        "browser": rows[0].get("browser"),
        "session_start": to_timestamp_string(start_ts),
        "session_end": to_timestamp_string(end_ts),
        "session_duration_seconds": max(0.0, (end_ts - start_ts).total_seconds()),
        "event_count": len(rows),
        "pageview_count": sum(1 for row in rows if row.get("page_type") in PAGEVIEW_TYPES),
        "product_view_count": sum(1 for row in rows if row.get("page_type") == "product"),
        "cart_count": cart_count,
        "purchase_count": purchase_count,
        "saw_home": any(row.get("page_type") == "home" for row in rows),
        "saw_product": any(row.get("page_type") == "product" for row in rows),
        "added_to_cart": cart_count > 0,
        "purchased": purchase_count > 0,
        "top_category": top_category,
        "session_date": start_ts.date().isoformat(),
        "version_emitted_at": to_timestamp_string(now),
        "processed_at": to_timestamp_string(now),
    }
