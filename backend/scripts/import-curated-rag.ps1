param(
  [Parameter(Mandatory = $true)]
  [string]$Path
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

Push-Location $BackendDir
try {
  $env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"
  & $Python -c "from app.curated_import import import_curated_file; count = import_curated_file(r'$Path'); print(f'imported {count} curated RAG items')"
} finally {
  Pop-Location
}
