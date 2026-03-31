$ErrorActionPreference = 'Stop'

param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet('backend', 'frontend')]
  [string]$Workspace
)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$env:PYTHONIOENCODING = 'utf-8'
$env:NODE_DISABLE_COLORS = $env:NODE_DISABLE_COLORS

chcp.com 65001 > $null

Write-Host "Starting $Workspace in UTF-8 mode..."
& npm.cmd run dev --workspace=$Workspace
