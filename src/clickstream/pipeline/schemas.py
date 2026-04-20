RAW_EVENTS_SCHEMA = {
    "fields": [
        {"name": "event_id", "type": "INT64", "mode": "REQUIRED"},
        {"name": "user_id", "type": "INT64", "mode": "NULLABLE"},
        {"name": "sequence_number", "type": "INT64", "mode": "NULLABLE"},
        {"name": "session_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "ip_address", "type": "STRING", "mode": "NULLABLE"},
        {"name": "city", "type": "STRING", "mode": "NULLABLE"},
        {"name": "state", "type": "STRING", "mode": "NULLABLE"},
        {"name": "postal_code", "type": "STRING", "mode": "NULLABLE"},
        {"name": "browser", "type": "STRING", "mode": "NULLABLE"},
        {"name": "traffic_source", "type": "STRING", "mode": "NULLABLE"},
        {"name": "uri", "type": "STRING", "mode": "NULLABLE"},
        {"name": "event_type", "type": "STRING", "mode": "NULLABLE"},
        {"name": "event_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "event_date", "type": "DATE", "mode": "REQUIRED"},
        {"name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "page_type", "type": "STRING", "mode": "NULLABLE"},
        {"name": "product_id", "type": "INT64", "mode": "NULLABLE"},
        {"name": "product_category", "type": "STRING", "mode": "NULLABLE"},
        {"name": "product_department", "type": "STRING", "mode": "NULLABLE"},
        {"name": "product_name", "type": "STRING", "mode": "NULLABLE"},
        {"name": "is_conversion", "type": "BOOL", "mode": "REQUIRED"},
        {"name": "processing_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "event_lag_seconds", "type": "FLOAT64", "mode": "NULLABLE"},
    ]
}

DEADLETTER_SCHEMA = {
    "fields": [
        {"name": "raw_message", "type": "STRING", "mode": "NULLABLE"},
        {"name": "error_message", "type": "STRING", "mode": "REQUIRED"},
        {"name": "failed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}

AGGREGATE_SCHEMA = {
    "fields": [
        {"name": "aggregate_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "window_start", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "window_end", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "event_date", "type": "DATE", "mode": "REQUIRED"},
        {"name": "traffic_source", "type": "STRING", "mode": "NULLABLE"},
        {"name": "browser", "type": "STRING", "mode": "NULLABLE"},
        {"name": "event_type", "type": "STRING", "mode": "NULLABLE"},
        {"name": "page_type", "type": "STRING", "mode": "NULLABLE"},
        {"name": "total_events", "type": "INT64", "mode": "REQUIRED"},
        {"name": "unique_sessions", "type": "INT64", "mode": "REQUIRED"},
        {"name": "unique_users", "type": "INT64", "mode": "REQUIRED"},
        {"name": "purchase_events", "type": "INT64", "mode": "REQUIRED"},
        {"name": "avg_event_lag_seconds", "type": "FLOAT64", "mode": "NULLABLE"},
        {"name": "version_emitted_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}

SESSION_SCHEMA = {
    "fields": [
        {"name": "session_record_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "session_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "user_id", "type": "INT64", "mode": "NULLABLE"},
        {"name": "traffic_source", "type": "STRING", "mode": "NULLABLE"},
        {"name": "browser", "type": "STRING", "mode": "NULLABLE"},
        {"name": "session_start", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "session_end", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "session_duration_seconds", "type": "FLOAT64", "mode": "REQUIRED"},
        {"name": "event_count", "type": "INT64", "mode": "REQUIRED"},
        {"name": "pageview_count", "type": "INT64", "mode": "REQUIRED"},
        {"name": "product_view_count", "type": "INT64", "mode": "REQUIRED"},
        {"name": "cart_count", "type": "INT64", "mode": "REQUIRED"},
        {"name": "purchase_count", "type": "INT64", "mode": "REQUIRED"},
        {"name": "saw_home", "type": "BOOL", "mode": "REQUIRED"},
        {"name": "saw_product", "type": "BOOL", "mode": "REQUIRED"},
        {"name": "added_to_cart", "type": "BOOL", "mode": "REQUIRED"},
        {"name": "purchased", "type": "BOOL", "mode": "REQUIRED"},
        {"name": "top_category", "type": "STRING", "mode": "NULLABLE"},
        {"name": "session_date", "type": "DATE", "mode": "REQUIRED"},
        {"name": "version_emitted_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}
