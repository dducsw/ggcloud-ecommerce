# Hướng Dẫn Chạy Data Quality Tests

Tài liệu này mô tả cách chạy các kiểm thử chất lượng dữ liệu đã được bổ sung theo `implementation_plan.md`, bao gồm dbt schema tests, dbt singular tests và script đối soát PostgreSQL với BigQuery.

## 1. Các Thành Phần Test Đã Bổ Sung

### dbt packages

File: `dbt/thelook_dwh/packages.yml`

Các package được dùng:

- `dbt-labs/dbt_utils`: bổ sung macro/test tiện ích cho dbt.
- `metaplane/dbt_expectations`: bổ sung các test dạng expectation, ví dụ kiểm tra số dòng trong bảng.

### Source tests

File: `dbt/thelook_dwh/models/sources.yml`

Nhóm test này kiểm tra dữ liệu raw/staging source trong BigQuery:

- `users.id`: `unique`, `not_null`
- `orders.order_id`: `unique`, `not_null`
- `orders.status`: `accepted_values`
- `order_items.id`: `unique`, `not_null`
- `order_items.order_id`: `not_null`
- Freshness cho một số source table như `orders`, `order_items`, `events`

### Staging model tests

File: `dbt/thelook_dwh/models/staging/schema.yml`

Nhóm test này kiểm tra dữ liệu sau khi dbt đã clean và deduplicate:

- Khóa chính staging phải `unique` và `not_null`
- Các khóa ngoại quan trọng dùng `relationships`
- Các timestamp quan trọng như `created_at` không được null
- `stg_orders.status` chỉ được nằm trong danh sách trạng thái hợp lệ
- `stg_orders` phải có ít nhất 1 dòng bằng `dbt_expectations.expect_table_row_count_to_be_between`

### Mart model tests

File: `dbt/thelook_dwh/models/marts/schema.yml`

Nhóm test này kiểm tra tầng data warehouse cuối:

- Dimension keys và business IDs phải `unique`, `not_null`
- Fact table keys phải liên kết được tới dimension table tương ứng
- Aggregate table như `agg_dashboard_daily`, `agg_user_stats` có các cột bắt buộc không null
- `agg_user_stats.customer_status` chỉ nhận các giá trị hợp lệ

### Singular SQL tests

Folder: `dbt/thelook_dwh/models/test/`

Các test SQL custom hiện có:

- `assert_positive_prices.sql`: không cho phép giá âm trong order items/products.
- `assert_order_item_count_match.sql`: số item khai báo trong order phải khớp số dòng order_items thực tế.
- `assert_future_dates.sql`: không cho phép timestamp nằm trong tương lai.
- `assert_revenue_consistency.sql`: tổng revenue từ `fact_order_items` phải khớp `fact_orders`.
- `assert_valid_order_status_transitions.sql`: kiểm tra thứ tự timestamp hợp lệ của vòng đời order.

### Reconciliation script

File: `src/testing/data_reconciliation.py`

Script này đối chiếu số liệu giữa PostgreSQL source và BigQuery warehouse:

- PostgreSQL `demo.orders` count
- PostgreSQL `demo.order_items` count
- PostgreSQL `SUM(sale_price)`
- BigQuery `fact_orders` count
- BigQuery `fact_order_items` count
- BigQuery revenue từ `fact_orders`

## 2. Chuẩn Bị Trước Khi Chạy

### Cài Python dependencies

Chạy từ root project:

```powershell
pip install -r requirements.txt
```

Các package cần cho phần test gồm:

- `dbt-bigquery`
- `psycopg2-binary`
- `google-cloud-bigquery`
- `python-dotenv`

### Kiểm tra PostgreSQL local

PostgreSQL source trong `docker-compose.yaml` dùng:

```text
host: localhost
port: 5433
database: thelook_db
user: db_user
password: db_password
schema: demo
```

Khởi động PostgreSQL nếu chưa chạy:

```powershell
docker compose up -d postgres-source
```

### Kiểm tra GCP credentials

dbt và reconciliation cần quyền truy cập BigQuery. Đảm bảo biến môi trường hoặc credential local đã được cấu hình, ví dụ:

```powershell
$env:GCP_PROJECT_ID="cloud-data-project-492514"
$env:GOOGLE_APPLICATION_CREDENTIALS="D:\path\to\gcp-key.json"
```

Nếu dùng file `.env`, các biến hữu ích là:

```text
GCP_PROJECT_ID=cloud-data-project-492514
GOLD_DATASET_ID=thelook_datawarehouse
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=thelook_db
POSTGRES_USER=db_user
POSTGRES_PASSWORD=db_password
```

## 3. Cài dbt Packages

Chạy từ thư mục dbt project:

```powershell
cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce\dbt\thelook_dwh
dbt deps --profiles-dir .
```

Kết quả mong đợi:

```text
Installing dbt-labs/dbt_utils
Installing metaplane/dbt_expectations
```

Sau khi cài xong, thư mục `dbt_packages` nên có:

```text
dbt_expectations
dbt_utils
```

Không commit `dbt_packages` lên git. Đây là dependency được sinh ra khi chạy `dbt deps`.

## 4. Chạy dbt Tests Theo Từng Nhóm

### Kiểm tra dbt compile trước

```powershell
cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce\dbt\thelook_dwh
dbt compile --profiles-dir .
```

Dùng lệnh này khi muốn kiểm tra cú pháp model, macro, source, ref trước khi chạy build thật.

### Chạy toàn bộ dbt build

```powershell
dbt build --profiles-dir .
```

Lệnh này chạy cả:

- `dbt run`: build model
- `dbt test`: chạy schema tests và singular tests

Đây là lệnh nên dùng cho kiểm thử đầy đủ tầng dbt.

### Chạy riêng dbt tests

```powershell
dbt test --profiles-dir .
```

Dùng khi model đã được build trước đó và chỉ muốn chạy lại test.

### Chạy test cho staging layer

```powershell
dbt test --profiles-dir . --select staging
```

Hoặc chạy theo model cụ thể:

```powershell
dbt test --profiles-dir . --select stg_orders
dbt test --profiles-dir . --select stg_order_items
```

### Chạy test cho marts layer

```powershell
dbt test --profiles-dir . --select marts
```

Hoặc chạy theo model cụ thể:

```powershell
dbt test --profiles-dir . --select fact_orders
dbt test --profiles-dir . --select fact_order_items
```

### Chạy singular SQL tests

```powershell
dbt test --profiles-dir . --select test_type:singular
```

Các test này nằm trong `dbt/thelook_dwh/models/test/`.

### Chạy source freshness

```powershell
dbt source freshness --profiles-dir .
```

Lệnh này kiểm tra độ mới của dữ liệu source theo cấu hình trong `sources.yml`.

## 5. Chạy Reconciliation PostgreSQL vs BigQuery

Chạy từ root project:

```powershell
cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce
python src/testing/data_reconciliation.py
```

Kết quả tốt sẽ có dạng:

```text
[Source PostgreSQL] Orders Count: ...
[Source PostgreSQL] Order Items Count: ...
[Source PostgreSQL] Total Revenue: ...
[Target BigQuery] fact_orders Count: ...
[Target BigQuery] fact_order_items Count: ...
[Target BigQuery] Total Revenue: ...
Orders Count: KHỚP 100%
Order Items Count: KHỚP 100%
Total Revenue: KHỚP 100%
```

Nếu lệch số dòng hoặc doanh thu, cần kiểm tra:

- CDC/Debezium có bị lag không
- Pub/Sub/Dataflow có message chưa xử lý không
- dbt model có đang lọc soft-delete hoặc deduplicate đúng không
- BigQuery warehouse đã được build lại sau khi dữ liệu source thay đổi chưa

## 6. Chạy Toàn Bộ Bằng Script Tổng Hợp

Chạy từ root project:

```powershell
cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce
.\run_dq_tests.ps1
```

Script sẽ chạy 3 bước:

1. `dbt deps --profiles-dir .`
2. `dbt build --profiles-dir .`
3. `python src/testing/data_reconciliation.py`

Lưu ý: nếu `dbt deps` bị lỗi khóa file trên Windows, không nên bỏ qua rồi chạy tiếp vì có thể tạo duplicate package trong `dbt_packages`.

## 7. Lỗi Thường Gặp Và Cách Xử Lý

### Lỗi dbt_expectations bị duplicate

Dấu hiệu:

```text
dbt found more than one package with the name "dbt_expectations"
```

Nguyên nhân thường gặp là `dbt deps` bị Windows khóa file khi đang rename package, để lại cùng lúc hai thư mục:

```text
dbt_packages\dbt-expectations-0.10.4
dbt_packages\dbt_expectations
```

Cách xử lý:

```powershell
cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce\dbt\thelook_dwh
Start-Sleep -Seconds 20
Remove-Item -Recurse -Force .\dbt_packages\dbt-expectations-0.10.4
Get-ChildItem .\dbt_packages -Directory
dbt build --profiles-dir .
```

Sau khi xóa, `dbt_packages` chỉ nên còn:

```text
dbt_expectations
dbt_utils
```

Nếu vẫn không xóa được, đóng VS Code preview, browser, File Explorer đang đứng trong thư mục đó, hoặc process `dbt docs serve` nếu có.

### Lỗi PostgreSQL password authentication failed

Dấu hiệu:

```text
password authentication failed for user "db_user"
```

Kiểm tra lại PostgreSQL container và biến môi trường:

```powershell
docker compose ps postgres-source
```

Credential mặc định trong `docker-compose.yaml` là:

```text
POSTGRES_DB=thelook_db
POSTGRES_USER=db_user
POSTGRES_PASSWORD=db_password
POSTGRES_PORT=5433
```

Nếu bạn từng đổi password hoặc volume Postgres đã tồn tại từ lần chạy cũ, biến trong `docker-compose.yaml` có thể không còn khớp với database thật trong volume.

### Warning CustomKeyInConfigDeprecation

Dấu hiệu:

```text
Custom key `+dataset` found in `config`
```

Đây là warning, chưa làm test fail. Về lâu dài nên đổi cấu hình `+dataset` trong `dbt_project.yml` sang cơ chế schema/dataset chuẩn hoặc đưa custom config vào `config.meta`.

### Warning dbt_date package deprecated

Dấu hiệu:

```text
calogica/dbt_date package is deprecated in favor of godatadriven/dbt_date
```

Đây cũng là warning. Nếu package này là dependency gián tiếp từ package khác thì chưa cần xử lý ngay để chạy test hiện tại.

### Tiếng Việt bị lỗi ký tự trong PowerShell

Dấu hiệu:

```text
Cáº­p nháº­t dbt packages
```

Đây là lỗi encoding khi PowerShell hiển thị text, không phải lỗi dbt. Có thể chạy:

```powershell
chcp 65001
```

trước khi chạy script để console dùng UTF-8.

## 8. Quy Trình Khuyến Nghị Khi Test Hằng Ngày

Chạy nhanh tầng dbt:

```powershell
cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce\dbt\thelook_dwh
dbt build --profiles-dir .
```

Chạy đối soát sau khi pipeline đã ingest dữ liệu mới:

```powershell
cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce
python src/testing/data_reconciliation.py
```

Chạy đầy đủ trước khi báo cáo hoặc demo:

```powershell
cd D:\BK_Document\252\BTL_DWH_CLOUD\ggcloud-ecommerce\ggcloud-ecommerce
.\run_dq_tests.ps1
```

