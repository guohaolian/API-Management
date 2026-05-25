$ErrorActionPreference = 'Stop'

# Switch to the project root directory (BE-CAM)
Set-Location -Path (Join-Path $PSScriptRoot '..')

Write-Host 'Database Migration Start...'
uv run alembic revision --autogenerate -m 'db migrate'
uv run alembic upgrade head
Write-Host 'Database Migration Success'
