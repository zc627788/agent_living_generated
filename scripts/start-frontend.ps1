param(
  [string]$ApiBaseUrl = "http://127.0.0.1:8000/api/v1",
  [int]$Port = 3000
)

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..\frontend")

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding

$env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl
$env:PORT = "$Port"

Write-Host ""
Write-Host "Frontend starting on http://0.0.0.0:$Port (localhost: http://127.0.0.1:$Port)" -ForegroundColor Cyan
Write-Host "Network access: http://<your-ip>:$Port" -ForegroundColor Green
Write-Host "NEXT_PUBLIC_API_BASE_URL=$ApiBaseUrl" -ForegroundColor Green
Write-Host ""

npm run dev
