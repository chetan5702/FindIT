[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "help", "setup", "up", "up-detached", "down", "logs", "ps",
        "migrate", "seed", "create-admin", "test", "test-backend",
        "test-frontend", "install-e2e", "test-e2e", "backend-shell"
    )]
    [string] $Command = "help",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CommandArguments
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function New-RandomHex {
    param([int] $ByteCount = 32)

    $Bytes = New-Object byte[] $ByteCount
    $Generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $Generator.GetBytes($Bytes)
    }
    finally {
        $Generator.Dispose()
    }
    return -join ($Bytes | ForEach-Object { $_.ToString("x2") })
}

function Assert-DockerCompose {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker was not found. Install Docker Desktop (with Compose v2) and try again."
    }

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker compose version 2> $null | Out-Null
    $ComposeExitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    if ($ComposeExitCode -ne 0) {
        throw "Docker Compose v2 is unavailable. Start or update Docker Desktop and try again."
    }
}

function Initialize-Environment {
    $ExamplePath = Join-Path $ProjectRoot ".env.example"
    $EnvironmentPath = Join-Path $ProjectRoot ".env"

    if (Test-Path -LiteralPath $EnvironmentPath) {
        Write-Host ".env already exists; it was left unchanged."
        return
    }

    $PostgresPassword = New-RandomHex 24
    $SessionSecret = New-RandomHex 48
    $Contents = Get-Content -LiteralPath $ExamplePath -Raw
    $Contents = $Contents.Replace("CHANGE_ME_POSTGRES_PASSWORD", $PostgresPassword)
    $Contents = $Contents.Replace("CHANGE_ME_SESSION_SECRET", $SessionSecret)
    $Utf8WithoutBom = New-Object Text.UTF8Encoding $false
    [IO.File]::WriteAllText($EnvironmentPath, $Contents, $Utf8WithoutBom)
    Write-Host "Created .env with random local-development secrets."
}

function Assert-Environment {
    $EnvironmentPath = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path -LiteralPath $EnvironmentPath)) {
        throw "Missing .env. Run './scripts/dev.ps1 setup' first."
    }

    $Contents = Get-Content -LiteralPath $EnvironmentPath -Raw
    $ConfiguredLines = ($Contents -split "\r?\n" | Where-Object {
        -not $_.TrimStart().StartsWith("#")
    }) -join "`n"
    if ($ConfiguredLines.Contains("CHANGE_ME")) {
        throw ".env still contains CHANGE_ME placeholders. Replace them before starting the app."
    }
}

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Arguments)

    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose exited with code $LASTEXITCODE."
    }
}

function Assert-HostNode {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm was not found. Install Node.js 20.19 or newer for host-side Playwright tests."
    }
}

function Invoke-FrontendHostCommand {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Arguments)

    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        & npm @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "npm exited with code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

function Show-Help {
    @"
FindIt Next development commands

  setup          Create .env with random development secrets
  up             Build and run all services in the foreground
  up-detached    Build and run all services in the background
  down           Stop services without deleting persistent data
  logs           Follow recent service logs
  ps             Show service and health status
  migrate        Apply all database migrations
  seed           Load safe development demo data
  create-admin   Interactively create the first administrator
  test           Run backend and frontend unit/component tests
  test-backend   Run pytest
  test-frontend  Run Vitest once
  install-e2e    Install host dependencies and Playwright Chromium once
  test-e2e       Run host-side Playwright against running services
  backend-shell  Open a shell in the running backend container

Examples:
  ./scripts/dev.ps1 setup
  ./scripts/dev.ps1 up
  ./scripts/dev.ps1 create-admin
"@ | Write-Host
}

Push-Location $ProjectRoot
try {
    switch ($Command) {
        "help" { Show-Help; break }
        "setup" { Initialize-Environment; break }
        "install-e2e" { Assert-HostNode; break }
        "test-e2e" { Assert-HostNode; break }
        default {
            Assert-DockerCompose
            Assert-Environment
        }
    }

    switch ($Command) {
        "up" { Invoke-Compose up --build }
        "up-detached" { Invoke-Compose up --build --detach }
        "down" { Invoke-Compose down }
        "logs" { Invoke-Compose logs --follow --tail 200 @CommandArguments }
        "ps" { Invoke-Compose ps }
        "migrate" { Invoke-Compose run --rm backend alembic upgrade head }
        "seed" { Invoke-Compose exec backend python -m app.seed }
        "create-admin" { Invoke-Compose exec backend python -m app.cli create-admin @CommandArguments }
        "test-backend" { Invoke-Compose run --rm backend pytest -q @CommandArguments }
        "test-frontend" { Invoke-Compose run --rm frontend npm test -- --run @CommandArguments }
        "install-e2e" {
            Invoke-FrontendHostCommand ci
            Invoke-FrontendHostCommand exec playwright install chromium
        }
        "test-e2e" {
            if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "frontend/node_modules"))) {
                throw "Frontend host dependencies are missing. Run './scripts/dev.ps1 install-e2e' first."
            }
            Invoke-FrontendHostCommand run test:e2e -- @CommandArguments
        }
        "backend-shell" { Invoke-Compose exec backend /bin/sh }
        "test" {
            Invoke-Compose run --rm backend pytest -q
            Invoke-Compose run --rm frontend npm test -- --run
        }
    }
}
finally {
    Pop-Location
}

