# Sentinel Edge Local Source Launcher
# Runs the edited local source tree without building an installer.

param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 3001,
    [switch]$NoBrowser,
    [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $ProjectRoot) { $ProjectRoot = (Get-Location).Path }

$Backend = Join-Path $ProjectRoot "backend"
$Frontend = Join-Path $ProjectRoot "frontend"
$DesktopPath = [Environment]::GetFolderPath("Desktop")
if (-not $DesktopPath) { $DesktopPath = Join-Path $HOME "Desktop" }
$LogFile = Join-Path $DesktopPath "Sentinel-Edge-Local.log"

$OwnedProcesses = New-Object System.Collections.Generic.List[System.Diagnostics.Process]
$BrowserProcess = $null
$BrowserProfileDir = $null
$ShutdownStarted = $false
$CleanupEventSubscription = $null
$CancelKeyPressHandler = $null

function Write-Status {
    param([string]$Message, [string]$Level = "INFO")
    $color = switch ($Level) {
        "OK" { "Green" }
        "WARN" { "Yellow" }
        "ERROR" { "Red" }
        default { "Cyan" }
    }
    Write-Host "[$Level] $Message" -ForegroundColor $color
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    Add-Content -Path $LogFile -Value "$timestamp [$Level] $Message" -Encoding UTF8
}

function Test-PortOpen {
    param([int]$Port)
    try {
        $client = New-Object Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(750, $false)
        if ($connected) { $client.EndConnect($async) }
        $client.Close()
        return $connected
    } catch {
        return $false
    }
}

function Wait-Port {
    param([int]$Port, [int]$Seconds = 45)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    } catch {
        return $false
    }
}

function Wait-HttpOk {
    param([string]$Url, [int]$Seconds = 45)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk -Url $Url) { return $true }
        Start-Sleep -Milliseconds 750
    }
    return $false
}

function Get-Json {
    param([string]$Url)
    try {
        return Invoke-RestMethod -Uri $Url -TimeoutSec 3
    } catch {
        return $null
    }
}

function Test-FrontendIdentity {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return ($response.Content -match "Sentinel Edge")
    } catch {
        return $false
    }
}

function Get-PythonVersion {
    param(
        [string]$FilePath,
        [string[]]$ArgumentPrefix = @()
    )
    try {
        $args = @($ArgumentPrefix + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"))
        $version = (& $FilePath @args 2>$null | Select-Object -First 1)
        if (-not $version) { return $null }
        return [version]$version
    } catch {
        return $null
    }
}

function Test-CompatiblePythonVersion {
    param([version]$Version)
    return $Version -and $Version.Major -eq 3 -and $Version.Minor -ge 11 -and $Version.Minor -le 13
}

function Find-CompatiblePython {
    $candidates = New-Object System.Collections.Generic.List[object]
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($selector in @("-3.11", "-3.12", "-3.13")) {
            $candidates.Add([pscustomobject]@{
                FilePath = $py.Source
                ArgumentPrefix = @($selector)
                Label = "py $selector"
            })
        }
    }

    foreach ($name in @("python3.11.exe", "python3.12.exe", "python3.13.exe", "python.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            $candidates.Add([pscustomobject]@{
                FilePath = $cmd.Source
                ArgumentPrefix = @()
                Label = $cmd.Source
            })
        }
    }

    foreach ($candidate in $candidates) {
        $version = Get-PythonVersion -FilePath $candidate.FilePath -ArgumentPrefix $candidate.ArgumentPrefix
        if (Test-CompatiblePythonVersion -Version $version) {
            return [pscustomobject]@{
                FilePath = $candidate.FilePath
                ArgumentPrefix = $candidate.ArgumentPrefix
                Version = $version
                Label = $candidate.Label
            }
        }
    }
    return $null
}

function Invoke-CompatiblePython {
    param(
        [object]$PythonInfo,
        [string[]]$Arguments
    )
    $fullArgs = @($PythonInfo.ArgumentPrefix + $Arguments)
    & $PythonInfo.FilePath @fullArgs
}

function Find-Npm {
    foreach ($name in @("npm.cmd", "npm.exe", "npm")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

function Find-BrowserExecutable {
    $candidates = @(
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    foreach ($name in @("msedge.exe", "chrome.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

function Join-ProcessArguments {
    param([string[]]$Arguments)
    return (($Arguments | ForEach-Object {
        $arg = $_
        if ([string]::IsNullOrEmpty($arg)) {
            '""'
        } elseif ($arg -match '[\s"]') {
            '"' + $arg.Replace('"', '\"') + '"'
        } else {
            $arg
        }
    }) -join " ")
}

function Start-OwnedProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [switch]$Visible
    )
    $startParams = @{
        FilePath = $FilePath
        WorkingDirectory = $WorkingDirectory
        PassThru = $true
    }
    if ($ArgumentList -and $ArgumentList.Count -gt 0) {
        $startParams.ArgumentList = Join-ProcessArguments -Arguments $ArgumentList
    }
    if (-not $Visible) {
        $startParams.WindowStyle = "Hidden"
    }
    $process = Start-Process @startParams
    $OwnedProcesses.Add($process)
    return $process
}

function Start-BrowserWindow {
    param([string]$Url)
    $browserExe = Find-BrowserExecutable
    if ($browserExe) {
        Write-Status "Opening dedicated browser window"
        $script:BrowserProfileDir = Join-Path ([System.IO.Path]::GetTempPath()) "SentinelEdge-Local-Browser-$PID"
        New-Item -ItemType Directory -Path $script:BrowserProfileDir -Force | Out-Null
        $browserArgs = Join-ProcessArguments -Arguments @("--new-window", "--app=$Url", "--user-data-dir=$script:BrowserProfileDir", "--no-first-run", "--disable-background-mode")
        return Start-Process -FilePath $browserExe -ArgumentList $browserArgs -PassThru
    }

    Write-Status "Opening default browser without close monitoring" "WARN"
    Start-Process $Url | Out-Null
    return $null
}

function Stop-ProcessTree {
    param([int]$ProcessId)
    try {
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue)
        foreach ($child in $children) {
            Stop-ProcessTree -ProcessId $child.ProcessId
        }
        $current = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($current) {
            Write-Status "Stopping process $($current.ProcessName) ($($current.Id))"
            Stop-Process -Id $current.Id -Force -ErrorAction SilentlyContinue
        }
    } catch {
    }
}

function Stop-OwnedProcesses {
    for ($i = $OwnedProcesses.Count - 1; $i -ge 0; $i--) {
        $process = $OwnedProcesses[$i]
        Stop-ProcessTree -ProcessId $process.Id
    }
}

function Stop-BrowserWindow {
    if ($BrowserProcess) {
        try {
            $current = Get-Process -Id $BrowserProcess.Id -ErrorAction SilentlyContinue
            if ($current) {
                $current.CloseMainWindow() | Out-Null
                Start-Sleep -Milliseconds 500
                $current = Get-Process -Id $BrowserProcess.Id -ErrorAction SilentlyContinue
                if ($current) { Stop-Process -Id $current.Id -Force -ErrorAction SilentlyContinue }
            }
        } catch {
        }
    }
    if ($BrowserProfileDir -and (Test-Path $BrowserProfileDir)) {
        Remove-Item -LiteralPath $BrowserProfileDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-LauncherCleanup {
    if ($script:ShutdownStarted) { return }
    $script:ShutdownStarted = $true
    Stop-BrowserWindow
    Stop-OwnedProcesses
}

function Register-LauncherShutdownHandlers {
    try {
        $script:CleanupEventSubscription = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
            Invoke-LauncherCleanup
        }
    } catch {
    }
    try {
        $script:CancelKeyPressHandler = [ConsoleCancelEventHandler]{
            param($sender, $eventArgs)
            $eventArgs.Cancel = $true
            Write-Status "Shutdown requested; closing browser and processes" "WARN"
            Invoke-LauncherCleanup
            exit 0
        }
        [Console]::CancelKeyPress += $script:CancelKeyPressHandler
    } catch {
    }
}

Register-LauncherShutdownHandlers

try {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Sentinel Edge - Local Source" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Status "Project root: $ProjectRoot"
    Write-Status "Local log: $LogFile"

    if (-not (Test-Path $Backend)) { throw "Backend folder not found: $Backend" }
    if (-not (Test-Path $Frontend)) { throw "Frontend folder not found: $Frontend" }

    $venvPath = Join-Path $Backend ".venv"
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (Test-Path $venvPython) {
        $venvVersion = Get-PythonVersion -FilePath $venvPython
        if (-not (Test-CompatiblePythonVersion -Version $venvVersion)) {
            Write-Status "Backend virtual environment uses Python $venvVersion; recreating with Python 3.11-3.13" "WARN"
            Remove-Item -LiteralPath $venvPath -Recurse -Force
        }
    }

    if (-not (Test-Path $venvPython)) {
        $pythonInfo = Find-CompatiblePython
        if (-not $pythonInfo) {
            throw "A compatible Python was not found. Sentinel Edge local source requires Python 3.11-3.13. Install Python 3.11 and rerun."
        }
        Write-Status "Creating backend virtual environment with $($pythonInfo.Label) ($($pythonInfo.Version))"
        Invoke-CompatiblePython -PythonInfo $pythonInfo -Arguments @("-m", "venv", $venvPath)
        $InstallDeps = $true
    }

    if ($InstallDeps) {
        Write-Status "Installing backend dependencies"
        & $venvPython -m pip install --retries 10 --timeout 180 --prefer-binary -r (Join-Path $Backend "requirements.txt")
    }

    $npm = Find-Npm
    if (-not $npm) { throw "npm was not found. Install Node.js." }
    if ($InstallDeps -or -not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Status "Installing frontend dependencies"
        Start-OwnedProcess -FilePath $npm -ArgumentList @("install") -WorkingDirectory $Frontend -Visible | Wait-Process
    }

    $backendUrl = "http://127.0.0.1:$BackendPort"
    $frontendUrl = "http://127.0.0.1:$FrontendPort"
    $env:PORT = "$BackendPort"
    $env:SENTINEL_EDGE_PORT = "$BackendPort"
    $env:SENTINEL_EDGE_HOST = "127.0.0.1"
    $env:SENTINEL_EDGE_OPEN_BROWSER = "false"
    $env:SENTINEL_EDGE_UI_URL = $frontendUrl
    $env:REACT_APP_BACKEND_URL = $backendUrl
    $backendReadyUrl = "$backendUrl/api/ready"

    if ($env:DEMO_MODE -and ($env:DEMO_MODE).ToLowerInvariant() -in @("true", "1", "yes")) {
        Write-Status "Clearing removed DEMO_MODE=$env:DEMO_MODE; local source launcher requires production dependencies" "WARN"
    }
    $env:DEMO_MODE = "false"

    $localCorsOrigins = @(
        "http://localhost:$FrontendPort",
        "http://127.0.0.1:$FrontendPort",
        "http://localhost:$BackendPort",
        "http://127.0.0.1:$BackendPort"
    ) -join ","
    if (-not $env:CORS_ORIGINS) {
        $env:CORS_ORIGINS = $localCorsOrigins
    }

    if (-not (Test-PortOpen -Port $BackendPort)) {
        Write-Status "Starting backend from source on port $BackendPort"
        Start-OwnedProcess -FilePath $venvPython -ArgumentList @("-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "$BackendPort", "--reload") -WorkingDirectory $Backend | Out-Null
        if (-not (Wait-Port -Port $BackendPort -Seconds 60)) {
            throw "Backend did not open port $BackendPort. Check $LogFile."
        }
        if (-not (Wait-HttpOk -Url $backendReadyUrl -Seconds 60)) {
            throw "Backend opened port $BackendPort but did not become ready at $backendReadyUrl. Check $LogFile."
        }
        Write-Status "Backend is ready" "OK"
    } else {
        Write-Status "Backend already running on port $BackendPort" "WARN"
        if (-not (Wait-HttpOk -Url $backendReadyUrl -Seconds 15)) {
            Write-Status "Backend port is open, but $backendReadyUrl did not return ready" "WARN"
        }
    }

    $readySnapshot = Get-Json -Url $backendReadyUrl
    if ($readySnapshot -and $readySnapshot.checks -and $readySnapshot.checks.demo_mode -eq $true) {
        throw "Backend on port $BackendPort reports removed demo_mode=true. Stop that backend and relaunch in production mode."
    }

    if (-not (Test-PortOpen -Port $FrontendPort)) {
        Write-Status "Starting Vite frontend from source on port $FrontendPort"
        Start-OwnedProcess -FilePath $npm -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort") -WorkingDirectory $Frontend | Out-Null
        if (-not (Wait-Port -Port $FrontendPort -Seconds 60)) {
            throw "Frontend did not open port $FrontendPort. Check $LogFile."
        }
        if (-not (Wait-HttpOk -Url $frontendUrl -Seconds 60) -or -not (Test-FrontendIdentity -Url $frontendUrl)) {
            throw "Frontend opened port $FrontendPort but did not serve the Sentinel Edge UI. Check $LogFile."
        }
        Write-Status "Frontend is ready" "OK"
    } else {
        Write-Status "Frontend already running on port $FrontendPort" "WARN"
        if (-not (Test-FrontendIdentity -Url $frontendUrl)) {
            throw "Frontend port $FrontendPort is already in use, but it is not serving the Sentinel Edge UI. Choose -FrontendPort or stop the conflicting service."
        }
    }

    if (-not $NoBrowser) {
        $BrowserProcess = Start-BrowserWindow -Url $frontendUrl
    }

    Write-Host ""
    Write-Host "Ready: $frontendUrl" -ForegroundColor Green
    Write-Host "Backend: $backendUrl" -ForegroundColor Gray
    Write-Host "Mode: production" -ForegroundColor Gray
    Write-Host "Close this window or press Ctrl+C to stop processes started by this launcher." -ForegroundColor Gray
    Write-Host ""

    while ($true) {
        foreach ($process in @($OwnedProcesses)) {
            if ($process.HasExited) {
                throw "Process $($process.Id) exited unexpectedly."
            }
        }
        Start-Sleep -Seconds 1
    }
} catch {
    Write-Status $_.Exception.Message "ERROR"
    exit 1
} finally {
    Invoke-LauncherCleanup
}
