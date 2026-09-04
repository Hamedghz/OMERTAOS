Write-Host "Running OMERTAOS tests..."

$failures = New-Object System.Collections.Generic.List[string]

function Invoke-Check {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Name"
    $global:LASTEXITCODE = 0

    try {
        & $Action
        $exitCode = $LASTEXITCODE
    } catch {
        Write-Host "FAILED: $Name - $($_.Exception.Message)" -ForegroundColor Red
        $failures.Add($Name)
        return
    }

    if ($exitCode -ne 0) {
        Write-Host "FAILED: $Name (exit $exitCode)" -ForegroundColor Red
        $failures.Add($Name)
    } else {
        Write-Host "PASSED: $Name" -ForegroundColor Green
    }
}

$python = $null
if (Test-Path ".\.venv\Scripts\python.exe") {
    $python = ".\.venv\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
}

if ($python -and (Test-Path ".\tests\architecture")) {
    Invoke-Check "Python architecture tests" {
        if ($python -eq "py") {
            & $python -3 -m pytest tests/architecture -q -k "not test_structure_migration_gate"
        } else {
            & $python -m pytest tests/architecture -q -k "not test_structure_migration_gate"
        }
    }
} elseif (Test-Path ".\tests") {
    Write-Host "Python interpreter not found; Python tests cannot run."
    $failures.Add("Python architecture tests")
}

if (Get-Command npm -ErrorAction SilentlyContinue) {
    if ((Test-Path ".\gateway\package.json") -and (Test-Path ".\tests\gateway")) {
        Invoke-Check "Gateway unit tests" {
            Push-Location ".\gateway"
            $hadToken = Test-Path Env:OMERTA_GATEWAY_ADMIN_TOKEN
            $oldToken = $env:OMERTA_GATEWAY_ADMIN_TOKEN
            $hadNodeEnv = Test-Path Env:NODE_ENV
            $oldNodeEnv = $env:NODE_ENV
            try {
                # Use deterministic, non-secret test values and restore the
                # caller's environment in the finally block.
                $env:OMERTA_GATEWAY_ADMIN_TOKEN = "test-only-admin-token"
                $env:NODE_ENV = "development"
                npm exec -- vitest run --root .. tests/gateway
            } finally {
                if ($hadToken) {
                    $env:OMERTA_GATEWAY_ADMIN_TOKEN = $oldToken
                } else {
                    Remove-Item Env:OMERTA_GATEWAY_ADMIN_TOKEN -ErrorAction SilentlyContinue
                }
                if ($hadNodeEnv) {
                    $env:NODE_ENV = $oldNodeEnv
                } else {
                    Remove-Item Env:NODE_ENV -ErrorAction SilentlyContinue
                }
                Pop-Location
            }
        }
    }

    if (Test-Path ".\console\package.json") {
        Invoke-Check "Console unit tests" {
            Push-Location ".\console"
            try {
                npm run test -- --config vitest.config.mts
            } finally {
                Pop-Location
            }
        }
    }
} else {
    Write-Host "npm not found; Node tests cannot run."
    $failures.Add("Node tests")
}

if ((Get-Command cargo -ErrorAction SilentlyContinue) -and (Test-Path ".\runtime-daemon\Cargo.toml")) {
    Invoke-Check "Runtime manifest contract" {
        cargo metadata --manifest-path runtime-daemon/Cargo.toml --no-deps --format-version 1 | Out-Null
    }
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Targeted test failures: $($failures -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "All targeted OMERTAOS tests passed." -ForegroundColor Green
