param(
  [string]$PostgresHome = "C:\Program Files\PostgreSQL\17",
  [string]$HostName = "localhost",
  [int]$Port = 5432,
  [string]$Database = "brain_rush",
  [string]$AdminUser = "postgres",
  [string]$AdminPassword = "",
  [string]$CMakePath = "",
  [string]$WorkDir = "$env:TEMP\pg_jieba_build"
)

$ErrorActionPreference = "Stop"

$PgBin = Join-Path $PostgresHome "bin"
$PgConfig = Join-Path $PgBin "pg_config.exe"
$Psql = Join-Path $PgBin "psql.exe"
$BackendDir = Split-Path -Parent $PSScriptRoot
$BundledCMake = Join-Path $BackendDir ".venv\Scripts\cmake.exe"
$SourceDir = Join-Path $WorkDir "pg_jieba"
$BuildDir = Join-Path $WorkDir "build"
$SourceZip = Join-Path $WorkDir "pg_jieba.zip"
$CompatDir = Join-Path $WorkDir "compat"

function Invoke-Step {
  param(
    [string]$Name,
    [scriptblock]$Action
  )
  Write-Host "==> $Name"
  & $Action
}

function Invoke-Native {
  param(
    [string]$FilePath,
    [string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$FilePath failed with exit code $LASTEXITCODE"
  }
}

function Copy-DirectoryContents {
  param(
    [string]$Source,
    [string]$Destination
  )
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
}

function Expand-GithubZip {
  param(
    [string]$Uri,
    [string]$ZipPath,
    [string]$ExtractPath,
    [string]$Destination,
    [string]$DirectoryPattern
  )
  if (Test-Path $ZipPath) {
    Remove-Item -Force -LiteralPath $ZipPath
  }
  if (Test-Path $ExtractPath) {
    Remove-Item -Recurse -Force -LiteralPath $ExtractPath
  }
  Invoke-WebRequest -Uri $Uri -OutFile $ZipPath
  Expand-Archive -Path $ZipPath -DestinationPath $ExtractPath -Force
  $Expanded = Get-ChildItem -Path $ExtractPath -Directory | Where-Object { $_.Name -like $DirectoryPattern } | Select-Object -First 1
  if (-not $Expanded) {
    throw "$Uri did not contain $DirectoryPattern"
  }
  if (Test-Path $Destination) {
    Remove-Item -Recurse -Force -LiteralPath $Destination
  }
  Copy-DirectoryContents $Expanded.FullName $Destination
}

function Ensure-ZipFallbackDependencies {
  $LibJiebaDir = Join-Path $SourceDir "libjieba"
  $LimonpDir = Join-Path $LibJiebaDir "deps\limonp"
  if (-not (Test-Path (Join-Path $LibJiebaDir "include\cppjieba\Jieba.hpp"))) {
    Expand-GithubZip `
      -Uri "https://github.com/yanyiwu/cppjieba/archive/refs/heads/master.zip" `
      -ZipPath (Join-Path $WorkDir "cppjieba.zip") `
      -ExtractPath (Join-Path $WorkDir "cppjieba_extract") `
      -Destination $LibJiebaDir `
      -DirectoryPattern "cppjieba-*"
  }
  if (-not (Test-Path (Join-Path $LimonpDir "include\limonp\Logging.hpp"))) {
    Expand-GithubZip `
      -Uri "https://github.com/yanyiwu/limonp/archive/refs/heads/master.zip" `
      -ZipPath (Join-Path $WorkDir "limonp.zip") `
      -ExtractPath (Join-Path $WorkDir "limonp_extract") `
      -Destination $LimonpDir `
      -DirectoryPattern "limonp-*"
  }
}

function New-WindowsCompatHeaders {
  New-Item -ItemType Directory -Force -Path (Join-Path $CompatDir "netinet") | Out-Null
  New-Item -ItemType Directory -Force -Path (Join-Path $CompatDir "arpa") | Out-Null
  Set-Content -Path (Join-Path $CompatDir "netinet\in.h") -Value "#pragma once`r`n#include <winsock2.h>`r`n#include <ws2tcpip.h>`r`n" -Encoding ASCII
  Set-Content -Path (Join-Path $CompatDir "arpa\inet.h") -Value "#pragma once`r`n#include <winsock2.h>`r`n#include <ws2tcpip.h>`r`n" -Encoding ASCII
}

try {
  if (-not (Test-Path $PgConfig)) {
    throw "pg_config.exe not found at $PgConfig"
  }
  if (-not (Test-Path $Psql)) {
    throw "psql.exe not found at $Psql"
  }
  $GitCommand = Get-Command git -ErrorAction SilentlyContinue
  if (-not $CMakePath) {
    if (Test-Path $BundledCMake) {
      $CMakePath = $BundledCMake
    } else {
      $CMakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
      if ($CMakeCommand) {
        $CMakePath = $CMakeCommand.Source
      }
    }
  }
  if (-not $CMakePath -or -not (Test-Path $CMakePath)) {
    throw "cmake is required to build pg_jieba"
  }

  New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

  Invoke-Step "clone pg_jieba" {
    if (Test-Path (Join-Path $SourceDir ".git")) {
      Invoke-Native "git" @("-C", $SourceDir, "pull", "--ff-only")
      Invoke-Native "git" @("-C", $SourceDir, "submodule", "update", "--init", "--recursive")
    } elseif (Test-Path (Join-Path $SourceDir "CMakeLists.txt")) {
      Write-Host "using existing pg_jieba source at $SourceDir"
    } else {
      if (Test-Path $SourceDir) {
        Remove-Item -Recurse -Force -LiteralPath $SourceDir
      }
      if ($GitCommand) {
        try {
          Invoke-Native "git" @("clone", "--depth", "1", "--recurse-submodules", "https://github.com/jaiminpan/pg_jieba.git", $SourceDir)
        } catch {
          Write-Warning "git clone failed, trying zip download fallback"
          Expand-GithubZip `
            -Uri "https://github.com/jaiminpan/pg_jieba/archive/refs/heads/master.zip" `
            -ZipPath $SourceZip `
            -ExtractPath (Join-Path $WorkDir "pg_jieba_extract") `
            -Destination $SourceDir `
            -DirectoryPattern "pg_jieba-*"
        }
      } else {
        Write-Warning "git clone failed, trying zip download fallback"
        Expand-GithubZip `
          -Uri "https://github.com/jaiminpan/pg_jieba/archive/refs/heads/master.zip" `
          -ZipPath $SourceZip `
          -ExtractPath (Join-Path $WorkDir "pg_jieba_extract") `
          -Destination $SourceDir `
          -DirectoryPattern "pg_jieba-*"
      }
    }
    Ensure-ZipFallbackDependencies
  }

  Invoke-Step "configure pg_jieba" {
    $CMakeArgs = @(
      "-S",
      $SourceDir,
      "-B",
      $BuildDir,
      "-DPG_CONFIG=$PgConfig",
      "-DCMAKE_POLICY_VERSION_MINIMUM=3.5"
    )
    if ($env:OS -eq "Windows_NT") {
      New-WindowsCompatHeaders
      $PgLib = Join-Path $PostgresHome "lib"
      $CMakeArgs += @(
        "-DCMAKE_C_STANDARD=99",
        "-DCMAKE_CXX_STANDARD=20",
        "-DCMAKE_C_FLAGS=/DWIN32 /utf-8 /I$CompatDir",
        "-DCMAKE_CXX_FLAGS=/DWIN32 /utf-8 /EHsc /I$CompatDir /std:c++20",
        "-DCMAKE_SHARED_LINKER_FLAGS=/LIBPATH:$PgLib postgres.lib"
      )
    }
    Invoke-Native $CMakePath $CMakeArgs
  }

  Invoke-Step "build and install pg_jieba" {
    Invoke-Native $CMakePath @("--build", $BuildDir, "--config", "Release", "--target", "install")
    $LibPgJieba = Join-Path $PostgresHome "lib\libpg_jieba.dll"
    $PgJieba = Join-Path $PostgresHome "lib\pg_jieba.dll"
    if ((Test-Path $LibPgJieba) -and -not (Test-Path $PgJieba)) {
      Copy-Item -LiteralPath $LibPgJieba -Destination $PgJieba -Force
    }
  }

  if ($AdminPassword) {
    $env:PGPASSWORD = $AdminPassword
  }

  Invoke-Step "enable pg_jieba extension" {
    Invoke-Native $Psql @("-h", $HostName, "-p", "$Port", "-U", $AdminUser, "-d", $Database, "-v", "ON_ERROR_STOP=1", "-c", "create extension if not exists pg_jieba;")
    Invoke-Native $Psql @("-h", $HostName, "-p", "$Port", "-U", $AdminUser, "-d", $Database, "-v", "ON_ERROR_STOP=1", "-c", "select 'jiebacfg'::regconfig as jieba_config;")
  }

  Invoke-Step "rebuild keyword FTS indexes with jiebacfg" {
    $Sql = @"
drop index if exists ix_question_bank_items_keyword_fts;
drop index if exists ix_knowledge_chunks_keyword_fts;
create index ix_question_bank_items_keyword_fts
on question_bank_items using gin (
  (
    setweight(to_tsvector('jiebacfg', coalesce(stem, '') || ' ' || coalesce(knowledge_point, '')), 'A') ||
    setweight(to_tsvector('jiebacfg', coalesce(tags_json::text, '')), 'A') ||
    setweight(to_tsvector('jiebacfg', coalesce(options_json::text, '') || ' ' || coalesce(explanation, '') || ' ' || coalesce(difficulty, '')), 'B')
  )
);
create index ix_knowledge_chunks_keyword_fts
on knowledge_chunks using gin (
  (
    setweight(to_tsvector('jiebacfg', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('jiebacfg', coalesce(tags_json::text, '')), 'A') ||
    setweight(to_tsvector('jiebacfg', coalesce(content, '')), 'B') ||
    setweight(to_tsvector('jiebacfg', coalesce(source_ref, '')), 'D')
  )
);
"@
    $SqlFile = Join-Path $WorkDir "rebuild-keyword-fts.sql"
    Set-Content -Path $SqlFile -Value $Sql -Encoding UTF8
    Invoke-Native $Psql @("-h", $HostName, "-p", "$Port", "-U", $AdminUser, "-d", $Database, "-v", "ON_ERROR_STOP=1", "-f", $SqlFile)
  }

  Write-Host "pg_jieba installed and keyword FTS indexes rebuilt"
} catch {
  Write-Warning "pg_jieba install failed: $($_.Exception.Message)"
  Write-Warning "Brain Rush can still run with simple FTS and Python keyword fallback."
} finally {
  if ($AdminPassword) {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
  }
}
