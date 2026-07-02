# Sentinel Edge + Sentinel Echo S/R Watch Design

## Purpose

S/R Watch is a split-control position-management feature for Sentinel Edge and Sentinel Echo. It lets Edge watch support and resistance structure for option positions held by trading bots, then send audited directives when structure confirms that an option should be closed, protected, or scaled.

The feature is not a broker-order path in Edge. Edge owns market-structure observation and directive generation. Sentinel Echo owns option positions, broker execution, risk controls, stop/trailing behavior, order retries, and reconciliation.

## Product Goals

1. Let operators switch a watched bot from ORB Watch to S/R Watch.
2. Let Edge maintain a ranked intraday support/resistance map seeded from opening-market levels and updated as new highs/lows and swing pivots appear.
3. Let Edge watch confirmed option positions from Sentinel Echo and other options bots.
4. Tell Sentinel Echo to immediately close adverse positions:
   - Long calls close when the underlying confirms a support break.
   - Long puts close when the underlying confirms a resistance break.
5. Tell Sentinel Echo to scale favorable positions:
   - Long calls can add when the underlying confirms a resistance break.
   - Long puts can add when the underlying confirms a support break.
6. Preserve standalone operation:
   - Edge can run as a market-structure watcher without Sentinel Echo.
   - Sentinel Echo can keep trading from Discord alerts without Edge.

## Existing System Fit

Sentinel Edge already has related pieces:

- `backend/chart_workspace.py` builds Market Map levels for session high/low, prior-day high/low, premarket high/low, opening range high/low, VWAP, and ATR bands.
- `backend/orb.py` tracks ORB sessions and breakout state.
- `backend/signals.py` uses ORB high/low in signal scoring.
- `backend/shared/bot_event_bus.py` provides append-only bot events and already names `sentinel-echo` as an Edge action target.
- `backend/server.py` exposes `GET /api/market-map/context/{symbol}` and `GET /api/market-map/proof-markers/{symbol}`.

Sentinel Echo already has related pieces:

- Discord ingestion and source policy controls.
- Per-source allowed actions and ticker allow/block lists.
- Simulation, paper-shadow, manual-confirm, sizing, stop-loss, trailing-stop, and readiness controls.
- Order status, fill reconciliation, and position lifecycle modules.
- A stale Edge client path that should be updated to the Market Map/SR contract rather than reused as-is.

## UI Ownership

Use a split UI.

Edge UI owns observation and directive settings:

- Watched bots.
- Watched symbols.
- ORB Watch vs S/R Watch mode per bot/source/symbol.
- S/R level ranking rules.
- Break confirmation modes.
- Directive cooldown and debounce.
- Advisory-only vs executable-intent directive mode.
- Directive and verdict audit log.

Sentinel Echo UI owns execution response settings:

- Whether to auto-act on Edge directives.
- Immediate sell behavior.
- Scale-in sizing and caps.
- Strict 0DTE exits.
- Stop trading after a configured market time.
- Break-even stop based on option entry premium.
- Pre-close trailing-stop response.
- Broker retry, cancel, replace, and reconciliation behavior.

Edge may display Sentinel Echo response policy as read-only when Sentinel Echo publishes it. Edge must not directly mutate Sentinel Echo broker or risk settings.

## Settings Precedence

Settings resolve from most specific to least specific:

1. Symbol override.
2. Channel/source override.
3. Bot override.
4. Global default.

This precedence applies on both sides. Edge applies it to observation/directive rules. Sentinel Echo applies it to execution/risk responses.

## Edge S/R Watch Settings

Each watched bot/source/symbol can configure:

- `watch_mode`: `orb` or `support_resistance`.
- `enabled`: boolean.
- `confirmation_modes`: one or more of:
  - `tick_break`
  - `candle_close_break`
  - `buffer_volume_break`
- `candle_timeframe`: default `1m`.
- `confirming_closes`: default `1`, configurable for stricter behavior.
- `percent_buffer`: configurable.
- `atr_buffer`: configurable.
- `volume_ratio_threshold`: configurable.
- `volume_zscore_threshold`: configurable.
- `min_touches`: minimum touches for a level to be considered strong.
- `cooldown_seconds`: directive cooldown per position/level/action.
- `max_directives_per_position_per_level`: default `1`.
- `advisory_only`: when true, emit context but not executable-intent directives.

Turning S/R Watch on for a scope replaces ORB Watch for that scope's bot directives. It does not remove Edge's existing ORB calculations, displays, tests, metrics, or independent Edge/Pulse workflows.

## Sentinel Echo Response Settings

Each bot/source/symbol can configure:

- `auto_act_on_sr_directives`: default true for enabled S/R Watch scopes.
- `exit_order_style`: default aggressive marketable limit.
- `exit_retry_policy`: configurable attempts and timeout.
- `scale_in_enabled`: default true when S/R Watch is enabled.
- `scale_in_size_mode`: default `buying_power_percent`.
- `scale_in_buying_power_percent`: default `25`.
- `scale_in_current_position_percent`: optional alternative.
- `scale_in_original_entry_percent`: optional alternative.
- `scale_in_fixed_contracts`: optional alternative.
- `scale_in_fixed_premium_cap`: optional alternative.
- `max_adds_per_position`: required cap.
- `max_total_contracts`: required cap.
- `strict_0dte_exits_enabled`: default true.
- `stop_trading_after_time_enabled`: default false.
- `stop_trading_after_time_et`: configurable.
- `move_stops_to_breakeven_enabled`: default false.
- `pre_close_trailing_rescue_enabled`: default false.

When `stop_trading_after_time_enabled` is true, Sentinel Echo blocks new entries and scale-ins after the cutoff, but still allows protective sells, adverse S/R sells, stop-loss sells, trailing-stop sells, and force-flat actions.

## Position Truth

Edge must not infer real positions from Discord text. Sentinel Echo owns position truth.

Sentinel Echo should publish position and fill updates to the bot event bus or expose a read endpoint that Edge can poll. Position identity must be contract-level:

```json
{
  "position_id": "sentinel-echo-pos-123",
  "bot_id": "sentinel-echo",
  "underlying": "AAPL",
  "option_type": "CALL",
  "strike": 210,
  "expiration": "2026-06-26",
  "quantity_open": 4,
  "entry_price": 1.25,
  "current_premium": 1.08,
  "broker": "alpaca",
  "source_channel": "discord-alerts",
  "status": "open"
}
```

Rules apply per position. If a bot holds multiple option contracts on the same underlying, Edge evaluates each position independently. Sentinel Echo still enforces aggregate exposure limits.

## S/R Level Engine

The S/R engine maintains a ranked multi-level stack per symbol.

Inputs:

- Opening range high/low.
- Premarket high/low.
- Prior-day high/low.
- Session high/low.
- VWAP and ATR bands as contextual levels.
- Swing highs and swing lows from intraday candles.
- New intraday highs/lows.
- Touch count, reaction strength, recency, and distance from current price.

Behavior:

- Seed the first levels from opening-market and premarket levels.
- Promote new swing highs/lows into candidate levels.
- Cluster nearby candidate levels using configurable tolerance.
- Rank levels by touches, recency, reaction strength, and source confidence.
- Expose nearest actionable support and resistance plus the ranked stack.
- Flip prior resistance into support only after a confirmed breakout and hold.
- Flip prior support into resistance only after a confirmed breakdown and hold.

The engine should be deterministic and replayable from OHLCV fixtures.

## Break Confirmation

S/R Watch supports three confirmation styles.

`tick_break`:

- Fires as soon as the underlying crosses the actionable level.
- Highest speed, highest whipsaw risk.

`candle_close_break`:

- Requires one or more candle closes beyond the level.
- Default timeframe is `1m`.
- Default confirming closes is `1`.

`buffer_volume_break`:

- Requires price to clear the level by a percent buffer or ATR buffer.
- Optionally requires volume ratio or volume z-score.
- Best default for scale-ins.

Operators can enable multiple modes. Edge records which mode confirmed the directive.

## Directive Rules

Adverse exits:

- Long call + confirmed support break: emit `close_position`.
- Long put + confirmed resistance break: emit `close_position`.
- Default close size is full position.
- Sentinel Echo executes immediately using aggressive marketable limit behavior.

Favorable scale-ins:

- Long call + confirmed resistance break: emit `scale_in`.
- Long put + confirmed support break: emit `scale_in`.
- Default size is 25% of available buying power.
- Sentinel Echo applies buying power, max contracts, max premium, source policy, readiness, broker capability, duplicate, and exposure gates before placing an order.

Pre-close protection:

- Break-even reference is the option contract entry premium.
- If premium is at or above entry near cutoff and configured, Sentinel Echo may move stops to break-even.
- If premium is below entry and the underlying breaks favorably near close, Edge may emit a directive for Sentinel Echo to enable its own trailing stop instead of forcing immediate exit.
- Adverse S/R breaks still take priority over trailing rescue.

0DTE behavior:

- `strict_0dte_exits_enabled` defaults true.
- Same-day expiration positions use stricter exits when enabled.
- Strict mode may require faster adverse exits, fewer scale-ins, or tighter cutoff rules as configured in Sentinel Echo.

## Directive Contract

Edge emits directives as bot events and may also return them from synchronous evaluation routes.

Example:

```json
{
  "contract_version": "edge.sr.directive.v1",
  "directive_id": "sr:AAPL:sentinel-echo-pos-123:close_position:support:20260624T143000Z",
  "target_bot": "sentinel-echo",
  "position_id": "sentinel-echo-pos-123",
  "underlying": "AAPL",
  "option_type": "CALL",
  "action": "close_position",
  "urgency": "immediate",
  "watch_mode": "support_resistance",
  "level": {
    "level_id": "AAPL:support:209.40",
    "kind": "support",
    "price": 209.4,
    "rank": 1,
    "touches": 4,
    "strength": "strong"
  },
  "confirmation": {
    "mode": "candle_close_break",
    "timeframe": "1m",
    "confirming_closes": 1,
    "observed_price": 208.92
  },
  "reason_codes": ["call_against_support_break", "confirmed_1m_close"],
  "created_at": "2026-06-24T14:30:00Z"
}
```

Sentinel Echo must treat directives as instructions requiring local validation, not as broker orders.

## Synchronous Evaluation Contract

Sentinel Echo can ask Edge before acting on a new alert:

```text
POST /api/sr/evaluate
```

Request:

```json
{
  "bot_id": "sentinel-echo",
  "source_channel": "discord-alerts",
  "underlying": "AAPL",
  "intent": "open_call",
  "price": 209.75,
  "position": null
}
```

Response:

```json
{
  "contract_version": "edge.sr.evaluation.v1",
  "status": "pass",
  "reason_codes": ["near_support_reclaim", "volume_confirmed"],
  "nearest_support": {"price": 209.4, "strength": "strong"},
  "nearest_resistance": {"price": 212.1, "strength": "medium"},
  "directive": null,
  "evaluated_at": "2026-06-24T14:30:00Z"
}
```

Statuses are `pass`, `review`, or `block`.

## Event Flow

Position update:

1. Sentinel Echo receives Discord alert and executes or updates a position through its own gates.
2. Sentinel Echo publishes `sentinel-echo.position.updated` with contract-level identity.
3. Edge stores or refreshes the watched position state.

Directive:

1. Edge updates S/R levels from current market data.
2. Edge evaluates watched positions against actionable levels.
3. Edge emits `edge.sr.directive.v1` to the bot event bus.
4. Sentinel Echo consumes the directive.
5. Sentinel Echo validates position, settings, broker, duplicate, sizing, readiness, and reconciliation requirements.
6. Sentinel Echo places or rejects the action and publishes `sentinel-echo.directive.feedback`.

Pre-entry gate:

1. Sentinel Echo parses a Discord alert.
2. Source policy allows the alert.
3. Sentinel Echo calls `POST /api/sr/evaluate`.
4. Sentinel Echo uses the Edge response as an additional deterministic gate.
5. Sentinel Echo records the Edge verdict in alert/trade proof.

## Failure Handling

If Edge is unavailable:

- Sentinel Echo standalone behavior remains configurable.
- For live automation, the recommended default is `review` or `block` for new entries and scale-ins.
- Protective exits remain allowed through Sentinel Echo's own stop/loss/trailing/risk controls.

If Sentinel Echo is unavailable:

- Edge can continue computing levels and recording theoretical directives.
- Edge must mark directives as not delivered.

If market data is stale or missing:

- Edge emits no new scale-in directive.
- Edge returns `review` or `block` for new-entry evaluation.
- Edge records stale-data reasons.

If a directive is repeated:

- Edge dedupes by position, level, action, and confirmation window.
- Sentinel Echo also dedupes by directive ID.

## Safety Rules

- Edge never places broker orders.
- Edge never directly mutates Sentinel Echo broker/risk settings.
- Sentinel Echo never treats an Edge directive as sufficient for execution.
- Adverse exits outrank scale-ins and trailing rescue.
- Scale-ins require explicit caps.
- Strict 0DTE exits default on.
- Time cutoffs block new entries and scale-ins, not protective exits.
- Missing position truth blocks Edge position-management directives.
- All directives and responses must be auditable and replayable.

## Implementation Slices

1. Edge S/R engine:
   - New support/resistance module.
   - Deterministic level stack and break confirmation.
   - Unit tests from OHLCV fixtures.
2. Edge watch config:
   - Global/bot/source/symbol observation settings.
   - CRUD endpoints and audit log.
3. Edge evaluation and directive contracts:
   - `POST /api/sr/evaluate`.
   - `edge.sr.directive.v1` event emission.
   - Directive dedupe/cooldown.
4. Sentinel Echo position truth publication:
   - Publish contract-level position updates.
   - Expose current positions for Edge recovery.
5. Sentinel Echo directive consumer:
   - Validate Edge directives.
   - Close adverse positions.
   - Scale favorable positions within caps.
   - Publish directive feedback.
6. Split UI:
   - Edge Watched Bots / S/R Watch screen.
   - Sentinel Echo Edge Directives / response-policy screen.
   - Read-only cross-bot policy/status views where useful.

## Test Strategy

Edge backend:

- S/R level seeding from opening range.
- Swing high/low promotion and clustering.
- Level ranking by touches, recency, reaction strength, and source confidence.
- Break confirmation for tick, candle close, and buffer/volume modes.
- Directive dedupe and cooldown.
- Synchronous evaluation contract.
- Event-bus directive contract.
- Missing/stale market data response.

Sentinel Echo backend:

- Position update publication.
- Directive consumption with valid/invalid position IDs.
- Immediate close for adverse call/put cases.
- Scale-in sizing using 25% buying power and all caps.
- Strict 0DTE exit behavior.
- Stop-after-time blocks entries/adds but permits exits.
- Break-even/trailing pre-close response using option entry premium.
- Broker failure, partial fill, cancel, retry, and reconciliation proof.

Integration:

- Physical or replayed Discord alert opens a simulated option position.
- Edge receives position truth.
- OHLCV replay confirms support or resistance break.
- Edge emits directive.
- Sentinel Echo executes or blocks with explicit reason.
- Audit chain links alert, position, Edge directive, order, fill, and feedback.

## Open Implementation Notes

- Reuse Market Map level payload shape where possible, but add stateful ranked S/R memory for live watch behavior.
- Do not reuse Sentinel Echo's stale `/api/v1/analyze` Edge client as-is; replace it with the S/R evaluation contract.
- Keep ORB Watch behavior backwards compatible.
- Prefer paper/simulation validation before any live directive auto-action.
- Update readiness documentation to clarify that S/R Watch is not live-money proof by itself.
