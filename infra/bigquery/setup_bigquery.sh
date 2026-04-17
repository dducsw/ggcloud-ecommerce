#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-}"
LOCATION="${LOCATION:-US}"
BRONZE_DATASET="${BRONZE_DATASET:-thelook_staging}"
GOLD_DATASET="${GOLD_DATASET:-thelook_datawarehouse}"
RAW_BUCKET_PREFIX="${RAW_BUCKET_PREFIX:-gs://my-thelook-datalake/raw}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is required. Example: PROJECT_ID=my-project ./infra/bigquery/setup_bigquery.sh"
  exit 1
fi

create_dataset_if_missing() {
  local dataset_name="$1"
  if bq --project_id="${PROJECT_ID}" ls --dataset_id "${PROJECT_ID}:${dataset_name}" >/dev/null 2>&1; then
    echo "Dataset already exists: ${PROJECT_ID}:${dataset_name}"
  else
    bq --location="${LOCATION}" --project_id="${PROJECT_ID}" mk --dataset "${PROJECT_ID}:${dataset_name}"
    echo "Created dataset: ${PROJECT_ID}:${dataset_name}"
  fi
}

create_external_table() {
  local table_name="$1"
  # ** glob bao cover tat ca subdirectory (date=.../hour=...)
  local source_uri="${RAW_BUCKET_PREFIX}/${table_name}/**"
  local hive_prefix="${RAW_BUCKET_PREFIX}/${table_name}/"

  if bq --project_id="${PROJECT_ID}" show "${PROJECT_ID}:${BRONZE_DATASET}.${table_name}" >/dev/null 2>&1; then
    bq --project_id="${PROJECT_ID}" rm -f -t "${PROJECT_ID}:${BRONZE_DATASET}.${table_name}"
    echo "Recreating external table: ${PROJECT_ID}:${BRONZE_DATASET}.${table_name}"
  fi

  bq --project_id="${PROJECT_ID}" mk \
    --table \
    --external_table_definition="AUTODETECT=TRUE,source_format=PARQUET,hive_partitioning_mode=AUTO,hive_partitioning_source_uri_prefix=${hive_prefix},uris=${source_uri}" \
    "${PROJECT_ID}:${BRONZE_DATASET}.${table_name}"

  echo "Created/updated external table: ${PROJECT_ID}:${BRONZE_DATASET}.${table_name} -> ${source_uri}"
}

create_dataset_if_missing "${BRONZE_DATASET}"
create_dataset_if_missing "${GOLD_DATASET}"

EXTERNAL_TABLES=(
  "users"
  "products"
  "dist_centers"
  "inventory_items"
  "order_items"
  "orders"
)

for table in "${EXTERNAL_TABLES[@]}"; do
  create_external_table "${table}"
done

echo "BigQuery environment setup complete."
