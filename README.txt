Sentinel Edge
=============

Sentinel Edge is the analysis, readiness, risk, and operator-console layer for the Sentinel trading suite. It watches market data, evaluates active symbols, generates decision context, exposes readiness/observability endpoints, and can hand structured instructions to Sentinel Pulse only when safety gates allow it.

Safety Boundary
---------------

Edge is not the broker adapter and does not place broker orders directly. Sentinel Pulse owns broker connectivity, account truth, positions, and execution. Edge can run by itself for analysis, observability, tutorials, chart work, simulation workflows, and operator review.

Current Feature Areas
---------------------

- Asset Command Console with Monitor, Command, Protect, Operations, and Settings modes.
- Active ticker monitoring with ORB, ATR, signal, price, volume, market-hours, and decision context.
- Trading Overview with add/remove ticker actions, metric toggles, market breadth, decision feed, and partial-refresh warnings.
- Advisor Health with Edge readiness, Pulse status, provider health, automation mode, kill switch state, and runtime details.
- Protection Ops with scheduler controls, kill switch, readiness blockers, Pulse queue/status, synced positions, trailing-stop bridge, and emergency-exit bridge.
- System Settings with non-secret config, provider catalog, automation controls, per-ticker Pulse handoff controls, notification channel discovery, and Simulation Lab status discovery.
- Experience/RUM observability with browser web vitals, backend RUM ingest, rate-limit pressure, copyable Prometheus text, and Grafana-style frontend panels.
- Chart Workspace with OHLCV snapshots, ORB overlays, EMA/SMA, RSI, MACD, indicator presets, strategy context, replay actions, and persistent chart preferences.
- Learning Center with tutorials, saved guides, notes, reading mode, progress, import/export, and practice checklist workflows.
- Backtesting, strategy catalog, Monte Carlo, and Simulation Lab discovery endpoints.
- Prometheus metrics, OpenTelemetry support, runbooks, and Alertmanager/Grafana-oriented operational docs.

Local Launcher
--------------

Run from the repository root:

    .\Launch-Sentinel-Edge-Local.ps1 -InstallDeps

Default local URLs:

    Backend:  http://127.0.0.1:8001
    Frontend: http://127.0.0.1:3001

Useful flags:

    -BackendPort <port>
    -FrontendPort <port>
    -NoBrowser
    -InstallDeps

The Windows source launcher starts the backend and frontend, waits for readiness, opens the UI in a dedicated temporary Edge/Chrome profile, and writes logs to the Desktop as Sentinel-Edge-Local.log.

Launcher lifecycle now matches Sentinel Pulse:

- Closing the dedicated browser window shuts down the Edge backend/frontend processes started by the launcher.
- Closing the launcher window or pressing Ctrl+C closes the dedicated browser profile and stops the owned backend/frontend process trees.
- The launcher tracks only its own temporary browser profile and owned child processes.
- Use -NoBrowser when running headless or when browser-close monitoring is not wanted.

Verification
------------

Run the root verification gate:

    .\scripts\verify-local.ps1

Focused launcher lifecycle regression test:

    python -m unittest backend.tests.test_local_launcher_lifecycle_static -v

Minimum docs-only check:

    git diff --check

More Detail
-----------

Use README.md for the full architecture, API, operations, configuration, and roadmap documentation.
