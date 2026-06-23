# Sentinel Bot Suite Launcher
# Starts the local Sentinel Edge, Sentinel Pulse, Darkpool, Discord options, Auto-Crypto, and Tandem launchers.

param(
    [string]$EdgeRoot = "C:\Users\Lite OS\.openclaw\workspace\repos\sentinel-edge",
    [string]$PulseRoot = "C:\Users\Lite OS\Documents\Codex\2026-05-22\based-on-my-analysis-of-the\Sentinel-Pulse-branch-audit",
    [string]$DarkpoolRoot = "C:\Users\Lite OS\Documents\Codex\2026-06-17\files-mentioned-by-the-user-pasted\work\darkpool-mon-frontend-check",
    [string]$DiscordRoot = "C:\Users\Lite OS\Documents\Codex\2026-06-17\files-mentioned-by-the-user-readme\work\Consolidation",
    [string]$CryptoRoot = "C:\Users\Lite OS\Documents\Codex\2026-06-17\start-by-researching-crypto-trading-bots\work\Auto-Crypto",
    [string]$TandemRoot = "C:\Users\Lite OS\Documents\Codex\2026-06-12\c-users-lite-os-openclaw-workspace\work\Tandem-Suite",
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
    [int]$TandemBackendPort = 8005,
    [int]$TandemFrontendPort = 3005,
    [switch]$SkipEdge,
    [switch]$SkipPulse,
    [switch]$SkipDarkpool,
    [switch]$SkipDiscord,
    [switch]$SkipCrypto,
    [switch]$SkipTandem,
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
        "SkipTandem"
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
    Write-Host "  1. Core operator stack (Sentinel Edge, Sentinel Pulse, Tandem)" -ForegroundColor Gray
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
            $script:SkipTandem = $true
        }
        "All" {
        }
        "None" {
            $script:SkipEdge = $true
            $script:SkipPulse = $true
            $script:SkipDarkpool = $true
            $script:SkipDiscord = $true
            $script:SkipCrypto = $true
            $script:SkipTandem = $true
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
        Start-ComponentLauncher -Name "Darkpool Monitor" -Root $DarkpoolRoot -LauncherName "Launch-Darkpool-Monitor.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $DarkpoolBackendPort
    } else {
        Write-Status "Skipping Darkpool Monitor" "WARN"
    }

    if (-not $SkipDiscord) {
        $args = New-ArgumentList
        $args.Add("-BackendPort"); $args.Add("$DiscordBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$DiscordFrontendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled (-not $OpenComponentBrowsers)
        Start-ComponentLauncher -Name "Discord Options Bot" -Root $DiscordRoot -LauncherName "Launch-Consolidation-Bot.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $DiscordBackendPort
    } else {
        Write-Status "Skipping Discord Options Bot" "WARN"
    }

    if (-not $SkipCrypto) {
        $args = New-ArgumentList
        $args.Add("-Port"); $args.Add("$CryptoBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$CryptoFrontendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled (-not $OpenComponentBrowsers)
        Start-ComponentLauncher -Name "Auto-Crypto" -Root $CryptoRoot -LauncherName "Launch-Auto-Crypto.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $CryptoBackendPort
    } else {
        Write-Status "Skipping Auto-Crypto" "WARN"
    }

    if (-not $SkipTandem) {
        $args = New-ArgumentList
        $args.Add("-BackendPort"); $args.Add("$TandemBackendPort")
        $args.Add("-FrontendPort"); $args.Add("$TandemFrontendPort")
        $args.Add("-EdgeApiUrl"); $args.Add("http://127.0.0.1:$EdgeBackendPort")
        $args.Add("-PulseApiUrl"); $args.Add("http://127.0.0.1:$PulseBackendPort")
        Add-OptionalSwitch -Arguments $args -SwitchName "-InstallDeps" -Enabled $InstallDeps
        Add-OptionalSwitch -Arguments $args -SwitchName "-NoBrowser" -Enabled $NoBrowser
        Start-ComponentLauncher -Name "Sentinel Tandem Suite" -Root $TandemRoot -LauncherName "Launch-Sentinel-Tandem.ps1" -LauncherArguments $args.ToArray() -ReadinessPort $TandemBackendPort
    } else {
        Write-Status "Skipping Sentinel Tandem Suite" "WARN"
    }

    Write-Host ""
    Write-Host "Sentinel bot suite launch requests are running." -ForegroundColor Green
    Write-Host "Edge:       backend http://127.0.0.1:$EdgeBackendPort       UI http://127.0.0.1:$EdgeFrontendPort" -ForegroundColor Gray
    Write-Host "Pulse:      backend http://127.0.0.1:$PulseBackendPort       UI http://127.0.0.1:$PulseFrontendPort" -ForegroundColor Gray
    Write-Host "Darkpool:   backend http://127.0.0.1:$DarkpoolBackendPort       UI http://127.0.0.1:$DarkpoolFrontendPort" -ForegroundColor Gray
    Write-Host "Discord:    backend http://127.0.0.1:$DiscordBackendPort       UI http://127.0.0.1:$DiscordFrontendPort" -ForegroundColor Gray
    Write-Host "Crypto:     backend http://127.0.0.1:$CryptoBackendPort       UI port reserved $CryptoFrontendPort" -ForegroundColor Gray
    Write-Host "Tandem:     backend http://127.0.0.1:$TandemBackendPort       UI http://127.0.0.1:$TandemFrontendPort" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Default behavior opens Tandem as the main operator UI and suppresses component browser windows." -ForegroundColor Gray
    Write-Host "Use -OpenComponentBrowsers to open Edge, Pulse, Darkpool, Discord, and Crypto windows too." -ForegroundColor Gray
    Write-Host "Use -Profile Core, -Profile Discord, -Profile All, or -All to bypass the desktop launch menu." -ForegroundColor Gray
    Write-Host "Use -SkipEdge, -SkipPulse, -SkipDarkpool, -SkipDiscord, -SkipCrypto, or -SkipTandem to launch a smaller set." -ForegroundColor Gray
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
