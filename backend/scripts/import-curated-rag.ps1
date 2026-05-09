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
  & $Python -c "from app.curated_import import import_curated_file_with_stats; stats = import_curated_file_with_stats(r'$Path'); print(f'imported {stats.total_imported} curated RAG items; embeddings generated={stats.embeddings_generated}, skipped={stats.embeddings_skipped}, failed={stats.embeddings_failed}')"
} finally {
  Pop-Location
}
