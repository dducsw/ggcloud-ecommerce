$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   DATA QUALITY & RECONCILIATION TEST" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Update dbt dependencies
Write-Host "`n[1/3] Cập nhật dbt packages..." -ForegroundColor Yellow
cd dbt/thelook_dwh
try {
    # Delete dbt_packages if it exists to avoid permission errors on Windows
    if (Test-Path -Path "dbt_packages") {
        Remove-Item -Recurse -Force dbt_packages -ErrorAction SilentlyContinue
    }
    dbt deps --profiles-dir .
} catch {
    Write-Host "⚠️ Lỗi khi chạy dbt deps. Có thể bị khoá file do process khác. Bỏ qua và tiếp tục..." -ForegroundColor Red
}

# 2. Run dbt build (which includes dbt run and dbt test)
Write-Host "`n[2/3] Chạy dbt build (Transform & Test)..." -ForegroundColor Yellow
dbt build --profiles-dir .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ dbt build/test đã FAIL. Vui lòng kiểm tra log dbt bên trên." -ForegroundColor Red
} else {
    Write-Host "✅ dbt build/test thành công. Data Quality Tests (Schema tests) đã PASS." -ForegroundColor Green
}

# 3. Run Python Reconciliation Script
Write-Host "`n[3/3] Chạy tập lệnh đối soát dữ liệu (Reconciliation)..." -ForegroundColor Yellow
cd ../..
python src/testing/data_reconciliation.py

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "           HOÀN TẤT KIỂM THỬ" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
