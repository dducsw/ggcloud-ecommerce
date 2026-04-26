# Clickstream Pipeline

Tài liệu này mô tả luồng clickstream hiện tại trong `src/clickstream` sau đợt review gần nhất.

## Tổng Quan

Luồng dữ liệu:

```text
datagen -> Pub/Sub -> Dataflow / Apache Beam -> BigQuery
```

Các thành phần chính:

- `datagen/thelook-ecomm/generator.py` hoặc `datagen/thelook-ecomm/generate_events_only.py` sinh event clickstream.
- `src/clickstream/event_publisher.py` publish event lên Pub/Sub topic.
- `src/clickstream/dataflow_job.py` là entrypoint chạy Beam/Dataflow job.
- `src/clickstream/pipeline/pipeline.py` orchestration toàn bộ pipeline.
- `src/clickstream/pipeline/transforms.py` chứa các transform xử lý dữ liệu chính.
- `src/clickstream/init_infra.py` tạo BigQuery tables/views và Pub/Sub resources.

## Output Tables Và Views

Pipeline ghi và phục vụ dữ liệu qua các bảng/view chính:

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

## Luồng Chi Tiết

### 1. ReadClickstreamPubSub

Pipeline đọc message JSON thô từ Pub/Sub subscription qua `beam.io.ReadFromPubSub(subscription=args.events_subscription)`.

Lưu ý vận hành:

- Script `run_clickstream_pipeline.ps1` phải truyền đúng flag `--events_subscription`.
- Subscription mặc định trong script là `projects/<project>/subscriptions/clickstream_topic-sub`.

### 2. ParseValidateDoFn

`ParseValidateDoFn` thực hiện:

- Decode message bytes thành UTF-8.
- Parse JSON.
- Hỗ trợ alias field `event_id` hoặc `id`.
- Hỗ trợ alias timestamp `event_timestamp` hoặc `created_at`.
- Chuẩn hóa timestamp về UTC string.
- Validate `event_type` theo contract hiện tại của datagen.
- Gán Beam event-time bằng `TimestampedValue`.

Các field bắt buộc:

- `event_id` hoặc `id`
- `session_id`
- `event_type`
- `event_timestamp` hoặc `created_at`
- `ingested_at`, mặc định lấy theo event timestamp nếu input không có

Các `event_type` hợp lệ hiện tại:

- `home`
- `department`
- `category`
- `product`
- `cart`
- `purchase`
- `cancel`
- `return`

Record lỗi được đưa sang dead-letter thay vì làm chết pipeline.

### 3. Dead-Letter

Record lỗi được ghi vào `events_deadletter` với:

- `raw_message`
- `error_message`
- `failed_at`

Mục đích là giữ pipeline chạy ổn định và có nơi kiểm tra chất lượng dữ liệu đầu vào.

### 4. DeduplicateEventsDoFn

Pipeline key theo `event_id`, sau đó dùng Beam user state và watermark timer để dedup trong runtime.

Cơ chế:

- Nếu `event_id` chưa thấy trong state, ghi state và emit record.
- Nếu `event_id` đã thấy, tăng metric `duplicate_events` và bỏ qua.
- State được clear sau `dedup_ttl_minutes`.

Đánh giá:

- Cách này giảm duplicate do Pub/Sub redelivery hoặc publisher gửi lặp.
- Đây không phải bảo đảm exactly-once tuyệt đối, vì state có thể mất khi job restart hoặc duplicate đến ngoài TTL.
- Vì vậy downstream vẫn nên dùng `v_events_raw_dedup` thay vì đọc trực tiếp `events_raw` cho analytics.

### 5. Product Lookup Và Enrichment

`EnrichEventDoFn` bổ sung thông tin derived/enriched:

- Parse `uri` thành `page_type`.
- Parse `product_id` nếu URI là trang product.
- Lookup product snapshot để lấy `product_category`, `product_department`, `product_name`.
- Tính `is_conversion`.
- Gắn `processing_time`.
- Tính `event_lag_seconds`.

Product lookup hiện là snapshot có chủ đích:

- Pipeline gọi `load_product_dimension(...)` khi job khởi động.
- Product map được đưa vào Beam side input bằng `CreateInitialProductMap`.
- Không có refresh định kỳ trong job đang chạy.
- Nếu product dimension thay đổi và cần phản ánh vào clickstream enrichment, restart Dataflow job để nạp snapshot mới.
- Nếu load từ BigQuery lỗi và có `products_csv`, pipeline log warning rồi fallback sang CSV.

Đánh giá:

- Snapshot lookup giúp enrichment ổn định, đơn giản và dễ debug.
- Trade-off là product metadata có thể stale cho đến lần restart job tiếp theo.
- Đây là lựa chọn phù hợp hiện tại vì yêu cầu đã xác nhận chưa cần refresh định kỳ.

### 6. Write events_raw

Sau parse, validate, dedup và enrich, record được ghi append-only vào `events_raw`.

Đặc điểm:

- Partition theo `event_date`.
- Cluster theo `event_type`, `traffic_source`, `browser`.
- Ghi bằng BigQuery streaming inserts.

Khuyến nghị sử dụng:

- `events_raw` là bảng lưu chi tiết và có tính append-only.
- Dashboard/query nghiệp vụ nên đọc `v_events_raw_dedup` để tránh double count nếu duplicate lọt qua runtime dedup.

### 7. v_events_raw_dedup

View này dedup theo `event_id`:

```sql
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY event_id
  ORDER BY ingested_at DESC, processing_time DESC
) = 1
```

Mục đích:

- Bù cho các trường hợp duplicate vẫn lọt vào bảng raw.
- Tạo serving layer an toàn hơn cho analytics.

## Nhánh Aggregate 5 Phút

### 8. Window5Minutes

Từ `enriched_events`, pipeline rẽ sang nhánh aggregate realtime và dùng:

- `FixedWindows(300)` theo event-time.
- `allowed_lateness_seconds`.
- Early firing bằng `AfterProcessingTime`.
- Late firing bằng `AfterCount`.
- `ACCUMULATING` mode.

Đánh giá:

- Cách này cho dashboard có kết quả sớm.
- Khi late event đến, cùng một aggregate window có thể phát thêm version mới.
- Vì vậy downstream cần dùng view latest.

### 9. AggregateKey

Aggregate key gồm:

- `event_date`
- `traffic_source`
- `browser`
- `event_type`
- `page_type`

### 10. create_aggregate_record

Transform này tính:

- `total_events`
- `unique_sessions`
- `unique_users`
- `purchase_events`
- `avg_event_lag_seconds`
- `version_emitted_at`

`aggregate_id` được tạo từ:

- `window_start`
- `event_date`
- `traffic_source`
- `browser`
- `event_type`
- `page_type`

Mục đích là cùng một window và cùng một aggregate key sẽ có cùng `aggregate_id`, kể cả khi có nhiều emitted versions.

### 11. Write events_5m

Aggregate được ghi append vào `events_5m`.

Do dùng `ACCUMULATING`, bảng này có thể chứa nhiều version cho cùng một `aggregate_id`.

### 12. v_events_5m_latest

Dashboard nên dùng `v_events_5m_latest`.

View này lấy version mới nhất theo:

- `aggregate_id`
- `version_emitted_at DESC`

Mục đích là tránh cộng đôi nhiều version của cùng một aggregate window.

## Nhánh Session

### 13. KeyBySessionId

Từ `enriched_events`, pipeline chuyển record thành:

```text
(session_id, row)
```

### 14. SessionWindow

Pipeline dùng Beam session window:

```python
beam.window.Sessions(args.session_gap_minutes * 60)
```

Mặc định `session_gap_minutes = 30`.

Ý nghĩa:

- Nếu cùng `session_id` không có event mới trong 30 phút, Beam coi session window đã kết thúc.
- Nếu late event đến trong allowed lateness, Beam có thể cập nhật lại session metric.

### 15. build_session_metric

Transform này gom event trong session, sort theo `event_timestamp`, rồi tạo một record tổng hợp.

Các metric chính:

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

Lý do:

- `session_start` có thể thay đổi khi late event đến sớm hơn event đầu tiên đã thấy trước đó.
- Nếu dùng `session_id + session_start`, cùng một session logic có thể sinh nhiều identity key khác nhau.
- Dùng `session_id` giúp latest view chọn đúng version mới nhất cho cùng một session.

Các flag funnel:

- `saw_home` dựa trên `page_type == "home"`.
- `saw_product` dựa trên `page_type == "product"`.

Lý do:

- `page_type` mô tả user đang ở loại trang nào.
- `event_type` mô tả hành động hoặc loại event.
- Với câu hỏi "session đã thấy home/product page chưa", dùng `page_type` đúng ngữ nghĩa hơn.

### 16. Write session_metrics

Session metrics được ghi append vào `session_metrics`.

Do session window dùng accumulating panes, bảng này có thể chứa nhiều version cho cùng một `session_id`.

### 17. v_session_metrics_latest

Downstream analytics nên dùng `v_session_metrics_latest`.

View này lấy version mới nhất theo:

- `session_id`
- `version_emitted_at DESC`

Mục đích là tránh double count khi cùng một session được emit nhiều lần do early/late firing.

### 18. v_session_funnel

`v_session_funnel` đọc từ `v_session_metrics_latest`.

Mục đích:

- Phân tích funnel trên session record mới nhất.
- Tránh dùng trực tiếp bảng append-only `session_metrics`.

## Business Views

### v_daily_channel_kpis

Nguồn:

- `v_events_raw_dedup`

Tính:

- Tổng events theo ngày và traffic source.
- Tổng sessions distinct.
- Tổng users distinct.
- Purchase events.
- Purchase per session.

### v_product_interest

Nguồn:

- `v_events_raw_dedup`

Tính theo ngày và product:

- Product views bằng `COUNTIF(page_type = 'product')`.
- Add-to-cart events.
- Purchase events.

## Đánh Giá Sau Review

Các điểm đã cải thiện:

- Script chạy Dataflow đã dùng đúng flag `--events_subscription`.
- Script chạy Dataflow expose các tham số tuning chính: dedup TTL, session gap, allowed lateness, early firing delay, late firing count.
- Product lookup đã được xác nhận là snapshot và code đã dọn phần refresh định kỳ không dùng.
- Product lookup fallback sang CSV có warning log để dễ debug lỗi BigQuery permission/table.
- `session_record_id` ổn định hơn vì không còn phụ thuộc `session_start`.
- `v_session_metrics_latest` lấy latest theo `session_id`, khớp với logic session key mới.
- `saw_home` và `saw_product` dùng `page_type`, nhất quán với `pageview_count` và `product_view_count`.
- `v_product_interest` dùng `page_type = 'product'` cho product views, đúng ngữ nghĩa page classification.
- `build_session_metric` có guard cap 5000 events/session để giảm rủi ro session bất thường làm worker tốn memory.
- `version_emitted_at` và `processed_at` trong session metric dùng cùng một timestamp.
- Pub/Sub subscription mới tạo dùng `ack_deadline_seconds = 600` để phù hợp hơn với Dataflow streaming.
- Publisher giữ `publish()` đồng bộ để tương thích, đồng thời có thêm `publish_async()` và `publish_batch()` cho luồng publish throughput cao hơn.

Các rủi ro còn lại:

- `events_raw`, `events_5m`, và `session_metrics` vẫn là append-oriented tables; đọc trực tiếp các bảng này có thể double count.
- BigQuery streaming inserts không tự đảm bảo dedup tuyệt đối cho mọi tình huống restart/redelivery.
- Product metadata có thể stale cho đến khi restart Dataflow job.
- `build_session_metric` vẫn cần materialize session trước khi cap, vì pipeline hiện dùng `GroupByKey`.
- Dedup TTL đang dùng watermark timer; nếu watermark bị giữ bởi late data nhiều, state cleanup có thể trễ hơn wall-clock TTL.
- `publish()` đơn lẻ vẫn chờ `future.result()`; dùng `publish_batch()` hoặc `publish_async()` khi cần throughput cao.

Khuyến nghị vận hành:

- Dashboard và marts nên dùng các view latest/dedup.
- Theo dõi Beam metrics `valid_events`, `invalid_events`, `duplicate_events`.
- Theo dõi số lượng record trong `events_deadletter`.
- Tune `dedup_ttl_minutes`, `allowed_lateness_seconds`, và `session_gap_minutes` dựa trên dữ liệu thực tế.
- Restart Dataflow job có kiểm soát khi cần cập nhật product dimension snapshot.
