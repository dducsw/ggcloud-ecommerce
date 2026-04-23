# Hướng dẫn chạy End-to-End Pipeline (Tiền đề Code Dashboard)

Văn bản này hướng dẫn chi tiết từng bước (từ lúc chưa có gì chạy đến lúc có dữ liệu "chín" ở lớp Gold) mô phỏng chính xác hệ thống Production để bạn có đầy đủ dữ liệu cho việc lập trình Dashboard.

> [!IMPORTANT]
> **Yêu cầu quan trọng trước khi bắt đầu:**
> - Máy đã cài Docker và Docker Compose.
> - Đã đăng nhập tài khoản Google Cloud (tài khoản có quyền thao tác BigQuery): Chạy lệnh `gcloud auth application-default login` nếu chưa login dạo gần đây.
> - Đảm bảo các port `5432` (PostgreSQL), `8080`, v..v không bị ứng dụng khác chiếm dụng.

---

## 1. Khởi động Tầng Nguồn & Event Bus (Docker)
Lớp lưới này chứa Database thật, trình sinh dữ liệu giả lập (Datagen), Kafka và Debezium.

1.  **Chạy lệnh khởi động:**
    Mở một terminal mới (Terminal A), di chuyển tới thư mục gốc dự án:
    ```powershell
    docker compose up -d
    ```

2.  **Kiểm tra tình trạng:**
    Chờ khoảng 30s - 1 phút, gõ lệnh:
    ```powershell
    docker compose ps
    ```
    ✅ **Pass khi:** Các services định danh như `postgres-source`, `ggcloud_datagen`, `ggcloud_kafka`, và đặc biệt là `debezium-server` đều ở trạng thái `Up`.

3.  **Kiểm tra Debezium bắt được CDC chưa:**
    ```powershell
    docker logs -f debezium-server
    ```
    ✅ **Pass khi:** Thấy log báo ping connect thành công tới Kafka/Pub-Sub và dòng dữ liệu chảy qua màn hình. Ấn `Ctrl + C` để thoát log.

---

## 2. Cài đặt Data Warehouse (BigQuery)
Tạo Dataset và khoét sẵn các External Table trỏ thẳng ra Data Lake.

1.  **Chạy script Setup:**
    *(Lưu ý: Thay thế Project ID của bạn nếu nó khác với `cloud-data-project-492514`)*
    ```powershell
    .\infra\bigquery\setup_bigquery.ps1 -ProjectId "cloud-data-project-492514" -Location "asia-southeast1" -BronzeDataset "thelook_staging" -GoldDataset "thelook_datawarehouse" -RawBucketPrefix "gs://etl-staging-0/raw"
    ```
    ✅ **Pass khi:** Bảng điều khiển màu xanh hiện ra báo `Successfully created dataset` hoặc `Tables updated`.

---

## 3. Chạy Streaming Router (Apache Beam)
Đây là trái tim luân chuyển data hot/cold.

1.  **Bật Beam:**
    Chạy lệnh này (có thể mở sang một **Terminal B** mới vì tiến trình này sẽ chạy vô hạn, nó đóng vai trò hứng data streaming):
    ```powershell
    .\run_local_dataflow.ps1
    ```
    ✅ **Pass khi:** Thấy log in ra đã parse schema thành công và đang lắng nghe (listening) vào CDC topics. Không thấy bị văng lỗi hay retry vô hạn.

---

## 4. Kiểm tra Staging (Dữ liệu đã về tới kho chưa?)
Đợi Beam chạy được khoảng 1-2 phút để nước bắt đầu ngấm vào xô. Dùng **Terminal C**.

1.  **Test Hot Path (luồng nhanh - events):**
    ```powershell
    bq query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `cloud-data-project-492514.thelook_staging.events`'
    ```
    ✅ Bạn phải thấy con số lớn hơn `0`. Chạy lại lần nữa phải thấy con số `tăng lên`.

2.  **Test Cold Path (luồng chậm - orders/users CDC):**
    ```powershell
    bq query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `cloud-data-project-492514.thelook_staging.orders`'
    ```
    *(Ghi chú: Vì Cold Path xài External Table trên GCS, Parquet flush định kì cứ 1-2 phút mới nhả 1 file, nếu thấy số 0 hãy kiên nhẫn pha tách trà đợi thêm xíu rồi query lại).*

---

## 5. Chạy Data Transformation (dbt) 🚀
Lớp này sẽ kích hoạt toàn bộ 100% logic kinh doanh siêu xịn sò chúng ta vừa làm khi nãy.

1.  **Vào thư mục dbt:**
    ```powershell
    cd dbt/thelook_dwh
    ```
2.  **Kiểm tra độ tươi của data (Freshness):**
    ```powershell
    dbt source freshness --profiles-dir .
    ```
3.  **Build toàn bộ Warehouse Layer:**
    ```powershell
    dbt build --profiles-dir .
    ```
    > [!TIP]
    > Lệnh `build` sẽ tự động chạy test trước, chạy models, và sinh bảng. Đặc biệt logic Incremental mạnh mẽ ở `fact_orders` sẽ tự tìm và scan đúng các đơn hàng cần thiết.

    ✅ **Pass khi:** Kết thúc màn hình toàn viền xanh lá `Completed successfully`. KHÔNG có chữ `ERROR`.

---

## 6. Sẵn sàng Code Dashboard!
Tới thời điểm này, toàn bộ Data Warehouse đã sạch sẽ, đẹp đẽ và đầy đủ số liệu tại dataset `thelook_datawarehouse`.

1.  **Mở app Streamlit:**
    Mở terminal ở thư mục gốc ban đầu (nơi chứa `src/dashboard`)
    ```powershell
    streamlit run src/dashboard/app.py
    ```

> [!NOTE]
> Bất cứ khi nào bạn thấy Dashboard hiển thị số bị ngưng trệ hoặc muốn có data mới của ngày hôm nay, bạn không cần làm lại từ bước 1. Cứ quay lại **Bước 5** (Chạy thư mục dbt) là số sẽ cập nhật tự động!
