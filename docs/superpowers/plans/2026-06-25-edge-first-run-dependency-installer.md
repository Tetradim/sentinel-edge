# Sentinel Edge first-run dependency installer plan

Date: 2026-06-25

## Plan

1. Add static regression coverage for the packaged launcher, workflow packaging, local batch wrapper, and README beta-user contract.
2. Add `Launch-Sentinel-Edge.bat` as the installed-app entrypoint with clear missing-file diagnostics.
3. Add `Launch-Sentinel-Edge.ps1` to perform first-run checks, cache/download missing runtime dependencies, start MongoDB when needed, start `SentinelEdge.exe`, and support `-SmokeTest`.
4. Harden `Launch-Sentinel-Edge-Local.bat` so partial ZIP extraction produces a useful support message instead of a PowerShell `-File` error.
5. Update `.github/workflows/build.yml` so the installer package copies the launcher pair, removes direct MongoDB/VC++ bundling, and routes shortcuts/postinstall launch through `Launch-Sentinel-Edge.bat`.
6. Update `README.md` so beta users are pointed at `SentinelEdge-Setup-<version>.exe` and understand first launch downloads missing runtime dependencies automatically.
7. Verify with targeted static tests and the packaged launcher smoke test, then commit and push `OC-Iteration`.
