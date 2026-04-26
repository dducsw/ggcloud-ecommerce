# Walkthrough: Initial Data Load Script (Postgres -> GCS)

Mình đã viết xong Script Python để phục vụ cho luồng Pipeline mới của bạn.

## Các tính năng chính của Script
- Đọc trực tiếp từ **PostgreSQL** (`users`, `products`, `inventory_items`, `orders`, `order_items`, `distribution_centers`).
- Bổ sung **CDC Metadata** (`cdc_operation='c'`, `cdc_timestamp=<hiện_tại>`) để tương thích hoàn toàn với dbt.
- Chuyển thành định dạng **Parquet**.
- Tải lên **GCS** theo chuẩn **Hive Partitioning** (`date=YYYY-MM-DD/hour=HH/part-...`).
- Tự động bỏ qua bảng `events` vì `events` là Hot Path đi thẳng lên BigQuery.

## Vị trí file
[src/data_ingestion/initial_load_gcs.py](file:///d:/BK_Document/252/BTL_DWH_CLOUD/ggcloud-ecommerce/ggcloud-ecommerce/src/data_ingestion/initial_load_gcs.py)

## Cấu hình môi trường (Requirements)
Các thư viện cần thiết đã có sẵn trong file `requirements.txt` của bạn nên không cần cài thêm gì cả:
- `psycopg2-binary`, `pandas`, `pyarrow`, `google-cloud-storage`, `python-dotenv`.

## Hướng dẫn Vận Hành Chuẩn (Quy trình Test E2E mới)

> [!IMPORTANT]
> **Thứ tự các bước rất quan trọng.** Setup BigQuery phải chạy SAU khi đã có dữ liệu trên GCS, vì script cần `gsutil ls` để detect partition layout.

### Bước 1: Khởi động Postgres (DB sạch)

```powershell
# Nếu cần reset hoàn toàn (xoá volume cũ):
docker compose down -v

# Khởi động Postgres
docker compose up -d postgres-source
```

### Bước 2: Seed dữ liệu ban đầu bằng Datagen

Datagen sẽ tạo tables, insert users/products/distribution_centers/inventory, rồi tự dừng sau 1 iteration:

```powershell
docker compose --profile manual run --rm --build datagen python generator.py `
  --db-host postgres-source `
  --db-user db_user `
  --db-password db_password `
  --db-name thelook_db `
  --db-schema demo `
  --max-iter 1 `
  --avg-qps 1
```

> [!TIP]
> Chờ đến khi log hiện `Initialization successful` và `Application shutdown complete` là xong.

### Bước 3: Full Load từ Postgres lên GCS

```powershell
python src/data_ingestion/initial_load_gcs.py
```

Kết quả mong đợi — dữ liệu được upload lên:
```
gs://etl-staging-0/raw/users/date=.../hour=.../part-...-initial-load.parquet
gs://etl-staging-0/raw/products/date=.../hour=.../part-...-initial-load.parquet
gs://etl-staging-0/raw/dist_centers/date=.../hour=.../part-...-initial-load.parquet
gs://etl-staging-0/raw/inventory_items/date=.../hour=.../part-...-initial-load.parquet
gs://etl-staging-0/raw/orders/date=.../hour=.../part-...-initial-load.parquet
gs://etl-staging-0/raw/order_items/date=.../hour=.../part-...-initial-load.parquet
```

### Bước 4: Tạo External Tables trên BigQuery

**Phải chạy SAU Bước 3** vì script dùng `gsutil ls` để detect partitions:

```powershell
infra/bigquery/setup_bigquery.ps1 `
  -ProjectId "cloud-data-project-492514" `
  -Location "asia-southeast1" `
  -RawBucketPrefix "gs://etl-staging-0/raw"
```

### Bước 5: Kích hoạt CDC Streaming (Delta Load)

```powershell
.\run_local_dataflow.ps1
```

Trong một terminal khác, bật Datagen chạy liên tục để sinh dữ liệu biến động:

```powershell
docker compose --profile manual up datagen
```

### Bước 6: Chạy dbt Build

```bash
cd dbt/thelook_dwh
dbt build
```

Lúc này, dbt test `relationships` (Khoá ngoại) sẽ hoàn toàn xanh (PASS) vì 100% dữ liệu gốc (users, products) đã được đẩy qua từ trước khi datagen tạo order mới.
