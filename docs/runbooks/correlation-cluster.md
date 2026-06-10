# Correlation Cluster

## What Fired

`CorrelationBearishCluster` means Edge detected one or more bearish correlation clusters in the last 5 minutes:

```promql
increase(analyst_correlation_clusters_total{direction="bearish"}[5m]) > 0
```

`StrongCorrelationCluster` means more than one high-strength cluster is active:

```promql
analyst_correlation_clusters_total{strength="high"} > 1
```

Correlation clusters are emitted by `CorrelationEngine` when multiple symbols move in the same direction inside the configured rolling window.
Each cluster includes a `risk_recommendation` object with `action`, `priority`, `scope`, `trailing_stop_action`, and `operator_summary` fields so operators do not have to infer trailing-stop posture from strength thresholds alone.

## Impact

A bearish cluster can indicate broad market stress rather than an isolated ticker problem. A strong bullish or bearish cluster can also signal a broad regime shift. Single-symbol signals may be lower quality during clustered moves, and high-strength bearish clusters can trigger a Pulse override for global risk reduction.

## First Checks

Check current cluster and breadth state:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/correlation
```

Check automation state before changing risk:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/automation
```

Pause automation if bearish correlation overlaps with drawdown, stale data, or active emergency exits:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8001/api/control/pause
```

Confirm recent clusters by direction and strength:

```promql
sum by (direction, strength) (increase(analyst_correlation_clusters_total[15m]))
```

## Triage

1. Identify whether the cluster is bearish or bullish and whether `strength` is `medium` or `high`.
2. Review `/api/correlation` for affected symbols and breadth percentages before changing per-ticker settings.
3. Read `risk_recommendation.action` and `risk_recommendation.trailing_stop_action` before changing risk controls:
   - `tighten_trailing_global` / `tighten`: confirm global trailing-stop tightening and pause new long entries.
   - `review_trailing_stops` / `review`: inspect affected symbols before adding exposure.
   - `observe_momentum` / `maintain`: keep current trailing-stop policy while monitoring breadth.
4. If the cluster is high-strength bearish, confirm whether a Pulse override was sent or suppressed.
5. Check `backend/analyst/correlation/engine.py` for `window_sec`, `min_symbols`, `cooldown_sec`, and Pulse override behavior.
6. Compare affected symbols with active positions, drawdown alerts, consecutive-loss alerts, and recent market news.
7. If this coincides with `CriticalBearishCorrelation` or `BearishClusterOverride`, treat the critical alert as the controlling incident.

## Resolution

The incident is resolved when:

- No new bearish clusters are detected over the current cooldown window.
- `/api/correlation` no longer shows a broad bearish latest cluster.
- Any Pulse override or global risk reduction has been confirmed.
- Automation and ticker-level risk settings have been reviewed before resuming normal operation.

## Escalation

Escalate if bearish clusters repeat across multiple windows, if Pulse override delivery is unclear, if correlated drawdowns are active, or if Edge is still entering new long exposure during a high-strength bearish cluster.
