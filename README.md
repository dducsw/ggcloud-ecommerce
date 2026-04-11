# TheLook Smart Router Lakehouse (GCP)

This repo now follows one pipeline only:

1. Source: PostgreSQL + datagen
2. CDC: Debezium -> Kafka (local), then Kafka -> Pub/Sub bridge
3. Router: Apache Beam/Dataflow routes by source table
4. Hot path: events/orders -> BigQuery bronze (streaming inserts)
5. Cold path: users/products/dist_centers -> Parquet on GCS
6. Transform: dbt models from bronze to gold
7. Serve: Streamlit dashboard on BigQuery

## Active Entrypoints

- Compose: docker-compose.yaml
- Debezium connector registration: src/cdc/register_debezium_connector.py
- Step 1 local helper (Windows): infra/cdc/run_step1_local.ps1
- Pub/Sub setup: src/streaming/setup_pubsub.py
- Kafka -> Pub/Sub bridge: src/streaming/kafka_to_pubsub_bridge.py
- Smart Router pipeline: src/dataflow/beam_router.py
- BigQuery setup (bash): infra/bigquery/setup_bigquery.sh
- BigQuery setup (PowerShell): infra/bigquery/setup_bigquery.ps1
- dbt project: dbt/thelook_dwh
- Dashboard: src/dashboard/app.py

## Step 1: Source + CDC (Local)

Run on Windows PowerShell:

```powershell
.\infra\cdc\run_step1_local.ps1
```

This starts:

- postgres-source (PostgreSQL 15, logical WAL)
- kafka
- debezium-cdc
- datagen

And auto-registers connector from:

- infra/cdc/connectors/debezium-connector.json

## Step 3: BigQuery Storage Setup

Run on Windows PowerShell:

```powershell
.\infra\bigquery\setup_bigquery.ps1 -ProjectId "<YOUR_GCP_PROJECT>" -Location "asia-southeast1" -RawBucketPrefix "gs://my-thelook-datalake/raw"
```

Or bash:

```bash
PROJECT_ID=<YOUR_GCP_PROJECT> LOCATION=asia-southeast1 RAW_BUCKET_PREFIX=gs://my-thelook-datalake/raw ./infra/bigquery/setup_bigquery.sh
```

This creates:

- dataset thelook_bronze
- dataset thelook_gold
- external tables in thelook_bronze: users, products, dist_centers

## Run Router + dbt + Dashboard

Create Pub/Sub resources:

```bash
python src/streaming/setup_pubsub.py --project-id <YOUR_GCP_PROJECT> --topic thelook-cdc-events --subscription thelook-cdc-events-sub
```

Start bridge:

```bash
python src/streaming/kafka_to_pubsub_bridge.py --project-id <YOUR_GCP_PROJECT> --pubsub-topic thelook-cdc-events
```

Run Beam router:

```bash
python src/dataflow/beam_router.py --project <YOUR_GCP_PROJECT> --runner DirectRunner --temp_location gs://<YOUR_BUCKET>/tmp --staging_location gs://<YOUR_BUCKET>/staging --pubsub_subscription projects/<YOUR_GCP_PROJECT>/subscriptions/thelook-cdc-events-sub --bronze_dataset thelook_bronze --gcs_output_prefix gs://my-thelook-datalake/raw
```

Run dbt:

```bash
cd dbt/thelook_dwh
dbt build --profiles-dir .
```

Run dashboard:

```bash
streamlit run src/dashboard/app.py
```
