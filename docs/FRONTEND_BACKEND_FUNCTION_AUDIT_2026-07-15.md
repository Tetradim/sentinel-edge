# Sentinel Edge Frontend ↔ Backend Function Audit

Date: 2026-07-15  
Branch audited: `codex/fill-authoritative-handoff`  
Purpose: verify that Edge's visible analytical and live-handoff controls are connected to registered backend functions and that exactly-once delivery/data freshness are observable.

## Status definitions

- **Connected** — a visible screen uses the registered backend route and consumes its current response.
- **Fixed in this branch** — a broken runtime contract was repaired during this audit.
- **Partial** — some state or actions are connected, but important behavior remains local-only or hidden.
- **Backend-only by design** — execution safety machinery should be automatic and only expose status.
- **Local-only** — a UI action changes browser/session state or creates an advisory note without calling the backend.
- **Not connected** — a backend function has no frontend client or visible path.

## Important baseline

`backend/tests/test_frontend_api_client_routes.py` verifies all 48 public methods in `frontend/src/lib/api.ts` against the current FastAPI OpenAPI routes. This proves URL/method registration, but it does not prove:

- a visible component actually calls the method;
- required runtime headers are sent;
- response fields are displayed correctly;
- a button performs a backend action rather than a local visual update;
- live command state remains visible after timeout or restart.

This audit checks those additional layers.

## High-impact findings fixed

1. **Mutating frontend calls did not satisfy the backend operator-action contract.**
   - Backend resume, live automation, event-bus writes and protected actions require `X-Edge-Operator-Secret`.
   - Live automation also requires `X-Edge-Live-Readiness-Signoff`.
   - Shared frontend client sent only `Content-Type`.
   - Fix: `operatorFetch.ts` attaches both headers to mutating `/api` calls, reads a build/local browser secret, and prompts/retries once when the backend requests the operator value.

2. **Persistent unresolved commands were invisible.**
   - `_pending_commands` survived restart and prevented duplicate/conflicting handoffs, but only the backend state file exposed them.
   - Fix: `GET /api/bus/automation-operations` returns pending IDs, last handoff, last suppression, Pulse delivery state and retry queue.

3. **Live execution-data freshness was invisible.**
   - The scheduler can suppress BUY/SELL/DCA with `live_execution_data_stale`, but the UI did not show which symbols were executable.
   - Fix: automation operations returns `PriceFetcher.execution_data_status` for every active ticker.

4. **No screen continuously displayed the repaired delivery state.**
   - Fix: a global collapsible `AutomationOperationsDrawer` is mounted beside the unified shell and is available from every view.

## Detailed function matrix

| Backend capability / route | Backend implementation | Frontend implementation | Status | Finding / action |
|---|---|---|---|---|
| Health | `GET /api/health` | unified shell, `AdvisorHealth` | Connected | Used for running/paused/Pulse/provider state. |
| Process liveness | `GET /api/live` | `AdvisorHealth`, unified shell snapshot | Connected | Displays process uptime. |
| Runtime readiness | `GET /api/ready` | `AdvisorHealth`, settings/readiness panels | Connected | 503 readiness responses are normalized rather than discarded. |
| Provider health | `GET /api/providers/health` | Advisor Health and System Health | Connected | Provider health/error counts are visible. |
| Market-data provider catalog/fallback order | `GET /api/market-data/providers` | Settings and Advisor Health | Connected | Active provider order and configuration state are shown. |
| Pulse connection status | `GET /api/pulse/status` | unified shell, Advisor Health | Connected | Circuit and availability are visible. |
| Pulse account | `GET /api/pulse/account` | Pulse context, portfolio/overview | Connected | Read-only account context. |
| Pulse positions | `GET /api/pulse/positions` | Pulse context, risk/overview derivation | Connected | Current position context is displayed. Stale version rejection remains pending cross-bot work. |
| Pulse retry queue | `GET /api/pulse/queue` | unified shell Pulse context | Connected | Queue status visible. New operations drawer also includes queue statistics. |
| Pulse handoff schema | `GET /api/pulse/handoff/schema` | Settings dashboard | Connected | Contract/version metadata displayed. |
| Ticker list | `GET /api/tickers` | shell selector, Settings ticker switches | Connected | Active symbols load from backend, then default fallback symbols are appended. |
| Add ticker | `POST /api/tickers/{symbol}` | shell symbol input | Connected | Uses real API action. Operator headers now attached globally. |
| Remove ticker | `DELETE /api/tickers/{symbol}` | shell remove control | Connected | Uses real API action. |
| Ticker config read/update | ticker config routes | API client, scanner/settings modules | Partial | Methods exist and routes register; not every config field is surfaced in the unified shell. |
| ORB levels | `GET /api/orb/{symbol}` | breakout/risk derivation | Connected | Used in shell state. |
| Chart workspace | `GET /api/chart-workspace/{symbol}` | charts and S/R evaluation | Connected | Real chart bars are requested. The shell still contains hard-coded fallback prices if no real price exists. |
| Market-map proof markers | proof-marker route | API client / market-map modules | Connected at client; limited visible use | Method is route-verified. Main shell more heavily uses market-map context. |
| Market-map context | context route | unified shell heat/risk/levels | Connected | Used in derived state. |
| Scanner workbench catalog | scanner route | `ScannerWorkbench` module | Connected | Visible operations module. |
| Watch-intent validation | scanner validation route | Scanner Workbench | Connected | Validates user workbench intent. |
| Markets/session coverage | `GET /api/markets` | Market Coverage and shell | Connected | Market/session context visible. |
| Backtest | `POST /api/backtest` | simulation/testing dashboards | Connected but secondary | Not part of live handoff execution. |
| Strategy optimization | `POST /api/backtest/optimize` | backtest UI | Connected but secondary | Route/client contract verified. |
| Dry-run status | `GET /api/dry-run/status` | settings/diagnostic modules | Connected at client | Not a main live operations surface. |
| Simulation lab | simulation routes | Settings/simulation modules | Connected but secondary | User priority is live functionality. |
| Notifications status | notification status route | Settings dashboard | Connected | Visibility only. |
| Config validation | `POST /api/config/validate` | Settings Save | Connected as validation | General settings are saved in browser localStorage, then validated by backend. They are not generally persisted as runtime backend config. |
| Support/resistance evaluation | `POST /api/support-resistance/evaluate` | unified shell refresh | Connected | Derived from fetched chart bars. |
| Pause scheduler | `POST /api/control/pause` | Overview and Protection Ops | Connected | Mutation now receives operator header transport. |
| Resume scheduler | `POST /api/control/resume` | Overview and Protection Ops | Fixed in this branch | Previously failed without required operator secret; global operator transport now supplies it. |
| Kill switch read | `GET /api/emergency/kill-switch` | shell and Advisor Health | Connected | Visible status. |
| Kill switch mutation | `POST /api/emergency/kill-switch` | topbar/Protection Ops | Fixed transport | Operator headers now attached. Confirmation remains in UI. |
| Automation settings read | `GET /api/automation` | Settings, shell and Advisor Health | Connected | Mode/global/per-ticker thresholds visible. |
| Automation settings update | `PUT /api/automation` | Settings and shell mode controls | Fixed transport | Live mode can now meet operator secret/signoff contract. |
| Per-ticker automation | `PUT /api/automation/tickers/{symbol}` | Settings and Protection Ops | Fixed transport | Backend receives operator headers. |
| Correlation | `GET /api/correlation` | shell/risk modules | Connected | Used in snapshot/derived state. |
| Decisions | `GET /api/decisions` | decision feed, Advisor Health count | Connected | Real decision list/count visible. |
| Enable Pulse trailing stop | Pulse bridge route | Protection Ops | Fixed transport | Sends real backend request rather than local advisory only. |
| Pulse emergency exit | Pulse bridge route | Protection Ops | Fixed transport | Sends real backend request after confirmation. Pulse still owns broker execution. |
| Cross-bot event read | `GET /api/bus/events` | No dedicated event history screen | Not connected | Backend event history exists but the UI uses derived audit rows instead. |
| Cross-bot event write | `POST /api/bus/events` | No general UI writer | Backend-only / intentional | Direct generic event publishing is not a normal operator workflow. |
| Manual Edge action event | `POST /api/bus/edge-actions` | No dedicated direct writer | Partial | Protection controls use specific backend routes; many shell “Advisory Commands” remain local session audit events. |
| Automation operations | `GET /api/bus/automation-operations` | global `AutomationOperationsDrawer` | Fixed in this branch | Shows pending IDs, delivery status, retry queue and executable data. |
| Pending exactly-once commands | `pending_command_patch.py` | operations drawer | Fixed in this branch | ID/action/reason/time are visible without allowing ID replacement. |
| Ambiguous handoff persistence | handoff delivery + pending patch | operations drawer | Fixed as status | Remains pending until resolved; UI does not create a new command ID. |
| Fresh websocket execution data | `PriceFetcher.execution_data_status` | operations drawer per-symbol list | Fixed in this branch | Source, age, price and executable/blocked status shown. |
| One-action-per-evaluation arbitration | `live_scheduler_patch.py` | no direct control | Backend-only by design | UI should display suppression, not select a competing action after the fact. |
| Last accepted handoff | automation controller | Settings/Advisor data plus operations drawer raw detail | Connected | Last handoff visible. |
| Last suppressed handoff | automation controller | Settings/Advisor data plus operations drawer raw detail | Connected | Suppression visible. |
| Frontend RUM | RUM routes | frontend telemetry helper | Connected | User-experience telemetry. |
| Rate-limit status | rate-limit route | shell/Advisor details | Connected | Read-only. |

## Visible controls that are local-only

The unified shell contains several controls that record local operator audit text but do not call a backend route:

- Arm Trigger;
- Risk Sweep;
- Convert Alert;
- Mute Watch;
- Diagnostics;
- Ack Alerts;
- Lock Buys;
- Advise Stops;
- Reduce Size;
- Inject Break;
- Allow Guarded Breakout;
- Block Buy Below Support;
- Reduce Size On Heat Spike;
- Resimulate Greeks;
- Export Levels.

The handler explicitly records these in `operatorAuditRows`. They are advisory/session functions, not broker or Pulse commands. Labels and confirmation text must continue making that distinction clear.

## Backend functions intentionally status-only

- deterministic command ID generation;
- durable pending command storage;
- ambiguous-delivery retention;
- same-ID retry;
- conflicting-action suppression;
- one-action arbitration;
- websocket quote freshness evaluation;
- live price-sensitive action suppression;
- Pulse circuit breaker/retry queue;
- position authority from Pulse feedback.

The frontend may inspect these states but should not rewrite them.

## Remaining UI gaps and misleading fallbacks

1. **Hard-coded price fallback in the unified shell** — `priceForSymbol` can provide fixed prices when no backend/chart/market-map price exists. This can make an unavailable data source look populated. Live labels should explicitly mark fallback data or remove the fixed values.
2. **Default symbols are always appended** — the selector adds SPY, QQQ, TSLA, NVDA, BTC-USD and ESU6 even when the backend does not monitor them. These should be visually marked as examples or removed from live mode.
3. **Bot Network catalog is partly static** — bot rows and local Windows paths are hard-coded. Health/latency/directive values are derived/fallback values, not confirmed connections to every listed repository.
4. **General Settings persistence** — most Settings Dashboard fields are stored in browser localStorage and only validated by the backend. Only automation/per-ticker settings are actually persisted into Edge runtime state.
5. **Cross-bot event history** — `/api/bus/events` has no dedicated screen.
6. **Pending command resolution action** — operations drawer is read-only. There is no explicit “query Pulse by command ID” or “mark definitive rejection” operator workflow.
7. **Versioned Pulse position snapshots** — Edge still needs monotonic snapshot consumption so stale Mongo/command events cannot overwrite newer position state.
8. **Expected-value telemetry** — no frontend display exists for spread/slippage/fees-adjusted expected edge because the backend model is not yet implemented.
9. **Operator secret management** — browser transport can prompt/store the configured secret, but Settings has no dedicated status/clear panel. `clearOperatorSecret` exists for a future control.
10. **Generic API-client reachability** — all 48 methods map to routes, but some are only used by lazy modules or diagnostic screens rather than the primary shell.

## Files changed by this audit

- `backend/bot_event_bus_routes.py`
- `frontend/src/lib/operatorFetch.ts`
- `frontend/src/main.tsx`
- `frontend/src/components/dashboards/AutomationOperationsDrawer.tsx`
- `frontend/src/App.tsx`
- `backend/tests/test_frontend_live_operations_wiring.py`
- `.github/workflows/live-readiness.yml`

## Verification boundary

Static and OpenAPI tests verify route/client presence and the operator-header/live-operations source contract. A browser integration run must still exercise resume, kill switch, live automation mode, pending-command display, stale-data suppression and same-ID recovery against a running backend and Pulse instance.
