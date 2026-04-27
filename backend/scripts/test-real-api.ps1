$RepoRoot = Resolve-Path "$PSScriptRoot\..\.."
$BackendRoot = Join-Path $RepoRoot "backend"
$VenvPython = Join-Path $BackendRoot ".venv\Scripts\python.exe"
$SitePackages = Resolve-Path "$BackendRoot\.venv\Lib\site-packages"

$env:PYTHONPATH = "$SitePackages;$BackendRoot;$env:PYTHONPATH"
& $VenvPython -m pytest "$BackendRoot\tests\real_api_manual.py" -s @args
