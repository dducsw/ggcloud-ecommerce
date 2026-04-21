# Clickstream Pipeline

Tài liệu này mô tả luồng clickstream hiện tại trong thư mục `src/clickstream`.

## Tổng quan

Luồng dữ liệu hiện tại:

```text
datagen -> Pub/Sub -> Dataflow -> BigQuery
```

Cụ thể:

1. `datagen/thelook-ecomm/generator.py` hoặc `datagen/thelook-ecomm/generate_events_only.py` sinh event clickstream.
2. `src/clickstream/event_publisher.py` publish event lên Pub/Sub topic clickstream.
3. `src/clickstream/dataflow_job.py` là entrypoint chạy Dataflow.
4. `src/clickstream/pipeline/pipeline.py` orchestration toàn bộ Beam pipeline.
5. Các transform chính nằm trong `src/clickstream/pipeline/transforms.py`.
6. Kết quả được ghi ra BigQuery.

## Các bảng và view đầu ra

Pipeline hiện tại sử dụng các bảng và view chính sau:

- `thelook_clickstream.events_raw`
- `thelook_clickstream.events_deadletter`
- `thelook_clickstream.events_5m`
- `thelook_clickstream.session_metrics`
- `thelook_clickstream.v_events_raw_dedup`
- `thelook_clickstream.v_events_5m_latest`
- `thelook_clickstream.v_session_metrics_latest`
- `thelook_clickstream.v_session_funnel`
- `thelook_clickstream.v_daily_channel_kpis`
- `thelook_clickstream.v_product_interest`

## Luồng chi tiết

### 1. ReadClickstreamPubSub

Pipeline đọc message từ Pub/Sub subscription clickstream.

Input ở bước này là message JSON thô.

### 2. ParseValidateDoFn

Transform này:

- parse JSON
- hỗ trợ cả 2 kiểu field:
  - `event_id` hoặc `id`
  - `event_timestamp` hoặc `created_at`
- chuẩn hóa dữ liệu thành schema nội bộ thống nhất
- kiểm tra các field bắt buộc:
  - `event_id/id`
  - `session_id`
  - `event_type`
  - `event_timestamp/created_at`

Nếu record lỗi:

- đưa sang nhánh dead-letter

Nếu record hợp lệ:

- gán `event_timestamp` làm event-time của Beam bằng `TimestampedValue`

### 3. Dead-letter

Những record lỗi được ghi vào:

- `events_deadletter`

Mục đích:

- không làm chết pipeline
- dễ kiểm tra chất lượng dữ liệu đầu vào

### 4. DeduplicateEventsDoFn

Pipeline key theo `event_id` rồi dùng Beam state + timer để dedup trong streaming.

Mục đích:

- tránh double-count khi message bị redelivery hoặc publish lặp

Lưu ý:

- đây là dedup trong runtime worker
- downstream vẫn có thêm lớp dedup bằng view BigQuery để an toàn hơn

### 5. Product lookup và enrichment

Pipeline enrich dữ liệu bằng `EnrichEventDoFn`.

Transform này:

- parse `uri` để suy ra:
  - `page_type`
  - `product_id`
- lookup thông tin product để enrich:
  - `product_category`
  - `product_department`
  - `product_name`
- bổ sung:
  - `is_conversion`
  - `processing_time`
  - `event_lag_seconds`

Hiện trạng product lookup:

- pipeline load product dimension từ BigQuery
- trong code hiện tại đang dùng `CreateInitialProductMap`, tức load một lần khi job khởi động
- có ghi chú trong `pipeline.py` rằng refresh định kỳ có thể bật lại trong Dataflow production, nhưng đang tắt để ổn định hơn khi test local

### 6. Write events_raw

Sau khi parse, validate, dedup và enrich, dữ liệu được ghi vào:

- `events_raw`

Đây là bảng raw chi tiết nhất của clickstream.

### 7. v_events_raw_dedup

Vì `events_raw` là append-only streaming table, downstream analytics dùng:

- `v_events_raw_dedup`

View này dedup theo `event_id` và lấy record mới nhất theo:

- `ingested_at DESC`
- `processing_time DESC`

Mục đích:

- giảm rủi ro duplicate nếu Beam state bị mất khi restart

## Nhánh aggregate 5 phút

### 8. Window5Minutes

Từ `enriched_events`, pipeline rẽ sang nhánh aggregate realtime.

Pipeline dùng:

- `FixedWindows(300)` tức cửa sổ 5 phút theo event-time

Hai nhánh `events_5m` và `session_metrics` cùng dùng chung một policy window:

- `allowed_lateness_seconds`
- `early_firing_delay_seconds`
- `late_firing_count`
- `ACCUMULATING`

Mục đích:

- nhất quán hành vi giữa aggregate 5 phút và session window

### 9. AggregateKey

Mỗi event được group theo:

- `event_date`
- `traffic_source`
- `browser`
- `event_type`
- `page_type`

### 10. GroupAggregateRows

Gom tất cả event cùng key trong cùng window lại.

### 11. create_aggregate_record

Transform này tính:

- `total_events`
- `unique_sessions`
- `unique_users`
- `purchase_events`
- `avg_event_lag_seconds`

Nó còn gắn:

- `window_start`
- `window_end`
- `aggregate_id`
- `version_emitted_at`

`aggregate_id` được tạo deterministically từ:

- `window_start`
- `event_date`
- `traffic_source`
- `browser`
- `event_type`
- `page_type`

Mục đích:

- cùng một window và cùng key sẽ có cùng `aggregate_id`

### 12. Write events_5m

Aggregate được ghi vào:

- `events_5m`

Vì dùng `ACCUMULATING`, cùng một window có thể có nhiều version nếu late event đến.

### 13. v_events_5m_latest

Dashboard và query downstream nên dùng:

- `v_events_5m_latest`

View này lấy version mới nhất theo:

- `aggregate_id`
- `version_emitted_at DESC`

Mục đích:

- tránh cộng đôi do nhiều version của cùng một aggregate window

## Nhánh session

### 14. KeyBySessionId

Từ `enriched_events`, pipeline chuyển thành:

- `(session_id, row)`

### 15. SessionWindow

Pipeline dùng:

- `beam.window.Sessions(session_gap_minutes * 60)`

Mặc định:

- gap là 30 phút

Ý nghĩa:

- nếu user im lặng quá 30 phút thì Beam coi đó là session mới

### 16. GroupSessionRows

Gom toàn bộ event trong cùng session sau khi Beam merge session window.

### 17. build_session_metric

Transform này tạo một record tổng hợp cho mỗi session:

- `session_record_id`
- `session_id`
- `session_start`
- `session_end`
- `session_duration_seconds`
- `event_count`
- `pageview_count`
- `product_view_count`
- `cart_count`
- `purchase_count`
- `saw_home`
- `saw_product`
- `added_to_cart`
- `purchased`
- `top_category`
- `session_date`
- `version_emitted_at`
- `processed_at`

`session_record_id` hiện được tạo từ:

- `session_id`
- `session_start`

Mục đích:

- version-safe cho cùng một session record khi late event làm session bị cập nhật lại

### 18. Write session_metrics

Kết quả được ghi vào:

- `session_metrics`

### 19. v_session_metrics_latest

Downstream analytics nên dùng:

- `v_session_metrics_latest`

View này lấy version mới nhất theo:

- `session_record_id`
- `version_emitted_at DESC`

### 20. v_session_funnel

View funnel session hiện đọc từ:

- `v_session_metrics_latest`

Mục đích:

- phân tích funnel trên session record mới nhất

## Các view business chính

### v_daily_channel_kpis

Nguồn:

- `v_events_raw_dedup`

Tính:

- tổng events theo ngày và traffic source
- total sessions distinct
- total users distinct
- purchase events
- purchase per session

### v_product_interest

Nguồn:

- `v_events_raw_dedup`

Tính:

- product views
- add-to-cart events
- purchase events

theo sản phẩm và ngày.

## Ghi chú quan trọng

- `events_raw` là bảng raw append-only
- `events_5m` và `session_metrics` là bảng aggregate có version
- downstream nên ưu tiên dùng các view latest/dedup để tránh double count
- session hiện chỉ dùng một cơ chế duy nhất là Beam Session Window
- product lookup hiện load một lần lúc job khởi động; phần refresh định kỳ đã được cân nhắc nhưng đang tắt trong code để ổn định hơn khi test local
