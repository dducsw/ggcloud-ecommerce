param(
  [string]$ProjectId = $env:GCP_PROJECT_ID,
  [string]$Region = $env:BQ_LOCATION,
  [string]$BucketName = $env:GCS_BUCKET_NAME,
  [string]$Subscription = "projects/$($env:GCP_PROJECT_ID)/subscriptions/clickstream_topic-sub",
  [string]$Dataset = "thelook_clickstream",
  [string]$Table = "events_raw",
  [int]$DedupTtlMinutes = 60,
  [int]$SessionGapMinutes = 30,
  [int]$AllowedLatenessSeconds = 600,
  [int]$EarlyFiringDelaySeconds = 60,
  [int]$LateFiringCount = 1,
  [switch]$Init
)

$ErrorActionPreference = "Stop"

if (-not $ProjectId) { throw "ProjectId is required. Set GCP_PROJECT_ID or pass -ProjectId." }
if (-not $Region) { $Region = "asia-southeast1" }
if (-not $BucketName) { throw "BucketName is required. Set GCS_BUCKET_NAME or pass -BucketName." }

if ($Init) {
  Write-Host "Initializing infrastructure..." -ForegroundColor Cyan
  python src/clickstream/init_infra.py --project $ProjectId --dataset $Dataset --location $Region
}

python src/clickstream/dataflow_job.py `
  --project $ProjectId `
  --region $Region `
  --runner DataflowRunner `
  --temp_location "gs://$BucketName/dataflow/tmp" `
  --staging_location "gs://$BucketName/dataflow/staging" `
  --events_subscription $Subscription `
  --dataset $Dataset `
  --raw_table $Table `
  --dedup_ttl_minutes $DedupTtlMinutes `
  --session_gap_minutes $SessionGapMinutes `
  --allowed_lateness_seconds $AllowedLatenessSeconds `
  --early_firing_delay_seconds $EarlyFiringDelaySeconds `
  --late_firing_count $LateFiringCount
