param(
  [Parameter(Mandatory = $true)]
  [string]$Path,

  [Parameter(Mandatory = $true)]
  [string]$Collection,

  [string]$Title = "",

  [string]$SourceUri = "",

  [int]$ChunkSize = 1200,

  [int]$ChunkOverlap = 150
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $BackendDir ".venv\Scripts\python.exe"

Push-Location $BackendDir
try {
  $env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"
  $env:RAG_DOCUMENT_PATH = $Path
  $env:RAG_DOCUMENT_COLLECTION = $Collection
  $env:RAG_DOCUMENT_TITLE = $Title
  $env:RAG_DOCUMENT_SOURCE_URI = $SourceUri
  $env:RAG_DOCUMENT_CHUNK_SIZE = [string]$ChunkSize
  $env:RAG_DOCUMENT_CHUNK_OVERLAP = [string]$ChunkOverlap
  & $Python -c "import os; from app.database import SessionLocal; from app.document_pipeline import import_document_file_with_stats; db = SessionLocal(); stats = import_document_file_with_stats(db, os.environ['RAG_DOCUMENT_PATH'], collection_title=os.environ['RAG_DOCUMENT_COLLECTION'], title=os.environ.get('RAG_DOCUMENT_TITLE') or None, source_uri=os.environ.get('RAG_DOCUMENT_SOURCE_URI') or None, chunk_size=int(os.environ['RAG_DOCUMENT_CHUNK_SIZE']), chunk_overlap=int(os.environ['RAG_DOCUMENT_CHUNK_OVERLAP'])); print(f'imported {stats.total_imported} document RAG chunks; embeddings generated={stats.embeddings_generated}, skipped={stats.embeddings_skipped}, failed={stats.embeddings_failed}'); db.close()"
} finally {
  Remove-Item Env:\RAG_DOCUMENT_PATH -ErrorAction SilentlyContinue
  Remove-Item Env:\RAG_DOCUMENT_COLLECTION -ErrorAction SilentlyContinue
  Remove-Item Env:\RAG_DOCUMENT_TITLE -ErrorAction SilentlyContinue
  Remove-Item Env:\RAG_DOCUMENT_SOURCE_URI -ErrorAction SilentlyContinue
  Remove-Item Env:\RAG_DOCUMENT_CHUNK_SIZE -ErrorAction SilentlyContinue
  Remove-Item Env:\RAG_DOCUMENT_CHUNK_OVERLAP -ErrorAction SilentlyContinue
  Pop-Location
}
