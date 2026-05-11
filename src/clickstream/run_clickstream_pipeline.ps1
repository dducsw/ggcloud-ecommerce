param(
  [string]$ProjectId = $env:GCP_PROJECT_ID,
  [string]$Region = $env:BQ_LOCATION,
  [string]$BucketName = $env:GCS_BUCKET_NAME,
  [string]$Subscription,
  [ValidateSet("DirectRunner", "DataflowRunner")]
  [string]$Runner = "DirectRunner",
  [string]$JobName = "clickstream-processing-v1",
  [string]$Dataset = "thelook_clickstream",
  [string]$Table = "events_raw",
  [string]$ProductLookupDataset = "thelook_datawarehouse",
  [string]$ProductLookupTable = "dim_products",
  [int]$MaxWorkers = 5,
  [string]$MachineType = "n1-standard-2",
  [int]$DirectNumWorkers = 4,
  [ValidateSet("in_memory", "multi_threading", "multi_processing")]
  [string]$DirectRunningMode = "multi_threading",
  [int]$DedupTtlMinutes = 60,
  [int]$SessionGapMinutes = 30,
  [int]$AllowedLatenessSeconds = 600,
  [int]$EarlyFiringDelaySeconds = 60,
  [int]$LateFiringCount = 1,
  [switch]$UsePublicIps,
  [switch]$Init
)

$ErrorActionPreference = "Stop"

if (-not $ProjectId) { throw "ProjectId is required. Set GCP_PROJECT_ID or pass -ProjectId." }
if (-not $Region) { $Region = "asia-east1" }
if (-not $BucketName) { throw "BucketName is required. Set GCS_BUCKET_NAME or pass -BucketName." }

$BucketUri = $BucketName
if (-not $BucketUri.StartsWith("gs://")) {
  $BucketUri = "gs://$BucketUri"
}

if (-not $Subscription) {
    $Subscription = "projects/$ProjectId/subscriptions/clickstream_topic-sub"
}

if ($Init) {
  Write-Host "Initializing infrastructure..." -ForegroundColor Cyan
  $env:PYTHONPATH = "."
  python src/clickstream/init_infra.py --project $ProjectId --dataset $Dataset --location $Region
}

$env:PYTHONPATH = "."
Write-Host "Starting Clickstream Pipeline..." -ForegroundColor Cyan
Write-Host "Runner: $Runner" -ForegroundColor Yellow
if ($Runner -eq "DataflowRunner") {
    Write-Host "Job Name: $JobName" -ForegroundColor DarkCyan
    Write-Host "Max Workers: $MaxWorkers, Machine Type: $MachineType" -ForegroundColor DarkCyan
} else {
    Write-Host "Mode: $DirectRunningMode, Local Workers: $DirectNumWorkers" -ForegroundColor DarkCyan
}

python src/clickstream/dataflow_job.py `
  --project $ProjectId `
  --region $Region `
  --runner $Runner `
  --job_name $JobName `
  --temp_location "$BucketUri/dataflow/tmp" `
  --staging_location "$BucketUri/dataflow/staging" `
  --max_workers $MaxWorkers `
  --worker_machine_type $MachineType `
  --events_subscription $Subscription `
  --dataset $Dataset `
  --raw_table $Table `
  --product_lookup_dataset $ProductLookupDataset `
  --product_lookup_table $ProductLookupTable `
  --dedup_ttl_minutes $DedupTtlMinutes `
  --session_gap_minutes $SessionGapMinutes `
  --allowed_lateness_seconds $AllowedLatenessSeconds `
  --early_firing_delay_seconds $EarlyFiringDelaySeconds `
  --late_firing_count $LateFiringCount `
  --direct_running_mode $DirectRunningMode `
  --direct_num_workers $DirectNumWorkers

