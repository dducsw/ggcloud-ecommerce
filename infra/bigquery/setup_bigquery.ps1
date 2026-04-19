param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [string]$Location = "US",
  [string]$BronzeDataset = "thelook_staging",
  [string]$GoldDataset = "thelook_datawarehouse",
  [string]$RawBucketPrefix = "gs://etl-staging-0/raw"
)

$ErrorActionPreference = "Stop"

function Ensure-Dataset {
  param([string]$Dataset)
  $datasetRef = "$ProjectId`:$Dataset"
  try {
    bq --project_id=$ProjectId ls --dataset_id $datasetRef | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to check dataset: $datasetRef" }
    Write-Host "Dataset already exists: $datasetRef"
  }
  catch {
    bq --project_id=$ProjectId --location=$Location mk --dataset $datasetRef | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to create dataset: $datasetRef" }
    Write-Host "Created dataset: $datasetRef"
  }
}

function Recreate-ExternalTable {
  param([string]$Table)

  $tableRef = "$ProjectId`:$BronzeDataset.$Table"
  # BigQuery external URI patterns do not support multiple '*' in a single URI.
  # Prefer new partition layout (date=...), fallback to legacy (window_end=...).
  $sourceUri = $null
  $hivePrefix = "$RawBucketPrefix/$Table/"
  $tmpDef = ".bq_extdef_$Table.tmp"
  $useHivePartitioning = $true

  gsutil ls "$RawBucketPrefix/$Table/date=*/" | Out-Null
  $hasDatePartition = ($LASTEXITCODE -eq 0)

  gsutil ls "$RawBucketPrefix/$Table/window_end=*/" | Out-Null
  $hasWindowEndPartition = ($LASTEXITCODE -eq 0)

  if ($hasDatePartition) {
    $sourceUri = "$RawBucketPrefix/$Table/date=*"
  }
  elseif ($hasWindowEndPartition) {
    $sourceUri = "$RawBucketPrefix/$Table/window_end=*"
  }
  else {
    # Fallback for distribution centers which may exist as a static file
    # instead of partitioned CDC output.
    if ($Table -eq "dist_centers") {
      $fallbackUri = "$RawBucketPrefix/distribution_centers.parquet"
      gsutil ls $fallbackUri | Out-Null
      if ($LASTEXITCODE -eq 0) {
        $sourceUri = $fallbackUri
        $useHivePartitioning = $false
      }
      else {
        Write-Warning "Skip external table ${tableRef}: no objects found under $RawBucketPrefix/$Table/ and fallback file $fallbackUri is missing."
        return
      }
    }
    else {
      Write-Warning "Skip external table ${tableRef}: no objects found under $RawBucketPrefix/$Table/."
      return
    }
  }

  try {
    bq --project_id=$ProjectId show $tableRef | Out-Null
    if ($LASTEXITCODE -eq 0) {
      bq --project_id=$ProjectId rm -f -t $tableRef | Out-Null
      if ($LASTEXITCODE -ne 0) { throw "Failed to drop table: $tableRef" }
    }
  }
  catch {
    # Table does not exist yet.
  }

  if ($useHivePartitioning) {
    bq mkdef --autodetect --source_format=PARQUET --hive_partitioning_mode=AUTO --hive_partitioning_source_uri_prefix=$hivePrefix $sourceUri | Out-File -FilePath $tmpDef -Encoding ascii
  }
  else {
    bq mkdef --autodetect --source_format=PARQUET $sourceUri | Out-File -FilePath $tmpDef -Encoding ascii
  }
  if ($LASTEXITCODE -ne 0) { throw "Failed to generate external table definition for: $tableRef" }

  bq --project_id=$ProjectId --location=$Location mk --table --external_table_definition=$tmpDef $tableRef | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Failed to create external table: $tableRef" }

  if (Test-Path $tmpDef) {
    Remove-Item $tmpDef -Force
  }

  Write-Host "Created external table: $tableRef -> $sourceUri  [hive partitioned: date/hour]"
}

Ensure-Dataset -Dataset $BronzeDataset
Ensure-Dataset -Dataset $GoldDataset

$externalTables = @(
  "users",
  "products",
  "dist_centers",
  "inventory_items",
  "order_items",
  "orders"
)

foreach ($table in $externalTables) {
  Recreate-ExternalTable -Table $table
}

Write-Host "[Step3] BigQuery setup complete."
