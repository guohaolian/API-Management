$ErrorActionPreference = 'Stop'

Set-Location -Path $PSScriptRoot

uv run robyn -m app --process=4 --workers=3
