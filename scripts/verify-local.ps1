# Sentinel Edge local verification runner.
# Runs the backend and frontend gates used before committing local changes.

param(
    [switch]$InstallBackendDevDeps,
    [switch]$InstallFrontendDeps,
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$SkipAudit
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$Backend = Join-Path $ProjectRoot "backend"
$Frontend = Join-Path $ProjectRoot "frontend"
$BackendPythonRelative = "backend\.venv\Scripts\python.exe"
$BackendPython = Join-Path $ProjectRoot $BackendPythonRelative

function Write-Status {
    param([string]$Message, [string]$Level = "INFO")
    $color = switch ($Level) {
        "OK" { "Green" }
        "ERROR" { "Red" }
        "WARN" { "Yellow" }
        default { "Cyan" }
    }
    Write-Host "[$Level] $Message" -ForegroundColor $color
}

function Find-CommandPath {
    param([string[]]$Names)
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    return $null
}

function Invoke-ExternalCommand {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )
    Write-Status $Name
    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList
        if ($LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE"
        }
        Write-Status "$Name passed" "OK"
    } finally {
        Pop-Location
    }
}

if (-not (Test-Path $Backend)) { throw "Backend folder not found: $Backend" }
if (-not (Test-Path $Frontend)) { throw "Frontend folder not found: $Frontend" }
if ((-not $SkipBackend -or $InstallBackendDevDeps) -and -not (Test-Path $BackendPython)) {
    throw "Backend virtualenv not found at $BackendPythonRelative. Run .\Launch-Sentinel-Edge-Local.ps1 -InstallDeps or create backend\.venv first."
}

if ($InstallBackendDevDeps) {
    Invoke-ExternalCommand `
        -Name "Install backend dev dependencies from requirements-dev.txt" `
        -FilePath $BackendPython `
        -ArgumentList @("-m", "pip", "install", "-r", "requirements-dev.txt") `
        -WorkingDirectory $Backend
} elseif (-not $SkipBackend) {
    & $BackendPython -c "import pytest" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dev dependencies are missing. Run .\scripts\verify-local.ps1 -InstallBackendDevDeps, then rerun verification."
    }
}

$git = Find-CommandPath -Names @("git.exe", "git")
if (-not $git) { throw "git was not found on PATH." }

if (-not $SkipBackend) {
    Invoke-ExternalCommand `
        -Name "Backend unittest discovery: -m unittest discover -s backend/tests" `
        -FilePath $BackendPython `
        -ArgumentList @("-m", "unittest", "discover", "-s", "backend/tests") `
        -WorkingDirectory $ProjectRoot

    Invoke-ExternalCommand `
        -Name 'Backend static unittest discovery: -m unittest discover -s backend/tests -p "test_*static.py"' `
        -FilePath $BackendPython `
        -ArgumentList @("-m", "unittest", "discover", "-s", "backend/tests", "-p", "test_*static.py") `
        -WorkingDirectory $ProjectRoot
}

if (-not $SkipFrontend) {
    $npm = Find-CommandPath -Names @("npm.cmd", "npm.exe", "npm")
    if (-not $npm) { throw "npm was not found on PATH." }

    $frontendNodeModules = Join-Path $Frontend "node_modules"
    if ($InstallFrontendDeps) {
        $frontendInstallArgs = if (Test-Path (Join-Path $Frontend "node_modules")) { @("install") } else { @("ci") }
        $frontendInstallCommand = if ($frontendInstallArgs[0] -eq "ci") { "npm ci" } else { "npm install" }
        Invoke-ExternalCommand `
            -Name "Install frontend dependencies: $frontendInstallCommand" `
            -FilePath $npm `
            -ArgumentList $frontendInstallArgs `
            -WorkingDirectory $Frontend
    } elseif (-not (Test-Path $frontendNodeModules)) {
        throw "frontend node_modules are missing. Run .\scripts\verify-local.ps1 -InstallFrontendDeps, then rerun verification."
    }

    Invoke-ExternalCommand `
        -Name "Frontend lint: npm run lint" `
        -FilePath $npm `
        -ArgumentList @("run", "lint") `
        -WorkingDirectory $Frontend

    Invoke-ExternalCommand `
        -Name "Frontend build: npm run build" `
        -FilePath $npm `
        -ArgumentList @("run", "build") `
        -WorkingDirectory $Frontend

    if (-not $SkipAudit) {
        Invoke-ExternalCommand `
            -Name "Frontend audit: npm audit --audit-level=moderate" `
            -FilePath $npm `
            -ArgumentList @("audit", "--audit-level=moderate") `
            -WorkingDirectory $Frontend
    }
}

Invoke-ExternalCommand `
    -Name "Workspace whitespace check: git diff --check" `
    -FilePath $git `
    -ArgumentList @("diff", "--check") `
    -WorkingDirectory $ProjectRoot

Write-Status "Local verification completed" "OK"
