@echo off
title MindMesh v2 - Stop

echo Stopping MindMesh v2 servers...

:: Kill uvicorn (backend)
taskkill /F /IM uvicorn.exe >nul 2>&1
echo [x] Backend stopped

:: Kill node (frontend Vite dev server)
taskkill /F /FI "WINDOWTITLE eq MindMesh Frontend" /IM node.exe >nul 2>&1
echo [x] Frontend stopped

echo.
echo All servers stopped.
pause
