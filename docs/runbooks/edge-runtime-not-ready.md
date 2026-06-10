# Edge Runtime Not Ready

## What Fired

`EdgeRuntimeNotReady` means `edge_readiness_status` stayed at `0` for at least 2 minutes.

`EdgeReadinessCheckFailed` means one named dependency in `edge_readiness_check_status{check="..."}` stayed at `0` for at least 2 minutes. Use the alert's `check` label as the first dependency to inspect.

The alert is based on `/api/ready`, which reports fixed dependency checks through `edge_readiness_check_status{check="..."}`. `/api/health` can still prove the process is reachable, but `/api/ready` is the signal for whether Edge is usable by launchers, monitors, and automation.

## Impact

Edge may be accepting HTTP requests while one or more runtime dependencies are missing or stalled. Do not enable live automation until readiness returns to `1`, because scheduler, market-data, analyst, or persistence dependencies may not be wired correctly.

## First Checks

1. Open the Grafana `Broker Health` dashboard and inspect `Edge Readiness Checks`.
2. Query the ready endpoint:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8001/api/ready
   ```

3. Read the detailed readiness blockers. `/api/ready` returns HTTP 503 while Edge is not ready, so capture the error body and inspect `detail.failing_check_details` for the check name, operator label, and description:

   ```powershell
   $payload = try {
     Invoke-RestMethod http://127.0.0.1:8001/api/ready
   } catch {
     $_.ErrorDetails.Message | ConvertFrom-Json
   }
   $detail = if ($payload.detail) { $payload.detail } else { $payload }
   $detail.failing_check_details | Select-Object name, label, description
   ```

4. Identify the failing checks from Prometheus:

   ```promql
   edge_readiness_check_status == 0
   ```

5. Confirm the overall runtime state:

   ```promql
   edge_readiness_status
   ```

## Triage

If `scheduler_initialized` is `0`, startup did not finish wiring the evaluation scheduler. Check the backend log for import errors, configuration failures, or exceptions before `EvaluationScheduler(...)` is created.

If `scheduler_running` or `scheduler_task_alive` is `0`, the scheduler loop stopped or crashed after startup. Check recent backend logs around `Scheduler fatal error`, then keep automation paused until the scheduler is running again.

If `price_fetcher_initialized` is `0`, market-data setup failed before the scheduler could receive a `PriceFetcher`. Check provider configuration, missing dependencies, and recent edits to `backend/price_fetcher.py` or provider modules.

If `analyst_initialized` is `0`, the Sentinel Edge analyst orchestrator was not created. Check MongoDB startup behavior, analyst plugin import errors, and `analyst.core` initialization logs.

If `mongo_available` is `0`, Edge is running outside demo mode and MongoDB is unavailable. Either restore MongoDB connectivity or start local development with demo mode enabled through `Launch-Sentinel-Edge-Local.ps1`.

## Mitigation

1. Pause automation before restarting or changing runtime dependencies.
2. If this is local development, launch with `Launch-Sentinel-Edge-Local.ps1` so the script waits on `/api/ready` instead of only checking the port.
3. If this is a deployed environment, restart Edge only after confirming configuration and dependency availability. Restarting repeatedly without fixing the failing check can hide the root cause.
4. Keep `EdgeRuntimeNotReady` active until `/api/ready` returns HTTP 200 and all dependency checks are `1`.

## Resolution

The incident is resolved when:

- `/api/ready` returns HTTP 200.
- `edge_readiness_status == 1`.
- No `edge_readiness_check_status` series is `0`.
- The scheduler is running and automation has been deliberately re-enabled, if it was paused during mitigation.
