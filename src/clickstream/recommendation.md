# Clickstream Recommendations

## Current Direction

- Product lookup is intentionally snapshot-based: the product dimension is loaded once when the Dataflow job starts.
- Restart the Dataflow job when product metadata changes and clickstream enrichment needs the new snapshot.
- Downstream analytics should use the latest/dedup views instead of reading append-only tables directly.

## Recommended Improvements

- Keep `v_events_raw_dedup`, `v_events_5m_latest`, and `v_session_metrics_latest` as the serving layer for dashboards to avoid double counting.
- Monitor dead-letter volume and duplicate-event counters so data quality issues are visible early.
- Tune `dedup_ttl_minutes`, `allowed_lateness_seconds`, and `session_gap_minutes` based on observed Pub/Sub redelivery and late-arrival behavior.
- Consider guarding session aggregation against extremely large bot-like sessions if event volume grows.
