param(
    [switch]$WithServices,
    [string]$ApiUrl = "http://127.0.0.1:8000/health"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".conda\python.exe"
$Node = Join-Path $Root ".conda\node.exe"

if (-not (Test-Path $Python)) {
    $Python = "python"
}
if (-not (Test-Path $Node)) {
    $Node = "node"
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-Host ""
    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Push-Location $Root
try {
    Invoke-Step "ruff" { & $Python -m ruff check backend/app backend/tests }
    Invoke-Step "mypy" { & $Python -m mypy backend/app --ignore-missing-imports }

    if ($WithServices) {
        Invoke-Step "docker services" { docker compose up -d postgres redis qdrant }
        $env:SMARTCS_RUN_INTEGRATION = "1"
        $env:DATA_BACKEND = "postgres"
        $env:REDIS_BACKEND = "redis"
        $env:KB_BACKEND = "qdrant"
        $env:DATABASE_URL = "postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs"
        $env:REDIS_URL = "redis://localhost:6379/0"
        $env:QDRANT_URL = "http://localhost:6333"
    }

    Invoke-Step "pytest" { & $Python -m pytest backend }
    Invoke-Step "frontend build" {
        Push-Location (Join-Path $Root "frontend")
        try {
            $env:npm_config_cache = Join-Path $Root ".npm_cache"
            & $Node node_modules\typescript\bin\tsc --noEmit
            if ($LASTEXITCODE -ne 0) {
                throw "tsc failed with exit code $LASTEXITCODE"
            }
            Start-Sleep -Milliseconds 500
            & $Node node_modules\vite\bin\vite.js build
            if ($LASTEXITCODE -ne 0) {
                throw "vite build failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }
    }

    if ($WithServices) {
        & $Python scripts/check_health.py `
            --url $ApiUrl `
            --expect repository_backend=postgresql `
            --expect runtime_backend=redis `
            --expect knowledge_backend=qdrant | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Invoke-Step "health" {
                & $Python scripts/check_health.py `
                    --url $ApiUrl `
                    --expect repository_backend=postgresql `
                    --expect runtime_backend=redis `
                    --expect knowledge_backend=qdrant
            }
            return
        }

        $Backend = Start-Job -ScriptBlock {
            param($RootPath, $PythonPath)
            Set-Location $RootPath
            & $PythonPath -m uvicorn app.api.main:app --app-dir backend --host 127.0.0.1 --port 8000
        } -ArgumentList $Root, $Python
        try {
            $Ready = $false
            for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
                Start-Sleep -Seconds 1
                & $Python scripts/check_health.py --url $ApiUrl | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $Ready = $true
                    break
                }
            }
            if (-not $Ready) {
                throw "FastAPI health endpoint did not become ready."
            }
            Invoke-Step "health" {
                & $Python scripts/check_health.py `
                    --url $ApiUrl `
                    --expect repository_backend=postgresql `
                    --expect runtime_backend=redis `
                    --expect knowledge_backend=qdrant
            }
        }
        finally {
            if ($Backend) {
                Stop-Job -Job $Backend -ErrorAction SilentlyContinue
                Remove-Job -Job $Backend -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
finally {
    Pop-Location
}
