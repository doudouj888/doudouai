$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root '.logs'

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$utf8Setup = @'
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONIOENCODING = 'utf-8'
chcp.com 65001 > $null
'@

function Start-Utf8Workspace {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace
  )

  $stdoutPath = Join-Path $logDir "$Workspace-dev.utf8.log"
  $stderrPath = Join-Path $logDir "$Workspace-dev.utf8.err.log"

  if (Test-Path $stdoutPath) {
    Remove-Item -LiteralPath $stdoutPath -Force
  }
  if (Test-Path $stderrPath) {
    Remove-Item -LiteralPath $stderrPath -Force
  }

  $command = @"
Set-Location '$root'
$utf8Setup
Write-Host 'Starting $Workspace in UTF-8 mode...'
& npm.cmd run dev --workspace=$Workspace
"@

  Start-Process `
    -FilePath 'powershell.exe' `
    -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $command) `
    -WorkingDirectory $root `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru
}

$backend = Start-Utf8Workspace -Workspace 'backend'
$frontend = Start-Utf8Workspace -Workspace 'frontend'

Write-Host "Backend PID: $($backend.Id)"
Write-Host "Frontend PID: $($frontend.Id)"
Write-Host "Backend log: $($logDir)\backend-dev.utf8.log"
Write-Host "Frontend log: $($logDir)\frontend-dev.utf8.log"
