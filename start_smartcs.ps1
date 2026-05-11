param(
    [switch]$SkipSeed,
    [switch]$Mock,
    [switch]$NoInstall,
    [switch]$NoDocker,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".conda\python.exe"
$Node = Join-Path $Root ".conda\node.exe"
$Npm = Join-Path $Root ".conda\npm.cmd"
$Logs = Join-Path $Root "logs"
$Tmp = Join-Path $Root ".tmp"

Set-Location $Root
New-Item -ItemType Directory -Force -Path $Logs, $Tmp | Out-Null

if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
    $processPath = [Environment]::GetEnvironmentVariable("Path", "Process")
    if (![string]::IsNullOrWhiteSpace($processPath)) {
        [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
        [Environment]::SetEnvironmentVariable("Path", $processPath, "Process")
    }
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Set-DefaultEnv {
    param([string]$Name, [string]$Value)
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name, "Process"))) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
    }
}

function Load-EnvFile {
    param([string]$Path)
    if (!(Test-Path -LiteralPath $Path)) {
        return
    }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (!$line -or $line.StartsWith("#")) {
            return
        }
        $index = $line.IndexOf("=")
        if ($index -le 0) {
            return
        }
        $key = $line.Substring(0, $index).Trim()
        $value = $line.Substring($index + 1).Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

function Ensure-CondaEnv {
    if (Test-Path -LiteralPath $Python) {
        return
    }
    Write-Step "Creating local conda environment"
    $conda = Get-Command conda -ErrorAction SilentlyContinue
    if (!$conda) {
        throw "Conda was not found. Install Miniconda/Anaconda, then run this script again."
    }
    Set-DefaultEnv "CONDA_PKGS_DIRS" (Join-Path $Root ".conda_pkgs")
    & conda env create --prefix (Join-Path $Root ".conda") --file (Join-Path $Root "environment.yml")
}

function Ensure-BackendDeps {
    if ($NoInstall) {
        return
    }
    Write-Step "Checking Python dependencies"
    & $Python -c "import fastapi, uvicorn, psycopg, redis, qdrant_client" 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $Python -m pip install -e "$Root\backend[dev]"
    }
}

function Ensure-FrontendDeps {
    if ($NoInstall) {
        return
    }
    Write-Step "Checking frontend dependencies"
    $vite = Join-Path $Root "frontend\node_modules\vite\bin\vite.js"
    if (!(Test-Path -LiteralPath $vite)) {
        Set-DefaultEnv "npm_config_cache" (Join-Path $Root ".npm_cache")
        Push-Location (Join-Path $Root "frontend")
        try {
            & $Npm install
        }
        finally {
            Pop-Location
        }
    }
}

function Stop-ProjectProcessOnPort {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $ownerPid = $connection.OwningProcess
        if (!$ownerPid) {
            continue
        }
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerPid" -ErrorAction SilentlyContinue
        $commandLine = $processInfo.CommandLine
        $exePath = $processInfo.ExecutablePath
        $belongsToProject =
            ($commandLine -and $commandLine.Contains($Root)) -or
            ($exePath -and $exePath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase))

        if ($belongsToProject) {
            Write-Host "Stopping previous project process on port $Port (PID $ownerPid)"
            Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
        }
        else {
            throw "Port $Port is already used by PID $ownerPid outside this project. Stop it first or change the port."
        }
    }
}

function Wait-Http {
    param([string]$Url, [string]$Name, [int]$TimeoutSeconds = 45)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "$Name is ready: $Url" -ForegroundColor Green
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 800
        }
    } while ((Get-Date) -lt $deadline)
    throw "$Name did not become ready in $TimeoutSeconds seconds. Check logs in $Logs."
}

$EnvPath = Join-Path $Root ".env"
$ExampleEnvPath = Join-Path $Root ".env.example"
Load-EnvFile $EnvPath

Set-DefaultEnv "APP_ENV" "local"
Set-DefaultEnv "LOG_LEVEL" "INFO"
Set-DefaultEnv "DATA_BACKEND" "postgres"
Set-DefaultEnv "REDIS_BACKEND" "redis"
Set-DefaultEnv "KB_BACKEND" "qdrant"
Set-DefaultEnv "DATABASE_URL" "postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs"
Set-DefaultEnv "REDIS_URL" "redis://localhost:6379/0"
Set-DefaultEnv "QDRANT_URL" "http://localhost:6333"
Set-DefaultEnv "QDRANT_COLLECTION" "smartcs_kb"

if ($Mock) {
    [Environment]::SetEnvironmentVariable("LLM_PROVIDER", "mock", "Process")
}
elseif (![string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    Set-DefaultEnv "LLM_PROVIDER" "openai-compatible"
    Set-DefaultEnv "OPENAI_API_BASE" "https://api.openai.com/v1"
    Set-DefaultEnv "MODEL_NAME" "gpt-4o-mini"
    Set-DefaultEnv "LLM_MODEL" $env:MODEL_NAME
    [Environment]::SetEnvironmentVariable("MOCK_MODE", "false", "Process")
}
else {
    Set-DefaultEnv "LLM_PROVIDER" "mock"
    Set-DefaultEnv "LLM_MODEL" "gpt-4o-mini"
    Write-Host "OPENAI_API_KEY not found. Starting in mock LLM mode. Copy .env.example to .env for real API mode." -ForegroundColor Yellow
    if (!(Test-Path -LiteralPath $EnvPath) -and (Test-Path -LiteralPath $ExampleEnvPath)) {
        Write-Host "Tip: Copy-Item .env.example .env" -ForegroundColor Yellow
    }
}

Ensure-CondaEnv
Ensure-BackendDeps
Ensure-FrontendDeps

if (!$NoDocker) {
    Write-Step "Starting PostgreSQL, Redis, and Qdrant"
    docker compose up -d postgres redis qdrant
}

if (!$SkipSeed) {
    Write-Step "Seeding demo data"
    & $Python (Join-Path $Root "scripts\seed_demo_data.py")
}

Write-Step "Starting backend and frontend"
Stop-ProjectProcessOnPort 8000
Stop-ProjectProcessOnPort 5173

$backendOut = Join-Path $Logs "backend.out.log"
$backendErr = Join-Path $Logs "backend.err.log"
$frontendOut = Join-Path $Logs "frontend.out.log"
$frontendErr = Join-Path $Logs "frontend.err.log"
Remove-Item -LiteralPath $backendOut, $backendErr, $frontendOut, $frontendErr -ErrorAction SilentlyContinue

$backend = Start-Process `
    -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "app.api.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr `
    -PassThru

$frontend = Start-Process `
    -FilePath $Node `
    -ArgumentList @("node_modules\vite\bin\vite.js", "--host", "127.0.0.1") `
    -WorkingDirectory (Join-Path $Root "frontend") `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr `
    -PassThru

Wait-Http "http://127.0.0.1:8000/health" "Backend"
Wait-Http "http://127.0.0.1:5173" "Frontend"

Write-Host ""
Write-Host "SmartCS Agent Desk is running." -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Backend:  http://127.0.0.1:8000/docs"
Write-Host "Qdrant:   http://127.0.0.1:6333/dashboard"
Write-Host "Backend PID:  $($backend.Id)"
Write-Host "Frontend PID: $($frontend.Id)"
Write-Host "Logs: $Logs"

if (!$NoBrowser) {
    Start-Process "http://127.0.0.1:5173"
}
