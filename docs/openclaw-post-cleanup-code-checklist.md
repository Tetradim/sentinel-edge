# OpenClaw Code Check Checklist: Post Runtime Mock Cleanup

Date: 2026-06-07
Branch: OC-Iteration

## P2 Status

- [x] Volume anomaly z-score is implemented in `backend/signals.py`, exported through metrics, used by `backend/scheduler.py`, and exposed in ticker state.
- [x] P&L UI no longer uses static local values. `PnLTracking.tsx` reads `/api/pulse/account` and shows an unavailable state when Pulse has no account data.
- [x] Static Broker Health panel is removed. `AdvisorHealth.tsx` uses live Edge stats, Pulse status, automation status, and provider health.
- [x] Add/remove ticker UI remains in `TradingOverview.tsx` and calls live backend routes.

## Post-Deletion Checks

- [x] Deleted runtime fake-data modules are guarded by `backend/tests/test_no_runtime_mock_demo_data_static.py`.
- [x] Removed references from active app code to the deleted mock-data module, mock mode state, paper trading routes, and the deleted simulator module.
- [x] Updated stale docs that listed deleted mock/paper modules as current architecture.
- [x] Verified the frontend production build after removing the deleted components.
- [x] Verified changed backend files compile.

## Second-Pass Hidden Check

- [x] Re-scanned active backend/frontend/docs for deleted dashboard/module/API names after the 3,500-line cleanup.
- [x] Removed stale historical test reports that described deleted mock mode as current behavior.
- [x] Replaced legacy README quick-start text that still described paper-trading startup as the default local path.
- [x] Confirmed remaining deleted-name references are only in the static guard test that prevents those names from returning.
- [x] Confirmed remaining Blink hits are CSS/browser terms (`BlinkMacSystemFont`, caret blink animation), not Blink AI tags.
- [x] Confirmed remaining paper-trading wording is only generic risk-disclaimer language or cleanup-handoff history, not runtime code.

## Verification Notes

- [x] `python -m unittest backend.tests.test_no_runtime_mock_demo_data_static backend.tests.test_p1_regression_static`
- [x] Backend Python compile check over `backend/**/*.py`
- [x] `npm.cmd run build` from `frontend`
- [x] `git diff --check`
- [x] Full `backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests` passes after installing the declared dev-test dependency (`pytest==9.0.2`) into the backend virtualenv.

## Intentionally Kept

- [x] `DEMO_MODE` / standalone no-Mongo plumbing remains. This is runtime resilience infrastructure, not generated market data.
- [x] Test-only fakes remain in tests where they isolate external services.
- [x] Backtesting replay remains available for future controlled scenario testing; fake naming was removed from the runtime scan path.

## Follow-Up Candidates

- [ ] Implement Approach A: controlled backend pattern scenario engine.
- [ ] Decide whether to rename `DEMO_MODE` to `STANDALONE_MODE` in a separate compatibility pass.
- [x] Removed historical test reports that described deleted mock mode as current behavior.
