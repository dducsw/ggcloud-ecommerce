param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [string]$Location = "asia-southeast1",
  [string]$Dataset = "thelook_clickstream"
)

$ErrorActionPreference = "Stop"

function Invoke-BqQuery {
  param([string]$Query)
  bq --project_id=$ProjectId --location=$Location query --use_legacy_sql=false $Query | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "BigQuery query failed." }
}

try {
  bq --project_id=$ProjectId ls --dataset_id "$ProjectId`:$Dataset" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Dataset check failed." }
  Write-Host "Dataset already exists: $ProjectId`:$Dataset"
}
catch {
  bq --project_id=$ProjectId --location=$Location mk --dataset "$ProjectId`:$Dataset" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Failed to create dataset." }
  Write-Host "Created dataset: $ProjectId`:$Dataset"
}

Invoke-BqQuery @"
CREATE TABLE IF NOT EXISTS `$ProjectId.$Dataset.events_raw` (
  event_id INT64 NOT NULL,
  user_id INT64,
  sequence_number INT64,
  session_id STRING,
  ip_address STRING,
  city STRING,
  state STRING,
  postal_code STRING,
  browser STRING,
  traffic_source STRING,
  uri STRING,
  event_type STRING,
  event_timestamp TIMESTAMP NOT NULL,
  event_date DATE NOT NULL,
  ingested_at TIMESTAMP NOT NULL,
  page_type STRING,
  product_id INT64,
  product_category STRING,
  product_department STRING,
  product_name STRING,
  is_conversion BOOL NOT NULL,
  processing_time TIMESTAMP NOT NULL,
  event_lag_seconds FLOAT64
)
PARTITION BY event_date
CLUSTER BY event_type, traffic_source, browser;
"@

Invoke-BqQuery @"
CREATE TABLE IF NOT EXISTS `$ProjectId.$Dataset.events_deadletter` (
  raw_message STRING,
  error_message STRING NOT NULL,
  failed_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(failed_at);
"@

Invoke-BqQuery @"
CREATE TABLE IF NOT EXISTS `$ProjectId.$Dataset.events_5m` (
  aggregate_id STRING NOT NULL,
  window_start TIMESTAMP NOT NULL,
  window_end TIMESTAMP NOT NULL,
  event_date DATE NOT NULL,
  traffic_source STRING,
  browser STRING,
  event_type STRING,
  page_type STRING,
  total_events INT64 NOT NULL,
  unique_sessions INT64 NOT NULL,
  unique_users INT64 NOT NULL,
  purchase_events INT64 NOT NULL,
  avg_event_lag_seconds FLOAT64,
  version_emitted_at TIMESTAMP NOT NULL
)
PARTITION BY event_date
CLUSTER BY aggregate_id, traffic_source, event_type, page_type;
"@

Invoke-BqQuery @"
CREATE OR REPLACE VIEW `$ProjectId.$Dataset.v_events_5m_latest` AS
SELECT
  aggregate_id,
  window_start,
  window_end,
  event_date,
  traffic_source,
  browser,
  event_type,
  page_type,
  total_events,
  unique_sessions,
  unique_users,
  purchase_events,
  avg_event_lag_seconds,
  version_emitted_at
FROM `$ProjectId.$Dataset.events_5m`
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY aggregate_id
  ORDER BY version_emitted_at DESC
) = 1;
"@

Invoke-BqQuery @"
CREATE TABLE IF NOT EXISTS `$ProjectId.$Dataset.session_metrics` (
  session_record_id STRING NOT NULL,
  session_id STRING NOT NULL,
  user_id INT64,
  traffic_source STRING,
  browser STRING,
  session_start TIMESTAMP NOT NULL,
  session_end TIMESTAMP NOT NULL,
  session_duration_seconds FLOAT64 NOT NULL,
  event_count INT64 NOT NULL,
  pageview_count INT64 NOT NULL,
  product_view_count INT64 NOT NULL,
  cart_count INT64 NOT NULL,
  purchase_count INT64 NOT NULL,
  saw_home BOOL NOT NULL,
  saw_product BOOL NOT NULL,
  added_to_cart BOOL NOT NULL,
  purchased BOOL NOT NULL,
  top_category STRING,
  session_date DATE NOT NULL,
  version_emitted_at TIMESTAMP NOT NULL,
  processed_at TIMESTAMP NOT NULL
)
PARTITION BY session_date
CLUSTER BY session_record_id, traffic_source, browser, purchased;
"@

Invoke-BqQuery @"
CREATE OR REPLACE VIEW `$ProjectId.$Dataset.v_events_raw_dedup` AS
SELECT
  event_id,
  user_id,
  sequence_number,
  session_id,
  ip_address,
  city,
  state,
  postal_code,
  browser,
  traffic_source,
  uri,
  event_type,
  event_timestamp,
  event_date,
  ingested_at,
  page_type,
  product_id,
  product_category,
  product_department,
  product_name,
  is_conversion,
  processing_time,
  event_lag_seconds
FROM `$ProjectId.$Dataset.events_raw`
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY event_id
  ORDER BY ingested_at DESC, processing_time DESC
) = 1;
"@

Invoke-BqQuery @"
CREATE OR REPLACE VIEW `$ProjectId.$Dataset.v_session_metrics_latest` AS
SELECT
  session_record_id,
  session_id,
  user_id,
  traffic_source,
  browser,
  session_start,
  session_end,
  session_duration_seconds,
  event_count,
  pageview_count,
  product_view_count,
  cart_count,
  purchase_count,
  saw_home,
  saw_product,
  added_to_cart,
  purchased,
  top_category,
  session_date,
  version_emitted_at,
  processed_at
FROM `$ProjectId.$Dataset.session_metrics`
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY session_record_id
  ORDER BY version_emitted_at DESC
) = 1;
"@

Invoke-BqQuery @"
CREATE OR REPLACE VIEW `$ProjectId.$Dataset.v_session_funnel` AS
SELECT
  session_id,
  user_id,
  traffic_source,
  browser,
  session_start AS session_started_at,
  saw_home,
  saw_product,
  added_to_cart,
  purchased,
  session_duration_seconds,
  event_count,
  top_category
FROM `$ProjectId.$Dataset.v_session_metrics_latest`;
"@

Invoke-BqQuery @"
CREATE OR REPLACE VIEW `$ProjectId.$Dataset.v_daily_channel_kpis` AS
SELECT
  event_date,
  traffic_source,
  COUNT(*) AS total_events,
  COUNT(DISTINCT session_id) AS total_sessions,
  COUNT(DISTINCT user_id) AS total_users,
  COUNTIF(event_type = 'purchase') AS purchase_events,
  SAFE_DIVIDE(COUNTIF(event_type = 'purchase'), COUNT(DISTINCT session_id)) AS purchase_per_session
FROM `$ProjectId.$Dataset.v_events_raw_dedup`
GROUP BY event_date, traffic_source;
"@

Invoke-BqQuery @"
CREATE OR REPLACE VIEW `$ProjectId.$Dataset.v_product_interest` AS
SELECT
  event_date,
  product_id,
  product_name,
  product_category,
  product_department,
  COUNTIF(event_type = 'product') AS product_views,
  COUNTIF(event_type = 'cart') AS add_to_cart_events,
  COUNTIF(event_type = 'purchase') AS purchase_events
FROM `$ProjectId.$Dataset.v_events_raw_dedup`
WHERE product_id IS NOT NULL
GROUP BY event_date, product_id, product_name, product_category, product_department;
"@

Write-Host "Created objects: events_raw, events_deadletter, events_5m, session_metrics, latest-safe views."

Write-Host "[Clickstream] BigQuery setup complete."
