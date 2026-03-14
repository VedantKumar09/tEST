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
start "MindMesh Backend" cmd /k "cd /d c:\My_Files\Projects\MindMeshV2\backend && .\venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
timeout /t 4 /nobreak >nul

:: Start Frontend (HTTPS)
echo [+] Starting frontend (port 5173 HTTPS)...
start "MindMesh Frontend" cmd /k "cd /d c:\My_Files\Projects\MindMeshV2\frontend && node node_modules/vite/bin/vite.js"
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
echo   PHONE (same Wi-Fi):
echo   https://192.168.105.154:5173
echo   Accept cert warning ^> tap Allow Camera
echo ========================================
pause
