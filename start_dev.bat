@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title PLA MMO Path Finder v0.7.3 - Dev Launcher - Junli^&GPT
cd /d "%~dp0"
set "LOG=%~dp0startup-dev.log"
echo Development start: %DATE% %TIME% > "%LOG%"
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
  echo [ERROR] Python 3.10+ not found.
  pause
  exit /b 1
)
%PY_CMD% -c "import flask, usb, z3" >nul 2>nul
if errorlevel 1 (
  %PY_CMD% -m pip install --force-reinstall -r requirements.txt >> "%LOG%" 2>&1
  if errorlevel 1 (
    echo [ERROR] Dependency installation failed. See startup-dev.log
    pause
    exit /b 1
  )
)
set "NEED_ENGINE=0"
if not exist "%~dp0offline_engine\pla\checkmmo.py" set "NEED_ENGINE=1"
if not exist "%~dp0offline_engine\engine_install_ok.txt" set "NEED_ENGINE=1"
if exist "%~dp0offline_engine\engine_manifest.json" (
  findstr /C:"app_version" "%~dp0offline_engine\engine_manifest.json" | findstr /C:"0.3.6" >nul
  if errorlevel 1 set "NEED_ENGINE=1"
) else (
  set "NEED_ENGINE=1"
)
if "%NEED_ENGINE%"=="1" (
  %PY_CMD% -u tools\prepare_offline_engine.py
  if errorlevel 1 echo [WARNING] Local engine setup failed. See offline_engine_setup.log.
)
set "PLA_PORT="
for /f %%P in ('%PY_CMD% -c "from pla_mmo.launcher import choose_local_port; print(choose_local_port())" 2^>nul') do set "PLA_PORT=%%P"
if defined PLA_PORT (
  echo [START] Development build at http://127.0.0.1:%PLA_PORT%
  if not "%PLA_PORT%"=="5000" echo [INFO] Port 5000 is occupied; using a free port to avoid the older instance.
) else (
  echo [WARNING] Could not preselect a port; app.py will attempt automatic selection.
)
set PLA_DEV=1
echo Keep this window open while using the tool.
%PY_CMD% -u app.py >> "%LOG%" 2>&1
echo App stopped. Log: %LOG%
powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 40"
pause
endlocal
