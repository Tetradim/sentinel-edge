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
- Demo mode can run without MongoDB.
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
| Chart workspace | Chart-ready OHLCV snapshots, toggleable ORB overlays with per-session ORB overlay filters, EMA/SMA, RSI, MACD, indicator presets, strategy context panels, chart replay actions, persistent Analysis/Execution/Research layouts, and persistent symbol, chart-type, indicator, and range preferences. |
| Safety controls | Kill switch, scheduler pause/resume, recommend-only mode, Pulse circuit breaker, quiet standalone suppression, read-only provider secrets policy. |

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
- ORB session tag
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
- Versioned handoff contract discovery through `/api/pulse/handoff/schema` with contract version `edge.pulse.handoff.v1`.
- Structured handoff transport headers: `Idempotency-Key`, `X-Edge-Mode`, and `X-Edge-Contract-Version`.
- Decision Feed Pulse feedback visibility for accepted, rejected, failed, and suppressed handoff outcomes tied to the decision that produced them.
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
- Chart Workspace snapshots through `/api/chart-workspace/{symbol}`, including toggleable ORB overlays, per-session ORB overlay filters, EMA/SMA, RSI, MACD, indicator presets, strategy context panels, chart-ready OHLCV bars, UI-ready context for persistent Analysis/Execution/Research layouts, and persistent symbol, chart-type, indicator, and range preferences.

The Simulation Lab foundation is default-hidden and off unless `EDGE_SIMULATION_LAB_ENABLED` is explicitly enabled. Its status contract is available at `/api/simulation-lab/status` so the UI and future lab workflows can discover whether experimental surfaces should be visible without accidentally exposing unfinished controls. Each experiment entry includes endpoint path, method, and result schema version metadata for client-side discovery. The initial Lab roadmap covers:

Simulation Lab status in Settings mirrors the same gate and experiment catalog read-only, so operators can confirm the backend lab posture without enabling experimental actions.

- ORB backtesting through the gated `/api/simulation-lab/orb/backtest` replay endpoint, including per-breakout risk/reward scoring from the opposite ORB boundary, target/stop/open outcome scoring, average realized R, and summary fields for scored breakouts, average reward R, maximum risk per share, and maximum reward per share.
- Buying-power allocation experiments through `/api/simulation-lab/buying-power/allocation`, including requested demand, unfilled demand, and aggregate fill-ratio summaries.
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
|-- Launch-Sentinel-Edge-Local.ps1      # Windows source launcher
|-- Launch-Sentinel-Edge-Local.bat
|-- docker-compose.yml
`-- README.md
```

---

## Quick Start

### Option 1: Windows local source launcher

From the repository root:

```powershell
.\Launch-Sentinel-Edge-Local.ps1 -InstallDeps
```

Useful flags:

| Flag | Purpose |
|------|---------|
| `-BackendPort 8001` | Choose backend port. |
| `-FrontendPort 3000` | Choose frontend port. |
| `-NoBrowser` | Do not open a browser automatically. |
| `-InstallDeps` | Install backend/frontend dependencies before launch. |
| `-NoDemoMode` | Do not force demo mode. |

The launcher looks for Python 3.11, 3.12, or 3.13, creates/uses the backend virtualenv, starts Vite, starts the backend, waits for readiness, and logs to `Sentinel-Edge-Local.log` on the Desktop.

### Option 2: Manual backend

From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
$env:DEMO_MODE = "true"
$env:SENTINEL_EDGE_PORT = "8001"
.\.venv\Scripts\python.exe server.py
```

Or with uvicorn:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8001 --reload
```

### Option 3: Manual frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend dev server defaults to Vite behavior. The local launcher uses port `3000`.

### Option 4: Docker stack

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

## Configuration

### Core runtime

| Variable | Purpose | Default/notes |
|----------|---------|---------------|
| `DEMO_MODE` | Run without MongoDB and suppress expected-absent Pulse behavior. | `false`; launcher usually uses demo mode unless `-NoDemoMode`. |
| `MONGO_URL` | MongoDB connection string. | Used by Docker and backend runtime. |
| `DB_NAME` | MongoDB database name. | `sentinel_edge`. |
| `DB_HOST` | MongoDB host for local code paths. | `localhost`. |
| `DB_PORT` | MongoDB port. | `27017`. |
| `CORS_ORIGINS` | Comma-separated allowed origins. | `*` in local/default paths. |
| `GLOBAL_KILL_SWITCH` | Initial kill switch state. | `false`. |

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
| `PULSE_PROBE_IN_DEMO` | Probe Pulse even in demo mode. |
| `PULSE_HANDOFF_ENDPOINT` | Optional structured Pulse handoff endpoint. If unset, Edge can fall back to legacy decision endpoint behavior. |

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

### Observability and alerts

| Variable | Purpose |
|----------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint for traces. |
| `OTEL_SERVICE_NAME` | OpenTelemetry service name. |
| `ANALYST_START_METRICS_SERVER` | Start optional analyst metrics server. |
| `WEBHOOK_SECRET` | Optional Alertmanager webhook receiver secret. |
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
| POST | `/control/pause` | Pause scheduler. |
| POST | `/control/resume` | Resume scheduler. |

### Tickers, decisions, and config

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/tickers` | Active ticker list with enriched state. |
| POST | `/tickers/{symbol}` | Add ticker. |
| DELETE | `/tickers/{symbol}` | Remove ticker. |
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
| PUT | `/automation` | Patch global/default automation settings. |
| PUT | `/automation/tickers/{symbol}` | Enable or disable one ticker for handoff. |

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
| POST | `/pulse/emergency-exit/{symbol}` | Manual emergency-exit bridge to Pulse. |
| POST | `/pulse/trailing-stop/{symbol}` | Manual trailing-stop bridge to Pulse. |
| POST | `/test/pulse-command` | Test Pulse command path. |
| POST | `/test/send-command` | Test command send path. |
| GET | `/test/commands` | Inspect test commands. |

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
| GET | `/simulation-lab/status` | Return the default-hidden Simulation Lab gate and planned experiment catalog. |
| POST | `/simulation-lab/orb/backtest` | Replay explicit OHLC bars through a gated ORB backtest scan with optional `target_r_multiple` risk/reward and target/stop/open outcome scoring. |
| POST | `/simulation-lab/buying-power/allocation` | Compare gated buying-power allocation plans for candidate trades with requested, unfilled, and fill-ratio summaries. |
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

Focused commands:

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests
backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*static.py"

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
   - buying-power allocation experiments with demand-fill summaries
   - stop/trailing/DCA comparisons with normalized P&L percentage summaries
   - default-hidden until explicitly enabled

4. Chart workspace
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
