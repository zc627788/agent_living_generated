param(
  [int]$Port = 8000,
  [switch]$Reload
)

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..\backend")

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding

function Stop-PortProcess {
  param([int]$TargetPort)

  $connections = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
  foreach ($connection in $connections) {
    try {
      Stop-Process -Id $connection.OwningProcess -Force -ErrorAction Stop
      Start-Sleep -Milliseconds 400
    } catch {
    }
  }
}

Stop-PortProcess -TargetPort $Port

$args = @(
  "-m", "uvicorn",
  "app.main:app",
  "--host", "0.0.0.0",
  "--port", "$Port"
)

if ($Reload) {
  $args += "--reload"
}

Write-Host ""
Write-Host "Backend starting on http://127.0.0.1:$Port" -ForegroundColor Cyan
if ($Reload) {
  Write-Host "Mode: reload (development)" -ForegroundColor Yellow
} else {
  Write-Host "Mode: stable single-process" -ForegroundColor Green
}
Write-Host ""

python @args
