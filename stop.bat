@echo off
title Stopping PricePilot
echo ========================================================
echo               Stopping PricePilot Services
echo ========================================================
echo.

cd /d "%~dp0"

echo Stopping processes on port 8000 (Backend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    taskkill /f /pid %%a 2>nul
)

echo Stopping processes on port 3000 (Web Frontend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000') do (
    taskkill /f /pid %%a 2>nul
)

echo.
echo ========================================================
echo   All PricePilot services stopped successfully!
echo ========================================================
echo.
pause
