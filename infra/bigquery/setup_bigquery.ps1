param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [string]$Location = "US",
  [string]$BronzeDataset = "thelook_staging",
  [string]$GoldDataset = "thelook_datawarehouse",
  [string]$RawBucketPrefix = "gs://my-thelook-datalake/raw"
)

$ErrorActionPreference = "Stop"

function Ensure-Dataset {
  param([string]$Dataset)
  $datasetRef = "$ProjectId`:$Dataset"
  try {
    bq --project_id=$ProjectId ls --dataset_id $datasetRef | Out-Null
    Write-Host "Dataset already exists: $datasetRef"
  }
  catch {
    bq --project_id=$ProjectId --location=$Location mk --dataset $datasetRef | Out-Null
    Write-Host "Created dataset: $datasetRef"
  }
}

function Recreate-ExternalTable {
  param([string]$Table)

  $tableRef = "$ProjectId`:$BronzeDataset.$Table"
  # ** glob bao cover tat ca subdirectory (date=.../hour=...)
  $sourceUri = "$RawBucketPrefix/$Table/**"
  $hivePrefix = "$RawBucketPrefix/$Table/"

  try {
    bq --project_id=$ProjectId show $tableRef | Out-Null
    bq --project_id=$ProjectId rm -f -t $tableRef | Out-Null
  }
  catch {
    # Table does not exist yet.
  }

  $extDef = "AUTODETECT=TRUE,source_format=PARQUET,hive_partitioning_mode=AUTO,hive_partitioning_source_uri_prefix=$hivePrefix,uris=$sourceUri"
  bq --project_id=$ProjectId mk --table --external_table_definition=$extDef $tableRef | Out-Null
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
