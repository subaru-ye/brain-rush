param(
  [string]$Path = ".\data\rag-knowledge.json"
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

Push-Location $BackendDir
try {
  $env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"
  & $Python -m app.rag_data_check $Path
} finally {
  Pop-Location
}
