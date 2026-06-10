# Sentinel Edge local verification runner.
# Runs the backend and frontend gates used before committing local changes.

param(
    [switch]$InstallBackendDevDeps,
    [switch]$InstallFrontendDeps,
    [string]$SummaryPath,
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
$VerificationStartedAt = Get-Date
$VerificationResults = New-Object System.Collections.Generic.List[object]

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

function Add-VerificationResult {
    param(
        [string]$Name,
        [string]$Status,
        [object]$ExitCode,
        [string]$WorkingDirectory,
        [double]$DurationSeconds,
        [object]$ErrorMessage = $null,
        [object]$Reason = $null
    )
    $VerificationResults.Add([pscustomobject]@{
        name = $Name
        status = $Status
        exit_code = $ExitCode
        duration_seconds = [math]::Round($DurationSeconds, 3)
        working_directory = $WorkingDirectory
        error = $ErrorMessage
        reason = $Reason
    })
}

function Add-VerificationSkipped {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Reason
    )
    Write-Status "$Name skipped: $Reason" "WARN"
    Add-VerificationResult `
        -Name $Name `
        -Status "skipped" `
        -ExitCode $null `
        -WorkingDirectory $WorkingDirectory `
        -DurationSeconds 0 `
        -ErrorMessage $null `
        -Reason $Reason
}

function Test-VerificationFailed {
    foreach ($result in $VerificationResults) {
        if ($result.status -eq "failed") { return $true }
    }
    return $false
}

function Get-VerificationCounts {
    $counts = [ordered]@{
        total = $VerificationResults.Count
        passed = 0
        failed = 0
        skipped = 0
    }
    foreach ($result in $VerificationResults) {
        switch ($result.status) {
            "passed" { $counts.passed += 1 }
            "failed" { $counts.failed += 1 }
            "skipped" { $counts.skipped += 1 }
        }
    }
    return [pscustomobject]$counts
}

function Write-VerificationSummary {
    if ([string]::IsNullOrWhiteSpace($SummaryPath)) { return }

    $summaryTarget = if ([System.IO.Path]::IsPathRooted($SummaryPath)) {
        $SummaryPath
    } else {
        Join-Path $ProjectRoot $SummaryPath
    }
    $summaryDirectory = Split-Path -Parent $summaryTarget
    if ($summaryDirectory -and -not (Test-Path $summaryDirectory)) {
        New-Item -ItemType Directory -Path $summaryDirectory -Force | Out-Null
    }

    $endedAt = Get-Date
    $summary = [pscustomobject]@{
        status = if (Test-VerificationFailed) { "failed" } else { "passed" }
        started_at = $VerificationStartedAt.ToUniversalTime().ToString("o")
        ended_at = $endedAt.ToUniversalTime().ToString("o")
        duration_seconds = [math]::Round(($endedAt - $VerificationStartedAt).TotalSeconds, 3)
        counts = Get-VerificationCounts
        project_root = $ProjectRoot
        results = @($VerificationResults.ToArray())
    }
    $summary | ConvertTo-Json -Depth 5 | Set-Content -Path $summaryTarget -Encoding UTF8
    Write-Status "verification summary written: $summaryTarget" "OK"
}

function Invoke-ExternalCommand {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )
    $startedAt = Get-Date
    $status = "passed"
    [object]$exitCode = $null
    [object]$errorMessage = $null
    Write-Status $Name
    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList
        $exitCode = $LASTEXITCODE
        if ($LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE"
        }
        Write-Status "$Name passed" "OK"
    } catch {
        $status = "failed"
        if ($null -eq $exitCode) {
            $exitCode = Get-Variable -Name LASTEXITCODE -ValueOnly -ErrorAction SilentlyContinue
        }
        $errorMessage = $_.Exception.Message
        throw
    } finally {
        Pop-Location
        Add-VerificationResult `
            -Name $Name `
            -Status $status `
            -ExitCode $exitCode `
            -WorkingDirectory $WorkingDirectory `
            -DurationSeconds ((Get-Date) - $startedAt).TotalSeconds `
            -ErrorMessage $errorMessage
    }
}

try {
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
} else {
    Add-VerificationSkipped `
        -Name "Backend verification" `
        -WorkingDirectory $ProjectRoot `
        -Reason "-SkipBackend was supplied"
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
    } else {
        Add-VerificationSkipped `
            -Name "Frontend audit: npm audit --audit-level=moderate" `
            -WorkingDirectory $Frontend `
            -Reason "-SkipAudit was supplied"
    }
} else {
    Add-VerificationSkipped `
        -Name "Frontend verification" `
        -WorkingDirectory $Frontend `
        -Reason "-SkipFrontend was supplied"
}

Invoke-ExternalCommand `
    -Name "Workspace whitespace check: git diff --check" `
    -FilePath $git `
    -ArgumentList @("diff", "--check") `
    -WorkingDirectory $ProjectRoot

Write-Status "Local verification completed" "OK"
} catch {
    if (-not (Test-VerificationFailed)) {
        Add-VerificationResult `
            -Name "Local verification" `
            -Status "failed" `
            -ExitCode (Get-Variable -Name LASTEXITCODE -ValueOnly -ErrorAction SilentlyContinue) `
            -WorkingDirectory $ProjectRoot `
            -DurationSeconds ((Get-Date) - $VerificationStartedAt).TotalSeconds `
            -ErrorMessage $_.Exception.Message
    }
    throw
} finally {
    Write-VerificationSummary
}
