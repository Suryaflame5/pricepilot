# PricePilot Production Shutdown Script
$rootDir = $PSScriptRoot

Write-Host "Stopping PricePilot services..." -ForegroundColor Yellow

# Kill from .pids file if present
if (Test-Path "$rootDir\.pids") {
    $pids = Get-Content "$rootDir\.pids"
    foreach ($pidNum in $pids) {
        if ($pidNum) {
            Stop-Process -Id ([int]$pidNum.Trim()) -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item "$rootDir\.pids" -Force -ErrorAction SilentlyContinue
}

# Ensure ports 8000 and 3000 are freed
$ports = @(8000, 3000)
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        $procIds = $conn.OwningProcess | Select-Object -Unique
        foreach ($procId in $procIds) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "[OK] PricePilot services stopped successfully." -ForegroundColor Green
