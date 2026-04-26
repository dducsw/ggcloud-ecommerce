import argparse
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv
from google.cloud import storage
from sqlalchemy import create_engine, text


load_dotenv()


@dataclass(frozen=True)
class ExportTable:
    source_name: str
    gcs_name: str
    query_template: str


EXPORT_TABLES: list[ExportTable] = [
    ExportTable(
        source_name="users",
        gcs_name="users",
        query_template="""
            select
                id,
                first_name,
                last_name,
                email,
                age,
                gender,
                street_address,
                postal_code,
                city,
                state,
                country,
                latitude,
                longitude,
                traffic_source,
                created_at,
                updated_at
            from {schema}.users
        """,
    ),
    ExportTable(
        source_name="products",
        gcs_name="products",
        query_template="""
            select
                id,
                cost,
                category,
                name,
                brand,
                retail_price,
                department,
                sku,
                distribution_center_id,
                :cdc_timestamp as cdc_timestamp
            from {schema}.products
        """,
    ),
    ExportTable(
        source_name="distribution_centers",
        gcs_name="dist_centers",
        query_template="""
            select
                id,
                name,
                latitude,
                longitude
            from {schema}.distribution_centers
        """,
    ),
    ExportTable(
        source_name="inventory_items",
        gcs_name="inventory_items",
        query_template="""
            select
                id,
                product_id,
                created_at,
                sold_at,
                cost,
                product_category,
                product_name,
                product_brand,
                product_retail_price,
                product_department,
                product_sku,
                product_distribution_center_id
            from {schema}.inventory_items
        """,
    ),
    ExportTable(
        source_name="order_items",
        gcs_name="order_items",
        query_template="""
            select
                id,
                order_id,
                user_id,
                product_id,
                inventory_item_id,
                status,
                created_at,
                updated_at,
                returned_at,
                shipped_at,
                delivered_at,
                sale_price,
                :cdc_timestamp as cdc_timestamp,
                'r' as cdc_operation
            from {schema}.order_items
        """,
    ),
    ExportTable(
        source_name="orders",
        gcs_name="orders",
        query_template="""
            select
                order_id,
                user_id,
                status,
                gender,
                created_at,
                updated_at,
                returned_at,
                shipped_at,
                delivered_at,
                num_of_item,
                :cdc_timestamp as cdc_timestamp,
                'r' as cdc_operation
            from {schema}.orders
        """,
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full load local PostgreSQL tables to GCS for BigQuery external-table staging."
    )
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5433)
    parser.add_argument("--pg-database", default="thelook_db")
    parser.add_argument("--pg-user", default="db_user")
    parser.add_argument("--pg-password", default="db_password")
    parser.add_argument("--pg-schema", default="demo")
    parser.add_argument("--gcs-bucket", default="etl-staging-0")
    parser.add_argument("--gcs-prefix", default="raw")
    parser.add_argument("--chunk-size", type=int, default=50000)
    parser.add_argument(
        "--tables",
        nargs="*",
        default=[table.source_name for table in EXPORT_TABLES],
        help="Subset of source tables to export. Defaults to all full-load tables.",
    )
    return parser.parse_args()


def build_engine(args: argparse.Namespace):
    return create_engine(
        "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}".format(
            user=args.pg_user,
            password=args.pg_password,
            host=args.pg_host,
            port=args.pg_port,
            database=args.pg_database,
        )
    )


def resolve_tables(selected_table_names: Iterable[str]) -> list[ExportTable]:
    selected = set(selected_table_names)
    resolved = [table for table in EXPORT_TABLES if table.source_name in selected]
    missing = sorted(selected - {table.source_name for table in EXPORT_TABLES})
    if missing:
        raise ValueError(f"Unsupported table names: {', '.join(missing)}")
    return resolved


def delete_existing_prefix(bucket: storage.Bucket, prefix: str) -> None:
    blobs = list(bucket.list_blobs(prefix=prefix))
    if blobs:
        bucket.delete_blobs(blobs)


def export_table_to_parquet(
    engine,
    table: ExportTable,
    pg_schema: str,
    chunk_size: int,
    cdc_timestamp: int,
    output_path: Path,
) -> int:
    row_count = 0
    parquet_writer = None
    query = text(table.query_template.format(schema=pg_schema))

    with engine.connect() as conn:
        chunk_iter = pd.read_sql_query(
            sql=query,
            con=conn,
            params={"cdc_timestamp": cdc_timestamp},
            chunksize=chunk_size,
        )

        for chunk in chunk_iter:
            if chunk.empty:
                continue

            arrow_table = pa.Table.from_pandas(chunk, preserve_index=False)
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(output_path, arrow_table.schema)
            parquet_writer.write_table(arrow_table)
            row_count += len(chunk)

    if parquet_writer is None:
        empty_table = pa.table({})
        pq.write_table(empty_table, output_path)
    else:
        parquet_writer.close()

    return row_count


def upload_to_gcs(
    client: storage.Client,
    bucket_name: str,
    gcs_prefix: str,
    table: ExportTable,
    local_file: Path,
    snapshot_time: datetime,
) -> str:
    bucket = client.bucket(bucket_name)
    table_root = f"{gcs_prefix.strip('/')}/{table.gcs_name}"
    delete_existing_prefix(bucket, f"{table_root}/")

    object_name = (
        f"{table_root}/"
        f"date={snapshot_time:%Y-%m-%d}/"
        f"hour={snapshot_time:%H}/"
        f"{table.gcs_name}_full_{snapshot_time:%Y%m%dT%H%M%SZ}.parquet"
    )
    blob = bucket.blob(object_name)
    blob.upload_from_filename(str(local_file), content_type="application/octet-stream")
    return f"gs://{bucket_name}/{object_name}"


def main() -> None:
    args = parse_args()
    snapshot_time = datetime.now(timezone.utc)
    cdc_timestamp = int(snapshot_time.timestamp() * 1000)

    engine = build_engine(args)
    storage_client = storage.Client()
    tables = resolve_tables(args.tables)

    try:
        for table in tables:
            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            try:
                row_count = export_table_to_parquet(
                    engine=engine,
                    table=table,
                    pg_schema=args.pg_schema,
                    chunk_size=args.chunk_size,
                    cdc_timestamp=cdc_timestamp,
                    output_path=tmp_path,
                )
                gcs_uri = upload_to_gcs(
                    client=storage_client,
                    bucket_name=args.gcs_bucket,
                    gcs_prefix=args.gcs_prefix,
                    table=table,
                    local_file=tmp_path,
                    snapshot_time=snapshot_time,
                )
                print(
                    f"Exported {row_count} rows from {args.pg_schema}.{table.source_name} to {gcs_uri}"
                )
            finally:
                tmp_path.unlink(missing_ok=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
