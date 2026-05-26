param(
  [string]$RedisUrl = "",
  [string]$WorkerClass = ""
)

$ErrorActionPreference = "Stop"

$BackendDir = Split-Path -Parent $PSScriptRoot
$VenvBin = Join-Path $BackendDir ".venv\Scripts"
if (-not (Test-Path $VenvBin)) {
  $VenvBin = Join-Path $BackendDir ".venv/bin"
}
$Python = Join-Path $VenvBin "python.exe"
if (-not (Test-Path $Python)) {
  $Python = Join-Path $VenvBin "python"
}
$Rq = Join-Path $VenvBin "rq.exe"
if (-not (Test-Path $Rq)) {
  $Rq = Join-Path $VenvBin "rq"
}

Push-Location $BackendDir
try {
  $env:PYTHONPATH = "$BackendDir;$env:PYTHONPATH"
  if (-not $RedisUrl) {
    $RedisUrl = & $Python -c "from app.config import get_settings; print(get_settings().redis_url)"
  }
  if (-not $WorkerClass) {
    $isWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
      [System.Runtime.InteropServices.OSPlatform]::Windows
    )
    if ($isWindows) {
      $WorkerClass = "app.rq_worker.WindowsSimpleWorker"
    }
  }
  $args = @("worker", "--url", $RedisUrl)
  if ($WorkerClass) {
    $args += @("--worker-class", $WorkerClass)
  }
  $args += "rag-imports"
  & $Rq @args
} finally {
  Pop-Location
}
