output "gcs_bucket_url" {
  value       = google_storage_bucket.datalake.url
  description = "The URL of the created GCS bucket"
}

output "staging_dataset_id" {
  value       = google_bigquery_dataset.staging.dataset_id
  description = "The ID of the BigQuery staging dataset"
}

output "datawarehouse_dataset_id" {
  value       = google_bigquery_dataset.datawarehouse.dataset_id
  description = "The ID of the BigQuery data warehouse dataset"
}

output "pubsub_topic_id" {
  value       = google_pubsub_topic.cdc_topic.id
  description = "The ID of the Pub/Sub topic"
}

output "pubsub_subscription_id" {
  value       = google_pubsub_subscription.cdc_subscription.id
  description = "The ID of the Pub/Sub subscription"
}
