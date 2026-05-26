param(
  [string]$Path = ".\data\rag-eval.json"
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

Push-Location $BackendDir
try {
  $env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"
  & $Python -m app.rag_eval $Path
} finally {
  Pop-Location
}
