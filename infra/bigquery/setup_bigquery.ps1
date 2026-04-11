param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [string]$Location = "US",
  [string]$BronzeDataset = "thelook_bronze",
  [string]$GoldDataset = "thelook_gold",
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
  $sourceUri = "$RawBucketPrefix/$Table/*.parquet"

  try {
    bq --project_id=$ProjectId show $tableRef | Out-Null
    bq --project_id=$ProjectId rm -f -t $tableRef | Out-Null
  }
  catch {
    # Table does not exist yet.
  }

  bq --project_id=$ProjectId mk --table --external_table_definition="AUTODETECT=TRUE,source_format=PARQUET,uris=$sourceUri" $tableRef | Out-Null
  Write-Host "Created external table: $tableRef -> $sourceUri"
}

Ensure-Dataset -Dataset $BronzeDataset
Ensure-Dataset -Dataset $GoldDataset

Recreate-ExternalTable -Table "users"
Recreate-ExternalTable -Table "products"
Recreate-ExternalTable -Table "dist_centers"

Write-Host "[Step3] BigQuery setup complete."
