$ErrorActionPreference = 'Stop'

Set-Location -Path $PSScriptRoot

uv run robyn -m app --dev
