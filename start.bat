@echo off
title MindMesh v2

echo ========================================
echo   MindMesh v2 - Starting...
echo ========================================

:: Kill any stale processes that might be holding the ports
echo [*] Stopping any existing servers...
taskkill /F /IM uvicorn.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173 "') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul

:: Start Backend
echo [+] Starting backend (port 8000)...
start "MindMesh Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --reload --port 8000"
timeout /t 4 /nobreak >nul

:: Start Frontend (HTTPS)
echo [+] Starting frontend (port 5173 HTTPS)...
start "MindMesh Frontend" cmd /k "cd /d "%~dp0frontend" && node node_modules/vite/bin/vite.js"
timeout /t 5 /nobreak >nul

:: Open browser
start https://localhost:5173

echo.
echo ========================================
echo   MindMesh v2 is running!
echo ========================================
echo.
echo   PC       ^> https://localhost:5173
echo   Backend  ^> http://localhost:8000
echo.
:: Auto-detect LAN IP
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -ne '127.0.0.1' } | Select-Object -First 1).IPAddress"') do set LAN_IP=%%i
echo   PHONE (same Wi-Fi):
echo   https://%LAN_IP%:5173
echo   Accept cert warning ^> tap Allow Camera
echo ========================================
pause
