# Google Cloud Storage Bucket (Data Lakehouse)
resource "google_storage_bucket" "datalake" {
  name                        = var.gcs_bucket_name
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

# BigQuery Staging Dataset
resource "google_bigquery_dataset" "staging" {
  dataset_id                  = var.bq_dataset_staging
  location                    = var.region
  description                 = "Staging layer for external tables pointing to GCS"
  delete_contents_on_destroy  = true
}

# BigQuery Data Warehouse Dataset
resource "google_bigquery_dataset" "datawarehouse" {
  dataset_id                  = var.bq_dataset_datawarehouse
  location                    = var.region
  description                 = "Data warehouse layer for processed data"
  delete_contents_on_destroy  = true
}

# Pub/Sub Topic for CDC events
resource "google_pubsub_topic" "cdc_topic" {
  name = var.pubsub_topic_name
}

# Pub/Sub Subscription for CDC events
resource "google_pubsub_subscription" "cdc_subscription" {
  name  = var.pubsub_subscription_name
  topic = google_pubsub_topic.cdc_topic.name

  ack_deadline_seconds = 20
}

# Example External Table (How dbt reads from GCS)
# Bạn có thể uncomment và chỉnh sửa đoạn này sau khi có dữ liệu trên GCS
/*
resource "google_bigquery_table" "external_example" {
  dataset_id = google_bigquery_dataset.staging.dataset_id
  table_id   = "external_table_name"

  external_data_configuration {
    autodetect    = true
    source_format = "PARQUET"
    source_uris   = ["gs://${google_storage_bucket.datalake.name}/raw/*.parquet"]
  }
}
*/

# --- Debezium Server Authentication ---

# 1. Tạo Service Account riêng cho Debezium Server
resource "google_service_account" "debezium_sa" {
  account_id   = "debezium-server-sa"
  display_name = "Service Account for Debezium Server"
}

# 2. Cấp quyền Pub/Sub Publisher cho Service Account này
resource "google_project_iam_member" "pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.debezium_sa.email}"
}

# 3. Tạo Key cho Service Account
resource "google_service_account_key" "debezium_sa_key" {
  service_account_id = google_service_account.debezium_sa.name
}

# 4. Lưu Key ra file local để Debezium Server trong Docker có thể dùng
resource "local_file" "gcp_key" {
  content  = base64decode(google_service_account_key.debezium_sa_key.private_key)
  filename = "${path.module}/../../credentials/gcp-key.json"
}
