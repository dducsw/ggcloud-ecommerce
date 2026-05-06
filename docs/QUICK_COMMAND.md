0. Chuẩn Bị

cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce

$env:GCP_PROJECT_ID="cloud-data-project-492514"
$env:BQ_LOCATION="asia-southeast1"
$env:GCS_BUCKET_NAME="etl-staging-0"
$env:BRONZE_DATASET_ID="thelook_staging"
$env:GOLD_DATASET_ID="thelook_datawarehouse"
$env:GOOGLE_APPLICATION_CREDENTIALS=(Resolve-Path .\credentials\gcp-key.json).Path
gcloud auth application-default login
gcloud config set project cloud-data-project-492514

1. Cài Dependencies

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r datagen/thelook-ecomm/requirements.txt

2. Tạo Pub/Sub

python src/streaming/setup_pubsub.py --project-id cloud-data-project-492514

3. Start Postgres + Debezium

docker compose up -d postgres-source debezium-server
docker compose ps
docker logs --tail=100 debezium-server

4. Start Datagen

Vì bạn vừa sửa datagen, cần build lại image:

docker compose --profile manual up -d --build datagen
docker logs -f ggcloud_datagen
Mở terminal khác để chạy tiếp các bước dưới.

5. Setup BigQuery Dataset

.\infra\bigquery\setup_bigquery.ps1 `
  -ProjectId "cloud-data-project-492514" `
  -Location "asia-southeast1" `
  -BronzeDataset "thelook_staging" `
  -GoldDataset "thelook_datawarehouse" `
  -RawBucketPrefix "gs://etl-staging-0/raw"

6. Chạy Dataflow Router

Mở terminal riêng, giữ terminal này chạy:

cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce
.\.venv\Scripts\Activate.ps1
.\run_local_dataflow.ps1
Chờ 5-7 phút để cold path flush Parquet ra GCS.

7. Kiểm Tra BigQuery/GCS

Hot path events:

bq --project_id=cloud-data-project-492514 query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `cloud-data-project-492514.thelook_staging.events`'
Cold path GCS:

gcloud storage ls gs://etl-staging-0/raw/ --recursive
8. Tạo Lại External Tables Sau Khi Có Parquet

.\infra\bigquery\setup_bigquery.ps1 `
  -ProjectId "cloud-data-project-492514" `
  -Location "asia-southeast1" `
  -BronzeDataset "thelook_staging" `
  -GoldDataset "thelook_datawarehouse" `
  -RawBucketPrefix "gs://etl-staging-0/raw"

9. Chạy dbt

cd dbt\thelook_dwh

Remove-Item -Recurse -Force .\dbt_packages -ErrorAction SilentlyContinue

dbt debug --profiles-dir .
dbt source freshness --profiles-dir .
dbt build --profiles-dir .

cd ..\..

10. Chạy Dashboard

streamlit run src/dashboard/app.py
Mở URL Streamlit, thường là:

http://localhost:8501
Có Cần Clickstream Riêng Không?

Không bắt buộc cho pipeline chính. Chỉ chạy thêm nếu cần các trang realtime/session analytics dùng dataset thelook_clickstream.

Luồng chính đã đủ cho:

Postgres -> Debezium -> Pub/Sub -> Beam -> GCS/BigQuery -> dbt -> Dashboard