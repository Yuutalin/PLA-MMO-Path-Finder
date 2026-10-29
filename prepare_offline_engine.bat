@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title PLA MMO Path Finder v0.7.3 - Local Engine Setup - Junli^&GPT
cd /d "%~dp0"
echo.
echo PLA MMO Path Finder - local RNG engine setup
echo First setup downloads the open-source engine and resources.
echo After the local calculation test passes, runtime path calculations can work offline.
echo User Seed files, settings, and history are not overwritten.
echo.
set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
  )
)
if not defined PY_CMD (
  echo [ERROR] Python 3.10+ was not found. Install Python and enable PATH.
  pause
  exit /b 1
)
%PY_CMD% -u tools\prepare_offline_engine.py
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" (
  echo [FAILED] The engine did not pass its local calculation test.
  echo Check offline_engine_setup.log and try again.
) else (
  echo [OK] The local RNG engine passed its calculation smoke test.
  echo You can now start the tool with start.bat.
)
echo.
pause
exit /b %RESULT%
