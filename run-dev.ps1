$ErrorActionPreference = 'Stop'

$rootPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendScript = Join-Path $rootPath 'BACKEND-NEXUS\run-dev.ps1'
$frontendPath = Join-Path $rootPath 'FRONTEND-NEXUS'

if (-not (Test-Path $backendScript)) {
    throw "找不到后端启动脚本：$backendScript"
}

if (-not (Test-Path $frontendPath)) {
    throw "找不到前端目录：$frontendPath"
}

Start-Process -FilePath 'powershell' -WorkingDirectory $rootPath -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy', 'Bypass',
    '-File', $backendScript
) | Out-Null

Start-Process -FilePath 'powershell' -WorkingDirectory $frontendPath -ArgumentList @(
    '-NoExit',
    '-Command', 'npm run dev'
) | Out-Null

Write-Host 'Backend and frontend started in separate windows.'