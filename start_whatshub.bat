@echo off
title WhatsHub - All-in-One Runner
color 0A

echo ============================================================
echo           WhatsHub - WhatsApp AI Dashboard Runner
echo   Team Hacknova ^| Gemma 2B ^| Neonize Daemon ^| Dashboard
echo ============================================================
echo.

:: ---- Python interpreter -------------------------------------------------
set PYTHON_EXE=C:\Users\tarun\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

:: ---- Ensure we are in the script directory -------------------------------
cd /d "%~dp0"

:: ---- Install / verify dependencies ---------------------------------------
echo Installing/checking project dependencies...
"%PYTHON_EXE%" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

:: ---- Ollama -------------------------------------------------------------
echo [1/3] Checking Ollama AI engine...
powershell -Command "try {Invoke-WebRequest -Uri http://localhost:11434 -UseBasicParsing -ErrorAction Stop} catch {}"
if %ERRORLEVEL% EQU 0 (
    echo     [OK] Ollama is active.
) else (
    echo     [INFO] Starting Ollama in background...
    start "" /b ollama serve >nul 2>&1
)

:: ---- Neonize daemon -----------------------------------------------------
echo [2/3] Starting WhatsApp Neonize Daemon on port 5001...
start "" %PYTHON_EXE% backend\listener.py

:: ---- Web UI -------------------------------------------------------------
timeout /t 2 /nobreak >nul
echo [3/3] Starting WhatsHub Web Server on port 8080...
rem Use /d to set the working directory so static files are served correctly
start "" %PYTHON_EXE% -m http.server 8080 --bind 127.0.0.1

:: ---- Give the user a friendly link --------------------------------------
timeout /t 2 /nobreak >nul
echo.
echo ============================================================
echo  [READY] Launching WhatsHub in your default browser...
echo  Link: http://127.0.0.1:8080
echo ============================================================
start http://127.0.0.1:8080

echo.
echo All services are running! You can keep this window open or close it.
echo To present, simply use the browser window at http://127.0.0.1:8080.
pause