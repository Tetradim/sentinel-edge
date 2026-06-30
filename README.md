# Sentinel Edge

Autonomous market-analysis brain, operator console, and safety-gated Pulse handoff layer for the Sentinel trading suite.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11--3.13-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.110-blue?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-blue?logo=react" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-6-blue?logo=typescript" alt="TypeScript">
  <img src="https://img.shields.io/badge/Runtime-Windows%20local%20beta-green?logo=windows" alt="Windows local beta">
  <img src="https://img.shields.io/badge/Automation-safety%20gated-red" alt="Safety gated automation">
</p>

Sentinel Edge is the analysis and decision layer for the Sentinel ecosystem. It watches market data, evaluates active symbols, calculates ORB/ATR/signal/risk state, explains operational readiness, and can hand structured action instructions to Sentinel Pulse only when explicit safety gates allow it.

Edge is intentionally not a broker adapter. It does not place broker orders directly. Sentinel Pulse owns execution and broker connectivity. Edge can run standalone for analysis, observability, tutorials, simulation, and operator review even when Pulse, MongoDB, or paid market-data providers are unavailable.

> Safety note: This project is software for research and operator-supervised trading workflows. It is not financial advice. Do not enable live automation without validating configuration, broker behavior, account permissions, risk limits, and emergency controls in your own environment.

---

## Table of Contents

- [What Edge Is](#what-edge-is)
- [Capability Map](#capability-map)
- [System Model](#system-model)
- [Safety Model](#safety-model)
- [Architecture](#architecture)
- [Frontend Experience](#frontend-experience)
- [Backend Capabilities](#backend-capabilities)
- [Market Data](#market-data)
- [Automation and Pulse Handoff](#automation-and-pulse-handoff)
- [Observability and Operations](#observability-and-operations)
- [Simulation and Backtesting](#simulation-and-backtesting)
- [Learning Center](#learning-center)
- [Repository Layout](#repository-layout)
- [Quick Start](#quick-start)
- [Local Launcher Lifecycle](#local-launcher-lifecycle)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Verification](#verification)
- [Operational Playbooks](#operational-playbooks)
- [Development Standards](#development-standards)
- [Roadmap](#roadmap)

---

## What Edge Is

Sentinel Edge is best understood as an "advisor runtime":

- It ingests market data from configurable providers.
- It maintains active ticker state.
- It calculates technical and risk context, including ORB and ATR state.
- It runs a scheduler that continuously evaluates active tickers.
- It records recent recommendations and decision context.
- It exposes FastAPI endpoints for dashboards, automation, readiness, metrics, and operational tooling.
- It provides a React operator console for command, monitor, protection, settings, and legacy operations workflows.
- It can send Pulse-facing handoff commands after explicit global, per-ticker, mode, confidence, cooldown, readiness, and Pulse-availability gates pass.

Edge is designed for Windows-local beta operation first, with Docker and observability stack support for fuller environments.

Edge is also designed to degrade safely:

- Missing Pulse should not make Edge noisy or unusable.
- MongoDB is required for startup; Edge does not run an in-memory trading path.
- Missing paid market-data keys should not break keyless or configured provider paths.
- Partial dashboard refresh failures are surfaced in the UI instead of silently clearing stale data.
- Runtime readiness is exposed separately from process liveness.

---

## Capability Map

| Area | What Edge provides |
|------|--------------------|
| Operator UI | Asset Command Console with monitor, command, protect, operations, and settings modes. |
| Trading overview | Active tickers, runtime stats, correlation clusters with correlation risk recommendation details, decisions, add/remove ticker actions, metric toggles, and refresh-failure warnings. |
| Advisor health | Edge service state, readiness, Pulse status, provider health, kill-switch state, recommendation counts, handoff mode, and runtime details. |
| Protection operations | Scheduler controls, kill switch controls, readiness guard, Pulse queue status, handoff status, synced positions, trailing-stop and emergency-exit bridges. |
| Settings | Local non-secret config, backend validation, read-only provider metadata, operator notification channel discovery, notification confirmation preview and feedback contract visibility, global/per-ticker Pulse handoff controls, Simulation Lab status discovery, and runtime metadata warnings. |
| Experience/RUM | Browser Web Vitals collection, backend RUM ingest, rate-limit status, Grafana-style observability panels inside Experience, copyable Prometheus text, and frontend performance visibility. |
| Market coverage | Market-hours/session status across supported markets. |
| Portfolio/P&L views | Pulse-backed account, portfolio, position, and P&L visibility when Pulse is available. |
| Learning Center | In-app tutorials, learning paths, saved guides, notes, reading modes, progress tracking, import/export, and practice checklists. |
| Scheduler | Continuous ticker evaluation, provider fallback, ORB/ATR/signal/risk computation, decision generation, WebSocket integration, and Pulse handoff gating. |
| Automation | Global handoff switch, mode selection, per-ticker gates, confidence threshold, cooldown, idempotency key, last handoff, last suppression, and local persistence. |
| Readiness | `/api/live` for process liveness, `/api/ready` for dependency readiness, readiness metrics, Grafana panels, alerts, and runbooks. |
| Observability | Prometheus metrics, frontend RUM metrics, rate-limit metrics, OpenTelemetry traces, Loki/Promtail/Grafana/Tempo/Alertmanager Docker stack. |
| Backtesting | Backtest execution, run reports, strategy optimization, Monte Carlo chart endpoints, dry-run status, and strategy catalog endpoints. |
| Market Map | Read-only operator chart cockpit built on Chart Workspace snapshots, toggleable ORB overlays with per-session ORB overlay filters, EMA/SMA, RSI, MACD, indicator presets, strategy context panels with Simulation Lab disabled reason visibility, chart replay actions, crosshair-style hover context, persistent Market Map presets, persistent Analysis/Execution/Research layouts, and persistent symbol, chart-type, indicator, and range preferences. |
| Safety controls | Kill switch, scheduler pause/resume, recommend-only mode, Pulse circuit breaker, quiet standalone suppression, read-only provider secrets policy. |
| Local launcher | Windows source launcher starts backend and frontend, opens a dedicated browser profile, shuts down owned tasks when the browser closes, and closes the browser/tasks if the launcher window exits. |

---

## System Model

The Sentinel ecosystem separates analysis from execution:

| System | Role | Owns |
|--------|------|------|
| Sentinel Edge | Brain / analyst / operator console | Market data, analysis, recommendations, readiness, risk context, automation gates, Pulse handoff instructions. |
| Sentinel Pulse | Worker / executor | Broker adapters, order placement, execution state, account truth, positions, and execution controls. |
| Darkpool-Mon | Flow/intelligence source | Darkpool, whale prints, scanner, options-flow, and volume-anomaly intelligence. |
| Consolidation | Options alert parser/executor | Discord options alerts, validation, and broker order execution workflows. |

Edge and Pulse should both remain useful independently:

- Edge without Pulse: analyze, simulate, show health/readiness, display tutorials, and stay quiet about expected missing execution infrastructure.
- Pulse without Edge: execute through its own controls.
- Edge plus Pulse: Edge can become the gated analysis layer that sends structured instructions to Pulse.

---

## Safety Model

Edge uses several layers of protection before any autonomous handoff can reach Pulse.

### What Edge will not do

- It does not place broker orders directly.
- It does not expose API key values to the browser.
- It does not store market-data API keys in frontend localStorage.
- It does not enable live handoff by default.
- It does not erase per-ticker automation preferences when the global handoff switch is turned off.
- It does not spam Pulse when Pulse is absent or its circuit breaker is open.

### Handoff gates

A Pulse handoff is blocked if any of these are true:

1. Global automation is disabled.
2. Mode is `recommend_only`.
3. The ticker is disabled.
4. Confidence is below `min_confidence`.
5. The ticker/action is still inside cooldown.
6. Pulse is unavailable.
7. Pulse circuit state is open.
8. The runtime is not ready for the requested workflow.

### Operator controls

Edge exposes:

- Scheduler pause/resume.
- Global kill switch status and toggle.
- Recommend-only / paper / live automation modes.
- Per-ticker handoff switches.
- Manual Pulse bridge controls for trailing stop and emergency exit.
- Readiness blockers before enabling paper handoff.
- Last handoff and last suppression status.
- Accessible UI warnings when refreshes fail or stale data is shown.

---

## Architecture

```text
Browser
  |
  | React + TypeScript + Vite
  v
Asset Command Console
  |-- Monitor mode
  |-- Command mode
  |-- Protect mode
  |-- Operations mode
  |     |-- Trading Overview
  |     |-- Advisor Health
  |     |-- Experience/RUM
  |     |-- Protection Ops
  |     |-- P&L Tracking
  |     |-- Market Coverage
  |     |-- Portfolio
  |     |-- System Settings
  |     `-- Tutorials
  `-- Settings mode
  |
  | native fetch API helpers
  v
FastAPI backend (`backend/server.py`)
  |-- health, liveness, readiness
  |-- ticker/config/decision APIs
  |-- provider catalog and provider health
  |-- automation settings and status
  |-- Pulse bridge endpoints
  |-- RUM ingest and rate-limit status
  |-- backtest, strategy, Monte Carlo endpoints
  |-- Prometheus `/metrics`
  |
  v
EvaluationScheduler (`backend/scheduler.py`)
  |-- active ticker loop
  |-- market data fetch and fallback
  |-- ORB / ATR / signal / correlation / risk context
  |-- DecisionEngine output
  |-- AutomationController handoff gate
  |
  +--> market-data providers
  |      |-- yfinance/keyless
  |      |-- Finnhub, Polygon, Alpha Vantage, Twelve Data when env keys exist
  |      `-- Stooq daily/EOD backfill only
  |
  +--> MongoDB when enabled
  |
  `--> PulseClient
         |-- health probe
         |-- circuit breaker
         |-- quiet standalone behavior
         |-- retry queue visibility
         `-- structured or legacy handoff to Sentinel Pulse
```

---

## Frontend Experience

The current app entry point mounts `AssetCommandConsole`, not a generic landing page. The console is built for repeated operational use: dense status, fast symbol switching, keyboard-aware tabs, runtime badges, and direct access to legacy dashboards inside the operations deck.

### Primary modes

| Mode | Purpose |
|------|---------|
| Monitor | Watch symbols, feed state, service rows, and system activity. |
| Command | Inspect a selected asset, prediction horizon, metric reels, watcher state, and command buttons. |
| Protect | Review risk/protection rows and trigger operator protection actions. |
| Operations | Open full dashboards: Trading Overview, Advisor Health, Experience, Protection Ops, P&L, Market Coverage, Portfolio, Settings, Tutorials. |
| Settings | Configure console display density and selected metric reels. |

### Operations modules

| Module | Details |
|--------|---------|
| Trading Overview | Active ticker view, correlation clusters with risk/trailing-stop recommendations, recent decisions, add/remove ticker actions, metric toggles, and partial-refresh warnings. |
| Advisor Health | Service liveness/readiness, Pulse state, provider health, fallback order, recommendation count, automation mode, kill switch, and runtime details. |
| Experience | Browser Web Vitals, backend RUM ingest status, rate-limit pressure, Grafana-style observability panels inside Experience, copyable Prometheus output, and frontend telemetry freshness. |
| Protection Ops | Safety guardrails, readiness blockers, scheduler controls, kill switch control, Pulse queue, handoff status, positions, trailing stop, and emergency exit bridge. |
| P&L Tracking | Pulse-backed account and P&L status when Pulse is available, with visible fallback errors. |
| Market Coverage | Market session status and cached fallback messages when backend refresh fails. |
| Portfolio | Pulse-backed portfolio analytics and position visibility when Pulse is available, with visible fallback errors. |
| System Settings | Local config, backend validation, provider catalog, operator notification channel discovery, preview-only confirmation workflows, automation controls, ticker handoff switches, and runtime metadata refresh warnings. |
| Tutorials | Learning paths, guide search, saved guides, notes, recent guides, import/export, reading mode, practice checklist, and module deep links. |

### UI reliability behavior

Recent UI reliability work makes dashboard failures explicit:

- Trading Overview warns when partial refreshes fail and keeps latest available data.
- Advisor Health warns when partial refreshes fail and preserves previous endpoint snapshots.
- Protection Ops warns when partial refreshes fail and preserves previous safety data.
- Settings warns when runtime metadata refreshes fail without overwriting save/validation errors.
- Ticker config load/action failures are visible.
- Tutorial local persistence failures are visible.
- Corrupt Settings localStorage is cleared and reported.

---

## Backend Capabilities

### FastAPI runtime

`backend/server.py` owns the main app, API router, lifecycle wiring, static frontend mounting, CORS, RUM ingest, rate limiting, readiness, metrics, and route registration.

Key runtime endpoints:

- `/api/live`: process liveness only.
- `/api/ready`: runtime dependency readiness.
- `/api/health`: high-level health state.
- `/metrics`: Prometheus text scrape endpoint outside the `/api` prefix.

### Evaluation scheduler

`backend/scheduler.py` continuously evaluates active tickers. For each ticker it can:

- Fetch price data using the configured provider order.
- Use WebSocket live-price triggers when available.
- Update market-hours metrics.
- Track active ticker state.
- Calculate ORB levels.
- Restore session-keyed ORB state on startup using the Eastern-time trading date and normalized persisted timestamps.
- Calculate ATR and volatility context.
- Evaluate signal/risk state through the engine.
- Query local or Pulse-backed position state.
- Produce enriched ticker state for the UI.
- Route eligible decisions through `_handoff_to_pulse()`.

### Decision and risk logic

Important backend modules include:

| Module | Responsibility |
|--------|----------------|
| `backend/engine.py` | Decision engine and risk logic. |
| `backend/scheduler.py` | Runtime evaluation loop and handoff integration. |
| `backend/orb.py` | Opening Range Breakout tracking. |
| `backend/atr.py` | Average True Range and volatility calculations. |
| `backend/signals.py` and `backend/signals_enhanced.py` | Signal generation and Prometheus metric updates. |
| `backend/market_hours.py` | Market session logic and market-hours metrics. |
| `backend/position_tracker.py` | Local/Pulse-aware position tracking mode. |
| `backend/correlation.py` and `backend/analyst/correlation/engine.py` | Correlation analysis, correlation risk recommendation payloads, and standalone-safe Pulse override behavior. |
| `backend/state_persistence.py` | State reconciliation and restoration helpers. |

### Rate limiting

Edge exposes aggregate API rate-limit status and browser-visible retry headers:

- `/api/rate-limit/status`
- `Retry-After`
- `RateLimit-Limit`
- `RateLimit-Remaining`
- `RateLimit-Reset`
- `X-RateLimit-*` compatibility headers

The frontend Experience dashboard surfaces rate-limit pressure so RUM or API clients do not fail silently.

---

## Market Data

Edge supports a safe provider fallback model. Providers that require API keys are only used when their backend environment variables are present.

| Provider | Role |
|----------|------|
| yfinance | Keyless/default provider for local beta and fallback. |
| Finnhub | Enabled by `FINNHUB_API_KEY`. |
| Polygon | Enabled by `POLYGON_API_KEY`. |
| Alpha Vantage | Enabled by `ALPHA_VANTAGE_API_KEY`. |
| Twelve Data | Enabled by `TWELVE_DATA_API_KEY`. |
| Alpaca market-data stream | Enabled by `ALPACA_MARKET_DATA_API_KEY` and `ALPACA_MARKET_DATA_SECRET_KEY`; do not use broker trading credentials in Edge. |
| Stooq | Daily/EOD backfill only; excluded from intraday scheduler fallback. |

Provider metadata is browser-safe:

- API key values are never returned.
- Provider catalog only exposes configured/not-configured booleans and capability metadata.
- Settings displays provider availability read-only.
- Old secret-like localStorage fields are filtered during Settings load/save migration.

Relevant modules:

- `backend/providers/catalog.py`
- `backend/providers/health.py`
- `backend/price_fetcher.py`
- `backend/providers/*_provider.py`

---

## Automation and Pulse Handoff

Automation is intentionally separate from signal generation. Edge can recommend continuously while still refusing to send Pulse commands unless the operator enables the required gates.

### Automation settings

`backend/automation.py` defines:

| Field | Meaning |
|-------|---------|
| `global_enabled` | Master handoff switch. |
| `mode` | `recommend_only`, `paper`, or `live`. |
| `default_ticker_enabled` | Default per-ticker handoff state. |
| `per_ticker_enabled` | Explicit ticker overrides. |
| `min_confidence` | Minimum confidence required before handoff. |
| `cooldown_seconds` | Per-symbol/action cooldown. |
| `quiet_when_pulse_absent` | Suppress expected Pulse-absent noise. |

Local settings are persisted to:

```text
data/automation_settings.json
```

Override path:

```text
EDGE_AUTOMATION_STATE_FILE=C:\path\to\automation_settings.json
```

### Handoff actions

The command schema supports these action types:

- `buy`
- `stop_buying`
- `stop_all`
- `regular_stop`
- `trailing_stop`
- `tighten_stop`
- `tighten_trailing_stop`
- `dca`
- `emergency_exit`

Payloads can include:

- symbol
- action
- confidence
- reason
- mode
- ORB session tag, with true ORB values `premarket_30m` and `market_open`; non-ORB strategy context values such as `puzzle_key` are separated in the schema contract, and unknown values are rejected before sending to Pulse.
- stop/trailing/DCA recommendation fields
- idempotency key
- metadata such as ATR, price, PnL, trend, drawdown, and signal strength

### Pulse client behavior

`backend/pulse_client.py` owns Pulse connectivity:

- Health probing.
- Circuit breaker state: `CLOSED`, `OPEN`, `HALF_OPEN`.
- Quiet standalone behavior.
- Retry queue visibility.
- Pulse account/position/queue calls.
- Manual bridge calls for trailing stops and emergency exits.
- Autonomous handoff through `PULSE_HANDOFF_ENDPOINT` when configured.
- Versioned handoff contract discovery through `/api/pulse/handoff/schema` with contract version `edge.pulse.handoff.v1`, with Settings rendering field semantics such as allowed mode, action, stop, DCA, and handoff session-context values.
- Structured handoff transport headers: `Idempotency-Key`, `X-Edge-Mode`, and `X-Edge-Contract-Version`.
- Decision Feed Pulse feedback visibility for accepted, rejected, failed, and suppressed handoff outcomes tied to the decision that produced them.
- Pulse feedback normalization promotes common Pulse response fields such as `handoff_id` and operator-facing `message` to stable top-level feedback fields while preserving the raw response payload for diagnostics.
- accepted/rejected/failed feedback semantics so Edge can distinguish Pulse acceptance, risk-limit rejection, and transport or processing failure.
- Legacy fallback to `/api/tickers/{symbol}/decision` when no structured endpoint is configured.

---

## Observability and Operations

Edge includes both in-app observability and an external LGTM-style stack.

### In-app observability

- Advisor Health dashboard for backend and automation health.
- Experience dashboard for frontend Web Vitals, RUM ingest, API rate-limit pressure, and Grafana-style observability panels inside Experience.
- Protection Ops dashboard for runtime safety controls.
- Market Coverage dashboard for market-session visibility.
- Settings metadata warnings when backend metadata is stale.
- Settings operator notification channel discovery for Telegram, Discord/Echo, Slack, and WhatsApp-style paths without exposing secret values.
- Settings notification confirmation preview contract discovery for live handoff, emergency-exit, risk-reduction, and trailing-stop review prompts. The preview contract is redacted and has no delivery side effects.
- Settings notification confirmation feedback contract discovery for future operator approve/reject relay callbacks. The feedback contract is redacted, has no Pulse side effects, and preserves mode/target idempotency scope for paper/live review paths.

### Metrics

Prometheus metrics are exposed at:

```text
/metrics
```

Tracked areas include:

- readiness checks
- scheduler/evaluation state
- market-hours state
- automation handoff outcomes
- Pulse circuit and retry behavior
- frontend RUM samples
- API rate-limit rejections and bucket pressure
- ATR/volatility/signal metrics

### Docker observability stack

`docker-compose.yml` includes:

| Service | Purpose |
|---------|---------|
| sentinel-edge | FastAPI app and metrics endpoint. |
| mongodb | Runtime data store with replica set for change streams. |
| prometheus | Metrics collection and alert rules. |
| grafana | Dashboards for Edge, broker health, frontend experience, readiness, and operations. |
| alertmanager | Alert routing to human notification channels and webhooks. |
| loki | Log storage. |
| promtail | Log shipping. |
| tempo | OpenTelemetry trace storage/query. |

Runbooks live in `docs/runbooks/` and are linked from alert rules.

---

## Simulation and Backtesting

Edge includes backtesting and simulation endpoints used by the UI and strategy workflows:

- Basic backtest execution.
- Full backtest run creation.
- Run listing.
- Report retrieval.
- Strategy catalog and strategy details.
- Puzzle Key strategy status.
- Dry-run status.
- Strategy optimization.
- Monte Carlo chart listing and chart serving.
- Market Map uses Chart Workspace snapshots through `/api/chart-workspace/{symbol}`, including toggleable ORB overlays, per-session ORB overlay filters, EMA/SMA, RSI, MACD, indicator presets, strategy context panels, latest EMA/SMA, RSI, and MACD values, chart-ready OHLCV bars, a persistent volume overlay control, crosshair-style hover context, UI-ready context for persistent Morning Plan/Intraday Alerts/Replay Proof presets, persistent Analysis/Execution/Research layouts, persistent symbol, chart-type, indicator, and range preferences, and the last Simulation Lab result with symbol and timestamp context so operators can clear stale persisted Simulation Lab context. The workspace also guards duplicate Simulation Lab submissions while a replay or experiment request is in flight, with Lab run actions disabled until chart bars are loaded, flags persisted Simulation Lab results when their symbol differs from the active chart, surfaces allocation skip reasons, and adds an operator-friendly result provenance badge.

### Market Map

The Operations deck exposes Market Map as the operator chart cockpit. It keeps the legacy `/api/chart-workspace/{symbol}` compatibility endpoint while adding Market Map presets for Morning Plan, Intraday Alerts, and Replay Proof. Market Map overlays support/resistance levels from the chart snapshot so operators can inspect session high/low, premarket high/low, VWAP, ATR bands, and ORB context without turning the chart into an order-entry surface. Market Map is read-only for broker activity and does not arm or submit live trades.

Market Map never submits broker orders, never arms live trading, and treats missing chart, option, or proof data as review/block context instead of a silent default.

The Simulation Lab foundation is default-hidden and off unless `EDGE_SIMULATION_LAB_ENABLED` is explicitly enabled. Its status contract is available at `/api/simulation-lab/status` so the UI and future lab workflows can discover whether experimental surfaces should be visible without accidentally exposing unfinished controls. Each experiment entry includes endpoint path, method, and result schema version metadata, plus result metadata fields, for client-side discovery. Runnable lab results include a deterministic `run_id`, full `input_fingerprint`, and `input_fingerprint_algorithm` (`sha256.canonical_json.v1`) so operators can compare repeated replays and correlate saved UI context without implying live execution. The initial Lab roadmap covers:

Simulation Lab status in Settings mirrors the same gate, disabled reason, experiment catalog, and result metadata fields read-only, so operators can confirm the backend lab posture without enabling experimental actions.

- ORB backtesting through the gated `/api/simulation-lab/orb/backtest` replay endpoint, including per-breakout risk/reward scoring from the opposite ORB boundary, target/stop/open outcome scoring, average realized R, and summary fields for scored breakouts, average reward R, maximum risk per share, and maximum reward per share.
- Buying-power allocation experiments through `/api/simulation-lab/buying-power/allocation`, including requested demand, unfilled demand, aggregate fill-ratio summaries, position-cap constraint attribution, `buying_power_exhausted` skipped-candidate explanations, and post-capacity fill ratios.
- Stop, trailing-stop, and DCA comparisons (`stop vs trailing-stop vs DCA comparisons`) through `/api/simulation-lab/stop-trailing-dca/compare`, ranking the same long trade path against fixed-stop, trailing-stop, and averaging assumptions by both absolute P&L and normalized P&L percentage.

These capabilities are intended for research, replay, and validation. They should remain clearly separated from live automation unless an operator deliberately promotes a tested workflow into a gated automation path.

---

## Learning Center

The Tutorials dashboard is an in-app learning system for operators and developers. It includes:

- Guided dashboard tutorials.
- Learning paths.
- Search and highlighting.
- Saved guides.
- Recently viewed guides.
- Personal notes.
- Reading comfort mode.
- Completion state.
- Practice checklists.
- Bulk practice actions.
- Import/export for learning state.
- Deep links back into operational modules.

The tutorial state is stored locally in the browser and now reports persistence failures instead of silently losing learning progress.

---

## Repository Layout

```text
sentinel-edge/
|-- backend/
|   |-- server.py                      # FastAPI app, routes, metrics, static frontend mount
|   |-- scheduler.py                   # Evaluation loop, ticker state, Pulse handoff gate
|   |-- automation.py                  # Global/per-ticker handoff settings and gating
|   |-- pulse_client.py                # Pulse HTTP client, circuit breaker, handoff transport
|   |-- engine.py                      # Decision/risk logic
|   |-- orb.py                         # Opening Range Breakout state
|   |-- atr.py                         # Average True Range calculations
|   |-- price_fetcher.py               # Provider fallback and data fetch orchestration
|   |-- market_hours.py                # Market session logic
|   |-- frontend_rum.py                # Browser RUM route normalization and budgeting helpers
|   |-- providers/                     # Market-data provider catalog, health, integrations
|   |-- analyst/                       # Analyst core, correlation, observability helpers
|   |-- backtest/                      # Backtest and simulation engines
|   |-- options/                       # Options/Greeks modules
|   |-- tests/                         # Unit, integration-style, and static regression tests
|   |-- requirements.txt
|   `-- requirements-dev.txt
|-- frontend/
|   |-- src/
|   |   |-- App.tsx                    # Mounts AssetCommandConsole
|   |   |-- lib/api.ts                 # Native fetch API helpers
|   |   |-- lib/webVitals.ts           # Browser RUM/Web Vitals collection
|   |   |-- components/asset-command/  # Primary operator console
|   |   |-- components/dashboards/     # Operations modules
|   |   `-- components/tutorials/      # Learning Center
|   |-- package.json
|   `-- vite.config.ts
|-- docs/
|   |-- runbooks/                      # Alert/runbook procedures
|   |-- tutorials/                     # Tutorial content
|   `-- superpowers/plans/             # Implementation plans and refactor plans
|-- grafana/                           # Provisioned dashboards
|-- prometheus/                         # Prometheus rules and Alertmanager config
|-- scripts/
|   `-- verify-local.ps1               # Local verification gate
|-- Launch-Sentinel-Bot-Suite.ps1      # Windows suite launcher for Edge, Pulse, Darkpool, Discord, Crypto, and Tandem
|-- Launch-Sentinel-Bot-Suite.bat
|-- Launch-Sentinel-Edge.ps1           # Windows installed-app launcher with first-run dependency repair
|-- Launch-Sentinel-Edge.bat
|-- Launch-Sentinel-Edge-Local.ps1      # Windows source launcher
|-- Launch-Sentinel-Edge-Local.bat
|-- docker-compose.yml
`-- README.md
```

---

## Quick Start

### Option 0: Windows bot suite launcher

From this repository root, double-click `Launch-Sentinel-Bot-Suite.bat` or run:

```powershell
.\Launch-Sentinel-Bot-Suite.ps1
```

The suite launcher starts the local Sentinel Edge, Sentinel Pulse, Darkpool Monitor, Discord options bot, Auto-Crypto, and Sentinel Tandem Suite launchers from the local paths used on this workstation. By default it suppresses individual component browser windows, then opens Tandem as the main operator console.

Useful flags:

| Flag | Purpose |
|------|---------|
| `-InstallDeps` | Forward dependency installation to child launchers. |
| `-OpenComponentBrowsers` | Also open Edge, Pulse, Darkpool, Discord, and Crypto browser windows. |
| `-NoBrowser` | Do not open Tandem automatically. |
| `-SkipEdge`, `-SkipPulse`, `-SkipDarkpool`, `-SkipDiscord`, `-SkipCrypto`, `-SkipTandem` | Launch a smaller local set. |
| `-NoWait` | Send launch requests and let this suite window exit. |

### Option 1: Windows beta installer

Beta testers should use `SentinelEdge-Setup-<version>.exe` from the Windows installer artifact or release download. After installation, double-click the `Sentinel Edge` Desktop or Start Menu shortcut.

The installed launcher downloads missing runtime dependencies on first launch. It checks for the Visual C++ Runtime, checks whether MongoDB is already reachable on port `27017`, reuses a system or cached `mongod.exe` when available, and downloads portable MongoDB into `%LOCALAPPDATA%\Sentinel Edge\dependencies` when it is missing. Later launches reuse the cached dependency folder.

The installed app does not require Python, Node.js, npm, or a developer checkout. Logs for support are written to the Desktop:

```text
Sentinel-Edge.log
Sentinel-Edge-Transcript.log
Sentinel-Edge-MongoDB.log
```

Use the source launcher below only when running from a repository checkout.

If the installed-app launcher is accidentally run from a source checkout and `SentinelEdge.exe` is not present, it falls back to `Launch-Sentinel-Edge-Local.ps1` after starting MongoDB. That fallback is intended for developer/source folders only; a real installed package should contain `SentinelEdge.exe`.

### Option 2: Windows local source launcher

From the repository root:

```powershell
.\Launch-Sentinel-Edge-Local.ps1 -InstallDeps
```

Useful flags:

| Flag | Purpose |
|------|---------|
| `-BackendPort 8000` | Choose backend port. |
| `-FrontendPort 3000` | Choose frontend port. |
| `-NoBrowser` | Do not open a browser automatically. |
| `-InstallDeps` | Install backend/frontend dependencies before launch. |

The launcher looks for Python 3.11, 3.12, or 3.13, creates/uses the backend virtualenv, starts Vite, starts the backend, waits for readiness, and logs to `Sentinel-Edge-Local.log` on the Desktop.

The launcher also mirrors the Sentinel Pulse local launcher lifecycle. When it can find Edge or Chrome, it opens the UI in an isolated temporary browser profile. Closing that dedicated browser window shuts down the Edge backend/frontend processes started by this launcher. Closing the launcher window or pressing Ctrl+C starts cleanup in the other direction: the browser profile is closed, temporary profile files are removed, and the owned backend/frontend process trees are stopped. Use `-NoBrowser` for headless runs where browser-close monitoring is intentionally disabled.

### Option 3: macOS beta installer

MacBook beta testers can install the local source build with the bundled macOS installer script. It creates the backend virtual environment, installs frontend dependencies, and adds a double-click launcher to the Desktop.

Prerequisites:

- macOS with Python 3.11, 3.12, or 3.13 on `PATH`
- Node.js 20+ with `npm`
- MongoDB Community with `mongod` available on `PATH`

Install MongoDB with Homebrew if needed:

```bash
brew tap mongodb/brew
brew install mongodb-community
```

From the repository root:

```bash
chmod +x install-macos.sh
./install-macos.sh
```

After installation, double-click `Sentinel Edge.command` on the Desktop. The launcher starts MongoDB when it is not already listening on port `27017`, starts the backend on `8000`, starts the frontend on `3000`, and opens the console. Logs are written to `~/Desktop/Sentinel-Edge-Local.log` and `~/Desktop/Sentinel-Edge-MongoDB.log`.

Manual launch options:

```bash
./install-macos.sh --launch
./install-macos.sh --launch --install-deps
./install-macos.sh --launch --backend-port 8000 --frontend-port 3000 --no-browser
./install-macos.sh --launch --skip-mongo
```

### Option 4: Manual backend

From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
$env:SENTINEL_EDGE_PORT = "8000"
.\.venv\Scripts\python.exe server.py
```

Or with uvicorn:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

### Option 5: Manual frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend dev server defaults to Vite behavior. The local launcher uses port `3000` in the workstation bot-suite map.

### Option 6: Docker stack

```powershell
docker compose up -d
```

Default exposed services:

| Service | URL |
|---------|-----|
| Edge API | `http://localhost:8001` |
| Edge metrics | `http://localhost:8001/metrics` |
| Grafana | `http://localhost:3001` |
| Prometheus | `http://localhost:9090` |
| Alertmanager | `http://localhost:9093` |
| Loki | `http://localhost:3100` |
| Tempo | `http://localhost:3200` |

---

## Local Launcher Lifecycle

`Launch-Sentinel-Edge-Local.ps1` is the recommended Windows-local operator entrypoint for source-tree work. It intentionally owns only the processes it starts; it does not kill unrelated Edge, Pulse, Tandem, browser, or broker software unless that process is occupying the selected local port and the launcher is explicitly replacing it during startup.

Lifecycle behavior:

1. The launcher resolves Python, npm, backend, and frontend paths.
2. It starts the backend from `backend/server.py` through uvicorn on `127.0.0.1:$BackendPort`.
3. It starts the Vite frontend on `127.0.0.1:$FrontendPort`.
4. It verifies backend readiness at `/api/ready` and frontend identity before reporting the UI as ready.
5. Unless `-NoBrowser` is set, it opens the frontend in a dedicated Edge/Chrome app window using a temporary `--user-data-dir`.
6. It records all browser processes tied to that temporary profile, including the visible window process.
7. A hidden watchdog watches the launcher process. If the command window exits unexpectedly, the watchdog closes the browser profile and stops the owned backend/frontend process trees.
8. The foreground loop watches the browser window. If the dedicated browser window closes, the launcher logs `Browser window closed; shutting down Sentinel Edge` and cleans up owned tasks.

This behavior keeps local tests tidy: closing the UI closes the local services, and closing the command window closes the UI. It also avoids mixing the operator's normal browser profile with bot-control pages.

Launcher logs are written to:

```text
%USERPROFILE%\Desktop\Sentinel-Edge-Local.log
```

Temporary browser profiles use the system temp folder and names like:

```text
SentinelEdge-Local-Browser-<launcher-pid>
```

---

## Configuration

### Core runtime

| Variable | Purpose | Default/notes |
|----------|---------|---------------|
| `MONGO_URL` | MongoDB connection string. | Used by Docker and backend runtime. |
| `DB_NAME` | MongoDB database name. | `sentinel_edge`. |
| `DB_HOST` | MongoDB host for local code paths. | `localhost`. |
| `DB_PORT` | MongoDB port. | `27017`. |
| `CORS_ORIGINS` | Comma-separated allowed origins. | Explicit localhost origins in Docker; wildcard disables credentialed CORS. |
| `GLOBAL_KILL_SWITCH` | Initial kill switch state. | `false`. |
| `EDGE_TEST_COMMAND_ENDPOINTS_ENABLED` | Enables `/api/test/*` command-bus injection/inspection endpoints. | `false`; disabled by default and intended only for isolated local testing. |

### Local server/browser

| Variable | Purpose |
|----------|---------|
| `SENTINEL_EDGE_HOST` | Backend bind host. |
| `SENTINEL_EDGE_PORT` | Backend port; direct server default is `8001`. |
| `SENTINEL_EDGE_OPEN_BROWSER` | Set `false` to disable browser launch from direct startup paths. |
| `SENTINEL_EDGE_UI_URL` | Override UI URL opened by the backend startup helper. |

### Pulse integration

| Variable | Purpose |
|----------|---------|
| `PULSE_API_URL` | Sentinel Pulse API base URL. |
| `PULSE_API_KEY` | Optional Pulse API key header. |
| `PULSE_HANDOFF_ENDPOINT` | Optional structured Pulse handoff endpoint. If unset, Edge can fall back to legacy decision endpoint behavior. |
| `EDGE_OPERATOR_ACTION_SECRET` | Required shared secret for manual `/api/pulse/emergency-exit/*`, `/api/pulse/trailing-stop/*`, `/api/bus/events`, `/api/bus/edge-actions`, scheduler resume, kill-switch disarm, and live automation escalation requests. Send as `X-Edge-Operator-Secret`; protected endpoints fail closed when unset. |

Live automation escalation also requires the explicit confirmation phrase `ENABLE LIVE AUTOMATION`. Send it as `live_readiness_signoff` in the automation request body or as `X-Edge-Live-Readiness-Signoff` for ticker add/remove paths that can alter live handoff scope. This is separate from the operator secret: the secret authorizes the caller, while the phrase records an intentional live-readiness signoff step.

### Automation

| Variable | Purpose |
|----------|---------|
| `EDGE_PULSE_HANDOFF_ENABLED` | Initial global handoff switch. |
| `EDGE_AUTOMATION_MODE` | Initial mode: `recommend_only`, `paper`, or `live`. |
| `EDGE_PULSE_HANDOFF_DEFAULT_TICKERS` | Initial default per-ticker handoff state. |
| `EDGE_AUTOMATION_STATE_FILE` | Override local automation settings file. |

### Simulation Lab

| Variable | Purpose |
|----------|---------|
| `EDGE_SIMULATION_LAB_ENABLED` | Enables default-hidden Simulation Lab discovery and future experimental surfaces. |

### Market data

| Variable | Purpose |
|----------|---------|
| `MARKET_DATA_PROVIDER_ORDER` | Comma-separated intraday provider order. |
| `FINNHUB_API_KEY` | Enables Finnhub. |
| `POLYGON_API_KEY` | Enables Polygon. |
| `ALPHA_VANTAGE_API_KEY` | Enables Alpha Vantage. |
| `TWELVE_DATA_API_KEY` | Enables Twelve Data. |
| `ALPACA_MARKET_DATA_API_KEY` | Enables Alpaca market-data websocket streaming. |
| `ALPACA_MARKET_DATA_SECRET_KEY` | Secret for Alpaca market-data websocket streaming. |
| `ALPACA_MARKET_DATA_WS_URL` | Optional Alpaca market-data websocket URL override. |

### Observability and alerts

| Variable | Purpose |
|----------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint for traces. |
| `OTEL_SERVICE_NAME` | OpenTelemetry service name. |
| `ANALYST_START_METRICS_SERVER` | Start optional analyst metrics server. |
| `WEBHOOK_SECRET` | Required Alertmanager webhook receiver secret for action-capable `/alerts` webhooks. |
| `TELEGRAM_BOT_TOKEN` | Optional Telegram alerting token. |
| `TELEGRAM_TRADING_CHAT` | Optional Telegram chat ID. |
| `SLACK_WEBHOOK_URL` | Optional Slack webhook URL. |
| `DISCORD_WEBHOOK_URL` | Optional Discord/Echo relay webhook URL for notification discovery. |
| `WHATSAPP_WEBHOOK_URL` | Optional WhatsApp relay webhook URL for notification discovery. |
| `RETRY_QUEUE_LOG_DIR` | Retry queue shutdown log directory. |

---

## API Reference

All application API endpoints below are under `/api` unless noted otherwise.

### Runtime and health

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Basic service identity and running/stopped state. |
| GET | `/live` | Process liveness without dependency checks. |
| GET | `/health` | High-level runtime health. |
| GET | `/ready` | Dependency readiness; returns 503 with blocker details when not ready. |
| GET | `/stats` | Scheduler/runtime statistics. |
| GET | `/markets` | Market session coverage. |
| GET | `/queue` | Runtime queue status. |
| POST | `/control/pause` | Pause scheduler immediately. |
| POST | `/control/resume` | Resume scheduler; requires `X-Edge-Operator-Secret`. |

### Tickers, decisions, and config

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/tickers` | Active ticker list with enriched state. |
| POST | `/tickers/{symbol}` | Add ticker. Requires `X-Edge-Operator-Secret` when global live automation and default ticker handoff are enabled. |
| DELETE | `/tickers/{symbol}` | Remove ticker. Requires `X-Edge-Operator-Secret` when global live automation is active. |
| GET | `/tickers/{symbol}/config` | Read ticker metric/risk config. |
| PUT | `/tickers/{symbol}/config` | Update ticker config. |
| GET | `/decisions` | Recent advisor decisions. |
| POST | `/config/validate` | Validate browser/local config against backend schema. |
| GET | `/config/hash` | Return backend config hash metadata. |
| GET | `/correlation` | Return correlation cluster state. |

### Provider and market data

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/providers/health` | Provider health state. |
| GET | `/market-data/providers` | Browser-safe provider catalog and fallback order. |
| GET | `/providers` | Provider list alias. |
| GET | `/providers/config` | Redacted provider config metadata. |
| GET | `/price/{symbol}` | Current price. |
| GET | `/quote/{symbol}` | Current quote. |
| GET | `/orb/{symbol}` | ORB levels and status. |
| GET | `/chart-workspace/{symbol}` | Return chart-ready OHLCV bars, ORB overlays, and EMA/SMA, RSI, MACD indicator series. |

### Automation

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/automation` | Current handoff settings, last handoff, and last suppression. |
| PUT | `/automation` | Patch global/default automation settings. Live-mode escalation requires `X-Edge-Operator-Secret`. |
| PUT | `/automation/tickers/{symbol}` | Enable or disable one ticker for handoff. Enabling handoff while global live automation is active requires `X-Edge-Operator-Secret`. |

### Pulse bridge

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/pulse/health` | Detailed Pulse health. |
| GET | `/pulse/handoff/schema` | Edge-to-Pulse structured handoff contract for `PULSE_HANDOFF_ENDPOINT` (`edge.pulse.handoff.v1`). |
| GET | `/pulse/status` | Pulse availability and circuit status. |
| GET | `/pulse/positions` | Pulse-synced positions. |
| GET | `/pulse/positions/{symbol}` | One Pulse-synced position. |
| GET | `/pulse/queue` | Pulse retry queue. |
| GET | `/pulse/account` | Pulse account view. |
| POST | `/pulse/emergency-exit/{symbol}` | Manual emergency-exit bridge to Pulse; requires `X-Edge-Operator-Secret`. |
| POST | `/pulse/trailing-stop/{symbol}` | Manual trailing-stop bridge to Pulse; requires `X-Edge-Operator-Secret`. |
| POST | `/test/pulse-command` | Test Pulse command path; disabled by default unless `EDGE_TEST_COMMAND_ENDPOINTS_ENABLED=true`. |
| POST | `/test/send-command` | Test command send path; disabled by default unless `EDGE_TEST_COMMAND_ENDPOINTS_ENABLED=true`. |
| GET | `/test/commands` | Inspect test commands; disabled by default unless `EDGE_TEST_COMMAND_ENDPOINTS_ENABLED=true`. |

### Cross-bot event bus

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/bus/events` | Recent local bot events. |
| POST | `/bus/events` | Publish a local bot event; requires `X-Edge-Operator-Secret`. |
| POST | `/bus/edge-actions` | Publish a manual Edge action event; requires `X-Edge-Operator-Secret`. |

### Backtest, simulation, and strategies

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/backtest` | Run basic backtest. |
| POST | `/backtest/run` | Create full backtest run. |
| GET | `/backtest/runs` | List backtest runs. |
| GET | `/backtest/report/{run_id}` | Fetch backtest report. |
| POST | `/backtest/optimize` | Run strategy optimization. |
| GET | `/backtest/monte-carlo/charts` | List Monte Carlo chart artifacts. |
| GET | `/backtest/monte-carlo/charts/{run_id}/{chart_name}` | Fetch a Monte Carlo chart artifact. |
| GET | `/simulation-lab/status` | Return the default-hidden Simulation Lab gate, planned experiment catalog, and result metadata field discovery. |
| POST | `/simulation-lab/orb/backtest` | Replay explicit OHLC bars through a gated ORB backtest scan with optional `target_r_multiple` risk/reward and target/stop/open outcome scoring. |
| POST | `/simulation-lab/buying-power/allocation` | Compare gated buying-power allocation plans for candidate trades with requested, unfilled, fill-ratio, position-limit, and post-capacity fill summaries. |
| POST | `/simulation-lab/stop-trailing-dca/compare` | Compare fixed-stop, trailing-stop, and DCA assumptions against one gated price path with absolute and percentage-normalized P&L summaries. |
| GET | `/strategies` | Strategy catalog. |
| GET | `/strategies/puzzle-key/status` | Puzzle Key strategy status. |
| GET | `/strategies/{strategy_name}` | Strategy details. |
| GET | `/dry-run/status` | Dry-run/simulation status. |

### Frontend experience and rate limits

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/frontend/rum` | Ingest browser Web Vitals/RUM snapshot. |
| GET | `/frontend/rum/status` | Return frontend RUM ingest freshness/status. |
| GET | `/rate-limit/status` | Aggregate API rate-limit pressure/status. |
| GET | `/notifications/status` | Redacted operator notification channel discovery for Settings. |
| POST | `/notifications/confirmation/preview` | Build a redacted, preview-only operator confirmation payload for safety-sensitive notification workflows. |
| POST | `/notifications/confirmation/feedback` | Normalize redacted operator confirmation feedback, including parsed mode/target idempotency scope, without sending notifications or Pulse commands. |

### Non-API routes

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/metrics` | Prometheus scrape endpoint. |
| mixed | `/api/webhook/*` | Alertmanager webhook receiver from `webhook_router`. |
| mixed | `/alerts` | Alert handler routes. |
| mixed | `/export/*` | Export API routes for trades/P&L. |

---

## Verification

Run the main local verification gate from the repository root:

```powershell
.\scripts\verify-local.ps1
```

Install missing backend dev dependencies:

```powershell
.\scripts\verify-local.ps1 -InstallBackendDevDeps
```

Install missing frontend dependencies too:

```powershell
.\scripts\verify-local.ps1 -InstallBackendDevDeps -InstallFrontendDeps
```

Write a JSON summary:

```powershell
.\scripts\verify-local.ps1 -SummaryPath .\verification-summary.json
```

The verification runner checks:

- backend unittest discovery
- backend static unittest discovery
- frontend lint
- frontend production build
- frontend npm audit at moderate level
- workspace whitespace via `git diff --check`

CI also includes `macOS Smoke Checks` in `.github/workflows/macos-smoke.yml`. The macOS workflow is a smoke gate: it runs backend static contract tests plus frontend install, lint, and production build on `macos-latest`. Windows installer remains the packaging path; macOS packaging should stay separate until it is deliberately designed and tested.

### Live-Money Readiness Status - 2026-06-24

Current status: paper automation and Pulse handoff testing are operational; live automation remains gated.

Latest local verification:
- Backend tests: `python -m pytest backend\tests -q` -> 483 passed, 134 skipped, 62 subtests passed.
- Live-scope controls require the operator secret plus the explicit `ENABLE LIVE AUTOMATION` phrase before live automation escalation or live-scope ticker mutation.
- Pulse handoff feedback, scheduler feedback, automation metrics, and operator-secret boundaries have regression coverage.
- Tandem observed Edge health and Pulse broker state after the VPG paper handoff drill.

Open gates before live-money use:
- Multi-session paper automation evidence using the production Pulse stack.
- Active-order broker reconnect and catch-up evidence.
- Market-transition monitoring across close, overnight, and next open.
- Controlled operator access review and final operator signoff.

Focused commands:

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests
backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*static.py"
python -m unittest backend.tests.test_local_launcher_lifecycle_static -v

cd frontend
npm run lint
npm run build
npm audit --audit-level=moderate
```

For docs-only changes, at minimum run:

```powershell
git diff --check
```

---

## Operational Playbooks

Runbooks live in `docs/runbooks/` and cover common production and local-beta incidents:

- `edge-runtime-not-ready.md`
- `engine-not-running.md`
- `engine-paused.md`
- `sidecar-down.md`
- `pulse-circuit-breaker.md`
- `pulse-api-slo-burn.md`
- `automation-handoff-failures.md`
- `price-fetch-failures.md`
- `stale-data.md`
- `slow-evaluation.md`
- `drawdown-risk.md`
- `consecutive-losses.md`
- `low-win-rate.md`
- `correlation-cluster.md`
- `auto-stop-triggered.md`
- `frontend-core-web-vitals.md`
- `frontend-rum-ingest-missing.md`
- `frontend-rum-dropped-metrics.md`
- `api-rate-limit-rejections.md`
- `api-rate-limit-bucket-pressure.md`

Alert rules reference these runbooks so an operator can move from Grafana/Alertmanager to remediation steps quickly.

---

## Development Standards

### Security and secret handling

- Keep API keys in backend environment variables only.
- Keep broker/trading account credentials out of Edge; broker connectivity belongs to Pulse.
- Do not add frontend API-key inputs unless they are explicitly redacted and never persisted.
- Do not commit generated runtime state, local automation state, virtualenvs, `node_modules`, or verification summaries.
- Keep provider config endpoints redacted.
- Keep CORS configuration explicit in deployed environments.

### UI reliability

- Visible user-facing actions should surface failures.
- Partial polling failures should preserve the last known good snapshot when possible.
- Alerts should use accessible `role="alert"` where the user needs to know immediately.
- Offline/demo/standalone paths should be clear rather than noisy.

### Backend reliability

- Keep liveness and readiness separate.
- Do not make readiness succeed when core dependencies are missing.
- Keep metrics labels low-cardinality.
- Keep rate-limit status observable.
- Keep Pulse absence quiet in demo/standalone mode.
- Keep automation gates separate from decision generation.

### Testing approach

The repository uses a mix of:

- Python unit tests.
- Static regression tests that lock important frontend/backend strings and route contracts.
- Frontend lint/build verification.
- npm audit.
- Docker/Grafana/Prometheus static checks.

Static tests are intentionally used for safety-sensitive UI and configuration contracts where a full browser test would be heavier than the protected behavior.

---

## Roadmap

Near-term priorities:

1. ORB session model v1
   - premarket and market-open session separation
   - persisted ORB state
   - UI-visible ORB readiness and decision context

2. Structured Pulse handoff contract
   - finalize `PULSE_HANDOFF_ENDPOINT`
   - align accepted/rejected response shape
   - preserve idempotency and paper/live semantics

3. Simulation Lab foundation
   - ORB strategy replay with risk/reward and outcome scoring
   - buying-power allocation experiments with demand-fill, position-limit, and post-capacity fill summaries
   - stop/trailing/DCA comparisons with normalized P&L percentage summaries
   - deterministic `run_id` and `input_fingerprint` metadata for replay comparison
   - default-hidden until explicitly enabled

4. Market Map
   - ORB overlays
   - indicator toggles
   - strategy context panels
   - operator-friendly layout customization

5. Operator notification paths
   - Telegram/Discord/Slack/WhatsApp-style review and confirmation flows
   - human-in-the-loop handoff confirmation

6. Packaging and cross-platform polish
   - stable Windows local beta
   - installer/runtime cleanup
   - later macOS workflow after Windows local beta is stable

---

## License

No license file is present in this checkout. Add a `LICENSE` file before publishing or distributing the repository outside the current private/internal workflow.
