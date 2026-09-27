@echo off
title PricePilot Launcher
echo ========================================================
echo               PricePilot Production Launcher
echo ========================================================
echo.

cd /d "%~dp0"

:: 1. Free ports 8000 and 3000 if occupied
echo Freeing existing ports 8000 and 3000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    taskkill /f /pid %%a 2>nul
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000') do (
    taskkill /f /pid %%a 2>nul
)

:: 2. Launch FastAPI Backend in a persistent process window
echo [1/2] Launching FastAPI Backend on http://localhost:8000 ...
start "PricePilot Backend" cmd /c "title PricePilot Backend (Port 8000) && set DATABASE_URL=sqlite+aiosqlite:///./pricepilot.db&& set REDIS_URL=&& set PYTHONPATH=%~dp0services;%~dp0packages&& "%~dp0.venv\Scripts\python.exe" -m uvicorn api.main:app --host 0.0.0.0 --port 8000"

:: 3. Launch Next.js Web Server in a persistent process window
echo [2/2] Launching Next.js Web App on http://localhost:3000 ...
start "PricePilot Frontend" cmd /c "title PricePilot Frontend (Port 3000) && cd "%~dp0apps\web" && npm run start -- -p 3000"

echo.
echo Waiting for servers to initialize...
timeout /t 3 /nobreak >nul

:: 4. Automatically launch browser
start http://localhost:3000

echo ========================================================
echo   PricePilot is running!
echo   Local Web App:  http://localhost:3000
echo   Live Vercel:    https://web-tan-mu-sbcza7wklv.vercel.app
echo   API Docs:       http://localhost:8000/docs
echo   To stop all services, double-click stop.bat
echo ========================================================
echo.
pause
