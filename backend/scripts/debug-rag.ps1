param(
  [Parameter(Mandatory = $true)]
  [string]$Query,

  [int]$Limit = 5
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

Push-Location $BackendDir
try {
  $env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"
  $env:RAG_DEBUG_QUERY = $Query
  & $Python -c "import json, os; from app.database import SessionLocal; from app.rag import debug_retrieve_curated_context; db = SessionLocal(); result = debug_retrieve_curated_context(db, os.environ['RAG_DEBUG_QUERY'], limit=$Limit); print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2)); db.close()"
} finally {
  Remove-Item Env:\RAG_DEBUG_QUERY -ErrorAction SilentlyContinue
  Pop-Location
}
