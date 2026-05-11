param(
  [string]$ProjectId  = $env:GCP_PROJECT_ID,
  [string]$Region     = "asia-east1",
  [string]$ServiceName = "thelook-dashboard",
  [string]$ImageTag   = "latest",
  [int]$Memory        = 512,   # MB
  [int]$Cpu           = 1,
  [int]$MaxInstances  = 2,
  [int]$MinInstances  = 0,     # scale-to-zero khi không có traffic
  [switch]$AllowUnauthenticated
)

$ErrorActionPreference = "Stop"

if (-not $ProjectId) { throw "ProjectId is required. Set GCP_PROJECT_ID or pass -ProjectId." }

$ImageUri = "gcr.io/$ProjectId/$ServiceName`:$ImageTag"
$DashboardDir = "$PSScriptRoot"

Write-Host "=== Cloud Run Deploy: $ServiceName ===" -ForegroundColor Cyan
Write-Host "Project : $ProjectId"    -ForegroundColor DarkGray
Write-Host "Region  : $Region"       -ForegroundColor DarkGray
Write-Host "Image   : $ImageUri"     -ForegroundColor DarkGray
Write-Host ""

# --- Step 1: Build Docker image ---
Write-Host "[1/3] Building Docker image..." -ForegroundColor Yellow
docker build -t $ImageUri $DashboardDir
if ($LASTEXITCODE -ne 0) { throw "Docker build failed." }

# --- Step 2: Push to Google Container Registry ---
Write-Host "[2/3] Pushing image to GCR..." -ForegroundColor Yellow
docker push $ImageUri
if ($LASTEXITCODE -ne 0) { throw "Docker push failed. Run: gcloud auth configure-docker" }

# --- Step 3: Deploy to Cloud Run ---
Write-Host "[3/3] Deploying to Cloud Run ($Region)..." -ForegroundColor Yellow

$authFlag = if ($AllowUnauthenticated) { "--allow-unauthenticated" } else { "--no-allow-unauthenticated" }

gcloud run deploy $ServiceName `
  --image=$ImageUri `
  --region=$Region `
  --project=$ProjectId `
  --platform=managed `
  --memory="${Memory}Mi" `
  --cpu=$Cpu `
  --max-instances=$MaxInstances `
  --min-instances=$MinInstances `
  --port=8080 `
  --set-env-vars="GCP_PROJECT_ID=$ProjectId,GOLD_DATASET_ID=thelook_datawarehouse,CLICKSTREAM_DATASET_ID=thelook_clickstream,REALTIME_TTL=60" `
  $authFlag

if ($LASTEXITCODE -ne 0) { throw "Cloud Run deploy failed." }

Write-Host ""
Write-Host "=== Deploy thành công! ===" -ForegroundColor Green
$url = (gcloud run services describe $ServiceName --region=$Region --project=$ProjectId --format="value(status.url)" 2>$null)
if ($url) {
  Write-Host "URL: $url" -ForegroundColor Cyan
}
