$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

Push-Location $BackendDir
try {
  & $Python -c "from app.database import init_database; init_database(); print('database initialized')"
} finally {
  Pop-Location
}
