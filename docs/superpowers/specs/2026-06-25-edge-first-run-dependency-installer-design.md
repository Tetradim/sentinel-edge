# Sentinel Edge first-run dependency installer design

Date: 2026-06-25

## Goal

Windows beta testers should install Sentinel Edge from `SentinelEdge-Setup-<version>.exe`, double-click the installed shortcut, and have missing runtime dependencies handled automatically on first launch.

The installed app path must not require testers to install Python, Node.js, MongoDB, or Visual C++ manually. The source launcher remains available for developers and source checkouts.

## Scope

- Add a packaged Windows launcher pair: `Launch-Sentinel-Edge.bat` and `Launch-Sentinel-Edge.ps1`.
- The packaged PowerShell launcher checks for the Visual C++ Runtime and MongoDB on first run.
- If MongoDB is not available on `27017` and no existing `mongod.exe` is found, the launcher downloads a portable MongoDB dependency into `%LOCALAPPDATA%\Sentinel Edge\dependencies`.
- Runtime downloads are cached and reused on later launches.
- The launcher starts `SentinelEdge.exe` with explicit local host/port environment variables and writes support logs to the Desktop.
- The Inno installer must install shortcuts and postinstall launch actions that call `Launch-Sentinel-Edge.bat`.
- CI packaging should stop bundling MongoDB and VC++ binaries directly.
- The local source batch wrapper should fail with a clear extract/install message if its PowerShell script is missing.

## Non-goals

- No source checkout dependency auto-download beyond the existing `-InstallDeps` behavior.
- No macOS packaging redesign.
- No cloud update channel or background updater.
