# Edge ↔ Pulse rolling-month minute sweep

**Experiment:** EXP-012  
**Requested range:** 2026-06-19 through 2026-07-17  
**Actual trading sessions:** 2026-06-22 through 2026-07-17 because the U.S. market was closed on June 19  
**Bar interval:** one minute  
**Status:** completed in paper/replay research; not approved as a live-default change

## Why this experiment was added

The purpose was to test the complete Edge-to-Pulse decision path on new intraday data while changing the two-sided buy/sell band and Pulse's flat-only auto-rebracket settings. The experiment also gave Edge a universe of 20 stocks outside Pulse's canonical `SPY`, `QQQ`, `AAPL`, and `NVDA` defaults, including five recent penny-stock breakouts, so the replay could verify whether Edge issued BUY handoffs that caused Pulse to create previously unknown tickers.

## Code and workflow changes

- Added `scripts/run_edge_pulse_minute_sweep.py`.
- Added `scripts/run_edge_pulse_minute_sweep_entry.py` so the standalone experiment installs enhanced Edge metrics and engine configuration in the same order as production.
- Added `.github/workflows/edge-pulse-minute-sweep.yml`.
- The workflow prefers Alpaca when repository credentials are present and otherwise downloads Yahoo one-minute bars in provider-safe chunks.
- The workflow preserves the raw minute bars, coverage table, Edge selections, Pulse communications, trades, full parameter grid, penny-breakout ranking, and machine-readable report in one artifact.

These changes make the test reproducible and separate research settings from live configuration.

## Data coverage

Alpaca credentials were not available to the workflow, so the completed run used Yahoo Finance.

- Candidate symbols requested: 35
- Candidate symbols with usable minute data: 35
- Final Edge universe: 20
- Total one-minute bars in the final universe: 296,196
- Regular-session one-minute bars: 127,858
- Failed data chunks: 0
- Synthetic price candles inserted: 0

The 20-symbol Edge universe was:

`AMD`, `MU`, `AMAT`, `KLAC`, `AVGO`, `TSLA`, `META`, `MSFT`, `GOOGL`, `AMZN`, `PLTR`, `SOFI`, `HOOD`, `COIN`, `RIVN`, `BIYA`, `SLND`, `CJMB`, `BNRG`, `BATL`.

## Penny-stock breakout selection

The runner downloaded a larger penny-stock candidate pool and selected five names from actual daily breakout magnitude and volume during the replay window:

- `BIYA`
- `SLND`
- `CJMB`
- `BNRG`
- `BATL`

Historical borrow-rate, utilization, and availability snapshots were not available from the minute-bar provider. Therefore, these five names received an explicitly labeled synthetic squeeze-pressure stress overlay derived from their actual historical breakout magnitude and volume. Historical price, volume, ORB confirmation, Edge ranking, expected-value gates, reward/risk gates, maximum-entry limits, entries, and exits remained based on real minute bars.

A synthetic pressure score alone still could not authorize a BUY. The real historical ORB or bullish structure and real historical volume confirmation were required.

## Edge activity

- Enhanced analyses: 22,851
- Complete score-all evaluation cycles: 1,330
- Top-ranked BUY selections before portfolio occupancy filtering: 260
- Pulse BUY attempts in the best portfolio simulation: 39
- Filled attempts: 37
- Missed fills: 2

Pulse began with only its four canonical defaults. In the best-performing 3% profile, Edge caused Pulse to create these 16 previously unknown tickers:

`TSLA`, `RIVN`, `SOFI`, `AMAT`, `COIN`, `KLAC`, `SLND`, `AMZN`, `BIYA`, `BATL`, `AVGO`, `HOOD`, `BNRG`, `PLTR`, `MSFT`, `MU`.

`AMD`, `META`, `GOOGL`, and `CJMB` produced Edge signals but were not reached as executable handoffs while the one-position-at-a-time portfolio was occupied. The tighter 0.25% and 0.50% profiles recycled capital faster and did create all 20 unknown Pulse tickers, but both profiles lost money after costs.

## Parameter search

### Symmetric buy/sell band

The same percentage was applied to the Pulse buy and sell range so the test tightened and loosened both sides together.

| Symmetric band | Best net return | Net P&L | Best trade count | Profit factor |
|---:|---:|---:|---:|---:|
| 0.25% | -0.7653% | -$76.53 | 181 | 0.7243 |
| 0.50% | -0.9455% | -$94.55 | 127 | 0.7651 |
| 0.75% | -0.2723% | -$27.23 | 104 | 0.9382 |
| 1.00% | +0.5119% | +$51.19 | 84 | 1.1234 |
| 1.50% | +1.3200% | +$132.00 | 61 | 1.3497 |
| 2.00% | +0.8522% | +$85.22 | 48 | 1.2151 |
| 3.00% | **+2.8090%** | **+$280.90** | 37 | **1.9307** |

The tight bands overtraded. Their higher win rates did not overcome transaction costs and stop losses. Performance became positive at 1%, peaked locally at 1.5%, weakened at 2%, and was strongest at the widest tested 3% band.

### Re-bracket grid

The coarse grid varied:

- Re-bracket threshold: 0.25%, 0.50%, 1.00%, and 2.00%
- Re-bracket spread: 0.50%, 0.80%, 1.20%, and 2.00%
- Re-bracket buffer: 0.05%, 0.10%, and 0.20%
- Symmetric band: 0.25% through 3.00%

A fine pass varied lookback at 5, 10, and 20 bars and cooldown at 0, 5, and 15 minutes. The workflow evaluated 444 total result rows.

The nominal top configuration was:

```json
{
  "band_pct": 3.0,
  "rebracket_threshold_pct": 0.25,
  "rebracket_spread_pct": 0.5,
  "rebracket_buffer_pct": 0.05,
  "rebracket_lookback": 10,
  "rebracket_cooldown_minutes": 5,
  "stop_multiplier": 1.5
}
```

However, this is **not evidence that the listed re-bracket values are optimal**. At the 3% band, 156 grid rows tied with the same return, drawdown, trade count, and fill count. Only one of 37 entries used Pulse's re-bracket path, and that trade reached the same 3% target. The reliable finding is the 3% symmetric band; the re-bracket sweet spot remains unresolved.

## Best completed profile

Assumptions:

- Starting capital: $10,000
- Maximum notional per trade: $1,000
- One portfolio position at a time
- Round-trip cost assumption: 10 basis points
- Entry attempts use Edge's execution-style and maximum-price policy
- Exit priority: Edge supervisory SELL, Pulse stop, Pulse target, session close

Results:

- Ending capital: $10,280.90
- Net profit: **$280.90**
- Net return: **2.8090%**
- Maximum drawdown: **0.9512%**
- Profit factor: **1.9307**
- Trades: 37
- Win rate: 64.8649%
- Average net trade: 0.7592%
- Median net trade: 1.6749%
- Fill rate: 94.8718%
- Missed fills: 2

Exit attribution:

- 18 target exits: +$522.00 net
- 5 stop exits: -$230.00 net
- 14 session-close exits: -$11.10 net

## Execution-style observations

### Breakout stop-limit

- Attempts: 38
- Fills: 36
- Fill rate: 94.7368%
- Net P&L: +$302.56
- Average net return: +0.8405%
- Average post-fill MFE: +3.7333%
- Average post-fill MAE: -1.7627%

### Passive limit

- Attempts: 1
- Fills: 1
- Net P&L: -$21.67
- Net return: -2.1669%

### Timed limit

No timed-limit entry reached the executable portfolio path in this window.

This sample supports breakout stop-limit behavior for this particular period, but it is insufficient to compare all three styles. Passive limit has one observation and timed limit has none.

## Short-squeeze observations

Three trades reached the fully confirmed `short_squeeze_breakout` path. All three were `BIYA` breakout stop-limit entries:

- Net result per trade: +2.90%
- Combined net P&L: +$87.00
- Two entered directly through the Edge handoff style.
- One entered through Pulse re-bracketing and then reached the target.

`SLND`, `CJMB`, `BNRG`, and `BATL` had synthetic pressure snapshots and real breakout evidence, but they did not all satisfy the fused squeeze trigger at an executable top-ranked cycle. This is the intended behavior: pressure does not become an automatic squeeze BUY.

## Decision

Do not promote the nominal re-bracket values or change live defaults from this one run.

The strongest candidate for the next paper experiment is a **3% symmetric buy/sell band** with existing Edge maximum-entry, EV, top-one, and stop ownership controls unchanged. The current production-like 3% baseline earned the same result as the nominal winning re-bracket row, so there is no demonstrated benefit from changing re-bracket settings yet.

## Next validation

- Repeat the band grid on at least two independent months.
- Run one trending month and one range/high-volatility month.
- Add historical bid/ask or NBBO data instead of the minute-range spread proxy.
- Ingest genuine historical short-interest snapshots before judging squeeze-pressure calibration.
- Force or separately sample enough continuation/reversal setups to compare passive and timed limit styles.
- Split the 3% target test into asymmetric buy and sell distances only after the symmetric result reproduces.
