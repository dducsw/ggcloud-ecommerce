# Kế hoạch Hiện thực hóa Data Quality Test Plan

Mục tiêu của kế hoạch này là bổ sung các công cụ kiểm thử tự động vào hệ thống thực tế nhằm đảm bảo dữ liệu qua luồng từ Datagen -> Pub/Sub -> Beam -> BigQuery -> dbt không bị mất mát và được xử lý deduplicate chuẩn xác.

## User Review Required

> [!IMPORTANT]
> - Việc chạy các bài test này có thể thay đổi dữ liệu hiện tại trong Data Warehouse (tạo ra thêm đơn hàng ảo từ Datagen). Bạn có muốn tôi tạo một môi trường schema test riêng rẽ trên BigQuery không, hay cứ chạy và test thẳng vào `thelook_datawarehouse` (môi trường dev hiện tại)?
> - Việc cài đặt `dbt-utils` và `dbt-expectations` sẽ yêu cầu bạn chạy `dbt deps` trong lần khởi động tới.
> - Kế hoạch này sẽ viết thêm script Python bằng thư viện `google-cloud-bigquery` và `psycopg2`. Vui lòng xác nhận môi trường ảo (virtualenv) của bạn đã cài đặt đủ các package này (nếu chưa, tôi sẽ bổ sung vào `requirements.txt`).

## Proposed Changes

---

### dbt Packages & Dependencies

Để áp dụng các test phức tạp (chẳng hạn kiểm tra giá trị chấp nhận được, format cột, số lượng row), chúng ta cần thêm các package tiện ích của cộng đồng dbt.

#### [NEW] [packages.yml](file:///d:/BK_Document/252/BTL_DWH_CLOUD/ggcloud-ecommerce/ggcloud-ecommerce/dbt/thelook_dwh/packages.yml)
- Tạo file để cài đặt `dbt-utils` (cho unique combination test) và `dbt-expectations` (cho row count test).

---

### dbt Data Quality Tests (Schema Assertions)

Bổ sung các test tự động vào cấu hình dbt để mỗi khi chạy `dbt test`, hệ thống sẽ bắt lỗi data (duplicate, null, mất quan hệ).

#### [MODIFY] [sources.yml](file:///d:/BK_Document/252/BTL_DWH_CLOUD/ggcloud-ecommerce/ggcloud-ecommerce/dbt/thelook_dwh/models/sources.yml)
- Bổ sung `tests: - not_null`, `tests: - unique` cho các khóa chính của raw data.
- Bổ sung `accepted_values` cho các trạng thái của orders.

#### [NEW] [schema.yml](file:///d:/BK_Document/252/BTL_DWH_CLOUD/ggcloud-ecommerce/ggcloud-ecommerce/dbt/thelook_dwh/models/staging/schema.yml)
- Cấu hình test cho tầng `staging`. Đảm bảo rằng sau khi áp dụng logic lọc `cdc_timestamp` và `cdc_operation != 'd'`, dữ liệu phải thực sự `unique`.
- Bổ sung test khóa ngoại (`relationships`) giữa `stg_orders` và `stg_users`.

---

### E2E Data Reconciliation Script (Đối soát Source - Target)

Chúng ta cần một công cụ độc lập để so sánh dữ liệu ở PostgreSQL với dữ liệu cuối cùng ở BigQuery (Fact/Dim tables) để chắc chắn 100% Beam/Pub/Sub không làm rớt data.

#### [NEW] [data_reconciliation.py](file:///d:/BK_Document/252/BTL_DWH_CLOUD/ggcloud-ecommerce/ggcloud-ecommerce/src/testing/data_reconciliation.py)
- Script Python có nhiệm vụ:
  1. Truy vấn số dòng (`COUNT(*)`) và Doanh thu (`SUM(sale_price)`) trực tiếp từ PostgreSQL (bảng `orders` & `order_items`).
  2. Truy vấn chỉ số tương tự từ BigQuery (`fact_orders` & `fact_events`).
  3. Đối soát hai kết quả và in ra cảnh báo nếu có sự sai lệch (Data Loss hoặc Duplicate Error).

#### [NEW] [run_dq_tests.ps1](file:///d:/BK_Document/252/BTL_DWH_CLOUD/ggcloud-ecommerce/ggcloud-ecommerce/run_dq_tests.ps1)
- Một bash/powershell script nhỏ gom các thao tác lại cho bạn test dễ dàng chỉ với 1 click:
  - Cập nhật dbt deps.
  - Chạy `dbt build` (bao gồm dbt run và dbt test).
  - Kích hoạt `data_reconciliation.py`.

## Verification Plan

### Automated Tests
- Chạy `.\run_dq_tests.ps1` để trigger toàn bộ chu trình.
- Kỳ vọng dbt tests vượt qua 100% (Green).
- Kỳ vọng output của `data_reconciliation.py` báo cáo số lượng row ở PostgreSQL bằng với số lượng row (không bị soft delete) ở BigQuery.

### Manual Verification
- Bạn có thể vào BigQuery UI, tự tay sửa một bản ghi trong `thelook_staging.orders` thành ID trùng lặp, sau đó chạy lại `dbt test` để thấy dbt cảnh báo lỗi ngay lập tức.
