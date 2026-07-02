# Sentinel Bot Suite Launcher
# Starts the local Sentinel Edge, Sentinel Pulse, Darkpool, Discord options, Sentinel-Chain, and Sentinel Core launchers.

param(
    [string]$EdgeRoot = "C:\Users\automation\GitBots\Sentinel-Edge",
    [string]$PulseRoot = "C:\Users\Lite OS\Documents\Codex\2026-05-22\based-on-my-analysis-of-the\Sentinel-Pulse-branch-audit",
    [string]$DarkpoolRoot = "C:\Users\Lite OS\Documents\Codex\2026-06-17\files-mentioned-by-the-user-pasted\work\sentinel-flare-frontend-check",
    [string]$DiscordRoot = "C:\Users\automation\GitBots\Sentinel-Echo",
    [string]$CryptoRoot = "C:\Users\automation\GitBots\Sentinel-Chain",
    [string]$SentinelCoreRoot = "C:\Users\automation\GitBots\Sentinel-Core",
    [int]$EdgeBackendPort = 8000,
    [int]$EdgeFrontendPort = 3000,
    [int]$PulseBackendPort = 8001,
    [int]$PulseFrontendPort = 3001,
    [int]$DarkpoolBackendPort = 8002,
    [int]$DarkpoolFrontendPort = 3002,
    [int]$DiscordBackendPort = 8003,
    [int]$DiscordFrontendPort = 3003,
    [int]$CryptoBackendPort = 8004,
    [int]$CryptoFrontendPort = 3004,
    [int]$SentinelCoreBackendPort = 8005,
    [int]$SentinelCoreFrontendPort = 3005,
    [switch]$SkipEdge,
    [switch]$SkipPulse,
    [switch]$SkipDarkpool,
    [switch]$SkipDiscord,
    [switch]$SkipCrypto,
    [switch]$SkipSentinelCore,
    [switch]$OpenComponentBrowsers,
    [switch]$NoBrowser,
    [switch]$InstallDeps,
    [switch]$NoWait,
    [ValidateSet("Menu", "Core", "Discord", "All", "None")]
    [string]$Profile = "Menu",
    [switch]$All
)

$ErrorActionPreference = "Stop"
$DesktopPath = [Environment]::GetFolderPath("Desktop")
if (-not $DesktopPath) { $DesktopPath = Join-Path $HOME "Desktop" }
$LogFile = Join-Path $DesktopPath "Sentinel-Bot-Suite.log"
$LauncherProcesses = New-Object System.Collections.Generic.List[System.Diagnostics.Process]

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
    param([int]$Port, [int]$Seconds = 120)
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -Port $Port) { return $true }
        Start-Sleep -Milliseconds 750
    }
    return $false
}

function Resolve-Launcher {
    param([string]$Root, [string]$LauncherName)
    if (-not (Test-Path -LiteralPath $Root)) {
        throw "Component root not found: $Root"
    }
    $launcher = Join-Path $Root $LauncherName
    if (-not (Test-Path -LiteralPath $launcher)) {
        throw "Launcher not found: $launcher"
    }
    return $launcher
}

function Add-OptionalSwitch {
    param(
        [System.Collections.Generic.List[string]]$Arguments,
        [string]$SwitchName,
        [bool]$Enabled
    )
    if ($Enabled) { $Arguments.Add($SwitchName) }
}

function Start-ComponentLauncher {
    param(
        [string]$Name,
        [string]$Root,
        [string]$LauncherName,
        [string[]]$LauncherArguments,
        [int]$ReadinessPort = 0
    )

    $launcher = Resolve-Launcher -Root $Root -LauncherName $LauncherName
    Write-Status "Starting $Name"
    $powershellArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher) + $LauncherArguments
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList (Join-ProcessArguments -Arguments $powershellArgs) -WorkingDirectory $Root -PassThru
    $LauncherProcesses.Add($process)

    if ($ReadinessPort -gt 0) {
        if (Wait-Port -Port $ReadinessPort -Seconds 180) {
            Write-Status "$Name opened port $ReadinessPort" "OK"
        } else {
            Write-Status "$Name has not opened port $ReadinessPort yet; its launcher window may still be installing or starting dependencies" "WARN"
        }
    }
}

function New-ArgumentList {
    $list = New-Object System.Collections.Generic.List[string]
    return ,$list
}

function Test-ExplicitComponentSelection {
    $componentSwitches = @(
        "SkipEdge",
        "SkipPulse",
        "SkipDarkpool",
        "SkipDiscord",
        "SkipCrypto",
        "SkipSentinelCore"
    )
    foreach ($switchName in $componentSwitches) {
        if ($PSBoundParameters.ContainsKey($switchName)) {
            return $true
        }
    }
    return $false
}

function Select-LaunchProfile {
    Write-Host ""
    Write-Host "Choose what to launch:" -ForegroundColor Cyan
    Write-Host "  1. Core operator stack (Sentinel Edge, Sentinel Pulse, Sentinel Core)" -ForegroundColor Gray
    Write-Host "  2. Discord Options Bot only" -ForegroundColor Gray
    Write-Host "  3. All components" -ForegroundColor Gray
    Write-Host "  Q. Quit without launching" -ForegroundColor Gray
    Write-Host ""
    $choice = Read-Host "Selection [1]"
    switch ($choice.Trim().ToUpperInvariant()) {
        "" { return "Core" }
        "1" { return "Core" }
        "CORE" { return "Core" }
        "2" { return "Discord" }
        "DISCORD" { return "Discord" }
        "3" { return "All" }
        "ALL" { return "All" }
        "Q" { return "None" }
        "QUIT" { return "None" }
        default {
            Write-Status "Unknown launch profile selection '$choice'; defaulting to Core operator stack" "WARN"
            return "Core"
        }
    }
}

function Apply-LaunchProfile {
    param([string]$SelectedProfile)

    switch ($SelectedProfile) {
        "Core" {
            $script:SkipDarkpool = $true
            $script:SkipDiscord = $true
            $script:SkipCrypto = $true
        }
        "Discord" {
            $script:SkipEdge = $true
            $script:SkipPulse = $true
            $script:SkipDarkpool = $true
            $script:SkipCrypto = $true
            $script:SkipSentinelCore = $true
        }
        "All" {
        }
        "None" {
            $script:SkipEdge = $true
            $script:SkipPulse = $true
            $script:SkipDarkpool = $true
            $script:SkipDiscord = $true
            $script:SkipCrypto = $true
            $script:SkipSentinelCore = $true
        }
    }
}

try {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Sentinel Bot Suite" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Status "Suite log: $LogFile"

    if ($All) {
        $Profile = "All"
    }
    if ($Profile -eq "Menu" -and -not (Test-ExplicitComponentSelection)) {
        $Profile = Select-LaunchProfile
    }
    if ($Profile -ne "Menu") {
        Apply-LaunchProfile -SelectedProfile $Profile
        Write-Status "Launch profile: $Profile"
    }

    if (-not $SkipEdge) {
        $args = New-ArgumentList
        $args.Add("-BackendPort"); $args.Add("$EdgeBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$EdgeFrontendPort")
        $args.Add("-PulseApiUrl"); $args.Add("http://127.0.0.1:$PulseBackendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled (-not $OpenComponentBrowsers)
        Start-ComponentLauncher -Name "Sentinel Edge" -Root $EdgeRoot -LauncherName "Launch-Sentinel-Edge-Local.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $EdgeBackendPort
    } else {
        Write-Status "Skipping Sentinel Edge" "WARN"
    }

    if (-not $SkipPulse) {
        $args = New-ArgumentList
        $args.Add("-BackendPort"); $args.Add("$PulseBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$PulseFrontendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled (-not $OpenComponentBrowsers)
        Start-ComponentLauncher -Name "Sentinel Pulse" -Root $PulseRoot -LauncherName "Launch-Sentinel-Pulse-Local.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $PulseBackendPort
    } else {
        Write-Status "Skipping Sentinel Pulse" "WARN"
    }

    if (-not $SkipDarkpool) {
        $args = New-ArgumentList
        $args.Add("-BackendPort"); $args.Add("$DarkpoolBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$DarkpoolFrontendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled (-not $OpenComponentBrowsers)
        Start-ComponentLauncher -Name "Sentinel Flare" -Root $DarkpoolRoot -LauncherName "Launch-Sentinel-Flare.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $DarkpoolBackendPort
    } else {
        Write-Status "Skipping Sentinel Flare" "WARN"
    }

    if (-not $SkipDiscord) {
        $args = New-ArgumentList
        $args.Add("-BackendPort"); $args.Add("$DiscordBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$DiscordFrontendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled (-not $OpenComponentBrowsers)
        Start-ComponentLauncher -Name "Discord Options Bot" -Root $DiscordRoot -LauncherName "Launch-Sentinel-Echo.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $DiscordBackendPort
    } else {
        Write-Status "Skipping Discord Options Bot" "WARN"
    }

    if (-not $SkipCrypto) {
        $args = New-ArgumentList
        $args.Add("-Port"); $args.Add("$CryptoBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$CryptoFrontendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled (-not $OpenComponentBrowsers)
        Start-ComponentLauncher -Name "Sentinel-Chain" -Root $CryptoRoot -LauncherName "Launch-Sentinel-Chain.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $CryptoBackendPort
    } else {
        Write-Status "Skipping Sentinel-Chain" "WARN"
    }

    if (-not $SkipSentinelCore) {
        $args = New-ArgumentList
        $args.Add("-BackendPort"); $args.Add("$SentinelCoreBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$SentinelCoreFrontendPort")
        $args.Add("-EdgeApiUrl"); $args.Add("http://127.0.0.1:$EdgeBackendPort")
        $args.Add("-PulseApiUrl"); $args.Add("http://127.0.0.1:$PulseBackendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled $NoBrowser
        Start-ComponentLauncher -Name "Sentinel Core" -Root $SentinelCoreRoot -LauncherName "Launch-Sentinel-Core.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $SentinelCoreBackendPort
    } else {
        Write-Status "Skipping Sentinel Core" "WARN"
    }

    Write-Host ""
    Write-Host "Sentinel bot suite launch requests are running." -ForegroundColor Green
    Write-Host "Edge:       backend http://127.0.0.1:$EdgeBackendPort       UI http://127.0.0.1:$EdgeFrontendPort" -ForegroundColor Gray
    Write-Host "Pulse:      backend http://127.0.0.1:$PulseBackendPort       UI http://127.0.0.1:$PulseFrontendPort" -ForegroundColor Gray
    Write-Host "Darkpool:   backend http://127.0.0.1:$DarkpoolBackendPort       UI http://127.0.0.1:$DarkpoolFrontendPort" -ForegroundColor Gray
    Write-Host "Discord:    backend http://127.0.0.1:$DiscordBackendPort       UI http://127.0.0.1:$DiscordFrontendPort" -ForegroundColor Gray
    Write-Host "Crypto:     backend http://127.0.0.1:$CryptoBackendPort       UI port reserved $CryptoFrontendPort" -ForegroundColor Gray
    Write-Host "Sentinel Core:     backend http://127.0.0.1:$SentinelCoreBackendPort       UI http://127.0.0.1:$SentinelCoreFrontendPort" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Default behavior opens Sentinel Core as the main operator UI and suppresses component browser windows." -ForegroundColor Gray
    Write-Host "Use -OpenComponentBrowsers to open Edge, Pulse, Darkpool, Discord, and Crypto windows too." -ForegroundColor Gray
    Write-Host "Use -Profile Core, -Profile Discord, -Profile All, or -All to bypass the desktop launch menu." -ForegroundColor Gray
    Write-Host "Use -SkipEdge, -SkipPulse, -SkipDarkpool, -SkipDiscord, -SkipCrypto, or -SkipSentinelCore to launch a smaller set." -ForegroundColor Gray
    Write-Host "Close each component launcher window to stop that component." -ForegroundColor Gray
    Write-Host ""

    if (-not $NoWait) {
        Write-Host "Monitoring launcher windows. Press Ctrl+C to stop monitoring; component windows remain in control of their own services." -ForegroundColor Gray
        while ($true) {
            $running = @($LauncherProcesses | Where-Object { -not $_.HasExited })
            if ($running.Count -eq 0) { break }
            Start-Sleep -Seconds 2
        }
    }
} catch {
    Write-Status $_.Exception.Message "ERROR"
    exit 1
}
