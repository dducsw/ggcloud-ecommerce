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





class WriteColdParquetDoFn(beam.DoFn):
    def __init__(self, output_prefix: str):
        self.output_prefix = output_prefix.rstrip("/")

    def process(self, element, window=beam.DoFn.WindowParam):
        table_name, records_iter = element
        records = list(records_iter)

        if not records:
            return

        flattened_rows = []
        for record in records:
            row_payload = dict(record.get("after") or record.get("before") or {})
            row_payload["cdc_timestamp"] = record.get("cdc_timestamp")
            row_payload["cdc_operation"] = record.get("op")
            flattened_rows.append(row_payload)

        all_columns = sorted({k for row in flattened_rows for k in row.keys()})
        normalized_rows = []
        for row in flattened_rows:
            normalized_rows.append({column: row.get(column) for column in all_columns})

        arrow_table = pa.Table.from_pylist(normalized_rows)
        # Using timezone-aware UTC datetime to fix Python DeprecationWarning
        window_end = datetime.fromtimestamp(window.end.to_utc_datetime().timestamp(), getattr(datetime, "UTC", None) or __import__("datetime").timezone.utc)
        processing_time = window_end.strftime("%Y%m%d%H%M%S")

        # Hive-style partitioning: date=YYYY-MM-DD/hour=HH
        # BQ External Table với hive_partitioning_mode=AUTO sẽ tự nhận partition key
        date_str = window_end.strftime("%Y-%m-%d")
        hour_str = window_end.strftime("%H")

        output_path = (
            f"{self.output_prefix}/{table_name}/"
            f"date={date_str}/hour={hour_str}/part-{processing_time}.parquet"
        )

        with FileSystems.create(output_path) as file_handle:
            pq.write_table(arrow_table, file_handle, coerce_timestamps='us', allow_truncated_timestamps=True)

        yield {
            "table": table_name,
            "row_count": len(normalized_rows),
            "path": output_path,
        }


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
            | "WindowCold5Min" >> beam.WindowInto(FixedWindows(300))
            | "KeyByTable" >> beam.Map(lambda record: (record.get("table", "unknown"), record))
            | "GroupByTable" >> beam.GroupByKey()
            | "WriteColdParquet" >> beam.ParDo(WriteColdParquetDoFn(known_args.gcs_output_prefix))
        )


if __name__ == "__main__":
    run()
