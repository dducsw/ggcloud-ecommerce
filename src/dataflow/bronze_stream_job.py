import argparse
import json
from datetime import datetime

import apache_beam as beam
from apache_beam.io import parquetio
from apache_beam.io.gcp.bigquery import WriteToBigQuery
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions, StandardOptions
import pyarrow as pa


def parse_pubsub_message(message: bytes):
    record = json.loads(message.decode("utf-8"))
    return {
        "ingested_at": record.get("ingested_at"),
        "topic": record.get("topic"),
        "partition": record.get("partition"),
        "offset": record.get("offset"),
        "key_json": record.get("key_json"),
        "value_json": record.get("value_json"),
    }


def to_parquet_row(record):
    # Keep raw payload for bronze replay/audit.
    return {
        "ingested_at": record.get("ingested_at") or datetime.utcnow().isoformat(),
        "topic": record.get("topic"),
        "partition": record.get("partition"),
        "offset": record.get("offset"),
        "key_json": record.get("key_json"),
        "value_json": record.get("value_json"),
    }


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="asia-southeast1")
    parser.add_argument("--runner", default="DirectRunner")
    parser.add_argument("--temp_location", required=False)
    parser.add_argument("--staging_location", required=False)
    parser.add_argument("--pubsub_subscription", required=True)
    parser.add_argument("--bronze_table", required=True, help="project:dataset.table")
    parser.add_argument("--gcs_bronze_prefix", required=True, help="gs://bucket/path/prefix")

    known_args, pipeline_args = parser.parse_known_args(argv)

    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(SetupOptions).save_main_session = True
    pipeline_options.view_as(StandardOptions).runner = known_args.runner

    bq_schema = {
        "fields": [
            {"name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
            {"name": "topic", "type": "STRING", "mode": "REQUIRED"},
            {"name": "partition", "type": "INTEGER", "mode": "NULLABLE"},
            {"name": "offset", "type": "INTEGER", "mode": "NULLABLE"},
            {"name": "key_json", "type": "STRING", "mode": "NULLABLE"},
            {"name": "value_json", "type": "STRING", "mode": "NULLABLE"},
        ]
    }

    parquet_schema = pa.schema(
        [
            ("ingested_at", pa.string()),
            ("topic", pa.string()),
            ("partition", pa.int64()),
            ("offset", pa.int64()),
            ("key_json", pa.string()),
            ("value_json", pa.string()),
        ]
    )

    with beam.Pipeline(options=pipeline_options) as p:
        rows = (
            p
            | "ReadPubSub" >> beam.io.ReadFromPubSub(subscription=known_args.pubsub_subscription)
            | "ParseJSON" >> beam.Map(parse_pubsub_message)
        )

        _ = (
            rows
            | "WriteBronzeBQ"
            >> WriteToBigQuery(
                known_args.bronze_table,
                schema=bq_schema,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                method=WriteToBigQuery.Method.STREAMING_INSERTS,
            )
        )

        _ = (
            rows
            | "ToParquetRow" >> beam.Map(to_parquet_row)
            | "WriteBronzeParquet"
            >> parquetio.WriteToParquet(
                file_path_prefix=known_args.gcs_bronze_prefix,
                schema=parquet_schema,
                file_name_suffix=".parquet",
                num_shards=1,
            )
        )


if __name__ == "__main__":
    run()
