@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title PLA MMO Path Finder - Build Tools - Junli^&GPT
cd /d "%~dp0.."

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3.12"
  if not defined PY_CMD (
    py -3 --version >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py -3"
  )
)
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
  )
)

if defined PY_CMD (
  %PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
  if errorlevel 1 set "PY_CMD="
)

if not defined PY_CMD (
  echo.
  echo [CHECK] 未检测到 Python 3.10 或更高版本。
  echo 构建工具可从 python.org 自动下载官方 Python 3.12.10 安装程序。
  choice /M "是否下载并安装 Python（需要网络）"
  if errorlevel 2 (
    echo 已取消。若只想运行源码版，请使用项目根目录的 start.bat，并先安装 Python。
    pause
    exit /b 2
  )
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap_python.ps1"
  if errorlevel 1 (
    echo [ERROR] Python 自动安装失败。请查看上方信息后重试。
    pause
    exit /b 2
  )
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
  if not defined PY_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
      py -3.12 --version >nul 2>nul
      if not errorlevel 1 set "PY_CMD=py -3.12"
    )
  )
  if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
      python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
      if not errorlevel 1 set "PY_CMD=python"
    )
  )
)

if not defined PY_CMD (
  echo [ERROR] 安装后仍未找到 Python。请重新打开终端，或检查 Python Launcher。
  pause
  exit /b 2
)

echo.
echo ==================================================
echo PLA MMO Path Finder v0.7.3 - Build Tools
echo 作者：君粒^&GPT
echo ==================================================
echo 使用 Python：%PY_CMD%
echo 构建文件位于 build_tools 文件夹。
echo Source mode does not need compilation: run start.bat from the project root.
echo.
%PY_CMD% "%~dp0build.py"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo [ERROR] 构建工具退出代码：%RESULT%
pause
exit /b %RESULT%
