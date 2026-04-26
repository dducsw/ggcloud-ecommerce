param(
  [string]$ComposeFile = "docker-compose.yaml",
  [string]$ProjectId = "cloud-data-project-492514"
)

$ErrorActionPreference = "Stop"

Write-Host "[Step1] Starting Postgres + Debezium Server..."
docker compose -f $ComposeFile up -d postgres-source debezium-server
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up failed. Check: docker compose -f $ComposeFile ps and logs debezium-server"
}

Write-Host "[Step1] Ensuring Pub/Sub topics/subscriptions for Debezium Server..."
python src/etl/debezium_incremental.py --project-id $ProjectId
if ($LASTEXITCODE -ne 0) {
  throw "Failed to prepare Debezium Server incremental CDC flow."
}

Write-Host "[Step1] Done."
Write-Host "Check logs: docker compose -f $ComposeFile logs -f debezium-server"
