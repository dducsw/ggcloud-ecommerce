param(
  [string]$ComposeFile = "docker-compose.yaml",
  [string]$ConnectorConfig = "infra/cdc/connectors/debezium-connector.json",
  [string]$ConnectUrl = "http://localhost:8083"
)

$ErrorActionPreference = "Stop"

Write-Host "[Step1] Starting Postgres + Kafka + Debezium + Datagen..."
docker compose -f $ComposeFile up -d postgres-source kafka debezium-cdc datagen
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up failed. Check: docker compose -f $ComposeFile ps and logs kafka/debezium-cdc"
}
if ($LASTEXITCODE -ne 0) {
  throw "docker compose failed to start services."
}

Write-Host "[Step1] Waiting for Debezium REST API..."
$maxAttempts = 30
for ($i = 1; $i -le $maxAttempts; $i++) {
  try {
    $null = Invoke-RestMethod -Uri "$ConnectUrl/connectors" -Method Get -TimeoutSec 3
    Write-Host "Debezium is ready."
    break
  }
  catch {
    if ($i -eq $maxAttempts) {
      throw "Debezium is not ready after $maxAttempts attempts."
    }
    Start-Sleep -Seconds 2
  }
}

Write-Host "[Step1] Registering Debezium connector..."
python src/cdc/register_debezium_connector.py --connect-url $ConnectUrl --config-path $ConnectorConfig
if ($LASTEXITCODE -ne 0) {
  throw "Failed to register Debezium connector."
}

Write-Host "[Step1] Done."
Write-Host "Check connector status: $ConnectUrl/connectors/thelook-postgres-source/status"
