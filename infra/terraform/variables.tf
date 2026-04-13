variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "region" {
  description = "The GCP region to deploy resources"
  type        = string
  default     = "asia-southeast1"
}

variable "gcs_bucket_name" {
  description = "The name of the GCS bucket for the Data Lakehouse"
  type        = string
}

variable "bq_dataset_staging" {
  description = "The BigQuery dataset ID for the staging layer"
  type        = string
  default     = "staging"
}

variable "bq_dataset_datawarehouse" {
  description = "The BigQuery dataset ID for the data warehouse layer"
  type        = string
  default     = "datawarehouse"
}

variable "pubsub_topic_name" {
  description = "The name of the Pub/Sub topic for CDC events"
  type        = string
  default     = "thelook-cdc-events"
}

variable "pubsub_subscription_name" {
  description = "The name of the Pub/Sub subscription for CDC events"
  type        = string
  default     = "thelook-cdc-events-sub"
}
