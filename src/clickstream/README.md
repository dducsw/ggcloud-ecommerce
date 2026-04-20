# Clickstream Analytics

Pipeline clickstream hiện tại:

- `datagen` publish event vào Pub/Sub topic `clickstream`
- `src/clickstream/dataflow_job.py` đọc stream từ Pub/Sub
- Dataflow thực hiện validation, dead-letter, event-time windowing, aggregate 5 phút, sessionization, enrichment product và stateful dedup
- BigQuery lưu các bảng `events_raw`, `events_deadletter`, `events_5m`, `session_metrics`

## Chạy BigQuery setup

```powershell
.\infra\bigquery\setup_clickstream_bigquery.ps1 -ProjectId <GCP_PROJECT_ID> -Location asia-southeast1
```

## Chạy Dataflow

```powershell
.\src\clickstream\run_clickstream_pipeline.ps1 -ProjectId <GCP_PROJECT_ID> -BucketName <GCS_BUCKET_NAME>
```

## Chạy datagen publish clickstream

```powershell
python datagen/thelook-ecomm/generator.py --publish-clickstream --gcp-project-id <GCP_PROJECT_ID> --clickstream-topic clickstream
```

## Outputs

- `thelook_clickstream.events_raw`
- `thelook_clickstream.events_deadletter`
- `thelook_clickstream.events_5m`
- `thelook_clickstream.session_metrics`
- `thelook_clickstream.v_session_funnel`
- `thelook_clickstream.v_daily_channel_kpis`
- `thelook_clickstream.v_product_interest`
