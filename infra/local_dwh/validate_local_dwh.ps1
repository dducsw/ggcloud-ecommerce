param(
  [string]$ContainerName = "postgres-source",
  [string]$DbName = "thelook_db",
  [string]$DbUser = "db_user",
  [string]$SchemaName = "dwh_local"
)

$ErrorActionPreference = "Stop"

function Invoke-PsqlScalar {
  param([string]$Query)

  $output = docker exec $ContainerName psql -U $DbUser -d $DbName -t -A -c $Query
  if ($LASTEXITCODE -ne 0) {
    throw "psql query failed: $Query"
  }
  return ($output | Out-String).Trim()
}

function To-Int {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return 0 }
  return [int64]$Value
}

Write-Host "[Local DWH] Running data quality checks on schema '$SchemaName'..."

$checks = @(
  @{ Name = "fact_orders has rows"; Query = "select count(*) from $SchemaName.fact_orders"; Mode = "gt0" }
  @{ Name = "fact_order_items has rows"; Query = "select count(*) from $SchemaName.fact_order_items"; Mode = "gt0" }
  @{ Name = "fact_events has rows"; Query = "select count(*) from $SchemaName.fact_events"; Mode = "gt0" }

  @{ Name = "duplicate order_id in fact_orders"; Query = "select count(*) from (select order_id from $SchemaName.fact_orders group by order_id having count(*) > 1) t"; Mode = "zero" }
  @{ Name = "duplicate order_item_id in fact_order_items"; Query = "select count(*) from (select order_item_id from $SchemaName.fact_order_items group by order_item_id having count(*) > 1) t"; Mode = "zero" }
  @{ Name = "duplicate event_id in fact_events"; Query = "select count(*) from (select event_id from $SchemaName.fact_events group by event_id having count(*) > 1) t"; Mode = "zero" }

  @{ Name = "null keys in fact_orders"; Query = "select count(*) from $SchemaName.fact_orders where order_id is null or user_id is null"; Mode = "zero" }
  @{ Name = "null keys in fact_order_items"; Query = "select count(*) from $SchemaName.fact_order_items where order_item_id is null or order_id is null or user_id is null or product_id is null"; Mode = "zero" }
  @{ Name = "null keys in fact_events"; Query = "select count(*) from $SchemaName.fact_events where event_id is null or user_id is null"; Mode = "zero" }

  @{ Name = "orphan users in fact_orders"; Query = "select count(*) from $SchemaName.fact_orders f left join $SchemaName.dim_users d on f.user_id = d.user_id where d.user_id is null"; Mode = "zero" }
  @{ Name = "orphan users in fact_order_items"; Query = "select count(*) from $SchemaName.fact_order_items f left join $SchemaName.dim_users d on f.user_id = d.user_id where d.user_id is null"; Mode = "zero" }
  @{ Name = "orphan products in fact_order_items"; Query = "select count(*) from $SchemaName.fact_order_items f left join $SchemaName.dim_products d on f.product_id = d.product_id where d.product_id is null"; Mode = "zero" }

  @{ Name = "negative num_of_item in fact_orders"; Query = "select count(*) from $SchemaName.fact_orders where num_of_item < 0"; Mode = "zero" }
  @{ Name = "negative sale_price in fact_order_items"; Query = "select count(*) from $SchemaName.fact_order_items where sale_price < 0"; Mode = "zero" }
)

$failed = @()

foreach ($check in $checks) {
  $raw = Invoke-PsqlScalar -Query $check.Query
  $value = To-Int -Value $raw

  $isPass = $false
  if ($check.Mode -eq "zero") {
    $isPass = ($value -eq 0)
  } elseif ($check.Mode -eq "gt0") {
    $isPass = ($value -gt 0)
  }

  if ($isPass) {
    Write-Host "[PASS] $($check.Name): $value" -ForegroundColor Green
  } else {
    Write-Host "[FAIL] $($check.Name): $value" -ForegroundColor Red
    $failed += "$($check.Name) => $value"
  }
}

$latestOrderTs = Invoke-PsqlScalar -Query "select coalesce(max(created_at)::text, 'NULL') from $SchemaName.fact_orders"
$latestEventTs = Invoke-PsqlScalar -Query "select coalesce(max(created_at)::text, 'NULL') from $SchemaName.fact_events"
Write-Host "[INFO] latest fact_orders.created_at: $latestOrderTs"
Write-Host "[INFO] latest fact_events.created_at: $latestEventTs"

if ($failed.Count -gt 0) {
  Write-Host "`n[Local DWH] Validation FAILED." -ForegroundColor Red
  $failed | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
  exit 1
}

Write-Host "`n[Local DWH] Validation PASSED." -ForegroundColor Green
exit 0
