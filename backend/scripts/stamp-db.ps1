param(
  [string]$Revision = "head"
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"
$AlembicConfig = Join-Path $BackendDir "alembic.ini"

Push-Location $BackendDir
try {
  $env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"
  & $Python -m alembic -c $AlembicConfig stamp $Revision
  Write-Host "database stamped to $Revision"
} finally {
  Pop-Location
}
