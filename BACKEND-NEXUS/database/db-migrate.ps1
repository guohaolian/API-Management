param(
    # 模型变更后生成新 revision（需已配置 .env 中的 DATABASE_URI）
    [switch]$Generate,
    [string]$Message = "db migrate"
)

$ErrorActionPreference = 'Stop'

Set-Location -Path (Join-Path $PSScriptRoot '..')

Write-Host 'Database Migration Start...'

if ($Generate) {
    Write-Host "Generating revision: $Message"
    uv run alembic revision --autogenerate -m $Message
}

uv run alembic upgrade head
Write-Host 'Database Migration Success'
