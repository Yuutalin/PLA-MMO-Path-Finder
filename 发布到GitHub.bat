@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ==========================================================
echo  PLA MMO Path Finder - GitHub 发布助手
echo  作者：君粒^&GPT
echo ==========================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo [错误] 没有检测到 Git。
  echo 请先安装 Git for Windows：https://git-scm.com/download/win
  echo 安装完成后重新运行本脚本。
  echo.
  pause
  exit /b 1
)

if not exist "README.md" (
  echo [错误] 未在脚本所在目录找到 README.md。
  echo 请在解压后的项目根目录运行本脚本，不要移动这个 BAT 文件。
  echo.
  pause
  exit /b 1
)

echo 第 1 步：检查 Git 提交身份。
set "GIT_NAME="
for /f "delims=" %%A in ('git config user.name 2^>nul') do set "GIT_NAME=%%A"
if not defined GIT_NAME (
  set /p "GIT_NAME=请输入提交显示名称（例如：君粒）："
  if not defined GIT_NAME set "GIT_NAME=GitHub Contributor"
  git config user.name "!GIT_NAME!"
)
set "GIT_EMAIL="
for /f "delims=" %%A in ('git config user.email 2^>nul') do set "GIT_EMAIL=%%A"
if not defined GIT_EMAIL (
  set /p "GIT_EMAIL=请输入提交邮箱（可使用 GitHub 提供的 noreply 邮箱）："
  if not defined GIT_EMAIL (
    echo [错误] 提交邮箱不能为空。
    pause
    exit /b 1
  )
  git config user.email "!GIT_EMAIL!"
)

echo.
echo 第 2 步：准备本地仓库。
if not exist ".git" (
  git init
  if errorlevel 1 goto :failed
)
git branch -M main
if errorlevel 1 goto :failed

echo.
echo 第 3 步：设置 GitHub 远程仓库。
for /f "delims=" %%A in ('git remote get-url origin 2^>nul') do set "CURRENT_ORIGIN=%%A"
if defined CURRENT_ORIGIN (
  echo 当前 origin：!CURRENT_ORIGIN!
  set "REPO_URL="
  set /p "REPO_URL=输入新的 GitHub 仓库 HTTPS/SSH 地址；直接回车保留当前地址："
  if defined REPO_URL (
    git remote set-url origin "!REPO_URL!"
    if errorlevel 1 goto :failed
  )
) else (
  echo 请先在 https://github.com/new 创建一个空仓库。
  set "REPO_URL="
  set /p "REPO_URL=粘贴新仓库地址（例如 https://github.com/用户名/PLA-MMO-Path-Finder.git）："
  if not defined REPO_URL (
    echo [错误] 仓库地址不能为空。
    pause
    exit /b 1
  )
  git remote add origin "!REPO_URL!"
  if errorlevel 1 goto :failed
)

for /f "delims=" %%A in ('git remote get-url origin 2^>nul') do set "CURRENT_ORIGIN=%%A"
if not defined CURRENT_ORIGIN goto :failed

echo.
echo 第 4 步：提交当前项目文件。
git add -A
if errorlevel 1 goto :failed
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Publish PLA MMO Path Finder v0.7.3"
  if errorlevel 1 goto :failed
) else (
  echo 没有新的文件变化，跳过提交。
)

echo.
echo 第 5 步：推送到 GitHub。
echo 远程仓库：!CURRENT_ORIGIN!
git push -u origin main
if errorlevel 1 (
  echo.
  echo [推送未完成] 请检查仓库地址、网络与 GitHub 登录授权。
  echo 如果 GitHub 仓库已有 README 等初始提交，可能需要先在 GitHub 端处理历史冲突。
  pause
  exit /b 1
)

echo.
echo [完成] 项目已推送到 GitHub 的 main 分支。
echo 请刷新仓库页面检查 README 和截图占位图。
pause
exit /b 0

:failed
echo.
echo [失败] Git 操作未完成。请检查上方错误信息后重试。
pause
exit /b 1
