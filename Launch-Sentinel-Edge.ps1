# Sentinel Edge Launcher
# Starts MongoDB and Sentinel Edge from the installed Windows package.

param(
    [string]$MongoPath = "",
    [string]$DataPath = "",
    [string]$LogPath = "",
    [int]$MongoPort = 27017,
    [int]$AppPort = 8001,
    [switch]$NoBrowser,
    [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $ProjectRoot) { $ProjectRoot = (Get-Location).Path }

$DesktopPath = [Environment]::GetFolderPath("Desktop")
if (-not $DesktopPath) { $DesktopPath = Join-Path $HOME "Desktop" }

if (-not $DataPath) { $DataPath = Join-Path $ProjectRoot "data" }
if (-not $LogPath) { $LogPath = $DesktopPath }

$OwnedProcesses = New-Object System.Collections.Generic.List[System.Diagnostics.Process]
$LogFile = Join-Path $LogPath "Sentinel-Edge.log"
$TranscriptFile = Join-Path $LogPath "Sentinel-Edge-Transcript.log"
$TranscriptStarted = $false
$BrowserProcess = $null
$BrowserProfileDir = $null
$BrowserProcessIds = @()
$BrowserWindowProcessIds = @()
$BrowserStartedAt = $null
$BrowserMonitorDisabled = $false
$ShutdownStarted = $false
$CleanupEventSubscription = $null
$CancelKeyPressHandler = $null
$LauncherWatchdogProcess = $null
$LauncherWatchdogStopFile = $null
$LauncherWatchdogScriptFile = $null
$VcRedistUrl = "https://aka.ms/vc14/vc_redist.x64.exe"
$MongoPortableVersion = "8.0.26"
$MongoPortableZipUrl = "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.0.26.zip"
$MongoPortableMsiUrl = "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.0.26-signed.msi"
$DependencyRoot = if ($env:LOCALAPPDATA) {
    Join-Path $env:LOCALAPPDATA "Sentinel Edge\dependencies"
} else {
    Join-Path $ProjectRoot ".dependencies"
}

function Write-Status {
    param([string]$Message, [string]$Level = "INFO")
    $color = switch ($Level) {
        "OK" { "Green" }
        "WARN" { "Yellow" }
        "ERROR" { "Red" }
        default { "Cyan" }
    }
    Write-Host "[$Level] $Message" -ForegroundColor $color
    if (Test-Path $LogPath) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
        Add-Content -Path $LogFile -Value "$timestamp [$Level] $Message" -Encoding UTF8
    }
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

function Test-MongoPort {
    param([int]$Port)
    return (Test-PortOpen -Port $Port)
}

function Wait-Port {
    param([int]$Port, [int]$Seconds = 30)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Test-SentinelEdgeReady {
    param([int]$Port)
    try {
        $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/ready" -Method Get -TimeoutSec 3
        return [bool]$ready.ready
    } catch {
        return $false
    }
}

function Wait-SentinelEdgeReady {
    param([int]$Port, [int]$Seconds = 45)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-SentinelEdgeReady -Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Wait-PortAttempts {
    param([int]$Port, [int]$Attempts = 3, [int]$IntervalSeconds = 3)
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        Start-Sleep -Seconds $IntervalSeconds
        if (Test-PortOpen -Port $Port) {
            Write-Status "Port $Port opened on check $attempt of $Attempts" "OK"
            return $true
        }
        Write-Status "Port $Port not open yet; check $attempt of $Attempts" "WARN"
    }
    return $false
}

function Test-ProcessElevated {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Test-VcRuntimeInstalled {
    $keys = @(
        "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
    )

    foreach ($key in $keys) {
        try {
            $runtime = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
            if ($runtime -and $runtime.Installed -eq 1) { return $true }
        } catch {
        }
    }

    return $false
}

function Remove-DirectoryInside {
    param(
        [string]$Path,
        [string]$ParentPath
    )

    if (-not (Test-Path -LiteralPath $Path)) { return }

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $resolvedParent = [System.IO.Path]::GetFullPath($ParentPath)
    if (-not $resolvedParent.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $resolvedParent = $resolvedParent + [System.IO.Path]::DirectorySeparatorChar
    }

    if (-not $resolvedPath.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove dependency path outside $resolvedParent"
    }

    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}

function Invoke-DependencyDownload {
    param(
        [string]$Url,
        [string]$OutFile,
        [string]$Label
    )

    New-Item -ItemType Directory -Path (Split-Path -Parent $OutFile) -Force | Out-Null
    if (Test-Path -LiteralPath $OutFile) {
        Write-Status "$Label already downloaded"
        return $OutFile
    }

    Write-Status "Downloading $Label"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    } catch {
    }

    try {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 180
    } catch {
        throw "Could not download $Label from $Url. $($_.Exception.Message)"
    }

    if (-not (Test-Path -LiteralPath $OutFile)) {
        throw "$Label download did not create $OutFile"
    }

    return $OutFile
}

function Install-VcRuntimeIfMissing {
    if (Test-VcRuntimeInstalled) {
        Write-Status "Microsoft Visual C++ Runtime is installed" "OK"
        return
    }

    Write-Status "Microsoft Visual C++ Runtime was not found; installing it automatically" "WARN"
    $installer = Join-Path $DependencyRoot "vc_redist.x64.exe"
    Invoke-DependencyDownload -Url $VcRedistUrl -OutFile $installer -Label "Microsoft Visual C++ Runtime" | Out-Null

    $process = Start-Process -FilePath $installer -ArgumentList "/install", "/quiet", "/norestart" -Wait -PassThru
    if (@(0, 3010, 1638) -contains $process.ExitCode) {
        Write-Status "Microsoft Visual C++ Runtime installer completed with code $($process.ExitCode)" "OK"
        return
    }

    Write-Status "Microsoft Visual C++ Runtime installer exited with code $($process.ExitCode). Sentinel Edge will continue and report any startup error." "WARN"
}

function Find-DownloadedMongoDbExecutable {
    if (-not $DependencyRoot -or -not (Test-Path -LiteralPath $DependencyRoot)) { return $null }

    $candidate = Get-ChildItem -LiteralPath $DependencyRoot -Filter "mongod.exe" -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "\\bin\\mongod\.exe$" } |
        Select-Object -First 1

    if ($candidate) { return $candidate.FullName }
    return $null
}

function Find-MongoDbExecutable {
    if ($MongoPath) {
        if (Test-Path -LiteralPath $MongoPath -PathType Leaf) { return $MongoPath }
        $directCandidate = Join-Path $MongoPath "mongod.exe"
        $binCandidate = Join-Path $MongoPath "bin\mongod.exe"
        if (Test-Path -LiteralPath $directCandidate) { return $directCandidate }
        if (Test-Path -LiteralPath $binCandidate) { return $binCandidate }
    }

    $downloaded = Find-DownloadedMongoDbExecutable
    if ($downloaded) { return $downloaded }

    $candidates = @(
        (Join-Path $ProjectRoot "mongodb\bin\mongod.exe"),
        (Join-Path $ProjectRoot "mongodb\mongod.exe"),
        "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe",
        "C:\Program Files\MongoDB\Server\8.0\bin\mongod.exe",
        "C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe",
        "C:\Program Files\MongoDB\Server\6.0\bin\mongod.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }

    $cmd = Get-Command mongod.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Install-MongoDbPortableDependency {
    $existing = Find-DownloadedMongoDbExecutable
    if ($existing) {
        Write-Status "Using downloaded MongoDB at $existing" "OK"
        return $existing
    }

    New-Item -ItemType Directory -Path $DependencyRoot -Force | Out-Null
    $zipPath = Join-Path $DependencyRoot "mongodb-windows-x86_64-$MongoPortableVersion.zip"
    $extractRoot = Join-Path $DependencyRoot "mongodb-$MongoPortableVersion"
    $extractingRoot = Join-Path $DependencyRoot "mongodb-$MongoPortableVersion.extracting"

    Invoke-DependencyDownload -Url $MongoPortableZipUrl -OutFile $zipPath -Label "MongoDB Community Server $MongoPortableVersion" | Out-Null

    Remove-DirectoryInside -Path $extractingRoot -ParentPath $DependencyRoot
    New-Item -ItemType Directory -Path $extractingRoot -Force | Out-Null

    try {
        Write-Status "Extracting MongoDB runtime"
        Expand-Archive -Path $zipPath -DestinationPath $extractingRoot -Force
    } catch {
        Remove-DirectoryInside -Path $extractingRoot -ParentPath $DependencyRoot
        throw "Could not extract MongoDB runtime. $($_.Exception.Message)"
    }

    $mongoExe = Get-ChildItem -LiteralPath $extractingRoot -Filter "mongod.exe" -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "\\bin\\mongod\.exe$" } |
        Select-Object -First 1

    if (-not $mongoExe) {
        Remove-DirectoryInside -Path $extractingRoot -ParentPath $DependencyRoot
        throw "MongoDB download did not contain mongod.exe."
    }

    Remove-DirectoryInside -Path $extractRoot -ParentPath $DependencyRoot
    Move-Item -LiteralPath $extractingRoot -Destination $extractRoot

    $installed = Find-DownloadedMongoDbExecutable
    if (-not $installed) {
        throw "MongoDB was extracted, but mongod.exe could not be found afterward."
    }

    Write-Status "MongoDB runtime is ready at $installed" "OK"
    return $installed
}

function Install-MongoDbMsiDependency {
    if (-not (Test-ProcessElevated)) {
        Write-Status "Skipping MongoDB MSI fallback because the launcher is not running as administrator" "WARN"
        return $null
    }

    $msiPath = Join-Path $DependencyRoot "mongodb-windows-x86_64-$MongoPortableVersion-signed.msi"
    Invoke-DependencyDownload -Url $MongoPortableMsiUrl -OutFile $msiPath -Label "MongoDB Community Server MSI $MongoPortableVersion" | Out-Null

    Write-Status "Installing MongoDB Community Server from MSI"
    $msiArgs = "/i `"$msiPath`" SHOULD_INSTALL_COMPASS=0 /qn /norestart"
    $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $msiArgs -Wait -PassThru
    if (-not (@(0, 3010, 1638) -contains $process.ExitCode)) {
        throw "MongoDB MSI installer exited with code $($process.ExitCode)."
    }

    return Find-MongoDbExecutable
}

function Ensure-LauncherDependencies {
    param([int]$MongoPort)

    Write-Status "Checking Sentinel Edge launcher dependencies"

    try {
        Install-VcRuntimeIfMissing
    } catch {
        Write-Status "Could not install Microsoft Visual C++ Runtime automatically. $($_.Exception.Message)" "WARN"
    }

    if (Test-MongoPort -Port $MongoPort) {
        Write-Status "MongoDB is already reachable on port $MongoPort" "OK"
        return
    }

    $mongoExe = Find-MongoDbExecutable
    if ($mongoExe) {
        Write-Status "MongoDB executable found at $mongoExe" "OK"
        return
    }

    Write-Status "MongoDB was not found; downloading a local runtime for Sentinel Edge" "WARN"
    try {
        Install-MongoDbPortableDependency | Out-Null
    } catch {
        Write-Status "Portable MongoDB install failed. $($_.Exception.Message)" "WARN"
        Install-MongoDbMsiDependency | Out-Null
    }

    $mongoExe = Find-MongoDbExecutable
    if (-not $mongoExe) {
        throw "MongoDB could not be installed automatically. Please send $LogFile and $TranscriptFile to Sentinel Edge support."
    }

    Write-Status "MongoDB dependency is ready at $mongoExe" "OK"
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
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }

    foreach ($name in @("msedge.exe", "chrome.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }

    return $null
}

function Get-BrowserProfileProcesses {
    if (-not $BrowserProfileDir) { return @() }
    try {
        return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($BrowserProfileDir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 } |
            ForEach-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue })
    } catch {
        return @()
    }
}

function Get-BrowserWindowProcesses {
    return @(Get-BrowserProfileProcesses | Where-Object { $_.MainWindowHandle -and $_.MainWindowHandle -ne 0 })
}

function Update-BrowserProcessIds {
    $profileProcesses = @(Get-BrowserProfileProcesses)
    if ($profileProcesses.Count -gt 0) {
        $script:BrowserProcessIds = @($profileProcesses | Select-Object -ExpandProperty Id)
    }
    $windowProcesses = @($profileProcesses | Where-Object { $_.MainWindowHandle -and $_.MainWindowHandle -ne 0 })
    if ($windowProcesses.Count -gt 0) {
        $script:BrowserWindowProcessIds = @($windowProcesses | Select-Object -ExpandProperty Id)
    }
    return $profileProcesses
}

function Wait-BrowserProfileProcesses {
    param([int]$Seconds = 10)

    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        $profileProcesses = @(Update-BrowserProcessIds)
        if ($profileProcesses.Count -gt 0) { return $profileProcesses }
        Start-Sleep -Milliseconds 250
    }
    return @(Update-BrowserProcessIds)
}

function Wait-BrowserWindowProcesses {
    param([int]$Seconds = 10)

    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        Update-BrowserProcessIds | Out-Null
        $windowProcesses = @(Get-BrowserWindowProcesses)
        if ($windowProcesses.Count -gt 0) {
            $script:BrowserWindowProcessIds = @($windowProcesses | Select-Object -ExpandProperty Id)
            return $windowProcesses
        }
        Start-Sleep -Milliseconds 250
    }
    Update-BrowserProcessIds | Out-Null
    return @(Get-BrowserWindowProcesses)
}

function Test-BrowserWindowClosed {
    if ($BrowserMonitorDisabled) { return $false }
    if (-not $BrowserProcess -and -not $BrowserProfileDir -and $BrowserProcessIds.Count -eq 0 -and $BrowserWindowProcessIds.Count -eq 0) { return $false }

    $profileProcesses = @(Update-BrowserProcessIds)
    $windowProcesses = @(Get-BrowserWindowProcesses)
    if ($windowProcesses.Count -gt 0) {
        $script:BrowserWindowProcessIds = @($windowProcesses | Select-Object -ExpandProperty Id)
        return $false
    }

    $knownWindowProcesses = @($BrowserWindowProcessIds | ForEach-Object {
        $process = Get-Process -Id $_ -ErrorAction SilentlyContinue
        if ($process -and $process.MainWindowHandle -and $process.MainWindowHandle -ne 0) { $process }
    })
    if ($knownWindowProcesses.Count -gt 0) { return $false }
    if ($BrowserWindowProcessIds.Count -gt 0) { return $true }

    $knownProcesses = @($BrowserProcessIds | ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
    if ($knownProcesses.Count -gt 0) { return $false }
    if ($BrowserProcessIds.Count -gt 0) { return $true }

    if ($BrowserProfileDir -and $BrowserStartedAt) {
        $elapsed = ((Get-Date) - $BrowserStartedAt).TotalSeconds
        if ($elapsed -lt 15 -and $profileProcesses.Count -gt 0) { return $false }
        if ($profileProcesses.Count -gt 0) { return $true }
    }

    if ($BrowserProcess -and $BrowserProcess.HasExited) {
        return $true
    }
    return $false
}

function Join-ProcessArguments {
    param([string[]]$Arguments)

    return (($Arguments | ForEach-Object {
        $arg = $_
        if ([string]::IsNullOrEmpty($arg)) {
            '""'
        } elseif ($arg -match '[\s"]') {
            $escaped = $arg.Replace('"', '\"')
            '"' + $escaped + '"'
        } else {
            $arg
        }
    }) -join " ")
}

function Start-BrowserWindow {
    param([string]$Url)

    $browserExe = Find-BrowserExecutable
    if ($browserExe) {
        Write-Status "Opening dedicated browser window"
        $script:BrowserProfileDir = Join-Path ([System.IO.Path]::GetTempPath()) "SentinelEdge-Browser-$PID"
        $script:BrowserStartedAt = Get-Date
        New-Item -ItemType Directory -Path $script:BrowserProfileDir -Force | Out-Null
        $browserArgs = Join-ProcessArguments -Arguments @("--new-window", "--app=$Url", "--user-data-dir=$script:BrowserProfileDir", "--no-first-run", "--disable-background-mode")
        $process = Start-Process -FilePath $browserExe -ArgumentList $browserArgs -PassThru
        Wait-BrowserProfileProcesses -Seconds 10 | Out-Null
        Wait-BrowserWindowProcesses -Seconds 10 | Out-Null
        return $process
    }

    Write-Status "Opening default browser without close monitoring" "WARN"
    Start-Process $Url | Out-Null
    return $null
}

function Start-OwnedProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )
    $startParams = @{
        FilePath = $FilePath
        WorkingDirectory = $WorkingDirectory
        PassThru = $true
        WindowStyle = "Hidden"
    }
    if ($ArgumentList -and $ArgumentList.Count -gt 0) {
        $startParams.ArgumentList = Join-ProcessArguments -Arguments $ArgumentList
    }
    $process = Start-Process @startParams
    $OwnedProcesses.Add($process)
    return $process
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
            Write-Status "Stopping process $($current.ProcessName) ($($current.Id))" "INFO"
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

function Start-LauncherShutdownWatchdog {
    if ($script:LauncherWatchdogProcess -and -not $script:LauncherWatchdogProcess.HasExited) { return }

    $watchdogName = "SentinelEdge-Watchdog-$PID"
    $script:LauncherWatchdogStopFile = Join-Path ([System.IO.Path]::GetTempPath()) "$watchdogName.stop"
    $script:LauncherWatchdogScriptFile = Join-Path ([System.IO.Path]::GetTempPath()) "$watchdogName.ps1"
    if (Test-Path $script:LauncherWatchdogStopFile) {
        Remove-Item -LiteralPath $script:LauncherWatchdogStopFile -Force -ErrorAction SilentlyContinue
    }

    $watchdogScript = @'
param(
    [int]$ParentProcessId,
    [string]$BrowserProfileDir,
    [string]$OwnedProcessIds,
    [string]$StopFile,
    [string]$LogFile
)

function Write-WatchdogLog {
    param([string]$Message)
    if (-not $LogFile) { return }
    try {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
        Add-Content -Path $LogFile -Value "$timestamp [WATCHDOG] $Message" -Encoding UTF8
    } catch {
    }
}

function Get-ProfileProcesses {
    if (-not $BrowserProfileDir) { return @() }
    try {
        return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($BrowserProfileDir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 } |
            ForEach-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue })
    } catch {
        return @()
    }
}

function Stop-ProcessTreeById {
    param([int]$ProcessId)
    try {
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue)
        foreach ($child in $children) {
            Stop-ProcessTreeById -ProcessId $child.ProcessId
        }
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    } catch {
    }
}

try {
    while ($true) {
        if ($StopFile -and (Test-Path -LiteralPath $StopFile)) { exit 0 }
        $parent = Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue
        if (-not $parent) { break }
        Start-Sleep -Seconds 1
    }

    Write-WatchdogLog "Launcher process $ParentProcessId ended; closing browser and owned processes"
    $profileProcesses = @(Get-ProfileProcesses)
    foreach ($process in $profileProcesses) {
        try { $process.CloseMainWindow() | Out-Null } catch {}
    }
    Start-Sleep -Milliseconds 750
    foreach ($process in $profileProcesses) {
        Stop-ProcessTreeById -ProcessId $process.Id
    }

    foreach ($idText in @($OwnedProcessIds -split ",")) {
        if (-not $idText) { continue }
        $id = 0
        if ([int]::TryParse($idText, [ref]$id)) {
            Stop-ProcessTreeById -ProcessId $id
        }
    }

    if ($BrowserProfileDir -and (Test-Path -LiteralPath $BrowserProfileDir)) {
        Remove-Item -LiteralPath $BrowserProfileDir -Recurse -Force -ErrorAction SilentlyContinue
    }
} catch {
    Write-WatchdogLog $_.Exception.Message
}
'@

    Set-Content -Path $script:LauncherWatchdogScriptFile -Value $watchdogScript -Encoding UTF8
    $ownedIds = @($OwnedProcesses | ForEach-Object { $_.Id }) -join ","
    $watchdogArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $script:LauncherWatchdogScriptFile,
        "-ParentProcessId", "$PID",
        "-BrowserProfileDir", "$BrowserProfileDir",
        "-OwnedProcessIds", $ownedIds,
        "-StopFile", $script:LauncherWatchdogStopFile,
        "-LogFile", $LogFile
    )
    $script:LauncherWatchdogProcess = Start-Process -FilePath "powershell.exe" -ArgumentList (Join-ProcessArguments -Arguments $watchdogArgs) -WindowStyle Hidden -PassThru
}

function Stop-LauncherShutdownWatchdog {
    if ($script:LauncherWatchdogStopFile) {
        New-Item -ItemType File -Path $script:LauncherWatchdogStopFile -Force -ErrorAction SilentlyContinue | Out-Null
    }
    if ($script:LauncherWatchdogProcess -and -not $script:LauncherWatchdogProcess.HasExited) {
        try {
            $script:LauncherWatchdogProcess.WaitForExit(2000) | Out-Null
            if (-not $script:LauncherWatchdogProcess.HasExited) {
                Stop-Process -Id $script:LauncherWatchdogProcess.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
        }
    }
    if ($script:LauncherWatchdogScriptFile -and (Test-Path $script:LauncherWatchdogScriptFile)) {
        Remove-Item -LiteralPath $script:LauncherWatchdogScriptFile -Force -ErrorAction SilentlyContinue
    }
    if ($script:LauncherWatchdogStopFile -and (Test-Path $script:LauncherWatchdogStopFile)) {
        Remove-Item -LiteralPath $script:LauncherWatchdogStopFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-BrowserWindow {
    $profileProcesses = @(Get-BrowserProfileProcesses)
    try {
        foreach ($current in $profileProcesses) {
            Write-Status "Closing browser window ($($current.Id))" "INFO"
            $current.CloseMainWindow() | Out-Null
        }
        Start-Sleep -Milliseconds 500
        foreach ($current in $profileProcesses) {
            $remaining = Get-Process -Id $current.Id -ErrorAction SilentlyContinue
            if ($remaining) {
                Stop-Process -Id $remaining.Id -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
    }
    if ($profileProcesses.Count -eq 0 -and $BrowserProcess) {
        try {
            $current = Get-Process -Id $BrowserProcess.Id -ErrorAction SilentlyContinue
            if ($current) {
                Write-Status "Closing browser window ($($current.Id))" "INFO"
                $current.CloseMainWindow() | Out-Null
                Start-Sleep -Milliseconds 500
                $current = Get-Process -Id $BrowserProcess.Id -ErrorAction SilentlyContinue
                if ($current) {
                    Stop-Process -Id $current.Id -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {
        }
    }
    if ($BrowserProfileDir -and (Test-Path $BrowserProfileDir)) {
        try { Remove-Item -LiteralPath $BrowserProfileDir -Recurse -Force -ErrorAction SilentlyContinue } catch {}
    }
}

function Invoke-LauncherCleanup {
    if ($script:ShutdownStarted) { return }
    $script:ShutdownStarted = $true
    Stop-LauncherShutdownWatchdog
    Stop-BrowserWindow
    Stop-OwnedProcesses
    if ($TranscriptStarted) {
        try { Stop-Transcript | Out-Null } catch {}
    }
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

function Start-MongoDb {
    param([int]$Port)

    if (Test-MongoPort -Port $Port) {
        Write-Status "MongoDB already running on port $Port" "WARN"
        return
    }

    $mongoExe = Find-MongoDbExecutable
    if (-not $mongoExe) {
        throw "MongoDB was not found. Sentinel Edge tried to download it automatically. Please send $LogFile and $TranscriptFile to support."
    }

    $mongoBin = Split-Path -Parent $mongoExe
    $mongoLog = Join-Path $LogPath "Sentinel-Edge-MongoDB.log"
    Write-Status "Starting MongoDB on port $Port"
    Start-OwnedProcess -FilePath $mongoExe -ArgumentList @("--dbpath", $DataPath, "--port", "$Port", "--logpath", $mongoLog, "--quiet") -WorkingDirectory $mongoBin | Out-Null
    if (-not (Wait-PortAttempts -Port $Port -Attempts 3 -IntervalSeconds 3)) {
        throw "MongoDB did not open port $Port. Check $mongoLog."
    }
    Write-Status "MongoDB is ready" "OK"
}

function Start-SentinelEdgeApp {
    param([int]$Port)

    if (Test-PortOpen -Port $Port) {
        if (Test-SentinelEdgeReady -Port $Port) {
            Write-Status "Sentinel Edge is already running on port $Port" "OK"
            return
        }
        throw "Port $Port is already in use by another service. Stop that service or launch Sentinel Edge with -AppPort <free port>."
    }

    $edgeExe = Join-Path $ProjectRoot "SentinelEdge.exe"
    if (-not (Test-Path -LiteralPath $edgeExe)) {
        throw "SentinelEdge.exe was not found in $ProjectRoot. Reinstall with SentinelEdge-Setup and send $LogFile to support if this continues."
    }

    $env:PORT = "$Port"
    $env:SENTINEL_EDGE_PORT = "$Port"
    $env:SENTINEL_EDGE_HOST = "127.0.0.1"
    $env:SENTINEL_EDGE_OPEN_BROWSER = "0"
    $env:SENTINEL_EDGE_UI_URL = "http://127.0.0.1:$Port"
    $env:MONGO_URL = "mongodb://127.0.0.1:$MongoPort"
    if (-not $env:DB_NAME) { $env:DB_NAME = "sentinel_edge" }
    if (-not $env:CORS_ORIGINS) {
        $env:CORS_ORIGINS = "http://localhost:$Port,http://127.0.0.1:$Port"
    }
    $env:LOG_FILE = $LogFile

    Write-Status "Starting SentinelEdge.exe on port $Port"
    Start-OwnedProcess -FilePath $edgeExe -ArgumentList @() -WorkingDirectory $ProjectRoot | Out-Null
    if (-not (Wait-Port -Port $Port -Seconds 30)) {
        throw "Sentinel Edge did not open port $Port. Check $LogFile."
    }
    if (-not (Wait-SentinelEdgeReady -Port $Port -Seconds 45)) {
        throw "Sentinel Edge opened port $Port, but /api/ready did not become healthy. Check $LogFile."
    }
    Write-Status "Sentinel Edge is ready on port $Port" "OK"
}

if ($SmokeTest) {
    Write-Status "Running launcher smoke test (-SmokeTest)"
    $basicArgs = Join-ProcessArguments -Arguments @("--dbpath", "C:\data\db", "--port", "27017")
    if (-not $basicArgs.Contains("--dbpath") -or -not $basicArgs.Contains("C:\data\db")) {
        throw "Basic argument smoke test failed."
    }
    $spacedArgs = Join-ProcessArguments -Arguments @("--logpath", "C:\Users\Lite OS\Desktop\Sentinel-Edge.log")
    if (-not $spacedArgs.Contains('"C:\Users\Lite OS\Desktop\Sentinel-Edge.log"')) {
        throw "Spaced argument quoting smoke test failed."
    }
    $browserArgs = Join-ProcessArguments -Arguments @("--user-data-dir=C:\Users\Lite OS\AppData\Local\Temp\SentinelEdge-Browser-1234")
    if (-not $browserArgs.Contains('"--user-data-dir=C:\Users\Lite OS\AppData\Local\Temp\SentinelEdge-Browser-1234"')) {
        throw "Browser argument quoting smoke test failed."
    }
    if (-not (Get-Command Start-Process -ErrorAction SilentlyContinue)) {
        throw "Start-Process is unavailable."
    }
    Write-Status "Launcher smoke test passed" "OK"
    exit 0
}

Register-LauncherShutdownHandlers

try {
    New-Item -ItemType Directory -Path $DataPath -Force | Out-Null
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
    try {
        Start-Transcript -Path $TranscriptFile -Append | Out-Null
        $TranscriptStarted = $true
    } catch {
        $TranscriptStarted = $false
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Sentinel Edge - Installed App" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Status "Install root: $ProjectRoot"
    Write-Status "App log: $LogFile"
    Write-Status "Launcher transcript: $TranscriptFile"
    Write-Status "Dependency cache: $DependencyRoot"
    Write-Status "MongoDB data path: $DataPath"

    Ensure-LauncherDependencies -MongoPort $MongoPort
    Start-MongoDb -Port $MongoPort
    Start-SentinelEdgeApp -Port $AppPort

    $url = "http://127.0.0.1:$AppPort"
    if (-not $NoBrowser) {
        $BrowserProcess = Start-BrowserWindow -Url $url
    }
    Start-LauncherShutdownWatchdog

    Write-Host ""
    Write-Host "Ready: $url" -ForegroundColor Green
    Write-Host "Close this window or press Ctrl+C to stop processes started by this launcher." -ForegroundColor Gray
    Write-Host ""

    while ($true) {
        foreach ($process in @($OwnedProcesses)) {
            if ($process.HasExited) {
                throw "Process $($process.Id) exited unexpectedly."
            }
        }
        if (Test-BrowserWindowClosed) {
            Write-Status "Browser window closed; shutting down Sentinel Edge" "OK"
            break
        }
        Start-Sleep -Seconds 1
    }
} catch {
    Write-Status $_.Exception.Message "ERROR"
    exit 1
} finally {
    Invoke-LauncherCleanup
}
