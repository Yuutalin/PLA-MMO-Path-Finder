@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title PLA MMO Path Finder v0.7.3 - Junli^&GPT
cd /d "%~dp0"
set "LOG=%~dp0startup.log"
echo ================================================== > "%LOG%"
echo PLA MMO Path Finder startup log >> "%LOG%"
echo Start time: %DATE% %TIME% >> "%LOG%"
echo Project directory: %~dp0 >> "%LOG%"
echo ================================================== >> "%LOG%"
echo.
echo PLA MMO Path Finder - startup checks
echo Project: %~dp0
echo Log: %LOG%
echo.
set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 --version >> "%LOG%" 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python --version >> "%LOG%" 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)
if not defined PY_CMD (
    echo [ERROR] Python 3 was not found. Install Python 3.10+ and enable PATH.
    echo See: %LOG%
    pause
    exit /b 1
)
echo [CHECK] Python command: %PY_CMD%
%PY_CMD% --version
%PY_CMD% --version >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [ERROR] Python cannot run. See %LOG%
    pause
    exit /b 1
)
%PY_CMD% -c "import flask, usb, z3, webview" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Installing missing Python dependencies. Internet may be required.
    %PY_CMD% -m pip install -r requirements.txt >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed. Recent log:
        powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 35"
        pause
        exit /b 1
    )
)
%PY_CMD% -c "import flask, usb, z3, webview; print('z3-solver', z3.get_version_string()); print('pywebview import OK')" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [ERROR] Flask, pyusb, z3-solver or pywebview is still unavailable. See %LOG%
    pause
    exit /b 1
)
set "NEED_ENGINE=0"
if not exist "%~dp0offline_engine\pla\checkmmo.py" set "NEED_ENGINE=1"
if not exist "%~dp0offline_engine\static\resources\mmo_es.json" set "NEED_ENGINE=1"
if not exist "%~dp0offline_engine\static\resources\mmopaths.json" set "NEED_ENGINE=1"
if not exist "%~dp0offline_engine\static\resources\nonbonuspaths.json" set "NEED_ENGINE=1"
if not exist "%~dp0offline_engine\static\resources\seedhashes.json" set "NEED_ENGINE=1"
if not exist "%~dp0offline_engine\engine_manifest.json" set "NEED_ENGINE=1"
if not exist "%~dp0offline_engine\engine_install_ok.txt" set "NEED_ENGINE=1"
if exist "%~dp0offline_engine\engine_manifest.json" (
    findstr /C:"app_version" "%~dp0offline_engine\engine_manifest.json" | findstr /C:"0.3.6" >nul
    if errorlevel 1 set "NEED_ENGINE=1"
) else (
    set "NEED_ENGINE=1"
)
if "%NEED_ENGINE%"=="1" (
    echo.
    echo [SETUP] Preparing or repairing the local RNG engine. First setup needs internet.
    %PY_CMD% -u tools\prepare_offline_engine.py
    if errorlevel 1 (
        echo [WARNING] Local engine setup failed. The app window may open, but calculations will be unavailable.
        echo Check offline_engine_setup.log and run prepare_offline_engine.bat after fixing the issue.
    )
)
echo.
set "PLA_PORT="
for /f %%P in ('%PY_CMD% -c "from pla_mmo.launcher import choose_local_port; print(choose_local_port())" 2^>nul') do set "PLA_PORT=%%P"
if not defined PLA_PORT (
    echo [WARNING] Could not preselect a port; app.py will attempt automatic selection.
) else (
    echo [START] Starting standalone app window; local service: http://127.0.0.1:%PLA_PORT%
    if not "%PLA_PORT%"=="5000" echo [INFO] Port 5000 is occupied; a free port was selected to avoid connecting to an older instance.
)
echo Starting the standalone desktop window. Keep this window open while using the tool.
set "PLA_DESKTOP=1"
echo Launching desktop app.py with PLA_PORT=%PLA_PORT% >> "%LOG%"
%PY_CMD% -u app.py >> "%LOG%" 2>&1
set "APP_EXIT=%ERRORLEVEL%"
echo.
if not "%APP_EXIT%"=="0" (
    echo [ERROR] App exited with code %APP_EXIT%. Log: %LOG%
    powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 35"
    echo.
    pause
) else (
    echo [INFO] App stopped. Log: %LOG%
)
endlocal
