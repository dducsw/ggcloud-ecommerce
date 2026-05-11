# Clickstream Analytics

Pipeline clickstream hiện tại:

- `datagen` publish event vào Pub/Sub topic `clickstream`
- `src/clickstream/dataflow_job.py` đọc stream từ Pub/Sub
- Dataflow thực hiện validation, dead-letter, event-time windowing, aggregate 5 phút, sessionization, enrichment product và stateful dedup
- BigQuery lưu các bảng `events_raw`, `events_deadletter`, `events_5m`, `session_metrics`

## Khởi tạo hạ tầng (Dataset, Pub/Sub, Tables, Views)

Sử dụng script Python để khởi tạo toàn bộ hạ tầng cần thiết:

```powershell
# Chạy lần đầu hoặc cập nhật infra
python src/clickstream/init_infra.py --project <GCP_PROJECT_ID>

# Chạy khi muốn xóa sạch dữ liệu BigQuery trước khi test
python src/clickstream/init_infra.py --project <GCP_PROJECT_ID> --truncate
```

(Hoặc dùng flag `-Init` trong script PowerShell bên dưới để chạy init + pipeline cùng lúc)

## Chạy Pipeline trên Dataflow

> Chạy từ **thư mục gốc** của project (`BTL-DWH/`).

**Cửa sổ 1 — Data Generator (Pub/Sub publisher):**

```powershell
cd datagen
.\manage_data.ps1 -Action gen-events -GCP_PROJECT 'cloud-data-project-492514'
```

**Cửa sổ 2 — Dataflow Streaming Job:**

```powershell
.\src\clickstream\run_clickstream_pipeline.ps1 `
  -ProjectId 'cloud-data-project-492514' `
  -BucketName 'etl-staging-0' `
  -Runner DataflowRunner `
  -ProductLookupDataset 'thelook_dwh' `
  -ProductLookupTable 'dim_products' `
  -UsePublicIps
```

> **Lưu ý:**
> - Lần đầu submit sẽ mất ~2 phút để build & upload `src` package lên GCS staging.
> - `-UsePublicIps` cần thiết nếu subnetwork chưa bật Private Google Access.
> - Để chạy local (DirectRunner): bỏ `-Runner DataflowRunner` và `-UsePublicIps`.

**Xem log job trên GCP Console:**

```
https://console.cloud.google.com/dataflow/jobs?project=cloud-data-project-492514
```

## Dừng / Hủy Dataflow Job

Có 2 cách dừng job streaming:

| Lệnh | Ý nghĩa | Khi nào dùng |
|---|---|---|
| `drain` | Xử lý hết data đang in-flight rồi dừng gracefully | Dừng bình thường, không mất data |
| `cancel` | Dừng ngay lập tức, data đang xử lý bị bỏ | Cần tắt gấp, debug, hoặc job bị lỗi |

**Drain (tắt graceful — khuyến nghị):**

```powershell
gcloud dataflow jobs drain <JOB_ID> --region=asia-east1
```

**Cancel (tắt ngay):**

```powershell
gcloud dataflow jobs cancel <JOB_ID> --region=asia-east1
```

**Tìm JOB_ID của job đang chạy và cancel luôn (one-liner):**

```powershell
$jobId = (gcloud dataflow jobs list `
  --region=asia-east1 `
  --filter="name=clickstream-processing-v1 AND state=Running" `
  --format="value(id)" `
  --project=cloud-data-project-492514) | Select-Object -First 1
gcloud dataflow jobs cancel $jobId --region=asia-east1
```

**Drain job đang chạy (one-liner):**

```powershell
$jobId = (gcloud dataflow jobs list `
  --region=asia-east1 `
  --filter="name=clickstream-processing-v1 AND state=Running" `
  --format="value(id)" `
  --project=cloud-data-project-492514) | Select-Object -First 1
gcloud dataflow jobs drain $jobId --region=asia-east1
```

> **Lưu ý:** Sau khi `drain`, job chuyển sang trạng thái `JOB_STATE_DRAINING` rồi `JOB_STATE_DRAINED`. Có thể mất vài phút.

## Outputs

- `thelook_clickstream.events_raw`
- `thelook_clickstream.events_deadletter`
- `thelook_clickstream.events_5m`
- `thelook_clickstream.session_metrics`
- `thelook_clickstream.v_session_funnel`
- `thelook_clickstream.v_daily_channel_kpis`
- `thelook_clickstream.v_product_interest`

## Deploy Dashboard lên Cloud Run

> Chạy từ **thư mục gốc** của project (`BTL-DWH/`).

```powershell
# Deploy lần đầu (public URL, không cần đăng nhập)
.\src\dashboard\deploy_cloudrun.ps1 `
  -ProjectId 'cloud-data-project-492514' `
  -AllowUnauthenticated

# Deploy update (không thay đổi quyền truy cập)
.\src\dashboard\deploy_cloudrun.ps1 `
  -ProjectId 'cloud-data-project-492514'
```

**Tham số tùy chọn:**

| Param | Default | Ý nghĩa |
|---|---|---|
| `-Region` | `asia-east1` | Region Cloud Run (Taiwan) |
| `-Memory` | `512` | RAM (MB) |
| `-MaxInstances` | `2` | Tối đa instances (giới hạn chi phí) |
| `-MinInstances` | `0` | Scale-to-zero khi không có traffic |
| `-AllowUnauthenticated` | off | Cho phép public access |

**Xem URL sau khi deploy:**

```powershell
gcloud run services describe thelook-dashboard `
  --region=asia-east1 `
  --project=cloud-data-project-492514 `
  --format="value(status.url)"
```



Việc cần làm, test Pub/Sub + Dataflow + BQ
Bằng cách cho chạy PubSub, chạy Dataflow job, check dữ liệu mới nhất trên BiqQuery
Trình bày lại Dashboad Clickstream phục vụ phân tích và ops. (Có thể redeploy dashboard và trình bày trên cloud), bổ sung thêm vài note nhỏ trên dashboard để biết event mới nhất đang ở thời gian nào -> dễ test luồng clickstream hơn
Với Dataflow và Cloud Run (cho dashboard) thì đang chạy ở asia-east1 (taiwan) cho tiết kiệm, khi test nhớ bật/tạo dataflow job, test xong thì nhớ cancel job
