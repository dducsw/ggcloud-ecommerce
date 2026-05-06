import argparse
import json
import logging
from datetime import datetime

import apache_beam as beam
from apache_beam.io.filesystems import FileSystems
from apache_beam.io.gcp.bigquery import WriteToBigQuery
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.options.pipeline_options import SetupOptions
from apache_beam.options.pipeline_options import StandardOptions
from apache_beam.transforms.window import FixedWindows
import pyarrow as pa
import pyarrow.parquet as pq


HOT_TABLES = {"events"}


def normalize_table_name(table_name: str) -> str:
    if table_name == "distribution_centers":
        return "dist_centers"
    return table_name


def parse_cdc_message(raw_message: bytes) -> dict:
    body = json.loads(raw_message.decode("utf-8"))

    if "value_json" in body and body.get("value_json"):
        cdc_envelope = json.loads(body["value_json"])
        payload = cdc_envelope.get("payload", cdc_envelope)
    else:
        payload = body.get("payload", body)

    source = payload.get("source", {})
    table_name = source.get("table") or body.get("table") or "unknown"
    schema_name = source.get("schema") or body.get("schema")

    after_state = payload.get("after")
    before_state = payload.get("before")
    operation = payload.get("op")
    cdc_timestamp = payload.get("ts_ms") or source.get("ts_ms")

    logging.info(f"Routing CDC message: table={normalize_table_name(table_name)}, op={operation}")

    return {
        "table": normalize_table_name(table_name),
        "schema": schema_name,
        "op": operation,
        "cdc_timestamp": cdc_timestamp,
        "after": after_state,
        "before": before_state,
        "payload": payload,
    }


def to_bq_row(record: dict) -> dict:
    row_payload = dict(record.get("after") or record.get("before") or {})
    row_payload["cdc_timestamp"] = record.get("cdc_timestamp")
    row_payload["cdc_operation"] = record.get("op")

    for key in list(row_payload.keys()):
        if key.endswith("_at") and isinstance(row_payload[key], int):
            row_payload[key] = datetime.fromtimestamp(row_payload[key] / 1000000.0, getattr(datetime, "UTC", None) or __import__("datetime").timezone.utc).isoformat()

    return row_payload






FLUSH_INTERVAL_SECONDS = 60  # flush Parquet ra GCS mỗi N giây


# Target timestamp type for all '_at' columns — must match BQ External Table schema (TIMESTAMP).
_TS_TYPE = pa.timestamp("us", tz="UTC")
_UTC = __import__("datetime").timezone.utc


def _epoch_micros_to_datetime(val):
    """Convert Debezium epoch-microseconds integer to a UTC-aware datetime.
    Returns None for null/invalid values.
    """
    if val is None:
        return None
    try:
        iv = int(val)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(iv / 1_000_000.0, _UTC)


def _normalize_row_timestamps(row: dict) -> dict:
    """Pre-process a CDC row dict: convert integer _at epoch-micros to Python datetime
    so that PyArrow infers timestamp[us] rather than int64, matching the BQ External Table.
    Also converts ISO-string timestamps to datetime (fallback for CDC rows already stringified).
    """
    out = {}
    for k, v in row.items():
        if k.endswith("_at"):
            if isinstance(v, int):
                out[k] = _epoch_micros_to_datetime(v)
            elif isinstance(v, str) and v not in ("", "null"):
                # ISO string (e.g. from to_bq_row path) → parse to datetime
                try:
                    import dateutil.parser as _dp
                    out[k] = _dp.parse(v).replace(tzinfo=_UTC) if _dp.parse(v).tzinfo is None else _dp.parse(v)
                except Exception:
                    out[k] = None
            else:
                out[k] = None
        else:
            out[k] = v
    return out


def _cast_arrow_schema(arrow_table):
    """Normalize column types for a Parquet file written to GCS so that BigQuery
    External Table (schema=TIMESTAMP for _at cols, INTEGER for id cols, STRING for rest)
    can read all files uniformly.

    Rules:
    - Columns ending with '_at' → timestamp[us, tz=UTC]  (BQ TIMESTAMP)
    - Integer columns           → int64                  (BQ INTEGER)
    - Pure-null columns         → string (safe fallback, except _at → timestamp)
    - Everything else           → keep as-is
    """
    TIMESTAMP_SUFFIXES = ("_at",)

    new_fields = []
    for field in arrow_table.schema:
        is_ts_col = any(field.name.endswith(sfx) for sfx in TIMESTAMP_SUFFIXES)

        if is_ts_col:
            # Always target timestamp regardless of current inferred type
            new_fields.append(pa.field(field.name, _TS_TYPE))
        elif pa.types.is_null(field.type):
            new_fields.append(pa.field(field.name, pa.string()))
        elif pa.types.is_integer(field.type):
            new_fields.append(pa.field(field.name, pa.int64()))
        else:
            new_fields.append(field)

    new_schema = pa.schema(new_fields)

    arrays = []
    for i, field in enumerate(new_schema):
        old_field = arrow_table.schema.field(i)
        col = arrow_table.column(i)
        is_ts_target = pa.types.is_timestamp(field.type)

        if pa.types.is_null(old_field.type):
            # All-null batch column: emit typed null array
            arrays.append(pa.array([None] * len(col), type=field.type))
        elif is_ts_target and not pa.types.is_timestamp(old_field.type):
            # Need to convert non-timestamp source to timestamp.
            # After _normalize_row_timestamps this should rarely happen,
            # but handle int64 (epoch μs) just in case.
            if pa.types.is_integer(old_field.type):
                # int64 epoch-micros → cast directly to timestamp[us, UTC]
                arrays.append(col.cast(_TS_TYPE))
            elif pa.types.is_string(old_field.type) or pa.types.is_large_string(old_field.type):
                # Parse string values to datetime
                def _parse_ts(v):
                    if v is None or v == "" or v == "null":
                        return None
                    try:
                        import dateutil.parser as _dp
                        dt = _dp.parse(v)
                        return dt.replace(tzinfo=_UTC) if dt.tzinfo is None else dt
                    except Exception:
                        return None
                arrays.append(pa.array([_parse_ts(v.as_py()) for v in col], type=_TS_TYPE))
            else:
                arrays.append(col.cast(field.type, safe=False))
        else:
            try:
                arrays.append(col.cast(field.type, safe=False))
            except Exception:
                arrays.append(col)

    return pa.table({field.name: arrays[i] for i, field in enumerate(new_schema)})


def _flush_to_gcs(table_name, rows, output_prefix):
    """Write a list of row dicts to a Parquet file on GCS."""
    import time as _time
    all_columns = sorted({k for row in rows for k in row.keys()})
    # Pre-convert _at int epoch-micros to Python datetime BEFORE Arrow inference
    # so that PyArrow picks timestamp[us] (matching BQ External Table schema).
    normalized = [
        _normalize_row_timestamps({col: row.get(col) for col in all_columns})
        for row in rows
    ]
    arrow_table = _cast_arrow_schema(pa.Table.from_pylist(normalized))

    now = datetime.fromtimestamp(
        _time.time(),
        getattr(datetime, "UTC", None) or __import__("datetime").timezone.utc,
    )
    ts = now.strftime("%Y%m%d%H%M%S%f")[:18]
    output_path = (
        f"{output_prefix.rstrip('/')}/{table_name}/"
        f"date={now.strftime('%Y-%m-%d')}/hour={now.strftime('%H')}/cdc-{ts}.parquet"
    )
    with FileSystems.create(output_path) as fh:
        pq.write_table(arrow_table, fh, coerce_timestamps="us", allow_truncated_timestamps=True)
    logging.info(f"[cold-path] Flushed {len(rows)} rows for '{table_name}' → {output_path}")
    return output_path




class _WriteBatchedParquetDoFn(beam.DoFn):
    """Receives (table_name, [records]) from GroupByKey and writes Parquet to GCS."""

    def __init__(self, output_prefix: str):
        self.output_prefix = output_prefix

    def process(self, element, window=beam.DoFn.WindowParam):
        table_name, records_iter = element
        rows = []
        for record in records_iter:
            row = dict(record.get("after") or record.get("before") or {})
            row["cdc_timestamp"] = record.get("cdc_timestamp")
            row["cdc_operation"] = record.get("op")
            rows.append(row)

        if not rows:
            return

        _flush_to_gcs(table_name, rows, self.output_prefix)
        yield {"table": table_name, "row_count": len(rows)}


def run(argv=None):
    logging.getLogger().setLevel(logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="asia-southeast1")
    parser.add_argument("--runner", default="DataflowRunner")
    parser.add_argument("--temp_location", required=True)
    parser.add_argument("--staging_location", required=True)
    parser.add_argument("--pubsub_subscription", required=True)
    parser.add_argument("--events_subscription", required=True, help="Subscription for the clickstream events topic")
    parser.add_argument("--bronze_dataset", default="thelook_staging")
    parser.add_argument("--gcs_output_prefix", default="gs://my-thelook-datalake/raw")

    known_args, pipeline_args = parser.parse_known_args(argv)

    pipeline_options = PipelineOptions(
        pipeline_args,
        project=known_args.project,
        region=known_args.region,
        runner=known_args.runner,
        temp_location=known_args.temp_location,
        staging_location=known_args.staging_location,
        streaming=True,
    )
    pipeline_options.view_as(StandardOptions).streaming = True
    pipeline_options.view_as(SetupOptions).save_main_session = True

    with beam.Pipeline(options=pipeline_options) as pipeline:
        parsed_main = (
            pipeline
            | "ReadMainPubSub" >> beam.io.ReadFromPubSub(subscription=known_args.pubsub_subscription)
            | "ParseMainJSON" >> beam.Map(parse_cdc_message)
        )

        parsed_events = (
            pipeline
            | "ReadEventsPubSub" >> beam.io.ReadFromPubSub(subscription=known_args.events_subscription)
            | "ParseEventsJSON" >> beam.Map(parse_cdc_message)
        )

        # Hot path: events topic → BigQuery Streaming Inserts
        # Cold path: all main CDC tables (users/products/dist_centers/inventory_items/orders/order_items) → GCS Parquet
        hot_records = parsed_events
        cold_records = parsed_main

        # Schema inline cho events — BQ streaming insert cần schema khi CREATE_IF_NEEDED
        events_bq_schema = {
            "fields": [
                {"name": "id",             "type": "INTEGER", "mode": "NULLABLE"},
                {"name": "user_id",        "type": "INTEGER", "mode": "NULLABLE"},
                {"name": "sequence_number","type": "INTEGER", "mode": "NULLABLE"},
                {"name": "session_id",     "type": "STRING",  "mode": "NULLABLE"},
                {"name": "created_at",     "type": "TIMESTAMP","mode": "NULLABLE"},
                {"name": "ip_address",     "type": "STRING",  "mode": "NULLABLE"},
                {"name": "city",           "type": "STRING",  "mode": "NULLABLE"},
                {"name": "state",          "type": "STRING",  "mode": "NULLABLE"},
                {"name": "postal_code",    "type": "STRING",  "mode": "NULLABLE"},
                {"name": "browser",        "type": "STRING",  "mode": "NULLABLE"},
                {"name": "traffic_source", "type": "STRING",  "mode": "NULLABLE"},
                {"name": "uri",            "type": "STRING",  "mode": "NULLABLE"},
                {"name": "event_type",     "type": "STRING",  "mode": "NULLABLE"},
                {"name": "cdc_timestamp",  "type": "INTEGER", "mode": "NULLABLE"},
                {"name": "cdc_operation",  "type": "STRING",  "mode": "NULLABLE"},
            ]
        }

        table_schemas = {"events": events_bq_schema}

        for table_name in HOT_TABLES:
            (
                hot_records
                | f"Only_{table_name}" >> beam.Filter(lambda r, t=table_name: r.get("table") == t)
                | f"{table_name}_to_bq_row" >> beam.Map(to_bq_row)
                | f"Write_{table_name}_BQ"
                >> WriteToBigQuery(
                    table=f"{known_args.project}:{known_args.bronze_dataset}.{table_name}",
                    schema=table_schemas.get(table_name),
                    write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                    create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                    method=WriteToBigQuery.Method.STREAMING_INSERTS,
                )
            )



        _ = (
            cold_records
            | "WindowCold" >> beam.WindowInto(
                FixedWindows(60),
                trigger=beam.transforms.trigger.AfterProcessingTime(60),
                accumulation_mode=beam.transforms.trigger.AccumulationMode.DISCARDING,
                allowed_lateness=0,
            )
            | "KeyByTable" >> beam.Map(lambda r: (r.get("table", "unknown"), r))
            | "GroupByTable" >> beam.GroupByKey()
            | "WriteColdParquet" >> beam.ParDo(
                _WriteBatchedParquetDoFn(known_args.gcs_output_prefix)
            )
        )


if __name__ == "__main__":
    run()
