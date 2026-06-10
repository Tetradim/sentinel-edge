# Sentinel Edge — Autonomous Market Analysis Brain

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-18+-blue?logo=react" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.115-blue?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/TypeScript-5-blue?logo=typescript" alt="TypeScript">
  <img src="https://img.shields.io/badge/Windows-Local%20Beta-green?logo=windows" alt="Windows Local Beta">
  <img src="https://img.shields.io/badge/Safety-Gated%20Automation-red" alt="Safety gated automation">
</p>

**Sentinel Edge** is the analysis and decision “brain” for the Tetradim trading suite. It monitors market data, calculates ORB/ATR/signal/risk state, produces recommendations, and—only when explicitly enabled—hands structured action instructions to **Sentinel Pulse**, the execution worker.

The current implementation is focused on **Windows-local beta testing** with safe standalone behavior. Edge can run without Pulse, without MongoDB in demo/standalone mode, and without paid market-data keys. When Pulse is present and automation is enabled, Edge can hand off buy/stop/trailing-stop style commands through a gated control layer.

> **Safety stance:** Edge is not a brokerage adapter. It does not place broker orders directly. Pulse owns execution. Live autonomous handoff is disabled unless the operator explicitly enables the global handoff switch and the relevant per-ticker switches.

---

## Current Implementation Status

### Recently implemented on `OC-Iteration`

| Area | Status | Notes |
|------|--------|-------|
| Local startup UX | Implemented | Running `backend/server.py` directly can open the local UI after `/api/health` becomes ready. Controlled by `SENTINEL_EDGE_OPEN_BROWSER`, `SENTINEL_EDGE_HOST`, `SENTINEL_EDGE_PORT`, and `SENTINEL_EDGE_UI_URL`. |
| Standalone/demo quiet mode | Implemented | `DEMO_MODE=true` skips MongoDB client creation and skips Pulse health probing unless explicitly enabled. Correlation Pulse overrides are suppressed in demo/standalone mode. |
| Safe market-data provider catalog | Implemented | Read-only provider metadata endpoint exposes capabilities and configured/not-configured booleans only, never secret values. |
| Provider fallback gating | Implemented | Runtime uses keyless/configured providers only. Keyed providers activate only when backend env vars are present. |
| Stooq EOD/backfill only | Implemented | Stooq is retained for daily/EOD CSV use only and is excluded from intraday scheduler fallback. |
| Frontend secret hygiene | Implemented | Settings no longer stores API keys; old localStorage secret-like fields are filtered out. Frontend uses native `fetch`, not Axios. |
| Advisor Health dashboard | Implemented | Replaced duplicate/static Service Health with a read-only operational dashboard for Edge, Pulse, providers, kill-switch status, and automation status. |
| Autonomous Pulse handoff foundation | Implemented | Global and per-ticker handoff gates, action mode, command schema, cooldown, idempotency key, status API, and UI controls. |
| Generated artifact cleanup | Implemented | `.gitignore` now excludes Python bytecode/generated artifacts and local automation state. |

Recent commits:

```text
ce227db Add autonomous Pulse handoff controls
c3d8aa6 Add read-only advisor health dashboard
a75d220 Gate market data providers by env configuration
d477ed9 Add safe market data provider fallback
20f0edd Open Sentinel Edge UI on local startup
```

---

## Product Model

The trading suite is split by responsibility:

| System | Role | Owns |
|--------|------|------|
| **Sentinel Edge** | Brain / market analyst | Market data ingestion, ORB/ATR/signal analysis, risk reasoning, recommendations, automation gating, Pulse handoff instructions. |
| **Sentinel Pulse** | Worker bee / executor | Broker adapters, order placement, execution state, position/account truth, dashboard execution controls. |
| **Darkpool-Mon** | Flow/intelligence source | Darkpool, whale prints, scanner, options-flow/volume-anomaly intelligence. |
| **Consolidation** | Options alert parser/executor | Discord options alert parsing, validation, and broker order execution. |

Edge and Pulse should be useful independently:

- Edge without Pulse: analyze, recommend, backtest/simulate, show health, stay quiet about missing Pulse.
- Pulse without Edge: execute via its own controls and broker adapters.
- Edge + Pulse: Edge can become the autonomous analysis layer that sends instructions to Pulse, but only through explicit operator-gated automation.

---

## Architecture Overview

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                              Sentinel Edge                                 │
│                                                                            │
│  React UI                                                                  │
│  ├─ Trading / Market / Settings dashboards                                 │
│  ├─ Advisor Health                                                         │
│  └─ Autonomous Pulse Handoff controls                                      │
│                         │                                                  │
│                         ▼                                                  │
│  FastAPI backend (`backend/server.py`)                                      │
│  ├─ Health / stats / provider APIs                                         │
│  ├─ Ticker configuration APIs                                              │
│  ├─ Automation APIs                                                        │
│  └─ Pulse integration APIs                                                 │
│                         │                                                  │
│                         ▼                                                  │
│  Evaluation Scheduler (`backend/scheduler.py`)                             │
│  ├─ Fetch price data                                                       │
│  ├─ Calculate ORB/ATR/signals/correlation                                  │
│  ├─ Query real/local position state                                        │
│  ├─ DecisionEngine decides BUY / STOP / TRAIL / EXIT                       │
│  └─ AutomationController gates any Pulse handoff                           │
│                         │                                                  │
│              ┌──────────┴──────────┐                                       │
│              ▼                     ▼                                       │
│  Market-data providers       PulseClient                                   │
│  ├─ yfinance/keyless          ├─ circuit breaker                           │
│  ├─ Finnhub env-gated         ├─ quiet standalone suppression              │
│  ├─ Polygon env-gated         ├─ retry queue for legacy decisions          │
│  ├─ Alpha Vantage env-gated   └─ structured handoff payloads               │
│  ├─ Twelve Data env-gated                                                   │
│  └─ Stooq EOD/backfill only                                                 │
│                                      │                                      │
│                                      ▼                                      │
│                           Sentinel Pulse                                    │
│                           Broker/order executor                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Autonomous Pulse Handoff Foundation

The automation layer is intentionally separate from signal generation. Edge may evaluate opportunities continuously, but Pulse commands are sent only when every gate passes.

### Backend module

`backend/automation.py` defines:

- `AutomationMode`
  - `recommend_only` — record recommendations/status only; no Pulse commands.
  - `paper` — allow handoff in paper/simulated mode semantics.
  - `live` — allow live handoff semantics after explicit enablement.
- `AutomationAction`
  - `buy`
  - `stop_buying`
  - `stop_all`
  - `regular_stop`
  - `trailing_stop`
  - `tighten_stop`
  - `tighten_trailing_stop`
  - `dca`
  - `emergency_exit`
- `AutomationSettings`
  - `global_enabled`
  - `mode`
  - `default_ticker_enabled`
  - `per_ticker_enabled`
  - `min_confidence`
  - `cooldown_seconds`
  - `quiet_when_pulse_absent`
- `HandoffCommand`
  - symbol/action/confidence/reason/mode
  - ORB session tag
  - stop/trailing/DCA recommendation fields
  - idempotency key
  - metadata payload
- `AutomationController`
  - loads/saves local settings
  - preserves per-ticker settings when global handoff is disabled
  - enforces global/ticker/mode/confidence/cooldown gates
  - exposes `last_handoff` and `last_suppressed` status

### Safety gates

A Pulse handoff is blocked if:

1. `global_enabled` is false.
2. mode is `recommend_only`.
3. the ticker is disabled.
4. confidence is below `min_confidence`.
5. the ticker/action is still inside cooldown.
6. Pulse is unavailable or its circuit breaker is open.

Global handoff is intentionally independent from per-ticker preferences. Turning global off does **not** erase ticker choices.

### Local persistence

Automation settings are persisted locally to:

```text
data/automation_settings.json
```

Override path:

```text
EDGE_AUTOMATION_STATE_FILE=C:\path\to\automation_settings.json
```

The state file is ignored by git because it is local runtime state.

### API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/automation` | Return global/per-ticker settings plus last handoff/suppression status. |
| PUT | `/api/automation` | Patch global automation settings without erasing ticker overrides. |
| PUT | `/api/automation/tickers/{symbol}` | Enable/disable autonomous handoff for one ticker. |

Example:

```bash
curl -X PUT http://localhost:8000/api/automation \
  -H "Content-Type: application/json" \
  -d '{
    "global_enabled": true,
    "mode": "live",
    "min_confidence": 0.75,
    "cooldown_seconds": 90
  }'

curl -X PUT http://localhost:8000/api/automation/tickers/SPY \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### Scheduler integration

`backend/scheduler.py` now routes decision actions through `_handoff_to_pulse()` before any Pulse command is attempted.

Currently gated actions include:

| Decision | Handoff action |
|----------|----------------|
| `Decision.BUY` | `buy` |
| `Decision.STOP_BUYING` | `stop_buying` |
| `Decision.ENABLE_TRAILING_STOP` | `trailing_stop` |
| `Decision.TIGHTEN_TRAILING_STOP` | `tighten_trailing_stop` |
| `Decision.TIGHTEN_STOP` | `tighten_stop` |
| `Decision.EMERGENCY_EXIT` | `emergency_exit` |

The command payload includes confidence, reason, ORB session, stop type/trailing percent when applicable, and metadata such as ATR, price, PnL, trend, drawdown, and signal strength.

### Pulse client behavior

`backend/pulse_client.py` includes `send_handoff_command(payload)`.

Behavior:

- If Pulse is unavailable or circuit-open, handoff is suppressed quietly.
- If `PULSE_HANDOFF_ENDPOINT` is configured, Edge sends the structured payload there.
- Otherwise Edge falls back to the existing legacy `/api/tickers/{symbol}/decision` endpoint while preserving metadata.
- No direct broker/exchange calls are made by Edge.

---

## Market-Data Provider Layer

Edge supports safe provider fallback without exposing secrets to the browser.

### Provider files

| File | Purpose |
|------|---------|
| `backend/providers/catalog.py` | Browser-safe provider metadata and configured/not-configured booleans. |
| `backend/providers/health.py` | Provider health state. |
| `backend/providers/polygon_provider.py` | Polygon integration with corrected date-range aggregate URL. |
| `backend/providers/finnhub_provider.py` | Finnhub integration. |
| `backend/providers/alpha_vantage_provider.py` | Alpha Vantage integration. |
| `backend/providers/twelve_data_provider.py` | Twelve Data integration. |
| `backend/providers/stooq_provider.py` | Stooq daily/EOD CSV provider for backfill only. |
| `backend/price_fetcher.py` | Runtime fallback ordering and active provider selection. |

### Provider rules

- Keyed providers activate only when backend env vars are present.
- API responses expose presence booleans, not key values and not frontend-editable key fields.
- Stooq is not used for intraday scheduler fallback.
- Frontend Settings displays read-only provider availability.
- Frontend does not store API keys in `localStorage`.

### Provider APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/market-data/providers` | Provider catalog, fallback order, configured status. |
| GET | `/api/providers` | Alias/provider list endpoint. |
| GET | `/api/providers/config` | Redacted provider config metadata. |
| GET | `/api/providers/health` | Provider health status. |
| GET | `/api/price/{symbol}` | Current market price. |
| GET | `/api/quote/{symbol}` | Current quote. |

### Relevant env vars

| Variable | Purpose |
|----------|---------|
| `MARKET_DATA_PROVIDER_ORDER` | Comma-separated intraday fallback order. |
| `FINNHUB_API_KEY` | Enables Finnhub. |
| `POLYGON_API_KEY` | Enables Polygon. |
| `ALPHA_VANTAGE_API_KEY` | Enables Alpha Vantage. |
| `TWELVE_DATA_API_KEY` | Enables Twelve Data. |

---

## Advisor Health Dashboard

`frontend/src/components/dashboards/AdvisorHealth.tsx` is the operational status view for Edge as an advisor/automation runtime.

It shows:

- Edge service state.
- Pulse link state and circuit state.
- Kill-switch status as a read-only indicator.
- Recent recommendation count.
- Pulse handoff mode/status.
- Latest automation handoff or suppression event.
- Active market-data fallback order.
- Provider health and last success/error counts.
- Runtime details such as scheduler state, retry queue, ORB levels, active tickers, and Pulse failures.

This replaced a duplicate/static Service Health tab and removed top-level execution-like tabs from primary navigation where they were confusing for Edge’s current role.

---

## Settings Dashboard

`frontend/src/components/dashboards/SettingsDashboard.tsx` now includes:

- Read-only Market Data Providers panel.
- No frontend API-key entry or secret persistence.
- Autonomous Pulse Handoff panel:
  - global enable/disable
  - mode selector (`recommend_only`, `paper`, `live`)
  - min confidence
  - cooldown seconds
  - default ticker behavior
  - per-ticker handoff switches

Settings still stores non-secret UI preferences in browser localStorage, but secret-like fields are filtered during migration/save.

---

## Standalone and Local Startup Behavior

Edge is designed to be useful when Pulse is absent.

### Demo/standalone mode

```bash
DEMO_MODE=true python backend/server.py
```

In demo mode:

- MongoDB client creation is skipped.
- Pulse health probing is skipped unless `PULSE_PROBE_IN_DEMO=true`.
- Correlation Pulse override calls are suppressed.
- Edge continues to run analysis where available.

### Browser startup

When run directly, `backend/server.py` can open the UI after the backend health endpoint is ready.

| Variable | Description |
|----------|-------------|
| `SENTINEL_EDGE_OPEN_BROWSER` | Set `false` to disable browser launch. |
| `SENTINEL_EDGE_HOST` | Backend bind host. |
| `SENTINEL_EDGE_PORT` | Backend port. |
| `SENTINEL_EDGE_UI_URL` | Override UI URL to open. |

---

## Pulse Integration

Pulse remains the executor. Edge sends instructions only through Pulse-facing APIs.

### Pulse APIs used by Edge

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/pulse/status` | Pulse availability/circuit status from Edge. |
| GET | `/api/pulse/positions` | Position view exposed through Edge. |
| GET | `/api/pulse/queue` | Retry queue status. |
| POST | `/api/pulse/emergency-exit/{symbol}` | Manual emergency exit bridge. |
| POST | `/api/pulse/trailing-stop/{symbol}` | Manual trailing-stop bridge. |
| POST | `/api/tickers/{symbol}/decision` | Legacy Edge → Pulse decision endpoint. |
| Optional | `PULSE_HANDOFF_ENDPOINT` | Structured autonomous handoff endpoint if Pulse implements it. |

### Circuit breaker behavior

`PulseClient` tracks:

- `CLOSED` — normal operation.
- `OPEN` — too many failures; requests are suppressed.
- `HALF_OPEN` — recovery probe state.

For autonomous handoff, Edge does not spam Pulse while absent/circuit-open. It suppresses quietly and exposes status through automation/health APIs.

---

## Repository Structure

```text
sentinel-edge/
├── backend/
│   ├── server.py                         # FastAPI app, lifespan wiring, REST endpoints
│   ├── automation.py                     # Global/per-ticker autonomous handoff controls
│   ├── scheduler.py                      # Evaluation loop, ORB/ATR/signal decisions, handoff gate
│   ├── engine.py                         # DecisionEngine/risk logic
│   ├── pulse_client.py                   # Pulse HTTP client, circuit breaker, quiet handoff
│   ├── price_fetcher.py                  # Market-data provider fallback selection
│   ├── orb.py                            # Opening Range Breakout tracking
│   ├── atr.py                            # Average True Range calculation
│   ├── providers/
│   │   ├── catalog.py                    # Browser-safe provider metadata
│   │   ├── health.py                     # Provider health state
│   │   ├── finnhub_provider.py
│   │   ├── polygon_provider.py
│   │   ├── alpha_vantage_provider.py
│   │   ├── twelve_data_provider.py
│   │   └── stooq_provider.py             # EOD/backfill only
│   ├── analyst/
│   │   ├── core.py                       # SentinelEdge orchestrator / change-stream path
│   │   └── correlation/engine.py         # Correlation logic and standalone suppression
│   ├── backtest/                         # Backtest/simulation engines
│   ├── options/                          # Greeks/IV modules
│   └── tests/
│       └── test_market_data_providers.py # Provider safety tests
├── frontend/
│   └── src/
│       ├── App.tsx                       # Dashboard navigation
│       ├── lib/api.ts                    # Native fetch API helpers
│       └── components/dashboards/
│           ├── AdvisorHealth.tsx         # Operational health/status dashboard
│           └── SettingsDashboard.tsx     # Provider + automation settings
├── docker-compose.yml
└── README.md
```

---

## API Summary

### Health and runtime

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Backend health and runtime state. |
| GET | `/api/stats` | Runtime statistics. |
| GET | `/api/emergency/kill-switch` | Read-only kill-switch status. |
| POST | `/api/emergency/kill-switch` | Toggle kill switch. |

### Tickers and decisions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tickers` | Active tickers with enriched live state. |
| POST | `/api/tickers/{symbol}` | Add ticker. |
| DELETE | `/api/tickers/{symbol}` | Remove ticker. |
| GET | `/api/tickers/{symbol}/config` | Get ticker metric/risk config. |
| PUT | `/api/tickers/{symbol}/config` | Update ticker metric/risk config. |
| GET | `/api/decisions` | Recent advisor decisions. |

### Automation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/automation` | Handoff settings/status. |
| PUT | `/api/automation` | Patch handoff settings. |
| PUT | `/api/automation/tickers/{symbol}` | Enable/disable ticker handoff. |

### Market data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/market-data/providers` | Browser-safe provider catalog and fallback order. |
| GET | `/api/providers` | Provider list alias. |
| GET | `/api/providers/config` | Redacted provider config metadata. |
| GET | `/api/providers/health` | Provider health. |
| GET | `/api/price/{symbol}` | Current price. |
| GET | `/api/quote/{symbol}` | Current quote. |
| GET | `/api/orb/{symbol}` | ORB levels. |

### Pulse bridge

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/pulse/status` | Pulse availability/circuit status. |
| GET | `/api/pulse/positions` | Position view. |
| GET | `/api/pulse/queue` | Retry queue. |
| GET | `/api/pulse/account` | Account view if Pulse available. |
| POST | `/api/pulse/emergency-exit/{symbol}` | Manual emergency exit bridge. |
| POST | `/api/pulse/trailing-stop/{symbol}` | Manual trailing-stop bridge. |

### Backtest/simulation and options

The repository also contains backtest, strategy optimization, portfolio/paper modules, and options Greeks endpoints. These are evolving toward a broader Simulation Lab and should remain default-hidden or clearly non-live unless explicitly enabled.

---

## Environment Variables

### Core runtime

| Variable | Description | Default |
|----------|-------------|---------|
| `DEMO_MODE` | Run without MongoDB and suppress expected-absent Pulse behavior. | `false` |
| `DB_NAME` | MongoDB database name. | `sentinel_edge` |
| `DB_HOST` | MongoDB host. | `localhost` |
| `DB_PORT` | MongoDB port. | `27017` |
| `PULSE_API_URL` | Sentinel Pulse API URL. | `http://localhost:8002` in local code path |
| `PULSE_API_KEY` | Optional Pulse API key header. | unset |
| `PULSE_PROBE_IN_DEMO` | Probe Pulse even in demo mode. | `false` |
| `GLOBAL_KILL_SWITCH` | Global kill switch state. | `false` |

### Local browser startup

| Variable | Description | Default |
|----------|-------------|---------|
| `SENTINEL_EDGE_OPEN_BROWSER` | Open UI after backend health is ready. | `true` for direct local startup |
| `SENTINEL_EDGE_HOST` | Backend host. | local default |
| `SENTINEL_EDGE_PORT` | Backend port. | local default |
| `SENTINEL_EDGE_UI_URL` | Explicit UI URL to open. | derived local URL |

### Automation

| Variable | Description | Default |
|----------|-------------|---------|
| `EDGE_PULSE_HANDOFF_ENABLED` | Initial global handoff switch. Saved local settings can override after first save. | `false` |
| `EDGE_AUTOMATION_MODE` | Initial mode: `recommend_only`, `paper`, or `live`. | `recommend_only` |
| `EDGE_PULSE_HANDOFF_DEFAULT_TICKERS` | Initial default per-ticker handoff state. | `false` |
| `EDGE_AUTOMATION_STATE_FILE` | Local automation settings path. | `data/automation_settings.json` |
| `PULSE_HANDOFF_ENDPOINT` | Optional structured Pulse handoff endpoint. | unset, fallback to legacy decision endpoint |

### Market data

| Variable | Description |
|----------|-------------|
| `MARKET_DATA_PROVIDER_ORDER` | Comma-separated intraday provider order. |
| `FINNHUB_API_KEY` | Enables Finnhub. |
| `POLYGON_API_KEY` | Enables Polygon. |
| `ALPHA_VANTAGE_API_KEY` | Enables Alpha Vantage. |
| `TWELVE_DATA_API_KEY` | Enables Twelve Data. |

---

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows PowerShell/CMD style may vary
pip install -r requirements.txt
python server.py
```

For standalone/demo analysis without MongoDB/Pulse noise:

```bash
set DEMO_MODE=true
python server.py
```

Or with uvicorn:

```bash
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up -d
```

---

## Verification Used During Recent Work

Run the full local verification gate from the repository root:

```powershell
.\scripts\verify-local.ps1
```

If the backend virtualenv is missing dev-test dependencies, install the declared stack through the same runner:

```powershell
.\scripts\verify-local.ps1 -InstallBackendDevDeps
```

For a fresh checkout that also needs frontend dependencies installed:

```powershell
.\scripts\verify-local.ps1 -InstallBackendDevDeps -InstallFrontendDeps
```

The recent implementation has been checked with:

```bash
python -m py_compile backend\automation.py backend\scheduler.py backend\pulse_client.py backend\server.py
```

Automation gate/persistence smoke:

```bash
python -c "from automation import AutomationController, HandoffCommand, AutomationAction, AutomationMode; c=AutomationController(); cmd=HandoffCommand(symbol='spy', action=AutomationAction.BUY, confidence=.9, reason='test', mode=AutomationMode.LIVE); assert c.plan(cmd)[0] is False; c.update_settings({'global_enabled': True, 'mode': 'live', 'per_ticker_enabled': {'SPY': True}, 'cooldown_seconds': 0}); assert c.plan(cmd)[0] is True; print('automation gate/persistence ok')"
```

Frontend build:

```bash
cd frontend
npm run lint
npm run build
npm audit --audit-level=moderate
```

Backend test discovery from the repository root:

```bash
backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests
python -m unittest discover -s backend/tests -p "test_*static.py"
```

If the backend virtualenv is missing test dependencies, install the declared dev stack first:

```bash
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

---

## Roadmap / Next Build Slices

### Highest priority

1. **ORB session model v1**
   - distinct `premarket_30m` and `market_open` ORB sessions
   - persist ORB session state and decision context
   - expose ORB session status in UI

2. **Pulse structured handoff contract**
   - finalize Pulse endpoint/schema for `PULSE_HANDOFF_ENDPOINT`
   - align idempotency, action types, stop/trail/DCA fields, paper/live semantics
   - add Pulse-side acceptance/rejection feedback

3. **Simulation Lab foundation**
   - ORB backtesting
   - buying-power allocation experiments
   - stop vs trailing-stop vs DCA comparisons
   - keep default-hidden/off unless explicitly enabled

4. **Chart Workspace v1**
   - TradingView-style or custom chart workspace
   - ORB overlays
   - indicator toggles such as EMA/SMA, RSI, MACD
   - Sentinel-themed/customizable/plugin-like layout

### Later

- Prometheus/Grafana-style observability panels inside Edge UI.
- Correlation and trailing-stop recommendation refinement.
- Confirmation/notification paths via Telegram/Discord/WhatsApp.
- Mac/Apple build workflow after Windows local beta is stable.

---

## Safety Notes

- Do not commit API keys or secrets.
- Do not store API keys in frontend localStorage.
- Do not scrape sources that disallow it.
- Do not make live broker calls from tests without explicit operator approval.
- Edge should not spam Pulse or logs when Pulse is absent.
- Paper/simulation features should stay clearly separated from live handoff.
- Volume anomaly/darkpool/options-flow intelligence belongs primarily in Darkpool-Mon, not Edge.

---

## License

MIT License - See LICENSE file for details.
