# Sentinel Edge live-functional repair log

Branch: `codex/fill-authoritative-handoff`
PR: #6
Review scope: live-money market analysis, decision arbitration and exactly-once handoff to Pulse. Security, paper trading and release gates are secondary to functional execution.

## Verified baseline before this repair cycle

- Edge Fill Authority: passing at `35ca83eaff9ae77cadea6ddc49cd2f2946529687`.
- macOS Smoke Checks: passing at the same commit.
- Observability Static Checks: passing at the same commit.

## Findings from post-fix review

### P0 — safe ambiguous-delivery transport is not installed

`backend/handoff_delivery_patch.py` contains the correct rule, but production `PulseClient.send_handoff_command` still falls back to the legacy execution endpoint after a failed structured request.

Planned fix:

1. Integrate the safe behavior directly into `PulseClient`.
2. Never use the legacy path after timeout, connection reset or 5xx in live mode.
3. Retry only the structured endpoint with the same command ID.
4. Remove live execution through the legacy decision endpoint.

### P0 — unresolved command persistence is not installed

`backend/pending_command_patch.py` defines an `install()` function but is not part of the production import path.

Planned fix:

- Integrate pending commands directly into `AutomationController`.
- Reuse the same idempotency key after ambiguous delivery and restart.
- Block conflicting actions until Pulse resolves the original command.

### P1 — live decisions can use stale market data

The default OHLCV cache is 30 seconds and stale data is returned after provider failure.

Planned fix:

- Require fresh real-time quotes in live mode.
- Add strict quote age, bid/ask/spread and liquidity requirements.
- Keep stale/yfinance data for historical indicators only.

### P1 — Edge receives incomplete position state

Pulse events do not yet provide a versioned broker-backed snapshot with reserved quantity, working orders, bid/ask, peak and drawdown state.

Planned fix:

- Consume a versioned `PositionSnapshot` from Pulse and reject stale/out-of-order versions.

### P1 — main strategy and plugins can independently send commands

The puzzle-key plugin can hand off after the main decision path in the same evaluation.

Planned fix:

- Make plugins return proposals only.
- Add one arbiter that emits at most one executable command per symbol/cycle.

### P1 — confidence is not calibrated to net expectancy

Confidence is derived from absolute signal strength and does not subtract spread, slippage or fees.

Planned fix:

- Add expected-value inputs and outcome attribution by strategy/version/regime.

## Repair order

1. Direct safe handoff transport.
2. Direct pending-command persistence.
3. Single decision arbiter.
4. Fresh executable quote contract.
5. Versioned Pulse position snapshots.
6. Expected-value calibration.
7. Full workflow run and source review.

## Status

In progress.
