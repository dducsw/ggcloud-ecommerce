# Kế Hoạch Kiểm Thử Chất Lượng Dữ Liệu (Data Quality Test Plan)

**Dự án**: E-commerce Data Warehouse Pipeline (Phiên bản GCP Streaming)
**Luồng dữ liệu**: Datagen (PostgreSQL) -> Debezium Server -> Pub/Sub -> Apache Beam (Hot/Cold Routing) -> BigQuery (Streaming & External Tables) -> dbt (Transformation) -> BigQuery DWH
**Mục tiêu cốt lõi**: Đảm bảo **Data Quality (DQ) cực kỳ nghiêm ngặt**, Zero Data Loss, và tính chính xác tuyệt đối của business logic.

---

## 1. Chặng 1: Datagen -> CDC (Debezium Server) -> Pub/Sub
*Mục tiêu: Đảm bảo không thất thoát dữ liệu, đúng thứ tự (ordering), và chịu lỗi tốt.*

### 1.1. Test Thất Thoát Dữ Liệu (Data Loss) & Replication
- **TC1.1.1 (CUD Parity):** Thực hiện 10,000 lệnh INSERT, 5,000 lệnh UPDATE, 1,000 lệnh DELETE trên Datagen. 
  - *Kỳ vọng:* Số lượng event sinh ra trong Pub/Sub topic (`clickstream_events` và `cdc-events`) phải khớp chuẩn xác 100%.
- **TC1.1.2 (Heartbeat/Watermark Test):** Tạo một bảng `heartbeat` trên Source, Datagen update mỗi giây.
  - *Kỳ vọng:* Pub/Sub nhận được đủ các event heartbeat, không bị đứt quãng. Dùng để đo replication lag của Debezium.
- **TC1.1.3 (Large Payload):** Insert các bản ghi có chứa trường text/JSON rất lớn.
  - *Kỳ vọng:* Debezium không bị OOM (Out Of Memory), Pub/Sub không rớt message do vượt giới hạn size của Google Cloud.

### 1.2. Test Trình Tự & Trùng Lặp (Ordering & Duplication)
- **TC1.2.1 (Strict Ordering):** Thực hiện liên tiếp INSERT -> UPDATE -> DELETE trên cùng 1 `id` (vd: `order_id = 1`) trong chớp nhoáng.
  - *Kỳ vọng:* Pub/Sub bảo đảm thứ tự event. Nếu event DELETE đến trước UPDATE, xử lý ở chặng sau sẽ sai lệch. (Đảm bảo message ordering key của Pub/Sub nếu có).
- **TC1.2.2 (At-least-once Delivery):** Giả lập Apache Beam pipeline bị crash và restart.
  - *Kỳ vọng:* Pub/Sub có thể gửi lại (duplicate) event do chưa được ack, hệ thống (Beam/dbt) phải được thiết kế Idempotent (xử lý deduplication qua `cdc_timestamp`).

### 1.3. Test Khả Năng Phục Hồi (Resilience)
- **TC1.3.1 (CDC Disconnect):** Tắt Debezium Server khoảng 1 tiếng, trong lúc đó Datagen vẫn chạy. Bật lại Debezium.
  - *Kỳ vọng:* Debezium đọc đúng WAL offset/LSN cuối cùng (với cấu hình `debezium.source.snapshot.mode=no_data`), đẩy bù toàn bộ data bị nghẽn mà không thiếu hay trùng lệch.

---

## 2. Chặng 2: Apache Beam Router & Staging Layer
*Mục tiêu: Đảm bảo luồng định tuyến (Routing) hoạt động chính xác theo cơ chế Hot/Cold.*

### 2.1. Test Logic Phân Luồng (Routing)
- **TC2.1.1 (Hot Path Routing):** Đẩy dữ liệu vào bảng `events`.
  - *Kỳ vọng:* Dữ liệu `events` đi qua luồng Hot và được Streaming Insert trực tiếp vào bảng `thelook_staging.events` trên BigQuery.
- **TC2.1.2 (Cold Path Routing):** Đẩy dữ liệu vào bảng `orders`, `users`.
  - *Kỳ vọng:* Dữ liệu đi qua luồng Cold, lưu thành file Hive Partitioned Parquet trên thư mục GCS (`gs://etl-staging-0/raw/`), và có thể truy vấn qua BigQuery External Tables (`thelook_staging.orders`, `thelook_staging.users`).

---

## 3. Chặng 3: dbt Transformations (Trọng tâm)
*Mục tiêu: Làm sạch, chuẩn hóa, áp dụng logic nghiệp vụ và xử lý các vấn đề của data phân tán.*

Sử dụng các package `dbt-utils` và `dbt-expectations` để test nghiêm ngặt.

### 3.1. Test Khử Trùng Lặp bằng `cdc_timestamp` (Cực kỳ quan trọng)
Do CDC (Pub/Sub) có thể sinh ra duplicate data (At-least-once), việc dbt xử lý deduplicate là chí mạng.
- **TC3.1.1 (Upsert Logic):** Đẩy 3 event update cho cùng 1 `order_id` với các `cdc_timestamp` khác nhau. Run dbt.
  - *Kỳ vọng:* Bảng ở Data Warehouse (`thelook_datawarehouse`) chỉ chứa **1 bản ghi duy nhất** của `order_id` đó, mang giá trị của `cdc_timestamp` lớn nhất. (Áp dụng logic: `row_number() over (partition by id order by cdc_timestamp desc)`).
- **TC3.1.2 (Late Arriving Data):** Đẩy 1 event UPDATE có `cdc_timestamp` cũ hơn bản ghi đã tồn tại trong DWH.
  - *Kỳ vọng:* dbt bỏ qua bản ghi này, không ghi đè data mới bằng data cũ.
- **TC3.1.3 (Hard Delete Handling):** Đẩy 1 event có `cdc_operation = 'd'`.
  - *Kỳ vọng:* dbt staging model hiểu được cờ xóa này và loại bỏ bản ghi ở các tầng phân tích phía sau (mặc dù vẫn giữ trong raw layer).

### 3.2. Test Tính Nguyên Vẹn & Ràng Buộc (Data Integrity)
- **TC3.2.1 (Not Null & Accepted Values):** Đảm bảo `order_id`, `user_id` không NULL.
- **TC3.2.2 (Referential Integrity):** Mọi `user_id` trong `orders` đều tồn tại bên bảng `users`. Xử lý Orphan records.

### 3.3. Test Logic Nghiệp Vụ (Business Logic) bằng dbt Unit Tests
- **TC3.3.1 (Tính toán Doanh thu):** Mock đầu vào và kiểm tra logic tính revenue, discount, tax ở tầng `fact_orders`.

---

## 4. Chặng 4: Data Warehouse Final Layer & Đối Soát (Reconciliation)
*Mục tiêu: Đảm bảo Data cuối cùng báo cáo cho user là chuẩn 100% so với Source.*

### 4.1. Đối soát tổng (Data Reconciliation)
- **TC4.1.1 (Row Count Audit):** Viết script đối chiếu: `SELECT COUNT(*) FROM source.orders` vs `SELECT COUNT(*) FROM thelook_datawarehouse.dim_orders` (cần trừ đi các row bị xóa nếu áp dụng soft-delete).
- **TC4.1.2 (Metric Reconciliation):** Đối chiếu Tổng Doanh Thu trên Source DB và Fact Table trên BigQuery.

---

## 5. Các Metrics Cần Monitor & Alert (Observability)

1. **Pub/Sub Unacked Messages Age:**
   - *Metric:* Thời gian message cũ nhất chưa được Apache Beam xử lý (ack).
   - *Alert:* Age > 5 phút (có thể do Beam bị nghẽn hoặc sập).
2. **Beam System Lag & Data Watermark Lag:**
   - *Metric:* Thời gian trễ xử lý streaming trong GCP Dataflow/Beam.
3. **Data Freshness (dbt):**
   - *Metric:* Dùng dbt `source freshness` kiểm tra dữ liệu trong staging.
   - *Alert:* Bảng external table hoặc streaming table không có data mới trong > 1 giờ.
4. **Data Quality Test Failure Rate:**
   - *Metric:* Bất kỳ test `unique`, `not_null` nào fail trong dbt đều phải alert.
