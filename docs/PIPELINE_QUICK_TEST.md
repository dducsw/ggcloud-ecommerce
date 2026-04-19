# Pipeline Quick Test (E2E)

Muc tieu: Kiem tra nhanh toan bo pipeline Source -> CDC -> Beam -> BigQuery -> dbt -> Dashboard.

## 1) Start local services

Chay:

```powershell
docker compose up -d
```

Kiem tra:

```powershell
docker compose ps
```

PASS khi cac service chinh dang Up: postgres-source, ggcloud_datagen, ggcloud_kafka, debezium-server.

## 2) Kiem tra Debezium server

Chay:

```powershell
docker logs -f debezium-server
```

PASS khi thay log ket noi thanh cong va co message CDC duoc publish lien tuc.

## 3) Setup BigQuery datasets + external tables

Chay:

```powershell
.\infra\bigquery\setup_bigquery.ps1 -ProjectId "cloud-data-project-492514" -Location "asia-southeast1" -BronzeDataset "thelook_staging" -GoldDataset "thelook_datawarehouse" -RawBucketPrefix "gs://etl-staging-0/raw"
```

PASS khi script bao da tao/cap nhat datasets va external tables.

## 4) Run Beam router

Chay:

```powershell
.\run_local_dataflow.ps1
```

PASS khi khong bi retry loi vo han, va co log routing CDC/events.

## 5) Check Hot path vao BigQuery staging.events

Chay:

```powershell
bq --project_id=cloud-data-project-492514 query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `cloud-data-project-492514.thelook_staging.events`'
```

PASS khi so dong tang theo thoi gian.

## 6) Check Cold path GCS -> BigQuery external table

Chay:

```powershell
bq --project_id=cloud-data-project-492514 query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `cloud-data-project-492514.thelook_staging.orders`'
bq --project_id=cloud-data-project-492514 query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `cloud-data-project-492514.thelook_staging.users`'
```

PASS khi query chay duoc va count > 0 (co the can doi vai phut de flush partition).

## 7) Run dbt

Chay:

```powershell
cd dbt/thelook_dwh
dbt debug --profiles-dir .
dbt source freshness --profiles-dir .
dbt build --profiles-dir .
```

PASS khi dbt debug OK va dbt build hoan tat khong loi.

## 8) Check Gold layer

Chay:

```powershell
bq --project_id=cloud-data-project-492514 query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `cloud-data-project-492514.thelook_datawarehouse.fact_orders`'
bq --project_id=cloud-data-project-492514 query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `cloud-data-project-492514.thelook_datawarehouse.fact_events`'
```

PASS khi cac bang fact co du lieu.

## 9) Run dashboard smoke test

Chay:

```powershell
streamlit run src/dashboard/app.py
```

PASS khi dashboard mo duoc va hien thi metric tu BigQuery.

---

## Quick FAIL clues

- 403 Forbidden: Thieu IAM role hoac credentials het han.
- Not Found ... thelook_staging.orders: External table chua tao dung prefix GCS.
- dbt loi ket noi BigQuery: Kiem tra GCP_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS, execution_project trong profile.
