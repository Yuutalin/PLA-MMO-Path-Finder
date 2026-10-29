$ErrorActionPreference = 'Stop'
$version = '3.12.10'
$url = "https://www.python.org/ftp/python/$version/python-$version-amd64.exe"
$work = Join-Path $PSScriptRoot '.work'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$installer = Join-Path $work "python-$version-amd64.exe"
Write-Host "正在从 python.org 下载 Python $version ..."
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
$signature = Get-AuthenticodeSignature -FilePath $installer
if ($signature.Status -ne 'Valid') {
    Remove-Item -Force -ErrorAction SilentlyContinue $installer
    throw "Python 安装程序的数字签名校验失败，已停止安装。状态：$($signature.Status)"
}
Write-Host '官方签名验证通过，正在以当前用户身份安装 Python。'
$arguments = @('/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1', 'Include_pip=1', 'Include_test=0')
$process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
if ($process.ExitCode -ne 0) {
    throw "Python 安装失败，退出代码：$($process.ExitCode)"
}
Write-Host 'Python 安装完成。请稍候，构建工具将重新检查 Python 启动器。'
