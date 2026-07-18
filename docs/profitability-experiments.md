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

### Risks

- Over-concentration in one erroneous signal.
- Candidate scores may not be well calibrated yet.
- A full sweep can increase data-provider load.
- Fast WebSocket moves can change ranking immediately after the sweep.

### Guardrails

- Existing per-trade and portfolio risk budgets remain active.
- The winning trade still requires regime approval, confidence, reward/risk, and expected-value approval.
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

**Status:** Edge preflight implemented; Pulse enforcement still required.

### Edge changes

- Trade cards already calculate `maximum_entry_price` from entry risk distance.
- The portfolio runtime now rechecks price immediately before releasing the winner.
- Chased entries are invalidated with `maximum_entry_price_exceeded` so the next cycle can select again.

### Pulse changes requested

- Reject or defer a fill when current executable price exceeds `maximum_entry_price`.
- Return `THESIS_APPROVED_PRICE_TOO_EXTENDED` rather than treating it as a strategy rejection.
- Record decision price, arrival price, fill price, and slippage.

### Why it may improve profitability

Correct direction does not guarantee a profitable entry. Preventing price chasing preserves the intended reward/risk ratio and separates forecast quality from execution quality.

## EXP-006 — Setup trigger and pullback entry

**Status:** Planned.

### Proposed Edge changes

- Separate forecast, setup, and trigger state in the trade card.
- Add `entry_zone_low`, `entry_zone_high`, `trigger_type`, and `trigger_deadline`.
- Do not create an executable BUY solely because trend is bullish.

### Proposed Pulse changes

- Support passive limit, breakout stop-limit, and pullback-entry policies.
- Report `ENTRY_DEFERRED_TRIGGER_NOT_MET` without closing the thesis.

### Why it may improve profitability

The historical replay entered near the first eligible bar. Triggered entries should reduce late or extended purchases and false breakouts.

## EXP-007 — Time stop and capital recycling

**Status:** Planned after EXP-001 has enough paper observations.

### Proposed changes

- Store maximum favorable excursion, maximum adverse excursion, bars held, and time-to-0.5R.
- Exit or reduce when a setup fails to reach 0.5R inside its strategy-specific time window.
- Re-rank the capital against current candidates before exiting.

### Why it may improve profitability

Stagnant positions consume scarce risk budget and can become losses without ever validating the original thesis. Time stops recycle capital into stronger opportunities.

## EXP-008 — Pulse execution-cost veto

**Status:** Planned in `Sentinel-Pulse`.

### Proposed changes

- Calculate spread, estimated slippage, and fill probability before order submission.
- Compare execution cost with the Edge-provided cost allowance.
- Defer or cancel when expected cost erases the remaining expected value.
- Return structured reasons such as `ENTRY_DEFERRED_POOR_LIQUIDITY` and `ENTRY_REJECTED_SLIPPAGE_LIMIT`.

### Why it may improve profitability

Edge can identify a good thesis that is temporarily untradeable. Pulse should preserve the strategy edge instead of converting it into an expensive fill.

## EXP-009 — Selected-versus-rejected counterfactual ledger

**Status:** Initial cycle-horizon ledger implemented.

### Code changes

- Persist one counterfactual record for every scored candidate, including selected and rejected opportunities.
- Mark each record at subsequent evaluation prices for the same symbol.
- Track horizon observations, marked return, maximum favorable excursion, and maximum adverse excursion.
- Compare average selected-candidate return with rejected-candidate return through `selection_edge_pct`.
- Expose the aggregate in portfolio profitability status and preserve the ledger across restarts.

### Next extension

- Close records at the selected trade’s actual exit horizon in addition to the fixed cycle horizon.
- Attribute selection, entry timing, execution, sizing, and exit management separately.

### Why it may improve profitability

Executed trades alone cannot prove that ranking works. Counterfactual results show whether Edge selected the right opportunity and whether rejected trades were correctly avoided.

## Promotion checklist

An experiment is eligible for promotion only when it has:

- Positive walk-forward net expectancy after costs.
- Better drawdown-adjusted performance than the current champion.
- Results across more than one market regime.
- Sufficient trade count for the decision being made.
- No position lifecycle, stop ownership, idempotency, or reconciliation failures.
- Separate attribution for Edge selection and Pulse execution.
