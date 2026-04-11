param(
  [string]$DbHost = "localhost",
  [int]$Port = 5433,
  [string]$Database = "thelook_db",
  [string]$User = "db_user",
  [string]$Password = "db_password",
  [string]$SourceSchema = "demo",
  [string]$TargetSchema = "dwh_local",
  [switch]$Reset,
  [switch]$DropOnly
)

$ErrorActionPreference = "Stop"

$args = @(
  "src/local_dwh/build_postgres_dwh.py",
  "--host", $DbHost,
  "--port", $Port,
  "--database", $Database,
  "--user", $User,
  "--password", $Password,
  "--source-schema", $SourceSchema,
  "--target-schema", $TargetSchema
)

if ($Reset) {
  $args += "--reset"
}

if ($DropOnly) {
  $args += "--drop-only"
}

Write-Host "[Local DWH] Running PostgreSQL warehouse build..."
python @args
if ($LASTEXITCODE -ne 0) {
  throw "Local DWH build failed"
}

Write-Host "[Local DWH] Done."
