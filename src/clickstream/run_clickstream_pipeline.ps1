param(
  [string]$ProjectId = $env:GCP_PROJECT_ID,
  [string]$Region = $env:BQ_LOCATION,
  [string]$BucketName = $env:GCS_BUCKET_NAME,
  [string]$Subscription = "projects/$($env:GCP_PROJECT_ID)/subscriptions/clickstream-sub",
  [string]$Dataset = "thelook_clickstream",
  [string]$Table = "events_raw"
)

$ErrorActionPreference = "Stop"

if (-not $ProjectId) { throw "ProjectId is required. Set GCP_PROJECT_ID or pass -ProjectId." }
if (-not $Region) { $Region = "asia-southeast1" }
if (-not $BucketName) { throw "BucketName is required. Set GCS_BUCKET_NAME or pass -BucketName." }

python src/clickstream/dataflow_job.py `
  --project $ProjectId `
  --region $Region `
  --runner DataflowRunner `
  --temp_location "gs://$BucketName/dataflow/tmp" `
  --staging_location "gs://$BucketName/dataflow/staging" `
  --subscription $Subscription `
  --dataset $Dataset `
  --raw_table $Table
