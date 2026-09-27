# PricePilot Production Startup Script
$ErrorActionPreference = "Stop"
$rootDir = $PSScriptRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       Starting PricePilot Production     " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Check if ports are already in use
$p8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($p8000) {
    Write-Host "[!] Port 8000 is currently occupied. Freeing port..." -ForegroundColor Yellow
    Stop-Process -Id ($p8000.OwningProcess | Select-Object -Unique) -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

$p3000 = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
if ($p3000) {
    Write-Host "[!] Port 3000 is currently occupied. Freeing port..." -ForegroundColor Yellow
    Stop-Process -Id ($p3000.OwningProcess | Select-Object -Unique) -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

# 2. Start Backend FastAPI Server
Write-Host "[+] Launching FastAPI Backend on http://0.0.0.0:8000..." -ForegroundColor Green
$backendStartInfo = New-Object System.Diagnostics.ProcessStartInfo
$backendStartInfo.FileName = "$rootDir\.venv\Scripts\python.exe"
$backendStartInfo.Arguments = "-m uvicorn api.main:app --host 0.0.0.0 --port 8000"
$backendStartInfo.WorkingDirectory = $rootDir
$backendStartInfo.UseShellExecute = $false
$backendStartInfo.CreateNoWindow = $true
$backendStartInfo.EnvironmentVariables["DATABASE_URL"] = "sqlite+aiosqlite:///./pricepilot.db"
$backendStartInfo.EnvironmentVariables["REDIS_URL"] = ""
$backendStartInfo.EnvironmentVariables["PYTHONPATH"] = "$rootDir\services;$rootDir\packages"

$backendProc = [System.Diagnostics.Process]::Start($backendStartInfo)

# Poll backend health
$backendHealthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($resp.status -eq "ok") {
            $backendHealthy = $true
            break
        }
    } catch {
        # Waiting for backend
    }
}

if (-not $backendHealthy) {
    Write-Host "[X] Backend failed to start within 30 seconds." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Backend is healthy at http://localhost:8000 (PID: $($backendProc.Id))" -ForegroundColor Green

# 3. Start Next.js Production Server
Write-Host "[+] Launching Next.js Production Web Server on http://0.0.0.0:3000..." -ForegroundColor Green
$webStartInfo = New-Object System.Diagnostics.ProcessStartInfo
$webStartInfo.FileName = "cmd.exe"
$webStartInfo.Arguments = "/c npm run start -- -p 3000"
$webStartInfo.WorkingDirectory = "$rootDir\apps\web"
$webStartInfo.UseShellExecute = $false
$webStartInfo.CreateNoWindow = $true
$webStartInfo.EnvironmentVariables["PORT"] = "3000"
$webStartInfo.EnvironmentVariables["NEXT_PUBLIC_API_URL"] = "http://localhost:8000"

$webProc = [System.Diagnostics.Process]::Start($webStartInfo)

# Poll web frontend
$webHealthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $webHealthy = $true
            break
        }
    } catch {
        # Waiting for frontend
    }
}

if (-not $webHealthy) {
    Write-Host "[X] Web frontend failed to start within 30 seconds." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Frontend is healthy at http://localhost:3000 (PID: $($webProc.Id))" -ForegroundColor Green

# Save PIDs to .pids file
Set-Content -Path "$rootDir\.pids" -Value "$($backendProc.Id)`n$($webProc.Id)"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  PricePilot Deployment Successful!       " -ForegroundColor Green
Write-Host "  Web Dashboard:   http://localhost:3000  " -ForegroundColor Cyan
Write-Host "  API Backend:     http://localhost:8000  " -ForegroundColor Cyan
Write-Host "  API Docs:        http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
