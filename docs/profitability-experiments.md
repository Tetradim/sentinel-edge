# Edge ↔ Pulse Profitability Experiment Log

This document is the implementation ledger for profitability changes. Each experiment must state the code change, why it could improve net returns, what can go wrong, and the evidence required before it becomes permanent.

## Operating rules

- Measure results after spread, slippage, commissions, and fees.
- Change one major behavior at a time whenever possible.
- Keep emergency exits and position supervision above experimentation.
- Run shadow or paper evaluation before increasing live risk.
- A missed trade is acceptable; uncontrolled correlated exposure is not.
- Promote a change only when it improves walk-forward net expectancy without unacceptable drawdown.

## EXP-001 — Score-all, top-one portfolio entry

**Status:** Implemented on `OC-Iteration`.

### Code changes

- Add a two-phase evaluation cycle in `edge_profitability_cycle.py`.
- During each scheduler sweep, score every unpositioned symbol before releasing any BUY.
- Defer per-symbol BUY decisions until the full candidate set is ranked.
- Authorize at most `EDGE_MAX_CYCLE_ENTRIES` entries; the experiment default is one.
- Persist the latest cycle, all candidate rankings, selection state, and rejection reasons through portfolio status.
- Force a complete scoring sweep even when WebSocket subscriptions would normally skip polling symbols. This is configurable with `EDGE_TOP_RANKED_FORCE_FULL_SWEEP`.

### Why it may improve profitability

The historical replay showed that Edge could buy several symbols near the beginning of a window before it knew which opportunity was best. Comparing the complete candidate set prevents evaluation order from becoming an accidental trading strategy. Capital is concentrated in the highest estimated net-expectancy opportunity rather than spread across several mediocre signals.

### Success measures

- Net expectancy per authorized trade.
- Difference between selected-candidate return and equal-weight eligible-candidate return.
- Number and P&L of prevented lower-ranked entries.
- Maximum drawdown and portfolio heat.
- Percentage of cycles with zero, one, or multiple eligible candidates.

### Risks and guardrails

- One erroneous signal can create concentration, so per-trade and portfolio risk budgets remain active.
- Candidate scores may not be calibrated yet, so selected and rejected opportunities are marked forward.
- Emergency exits and supervisory actions are never deferred by the portfolio cycle.

## EXP-002 — Minimum net expected value after costs

**Status:** Implemented as part of EXP-001.

### Code changes

- Require `expected_value_pct >= EDGE_MIN_NET_EXPECTED_VALUE_PCT`.
- Default experiment threshold: **0.15% after estimated round-trip costs**.
- Log `expected_value_below_net_threshold` separately from raw negative expectancy.

### Why it may improve profitability

A theoretically positive setup can still be too small to survive estimation error, spread changes, and execution slippage. A positive buffer avoids spending risk on trades whose projected advantage is effectively noise.

### Evaluation

Test thresholds of 0.00%, 0.10%, 0.15%, 0.25%, and 0.40% in walk-forward replay. Compare net expectancy, trade frequency, and missed-opportunity cost.

## EXP-003 — Two-to-one reward/risk floor

**Status:** Implemented in portfolio-cycle selection.

### Code changes

- Require `reward_risk >= EDGE_EXPERIMENT_MIN_REWARD_RISK`.
- Default experiment floor: **2.0R**.
- Keep the older general profitability threshold available for non-cycle and compatibility paths.

### Why it may improve profitability

The floor gives the strategy room to be wrong more often while remaining profitable and discourages late entries where the remaining upside is small relative to invalidation distance.

### Risk

Estimated targets and stops can be inaccurate. A nominal 2R setup is not useful when the target has low probability or the stop is likely to gap.

## EXP-004 — Hard correlated-substitute rejection

**Status:** Implemented for portfolio cycles.

### Code changes

- Define configurable substitute groups through `EDGE_CORRELATED_SUBSTITUTE_GROUPS_JSON`.
- Default groups include U.S. growth/equity beta and semiconductors.
- Treat SPY, QQQ, AAPL, NVDA, and related mega-cap growth symbols as overlapping exposure for this experiment.
- Reject a candidate when a correlated trade card is already armed or active.
- Label lower-ranked same-group candidates as `correlated_substitute_of:<winner>`.

### Why it may improve profitability

SPY, QQQ, AAPL, and NVDA longs can represent the same underlying risk-on technology thesis. Holding them simultaneously multiplies drawdown without providing four independent sources of alpha.

### Evaluation

Compare raw ticker count with correlation-adjusted position count, factor concentration, drawdown during technology selloffs, and returns from the selected representative versus the rejected substitutes.

## EXP-005 — Maximum acceptable entry price

**Status:** Implemented in Edge and Pulse on `OC-Iteration`.

### Edge changes

- Trade cards calculate `maximum_entry_price` from the entry risk distance.
- Edge rechecks the selected price immediately before releasing the winner.
- BUY execution intents carry `edge.entry_policy.v1`, including reference price, maximum price, expected value, baseline cost, cost allowance, minimum remaining edge, position ID, card ID, and trigger state.
- Chased entries are invalidated with `maximum_entry_price_exceeded` so the next cycle can select again.

### Pulse changes

- Pulse validates the policy before changing ticker capital or submitting an order.
- Pulse validates it again against each broker's fresh executable ask immediately before live placement.
- A price above the ceiling returns `ENTRY_REJECTED_MAXIMUM_ENTRY_PRICE`.
- The audit record retains preflight and fresh-quote execution measurements.

### Why it may improve profitability

Correct direction does not guarantee a profitable entry. Preventing price chasing preserves the intended reward/risk ratio and separates forecast quality from execution quality.

### Success measures

- P&L of prevented chased entries.
- Reward/risk at decision price versus executable price.
- Frequency of stale or extended authorizations.
- Counterfactual return after a rejected entry.

## EXP-006 — Forecast, setup, and trigger entry

**Status:** Edge state machine and Pulse execution styles implemented on `OC-Iteration`.

### Edge changes

- Add the durable `edge.entry_timing.v1` state machine with `forecast`, `setup`, `triggered`, `expired`, and `invalidated` states.
- Confirmed resistance breakouts can trigger in one cycle because structure already supplies the setup and trigger.
- Trend and continuation forecasts must approach support or EMA within `EDGE_ENTRY_SETUP_PROXIMITY_ATR`, then reclaim by `EDGE_ENTRY_TRIGGER_RECLAIM_ATR` with improving signal and sufficient confidence.
- Persist setup observations across complete portfolio cycles.
- Store ideal entry, trigger price, maximum price, timing reason, and trigger state in the trade card and Pulse entry policy.

### Pulse implementation

- Pullback and continuation theses prefer `passive_limit`.
- Ordinary trend entries prefer `timed_limit`.
- Confirmed ORB and squeeze breakouts prefer `breakout_stop_limit`.
- Style selection remains bounded by Edge's maximum price and minimum remaining expected value.

### Why it may improve profitability

The earlier replay entered near the first eligible bar. Requiring location plus confirmation should reduce extended purchases and false breakouts while preserving immediate but bounded execution for genuinely confirmed structure breaks.

### Success measures

- Entry slippage in R compared with immediate-entry counterfactuals.
- False-breakout loss rate.
- Missed winners caused by the trigger requirement.
- Net expectancy by entry trigger and execution style.

## EXP-007 — Time stop and capital recycling

**Status:** Measurement and optional enforcement implemented; default mode is `shadow`.

### Code changes

- Record confirmed-open time, observation count, current R, maximum favorable excursion, maximum adverse excursion, and observations/time required to reach +0.5R.
- Use strategy-specific default windows: 30 minutes for breakouts, 45 minutes for continuation/reversal patterns, and 60 minutes for broader trend trades.
- Generate a time-stop recommendation when the trade has not reached the configured progress target and current R remains weak after enough observations.
- Recommend `reduce_position` for stagnation and `sell` for severe negative stagnation.
- Preserve the measurements on the terminal outcome for later attribution.
- Expose modes through `EDGE_TIME_STOP_MODE=off|shadow|reduce|exit`; `shadow` is the default.
- Enforcement reuses the existing position-scoped, quantity-guarded supervision path and never overrides emergency or bearish invalidation actions.

### Why it may improve profitability

Stagnant positions consume scarce risk budget and can become losses without validating the original thesis. Measuring progress in R allows capital to be recycled based on thesis behavior rather than arbitrary clock time.

### Promotion evidence

- Compare shadow exit/reduction prices with actual later exits.
- Require positive net improvement after costs across multiple strategies and regimes.
- Confirm that time stops do not materially truncate trades that later exceed +1R or +2R.
- Tune windows from observed time-to-0.5R distributions rather than enabling enforcement from defaults alone.

## EXP-008 — Pulse execution-cost veto

**Status:** Typed veto implemented in `Sentinel-Pulse` on `OC-Iteration`.

### Code changes

- Add `edge.entry_policy.v1` to the existing `edge.execution_intent.v2` BUY contract without changing the public `edge.pulse.handoff.v1` envelope.
- Estimate spread, adverse movement from the Edge reference, configured fees, and a slippage buffer.
- Compare fresh executable cost with Edge's maximum cost allowance and minimum remaining expected value.
- Validate once before Pulse mutates strategy state and again against broker-native bid/ask immediately before live placement.
- Return structured outcomes for poor liquidity, price extension, slippage, expected-value erosion, and unavailable styles.
- Persist preflight, broker checks, selection, and rejection detail in `edge_entry_policy_audit`.

### Why it may improve profitability

Edge can identify a good thesis that is temporarily untradeable. Pulse should preserve the strategy edge instead of converting it into an expensive fill. Rechecking at the broker quote closes the gap between Edge's decision price and Pulse's actual executable market.

### Evaluation

- Measure gross signal expectancy, executable expectancy, and realized expectancy separately.
- Track defer/reject frequency by symbol, session, spread, broker, and style.
- Compare rejected-order counterfactual returns with accepted fills.
- Tune fee and slippage buffers from observed fill data.

## EXP-009 — Selected-versus-rejected counterfactual ledger

**Status:** Initial cycle-horizon ledger implemented.

### Code changes

- Persist one counterfactual record for every scored candidate, including selected and rejected opportunities.
- Mark each record at subsequent evaluation prices for the same symbol.
- Track horizon observations, marked return, maximum favorable excursion, and maximum adverse excursion.
- Compare average selected-candidate return with rejected-candidate return through `selection_edge_pct`.
- Expose the aggregate in portfolio profitability status and preserve the ledger across restarts.

### Next extension

- Close records at the selected trade's actual exit horizon in addition to the fixed cycle horizon.
- Attribute selection, entry timing, execution, sizing, time-stop management, and final exit separately.

### Why it may improve profitability

Executed trades alone cannot prove that ranking works. Counterfactual results show whether Edge selected the right opportunity and whether rejected trades were correctly avoided.

## EXP-010 — ORB and short-squeeze fusion

**Status:** Implemented on Edge `OC-Iteration`.

### Code changes

- Promote locked premarket and regular-session ORB ranges into `edge.orb.evidence.v1` inside the authoritative enhanced analysis.
- Preserve 5-, 15-, and 30-minute confirmation details without adding a second execution path.
- Add durable `edge.squeeze.snapshot.v1` ingestion with timestamp, expiry, deduplication, and bounded pressure components.
- Compute squeeze pressure from short float, days to cover, borrow rate, utilization, borrow availability, gamma context, and catalysts.
- Require price/volume confirmation before a squeeze can become `triggering`; pressure alone remains `watch` or `armed` and cannot authorize a BUY.
- Fuse ORB, squeeze, pattern, volume, MTF, and structure evidence once, with bounded adjustments to avoid double-counting chart patterns or volume.
- Create the explicit `short_squeeze_breakout` strategy when pressure, ORB or bullish structure, and volume confirm together.
- Persist ORB, squeeze, and fusion metadata in ticker state, decision history, trade thesis, trade card, and Pulse entry policy.

### Why it may improve profitability

Short interest represents stored buying pressure, not timing. ORB and price structure identify whether that pressure has begun to release. Combining the distinct evidence families should avoid buying high-short-interest names that never trigger while recognizing session-specific breakouts that ordinary chart patterns cannot fully describe.

### Risks and guardrails

- Short-interest data can be delayed, so every snapshot expires and carries its observation time.
- A high squeeze score never bypasses regime, EV, reward/risk, correlation, timing, maximum-price, or execution-cost gates.
- Bearish structure blocks the squeeze trigger.
- The fused signal adjustment is bounded and records its ORB and squeeze components separately.

### Success measures

- Net expectancy of `short_squeeze_breakout` versus ordinary breakout trades.
- Triggered versus armed-only counterfactual returns.
- False-breakout rate after returning inside the ORB.
- Contribution of short-float, days-to-cover, borrow, gamma, and catalyst components by regime.
- Performance by ORB timeframe and premarket versus regular-session confirmation.

## EXP-011 — Pulse execution-style selection and attribution

**Status:** Implemented on Pulse `OC-Iteration`; promotion remains evidence-driven.

### Code changes

- Add `edge.execution_style.v1` inside the existing entry policy.
- Select among `passive_limit`, `timed_limit`, and `breakout_stop_limit` from thesis urgency and confirmation.
- Recompute exact prices from fresh broker quotes while preserving Edge's maximum entry.
- Poll timed limit and breakout stop-limit orders until the configured deadline, then cancel unfilled remainder on Alpaca and Tradier.
- Keep passive limits pending and reconciliation-safe rather than pretending submission is a fill.
- Persist style, arrival quote, limit, stop, timeout, fill price, fill quantity, and slippage.
- Classify zero-fill canceled, expired, rejected, deferred, or failed attempts as missed fills.
- Mark post-fill price movement once at 30, 60, and 300 seconds.
- Write attribution to the ticker, trade, broker-order ledger, and dedicated `execution_attributions` collection.

### Why it may improve profitability

Different theses require different urgency. A pullback setup can benefit from price improvement, an ordinary trend entry may need a short bounded attempt, and an ORB or squeeze breakout should activate only beyond its trigger. Separating styles allows Pulse to preserve Edge's alpha while measuring the cost of urgency.

### Promotion evidence

Compare each style on:

- Net expectancy after spread, slippage, fees, and missed opportunities.
- Median, 90th-percentile, and worst fill slippage.
- Fill, partial-fill, cancellation, reconciliation, and missed-fill rates.
- Post-fill movement at 30, 60, and 300 seconds.
- Adverse selection after aggressive fills.
- Results by strategy, symbol liquidity, market regime, ORB timeframe, and squeeze state.

A style is not promoted because it fills more often. It must improve net expectancy after the value of missed and avoided trades is included.

## Promotion checklist

An experiment is eligible for promotion only when it has:

- Positive walk-forward net expectancy after costs.
- Better drawdown-adjusted performance than the current champion.
- Results across more than one market regime.
- Sufficient trade count for the decision being made.
- No position lifecycle, stop ownership, idempotency, or reconciliation failures.
- Separate attribution for Edge selection, entry timing, Pulse execution, time-stop management, and final exit.
