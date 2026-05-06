# Hướng dẫn thiết lập GCP & Phối hợp dự án (Partner Setup)

Tài liệu này hướng dẫn cách các thành viên trong nhóm thiết lập môi trường để có thể phối hợp làm việc trên hạ tầng Google Cloud Platform (GCP) của dự án **TheLook Data Lakehouse**.

---

## 1. Yêu cầu tiên quyết (Prerequisites)

Hãy đảm bảo máy bạn đã cài đặt các công cụ sau:
*   **Git**: Để clone và quản lý mã nguồn.
*   **Python 3.10+**: Để chạy các script ETL và Dashboard.
*   **Docker & Docker Compose**: Để chạy Postgres, Kafka và Debezium local.
*   **Google Cloud SDK (gcloud CLI)**: [Tải về tại đây](https://cloud.google.com/sdk/docs/install).
*   **Terraform**: [Tải về tại đây](https://developer.hashicorp.com/terraform/downloads).

---

## 2. Thiết lập xác thực (Authentication)

Vì dự án đã được chia sẻ quyền IAM, bạn cần login tài khoản cá nhân của mình trên máy local:

```powershell
# Đăng nhập Google Cloud
gcloud auth login

# Thiết lập Application Default Credentials (quan trọng để Terraform và Python chạy được)
gcloud auth application-default login
```

---

## 3. Cấu hình biến môi trường (Environment Config)

Bạn cần tạo các file cấu hình sau từ các mẫu có sẵn:

1.  **File `.env`**: Copy từ `.env.examle`, điền `GCP_PROJECT_ID` của nhóm.
2.  **File `terraform.tfvars`**: Vào thư mục `infra/terraform`, copy từ `terraform.tfvars.example`. Đảm bảo các thông tin về `project_id`, `region`, và `gcs_bucket_name` trùng khớp với hạ tầng chung.

---

## 4. Triển khai hạ tầng (Terraform)

Dự án sử dụng **Remote Backend (GCS)**, vì vậy tất cả thành viên sẽ cùng thấy một trạng thái hạ tầng duy nhất.

```powershell
cd infra/terraform

# Khởi tạo (Terraform sẽ tự kết nối tới GCS)
# Lưu ý: nếu đang dùng `GOOGLE_APPLICATION_CREDENTIALS` cho Debezium,
# hãy bỏ biến đó ra hoặc dùng một đường dẫn tuyệt đối trước khi chạy `terraform init`.
terraform init

# Kiểm tra thay đổi
terraform plan

# Áp dụng (Lệnh này cũng sẽ tự tạo file credentials/gcp-key.json cho bạn)
terraform apply
```

> [!IMPORTANT]
> Sau khi chạy `terraform apply` thành công, file **`credentials/gcp-key.json`** sẽ tự động được tạo ra. File này cần thiết để Debezium Server trong Docker có thể đẩy dữ liệu lên Cloud.

---

## 5. Khởi chạy hệ thống Local (CDC & Pipeline)

Tại thư mục gốc của dự án:

```powershell
# Khởi động Docker (Postgres, Kafka, Debezium Server)
docker-compose up -d

# Kiểm tra log của Debezium Server để đảm bảo kết nối thành công tới Pub/Sub
docker logs -f debezium-server
```

---

## 6. Xử lý & Phân tích dữ liệu

### Xử lý bằng dbt
Bạn vào thư mục `dbt/thelook_dwh` để thực hiện biến đổi dữ liệu từ lớp `staging` sang `datawarehouse`:
```powershell
dbt build
```

### Xem Dashboard
```powershell
streamlit run src/dashboard/app.py
```

---

## 7. Lưu ý khi làm việc nhóm

*   **Không đẩy file nhạy cảm**: Tuyệt đối không xóa `.gitignore`. Không bao giờ commit các file `.env`, `terraform.tfvars` hay các file `.json` trong thư mục `credentials/`.
*   **Cập nhật Terraform**: Trước khi sửa bất kỳ tài nguyên Cloud nào, hãy luôn chạy `terraform pull` (hoặc đơn giản là `terraform init`) để đảm bảo bạn đang có state mới nhất từ GCS.
*   **Replication Slots**: Hệ thống sử dụng Replication Slots trên Postgres. Nếu bạn khởi động lại Docker mà gặp lỗi liên quan đến slot, hãy kiểm tra log Postgres hoặc xóa volume cũ để khởi tạo lại.

---
*Chúc cả nhóm phối hợp tốt! Mọi thắc mắc hãy thảo luận trực tiếp trên kênh chat dự án.*
