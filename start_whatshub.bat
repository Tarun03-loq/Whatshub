@echo off
title WhatsHub - All-in-One Runner
color 0A

echo ============================================================
echo           WhatsHub - WhatsApp AI Dashboard Runner
echo   Team Hacknova ^| Gemma 2B ^| Neonize Daemon ^| Dashboard
echo ============================================================
echo.

set PYTHON_EXE=C:\Users\tarun\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

cd /d "%~dp0"

echo [1/3] Checking Ollama AI engine...
curl -s http://localhost:11434 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo     [OK] Ollama is active (Gemma 2B ready).
) else (
    echo     [INFO] Starting Ollama in background...
    start "" /b ollama serve >nul 2>&1
)

echo [2/3] Starting WhatsApp Neonize Daemon on port 5001...
start "WhatsHub - WhatsApp Daemon (:5001)" cmd /k ""%PYTHON_EXE%" backend\listener.py"

timeout /t 2 /nobreak >nul

echo [3/3] Starting WhatsHub Web Server on port 8000...
start "WhatsHub - Web Server (:8000)" cmd /k ""%PYTHON_EXE%" -m http.server 8000"

timeout /t 2 /nobreak >nul

echo.
echo ============================================================
echo  [READY] Launching WhatsHub in your default browser...
echo  Link: http://localhost:8000
echo ============================================================
start http://localhost:8000

echo.
echo All services are running! You can keep this window open or close it.
echo To present, simply use the browser window at http://localhost:8000.
pause
