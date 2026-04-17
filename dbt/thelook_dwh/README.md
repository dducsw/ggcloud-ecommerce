# dbt BigQuery Configuration (GCS -> BigQuery)

This dbt project assumes:

- `orders`, `events`: streaming tables in BigQuery bronze.
- `users`, `products`, `dist_centers`, `inventory_items`, `order_items`: external parquet tables in BigQuery bronze, backed by GCS.

## 1) Prepare BigQuery bronze/gold + external tables

Run one of:

```powershell
.\infra\bigquery\setup_bigquery.ps1 -ProjectId "<YOUR_GCP_PROJECT>" -Location "asia-southeast1" -RawBucketPrefix "gs://<YOUR_BUCKET>/raw"
```

```bash
PROJECT_ID=<YOUR_GCP_PROJECT> LOCATION=asia-southeast1 RAW_BUCKET_PREFIX=gs://<YOUR_BUCKET>/raw ./infra/bigquery/setup_bigquery.sh
```

## 2) Set dbt environment variables

```powershell
$env:GCP_PROJECT_ID="<YOUR_GCP_PROJECT>"
$env:BRONZE_DATASET_ID="thelook_bronze"
$env:GOLD_DATASET_ID="thelook_gold"
$env:BQ_LOCATION="asia-southeast1"
$env:GOOGLE_APPLICATION_CREDENTIALS="<ABSOLUTE_PATH_TO_SERVICE_ACCOUNT_JSON>"
```

## 3) Validate and run

```powershell
cd dbt/thelook_dwh
dbt debug --profiles-dir .
dbt source freshness --profiles-dir .
dbt build --profiles-dir .
```

## Notes

- Source `distribution_centers` is mapped to physical table `dist_centers`.
- `loaded_at_field` for source freshness is `cdc_timestamp`.
