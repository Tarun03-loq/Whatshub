@echo off
title UNIFIES WhatsApp Neonize Daemon
cd /d "%~dp0"

echo ============================================================
echo   UNIFIES Cross-Chat Task Aggregator - WhatsApp Daemon
echo   Neonize Multi-Device Protocol with Segno Base64 QR Code
echo ============================================================
echo.

:: Detect Python
set PYTHON_CMD=python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set PYTHON_CMD="%LocalAppData%\Programs\Python\Python312\python.exe"
    ) else if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set PYTHON_CMD="%LocalAppData%\Programs\Python\Python311\python.exe"
    ) else if exist "%ProgramFiles%\Python312\python.exe" (
        set PYTHON_CMD="%ProgramFiles%\Python312\python.exe"
    ) else (
        echo [ERROR] Python not detected. Please install Python 3.10+ from python.org or run winget install Python.Python.3.12
        pause
        exit /b 1
    )
)

echo [1/2] Verifying Python runtime:
%PYTHON_CMD% --version
echo.

echo [2/2] Installing project dependencies...
%PYTHON_CMD% -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Launching WhatsHub dashboard and WhatsApp daemon
echo ============================================================
echo.
start "WhatsHub Dashboard Server" /min %PYTHON_CMD% -m http.server 8080 --bind 127.0.0.1 --directory "%~dp0"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8080"
if exist listener.py (%PYTHON_CMD% listener.py) else (%PYTHON_CMD% backend\listener.py)
pause
