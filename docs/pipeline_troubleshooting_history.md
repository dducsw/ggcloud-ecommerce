# Báo Cáo Triển Khai & Khắc Phục Sự Cố Dòng Chảy Dữ Liệu (CDC Pipeline)

Tài liệu này ghi chép lại toàn bộ quá trình tái cấu trúc, gỡ lỗi và tối ưu hóa hệ thống Data Pipeline theo kiến trúc Serverless (loại bỏ hoàn toàn Kafka, kết nối thẳng Debezium lên Google Cloud Pub/Sub).

---

## 🏗️ 1. Tái cấu trúc Kiến trúc (Kafka-less)
**Vấn đề:** Kiến trúc cũ sử dụng cụm Kafka trung gian khá cồng kềnh, tiêu tốn phần cứng Local. Mục tiêu là stream trực tiếp bản ghi CDC từ PostgreSQL lên nền tảng Cloud.
**Giải pháp:**
- Chuyển config sang sử dụng trực tiếp `debezium-server` với Sink là `pubsub`.
- Cơ chế **Routing (ByLogicalTableRouter):** Phân luồng dữ liệu thông minh trong file `application.properties`:
  - Bảng `events` (Lưu lượng lớn, cần phân tích hành vi riêng) $\rightarrow$ Đẩy vào Topic đặc thù `thelook_clickstream_events`.
  - Các bảng hệ thống còn lại (`users`, `orders`, `products`...) $\rightarrow$ Đẩy vào chung Topic `thelook-cdc-events`.

---

## 🔐 2. Xử lý Trục trặc Phân Quyền (IAM)
**Vấn đề:** Debezium Server ở local liên tục văng lỗi `PERMISSION_DENIED` hoặc phàn nàn thiếu quyền gọi Cloud Pub/Sub API. 
**Giải pháp:**
- Dò tìm file `infra/terraform/main.tf` và phát hiện Service Account mới chỉ được cấp `roles/pubsub.publisher` (chỉ có quyền nhét data).
- Tiến hành ghi đè thành quyền `roles/pubsub.admin` và đảm bảo API Pub/Sub được Active qua gcloud. Khởi động lại Container để bypass thời gian trễ (propagation delay) của Google Cloud.

---

## 🚦 3. Lưu thông Điểm Nghẽn Cổ Chai (Snapshot Congestion)
**Vấn đề:** Dù Debezium đã gửi thành công, lệnh chạy Apache Beam `run_local_dataflow.ps1` có vẻ như bị đóng băng, dòng log chỉ lẹt đẹt `Routing CDC message: table=users` mà hoàn toàn không thấy BigQuery có biến động.
**Giải pháp:**
- **Nguyên nhân cốt lõi:** Cơ chế mặc định của Debezium khi cắm vào Database mới là *Initial Snapshot* (hút chụp lại toàn bộ cơ sở dữ liệu lịch sử). Máy local chạy Dataflow (`DirectRunner`) trong 1 tiến trình duy nhất bị nghẹt thở bởi 20.000 dòng dữ liệu cũ của bảng `users` và `products`.
- **Khắc phục triệt để:** 
  1. Set cấu hình `debezium.source.snapshot.mode=schema_only` để bỏ qua đống rác quá khứ, chỉ bắt những đơn hàng Real-time ngay tại thời điểm bấm chạy.
  2. Viết Python script clear sạch 20.000 tin nhắn bị kẹt (Purge) trong hàng đợi (Subscription) để mở đường cao tốc cho Dataflow.

---

## 🛠️ 4. Xóa Sạch Các Rào Cản Apache Beam & BigQuery

Khi dữ liệu chính thức thông xe và đổ về cửa BigQuery, 3 "tai nạn rải đinh" đã xuất hiện và bị dẹp loạn tức thì:

1. **Lỗi "Bộ chạy ảo" (PrismRunner Exception)**
   - **Tình trạng:** Terminal nháy đỏ toàn báo lỗi `ERROR:PrismRunner`.
   - **Giải quyết:** Hệ điều hành Windows xung đột cục bộ với Prism, nhưng Beam đã tự động chuyển hướng cực chuẩn xác sang `DirectRunner` ở dòng tiếp theo. Lỗi đỏ chỉ là "cảnh báo ảo", hệ thống vẫn sống nguyên.

2. **Lỗi Lạc Đường Nhầm Dataset (NotFound Dataset)**
   - **Tình trạng:** Script Python truyền tham số `--bronze_dataset thelook_bronze`, nhưng Terraform trên Google Cloud chỉ tạo dataset tên là `staging`. Dữ liệu bơ vơ không biết về đâu.
   - **Giải quyết:** Dẫn link chuyển cổng sang lưu tại `--bronze_dataset staging`. Đồng thời, chuẩn hóa format file GCS Parquet thành thư mục xịn xò (VD: `/raw/users/...`).

3. **Lỗi "Xây nhà không có bản thiết kế" (Table requires a schema)**
   - **Tình trạng:** Lệnh Streaming API Insert đập thẳng vào BigQuery bị từ chối do 2 bảng `orders` và `events` chưa từng được định nghĩa các cột. Dataflow lặp vô hạn `Retry with exponential backoff`.
   - **Giải quyết:** Đẩy một lệnh Python DDL script tạo nóng 2 khung bảng ở BigQuery với đầy đủ các cột khai báo chính xác.

4. **Lỗi Vượt Thời Gian Mốc Giới Hạn (Epoch out of range)**
   - **Tình trạng:** Gửi `created_at` qua BigQuery thì nhận được lỗi dị thường thông báo năm xa xăm (56 triệu Công nguyên). 
   - **Giải quyết:** Nguồn rễ là do Debezium đo đếm Timestamp PostgreSQL bằng đơn vị **Microseconds**, trong khi BigQuery mong chờ định dạng **Seconds**. Thay đổi cơ chế lõi của hàm `to_bq_row()` trong `beam_router.py` để chia một triệu ($1.000.000$) và parse về ISO-8601 String chuẩn quốc tế.

5. **Lỗi Thiếu Cột Sinh Tử (no such field: updated_at)**
   - **Tình trạng:** Bảng `orders` bị hụt một cột `updated_at` trong cấu hình do bất cẩn tạo DDL script thiếu.
   - **Giải quyết:** Đâm thẳng lệnh SQL `ALTER TABLE staging.orders ADD COLUMN updated_at TIMESTAMP`. Lợi dụng cơ chế "Exponential Backoff Retry" của Beam, sau 2 giây Dataflow tự động đẩy mớ data bị văng rớt vào khe trống mượt mà.

---

## ✅ KẾT QUẢ CUỐI CÙNG
- **Cold Path (Batch):** Hoàn hảo dải Parquet dưới Data Lake Cloud Storage với 0 warning `utcfromtimestamp` thần thánh.
- **Hot Path (Speed):** Bảng `orders` và `events` nhận data Real-time siêu mượt từ Web Fake Datagen, trôi thẳng đuột vào BigQuery trong vòng chưa tới 1 giây.
- **Kinh nghiệm vô giá rút ra:** Hãy đặt niềm tin vào cơ chế Dataflow, đừng vội gõ `Ctrl + C` mỗi khi thấy chữ vàng khè hay khi hệ thống đang xử lý tác vụ dưới ngầm! 🚀


Lệnh chạy Dataflow:
python src/dataflow/beam_router.py `
  --project cloud-data-project-492514 `
  --runner DirectRunner `
  --temp_location gs://etl-staging-0/tmp `
  --staging_location gs://etl-staging-0/staging `
  --pubsub_subscription projects/cloud-data-project-492514/subscriptions/thelook-cdc-events-sub `
  --events_subscription projects/cloud-data-project-492514/subscriptions/thelook_clickstream_events-sub `
  --bronze_dataset staging `
  --gcs_output_prefix gs://etl-staging-0/raw

Ý nghĩa: 
--project: Chỉ định dự án Google Cloud nơi chứa tài nguyên.
--runner DirectRunner: Yêu cầu Apache Beam chạy pipeline ngay trên máy local (DirectRunner) thay vì triển khai lên Dataflow Service.
--temp_location: Đường dẫn tạm thời trên GCS để lưu trữ các file trung gian của pipeline.
--staging_location: Đường dẫn trên GCS để lưu trữ các file staging (cần thiết cho Dataflow Service, nhưng vẫn hữu ích cho DirectRunner).
--pubsub_subscription: ID của Pub/Sub subscription chứa các bản ghi CDC từ Debezium (cho các bảng hệ thống).
--events_subscription: ID của Pub/Sub subscription chứa các bản ghi sự kiện (từ bảng events).
--bronze_dataset: Tên dataset trong BigQuery nơi dữ liệu sẽ được ghi vào (ở tầng Bronze/Raw).
--gcs_output_prefix: Tiền tố đường dẫn trên GCS nơi dữ liệu sẽ được ghi vào dưới dạng Parquet (cho Cold Path).
Lệnh dùng để:
- Đọc dữ liệu từ Pub/Sub
- Xử lý dữ liệu
- Ghi dữ liệu vào BigQuery
- Ghi dữ liệu vào GCS