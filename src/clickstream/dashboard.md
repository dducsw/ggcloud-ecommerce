# Clickstream Dashboard Deployment & Cost Analysis

Bản báo cáo tóm tắt quá trình triển khai hệ thống Dashboard phân tích clickstream lên môi trường Cloud.

## 1. Tóm tắt công việc đã thực hiện

### 🔧 Kỹ thuật & Hạ tầng
- **Containerization**: Đóng gói ứng dụng Streamlit vào Docker image (`python:3.11-slim`).
- **Cloud Run Deployment**: Triển khai lên Google Cloud Run tại region `asia-east1` (Đài Loan) để tối ưu chi phí.
- **CI/CD Script**: Tạo script `deploy_cloudrun.ps1` tự động hóa quy trình Build -> Push -> Deploy.
- **Infrastructure as Code**: Tự động kích hoạt các API cần thiết (`run.googleapis.com`, `artifactregistry.googleapis.com`).

## 2. Các lệnh vận hành Dashboard

### 🚀 Triển khai & Cập nhật
Chạy từ thư mục gốc của project:
```powershell
# Triển khai mới hoặc cập nhật code (mặc định cho phép truy cập công khai)
.\src\dashboard\deploy_cloudrun.ps1 -ProjectId 'cloud-data-project-492514' -AllowUnauthenticated
```

### 🛑 Tắt / Xóa Dashboard
Khi không còn nhu cầu sử dụng và muốn xóa hoàn toàn resource để tránh rủi ro phát sinh phí (dù rất nhỏ):
```powershell
# Xóa service Cloud Run
gcloud run services delete thelook-dashboard --region=asia-east1 --project=cloud-data-project-492514 --quiet

# Xóa Docker image trong Registry (giảm phí lưu trữ)
gcloud container images delete gcr.io/cloud-data-project-492514/thelook-dashboard:latest --force-delete-tags --quiet
```

> **Lưu ý**: Nhờ cấu hình `Scale-to-Zero`, bạn **không nhất thiết** phải xóa service hàng ngày. Khi không có ai truy cập, Cloud Run sẽ tự động tắt hết các instance và không tính phí CPU/RAM.

### ⚡ Tối ưu hóa hiệu năng & Chi phí
- **Memory Optimization**: Loại bỏ toàn bộ `st.cache_data` và `st.cache_resource` trong mã nguồn. 
  - *Lý do*: RAM trên Cloud Run rất đắt và giới hạn (512MB). Việc cache trong RAM instance sẽ làm tăng rủi ro lỗi OOM (Out Of Memory) khi có nhiều người truy cập.
- **Cloud-Native Caching**: Chuyển sang sử dụng hoàn toàn **BigQuery Query Cache**.
  - *Kết quả*: Kết quả các lần query giống nhau sẽ được BQ trả về ngay lập tức và **miễn phí**, không tốn tài nguyên xử lý của Cloud Run.
- **Scale-to-Zero**: Cấu hình `--min-instances=0`. Dashboard sẽ tự động tắt hoàn toàn khi không có người xem, giúp tiết kiệm 100% chi phí chạy idle.

---

## 2. Ước tính chi phí (GCP Asia-East1)

Giả sử Dashboard phục vụ **1 giờ truy cập chủ động mỗi ngày** (Active Usage).

### A. Cloud Run
Cấu hình: 1 vCPU, 512MB RAM.

| Thành phần | Công thức tính (30 ngày) | Chi phí |
|---|---|---|
| **vCPU** | 1 CPU * 3600s * 30 ngày = 108,000s | $0 (Dưới mức Free Tier 180k s) |
| **RAM** | 0.5GB * 3600s * 30 ngày = 54,000s | $0 (Dưới mức Free Tier 360k s) |
| **Requests** | ~10,000 requests/tháng | $0 (Dưới mức Free Tier 2M req) |
| **Tổng Cloud Run** | | **$0.00 / tháng** |

### B. BigQuery (Dữ liệu Gold Layer)
| Thành phần | Ước tính | Chi phí |
|---|---|---|
| **Storage** | ~500MB dữ liệu | ~$0.01 / tháng |
| **Analysis** | ~5GB quét mỗi tháng | $0 (Dưới mức Free Tier 1TB) |
| **Tổng BigQuery** | | **~$0.01 / tháng** |

### C. Artifact Registry (Lưu trữ Docker Image)
- Kích thước image: ~450MB.
- Giá: $0.10 / GB / tháng.
- **Tổng lưu trữ**: **~$0.05 / tháng**.

---

## 3. Tổng kết chi phí vận hành

> [!TIP]
> Với lưu lượng truy cập thấp cho mục đích báo cáo nội bộ, hệ thống Dashboard clickstream gần như chạy **MIỄN PHÍ** (~$0.06/tháng, khoảng 1.500 VNĐ).

**So sánh với chạy Local:**
- **Local**: Tốn điện, cần máy chủ bật 24/7 hoặc mở thủ công, khó chia sẻ link.
- **Cloud Run**: Sẵn sàng 24/7 qua HTTPS, tự động bảo mật, chi phí tiệm cận bằng 0 nhờ chế độ Scale-to-zero.

**URL Dashboard:** [https://thelook-dashboard-341195080773.asia-east1.run.app](https://thelook-dashboard-341195080773.asia-east1.run.app)
