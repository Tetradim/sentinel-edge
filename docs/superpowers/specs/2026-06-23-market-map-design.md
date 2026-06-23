# Sentinel Edge Market Map Design

## Purpose

Market Map is Sentinel Edge's visual trading cockpit. It turns existing chart, scanner, ORB, Simulation Lab, cross-bot event bus, and market coverage capabilities into one operator surface for planning, live alert context, and replay proof.

The feature belongs in Sentinel Edge. Consolidation should keep focusing on Discord alert ingestion, broker execution, and reconciliation. Sentinel Edge should provide market context and scoring that Consolidation can request before trading.

## Product Thesis

Market Map should answer four questions quickly:

1. Where is the market right now relative to important levels?
2. Did this Discord alert happen in a favorable or dangerous location?
3. What does Sentinel Edge think about the setup?
4. Can the operator prove what the bot saw, parsed, decided, placed, and reconciled?

The design should feel strict, useful, and explainable. It should not become a decorative dashboard or a manual trading toy that bypasses safety gates.

## Scope

Market Map evolves the existing `ChartWorkspace` rather than creating a separate charting subsystem.

Included:

- Candlestick and line chart modes.
- Indicator controls for EMA, SMA, RSI, MACD, VWAP, volume, and future extensible overlays.
- Morning support and resistance levels.
- Intraday alert markers and trade markers.
- Sentinel Edge confidence and market-state panel.
- Options contract context panel.
- Replay/proof panel linked to cross-bot alert chains.
- Watchlist heat map and ticker selector.
- Layout presets for Morning Plan, Intraday Alerts, and Replay Proof.
- Local persisted UI preferences, continuing the current Chart Workspace pattern.

Excluded for the first implementation:

- Real broker order entry from Market Map.
- Drawing tools that mutate trade decisions without audit.
- A full TradingView clone.
- Unbounded custom indicator scripting.
- Live-money readiness claims.

## Existing System Fit

Relevant existing Sentinel Edge pieces:

- `frontend/src/components/dashboards/ChartWorkspace.tsx`: current chart cockpit with Plotly, candlestick/line modes, indicators, ORB overlays, layout preferences, and Simulation Lab actions.
- `backend/chart_workspace.py`: chart snapshot assembly, OHLCV normalization, indicator calculation, and ORB overlay payloads.
- `frontend/src/components/asset-command/data.ts`: Operations navigation where `Chart Workspace` currently appears.
- `frontend/src/components/dashboards/ScannerWorkbench.tsx`: watchlist/scanner source for future ticker collections.
- `frontend/src/components/dashboards/MarketCoverage.tsx` and `MarketBreadth.tsx`: market coverage and breadth context.
- `backend/shared/bot_event_bus.py` and route wrappers: cross-bot alert/decision/event transport.
- `docs/chrome-discord-bridge.md` and `docs/cross-bot-event-bus.md`: bridge and event-bus contracts.

The first implementation should rename or relabel Chart Workspace as Market Map in the Operations deck while preserving backwards-compatible component structure.

## Core Layout

Market Map uses a three-zone cockpit.

Left rail:

- Watchlist heat map.
- Ticker search and quick symbols.
- Active Discord source and bot-event feed summary.
- Scanner/strategy filters.

Center canvas:

- Main Plotly chart.
- Candlestick or line mode.
- Volume sub-panel.
- Indicator overlays.
- Support/resistance overlays.
- Alert and trade markers.
- Crosshair-friendly chart interactions.

Right rail:

- Selected ticker briefing.
- Morning levels table.
- Sentinel Edge confidence panel.
- Options contract quality panel.
- Replay/proof panel.
- Risk and exposure summary.

## Layout Presets

Morning Plan:

- Prioritizes support/resistance, premarket levels, trend, VWAP, and watchlist heat.
- Intended before the trading session starts.

Intraday Alerts:

- Prioritizes live alert markers, selected ticker chart, Edge confidence, and options contract context.
- Intended while Discord alerts are arriving.

Replay Proof:

- Prioritizes alert-chain timeline, chart markers, replay controls, and reconciliation evidence.
- Intended after or during test runs.

Presets should be stored in local storage first. Backend persistence is out of scope for the first implementation and should be added only when multiple operator machines need shared layouts.

## Morning Levels

Backend chart payload should add a `levels` section with a schema version.

Initial levels:

- Prior day high.
- Prior day low.
- Session high.
- Session low.
- Premarket high.
- Premarket low.
- Opening range high.
- Opening range low.
- VWAP.
- ATR upper/lower bands.

Each level should include:

- `id`
- `label`
- `kind`
- `price`
- `source`
- `session`
- `confidence`
- `timestamp`
- `locked`

These levels are context, not orders. They can inform decision scoring but must not directly place trades.

## Indicators

Existing indicators stay:

- EMA 9.
- EMA 20.
- SMA 20.
- RSI 14.
- MACD.

Add next:

- SMA 50.
- SMA 200.
- VWAP.
- ATR bands.

Indicator calculations should remain deterministic and tested in backend helpers. Unknown indicator IDs should continue to fail clearly.

## Alert And Trade Markers

Market Map should consume cross-bot events and alert-chain data.

Markers:

- Discord alert seen.
- Parsed buy/sell/trim/close.
- Decision accepted/skipped.
- Broker order placed.
- Fill/reconciliation.
- Stop/trailing exit event.

Each marker should link back to a proof row:

- event ID
- raw text
- parsed contract
- parser confidence
- source policy proof
- decision status
- trade/order/position IDs

Accepted alerts without proof should be visually distinct and treated as review items.

## Sentinel Edge Confidence Panel

The selected ticker panel should show:

- Directional bias.
- Trend state.
- Momentum state.
- Volatility state.
- Level proximity.
- Alert quality score.
- Risk note.
- Reasons for pass/block/review.

The panel must show reasons, not just a score. Scores without reasons are not explainable enough for live-readiness work.

## Options Cockpit

For alerts with option contracts, show:

- ticker
- strike
- side
- expiration
- entry price
- bid/ask spread
- estimated premium
- liquidity warning
- delta target
- selected contract status

If options market data is unavailable, show that explicitly and keep any trade recommendation in review state.

## Cross-Bot Integration

Target flow:

1. Chrome/Discord bridge or bot observes alert.
2. Consolidation parses alert and creates audit proof.
3. Consolidation asks Sentinel Edge for market-map context.
4. Sentinel Edge returns level proximity, market state, confidence, and warnings.
5. Consolidation uses that context in its deterministic decision gate.
6. Market Map displays the whole chain for review and replay.

Sentinel Edge should never silently assume a source is trusted. Source/channel/author proof remains owned by the alert-ingestion bot and should be displayed when available.

## The Ten Companion Ideas

1. Market Map tab: the primary chart/context cockpit.
2. Morning levels engine: premarket and prior-session support/resistance.
3. Alert-to-chart replay: plot alerts and decisions on candles.
4. Sentinel Edge overlay: trend, confidence, volatility, and level context.
5. Options strike cockpit: spread, liquidity, delta, expiration, and contract quality.
6. Discord source monitor: channel/author/source health shown as evidence.
7. Risk exposure heat map: ticker exposure, direction, P/L, and concentration.
8. Trade decision journal: see/parse/decide/place/reconcile timeline.
9. Playbook/backtest lab: test alert rules against levels and replay outcomes.
10. Operator briefing mode: morning plan with levels, bias, watched tickers, and blockers.

## Implementation Slices

Slice 1: Market Map shell

- Relabel `Chart Workspace` to `Market Map`.
- Add layout preset state: Morning Plan, Intraday Alerts, Replay Proof.
- Add a right-side Market Map briefing panel.
- Keep existing chart behavior intact.

Slice 2: Support/resistance payload

- Extend `backend/chart_workspace.py` with deterministic level payloads.
- Add VWAP and ATR band calculations.
- Add backend tests for level schema and calculations.

Slice 3: Market Map overlays

- Render levels as chart overlays.
- Add level table and proximity summary.
- Add frontend tests/static checks for Market Map controls and labels.

Slice 4: Alert and proof markers

- Add event-bus/alert-chain marker ingestion.
- Display alert markers on chart.
- Link markers to proof details.

Slice 5: Edge scoring API

- Add endpoint for Consolidation to request market-map context for a parsed alert.
- Return deterministic pass/review/block reasons.
- Keep response read-only and audit-friendly.

Slice 6: Options cockpit

- Add contract-context panel.
- Show unavailable market data explicitly.
- Surface spread/liquidity warnings.

## Test Strategy

Backend:

- Unit tests for level calculation.
- Unit tests for indicator validation and VWAP/ATR output.
- API/static tests for schema version and endpoint shape.

Frontend:

- Static tests that Operations navigation exposes Market Map.
- Component/static tests that Market Map renders layout presets, level controls, and proof panels.
- Existing UI build/lint checks.

Integration:

- Replay fixture where a Discord alert marker appears on a candle and links to an alert-chain proof row.
- Edge context response fixture consumed by Consolidation in simulation mode only.

## Safety Rules

- Market Map never arms live trading.
- Market Map never submits broker orders.
- Market Map scoring is advisory unless a downstream bot explicitly gates on it with audited settings.
- Missing chart, options, or event-bus data must produce review/block states, not silent defaults.
- No live-money readiness claim should depend on Market Map until readiness endpoints prove source, broker, arming, replay, reconciliation, and operator checks.

## Open Implementation Notes

- Keep `ChartWorkspace` exports temporarily to avoid breaking imports while renaming the user-facing label.
- Use existing Plotly infrastructure before considering a new charting library.
- Prefer deterministic server-side calculations for levels and indicators over ad hoc frontend-only math.
- If a future TradingView-style drawing layer is needed, treat drawings as annotations with audit metadata, not trading instructions.
